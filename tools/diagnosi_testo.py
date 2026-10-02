#!/usr/bin/env python3
"""CENSIMENTO DELLA QUALITA' DEL TESTO ESTRATTO.

PERCHE' SERVE. Un documento il cui testo e' illeggibile non produce un
errore: produce un documento senza citazioni. E' la perdita piu' insidiosa
di tutta la catena, perche' si presenta come un risultato normale.

COME SI RICONOSCE UN TESTO ROTTO SENZA SAPERE CHE LINGUA E'.
Il primo tentativo cercava parole funzione inglesi e italiane e segnalava
il 7,7% del corpus. Era sbagliato: segnalava come illeggibile ogni
documento in nepalese, cinese, giapponese o portoghese. Il difetto stava
nella misura, non nei dati — ed e' il tipo di errore che, se non
controllato, avrebbe portato a rifare l'OCR di 1.288 documenti sani.

La misura buona non dipende dalla lingua: in alfabeto latino le vocali
sono circa il 35-45% delle lettere, in qualunque lingua europea. Un testo
con codifica di font non standard perde quella proporzione, perche' ogni
carattere e' mappato su un simbolo diverso. Sugli alfabeti non latini la
misura non e' applicabile e il giudizio si sospende: dichiararli sospetti
sarebbe ripetere l'errore di prima.

QUATTRO ESITI, non due:
  sano            testo latino con proporzione di vocali normale
  corrotto        testo latino con vocali crollate -> codifica rotta
  altro alfabeto  non giudicabile con questa misura
  corto           meno di 2.000 caratteri: puo' essere un documento breve
                  legittimo o una scansione mal riuscita, e la distinzione
                  richiede di guardarli
"""

import collections
import json
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
CHUNKS = HERE / 'index' / 'chunks.jsonl'
OUT = HERE / 'index' / 'diagnosi_testo.json'

VOCALI = set('aeiouAEIOUàèéìòùáíóúäöüâêîôûãõåø')
SOGLIA_VOCALI = 0.25     # sotto: codifica sospetta
SOGLIA_CORTO = 2000      # caratteri
QUOTA_LATINO = 0.30      # sotto: alfabeto non latino


def main():
    per_doc = collections.defaultdict(lambda: {'lat': 0, 'voc': 0, 'tot': 0, 'file': ''})
    with CHUNKS.open(encoding='utf-8') as f:
        for riga in f:
            d = json.loads(riga)
            v = per_doc[d['document_id']]
            v['file'] = d['file']
            for ch in d['testo']:
                v['tot'] += 1
                if ch.isalpha() and 'LATIN' in unicodedata.name(ch, ''):
                    v['lat'] += 1
                    if ch in VOCALI:
                        v['voc'] += 1

    esiti = collections.Counter()
    liste = collections.defaultdict(list)
    for doc, v in per_doc.items():
        if v['tot'] < SOGLIA_CORTO:
            esito = 'corto'
        elif v['lat'] < v['tot'] * QUOTA_LATINO:
            esito = 'altro alfabeto'
        elif v['voc'] / max(1, v['lat']) < SOGLIA_VOCALI:
            esito = 'corrotto'
        else:
            esito = 'sano'
        esiti[esito] += 1
        if esito != 'sano':
            liste[esito].append({
                'document_id': doc,
                'file': v['file'],
                'caratteri': v['tot'],
                'vocali_su_lettere': round(v['voc'] / max(1, v['lat']), 3),
            })

    tot = sum(esiti.values())
    print(f'documenti esaminati : {tot}')
    for k in ('sano', 'corrotto', 'corto', 'altro alfabeto'):
        n = esiti[k]
        print(f'  {k:16s}: {n:6d}  ({100 * n / tot:.1f}%)')

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        'totale': tot,
        'esiti': dict(esiti),
        'soglie': {
            'vocali_su_lettere': SOGLIA_VOCALI,
            'caratteri_minimi': SOGLIA_CORTO,
            'quota_latino': QUOTA_LATINO,
        },
        'liste': {k: sorted(v, key=lambda x: x['caratteri']) for k, v in liste.items()},
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\nelenchi scritti in : {OUT}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
