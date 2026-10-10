"""T04 COMPARED WITH DEEPSEEK, T01 AND THE TEAM (07/10/2026: deciding how to use T04 in TRACE 0.2).

Original: `tools/confronto_t04.py` of the TRACE working tree (frozen with TRACE 0.1). Same computation; paths are
arguments; the frozen T04 code is loaded by `_t04.py` (as `tools/t04_tutte.t04()` did); the two helpers of
`tools/t04_tutte.py` it used (`jl`, `esito_json`) are copied below unchanged. Italian strings written into the outputs
(the .md report, keys, labels) are data.

Read only, no GPU, no database writes. Inputs (not published):
  - the answers of T04 (TRACE-Reranker "reasoning", final LoRA on Qwen3.5-9B) on all live rows: esiti/fetta*.jsonl;
  - the live rows read from Firestore on 7/10 (righe_vive.jsonl.gz): DeepSeek proposals (proposto_principi_voti,
    proposto_principi, proposto_riferimento_voti), T01 scores (proposto_punteggi_principi), team judgments (esito,
    validato_principi, validato_contesto, campione_cieco, settembre);
  - the 94 training rows of T04 (versioni/T04/esempi_di_addestramento_id.txt, published): OUT of every comparison
    with the team.

READING THE T04 ANSWERS: the same reader as the published T04 measure (Misuratore.estrai of
versioni/T04/addestra_reranker_ragiona.py, with json_risposta of the frozen versioni/T04/ragionamento.py); an answer
counts only if it is "readable" by the rule of the collect step (non-empty list of principles and "cita_il_caso"
present). T04 principles = those said "yes"; "uncertain" is not a yes (as in the published measure).

THE ARMS.
  T04      the "yes" of T04.
  DS-R11   the majority of the five readings of DeepSeek V4 Flash from the saved votes (proposto_principi_voti): a
           principle is taken if v >= n//2+1 over the n valid readings (maggioranza.soglia, the rule of R11). Without
           the paragraph map.
  DS-pub   the proposal written on the row (proposto_principi: R11..R16 depending on the row, with the paragraph map),
           i.e. the one published in TRACE 0.1 and shown to the team when proposals were visible.
  T01      the principles with T01 score >= 0.5 (proposto_punteggi_principi).

MEASURES (same definitions as the T04 card: ragionamento.prf, bootstrap by citing filing, seed 20261004, 1000 times,
percentiles 2.5 and 97.5).
  principi  P/R/F1 against the principles confirmed by the team (confirmed rows with validato_principi, all of the
            case; "nessuno" and "altro" out of the count). On the PAIRED set: rows where all four arms answer.
            Split: blind / proposal visible (validato_contesto.proposte_mostrate, then campione_cieco: the rule of
            team_judgments.py); in the 691 of the training-measure (where rules G05/G06 were born) / judged after;
            by network (lexical, descriptive, both); blind AND judged after the 691 (the cleanest subset).
  scarto    T04: "cita_il_caso" yes/no/uncertain; DeepSeek: majority of proposto_riferimento_voti ("caso" = keep);
            T01 gives no discard signal. Against the team outcome (Uptakes) and, for kept rows only, September.
  accordo   on rows without judgment, in the queue (lexical, both, descriptive): T04 against DS-R11, per row (same
            set) and per principle (Cohen's kappa); the list of doubts sorted by D = sum over the principles of the
            case of |T04 score from the verdict tokens - share of DeepSeek votes|.

Usage:  python reproduce/compare_t04.py --rows righe_vive.jsonl.gz --answers-dir esiti --insieme insieme.json \\
            --r11-judged r11_su_giudicate.json --out-dir <folder> [--root <project root>]
Writes CONFRONTO-2026-10-07.md, confronto-2026-10-07.json and dubbi-2026-10-07.csv.
"""
# The code keeps the frozen original line for line (names and long lines are not restyled).
# ruff: noqa: B905, E501, E702, F541, N803, N806, N812, RUF001, RUF059, SIM115
import argparse
import collections
import csv
import json
import pathlib
import random
import sys
import types

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _t04
from _common import jl, project_root

# set by main() from the arguments (originally derived from the location of the script)
QUI = T04 = RIGHE = ESITI = ADDESTR = INSIEME = R11_GIUDICATE = OUT = None


