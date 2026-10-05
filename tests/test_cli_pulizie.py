"""The commands of the clean-up steps (``trace c03``, ``trace c07``, ``trace coppie``): they run on a snapshot, and
nothing is written to the platform without ``--scrivi``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tracepipe.cli import main, parser

FRASE = 'The court held that the State must reduce its emissions by 25 percent by 2020, as the judgment says.'


def riga(codice: str, cs: int, offset: list[int]) -> dict[str, Any]:
    return {
        'codice': codice,
        'case_id': 'c',
        'document_id': 'doc1',
        'caso_citato': 'neubauer',
        'proposto_rete': 'lessicale',
        'proposto_pagina': 3,
        'char_start': cs,
        'proposto_frase_sostenuta': FRASE,
        'proposto_frase_offset': offset,
        'file': 'markdown/doc1.md',
    }


@pytest.fixture()
def foto(tmp_path: Path) -> Path:
    f = tmp_path / 'foto.json'
    f.write_text(
        json.dumps({'a': riga('NEU-0001', 100, [50, 200]), 'b': riga('NEU-0002', 900, [800, 850])}), encoding='utf-8'
    )
    return f


def test_i_comandi_nuovi_sono_nel_parser() -> None:
    a = parser().parse_args(['c03', '--da', 'x', '--rivisto', 'r.tsv', '--scrivi'])
    assert (a.comando, a.da, a.rivisto, a.scrivi) == ('c03', 'x', 'r.tsv', True)
    a = parser().parse_args(['c07', '--da', 'x', '--spunte-team', 's.tsv', '--ipotesi-tutte'])
    assert a.comando == 'c07' and a.spunte_team == 's.tsv' and a.ipotesi_tutte and not a.scrivi
    a = parser().parse_args(['coppie', 'elenco', '--fotografia', 'f.json', '--uscita', 'u.tsv'])
    assert (a.cosa, a.soglia) == ('elenco', 5000)
    with pytest.raises(SystemExit):
        parser().parse_args(['c03'])  # --da is required


def test_c03_in_anteprima_scrive_gli_elenchi_e_niente_altro(
    tmp_path: Path, foto: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(['--radice', str(tmp_path), '--senza-giornale', 'c03', '--da', 'prova', '--fotografia', str(foto)]) == 0
    assert 'ANTEPRIMA: niente scritto in banca dati' in capsys.readouterr().out
    elenco = tmp_path / 'training' / 'esclusioni' / 'C03_da_scrivere.tsv'
    assert elenco.read_text(encoding='utf-8').splitlines()[1].startswith('testo_nota\tNEU-0001\tNEU-0002')


def test_c07_in_anteprima(tmp_path: Path, foto: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(['--radice', str(tmp_path), '--senza-giornale', 'c07', '--da', 'prova', '--fotografia', str(foto)]) == 0
    assert 'righe toccate 0' in capsys.readouterr().out
    assert main(['--radice', str(tmp_path), '--senza-giornale', 'c07', '--da', 'p', '--ipotesi-tutte', '--scrivi']) == 2


def test_la_prova_dei_freni_da_riga_di_comando(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(['--senza-giornale', 'coppie', 'prova-freni']) == 0
    assert 'PROVA DEI FRENI: PASSA' in capsys.readouterr().out


def test_l_elenco_delle_coppie_vicine(tmp_path: Path, foto: Path, capsys: pytest.CaptureFixture[str]) -> None:
    uscita = tmp_path / 'coppie.tsv'
    base = ['--radice', str(tmp_path), '--senza-giornale', 'coppie', 'elenco', '--fotografia', str(foto)]
    assert main([*base, '--uscita', str(uscita)]) == 0
    righe = uscita.read_text(encoding='utf-8').splitlines()
    assert righe[0].startswith('id_coppia\tcaso') and righe[1].split('\t')[:2] == ['NEU-0001a-NEU-0001b', 'neubauer']
    assert '1 coppie a 5000 caratteri' in capsys.readouterr().out
    assert main([*base, '--soglia', '50', '--uscita', str(uscita)]) == 0
    assert len(uscita.read_text(encoding='utf-8').splitlines()) == 1
