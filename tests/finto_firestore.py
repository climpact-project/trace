"""A minimal ``google.cloud.firestore`` for running live scripts in the tests (no network, nothing applied).

Only what the loaders and checks call: ``Client``, ``collection``, ``where(filter=FieldFilter(...))``, ``stream``,
``document``, ``batch`` (``set``, ``update``, ``create``, ``delete``, ``commit``), ``SERVER_TIMESTAMP``. Writes are
recorded as :class:`tracepipe.banca.BancaDatiMemoria` records them, so the two can be compared directly.
"""

from __future__ import annotations

import copy
import types
from typing import Any

from tracepipe.banca import ORA_DEL_SERVER, BancaDatiMemoria, Scrittura


def modulo(collezioni: dict[str, dict[str, dict[str, Any]]]) -> tuple[types.ModuleType, BancaDatiMemoria]:
    """A fake ``firestore`` module over ``collezioni`` and the memory database that records its writes."""
    registro = BancaDatiMemoria(collezioni)

    class FieldFilter:
        def __init__(self, campo: str, op: str, valore: Any) -> None:
            self.filtro = (campo, op, valore)

    class Rif:
        def __init__(self, col: str, did: str) -> None:
            self.col, self.id = col, did
            self._path = (col, did)

        def set(self, dati: dict[str, Any], merge: bool = False) -> None:
            registro._registra(Scrittura('set', self.col, self.id, dati, merge), 'documento')

        def update(self, dati: dict[str, Any]) -> None:
            registro._registra(Scrittura('update', self.col, self.id, dati), 'documento')

    class Doc:
        def __init__(self, col: str, did: str, dati: dict[str, Any]) -> None:
            self.id, self.reference, self._d = did, Rif(col, did), dati

        def to_dict(self) -> dict[str, Any]:
            return copy.deepcopy(self._d)

    class Query:
        def __init__(self, col: str, filtri: list[Any]) -> None:
            self.col, self.filtri = col, filtri

        def where(self, filter: Any = None) -> Query:
            return Query(self.col, [*self.filtri, filter.filtro])

        def stream(self) -> Any:
            for i, d in registro.righe(self.col, self.filtri):
                yield Doc(self.col, i, d)

        def document(self, did: str) -> Rif:
            return Rif(self.col, did)

    class Lotto:
        def __init__(self) -> None:
            self.ops: list[Scrittura] = []

        def update(self, rif: Rif, dati: dict[str, Any]) -> None:
            self.ops.append(Scrittura('update', rif.col, rif.id, dati))

        def set(self, rif: Rif, dati: dict[str, Any], merge: bool = False) -> None:
            self.ops.append(Scrittura('set', rif.col, rif.id, dati, merge))

        def create(self, rif: Rif, dati: dict[str, Any]) -> None:
            self.ops.append(Scrittura('create', rif.col, rif.id, dati))

        def delete(self, rif: Rif) -> None:
            self.ops.append(Scrittura('delete', rif.col, rif.id))

        def commit(self) -> None:
            for s in self.ops:
                registro._registra(s, 'lotto')
            self.ops = []

    class Client:
        def __init__(self, project: str | None = None, **kw: Any) -> None:
            self.project = project

        def collection(self, nome: str) -> Query:
            return Query(nome, [])

        def batch(self) -> Lotto:
            return Lotto()

    m = types.ModuleType('firestore')
    m.Client, m.FieldFilter, m.SERVER_TIMESTAMP = Client, FieldFilter, ORA_DEL_SERVER  # type: ignore[attr-defined]
    return m, registro


def installa(monkeypatch: Any, collezioni: dict[str, dict[str, dict[str, Any]]]) -> BancaDatiMemoria:
    """Put the fake in ``sys.modules`` as ``google.cloud.firestore`` for the duration of a test."""
    import sys

    m, registro = modulo(collezioni)
    google = types.ModuleType('google')
    cloud = types.ModuleType('google.cloud')
    cloud.firestore = m  # type: ignore[attr-defined]
    google.cloud = cloud  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, 'google', google)
    monkeypatch.setitem(sys.modules, 'google.cloud', cloud)
    monkeypatch.setitem(sys.modules, 'google.cloud.firestore', m)
    return registro
