"""S08, the close pairs: references to the same case in the same filing, read together (``coppie_vicine``).

Class-based version of ``tools/coppie_vicine.py`` (4 and 5 October 2026; solution of the PI to the «same page»
deduplication).

THE PROBLEM. Two true citations of the same case on the same page of one filing were lost (Children of Austria p. 29;
BMW p. 10). The loss had three sources in the code: the descriptive network skipped every match on a page where the
case is already named or a row already exists (a second citation without the name, on the page of the first, did not
become a row); the deduplication of the name search dropped identical text on the same filing and page (the double text
layer of the PDF, which stays); the merge rules count one citation under 200 characters (which stay).

THE SOLUTION. The references to the same case, in the same filing, within a distance (in characters) become a CANDIDATE
PAIR. Each one has a provisional code ``<code>a``, ``<code>b`` (``<code>c`` if the chain has more). DeepSeek and the
reranker read each of the two rows as every row, then the PAIR together with question L13 («one citation or two?»,
five readings); ONE: they are merged as in C03; TWO: they count two; uncertain: to the team.

WHAT THIS MODULE DOES (nothing is written to the database):

- :class:`CoppieVicine`: from the live rows of a snapshot, the links between CONSECUTIVE rows of the same case and
  filing at a ``char_start`` distance up to the threshold (:data:`SOGLIA_S08`, 5,000), the chains (connected
  components), the list of the pairs for L13 and the counts at every threshold;
- :class:`Taratura`: the threshold chosen with the numbers (the PI: «every choice motivated, it is for the paper») on
  the 850 pairs of C03 reread by hand: distances, coverage, cost, and the precision of every clue;
- :func:`classifica_recuperate`: the rows recovered by the scan (the descriptive network redone WITHOUT the page filter
  on the whole corpus) are «assorbita» if within 200 characters of a name or a row (the same citation, explained: S07
  was right) and «nuova» otherwise: that is the recovery.

The scan itself (17,000 filings, minutes) needs ``tools/rete_descrittiva.py`` and stays in ``tools/coppie_vicine.py``:
it saves its result in a file and the package starts from it.

A DECLARED LIMIT. The threshold is a cost (every pair is five readings of DeepSeek), not a natural law: it is chosen
with the pairs of C03 reread by hand (at what distance the «one citation» pairs stood). It proves nothing about pairs
farther apart than C03 saw (C03 looks for the same sentence within one page).
"""

from __future__ import annotations

import bisect
import collections
import csv
import re
import statistics
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

from .coppia import ArchivioAtti, Coppia, verdetto_indizi
from .righe import RETI_VIVE, LettoreAtti, Riga, pagina_di_riga, posizione_di_riga
from .unione_c03 import GeneratoreCoppie

SOGLIE: tuple[int, ...] = (200, 500, 1000, 2000, 3000, 5000, 8000, 12000)
"""The thresholds counted in the report."""
SOGLIA_S08 = 5000
"""THE THRESHOLD CHOSEN (5 October 2026): see :class:`Taratura` and the S08 report in ``training/misure/``."""
ASSORBITA = 200
"""Under this distance a recovered match is the same citation of a name or a row (as the merge of 200)."""
LETTERE = 'abcdefghijklmnopqrstuvwxyz'
PAGINA = re.compile(r'<!--\s*page\s+\d+\s*-->')


@dataclass(frozen=True)
class Legame:
    """Two consecutive rows of the same case and filing within the threshold.

    Attributes:
        distanza: characters between the two points.
        atto: ``(document_id, case)``.
        a: ``(key, row)`` of the first in the text (the key is the id of the row, or that of a new row of the scan).
        b: ``(key, row)`` of the second.
    """

    distanza: int
    atto: tuple[str, str]
    a: tuple[str, Riga]
    b: tuple[str, Riga]


