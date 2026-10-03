"""IL CONFRONTO FRA DUE SERIE DI SONDE (01/10/2026, il PI: «non buttare i vecchi, vediamo come va»).

   Le proposte si calcolano con le stesse regole della piattaforma (`035_carica_ripresa.py --salva`), una volta con le sonde
   in uso (P02) e una con quelle in prova (P03, TRACE_SONDE=P03); qui si mettono a confronto. Tre misure:
   1. Uso: quante citazioni ricevono almeno un principio, quante «nessuno», e quanto pesa ogni sonda.
   2. Il reranker separa le sonde? Sulle citazioni che indicano paragrafi da cui viene UN solo principio (la mappa dei
      paragrafi: una regola, non un modello), quante volte il principio col punteggio piu' alto di T01 e' proprio quello.
      La lettura di DeepSeek non si misura cosi': nel suo prompt c'e' gia' il principio della mappa (sarebbe circolare).
      Il caso fortuito e' 1 su numero di sonde.
   3. Seguito: quante citazioni hanno almeno una pagina di seguito proposta.
   Non c'e' un metro umano (Neubauer: 1 citazione giudicata; Future Generations: 0): sono misure di coerenza, non di
   correttezza. Scrive training/confronto_sonde/<caso>.md e .json.

   Uso:  .venv/bin/python tools/046_confronta_sonde.py --caso neubauer
"""
import argparse, collections, json, pathlib
QUI = pathlib.Path(__file__).resolve().parent.parent
P, C = QUI/'training'/'principi', QUI/'training'/'confronto_sonde'


def misure(proposte, paragrafi):
    n = len(proposte)
    uso = collections.Counter(); nessuno = con = 0; seguito = 0
    for c in proposte.values():
        pr = [x for x in (c.get('proposto_principi') or []) if x != 'nessuno']
        if pr:
            con += 1
            for x in pr:
                uso[x.split('.')[-1]] += 1
        else:
            nessuno += 1
        seguito += any(v.get('prosegue') for v in (c.get('proposto_estensione') or []))
    giusti = tot = 0; k = None
    for rid, c in proposte.items():
        pp = (paragrafi.get(rid) or {}).get('principi') or []
        sc = c.get('proposto_punteggi_principi') or {}
        k = k or len(sc)
        if len(pp) == 1 and sc:
            tot += 1
            giusti += max(sc, key=sc.get) == pp[0]
    return {'citazioni': n, 'con_principio': con, 'nessuno': nessuno, 'con_seguito': seguito,
            'uso': dict(uso.most_common()), 'reranker_giusti': giusti, 'reranker_prove': tot,
            'reranker_quota': round(giusti / tot, 3) if tot else None, 'caso_fortuito': round(1 / k, 3) if k else None}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--caso', required=True); ap.add_argument('--a', default='P02'); ap.add_argument('--b', default='P03')
    a = ap.parse_args()
    out = {}
    for s in (a.a, a.b):
        prop = json.load(open(C/f'{a.caso}_{s}.json', encoding='utf-8'))
        suf = '' if s == a.a else f'_{s}'
        par = {json.loads(l)['id']: json.loads(l) for l in open(P/f'{a.caso}_da_paragrafi{suf}.jsonl', encoding='utf-8')}
        out[s] = misure(prop, par)
    comuni = set(json.load(open(C/f'{a.caso}_{a.a}.json'))) & set(json.load(open(C/f'{a.caso}_{a.b}.json')))
    out['citazioni_in_comune'] = len(comuni)
    json.dump(out, open(C/f'{a.caso}.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    x, y = out[a.a], out[a.b]
    pct = lambda m, d: f'{m} ({100 * m / d:.0f}%)' if d else str(m)
    righe = [f'# Confronto delle sonde: {a.caso}, {a.a} contro {a.b}', '',
             f'Citazioni da giudicare confrontate: {out["citazioni_in_comune"]}.', '',
             f'| Misura | {a.a} | {a.b} |', '|---|---|---|',
             f'| Citazioni con almeno un principio | {pct(x["con_principio"], x["citazioni"])} | {pct(y["con_principio"], y["citazioni"])} |',
             f'| Citazioni «nessuno» | {pct(x["nessuno"], x["citazioni"])} | {pct(y["nessuno"], y["citazioni"])} |',
             f'| Citazioni con un seguito proposto | {pct(x["con_seguito"], x["citazioni"])} | {pct(y["con_seguito"], y["citazioni"])} |',
             f'| Reranker: punteggio piu\' alto sul principio dei paragrafi | {x["reranker_giusti"]} su {x["reranker_prove"]} ({x["reranker_quota"]}) | {y["reranker_giusti"]} su {y["reranker_prove"]} ({y["reranker_quota"]}) |',
             f'| Caso fortuito (1 su numero di sonde) | {x["caso_fortuito"]} | {y["caso_fortuito"]} |', '',
             f'## Quanto pesa ogni sonda', '', f'**{a.a}**', '']
    righe += [f'- {k}: {v}' for k, v in x['uso'].items()] + ['', f'**{a.b}**', '']
    righe += [f'- {k}: {v}' for k, v in y['uso'].items()]
    righe += ['', 'Misure di coerenza, non di correttezza: nessun giudizio umano su questi casi. Il reranker (T01) e\' stato '
                  'addestrato su Urgenda: sulle sonde di Neubauer e Future Generations lavora senza addestramento, con tutte e due le serie.']
    (C/f'{a.caso}.md').write_text('\n'.join(righe) + '\n', encoding='utf-8')
    print('\n'.join(righe))


if __name__ == '__main__':
    main()
