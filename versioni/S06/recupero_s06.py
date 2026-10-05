"""S06, LE COPIE DI S05 IN UN ATTO DI UN'ALTRA CAUSA, RECUPERATE (03/10/2026, col si' del PI: «ok va bene»).

   Da dove. La ricerca per nome S05 (`cerca_s05.py`) butta un frammento come «copia di un altro frammento» quando
   i suoi primi 400 caratteri (spazi uniti, minuscole) sono uguali a quelli di un frammento gia' visto IN TUTTO IL
   CORPUS, anche in un atto di un'altra causa. La misura del 03/10 (`training/misure/DEDUP-FRA-ATTI.md`) conta 438
   copie buttate, 267 in un atto di un'altra causa: 265 righe distinte, perche' a Neubauer due brani tornano due
   volte nello stesso atto e la seconda volta resta una copia (come nella deduplica per atto,
   `cerca_s05_per_atto.deduplica`). Il PI ha deciso di recuperare quelle in un'altra causa, con lo stesso
   trattamento delle altre righe (cinque letture, R10, R11, freni).

   Lo stesso documento due volte. Su 20 coppie lette nella misura, 13 erano lo stesso atto depositato due volte nel
   corpus di Sabin (due schede della stessa causa, un'ordinanza registrata sotto ogni ricorso): quelle non sono una
   ripresa a se'. Si tolgono solo dove si riconoscono con certezza, confrontando l'atto della copia con l'atto della
   riga tenuta e con gli atti delle copie gia' prese dello stesso testo:
     - stesso PDF: la stessa impronta `sha256_pdf` nell'intestazione del Markdown;
     - stesso testo: la stessa impronta SHA-256 del testo intero (dopo l'intestazione, spazi uniti).
   Provati e NON usati (misura del 03/10 sulle 265): la stessa pagina della citazione la hanno anche atti diversi,
   per esempio i ricorsi paralleli di DUH contro Mercedes e contro BMW o le due istanze di Lemme contro la Baviera
   (14 righe con la stessa pagina e un numero di pagine diverso); lo stesso titolo con lo stesso numero di pagine non
   capita mai (i titoli portano il nome della causa, che e' diversa per definizione).

   Fasi (le chiama tools/ciclo_s06.sh; senza --scrivi niente si scrive in banca dati):
     righe     le copie di S05 in un'altra causa, ricalcolate dai CSV della ricerca e confrontate con la misura;
               tolte quelle dello stesso documento -> training/s06/righe_s06.jsonl, escluse_stesso_documento.jsonl,
               conti.json
     contesti  le righe per i lettori, con classifica_lessicali.prepara (dalla banca dati se le righe ci sono,
               altrimenti dai documenti che si scriverebbe) -> training/s06/lessicali_<caso>_righe_s06.jsonl
     coppie    le coppie per T01: brano delle righe e pagine attorno (10 prima, 10 dopo) ancora senza punteggio
               -> training/s06/s06_coppie.jsonl (i punteggi: tools/punteggi_t01_s06.py)
     scrivi    le righe in corpus_rows FUORI DALLE CODE: chi le avra' sta in `assegnato_a_in_attesa`, non in
               `assegnato_a` (come tools/attesa_s05.py); codici dopo il piu' alto del caso
     aggiungi  le righe di S06 nei file dei lettori (lessicali_<caso>_righe.jsonl), con la copia di prima accanto
     rimetti   le righe di S06 con tutte le proposte tornano nelle code; le altre restano fuori, elencate
     verifica  un file di proposte calcolate a secco (--salva dei caricatori) tocca solo righe di S06?

   Uso:  .venv/bin/python tools/recupero_s06.py righe|contesti|coppie|scrivi|aggiungi|rimetti|verifica [--scrivi]
"""
import argparse
import collections
import csv
import gzip
import hashlib
import json
import pathlib
import random
import re
import shutil
import sys

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
S6 = QUI/'training'/'s06'
T = QUI/'training'
P = T/'principi'
DATA = '2026-10-03'
ESTRAZIONE = 'S06'
CASI = ['urgenda', 'neubauer', 'future-generations', 'klimaseniorinnen', 'cig-parere-clima', 'idh-oc-32-25']
PREFISSI = {'urgenda': 'URG', 'neubauer': 'NEU', 'future-generations': 'FGC', 'klimaseniorinnen': 'KLS',
            'cig-parere-clima': 'ICJ', 'idh-oc-32-25': 'IAC'}
