"""LE FORMULAZIONI ALTERNATIVE DELLE SONDE DEBOLI (02/10/2026, il PI: «fai formulazioni alternative e prova»).

   La prova del reranker sui casi nuovi (`044_prova_sonde_reranker.py`, serie P06, P07, P08) ha trovato sonde che quasi non
   vincono mai sulle citazioni che la mappa dei paragrafi attribuisce a loro. Per ognuna ci sono tre formulazioni in
   `training/confronto_sonde/alternative_2026-10-02.yaml` (A: la frase della decisione; B: corta, con le parole proprie;
   C: come la riassume chi cita). Qui:
     prepara  Mac -> training/principi/alt_<caso>_coppie.jsonl: il brano di ogni citazione della prova contro ogni
              formulazione alternativa (le sonde in uso hanno gia' il loro punteggio sullo stesso brano, stesso modello);
     valuta   Mac -> training/confronto_sonde/alternative_<caso>.json: per ogni sonda debole si sceglie la formulazione
              che fa meglio sulla meta' SVILUPPO (le altre sonde ferme), una sonda alla volta; il risultato che conta e'
              quello sulla meta' VERIFICA, che la scelta non guarda. Stessa divisione per documento di prova_sonde_reranker.

   Uso:  .venv/bin/python tools/045_prova_sonde_alternative.py prepara
         (punteggi su ReCaS: 028_ripresa_punteggi.py punteggi --caso alt_<caso>)
         .venv/bin/python tools/045_prova_sonde_alternative.py valuta
"""
import argparse, collections, glob, json, pathlib, sys
import yaml
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
P, C = QUI/'training'/'principi', QUI/'training'/'confronto_sonde'
ALT = C/'alternative_2026-10-02.yaml'
SERIE = {'klimaseniorinnen': 'P06', 'cig-parere-clima': 'P07', 'idh-oc-32-25': 'P08'}
ALLARGA = 800


def meta(rid):
    import hashlib
    return 'sviluppo' if int(hashlib.sha256(rid.split('__')[1].encode()).hexdigest(), 16) % 2 == 0 else 'verifica'


def prova(caso):
    """le citazioni della prova: quelle che la mappa dei paragrafi attribuisce a UN solo principio"""
    out = {}
    for l in open(P/f'{caso}_da_paragrafi.jsonl', encoding='utf-8'):
        x = json.loads(l)
        if len(x.get('principi') or []) == 1:
            out[x['id']] = x['principi'][0].split('.')[-1]
    return out


def prepara():
    _m_prepara_training = __import__('026_prepara_training')
    mascheratore = _m_prepara_training.mascheratore
    SEGNAPOSTO = _m_prepara_training.SEGNAPOSTO
    alt = yaml.safe_load(open(ALT, encoding='utf-8'))
    for caso, sonde in alt.items():
        conf = yaml.safe_load(open(QUI/'cited-cases'/f'{caso}.yaml', encoding='utf-8'))
        maschera = mascheratore([str(f) for f in conf['forme']] + [conf.get('nome', '')])
        ids = prova(caso); n = 0
        with open(P/f'alt_{caso}_coppie.jsonl', 'w', encoding='utf-8') as f:
            for l in open(QUI/'training'/f'lessicali_{caso}_righe.jsonl', encoding='utf-8'):
                r = json.loads(l)
                if r['id'] not in ids:
                    continue
                ctx = r['contesto']; a, b = ctx.find('[[INIZIO DEL BRANO SEGNALATO]]'), ctx.find('[[FINE DEL BRANO SEGNALATO]]')
                if a < 0 or b < 0:
                    continue
                brano = ctx[max(0, a - ALLARGA): b + len('[[FINE DEL BRANO SEGNALATO]]') + ALLARGA]
                brano = brano.replace('[[INIZIO DEL BRANO SEGNALATO]]', '').replace('[[FINE DEL BRANO SEGNALATO]]', '').replace('⟦', '').replace('⟧', '')
                brano = maschera.sub(SEGNAPOSTO, ' '.join(brano.split()))
                for sonda, varianti in sonde.items():
                    for v, testo in varianti.items():
                        f.write(json.dumps({'riga': r['id'], 'dove': 'brano', 'pagina': r.get('pagina'), 'principio': f'{sonda}#{v}',
                                            'q': ' '.join(testo.split()), 'd': brano}, ensure_ascii=False) + '\n'); n += 1
        print(caso, len(ids), 'citazioni della prova,', n, 'coppie')


def quota(b, ids, scelta, metà):
    g = t = 0; per = collections.defaultdict(lambda: [0, 0])
    for rid, giusto in ids.items():
        sc = b.get(rid)
        if not sc or meta(rid) != metà:
            continue
        val = {}
        for p in set(k.split('#')[0] for k in sc):
            k = f'{p}#{scelta[p]}' if scelta.get(p, 'in_uso') != 'in_uso' else p
            if k in sc:
                val[p] = sc[k]
        if giusto not in val:
            continue
        ok = max(val, key=val.get) == giusto; g += ok; t += 1; per[giusto][0] += ok; per[giusto][1] += 1
    return g, t, {p: f'{a}/{b}' for p, (a, b) in per.items()}


def valuta():
    alt = yaml.safe_load(open(ALT, encoding='utf-8')); out = {}
    for caso, sonde in alt.items():
        ids = prova(caso); b = collections.defaultdict(dict)
        for f in glob.glob(str(P/f'{caso}_{SERIE[caso]}_punteggi_*.jsonl')) + glob.glob(str(P/f'alt_{caso}_punteggi_*.jsonl')):
            for l in open(f, encoding='utf-8'):
                x = json.loads(l)
                if x['dove'] == 'brano' and x['riga'] in ids:
                    b[x['riga']][x['principio'].split('.')[-1]] = x['punteggio']
        scelta = {}
        prima = {m: quota(b, ids, scelta, m) for m in ('sviluppo', 'verifica')}
        for sonda in sonde:                             # una sonda alla volta, le altre ferme sulla scelta fin qui
            prove = {v: quota(b, ids, dict(scelta, **{sonda: v}), 'sviluppo')[0] for v in ['in_uso'] + list(sonde[sonda])}
            scelta[sonda] = max(prove, key=lambda v: (prove[v], v == 'in_uso'))
        dopo = {m: quota(b, ids, scelta, m) for m in ('sviluppo', 'verifica')}
        out[caso] = {'scelta': scelta,
                     'prima': {m: f'{g}/{t} ({g / t:.3f})' for m, (g, t, _) in prima.items()},
                     'dopo': {m: f'{g}/{t} ({g / t:.3f})' for m, (g, t, _) in dopo.items()},
                     'verifica_per_sonda_prima': prima['verifica'][2], 'verifica_per_sonda_dopo': dopo['verifica'][2]}
        print(f"== {caso}: scelta {scelta}")
        print(f"   sviluppo {out[caso]['prima']['sviluppo']} -> {out[caso]['dopo']['sviluppo']}; VERIFICA {out[caso]['prima']['verifica']} -> {out[caso]['dopo']['verifica']}")
        print(f"   verifica per sonda prima {prima['verifica'][2]}")
        print(f"   verifica per sonda dopo  {dopo['verifica'][2]}")
    json.dump(out, open(C/'alternative_2026-10-02_esito.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('fase', choices=['prepara', 'valuta'])
    a = ap.parse_args()
    prepara() if a.fase == 'prepara' else valuta()