@dataclass(frozen=True)
class Catena:
    """The rows connected by consecutive links in one filing and case, in the order of the text (at least two)."""

    atto: tuple[str, str]
    righe: tuple[tuple[str, Riga], ...]

    @property
    def codice_base(self) -> str | None:
        """The lowest code of the chain, ``None`` if no row has one."""
        codici = sorted(str(r.get('codice')) for _, r in self.righe if r.get('codice'))
        return codici[0] if codici else None

    def codici_provvisori(self, n_nuovo: int = 0) -> tuple[str, list[str]]:
        """``(base, [base + 'a', base + 'b', ...])``; ``NUOVA-<n>`` as base if no row has a code (new rows of the scan).
        Provisional: never written to the database."""
        base = self.codice_base or f'NUOVA-{n_nuovo:05d}'
        return base, [f'{base}{LETTERE[i] if i < len(LETTERE) else "z" + str(i)}' for i in range(len(self.righe))]


class CoppieVicine:
    """The links, the chains and the list of the pairs at a threshold.

    Args:
        soglia: the distance in characters (default :data:`SOGLIA_S08`).
    """

    def __init__(self, soglia: int = SOGLIA_S08) -> None:
        self.soglia = soglia

    @staticmethod
    def righe_per_atto(
        banca: Mapping[str, Riga], nuove: Iterable[Mapping[str, Any]] = ()
    ) -> dict[tuple[str, str], list[tuple[int, str, Riga]]]:
        """``{(document_id, case): [(char_start, key, row)]}`` in text order.

        Live rows with a position; ``nuove``: rows recovered by the scan (dicts with ``document_id``, ``caso_citato``,
        ``char_start``, ``pagina``, ``chiave``), without a code.
        """
        per: dict[tuple[str, str], list[tuple[int, str, Riga]]] = collections.defaultdict(list)
        for i, r in banca.items():
            pos = posizione_di_riga(r)
            if r.get('proposto_rete') in RETI_VIVE and r.get('document_id') and pos is not None:
                per[(r['document_id'], r['caso_citato'])].append((pos, i, r))
        for n in nuove:
            per[(n['document_id'], n['caso_citato'])].append((int(n['char_start']), n['chiave'], n))
        for v in per.values():
            v.sort(key=lambda x: (x[0], str(x[1])))
        return per

    def legami(
        self, per: Mapping[tuple[str, str], Sequence[tuple[int, str, Riga]]], soglia: int | None = None
    ) -> list[Legame]:
        """The links between CONSECUTIVE rows (in the order of the text) of the same filing and case at a distance up to
        the threshold. With three rows at 100 and 150 characters there are two links (A-B, B-C): the chain."""
        soglia = self.soglia if soglia is None else soglia
        out: list[Legame] = []
        for k, v in per.items():
            for (pa, ia, ra), (pb, ib, rb) in pairwise(v):
                if pb - pa <= soglia:
                    out.append(Legame(pb - pa, k, (ia, ra), (ib, rb)))
        return out

    @staticmethod
    def catene(legami: Sequence[Legame]) -> list[Catena]:
        """The chains: the links of one filing and case that follow each other, with at least two rows."""
        per: dict[tuple[str, str], list[Legame]] = collections.defaultdict(list)
        for lg in legami:
            per[lg.atto].append(lg)
        out: list[Catena] = []
        for k, ls in per.items():
            cur = [ls[0].a, ls[0].b]
            for lg in ls[1:]:
                if lg.a[0] == cur[-1][0]:
                    cur.append(lg.b)
                else:
                    out.append(Catena(k, tuple(cur)))
                    cur = [lg.a, lg.b]
            out.append(Catena(k, tuple(cur)))
        return out

    def elenco(self, banca: Mapping[str, Riga], nuove: Iterable[Mapping[str, Any]] = ()) -> list[dict[str, Any]]:
        """One element per LINK: ``{id, base, caso, atto, distanza, stessa_pagina, a, b}``, with the provisional codes
        of the chain (``<base>a``, ``<base>b``, ``<base>c``); ``a`` and ``b`` are ``{prov, chiave, codice, char_start,
        pagina, nuova}``. Sorted by case, filing and position."""
        per = self.righe_per_atto(banca, nuove)
        legami = self.legami(per)
        prov: dict[tuple[tuple[str, str], str], tuple[str, str]] = {}
        n_nuovo = 0
        for catena in self.catene(legami):
            if not catena.codice_base:
                n_nuovo += 1
            base, codici = catena.codici_provvisori(n_nuovo)
            for (chiave, _), c in zip(catena.righe, codici, strict=True):
                prov[(catena.atto, chiave)] = (base, c)
        out: list[dict[str, Any]] = []
        for lg in legami:
            (ia, ra), (ib, rb) = lg.a, lg.b
            base, ca = prov[(lg.atto, ia)]
            _, cb = prov[(lg.atto, ib)]
            pa, pb = pagina_di_riga(ra), pagina_di_riga(rb)
            out.append(
                {
                    'id': f'{ca}-{cb}',
                    'base': base,
                    'caso': lg.atto[1],
                    'atto': lg.atto[0],
                    'distanza': lg.distanza,
                    'stessa_pagina': pa is not None and pa == pb,
                    'a': self._estremo(ca, ia, ra, pa),
                    'b': self._estremo(cb, ib, rb, pb),
                }
            )
        out.sort(key=lambda x: (x['caso'], x['atto'], x['a']['char_start']))
        return out

    @staticmethod
    def _estremo(prov: str, chiave: str, riga: Riga, pagina: int | None) -> dict[str, Any]:
        return {
            'prov': prov,
            'chiave': chiave,
            'codice': riga.get('codice'),
            'char_start': posizione_di_riga(riga),
            'pagina': pagina,
            'nuova': not riga.get('codice'),
        }

    def prova_due_lontane(
        self,
        attese: Iterable[tuple[str, str, int, int]],
        banca: Mapping[str, Riga],
        nuove: Iterable[Mapping[str, Any]] = (),
        soglia: int = 12000,
    ) -> list[tuple[str, str, int, int]]:
        """THE PROOF OF THE STEP (entry S08 of the registry): if two distant citations are on a page and only one comes
        out, it FAILS. ``attese``: ``[(case, document_id, char_a, char_b)]``, each of which must come out as a link of
        :meth:`elenco` at ``soglia``. Returns the missing ones (empty: the proof passes)."""
        visti = {
            (c['caso'], c['atto'], c['a']['char_start'], c['b']['char_start'])
            for c in self.elenco_a(banca, nuove, soglia)
        }
        return [x for x in attese if (x[0], x[1], min(x[2], x[3]), max(x[2], x[3])) not in visti]

    def elenco_a(
        self, banca: Mapping[str, Riga], nuove: Iterable[Mapping[str, Any]], soglia: int
    ) -> list[dict[str, Any]]:
        """:meth:`elenco` at another threshold."""
        return CoppieVicine(soglia).elenco(banca, nuove)

    def conta_soglie(
        self,
        banca: Mapping[str, Riga],
        nuove: Iterable[Mapping[str, Any]] = (),
        c03: frozenset[frozenset[str]] = frozenset(),
        soglie: Iterable[int] = SOGLIE,
    ) -> dict[int, dict[str, Any]]:
        """``{threshold: {'per_caso': {...}, 'totale': {...}}}``. For each threshold:

        - ``legami``: pairs of consecutive rows (the L13 questions);
        - ``catene``: the groups (a chain of k rows = k-1 links);
        - ``righe``: live rows involved;
        - ``stessa_pagina``: links with the two rows on the same page (the loss of S07);
        - ``gia_c03``: links C03 already finds (same sentence);
        - ``nuovi_legami``: links with at least one NEW row (recovered, not in the database);
        - ``catena_piu_lunga``.

        ``nuove`` are the «new» rows of the scan (not absorbed).
        """
        out: dict[int, dict[str, Any]] = {}
        per = self.righe_per_atto(banca, nuove)
        for s in soglie:
            legami = self.legami(per, s)
            d: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
            for lg in legami:
                c = d[lg.atto[1]]
                (_, ra), (_, rb) = lg.a, lg.b
                c['legami'] += 1
                pa, pb = pagina_di_riga(ra), pagina_di_riga(rb)
                if pa is not None and pa == pb:
                    c['stessa_pagina'] += 1
                ca, cb = ra.get('codice'), rb.get('codice')
                if ca and cb and frozenset((ca, cb)) in c03:
                    c['gia_c03'] += 1
                if not ca or not cb:
                    c['nuovi_legami'] += 1
            for catena in self.catene(legami):
                c = d[catena.atto[1]]
                c['catene'] += 1
                c['righe'] += len(catena.righe)
                c['catena_piu_lunga'] = max(c['catena_piu_lunga'], len(catena.righe))
            totale: collections.Counter[str] = collections.Counter()
            for c in d.values():
                for k, v in c.items():
                    totale[k] = max(totale[k], v) if k == 'catena_piu_lunga' else totale[k] + v
            out[s] = {'per_caso': {k: dict(v) for k, v in d.items()}, 'totale': dict(totale)}
        return out

    def righe_nuove_vicine(
        self, nuove: Sequence[Mapping[str, Any]], banca: Mapping[str, Riga], soglie: Iterable[int] = SOGLIE
    ) -> dict[int, dict[str, int]]:
        """For each threshold: how many new rows stand within it of a live row of the same filing (they become a pair)
        and how many farther (they stay alone, without an L13 question)."""
        per_vive = self.righe_per_atto(banca)
        distanze = [distanza_da_righe(n, per_vive) for n in nuove]
        out: dict[int, dict[str, int]] = {}
        for s in soglie:
            vicine = sum(1 for x in distanze if x is not None and x <= s)
            out[s] = {'vicine_a_una_riga_viva': vicine, 'sole_o_lontane': len(distanze) - vicine}
        return out

    @staticmethod
    def coppie_c03(banca: Mapping[str, Riga]) -> frozenset[frozenset[str]]:
        """The body/footnote pairs C03 already finds (same supported sentence): a subset of the close pairs."""
        coppie = GeneratoreCoppie().testo_nota(banca, set())
        return frozenset(frozenset((c.tenuta['codice'], c.esce['codice'])) for c in coppie)


