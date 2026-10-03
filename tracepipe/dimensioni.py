"""The four dimensions proposed by the system for each name occurrence (``tools/dimensioni.py``).

Who cites (from the type of filing, corrected when a court reports a party's argument), the seat of the passage
(reasoning, reported submissions, dissent, concurrence, party filing), and where the reference sits (body or footnote,
read from the PDF: the markdown flattens font size and position). Each proposal carries a confidence; ``bassa`` means
no clue was found and the value is a fallback. The patterns and thresholds are the live ones, verbatim.
"""

from __future__ import annotations

import contextlib
import re
import statistics
from collections.abc import Mapping
from pathlib import Path
from typing import Any

DA_TIPO_ATTO = {
    'decisione': 'corte',
    'ordinanza': 'corte',
    'atto introduttivo': 'parte',
    'replica': 'parte',
    'istanza': 'parte',
    'memoria': 'parte',
    'opposizione': 'parte',
    'amicus': 'amicus',
}

# ── Indizi di difesa riportata ──────────────────────────────────────────
#
# Le formule con cui una corte attribuisce un argomento a chi glielo ha
# proposto. Sono espressioni di rito, quindi stabili dentro ciascuna
# lingua: e' il motivo per cui si possono cercare.
#
# LE LINGUE SONO QUELLE EFFETTIVAMENTE PRESENTI NEL CORPUS. Dove manca la
# lingua, l'indizio non si trova e la confidenza scende a `bassa`: il
# sistema dichiara di non sapere invece di indovinare.

_ATTORI = (
    r'plaintiffs?|applicants?|claimants?|appellants?|petitioners?|'
    r'respondents?|defendants?|complainants?|intervenors?|'
    r'ricorrent[ei]|resistent[ei]|attor[ei]|convenut[oi]|'
    r'demandantes?|demandados?|recurrentes?|'
    r'requ[eé]rants?|d[eé]fendeurs?|'
    r'kl[aä]ger(?:in)?(?:nen)?|beklagten?|'
    r'eisers?|verweerders?|'
    r'autores?|r[eé]us?'
)

INDIZI_DIFESA = [
    re.compile(p, re.I)
    for p in (
        # inglese
        rf'\b(?:the\s+)?(?:{_ATTORI})\b[^.]{{0,60}}?\b'
        r'(?:argue|argues|argued|contend|contends|submit|submits|submitted|'
        r'assert|asserts|maintain|maintains|claim|claims|rely|relies|relied|'
        r'invoke|invokes|invoked|point|points|cite|cites|cited)\b',
        rf'\baccording to (?:the\s+)?(?:{_ATTORI})\b',
        r'\b(?:it is|it was) (?:submitted|argued|contended|alleged)\b',
        r'\bcounsel for (?:the )?\w+',
        r'\bin (?:their|his|her|its) (?:submission|brief|pleadings?|'
        r'written observations|memorial)\b',
        r'\b(?:the )?(?:parties|applicants?|plaintiffs?) (?:refer|refers|referred) to\b',
        # italiano
        rf'\b(?:i|le|il|la)\s+(?:{_ATTORI})\b[^.]{{0,50}}?\b'
        r'(?:sostengono|sostiene|deducono|deduce|lamentano|lamenta|'
        r'assumono|assume|invocano|invoca|richiamano|richiama|eccepiscono)\b',
        r'\bsecondo (?:il|la|i|le)\s+\w+',
        r'\ba (?:dire|avviso|parere) (?:del|della|dei)\b',
        # spagnolo
        rf'\b(?:los|las|el|la)\s+(?:{_ATTORI})\b[^.]{{0,50}}?\b'
        r'(?:sostienen|sostiene|alegan|alega|argumentan|argumenta|'
        r'invocan|invoca|citan|cita|aducen)\b',
        r'\bseg[uú]n (?:el|la|los|las)\s+\w+',
        # francese
        rf'\b(?:les|le|la)\s+(?:{_ATTORI})\b[^.]{{0,50}}?\b'
        r'(?:soutiennent|soutient|font valoir|fait valoir|invoquent|invoque|'
        r'all[eè]guent|all[eè]gue|se pr[eé]valent)\b',
        r'\bselon (?:le|la|les)\s+\w+',
        # tedesco
        rf'\b(?:die|der|das)\s+(?:{_ATTORI})\b[^.]{{0,50}}?\b'
        r'(?:machen geltend|macht geltend|tragen vor|tr[aä]gt vor|'
        r'berufen sich|beruft sich)\b',
        r'\bnach (?:Auffassung|Ansicht) (?:der|des)\b',
        # olandese
        rf'\b(?:de|het)\s+(?:{_ATTORI})\b[^.]{{0,50}}?\b'
        r'(?:stellen|stelt|voeren aan|voert aan|beroepen zich|beroept zich)\b',
        r'\bvolgens (?:de|het)\s+\w+',
        # portoghese
        rf'\b(?:os|as|o|a)\s+(?:{_ATTORI})\b[^.]{{0,50}}?\b'
        r'(?:alegam|alega|sustentam|sustenta|invocam|invoca)\b',
        r'\bsegundo (?:o|a|os|as)\s+\w+',
    )
]

