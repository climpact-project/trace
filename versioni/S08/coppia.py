"""S08, the candidate pair: the text of the filing around two references and the deterministic clues (``coppia``).

Class-based version of ``tools/coppia_s08.py`` (5 October 2026). Three steps need to see the same pair in the same way:
the question to the readers (:mod:`tracepipe.lettura_coppia`), the decision (:mod:`tracepipe.decisione_coppie`) and the
list of the pairs (:mod:`tracepipe.coppie_vicine`).

A :class:`Coppia` is born from two live rows of the same case and the same filing (or new rows of the scan), the first
in the text called ``a``, the second ``b``. Nothing is written: it is all reading of a snapshot of the database and of
the markdown files.

THE CLUES (:meth:`Coppia.indizi`) NEVER ENTER THE PROMPT: they serve to measure the readings apart and to send to the
team the pairs in which the readings and a strong clue contradict each other. Each one has its precision measured on
the 850 pairs of C03 reread by hand (``training/misure/S08-COPPIE-VICINE-2026-10-04.md``).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from .corpus import PAGINA_MD
from .ricerca import INIZIO_NOTA, confine_di_nota, e_inizio_nota, front_matter, segni_pagina
from .righe import LettoreAtti, Riga, normalizza, pagina_di_riga

ATTORNO = 1500
"""Characters of filing before the first reference and after the last."""
TETTO_FINESTRA = 26000
"""The window never exceeds this (two very distant references: the borders are cut, never the middle)."""
SOGLIA_FRASE = 95
"""R15: the same sentence if the rapidfuzz ratio is at least this (as in C03)."""
MIN_FRASE = 40
"""Minimum characters of the supported sentence for the comparison."""
LUNGHEZZA_NOME = 160
"""Characters after the name compared for «same words»."""
LUNGHEZZA_DESCRIZIONE = 40
"""The length given to a reference found by description (the name is not there)."""
VUOTA = re.compile(r'\n[ \t]*\n')
_RICHIAMO = r'(?<=[^\W\d_\s.,;:]){n}(?![\d])|(?<=[\)\]\.\,\;\:\u201d"\u00bb\u2019\']){n}(?![\d])'


def pulisci_pagine(testo: str) -> str:
    """The page mark as it is in the prompt of the other readings: ``[pagina N]``."""
    return PAGINA_MD.sub(lambda m: f'[pagina {m.group(1)}]', testo)


def lunghezza_riferimento(riga: Riga) -> int:
    """How many characters the reference starting at ``char_start`` takes: the form found by the lexical network; for
    the descriptive network (the name is not there) a fixed length."""
    forma = riga.get('proposto_forma_trovata') or ''
    if forma and not forma.startswith('descrizione'):
        return len(forma)
    return LUNGHEZZA_DESCRIZIONE


@dataclass(frozen=True)
class Atto:
    """A filing read from its markdown file.

    Attributes:
        testo: the whole text.
        meta: the front matter.
        inizio: the offset where the front matter ends.
        segni: ``(offset, page)`` of every page mark.
    """

    testo: str
    meta: Mapping[str, str]
    inizio: int
    segni: tuple[tuple[int, int], ...]


class ArchivioAtti:
    """The filings, read once and kept (the ``leggi_atto`` cache of the live tool).

    Args:
        radice: the project root.
    """

    def __init__(self, radice: Path | str) -> None:
        self.lettore = LettoreAtti(radice)
        self._atti: dict[str, Atto] = {}

    def atto(self, file: str) -> Atto:
        if file not in self._atti:
            testo = self.lettore.testo(file)
            meta, inizio = front_matter(testo)
            self._atti[file] = Atto(testo, meta, inizio, tuple(segni_pagina(testo)))
        return self._atti[file]


class Coppia:
    """Two live rows of the same filing and the same case. ``a`` comes before ``b`` in the text.

    Args:
        a: a row.
        b: the other row.
        atti: where the filings are read.
        id_coppia: the id of the pair (default ``<code a>-<code b>``).
        caso: the case (default that of ``a``).
    """

    def __init__(self, a: Riga, b: Riga, atti: ArchivioAtti, id_coppia: str = '', caso: str = '') -> None:
        if int(a['char_start']) > int(b['char_start']):
            a, b = b, a
        self.a, self.b = a, b
        self.id = id_coppia or f'{a.get("codice")}-{b.get("codice")}'
        self.caso = caso or a.get('caso_citato', '')
        self.file = a['file']
        atto = atti.atto(self.file)
        self.testo, self.meta, self.inizio, self.segni = atto.testo, atto.meta, atto.inizio, atto.segni
        self.pa, self.pb = int(a['char_start']), int(b['char_start'])

    # the window of the filing

    def intervallo(self) -> tuple[int, int]:
        """``(from, to)`` in characters of the file: from the first reference minus :data:`ATTORNO` to the last plus
        :data:`ATTORNO`; if it exceeds the cap the two borders are cut."""
        da = max(self.inizio, self.pa - ATTORNO)
        a = min(len(self.testo), self.pb + lunghezza_riferimento(self.b) + ATTORNO)
        if a - da > TETTO_FINESTRA:
            extra = a - da - TETTO_FINESTRA
            da, a = da + extra // 2, a - (extra - extra // 2)
        return da, a

    def finestra(self) -> tuple[str, str]:
        """``(text with the marks ⟦A⟧ and ⟦B⟧ for the model, plain text for the brakes)``.

        The marks stand BEFORE the reference, never inside a word; the plain text is the filing as it is (with
        ``[pagina N]``), the one in which the brakes look for the sentences.
        """
        da, a = self.intervallo()
        puro = pulisci_pagine(self.testo[da:a])
        pezzi: list[str] = []
        cur = da
        for p, marca in ((self.pa, '⟦A⟧'), (self.pb, '⟦B⟧')):
            pezzi.append(self.testo[cur:p])
            pezzi.append(marca)
            cur = p
        pezzi.append(self.testo[cur:a])
        return pulisci_pagine(''.join(pezzi)), puro

    # the deterministic clues

    def nota_di(self, pos: int) -> tuple[str | None, int | None]:
        """``(number of the footnote that contains pos, where it starts)``, or ``(None, None)`` if pos is in the text.

        It looks at the TEXT, not at ``proposto_posizione`` (wrong in many rows: «marked body but it is note 111»):
        ``pos`` is in a note if the last note start before it (a number at the start of a line, filtered by
        :func:`e_inizio_nota`) is on the same page and no empty line (a change of paragraph) lies between them.
        """
        da = max(self.inizio, pos - 4000)
        ultimo = None
        for x in INIZIO_NOTA.finditer(self.testo, da, min(len(self.testo), pos + 1)):
            if x.end() > pos:
                break
            if e_inizio_nota(self.testo, x):
                ultimo = x
        if ultimo is None:
            return None, None
        fra = self.testo[ultimo.end() : pos]
        if VUOTA.search(fra) or PAGINA_MD.search(fra):
            return None, None
        return (ultimo.group(1) or ultimo.group(3) or ultimo.group(2)), ultimo.end()

    def posizione(self, riga: Riga) -> str:
        """``'nota'`` if the point of the reference is inside a footnote, else ``'testo'``."""
        return 'nota' if self.nota_di(int(riga['char_start']))[0] else 'testo'

    def frase_della_riga(self, riga: Riga) -> tuple[int, int]:
        """The interval of the sentence of the row: ``proposto_frase_offset`` if there is one, else about 350
        characters around the name."""
        o = riga.get('proposto_frase_offset')
        try:
            if isinstance(o, list) and len(o) == 2:
                return int(o[0]), int(o[1])
        except (TypeError, ValueError):
            pass
        c = int(riga['char_start'])
        return max(self.inizio, c - 200), c + 150

    def nota_chiamata(self, nota: Riga, testo_r: Riga) -> bool | None:
        """Is the note of ``nota`` (the row in a note) called by the sentence of ``testo_r``?

        The mark is the number of the note stuck to the end of a word or a sign in the sentence (``...1990)15.``): the
        number is searched and must not be any digit (a year, a paragraph number). ``None`` if the row is not in a note.
        """
        n, _ = self.nota_di(int(nota['char_start']))
        if not n:
            return None
        d, a = self.frase_della_riga(testo_r)
        a = min(len(self.testo), a + 40)
        frase = self.testo[d:a]
        return bool(re.search(_RICHIAMO.format(n=n), frase))

    def indizi(self) -> dict[str, Any]:
        """The clues of the pair, as a dictionary (distance, positions, same sentence, same note, called note...)."""
        a, b = self.a, self.b
        fa, fb = normalizza(a.get('proposto_frase_sostenuta')), normalizza(b.get('proposto_frase_sostenuta'))
        pos_a, pos_b = self.posizione(a), self.posizione(b)
        entro = self.testo[self.pa : self.pb]
        na, _ = self.nota_di(self.pa) if pos_a == 'nota' else (None, None)
        nb, _ = self.nota_di(self.pb) if pos_b == 'nota' else (None, None)
        confine = confine_di_nota(self.testo, self.pa + lunghezza_riferimento(a), self.pb)
        par_a, par_b = set(a.get('proposto_paragrafi') or []), set(b.get('proposto_paragrafi') or [])
        pagina_a, pagina_b = pagina_di_riga(a), pagina_di_riga(b)
        ia: dict[str, Any] = {
            'distanza': self.pb - self.pa,
            'pagine': abs((pagina_a or 0) - (pagina_b or 0)) if pagina_a and pagina_b else None,
            'stessa_pagina': pagina_a == pagina_b and pagina_a is not None,
            'posizione_a': pos_a,
            'posizione_b': pos_b,
            'stessa_frase': bool(
                len(fa) >= MIN_FRASE and len(fb) >= MIN_FRASE and (fa == fb or fuzz.ratio(fa, fb) >= SOGLIA_FRASE)
            ),
            'nota_contro_testo': {pos_a, pos_b} == {'testo', 'nota'},
            'confine_di_nota_fra_le_due': confine,
            'stesso_paragrafo': VUOTA.search(entro) is None,
            'stessa_nota': bool(na and nb and na == nb and not confine),
            'due_note_diverse': bool(pos_a == 'nota' and pos_b == 'nota' and confine),
            'paragrafi_in_comune': bool(par_a & par_b),
            'paragrafi_diversi': bool(par_a and par_b and not (par_a & par_b)),
            'stesse_parole': round(
                fuzz.ratio(
                    normalizza(self.testo[self.pa : self.pa + LUNGHEZZA_NOME]),
                    normalizza(self.testo[self.pb : self.pb + LUNGHEZZA_NOME]),
                )
                / 100,
                3,
            ),
        }
        if ia['nota_contro_testo']:
            nota, testo_r = (a, b) if pos_a == 'nota' else (b, a)
            ia['nota_chiamata_dal_testo'] = self.nota_chiamata(nota, testo_r)
        else:
            ia['nota_chiamata_dal_testo'] = None
        return ia

    def dove(self, riga: Riga) -> str:
        """``'testo'`` or ``'nota'``: where the reference is, according to the text."""
        return self.posizione(riga)


def verdetto_indizi(i: Mapping[str, Any]) -> tuple[str | None, str, bool]:
    """THE JUDGMENT OF THE CLUES: ``(outcome, reason, strong)``.

    ``outcome`` is ``'una'`` (one citation), ``'due'`` (two) or ``None`` (no clue); ``strong`` says whether the clue has
    a measured precision of at least 0.97 on the 692 pairs of C03 reread by hand in the same filing: only a strong clue
    can send to the team a pair on which the readings agree. Weak clues stay in the report but do not decide.

    ======  ======  ====================================================================================
    Out     Strong  Clue
    ======  ======  ====================================================================================
    una     yes     same note: the two rows are in the same note, with no note start between them
    una     yes     body row and note row: the note is called by the sentence of the body row
    due     no      two different notes (a note start lies between the two rows): consecutive notes stay apart
    due     no      the note is not called by the sentence and the cited paragraphs differ
    ======  ======  ====================================================================================
    """
    if i['stessa_nota']:
        return 'una', 'stessa nota', True
    if i['nota_contro_testo'] and i['nota_chiamata_dal_testo']:
        return 'una', "la nota e' chiamata dalla frase del testo", True
    if i['due_note_diverse']:
        return 'due', 'due note diverse', False
    if i['paragrafi_diversi'] and i['nota_chiamata_dal_testo'] is False:
        return 'due', 'nota non chiamata e paragrafi citati diversi', False
    return None, '', False
