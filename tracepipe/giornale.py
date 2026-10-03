"""The operations journal (``giornale delle operazioni``) as a class, with the JSONL schema of ``tools/giornale.py``.

Two lines per run in ``<root>/giornale/<host>/<YYYY-MM>.jsonl``, append only: ``inizio`` when the run starts, ``fine``
when it ends (a run that dies without the second line shows). The ``fine`` line carries, as live:

- ``file``: the files of the project opened with the built-in ``open`` or ``gzip.open`` while the journal is active,
  read or written, with size, lines (``.jsonl``/``.csv``/``.txt``/``.tsv``) and SHA-256 (up to 300 MB); more than 50
  files in one folder become one summary in ``cartelle``;
- ``firestore``: per collection, how many ``set``/``update``/``delete`` and which fields (from :mod:`tracepipe.banca`);
- ``deepseek``: calls, successful ones, attempts, finish reasons, caps, errors (from
  :class:`tracepipe.deepseek.ClienteDeepSeek`);
- ``conti`` (counts the tool adds), ``errori``, ``eccezione`` (the traceback that stopped the run) and ``esito``.

Use it as a context manager around a run::

    with Giornale(radice, 'tracepipe carica ripresa', argv) as g:
        banca = BancaDatiFirestore(osservatore=g.scrittura_firestore)
        ...

NOTE: like the live journal, files are seen by intercepting the built-in ``open`` and ``gzip.open``: what a run reads
through ``pathlib`` (``Path.read_text``, ``Path.open``) is not listed. The package keeps the same reads on the same
side of that line, so its journal lists the same files as the live one. Any error of the journal itself is ignored:
the journal never stops a run.
"""

from __future__ import annotations

import builtins
import contextlib
import datetime
import getpass
import gzip
import hashlib
import json
import os
import platform
import socket
import subprocess
import threading
import traceback
import uuid
from collections.abc import Iterable, Sequence
from pathlib import Path
from types import TracebackType
from typing import Any

COLLEZIONE = 'trace_giornale'
LIMITE_SHA = 300_000_000
LIMITE_RIGHE = 2_000_000_000
MOLTI_FILE = 50
_OPEN_VERO = builtins.open
_GZIP_VERO = gzip.open


def _ora() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


def macchina() -> str:
    """The short host name (``giornale/<host>/``)."""
    return socket.gethostname().split('.')[0] or 'sconosciuto'


def sha256_file(p: Path, limite: int = LIMITE_SHA) -> str | None:
    """SHA-256 of a file, ``None`` above ``limite`` bytes or on error."""
    try:
        if p.stat().st_size > limite:
            return None
        h = hashlib.sha256()
        with _OPEN_VERO(p, 'rb') as f:
            for b in iter(lambda: f.read(1 << 20), b''):
                h.update(b)
        return h.hexdigest()
    except Exception:
        return None


def righe_file(p: Path) -> int | None:
    """Lines of a text table (``.jsonl``, ``.csv``, ``.txt``, ``.tsv``), else ``None``."""
    try:
        if p.suffix not in ('.jsonl', '.csv', '.txt', '.tsv') or p.stat().st_size > LIMITE_RIGHE:
            return None
        with _OPEN_VERO(p, 'rb') as f:
            return sum(1 for _ in f)
    except Exception:
        return None


def impronta_codice(file: Iterable[Path]) -> str | None:
    """One SHA-256 over the source files of the package (``codice_sha256`` of the journal)."""
    try:
        h = hashlib.sha256()
        for p in sorted(file):
            h.update(p.name.encode('utf-8'))
            h.update(p.read_bytes())
        return h.hexdigest()
    except Exception:
        return None


