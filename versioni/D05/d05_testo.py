#!/usr/bin/env python3
"""D05, PASSI 2 E 3: TESTO CON L'OCR PER PAGINA, MARKDOWN, INDICE DELLE PAGINE (04/10/2026).

   Il difetto (audit del 04/10/2026): `extract_text.py` (righe 33 e 58) decide l'OCR per DOCUMENTO, sulla media dei
   caratteri per pagina (< 20). Una scansione con il solo timbro del deposito su ogni pagina («Case 4:18-cv-03237
   Document 68-1 Filed 10/23/18 Page 16 of 22») supera la media e non va mai all'OCR: 111 atti, 3.403 pagine con
   meno di 200 caratteri, fuori dall'indice delle pagine e quindi dalla ricerca.

   LA REGOLA PER PAGINA (qui, per gli atti nuovi di D05 e per i 111):
     una pagina va all'OCR se il suo testo, con gli spazi ridotti come nell'indice delle pagine, ha meno di
     MIN_CARATTERI = 200 caratteri (la soglia sotto cui l'indice non la prende), oppure se `freni.leggibile` la dice
     illeggibile (la regola di D02 e D04).
     Si SOSTITUISCE solo se: (pagina corta) l'OCR e' leggibile e ha almeno MIN_CARATTERI caratteri e almeno 50 piu'
     della vecchia; (pagina illeggibile) `applica_ocr.da_sostituire`, la regola di D02.
   OCR: lo stesso di D02 (`training/ocr/esegui.sh`): ocrmypdf --force-ocr con tesseract, testo in sidecar, solo le
   pagine scelte (--pages). Lingue dal campo Language(s) del Sabin (sempre con l'inglese).

   CONTROLLO DEL PDF (come D02): il PDF usato deve avere l'impronta `sha256_pdf` del Markdown (o del suo `.orig`) per i
   111; per gli atti nuovi l'impronta della riga del manifest scritta dallo scarico di oggi.

   DOVE SCRIVE (mai sopra un file: creazione esclusiva):
     nuovi    text/ e markdown/ col nome del file scaricato (come build_markdown_s05.py e build_markdown_d04.py);
     111      training/d05/markdown_ocr/<stesso percorso di markdown/>: il Markdown VIVO NON SI TOCCA (la ricerca S07
              gira su markdown/); lo scambio si decide dopo;
     indice   index/pagine/pagine.d05.jsonl.gz = l'indice D04 (pagine.d04.jsonl.gz) senza le pagine dei 111, piu' le
              pagine dei 111 rifatte (dal Markdown in training/d05/markdown_ocr/) e quelle degli atti nuovi;
              index/pagine/pagine.d05.aggiunte.jsonl.gz = solo le pagine nuove o rifatte;
     registro training/d05/markdown_d05_registro.json (impronte di ogni ingresso e uscita, pagine rifatte per atto).

   Uso:  .venv/bin/python tools/d05_testo.py nuovi      [--scrivi] [--paralleli 3]
         .venv/bin/python tools/d05_testo.py scansioni  [--scrivi] [--paralleli 3]
         .venv/bin/python tools/d05_testo.py indice     [--scrivi]
"""
import argparse, gzip, hashlib, json, re, shutil, subprocess, sys, tempfile, threading, time, unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

QUI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools')); sys.path.insert(0, str(QUI))
import build_markdown as BM            # noqa: E402  stesso front matter dei 16.791 documenti
import build_markdown_s05 as S         # noqa: E402  pagine dell'indice, sha
from freni import leggibile            # noqa: E402
from applica_ocr import da_sostituire, quota_cjk   # noqa: E402

