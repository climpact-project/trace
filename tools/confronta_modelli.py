#!/usr/bin/env python3
"""QUALE MODELLO DI EMBEDDING, MISURATO E NON SCELTO PER FAMA.

LA DOMANDA. "Il modello migliore" in generale non esiste: esiste quello che
recupera meglio SU QUESTO CORPUS. Questa prova lo trasforma da opinione a
numero, e il numero finisce nel metodo.

COME E' COSTRUITA LA PROVA.

  Positivi  — frammenti che nominano Urgenda e ne discutono il contenuto.
              Sono i passaggi che una ricerca semantica DEVE ritrovare.
  Pagliaio  — frammenti sorteggiati da documenti che non la nominano mai.
              Servono a rendere il compito realistico: trovare venti
              passaggi fra venti e' facile, fra cinquemila no.
  Domande   — formulazioni SOSTANZIALI del contenuto di Urgenda, che NON
              contengono mai la parola. E' il punto: se la domanda
              contenesse il nome, misureremmo la ricerca testuale, che gia'
              sappiamo fare in un secondo e senza modelli.

LA MISURA. Per ogni domanda si guarda quanti positivi compaiono entro le
prime k posizioni (recall@k). Si riporta anche il tempo di indicizzazione e
la dimensione dell'indice risultante, perche' la scelta non e' solo di
qualita': un indice piu' preciso ma da dieci gigabyte va copiato su quattro
portatili e riletto a ogni interrogazione.

IL LIMITE DI QUESTA PROVA, dichiarato. I positivi sono individuati per via
lessicale, quindi sono passaggi che nominano Urgenda. I passaggi che ne
riprendono il ragionamento SENZA nominarla — il caso piu' interessante —
non sono in questo insieme, perche' non c'e' modo di individuarli
automaticamente. La prova misura dunque il recupero semantico su passaggi
che parlano del tema, non il recupero del richiamo implicito puro. E' un
buon indicatore, non una misura completa: quella richiede il campione
codificato a mano.
"""

import argparse
import json
import random
import re
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
CHUNKS = HERE / 'index' / 'chunks.jsonl'

# Le domande: il contenuto sostanziale di Urgenda, senza il nome.
DOMANDE = [
    "lo Stato ha un dovere di diligenza verso i propri cittadini di ridurre "
    "le emissioni di gas serra per proteggerli dal cambiamento climatico",

    "the State has a positive obligation under Articles 2 and 8 of the European "
    "Convention on Human Rights to take measures against dangerous climate change",

    "the government must reduce greenhouse gas emissions by at least 25% by the "
    "end of 2020 compared to 1990 levels",

    "a court may order the government to adopt a more ambitious emission "
    "reduction target without violating the separation of powers",

    "each State is responsible for its own share of global emissions and cannot "
    "escape responsibility by arguing that its contribution is small",
]

# I CANDIDATI. Tutti a pesi aperti, tutti multilingui: il corpus contiene
# atti in decine di lingue e un modello monolingue perderebbe i documenti
# non inglesi in silenzio.
# La dimensione del vettore non e' un dettaglio estetico: decide quanto
# pesa l'indice, che quattro persone devono tenere in copia locale.
MODELLI = [
    ('BAAI/bge-m3', 1024),
    ('intfloat/multilingual-e5-large', 1024),
    ('intfloat/multilingual-e5-base', 768),
    ('sentence-transformers/paraphrase-multilingual-mpnet-base-v2', 768),
]


# I positivi devono DISCUTERE il contenuto, non limitarsi a nominarlo.
# Prima bastava la parola "Urgenda": fra i 150 finivano cosi' anche le
# menzioni in catena — il nome dentro un elenco di precedenti, senza una
# riga di merito. Una domanda sul contenuto non deve portarle in alto, e
# infatti non le portava: il recupero sembrava scarso ed era il metro a
# essere sbagliato.
# Ora serve la parola PIU' almeno un segno di merito.
MERITO = re.compile(
    r'\b(25\s*%|25 per\s*cent|article\s*[28]\b|articles?\s*2\s*and\s*8'
    r'|duty of care|zorgplicht|dovere di diligenza|echr|european convention'
    r'|greenhouse gas|emission reduction|separation of powers|hazardous climate)',
    re.I)


def prepara(n_pagliaio: int, seme: int = 20260730):
    """Positivi e pagliaio, sorteggiati in modo riproducibile."""
    urgenda_re = re.compile(r'urgenda', re.I)
    positivi, altri = [], []
    with CHUNKS.open(encoding='utf-8') as f:
        for riga in f:
            d = json.loads(riga)
            if urgenda_re.search(d['testo']) and MERITO.search(d['testo']):
                positivi.append(d)
            elif not urgenda_re.search(d['testo']):
                altri.append(d)
    random.seed(seme)
    pagliaio = random.sample(altri, min(n_pagliaio, len(altri)))
    return positivi, pagliaio


