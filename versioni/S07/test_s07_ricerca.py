"""S07 (04/10/2026): the search-side fixes of the 04/10 review, each with a case that MUST fail under the old rule.

- grouping (``fondi``, rule 3): matches in two different footnotes are two citations, in every copy of the rule
  (tools/cerca.py, cerca_s05.py, cerca_s05_per_atto.py, tracepipe/ricerca.py); a line break inside one reference (a
  year, a date, ``Rn.\\n158``, ``\\n1 BvR``) is NOT a footnote boundary;
- dedup (``deduplica``): a copy is dropped only in the same document AND on the same page;
- merge (``unisci_e_aggiungi``, ``tracepipe.ricerca.UnioneRighe``): a row of identifiers only is the tail of a split
  citation only if a NAME stands before it in its own footnote;
- the descriptive network: positions map back to the original text; ``solo_atti_col_nome``;
- the same document filed twice: the catalogue metadata choose the copy (Kaiser, not Allhoff-Cramer).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / 'tools'))
sys.path.insert(0, str(RADICE))
sys.dont_write_bytecode = True

import cerca  # noqa: E402
import cerca_s05  # noqa: E402
import cerca_s05_per_atto  # noqa: E402
import cerca_s07  # noqa: E402
import unisci_e_aggiungi  # noqa: E402
from tracepipe import ricerca as tp  # noqa: E402

MODULI = [cerca, cerca_s05, cerca_s05_per_atto, tp]
FORME = re.compile(r'BVerfG, Beschluss vom 24\. März 2021|1 BvR 2656/18|Urgenda|Beschluss vom 24\. März\s+2021')

# two consecutive footnotes, 75 characters apart (Steinmetz, petition, p. 64: notes 133-135)
NOTE = ('Denn nach wie vor werden erhebliche Teile des Budgets aufgezehrt.\n \n'
        '133 BVerfG, Beschluss vom 24. März 2021 – 1 BvR 2656/18 –, Rn. 185, juris. \n'
        '134 BVerfG, Beschluss vom 24. März 2021 – 1 BvR 2656/18 –, Rn. 186, juris. \n'
        '135 BVerfG, Beschluss vom 24. März 2021 – 1 BvR 2656/18 –, Rn. 187, juris. \n')


def inizi(modulo, testo, patt=FORME):
    return [f[0].start() for f in modulo.fondi(testo, list(patt.finditer(testo)))]


# ── grouping ───────────────────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('modulo', MODULI, ids=lambda m: m.__name__)
def test_note_consecutive_sono_citazioni_distinte(modulo):
    attese = [NOTE.index('BVerfG', NOTE.index(n)) for n in ('\n133 ', '\n134 ', '\n135 ')]
    assert inizi(modulo, NOTE) == attese


@pytest.mark.parametrize('modulo', MODULI, ids=lambda m: m.__name__)
def test_deve_fallire_senza_il_confine(modulo, monkeypatch):
    """the must-fail case: without the footnote boundary the old rule 1 folds the three notes into one row"""
    monkeypatch.setattr(modulo, 'confine_di_nota', lambda *a, **k: False)
    assert len(inizi(modulo, NOTE)) == 1


@pytest.mark.parametrize('modulo', MODULI, ids=lambda m: m.__name__)
@pytest.mark.parametrize('testo', [
    'BVerfG, Beschluss vom 24. März 2021 –\n1 BvR 2656/18 –, Rn. 33',          # the docket number at line start
    'Beschluss vom 24. März\n2021 – 1 BvR 2656/18 –, Rn. 33',                    # a year at line start
    'BVerfG, Beschluss vom 24. März 2021 – 1 BvR 2656/18 –, Rn.\n158 ff.; ebenso 1 BvR 2656/18',  # «Rn.» governs it
    'the judgment in Urgenda of\n24 June 2015, confirmed in Urgenda',            # a date at line start
])
def test_a_capo_dentro_una_citazione_non_e_una_nota(modulo, testo):
    assert len(inizi(modulo, testo)) == 1, testo


@pytest.mark.parametrize('modulo', MODULI, ids=lambda m: m.__name__)
def test_nota_in_apice_e_markdown(modulo):
    for segno in ('¹²', '[^12]:'):
        t = f'Urgenda, para 5.7.5.\n{segno} Urgenda, para 5.7.6.'
        assert len(inizi(modulo, t)) == 2, segno


def test_poelina_note_324_327():
    """the memory rule: a new merge rule is tried first on consecutive notes (Poelina 324-327)"""
    t = ''.join(f'\n{n} Urgenda Foundation v State of the Netherlands, para. 5.7.{n - 320}.' for n in range(324, 328))
    for modulo in MODULI:
        assert len(inizi(modulo, t)) == 4, modulo.__name__


def test_tracepipe_come_cerca():
    for t in (NOTE, 'Urgenda, para 5.\n12 Urgenda, para 6.', 'BVerfG, Beschluss vom 24. März 2021 –\n1 BvR 2656/18'):
        ms = list(FORME.finditer(t))
        assert [f[0].start() for f in tp.fondi(t, ms)] == [f[0].start() for f in cerca.fondi(t, ms)]


# ── dedup ──────────────────────────────────────────────────────────────────────────────────────────────────────


def _righe():
    return [dict(document_id='agapan_1bb7', pagina=93, char_start=521655, citazione_testuale='ordine IBAMA ...'),
            dict(document_id='agapan_1bb7', pagina=145, char_start=805696, citazione_testuale='ordine IBAMA ...'),
            dict(document_id='ado-54_a139', pagina=614, char_start=2691143, citazione_testuale='Tierra Nuestra ...'),
            dict(document_id='ado-54_a139', pagina=614, char_start=2693334, citazione_testuale='Tierra Nuestra ...'),
            dict(document_id='altro_atto', pagina=3, char_start=10, citazione_testuale='ordine IBAMA ...')]


@pytest.mark.parametrize('dedup', [cerca_s05.deduplica, cerca_s05_per_atto.deduplica, cerca_s07.deduplica,
                                   lambda r, s: tp.deduplica(r, s, per_atto=True)])
def test_deduplica_solo_stessa_pagina(dedup):
    scarti = []
    tenute = dedup(_righe(), scarti)
    assert [(r['document_id'], r['char_start']) for r in scarti] == [('ado-54_a139', 2693334)]   # doubled text layer
    st = {(r['document_id'], r['char_start']): r['stesso_testo_di'] for r in tenute}
    assert st[('agapan_1bb7', 805696)] == 'agapan_1bb7__521655'       # the DISPOSITIVO page stays
    assert st[('altro_atto', 10)] == 'agapan_1bb7__521655'
    assert st[('agapan_1bb7', 521655)] == ''


def test_deduplica_deve_fallire_con_la_chiave_per_atto():
    """the must-fail case: the 03/10 key (document, text) drops the DISPOSITIVO copy on p. 145"""
    visti, scarti = set(), []
    for r in _righe():
        k = (r['document_id'], r['citazione_testuale'])
        if k in visti:
            scarti.append(r['char_start'])
        visti.add(k)
    assert 805696 in scarti


# ── merge ──────────────────────────────────────────────────────────────────────────────────────────────────────

UNIONE = ('Hessen.\n44 BVerfG, Beschluss vom 24. März 2021 – 1 BvR 2656/18 –, juris, Rn. 33, 227. \n'
          '45 IPCC, Climate Change 2021, SPM. \n46 1 BvR 2656/18, Rn. 37. \n')


@pytest.mark.parametrize('f', [unisci_e_aggiungi.nome_prima_nella_nota, tp.nome_prima_nella_nota])
def test_unione_solo_nella_stessa_nota(f):
    ms = list(FORME.finditer(UNIONE))
    nota46 = UNIONE.index('1 BvR 2656/18, Rn. 37')
    stessa = UNIONE.index('1 BvR 2656/18 –, juris')
    assert f(UNIONE, ms, nota46) is False       # NEU-0022 (note 46) is not the tail of NEU-0021 (note 44)
    assert f(UNIONE, ms, stessa) is True        # the docket number after the name in note 44 is


def test_unione_deve_fallire_senza_la_nota(monkeypatch):
    """the must-fail case: without the footnote start the identifier of note 46 has a name before it, and merges"""
    monkeypatch.setattr(cerca, 'inizio_della_nota', lambda testo, pos, indietro=4000: 0)
    ms = list(FORME.finditer(UNIONE))
    assert unisci_e_aggiungi.nome_prima_nella_nota(UNIONE, ms, UNIONE.index('1 BvR 2656/18, Rn. 37')) is True


def test_gruppi_del_documento_separano_le_note(tmp_path):
    md = tmp_path / 'x.md'
    md.write_text('---\ndocument_id: x\n---\n' + UNIONE, encoding='utf-8')
    testo, ms, di, starts = unisci_e_aggiungi.gruppi_del_documento(md, FORME)
    assert len(starts) == 2 and di[ms[-1].start()] == 1


# ── the descriptive network ────────────────────────────────────────────────────────────────────────────────────


def test_rete_descrittiva_posizioni_e_regole():
    import rete_descrittiva as RD
    t = 'vgl. BVerfG, a. a. O., Rn. 118 ff.; der Klimabe-\nschluss'
    s, idx = RD.piatto_con_mappa(t)
    assert 'BVerfG, a. a. O.' in s and 'Klimabeschluss' in s
    assert t[idx[s.index('BVerfG')]:].startswith('BVerfG')
    regole = [{'id': 'N_aao', 'ancora': re.compile(r'bverfg,? ?(a\. ?a\. ?o|aao)', re.I), 'con': [], 'finestra': 0,
               'escludi': None, 'solo_atti_col_nome': True}]
    assert RD.corrispondenze_descrittive(t, 0, regole, col_nome=False) == []        # must fail without the name
    ((a, b, regola, trovato),) = RD.corrispondenze_descrittive(t, 0, regole, col_nome=True)
    assert regola == 'N_aao' and t[a:b] == 'BVerfG, a. a. O'


def test_rete_descrittiva_esclude_oc23():
    import rete_descrittiva as RD
    regole, _ = RD.leggi_regole(RADICE / 'cited-cases' / 'idh-oc-32-25-S07.yaml')
    vero = 'Inter-American Court of Human Rights, Advisory Opinion (2025), para. 350'
    falso = 'Corte IDH, Opinión Consultiva OC-23/17 de 2025 (sic), párr. 3'
    assert RD.corrispondenze_descrittive(vero, 0, regole, True)
    assert not RD.corrispondenze_descrittive(falso, 0, regole, True)


# ── the same document filed twice ──────────────────────────────────────────────────────────────────────────────

KAISER = sorted((RADICE / 'markdown').glob('kaiser-et-al-v-volkswagen-ag_aa30/kaiser-et-al-v-volkswagen-ag-petition_345b__*.md'))
ALLHOFF = sorted((RADICE / 'markdown').glob('allhoff-cramer-v-volkswagen-ag_822d/allhoff-cramer-v-volkswagen-ag-complaint_edaa__*.md'))


@pytest.mark.skipif(not (KAISER and ALLHOFF), reason='markdown/ absent')
def test_stesso_documento_sceglie_la_scheda():
    import recupero_s07 as R
    a, k = str(ALLHOFF[0].relative_to(RADICE)), str(KAISER[0].relative_to(RADICE))
    assert R.scegli_per_scheda([a, k])[0] == k
    assert R.scegli_per_scheda([k, a])[0] == k      # path order does not matter any more