MISURA = T/'misure'/'dedup_fra_atti_2026-10-03.json'
COPIA = 'copia di un altro frammento'
MOTIVO = "copia di una citazione S05 in un atto di un'altra causa, recuperata (S06, 03/10/2026)"
FINESTRA = 10          # pagine prima e dopo la citazione con un punteggio T01 (ripresa_punteggi.PRIMA, DOPO)
INIZIO, FINE = '[[INIZIO DEL BRANO SEGNALATO]]', '[[FINE DEL BRANO SEGNALATO]]'


def leggi_jsonl(f):
    with open(f, encoding='utf-8') as h:
        return [json.loads(riga) for riga in h if riga.strip()]


def scrivi_jsonl(f, xs):
    with open(f, 'w', encoding='utf-8') as h:
        for x in xs:
            h.write(json.dumps(x, ensure_ascii=False, default=str) + '\n')


def leggi_json(f):
    with open(f, encoding='utf-8') as h:
        return json.load(h)


def scrivi_json(f, x):
    with open(f, 'w', encoding='utf-8') as h:
        json.dump(x, h, ensure_ascii=False, indent=1, default=str)


def csv_s05(caso, scarti=False):
    f = QUI/'index'/f"nomi_{caso}_2026-10-02-S05{'.SCARTI' if scarti else ''}.csv"
    if not f.exists():
        return []
    with open(f, encoding='utf-8') as h:
        return list(csv.DictReader(h))


def chiave_testo(r):
    """la chiave della deduplica di S03/S05: i primi 400 caratteri del frammento, spazi uniti e minuscole"""
    return re.sub(r'\s+', ' ', r['citazione_testuale']).strip().lower()[:400]


def id_di(caso, r):
    from pubblica import id_riga
    return id_riga(caso, r['document_id'], int(r['char_start']))


# ── le copie in un'altra causa ─────────────────────────────────────────────────────────────────────────────

def copie_altra_causa(tenute, scarti):
    """Le copie buttate dalla deduplica di S05 il cui frammento tenuto (stesso testo) sta in un'altra causa
    (`case_id` diverso). Una sola riga per atto e testo: la seconda volta nello stesso atto resta una copia, come
    nella deduplica per atto. Ogni copia porta la riga tenuta in `primo`. Le copie senza riga tenuta si contano."""
    primo = {}
    for r in tenute:
        primo.setdefault(chiave_testo(r), r)
    out, viste, senza = [], set(), 0
    for r in sorted((r for r in scarti if r.get('motivo_scarto') == COPIA),
                    key=lambda r: (r['document_id'], int(r['char_start']))):
        k = chiave_testo(r)
        p = primo.get(k)
        if p is None:
            senza += 1
            continue
        if p['case_id'] == r['case_id'] or (r['document_id'], k) in viste:
            continue
        viste.add((r['document_id'], k))
        out.append({'riga': r, 'primo': p})
    return out, senza


def impronte(file, cache=None):
    """le impronte di un atto: `pdf` (sha256_pdf dell'intestazione del Markdown, '' se manca) e `testo` (SHA-256
    del testo dopo l'intestazione, spazi uniti)"""
    if cache is not None and file in cache:
        return cache[file]
    from cerca import front_matter
    testo = (QUI/file).read_text(encoding='utf-8', errors='replace')
    meta, inizio = front_matter(testo)
    x = {'pdf': meta.get('sha256_pdf', ''),
         'testo': hashlib.sha256(' '.join(testo[inizio:].split()).encode('utf-8')).hexdigest()}
    if cache is not None:
        cache[file] = x
    return x


