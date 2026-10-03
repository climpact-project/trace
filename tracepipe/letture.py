"""DeepSeek readings (``letture``, Italian for readings) and the parsing of their answers.

A reading is the JSON object the model writes, as the readers save it in ``letture`` of a reading file. Its fields
depend on the reading version: the citation type (L02/L03: ``riferimento``, ``tipo_citazione``, ``chi_parla``,
``proposizione``, ``motivo``), the principles (L04: ``principi``, ``altro``, ``motivo``, ``vicine``), the uptake with
the dossier (L05: also ``frase_sostenuta``). An answer that cannot be parsed is saved as
``{'esito': 'ILLEGGIBILE', 'grezzo': <first 200 characters>}``; a tolerant parse that rebuilt the fields one by one adds
``recuperata: True`` and keeps up to 2,000 characters of raw text.

:func:`estrai` is ``tools/giudica_llm.estrai``; :func:`estrai_tollerante` is ``tools/classifica_lessicali.
estrai_tollerante`` with the fix of 02/10/2026 (recovery on the full text, not on the 200-character ``grezzo``).
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from typing import Any

LETTURE_PROTOCOLLO = 5
"""Readings per row of the measured protocol (R11, 02/10/2026: ``training/misure/GIRI-E-DOMANDA.md``, 5 is the first k
whose Krippendorff alpha between two independent majorities passes 0.80). The default of ``--letture`` since
03/10/2026 (it was 2, the old two-reading agreement)."""

ILLEGGIBILE = 'ILLEGGIBILE'
"""The ``esito`` of an answer that could not be parsed (Italian: unreadable)."""

CAMPI = ('riferimento', 'tipo_citazione', 'chi_parla', 'proposizione', 'motivo')
"""Fields recovered one by one by :func:`estrai_tollerante` (tools/classifica_lessicali.py CAMPI)."""

_OGGETTO = re.compile(r'\{.*\}', re.S)
_CAMPO = {k: re.compile(rf'"{k}"\s*:\s*"([^"]*)"') for k in CAMPI}


def estrai(testo: str) -> Any:
    """The first-to-last brace span of ``testo`` parsed as JSON, or the unreadable marker.

    Same as ``tools/giudica_llm.estrai``: greedy match from the first ``{`` to the last ``}``; if there is none, or it
    is not valid JSON, ``{'esito': 'ILLEGGIBILE', 'grezzo': <200 characters>}``.
    """
    m = _OGGETTO.search(testo)
    if not m:
        return {'esito': ILLEGGIBILE, 'grezzo': testo[:200]}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {'esito': ILLEGGIBILE, 'grezzo': m.group(0)[:200]}


def estrai_tollerante(testo: str) -> Any:
    """Parse the JSON; if it does not parse, rebuild the fields of :data:`CAMPI` one by one.

    DeepSeek's JSON breaks when the proposition contains unescaped quotes (12 readings out of 684 on 26/09/2026).
    The recovered reading is marked ``recuperata`` and keeps ``grezzo`` (up to 2,000 characters). Recovery needs at
    least ``tipo_citazione``; otherwise the unreadable marker of :func:`estrai` is returned. Since 02/10/2026 the
    recovery reads the full text, not the 200-character ``grezzo`` of :func:`estrai` (the recovered readings were
    losing ``proposizione`` and ``motivo``, which come after the type).
    """
    g = estrai(testo)
    if g.get('esito') != ILLEGGIBILE:
        return g
    grezzo = testo or g.get('grezzo') or ''
    r = {k: m.group(1) for k in CAMPI for m in [_CAMPO[k].search(grezzo)] if m}
    return {**r, 'recuperata': True, 'grezzo': grezzo[:2000]} if r.get('tipo_citazione') else g


def vero(x: Any) -> bool:
    """A yes/no of a reading, read strictly (03/10/2026, external review): ``True``, the string ``"true"`` (case and
    spaces aside) or the integer ``1`` is yes; anything else, the string ``"false"`` included, is no.

    ``bool()`` made the non-empty string ``"false"`` a yes. Same as ``tools/maggioranza.vero``. In the saved readings
    of 03/10/2026: 197,892 booleans and 2 strings ``"true"``, no ``"false"``: no past proposal changes.
    """
    if x is True:
        return True
    if isinstance(x, str):
        return x.strip().lower() == 'true'
    return type(x) is int and x == 1


def vuota(lettura: Any) -> bool:
    """A reading saved without an answer: the mark left by :func:`estrai_tollerante` on an empty text.

    Same as ``tools/chiamata_deepseek.vuota``.
    """
    return isinstance(lettura, dict) and 'grezzo' in lettura and not str(lettura.get('grezzo') or '').strip()


@dataclass(frozen=True)
class Lettura:
    """One reading of one row, as saved by the readers (``lettura``: a reading).

    The object wraps the saved dict without changing it: :meth:`come_dict` returns exactly what the live readers
    write, so a reading can go through this class and back unchanged.

    Attributes:
        dati: the parsed answer (or the unreadable marker).
    """

    dati: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def da_testo(cls, testo: str, tollerante: bool = True) -> Lettura:
        """Parse a model answer (tolerant by default, as every reader since 26/09/2026)."""
        x = estrai_tollerante(testo) if tollerante else estrai(testo)
        return cls(x if isinstance(x, dict) else {'valore': x})

    @classmethod
    def da_dict(cls, x: Any) -> Lettura:
        """Wrap a saved reading; a non-dict (a broken line) becomes an empty reading, as the composition treats it."""
        return cls(x if isinstance(x, dict) else {})

    def come_dict(self) -> dict[str, Any]:
        """A deep copy of the saved dict."""
        return copy.deepcopy(self.dati)

    @property
    def illeggibile(self) -> bool:
        """True if the answer could not be parsed (and was not recovered)."""
        return self.dati.get('esito') == ILLEGGIBILE

    @property
    def recuperata(self) -> bool:
        """True if the fields were rebuilt one by one from a broken JSON."""
        return bool(self.dati.get('recuperata'))

    @property
    def grezzo(self) -> str | None:
        """The raw text kept with an unreadable or recovered reading."""
        return self.dati.get('grezzo')

    @property
    def vuota(self) -> bool:
        """True if the reading was saved without an answer (see :func:`vuota`)."""
        return vuota(self.dati)

    @property
    def principi(self) -> list[str]:
        """The principle ids of an L04/L05 reading (only the strings, as the composition reads them)."""
        return [p for p in (self.dati.get('principi') or []) if isinstance(p, str)]

    @property
    def tipo_citazione(self) -> str | None:
        """The citation type of an L02/L03 reading."""
        return self.dati.get('tipo_citazione')
