"""R11, the majority composition of the five readings (``maggioranza``: majority), twin of ``tools/maggioranza.py``.

Approved by the PI on 02/10/2026; measure ``training/misure/GIRI-E-DOMANDA.md``: with 5 readings per row Krippendorff's
alpha between two independent majorities is 0.83 on the principles (L05) and 0.83 on the type, against 0.66 and 0.67
with one reading; 5 is the first k above 0.80, all cases together.

- **Type**: the most voted codebook type among the valid readings. **Ties** (2-2-1, 1-1-1-1-1): among the tied types,
  the one that appears first in reading order (reading 1, then 2, ...): fixed, repeatable. Margin = votes of the first
  minus votes of the second; the decision is *uncertain* when the margin is at most 1 (the definition of the measure),
  so a tie always is. Speaker, proposition and reason come from the first reading that gave the winning type.
- **Principles** (L05): every valid reading (not empty, readable, with a non-empty principle list) votes the set of
  principles it takes (case codes, "altro" with its sentence; "nessuno" when none). A principle is proposed when the
  majority of the valid readings votes it: at least 3 of 5 (3 of 4, 2 of 3, ...). Votes are recorded for every
  principle voted at least once ("4/5"); a decision is uncertain when ``|2v - n| <= 1``. If no principle reaches the
  majority: "nessuno" (as in the measure). As in R05: paragraph-map principles, "nessuno" for a chain mention (here the
  majority type), reranker hints among the sources.
- **Surrounding pages**: a page follows when the majority of the valid readings says so and the evidence of at least
  one of those readings is really in the page (the brake of 30/09 stays a filter on pages); its principle is the most
  voted among the readings that say yes.
- **Supported sentence**: from the first reading whose principle set equals the majority set, otherwise from the first
  reading with a sentence; checked with the brakes as today.
- **Missing evidence**: a principle proposed by the reading alone (not by a paragraph) has evidence when the supported
  sentence is found in the page, or when a ticked surrounding page on that principle has its evidence found. Without
  evidence the principle is NOT dropped (the measure: dropping does not improve agreement with people and lowers
  recall): it stays, flagged ``proposto_prova_mancante`` with the list of principles without evidence.
"""

from __future__ import annotations

import collections
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .letture import vero as vero  # re-exported: the strict yes/no of the page votes
from .letture import vuota

CATEGORIE_ORDINE = ('menzione_in_catena', 'descrittiva', 'sostanziale', 'distinguente', 'critica', 'implicita')
NESSUNO, ALTRO = 'nessuno', 'altro'


def valida(y: Any) -> bool:
    """A reading that is an answer: read (not empty) and not unreadable."""
    return isinstance(y, dict) and not vuota(y) and y.get('esito') != 'ILLEGGIBILE'


def soglia(n: int) -> int:
    """The majority of ``n`` valid readings: 3 of 5, 3 of 4, 2 of 3, 2 of 2, 1 of 1."""
    return n // 2 + 1


def incerta(v: int, n: int) -> bool:
    """A yes/no decision with ``v`` votes of ``n`` is uncertain when the margin is at most 1."""
    return abs(2 * v - n) <= 1


def voti_testo(v: int, n: int) -> str:
    return f'{v}/{n}'


def voto_tipo(letture: Sequence[Any]) -> dict[str, Any] | None:
    """The majority type, or ``None`` when no reading gives a codebook type."""
    valide = [(k, y) for k, y in enumerate(letture or []) if valida(y) and y.get('tipo_citazione') in CATEGORIE_ORDINE]
    if not valide:
        return None
    voti = collections.Counter(y['tipo_citazione'] for _, y in valide)
    ordine: list[str] = []
    for _, y in valide:
        if y['tipo_citazione'] not in ordine:
            ordine.append(y['tipo_citazione'])
    alto = max(voti.values())
    pari = [t for t in ordine if voti[t] == alto]
    tipo = pari[0]
    secondo = max([v for t, v in voti.items() if t != tipo] or [0])
    margine = alto - secondo
    k, rapp = next((k, y) for k, y in valide if y['tipo_citazione'] == tipo)
    return {
        'tipo': tipo,
        'n': len(valide),
        'voti': {t: voti[t] for t in sorted(ordine, key=lambda t: (-voti[t], ordine.index(t)))},
        'margine': margine,
        'parita': len(pari) > 1,
        'incerto': margine <= 1,
        'lettura': rapp,
        'indice': k,
    }


