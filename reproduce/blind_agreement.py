"""THE FIRST BLIND FIGURE (9/10/2026): machine-team agreement on the team judgments of the data release given
without the machine proposal on the screen (blind), against those given with the proposal visible.

Original: `tools/misura_cieca_rilascio.py` of the TRACE working tree (frozen with TRACE 0.1). Same computation; paths
are arguments. The rule and the bases were written before the numbers (training/misure/CIECA-RILASCIO-2026-10-09.md, not
published; --md updates its results block if you have it). Italian strings written into the outputs are data.

Inputs, read only:
  --team-judgments  trace-0.1-team-judgments.jsonl of the TRACE 0.1 dataset (columns machine_* and team_*): public;
  --citations       trace-0.1-citations.jsonl of the same dataset (the rule that composed each proposal): public;
  --rich-data       pubblicazione/mappa/dati_ricchi.json (only for the citing filing of each code, used by the bootstrap
                    that resamples filings): not published. Without it the citing filing comes from the citations file;
                    the citations the team discarded are not in that file, so each of them counts as a filing of its
                    own: the point figures are the same, the bootstrap intervals can move slightly.

Usage:
  python reproduce/blind_agreement.py --team-judgments trace-0.1-team-judgments.jsonl \\
      --citations trace-0.1-citations.jsonl [--rich-data dati_ricchi.json] --out cieca_rilascio_2026-10-09.json [--md FILE]
"""
# The code keeps the frozen original line for line (names and long lines are not restyled).
# ruff: noqa: E501, E702, E731, E741, N806, SIM115
import argparse
import json
import math
import pathlib
import random
from collections import defaultdict

SEME, B = 20261009, 2000


def wilson(k, n, z=1.959964):
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [c - h, c + h]


def misure(righe):
    """righe: judgments; returns the raw counts (they add up correctly in the bootstrap)"""
    m = {'esito': [0, 0], 'tipo': [0, 0], 'chi': [0, 0], 'insieme': [0, 0], 'tp': 0, 'fp': 0, 'fn': 0}
    for x in righe:
        conf = x['outcome'] == 'confirmed'
        m['esito'][1] += 1
        m['esito'][0] += conf
        if not conf:
            continue
        if x['machine_citation_function'] and x['team_citation_function']:
            m['tipo'][1] += 1
            m['tipo'][0] += x['machine_citation_function'] == x['team_citation_function']
        if x['machine_who_speaks'] and x['team_who_speaks']:
            m['chi'][1] += 1
            m['chi'][0] += x['machine_who_speaks'] == x['team_who_speaks']
        if x['team_principles'] is not None:
            a, b = set(x['machine_principles'] or []), set(x['team_principles'] or [])
            m['tp'] += len(a & b); m['fp'] += len(a - b); m['fn'] += len(b - a)
            m['insieme'][1] += 1
            m['insieme'][0] += a == b
    return m


def valori(m):
    q = lambda k: (m[k][0] / m[k][1]) if m[k][1] else None
    den = 2 * m['tp'] + m['fp'] + m['fn']
    return {'esito': q('esito'), 'tipo': q('tipo'), 'chi': q('chi'), 'insieme': q('insieme'),
            'f1': (2 * m['tp'] / den) if den else None}


def per_atto(righe, doc):
    g = defaultdict(list)
    for x in righe:
        g[doc.get(x['citation_code'], x['citation_code'])].append(x)
    return list(g.values())


def somma(gruppi):
    return misure([x for gg in gruppi for x in gg])


def boot(cieche, viste, doc):
    rng = random.Random(SEME)
    gc, gv = per_atto(cieche, doc), per_atto(viste, doc)
    acc = defaultdict(list)
    for _ in range(B):
        vc = valori(somma([rng.choice(gc) for _ in gc]))
        vv = valori(somma([rng.choice(gv) for _ in gv]))
        for k in vc:
            if vc[k] is not None:
                acc['c_' + k].append(vc[k])
            if vv[k] is not None:
                acc['v_' + k].append(vv[k])
            if vc[k] is not None and vv[k] is not None:
                acc['d_' + k].append(vc[k] - vv[k])
    q = lambda v: [sorted(v)[int(.025 * len(v))], sorted(v)[int(.975 * len(v)) - 1]]
    return {k: q(v) for k, v in acc.items()}


