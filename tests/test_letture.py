"""Readings: the parsers are identical to the live ones, including the fix of 02/10/2026."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from conftest import CAMPIONE, richiede_campione

from tracepipe.letture import Lettura, estrai, estrai_tollerante, vuota

ROTTO = (
    '{"riferimento": "caso", "tipo_citazione": "sostanziale", "chi_parla": "corte", '
    '"proposizione": "lo Stato deve "ridurre" le emissioni", "motivo": "' + 'x' * 250 + '"}'
)

TESTI = [
    '{"tipo_citazione": "descrittiva", "chi_parla": "parte"}',
    'prima {"a": 1} dopo',
    '{"a": 1} e poi {"b": 2}',
    'nessun oggetto qui',
    '',
    '{rotto',
    '{"tipo_citazione": "critica", "proposizione": "con "virgolette" dentro"}',
    '{"chi_parla": "corte", "proposizione": "senza tipo "rotta""}',
    ROTTO,
    '```json\n{"principi": ["urgenda.dovere"], "altro": "", "motivo": "m"}\n```',
]


@pytest.mark.parametrize('testo', TESTI)
def test_come_vivo(vivi, testo: str) -> None:
    assert estrai(testo) == vivi('giudica_llm').estrai(testo)
    assert estrai_tollerante(testo) == vivi('classifica_lessicali').estrai_tollerante(testo)


def test_correzione_del_2_ottobre_testo_intero() -> None:
    """Recovery reads the full text: the motive after 200 characters is no longer lost."""
    x = estrai_tollerante(ROTTO)
    assert x['recuperata'] is True
    assert x['tipo_citazione'] == 'sostanziale'
    assert x['motivo'] == 'x' * 250
    assert len(estrai(ROTTO)['grezzo']) == 200
    assert x['grezzo'] == ROTTO


def test_illeggibile_senza_tipo() -> None:
    x = estrai_tollerante('{"chi_parla": "corte", "proposizione": "senza tipo "rotta""}')
    assert x['esito'] == 'ILLEGGIBILE'
    assert 'recuperata' not in x


def test_vuota(vivi) -> None:
    cd = vivi('chiamata_deepseek')
    for x in (
        {'esito': 'ILLEGGIBILE', 'grezzo': ''},
        {'esito': 'ILLEGGIBILE', 'grezzo': '  '},
        {'esito': 'ILLEGGIBILE', 'grezzo': 'x'},
        {'tipo_citazione': 'critica'},
        None,
        'testo',
        {'grezzo': None},
    ):
        assert vuota(x) == cd.vuota(x)
        assert Lettura.da_dict(x).vuota == cd.vuota(x if isinstance(x, dict) else {})
    assert vuota(estrai_tollerante(''))


def test_lettura_avanti_e_indietro() -> None:
    d = {'principi': ['a', 3, 'b'], 'altro': '', 'motivo': 'm', 'vicine': [{'pagina': 2}]}
    lettura = Lettura.da_dict(d)
    assert lettura.come_dict() == d
    assert lettura.come_dict() is not d
    assert lettura.principi == ['a', 'b']
    assert not lettura.illeggibile
    assert Lettura.da_testo('niente').illeggibile
    assert Lettura.da_testo(ROTTO).recuperata
    assert Lettura.da_testo(ROTTO).tipo_citazione == 'sostanziale'


def _letture_del_campione() -> Iterator[dict]:
    t = CAMPIONE / 'training'
    for f in sorted([*t.glob('lessicali_*_deepseek*.jsonl'), *(t / 'principi').glob('*_ripresa_deepseek*.jsonl')]):
        with open(f, encoding='utf-8') as h:
            for riga in h:
                for x in json.loads(riga).get('letture') or []:
                    if isinstance(x, dict):
                        yield x


@richiede_campione
def test_su_tutte_le_letture_del_campione(vivi) -> None:
    """Every saved reading of the sample, as JSON, cut in the middle, with broken quotes and as its raw text."""
    e_vivo, t_vivo = vivi('giudica_llm').estrai, vivi('classifica_lessicali').estrai_tollerante
    n = 0
    for x in _letture_del_campione():
        intero = json.dumps(x, ensure_ascii=False)
        prove = [intero, intero[: len(intero) // 2], intero.replace('\\"', '"'), 'Ecco: ' + intero + ' fine']
        if isinstance(x.get('grezzo'), str):
            prove.append(x['grezzo'])
        for testo in prove:
            assert estrai(testo) == e_vivo(testo)
            assert estrai_tollerante(testo) == t_vivo(testo)
            n += 1
    assert n > 1000
