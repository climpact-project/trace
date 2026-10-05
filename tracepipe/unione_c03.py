"""C03: body text and its footnote, translations of the same filing, counted once (``unione_c03``).

Class-based version of ``tools/unisci_c03.py`` (4 and 5 October 2026). The same citation reaches the database twice
when it is found in the body text and again in the footnote that the same sentence calls, or in two translations of
the same filing. C03 keeps one row and marks the other as excluded; nothing is deleted.

The pairs
    ``testo_nota``  two live rows of the same case in the same filing, at most one page apart, that support the same
                    sentence (normalised, rapidfuzz ratio >= 95, at least 40 characters). TWO footnotes with the
                    same sentence stay apart: a pair is merged only if one of the two is in the body text. The body
                    text row is the one whose point (``char_start``) falls inside the supported sentence
                    (``proposto_frase_offset``), else the one with position «corpo», else the first.
    ``traduzione``  the same filing in another language of the same case (test 8 of ``descrittiva_stretta``). The
                    row in the ORIGINAL language of the filing stays. The test and the language recognition are not
                    part of the package: they come in through a :class:`RegolaTraduzioni`.

Two ways to get the pairs: :class:`GeneratoreCoppie` (the automatic rule) and :class:`CoppieRivedute` (the pairs read
by hand on 4 October: only what a person decided is written, the rule decides nothing; the automatic rule took the
wrong original language in 46 translations out of 105 because it read the first language of the header).

What is written (:meth:`UnioneC03.esegui` with ``scrivi``; the full copy first, if it cannot be read back nothing is
written)
    excluded row   ``proposto_rete`` ``'esclusa'``, ``esclusa_rete_prima``, ``esclusa_regola`` ``'C03'``,
                   ``unita_a`` (the kept code), ``esclusa_motivo``, ``esclusa_da``, ``esclusa_il``
    kept row       body/footnote: ``proposto_nota_appoggio`` ``{codice, testo, paragrafi}`` and the merged
                   ``proposto_paragrafi``; translation: ``proposto_traduzioni_unite`` (the codes); ``c03_da``,
                   ``c03_il`` (provenance)
A row that went out is put back with ``tools/rimetti_righe.py`` (it removes the ``esclusa_*`` fields; ``unita_a`` and
the support fields are removed by hand).

Rows judged by the team (verdict, or the September judgment) are never merged by the automatic rule: their pairs go to
``training/esclusioni/C03_giudicate_da_rivedere.tsv``.
"""

from __future__ import annotations

import collections
import csv
import datetime
import gzip
import json
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from rapidfuzz import fuzz

from .banca import ORA_DEL_SERVER, BancaDati, Scrittura
from .config import Config
from .copia_prima import CopiaPrima
from .righe import RETI_VIVE, Riga, giudicata, giudizio, normalizza

CODICE = 'C03'
"""The registry code of the rule."""
SOGLIA_FRASE = 95
"""Minimum rapidfuzz ratio for two supported sentences to be the same sentence."""
MIN_FRASE = 40
"""Minimum characters of a supported sentence to be compared."""
LINGUE: Mapping[str, str] = {
    'english': 'en',
    'german': 'de',
    'french': 'fr',
    'spanish': 'es',
    'portuguese': 'pt',
    'dutch': 'nl',
    'italian': 'it',
    'korean': 'ko',
    'japanese': 'ja',
    'chinese': 'zh',
}
"""The language names of a filing header and their codes."""
PARAGRAFI = re.compile(
    r'(?:para(?:s|graph)?s?\.?|¶¶?|§§?|Rn\.|Rdnr\.|par\.|r\.o\.)\s*(\d+(?:\.\d+)*(?:\s*[-\u2013]\s*\d+)?)',
    re.IGNORECASE,
)
"""A paragraph reference in the text of the excluded row."""
INTESTAZIONE_TSV = ['tipo', 'codice_tenuto', 'codice_che_esce', 'giudizio_tenuto', 'giudizio_che_esce', 'motivo']
"""The columns of the lists of pairs."""
CARTELLA_ELENCHI = ('training', 'esclusioni')

Stampa = Callable[[str], None]


def _stampa(testo: str) -> None:
    print(testo, flush=True)


@dataclass(frozen=True)
class CoppiaC03:
    """Two rows that are the same citation: the one that stays and the one that goes out.

    Attributes:
        tipo: ``'testo_nota'`` or ``'traduzione'``.
        tenuta: the row that stays.
        esce: the row marked as excluded.
        motivo: why, in words.
    """

    tipo: str
    tenuta: Riga
    esce: Riga
    motivo: str


