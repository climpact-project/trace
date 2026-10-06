"""Il tetto dei lotti di Decision 2.0 (tools/decisori_d2.py, 06/10/2026): stesse domande, piu' passaggi, nessuna perdita."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))

import decisori_d2 as d


def test_ogni_domanda_in_un_solo_lotto():
    lunghezze = [20000, 3000, 20000, 9000, 20000, 20000, 20000, 20000]
    for tetto in (1, 12000, 30000, 10**9):
        gruppi = d.lotti_con_tetto(tetto)(lunghezze, 1_000_000)
        visti = sorted(i for g in gruppi for i in g)
        assert visti == list(range(len(lunghezze)))
        for g in gruppi:
            assert g == sorted(g)


def test_una_domanda_oltre_il_tetto_va_da_sola_ma_non_oltre_la_guardia():
    gruppi = d.lotti_con_tetto(12000)([20000, 20000, 3000], 1_000_000)
    assert [20000 // 8 * 8 for _ in gruppi]  # non si spezza nulla
    assert sorted(len(g) for g in gruppi) == [1, 1, 1]
    with pytest.raises(ValueError):
        d.lotti_con_tetto(12000)([20000], 10000)


def test_domande_corte_restano_insieme():
    assert d.lotti_con_tetto(12000)([1000] * 6, 1_000_000) == [[0, 1, 2, 3, 4, 5]]
    assert len(d.lotti_con_tetto(12000)([5000] * 6, 1_000_000)) == 3


def test_tetto_senza_guardia():
    assert d.lotti_con_tetto(100)([40, 40, 40], None) == [[0, 1], [2]]
