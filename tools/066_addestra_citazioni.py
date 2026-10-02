"""IL PRIMO MODELLO ADDESTRATO SULLE CITAZIONI ESPLICITE (senza giudizi umani) — diario:
   DIARIO-ADDESTRAMENTO-CITAZIONI.md.

   Stessa ricetta del §62.7 (Qwen3-Embedding-4B, LoRA solo sul lato della domanda, le pagine le legge
   il modello di base, perdita contrastiva a temperatura 0,05, 1 positivo e 7 negativi), ma gli
   esempi vengono da `083_coppie_citazioni.py`: domanda = paragrafo della sentenza citata, positivo =
   pagina che lo cita col nome del caso tolto.
   Due varianti di negativi, per sapere quanto aggiunge ciascuna:
     facili       7 pagine a caso del corpus;
     concorrenti  3 a caso + 4 pagine che ragionano da altre fonti (Parigi, UNFCCC/CBDR, CEDU)
                  senza nominare nessuno dei casi citati.
   Misura dopo ogni passata sulle 133 righe di prova di Urgenda (sonda contro pagina), come sempre.
   L'adattatore salvato si puo' poi rifinire sui giudizi umani: 067_addestra_primo_qwen.py --inizio.
"""
import argparse, json, pathlib, random, sys, time
import numpy as np
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
_m_addestra_primo_qwen = __import__('067_addestra_primo_qwen')
carica = _m_addestra_primo_qwen.carica
auc = _m_addestra_primo_qwen.auc
prime = _m_addestra_primo_qwen.prime
ISTR = _m_addestra_primo_qwen.ISTR
MODELLI = _m_addestra_primo_qwen.MODELLI
C = QUI/'training'/'citazioni'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--negativi', choices=['facili', 'concorrenti'], required=True)
    ap.add_argument('--modello', default='qwen4b', choices=list(MODELLI))
    ap.add_argument('--passate', type=int, default=2)
    ap.add_argument('--semi', default='1,2,3')
    ap.add_argument('--lr', type=float, default=5e-5)
    ap.add_argument('--rango', type=int, default=16)
    ap.add_argument('--maxlen', type=int, default=2048)
    # ADDESTRAMENTO CONGIUNTO (26/09/2026): i giudizi umani di Urgenda mescolati alle citazioni nello stesso
    # addestramento, ripetuti PESO volte per passata, invece di una rifinitura dopo (che su Perplexity non
    # spostava niente). Etichette rivedute: Neubauer p. 43 vera, Smith fuori.
    ap.add_argument('--umani', type=int, default=0, help='peso dei giudizi umani (0 = non usarli)')
    # PER IL RICHIAMO (26/09/2026): solo le riprese confermate dalle persone come positivi, contro pagine QUALSIASI
    # del corpus. Niente citazioni, niente scartate come negativi: il retriever non deve imparare a spingere giu'
    # lo stesso argomento (quello e' il mestiere del riordinatore), deve tenere in alto le riprese.
    ap.add_argument('--richiamo', action='store_true')
    a = ap.parse_args()
    import torch, torch.nn.functional as F
    from transformers import AutoTokenizer, AutoModel
    from peft import LoraConfig, get_peft_model
    NOME, POOL, PQ, PD = MODELLI[a.modello]; PQ = PQ.replace('{ISTR}', ISTR)
    tok = AutoTokenizer.from_pretrained(NOME, padding_side='left', trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    coppie = [json.loads(l) for l in open(C/'coppie.jsonl', encoding='utf-8')]
    neg = json.load(open(C/'negativi.json', encoding='utf-8'))
    te = carica('prova'); y = np.array([x['etichetta'] for x in te])
    print(f'coppie {len(coppie)} | negativi facili {len(neg["facili"])}, concorrenti {len(neg["concorrenti"])} | prova {len(te)} ({y.sum()} vere)', flush=True)

    def codifica(m, testi, domanda, grad=False, batch=4):
        out = []
        for i in range(0, len(testi), batch):
            pezzo = [(PQ if domanda else PD) + t for t in testi[i:i+batch]]
            enc = tok(pezzo, padding=True, truncation=True, max_length=a.maxlen, return_tensors='pt').to('cuda')
            with torch.set_grad_enabled(grad), torch.autocast('cuda', dtype=torch.bfloat16):
                hs = m(**enc).last_hidden_state
                if POOL == 'media':
                    k = enc['attention_mask'].unsqueeze(-1).to(hs.dtype); h = (hs*k).sum(1)/k.sum(1)
                else:
                    h = hs[:, -1]
            out.append(F.normalize(h.float(), dim=-1))
        return torch.cat(out)

    def pagine(m, testi):
        with m.disable_adapter():
            return codifica(m, testi, False).detach()

    def misura(m, etichetta):
        m.eval()
        sonde = sorted({x['sonda_testo'] for x in te})
        with torch.no_grad():
            Q = dict(zip(sonde, codifica(m, sonde, True).cpu().numpy()))
            V = pagine(m, [x['finestra'] for x in te]).cpu().numpy()
        s = [float(Q[x['sonda_testo']] @ V[i]) for i, x in enumerate(te)]
        print(f'  {etichetta:40s} AUC {auc(y, s):.3f}   prime 20 {100*prime(y, s, 20):3.0f}%   prime 40 {100*prime(y, s, 40):3.0f}%', flush=True)
        return s

    umani = []
    if a.umani:
        import collections
        rv = [json.loads(l) for l in open(QUI/'training'/'urgenda_decisione_addestramento_rivedute_larghe.jsonl', encoding='utf-8')]
        rv = [x for x in rv if x['frammento'] and x.get('finestra')]
        der = json.loads((QUI/'training'/'formulazioni_derivate.json').read_text(encoding='utf-8'))
        fab = json.loads((QUI/'training'/'formulazioni_fable.json').read_text(encoding='utf-8'))
        G = collections.defaultdict(lambda: {'q': set(), 'si': [], 'no': [], 'conc': []})
        for x in rv:
            sid = x['sonda_id'].split('__')[0]; g = G[sid]
            g['q'].add(x['sonda_testo']); g['si' if x['etichetta'] else 'no'].append(x['finestra'])
        for sid, g in G.items():
            g['q'] |= {f['testo'] for f in der.get(sid, {}).get('ripresa', [])}
            g['q'] |= {(f if isinstance(f, str) else f['testo']) for f in fab.get(sid, {}).get('ripresa', [])}
            g['conc'] = [f['testo'] for f in der.get(sid, {}).get('concorrenti', [])] + \
                        [(f if isinstance(f, str) else f['testo']) for f in fab.get(sid, {}).get('concorrenti', [])]
        umani = [(sid, q) for sid, g in G.items() if g['si'] and g['no'] for q in g['q']]
        print(f'giudizi umani: {len(rv)} righe, {len(umani)} domande, peso {a.umani}', flush=True)
    esiti = {'ids': [x['id'] for x in te]}
    for seme in [int(s) for s in a.semi.split(',')]:
        random.seed(seme); torch.manual_seed(seme)
        m = AutoModel.from_pretrained(NOME, torch_dtype=torch.bfloat16, trust_remote_code=True)
        m.gradient_checkpointing_enable(); m.enable_input_require_grads()
        m = get_peft_model(m, LoraConfig(r=a.rango, lora_alpha=2*a.rango, lora_dropout=0.1,
                                         target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj'])).to('cuda')
        if seme == int(a.semi.split(',')[0]):
            esiti['non_addestrato'] = misura(m, 'non addestrato (adattatore a zero)')
        opt = torch.optim.AdamW([p for p in m.parameters() if p.requires_grad], lr=a.lr)
        for ep in range(1, a.passate + 1):
            m.train(); t0 = time.time(); somma = 0.0
            passi = ([] if a.richiamo else [('c', c) for c in coppie]) + [('u', u) for u in umani for _ in range(a.umani)]
            random.shuffle(passi)
            for tipo, c in passi:
                if tipo == 'u':
                    sid, q = c; g = G[sid]
                    if a.richiamo:
                        negs = random.sample(neg['facili'], 7)
                    else:
                        cand = g['no'] + g['conc']
                        negs = random.sample(cand, min(5, len(cand))) + random.sample(neg['concorrenti'], 2)
                    domanda, positivo = q, random.choice(g['si'])
                else:
                    if a.negativi == 'facili':
                        negs = random.sample(neg['facili'], 7)
                    else:
                        negs = random.sample(neg['facili'], 3) + random.sample(neg['concorrenti'], 4)
                    domanda, positivo = c['domanda'], c['pagina']
                vq = codifica(m, [domanda], True, grad=True)
                vd = pagine(m, [positivo] + negs)
                l = F.cross_entropy((vq @ vd.T) / 0.05, torch.tensor([0], device='cuda'))
                l.backward(); opt.step(); opt.zero_grad(); somma += l.item()
            print(f'seme {seme} passata {ep}: perdita {somma/len(passi):.3f} [{time.time()-t0:.0f}s]', flush=True)
            esiti[f'seme{seme}_passata{ep}'] = misura(m, f'seme {seme} dopo passata {ep}')
            m.save_pretrained(QUI/'training'/f'lora_{"richiamo" if a.richiamo else "citazioni_" + a.negativi}{"_umani" + str(a.umani) if a.umani else ""}_{a.modello}_{seme}'/f'passata_{ep}')
        del m, opt; torch.cuda.empty_cache()
    (QUI/'training'/f'esiti_{"richiamo" if a.richiamo else "citazioni_" + a.negativi}{"_umani" + str(a.umani) if a.umani else ""}_{a.modello}.json').write_text(json.dumps(esiti), encoding='utf-8')


if __name__ == '__main__':
    main()
