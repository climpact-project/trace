"""UNISCE LE LISTE DI PIU' RETRIEVER (26/09/2026): una coppia sonda-pagina entra se la trova almeno uno dei due;
`posto` e `punteggio` sono quelli del retriever che la mette piu' in alto. Uso:
   python3 tools/043_unisci_candidati.py uscita.csv lista1.csv lista2.csv ...
"""
import csv, sys
uscita, liste = sys.argv[1], sys.argv[2:]
best = {}
for f in liste:
    for r in csv.DictReader(open(f, encoding='utf-8')):
        k = (r['sonda'], r['pagina_id'])
        if k not in best or int(r['posto']) < int(best[k]['posto']):
            best[k] = r
campi = ['sonda', 'posto', 'punteggio', 'pagina_id', 'document_id', 'case_id', 'pagina']
with open(uscita, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=campi, extrasaction='ignore'); w.writeheader()
    for r in best.values():
        w.writerow(r)
print(f'{len(best)} coppie, {len({k[1] for k in best})} pagine -> {uscita}')
