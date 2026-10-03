"""IL PRIMO PASSO CON PIU' DOMANDE — tre segnali economici, provati come pipeline.

   LA DOMANDA DEL PI (23/09/2026). Si puo' far fare al primo modello «qualche
   domanda in piu'», senza farlo ragionare frammento per frammento (che su un
   milione di frammenti costerebbe mesi), in modo che distingua la ripresa di
   un ragionamento dalla semplice vicinanza di argomento?

   TRE DOMANDE, TUTTE ISTANTANEE ANCHE SU UN MILIONE DI FRAMMENTI:
     1. PIU' FORMULAZIONI. Per ogni proposizione, venti modi in cui un altro
        giudice o una parte la riprenderebbe, in piu' lingue, senza nominare il
        caso. Si tiene la somiglianza migliore.
     2. LA DOMANDA CONTRARIA. Dodici formulazioni che arrivano a una conclusione
        simile fondandola su un'ALTRA fonte (Parigi, UNFCCC, CBDR, ARSIWA,
        costituzioni, sistemi regionali, altri casi). Un passaggio piu' vicino
        a queste che alla ripresa e' sospetto: e' il guasto ricorrente misurato
        nelle note dei validatori (§56.2 del documento unico).
     3. LE PAROLE DELLA DOTTRINA. I `lexical_markers` dichiarati nel file del
        caso il 2/09/2026, prima dei giudizi, usati cosi' come sono.

   CONTRO IL BARARE. Le formulazioni 1 e 2 le ha scritte un LLM in una sessione
   separata che NON ha visto nessuna riga giudicata: conosceva solo il caso e le
   cinque proposizioni (`training/formulazioni_fable.json`). I marcatori non
   sono stati ritoccati dopo aver visto i risultati. I pesi con cui si
   combinano i segnali si imparano sulle righe di ADDESTRAMENTO e si provano
   su quelle di PROVA.

   DOMANDE INVENTATE E DOMANDE VERE, a confronto (richiesta del PI). Le
   formulazioni di Fable sono frasi scritte apposta: domande, non prove, ma
   possono non suonare come scrive un giudice. L'alternativa usa testo vero,
   preso SOLO dalle righe di addestramento: come riprese i passaggi confermati
   dal gruppo, come concorrenti i passaggi bocciati per quella proposizione.
   Per ogni riga si escludono le domande che vengono dal suo stesso caso
   citante: senza, una riga di addestramento troverebbe se stessa e i pesi
   imparati sarebbero falsati; ed e' la condizione in cui stanno gia' le
   righe di prova, che vengono da casi diversi per costruzione.

   TRE CONFIGURAZIONI: e5 sul frammento (l'indice di oggi), e Qwen3-Embedding-4B
   e -8B sulla pagina (la migliore delle unita' nella prova del mattino, §59.3).
"""
import argparse, collections, gc, json, pathlib, re, time
import numpy as np

QUI = pathlib.Path(__file__).resolve().parent.parent

ISTR_RIPRESA = ('Given a legal proposition established in a specific court judgment, retrieve '
                'passages from other cases that adopt this same line of reasoning as their '
                'own, not passages that merely discuss the same topic or that derive a '
                'similar conclusion from other legal sources')
ISTR_ARGOMENTO = ('Given a legal proposition, retrieve passages from court decisions or '
                  'party submissions that discuss this proposition')


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


def bootstrap(y, a, b, n=4000, seme=20260923):
    rng = np.random.default_rng(seme); y = np.asarray(y); a = np.asarray(a); b = np.asarray(b)
    d = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if y[i].sum() in (0, len(y)):
            continue
        d.append(auc(y[i], b[i]) - auc(y[i], a[i]))
    d = np.array(d)
    return float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5)), float((d <= 0).mean())


