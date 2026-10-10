"""T04 ACROSS SEEDS (09/10/2026): the F1 on the principles of every complete seed of T04 and its summary, the figure
"9 seeds, 0.718 +/- 0.028 on the 137 rows of the jury" of the technical report and of the registry entry T04.

Original: `tools/t04_semi.py` of the TRACE working tree (frozen with TRACE 0.1). Same computation; paths are
arguments. The original ran the measuring step of the training script in a subprocess
(`addestra_reranker_ragiona.py misura`, against the same untrained 9B); here the same step (`Misuratore.misura`) runs in
process from the frozen copy versioni/T04/ (see `_t04.py`; its measuring code is the same as the working-tree script's).
Italian strings and keys written into the outputs are data.

An "arm" is a seed (s1..s12) or a re-extraction of the original adapters (sorig1, sorig2); it is complete when its 4
folds have their file in the pool*_fatti lists of ReCaS (collected in fatte.json). For every complete arm: the same
measure as the first round, output misura_<arm>.json. The summary (F1 on the 137 rows of the jury and on the paired
rows, difference from the untrained model, per arm; mean, standard deviation, t interval over the seeds) goes to --out.
The rule of decision was written before (training/misure/T04-SEMI-2026-10-09.md, not published).

Inputs (not published: they hold the texts of the filings or the team judgments outside the dataset), read only:
  --seeds-dir  fatte.json, esiti/s<arm>_piega<k>.jsonl (the answers of each fold's adapter), misura_originale.json
               (the measure of the first round, 05/10/2026);
  --base       q9_rrl.jsonl, the answers of the untrained Qwen3.5-9B;
  --data       dati.jsonl.gz, the training set of T04 with folds (SHA-256 in the registry entry T04);
  --verita, --insieme  the team judgments and the rows of the measure (training/ragionamento/verita.json, insieme.json).
Writes s<arm>_tutte.jsonl and misura_s<arm>.json into --work-dir (default: --seeds-dir) and the summary into --out.

`collect` is the first step of the original (rsync and ssh from the ReCaS cluster); it needs an account there.

Usage:
  python reproduce/t04_seeds.py measure --seeds-dir training/ragionamento/semi --base .../q9_rrl.jsonl \\
      --data .../dati.jsonl.gz --verita .../verita.json --insieme .../insieme.json --out t04_semi_2026-10-09.json
"""
# The code keeps the frozen original line for line (names and long lines are not restyled).
# ruff: noqa: E501, E702, E741, N803, N806, SIM115
import argparse
import contextlib
import io
import json
import math
import pathlib
import statistics
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _t04
from _common import project_root

T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179}


def raccogli(S, remoto, host):
    """collect: the outputs of the seed jobs from the cluster (rsync) and the list of finished folds (ssh)."""
    S.mkdir(parents=True, exist_ok=True)
    subprocess.run(['rsync', '-a', '-e', 'ssh -o ConnectTimeout=20', remoto + 'esiti/', str(S / 'esiti') + '/'], check=True)
    fatte = subprocess.run(['ssh', '-o', 'ConnectTimeout=20', host, 'cd ~/trace/misure/ragionamento/semi && cat pool2_fatti/* pool3_fatti/* 2>/dev/null'],
                           capture_output=True, text=True).stdout.split('\n')
    bracci = {}
    for r in fatte:
        if r.strip():
            b, p = r.split()
            bracci.setdefault(b, set()).add(int(p))
    json.dump({b: sorted(p) for b, p in bracci.items()}, open(S / 'fatte.json', 'w'), indent=1)
    print('piegature finite per braccio:', {b: sorted(p) for b, p in sorted(bracci.items())})


