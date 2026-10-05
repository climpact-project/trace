"""LA FRASE SOSTENUTA ESTRATTA DAL TESTO, SENZA IL MODELLO (R15, 04/10/2026, il PI: «correggi tutto»).

   PERCHE'. Fino a R14 la frase dell'atto che la citazione sostiene (`proposto_frase_sostenuta`) la copiava DeepSeek
   nelle letture L05 (istruzioni, DOMANDA 3: «la frase del testo a cui e' agganciata la nota che cita il caso, oppure la
   frase che contiene la citazione»). In una parte delle righe la frase copiata non si ritrova nella pagina: il modello
   riassume invece di copiare (soprattutto oltre le 60 parole che gli si chiedevano), la frase scavalca il salto di
   pagina, i numeri delle note o il testo dell'OCR non coincidono, la nota sta in fondo a una pagina e la frase del corpo
   su un'altra. Qui la frase si ricava dal testo, in modo deterministico, con la stessa definizione delle istruzioni.

   COME.
     1. La citazione e' in una NOTA? Si guarda la pagina nel PDF (PyMuPDF, `get_text('dict')`): il testo del markdown
        del corpus e' quello di `get_text('text')`, carattere per carattere, quindi ogni carattere ha il suo corpo e la
        sua linea di base. Le note sono le righe in corpo minore in fondo alla pagina; una nota comincia con il suo
        numero (in apice, o in testa alla riga). Le righe in fondo che precedono il primo numero sono il seguito
        dell'ultima nota della pagina prima (nota che continua).
     2. Il RICHIAMO della nota nel corpo: il numero in apice (corpo minore e linea di base rialzata, o il segno di
        apice del PDF) uguale al numero della nota, sulla pagina della nota o fino a 2 pagine prima della citazione.
        Se il PDF non lo segna in apice, il numero attaccato a una parola o a una punteggiatura («sollen.315»). Piu'
        richiami uguali sulla stessa pagina: decide l'ordine con i richiami N-1 e N+1; se resta il dubbio, «ambiguo».
     3. La FRASE: quella che contiene il richiamo (nota) o il nome trovato (`char_start`, corpo), sul testo del corpo
        delle pagine vicine senza note, numeri di pagina e testate ripetute, ricucita oltre il salto di pagina e oltre
        la parola spezzata a capo. Il taglio delle frasi non cade dopo le abbreviazioni («para.», «Rn.», «v.», «art.»,
        «No.», mesi, iniziali, sigle puntate), ne' davanti a una minuscola; i numeri dei paragrafi («12.», «326.»)
        restano fuori dalla frase. Nessun taglio a 60 parole.
     4. Le pagine senza corrispondenza col PDF (pagine rifatte con l'OCR, corpus D02, o testo diverso) si leggono dal
        solo testo, e li' la frase non scavalca mai la pagina.
   L'esito porta il metodo: «nota→corpo», «corpo», o «ambiguo» con il motivo. AMBIGUO NON TIRA MAI A INDOVINARE: niente
   richiamo trovato, richiamo doppio, nota senza numero, frase che arriva al bordo del testo letto, frase di oltre 200
   parole (taglio incerto) o di meno di 4 (il visore non la accende) danno «ambiguo» e nessuna frase.

   Uso:
       import frase_sostenuta as FS
       e = FS.estrai(riga['file'], riga['char_start'], riga.get('file_pdf'))
       e['metodo'], e['frase'], e['pagine'], e['inizio'], e['fine'], e['motivo']
   Prova su una riga:  .venv/bin/python tools/frase_sostenuta.py <file markdown> <char_start> [<file pdf>]
"""
from __future__ import annotations

import collections
import functools
import pathlib
import re
import statistics
import sys

QUI = pathlib.Path(__file__).resolve().parent.parent
PAGE_RE = re.compile(r'<!--\s*page\s+(\d+)\s*-->')
VERSIONE = 'R15'

MAX_PAROLE = 200      # oltre, il taglio delle frasi e' fallito (una tabella, un elenco): ambiguo
MIN_PAROLE = 4        # sotto, il visore non accende la frase (evidenzia.js, PAROLE_MINIME): ambiguo
PAGINE_INDIETRO = 2   # il richiamo si cerca sulla pagina della nota e fino a 2 pagine prima della citazione

# abbreviazioni dopo le quali il punto non chiude la frase (minuscole, senza il punto)
ABBREVIAZIONI = set('''
para paras par parr pt pts p pp n nn no nos nr nrn rn rz rdnr art arts artt abs ziff lit lett let s ss ff f fn fns anm
v vs vgl cf cfr ibid id op cit loc sez sect sec secs ch chap cl reg regs sch subs subpara al seq sqq sq eg ie e i etc
dr mr mrs ms mme mlle prof hon jj lj cj st ste inc ltd co corp ct cir app supp rep rev doc docs res ed eds vol vols bd
jg aufl hrsg bgbl nj njw dz tz u z a o b c d g h j k l m q r t w x y bzw usw ua zb sog ggf vgl evtl insb einschl
jan feb mar apr jun jul aug sep sept oct nov dec janv fevr avr juil sept oct nov dec genn febbr magg giu lug ag sett ott
nov dic ene abr ago dic
fig figs tab cap capp pag pagg cass cost cc cp cpc cpp trib sent ord dlgs dpr l ln reg dir racc ecr ecli
nr nro núm num nº n° no° art° ss sgg segg
čl odst písm sp zn č tzv např resp atd apod srov ust tj ods pkt ust zw tzw np dz poz ust
dist mots mot cert pet ex rel assn dept dep't gov govt comm comm'n envtl env int'l nat'l univ div fed rptr wl mass
cal colo conn del fla ga ill ind kan ky la md mich minn miss mo mont neb nev okla or pa tenn tex va vt wash wis wyo ariz
ark haw supr super sup bk bankr bus cong sess stat pub doc sen h.r ord stj stf ap resp dje rel min des proc ag rec
'''.split())

