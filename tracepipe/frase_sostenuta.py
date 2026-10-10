"""R15: the supported sentence extracted from the text of the filing, without the model (4 October 2026).

Twin of ``tools/frase_sostenuta.py`` (frozen copy ``versioni/R15/frase_sostenuta.py``); the logic is unchanged, so that
the package gives the same sentences as the ones in the TRACE 0.1 data.

WHY. Up to R14 the sentence of the filing that the citation supports (``proposto_frase_sostenuta``) was copied by
DeepSeek in the L05 readings (instructions, QUESTION 3: "the sentence of the text the footnote citing the case is
attached to, or the sentence that contains the citation"). In part of the rows the copied sentence is not found in the
page: the model summarises instead of copying (above all past the 60 words it was asked for), the sentence crosses the
page break, the footnote numbers or the OCR text do not match, the footnote is at the bottom of one page and the body
sentence on another. Here the sentence is derived from the text, deterministically, with the same definition as the
instructions.

HOW.
  1. Is the citation in a FOOTNOTE? The page is read in the PDF (PyMuPDF, ``get_text('dict')``): the markdown text of
     the corpus is the one of ``get_text('text')``, character by character, so every character has its font size and
     baseline. Footnotes are the lines in a smaller size at the bottom of the page; a footnote starts with its number
     (superscript, or at the head of the line). Bottom lines before the first number continue the last footnote of the
     previous page.
  2. The footnote MARK in the body: the superscript number (smaller size and raised baseline, or the PDF superscript
     flag) equal to the footnote number, on the footnote page or up to 2 pages before the citation. If the PDF does not
     mark it as superscript, the number stuck to a word or to a punctuation mark ("sollen.315"). Several equal marks on
     the same page: the order with marks N-1 and N+1 decides; if in doubt, "ambiguo".
  3. The SENTENCE: the one containing the mark (footnote) or the name found (``char_start``, body), on the body text of
     the nearby pages without footnotes, page numbers and repeated headers, stitched across the page break and across
     a word split at the line end. Sentences are never cut after abbreviations ("para.", "Rn.", "v.", "art.", "No.",
     months, initials, dotted acronyms), nor before a lowercase letter; paragraph numbers ("12.", "326.") stay out of
     the sentence. No cut at 60 words.
  4. Pages without a match in the PDF (pages redone with OCR, corpus D02, or a different text) are read from the text
     only, and there the sentence never crosses the page.
The result carries the method: "nota→corpo" (footnote to body), "corpo" (body), or "ambiguo" (ambiguous) with the
reason. AMBIGUOUS NEVER GUESSES: no mark found, a repeated mark, a footnote without a number, a sentence reaching the
edge of the text read, a sentence of more than 200 words (uncertain cut) or of fewer than 4 (the viewer does not light
it up) give "ambiguo" and no sentence.

The reasons and methods are Italian strings because they are data: they are written into the rows as they are.

Use::

    from tracepipe import frase_sostenuta as fs
    e = fs.estrai(row['file'], row['char_start'], row.get('file_pdf'), radice=corpus_root)
    e['metodo'], e['frase'], e['pagine'], e['inizio'], e['fine'], e['motivo']

The markdown and PDF files of the filings are not public: they are in the restricted index of TRACE 0.1 (on request).
"""

from __future__ import annotations

import collections
import functools
import itertools
import pathlib
import re
import statistics

from .prova_intera import FreniProvaIntera

_FRENI = FreniProvaIntera()
PAGE_RE = re.compile(r'<!--\s*page\s+(\d+)\s*-->')
VERSIONE = 'R15'

MAX_PAROLE = 200  # above it, the sentence cut has failed (a table, a list): ambiguo
MIN_PAROLE = 4  # below it, the viewer does not light up the sentence (evidenzia.js, PAROLE_MINIME): ambiguo
PAGINE_INDIETRO = 2  # the footnote mark is searched on the footnote page and up to 2 pages before the citation

# abbreviations after which the full stop does not close the sentence (lower case, without the full stop)
ABBREVIAZIONI = set(
    """
para paras par parr pt pts p pp n nn no nos nr nrn rn rz rdnr art arts artt abs ziff lit lett let s ss ff f fn
fns anm v vs vgl cf cfr ibid id op cit loc sez sect sec secs ch chap cl reg regs sch subs subpara al seq sqq sq
eg ie e i etc dr mr mrs ms mme mlle prof hon jj lj cj st ste inc ltd co corp ct cir app supp rep rev doc docs
res ed eds vol vols bd jg aufl hrsg bgbl nj njw dz tz u z a o b c d g h j k l m q r t w x y bzw usw ua zb sog
ggf vgl evtl insb einschl jan feb mar apr jun jul aug sep sept oct nov dec janv fevr avr juil sept oct nov dec
genn febbr magg giu lug ag sett ott nov dic ene abr ago dic fig figs tab cap capp pag pagg cass cost cc cp cpc
cpp trib sent ord dlgs dpr l ln reg dir racc ecr ecli nr nro núm num nº n° no° art° ss sgg segg čl odst písm sp
zn č tzv např resp atd apod srov ust tj ods pkt ust zw tzw np dz poz ust dist mots mot cert pet ex rel assn dept
dep't gov govt comm comm'n envtl env int'l nat'l univ div fed rptr wl mass cal colo conn del fla ga ill ind kan
ky la md mich minn miss mo mont neb nev okla or pa tenn tex va vt wash wis wyo ariz ark haw supr super sup bk
bankr bus cong sess stat pub doc sen h.r ord stj stf ap resp dje rel min des proc ag rec
""".split()  # noqa: SIM905
)

MESI = set(
    """
januar jänner februar märz april mai juni juli august september oktober november dezember january february march
june july october december janvier février mars avril juin juillet août septembre octobre novembre décembre
gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre dicembre enero febrero marzo abril
mayo junio julio agosto septiembre octubre noviembre diciembre januari februari maart mei augustus
""".split()  # noqa: SIM905
)
ORDINALE_DOPO = set('am vom bis seit zum zur ab der die des dem den im ein eine einer eines vor nach'.split())  # noqa: SIM905
_LETTERA = r'[^\W\d_]'
# a lowercase division label that opens a sentence: «ddd) Article», «a) Wissenschaftliche», «i. Urgenda», «k. The»
_ETICHETTA = re.compile(r'(?:[a-z]{1,4}\)|[ivx]{1,5}\)|(?:[a-z]|[ivx]{1,5})\.)\s+[A-ZÀ-Ý]')
_A_CAPO = re.compile(rf'(?<={_LETTERA})[-­‐]\n\s*(?=[^\W\d_A-ZÀ-ÖØ-Þ])')
_CHIUSE = '”"’\'»)]›」』）“'
_APERTE = '“"‘\'«([‹「『（¿¡'
_PUNTI_ELENCO = '•▪◦●■□➢►‣⁃○◆◇❖➤✓·\uf0a7\uf0b7\uf076\uf0d8\uf0fc\uf06e\uf02d'
_CJK = re.compile(r'[぀-ヿ㐀-鿿가-힯豈-﫿]')
_FINE_CJK = '。！？'


# ── THE DOCUMENT: MARKDOWN TEXT, PAGES, LINES ALIGNED TO THE PDF ──────────────────────────────────────────────────


