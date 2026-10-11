"""Gli atti di ogni caso citante nell'elenco dei casi di n01_sito.json (11/10/2026).

Il sito cercava il caso di un atto nel file dei casi della mappa (casi.json, dal dump del 4/10): 19 atti citanti non vi
compaiono, e la scheda li diceva «non legati a un caso». Ma l'indice N01 conta i casi dal case_id di corpus_rows, che
ogni riga porta. Qui si aggiunge a ogni voce di casi_elenco l'elenco dei suoi document_id, letti da corpus_rows, senza
ricalcolare niente: le cifre dell'indice restano quelle. Sola lettura su Firestore.

  .venv/bin/python tools/n01_atti_dei_casi.py pubblicazione/influenza/n01_sito.json
"""
import json, sys, pathlib, collections
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import n01_influenza as N

p = pathlib.Path(sys.argv[1])
sito = json.loads(p.read_text())
righe = N.leggi_firestore(list(sito['decisioni'].keys()))
for k, d in sito['decisioni'].items():
    atti = collections.defaultdict(set)
    for r in righe[k]:
        if r.get('case_id') and r.get('document_id'):
            atti[r['case_id']].add(r['document_id'])
    senza = 0
    for c in d.get('casi_elenco', []):
        c['atti'] = sorted(atti.get(c['id'], ()))
        if not c['atti']:
            senza += 1
    print(k, len(d.get('casi_elenco', [])), 'casi;', senza, 'senza atti')
p.write_text(json.dumps(sito, ensure_ascii=False, separators=(',', ':')))
