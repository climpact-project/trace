"""The composition of the proposals on the lexical rows (``composizione``), rule R05 (``tools/carica_ripresa.py``).

For every lexical row without a human verdict the composition writes the fields the review form reads (§63.25,
codebook 0.3-pilot, dimensions 6 and 7):

- ``proposto_principi``: the principles ticked at the start: those of the cited paragraphs (paragraph map) plus those
  of the first DeepSeek reading; ``["nessuno"]`` if the reading says none and no paragraph carries one;
- ``proposto_principi_fonti``: for every principle where it comes from: ``paragrafo``, ``lettura``, ``reranker``
  (passage score >= 0.5: close in words, shown as a hint even when not ticked);
- ``proposto_principio_altro``: the sentence of the reading when it says "altro" (other);
- ``proposto_estensione``: the surrounding pages, with follows/does not follow, principle and sentence of the reading;
- ``proposto_paragrafi``, ``proposto_principi_motivo``, ``proposto_ripresa_lettore``, the supported sentence
  (``proposto_frase_*``) and the provenance codes (``provenienza.*``) of the version register.

They are proposals: training labels come from people or from the paragraph map, never from DeepSeek.

The live ``proposta()`` is one function of cyclomatic complexity 113; :class:`Composizione` splits it into small
methods with identical output. :class:`IngressiComposizione` gathers its inputs from the files (reads only), and
:meth:`Composizione.componi` reproduces the row selection of ``main`` without writing to Firestore.
"""

from __future__ import annotations

import collections
import difflib
import hashlib
import json
import re
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .caso import SerieSonde
from .config import Config
from .freni import FRENI, Freni
from .letture import vero
from .pagine_attorno import per_id

LETTORE = 'mappa dei paragrafi + DeepSeek V4 Flash 0731 + TRACE-Reranker, 27/09/2026'
NESSUNO = 'nessuno'
ALTRO = 'altro'
IN_CATENA = 'menzione_in_catena'

Righe = Mapping[str, Mapping[str, Any]]
"""Lines of a JSONL file by row id."""

_NON_PAROLA = re.compile(r'\W+')


def _norm(t: object) -> str:
    """The composition's own normalisation (``str(t)``, so ``None`` becomes ``'none'``, unlike ``Freni.norm``)."""
    return _NON_PAROLA.sub(' ', str(t).lower()).strip()


def _spazi(t: object) -> str:
    return ' '.join(str(t or '').split())


def _prima_dict(letture: list[Any]) -> dict[str, Any] | None:
    """The first reading if it is a dict."""
    return letture[0] if letture and isinstance(letture[0], dict) else None


def documento_di(rid: str) -> str:
    """The document of a row id (``<case>__<document>__<offset>``); ``''`` when the id has no ``__`` (03/10/2026:
    ``rid.split('__')[1]`` raised IndexError and stopped the whole case)."""
    parti = str(rid).split('__')
    return parti[1] if len(parti) > 1 else ''


def id_malformato(rid: str, conti: collections.Counter[str]) -> bool:
    """True (the row is skipped) when the id is not ``<case>__<document>__...``: said on stderr and counted, as
    ``tools/carica_ripresa.id_malformato``. Braces are replaced: the chain reads the counts from the first ``{``."""
    if len(str(rid).split('__')) > 1:
        return False
    testo = ('malformed row id, row skipped: ' + repr(rid)).replace('{', '(').replace('}', ')')
    print(testo, file=sys.stderr)
    conti['id malformato (saltata)'] += 1
    return True


def _senza_principi(x: Mapping[str, Any]) -> bool:
    """A reading with an empty principle list is not an answer (review of 30/09/2026: 247 rows with ``[]``)."""
    return not [q for q in (x.get('principi') or []) if isinstance(q, str) and q]


