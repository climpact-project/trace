"""The two checks run after every load (``controlli``: checks).

- :class:`ControlloCompletezza`: does every Uptakes row have everything it must have?
  (``tools/controllo_completezza.py``, 29/09/2026). It starts from the DATABASE, not from the files: rows missing
  from the prepared files would otherwise stay without proposals unseen. Prints the problems per case, writes the
  ids of the rows to judge without proposals in ``training/mancanti_<case>_<date>.txt`` and, with ``scrivi``, the
  report in ``trace_controlli/<date>``.
- :class:`ControlloFinestra`: are the pages of the window (10 before, 10 after the citation) all scored by the
  reranker? (``tools/controllo_finestra.py``, 01/10/2026). The operation is finished only with zero missing pages.

Same screen lines, files and writes as the live scripts.
"""

from __future__ import annotations

import collections
import datetime
import glob
import gzip
import json
import re
from collections.abc import Callable, Mapping
from typing import Any

from . import casi_registro
from .banca import BancaDati
from .config import Config
from .pagine_attorno import numero_pagina

PREFISSI: Mapping[str, str] = dict(casi_registro.PREFISSI)
"""The code prefix of each case (``URG-0001``...)."""

Stampa = Callable[[str], None]


def _stampa(testo: str) -> None:
    print(testo, flush=True)


class ControlloCompletezza:
    """The completeness check of the Uptakes rows.

    Args:
        config: paths.
        banca: the platform database.
        scrivi: write the report in ``trace_controlli`` (``--scrivi``).
        stampa: where the screen lines go.
        orologio: the clock that names the report and the missing files.
    """

    def __init__(
        self,
        config: Config,
        banca: BancaDati,
        scrivi: bool = False,
        stampa: Stampa = _stampa,
        orologio: Callable[[], datetime.datetime] = datetime.datetime.now,
    ) -> None:
        self.config = config
        self.banca = banca
        self.scrivi = scrivi
        self.stampa = stampa
        self.orologio = orologio

    @staticmethod
    def problemi_riga(
        rid: str, r: Mapping[str, Any], pre: str, versioni: set[str], problemi: dict[str, list[str]]
    ) -> list[str]:
        """Add the problems of one Uptakes row to ``problemi``; return what is missing among the proposals."""
        cod = r.get('codice') or ''
        chi = cod or rid
        if not re.fullmatch(pre + r'-\d{4}', cod):
            problemi['codice mancante o sbagliato'].append(chi)
        if not r.get('document_id') or not r.get('file'):
            problemi['senza documento'].append(chi)
        pv = r.get('provenienza') or {}
        if not pv:
            problemi['senza provenienza'].append(chi)
        usate = [pv.get(k) for k in ('corpus', 'estrazione', 'tipo', 'composizione', 'seguito', 'sonde')]
        # since 01/10/2026 every proposal of principles says with which probe series it was made (family P)
        if not r.get('esito') and r.get('proposto_principi') and not pv.get('sonde'):
            problemi['principi proposti senza il codice delle sonde'].append(chi)
        usate += [x for v in (pv.get('principi') or {}).values() for x in v]
        for u in usate:
            if u and u not in versioni:
                problemi[f'versione {u} assente dal registro'].append(chi)
        manca = []
        if not r.get('proposto_tipo_citazione'):
            manca.append('tipo proposto')
        # an EMPTY list counts as missing too (review of 30/09/2026: 247 rows with [] passed the check)
        if r.get('proposto_principi') is None or r.get('proposto_principi') == []:
            manca.append('principi proposti')
        if not r.get('proposto_punteggi_principi'):
            manca.append('punteggi del reranker')
        for m in manca:
            problemi[f'senza {m}'].append(chi)
        if r.get('proposto_tipo_citazione') and not pv.get('tipo'):
            problemi['tipo proposto senza versione'].append(chi)
        if r.get('proposto_principi') and r.get('proposto_principi') != ['nessuno'] and not pv.get('principi'):
            problemi['principi proposti senza versione'].append(chi)
        if not pv.get('estrazione'):
            problemi['senza la versione della ricerca'].append(chi)
        # the brakes (30/09/2026): no proposal rests on invented or missing evidence
        for e in r.get('proposto_estensione') or []:
            if e.get('prova_esito') == 'inventata':
                problemi['prova inventata (copiata dal prompt)'].append(chi)
                break
        # only rows to judge: judged rows keep the proposals the person saw (before the brakes)
        if not r.get('esito') and any(
            e.get('prosegue') and not e.get('testuale') for e in (r.get('proposto_estensione') or [])
        ):
            problemi['pagina spuntata senza prova trovata'].append(chi)
        if r.get('proposto_frase_esito') == 'inventata':
            problemi['frase sostenuta inventata'].append(chi)
        if r.get('proposta_provvisoria') and not r.get('esito'):
            problemi['proposta provvisoria, in attesa della lettura di DeepSeek'].append(chi)
        if r.get('esito'):
            if not r.get('validato_da'):
                problemi['giudicata senza chi'].append(chi)
            if not r.get('validato_il'):
                problemi['giudicata senza quando'].append(chi)
            if r.get('esito') == 'confermata' and r.get('validato_principi') is None:
                problemi['confermata senza principi salvati'].append(chi)
        elif r.get('validato_da') and not r.get('da_discutere'):
            problemi['chi senza giudizio'].append(chi)
        return manca

    def caso(self, caso: str, pre: str, versioni: set[str], oggi: str) -> dict[str, Any]:
        """Check one case, print its lines, write its missing file; return its part of the report."""
        righe = list(self.banca.righe('corpus_rows', [('caso_citato', '==', caso)]))
        codici = {r.get('codice'): (i, r) for i, r in righe if r.get('codice')}
        problemi: dict[str, list[str]] = collections.defaultdict(list)
        mancanti: list[str] = []
        viste: collections.Counter[str] = collections.Counter()
        for i, r in righe:
            rete = r.get('proposto_rete')
            if rete == 'fusa':
                t = codici.get(r.get('fusa_in'))
                if not t:
                    problemi['unita verso un codice che non esiste'].append(r.get('codice') or i)
                elif t[1].get('proposto_rete') == 'fusa':
                    problemi['unita verso una riga a sua volta unita'].append(r.get('codice') or i)
                continue
            if rete not in ('lessicale', 'entrambe', 'descrittiva'):
                continue
            viste[r.get('codice') or ''] += 1
            manca = self.problemi_riga(i, r, pre, versioni, problemi)
            if manca and not r.get('esito') and not r.get('proposta_provvisoria'):
                mancanti.append(i)
        for cod, n in viste.items():
            if cod and n > 1:
                problemi['codice doppio'].append(cod)
        tot = sum(1 for _, r in righe if r.get('proposto_rete') in ('lessicale', 'entrambe', 'descrittiva'))
        self.stampa(f'\n{caso}: {tot} rows in Uptakes')
        if not problemi:
            self.stampa('   all in order')
        for k, v in sorted(problemi.items()):
            self.stampa(f'   {k}: {len(v)}  {v[:8]}')
        if mancanti:
            f = self.config.training / f'mancanti_{caso}_{oggi}.txt'
            f.write_text('\n'.join(mancanti) + '\n')
            self.stampa(f'   rows to judge without proposals: {len(mancanti)} -> {f.name}')
        return {
            'righe': tot,
            'problemi': {k: {'quante': len(v), 'esempi': v[:50]} for k, v in problemi.items()},
            'senza_proposte_da_giudicare': len(mancanti),
        }

    def esegui(self) -> dict[str, Any]:
        """Check every case; returns the report (written only with ``scrivi``)."""
        versioni = self.banca.ids('trace_versioni')
        oggi = self.orologio().strftime('%Y-%m-%d_%H%M')
        rapporto: dict[str, Any] = {
            'quando': self.banca.ora_del_server,
            'versioni_nel_registro': sorted(versioni),
            'casi': {},
        }
        for caso, pre in PREFISSI.items():
            rapporto['casi'][caso] = self.caso(caso, pre, versioni, oggi)
        if self.scrivi:
            self.banca.imposta('trace_controlli', oggi, rapporto)
            self.stampa(f'\nwritten trace_controlli/{oggi}')
        return rapporto


