#!/usr/bin/env python3
"""DAI DOCUMENTI AI FRAMMENTI DA INDICIZZARE.

LA DECISIONE CENTRALE: DUE MISURE, NON UNA.

Si indicizzano frammenti BREVI — uno o due paragrafi. Non per risparmiare
spazio: perche' un frammento lungo produce un vettore che media argomenti
diversi, e un vettore che media tutto non somiglia precisamente a niente.
La rappresentazione di una pagina intera e' poltiglia.

Ma il frammento breve NON e' quello che verra' letto per decidere il tipo
di citazione: per quello serve sapere chi parla e in che punto
dell'argomentazione si e'. Quindi ogni frammento porta con se' le
coordinate (`char_start`, `char_end`) che permettono, a lettura, di
riaprire il documento e prendere la finestra allargata attorno.

Ricerca precisa, giudizio contestuale. E' tutto qui.

PERCHE' SI TAGLIA SUI CONFINI E NON A LUNGHEZZA FISSA. Un taglio a
lunghezza fissa spezza le frasi a meta'. Meta' frase produce un vettore
sbagliato in modo silenzioso — non da' errore, da' solo risultati peggiori
senza che nessuno capisca perche'. Qui si taglia sui paragrafi, e i
paragrafi troppo lunghi si spezzano sulle frasi.

PERCHE' LA SOVRAPPOSIZIONE. Un passaggio a cavallo fra due frammenti
verrebbe perso da entrambi: nel primo e' mozzato in coda, nel secondo in
testa, e in nessuno dei due somiglia abbastanza alla domanda. La
sovrapposizione e' l'assicurazione contro il caso peggiore, e costa solo
un po' di ripetizione.

IL NUMERO DI PAGINA SI PROPAGA. I segni `<!-- page N -->` sono gia' nel
testo: mentre si scorre si tiene l'ultimo visto, e ogni frammento nasce
sapendo a che pagina sta. Senza questo, il risultato non sarebbe
verificabile a mano — cioe' non servirebbe a niente.
"""

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
MD = HERE / 'markdown'
OUT = HERE / 'index' / 'chunks.jsonl'

# Misure in caratteri. Il modello ragiona in token, ma i caratteri sono
# osservabili e non dipendono dal tokenizzatore: con testo giuridico
# inglese e italiano il rapporto e' intorno a 4 caratteri per token, quindi
# 1.100 caratteri stanno largamente dentro qualunque finestra.
TARGET = 1100          # ampiezza a cui si punta
MIN_CHUNK = 250        # sotto questa soglia si accorpa al successivo
OVERLAP = 200          # coda del frammento precedente ripetuta in testa

PAGE_RE = re.compile(r'<!--\s*page\s+(\d+)\s*-->')
# Fine frase: punto, punto e virgola, due punti o interrogativo seguiti da
# spazio e maiuscola. Il negativo esclude le abbreviazioni piu' comuni negli
# atti — 'v.', 'No.', 'Inc.', 'Cir.' — che altrimenti spezzerebbero una
# citazione di causa a meta'.
SENT_RE = re.compile(
    r'(?<!\bv)(?<!\bNo)(?<!\bInc)(?<!\bCir)(?<!\bCo)(?<!\bLtd)(?<!\bMr)(?<!\bMrs)'
    r'[.;:?!]\s+(?=[A-Z"“(])'
)


def leggi(md: Path):
    """Separa il front matter dal corpo, conservando l'offset del corpo.

    Gli offset che finiscono nei frammenti sono riferiti al FILE INTERO e
    non al solo corpo: chi riapre il documento per prendere la finestra
    allargata apre il file, non una sua porzione."""
    testo = md.read_text(encoding='utf-8', errors='replace')
    if not testo.startswith('---\n'):
        return {}, testo, 0
    fine = testo.find('\n---\n', 4)
    if fine < 0:
        return {}, testo, 0
    testa, corpo_off = testo[4:fine], fine + 5
    meta = {}
    for riga in testa.split('\n'):
        m = re.match(r'^([a-z_0-9]+):\s*(.*)$', riga)
        if m:
            v = m.group(2).strip()
            if v.startswith("'") and v.endswith("'") and len(v) >= 2:
                v = v[1:-1].replace("''", "'")
            meta[m.group(1)] = v
    return meta, testo[corpo_off:], corpo_off


