"""IL PRIMO MODELLO ADDESTRATO — LoRA su Qwen3-Embedding-4B, sulla pagina.

   DECISIONE DEL PI (23/09/2026, sera): il primo modello si addestra. Il
   tentativo del 22/09 era su e5 (`addestra_recupero.py`) e non ha spostato
   niente (§57.3); Qwen3-Embedding, il modello che lo sostituisce (§60.1),
   non era mai stato addestrato.

   CHE COSA CAMBIA RISPETTO AL TENTATIVO SU e5.
   1. PIU' DOMANDE. Su e5 le domande erano le sole sonde: 10 testi, un passo
      per sonda per epoca. Qui ogni sonda porta con se' le sue formulazioni di
      ripresa — le 20 inventate e le 20 ricavate dai testi veri — e ciascuna
      e' una domanda di addestramento con gli stessi confermati e bocciati.
      Da 10 domande a circa 210: e' la cosa che mancava.
   2. PIU' NEGATIVI DIFFICILI. Oltre ai passaggi bocciati dai validatori, le
      formulazioni CONCORRENTI (stessa conclusione, altra fonte) entrano come
      documenti da tenere lontani: e' esattamente il guasto da correggere.
   3. LA PAGINA, NON IL FRAMMENTO. L'indice con Qwen non esiste ancora e va
      costruito comunque sulle pagine (§60.2): adattare anche il lato dei
      documenti non costa un indice in piu'.

   CONTRO IL BARARE. Solo righe di ADDESTRAMENTO; le formulazioni ricavate
   vengono da ancore delle sole righe di addestramento. Si misura sulle righe
   di PROVA con la sola proposizione originale, come il sistema di oggi, e col
   tetto della domanda ideale (§57.3).
"""
import argparse, collections, json, pathlib, random, time
import numpy as np

QUI = pathlib.Path(__file__).resolve().parent.parent
MODELLO = 'Qwen/Qwen3-Embedding-4B'
# LA GARA (§63, 25/09/2026): la stessa ricetta sugli sfidanti. nome -> (modello, pooling, prefisso domanda, prefisso pagina).
# Ogni modello col formato che dichiara la sua scheda: Nemotron vuole «query:»/«passage:» e la media dei token.
MODELLI = {
    'qwen4b': ('Qwen/Qwen3-Embedding-4B', 'ultimo', 'Instruct: {ISTR}\nQuery:', ''),
    'harrier06b': ('microsoft/harrier-oss-v1-0.6b', 'ultimo', 'Instruct: {ISTR}\nQuery: ', ''),
    'nemotron8b': ('nvidia/Nemotron-3-Embed-8B-BF16', 'media', 'query: ', 'passage: '),
    # Qwen3-VL-Embedding: il testo va nel formato di conversazione (istruzione come sistema, testo come utente)
    'qwen3vl8b': ('Qwen/Qwen3-VL-Embedding-8B', 'ultimo', 'CHAT:{ISTR}', "CHAT:Represent the user's input."),
    # Perplexity: Qwen3 reso bidirezionale, media dei token, nessun prefisso; codice suo (trust_remote_code)
    'pplx4b': ('perplexity-ai/pplx-embed-v1-4b', 'media', '', ''),
}
ISTR = ('Given a legal proposition established in a specific court judgment, retrieve passages from other '
        'cases that adopt this same line of reasoning as their own, not passages that merely discuss the '
        'same topic or that derive a similar conclusion from other legal sources')


def carica(parte):
    p = QUI/'training'/f'urgenda_decisione_{parte}_corrette_larghe.jsonl'
    return [x for x in (json.loads(r) for r in p.read_text(encoding='utf-8').splitlines() if r.strip())
            if x['frammento'] and x.get('finestra')]


def auc(y, s):
    y = np.asarray(y); s = np.asarray(s, float)
    o = np.argsort(s); r = np.empty(len(s)); r[o] = np.arange(1, len(s)+1)
    for v in np.unique(s):
        m = s == v
        if m.sum() > 1:
            r[m] = r[m].mean()
    p, n = y.sum(), len(y)-y.sum()
    return float((r[y == 1].sum()-p*(p+1)/2)/(p*n)) if p and n else float('nan')


def prime(y, s, k):
    return float(np.asarray(y)[np.argsort(-np.asarray(s, float))[:k]].mean())


