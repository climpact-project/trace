#!/usr/bin/env python3
"""IL TESTO DEI FILE NON PDF MAI ESTRATTI (03/10/2026): 20 FILE, 8 DEI QUALI TROVATI DA S05.

   Trovati dalla preparazione di S05 (`build_markdown_s05.py`, registro training/s05/markdown_s05_registro.json): otto
   documenti di luglio (.docx, .doc, .png) scaricati bene (impronta del disco = impronta di manifest.jsonl) ma mai
   estratti, perche' `extract_text.py` legge solo i PDF. Il file di testo che sembra loro (stesso nome troncato, .txt)
   e' il testo di un PDF dello stesso caso, che ha gia' il suo Markdown. La classe e' piu' larga: in manifest.jsonl i
   file non PDF senza Markdown sono 20 (gli altri 12 senza nemmeno il file di testo), e si estraggono tutti. Misura: training/misure/CORPUS-DIFETTI-2026-10-03.md.

   Che cosa fa, e solo questo:
     1. controlla che il file sul disco abbia l'impronta scritta in manifest.jsonl (se no, il documento si salta);
     2. .docx: il testo dal document.xml, diviso in pagine dove Word ha segnato le interruzioni di pagina che ha
        disegnato l'ultima volta (w:lastRenderedPageBreak) o quelle volute (w:br type=page), con gli stessi segni di
        pagina di extract_text.py; .doc: prima in .docx con textutil di macOS (che non porta le interruzioni: una
        pagina sola, detto nel registro); .png: OCR con tesseract (una pagina). LibreOffice non e' installato
        (il soffice di Homebrew rimanda a un'app che non c'e' piu'), quindi niente conversione in PDF;
     3. scrive testo e Markdown in una cartella NUOVA, `training/difetti-2026-10-03/` (text/ e markdown/, stessa
        sottocartella del caso, nome = document_id), con lo stesso front matter di build_markdown.front_matter.
   NON tocca markdown/, text/, documents/ ne' l'indice delle pagine: portare questi Markdown nel corpus e' un corpus
   nuovo (un codice D nuovo) e lo decide il PI. Ogni file si apre in creazione esclusiva: se esiste, si salta.
   Impronte di ogni ingresso e uscita in training/difetti-2026-10-03/registro_non_pdf.json.

   Uso:  .venv/bin/python tools/estrai_non_pdf.py            dice cosa farebbe
         .venv/bin/python tools/estrai_non_pdf.py --scrivi   scrive
"""
import argparse, hashlib, json, re, subprocess, sys, tempfile, unicodedata
from pathlib import Path

QUI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
import build_markdown as BM            # noqa: E402  stesso front matter dei 16.791 documenti
import build_markdown_s05 as S         # noqa: E402  stessa lettura dei metadati (metadata.csv e CSV degli aggiornamenti)

OUT = QUI/'training'/'difetti-2026-10-03'
PAGE_MARK = "\n\n<!-- page {n} -->\n\n"     # come extract_text.py
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def sha_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def da_estrarre():
    """Tutti i file non PDF di manifest.jsonl (scaricati, http 200) il cui documento non ha un Markdown. Erano 8 nel
    registro di S05 (nome troncato uguale a quello di un PDF, testo che sembra loro ma non e'), ma la classe e' piu'
    larga: altri 12 non hanno nemmeno il file di testo (i «senza testo» dei conti di S05). Misura del 03/10: 20 file,
    16 .docx, 3 .doc, 1 .png."""
    con_md, _ = S.documenti_con_markdown()
    out = []
    for l in open(QUI/'manifest.jsonl', encoding='utf-8'):
        m = json.loads(l)
        if not m.get('path') or not m.get('docs') or m['path'].lower().endswith('.pdf') or m.get('http') != 200:
            continue
        ids = [d['document_id'] for d in m['docs']]
        if any(x in con_md for x in ids):
            continue
        out.append(({'document_id': ids[0], 'origine': m['path']}, m))
    return out


def pagine_docx(path):
    """Il testo di un .docx per pagine: si va a pagina nuova a ogni w:lastRenderedPageBreak (dove Word ha messo la
    pagina l'ultima volta che ha disegnato il documento) e a ogni w:br w:type="page". Paragrafi separati da un a capo,
    tabulazioni e a capo dentro il paragrafo conservati, celle delle tabelle in ordine di lettura."""
    import zipfile
    import xml.etree.ElementTree as ET
    root = ET.fromstring(zipfile.ZipFile(path).read('word/document.xml'))
    pagine, cur, segni = [[]], [], 0
    for p in root.iter(W + 'p'):
        for el in p.iter():
            if el.tag == W + 'lastRenderedPageBreak' or (el.tag == W + 'br' and el.get(W + 'type') == 'page'):
                pagine[-1].append(''.join(cur)); cur = []; pagine.append([]); segni += 1
            elif el.tag == W + 't':
                cur.append(el.text or '')
            elif el.tag == W + 'tab':
                cur.append('\t')
            elif el.tag in (W + 'br', W + 'cr'):
                cur.append('\n')
        pagine[-1].append(''.join(cur)); cur = []
    testi = ['\n'.join(x) for x in pagine]
    # una pagina vuota in testa (il primo paragrafo comincia con l'interruzione) non e' una pagina del documento
    while len(testi) > 1 and not testi[0].strip():
        testi.pop(0)
    return ''.join(PAGE_MARK.format(n=i) + t + '\n' for i, t in enumerate(testi, 1)), len(testi), segni


