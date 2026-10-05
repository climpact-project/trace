"""S06 (03/10/2026): the S05 copies in a filing of another case, recovered (tools/recupero_s06.py, tools/ciclo_s06.sh).

What must hold:

- only copies whose kept fragment is in ANOTHER case come back, one row per filing and text;
- a copy whose filing is the same document as the kept one (same PDF hash, or same full text) is excluded, also when
  it repeats a copy already taken; a filing that only shares the cited page is NOT excluded;
- the new rows stay out of the team queues (``assegnato_a`` absent, ``assegnato_a_in_attesa`` set) and carry S06;
- only complete S06 rows go back into the queues;
- the T01 check against the H100 scores fails when it must;
- the launchd watcher starts the chain only after the five-reading chain wrote FINITO, loaded and closed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / 'tools'))
sys.dont_write_bytecode = True

import punteggi_t01_s06 as t01  # noqa: E402
import recupero_s06 as r6  # noqa: E402

TESTO = 'As held in Urgenda, the State has a duty of care towards its citizens to reduce emissions by 25 per cent.'


def riga(doc, case, cs, testo=TESTO, motivo='', file=''):
    return {'document_id': doc, 'case_id': case, 'char_start': str(cs), 'citazione_testuale': testo,
            'motivo_scarto': motivo, 'file': file or f'markdown/{doc}.md', 'pagina': '3', 'rete': 'lessicale',
            'case_name': case, 'tipo_atto': 'ricorso', 'data': '2024-01-01'}


# ── which copies come back ────────────────────────────────────────────────────────────────────────────────────────

def test_only_copies_in_another_case_one_per_filing():
    tenute = [riga('a-petition_1', 'case-a', 100)]
    scarti = [
        riga('a-reply_2', 'case-a', 90, motivo=r6.COPIA),                  # same case: stays a copy
        riga('b-complaint_3', 'case-b', 50, motivo=r6.COPIA),              # another case: comes back
        riga('b-complaint_3', 'case-b', 900, motivo=r6.COPIA),             # same filing, same text again: a copy
        riga('c-brief_4', 'case-c', 70, testo='  ' + TESTO.upper() + ' ', motivo=r6.COPIA),  # same key (spaces, case)
        riga('d-brief_5', 'case-d', 10, testo='another text entirely', motivo=r6.COPIA),     # no kept fragment
        riga('e-brief_6', 'case-e', 10, motivo='documento del 2019-12-01, anteriore alla pronuncia'),  # not a copy
    ]
    copie, senza = r6.copie_altra_causa(tenute, scarti)
    presi = [(c['riga']['document_id'], c['riga']['char_start']) for c in copie]
    assert presi == [('b-complaint_3', '50'), ('c-brief_4', '70')]
    assert all(c['primo']['document_id'] == 'a-petition_1' for c in copie)
    assert senza == 1


def test_same_document_needs_same_pdf_or_same_text():
    a = {'pdf': 'x' * 64, 'testo': '1' * 64}
    assert r6.stesso_documento(a, {'pdf': 'x' * 64, 'testo': '2' * 64}) == 'stesso PDF (sha256_pdf)'
    assert r6.stesso_documento(a, {'pdf': 'y' * 64, 'testo': '1' * 64}) == 'stesso testo'
    assert r6.stesso_documento(a, {'pdf': 'y' * 64, 'testo': '2' * 64}) == ''
    # an empty PDF hash on both sides is not «the same PDF»
    assert r6.stesso_documento({'pdf': '', 'testo': '1'}, {'pdf': '', 'testo': '2'}) == ''


def test_separa_excludes_against_kept_and_against_taken_copies():
    primo = riga('a-petition_1', 'case-a', 100)
    copie = [{'riga': riga(d, c, 10), 'primo': primo}
             for d, c in (('b-order_2', 'case-b'), ('c-order_3', 'case-c'), ('d-order_4', 'case-d'),
                          ('e-other_5', 'case-e'))]
    imp = {'markdown/a-petition_1.md': {'pdf': 'P1', 'testo': 'T1'},
           'markdown/b-order_2.md': {'pdf': 'P1', 'testo': 'T1'},     # the kept filing again
           'markdown/c-order_3.md': {'pdf': 'P3', 'testo': 'T3'},     # a different filing: taken
           'markdown/d-order_4.md': {'pdf': 'P4', 'testo': 'T3'},     # same text as the copy just taken
           'markdown/e-other_5.md': {'pdf': 'P5', 'testo': 'T5'}}
    tenere, escluse = r6.separa(copie, lambda f: imp[f])
    assert [c['riga']['document_id'] for c in tenere] == ['c-order_3', 'e-other_5']
    assert [(c['riga']['document_id'], c['uguale_a'], c['perche']) for c in escluse] == [
        ('b-order_2', 'a-petition_1', 'stesso PDF (sha256_pdf)'), ('d-order_4', 'c-order_3', 'stesso testo')]


def test_impronte_ignore_front_matter_and_spacing(tmp_path):
    a, b = tmp_path / 'a.md', tmp_path / 'b.md'
    a.write_text("---\ndocument_id: 'a'\nsha256_pdf: 'aaa'\n---\nThe  same\ntext.\n", encoding='utf-8')
    b.write_text("---\ndocument_id: 'b'\ndocument_title: 'other'\n---\nThe same text.\n", encoding='utf-8')
    ia, ib = r6.impronte(str(a)), r6.impronte(str(b))
    assert ia['pdf'] == 'aaa' and ib['pdf'] == ''
    assert ia['testo'] == ib['testo']
    assert r6.stesso_documento(ia, ib) == 'stesso testo'


# ── the rows written to the platform ──────────────────────────────────────────────────────────────────────────────

def test_documenti_hidden_numbered_and_marked():
    righe = [{'caso': 'neubauer', 'id': f'neubauer__b-complaint_3__{cs}', 'riga': riga('b-complaint_3', 'case-b', cs),
              'primo_id': 'neubauer__a-petition_1__100', 'primo_case_id': 'case-a'} for cs in (50, 70)]
    esistenti = [('x1', {'codice': 'NEU-1650', 'proposto_rete': 'lessicale', 'assegnato_a': 'u2'}),
                 ('x2', {'codice': 'NEU-1700', 'proposto_rete': 'lessicale', 'assegnato_a': 'u1'}),
                 ('x3', {'codice': 'NEU-0001', 'proposto_rete': 'lessicale', 'assegnato_a': 'u3',
                         'esito': 'confermata'})]
    docs = r6.documenti('neubauer', righe, esistenti, set())
    assert sorted(d['codice'] for d in docs.values()) == ['NEU-1701', 'NEU-1702']
    for d in docs.values():
        assert 'assegnato_a' not in d
        assert d['assegnato_a_in_attesa'] in {'u1', 'u2'}               # only people with rows still to judge
        assert d['provenienza']['estrazione'] == 'S06' and d['provenienza']['corpus'] == 'D01'
        assert d['stesso_testo_di'] == 'a-petition_1__100' and d['stesso_testo_di_causa'] == 'case-a'
        assert d['proposto_rete'] == 'lessicale' and d['esito'] is None
        assert d['esecuzione_id'] == 'neubauer__nomi__2026-10-03-S06'
    assert r6.documenti('neubauer', righe, esistenti, set()) == docs   # same input, same codes and assignments
    with pytest.raises(ValueError):
        r6.documenti('neubauer', righe, [*esistenti, (righe[0]['id'], {})], set())


def test_rimetti_moves_only_complete_unjudged_s06_rows():
    completa = {'proposto_tipo_citazione': 'descrittiva', 'proposto_principi': ['nessuno'],
                'proposto_punteggi_principi': {'p': 0.1}, 'assegnato_a_in_attesa': 'u1',
                'provenienza': {'estrazione': 'S06'}}
    righe = [('ok', completa),
             ('senza_principi', {**completa, 'proposto_principi': []}),
             ('provvisoria', {**completa, 'proposta_provvisoria': True}),
             ('giudicata', {**completa, 'esito': 'confermata'}),
             ('s05', {**completa, 'provenienza': {'estrazione': 'S05'}}),
             ('gia_dentro', {**completa, 'assegnato_a_in_attesa': None, 'assegnato_a': 'u1'})]
    mosse, incomplete = r6.mosse_rimetti(righe)
    assert [i for i, _ in mosse] == ['ok'] and mosse[0][1]['assegnato_a'] == 'u1'
    assert incomplete == ['senza_principi', 'provvisoria']


def test_brano_masks_name_and_drops_markers():
    import re
    ctx = ('===== PAGINA DELLA CITAZIONE =====\nbefore [[INIZIO DEL BRANO SEGNALATO]]As held in ⟦Urgenda⟧, '
           'the duty[[FINE DEL BRANO SEGNALATO]] after')
    br = r6.brano(ctx, re.compile('Urgenda', re.I))
    assert br == '===== PAGINA DELLA CITAZIONE ===== before As held in ⟦CASO_CITATO⟧, the duty after'
    assert r6.brano('no markers here', re.compile('x')) is None


def test_pagine_attorno_window():
    ids = r6.pagine_attorno([{'document_id': 'd', 'pagina': 3}, {'document_id': 'e', 'pagina': 0}], finestra=2)
    assert ids == {'d#p1', 'd#p2', 'd#p4', 'd#p5'}


# ── the T01 check against the H100 scores must be able to fail ───────────────────────────────────────────────────

def test_esito_prova_passes_and_fails():
    ref = [0.1, 0.45, 0.9, 0.62]
    assert t01.esito_prova([0.1005, 0.452, 0.899, 0.621], ref)['passa']
    # a pair crossing 0.5 far from the threshold must fail even with a small mean difference
    assert not t01.esito_prova([0.1, 0.45, 0.9, 0.40], ref)['passa']
    # a crossing right at the threshold is noise, if the difference is small
    e = t01.esito_prova([0.499, 0.2], [0.502, 0.2])
    assert e['cambi_di_lato'] == 1 and e['cambi_di_lato_lontani_dalla_soglia'] == 0 and e['passa']
    assert not t01.esito_prova([0.2] * 4, [0.25] * 4)['passa']                         # mean difference too large
    with pytest.raises(ValueError):
        t01.esito_prova([], [])


def test_ricomponi_puts_each_score_back_on_its_pair():
    righe = [{'caso': 'c', 'riga': f'r{i}', 'dove': 'brano', 'principio': f'p{i % 2}', 'q': 'q', 'd': f'd{i}'}
             for i in range(5)]
    coppie = t01.coppie_ferma(righe, [('q5', 'd5'), ('q6', 'd6')])
    assert [x['riga'] for x in coppie[-2:]] == ['prova0', 'prova1'] and coppie[-1]['dove'] == 'prova'
    # what ripresa_punteggi.punteggi writes for piece k of n: the pairs coppie[k::n], in order
    pezzi = [[{k: x[k] for k in ('riga', 'pagina_id', 'dove', 'pagina', 'principio') if k in x} | {'punteggio': j / 10}
              for j, x in enumerate(coppie[k::3])] for k in range(3)]
    m = t01.ricomponi(coppie, pezzi)
    assert m[t01.chiave('q', 'd4')] == 0.1          # coppie[4] is the second pair of piece 1
    assert m[t01.chiave('q6', 'd6')] == 0.2         # coppie[6] is the third pair of piece 0
    sbagliati = [pezzi[1], pezzi[0], pezzi[2]]
    with pytest.raises(ValueError):
        t01.ricomponi(coppie, sbagliati)
    with pytest.raises(ValueError):
        t01.ricomponi(coppie, [pezzi[0][:-1], pezzi[1], pezzi[2]])


def test_chiave_depends_on_query_and_text():
    assert t01.chiave('q', 'd') == t01.chiave('q', 'd')
    assert t01.chiave('q', 'd') != t01.chiave('q', 'd ') != t01.chiave('q2', 'd')


# ── the launchd watcher ───────────────────────────────────────────────────────────────────────────────────────────

def guardiano(tmp_path, log, scrittura=True, plist=False):
    casa = tmp_path / 'casa'
    radice = casa / 'sabin-corpus'
    (radice / 'tools').mkdir(parents=True)
    (radice / 'training' / 'cinque' / 'passi').mkdir(parents=True)
    (casa / 'Library' / 'LaunchAgents').mkdir(parents=True)
    (radice / 'tools' / 'ciclo_s06.sh').write_text('echo PARTITO\n', encoding='utf-8')
    (radice / 'training' / 'cinque' / 'ciclo.log').write_text(log, encoding='utf-8')
    if scrittura:
        (radice / 'training' / 'cinque' / 'passi' / 'scrittura').write_text('x', encoding='utf-8')
    if plist:
        (casa / 'Library' / 'LaunchAgents' / 'it.climpact.cinque-letture.plist').write_text('x', encoding='utf-8')
    p = subprocess.run(['/bin/bash', str(RADICE / 'tools' / 'launchd' / 'attesa_s06.sh')], capture_output=True,
                       text=True, env={**os.environ, 'HOME': str(casa)}, check=False)
    return p.stdout, (radice / 'training' / 's06' / 'attesa.log')


@pytest.mark.parametrize(('log', 'scrittura', 'plist', 'parte', 'fermo'), [
    ('03/10 08:00 S05 FINITO: si comincia\n03/10 09:00 cinque_011 in coda-ds3\n', True, False, False, False),
    ('03/10 21:00 FINITO\n', False, False, False, False),           # load step not marked
    ('03/10 21:00 FINITO\n', True, True, False, False),             # the chain has not closed yet
    ('03/10 21:00 FINITO\n03/10 21:01 plist tolto da LaunchAgents\n', True, False, True, False),
    ('03/10 20:00 FERMO: letture (6 tentativi)\n03/10 20:00 plist tolto da LaunchAgents\n', True, False, False, True),
    ('03/10 18:00 FERMO: rapporto\n03/10 21:00 FINITO\n', True, False, True, False),   # stopped, restarted, finished
])
def test_guardiano(tmp_path, log, scrittura, plist, parte, fermo):
    out, attesa = guardiano(tmp_path, log, scrittura, plist)
    assert ('PARTITO' in out) == parte
    assert fermo == (attesa.exists() and 'cinque letture ferme' in attesa.read_text(encoding='utf-8'))
