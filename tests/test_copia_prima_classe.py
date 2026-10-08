"""The copy kept before a write (``copia_prima``) and what the clean-up steps share about a row (``righe``)."""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from tracepipe.copia_prima import CopiaNonRiuscitaError, CopiaPrima
from tracepipe.righe import (
    LettoreAtti,
    e_viva,
    giudicata,
    giudizio,
    normalizza,
    pagina_di_riga,
    posizione_di_riga,
    principi_di,
)

ORA = datetime.datetime(2026, 10, 5, 7, 1, 2)


def copia(tmp_path: Path) -> CopiaPrima:
    return CopiaPrima(tmp_path, cartella=tmp_path / 'copie', orologio=lambda: ORA, stampa=lambda t: None)


def test_tiene_i_campi_proposti_la_provenienza_e_quello_che_la_scrittura_tocca() -> None:
    riga = {
        'proposto_rete': 'lessicale',
        'proposto_x': 1,
        'codice': 'A',
        'provenienza': {'tipo': 'L03'},
        'altro': 5,
        'nota': 'n',
    }
    tenere, assenti = CopiaPrima.campi_di(riga, ['nota', 'provenienza.tipo', 'esclusa_da', 'esclusa_da'])
    assert tenere == {
        'proposto_rete': 'lessicale',
        'proposto_x': 1,
        'codice': 'A',
        'provenienza': {'tipo': 'L03'},
        'nota': 'n',
    }
    assert assenti == ['esclusa_da'] and 'altro' not in tenere
    assert CopiaPrima.campi_di(None, ['x']) == ({}, ['x'])


def test_salva_e_rilegge(tmp_path: Path) -> None:
    prima = {'r1': {'proposto_rete': 'lessicale', 'codice': 'U-1'}}
    p = copia(tmp_path).salva(
        'unisci_c03', 'tutti', prima, {'r1': {'esclusa_da': 'x'}, 'r2': {'c03_da': 'x'}}, 'esclusioni'
    )
    assert p.name == 'prima_unisci_c03_tutti_2026-10-05_070102.json.gz'
    d = CopiaPrima.leggi(p)
    assert d['n_righe'] == 2 and d['campi_scritti'] == ['c03_da', 'esclusa_da']
    assert d['righe']['r1'] == {'prima': prima['r1'], 'assenti': ['esclusa_da'], 'riga_letta': True}
    assert d['righe']['r2'] == {'prima': {}, 'assenti': ['c03_da'], 'riga_letta': False}


def test_due_copie_nello_stesso_secondo_non_si_sovrascrivono(tmp_path: Path) -> None:
    c = copia(tmp_path)
    a = c.salva('p', 'tutti', {}, {'r': {'x': 1}})
    b = c.salva('p', 'tutti', {}, {'r': {'x': 1}})
    assert a != b and b.name.endswith('_2.json.gz') and a.exists() and b.exists()


def test_se_la_copia_non_si_scrive_niente_si_scrive(tmp_path: Path) -> None:
    (tmp_path / 'copie').write_text('un file al posto della cartella', encoding='utf-8')
    with pytest.raises(CopiaNonRiuscitaError, match='nothing written'):
        copia(tmp_path).salva('p', 'tutti', {}, {'r': {'x': 1}})


def test_sotto_pytest_senza_cartella_la_copia_va_in_una_cartella_temporanea(tmp_path: Path) -> None:
    p = CopiaPrima(tmp_path, orologio=lambda: ORA, stampa=lambda t: None).salva(
        'p', 'prova_cartella', {}, {'r': {'x': 1}}
    )
    assert tmp_path not in p.parents and 'trace_copie_prima_prove' in str(p)
    p.unlink()


def test_la_variabile_di_ambiente_sostituisce_la_cartella(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('TRACE_COPIE_PRIMA_CARTELLA', str(tmp_path / 'altrove'))
    p = CopiaPrima(tmp_path, orologio=lambda: ORA, stampa=lambda t: None).salva('p', 'c', {}, {'r': {'x': 1}})
    assert p.parent == tmp_path / 'altrove'


def test_normalizza() -> None:
    assert normalizza('  The  Court, held: “X”!  ') == 'the court held x'
    assert normalizza(None) == '' and normalizza('\uff35\uff52\uff47\uff45\uff4e\uff44\uff41') == 'urgenda'


def test_giudizio_e_principi_e_pagina() -> None:
    assert giudicata({'esito': 'confermata'}) and giudicata({'settembre': {'x': 1}}) and not giudicata({})
    assert (
        giudizio({'esito': 'scartata'}) == 'scartata'
        and giudizio({'settembre': True}) == 'settembre'
        and giudizio({}) == ''
    )
    assert principi_di({'validato_principi': ['a'], 'proposto_principi': ['b', 'nessuno']}) == {'a', 'b'}
    assert pagina_di_riga({'validato_pagina': 'x', 'proposto_pagina': 4, 'pagina': 9}) == 4
    assert pagina_di_riga({'pagina': '9'}) == 9 and pagina_di_riga({}) is None
    assert posizione_di_riga({'char_start': '12'}) == 12 and posizione_di_riga({'char_start': None}) is None
    assert e_viva({'proposto_rete': 'descrittiva'}) and not e_viva({'proposto_rete': 'esclusa'})


def test_il_lettore_degli_atti_legge_una_volta_e_non_si_arrabbia_se_manca(tmp_path: Path) -> None:
    (tmp_path / 'a.md').write_text('testo', encoding='utf-8')
    atti = LettoreAtti(tmp_path)
    assert atti.testo('a.md') == 'testo' and atti.testo('manca.md') == ''
    (tmp_path / 'a.md').write_text('cambiato', encoding='utf-8')
    assert atti.testo('a.md') == 'testo'  # kept
