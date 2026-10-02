"""DISTILLAZIONE: il riordinatore addestrato fa da maestro al primo modello — diario:
   DIARIO-ADDESTRAMENTO-CITAZIONI.md §5.

   IDEA. Il riordinatore (Qwen3-Reranker-4B + nostro adattatore, 0,787) legge sonda e pagina insieme
   ed e' piu' preciso ma lento; il primo modello e' veloce ma meno fine (0,74). Il maestro da' un voto
   a migliaia di pagine che nessuno ha giudicato; lo studente impara a riprodurre il suo ordine.
   SCORCIATOIA. Si addestra solo la domanda (§62.7): le pagine sono lette dal modello di base, e i
   loro vettori sono GIA' nell'indice delle pagine (§63.7). Lo studente si confronta con centinaia
   di pagine per passo invece di 8 (i «lotti grandi»), senza rileggerle.
   ANTI-BARARE. Dai candidati si tolgono i documenti delle righe di PROVA di Urgenda e gli atti di
   Urgenda stessa. Il maestro e' stato addestrato solo sulle righe di addestramento.

   Fasi (una GPU):  voti   il maestro vota le prime K pagine di ogni sonda  -> training/distilla/voti.json
                    studia lo studente impara dai voti (3 semi), misura sulle 133 righe di prova
"""
import argparse, gzip, json, pathlib, random, sys, time, collections
import numpy as np
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
_m_addestra_primo_qwen = __import__('067_addestra_primo_qwen')
carica = _m_addestra_primo_qwen.carica
auc = _m_addestra_primo_qwen.auc
prime = _m_addestra_primo_qwen.prime
ISTR = _m_addestra_primo_qwen.ISTR
D = QUI/'training'/'distilla'; D.mkdir(parents=True, exist_ok=True)
IDX = QUI/'index'/'pagine'
MOD = 'Qwen/Qwen3-Embedding-4B'
# nome -> (modello, pooling, prefisso della domanda, cartella dell'indice). Perplexity (26/09/2026): media dei
# token, nessun prefisso, indice suo (stesse pagine, stesso ordine di quello di Qwen).
MODELLI = {'qwen4b': ('Qwen/Qwen3-Embedding-4B', 'ultimo', 'Instruct: {ISTR}\nQuery:', 'pagine'),
           'pplx4b': ('perplexity-ai/pplx-embed-v1-4b', 'media', '', 'pagine_pplx4b')}


def indice(cartella='pagine'):
    V, ids = [], []
    d = QUI/'index'/cartella
    for i in range(4):
        V.append(np.load(d/f'vettori_{i}.npy')); ids += json.load(open(d/f'ids_{i}.json'))
    return np.concatenate(V), ids


def sonde_e_domande():
    """Per ogni sonda (id base): i suoi testi (sonde e seconda formulazione) e le formulazioni di ripresa."""
    tr, te = carica('addestramento'), carica('prova')
    base = lambda x: x['sonda_id'].split('__')[0]
    testi = collections.defaultdict(set)
    for x in tr + te:
        testi[base(x)].add(x['sonda_testo'])
    der = json.loads((QUI/'training'/'formulazioni_derivate.json').read_text(encoding='utf-8'))
    fab = json.loads((QUI/'training'/'formulazioni_fable.json').read_text(encoding='utf-8'))
    domande = {s: set(t) | {f['testo'] for f in der.get(s, {}).get('ripresa', [])}
               | {(f if isinstance(f, str) else f['testo']) for f in fab.get(s, {}).get('ripresa', [])} for s, t in testi.items()}
    return testi, domande, te


def esclusi(te):
    fuori = {x['document_id'] for x in te}
    return lambda doc: doc in fuori or doc.startswith('urgenda-foundation-v-state-of-the-netherlands')


