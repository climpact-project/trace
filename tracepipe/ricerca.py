"""The search by name and its comparison with the platform (``ricerca``: search).

- :class:`RicercaPerNome`: the lexical network of ``tools/cerca.py --solo-lessicale``: every occurrence of the declared
  forms in every document (exhaustive by construction, not a ranking), close matches merged into one citation, the
  four dimensions proposed, the date filter, duplicates removed, body or footnote read from the PDF, the CSV of the
  candidates with its discards and its reading instructions. The semantic network (embedding model, vector index,
  reranker) is out of scope: with ``solo_lessicale=False`` the class refuses to run.
- :class:`UnioneRighe`: the comparison of ``tools/unisci_e_aggiungi.py`` between a new search by name and the rows on
  the platform: groups without a row are NEW rows (code after the highest of the case, assigned in turn, one in five
  blind), groups with two or more rows are a SPLIT citation (the judged row stays, the others are marked ``fusa``).
  Nothing is deleted, no verdict is touched; without ``scrivi`` it only prints and writes the report file.
"""

from __future__ import annotations

import collections
import csv
import datetime
import json
import random
import re
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .banca import BancaDati, Scrittura
from .caso import forma_regex
from .config import Config
from .controlli import PREFISSI
from .corpus import PAGINA_MD, PosizioniDopoOcr
from .dimensioni import PosizioneNelPdf, dimensioni

PRIMA, DOPO = 200, 260
"""Characters of context around an occurrence in the ``citazione_testuale`` column (tools/cerca.py)."""
FUSIONE = 200
"""Matches closer than this are ONE citation (tools/cerca.py FUSIONE)."""
NOMINALI = ('lessicale', 'entrambe')
"""The networks that found the NAME of the case."""

Stampa = Callable[[str], None]


def _stampa(testo: str) -> None:
    print(testo, flush=True)


def _uno_spazio(v: Any) -> str:
    return re.sub(r'\s+', ' ', str(v or '')).strip()


# the cited case as the search reads it


def leggi_caso(percorso: Path, con_alternative: bool = False) -> dict[str, Any]:
    """The query specification: forms, probes, excluded wordings (tools/cerca.py ``leggi_caso``).

    Only what the file declares, each field apart; dates become ``YYYY-MM-DD``; ``probe_alternativa`` becomes a probe
    of its own with ``con_alternative``.
    """
    dati = yaml.safe_load(percorso.read_text(encoding='utf-8')) or {}
    conf: dict[str, Any] = {'forme': [], 'sonde': [], 'escluse': []}
    for chiave in (
        'nome',
        'codebook_versione',
        'data_decisione',
        'escludi_case_id',
        'case',
        'versione_file',
        'filtro_data_documento',
    ):
        if chiave in dati and dati[chiave] is not None:
            v = dati[chiave]
            if isinstance(v, (datetime.date, datetime.datetime)):
                v = v.isoformat()[:10]
            elif not isinstance(v, (list, tuple)):
                v = str(v)
            conf[chiave] = v
    conf['forme'] = [str(f).strip() for f in (dati.get('forme') or []) if str(f).strip()]
    for s in dati.get('semantic_queries') or []:
        if not isinstance(s, dict) or not _uno_spazio(s.get('testo')):
            continue
        sid = str(s.get('id') or '').strip()
        titolo = _uno_spazio(s.get('titolo'))
        conf['sonde'].append({'id': sid, 'titolo': titolo, 'testo': _uno_spazio(s.get('testo'))})
        alt = _uno_spazio(s.get('probe_alternativa'))
        if con_alternative and alt:
            conf['sonde'].append({'id': f'{sid}__alt', 'titolo': f'{titolo} [2a formulazione]', 'testo': alt})
    for e in dati.get('formulazioni_escluse') or []:
        if not isinstance(e, dict) or not _uno_spazio(e.get('testo')):
            continue
        per = str(e.get('per') or '').strip()
        escl = {'per': per, 'id': str(e.get('id') or '').strip(), 'testo': _uno_spazio(e.get('testo'))}
        conf['escluse'].append(escl)
        if con_alternative:
            conf['escluse'].append(dict(escl, per=f'{per}__alt'))
    return conf


# the document


def front_matter(testo: str) -> tuple[dict[str, str], int]:
    """The front matter of a markdown file and the offset where the body starts."""
    meta: dict[str, str] = {}
    fine = testo.find('\n---\n', 4)
    if fine < 0:
        return meta, 0
    for riga in testo[4:fine].split('\n'):
        m = re.match(r'^([a-z_0-9]+):\s*(.*)$', riga)
        if m:
            v = m.group(2).strip()
            if v.startswith("'") and v.endswith("'") and len(v) >= 2:
                v = v[1:-1].replace("''", "'")
            meta[m.group(1)] = v
    return meta, fine + 5


def segni_pagina(testo: str) -> list[tuple[int, int]]:
    """``(offset, page number)`` of every page mark."""
    return [(m.start(), int(m.group(1))) for m in PAGINA_MD.finditer(testo)]


