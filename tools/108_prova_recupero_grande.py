"""UN PRIMO MODELLO PIU' GRANDE: SEPARA MEGLIO? — la prova prima del cambio.

   PERCHE'. Il 22/09/2026 la prova della «domanda ideale» (METODO-RECUPERO 24.3)
   ha mostrato che nello spazio di `multilingual-e5-large` le riprese vere e i
   passaggi che parlano genericamente di obblighi climatici sono mescolati:
   anche la posizione migliore possibile della domanda, ricavata dalle
   risposte, non li separa (AUC 0,568 -> 0,582). Il limite e' la mappa, non la
   domanda. Una mappa disegnata da un modello diverso puo' essere diversa.

   COSA SI PROVA. `Qwen3-Embedding` in due taglie (4 e 8 miliardi di parametri,
   contro i 560 milioni di e5), costruito sopra un LLM e capace di seguire
   un'ISTRUZIONE sul tipo di somiglianza cercata. Tre istruzioni: quella di
   serie, una sull'argomento, una sulla ripresa del ragionamento.

   PERCHE' PRIMA DI CAMBIARE. Ricalcolare l'indice di 1.210.717 frammenti con un
   modello da 8 miliardi costa ore di GPU; addestrarlo costa giorni di lavoro.
   Questa prova costa un pomeriggio e dice se ne vale la pena.

   L'UNITA' INDICIZZATA, provata insieme al modello. La frammentazione di
   `007_build_chunks.py` (1.100 caratteri, tagli su paragrafi e frasi) non dipende
   da e5, ma la sua misura e' stata scelta per un modello piccolo: «una pagina
   intera e' poltiglia». Per un modello che legge 32.000 token puo' non valere
   piu', e per il riordinatore non valeva (pagina invece di frammento: prime
   venti righe da 40% a 55%, §57.2). Ogni modello si prova quindi due volte:
   sul frammento dell'indice e sulla pagina che lo contiene. e5 sulla pagina
   ne legge solo i primi 512 token: e' il suo limite vero, e si misura.

   SU CHE COSA. Le 390 righe della rete semantica pura giudicate dal gruppo, con
   le etichette corrette (§58.3 del documento unico), il frammento ESATTO che
   finisce nell'indice, e la stessa divisione congelata delle altre prove.
   L'e5 si ricalcola qui, sulle stesse righe: nessun confronto con numeri presi
   da un'altra prova.
"""
import argparse, collections, gc, json, pathlib, time
import numpy as np

QUI = pathlib.Path(__file__).resolve().parent.parent

ISTRUZIONI = {
    'di_serie': 'Given a web search query, retrieve relevant passages that answer the query',
    'argomento': 'Given a legal proposition, retrieve passages from court decisions or '
                 'party submissions that discuss this proposition',
    'ripresa': 'Given a legal proposition established in a specific court judgment, retrieve '
               'passages from other cases that adopt this same line of reasoning as their '
               'own, not passages that merely discuss the same topic or that derive a '
               'similar conclusion from other legal sources',
}


def carica(parte):
    p = QUI/'training'/f'urgenda_decisione_{parte}_corrette.jsonl'
    return [x for x in (json.loads(r) for r in p.read_text(encoding='utf-8').splitlines() if r.strip())
            if x['frammento']]


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
    """La domanda ideale per sonda: direzione ricavata dalle risposte giuste
    di ADDESTRAMENTO, provata sulle righe di PROVA. Un tetto ottimistico."""
    g = collections.defaultdict(lambda: {'tr': [], 'te': []})
    for i, x in enumerate(tr):
        g[x['sonda_titolo']]['tr'].append(i)
    for i, x in enumerate(te):
        g[x['sonda_titolo']]['te'].append(i)
    y_all, s_all = [], []
    for v in g.values():
        itr, ite = v['tr'], v['te']
        ytr = np.array([tr[i]['etichetta'] for i in itr]) if itr else np.array([])
        yte = np.array([te[i]['etichetta'] for i in ite])
        if not ite or len(ytr) == 0 or ytr.sum() in (0, len(ytr)) or yte.sum() in (0, len(yte)):
            continue
        d = Vtr[itr][ytr == 1].mean(0) - Vtr[itr][ytr == 0].mean(0)
        d /= np.linalg.norm(d)
        y_all += list(yte); s_all += list(Vte[ite] @ d)
    return auc(y_all, s_all), len(y_all)