def stesso_documento(a, b):
    """perche' due atti sono lo stesso documento ('' se non lo sono, o se non lo si puo' dire con certezza)"""
    if a['pdf'] and a['pdf'] == b['pdf']:
        return 'stesso PDF (sha256_pdf)'
    if a['testo'] == b['testo']:
        return 'stesso testo'
    return ''


def separa(copie, impronta):
    """(da recuperare, escluse): una copia si esclude se il suo atto e' lo stesso documento dell'atto della riga
    tenuta o dell'atto di una copia gia' presa dello stesso testo. `impronta(file)` da' le impronte di un atto."""
    prese = collections.defaultdict(list)       # testo -> atti gia' rappresentati (il primo, poi le copie prese)
    tenere, escluse = [], []
    for c in copie:
        r, p = c['riga'], c['primo']
        k = chiave_testo(r)
        if not prese[k]:
            prese[k].append((p['document_id'], impronta(p['file'])))
        mie = impronta(r['file'])
        uguale = next(((d, perche) for d, imp in prese[k] for perche in [stesso_documento(mie, imp)] if perche),
                      None)
        if uguale:
            escluse.append({**c, 'uguale_a': uguale[0], 'perche': uguale[1]})
        else:
            tenere.append(c)
            prese[k].append((r['document_id'], mie))
    return tenere, escluse


def gia_in_banca(ids):
    """gli id gia' in corpus_rows con una provenienza che non e' S06 (una riga di S06 gia' scritta va bene: e' la
    ripresa dopo una scrittura a meta')"""
    from google.cloud import firestore
    db = firestore.Client(project='climpact-drp')
    out = []
    for i in ids:
        d = db.collection('corpus_rows').document(i).get()
        if d.exists and ((d.to_dict() or {}).get('provenienza') or {}).get('estrazione') != ESTRAZIONE:
            out.append(i)
    return out


def fase_righe(a):
    S6.mkdir(parents=True, exist_ok=True)
    misura = leggi_json(MISURA)['casi']
    conti, tutte, tutte_escluse = {}, [], []
    cache = {}
    for caso in CASI:
        copie, senza = copie_altra_causa(csv_s05(caso), csv_s05(caso, scarti=True))
        attese = {x['id'] for x in misura.get(caso, {}).get('righe', []) if x['causa_diversa']}
        mie = {id_di(caso, c['riga']) for c in copie}
        if mie != attese:
            raise SystemExit(f"{caso}: le copie in un'altra causa ricalcolate ({len(mie)}) non sono quelle della "
                             f'misura ({len(attese)}): {sorted(mie ^ attese)[:5]}')
        tenere, escluse = separa(copie, lambda f: impronte(f, cache))
        tutte += [{'caso': caso, 'id': id_di(caso, c['riga']), 'riga': c['riga'], 'primo_id': id_di(caso, c['primo']),
                   'primo_case_id': c['primo']['case_id']} for c in tenere]
        tutte_escluse += [{'caso': caso, 'id': id_di(caso, c['riga']), 'document_id': c['riga']['document_id'],
                           'case_id': c['riga']['case_id'], 'primo_id': id_di(caso, c['primo']),
                           'uguale_a_documento': c['uguale_a'], 'perche': c['perche']} for c in escluse]
        conti[caso] = {'copie_in_altra_causa': len(copie), 'copie_senza_riga_tenuta': senza,
                       'da_recuperare': len(tenere), 'escluse_stesso_documento': len(escluse),
                       'per_motivo': dict(collections.Counter(c['perche'] for c in escluse))}
        print(caso, conti[caso])
    if not a.senza_banca_dati:
        gia = gia_in_banca([x['id'] for x in tutte])
        if gia:
            raise SystemExit(f"{len(gia)} righe gia' in banca dati con un'altra provenienza: {gia[:5]}")
    scrivi_jsonl(S6/'righe_s06.jsonl', tutte)
    scrivi_jsonl(S6/'escluse_stesso_documento.jsonl', tutte_escluse)
    tot = {'copie_in_altra_causa': sum(c['copie_in_altra_causa'] for c in conti.values()),
           'da_recuperare': len(tutte), 'escluse_stesso_documento': len(tutte_escluse),
           'per_motivo': dict(collections.Counter(x['perche'] for x in tutte_escluse))}
    scrivi_json(S6/'conti.json', {'data': DATA, 'casi': conti, 'tutti': tot})
    print('tutti', tot)


