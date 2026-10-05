#!/usr/bin/env python3
"""D04, PASSO 1: SCARICARE I 27 ATTI DELL'AGGIORNAMENTO DEL 19/09 MAI SCARICATI (03/10/2026).

   Misura: training/misure/CORPUS-DIFETTI-2026-10-03.md, punto 1. `fetch_sabin.py` (righe 245-251) trovava il nome del
   file gia' occupato da un atto di luglio dello stesso caso, non scaricava e scriveva in manifest.jsonl una riga
   `http: 0` con l'impronta DEL FILE CHE C'ERA. I 27 sono le righe `http: 0` il cui atto e' diverso da quello di luglio
   e non ha un Markdown (gli altri 243 `http: 0` restano fuori: 237 versioni nuove dello stesso atto, 6 con Markdown).

   Che cosa fa, e solo questo:
     1. ritrova i 27 nel manifest con la regola qui sopra e li confronta con l'elenco del documento di misura
        (se non coincidono, si ferma);
     2. li scarica uno per volta, una richiesta ogni 2 secondi almeno, con un User-Agent che dice chi siamo; al primo
        errore (rete, http diverso da 200, tipo diverso da PDF, lunghezza diversa da Content-Length) SI FERMA: niente
        nuovi tentativi in ciclo;
     3. NOME NUOVO, mai sopra un file esistente: `<nome del manifest senza estensione>__<prime 8 cifre di
        sha256(url)>.pdf`, la regola dei doppioni di `fetch_sabin.py`. Il file si scrive accanto come `.part` in
        creazione esclusiva e poi si collega al nome finale con `os.link`, che fallisce se il nome esiste;
     4. verifica ogni file con prove indipendenti dal manifest (la cui impronta, per questi 27, e' quella sbagliata):
        `%PDF` in testa, PyMuPDF lo apre, pagine > 0, impronta DIVERSA da quella del manifest, da quella del file di
        luglio sul disco (e del suo `.pdf.orig`, per i pae-antimary) e da ogni altra impronta del manifest; e il testo
        delle prime pagine con il numero del processo o le parole del nome del caso (stampato, da guardare a occhio);
     5. scrive le impronte vere in `manifest_supplemento_2026-10-03.jsonl` (una riga per atto, in aggiunta).
        manifest.jsonl NON si tocca.

   Uso:  .venv/bin/python tools/scarica_d04.py            dice cosa scaricherebbe
         .venv/bin/python tools/scarica_d04.py --scarica  scarica (salta gli atti gia' nel supplemento)
"""
import argparse, hashlib, json, os, re, sys, time, unicodedata, urllib.request
from pathlib import Path

QUI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
SUPPL = QUI/'manifest_supplemento_2026-10-03.jsonl'
MISURA = QUI/'training'/'misure'/'CORPUS-DIFETTI-2026-10-03.md'
UA = 'CLIMPACT-research/1.0 (Universita di Bari, progetto CLIMPACT; riparazione del corpus D04, scarico una tantum di 27 atti)'
PAUSA = 2.0


def sha_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def elenco_misura():
    t = MISURA.read_text(encoding='utf-8')
    sez = t.split('### I 24 (punto 1a)')[1].split('### I 20 file non PDF')[0]
    return [l.split('`')[1] for l in sez.splitlines() if l.startswith('| `')]


def i_27():
    """Le righe http 0 il cui atto e' diverso da quello della riga che ha lo stesso percorso e non ha un Markdown."""
    import build_markdown_s05 as S
    con_md, _ = S.documenti_con_markdown()
    M = [json.loads(l) for l in open(QUI/'manifest.jsonl', encoding='utf-8')]
    per_percorso = {}
    for m in M:
        if m.get('path'):
            per_percorso.setdefault(m['path'], []).append(m)
    out = []
    for m in M:
        if m.get('http') != 0 or not m.get('docs'):
            continue
        ids = {d['document_id'] for d in m['docs']}
        altri = [x for x in per_percorso[m['path']] if x is not m and x.get('http') == 200]
        if any(ids & {d['document_id'] for d in x.get('docs') or []} for x in altri):
            continue                      # stesso atto, versione nuova: fuori da D04
        if ids & con_md:
            continue
        out.append((m, altri))
    return out, {m['sha256'] for m in M if m.get('sha256')}