MESI = set('''januar jänner februar märz april mai juni juli august september oktober november dezember january february
march june july october december janvier février mars avril juin juillet août septembre octobre novembre décembre
gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre dicembre enero febrero marzo abril mayo
junio julio agosto septiembre octubre noviembre diciembre januari februari maart mei augustus'''.split())
ORDINALE_DOPO = set('am vom bis seit zum zur ab der die des dem den im ein eine einer eines vor nach'.split())
_LETTERA = r'[^\W\d_]'
# un'etichetta di partizione in minuscolo che apre una frase: «ddd) Article», «a) Wissenschaftliche», «i. Urgenda», «k. The»
_ETICHETTA = re.compile(r'(?:[a-z]{1,4}\)|[ivx]{1,5}\)|(?:[a-z]|[ivx]{1,5})\.)\s+[A-ZÀ-Ý]')
_A_CAPO = re.compile(rf'(?<={_LETTERA})[-­‐]\n\s*(?=[^\W\d_A-ZÀ-ÖØ-Þ])')
_CHIUSE = '”"’\'»)]›」』）“'
_APERTE = '“"‘\'«([‹「『（¿¡'
_PUNTI_ELENCO = '•▪◦●■□➢►‣⁃○◆◇❖➤✓·\uf0a7\uf0b7\uf076\uf0d8\uf0fc\uf06e\uf02d'
_CJK = re.compile(r'[぀-ヿ㐀-鿿가-힯豈-﫿]')
_FINE_CJK = '。！？'


# ── IL DOCUMENTO: TESTO DEL MARKDOWN, PAGINE, RIGHE ALLINEATE AL PDF ──────────────────────────────────────────────

class Riga:
    __slots__ = ('a', 'b', 'testo', 'corpo', 'base', 'x', 'richiami', 'numero_testa', 'arredo', 'nota', 'pagina', 'bbox', 'spans', 'grassetto')

    def __init__(self, a, b, testo, corpo=None, base=None, x=None, richiami=(), numero_testa=None, pagina=0):
        self.a, self.b, self.testo = a, b, testo
        self.corpo, self.base, self.x = corpo, base, x
        self.richiami = list(richiami)       # [(a, b, numero)] cifre in apice nella riga (offset nel markdown)
        self.numero_testa = numero_testa     # il numero in apice (o in corpo minore) in testa alla riga
        self.arredo = False                  # numero di pagina, testata ripetuta, numerazione delle righe, riga vuota
        self.nota = False                    # nella zona delle note in fondo alla pagina
        self.pagina = pagina
        self.bbox = None                     # il riquadro della riga nel PDF
        self.spans = []                      # [(a, b, x0, x1)] i pezzi della riga nel PDF
        self.grassetto = None                # True se tutta la riga e' in grassetto (un titolo), col PDF

    def __repr__(self):
        return f'Riga(p{self.pagina} {self.a}-{self.b} corpo={self.corpo} nota={self.nota} arredo={self.arredo} {self.testo[:40]!r})'


class Documento:
    def __init__(self, file_md, file_pdf=None, radice=QUI):
        self.file_md = str(file_md)
        p = pathlib.Path(file_md)
        self.testo = (p if p.is_absolute() else pathlib.Path(radice)/p).read_text(encoding='utf-8')
        marks = list(PAGE_RE.finditer(self.testo))
        self.pagine = {}                     # numero -> (inizio, fine) del testo della pagina nel markdown
        for k, m in enumerate(marks):
            fine = marks[k+1].start() if k + 1 < len(marks) else len(self.testo)
            self.pagine[int(m.group(1))] = (m.end(), fine)
        self.pdf = None
        if file_pdf:
            q = pathlib.Path(file_pdf)
            q = q if q.is_absolute() else pathlib.Path(radice)/q
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
                self.altezza[n] = self.pdf[n-1].rect.height
                return righe
        self.allineata[n] = False
        out, pos = [], a
        for t in seg.split('\n'):
            out.append(Riga(pos, pos + len(t), t, pagina=n)); pos += len(t) + 1
        return out

    def _dal_pdf(self, n, a, seg):
        import fitz
        pg = self.pdf[n-1]
        dd = pg.get_text('dict', flags=fitz.TEXTFLAGS_TEXT)
        linee = [l for bl in dd['blocks'] if bl.get('type') == 0 for l in bl['lines']]
        rec = ''.join(''.join(s['text'] for s in l['spans']) + '\n' for l in linee)
        if not rec.strip():
            return None
        i = seg.find(rec)
        if i < 0:
            i = seg.find(rec.rstrip())
        if i < 0:                       # il testo della pagina non e' quello del PDF (OCR, D02): solo testo
            return None
        pos = a + i
        out = []
        for l in linee:
            spans = l['spans']
            t = ''.join(s['text'] for s in spans)
            r = Riga(pos, pos + len(t), t, pagina=n)
            # corpo e linea di base della riga: quelli delle lettere che non sono cifre in apice
            peso = collections.Counter(); basi = collections.Counter()
            for s in spans:
                if s['text'].strip():
                    peso[round(s['size'] * 2) / 2] += len(s['text'].strip())
                    basi[round(s['origin'][1], 1)] += len(s['text'].strip())
            if peso:
                # il corpo dominante, senza le cifre piccole (richiami) quando c'e' altro
                grandi = collections.Counter()
                for s in spans:
                    tt = s['text'].strip()
                    if tt and not re.fullmatch(r'[\d,\-–\s*†‡]+', tt):
                        grandi[round(s['size'] * 2) / 2] += len(tt)
                r.corpo = (grandi or peso).most_common(1)[0][0]
                base_dom = max((s for s in spans if s['text'].strip()), key=lambda s: (round(s['size'] * 2) / 2 == r.corpo, len(s['text'].strip())))
                r.base = base_dom['origin'][1]
                r.x = l['bbox'][0]
            r.bbox = tuple(l['bbox'])
            piene_s = [s for s in spans if s['text'].strip()]
            if piene_s:
                r.grassetto = all((s['flags'] & 16) or 'bold' in s['font'].lower() for s in piene_s)
            # le cifre in apice: corpo minore e linea di base piu' alta, oppure il segno di apice del PDF
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
        # IL RICHIAMO SU UNA RIGA SUA: il PDF a volte scrive la cifra in apice come un oggetto a parte, che PyMuPDF
        # mette su una riga propria (altrove nel testo). Si riattacca alla riga del corpo che la porta (stessa altezza,
        # dentro la riga in orizzontale), nel punto del pezzo di testo che le sta a sinistra.
        for d in out:
            m = re.fullmatch(r'\s*(\d{1,4})\s*', d.testo)
            if not m or not d.corpo or not d.bbox:
                continue
            for L in out:
                if L is d or not L.corpo or not L.bbox or L.corpo * 0.85 < d.corpo or re.fullmatch(r'\s*\d*\s*', L.testo):
                    continue
                if L.base - L.corpo <= d.base <= L.base - 0.12 * L.corpo and L.bbox[0] - 2 <= d.bbox[0] <= L.bbox[2] + 3:
                    sx = [sp for sp in L.spans if sp[2] <= d.bbox[0] + 1] or L.spans[:1]
                    a_, b_, x0, x1 = sx[-1]
                    q = b_ if d.bbox[0] >= x1 - 1 else a_ + round((d.bbox[0] - x0) / max(1e-6, x1 - x0) * (b_ - a_))
                    L.richiami.append((max(a_, min(b_, q)), max(a_, min(b_, q)), int(m.group(1))))
                    break
        return out


