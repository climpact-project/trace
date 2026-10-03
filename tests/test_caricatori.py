"""The loaders: the same writes (content and order), the same screen lines, as ``carica_lessicali`` and
``carica_ripresa``; batches of 400; nothing written without ``scrivi``."""

from __future__ import annotations

import copy
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import finto_firestore
import pytest
from conftest import ATTESI, CAMPIONE, CASI, attesi_file, attesi_jsonl, richiede_attesi, richiede_campione

from tracepipe.banca import BancaDatiMemoria
from tracepipe.caricatori import CaricatoreRipresa, CaricatoreTipo, versione_codebook
from tracepipe.config import Config

# synthetic rows for the type loader

LETTURE = {
    'c__a__1': {
        'letture': [
            {
                'tipo_citazione': 'descrittiva',
                'chi_parla': 'corte',
                'proposizione': ' una\n frase ',
                'riferimento': 'caso',
                'motivo': 'perche\n si',
            },
            {'tipo_citazione': 'descrittiva'},
        ],
        'data': '2026-09-28',
    },
    'c__a__2': {
        'letture': [
            {'tipo_citazione': 'sostanziale', 'chi_parla': 'giudice', 'riferimento': 'soggetto_omonimo'},
            {'tipo_citazione': None},
        ],
        'data': '2026-10-02',
        'codebook': '0.4-pilot',
    },
    'c__a__3': {'letture': [{'tipo_citazione': 'inventata'}, {}]},
    'c__a__4': {
        'letture': [{'tipo_citazione': 'critica', 'riferimento': 'qualcosa'}, {'tipo_citazione': 'critica'}],
        'data': '2026-10-01',
    },
    'c__a__6': {'letture': [{'tipo_citazione': 'implicita'}, {'tipo_citazione': 'descrittiva'}]},
    'c__a__7': {'letture': [{'tipo_citazione': 'menzione_in_catena', 'riferimento': 'caso_urgenda'}]},
}
RIGHE = {
    'c__a__1': {'proposto_rete': 'lessicale', 'proposto_note': 'nota mia\nDeepSeek, due letture: ? / ?.\naltra'},
    'c__a__2': {'proposto_rete': 'entrambe'},
    'c__a__3': {'proposto_rete': 'lessicale'},
    'c__a__4': {'proposto_rete': 'lessicale', 'proposto_tipo_citazione': 'descrittiva'},
    'c__a__5': {'proposto_rete': 'lessicale'},
    'c__a__6': {'proposto_rete': 'semantica'},
    'c__a__7': {'proposto_rete': 'lessicale', 'esito': 'confermata'},
    'c__a__8': {'proposto_rete': 'lessicale', 'proposto_note': 'DeepSeek, due letture: a / b.'},
}


def _radice_tipo(tmp: Path, caso: str, etichetta: str) -> Path:
    r = tmp / 'radice'
    (r / 'training').mkdir(parents=True)
    suf = f'_{etichetta}' if etichetta else ''
    with open(r / 'training' / f'lessicali_{caso}_deepseek{suf}.jsonl', 'w', encoding='utf-8') as f:
        for i, x in LETTURE.items():
            f.write(json.dumps({'id': i.replace('c__', f'{caso}__'), **x}, ensure_ascii=False) + '\n')
    return r


def _righe(caso: str) -> dict[str, dict[str, Any]]:
    return {i.replace('c__', f'{caso}__'): dict(r, caso_citato=caso) for i, r in RIGHE.items()}


@richiede_campione
@pytest.mark.parametrize('caso', ['urgenda', 'neubauer'])
@pytest.mark.parametrize('sovrascrivi', [False, True])
@pytest.mark.parametrize('scrivi', [False, True])
def test_tipo_come_carica_lessicali(vivi, monkeypatch, tmp_path, caso, sovrascrivi, scrivi) -> None:
    etichetta = 'v2' if caso == 'urgenda' else ''
    r = _radice_tipo(tmp_path, caso, etichetta)
    cl = vivi('carica_lessicali')
    vivo = finto_firestore.installa(monkeypatch, {'corpus_rows': _righe(caso)})
    monkeypatch.setattr(cl, 'QUI', r)
    argv = ['carica_lessicali.py', '--caso', caso, '--etichetta', etichetta]
    argv += ['--sovrascrivi'] * sovrascrivi + ['--scrivi'] * scrivi
    monkeypatch.setattr(sys, 'argv', argv)
    out = io.StringIO()
    with redirect_stdout(out):
        cl.main()
    banca = BancaDatiMemoria({'corpus_rows': _righe(caso)})
    righe: list[str] = []
    CaricatoreTipo(
        Config(radice=r), caso, banca, etichetta=etichetta, sovrascrivi=sovrascrivi, scrivi=scrivi, stampa=righe.append
    ).esegui()
    assert banca.scritture == vivo.scritture
    assert '\n'.join(righe) + '\n' == out.getvalue()
    if scrivi:
        assert banca.scritture, 'the synthetic rows produce writes'