def nome_nuovo(m):
    p = Path(m['path'])
    tag = hashlib.sha256(m['url'].encode()).hexdigest()[:8]
    return p.with_name(f'{p.stem}__{tag}.pdf')


def parole_attese(m):
    """Indizi per il controllo del testo: numeri del processo dal nome del file alla fonte, parole del nome del caso."""
    base = unicodedata.normalize('NFC', m['url'].rsplit('/', 1)[-1])
    num = [x for x in re.findall(r'[\d][\d.\-]{3,}[\d]', base[9:]) if len(re.sub(r'\D', '', x)) >= 4]
    caso = m['docs'][0].get('case_name') or ''
    vuote = {'office', 'public', 'prosecutors', 'federal', 'state', 'others', 'and', 'the', 'climate', 'department',
             'deforestation', 'damage', 'national', 'government', 'union'}
    par = [w for w in re.findall(r'\w{5,}', caso.lower()) if w not in vuote]
    return num, par


def testo_prime_pagine(pdf, n=3):
    import fitz
    d = fitz.open(pdf)
    t = ' '.join(d[i].get_text('text') for i in range(min(n, len(d))))
    pagine = len(d)
    meta = d.metadata or {}
    d.close()
    return t, pagine, meta


def senza_accenti(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn').lower()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--scarica', action='store_true'); a = ap.parse_args()
    voci, tutte_impronte = i_27()
    ids = [m['docs'][0]['document_id'] for m, _ in voci]
    attesi = elenco_misura()
    if sorted(ids) != sorted(attesi):
        print('FERMO: i 27 del manifest non coincidono con l\'elenco della misura', set(ids) ^ set(attesi)); return 1
    print(f'{len(voci)} atti, coincidono con la misura del 03/10')
    fatti = set()
    if SUPPL.exists():
        fatti = {json.loads(l)['url'] for l in open(SUPPL, encoding='utf-8')}
    ultimo = 0.0
    for m, altri in voci:
        did = m['docs'][0]['document_id']
        dest = QUI/nome_nuovo(m)
        if m['url'] in fatti:
            print('gia\' nel supplemento:', did[-40:]); continue
        if not a.scarica:
            print(did[-50:], '->', dest.relative_to(QUI)); continue
        if dest.exists():
            print('FERMO: il nome nuovo esiste gia\'', dest); return 1
        attesa = PAUSA - (time.monotonic() - ultimo)
        if attesa > 0:
            time.sleep(attesa)
        ultimo = time.monotonic()
        req = urllib.request.Request(m['url'], headers={'User-Agent': UA, 'Accept': 'application/pdf'})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                http, tipo, lung = r.status, r.headers.get('Content-Type', ''), r.headers.get('Content-Length')
                dati = r.read()
        except Exception as e:
            print(f'FERMO al primo errore ({did}): {e}'); return 1
        if http != 200 or 'pdf' not in tipo.lower() or (lung and int(lung) != len(dati)) or not dati.startswith(b'%PDF'):
            print(f'FERMO: {did}: http {http}, tipo {tipo}, lunghezza {lung} contro {len(dati)}, testa {dati[:8]!r}'); return 1
        h = hashlib.sha256(dati).hexdigest()
        vecchio = QUI/m['path']
        confronti = {'manifest': m['sha256'], 'disco': sha_file(vecchio) if vecchio.exists() else None}
        orig = vecchio.with_name(vecchio.name + '.orig')
        if orig.exists():
            confronti['disco_orig'] = sha_file(orig)
        if h in confronti.values():
            print(f'FERMO: {did}: l\'impronta scaricata e\' quella del file di luglio ({h[:12]})'); return 1
        if h in tutte_impronte:
            # IDENTICO ALLA FONTE A UN ALTRO ATTO GIA' SCARICATO (03/10: Suncor amicus-brief-18 = amicus-brief-21, _b0d1,
            # stessi byte a due indirizzi del Sabin). Non e' il file di luglio: e' una copia gia' nel corpus. Non si
            # scrive un secondo file (la ricerca la toglierebbe come copia): si registra l'impronta vera e il gemello.
            gem = [json.loads(l) for l in open(QUI/'manifest.jsonl', encoding='utf-8') if h in l]
            gem = [g for g in gem if g.get('sha256') == h and g.get('http') == 200 and g['url'] != m['url']]
            if not gem or not (QUI/gem[0]['path']).exists() or sha_file(QUI/gem[0]['path']) != h:
                print(f'FERMO: {did}: impronta gia\' nel manifest ma senza un gemello scaricato verificabile ({h[:12]})'); return 1
            rec = {'url': m['url'], 'path': gem[0]['path'], 'bytes': len(dati), 'sha256': h, 'status': 'ok', 'http': http,
                   'content_type': tipo, 'content_length': int(lung) if lung else None, 'docs': m['docs'],
                   'ts': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'user_agent': UA,
                   'corregge': {'path': m['path'], 'sha256_falso': m['sha256'], 'ts': m['ts'],
                                'perche': 'riga http 0 di fetch_sabin.py: nome occupato da un atto di luglio, impronta del file sbagliato'},
                   'duplicato_alla_fonte': {'url': gem[0]['url'], 'document_id': gem[0]['docs'][0]['document_id'],
                                            'path': gem[0]['path'], 'nota': 'stessi byte: nessun file nuovo, nessun Markdown nuovo'},
                   'verifica': {'impronte_confrontate': confronti, 'diversa_dal_file_di_luglio': True}}
            with open(SUPPL, 'a', encoding='utf-8') as f:
                f.write(json.dumps(rec, ensure_ascii=False) + '\n')
            print(f'{did[-45:]:45s} {len(dati):>9} B  IDENTICO alla fonte a {gem[0]["docs"][0]["document_id"][-6:]} ({h[:12]})')
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + '.part')
        with open(part, 'xb') as f:
            f.write(dati)
        os.link(part, dest)            # fallisce se il nome esiste: mai sopra un file
        part.unlink()
        assert sha_file(dest) == h
        testo, pagine, meta = testo_prime_pagine(dest)
        num, par = parole_attese(m)
        tn = senza_accenti(re.sub(r'\s+', ' ', testo))
        num_trovati = [x for x in num if re.sub(r'\D', '', x) in re.sub(r'\D', '', tn)]
        par_trovate = [w for w in par if senza_accenti(w) in tn]
        rec = {'url': m['url'], 'path': str(dest.relative_to(QUI)), 'bytes': len(dati), 'sha256': h, 'status': 'ok',
               'http': http, 'content_type': tipo, 'content_length': int(lung) if lung else None, 'docs': m['docs'],
               'ts': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'user_agent': UA,
               'corregge': {'path': m['path'], 'sha256_falso': m['sha256'], 'ts': m['ts'],
                            'perche': 'riga http 0 di fetch_sabin.py: nome occupato da un atto di luglio, impronta del file sbagliato'},
               'verifica': {'pagine': pagine, 'titolo_pdf': meta.get('title', ''), 'impronte_confrontate': confronti,
                            'diversa_da_tutte': True, 'numeri_attesi': num, 'numeri_trovati': num_trovati,
                            'parole_attese': par, 'parole_trovate': par_trovate, 'caratteri_prime_pagine': len(testo.strip()),
                            'inizio_testo': re.sub(r'\s+', ' ', testo)[:400]}}
        with open(SUPPL, 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        print(f'{did[-45:]:45s} {len(dati):>9} B {pagine:>4} pp  num {len(num_trovati)}/{len(num)} parole {len(par_trovate)}/{len(par)}  {h[:12]}')
    return 0


if __name__ == '__main__':
    import giornale  # il giornale delle operazioni: ogni esecuzione, i file, le scritture, gli errori
    giornale.avvia()
    raise SystemExit(main())
