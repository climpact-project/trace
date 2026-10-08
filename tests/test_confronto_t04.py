"""Le funzioni pure di tools/confronto_t04.py (07/10/2026): maggioranza R11 dai voti, riferimento, P/R/F1, kappa,
distanza dei dubbi, bootstrap ripetibile per atto. Non leggono dati."""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
import confronto_t04 as C  # noqa: E402


def test_r11_da_voti_maggioranza_stretta():
    assert C.r11_da_voti({'urgenda.a': '3/5', 'urgenda.b': '2/5', 'nessuno': '3/5'}) == {'a'}
    assert C.r11_da_voti({'a': '2/3', 'b': '1/2'}) == {'a'}        # 2 su 3 si', 1 su 2 no
    assert C.r11_da_voti({}) is None and C.r11_da_voti(None) is None


def test_riferimento_tiene():
    assert C.riferimento_tiene({'caso': '4/5', 'omonimo': '1/5'}) is True
    assert C.riferimento_tiene({'indice_o_elenco': '5/5'}) is False
    assert C.riferimento_tiene(None) is None


def test_prf_e_f1():
    V = {'r1': {'a', 'b'}, 'r2': set()}
    b = {'r1': {'a'}, 'r2': {'c'}}
    assert C.conti(V, b, ['r1', 'r2']) == (1, 1, 1)
    assert C.prf(1, 1, 1)['f1'] == 0.5
    assert C.f1(V, {'r1': set(), 'r2': set()}, ['r2']) is None


def test_kappa():
    assert C.kappa([1, 0, 1, 0], [1, 0, 1, 0]) == 1.0
    assert C.kappa([1, 1, 0, 0], [0, 0, 1, 1]) == -1.0
    assert C.kappa([], []) is None


def test_distanza():
    assert C.distanza({'a', 'b'}, {'a': 1.0, 'b': 0.0}, {'a': 0.2}) == 0.8


def test_bootstrap_ripetibile_per_atto():
    atti = {f'r{i}': f'atto{i % 3}' for i in range(9)}
    stat = lambda rr: len(rr) / 9  # noqa: E731
    assert C.bootstrap(list(atti), atti, stat, volte=200) == C.bootstrap(list(atti), atti, stat, volte=200)