def test_note_e_lettore() -> None:
    assert CaricatoreTipo.note_senza_deepseek('a\nDeepSeek, due letture: x.\nb') == 'a\nb'
    assert versione_codebook({'codebook': '0.5'}) == '0.5'
    assert versione_codebook({'data': '2026-10-02'}) == '0.4-pilot'
    assert versione_codebook({'data': '2026-10-01'}) == '0.3-pilot'


class _Lotti(BancaDatiMemoria):
    """Records the size of every committed batch."""

    def __init__(self, *a: Any, **k: Any) -> None:
        super().__init__(*a, **k)
        self.lotti: list[int] = []

    def _applica(self, scritture: list[Any]) -> None:
        self.lotti.append(len(scritture))
        super()._applica(scritture)


def test_lotti_da_400_nell_ordine(tmp_path) -> None:
    r = tmp_path / 'radice'
    (r / 'training').mkdir(parents=True)
    ids = [f'urgenda__d__{i:04d}' for i in range(905)]
    with open(r / 'training' / 'lessicali_urgenda_deepseek_v2.jsonl', 'w', encoding='utf-8') as f:
        for i in ids:
            f.write(json.dumps({'id': i, 'letture': [{'tipo_citazione': 'descrittiva'}] * 2}) + '\n')
    banca = _Lotti({'corpus_rows': {i: {'caso_citato': 'urgenda', 'proposto_rete': 'lessicale'} for i in ids}})
    e = CaricatoreTipo(Config(radice=r), 'urgenda', banca, scrivi=True, stampa=lambda s: None).esegui()
    assert banca.lotti == [400, 400, 105]
    assert [x['doc_id'] for x in banca.scritture] == ids and e.scritte == 905
    assert {(x['op'], x['via']) for x in banca.scritture} == {('update', 'lotto')}


# the harness: step 09 (type of the "rif" readings) on the sample


@richiede_attesi
@pytest.mark.parametrize('caso', CASI)
def test_passo_09_del_banco(tmp_path, caso) -> None:
    r = tmp_path / 'radice'
    (r / 'training').mkdir(parents=True)
    rel = f'training/lessicali_{caso}_deepseek_rif.jsonl'
    with open(r / rel, 'w', encoding='utf-8') as f:
        for x in attesi_jsonl(attesi_file(f'05_classifica_leggi_{caso}', rel)):
            f.write(json.dumps(x, ensure_ascii=False) + '\n')
    fixture = json.loads((CAMPIONE / 'fixture' / 'corpus_rows.json').read_text(encoding='utf-8'))
    banca = BancaDatiMemoria({'corpus_rows': fixture})
    righe: list[str] = []
    CaricatoreTipo(
        Config(radice=r), caso, banca, etichetta='rif', sovrascrivi=True, scrivi=True, stampa=righe.append
    ).esegui()
    attese = attesi_jsonl(ATTESI / f'09_carica_lessicali_rif_{caso}' / 'firestore_scritture.jsonl')
    assert [json.loads(json.dumps(x, sort_keys=True)) for x in banca.scritture] == attese
    assert '\n'.join(righe) + '\n' == (ATTESI / f'09_carica_lessicali_rif_{caso}' / 'stdout.txt').read_text()


# the ripresa loader against the live one, on the sample files as they are


@pytest.fixture
def ripresa_viva(vivi, monkeypatch):
    cr = vivi('carica_ripresa')
    monkeypatch.setattr(cr, 'CODICI_RUN', dict(cr.CODICI_RUN))
    monkeypatch.setattr(cr, 'PRINCIPI_TESTO', {})
    return cr


@richiede_campione
@pytest.mark.parametrize('caso', CASI)
def test_ripresa_come_carica_ripresa(ripresa_viva, monkeypatch, tmp_path, caso) -> None:
    fixture = json.loads((CAMPIONE / 'fixture' / 'corpus_rows.json').read_text(encoding='utf-8'))
    vivo = finto_firestore.installa(monkeypatch, {'corpus_rows': copy.deepcopy(fixture)})
    sv, sp = tmp_path / 'vivo.json', tmp_path / 'nuovo.json'
    monkeypatch.setattr(
        sys, 'argv', ['carica_ripresa.py', '--caso', caso, '--principi-da-l04', '--scrivi', '--salva', str(sv)]
    )
    out = io.StringIO()
    with redirect_stdout(out):
        ripresa_viva.main()
    banca = BancaDatiMemoria({'corpus_rows': fixture})
    righe: list[str] = []
    CaricatoreRipresa(
        Config(radice=CAMPIONE),
        caso,
        banca,
        principi_da_l04=True,
        salva=str(sp),
        compat=True,
        scrivi=True,
        stampa=righe.append,
    ).esegui()
    assert banca.scritture == vivo.scritture
    assert '\n'.join(righe).replace(str(sp), str(sv)) + '\n' == out.getvalue()
    assert sp.read_bytes() == sv.read_bytes()


