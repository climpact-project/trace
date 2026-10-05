"""VARIANTI DELLA SOGLIA DEI PRINCIPI SU R11 (04/10/2026, col si' del PI: «calcola, SENZA scrivere niente»).

   Seguito di `tools/r11_su_giudicate.py`: sulle 137 righe giudicate con le cinque letture R11 (maggioranza, 3 su 5) fa
   peggio della proposta di prima (R05) sui principi, perche' i principi a 2/5 il team li prende quanto quelli a 3/5.
   Qui si confrontano, con le STESSE funzioni del caricamento (carica_ripresa.proposta_r11, maggioranza.py), le varianti:

     R05     la proposta di prima (quella che il team ha visto);
     R11     maggioranza: almeno 3 su 5 (3 su 4, 2 su 3, 2 su 2, 1 su 1);
     V2      almeno 2 letture (1 se ce n'e' una sola): soglia min(2, maggioranza);
     V2P     maggioranza, oppure 2 voti E la frase sostenuta di almeno una lettura che lo vota trovata nel testo (freni);
     V2R     maggioranza, oppure 2 voti E punteggio del reranker sul brano >= 0,5 (la soglia fissa dell'«indizio», non tarata);
     U       principi di R05 uniti a quelli di R11 (la menzione in catena resta senza principi).
   Per le pagine attorno: R11 (principi 3/5, pagine 3/5), V2 con pagine 3/5, V2 con pagine 2/5 (stessa soglia dei principi).

   NIENTE SI SCRIVE IN BANCA DATI, e non la si legge neppure: i giudizi vengono da training/cinque/r11_su_giudicate.json,
   le proposte di prima da training/cinque/proposte_prima.json, quelle caricate stanotte da secco_ripresa_<caso>.json.
   Esce training/cinque/r12_varianti.json.

   Uso:  .venv/bin/python tools/r12_varianti.py [--volte 2000]
"""
import argparse, collections, json, pathlib, random, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import maggioranza as M
import carica_ripresa as CR
import sonde as S
from freni import verifica
QUI = pathlib.Path(__file__).resolve().parent.parent
C = QUI/'training'/'cinque'
CASI = ['urgenda', 'neubauer', 'future-generations', 'klimaseniorinnen', 'cig-parere-clima', 'idh-oc-32-25']
SEME = 20261004
_ORIG = M.voto_principi
CUR = {}          # la riga in corso: id, contesto, punteggi del reranker, testi del prompt (per V2P e V2R)


def corto(p):
    return str(p).strip().split('.')[-1]


def insieme(lst):
    s = {corto(p) for p in (lst or []) if str(p).strip()}
    s.discard('nessuno')
    return frozenset(s)


def soglia_v2(n):
    return min(2, M.soglia(n))


def con_prova(p, vp):
    for _, y, s in vp['insiemi']:
        if p in s:
            fr = ' '.join(str(y.get('frase_sostenuta') or '').split())[:600]
            if fr and verifica(fr, CUR['contesto'], CUR['testi_prompt']) == 'trovata':
                return True
    return False


def con_reranker(p, vp):
    return (CUR['brano'].get(p) or 0) >= CR.SOGLIA_RERANKER


def variante(tp, tg, filtro=None):
    """voto_principi con la soglia dei principi tp(n) (e, se c'e', un filtro sui principi sotto la maggioranza) e la
    soglia delle pagine tg(n)"""
    def vp_(letture, ids, canonico, *_):
        vp = _ORIG(letture, ids, canonico)
        if vp is None:
            return None
        n, v = vp['n'], vp['voti']
        def preso(p):
            if v.get(p, 0) >= M.soglia(n):
                return True
            if v.get(p, 0) >= tp(n):
                return filtro is None or filtro(p, vp)
            return False
        presi = [p for p in ids if preso(p)] + ([M.ALTRO] if preso(M.ALTRO) else [])
        vp['maggioranza'] = presi or [M.NESSUNO]
        vp['soglia'] = tg(n)
        return vp
    return vp_


VARIANTI = {   # nome: (soglia principi, soglia pagine, filtro)
    'R11': (M.soglia, M.soglia, None),
    'V2': (soglia_v2, M.soglia, None),
    'V2P': (soglia_v2, M.soglia, con_prova),
    'V2R': (soglia_v2, M.soglia, con_reranker),
    'V2pag2': (soglia_v2, soglia_v2, None),
}