def esito_json(t):
    """`tools/t04_tutte.esito_json`, unchanged: the JSON of an answer, after the reasoning and without code fences."""
    import re
    t = str(t or '')
    if '</think>' in t:
        t = t.rsplit('</think>', 1)[1]
    t = re.sub(r'^```(?:json)?\s*|\s*```$', '', t.strip())
    i = t.find('{')
    while i >= 0:
        try:
            return json.JSONDecoder().raw_decode(t[i:])[0]
        except ValueError:
            i = t.find('{', i + 1)
    return {}


# the two helpers of tools/t04_tutte.py, under the name the code below uses
TT = types.SimpleNamespace(jl=jl, esito_json=esito_json)

DATA = '2026-10-07'
SEME, VOLTE = 20261004, 1000
RETI_CODA = ('lessicale', 'entrambe', 'descrittiva')
FUORI = {'nessuno', 'altro'}


# ── pure functions (tested in tests/test_confronto_t04.py of the working tree) ─────────────────────────────────────

def corto(p):
    return str(p).strip().split('.')[-1]


def soglia(n):
    """as maggioranza.soglia (R11): 3 of 5, 3 of 4, 2 of 3"""
    return n // 2 + 1


def voti(v):
    """'4/5' -> (4, 5); None if unreadable"""
    try:
        a, b = str(v).split('/')
        return int(a), int(b)
    except ValueError:
        return None


def r11_da_voti(vv):
    """the majority principles (R11) from the saved votes, without "nessuno" and "altro"; None if there are no votes"""
    if not vv:
        return None
    out = set()
    for p, s in vv.items():
        x = voti(s)
        if x and x[1] and x[0] >= soglia(x[1]):
            out.add(corto(p))
    return out - FUORI


def quota_voti(vv):
    out = {}
    for p, s in (vv or {}).items():
        x = voti(s)
        if x and x[1]:
            out[corto(p)] = x[0] / x[1]
    return out


def riferimento_tiene(rv):
    """majority of the readings on the reference: True if "caso" has the majority, False if not, None without votes"""
    if not rv:
        return None
    x = voti(rv.get('caso', '0/0'))
    n = max((voti(s) or (0, 0))[1] for s in rv.values())
    return bool(n and x and x[0] >= soglia(n))


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else None
    return {'tp': tp, 'fp': fp, 'fn': fn, 'precisione': None if p is None else round(p, 3),
            'richiamo': None if r is None else round(r, 3), 'f1': None if f is None else round(f, 3)}


def conti(V, b, righe):
    tp = fp = fn = 0
    for k in righe:
        ts, ms = V[k], b[k]
        tp += len(ts & ms); fp += len(ms - ts); fn += len(ts - ms)
    return tp, fp, fn


def f1(V, b, righe):
    tp, fp, fn = conti(V, b, righe)
    return 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else None


def bootstrap(righe, atti, stat, volte=VOLTE, seme=SEME):
    """95% interval of stat(righe) resampling the citing filings (as ragionamento.bootstrap_diff_f1)"""
    per = collections.defaultdict(list)
    for k in righe:
        per[atti[k]].append(k)
    chiavi = sorted(per)
    if not chiavi:
        return (None, None)
    rng = random.Random(seme); q = []
    for _ in range(volte):
        rr = [k for x in (rng.choice(chiavi) for _ in chiavi) for k in per[x]]
        v = stat(rr)
        if v is not None:
            q.append(v)
    q.sort()
    return (round(q[int(.025 * len(q))], 3), round(q[int(.975 * len(q)) - 1], 3)) if q else (None, None)


def kappa(a, b):
    """Cohen's kappa between two lists of 0/1"""
    n = len(a)
    if not n:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return round((po - pe) / (1 - pe), 3) if pe < 1 else None


def distanza(validi, t04_punti, ds_quote):
    """D = sum over the principles of the case of |T04 score - share of DeepSeek votes| (0 = same verdicts and certainty)"""
    return round(sum(abs(t04_punti.get(p, 0.0) - ds_quote.get(p, 0.0)) for p in validi), 3)


# ── loading ──────────────────────────────────────────────────────────────────────────────────────────────────────────

