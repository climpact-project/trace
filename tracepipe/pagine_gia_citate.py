"""C07: a surrounding page that is a citation of its own is marked «also cited separately» (``pagine_gia_citate``).

Class-based version of ``tools/applica_c07.py`` and of ``pagine_gia_citate`` of ``tools/controlli_automatici.py``
(4 and 5 October 2026; case ICJ-0154). A row of the pipeline carries, in ``proposto_estensione``, the surrounding
pages the readers looked at; a page that DeepSeek reads as «continues the reasoning» may in fact hold ANOTHER citation
of the same judgment, with a row of its own.

For every live row and every surrounding page the rule asks whether another live row of the same case in the same
filing sits on that page: by position (its ``char_start`` falls inside the page) or by text (the proof found on the
page matches the supported sentence, the reading sentence or the quoted text of that other row: normalised,
rapidfuzz partial ratio >= 90, at least 30 and 40 characters). Only pages with NO principle in common with the other
row are marked (decision of the PI: another principle means a separate citation; with a principle in common DeepSeek
decides).

What it writes (rows judged by the team are never touched, except for the ticked pages described below)
    the entry of the page in ``proposto_estensione``: ``c07`` true, ``c07_altra_riga`` (the first code),
    ``c07_segno`` «also cited separately as ...». ``prosegue`` stays as it was: the reading of DeepSeek is not erased;
    composition and map treat the entry as NOT a continuation.
    ``proposto_principi``: a principle P is removed only if ALL of these hold: it comes from a marked page that
    continues; it comes from no other continuing, unmarked page; it is not in the map of the paragraphs the row cites;
    the readings of the row do not hold it (fewer than 3 of 5 votes: the threshold of R11); and the OTHER row has P.
    If the other row does not have P, the principle stays and goes to the list for the team. A removed principle goes
    to ``principi_tolti_c07`` ``[{principio, pagina, altra_riga, motivo}]``.
    ``c07_da``, ``c07_il`` (provenance), after the full copy of the rows (:mod:`tracepipe.copia_prima`).

The pages DeepSeek read as «continues» (about 1,190) are applied only if a person reread them as ANOTHER CITATION
(``rilette``: a file with the columns ``codice``, ``pagina``, ``esito``, the outcome beginning with «altra»); the
others go to ``C07_prosegue_da_rileggere.tsv``.

Pages ticked as «continuation» by the team on judged rows (:meth:`ApplicaC07.spunte_del_team`, 5 October): the
by-hand review of 229 pages (``C07-REVISIONE-SEGUITI-2026-10-04.tsv``) says which of them are a citation of their
own; the tick is removed from ``validato_estensione`` and the entry takes the mark, with a trace in
``c07_spunte_tolte`` ``{pagina, altra_riga, motivo}`` to put it back by hand. Principles and verdict stay the team's.
"""

from __future__ import annotations

import collections
import csv
import datetime
import random
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from .banca import BancaDati, Scrittura
from .config import Config
from .copia_prima import CopiaPrima
from .righe import RETI_VIVE, LettoreAtti, Riga, giudicata, giudizio, normalizza, principi_di
from .unione_c03 import carica_fotografia, righe_vive_della_banca

CODICE = 'C07'
"""The registry code of the rule."""
SOGLIA_VOTI = 3
"""Votes out of five that keep a principle (the threshold of R11)."""
MIN_PROVA = 30
"""Characters of the proof, normalised, to look for it in another row."""
MIN_FRASE = 40
"""Characters of the other row's sentence, normalised, to compare."""
SOGLIA_TESTO = 90
"""rapidfuzz partial ratio at which the text of the proof matches another row."""
SEME_ESEMPI = 20261004
"""The fixed seed of the ten examples in the preview."""
PAGINA = re.compile(r'<!-- page (\d+) -->')
CARTELLA_ELENCHI = ('training', 'esclusioni')

Stampa = Callable[[str], None]