class Riga:
    __slots__ = (
        'a',
        'arredo',
        'b',
        'base',
        'bbox',
        'corpo',
        'grassetto',
        'nota',
        'numero_testa',
        'pagina',
        'richiami',
        'spans',
        'testo',
        'x',
    )

    def __init__(self, a, b, testo, corpo=None, base=None, x=None, richiami=(), numero_testa=None, pagina=0):
        self.a, self.b, self.testo = a, b, testo
        self.corpo, self.base, self.x = corpo, base, x
        self.richiami = list(richiami)  # [(a, b, number)] superscript digits in the line (offsets in the markdown)
        self.numero_testa = numero_testa  # the superscript number (or in a smaller size) at the head of the line
        self.arredo = False  # page number, repeated header, line numbering, empty line
        self.nota = False  # in the footnote area at the bottom of the page
        self.pagina = pagina
        self.bbox = None  # the bounding box of the line in the PDF
        self.spans = []  # [(a, b, x0, x1)] the pieces of the line in the PDF
        self.grassetto = None  # True if the whole line is bold (a heading), with the PDF

    def __repr__(self):
        return f'Riga(p{self.pagina} {self.a}-{self.b} corpo={self.corpo} nota={self.nota} arredo={self.arredo} {self.testo[:40]!r})'  # noqa: E501


class Documento:
    def __init__(self, file_md, file_pdf=None, radice=None):
        # relative paths of the rows (``file``, ``file_pdf``) start from the corpus root (default: the working folder)
        radice = pathlib.Path(radice) if radice else pathlib.Path.cwd()
        self.file_md = str(file_md)
        p = pathlib.Path(file_md)
        self.testo = (p if p.is_absolute() else radice / p).read_text(encoding='utf-8')
        marks = list(PAGE_RE.finditer(self.testo))
        self.pagine = {}  # number -> (start, end) of the page text in the markdown
        for k, m in enumerate(marks):
            fine = marks[k + 1].start() if k + 1 < len(marks) else len(self.testo)
            self.pagine[int(m.group(1))] = (m.end(), fine)
        self.pdf = None
        if file_pdf:
            q = pathlib.Path(file_pdf)
            q = q if q.is_absolute() else radice / q
            if q.exists():
                try:
                    import fitz

                    self.pdf = fitz.open(str(q))
                except Exception:
                    self.pdf = None
        self._righe = {}
        self.allineata = {}
        self.altezza = {}

    def pagina_di(self, off):
        for n, (a, b) in self.pagine.items():
            if a <= off < b or (off == b and b == len(self.testo)):
                return n
        prima = [n for n, (a, b) in self.pagine.items() if a <= off]
        return max(prima) if prima else None

    def righe(self, n):
        if n not in self._righe:
            self._righe[n] = self._leggi(n) if n in self.pagine else []
        return self._righe[n]

    def _leggi(self, n):
        a, b = self.pagine[n]
        seg = self.testo[a:b]
        if self.pdf is not None and 1 <= n <= self.pdf.page_count:
            try:
                righe = self._dal_pdf(n, a, seg)
            except Exception:
                righe = None
            if righe is not None:
                self.allineata[n] = True
                self.altezza[n] = self.pdf[n - 1].rect.height
                return righe
        self.allineata[n] = False
        out, pos = [], a
        for t in seg.split('\n'):
            out.append(Riga(pos, pos + len(t), t, pagina=n))
            pos += len(t) + 1
        return out

    def _dal_pdf(self, n, a, seg):
        import fitz

        pg = self.pdf[n - 1]
        dd = pg.get_text('dict', flags=fitz.TEXTFLAGS_TEXT)
        linee = [ln for bl in dd['blocks'] if bl.get('type') == 0 for ln in bl['lines']]
        rec = ''.join(''.join(s['text'] for s in ln['spans']) + '\n' for ln in linee)
        if not rec.strip():
            return None
        i = seg.find(rec)
        if i < 0:
            i = seg.find(rec.rstrip())
        if i < 0:  # the page text is not the one of the PDF (OCR, D02): text only
            return None
        pos = a + i
        out = []
        for ln in linee:
            spans = ln['spans']
            t = ''.join(s['text'] for s in spans)
            r = Riga(pos, pos + len(t), t, pagina=n)
            # font size and baseline of the line: those of the letters that are not superscript digits
            peso = collections.Counter()
            basi = collections.Counter()
            for s in spans:
                if s['text'].strip():
                    peso[round(s['size'] * 2) / 2] += len(s['text'].strip())
                    basi[round(s['origin'][1], 1)] += len(s['text'].strip())
            if peso:
                # the dominant font size, without the small digits (footnote marks) when there is something else
                grandi = collections.Counter()
                for s in spans:
                    tt = s['text'].strip()
                    if tt and not re.fullmatch(r'[\d,\-–\s*†‡]+', tt):
                        grandi[round(s['size'] * 2) / 2] += len(tt)
                r.corpo = (grandi or peso).most_common(1)[0][0]
                base_dom = max(
                    (s for s in spans if s['text'].strip()),
                    key=lambda s: (round(s['size'] * 2) / 2 == r.corpo, len(s['text'].strip())),
                )
                r.base = base_dom['origin'][1]
                r.x = ln['bbox'][0]
            r.bbox = tuple(ln['bbox'])
            piene_s = [s for s in spans if s['text'].strip()]
            if piene_s:
                r.grassetto = all((s['flags'] & 16) or 'bold' in s['font'].lower() for s in piene_s)
            # the superscript digits: smaller size and higher baseline, or the PDF superscript flag
            p = pos
            primo = True
            for s in spans:
                tt = s['text']
                st = tt.strip()
                if st and r.corpo:
                    piccolo = s['size'] <= r.corpo * 0.85
                    alto = r.base is not None and s['origin'][1] < r.base - 0.12 * r.corpo
                    apice = bool(s['flags'] & 1) or (piccolo and alto)
                    m = re.fullmatch(r'\s*(\d{1,4})\s*([,–\-]\s*\d{1,4}\s*)*', tt)
                    if apice and m and (piccolo or s['flags'] & 1):
                        if primo:
                            r.numero_testa = int(m.group(1))
                        else:
                            for mm in re.finditer(r'\d{1,4}', tt):
                                r.richiami.append((p + mm.start(), p + mm.end(), int(mm.group())))
                if st:
                    primo = False
                r.spans.append((p, p + len(tt), s['bbox'][0], s['bbox'][2]))
                p += len(tt)
            out.append(r)
            pos += len(t) + 1
        # THE FOOTNOTE MARK ON A LINE OF ITS OWN: the PDF sometimes writes the superscript digit as a separate object,
        # which PyMuPDF puts on a line of its own (elsewhere in the text). It is reattached to the body line that
        # carries it (same height, inside the line horizontally), at the point of the piece of text to its left.
        for d in out:
            m = re.fullmatch(r'\s*(\d{1,4})\s*', d.testo)
            if not m or not d.corpo or not d.bbox:
                continue
            for riga_corpo in out:
                if (
                    riga_corpo is d
                    or not riga_corpo.corpo
                    or not riga_corpo.bbox
                    or riga_corpo.corpo * 0.85 < d.corpo
                    or re.fullmatch(r'\s*\d*\s*', riga_corpo.testo)
                ):
                    continue
                if (
                    riga_corpo.base - riga_corpo.corpo <= d.base <= riga_corpo.base - 0.12 * riga_corpo.corpo
                    and riga_corpo.bbox[0] - 2 <= d.bbox[0] <= riga_corpo.bbox[2] + 3
                ):
                    sx = [sp for sp in riga_corpo.spans if sp[2] <= d.bbox[0] + 1] or riga_corpo.spans[:1]
                    a_, b_, x0, x1 = sx[-1]
                    q = b_ if d.bbox[0] >= x1 - 1 else a_ + round((d.bbox[0] - x0) / max(1e-6, x1 - x0) * (b_ - a_))
                    riga_corpo.richiami.append((max(a_, min(b_, q)), max(a_, min(b_, q)), int(m.group(1))))
                    break
        return out


