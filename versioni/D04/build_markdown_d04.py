#!/usr/bin/env python3
"""D04, PASSO 2: TESTO, MARKDOWN E PAGINE DEI 26 PDF RISCARICATI E DEI 20 FILE NON PDF (03/10/2026).

   Ingressi:
     - `manifest_supplemento_2026-10-03.jsonl` (scritto da `tools/scarica_d04.py`): i 27 atti del 19/09 mai scaricati.
       26 hanno un file nuovo; uno (Suncor amicus-brief-18, _0873) e' identico alla fonte a un atto gia' nel corpus
       (_b0d1) e NON si riscrive: la ricerca lo toglierebbe come copia.
     - `training/difetti-2026-10-03/registro_non_pdf.json` (scritto da `tools/estrai_non_pdf.py`): i 20 file non PDF
       mai estratti, con il loro testo gia' fatto nella cartella a parte.

   Come il corpus (stesse regole, stesso codice dove si puo'):
     - testo dei PDF: PyMuPDF pagina per pagina con i segni di pagina di `extract_text.py`; se il documento ha meno di
       20 caratteri per pagina (`extract_text.OCR_THRESHOLD`) e' una scansione e va tutto all'OCR di `ocr_pass.py`
       (Vision di macOS, lingue dal campo Language(s) del Sabin, 200 dpi);
     - OCR solo dove il testo e' inservibile, con i freni: nei documenti col testo, una pagina passa all'OCR solo se
       `freni.leggibile` la dice illeggibile, e si sostituisce solo se l'OCR e' leggibile (la regola
       `applica_ocr.da_sostituire` di D02). Le pagine sostituite sono scritte nel registro;
     - Markdown: `build_markdown.front_matter` con la riga dei metadati che descrive lo stesso indirizzo
       (`build_markdown_s05.metadati`), impronta vera dal supplemento.
   NOMI NUOVI, MAI SOVRASCRIVERE: i PDF hanno gia' il nome `<nome>__<8 cifre di sha256(url)>.pdf`; testo e Markdown
   prendono lo stesso nome in `text/` e `markdown/`. I 20 non PDF prendono `<nome del file d'origine>__<8 cifre di
   sha256(url)>` (8 di loro hanno lo stesso nome troncato di un PDF che ha gia' il suo Markdown). Ogni file si apre in
   creazione esclusiva.

   L'INDICE DELLE PAGINE VIVO NON SI TOCCA (una catena lo legge): si scrive accanto `index/pagine/pagine.d04.jsonl.gz`
   (il vivo copiato byte per byte piu' le pagine nuove come secondo membro gzip, come `build_markdown_s05.py`) e
   `index/pagine/pagine.d04.aggiunte.jsonl.gz` (solo le nuove). Impronte di ingressi e uscite in
   `training/d04/markdown_d04_registro.json`.

   Uso:  .venv/bin/python tools/build_markdown_d04.py            dice cosa farebbe
         .venv/bin/python tools/build_markdown_d04.py --scrivi   scrive
"""
import argparse, gzip, hashlib, io, json, re, shutil, sys, time
from pathlib import Path

QUI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools')); sys.path.insert(0, str(QUI))
import build_markdown as BM            # noqa: E402
import build_markdown_s05 as S         # noqa: E402  metadati e pagine dell'indice
from freni import leggibile            # noqa: E402
from applica_ocr import da_sostituire, quota_cjk   # noqa: E402

SUPPL = QUI/'manifest_supplemento_2026-10-03.jsonl'
NONPDF = QUI/'training'/'difetti-2026-10-03'/'registro_non_pdf.json'
D04 = QUI/'training'/'d04'
PAG = QUI/'index'/'pagine'
PAGE_MARK = "\n\n<!-- page {n} -->\n\n"     # come extract_text.py
OCR_THRESHOLD = 20                           # come extract_text.py
sha_file = S.sha_file


def riga_metadati(meta, did, url):
    cand = sorted(meta.get(did, []), key=lambda r: (r[0].get('Document Content URL', '') != url, r[1] != 'metadata.csv'))
    return cand[0] if cand else (None, None)


def ocr_pagina(page, prefs):
    import ocr_pass as O
    from ocrmac import ocrmac
    from PIL import Image
    pix = page.get_pixmap(dpi=O.DPI)
    img = Image.open(io.BytesIO(pix.tobytes('png')))
    return O.page_text(ocrmac.OCR(img, language_preference=prefs).recognize())


