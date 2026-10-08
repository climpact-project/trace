"""S08, the team's answers read back on the Mac (tools/leggi_risposte_s08.py): every answer exported once, the last answer of
each person counts, «One citation» pairs merged exactly as scrivi_s08.py does, disagreements and judged rows to the PI,
nothing written without --scrivi.

Synthetic rows only: nothing here reads or writes the platform. Skipped when ``tools/`` is not there (public repository).
"""

from __future__ import annotations

import csv
import gzip
import json
import pathlib
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parent.parent / 'tools'
if not (TOOLS / 'leggi_risposte_s08.py').exists():
    pytest.skip('tools/ is not in this repository', allow_module_level=True)
sys.path.insert(0, str(TOOLS))
import leggi_risposte_s08 as L  # noqa: E402


def riga(codice, cs, coppie=(), **kw):
    r = {'codice': codice, 'caso_citato': 'neubauer', 'document_id': 'doc1', 'case_id': 'c1', 'case_name': 'Case 1',
         'proposto_rete': 'lessicale', 'char_start': cs, 'proposto_pagina': 3, 'assegnato_a': 'uid-coder',
         'proposto_citazione_testuale': f'text of {codice}, para. 12', 's08_coppie_team': list(coppie)}
    r.update(kw)
    return r


def voce(con_id, con_codice, risposta, chi, quando, nota=''):
    return {'con_id': con_id, 'con_codice': con_codice, 'risposta': risposta, 'nota': nota, 'chi': chi, 'chi_nome': chi.title(),
            'quando': quando, 'da_riga': 'x'}


def banca():
    """Coppie al team: 1+2 (una, poi Luca ci ripensa: resta una), 3+4 (disaccordo), 5+6 (due), 7+8 (solo incerta),
    9+10 (nessuna risposta), 11+12 (una, ma le due righe sono confermate dal team: unire ne toglierebbe una)."""
    b = {}

    def coppia(i, j, risposte_i=(), **kw):
        ci, cj = f'NEU-{i:04d}', f'NEU-{j:04d}'
        ii, ij = f'n__doc1__{i * 1000}', f'n__doc1__{j * 1000 + 100}'
        b[ii] = riga(ci, i * 1000, [cj], **kw)
        b[ij] = riga(cj, j * 1000 + 100, [ci], **kw)
        # la stessa voce sulle due righe, come la scrive la piattaforma
        b[ii]['s08_risposte'] = [voce(ij, cj, r, chi, q, n) for r, chi, q, n in risposte_i]
        b[ij]['s08_risposte'] = [voce(ii, ci, r, chi, q, n) for r, chi, q, n in risposte_i]
    coppia(1, 2, [('due', 'luca', '2026-10-07T09:00:00Z', ''), ('una', 'anna', '2026-10-07T10:00:00Z', 'NEU-0001 stays'),
                  ('una', 'luca', '2026-10-07T11:00:00Z', '')])
    coppia(3, 4, [('una', 'anna', '2026-10-07T10:00:00Z', ''), ('due', 'luca', '2026-10-07T11:00:00Z', 'two paragraphs')])
    coppia(5, 6, [('due', 'anna', '2026-10-07T10:00:00Z', '')])
    coppia(7, 8, [('incerta', 'anna', '2026-10-07T10:00:00Z', '')])
    coppia(9, 10)
    coppia(11, 12, [('una', 'anna', '2026-10-07T10:00:00Z', '')], esito='confermata', validato_da='uid-judge')
    return b


def test_ogni_risposta_una_volta_e_vale_l_ultima_di_ognuno():
    b = banca()
    voci = L.raccogli(b)
    assert len(voci) == 3 + 2 + 1 + 1 + 1          # le voci doppie (sulle due righe) contano una volta
    ver = L.verdetti(b, voci)
    per = {x['codici']: x['verdetto'] for x in ver.values()}
    assert per == {('NEU-0001', 'NEU-0002'): 'una', ('NEU-0003', 'NEU-0004'): 'disaccordo', ('NEU-0005', 'NEU-0006'): 'due',
                   ('NEU-0007', 'NEU-0008'): 'incerta', ('NEU-0009', 'NEU-0010'): 'nessuna', ('NEU-0011', 'NEU-0012'): 'una'}