def pagina_di(marks: Sequence[tuple[int, int]], off: int) -> int:
    p = 1
    for pos, n in marks:
        if pos <= off:
            p = n
        else:
            break
    return p


def blocco_pagina(testo: str, marks: Sequence[tuple[int, int]], off: int) -> tuple[str, int]:
    """(raw text of the page of ``off``, offset of ``off`` inside it)."""
    inizio, fine = 0, len(testo)
    for i, (pos, _) in enumerate(marks):
        if pos <= off:
            inizio = pos
            fine = marks[i + 1][0] if i + 1 < len(marks) else len(testo)
        else:
            break
    return testo[inizio:fine], off - inizio


def finestra_pagina(testo: str, marks: Sequence[tuple[int, int]], off: int) -> str:
    """The text of the page of the occurrence, footnotes included, without the page mark."""
    return PAGINA_MD.sub(' ', blocco_pagina(testo, marks, off)[0]).strip()


def e_nome(testo: str, m: re.Match[str]) -> bool:
    """Does the match NAME the case (not only an identifier: docket number, ECLI, the name inside a web address)?"""
    s = m.group(0)
    if re.search(r'[^\x00-\x7f]', s):
        return True
    if not re.search(r'[a-z]{3}', s):
        return False
    prima = testo[max(0, m.start() - 60) : m.start()]
    coda = re.search(r'\S*$', prima).group(0)  # type: ignore[union-attr]
    return not ('/' in coda or 'www' in coda.lower() or 'http' in coda.lower())


def fondi(testo: str, grezze: Iterable[re.Match[str]]) -> list[list[Any]]:
    """ONE CITATION, ONE ROW: ``[first match, forms, start of the last match]`` per citation.

    Matches within 200 characters of the start of the group are one citation; since 29/09/2026 an IDENTIFIER within
    200 characters of the previous match continues it too, while a NAME beyond 200 characters opens a new one.
    """
    fuse: list[list[Any]] = []
    fine: int | None = None
    for m in grezze:
        if fuse and (
            m.start() - fuse[-1][0].start() < FUSIONE
            or (fine is not None and m.start() - fine < FUSIONE and not e_nome(testo, m))
        ):
            fuse[-1][1].append(m.group(0))
            fuse[-1][2] = m.start()
        else:
            fuse.append([m, [m.group(0)], m.start()])
        fine = m.end()
    return fuse


def data_documento(meta: Mapping[str, Any]) -> str:
    """YYYY-MM-DD from the name of the source file (``.../2024/20240417_...``), else empty."""
    m = re.search(r'/(\d{4})(\d{2})(\d{2})_', str(meta.get('url_origine') or ''))
    return f'{m.group(1)}-{m.group(2)}-{m.group(3)}' if m else ''


def modello_forme(forme: Iterable[str]) -> re.Pattern[str]:
    """Every form in one case-insensitive pattern (CJK forms allow spaces between characters)."""
    return re.compile('|'.join(forma_regex(f) for f in forme), re.I)


# the search by name


def chiave_testo(r: Mapping[str, Any]) -> str:
    """The first 400 characters of the passage, spaces joined and lower case: the key of the deduplication."""
    return re.sub(r'\s+', ' ', r['citazione_testuale']).strip().lower()[:400]


def deduplica(
    righe: list[dict[str, Any]], scarti: list[dict[str, Any]], per_atto: bool = False
) -> list[dict[str, Any]]:
    """The kept rows; the copies go to ``scarti`` ("copia di un altro frammento") and the first counts its ``copie``.

    By default (the live ``cerca.py``) a passage is a copy when its key equals one already seen anywhere in the corpus.
    With ``per_atto`` (03/10/2026, external review; ``tools/cerca_s05_per_atto.deduplica``) only a copy inside the same
    document is dropped: the same text in another document stays, and carries ``stesso_testo_di`` =
    ``<document_id>__<char_start>`` of the first passage with that text (empty on the first; the platform row id is
    ``<case>__`` plus this). Measured on 03/10/2026: 425 of the 438 copies dropped were in another document
    (``training/misure/DEDUP-FRA-ATTI.md``).
    """
    visti: dict[Any, dict[str, Any]] = {}
    primo: dict[str, dict[str, Any]] = {}
    uniche = []
    for r in righe:
        testo = chiave_testo(r)
        k: Any = (r.get('document_id') or '', testo) if per_atto else testo
        if k in visti:
            visti[k]['copie'] = int(visti[k].get('copie') or 1) + 1
            r['motivo_scarto'] = 'copia di un altro frammento'
            scarti.append(r)
            continue
        r['copie'] = 1
        if per_atto:
            p = primo.setdefault(testo, r)
            r['stesso_testo_di'] = '' if p is r else f'{p.get("document_id", "")}__{p.get("char_start", "")}'
        visti[k] = r
        uniche.append(r)
    return uniche


