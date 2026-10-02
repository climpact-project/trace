#!/usr/bin/env python3
"""AGGIUNGE LO STRATO DI TESTO AI PDF CHE NON CE L'HANNO.

A CHE SERVE. Il controllo manuale — il 20% delle righe che una persona
verifica aprendo il documento — si fa sul PDF. Se il PDF e' una scansione
senza strato di testo, il lettore mostra l'immagine e la ricerca dentro non
trova niente: chi verifica deve scorrere a occhio quarantotto pagine per
ritrovare la citazione che il sistema ha gia' individuato. E' il modo piu'
veloce per far abbandonare la verifica.

CHI RIGUARDA. Solo i 562 riparati: 521 scansioni senza testo, 23 con testo
per pagina insufficiente e 19 con codifica di font non standard. Gli altri
16.229 documenti lo strato di testo ce l'hanno gia' e sono ricercabili cosi'
come sono — su quelli non si tocca niente, perche' rifare l'OCR di un PDF
gia' buono lo peggiora.

L'ASPETTO NON CAMBIA. `ocrmypdf` aggiunge un livello di testo INVISIBILE
sotto l'immagine della pagina: si vede esattamente la stessa scansione di
prima, ma la si puo' cercare, selezionare e copiare.

DUE MODI DIVERSI PER DUE GUASTI DIVERSI:
  scansione  — non c'e' testo: si aggiunge (`--skip-text` non serve, non
               c'e' nulla da saltare).
  codifica   — il testo c'e' ma e' sbagliato: va SOSTITUITO
               (`--force-ocr`), altrimenti ocrmypdf lo trova e non fa
               niente, e il PDF resta illeggibile alla ricerca.

L'ORIGINALE SI CONSERVA, accanto, come `.pdf.orig`. Non e' scrupolo: il
PDF originale e' la fonte, e la sua impronta (`sha256_pdf` nel front
matter) identifica il file scaricato dal Sabin. Riscrivendolo quell'impronta
non corrisponderebbe piu', e senza l'originale non ci sarebbe modo di
dimostrare che il documento e' quello.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
LINGUE = {
    'english': 'eng', 'italian': 'ita', 'french': 'fra', 'spanish': 'spa',
    'german': 'deu', 'portuguese': 'por', 'dutch': 'nld',
}


def da_fare():
    """I 562, con il motivo — che decide come si tratta il PDF."""
    fuori = {}
    reg = HERE / 'text_index.jsonl'
    if reg.exists():
        for riga in reg.open(encoding='utf-8'):
            try:
                r = json.loads(riga)
            except ValueError:
                continue
            if r.get('needs_ocr') or (r.get('chars_per_page') or 0) < 50:
                rel = r['path']
                if not rel.startswith('documents/'):
                    rel = 'documents/' + rel
                fuori[rel] = 'scansione'
    # I DOCUMENTI NASCOSTI DAL TIMBRO vanno trattati come quelli con la
    # codifica rotta: il testo digitale c'e' (e' il timbro di deposito) ma
    # non e' quello del documento, quindi va SOSTITUITO. Con `--skip-text`
    # ocrmypdf troverebbe il timbro, concluderebbe che il PDF ha gia' testo
    # e non farebbe niente — che e' esattamente il motivo per cui questi 129
    # erano sfuggiti a tutti i controlli precedenti.
    timbro = HERE / 'index' / 'da_riparare_timbro.json'
    if timbro.exists():
        for v in json.loads(timbro.read_text(encoding='utf-8')):
            fuori[v['file'].replace('markdown/', 'documents/')
                  .replace('.md', '.pdf')] = 'codifica'

    diag = HERE / 'index' / 'diagnosi_testo.json'
    if diag.exists():
        d = json.loads(diag.read_text(encoding='utf-8'))
        for v in d.get('liste', {}).get('corrotto', []):
            fuori[v['file'].replace('markdown/', 'documents/')
                  .replace('.md', '.pdf')] = 'codifica'
    return fuori


def lingua(md: Path) -> str:
    import re
    try:
        testa = md.read_text(encoding='utf-8', errors='replace')[:4000]
    except OSError:
        return 'eng'
    m = re.search(r"^lingue: '(.*)'", testa, re.M)
    if not m:
        return 'eng'
    for pezzo in m.group(1).split(';'):
        c = LINGUE.get(pezzo.strip().lower())
        if c:
            return f'{c}+eng' if c != 'eng' else 'eng'
    return 'eng'


def uno(args):
    rel, motivo, lang = args
    pdf = HERE / rel
    orig = pdf.with_suffix('.pdf.orig')
    if not pdf.exists():
        return ('assente', rel, '')
    if orig.exists():
        return ('gia fatto', rel, '')

    tmp = pdf.with_suffix('.pdf.tmp')
    cmd = ['ocrmypdf', '--quiet', '-l', lang, '--optimize', '1']
    if motivo == 'codifica':
        # Il testo c'e' ma e' sbagliato: va sostituito, non saltato.
        cmd.append('--force-ocr')
    else:
        # Se qualche pagina avesse gia' del testo buono, non si tocca.
        cmd.append('--skip-text')
    cmd += [str(pdf), str(tmp)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        tmp.unlink(missing_ok=True)
        return ('tempo scaduto', rel, '')
    if r.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        return ('errore', rel, (r.stderr or '').strip()[:90])

    # L'originale prima, poi la sostituzione: se qualcosa va storto a meta',
    # non si resta senza nessuna delle due versioni.
    shutil.copy2(pdf, orig)
    shutil.move(str(tmp), str(pdf))
    return ('ok', rel, '')


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--limite', type=int, default=0)
    args = ap.parse_args(argv[1:])

    elenco = da_fare()
    lavori = []
    for rel, motivo in sorted(elenco.items()):
        if not (HERE / rel).exists():
            continue
        md = HERE / 'markdown' / Path(rel).relative_to('documents').with_suffix('.md')
        lavori.append((rel, motivo, lingua(md)))
        if args.limite and len(lavori) >= args.limite:
            break

    proc = max(1, (os.cpu_count() or 4) - 2)
    print(f'PDF da rendere ricercabili: {len(lavori)}')
    print(f'processi in parallelo     : {proc}', flush=True)

    esiti = {}
    with ProcessPoolExecutor(max_workers=proc) as pool:
        futuri = [pool.submit(uno, l) for l in lavori]
        for i, f in enumerate(as_completed(futuri), 1):
            esito, rel, msg = f.result()
            esiti[esito] = esiti.get(esito, 0) + 1
            if esito in ('errore', 'tempo scaduto'):
                print(f'  ! {Path(rel).name[:46]}: {msg}', flush=True)
            if i % 25 == 0:
                print(f'  {i}/{len(lavori)}  (fatti {esiti.get("ok", 0)})', flush=True)

    print()
    for k, v in sorted(esiti.items()):
        print(f'  {k:14s}: {v}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