@functools.lru_cache(maxsize=64)
def documento(file_md, file_pdf=None):
    return Documento(file_md, file_pdf)


# ── CLASSIFICARE LE RIGHE DI UNA PAGINA: ARREDO, NOTE ────────────────────────────────────────────────────────────

_ARREDO = re.compile(r'^\s*(?:[-–—]?\s*\d{1,4}\s*[-–—]?|[ivxlcdm]{1,6}|(?:page|pagina|pag\.|p\.|seite|página|page)\s*\d+'
                     r'(?:\s*(?:of|di|von|de|/)\s*\d+)?|\d+\s*(?:/|of|di|von)\s*\d+)\s*$', re.I)


def _chiave_testata(t):
    return re.sub(r'\s+', ' ', re.sub(r'\d+', '#', t.lower())).strip()


def _corpo_testo(doc, pagine):
    """il corpo del testo (in punti) delle pagine allineate: il piu' frequente pesato sui caratteri"""
    c = collections.Counter()
    for n in pagine:
        for r in doc.righe(n):
            if r.corpo and r.testo.strip():
                c[r.corpo] += len(r.testo.strip())
    return c.most_common(1)[0][0] if c else None


def classifica(doc, n):
    """segna arredo e note sulle righe della pagina n (una volta sola); ritorna le righe"""
    righe = doc.righe(n)
    if n in getattr(doc, '_classificate', set()):
        return righe
    doc.__dict__.setdefault('_classificate', set()).add(n)
    # TESTATE E PIEDI RIPETUTI: la stessa riga (numeri a parte) su almeno due delle pagine vicine, e nella stessa
    # posizione: fra le prime o le ultime tre righe, e (col PDF) alla stessa altezza. Una nota che ripete la stessa
    # citazione breve pagina dopo pagina («157 BVerfG, Beschluss vom 24. März 2021 ..., Rn. 192.») non e' una testata:
    # sta piu' in alto o piu' in basso secondo la lunghezza delle note, e comincia con il suo numero.
    def posti(m):
        rr = [r for r in doc.righe(m) if r.testo.strip()]
        col_pdf = doc.allineata.get(m) and all(r.base is not None for r in rr)
        per_y = sorted(rr, key=lambda r: r.base) if col_pdf else rr
        bordo = per_y[:3] + per_y[-3:]
        if col_pdf:                     # col PDF: anche tutte le righe nella fascia alta e bassa (12% della pagina)
            h = doc.altezza.get(m) or 842
            bordo += [r for r in rr if r.base < 0.12 * h or r.base > 0.88 * h]
        return {(_chiave_testata(r.testo), round(r.base / 6) if col_pdf else None) for r in bordo}, bool(col_pdf)
    qui, qui_pdf = posti(n)
    altre = collections.Counter()
    for m in [m for m in range(n - 3, n + 4) if m != n and m in doc.pagine]:
        chiavi, _ = posti(m)
        for k in chiavi:
            altre[k] += 1
            if k[1] is not None:            # tolleranza di mezzo passo sull'altezza
                altre[(k[0], k[1] + 1)] += 1; altre[(k[0], k[1] - 1)] += 1
    # IL TESTO SCRITTO DUE VOLTE (PDF firmati: ogni riga ripetuta alla stessa altezza): la copia e' arredo
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
        if not t or _ARREDO.match(t) or (r.corpo is not None and r.corpo < 3):   # riga vuota, numero, testo invisibile
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
    # le righe che portano un richiamo in apice sono corpo del testo: il loro corpo vale piu' della media delle pagine
    # vicine, che nelle memorie con note lunghe e' quello delle note (p. 97 di un parere: corpo 11, note 10)
    con_richiami = collections.Counter(r.corpo for r in righe if r.richiami and r.corpo and not r.arredo)
    if con_richiami:
        corpo = con_richiami.most_common(1)[0][0]
    if not corpo:
        return righe
    # il numero della nota da solo sulla sua riga, in corpo minore («522» e accanto il testo della nota): non e' un numero
    # di pagina. Torna arredo se non finisce nella zona delle note.
    numeri = [r for r in righe if r.arredo and r.corpo and r.corpo <= corpo - 0.5 and re.fullmatch(r'\s*\d{1,4}\s*', r.testo)]
    for r in numeri:
        r.arredo = False
    # la zona delle note: le righe in corpo minore in fondo alla pagina (per linea di base)
    piene = sorted([r for r in righe if not r.arredo and r.corpo and r.base is not None], key=lambda r: (r.base, r.x or 0))
    zona = []
    for r in reversed(piene):
        if r.corpo <= corpo - 0.5:      # corpo minore (11 contro 12, 9 contro 11): misure arrotondate al mezzo punto
            zona.append(r)
        else:
            break
    zona.reverse()
    # le note hanno il corpo della loro prima riga numerata: sopra di essa, le righe in un corpo piu' grande sono ancora
    # corpo del testo (KLS: righe a 11 punti fra il corpo a 12 e le note a 9)
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
        # NOTE NEL CORPO DEL TESTO (stesso corpo, numero in apice in testa alla riga): la zona comincia dalla prima riga
        # con il numero in apice il cui richiamo sta piu' su nella pagina, se da li' in giu' i numeri crescono
        # (anche col numero non in apice, «36 MTD 13.», se il suo richiamo in apice sta piu' su nella pagina)
        for k, r in enumerate(piene):
            num = _inizio_nota(r)
            if num is None or k == 0:
                continue
            sopra = {x[2] for q in piene[:k] for x in q.richiami}
            if num not in sopra or r.base < 0.4 * (doc.altezza.get(n) or 842):
                continue
            if any(q.richiami for q in piene[k:]):     # sotto non ci sono richiami del corpo: e' la zona delle note
                continue
            numeri_giu = [_inizio_nota(q) for q in piene[k:] if _inizio_nota(q) is not None]
            if all(a < b for a, b in zip(numeri_giu, numeri_giu[1:])):
                # sopra la prima nota numerata, le righe con l'interlinea delle note (non quella del corpo, e senza un
                # salto) sono il seguito di una nota della pagina prima
                passi = [b.base - a.base for a, b in zip(piene[k:], piene[k+1:]) if b.base - a.base > 0.5]
                passo = statistics.median(passi) if passi else (r.corpo or 10) * 1.25
                inizio = k
                while inizio > 0 and 0.5 < piene[inizio].base - piene[inizio-1].base <= 1.35 * passo \
                        and not piene[inizio-1].richiami:
                    inizio -= 1
                for q in piene[inizio:]:
                    q.nota = True
                break
    for r in numeri:
        if not r.nota:
            r.arredo = True
    return righe


