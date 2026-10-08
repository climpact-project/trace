"""The platform database seen by the pipeline (``banca dati``): :class:`BancaDati` and its two implementations.

The live scripts talk to Firestore directly (``firestore.Client(project='climpact-drp')``). The package goes through a
small interface with only what the scripts use:

- :meth:`BancaDati.righe`: the documents of a collection, optionally filtered by equality, in id order (Firestore
  streams by ``__name__``);
- :meth:`BancaDati.lotto`: a write batch (``set``, ``update``, ``create``, ``delete``, then ``commit``);
- :meth:`BancaDati.imposta`: a single document ``set``;
- :meth:`BancaDati.scrivi_a_lotti`: the live loop ``for i in range(0, len(w), 400): b = db.batch() ...``.

:class:`BancaDatiFirestore` is the real one (it imports ``google.cloud.firestore`` only when used, so on the harness
the fake of ``prove/finti`` answers). :class:`BancaDatiMemoria` keeps the documents in memory and records every write
in the same form as the harness fake (``op``, ``collezione``, ``doc_id``, ``dati``, ``via``, ``esiste``, ``merge``),
never applying it: each run sees the same frozen rows, as on the harness.

Every write is also reported to an optional observer ``(collection, op, fields)``: the journal counts writes there.
"""

from __future__ import annotations

import contextlib
import copy
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

PROGETTO = 'climpact-drp'
"""The Firebase project of the platform."""
LOTTO = 400
"""Writes per batch, as every live loader (Firestore allows 500)."""

Osservatore = Callable[[str, str, list[str]], None]
"""Called with (collection, operation, field names) for every write; the journal counts them."""
Filtro = tuple[str, str, Any]
"""(field, operator, value); only ``==`` is used by the pipeline."""


class OraDelServer:
    """Stand-in for ``firestore.SERVER_TIMESTAMP`` in the memory database; written as ``__SERVER_TIMESTAMP__``."""

    def __repr__(self) -> str:
        return '__SERVER_TIMESTAMP__'


ORA_DEL_SERVER = OraDelServer()


@dataclass(frozen=True)
class Scrittura:
    """One write of a batch: operation, collection, document id, data, ``merge`` for ``set``."""

    op: str
    collezione: str
    doc_id: str
    dati: Mapping[str, Any] | None = None
    merge: bool = False


class Lotto:
    """A write batch: operations are queued and applied in order by :meth:`commit` (``lotto``: batch)."""

    def __init__(self, banca: BancaDati) -> None:
        self.banca = banca
        self.scritture: list[Scrittura] = []

    def _aggiungi(self, s: Scrittura) -> None:
        # the live journal counts a write when it is queued (WriteBatch.update), not when committed
        if s.op != 'create':
            self.banca._osserva(s.collezione, s.op, list(s.dati or {}) if s.op != 'delete' else [])
        self.scritture.append(s)

    def set(self, collezione: str, doc_id: str, dati: Mapping[str, Any], merge: bool = False) -> None:
        self._aggiungi(Scrittura('set', collezione, doc_id, dati, merge))

    def update(self, collezione: str, doc_id: str, dati: Mapping[str, Any]) -> None:
        self._aggiungi(Scrittura('update', collezione, doc_id, dati))

    def create(self, collezione: str, doc_id: str, dati: Mapping[str, Any]) -> None:
        # NOTE(bug): the live journal does not hook WriteBatch.create, so created documents are never counted.
        # Kept: the package journal counts what the live one counts.
        self._aggiungi(Scrittura('create', collezione, doc_id, dati))

    def delete(self, collezione: str, doc_id: str) -> None:
        self._aggiungi(Scrittura('delete', collezione, doc_id))

    def commit(self) -> int:
        n = len(self.scritture)
        self.banca._applica(self.scritture)
        self.scritture = []
        return n


class BancaDati(ABC):
    """What the pipeline reads from and writes to the platform database.

    Args:
        osservatore: called for every write (see :data:`Osservatore`).
    """

    def __init__(self, osservatore: Osservatore | None = None) -> None:
        self.osservatore = osservatore

    def _osserva(self, collezione: str, op: str, campi: list[str]) -> None:
        if self.osservatore is not None:
            with contextlib.suppress(Exception):  # the journal never stops a write
                self.osservatore(collezione, op, campi)

    @property
    @abstractmethod
    def ora_del_server(self) -> Any:
        """The server-timestamp sentinel of the backend."""

    @abstractmethod
    def righe(self, collezione: str, filtri: Sequence[Filtro] = ()) -> Iterator[tuple[str, dict[str, Any]]]:
        """``(id, fields)`` of the documents that pass every filter, in id order."""

    @abstractmethod
    def _applica(self, scritture: list[Scrittura]) -> None:
        """Apply a committed batch."""

    @abstractmethod
    def imposta(self, collezione: str, doc_id: str, dati: Mapping[str, Any], merge: bool = False) -> None:
        """A single document ``set`` (not in a batch)."""

    def lotto(self) -> Lotto:
        """A new write batch."""
        return Lotto(self)

    def scrivi_a_lotti(self, scritture: Iterable[Scrittura], dimensione: int = LOTTO) -> int:
        """Write in batches of ``dimensione``, in order; returns the number of writes."""
        tutte = list(scritture)
        for i in range(0, len(tutte), dimensione):
            b = self.lotto()
            for s in tutte[i : i + dimensione]:
                b._aggiungi(s)
            b.commit()
        return len(tutte)

    def ids(self, collezione: str) -> set[str]:
        """Ids of every document of a collection."""
        return {i for i, _ in self.righe(collezione)}

    def esistenti(self, collezione: str, ids: Iterable[str]) -> set[str]:
        """The ids among ``ids`` that already exist in the collection (read by id where the backend can)."""
        cercati = set(ids)
        return cercati & self.ids(collezione)


