"""D04 (03/10/2026): the 13 rows of the new documents, loaded like the others (tools/recupero_d04.py, ciclo_d04.sh).

What must hold:

- a prepared row already in the database with another provenance, or another row in the same document, stops the load;
- the rows written to the platform take the codes after the highest of today (S06 rows included), stay out of the team
  queues (``assegnato_a_in_attesa``) and carry corpus D04, name search S05;
- only complete, unjudged D04 rows go back into the queues;
- the live page index becomes the live index plus the D04 pages, with the copy of before kept, and never twice;
- the D04 entry goes into the version registry exactly once, and its code runs;
- the launchd watcher starts the chain only after S06 wrote FINITO and closed; on FERMO it frees the queue lock;
- the queue lock made immutable survives the ``rm -f`` of the S06 chain.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / 'tools'))
sys.dont_write_bytecode = True

import recupero_d04 as r4  # noqa: E402
import registro_d04 as reg4  # noqa: E402


def preparata(caso, doc, cs, chi='u1'):
    return {
        'caso': caso,
        'id': f'{caso}__{doc}__{cs}',
        'codice_provvisorio': 'URG-1757',
        'causa': 'markdown_nuovo_d04',
        'caso_citato': caso,
        'document_id': doc,
        'char_start': cs,
        'file': f'markdown/{doc}.md',
        'proposto_rete': 'lessicale',
        'esito': None,
        'assegnato_a': chi,
        'campione_cieco': False,
        'provenienza': {
            'corpus': 'D04',
            'estrazione': 'S05',
            'tipo': '',
            'principi': {},
            'composizione': '',
            'seguito': '',
        },
        'motivo_aggiunta': r4.MOTIVO,
    }


# ── the rows ──────────────────────────────────────────────────────────────────────────────────────────────────────


def test_controlla_righe_stops_on_other_provenance_or_rows_in_the_same_document():
    righe = [preparata('urgenda', 'doc-a', 10), preparata('urgenda', 'doc-b', 20)]
    assert r4.controlla_righe(righe, {'x': {'document_id': 'other'}}) == ([], [])
    # a D04 row already written (restart after a half write) is not a problem
    problemi, gia = r4.controlla_righe(righe, {righe[0]['id']: {k: v for k, v in righe[0].items() if k != 'id'}})
    assert problemi == [] and gia == [righe[0]['id']]
    problemi, _ = r4.controlla_righe(righe, {righe[0]['id']: {'provenienza': {'corpus': 'D03'}}})
    assert len(problemi) == 1 and 'altra provenienza' in problemi[0]
    problemi, _ = r4.controlla_righe(righe, {'s06-row': {'document_id': 'doc-b', 'provenienza': {'estrazione': 'S06'}}})
    assert len(problemi) == 1 and problemi[0].startswith('doc-b: altre righe')


def test_documenti_after_the_highest_code_hidden_and_marked():
    righe = [preparata('urgenda', 'doc-b', 30, 'u2'), preparata('urgenda', 'doc-a', 10, 'u1')]
    # URG-1790: an S06 row written after the dry run of cerca_d04.py
    esistenti = [('x1', {'codice': 'URG-1756'}), ('x2', {'codice': 'URG-1790'}), ('x3', {'codice': 'not a code'})]
    docs = r4.documenti('urgenda', righe, esistenti)
    assert [(i.split('__')[1], d['codice']) for i, d in docs.items()] == [('doc-a', 'URG-1791'), ('doc-b', 'URG-1792')]
    for d in docs.values():
        assert 'assegnato_a' not in d and d['assegnato_a_in_attesa'] in {'u1', 'u2'}
        assert d['provenienza']['corpus'] == 'D04' and d['provenienza']['estrazione'] == 'S05'
        assert d['esecuzione_id'] == 'urgenda__nomi__2026-10-03-D04' and d['motivo_aggiunta'] == r4.MOTIVO
        assert not {'id', 'codice_provvisorio', 'causa', 'caso'} & set(d)
        assert r4.e_d04(d)
    assert r4.documenti('urgenda', righe, esistenti) == docs  # same input, same codes
    with pytest.raises(ValueError):
        r4.documenti('urgenda', righe, [*esistenti, (righe[0]['id'], {})])


def test_rimetti_moves_only_complete_unjudged_d04_rows():
    completa = {
        'proposto_tipo_citazione': 'descrittiva',
        'proposto_principi': ['nessuno'],
        'proposto_punteggi_principi': {'p': 0.1},
        'assegnato_a_in_attesa': 'u1',
        'provenienza': {'corpus': 'D04'},
        'motivo_aggiunta': r4.MOTIVO,
    }
    righe = [
        ('ok', completa),
        ('senza_tipo', {**completa, 'proposto_tipo_citazione': ''}),
        ('giudicata', {**completa, 'esito': 'confermata'}),
        ('s06', {**completa, 'provenienza': {'estrazione': 'S06'}, 'motivo_aggiunta': 'altro'}),
        ('gia_dentro', {**completa, 'assegnato_a_in_attesa': None, 'assegnato_a': 'u1'}),
    ]
    mosse, incomplete = r4.mosse_rimetti(righe)
    assert mosse == [('ok', {'assegnato_a': 'u1', 'assegnato_a_in_attesa': None})]
    assert incomplete == ['senza_tipo']


def test_unisci_righe_replaces_and_appends():
    vecchie = ['{"id": "a"}\n', '{"id": "b"}\n']
    nuove = ['{"id": "b", "x": 1}\n', '{"id": "c"}\n']
    assert r4.unisci_righe(vecchie, nuove) == ['{"id": "a"}\n', '{"id": "b", "x": 1}\n', '{"id": "c"}\n']


def test_url_pdf_quotes_each_segment():
    assert r4.url_pdf('documents/a b/âmbar.pdf') == 'https://corpus.climpact.it/pdf/documents/a%20b/%C3%A2mbar.pdf'


# ── the live page index ───────────────────────────────────────────────────────────────────────────────────────────


def scrivi_gz(f, ids):
    with gzip.open(f, 'wt', encoding='utf-8') as h:
        for i in ids:
            h.write(json.dumps({'id': i, 'testo': i}) + '\n')


def test_indice_live_plus_added_pages_once(tmp_path, monkeypatch):
    pag, d4 = tmp_path / 'pagine', tmp_path / 'd04'
    pag.mkdir()
    d4.mkdir()
    scrivi_gz(pag / 'pagine.jsonl.gz', ['a#p1', 'a#p2'])
    scrivi_gz(pag / 'pagine.d04.aggiunte.jsonl.gz', ['n#p1'])
    reg = {
        'ingressi': {'index/pagine/pagine.jsonl.gz (vivo, copiato)': 'old'},
        'uscite': {
            'index/pagine/pagine.d04.aggiunte.jsonl.gz': r4.sha_file(pag / 'pagine.d04.aggiunte.jsonl.gz'),
            'pagine_aggiunte': 1,
        },
    }
    (d4 / 'markdown_d04_registro.json').write_text(json.dumps(reg), encoding='utf-8')
    monkeypatch.setattr(r4, 'PAG', pag)
    monkeypatch.setattr(r4, 'D4', d4)
    prima = r4.sha_file(pag / 'pagine.jsonl.gz')
    r4.fase_indice(argparse.Namespace(scrivi=False))
    assert r4.sha_file(pag / 'pagine.jsonl.gz') == prima  # a dry run writes nothing
    r4.fase_indice(argparse.Namespace(scrivi=True))
    assert r4.ids_gzip(pag / 'pagine.jsonl.gz') == ['a#p1', 'a#p2', 'n#p1']
    assert r4.sha_file(pag / 'pagine.prima-D04.jsonl.gz') == prima
    stato = json.loads((d4 / 'indice_d04.json').read_text(encoding='utf-8'))
    assert stato['vivo_cambiato_dopo_d04'] and stato['righe_dopo'] == 3
    r4.fase_indice(argparse.Namespace(scrivi=True))  # again: nothing added twice
    assert r4.ids_gzip(pag / 'pagine.jsonl.gz') == ['a#p1', 'a#p2', 'n#p1']


def test_indice_refuses_added_pages_not_registered(tmp_path, monkeypatch):
    pag, d4 = tmp_path / 'pagine', tmp_path / 'd04'
    pag.mkdir()
    d4.mkdir()
    scrivi_gz(pag / 'pagine.jsonl.gz', ['a#p1'])
    scrivi_gz(pag / 'pagine.d04.aggiunte.jsonl.gz', ['a#p1'])
    reg = {
        'ingressi': {'index/pagine/pagine.jsonl.gz (vivo, copiato)': 'x'},
        'uscite': {'index/pagine/pagine.d04.aggiunte.jsonl.gz': 'not the hash', 'pagine_aggiunte': 1},
    }
    (d4 / 'markdown_d04_registro.json').write_text(json.dumps(reg), encoding='utf-8')
    monkeypatch.setattr(r4, 'PAG', pag)
    monkeypatch.setattr(r4, 'D4', d4)
    with pytest.raises(SystemExit, match='registrate'):
        r4.fase_indice(argparse.Namespace(scrivi=True))
    reg['uscite']['index/pagine/pagine.d04.aggiunte.jsonl.gz'] = r4.sha_file(pag / 'pagine.d04.aggiunte.jsonl.gz')
    (d4 / 'markdown_d04_registro.json').write_text(json.dumps(reg), encoding='utf-8')
    with pytest.raises(SystemExit, match="gia' nel vivo"):
        r4.fase_indice(argparse.Namespace(scrivi=True))


# ── the version registry ──────────────────────────────────────────────────────────────────────────────────────────


def test_registro_entry_inserted_once_and_compiles():
    testo = (RADICE / 'tools' / 'registro_versioni.py').read_text(encoding='utf-8')
    if "'codice': 'D04'" in testo:
        pytest.skip("la voce D04 e' gia' nel registro")
    nuovo = reg4.applica(testo)
    compile(nuovo, 'registro_versioni.py', 'exec')
    assert nuovo.count("'codice': 'D04'") == 1 and nuovo.count("'D04': ('D03'") == 1
    assert nuovo.count("'D04': ('Documents: D03") == 1
    assert nuovo.index("'codice': 'D04'") < nuovo.index("'codice': 'T01'")
    assert reg4.applica(nuovo) == nuovo
    with pytest.raises(ValueError):
        reg4.applica(testo.replace(reg4.PRIMA_DI_T01, ''))


def test_registro_entry_runs(tmp_path):
    d4 = tmp_path / 'training' / 'd04'
    d4.mkdir(parents=True)
    (d4 / 'conti.json').write_text(json.dumps({'righe': 13, 'casi': {'urgenda': 4, 'idh-oc-32-25': 9}}))
    (d4 / 'pdf_d04.json').write_text(
        json.dumps({'pdf': [{'byte': 5, 'servito': ['200', 5]}, {'byte': 6, 'servito': ['404', 25]}]})
    )
    ns = {'QUI': tmp_path, 'json': json, 'R': [], 'sha': lambda p: 'x', 'copia': lambda c, *f: list(f)}
    exec('def registro():\n' + reg4.VOCE + '    return R\n', ns)
    (v,) = ns['registro']()
    assert v['codice'] == 'D04' and v['tipo'] == 'corpus'
    assert [m['valore'] for m in v['misure']][1:] == ['13: urgenda 4, idh-oc-32-25 9', '1 su 2']
    assert 'tools/ciclo_d04.sh' in v['codice_sorgente']
    for f in v['codice_sorgente']:
        assert (RADICE / f).exists(), f
    # without the counts (before the chain) the entry is not there
    (d4 / 'conti.json').unlink()
    ns['R'] = []
    assert ns['registro']() == []


# ── the launchd watcher and the queue lock ────────────────────────────────────────────────────────────────────────


def guardiano(tmp_path, log, plist_s06=False, iniziato=False, lucchetto=False):
    casa = tmp_path / 'casa'
    radice = casa / 'sabin-corpus'
    (radice / 'tools').mkdir(parents=True)
    (radice / 'training' / 's06').mkdir(parents=True)
    (casa / 'Library' / 'LaunchAgents').mkdir(parents=True)
    (radice / 'tools' / 'ciclo_d04.sh').write_text('echo PARTITO\n', encoding='utf-8')
    (radice / 'training' / 's06' / 'ciclo_s06.log').write_text(log, encoding='utf-8')
    if plist_s06:
        (casa / 'Library' / 'LaunchAgents' / 'it.climpact.s06.plist').write_text('x', encoding='utf-8')
    if iniziato:
        (radice / 'training' / 'd04' / 'passi').mkdir(parents=True)
        (radice / 'training' / 'd04' / 'passi' / 'inizio').write_text('x', encoding='utf-8')
    luc = radice / 'training' / 's06' / 'coda_occupata'
    if lucchetto:
        luc.write_text('S06', encoding='utf-8')
        subprocess.run(['chflags', 'uchg', str(luc)], check=True)
    p = subprocess.run(
        ['/bin/bash', str(RADICE / 'tools' / 'launchd' / 'attesa_d04.sh')],
        capture_output=True,
        text=True,
        env={**os.environ, 'HOME': str(casa)},
        check=False,
    )
    esiste = luc.exists()
    if esiste:
        subprocess.run(['chflags', 'nouchg', str(luc)], check=True)  # pytest must be able to clean up
    return p.stdout, esiste


@pytest.mark.skipif(sys.platform != 'darwin', reason='chflags e launchd: solo sul Mac')
@pytest.mark.parametrize(
    ('log', 'plist_s06', 'iniziato', 'parte', 'lucchetto_resta'),
    [
        ('03/10 10:06 inizio (pid 1)\n03/10 10:06 in attesa della scelta su T01\n', True, False, False, True),
        ('04/10 01:00 letture finite\n04/10 02:00 FINITO\n', True, False, False, True),  # S06 has not closed yet
        ('04/10 01:00 letture finite\n04/10 02:00 FINITO\n04/10 02:00 plist tolto\n', False, False, True, True),
        ('04/10 01:00 FERMO: letture (6 tentativi)\n04/10 01:00 plist tolto\n', False, False, False, False),
        ('04/10 01:00 FERMO: rapporto\n04/10 03:00 FINITO\n', False, False, True, True),  # stopped, resumed, finished
        ('', True, True, True, True),  # D04 already started: resume
    ],
)
def test_guardiano(tmp_path, log, plist_s06, iniziato, parte, lucchetto_resta):
    out, resta = guardiano(tmp_path, log, plist_s06, iniziato, lucchetto=True)
    assert ('PARTITO' in out) == parte
    assert resta == lucchetto_resta


@pytest.mark.skipif(sys.platform != 'darwin', reason='chflags: solo sul Mac')
def test_immutable_lock_survives_rm_f(tmp_path):
    luc = tmp_path / 'coda_occupata'
    luc.write_text('x', encoding='utf-8')
    subprocess.run(['chflags', 'uchg', str(luc)], check=True)
    try:
        p = subprocess.run(['/bin/bash', '-c', f'rm -f {luc}; echo dopo'], capture_output=True, text=True, check=False)
        assert luc.exists() and 'dopo' in p.stdout  # S06 goes on, the lock stays
        assert subprocess.run(['/bin/bash', '-c', f'[ -f {luc} ]'], check=False).returncode == 0  # guida.sh's test
    finally:
        subprocess.run(['chflags', 'nouchg', str(luc)], check=True)
