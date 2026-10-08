"""Il campo `t04` di tools/carica_segnale_t04.py (07/10/2026): mappa, confronto con la proposta, righe cieche. Non legge dati."""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
import carica_segnale_t04 as S  # noqa: E402

IDS = {'a': 'neubauer.a', 'b': 'neubauer.b', 'c': 'neubauer.c'}


def test_segnale_mappa_e_disaccordo():
    r = {'caso_citato': 'neubauer', 'proposto_principi': ['neubauer.b', 'neubauer.c', 'nessuno']}
    e = {'principi': {'a', 'b', 'altro'}, 'incerti': {'c'}, 'cita': 'si'}
    s = S.segnale(r, e, {'a': 0.91, 'b': 0.8, 'c': 0.5, 'nessuno': 0.1}, IDS)
    assert s == {'versione': 'T04', 'principi': ['neubauer.a', 'neubauer.b'], 'incerti': ['neubauer.c'],
                 'punteggi': {'neubauer.a': 0.91, 'neubauer.b': 0.8, 'neubauer.c': 0.5},
                 'solo_t04': ['neubauer.a'], 'solo_proposta': ['neubauer.c'], 'disaccordo': True,
                 'confronto_con': 'proposto_principi', 'letto_il': '2026-10-07'}


def test_segnale_d_accordo_e_senza_proposta():
    e = {'principi': {'a'}, 'incerti': set()}
    assert S.segnale({'proposto_principi': ['neubauer.a']}, e, {}, IDS)['disaccordo'] is False
    s = S.segnale({'proposto_principi': None}, e, {}, IDS)
    assert s['disaccordo'] is False and s['confronto_con'] is None and s['solo_t04'] == []


def test_cieche_fuori():
    E = {'r1': {'principi': {'a'}, 'incerti': set()}, 'r2': {'principi': {'a'}, 'incerti': set()},
         'r3': {'principi': {'a'}, 'incerti': set()}, 'r4': {'principi': {'a'}, 'incerti': set()}}
    banca = {'r1': {'codice': 'X-1', 'caso_citato': 'neubauer', 'campione_cieco': True},
             'r2': {'codice': 'X-2', 'caso_citato': 'neubauer', 'validato_contesto': {'proposte_mostrate': False}},
             'r3': {'codice': 'X-3', 'caso_citato': 'neubauer', 'proposto_principi': ['neubauer.b']},
             'r4': {'codice': 'X-4', 'caso_citato': 'neubauer', 'scartato': True}}
    scr, conti = S.calcola(banca, E, {}, {'neubauer': IDS})
    assert list(scr) == ['r3'] and set(scr['r3']) == {'t04'}
    assert conti['cieche saltate'] == 2 and conti['con disaccordo'] == 1
