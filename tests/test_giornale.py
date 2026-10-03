"""The operations journal: same JSONL schema as ``tools/giornale.py``, files, Firestore counts, DeepSeek calls,
exceptions; it never stops a run and always gives back ``open``."""

from __future__ import annotations

import builtins
import gzip
import json
from pathlib import Path
from typing import Any

import pytest
from conftest import ATTESI, richiede_attesi

from tracepipe.banca import BancaDatiMemoria
from tracepipe.giornale import Giornale, macchina


def _righe(radice: Path) -> list[dict[str, Any]]:
    out = []
    for f in sorted((radice / 'giornale').rglob('*.jsonl')):
        out += [json.loads(x) for x in f.read_text(encoding='utf-8').split('\n') if x]
    return out


def test_una_corsa(tmp_path: Path) -> None:
    (tmp_path / 'training').mkdir()
    (tmp_path / 'molti').mkdir()
    fuori = tmp_path.parent / f'{tmp_path.name}_fuori.txt'
    fuori.write_text('x')
    (tmp_path / 'training' / 'a.jsonl').write_text('{"id": 1}\n{"id": 2}\n')
    (tmp_path / 'training' / 'd.json').write_text('{}')
    with Giornale(tmp_path, 'tracepipe prova', ['--x']) as g:
        with open(tmp_path / 'training' / 'a.jsonl', encoding='utf-8') as f:
            f.read()
        with open(tmp_path / 'training' / 'b.txt', 'w') as f:
            f.write('uno\ndue\n')
        with gzip.open(tmp_path / 'training' / 'c.gz', 'wt') as f:
            f.write('z')
        open(fuori).close()
        (tmp_path / 'training' / 'd.json').read_text()  # pathlib: not seen, as live
        for i in range(51):
            open(tmp_path / 'molti' / f'{i}.txt', 'w').close()
        banca = BancaDatiMemoria(osservatore=g.scrittura_firestore)
        lotto = banca.lotto()
        lotto.update('corpus_rows', 'r1', {'b': 1, 'a': 2})
        lotto.create('corpus_rows', 'r2', {'z': 1})  # as live: a create is not counted
        lotto.commit()
        g.scrittura_firestore('corpus_rows', 'update', ['c'])
        g.chiamata_deepseek(
            {'tentativi': 2, 'fine': 'stop', 'tetto': 8000, 'riuscita': True, 'storia': [{'errore': 'e'}]}
        )
        g.conta('righe', 3)
        g.errore('qualcosa')
    assert builtins.open is not g._open
    inizio, fine = _righe(tmp_path)
    assert inizio['tipo'] == 'inizio' and fine['tipo'] == 'fine' and inizio['id'] == fine['id']
    assert fine['strumento'] == 'tracepipe prova' and fine['argomenti'] == ['--x'] and fine['macchina'] == macchina()
    file = {e['percorso']: e for e in fine['file']}
    assert set(file) == {'training/a.jsonl', 'training/b.txt', 'training/c.gz'}
    assert file['training/a.jsonl']['uso'] == ['letto'] and file['training/a.jsonl']['righe'] == 2
    assert file['training/b.txt']['uso'] == ['scritto'] and file['training/b.txt']['righe'] == 2
    assert len(file['training/b.txt']['sha256']) == 64
    assert fine['cartelle'] == [{'cartella': 'molti', 'file': 51, 'byte': 0, 'uso': ['scritto']}]
    assert fine['firestore'] == {'corpus_rows': {'set': 0, 'update': 2, 'delete': 0, 'campi': ['a', 'b', 'c']}}
    assert fine['deepseek'] == {
        'chiamate': 1,
        'riuscite': 1,
        'tentativi': 2,
        'fine': {'stop': 1},
        'tetto': {'8000': 1},
        'errori': ['e'],
    }
    assert fine['conti'] == {'righe': 3} and fine['errori'] == ['qualcosa']
    assert fine['eccezione'] is None and fine['esito'] == 'ok'


def test_eccezione_e_uscita(tmp_path: Path) -> None:
    with pytest.raises(ValueError), Giornale(tmp_path, 't'):
        raise ValueError('rotto')
    with pytest.raises(SystemExit), Giornale(tmp_path, 't'):
        raise SystemExit(1)
    _, b, _, d = _righe(tmp_path)
    assert b['esito'] == 'errore' and 'ValueError: rotto' in b['eccezione']
    assert d['esito'] == 'ok' and d['eccezione'] is None  # as live: SystemExit does not go through sys.excepthook


def test_come_il_giornale_vivo(vivi, monkeypatch) -> None:
    """The DeepSeek aggregation is the live one, call for call."""
    gv = vivi('giornale')
    monkeypatch.setattr(gv, '_stato', {**gv._stato, 'deepseek': {}})
    g = Giornale(Path('/x'), 't')
    chiamate = [
        {'tentativi': 1, 'fine': 'stop', 'tetto': 8000, 'riuscita': True, 'storia': []},
        {
            'tentativi': 4,
            'fine': 'length',
            'tetto': 16000,
            'riuscita': False,
            'storia': [{'errore': f'e{i}'} for i in range(7)],
        },
        {'tentativi': 0, 'fine': None, 'tetto': 8000, 'riuscita': False},
    ]
    for c in chiamate:
        gv.chiamata_deepseek(c)
        g.chiamata_deepseek(c)
    assert g.deepseek == gv._stato['deepseek']


@richiede_attesi
def test_stesse_chiavi_del_giornale_vivo(tmp_path: Path) -> None:
    """The keys of the start and end lines are those of the live journal (minus nothing: volatile keys included)."""
    from conftest import attesi_jsonl

    vive = attesi_jsonl(ATTESI / '10_carica_ripresa_urgenda' / 'giornale.jsonl')
    via = {'id', 'inizio', 'fine', 'durata_s', 'macchina', 'utente', 'cartella', 'python', 'commit', 'codice_sha256'}
    with Giornale(tmp_path, 't'):
        pass
    nuove = _righe(tmp_path)
    for v, n in zip(vive, nuove, strict=True):
        assert set(n) - via == set(v) and set(n) >= via - ({'fine', 'durata_s'} if n['tipo'] == 'inizio' else set())


def test_invia_con_la_banca(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv('GIORNALE_SENZA_FIRESTORE', raising=False)
    monkeypatch.setattr('tracepipe.giornale.macchina', lambda: 'mac')
    with Giornale(tmp_path, 't'):
        pass
    banca = BancaDatiMemoria()
    g = Giornale(tmp_path, 'invia')
    assert g.invia(banca) == 1
    assert [(x['collezione'], x['op'], x['merge']) for x in banca.scritture] == [('trace_giornale', 'set', True)]
    assert g.invia(banca) == 0  # already sent (giornale/inviate.txt)
    monkeypatch.setenv('GIORNALE_SENZA_FIRESTORE', '1')
    with Giornale(tmp_path, 't'):
        pass
    assert g.invia(banca) == 0


def test_osservatore_rotto_non_ferma(tmp_path: Path) -> None:
    def rotto(*_: Any) -> None:
        raise RuntimeError('x')

    banca = BancaDatiMemoria(osservatore=rotto)
    banca.imposta('c', 'd', {'a': 1})
    assert banca.scritture[0]['op'] == 'set'
