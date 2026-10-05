"""The surrounding pages of an uptake (``pagine attorno``), rules R08 and R10 (``tools/leggi_ripresa.py`` ``prepara``).

For every lexical citation row DeepSeek receives, besides the citation page, up to five pages of the same filing
that the TRACE-Reranker (T01) finds close to a principle of the cited case: the possible follow-up of the uptake.

R08 (01/10/2026, measured with ``misura_finestra.py``, §63.28): the follow-up is searched up to 10 pages on each
side. Near the citation (from 2 pages before to 3 after) a page qualifies with a best score >= 0.5; farther away it
needs 0.8, the threshold at which the reading of the sample found a true follow-up in more than half of the cases.
At most 5 pages, the best ones (ties broken by the higher page number). A page with no real words (the first
brake, :meth:`tracepipe.freni.Freni.leggibile`) never reaches the model: it is listed in ``vicine_illeggibili``.

R10 (02/10/2026, ``prepara --regola R10``, always into a labelled file): 0.5 at every distance within +-10, no cap
(:meth:`tracepipe.config.SoglieFinestra.per_regola`).
"""

from __future__ import annotations

import collections
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import TETTO_PAGINA, Config, SoglieFinestra
from .corpus import IndicePagine, Pagina
from .freni import FRENI, Freni

Candidata = tuple[float, int, str]
"""A candidate page: (best reranker score, page number, page id)."""


def numero_pagina(valore: Any) -> int | None:
    """The citation page of a row as a positive number, ``None`` when missing, zero or not a number."""
    try:
        n = int(valore or 0)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def leggi_jsonl(percorso: Path) -> list[dict[str, Any]]:
    """Every line of a JSONL file (blank lines are not expected: the live readers do not skip them)."""
    with open(percorso, encoding='utf-8') as f:
        return [json.loads(riga) for riga in f]


def per_id(percorso: Path) -> dict[str, dict[str, Any]]:
    """A JSONL file as ``{id: line}``; the last line of an id wins."""
    return {x['id']: x for x in leggi_jsonl(percorso)}


@dataclass
class Punteggi:
    """Reranker (T01) scores of a case (``punteggi``: scores).

    Attributes:
        brano: ``{row id: {principle: score}}`` for the flagged passage of each row.
        vicina: ``{page id: {principle: score}}`` for the pages of the filings.
    """

    brano: dict[str, dict[str, float]] = field(default_factory=lambda: collections.defaultdict(dict))
    vicina: dict[str, dict[str, float]] = field(default_factory=lambda: collections.defaultdict(dict))

    @classmethod
    def da_file(cls, files: Iterable[Path]) -> Punteggi:
        """Read score files in order: a later file overwrites the same (row or page, principle)."""
        p = cls()
        for f in files:
            with open(f, encoding='utf-8') as h:
                for riga in h:
                    x = json.loads(riga)
                    if x['dove'] == 'brano':
                        p.brano[x['riga']][x['principio']] = x['punteggio']
                    else:
                        p.vicina[x['pagina_id']][x['principio']] = x['punteggio']
        return p

    @staticmethod
    def file_finestra(config: Config, caso: str) -> list[Path]:
        """The score files read by the window selection, OCR scores last.

        Historical series: the passage and page scores plus the whole-window scores (``_finestra_punteggi_``); a series
        on trial: only its own scores. The scores on the OCR text (01/10/2026) come last: they replace those given to
        the same unreadable pages.
        """
        cartella = config.principi
        if config.storica(caso):
            tutti = sorted(cartella.glob(f'{caso}_punteggi_*.jsonl')) + sorted(
                cartella.glob(f'{caso}_finestra_punteggi_*.jsonl')
            )
        else:
            tutti = sorted(cartella.glob(f'{caso}{config.suf(caso)}_punteggi_*.jsonl'))
        return [f for f in tutti if '_ocr' not in f.name] + [f for f in tutti if '_ocr' in f.name]