def test_una_si_unisce_come_scrivi_s08_e_il_resto_non_si_tocca():
    b = banca()
    _, ver, decisioni, piano = L.prepara(b)
    assert {d['id'] for d in decisioni} == {'NEU-0001__NEU-0002', 'NEU-0011__NEU-0012'}
    # 1+2: la seconda nell'atto esce, come C03, con la regola S08
    esce = piano.righe['n__doc1__2100']
    assert esce['proposto_rete'] == 'esclusa' and esce['esclusa_regola'] == 'S08' and esce['unita_a'] == 'NEU-0001'
    assert esce['esclusa_da'] == L.DA and esce['esclusa_motivo'].startswith('S08 il team: una citazione')
    assert [x['codice'] for x in piano.righe['n__doc1__1000']['proposto_nota_appoggio']] == ['NEU-0002']
    # 11+12: tutte e due confermate dal team; scrivi_s08 la rimanderebbe al team, qui va al PI e non si scrive niente
    assert 'n__doc1__11000' not in piano.righe and 'n__doc1__12100' not in piano.righe
    assert not any('s08_coppie_team' in c for c in piano.righe.values())
    assert not piano.revisioni
    # disaccordo, due, incerta, nessuna: niente
    for i in ('n__doc1__3000', 'n__doc1__4100', 'n__doc1__5000', 'n__doc1__6100', 'n__doc1__7000', 'n__doc1__8100'):
        assert i not in piano.righe


def test_la_tenuta_segue_il_giudizio_del_team():
    """Se la prima nell'atto e' scartata, resta l'altra (la regola di decidi_s08, nel Piano di scrivi_s08)."""
    b = banca()
    b['n__doc1__1000'].update(esito='scartata', validato_da='uid-judge')
    _, _, _, piano = L.prepara(b)
    assert 'n__doc1__1000' not in piano.righe or piano.righe['n__doc1__1000'].get('proposto_rete') != 'esclusa'


def test_esporta_disaccordi_e_righe_giudicate_al_pi(tmp_path):
    b = banca()
    voci, ver, _, piano = L.prepara(b)
    righe, pi = L.esporta(tmp_path, b, voci, ver, piano)
    assert sorted((x['codice_a'], x['perche'][:11]) for x in pi) == [('NEU-0003', 'disaccordo'), ('NEU-0011', 'unire togli')]
    with open(tmp_path / 'risposte_s08.tsv', encoding='utf-8') as h:
        tutte = list(csv.DictReader(h, delimiter='\t'))
    assert len(tutte) == 8
    superata = [x for x in tutte if x['chi'] == 'luca' and x['riga_codice'] in ('NEU-0001', 'NEU-0002')]
    assert sorted(x['vale'] for x in superata) == ['no', 'si']          # Luca ci ha ripensato: vale l'ultima
    with open(tmp_path / 'coppie_s08_team.tsv', encoding='utf-8') as h:
        coppie = {(x['codice_a'], x['codice_b']): x for x in csv.DictReader(h, delimiter='\t')}
    assert coppie[('NEU-0001', 'NEU-0002')]['che_cosa_si_fa'] == 'unita: esce NEU-0002, resta NEU-0001'
    assert 'Anna: One citation (NEU-0001 stays)' in coppie[('NEU-0001', 'NEU-0002')]['risposte']
    assert coppie[('NEU-0009', 'NEU-0010')]['che_cosa_si_fa'] == 'niente: nessuna risposta ancora'


def test_a_secco_di_serie_e_scrivi_vuole_vivo(tmp_path, monkeypatch):
    f = tmp_path / 'banca.json.gz'
    with gzip.open(f, 'wt', encoding='utf-8') as h:
        json.dump(banca(), h)
    chiamate = []
    monkeypatch.setattr(L.S, 'scrivi', lambda *a, **k: chiamate.append(a))
    assert L.main(['--banca', str(f), '--uscita', str(tmp_path / 'out'), '--revisione-c03', str(tmp_path / 'no.tsv')]) == 0
    assert not chiamate
    assert (tmp_path / 'out' / 'da_decidere_pi.tsv').exists() and (tmp_path / 'out' / 'scrivi_s08_scritture.json').exists()
    with pytest.raises(SystemExit):
        L.main(['--banca', str(f), '--scrivi'])