def testo_pdf(pdf, lingue):
    """(testo con i segni di pagina, pagine, metodo, pagine rifatte con l'OCR)"""
    import fitz
    import ocr_pass as O
    prefs = O.langs_for(lingue)
    doc = fitz.open(pdf)
    vecchie = [p.get_text('text') for p in doc]
    n = len(vecchie)
    cpp = sum(len(t.strip()) for t in vecchie) / n if n else 0
    if cpp < OCR_THRESHOLD:
        nuove = [ocr_pagina(doc[i], prefs) for i in range(n)]
        doc.close()
        legg = sum(1 for t in nuove if leggibile(t)[0])
        return (''.join(PAGE_MARK.format(n=i) + t for i, t in enumerate(nuove, 1)), n,
                f'OCR Vision di tutto il documento ({cpp:.1f} caratteri per pagina nel testo del PDF; lingue {prefs}); '
                f'pagine leggibili dopo l\'OCR {legg}/{n}', list(range(1, n + 1)))
    cjk = any(quota_cjk(t) > 0.2 for t in vecchie)
    rifatte = []
    for i, t in enumerate(vecchie):
        if leggibile(t)[0]:
            continue
        nuova = ocr_pagina(doc[i], prefs)
        if da_sostituire(t, nuova, cjk):
            vecchie[i] = nuova
            rifatte.append(i + 1)
    doc.close()
    metodo = 'testo del PDF (PyMuPDF)' + (f'; OCR Vision sulle pagine illeggibili {rifatte} (freni.leggibile)' if rifatte else '')
    return ''.join(PAGE_MARK.format(n=i) + t for i, t in enumerate(vecchie, 1)), n, metodo, rifatte