def _inizio_nota(r):
    """il numero della nota se la riga comincia una nota (numero in apice in testa, o numero e spazio in testa)"""
    if r.numero_testa is not None:
        return r.numero_testa
    m = re.match(r'^\s*(\d{1,4})(?:[.)]?\s+|\s*$)(?=\S|$)', r.testo)
    # un anno in testa alla riga («2018 WL 123», «1998, p. 4») non e' il numero di una nota
    if not m or (len(m.group(1)) == 4 and 1800 <= int(m.group(1)) <= 2100):
        return None
    return int(m.group(1))


def _note_della_pagina(doc, n):
    """[(riga, numero o None)] le righe della zona note per linea di base, col numero della nota a cui appartengono
    (None per le righe prima del primo numero: seguito di una nota della pagina prima)"""
    righe = [r for r in classifica(doc, n) if r.nota]
    righe.sort(key=lambda r: (r.base, r.x or 0))
    # un numero non in apice in testa alla riga («280 (Sup. Ct. India 2024); ...») e' l'inizio di una nota solo se c'e'
    # un richiamo con quel numero nel corpo (pagina o due prima), quando la pagina ha richiami in apice
    apici = {x[2] for m in (n, n - 1, n - 2) if m in doc.pagine for x in _richiami_apice(doc, m)}
    out, cur = [], None
    for k, r in enumerate(righe):
        num = _inizio_nota(r)
        if num is not None and r.numero_testa is None and apici and num not in apici:
            num = None
        if num is not None and r.testo.strip() == str(num) and k + 1 < len(righe):
            cur = num                           # il numero da solo, il testo nella riga accanto
        elif num is not None:
            cur = num
        out.append((r, cur))
    return out


# ── IL RICHIAMO DELLA NOTA NEL CORPO ─────────────────────────────────────────────────────────────────────────────

def _richiami_testo(doc, n, num):
    """i richiami cercati nel solo testo: il numero attaccato a una minuscola o a una punteggiatura di chiusura"""
    out = []
    pat = re.compile(rf'(?<=[a-zß-ÿ.,;:!?)\]”’"»])({num})(?=[\s.,;:)\]]|$)')
    for r in classifica(doc, n):
        if r.arredo or r.nota:
            continue
        for m in pat.finditer(r.testo):
            prima = r.testo[:m.start()]
            # «5.7.7» e «art. 2.3»: un numero dopo cifra e punto e' un numero, non un richiamo
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
    """(inizio, fine, pagina, come) del richiamo `num` nel corpo, oppure (None, None, None, motivo)"""
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
                # l'ordine dei richiami: fra N-1 e N+1, se quelli sono unici sulla pagina
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


# ── IL FLUSSO DEL CORPO E IL TAGLIO DELLE FRASI ──────────────────────────────────────────────────────────────────

def flusso(doc, pagine, togli=()):
    """(testo, offset) il corpo delle pagine date, righe dopo righe (senza note e arredo), con gli offset nel markdown di
    ogni carattere; `togli` sono intervalli (richiami) che restano fuori. Fra le pagine un a capo, come fra le righe."""
    chars, offs = [], []
    togli = sorted(togli)
    prec = None
    for n in pagine:
        if n not in doc.pagine:
            continue
        # L'INTERLINEA DELLA PAGINA: uno spazio piu' alto (oltre 1,22 volte) fra due righe e' un capoverso o un titolo
        corpo_righe = sorted([r for r in classifica(doc, n) if not (r.arredo or r.nota) and r.testo.strip() and r.base is not None],
                             key=lambda r: r.base)
        salti = [b.base - a.base for a, b in zip(corpo_righe, corpo_righe[1:]) if b.base - a.base > 0.5]
        passo = statistics.median(salti) if len(salti) >= 4 else None
        for r in classifica(doc, n):
            # IL CAMBIO DI STILE FRA DUE RIGHE (titolo in grassetto, corpo diverso di almeno un punto): un confine certo,
            # segnato con \x1e (i titoli senza punto, «IV.A.2. The IACtHR OC-32/25: Intergenerational Equity ...»)
            if not (r.arredo or r.nota) and r.testo.strip() and prec is not None and r.grassetto is not None \
                    and prec.grassetto is not None and (r.grassetto != prec.grassetto or abs((r.corpo or 0) - (prec.corpo or 0)) >= 1
                                                        or (passo and prec.pagina == r.pagina and r.base - prec.base > 1.22 * passo)):
                chars.append('\x1e'); offs.append(r.a)
            if not (r.arredo or r.nota) and r.testo.strip():
                prec = r
            if r.arredo and not r.testo.strip() and chars and chars[-1] == '\n' and (len(chars) < 2 or chars[-2] != '\n'):
                chars.append('\n'); offs.append(r.a)       # la riga vuota fra due paragrafi resta: un a capo in piu'
                continue
            if r.arredo or r.nota:
                continue
            for k, ch in enumerate(r.testo):
                o = r.a + k
                if any(a <= o < b for a, b in togli):
                    # il richiamo fra due lettere («Inter-American386and»): al suo posto uno spazio, le parole restano due
                    if k + 1 < len(r.testo) and r.testo[k+1].isalpha() and chars and chars[-1].isalpha() \
                            and not any(a <= o + 1 < b for a, b in togli):
                        chars.append(' '); offs.append(o)
                    continue
                chars.append(' ' if ch in '\u200b\u200c\u200d\ufeff' else ch); offs.append(o)   # spazi di larghezza zero
            chars.append('\n'); offs.append(r.b)
    return ''.join(chars), offs


