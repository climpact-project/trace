"""T01 (TRACE-Reranker 0.1) scores: the pure parts of ``punteggio_t01``, without GPU, weights or torch.

Where the frozen copy ``versioni/T01`` (and ``tools/prepara_training.py``) are present, the same functions are
compared with them; in the public repository, without those folders, those comparisons are skipped.
"""

from __future__ import annotations

import argparse
import ast
import gzip
import importlib.util
import json
import math
import re
import subprocess
import sys
import types
from pathlib import Path

import pytest

from tracepipe import punteggio_t01 as pt

RADICE = Path(__file__).resolve().parent.parent

CONF = {
    'nome': 'Urgenda Foundation v. State of the Netherlands',
    'forme': ['Urgenda', 'the Urgenda case', 'State of the Netherlands v. Urgenda Foundation', 'HR', 2019],
    'semantic_queries': [
        {'id': 'propria_quota', 'testo': 'Each  State must do\n its own share.'},
        {'id': 'dovere_diligenza', 'testo': 'A duty of care\tbinds the State.'},
    ],
}

CONTESTO = (
    'x' * 900
    + 'As held in [[INIZIO DEL BRANO SEGNALATO]]the Urgenda case (ECLI:NL:HR:2019:2007)[[FINE DEL BRANO SEGNALATO]]'
    + ', the ⟦State⟧   must act.\n'
    + 'y' * 900
)


def test_mascheratore_forms_ecli_and_dockets() -> None:
    m = pt.maschera_caso(CONF)
    t = 'State of the Netherlands v. Urgenda Foundation, the URGENDA case, ECLI:NL:HR:2019:2007, 19/00135, HR'
    assert m.sub(pt.SEGNAPOSTO, t) == '⟦CASO_CITATO⟧, ⟦CASO_CITATO⟧, ⟦CASO_CITATO⟧, ⟦CASO_CITATO⟧, HR'
    assert m.sub(pt.SEGNAPOSTO, '200.178.245/01 and 12/123456') == '⟦CASO_CITATO⟧ and 12/123456'
    # the longest form is consumed first: no «State of the Netherlands v.» residue
    assert 'Netherlands' not in m.sub(pt.SEGNAPOSTO, 'State of the Netherlands v. Urgenda Foundation')


def test_brano_window_markers_and_whitespace() -> None:
    d = pt.brano(CONTESTO, pt.maschera_caso(CONF))
    assert d is not None
    a = CONTESTO.find(pt.INIZIO)
    atteso = CONTESTO[a - 800 : CONTESTO.find(pt.FINE) + len(pt.FINE) + 800]
    atteso = atteso.replace(pt.INIZIO, '').replace(pt.FINE, '').replace('⟦', '').replace('⟧', '')
    atteso = (
        ' '.join(atteso.split())
        .replace('the Urgenda case', pt.SEGNAPOSTO)
        .replace('ECLI:NL:HR:2019:2007', pt.SEGNAPOSTO)
    )
    assert d == atteso
    assert d.startswith('x' * (800 - len('As held in ')) + 'As held in')
    assert 'the State must act.' in d
    assert '[[' not in d and '⟦State⟧' not in d
    assert pt.brano('no markers here', pt.maschera_caso(CONF)) is None


def test_pagine_attorno_window() -> None:
    righe = [
        {'id': 'r1', 'document_id': 'D', 'pagina': 2},
        {'id': 'r2', 'document_id': 'D', 'pagina': 3},
        {'id': 'r3', 'document_id': 'E', 'pagina': None},
    ]
    s = pt.pagine_attorno(righe, prima=2, dopo=3)
    assert s == {
        'D#p1': {'r1', 'r2'},
        'D#p2': {'r2'},
        'D#p3': {'r1'},
        'D#p4': {'r1', 'r2'},
        'D#p5': {'r1', 'r2'},
        'D#p6': {'r2'},
    }
    assert len(pt.pagine_attorno([{'id': 'r', 'document_id': 'D', 'pagina': 11}])) == 20


def test_prepara_writes_passages_then_pages(tmp_path: Path) -> None:
    indice = tmp_path / 'pagine.jsonl.gz'
    with gzip.open(indice, 'wt', encoding='utf-8') as f:
        for pid, testo in (('D#p4', 'page  four, Urgenda'), ('X#p1', 'other'), ('D#p6', 'page six')):
            f.write(json.dumps({'id': pid, 'testo': testo}) + '\n')
    righe = [
        {'id': 'r1', 'document_id': 'D', 'pagina': 5, 'contesto': CONTESTO},
        {'id': 'r2', 'document_id': 'D', 'pagina': 5, 'contesto': 'no markers'},
    ]
    e = pt.prepara(CONF, righe, indice, tmp_path / 'out' / 'c.jsonl', prima=2, dopo=3)
    out = [json.loads(x) for x in (tmp_path / 'out' / 'c.jsonl').read_text(encoding='utf-8').splitlines()]
    assert (e.righe, e.pagine, e.coppie) == (2, 2, 6)
    assert [(x['dove'], x.get('riga') or x['pagina_id'], x['principio']) for x in out] == [
        ('brano', 'r1', 'propria_quota'),
        ('brano', 'r1', 'dovere_diligenza'),
        ('vicina', 'D#p4', 'propria_quota'),
        ('vicina', 'D#p4', 'dovere_diligenza'),
        ('vicina', 'D#p6', 'propria_quota'),
        ('vicina', 'D#p6', 'dovere_diligenza'),
    ]
    assert out[0]['q'] == 'Each State must do its own share.'
    assert out[0]['pagina'] == 5
    assert out[2]['d'] == 'page four, ⟦CASO_CITATO⟧'
    assert list(out[2]) == ['pagina_id', 'dove', 'principio', 'q', 'd']
    assert list(out[0]) == ['riga', 'dove', 'pagina', 'principio', 'q', 'd']
    assert '⟦CASO_CITATO⟧' in (tmp_path / 'out' / 'c.jsonl').read_text(encoding='utf-8')  # not escaped