@dataclass
class EsitoRicerca:
    """The rows of the CSV, the discards, and the counts printed at the end."""

    righe: list[dict[str, Any]] = field(default_factory=list)
    scarti: list[dict[str, Any]] = field(default_factory=list)
    anteriori: int = 0
    duplicati: int = 0
    uscita: Path | None = None
    codice: int = 0


class RicercaPerNome:
    """The lexical network of the search tool (``tools/cerca.py --solo-lessicale``).

    Args:
        config: the project root.
        caso: the case name (``urgenda``) or the path of its file, as given on the command line.
        uscita: the CSV, relative to the root (default ``index/candidati_<case>.csv``).
        solo_decisioni: only decisions and orders.
        tipo_atto: filing types separated by commas.
        con_anteriori: keep the filings before the decision.
        con_alternative: read ``probe_alternativa`` too (no effect on the lexical network).
        solo_lessicale: must be True: the semantic network is not part of the package.
        dedup_per_atto: drop a copy only inside the same document, keep the same text in another one with
            ``stesso_testo_di`` (see :func:`deduplica`; not in use: the live search drops copies across the corpus).
        stampa: where the screen lines go.
        orologio: the clock of the durations printed.
    """

    def __init__(
        self,
        config: Config,
        caso: str,
        uscita: str = '',
        solo_decisioni: bool = False,
        tipo_atto: str = '',
        con_anteriori: bool = False,
        con_alternative: bool = False,
        solo_lessicale: bool = True,
        dedup_per_atto: bool = False,
        stampa: Stampa = _stampa,
        orologio: Callable[[], float] = time.time,
    ) -> None:
        if not solo_lessicale:
            raise NotImplementedError('la rete semantica non fa parte del pacchetto: si usa tools/cerca.py')
        self.config = config
        self.caso = caso
        self.uscita = uscita
        self.solo_decisioni = solo_decisioni
        self.tipo_atto = tipo_atto
        self.con_anteriori = con_anteriori
        self.con_alternative = con_alternative
        self.dedup_per_atto = dedup_per_atto
        self.stampa = stampa
        self.orologio = orologio

    @property
    def radice(self) -> Path:
        return self.config.radice

    def tipi(self) -> set[str] | None:
        if self.solo_decisioni:
            return {'decisione', 'ordinanza'}
        if self.tipo_atto:
            return {t.strip().lower() for t in self.tipo_atto.split(',') if t.strip()}
        return None

    def rete_lessicale(self, forme: Sequence[str], escludi: Any = '', tipi: set[str] | None = None) -> list[dict]:
        """Every occurrence in every markdown file, close matches merged (``rete_lessicale``)."""
        patt = modello_forme(forme)
        esclusi = [escludi] if isinstance(escludi, str) else list(escludi or [])
        esclusi = [str(x).lower() for x in esclusi if str(x).strip()]
        fuori = []
        for md in sorted((self.radice / 'markdown').rglob('*.md')):
            testo = md.read_text(encoding='utf-8', errors='replace')
            meta, inizio = front_matter(testo)
            cid = (meta.get('case_id') or '').lower()
            if any(x in cid for x in esclusi):
                continue
            if tipi and (meta.get('tipo_atto') or '').strip().lower() not in tipi:
                continue
            grezze = list(patt.finditer(testo, inizio))
            if not grezze:
                continue
            marks = segni_pagina(testo)
            for m, forme_qui, _ in fondi(testo, grezze):
                blocco, off_rel = blocco_pagina(testo, marks, m.start())
                fuori.append(
                    {
                        'dim': dimensioni(meta, blocco, off_rel, testo[: m.start()]),
                        'meta': meta,
                        'file': str(md.relative_to(self.radice)),
                        'char_start': m.start(),
                        'pagina': pagina_di(marks, m.start()),
                        'forma': ' + '.join(dict.fromkeys(forme_qui)),
                        'verbatim': re.sub(
                            r'\s+', ' ', PAGINA_MD.sub(' ', testo[max(inizio, m.start() - PRIMA) : m.start() + DOPO])
                        ).strip(),
                        'finestra': finestra_pagina(testo, marks, m.start()),
                        'rete': 'lessicale',
                        'punteggio': '',
                    }
                )
        return fuori

    @staticmethod
    def riga_csv(r: Mapping[str, Any], cb_versione: str) -> dict[str, Any]:
        """One CSV row, columns in the live order."""
        m = r['meta']
        return {
            'case_id': m.get('case_id', ''),
            'case_name': m.get('case_name', ''),
            'giurisdizioni': m.get('giurisdizioni', ''),
            'document_id': m.get('document_id', ''),
            'tipo_atto': m.get('tipo_atto', ''),
            'tipo_atto_sabin': m.get('tipo_atto_sabin', ''),
            'data': m.get('data_deposito', ''),
            'pagina': r['pagina'],
            'data_documento': data_documento(m),
            'rete': r['rete'],
            'sonda': r.get('sonda', ''),
            'punteggio': r['punteggio'],
            'punteggio_riordino': '',
            'copie': '',
            'anteriore': '',
            'punteggio_escluse': r.get('punteggio_escluse', ''),
            'margine': r.get('margine', ''),
            'sospetto': r.get('sospetto', ''),
            'forma_trovata': r['forma'],
            'citazione_testuale': r['verbatim'],
            'verbatim_intero': r.get('verbatim_intero', ''),
            'finestra_pagina': r['finestra'],
            'chi_cita_auto': r['dim']['chi_cita_auto'],
            'posizione_auto': '',
            'sede_auto': r['dim']['sede_auto'],
            'dimensioni_confidenza': r['dim']['dimensioni_confidenza'],
            'chi_parla': r['dim']['chi_cita_auto'],
            'posizione': '',
            'sede': r['dim']['sede_auto'],
            'tipo_citazione': '',
            'annidata': '',
            'proposizione_sostenuta': '',
            'confidenza': '',
            'note': '',
            'file': r['file'],
            'char_start': r['char_start'],
            'url_documento': m.get('url_documento', ''),
            'codebook_versione': cb_versione,
        }

    def esegui(self) -> EsitoRicerca:
        """The whole run: search, filters, PDF positions, CSV, discards, instructions, screen lines."""
        s = self.stampa
        percorso = Path(self.caso)
        if not percorso.exists():
            percorso = self.radice / 'cited-cases' / f'{self.caso}.yaml'
        if not percorso.exists():
            disponibili = sorted(p.stem for p in (self.radice / 'cited-cases').glob('*.yaml'))
            s(f'Caso citato non trovato: {self.caso}')
            s(f'Disponibili: {", ".join(disponibili) or "nessuno"}')
            return EsitoRicerca(codice=1)
        conf = leggi_caso(percorso, con_alternative=self.con_alternative)
        tipi = self.tipi()
        cb_file = self.radice / 'codebook' / 'citazioni.yaml'
        cb_testo = cb_file.read_text(encoding='utf-8') if cb_file.exists() else ''
        m = re.search(r'^versione:\s*(.+)$', cb_testo, re.M)
        cb_versione = m.group(1).strip() if m else 'assente'
        m = re.search(r'^approvato_da:\s*(.+)$', cb_testo, re.M)
        cb_approvato = m.group(1).strip() if m else 'null'
        if cb_approvato in ('null', '', 'None'):
            s(f'codebook    : {cb_versione}   NON ANCORA APPROVATO — le codifiche prodotte ora non sono definitive')
        else:
            s(f'codebook    : {cb_versione}   approvato da {cb_approvato}')
        nome = conf.get('nome', Path(self.caso).stem)
        s(f'caso citato : {nome}')
        s(f'forme       : {len(conf["forme"])}')
        s(f'sonde       : {len(conf["sonde"])}')
        if tipi:
            s(f'FILTRO      : solo {", ".join(sorted(tipi))}')
        s('')
        s('rete lessicale (esaustiva)…')
        t0 = self.orologio()
        less = self.rete_lessicale(conf['forme'], conf.get('escludi_case_id', ''), tipi)
        s(f'  {len(less):,} occorrenze in {self.orologio() - t0:.0f}s\n')

        righe = [self.riga_csv(r, cb_versione) for r in less]
        esito = EsitoRicerca()
        scarti = esito.scarti
        anteriori: list[dict[str, Any]] = []
        dmin = (conf.get('data_decisione') or '').strip()[:10]
        if dmin and not self.con_anteriori:
            tenute = []
            for r in righe:
                d = (r.get('data') or '').strip()[:10]
                if r['rete'] not in NOMINALI and d and d < dmin:
                    r['anteriore'] = 'si'
                    r['motivo_scarto'] = f'anteriore al {dmin}'
                    anteriori.append(r)
                    scarti.append(r)
                elif conf.get('filtro_data_documento') and r.get('data_documento') and r['data_documento'] < dmin:
                    r['anteriore'] = 'si'
                    r['motivo_scarto'] = f'documento del {r["data_documento"]}, anteriore alla pronuncia del {dmin}'
                    anteriori.append(r)
                    scarti.append(r)
                else:
                    tenute.append(r)
            righe = tenute
        uniche = deduplica(righe, scarti, per_atto=self.dedup_per_atto)
        esito.duplicati = len(righe) - len(uniche)
        righe = uniche
        gemelle = sum(1 for r in righe if r.get('stesso_testo_di'))
        if gemelle:
            s(f'stesso testo in un altro atto: {gemelle:,} righe tenute, con stesso_testo_di')
        # the reranker runs only on semantic candidates: none in the lexical network
        righe.sort(key=lambda x: (x['file'], x['pagina']))
        s('\ncorpo o nota (dal PDF)…')
        t0 = self.orologio()
        try:
            import fitz  # noqa: F401
        except ImportError:
            s('  FERMO: manca PyMuPDF, la colonna corpo/nota non si puo')
            s('  calcolare. Installalo e rilancia:')
            s('    ./.venv/bin/pip install pymupdf')
            esito.codice = 1
            return esito
        with PosizioneNelPdf() as pdf:
            for r in righe:
                f = self.radice / r['file'].replace('markdown/', 'documents/').replace('.md', '.pdf')
                if f.exists():
                    pos, cpos = pdf.posizione(f, int(r['pagina']), r['citazione_testuale'])
                else:
                    pos, cpos = 'non_determinabile', 'bassa'
                r['posizione_auto'] = pos
                r['posizione'] = pos
                if cpos == 'bassa' and r['dimensioni_confidenza'] != 'bassa':
                    r['dimensioni_confidenza'] = 'media'
        s(f'  {self.orologio() - t0:.0f}s')
        righe.sort(key=lambda x: (x['case_name'], x['document_id'], x['pagina']))
        out = self.radice / (self.uscita or f'index/candidati_{Path(self.caso).stem}.csv')
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open('w', newline='', encoding='utf-8') as f:
            for r in righe:
                r.pop('verbatim_intero', None)
            w = csv.DictWriter(f, fieldnames=list(righe[0].keys()))
            w.writeheader()
            w.writerows(righe)
        esito.righe, esito.anteriori, esito.uscita = righe, len(anteriori), out
        self.riepilogo(esito, dmin, nome, cb_versione, cb_testo)
        return esito

    def riepilogo(self, esito: EsitoRicerca, dmin: str, nome: str, cb_versione: str, cb_testo: str) -> None:
        """The counts at the end, the discards file and the reading instructions next to the CSV."""
        s, righe, out = self.stampa, esito.righe, esito.uscita
        assert out is not None
        s(f'RIGHE      : {len(righe):,}')
        for k, v in collections.Counter(r['rete'] for r in righe).most_common():
            s(f'  {k:12s}: {v:,}')
        s(f'documenti  : {len({r["document_id"] for r in righe}):,}')
        s('sede (proposta):')
        for k, v in collections.Counter(r['sede_auto'] for r in righe).most_common():
            s(f'  {k:18s}: {v:,}')
        n = collections.Counter(r['posizione_auto'] for r in righe)
        s(f'posizione  : corpo {n.get("corpo", 0):,}   nota {n.get("nota", 0):,}')
        if dmin and not self.con_anteriori:
            s(
                f'anteriori  : {esito.anteriori:,} candidati in documenti '
                f'precedenti al {dmin} — tolti (con --con-anteriori restano)'
            )
        if esito.duplicati:
            s(f'duplicati  : {esito.duplicati:,} righe erano copie dello stesso testo')
        sosp = sum(1 for r in righe if r['sospetto'])
        if sosp:
            s(
                f'SOSPETTE   : {sosp:,} righe piu vicine a una formulazione esclusa '
                'che alla sonda — da leggere per prime'
            )
        b = sum(1 for r in righe if r['dimensioni_confidenza'] == 'bassa')
        if b:
            s(f'da guardare per prime: {b:,} righe con confidenza bassa')
        s(f'casi       : {len({r["case_id"] for r in righe}):,}')
        s(f'uscita     : {out}')
        if esito.scarti:
            fs = out.with_name(out.stem + '.SCARTI.csv')
            campi = [*list(righe[0].keys()), 'motivo_scarto']
            with fs.open('w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=campi, extrasaction='ignore')
                w.writeheader()
                for r in esito.scarti:
                    r.setdefault('copie', '')
                    r.setdefault('anteriore', '')
                    w.writerow({k: r.get(k, '') for k in campi})
            s(f'scarti     : {fs}')
            for k, v in collections.Counter(
                r.get('motivo_scarto', '?').split(' ')[0] for r in esito.scarti
            ).most_common():
                s(f'   {v:>6,}  {k}')
        istr = re.search(r'^istruzioni_lettura:\s*\|(.*)$', cb_testo, re.M | re.S)
        if istr:
            gemello = out.with_suffix('.ISTRUZIONI.md')
            gemello.write_text(
                f'# Come classificare — codebook {cb_versione}\n\n'
                f'Caso citato: **{nome}**\n\n'
                f'Righe da classificare: {len(righe):,}\n\n'
                + '\n'.join(riga[2:] if riga.startswith('  ') else riga for riga in istr.group(1).split('\n')).strip()
                + '\n\n---\n\nCategorie e casi limite: `codebook/citazioni.yaml`.\n',
                encoding='utf-8',
            )
            s(f'istruzioni : {gemello}')


# the comparison with the platform (tools/unisci_e_aggiungi.py)

DATA_PRIMA_RICERCA = '2026-09-29'
"""The corrected search of 29/09/2026 (S02); later dates are S03."""


def id_riga(caso: str, document_id: str, char_start: Any) -> str:
    """The row id the portal computes, character for character (tools/pubblica.py ``id_riga``)."""
    return re.sub(r'[/\s]+', '_', f'{caso}__{document_id}__{char_start}')[:400]


def _num(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def documento_riga(r: Mapping[str, Any], caso: str, scartata: str = '') -> dict[str, Any]:
    """A platform row out of a CSV row (tools/pubblica.py ``documento``): the machine proposals, never overwritten."""
    pagina = int(r['pagina']) if str(r.get('pagina', '')).strip().isdigit() else 0
    inizio = int(r['char_start']) if str(r.get('char_start', '')).strip().lstrip('-').isdigit() else 0
    tipo = r.get('tipo_citazione') or ''
    conf = r.get('confidenza') or ''
    rete = r.get('rete') or ''
    return {
        'caso_citato': caso,
        'case_id': r.get('case_id', ''),
        'case_name': r.get('case_name', ''),
        'giurisdizioni': r.get('giurisdizioni', ''),
        'document_id': r.get('document_id', ''),
        'tipo_atto': r.get('tipo_atto', ''),
        'tipo_atto_sabin': r.get('tipo_atto_sabin', ''),
        'data': r.get('data', ''),
        'url_documento': r.get('url_documento', ''),
        'file': r.get('file', ''),
        'file_pdf': re.sub(r'\.md$', '.pdf', re.sub(r'^markdown/', 'documents/', r.get('file', ''))),
        'char_start': inizio,
        'proposto_pagina': pagina,
        'proposto_forma_trovata': r.get('forma_trovata', ''),
        'proposto_citazione_testuale': r.get('citazione_testuale', ''),
        'finestra_pagina': r.get('finestra_pagina', ''),
        'proposto_tipo_citazione': tipo,
        'proposto_chi_parla': r.get('chi_parla', ''),
        'proposto_annidata': str(r.get('annidata', '')).lower() == 'true',
        'proposto_proposizione': r.get('proposizione_sostenuta', ''),
        'proposto_confidenza': conf,
        'proposto_rete': rete,
        'proposto_note': r.get('note', ''),
        'proposto_posizione': r.get('posizione_auto', ''),
        'proposto_sede': r.get('sede_auto', ''),
        'proposto_chi_cita': r.get('chi_cita_auto', ''),
        'dimensioni_confidenza': r.get('dimensioni_confidenza', ''),
        'sonda': r.get('sonda', ''),
        'punteggio': _num(r.get('punteggio')),
        'punteggio_riordino': _num(r.get('punteggio_riordino')),
        'punteggio_escluse': _num(r.get('punteggio_escluse')),
        'margine': _num(r.get('margine')),
        'sospetto': r.get('sospetto', ''),
        'copie': int(r['copie']) if str(r.get('copie', '')).strip().isdigit() else 1,
        'anteriore': (r.get('anteriore') or '') == 'si',
        'codebook_versione': r.get('codebook_versione', ''),
        'esito': None,
        'validato_da': None,
        'validato_il': None,
        'nel_campione': False,
        'integrale': tipo == 'implicita' or conf == 'bassa' or rete == 'semantica',
        'doppia_codifica': False,
        'strato': '|'.join([tipo or 'ignoto', conf or 'ignota', rete or 'ignota']),
        'scartato': bool(scartata),
        'motivo_scarto': scartata,
    }


Riga = tuple[str, dict[str, Any]]
"""(platform row id, fields)."""


@dataclass
class EsitoUnione:
    """The decisions of one case: rows to add, split citations, rows without a group."""

    caso: str
    nuove: dict[str, dict[str, Any]] = field(default_factory=dict)
    spezzate: list[tuple[Riga, list[Riga], int]] = field(default_factory=list)
    orfane: list[tuple[str | None, dict[str, Any]]] = field(default_factory=list)
    piu_nomi: int = 0
    nominali: int = 0
    nella_ricerca: int = 0
    ultimo_codice: int = 0
    validatori: int = 0


class UnioneRighe:
    """Merge the split citations and add the missing ones (``tools/unisci_e_aggiungi.py``).

    Args:
        config: the project root.
        banca: the platform database.
        data: the date of the search to compare (``index/nomi_<case>_<date>b.csv``).
        casi: the cases (default all six).
        scrivi: write (``--scrivi``); otherwise only counts and the report file.
        stampa: where the screen lines go.
    """

    def __init__(
        self,
        config: Config,
        banca: BancaDati,
        data: str = DATA_PRIMA_RICERCA,
        casi: Sequence[str] = (),
        scrivi: bool = False,
        stampa: Stampa = _stampa,
    ) -> None:
        self.config = config
        self.banca = banca
        self.data = data
        self.casi = list(casi) or list(PREFISSI)
        self.scrivi = scrivi
        self.stampa = stampa
        self.ocr = PosizioniDopoOcr(config.radice)

    @property
    def esecuzione(self) -> str:
        return f'nomi__{self.data}'

    @staticmethod
    def gruppi_del_documento(
        md: Path, patt: re.Pattern[str]
    ) -> tuple[str, list[re.Match[str]], dict[int, int], list[int]]:
        """(text, matches, group of each match by start, start of each group), with the rule of :func:`fondi`."""
        testo = md.read_text(encoding='utf-8', errors='replace')
        _, inizio = front_matter(testo)
        ms = list(patt.finditer(testo, inizio))
        inizi = {f[0].start() for f in fondi(testo, ms)}
        di: dict[int, int] = {}
        g, starts = -1, []
        for m in ms:
            if m.start() in inizi:
                g += 1
                starts.append(m.start())
            di[m.start()] = g
        return testo, ms, di, starts

    def confronta(self, caso: str) -> EsitoUnione:
        """The decisions for one case (reads only)."""
        radice = self.config.radice
        pre = PREFISSI[caso]
        conf = leggi_caso(radice / 'cited-cases' / f'{caso}.yaml')
        patt = modello_forme(conf['forme'])
        tutte = list(self.banca.righe('corpus_rows', [('caso_citato', '==', caso)]))
        nominali = [(i, r) for i, r in tutte if r.get('proposto_rete') in NOMINALI]
        with open(radice / 'index' / f'nomi_{caso}_{self.data}b.csv', encoding='utf-8') as f:
            nuove_csv = list(csv.DictReader(f))
        esito = EsitoUnione(caso=caso, nominali=len(nominali), nella_ricerca=len(nuove_csv))
        per_doc: dict[str, list[Riga]] = collections.defaultdict(list)
        for i, r in nominali:
            per_doc[r['document_id']].append((i, r))
        csv_doc: dict[str, dict[int, dict[str, Any]]] = collections.defaultdict(dict)
        for r in nuove_csv:
            csv_doc[r['document_id']][int(r['char_start'])] = r
        file_di = {r['document_id']: r['file'] for r in nuove_csv}
        for _, r in nominali:
            file_di.setdefault(r['document_id'], r.get('file'))
        da_aggiungere: list[dict[str, Any]] = []
        for doc in sorted(set(per_doc) | set(csv_doc)):
            md = radice / file_di[doc]
            if not md.exists():
                esito.orfane += per_doc.get(doc, [])
                continue
            testo, ms, gruppo_di, starts = self.gruppi_del_documento(md, patt)
            coperti: set[int] = set()
            rapp: dict[int, list[Riga]] = collections.defaultdict(list)
            code: dict[int, list[Riga]] = collections.defaultdict(list)
            for i, r in per_doc.get(doc, []):
                cs = int(r.get('char_start') or -1)
                if cs >= 0:
                    cs, _ = self.ocr.traduci(file_di[doc], cs, patt, bool((r.get('provenienza') or {}).get('ocr')))
                cov = [m for m in ms if cs <= m.start() < cs + FUSIONE]
                if not cov:
                    esito.orfane.append((i, r))
                    continue
                coperti |= {gruppo_di[m.start()] for m in cov}
                nomi = [m for m in cov if e_nome(testo, m)]
                (rapp if nomi else code)[gruppo_di[(nomi or cov)[0].start()]].append((i, r))
            for g in sorted(set(rapp) | set(code)):
                if len(rapp[g]) > 1:
                    esito.piu_nomi += 1
                tutte_g = sorted(rapp[g] + code[g], key=lambda x: int(x[1]['char_start']))
                if not code[g] or len(tutte_g) < 2:
                    continue
                base = rapp[g] or code[g]
                giudicate = [x for x in base if x[1].get('esito')] or [x for x in code[g] if x[1].get('esito')]
                tieni = giudicate[0] if giudicate else sorted(base, key=lambda x: int(x[1]['char_start']))[0]
                via = [x for x in code[g] if x[0] != tieni[0]]
                if tieni in code[g] and len(rapp[g]) == 1:
                    via += rapp[g]
                esito.spezzate.append((tieni, via, sum(1 for x in tutte_g if x[1].get('esito'))))
            for g, g0 in enumerate(starts):
                if g not in coperti:
                    riga = csv_doc[doc].get(g0)
                    if riga is not None:
                        da_aggiungere.append(riga)
        gia = [
            int(m.group(1)) for _, r in tutte for m in [re.fullmatch(rf'{pre}-(\d+)', str(r.get('codice') or ''))] if m
        ]
        n = max(gia, default=0)
        chi = sorted({r['assegnato_a'] for _, r in nominali if r.get('assegnato_a') and not r.get('esito')})
        esito.validatori = len(chi)
        rnd = random.Random(f'{caso}-{self.data}')
        esistenti = {i for i, _ in tutte}
        for k, r in enumerate(sorted(da_aggiungere, key=lambda x: (x['document_id'], int(x['char_start'])))):
            d = documento_riga(r, caso)
            rid = id_riga(caso, d['document_id'], d['char_start'])
            if rid in esistenti:
                esito.orfane.append((None, {'document_id': d['document_id'], 'char_start': d['char_start'], 'id': rid}))
                continue
            n += 1
            d.update(
                {
                    'corroborazione': 'nome_presente',
                    'ordine': random.Random(rid).random(),
                    'codice': f'{pre}-{n:04d}',
                    'assegnato_a': chi[k % len(chi)] if chi else None,
                    'campione_cieco': rnd.random() < 0.20,
                    'incerta': False,
                    'provenienza': {
                        'corpus': 'D01',
                        'estrazione': 'S02' if self.data == DATA_PRIMA_RICERCA else 'S03',
                        'tipo': '',
                        'principi': {},
                        'composizione': '',
                        'seguito': '',
                    },
                    'motivo_aggiunta': r.get('motivo_mancava', ''),
                }
            )
            esito.nuove[rid] = d
        esito.ultimo_codice = n
        return esito

    def mostra(self, e: EsitoUnione) -> None:
        pre, n, s = PREFISSI[e.caso], e.ultimo_codice, self.stampa
        s(f'\n== {e.caso}: in piattaforma {e.nominali} righe col nome; ricerca nuova {e.nella_ricerca} citazioni')
        s(
            f'   da aggiungere {len(e.nuove)} (codici {pre}-{n - len(e.nuove) + 1:04d}..{pre}-{n:04d}), validatori '
            f'{e.validatori}, alla cieca {sum(d["campione_cieco"] for d in e.nuove.values())}'
        )
        s(
            f'   citazioni spezzate {len(e.spezzate)}: righe da unire {sum(len(x[1]) for x in e.spezzate)}, '
            f"con una riga giudicata {sum(1 for x in e.spezzate if x[2])}, con PIU' righe giudicate "
            f'{sum(1 for x in e.spezzate if x[2] > 1)}'
        )
        s(
            f'   righe della piattaforma senza gruppo nella ricerca nuova (non si toccano): {len(e.orfane)}; '
            f"gruppi con piu' righe che nominano il caso (restano tutte): {e.piu_nomi}"
        )
        for _, r in e.orfane[:5]:
            s(f'      {r.get("codice")} {r["document_id"][:60]} {r.get("char_start")}')

    @staticmethod
    def rapporto(e: EsitoUnione) -> dict[str, Any]:
        return {
            'aggiunte': [
                (d['codice'], d['document_id'], d['proposto_pagina'], d['proposto_forma_trovata'])
                for d in e.nuove.values()
            ],
            'unite': [(t[1].get('codice'), [x[1].get('codice') for x in via]) for t, via, _ in e.spezzate],
            'orfane': [r.get('codice') for _, r in e.orfane],
        }

    def scritture(self, e: EsitoUnione, conf_testo: str, forme: int) -> tuple[list[Scrittura], Scrittura]:
        """The batched writes (new rows created, split rows marked) and the run document."""
        ora = self.banca.ora_del_server
        w = [
            Scrittura(
                'create',
                'corpus_rows',
                rid,
                {**d, 'esecuzione_id': f'{e.caso}__{self.esecuzione}', 'creato_il': ora},
            )
            for rid, d in e.nuove.items()
        ]
        for (_, t), via, _ in e.spezzate:
            for i, r in via:
                w.append(
                    Scrittura(
                        'update',
                        'corpus_rows',
                        i,
                        {
                            'proposto_rete': 'fusa',
                            'fusa_rete_prima': r.get('proposto_rete'),
                            'fusa_in': t.get('codice'),
                            'fusa_il': self.data,
                            'fusa_motivo': 'stessa citazione spezzata in due righe dalla vecchia regola di fusione',
                        },
                    )
                )
        origine = (
            'ricerca per nome rifatta (cerca.py corretto: niente tagli semantici sulle '
            'righe col nome, fusione dalla corrispondenza precedente, forme coreana e giapponese)'
            if self.data == DATA_PRIMA_RICERCA
            else f'ricerca per nome rifatta il {self.data}: testo OCR dei documenti con pagine illeggibili, '
            'altre forme giapponesi e coreane, a capo ammesso dentro i nomi in quelle scritture'
        )
        corsa = Scrittura(
            'set',
            'corpus_runs',
            f'{e.caso}__{self.esecuzione}',
            {
                'caso_citato': e.caso,
                'origine': origine,
                'righe_aggiunte': len(e.nuove),
                'righe_unite': sum(len(x[1]) for x in e.spezzate),
                'quando': ora,
                'forme': forme,
                'search_strategy': conf_testo,
            },
        )
        return w, corsa

    def esegui(self) -> dict[str, Any]:
        """Every case: decisions, screen lines, writes with ``scrivi``; the report file is always written."""
        rapporto = {}
        for caso in self.casi:
            e = self.confronta(caso)
            self.mostra(e)
            rapporto[caso] = self.rapporto(e)
            if not self.scrivi:
                continue
            f = self.config.cited_cases / f'{caso}.yaml'
            w, corsa = self.scritture(e, f.read_text(encoding='utf-8'), len(leggi_caso(f)['forme']))
            self.banca.scrivi_a_lotti(w)
            self.banca.imposta(corsa.collezione, corsa.doc_id, dict(corsa.dati or {}))
            self.stampa(f'   scritte: {len(e.nuove)} nuove, {sum(len(x[1]) for x in e.spezzate)} unite')
        with open(self.config.training / f'nomi_unisci_aggiungi_{self.data}.json', 'w') as f:
            json.dump(rapporto, f, ensure_ascii=False, indent=1)
        return rapporto