def carica():
    RG, AR = _t04.load(T04, QUI)                                         # versioni/T04/ragionamento.py, frozen
    import team_judgments as TJ
    righe = {r['id']: r for r in TT.jl(RIGHE)}
    shim = types.SimpleNamespace(RG=RG, dati=righe)
    E, punti, cita = {}, {}, {}
    for f in sorted(ESITI.glob('fetta*.jsonl')):
        e = AR.Misuratore.estrai(shim, f)                                 # the reader of the published measure
        for x in TT.jl(f):
            j = TT.esito_json(x.get('testo'))                            # the "readable" rule of the collect step
            if not (isinstance(j, dict) and isinstance(j.get('principi'), list) and j['principi']
                    and isinstance(j.get('cita_il_caso'), dict)) or x['id'] not in e:
                continue
            E[x['id']] = e[x['id']]
            # score of every principle: from the tokens of the verdict, P(yes) + 0.5 P(uncertain) (ragionamento.
            # punteggio_token), aligned as in ragionamento.esiti_rr (the last verdicts: "cita_il_caso", then the
            # principles). The "punteggio" written in the JSON is not used: the 9B writes it sometimes as P(yes),
            # sometimes as the certainty of the no.
            jj = RG.json_risposta(x.get('testo'))
            lst = [y for y in jj.get('principi') or [] if isinstance(y, dict)]
            vl = list(x.get('verdetti_logprob') or [])
            nv = len(lst) + 1
            vl = vl[-nv:][1:] if len(vl) >= nv else [None] * len(lst)
            pp = {}
            for y, v in zip(lst, vl):
                s = RG.punteggio_token(v) if isinstance(v, dict) else None
                pp[corto(y.get('principio'))] = s if s is not None else {'si': 1.0, 'no': 0.0}.get(AR.esito_principio(y.get('esito')), 0.5)
            punti[x['id']] = pp
            cita[x['id']] = e[x['id']]['cita']
    validi = {}
    for caso in sorted({r['caso_citato'] for r in righe.values()}):
        validi[caso] = {corto(q['id']) for q in RG.caso_conf(caso)['semantic_queries']}
    return righe, E, punti, cita, validi, TJ


def cieca(r):
    """the rule of team_judgments.costruisci: proposte_mostrate, then campione_cieco; None = unknown"""
    ctx = r.get('validato_contesto') or {}
    if ctx.get('proposte_mostrate') is not None:
        return ctx['proposte_mostrate'] is False
    if r.get('campione_cieco') is not None:
        return bool(r['campione_cieco'])
    return None


# ── measure ──────────────────────────────────────────────────────────────────────────────────────────────────────────

