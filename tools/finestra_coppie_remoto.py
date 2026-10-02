"""Le coppie per `misura_finestra.py`, generate su ReCaS dall'indice delle pagine che c'e' gia' (28/09/2026).
   Caricare il file di coppie dal Mac (630 MB) andava a 60 KB/s. Qui si mandano solo gli elenchi degli atti.
   Stessa maschera di `prepara_training.mascheratore` (copiata qui: su ReCaS quel modulo non c'e')."""
import gzip, json, pathlib, re
import yaml
QUI = pathlib.Path(__file__).resolve().parent.parent
P = QUI/'training'/'principi'
SEGNAPOSTO = '⟦CASO_CITATO⟧'


def mascheratore(forme):
    pezzi = sorted({f for f in forme if len(f) > 3}, key=len, reverse=True)
    pat = '|'.join(re.escape(f) for f in pezzi)
    pat += r'|ECLI:[A-Z]{2}:[A-Z]+:\d{4}:\d+|\b\d{2}/\d{5}\b|\b200\.\d{3}\.\d{3}/\d{2}\b'
    return re.compile(pat, re.I)


conf = yaml.safe_load(open(QUI/'cited-cases'/'urgenda.yaml', encoding='utf-8'))
maschera = mascheratore([str(f) for f in conf['forme']] + [conf.get('nome', '')])
principi = {s['id']: ' '.join(s['testo'].split()) for s in conf['semantic_queries']}
doc = json.load(open(P/'urgenda_finestra_documenti.json'))
gruppo_di = {d: 'cita' for d in doc['cita']} | {d: 'stesso_caso' for d in doc['stesso_caso']}
n = 0
with gzip.open(QUI/'index'/'pagine'/'pagine.jsonl.gz', 'rt', encoding='utf-8') as f, \
     open(P/'urgenda_finestra_coppie.jsonl', 'w', encoding='utf-8') as out:
    for l in f:
        x = json.loads(l); g = gruppo_di.get(x['id'].split('#p')[0])
        if not g:
            continue
        testo = maschera.sub(SEGNAPOSTO, ' '.join(x['testo'].split()))
        for pid, q in principi.items():
            out.write(json.dumps({'pagina_id': x['id'], 'gruppo': g, 'dove': 'pagina', 'principio': pid, 'q': q, 'd': testo}, ensure_ascii=False) + '\n')
        n += 1
print('pagine', n)