D05 = QUI/'training'/'d05'
STAGE = D05/'markdown_ocr'
PAG = QUI/'index'/'pagine'
REG = D05/'markdown_d05_registro.json'
DUMP = QUI/'dumps'/'CCC-whole_data_dump-2026-10-04.zip'
SCANSIONI = D05/'scansioni_111.json'
PAGE_MARK = "\n\n<!-- page {n} -->\n\n"     # come extract_text.py
PAGE_RE = re.compile(r'<!--\s*page\s+(\d+)\s*-->')
MIN_CARATTERI = 200                          # come l'indice delle pagine (build_markdown_s05.pagine_del_file)
DATA_SCARICO = '2026-10-04'
sha_file = S.sha_file
LINGUE = {'english': 'eng', 'spanish': 'spa', 'portuguese': 'por', 'french': 'fra', 'german': 'deu', 'italian': 'ita',
          'dutch': 'nld', 'korean': 'kor', 'japanese': 'jpn', 'chinese': 'chi_sim+chi_tra', 'russian': 'rus',
          'polish': 'pol', 'swedish': 'swe', 'norwegian': 'nor', 'danish': 'dan', 'finnish': 'fin', 'czech': 'ces',
          'turkish': 'tur', 'ukrainian': 'ukr', 'indonesian': 'ind', 'hebrew': 'heb', 'arabic': 'ara', 'greek': 'ell',
          'romanian': 'ron', 'hungarian': 'hun', 'thai': 'tha', 'vietnamese': 'vie', 'catalan': 'cat',
          'estonian': 'est', 'croatian': 'hrv', 'slovak': 'slk', 'slovenian': 'slv', 'bulgarian': 'bul',
          'lithuanian': 'lit', 'latvian': 'lav', 'icelandic': 'isl', 'filipino': 'fil', 'malay': 'msa',
          'hindi': 'hin', 'nepali': 'nep', 'bengali': 'ben', 'persian': 'fas', 'urdu': 'urd', 'serbian': 'srp'}
_lock = threading.Lock()


GEO = {'south korea': 'kor', 'korea': 'kor', 'japan': 'jpn', 'taiwan': 'chi_tra', 'china': 'chi_sim', 'brazil': 'por',
       'portugal': 'por', 'mexico': 'spa', 'argentina': 'spa', 'colombia': 'spa', 'chile': 'spa', 'peru': 'spa',
       'spain': 'spa', 'ecuador': 'spa', 'france': 'fra', 'belgium': 'fra', 'germany': 'deu', 'austria': 'deu',
       'italy': 'ita', 'netherlands': 'nld', 'indonesia': 'ind', 'turkey': 'tur', 'russia': 'rus', 'poland': 'pol'}


def lingue_tess(campo, geografie=''):
    """Lingue di tesseract dal campo Language(s); se e' vuoto, dalla prima geografia (04/10/2026: la decisione coreana
    sulla politica del carbone dell'NPS, campo vuoto, usciva dall'OCR inglese senza una pagina leggibile)."""
    out = []
    if not (campo or '').strip():
        for g in re.split(r';', geografie or ''):
            k = GEO.get(g.strip().lower())
            if k:
                out.append(k)
                break
    for x in re.split(r'[;,]', campo or ''):
        k = LINGUE.get(x.strip().lower())
        if k and k not in out:
            out.append(k)
    if 'eng' not in out:
        out.append('eng')
    return '+'.join(out)


def compatta(t):
    return re.sub(r'\s+', ' ', t or '').strip()


def da_ocr(t):
    return len(compatta(t)) < MIN_CARATTERI or not leggibile(t)[0]


def sostituire(vecchia, nuova, cjk):
    if len(compatta(vecchia)) < MIN_CARATTERI:
        return (leggibile(nuova)[0] and len(compatta(nuova)) >= MIN_CARATTERI
                and len(compatta(nuova)) >= len(compatta(vecchia)) + 50)
    return da_sostituire(vecchia, nuova, cjk)


