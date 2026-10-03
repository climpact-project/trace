"""Pages and the page index, on a synthetic index (no filing text)."""

from __future__ import annotations

from pathlib import Path

from conftest import CAMPIONE, richiede_campione, scrivi_gz

from tracepipe.corpus import IndicePagine, Pagina


def _indice(tmp_path: Path) -> IndicePagine:
    p = tmp_path / 'index' / 'pagine' / 'pagine.jsonl.gz'
    scrivi_gz(
        p,
        [
            {'id': 'doc-a#p1', 'doc': 'doc-a', 'file': 'markdown/a.md', 'pagina': 1, 'da': 0, 'a': 10, 'testo': 'uno'},
            {'id': 'doc-a#p2', 'doc': 'doc-a', 'file': 'markdown/a.md', 'pagina': 2, 'da': 10, 'a': 20, 'testo': 'due'},
            {'id': 'doc-b#p1', 'doc': 'doc-b', 'file': 'markdown/b.md', 'pagina': 1, 'da': 0, 'a': 5, 'testo': 'tre'},
            {
                'id': 'doc-a#p2',
                'doc': 'doc-a',
                'file': 'markdown/a.md',
                'pagina': 2,
                'da': 10,
                'a': 20,
                'testo': 'due bis',
            },
        ],
    )
    return IndicePagine(p)


def test_id_pagina() -> None:
    assert Pagina.id_di('doc-a', 7) == 'doc-a#p7'


def test_testi_solo_quelli_chiesti_ultima_vince(tmp_path: Path) -> None:
    ind = _indice(tmp_path)
    assert ind.testi(['doc-a#p2', 'doc-b#p1', 'manca#p1']) == {'doc-a#p2': 'due bis', 'doc-b#p1': 'tre'}
    assert ind.testi([]) == {}


def test_pagine_e_documento(tmp_path: Path) -> None:
    ind = _indice(tmp_path)
    p = ind.pagine(['doc-b#p1'])['doc-b#p1']
    assert (p.doc, p.numero, p.da, p.a, p.testo) == ('doc-b', 1, 0, 5, 'tre')
    d = ind.documento('doc-a')
    assert sorted(d.pagine) == [1, 2]
    assert d.file == 'markdown/a.md'
    assert d.testo(2) == 'due bis'
    assert d.testo(9) == ''
    assert d.pagina(9) is None


@richiede_campione
def test_indice_del_campione_come_lettura_diretta() -> None:
    """The streaming reader gives the same texts as reading the sample index line by line."""
    import gzip
    import json

    percorso = CAMPIONE / 'index' / 'pagine' / 'pagine.jsonl.gz'
    diretti = {}
    with gzip.open(percorso, 'rt', encoding='utf-8') as f:
        for riga in f:
            x = json.loads(riga)
            diretti[x['id']] = x['testo']
    ind = IndicePagine(percorso)
    assert ind.testi(diretti) == diretti