def test_prompt_format() -> None:
    t = pt.testo_coppia('Q', 'D')
    assert t == f'<Instruct>: {pt.ISTRUZIONE}\n<Query>: Q\n<Document>: D'
    p = pt.prompt_intero('Q', 'D')
    assert p.startswith('<|im_start|>system\nJudge whether the Document meets the requirements')
    assert p.endswith('<Document>: D<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n')
    assert pt.ISTRUZIONE.startswith('Judge whether the Document adopts, as its own reasoning, the legal proposition')


def test_score_from_logits() -> None:
    assert pt.punteggio_da_logit(0.0, 0.0) == pytest.approx(0.5)
    for no, si in ((1.5, -2.25), (-30.0, 12.0), (7.0, 7.5), (900.0, 901.0)):
        assert pt.punteggio_da_logit(no, si) == pytest.approx(1 / (1 + math.exp(no - si)), rel=1e-12)


def test_mean_rounding_and_lines() -> None:
    m = pt.media_semi([[0.1, 0.9], [0.2, 0.7], [0.3, 0.8]])
    assert m == pytest.approx([0.2, 0.8])
    assert pt.arrotonda(0.123456789) == 0.12346
    with pytest.raises(ValueError):
        pt.media_semi([[0.1], [0.2, 0.3]])
    c = {'riga': 'r1', 'dove': 'brano', 'pagina': 7, 'principio': 'p', 'q': 'Q', 'd': 'D'}
    assert json.dumps(pt.riga_punteggio(c, 0.2318004)) == (
        '{"riga": "r1", "dove": "brano", "pagina": 7, "principio": "p", "punteggio": 0.2318}'
    )
    v = {'pagina_id': 'D#p4', 'dove': 'vicina', 'principio': 'p', 'q': 'Q', 'd': 'D'}
    assert pt.riga_punteggio(v, 0.47209123) == {
        'pagina_id': 'D#p4',
        'dove': 'vicina',
        'principio': 'p',
        'punteggio': 0.47209,
    }
    assert pt.pezzo_di(list(range(10)), 1, 4) == [1, 5, 9]


def test_adapter_path() -> None:
    assert pt.percorso_adattatore(pt.ADATTATORI, 2, Path('/r')) == Path('/r/training/lora_qwen_rr4b_2/passata_2')
    assert pt.percorso_adattatore('/abs/s{seme}', 3, Path('/r')) == Path('/abs/s3')


def test_parser_without_torch() -> None:
    ap = argparse.ArgumentParser()
    pt.aggiungi_parser(ap.add_subparsers(dest='comando'))
    a = ap.parse_args(
        ['punteggi', 'calcola', '--coppie', 'c.jsonl', '--uscita', 'u.jsonl', '--pezzo', '1', '--pezzi', '4']
    )
    assert (a.comando, a.cosa, a.semi, a.lotto, a.max_lunghezza, a.pezzo, a.pezzi) == (
        'punteggi',
        'calcola',
        '1,2,3',
        8,
        2560,
        1,
        4,
    )


def test_import_does_not_load_torch() -> None:
    codice = (
        'import sys, tracepipe.punteggio_t01; print(any(m in sys.modules for m in ("torch", "transformers", "peft")))'
    )
    r = subprocess.run([sys.executable, '-c', codice], cwd=RADICE, capture_output=True, text=True, check=True)
    assert r.stdout.strip() == 'False'


# ── against the frozen code, when present ────────────────────────────────────────────────────────────────────


def _carica(nome: str, percorso: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(nome, percorso)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_same_constants_as_frozen_reranker() -> None:
    f = RADICE / 'versioni' / 'T01' / 'prova_riordinatori.py'
    if not f.exists():
        pytest.skip('versioni/T01 is not part of this repository')
    pytest.importorskip('numpy')
    pytest.importorskip('torch')
    mod = _carica('_t01_prova_riordinatori', f)
    assert mod.ISTR['ripresa'] == pt.ISTRUZIONE
    assert mod.ISTR['di_serie'] == pt.ISTRUZIONE_DI_SERIE
    assert (mod.PREFISSO, mod.SUFFISSO) == (pt.PREFISSO, pt.SUFFISSO)


def test_same_masking_as_frozen_tools() -> None:
    f = RADICE / 'tools' / 'prepara_training.py'
    if not f.exists():
        pytest.skip('tools/ is not part of this repository')
    albero = ast.parse(f.read_text(encoding='utf-8'))
    pezzi = [n for n in albero.body if isinstance(n, ast.FunctionDef) and n.name == 'mascheratore']
    pezzi += [n for n in albero.body if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == 'SEGNAPOSTO']
    spazio: dict[str, object] = {'re': re}
    exec(compile(ast.Module(body=pezzi, type_ignores=[]), str(f), 'exec'), spazio)
    assert spazio['SEGNAPOSTO'] == pt.SEGNAPOSTO
    forme = [str(x) for x in CONF['forme']] + [CONF['nome']]
    vecchio, nuovo = spazio['mascheratore'](forme), pt.mascheratore(forme)  # type: ignore[operator]
    assert (vecchio.pattern, vecchio.flags) == (nuovo.pattern, nuovo.flags)
    assert vecchio.sub(pt.SEGNAPOSTO, CONTESTO) == nuovo.sub(pt.SEGNAPOSTO, CONTESTO)