def tetto(tr, te, Vtr, Vte):
    g = collections.defaultdict(lambda: {'tr': [], 'te': []})
    for i, x in enumerate(tr): g[x['sonda_titolo']]['tr'].append(i)
    for i, x in enumerate(te): g[x['sonda_titolo']]['te'].append(i)
    ya, sa = [], []
    for v in g.values():
        ytr = np.array([tr[i]['etichetta'] for i in v['tr']]); yte = np.array([te[i]['etichetta'] for i in v['te']])
        if not v['te'] or len(ytr) == 0 or ytr.sum() in (0, len(ytr)) or yte.sum() in (0, len(yte)):
            continue
        d = Vtr[v['tr']][ytr == 1].mean(0) - Vtr[v['tr']][ytr == 0].mean(0); d /= np.linalg.norm(d)
        ya += list(yte); sa += list(Vte[v['te']] @ d)
    return auc(ya, sa)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--epoche', type=int, default=4)
    ap.add_argument('--lr', type=float, default=5e-5)
    ap.add_argument('--rango', type=int, default=16)
    ap.add_argument('--maxlen', type=int, default=2048)
    ap.add_argument('--negativi', type=int, default=7)
    ap.add_argument('--temperatura', type=float, default=0.05)
    ap.add_argument('--semi', default='1,2,3')
    ap.add_argument('--unita', default='finestra', choices=['finestra', 'pagina_piu_mezza', 'finestra_larga'],
                    help='la pagina (di serie), la pagina con la successiva, la pagina con quella prima e dopo: '
                         'la prova delle unita\' (§60.2) rifatta col modello addestrato, su richiesta del PI')
    ap.add_argument('--solo-domanda', action='store_true',
                    help='adatta solo il lato della domanda: le pagine restano codificate dal modello di base, '
                         'quindi l indice si costruisce una volta e non va rifatto a ogni riaddestramento')
    ap.add_argument('--modello', default='qwen4b', choices=list(MODELLI))
    ap.add_argument('--inizio', default='', help='cartella di un adattatore da cui partire (es. quello addestrato sulle citazioni) invece che da zero')
    ap.add_argument('--etichetta', default='', help='suffisso dei file di uscita')
    ap.add_argument('--senza-formulazioni', action='store_true', help='solo le sonde come domande, per confronto')
    a = ap.parse_args()

    import torch, torch.nn.functional as F
    from transformers import AutoTokenizer, AutoModel
    from peft import LoraConfig, get_peft_model
    dev = 'cuda'
    global MODELLO
    MODELLO, POOL, PQ, PD = MODELLI[a.modello]; PQ = PQ.replace('{ISTR}', ISTR)
    tok = AutoTokenizer.from_pretrained(MODELLO, padding_side='left', trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    tr, te = carica('addestramento'), carica('prova')
    y_te = np.array([x['etichetta'] for x in te])
    base_id = lambda x: x['sonda_id'].split('__')[0]
    print(f'addestramento {len(tr)} ({sum(x["etichetta"] for x in tr)} vere) | prova {len(te)} ({y_te.sum()} vere)', flush=True)

    # domande per sonda: il testo della sonda (e la seconda formulazione) piu' le riprese
    fable = json.loads((QUI/'training'/'formulazioni_fable.json').read_text(encoding='utf-8'))
    der = json.loads((QUI/'training'/'formulazioni_derivate.json').read_text(encoding='utf-8'))
    gruppi = collections.defaultdict(lambda: {'domande': set(), 'si': [], 'no': [], 'concorrenti': []})
    for x in tr:
        g = gruppi[base_id(x)]
        g['domande'].add(x['sonda_testo'])
        g['si' if x['etichetta'] else 'no'].append(x[a.unita])
    if not a.senza_formulazioni:
        for sid, g in gruppi.items():
            g['domande'] |= {t if isinstance(t, str) else t['testo'] for t in fable.get(sid, {}).get('ripresa', [])}
            g['domande'] |= {f['testo'] for f in der.get(sid, {}).get('ripresa', [])}
    for sid, g in gruppi.items():
        g['concorrenti'] = [t if isinstance(t, str) else t['testo'] for t in fable.get(sid, {}).get('concorrenti', [])]
        g['concorrenti'] += [f['testo'] for f in der.get(sid, {}).get('concorrenti', [])]
    esempi = [(sid, q) for sid, g in gruppi.items() if g['si'] and g['no'] for q in g['domande']]
    print('domande per sonda:', {k: len(v['domande']) for k, v in gruppi.items()}, f'-> {len(esempi)} passi per epoca', flush=True)

    def codifica(modello, testi, domanda, grad=False, batch=4):
        fuori = []
        for i in range(0, len(testi), batch):
            pre = PQ if domanda else PD
            if pre.startswith('CHAT:'):
                istr = pre[5:].strip(); istr = istr if istr.endswith(('.', '?', '!')) else istr + '.'
                pezzo = [tok.apply_chat_template([{'role': 'system', 'content': istr}, {'role': 'user', 'content': t}],
                                                 tokenize=False, add_generation_prompt=True) for t in testi[i:i+batch]]
            else:
                pezzo = [pre + t for t in testi[i:i+batch]]
            enc = tok(pezzo, padding=True, truncation=True, max_length=a.maxlen, return_tensors='pt').to(dev)
            with torch.set_grad_enabled(grad), torch.autocast('cuda', dtype=torch.bfloat16):
                hs = modello(**enc).last_hidden_state
                if POOL == 'media':
                    k = enc['attention_mask'].unsqueeze(-1).to(hs.dtype); h = (hs*k).sum(1)/k.sum(1)
                else:
                    h = hs[:, -1]
            fuori.append(F.normalize(h.float(), dim=-1))
        return torch.cat(fuori)

    def docs(modello, testi, grad=False):
        if a.solo_domanda and hasattr(modello, 'disable_adapter'):
            with modello.disable_adapter():
                return codifica(modello, testi, False, grad=False).detach()
        return codifica(modello, testi, False, grad=grad)

    def misura(modello, etichetta):
        modello.eval()
        sonde = sorted({x['sonda_testo'] for x in tr + te})
        with torch.no_grad():
            Q = dict(zip(sonde, codifica(modello, sonde, True).cpu().numpy()))
            Vtr = docs(modello, [x[a.unita] for x in tr]).cpu().numpy()
            Vte = docs(modello, [x[a.unita] for x in te]).cpu().numpy()
        s = [float(Q[x['sonda_testo']] @ Vte[i]) for i, x in enumerate(te)]
        t = tetto(tr, te, Vtr, Vte)
        print(f'  {etichetta:40s} AUC {auc(y_te, s):.3f}   prime 20 {100*prime(y_te, s, 20):3.0f}%   prime 40 {100*prime(y_te, s, 40):3.0f}%   tetto {t:.3f}', flush=True)
        return s

    base = AutoModel.from_pretrained(MODELLO, torch_dtype=torch.bfloat16, trust_remote_code=True).to(dev)
    esiti = {'ids': [x['id'] for x in te], 'non_addestrato': misura(base, 'non addestrato')}
    del base; torch.cuda.empty_cache()

    for seme in [int(s) for s in a.semi.split(',')]:
        random.seed(seme); torch.manual_seed(seme)
        m = AutoModel.from_pretrained(MODELLO, torch_dtype=torch.bfloat16, trust_remote_code=True)
        m.gradient_checkpointing_enable(); m.enable_input_require_grads()
        if a.inizio:
            from peft import PeftModel
            m = PeftModel.from_pretrained(m, a.inizio.replace('{seme}', str(seme)), is_trainable=True).to(dev)
        else:
            m = get_peft_model(m, LoraConfig(r=a.rango, lora_alpha=2*a.rango, lora_dropout=0.1,
                                              target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj'])).to(dev)
        opt = torch.optim.AdamW([p for p in m.parameters() if p.requires_grad], lr=a.lr)
        for ep in range(1, a.epoche+1):
            m.train(); t0 = time.time(); somma = 0.0
            random.shuffle(esempi)
            for sid, q in esempi:
                g = gruppi[sid]
                pos = random.choice(g['si'])
                cand = [(d, 'no') for d in g['no']] + [(d, 'conc') for d in g['concorrenti']]
                neg = [d for d, _ in random.sample(cand, min(a.negativi, len(cand)))]
                vq = codifica(m, [q], True, grad=True)
                vd = docs(m, [pos] + neg, grad=True)
                l = F.cross_entropy((vq @ vd.T) / a.temperatura, torch.tensor([0], device=dev))
                l.backward(); opt.step(); opt.zero_grad(); somma += l.item()
            print(f'seme {seme} passata {ep}: perdita {somma/len(esempi):.3f} [{time.time()-t0:.0f}s]', flush=True)
            esiti[f'seme{seme}_passata{ep}'] = misura(m, f'seme {seme} dopo passata {ep}')
            m.save_pretrained(QUI/'training'/f'lora_primo_{"qwen4b" if a.modello == "qwen4b" else a.modello}{"_senzaform" if a.senza_formulazioni else ""}{"" if a.unita == "finestra" else "_" + a.unita}{"_solodomanda" if a.solo_domanda else ""}{a.etichetta}_{seme}'/f'passata_{ep}')
        del m, opt; torch.cuda.empty_cache()

    semi = [int(s) for s in a.semi.split(',')]
    for ep in range(1, a.epoche+1):
        s = np.mean([np.argsort(np.argsort(esiti[f'seme{k}_passata{ep}'])) for k in semi], 0)
        print(f'  semi insieme dopo {ep} passate            AUC {auc(y_te, s):.3f}   prime 20 {100*prime(y_te, s, 20):3.0f}%', flush=True)
    nome = 'esiti_primo_' + ('qwen4b' if a.modello == 'qwen4b' else a.modello) + ('_senzaform' if a.senza_formulazioni else '') + ('' if a.unita == 'finestra' else '_' + a.unita) + ('_solodomanda' if a.solo_domanda else '') + a.etichetta + '.json'
    (QUI/'training'/nome).write_text(json.dumps(esiti), encoding='utf-8')


if __name__ == '__main__':
    main()
