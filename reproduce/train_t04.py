"""TRAINING T04 (TRACE-Reranker, reasoning: Qwen3.5-9B with a LoRA adapter), from the frozen code of TRACE 0.1.

This script does not change the training: it runs the frozen copy in versioni/T04/ (published in the repository as
`versioni/T04/`), after checking that every frozen file has the SHA-256 written in the registry entry T04 of
versioni/registro.json. The frozen files are:

  addestra_reranker_ragiona.py  sha256 5cbdf3cd77df97fd6362d769330c2c3ec32266927934a2e82068be4b6ccf4479
  ragionamento.py               sha256 5e3b654a84afdce0f59d831b4281d86975d38b94ad824a6d47f7e879caf498fd
  ragionamento_corri.py         sha256 7f8405fe3c6bdb5955bb10fea4cdfeee6340c79d3e491a261a7bfe23f8f61fc6
  freni.py                      sha256 0268ff53ecee8c7dd6c6541edbb7ff2645cb699218026768d6bdf0d41c0d1f89
  istruzioni_intestazione_e_regole.txt, istruzioni_domanda_e_formato.txt, esempi_di_addestramento_id.txt
                                (SHA-256 in the registry entry T04, field "istruzioni")

The frozen code reads its inputs under a project root laid out as the TRACE working tree (training/ragionamento/...,
cited-cases/); --root gives that root (default: TRACE_ROOT or the current folder). `_t04.py` sets the root inside the
frozen code and gives it the two helpers it imported from the working tree (see there); nothing else is changed.

THE STEPS (sub-commands of the frozen script; the options after the step are passed to it unchanged):
  costruisci   (CPU) dati.jsonl.gz: the answers of the untrained 9B (--esiti q9_rrl.jsonl), the team judgment (only to
               choose, never in the question), the filter and the 4 folds by citing filing (seed 20261005). Reads the
               database snapshot training/s08/banca_2026-10-04_171547.json.gz, training/ragionamento/verita.json and
               insieme.json, and the blind samples training/cieco_*.json (never in training).
  prova-secca  (CPU, needs torch, transformers, peft) a tiny model with the same architecture: trains two steps, merges,
               checks that the merged model gives the same logits as the adapter. Does not load the 9B.
  fumo         (GPU) one forward-backward pass on the real 9B with the longest sequence that fits.
  addestra     (GPU) the LoRA of one fold (--piega k, k = 0..3) or of all useful rows (--finale), --pesi <Qwen3.5-9B>,
               --dati dati.jsonl.gz, --adattatore <file .pt>. Settings of the published adapter: rank 16, alpha 32,
               dropout 0.05, 3 epochs, lr 1e-4, 8 examples per update, up to 28,000 tokens, bfloat16, seed 20261005
               (the defaults of the frozen script).
  fondi        (GPU) adds the adapter to the original weights (--pesi, --adattatore, --uscita) for vLLM.
  richieste    the RRL requests of the rows of one fold (--dati, --richieste, --piega, --uscita). The answers of each
               fold's adapter were produced on ReCaS-Bari with ragionamento_corri.py and vLLM; that runner imports
               `chiamata_deepseek`, which is not part of the T04 frozen copy, so it is not wrapped here.
  misura       (CPU) F1, precision and recall on the principles against the team and against the untrained 9B
               (--base q9_rrl.jsonl, --addestrato <answers of the 4 folds>, --dati, --uscita). For the nine seeds of
               the technical report use reproduce/t04_seeds.py, which runs this same step.
  verify       (this script) only checks the SHA-256 of the frozen files against the registry.

Published result (registry entry T04): adapter training/ragionamento/addestra/adattatori/finale.pt, sha256
6ae7468c13fb9a8024dbb600e3d73e7dfc1c2230830caa61856426228db8096e, and the same tensors in peft format on Zenodo
(adapter_model.safetensors, sha256 1c12cb735425b163370fffa928282e5711bfd15570cf9e385002c7be68f2758a). Base model
Qwen/Qwen3.5-9B, revision c202236235762e1c871ad0ccb60c8ee5ba337b9a. Software of the run: torch 2.14.0, transformers
5.17.0, peft 0.21.0, on one NVIDIA H100 80GB (HTCondor job 1917420, about 20 minutes). GPU training is not bit-for-bit
deterministic: a new run gives an adapter with the same recipe, not the same bytes (the nine-seed measure is how the
report describes that spread).

Inputs not published: dati.jsonl.gz contains the texts of the filings (it is not redistributed; the ids of its 94
training rows are versioni/T04/esempi_di_addestramento_id.txt), the database snapshot and the team judgments outside the
dataset. The texts of the filings are in the restricted index (DOI 10.5281/zenodo.23116960, on request).

Usage:
  python reproduce/train_t04.py verify
  python reproduce/train_t04.py costruisci --root <project root> -- --esiti q9_rrl.jsonl --richieste rrl.jsonl.gz
  python reproduce/train_t04.py addestra --root <project root> -- --pesi <Qwen3.5-9B> --piega 0 --adattatore piega0.pt
  python reproduce/train_t04.py misura --root <project root> -- --addestrato tutte.jsonl --uscita misura.json
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _t04
from _common import project_root

FASI = ('costruisci', 'prova-secca', 'fumo', 'addestra', 'fondi', 'richieste', 'misura')


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description='Run the frozen T04 training code (versioni/T04/) after checking its SHA-256 against the registry.',
        epilog='Options after "--" go to the frozen script unchanged (see the docstring of this file for each step).')
    ap.add_argument('fase', choices=(*FASI, 'verify'), help='step of the frozen script, or verify')
    ap.add_argument('--t04-dir', default=str(_t04.default_t04_dir()), help='frozen copy of T04 (default: versioni/T04)')
    ap.add_argument('--registry', default=str(_t04.default_registry()), help='versioni/registro.json')
    ap.add_argument('--root', help='project root laid out as the TRACE working tree (default: TRACE_ROOT or cwd)')
    ap.add_argument('--skip-sha-check', action='store_true', help='run even if a frozen file differs from the registry')
    ap.add_argument('frozen_args', nargs=argparse.REMAINDER, help='options for the frozen script, after "--"')
    return ap


def main(argv=None) -> int:
    a = parser().parse_args(argv)
    t04_dir = pathlib.Path(a.t04_dir)
    esiti = _t04.check_sha256(t04_dir, pathlib.Path(a.registry))
    for nome, ok in esiti.items():
        print(f'{"ok  " if ok else "DIFF"} {nome}')
    if a.fase == 'verify':
        return 0 if all(esiti.values()) else 1
    if not all(esiti.values()) and not a.skip_sha_check:
        print('a frozen file differs from the registry: not running (--skip-sha-check overrides)', file=sys.stderr)
        return 1
    _, ar = _t04.load(t04_dir, project_root(a.root))
    resto = [x for x in a.frozen_args if x != '--']
    sys.argv = [str(t04_dir / 'addestra_reranker_ragiona.py'), a.fase, *resto]
    ar.main()
    return 0


if __name__ == '__main__':
    sys.exit(main())
