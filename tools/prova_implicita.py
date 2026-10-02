#!/usr/bin/env python3
"""LA RIPRESA IMPLICITA: SI PUO' MISURARE SENZA CODIFICARE A MANO?

IL PROBLEMA. Le due prove precedenti passavano entrambe dal nome del caso —
il testo di origine, oppure passaggi che lo nominano altrove. Nessuna delle
due dice niente su cio' che davvero ci interessa: i passaggi che riprendono
il ragionamento SENZA nominarlo. E quelli, per definizione, non si
riconoscono da una stringa.

DUE PROVE, NESSUNA DELLE QUALI E' SUFFICIENTE DA SOLA.

(1) LE FORMULAZIONI ESCLUSE COME CONTROLLO NEGATIVO — automatica.
    Per ogni sonda sono dichiarate una o due proposizioni che le somigliano
    ma dicono altro: il dovere di diligenza civilistico ordinario, la
    separazione dei poteri generica, le responsabilita' comuni ma
    differenziate. Si guardano i primi risultati che NON nominano il caso —
    cioe' i candidati alla ripresa implicita — e si conta quanti sono piu'
    vicini a una formulazione esclusa che alla sonda.
    Meno ce ne sono, meglio la variante sta distinguendo la dottrina dal suo
    sosia. E' un controllo negativo, non una misura di richiamo: dice quanto
    sporco entra, non quanto pulito si perde.

(2) IL CAMPIONE DI DISACCORDO — da leggere.
    Non serve giudicare tutti i risultati: serve giudicare quelli su cui le
    varianti NON sono d'accordo, perche' sono gli unici che la scelta
    cambia. Si mettono insieme i primi risultati delle tre varianti, si
    tolgono quelli che nominano il caso, e si tengono i frammenti presenti
    in alcune varianti e non in altre. Quel gruppo si legge.

    Questo e' il modo standard di costruire un insieme di giudizi quando non
    si puo' giudicare tutto: si mettono in comune i risultati di tutti i
    sistemi in gara e si giudica quell'insieme, cosi' nessuna variante e'
    favorita dall'essere stata usata per costruire la prova.
"""

import csv
import json
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
INDEX = HERE / 'index'
sys.path.insert(0, str(HERE / 'tools'))
from cerca import leggi_caso  # noqa: E402

VARIANTI = [('query: ', 'query'), ('passage: ', 'passage'), ('', 'niente')]
K = 200
K_POOL = 25


def main():
    caso = sys.argv[1] if len(sys.argv) > 1 else 'urgenda'
    conf = leggi_caso(HERE / 'cited-cases' / f'{caso}.yaml')
    man = json.loads((INDEX / 'manifesto.json').read_text(encoding='utf-8'))
    V = np.load(INDEX / 'vettori.npy', mmap_mode='r')
    ids = json.loads((INDEX / 'ids.json').read_text(encoding='utf-8'))

    print('carico i frammenti…', flush=True)
    fr = {}
    with (INDEX / 'chunks.jsonl').open(encoding='utf-8') as f:
        for riga in f:
            d = json.loads(riga)
            fr[d['id']] = d
    # I CANDIDATI ALLA RIPRESA IMPLICITA: non stanno nel giudizio citato e
    # non lo nominano. Tutto il resto e' citazione esplicita, gia' misurata.
    implicito = np.array([
        caso not in (fr.get(i, {}).get('file') or '').lower()
        and caso not in (fr.get(i, {}).get('testo') or '').lower()
        for i in ids])
    print(f'  candidati impliciti nell indice: {int(implicito.sum()):,}\n', flush=True)

    from sentence_transformers import SentenceTransformer
    import torch
    dev = ('cuda' if torch.cuda.is_available()
           else 'mps' if torch.backends.mps.is_available() else 'cpu')
    m = SentenceTransformer(man['modello'], device=dev)
    m.max_seq_length = man.get('max_token', 512)

    # Le formulazioni escluse, per sonda, gia' trasformate in vettori.
    escluse = conf.get('escluse', [])
    E = (m.encode([e['testo'] for e in escluse], normalize_embeddings=True,
                  convert_to_numpy=True, show_progress_bar=False).astype(np.float16)
         if escluse else None)
    per_sonda = {}
    for i, e in enumerate(escluse):
        per_sonda.setdefault(e['per'], []).append((e['id'], E[i]))

    esiti, pool = {}, {}
    for pre, nome in VARIANTI:
        Q = m.encode([pre + s['testo'] for s in conf['sonde']],
                     normalize_embeddings=True, convert_to_numpy=True,
                     show_progress_bar=False).astype(np.float16)
        sporchi = tot = 0
        margini = []
        pool[nome] = {}
        for i, s in enumerate(conf['sonde']):
            punt = V @ Q[i]
            ordine = [j for j in np.argsort(-punt)[:K * 3] if implicito[j]][:K]
            pool[nome][s['id']] = [ids[j] for j in ordine[:K_POOL]]
            mie = per_sonda.get(s['id'], [])
            if not mie:
                continue
            for j in ordine:
                p_escl = max(float(V[j] @ v) for _, v in mie)
                marg = float(punt[j]) - p_escl
                margini.append(marg)
                tot += 1
                if marg <= 0:
                    sporchi += 1
        esiti[nome] = (sporchi, tot, float(np.mean(margini)) if margini else 0.0)

    print('CONTROLLO NEGATIVO — fra i primi 200 candidati IMPLICITI di ogni sonda,')
    print('quanti sono piu vicini a una formulazione esclusa che alla sonda\n')
    print(f"{'variante':14s}{'sospetti':>12s}{'su':>8s}{'quota':>10s}{'margine medio':>16s}")
    for _, nome in VARIANTI:
        sp, tot, mm = esiti[nome]
        print(f'{nome:14s}{sp:>12,}{tot:>8,}{sp/max(tot,1)*100:>9.1f}%{mm:>16.4f}')

    # ── il campione di disaccordo, da leggere ───────────────────────────
    righe = []
    for s in conf['sonde']:
        conteggio = {}
        for _, nome in VARIANTI:
            for r, fid in enumerate(pool[nome][s['id']]):
                conteggio.setdefault(fid, {})[nome] = r + 1
        for fid, dove in conteggio.items():
            if len(dove) == len(VARIANTI):
                continue          # d'accordo: non discrimina, non si legge
            d = fr.get(fid, {})
            righe.append({
                'sonda': s['id'],
                'in_query': dove.get('query', ''),
                'in_passage': dove.get('passage', ''),
                'in_niente': dove.get('niente', ''),
                'giudizio': '',       # si | no | dubbio  — da riempire
                'testo': re.sub(r'\s+', ' ', d.get('testo', ''))[:900],
                'file': d.get('file', ''),
                'pagina': d.get('pagina', ''),
                'id': fid,
            })
    out = INDEX / f'disaccordo_{caso}.csv'
    with out.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(righe[0].keys()))
        w.writeheader()
        w.writerows(righe)
    print(f'\nCAMPIONE DI DISACCORDO: {len(righe):,} frammenti')
    print(f'  (presenti nei primi {K_POOL} di alcune varianti e non di altre)')
    print(f'  {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
