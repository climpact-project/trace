"""End to end on the 180-row sample: the package redoes steps 02, 04 and 10 of the harness and matches ``prove/attesi``.

The chain is the one of the harness: the rows prepared at step 01 (taken from the expected outputs, step 01 is not in
this phase) -> :class:`MappaParagrafi` (step 02) -> :class:`SceltaPagineAttorno` (step 04) -> :class:`Composizione`
(step 10, with ``--principi-da-l04``). Each step reads what the previous one of the PACKAGE wrote, in a working root
under ``tmp_path`` whose other files are links to the sample. The comparison is field by field.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from conftest import (
    ATTESI,
    CAMPIONE,
    CASI,
    SERIE,
    attesi_file,
    attesi_jsonl,
    differenze,
    json_come_scritto,
    richiede_attesi,
)

from tracepipe.caso import MappaParagrafi
from tracepipe.composizione import Composizione, IngressiComposizione
from tracepipe.config import Config
from tracepipe.pagine_attorno import SceltaPagineAttorno, leggi_jsonl

pytestmark = richiede_attesi


def _scrivi_jsonl(percorso: Path, righe: list[dict[str, Any]]) -> None:
    """As the live scripts write: one ``json.dumps(..., ensure_ascii=False)`` per line."""
    if percorso.is_symlink():
        percorso.unlink()
    with open(percorso, 'w', encoding='utf-8') as f:
        for r in righe:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


@pytest.fixture(scope='module')
def radice(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A working root: links to the sample, real files for what the chain rewrites."""
    r = tmp_path_factory.mktemp('radice')
    for nome in ('cited-cases', 'index', 'codebook', 'markdown', 'documents'):
        if (CAMPIONE / nome).exists():
            (r / nome).symlink_to(CAMPIONE / nome)
    tr = r / 'training'
    tr.mkdir()
    for p in (CAMPIONE / 'training').iterdir():
        if p.name != 'principi':
            (tr / p.name).symlink_to(p)
    (tr / 'principi').mkdir()
    for p in (CAMPIONE / 'training' / 'principi').iterdir():
        (tr / 'principi' / p.name).symlink_to(p)
    for caso in CASI:  # step 01: the rows as the harness prepared them
        dst = tr / f'lessicali_{caso}_righe.jsonl'
        dst.unlink()
        shutil.copyfile(attesi_file(f'01_classifica_prepara_{caso}', f'training/lessicali_{caso}_righe.jsonl'), dst)
    return r


@pytest.fixture(scope='module')
def config(radice: Path) -> Config:
    return Config(radice=radice)


def _stdout(passo: str) -> str:
    return (ATTESI / passo / 'stdout.txt').read_text(encoding='utf-8')


# step 02: paragraph map


def _passi_02() -> list[tuple[str, str, str]]:
    out = [(c, '', f'02_principi_da_paragrafi_{c}') for c in CASI]
    out += [(c, s, f'02_principi_da_paragrafi_{c}_{s}') for c, s in SERIE.items()]
    return out


@pytest.fixture(scope='module')
def passo_02(config: Config) -> dict[str, tuple[list[dict[str, Any]], dict[str, int]]]:
    """Run the paragraph map for every case (and series in use), in harness order, writing like the live script."""
    risultati = {}
    righe_di = {c: leggi_jsonl(config.training / f'lessicali_{c}_righe.jsonl') for c in CASI}
    for caso, serie, passo in _passi_02():
        mappa = MappaParagrafi.carica(config, caso, serie)
        out, conti = mappa.principi_righe(righe_di[caso])
        _scrivi_jsonl(config.principi / f'{caso}_da_paragrafi{"_" + serie if serie else ""}.jsonl', out)
        risultati[passo] = (out, dict(conti))
    return risultati


@pytest.mark.parametrize(('caso', 'serie', 'passo'), _passi_02())
def test_passo_02_mappa_paragrafi(passo_02: dict, caso: str, serie: str, passo: str) -> None:
    out, conti = passo_02[passo]
    nome = f'training/principi/{caso}_da_paragrafi{"_" + serie if serie else ""}.jsonl'
    atteso = attesi_jsonl(attesi_file(passo, nome))
    assert len(out) == len(atteso)
    for i, (a, b) in enumerate(zip(atteso, json_come_scritto(out), strict=True)):
        assert not differenze(a, b), f'line {i + 1}: {differenze(a, b)}'
    assert _stdout(passo).split(' -> ')[0] == str(conti)