def distanza_da_righe(
    rec: Mapping[str, Any], per_vive: Mapping[tuple[str, str], Sequence[tuple[int, str, Riga]]]
) -> int | None:
    """The distance from the nearest live row of the same filing and case (``None`` if there is none)."""
    v = per_vive.get((rec['document_id'], rec['caso_citato'])) or []
    if not v:
        return None
    pos = [x[0] for x in v]
    j = bisect.bisect_left(pos, rec['char_start'])
    return min(abs(pos[k] - rec['char_start']) for k in (j - 1, j) if 0 <= k < len(pos))


def classifica_recuperate(recuperate: Iterable[Mapping[str, Any]], banca: Mapping[str, Riga]) -> list[dict[str, Any]]:
    """«assorbita» (within :data:`ASSORBITA` characters of a name or of a live row) or «nuova»; adds ``chiave``,
    ``dist_riga`` and ``esito`` to each recovered group."""
    per_vive = CoppieVicine.righe_per_atto(banca)
    out = []
    for r in recuperate:
        dr = distanza_da_righe(r, per_vive)
        dn = r.get('dist_nome')
        distanze = [x for x in (dr, dn) if x is not None]
        m = min(distanze) if distanze else None
        out.append(
            dict(
                r,
                chiave=f'S08-{r["caso_citato"]}-{r["document_id"][-8:]}-{r["char_start"]}',
                dist_riga=dr,
                esito='assorbita' if (m is not None and m < ASSORBITA) else 'nuova',
            )
        )
    return out