def voti(k):
    import torch, torch.nn.functional as F
    from transformers import AutoTokenizer, AutoModel
    from peft import PeftModel
    _m_prova_riordinatori = __import__('027_prova_riordinatori')
    QwenRiordinatore = _m_prova_riordinatori.QwenRiordinatore
    ISTR_R = _m_prova_riordinatori.ISTR
    V, ids = indice(); Vt = torch.from_numpy(V).cuda()
    testi, domande, te = sonde_e_domande(); fuori = esclusi(te)
    tok = AutoTokenizer.from_pretrained(MOD, padding_side='left'); m = AutoModel.from_pretrained(MOD, torch_dtype=torch.bfloat16).cuda().eval()
    cand = {}
    with torch.no_grad():
        for s, ts in testi.items():
            for t in sorted(ts):
                e = tok([f'Instruct: {ISTR}\nQuery:{t}'], return_tensors='pt').to('cuda')
                q = F.normalize(m(**e).last_hidden_state[:, -1].float(), dim=-1).half()
                sc = (Vt @ q[0]).float().cpu().numpy(); ordine = np.argsort(-sc)
                presi = [int(i) for i in ordine[:3*k] if not fuori(ids[i].split('#')[0])][:k]
                cand.setdefault(s, set()).update(presi)
    del m, Vt; torch.cuda.empty_cache()
    serve = {i for v in cand.values() for i in v}; testo = {}
    with gzip.open(IDX/'pagine.jsonl.gz', 'rt', encoding='utf-8') as f:
        pos = {pid: n for n, pid in enumerate(ids)}
        for l in f:
            x = json.loads(l); n = pos.get(x['id'])
            if n in serve:
                testo[n] = x['testo']
    coppie = [(s, t, i) for s, v in cand.items() for i in sorted(v) for t in [sorted(testi[s])[0]]]
    print(f'sonde {len(cand)}, candidati {len(coppie)}', flush=True)
    punti = []
    for seme in (1, 2, 3):
        t0 = time.time(); q = QwenRiordinatore('Qwen/Qwen3-Reranker-4B')
        q.m = PeftModel.from_pretrained(q.m, str(QUI/'training'/f'lora_qwen_rr4b_{seme}'/'passata_2'))
        punti.append(q.punteggi([(t, testo[i]) for s, t, i in coppie], ISTR_R['ripresa'], 2560)); q.libera()
        print(f'  maestro seme {seme}: {time.time()-t0:.0f}s', flush=True)
    p = np.mean(punti, 0)
    json.dump([{'sonda': s, 'pagina': ids[i], 'riga': i, 'voto': float(v)} for (s, t, i), v in zip(coppie, p)],
              open(D/'voti.json', 'w'), indent=0)
    print('voti: sopra 0,5', int((p > .5).sum()), 'su', len(p), flush=True)


