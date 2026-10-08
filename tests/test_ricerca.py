"""The search by name and the merge with the platform: same CSV, discards, instructions, report, writes and screen
lines as ``cerca.py --solo-lessicale`` and ``unisci_e_aggiungi.py``, run on a small root under ``tmp_path``."""

from __future__ import annotations

import io
import json
import re
import shutil
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import finto_firestore
import pytest
from conftest import CAMPIONE, richiede_campione
from schermo_en import in_inglese

from tracepipe.banca import BancaDatiMemoria
from tracepipe.config import Config
from tracepipe.dimensioni import PosizioneNelPdf, dimensioni
from tracepipe.ricerca import (
    RicercaPerNome,
    UnioneRighe,
    blocco_pagina,
    documento_riga,
    e_nome,
    fondi,
    front_matter,
    id_riga,
    leggi_caso,
    modello_forme,
    segni_pagina,
)

pytestmark = richiede_campione
DURATA = re.compile(r'(?<![\w.])\d+(?:\.\d+)?s(?![\w])')
CARTELLE = 9  # case folders of the sample markdown copied into the small root (Korean OCR documents included)

SINTETICO = """---
case_id: 'caso-sintetico'
case_name: 'Caso sintetico'
document_id: 'sintetico_0001'
tipo_atto: 'decisione'
data_deposito: '2020-01-01'
url_origine: 'https://x/2020/20200105_doc.pdf'
---
<!-- page 1 -->
The applicants argue that the Urgenda Foundation v. State of the Netherlands judgment (ECLI:NL:RBDHA:2015:7145)
applies here, as the court held in its reasoning on the duty of care owed to residents, a duty which was then
confirmed on appeal and later by the supreme court.
<!-- page 2 -->
Reasons. Much later the court returns to Urgenda once more, on the remaining budget.
"""


@pytest.fixture(scope='module')
def radice(tmp_path_factory: pytest.TempPathFactory) -> Path:
    r = tmp_path_factory.mktemp('ricerca')
    for d in ('cited-cases', 'codebook'):
        (r / d).symlink_to(CAMPIONE / d)
    (r / 'training').mkdir()
    (r / 'training' / 'ocr').symlink_to(CAMPIONE / 'training' / 'ocr')
    (r / 'index').mkdir()
    cartelle = sorted(p.name for p in (CAMPIONE / 'markdown').iterdir() if p.is_dir())[:CARTELLE]
    for c in cartelle:
        shutil.copytree(CAMPIONE / 'markdown' / c, r / 'markdown' / c)
        if (CAMPIONE / 'documents' / c).exists():
            (r / 'documents').mkdir(exist_ok=True)
            (r / 'documents' / c).symlink_to(CAMPIONE / 'documents' / c)
    (r / 'markdown' / 'sintetico').mkdir()
    (r / 'markdown' / 'sintetico' / 'sintetico_0001.md').write_text(SINTETICO, encoding='utf-8')
    return r


def _cerca_vivo(vivi, monkeypatch, radice: Path, argv: list[str]) -> tuple[int, str]:
    ce = vivi('cerca')
    monkeypatch.setattr(ce, 'HERE', radice)
    monkeypatch.setattr(ce, 'MD', radice / 'markdown')
    monkeypatch.setattr(ce, 'INDEX', radice / 'index')
    monkeypatch.setattr(sys, 'argv', ['cerca.py', *argv])
    monkeypatch.chdir(radice)
    out = io.StringIO()
    with redirect_stdout(out):
        codice = ce.main()
    return codice, out.getvalue()


def _cerca(radice: Path, monkeypatch, caso: str, uscita: str, **kw: Any) -> tuple[int, str]:
    monkeypatch.chdir(radice)
    righe: list[str] = []
    e = RicercaPerNome(Config(radice=radice), caso, uscita=uscita, stampa=righe.append, **kw).esegui()
    return e.codice, '\n'.join(righe) + '\n'


@pytest.mark.parametrize('caso', ['urgenda', 'neubauer', 'klimaseniorinnen', 'idh-oc-32-25'])
def test_ricerca_come_cerca(vivi, monkeypatch, radice, caso) -> None:
    caso_arg = f'cited-cases/{caso}.yaml'
    cv, ov = _cerca_vivo(
        vivi, monkeypatch, radice, ['--caso', caso_arg, '--solo-lessicale', '--uscita', f'index/v_{caso}.csv']
    )
    cp, op = _cerca(radice, monkeypatch, caso_arg, f'index/p_{caso}.csv')
    assert cp == cv
    norm = lambda t: DURATA.sub('Ns', t).replace(f'/p_{caso}.', '/v_{caso}.'.replace('{caso}', caso))  # noqa: E731
    assert norm(op) == DURATA.sub('Ns', in_inglese(ov))
    for suf in ('.csv', '.SCARTI.csv', '.ISTRUZIONI.md'):
        v, p = radice / 'index' / f'v_{caso}{suf}', radice / 'index' / f'p_{caso}{suf}'
        assert v.exists() == p.exists(), suf
        if v.exists():
            vivo = v.read_bytes()
            if suf == '.ISTRUZIONI.md':   # the header of the file is in English in the package (06/10/2026)
                intestazioni = (
                    ('# Come classificare — codebook', '# How to classify: codebook'),
                    ('Caso citato:', 'Cited case:'),
                    ('Righe da classificare:', 'Rows to classify:'),
                    ('Categorie e casi limite:', 'Categories and borderline cases:'),
                )
                for it, en in intestazioni:
                    vivo = vivo.replace(it.encode(), en.encode())
            assert p.read_bytes() == vivo, suf


