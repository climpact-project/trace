"""The ``trace`` command: subcommands, dry run by default, journal of every run."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tracepipe import cli
from tracepipe.banca import BancaDatiMemoria


def test_comandi() -> None:
    p = cli.parser()
    for argv in (
        ['cerca', '--caso', 'urgenda', '--solo-lessicale'],
        ['unisci', '--caso', 'urgenda', '--data', '2026-10-02'],
        ['prepara', 'paragrafi', '--caso', 'neubauer', '--sonde', 'P05'],
        ['prepara', 'pagine-attorno', '--caso', 'neubauer'],
        [
            'leggi',
            'tipo',
            '--caso',
            'neubauer',
            '--gruppo',
            'tutte',
            '--solo-vuote',
            '--temperatura',
            '0',
            '--seme',
            '1',
        ],
        ['leggi', 'principi', '--caso', 'neubauer'],
        ['leggi', 'pagine-attorno', '--caso', 'neubauer', '--etichetta', 'P05', '--uscita-suffisso', '_x'],
        ['carica', 'tipo', '--caso', 'neubauer', '--etichetta', '', '--sovrascrivi'],
        ['carica', 'ripresa', '--caso', 'neubauer', '--principi-da-l04', '--salva', 'x.json'],
        ['controlla', 'completezza', '--scrivi'],
        ['controlla', 'finestra'],
    ):
        a = p.parse_args(argv)
        assert cli.nome_strumento(a).startswith('tracepipe ' + argv[0])
    assert p.parse_args(['leggi', 'principi']).etichetta == 'l04nuove'
    a = p.parse_args(['carica', 'tipo'])
    assert a.scrivi is False and a.etichetta == 'v2'
    assert cli.nome_strumento(p.parse_args(['leggi', 'pagine-attorno'])) == 'tracepipe leggi pagine-attorno'


def test_cerca_solo_lessicale(tmp_path: Path, capsys) -> None:
    assert cli.main(['--radice', str(tmp_path), '--senza-giornale', 'cerca', '--caso', 'urgenda']) == 2
    assert 'rete semantica' in capsys.readouterr().err


def test_anteprima_e_giornale(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / 'training').mkdir()
    (tmp_path / 'training' / 'lessicali_neubauer_deepseek.jsonl').write_text(
        json.dumps({'id': 'neubauer__d__1', 'letture': [{'tipo_citazione': 'descrittiva'}] * 2}) + '\n'
    )
    banche: list[BancaDatiMemoria] = []

    def banca(g):
        b = BancaDatiMemoria(
            {'corpus_rows': {'neubauer__d__1': {'caso_citato': 'neubauer', 'proposto_rete': 'lessicale'}}},
            osservatore=g.scrittura_firestore if g else None,
        )
        banche.append(b)
        return b

    monkeypatch.setattr(cli, '_banca', banca)
    argv = ['--radice', str(tmp_path), 'carica', 'tipo', '--caso', 'neubauer', '--etichetta', '']
    assert cli.main(argv) == 0
    assert banche[-1].scritture == [] and 'ANTEPRIMA: niente scritto' in capsys.readouterr().out
    assert cli.main([*argv, '--scrivi']) == 0
    assert len(banche[-1].scritture) == 1
    righe = [json.loads(x) for f in (tmp_path / 'giornale').rglob('*.jsonl') for x in f.read_text().split('\n') if x]
    fine = [x for x in righe if x['tipo'] == 'fine']
    assert [x['strumento'] for x in fine] == ['tracepipe carica tipo'] * 2
    assert fine[-1]['firestore']['corpus_rows']['update'] == 1
    assert fine[-1]['file'][0]['percorso'] == 'training/lessicali_neubauer_deepseek.jsonl'


def test_radice_predefinita(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv('TRACE_RADICE', raising=False)
    assert cli._radice('') == cli.PREDEFINITA
    monkeypatch.setenv('TRACE_RADICE', str(tmp_path))
    assert cli._radice('') == tmp_path.resolve()


@pytest.mark.parametrize('cosa', ['tipo', 'principi', 'pagine-attorno'])
def test_lettori_senza_chiave(tmp_path: Path, cosa: str) -> None:
    """Without the key file the readers stop before reading anything (no DeepSeek is contacted)."""
    with pytest.raises(FileNotFoundError):
        cli.main(['--radice', str(tmp_path), '--senza-giornale', 'leggi', cosa, '--caso', 'neubauer'])


@pytest.mark.skipif(
    not (Path(cli.PREDEFINITA) / 'tools' / 'nuovi' / 'carica_ripresa.py').exists(),
    reason='live scripts absent: tools/nuovi/ is not in the public repository',
)
def test_esempio_di_passaggio(monkeypatch) -> None:
    """``tools/nuovi/carica_ripresa.py`` hands the live arguments to ``trace carica ripresa`` (nothing runs here)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        'nuovo_carica_ripresa', Path(cli.PREDEFINITA) / 'tools' / 'nuovi' / 'carica_ripresa.py'
    )
    assert spec is not None and spec.loader is not None
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    visti: list[list[str]] = []
    monkeypatch.setattr(cli, 'main', lambda argv: visti.append(argv) or 0)
    assert m.main(['--caso', 'neubauer', '--principi-da-l04', '--salva', 'x.json', '--scrivi']) == 0
    assert visti == [
        [
            '--radice',
            str(cli.PREDEFINITA),
            'carica',
            'ripresa',
            '--caso',
            'neubauer',
            '--principi-da-l04',
            '--salva',
            'x.json',
            '--scrivi',
        ]
    ]