class RegolaTraduzioni(Protocol):
    """What the automatic rule needs to find translations (test 8 of ``tools/descrittiva_stretta.py``).

    The package does not carry that test; a caller that has it passes an object with these four methods.
    """

    def prepara(self, banca: Mapping[str, Riga]) -> None:
        """Index the rows (by filing, by case) once before the search."""

    def codice_altra_riga(self, rid: str, riga: Riga) -> str | None:
        """The code of the row that is the same point in another language, ``None`` if there is none."""

    def lingua_del_testo(self, file: str) -> str | None:
        """The language recognised from the text of a file (``'en'``, ``'de'``...)."""

    def lingua_originale(self, riga: Riga) -> str | None:
        """The original language of the filing of the row, ``None`` when unknown."""


def lingua_dall_intestazione(testo: str) -> str | None:
    """The language code of the FIRST language of the ``lingue:`` line in the header of a filing, ``None`` if absent.

    It reads the first 6,000 characters. It is the rule that took the wrong original language in 46 of 105
    translations (the header puts English first): good for a guess, never to decide.
    """
    m = re.search(r"^lingue:\s*'?([^'\n]*)", testo[:6000], re.MULTILINE)
    prima = m.group(1).split(';')[0].strip().lower() if m else ''
    return LINGUE.get(prima)


def nel_testo(riga: Riga) -> bool:
    """True if the point of the row falls inside its supported sentence: the row is in the body text."""
    o = riga.get('proposto_frase_offset')
    try:
        return isinstance(o, list) and len(o) == 2 and int(o[0]) <= int(riga.get('char_start') or -1) <= int(o[1])
    except (TypeError, ValueError):
        return False


def chi_e_il_testo(x: Riga, y: Riga) -> tuple[Riga, Riga]:
    """``(body text row, footnote row)`` between two rows of the same citation."""
    if nel_testo(x) != nel_testo(y):
        return (x, y) if nel_testo(x) else (y, x)
    if (x.get('proposto_posizione') == 'corpo') != (y.get('proposto_posizione') == 'corpo'):
        return (x, y) if x.get('proposto_posizione') == 'corpo' else (y, x)
    return (x, y) if int(x.get('char_start') or 0) <= int(y.get('char_start') or 0) else (y, x)


def appoggio(tenuta: Riga, esce: Riga) -> dict[str, Any]:
    """The support the kept row receives from the excluded one: its code, its text (1,200 characters) and the paragraphs
    it cites (looked for in the first 1,500 characters)."""
    testo = esce.get('proposto_citazione_testuale') or esce.get('finestra_pagina') or ''
    paragrafi = sorted({m.group(0).strip() for m in PARAGRAFI.finditer(testo[:1500])})
    return {'codice': esce['codice'], 'testo': re.sub(r'\s+', ' ', testo)[:1200], 'paragrafi': paragrafi}