@richiede_campione
def test_ripresa_corretta_e_compat() -> None:
    """compat=False changes only what was fixed: the rule of the pages (R08) and the provenance after a fallback."""
    fixture = json.loads((CAMPIONE / 'fixture' / 'corpus_rows.json').read_text(encoding='utf-8'))
    diverse: dict[str, set[str]] = {}
    for caso in CASI:
        esiti = {}
        for compat in (True, False):
            banca = BancaDatiMemoria({'corpus_rows': fixture})
            c = CaricatoreRipresa(
                Config(radice=CAMPIONE), caso, banca, principi_da_l04=True, compat=compat, stampa=lambda s: None
            )
            esiti[compat] = dict(c.esegui().scritture)
            assert banca.scritture == []  # without scrivi nothing is written
        for rid, vecchia in esiti[True].items():
            nuova = esiti[False][rid]
            for k in vecchia:
                if vecchia[k] != nuova[k]:
                    diverse.setdefault(k, set()).add(rid)
            for v in nuova['proposto_estensione']:
                assert v['scelta']['regola'] == 'R08'
    assert set(diverse) <= {'proposto_estensione', 'provenienza.principi'}


def test_anteprima_senza_scrivere(tmp_path) -> None:
    r = _radice_tipo(tmp_path, 'neubauer', '')
    banca = BancaDatiMemoria({'corpus_rows': _righe('neubauer')})
    righe: list[str] = []
    e = CaricatoreTipo(Config(radice=r), 'neubauer', banca, etichetta='', stampa=righe.append).esegui()
    assert e.scritture and banca.scritture == [] and righe[-1] == 'ANTEPRIMA: niente scritto'


# R11 (02/10/2026): the type by majority, written also over an earlier proposal; never on a judged row


def test_tipo_r11(tmp_path) -> None:
    r = tmp_path / 'radice'
    (r / 'training').mkdir(parents=True)
    letture = {
        'neubauer__a__1': ['sostanziale', 'sostanziale', 'descrittiva', 'sostanziale', 'critica'],
        'neubauer__a__2': ['critica', 'descrittiva', 'descrittiva', 'critica', 'implicita'],
        'neubauer__a__4': ['descrittiva'] * 5,
        'neubauer__a__7': ['sostanziale'] * 5,
        'neubauer__a__8': [None] * 5,
    }
    with open(r / 'training' / 'lessicali_neubauer_deepseek_cinque.jsonl', 'w', encoding='utf-8') as f:
        for i, t in letture.items():
            x = {
                'id': i,
                'data': '2026-10-03',
                'codebook': '0.4-pilot',
                'letture': [{'tipo_citazione': y, 'motivo': 'm'} for y in t],
            }
            f.write(json.dumps(x) + '\n')
    banca = BancaDatiMemoria({'corpus_rows': _righe('neubauer')})
    e = CaricatoreTipo(
        Config(radice=r), 'neubauer', banca, etichetta='cinque', composizione='R11', stampa=lambda s: None, scrivi=True
    ).esegui()
    campi = dict(e.scritture)
    assert set(campi) == {'neubauer__a__1', 'neubauer__a__2', 'neubauer__a__4'}
    assert campi['neubauer__a__1']['proposto_tipo_citazione'] == 'sostanziale'
    assert campi['neubauer__a__1']['proposto_confidenza'] == 'alta'
    assert campi['neubauer__a__1']['proposto_tipo_voti'] == {
        'sostanziale': '3/5',
        'descrittiva': '1/5',
        'critica': '1/5',
    }
    assert (
        campi['neubauer__a__1']['proposto_note'] == 'nota mia\naltra\nDeepSeek, letture a maggioranza (5): '
        'sostanziale 3/5, descrittiva 1/5, critica 1/5. Motivo: m'
    )
    # 2-2-1: the first tied type in reading order, uncertain
    assert campi['neubauer__a__2']['proposto_tipo_citazione'] == 'critica'
    assert (
        campi['neubauer__a__2']['proposto_tipo_incerto'] and campi['neubauer__a__2']['proposto_confidenza'] == 'bassa'
    )
    assert 'parita' in campi['neubauer__a__2']['proposto_note']
    # an earlier proposed type is replaced; the judged row 7 and the row without valid readings 8 are not touched
    assert (
        campi['neubauer__a__4']['proposto_lettore']
        == 'DeepSeek V4 Flash 0731, codebook 0.4-pilot, 03/10/2026, 5 letture a maggioranza (R11)'
    )
    assert e.conti['gia giudicata (non toccata)'] == 1 and e.conti['nessuna lettura valida (non toccata)'] == 1
    assert e.conti['tipo cambiato'] == 0 and e.scritte == 3
