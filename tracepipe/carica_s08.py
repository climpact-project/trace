"""S08, loading the new rows (``carica_s08``).

Class-based version of ``tools/carica_righe_s08.py`` (5 October 2026).

THE ROWS. They are the «new» citations recovered by S08 (descriptive network without the filter of the page; outcome
``nuova`` of the scan, see :func:`tracepipe.coppie_vicine.classifica_recuperate`): citations of the same case that S07
lost because the page already had the name or a row. They become rows of ``corpus_rows`` IDENTICAL IN FORM to the
descriptive rows of S07: the fields of :func:`tracepipe.ricerca.documento_riga`, ``proposto_rete`` «descrittiva», the
code after the highest of the case, the row OUTSIDE THE QUEUES (``assegnato_a_in_attesa``: whoever completes it puts it
back in the queues), the id of :func:`tracepipe.ricerca.id_riga`.

THE DIFFERENCES FROM S07 (all and only):

- ``provenienza.estrazione`` and ``esecuzione_id`` say S08; ``causa_s07`` is replaced by ``causa_s08``
  «S08_stessa_pagina»;
- the verdict of C04 (``c04_resta``, ``c04_motivo``) is a CLUE written on the row, NOT an exclusion: C04 discards by
  mistake the citation of Children of Austria p. 29 (the date of the Klimabeschluss, «2021»), and S08 comes before C04
  in the cycle;
- ``s08_vicina_*``: the nearest live row of the same filing and case within the threshold (code, id, distance), so the
  S08 pair forms by itself, without recomputing it from the snapshot.

THE COPIES (5 October 2026, the PI: «align it to the best»): as in S07, a citation found in two copies of the same
document (the same filing published under several cases) is ONE: :class:`Copie`, with the rules of ``recupero_s06`` and
``recupero_s07`` (fingerprints, fragment, choice of the copy from the catalogue record, D04 filings and S06 rows
postponed). The write refuses every id already in the database. The database is read LIVE, never from a snapshot.

WHAT STAYS IN ``tools/``. Rebuilding each row from the markdown (the form found, the quoted text, the dimensions, the
position in the PDF) needs ``tools/rete_descrittiva.py`` and ``tools/cerca_s05_per_atto.py``; the rules of the copies
need ``tools/recupero_s06.py`` and ``tools/recupero_s07.py``. The package takes the rebuilt rows
(:class:`SorgenteNuove`) and the copy rules (:class:`RegoleCopie`) from the caller, and does everything else.
"""

from __future__ import annotations

import collections
import datetime
import json
import random
import re
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .banca import BancaDati, Scrittura
from .config import Config
from .coppie_vicine import SOGLIA_S08, CoppieVicine
from .ricerca import documento_riga, id_riga
from .righe import RETI_VIVE, Riga

ESTRAZIONE = 'S08'
CAUSA = 'S08_stessa_pagina'
from . import casi_registro  # noqa: E402
PREFISSI: Mapping[str, str] = dict(casi_registro.PREFISSI)
MOTIVO = (
    "citazione sulla stessa pagina di un'altra riga dello stesso caso, che la deduplica della pagina di S07 "
    'perdeva, recuperata da S08 (coppie vicine, 05/10/2026)'
)
LOTTO = 400
"""Writes per batch."""
QUOTA_CAMPIONE_CIECO = 0.20
"""Share of the new rows that go to the blind sample."""
ATTESE: tuple[tuple[str, str, int, int, int], ...] = (
    ('neubauer', '_6a3b', 29, 69272, 70664),
    ('neubauer', '_d48d', 10, 57336, 58268),
)
"""The proof cases ``(case, end of the filing id, page, char_start of the NEW row, char_start of the live row it pairs
with)``: Children of Austria p. 29 and BMW p. 10."""

Stampa = Callable[[str], None]


def _stampa(testo: str) -> None:
    print(testo, flush=True)


class SorgenteNuove(Protocol):
    """Where the rebuilt new rows come from (the CSV columns of the descriptive network of S07)."""

    def righe(self) -> list[dict[str, Any]]:
        """The new rows, in the order of the list, in the form of the descriptive CSV of S07."""


