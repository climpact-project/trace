"""UN CODICE UNICO E PERMANENTE PER OGNI CITAZIONE (28/09/2026, richiesta del PI).

   «Per discutere con te e per cercare i singoli risultati ogni risultato dovrebbe avere un codice univoco, per il
   futuro anche per pubblicarlo.» Ogni riga lessicale (e «entrambe») riceve `codice` = <PREFISSO>-<numero a 4 cifre>,
   in ordine di documento e posizione nel documento. Il codice NON si riassegna mai: le righe che lo hanno gia' lo
   tengono, le nuove prendono il numero dopo il piu' alto del caso.

   Uso:  .venv/bin/python tools/assegna_codici.py [--scrivi]
"""
import argparse, collections, re
from google.cloud import firestore
PREFISSI = {'urgenda': 'URG', 'neubauer': 'NEU', 'future-generations': 'FGC', 'klimaseniorinnen': 'KLS', 'cig-parere-clima': 'ICJ', 'idh-oc-32-25': 'IAC'}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--scrivi', action='store_true'); a = ap.parse_args()
    db = firestore.Client(project='climpact-drp')
    for caso, pre in PREFISSI.items():
        tutte = [(d.reference, d.to_dict()) for d in db.collection('corpus_rows')
                 .where(filter=firestore.FieldFilter('caso_citato', '==', caso)).stream()]
        righe = [(ref, r) for ref, r in tutte if r.get('proposto_rete') in ('lessicale', 'entrambe')]
        # Il massimo si cerca su TUTTE le righe del caso, comprese quelle unite (`proposto_rete = 'fusa'`, dal
        # 29/9/2026): contando solo le lessicali, un numero tenuto da una riga unita tornerebbe in circolo.
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
