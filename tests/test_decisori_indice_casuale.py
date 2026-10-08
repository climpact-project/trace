"""Prove di tools/decisori_indice_casuale.py e tools/decisori_dopo_letture.py (05/10/2026): niente rete, niente banca dati."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'tools'))
import decisori_dopo_letture as dl  # noqa: E402
import decisori_indice_casuale as ic  # noqa: E402


def test_wilson_contiene_la_proporzione_e_sta_in_0_1():
    lo, hi = ic.wilson(3, 10)
    assert 0 <= lo < 0.3 < hi <= 1
    assert ic.wilson(0, 0) is None
    assert ic.wilson(10, 10)[1] == 1.0


def test_compiti_dopo_sono_i_giri_0_4_e_i_principi_solo_dove_mancano():
    lavoro = {'righe': [{'id': 'a', 'l05': 'x', 'l05_dai_giri': True},
                        {'id': 'b', 'l05': 'x', 'l05_dai_giri': False},
                        {'id': 'c'}]}
    c = dl.compiti_dopo(lavoro)
    assert [x for x in c if x[2] == 'a'] == [('A', 'TIPO', 'a', str(g), 0) for g in range(5)]
    assert len([x for x in c if x[2] == 'b' and x[1] == 'L05']) == 5
    assert not [x for x in c if x[2] == 'c' and x[1] == 'L05']
    assert len(c) == 5 + 10 + 5


def test_campione_casuale_e_ripetibile_con_il_seme():
    import random
    elenco = [f'doc{i}#p{i % 7 + 1}' for i in range(500)]
    assert random.Random(ic.SEME).sample(elenco, 50) == random.Random(ic.SEME).sample(elenco, 50)