def bootstrap_diff(y, a, b, n=4000, seme=20260923):
    rng = np.random.default_rng(seme); y = np.asarray(y); a = np.asarray(a); b = np.asarray(b)
    out = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if y[i].sum() in (0, len(y)):
            continue
        out.append(auc(y[i], b[i]) - auc(y[i], a[i]))
    out = np.array(out)
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5)), float((out <= 0).mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--modelli', default='intfloat/multilingual-e5-large,Qwen/Qwen3-Embedding-4B,Qwen/Qwen3-Embedding-8B')
    ap.add_argument('--lotto', type=int, default=4)
    a = ap.parse_args()

    import torch
    from sentence_transformers import SentenceTransformer
    dev = 'cuda' if torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu')

    tr, te = carica('addestramento'), carica('prova')
    y_te = [x['etichetta'] for x in te]
    print(f'dispositivo {dev}  addestramento {len(tr)} ({sum(x["etichetta"] for x in tr)} vere)  '
          f'prova {len(te)} ({sum(y_te)} vere)', flush=True)
    sonde = sorted({x['sonda_testo'] for x in tr + te})

    risultati = {}
    base = None
    for nome in a.modelli.split(','):
        t0 = time.time()
        e5 = 'e5' in nome
        m = SentenceTransformer(nome, device=dev,
                                model_kwargs={} if e5 else {'torch_dtype': torch.bfloat16})
        pref_doc = 'passage: ' if e5 else ''
        for unita in ('frammento', 'finestra'):
            m.max_seq_length = 512 if e5 else (1024 if unita == 'frammento' else 2560)
            Vtr = m.encode([pref_doc + x[unita] for x in tr], batch_size=a.lotto,
                           normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False).astype(np.float32)
            Vte = m.encode([pref_doc + x[unita] for x in te], batch_size=a.lotto,
                           normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False).astype(np.float32)
            th, n_th = tetto(tr, te, Vtr, Vte)
            istr = {'e5, prefisso passage:': None} if e5 else ISTRUZIONI
            for chiave, testo in istr.items():
                if e5:
                    Q = m.encode(['passage: ' + s for s in sonde], normalize_embeddings=True,
                                 convert_to_numpy=True, show_progress_bar=False)
                else:
                    Q = m.encode(sonde, prompt=f'Instruct: {testo}\nQuery:', normalize_embeddings=True,
                                 convert_to_numpy=True, show_progress_bar=False)
                qi = {s: Q[i] for i, s in enumerate(sonde)}
                s_te = [float(qi[x['sonda_testo']] @ Vte[i]) for i, x in enumerate(te)]
                etichetta = f'{nome.split("/")[-1]} | {unita} | {chiave}'
                risultati[etichetta] = s_te
                if e5 and unita == 'frammento':
                    base = s_te
                print(f'  {etichetta:66s} AUC {auc(y_te, s_te):.3f}   prime 20 {100*prime(y_te, s_te, 20):3.0f}%   '
                      f'prime 40 {100*prime(y_te, s_te, 40):3.0f}%', flush=True)
            print(f'  {"":66s} tetto della domanda ideale: AUC {th:.3f} (su {n_th} righe)   [{time.time()-t0:.0f}s]', flush=True)
        del m; gc.collect()
        if dev == 'mps':
            torch.mps.empty_cache()

    if base is not None:
        print('\nCONTRO e5, bootstrap sulle righe di prova (intervallo al 95%, e quante volte il nuovo non e\' meglio):')
        for k, v in risultati.items():
            if k.startswith('multilingual-e5-large | frammento'):
                continue
            lo, hi, peggio = bootstrap_diff(y_te, base, v)
            print(f'  {k:66s} {auc(y_te, v)-auc(y_te, base):+.3f}  [{lo:+.3f}, {hi:+.3f}]  non meglio nel {100*peggio:.0f}%')
    (QUI/'training'/'prova_recupero_grande.json').write_text(json.dumps(
        {k: {x['id']: s for x, s in zip(te, v)} for k, v in risultati.items()}, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
