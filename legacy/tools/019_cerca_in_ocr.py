"""LE CITAZIONI NEI DOCUMENTI RIFATTI CON L'OCR (01/10/2026). Sette documenti della mappa avevano pagine illeggibili
   (font rotti: coreano, cinese, spagnolo): la ricerca per nome su quelle pagine non poteva trovare niente. Qui si
   cercano le forme dei tre casi nel testo OCR (`training/ocr/<doc>.txt`, pagine separate da \\f) e si confrontano con
   le righe che la banca dati ha gia' per quel documento e quella pagina. Solo lettura: scrive l'elenco delle pagine
   con una citazione nuova in `training/ocr/citazioni_nuove.json`, da caricare poi con le letture."""
import json, pathlib, re, yaml
from google.cloud import firestore
QUI = pathlib.Path(__file__).resolve().parent.parent
O = QUI/'training'/'ocr'
forme = {}
for caso in ['urgenda', 'neubauer', 'future-generations']:
    c = yaml.safe_load(open(QUI/'cited-cases'/f'{caso}.yaml', encoding='utf-8'))
    ff = [f for f in (c.get('forme') or c.get('forms') or c.get('nomi') or []) if isinstance(f, str) and len(f) >= 4]
    forme[caso] = re.compile('|'.join(re.escape(f) for f in sorted(ff, key=len, reverse=True)), re.I) if ff else None
db = firestore.Client(project='climpact-drp')
nuove, viste = [], 0
for t in sorted(p for p in O.glob('*.txt') if p.stem != 'lista' and '.' not in p.stem):
    doc = t.stem
    pagine = t.read_text(encoding='utf-8').split('\f')
    gia = {(r.get('caso_citato'), str(r.get('proposto_pagina'))) for r in (x.to_dict() for x in db.collection('corpus_rows').where(filter=firestore.FieldFilter('document_id', '==', doc)).get())}
    for n, testo in enumerate(pagine, 1):
        for caso, rx in forme.items():
            if rx and rx.search(testo):
                viste += 1
                if (caso, str(n)) not in gia:
                    m = rx.search(testo)
                    nuove.append({'doc': doc, 'pagina': n, 'caso': caso, 'forma': m.group(0), 'contesto': ' '.join(testo[max(0, m.start()-300):m.end()+300].split())})
json.dump(nuove, open(O/'citazioni_nuove.json', 'w'), ensure_ascii=False, indent=1)
print('pagine con un nome nel testo OCR:', viste, '| senza riga in banca dati:', len(nuove), '->', O/'citazioni_nuove.json')
