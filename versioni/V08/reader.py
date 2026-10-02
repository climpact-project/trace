"""TRACE-READER: UN MODELLO NOSTRO, PICCOLO, CHE FA IL LAVORO DI DEEPSEEK SULLE CITAZIONI (27/09/2026).

   PERCHE'. Nel sistema nuovo (§63.25) DeepSeek legge ogni citazione esplicita e propone: se e' davvero il caso,
   il tipo di citazione, chi parla, la proposizione, i principi presi, con un commento. DeepSeek e' enorme (149 GB
   di pesi) e non si puo' consegnare ne' addestrare. Il PI ha chiesto un modello nostro: Qwen3-14B con un
   adattatore LoRA, addestrato prima sulle letture di DeepSeek (distillazione, da dichiarare) e poi sulle
   correzioni del team.

   REGOLA FISSATA PRIMA. Il Reader si misura sulle stesse righe di prova di DeepSeek (le citazioni lessicali di
   Urgenda con un tipo dato dalle persone, 317). Se eguaglia o supera DeepSeek, fa lui le proposte; se no, le fa
   DeepSeek e il Reader resta un esperimento documentato con il suo numero.

   PULIZIA. Nessuna riga di prova entra nell'addestramento, e il maestro e' solo DeepSeek (mai i giudizi delle
   persone sulle righe di prova). Si usano solo le righe in cui le due letture di DeepSeek danno lo stesso tipo.
   Escludere anche i documenti della prova lascerebbe 305 righe su 1.678 (i documenti con molte citazioni stanno
   quasi tutti nella prova): con `--escludi-documenti` si fa lo stesso, per misurare quanto conta.

   Fasi:
     dati      Mac  -> training/reader/urgenda_{addestramento,prova}.jsonl
     addestra  ReCaS, una GPU  -> training/reader/lora_reader_<etichetta>/
     valuta    ReCaS, una GPU  -> training/reader/valuta_<etichetta>.jsonl
"""
import argparse, collections, json, pathlib, random, re, sys
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
R = QUI/'training'/'reader'
MODELLO = 'Qwen/Qwen3-14B'
TAGLIO = 12000


def istruzioni(caso, v1=False):
    import yaml
    from classifica_lessicali import codebook
    _, tipi, chi, limiti = codebook()
    conf = yaml.safe_load(open(QUI/'cited-cases'/f'{caso}.yaml', encoding='utf-8'))
    princ = '\n'.join(f"- {s['id']}: {' '.join(s['titolo'].split())}" for s in conf['semantic_queries'])
    return (f"Codifichi una citazione del caso {conf.get('nome') or caso} in un atto di contenzioso climatico.\n"
            f"TIPI DI CITAZIONE:\n{tipi}\nCHI PARLA:\n{chi}\nREGOLE:\n{limiti}\nPRINCIPI DEL CASO:\n{princ}\n"
            "Il nome trovato e' marcato con ⟦ ⟧ dentro [[INIZIO DEL BRANO SEGNALATO]] ... [[FINE DEL BRANO SEGNALATO]].\n"
            'Rispondi SOLO con JSON: {"riferimento": "caso_urgenda|fondazione_urgenda|indice_o_elenco|omonimo|non_determinabile", '
            '"tipo_citazione": codice, "chi_parla": codice, "principi": [id o "nessuno" o "altro"], '
            '"proposizione": una frase, "motivo": una frase che giustifica le scelte'
            + (', "vicine": [{"pagina": numero, "prosegue": true o false}]}' if v1 else '}'))