def test_ricerca_rifiuta_la_rete_semantica() -> None:
    with pytest.raises(NotImplementedError):
        RicercaPerNome(Config(radice=Path('/x')), 'urgenda', solo_lessicale=False)


def test_caso_che_non_esiste(radice, monkeypatch) -> None:
    codice, out = _cerca(radice, monkeypatch, 'nessuno', 'index/x.csv')
    assert codice == 1 and out.startswith('Cited case not found: nessuno\nAvailable: ')


def test_pezzi_come_cerca(vivi, radice) -> None:
    ce = vivi('cerca')
    conf = leggi_caso(radice / 'cited-cases' / 'urgenda.yaml')
    assert conf == ce.leggi_caso(radice / 'cited-cases' / 'urgenda.yaml')
    assert leggi_caso(radice / 'cited-cases' / 'neubauer-P05.yaml', True) == ce.leggi_caso(
        radice / 'cited-cases' / 'neubauer-P05.yaml', True
    )
    patt = modello_forme(conf['forme'])
    for md in sorted((radice / 'markdown').rglob('*.md')):
        testo = md.read_text(encoding='utf-8', errors='replace')
        meta, inizio = front_matter(testo)
        assert (meta, inizio) == ce.front_matter(testo)
        ms = list(patt.finditer(testo, inizio))
        assert [[m[0].start(), m[1], m[2]] for m in fondi(testo, ms)] == [
            [m[0].start(), m[1], m[2]] for m in ce.fondi(testo, ms)
        ]
        assert [e_nome(testo, m) for m in ms] == [ce.e_nome(testo, m) for m in ms]
        marks = segni_pagina(testo)
        for m in ms[:40]:
            blocco, off = blocco_pagina(testo, marks, m.start())
            assert (blocco, off) == ce.blocco_pagina(testo, marks, m.start())
            assert dimensioni(meta, blocco, off, testo[: m.start()]) == ce.calcola_dimensioni(
                meta, blocco, off, testo[: m.start()]
            )


def test_posizione_nel_pdf_come_dimensioni(vivi, radice) -> None:
    di = vivi('dimensioni')
    pdf = sorted((radice / 'documents').rglob('*.pdf'))[:4]
    with PosizioneNelPdf() as nuovo:
        for p in pdf:
            for n in (1, 2, 3, 99):
                for ago in ('the court', 'Urgenda Foundation v. State of the Netherlands, ECLI', 'x' * 30):
                    assert nuovo.posizione(p, n, ago) == di.posizione(p, n, ago)
    di.chiudi_pdf()


def test_riga_e_documento_come_pubblica(vivi) -> None:
    pu = vivi('pubblica')
    r = {
        'pagina': '3',
        'char_start': '120',
        'rete': 'lessicale',
        'file': 'markdown/a/b.md',
        'copie': '2',
        'anteriore': 'si',
        'punteggio': '0.5',
        'confidenza': 'bassa',
        'annidata': 'True',
    }
    assert documento_riga(r, 'urgenda') == pu.documento(r, 'urgenda')
    assert documento_riga({}, 'urgenda', 'x') == pu.documento({}, 'urgenda', 'x')
    assert id_riga('urgenda', 'a b/c', 12) == pu.id_riga('urgenda', 'a b/c', 12)


# the merge


def _righe_piattaforma(radice: Path, caso: str) -> dict[str, dict[str, Any]]:
    fixture = json.loads((CAMPIONE / 'fixture' / 'corpus_rows.json').read_text(encoding='utf-8'))
    docs = {
        front_matter(p.read_text(encoding='utf-8'))[0].get('document_id') for p in (radice / 'markdown').rglob('*.md')
    }
    out = {i: r for i, r in fixture.items() if r.get('caso_citato') == caso and r.get('document_id') in docs}
    if caso == 'urgenda':
        testo = SINTETICO
        nome, ecli = testo.index('Urgenda Foundation v.'), testo.index('ECLI:NL')
        base = {
            'caso_citato': 'urgenda',
            'document_id': 'sintetico_0001',
            'file': 'markdown/sintetico/sintetico_0001.md',
            'proposto_rete': 'lessicale',
            'assegnato_a': 'persona@x',
        }
        out[f'urgenda__sintetico_0001__{nome}'] = dict(base, char_start=nome, codice='URG-0900')
        out[f'urgenda__sintetico_0001__{ecli}'] = dict(base, char_start=ecli, codice='URG-0901', esito='confermata')
        out['urgenda__sparito__1'] = dict(base, document_id='sparito', file='markdown/x/sparito.md', char_start=1)
    return out


