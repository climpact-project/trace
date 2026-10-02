#!/usr/bin/env python3
"""IL PREFISSO DELLA SONDA CAMBIA I RISULTATI? DI QUANTO?

LA DOMANDA. I passaggi del corpus sono stati codificati con il prefisso
`passage: `, cotto ormai dentro i vettori. Per la sonda invece si sceglie
al momento della ricerca, e la scelta non e' ovvia: gli autori di E5
raccomandano prefissi diversi (`query: ` / `passage: `) nei compiti
ASIMMETRICI — domanda breve, passaggio lungo — e lo stesso prefisso su
entrambi i lati in quelli SIMMETRICI, dove i due testi sono della stessa
natura. Le nostre sonde non sono domande: sono proposizioni giuridiche
lunghe quanto un passaggio e scritte nella stessa lingua di rito.

COME SI MISURA SENZA UN GIUDIZIO UMANO. Serve un insieme di passaggi di cui
si sappia in anticipo che sono pertinenti. Ce l'abbiamo, e non e' una
scelta arbitraria: le sonde sono state ricavate DALLE PAROLE DELLA
SENTENZA citata. Quindi i frammenti dei documenti di quel giudizio sono
pertinenti per costruzione — sono il testo da cui la proposizione e' presa.
Una variante che li fa risalire piu' in alto sta allineando meglio la sonda
al modo in cui il corpus e' stato codificato.

NON E' UNA MISURA DI QUALITA' FINALE, ed e' bene dirlo: misura l'aggancio
alla fonte, non la capacita' di trovare la ripresa implicita altrove. Serve
a decidere fra tre varianti dello stesso strumento, non a validare il
metodo.
"""

import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
INDEX = HERE / 'index'
sys.path.insert(0, str(HERE / 'tools'))
_m_cerca = __import__('016_cerca')
leggi_caso = _m_cerca.leggi_caso

VARIANTI = [
    ('query: ', 'asimmetrico (attuale)'),
    ('passage: ', 'stesso prefisso dei passaggi'),
    ('', 'nessun prefisso'),
]
K = 200


def main():
    caso = sys.argv[1] if len(sys.argv) > 1 else 'urgenda'
    conf = leggi_caso(HERE / 'cited-cases' / f'{caso}.yaml')
    man = json.loads((INDEX / 'manifesto.json').read_text(encoding='utf-8'))
    print(f"indice   : {man['frammenti']:,} frammenti, {man['modello']}")
    print(f"passaggi codificati con: {man['prefisso_passaggio']!r}\n", flush=True)

    V = np.load(INDEX / 'vettori.npy', mmap_mode='r')
    ids = json.loads((INDEX / 'ids.json').read_text(encoding='utf-8'))

    # Quali righe della matrice appartengono al giudizio citato.
    # Si riconosce dal percorso del file, che porta il nome del caso.
    # DUE BERSAGLI, NON UNO — e il secondo conta di piu'.
    #
    # (A) i frammenti del giudizio citato. Pertinenti per costruzione, ma
    #     misurano il ritrovamento QUASI ALLA LETTERA del testo da cui la
    #     sonda e' stata ricavata: una variante brava a riconoscere il
    #     quasi-identico vince qui senza per questo essere brava sul resto.
    # (B) i frammenti che parlano del caso citato ALTROVE — testo che lo
    #     nomina, in documenti di altri giudizi. E' la ripresa esplicita in
    #     un contesto diverso, cioe' molto piu' vicino a cio' che la rete
    #     semantica deve davvero saper fare.
    print('individuo i due bersagli…', flush=True)
    fr_file, fr_txt = {}, {}
    with (INDEX / 'chunks.jsonl').open(encoding='utf-8') as f:
        for riga in f:
            d = json.loads(riga)
            fr_file[d['id']] = d['file']
            fr_txt[d['id']] = d['testo']
    dentro = np.array([caso in (fr_file.get(i) or '').lower() for i in ids])
    fuori = np.array([
        (caso not in (fr_file.get(i) or '').lower())
        and (caso in (fr_txt.get(i) or '').lower())
        for i in ids])
    print(f'  (A) nel giudizio citato : {int(dentro.sum()):,} frammenti')
    print(f'  (B) che lo nominano altrove: {int(fuori.sum()):,} frammenti\n', flush=True)
    BERSAGLI = [('A: nel giudizio citato', dentro),
                ('B: ripreso altrove', fuori)]

    from sentence_transformers import SentenceTransformer
    import torch
    dev = ('cuda' if torch.cuda.is_available()
           else 'mps' if torch.backends.mps.is_available() else 'cpu')
    m = SentenceTransformer(man['modello'], device=dev)
    m.max_seq_length = man.get('max_token', 512)
    print(f'modello caricato su {dev}\n', flush=True)

    risultati = {}
    primi = {}
    for pre, nome in VARIANTI:
        Q = m.encode([pre + s['testo'] for s in conf['sonde']],
                     normalize_embeddings=True, convert_to_numpy=True,
                     show_progress_bar=False).astype(np.float16)
        conta = {b: [] for b, _ in BERSAGLI}
        top = {}
        t0 = time.time()
        for i, s in enumerate(conf['sonde']):
            punt = V @ Q[i]
            ordine = np.argsort(-punt)[:K]
            for nb, mask in BERSAGLI:
                conta[nb].append(int(mask[ordine].sum()))
            top[s['id']] = [ids[j] for j in ordine[:20]]
        risultati[nome] = (conta, time.time() - t0)
        primi[nome] = top

    for nb, _ in BERSAGLI:
        print(f'\nBERSAGLIO {nb} — quanti nei primi {K}\n')
        intest = f"{'sonda':24s}"
        for _, nome in VARIANTI:
            intest += f'{nome[:26]:>28s}'
        print(intest)
        for i, s in enumerate(conf['sonde']):
            riga = f"{s['id'][:23]:24s}"
            for _, nome in VARIANTI:
                conta, _ = risultati[nome]
                riga += f'{conta[nb][i]:>28}'
            print(riga)
        riga = f"{'TOTALE':24s}"
        for _, nome in VARIANTI:
            conta, _ = risultati[nome]
            riga += f'{sum(conta[nb]):>28}'
        print(riga)

    print('\nQUANTO CAMBIANO I PRIMI 20 (sovrapposizione con la variante attuale)')
    base = primi['asimmetrico (attuale)']
    for _, nome in VARIANTI[1:]:
        quote = []
        for s in conf['sonde']:
            a, b = set(base[s['id']]), set(primi[nome][s['id']])
            quote.append(len(a & b) / 20)
        print(f'  {nome:32s} {np.mean(quote)*100:.0f}% in comune '
              f'(per sonda: {[f"{q*100:.0f}%" for q in quote]})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
