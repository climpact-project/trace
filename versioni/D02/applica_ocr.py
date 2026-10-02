"""METTERE NEL CORPUS IL TESTO OCR DELLE PAGINE ILLEGGIBILI (01/10/2026).

   Prima era un comando a mano, e due documenti su sette avevano preso il PDF sbagliato (un altro PDF della stessa
   cartella): la richiesta di parere alla Corte interamericana (249 pagine contro 138, visto dal numero di pagine) e la
   petizione taiwanese Lee (12 pagine come il giusto: visto solo perche' il nome del caso era sparito dalla pagina).
   Qui ogni documento passa quattro controlli PRIMA di toccare qualunque file, e se uno fallisce il documento si salta:
     0. L'IMPRONTA (proposta del PI, 01/10/2026): il markdown porta nell'intestazione `sha256_pdf`, l'impronta del PDF da
        cui e' nato. Il PDF usato per l'OCR deve avere quella impronta, oppure deve averla il suo `.orig` (a fine luglio
        sei di questi PDF sono stati riscritti sul posto e l'originale e' rimasto accanto come `.pdf.orig`). Misura
        dell'1/10: i due PDF sbagliati non combaciano, i sette giusti si' (uno diretto, sei tramite `.orig`);
     1. il PDF ha lo stesso nome del markdown (cartella documents/ invece di markdown/);
     2. l'OCR ha lo stesso numero di pagine del markdown;
     3. somiglianza: sulle pagine con almeno 10 parole latine o numeri, la mediana della quota di quelle della pagina
        vecchia che si ritrova nella pagina OCR e' almeno 0,15. Misura dell'1/10 sui sei documenti: col PDF giusto
        0,25-0,50 (bassa dove le pagine vecchie erano spazzatura), col PDF sbagliato di Lee 0,02.
   Si sostituisce una pagina solo se la vecchia e' illeggibile e la nuova leggibile (freni.leggibile). Copia del
   markdown in training/ocr/prima/ (una volta sola), elenco in training/ocr/pagine_sostituite.json, indice delle pagine
   ricostruito dalla copia index/pagine/pagine.prima-ocr-2026-10-01.jsonl.gz.

   Uso:  .venv/bin/python tools/applica_ocr.py <document_id> [...] [--scrivi]
"""
import argparse, gzip, hashlib, json, pathlib, re, shutil, statistics, sys
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
from freni import leggibile
from posizione_dopo_ocr import _pagine
O = QUI/'training'/'ocr'
TOK = re.compile(r'\d{2,}|[A-Za-z]{5,}')


def controlla(doc, lista, o):
    md = QUI/o[doc]['file']
    pdf = QUI/lista[doc]
    m = re.search(r"^sha256_pdf:\s*'?([0-9a-f]{64})", md.read_text(encoding='utf-8')[:6000], re.M)
    if not m:
        return None, 'il markdown non porta l\'impronta del suo PDF'
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else ''
    if m.group(1) not in (sha(pdf), sha(pdf.with_name(pdf.name + '.orig'))):
        return None, f'impronta diversa: {pdf.name} non e\' il PDF da cui e\' nato il markdown'
    giusto = QUI/str(pathlib.Path(o[doc]['file'].replace('markdown/', 'documents/', 1)).with_suffix('.pdf'))
    if pdf.resolve() != giusto.resolve():
        return None, f'PDF diverso dal markdown: {pdf.name}'
    ocr = (O/f'{doc}.txt').read_text(encoding='utf-8').split('\f')
    if ocr and not ocr[-1].strip():
        ocr = ocr[:-1]
    base = O/'prima'/md.name
    testo = (base if base.exists() else md).read_text(encoding='utf-8')
    pag = {n: testo[a:b] for a, b, n in _pagine(testo)}
    if len(ocr) != len(pag):
        return None, f'pagine OCR {len(ocr)} contro {len(pag)} del markdown'
    sim = []
    for n, t in pag.items():
        a = set(TOK.findall(t))
        if len(a) >= 10:
            sim.append(len(a & set(TOK.findall(ocr[n-1]))) / len(a))
    med = statistics.median(sim) if sim else None
    if med is not None and med < 0.15:
        return None, f'somiglianza mediana {med:.2f}: il testo OCR non e\' quello del documento'
    return (md, base, testo, pag, ocr), f'ok (somiglianza mediana {med if med is None else round(med, 2)} su {len(sim)} pagine)'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('doc', nargs='+'); ap.add_argument('--scrivi', action='store_true')
    a = ap.parse_args()
    o = json.load(open(QUI/'training'/'da_ocr_documenti.json'))
    lista = {l.split('|')[0]: l.strip().split('|')[2] for l in open(O/'lista.txt') if l.strip()}
    sost = json.load(open(O/'pagine_sostituite.json'))
    cambiati = False
    for doc in a.doc:
        dati, esito = controlla(doc, lista, o)
        print(doc[:70], '->', esito)
        if not dati:
            continue
        md, base, testo, pag, ocr = dati
        nuove = {n: ocr[n-1].strip() for n, t in pag.items() if not leggibile(t)[0] and leggibile(ocr[n-1])[0]}
        print(f'   pagine {len(pag)}, illeggibili prima {sum(not leggibile(t)[0] for t in pag.values())}, sostituite {len(nuove)}')
        if not a.scrivi:
            continue
        if not base.exists():
            shutil.copy(md, base)
        pezzi, ultimo = [], 0
        for a_, b_, n in _pagine(testo):
            if n in nuove:
                inizio = testo.index('-->', a_) + 3
                pezzi += [testo[ultimo:inizio], '\n' + nuove[n] + '\n\n']; ultimo = b_
        pezzi.append(testo[ultimo:]); md.write_text(''.join(pezzi), encoding='utf-8')
        for k in [k for k in sost if k.startswith(doc + '#')]:
            del sost[k]
        sost.update({f'{doc}#p{n}': t for n, t in nuove.items()})
        cambiati = True
    if cambiati:
        json.dump(sost, open(O/'pagine_sostituite.json', 'w'), ensure_ascii=False)
        src, bak = QUI/'index/pagine/pagine.jsonl.gz', QUI/'index/pagine/pagine.prima-ocr-2026-10-01.jsonl.gz'
        n = 0
        with gzip.open(bak, 'rt') as f, gzip.open(str(src) + '.nuovo', 'wt') as g:
            for l in f:
                x = json.loads(l)
                if x['id'] in sost:
                    x['testo'] = sost[x['id']]; x['ocr'] = '2026-10-01'; n += 1
                g.write(json.dumps(x, ensure_ascii=False) + '\n')
        pathlib.Path(str(src) + '.nuovo').replace(src)
        print('indice: pagine col testo OCR', n, '| elenco', len(sost))


if __name__ == '__main__':
    main()