def scrivi_x(p, testo):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'x', encoding='utf-8') as f:     # creazione esclusiva: mai sopra un file
        f.write(testo)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--scrivi', action='store_true'); a = ap.parse_args()
    meta = S.metadati()
    voci = []
    # ── 1. i PDF riscaricati ──────────────────────────────────────────────────────────────────────────────────────────
    for l in open(SUPPL, encoding='utf-8'):
        r = json.loads(l)
        did = r['docs'][0]['document_id']
        v = {'document_id': did, 'origine': r['path'], 'url': r['url'], 'sha256_origine': r['sha256'], 'gruppo': 'pdf_riscaricato'}
        if r.get('duplicato_alla_fonte'):
            v['esito'] = f"non scritto: identico alla fonte a {r['duplicato_alla_fonte']['document_id']}, che ha gia' il suo Markdown"
            voci.append(v); print(did[-40:], v['esito'][:60]); continue
        pdf = QUI/r['path']
        assert sha_file(pdf) == r['sha256'], f'{pdf}: impronta diversa dal supplemento'
        rel = Path(r['path']).relative_to('documents')
        txt, md = QUI/'text'/rel.with_suffix('.txt'), QUI/'markdown'/rel.with_suffix('.md')
        riga, fonte = riga_metadati(meta, did, r['url'])
        v.update({'testo': str(txt.relative_to(QUI)), 'markdown': str(md.relative_to(QUI)), 'fonte_metadati': fonte})
        if riga is None:
            v['esito'] = 'non scritto: senza metadati'; voci.append(v); print(did[-40:], v['esito']); continue
        if txt.exists() or md.exists():
            v['esito'] = 'esiste gia\' (non toccato)'; voci.append(v); print(did[-40:], v['esito']); continue
        if not a.scrivi:
            v['esito'] = 'da scrivere'; voci.append(v); print(did[-40:], '->', v['markdown'][-70:]); continue
        testo, n, metodo, rifatte = testo_pdf(pdf, riga.get('Language(s)', ''))
        scrivi_x(txt, testo)
        scrivi_x(md, BM.front_matter(riga, txt, pdf, n, r['sha256']) + testo)
        legg = [leggibile(t)[0] for t in re.split(r'<!-- page \d+ -->', testo)[1:]]
        v.update({'esito': 'scritto', 'metodo': metodo, 'pagine': n, 'pagine_ocr': rifatte,
                  'pagine_leggibili': sum(legg), 'parole': len(re.findall(r'\w+', re.sub(r'<!--.*?-->', '', testo))),
                  'sha256_testo': sha_file(txt), 'sha256_markdown': sha_file(md)})
        voci.append(v); print(did[-40:], 'scritto', n, 'pagine,', sum(legg), 'leggibili;', metodo[:70])
    # ── 2. i 20 non PDF, dal testo gia' estratto a parte ──────────────────────────────────────────────────────────────
    for x in json.load(open(NONPDF, encoding='utf-8'))['documenti']:
        did = x['document_id']
        v = {'document_id': did, 'origine': x['origine'], 'url': x['url'], 'sha256_origine': x['sha256_manifest'], 'gruppo': 'non_pdf'}
        if x.get('esito') != 'scritto':
            v['esito'] = 'non scritto: non estratto il 03/10'; voci.append(v); continue
        sorg = QUI/x['testo']
        assert sha_file(sorg) == x['sha256_testo'], f'{sorg}: testo cambiato dopo l\'estrazione'
        orig = QUI/x['origine']
        assert sha_file(orig) == x['sha256_manifest'], f'{orig}: impronta diversa dal manifest'
        rel = Path(x['origine']).relative_to('documents')
        tag = hashlib.sha256(x['url'].encode()).hexdigest()[:8]
        stem = rel.stem if rel.stem.endswith(f'__{tag}') else f'{rel.stem}__{tag}'   # gia' col suffisso dei doppioni di luglio
        txt, md = QUI/'text'/rel.parent/f'{stem}.txt', QUI/'markdown'/rel.parent/f'{stem}.md'
        riga, fonte = riga_metadati(meta, did, x['url'])
        v.update({'testo': str(txt.relative_to(QUI)), 'markdown': str(md.relative_to(QUI)), 'fonte_metadati': fonte,
                  'testo_estratto_il_03_10': x['testo'], 'metodo': x['metodo']})
        if txt.exists() or md.exists():
            v['esito'] = 'esiste gia\' (non toccato)'; voci.append(v); print(did[-40:], v['esito']); continue
        if not a.scrivi:
            v['esito'] = 'da scrivere'; voci.append(v); print(did[-40:], '->', v['markdown'][-70:]); continue
        testo = sorg.read_text(encoding='utf-8')
        scrivi_x(txt, testo)
        scrivi_x(md, BM.front_matter(riga, txt, orig, x['pagine'], x['sha256_manifest']) + testo)
        legg = [leggibile(t)[0] for t in re.split(r'<!-- page \d+ -->', testo)[1:]]
        v.update({'esito': 'scritto', 'pagine': x['pagine'], 'pagine_leggibili': sum(legg), 'parole': x['parole'],
                  'sha256_testo': sha_file(txt), 'sha256_markdown': sha_file(md)})
        voci.append(v); print(did[-40:], 'scritto', x['pagine'], 'pagine')
    if not a.scrivi:
        print('PROVA: niente scritto (--scrivi per scrivere)'); return 0
    # ── 3. l'indice delle pagine D04 accanto al vivo ──────────────────────────────────────────────────────────────────
    nuove = []
    for v in voci:
        if v['esito'] == 'scritto':
            pp = S.pagine_del_file(QUI/v['markdown'])
            v['pagine_nell_indice'] = len(pp)
            nuove += pp
    vivo = PAG/'pagine.jsonl.gz'
    sha_vivo = sha_file(vivo)
    agg, d04 = PAG/'pagine.d04.aggiunte.jsonl.gz', PAG/'pagine.d04.jsonl.gz'
    for p in (agg, d04):
        if p.exists():
            print(f'FERMO: {p.name} esiste gia\''); return 1
    with gzip.open(agg, 'xt', encoding='utf-8') as f:
        for x in nuove:
            f.write(json.dumps(x, ensure_ascii=False) + '\n')
    with open(d04, 'xb') as f, open(vivo, 'rb') as g:
        shutil.copyfileobj(g, f)
    with open(d04, 'ab') as f, open(agg, 'rb') as g:
        shutil.copyfileobj(g, f)
    assert sha_file(vivo) == sha_vivo, "l'indice vivo e' cambiato durante la copia: rifare"
    # controllo: il D04 si legge per intero e ha le righe del vivo piu' le nuove, senza identificativi doppi
    # (il vivo ha gia' 27 identificativi doppi, misurati il 03/10: non si correggono qui; le pagine nuove non ne aggiungono)
    ids_vivo = [json.loads(l)['id'] for l in gzip.open(vivo, 'rt', encoding='utf-8')]
    n_vivo, doppi_vivo = len(ids_vivo), len(ids_vivo) - len(set(ids_vivo))
    ids = [json.loads(l)['id'] for l in gzip.open(d04, 'rt', encoding='utf-8')]
    nuovi_ids = [x['id'] for x in nuove]
    assert len(ids) == n_vivo + len(nuove) and ids[n_vivo:] == nuovi_ids, 'indice D04 incoerente'
    assert len(set(nuovi_ids)) == len(nuovi_ids) and not (set(nuovi_ids) & set(ids_vivo)), 'pagine nuove con identificativi gia\' usati'
    D04.mkdir(parents=True, exist_ok=True)
    reg = {'data': '2026-10-03', 'codice': 'D04',
           'descrizione': 'D03 piu\' 27 atti dell\'aggiornamento del 19/09 riscaricati (26 file nuovi, 1 identico alla fonte a un '
                          'atto gia\' nel corpus) e 20 atti non PDF estratti',
           'ingressi': {'manifest_supplemento_2026-10-03.jsonl': sha_file(SUPPL), 'registro_non_pdf.json': sha_file(NONPDF),
                        'index/pagine/pagine.jsonl.gz (vivo, copiato)': sha_vivo, 'righe del vivo': n_vivo,
                        'identificativi doppi gia\' nel vivo': doppi_vivo},
           'uscite': {'index/pagine/pagine.d04.jsonl.gz': sha_file(d04), 'index/pagine/pagine.d04.aggiunte.jsonl.gz': sha_file(agg),
                      'pagine_aggiunte': len(nuove), 'righe_d04': len(ids)},
           'documenti': voci}
    (D04/'markdown_d04_registro.json').write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f"scritti {sum(v['esito'] == 'scritto' for v in voci)} Markdown; pagine aggiunte {len(nuove)}; indice D04 {len(ids)} righe")
    return 0


if __name__ == '__main__':
    import giornale  # il giornale delle operazioni: ogni esecuzione, i file, le scritture, gli errori
    giornale.avvia()
    raise SystemExit(main())
