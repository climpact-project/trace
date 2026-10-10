"""KRIPPENDORFF'S ALPHA OF THE REPEATED DEEPSEEK READINGS (02/10/2026): how reliable the machine is with itself.

Original: `tools/misura_alfa.py` of the TRACE working tree (frozen with TRACE 0.1). Same computation; the project root
and the output are arguments; the reading helpers of `tools/stabilita_deepseek.py` are copied in `_stabilita.py`; the
operations journal (`tools/giornale.py`) is left out (it records the run, it computes nothing). Italian strings written
into the outputs are data.

Why. `stabilita_deepseek.py` says how often two readings give the same set of principles and the same type. The paper
needs the chance-corrected measure: Krippendorff's alpha, with its confidence interval. A principle present almost always
(or almost never) gives a high percentage agreement even between readers who toss a coin: for this the percentage
agreement and the prevalence are written next to alpha, so the effect of the correction can be seen.

What is measured, per case and per kind of reading (type L03, principles L04, principles L05). Every reading is a
"coder":
  dentro    the two readings of the same run, on the rows of the files in use (reading 1 against reading 2);
  fra_giri  the re-reading of 02/10 (`*_stab.jsonl`) against the reading in the platform, reading 1 with reading 1, on
            the same pairs as `stabilita_deepseek.py` (same files, same skipped readings);
  quattro   the four readings of the re-read rows (two of the original run, two of the re-run), alpha with 4 coders.
The re-reading exists only for type and L04: for L05 only "dentro".
- type: nominal alpha on `tipo_citazione`;
- principles: binary alpha PER PRINCIPLE (present/absent), and the plain mean over the principles (macro).
Failed readings (empty or unreadable answer, `esito` ILLEGGIBILE, `grezzo`) are missing values, as in
`stabilita_deepseek.py`: they do not count as "no principle". The principle names are brought back to the list of the
case (`cited-cases/<case>.yaml`) as the composition does (`carica_ripresa.py`): without prefix, and typos with
similarity >= 0.85; codes outside the list are counted and do not enter the per-principle alpha.
95% interval: percentile bootstrap, 1,000 resamples of the rows, seed 20261002.
Alpha is computed here (no external library) and checked at start on the example of Krippendorff (2011), "Computing
Krippendorff's Alpha-Reliability", 4 coders and 12 units with missing values: nominal alpha 0.743.

Inputs (not published: the raw DeepSeek V4 Flash readings of the working tree, read only), under --root:
  training/lessicali_<case>_deepseek[_v2|_v10|_stab].jsonl, training/principi/<case>_ripresa_deepseek_*.jsonl,
  cited-cases/casi.yaml and cited-cases/<case>.yaml (published in the repository).

Usage:  python reproduce/krippendorff_alpha.py --root <project root> --out training/misure/alfa_2026-10-02
Writes <out>.json and <out>.md.
"""
# The code keeps the frozen original line for line (names and long lines are not restyled).
# ruff: noqa: B023, B905, E501, E702, E741, N803, N806, N812, RUF046, SIM115
import argparse
import collections
import difflib
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _stabilita as S  # same reading rules, same files of the re-reading
from _common import Cases, project_root

SEME, B = 20261002, 1000
# set by main() from the arguments (originally derived from the location of the script)
QUI = T = P = USCITA = None
CASI = []
IN_USO = {}