def misura(S, W, base, dati, uscita, AR):
    """measure: every complete arm with the measuring step of the training script, then the summary."""
    fatte = json.load(open(S / 'fatte.json'))
    righe = []
    for b, pieghe in sorted(fatte.items()):
        if sorted(pieghe) != [0, 1, 2, 3]:
            continue
        tag = f's{b}'
        tutte = W / f'{tag}_tutte.jsonl'
        with open(tutte, 'w', encoding='utf-8') as f:
            for p in range(4):
                f.write(open(S / 'esiti' / f'{tag}_piega{p}.jsonl', encoding='utf-8').read())
        m = W / f'misura_{tag}.json'
        # the original ran `addestra_reranker_ragiona.py misura` with capture_output=True: same step, output kept quiet
        with contextlib.redirect_stdout(io.StringIO()):
            AR.Misuratore(str(base), str(tutte), str(dati), str(m)).misura()
        righe.append((b, json.load(open(m))))
    orig = json.load(open(S / 'misura_originale.json'))

    def riga(M):
        I = M['insiemi']
        return {'f1_giuria137': I['giuria137 (appaiate)']['addestrato']['principi']['f1'],
                'f1_base_giuria137': I['giuria137 (appaiate)']['base']['principi']['f1'],
                'f1_appaiate': I['appaiate']['addestrato']['principi']['f1'],
                'f1_base_appaiate': I['appaiate']['base']['principi']['f1'],
                'appaiate': M['appaiate'], 'righe_addestrato': M['righe_addestrato'],
                'ic_diff_giuria137_per_atto': M['differenza_f1_giuria137'], 'ic_diff_appaiate_per_atto': M['differenza_f1_appaiate']}
    tab = {'20261005': riga(orig)}
    tab.update({b: riga(M) for b, M in righe})

    def sintesi(chiavi):
        out = {}
        for c in ('f1_giuria137', 'f1_appaiate'):
            v = [tab[k][c] for k in chiavi]
            d = [tab[k][c] - tab[k][c.replace('f1_', 'f1_base_')] for k in chiavi]
            n = len(v)
            ds = statistics.stdev(v) if n > 1 else None
            dd = statistics.stdev(d) if n > 1 else None
            out[c] = {'n': n, 'media': round(statistics.mean(v), 4), 'ds': ds and round(ds, 4),
                      'min': min(v), 'max': max(v), 'diff_media': round(statistics.mean(d), 4),
                      'diff_ic95_t': [round(statistics.mean(d) - T95[n-1]*dd/math.sqrt(n), 4), round(statistics.mean(d) + T95[n-1]*dd/math.sqrt(n), 4)] if n > 1 else None,
                      'diff_positive': sum(x > 0 for x in d)}
        return out
    semi = [k for k in tab if not k.startswith('orig')]
    rie = [k for k in tab if k.startswith('orig')] + ['20261005']
    R = {'bracci': tab, 'semi': sintesi(semi), 'riestrazioni_originale': sintesi(rie) if len(rie) > 1 else None}
    json.dump(R, open(uscita, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for k, v in tab.items():
        print(f"{k:10s} giuria137 {v['f1_giuria137']} (base {v['f1_base_giuria137']})  appaiate {v['f1_appaiate']} (base {v['f1_base_appaiate']}, {v['appaiate']} righe)")
    print('semi:', json.dumps(R['semi'])); print('riestrazioni:', json.dumps(R['riestrazioni_originale']))
    print('scritto', uscita)
    return R


def main(argv=None):
    ap = argparse.ArgumentParser(description='T04 across seeds: F1 on the principles of every complete seed, and the summary.')
    sub = ap.add_subparsers(dest='fase', required=True)
    c = sub.add_parser('collect', help='copy the seed outputs from the cluster (needs an account there)')
    c.add_argument('--seeds-dir', required=True)
    c.add_argument('--remote', required=True, help='rsync source of the seed folder, e.g. <host>:trace/misure/ragionamento/semi/')
    c.add_argument('--host', required=True, help='ssh host of the cluster')
    m = sub.add_parser('measure', help='measure every complete arm and write the summary')
    m.add_argument('--seeds-dir', required=True, help='folder with fatte.json, esiti/ and misura_originale.json')
    m.add_argument('--work-dir', help='where s<arm>_tutte.jsonl and misura_s<arm>.json are written (default: --seeds-dir)')
    m.add_argument('--base', required=True, help='q9_rrl.jsonl: answers of the untrained Qwen3.5-9B')
    m.add_argument('--data', required=True, help='dati.jsonl.gz: the T04 training set with folds')
    m.add_argument('--verita', required=True, help='verita.json: team judgments of the measure')
    m.add_argument('--insieme', required=True, help='insieme.json: rows of the measure (jury of 137 and the others)')
    m.add_argument('--out', required=True, help='summary JSON (originally training/misure/t04_semi_2026-10-09.json)')
    m.add_argument('--t04-dir', default=str(_t04.default_t04_dir()), help='frozen copy of T04 (default: versioni/T04)')
    m.add_argument('--root', help='project root for the frozen code (cited-cases/); default TRACE_ROOT or current folder')
    a = ap.parse_args(argv)
    if a.fase == 'collect':
        raccogli(pathlib.Path(a.seeds_dir), a.remote, a.host)
        return None
    _, AR = _t04.load(pathlib.Path(a.t04_dir), project_root(a.root), a.verita, a.insieme)
    S = pathlib.Path(a.seeds_dir)
    W = pathlib.Path(a.work_dir) if a.work_dir else S
    W.mkdir(parents=True, exist_ok=True)
    return misura(S, W, a.base, a.data, a.out, AR)


if __name__ == '__main__':
    main()
