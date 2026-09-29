#!/usr/bin/env python3
"""Split the markdown corpus into chunks for dense indexing.

Two granularities. Indexed chunks are SHORT (one or two paragraphs): a long
chunk yields a vector that averages several topics and matches nothing
precisely. The short chunk is not what is later read to classify a citation,
which needs the surrounding argument; each chunk therefore carries its
coordinates (`char_start`, `char_end`) so the reader can reopen the document
and take a wider window. Precise retrieval, contextual judgment.

Boundaries, not fixed length. A fixed-length cut splits sentences, and a
half sentence silently degrades its vector. Chunks are cut on paragraphs;
paragraphs that are too long are split on sentences.

Overlap. A passage straddling two chunks would be truncated in both and match
the query in neither. Each chunk repeats the tail (OVERLAP characters) of the
previous one.

Page numbers. The `<!-- page N -->` markers are already in the text; the last
marker seen is propagated so every chunk knows its page, which makes results
verifiable by hand.

Usage: python tools/build_chunks.py [<case_id>]   -> index/chunks.jsonl
"""

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
MD = HERE / 'markdown'
OUT = HERE / 'index' / 'chunks.jsonl'

# Sizes in characters. Models work in tokens, but characters are observable
# and tokenizer-independent: for English and Italian legal text the ratio is
# about 4 characters per token, so 1,100 characters fit well within any
# context window.
TARGET = 1100          # target chunk size
MIN_CHUNK = 250        # below this size a chunk is merged with its neighbour
OVERLAP = 200          # tail of the previous chunk repeated at the start

PAGE_RE = re.compile(r'<!--\s*page\s+(\d+)\s*-->')
# Sentence end: period, semicolon, colon, question or exclamation mark followed
# by whitespace and an uppercase letter. The negative lookbehinds exclude common
# abbreviations in legal documents ('v.', 'No.', 'Inc.', 'Cir.', ...) that would
# otherwise split a case citation in half.
SENT_RE = re.compile(
    r'(?<!\bv)(?<!\bNo)(?<!\bInc)(?<!\bCir)(?<!\bCo)(?<!\bLtd)(?<!\bMr)(?<!\bMrs)'
    r'[.;:?!]\s+(?=[A-Z"“(])'
)


def leggi(md: Path):
    """Split front matter from body, returning (meta, body, body offset).

    Offsets stored in chunks refer to the WHOLE FILE, not to the body alone:
    whoever reopens the document to take the wider window opens the file."""
    testo = md.read_text(encoding='utf-8', errors='replace')
    if not testo.startswith('---\n'):
        return {}, testo, 0
    fine = testo.find('\n---\n', 4)
    if fine < 0:
        return {}, testo, 0
    testa, corpo_off = testo[4:fine], fine + 5
    meta = {}
    for riga in testa.split('\n'):
        m = re.match(r'^([a-z_0-9]+):\s*(.*)$', riga)
        if m:
            v = m.group(2).strip()
            if v.startswith("'") and v.endswith("'") and len(v) >= 2:
                v = v[1:-1].replace("''", "'")
            meta[m.group(1)] = v
    return meta, testo[corpo_off:], corpo_off


def pagine(corpo: str):
    """List of (offset, page number) for the page markers, in order."""
    return [(m.start(), int(m.group(1))) for m in PAGE_RE.finditer(corpo)]


def pagina_di(marks, off: int) -> int:
    """Page containing an offset: the last marker before it (1 if none)."""
    p = 0
    for pos, num in marks:
        if pos <= off:
            p = num
        else:
            break
    return p or 1


def spezza_lungo(testo: str, base: int):
    """Split a paragraph longer than TARGET on sentence boundaries."""
    tagli = [0] + [m.end() for m in SENT_RE.finditer(testo)] + [len(testo)]
    pezzi, inizio = [], 0
    for i in range(1, len(tagli)):
        if tagli[i] - inizio >= TARGET or i == len(tagli) - 1:
            if tagli[i] > inizio:
                pezzi.append((base + inizio, base + tagli[i]))
            inizio = tagli[i]
    return pezzi


def frammenti(corpo: str):
    """Chunk boundaries (start, end), cut on paragraph boundaries."""
    # Page markers are not text: they are excluded from the length count but
    # NOT removed from the document, so offsets stay true to the file.
    grezzi, pos = [], 0
    for par in re.split(r'\n\s*\n', corpo):
        lung = len(par) + 2
        pulito = PAGE_RE.sub('', par).strip()
        if pulito:
            grezzi.append((pos, pos + len(par), len(pulito)))
        pos += lung

    fuse, cur = [], None
    for a, b, utile in grezzi:
        if utile > TARGET * 1.6:
            if cur:
                fuse.append(cur); cur = None
            fuse.extend(spezza_lungo(corpo[a:b], a))
            continue
        if cur is None:
            cur = (a, b)
        elif (b - cur[0]) <= TARGET:
            cur = (cur[0], b)
        else:
            fuse.append(cur); cur = (a, b)
    if cur:
        fuse.append(cur)

    # Merge leftovers: a two-line chunk has too little content to be
    # meaningfully compared with a query.
    out = []
    for a, b in fuse:
        if out and (b - a) < MIN_CHUNK:
            out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return out


def main(argv):
    solo = argv[1] if len(argv) > 1 else None
    OUT.parent.mkdir(parents=True, exist_ok=True)
    n_doc = n_frag = 0
    with OUT.open('w', encoding='utf-8') as f:
        for md in sorted(MD.rglob('*.md')):
            if solo and md.parent.name != solo:
                continue
            meta, corpo, base = leggi(md)
            marks = pagine(corpo)
            conf = frammenti(corpo)
            for i, (a, b) in enumerate(conf):
                testo = PAGE_RE.sub(' ', corpo[max(0, a - OVERLAP):b])
                testo = re.sub(r'[ \t]+', ' ', testo).strip()
                if len(testo) < MIN_CHUNK // 2:
                    continue
                f.write(json.dumps({
                    'id': f"{meta.get('document_id', md.stem)}#{i}",
                    'document_id': meta.get('document_id', ''),
                    'case_id': meta.get('case_id', ''),
                    'case_name': meta.get('case_name', ''),
                    'tipo_atto': meta.get('tipo_atto', ''),
                    'giurisdizioni': meta.get('giurisdizioni', ''),
                    'data': meta.get('data_deposito', ''),
                    # Start and end page: a chunk can cross a page break,
                    # and recording only one page would send the checker
                    # to the wrong page exactly where a citation is split.
                    'pagina': pagina_di(marks, a),
                    'pagina_fine': pagina_di(marks, b),
                    # File offsets (not body offsets), used to reopen the
                    # document and take the wider window.
                    'char_start': base + a,
                    'char_end': base + b,
                    'file': str(md.relative_to(HERE)),
                    'url_documento': meta.get('url_documento', ''),
                    'testo': testo,
                }, ensure_ascii=False) + '\n')
                n_frag += 1
            n_doc += 1
    print(f'documenti : {n_doc}')
    print(f'frammenti : {n_frag}')
    print(f'media     : {n_frag / max(1, n_doc):.1f} frammenti per documento')
    print(f'uscita    : {OUT}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
