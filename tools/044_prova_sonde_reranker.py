"""LA PROVA DELLE SONDE COL RERANKER (01/10/2026, il PI: «sistema le sonde problematiche e riprovale»).

   Domanda: il TRACE-Reranker (T01) separa le sonde di un caso? Metro: le citazioni che indicano paragrafi della
   sentenza da cui viene UN solo principio (mappa dei paragrafi: una regola, non un modello). Una citazione e' «giusta»
   se la sonda col punteggio piu' alto sul brano e' quella dei paragrafi. Le citazioni sono divise in due meta' PER
   DOCUMENTO (impronta del nome del documento, pari = sviluppo, dispari = verifica): i testi delle sonde si correggono
   guardando solo lo sviluppo; il risultato che conta e' quello della verifica, che non si guarda mentre si scrive.
   Limiti: T01 e' addestrato su Urgenda e qui lavora senza addestramento; la mappa e' un metro di coerenza, non un
   giudizio umano. Scrive training/confronto_sonde/reranker_<caso>.json.

   Uso:  .venv/bin/python tools/044_prova_sonde_reranker.py --caso neubauer --serie P03 P04
"""
import argparse, collections, glob, hashlib, json, pathlib
QUI = pathlib.Path(__file__).resolve().parent.parent
P, C = QUI/'training'/'principi', QUI/'training'/'confronto_sonde'


def meta(rid):
    return 'sviluppo' if int(hashlib.sha256(rid.split('__')[1].encode()).hexdigest(), 16) % 2 == 0 else 'verifica'


def punteggi(caso, serie):
    b = collections.defaultdict(dict)
    for f in glob.glob(str(P/f'{caso}_{serie}_punteggi_*.jsonl')):
        for l in open(f, encoding='utf-8'):
            x = json.loads(l)
            if x['dove'] == 'brano':
                b[x['riga']][x['principio'].split('.')[-1]] = x['punteggio']
    return b


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--caso', required=True); ap.add_argument('--serie', nargs='+', required=True)
    a = ap.parse_args()
    out = {}
    for s in a.serie:
        b = punteggi(a.caso, s)
        par = {json.loads(l)['id']: json.loads(l) for l in open(P/f'{a.caso}_da_paragrafi_{s}.jsonl', encoding='utf-8')}
        r = {'sviluppo': [0, 0], 'verifica': [0, 0]}; per = collections.defaultdict(lambda: [0, 0]); primo = collections.Counter()
        for rid, sc in b.items():
            primo[max(sc, key=sc.get)] += 1
            pp = (par.get(rid) or {}).get('principi') or []
            if len(pp) == 1:
                ok = max(sc, key=sc.get) == pp[0].split('.')[-1]
                m = meta(rid); r[m][0] += ok; r[m][1] += 1
                if m == 'verifica':
                    per[pp[0].split('.')[-1]][0] += ok; per[pp[0].split('.')[-1]][1] += 1
        k = len(next(iter(b.values()))) if b else 0
        out[s] = {'citazioni': len(b), 'sonde': k, 'caso_fortuito': round(1 / k, 3) if k else None,
                  **{f'{m}_giusti': r[m][0] for m in r}, **{f'{m}_prove': r[m][1] for m in r},
                  **{f'{m}_quota': round(r[m][0] / r[m][1], 3) if r[m][1] else None for m in r},
                  'verifica_per_sonda': {p: f'{g}/{t}' for p, (g, t) in sorted(per.items(), key=lambda kv: -kv[1][1])},
                  'sonda_prima_su_tutte': dict(primo.most_common())}
    C.mkdir(exist_ok=True)
    json.dump(out, open(C/f'reranker_{a.caso}.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for s, x in out.items():
        print(f"== {a.caso} {s}: sviluppo {x['sviluppo_giusti']}/{x['sviluppo_prove']} ({x['sviluppo_quota']}), "
              f"VERIFICA {x['verifica_giusti']}/{x['verifica_prove']} ({x['verifica_quota']}), caso {x['caso_fortuito']}")
        print('   verifica per sonda:', x['verifica_per_sonda'])
        print('   sonda prima su tutte le citazioni:', x['sonda_prima_su_tutte'])


if __name__ == '__main__':
    main()