def righe_s06(caso=None):
    return [x for x in leggi_jsonl(S6/'righe_s06.jsonl') if caso is None or x['caso'] == caso]


def casi_s06():
    return [c for c in CASI if righe_s06(c)]


# ── i documenti delle righe ────────────────────────────────────────────────────────────────────────────────

def markdown_d03():
    f = T/'s05'/'markdown_s05_registro.json'
    if not f.exists():
        return set()
    return {d['markdown'] for d in leggi_json(f)['documenti'] if d.get('esito') == 'scritto'}


def documenti(caso, righe, esistenti, nuovi_md, data=DATA):
    """I documenti di corpus_rows per le righe di S06 di un caso, come `unisci_s05.py` (stessi campi, stessa
    assegnazione a turno fra chi ha righe del caso da fare, una su cinque alla cieca), con tre differenze: la
    provenienza dice S06; chi lavorera' la riga sta in `assegnato_a_in_attesa` (la riga resta fuori dalle code
    finche' non ha le proposte); `stesso_testo_di` dice la riga tenuta con lo stesso testo
    (`<document_id>__<char_start>`, come la deduplica per atto). `esistenti`: le righe del caso, [(id, dati)]."""
    from posizione_dopo_ocr import PRIMA
    from pubblica import documento
    pre = PREFISSI[caso]
    gia = [int(m.group(1)) for _, r in esistenti
           for m in [re.fullmatch(rf'{pre}-(\d+)', str(r.get('codice') or ''))] if m]
    n = max(gia, default=0)
    chi = sorted({r.get('assegnato_a') or r.get('assegnato_a_in_attesa') for _, r in esistenti
                  if r.get('proposto_rete') in ('lessicale', 'entrambe') and not r.get('esito')
                  and (r.get('assegnato_a') or r.get('assegnato_a_in_attesa'))})
    rnd = random.Random(f'{caso}-{data}-{ESTRAZIONE}')
    ids = {i for i, _ in esistenti}
    out = {}
    for k, x in enumerate(sorted(righe, key=lambda x: (x['riga']['document_id'], int(x['riga']['char_start'])))):
        r = x['riga']
        d = documento(r, caso)
        rid = x['id']
        if rid in ids:
            raise ValueError(f"riga gia' in banca dati: {rid}")
        n += 1
        prov = {'corpus': 'D03' if r['file'] in nuovi_md else 'D01', 'estrazione': ESTRAZIONE, 'tipo': '',
                'principi': {}, 'composizione': '', 'seguito': ''}
        if (PRIMA/pathlib.Path(r['file']).name).exists():
            prov['ocr'] = data          # la posizione e' gia' quella del testo dopo l'OCR: non si traduce
        d.update({'corroborazione': 'nome_presente', 'ordine': random.Random(rid).random(), 'codice': f'{pre}-{n:04d}',
                  'assegnato_a_in_attesa': chi[k % len(chi)] if chi else None,
                  'campione_cieco': rnd.random() < 0.20, 'incerta': False, 'provenienza': prov,
                  'motivo_aggiunta': MOTIVO, 'stesso_testo_di': x['primo_id'].split('__', 1)[1],
                  'stesso_testo_di_causa': x['primo_case_id'], 'esecuzione_id': f'{caso}__nomi__{data}-{ESTRAZIONE}'})
        out[rid] = d
    return out


def leggi_caso(db, caso):
    from google.cloud import firestore
    return [(d.id, d.to_dict()) for d in db.collection('corpus_rows')
            .where(filter=firestore.FieldFilter('caso_citato', '==', caso)).stream()]


