"""S08, the decision on the pairs: one = merge, two = keep, doubt = to the team (``decisione_coppie``).

Class-based version of ``tools/decidi_s08.py`` (5 October 2026). The rule of the PI (4-5 October 2026): the close
references to the same case in the same filing are candidate pairs; DeepSeek (L13, five readings) and the reasoning
reranker (three readings) read each pair in whole and answer «one citation or two?».

    una   the two readers say ONE and no strong clue says TWO: they are merged as in C03 (one row stays, the other keeps
          attached as support: ``unita_a``, ``esclusa_regola`` «S08»);
    due   the two readers say TWO and no strong clue says ONE: two rows count, nothing is written;
    team  every other case: the readers disagree, a reader is uncertain or has no valid answers (the brakes of
          :mod:`tracepipe.prova_intera` discarded its readings), a strong clue contradicts the readers. The pair goes to
          «To review».

S08 replaces the automatic rule of C03 for the NEW rows: the C03 rule (:class:`tracepipe.unione_c03.GeneratoreCoppie`)
stays only as a generator of candidates.

WHICH ROW STAYS (when it is «una»), in this order: the row not discarded by the team; the one confirmed by the team; the
row in the text (not in a note; from the text of the filing, because ``proposto_posizione`` is wrong in many rows); the
main one named by the readers (majority of A or B); the first in the filing. For TRANSLATIONS (two filings in different
languages) S08 does not decide: they stay with C03 and the original language reread by hand (the rule of the header
was wrong 46 times out of 105).

WITHOUT WRITING. This module prepares the decisions and the writes, in the same format as
:mod:`tracepipe.unione_c03`, and never writes them: S08 is written to the database only after the proof on the C03 pairs
and the PI's yes. The NEW rows of the scan have no code in the database yet: the pair is decided but the write waits for
them to be loaded (``scrittura rinviata``).
"""

from __future__ import annotations

import collections
import csv
import datetime
import gzip
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import Config
from .coppia import ArchivioAtti, Coppia, verdetto_indizi
from .coppie_vicine import Taratura
from .righe import RETI_VIVE, Riga
from .unione_c03 import appoggio

CODICE = 'S08'
"""The registry code of the rule."""
MIN_DS = 3
"""Of five valid DeepSeek readings, at least three equal (as L05)."""
MIN_RR = 2
"""Of three valid reranker readings, at least two equal."""

Stampa = Callable[[str], None]


def _stampa(testo: str) -> None:
    print(testo, flush=True)


class VerdettoLettore:
    """The verdict of a reader on a pair, from the votes of :func:`tracepipe.lettura_coppia.raccogli`.

    Args:
        nome: the name of the reader.
        minimo: how many equal valid readings make a verdict.
    """

    def __init__(self, nome: str, minimo: int) -> None:
        self.nome = nome
        self.minimo = minimo

    def verdetto(self, raccolta: Mapping[str, Any] | None) -> tuple[str | None, dict[str, int]]:
        """``('una'|'due'|'incerta'|None, votes)``: ``None`` = no valid reading (the brakes) or no reading."""
        if not raccolta or not raccolta.get('valide'):
            return None, {}
        voti = raccolta['voti']
        esito, n = max(voti.items(), key=lambda kv: kv[1])
        if sum(1 for v in voti.values() if v == n) > 1 or n < self.minimo:
            return 'incerta', voti  # a tie, or no majority
        return esito, voti

    @staticmethod
    def principale(raccolta: Mapping[str, Any] | None) -> str:
        """The main row named by the majority of the valid «una» readings (``A`` or ``B``), or ``''``."""
        c: collections.Counter[str] = collections.Counter(
            (x['json'].get('riga_principale') or '')
            for x in (raccolta or {}).get('letture', [])
            if x['valida'] and x['json'].get('esito') == 'una'
        )
        c.pop('', None)
        return c.most_common(1)[0][0] if c else ''


class Decisione:
    """The outcome of a pair.

    Args:
        id_coppia: the id of the pair.
        esito: ``'una'``, ``'due'`` or ``'team'``.
        motivo: why, in words.
        tenuta: the row that stays (only for ``una``).
        esce: the row that goes out (only for ``una``).
        extra: votes and clues, for the report.
    """

    def __init__(
        self,
        id_coppia: str,
        esito: str,
        motivo: str,
        tenuta: Riga | None = None,
        esce: Riga | None = None,
        **extra: Any,
    ) -> None:
        self.id, self.esito, self.motivo, self.tenuta, self.esce, self.extra = (
            id_coppia,
            esito,
            motivo,
            tenuta,
            esce,
            extra,
        )

    def riga(self) -> dict[str, Any]:
        """The decision as a flat row for the report file."""
        return {
            'id': self.id,
            'esito': self.esito,
            'motivo': self.motivo,
            'tiene': (self.tenuta or {}).get('codice'),
            'esce': (self.esce or {}).get('codice'),
            **self.extra,
        }