def ocr_pagine(pdf, pagine, lingue, log):
    """{numero di pagina: testo} con ocrmypdf --force-ocr --pages, testo dal sidecar (pagine separate da \\f; le
    pagine saltate sono un segnaposto «[OCR skipped on page(s) a-b]»)."""
    if not pagine:
        return {}
    with tempfile.TemporaryDirectory(dir=str(D05)) as tmp:
        side = Path(tmp)/'sidecar.txt'
        cmd = ['ocrmypdf', '--force-ocr', '-l', lingue, '--pages', ','.join(map(str, pagine)), '--sidecar', str(side),
               '--output-type', 'none', '--jobs', '2', '--invalidate-digital-signatures', str(pdf), '-']
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        Path(log).write_text(' '.join(cmd) + '\n\n' + r.stderr[-20000:], encoding='utf-8')
        if r.returncode != 0 or not side.exists():
            raise RuntimeError(f'ocrmypdf {r.returncode}: {r.stderr[-400:]}')
        pezzi = side.read_text(encoding='utf-8', errors='replace').split('\f')
    out, n = {}, 1
    for p in pezzi:
        m = re.fullmatch(r'\s*\[OCR skipped on page\(s\) (\d+)(?:-(\d+))?\]\s*', p)
        if m:
            n = int(m.group(2) or m.group(1)) + 1
            continue
        if n in pagine:
            out[n] = p.strip()
        n += 1
    return out


def rifai_pagine(pdf, testi, lingue, cjk, log):
    """testi: {n: testo vecchio}. Ritorna (testi nuovi, pagine mandate all'OCR, pagine sostituite)."""
    scelte = sorted(n for n, t in testi.items() if da_ocr(t))
    ocr = ocr_pagine(pdf, scelte, lingue, log)
    nuovi, sost = dict(testi), []
    for n in scelte:
        if n in ocr and sostituire(testi[n], ocr[n], cjk):
            nuovi[n] = ocr[n] + '\n'
            sost.append(n)
    return nuovi, scelte, sost


# ── righe del dump ────────────────────────────────────────────────────────────────────────────────────────────────
def righe_dump():
    import check_updates
    idx = {}
    for r in check_updates.read_dump(DUMP)[0]:
        did = (r.get('Document ID') or '').strip()
        if did:
            idx.setdefault(did, []).append(r)
    return idx


def riga_per(idx, did, url):
    c = sorted(idx.get(did, []), key=lambda r: unicodedata.normalize('NFC', r.get('Document Content URL', '')).strip() != url)
    return c[0] if c else None


# ── nuovi ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def scaricati_oggi():
    out = []
    for l in open(QUI/'manifest.jsonl', encoding='utf-8'):
        r = json.loads(l)
        if r.get('ts', '').startswith(DATA_SCARICO) and r.get('status') == 'ok' and r.get('http') == 200:
            out.append(r)
    return out


def con_markdown():
    ids, perc = S.documenti_con_markdown()
    return ids, perc


def piano_nuovi():
    """Una voce per ogni riga scaricata oggi. gruppo: nuovo (atto senza Markdown, byte nuovi), stessi_byte (file gia'
    nel corpus), versione_nuova (atto che ha gia' un Markdown, byte nuovi: l'URL e' cambiata alla fonte)."""
    md_ids, _ = con_markdown()
    # i Markdown scritti da un giro precedente di questo passo non fanno di un atto nuovo una «versione nuova»
    # (04/10/2026: il secondo giro li ha presi per versioni e li ha riscritti in versioni_nuove/, poi tolti)
    md_ids -= {v['document_id'] for v in registro().get('nuovi', []) if v.get('gruppo') == 'nuovo'}
    voci = []
    for r in scaricati_oggi():
        ids = [d['document_id'] for d in r['docs']]
        senza = [i for i in ids if i not in md_ids]
        v = {'url': r['url'], 'origine': r['path'], 'sha256_origine': r['sha256'], 'document_ids': ids}
        if r.get('stessi_byte_di'):
            v.update({'gruppo': 'stessi_byte', 'esito': f"non scritto: stessi byte di {r['stessi_byte_di']}"})
        elif senza:
            v.update({'gruppo': 'nuovo', 'document_id': senza[0], 'altri_id': [i for i in ids if i != senza[0]]})
        else:
            v.update({'gruppo': 'versione_nuova', 'document_id': ids[0], 'altri_id': ids[1:]})
        voci.append(v)
    return voci