@functools.lru_cache(maxsize=64)
def documento(file_md, file_pdf=None, radice=None):
    return Documento(file_md, file_pdf, radice)


# ── CLASSIFYING THE LINES OF A PAGE: PAGE FURNITURE, FOOTNOTES ───────────────────────────────────────────────────

_ARREDO = re.compile(
    r'^\s*(?:[-–—]?\s*\d{1,4}\s*[-–—]?|[ivxlcdm]{1,6}|(?:page|pagina|pag\.|p\.|seite|página|page)\s*\d+'
    r'(?:\s*(?:of|di|von|de|/)\s*\d+)?|\d+\s*(?:/|of|di|von)\s*\d+)\s*$',
    re.I,
)


def _chiave_testata(t):
    return re.sub(r'\s+', ' ', re.sub(r'\d+', '#', t.lower())).strip()


def _corpo_testo(doc, pagine):
    """the body font size (in points) of the aligned pages: the most frequent, weighted on characters"""
    c = collections.Counter()
    for n in pagine:
        for r in doc.righe(n):
            if r.corpo and r.testo.strip():
                c[r.corpo] += len(r.testo.strip())
    return c.most_common(1)[0][0] if c else None


def classifica(doc, n):
    """marks page furniture and footnotes on the lines of page n (only once); returns the lines"""
    righe = doc.righe(n)
    if n in getattr(doc, '_classificate', set()):
        return righe
    doc.__dict__.setdefault('_classificate', set()).add(n)

    # REPEATED HEADERS AND FOOTERS: the same line (numbers aside) on at least two of the nearby pages, and in the same
    # position: among the first or last three lines, and (with the PDF) at the same height. A footnote that repeats the
    # same short citation page after page («157 BVerfG, Beschluss vom 24. März 2021 ..., Rn. 192.») is not a header: it
    # sits higher or lower depending on the length of the footnotes, and starts with its number.
    def posti(m):
        rr = [r for r in doc.righe(m) if r.testo.strip()]
        col_pdf = doc.allineata.get(m) and all(r.base is not None for r in rr)
        per_y = sorted(rr, key=lambda r: r.base) if col_pdf else rr
        bordo = per_y[:3] + per_y[-3:]
        if col_pdf:  # with the PDF: also all the lines in the top and bottom band (12% of the page)
            h = doc.altezza.get(m) or 842
            bordo += [r for r in rr if r.base < 0.12 * h or r.base > 0.88 * h]
        return {(_chiave_testata(r.testo), round(r.base / 6) if col_pdf else None) for r in bordo}, bool(col_pdf)

    qui, qui_pdf = posti(n)
    altre = collections.Counter()
    for m in [m for m in range(n - 3, n + 4) if m != n and m in doc.pagine]:
        chiavi, _ = posti(m)
        for k in chiavi:
            altre[k] += 1
            if k[1] is not None:  # tolerance of half a step on the height
                altre[(k[0], k[1] + 1)] += 1
                altre[(k[0], k[1] - 1)] += 1
    # THE TEXT WRITTEN TWICE (signed PDFs: every line repeated at the same height): the copy is page furniture
    viste = set()
    for r in righe:
        if r.base is not None and r.testo.strip():
            chiave = (r.testo, round(r.base), round(r.x or 0))
            if chiave in viste:
                r.arredo = True
            viste.add(chiave)
    for r in righe:
        t = r.testo.strip()
        if r.arredo:
            continue
        if not t or _ARREDO.match(t) or (r.corpo is not None and r.corpo < 3):  # empty line, number, invisible text
            r.arredo = True
            continue
        if len(t) >= 120 or re.match(r'^\s*\d{1,4}\s+\S', t) or r.numero_testa is not None:
            continue
        k = (_chiave_testata(t), round(r.base / 6) if (qui_pdf and r.base is not None) else None)
        if k in qui and altre[k] >= 2:
            r.arredo = True
    if not doc.allineata.get(n):
        return righe
    corpo = _corpo_testo(doc, [m for m in range(n - 2, n + 3) if m in doc.pagine])
    # the lines carrying a superscript footnote mark are body text: their font size counts more than the average of the
    # nearby pages, which in briefs with long footnotes is the one of the footnotes (p. 97 of an opinion: body 11,
    # footnotes 10)
    con_richiami = collections.Counter(r.corpo for r in righe if r.richiami and r.corpo and not r.arredo)
    if con_richiami:
        corpo = con_richiami.most_common(1)[0][0]
    if not corpo:
        return righe
    # the footnote number alone on its line, in a smaller size («522» and next to it the text of the footnote): it is
    # not a page number. It goes back to page furniture if it does not end up in the footnote area.
    numeri = [
        r for r in righe if r.arredo and r.corpo and r.corpo <= corpo - 0.5 and re.fullmatch(r'\s*\d{1,4}\s*', r.testo)
    ]
    for r in numeri:
        r.arredo = False
    # the footnote area: the lines in a smaller size at the bottom of the page (by baseline)
    piene = sorted(
        [r for r in righe if not r.arredo and r.corpo and r.base is not None], key=lambda r: (r.base, r.x or 0)
    )
    zona = []
    for r in reversed(piene):
        if r.corpo <= corpo - 0.5:  # smaller size (11 against 12, 9 against 11): sizes rounded to the half point
            zona.append(r)
        else:
            break
    zona.reverse()
    # the footnotes have the size of their first numbered line: above it, the lines in a larger size are still body text
    # (KLS: lines at 11 points between the body at 12 and the footnotes at 9)
    prima_num = next((k for k, r in enumerate(zona) if _inizio_nota(r) is not None), None)
    if prima_num is not None:
        cn = zona[prima_num].corpo
        k = 0
        while k < prima_num and zona[k].corpo > cn + 0.25:
            k += 1
        zona = zona[k:]
    if zona and len(zona) < len(piene):
        for r in zona:
            r.nota = True
    elif not zona or len(zona) == len(piene):
        # FOOTNOTES IN THE BODY TEXT (same size, superscript number at the head of the line): the area starts from the
        # first line with the superscript number whose footnote mark is higher up on the page, if from there downwards
        # the numbers increase (also with the number not in superscript, «36 MTD 13.», if its superscript mark is higher
        # up on the page)
        for k, r in enumerate(piene):
            num = _inizio_nota(r)
            if num is None or k == 0:
                continue
            sopra = {x[2] for q in piene[:k] for x in q.richiami}
            if num not in sopra or r.base < 0.4 * (doc.altezza.get(n) or 842):
                continue
            if any(q.richiami for q in piene[k:]):  # below there are no body footnote marks: it is the footnote area
                continue
            numeri_giu = [_inizio_nota(q) for q in piene[k:] if _inizio_nota(q) is not None]
            if all(a < b for a, b in itertools.pairwise(numeri_giu)):
                # above the first numbered footnote, the lines with the line spacing of the footnotes (not the one of
                # the body, and without a gap) are the continuation of a footnote from the previous page
                passi = [b.base - a.base for a, b in itertools.pairwise(piene[k:]) if b.base - a.base > 0.5]
                passo = statistics.median(passi) if passi else (r.corpo or 10) * 1.25
                inizio = k
                while (
                    inizio > 0
                    and 0.5 < piene[inizio].base - piene[inizio - 1].base <= 1.35 * passo
                    and not piene[inizio - 1].richiami
                ):
                    inizio -= 1
                for q in piene[inizio:]:
                    q.nota = True
                break
    for r in numeri:
        if not r.nota:
            r.arredo = True
    return righe