class SceltaPagineAttorno:
    """Choice of the surrounding pages, R08 (``scelta``: choice).

    Args:
        punteggi: the reranker scores of the case.
        soglie: the window thresholds.
        freni: the brakes (readability check).
        compat: reproduce the live behaviour on rows without a page number (see :meth:`candidate`). ``False`` (the
            default) is the fixed behaviour decided on 02/10/2026; the harness runs with ``True``.
    """

    REGOLA = 'R08'
    """The rule of the default window (``soglie.regola`` says which one is in use)."""

    def __init__(
        self, punteggi: Punteggi, soglie: SoglieFinestra | None = None, freni: Freni = FRENI, compat: bool = False
    ) -> None:
        self.punteggi = punteggi
        self.soglie = soglie or SoglieFinestra()
        self.freni = freni
        self.compat = compat

    @classmethod
    def per_caso(cls, config: Config, caso: str, compat: bool = False, regola: str = 'R08') -> SceltaPagineAttorno:
        """The selection with the score files of ``caso`` (``regola``: R08, the window of the config, or R10)."""
        soglie = config.finestra if regola == 'R08' else SoglieFinestra.per_regola(regola)
        return cls(Punteggi.da_file(Punteggi.file_finestra(config, caso)), soglie, compat=compat)

    @staticmethod
    def file_uscita(config: Config, caso: str, etichetta: str = '') -> Path:
        """``training/principi/<caso>_ripresa_righe<suf>.jsonl``, or ``<caso>_ripresa_righe_<etichetta>.jsonl`` (the
        rows the reader reads with ``--etichetta``)."""
        if etichetta:
            return config.principi / f'{caso}_ripresa_righe_{etichetta}.jsonl'
        return config.principi / f'{caso}_ripresa_righe{config.suf(caso)}.jsonl'

    def candidate(self, riga: Mapping[str, Any]) -> list[Candidata]:
        """The chosen pages of one row, best first.

        Every page from ``larga`` before to ``larga`` after the citation page (not the page itself, not page 0 or
        below) that has scores qualifies if its best score reaches the threshold of its distance. A row without a
        page number has no window (fixed on 02/10/2026; see ``compat``).
        """
        s = self.soglie
        if self.compat:
            # NOTE(bug): live, a row without a page number gets p = 0, so pages 1-10 of the filing are searched as if
            # the citation were on page 0 (pages 1-3 even with the near threshold). Reproduced with compat=True.
            p = int(riga.get('pagina') or 0)
        else:
            q = numero_pagina(riga.get('pagina'))
            if q is None:
                return []
            p = q
        cand: list[Candidata] = []
        for k in range(p - s.larga, p + s.larga + 1):
            pid = Pagina.id_di(riga['document_id'], k)
            if k != p and k > 0 and pid in self.punteggi.vicina:
                m = max(self.punteggi.vicina[pid].values())
                if m >= s.soglia(k - p):
                    cand.append((m, k, pid))
        return sorted(cand, reverse=True)[: s.max_vicine_larga]

    def scegli(self, righe: Iterable[Mapping[str, Any]]) -> dict[str, list[Candidata]]:
        """The candidates of every row, by row id."""
        return {r['id']: self.candidate(r) for r in righe}

    def riga_uscita(
        self,
        r: Mapping[str, Any],
        cand: list[Candidata],
        par: Mapping[str, Mapping[str, Any]],
        testi: Mapping[str, str],
    ) -> dict[str, Any]:
        """The output line of one row, in the key order of the live file."""
        in_ordine = sorted(cand, key=lambda c: c[1])
        leggibili = {pid: self.freni.leggibile(testi.get(pid, ''))[0] for _, _, pid in in_ordine}
        return {
            'id': r['id'],
            'document_id': r['document_id'],
            'case_name': r.get('case_name'),
            'tipo_atto': r.get('tipo_atto'),
            'data': r.get('data'),
            'pagina': r.get('pagina'),
            'forma': r.get('forma'),
            'contesto': r['contesto'],
            'principi_paragrafi': par.get(r['id'], {}).get('principi', []),
            'paragrafi': par.get(r['id'], {}).get('paragrafi', []),
            'punteggi_brano': self.punteggi.brano.get(r['id'], {}),
            'vicine': [
                {
                    'pagina': k,
                    'punteggi': self.punteggi.vicina[pid],
                    'testo': testi.get(pid, '')[: self.soglie.taglio_vicina or TETTO_PAGINA],
                }
                for _, k, pid in in_ordine
                if leggibili[pid]
            ],
            'vicine_illeggibili': [k for _, k, pid in in_ordine if not leggibili[pid]],
        }

    def prepara(
        self, righe: list[Mapping[str, Any]], par: Mapping[str, Mapping[str, Any]], indice: IndicePagine
    ) -> tuple[list[dict[str, Any]], collections.Counter[str]]:
        """Output lines for every row and the counts printed by the live script.

        Args:
            righe: the lexical rows (``training/lessicali_<caso>_righe.jsonl``).
            par: the paragraph-map lines by row id (``<caso>_da_paragrafi<suf>.jsonl``).
            indice: the page index, read once for the chosen pages.
        """
        scelte = self.scegli(righe)
        serve = {c[2] for cand in scelte.values() for c in cand}
        testi = indice.testi(serve)
        n: collections.Counter[str] = collections.Counter()
        out = []
        for r in righe:
            cand = scelte[r['id']]
            n['con pagine vicine' if cand else 'senza pagine vicine'] += 1
            out.append(self.riga_uscita(r, cand, par, testi))
        return out, n

    @classmethod
    def prepara_caso(
        cls, config: Config, caso: str, compat: bool = False, regola: str = 'R08'
    ) -> tuple[list[dict[str, Any]], collections.Counter[str]]:
        """``prepara`` on the files of ``caso`` under ``config.radice`` (reads only; writing is the caller's)."""
        righe = leggi_jsonl(config.training / f'lessicali_{caso}_righe.jsonl')
        par = per_id(config.principi / f'{caso}_da_paragrafi{config.suf(caso)}.jsonl')
        return cls.per_caso(config, caso, compat, regola).prepara(righe, par, IndicePagine(config.indice_pagine))