def testo_pdf(pdf, lingue, cjk_campo, log):
    import fitz
    d = fitz.open(pdf)
    vecchi = {i + 1: p.get_text('text') for i, p in enumerate(d)}
    d.close()
    cjk = cjk_campo or any(quota_cjk(t) > 0.2 for t in vecchi.values())
    nuovi, scelte, sost = rifai_pagine(pdf, vecchi, lingue, cjk, log)
    testo = ''.join(PAGE_MARK.format(n=n) + nuovi[n] for n in sorted(nuovi))
    return testo, len(vecchi), scelte, sost


def fai_nuovo(v, idx, scrivi):
    orig = QUI/v['origine']
    if sha_file(orig) != v['sha256_origine']:
        v['esito'] = 'non scritto: impronta del file diversa dal manifest'; return v
    rel = Path(v['origine']).relative_to('documents')
    txt, md = QUI/'text'/rel.with_suffix('.txt'), QUI/'markdown'/rel.with_suffix('.md')
    if v['gruppo'] == 'versione_nuova':
        md = STAGE.parent/'versioni_nuove'/rel.with_suffix('.md')
        txt = STAGE.parent/'versioni_nuove'/'text'/rel.with_suffix('.txt')
    v.update({'testo': str(txt.relative_to(QUI)), 'markdown': str(md.relative_to(QUI))})
    riga = riga_per(idx, v['document_id'], v['url'])
    if riga is None:
        v['esito'] = 'non scritto: atto assente dal dump del 04/10'; return v
    if txt.exists() or md.exists():
        v['esito'] = "esiste gia' (non toccato)"; return v
    if not scrivi:
        v['esito'] = 'da scrivere'; return v
    lingue = lingue_tess(riga.get('Language(s)', ''), riga.get('Geographies', ''))
    cjk = bool(re.search(r'kor|jpn|chi', lingue))
    log = D05/'ocr_log'/f"{v['document_id'][:150]}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    if orig.suffix.lower() == '.pdf':
        testo, n, scelte, sost = testo_pdf(orig, lingue, cjk, log)
        metodo = 'testo del PDF (PyMuPDF)' + (f'; OCR ocrmypdf/tesseract ({lingue}) per pagina: {len(scelte)} pagine provate, '
                                             f'{len(sost)} sostituite' if scelte else '')
    else:
        import estrai_non_pdf as E
        with tempfile.TemporaryDirectory(dir=str(D05)) as tmp:
            testo, n, metodo, _ = E.converti(orig, Path(tmp))
        scelte, sost = [], []
    if not re.sub(r'<!--.*?-->', '', testo).strip():
        v.update({'esito': 'non scritto: nessun testo, neanche con l\'OCR', 'pagine': n, 'pagine_ocr_provate': scelte}); return v
    with _lock:
        for p in (txt, md):
            p.parent.mkdir(parents=True, exist_ok=True)
        with open(txt, 'x', encoding='utf-8') as f:
            f.write(testo)
        with open(md, 'x', encoding='utf-8') as f:
            f.write(BM.front_matter(riga, txt, orig, n, v['sha256_origine']) + testo)
    legg = [leggibile(t)[0] for t in PAGE_RE.split(testo)[2::2]]
    v.update({'esito': 'scritto', 'metodo': metodo, 'lingue_ocr': lingue, 'pagine': n, 'pagine_ocr_provate': scelte,
              'pagine_ocr': sost, 'pagine_leggibili': sum(legg),
              'parole': len(re.findall(r'\w+', re.sub(r'<!--.*?-->', '', testo))),
              'sha256_testo': sha_file(txt), 'sha256_markdown': sha_file(md)})
    return v


# ── i 111 ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def fronte(md):
    t = md.read_text(encoding='utf-8')
    g = lambda k: (re.search(rf"^{k}: '?(.*?)'?$", t[:8000], re.M) or [None, ''])[1].replace("''", "'")
    return t, g