def _inizio_nota(r):
    """the footnote number if the line starts a footnote (superscript number, or number and space, at its head)"""
    if r.numero_testa is not None:
        return r.numero_testa
    m = re.match(r'^\s*(\d{1,4})(?:[.)]?\s+|\s*$)(?=\S|$)', r.testo)
    # a year at the head of the line («2018 WL 123», «1998, p. 4») is not the number of a footnote
    if not m or (len(m.group(1)) == 4 and 1800 <= int(m.group(1)) <= 2100):
        return None
    return int(m.group(1))


def _note_della_pagina(doc, n):
    """[(line, number or None)] the lines of the footnote area by baseline, with the number of the footnote they
    belong to (None for the lines before the first number: continuation of a footnote from the previous page)"""
    righe = [r for r in classifica(doc, n) if r.nota]
    righe.sort(key=lambda r: (r.base, r.x or 0))
    # a number not in superscript at the head of the line («280 (Sup. Ct. India 2024); ...») is the start of a footnote
    # only if there is a footnote mark with that number in the body (page or two before), when the page has superscript
    # marks
    apici = {x[2] for m in (n, n - 1, n - 2) if m in doc.pagine for x in _richiami_apice(doc, m)}
    out, cur = [], None
    for k, r in enumerate(righe):
        num = _inizio_nota(r)
        if num is not None and r.numero_testa is None and apici and num not in apici:
            num = None
        if num is not None and r.testo.strip() == str(num) and k + 1 < len(righe):
            cur = num  # the number alone, the text in the line next to it
        elif num is not None:
            cur = num
        out.append((r, cur))
    return out


# ── THE FOOTNOTE MARK IN THE BODY ────────────────────────────────────────────────────────────────────────────────


def _richiami_testo(doc, n, num):
    """the footnote marks searched in the text only: the number stuck to a lowercase letter or to closing punctuation"""
    out = []
    pat = re.compile(rf'(?<=[a-zß-ÿ.,;:!?)\]”’"»])({num})(?=[\s.,;:)\]]|$)')
    for r in classifica(doc, n):
        if r.arredo or r.nota:
            continue
        for m in pat.finditer(r.testo):
            prima = r.testo[: m.start()]
            # «5.7.7» and «art. 2.3»: a number after a digit and a full stop is a number, not a footnote mark
            if re.search(r'\d[.,]$', prima):
                continue
            out.append((r.a + m.start(1), r.a + m.end(1), num))
    return out


def _richiami_apice(doc, n, num=None):
    out = []
    for r in classifica(doc, n):
        if r.arredo or r.nota:
            continue
        out += [x for x in r.richiami if num is None or x[2] == num]
    return out


def trova_richiamo(doc, num, pagine):
    """(start, end, page, how) of the footnote mark `num` in the body, or (None, None, None, reason)"""
    for modo in ('apice', 'testo'):
        for n in pagine:
            if n not in doc.pagine:
                continue
            classifica(doc, n)
            if modo == 'apice' and not doc.allineata.get(n):
                continue
            c = _richiami_apice(doc, n, num) if modo == 'apice' else _richiami_testo(doc, n, num)
            if len(c) == 1:
                return c[0][0], c[0][1], n, modo
            if len(c) > 1:
                # the order of the footnote marks: between N-1 and N+1, if those are unique on the page
                f = _richiami_apice if modo == 'apice' else _richiami_testo
                pr = f(doc, n, num - 1) if num > 1 else []
                do = f(doc, n, num + 1)
                lo = pr[0][0] if len(pr) == 1 else -1
                hi = do[0][0] if len(do) == 1 else 10**12
                d = [x for x in c if lo < x[0] < hi]
                if len(d) == 1 and (lo >= 0 or hi < 10**12):
                    return d[0][0], d[0][1], n, modo + ' (ordine)'
                return None, None, None, f'richiamo {num} ripetuto {len(c)} volte a p. {n}'
    return None, None, None, f'richiamo {num} non trovato nel corpo'


# ── THE BODY FLOW AND THE SENTENCE CUT ───────────────────────────────────────────────────────────────────────────


def flusso(doc, pagine, togli=()):
    """(text, offsets) the body of the given pages, line after line (without footnotes and page furniture), with the
    markdown offset of every character; `togli` are intervals (footnote marks) that stay out. Between pages a line
    break, as between lines."""
    chars, offs = [], []
    togli = sorted(togli)
    prec = None
    for n in pagine:
        if n not in doc.pagine:
            continue
        # THE LINE SPACING OF THE PAGE: a larger gap (over 1.22 times) between two lines is a paragraph break or a
        # heading
        corpo_righe = sorted(
            [r for r in classifica(doc, n) if not (r.arredo or r.nota) and r.testo.strip() and r.base is not None],
            key=lambda r: r.base,
        )
        salti = [b.base - a.base for a, b in itertools.pairwise(corpo_righe) if b.base - a.base > 0.5]
        passo = statistics.median(salti) if len(salti) >= 4 else None
        for r in classifica(doc, n):
            # THE CHANGE OF STYLE BETWEEN TWO LINES (bold heading, size different by at least one point): a certain
            # boundary, marked with \x1e (headings without a full stop, «IV.A.2. The IACtHR OC-32/25: Intergenerational
            # Equity ...»)
            if (
                not (r.arredo or r.nota)
                and r.testo.strip()
                and prec is not None
                and r.grassetto is not None
                and prec.grassetto is not None
                and (
                    r.grassetto != prec.grassetto
                    or abs((r.corpo or 0) - (prec.corpo or 0)) >= 1
                    or (passo and prec.pagina == r.pagina and r.base - prec.base > 1.22 * passo)
                )
            ):
                chars.append('\x1e')
                offs.append(r.a)
            if not (r.arredo or r.nota) and r.testo.strip():
                prec = r
            if (
                r.arredo
                and not r.testo.strip()
                and chars
                and chars[-1] == '\n'
                and (len(chars) < 2 or chars[-2] != '\n')
            ):
                chars.append('\n')
                offs.append(r.a)  # the empty line between two paragraphs stays: one more line break
                continue
            if r.arredo or r.nota:
                continue
            for k, ch in enumerate(r.testo):
                o = r.a + k
                if any(a <= o < b for a, b in togli):
                    # the footnote mark between two letters («Inter-American386and»): a space in its place, the words
                    # stay two
                    if (
                        k + 1 < len(r.testo)
                        and r.testo[k + 1].isalpha()
                        and chars
                        and chars[-1].isalpha()
                        and not any(a <= o + 1 < b for a, b in togli)
                    ):
                        chars.append(' ')
                        offs.append(o)
                    continue
                chars.append(' ' if ch in '\u200b\u200c\u200d\ufeff' else ch)
                offs.append(o)  # zero-width spaces
            chars.append('\n')
            offs.append(r.b)
    return ''.join(chars), offs