def pagine(corpo: str):
    """Elenco (offset, numero) dei segni di pagina, in ordine."""
    return [(m.start(), int(m.group(1))) for m in PAGE_RE.finditer(corpo)]


def pagina_di(marks, off: int) -> int:
    """La pagina in cui cade un offset: l'ultimo segno che lo precede."""
    p = 0
    for pos, num in marks:
        if pos <= off:
            p = num
        else:
            break
    return p or 1


def spezza_lungo(testo: str, base: int):
    """Un paragrafo piu' lungo del bersaglio si spezza sulle frasi."""
    tagli = [0] + [m.end() for m in SENT_RE.finditer(testo)] + [len(testo)]
    pezzi, inizio = [], 0
    for i in range(1, len(tagli)):
        if tagli[i] - inizio >= TARGET or i == len(tagli) - 1:
            if tagli[i] > inizio:
                pezzi.append((base + inizio, base + tagli[i]))
            inizio = tagli[i]
    return pezzi


def frammenti(corpo: str):
    """Confini (inizio, fine) dei frammenti, sui confini di paragrafo."""
    # I segni di pagina non sono testo: si tolgono dal conteggio ma NON dal
    # documento, perche' gli offset devono restare quelli veri del file.
    grezzi, pos = [], 0
    for par in re.split(r'\n\s*\n', corpo):
        lung = len(par) + 2
        pulito = PAGE_RE.sub('', par).strip()
        if pulito:
            grezzi.append((pos, pos + len(par), len(pulito)))
        pos += lung

    fuse, cur = [], None
    for a, b, utile in grezzi:
        if utile > TARGET * 1.6:
            if cur:
                fuse.append(cur); cur = None
            fuse.extend(spezza_lungo(corpo[a:b], a))
            continue
        if cur is None:
            cur = (a, b)
        elif (b - cur[0]) <= TARGET:
            cur = (cur[0], b)
        else:
            fuse.append(cur); cur = (a, b)
    if cur:
        fuse.append(cur)

    # Accorpamento dei residui: un frammento di due righe non ha abbastanza
    # contenuto per essere confrontato con qualcosa.
    out = []
    for a, b in fuse:
        if out and (b - a) < MIN_CHUNK:
            out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return out


def main(argv):
    solo = argv[1] if len(argv) > 1 else None
    OUT.parent.mkdir(parents=True, exist_ok=True)
    n_doc = n_frag = 0
    with OUT.open('w', encoding='utf-8') as f:
        for md in sorted(MD.rglob('*.md')):
            if solo and md.parent.name != solo:
                continue
            meta, corpo, base = leggi(md)
            marks = pagine(corpo)
            conf = frammenti(corpo)
            for i, (a, b) in enumerate(conf):
                testo = PAGE_RE.sub(' ', corpo[max(0, a - OVERLAP):b])
                testo = re.sub(r'[ \t]+', ' ', testo).strip()
                if len(testo) < MIN_CHUNK // 2:
                    continue
                f.write(json.dumps({
                    'id': f"{meta.get('document_id', md.stem)}#{i}",
                    'document_id': meta.get('document_id', ''),
                    'case_id': meta.get('case_id', ''),
                    'case_name': meta.get('case_name', ''),
                    'tipo_atto': meta.get('tipo_atto', ''),
                    'giurisdizioni': meta.get('giurisdizioni', ''),
                    'data': meta.get('data_deposito', ''),
                    # DUE PAGINE, NON UNA. Un frammento puo' scavalcare
                    # un'interruzione di pagina: registrarne una sola
                    # manderebbe chi verifica alla pagina sbagliata proprio
                    # nei casi a cavallo, che sono quelli in cui una
                    # citazione si spezza. Suggerimento adottato in
                    # revisione esterna.
                    'pagina': pagina_di(marks, a),
                    'pagina_fine': pagina_di(marks, b),
                    # Riferiti al FILE, non al corpo: servono a riaprire il
                    # documento e prendere la finestra allargata.
                    'char_start': base + a,
                    'char_end': base + b,
                    'file': str(md.relative_to(HERE)),
                    'url_documento': meta.get('url_documento', ''),
                    'testo': testo,
                }, ensure_ascii=False) + '\n')
                n_frag += 1
            n_doc += 1
    print(f'documenti : {n_doc}')
    print(f'frammenti : {n_frag}')
    print(f'media     : {n_frag / max(1, n_doc):.1f} frammenti per documento')
    print(f'uscita    : {OUT}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