def in_uso(T, P, CASI):
    """THE FILES IN USE (02/10/2026), read one after the other (for the same row the last one wins, as in the loads):
    type: Urgenda v2 (codebook with the footnote rule) plus v10 (the new rows), the others the first reading;
    L04: for the historical series (Urgenda) the reading of 27/09 plus "l04nuove"; for the new series the series reading;
    L05: for the historical series v2; for the new series (P05 Neubauer and Future Generations, P09 ICJ) the series reading."""
    return {
        'tipo': {c: [T/f'lessicali_{c}_deepseek.jsonl'] for c in CASI} | {
            'urgenda': [T/'lessicali_urgenda_deepseek_v2.jsonl', T/'lessicali_urgenda_deepseek_v10.jsonl']},
        'L04': {'urgenda': [P/'urgenda_ripresa_deepseek.jsonl', P/'urgenda_ripresa_deepseek_l04nuove.jsonl'],
                'neubauer': [P/'neubauer_ripresa_deepseek_l04P05.jsonl'], 'future-generations': [P/'future-generations_ripresa_deepseek_l04P05.jsonl'],
                'klimaseniorinnen': [P/'klimaseniorinnen_ripresa_deepseek_l04nuove.jsonl'],
                'cig-parere-clima': [P/'cig-parere-clima_ripresa_deepseek_l04P09.jsonl'], 'idh-oc-32-25': [P/'idh-oc-32-25_ripresa_deepseek_l04nuove.jsonl']},
        'L05': {'urgenda': [P/'urgenda_ripresa_deepseek_v2.jsonl'], 'neubauer': [P/'neubauer_ripresa_deepseek_P05.jsonl'],
                'future-generations': [P/'future-generations_ripresa_deepseek_P05.jsonl'],
                'klimaseniorinnen': [P/'klimaseniorinnen_ripresa_deepseek_v2.jsonl'],
                'cig-parere-clima': [P/'cig-parere-clima_ripresa_deepseek_P09.jsonl'], 'idh-oc-32-25': [P/'idh-oc-32-25_ripresa_deepseek_v2.jsonl']},
    }


# ── alpha ──────────────────────────────────────────────────────────────

def matrice(unita):
    """From a list of units (every unit = list of the coders' values, None if missing) to the count matrix n_uc, only
    the units with at least two values (the only ones that make pairs, Krippendorff's rule)."""
    cat = sorted({v for u in unita for v in u if v is not None}, key=str)
    idx = {c: k for k, c in enumerate(cat)}
    righe = []
    for u in unita:
        v = [x for x in u if x is not None]
        if len(v) >= 2:
            r = np.zeros(max(len(cat), 1))
            for x in v:
                r[idx[x]] += 1
            righe.append(r)
    return np.array(righe) if righe else np.zeros((0, max(len(cat), 1)))


def alfa_pesi(n_uc, W):
    """Nominal alpha for every row of weights W (B x U: how many times every unit enters the resample; a row of all 1
    is the true data). alpha = 1 - (n-1) * sum_u d_u / (n^2 - sum_c n_c^2),
    with d_u = (m_u^2 - sum_c n_uc^2) / (m_u - 1), the discordant pairs of the unit."""
    m = n_uc.sum(1)
    d = (m ** 2 - (n_uc ** 2).sum(1)) / (m - 1)
    Do = W @ d
    nc = W @ n_uc
    n = nc.sum(1)
    De = n ** 2 - (nc ** 2).sum(1)
    with np.errstate(divide='ignore', invalid='ignore'):
        a = 1 - (n - 1) * Do / De
    return np.where(De > 0, a, np.nan)


def accordo(n_uc):
    """pairwise percentage agreement: agreeing pairs over possible pairs, within the units"""
    m = n_uc.sum(1)
    tot = (m * (m - 1)).sum()
    return float((n_uc * (n_uc - 1)).sum() / tot) if tot else None


def prova():
    """The example of Krippendorff (2011): nominal alpha 0.743."""
    N = None
    A = [1, 2, 3, 3, 2, 1, 4, 1, 2, N, N, N]
    Bc = [1, 2, 3, 3, 2, 2, 4, 1, 2, 5, N, 3]
    C = [N, 3, 3, 3, 2, 3, 4, 2, 2, 5, 1, N]
    D = [1, 2, 3, 3, 2, 4, 4, 1, 2, 5, 1, N]
    n_uc = matrice(list(zip(A, Bc, C, D)))
    a = float(alfa_pesi(n_uc, np.ones((1, len(n_uc))))[0])
    assert round(a, 3) == 0.743, a
    # and two coders without missing values, binary, computed by hand: 10 units, 8 agreeing
    x = [(1, 1), (1, 1), (0, 0), (0, 0), (0, 0), (1, 0), (0, 1), (1, 1), (0, 0), (0, 0)]
    n_uc = matrice(x)
    # n=20, n_1=8, n_0=12; D_o = 2 discordant units * 2 ordered pairs / 1 = 4; De = 400 - 64 - 144 = 192
    assert abs(float(alfa_pesi(n_uc, np.ones((1, 10)))[0]) - (1 - 19 * 4 / 192)) < 1e-12
    return a


# ── the readings ───────────────────────────────────────────────────────