def _parola_prima(t, i):
    j = i
    while j > 0 and not t[j - 1].isspace():
        j -= 1
    return t[j:i].lstrip(_APERTE)


def _fine_valida(t, i, k):
    """does the full stop (or ! ?) in t[i] close the sentence? k is the index of the first character after the spaces"""
    if k < len(t):
        c = t[k]
        # «... oben. ddd) Article 12 ...», «a) Wissenschaftliche ...»: a lowercase division label opens a sentence
        etichetta = bool(_ETICHETTA.match(t, k))
        if c.islower() and not etichetta:
            return False
        if not etichetta and not (
            c.isupper()
            or c.isdigit()
            or c in _APERTE
            or c in _PUNTI_ELENCO
            or c in '-–—§'
            or _CJK.match(c)
            or not c.isalpha()
        ):
            return False
    if t[i] == '…' and i > 0 and (t[i - 1] in _APERTE or t[i - 1] in '„‚'):  # «„… S ohledem»: the omission at the head
        return False
    if t[i] != '.':
        return True
    if t[max(0, i - 2) : i] == '. ' or t[i + 1 : i + 3] == ' .':  # «. . .» spaced dots
        return False
    w = _parola_prima(t, i)
    nuda = w.rstrip('.').lower()
    if not nuda:
        return True
    # «Rn. 136 f. Vorliegend ...»: f. and ff. after a number close the sentence before a capital letter (outside the
    # parentheses, which do not get here)
    if (
        nuda in ('f', 'ff')
        and re.search(r'\d\s*$', t[max(0, i - len(w) - 6) : i - len(w)])
        and k < len(t)
        and t[k].isupper()
    ):
        return True
    if nuda in ABBREVIAZIONI or nuda.replace('.', '') in ABBREVIAZIONI:
        return False
    if re.fullmatch(r'(?:[^\W\d_]\.)+[^\W\d_]', nuda):  # U.S., e.g., z.B., u.a.
        return False
    if re.fullmatch(r'[^\W\d_]', nuda):  # initials, «v.», «S.»
        return False
    if t[i - 1 : i] == '.':  # «...»
        return False
    # «24. März 2021», «am 1. Senat», «le 1. Mai»: a small number with a full stop before a month, or after an article
    # or a preposition, is an ordinal (German), not the end of the sentence
    if re.fullmatch(r'\d{1,2}', nuda):
        dopo = re.match(r'[^\W\d_]+', t[k : k + 14])
        if dopo and dopo.group().lower() in MESI:
            return False
        prima_parola = re.search(r'([^\W\d_]+)\W*$', t[max(0, i - 30) : i - len(w)])
        if prima_parola and prima_parola.group(1).lower() in ORDINALE_DOPO:
            return False
    # after a number followed by a number («5.7.7», «Rn. 242. 30 ICJ»): not an end if the number follows immediately
    return not (k < len(t) and t[k].isdigit() and re.fullmatch(r'[\d.]+', nuda) and k == i + 1)


def confini(t):
    """the indices where a sentence starts (after the cut) in the flow t"""
    tagli = [0]
    righe = [x for x in t.split('\n') if x.strip()]
    lun = statistics.median([len(x.strip()) for x in righe]) if righe else 0
    i, lun_t = 0, len(t)
    # INSIDE PARENTHESES the sentence does not end («(S. VAN DROOGHENBROECK, "Flandria, ... Urgenda? Entre réparation
    # ...", 2020/36, p. 750)»): a full stop or a ? in a citation in parentheses does not close the sentence. A
    # parenthesis left open for over 400 characters (OCR, «a)» lists) no longer counts.
    prof, aperta = 0, 0
    while i < lun_t:
        ch = t[i]
        if ch in '([':
            if prof == 0:
                aperta = i
            prof += 1
        elif ch in ')]' and prof:
            prof -= 1
        if prof and i - aperta > 400:
            prof = 0
        if ch == '\x1e':
            k = i + 1
            while k < lun_t and t[k].isspace():
                k += 1
            prima = t[:i].rstrip()
            if k < lun_t and (not t[k].islower() or _ETICHETTA.match(t, k)) and not (prima and prima[-1] in ',;(-–'):
                tagli.append(k)
                prof = 0
            i += 1
            continue
        if t[i : i + 3] == '[.]':  # «in other states[.]” The court continued»: a bracketed full stop ends the sentence
            if prof:
                prof -= 1  # the open bracket has already been counted above
            j = i + 3
            while j < lun_t and t[j] in _CHIUSE:
                j += 1
            if j < lun_t and t[j].isdigit():  # the footnote mark stuck on, in text only («states[.]”516 The»)
                while j < lun_t and t[j].isdigit():
                    j += 1
            k = j
            while k < lun_t and t[k].isspace():
                k += 1
            if k < lun_t and (t[k].isupper() or t[k] in _APERTE):
                tagli.append(k)
            i = j
            continue
        if prof and (ch in '.!?…' or ch in _FINE_CJK):
            i += 1
            continue
        if ch in '.!?' or ch in _FINE_CJK or ch == '…':
            j = i + 1
            while j < lun_t and t[j] in _CHIUSE:
                j += 1
            if ch in _FINE_CJK:
                k = j
                while k < lun_t and t[k].isspace():
                    k += 1
                tagli.append(k)
                i = j
                continue
            if j < lun_t and t[j].isdigit() and ch == '.' and i > 0 and (t[i - 1].isalpha() or t[i - 1] in _CHIUSE):
                # the footnote mark stuck to the full stop, in text only («inadecuados.498 Sin embargo»): end after the
                # digits
                j2 = j
                while j2 < lun_t and t[j2].isdigit() and j2 - j < 3:
                    j2 += 1
                k = j2
                while k < lun_t and t[k].isspace():
                    k += 1
                if j2 < lun_t and t[j2].isspace() and k < lun_t and t[k].isupper() and _fine_valida(t, i, k):
                    tagli.append(k)
                i = j2
                continue
            if j < lun_t and not t[j].isspace():
                i += 1
                continue
            k = j
            while k < lun_t and t[k].isspace():
                k += 1
            if _fine_valida(t, i, k):
                tagli.append(k)
            i = j
            continue
        if ch == '\n':
            # the line before: is it short and without linking punctuation (a heading, the end of a paragraph)?
            s = t.rfind('\n', 0, i) + 1
            prec = t[s:i].strip()
            k = i + 1
            vuote = 0
            while k < lun_t and t[k].isspace():
                if t[k] == '\n':
                    vuote += 1
                k += 1
            if k < lun_t:
                nx = t[k]
                if nx in _PUNTI_ELENCO:  # a bullet always starts a sentence
                    k2 = k + 1
                    while k2 < lun_t and t[k2].isspace():
                        k2 += 1
                    tagli.append(k2)
                elif (
                    prec
                    and lun
                    and len(prec) < (0.8 if vuote else 0.55) * lun
                    and not re.search(
                        r'[,;:\-–(\[/&]$|\b(?:and|or|of|the|und|oder|der|die|das|et|ou|de|la|le|e|o|di|del|y)$',
                        prec,
                        re.I,
                    )
                    and (nx.isupper() or nx.isdigit() or nx in _APERTE)
                    and not _CJK.match(nx)
                ) or (prec and prec[-1] in _PUNTI_ELENCO):
                    tagli.append(k)
        i += 1
    tagli.append(lun_t)
    return sorted(set(tagli))