def blocco(nome, righe):
    m = misure(righe)
    v = valori(m)
    return {'nome': nome, 'giudizi': len(righe), 'atti': len({x['_doc'] for x in righe}),
            'conteggi': m, 'valori': v,
            'wilson': {k: wilson(*m[k]) for k in ('esito', 'tipo', 'chi', 'insieme')}}


def main(argv=None):
    ap = argparse.ArgumentParser(description='Blind against visible machine-team agreement on the TRACE 0.1 team judgments.')
    ap.add_argument('--team-judgments', required=True, help='trace-0.1-team-judgments.jsonl (public dataset)')
    ap.add_argument('--citations', required=True, help='trace-0.1-citations.jsonl (public dataset)')
    ap.add_argument('--rich-data', help='dati_ricchi.json (not published): citing filing of every code, discarded ones too')
    ap.add_argument('--out', required=True, help='JSON file of the results (originally training/misure/cieca_rilascio_2026-10-09.json)')
    ap.add_argument('--md', help='pre-registration .md whose RESULTS block is replaced (optional)')
    a = ap.parse_args(argv)
    J = [json.loads(l) for l in open(a.team_judgments, encoding='utf-8')]
    if a.rich_data:
        R = json.load(open(a.rich_data, encoding='utf-8'))
        doc = {c['codice']: c['doc'] for c in R['citazioni'] if c.get('codice')}
    else:
        # public fallback: the citing filing from the citations file (discarded citations are not there)
        doc = {json.loads(l)['citation_code']: json.loads(l)['document_id'] for l in open(a.citations, encoding='utf-8')}
    for x in J:
        x['_doc'] = doc.get(x['citation_code'], x['citation_code'])
    senza_doc = sorted(x['citation_code'] for x in J if x['citation_code'] not in doc and x['blind'] in ('yes', 'no'))
    cieche = [x for x in J if x['blind'] == 'yes' and x['counted_in_release'] == 'yes']
    viste = [x for x in J if x['blind'] == 'no' and x['counted_in_release'] == 'yes']
    tutte_cieche = [x for x in J if x['blind'] == 'yes']
    cieche_dal_2 = [x for x in cieche if x['judged_on'] >= '2026-10-02']
    res = {
        'data': '2026-10-09', 'file_giudizi': a.team_judgments, 'seme': SEME, 'ricampionamenti': B,
        'senza_atto_citante': senza_doc,
        'cieche': blocco('cieche, giudizio del titolare (counted_in_release = yes)', cieche),
        'viste': blocco('viste, giudizio del titolare (counted_in_release = yes)', viste),
        'sens_tutte_cieche': blocco('tutte le cieche del file (anche seconde revisioni)', tutte_cieche),
        'sens_cieche_dal_2_10': blocco('cieche principali giudicate dal 2/10/2026', cieche_dal_2),
    }
    # descriptive check, NOT fixed in advance: within each cited judgment, and the rule that composed the proposal
    regola = {json.loads(l)['citation_code']: json.loads(l)['proposal_rule'] for l in open(a.citations, encoding='utf-8')}
    per_caso = {}
    for caso in sorted({x['cited_judgment'] for x in cieche + viste}):
        mc = misure([x for x in cieche if x['cited_judgment'] == caso]); mv = misure([x for x in viste if x['cited_judgment'] == caso])
        per_caso[caso] = {'cieche': {'tipo': mc['tipo'], 'f1': valori(mc)['f1']}, 'viste': {'tipo': mv['tipo'], 'f1': valori(mv)['f1']}}
    q = lambda c, n: (c[0] / c[1]) if c[1] else None
    res['descrittivo_per_caso'] = per_caso
    res['casi_tipo_piu_basso_cieche'] = sum(1 for v in per_caso.values() if v['cieche']['tipo'][1] and v['viste']['tipo'][1] and q(v['cieche']['tipo'], 0) < q(v['viste']['tipo'], 0))
    res['casi_confrontabili'] = sum(1 for v in per_caso.values() if v['cieche']['tipo'][1] and v['viste']['tipo'][1])
    cinque = lambda g: [sum(1 for x in g if x['outcome'] == 'confirmed' and regola.get(x['citation_code']) in ('R11', 'R15', 'R16')), sum(1 for x in g if x['outcome'] == 'confirmed')]
    res['confermate_con_cinque_letture'] = {'cieche': cinque(cieche), 'viste': cinque(viste)}
    res['ic'] = boot(cieche, viste, doc)
    res['ic_sens_tutte'] = boot(tutte_cieche, viste, doc)
    res['ic_sens_dal_2_10'] = boot(cieche_dal_2, viste, doc)
    json.dump(res, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # the results in the .md (below the rule, which stays as it is)
    f = lambda v: '-' if v is None else f'{v:.3f}'
    fi = lambda v: '-' if not v else f'[{v[0]:.3f}; {v[1]:.3f}]'
    righe_md = ['', '<!-- RISULTATI -->', f'Calcolato il 09/10/2026 da `tools/misura_cieca_rilascio.py` (file: `{a.out}`).', '',
                '| base | giudizi | atti | esito | tipo | chi parla | principi F1 | principi insieme uguale |', '|---|---|---|---|---|---|---|---|']
    for k in ('cieche', 'viste', 'sens_tutte_cieche', 'sens_cieche_dal_2_10'):
        b = res[k]; m = b['conteggi']; v = b['valori']
        righe_md.append(f"| {b['nome']} | {b['giudizi']} | {b['atti']} | {m['esito'][0]}/{m['esito'][1]} = {f(v['esito'])} | "
                        f"{m['tipo'][0]}/{m['tipo'][1]} = {f(v['tipo'])} | {m['chi'][0]}/{m['chi'][1]} = {f(v['chi'])} | {f(v['f1'])} | "
                        f"{m['insieme'][0]}/{m['insieme'][1]} = {f(v['insieme'])} |")
    righe_md += ['', 'Intervalli al 95%: Wilson per le quote, bootstrap per atto citante per la F1 e per le differenze.', '',
                 '| misura | cieche (Wilson / bootstrap) | viste | cieche meno viste [bootstrap] | tutte le cieche meno viste | dal 2/10 meno viste |',
                 '|---|---|---|---|---|---|']
    for k in ('esito', 'tipo', 'chi', 'f1', 'insieme'):
        wc = res['cieche']['wilson'].get(k) or res['ic'].get('c_' + k)
        wv = res['viste']['wilson'].get(k) or res['ic'].get('v_' + k)
        righe_md.append(f"| {k} | {f(res['cieche']['valori'][k])} {fi(wc)} | {f(res['viste']['valori'][k])} {fi(wv)} | "
                        f"{fi(res['ic'].get('d_' + k))} | {fi(res['ic_sens_tutte'].get('d_' + k))} | {fi(res['ic_sens_dal_2_10'].get('d_' + k))} |")
    if senza_doc:
        righe_md += ['', f'Codici senza atto citante nei dati ricchi (contano come un atto ciascuno): {", ".join(senza_doc)}']
    righe_md.append('<!-- /RISULTATI -->')
    if a.md:
        MD = pathlib.Path(a.md)
        t = MD.read_text(encoding='utf-8')
        if '<!-- RISULTATI -->' in t:
            t = t[:t.index('<!-- RISULTATI -->')].rstrip('\n') + '\n' + t[t.index('<!-- /RISULTATI -->') + len('<!-- /RISULTATI -->'):]
        MD.write_text(t.rstrip('\n') + '\n' + '\n'.join(righe_md) + '\n', encoding='utf-8')
    print('\n'.join(righe_md))


if __name__ == '__main__':
    main()
