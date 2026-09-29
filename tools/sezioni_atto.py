"""Section tree of a filing, built without a language model (PageIndex-style experiment).

   PageIndex (VectifyAI) builds the table of contents of a long document and navigates it. TRACE needs it for one
   question: whether a high-scoring page lies in the SAME SECTION as the citation (true continuation) or elsewhere
   (same topic only). Only 67 of the 314 filings citing Urgenda carry an embedded PDF outline; for the others the
   outline is inferred from headings: short lines in a font larger than the body text, or bold and numbered
   ("V.1.2", "A.", "3."). The heuristic is measured on filings that have an outline: how many true headings it
   recovers and how many it invents.

   Usage:  .venv/bin/python tools/sezioni_atto.py misura      (inferred headings vs. the PDF outline)
"""
import collections, glob, json, pathlib, re, statistics, sys
import fitz
QUI = pathlib.Path(__file__).resolve().parent.parent
T = QUI/'training'

NUMERO = re.compile(r'^\s*((\d+(\.\d+)*\.?)|([IVXLC]+\.)|([A-Z]\.)|(\([a-z0-9]+\))|(§\s*\d+))\s+\S')


def titoli(pdf):
    """Return [(level, title, page)] like get_toc(). Level 1 = largest font among the headings."""
    doc = fitz.open(pdf)
    righe, corpi = [], []
    for n, pg in enumerate(doc, 1):
        for b in pg.get_text('dict')['blocks']:
            for l in b.get('lines', []):
                sp = [s for s in l['spans'] if s['text'].strip()]
                if not sp:
                    continue
                t = ' '.join(s['text'].strip() for s in sp)
                size = max(s['size'] for s in sp)
                bold = all(('Bold' in s['font']) or (s['flags'] & 16) for s in sp)
                corpi += [round(x['size'], 1) for x in sp for _ in x['text']]
                righe.append((n, t, round(size, 1), bold))
    if not corpi:
        return []
    corpo = statistics.mode(corpi)
    out = []
    for n, t, size, bold in righe:
        parole = len(t.split())
        if parole == 0 or parole > 14 or t.endswith((',', ';')) or re.fullmatch(r'[\d\s./-]+', t):
            continue
        grande = size >= corpo * 1.15
        numerato = bool(NUMERO.match(t))
        if grande and (bold or numerato or t.isupper()) or (bold and numerato):
            out.append((size, t, n))
    if not out:
        return []
    taglie = sorted({s for s, _, _ in out}, reverse=True)
    return [(min(taglie.index(s) + 1, 3), t, n) for s, t, n in out]


def sezione(toc, p, livello=None):
    best = None
    for i, (lv, _, pg) in enumerate(toc):
        if livello and lv > livello:
            continue
        if pg <= p:
            best = i
    return best


def pdf_di():
    F = json.load(open(T/'fase2'/'urgenda_corpus_rows_2026-09-26.json'))
    return {x['document_id']: QUI/x['file_pdf'] for x in F if x.get('file_pdf')}


def misura():
    R = [json.loads(l) for l in open(T/'lessicali_urgenda_righe.jsonl')]
    P = pdf_di()
    ok = trovati = veri = inventati = 0
    for d in sorted({r['document_id'] for r in R}):
        if d not in P or not P[d].exists():
            continue
        vero = fitz.open(P[d]).get_toc()
        if len(vero) < 3:
            continue
        mio = titoli(P[d])
        pv = {(pg) for _, _, pg in vero}
        pm = {(pg) for _, _, pg in mio}
        ok += 1
        veri += len(pv); trovati += len(pv & pm); inventati += len(pm - pv)
    print(f'atti con indice: {ok}; pagine con un titolo vero {veri}, ritrovate {trovati} ({trovati / max(veri, 1):.0%}); '
          f'pagine con titoli ricavati che l\'indice non ha {inventati}')


if __name__ == '__main__':
    {'misura': misura}[sys.argv[1]]()
