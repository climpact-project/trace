"""QUANTO TESTO IN UN PUNTO — l'unita' dell'indice, misurata.

   LA DOMANDA DEL PI (23/09/2026): «servirebbe anche la pagina prima e dopo?».
   Il ragionamento di una decisione comincia spesso prima e si chiude dopo, e
   le pagine del PDF tagliano il testo dove capita. Ma piu' testo in un solo
   punto mescola piu' argomenti (la «poltiglia» di `007_build_chunks.py`). Si
   misura invece di decidere: quattro unita' — il frammento dell'indice (1.141
   caratteri in mediana), la pagina (3.198), la pagina con la successiva
   (6.185), la pagina con quella prima e quella dopo (9.303) — con il modello
   di oggi e con i due modelli nuovi.

   Stesse 390 righe semantiche pure, etichette corrette, stessa divisione.
   Oltre all'AUC con la proposizione originale, il tetto della domanda ideale
   (§57.3): dice se l'unita' rende lo spazio piu' separabile, non solo se la
   sonda di oggi ci si trova meglio.
"""
import collections, gc, json, pathlib, time
import numpy as np
import torch

QUI = pathlib.Path(__file__).resolve().parent.parent
ISTR = {
    'argomento': 'Given a legal proposition, retrieve passages from court decisions or party submissions that discuss this proposition',
    'ripresa': ('Given a legal proposition established in a specific court judgment, retrieve passages from other '
                'cases that adopt this same line of reasoning as their own, not passages that merely discuss the '
                'same topic or that derive a similar conclusion from other legal sources'),
}


def carica(parte):
    p = QUI/'training'/f'urgenda_decisione_{parte}_corrette_larghe.jsonl'
    return [x for x in (json.loads(r) for r in p.read_text(encoding='utf-8').splitlines() if r.strip())
            if x['frammento'] and x.get('finestra_larga')]


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
    from sentence_transformers import SentenceTransformer
    tr, te = carica('addestramento'), carica('prova')
    y_te = [x['etichetta'] for x in te]
    sonde = sorted({x['sonda_testo'] for x in tr + te})
    print(f'prova {len(te)} ({sum(y_te)} vere) | addestramento {len(tr)}', flush=True)
    esiti = {}
    for nome in ('intfloat/multilingual-e5-large', 'Qwen/Qwen3-Embedding-4B', 'Qwen/Qwen3-Embedding-8B'):
        e5 = 'e5' in nome
        m = SentenceTransformer(nome, device='cuda', model_kwargs={} if e5 else {'torch_dtype': torch.bfloat16})
        print(f'\n══ {nome.split("/")[-1]} ══', flush=True)
        for unita in ('frammento', 'finestra', 'pagina_piu_mezza', 'finestra_larga'):
            t0 = time.time()
            m.max_seq_length = 512 if e5 else 8192
            enc = lambda T: m.encode([('passage: ' if e5 else '') + t for t in T], batch_size=4,
                                     normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
            Vtr, Vte = enc([x[unita] for x in tr]), enc([x[unita] for x in te])
            th = tetto(tr, te, Vtr, Vte)
            for k, istr in ({'e5': None} if e5 else ISTR).items():
                Q = (m.encode(['passage: ' + s for s in sonde], normalize_embeddings=True, convert_to_numpy=True)
                     if e5 else m.encode(sonde, prompt=f'Instruct: {istr}\nQuery:', normalize_embeddings=True, convert_to_numpy=True))
                qi = dict(zip(sonde, Q))
                s = [float(qi[x['sonda_testo']] @ Vte[i]) for i, x in enumerate(te)]
                esiti[f'{nome}|{unita}|{k}'] = s
                print(f'  {unita:18s} {k:10s} AUC {auc(y_te, s):.3f}   prime 20 {100*prime(y_te, s, 20):3.0f}%   prime 40 {100*prime(y_te, s, 40):3.0f}%', flush=True)
            print(f'  {unita:18s} {"":10s} tetto della domanda ideale {th:.3f}   [{time.time()-t0:.0f}s]', flush=True)
        del m; gc.collect(); torch.cuda.empty_cache()
    (QUI/'training'/'prova_unita.json').write_text(json.dumps({'ids': [x['id'] for x in te], **esiti}), encoding='utf-8')


if __name__ == '__main__':
    main()