def _togli_etichetta(s):
    """«12. », «326. », «(5) », «• » at the head of the sentence: paragraph numbers, not words of the sentence"""
    while True:
        m = re.match(
            r'^\s*(?:\(?\d{1,4}(?:\.\d{1,3})*[.)]|\([ivxlc]{1,5}\)|\([a-z]\)|(?:[ivx]{1,5}|[a-z]{1,4})[.)](?=\s+[A-ZÀ-Ý])|\[\d{1,4}\]|['
            + _PUNTI_ELENCO
            + r'])\s+',
            s,
        )
        if not m:
            return s, 0
        s2 = s[m.end() :]
        if not s2:
            return s, 0
        return s2, m.end()


def ricuci(s):
    """the word split at the line end stitched back, spaces and line breaks reduced to one space"""
    s = _A_CAPO.sub('', s).replace('\x1e', ' ')
    s = ' '.join(s.split())
    # between two Chinese, Japanese or Korean characters the space is the line break of the page, not a space of the
    # text
    s = re.sub(r'(?<=[\u3000-\u30ff\u3400-\u9fff\uf900-\uffef]) (?=[\u3000-\u30ff\u3400-\u9fff\uf900-\uffef])', '', s)
    return s.lstrip('，、,;；:：)）]」』 ')


def _tutta_fra_parentesi(x):
    x = x.strip().rstrip('.;').rstrip()
    if not (x.startswith('(') and x.endswith(')')):
        return False
    prof = 0
    for k, c in enumerate(x):
        prof += (c == '(') - (c == ')')
        if prof == 0 and k < len(x) - 1:
            return False
    return True


def frase_attorno(doc, pagine, ancora_md, togli=(), testo_solo=False, prima=False, fine_richiamo=None):
    """the sentence of the flow of the `pagine` that contains the offset `ancora_md`. -> dict or (None, reason)"""
    t, offs = flusso(doc, pagine, togli)
    if not offs:
        return None, 'corpo vuoto'
    # the index of the character carrying the anchor (or the first one after it)
    import bisect

    idx = bisect.bisect_left(offs, ancora_md)
    if idx >= len(offs):
        return None, 'ancora fuori dal corpo'
    tolta = prima or offs[idx] != ancora_md
    if tolta:
        idx = max(0, idx - 1)  # the anchor is a footnote mark: the character before, which closes the sentence
        while idx > 0 and t[idx].isspace():
            idx -= 1
    tg = confini(t)
    inizio = max(x for x in tg if x <= idx) if any(x <= idx for x in tg) else 0
    dopo = [x for x in tg if x > idx]
    fine = dopo[0] if dopo else len(t)
    # THE FOOTNOTE MARK AFTER THE COLON («... as follows:525» and below it the block quotation): the sentence carrying
    # the footnote is the one introducing the quotation, and it ends at the colon
    if (
        tolta
        and fine_richiamo is not None
        and t[idx] == ':'
        and not doc.testo[fine_richiamo : doc.testo.find('\n', fine_richiamo)].strip()
    ):
        fine = idx + 1
    # the edge of the text read: the sentence could continue beyond it (except at the start or end of the document)
    prima_pag, ultima_pag = min(doc.pagine), max(doc.pagine)
    lette = [n for n in pagine if n in doc.pagine]
    if (inizio == 0 and lette[0] != prima_pag) or (fine >= len(t.rstrip()) and lette[-1] != ultima_pag):
        return None, 'la frase arriva al bordo delle pagine lette'
    # THE CITATION IN PARENTHESES ON ITS OWN («(BVerfG, Beschluss vom 24. März 2021 ..., Rn. 120).» after a block
    # quotation): it is not a sentence of the filing, it is the reference of the sentence before. That one is taken, if
    # there is one and it touches it.
    if _tutta_fra_parentesi(t[inizio:fine]) and inizio > 0:
        prec = [x for x in tg if x < inizio]
        if prec:
            fine = inizio
            inizio = prec[-1]
            while fine > inizio and t[fine - 1].isspace():
                fine -= 1
    pezzo = t[inizio:fine]
    pezzo_s, tolto = _togli_etichetta(pezzo)
    inizio += tolto + (len(pezzo_s) - len(pezzo_s.lstrip()))
    pezzo = t[inizio:fine].rstrip()
    fine = inizio + len(pezzo)
    frase = ricuci(pezzo)
    if not frase:
        return None, 'frase vuota'
    a, b = offs[inizio], offs[fine - 1] + 1
    pag = sorted({doc.pagina_di(offs[k]) for k in range(inizio, fine) if t[k].strip()})
    if testo_solo and len(pag) > 1:
        return None, 'pagina senza corrispondenza col PDF: la frase scavalca la pagina'
    # text only: a line inside the sentence that starts like a footnote («5 Asseibourg (dec.)») means that body and
    # footnotes got mixed in the OCR text
    if testo_solo and re.search(r'\n\s*(?:\d{1,3}\s+[A-ZÀ-Ý]|[*#%®“"]{1,2}\s*\d{0,3}\s*[A-Z])', t[inizio:fine]):
        return None, 'solo testo: corpo e note mescolati nella frase'
    frase = frase.rstrip(' ' + _PUNTI_ELENCO)
    frase = re.sub(
        r'(?<=[.!?:;”"’»)])\s+(?:[a-z]{1,3}\)|\(\w{1,4}\)|[IVX]{1,5}\.|[A-Z]\.)$', '', frase
    )  # «... 67. bb)»: the heading after
    frase = re.sub(r'([.!?]\]?[”"’»)]*)\d{1,3}$', r'\1', frase)  # the mark stuck to the final full stop (text only)
    parole = len([w for w in frase.split() if re.search(r'[^\W\d_]', w)]) if not _CJK.search(frase) else len(frase) // 2
    if re.search(r'\.{5,}|(?:\. ){4,}|…{3,}', frase):
        return None, 'riga di un indice o di un sommario (puntini di guida)'
    # MEANINGLESS OCR TEXT («= nC) K i10 _ fe) ne) _ OL co Jj so OT»): fewer than half of the words are words
    gettoni = [g for g in frase.split() if not _CJK.search(g)]
    if len(gettoni) >= 6 and len(_CJK.findall(frase)) < 0.2 * len(frase):

        def buona(g):
            n = re.sub(r'[\W\d_]', '', g)
            if len(n) < 2:
                return n.lower() in ('a', 'e', 'o', 'y', 'i', 'à', 'é', 'è', 'u', 'v', 'z', 's', 'k', 'w')
            return (
                bool(re.search(r'[aeiouyàáâãäåèéêëìíîïòóôõöùúûüæœøąęěůýаеиоуыэюяіїєαεηιουω]', n, re.I))
                or len(n) >= 4
                or (n.isupper() and len(n) <= 6)
            )

        buone = sum(1 for g in gettoni if buona(g))
        numeri = sum(1 for g in gettoni if re.fullmatch(r'[\W]*[\d][\d\W]*', g))
        lettere = sum(len(re.sub(r'[\W\d_]', '', g)) for g in gettoni) / len(gettoni)
        if (buone + numeri) / len(gettoni) < 0.6 or lettere < 3.0:
            return None, 'testo OCR senza senso'
    if _CJK.search(frase):
        latine = re.findall(r'[A-Za-z]{1,5}\b', frase)
        if len(latine) >= 8 and sum(w.isupper() for w in latine) / len(latine) > 0.5:
            return None, 'testo OCR illeggibile (lettere latine a caso in una pagina cinese, giapponese o coreana)'
    if parole > MAX_PAROLE:
        return None, f'frase di {parole} parole: taglio incerto'
    if parole < MIN_PAROLE:
        return None, f'frase di {parole} parole'
    return {'frase': frase, 'inizio': a, 'fine': b, 'pagine': pag}, ''


