"""The synthetic example (``examples/synthetic``): an invented cited case and invented filings on which the name search
and the compositions R11 to R16 run without private data, network, GPU or Firestore."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from tracepipe.cli import main

RADICE = Path(__file__).resolve().parent.parent
POSTI = (
    RADICE / 'examples' / 'synthetic',
    RADICE / 'pubblicazione' / 'trace-0.1' / 'vetrina' / 'examples' / 'synthetic',
)
ESEMPIO = next((p for p in POSTI if (p / 'rows.json').exists()), None)
pytestmark = pytest.mark.skipif(ESEMPIO is None, reason='the synthetic example is not in this checkout')

CASO = 'example-foundation'
A1 = f'{CASO}__northfield-v-caldera-judgment_a1b2__1060'  # body citation, page 3 follows with an invented ending
A2 = f'{CASO}__northfield-v-caldera-judgment_a1b2__2338'  # footnote, court_order in 2 of 5 readings
B1 = f'{CASO}__coastal-youth-v-meridia-petition_c3d4__687'  # chain mention, five empty principle lists
B2 = f'{CASO}__coastal-youth-v-meridia-petition_c3d4__1322'  # footnote, summarised sentence in the readings
PROVA_VERA = (
    'The duty of care owed by the Republic to its residents requires it to take reasonable and timely measures '
    'against a known and serious risk.'
)


def componi(regola: str, tmp_path: Path) -> dict[str, dict]:
    uscita = tmp_path / f'{regola}.json'
    codice = main(
        [
            *['--radice', str(ESEMPIO), '--senza-giornale', 'carica', 'ripresa', '--caso', CASO],
            *['--composizione', regola, '--etichetta', 'cinque', '--fotografia', str(ESEMPIO / 'rows.json')],
            *['--salva', str(uscita)],
        ]
    )
    assert codice == 0
    return json.loads(uscita.read_text(encoding='utf-8'))


def test_ricerca_per_nome(tmp_path: Path) -> None:
    uscita = tmp_path / 'candidati.csv'
    pytest.importorskip('fitz')
    assert main(['--radice', str(ESEMPIO), '--senza-giornale', 'cerca', '--caso', CASO, '--solo-lessicale',
                 '--uscita', str(uscita)]) == 0  # fmt: skip
    righe = list(csv.DictReader(uscita.open(encoding='utf-8')))
    trovate = {f'{CASO}__{r["document_id"]}__{r["char_start"]}': r for r in righe}
    assert set(trovate) == {A1, A2, B1, B2}
    assert set(trovate) == set(json.loads((ESEMPIO / 'rows.json').read_text(encoding='utf-8')))
    # the name and the identifier within 200 characters are one citation
    assert trovate[A2]['forma_trovata'] == 'Example Foundation + EX:SC:2019:88'
    assert {r['pagina'] for r in righe} == {'1', '2', '4'}  # page 3 develops the principle but does not name it


def test_fotografia_non_scrive() -> None:
    with pytest.raises(SystemExit):
        main(['--radice', str(ESEMPIO), '--senza-giornale', 'carica', 'ripresa', '--caso', CASO, '--composizione',
              'R11', '--etichetta', 'cinque', '--fotografia', str(ESEMPIO / 'rows.json'), '--scrivi'])  # fmt: skip


def test_r11_e_r12(tmp_path: Path) -> None:
    r11, r12 = componi('R11', tmp_path), componi('R12', tmp_path)
    assert r11[A2]['proposto_principi'] == ['own_share']
    assert r11[A2]['proposto_incerta'] is False
    assert r12[A2]['proposto_principi'] == ['own_share', 'court_order']
    assert r12[A2]['proposto_principi_voti']['court_order'] == '2/5'
    assert r12[A2]['proposto_incerta'] is True
    # five empty lists are not an answer before R13: the row is not touched
    assert B1 not in r11 and B1 not in r12
    assert r11[A1]['proposto_principi'] == ['own_share', 'duty_of_care']


def test_r13_elenco_vuoto(tmp_path: Path) -> None:
    r13 = componi('R13', tmp_path)
    assert r13[B1]['proposto_principi'] == ['nessuno']


def test_r15_frase_dal_testo(tmp_path: Path) -> None:
    r15 = componi('R15', tmp_path)
    assert r15[B2]['proposto_frase_lettura_esito'] == 'non trovata'
    assert r15[B2]['proposto_frase_metodo'] == 'nota→corpo'
    assert r15[B2]['proposto_frase_sostenuta'] == (
        'Such knowledge gives rise to a duty to act with reasonable care and without delay against the risk to the '
        'petitioners.'
    )
    assert r15[A1]['proposto_frase_metodo'] == 'corpo'
    assert r15[A1]['proposto_frase_esito'] == 'trovata'


def test_r16_ripara_la_prova(tmp_path: Path) -> None:
    pagina = {r: {v['pagina']: v for v in c[A1]['proposto_estensione']} for r, c in
              (('R14', componi('R14', tmp_path)), ('R16', componi('R16', tmp_path)))}  # fmt: skip
    prima, dopo = pagina['R14'][3], pagina['R16'][3]
    assert prima['prova_esito'] == 'trovata' and prima['prova'].endswith('coal power.')
    assert dopo['prova_riparata'] is True
    assert dopo['prova'] == PROVA_VERA
    assert dopo['prova_modello'].endswith('including an immediate ban on all coal power.')
    assert dopo['prosegue'] is True