def _stampa(testo: str) -> None:
    print(testo, flush=True)


def segno_c07(codici: Iterable[str]) -> str:
    """The text that panel, DeepSeek question and map data show next to the page (English)."""
    return 'also cited separately as ' + ', '.join(codici)


def spazi_pagine(testo: str) -> dict[int, tuple[int, int]]:
    """``{page: (start, end)}`` of the pages of a markdown text: from the end of its mark to the start of the next."""
    marche = list(PAGINA.finditer(testo))
    return {
        int(m.group(1)): (m.end(), marche[k + 1].start() if k + 1 < len(marche) else len(testo))
        for k, m in enumerate(marche)
    }


def voti(riga: Riga, principio: str) -> int:
    """How many readings of five hold the principle (``proposto_principi_voti`` is ``'n/5'``); 0 if unreadable."""
    v = (riga.get('proposto_principi_voti') or {}).get(principio)
    try:
        return int(str(v).split('/')[0])
    except (TypeError, ValueError):
        return 0


@dataclass(frozen=True)
class PaginaGiaCitata:
    """A page of a row that another live row of the same filing already cites.

    Attributes:
        codici: the codes of the other rows on the page, in order.
        posizione: one of them sits on the page by position.
        testo: one of them matches by text.
        seguito: the other rows share a principle with this row (the page stays a candidate).
    """

    codici: tuple[str, ...]
    posizione: bool
    testo: bool
    seguito: bool

    @property
    def segno(self) -> str:
        return segno_c07(self.codici)


class RiconoscitorePagine:
    """Finds, in a row, the surrounding pages that another live row already cites."""

    @staticmethod
    def sulla_pagina(altra: Riga, inizio: int, fine: int) -> bool:
        """The point of the other row falls inside the page."""
        cs = altra.get('char_start')
        return cs not in (None, '') and inizio <= int(cs) < fine

    @staticmethod
    def nel_testo(prova: str, altra: Riga) -> bool:
        """The proof matches a sentence of the other row (the shorter inside the longer, partial ratio >= 90)."""
        for x in (
            altra.get('proposto_frase_sostenuta'),
            altra.get('proposto_frase_lettura'),
            altra.get('proposto_citazione_testuale'),
        ):
            x = normalizza(x)
            if len(x) < MIN_FRASE:
                continue
            a, b = (prova, x) if len(prova) <= len(x) else (x, prova)
            if fuzz.partial_ratio(a, b, score_cutoff=SOGLIA_TESTO):
                return True
        return False

    def pagine(
        self, riga: Riga, righe_stesso_atto: Iterable[Riga], spazi: Mapping[int, tuple[int, int]]
    ) -> dict[int, PaginaGiaCitata]:
        """``{page: PaginaGiaCitata}`` for the surrounding pages of ``riga``.

        Args:
            riga: the row.
            righe_stesso_atto: the rows of the same ``document_id`` and case.
            spazi: ``{page: (start, end)}`` in the markdown (:func:`spazi_pagine`).
        """
        altre = [
            s
            for s in righe_stesso_atto
            if s.get('codice') != riga.get('codice') and s.get('proposto_rete') in RETI_VIVE
        ]
        out: dict[int, PaginaGiaCitata] = {}
        for e in riga.get('proposto_estensione') or []:
            p = e.get('pagina')
            if p not in spazi:
                continue
            inizio, fine = spazi[p]
            prova = normalizza(e.get('prova'))
            trovate: list[tuple[Riga, bool, bool]] = []
            for s in altre:
                pos = self.sulla_pagina(s, inizio, fine)
                txt = len(prova) >= MIN_PROVA and not pos and self.nel_testo(prova, s)
                if pos or txt:
                    trovate.append((s, pos, txt))
            if not trovate:
                continue
            out[p] = PaginaGiaCitata(
                codici=tuple(sorted(s.get('codice') for s, _, _ in trovate)),
                posizione=any(x[1] for x in trovate),
                testo=any(x[2] for x in trovate),
                seguito=any(principi_di(riga) & principi_di(s) for s, _, _ in trovate),
            )
        return out


