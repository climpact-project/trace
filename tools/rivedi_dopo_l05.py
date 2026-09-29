"""Flag already-judged rows on which L05 disagrees with the human judgment.

   Rows judged in Uptakes were decided against L04 proposals with a narrow window (2 pages before to 3 after).
   L05 also reads the case file, applies the footnote rule and looks up to 10 pages on each side. Rows are not
   re-judged wholesale: for each confirmed row the current L05 proposal is computed (same rules as
   `carica_ripresa.proposta`) and the row is flagged only if
     - L05 selects a principle the annotator did not confirm, or selects none of the confirmed ones;
     - L05 proposes a continuation page the annotator did not confirm (in particular distant ones, 4-10 pages).
   With --scrivi the row receives `rivedere` = {motivi, l05_principi, l05_seguito, quando}. The judgment itself is
   not modified; the Uptakes view shows the row as "to review" to its annotator.

   Usage:  .venv/bin/python tools/rivedi_dopo_l05.py --caso urgenda [--scrivi]
"""
import argparse, collections, datetime, json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from carica_ripresa import carica, proposta


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--caso', required=True); ap.add_argument('--scrivi', action='store_true')
    a = ap.parse_args()
    ids, par, brano, ds, cand = carica(a.caso)
    from google.cloud import firestore
    db = firestore.Client(project='climpact-drp')
    conti, scritture = collections.Counter(), []
    for d in db.collection('corpus_rows').where(filter=firestore.FieldFilter('caso_citato', '==', a.caso)).stream():
        r = d.to_dict()
        if r.get('proposto_rete') not in ('lessicale', 'entrambe') or r.get('esito') != 'confermata':
            continue
        conti['giudicate e confermate'] += 1
        if not (ds.get(d.id) or {}).get('seconda'):
            conti['senza lettura L05'] += 1; continue
        c = proposta(a.caso, d.id, ids, par, brano, ds, cand, r.get('validato_tipo_citazione') or r.get('proposto_tipo_citazione') or '')
        l05 = set(c['proposto_principi'] or []) - {'nessuno'}
        umani = set(r.get('validato_principi') or []) - {'nessuno'}
        pag_l05 = {v['pagina'] for v in c['proposto_estensione'] if v.get('prosegue')}
        pag_umane = {(e['pagina'] if isinstance(e, dict) else e) for e in (r.get('validato_estensione') or [])}
        p = int(r.get('validato_pagina') or r.get('proposto_pagina') or 0)
        motivi = []
        if l05 - umani:
            motivi.append('L05 spunta principi non confermati: ' + ', '.join(sorted(l05 - umani)))
        if umani and not (l05 & umani):
            motivi.append('L05 non spunta nessuno dei principi confermati')
        nuove = pag_l05 - pag_umane
        if nuove:
            lontane = sorted(k for k in nuove if not -2 <= k - p <= 3)
            motivi.append('L05 propone seguito su pagine non confermate: ' + ', '.join(map(str, sorted(nuove)))
                          + (f' (lontane: {", ".join(map(str, lontane))})' if lontane else ''))
        if motivi:
            conti['da rivedere'] += 1
            scritture.append((d.reference, {'rivedere': {
                'motivi': motivi, 'l05_principi': sorted(l05), 'l05_seguito': sorted(pag_l05),
                'quando': datetime.date.today().isoformat(), 'fatto': False}}))
            print(r.get('codice'), '|', ' / '.join(motivi))
        else:
            conti['L05 concorda'] += 1
    print(json.dumps(dict(conti), ensure_ascii=False))
    if a.scrivi and scritture:
        b = db.batch()
        for ref, x in scritture:
            b.update(ref, x)
        b.commit(); print('scritte', len(scritture))


if __name__ == '__main__':
    main()
