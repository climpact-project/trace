"""Paths, case list, probe series and thresholds of the TRACE pipeline.

Every constant here mirrors a live script in ``tools/``; the source is named next to each one. The live scripts
compute the root from their own location (``Path(__file__).resolve().parent.parent``); :class:`Config` does the same
by default, and can be pointed at another root (the test harness uses ``prove/campione``).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

# The six cited cases of the pipeline (prove/esegui_riferimento.py CASI).
CASI: tuple[str, ...] = (
    'urgenda',
    'neubauer',
    'future-generations',
    'klimaseniorinnen',
    'cig-parere-clima',
    'idh-oc-32-25',
)

# tools/sonde.py SERIE_IN_USO: the probe series in use per case when TRACE_SONDE is not set.
SERIE_IN_USO: Mapping[str, str] = MappingProxyType(
    {'neubauer': 'P05', 'future-generations': 'P05', 'cig-parere-clima': 'P09'}
)
# tools/sonde.py STORICHE: historical series, whose derived files carry no suffix.
STORICHE: frozenset[str] = frozenset({'P01', 'P02'})
# tools/sonde.py PRIMA_SERIE: the first series of each case, the one of the files without suffix.
PRIMA_SERIE: Mapping[str, str] = MappingProxyType(
    {
        'urgenda': 'P01',
        'neubauer': 'P02',
        'future-generations': 'P02',
        'klimaseniorinnen': 'P06',
        'cig-parere-clima': 'P07',
        'idh-oc-32-25': 'P08',
    }
)


class SerieMancanteError(SystemExit):
    """The requested probe series has no ``cited-cases/<case>-<series>.yaml`` file.

    A subclass of ``SystemExit`` because the live ``tools/sonde.serie`` stops the program with that exception.
    """


@dataclass(frozen=True)
class SoglieFinestra:
    """Window of the surrounding pages (tools/leggi_ripresa.py, rule R08 of 01/10/2026).

    The follow-up of an uptake is searched up to ``larga`` pages on each side of the citation page. Within the near
    band (from 2 pages before to 3 after) a page qualifies with a reranker score >= ``soglia_vicina``; farther away
    it needs ``soglia_lontana``. At most ``max_vicine_larga`` pages are kept, and each page text is cut at
    ``taglio_vicina`` characters before it reaches the model.
    """

    larga: int = 10
    soglia_vicina: float = 0.5
    soglia_lontana: float = 0.8
    max_vicine: int = 3  # MAX_VICINE: the old narrow window, still defined but unused by R08
    max_vicine_larga: int | None = 5
    banda_vicina: tuple[int, int] = (-2, 3)
    taglio_vicina: int = 3500
    regola: str = 'R08'

    @classmethod
    def per_regola(cls, regola: str = 'R08') -> SoglieFinestra:
        """The window of a rule: ``R08`` (above) or ``R10``.

        R10 (02/10/2026, with the PI's yes; measure ``training/misure/PERDITE-PAGINE-ATTORNO.md``): threshold 0.5 at
        every distance within +-10 pages and no cap. Measured recall within +-10 goes from 27% (R08) to 57%, at 4.6
        pages read per citation instead of 2.0.
        """
        if regola == 'R08':
            return cls()
        if regola == 'R10':
            return cls(soglia_lontana=0.5, max_vicine_larga=None, regola='R10')
        raise ValueError(f'unknown window rule: {regola}')

    def vicina(self, distanza: int) -> bool:
        """True if ``distanza`` (page minus citation page) lies in the near band."""
        return self.banda_vicina[0] <= distanza <= self.banda_vicina[1]

    def soglia(self, distanza: int) -> float:
        """The reranker threshold that applies at ``distanza`` pages from the citation."""
        return self.soglia_vicina if self.vicina(distanza) else self.soglia_lontana


@dataclass(frozen=True)
class LimitiDeepSeek:
    """Caps of a DeepSeek call (tools/chiamata_deepseek.py, 02/10/2026).

    ``tetto`` is the answer cap of the L03/L04/L05 readings; after ``tentativi`` identical attempts that still end with
    ``finish_reason == 'length'`` one last attempt uses ``tetto_alto``, never beyond the room left in the vLLM context
    (``contesto`` minus the prompt tokens minus ``margine``). Network errors are retried ``errori_rete`` times per
    attempt, sleeping ``pausa_rete_s * (n + 1)`` seconds.
    """

    tetto: int = 8000
    tetto_alto: int = 16000
    contesto: int = 65536
    margine: int = 512
    tentativi: int = 3
    errori_rete: int = 5
    pausa_rete_s: float = 5.0


@dataclass(frozen=True)
class Config:
    """Where the pipeline reads and writes, and which probe series it uses.

    Attributes:
        radice: the project root (``~/sabin-corpus``, or a copy such as ``prove/campione/lavoro``).
        trace_sonde: the value of the ``TRACE_SONDE`` environment variable (a probe series on trial); empty means
            the series in use (:data:`SERIE_IN_USO`).
        casi: the cited cases.
        finestra: thresholds of the surrounding-pages window.
        deepseek: caps of a DeepSeek call.
        soglia_reranker: brano score at which the reranker is listed as a source of a principle
            (tools/carica_ripresa.py SOGLIA_RERANKER).
    """

    radice: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    trace_sonde: str = ''
    casi: tuple[str, ...] = CASI
    serie_in_uso: Mapping[str, str] = SERIE_IN_USO
    storiche: frozenset[str] = STORICHE
    prima_serie: Mapping[str, str] = PRIMA_SERIE
    finestra: SoglieFinestra = field(default_factory=SoglieFinestra)
    deepseek: LimitiDeepSeek = field(default_factory=LimitiDeepSeek)
    soglia_reranker: float = 0.5

    @classmethod
    def da_ambiente(cls, radice: Path | str | None = None) -> Config:
        """A configuration that reads ``TRACE_SONDE`` from the environment, like the live scripts."""
        kw = {'radice': Path(radice).resolve()} if radice is not None else {}
        return cls(trace_sonde=os.environ.get('TRACE_SONDE', ''), **kw)

    # paths
    @property
    def training(self) -> Path:
        """``training/``: rows, readings, scores."""
        return self.radice / 'training'

    @property
    def principi(self) -> Path:
        """``training/principi/``: everything about uptakes and principles."""
        return self.training / 'principi'

    @property
    def index(self) -> Path:
        """``index/``."""
        return self.radice / 'index'

    @property
    def indice_pagine(self) -> Path:
        """``index/pagine/pagine.jsonl.gz``: one JSON line per page of the corpus."""
        return self.index / 'pagine' / 'pagine.jsonl.gz'

    @property
    def cited_cases(self) -> Path:
        """``cited-cases/``: case files, probe series, paragraph maps, dossiers."""
        return self.radice / 'cited-cases'

    @property
    def markdown(self) -> Path:
        """``markdown/``: the documents as markdown with page marks."""
        return self.radice / 'markdown'

    @property
    def pagine_sostituite(self) -> Path:
        """``training/ocr/pagine_sostituite.json``: pages replaced by OCR (corpus D02)."""
        return self.training / 'ocr' / 'pagine_sostituite.json'

    # probe series (tools/sonde.py)
    def serie(self, caso: str | None = None) -> str:
        """The probe series of ``caso``: ``TRACE_SONDE`` if set, else the series in use, else ``''``.

        Raises:
            SerieMancanteError: the series file ``cited-cases/<caso>-<series>.yaml`` does not exist.
        """
        s = self.trace_sonde or (self.serie_in_uso.get(caso, '') if caso else '')
        if s and caso and not (self.cited_cases / f'{caso}-{s}.yaml').exists():
            raise SerieMancanteError(f'TRACE_SONDE={s}: manca cited-cases/{caso}-{s}.yaml')
        return s

    def suf(self, caso: str | None = None) -> str:
        """File suffix of the derived files of the series (``'_P05'``), empty for historical series."""
        s = self.serie(caso)
        return f'_{s}' if s and s not in self.storiche else ''

    def storica(self, caso: str | None = None) -> bool:
        """True if the chosen series is historical (derived files without suffix, earlier readings)."""
        return self.serie(caso) in ('',) or self.serie(caso) in self.storiche

    def codice(self, caso: str) -> str:
        """The register code of the series (``P01``...``P09``)."""
        return self.serie(caso) or self.prima_serie.get(caso, 'P02')

    def file_caso(self, caso: str) -> Path:
        """The case file carrying the probes of the series."""
        s = self.serie(caso)
        return self.cited_cases / (f'{caso}-{s}.yaml' if s else f'{caso}.yaml')

    def file_fascicolo(self, caso: str) -> Path:
        """The case dossier of the series, falling back to the base dossier."""
        s = self.serie(caso)
        f = self.cited_cases / f'{caso}-fascicolo-{s}.md'
        return f if s and f.exists() else self.cited_cases / f'{caso}-fascicolo.md'

    def codice_mappa(self, caso: str) -> str:
        """Register code of the paragraph map used for ``caso`` (tools/carica_ripresa.py ``main``)."""
        return {'P03': 'R06', 'P05': 'R07'}.get(self.serie(caso)) or {
            'klimaseniorinnen': 'R09',
            'cig-parere-clima': 'R09',
            'idh-oc-32-25': 'R09',
        }.get(caso, 'R04')