def _parola_prima(t, i):
    j = i
    while j > 0 and not t[j-1].isspace():
        j -= 1
    return t[j:i].lstrip(_APERTE)


def _fine_valida(t, i, k):
    """il punto (o ! ?) in t[i] chiude la frase? k e' l'indice del primo carattere dopo gli spazi"""
    if k < len(t):
        c = t[k]
        # «... oben. ddd) Article 12 ...», «a) Wissenschaftliche ...»: un'etichetta di partizione in minuscolo apre una frase
        etichetta = bool(_ETICHETTA.match(t, k))
        if c.islower() and not etichetta:
            return False
        if not etichetta and not (c.isupper() or c.isdigit() or c in _APERTE or c in _PUNTI_ELENCO or c in '-–—§' or _CJK.match(c)
                or not c.isalpha()):
            return False
    if t[i] == '…' and i > 0 and (t[i-1] in _APERTE or t[i-1] in '„‚'):   # «„… S ohledem»: l'omissione in testa
        return False
    if t[i] != '.':
        return True
    if t[max(0, i-2):i] == '. ' or t[i+1:i+3] == ' .':          # «. . .» puntini spaziati
        return False
    w = _parola_prima(t, i)
    nuda = w.rstrip('.').lower()
    if not nuda:
        return True
    # «Rn. 136 f. Vorliegend ...»: f. e ff. dopo un numero chiudono la frase davanti a una maiuscola (fuori dalle
    # parentesi, che non arrivano qui)
    if nuda in ('f', 'ff') and re.search(r'\d\s*$', t[max(0, i - len(w) - 6):i - len(w)]) and k < len(t) and t[k].isupper():
        return True
    if nuda in ABBREVIAZIONI or nuda.replace('.', '') in ABBREVIAZIONI:
        return False
    if re.fullmatch(r'(?:[^\W\d_]\.)+[^\W\d_]', nuda):         # U.S., e.g., z.B., u.a.
        return False
    if re.fullmatch(r'[^\W\d_]', nuda):                        # iniziali, «v.», «S.»
        return False
    if t[i-1:i] == '.':                                         # «...»
        return False
    # «24. März 2021», «am 1. Senat», «le 1. Mai»: un numero piccolo col punto davanti a un mese, o dopo un articolo o una
    # preposizione, e' un ordinale (tedesco), non la fine della frase
    if re.fullmatch(r'\d{1,2}', nuda):
        dopo = re.match(r'[^\W\d_]+', t[k:k+14])
        if dopo and dopo.group().lower() in MESI:
            return False
        prima_parola = re.search(r'([^\W\d_]+)\W*$', t[max(0, i - 30):i - len(w)])
        if prima_parola and prima_parola.group(1).lower() in ORDINALE_DOPO:
            return False
    # dopo un numero seguito da un numero («5.7.7», «Rn. 242. 30 ICJ»): non e' una fine se il numero segue subito
    if k < len(t) and t[k].isdigit() and re.fullmatch(r'[\d.]+', nuda) and k == i + 1:
        return False
    return True


def confini(t):
    """gli indici dove comincia una frase (dopo il taglio) nel flusso t"""
    tagli = [0]
    righe = [l for l in t.split('\n') if l.strip()]
    lun = statistics.median([len(l.strip()) for l in righe]) if righe else 0
    i, L = 0, len(t)
    # DENTRO LE PARENTESI la frase non finisce («(S. VAN DROOGHENBROECK, "Flandria, ... Urgenda? Entre réparation ...",
    # 2020/36, p. 750)»): un punto o un ? in una citazione fra parentesi non chiude la frase. Una parentesi rimasta aperta
    # per oltre 400 caratteri (OCR, elenchi «a)») non conta piu'.
    prof, aperta = 0, 0
    while i < L:
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
            while k < L and t[k].isspace():
                k += 1
            prima = t[:i].rstrip()
            if k < L and (not t[k].islower() or _ETICHETTA.match(t, k)) \
                    and not (prima and prima[-1] in ',;(-–'):
                tagli.append(k); prof = 0
            i += 1; continue
        if t[i:i+3] == '[.]':           # «in other states[.]” The court continued»: il punto fra quadre chiude la frase
            if prof:
                prof -= 1               # la quadra aperta e' gia' stata contata qui sopra
            j = i + 3
            while j < L and t[j] in _CHIUSE:
                j += 1
            if j < L and t[j].isdigit():           # il richiamo attaccato nel solo testo («states[.]”516 The»)
                while j < L and t[j].isdigit():
                    j += 1
            k = j
            while k < L and t[k].isspace():
                k += 1
            if k < L and (t[k].isupper() or t[k] in _APERTE):
                tagli.append(k)
            i = j; continue
        if prof and (ch in '.!?…' or ch in _FINE_CJK):
            i += 1; continue
        if ch in '.!?' or ch in _FINE_CJK or ch == '…':
            j = i + 1
            while j < L and t[j] in _CHIUSE:
                j += 1
            if ch in _FINE_CJK:
                k = j
                while k < L and t[k].isspace():
                    k += 1
                tagli.append(k); i = j; continue
            if j < L and t[j].isdigit() and ch == '.' and i > 0 and (t[i-1].isalpha() or t[i-1] in _CHIUSE):
                # il richiamo attaccato al punto nel solo testo («inadecuados.498 Sin embargo»): fine dopo le cifre
                j2 = j
                while j2 < L and t[j2].isdigit() and j2 - j < 3:
                    j2 += 1
                k = j2
                while k < L and t[k].isspace():
                    k += 1
                if j2 < L and t[j2].isspace() and k < L and t[k].isupper() and _fine_valida(t, i, k):
                    tagli.append(k)
                i = j2; continue
            if j < L and not t[j].isspace():
                i += 1; continue
            k = j
            while k < L and t[k].isspace():
                k += 1
            if _fine_valida(t, i, k):
                tagli.append(k)
            i = j; continue
        if ch == '\n':
            # la riga prima: e' corta e senza punteggiatura che lega (un titolo, la fine di un paragrafo)?
            s = t.rfind('\n', 0, i) + 1
            prec = t[s:i].strip()
            k = i + 1
            vuote = 0
            while k < L and t[k].isspace():
                if t[k] == '\n':
                    vuote += 1
                k += 1
            if k < L:
                nx = t[k]
                if nx in _PUNTI_ELENCO:                           # un punto d'elenco comincia sempre una frase
                    k2 = k + 1
                    while k2 < L and t[k2].isspace():
                        k2 += 1
                    tagli.append(k2)
                elif prec and lun and len(prec) < (0.8 if vuote else 0.55) * lun and not re.search(r'[,;:\-–(\[/&]$|\b(?:and|or|of|the|und|oder|der|die|das|et|ou|de|la|le|e|o|di|del|y)$', prec, re.I) \
                        and (nx.isupper() or nx.isdigit() or nx in _APERTE) and not _CJK.match(nx):
                    tagli.append(k)
                elif prec and prec[-1] in _PUNTI_ELENCO:
                    tagli.append(k)
        i += 1
    tagli.append(L)
    return sorted(set(tagli))