def valuta(nome, testi, n_pos, domande, batch):
    """Indicizza, interroga e misura. Torna qualita', tempo e ingombro."""
    from sentence_transformers import SentenceTransformer
    t0 = time.time()
    m = SentenceTransformer(nome, device='mps')
    # LA LUNGHEZZA MASSIMA VA FISSATA, SEMPRE.
    # BGE-m3 accetta di serie passaggi fino a 8.192 token: con un lotto da
    # 64 ha provato ad allocare 14 GB e la GPU del Mac si e' esaurita, e il
    # modello e' rimasto non valutato. I nostri frammenti hanno una mediana
    # di 352 token e un massimo di 718, quindi 768 basta e avanza: si paga
    # solo il lavoro che serve.
    m.max_seq_length = min(getattr(m, 'max_seq_length', 512) or 512, 768)
    caricato = time.time() - t0

    # I PREFISSI DI e5: DUE, NON UNO — E QUI STAVA L'ERRORE.
    #
    # `multilingual-e5` e' addestrato in modo ASIMMETRICO: le domande vanno
    # marcate `query: `, i passaggi `passage: `. Nella prova precedente
    # avevo messo solo il primo. Senza il secondo, domande e passaggi
    # finiscono in due regioni diverse dello spazio e la somiglianza
    # calcolata non significa piu' niente: il modello sembra scadente ed e'
    # la prova a essere sbagliata.
    # Non e' un accorgimento facoltativo, e' come quel modello e' fatto.
    pre_p = 'passage: ' if 'e5' in nome else ''
    pre_q = 'query: ' if 'e5' in nome else ''

    t0 = time.time()
    V = m.encode([pre_p + t for t in testi], batch_size=batch,
                 normalize_embeddings=True, convert_to_numpy=True,
                 show_progress_bar=False).astype(np.float16)
    indicizzato = time.time() - t0

    dom = [pre_q + d for d in domande]
    Q = m.encode(dom, normalize_embeddings=True, convert_to_numpy=True,
                 show_progress_bar=False).astype(np.float32)

    punteggi = Q @ V.astype(np.float32).T          # coseno
    esiti = {}
    for k in (10, 50, 100):
        trovati = []
        for i in range(len(domande)):
            primi = np.argsort(-punteggi[i])[:k]
            trovati.append(int((primi < n_pos).sum()))
        esiti[f'recall@{k}'] = trovati
    return {
        'modello': nome,
        'dimensioni': int(V.shape[1]),
        'caricamento_s': round(caricato, 1),
        'indicizzazione_s': round(indicizzato, 1),
        'frammenti_al_secondo': round(len(testi) / max(indicizzato, 1e-9), 1),
        'esiti': esiti,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pagliaio', type=int, default=4000)
    ap.add_argument('--positivi', type=int, default=150)
    ap.add_argument('--batch', type=int, default=64)
    args = ap.parse_args()

    positivi, pagliaio = prepara(args.pagliaio)
    random.seed(20260730)
    positivi = random.sample(positivi, min(args.positivi, len(positivi)))
    testi = [d['testo'] for d in positivi] + [d['testo'] for d in pagliaio]
    n_pos = len(positivi)
    print(f'positivi : {n_pos}')
    print(f'pagliaio : {len(pagliaio):,}')
    print(f'domande  : {len(DOMANDE)} (nessuna contiene la parola "Urgenda")\n', flush=True)

    esiti = []
    for nome, _ in MODELLI:
        print(f'— {nome}', flush=True)
        try:
            r = valuta(nome, testi, n_pos, DOMANDE, args.batch)
        except Exception as e:
            print(f'  non valutabile: {str(e)[:90]}\n')
            continue
        esiti.append(r)
        tot = 1_206_795
        gb = tot * r['dimensioni'] * 2 / 1e9
        ore = tot / r['frammenti_al_secondo'] / 3600
        print(f"  {r['dimensioni']} dim, {r['frammenti_al_secondo']}/s")
        for k, v in r['esiti'].items():
            print(f"  {k:11s}: {v}  (su {n_pos} positivi, per ciascuna domanda)")
        print(f'  indice sul corpus intero: {gb:.1f} GB, {ore:.1f} ore su questo Mac\n')

    (HERE / 'index' / 'confronto_modelli.json').write_text(
        json.dumps({'positivi': n_pos, 'pagliaio': len(pagliaio),
                    'domande': DOMANDE, 'esiti': esiti},
                   ensure_ascii=False, indent=2), encoding='utf-8')
    print('scritto: index/confronto_modelli.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
