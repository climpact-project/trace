"""LE COPPIE PER IL RERANKER DOPO L'OCR (01/10/2026).

   Le righe che stanno nei documenti rifatti con l'OCR (lette prima su pagine illeggibili) e le righe nuove trovate sul
   testo OCR vanno rilette, e il TRACE-Reranker (T01) deve ridare i punteggi: al brano della riga per ogni principio, e
   alle pagine rifatte di quei documenti (le pagine vicine fra cui la lettura sceglie il seguito). Stessa preparazione
   delle coppie della prima volta (`prepara_training.mascheratore`: il nome del caso si copre con un segnaposto).
   Scrive training/principi/ocr2_coppie.jsonl; il lavoro su ReCaS scrive ocr2_punteggi_0.jsonl, che si divide per caso
   in <caso>_punteggi_ocr2.jsonl (caricati per ultimi: prendono il posto dei punteggi dati alle pagine illeggibili).

   Uso:  .venv/bin/python tools/coppie_ocr.py <file con gli id delle righe>
"""
import gzip, json, pathlib, sys, yaml
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
from prepara_training import mascheratore, SEGNAPOSTO
T, P = QUI/'training', QUI/'training'/'principi'
INIZIO, FINE = '[[INIZIO DEL BRANO SEGNALATO]]', '[[FINE DEL BRANO SEGNALATO]]'


def main():
    ids = set(pathlib.Path(sys.argv[1]).read_text().split())
    sost = json.load(open(T/'ocr'/'pagine_sostituite.json'))
    out, n = open(P/'ocr2_coppie.jsonl', 'w', encoding='utf-8'), 0
    for caso in ['urgenda', 'neubauer', 'future-generations']:
        righe = {}
        for l in open(T/f'lessicali_{caso}_righe.jsonl', encoding='utf-8'):
            x = json.loads(l)
            if x['id'] in ids:
                righe[x['id']] = x
        if not righe:
            continue
        conf = yaml.safe_load(open(QUI/'cited-cases'/f'{caso}.yaml', encoding='utf-8'))
        maschera = mascheratore([str(f) for f in conf['forme']] + [conf.get('nome', '')])
        principi = {s['id']: ' '.join(s['testo'].split()) for s in conf['semantic_queries']}
        for r in righe.values():
            ctx = r['contesto']; a, b = ctx.find(INIZIO), ctx.find(FINE)
            brano = ctx[max(0, a - 800):b + len(FINE) + 800]
            for t in (INIZIO, FINE, '⟦', '⟧'):
                brano = brano.replace(t, '')
            brano = maschera.sub(SEGNAPOSTO, ' '.join(brano.split()))
            for pid, q in principi.items():
                out.write(json.dumps({'caso': caso, 'riga': r['id'], 'dove': 'brano', 'pagina': r['pagina'], 'principio': pid,
                                      'q': q, 'd': brano}, ensure_ascii=False) + '\n'); n += 1
        docs = {r['document_id'] for r in righe.values()}
        for pagid, testo in sost.items():
            if pagid.split('#')[0] in docs:
                d = maschera.sub(SEGNAPOSTO, ' '.join(testo.split()))
                for pid, q in principi.items():
                    out.write(json.dumps({'caso': caso, 'pagina_id': pagid, 'dove': 'vicina', 'principio': pid, 'q': q, 'd': d},
                                         ensure_ascii=False) + '\n'); n += 1
        print(caso, 'righe', len(righe), 'documenti', len(docs))
    out.close(); print('coppie', n, '->', P/'ocr2_coppie.jsonl')


if __name__ == '__main__':
    main()