class Decisore:
    """Puts the two readers and the clues together.

    With ``solo_indizi`` it decides with the strong clues only (no reader: it serves to try the system on the reviewed
    C03 pairs and to say how many pairs the clues alone leave to the team).
    """

    def __init__(self, solo_indizi: bool = False) -> None:
        self.ds = VerdettoLettore('DeepSeek L13', MIN_DS)
        self.rr = VerdettoLettore('Qwen3.5-9B', MIN_RR)
        self.solo_indizi = solo_indizi

    @staticmethod
    def giudizio(riga: Riga) -> str:
        """The verdict of the team on the row, ``''`` if none."""
        return str(riga.get('esito') or '')

    def riga_tenuta(self, c: Coppia, principale: str = '') -> tuple[Riga, Riga]:
        """``(kept, excluded)`` between the two rows of the pair, with the rule written at the top of the module."""
        a, b = c.a, c.b
        scartate = (self.giudizio(a) == 'scartata', self.giudizio(b) == 'scartata')
        if scartate[0] != scartate[1]:
            return (b, a) if scartate[0] else (a, b)
        confermate = (self.giudizio(a) == 'confermata', self.giudizio(b) == 'confermata')
        if confermate[0] != confermate[1]:
            return (a, b) if confermate[0] else (b, a)
        pa, pb = c.posizione(a), c.posizione(b)
        if pa != pb:
            return (a, b) if pa == 'testo' else (b, a)
        if principale in ('A', 'B'):
            return (a, b) if principale == 'A' else (b, a)
        return a, b

    def decidi(
        self, c: Coppia, raccolta_ds: Mapping[str, Any] | None = None, raccolta_rr: Mapping[str, Any] | None = None
    ) -> Decisione:
        """The decision on one pair."""
        ind = c.indizi()
        i_esito, i_motivo, i_forte = verdetto_indizi(ind)
        extra: dict[str, Any] = {
            'indizio': i_esito or '',
            'indizio_motivo': i_motivo,
            'indizio_forte': int(i_forte),
            'distanza': ind['distanza'],
            'stessa_pagina': int(ind['stessa_pagina']),
        }
        if self.solo_indizi:
            if i_esito == 'una' and i_forte:
                t, e = self.riga_tenuta(c)
                return Decisione(c.id, 'una', 'solo indizi: ' + i_motivo, t, e, **extra)
            return Decisione(c.id, 'team', 'senza lettori nessun indizio forte', **extra)
        d, vd = self.ds.verdetto(raccolta_ds)
        r, vr = self.rr.verdetto(raccolta_rr)
        extra |= {
            'voti_ds': json.dumps(vd, ensure_ascii=False),
            'voti_rr': json.dumps(vr, ensure_ascii=False),
            'ds': d or '',
            'rr': r or '',
        }
        if d is None or r is None:
            return Decisione(
                c.id, 'team', 'manca un lettore o tutte le sue letture sono state scartate dai freni', **extra
            )
        if d == 'incerta' or r == 'incerta':
            return Decisione(c.id, 'team', "un lettore e' incerto o senza maggioranza", **extra)
        if d != r:
            return Decisione(c.id, 'team', f'disaccordo: DeepSeek {d}, reranker {r}', **extra)
        if i_forte and i_esito != d:
            return Decisione(
                c.id, 'team', f'i lettori dicono {d} ma un indizio forte dice {i_esito} ({i_motivo})', **extra
            )
        if d == 'due':
            return Decisione(c.id, 'due', 'i due lettori dicono due citazioni', **extra)
        principale = self.ds.principale(raccolta_ds) or self.rr.principale(raccolta_rr)
        t, e = self.riga_tenuta(c, principale)
        return Decisione(c.id, 'una', 'i due lettori dicono una citazione', t, e, **extra)