def carica(files):
    out = {}
    for f in files:
        if f.exists():
            for l in open(f, encoding='utf-8'):
                x = json.loads(l); out[x['id']] = x
    return out


def letture(x):
    l = (x or {}).get('letture') or []
    return [l[k] if k < len(l) else None for k in range(2)]


def sonde(caso):
    import yaml
    return [s['id'].split('.')[-1] for s in yaml.safe_load(open(QUI/'cited-cases'/f'{caso}.yaml', encoding='utf-8'))['semantic_queries']]


def canonici(insieme, elenco, fuori):
    """the names brought back to the list of the case as in carica_ripresa.canonico; those left out are counted"""
    out = set()
    for q in insieme:
        if q in elenco:
            out.add(q); continue
        m = difflib.get_close_matches(q, elenco, n=1, cutoff=0.85)
        if m:
            out.add(m[0])
        else:
            fuori[q] += 1
    return frozenset(out)


# ── the measures ───────────────────────────────────────────────────────

def pesi(U, rng):
    return np.vstack([np.ones(U), rng.multinomial(U, np.full(U, 1 / U), size=B)]) if U else np.zeros((B + 1, 0))


def riassunto(valori):
    v = valori[1:]; v = v[~np.isnan(v)]
    a = valori[0]
    return {'alfa': None if np.isnan(a) else round(float(a), 3),
            'ic95': [round(float(np.percentile(v, 2.5)), 3), round(float(np.percentile(v, 97.5)), 3)] if len(v) else None,
            'ricampionamenti_validi': int(len(v))}


def misura_tipo(unita, rng):
    n_uc = matrice(unita)
    W = pesi(len(n_uc), rng)
    r = riassunto(alfa_pesi(n_uc, W)) if len(n_uc) else {'alfa': None, 'ic95': None}
    cat = collections.Counter(v for u in unita for v in u if v is not None)
    return {'righe': int(len(n_uc)), 'codificatori': len(unita[0]) if unita else 0, **r, 'accordo_percentuale': accordo(n_uc) and round(accordo(n_uc), 3),
            'letture_mancanti': sum(v is None for u in unita for v in u), 'categorie': dict(cat.most_common())}


def misura_principi(unita, elenco, rng):
    """units: list of rows, every row = list of sets (or None) per coder"""
    unita = [u for u in unita if sum(v is not None for v in u) >= 2]
    U = len(unita)
    W = pesi(U, rng)
    per, matrici = {}, []
    for p in elenco:
        bin_ = [[None if v is None else int(p in v) for v in u] for u in unita]
        n_uc = matrice(bin_)
        if n_uc.shape[1] < 2:                 # the principle never appears (or always): alpha undefined
            n_uc = np.hstack([n_uc, np.zeros((len(n_uc), 2 - n_uc.shape[1]))])
        valori = alfa_pesi(n_uc, W) if U else np.full(B + 1, np.nan)
        matrici.append(valori)
        tutte = [x for u in bin_ for x in u if x is not None]
        per[p] = {'prevalenza': round(sum(tutte) / len(tutte), 3) if tutte else None, **riassunto(valori),
                  'accordo_percentuale': accordo(n_uc) and round(accordo(n_uc), 3)}
    M = np.vstack(matrici) if matrici else np.full((1, B + 1), np.nan)
    with np.errstate(all='ignore'):
        macro = np.nanmean(M, axis=0)          # mean over the defined principles, for every resample
    acc = [per[p]['accordo_percentuale'] for p in elenco if per[p]['accordo_percentuale'] is not None]
    # same set and Jaccard between the first two valid readings of every row (the definitions of stabilita_deepseek.py)
    # (not computed with four coders: the first two would be the two readings of the same run)
    coppie = [[v for v in u if v is not None] for u in unita] if unita and len(unita[0]) == 2 else []
    U2 = len(coppie)
    return {'righe': U, 'codificatori': len(unita[0]) if unita else 0,
            'macro': {**riassunto(macro), 'accordo_percentuale_medio': round(sum(acc) / len(acc), 3) if acc else None,
                      'principi_con_alfa': int(sum(per[p]['alfa'] is not None for p in elenco))},
            'stesso_insieme': round(sum(a == b for a, b in coppie) / U2, 3) if U2 else None,
            'jaccard_medio': round(sum(S.jaccard(a, b) for a, b in coppie) / U2, 3) if U2 else None,
            'per_principio': per}


