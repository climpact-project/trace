#!/usr/bin/env python3
"""IL CONTROLLO DEGLI SCARTI — sempre, da solo, visibile solo nel cruscotto.

DECISIONE DEL PI (23 settembre 2026). I validatori controllano tutto cio' che
la macchina propone, piu' una parte a caso di cio' che scarta: e' l'unico modo
di sapere quante citazioni vere la macchina perde. Gli scarti venivano
pubblicati in `corpus_discarded` fin da luglio, ma il portale non li mostrava
a nessuno: il pezzo che doveva pescarne una quota non era mai stato scritto.
Il PI non vuole un pulsante: deve succedere sempre, in automatico, e il
risultato si deve vedere solo nel cruscotto.

COME FUNZIONA
  - A ogni pubblicazione (lo chiama `020_pubblica.py`, ma si puo' lanciare anche da
    solo per un caso gia' pubblicato) si pesca il 10% degli scarti di ogni
    motivo, almeno uno per motivo. Fuori le COPIE: sono lo stesso testo di una
    riga gia' in coda, controllarle non misura niente.
  - Il sorteggio ha per seme l'identificativo della riga: ripubblicare pesca
    le stesse righe, e quelle gia' entrate non si toccano.
  - Le righe pescate entrano in `corpus_rows` COME RIGHE QUALSIASI: niente
    segni visibili nella coda, cosi' chi valida non sa che la macchina le aveva
    buttate e giudica alla cieca. Il segno sta in campi che la coda non mostra:
    `controllo_scarti: true`, `motivo_macchina` (perche' era stata scartata).
    `corroborazione` diventa `controllo_scarti` (l'originale resta in
    `corroborazione_originale`), cosi' la precisione per fascia del cruscotto
    resta quella di cio' che la macchina ha proposto.
  - Sono sempre da guardare (`integrale`, `nel_campione`), e vanno a una
    persona a caso fra quelle che lavorano gia' sul caso, cosi' arrivano nelle
    code senza che nessuno debba ridividere il lavoro.
  - Il cruscotto le conta a parte, le toglie dai conti della macchina e mostra
    quante citazioni vere c'erano fra gli scarti controllati.

Uso:  python3 tools/038_controllo_scarti.py --caso urgenda [--quota 0.10] [--prova]
"""
import argparse, collections, math, random, sys

PROGETTO = 'climpact-drp'
ESCLUSI = {'copia'}


def aggiungi_controllo(db, caso, quota=0.10, prova=False):
    from google.cloud import firestore
    scarti = [(d.id, d.to_dict()) for d in db.collection('corpus_discarded')
              .where(filter=firestore.FieldFilter('caso_citato', '==', caso)).stream()]
    per_motivo = collections.defaultdict(list)
    for rid, d in scarti:
        # Il motivo porta con se' il numero («riordino 0.0012 < 0.05»,
        # «anteriore al 2015-06-24»): si raggruppa per la prima parola.
        m = (d.get('motivo_scarto') or 'ignoto').split()[0]
        if m not in ESCLUSI:
            per_motivo[m].append((rid, d))
    righe = {d.id: d.to_dict() for d in db.collection('corpus_rows')
             .where(filter=firestore.FieldFilter('caso_citato', '==', caso)).stream()}
    squadra = sorted({r.get('assegnato_a') for r in righe.values() if r.get('assegnato_a')})
    scelte = []
    for m, gruppo in sorted(per_motivo.items()):
        n = max(1, math.ceil(len(gruppo) * quota))
        ordinati = sorted(gruppo, key=lambda x: random.Random(x[0]).random())
        scelte += [(rid, d, m) for rid, d in ordinati[:n]]
    nuove = [(rid, d, m) for rid, d, m in scelte if rid not in righe]
    print(f'{caso}: scarti {len(scarti):,}; per motivo ' +
          ', '.join(f'{m} {len(g)}' for m, g in sorted(per_motivo.items())) +
          f'; pescati {len(scelte)}, gia\' in coda {len(scelte) - len(nuove)}, da aggiungere {len(nuove)}; '
          f'squadra {len(squadra)} persone')
    if prova or not nuove:
        return len(nuove)
    for i in range(0, len(nuove), 450):
        lotto = db.batch()
        for rid, d, m in nuove[i:i + 450]:
            riga = dict(d)
            riga.update({
                'scartato': False, 'motivo_scarto': None,
                'controllo_scarti': True, 'motivo_macchina': d.get('motivo_scarto') or m,
                'corroborazione_originale': d.get('corroborazione'),
                'corroborazione': 'controllo_scarti',
                'integrale': True, 'nel_campione': True,
                'esito': None, 'validato_da': None, 'validato_il': None, 'doppia_codifica': False,
                'assegnato_a': (random.Random(rid + '|squadra').choice(squadra) if squadra else None),
                'creato_il': firestore.SERVER_TIMESTAMP,
            })
            lotto.set(db.collection('corpus_rows').document(rid), riga)
        lotto.commit()
    print(f'  aggiunte {len(nuove)} righe di controllo alla coda di {caso}')
    return len(nuove)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--caso', required=True)
    ap.add_argument('--quota', type=float, default=0.10)
    ap.add_argument('--prova', action='store_true', help='non scrive niente: dice solo cosa farebbe')
    a = ap.parse_args()
    from google.cloud import firestore
    aggiungi_controllo(firestore.Client(project=PROGETTO), a.caso, a.quota, a.prova)


if __name__ == '__main__':
    sys.exit(main())