def _togli_etichetta(s):
    """«12. », «326. », «(5) », «• » in testa alla frase: numeri di paragrafo, non parole della frase"""
    while True:
        m = re.match(r'^\s*(?:\(?\d{1,4}(?:\.\d{1,3})*[.)]|\([ivxlc]{1,5}\)|\([a-z]\)|(?:[ivx]{1,5}|[a-z]{1,4})[.)](?=\s+[A-ZÀ-Ý])|\[\d{1,4}\]|['
                     + _PUNTI_ELENCO + r'])\s+', s)
        if not m:
            return s, 0
        s2 = s[m.end():]
        if not s2:
            return s, 0
        return s2, m.end()


def ricuci(s):
    """la parola spezzata a capo ricucita, gli spazi e gli a capo ridotti a uno spazio"""
    s = _A_CAPO.sub('', s).replace('\x1e', ' ')
    s = ' '.join(s.split())
    # fra due caratteri cinesi, giapponesi o coreani lo spazio e' l'a capo della pagina, non uno spazio del testo
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
    """la frase del flusso delle `pagine` che contiene l'offset `ancora_md`. -> dict o (None, motivo)"""
    t, offs = flusso(doc, pagine, togli)
    if not offs:
        return None, 'corpo vuoto'
    # l'indice del carattere che porta l'ancora (o il primo dopo)
    import bisect
    idx = bisect.bisect_left(offs, ancora_md)
    if idx >= len(offs):
        return None, 'ancora fuori dal corpo'
    tolta = prima or offs[idx] != ancora_md
    if tolta:
        idx = max(0, idx - 1)        # l'ancora e' un richiamo: il carattere prima, che chiude la frase
        while idx > 0 and t[idx].isspace():
            idx -= 1
    tg = confini(t)
    inizio = max(x for x in tg if x <= idx) if any(x <= idx for x in tg) else 0
    dopo = [x for x in tg if x > idx]
    fine = dopo[0] if dopo else len(t)
    # IL RICHIAMO DOPO I DUE PUNTI («... as follows:525» e sotto la citazione in blocco): la frase che porta la nota e'
    # quella che introduce la citazione, e finisce ai due punti
    if tolta and fine_richiamo is not None and t[idx] == ':' and not doc.testo[fine_richiamo:doc.testo.find('\n', fine_richiamo)].strip():
        fine = idx + 1
    # il bordo del testo letto: la frase potrebbe continuare oltre (salvo inizio o fine del documento)
    prima_pag, ultima_pag = min(doc.pagine), max(doc.pagine)
    lette = [n for n in pagine if n in doc.pagine]
    if (inizio == 0 and lette[0] != prima_pag) or (fine >= len(t.rstrip()) and lette[-1] != ultima_pag):
        return None, 'la frase arriva al bordo delle pagine lette'
    # LA CITAZIONE FRA PARENTESI DA SOLA («(BVerfG, Beschluss vom 24. März 2021 ..., Rn. 120).» dopo una citazione in
    # blocco): non e' una frase dell'atto, e' il riferimento della frase prima. Si prende quella, se c'e' e la tocca.
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
    # solo testo: una riga dentro la frase che comincia come una nota («5 Asseibourg (dec.)») vuol dire che corpo e note
    # si sono mescolati nel testo dell'OCR
    if testo_solo and re.search(r'\n\s*(?:\d{1,3}\s+[A-ZÀ-Ý]|[*#%®“"]{1,2}\s*\d{0,3}\s*[A-Z])', t[inizio:fine]):
        return None, 'solo testo: corpo e note mescolati nella frase'
    frase = frase.rstrip(' ' + _PUNTI_ELENCO)
    frase = re.sub(r'(?<=[.!?:;”"’»)])\s+(?:[a-z]{1,3}\)|\(\w{1,4}\)|[IVX]{1,5}\.|[A-Z]\.)$', '', frase)  # «... 67. bb)»: il titolo dopo
    frase = re.sub(r'([.!?]\]?[”"’»)]*)\d{1,3}$', r'\1', frase)    # il richiamo attaccato al punto finale (solo testo)
    parole = len([w for w in frase.split() if re.search(r'[^\W\d_]', w)]) if not _CJK.search(frase) else len(frase) // 2
    if re.search(r'\.{5,}|(?:\. ){4,}|…{3,}', frase):
        return None, 'riga di un indice o di un sommario (puntini di guida)'
    # TESTO DELL'OCR SENZA SENSO («= nC) K i10 _ fe) ne) _ OL co Jj so OT»): meno della meta' delle parole sono parole
    gettoni = [g for g in frase.split() if not _CJK.search(g)]
    if len(gettoni) >= 6 and len(_CJK.findall(frase)) < 0.2 * len(frase):
        def buona(g):
            n = re.sub(r'[\W\d_]', '', g)
            if len(n) < 2:
                return n.lower() in ('a', 'e', 'o', 'y', 'i', 'à', 'é', 'è', 'u', 'v', 'z', 's', 'k', 'w')
            return bool(re.search(r'[aeiouyàáâãäåèéêëìíîïòóôõöùúûüæœøąęěůýаеиоуыэюяіїєαεηιουω]', n, re.I)) or len(n) >= 4 \
                or (n.isupper() and len(n) <= 6)
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


