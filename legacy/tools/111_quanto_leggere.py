"""QUANTO LAVORO: scendendo nella classifica del riordinatore (pagina = voto migliore fra le sonde), dopo quante
pagine lette si trovano il 50, 75, 90, 100% delle riprese confermate note, e quante scartate si incontrano.
   python3 tools/111_quanto_leggere.py riordino.csv righe_firestore.json
"""
import csv, json, sys
best = {}
for r in csv.DictReader(open(sys.argv[1], encoding='utf-8')):
    best[r['pagina_id']] = max(best.get(r['pagina_id'], 0.0), float(r['riordino']))
ordine = sorted(best, key=lambda p: -best[p]); posto = {p: k for k, p in enumerate(ordine, 1)}
fs = json.load(open(sys.argv[2], encoding='utf-8'))
pr = lambda x: str(x.get('validato_pagina') or x.get('proposto_pagina') or '').strip()
sem = lambda x: x.get('proposto_rete') in ('semantica', 'entrambe')
conf = {f"{x['document_id']}#p{pr(x)}" for x in fs if sem(x) and x.get('esito') == 'confermata'}
scar = {f"{x['document_id']}#p{pr(x)}" for x in fs if sem(x) and x.get('esito') == 'scartata'} - conf
trovate = sorted(posto[p] for p in conf if p in posto)
print(f'pagine in classifica {len(ordine)}; confermate note {len(conf)}, in classifica {len(trovate)}')
for q in (0.5, 0.75, 0.9, 1.0):
    n = max(1, round(q * len(conf)))
    if n <= len(trovate):
        k = trovate[n - 1]
        print(f'  {int(q*100)}% delle confermate ({n}): leggere le prime {k} pagine; scartate note incontrate {sum(1 for p in scar if posto.get(p, 10**9) <= k)}')
    else:
        print(f'  {int(q*100)}% delle confermate ({n}): non raggiungibile, in classifica ne stanno {len(trovate)}')
