"""The brakes of R14 and R16: the proof is searched in the filing without the system marks, and in whole.

:class:`FreniProvaIntera` extends :class:`tracepipe.freni.Freni` with the two corrections of 4 October 2026 that
``tools/freni.py`` has and the first brakes of the package do not (the existing methods keep their behaviour; the new
arguments default to the old one).

R14, the text of the filing under the marks of the system. The context sent to the model carries the marks of the
passage (``[[INIZIO/FINE DEL BRANO SEGNALATO]]``) and of the name (``⟦ ⟧``), put at an exact character, often inside a
word. The model copies the sentence of the filing without them, and the brake called it «not found» (2,211 supported
sentences out of 4,696 on 4 October). With ``ricostruisci`` the proof is also searched in the text without the marks and
with the words split at the line end stitched back (684 sentences and 3,788 proofs of the surrounding pages).

R16, the whole proof (the PI's yes of 4 October). Up to R14 only the first 60 normalised characters of the proof were
searched: a proof with a true beginning and an invented end passed. With ``intera`` (which implies R14) a proof passes
only if it is in the page WHOLE:

- every stretch between two omission dots (``...``, ``[...]``, ``…``) is searched on its own;
- without spaces (words split by the line end), without the lone numbers of the page (footnote marks between words)
  and without the digits stuck to a word, in the page and in the proof;
- on the page joined to the NEXT page, also without the footnote lines: the sentence goes on after the notes;
- without the marks of the context (``===== PAGINA ... =====``, ``[pagina N]``);
- if not all of it is there: at least 90% of the characters of the proof in stretches of 20 or more characters that are
  in the page (an invented ending does not pass; a silent cut in the middle passes if the two pieces are long: a
  declared limit);
- accented letters written apart (``ü``) recomposed (NFC);
- only in documents redone with OCR (D02): one different letter per word (the model corrects an OCR misprint).

Measured on the L05 readings of 3 October (about 119,000 proofs and sentences found by R14): 768 no longer pass
(0.6%); of 20 read by hand 15 are not copied to the letter, 2 or 3 are wrongly refused, 1 is an index line too short to
be a proof.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from .freni import Freni

_SEGNI = re.compile(r'\[\[(?:INIZIO|FINE) DEL BRANO SEGNALATO\]\]|[\u27e6\u27e7]')
_A_CAPO = re.compile(r'(?<=\w)[-\u00ad\u2010]\s*\n\s*(?=\w)')
_OMISSIONE = re.compile(r'\s*(?:\[\s*(?:\.\s*){2,}\]|\(\s*(?:\.\s*){2,}\)|(?:\.\s*){3,}|…|\[…\]|\(…\))\s*')
_NUMERI_SOLI = re.compile(r'(?<!\S)\d+(?!\S)')
_CIFRE_INCOLLATE = re.compile(r'(?<=[^\W\d_])\d+')
_RIGA_NOTA = re.compile(r'^\s*\(?\d{1,4}[\).]?\s+\S.*$', re.MULTILINE)
_SEGNI_CONTESTO = re.compile(r'^=====.*=====\s*$|\[pagina \d+\]', re.MULTILINE)


class FreniProvaIntera(Freni):
    """The brakes with R14 and R16.

    Args:
        copertura_intera: the share of the proof that must be in found stretches (default 0.9).
        tratto_intero: the minimum length of a stretch (default 20 characters).
        **kw: the thresholds of :class:`tracepipe.freni.Freni`.
    """

    def __init__(self, copertura_intera: float = 0.9, tratto_intero: int = 20, **kw: float) -> None:
        super().__init__(**kw)
        self.copertura_intera = copertura_intera
        self.tratto_intero = tratto_intero

    # R14: the text of the filing under the marks of the system
    @staticmethod
    def testi_atto(testo_pagina: object) -> list[str]:
        """The page as it is, without the marks of the system, and without them with split words stitched."""
        t = str(testo_pagina or '')
        s = _SEGNI.sub('', t)
        return [t, s, _A_CAPO.sub('', s)]

    def prova_trovata(self, prova: object, testo_pagina: object, ricostruisci: bool = False) -> bool:
        """The first characters of the proof are in the page; with ``ricostruisci`` (R14) also in the text of the
        filing without the marks of the system."""
        if ricostruisci:
            if len(self.norm(prova)) < self.min_prova:
                return False
            return any(super(FreniProvaIntera, self).prova_trovata(prova, t) for t in self.testi_atto(testo_pagina))
        return super().prova_trovata(prova, testo_pagina)

    # R16: the whole proof
    def _n16(self, t: object) -> str:
        return _CIFRE_INCOLLATE.sub('', self.norm(unicodedata.normalize('NFC', str(t or ''))))

    def tratti(self, prova: object) -> list[str]:
        """The proof cut at the omission dots, each stretch normalised, empty ones dropped."""
        return [p for p in (self._n16(x) for x in _OMISSIONE.split(str(prova or ''))) if p]

    def copertura(self, p: str, t: str) -> float:
        """The share of the characters of ``p`` covered by stretches of at least ``tratto_intero`` characters that are
        in ``t`` (the longest one from the left)."""
        i = cop = 0
        m = len(p)
        while i < m:
            lo, hi = self.tratto_intero, m - i
            if hi < lo or p[i : i + lo] not in t:
                i += 1
                continue
            while lo < hi:
                mm = (lo + hi + 1) // 2
                if p[i : i + mm] in t:
                    lo = mm
                else:
                    hi = mm - 1
            cop += lo
            i += lo
        return cop / max(m, 1)

    @staticmethod
    def senza_note(t: str) -> str:
        """The text without the lines that start a footnote."""
        return _RIGA_NOTA.sub(' ', t)

    def testi_r16(self, testo_pagina: object, seguito: str = '') -> list[str]:
        """The texts of the page the whole proof is looked for in."""
        base = [_SEGNI_CONTESTO.sub(' ', t) for t in self.testi_atto(testo_pagina)]
        if seguito:
            return (
                base
                + [t + '\n' + seguito for t in base]
                + [self.senza_note(t) + '\n' + self.senza_note(seguito) for t in base]
            )
        return base + [self.senza_note(t) for t in base]

    @staticmethod
    def una_lettera(a: str, b: str) -> bool:
        """The two words are equal or differ by one letter (one changed, added or missing); never under four letters."""
        if a == b:
            return True
        if abs(len(a) - len(b)) > 1 or min(len(a), len(b)) < 4:
            return False
        if len(a) == len(b):
            return sum(x != y for x, y in zip(a, b, strict=True)) <= 1
        if len(a) > len(b):
            a, b = b, a
        i = 0
        while i < len(a) and a[i] == b[i]:
            i += 1
        return a[i:] == b[i + 1 :]

    def con_refusi(self, tratti: Iterable[str], t: str) -> bool:
        """Every stretch is in the text allowing one different letter per word (OCR misprints)."""
        w = t.split()
        for p in tratti:
            q = p.split()
            if q and not any(
                all(self.una_lettera(x, y) for x, y in zip(q, w[i : i + len(q)], strict=False))
                for i in range(len(w) - len(q) + 1)
            ):
                return False
        return True

    def prova_intera(self, prova: object, testo_pagina: object, seguito: str = '', ocr: bool = False) -> bool:
        """R16: the proof is in the page whole (see the module).

        Args:
            prova: the proof the model quoted.
            testo_pagina: the page.
            seguito: the text of the next page.
            ocr: the document was redone with OCR (D02).
        """
        tr = self.tratti(prova)
        if sum(len(x) for x in tr) < self.min_prova:
            return False
        senza = [x.replace(' ', '') for x in tr]
        compatti: list[str] = []
        for testo in self.testi_r16(testo_pagina, seguito):
            n = self._n16(testo)
            for t in (n, _NUMERI_SOLI.sub(' ', n)):
                if all(x in t for x in tr) or (ocr and self.con_refusi(tr, t)):
                    return True
                t = t.replace(' ', '')
                if all(x in t for x in senza):
                    return True
                compatti.append(t)
        # the coverage by stretches only after the exact comparisons, and once per different text
        if len(senza) == 1:
            for t in dict.fromkeys(compatti):
                if self.copertura(senza[0], t) >= self.copertura_intera:
                    return True
        return False

    def verifica(
        self,
        prova: object,
        testo_pagina: object,
        testi_prompt: Iterable[str] | None = (),
        ricostruisci: bool = False,
        intera: bool = False,
        seguito: str = '',
        ocr: bool = False,
    ) -> str:
        """The outcome of a proof: ``'trovata'`` | ``'inventata'`` | ``'non trovata'`` | ``'assente'``.

        ``ricostruisci`` (R14): see :meth:`prova_trovata`. ``intera`` (R16, implies R14): the proof must also be in the
        page whole (:meth:`prova_intera`, with ``seguito`` and ``ocr``). The check against the prompt does not change.
        """
        if not prova or len(self.norm(prova)) < self.min_prova:
            return 'assente'
        if self.prova_trovata(prova, testo_pagina, ricostruisci or intera) and (
            not intera or self.prova_intera(prova, testo_pagina, seguito, ocr)
        ):
            return 'trovata'
        if self.prova_dal_prompt(prova, testi_prompt):
            return 'inventata'
        return 'non trovata'
