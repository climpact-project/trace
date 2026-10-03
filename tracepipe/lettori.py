"""The three DeepSeek readers as classes sharing one base (``lettori``: readers).

- :class:`LettoreTipo`: the citation type (``tools/classifica_lessicali.py leggi``, L02 Urgenda, L03 the others);
- :class:`LettorePrincipi`: the principles as read on 27/09/2026 (``tools/leggi_l04.py leggi``, L04);
- :class:`LettorePagineAttorno`: principles, surrounding pages and supported sentence (``tools/leggi_ripresa.py
  leggi``, L05).

What they share (:class:`Lettore`): the rows to read, the output file read back to skip the rows already done (or, with
``solo_vuote``, to redo only the readings left empty, keeping the good ones of the same row; or, with
``aggiungi_letture``, to top every row up to ``k`` valid readings of the very same prompt), ``k`` readings per row
with :class:`tracepipe.deepseek.ClienteDeepSeek`, a thread pool whose output keeps the order of the input rows
(``ThreadPoolExecutor.map``), one JSON line appended and flushed per row, progress lines on screen.

The prompts are byte-identical to the live builders and the output records have the same keys in the same order.

``compat=True`` reproduces the readers of the harness (commit 8650281): reasoning cut at 4,000 (type) or 6,000
characters (L04/L05) and the call record without ``modello``, ``istruzioni_sha256``, ``parametri``. ``compat=False``
(the default) is today's live readers: full reasoning, full call record.
"""

from __future__ import annotations

import concurrent.futures as cf
import datetime
import hashlib
import json
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

import yaml

from .config import Config
from .deepseek import ClienteDeepSeek
from .istruzioni import FINE, INIZIO, MODULO_PAGINE_ATTORNO, MODULO_PRINCIPI, NOMI_BREVI, blocchi_codebook, modulo_tipo
from .letture import LETTURE_PROTOCOLLO, estrai_tollerante, vuota

MODELLO_TIPO = 'DeepSeek-V4-Flash-0731'
"""The model name written in the type readings (tools/classifica_lessicali.py MODELLO)."""

Stampa = Callable[[str], None]


def _stampa(testo: str) -> None:
    print(testo, flush=True)


def _leggi_jsonl(percorso: Path) -> list[dict[str, Any]]:
    with open(percorso, encoding='utf-8') as f:
        return [json.loads(riga) for riga in f]


