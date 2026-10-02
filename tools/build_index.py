#!/usr/bin/env python3
"""L'INDICE SEMANTICO.

COSA FA. Converte ogni frammento in un vettore con BGE-m3 e salva il
risultato in un file unico, insieme a un manifesto che dice con quale
modello e con quali parametri e' stato costruito.

CHE COSA NON FA. Non addestra e non adatta nulla: il modello viene
impiegato cosi' com'e', a versione fissata. Il corpus resta dato e non
diventa in nessun momento peso di un modello.

PERCHE' multilingual-e5-large, E PERCHE' NON BGE-m3. Qui c'era scritto
"perche' BGE-m3", ed era rimasto da una versione precedente: venti righe
piu' sotto il codice carica `intfloat/multilingual-e5-large`. Due
risposte incompatibili nello stesso file, e questo file accompagnera' il
repository quando esce con l'articolo.

La scelta non e' per reputazione, e' MISURATA: 200 passaggi pertinenti
nascosti fra 6.000, cinque domande formulate sul contenuto e nessuna
contenente il nome del caso, quattro modelli a parita' di condizioni
(vedi `index/confronto_modelli.json` e METODO-RECUPERO 5.1). Richiamo@100:
e5-large 44,6 — BGE-m3 44,0 — e5-base 40,6 — paraphrase-multilingual 32,8.
BGE-m3 era il candidato per fama ed e' arrivato secondo: senza la prova
sarebbe stato adottato lo stesso.

I tre requisiti restano quelli: multilingue (il Climate Case Chart
raccoglie atti in decine di lingue), pesi aperti — quindi la versione si
dichiara e chiunque rifa' il calcolo ottiene lo stesso risultato — e
memoria compatibile con i portatili su cui l'indice gira davvero.
IL LIMITE, dichiarato: la finestra e' di 512 token, la piu' corta della
sua fascia. Tronca la coda di una minoranza di frammenti e preclude la
frammentazione tardiva, che ne richiede 8.192.

PERCHE' float16 E NON float32. Un milione e duecentomila vettori da 1024
dimensioni occupano 4,9 GB in precisione piena e 2,5 in mezza. La
differenza di precisione sul coseno e' nell'ordine del millesimo — cioe'
invisibile su una graduatoria — mentre la differenza di dimensione decide
se l'indice sta comodo su un portatile o no. E deve starci: le quattro
persone ne tengono una copia ciascuna.

PERCHE' NESSUNA LIBRERIA DI RICERCA APPROSSIMATA. Con 1,2 milioni di
vettori il confronto esaustivo in memoria richiede un paio di secondi per
interrogazione su questa macchina. Una struttura approssimata (FAISS e
simili) lo porterebbe a millesimi, ma introdurrebbe un parametro in piu' da
dichiarare, una dipendenza in piu' da installare su quattro macchine, e —
soprattutto — un recupero che PUO' non trovare il vicino migliore. Due
secondi sono un prezzo accettabile per una ricerca che non sbaglia mai per
costruzione.

IL MANIFESTO non e' burocrazia. Se quattro persone interrogano indici
diversi, due risultati discordanti diventano indistinguibili da due indici
diversi — e non lo si scopre guardando i risultati, che sembrano comunque
plausibili. Il manifesto permette di verificarlo in un comando.
"""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
CHUNKS = HERE / 'index' / 'chunks.jsonl'
OUT_DIR = HERE / 'index'
MODELLO = 'intfloat/multilingual-e5-large'
DIM = 1024