def ritaglia(ctx):
    a = ctx.find('[[INIZIO DEL BRANO SEGNALATO]]')
    if a < 0 or len(ctx) <= TAGLIO:
        return ctx[:TAGLIO]
    da = max(0, a - TAGLIO // 2)
    return ctx[da: da + TAGLIO]


def testo_con_vicine(r, vicine, v1):
    t = ritaglia(r['contesto'])
    if not v1:
        return t
    pag = vicine.get(r['id'], [])
    if not pag:
        return t + '\n\nPAGINE VICINE: nessuna proposta.'
    return t + '\n\nPAGINE VICINE DELLO STESSO ATTO (dire quali proseguono la ripresa):\n' + '\n\n'.join(
        f"--- PAGINA {v['pagina']} ---\n{v['testo'][:2500]}" for v in pag)


def dati(caso, escludi_documenti=False, senza_principi=False, v1=False):
    righe = [json.loads(l) for l in open(QUI/'training'/f'lessicali_{caso}_righe.jsonl', encoding='utf-8')]
    ds = {json.loads(l)['id']: json.loads(l) for l in open(QUI/'training'/f'lessicali_{caso}_deepseek_v2.jsonl', encoding='utf-8')}
    rp = {}
    f = QUI/'training'/'principi'/f'{caso}_ripresa_deepseek.jsonl'
    if f.exists():
        rp = {json.loads(l)['id']: json.loads(l) for l in open(f, encoding='utf-8')}
    # v1 (28/09/2026): anche le pagine vicine proposte dal reranker, e nel bersaglio quali proseguono la ripresa.
    vicine = {}
    fv = QUI/'training'/'principi'/f'{caso}_ripresa_righe.jsonl'
    if v1 and fv.exists():
        vicine = {json.loads(l)['id']: json.loads(l)['vicine'] for l in open(fv, encoding='utf-8')}
    prova = [r for r in righe if (r.get('umano') or {}).get('validato_tipo_citazione')]
    doc_prova = {r['document_id'] for r in prova}
    ist = istruzioni(caso, v1)
    R.mkdir(parents=True, exist_ok=True)
    n = collections.Counter()
    suf = '_v1' if v1 else ''
    with open(R/f'{caso}_addestramento{suf}.jsonl', 'w', encoding='utf-8') as fa:
        for r in righe:
            if r in prova or (escludi_documenti and r['document_id'] in doc_prova):
                n['esclusa (prova o suo documento)'] += 1; continue
            d = ds.get(r['id'])
            if not d or len(d['letture']) < 2:
                n['senza lettura'] += 1; continue
            l1, l2 = d['letture'][0], d['letture'][1]
            if not l1.get('tipo_citazione') or l1.get('tipo_citazione') != l2.get('tipo_citazione'):
                n['letture discordi (escluse)'] += 1; continue
            pr = ((rp.get(r['id']) or {}).get('letture') or [{}])[0]
            principi = [p for p in (pr.get('principi') or []) if isinstance(p, str)] if isinstance(pr, dict) else []
            if senza_principi:
                principi = None
            bersaglio = {'riferimento': l1.get('riferimento') or 'caso_urgenda', 'tipo_citazione': l1['tipo_citazione'],
                         'chi_parla': l1.get('chi_parla') or 'non_determinabile', 'principi': principi,
                         'proposizione': ' '.join(str(l1.get('proposizione') or '').split()),
                         'motivo': ' '.join(str(l1.get('motivo') or '').split())}
            if principi is None:
                bersaglio.pop('principi')
            if v1:
                cand = {v['pagina'] for v in vicine.get(r['id'], [])}
                bersaglio['vicine'] = [{'pagina': int(v['pagina']), 'prosegue': bool(v.get('prosegue'))}
                                       for v in (pr.get('vicine') or []) if isinstance(v, dict) and str(v.get('pagina', '')).isdigit()
                                       and int(v['pagina']) in cand]
            fa.write(json.dumps({'id': r['id'], 'istruzioni': ist, 'testo': testo_con_vicine(r, vicine, v1),
                                 'bersaglio': json.dumps(bersaglio, ensure_ascii=False)}, ensure_ascii=False) + '\n')
            n['addestramento'] += 1
    with open(R/f'{caso}_prova{suf}.jsonl', 'w', encoding='utf-8') as fp:
        for r in prova:
            fp.write(json.dumps({'id': r['id'], 'istruzioni': ist, 'testo': testo_con_vicine(r, vicine, v1),
                                 'umano': r['umano']['validato_tipo_citazione']}, ensure_ascii=False) + '\n')
            n['prova'] += 1
    print(dict(n), '->', R)


def messaggi(tok, x, con_risposta):
    m = [{'role': 'system', 'content': x['istruzioni']}, {'role': 'user', 'content': x['testo']}]
    pre = tok.apply_chat_template(m, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    return pre, (x['bersaglio'] + tok.eos_token) if con_risposta else None


def addestra(caso, etichetta, passate, lr, massimo):
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from peft import LoraConfig, get_peft_model
    random.seed(0); torch.manual_seed(0)
    tok = AutoTokenizer.from_pretrained(MODELLO)
    m = AutoModelForCausalLM.from_pretrained(MODELLO, torch_dtype=torch.bfloat16, attn_implementation='sdpa').cuda()
    m.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False}); m.config.use_cache = False
    m = get_peft_model(m, LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, task_type='CAUSAL_LM',
                                     target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj']))
    m.enable_input_require_grads()
    # SENZA train() IL CHECKPOINTING NON SCATTA (gli strati lo applicano solo in addestramento): secondo lancio
    # finito ancora senza memoria per questo.
    m.train()
    suf = '_v1' if etichetta.startswith('v1') else ''
    X = [json.loads(l) for l in open(R/f'{caso}_addestramento{suf}.jsonl', encoding='utf-8')]
    opt = torch.optim.AdamW([p for p in m.parameters() if p.requires_grad], lr=lr)
    accumula = 8; passo = 0
    for ep in range(passate):
        random.shuffle(X); tot = 0.0
        for i, x in enumerate(X):
            pre, ris = messaggi(tok, x, True)
            a = tok(pre, add_special_tokens=False)['input_ids']; b = tok(ris, add_special_tokens=False)['input_ids']
            a = a[-(massimo - len(b)):] if len(a) + len(b) > massimo else a
            ids = torch.tensor([a + b]).cuda()
            # LA MEMORIA: i logit su tutto il testo (151.000 voci x 6.000 token) non stanno in una H100 accanto al
            # modello (primo lancio: esaurita). Il vocabolario si applica solo alle posizioni della risposta.
            h = m.base_model.model.model(input_ids=ids).last_hidden_state[:, len(a) - 1:-1]
            logit = m.base_model.model.lm_head(h).float()
            loss = torch.nn.functional.cross_entropy(logit.view(-1, logit.size(-1)), torch.tensor(b).cuda()) / accumula
            loss.backward(); tot += loss.item() * accumula
            if (i + 1) % accumula == 0:
                opt.step(); opt.zero_grad(); passo += 1
            if (i + 1) % 100 == 0:
                print(f'  passata {ep+1} riga {i+1}/{len(X)} perdita media {tot/(i+1):.4f}', flush=True)
        cart = R/f'lora_reader_{etichetta}'/f'passata_{ep+1}'
        cart.mkdir(parents=True, exist_ok=True); m.save_pretrained(str(cart))
        print(f'passata {ep+1} fatta, perdita {tot/len(X):.4f} -> {cart}', flush=True)


def valuta(caso, etichetta, passata):
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from peft import PeftModel
    tok = AutoTokenizer.from_pretrained(MODELLO, padding_side='left')
    m = AutoModelForCausalLM.from_pretrained(MODELLO, torch_dtype=torch.bfloat16).cuda()
    if etichetta != 'base':
        m = PeftModel.from_pretrained(m, str(R/f'lora_reader_{etichetta}'/f'passata_{passata}'))
    m.eval()
    suf = '_v1' if etichetta.startswith('v1') else ''
    X = [json.loads(l) for l in open(R/f'{caso}_prova{suf}.jsonl', encoding='utf-8')]
    out = open(R/f'valuta_{etichetta}_p{passata}.jsonl', 'w', encoding='utf-8')
    giusti = n = 0
    for i in range(0, len(X), 4):
        lotto = X[i:i+4]
        pre = [messaggi(tok, x, False)[0] for x in lotto]
        enc = tok(pre, return_tensors='pt', padding=True, add_special_tokens=False).to('cuda')
        with torch.no_grad():
            g = m.generate(**enc, max_new_tokens=600, do_sample=False)
        for x, seq in zip(lotto, g):
            testo = tok.decode(seq[enc['input_ids'].shape[1]:], skip_special_tokens=True)
            mm = re.search(r'\{.*\}', testo, re.S)
            try:
                j = json.loads(mm.group(0)) if mm else {}
            except Exception:
                j = {}
            tipo = j.get('tipo_citazione', '')
            n += 1; giusti += tipo == x['umano']
            out.write(json.dumps({'id': x['id'], 'umano': x['umano'], 'tipo': tipo, 'risposta': testo[:3000]}, ensure_ascii=False) + '\n')
        print(f'  {n}/{len(X)} accuratezza finora {giusti/n:.3f}', flush=True)
    print(json.dumps({'etichetta': etichetta, 'passata': passata, 'righe': n, 'accuratezza_tipo': round(giusti / max(n, 1), 3)}), flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('fase', choices=['dati', 'addestra', 'valuta'])
    ap.add_argument('--caso', default='urgenda'); ap.add_argument('--etichetta', default='v0')
    ap.add_argument('--passate', type=int, default=2); ap.add_argument('--passata', type=int, default=2)
    ap.add_argument('--escludi-documenti', action='store_true')
    ap.add_argument('--senza-principi', action='store_true', help='v0: solo tipo, chi parla, riferimento, proposizione, motivo')
    ap.add_argument('--v1', action='store_true', help='principi e pagine vicine')
    ap.add_argument('--lr', type=float, default=1e-4); ap.add_argument('--massimo', type=int, default=6144)
    a = ap.parse_args()
    if a.fase == 'dati':
        dati(a.caso, a.escludi_documenti, a.senza_principi, a.v1)
    elif a.fase == 'addestra':
        addestra(a.caso, a.etichetta, a.passate, a.lr, a.massimo)
    else:
        valuta(a.caso, a.etichetta, a.passata)