def pagine_intere(config: Config, cand: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The proof is looked for in the WHOLE page (04/10/2026, truncation audit): twin of ``pagine_intere`` in
    ``tools/carica_ripresa.py``. The L05 reader rows carry their surrounding pages cut at 3,500 characters, so a proof
    copied from the tail (the footnotes) came out «not found». Each surrounding page gets its page-index text (up to
    12,000 characters) in ``vicine_testo``, only when it starts like the row's text (same source: OCR pages stay)."""
    if not config.indice_pagine.exists():
        return cand
    from .corpus import IndicePagine

    serve = {f"{c['document_id']}#p{v['pagina']}" for c in cand.values() for v in c.get('vicine', [])}
    testi = {k: t[:12000] for k, t in IndicePagine(config.indice_pagine).testi(serve).items()}
    for c in cand.values():
        vt = c.get('vicine_testo') or {}
        for v in c.get('vicine', []):
            n = v['pagina']
            t = testi.get(f"{c['document_id']}#p{n}", '')
            prima = v.get('testo') or ''
            if n in vt or str(n) in vt or not t or len(t) <= len(prima) or not t.startswith(prima[:200]):
                continue
            vt[n] = t
        if vt:
            c['vicine_testo'] = vt
    return cand


_intere = pagine_intere


# 04/10/2026, from the truncation audit: the supported sentence was kept to 600 characters and 55% of the cut
# sentences lost material (footnotes, paragraph numbers, the case name). Now 2,000 (compat=True keeps 600).
FRASE_MAX = 2000


@dataclass
class _Scelta:
    """The reading the principles come from, and whether it is an L04 reading."""

    lettura: dict[str, Any]
    da_l04: bool


@dataclass
class Composizione:
    """Composition of the proposals of one cited case (R05).

    Args:
        ids: the principle ids of the probe series, in file order.
        principi_testo: ``id -> (title, text)``: the texts that were in the prompt (invented evidence is copied
            from them).
        codice_sonde: register code of the probe series (``provenienza.sonde``).
        codice_mappa: register code of the paragraph map (``R04``, ``R07``, ``R09``...).
        documenti_ocr: ids of the documents redone with OCR (corpus D02).
        soglia_reranker: passage score at which the reranker is listed as a source.
        freni: the brakes (evidence check).
        compat: reproduce the three live defects fixed on 02/10/2026 (provenance L04 after a fallback to an L05
            reading, ``principi`` given as a string, rule ``R03`` on each surrounding page). ``False`` (the default)
            is the fixed behaviour; the harness runs with ``True``.
    """

    ids: list[str]
    principi_testo: Mapping[str, tuple[str, str]]
    codice_sonde: str = ''
    codice_mappa: str = 'R04'
    documenti_ocr: frozenset[str] = frozenset()
    soglia_reranker: float = 0.5
    freni: Freni = field(default=FRENI)
    compat: bool = False

    # construction
    @classmethod
    def per_caso(cls, config: Config, caso: str, compat: bool = False) -> Composizione:
        """The composition of ``caso`` with the probe series in use, its codes and the OCR documents."""
        sonde = SerieSonde.carica(config, caso)
        return cls(
            ids=sonde.ids,
            principi_testo=sonde.testi(),
            codice_sonde=config.codice(caso),
            codice_mappa=config.codice_mappa(caso),
            documenti_ocr=documenti_ocr(config),
            soglia_reranker=config.soglia_reranker,
            compat=compat,
        )

    @property
    def testi_prompt(self) -> list[str]:
        """Every principle title and text, in id order."""
        return [t for k in self.ids for t in (self.principi_testo.get(k) or ())]

    # principles
    @staticmethod
    def prima_lettura(ds: Righe, rid: str) -> tuple[dict[str, Any], list[Any]]:
        """``(first L05 reading or {}, all L05 readings)`` of a row."""
        letture = (ds.get(rid) or {}).get('letture') or [{}]
        return (letture[0] if isinstance(letture[0], dict) else {}), letture

    def lettura_principi(
        self, rid: str, ds_principi: Righe | None, l1: dict[str, Any], letture_l05: list[Any]
    ) -> _Scelta:
        """The reading the principles are taken from.

        Principles from L04, the rest from L05 (30/09/2026, with the PI's yes): L05 decides the principle on the note
        sentence only and does worse than L04 against the PI's verdicts (§63.35). Where L04 is missing the principles
        stay those of L05. A reading with an empty list passes to the second reading of the same version, then to the
        L05 readings.
        """
        letture_l04 = ((ds_principi or {}).get(rid) or {}).get('letture') or []
        lp = _prima_dict(letture_l04)
        scelta = _Scelta(lp, True) if lp is not None else _Scelta(l1, False)
        if _senza_principi(scelta.lettura):
            altre = [(x, True) for x in letture_l04[1:]] + [(x, False) for x in letture_l05 if isinstance(x, dict)]
            for alt, l04 in altre:
                if isinstance(alt, dict) and not _senza_principi(alt):
                    scelta.lettura = alt
                    # NOTE(bug): live, when the fallback lands on an L05 reading `da_l04` stays True and the
                    # provenance of these principles is still written as L04. Fixed on 02/10/2026; compat=True keeps it.
                    if not self.compat:
                        scelta.da_l04 = scelta.da_l04 and l04
                    break
        return scelta

    def canonico(self, q: str) -> str:
        """A principle id as written by the model, brought back to a valid id.

        Without the case prefix ("vorwirkung_..." for "neubauer.vorwirkung_...", 82 Neubauer readings) or with a typo
        ("neubaurer.liberta_intertemporale", 4 readings out of 3,488): the closest valid id if very similar (0.85).
        """
        if q in self.ids:
            return q
        trovato = next((i for i in self.ids if i.endswith('.' + q)), None)
        if trovato:
            return trovato
        corto = {i.split('.')[-1]: i for i in self.ids}
        m = difflib.get_close_matches(q.split('.')[-1], list(corto), n=1, cutoff=0.85)
        return corto[m[0]] if m else q

    def principi_letti(self, lp: Mapping[str, Any]) -> list[str]:
        """The principles of a reading, canonical (non-ids kept as written).

        A string instead of a list (``"neubauer.budget_residuo, altro"``) is split on commas and semicolons.
        """
        principi = lp.get('principi') or []
        if isinstance(principi, str) and not self.compat:
            principi = [q.strip() for q in re.split(r'[,;]', principi) if q.strip()]
        # NOTE(bug): live, a string is iterated character by character (no principle survives). Fixed on 02/10/2026;
        # compat=True keeps it.
        return [self.canonico(p) for p in principi if isinstance(p, str)]

    def fonti(
        self, rid: str, par: Righe, brano: Mapping[str, Mapping[str, float]], lett: list[str]
    ) -> collections.defaultdict[str, list[str]]:
        """Where every principle comes from: paragraph map, reading, reranker (in this order)."""
        fonti: collections.defaultdict[str, list[str]] = collections.defaultdict(list)
        for p in par.get(rid, {}).get('principi', []):
            fonti[p].append('paragrafo')
        for p in lett:
            if p in self.ids:
                fonti[p].append('lettura')
        for p, s in brano.get(rid, {}).items():
            if s >= self.soglia_reranker:
                fonti[p].append('reranker')
        return fonti

    def spuntati(
        self, fonti: collections.defaultdict[str, list[str]], lett: list[str], altro: str, in_catena: bool
    ) -> list[str]:
        """The ticked principles.

        A principle is ticked if a paragraph or the reading proposes it; ``altro`` when the reading says so with a
        sentence. Readings that give only codes that are not probes ("cooperazione_obbligo", ICJ-0629) mean "nessuno",
        not a row without a proposal. A chain mention takes no principle (codebook, dimension 6): the hints stay in
        the sources, visible but not ticked (287 rows on 28/09/2026).
        """
        spuntati = [p for p in self.ids if 'paragrafo' in fonti[p] or 'lettura' in fonti[p]]
        if ALTRO in lett and altro:
            spuntati.append(ALTRO)
        if not spuntati and (NESSUNO in lett or not [q for q in lett if q in self.ids]):
            spuntati = [NESSUNO]
        if in_catena:
            spuntati = [NESSUNO]
        return spuntati

    # surrounding pages
    @staticmethod
    def lettura_seguito(rid: str, ds_seguito: Righe | None, l1: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """``(reading of the follow-up, True if it is the L07 re-reading)``.

        Where the principles changed, the follow-up re-read on today's principles (L07, 30/09/2026) replaces L05.
        """
        ls_ = ((ds_seguito or {}).get(rid) or {}).get('letture') or []
        if ls_ and isinstance(ls_[0], dict) and 'vicine' in ls_[0]:
            return ls_[0], True
        return l1, False

    @staticmethod
    def pagina_citazione(c: Mapping[str, Any]) -> int:
        """The citation page of the candidate row, 0 if missing or not a number."""
        try:
            return int(c.get('pagina') or 0)
        except (TypeError, ValueError):
            return 0

    def principio_pagina(self, v: Mapping[str, Any]) -> str:
        """The principle a page follows, with the case prefix restored if the model dropped it."""
        pr_v = v.get('principio') or ''
        return pr_v if (not pr_v or pr_v in self.ids) else next((i for i in self.ids if i.endswith('.' + pr_v)), pr_v)

    @staticmethod
    def testo_pagina(c: Mapping[str, Any], n: int) -> str:
        """The text of surrounding page ``n`` as it was given to the model."""
        return c.get('vicine_testo', {}).get(n) or next(
            (w.get('testo', '') for w in c.get('vicine', []) if w['pagina'] == n), ''
        )

    def scelta_pagina(self, punteggi: Mapping[str, float], dist: int | None) -> dict[str, Any]:
        """Why the reranker chose a page: best T01 score, its principle, distance and the threshold that applied."""
        migliore = max(punteggi.items(), key=lambda kv: kv[1]) if punteggi else (None, None)
        return {
            'punteggio': round(float(migliore[1]), 3) if migliore[1] is not None else None,
            'principio': migliore[0] or '',
            'distanza': dist,
            'soglia': (0.5 if dist is not None and -2 <= dist <= 3 else 0.8),
            'versione': 'T01',
            # NOTE(bug): live, the window is chosen by R08 (provenienza.scelta_vicine) but each page says R03. Fixed on
            # 02/10/2026; compat=True keeps R03.
            'regola': 'R03' if self.compat else 'R08',
        }

    def estensione(self, c: Mapping[str, Any], lv: Mapping[str, Any]) -> list[dict[str, Any]]:
        """The surrounding pages the reading judged, restricted to the pages that were proposed.

        A page follows only if its evidence is really in the page (the brake of 30/09/2026); evidence copied from the
        prompt is invented and the page is never ticked.
        """
        vicine = c.get('vicine', [])
        pagine_cand = {v['pagina'] for v in vicine}
        punti_vicine = {v['pagina']: v.get('punteggi') or {} for v in vicine}
        pag_cit = self.pagina_citazione(c)
        testi_prompt = self.testi_prompt
        vic = []
        for v in lv.get('vicine') or []:
            try:
                n = int(v.get('pagina'))
            except (TypeError, ValueError):
                continue
            if n not in pagine_cand:
                continue
            prova = _spazi(v.get('prova'))[:300]
            dist = n - pag_cit if pag_cit else None
            esito_prova = self.freni.verifica(prova, self.testo_pagina(c, n), testi_prompt)
            vic.append(
                {
                    'pagina': n,
                    # strict yes/no (03/10/2026): the string "false" is a no
                    'prosegue': vero(v.get('prosegue')) and esito_prova == 'trovata',
                    'principio': self.principio_pagina(v),
                    'prova': prova,
                    'testuale': esito_prova == 'trovata',
                    'prova_esito': esito_prova,
                    'scelta': self.scelta_pagina(punti_vicine.get(n) or {}, dist),
                }
            )
        return vic

    @staticmethod
    def filtra_seguito(vic: list[dict[str, Any]], spuntati: list[str]) -> list[dict[str, Any]]:
        """No follow-up without a principle, and none on a principle the row does not propose.

        If the citation takes no principle nothing follows (PI, 28/09/2026: pages stay listed, none ticked). Since
        30/09 principles (L04) and follow-up (L05/L07) come from different readings: a page ticked on another principle
        stays listed, not ticked (R02).
        """
        if spuntati == [NESSUNO]:
            return [dict(v, prosegue=False) for v in vic]
        return [
            dict(v, prosegue=False) if (v['prosegue'] and v['principio'] and v['principio'] not in spuntati) else v
            for v in vic
        ]

    # provenance and supported sentence
    def provenienza(
        self,
        rid: str,
        ds: Righe,
        ds_principi: Righe | None,
        scelta: _Scelta,
        fonti: Mapping[str, list[str]],
        spuntati: list[str],
        vic: list[dict[str, Any]],
        seguito_l07: bool,
        brano: Mapping[str, Mapping[str, float]],
        contesto: str,
    ) -> dict[str, Any]:
        """The provenance codes of the version register (tools/registro_versioni.py)."""
        lettura = 'L05' if (ds.get(rid) or {}).get('seconda') else 'L04'
        codici = {
            'paragrafo': self.codice_mappa,
            'lettura': 'L04' if (scelta.da_l04 and ds_principi is not None) else lettura,
            'reranker': 'T01',
        }
        prin_prov = {k: sorted({codici[f] for f in v}) for k, v in fonti.items() if v}
        # "altro" (a principle outside the list) comes only from the reading
        if ALTRO in (spuntati or []) and ALTRO not in prin_prov:
            prin_prov[ALTRO] = [codici['lettura']]
        ocr = {'provenienza.corpus': 'D02'} if documento_di(rid) in self.documenti_ocr else {}
        return {
            'provenienza.principi': prin_prov,
            'provenienza.seguito': ('L07' if seguito_l07 else lettura) if vic else '',
            'provenienza.composizione': 'R05',
            'provenienza.sonde': self.codice_sonde,
            'provenienza.scelta_vicine': 'R08' if vic else '',
            'proposto_punteggi_principi': {k: round(float(x), 4) for k, x in brano.get(rid, {}).items()},
            **ocr,
            'proposto_testo_impronta': hashlib.sha256(contesto.encode('utf-8')).hexdigest(),
        }

    def frase(self, l1: Mapping[str, Any], contesto: str) -> dict[str, Any]:
        """The sentence of the filing the citation supports (V05, 28/09/2026), checked against the page.

        If today's reading has no sentence, the one of an earlier reading is cleared (02/10/2026, NEU-0308).
        """
        frase = _spazi(l1.get('frase_sostenuta'))[: 600 if self.compat else FRASE_MAX]
        if not frase:
            return {'proposto_frase_sostenuta': '', 'proposto_frase_testuale': False, 'proposto_frase_esito': ''}
        return {
            'proposto_frase_sostenuta': frase,
            'proposto_frase_testuale': _norm(frase)[:60] in _norm(contesto),
            'proposto_frase_esito': self.freni.verifica(frase, contesto, self.testi_prompt),
        }

    # the proposal
    def proposta(
        self,
        rid: str,
        par: Righe,
        brano: Mapping[str, Mapping[str, float]],
        ds: Righe,
        cand: Righe,
        tipo: str = '',
        ds_principi: Righe | None = None,
        ds_seguito: Righe | None = None,
    ) -> dict[str, Any]:
        """The proposed fields of one row (tools/carica_ripresa.py ``proposta``), touching nothing.

        Args:
            rid: the row id.
            par: paragraph-map lines by row id.
            brano: passage scores by row id.
            ds: L05 readings by row id (``seconda`` marks the second reading).
            cand: the candidate rows with their surrounding pages (``_ripresa_righe``) by row id.
            tipo: the proposed citation type of the row (``proposto_tipo_citazione``).
            ds_principi: L04 readings by row id, when the principles come from L04.
            ds_seguito: L07 follow-up readings by row id.
        """
        l1, letture_l05 = self.prima_lettura(ds, rid)
        scelta = self.lettura_principi(rid, ds_principi, l1, letture_l05)
        lp = scelta.lettura
        lett = self.principi_letti(lp)
        fonti = self.fonti(rid, par, brano, lett)
        altro = _spazi(lp.get('altro'))
        in_catena = tipo == IN_CATENA
        spuntati = self.spuntati(fonti, lett, altro, in_catena)
        c = cand.get(rid) or {}
        contesto = c.get('contesto') or ''
        lv, seguito_l07 = self.lettura_seguito(rid, ds_seguito, l1)
        vic = self.filtra_seguito(self.estensione(c, lv), spuntati)
        prov = self.provenienza(rid, ds, ds_principi, scelta, fonti, spuntati, vic, seguito_l07, brano, contesto)
        prov.update(self.frase(l1, contesto))
        return {
            **prov,
            'proposto_principi': spuntati,
            'proposto_principi_fonti': {k: v for k, v in fonti.items() if v},
            'proposto_principio_altro': altro if ALTRO in spuntati else '',
            'proposto_estensione': vic,
            'proposto_paragrafi': par.get(rid, {}).get('paragrafi', []),
            'proposto_principi_motivo': ('Menzione in catena: nessun principio proposto. ' if in_catena else '')
            + _spazi(lp.get('motivo'))[:400],
            'proposto_ripresa_lettore': LETTORE,
        }

    # the rows to write (main)
    def componi(
        self,
        righe_fs: Iterable[tuple[str, Mapping[str, Any]]],
        ingressi: IngressiComposizione,
        anche_senza_lettura: bool = False,
    ) -> tuple[list[tuple[str, dict[str, Any]]], collections.Counter[str]]:
        """The fields to write on every eligible row, and the counts printed by the live script.

        Args:
            righe_fs: ``(document id, fields)`` of the Firestore rows of the case, in stream order.
            ingressi: the inputs read from the files.
            anche_senza_lettura: also rows DeepSeek has not read yet (provisional proposal from paragraphs and
                reranker, 01/10/2026).

        Returns:
            ``([(row id, fields)], counts)``. Rows that are not lexical, already judged, or (by default) unread are
            skipped; no human verdict is ever touched.
        """
        g = ingressi
        conti: collections.Counter[str] = collections.Counter()
        scritture: list[tuple[str, dict[str, Any]]] = []
        for rid, r in righe_fs:
            if r.get('proposto_rete') not in ('lessicale', 'entrambe', 'descrittiva'):
                continue
            if r.get('esito'):
                conti['gia giudicata (non toccata)'] += 1
                continue
            if id_malformato(rid, conti):
                continue
            if rid not in g.ds and not anche_senza_lettura:
                conti['senza lettura'] += 1
                continue
            if rid not in g.ds:
                conti['provvisoria: paragrafi e reranker, lettura in arrivo'] += 1
            campi = self.proposta(
                rid, g.par, g.brano, g.ds, g.cand, r.get('proposto_tipo_citazione') or '', g.ds_principi, g.ds_seguito
            )
            campi['proposta_provvisoria'] = rid not in g.ds
            # without a reading "nessuno" is not a proposal: the machine has not read yet
            if campi['proposta_provvisoria'] and campi.get('proposto_principi') == [NESSUNO]:
                campi['proposto_principi'] = []
            if g.ds_seguito is not None and rid in g.ds_seguito:
                conti['seguito riletto (L07)'] += 1
            if g.ds_principi is not None:
                conti['principi da L04' if rid in g.ds_principi else 'principi da L05 (manca L04)'] += 1
            spuntati, vic = campi['proposto_principi'], campi['proposto_estensione']
            scritture.append((rid, campi))
            conti['da scrivere'] += 1
            conti[
                'con principio spuntato'
                if spuntati and spuntati != [NESSUNO]
                else (NESSUNO if spuntati else 'senza proposta')
            ] += 1
            conti['con seguito proposto' if any(v['prosegue'] for v in vic) else 'senza seguito'] += 1
        return scritture, conti


# inputs


def documenti_ocr(config: Config) -> frozenset[str]:
    """Documents redone with OCR (``training/ocr/pagine_sostituite.json`` keys, before ``#``)."""
    f = config.pagine_sostituite
    if not f.exists():
        return frozenset()
    # read through pathlib: live this file is read at import time, before the journal starts, so it is not listed
    return frozenset(k.split('#')[0] for k in json.loads(f.read_text(encoding='utf-8')))


def _per_id_se(percorso: Path, **extra: Any) -> dict[str, dict[str, Any]]:
    return {i: dict(x, **extra) for i, x in per_id(percorso).items()} if percorso.exists() else {}


@dataclass
class IngressiComposizione:
    """The inputs of the composition of one case, read from the files (``ingressi``: inputs).

    Attributes:
        par: paragraph-map lines by row id.
        brano: passage scores by row id.
        ds: L05 readings by row id.
        cand: candidate rows (with surrounding pages) by row id.
        ds_principi: L04 readings by row id, or ``None`` when the principles come from L05.
        ds_seguito: L07 follow-up readings by row id, or ``None``.
    """

    par: dict[str, dict[str, Any]]
    brano: dict[str, dict[str, float]]
    ds: dict[str, dict[str, Any]]
    cand: dict[str, dict[str, Any]]
    ds_principi: dict[str, dict[str, Any]] | None = None
    ds_seguito: dict[str, dict[str, Any]] | None = None

    @classmethod
    def carica(
        cls, config: Config, caso: str, principi_da_l04: bool = False, pagine_intere: bool = False
    ) -> IngressiComposizione:
        """Read the inputs as ``tools/carica_ripresa.py`` (``carica``, ``load_l04`` and the L07 part of ``main``).

        ``pagine_intere`` (04/10/2026): the proofs are checked on the whole page (:func:`pagine_intere`).
        """
        cartella = config.principi
        suf = config.suf(caso)
        par = per_id(cartella / f'{caso}_da_paragrafi{suf}.jsonl')
        brano: dict[str, dict[str, float]] = collections.defaultdict(dict)
        # NOTE: unlike the window selection, OCR score files are not moved last here (plain sorted order).
        for f in sorted(cartella.glob(f'{caso}{suf}_punteggi_*.jsonl')):
            with open(f, encoding='utf-8') as h:
                for riga in h:
                    x = json.loads(riga)
                    if x['dove'] == 'brano':
                        brano[x['riga']][x['principio']] = x['punteggio']
        cand = per_id(cartella / f'{caso}_ripresa_righe{suf}.jsonl')
        if pagine_intere:
            cand = _intere(config, cand)
        ds = cls.letture_l05(config, caso)
        ds_principi = cls.letture_l04(config, caso) if principi_da_l04 else None
        ds_seguito = cls.letture_l07(config, caso) if principi_da_l04 else None
        return cls(par=par, brano=brano, ds=ds, cand=cand, ds_principi=ds_principi, ds_seguito=ds_seguito)

    @staticmethod
    def letture_l05(config: Config, caso: str) -> dict[str, dict[str, Any]]:
        """The L05 readings: the series file for a series on trial; otherwise the first reading overridden by the
        second ones (``v2`` note rule, ``v10`` corrected search, ``ocr`` and ``ocr2`` OCR texts), marked ``seconda``."""
        cartella = config.principi
        if not config.storica(caso):
            return _per_id_se(cartella / f'{caso}_ripresa_deepseek_{config.serie(caso)}.jsonl', seconda=True)
        ds = per_id(cartella / f'{caso}_ripresa_deepseek.jsonl')
        for nome in ('v2', 'v10', 'ocr', 'ocr2'):
            ds.update(_per_id_se(cartella / f'{caso}_ripresa_deepseek_{nome}.jsonl', seconda=True))
        return ds

    @staticmethod
    def letture_l04(config: Config, caso: str) -> dict[str, dict[str, Any]]:
        """The L04 readings (tools/carica_ripresa.py ``load_l04``)."""
        cartella = config.principi
        if not config.storica(caso):
            return _per_id_se(cartella / f'{caso}_ripresa_deepseek_l04{config.serie(caso)}.jsonl')
        out = per_id(cartella / f'{caso}_ripresa_deepseek.jsonl')
        for nome in ('l04nuove', 'l04ocr', 'l04ocr2'):
            out.update(_per_id_se(cartella / f'{caso}_ripresa_deepseek_{nome}.jsonl'))
        return out

    @staticmethod
    def letture_l07(config: Config, caso: str) -> dict[str, dict[str, Any]] | None:
        """The L07 follow-up readings, without the rows re-read on the OCR text (``ocr2``); ``None`` if absent."""
        cartella = config.principi
        f7 = cartella / f'{caso}_seguito_l07.jsonl' if config.storica(caso) else cartella / '_nessuno.jsonl'
        if not f7.exists():
            return None
        ds_seguito = per_id(f7)
        f_ocr2 = cartella / f'{caso}_ripresa_deepseek_ocr2.jsonl'
        if ds_seguito and f_ocr2.exists():
            for i in per_id(f_ocr2):
                ds_seguito.pop(i, None)
        return ds_seguito


# R11: the majority of the five readings (02/10/2026)


@dataclass
class IngressiMaggioranza:
    """The inputs of the R11 composition of one case (``--composizione R11 --etichetta E --etichetta-tipo T``).

    Attributes:
        par: paragraph-map lines by row id.
        brano: passage scores by row id.
        ds: the L05 readings of ``<caso>_ripresa_deepseek_<E>.jsonl`` by row id (five per row).
        cand: the rows with their R10 surrounding pages, ``<caso>_ripresa_righe_<E>.jsonl``, by row id.
        tipi: the type readings of ``lessicali_<caso>_deepseek_<T>.jsonl`` by row id (empty if the file is absent).
    """

    par: dict[str, dict[str, Any]]
    brano: dict[str, dict[str, float]]
    ds: dict[str, dict[str, Any]]
    cand: dict[str, dict[str, Any]]
    tipi: dict[str, dict[str, Any]]

    @classmethod
    def carica(
        cls, config: Config, caso: str, etichetta: str, etichetta_tipo: str = 'cinque', pagine_intere: bool = False
    ) -> IngressiMaggioranza:
        if not etichetta:
            raise ValueError('R11 needs a label (the readings and the rows with the R10 surrounding pages)')
        base = IngressiComposizione.carica(config, caso)
        cartella = config.principi
        f_tipi = config.training / f'lessicali_{caso}_deepseek_{etichetta_tipo}.jsonl'
        return cls(
            par=base.par,
            brano=base.brano,
            ds=per_id(cartella / f'{caso}_ripresa_deepseek_{etichetta}.jsonl'),
            cand=_intere(config, per_id(cartella / f'{caso}_ripresa_righe_{etichetta}.jsonl')) if pagine_intere
            else per_id(cartella / f'{caso}_ripresa_righe_{etichetta}.jsonl'),
            tipi=per_id(f_tipi) if f_tipi.exists() else {},
        )


class ComposizioneMaggioranza(Composizione):
    """The R11 composition: twin of ``tools/carica_ripresa.py`` ``proposta_r11``.

    The voting rules are in :mod:`tracepipe.maggioranza`.
    """

    def proposta_r11(
        self,
        rid: str,
        par: Righe,
        brano: Mapping[str, Mapping[str, float]],
        ds: Righe,
        cand: Righe,
        vt: Mapping[str, Any] | None = None,
        tipo_fs: str = '',
    ) -> dict[str, Any] | None:
        """The proposed fields of one row with R11, or ``None`` when the row has no valid L05 reading."""
        from . import maggioranza

        ids = self.ids
        rec = ds.get(rid) or {}
        vp = maggioranza.voto_principi(rec.get('letture') or [], ids, self.canonico)
        if vp is None:
            return None
        fonti: collections.defaultdict[str, list[str]] = collections.defaultdict(list)
        for p in par.get(rid, {}).get('principi', []):
            fonti[p].append('paragrafo')
        for p in vp['maggioranza']:
            if p in ids:
                fonti[p].append('lettura')
        for p, s in brano.get(rid, {}).items():
            if s >= self.soglia_reranker:
                fonti[p].append('reranker')
        tipo = vt['tipo'] if vt else tipo_fs
        in_catena = tipo == IN_CATENA
        spuntati = [p for p in ids if 'paragrafo' in fonti[p] or 'lettura' in fonti[p]]
        altro = next((_spazi(y.get('altro')) for _, y, s in vp['insiemi'] if ALTRO in s), '')
        if ALTRO in vp['maggioranza'] and altro:
            spuntati.append(ALTRO)
        if not spuntati or in_catena:
            spuntati = [NESSUNO]
        c = cand.get(rid) or {}
        contesto = c.get('contesto') or ''
        testi_prompt = self.testi_prompt
        pagine_cand = {v['pagina']: v for v in c.get('vicine', [])}
        pag_cit = self.pagina_citazione(c)

        def esito(v: Mapping[str, Any], n: int) -> tuple[Mapping[str, Any], str, str]:
            prova = _spazi(v.get('prova'))[:300]
            testo = (c.get('vicine_testo') or {}).get(n) or pagine_cand[n].get('testo', '')
            return v, prova, self.freni.verifica(prova, testo, testi_prompt)

        vic = []
        for n, voci in sorted(maggioranza.voto_pagine(vp).items()):
            if n not in pagine_cand:
                continue
            si = [v for _, v in voci if vero(v.get('prosegue'))]  # strict vote (03/10/2026): "false" is a no
            maggioranza_si = len(si) >= vp['soglia']
            if si:
                nomi = [self.principio_pagina(v) for v in si]
                conta = collections.Counter(nomi)
                principio = max(conta, key=lambda q: (conta[q], -nomi.index(q)))
                prove = [esito(v, n) for v in si]
                rapp = (
                    next((x for x in prove if x[2] == 'trovata' and self.principio_pagina(x[0]) == principio), None)
                    or next((x for x in prove if x[2] == 'trovata'), None)
                    or prove[0]
                )
                # ticked only with a found evidence OF the winning principle (03/10/2026, external review)
                trovata = any(x[2] == 'trovata' and self.principio_pagina(x[0]) == principio for x in prove)
            else:
                rapp = esito(voci[0][1], n)
                principio = self.principio_pagina(voci[0][1])
                trovata = False
            punti = pagine_cand[n].get('punteggi') or {}
            migliore = max(punti.items(), key=lambda kv: kv[1]) if punti else (None, None)
            dist = n - pag_cit if pag_cit else None
            vic.append(
                {
                    'pagina': n,
                    'prosegue': bool(maggioranza_si and trovata),
                    'principio': principio,
                    'prova': rapp[1],
                    'testuale': rapp[2] == 'trovata',
                    'prova_esito': rapp[2],
                    'voti': maggioranza.voti_testo(len(si), vp['n']),
                    'scelta': {
                        'punteggio': round(float(migliore[1]), 3) if migliore[1] is not None else None,
                        'principio': migliore[0] or '',
                        'distanza': dist,
                        'soglia': 0.5,
                        'versione': 'T01',
                        'regola': 'R10',
                    },
                }
            )
        vic = self.filtra_seguito(vic, spuntati)
        ys = maggioranza.lettura_scelta(vp)
        frase = _spazi(maggioranza.frase_scelta(vp).get('frase_sostenuta'))[: 600 if self.compat else FRASE_MAX]
        frase_esito = self.freni.verifica(frase, contesto, testi_prompt) if frase else ''
        senza_prova = [
            p
            for p in spuntati
            if p in ids
            and 'lettura' in fonti[p]
            and 'paragrafo' not in fonti[p]
            and frase_esito != 'trovata'
            and not any(v['prosegue'] and v['principio'] == p for v in vic)
        ]
        codici = {'paragrafo': self.codice_mappa, 'lettura': 'L05', 'reranker': 'T01'}
        prin_prov = {k: sorted({codici[f] for f in v}) for k, v in fonti.items() if v}
        if ALTRO in spuntati and ALTRO not in prin_prov:
            prin_prov[ALTRO] = ['L05']
        # row uncertainty only from the decisions that make the proposal (03/10/2026, external review): an adopted
        # principle with margin <= 1, or, when none is adopted, a near miss; the type confidence is not mixed in
        adottati = [p for p in vp['maggioranza'] if p in vp['voti'] and p != NESSUNO]
        incerta = any(p in vp['incerti'] for p in adottati) if adottati else bool(vp['incerti'])
        data = '/'.join(reversed(str(rec.get('data') or '')[:10].split('-')))
        ocr = {'provenienza.corpus': 'D02'} if documento_di(rid) in self.documenti_ocr else {}
        out: dict[str, Any] = {
            'provenienza.principi': prin_prov,
            'provenienza.seguito': 'L05' if vic else '',
            'provenienza.composizione': 'R11',
            'provenienza.sonde': self.codice_sonde,
            'provenienza.scelta_vicine': 'R10' if vic else '',
            'provenienza.letture': {'principi': vp['n'], 'tipo': vt['n'] if vt else 0},
            'proposto_punteggi_principi': {k: round(float(x), 4) for k, x in brano.get(rid, {}).items()},
            **ocr,
            'proposto_testo_impronta': hashlib.sha256(contesto.encode('utf-8')).hexdigest(),
            'proposto_frase_sostenuta': frase,
            'proposto_frase_testuale': bool(frase) and _norm(frase)[:60] in _norm(contesto),
            'proposto_frase_esito': frase_esito,
            'proposto_principi': spuntati,
            'proposto_principi_fonti': {k: v for k, v in fonti.items() if v},
            'proposto_principio_altro': altro if ALTRO in spuntati else '',
            'proposto_estensione': vic,
            'proposto_paragrafi': par.get(rid, {}).get('paragrafi', []),
            'proposto_principi_motivo': ('Menzione in catena: nessun principio proposto. ' if in_catena else '')
            + _spazi(ys.get('motivo'))[:400],
            'proposto_ripresa_lettore': (
                f'mappa dei paragrafi + DeepSeek V4 Flash 0731, {vp["n"]} letture a maggioranza (R11), {data} '
                '+ TRACE-Reranker, pagine attorno R10'
            ),
            # the two sources apart (03/10/2026, external review): the ticked principles are map + majority; here each
            # on its own, before the chain-mention rule, so the analysis can separate them
            'proposto_principi_da_mappa': [p for p in ids if 'paragrafo' in fonti[p]],
            'proposto_principi_da_lettura': list(vp['maggioranza']),
            'proposto_principi_voti': {p: maggioranza.voti_testo(v, vp['n']) for p, v in vp['voti'].items()},
            'proposto_principi_incerti': vp['incerti'],
            'proposto_prova_mancante': bool(senza_prova),
            'proposto_principi_senza_prova': senza_prova,
            'proposto_incerta': incerta,
            'proposta_provvisoria': False,
        }
        # the type confidence is written by the type loader only (CaricatoreTipo, R11)
        return out

    def componi_r11(
        self, righe_fs: Iterable[tuple[str, Mapping[str, Any]]], ingressi: IngressiMaggioranza
    ) -> tuple[list[tuple[str, dict[str, Any]]], collections.Counter[str]]:
        """The R11 fields of every lexical row without a verdict that has readings; counts as the live ``main_r11``."""
        from . import maggioranza

        g = ingressi
        conti: collections.Counter[str] = collections.Counter()
        scritture: list[tuple[str, dict[str, Any]]] = []
        for rid, r in righe_fs:
            if r.get('proposto_rete') not in ('lessicale', 'entrambe', 'descrittiva'):
                continue
            if r.get('esito'):
                conti['gia giudicata (non toccata)'] += 1
                continue
            if id_malformato(rid, conti):
                continue
            if rid not in g.ds:
                conti['senza lettura (non toccata)'] += 1
                continue
            vt = maggioranza.voto_tipo((g.tipi.get(rid) or {}).get('letture') or [])
            campi = self.proposta_r11(rid, g.par, g.brano, g.ds, g.cand, vt, r.get('proposto_tipo_citazione') or '')
            if campi is None:
                conti['nessuna lettura valida (non toccata)'] += 1
                continue
            if not vt:
                conti['tipo a maggioranza mancante: tipo della riga'] += 1
            scritture.append((rid, campi))
            sp = campi['proposto_principi']
            conti['da scrivere'] += 1
            conti['con principio spuntato' if sp and sp != [NESSUNO] else NESSUNO] += 1
            conti[
                'con seguito proposto' if any(v['prosegue'] for v in campi['proposto_estensione']) else 'senza seguito'
            ] += 1
            conti['incerta'] += campi['proposto_incerta']
            conti['con prova mancante'] += campi['proposto_prova_mancante']
            conti[f'letture L05 valide {campi["provenienza.letture"]["principi"]}'] += 1
        return scritture, conti