# Intestazioni che aprono una sezione dedicata alle difese: valgono per
# tutto il seguito, non solo per la frase in cui compaiono.
INTESTAZIONI_DIFESE = re.compile(
    r'^\s*(?:[IVXLC]+\.?\s*|\d+[\.\)]\s*)?'
    r'(?:(?:the\s+)?(?:parties[’\']?\s+)?'
    r'(?:submissions?|arguments?|contentions?|pleadings?|'
    r'position of the parties|arguments of the parties|'
    r'summary of (?:the )?(?:arguments|submissions))'
    r'|argomenti (?:del|delle|dei) part[ei]|le difese|posizioni delle parti'
    r'|alegaciones|argumentos de las partes'
    r'|arguments des parties|th[eè]ses des parties'
    r'|vorbringen der (?:parteien|beteiligten)'
    r'|standpunt(?:en)? van (?:de )?partijen'
    r')\s*:?\s*$',
    re.I | re.M,
)

# ── Dimensione: dove sta il riferimento ─────────────────────────────────
#
# Corpo o nota a pie' di pagina. Negli atti giuridici la nota e' il luogo
# in cui si dice A CHI si attribuisce un principio: un riferimento in nota
# e un riferimento nel corpo non pesano uguale, e sommarli e' un errore.
#
# NON E' INFALLIBILE, e non pretende di esserlo: quando la zona non si
# distingue, dichiara che non c'e' invece di indovinare.

# IL SEGNALE E' LA NUMERAZIONE CONSECUTIVA, non l'aspetto della riga.
#
# Primo tentativo, scartato: risalire dal fondo finche' le righe "sembrano
# note". Falliva su due cose viste nel corpus reale — un numero di pagina in
# ultima riga interrompeva la risalita prima di arrivare alle note, e le
# note oltre la novecentonovantanovesima (Klimaatzaak ne ha piu' di mille)
# non venivano riconosciute. In piu' l'estrazione a volte attacca le note
# alla fine dell'ultima riga di testo, e una regola per righe non le vede.
#
# Qui si cercano i marcatori ovunque nella meta' bassa della pagina e si
# tiene la piu' lunga sequenza CRESCENTE: due o piu' numeri che salgono di
# poco, ciascuno seguito da un capoverso. E' cio' che distingue una zona di
# note da un numero qualsiasi in mezzo al testo — e nessun testo continuo
# produce per caso una sequenza crescente di marcatori.

_MARCATORE = re.compile(
    r"(?:(?<=^)|(?<=[\s.\)\]\u201d\"'\u2019]))"  # a inizio riga o dopo una chiusura
    r'[\(\[]?(\d{1,4})[\)\].,:]?[ \t]+'  # il numero della nota
    r'(?=[A-Z“"\(\[«\u00C0-\u024F])',  # e un capoverso che comincia
    re.M,
)

DISSENSO = re.compile(
    r'\b(?:dissenting|dissent(?:s|ed)?|in dissent|'
    r'opini[oó]n disidente|voto (?:particular|disidente|razonado)|'
    r'opinion dissidente|abweichende meinung|sondervotum|'
    r'opinione dissenziente|dissenso)\b',
    re.I,
)
CONCORRENTE = re.compile(
    r'\b(?:concurring|concurrence|opini[oó]n concurrente|'
    r'opinion concordante|opinione concorrente)\b',
    re.I,
)


_ORDINE = {'alta': 2, 'media': 1, 'bassa': 0}
_MOTIVAZIONE = re.compile(
    r'^\s*(?:[IVXLC]+\.?\s*|\d+[\.\)]\s*)?'
    r'(?:reasons|analysis|discussion|findings|'
    r'the court[’\']?s assessment|motivazione|'
    r'considerato in diritto|fundamentos|'
    r'motifs|entscheidungsgr[uü]nde|beoordeling)'
    r'\s*:?\s*$',
    re.I | re.M,
)


