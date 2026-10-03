"""Shared fixtures of the TRACE tests.

Two kinds of reference:

- the *expected outputs* of the harness (``prove/attesi/``) on the 180-row sample (``prove/campione/``). They contain
  filing text and platform data, so they are not in git: the tests that need them are skipped when they are absent;
- the *live functions* of ``tools/``, imported from the copy in ``prove/campione/tools`` (identical to ``tools/``,
  checked by ``test_strumenti_del_campione_uguali``) so that their root is the sample, not production.

Nothing here writes outside ``tmp_path``; bytecode is not written, so ``tools/`` is never touched.
"""

from __future__ import annotations

import gzip
import importlib
import importlib.util
import json
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

sys.dont_write_bytecode = True

RADICE = Path(__file__).resolve().parent.parent
PROVE = RADICE / 'prove'
CAMPIONE = PROVE / 'campione'
ATTESI = PROVE / 'attesi'
STRUMENTI = RADICE / 'tools'
STRUMENTI_CAMPIONE = CAMPIONE / 'tools'
CASI = ('urgenda', 'neubauer', 'future-generations', 'klimaseniorinnen', 'cig-parere-clima', 'idh-oc-32-25')
SERIE = {'neubauer': 'P05', 'future-generations': 'P05', 'cig-parere-clima': 'P09'}

C_E_IL_CAMPIONE = (CAMPIONE / 'fixture' / 'corpus_rows.json').exists() and (CAMPIONE / 'tools').exists()
C_SONO_GLI_ATTESI = (ATTESI / 'MANIFEST.json').exists()

# the harness sample holds filing texts and platform data: it is never in git, nor in the public repository
richiede_campione = pytest.mark.skipif(
    not C_E_IL_CAMPIONE, reason='private data: prove/campione absent (filing texts, not redistributed)'
)
richiede_attesi = pytest.mark.skipif(
    not (C_E_IL_CAMPIONE and C_SONO_GLI_ATTESI),
    reason='private data: prove/campione or prove/attesi absent (filing texts, not redistributed)',
)


@pytest.fixture(autouse=True)
def _senza_trace_sonde(monkeypatch: pytest.MonkeyPatch) -> None:
    """The live probe-series helpers read TRACE_SONDE: every test starts without it."""
    monkeypatch.delenv('TRACE_SONDE', raising=False)


@pytest.fixture(scope='session')
def vivi() -> Callable[[str], ModuleType]:
    """Import a live module of ``tools/`` (the sample copy if present, else ``tools/`` itself)."""
    cartella = STRUMENTI_CAMPIONE if STRUMENTI_CAMPIONE.exists() else STRUMENTI
    if not cartella.exists():
        pytest.skip('live scripts absent: tools/ is not in the public repository (see legacy/tools)')
    if str(cartella) in sys.path:
        sys.path.remove(str(cartella))
    sys.path.insert(0, str(cartella))
    # a test module that imports today's tools/ by name at collection (tests/test_cerca_s05.py) leaves those modules
    # cached under the same names: drop them, so that the harness copies are the ones imported here (the test module
    # keeps its own references)
    if cartella.resolve() != STRUMENTI.resolve():
        for k, v in list(sys.modules.items()):
            f = getattr(v, '__file__', None) or ''
            if f and Path(f).resolve().parent == STRUMENTI.resolve():
                del sys.modules[k]

    def importa(nome: str) -> ModuleType:
        m = importlib.import_module(nome)
        assert Path(m.__file__).resolve().parent == cartella.resolve(), f'{nome} imported from {m.__file__}'
        return m

    return importa


@pytest.fixture(scope='session')
def vivi_oggi() -> Callable[[str], ModuleType]:
    """Import a module of today's ``tools/`` under another name (``<name>__oggi``), next to the harness copy.

    Only modules without side effects at import time are imported this way; nothing is run against production.
    """
    if not STRUMENTI.exists():
        pytest.skip('live scripts absent: tools/ is not in the public repository (see legacy/tools)')
    caricati: dict[str, ModuleType] = {}

    def importa(nome: str) -> ModuleType:
        if nome not in caricati:
            spec = importlib.util.spec_from_file_location(f'{nome}__oggi', STRUMENTI / f'{nome}.py')
            assert spec is not None and spec.loader is not None
            m = importlib.util.module_from_spec(spec)
            # the live scripts put tools/ first on sys.path and import their siblings: undo both, so that the harness
            # copies stay the ones imported by name (and nothing rooted in production is left behind)
            percorso, moduli = list(sys.path), set(sys.modules)
            try:
                spec.loader.exec_module(m)
            finally:
                sys.path[:] = percorso
                for k in set(sys.modules) - moduli:
                    f = getattr(sys.modules[k], '__file__', None) or ''
                    if Path(f).resolve().parent == STRUMENTI.resolve():
                        del sys.modules[k]
            caricati[nome] = m
        return caricati[nome]

    return importa


# reading the expected outputs


def attesi_jsonl(percorso: Path) -> list[dict[str, Any]]:
    """A normalised JSONL file of the expected outputs."""
    return [json.loads(riga) for riga in percorso.read_text(encoding='utf-8').split('\n') if riga.strip()]


def attesi_file(passo: str, relativo: str) -> Path:
    """``prove/attesi/<step>/file/<path relative to the root>``."""
    return ATTESI / passo / 'file' / relativo


def json_come_scritto(x: Any) -> Any:
    """``x`` after a JSON round trip, as the live scripts write it."""
    return json.loads(json.dumps(x, ensure_ascii=False, default=str))


def differenze(a: Any, b: Any, dove: str = '') -> list[str]:
    """Field-by-field differences between two JSON values (paths), empty when equal."""
    out: list[str] = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append(f'{dove}.{k}: missing in expected')
            elif k not in b:
                out.append(f'{dove}.{k}: missing in new')
            else:
                out += differenze(a[k], b[k], f'{dove}.{k}')
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            out += differenze(x, y, f'{dove}[{i}]')
    elif a != b or type(a) is not type(b):
        out.append(
            f'{dove or "."}: expected {json.dumps(a, ensure_ascii=False)[:200]} '
            f'new {json.dumps(b, ensure_ascii=False)[:200]}'
        )
    return out


def scrivi_gz(percorso: Path, righe: list[dict[str, Any]]) -> None:
    """Write a small synthetic page index."""
    percorso.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(percorso, 'wt', encoding='utf-8') as f:
        for r in righe:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
