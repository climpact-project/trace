"""End to end: the harness steps redone by the package (``prove/esegui_pacchetto.py``), compared with ``confronta.py``.

About three minutes of CPU (the search by name reads every markdown file of the sample): it runs only with
``TRACE_BANCO=1``. The script runs the package with ``--compat`` on a clean copy of the sample, then
``confronta.py`` on every step the package covers (``comando.json`` and ``giornale.jsonl`` apart), then compares the
journals without ``strumento`` and ``argomenti``; exit 0 means everything equal.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
from conftest import PROVE, RADICE, richiede_attesi

pytestmark = [
    richiede_attesi,
    pytest.mark.skipif(os.environ.get('TRACE_BANCO') != '1', reason='slow: set TRACE_BANCO=1'),
]


def test_passi_del_banco_uguali() -> None:
    r = subprocess.run(
        [sys.executable, str(PROVE / 'esegui_pacchetto.py')], cwd=RADICE, capture_output=True, text=True, timeout=3600
    )
    assert r.returncode == 0, r.stdout[-4000:] + r.stderr[-2000:]
    assert 'diversi 0, mancano 0' in r.stdout
