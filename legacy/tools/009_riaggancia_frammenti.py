#!/usr/bin/env python3
"""RIMETTE I FRAMMENTI DELL'INDICE AL LORO POSTO NEL MARKDOWN.

IL PROBLEMA. Le posizioni registrate nei frammenti non puntano al testo
giusto nel file: su un campione di 1.200, nessuna combaciava.

LA DIAGNOSI, in tre passi. Il primo campione dava uno scostamento di -200
quasi ovunque, cioe' esattamente la sovrapposizione fra frammenti: sembrava
un errore di calcolo dell'inizio. Ma un quinto dei frammenti non si trovava
affatto, nemmeno cercandolo da capo. Leggendo il punto in cui il testo del
frammento e quello del file divergono, si vede la ragione vera:

    frammento : ...visa. \n \n8GTKH[ XGTUKQP\n\n\n \n\n5KIPGF ...
    file      : ...visa.  \n \n8GTKH[ XGTUKQP\n\n\n<!-- page 2 -->\n\n5KIPGF ...

Il frammentatore ha lavorato su una versione NORMALIZZATA del documento —
marcatori di pagina rimossi, sequenze di spazi collassate — e ha registrato
gli offset su quella. Non e' un dato corrotto: e' una corrispondenza fra due
versioni dello stesso testo, che non era stata conservata.

PERCHE' NON SI RICOSTRUISCE L'INDICE. I vettori codificano il TESTO dei
frammenti, e quel testo e' testo vero del corpus: la ricerca semantica
funziona. E' sbagliata solo la posizione registrata, cioe' pagina e finestra
di lettura — che e' pero' esattamente cio' che serve per riaprire il
documento e verificare. Ricostruire costerebbe un'altra ora di GPU per
riottenere gli stessi vettori.

COME. Per ogni documento si ricostruisce la stessa normalizzazione,
tenendo pero' la MAPPA fra ogni carattere normalizzato e la sua posizione
nel file vero. Il frammento si cerca nel testo normalizzato — dove combacia
esattamente — e la posizione trovata si riporta indietro attraverso la
mappa. Esatto, non approssimato, e indipendente da quanto vale la
sovrapposizione.

GLI IDENTIFICATIVI NON SI TOCCANO. `ids.json` associa ogni riga della
matrice dei vettori a un identificativo di frammento: cambiarli
scollegherebbe l'indice. Qui cambiano solo `char_start`, `char_end` e
`pagina`.

CHI NON SI RITROVA viene marcato e contato, non buttato: un frammento il cui
testo non esiste piu' nel markdown segnala che quel documento e' cambiato
dopo la costruzione dell'indice, ed e' un'informazione da avere.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
PAGE_RE = re.compile(r'<!-- page (\d+) -->')
SORGENTE = HERE / 'index' / 'chunks.pod.jsonl'
USCITA = HERE / 'index' / 'chunks.jsonl'


def normalizza(t: str):
    """(testo senza marcatori e con gli spazi collassati, mappa all'originale).

    `mappa[i]` e' la posizione, nel file vero, del carattere `i` del testo
    normalizzato. E' cio' che permette di cercare in un testo e rispondere
    nell'altro."""
    fuori, mappa = [], []
    i, n = 0, len(t)
    while i < n:
        m = PAGE_RE.match(t, i)
        if m:
            i = m.end()
            continue
        c = t[i]
        if c.isspace():
            j = i
            while j < n:
                mm = PAGE_RE.match(t, j)
                if mm:
                    j = mm.end()
                elif t[j].isspace():
                    j += 1
                else:
                    break
            fuori.append(' ')
            mappa.append(i)
            i = j
        else:
            fuori.append(c)
            mappa.append(i)
            i += 1
    return ''.join(fuori), mappa


def pagina_di(marks, off):
    p = 1
    for pos, n in marks:
        if pos <= off:
            p = n
        else:
            break
    return p


def main():
    if not SORGENTE.exists():
        print(f'Manca {SORGENTE}'), sys.exit(1)
    ids_file = HERE / 'index' / 'ids.json'
    attesi = set(json.loads(ids_file.read_text(encoding='utf-8'))) if ids_file.exists() else None

    tmp = USCITA.with_suffix('.jsonl.tmp')
    corrente, testo, marks = None, '', []
    cursore = 0
    n = riagganciati = spostati = non_trovati = fuori_indice = 0
    scostamenti = {}

    with SORGENTE.open(encoding='utf-8') as f, tmp.open('w', encoding='utf-8') as out:
        for riga in f:
            d = json.loads(riga)
            n += 1
            if attesi is not None and d['id'] not in attesi:
                # Frammento presente nel file ma non nell'indice: si
                # riscrive com'e', non serve a nulla riagganciarlo.
                fuori_indice += 1
                out.write(riga)
                continue

            if d['file'] != corrente:
                corrente = d['file']
                p = HERE / corrente
                testo = p.read_text(encoding='utf-8', errors='replace') if p.exists() else ''
                marks = [(m.start(), int(m.group(1))) for m in PAGE_RE.finditer(testo)]
                pulito, mappa = normalizza(testo)
                cursore = 0

            ago = re.sub(r'\s+', ' ', d['testo'])
            # SI CERCA A PARTIRE DAL PUNTO GIA' RAGGIUNTO. I frammenti di un
            # file arrivano in ordine, quindi la ricerca non riparte da capo
            # ogni volta — e non puo' agganciarsi a una ripetizione che sta
            # prima di dove eravamo.
            da = max(0, min(cursore, len(pulito)) - 400)
            k = pulito.find(ago, da)
            if k < 0:
                k = pulito.find(ago[:180], da)
            if k < 0:
                k = pulito.find(ago[:180])
            pos = mappa[k] if k >= 0 else -1
            if pos < 0:
                non_trovati += 1
                d['riagganciato'] = False
                out.write(json.dumps(d, ensure_ascii=False) + '\n')
                continue

            delta = pos - d['char_start']
            if delta:
                spostati += 1
                scostamenti[delta] = scostamenti.get(delta, 0) + 1
            fine_norm = min(k + len(ago), len(mappa) - 1)
            d['char_start'] = pos
            d['char_end'] = mappa[fine_norm] + 1
            d['pagina'] = pagina_di(marks, pos)
            fine = pagina_di(marks, d['char_end'])
            if fine != d['pagina']:
                d['pagina_fine'] = fine
            elif 'pagina_fine' in d:
                d['pagina_fine'] = fine
            d['riagganciato'] = True
            cursore = k + max(1, len(ago) // 2)
            riagganciati += 1
            out.write(json.dumps(d, ensure_ascii=False) + '\n')

            if n % 200000 == 0:
                print(f'  {n:,}…', flush=True)

    tmp.replace(USCITA)
    print(f'\nframmenti letti     : {n:,}')
    print(f'  riagganciati      : {riagganciati:,}')
    print(f'  di cui spostati   : {spostati:,}')
    print(f'  non ritrovati     : {non_trovati:,}')
    print(f'  fuori indice      : {fuori_indice:,}')
    print('\nscostamenti piu frequenti:')
    for k, v in sorted(scostamenti.items(), key=lambda x: -x[1])[:8]:
        print(f'  {k:+6d} : {v:,}')

    # IL MANIFESTO VA RIALLINEATO, altrimenti l'installatore avverte a ogni
    # avvio che i frammenti non sono quelli con cui l'indice e' stato
    # costruito — ed e' un allarme che, ripetuto senza motivo, si smette di
    # leggere proprio quando conta.
    man_file = HERE / 'index' / 'manifesto.json'
    if man_file.exists():
        man = json.loads(man_file.read_text(encoding='utf-8'))
        man['impronta_frammenti'] = hashlib.sha256(
            USCITA.read_bytes()).hexdigest()[:32]
        man['posizioni_riagganciate'] = {
            'quando': '2026-07-31',
            'perche': 'char_start dell indice indicava l inizio della parte '
                      'nuova del frammento invece che del frammento intero',
            'riagganciati': riagganciati,
            'non_ritrovati': non_trovati,
        }
        man_file.write_text(json.dumps(man, indent=2, ensure_ascii=False),
                            encoding='utf-8')
        print(f"\nmanifesto aggiornato: impronta {man['impronta_frammenti']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