@pytest.mark.parametrize('caso', ['urgenda', 'neubauer'])
@pytest.mark.parametrize('scrivi', [False, True])
def test_unione_come_unisci(vivi, monkeypatch, radice, caso, scrivi) -> None:
    data = '2026-10-02'
    # the search to compare, made by the package (equal to the live one: test above)
    _cerca(radice, monkeypatch, f'cited-cases/{caso}.yaml', f'index/nomi_{caso}_{data}b.csv')
    un, po = vivi('unisci_e_aggiungi'), vivi('posizione_dopo_ocr')
    monkeypatch.setattr(un, 'QUI', radice)
    monkeypatch.setattr(po, 'QUI', radice)
    monkeypatch.setattr(po, 'PRIMA', radice / 'training' / 'ocr' / 'prima')
    righe = _righe_piattaforma(radice, caso)
    vivo = finto_firestore.installa(monkeypatch, {'corpus_rows': righe})
    monkeypatch.setattr(sys, 'argv', ['unisci_e_aggiungi.py', '--caso', caso, '--data', data] + ['--scrivi'] * scrivi)
    out = io.StringIO()
    with redirect_stdout(out):
        un.main()
    rapporto_vivo = (radice / 'training' / f'nomi_unisci_aggiungi_{data}.json').read_bytes()
    banca = BancaDatiMemoria({'corpus_rows': righe})
    stampa: list[str] = []
    UnioneRighe(Config(radice=radice), banca, data=data, casi=[caso], scrivi=scrivi, stampa=stampa.append).esegui()
    assert '\n'.join(stampa) + '\n' == in_inglese(out.getvalue())
    assert (radice / 'training' / f'nomi_unisci_aggiungi_{data}.json').read_bytes() == rapporto_vivo
    assert banca.scritture == vivo.scritture
    if caso == 'urgenda':
        r = json.loads(rapporto_vivo)['urgenda']
        assert ['URG-0901', ['URG-0900']] in r['unite']  # the judged row stays, the name row is merged into it
        assert r['aggiunte'] and None in r['orfane']  # the second mention is added; the row without file stays
    if scrivi:
        assert {x['op'] for x in banca.scritture} >= {'create', 'set'}


# the deduplication per document (03/10/2026, external review; not in use)


def _righe_dedup() -> list[dict[str, Any]]:
    testo = 'The court followed Urgenda   on the duty of care. ' * 3
    return [
        {'document_id': 'a', 'char_start': 10, 'citazione_testuale': testo},
        {'document_id': 'a', 'char_start': 900, 'citazione_testuale': testo.upper()},  # same document: a copy
        {'document_id': 'b', 'char_start': 40, 'citazione_testuale': ' ' + testo},  # another filing: kept, linked
        {'document_id': 'c', 'char_start': 5, 'citazione_testuale': 'another passage on Urgenda'},
        {'document_id': 'b', 'char_start': 70, 'citazione_testuale': testo},  # copy inside b
    ]


def test_deduplica_su_tutto_il_corpus_come_prima() -> None:
    from tracepipe.ricerca import deduplica

    scarti: list[dict[str, Any]] = []
    tenute = deduplica(_righe_dedup(), scarti)
    assert [(r['document_id'], r['char_start']) for r in tenute] == [('a', 10), ('c', 5)]
    assert tenute[0]['copie'] == 4 and len(scarti) == 3 and all('stesso_testo_di' not in r for r in tenute)


def test_deduplica_per_atto() -> None:
    from tracepipe.ricerca import deduplica

    scarti: list[dict[str, Any]] = []
    tenute = deduplica(_righe_dedup(), scarti, per_atto=True)
    assert [(r['document_id'], r['char_start'], r['stesso_testo_di'], r['copie']) for r in tenute] == [
        ('a', 10, '', 2),
        ('b', 40, 'a__10', 2),
        ('c', 5, '', 1),
    ]
    assert [(r['document_id'], r['char_start'], r['motivo_scarto']) for r in scarti] == [
        ('a', 900, 'copia di un altro frammento'),
        ('b', 70, 'copia di un altro frammento'),
    ]


def test_deduplica_per_atto_come_la_copia_viva(vivi_oggi, monkeypatch) -> None:
    import copy
    import random

    from tracepipe.ricerca import deduplica

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parent.parent / 'tools'))  # its sibling `dimensioni`
    viva = vivi_oggi('cerca_s05_per_atto')
    rnd = random.Random(1003)
    testi = ['Urgenda held x', 'urgenda   HELD x', 'Neubauer said y', 'z' * 500, 'z' * 400 + 'w']
    for _ in range(200):
        righe = [
            {'document_id': rnd.choice('abc'), 'char_start': k, 'citazione_testuale': rnd.choice(testi)}
            for k in range(rnd.randint(0, 12))
        ]
        sv: list[dict[str, Any]] = []
        sp: list[dict[str, Any]] = []
        assert viva.deduplica(copy.deepcopy(righe), sv) == deduplica(copy.deepcopy(righe), sp, per_atto=True)
        assert sv == sp
