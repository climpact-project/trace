"""Build the input for the L05 reading pass: all name-matched rows, with the wide window.

   State is read from the database, never from a previously prepared file. Rows with the case name (`lessicale`,
   `entrambe`) are all included; rows without a proposed citation type are included as well. Candidates come from
   `leggi_ripresa.py prepara`, which searches for continuation up to 10 pages on each side.
   Writes `training/principi/<caso>_ripresa_righe_v2.jsonl`.

   Usage:  .venv/bin/python tools/prepara_l05.py --caso urgenda
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
        # L05 runs on all rows. Already-judged rows are used to measure L05 against human annotators (the loaders
        # do not modify them); chain mentions show whether the proposed type was wrong (rule R02 still applies:
        # no principles and no continuation for chain mentions).
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
