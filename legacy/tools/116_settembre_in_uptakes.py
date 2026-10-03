"""LE RIGHE GIUDICATE SOLO NELLA VALIDAZIONE VECCHIA TORNANO NELLA CODA DI UPTAKES (29/09/2026, si' del PI).

   La validazione di settembre diceva se la citazione e' del caso, il tipo e chi parla; principi e seguito non
   esistevano. Quelle righe avevano `esito` e quindi risultavano fatte anche in Uptakes: nessuno le avrebbe mai
   guardate per i principi. Qui, per le righe col nome giudicate «confermata» o «riclassificata» e mai salvate dalla
   scheda Uptakes: il giudizio vecchio va in `settembre` (esito, validato_da, validato_il), `esito`, `validato_da` e
   `validato_il` tornano vuoti. Tipo e chi parla validati restano sulla riga e il portale li mostra gia' compilati,
   con «It cites» gia' scelto. Le righe scartate a settembre restano fatte. Senza --scrivi non scrive niente.
"""
import argparse, collections
from google.cloud import firestore


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--scrivi', action='store_true'); a = ap.parse_args()
    db = firestore.Client(project='climpact-drp')
    w, n = [], collections.Counter()
    for caso in ('urgenda', 'neubauer', 'future-generations'):
        for d in db.collection('corpus_rows').where(filter=firestore.FieldFilter('caso_citato', '==', caso)).stream():
            r = d.to_dict()
            if r.get('proposto_rete') not in ('lessicale', 'entrambe') or r.get('esito') not in ('confermata', 'riclassificata'):
                continue
            if r.get('validato_principi') is not None or (r.get('validato_contesto') or {}).get('scheda') == 'riprese':
                n[(caso, 'gia in Uptakes')] += 1
                continue
            n[(caso, 'torna in coda')] += 1
            w.append((d.reference, {
                'settembre': {'esito': r.get('esito'), 'validato_da': r.get('validato_da'), 'validato_il': r.get('validato_il')},
                'esito': None, 'validato_da': None, 'validato_il': None, 'torna_in_uptakes': '2026-09-29',
            }))
    print(dict(n))
    if a.scrivi:
        for i in range(0, len(w), 400):
            b = db.batch()
            for ref, c in w[i:i + 400]:
                b.update(ref, c)
            b.commit()
        print('scritte', len(w))


if __name__ == '__main__':
    main()