class GeneratoreCoppie:
    """The automatic rule: the pairs C03 finds by itself in the live rows.

    Args:
        traduzioni: the rule for translations; without it only body/footnote pairs are generated.
    """

    def __init__(self, traduzioni: RegolaTraduzioni | None = None) -> None:
        self.traduzioni = traduzioni

    @staticmethod
    def per_atto(banca: Mapping[str, Riga]) -> dict[tuple[str, str], list[Riga]]:
        """The live rows with a code, by ``(document_id, caso_citato)``."""
        per: dict[tuple[str, str], list[Riga]] = collections.defaultdict(list)
        for r in banca.values():
            if r.get('proposto_rete') in RETI_VIVE and r.get('codice'):
                per[(r['document_id'], r['caso_citato'])].append(r)
        return per

    @staticmethod
    def stessa_frase(fx: str, fy: str) -> bool:
        """The normalised sentences are equal or at least :data:`SOGLIA_FRASE` similar."""
        return fx == fy or fuzz.ratio(fx, fy) >= SOGLIA_FRASE

    @staticmethod
    def a_una_pagina(x: Riga, y: Riga) -> bool:
        """The proposed pages differ by at most one (a missing page counts as 0; an unreadable one fails)."""
        try:
            return abs(int(x.get('proposto_pagina') or 0) - int(y.get('proposto_pagina') or 0)) <= 1
        except (TypeError, ValueError):
            return False

    def testo_nota(self, banca: Mapping[str, Riga], visti: set[str]) -> list[CoppiaC03]:
        """The body/footnote pairs; the codes of the rows that go out are added to ``visti``."""
        out: list[CoppiaC03] = []
        for rr in self.per_atto(banca).values():
            frasi = [(r, normalizza(r.get('proposto_frase_sostenuta'))) for r in rr]
            frasi = [(r, f) for r, f in frasi if len(f) >= MIN_FRASE]
            for a in range(len(frasi)):
                for c in range(a + 1, len(frasi)):
                    (x, fx), (y, fy) = frasi[a], frasi[c]
                    if not self.a_una_pagina(x, y) or not self.stessa_frase(fx, fy):
                        continue
                    t, n = chi_e_il_testo(x, y)
                    # two footnotes with the same sentence are two citations (rule of S07): merged only with a body row
                    if not (nel_testo(t) or t.get('proposto_posizione') == 'corpo') or n['codice'] in visti:
                        continue
                    visti.add(n['codice'])
                    out.append(
                        CoppiaC03(
                            'testo_nota',
                            t,
                            n,
                            f'stessa frase sostenuta di {t["codice"]} (p. {t.get("proposto_pagina")}): '
                            f"la nota {n['codice']} e' la stessa citazione del testo",
                        )
                    )
        return out

    def traduzioni_di(self, banca: Mapping[str, Riga], visti: set[str]) -> list[CoppiaC03]:
        """The translation pairs, if a :class:`RegolaTraduzioni` was given."""
        regola = self.traduzioni
        if regola is None:
            return []
        regola.prepara(banca)
        per_codice = {r.get('codice'): r for r in banca.values() if r.get('codice')}
        out: list[CoppiaC03] = []
        for rid, r in banca.items():
            if r.get('proposto_rete') not in RETI_VIVE or r.get('codice') in visti:
                continue
            codice = regola.codice_altra_riga(rid, r)
            altra = per_codice.get(codice) if codice else None
            if not altra or altra.get('codice') in visti:
                continue
            originale = regola.lingua_originale(r)
            la, lb = regola.lingua_del_testo(r['file']), regola.lingua_del_testo(altra['file'])
            if originale and (la == originale) != (lb == originale):
                tieni, esce = (r, altra) if la == originale else (altra, r)
                come = f'lingua originale dell atto ({originale})'
            else:
                tieni, esce = sorted((r, altra), key=lambda z: z['codice'])
                come = 'lingua originale non nota o uguale: la prima'
            if esce['codice'] in visti:
                continue
            visti.add(esce['codice'])
            out.append(
                CoppiaC03(
                    'traduzione',
                    tieni,
                    esce,
                    f"traduzione dello stesso atto: la stessa citazione e' {tieni['codice']} "
                    f'in {regola.lingua_del_testo(tieni["file"])} ({come})',
                )
            )
        return out

    def coppie(self, banca: Mapping[str, Riga]) -> list[CoppiaC03]:
        """Every pair, body/footnote first, then translations, on all the live rows."""
        visti: set[str] = set()
        return self.testo_nota(banca, visti) + self.traduzioni_di(banca, visti)


class CoppieRivedute:
    """The pairs read by hand (5 October 2026: only what was decided by hand is written).

    The list is ``training/esclusioni/C03_da_scrivere_RIVISTO.tsv`` (columns ``codice_tenuto``, ``codice_che_esce``,
    ``tipo``, ``motivo``): only the pairs to MERGE, with the row to keep chosen by reading the filing. Checks: a row
    that goes out in two pairs goes out once; a chain (A keeps B, B keeps C) closes on its final row; a row already
    excluded, discarded by the team or missing is never kept, and the pair is skipped and counted.

    Args:
        stampa: where the «saltate» lines go.
    """

    def __init__(self, stampa: Stampa = _stampa) -> None:
        self.stampa = stampa

    @staticmethod
    def leggi(elenco: Path | str) -> list[dict[str, str]]:
        """The rows of the list."""
        with open(elenco, encoding='utf-8', newline='') as f:
            return list(csv.DictReader(f, delimiter='\t'))

    def coppie(self, banca: Mapping[str, Riga], elenco: Path | str) -> list[CoppiaC03]:
        """The pairs of the list that are still valid on ``banca``."""
        per_codice = {r.get('codice'): r for r in banca.values() if r.get('codice')}
        righe = self.leggi(elenco)
        tenuta_di = {x['codice_che_esce']: x['codice_tenuto'] for x in righe}

        def finale(codice: str, passi: int = 0) -> str:
            return finale(tenuta_di[codice], passi + 1) if codice in tenuta_di and passi < 10 else codice

        out: list[CoppiaC03] = []
        visti: set[str] = set()
        saltate: collections.Counter[str] = collections.Counter()
        for x in righe:
            t, n = per_codice.get(finale(x['codice_tenuto'])), per_codice.get(x['codice_che_esce'])
            if not t or not n or t is n:
                saltate['riga assente o catena chiusa su se stessa'] += 1
            elif n['codice'] in visti:
                saltate["riga che esce gia' in un'altra coppia"] += 1
            elif t.get('proposto_rete') not in RETI_VIVE or t.get('esito') == 'scartata':
                saltate['riga da tenere non viva o scartata'] += 1
            elif n.get('proposto_rete') not in RETI_VIVE:
                saltate["riga che esce gia' esclusa"] += 1
            else:
                visti.add(n['codice'])
                out.append(CoppiaC03(x['tipo'], t, n, x['motivo']))
        for k, v in saltate.items():
            self.stampa(f'saltate ({k}): {v}')
        return out