class ControlloFinestra:
    """The window check: pages of the window that exist in the corpus and have no reranker score.

    Args:
        config: paths, probe series, window width.
        compat: rows without a page number are checked as if the citation were on page 0 (the live defect fixed on
            02/10/2026 in the window selection; fixed, such a row has no window to check).
        stampa: where the screen lines go.
    """

    def __init__(self, config: Config, compat: bool = False, stampa: Stampa = _stampa) -> None:
        self.config = config
        self.compat = compat
        self.stampa = stampa

    def esistenti(self) -> set[str]:
        out = set()
        with gzip.open(self.config.indice_pagine, 'rt', encoding='utf-8') as f:
            for riga in f:
                out.add(json.loads(riga)['id'])
        return out

    def file_punteggi(self, caso: str) -> list[str]:
        """The score files of the series in use (``glob`` order, as live: the order does not change the result)."""
        p = self.config.principi
        if self.config.storica(caso):
            return glob.glob(str(p / f'{caso}_punteggi_*.jsonl')) + glob.glob(
                str(p / f'{caso}_finestra_punteggi_*.jsonl')
            )
        return glob.glob(str(p / f'{caso}{self.config.suf(caso)}_punteggi_*.jsonl'))

    def pagina(self, r: Mapping[str, Any]) -> int | None:
        if self.compat:
            # NOTE(bug): live, a row without a page number is checked as if the citation were on page 0.
            return int(r.get('pagina') or 0)
        return numero_pagina(r.get('pagina'))

    def esegui(self) -> int:
        """Print one line per case and the verdict; returns 0 if the window is complete, 1 otherwise."""
        esistenti = self.esistenti()
        larga = self.config.finestra.larga
        totale = 0
        for caso in self.config.casi:
            con = set()
            for fn in self.file_punteggi(caso):
                with open(fn, encoding='utf-8') as f:
                    for riga in f:
                        x = json.loads(riga)
                        if x['dove'] != 'brano':
                            con.add(x['pagina_id'])
            manca: collections.Counter[str] = collections.Counter()
            righe_con_buchi = 0
            with open(self.config.training / f'lessicali_{caso}_righe.jsonl', encoding='utf-8') as f:
                for riga in f:
                    r = json.loads(riga)
                    p = self.pagina(r)
                    buchi = 0
                    if p is not None:
                        for k in range(p - larga, p + larga + 1):
                            pid = f'{r["document_id"]}#p{k}'
                            if k != p and k > 0 and pid in esistenti and pid not in con:
                                manca[pid] += 1
                                buchi += 1
                    righe_con_buchi += bool(buchi)
            totale += len(manca)
            self.stampa(
                f'{caso} (probes {self.config.codice(caso)}): window pages without a score {len(manca)}, '
                f'citations with gaps {righe_con_buchi}'
            )
        self.stampa('WINDOW COMPLETE' if totale == 0 else f'WINDOW INCOMPLETE: {totale} pages without a score')
        return 0 if totale == 0 else 1