def principi_lettura(y: Mapping[str, Any], canonico: Callable[[str], str]) -> list[str]:
    """The codes an L05 reading takes, canonical; a string is split on commas and semicolons."""
    pr = y.get('principi') or []
    if isinstance(pr, str):
        pr = [q.strip() for q in re.split(r'[,;]', pr) if q.strip()]
    return [canonico(q) for q in pr if isinstance(q, str) and q]


def insieme(y: Mapping[str, Any], ids: Sequence[str], canonico: Callable[[str], str]) -> list[str]:
    """The set a reading votes: its case principles, "altro" when said with a sentence, else "nessuno"."""
    lett = principi_lettura(y, canonico)
    s = [p for p in ids if p in lett]
    if ALTRO in lett and ' '.join(str(y.get('altro') or '').split()):
        s.append(ALTRO)
    return s or [NESSUNO]


def voto_principi(letture: Sequence[Any], ids: Sequence[str], canonico: Callable[[str], str]) -> dict[str, Any] | None:
    """The votes of the valid L05 readings; ``None`` when there is none (an empty list is not an answer, R05)."""
    valide = [(k, y) for k, y in enumerate(letture or []) if valida(y) and principi_lettura(y, canonico)]
    n = len(valide)
    if not n:
        return None
    insiemi = [(k, y, insieme(y, ids, canonico)) for k, y in valide]
    voti = collections.Counter(p for _, _, s in insiemi for p in s)
    t = soglia(n)
    presi = [p for p in ids if voti[p] >= t] + ([ALTRO] if voti[ALTRO] >= t else [])
    ordine = [p for p in ids if voti[p]] + [p for p in (ALTRO, NESSUNO) if voti[p]]
    return {
        'n': n,
        'soglia': t,
        'insiemi': insiemi,
        'voti': {p: voti[p] for p in ordine},
        'maggioranza': presi or [NESSUNO],
        'incerti': [p for p in ordine if incerta(voti[p], n)],
    }


def _con_frase(y: Mapping[str, Any]) -> bool:
    return bool(' '.join(str(y.get('frase_sostenuta') or '').split()))


def lettura_scelta(vp: Mapping[str, Any]) -> Mapping[str, Any]:
    """Where reason and "altro" come from: the first reading with the majority set, else the first with a sentence,
    else the first valid one."""
    for _, y, s in vp['insiemi']:
        if sorted(s) == sorted(vp['maggioranza']):
            return y
    for _, y, _ in vp['insiemi']:
        if _con_frase(y):
            return y
    return vp['insiemi'][0][1]


def frase_scelta(vp: Mapping[str, Any]) -> Mapping[str, Any]:
    """The supported sentence: first reading with the majority set and a sentence, else the first with a sentence."""
    for _, y, s in vp['insiemi']:
        if sorted(s) == sorted(vp['maggioranza']) and _con_frase(y):
            return y
    for _, y, _ in vp['insiemi']:
        if _con_frase(y):
            return y
    return {}


def voto_pagine(vp: Mapping[str, Any]) -> dict[int, list[tuple[int, Mapping[str, Any]]]]:
    """For every judged page: ``[(reading index, entry)]`` of the valid readings, in order (first entry per page)."""
    out: dict[int, list[tuple[int, Mapping[str, Any]]]] = collections.defaultdict(list)
    for k, y, _ in vp['insiemi']:
        visti: set[int] = set()
        for v in y.get('vicine') if isinstance(y.get('vicine'), list) else []:
            if not isinstance(v, dict):
                continue
            try:
                n = int(v.get('pagina'))
            except (TypeError, ValueError):
                continue
            if n in visti:
                continue
            visti.add(n)
            out[n].append((k, v))
    return out