# ── L'ESTRAZIONE ─────────────────────────────────────────────────────────────────────────────────────────────────

def _ambiguo(motivo, **k):
    return {'metodo': 'ambiguo', 'frase': '', 'pagine': [], 'inizio': None, 'fine': None, 'motivo': motivo, **k}


def estrai(file_md, char_start, file_pdf=None, doc=None):
    """La frase sostenuta della citazione che comincia a `char_start` nel markdown `file_md`.
    -> {'metodo': 'nota→corpo'|'corpo'|'ambiguo', 'frase', 'pagine', 'inizio', 'fine', 'motivo', 'nota', ...}"""
    try:
        doc = doc or documento(str(file_md), str(file_pdf) if file_pdf else None)
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

    # 1. LA NOTA
    num, pagina_nota = None, p
    if allineata and riga.nota:
        note = _note_della_pagina(doc, p)
        num = next((k for r, k in note if r is riga), None)
        if num is None:
            # seguito di una nota cominciata nella pagina prima: l'ultima nota di quella pagina
            if p - 1 in doc.pagine and doc.allineata.get(p - 1) is not False:
                classifica(doc, p - 1)
                prec = _note_della_pagina(doc, p - 1) if doc.allineata.get(p - 1) else []
                numeri = [k for _, k in prec if k is not None]
                if numeri:
                    ultima = [r for r, k in prec if k == numeri[-1]]
                    coda = ultima[-1].testo.rstrip() if ultima else ''
                    # la nota della pagina prima non era finita: niente punto finale, o un punto d'abbreviazione («Dist.»)
                    finita = bool(coda) and coda[-1] in '.!?' and _fine_valida(coda + ' X', len(coda) - 1, len(coda) + 1)
                    if coda and not finita:
                        num, pagina_nota = numeri[-1], p - 1
            if num is None:
                return _ambiguo('nome nelle righe in corpo minore in fondo alla pagina, senza numero di nota', **base)
    elif not allineata:
        # SOLO TESTO (pagine rifatte con l'OCR, testo diverso dal PDF): niente corpi ne' altezze. Una nota se, risalendo
        # dalla riga del nome fino a 15 righe (senza passare una riga vuota dopo la prima), una riga comincia con un
        # segno da nota: «N testo», o i segni che l'OCR fa dei numeri in apice («*2 CEDH», «% UNFCCC», «#8 Cass.»), e la
        # riga sta nella parte bassa della pagina. Col numero si cerca il richiamo; senza numero leggibile: ambiguo.
        k = righe.index(riga)
        a_pag, b_pag = doc.pagine[p]
        for j in range(k, max(-1, k - 16), -1):
            r = righe[j]
            if not r.testo.strip():
                if j < k and (r.a - a_pag) / max(1, b_pag - a_pag) < 0.45:
                    break           # nella parte bassa le note dell'OCR sono spesso separate da righe vuote
                continue
            m = re.match(r'^\s*(\d{1,3})\s+(?=[^\d\s])', r.testo)
            segno = re.match(r'^\s*(?:[*#%®“"”\'’^]{1,2}\s*\d{0,3}|\d{1,3}[*#%®])\s*(?=[A-Za-zÀ-ÿ])', r.testo)
            in_basso = (r.a - a_pag) / max(1, b_pag - a_pag) >= 0.45
            if m and in_basso:
                num = int(m.group(1)); break
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
                # «N testo» in testa a una riga senza richiamo: un paragrafo numerato, non una nota. Nel solo testo non
                # si puo' dire: ambiguo
                return _ambiguo(f'solo testo: riga che comincia con {num}, {come}', nota=num, **base)
            return _ambiguo(come, nota=num, **base)
        # i richiami della pagina restano fuori dal testo della frase (non le cifre: solo quelli in apice)
        togli = [(a, b) for n in (pr - 1, pr, pr + 1) if n in doc.pagine for (a, b, _) in _richiami_apice(doc, n)]
        togli += [(off, off_fine)]
        vic = [pr] if not doc.allineata.get(pr) else [n for n in (pr - 1, pr, pr + 1) if n in doc.pagine]
        f, motivo = frase_attorno(doc, vic, off, togli, testo_solo=not doc.allineata.get(pr), prima=True, fine_richiamo=off_fine)
        if f is None:
            return _ambiguo(motivo, nota=num, pagina_richiamo=pr, **base)
        return {'metodo': 'nota→corpo', 'motivo': f'nota {num}, richiamo a p. {pr} ({come})', 'nota': num,
                'pagina_richiamo': pr, 'richiamo': [off, off_fine], **f, **base}

    # 2. IL CORPO
    if allineata and riga.nota:
        return _ambiguo('nome nella zona delle note', **base)
    togli = [(a, b) for n in (p - 1, p, p + 1) if n in doc.pagine for (a, b, _) in _richiami_apice(doc, n)]
    vic = [n for n in (p - 1, p, p + 1) if n in doc.pagine] if allineata else [p]
    f, motivo = frase_attorno(doc, vic, cs, togli, testo_solo=not allineata)
    if f is None:
        return _ambiguo(motivo, **base)
    return {'metodo': 'corpo', 'motivo': 'frase che contiene il nome', 'nota': None, **f, **base}