class ScrittureS08:
    """The PREPARED writes (never executed here), in the format of :mod:`tracepipe.unione_c03`.

    On the excluded row ``proposto_rete`` «esclusa», ``esclusa_rete_prima``, ``esclusa_regola`` «S08», ``unita_a``,
    ``esclusa_motivo``, ``esclusa_da``; on the kept row ``proposto_nota_appoggio``, the merged ``proposto_paragrafi``,
    ``s08_da``. A chain (A keeps B, B keeps C) closes on the final row; a row that goes out in two pairs goes out
    once; a row without a code (new) postpones the write.

    Args:
        banca: ``{id: row}`` snapshot.
        da: who prepares them (``esclusa_da``, ``s08_da``).
    """

    def __init__(self, banca: Mapping[str, Riga], da: str = CODICE) -> None:
        self.banca = banca
        self.da = da
        self.id_di = {r.get('codice'): i for i, r in banca.items() if r.get('codice')}

    def prepara(self, decisioni: Iterable[Decisione]) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
        """``({row id: fields}, {reason: number of pairs skipped})``."""
        decisioni = [d for d in decisioni if d.esito == 'una']
        tenuta_di = {
            d.esce['codice']: d.tenuta['codice']
            for d in decisioni
            if d.tenuta and d.esce and d.tenuta.get('codice') and d.esce.get('codice')
        }

        def finale(codice: str, passi: int = 0) -> str:
            return finale(tenuta_di[codice], passi + 1) if codice in tenuta_di and passi < 10 else codice

        out: dict[str, dict[str, Any]] = {}
        visti: set[str] = set()
        saltate: collections.Counter[str] = collections.Counter()
        per_codice = {r.get('codice'): r for r in self.banca.values() if r.get('codice')}
        for d in decisioni:
            if not d.tenuta or not d.esce or not d.tenuta.get('codice') or not d.esce.get('codice'):
                saltate['scrittura rinviata: riga nuova senza codice in banca'] += 1
                continue
            t, n = per_codice.get(finale(d.tenuta['codice'])), per_codice.get(d.esce['codice'])
            if not t or not n or t is n:
                saltate['riga assente o catena chiusa su se stessa'] += 1
            elif n['codice'] in visti:
                saltate["riga che esce gia' in un'altra coppia"] += 1
            elif (
                n.get('proposto_rete') not in RETI_VIVE
                or t.get('proposto_rete') not in RETI_VIVE
                or t.get('esito') == 'scartata'
            ):
                saltate["una riga non e' piu' viva o la tenuta e' scartata"] += 1
            else:
                visti.add(n['codice'])
                ine, it = self.id_di[n['codice']], self.id_di[t['codice']]
                out[ine] = {
                    'proposto_rete': 'esclusa',
                    'esclusa_rete_prima': n.get('proposto_rete'),
                    'esclusa_regola': CODICE,
                    'unita_a': t['codice'],
                    'esclusa_motivo': f'{CODICE} {d.motivo}',
                    'esclusa_da': self.da,
                }
                ct = out.setdefault(it, {'s08_da': self.da})
                ct.setdefault('proposto_nota_appoggio', []).append(appoggio(t, n))
                ct['proposto_paragrafi'] = sorted(
                    set(ct.get('proposto_paragrafi') or t.get('proposto_paragrafi') or [])
                    | set(n.get('proposto_paragrafi') or [])
                )
        return out, dict(saltate)


@dataclass
class Valutazione:
    """The result of :meth:`DecisioneCoppie.valuta`: the counts and the decision of every pair of the truth."""

    conti: dict[str, Any] = field(default_factory=dict)
    decisioni: list[tuple[str, str, Decisione]] = field(default_factory=list)


