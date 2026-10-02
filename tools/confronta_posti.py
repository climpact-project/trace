"""PAGINA INTERA CONTRO FINESTRE: a che posto finiscono le pagine giudicate dalle persone (26/09/2026).

   Per ogni pagina si prende il posto migliore fra le sonde (e le loro seconde formulazioni): una pagina
   entra fra le candidate se e' fra le prime k di almeno una. Si contano le confermate e le scartate dalle
   persone entro 100, 200, 500, 1.000, 5.000. Criterio fissato prima: le finestre sostituiscono la pagina
   intera solo se mettono piu' confermate fra le prime 500.
"""
import json, pathlib, sys
QUI = pathlib.Path(__file__).resolve().parent.parent
F = QUI/'training'/'fase2'
SOGLIE = (100, 200, 500, 1000, 5000)


def migliori(nome):
    p = F/nome
    if not p.exists():
        return None
    return {pid: min(v.values()) for pid, v in json.load(open(p)).items()}


def conta(m, n):
    return {k: sum(1 for x in m.values() if x <= k) for k in SOGLIE} | {'totale': n}


fuori = {}
for gruppo in ('confermate', 'scartate'):
    n = len(json.load(open(F/f'pagine_{gruppo}.json')))
    # tutte le varianti misurate: posti_pagine_<gruppo><suffisso>.json
    varianti = sorted(((x.stem[len(f'posti_pagine_{gruppo}'):].lstrip('_') or 'pplx_distillato',
                        x.stem[len(f'posti_pagine_{gruppo}'):]) for x in F.glob(f'posti_pagine_{gruppo}*.json')))
    for modo, suff in varianti:
        nome = f'posti_pagine_{gruppo}{suff}.json'
        m = migliori(nome)
        if m is not None:
            fuori[f'{gruppo}_{modo}'] = conta(m, n)
            if gruppo == 'confermate':
                # SOLO I DOCUMENTI DI PROVA: le pagine che nessun adattatore ha visto in addestramento
                prova = {json.loads(l)['document_id'] for l in open(QUI/'training'/'urgenda_decisione_prova_corrette_larghe.jsonl', encoding='utf-8')}
                mp = {p: v for p, v in m.items() if p.split('#')[0] in prova}
                fuori[f'{gruppo}_PROVA_{modo}'] = conta(mp, sum(1 for p in json.load(open(F/'pagine_confermate.json')) if p.split('#')[0] in prova))
                # e il resto: con queste si SCEGLIE (per esempio il peso del WiSE-FT), con la prova si verifica
                ma = {p: v for p, v in m.items() if p.split('#')[0] not in prova}
                fuori[f'{gruppo}_SCELTA_{modo}'] = conta(ma, sum(1 for p in json.load(open(F/'pagine_confermate.json')) if p.split('#')[0] not in prova))
json.dump(fuori, open(F/'confronto_pagina_finestre.json', 'w'), indent=1)
for k, v in fuori.items():
    print(f'{k:36s}', '  '.join(f'{s}:{v[s]}' for s in SOGLIE), f' su {v["totale"]}')