# I DUE PREFISSI DI e5 — LA COSA PIU' FACILE DA SBAGLIARE DI TUTTO IL
# SISTEMA, E LA PIU' SILENZIOSA.
#
# Questo modello e' addestrato in modo ASIMMETRICO: i passaggi vanno
# marcati 'passage: ', le domande 'query: '. Non sono decorazioni, sono
# come il modello e' fatto: senza, domande e passaggi finiscono in due
# regioni diverse dello spazio e la somiglianza calcolata non significa
# piu' nulla.
#
# E' gia' successo: nel primo confronto avevo messo solo il prefisso delle
# domande, il modello e' sembrato scadente ed era la prova a essere
# sbagliata.
#
# IL PERICOLO VERO E' L'ASIMMETRIA FRA COSTRUZIONE E INTERROGAZIONE. Se
# l'indice si costruisce con 'passage: ' e le domande si pongono senza
# 'query: ', non si rompe niente: si ottengono risultati plausibili e
# sbagliati, per sempre. Per questo i due prefissi sono scritti QUI, uno
# accanto all'altro, e il manifesto li registra: chi interroga deve poter
# verificare quale sia stato usato.
PREFISSO_PASSAGGIO = 'passage: '
PREFISSO_DOMANDA = 'query: '

# I nostri frammenti hanno una mediana di 352 token e un massimo di 718.
# Fissarla evita che il modello riempia inutilmente la sua finestra
# massima — che su BGE-m3 aveva esaurito la memoria della GPU del Mac.
# 512, NON 768. `multilingual-e5-large` e' costruito su XLM-RoBERTa, che ha
# 512 posizioni: chiedergliene di piu' fa fallire la ricerca nella tabella
# delle posizioni e la GPU si ferma con un errore di asserzione, non con un
# messaggio comprensibile.
# Il 768 veniva da BGE-m3, che arriva a 8192: un numero portato dietro
# cambiando modello. I nostri frammenti hanno mediana 352 token e massimo
# 718, quindi una minoranza viene troncata in coda — accettabile, e va
# dichiarato nel metodo.
MAX_TOKEN = 512


def carica_frammenti(limite=0):
    righe = []
    with CHUNKS.open(encoding='utf-8') as f:
        for i, riga in enumerate(f):
            if limite and i >= limite:
                break
            righe.append(json.loads(riga))
    return righe