class DecisioneCoppie:
    """The S08 step: decide the pairs, prepare the writes, measure the system on the C03 truth. Never writes.

    Args:
        config: paths.
        banca: ``{id: row}`` snapshot of ``corpus_rows``.
        da: who prepares the writes.
        orologio: the clock of the report date.
        stampa: where the screen lines go.
    """

    def __init__(
        self,
        config: Config,
        banca: Mapping[str, Riga],
        da: str = CODICE,
        orologio: Callable[[], datetime.date] = datetime.date.today,
        stampa: Stampa = _stampa,
    ) -> None:
        self.config = config
        self.banca = banca
        self.da = da
        self.orologio = orologio
        self.stampa = stampa
        self.atti = ArchivioAtti(config.radice)

    @staticmethod
    def leggi_richieste(percorso: Path | str) -> list[dict[str, Any]]:
        """The requests of the pairs: a ``.json`` list or a ``.jsonl.gz`` file."""
        p = Path(percorso)
        if str(p).endswith('.json'):
            return json.loads(p.read_text(encoding='utf-8'))
        with gzip.open(p, 'rt', encoding='utf-8') as h:
            return [json.loads(x) for x in h]

    def decidi(
        self,
        richieste: Sequence[Mapping[str, Any]],
        ds: Mapping[str, Any] | None,
        rr: Mapping[str, Any] | None,
        uscita: Path | str,
    ) -> tuple[list[Decisione], dict[str, dict[str, Any]], dict[str, int]]:
        """Decide every pair whose two rows are in the database; write the report and the prepared writes (a secco)."""
        per_codice = {r.get('codice'): r for r in self.banca.values() if r.get('codice')}
        decisore = Decisore()
        decisioni: list[Decisione] = []
        for r in richieste:
            ca, cb = r['codici']
            ra, rb = per_codice.get(ca) if ca else None, per_codice.get(cb) if cb else None
            if not ra or not rb:
                continue  # pairs with new rows are decided when the rows are in the database
            decisioni.append(
                decisore.decidi(Coppia(ra, rb, self.atti, r['id']), (ds or {}).get(r['id']), (rr or {}).get(r['id']))
            )
        out = Path(uscita)
        out.mkdir(parents=True, exist_ok=True)
        if decisioni:
            with open(out / 'decisioni_s08.tsv', 'w', newline='', encoding='utf-8') as h:
                w = csv.DictWriter(h, list(decisioni[0].riga()), delimiter='\t', extrasaction='ignore')
                w.writeheader()
                w.writerows(d.riga() for d in decisioni)
        scritture, saltate = ScrittureS08(self.banca, self.da).prepara(decisioni)
        (out / 'scritture_s08_A_SECCO.json').write_text(
            json.dumps(
                {'data': self.orologio().isoformat(), 'scritture': scritture, 'saltate': saltate}, ensure_ascii=False
            ),
            encoding='utf-8',
        )
        self.stampa(
            f'{collections.Counter(d.esito for d in decisioni)} scritture preparate: {len(scritture)} {saltate} '
            '(A SECCO: niente scritto)'
        )
        return decisioni, scritture, saltate

    def valuta(
        self,
        verita: Path | str,
        raccolte_ds: Mapping[str, Any] | None = None,
        raccolte_rr: Mapping[str, Any] | None = None,
        solo_indizi: bool = False,
    ) -> Valutazione:
        """The 692 C03 pairs reread by hand in the same filing as the truth (UNIRE = one, TENERE = two): for every pair
        the decision of S08, then the counts: right, wrong (one instead of two or the reverse), to the team; and, for
        the UNIRE decided «una», how many times S08 keeps the right row."""
        tara = Taratura(self.banca, verita)
        righe = {r['id']: r for r in tara.righe}
        dec = Decisore(solo_indizi)
        conti: collections.Counter[tuple[str, str]] = collections.Counter()
        riga_giusta = rg_tot = 0
        tutte: list[tuple[str, str, Decisione]] = []
        for d, a, b, i in tara.coppie_stesso_atto():
            c = Coppia(a, b, self.atti, f'{a["codice"]}__{b["codice"]}')
            x = dec.decidi(c, (raccolte_ds or {}).get(c.id), (raccolte_rr or {}).get(c.id))
            attesa = 'una' if d == 'UNIRE' else 'due'
            conti[(attesa, x.esito)] += 1
            tutte.append((i, attesa, x))
            if d == 'UNIRE':  # which row stays, even for the pairs S08 sends to the team (the rule alone)
                t, _ = dec.riga_tenuta(c)
                rg_tot += 1
                riga_giusta += int(t['codice'] == righe[i]['riga_da_tenere'])
        n: collections.Counter[str] = collections.Counter()
        for (att, _), v in conti.items():
            n[att] += v
        ris: dict[str, Any] = {
            'coppie': dict(n),
            'matrice': {f'{k[0]}->{k[1]}': v for k, v in sorted(conti.items())},
            'decise_giuste': conti[('una', 'una')] + conti[('due', 'due')],
            'decise_sbagliate': conti[('una', 'due')] + conti[('due', 'una')],
            'al_team': conti[('una', 'team')] + conti[('due', 'team')],
            'riga_tenuta_giusta_sulle_unire': f'{riga_giusta}/{rg_tot}',
            'modo': 'solo indizi' if solo_indizi else 'lettori + indizi',
        }
        decise = ris['decise_giuste'] + ris['decise_sbagliate']
        ris['precisione_sulle_decise'] = round(ris['decise_giuste'] / decise, 4) if decise else None
        ris['quota_decise'] = round(decise / sum(n.values()), 4)
        return Valutazione(ris, tutte)
