"""S08, the writer of the pair decisions (tools/scrivi_s08.py): merges as C03 did, the hand review of C03 wins, the team's
judgment is never altered, the «team» pairs reach To review through the fields and the collection the platform already has.

Synthetic rows only: nothing here reads or writes the platform. Skipped when ``tools/`` is not there (public repository).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parent.parent / 'tools'
if not (TOOLS / 'scrivi_s08.py').exists():
    pytest.skip('tools/ is not in this repository', allow_module_level=True)
sys.path.insert(0, str(TOOLS))
import scrivi_s08 as S  # noqa: E402


def riga(codice, cs, **kw):
    r = {'codice': codice, 'caso_citato': 'neubauer', 'document_id': 'doc1', 'case_id': 'c1', 'case_name': 'Case 1',
         'proposto_rete': 'lessicale', 'char_start': cs, 'proposto_pagina': 3, 'file': 'markdown/doc1.md',
         'assegnato_a': 'uid-coder', 'proposto_citazione_testuale': f'text of {codice}, para. 12'}
    r.update(kw)
    return r


def banca():
    return {
        'n__doc1__100': riga('NEU-0001', 100, proposto_paragrafi=['12'],
                             proposto_nota_appoggio=[{'codice': 'NEU-0090', 'testo': 'old', 'paragrafi': []}]),
        'n__doc1__900': riga('NEU-0002', 900, proposto_paragrafi=['13']),
        'n__doc1__2000': riga('NEU-0003', 2000),
        'n__doc1__2500': riga('NEU-0004', 2500, esito='confermata', validato_da='uid-judge'),
        'n__doc1__4000': riga('NEU-0005', 4000),
        'n__doc1__4100': riga('NEU-0006', 4100),
        'n__doc1__6000': riga('NEU-0007', 6000),
        'n__doc1__6200': riga('NEU-0008', 6200, proposto_rete='esclusa', esclusa_regola='C03', unita_a='NEU-0007'),
        'n__doc1__8000': riga('NEU-0009', 8000),
        'n__doc1__8100': riga('NEU-0010', 8100),
    }


def dec(a, b, esito, tiene='', esce='', motivo='m'):
    return {'id': f'{a}__{b}', 'esito': esito, 'motivo': motivo, 'tiene': tiene, 'esce': esce, 'codice_a': a, 'codice_b': b}


def piano(decisioni, mano=None, b=None):
    return S.Piano(b or banca(), decisioni, {}, mano or {}).calcola()


def test_una_si_unisce_come_c03_con_la_regola_s08():
    p = piano([dec('NEU-0001', 'NEU-0002', 'una', 'NEU-0001', 'NEU-0002')])
    esce, tenuta = p.righe['n__doc1__900'], p.righe['n__doc1__100']
    assert esce['proposto_rete'] == 'esclusa' and esce['esclusa_regola'] == 'S08' and esce['unita_a'] == 'NEU-0001'
    assert esce['esclusa_rete_prima'] == 'lessicale' and esce['esclusa_motivo'].startswith('S08 ') and 'esclusa_il' in esce
    # l'appoggio si AGGIUNGE a quello di prima (C03), i paragrafi si uniscono
    assert [x['codice'] for x in tenuta['proposto_nota_appoggio']] == ['NEU-0090', 'NEU-0002']
    assert tenuta['proposto_paragrafi'] == ['12', '13']
    assert not p.revisioni


def test_la_revisione_a_mano_di_c03_vince_sempre():
    """N530 (IAC-0047/IAC-0048): la mano dice tenere tutte e due, S08 dice una. Non si unisce, si elenca."""
    mano = {frozenset(('NEU-0001', 'NEU-0002')): ('TENERE TUTTE E DUE', 'NEU-0001+NEU-0002', 'N530')}
    p = piano([dec('NEU-0001', 'NEU-0002', 'una', 'NEU-0001', 'NEU-0002')], mano)
    assert not p.righe and not p.revisioni
    assert p.elenco[0]['mano'] == 'N530' and 'revisione a mano' in p.elenco[0]['perche']
    # una coppia al team che la mano ha gia' deciso non va al team
    p = piano([dec('NEU-0001', 'NEU-0002', 'team')], mano)
    assert not p.righe and not p.revisioni


def test_unire_a_mano_sceglie_la_riga_della_mano():
    mano = {frozenset(('NEU-0001', 'NEU-0002')): ('UNIRE', 'NEU-0002', 'N001')}
    p = piano([dec('NEU-0001', 'NEU-0002', 'una', 'NEU-0001', 'NEU-0002')], mano)
    assert p.righe['n__doc1__100']['unita_a'] == 'NEU-0002'


def test_la_riga_confermata_dal_team_non_esce_mai():
    """deve fallire se la riga confermata viene esclusa: la regola la tiene, e se tutte e due sono giudicate va al team"""
    p = piano([dec('NEU-0003', 'NEU-0004', 'una', 'NEU-0003', 'NEU-0004')])
    assert p.righe['n__doc1__2500'].get('proposto_rete') is None          # la confermata resta
    assert p.righe['n__doc1__2000']['unita_a'] == 'NEU-0004'
    b = banca()
    b['n__doc1__2000'].update(esito='confermata', validato_da='uid-judge2')
    p = piano([dec('NEU-0003', 'NEU-0004', 'una', 'NEU-0003', 'NEU-0004')], b=b)
    assert all(c.get('proposto_rete') != 'esclusa' for c in p.righe.values())
    assert p.elenco[0]['esito_scrittura'] == 'al team'
    assert {v['assegnato_a'] for v in p.revisioni.values()} == {'uid-judge', 'uid-judge2'}
    # i campi del giudizio non si scrivono mai
    assert not any(k in c for c in p.righe.values() for k in ('esito', 'validato_da', 'validato_il', 'settembre'))


def test_gia_unite_righe_morte_e_due_non_scrivono():
    p = piano([dec('NEU-0007', 'NEU-0008', 'una', 'NEU-0007', 'NEU-0008'),
               dec('NEU-0007', 'NEU-0008', 'team'),
               dec('NEU-0009', 'NEU-0010', 'due'),
               dec('NEU-0009', 'NEU-0099', 'una', 'NEU-0009', 'NEU-0099')])
    assert not p.righe and not p.revisioni
    assert [x['perche'] for x in p.elenco][:2] == ["gia' unite", "gia' unite"]
    assert p.elenco[3]['perche'] == "una riga non c'e' piu' in banca"


def test_team_segna_le_due_righe_e_una_richiesta_per_riga():
    p = piano([dec('NEU-0005', 'NEU-0006', 'team'), dec('NEU-0006', 'NEU-0009', 'team')])
    a, b = p.righe['n__doc1__4000'], p.righe['n__doc1__4100']
    assert a['s08_vicina_codice'] == 'NEU-0006' and a['s08_vicina_distanza'] == 100 and a['s08_vicina_id'] == 'n__doc1__4100'
    assert b['s08_vicina_codice'] == 'NEU-0005' and b['s08_coppie_team'] == ['NEU-0005', 'NEU-0009']
    assert len(p.revisioni) == 3                                            # una per riga, mai una per coppia
    v = p.revisioni[S.id_revisione('n__doc1__4100')]
    assert v['categoria'] == 'altro' and v['motivo'] == S.MOTIVO_TEAM and v['stato'] == 'aperta'
    assert v['url'] == '/corpus?riga=NEU-0006' and v['assegnato_a'] == 'uid-coder'
    assert 'NEU-0005 (100 characters away)' in v['dettaglio'] and 'NEU-0009' in v['dettaglio']
    assert S.id_revisione('n__doc1__4100') == S.id_revisione('n__doc1__4100')   # rilanciare non fa doppioni


def test_una_riga_che_esce_non_resta_al_team():
    p = piano([dec('NEU-0005', 'NEU-0006', 'una', 'NEU-0005', 'NEU-0006'), dec('NEU-0006', 'NEU-0009', 'team')])
    assert p.righe['n__doc1__4100']['proposto_rete'] == 'esclusa'
    assert 's08_coppie_team' not in p.righe['n__doc1__4100']
    assert S.id_revisione('n__doc1__4100') not in p.revisioni and S.id_revisione('n__doc1__8000') not in p.revisioni


def test_catena_e_riga_che_esce_una_volta():
    p = piano([dec('NEU-0005', 'NEU-0006', 'una', 'NEU-0005', 'NEU-0006'),
               dec('NEU-0006', 'NEU-0009', 'una', 'NEU-0006', 'NEU-0009'),
               dec('NEU-0010', 'NEU-0006', 'una', 'NEU-0010', 'NEU-0006')])
    assert p.righe['n__doc1__8000']['unita_a'] == 'NEU-0005'              # la catena si chiude sulla riga finale
    assert sum(1 for x in p.elenco if 'esce gia' in x['perche']) == 1


def test_la_rilettura_vede_un_campo_diverso():
    assert S.uguali({'a': 1, 't': '__ORA__'}, {'a': 1, 't': 'x'}) == []
    assert S.uguali({'a': 1, 't': '__ORA__'}, {'a': 2}) == ['a', 't']
    assert S.con_ora({'a': '__ORA__', 'b': 1}, 'ORA') == {'a': 'ORA', 'b': 1}


def test_scrivi_senza_vivo_e_rifiutato(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['scrivi_s08.py', '--decisioni', str(tmp_path), '--banca', 'x', '--scrivi'])
    with pytest.raises(SystemExit, match='--vivo'):
        S.main()


def test_senza_il_secondo_lettore_non_si_scrive(tmp_path, monkeypatch):
    """con il 9B a meta' (07/10: 3.929 coppie su 6.290 al team per un lettore mancante) --scrivi si ferma prima della banca viva"""
    import csv
    import gzip
    import json
    righe = [dec('NEU-0005', 'NEU-0006', 'team', motivo='manca un lettore o tutte le sue letture sono state scartate dai freni'),
             dec('NEU-0009', 'NEU-0010', 'due')]
    with open(tmp_path / 'decisioni_s08.tsv', 'w', newline='', encoding='utf-8') as h:
        w = csv.DictWriter(h, list(righe[0]), delimiter='\t')
        w.writeheader()
        w.writerows(righe)
    with gzip.open(tmp_path / 'b.json.gz', 'wt', encoding='utf-8') as h:
        json.dump(banca(), h)
    monkeypatch.setattr(S, 'db_', lambda: None)
    monkeypatch.setattr(S, 'leggi_vivo', lambda db=None: banca())
    monkeypatch.setattr(S, 'scrivi', lambda *a, **k: pytest.fail('ha scritto'))
    monkeypatch.setattr(sys, 'argv', ['scrivi_s08.py', '--decisioni', str(tmp_path), '--vivo', '--scrivi', '--revisione-c03', 'nessuno'])
    with pytest.raises(SystemExit, match='9B'):
        S.main()