# ── THE EXTRACTION ───────────────────────────────────────────────────────────────────────────────────────────────


def _ambiguo(motivo, **k):
    return {'metodo': 'ambiguo', 'frase': '', 'pagine': [], 'inizio': None, 'fine': None, 'motivo': motivo, **k}


def estrai(file_md, char_start, file_pdf=None, doc=None, radice=None):
    """The supported sentence of the citation that starts at `char_start` in the markdown `file_md`.
    -> {'metodo': 'nota→corpo'|'corpo'|'ambiguo', 'frase', 'pagine', 'inizio', 'fine', 'motivo', 'nota', ...}"""
    try:
        doc = doc or documento(str(file_md), str(file_pdf) if file_pdf else None, str(radice) if radice else None)
    except Exception as e:
        return _ambiguo(f'documento illeggibile: {type(e).__name__}')
    try:
        cs = int(char_start)
    except (TypeError, ValueError):
        return _ambiguo('char_start mancante')
    p = doc.pagina_di(cs)
    if p is None:
        return _ambiguo('posizione fuori dalle pagine')
    righe = classifica(doc, p)
    riga = next((r for r in righe if r.a <= cs <= r.b), None)
    if riga is None:
        return _ambiguo('posizione fuori dalle righe')
    allineata = bool(doc.allineata.get(p))
    base = {'allineata': allineata, 'pagina_citazione': p}
    if riga.arredo:
        return _ambiguo('il nome sta in una testata o in un numero di pagina', **base)

    # 1. THE FOOTNOTE
    num, pagina_nota = None, p
    if allineata and riga.nota:
        note = _note_della_pagina(doc, p)
        num = next((k for r, k in note if r is riga), None)
        if num is None:
            # continuation of a footnote started on the previous page: the last footnote of that page
            if p - 1 in doc.pagine and doc.allineata.get(p - 1) is not False:
                classifica(doc, p - 1)
                prec = _note_della_pagina(doc, p - 1) if doc.allineata.get(p - 1) else []
                numeri = [k for _, k in prec if k is not None]
                if numeri:
                    ultima = [r for r, k in prec if k == numeri[-1]]
                    coda = ultima[-1].testo.rstrip() if ultima else ''
                    # the footnote of the previous page was not finished: no final full stop, or an abbreviation full
                    # stop («Dist.»)
                    finita = (
                        bool(coda) and coda[-1] in '.!?' and _fine_valida(coda + ' X', len(coda) - 1, len(coda) + 1)
                    )
                    if coda and not finita:
                        num, pagina_nota = numeri[-1], p - 1
            if num is None:
                return _ambiguo('nome nelle righe in corpo minore in fondo alla pagina, senza numero di nota', **base)
    elif not allineata:
        # TEXT ONLY (pages redone with OCR, text different from the PDF): no font sizes or heights. A footnote if, going
        # up from the line of the name for up to 15 lines (without passing an empty line after the first), a line starts
        # with a footnote sign: «N text», or the signs the OCR makes of superscript numbers («*2 CEDH», «% UNFCCC», «#8
        # Cass.»), and the line is in the lower part of the page. With the number the footnote mark is searched; without
        # a readable number: ambiguous.
        k = righe.index(riga)
        a_pag, b_pag = doc.pagine[p]
        for j in range(k, max(-1, k - 16), -1):
            r = righe[j]
            if not r.testo.strip():
                if j < k and (r.a - a_pag) / max(1, b_pag - a_pag) < 0.45:
                    break  # in the lower part the OCR footnotes are often separated by empty lines
                continue
            m = re.match(r'^\s*(\d{1,3})\s+(?=[^\d\s])', r.testo)
            segno = re.match(r'^\s*(?:[*#%®“"”\'’^]{1,2}\s*\d{0,3}|\d{1,3}[*#%®])\s*(?=[A-Za-zÀ-ÿ])', r.testo)
            in_basso = (r.a - a_pag) / max(1, b_pag - a_pag) >= 0.45
            if m and in_basso:
                num = int(m.group(1))
                break
            if segno and in_basso:
                return _ambiguo('solo testo: nota con un numero illeggibile (OCR)', **base)
            if j < k and re.search(r'[.!?]["”’»)]*\s*$', r.testo) and not in_basso:
                break
    if num is not None:
        pagine = [n for n in range(pagina_nota, p - PAGINE_INDIETRO - 1, -1) if n in doc.pagine]
        if not allineata:
            pagine = [p]
        off, off_fine, pr, come = trova_richiamo(doc, num, pagine)
        if off is None:
            if not allineata:
                # «N text» at the head of a line without a footnote mark: a numbered paragraph, not a footnote. In text
                # only it cannot be told: ambiguous
                return _ambiguo(f'solo testo: riga che comincia con {num}, {come}', nota=num, **base)
            return _ambiguo(come, nota=num, **base)
        # the footnote marks of the page stay out of the sentence text (not the digits: only the superscript ones)
        togli = [(a, b) for n in (pr - 1, pr, pr + 1) if n in doc.pagine for (a, b, _) in _richiami_apice(doc, n)]
        togli += [(off, off_fine)]
        vic = [pr] if not doc.allineata.get(pr) else [n for n in (pr - 1, pr, pr + 1) if n in doc.pagine]
        f, motivo = frase_attorno(
            doc, vic, off, togli, testo_solo=not doc.allineata.get(pr), prima=True, fine_richiamo=off_fine
        )
        if f is None:
            return _ambiguo(motivo, nota=num, pagina_richiamo=pr, **base)
        return {
            'metodo': 'nota→corpo',
            'motivo': f'nota {num}, richiamo a p. {pr} ({come})',
            'nota': num,
            'pagina_richiamo': pr,
            'richiamo': [off, off_fine],
            **f,
            **base,
        }

    # 2. THE BODY
    if allineata and riga.nota:
        return _ambiguo('nome nella zona delle note', **base)
    togli = [(a, b) for n in (p - 1, p, p + 1) if n in doc.pagine for (a, b, _) in _richiami_apice(doc, n)]
    vic = [n for n in (p - 1, p, p + 1) if n in doc.pagine] if allineata else [p]
    f, motivo = frase_attorno(doc, vic, cs, togli, testo_solo=not allineata)
    if f is None:
        return _ambiguo(motivo, **base)
    return {'metodo': 'corpo', 'motivo': 'frase che contiene il nome', 'nota': None, **f, **base}