def impronta_modello(modello) -> str:
    """Impronta dei pesi, per il manifesto.

    Non basta il nome del modello: un deposito puo' essere aggiornato senza
    cambiare nome, e due indici costruiti con lo 'stesso' modello a mesi di
    distanza potrebbero non essere confrontabili. L'impronta lo rende
    verificabile."""
    h = hashlib.sha256()
    for p in sorted(modello.parameters(), key=lambda x: x.shape):
        h.update(p.detach().to('cpu').numpy().tobytes()[:4096])
    return h.hexdigest()[:32]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prova', type=int, default=0,
                    help='indicizza solo N frammenti e riporta la velocita')
    ap.add_argument('--batch', type=int, default=32)
    args = ap.parse_args()

    from sentence_transformers import SentenceTransformer

    frammenti = carica_frammenti(args.prova)
    print(f'frammenti: {len(frammenti):,}')

    print(f'carico {MODELLO} …')
    t0 = time.time()
    import torch
    dispositivo = ('cuda' if torch.cuda.is_available()
                   else 'mps' if torch.backends.mps.is_available() else 'cpu')
    # MEZZA PRECISIONE SULLA GPU. Raddoppia la velocita' e dimezza la
    # memoria occupata; sulla somiglianza fra vettori la differenza e'
    # nell'ordine del millesimo, cioe' invisibile su una graduatoria.
    # Su CPU non si usa: li' la mezza precisione e' piu' lenta, non piu'
    # veloce.
    kw = {'torch_dtype': torch.float16} if dispositivo == 'cuda' else {}
    modello = SentenceTransformer(MODELLO, device=dispositivo, model_kwargs=kw)
    modello.max_seq_length = min(getattr(modello, 'max_seq_length', MAX_TOKEN) or MAX_TOKEN, MAX_TOKEN)
    print(f'  caricato in {time.time() - t0:.0f}s su {dispositivo}')

    testi = [PREFISSO_PASSAGGIO + f['testo'] for f in frammenti]

    # SALVATAGGI INTERMEDI, e non e' una precauzione eccessiva.
    # Il lavoro dura ore: verra' interrotto. Un aggiornamento di sistema, il
    # coperchio chiuso, una disattenzione. Senza scritture parziali
    # ricomincerebbe da capo, e ricominciare da capo un lavoro di ventisette
    # ore significa non finirlo mai.
    # I vettori si scrivono in un file mappato in memoria, un blocco per
    # volta; accanto, un segnalibro dice a che punto si era. Rilanciando, si
    # riparte da li'.
    t0 = time.time()
    if args.prova:
        vettori = modello.encode(
            testi, batch_size=args.batch, show_progress_bar=True,
            normalize_embeddings=True, convert_to_numpy=True,
        ).astype(np.float16)
    else:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        percorso = OUT_DIR / 'vettori.npy'
        segnalibro = OUT_DIR / 'segnalibro.json'
        fatti = 0
        if percorso.exists() and segnalibro.exists():
            fatti = json.loads(segnalibro.read_text(encoding='utf-8')).get('fatti', 0)
            if fatti:
                print(f'riprendo dal frammento {fatti:,}')
        vettori = np.lib.format.open_memmap(
            percorso, mode='r+' if fatti else 'w+',
            dtype=np.float16, shape=(len(testi), DIM))
        BLOCCO = 2048
        for i in range(fatti, len(testi), BLOCCO):
            fine = min(i + BLOCCO, len(testi))
            vettori[i:fine] = modello.encode(
                testi[i:fine], batch_size=args.batch, show_progress_bar=False,
                normalize_embeddings=True, convert_to_numpy=True,
            ).astype(np.float16)
            vettori.flush()
            segnalibro.write_text(json.dumps({'fatti': fine}), encoding='utf-8')
            trascorso = time.time() - t0
            fatti_ora = fine - fatti
            resta = (len(testi) - fine) / max(fatti_ora / trascorso, 1e-9) / 3600
            print(f'  {fine:,}/{len(testi):,}  ({100*fine/len(testi):.1f}%)  '
                  f'mancano ~{resta:.1f} ore', flush=True)
    dt = time.time() - t0

    vel = len(testi) / max(dt, 1e-9)
    print(f'\n{len(testi):,} frammenti in {dt:.0f}s  ->  {vel:.1f} al secondo')

    if args.prova:
        totale = sum(1 for _ in CHUNKS.open(encoding='utf-8'))
        ore = totale / vel / 3600
        print(f'\nSTIMA sul corpus intero ({totale:,} frammenti): {ore:.1f} ore')
        print('(prova: nessun file scritto)')
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / 'ids.json').write_text(
        json.dumps([f['id'] for f in frammenti]), encoding='utf-8')

    manifesto = {
        'costruito': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'modello': MODELLO,
        'impronta_pesi': impronta_modello(modello),
        # Registrati perche' chi interroga DEVE usare gli stessi: un indice
        # costruito con un prefisso e interrogato senza produce risultati
        # plausibili e sbagliati, senza alcun segnale.
        'prefisso_passaggio': PREFISSO_PASSAGGIO,
        'prefisso_domanda': PREFISSO_DOMANDA,
        'max_token': MAX_TOKEN,
        'dimensioni': int(vettori.shape[1]),
        'frammenti': int(vettori.shape[0]),
        'precisione': 'float16',
        'normalizzati': True,
        'similitudine': 'coseno (prodotto scalare su vettori normalizzati)',
        'ricerca': 'esaustiva, nessuna approssimazione',
        'parametri_frammentazione': {'target': 1100, 'minimo': 250, 'sovrapposizione': 200},
        'impronta_frammenti': hashlib.sha256(
            CHUNKS.read_bytes()).hexdigest()[:32],
    }
    (OUT_DIR / 'manifesto.json').write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"\nindice   : {OUT_DIR / 'vettori.npy'}  "
          f'({vettori.nbytes / 1e9:.2f} GB)')
    print(f"manifesto: {OUT_DIR / 'manifesto.json'}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
