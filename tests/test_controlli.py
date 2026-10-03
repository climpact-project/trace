"""The checks: same lines, files and report as ``controllo_completezza`` and ``controllo_finestra``."""

from __future__ import annotations

import datetime
import gzip
import io
import json
import shutil
import sys
import types
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import finto_firestore
import pytest
from conftest import ATTESI, CAMPIONE, attesi_jsonl, richiede_attesi, richiede_campione

from tracepipe.banca import BancaDatiMemoria
from tracepipe.config import Config
from tracepipe.controlli import ControlloCompletezza, ControlloFinestra

PV = {'corpus': 'D01', 'estrazione': 'S01', 'tipo': 'L03', 'sonde': 'P05', 'principi': {'n.a': ['L04']}}
BUONA = {
    'caso_citato': 'neubauer',
    'proposto_rete': 'lessicale',
    'codice': 'NEU-0001',
    'document_id': 'd',
    'file': 'markdown/d.md',
    'provenienza': PV,
    'proposto_tipo_citazione': 'descrittiva',
    'proposto_principi': ['n.a'],
    'proposto_punteggi_principi': {'n.a': 0.4},
}


def _r(**kw: Any) -> dict[str, Any]:
    x = json.loads(json.dumps(BUONA))
    for k, v in kw.items():
        if v is None:
            x.pop(k, None)
        else:
            x[k] = v
    return x


RIGHE = {
    'neubauer__d__1': _r(),
    'neubauer__d__2': _r(codice='NEU-2', provenienza={}),
    'neubauer__d__3': _r(codice='NEU-0003', proposto_principi=[], proposto_tipo_citazione=None),
    'neubauer__d__4': _r(codice='NEU-0004', provenienza=dict(PV, sonde='', tipo='X99'), proposto_punteggi_principi={}),
    'neubauer__d__5': _r(codice='NEU-0001'),
    'neubauer__d__6': _r(
        codice='NEU-0006',
        proposto_estensione=[{'prova_esito': 'inventata', 'prosegue': True, 'testuale': False}],
        proposto_frase_esito='inventata',
    ),
    'neubauer__d__7': _r(codice='NEU-0007', esito='confermata', validato_principi=None),
    'neubauer__d__8': _r(codice='NEU-0008', validato_da='x'),
    'neubauer__d__9': _r(codice='NEU-0009', proposta_provvisoria=True, proposto_principi=[]),
    'neubauer__d__10': _r(codice='NEU-0010', proposto_rete='fusa', fusa_in='NEU-9999'),
    'neubauer__d__11': _r(codice='NEU-0011', proposto_rete='fusa', fusa_in='NEU-0010'),
    'neubauer__d__12': _r(codice='NEU-0012', proposto_rete='semantica'),
    'neubauer__d__13': _r(codice=None, document_id='', provenienza=dict(PV, estrazione=''), proposto_principi=None),
    'neubauer__d__14': _r(codice='NEU-0014', proposto_principi=['x'], provenienza=dict(PV, principi={})),
    'urgenda__d__1': _r(caso_citato='urgenda', codice='URG-0001', provenienza=dict(PV, tipo='')),
}


def FERMA() -> datetime.datetime:  # noqa: N802 (a constant clock)
    return datetime.datetime(2026, 10, 2, 12, 0)


VERSIONI = {k: {} for k in ('D01', 'S01', 'L03', 'L04', 'P05')}


@richiede_campione
@pytest.mark.parametrize('scrivi', [False, True])
def test_completezza_come_il_vivo(vivi, monkeypatch, tmp_path, scrivi) -> None:
    cc = vivi('controllo_completezza')
    rv, rp = tmp_path / 'v', tmp_path / 'p'
    for r in (rv, rp):
        (r / 'training').mkdir(parents=True)
    vivo = finto_firestore.installa(monkeypatch, {'corpus_rows': RIGHE, 'trace_versioni': VERSIONI})
    monkeypatch.setattr(cc, 'firestore', sys.modules['google.cloud.firestore'])
    monkeypatch.setattr(cc, 'QUI', rv)
    monkeypatch.setattr(cc, 'datetime', types.SimpleNamespace(datetime=types.SimpleNamespace(now=FERMA)))
    monkeypatch.setattr(sys, 'argv', ['controllo_completezza.py'] + ['--scrivi'] * scrivi)
    out = io.StringIO()
    with redirect_stdout(out):
        cc.main()
    banca = BancaDatiMemoria({'corpus_rows': RIGHE, 'trace_versioni': VERSIONI})
    righe: list[str] = []
    rapporto = ControlloCompletezza(
        Config(radice=rp), banca, scrivi=scrivi, stampa=righe.append, orologio=FERMA
    ).esegui()
    assert '\n'.join(righe) + '\n' == out.getvalue()
    assert banca.scritture == vivo.scritture
    assert sorted(p.name for p in (rv / 'training').iterdir()) == sorted(p.name for p in (rp / 'training').iterdir())
    for p in (rv / 'training').iterdir():
        assert p.read_bytes() == (rp / 'training' / p.name).read_bytes()
    problemi = rapporto['casi']['neubauer']['problemi']
    assert len(problemi) >= 15, sorted(problemi)