def studia(passate, semi, lista, poi_umani, maestri='rr', modello='qwen4b'):
    import torch, torch.nn.functional as F
    from transformers import AutoTokenizer, AutoModel
    from peft import LoraConfig, get_peft_model
    NOME, POOL, PQ, CART = MODELLI[modello]; PQ = PQ.replace('{ISTR}', ISTR)
    V, ids = indice(CART)
    pos = {pid: n for n, pid in enumerate(ids)}
    testi, domande, te = sonde_e_domande()
    vt = json.load(open(D/'voti.json'))
    for x in vt:                       # le righe dei voti sono dell'indice di Qwen: si rimappano per identificativo
        x['riga'] = pos[x['pagina']]
    ds = {}
    if maestri == 'rr+ds':
        # secondo maestro: DeepSeek 0731, frazione di letture «ripresa»; si media con il riordinatore
        for x in json.load(open(QUI/'training'/'deepseek_distilla_v4_distilla.json')):
            n = len(x['letture']) or 1
            ds[x['id']] = x['voti_ripresa'] / n
        print(f'voti di DeepSeek: {len(ds)}', flush=True)
    per = collections.defaultdict(list)
    for x in vt:
        v = x['voto'] if maestri == 'rr' else (x['voto'] + ds.get(f"{x['sonda']}|{x['pagina']}", x['voto'])) / 2
        per[x['sonda']].append((x['riga'], v))
    righe = {s: np.array([r for r, _ in v]) for s, v in per.items()}
    bersaglio = {s: torch.tensor([np.log(max(p, 1e-4) / max(1 - p, 1e-4)) for _, p in v], dtype=torch.float32) for s, v in per.items()}
    Vs = {s: torch.from_numpy(V[r].astype(np.float32)).cuda() for s, r in righe.items()}
    tok = AutoTokenizer.from_pretrained(NOME, padding_side='left', trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    y = np.array([x['etichetta'] for x in te])

    def pool(hs, mask):
        if POOL == 'media':
            mk = mask.unsqueeze(-1).to(hs.dtype); return (hs*mk).sum(1)/mk.sum(1)
        return hs[:, -1]
    esempi = [(s, d) for s in per for d in domande[s]]
    print(f'domande {len(esempi)}, pagine votate per sonda {[len(v) for v in per.values()]}', flush=True)

    def q_vec(m, testi_, grad):
        e = tok([PQ + t for t in testi_], padding=True, return_tensors='pt').to('cuda')
        with torch.set_grad_enabled(grad), torch.autocast('cuda', dtype=torch.bfloat16):
            h = pool(m(**e).last_hidden_state, e['attention_mask'])
        return F.normalize(h.float(), dim=-1)

    def misura(m, et):
        m.eval(); sonde = sorted({x['sonda_testo'] for x in te})
        with torch.no_grad():
            Q = dict(zip(sonde, q_vec(m, sonde, False).cpu().numpy()))
            with m.disable_adapter():
                P = []
                for i in range(0, len(te), 4):
                    e = tok([x['finestra'] for x in te[i:i+4]], padding=True, truncation=True, max_length=2048, return_tensors='pt').to('cuda')
                    with torch.autocast('cuda', dtype=torch.bfloat16):
                        P.append(F.normalize(pool(m(**e).last_hidden_state, e['attention_mask']).float(), dim=-1).cpu().numpy())
                P = np.concatenate(P)
        s = [float(Q[x['sonda_testo']] @ P[i]) for i, x in enumerate(te)]
        print(f'  {et:40s} AUC {auc(y, s):.3f}   prime 20 {100*prime(y, s, 20):3.0f}%   prime 40 {100*prime(y, s, 40):3.0f}%', flush=True)
        return s

    esiti = {}
    for seme in semi:
        random.seed(seme); torch.manual_seed(seme)
        m = AutoModel.from_pretrained(NOME, torch_dtype=torch.bfloat16, trust_remote_code=True)
        m.gradient_checkpointing_enable(); m.enable_input_require_grads()
        m = get_peft_model(m, LoraConfig(r=16, lora_alpha=32, lora_dropout=0.1, target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj'])).cuda()
        if seme == semi[0]:
            esiti['non_addestrato'] = misura(m, 'non addestrato')
        opt = torch.optim.AdamW([p for p in m.parameters() if p.requires_grad], lr=5e-5)
        for ep in range(1, passate + 1):
            m.train(); random.shuffle(esempi); somma = 0.0; t0 = time.time()
            for s, d in esempi:
                n = len(righe[s]); scelti = torch.randperm(n)[:lista]
                vq = q_vec(m, [d], True)[0]
                stud = (Vs[s][scelti.cuda()] @ vq) / 0.05
                maes = bersaglio[s][scelti].cuda()
                l = F.kl_div(F.log_softmax(stud, 0), F.softmax(maes, 0), reduction='sum')
                l.backward(); opt.step(); opt.zero_grad(); somma += l.item()
            print(f'seme {seme} passata {ep}: perdita {somma/len(esempi):.3f} [{time.time()-t0:.0f}s]', flush=True)
            esiti[f'seme{seme}_passata{ep}'] = misura(m, f'seme {seme} dopo passata {ep}')
            m.save_pretrained(QUI/'training'/f'lora_distilla{"" if maestri == "rr" else "_" + maestri.replace("+", "")}{"" if modello == "qwen4b" else "_" + modello}_{seme}'/f'passata_{ep}')
        del m, opt; torch.cuda.empty_cache()
    json.dump(esiti, open(QUI/'training'/f'esiti_distilla{"" if maestri == "rr" else "_" + maestri.replace("+", "")}{"" if modello == "qwen4b" else "_" + modello}.json', 'w'))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('fase'); ap.add_argument('--k', type=int, default=400)
    ap.add_argument('--passate', type=int, default=3); ap.add_argument('--semi', default='1,2,3'); ap.add_argument('--lista', type=int, default=256); ap.add_argument('--maestri', default='rr', choices=['rr', 'rr+ds']); ap.add_argument('--modello', default='qwen4b', choices=list(MODELLI))
    a = ap.parse_args()
    voti(a.k) if a.fase == 'voti' else studia(a.passate, [int(s) for s in a.semi.split(',')], a.lista, False, a.maestri, a.modello)
