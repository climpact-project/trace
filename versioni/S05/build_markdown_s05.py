#!/usr/bin/env python3
"""IL MARKDOWN DEI DOCUMENTI CHE NE ERANO SENZA (S05, 02/10/2026).

   La misura delle perdite della ricerca per nome (training/misure/PERDITE-RICERCA-NOME.md, punto 3) ha trovato 313
   documenti con il testo in `text/` ma senza Markdown: la ricerca per nome legge solo `markdown/`, quindi non li vede.
   Le cause, misurate qui sul registro dello scarico (`manifest.jsonl`) e non supposte:
     - 277 PDF scaricati con l'aggiornamento del 19/09/2026: i loro metadati stanno solo in
       `aggiornamenti/da-scaricare-ccc-2026-09-19.csv` (alcuni anche in quello del 28/09), mai fusi in `metadata.csv`,
       quindi `build_markdown.py` li salta («senza metadati»). Si scrivono.
     - 1 PDF («sebastião», petition_67a5) con metadati in `metadata.csv`: il suo testo ha solo i segni di pagina
       (nessuna parola estratta), e `build_markdown.py` salta i testi vuoti. Resta fuori anche qui: va passato all'OCR.
     - 27 PDF dello stesso aggiornamento il cui nome, troncato, coincide con quello di un file gia' scaricato a luglio:
       24 sono LO STESSO file (stessa impronta) ricatalogato sotto un altro identificativo, e il suo testo ha gia' un
       Markdown col vecchio identificativo; 3 (pae-antimary, giudizi _612b, _1fbc, _78e1) sono file diversi che hanno
       SOVRASCRITTO il PDF di luglio sul disco, mentre testo e Markdown restano quelli di luglio. Non si scrivono:
       il testo non e' il loro (i 3 vanno riestratti a parte).
     - 8 file non PDF (.docx, .doc, .png) con lo stesso problema di nome: il file di testo che sembra loro e' il testo
       di un PDF dello stesso caso, che ha gia' il suo Markdown. Non si scrivono; vanno estratti a parte.

   Come gli altri: stesso front matter di `build_markdown.front_matter`, stesso percorso (`markdown/<cartella>/<nome>.md`
   come il file di testo), testo intatto. MAI SOVRASCRIVERE: ogni file si apre in creazione esclusiva; se esiste, si
   salta e lo si dice.

   L'indice delle pagine NON si tocca: si scrive accanto `index/pagine/pagine.s05.jsonl.gz` (l'indice vivo piu' le
   pagine nuove, con le regole di `indice_pagine.prepara`) e `pagine.s05.aggiunte.jsonl.gz` (solo le nuove). Lo
   scambio lo decide il PI dopo la revisione.

   Le impronte sha256 di ogni ingresso (testo, file d'origine, CSV dei metadati, indice vivo) e di ogni uscita vanno in
   `training/s05/markdown_s05_registro.json`.

   Uso:  .venv/bin/python tools/build_markdown_s05.py            conta e dice cosa scriverebbe
         .venv/bin/python tools/build_markdown_s05.py --scrivi   scrive i Markdown nuovi e i due indici accanto
"""
import argparse, collections, csv, gzip, hashlib, json, re, shutil, sys, unicodedata
from pathlib import Path

QUI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
import build_markdown as BM          # noqa: E402  stesso front matter dei 16.791 documenti
import build_chunks as BC            # noqa: E402  stessa lettura delle pagine dell'indice

S05 = QUI/'training'/'s05'
PAG = QUI/'index'/'pagine'
AGG = [QUI/'aggiornamenti'/'da-scaricare-ccc-2026-09-28.csv', QUI/'aggiornamenti'/'da-scaricare-ccc-2026-09-21.csv',
       QUI/'aggiornamenti'/'da-scaricare-ccc-2026-09-22.csv', QUI/'aggiornamenti'/'da-scaricare-ccc-2026-09-19.csv']


