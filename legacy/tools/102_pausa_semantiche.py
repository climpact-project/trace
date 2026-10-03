"""LE RIGHE SEMANTICHE DA FARE VANNO IN FONDO ALLA CODA (27/09/2026, decisione del PI, §63.25).

   La rilettura dei giudizi di luglio (§63.24) ha trovato 3-4 riprese implicite vere su 400 pagine: il lavoro
   riparte dalle citazioni esplicite e l'implicito si cerca come loro seguito. Le righe semantiche ancora da
   giudicare non si cancellano: `ordine` va oltre 9 (le lessicali stanno fra 0 e 1), il valore di prima resta in
   `ordine_prima`, e la coda della piattaforma non le mostra finche' non si sceglie «Semantic».
   Per tornare indietro: `ordine = ordine_prima` e togliere `pausa_semantica`.

   Uso:  .venv/bin/python tools/102_pausa_semantiche.py [--scrivi]
"""
import argparse, collections
from google.cloud import firestore
ap = argparse.ArgumentParser(); ap.add_argument('--scrivi', action='store_true'); a = ap.parse_args()
db = firestore.Client(project='climpact-drp')
w = []; n = collections.Counter()
for d in db.collection('corpus_rows').where(filter=firestore.FieldFilter('proposto_rete', '==', 'semantica')).stream():
    r = d.to_dict()
    if r.get('esito') or r.get('da_discutere') or r.get('pausa_semantica'):
        n['non toccata'] += 1; continue
    o = r.get('ordine')
    if o is None:
        n['senza ordine'] += 1; continue
    w.append((d.reference, {'ordine_prima': o, 'ordine': 10 + float(o), 'pausa_semantica': '2026-09-27'}))
    n[f"in pausa {r.get('caso_citato')}"] += 1
print(dict(n))
if a.scrivi:
    for i in range(0, len(w), 400):
        b = db.batch()
        for ref, c in w[i:i+400]:
            b.update(ref, c)
        b.commit()
    print('scritte', len(w))
else:
    print('ANTEPRIMA: niente scritto')