class BancaDatiFirestore(BancaDati):
    """Firestore through ``google.cloud.firestore`` (the real platform, or the harness fake on ``PYTHONPATH``).

    Args:
        progetto: the Firebase project.
        client: an existing ``firestore.Client`` (tests); created on first use otherwise.
        osservatore: see :class:`BancaDati`.
    """

    def __init__(self, progetto: str = PROGETTO, client: Any = None, osservatore: Osservatore | None = None) -> None:
        super().__init__(osservatore)
        self.progetto = progetto
        self._client = client

    @property
    def modulo(self) -> Any:
        from google.cloud import firestore

        return firestore

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = self.modulo.Client(project=self.progetto)
        return self._client

    @property
    def ora_del_server(self) -> Any:
        return self.modulo.SERVER_TIMESTAMP

    def _rif(self, collezione: str, doc_id: str) -> Any:
        return self.client.collection(collezione).document(doc_id)

    def righe(self, collezione: str, filtri: Sequence[Filtro] = ()) -> Iterator[tuple[str, dict[str, Any]]]:
        q = self.client.collection(collezione)
        for campo, op, valore in filtri:
            q = q.where(filter=self.modulo.FieldFilter(campo, op, valore))
        for d in q.stream():
            yield d.id, d.to_dict()

    def esistenti(self, collezione: str, ids: Iterable[str]) -> set[str]:
        """By id, 300 references at a time: it does not depend on the case and reads no other document."""
        cercati = list(ids)
        gia: set[str] = set()
        for k in range(0, len(cercati), 300):
            rif = [self._rif(collezione, i) for i in cercati[k : k + 300]]
            gia |= {d.id for d in self.client.get_all(rif) if d.exists}
        return gia

    def _applica(self, scritture: list[Scrittura]) -> None:
        b = self.client.batch()
        for s in scritture:
            rif = self._rif(s.collezione, s.doc_id)
            if s.op == 'set':
                b.set(rif, dict(s.dati or {}), merge=s.merge) if s.merge else b.set(rif, dict(s.dati or {}))
            elif s.op == 'update':
                b.update(rif, dict(s.dati or {}))
            elif s.op == 'create':
                b.create(rif, dict(s.dati or {}))
            elif s.op == 'delete':
                b.delete(rif)
            else:
                raise ValueError(f'unknown operation: {s.op}')
        b.commit()

    def imposta(self, collezione: str, doc_id: str, dati: Mapping[str, Any], merge: bool = False) -> None:
        self._osserva(collezione, 'set', list(dati))
        rif = self._rif(collezione, doc_id)
        rif.set(dict(dati), merge=merge) if merge else rif.set(dict(dati))


def _come_json(x: Any) -> Any:
    """Data of a write in JSON form, as the harness fake records it."""
    if isinstance(x, OraDelServer):
        return repr(x)
    if isinstance(x, Mapping):
        return {str(k): _come_json(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_come_json(v) for v in x]
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    if hasattr(x, 'isoformat'):
        return x.isoformat()
    return repr(x)


class BancaDatiMemoria(BancaDati):
    """An in-memory database that records writes and never applies them (like the harness fake).

    Args:
        collezioni: ``{collection: {id: fields}}``.
        osservatore: see :class:`BancaDati`.

    Attributes:
        scritture: every write, as the harness fake writes ``firestore_scritture.jsonl``.
    """

    def __init__(
        self,
        collezioni: Mapping[str, Mapping[str, Mapping[str, Any]]] | None = None,
        osservatore: Osservatore | None = None,
    ) -> None:
        super().__init__(osservatore)
        self.collezioni = {c: {i: dict(d) for i, d in docs.items()} for c, docs in (collezioni or {}).items()}
        self.scritture: list[dict[str, Any]] = []

    @property
    def ora_del_server(self) -> Any:
        return ORA_DEL_SERVER

    @staticmethod
    def _passa(dati: Mapping[str, Any], filtro: Filtro) -> bool:
        campo, op, valore = filtro
        x: Any = dati
        for k in campo.split('.'):
            if not isinstance(x, Mapping) or k not in x:
                return False
            x = x[k]
        if op == '==':
            return x == valore
        raise NotImplementedError(f'operator {op!r}')

    def righe(self, collezione: str, filtri: Sequence[Filtro] = ()) -> Iterator[tuple[str, dict[str, Any]]]:
        docs = self.collezioni.get(collezione, {})
        for i in sorted(docs):
            if all(self._passa(docs[i], f) for f in filtri):
                yield i, copy.deepcopy(docs[i])

    def esistenti(self, collezione: str, ids: Iterable[str]) -> set[str]:
        return set(ids) & set(self.collezioni.get(collezione, {}))

    def _registra(self, s: Scrittura, via: str) -> None:
        self.scritture.append(
            {
                'op': s.op,
                'collezione': s.collezione,
                'doc_id': s.doc_id,
                'dati': _come_json(s.dati) if s.dati is not None else None,
                'via': via,
                'esiste': s.doc_id in self.collezioni.get(s.collezione, {}),
                'merge': bool(s.merge),
            }
        )

    def _applica(self, scritture: list[Scrittura]) -> None:
        for s in scritture:
            self._registra(s, 'lotto')

    def imposta(self, collezione: str, doc_id: str, dati: Mapping[str, Any], merge: bool = False) -> None:
        self._osserva(collezione, 'set', list(dati))
        self._registra(Scrittura('set', collezione, doc_id, dati, merge), 'documento')