class RegoleCopie(Protocol):
    """The rules of ``recupero_s06`` and ``recupero_s07`` that :class:`Copie` needs."""

    def documenti_d04(self) -> set[str]:
        """The filings of D04 whose rows the D04 cycle has not written yet."""

    def ids_s06(self) -> set[str]:
        """The ids of the rows of S06."""

    def impronte(self, file: str) -> Mapping[str, str]:
        """``{'pdf': ..., 'testo': ...}`` fingerprints of a filing."""

    def chiave_testo(self, riga: Mapping[str, Any]) -> str:
        """The key of the fragment of a row (its quoted text, normalised)."""

    def stesso_documento(self, a: Mapping[str, str], b: Mapping[str, str]) -> str:
        """Why two fingerprints are the same document (empty if they are not)."""

    def scegli_per_scheda(self, files: Sequence[str]) -> tuple[str, Any]:
        """The copy to keep, from the catalogue record: ``(file, why)``."""


class Copie:
    """The copies of the SAME DOCUMENT in several filings (the rules of S07, ``recupero_s07.fase_righe``, 4 October).

    The Sabin Center publishes the same document under several cases (the same PDF or the same text). The same citation
    found in two copies is ONE citation. A new row goes out if:

    1. its filing is the same document as another filing that already has a live row of the case with the same fragment:
       the citation is there already, in the other copy;
    2. among the new rows another copy of the same fragment is already taken: which copy keeps the row is told by the
       catalogue record (``scegli_per_scheda``), not by the order of the paths;
    3. its filing is of D04 and the D04 cycle has not written its rows yet (D04 stops if it finds rows that are not its
       own), or its id is of S06: they are redone later, as in S07.

    The kept row carries the other ``case_id`` in ``stesso_documento_case_ids``.

    Args:
        banca_viva: ``{id: row}`` read from the live database.
        regole: the copy rules.
        radice: the project root, to see whether the file of a filing exists (``None``: every file exists).
    """

    def __init__(self, banca_viva: Mapping[str, Riga], regole: RegoleCopie, radice: Path | None = None) -> None:
        self.banca = banca_viva
        self.regole = regole
        self.radice = radice
        self.d04 = regole.documenti_d04()
        self.s06 = regole.ids_s06()

    def impronte(self, file: str | None) -> Mapping[str, str]:
        """The fingerprints of the filing; empty ones if the file is missing."""
        if file and (self.radice is None or (self.radice / file).exists()):
            return self.regole.impronte(file)
        return {'pdf': '', 'testo': ''}

    def chiave(self, riga: Mapping[str, Any]) -> str:
        return self.regole.chiave_testo({'citazione_testuale': riga.get('citazione_testuale') or ''})

    def _vive(self, caso: str) -> dict[str, list[tuple[str, str | None, Mapping[str, str]]]]:
        """``{fragment key: [(document_id, case_id, fingerprints)]}`` of the live rows of the case."""
        out: dict[str, list[tuple[str, str | None, Mapping[str, str]]]] = collections.defaultdict(list)
        for x in self.banca.values():
            if x.get('caso_citato') == caso and x.get('proposto_rete') in RETI_VIVE and x.get('citazione_testuale'):
                out[self.chiave(x)].append((x['document_id'], x.get('case_id'), self.impronte(x.get('file'))))
        return out

    @staticmethod
    def segno(r: Mapping[str, Any], rid: str) -> dict[str, Any]:
        """The identifying part of a row for the list of the excluded."""
        return {
            'id': rid,
            'caso': r['caso'],
            'document_id': r['document_id'],
            'case_id': r.get('case_id'),
            'pagina': r.get('pagina'),
            'char_start': r['char_start'],
        }

    def separa(
        self, righe: Iterable[dict[str, Any]], id_di: Callable[[Mapping[str, Any]], str]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """``(kept, excluded)``: the new rows without the copies of the same document."""
        tenute: list[dict[str, Any]] = []
        escluse: list[dict[str, Any]] = []
        vive: dict[str, dict[str, list[tuple[str, str | None, Mapping[str, str]]]]] = {}
        prese: dict[tuple[str, str], list[tuple[str, str, str | None, Mapping[str, str]]]] = collections.defaultdict(
            list
        )
        for r in sorted(righe, key=lambda r: (r['caso'], r['document_id'], int(r['char_start']))):
            rid, caso = id_di(r), r['caso']
            if r['document_id'] in self.d04 or rid in self.s06:
                escluse.append({**self.segno(r, rid), 'perche': 'atto di D04 non ancora scritto, o riga di S06'})
                continue
            if caso not in vive:
                vive[caso] = self._vive(caso)
            k, mie = self.chiave(r), self.impronte(r['file'])
            gia = next(
                (
                    (d, c, p)
                    for d, c, imp in vive[caso][k]
                    if d != r['document_id']
                    for p in [self.regole.stesso_documento(mie, imp)]
                    if p
                ),
                None,
            )
            if gia:
                escluse.append(
                    {
                        **self.segno(r, rid),
                        'uguale_a_documento': gia[0],
                        'uguale_a_case_id': gia[1],
                        'perche': f"{gia[2]}: la citazione c'e' gia', riga viva nell'altra copia",
                    }
                )
                continue
            uguale = next(
                (
                    (i, p)
                    for i, (d, _f, _c, imp) in enumerate(prese[(caso, k)])
                    if d != r['document_id']
                    for p in [self.regole.stesso_documento(mie, imp)]
                    if p
                ),
                None,
            )
            if uguale is None:
                tenute.append(r)
                prese[(caso, k)].append((r['document_id'], r['file'], r.get('case_id'), mie))
                continue
            i, perche = uguale
            altra = next(t for t in tenute if t['document_id'] == prese[(caso, k)][i][0] and self.chiave(t) == k)
            scelta, _ = self.regole.scegli_per_scheda([altra['file'], r['file']])
            tieni, esce = (r, altra) if scelta == r['file'] else (altra, r)
            if tieni is r:
                tenute[tenute.index(altra)] = r
                prese[(caso, k)][i] = (r['document_id'], r['file'], r.get('case_id'), mie)
            escluse.append(
                {
                    **self.segno(esce, id_di(esce)),
                    'uguale_a_documento': tieni['document_id'],
                    'uguale_a_case_id': tieni.get('case_id'),
                    'perche': perche + ', copia scelta dalla scheda',
                }
            )
        altri: dict[str, set[str]] = collections.defaultdict(set)
        for e in escluse:
            if e.get('uguale_a_documento'):
                altri[e['uguale_a_documento']].add(e['case_id'])
        for t in tenute:
            if t['document_id'] in altri:
                t['stesso_documento_case_ids'] = sorted(altri[t['document_id']] - {t.get('case_id')})
        return tenute, escluse


class Caricatore:
    """Turns the new rows into documents of ``corpus_rows``, equal in form to those of S07.

    Args:
        banca_viva: ``{id: row}`` read from the live database.
        data: the date of the load (``AAAA-MM-GG``); it names the execution and seeds the blind sample.
        nuovi_md: the filings that came with D03 (``provenienza.corpus`` D03 instead of D01).
        ocr_prima: the folder of the copies of the filings before the OCR (``training/ocr/prima``); a filing with a copy
            there gets ``provenienza.ocr``.
        documento: the builder of the platform row from a CSV row (default :func:`tracepipe.ricerca.documento_riga`).
        soglia: the distance of the nearest live row (default the S08 threshold).
    """

    def __init__(
        self,
        banca_viva: Mapping[str, Riga],
        data: str,
        nuovi_md: Collection[str] = (),
        ocr_prima: Path | None = None,
        documento: Callable[[dict[str, Any], str], dict[str, Any]] = documento_riga,
        soglia: int = SOGLIA_S08,
    ) -> None:
        self.banca = banca_viva
        self.data = data
        self.nuovi_md = set(nuovi_md)
        self.ocr_prima = ocr_prima
        self.documento = documento
        self.soglia = soglia
        self.per_atto = CoppieVicine.righe_per_atto(banca_viva)

    @staticmethod
    def id_di(r: Mapping[str, Any]) -> str:
        """The id the portal gives the row."""
        return id_riga(r['caso'], r['document_id'], int(r['char_start']))

    def vicina(self, r: Mapping[str, Any], soglia: int | None = None) -> tuple[str, str, int] | None:
        """The nearest live row of the same filing and case within the threshold: ``(code, id, distance)`` or None."""
        soglia = self.soglia if soglia is None else soglia
        v = self.per_atto.get((r['document_id'], r['caso'])) or []
        cs = int(r['char_start'])
        migliore = min(((abs(p - cs), i) for p, i, _ in v), default=None)
        if migliore is None or migliore[0] > soglia:
            return None
        i = migliore[1]
        return self.banca[i].get('codice') or '', i, migliore[0]

    def ultimo_codice(self, caso: str) -> int:
        """The highest number among the codes of the case (``NEU-0300`` -> 300)."""
        pre = PREFISSI[caso]
        numeri = [
            int(m.group(1))
            for x in self.banca.values()
            if x.get('caso_citato') == caso
            for m in [re.fullmatch(rf'{pre}-(\d+)', str(x.get('codice') or ''))]
            if m
        ]
        return max(numeri, default=0)

    def assegnatari(self, caso: str) -> list[str]:
        """Who has rows of the case awaiting judgment, sorted: the new rows are shared among them."""
        return sorted(
            {
                x.get('assegnato_a') or x.get('assegnato_a_in_attesa')
                for x in self.banca.values()
                if x.get('caso_citato') == caso
                and x.get('proposto_rete') in ('lessicale', 'entrambe')
                and not x.get('esito')
                and (x.get('assegnato_a') or x.get('assegnato_a_in_attesa'))
            }
        )

    def documenti(self, righe: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
        """``{id: document}`` for all the rows, as ``recupero_s07.documenti`` (codes after the highest of the case).

        Raises:
            ValueError: an id is already in the database.
        """
        out: dict[str, dict[str, Any]] = {}
        for caso in sorted({r['caso'] for r in righe}):
            n = self.ultimo_codice(caso)
            pre = PREFISSI[caso]
            chi = self.assegnatari(caso)
            rnd = random.Random(f'{caso}-{self.data}-{ESTRAZIONE}')
            mie = sorted(
                (r for r in righe if r['caso'] == caso), key=lambda r: (r['document_id'], int(r['char_start']))
            )
            for k, r in enumerate(mie):
                rid = self.id_di(r)
                if rid in self.banca:
                    raise ValueError(f'row already in the database: {rid}')
                d = self.documento(dict(r), caso)
                n += 1
                prov: dict[str, Any] = {
                    'corpus': 'D03' if r['file'] in self.nuovi_md else 'D01',
                    'estrazione': ESTRAZIONE,
                    'tipo': '',
                    'principi': {},
                    'composizione': '',
                    'seguito': '',
                }
                if self.ocr_prima is not None and (self.ocr_prima / Path(r['file']).name).exists():
                    prov['ocr'] = self.data
                d.update(
                    {
                        'corroborazione': 'descrizione',
                        'ordine': random.Random(rid).random(),
                        'codice': f'{pre}-{n:04d}',
                        'assegnato_a_in_attesa': chi[k % len(chi)] if chi else None,
                        'campione_cieco': rnd.random() < QUOTA_CAMPIONE_CIECO,
                        'incerta': False,
                        'provenienza': prov,
                        'motivo_aggiunta': MOTIVO,
                        'causa_s08': CAUSA,
                        'esecuzione_id': f'{caso}__nomi__{self.data}-{ESTRAZIONE}',
                        'proposto_rete': 'descrittiva',
                        'trovata_per_descrizione': True,
                        'regola_descrittiva': r.get('regola_descrittiva', ''),
                        'testo_trovato': r.get('testo_trovato', ''),
                        'c04_resta': r['c04_resta'],
                        'c04_motivo': r['c04_motivo'],
                    }
                )
                if r.get('stesso_documento_case_ids'):
                    d['stesso_documento_case_ids'] = r['stesso_documento_case_ids']
                v = self.vicina(r)
                if v:
                    d.update({'s08_vicina_codice': v[0], 's08_vicina_id': v[1], 's08_vicina_distanza': v[2]})
                out[rid] = d
        return out


def verifiche(
    docs: Mapping[str, Mapping[str, Any]], righe: Sequence[Mapping[str, Any]], gia: Collection[str]
) -> list[tuple[str, bool, str]]:
    """``[(description, outcome, detail)]``: no id already in the database, unique ids and codes, the proof cases."""
    v = [
        ("nessun id gia' in banca (lettura dal vivo)", not gia, f"{len(gia)} gia' presenti"),
        (
            'id e codici unici',
            len(docs) == len(righe) and len({d['codice'] for d in docs.values()}) == len(docs),
            f'{len(docs)} documenti per {len(righe)} righe',
        ),
    ]
    for caso, fine, pagina, inizio, viva in ATTESE:
        trovate = [
            d
            for d in docs.values()
            if d['caso_citato'] == caso
            and d['document_id'].endswith(fine)
            and d['proposto_pagina'] == pagina
            and d['char_start'] == inizio
            and d.get('s08_vicina_id', '').endswith(f'__{viva}')
        ]
        dettaglio = 'mancante'
        if trovate:
            dettaglio = trovate[0]['codice']
            if 's08_vicina_codice' in trovate[0]:
                dettaglio += f' (vicina {trovate[0]["s08_vicina_codice"]} a {trovate[0]["s08_vicina_distanza"]})'
        v.append(
            (
                f'{caso} ...{fine} p. {pagina} (char {inizio}, coppia con la viva a {viva}) presente',
                len(trovate) == 1,
                dettaglio,
            )
        )
    return v


@dataclass
class EsitoCaricamento:
    """What a run of :class:`CaricaS08` did.

    Attributes:
        documenti: ``{id: document}`` to write.
        escluse: the new rows left out as copies of the same document or postponed.
        verifiche: the checks ``(description, outcome, detail)``.
        copia: the path of the list of the ids to create (a copy to go back), when written.
        scritti: how many documents were written.
    """

    documenti: dict[str, dict[str, Any]] = field(default_factory=dict)
    escluse: list[dict[str, Any]] = field(default_factory=list)
    verifiche: list[tuple[str, bool, str]] = field(default_factory=list)
    copia: Path | None = None
    scritti: int = 0

    @property
    def ok(self) -> bool:
        return all(v[1] for v in self.verifiche)


class CaricaS08:
    """The S08 loader: separate the copies, build the documents, check, and (with ``scrivi``) create the rows.

    Without ``scrivi`` it is a PREVIEW: counts, two whole rows, the checks, and nothing is written to the database.

    Args:
        config: paths (the lists go under ``training/s08``).
        banca: the live database (read the rows, check the ids, write with ``scrivi``).
        sorgente: the rebuilt new rows.
        regole: the copy rules.
        nuovi_md: the filings of D03.
        data: the date of the load.
        scrivi: write to the database.
        orologio: the clock of the copy name.
        stampa: where the screen lines go.
    """

    def __init__(
        self,
        config: Config,
        banca: BancaDati,
        sorgente: SorgenteNuove,
        regole: RegoleCopie,
        nuovi_md: Collection[str] = (),
        data: str = '2026-10-05',
        scrivi: bool = False,
        orologio: Callable[[], datetime.datetime] = datetime.datetime.now,
        stampa: Stampa = _stampa,
    ) -> None:
        self.config = config
        self.banca = banca
        self.sorgente = sorgente
        self.regole = regole
        self.nuovi_md = nuovi_md
        self.data = data
        self.scrivi = scrivi
        self.orologio = orologio
        self.stampa = stampa

    @property
    def cartella(self) -> Path:
        return self.config.training / 's08'

    def righe_vive(self) -> dict[str, dict[str, Any]]:
        """The live rows of every case, values made JSON-friendly."""
        out: dict[str, dict[str, Any]] = {}
        for caso in self.config.casi:
            for rid, r in self.banca.righe('corpus_rows', [('caso_citato', '==', caso)]):
                out[rid] = json.loads(json.dumps(r, default=str))
        return out

    def copia_prima(self, ids: Iterable[str]) -> Path:
        """The copy before the write: here all the rows are NEW (created, never updated), so the copy is the list of the
        ids to be created, to delete them one by one if we must go back."""
        self.cartella.mkdir(parents=True, exist_ok=True)
        f = self.cartella / f'copia_prima_carica_s08_{self.orologio():%Y%m%d_%H%M%S}.json'
        f.write_text(json.dumps({'data': self.data, 'creati': sorted(ids)}, indent=1), encoding='utf-8')
        return f

    def anteprima(self, esito: EsitoCaricamento, soglia: int = SOGLIA_S08) -> None:
        """The preview on screen."""
        docs = esito.documenti
        per = collections.Counter(d['caso_citato'] for d in docs.values())
        con = collections.Counter(d['caso_citato'] for d in docs.values() if 's08_vicina_id' in d)
        self.stampa(f'{len(docs)} new rows (outcome «nuova» of the TSV)')
        for caso in self.config.casi:
            self.stampa(
                f'  {caso:20s} {per[caso]:4d}   with a live row within {soglia}: {con[caso]:4d}   '
                f'alone: {per[caso] - con[caso]:4d}'
            )
        self.stampa(
            f'  TOTAL                {len(docs):4d}   with a live row within {soglia}: {sum(con.values()):4d}   '
            f'alone: {len(docs) - sum(con.values()):4d}'
        )
        resta = sum(1 for d in docs.values() if d['c04_resta'])
        self.stampa(f'  C04 clue: {resta} stay, {len(docs) - resta} would be discarded (a clue, not an exclusion)')
        for rid in list(docs)[:2]:
            self.stampa(f'\n--- {rid}\n' + json.dumps(docs[rid], ensure_ascii=False, indent=1, default=str))
        for descr, ok, det in esito.verifiche:
            self.stampa(('OK     ' if ok else 'FAILED ') + f'{descr}: {det}')

    def esegui(self) -> EsitoCaricamento:
        """Build and check; with ``scrivi`` create the rows (list of ids first)."""
        viva = self.righe_vive()
        car = Caricatore(viva, self.data, self.nuovi_md, self.config.training / 'ocr' / 'prima')
        righe, escluse = Copie(viva, self.regole, self.config.radice).separa(self.sorgente.righe(), car.id_di)
        esito = EsitoCaricamento(escluse=escluse)
        self.cartella.mkdir(parents=True, exist_ok=True)
        with open(self.cartella / 'escluse_copie_s08.jsonl', 'w', encoding='utf-8') as h:
            for e in escluse:
                h.write(json.dumps(e, ensure_ascii=False, default=str) + '\n')
        motivi = collections.Counter(e['perche'].split(':')[0] for e in escluse).most_common()
        self.stampa(f'copies of the same document and deferred rows (D04, S06): {len(escluse)} excluded, {motivi}')
        esito.documenti = car.documenti(righe)
        gia = self.banca.esistenti('corpus_rows', esito.documenti)
        (self.cartella / 'documenti_s08_da_scrivere.json').write_text(
            json.dumps(esito.documenti, ensure_ascii=False, default=str), encoding='utf-8'
        )
        esito.verifiche = verifiche(esito.documenti, righe, gia)
        self.anteprima(esito)
        if not self.scrivi:
            self.stampa('\nPREVIEW: nothing written')
            return esito
        if not esito.ok:
            raise RuntimeError('checks failed: nothing written')
        esito.copia = self.copia_prima(esito.documenti)
        self.stampa(f'safety copy: {esito.copia}')
        ora = self.banca.ora_del_server
        scritture = [
            Scrittura('create', 'corpus_rows', rid, {**d, 'creato_il': ora}) for rid, d in esito.documenti.items()
        ]
        esito.scritti = self.banca.scrivi_a_lotti(scritture, LOTTO)
        self.stampa(f'   written: {esito.scritti}/{len(scritture)}')
        return esito
