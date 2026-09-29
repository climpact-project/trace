"""Assign a unique, permanent code to every citation row.

   Each lexical (and 'entrambe') row receives `codice` = <PREFIX>-<4-digit number>, ordered by document and by
   position within the document, so individual results can be referenced and later published. Codes are never
   reassigned: rows that already have one keep it, new rows continue after the highest number of the case.

   Usage:  .venv/bin/python tools/assegna_codici.py [--scrivi]
"""
import argparse, collections, re
from google.cloud import firestore
PREFISSI = {'urgenda': 'URG', 'neubauer': 'NEU', 'future-generations': 'FGC'}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--scrivi', action='store_true'); a = ap.parse_args()
    db = firestore.Client(project='climpact-drp')
    for caso, pre in PREFISSI.items():
        tutte = [(d.reference, d.to_dict()) for d in db.collection('corpus_rows')
                 .where(filter=firestore.FieldFilter('caso_citato', '==', caso)).stream()]
        righe = [(ref, r) for ref, r in tutte if r.get('proposto_rete') in ('lessicale', 'entrambe')]
        # The maximum is taken over ALL rows of the case, merged rows included (`proposto_rete = 'fusa'`):
        # counting only lexical rows would let a number held by a merged row be reused.
        gia = [int(m.group(1)) for _, r in tutte for m in [re.fullmatch(rf'{pre}-(\d+)', str(r.get('codice') or ''))] if m]
        n = max(gia, default=0)
        nuove = sorted([(ref, r) for ref, r in righe if not r.get('codice')],
                       key=lambda x: (x[1].get('document_id') or '', int(x[1].get('char_start') or 0), x[0].id))
        w = []
        for ref, r in nuove:
            n += 1
            w.append((ref, {'codice': f'{pre}-{n:04d}'}))
        print(caso, 'gia con codice', len(gia), 'nuovi', len(w), 'ultimo', f'{pre}-{n:04d}')
        if a.scrivi:
            for i in range(0, len(w), 400):
                b = db.batch()
                for ref, c in w[i:i+400]:
                    b.update(ref, c)
                b.commit()


if __name__ == '__main__':
    main()