if __name__ == '__main__':
    import json
    e = estrai(sys.argv[1], int(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else None)
    print(json.dumps(e, ensure_ascii=False, indent=1))


# ── R15 NELLA COMPOSIZIONE (tools/carica_ripresa.py --composizione R15) ──────────────────────────────────────────

CAMPI_FRASE = ('proposto_frase_sostenuta', 'proposto_frase_testuale', 'proposto_frase_esito', 'proposto_frase_metodo',
               'proposto_frase_motivo', 'proposto_frase_pagine', 'proposto_frase_offset', 'proposto_frase_lettura',
               'proposto_frase_lettura_esito', 'proposto_frase_lettura_testuale')


def testo_delle_pagine(doc, pagine, richiamo=None):
    """IL TESTO DELL'ATTO SU CUI SI PROVA LA FRASE (il freno): il corpo delle pagine da cui viene, come lo legge l'estrattore,
    cioe' senza note, testate e numeri di pagina e senza i numeri dei richiami in apice (che nella frase non ci sono:
    «States70 to justify» nella pagina, «States to justify» nella frase), con le parole spezzate a capo ricucite. Senza
    togliere i richiami il freno dava «non trovata» a 334 frasi giuste su 6.396 (prova a secco del 04/10)."""
    togli = [(a, b) for n in pagine if n in doc.pagine for (a, b, _) in _richiami_apice(doc, n)]
    if richiamo:
        togli.append(tuple(richiamo))
    t, _ = flusso(doc, [n for n in pagine if n in doc.pagine], togli)
    return ricuci(t)


def campi_r15(riga, frase_lettura='', esito_lettura='', testuale_lettura=False):
    """I campi della frase sostenuta con R15 per una riga di corpus_rows (servono file, char_start, file_pdf).
    - estrazione sicura (nota→corpo, corpo): la frase estratta e' la proposta; il freno (`freni.verifica`, testo dell'atto
      ricostruito come in R14) la ritrova per costruzione nelle pagine da cui viene: se non la ritrovasse, vale ambiguo;
    - ambiguo: resta la frase della lettura di DeepSeek con il suo esito (trovata, o «non trovata» come prima).
    La frase della lettura resta comunque in `proposto_frase_lettura` (e il suo esito), per il confronto.
    -> (campi, estrazione)"""
    from freni import verifica
    try:
        e = estrai(riga.get('file'), riga.get('char_start'), riga.get('file_pdf'))
    except Exception as x:                       # mai fermare il caricatore per una riga: ambiguo, col motivo
        e = _ambiguo(f'errore: {type(x).__name__}')
    out = {'proposto_frase_lettura': frase_lettura or '', 'proposto_frase_lettura_esito': esito_lettura or '',
           'proposto_frase_lettura_testuale': bool(testuale_lettura)}
    if e['metodo'] != 'ambiguo':
        doc = documento(str(riga.get('file')), str(riga.get('file_pdf')) if riga.get('file_pdf') else None)
        esito = verifica(e['frase'], testo_delle_pagine(doc, e['pagine'], e.get('richiamo')), (), True)
        if esito == 'trovata':
            out.update({'proposto_frase_sostenuta': e['frase'], 'proposto_frase_testuale': True,
                        'proposto_frase_esito': 'trovata', 'proposto_frase_metodo': e['metodo'],
                        'proposto_frase_motivo': e['motivo'], 'proposto_frase_pagine': e['pagine'],
                        'proposto_frase_offset': [e['inizio'], e['fine']]})
            return out, e
        e = _ambiguo('frase estratta troppo corta per il freno (meno di 20 caratteri)' if esito == 'assente' else
                     'frase estratta non ritrovata dal freno nelle sue pagine', **{k: e[k] for k in ('allineata', 'pagina_citazione') if k in e})
    out.update({'proposto_frase_sostenuta': frase_lettura or '', 'proposto_frase_testuale': bool(testuale_lettura),
                'proposto_frase_esito': esito_lettura or '', 'proposto_frase_metodo': 'ambiguo',
                'proposto_frase_motivo': e['motivo'], 'proposto_frase_pagine': [], 'proposto_frase_offset': None})
    return out, e


def _uguali(a, b):
    import json
    return json.dumps(a, sort_keys=True, ensure_ascii=False, default=str) == json.dumps(b, sort_keys=True, ensure_ascii=False, default=str)


def r15_da_scrivere(riga, campi=None, uguale=None):
    """Che cosa scrive R15 su una riga NON giudicata. `campi`: la proposta che la composizione R14 ha appena calcolato
    (None se la riga non ha letture L05 valide); `uguale(riga, campi)`: il confronto di `carica_ripresa.uguale_a_oggi`.
      - se il resto della proposta R14 e' quello che la riga ha oggi: la proposta intera, con la frase R15 e
        provenienza.composizione = R15;
      - altrimenti (letture mancanti, o la riga porta gia' una composizione diversa, p.es. di un'altra sessione): SOLO i
        campi della frase e provenienza.frase = R15, il resto com'e'.
    La frase della lettura e' quella appena calcolata; senza, quella che la riga ha oggi (o, se la riga ha gia' R15, quella
    conservata in proposto_frase_lettura): il passaggio si puo' rifare senza perdere la frase di DeepSeek.
    -> (campi da scrivere o None se non cambia niente, etichetta, estrazione)"""
    if campi is not None:
        fl, el, tl = campi.get('proposto_frase_sostenuta') or '', campi.get('proposto_frase_esito') or '', campi.get('proposto_frase_testuale')
    elif 'proposto_frase_lettura' in riga:
        fl, el, tl = riga.get('proposto_frase_lettura') or '', riga.get('proposto_frase_lettura_esito') or '', riga.get('proposto_frase_lettura_testuale')
    else:
        fl, el, tl = riga.get('proposto_frase_sostenuta') or '', riga.get('proposto_frase_esito') or '', riga.get('proposto_frase_testuale')
    frase, e = campi_r15(riga, fl, el, tl)
    frase['provenienza.frase'] = VERSIONE
    resto = {k: v for k, v in (campi or {}).items() if k not in CAMPI_FRASE}
    if campi is not None and uguale is not None and uguale(riga, resto):
        out, etichetta = {**campi, **frase, 'provenienza.composizione': VERSIONE}, 'proposta R15 (resto uguale a R14)'
    else:
        out, etichetta = frase, ('solo la frase: senza lettura valida' if campi is None else 'solo la frase: il resto della riga e\' diverso da R14')
    gia = (riga.get('provenienza') or {}).get('frase') == VERSIONE and \
        (out.get('provenienza.composizione') in (None, (riga.get('provenienza') or {}).get('composizione')))
    if gia and all(_uguali(riga.get(k), v) for k, v in out.items() if not k.startswith('provenienza.') and k != 'proposto_ripresa_lettore'):
        return None, 'invariata', e
    return out, etichetta, e
