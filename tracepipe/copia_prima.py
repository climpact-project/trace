"""The full copy kept before every write of a clean-up step (``copia_prima``: copy before).

On 3 October 2026 R11 wrote over the proposals of R05 and only a partial copy of the old ones was left: a replaced
proposal could not be put back as it was. From 4 October every step that writes fields on rows that already exist
saves, BEFORE the first batch, the ``proposto_*`` fields of each row as they are today, the whole ``provenienza``
and every other field the write is about to touch (``assenti`` lists the ones the row did not have). If the copy is
not written or does not read back equal, the step stops without writing anything (:class:`CopiaNonRiuscitaError`).

The copy lives in ``<root>/training/<cycle>/prima_<step>_<case>_<date>.json.gz``; ``TRACE_COPIE_PRIMA_CARTELLA``
replaces the folder, and ``TRACE_CICLO`` (set by the chains) the cycle. Under pytest, without either, it goes to a
temporary folder, so the tests never touch ``training/``. It is ``tools/copia_prima.py`` as a class.

To put a row back as it was: read the file (gzip and json), ``righe[<id>]['prima']`` are the fields of then;
``righe[<id>]['assenti']`` did not exist then and are removed with ``DELETE_FIELD``.
"""

from __future__ import annotations

import datetime
import gzip
import json
import os
import sys
import tempfile
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

CAMPI_SEMPRE: tuple[str, ...] = (
    'provenienza',
    'proposta_provvisoria',
    'proposto_rete',
    'codice',
    'caso_citato',
    'esito',
    'esecuzione_id',
)
"""Fields kept in every copy, besides the ``proposto_*`` ones."""


class CopiaNonRiuscitaError(RuntimeError):
    """The copy before the write was not written or did not read back equal: nothing must be written."""


class CopiaPrima:
    """Writes and reads the full copy of the rows a step is about to change.

    Args:
        radice: the project root (the copy goes under ``training/``).
        cartella: the folder of the copy; overrides everything else.
        orologio: the clock that names the file.
        stampa: where the line about the copy goes (default: standard error, as live).
    """

    def __init__(
        self,
        radice: Path | str,
        cartella: Path | str | None = None,
        orologio: Callable[[], datetime.datetime] = datetime.datetime.now,
        stampa: Callable[[str], None] | None = None,
    ) -> None:
        self.radice = Path(radice)
        self.cartella = Path(cartella) if cartella else None
        self.orologio = orologio
        self.stampa = stampa or (lambda t: print(t, file=sys.stderr))

    @staticmethod
    def campi_di(riga: Mapping[str, Any] | None, scritti: Iterable[str] = ()) -> tuple[dict[str, Any], list[str]]:
        """``(fields to keep, fields the write touches that the row does not have)``.

        ``provenienza.tipo`` touches ``provenienza``: the dotted path counts as its first segment.
        """
        riga = riga or {}
        tenere = {k: v for k, v in riga.items() if k.startswith('proposto_') or k in CAMPI_SEMPRE}
        assenti: list[str] = []
        for k in scritti:
            primo = str(k).split('.')[0]
            if primo in riga:
                tenere[primo] = riga[primo]
            elif primo not in assenti:
                assenti.append(primo)
        return tenere, sorted(assenti)

    def percorso(self, passo: str, caso: str, ciclo: str | None, quando: datetime.datetime) -> Path:
        """The first free file name of the copy."""
        cartella = self.cartella
        if cartella is None and os.environ.get('TRACE_COPIE_PRIMA_CARTELLA'):
            cartella = Path(os.environ['TRACE_COPIE_PRIMA_CARTELLA'])
        if cartella is None:
            if os.environ.get('PYTEST_CURRENT_TEST'):
                cartella = Path(tempfile.gettempdir()) / 'trace_copie_prima_prove'
            else:
                cartella = self.radice / 'training' / (os.environ.get('TRACE_CICLO') or ciclo or 'copie_prima')
        base = f'prima_{passo}_{caso}_{quando.strftime("%Y-%m-%d_%H%M%S")}'
        p = cartella / f'{base}.json.gz'
        n = 1
        while p.exists():
            n += 1
            p = cartella / f'{base}_{n}.json.gz'
        return p

    def salva(
        self,
        passo: str,
        caso: str,
        prima: Mapping[str, Mapping[str, Any]],
        scritture: Mapping[str, Mapping[str, Any] | None],
        ciclo: str | None = None,
    ) -> Path:
        """Write the copy, read it back, return its path.

        Args:
            passo: the step that writes (``unisci_c03``).
            caso: the case, or ``'tutti'``.
            prima: ``{id: row as it is today}``.
            scritture: ``{id: fields about to be written}``.
            ciclo: the folder under ``training/``.

        Raises:
            CopiaNonRiuscitaError: the copy was not written or does not read back equal; nothing was written.
        """
        quando = self.orologio()
        p = self.percorso(passo, caso, ciclo, quando)
        righe = {}
        for rid, campi in scritture.items():
            tenere, assenti = self.campi_di(prima.get(rid), campi or {})
            righe[rid] = {'prima': tenere, 'assenti': assenti, 'riga_letta': rid in prima}
        documento = {
            'caricatore': passo,
            'caso': caso,
            'quando': quando.isoformat(timespec='seconds'),
            'comando': sys.argv,
            'n_righe': len(righe),
            'campi_scritti': sorted({str(k) for c in scritture.values() for k in (c or {})}),
            'righe': righe,
        }
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_name(p.name + '.tmp')
            with gzip.open(tmp, 'wt', encoding='utf-8') as f:
                json.dump(documento, f, ensure_ascii=False, default=str)
            riletto = self.leggi(tmp)
            if riletto.get('n_righe') != len(righe) or set(riletto.get('righe') or {}) != set(righe):
                raise ValueError('copia riletta diversa')
            os.replace(tmp, p)
        except Exception as e:  # no copy, no write
            raise CopiaNonRiuscitaError(f'copia prima non riuscita ({e}): niente scritto') from e
        self.stampa(f'copia prima della scrittura: {p} ({len(righe)} righe)')
        return p

    @staticmethod
    def leggi(percorso: Path | str) -> dict[str, Any]:
        """The content of a copy."""
        with gzip.open(percorso, 'rt', encoding='utf-8') as f:
            return json.load(f)