def sha_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def documenti_con_markdown():
    """document_id dal front matter di ogni Markdown esistente (non dal nome del file: il nome e' troncato)."""
    ids, percorsi = set(), set()
    for p in QUI.joinpath('markdown').rglob('*.md'):
        percorsi.add(unicodedata.normalize('NFC', str(p.relative_to(QUI))))
        with p.open(encoding='utf-8', errors='replace') as f:   # Path.open: il giornale non registra 16.791 letture
            testa = f.read(600)
        m = re.search(r"^document_id: '(.*)'$", testa, re.M)
        if m:
            ids.add(m.group(1).replace("''", "'"))
    return ids, percorsi


def metadati():
    """Document ID -> (riga, fonte). metadata.csv prima; poi i CSV degli aggiornamenti, il piu' recente prima."""
    idx = {}
    for r in csv.DictReader(open(QUI/'metadata.csv', encoding='utf-8')):
        did = (r.get('Document ID') or '').strip()
        if did:
            idx.setdefault(did, []).append((r, 'metadata.csv'))
    for f in AGG:
        if f.exists():
            for r in csv.DictReader(open(f, encoding='utf-8')):
                did = (r.get('Document ID') or '').strip()
                if did:
                    idx.setdefault(did, []).append((r, str(f.relative_to(QUI))))
    return idx


def inventario():
    md_ids, md_percorsi = documenti_con_markdown()
    meta = metadati()
    voci, conti = [], collections.Counter()
    for l in open(QUI/'manifest.jsonl', encoding='utf-8'):
        m = json.loads(l)
        if not m.get('path') or not m.get('docs'):
            continue
        ids = [d['document_id'] for d in m['docs']]
        if any(x in md_ids for x in ids):
            continue
        rel = Path(m['path']).relative_to('documents')
        txt = QUI/'text'/rel.with_suffix('.txt')
        if not txt.exists():
            conti['senza testo'] += 1
            continue
        dest = QUI/'markdown'/rel.with_suffix('.md')
        v = {'document_id': ids[0], 'altri_id': ids[1:], 'origine': m['path'], 'url': m['url'], 'sha256_origine': m.get('sha256', ''),
             'testo': str(txt.relative_to(QUI)), 'markdown': str(dest.relative_to(QUI))}
        if unicodedata.normalize('NFC', v['markdown']) in md_percorsi or dest.exists():
            # il nome troncato coincide con quello di un altro file dello stesso caso (un PDF che ha gia' il suo Markdown)
            v['esito'] = 'collisione: il file di testo e il Markdown sono di un altro documento con lo stesso nome troncato'
            conti['collisione di nome (non scritto)'] += 1
            voci.append(v)
            continue
        cand = [x for i in ids for x in meta.get(i, [])]
        # fra piu' righe vale quella che descrive lo stesso file scaricato (stesso indirizzo), poi metadata.csv, poi la piu' recente
        cand.sort(key=lambda x: (x[0].get('Document Content URL', '') != m['url'], x[1] != 'metadata.csv'))
        if not cand:
            v['esito'] = 'senza metadati in nessun CSV'
            conti['senza metadati'] += 1
            voci.append(v)
            continue
        v['riga'], v['fonte_metadati'] = cand[0]
        v['esito'] = 'da scrivere'
        v['causa'] = ('metadati solo nel CSV dell\'aggiornamento' if v['fonte_metadati'] != 'metadata.csv'
                      else 'metadati presenti (testo da controllare)')
        conti['da scrivere: ' + v['causa']] += 1
        voci.append(v)
    return voci, conti