def fase_scrivi(a):
    from google.cloud import firestore
    db = firestore.Client(project='climpact-drp')
    nuovi_md = markdown_d03()
    for caso in casi_s06():
        esistenti = leggi_caso(db, caso)
        # una ripresa dopo una scrittura a meta': le righe di S06 gia' scritte restano, si scrivono le altre
        gia = {i for i, r in esistenti if (r.get('provenienza') or {}).get('estrazione') == ESTRAZIONE}
        righe = [x for x in righe_s06(caso) if x['id'] not in gia]
        if gia:
            print(f"{caso}: {len(gia)} righe S06 gia' in banca dati, restano come sono")
        if not righe:
            continue
        docs = documenti(caso, righe, esistenti, nuovi_md)
        codici = sorted(d['codice'] for d in docs.values())
        print(f'{caso}: {len(docs)} righe nuove, codici {codici[0]}..{codici[-1]}, fuori dalle code (in attesa '
              f'per {len({d["assegnato_a_in_attesa"] for d in docs.values()})} persone)')
        scrivi_json(S6/f'documenti_{caso}.json', docs)
        if not a.scrivi:
            continue
        w = list(docs.items())
        for i in range(0, len(w), 400):
            b = db.batch()
            for rid, d in w[i:i + 400]:
                b.create(db.collection('corpus_rows').document(rid), {**d, 'creato_il': firestore.SERVER_TIMESTAMP})
            b.commit()
        print(f'   scritte: {len(w)}')
    if not a.scrivi:
        print('ANTEPRIMA: niente scritto')


# ── i contesti e le coppie per T01 ─────────────────────────────────────────────────────────────────────────

def fase_contesti(a):
    """le righe per i lettori con classifica_lessicali.prepara: dalla banca dati (dopo `scrivi`), o dai documenti
    che `scrivi` scriverebbe (prima)"""
    import classifica_lessicali as cl
    db = None
    if not a.dai_documenti:
        from google.cloud import firestore
        db = firestore.Client(project='climpact-drp')
    for caso in casi_s06():
        ids = [x['id'] for x in righe_s06(caso)]
        if db is not None:
            docs = []
            for i in ids:
                d = db.collection('corpus_rows').document(i).get()
                if not d.exists:
                    raise SystemExit(f"{i}: non e' in banca dati")
                docs.append({**d.to_dict(), '_id': i})
        else:
            docs = [{**d, '_id': i} for i, d in documenti(caso, righe_s06(caso), [], markdown_d03()).items()]
        tmp = S6/f'_esportate_{caso}.json'
        scrivi_json(tmp, docs)
        cl.RIGHE = S6/f'lessicali_{caso}_righe_s06.jsonl'
        cl.prepara(str(tmp), caso)
        tmp.unlink()
        fatte = {x['id'] for x in leggi_jsonl(cl.RIGHE)}
        if fatte != set(ids):
            raise SystemExit(f'{caso}: righe per i lettori {len(fatte)} su {len(ids)}')


def maschera_e_principi(caso):
    import sonde
    import yaml
    from prepara_training import mascheratore
    with open(sonde.file_caso(caso), encoding='utf-8') as h:
        conf = yaml.safe_load(h)
    with open(QUI/'cited-cases'/f'{caso}.yaml', encoding='utf-8') as h:
        vive = yaml.safe_load(h)
    forme = sorted({str(f) for f in list(conf['forme']) + list(vive['forme'])})
    maschera = mascheratore([*forme, conf.get('nome', '')])
    return maschera, {s['id']: ' '.join(s['testo'].split()) for s in conf['semantic_queries']}


def brano(contesto, maschera, allarga=800):
    """il brano per T01 come in ripresa_punteggi.prepara: il passaggio segnalato con 800 caratteri prima e dopo,
    senza i segni, spazi uniti, nome del caso mascherato. None se il contesto non ha il brano segnato."""
    from prepara_training import SEGNAPOSTO
    a, b = contesto.find(INIZIO), contesto.find(FINE)
    if a < 0 or b < 0:
        return None
    br = contesto[max(0, a - allarga): b + len(FINE) + allarga]
    br = br.replace(INIZIO, '').replace(FINE, '').replace('⟦', '').replace('⟧', '')
    return maschera.sub(SEGNAPOSTO, ' '.join(br.split()))