@dataclass
class EsitoC03:
    """What a run of :class:`UnioneC03` did.

    Attributes:
        coppie: every pair found.
        libere: the pairs to write.
        giudicate: the pairs in which the team judged a row (to review one by one).
        scritture: ``{row id: fields}`` prepared (written only with ``scrivi``).
        copia: the path of the copy before the write, when written.
    """

    coppie: list[CoppiaC03] = field(default_factory=list)
    libere: list[CoppiaC03] = field(default_factory=list)
    giudicate: list[CoppiaC03] = field(default_factory=list)
    scritture: dict[str, dict[str, Any]] = field(default_factory=dict)
    copia: Path | None = None


def carica_fotografia(percorso: Path | str) -> dict[str, dict[str, Any]]:
    """A snapshot of ``corpus_rows``: a JSON file, gzipped when the name ends in ``.gz``."""
    p = Path(percorso)
    with gzip.open(p, 'rt', encoding='utf-8') if p.suffix == '.gz' else open(p, encoding='utf-8') as f:
        return json.load(f)


def righe_vive_della_banca(banca: BancaDati, casi: Iterable[str]) -> dict[str, dict[str, Any]]:
    """``{id: row}`` of the given cases from the database, values made JSON-friendly (read only)."""
    out: dict[str, dict[str, Any]] = {}
    for caso in casi:
        for rid, r in banca.righe('corpus_rows', [('caso_citato', '==', caso)]):
            out[rid] = json.loads(json.dumps(r, default=str))
    return out


