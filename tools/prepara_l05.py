"""L'INGRESSO DELLA LETTURA L05 (29/09/2026): tutte le righe col nome, con la finestra larga.

   Si legge lo stato dalla banca dati (regola del controllo di completezza: mai da un file preparato prima): righe
   col nome (`lessicale`, `entrambe`) senza giudizio, tranne le menzioni in catena proposte (non prendono principi
   ne' seguito, R02). Le righe senza tipo proposto entrano. I candidati vengono da `leggi_ripresa.py prepara`, che dal
   29/09 cerca il seguito fino a 10 pagine per lato. Scrive `training/principi/<caso>_ripresa_righe_v2.jsonl`.

   Uso:  .venv/bin/python tools/prepara_l05.py --caso urgenda
"""
import argparse, collections, json, pathlib
from google.cloud import firestore
P = pathlib.Path(__file__).resolve().parent.parent/'training'/'principi'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--caso', required=True); a = ap.parse_args()
    db = firestore.Client(project='climpact-drp')
    tenere, n = set(), collections.Counter()
    for d in db.collection('corpus_rows').where(filter=firestore.FieldFilter('caso_citato', '==', a.caso)).stream():
        r = d.to_dict()
        if r.get('proposto_rete') not in ('lessicale', 'entrambe'):
            continue
        # TUTTE LE RIGHE (29/09/2026, il PI: «L05 deve girare su tutto»). Le giudicate servono a misurare L05 contro
        # le persone (i caricatori non le toccano); le menzioni in catena a vedere se il tipo era sbagliato (la regola
        # R02 resta: niente principi ne' seguito).
        n['gia giudicata' if r.get('esito') else 'menzione in catena' if r.get('proposto_tipo_citazione') == 'menzione_in_catena'
          else 'da giudicare'] += 1
        tenere.add(d.id)
    scritte = 0
    with open(P/f'{a.caso}_ripresa_righe_v2.jsonl', 'w', encoding='utf-8') as f:
        for l in open(P/f'{a.caso}_ripresa_righe.jsonl', encoding='utf-8'):
            if json.loads(l)['id'] in tenere:
                f.write(l); scritte += 1
    print(a.caso, dict(n), 'scritte', scritte, 'mancano dal file dei candidati', len(tenere) - scritte)


if __name__ == '__main__':
    main()
