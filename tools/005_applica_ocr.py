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
     3. somiglianza: sulle pagine vecchie leggibili (dal 02/10) con almeno 10 parole latine o numeri, la mediana della quota di quelle della pagina
        vecchia che si ritrova nella pagina OCR e' almeno 0,15. Misura dell'1/10 sui sei documenti: col PDF giusto
        0,25-0,50 (bassa dove le pagine vecchie erano spazzatura), col PDF sbagliato di Lee 0,02.
   Si sostituisce una pagina solo se la vecchia e' illeggibile e la nuova leggibile (freni.leggibile). Copia del
   markdown in training/ocr/prima/ (una volta sola), elenco in training/ocr/pagine_sostituite.json, indice delle pagine
   ricostruito dalla copia index/pagine/pagine.prima-ocr-2026-10-01.jsonl.gz.

   Uso:  .venv/bin/python tools/005_applica_ocr.py <document_id> [...] [--scrivi]
"""
import argparse, gzip, hashlib, json, pathlib, re, shutil, statistics, sys
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
_m_freni = __import__('034_freni')
leggibile = _m_freni.leggibile
_m_posizione_dopo_ocr = __import__('006_posizione_dopo_ocr')
_pagine = _m_posizione_dopo_ocr._pagine
O = QUI/'training'/'ocr'
TOK = re.compile(r'\d{2,}|[A-Za-z]{5,}')
# 02/10/2026: in coreano, giapponese e cinese il testo estratto dal PDF e' spesso la lingua giusta resa in lettere latine
# senza senso («Ep etizi+ Seals Az | Sol] Sale»): il freno 1 la dice leggibile e la pagina non si sostituiva. In un
# documento in queste lingue la pagina si sostituisce anche quando la vecchia ha meno del 5% di caratteri CJK e l'OCR
# piu' del 20% (e almeno 200 caratteri; al 30% restava fuori la copertina con la citazione coreana di Urgenda, 28%). La
# somiglianza (controllo 3) si misura su parole latine e qui non dice niente: fa fede l'impronta del PDF.
CJK = re.compile(r'[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]')
def quota_cjk(t):
    return len(CJK.findall(t)) / max(1, len(t.strip()))
def da_sostituire(vecchia, nuova, cjk):
    if not leggibile(vecchia)[0] and leggibile(nuova)[0]:
        return True
    return cjk and quota_cjk(vecchia) < 0.05 and quota_cjk(nuova) > 0.2 and len(nuova.strip()) > 200


def copia_prima(doc, md):
    """la copia del markdown prima dell'OCR. Fino al 02/10 si chiamava col nome del file, e due documenti in cartelle
    diverse possono avere lo stesso nome (i due `alliance-for-water-efficiency-...petition-for-review`, a550 e 69db): il
    secondo avrebbe letto la copia del primo. Il controllo delle pagine l'ha fermato (27 contro 23) e nulla e' stato
    scritto. Ora la copia porta il codice del documento; quella vecchia vale solo se e' davvero di questo documento."""
    nuova = O/'prima'/f'{doc}.md'
    if nuova.exists():
        return nuova
    vecchia = O/'prima'/md.name
    if vecchia.exists() and re.search(rf"^document_id:\s*'?{re.escape(doc)}'?\s*$", vecchia.read_text(encoding='utf-8')[:3000], re.M):
        return vecchia
    return nuova


def controlla(doc, lista, o, cjk=False):
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
    base = copia_prima(doc, md)
    testo = (base if base.exists() else md).read_text(encoding='utf-8')
    pag = {n: testo[a:b] for a, b, n in _pagine(testo)}
    if len(ocr) != len(pag):
        return None, f'pagine OCR {len(ocr)} contro {len(pag)} del markdown'
    sim = []
    for n, t in pag.items():
        # 02/10/2026: solo le pagine vecchie LEGGIBILI. Dove il testo vecchio e' spazzatura di codifica (caratteri di
        # controllo, font senza mappa) le «parole» trovate sono frammenti a caso e la somiglianza esce 0,00-0,12 anche
        # col PDF giusto: 19 documenti su 108 fermati cosi', a impronta giusta. Il PDF lo garantisce l'impronta (0).
        if not leggibile(t)[0]:
            continue
        a = set(TOK.findall(t))
        if len(a) >= 10:
            sim.append(len(a & set(TOK.findall(ocr[n-1]))) / len(a))
    med = statistics.median(sim) if sim else None
    if med is not None and med < 0.15 and not cjk:
        return None, f'somiglianza mediana {med:.2f}: il testo OCR non e\' quello del documento'
    return (md, base, testo, pag, ocr), f'ok (somiglianza mediana {med if med is None else round(med, 2)} su {len(sim)} pagine)'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('doc', nargs='+'); ap.add_argument('--scrivi', action='store_true')
    a = ap.parse_args()
    o = json.load(open(QUI/'training'/'da_ocr_documenti.json'))
    lista = {l.split('|')[0]: l.strip().split('|')[2] for l in open(O/'lista.txt') if l.strip()}
    lingue = {l.split('|')[0]: l.strip().split('|')[1] for l in open(O/'lista.txt') if l.strip()}
    sost = json.load(open(O/'pagine_sostituite.json'))
    cambiati = False
    for doc in a.doc:
        cjk = bool(re.search(r'kor|jpn|chi', lingue.get(doc, '')))
        dati, esito = controlla(doc, lista, o, cjk)
        print(doc[:70], '->', esito)
        if not dati:
            continue
        md, base, testo, pag, ocr = dati
        nuove = {n: ocr[n-1].strip() for n, t in pag.items() if da_sostituire(t, ocr[n-1], cjk)}
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
        n, visti = 0, set()
        with gzip.open(bak, 'rt') as f, gzip.open(str(src) + '.nuovo', 'wt') as g:
            for l in f:
                x = json.loads(l)
                if x['id'] in sost:
                    x['testo'] = sost[x['id']]; x['ocr'] = '2026-10-01'; n += 1
                g.write(json.dumps(x, ensure_ascii=False) + '\n'); visti.add(x['id'])
            # 02/10/2026: le pagine che all'epoca erano vuote non erano nell'indice (228 su 3.044): si aggiungono, con
            # le posizioni nel markdown di PRIMA dell'OCR, come tutte le altre voci dell'indice
            for k in sorted(set(sost) - visti):
                d, n_ = k.split('#p'); voce = o.get(d)
                if not voce:
                    continue
                base_ = copia_prima(d, QUI/voce['file'])
                t_ = (base_ if base_.exists() else QUI/voce['file']).read_text(encoding='utf-8')
                pos = {str(nn): (aa, bb) for aa, bb, nn in _pagine(t_)}
                if n_ not in pos:
                    continue
                g.write(json.dumps({'id': k, 'doc': d, 'file': voce['file'], 'pagina': n_, 'da': str(pos[n_][0]), 'a': str(pos[n_][1]),
                                    'testo': sost[k], 'ocr': '2026-10-02'}, ensure_ascii=False) + '\n'); n += 1
        pathlib.Path(str(src) + '.nuovo').replace(src)
        print('indice: pagine col testo OCR', n, '| elenco', len(sost))


if __name__ == '__main__':
    main()