def main(argv=None):
    global QUI, T, P, USCITA, CASI, IN_USO
    ap = argparse.ArgumentParser(description="Krippendorff's alpha of the repeated DeepSeek V4 Flash readings (02/10/2026).")
    ap.add_argument('--root', help='project root with training/ and cited-cases/ (default: TRACE_ROOT or the current folder)')
    ap.add_argument('--out', default='training/misure/alfa_2026-10-02',
                    help='output prefix, relative to the root unless absolute; .json and .md are added')
    a = ap.parse_args(argv)
    QUI = project_root(a.root)
    T, P = QUI/'training', QUI/'training'/'principi'
    USCITA = QUI/a.out if not pathlib.Path(a.out).is_absolute() else pathlib.Path(a.out)
    CASI = list(Cases(QUI).CASI)
    IN_USO = in_uso(T, P, CASI)
    a_prova = prova()
    print(f'prova sull\'esempio di Krippendorff (2011): alfa nominale {a_prova:.4f} (atteso 0,743)')
    rng = np.random.default_rng(SEME)
    out = {'data': '2026-10-02', 'seme': SEME, 'ricampionamenti': B, 'prova_krippendorff_2011': round(a_prova, 4),
           'file_in_uso': {k: {c: [str(f.relative_to(QUI)) for f in v] for c, v in d.items()} for k, d in IN_USO.items()},
           'file_rilettura': {'tipo': {c: [f"training/lessicali_{c}_deepseek{'_' + S.TIPO[c] if c in S.TIPO else ''}.jsonl",
                                           f'training/lessicali_{c}_deepseek_stab.jsonl'] for c in CASI},
                              'L04': {c: [f'training/principi/{c}_ripresa_deepseek_{S.L04[c]}.jsonl',
                                          f'training/principi/{c}_ripresa_deepseek_stab.jsonl'] for c in CASI}},
           'casi': {}}
    for caso in CASI:
        elenco = sonde(caso)
        R = out['casi'][caso] = {'principi_elenco': elenco}
        # type
        d = carica(IN_USO['tipo'][caso])
        R['tipo'] = {'dentro': misura_tipo([[S.tipo(l) for l in letture(x)] for x in d.values()], rng)}
        prima = S.carica(T/f"lessicali_{caso}_deepseek{'_' + S.TIPO[caso] if caso in S.TIPO else ''}.jsonl")
        dopo = S.carica(T/f'lessicali_{caso}_deepseek_stab.jsonl')
        com = [i for i in dopo if i in prima]
        R['tipo']['fra_giri'] = misura_tipo([[S.tipo(letture(prima[i])[0]), S.tipo(letture(dopo[i])[0])] for i in com], rng)
        R['tipo']['quattro'] = misura_tipo([[S.tipo(l) for l in letture(prima[i]) + letture(dopo[i])] for i in com], rng)
        # principles
        for tipo_l in ('L04', 'L05'):
            fuori = collections.Counter()
            def ins(l):
                s = S.principi(l)
                return None if s is None else canonici(s, elenco, fuori)
            d = carica(IN_USO[tipo_l][caso])
            R[tipo_l] = {'dentro': misura_principi([[ins(l) for l in letture(x)] for x in d.values()], elenco, rng)}
            if tipo_l == 'L04':
                prima = S.carica(P/f'{caso}_ripresa_deepseek_{S.L04[caso]}.jsonl')
                dopo = S.carica(P/f'{caso}_ripresa_deepseek_stab.jsonl')
                com = [i for i in dopo if i in prima]
                R[tipo_l]['fra_giri'] = misura_principi([[ins(letture(prima[i])[0]), ins(letture(dopo[i])[0])] for i in com], elenco, rng)
                R[tipo_l]['quattro'] = misura_principi([[ins(l) for l in letture(prima[i]) + letture(dopo[i])] for i in com], elenco, rng)
                # the definition of stabilita_deepseek.py, without bringing the names back to the list (to compare with its numbers)
                cp = [(S.principi(letture(prima[i])[0]), S.principi(letture(dopo[i])[0])) for i in com]
                cp = [(a, b) for a, b in cp if a is not None and b is not None]
                R[tipo_l]['fra_giri']['stesso_insieme_come_stabilita_deepseek'] = round(sum(a == b for a, b in cp) / len(cp), 3) if cp else None
            R[tipo_l]['codici_fuori_elenco'] = dict(fuori.most_common())
        print(caso, 'tipo', R['tipo']['dentro']['alfa'], R['tipo']['fra_giri']['alfa'],
              'L04', R['L04']['dentro']['macro']['alfa'], R['L04']['fra_giri']['macro']['alfa'],
              'L05', R['L05']['dentro']['macro']['alfa'], flush=True)
    USCITA.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(USCITA.with_suffix('.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    USCITA.with_suffix('.md').write_text(testo(out), encoding='utf-8')


def f(x):
    if not x or x.get('alfa') is None:
        return 'n.d.'
    ic = x.get('ic95')
    return f"{x['alfa']:.3f} [{ic[0]:.3f}, {ic[1]:.3f}]" if ic else f"{x['alfa']:.3f}"


def testo(o):
    r = ["# Krippendorff's alpha of repeated DeepSeek readings (02/10/2026)", '',
         f"Generated by `tools/misura_alfa.py`. Each reading is a coder. 95% CI: percentile bootstrap over rows, "
         f"{o['ricampionamenti']} resamples, seed {o['seme']}. Failed readings (empty/unparseable) are missing values. "
         f"Implementation checked on Krippendorff (2011) example: nominal alpha {o['prova_krippendorff_2011']} (expected 0.743).", '',
         '- **within**: reading 1 vs reading 2 of the same run, all rows of the files in use.',
         '- **between**: 02/10 re-run (`*_stab`) reading 1 vs original reading 1 (same pairs as `stabilita_deepseek.py`).',
         '- **4 coders**: both readings of both runs on the re-read rows.', '',
         '## Citation type (nominal alpha)', '', '| case | within n | within alpha [95% CI] | % agr | between n | between alpha [95% CI] | % agr | 4 coders alpha |',
         '|---|---|---|---|---|---|---|---|']
    for c, R in o['casi'].items():
        t = R['tipo']
        r.append(f"| {c} | {t['dentro']['righe']} | {f(t['dentro'])} | {t['dentro']['accordo_percentuale']} | {t['fra_giri']['righe']} | "
                 f"{f(t['fra_giri'])} | {t['fra_giri']['accordo_percentuale']} | {f(t['quattro'])} |")
    r += ['', '## Principles: macro average of per-principle binary alpha', '',
          '| case | kind | n | macro alpha [95% CI] | mean % agr | same set | Jaccard |', '|---|---|---|---|---|---|---|']
    for c, R in o['casi'].items():
        for k, nome in (('L04', 'dentro'), ('L04', 'fra_giri'), ('L04', 'quattro'), ('L05', 'dentro')):
            x = R[k][nome]
            et = {'dentro': 'within', 'fra_giri': 'between', 'quattro': '4 coders'}[nome]
            r.append(f"| {c} | {k} {et} | {x['righe']} | {f(x['macro'])} | {x['macro']['accordo_percentuale_medio']} | {x['stesso_insieme']} | {x['jaccard_medio']} |")
    r += ['', '## Per principle: prevalence, alpha, % agreement', '']
    for c, R in o['casi'].items():
        r += [f'### {c}', '', '| principle | L04 prev | L04 within alpha | % | L04 between alpha | % | L05 prev | L05 within alpha | % |',
              '|---|---|---|---|---|---|---|---|---|']
        for p in R['principi_elenco']:
            a, b, d = R['L04']['dentro']['per_principio'][p], R['L04']['fra_giri']['per_principio'][p], R['L05']['dentro']['per_principio'][p]
            r.append(f"| {p} | {a['prevalenza']} | {f(a)} | {a['accordo_percentuale']} | {f(b)} | {b['accordo_percentuale']} | "
                     f"{d['prevalenza']} | {f(d)} | {d['accordo_percentuale']} |")
        fu = {k: R[k]['codici_fuori_elenco'] for k in ('L04', 'L05') if R[k]['codici_fuori_elenco']}
        if fu:
            r += ['', f'Off-list codes (excluded from per-principle alpha): {json.dumps(fu, ensure_ascii=False)}']
        r.append('')
    return '\n'.join(r) + '\n'

if __name__ == '__main__':
    main()