def calcola_righe(caso, rids, tipo_fs):
    """{rid: {variante: {'principi', 'pagine', 'cand', 'campi'}}} per le righe date, senza banca dati"""
    et = f"{S.SERIE_IN_USO.get(caso, '')}cinque"
    ids, par, brano, _, _ = CR.carica(caso)
    ds = CR.per_id(CR.P/f'{caso}_ripresa_deepseek_{et}.jsonl')
    cand = CR.per_id(CR.P/f'{caso}_ripresa_righe_{et}.jsonl')
    tipi = CR.per_id(QUI/'training'/f'lessicali_{caso}_deepseek_cinque.jsonl')
    CR.CODICI_RUN.update({'sonde': S.codice(caso), 'mappa': {'P03': 'R06', 'P05': 'R07'}.get(S.serie(caso)) or {'klimaseniorinnen': 'R09', 'cig-parere-clima': 'R09', 'idh-oc-32-25': 'R09'}.get(caso, 'R04')})
    testi_prompt = [t for k in ids for t in (CR.PRINCIPI_TESTO.get(k) or ())]
    out = {}
    for rid in rids:
        if rid not in ds:
            continue
        vt = M.voto_tipo((tipi.get(rid) or {}).get('letture') or [])
        CUR.update(rid=rid, contesto=(cand.get(rid) or {}).get('contesto') or '', brano=brano.get(rid, {}), testi_prompt=testi_prompt)
        r = {}
        for nome, (tp, tg, fl) in VARIANTI.items():
            M.voto_principi = variante(tp, tg, fl)
            try:
                c = CR.proposta_r11(caso, rid, ids, par, brano, ds, cand, vt, tipo_fs.get(rid) or '')
            finally:
                M.voto_principi = _ORIG
            if c is None:
                break
            r[nome] = {'principi': c['proposto_principi'],
                       'pagine': sorted(int(v['pagina']) for v in c['proposto_estensione'] if v['prosegue']),
                       'cand': sorted(int(v['pagina']) for v in c['proposto_estensione']),
                       'tipo': vt['tipo'] if vt else (tipo_fs.get(rid) or ''), 'n': c['provenienza.letture']['principi'],
                       'voti': c['proposto_principi_voti']}
        if r:
            out[rid] = r
    return out


def unione(prima, r11, tipo):
    if tipo == 'menzione_in_catena':
        return frozenset()
    return insieme(prima) | insieme(r11)


# ── misure ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def prf(coppie):
    tp = sum(len(v & p) for v, p in coppie); fp = sum(len(p - v) for v, p in coppie); fn = sum(len(v - p) for v, p in coppie)
    pr = tp / (tp + fp) if tp + fp else 0.0; ri = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * pr * ri / (pr + ri) if pr + ri else 0.0
    return {'F1': f1, 'P': pr, 'R': ri, 'id': sum(v == p for v, p in coppie) / len(coppie) if coppie else 0.0}


def boot(righe, chi, contro, campo, volte, seme=SEME):
    """differenza appaiata chi - contro sulla misura `campo`, ricampionando gli atti"""
    atti = collections.defaultdict(list)
    for x in righe:
        atti[x['atto']].append(x)
    chiavi = sorted(atti); rng = random.Random(seme); d = []
    for _ in range(volte):
        rr = [x for a in (rng.choice(chiavi) for _ in chiavi) for x in atti[a]]
        a = prf([(x['team'], x['v'][chi]) for x in rr])[campo]; b = prf([(x['team'], x['v'][contro]) for x in rr])[campo]
        d.append(a - b)
    d.sort()
    return d[int(0.025 * len(d))], d[min(len(d) - 1, int(0.975 * len(d)))], len(chiavi)