def fai_scansione(x, scrivi):
    md = QUI/x['markdown']
    t, g = fronte(md)
    v = {'document_id': x['doc'], 'markdown_vivo': x['markdown'], 'sha256_markdown_vivo': sha_file(md)}
    pdf = QUI/g('file_pdf')
    sha = g('sha256_pdf')
    cands = [p for p in (pdf, pdf.with_name(pdf.name + '.orig')) if p.exists() and sha_file(p) == sha]
    if not sha or not cands:
        v['esito'] = 'saltato: nessun PDF con l\'impronta sha256_pdf del Markdown'; return v
    pdf = cands[0]
    v.update({'pdf': str(pdf.relative_to(QUI)), 'sha256_pdf': sha})
    fine_fm = t.index('\n---', 3) + 4
    corpo = t[fine_fm:]
    marks = [(m.start(), m.end(), int(m.group(1))) for m in PAGE_RE.finditer(corpo)]
    testi = {n: corpo[e:(marks[i + 1][0] if i + 1 < len(marks) else len(corpo))] for i, (s, e, n) in enumerate(marks)}
    import fitz
    d = fitz.open(pdf); npdf = len(d); d.close()
    if npdf != len(testi):
        v['esito'] = f'saltato: pagine del PDF {npdf} contro {len(testi)} del Markdown'; return v
    dest = STAGE/Path(x['markdown']).relative_to('markdown')
    v['markdown'] = str(dest.relative_to(QUI))
    scelte = sorted(n for n, tt in testi.items() if da_ocr(tt))
    if dest.exists():
        # gia' scritto da un giro precedente (04/10/2026: il primo giro e' caduto sul salvataggio del registro dopo aver
        # scritto 110 Markdown): la voce si ricostruisce dal file, confrontando pagina per pagina col Markdown vivo
        t2, g2 = fronte(dest)
        corpo2 = t2[t2.index('\n---', 3) + 4:]
        m2 = [(m.start(), m.end(), int(m.group(1))) for m in PAGE_RE.finditer(corpo2)]
        testi2 = {n: corpo2[e:(m2[i + 1][0] if i + 1 < len(m2) else len(corpo2))] for i, (s, e, n) in enumerate(m2)}
        if t2[:fine_fm] != t[:fine_fm] or sorted(testi2) != sorted(testi):
            v['esito'] = "esiste gia' ma non corrisponde al Markdown vivo (non toccato)"; return v
        v.update({'esito': 'scritto', 'ricostruita_dal_file': True, 'lingue_ocr': lingue_tess(g('lingue')),
                  'pagine': len(testi), 'pagine_da_ocr': len(scelte), 'pagine_ocr_provate': scelte,
                  'pagine_ocr': [n for n in sorted(testi) if compatta(testi[n]) != compatta(testi2[n])],
                  'sha256_markdown': sha_file(dest)})
        return v
    v['pagine'] = len(testi); v['pagine_da_ocr'] = len(scelte)
    if not scrivi:
        v['esito'] = 'da fare'; return v
    lingue = lingue_tess(g('lingue'))
    cjk = bool(re.search(r'kor|jpn|chi', lingue))
    log = D05/'ocr_log'/f"{x['doc'][:150]}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    nuovi, scelte, sost = rifai_pagine(pdf, testi, lingue, cjk, log)
    pezzi, ultimo = [], 0
    for i, (s, e, n) in enumerate(marks):
        fine = marks[i + 1][0] if i + 1 < len(marks) else len(corpo)
        if n in sost:
            pezzi += [corpo[ultimo:e], '\n\n' + nuovi[n].strip() + ('\n\n' if i + 1 < len(marks) else '\n')]
            ultimo = fine
    pezzi.append(corpo[ultimo:])
    nuovo = t[:fine_fm] + ''.join(pezzi)
    with _lock:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, 'x', encoding='utf-8') as f:
            f.write(nuovo)
    v.update({'esito': 'scritto', 'lingue_ocr': lingue, 'pagine_ocr_provate': scelte, 'pagine_ocr': sost,
              'sha256_markdown': sha_file(dest)})
    return v


def scansioni_elenco():
    return json.load(open(SCANSIONI, encoding='utf-8'))['documenti']


# ── esecuzione ────────────────────────────────────────────────────────────────────────────────────────────────────
def registro():
    return json.load(open(REG, encoding='utf-8')) if REG.exists() else {'data': '2026-10-04', 'codice': 'D05'}


