"""IL CATALOGO PARZIALE CON e5, DALL'INDICE DI LUGLIO — il metro di paragone.

   e5 e' bocciato come primo modello (§60.1), ma nel catalogo parziale serve da
   paragone: e' il sistema con cui sono nate tutte le righe giudicate. Invece di
   rileggere 66.000 frammenti su una GPU, si prendono i loro vettori dall'indice
   di luglio (`index/vettori.npy`, stesso modello, stessa frammentazione), cioe'
   ESATTAMENTE i numeri del sistema di oggi. Un frammento del catalogo si ritrova
   nell'indice per documento e fine del frammento (`char_end`); quelli non
   ritrovati (documenti riparati dopo luglio) si dichiarano.

   Stesse misure di `catalogo_parziale.py`: vere trovate, bocciate, disturbo, ai
   primi 50, 200 e 500 posti di ogni sonda.
"""
import collections, json, pathlib
import numpy as np

QUI = pathlib.Path(__file__).resolve().parent.parent
T = QUI/'training'


def main():
    import torch, torch.nn.functional as F
    from transformers import AutoTokenizer, AutoModel
    c = json.loads((T/'catalogo_parziale.json').read_text(encoding='utf-8'))
    Fr, R = c['frammenti'], [r for r in c['righe'] if r['parte'] == 'prova']
    docs = {f['doc'] for f in Fr}
    ids = json.load(open(QUI/'index'/'ids.json'))
    riga_di = {i: n for n, i in enumerate(ids)}
    chiave = {}
    with open(QUI/'index'/'chunks.jsonl', encoding='utf-8') as f:
        for l in f:
            d = l[8:l.find('"', 8)]            # l'id, senza decodificare tutta la riga
            if d.split('#')[0] not in docs:
                continue
            x = json.loads(l)
            chiave[(x['document_id'], x['char_end'])] = riga_di[x['id']]
    tenuti = [(f, chiave.get((f['doc'], f['a']))) for f in Fr]
    print(f'frammenti del catalogo {len(Fr)}, ritrovati nell\'indice {sum(n is not None for _, n in tenuti)}', flush=True)
    # MISURATO IL 23/09/2026: solo il 31,6% si ritrova, perche' molti documenti
    # sono stati riparati dopo luglio e le posizioni non coincidono piu'. Un
    # paragone su un terzo del catalogo non vale: i frammenti si rileggono con
    # e5 qui, stesso modello e stesso prefisso dell'indice.
    dev = 'mps' if torch.backends.mps.is_available() else 'cpu'
    tok = AutoTokenizer.from_pretrained('intfloat/multilingual-e5-large')
    m = AutoModel.from_pretrained('intfloat/multilingual-e5-large', torch_dtype=torch.float16).to(dev).eval()
    U, blocchi = Fr, []
    with torch.no_grad():
        for i in range(0, len(U), 64):
            e = tok(['passage: ' + f['testo'] for f in U[i:i+64]], padding=True, truncation=True, max_length=512, return_tensors='pt').to(dev)
            h = m(**e).last_hidden_state.float(); k = e['attention_mask'].unsqueeze(-1).float()
            blocchi.append(F.normalize((h*k).sum(1)/k.sum(1), dim=-1).cpu().numpy())
            if i % 6400 == 0:
                print(f'  {i}/{len(U)}', flush=True)
    M = np.concatenate(blocchi)
    sonde = sorted({r['sonda'] for r in R})
    with torch.no_grad():
        e = tok(['passage: ' + s for s in sonde], padding=True, truncation=True, max_length=512, return_tensors='pt').to(dev)
        h = m(**e).last_hidden_state.float(); k = e['attention_mask'].unsqueeze(-1).float()
        Q = dict(zip(sonde, F.normalize((h*k).sum(1)/k.sum(1), dim=-1).cpu().numpy()))

    vere, bocciate = collections.defaultdict(set), collections.defaultdict(set)
    for r in R:
        (vere if r['etichetta'] else bocciate)[r['sonda']].add((r['doc'], r['pagina']))
    esiti = {}
    for K in (50, 200, 500):
        tr = bo = di = tot = 0
        for s in sonde:
            coperte = set()
            for i in np.argsort(-(M @ Q[s]))[:K]:
                u = U[i]
                for p in range(u['pagina'], u.get('pagina_fine', u['pagina']) + 1):
                    coperte.add((u['doc'], p))
                di += u['disturbo']
            tr += len(vere[s] & coperte); tot += len(vere[s]); bo += len(bocciate[s] & coperte)
        esiti[K] = {'trovate': tr, 'di': tot, 'bocciate': bo, 'disturbo': di/(K*len(sonde))}
        print(f'  {"e5, frammenti (oggi)":36s} primi {K:3d}: vere trovate {tr}/{tot} ({100*tr/max(tot,1):.0f}%)  '
              f'bocciate {bo}  dal disturbo {100*di/(K*len(sonde)):.0f}%', flush=True)
    (T/'esiti_catalogo_e5_indice.json').write_text(json.dumps(esiti, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
