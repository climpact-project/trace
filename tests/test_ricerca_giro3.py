"""The search by name after the third round of the external review (03/10/2026), on synthetic data only.

- the deduplication in its two modes: by default the key and the result are those of the old inline loop of
  ``RicercaPerNome.esegui`` (first 400 characters, spaces joined, lower case, across the corpus), which produced the
  harness outputs; with ``per_atto`` a copy is dropped only inside the same filing and a twin in another filing is kept
  with ``stesso_testo_di``; ``copie`` stays on the kept row in both modes;
- the CSV and the discards file with twins, and a case whose rows are all filtered out (no ``IndexError``);
- the merge with the platform: a mixed group already judged, a platform row without ``file``, and the screen count of
  split citations (only groups with a row to merge; the old count with ``compat``).
"""

from __future__ import annotations

import copy
import csv
import random
import re
from pathlib import Path
from typing import Any

import pytest

from tracepipe.banca import BancaDatiMemoria
from tracepipe.config import Config
from tracepipe.ricerca import RicercaPerNome, UnioneRighe, chiave_testo, colonne_csv, deduplica

# the deduplication


def _vecchio_ciclo(righe: list[dict[str, Any]], scarti: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The inline loop of ``RicercaPerNome.esegui`` before 03/10/2026 (commit 0c285f2), character for character."""
    visti: dict[str, dict[str, Any]] = {}
    uniche = []
    for r in righe:
        k = re.sub(r'\s+', ' ', r['citazione_testuale']).strip().lower()[:400]
        if k in visti:
            visti[k]['copie'] = int(visti[k].get('copie') or 1) + 1
            r['motivo_scarto'] = 'copia di un altro frammento'
            scarti.append(r)
            continue
        r['copie'] = 1
        visti[k] = r
        uniche.append(r)
    return uniche


TESTI = [
    'Urgenda held x',
    'urgenda   HELD x',
    ' Urgenda held\nx ',
    'Neubauer said y',
    'z' * 500,
    'z' * 400 + 'w',  # equal to the one above in the first 400 characters: a copy in both modes' key
    'z' * 399 + 'w',
]


def test_chiave_di_400_caratteri_come_il_vecchio_ciclo() -> None:
    for t in TESTI:
        assert chiave_testo({'citazione_testuale': t}) == re.sub(r'\s+', ' ', t).strip().lower()[:400]
    assert chiave_testo({'citazione_testuale': 'z' * 500}) == chiave_testo({'citazione_testuale': 'z' * 400 + 'w'})


def test_deduplica_predefinita_come_il_vecchio_ciclo() -> None:
    rnd = random.Random(20261003)
    for _ in range(300):
        righe = [
            {'document_id': rnd.choice('abc'), 'char_start': k, 'citazione_testuale': rnd.choice(TESTI), 'copie': ''}
            for k in range(rnd.randint(0, 15))
        ]
        sv: list[dict[str, Any]] = []
        sn: list[dict[str, Any]] = []
        assert deduplica(copy.deepcopy(righe), sn) == _vecchio_ciclo(copy.deepcopy(righe), sv)
        assert sn == sv


def _righe() -> list[dict[str, Any]]:
    t = 'The court followed Urgenda on the duty of care.'
    return [
        {'document_id': 'a', 'char_start': 10, 'citazione_testuale': t},
        {'document_id': 'a', 'char_start': 900, 'citazione_testuale': t.upper()},  # same filing
        {'document_id': 'b', 'char_start': 40, 'citazione_testuale': t},  # another filing
        {'document_id': 'b', 'char_start': 70, 'citazione_testuale': t},  # same filing as the one above
        {'document_id': 'c', 'char_start': 5, 'citazione_testuale': 'another passage on Urgenda'},
    ]


def test_deduplica_su_tutto_il_corpus_copie_sulla_riga_tenuta() -> None:
    scarti: list[dict[str, Any]] = []
    tenute = deduplica(_righe(), scarti)
    assert [(r['document_id'], r['char_start'], r['copie']) for r in tenute] == [('a', 10, 4), ('c', 5, 1)]
    assert [(r['document_id'], r['char_start']) for r in scarti] == [('a', 900), ('b', 40), ('b', 70)]
    assert all(r['motivo_scarto'] == 'copia di un altro frammento' for r in scarti)
    assert all('stesso_testo_di' not in r for r in tenute + scarti)


def test_deduplica_per_atto_stesso_atto_scartato_altro_atto_tenuto() -> None:
    scarti: list[dict[str, Any]] = []
    tenute = deduplica(_righe(), scarti, per_atto=True)
    assert [(r['document_id'], r['char_start'], r['stesso_testo_di'], r['copie']) for r in tenute] == [
        ('a', 10, '', 2),
        ('b', 40, 'a__10', 2),
        ('c', 5, '', 1),
    ]
    assert [(r['document_id'], r['char_start']) for r in scarti] == [('a', 900), ('b', 70)]
    assert all('stesso_testo_di' not in r for r in scarti)  # the discards file writes it empty
    gemelle = sum(1 for r in tenute if r.get('stesso_testo_di'))
    assert gemelle == 1  # the log line counts kept twins, not discarded copies


def test_colonne_csv() -> None:
    assert colonne_csv([{'a': 1, 'b': 2}, {'a': 3, 'b': 4}]) == ['a', 'b']  # = list(righe[0].keys())
    assert colonne_csv([{'a': 1}, {'a': 2, 'x': 3}]) == ['a', 'x']  # a key only on a later row is a column
    assert colonne_csv([], ['a', 'b']) == ['a', 'b']


# the search on a synthetic root

RIEMPI = 'lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore '
BLOCCO = (RIEMPI * 4)[:300] + 'Urgenda' + (RIEMPI * 4)[:300]  # the same 460-character window around the name


def _documento(caso_id: str, doc: str, corpo: str, anno: str = '2021') -> str:
    return (
        f"---\ncase_id: '{caso_id}'\ncase_name: 'Caso {caso_id}'\ndocument_id: '{doc}'\ntipo_atto: 'decisione'\n"
        f"data_deposito: '{anno}-02-01'\nurl_origine: 'https://x/{anno}/{anno}0201_{doc}.pdf'\n---\n"
        f'<!-- page 1 -->\n{corpo}\n'
    )


@pytest.fixture
def radice(tmp_path: Path) -> Path:
    # the name search computes the body-or-footnote column from the PDF and stops without PyMuPDF (the `pdf` extra)
    pytest.importorskip('fitz', reason='needs PyMuPDF: pip install ".[pdf]"')
    (tmp_path / 'cited-cases').mkdir()
    (tmp_path / 'cited-cases' / 'urgenda.yaml').write_text(
        "nome: Urgenda\nforme:\n  - Urgenda\n  - 'ECLI:NL:RBDHA:2015:7145'\n", encoding='utf-8'
    )
    (tmp_path / 'cited-cases' / 'filtrato.yaml').write_text(
        "nome: Urgenda\nforme:\n  - Urgenda\ndata_decisione: '2030-01-01'\nfiltro_data_documento: true\n",
        encoding='utf-8',
    )
    md = tmp_path / 'markdown'
    for d in ('x', 'y', 'z'):
        (md / d).mkdir(parents=True)
    (md / 'x' / 'a.md').write_text(_documento('caso-x', 'a', BLOCCO + BLOCCO), encoding='utf-8')  # a copy inside
    (md / 'y' / 'b.md').write_text(_documento('caso-y', 'b', BLOCCO), encoding='utf-8')  # the same text elsewhere
    (md / 'z' / 'c.md').write_text(_documento('caso-z', 'c', RIEMPI + 'Urgenda, another passage.'), encoding='utf-8')
    (tmp_path / 'index').mkdir()
    (tmp_path / 'training').mkdir()
    return tmp_path


def _leggi(f: Path) -> tuple[list[str], list[dict[str, str]]]:
    with f.open(encoding='utf-8') as h:
        r = csv.DictReader(h)
        return list(r.fieldnames or []), list(r)


def _cerca(radice: Path, caso: str, per_atto: bool) -> tuple[int, list[str]]:
    righe: list[str] = []
    e = RicercaPerNome(
        Config(radice=radice), caso, uscita=f'index/{caso}.csv', dedup_per_atto=per_atto, stampa=righe.append
    ).esegui()
    return e.codice, righe


def test_csv_con_gemelle_per_atto(radice: Path) -> None:
    codice, schermo = _cerca(radice, 'urgenda', per_atto=True)
    assert codice == 0
    campi, righe = _leggi(radice / 'index' / 'urgenda.csv')
    assert campi[-1] == 'stesso_testo_di' and 'verbatim_intero' not in campi
    a = next(r for r in righe if r['document_id'] == 'a')
    assert [(r['document_id'], r['copie'], r['stesso_testo_di']) for r in righe] == [
        ('a', '2', ''),
        ('b', '1', f'a__{a["char_start"]}'),
        ('c', '1', ''),
    ]
    campi_s, scarti = _leggi(radice / 'index' / 'urgenda.SCARTI.csv')
    assert campi_s == [*campi, 'motivo_scarto']
    assert [(r['document_id'], r['stesso_testo_di'], r['motivo_scarto']) for r in scarti] == [
        ('a', '', 'copia di un altro frammento')
    ]
    assert 'same text in another filing: 1 rows kept, with stesso_testo_di' in schermo
    assert 'duplicates  : 1 rows were copies of the same text' in schermo


def test_csv_su_tutto_il_corpus(radice: Path) -> None:
    codice, schermo = _cerca(radice, 'urgenda', per_atto=False)
    assert codice == 0
    campi, righe = _leggi(radice / 'index' / 'urgenda.csv')
    assert 'stesso_testo_di' not in campi
    assert [(r['document_id'], r['copie']) for r in righe] == [('a', '3'), ('c', '1')]
    campi_s, scarti = _leggi(radice / 'index' / 'urgenda.SCARTI.csv')
    assert campi_s == [*campi, 'motivo_scarto'] and [r['document_id'] for r in scarti] == ['a', 'b']
    assert not any('same text in another filing' in s for s in schermo)


@pytest.mark.parametrize('per_atto', [False, True])
def test_caso_svuotato_dal_filtro(radice: Path, per_atto: bool) -> None:
    codice, schermo = _cerca(radice, 'filtrato', per_atto=per_atto)
    assert codice == 0
    campi, righe = _leggi(radice / 'index' / 'filtrato.csv')
    assert righe == [] and campi[:2] == ['case_id', 'case_name'] and ('stesso_testo_di' in campi) == per_atto
    campi_s, scarti = _leggi(radice / 'index' / 'filtrato.SCARTI.csv')
    assert campi_s == [*campi, 'motivo_scarto'] and len(scarti) == 4
    assert all(r['anteriore'] == 'si' and 'anteriore alla pronuncia' in r['motivo_scarto'] for r in scarti)
    assert 'ROWS       : 0' in schermo


def test_caso_senza_occorrenze(radice: Path) -> None:
    (radice / 'cited-cases' / 'nessuno.yaml').write_text('nome: Nessuno\nforme:\n  - Inesistente\n', encoding='utf-8')
    assert _cerca(radice, 'nessuno', per_atto=False)[0] == 0
    campi, righe = _leggi(radice / 'index' / 'nessuno.csv')
    assert righe == [] and 'citazione_testuale' in campi
    assert not (radice / 'index' / 'nessuno.SCARTI.csv').exists()


# the merge with the platform

DATA = '2026-10-03'
NOME = 'The Urgenda Foundation judgment (ECLI:NL:RBDHA:2015:7145) applies.'


def _unione(radice: Path, piattaforma: dict[str, dict[str, Any]]) -> UnioneRighe:
    (radice / 'markdown' / 'u').mkdir()
    (radice / 'markdown' / 'u' / 'u.md').write_text(_documento('caso-u', 'u', NOME), encoding='utf-8')
    _cerca(radice, 'urgenda', per_atto=False)
    (radice / 'index' / 'urgenda.csv').rename(radice / 'index' / f'nomi_urgenda_{DATA}b.csv')
    banca = BancaDatiMemoria({'corpus_rows': piattaforma})
    return UnioneRighe(Config(radice=radice), banca, data=DATA, casi=['urgenda'], stampa=lambda _: None)


def _riga(testo: str, codice: str, **kw: Any) -> dict[str, Any]:
    """A platform row starting at ``testo`` in the document of :data:`NOME`."""
    return {
        'caso_citato': 'urgenda',
        'document_id': 'u',
        'file': 'markdown/u/u.md',
        'char_start': _documento('caso-u', 'u', NOME).index(testo),
        'proposto_rete': 'lessicale',
        'codice': codice,
        **kw,
    }


def test_unione_gruppo_misto_gia_giudicato(radice: Path) -> None:
    """A citation split by the old merge rule into a NAME row and a CODE row (the ECLI), the code row already judged:
    the judged row stays and the name row is merged into it (``fusa_in``), as in ``tools/unisci_e_aggiungi.py``. It
    is the rule, not an accident: a person's judgement is never thrown away, and both rows are the same citation."""
    nome = _riga('Urgenda Foundation', 'URG-0001')
    ecli = _riga('ECLI:NL', 'URG-0002', esito='confermata')
    e = _unione(radice, {'n': nome, 'e': ecli}).confronta('urgenda')
    assert [(t[0], [x[0] for x in via], giudicate) for t, via, giudicate in e.spezzate] == [('e', ['n'], 1)]
    assert not e.orfane and all(d['document_id'] != 'u' for d in e.nuove.values())  # the group is covered


def test_unione_gruppo_misto_non_giudicato(radice: Path) -> None:
    nome = _riga('Urgenda Foundation', 'URG-0001')
    ecli = _riga('ECLI:NL', 'URG-0002')
    e = _unione(radice, {'n': nome, 'e': ecli}).confronta('urgenda')
    assert [(t[0], [x[0] for x in via]) for t, via, _ in e.spezzate] == [('n', ['e'])]  # the name row stays


def _due_nomi_e_un_codice_giudicato(radice: Path, compat: bool = False) -> tuple[UnioneRighe, Any, list[str]]:
    """Two name rows and a judged code row in the same group: nothing to merge (``via`` empty)."""
    nome = _riga('Urgenda Foundation', 'URG-0001')
    nome2 = dict(nome, char_start=nome['char_start'] - 4, codice='URG-0003')  # a few characters before: same group
    ecli = _riga('ECLI:NL', 'URG-0002', esito='confermata')
    u = _unione(radice, {'n': nome, 'n2': nome2, 'e': ecli})
    schermo: list[str] = []
    u.stampa, u.compat = schermo.append, compat
    return u, u.confronta('urgenda'), schermo


def test_unione_due_righe_col_nome_nessuna_fusione(radice: Path) -> None:
    """With more than one name row in the group, a judged code row does not turn any of them off: the group is kept in
    ``spezzate`` with an empty ``via`` (the decision of the live tool), and nothing is written for it."""
    u, e, _ = _due_nomi_e_un_codice_giudicato(radice)
    assert e.piu_nomi == 1
    assert [(t[0], [x[0] for x in via]) for t, via, _ in e.spezzate] == [('e', [])]
    w, corsa = u.scritture(e, '', 1)
    assert not [x for x in w if x.op == 'update'] and corsa.dati['righe_unite'] == 0  # no row turned off


def test_conto_delle_spezzate_solo_gruppi_da_unire(radice: Path) -> None:
    """The screen count of split citations: by default only the groups with a row to merge (here none); with
    ``compat`` the old count of the live tool, which included the group with nothing to merge (the harness)."""
    u, e, schermo = _due_nomi_e_un_codice_giudicato(radice)
    u.mostra(e)
    assert u.da_contare(e) == []
    assert any(r.startswith('   split citations 0: rows to merge 0, with one judged row 0,') for r in schermo)
    schermo.clear()
    u.compat = True
    u.mostra(e)
    assert len(u.da_contare(e)) == 1
    assert any(r.startswith('   split citations 1: rows to merge 0, with one judged row 1,') for r in schermo)


@pytest.mark.parametrize('compat', [False, True])
def test_conto_delle_spezzate_con_una_fusione(radice: Path, compat: bool) -> None:
    """A group with a row to merge is counted in both modes."""
    u = _unione(radice, {'n': _riga('Urgenda Foundation', 'URG-0001'), 'e': _riga('ECLI:NL', 'URG-0002')})
    schermo: list[str] = []
    u.stampa, u.compat = schermo.append, compat
    u.mostra(u.confronta('urgenda'))
    assert any(r.startswith('   split citations 1: rows to merge 1,') for r in schermo)


def test_unione_riga_senza_file(radice: Path) -> None:
    """A platform row whose document has no ``file`` (and is not in the search) is an orphan, not a TypeError."""
    nome = _riga('Urgenda Foundation', 'URG-0001')
    senza = {'caso_citato': 'urgenda', 'document_id': 'sparito', 'char_start': 3, 'proposto_rete': 'lessicale'}
    e = _unione(radice, {'n': nome, 's': senza}).confronta('urgenda')
    assert [i for i, _ in e.orfane] == ['s']


def test_colonne_della_copia_per_atto(vivi_oggi, monkeypatch) -> None:
    """``tools/cerca_s05_per_atto.py`` (not in use): same columns as before with rows, no ``IndexError`` without."""
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parent.parent / 'tools'))  # its sibling `dimensioni`
    viva = vivi_oggi('cerca_s05_per_atto')
    righe = [{'case_id': 'x', 'copie': 2, 'stesso_testo_di': ''}, {'case_id': 'y', 'copie': 1, 'stesso_testo_di': 'a'}]
    assert viva.colonne_csv(righe, []) == list(righe[0].keys())
    scarti = [{'case_id': 'x', 'copie': '', 'verbatim_intero': 'v', 'motivo_scarto': 'anteriore al 2030-01-01'}]
    assert viva.colonne_csv([], scarti) == ['case_id', 'copie', 'stesso_testo_di']
    assert viva.colonne_csv([], []) == []