def pagine_attorno(righe, finestra=FINESTRA):
    """gli id delle pagine fino a `finestra` prima e dopo la pagina di ogni riga (senza la sua)"""
    return {f"{r['document_id']}#p{k}" for r in righe if int(r.get('pagina') or 0)
            for k in range(int(r['pagina']) - finestra, int(r['pagina']) + finestra + 1)
            if k > 0 and k != int(r['pagina'])}


def file_punteggi(caso):
    """i file di punteggi T01 che leggi_ripresa.prepara legge per le pagine attorno (stessa scelta): per una serie
    storica anche quelli della misura della finestra"""
    import sonde
    if sonde.storica(caso):
        return sorted(P.glob(f'{caso}_punteggi_*.jsonl')) + sorted(P.glob(f'{caso}_finestra_punteggi_*.jsonl'))
    return sorted(P.glob(f'{caso}{sonde.suf(caso)}_punteggi_*.jsonl'))


def pagine_con_punteggio(caso):
    """le pagine che hanno gia' un punteggio T01 (i punteggi di S06 stessi esclusi: le coppie si rifanno tutte)"""
    gia = set()
    for f in file_punteggi(caso):
        if f.name.endswith('_punteggi_s06.jsonl'):
            continue
        with open(f, encoding='utf-8') as h:
            for riga in h:
                x = json.loads(riga)
                if x['dove'] == 'vicina':
                    gia.add(x['pagina_id'])
    return gia


def testi_pagine(ids):
    pag = {}
    with gzip.open(QUI/'index'/'pagine'/'pagine.jsonl.gz', 'rt', encoding='utf-8') as f:
        for riga in f:
            x = json.loads(riga)
            if x['id'] in ids:
                pag[x['id']] = x['testo']
    return pag


def fase_coppie(a):
    from prepara_training import SEGNAPOSTO
    out = []
    for caso in casi_s06():
        maschera, principi = maschera_e_principi(caso)
        righe = leggi_jsonl(S6/f'lessicali_{caso}_righe_s06.jsonl')
        pag = testi_pagine(pagine_attorno(righe) - pagine_con_punteggio(caso))
        senza = 0
        for r in righe:
            br = brano(r['contesto'], maschera)
            if br is None:
                senza += 1
                continue
            out += [{'caso': caso, 'riga': r['id'], 'dove': 'brano', 'pagina': r.get('pagina'), 'principio': pid,
                     'q': q, 'd': br} for pid, q in principi.items()]
        for pagid in sorted(pag):
            d = maschera.sub(SEGNAPOSTO, ' '.join(pag[pagid].split()))
            out += [{'caso': caso, 'pagina_id': pagid, 'dove': 'vicina', 'principio': pid, 'q': q, 'd': d}
                    for pid, q in principi.items()]
        print(caso, 'righe', len(righe), 'senza brano segnato', senza, 'pagine attorno senza punteggio', len(pag))
        if senza:
            raise SystemExit(f'{caso}: {senza} righe senza brano segnato: niente punteggi del brano')
    scrivi_jsonl(S6/'s06_coppie.jsonl', out)
    print('coppie', len(out))


# ── le righe nei file dei lettori ──────────────────────────────────────────────────────────────────────────

def fase_aggiungi(a):
    """le righe di S06 in coda a training/lessicali_<caso>_righe.jsonl (il file che leggono i lettori, la mappa dei
    paragrafi e le pagine attorno), con la copia di prima accanto; una riga gia' presente si sostituisce"""
    for caso in casi_s06():
        vivo = T/f'lessicali_{caso}_righe.jsonl'
        with open(S6/f'lessicali_{caso}_righe_s06.jsonl', encoding='utf-8') as h:
            nuove = {json.loads(riga)['id']: riga if riga.endswith('\n') else riga + '\n' for riga in h if riga.strip()}
        prima = S6/f'lessicali_{caso}_righe.prima-s06.jsonl'
        if not prima.exists():
            shutil.copy(vivo, prima)
        with open(prima, encoding='utf-8') as h:
            vecchie = [riga for riga in h if riga.strip() and json.loads(riga)['id'] not in nuove]
        tmp = vivo.with_suffix('.jsonl.tmp')
        tmp.write_text(''.join(vecchie) + ''.join(nuove.values()), encoding='utf-8')
        tmp.replace(vivo)
        print(caso, 'righe di prima', len(vecchie), '+ S06', len(nuove), '->', vivo.relative_to(QUI))


