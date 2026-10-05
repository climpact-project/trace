"""What the clean-up steps (C03, C07, S08) share about a row of ``corpus_rows`` (``righe``: rows).

Three small things every step needs: which networks count as a live row, whether the team already judged a row, and
the normal form in which two sentences are compared. They were repeated in ``tools/unisci_c03.py``,
``tools/controlli_automatici.py`` and ``tools/coppia_s08.py``; here they are written once.
"""

from __future__ import annotations

import functools
import re
import unicodedata
from collections.abc import Mapping
from pathlib import Path
from typing import Any

RETI_VIVE: tuple[str, ...] = ('lessicale', 'entrambe', 'descrittiva')
"""``proposto_rete`` of a row that counts: found by name, by name and meaning, or by description."""

NESSUN_PRINCIPIO = 'nessuno'
"""The «no principle» value of ``proposto_principi`` and ``validato_principi``."""

_NON_PAROLA = re.compile(r'[^\w]+')
_SPAZI = re.compile(r'\s+')

Riga = Mapping[str, Any]


@functools.lru_cache(maxsize=200_000)
def normalizza(testo: object) -> str:
    """Lower case, NFKC, every run of non-word characters replaced by one space, stripped.

    The comparison form of the supported sentences: ``unisci_c03.norm``, ``controlli_automatici._n`` and
    ``coppia_s08.norm`` of the live tools are this function.
    """
    s = unicodedata.normalize('NFKC', str(testo or '')).lower()
    return _SPAZI.sub(' ', _NON_PAROLA.sub(' ', s)).strip()


def e_viva(riga: Riga) -> bool:
    """True if the row is live: found by one of the three networks."""
    return riga.get('proposto_rete') in RETI_VIVE


def giudicata(riga: Riga) -> bool:
    """True if the team judged the row: a verdict (``esito``) or a September judgment (``settembre``)."""
    return bool(riga.get('esito') or riga.get('settembre'))


def giudizio(riga: Riga) -> str:
    """The judgment of the row as a word: the verdict, ``'settembre'`` or an empty string."""
    return str(riga.get('esito') or ('settembre' if riga.get('settembre') else ''))


def principi_di(riga: Riga) -> set[str]:
    """The principles of a row: the ones the team validated plus the proposed ones, without «nessuno»."""
    return (set(riga.get('validato_principi') or []) | set(riga.get('proposto_principi') or [])) - {NESSUN_PRINCIPIO}


def pagina_di_riga(riga: Riga) -> int | None:
    """The page of a row: validated by the team, else proposed, else the plain ``pagina`` field."""
    for chiave in ('validato_pagina', 'proposto_pagina', 'pagina'):
        try:
            return int(riga[chiave])
        except (KeyError, TypeError, ValueError):
            continue
    return None


def posizione_di_riga(riga: Riga) -> int | None:
    """``char_start`` of a row as an integer, ``None`` when it has none."""
    try:
        return int(riga['char_start'])
    except (KeyError, TypeError, ValueError):
        return None


class LettoreAtti:
    """The text of the filings (markdown files under the project root), read once and kept.

    ``tools/descrittiva_stretta.testo`` of the live tools: a missing file is an empty text, never an error.

    Args:
        radice: the project root; the ``file`` of a row is relative to it.
    """

    def __init__(self, radice: Path | str) -> None:
        self.radice = Path(radice)
        self._cache: dict[str, str] = {}

    def testo(self, file: str) -> str:
        """The whole text of the file, ``''`` if it does not exist."""
        if file not in self._cache:
            p = self.radice / file
            self._cache[file] = p.read_text(encoding='utf-8', errors='replace') if p.exists() else ''
        return self._cache[file]