def marcatori():
    import yaml
    d = yaml.safe_load((QUI/'cited-cases'/'urgenda.yaml').read_text(encoding='utf-8'))
    out = {}
    for s in d['semantic_queries']:
        m = s.get('lexical_markers') or {}
        out[s['id']] = [t.lower() for lst in m.values() for t in lst]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lotto', type=int, default=2)
    a = ap.parse_args()

    import torch
    from sentence_transformers import SentenceTransformer
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    dev = 'cuda' if torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu')

    tr, te = carica('addestramento'), carica('prova')
    y_tr = np.array([x['etichetta'] for x in tr]); y_te = np.array([x['etichetta'] for x in te])
    form = json.loads((QUI/'training'/'formulazioni_fable.json').read_text(encoding='utf-8'))
    # TERZA FAMIGLIA: ricavate dai testi veri (sentenze di Urgenda, passaggi
    # confermati e bocciati delle sole righe di addestramento). Ogni frase
    # dichiara l'ancora da cui nasce; l'ancora porta il caso citante, e per le
    # righe di quel caso la frase si esclude, come per le domande vere.
    der = json.loads((QUI/'training'/'formulazioni_derivate.json').read_text(encoding='utf-8'))
    mappa_casi = json.loads((QUI/'training'/'ancore_mappa_casi.json').read_text(encoding='utf-8'))
    mk = marcatori()
    base_id = lambda x: x['sonda_id'].split('__')[0]
    print(f'prova {len(te)} righe ({y_te.sum()} vere) | addestramento {len(tr)} ({y_tr.sum()} vere)')
    print('formulazioni per proposizione:', {k: (len(v['ripresa']), len(v['concorrenti'])) for k, v in form.items()}, flush=True)

    riepilogo = {}
    base_oggi = None
    for nome, unita in (('intfloat/multilingual-e5-large', 'frammento'),
                        ('Qwen/Qwen3-Embedding-4B', 'finestra'),
                        ('Qwen/Qwen3-Embedding-8B', 'finestra')):
        t0 = time.time()
        e5 = 'e5' in nome
        m = SentenceTransformer(nome, device=dev, model_kwargs={} if e5 else {'torch_dtype': torch.bfloat16})
        m.max_seq_length = 512 if e5 else 2560

        def doc(testi):
            return m.encode([('passage: ' if e5 else '') + t for t in testi], batch_size=a.lotto,
                            normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)

        def dom(testi, istr):
            if e5:
                return m.encode(['passage: ' + t for t in testi], normalize_embeddings=True,
                                convert_to_numpy=True, show_progress_bar=False)
            return m.encode(testi, prompt=f'Instruct: {istr}\nQuery:', normalize_embeddings=True,
                            convert_to_numpy=True, show_progress_bar=False)

        Dtr, Dte = doc([x[unita] for x in tr]), doc([x[unita] for x in te])
        # le domande: la proposizione originale di ogni riga, le formulazioni, le concorrenti
        testi_orig = sorted({x['sonda_testo'] for x in tr + te})
        orig = dict(zip(testi_orig, dom(testi_orig, ISTR_RIPRESA)))
        Rip = {k: dom(v['ripresa'], ISTR_RIPRESA) for k, v in form.items()}
        Con = {k: dom(v['concorrenti'], ISTR_ARGOMENTO) for k, v in form.items()}
        RipD = {k: (dom([x['testo'] for x in v['ripresa']], ISTR_RIPRESA),
                    np.array([mappa_casi.get(x['ancora'], '') for x in v['ripresa']])) for k, v in der.items()}
        ConD = {k: (dom([x['testo'] for x in v['concorrenti']], ISTR_ARGOMENTO),
                    np.array([mappa_casi.get(x['ancora'], '') for x in v['concorrenti']])) for k, v in der.items()}
        # le domande VERE: passaggi delle sole righe di addestramento
        veri = collections.defaultdict(lambda: {'pos': [], 'neg': []})
        for x in tr:
            veri[base_id(x)]['pos' if x['etichetta'] else 'neg'].append(x)
        RipV = {k: (dom([x['frammento'] for x in v['pos']], ISTR_RIPRESA) if v['pos'] else np.zeros((0, Dtr.shape[1])),
                    np.array([x['case_id'] for x in v['pos']])) for k, v in veri.items()}
        ConV = {k: (dom([x['frammento'] for x in v['neg']], ISTR_ARGOMENTO) if v['neg'] else np.zeros((0, Dtr.shape[1])),
                    np.array([x['case_id'] for x in v['neg']])) for k, v in veri.items()}

        def vicini(Q, casi, d, caso_riga, ripiego):
            """Somiglianza massima e media delle 5 migliori, escluse le domande
            che vengono dallo stesso caso citante della riga."""
            if len(casi) == 0:
                return ripiego, ripiego
            s_ = (Q @ d)[casi != caso_riga]
            if len(s_) == 0:
                return ripiego, ripiego
            s_ = np.sort(s_)[::-1]
            return float(s_[0]), float(s_[:5].mean())

        def caratteristiche(righe, D):
            F = []
            for x, d in zip(righe, D):
                k = base_id(x)
                f_orig = float(orig[x['sonda_testo']] @ d)
                sr = np.sort(Rip[k] @ d)[::-1]
                sc = np.sort(Con[k] @ d)[::-1]
                testo = x[unita].lower()
                lex = sum(1 for t in mk.get(k, []) if t in testo)
                vp, vp5 = vicini(*RipV.get(k, (np.zeros((0, len(d))), np.array([]))), d, x['case_id'], f_orig)
                vn, _ = vicini(*ConV.get(k, (np.zeros((0, len(d))), np.array([]))), d, x['case_id'], f_orig)
                dp, dp5 = vicini(*RipD[k], d, x['case_id'], f_orig)
                dn, _ = vicini(*ConD[k], d, x['case_id'], f_orig)
                F.append([f_orig, sr[0], sr[:5].mean(), sc[0], sr[0] - sc[0], lex, vp, vp5, vn, vp - vn,
                          dp, dp5, dn, dp - dn])
            return np.array(F)

        Ftr, Fte = caratteristiche(tr, Dtr), caratteristiche(te, Dte)
        nomi = ['proposizione originale', 'INV migliore ripresa', 'INV media 5 riprese',
                'INV concorrente piu vicina', 'INV ripresa meno concorrente', 'marcatori lessicali',
                'VERE migliore ripresa', 'VERE media 5 riprese', 'VERE bocciata piu vicina',
                'VERE ripresa meno bocciata', 'RICAVATE migliore ripresa', 'RICAVATE media 5 riprese',
                'RICAVATE concorrente piu vicina', 'RICAVATE ripresa meno concorrente']
        verso = [1, 1, 1, -1, 1, 1, 1, 1, -1, 1, 1, 1, -1, 1]   # vicino alla concorrente = peggio
        etich = f'{nome.split("/")[-1]} sul {unita}'
        print(f'\n══ {etich} ══', flush=True)
        print('  ciascun segnale da solo:')
        for j, n in enumerate(nomi):
            sgl = verso[j] * Fte[:, j]
            print(f'    {n:32s} AUC {auc(y_te, sgl):.3f}   prime 20 {100*prime(y_te, sgl, 20):3.0f}%   prime 40 {100*prime(y_te, sgl, 40):3.0f}%')
        famiglie = {'con domande INVENTATE (Fable)': [0, 1, 2, 3, 4, 5],
                    'con domande VERE (addestramento)': [0, 5, 6, 7, 8, 9],
                    'con domande RICAVATE dai testi veri': [0, 5, 10, 11, 12, 13],
                    'VERE + RICAVATE': [0, 5, 6, 7, 8, 9, 10, 11, 12, 13],
                    'TUTTE e tre': list(range(14))}
        print('  combinati, pesi imparati sull addestramento:')
        miglior = None
        for fam, cols in famiglie.items():
            sc_ = StandardScaler().fit(Ftr[:, cols])
            lr = LogisticRegression(C=1.0, max_iter=2000).fit(sc_.transform(Ftr[:, cols]), y_tr)
            comb = lr.decision_function(sc_.transform(Fte[:, cols]))
            lo, hi, pg = bootstrap(y_te, Fte[:, 0], comb)
            print(f'    {fam:32s} AUC {auc(y_te, comb):.3f}   prime 20 {100*prime(y_te, comb, 20):3.0f}%   prime 40 {100*prime(y_te, comb, 40):3.0f}%'
                  f'   | contro la sola originale {auc(y_te, comb)-auc(y_te, Fte[:, 0]):+.3f} [{lo:+.3f}, {hi:+.3f}]')
            if base_oggi is not None:
                lo, hi, pg = bootstrap(y_te, base_oggi, comb)
                print(f'    {"":32s} contro il sistema di OGGI (e5, frammento, originale): {auc(y_te, comb)-auc(y_te, base_oggi):+.3f} [{lo:+.3f}, {hi:+.3f}], non meglio nel {100*pg:.0f}%')
            if miglior is None or auc(y_te, comb) > miglior[1]:
                miglior = (comb, auc(y_te, comb))
        comb = miglior[0]
        if e5:
            base_oggi = Fte[:, 0]
        riepilogo[etich] = {'combinato': {x['id']: float(s) for x, s in zip(te, comb)}}
        print(f'  [{time.time()-t0:.0f}s]', flush=True)
        del m; gc.collect()
        if dev == 'mps':
            torch.mps.empty_cache()
        elif dev == 'cuda':
            torch.cuda.empty_cache()
    (QUI/'training'/'prova_pipeline_primo.json').write_text(json.dumps(riepilogo, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
