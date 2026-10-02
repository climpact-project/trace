#!/usr/bin/env python3
"""ESTRAE OGNI OCCORRENZA DEL CASO CITATO, IN OGNI DOCUMENTO.

LA REGOLA: UNA RIGA PER OCCORRENZA. Non una per documento, non una per
frammento.

PERCHE' NON PER DOCUMENTO. Un atto puo' citare lo stesso precedente tre
volte a sostegno di tre proposizioni diverse — verificato sul ricorso di
Lliuya v. RWE: pagina 28 per le emissioni antropiche, pagina 33 per il
nesso causale, pagina 36 per la consapevolezza del pericolo prima del 1990.
Sono tre usi distinti e vanno contati tre volte.

PERCHE' NON PER FRAMMENTO. I frammenti si sovrappongono di 200 caratteri
per non perdere i passaggi a cavallo. Un'occorrenza vicina a un confine
compare quindi in DUE frammenti, e contarli produrrebbe una citazione in
piu'. Sullo stesso documento di Lliuya: 3 occorrenze, 4 frammenti.
Lo sbaglio non e' uniforme — gonfia di piu' i documenti con citazioni
ravvicinate, cioe' proprio quelli piu' interessanti.

Qui si lavora quindi sul TESTO INTEGRALE del documento e si contano le
posizioni: ogni corrispondenza e' una riga, con la sua pagina e il suo
contesto. I frammenti servono all'indice semantico, non a contare.

LE VARIANTI DA OCR NON SONO UN DETTAGLIO. Nel documento di Duarte
Agostinho il testo scrive "Lirgenda" — la U letta come L. Una ricerca della
sola parola esatta quel passaggio non lo trova, e la garanzia di
esaustivita' della rete lessicale varrebbe solo per il testo scritto bene.
Le varianti si dichiarano nel file del caso citato e finiscono in appendice
al metodo.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
MD = HERE / 'markdown'
PAGE_RE = re.compile(r'<!--\s*page\s+(\d+)\s*-->')

# Quanto contesto attorno all'occorrenza finisce nella colonna verbatim.
# Non e' la finestra di lettura: quella e' piu' ampia e la prende chi legge
# usando char_start.
PRIMA, DOPO = 200, 260


def leggi_front_matter(testo: str):
    meta = {}
    if not testo.startswith('---\n'):
        return meta, 0
    fine = testo.find('\n---\n', 4)
    if fine < 0:
        return meta, 0
    for riga in testo[4:fine].split('\n'):
        m = re.match(r'^([a-z_0-9]+):\s*(.*)$', riga)
        if m:
            v = m.group(2).strip()
            if v.startswith("'") and v.endswith("'") and len(v) >= 2:
                v = v[1:-1].replace("''", "'")
            meta[m.group(1)] = v
    return meta, fine + 5


def pagine(testo: str):
    return [(m.start(), int(m.group(1))) for m in PAGE_RE.finditer(testo)]


def pagina_di(marks, off):
    p = 1
    for pos, n in marks:
        if pos <= off:
            p = n
        else:
            break
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--caso', required=True,
                    help='file YAML del caso citato (cited case)')
    ap.add_argument('--uscita', default='index/candidati.csv')
    args = ap.parse_args()

    conf = {}
    for riga_grezza in Path(args.caso).read_text(encoding='utf-8').splitlines():
        # I COMMENTI VANNO TOLTI PRIMA DI LEGGERE IL VALORE.
        # Senza questo, una forma annotata ("Lirgenda  # U letta come L")
        # entrava nella ricerca con il commento attaccato: una stringa che
        # nel corpus non esiste, quindi una variante dichiarata e mai
        # cercata. Il guasto e' silenzioso — l'elenco delle forme sembra
        # giusto e la ricerca non trova nulla di piu'.
        riga = re.sub(r'\s+#.*$', '', riga_grezza).rstrip()
        m = re.match(r'^\s*-\s*(.+)$', riga)
        if m and conf.get('_in') == 'forme':
            conf.setdefault('forme', []).append(m.group(1).strip().strip('"\''))
        elif riga.strip().startswith('forme:'):
            conf['_in'] = 'forme'
        elif riga.strip() and not riga.startswith(' '):
            k = riga.split(':')[0].strip()
            conf['_in'] = None
            if ':' in riga:
                conf[k] = riga.split(':', 1)[1].strip().strip('"\'')

    forme = conf.get('forme') or []
    if not forme:
        print('Il file del caso citato non elenca nessuna forma da cercare.')
        return 1
    escludi = conf.get('escludi_case_id', '')
    patt = re.compile('|'.join(re.escape(f) for f in forme), re.I)
    print(f'caso citato : {conf.get("nome", "?")}')
    print(f'forme       : {len(forme)}  ({", ".join(forme[:6])}…)')

    righe = []
    n_doc = 0
    for md in sorted(MD.rglob('*.md')):
        testo = md.read_text(encoding='utf-8', errors='replace')
        meta, inizio = leggi_front_matter(testo)
        if escludi and escludi.lower() in (meta.get('case_id') or '').lower():
            continue
        corpo_off = inizio
        marks = pagine(testo)
        grezze = list(patt.finditer(testo, corpo_off))
        if not grezze:
            continue

        # FONDERE LE CORRISPONDENZE RAVVICINATE: UNA CITAZIONE, UNA RIGA.
        #
        # Un atto scrive spesso "il tribunale dell'Aja (ECLI:NL:RBDHA:2015:7196,
        # causa C/09/456689) nel caso Urgenda": e' UNA citazione, ma le forme
        # dichiarate la intercettano tre volte. Misurato sul corpus: 721
        # corrispondenze cadono a meno di 200 caratteri da un'altra.
        #
        # Contarle separatamente gonfierebbe il dato, e non in modo uniforme:
        # gonfia di piu' gli atti che citano per esteso — cioe' quelli che
        # danno peso al precedente, che sono i piu' interessanti. Sarebbe una
        # distorsione correlata proprio alla variabile in studio.
        #
        # La finestra e' 200 caratteri: la lunghezza tipica di un riferimento
        # completo con parentesi. Le forme fuse restano tutte registrate, cosi'
        # chi legge sa da che cosa e' stata riconosciuta.
        FUSIONE = 200
        trovate = []
        for m in grezze:
            if trovate and m.start() - trovate[-1][0].start() < FUSIONE:
                trovate[-1][1].append(m.group(0))
            else:
                trovate.append((m, [m.group(0)]))

        n_doc += 1
        for m, forme_qui in trovate:
            ctx = re.sub(r'\s+', ' ',
                         PAGE_RE.sub(' ', testo[max(corpo_off, m.start() - PRIMA):
                                                m.start() + DOPO])).strip()
            righe.append({
                'case_id': meta.get('case_id', ''),
                'case_name': meta.get('case_name', ''),
                'giurisdizioni': meta.get('giurisdizioni', ''),
                'document_id': meta.get('document_id', ''),
                'tipo_atto': meta.get('tipo_atto', ''),
                'tipo_atto_sabin': meta.get('tipo_atto_sabin', ''),
                'data': meta.get('data_deposito', ''),
                'pagina': pagina_di(marks, m.start()),
                'forma_trovata': ' + '.join(dict.fromkeys(forme_qui)),
                'citazione_testuale': ctx,
                # Da riempire leggendo: il codebook governa questi campi.
                'tipo_citazione': '', 'chi_parla': '', 'annidata': '',
                'proposizione_sostenuta': '', 'confidenza': '', 'note': '',
                'rete': 'lessicale',
                'file': str(md.relative_to(HERE)),
                'char_start': m.start(),
                'url_documento': meta.get('url_documento', ''),
                'codebook_versione': conf.get('codebook_versione', '0.1-bozza'),
            })

    out = HERE / args.uscita
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(righe[0].keys()))
        w.writeheader()
        w.writerows(righe)

    print(f'\noccorrenze : {len(righe):,}')
    print(f'documenti  : {n_doc}')
    print(f'casi       : {len({r["case_id"] for r in righe})}')
    print(f'uscita     : {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