class Lettore(ABC):
    """A DeepSeek reader of one case.

    Args:
        config: paths and probe series.
        caso: the cited case.
        cliente: the DeepSeek client (its ``osservatore`` is where the journal listens).
        letture: readings per row (``--letture``, k).
        paralleli: threads (``--paralleli``).
        etichetta: the label of the input and output files (``--etichetta``).
        solo_vuote: redo only the readings left empty, keep the good ones (``--solo-vuote``).
        aggiungi_letture: bring every row to ``letture`` valid readings, keeping the valid ones already made with the
            very same prompt (``--aggiungi-letture``, 02/10/2026; see :meth:`tenute`).
        compat: the harness readers (see the module docstring).
        stampa: where the screen lines go.
        orologio: the clock of the progress lines.
    """

    TAGLIO_RAGIONAMENTO = 6000
    """Reasoning kept per reading with ``compat`` (the harness readers cut it)."""
    OGNI = 50
    """A progress line every this many rows."""

    def __init__(
        self,
        config: Config,
        caso: str,
        cliente: ClienteDeepSeek,
        letture: int = LETTURE_PROTOCOLLO,
        paralleli: int = 48,
        etichetta: str = '',
        solo_vuote: bool = False,
        compat: bool = False,
        stampa: Stampa = _stampa,
        orologio: Callable[[], float] = time.time,
        aggiungi_letture: bool = False,
    ) -> None:
        if solo_vuote and aggiungi_letture:
            raise ValueError('--aggiungi-letture and --solo-vuote together: no')
        self.config = config
        self.caso = caso
        self.cliente = cliente
        self.letture = letture
        self.paralleli = paralleli
        self.etichetta = etichetta
        self.solo_vuote = solo_vuote
        self.aggiungi_letture = aggiungi_letture
        self._tenute: dict[str, tuple[list[int], int]] = {}
        self.compat = compat
        self.stampa = stampa
        self.orologio = orologio

    @property
    def suf(self) -> str:
        """``_<label>`` or empty."""
        return f'_{self.etichetta}' if self.etichetta else ''

    # what each reader defines
    @property
    @abstractmethod
    def file_righe(self) -> Path:
        """The rows to read."""

    @property
    @abstractmethod
    def file_uscita(self) -> Path:
        """The readings, appended."""

    @abstractmethod
    def prepara(self) -> None:
        """Read what the prompts need (case file, dossier, codebook): called once, before the rows."""

    @abstractmethod
    def prompt(self, r: Mapping[str, Any]) -> str:
        """The prompt of one row, byte-identical to the live builder."""

    @abstractmethod
    def extra_body(self) -> dict[str, Any]:
        """The ``extra_body`` of one request (a new dict per call, as live)."""

    @abstractmethod
    def messaggio_inizio(self, righe: list[dict[str, Any]], fatte: set[str], da_fare: list[dict[str, Any]]) -> str:
        """The first screen line."""

    @abstractmethod
    def lettura_tenuta(self, prima: Mapping[str, Any], k: int) -> tuple[Any, ...] | None:
        """``(reading, reasoning, [token,] call)`` of reading ``k`` kept from ``prima`` (``solo_vuote``), else None."""

    @abstractmethod
    def record(
        self, r: Mapping[str, Any], parti: list[list[Any]], rifatta: bool, aggiunte: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """The output line of one row (``aggiunte``: what ``--aggiungi-letture`` kept and added)."""

    @abstractmethod
    def parte_tenuta(self, prima: Mapping[str, Any], k: int) -> list[Any]:
        """``[reading, reasoning, [token,] call]`` of reading ``k`` of ``prima``, kept by ``--aggiungi-letture``."""

    # shared
    def righe(self) -> list[dict[str, Any]]:
        """The rows to read, as filtered by the reader."""
        return _leggi_jsonl(self.file_righe)

    def esistenti(self) -> dict[str, dict[str, Any]]:
        """The lines already in the output file, by id (the last one of an id wins)."""
        out: dict[str, dict[str, Any]] = {}
        if self.file_uscita.exists():
            with open(self.file_uscita, encoding='utf-8') as f:
                for riga in f:
                    x = json.loads(riga)
                    out[x['id']] = x
        return out

    @staticmethod
    def valida(y: Any) -> bool:
        """A reading that is an answer: read (not empty) and not unreadable."""
        return isinstance(y, dict) and not vuota(y) and y.get('esito') != 'ILLEGGIBILE'

    @classmethod
    def tenute(cls, prima: Mapping[str, Any] | None, domanda: str) -> tuple[list[int], int]:
        """``(indices of the valid readings of prima made with this very prompt, valid readings made with another)``.

        The prompt is recognised by the SHA-256 that the call record carries since 02/10/2026
        (``chiamate[k].istruzioni_sha256``); a reading without it cannot be checked and is not kept.
        """
        if not prima:
            return [], 0
        h = hashlib.sha256(domanda.encode('utf-8')).hexdigest()
        letture, chiamate = prima.get('letture') or [], prima.get('chiamate') or []
        ok, altre = [], 0
        for k, y in enumerate(letture):
            if not cls.valida(y):
                continue
            c = chiamate[k] if k < len(chiamate) else None
            if isinstance(c, dict) and c.get('istruzioni_sha256') == h:
                ok.append(k)
            else:
                altre += 1
        return ok, altre

    def da_fare(self, righe: list[dict[str, Any]], esistenti: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
        """Rows not read yet; with ``solo_vuote``, rows already read with at least one empty reading; with
        ``aggiungi_letture``, rows with fewer than ``letture`` valid readings of the same prompt."""
        if self.aggiungi_letture:
            self._tenute = {r['id']: self.tenute(esistenti.get(r['id']), self.prompt(r)) for r in righe}
            fare = [r for r in righe if len(self._tenute[r['id']][0]) < self.letture]
            self.stampa(
                f'aggiunte: {sum(1 for r in fare if self._tenute[r["id"]][0])} righe da completare, '
                f'{sum(1 for r in fare if not self._tenute[r["id"]][0])} da capo, '
                f"{sum(self._tenute[r['id']][1] for r in fare)} letture scartate perche' la domanda e' cambiata"
            )
            return fare
        if self.solo_vuote:
            return [
                r
                for r in righe
                if r['id'] in esistenti and any(vuota(y) for y in esistenti[r['id']].get('letture') or [])
            ]
        return [r for r in righe if r['id'] not in esistenti]

    def taglia(self, ragionamento: str) -> str:
        """The reasoning as saved: whole, or cut as the harness readers did."""
        return ragionamento[: self.TAGLIO_RAGIONAMENTO] if self.compat else ragionamento

    def chiama(self, testo: str) -> dict[str, Any]:
        return self.cliente.chiama(testo)

    def nuova(self, x: Mapping[str, Any]) -> list[Any]:
        """``[reading, reasoning, call]`` of a fresh reading (the type reader adds the tokens)."""
        return [estrai_tollerante(x['testo']), self.taglia(x['ragionamento']), x['chiamata']]

    def leggi_riga(self, r: Mapping[str, Any], esistenti: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
        """The ``k`` readings of one row (kept or fresh) and its output line."""
        testo = self.prompt(r)
        if self.aggiungi_letture:
            vecchia = esistenti.get(r['id']) or {}
            tenute_k, scartate = self._tenute[r['id']]
            parti = [self.parte_tenuta(vecchia, k) for k in tenute_k]
            parti += [self.nuova(self.chiama(testo)) for _ in range(self.letture - len(tenute_k))]
            aggiunte = {
                'tenute': len(tenute_k),
                'nuove': self.letture - len(tenute_k),
                'scartate_domanda_cambiata': scartate,
                'data': self.oggi(),
            }
            return self.record(r, parti, False, aggiunte)
        prima = esistenti.get(r['id']) if self.solo_vuote else None
        parti: list[list[Any]] = []
        for k in range(self.letture):
            tenuta = self.lettura_tenuta(prima, k) if prima else None
            if tenuta is not None:
                parti.append(list(tenuta))
                continue
            parti.append(self.nuova(self.chiama(testo)))
        return self.record(r, parti, bool(prima))

    def esegui(self) -> int:
        """Read every row to do and append the lines; returns the number of rows written."""
        self.prepara()
        self.cliente.extra_body = self.extra_body()
        righe = self.righe()
        esistenti = self.esistenti()
        da_fare = self.da_fare(righe, esistenti)
        self.stampa(self.messaggio_inizio(righe, set(esistenti), da_fare))
        blocco = threading.Lock()
        t0 = self.orologio()
        n = 0
        with cf.ThreadPoolExecutor(self.paralleli) as ex, open(self.file_uscita, 'a', encoding='utf-8') as f:
            for n, e in enumerate(ex.map(lambda r: self.leggi_riga(r, esistenti), da_fare), 1):
                with blocco:
                    f.write(json.dumps(e, ensure_ascii=False) + '\n')
                    f.flush()
                if n % self.OGNI == 0:
                    self.stampa(f'  {n}/{len(da_fare)} [{self.orologio() - t0:.0f}s]')
        self.stampa(f'fatto in {self.orologio() - t0:.0f}s')
        return n

    @staticmethod
    def oggi() -> str:
        return datetime.date.today().isoformat()


def _primo(lista: Any, k: int, predefinito: Any) -> Any:
    """``(lista or [])[k:k + 1] or [predefinito]`` -> its only element (the live idiom)."""
    return ((lista or [])[k : k + 1] or [predefinito])[0]


class LettoreTipo(Lettore):
    """The type of each lexical citation (L02/L03), two readings per row by default.

    Args:
        gruppo: ``validate``, ``non_validate`` or ``tutte`` (``--gruppo``).
        solo_id: a file with the ids to read, one per line (``--solo-id``).
        max_righe: read at most this many rows (``--max-righe``; 0 = all).
        sforzo: the reasoning effort (``--sforzo``).
        kwargs_modello: JSON for ``chat_template_kwargs`` of another model (``--kwargs-modello``).
        Other arguments: see :class:`Lettore`.
    """

    TAGLIO_RAGIONAMENTO = 4000
    OGNI = 20

    def __init__(
        self,
        config: Config,
        caso: str,
        cliente: ClienteDeepSeek,
        gruppo: str = 'validate',
        solo_id: str = '',
        max_righe: int = 0,
        sforzo: str = 'low',
        kwargs_modello: str = '',
        **kw: Any,
    ) -> None:
        super().__init__(config, caso, cliente, **kw)
        self.gruppo = gruppo
        self.solo_id = solo_id
        self.max_righe = max_righe
        self.sforzo = sforzo
        self.kwargs_modello = kwargs_modello
        self._modulo = ''
        self._fascicolo = ''
        self._cb: tuple[dict[str, Any], str, str, str] | None = None

    @property
    def file_righe(self) -> Path:
        return self.config.training / f'lessicali_{self.caso}_righe.jsonl'

    @property
    def file_uscita(self) -> Path:
        return self.config.training / f'lessicali_{self.caso}_deepseek{self.suf}.jsonl'

    def prepara(self) -> None:
        # the dossier of the case file without series (the live reader does not follow TRACE_SONDE here)
        self._fascicolo = (self.config.cited_cases / f'{self.caso}-fascicolo.md').read_text(encoding='utf-8')
        with open(self.config.radice / 'codebook' / 'citazioni.yaml', encoding='utf-8') as f:
            cb = yaml.safe_load(f)
        self._cb = (cb, *blocchi_codebook(cb))
        conf = None
        if self.caso != 'urgenda':
            with open(self.config.cited_cases / f'{self.caso}.yaml', encoding='utf-8') as f:
                conf = yaml.safe_load(f)
        self._modulo = modulo_tipo(self.caso, conf)

    def righe(self) -> list[dict[str, Any]]:
        righe = [r for r in super().righe() if self.gruppo in ('tutte', r['gruppo'])]
        if self.solo_id:
            tenere = set(Path(self.solo_id).read_text(encoding='utf-8').split())
            righe = [r for r in righe if r['id'] in tenere]
        if self.max_righe:
            righe = righe[: self.max_righe]
        return righe

    def prompt(self, r: Mapping[str, Any]) -> str:
        assert self._cb is not None, 'prepara() first'
        cb, tipi, chi, limiti = self._cb
        return self._modulo.format(
            fascicolo=self._fascicolo,
            versione=cb['versione'],
            tipi=tipi,
            chi=chi,
            limiti=limiti,
            case_name=r.get('case_name') or r['case_id'],
            tipo_atto=r.get('tipo_atto') or 'atto',
            data=r.get('data') or 's.d.',
            document_id=r['document_id'],
            forma=r.get('forma') or NOMI_BREVI.get(self.caso, self.caso),
            inizio=INIZIO,
            fine=FINE,
            contesto=r['contesto'],
        )

    def extra_body(self) -> dict[str, Any]:
        if self.kwargs_modello:
            return {'chat_template_kwargs': json.loads(self.kwargs_modello)}
        return {'chat_template_kwargs': {'thinking': True, 'reasoning_effort': self.sforzo}}

    def messaggio_inizio(self, righe: list[dict[str, Any]], fatte: set[str], da_fare: list[dict[str, Any]]) -> str:
        return f"{self.gruppo}: {len(righe)} righe, {len(fatte)} gia' fatte in tutto, {len(da_fare)} da fare"

    def nuova(self, x: Mapping[str, Any]) -> list[Any]:
        # NOTE(bug): in today's live reader (02/10/2026 evening) a comment swallowed
        # `tok.append(x['token']); chiamate.append(x['chiamata'])`, so fresh readings lose their tokens and call
        # record. Not reproduced: the package writes them (see the report).
        return [estrai_tollerante(x['testo']), self.taglia(x['ragionamento']), x['token'], x['chiamata']]

    def lettura_tenuta(self, prima: Mapping[str, Any], k: int) -> tuple[Any, ...] | None:
        vecchie = prima.get('letture') or []
        if k < len(vecchie) and not vuota(vecchie[k]):
            return (
                vecchie[k],
                _primo(prima.get('ragionamenti'), k, ''),
                _primo(prima.get('token'), k, 0),
                _primo(prima.get('chiamate'), k, {'tenuta': True}),
            )
        return None

    @staticmethod
    def accordi(x: dict[str, Any]) -> dict[str, Any]:
        """Agreement of the readings on type, speaker and referent (tools/classifica_lessicali.py ``accordi``)."""
        g = x['letture']
        for k, c in (('tipo', 'tipo_citazione'), ('chi_parla', 'chi_parla'), ('riferimento', 'riferimento')):
            v = [y.get(c) for y in g]
            x[f'accordo_{k}'] = len(g) > 1 and len(set(v)) == 1 and v[0] is not None
        return x

    def parte_tenuta(self, prima: Mapping[str, Any], k: int) -> list[Any]:
        return [
            prima['letture'][k],
            _primo(prima.get('ragionamenti'), k, ''),
            _primo(prima.get('token'), k, 0),
            prima['chiamate'][k],
        ]

    def record(
        self, r: Mapping[str, Any], parti: list[list[Any]], rifatta: bool, aggiunte: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        assert self._cb is not None
        out = {
            'id': r['id'],
            'modello': MODELLO_TIPO,
            'data': self.oggi(),
            'gruppo': r['gruppo'],
            'codebook': self._cb[0].get('versione'),
            'letture': [p[0] for p in parti],
            'ragionamenti': [p[1] for p in parti],
            'token': [p[2] for p in parti],
            'chiamate': [p[3] for p in parti],
        }
        if rifatta:
            out['rifatte_vuote'] = self.oggi()
        if aggiunte is not None:
            out['aggiunte'] = aggiunte
        return self.accordi(out)


class LettorePagineAttorno(Lettore):
    """The uptake with the surrounding pages (L05): principles, pages that follow, the supported sentence.

    Args:
        uscita_suffisso: an extra suffix of the output file (``--uscita-suffisso``).
        Other arguments: see :class:`Lettore`.
    """

    MODULO = MODULO_PAGINE_ATTORNO

    def __init__(
        self, config: Config, caso: str, cliente: ClienteDeepSeek, uscita_suffisso: str = '', **kw: Any
    ) -> None:
        super().__init__(config, caso, cliente, **kw)
        self.uscita_suffisso = uscita_suffisso
        self._principi = ''
        self._nome_caso = ''
        self._fascicolo = ''

    @property
    def file_righe(self) -> Path:
        return self.config.principi / f'{self.caso}_ripresa_righe{self.suf}.jsonl'

    @property
    def file_uscita(self) -> Path:
        return self.config.principi / f'{self.caso}_ripresa_deepseek{self.suf}{self.uscita_suffisso}.jsonl'

    def prepara(self) -> None:
        with open(self.config.file_caso(self.caso), encoding='utf-8') as f:
            conf = yaml.safe_load(f)
        self._principi = '\n'.join(
            f'- {s["id"]}: {" ".join(s["titolo"].split())}. {" ".join(s["testo"].split())}'
            for s in conf['semantic_queries']
        )
        self._nome_caso = conf.get('nome') or self.caso
        # the dossier of the case (PI, 28/09/2026), only with a label, as live
        self._fascicolo = ''
        if self.etichetta:
            testo_f = self.config.file_fascicolo(self.caso).read_text(encoding='utf-8')
            self._fascicolo = (
                '\nQui sotto il FASCICOLO del caso, scritto per il gruppo di ricerca: serve a sapere che cosa ha '
                'deciso e con quali paragrafi. Le domande sono quelle in fondo.\n\n'
                + testo_f
                + '\n\n========== FINE DEL FASCICOLO ==========\n'
            )

    def prompt(self, r: Mapping[str, Any]) -> str:
        aiuto = ''
        if r['paragrafi']:
            aiuto = (
                f'La citazione indica i paragrafi {", ".join(r["paragrafi"])}; secondo la mappa dei paragrafi '
                f'reggono i principi: {", ".join(r["principi_paragrafi"]) or "nessuno (fatti o procedura)"}.\n'
            )
        vic = '\n\n'.join(f'--- PAGINA {v["pagina"]} ---\n{v["testo"]}' for v in r['vicine']) or (
            '(nessuna pagina vicina proposta)'
        )
        return self.MODULO.format(
            fascicolo=self._fascicolo,
            nome_caso=self._nome_caso,
            principi=self._principi,
            case_name=r.get('case_name') or '',
            tipo_atto=r.get('tipo_atto') or 'atto',
            data=(r.get('data') or 's.d.')[:10],
            document_id=r['document_id'],
            forma=r.get('forma') or self._nome_caso,
            contesto=r['contesto'],
            aiuto_paragrafi=aiuto,
            vicine=vic,
        )

    def extra_body(self) -> dict[str, Any]:
        return {'chat_template_kwargs': {'thinking': True, 'reasoning_effort': 'low'}}

    def messaggio_inizio(self, righe: list[dict[str, Any]], fatte: set[str], da_fare: list[dict[str, Any]]) -> str:
        return f'{len(righe)} righe, {len(fatte)} fatte, {len(da_fare)} da fare'

    def nuova(self, x: Mapping[str, Any]) -> list[Any]:
        # NOTE(bug): in today's live reader a comment swallowed `chiamate.append(x['chiamata'])`, so fresh readings
        # lose their call record (and the lists of a row go out of step). Not reproduced: see the report.
        return [estrai_tollerante(x['testo']), self.taglia(x['ragionamento']), x['chiamata']]

    def lettura_tenuta(self, prima: Mapping[str, Any], k: int) -> tuple[Any, ...] | None:
        vecchie = prima.get('letture') or []
        vecchia = (vecchie or [None] * self.letture)[k] if k < len(vecchie) else None
        if vecchia is not None and not vuota(vecchia):
            return (
                vecchia,
                _primo(prima.get('ragionamenti') or [''] * self.letture, k, ''),
                _primo(prima.get('chiamate') or [None] * self.letture, k, None) or {'tenuta': True},
            )
        return None

    def parte_tenuta(self, prima: Mapping[str, Any], k: int) -> list[Any]:
        return [prima['letture'][k], _primo(prima.get('ragionamenti'), k, ''), prima['chiamate'][k]]

    def record(
        self, r: Mapping[str, Any], parti: list[list[Any]], rifatta: bool, aggiunte: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        out = {
            'id': r['id'],
            'data': self.oggi(),
            'letture': [p[0] for p in parti],
            'ragionamenti': [p[1] for p in parti],
            'chiamate': [p[2] for p in parti],
        }
        if rifatta:
            out['rifatte_vuote'] = self.oggi()
        if aggiunte is not None:
            out['aggiunte'] = aggiunte
        return out


class LettorePrincipi(LettorePagineAttorno):
    """The principles as read on 27/09/2026 (L04): the L05 reader with the L04 instructions.

    The default label is ``l04nuove`` (``tools/leggi_l04.py``); the dossier is read when there is a label, as live,
    but the L04 instructions have no place for it.
    """

    MODULO = MODULO_PRINCIPI

    def __init__(
        self, config: Config, caso: str, cliente: ClienteDeepSeek, etichetta: str = 'l04nuove', **kw: Any
    ) -> None:
        super().__init__(config, caso, cliente, etichetta=etichetta, **kw)


LETTORI: Mapping[str, type[Lettore]] = {
    'tipo': LettoreTipo,
    'principi': LettorePrincipi,
    'pagine-attorno': LettorePagineAttorno,
}
"""The readers by CLI name."""


def ordine_conservato(righe: Iterable[Mapping[str, Any]], uscita: Iterable[Mapping[str, Any]]) -> bool:
    """True if the output lines follow the order of the input rows (a check used by the tests)."""
    pos = {r['id']: i for i, r in enumerate(righe)}
    ids = [x['id'] for x in uscita]
    return [pos[i] for i in ids] == sorted(pos[i] for i in ids)