class UnioneC03:
    """The C03 step: find the pairs, list them, and (with ``scrivi``) mark the excluded rows.

    Args:
        config: paths (the lists go under ``training/esclusioni``).
        banca: the platform database; also where the rows are read from unless ``fotografia`` is given.
        da: who runs it (``esclusa_da``, ``c03_da``).
        rivisto: the list read by hand; with it the pairs come only from that list.
        fotografia: a snapshot of ``corpus_rows`` to use instead of reading the database.
        scrivi: write to the database (without it the step is a preview: only the lists are written).
        generatore: the automatic rule (default without the translation rule).
        copia: the copy before the write.
        orologio: the clock of the screen line.
        stampa: where the screen lines go.
    """

    def __init__(
        self,
        config: Config,
        banca: BancaDati,
        da: str,
        rivisto: Path | str = '',
        fotografia: Path | str = '',
        scrivi: bool = False,
        generatore: GeneratoreCoppie | None = None,
        copia: CopiaPrima | None = None,
        orologio: Callable[[], datetime.datetime] = datetime.datetime.now,
        stampa: Stampa = _stampa,
    ) -> None:
        self.config = config
        self.banca = banca
        self.da = da
        self.rivisto = rivisto
        self.fotografia = fotografia
        self.scrivi = scrivi
        self.generatore = generatore or GeneratoreCoppie()
        self.copia = copia or CopiaPrima(config.radice)
        self.orologio = orologio
        self.stampa = stampa

    @property
    def cartella(self) -> Path:
        return self.config.radice.joinpath(*CARTELLA_ELENCHI)

    def righe(self) -> dict[str, dict[str, Any]]:
        """The rows to work on."""
        if self.fotografia:
            return carica_fotografia(self.fotografia)
        return righe_vive_della_banca(self.banca, self.config.casi)

    @staticmethod
    def separa(coppie: Sequence[CoppiaC03]) -> tuple[list[CoppiaC03], list[CoppiaC03]]:
        """``(free pairs, pairs with a row the team judged)``."""
        libere = [c for c in coppie if not (giudicata(c.tenuta) or giudicata(c.esce))]
        return libere, [c for c in coppie if giudicata(c.tenuta) or giudicata(c.esce)]

    @staticmethod
    def scrivi_elenco(percorso: Path, coppie: Iterable[CoppiaC03]) -> None:
        """A list of pairs as a tab-separated file."""
        percorso.parent.mkdir(parents=True, exist_ok=True)
        with open(percorso, 'w', newline='', encoding='utf-8') as h:
            w = csv.writer(h, delimiter='\t')
            w.writerow(INTESTAZIONE_TSV)
            for c in coppie:
                w.writerow(
                    [c.tipo, c.tenuta['codice'], c.esce['codice'], giudizio(c.tenuta), giudizio(c.esce), c.motivo]
                )

    def prepara_scritture(self, banca: Mapping[str, Riga], libere: Sequence[CoppiaC03]) -> dict[str, dict[str, Any]]:
        """The fields to write: ``{row id: fields}``, one entry per row touched (a kept row may also be excluded)."""
        id_di = {r.get('codice'): i for i, r in banca.items() if r.get('codice')}
        # the server clock only when writing: a preview on a snapshot needs no connection to the database
        ora = self.banca.ora_del_server if self.scrivi else ORA_DEL_SERVER
        campi: dict[str, dict[str, Any]] = {}
        for c in libere:
            ine, it = id_di[c.esce['codice']], id_di[c.tenuta['codice']]
            campi[ine] = {
                'proposto_rete': 'esclusa',
                'esclusa_rete_prima': c.esce.get('proposto_rete'),
                'esclusa_regola': CODICE,
                'unita_a': c.tenuta['codice'],
                'esclusa_motivo': f'{CODICE} {c.motivo}',
                'esclusa_da': self.da,
                'esclusa_il': ora,
            }
            ct = campi.setdefault(it, {'c03_da': self.da, 'c03_il': ora})
            if c.tipo == 'testo_nota':
                ct.setdefault('proposto_nota_appoggio', []).append(appoggio(c.tenuta, c.esce))
                ct['proposto_paragrafi'] = sorted(
                    set(ct.get('proposto_paragrafi') or c.tenuta.get('proposto_paragrafi') or [])
                    | set(c.esce.get('proposto_paragrafi') or [])
                )
            else:
                ct.setdefault('proposto_traduzioni_unite', []).append(c.esce['codice'])
        return campi

    def esegui(self) -> EsitoC03:
        """Find the pairs, write the two lists, and with ``scrivi`` write the rows (copy first)."""
        banca = self.righe()
        esito = EsitoC03()
        if self.rivisto:
            esito.coppie = CoppieRivedute(self.stampa).coppie(banca, self.rivisto)
            esito.libere, esito.giudicate = esito.coppie, []  # already reviewed one by one, judged rows included
            uscita = self.cartella / 'C03_da_scrivere_RIVISTO_controllato.tsv'
        else:
            esito.coppie = self.generatore.coppie(banca)
            esito.libere, esito.giudicate = self.separa(esito.coppie)
            uscita = self.cartella / 'C03_da_scrivere.tsv'
        giudicate = self.cartella / 'C03_giudicate_da_rivedere.tsv'
        self.scrivi_elenco(uscita, esito.libere)
        self.scrivi_elenco(giudicate, esito.giudicate)
        k = collections.Counter(c.tipo for c in esito.libere)
        g = collections.Counter(c.tipo for c in esito.giudicate)
        self.stampa(
            f'coppie: {len(esito.coppie)} | da scrivere {len(esito.libere)} {dict(k)} | '
            f'giudicate, da rivedere {len(esito.giudicate)} {dict(g)}'
        )
        self.stampa(f'elenchi: {uscita} {giudicate}')
        esito.scritture = self.prepara_scritture(banca, esito.libere)
        if not self.scrivi:
            self.stampa('ANTEPRIMA: niente scritto in banca dati')
            return esito
        prima = {rid: banca[rid] for rid in esito.scritture}
        esito.copia = self.copia.salva('unisci_c03', 'tutti', prima, esito.scritture, ciclo='esclusioni')
        self.banca.scrivi_a_lotti(Scrittura('update', 'corpus_rows', rid, c) for rid, c in esito.scritture.items())
        self.stampa(
            f'scritte {len(esito.scritture)} righe | copia {esito.copia} | {self.orologio().strftime("%d/%m/%Y %H:%M")}'
        )
        return esito
