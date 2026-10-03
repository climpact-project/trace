"""S05, the name search with text normalisation (tools/cerca_s05.py): what it adds and what it must not change.

Two kinds of test:

- synthetic texts: hyphenation at line breaks, line breaks inside multi-word forms, typographic hyphens and spaces,
  whole-word acronyms, and positions that stay those of the ORIGINAL text;
- the real corpus (skipped when ``markdown/`` is absent): on all six cases, every S03 match is still an S05 match with
  the same start and end, and every S03 citation (group of matches, whose start is the row id) is still found at the
  same id. A citation whose group now begins earlier, because a new S05 match sits less than 200 characters before it
  (``cerca.fondi``), is still found at its id by the platform matching of ``unisci_e_aggiungi.py`` (a row covers the
  matches in the 200 characters after its start): those are counted and checked, not hidden.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / 'tools'))
sys.dont_write_bytecode = True

import cerca as S03  # noqa: E402
import cerca_s05 as S05  # noqa: E402

CASI = ('urgenda', 'neubauer', 'future-generations', 'klimaseniorinnen', 'cig-parere-clima', 'idh-oc-32-25')


def trova(forme, testo, intere=(), ancora=None):
    patt = S05.regex_caso({'forme': list(forme), 'forme_parola_intera': list(intere)})
    anc = S05.regex_ancora(ancora) if ancora else None
    return [(m.start(), m.end(), m.group(0)) for m in S05.corrispondenze(testo, 0, patt, anc)]


# ── the normalisation ──────────────────────────────────────────────────────────────────────────────────────────────


def test_sillabazione_a_fine_riga():
    testo = 'vgl. den Klimabe-\nschluss des BVerfG'
    ((inizio, fine, s),) = trova(['Klimabeschluss'], testo)
    assert inizio == testo.index('Klimabe') and testo[inizio:fine] == 'Klimabe-\nschluss'
    assert S05.forma_normalizzata(s) == 'Klimabeschluss'


def test_sillabazione_con_spazi_e_trattino_morbido():
    assert trova(['KlimaSeniorinnen'], 'Verein Klimaseni- \n  orinnen Schweiz')
    assert trova(['KlimaSeniorinnen'], 'Verein Klima­Seniorinnen')
    assert trova(['KlimaSeniorinnen'], 'Verein Klima​Seniorinnen')


def test_a_capo_e_spazi_dentro_le_forme_di_piu_parole():
    testo = 'see Future Generations v. Ministry of the\nEnvironment and Others, para. 11'
    ((inizio, _, s),) = trova(['Future Generations v. Ministry of the Environment'], testo)
    assert inizio == testo.index('Future')
    assert trova(
        ['Urgenda Foundation v. State of the Netherlands'], 'Urgenda Foundation v. State of  the\r\nNetherlands'
    )


def test_trattini_tipografici():
    for t in ('AO‑32/25', 'AO–32/25', 'AO−32/25', 'AO-\n32/25'):
        assert trova(['AO-32/25'], f'per {t}, para 233'), t
    assert S05.forma_normalizzata('AO‑32/25') == 'AO-32/25'


def test_apostrofi_e_lettere_scomposte():
    assert trova(["ICJ's Advisory Opinion"], 'the ICJ’s Advisory Opinion')
    assert trova(['Barragán, et al. v. Presidencia'], 'Barragán, et al. v. Presidencia')


def test_non_inventa_corrispondenze():
    assert not trova(['Klimabeschluss'], 'Klima beschluss')  # uno spazio dentro la parola non e' sillabazione
    assert not trova(['Urgenda'], 'Ur genda')
    assert not trova(['OC-32/25'], 'OC 32/25')  # il trattino non diventa uno spazio


def test_parola_intera():
    assert trova(['VKS'], 'applying VKS at [478]', intere=['VKS'])
    assert trova(['VKS'], '(VKS, §552)', intere=['VKS'])
    assert not trova(['VKS'], 'the AVKS register and VKSZ', intere=['VKS'])
    assert trova(['VKS'], 'AVKS')  # senza `forme_parola_intera` vale come in S03


def test_forme_cjk_come_s03():
    for f in ('ノイバウアー', '우르헨다', '德國聯邦憲法法院KSG'):
        assert S05.forma_regex(f) == S03.forma_regex(f)


# ── the S03 matches stay identical ─────────────────────────────────────────────────────────────────────────────────


def test_ancora_s03_non_si_inghiotte():
    # la forma nuova comincia prima e coprirebbe la corrispondenza di S03: vince S03, la nuova si scarta
    testo = 'the ICJ in its Advisory Opinion of 23 July 2025, para 1'
    s03 = ['Advisory Opinion of 23 July 2025']
    senza = trova(s03 + ['ICJ in its Advisory Opinion'], testo)
    assert senza[0][0] == testo.index('ICJ')  # senza ancora la riga di S03 si perderebbe
    con = trova(s03 + ['ICJ in its Advisory Opinion'], testo, ancora=s03)
    assert [(a, b) for a, b, _ in con] == [(testo.index('Advisory'), testo.index(', para'))]


def test_forma_esatta_invariata():
    for f in (
        'Urgenda',
        'ECLI:NL:HR:2019:2007',
        'Klima-Beschluss',
        "ICJ's Advisory Opinion",
        '53600/20',
        'Neubauer u. a.',
    ):
        assert S05.forma_normalizzata(f) == f


def test_e_nome_come_s03_sulle_forme_esatte():
    for testo in (
        'see Urgenda, para 5',
        'ECLI:NL:HR:2019:2007',
        'http://www.urgenda.nl/x',
        '1 BvR 2656/18',
        'VKS at 552',
    ):
        m = re.search(r'\S.*', testo)
        assert S05.e_nome(testo, m) == S03.e_nome(testo, m)


# ── the real corpus, all six cases ─────────────────────────────────────────────────────────────────────────────────

CORPUS = (RADICE / 'markdown').exists() and (RADICE / 'cited-cases' / 'urgenda-S05.yaml').exists()


def _gruppi(testo, ms, modulo):
    fuse = modulo.fondi(testo, ms)
    return [f[0].start() for f in fuse], fuse


@pytest.mark.skipif(not CORPUS, reason='markdown/ or the S05 case files absent')
@pytest.mark.parametrize('caso', CASI)
def test_s03_ritrovata_allo_stesso_id(caso):
    """Every S03 match is an S05 match (same start and end); every S03 citation is found at the same id."""
    f5 = RADICE / 'cited-cases' / f'{caso}-S05.yaml'
    c3 = S03.leggi_caso(S05.file_ancora(f5))  # la copia fissa di S03 (cited-cases/ancora-S03/)
    c5 = S05.leggi_caso(f5)
    p3 = re.compile('|'.join(S03.forma_regex(f) for f in c3['forme']), re.I)
    p5 = S05.regex_caso(c5)
    a5 = S05.regex_ancora(c3['forme'])
    file = _file_con_s03(caso, p3)
    assert file, 'nessun file con corrispondenze S03: la prova non proverebbe niente'
    gruppi = assorbiti = legate = 0
    for md in file:
        testo = md.read_text(encoding='utf-8', errors='replace')
        _, inizio = S03.front_matter(testo)
        m3 = list(p3.finditer(testo, inizio))
        m5 = S05.corrispondenze(testo, inizio, p5, a5)
        span5 = {(m.start(), m.end()) for m in m5}
        assert {(m.start(), m.end()) for m in m3} <= span5, md
        g3, _ = _gruppi(testo, m3, S03)
        g5, fuse5 = _gruppi(testo, m5, S05)
        inizi5 = set(g5)
        vecchie = {(m.start(), m.end()) for m in m3}
        for g in g3:
            gruppi += 1
            if g in inizi5:
                continue
            # la citazione di S03 sta dentro un gruppo S05 che comincia prima: o con una corrispondenza nuova a meno di
            # 200 caratteri (`cerca.fondi`, regola 1), o con la citazione S03 precedente, a cui una corrispondenza nuova
            # in mezzo la lega (regola 2: un identificativo a meno di 200 caratteri dalla corrispondenza precedente)
            gruppo = next(f for f in fuse5 if f[0].start() <= g <= f[2])
            # la riga gia' in piattaforma a questo id si ritrova con la regola di `unisci_e_aggiungi.py`: copre le
            # corrispondenze nei 200 caratteri dal suo inizio, e quella che comincia in `g` c'e' ancora, identica
            assert any(m.start() == g for m in m5)
            if (gruppo[0].start(), gruppo[0].end()) in vecchie:
                legate += 1
            else:
                assorbiti += 1
    print(f'{caso}: {len(file)} file, {gruppi} citazioni S03 ritrovate allo stesso id; il gruppo S05 comincia prima per '
          f'{assorbiti} (corrispondenza nuova davanti) e {legate} (legata alla citazione precedente)')


def _file_con_s03(caso, p3):
    """I Markdown in cui S03 trova il caso: dal CSV piu' recente della ricerca per nome, piu' una ricerca veloce."""
    import csv

    csvs = sorted((RADICE / 'index').glob(f'nomi_{caso}_2026-10-0*b.csv'))
    file = set()
    if csvs:
        with open(csvs[-1], encoding='utf-8') as f:
            file |= {r['file'] for r in csv.DictReader(f)}
    return [RADICE / x for x in sorted(file) if (RADICE / x).exists()]