@richiede_attesi
def test_completezza_del_banco(tmp_path) -> None:
    fixture = json.loads((CAMPIONE / 'fixture' / 'corpus_rows.json').read_text(encoding='utf-8'))
    altre = json.loads((CAMPIONE / 'fixture' / 'altre_collezioni.json').read_text(encoding='utf-8'))
    banca = BancaDatiMemoria({'corpus_rows': fixture, **altre})
    (tmp_path / 'training').mkdir()
    righe: list[str] = []
    ControlloCompletezza(Config(radice=tmp_path), banca, scrivi=True, stampa=righe.append, orologio=FERMA).esegui()
    assert '\n'.join(righe) + '\n' == (ATTESI / '11_controllo_completezza' / 'stdout.txt').read_text()
    attese = attesi_jsonl(ATTESI / '11_controllo_completezza' / 'firestore_scritture.jsonl')
    assert [json.loads(json.dumps(x, sort_keys=True)) for x in banca.scritture] == attese


@richiede_campione
def test_finestra_come_il_vivo(vivi, monkeypatch) -> None:
    cf = vivi('controllo_finestra')
    out = io.StringIO()
    with redirect_stdout(out):
        codice = cf.main()
    righe: list[str] = []
    assert ControlloFinestra(Config(radice=CAMPIONE), compat=True, stampa=righe.append).esegui() == codice
    assert '\n'.join(righe) + '\n' == out.getvalue()


def _radice_finestra(tmp: Path) -> Path:
    r = tmp / 'r'
    (r / 'index' / 'pagine').mkdir(parents=True)
    (r / 'training' / 'principi').mkdir(parents=True)
    (r / 'cited-cases').mkdir()
    for c in Config().casi:
        (r / 'training' / f'lessicali_{c}_righe.jsonl').write_text('')
    shutil.copy(CAMPIONE / 'cited-cases' / 'neubauer-P05.yaml', r / 'cited-cases') if CAMPIONE.exists() else None
    with gzip.open(r / 'index' / 'pagine' / 'pagine.jsonl.gz', 'wt', encoding='utf-8') as f:
        for k in range(1, 30):
            f.write(json.dumps({'id': f'd#p{k}'}) + '\n')
    with open(r / 'training' / 'principi' / 'urgenda_punteggi_0.jsonl', 'w', encoding='utf-8') as f:
        for k in range(1, 30):
            if k != 5:
                f.write(
                    json.dumps({'dove': 'vicina', 'pagina_id': f'd#p{k}', 'principio': 'p', 'punteggio': 0.1}) + '\n'
                )
    righe = [{'id': 'a', 'document_id': 'd', 'pagina': 3}, {'id': 'b', 'document_id': 'd', 'pagina': None}]
    (r / 'training' / 'lessicali_urgenda_righe.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in righe))
    return r


@pytest.mark.skipif(not CAMPIONE.exists(), reason='needs the neubauer-P05 case file of the sample')
@pytest.mark.parametrize('compat', [True, False])
def test_finestra_pagina_mancante_e_riga_senza_pagina(tmp_path, compat) -> None:
    r = _radice_finestra(tmp_path)
    (r / 'cited-cases' / 'future-generations-P05.yaml').write_text('x: 1\n')
    (r / 'cited-cases' / 'cig-parere-clima-P09.yaml').write_text('x: 1\n')
    righe: list[str] = []
    assert ControlloFinestra(Config(radice=r), compat=compat, stampa=righe.append).esegui() == 1
    # page 5 has no score: row a (page 3) sees it; row b without a page only with the live defect (window from 0)
    assert righe[0] == f'urgenda (sonde P01): pagine della finestra senza punteggio 1, citazioni con buchi {1 + compat}'
    assert righe[-1] == 'FINESTRA INCOMPLETA: 1 pagine senza punteggio'