# step 04: surrounding pages


@pytest.fixture(scope='module')
def passo_04(config: Config, passo_02: dict) -> dict[str, tuple[list[dict[str, Any]], dict[str, int]]]:
    """Choose the surrounding pages for every case, on the paragraph map written by step 02."""
    risultati = {}
    for caso in CASI:
        out, conti = SceltaPagineAttorno.prepara_caso(config, caso, compat=True)
        _scrivi_jsonl(SceltaPagineAttorno.file_uscita(config, caso), out)
        risultati[caso] = (out, dict(conti))
    return risultati


@pytest.mark.parametrize('caso', CASI)
def test_passo_04_pagine_attorno(passo_04: dict, config: Config, caso: str) -> None:
    out, conti = passo_04[caso]
    passo = f'04_leggi_ripresa_prepara_{caso}'
    atteso = attesi_jsonl(attesi_file(passo, f'training/principi/{caso}_ripresa_righe{config.suf(caso)}.jsonl'))
    assert len(out) == len(atteso)
    for i, (a, b) in enumerate(zip(atteso, json_come_scritto(out), strict=True)):
        assert not differenze(a, b), f'line {i + 1}: {differenze(a, b)[:5]}'
    assert _stdout(passo).split(' -> ')[0] == str(conti)


# step 10: composition


@pytest.fixture(scope='module')
def righe_firestore() -> dict[str, dict[str, Any]]:
    return json.loads((CAMPIONE / 'fixture' / 'corpus_rows.json').read_text(encoding='utf-8'))


@pytest.fixture(scope='module')
def passo_10(config: Config, passo_04: dict, righe_firestore: dict) -> dict[str, Any]:
    """Compose the proposals for every case, as ``carica_ripresa.py --principi-da-l04``."""
    risultati = {}
    for caso in CASI:
        ingressi = IngressiComposizione.carica(config, caso, principi_da_l04=True)
        comp = Composizione.per_caso(config, caso, compat=True)
        # the fake Firestore streams in id order, like Firestore (order by __name__)
        righe = [
            (i, righe_firestore[i]) for i in sorted(righe_firestore) if righe_firestore[i].get('caso_citato') == caso
        ]
        risultati[caso] = comp.componi(righe, ingressi)
    return risultati


@pytest.mark.parametrize('caso', CASI)
def test_passo_10_scritture_firestore(passo_10: dict, caso: str) -> None:
    scritture, _ = passo_10[caso]
    attese = attesi_jsonl(ATTESI / f'10_carica_ripresa_{caso}' / 'firestore_scritture.jsonl')
    assert [(x['op'], x['collezione'], x['via']) for x in attese] == [('update', 'corpus_rows', 'lotto')] * len(attese)
    assert [x['doc_id'] for x in attese] == [rid for rid, _ in scritture]
    for x, (rid, campi) in zip(attese, scritture, strict=True):
        d = differenze(x['dati'], json_come_scritto(campi))
        assert not d, f'{rid}: {d[:5]}'


@pytest.mark.parametrize('caso', CASI)
def test_passo_10_proposte_salvate(passo_10: dict, caso: str) -> None:
    scritture, _ = passo_10[caso]
    f = attesi_file(f'10_carica_ripresa_{caso}', f'training/principi/{caso}_proposte_salvate.json')
    atteso = json.loads(f.read_text(encoding='utf-8'))
    nuovo = json_come_scritto(dict(scritture))
    assert not differenze(atteso, nuovo)


@pytest.mark.parametrize('caso', CASI)
def test_passo_10_conti(passo_10: dict, caso: str) -> None:
    """The counts the live script prints, in the same order."""
    _, conti = passo_10[caso]
    stampati, _ = json.JSONDecoder().raw_decode(_stdout(f'10_carica_ripresa_{caso}'))
    assert list(stampati.items()) == list(conti.items())


def test_passo_10_casi_coperti(passo_10: dict) -> None:
    """The sample exercises the branches that matter: L04 principles, follow-up, OCR corpus, cleared sentence."""
    tutte = [c for s, _ in passo_10.values() for _, c in s]
    assert len(tutte) >= 150
    assert any(c.get('provenienza.corpus') == 'D02' for c in tutte)
    assert any(v['prosegue'] for c in tutte for v in c['proposto_estensione'])
    assert any(c['proposto_frase_sostenuta'] == '' for c in tutte)
    assert any(c['proposto_principi'] == ['nessuno'] for c in tutte)
