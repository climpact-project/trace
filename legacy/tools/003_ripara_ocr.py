#!/usr/bin/env python3
"""RIPARA I DOCUMENTI SENZA TESTO UTILIZZABILE.

CHI RIPARA E PERCHE'. Due gruppi, individuati dal censimento
(`tools/002_diagnosi_testo.py`) e dal registro del corpus (`text_index.jsonl`):

  537  scansioni senza strato di testo, gia' segnalate `needs_ocr`
   19  PDF con codifica di font non standard: hanno molto testo, ma ogni
       carattere e' mappato sul simbolo sbagliato. Il campo `needs_ocr` non
       poteva vederli, perche' guarda la quantita' di testo e non la sua
       leggibilita'.

Sono 556 documenti sui 16.791 del corpus. Il punto non e' la quota: sono
documenti che oggi, in ogni ricerca, risultano MUTI — non "assenti", che
si noterebbe, ma "senza citazioni", che non si nota.

COME. Si rende ogni pagina in immagine e la si legge con tesseract. Non si
tocca il PDF: si riscrive soltanto il `.txt`, nello stesso formato di
prima, con gli stessi segni `<!-- page N -->`. Il resto della catena non se
ne accorge.

PERCHE' NON SI USA LO STRATO DI TESTO. Per le scansioni non c'e'. Per i 19
c'e' ma e' sbagliato, ed e' proprio il motivo per cui vanno letti
dall'immagine: la pagina renderizzata e' corretta, e' la sua codifica a non
esserlo. Verificato su un atto della Corte d'appello del Quinto Circuito:
lo strato di testo dava `,QWKH8QLWHG6WDWHV`, l'OCR sulla pagina resa
`In the United States`.

LA LINGUA. Presa dai metadati quando c'e' (`lingue` nel front matter),
altrimenti inglese. Una lingua sbagliata non impedisce la lettura ma
peggiora l'accuratezza, e su un corpus multilingue vale la pena chiederlo
ai dati invece di supporlo.

I 300 PUNTI PER POLLICE non sono un valore a caso: sotto i 200 tesseract
perde le lettere piccole delle note a pie' di pagina, che negli atti sono
esattamente dove stanno le citazioni.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import fitz  # PyMuPDF

HERE = Path(__file__).resolve().parent.parent
TEXT = HERE / 'text'
DOCS = HERE / 'documents'
DPI = 300

# Dai codici lingua del CSV a quelli di tesseract. Solo quelli installati:
# una lingua non installata fa fallire il comando, e un fallimento su un
# documento non deve fermare gli altri 555.
LINGUE = {
    'english': 'eng', 'italian': 'ita', 'french': 'fra', 'spanish': 'spa',
    'german': 'deu', 'portuguese': 'por', 'dutch': 'nld',
}


def lingue_disponibili():
    try:
        r = subprocess.run(['tesseract', '--list-langs'],
                           capture_output=True, text=True, timeout=30)
        return set(r.stdout.split()[1:])
    except Exception:
        return {'eng'}


def lingua_per(md_path: Path, disponibili: set) -> str:
    """La lingua dichiarata nei metadati, se e' installata."""
    try:
        testa = md_path.read_text(encoding='utf-8', errors='replace')[:4000]
    except OSError:
        return 'eng'
    m = re.search(r"^lingue: '(.*)'", testa, re.M)
    if not m:
        return 'eng'
    for pezzo in m.group(1).split(';'):
        cod = LINGUE.get(pezzo.strip().lower())
        if cod and cod in disponibili:
            return f'{cod}+eng' if cod != 'eng' else 'eng'
    return 'eng'


def ocr_pdf(pdf: Path, lang: str) -> str:
    """Il testo del PDF letto dalle pagine rese, con i segni di pagina."""
    doc = fitz.open(pdf)
    mat = fitz.Matrix(DPI / 72, DPI / 72)
    pezzi = []
    tmp = Path(tempfile.mkdtemp(prefix='ocr_'))
    try:
        for i, pagina in enumerate(doc, 1):
            img = tmp / f'p{i:04d}.png'
            pagina.get_pixmap(matrix=mat).save(img)
            r = subprocess.run(
                ['tesseract', str(img), 'stdout', '-l', lang],
                capture_output=True, text=True, timeout=180,
            )
            pezzi.append(f'\n\n<!-- page {i} -->\n\n' + (r.stdout or ''))
            img.unlink(missing_ok=True)
    finally:
        doc.close()
        shutil.rmtree(tmp, ignore_errors=True)
    return ''.join(pezzi)