def converti(orig, tmp):
    ext = orig.suffix.lower()
    if ext == '.docx':
        testo, n, segni = pagine_docx(orig)
        return testo, n, f'document.xml del .docx, pagine dalle interruzioni segnate da Word ({segni})', None
    if ext == '.doc':
        dx = tmp/(orig.stem + '.docx')
        r = subprocess.run(['textutil', '-convert', 'docx', '-output', str(dx), str(orig)], capture_output=True, text=True, timeout=300)
        if r.returncode or not dx.exists():
            raise RuntimeError(f'textutil non ha convertito il .doc: {r.stderr[-300:]}')
        testo, n, segni = pagine_docx(dx)
        return testo, n, f'textutil -convert docx, poi document.xml (interruzioni di pagina {segni}: il .doc non porta quelle disegnate)', None
    if ext == '.png':
        r = subprocess.run(['tesseract', str(orig), '-', '-l', 'eng'], capture_output=True, text=True, timeout=300)
        if r.returncode:
            raise RuntimeError(r.stderr[-300:])
        return PAGE_MARK.format(n=1) + r.stdout, 1, 'tesseract -l eng', None
    raise RuntimeError(f'estensione non prevista: {ext}')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--scrivi', action='store_true'); a = ap.parse_args()
    meta = S.metadati()
    voci = []
    for x, m in da_estrarre():
        did, orig = x['document_id'], QUI/x['origine']
        v = {'document_id': did, 'origine': x['origine'], 'url': m['url'] if m else None,
             'sha256_manifest': m['sha256'] if m else None, 'sha256_disco': sha_file(orig) if orig.exists() else None}
        if not m or v['sha256_manifest'] != v['sha256_disco']:
            v['esito'] = 'saltato: impronta del disco diversa da manifest.jsonl'; voci.append(v); print(did[-40:], v['esito']); continue
        cand = sorted(meta.get(did, []), key=lambda r: (r[0].get('Document Content URL', '') != m['url'], r[1] != 'metadata.csv'))
        if not cand:
            v['esito'] = 'saltato: senza metadati'; voci.append(v); print(did[-40:], v['esito']); continue
        cartella = Path(x['origine']).parent.relative_to('documents')
        txt = OUT/'text'/cartella/f'{did}.txt'
        md = OUT/'markdown'/cartella/f'{did}.md'
        v.update({'testo': str(txt.relative_to(QUI)), 'markdown': str(md.relative_to(QUI)), 'fonte_metadati': cand[0][1]})
        if not a.scrivi:
            v['esito'] = 'da scrivere'; voci.append(v); print(did[-40:], '->', v['markdown']); continue
        if txt.exists() or md.exists():
            v['esito'] = 'esiste gia\' (non toccato)'; voci.append(v); print(did[-40:], v['esito']); continue
        with tempfile.TemporaryDirectory() as t:
            testo, n, metodo, _ = converti(orig, Path(t))
        txt.parent.mkdir(parents=True, exist_ok=True); md.parent.mkdir(parents=True, exist_ok=True)
        with open(txt, 'x', encoding='utf-8') as f:
            f.write(testo)
        testa = BM.front_matter(cand[0][0], txt, orig, n, m['sha256'])
        with open(md, 'x', encoding='utf-8') as f:
            f.write(testa + testo)
        parole = len(re.findall(r'\w+', re.sub(r'<!--.*?-->', '', testo)))
        v.update({'esito': 'scritto', 'metodo': metodo, 'pagine': n, 'parole': parole,
                  'sha256_testo': sha_file(txt), 'sha256_markdown': sha_file(md)})
        voci.append(v); print(did[-40:], 'scritto', n, 'pagine', parole, 'parole')
    if a.scrivi:
        OUT.mkdir(parents=True, exist_ok=True)
        try:   # i documenti gia' scritti da un'esecuzione precedente tengono la loro voce
            prima = {v['document_id']: v for v in json.load(open(OUT/'registro_non_pdf.json', encoding='utf-8'))['documenti']
                     if v.get('esito') == 'scritto'}
        except FileNotFoundError:
            prima = {}
        voci = [prima.get(v['document_id'], v) if v['esito'].startswith('esiste') else v for v in voci]
        (OUT/'registro_non_pdf.json').write_text(json.dumps(
            {'data': '2026-10-03', 'ingressi': {'manifest.jsonl': sha_file(QUI/'manifest.jsonl'),
                                                'training/s05/markdown_s05_registro.json': sha_file(QUI/'training/s05/markdown_s05_registro.json')},
             'documenti': voci}, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    import giornale  # il giornale delle operazioni: ogni esecuzione, i file, le scritture, gli errori
    giornale.avvia()
    main()