class LettoreAttiPagine:
    """The page spaces of the filings, computed once per file (a thin cache over :class:`LettoreAtti`)."""

    def __init__(self, radice: Path | str) -> None:
        self.atti = LettoreAtti(radice)
        self._spazi: dict[str, dict[int, tuple[int, int]]] = {}

    def spazi(self, file: str) -> dict[int, tuple[int, int]]:
        if file not in self._spazi:
            self._spazi[file] = spazi_pagine(self.atti.testo(file))
        return self._spazi[file]


class TutteLeRilette:
    """For the preview ``ipotesi_tutte`` only: acts as if a person had reread EVERY «continues» page as another
    citation (the ceiling of what the rule could do)."""

    def __contains__(self, _chiave: object) -> bool:
        return True


@dataclass
class RisultatoC07:
    """What the rule decides on a snapshot of the rows (nothing is written yet).

    Attributes:
        scritture: ``{row id: fields}``.
        tolti: removed principles ``(code, case, principle, page, other row)``.
        per_il_team: principles that stay but go to the team ``(code, principle, page, other row, its principles)``.
        saltate: marked pages of rows the team judged ``(code, page, other row, judgment)``.
        segni: pages marked.
        da_rileggere: «continues» pages kept apart ``(code, page, other row, judgment)``.
    """

    scritture: dict[str, dict[str, Any]] = field(default_factory=dict)
    tolti: list[tuple[str, str, str, int, str]] = field(default_factory=list)
    per_il_team: list[tuple[str, str, int, str, str]] = field(default_factory=list)
    saltate: list[tuple[str, int, str, str]] = field(default_factory=list)
    segni: int = 0
    da_rileggere: list[tuple[str, int, str, str]] = field(default_factory=list)


