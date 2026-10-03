"""SceltaPagineAttorno (R08) on a synthetic root, against the live ``leggi_ripresa.prepara`` run on the same root."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import scrivi_gz

from tracepipe.config import Config
from tracepipe.corpus import IndicePagine
from tracepipe.pagine_attorno import Punteggi, SceltaPagineAttorno

CASO = 'caso-finto'
PAROLE = ' '.join(['the court held that the state has a duty of care towards its citizens'] * 6)
ROTTA = ' '.join(['xq7 zz9 ##4 kk1'] * 20)


def _scrivi(p: Path, righe: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in righe), encoding='utf-8')


@pytest.fixture
def radice(tmp_path: Path) -> Path:
    """A root with 4 rows, scores at every distance, an OCR score file and an unreadable page."""
    righe = [
        {'id': f'{CASO}__doc-a__1', 'document_id': 'doc-a', 'pagina': 12, 'contesto': 'c1', 'forma': 'F'},
        {'id': f'{CASO}__doc-a__2', 'document_id': 'doc-a', 'pagina': 3, 'contesto': 'c2', 'case_name': 'N'},
        {'id': f'{CASO}__doc-a__3', 'document_id': 'doc-a', 'pagina': None, 'contesto': 'c3'},
        {'id': f'{CASO}__doc-b__4', 'document_id': 'doc-b', 'pagina': '5', 'contesto': 'c4'},
    ]
    _scrivi(tmp_path / 'training' / f'lessicali_{CASO}_righe.jsonl', righe)
    _scrivi(
        tmp_path / 'training' / 'principi' / f'{CASO}_da_paragrafi.jsonl',
        [{'id': righe[0]['id'], 'paragrafi': ['unica:5'], 'principi': ['p1'], 'metodo': 'mappa dei paragrafi'}],
    )
    punti, ocr, finestra = [], [], []
    for k in range(1, 25):
        s = round(0.45 + 0.02 * k, 3)  # increasing with the page: 0.47 ... 0.93
        punti.append({'dove': 'pagina', 'pagina_id': f'doc-a#p{k}', 'principio': 'p1', 'punteggio': s})
        punti.append({'dove': 'pagina', 'pagina_id': f'doc-a#p{k}', 'principio': 'p2', 'punteggio': 0.1})
    punti.append({'dove': 'pagina', 'pagina_id': 'doc-a#p14', 'principio': 'p1', 'punteggio': 0.2})
    ocr.append({'dove': 'pagina', 'pagina_id': 'doc-a#p14', 'principio': 'p1', 'punteggio': 0.99})
    punti += [{'dove': 'pagina', 'pagina_id': f'doc-b#p{k}', 'principio': 'p1', 'punteggio': 0.9} for k in (2, 3, 7, 9)]
    finestra.append({'dove': 'pagina', 'pagina_id': 'doc-b#p15', 'principio': 'p1', 'punteggio': 0.95})
    punti.append({'dove': 'brano', 'riga': righe[0]['id'], 'principio': 'p1', 'punteggio': 0.7})
    ocr.append({'dove': 'brano', 'riga': righe[0]['id'], 'principio': 'p1', 'punteggio': 0.71})
    principi = tmp_path / 'training' / 'principi'
    _scrivi(principi / f'{CASO}_punteggi_0.jsonl', punti)
    _scrivi(principi / f'{CASO}_punteggi_ocr.jsonl', ocr)
    _scrivi(principi / f'{CASO}_finestra_punteggi_0.jsonl', finestra)
    pagine = [
        {'id': f'doc-a#p{k}', 'doc': 'doc-a', 'pagina': k, 'testo': ROTTA if k == 14 else f'{PAROLE} {k}'}
        for k in range(1, 25)
    ]
    pagine += [{'id': f'doc-b#p{k}', 'doc': 'doc-b', 'pagina': k, 'testo': PAROLE + 'x' * 4000} for k in range(1, 16)]
    scrivi_gz(tmp_path / 'index' / 'pagine' / 'pagine.jsonl.gz', pagine)
    (tmp_path / 'cited-cases').mkdir()
    return tmp_path


def test_come_leggi_ripresa_prepara(vivi, monkeypatch: pytest.MonkeyPatch, radice: Path) -> None:
    lr, so = vivi('leggi_ripresa'), vivi('sonde')
    monkeypatch.setattr(lr, 'QUI', radice)
    monkeypatch.setattr(lr, 'P', radice / 'training' / 'principi')
    monkeypatch.setattr(so, 'QUI', radice)
    lr.prepara(CASO)
    vivo = [json.loads(r) for r in (radice / 'training' / 'principi' / f'{CASO}_ripresa_righe.jsonl').open()]
    out, conti = SceltaPagineAttorno.prepara_caso(Config(radice=radice), CASO, compat=True)
    assert json.loads(json.dumps(out)) == vivo
    assert dict(conti) == {'con pagine vicine': 4}


@pytest.mark.parametrize('compat', [True, False])
def test_regole_della_finestra(radice: Path, compat: bool) -> None:
    config = Config(radice=radice)
    s = SceltaPagineAttorno.per_caso(config, CASO, compat=compat)
    c = s.candidate({'id': 'r', 'document_id': 'doc-a', 'pagina': 12})
    # at most 5, best first; the OCR score of page 14 (0.99) replaced the 0.2 of the same page
    assert [k for _, k, _ in c] == [14, 22, 21, 20, 19]
    assert c[0][0] == 0.99
    # near band from -2 to +3 at 0.5; farther at 0.8 (page 3 at 0.51 qualifies only from page 4 or 5)
    near = s.candidate({'id': 'r', 'document_id': 'doc-a', 'pagina': 4})
    assert 3 in [k for _, k, _ in near]
    far = s.candidate({'id': 'r', 'document_id': 'doc-a', 'pagina': 6})
    assert 3 not in [k for _, k, _ in far]
    # a row without a page: with the live defect pages 1-10 are searched as if the citation were on page 0; fixed,
    # there is no window
    senza = s.candidate({'id': 'r', 'document_id': 'doc-a', 'pagina': None})
    assert bool(senza) is compat
    assert bool(s.candidate({'id': 'r', 'document_id': 'doc-a', 'pagina': 0})) is compat


def test_pagina_illeggibile_e_taglio(radice: Path) -> None:
    config = Config(radice=radice)
    out, _ = SceltaPagineAttorno.prepara_caso(config, CASO)
    primo = out[0]
    assert 14 in primo['vicine_illeggibili']
    assert all(v['pagina'] != 14 for v in primo['vicine'])
    quarto = out[3]
    assert all(len(v['testo']) == 3500 for v in quarto['vicine'])
    assert primo['punteggi_brano'] == {'p1': 0.71}
    assert primo['principi_paragrafi'] == ['p1']


def test_punteggi_ordine_dei_file(radice: Path) -> None:
    files = Punteggi.file_finestra(Config(radice=radice), CASO)
    assert [f.name for f in files] == [
        f'{CASO}_punteggi_0.jsonl',
        f'{CASO}_finestra_punteggi_0.jsonl',
        f'{CASO}_punteggi_ocr.jsonl',
    ]


def test_indice_letto_solo_per_le_pagine_scelte(radice: Path) -> None:
    ind = IndicePagine(radice / 'index' / 'pagine' / 'pagine.jsonl.gz')
    assert set(ind.testi({'doc-a#p1', 'doc-b#p2'})) == {'doc-a#p1', 'doc-b#p2'}


# R10 (02/10/2026): 0.5 at every distance within +-10, no cap, always into a labelled file


def test_r10_come_leggi_ripresa_di_oggi(vivi, vivi_oggi, monkeypatch: pytest.MonkeyPatch, radice: Path) -> None:
    lr, so = vivi_oggi('leggi_ripresa'), vivi('sonde')
    monkeypatch.setattr(lr, 'QUI', radice)
    monkeypatch.setattr(lr, 'P', radice / 'training' / 'principi')
    monkeypatch.setattr(so, 'QUI', radice)
    lr.prepara(CASO, 'R10', 'cinque')
    vivo = [json.loads(r) for r in (radice / 'training' / 'principi' / f'{CASO}_ripresa_righe_cinque.jsonl').open()]
    out, _ = SceltaPagineAttorno.prepara_caso(Config(radice=radice), CASO, compat=True, regola='R10')
    assert json.loads(json.dumps(out)) == vivo
    assert (
        SceltaPagineAttorno.file_uscita(Config(radice=radice), CASO, 'cinque').name
        == f'{CASO}_ripresa_righe_cinque.jsonl'
    )
    # the live file of R08 is not touched by R10, and R10 without a label is refused
    assert not (radice / 'training' / 'principi' / f'{CASO}_ripresa_righe.jsonl').exists()
    with pytest.raises(SystemExit):
        lr.prepara(CASO, 'R10')
    # R08 by default, as before
    lr.prepara(CASO)
    r08 = [json.loads(r) for r in (radice / 'training' / 'principi' / f'{CASO}_ripresa_righe.jsonl').open()]
    out08, _ = SceltaPagineAttorno.prepara_caso(Config(radice=radice), CASO, compat=True)
    assert json.loads(json.dumps(out08)) == r08


def test_regole_r10(radice: Path) -> None:
    s = SceltaPagineAttorno.per_caso(Config(radice=radice), CASO, regola='R10')
    assert s.soglie.regola == 'R10' and s.soglie.max_vicine_larga is None
    # page 12: every page from 2 to 22 except 12 itself with a best score >= 0.5 (page 2 is 0.49: out), no cap
    c = s.candidate({'id': 'r', 'document_id': 'doc-a', 'pagina': 12})
    assert sorted(k for _, k, _ in c) == [k for k in range(3, 23) if k != 12]
    # page 3 (0.51) qualifies at 3 pages of distance too, which R08 refuses (0.8 there)
    assert 3 in [k for _, k, _ in s.candidate({'id': 'r', 'document_id': 'doc-a', 'pagina': 6})]
    with pytest.raises(ValueError):
        SceltaPagineAttorno.per_caso(Config(radice=radice), CASO, regola='R99')