def misura():
    righe, E, punti, cita, validi, TJ = carica()
    addestr = set(ADDESTR.read_text().split())
    insieme = set(json.load(open(INSIEME, encoding='utf-8')))
    atti = {k: r['document_id'] for k, r in righe.items()}
    caso = {k: r['caso_citato'] for k, r in righe.items()}

    # the load of the five readings wrote the votes only on the rows without outcome: for those already judged the R11
    # votes are the ones recomputed on 04/10 with the same functions (tools/r11_su_giudicate.py, read only)
    r11g = json.load(open(R11_GIUDICATE, encoding='utf-8'))['righe']
    da_r11g = 0
    for k, x in r11g.items():
        r = righe.get(k)
        if r is not None and not r.get('proposto_principi_voti') and (x.get('r11') or {}).get('principi_voti'):
            r['proposto_principi_voti'] = x['r11']['principi_voti']
            if not r.get('proposto_riferimento_voti') and x['r11'].get('riferimento'):
                n = sum(x['r11']['riferimento'].values())
                r['proposto_riferimento_voti'] = {('caso' if str(a).startswith('caso') else str(a)): f'{v}/{n}'
                                                  for a, v in x['r11']['riferimento'].items()}
            da_r11g += 1
    bracci = {'T04': {}, 'DS-R11': {}, 'DS-pub': {}, 'T01': {}}
    for k, r in righe.items():
        if k in E:
            bracci['T04'][k] = set(E[k]['principi']) - FUORI
        x = r11_da_voti(r.get('proposto_principi_voti'))
        if x is not None:
            bracci['DS-R11'][k] = x
        if r.get('proposto_principi') is not None:
            bracci['DS-pub'][k] = {corto(p) for p in r['proposto_principi']} - FUORI
        if r.get('proposto_punteggi_principi'):
            bracci['T01'][k] = {corto(p) for p, s in r['proposto_punteggi_principi'].items() if s is not None and s >= 0.5}

    # the team judgment on the principles
    V, info = {}, {}
    esclusi = collections.Counter()
    for k, r in righe.items():
        if r.get('esito') != 'confermata':
            continue
        if k in addestr:
            esclusi['addestramento T04'] += 1; continue
        vp = r.get('validato_principi')
        if vp is None:
            esclusi['senza principi giudicati'] += 1; continue
        s = {corto(p) for p in vp if str(p).strip()}
        if not s <= validi[caso[k]] | FUORI:
            esclusi['principio fuori caso'] += 1; continue
        V[k] = s - FUORI
        c = cieca(r)
        info[k] = {'cieca': 'cieca' if c else 'visibile' if c is False else 'non si sa',
                   'gruppo': 'nelle 691' if k in insieme else 'dopo le 691',
                   'rete': r.get('proposto_rete') or 'non si sa',
                   'cieca e dopo le 691': 'si' if c and k not in insieme else 'no'}
    appaiate = sorted(k for k in V if all(k in b for b in bracci.values()))
    M = {'data': DATA, 'righe_vive': len(righe), 't04_leggibili': len(E), 'addestramento_t04': len(addestr),
         'addestramento_t04_fra_le_vive': len(addestr & set(righe)),
         'voti_r11_dalle_giudicate_del_04_10': da_r11g, 'confermate_giudicate_utili': len(V), 'esclusi': dict(esclusi), 'appaiate': len(appaiate),
         'mancano_nell_appaiato': {n: sum(1 for k in V if k not in b) for n, b in bracci.items()}}

    def tabella(rr):
        out = {'n_righe': len(rr), 'n_atti': len({atti[k] for k in rr}), 'principi_team': sum(len(V[k]) for k in rr)}
        for n, b in bracci.items():
            out[n] = prf(*conti(V, b, rr))
            out[n]['ic_f1'] = bootstrap(rr, atti, lambda x, b=b: f1(V, b, x))
        for n in ('DS-R11', 'DS-pub', 'T01'):
            b = bracci[n]
            out['T04 - ' + n] = bootstrap(rr, atti, lambda x, b=b: (lambda a, c: None if a is None or c is None else a - c)(
                f1(V, bracci['T04'], x), f1(V, b, x)))
        return out

    M['principi'] = {'tutte': tabella(appaiate)}
    for chiave, valori in (('cieca', ('cieca', 'visibile', 'non si sa')), ('gruppo', ('nelle 691', 'dopo le 691')),
                           ('rete', RETI_CODA), ('cieca e dopo le 691', ('si',))):
        for v in valori:
            rr = [k for k in appaiate if info[k][chiave] == v]
            if rr:
                M['principi'][f'{chiave}: {v}'] = tabella(rr)
    for c in sorted(validi):
        rr = [k for k in appaiate if caso[k] == c]
        if rr:
            M['principi'][f'caso: {c}'] = tabella(rr)
    # each arm on its own rows (outside the paired set)
    M['principi_ciascuno'] = {n: dict(prf(*conti(V, b, [k for k in V if k in b])), n_righe=sum(1 for k in V if k in b))
                             for n, b in bracci.items()}

    # per principle: T04 and DS-R11 against the team, and who is right when they disagree
    pp = {}
    for k in appaiate:
        for p in validi[caso[k]]:
            d = pp.setdefault(f'{caso[k]}.{p}', collections.Counter())
            t, a, b = p in V[k], p in bracci['T04'][k], p in bracci['DS-R11'][k]
            d['team_si'] += t
            for n, x in (('T04', a), ('DS', b)):
                d[f'{n}_tp'] += x and t; d[f'{n}_fp'] += x and not t; d[f'{n}_fn'] += (not x) and t
            if a != b:
                d['disaccordi'] += 1
                d['ha_ragione_T04' if a == t else 'ha_ragione_DS'] += 1
    M['per_principio'] = {p: dict(c) for p, c in sorted(pp.items())}
    dis = collections.Counter()
    for c in pp.values():
        dis['disaccordi'] += c['disaccordi']; dis['T04'] += c['ha_ragione_T04']; dis['DS'] += c['ha_ragione_DS']
    M['disaccordi_arbitrati'] = dict(dis)

    # discard/keep
    sc = {}
    for k, r in righe.items():
        if k in addestr:
            continue
        if r.get('esito') in ('confermata', 'scartata'):
            giro, es = 'uptakes', r['esito']
        elif (r.get('settembre') or {}).get('esito') in ('confermata', 'scartata'):
            giro, es = 'settembre', r['settembre']['esito']
        else:
            continue
        for n, segnale in (('T04', cita.get(k)), ('DeepSeek', riferimento_tiene(r.get('proposto_riferimento_voti')))):
            if n == 'DeepSeek':
                segnale = None if segnale is None else ('si' if segnale else 'no')
            d = sc.setdefault(f'{giro} {n}', collections.Counter())
            d[f'{es} / {segnale or "nessun segnale"}'] += 1
    M['scarto'] = {k: dict(v) for k, v in sorted(sc.items())}
    # on the discarded rows the true signal can be "no principle", even when "cita_il_caso" is yes
    scart = [k for k, r in righe.items() if r.get('esito') == 'scartata' and k not in addestr]
    M['scartate_senza_principi'] = {n: {'n': sum(1 for k in scart if k in bracci[n]),
                                        'nessun_principio': sum(1 for k in scart if k in bracci[n] and not bracci[n][k])}
                                    for n in bracci}
    M['scartate_motivi'] = dict(collections.Counter(str(righe[k].get('motivo_scarto')) for k in scart))
    conf_t04 = [k for k, r in righe.items() if r.get('esito') == 'confermata' and k not in addestr and k in cita]
    M['t04_no_sulle_confermate'] = {'n': len(conf_t04), 'no': sum(cita[k] == 'no' for k in conf_t04),
                                    'incerto': sum(cita[k] == 'incerto' for k in conf_t04),
                                    'ic_quota_no': bootstrap(conf_t04, atti, lambda x: sum(cita[k] == 'no' for k in x) / len(x) if x else None)}

    # agreement on the rows without judgment, in the queue
    U = sorted(k for k, r in righe.items() if not r.get('esito') and r.get('proposto_rete') in RETI_CODA
               and k in bracci['T04'] and k in bracci['DS-R11'])
    acc = {}
    for gruppo, rr in [('tutte', U)] + [(f'caso: {c}', [k for k in U if caso[k] == c]) for c in sorted(validi)] + \
            [(f'rete: {x}', [k for k in U if righe[k].get('proposto_rete') == x]) for x in RETI_CODA]:
        if not rr:
            continue
        uguali = sum(bracci['T04'][k] == bracci['DS-R11'][k] for k in rr)
        acc[gruppo] = {'n_righe': len(rr), 'stesso_insieme': uguali, 'quota': round(uguali / len(rr), 3),
                       'ic_quota': bootstrap(rr, atti, lambda x: sum(bracci['T04'][k] == bracci['DS-R11'][k] for k in x) / len(x) if x else None),
                       'T04_principi_per_riga': round(sum(len(bracci['T04'][k]) for k in rr) / len(rr), 2),
                       'DS_principi_per_riga': round(sum(len(bracci['DS-R11'][k]) for k in rr) / len(rr), 2),
                       'T04_cita_no': sum(cita.get(k) == 'no' for k in rr)}
    M['accordo_senza_giudizio'] = acc
    kp = {}
    for c in sorted(validi):
        rr = [k for k in U if caso[k] == c]
        for p in sorted(validi[c]):
            a = [int(p in bracci['T04'][k]) for k in rr]; b = [int(p in bracci['DS-R11'][k]) for k in rr]
            if rr:
                kp[f'{c}.{p}'] = {'n': len(rr), 'T04_si': sum(a), 'DS_si': sum(b), 'solo_T04': sum(x and not y for x, y in zip(a, b)),
                                  'solo_DS': sum(y and not x for x, y in zip(a, b)), 'kappa': kappa(a, b)}
    M['accordo_per_principio'] = kp

    # the list of doubts
    dubbi = []
    for k in U:
        r = righe[k]
        dq = quota_voti(r.get('proposto_principi_voti'))
        dubbi.append({'codice': r.get('codice'), 'id': k, 'caso': caso[k], 'rete': r.get('proposto_rete'),
                      'D': distanza(validi[caso[k]], punti[k], dq),
                      'T04_si': ' '.join(sorted(bracci['T04'][k])), 'DS_R11_si': ' '.join(sorted(bracci['DS-R11'][k])),
                      'T04_cita': cita.get(k), 'voti_DS': ' '.join(f'{corto(p)}={s}' for p, s in sorted((r.get('proposto_principi_voti') or {}).items()))})
    dubbi.sort(key=lambda x: (-x['D'], x['codice'] or ''))
    M['dubbi'] = {'n': len(dubbi), 'D_mediana': dubbi[len(dubbi) // 2]['D'] if dubbi else None,
                  'D_almeno_1': sum(x['D'] >= 1 for x in dubbi), 'primi_30': dubbi[:30]}
    return M, dubbi


# ── writing ──────────────────────────────────────────────────────────────────────────────────────────────────────────

def n3(x):
    return '' if x is None else f'{x:.3f}'.replace('.', ',')


def ic(t):
    return '' if not t or t[0] is None else f'{n3(t[0])} – {n3(t[1])}'


def scrivi(M, dubbi):
    j = OUT / f'confronto-{DATA}.json'
    json.dump(M, open(j, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
    with open(OUT / f'dubbi-{DATA}.csv', 'w', encoding='utf-8', newline='') as h:
        w = csv.DictWriter(h, fieldnames=list(dubbi[0]) if dubbi else ['codice'])
        w.writeheader(); w.writerows(dubbi)
    P = M['principi']
    L = [f'# T04 a confronto con DeepSeek, T01 e il team ({DATA[8:]}/{DATA[5:7]}/{DATA[:4]})', '',
         'Sola lettura, solo Mac. Rifare: `.venv/bin/python tools/confronto_t04.py`. Numeri completi in '
         f'`confronto-{DATA}.json`; lista dei dubbi intera in `dubbi-{DATA}.csv`.', '',
         '## Metodo, in breve', '',
         f'- **T04** ha risposto a {M["righe_vive"]:,} righe vive; {M["t04_leggibili"]:,} risposte leggibili (regola di '
         '`t04_tutte.py raccogli`), lette con il lettore della misura pubblicata di T04 (`Misuratore.estrai`). '
         'Principi di T04 = i «si»; «incerto» non conta.'.replace(',', '.'),
         '- **DS-R11**: maggioranza delle cinque letture di DeepSeek V4 Flash dai voti salvati (v >= n//2+1). '
         '**DS-pub**: la proposta scritta sulla riga (R11..R16 con la mappa dei paragrafi), quella pubblicata nella 0.1 e '
         'vista dal team. **T01**: punteggio >= 0,5.',
         f'- **Fuori dal confronto col team**: le {M["addestramento_t04"]} righe dell\'addestramento di T04 '
         f'({M["addestramento_t04_fra_le_vive"]} sono fra le vive, tutte confermate; le scartate non sono piu\' vive). '
         f'Altre escluse: {", ".join(f"{k} {v}" for k, v in M["esclusi"].items())}.',
         f'- **Insieme appaiato**: {M["appaiate"]} righe confermate dove rispondono tutti e quattro i bracci; il confronto e\' '
         'sempre sulle stesse righe. F1 sui principi contro quelli confermati dal team («nessuno» e «altro» fuori), '
         'intervalli al 95% ricampionando gli atti citanti (1000 volte, seme 20261004), come nella scheda di T04.',
         '- **Cieca / visibile**: `validato_contesto.proposte_mostrate`, poi `campione_cieco` (regola di '
         '`team_judgments.py`). Con la proposta visibile il team ha visto DS-pub: quei giudizi misurano l\'accordo con '
         'un team ancorato a DeepSeek, non un accordo cieco.', '',
         '## Principi: precisione, richiamo, F1', '',
         '| Righe | n righe (atti) | T04 F1 [IC] | DS-R11 F1 [IC] | DS-pub F1 [IC] | T01 F1 [IC] | T04 − DS-R11 | T04 − T01 |',
         '|---|---:|---:|---:|---:|---:|---:|---:|']
    for nome, t in P.items():
        L.append(f'| {nome} | {t["n_righe"]} ({t["n_atti"]}) | ' + ' | '.join(
            f'{n3(t[b]["f1"])} [{ic(t[b]["ic_f1"])}]' for b in ('T04', 'DS-R11', 'DS-pub', 'T01'))
            + f' | {ic(t["T04 - DS-R11"])} | {ic(t["T04 - T01"])} |')
    t = P['tutte']
    L += ['', 'Precisione / richiamo sull\'insieme appaiato: ' + '; '.join(
        f'{b} {n3(t[b]["precisione"])} / {n3(t[b]["richiamo"])}' for b in ('T04', 'DS-R11', 'DS-pub', 'T01')) + '.', '',
        'Ciascuno sulle sue righe (non appaiato): ' + '; '.join(
            f'{b} F1 {n3(v["f1"])} su {v["n_righe"]}' for b, v in M['principi_ciascuno'].items()) + '.', '']
    d = M['disaccordi_arbitrati']
    L += ['## Quando T04 e DS-R11 non sono d\'accordo (righe giudicate)', '',
          f'Sui {d.get("disaccordi", 0)} verdetti di principio in cui differiscono, il team da\' ragione a T04 '
          f'{d.get("T04", 0)} volte e a DeepSeek {d.get("DS", 0)}. Per principio (solo quelli con almeno 5 disaccordi):', '',
          '| Principio | team si | T04 tp/fp/fn | DS tp/fp/fn | disaccordi | ragione T04 | ragione DS |', '|---|---:|---:|---:|---:|---:|---:|']
    for p, c in M['per_principio'].items():
        if c.get('disaccordi', 0) >= 5:
            L.append(f'| {p} | {c.get("team_si", 0)} | {c.get("T04_tp", 0)}/{c.get("T04_fp", 0)}/{c.get("T04_fn", 0)} | '
                     f'{c.get("DS_tp", 0)}/{c.get("DS_fp", 0)}/{c.get("DS_fn", 0)} | {c.get("disaccordi", 0)} | '
                     f'{c.get("ha_ragione_T04", 0)} | {c.get("ha_ragione_DS", 0)} |')
    L += ['', '## Tenere o scartare', '',
          '| Giro e modello | esito del team / segnale del modello: righe |', '|---|---|']
    for k, v in M['scarto'].items():
        L.append(f'| {k} | ' + '; '.join(f'{a}: {b}' for a, b in sorted(v.items())) + ' |')
    s = M['t04_no_sulle_confermate']
    L += ['', f'T04 dice «non cita» su {s["no"]} delle {s["n"]} confermate (Uptakes) [quota, IC {ic(s["ic_quota_no"])}] e '
          f'«incerto» su {s["incerto"]}. T01 non da\' un segnale di scarto. Sulle scartate dal team, nessun principio preso: ' +
          '; '.join(f'{b} {v["nessun_principio"]} su {v["n"]}' for b, v in M['scartate_senza_principi'].items()) +
          f' (motivi: {", ".join(f"{a} {b}" for a, b in M["scartate_motivi"].items())}).', '',
          '## Accordo T04 / DS-R11 sulle righe senza giudizio (in coda)', '',
          '| Righe | n | stesso insieme di principi [IC] | principi per riga T04 / DS | T04 «non cita» |', '|---|---:|---:|---:|---:|']
    for g, a in M['accordo_senza_giudizio'].items():
        L.append(f'| {g} | {a["n_righe"]} | {n3(a["quota"])} [{ic(a["ic_quota"])}] | {a["T04_principi_per_riga"]} / '
                 f'{a["DS_principi_per_riga"]} | {a["T04_cita_no"]} |'.replace('.', ','))
    L += ['', 'Per principio (kappa di Cohen fra T04 e DS-R11; «solo T04» / «solo DS» = righe dove lo prende uno solo):', '',
          '| Principio | n | T04 si | DS si | solo T04 | solo DS | kappa |', '|---|---:|---:|---:|---:|---:|---:|']
    for p, k in M['accordo_per_principio'].items():
        L.append(f'| {p} | {k["n"]} | {k["T04_si"]} | {k["DS_si"]} | {k["solo_T04"]} | {k["solo_DS"]} | {n3(k["kappa"])} |')
    du = M['dubbi']
    L += ['', f'## Dubbi prima: le righe dove T04 e DeepSeek si allontanano di piu\'', '',
          f'D = somma sui principi del caso di |punteggio di T04 − quota dei voti di DeepSeek|; il punteggio di T04 e\' P(si) + 0,5 P(incerto) dai token del verdetto (il numero scritto nel JSON e\' a volte la certezza del no, non si usa). Su {du["n"]} righe in coda: '
          f'mediana {n3(du["D_mediana"])}, {du["D_almeno_1"]} con D >= 1 (almeno un principio pieno in disaccordo). '
          f'Le prime 30 (tutte in `dubbi-{DATA}.csv`):', '',
          '| Codice | Caso | D | T04 si | DS-R11 si | T04 cita |', '|---|---|---:|---|---|---|']
    for x in du['primi_30']:
        L.append(f'| {x["codice"]} | {x["caso"]} | {n3(x["D"])} | {x["T04_si"] or "–"} | {x["DS_R11_si"] or "–"} | {x["T04_cita"]} |')
    L += ['', '## Limiti', '',
          '- Le righe giudicate «nelle 691» sono quelle su cui sono state contate le regole G05/G06 della domanda di T04 '
          '(e C05): li\' T04 parte avvantaggiato anche fuori dalle 94. Pulite sono quelle giudicate dopo.',
          '- Con la proposta visibile il team ha visto la proposta di DeepSeek: quei giudizi favoriscono DeepSeek.',
          '- Lo scarto si misura poco: le scartate dal team non sono piu\' righe vive (T04 non le ha lette), restano le '
          'poche scartate dell\'ultimo giro. La misura per piegature della scheda di T04 (207 scartate) resta il riferimento.',
          '- Nessuna riga della rete descrittiva (trovata per descrizione, S07) e\' stata giudicata: su quelle c\'e\' solo '
          'l\'accordo fra i modelli, non la misura contro il team.',
          '- DS-pub sulle righe giudicate e\' la proposta di quel momento (R05..R16), la stessa che il team vedeva quando '
          'le proposte erano visibili.',
          '- DS-R11 qui e\' ricalcolato dai voti salvati, senza la mappa dei paragrafi; DS-pub e\' la proposta vera della riga.',
          '- Le risposte non leggibili di T04 (circa 5%, molte tronche al tetto dei token) mancano: l\'appaiato le esclude '
          'per tutti i bracci.', '']
    (OUT / f'CONFRONTO-{DATA}.md').write_text('\n'.join(L), encoding='utf-8')
    print('scritti', j.name, f'CONFRONTO-{DATA}.md', f'dubbi-{DATA}.csv')


def main(argv=None):
    global QUI, T04, RIGHE, ESITI, ADDESTR, INSIEME, R11_GIUDICATE, OUT
    ap = argparse.ArgumentParser(description='T04 against DeepSeek V4 Flash, T01 and the team (07/10/2026), read only.')
    ap.add_argument('--rows', required=True, help='righe_vive.jsonl.gz: the live rows read from Firestore on 07/10 (not published)')
    ap.add_argument('--answers-dir', required=True, help='folder with the T04 answers fetta*.jsonl (not published)')
    ap.add_argument('--insieme', required=True, help='training/ragionamento/insieme.json: the 691 rows of the training-measure')
    ap.add_argument('--r11-judged', required=True, help='training/cinque/r11_su_giudicate.json: R11 votes recomputed on judged rows')
    ap.add_argument('--training-ids', default=None, help='ids of the 94 T04 training rows (default: versioni/T04/esempi_di_addestramento_id.txt)')
    ap.add_argument('--out-dir', required=True, help='where confronto-2026-10-07.json, dubbi-2026-10-07.csv and the .md are written')
    ap.add_argument('--t04-dir', default=str(_t04.default_t04_dir()), help='frozen copy of T04 (default: versioni/T04)')
    ap.add_argument('--root', help='project root with cited-cases/ (default: TRACE_ROOT or the current folder)')
    a = ap.parse_args(argv)
    QUI = project_root(a.root)
    T04 = pathlib.Path(a.t04_dir)
    RIGHE, ESITI = pathlib.Path(a.rows), pathlib.Path(a.answers_dir)
    ADDESTR = pathlib.Path(a.training_ids) if a.training_ids else T04 / 'esempi_di_addestramento_id.txt'
    INSIEME, R11_GIUDICATE = pathlib.Path(a.insieme), pathlib.Path(a.r11_judged)
    OUT = pathlib.Path(a.out_dir)
    OUT.mkdir(parents=True, exist_ok=True)
    M, dubbi = misura()
    scrivi(M, dubbi)
    t = M['principi']['tutte']
    print('appaiate', M['appaiate'], {b: t[b]['f1'] for b in ('T04', 'DS-R11', 'DS-pub', 'T01')},
          'T04-DS', t['T04 - DS-R11'], 'T04-T01', t['T04 - T01'])


if __name__ == '__main__':
    main()
