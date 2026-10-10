"""Light tests of the scripts of `reproduce/` (the figures of the TRACE 0.1 technical report).

No network, no GPU, no Firestore: tiny synthetic inputs in tmp_path. The scripts are at `<root>/reproduce/` in the
public repository and at `<root>/pubblicazione/trace-0.1/vetrina/reproduce/` in the TRACE working tree; the tests skip
if neither exists.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = [ROOT / 'reproduce', ROOT / 'pubblicazione' / 'trace-0.1' / 'vetrina' / 'reproduce']
REPRO = next((d for d in CANDIDATES if (d / 'prepare_dataset.py').is_file()), None)
pytestmark = pytest.mark.skipif(REPRO is None, reason='reproduce/ not found')


def load(name: str):
    sys.path.insert(0, str(REPRO))
    spec = importlib.util.spec_from_file_location(f'repro_{name}', REPRO / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def judgment(code, outcome='confirmed', blind='yes', counted='yes', mf='Substantive', tf='Substantive',
             mp=('a',), tp=('a',), judged='2026-10-05', case='Urgenda'):
    return {'citation_code': code, 'cited_judgment': case, 'outcome': outcome, 'counted_in_release': counted,
            'discard_reason': '', 'judgment_round': 'Uptakes screen', 'machine_citation_function': mf,
            'team_citation_function': tf, 'machine_who_speaks': 'Party', 'team_who_speaks': 'Party',
            'machine_where_in_text': '', 'team_where_in_text': '', 'machine_principles': list(mp),
            'team_principles': list(tp), 'machine_surrounding_pages': [], 'team_surrounding_pages': [],
            'team_other_principle': '', 'blind': blind, 'codebook_version': '', 'judged_on': judged,
            'coder': 'coder A', 'second_coder': '', 'second_outcome': '', 'second_function': '',
            'second_principles': None, 'agreement_outcome': ''}


def write_jsonl(path: Path, rows) -> Path:
    path.write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
    return path


def test_blind_agreement_on_tiny_files(tmp_path) -> None:
    ba = load('blind_agreement')
    rows = [judgment('URG-0001'), judgment('URG-0002', tf='Descriptive'), judgment('URG-0003', blind='no'),
            judgment('URG-0004', blind='no', outcome='discarded', tp=())]
    tj = write_jsonl(tmp_path / 'tj.jsonl', rows)
    cit = write_jsonl(tmp_path / 'cit.jsonl', [{'citation_code': f'URG-000{i}', 'document_id': f'd{i}',
                                                'proposal_rule': 'R11'} for i in (1, 2, 3)])
    out = tmp_path / 'out.json'
    ba.main(['--team-judgments', str(tj), '--citations', str(cit), '--out', str(out)])
    res = json.loads(out.read_text())
    assert res['cieche']['conteggi']['tipo'] == [1, 2]          # one of the two blind functions agrees
    assert res['viste']['conteggi']['esito'] == [1, 2]          # one visible confirmation, one discard
    assert res['senza_atto_citante'] == ['URG-0004']            # the discarded code has no public filing


def test_team_judgments_counts() -> None:
    tj = load('team_judgments')
    rows = [judgment('URG-0001'), judgment('URG-0002', outcome='discarded', blind='no')]
    c = tj.conta(rows)
    assert (c['rows'], c['confirmed'], c['discarded'], c['counted'], c['blind']) == (2, 1, 1, 2, 1)
    assert tj.contata('confermata', 'verified') and not tj.contata('confermata', 'proposed')


def test_prepare_dataset_check(tmp_path) -> None:
    pd = load('prepare_dataset')
    write_jsonl(tmp_path / 'trace-0.1-citations.jsonl', [
        {'citation_code': 'URG-0001', 'document_id': 'd1', 'cited_judgment': 'Urgenda',
         'review_status': 'checked by the team', 'five_readings': 'yes', 'proposal_rule': 'R11',
         'reference_kind': 'named'},
        {'citation_code': 'URG-0002', 'document_id': 'd1', 'cited_judgment': 'Urgenda',
         'review_status': 'proposed by the machine, not yet checked', 'five_readings': 'no', 'proposal_rule': 'R15',
         'reference_kind': 'descriptive'}])
    write_jsonl(tmp_path / 'trace-0.1-team-judgments.jsonl', [judgment('URG-0001')])
    out = pd.check(type('A', (), {'dataset': str(tmp_path)})())
    assert out['citations'] == 2 and out['documents'] == 1 and out['checked_by_the_team'] == 1
    assert out['counted_confirmations_equal_checked_citations'] is True


def test_krippendorff_alpha_reference_example() -> None:
    pytest.importorskip('numpy')  # the alpha script needs numpy, not a dependency of the package
    ka = load('krippendorff_alpha')
    assert round(ka.prova(), 3) == 0.743                          # Krippendorff (2011)


def test_count_gate_rule() -> None:
    import collections
    cg = load('count_gate')
    row = {'proposto_rete': 'lessicale'}
    assert cg.entra(row, collections.Counter({'caso': 3, 'omonimo': 2}))[0]
    assert not cg.entra({'proposto_rete': 'descrittiva'}, collections.Counter({'caso': 3, 'omonimo': 2}))[0]
    assert cg.entra({'esito': 'confermata'}, None)[0]


def test_t04_seeds_summary(tmp_path) -> None:
    ts = load('t04_seeds')

    def m(f1, base):
        ins = {'addestrato': {'principi': {'f1': f1}}, 'base': {'principi': {'f1': base}}}
        return {'insiemi': {'giuria137 (appaiate)': ins, 'appaiate': ins}, 'appaiate': 10, 'righe_addestrato': 10,
                'differenza_f1_giuria137': [0, 0], 'differenza_f1_appaiate': [0, 0]}
    (tmp_path / 'fatte.json').write_text('{}')
    (tmp_path / 'misura_originale.json').write_text(json.dumps(m(0.75, 0.73)))
    r = ts.misura(tmp_path, tmp_path, 'b', 'd', tmp_path / 'out.json', AR=None)
    assert r['semi']['f1_giuria137']['n'] == 1 and r['semi']['f1_giuria137']['media'] == 0.75


@pytest.mark.parametrize('script', ['train_t04', 't04_seeds', 'compare_t04', 'prepare_dataset', 'blind_agreement',
                                    'krippendorff_alpha', 'count_gate'])
def test_help_without_heavy_imports(script) -> None:
    if script == 'krippendorff_alpha':
        pytest.importorskip('numpy')
    code = (f'import sys; sys.argv = ["{script}", "--help"]; sys.path.insert(0, {str(REPRO)!r});\n'
            f'import runpy\ntry:\n    runpy.run_path({str(REPRO / (script + ".py"))!r}, run_name="__main__")\n'
            'except SystemExit as e:\n    assert e.code in (0, None), e.code\n'
            'assert "torch" not in sys.modules and "google.cloud.firestore" not in sys.modules')
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, cwd=str(ROOT))
    assert r.returncode == 0, r.stderr
    assert 'usage' in r.stdout


def test_train_t04_arguments() -> None:
    tr = load('train_t04')
    a = tr.parser().parse_args(['addestra', '--root', '.', '--', '--piega', '0'])
    assert a.fase == 'addestra' and a.frozen_args[-2:] == ['--piega', '0']
    assert 'torch' not in sys.modules
