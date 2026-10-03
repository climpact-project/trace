"""LA CODA DI UPTAKES: UNA RIGA SU CINQUE ALLA CIECA, ORDINE CASUALE (28/09/2026, decisione del PI).

   Il PI: «nessun fronte nuovo». Niente campagna a parte: dentro la coda normale
   - una riga su dieci, a caso, arriva SENZA le proposte della macchina (`campione_cieco`): campi vuoti, niente
     commento, nessuna spunta. Serve a misurare la macchina su giudizi presi da soli; si riempie mentre il team lavora;
   - l'ORDINE RESTA CASUALE (il PI: «forse non ha senso, meglio che sia casuale»): le righe giudicate restano un
     campione di tutte, e ogni numero ricavato vale per tutte. `incerta` (due letture di DeepSeek discordi, paragrafo e
     lettura con principi diversi, un principio indicato solo dal reranker) si scrive per le analisi, non per l'ordine.
   Solo righe lessicali ancora da giudicare. Il sorteggio ha seme fisso: rilanciato, da' le stesse righe.

   Uso:  .venv/bin/python tools/022_coda_uptakes.py [--scrivi]
"""
import argparse, collections, random
from google.cloud import firestore


def incerta(r):
    if r.get('proposto_confidenza') == 'bassa':
        return True
    f = r.get('proposto_principi_fonti') or {}
    par = {p for p, v in f.items() if 'paragrafo' in v}
    let = {p for p, v in f.items() if 'lettura' in v}
    if par and let and par != let:
        return True
    return any(v == ['reranker'] for v in f.values()) and r.get('proposto_principi') != ['nessuno']


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--scrivi', action='store_true'); a = ap.parse_args()
    db = firestore.Client(project='climpact-drp')
    rnd = random.Random(20260928)
    n = collections.Counter(); w = []
    for caso in ('urgenda', 'neubauer', 'future-generations'):
        for d in db.collection('corpus_rows').where(filter=firestore.FieldFilter('caso_citato', '==', caso)).stream():
            r = d.to_dict()
            if r.get('proposto_rete') not in ('lessicale', 'entrambe') or r.get('esito') or r.get('da_discutere'):
                continue
            inc = incerta(r)
            cieco = rnd.random() < 0.20
            c = {'incerta': inc, 'campione_cieco': cieco}
            w.append((d.reference, c))
            n[(caso, 'incerta' if inc else 'sicura')] += 1; n[(caso, 'cieca')] += cieco
    print(dict(n))
    if a.scrivi:
        for i in range(0, len(w), 400):
            b = db.batch()
            for ref, c in w[i:i+400]:
                b.update(ref, c)
            b.commit()
        print('scritte', len(w))


if __name__ == '__main__':
    main()