def pagine_del_file(p):
    """Le pagine di un Markdown, con le stesse regole di `indice_pagine.prepara`."""
    meta, corpo, base = BC.leggi(p)
    marks = BC.pagine(corpo)
    doc = meta.get('document_id') or p.stem
    confini = marks + [(len(corpo), None)]
    out = []
    for (a, num), (b, _) in zip(confini, confini[1:], strict=False):
        t = re.sub(r'[ \t]+', ' ', BC.PAGE_RE.sub(' ', corpo[a:b])).strip()
        if len(t) >= 200:
            out.append({'id': f'{doc}#p{num}', 'doc': doc, 'file': str(p.relative_to(QUI)), 'pagina': num,
                        'da': base + a, 'a': base + b, 'testo': t[:12000]})
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--scrivi', action='store_true'); a = ap.parse_args()
    voci, conti = inventario()
    for k, v in sorted(conti.items()):
        print(f'  {v:>5}  {k}')
    if not a.scrivi:
        print('PROVA: niente scritto (--scrivi per scrivere i Markdown nuovi e gli indici accanto)')
        return 0
    S05.mkdir(parents=True, exist_ok=True)
    scritti, nuove_pagine, fonti_csv = [], [], {}
    for v in voci:
        if v['esito'] != 'da scrivere':
            continue
        txt, dest = QUI/v['testo'], QUI/v['markdown']
        corpo = txt.read_text(encoding='utf-8', errors='replace')
        if not re.sub(r'<!--.*?-->', '', corpo).strip():
            v['esito'] = 'testo vuoto (non scritto)'
            continue
        pagine = len(re.findall(r'<!--\s*page\s+\d+\s*-->', corpo))
        orig = QUI/v['origine']
        testa = BM.front_matter(v['riga'], txt, orig, pagine, v['sha256_origine'])
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(dest, 'x', encoding='utf-8') as f:     # creazione esclusiva: mai sovrascrivere
                f.write(testa + corpo)
        except FileExistsError:
            v['esito'] = 'esiste gia\' (non toccato)'
            continue
        v['esito'] = 'scritto'
        v['sha256_testo'] = sha_file(txt)
        v['sha256_origine_ricalcolato'] = sha_file(orig) if orig.exists() else ''
        v['sha256_markdown'] = sha_file(dest)
        fonti_csv.setdefault(v['fonte_metadati'], sha_file(QUI/v['fonte_metadati']))
        nuove_pagine += pagine_del_file(dest)
        scritti.append(v)
    # gli indici delle pagine ACCANTO a quello vivo: il vivo si copia byte per byte e le pagine nuove si aggiungono come
    # secondo membro gzip (gzip.open li legge di seguito, come un file solo)
    vivo = PAG/'pagine.jsonl.gz'
    sha_vivo = sha_file(vivo)
    agg = PAG/'pagine.s05.aggiunte.jsonl.gz'
    with gzip.open(agg, 'wt', encoding='utf-8') as f:
        for x in nuove_pagine:
            f.write(json.dumps(x, ensure_ascii=False) + '\n')
    s05 = PAG/'pagine.s05.jsonl.gz'
    shutil.copyfile(vivo, s05)
    with open(s05, 'ab') as f, open(agg, 'rb') as g:
        shutil.copyfileobj(g, f)
    assert sha_file(vivo) == sha_vivo, "l'indice vivo e' cambiato durante la copia: rifare"
    registro = {
        'data': '2026-10-02', 'codice': 'S05', 'conti': dict(conti),
        'ingressi': {'metadata': fonti_csv, 'manifest.jsonl': sha_file(QUI/'manifest.jsonl'),
                     'index/pagine/pagine.jsonl.gz (vivo, copiato)': sha_vivo},
        'uscite': {'index/pagine/pagine.s05.jsonl.gz': sha_file(s05), 'index/pagine/pagine.s05.aggiunte.jsonl.gz': sha_file(agg),
                   'pagine_aggiunte': len(nuove_pagine)},
        'documenti': [{k: v.get(k) for k in ('document_id', 'altri_id', 'causa', 'fonte_metadati', 'origine', 'testo', 'markdown',
                                              'sha256_origine', 'sha256_origine_ricalcolato', 'sha256_testo', 'sha256_markdown', 'esito')}
                      for v in voci]}
    (S05/'markdown_s05_registro.json').write_text(json.dumps(registro, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'scritti {len(scritti)} Markdown nuovi; pagine aggiunte {len(nuove_pagine)}')
    print(f'indici: {s05.relative_to(QUI)}, {agg.relative_to(QUI)}; registro: training/s05/markdown_s05_registro.json')
    return 0


if __name__ == '__main__':
    import giornale  # il giornale delle operazioni: ogni esecuzione, i file, le scritture, gli errori
    giornale.avvia()
    raise SystemExit(main())