class Taratura:
    """THE THRESHOLD IS CHOSEN WITH THE NUMBERS (5 October 2026, the PI: «every choice motivated, it is for the paper»).

    The truth are the 850 pairs of C03 reread by hand on 4 October: 693 UNIRE (one citation), 156 TENERE TUTTE E DUE
    (two) and 1 INCERTA (left out). Here count the 692 pairs with the two rows IN THE SAME FILING (the 157 translations
    are in two filings: S08 works inside one filing, translations stay with C03 and its test 8).

    What is measured:

    - ``distanze``: the characters between the two names, for UNIRE and TENERE (percentiles);
    - coverage: for each threshold, how many UNIRE and TENERE become a candidate pair, in two ways: the pair of rows at
      distance <= threshold, and the two rows in the same chain (S08 would link them, even with a row in between);
    - cost: the links (= L13 questions, each five readings of DeepSeek) at each threshold, and the extra links per extra
      UNIRE between a threshold and the next.

    The threshold chosen is the first beyond which the extra UNIRE cost more than ``COSTO_MASSIMO`` links each: it is a
    DECISION OF COST, not a threshold found in the data (the distances of UNIRE and TENERE overlap: distance does not
    separate the classes, it only decides where to stop looking).

    A DECLARED LIMIT. The pairs of C03 are born from the same supported sentence at most one page apart: the truth is
    «censored» at one page and says nothing about farther UNIRE. That is why the threshold is not the maximum of the
    UNIRE seen (5,834 characters) but a little less: beyond a page (median ``pagina_mediana``) C03 did not look.

    Args:
        banca: ``{id: row}``.
        verita: the file of the pairs reread by hand (tab-separated).
    """

    COSTO_MASSIMO = 50

    def __init__(self, banca: Mapping[str, Riga], verita: Path | str) -> None:
        self.banca = banca
        self.cod = {r.get('codice'): r for r in banca.values() if r.get('codice')}
        with open(verita, encoding='utf-8', newline='') as f:
            self.righe = list(csv.DictReader(f, delimiter='\t'))
        self.vicine = CoppieVicine()

    def coppie_stesso_atto(self) -> list[tuple[str, Riga, Riga, str]]:
        """``[(decision, row_a, row_b, id)]`` for the pairs with both rows in the same filing; UNIRE or TENERE."""
        out = []
        for r in self.righe:
            a = self.cod.get(r['codice_tenuto_dalla_regola'])
            b = self.cod.get(r['codice_che_esce_per_la_regola'])
            if not a or not b or a['document_id'] != b['document_id']:
                continue
            d = {'UNIRE': 'UNIRE', 'TENERE TUTTE E DUE': 'TENERE'}.get(r['decisione'])
            if d:
                out.append((d, a, b, r['id']))
        return out

    @staticmethod
    def percentili(v: Iterable[int]) -> dict[str, int]:
        """Percentiles 5, 25, 50, 75, 90, 95, 99 plus minimum and maximum."""
        v = sorted(v)
        return {f'p{p}': v[min(len(v) - 1, int(len(v) * p / 100))] for p in (5, 25, 50, 75, 90, 95, 99)} | {
            'min': v[0],
            'max': v[-1],
        }

    def catene_a(self, soglia: int) -> dict[str, int]:
        """``{row key: chain index}`` at this threshold (the live rows, connected components of the links)."""
        per = self.vicine.righe_per_atto(self.banca)
        cat: dict[str, int] = {}
        for n, catena in enumerate(self.vicine.catene(self.vicine.legami(per, soglia))):
            for chiave, _ in catena.righe:
                cat[chiave] = n
        return cat

    def pagina_mediana(self, atti: LettoreAtti, campione: int = 400) -> int | None:
        """The median length in characters of a page, on a sample of filings: it says how long a page is."""
        lun: list[int] = []
        for r in list(self.banca.values())[:3000]:
            if r.get('file') and len(lun) < campione and r.get('proposto_rete') in RETI_VIVE:
                seg = [m.start() for m in PAGINA.finditer(atti.testo(r['file']))]
                lun += [b - a for a, b in pairwise(seg)]
        return int(statistics.median(lun)) if lun else None

    def misura(self, soglie: Sequence[int] = SOGLIE, atti: LettoreAtti | None = None) -> dict[str, Any]:
        """The table of the coverage and the cost at every threshold, the distances and the threshold chosen."""
        cp = self.coppie_stesso_atto()
        dist: dict[str, list[int]] = {'UNIRE': [], 'TENERE': []}
        for d, a, b, _ in cp:
            dist[d].append(abs(int(a['char_start']) - int(b['char_start'])))
        n = {k: len(v) for k, v in dist.items()}
        per = self.vicine.righe_per_atto(self.banca)
        chiave = {id(r): i for i, r in self.banca.items()}
        tabella: list[dict[str, Any]] = []
        for s in soglie:
            legami = self.vicine.legami(per, s)
            cat = self.catene_a(s)
            coppie_chiave = {frozenset((lg.a[0], lg.b[0])) for lg in legami}
            riga: dict[str, Any] = {'soglia': s, 'legami': len(legami), 'catene': len(self.vicine.catene(legami))}
            for d in ('UNIRE', 'TENERE'):
                entro = sum(1 for x in dist[d] if x <= s)
                consecutive = sum(
                    1 for dd, a, b, _ in cp if dd == d and frozenset((chiave[id(a)], chiave[id(b)])) in coppie_chiave
                )
                stessa = sum(
                    1
                    for dd, a, b, _ in cp
                    if dd == d
                    and cat.get(chiave[id(a)]) is not None
                    and cat.get(chiave[id(a)]) == cat.get(chiave[id(b)])
                )
                riga[d] = {
                    'a_distanza': entro,
                    'consecutive': consecutive,
                    'stessa_catena': stessa,
                    'quota_stessa_catena': round(stessa / n[d], 4),
                }
            riga['legami_per_unire_in_piu'] = None
            if tabella:
                dun = riga['UNIRE']['stessa_catena'] - tabella[-1]['UNIRE']['stessa_catena']
                riga['legami_per_unire_in_piu'] = (
                    round((riga['legami'] - tabella[-1]['legami']) / dun, 1) if dun > 0 else None
                )
            tabella.append(riga)
        return {
            'coppie': n,
            'distanze': {k: self.percentili(v) for k, v in dist.items()},
            'tabella': tabella,
            'soglia_scelta': self.scegli(tabella),
            'pagina_mediana': self.pagina_mediana(atti) if atti else None,
            'costo_massimo': self.COSTO_MASSIMO,
        }

    def scegli(self, tabella: Sequence[Mapping[str, Any]]) -> int:
        """The first threshold after which the next costs more than ``COSTO_MASSIMO`` links for every extra UNIRE (or
        adds none)."""
        for prima, dopo in pairwise(tabella):
            c = dopo['legami_per_unire_in_piu']
            if c is None or c > self.COSTO_MASSIMO:
                return prima['soglia']
        return tabella[-1]['soglia']

    def indizi(self, atti: ArchivioAtti) -> dict[str, Any]:
        """The precision of every strong clue on the pairs of the truth: for every rule of :func:`verdetto_indizi`, how
        many times it fires and how many times it is right (UNIRE = «una», TENERE = «due»)."""
        conti: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
        tot: collections.Counter[str] = collections.Counter()
        for d, a, b, i in self.coppie_stesso_atto():
            esito, motivo, forte = verdetto_indizi(Coppia(a, b, atti, i).indizi())
            tot[d] += 1
            if esito:
                giusto = (esito == 'una') == (d == 'UNIRE')
                conti[motivo]['scatta'] += 1
                conti[motivo]['giusta' if giusto else 'sbagliata'] += 1
                conti[motivo]['forte'] = int(forte)
        risposta: dict[str, Any] = {
            m: dict(c) | {'precisione': round(c['giusta'] / c['scatta'], 4)} for m, c in conti.items()
        }
        return risposta | {'_coppie': dict(tot)}