def da_riparare():
    """L'elenco dei documenti da rifare, dalle due fonti."""
    fuori = {}
    reg = HERE / 'text_index.jsonl'
    if reg.exists():
        for riga in reg.open(encoding='utf-8'):
            try:
                r = json.loads(riga)
            except ValueError:
                continue
            if r.get('needs_ocr') or (r.get('chars_per_page') or 0) < 50:
                # I DUE REGISTRI SCRIVONO I PERCORSI IN MODO DIVERSO.
                # `manifest.jsonl` li scrive completi ('documents/caso/x.pdf'),
                # `text_index.jsonl` li scrive relativi alla cartella dei
                # documenti ('caso/x.pdf'). Cercando i file cosi' come sono
                # scritti, 543 documenti su 562 risultavano assenti dal disco:
                # sembrava un buco nel corpus ed era una differenza di
                # convenzione fra due file. Si normalizza qui, una volta.
                rel = r['path']
                if not rel.startswith('documents/'):
                    rel = 'documents/' + rel
                fuori[rel] = 'scansione'
    # IL TERZO GRUPPO: I DOCUMENTI NASCOSTI DAL TIMBRO.
    #
    # I tribunali federali statunitensi e la corte di New York stampano su
    # ogni pagina un timbro di deposito elettronico — "Case 3:17-cv-06011-WHA
    # Document 280 Filed 06/23/18 Page 1 of 1". Quel timbro e' testo
    # DIGITALE sovrapposto a una pagina che per il resto e' un'immagine.
    #
    # Da solo vale 60-140 caratteri per pagina: abbastanza da superare la
    # soglia di 50 caratteri/pagina con cui si decideva chi mandare all'OCR.
    # Risultato: 129 documenti — 34 dei quali oltre le venti pagine —
    # risultavano "con testo" e il loro contenuto non e' mai stato letto.
    # Verificato su una rinuncia alla notifica in City of Oakland v. BP:
    # 68 caratteri estraibili, 2.708 di contenuto reale.
    #
    # Vanno trattati come i 19 con la codifica rotta: il testo c'e' ma non
    # e' quello del documento, quindi va SOSTITUITO, non integrato.
    timbro = HERE / 'index' / 'da_riparare_timbro.json'
    if timbro.exists():
        for v in json.loads(timbro.read_text(encoding='utf-8')):
            fuori[v['file'].replace('markdown/', 'documents/')
                  .replace('.md', '.pdf')] = 'codifica'

    diag = HERE / 'index' / 'diagnosi_testo.json'
    if diag.exists():
        d = json.loads(diag.read_text(encoding='utf-8'))
        for v in d.get('liste', {}).get('corrotto', []):
            # `file` e' il percorso del markdown: si risale al PDF.
            p = v['file'].replace('markdown/', 'documents/').replace('.md', '.pdf')
            fuori[p] = 'codifica'
    return fuori


def ripara_uno(args):
    """Ripara un documento. Gira in un processo suo.

    PERCHE' UN PROCESSO PER DOCUMENTO E NON PER PAGINA. Il lavoro pesante e'
    tesseract, che e' un programma esterno: parallelizzare per documento
    tiene occupati tutti i core senza dover coordinare nulla, e un
    documento che fallisce non trascina gli altri.

    Si lasciano due core liberi: la macchina deve restare usabile mentre il
    lavoro gira, e un OCR che rende inutilizzabile il portatile per tre ore
    e' un OCR che non si lancia mai.
    """
    rel, lang = args
    pdf = HERE / rel
    txt = TEXT / Path(rel).relative_to('documents').with_suffix('.txt')

    # GIA' RIPARATO: NON SI RIFA'.
    # La copia di riserva `.txt.pre-ocr` esiste solo se quel documento e'
    # gia' passato di qui. Senza questo controllo, ogni nuovo gruppo da
    # riparare si trascinava dietro tutti i precedenti: aggiungendo 129
    # documenti se ne rileggevano 672, cioe' un'ora di lavoro per rifare
    # cio' che era gia' fatto — e sovrascrivendo un buon risultato con un
    # secondo passaggio identico.
    if txt.with_suffix('.txt.pre-ocr').exists():
        return ('gia fatto', rel, '')

    try:
        nuovo = ocr_pdf(pdf, lang)
    except Exception as e:
        return ('errore', rel, str(e)[:80])
    utile = len(re.sub(r'<!--.*?-->', '', nuovo).strip())
    if utile < 200:
        return ('vuoto', rel, '')
    if txt.exists() and not txt.with_suffix('.txt.pre-ocr').exists():
        shutil.copy2(txt, txt.with_suffix('.txt.pre-ocr'))
    txt.parent.mkdir(parents=True, exist_ok=True)
    txt.write_text(nuovo, encoding='utf-8')
    return ('ok', rel, '')


def main(argv):
    limite = int(argv[1]) if len(argv) > 1 else 0
    disp = lingue_disponibili()
    elenco = da_riparare()

    lavori = []
    assenti = 0
    for rel in sorted(elenco):
        if not (HERE / rel).exists():
            assenti += 1
            continue
        md = HERE / 'markdown' / Path(rel).relative_to('documents').with_suffix('.md')
        lavori.append((rel, lingua_per(md, disp)))
        if limite and len(lavori) >= limite:
            break

    processi = max(1, (os.cpu_count() or 4) - 2)
    print(f'da riparare: {len(lavori)}  (assenti dal disco: {assenti})')
    print(f'processi in parallelo: {processi}')

    import collections
    esiti = collections.Counter()
    with ProcessPoolExecutor(max_workers=processi) as pool:
        futuri = {pool.submit(ripara_uno, l): l[0] for l in lavori}
        for i, f in enumerate(as_completed(futuri), 1):
            esito, rel, msg = f.result()
            esiti[esito] += 1
            if esito == 'errore':
                print(f'  ! {Path(rel).name[:48]}: {msg}')
            if i % 25 == 0:
                print(f'  {i}/{len(lavori)}  (riparati {esiti["ok"]})')

    print(f'\nriparati    : {esiti["ok"]}')
    print(f'OCR a vuoto : {esiti["vuoto"]}')
    print(f'errori      : {esiti["errore"]}')
    print(f'assenti     : {assenti}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