class ApplicaC07:
    """The C07 step on a snapshot of the live rows.

    Args:
        config: paths (the lists go under ``training/esclusioni``; the filings are read from the project root).
        banca: the platform database (read for the rows, written with ``scrivi``).
        da: who runs it (``c07_da``).
        rilette: ``{(code, page)}`` reread by hand as another citation; ``None`` applies none of the «continues» pages.
        revisione: the by-hand review of the ticked pages (``--spunte-team``), a TSV path.
        fotografia: a snapshot of ``corpus_rows`` to use instead of reading the database.
        ipotesi_tutte: preview only, as if every «continues» page had been reread as another citation.
        scrivi: write to the database.
        riconoscitore: the page recogniser.
        copia: the copy before the write.
        orologio: the clock of the screen line.
        stampa: where the screen lines go.
    """

    def __init__(
        self,
        config: Config,
        banca: BancaDati,
        da: str,
        rilette: set[tuple[str, int]] | None = None,
        revisione: Path | str = '',
        fotografia: Path | str = '',
        ipotesi_tutte: bool = False,
        scrivi: bool = False,
        riconoscitore: RiconoscitorePagine | None = None,
        copia: CopiaPrima | None = None,
        orologio: Callable[[], datetime.datetime] = datetime.datetime.now,
        stampa: Stampa = _stampa,
    ) -> None:
        if ipotesi_tutte and scrivi:
            raise ValueError('--ipotesi-tutte non si usa con --scrivi')
        self.config = config
        self.banca = banca
        self.da = da
        self.rilette: Any = TutteLeRilette() if ipotesi_tutte else rilette
        self.revisione = revisione
        self.fotografia = fotografia
        self.ipotesi_tutte = ipotesi_tutte
        self.scrivi = scrivi
        self.riconoscitore = riconoscitore or RiconoscitorePagine()
        self.copia = copia or CopiaPrima(config.radice)
        self.orologio = orologio
        self.stampa = stampa

    @staticmethod
    def leggi_rilette(percorso: Path | str) -> set[tuple[str, int]]:
        """``{(code, page)}`` of the reread pages whose outcome begins with «altra» (another citation)."""
        with open(percorso, encoding='utf-8', newline='') as f:
            return {
                (x['codice'], int(x['pagina']))
                for x in csv.DictReader(f, delimiter='\t')
                if (x.get('esito') or '').strip().lower().startswith('altra')
            }

    @property
    def cartella(self) -> Path:
        return self.config.radice.joinpath(*CARTELLA_ELENCHI)

    def righe(self) -> dict[str, dict[str, Any]]:
        """The rows to work on."""
        if self.fotografia:
            return carica_fotografia(self.fotografia)
        return righe_vive_della_banca(self.banca, self.config.casi)

    def principi_da_togliere(
        self,
        r: Riga,
        estensione: list[dict[str, Any]],
        per_codice: Mapping[str, Riga],
        out: RisultatoC07,
    ) -> dict[str, Any]:
        """The ``proposto_principi`` part of the write: which principles go away and which go to the team."""
        princ = list(r.get('proposto_principi') or [])
        mappa = set(r.get('proposto_principi_da_mappa') or [])
        da_altre = {e.get('principio') for e in estensione if e.get('prosegue') and not e.get('c07')}
        nuovi: list[str] = []
        via: list[dict[str, Any]] = []
        for p in princ:
            pagine_c07 = [e for e in estensione if e.get('c07') and e.get('prosegue') and e.get('principio') == p]
            if not pagine_c07 or p in da_altre or p in mappa or voti(r, p) >= SOGLIA_VOTI:
                nuovi.append(p)
                continue
            e = pagine_c07[0]
            altra = per_codice.get(e['c07_altra_riga']) or {}
            if p in principi_di(altra):
                via.append(
                    {
                        'principio': p,
                        'pagina': e['pagina'],
                        'altra_riga': altra.get('codice'),
                        'motivo': (
                            f"C07: viene solo dalla p. {e['pagina']}, che e' la citazione {altra.get('codice')} "
                            f"(ha gia' questo principio); non retto da mappa dei paragrafi ne' letture ({voti(r, p)}/5)"
                        ),
                    }
                )
            else:
                nuovi.append(p)
                out.per_il_team.append(
                    (r['codice'], p, e['pagina'], e['c07_altra_riga'], ';'.join(sorted(principi_di(altra))))
                )
        campi: dict[str, Any] = {}
        if via:
            campi['proposto_principi'] = nuovi or ['nessuno']
            campi['principi_tolti_c07'] = via
        return campi

    def calcola(self, banca: Mapping[str, Riga]) -> RisultatoC07:
        """The decisions of the rule on ``banca`` (reads only)."""
        atti = LettoreAttiPagine(self.config.radice)
        per: dict[tuple[str, str], list[Riga]] = collections.defaultdict(list)
        for r in banca.values():
            if r.get('document_id') and r.get('proposto_rete') in RETI_VIVE:
                per[(r['document_id'], r['caso_citato'])].append(r)
        per_codice = {r.get('codice'): r for r in banca.values() if r.get('codice')}
        out = RisultatoC07()
        for rid, r in banca.items():
            if r.get('proposto_rete') not in RETI_VIVE or not r.get('proposto_estensione'):
                continue
            marcate = self.riconoscitore.pagine(r, per[(r['document_id'], r['caso_citato'])], atti.spazi(r['file']))
            marcate = {p: v for p, v in marcate.items() if not v.seguito}  # only a different principle (the PI)
            prosegue = {e.get('pagina') for e in r['proposto_estensione'] if e.get('prosegue')}
            for p in [p for p in marcate if p in prosegue]:
                if self.rilette is None or (r['codice'], p) not in self.rilette:
                    out.da_rileggere.append((r['codice'], p, marcate[p].codici[0], giudizio(r)))
                    del marcate[p]
            if not marcate:
                continue
            if giudicata(r):
                out.saltate += [(r['codice'], p, v.codici[0], giudizio(r)) for p, v in marcate.items()]
                continue
            estensione = [dict(e) for e in r['proposto_estensione']]
            for e in estensione:
                if e.get('pagina') in marcate:
                    v = marcate[e['pagina']]
                    e['c07'] = True
                    e['c07_altra_riga'] = v.codici[0]
                    e['c07_segno'] = v.segno
                    out.segni += 1
            campi = {'proposto_estensione': estensione} | self.principi_da_togliere(r, estensione, per_codice, out)
            out.tolti += [
                (r['codice'], r['caso_citato'], x['principio'], x['pagina'], x['altra_riga'])
                for x in campi.get('principi_tolti_c07', [])
            ]
            out.scritture[rid] = campi
        return out

    def spunte_del_team(self, banca: Mapping[str, Riga], revisione: Path | str) -> dict[str, dict[str, Any]]:
        """``{id: fields}`` for the JUDGED rows: the pages ticked as «continuation» by the team that the by-hand review
        says are a citation of their own (``team_spunta_seguito`` = ``si`` and ``revisione`` beginning with ALTRA).

        The page leaves ``validato_estensione``, the entry of ``proposto_estensione`` takes the mark, and
        ``c07_spunte_tolte`` keeps the trace. Nothing else changes.
        """
        id_di = {r.get('codice'): i for i, r in banca.items() if r.get('codice')}
        scritture: dict[str, dict[str, Any]] = {}
        saltate: collections.Counter[str] = collections.Counter()
        with open(revisione, encoding='utf-8', newline='') as f:
            righe = list(csv.DictReader(f, delimiter='\t'))
        for x in righe:
            if x['team_spunta_seguito'] != 'si' or not x['revisione'].upper().startswith('ALTRA'):
                continue
            i = id_di.get(x['riga'])
            if i is None:
                saltate['riga assente'] += 1
                continue
            r, p = banca[i], int(x['pagina_attorno'])
            c = scritture.setdefault(
                i,
                {
                    'validato_estensione': list(r.get('validato_estensione') or []),
                    'proposto_estensione': [dict(e) for e in r.get('proposto_estensione') or []],
                    'c07_spunte_tolte': list(r.get('c07_spunte_tolte') or []),
                },
            )
            if p not in c['validato_estensione']:
                saltate["spunta gia' tolta"] += 1
                continue
            altra = x['altre_righe_sulla_pagina'].split(',')[0].strip()
            c['validato_estensione'].remove(p)
            for e in c['proposto_estensione']:
                if e.get('pagina') == p:
                    e['c07'] = True
                    e['c07_altra_riga'] = altra
                    e['c07_segno'] = segno_c07([altra])
            c['c07_spunte_tolte'].append({'pagina': p, 'altra_riga': altra, 'motivo': 'C07 ' + x['motivo'][:300]})
        for k, v in saltate.items():
            self.stampa(f'spunte del team saltate ({k}): {v}')
        return scritture

    def scrivi_elenchi(self, ris: RisultatoC07) -> None:
        """The four lists of the step, tab-separated, under ``training/esclusioni``."""
        self.cartella.mkdir(parents=True, exist_ok=True)
        for nome, testa, el in (
            ('C07_principi_tolti.tsv', ['codice', 'caso', 'principio', 'pagina', 'altra_riga'], ris.tolti),
            (
                'C07_principi_per_il_team.tsv',
                ['codice', 'principio', 'pagina', 'altra_riga', 'principi_altra'],
                ris.per_il_team,
            ),
            ('C07_giudicate_saltate.tsv', ['codice', 'pagina', 'altra_riga', 'giudizio'], ris.saltate),
            ('C07_prosegue_da_rileggere.tsv', ['codice', 'pagina', 'altra_riga', 'giudizio'], ris.da_rileggere),
        ):
            with open(self.cartella / nome, 'w', newline='', encoding='utf-8') as h:
                w = csv.writer(h, delimiter='\t')
                w.writerow(testa)
                w.writerows(el)

    def scrivi_esempi(self, banca: Mapping[str, Riga], scritture: Mapping[str, Mapping[str, Any]], n: int = 10) -> None:
        """Ten examples with before and after (fixed seed): first the ones with a principle removed, then at random."""
        ids = sorted(scritture)
        random.Random(SEME_ESEMPI).shuffle(ids)
        ids = sorted(ids, key=lambda i: 0 if scritture[i].get('principi_tolti_c07') else 1)[:n]
        suffisso = '_IPOTESI' if self.ipotesi_tutte else ''
        with open(self.cartella / f'C07_esempi{suffisso}.tsv', 'w', newline='', encoding='utf-8') as h:
            w = csv.writer(h, delimiter='\t')
            w.writerow(['codice', 'pagine_prima', 'pagine_dopo', 'principi_prima', 'principi_dopo'])
            for i in ids:
                r, c = banca[i], scritture[i]
                prima = ', '.join(
                    f'p.{e["pagina"]}{" (seguito)" if e.get("prosegue") else ""}' for e in r['proposto_estensione']
                )
                dopo = ', '.join(
                    f'p.{e["pagina"]}'
                    + (
                        f' (altra citazione {e["c07_altra_riga"]}, non seguito)'
                        if e.get('c07')
                        else (' (seguito)' if e.get('prosegue') else '')
                    )
                    for e in c['proposto_estensione']
                )
                riga = [
                    r['codice'],
                    prima,
                    dopo,
                    ';'.join(r.get('proposto_principi') or []),
                    ';'.join(c.get('proposto_principi', r.get('proposto_principi') or [])),
                ]
                w.writerow(riga)
                self.stampa('ESEMPIO ' + ' | '.join(riga))

    def esegui(self) -> RisultatoC07:
        """Compute, write the lists and the examples, and with ``scrivi`` write the rows (copy first)."""
        banca = self.righe()
        ris = self.calcola(banca)
        if self.revisione:
            spunte = self.spunte_del_team(banca, self.revisione)
            if set(spunte) & set(ris.scritture):
                raise ValueError("una riga giudicata e' finita anche fra quelle della regola")
            n = sum(len(c['c07_spunte_tolte']) - len(banca[i].get('c07_spunte_tolte') or []) for i, c in spunte.items())
            self.stampa(f'spunte del team tolte: {n} pagine su {len(spunte)} righe giudicate')
            ris.scritture.update(spunte)
        self.scrivi_elenchi(ris)
        giudicate = {x[0] for x in ris.saltate}
        self.stampa(
            f'righe toccate {len(ris.scritture)} | segni {ris.segni} | principi tolti {len(ris.tolti)} | '
            f'per il team {len(ris.per_il_team)} | giudicate saltate {len(giudicate)} righe '
            f'({len(ris.saltate)} pagine) | '
            f'«prosegue» tenute a parte {len(ris.da_rileggere)}'
        )
        self.stampa(f'tolti per caso: {dict(collections.Counter(x[1] for x in ris.tolti))}')
        self.stampa(f'tolti per principio: {collections.Counter(x[2] for x in ris.tolti).most_common()}')
        self.scrivi_esempi(banca, ris.scritture)
        if not self.scrivi:
            self.stampa('ANTEPRIMA: niente scritto in banca dati')
            return ris
        ora = self.banca.ora_del_server
        for c in ris.scritture.values():
            c['c07_da'] = self.da
            c['c07_il'] = ora
        copia = self.copia.salva(
            'applica_c07', 'tutti', {i: banca[i] for i in ris.scritture}, ris.scritture, 'esclusioni'
        )
        self.banca.scrivi_a_lotti(Scrittura('update', 'corpus_rows', rid, c) for rid, c in ris.scritture.items())
        self.stampa(f'scritte {len(ris.scritture)} | copia {copia} | {self.orologio().strftime("%d/%m/%Y %H:%M")}')
        return ris