def commit_di(cartella: Path, sotto: str) -> str | None:
    """``git rev-parse HEAD`` of the repository of ``cartella``, ``+modifiche`` if ``sotto`` has local changes."""
    try:
        r = subprocess.run(['git', '-C', str(cartella), 'rev-parse', 'HEAD'], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            sporco = subprocess.run(
                ['git', '-C', str(cartella), 'status', '--porcelain', '--', sotto],
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
            return r.stdout.strip() + ('+modifiche' if sporco else '')
    except Exception:
        pass
    return None


class Giornale:
    """The journal of one run.

    Args:
        radice: the project root; files are listed relative to it, and the journal lives in ``<radice>/giornale``.
        strumento: what runs (``tracepipe carica ripresa``).
        argomenti: its arguments.
        intercetta: intercept the built-in ``open`` and ``gzip.open`` to list files (the live behaviour).
        codice: the source files whose hash goes in ``codice_sha256`` (default: the package).
    """

    def __init__(
        self,
        radice: Path | str,
        strumento: str,
        argomenti: Sequence[str] = (),
        intercetta: bool = True,
        codice: Iterable[Path] | None = None,
    ) -> None:
        self.radice = Path(radice).resolve()
        self.cartella = self.radice / 'giornale'
        self.strumento = strumento
        self.argomenti = list(argomenti)
        self.intercetta = intercetta
        self._codice = list(codice) if codice is not None else sorted(Path(__file__).resolve().parent.glob('*.py'))
        self._blocco = threading.Lock()
        self.voce: dict[str, Any] | None = None
        self.file: dict[str, set[str]] = {}
        self.firestore: dict[str, dict[str, Any]] = {}
        self.deepseek: dict[str, Any] = {}
        self.conti: dict[str, int] = {}
        self.errori: list[str] = []
        self.eccezione: str | None = None
        self._open_prima: Any = None
        self._gzip_prima: Any = None

    # writing a line
    def _file_del_mese(self) -> Path:
        return self.cartella / macchina() / f'{datetime.date.today():%Y-%m}.jsonl'

    def _scrivi_riga(self, riga: dict[str, Any]) -> None:
        try:
            f = self._file_del_mese()
            f.parent.mkdir(parents=True, exist_ok=True)
            with _OPEN_VERO(f, 'a', encoding='utf-8') as h:
                h.write(json.dumps(riga, ensure_ascii=False, default=str) + '\n')
        except Exception:
            pass

    # files
    def segna(self, percorso: Any, modo: str = 'r') -> None:
        """Record that a file was opened (``modo`` with ``w``, ``a``, ``x`` or ``+`` means written)."""
        try:
            p = Path(os.fspath(percorso)).expanduser()
            p = (Path.cwd() / p if not p.is_absolute() else p).resolve()
            if self.radice not in p.parents or self.cartella in p.parents or '__pycache__' in p.parts:
                return
            m = str(modo or 'r')
            tipo = 'scritto' if any(c in m for c in 'wax+') else 'letto'
            with self._blocco:
                self.file.setdefault(str(p.relative_to(self.radice)), set()).add(tipo)
        except Exception:
            pass

    def _open(self, file: Any, mode: str = 'r', *a: Any, **k: Any) -> Any:
        if isinstance(file, (str, bytes, os.PathLike)):
            self.segna(file, mode)
        return _OPEN_VERO(file, mode, *a, **k)

    def _gzopen(self, filename: Any, mode: str = 'rb', *a: Any, **k: Any) -> Any:
        if isinstance(filename, (str, bytes, os.PathLike)):
            self.segna(filename, mode)
        return _GZIP_VERO(filename, mode, *a, **k)

    # Firestore, DeepSeek, counts, errors
    def scrittura_firestore(self, collezione: str, op: str, campi: Iterable[str]) -> None:
        """Count one write (the observer of :class:`tracepipe.banca.BancaDati`)."""
        try:
            with self._blocco:
                e = self.firestore.setdefault(collezione or '?', {'set': 0, 'update': 0, 'delete': 0, 'campi': set()})
                e[op] = e.get(op, 0) + 1
                e['campi'].update(campi or [])
        except Exception:
            pass

    def chiamata_deepseek(self, info: dict[str, Any]) -> None:
        """Add one DeepSeek call (the observer of :class:`tracepipe.deepseek.ClienteDeepSeek`)."""
        try:
            with self._blocco:
                d = self.deepseek
                d['chiamate'] = d.get('chiamate', 0) + 1
                d['riuscite'] = d.get('riuscite', 0) + (1 if info.get('riuscita') else 0)
                d['tentativi'] = d.get('tentativi', 0) + int(info.get('tentativi') or 0)
                fine = str(info.get('fine'))
                d.setdefault('fine', {})
                d['fine'][fine] = d['fine'].get(fine, 0) + 1
                tetto = str(info.get('tetto'))
                d.setdefault('tetto', {})
                d['tetto'][tetto] = d['tetto'].get(tetto, 0) + 1
                errori = [s.get('errore') for s in info.get('storia') or [] if s.get('errore')]
                if errori:
                    d.setdefault('errori', [])
                    if len(d['errori']) < 50:
                        d['errori'].extend(errori[:5])
        except Exception:
            pass

    def conta(self, chiave: str, n: int = 1) -> None:
        with self._blocco:
            self.conti[chiave] = self.conti.get(chiave, 0) + n

    def errore(self, testo: Any) -> None:
        with self._blocco:
            if len(self.errori) < 200:
                self.errori.append(str(testo)[:1000])

    # start and end
    def avvia(self) -> Giornale:
        """Write the ``inizio`` line and start listening."""
        if self.voce is not None:
            return self
        self.voce = {
            'id': uuid.uuid4().hex,
            'strumento': self.strumento,
            'argomenti': self.argomenti,
            'cartella': os.getcwd(),
            'macchina': macchina(),
            'utente': getpass.getuser(),
            'python': platform.python_version(),
            'serie_sonde': os.environ.get('TRACE_SONDE') or None,
            'codice_sha256': impronta_codice(self._codice),
            'commit': commit_di(Path(__file__).resolve().parent, 'tracepipe'),
            'inizio': _ora(),
        }
        self._scrivi_riga({'tipo': 'inizio', **self.voce})
        if self.intercetta:
            self._open_prima, self._gzip_prima = builtins.open, gzip.open
            builtins.open = self._open
            gzip.open = self._gzopen
        return self

    def _smetti(self) -> None:
        if self._open_prima is not None:
            builtins.open, gzip.open = self._open_prima, self._gzip_prima
            self._open_prima = self._gzip_prima = None

    def voce_di_fine(self) -> dict[str, Any]:
        """The ``fine`` line (also used by the tests)."""
        voce = dict(self.voce or {})
        fine = datetime.datetime.now().astimezone()
        file: list[dict[str, Any]] = []
        cartelle: list[dict[str, Any]] = []
        per_cartella: dict[str, list[tuple[str, set[str]]]] = {}
        for rel, tipi in self.file.items():
            per_cartella.setdefault(str(Path(rel).parent), []).append((rel, tipi))
        singoli: dict[str, set[str]] = {}
        for cart, voci in per_cartella.items():
            if len(voci) > MOLTI_FILE:
                usi = sorted({t for _, ti in voci for t in ti})
                byte = sum((self.radice / r).stat().st_size for r, _ in voci if (self.radice / r).exists())
                cartelle.append({'cartella': cart, 'file': len(voci), 'byte': byte, 'uso': usi})
            else:
                singoli.update(dict(voci))
        for rel, tipi in sorted(singoli.items()):
            p = self.radice / rel
            e: dict[str, Any] = {'percorso': rel, 'uso': sorted(tipi)}
            if p.exists():
                e['byte'] = p.stat().st_size
                e['righe'] = righe_file(p)
                if 'scritto' in tipi or e['byte'] < 50_000_000:
                    e['sha256'] = sha256_file(p)
            else:
                e['manca_alla_fine'] = True
            file.append(e)
        fs = {
            c: {**{k: v for k, v in e.items() if k != 'campi'}, 'campi': sorted(e['campi'])}
            for c, e in self.firestore.items()
        }
        inizio = voce.get('inizio')
        durata = round((fine - datetime.datetime.fromisoformat(inizio)).total_seconds(), 1) if inizio else None
        voce.update(
            {
                'tipo': 'fine',
                'fine': fine.isoformat(timespec='seconds'),
                'durata_s': durata,
                'file': file,
                'cartelle': cartelle or None,
                'firestore': fs,
                'deepseek': self.deepseek or None,
                'conti': self.conti or None,
                'errori': self.errori or None,
                'eccezione': self.eccezione,
                'esito': 'errore' if self.eccezione else 'ok',
            }
        )
        return voce

    def chiudi(self) -> None:
        """Stop listening and write the ``fine`` line."""
        try:
            self._smetti()
            if self.voce is not None:
                self._scrivi_riga(self.voce_di_fine())
        except Exception:
            pass

    def __enter__(self) -> Giornale:
        return self.avvia()

    def __exit__(
        self, tipo: type[BaseException] | None, valore: BaseException | None, tb: TracebackType | None
    ) -> None:
        # as the live sys.excepthook: an exception that stops the run is written; SystemExit is a normal exit
        if tipo is not None and not issubclass(tipo, SystemExit):
            self.eccezione = ''.join(traceback.format_exception(tipo, valore, tb))[-4000:]
        self.chiudi()

    # sending to Firestore (``giornale.py invia``)
    def voci_da_inviare(self) -> list[dict[str, Any]]:
        """End, event, rebuilt and note lines not yet sent (``giornale/inviate.txt``)."""
        fatto = self.cartella / 'inviate.txt'
        gia = set(fatto.read_text(encoding='utf-8').split()) if fatto.exists() else set()
        voci = []
        for f in sorted(self.cartella.rglob('*.jsonl')):
            for riga in f.read_text(encoding='utf-8').splitlines():
                try:
                    x = json.loads(riga)
                except ValueError:
                    continue
                if x.get('tipo') in ('fine', 'evento', 'ricostruita', 'nota') and x.get('id') not in gia:
                    voci.append(x)
        return voci

    def invia(self, banca: Any, lotto: int = 400) -> int:
        """Send the pending lines to ``trace_giornale`` through a :class:`tracepipe.banca.BancaDati`."""
        if macchina().startswith(('wn-', 'ettore', 'recas')) or os.environ.get('GIORNALE_SENZA_FIRESTORE'):
            return 0
        from .banca import Scrittura

        voci = self.voci_da_inviare()
        n = 0
        for i in range(0, len(voci), lotto):
            pezzo = voci[i : i + lotto]
            try:
                banca.scrivi_a_lotti(
                    [
                        Scrittura('set', COLLEZIONE, v['id'], json.loads(json.dumps(v, default=str)), True)
                        for v in pezzo
                    ],
                    dimensione=lotto,
                )
            except Exception:
                continue
            with _OPEN_VERO(self.cartella / 'inviate.txt', 'a', encoding='utf-8') as g:
                g.write('\n'.join(v['id'] for v in pezzo) + '\n')
            n += len(pezzo)
        return n


@contextlib.contextmanager
def nessun_giornale() -> Any:
    """A stand-in when no journal is wanted (tests, library use)."""
    yield None