def tab(nome, righe, nomi, volte, confronti=('R05', 'R11')):
    if not righe:
        return {}
    print(f"\n== {nome}: {len(righe)} righe, {len({x['atto'] for x in righe})} atti ==")
    out = {}
    for chi in nomi:
        m = prf([(x['team'], x['v'][chi]) for x in righe])
        s = f"  {chi:7s} F1 {100*m['F1']:3.0f}  P {100*m['P']:3.0f}  R {100*m['R']:3.0f}  identici {100*m['id']:3.0f}%"
        out[chi] = dict(m)
        for k in confronti:
            if k != chi and volte and len({x['atto'] for x in righe}) > 1:
                lo, hi, _ = boot(righe, chi, k, 'F1', volte)
                di = m['F1'] - prf([(x['team'], x['v'][k]) for x in righe])['F1']
                s += f" | F1 contro {k} {100*di:+3.0f} [{100*lo:+.0f} {100*hi:+.0f}]"
                out[chi][f'dF1_{k}'] = (di, lo, hi)
        print(s)
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--volte', type=int, default=2000)
    a = ap.parse_args()
    G = json.load(open(C/'r11_su_giudicate.json', encoding='utf-8'))['righe']
    prima_tutte = json.load(open(C/'proposte_prima.json', encoding='utf-8'))
    ris = {}
    # 1. le righe giudicate
    calc = {}
    for caso in CASI:
        rr = [k for k, x in G.items() if x['caso'] == caso]
        calc.update(calcola_righe(caso, rr, {k: G[k]['prima']['tipo'] for k in rr}))
    # controllo: R11 ricalcolato = R11 del file di ieri sera
    diversi = [k for k, v in calc.items() if sorted(insieme(v['R11']['principi'])) != sorted(G[k]['r11']['principi'] or [])]
    print(f'controllo R11 ricalcolato contro r11_su_giudicate.json: {len(calc)} righe, diverse {len(diversi)}')
    righe, righe_pag = [], []
    for k, x in G.items():
        if x['team']['esito'] != 'confermata' or x['team']['principi'] is None or k not in calc or x['prima']['principi'] is None:
            continue
        v = {n: insieme(c['principi']) for n, c in calc[k].items()}
        v['R05'] = insieme(x['prima']['principi'])
        v['U'] = unione(x['prima']['principi'], calc[k]['R11']['principi'], calc[k]['R11']['tipo'])
        righe.append({'id': k, 'caso': x['caso'], 'atto': x['atto'], 'cieca': x['cieca'], 'team': frozenset(x['team']['principi']),
                      'v': v, 'n': calc[k]['R11']['n']})
        if x['team']['pagine'] is not None:
            comuni = set(x['prima']['pagine_candidate']) & set(calc[k]['R11']['cand'])
            vp = {n: frozenset(set(c['pagine']) & comuni) for n, c in calc[k].items()}
            vp['R05'] = frozenset(set(x['prima']['pagine']) & comuni)
            righe_pag.append({'id': k, 'caso': x['caso'], 'atto': x['atto'], 'cieca': x['cieca'],
                              'team': frozenset(set(x['team']['pagine']) & comuni), 'v': vp})
    nomi = ['R05', 'R11', 'V2', 'V2P', 'V2R', 'U']
    print('\n######## PRINCIPI ########')
    for nome, f in (('tutte', lambda x: True), ('alla cieca', lambda x: x['cieca']), ('proposta visibile', lambda x: not x['cieca']),
                    ('solo righe con 5 letture valide', lambda x: x['n'] == 5)):
        ris['principi ' + nome] = tab(nome, [x for x in righe if f(x)], nomi, a.volte)
    print('\n-- per caso (F1; tra parentesi cieche/visibili) --')
    per_caso = {}
    for caso in CASI:
        rr = [x for x in righe if x['caso'] == caso]
        if not rr:
            continue
        m = {n: prf([(x['team'], x['v'][n]) for x in rr])['F1'] for n in nomi}
        per_caso[caso] = {'n': len(rr), 'atti': len({x['atto'] for x in rr}), 'cieche': sum(x['cieca'] for x in rr), **m}
        print(f"  {caso:20s} n={len(rr):3d} atti={per_caso[caso]['atti']:2d} cieche={per_caso[caso]['cieche']:2d}  " +
              '  '.join(f'{n} {100*m[n]:3.0f}' for n in nomi))
    ris['principi per caso'] = per_caso
    # calibrazione: i principi a 2/5, con e senza prova, con e senza reranker
    print('\n-- principi a 2/5 (righe con 5 letture): quanti li prende il team --')
    cal = collections.defaultdict(lambda: [0, 0])
    for x in righe:
        if x['n'] != 5:
            continue
        for p in x['v']['V2'] - x['v']['R11']:
            cal['2/5 tutti'][1] += 1; cal['2/5 tutti'][0] += p in x['team']
            k1 = '2/5 con prova' if p in x['v']['V2P'] else '2/5 senza prova'
            k2 = '2/5 reranker >= 0,5' if p in x['v']['V2R'] else '2/5 reranker < 0,5'
            k3 = ('alla cieca' if x['cieca'] else 'visibile') + ', 2/5'
            k4 = '2/5 e nella proposta di prima' if p in x['v']['R05'] else '2/5 e NON nella proposta di prima'
            for kk in (k1, k2, k3, k4):
                cal[kk][1] += 1; cal[kk][0] += p in x['team']
    for k, (s, n) in cal.items():
        print(f'  {k:36s} {s}/{n} = {100*s/n:.0f}%')
    ris['calibrazione 2/5'] = {k: tuple(v) for k, v in cal.items()}
    print('\n######## PAGINE ATTORNO (solo pagine candidate sia in R05 sia in R11) ########')
    for nome, f in (('tutte', lambda x: True), ('alla cieca', lambda x: x['cieca']), ('proposta visibile', lambda x: not x['cieca'])):
        ris['pagine ' + nome] = tab(nome, [x for x in righe_pag if f(x)], ['R05', 'R11', 'V2', 'V2pag2'], a.volte, ('R05', 'R11', 'V2'))
    # 2. le righe caricate stanotte
    print('\n######## RIGHE CARICATE STANOTTE (non giudicate) ########')
    cambi = collections.Counter(); per_caso_c = {}
    for caso in CASI:
        sec = json.load(open(C/f'secco_ripresa_{caso}.json', encoding='utf-8'))
        tipo_fs = {k: (prima_tutte.get(k) or {}).get('proposto_tipo_citazione') or '' for k in sec}
        cc = calcola_righe(caso, list(sec), tipo_fs)
        c = collections.Counter()
        for k, s in sec.items():
            if k not in cc:
                c['non ricalcolata'] += 1; continue
            v = cc[k]
            c['righe'] += 1
            c['R11 ricalcolato diverso dal caricato'] += sorted(v['R11']['principi']) != sorted(s['proposto_principi'])
            pag_car = sorted(int(e['pagina']) for e in s['proposto_estensione'] if e['prosegue'])
            c['pagine R11 ricalcolate diverse dal caricato'] += v['R11']['pagine'] != pag_car
            for n in ('V2', 'V2P', 'V2R'):
                c[f'principi cambiati con {n}'] += insieme(v[n]['principi']) != insieme(v['R11']['principi'])
            c['pagine cambiate con V2 (pagine 3/5)'] += v['V2']['pagine'] != v['R11']['pagine']
            c['pagine cambiate con V2pag2'] += v['V2pag2']['pagine'] != v['R11']['pagine']
            pp = (prima_tutte.get(k) or {}).get('proposto_principi')
            if pp is not None:
                c['principi cambiati con U'] += unione(pp, v['R11']['principi'], v['R11']['tipo']) != insieme(v['R11']['principi'])
            c['V2: righe da «nessuno» a un principio'] += (not insieme(v['R11']['principi'])) and bool(insieme(v['V2']['principi']))
            c['V2: principi aggiunti'] += len(insieme(v['V2']['principi']) - insieme(v['R11']['principi']))
            c['V2: principi tolti'] += len(insieme(v['R11']['principi']) - insieme(v['V2']['principi']))
        per_caso_c[caso] = dict(c); cambi.update(c)
        print(f'  {caso:20s} ' + '; '.join(f'{k} {n}' for k, n in c.items()))
    print('  TUTTI: ' + json.dumps(dict(cambi), ensure_ascii=False, indent=1))
    ris['caricate stanotte'] = {'per caso': per_caso_c, 'tutti': dict(cambi)}
    json.dump({'scritto': '04/10/2026, tools/r12_varianti.py (nessuna lettura ne scrittura della banca dati)', 'misure': ris,
               'righe': [{**x, 'team': sorted(x['team']), 'v': {k: sorted(v) for k, v in x['v'].items()}} for x in righe]},
              open(C/'r12_varianti.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
    print('\nsalvato', C/'r12_varianti.json')


if __name__ == '__main__':
    main()