# ── R15 IN THE COMPOSITION (tools/carica_ripresa.py --composizione R15) ──────────────────────────────────────────

CAMPI_FRASE = (
    'proposto_frase_sostenuta',
    'proposto_frase_testuale',
    'proposto_frase_esito',
    'proposto_frase_metodo',
    'proposto_frase_motivo',
    'proposto_frase_pagine',
    'proposto_frase_offset',
    'proposto_frase_lettura',
    'proposto_frase_lettura_esito',
    'proposto_frase_lettura_testuale',
)


def testo_delle_pagine(doc, pagine, richiamo=None):
    """THE TEXT OF THE FILING ON WHICH THE SENTENCE IS CHECKED (the brake): the body of the pages it comes from, as the
    extractor reads it, that is without footnotes, headers and page numbers and without the numbers of the superscript
    footnote marks (which are not in the sentence: «States70 to justify» in the page, «States to justify» in the
    sentence), with the words split at the line end stitched back. Without removing the footnote marks the brake gave
    «non trovata» to 334 correct sentences out of 6,396 (dry run of 04/10)."""
    togli = [(a, b) for n in pagine if n in doc.pagine for (a, b, _) in _richiami_apice(doc, n)]
    if richiamo:
        togli.append(tuple(richiamo))
    t, _ = flusso(doc, [n for n in pagine if n in doc.pagine], togli)
    return ricuci(t)


def campi_r15(riga, frase_lettura='', esito_lettura='', testuale_lettura=False, radice=None):
    """The fields of the supported sentence with R15 for a row of corpus_rows (file, char_start, file_pdf are needed).
    - safe extraction (nota→corpo, corpo): the extracted sentence is the proposal; the brake (`freni.verifica`, text of
      the filing rebuilt as in R14) finds it again by construction in the pages it comes from: if it did not, it counts
      as ambiguo;
    - ambiguo: the sentence of the DeepSeek reading stays, with its outcome (found, or «non trovata» as before).
    The sentence of the reading stays in `proposto_frase_lettura` anyway (with its outcome), for the comparison.
    -> (fields, extraction)"""
    try:
        e = estrai(riga.get('file'), riga.get('char_start'), riga.get('file_pdf'), radice=radice)
    except Exception as x:  # never stop the loader for one row: ambiguous, with the reason
        e = _ambiguo(f'errore: {type(x).__name__}')
    out = {
        'proposto_frase_lettura': frase_lettura or '',
        'proposto_frase_lettura_esito': esito_lettura or '',
        'proposto_frase_lettura_testuale': bool(testuale_lettura),
    }
    if e['metodo'] != 'ambiguo':
        doc = documento(
            str(riga.get('file')),
            str(riga.get('file_pdf')) if riga.get('file_pdf') else None,
            str(radice) if radice else None,
        )
        esito = _FRENI.verifica(e['frase'], testo_delle_pagine(doc, e['pagine'], e.get('richiamo')), (), True)
        if esito == 'trovata':
            out.update(
                {
                    'proposto_frase_sostenuta': e['frase'],
                    'proposto_frase_testuale': True,
                    'proposto_frase_esito': 'trovata',
                    'proposto_frase_metodo': e['metodo'],
                    'proposto_frase_motivo': e['motivo'],
                    'proposto_frase_pagine': e['pagine'],
                    'proposto_frase_offset': [e['inizio'], e['fine']],
                }
            )
            return out, e
        e = _ambiguo(
            'frase estratta troppo corta per il freno (meno di 20 caratteri)'
            if esito == 'assente'
            else 'frase estratta non ritrovata dal freno nelle sue pagine',
            **{k: e[k] for k in ('allineata', 'pagina_citazione') if k in e},
        )
    out.update(
        {
            'proposto_frase_sostenuta': frase_lettura or '',
            'proposto_frase_testuale': bool(testuale_lettura),
            'proposto_frase_esito': esito_lettura or '',
            'proposto_frase_metodo': 'ambiguo',
            'proposto_frase_motivo': e['motivo'],
            'proposto_frase_pagine': [],
            'proposto_frase_offset': None,
        }
    )
    return out, e


def _uguali(a, b):
    import json

    return json.dumps(a, sort_keys=True, ensure_ascii=False, default=str) == json.dumps(
        b, sort_keys=True, ensure_ascii=False, default=str
    )


def r15_da_scrivere(riga, campi=None, uguale=None, radice=None):
    """What R15 writes on a row NOT judged. `campi`: the proposal the R14 composition has just computed (None if the
    row has no valid L05 readings); `uguale(riga, campi)`: the comparison of `carica_ripresa.uguale_a_oggi`.
      - if the rest of the R14 proposal is what the row has today: the whole proposal, with the R15 sentence and
        provenienza.composizione = R15;
      - otherwise (missing readings, or the row already carries a different composition, e.g. from another session):
        ONLY the sentence fields and provenienza.frase = R15, the rest as it is.
    The sentence of the reading is the one just computed; without it, the one the row has today (or, if the row already
    has R15, the one kept in proposto_frase_lettura): the pass can be redone without losing the DeepSeek sentence.
    -> (fields to write or None if nothing changes, label, extraction)"""
    if campi is not None:
        fl, el, tl = (
            campi.get('proposto_frase_sostenuta') or '',
            campi.get('proposto_frase_esito') or '',
            campi.get('proposto_frase_testuale'),
        )
    elif 'proposto_frase_lettura' in riga:
        fl, el, tl = (
            riga.get('proposto_frase_lettura') or '',
            riga.get('proposto_frase_lettura_esito') or '',
            riga.get('proposto_frase_lettura_testuale'),
        )
    else:
        fl, el, tl = (
            riga.get('proposto_frase_sostenuta') or '',
            riga.get('proposto_frase_esito') or '',
            riga.get('proposto_frase_testuale'),
        )
    frase, e = campi_r15(riga, fl, el, tl, radice)
    frase['provenienza.frase'] = VERSIONE
    resto = {k: v for k, v in (campi or {}).items() if k not in CAMPI_FRASE}
    if campi is not None and uguale is not None and uguale(riga, resto):
        out, etichetta = {**campi, **frase, 'provenienza.composizione': VERSIONE}, 'proposta R15 (resto uguale a R14)'
    else:
        out, etichetta = (
            frase,
            (
                'solo la frase: senza lettura valida'
                if campi is None
                else "solo la frase: il resto della riga e' diverso da R14"
            ),
        )
    gia = (riga.get('provenienza') or {}).get('frase') == VERSIONE and (
        out.get('provenienza.composizione') in (None, (riga.get('provenienza') or {}).get('composizione'))
    )
    if gia and all(
        _uguali(riga.get(k), v)
        for k, v in out.items()
        if not k.startswith('provenienza.') and k != 'proposto_ripresa_lettore'
    ):
        return None, 'invariata', e
    return out, etichetta, e