# ── fuori e dentro le code ─────────────────────────────────────────────────────────────────────────────────

def completa(r):
    """una riga ha tutte le proposte (le stesse voci del controllo di completezza)"""
    return (bool(r.get('proposto_tipo_citazione')) and r.get('proposto_principi') not in (None, [])
            and bool(r.get('proposto_punteggi_principi')) and not r.get('proposta_provvisoria'))


def mosse_rimetti(righe):
    """([(id, campi)], incomplete): le righe di S06 non giudicate, ancora fuori dalle code e complete tornano a chi
    le aveva in attesa; le incomplete restano fuori"""
    mosse, incomplete = [], []
    for i, r in righe:
        if (r.get('esito') or not r.get('assegnato_a_in_attesa')
                or (r.get('provenienza') or {}).get('estrazione') != ESTRAZIONE):
            continue
        if completa(r):
            mosse.append((i, {'assegnato_a': r['assegnato_a_in_attesa'], 'assegnato_a_in_attesa': None}))
        else:
            incomplete.append(i)
    return mosse, incomplete


def fase_rimetti(a):
    from google.cloud import firestore
    db = firestore.Client(project='climpact-drp')
    righe = [(d.id, d.to_dict()) for d in db.collection('corpus_rows')
             .where(filter=firestore.FieldFilter('provenienza.estrazione', '==', ESTRAZIONE)).stream()]
    mosse, incomplete = mosse_rimetti(righe)
    print(f'righe S06 {len(righe)}, da rimettere nelle code {len(mosse)}, '
          f'senza tutte le proposte (restano fuori) {len(incomplete)}')
    (S6/'restano_fuori_dalle_code.txt').write_text(''.join(i + '\n' for i in incomplete), encoding='utf-8')
    if not a.scrivi:
        print('ANTEPRIMA: niente scritto')
        return
    for i in range(0, len(mosse), 400):
        b = db.batch()
        for rid, campi in mosse[i:i + 400]:
            b.update(db.collection('corpus_rows').document(rid),
                     {**campi, 'assegnato_a_in_attesa': firestore.DELETE_FIELD})
        b.commit()
    print('rimesse', len(mosse))


def fuori_da_s06(salvate, ids):
    """le righe di un file di proposte che non sono di S06"""
    return sorted(set(salvate) - set(ids))


def fase_verifica(a):
    """un file di proposte calcolate a secco (--salva di carica_lessicali/carica_ripresa) tocca solo righe di S06"""
    salvate = leggi_json(a.file)
    fuori = fuori_da_s06(salvate, [x['id'] for x in righe_s06()])
    print(f'{a.file}: {len(salvate)} righe, fuori da S06 {len(fuori)}')
    if fuori:
        raise SystemExit(f'righe che non sono di S06: {fuori[:5]}')


FASI = {'righe': fase_righe, 'contesti': fase_contesti, 'coppie': fase_coppie, 'scrivi': fase_scrivi,
        'aggiungi': fase_aggiungi, 'rimetti': fase_rimetti, 'verifica': fase_verifica}

if __name__ == '__main__':
    import giornale  # il giornale delle operazioni: ogni esecuzione, i file, le scritture, gli errori
    giornale.avvia()
    ap = argparse.ArgumentParser()
    ap.add_argument('fase', choices=list(FASI))
    ap.add_argument('--scrivi', action='store_true')
    ap.add_argument('--senza-banca-dati', action='store_true',
                    help='righe: non controllare che le righe manchino in banca dati')
    ap.add_argument('--dai-documenti', action='store_true',
                    help='contesti: dai documenti che scrivi scriverebbe, non dalla banca dati')
    ap.add_argument('--file', default='', help='verifica: il file JSON salvato da un caricatore con --salva')
    a = ap.parse_args()
    FASI[a.fase](a)