def salva_registro(reg, chiavi=None):
    """Riscrive il registro rileggendo quello sul disco: si aggiornano solo le `chiavi` di questo passo, cosi' due
    passi in parallelo (nuovi e scansioni) non si cancellano a vicenda."""
    disco = registro()
    for k in (chiavi or reg.keys()):
        if k in reg:
            disco[k] = reg[k]
    tmp = REG.with_suffix('.json.nuovo')
    tmp.write_text(json.dumps(disco, ensure_ascii=False, indent=1), encoding='utf-8')
    tmp.replace(REG)


def esegui(voci, f, paralleli, nome):
    fatte, t0 = [], time.time()
    def uno(v):
        try:
            r = f(v)
        except Exception as e:  # un atto che fallisce non ferma gli altri: si scrive l'errore
            r = dict(v); r['esito'] = f'errore: {type(e).__name__}: {str(e)[:300]}'
            r.setdefault('document_id', v.get('doc') or v.get('document_id') or '')
        with _lock:
            fatte.append(r)
            print(f"[{nome} {len(fatte)}/{len(voci)} {time.time()-t0:.0f}s] {str(r.get('document_id'))[-50:]}: "
                  f"{r['esito'][:60]} ocr {len(r.get('pagine_ocr') or [])}/{len(r.get('pagine_ocr_provate') or [])}", flush=True)
        return r
    with ThreadPoolExecutor(max_workers=paralleli) as pool:
        return list(pool.map(uno, voci))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('passo', choices=['nuovi', 'scansioni', 'indice'])
    ap.add_argument('--scrivi', action='store_true'); ap.add_argument('--paralleli', type=int, default=3)
    a = ap.parse_args()
    D05.mkdir(parents=True, exist_ok=True)
    reg = registro()
    if a.passo == 'nuovi':
        idx = righe_dump()
        voci = piano_nuovi()
        fare = [v for v in voci if v['gruppo'] != 'stessi_byte']
        fatte = esegui(fare, lambda v: fai_nuovo(v, idx, a.scrivi), a.paralleli, 'nuovi')
        tutte = fatte + [v for v in voci if v['gruppo'] == 'stessi_byte']
        if a.scrivi:
            # un secondo giro (dopo un errore) non cancella le voci gia' scritte: quelle restano come erano
            prima = {v['url']: v for v in reg.get('nuovi', []) if v.get('esito') == 'scritto'}
            tutte = [prima.get(v['url'], v) if v.get('esito', '').startswith('esiste') else v for v in tutte]
            reg['nuovi'] = sorted(tutte, key=lambda v: v['url'])
            reg['ingressi_nuovi'] = {'manifest.jsonl': sha_file(QUI/'manifest.jsonl'), DUMP.name: sha_file(DUMP)}
            salva_registro(reg, ['nuovi', 'ingressi_nuovi'])
        import collections
        print(collections.Counter((v['gruppo'], v['esito'][:40]) for v in tutte))
    elif a.passo == 'scansioni':
        voci = scansioni_elenco()
        fatte = esegui(voci, lambda x: fai_scansione(x, a.scrivi), a.paralleli, 'scansioni')
        if a.scrivi:
            reg['scansioni'] = sorted(fatte, key=lambda v: v.get('document_id') or '')
            reg['ingressi_scansioni'] = {SCANSIONI.name: sha_file(SCANSIONI)}
            salva_registro(reg, ['scansioni', 'ingressi_scansioni'])
        import collections
        print(collections.Counter(v['esito'][:50] for v in fatte),
              'pagine sostituite', sum(len(v.get('pagine_ocr') or []) for v in fatte))
    else:
        return indice(reg, a.scrivi)
    return 0


