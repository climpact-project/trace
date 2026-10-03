"""BancaDati: the Firestore implementation (over a fake module) and the memory one write the same records."""

from __future__ import annotations

from typing import Any

import finto_firestore

from tracepipe.banca import ORA_DEL_SERVER, BancaDatiFirestore, BancaDatiMemoria, Scrittura

DATI = {
    'corpus_rows': {
        'b': {'caso_citato': 'urgenda', 'x': {'y': 1}},
        'a': {'caso_citato': 'urgenda'},
        'c': {'caso_citato': 'neubauer'},
    },
    'trace_versioni': {'L04': {}, 'R08': {}},
}


def _scrivi(banca: Any) -> None:
    banca.scrivi_a_lotti(
        [
            Scrittura('update', 'corpus_rows', 'a', {'k': 1}),
            Scrittura('create', 'corpus_rows', 'z', {'quando': banca.ora_del_server}),
            Scrittura('set', 'corpus_runs', 'r', {'n': 2}, merge=True),
            Scrittura('delete', 'corpus_rows', 'c'),
        ],
        dimensione=3,
    )
    banca.imposta('trace_controlli', 'oggi', {'casi': {}})


def test_firestore_e_memoria_uguali(monkeypatch) -> None:
    registro = finto_firestore.installa(monkeypatch, DATI)
    visti_f: list[tuple[str, str, list[str]]] = []
    visti_m: list[tuple[str, str, list[str]]] = []
    f = BancaDatiFirestore(osservatore=lambda *a: visti_f.append(a))
    m = BancaDatiMemoria(DATI, osservatore=lambda *a: visti_m.append(a))
    filtro = [('caso_citato', '==', 'urgenda')]
    assert (
        list(f.righe('corpus_rows', filtro))
        == list(m.righe('corpus_rows', filtro))
        == [
            ('a', {'caso_citato': 'urgenda'}),
            ('b', {'caso_citato': 'urgenda', 'x': {'y': 1}}),
        ]
    )
    assert list(m.righe('corpus_rows', [('x.y', '==', 1)])) == [('b', DATI['corpus_rows']['b'])]
    assert f.ids('trace_versioni') == m.ids('trace_versioni') == {'L04', 'R08'}
    assert f.ora_del_server is ORA_DEL_SERVER is m.ora_del_server
    _scrivi(f)
    _scrivi(m)
    assert registro.scritture == m.scritture
    assert [x['via'] for x in m.scritture] == ['lotto'] * 4 + ['documento']
    assert m.scritture[1]['dati'] == {'quando': '__SERVER_TIMESTAMP__'} and m.scritture[1]['esiste'] is False
    # the journal sees set/update/delete, not create (as the live journal)
    assert (
        visti_f
        == visti_m
        == [
            ('corpus_rows', 'update', ['k']),
            ('corpus_runs', 'set', ['n']),
            ('corpus_rows', 'delete', []),
            ('trace_controlli', 'set', ['casi']),
        ]
    )


def test_memoria_non_applica() -> None:
    m = BancaDatiMemoria(DATI)
    m.imposta('corpus_rows', 'a', {'caso_citato': 'altro'})
    assert dict(m.righe('corpus_rows'))['a'] == {'caso_citato': 'urgenda'}
