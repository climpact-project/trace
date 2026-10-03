"""The brakes against invented answers (``freni``, Italian for brakes), from ``tools/freni.py`` (30/09/2026).

On 30/09 the re-reading found that DeepSeek, given 130 unreadable pages (broken characters), answered anyway, and in
5 cases quoted the text of a principle from the prompt as "a sentence copied from the page". The model always
answers; the brake is in the code, not in the instructions. Four checks, used in every reading:

1. :meth:`Freni.leggibile` before reading: a page without enough real words never reaches the model;
2. :meth:`Freni.prova_trovata` after the answer: the quoted evidence must be in the page, word for word;
3. :meth:`Freni.prova_dal_prompt`: evidence that matches a prompt text (principles, instructions) is invented;
4. :meth:`Freni.verifica` combines them into one outcome.

The logic is the live one, character for character; only the packaging changes.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# Latin vowels (with accents) that make a Latin-script token a word.
_VOCALI = re.compile(r'[aeiouyàèéìòùäöüáíóúãõâêôîûœæ]', re.I)
_NORM = re.compile(r'[^\w]+', re.U)
_SPAZI = re.compile(r'\s+')
_NON_PAROLA = re.compile(r'[^\w]')
_ALFANUMERICO = re.compile(r'\w')
# Japanese, Chinese and Korean, compared without spaces (01/10/2026).
_CJK = re.compile(r'[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\uf900-\ufaff]')


def _senza_spazi_tra_parole(ch: str) -> bool:
    """Scripts written without spaces between words: East Asian, Thai, Lao, Khmer, Burmese (02/10/2026)."""
    o = ord(ch)
    return o > 0x2E7F or 0x0E00 <= o <= 0x0EFF or 0x1000 <= o <= 0x109F or 0x1780 <= o <= 0x17FF


class Freni:
    """The four brakes with their thresholds.

    Attributes:
        soglia_leggibile: minimum share of tokens that are real words (``SOGLIA_LEGGIBILE``).
        min_parole: below this number of tokens a page is empty, not "unreadable" (``MIN_PAROLE``).
        lunghezza_confronto: normalised characters with which evidence is searched in a page
            (``LUNGHEZZA_CONFRONTO``).
        soglia_scrittura_continua: share of letters of space-less scripts above which the page is measured on
            characters instead of words.
        min_caratteri_continua: minimum non-space characters of a space-less page.
        quota_lettere_continua: minimum share of letters among the non-space characters of a space-less page.
        min_prova: minimum normalised length of a piece of evidence.
    """

    def __init__(
        self,
        soglia_leggibile: float = 0.5,
        min_parole: int = 40,
        lunghezza_confronto: int = 60,
        soglia_scrittura_continua: float = 0.3,
        min_caratteri_continua: int = 200,
        quota_lettere_continua: float = 0.6,
        min_prova: int = 20,
    ) -> None:
        self.soglia_leggibile = soglia_leggibile
        self.min_parole = min_parole
        self.lunghezza_confronto = lunghezza_confronto
        self.soglia_scrittura_continua = soglia_scrittura_continua
        self.min_caratteri_continua = min_caratteri_continua
        self.quota_lettere_continua = quota_lettere_continua
        self.min_prova = min_prova

    @staticmethod
    def norm(t: object) -> str:
        """Lower case, every run of non-word characters replaced by one space, stripped."""
        return _NORM.sub(' ', str(t or '').lower()).strip()

    # 1. readability
    def leggibile(self, testo: object) -> tuple[bool, float]:
        """``(readable, share)``: the share of tokens that look like words of a language.

        Space-less scripts (CJK, Thai, Lao, Khmer, Burmese) are measured on characters: readable if at least 60% of
        the non-space characters are letters and there are at least 200 of them. Otherwise tokens made only of
        punctuation do not count; a Latin token is a word with at least three letters and a vowel; a non-Latin token
        (code point >= U+0370) is a word with at least two letters (or one East Asian character).
        """
        testo = str(testo or '')
        car = [c for c in testo if not c.isspace()]
        continua = sum(1 for c in car if c.isalpha() and _senza_spazi_tra_parole(c))
        if car and continua / len(car) > self.soglia_scrittura_continua:
            return self._leggibile_per_caratteri(car)
        tok = [t for t in _SPAZI.split(testo) if t and _ALFANUMERICO.search(t)]
        if len(tok) < self.min_parole:
            return False, 0.0
        parole = sum(1 for t in tok if self._e_parola(t))
        quota = parole / len(tok)
        return quota >= self.soglia_leggibile, round(quota, 3)

    def _leggibile_per_caratteri(self, car: list[str]) -> tuple[bool, float]:
        lett = sum(1 for c in car if c.isalpha())
        quota = lett / len(car)
        return (len(car) >= self.min_caratteri_continua and quota >= self.quota_lettere_continua), round(quota, 3)

    @staticmethod
    def _e_parola(token: str) -> bool:
        s = _NON_PAROLA.sub('', token)
        if not s.isalpha() or len(s) > 25:
            return False
        if any(ord(ch) >= 0x0370 for ch in s):
            # non-Latin scripts; single scattered letters (one Cyrillic letter at a time) are encoding garbage
            return len(s) >= 2 or ord(s[0]) > 0x2E7F
        return len(s) >= 3 and bool(_VOCALI.search(s))

    # 2. evidence in the page
    def prova_trovata(self, prova: object, testo_pagina: object) -> bool:
        """True if the first characters of the normalised evidence are in the normalised page.

        In Japanese, Chinese and Korean line breaks fall inside words and OCR adds spaces around numbers, so there the
        comparison ignores spaces.
        """
        p = self.norm(prova)
        if len(p) < self.min_prova:
            return False
        if _CJK.search(p):
            return p.replace(' ', '')[: self.lunghezza_confronto] in self.norm(testo_pagina).replace(' ', '')
        return p[: self.lunghezza_confronto] in self.norm(testo_pagina)

    # 3. evidence copied from the prompt
    def prova_dal_prompt(self, prova: object, testi_prompt: Iterable[str] | None) -> bool:
        """True if the evidence matches (or is contained in) one of the texts that were in the prompt."""
        p = self.norm(prova)
        if len(p) < self.min_prova:
            return False
        return any(p[: self.lunghezza_confronto] in self.norm(t) for t in (testi_prompt or []) if t)

    # 4. outcome
    def verifica(self, prova: object, testo_pagina: object, testi_prompt: Iterable[str] | None = ()) -> str:
        """Outcome of a piece of evidence: ``'trovata'`` | ``'inventata'`` | ``'non trovata'`` | ``'assente'``.

        ``trovata`` (found in the page), ``inventata`` (copied from the prompt), ``non trovata`` (not found),
        ``assente`` (missing or shorter than 20 normalised characters).
        """
        if not prova or len(self.norm(prova)) < self.min_prova:
            return 'assente'
        if self.prova_trovata(prova, testo_pagina):
            return 'trovata'
        if self.prova_dal_prompt(prova, testi_prompt):
            return 'inventata'
        return 'non trovata'


FRENI = Freni()
"""The brakes with the live thresholds."""