def indice(reg, scrivi):
    base = PAG/'pagine.d04.jsonl.gz'
    sha_base = sha_file(base)
    rifatti = {v['document_id']: v for v in reg.get('scansioni', []) if v['esito'] == 'scritto'}
    nuovi = [v for v in reg.get('nuovi', []) if v['esito'] == 'scritto' and v['gruppo'] == 'nuovo']
    versioni = [v for v in reg.get('nuovi', []) if v['esito'] == 'scritto' and v['gruppo'] == 'versione_nuova']
    aggiunte = []
    for v in rifatti.values():
        pp = S.pagine_del_file(QUI/v['markdown'])
        for p in pp:
            if p['pagina'] in v['pagine_ocr']:
                p['ocr'] = '2026-10-04'
        v['pagine_nell_indice'] = len(pp)
        aggiunte += pp
    ids_nuovi = set()
    for v in nuovi:
        pp = S.pagine_del_file(QUI/v['markdown'])
        for p in pp:
            if p['pagina'] in (v.get('pagine_ocr') or []):
                p['ocr'] = '2026-10-04'
        v['pagine_nell_indice'] = len(pp)
        aggiunte += pp
        ids_nuovi.add(v['document_id'])
    for v in versioni:   # versione nuova di un atto gia' nel corpus: pagine con un identificativo proprio, mai sopra quelle vecchie
        tag = v['sha256_origine'][:8]
        pp = S.pagine_del_file(QUI/v['markdown'])
        for p in pp:
            p['id'] = f"{p['doc']}@{tag}#p{p['pagina']}"
            p['versione_di'] = p['doc']
            if p['pagina'] in (v.get('pagine_ocr') or []):
                p['ocr'] = '2026-10-04'
        v['pagine_nell_indice'] = len(pp)
        aggiunte += pp
    print('pagine aggiunte o rifatte', len(aggiunte), '| atti rifatti', len(rifatti), '| nuovi', len(nuovi), '| versioni nuove', len(versioni))
    if not scrivi:
        return 0
    out, agg = PAG/'pagine.d05.jsonl.gz', PAG/'pagine.d05.aggiunte.jsonl.gz'
    for p in (out, agg):
        if p.exists():
            print(f"FERMO: {p.name} esiste gia'"); return 1
    tolte, tenute, ids = 0, 0, set()
    with gzip.open(base, 'rt', encoding='utf-8') as f, gzip.open(out, 'xt', encoding='utf-8') as g:
        for l in f:
            x = json.loads(l)
            if x['doc'] in rifatti:
                tolte += 1; continue
            if x['doc'] in ids_nuovi:
                raise SystemExit(f"FERMO: l'atto nuovo {x['doc']} ha gia' pagine nell'indice D04")
            g.write(l if l.endswith('\n') else l + '\n'); tenute += 1; ids.add(x['id'])
        for x in aggiunte:
            g.write(json.dumps(x, ensure_ascii=False) + '\n')
    with gzip.open(agg, 'xt', encoding='utf-8') as g:
        for x in aggiunte:
            g.write(json.dumps(x, ensure_ascii=False) + '\n')
    assert sha_file(base) == sha_base, "l'indice D04 e' cambiato durante la copia"
    nuovi_ids = [x['id'] for x in aggiunte]
    assert len(set(nuovi_ids)) == len(nuovi_ids), 'pagine aggiunte con identificativi doppi'
    doppi = set(nuovi_ids) & ids
    assert not doppi, f'pagine aggiunte con identificativi gia\' nell\'indice: {list(doppi)[:5]}'
    n = sum(1 for _ in gzip.open(out, 'rt', encoding='utf-8'))
    assert n == tenute + len(aggiunte)
    reg['indice'] = {'base': {'index/pagine/pagine.d04.jsonl.gz': sha_base},
                     'uscite': {'index/pagine/pagine.d05.jsonl.gz': sha_file(out),
                                'index/pagine/pagine.d05.aggiunte.jsonl.gz': sha_file(agg)},
                     'righe_tolte_dei_111': tolte, 'righe_tenute': tenute, 'pagine_aggiunte_o_rifatte': len(aggiunte),
                     'righe_d05': n}
    salva_registro(reg, ['indice'])
    print(json.dumps(reg['indice'], indent=1))
    return 0


if __name__ == '__main__':
    import giornale  # il giornale delle operazioni: ogni esecuzione, i file, le scritture, gli errori
    giornale.avvia()
    raise SystemExit(main())
