"""I giudizi del team nel deposito dati (07/10/2026): abbinamento macchina/team su un esempio e nessuna fuga di
nomi, uid o email nel file pubblicato."""
import importlib.util
import json
from pathlib import Path

QUI = Path(__file__).resolve().parent.parent / 'pubblicazione' / 'trace-0.1' / 'team_judgments.py'
spec = importlib.util.spec_from_file_location('team_judgments', QUI)
TJ = importlib.util.module_from_spec(spec)
spec.loader.exec_module(TJ)

T = {'use': {'sostanziale': 'Substantive', 'descrittiva': 'Descriptive', '': ''},
     'who': {'corte': 'The court', 'parte': 'A party', '': ''},
     'where': {'corpo': 'In the body of the text', '': ''}}
UID_A, UID_B, UID_C = 'uidAAAAAAAAAAAAAAAAAAAAAAAA', 'uidBBBBBBBBBBBBBBBBBBBBBBBB', 'uidCCCCCCCCCCCCCCCCCCCCCCCC'
NOMI = ['Maria Rossi', 'Luca Bianchi', 'Anna Verdi']
EMAIL = ['maria.rossi@example.org', 'luca@example.org', 'anna@example.org']


def principio(caso, p):
    return {'x.uno': 'First principle', 'x.due': 'Second principle'}.get(p, p)


def base(codice, **k):
    r = {'codice': codice, 'caso_citato': 'x', 'proposto_tipo_citazione': 'descrittiva', 'proposto_chi_parla': 'parte',
         'proposto_posizione': 'corpo', 'proposto_principi': ['x.uno', 'nessuno'],
         'proposto_estensione': [{'pagina': 4, 'prosegue': True}, {'pagina': 5, 'prosegue': False},
                                 {'pagina': 6, 'prosegue': True, 'c07': True}]}
    r.update(k)
    return r


RIGHE = {
    'a': base('X-0001', esito='confermata', validato_da=UID_B, validato_il='2026-10-04 10:00:00+00:00',
              validato_tipo_citazione='sostanziale', validato_chi_parla='corte', validato_principi=['x.due', 'altro'],
              validato_principio_altro='A note-like principle', validato_estensione=[{'pagina': 9, 'prosegue': True}],
              validato_codebook_versione='0.5-pilot', validato_contesto={'proposte_mostrate': False},
              validato_note='Maria Rossi wrote this'),
    'b': base('X-0002', esito='scartata', motivo_scarto='non_e_una_citazione', validato_da=UID_A,
              validato_il='2026-10-01 08:00:00+00:00', validato_tipo_citazione='descrittiva',
              validato_contesto={'proposte_mostrate': True}),
    'c': base('X-0003', settembre={'esito': 'riclassificata', 'validato_da': UID_A, 'validato_il': '2026-09-14 20:00:00+00:00'}),
    'd': base('X-0004'),                                    # mai giudicata: fuori
    'e': base('X-0005', esito='confermata', validato_da=UID_A, validato_il='2026-10-05 10:00:00+00:00',
              validato_tipo_citazione='descrittiva', validato_chi_parla='parte', validato_principi=['nessuno'],
              validato_estensione=[], validato_contesto={'proposte_mostrate': True}),
    'f': base('X-0006', esito='confermata', validato_da=UID_A, validato_il='2026-10-05 10:00:00+00:00'),  # fuori universo
}
REV = {'e': {UID_C: {'chi': UID_C, 'esito': 'scartata', 'motivo_scarto': 'altro', 'quando': '2026-10-06 09:00:00+00:00'}}}


def costruisci():
    return TJ.costruisci(RIGHE, REV, {'X-0001', 'X-0002', 'X-0003', 'X-0004', 'X-0005'}, {'x': 'Judgment X'}, T, principio)


def test_universo_e_pseudonimi_per_data_del_primo_giudizio():
    righe, pseudo = costruisci()
    assert [x['citation_code'] for x in righe] == ['X-0001', 'X-0002', 'X-0003', 'X-0005']
    # A: settembre 14/09, B: 04/10, C: 06/10
    assert pseudo == {UID_A: 'coder A', UID_B: 'coder B', UID_C: 'coder C'}


def test_macchina_e_team_in_colonne_accoppiate():
    x = {r['citation_code']: r for r in costruisci()[0]}['X-0001']
    assert (x['machine_citation_function'], x['team_citation_function']) == ('Descriptive', 'Substantive')
    assert (x['machine_who_speaks'], x['team_who_speaks']) == ('A party', 'The court')
    assert (x['machine_principles'], x['team_principles']) == (['First principle'], ['Second principle'])
    assert (x['machine_surrounding_pages'], x['team_surrounding_pages']) == ([4], [9])
    assert x['team_other_principle'] == 'A note-like principle'
    assert x['blind'] == 'yes' and x['codebook_version'] == '0.5-pilot' and x['judged_on'] == '2026-10-04'
    assert x['coder'] == 'coder B' and x['outcome'] == 'confirmed'


def test_scartata_riclassificata_e_secondo_giudice():
    d = {r['citation_code']: r for r in costruisci()[0]}
    assert d['X-0002']['outcome'] == 'discarded' and d['X-0002']['discard_reason'] == 'not a citation at all'
    assert d['X-0002']['team_citation_function'] == '' and d['X-0002']['blind'] == 'no'
    assert d['X-0003']['outcome'] == 'reclassified' and d['X-0003']['blind'] == ''
    e = d['X-0005']
    assert (e['second_coder'], e['second_outcome'], e['agreement_outcome']) == ('coder C', 'discarded', 'no')


def test_nessuna_fuga_di_nomi_uid_o_email():
    righe, _ = costruisci()
    testo = '\n'.join(json.dumps(x, ensure_ascii=False) for x in righe)
    testo += '\n' + '\n'.join(','.join(map(str, TJ.csv_riga(x).values())) for x in righe)
    for segreto in [UID_A, UID_B, UID_C, *NOMI, *EMAIL, 'Maria', 'wrote this']:
        assert segreto not in testo
    assert {x['coder'] for x in righe} <= {'coder A', 'coder B', 'coder C'}
