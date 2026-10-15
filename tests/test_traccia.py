"""The common record of J, N and M: converters and schema, on invented rows (no filing text)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from tracepipe.traccia import (
    Identificativi,
    MetadatiFonte,
    Pulizia,
    ancora,
    codice_con_lettera,
    controlla,
    da_j,
    da_m,
    da_n,
    errori,
    validatore,
)

pytest.importorskip('jsonschema')

IDENTIFICATIVI = Path(__file__).resolve().parent.parent / 'identifiers'


@pytest.fixture(scope='module')
def v():
    return validatore()


@pytest.fixture(scope='module')
def ids():
    return Identificativi(IDENTIFICATIVI)


def _riga_j(**altro):
    r = {
        'citation_code': 'URG-0002',
        'cited_judgment': 'Urgenda',
        'document_id': 'invented-v-state-application_ab12',
        'document_name': 'Invented v. State',
        'document_type': 'Application',
        'document_date': '2021-05-20',
        'document_year': '2021',
        'court': 'Invented Court',
        'country': 'Italy',
        'document_url': 'https://www.climatecasechart.com/documents/invented-v-state-application_ab12',
        'page': '18',
        'citation_function': 'Substantive',
        'who_speaks': 'A party',
        'where_in_text': 'Not determinable',
        'principles': ['A first principle', 'A second principle'],
        'cited_paragraphs': [],
        'surrounding_pages': ['19', '20'],
        'review_status': 'proposed by the machine, not yet checked',
        'found_by': 'S01',
        'corpus_version': 'D01',
        'proposal_rule': 'R15',
        'five_readings': 'yes',
        'reference_kind': 'named',
        'sentence': 'An invented sentence that names the invented judgment.',
        'passage': 'An invented passage around it.',
    }
    r.update(altro)
    return r


def _meta(tmp_path: Path) -> MetadatiFonte:
    p = tmp_path / 'metadata.csv'
    with open(p, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(
            [
                'Document ID',
                'Internal Document ID',
                'Case ID',
                'Internal Case ID',
                'Case Name',
                'Bundle ID(s)',
                'Language(s)',
                'Geography ISOs',
            ]
        )
        w.writerow(
            [
                'invented-v-state-application_ab12',
                'Sabin.document.1.2',
                'invented-v-state_cd34',
                'Sabin.family.1.0',
                'Invented v. State',
                '',
                'Italian',
                'ITA',
            ]
        )
    return MetadatiFonte(p)


def test_codice_con_lettera():
    assert codice_con_lettera('URG-0146', 'J') == ('URG-0146-J', ['URG-0146'])
    assert codice_con_lettera('NEU-0001-N', 'N') == ('NEU-0001-N', [])
    with pytest.raises(ValueError):
        codice_con_lettera('NEU-0001-N', 'J')
    with pytest.raises(ValueError):
        codice_con_lettera('TRC 42', 'J')


def test_ancora_non_dipende_dagli_spazi_ne_dalle_maiuscole():
    a = ancora('doc', 3, 'URG', 'The  Urgenda judgment, as held.', 'Around it.')
    assert a == ancora('doc', 3, 'URG', 'the urgenda judgment as held', 'around it')
    assert a.startswith('doc|3|URG|') and [len(x) for x in a.split('|')[3:]] == [16, 8]
    assert a != ancora('doc', 3, 'NEU', 'The  Urgenda judgment, as held.', 'Around it.'), 'one sentence, two cases'
    assert a != ancora('doc', 3, 'URG', 'The  Urgenda judgment, as held.', 'Another footnote.')
    assert ancora('doc', None, 'URG', 'x') is None


def test_j_valido_con_gli_identificativi_esterni(tmp_path, ids, v):
    rec = da_j(_riga_j(), ids, _meta(tmp_path))
    assert errori(rec, v) == []
    assert rec['ids']['code'] == 'URG-0002-J' and rec['ids']['aliases'] == ['URG-0002']
    assert rec['cited']['case_id'] == 'CL-C-000001-3'
    assert rec['citing']['document_import_id'] == 'Sabin.document.1.2'
    assert rec['citing']['family_import_id'] == 'Sabin.family.1.0'
    assert rec['citing']['geography_iso'] == ['ITA']
    assert rec['classification']['surrounding_pages'] == [19, 20]
    assert rec['provenance']['five_readings'] is True


def test_j_toglie_il_byte_nullo_e_lo_conta(tmp_path, ids, v):
    pulizia = Pulizia()
    rec = da_j(_riga_j(passage='before\x00after\x07'), ids, _meta(tmp_path), pulizia)
    assert rec['evidence']['passage'] == 'beforeafter'
    assert pulizia['passage'] == 1
    assert errori(rec, v) == []


def test_lo_schema_rifiuta_il_byte_nullo(tmp_path, ids, v):
    rec = da_j(_riga_j(), ids, _meta(tmp_path))
    rec['evidence']['sentence'] = 'a\x00b'
    assert errori(rec, v)


def test_n_valido(ids, v):
    r = {
        'caso': 'neubauer',
        'codice': 'NEU-0001-N',
        'document_id': 'invented-report_da17',
        'document_title': 'Invented Report',
        'family_id': 'invented-report_33ea',
        'family_title': 'Invented Report',
        'geografie': 'No Geography',
        'geografie_iso': 'XAA',
        'tipo_atto': 'Report',
        'data': '2022-04-04',
        'pagina': '12',
        'char_start': '8779',
        'forma_trovata': 'Neubauer',
        'citazione_testuale': 'An invented sentence on the Neubauer case.',
        'url_documento': 'https://climate-laws.org/documents/invented-report_da17',
        'legame': 'compagna: Federal Constitutional Court',
    }
    rec = da_n(r, ids, 'S07-N-v3')
    assert errori(rec, v) == []
    assert rec['cited']['case_id'] == 'CL-C-000002-1'
    assert rec['citing']['geography_iso'] == ['XAA']
    assert rec['provenance']['found_by'] == 'S07-N-v3'


def test_m_senza_testo(ids, v):
    a = {
        'codice': 'URG-0001-M',
        'caso': 'Urgenda Foundation v. State of the Netherlands',
        'titolo': 'Invented title',
        'testata': 'Invented Courant',
        'data': '2013-01-12',
        'urn': '57GK-0000-0000-0000-00000-00',
        'paese_testata': 'Netherlands',
        'lingua': ['Dutch', 'Nederlands'],
        'tipo_pubblicazione': 'Krant',
        'subject': [{'nome': 'CLIMATE CHANGE', 'pct': 99}],
        'blocco': 'urg_0001-0050.zip',
        'profilo_testata': {
            'paese': 'Netherlands',
            'ambito': 'regional',
            'formato': 'newspaper',
            'editore': 'Invented',
            'wikidata_qid': 'Q1',
        },
    }
    rec = da_m(a, ids, 'ae052291ca6a')
    assert errori(rec, v) == []
    assert rec['kind'] == 'item' and rec['evidence'] is None and rec['access']['tier'] == 3
    rec['evidence'] = {'sentence': 'a sentence of the article', 'passage': None}
    assert errori(rec, v), 'the schema must refuse media text'


def test_controlla_conta_codici_doppi(tmp_path, ids, v):
    rec = da_j(_riga_j(), ids, _meta(tmp_path))
    esito = controlla([rec, json.loads(json.dumps(rec))], v)
    assert esito['conti']['duplicate codes'] == 1
    assert esito['conti']['shared anchors'] == 1