def dimensioni(meta: Mapping[str, Any], pagina: str, off_in_pagina: int, prima: str) -> dict[str, str]:
    """The proposals for one occurrence: ``chi_cita_auto``, ``sede_auto``, ``dimensioni_confidenza``.

    Args:
        meta: the front matter of the document (``tipo_atto``).
        pagina: the whole page of the occurrence.
        off_in_pagina: where the occurrence falls in the page.
        prima: the text of the document before the occurrence (section headings, separate opinions).
    """
    tipo = (meta.get('tipo_atto') or '').strip().lower()
    base = DA_TIPO_ATTO.get(tipo, 'non_determinabile')
    vicino = pagina[max(0, off_in_pagina - 420) : off_in_pagina + 120]
    coda = prima[-9000:]
    sede, conf_sede = 'motivazione', 'bassa'
    if base == 'corte':
        if any(p.search(vicino) for p in INDIZI_DIFESA):
            sede, conf_sede = 'difese_riportate', 'alta'
        else:
            ints = list(INTESTAZIONI_DIFESE.finditer(coda))
            if ints:
                dopo = coda[ints[-1].end() :]
                if not _MOTIVAZIONE.search(dopo):
                    sede, conf_sede = 'difese_riportate', 'media'
            if sede == 'motivazione':
                conf_sede = 'media'
        if DISSENSO.search(coda[-4000:]):
            sede, conf_sede = 'dissenso', 'media'
        elif CONCORRENTE.search(coda[-4000:]):
            sede, conf_sede = 'concorrente', 'media'
    elif base in ('parte', 'amicus'):
        sede, conf_sede = 'atto_di_parte', 'alta'
    else:
        sede, conf_sede = 'non_determinabile', 'bassa'
    chi = base
    conf_chi = 'alta' if base != 'non_determinabile' else 'bassa'
    if base == 'corte' and sede == 'difese_riportate':
        chi = 'parte'
        conf_chi = conf_sede
    conf = min((conf_chi, conf_sede), key=lambda c: _ORDINE[c])
    return {'chi_cita_auto': chi, 'sede_auto': sede, 'dimensioni_confidenza': conf}


def _norm(t: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', t.lower())


class PosizioneNelPdf:
    """Body or footnote, read from the PDF with PyMuPDF; each PDF is opened once (``posizione``, ``chiudi_pdf``).

    The signal is the font size and the position on the page: footnotes are lines smaller than 94% of the median
    body size in the lower 45% of the page. Flat pages (one size: the OCR layer of tesseract) say
    ``non_determinabile``.
    """

    def __init__(self) -> None:
        self._aperti: dict[str, Any] = {}

    def __enter__(self) -> PosizioneNelPdf:
        return self

    def __exit__(self, *_: object) -> None:
        self.chiudi()

    def _pagine_note(self, pdf: Path, npag: int) -> tuple[str, str] | None:
        try:
            import fitz
        except ImportError as e:
            raise RuntimeError(
                'PyMuPDF non e installato: la colonna corpo/nota non si puo '
                'calcolare. Installalo con  ./.venv/bin/pip install pymupdf'
            ) from e
        chiave = str(pdf)
        d = self._aperti.get(chiave)
        if d is None:
            try:
                d = fitz.open(pdf)
            except Exception:
                self._aperti[chiave] = False
                return None
            self._aperti[chiave] = d
        if d is False or npag < 1 or npag > d.page_count:
            return None
        try:
            pg = d[npag - 1]
            alt = pg.rect.height
            righe = []
            for blocco in pg.get_text('dict')['blocks']:
                for riga in blocco.get('lines', []):
                    t = ''.join(sp['text'] for sp in riga['spans'])
                    if not t.strip():
                        continue
                    dim = statistics.median(
                        [sp['size'] for sp in riga['spans'] for _ in range(max(1, len(sp['text'])))]
                    )
                    righe.append((riga['bbox'][1], dim, t))
        except Exception:
            return None
        if len(righe) < 4:
            return None
        corpo_dim = statistics.median([dim for _, dim, t in righe for _ in range(len(t))])
        if not any(dim < corpo_dim * 0.94 for _, dim, _ in righe):
            return None
        note: list[str] = []
        testo: list[str] = []
        for y, dim, t in righe:
            (note if (dim < corpo_dim * 0.94 and y > alt * 0.55) else testo).append(t)
        if not note:
            return '\n'.join(testo), ''
        return '\n'.join(testo), '\n'.join(note)

    def posizione(self, pdf: Path, npag: int, ago: str) -> tuple[str, str]:
        """``(corpo | nota | non_determinabile, confidence)``; ``ago`` is a piece of the occurrence text."""
        out = self._pagine_note(pdf, npag)
        if out is None:
            return 'non_determinabile', 'bassa'
        corpo_t, note_t = out
        if not note_t:
            return 'corpo', 'alta'
        a = _norm(ago)[:70]
        if len(a) < 24:
            return 'non_determinabile', 'bassa'
        in_note = a in _norm(note_t)
        in_corpo = a in _norm(corpo_t)
        if in_note and not in_corpo:
            return 'nota', 'alta'
        if in_corpo and not in_note:
            return 'corpo', 'alta'
        return 'non_determinabile', 'bassa'

    def chiudi(self) -> None:
        for d in self._aperti.values():
            if d:
                with contextlib.suppress(Exception):
                    d.close()
        self._aperti.clear()
