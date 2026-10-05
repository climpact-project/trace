"""D04, LE 13 RIGHE DEI DOCUMENTI NUOVI IN PIATTAFORMA (03/10/2026, preparato per la notte dopo S06).

   Da dove. D04 (`tools/scarica_d04.py`, `tools/build_markdown_d04.py`, `tools/cerca_d04.py`) ha riscaricato i 27 atti
   dell'aggiornamento del 19/09 mai scaricati ed estratto i 20 atti non PDF: 46 Markdown nuovi. La ricerca per nome S05
   fatta solo su di loro, a secco, ha trovato 13 righe nuove (training/d04/<caso>_righe_nuove.jsonl: Urgenda 4, parere
   CIG 5, Corte IDH 4). Qui ricevono lo STESSO trattamento delle altre righe (lo stesso del ciclo S06): fuori dalle code
   finche' non hanno le proposte, T01 sul brano e sulle pagine attorno, cinque letture del tipo e cinque L05 sulle
   pagine attorno R10, R11 con i freni, poi nelle code.

   Fasi (le chiama tools/ciclo_d04.sh; senza --scrivi niente si scrive in banca dati o sul disco del server):
     indice    l'indice delle pagine D04 diventa il vivo: il vivo di oggi + le pagine aggiunte di D04 (secondo membro
               gzip, come build_markdown_d04.py), copia di prima in index/pagine/pagine.prima-D04.jsonl.gz
     righe     le 13 righe ricontrollate sulla banca dati di oggi -> training/d04/righe_d04.jsonl, conti.json
     scrivi    le righe in corpus_rows FUORI DALLE CODE (`assegnato_a_in_attesa`), codici dopo il piu' alto del caso
               (dopo S06), provenienza corpus D04, estrazione S05
     pdf       i PDF riscaricati di D04 sul server del corpus, accanto agli altri (documents/<causa>/<file>.pdf), mai
               sopra un file che c'e' gia'; poi la prova dal servizio vero (corpus.climpact.it/pdf/...)
     contesti  le righe per i lettori dalla banca dati -> training/d04/lessicali_<caso>_righe_d04.jsonl
     aggiungi  le righe nei file dei lettori (training/lessicali_<caso>_righe.jsonl), con la copia di prima accanto
     coppie    le coppie per T01: brano delle righe e pagine attorno (10 prima, 10 dopo) ancora senza punteggio
     prepara-ferma / raccogli-ferma   T01 nel modo recas-ferma di S06 (vLLM fermato e riacceso dalla trap)
     rimetti   le righe D04 con tutte le proposte tornano nelle code; le altre restano fuori, elencate
     verifica  un file di proposte calcolate a secco tocca solo righe di D04?

   Uso:  .venv/bin/python tools/recupero_d04.py <fase> [--scrivi]
"""
import argparse
import collections
import gzip
import hashlib
import json
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import time
import urllib.parse

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
import recupero_s06 as r6  # noqa: E402  gli aiuti comuni (letti, non cambiati)
from gettone_corpus import con_gettone  # noqa: E402  /pdf/ vuole il gettone dal 03/10/2026

T = QUI/'training'
D4 = T/'d04'
P = T/'principi'
PAG = QUI/'index'/'pagine'
DATA = '2026-10-03'
CORPUS = 'D04'
CASI = r6.CASI
PREFISSI = r6.PREFISSI
MOTIVO = 'documento senza Markdown fino al 03/10/2026 (D04: riscaricato o non PDF)'
CAMPI_SOLO_FILE = ('id', 'codice_provvisorio', 'causa')       # nel file delle righe, non in banca dati
SERVER_PDF = 'root@188.213.175.194'                         # il server del corpus (docs/PROMPT-CORPUS.md)
RADICE_PDF = '/root/corpus'
SERVIZIO_PDF = 'https://corpus.climpact.it/pdf/'
FERMA_COPPIE = P/'d04_coppie.jsonl'     # ripresa_punteggi.py punteggi --caso d04 legge training/principi/d04_coppie...

leggi_jsonl, scrivi_jsonl, leggi_json, scrivi_json = r6.leggi_jsonl, r6.scrivi_jsonl, r6.leggi_json, r6.scrivi_json


def sha_file(f):
    h = hashlib.sha256()
    with open(f, 'rb') as x:
        for b in iter(lambda: x.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


# ── l'indice delle pagine ──────────────────────────────────────────────────────────────────────────────────────────

def ids_gzip(f):
    with gzip.open(f, 'rt', encoding='utf-8') as h:
        return [json.loads(riga)['id'] for riga in h if riga.strip()]


def fase_indice(a):
    """Il vivo + le pagine aggiunte di D04 (lo stesso file che build_markdown_d04.py ha scritto accanto, rifatto sul
    vivo di oggi se nel frattempo e' cambiato). Si controlla: le pagine aggiunte sono quelle registrate (impronta),
    nessuna e' gia' nel vivo; dopo la sostituzione il vivo ha tutte le pagine di prima piu' quelle aggiunte."""
    reg = leggi_json(D4/'markdown_d04_registro.json')
    vivo, agg = PAG/'pagine.jsonl.gz', PAG/'pagine.d04.aggiunte.jsonl.gz'
    stato = D4/'indice_d04.json'
    if stato.exists() and sha_file(vivo) == leggi_json(stato)['vivo_dopo']:
        print("l'indice vivo e' gia' quello D04:", leggi_json(stato))
        return 0
    if sha_file(agg) != reg['uscite']['index/pagine/pagine.d04.aggiunte.jsonl.gz']:
        raise SystemExit("le pagine aggiunte di D04 non sono quelle registrate: rifare build_markdown_d04.py")
    nuove = ids_gzip(agg)
    if len(nuove) != reg['uscite']['pagine_aggiunte']:
        raise SystemExit(f"pagine aggiunte {len(nuove)}, registrate {reg['uscite']['pagine_aggiunte']}")
    prima = ids_gzip(vivo)
    gia = set(nuove) & set(prima)
    if gia:
        raise SystemExit(f"{len(gia)} pagine di D04 gia' nel vivo: {sorted(gia)[:3]}")
    sha_prima = sha_file(vivo)
    x = {'data': time.strftime('%Y-%m-%d %H:%M'), 'vivo_prima': sha_prima, 'righe_prima': len(prima),
         'vivo_registrato_da_d04': reg['ingressi']['index/pagine/pagine.jsonl.gz (vivo, copiato)'],
         'pagine_aggiunte': len(nuove), 'aggiunte': sha_file(agg)}
    x['vivo_cambiato_dopo_d04'] = x['vivo_prima'] != x['vivo_registrato_da_d04']
    print(json.dumps(x, ensure_ascii=False, indent=1))
    if not a.scrivi:
        print('ANTEPRIMA: niente scritto')
        return 0
    copia = PAG/'pagine.prima-D04.jsonl.gz'
    if not copia.exists():
        shutil.copy2(vivo, copia)
    if sha_file(copia) != sha_prima:
        raise SystemExit(f"{copia.name} esiste ed e' diverso dal vivo di oggi: controllare a mano")
    tmp = PAG/'pagine.jsonl.gz.d04-tmp'
    with open(tmp, 'wb') as out:
        for f in (vivo, agg):
            with open(f, 'rb') as h:
                shutil.copyfileobj(h, out, 1 << 22)
    dopo = ids_gzip(tmp)
    if dopo != prima + nuove:
        tmp.unlink()
        raise SystemExit('il file nuovo non ha le pagine attese')
    if sha_file(vivo) != sha_prima:
        tmp.unlink()
        raise SystemExit("l'indice vivo e' cambiato durante la copia: rifare")
    tmp.replace(vivo)
    x['vivo_dopo'] = sha_file(vivo)
    x['righe_dopo'] = len(dopo)
    scrivi_json(stato, x)
    print('indice vivo con le pagine di D04:', x['righe_dopo'], 'righe')
    return 0


# ── le righe ───────────────────────────────────────────────────────────────────────────────────────────────────────

def righe_preparate(caso=None):
    out = []
    for c in CASI:
        f = D4/f'{c}_righe_nuove.jsonl'
        if (caso is None or c == caso) and f.exists():
            out += [{'caso': c, **x} for x in leggi_jsonl(f)]
    return out


def righe_d04(caso=None):
    return [x for x in leggi_jsonl(D4/'righe_d04.jsonl') if caso is None or x['caso'] == caso]


def casi_d04():
    return [c for c in CASI if righe_d04(c)]


def e_d04(r):
    """una riga gia' scritta da questo caricamento"""
    return (r.get('provenienza') or {}).get('corpus') == CORPUS and r.get('motivo_aggiunta') == MOTIVO


def controlla_righe(preparate, esistenti):
    """(problemi, gia_scritte). `esistenti`: {id: dati} di tutta la banca dati dei casi. Un problema: un id gia' in
    banca dati che non e' una riga D04; un'altra riga (non D04) nello stesso documento, che vorrebbe dire che la
    copertura calcolata da cerca_d04.py (nessuna riga in quei documenti) non vale piu'."""
    problemi, gia = [], []
    docs = {x['document_id'] for x in preparate}
    per_doc = collections.defaultdict(list)
    for i, r in esistenti.items():
        if r.get('document_id') in docs and not e_d04(r):
            per_doc[r['document_id']].append(i)
    for x in preparate:
        r = esistenti.get(x['id'])
        if r is not None:
            if e_d04(r):
                gia.append(x['id'])
            else:
                problemi.append(f"{x['id']}: gia' in banca dati con un'altra provenienza")
    for d, ids in sorted(per_doc.items()):
        problemi.append(f'{d}: altre righe nello stesso documento ({len(ids)}, per esempio {ids[0]})')
    return problemi, gia


def leggi_banca(db):
    out = {}
    for caso in CASI:
        for i, r in r6.leggi_caso(db, caso):
            out[i] = r
    return out


def fase_righe(a):
    from google.cloud import firestore
    db = firestore.Client(project='climpact-drp')
    preparate = righe_preparate()
    for x in preparate:
        if not (QUI/x['file']).exists():
            raise SystemExit(f"{x['id']}: manca il Markdown {x['file']}")
    problemi, gia = controlla_righe(preparate, leggi_banca(db))
    if problemi:
        raise SystemExit('righe D04 non caricabili:\n  ' + '\n  '.join(problemi))
    scrivi_jsonl(D4/'righe_d04.jsonl', preparate)
    conti = {'data': time.strftime('%Y-%m-%d %H:%M'), 'righe': len(preparate), 'gia_scritte': len(gia),
             'casi': dict(collections.Counter(x['caso'] for x in preparate)),
             'documenti': dict(collections.Counter(x['document_id'] for x in preparate))}
    scrivi_json(D4/'conti.json', conti)
    print(json.dumps(conti, ensure_ascii=False, indent=1))


def documenti(caso, righe, esistenti, data=DATA):
    """I documenti di corpus_rows per le righe D04 di un caso: quelli preparati da cerca_d04.py (stessa regola di
    unisci_s05.py), con tre cambi fatti adesso, sulla banca dati di oggi: il codice dopo il piu' alto del caso (S06 ha
    aggiunto righe dopo la prova a secco), chi lavorera' la riga in `assegnato_a_in_attesa` (fuori dalle code finche'
    non ha le proposte), l'esecuzione. `esistenti`: [(id, dati)] del caso."""
    pre = PREFISSI[caso]
    gia = [int(m.group(1)) for _, r in esistenti
           for m in [re.fullmatch(rf'{pre}-(\d+)', str(r.get('codice') or ''))] if m]
    n = max(gia, default=0)
    ids = {i for i, _ in esistenti}
    out = {}
    for x in sorted(righe, key=lambda x: (x['document_id'], int(x['char_start']))):
        if x['id'] in ids:
            raise ValueError(f"riga gia' in banca dati: {x['id']}")
        d = {k: v for k, v in x.items() if k not in CAMPI_SOLO_FILE and k != 'caso'}
        n += 1
        d['codice'] = f'{pre}-{n:04d}'
        d['assegnato_a_in_attesa'] = d.pop('assegnato_a', None)
        d['provenienza'] = {**(d.get('provenienza') or {}), 'corpus': CORPUS, 'estrazione': 'S05'}
        d['motivo_aggiunta'] = MOTIVO
        d['esecuzione_id'] = f'{caso}__nomi__{data}-{CORPUS}'
        out[x['id']] = d
    return out


def fase_scrivi(a):
    from google.cloud import firestore
    db = firestore.Client(project='climpact-drp')
    for caso in casi_d04():
        esistenti = r6.leggi_caso(db, caso)
        # una ripresa dopo una scrittura a meta': le righe D04 gia' scritte restano, si scrivono le altre
        gia = {i for i, r in esistenti if e_d04(r)}
        righe = [x for x in righe_d04(caso) if x['id'] not in gia]
        if gia:
            print(f"{caso}: {len(gia)} righe D04 gia' in banca dati, restano come sono")
        if not righe:
            continue
        docs = documenti(caso, righe, esistenti)
        codici = sorted(d['codice'] for d in docs.values())
        print(f'{caso}: {len(docs)} righe nuove, codici {codici[0]}..{codici[-1]}, fuori dalle code')
        scrivi_json(D4/f'documenti_{caso}.json', docs)
        if not a.scrivi:
            continue
        b = db.batch()
        for rid, d in docs.items():
            b.create(db.collection('corpus_rows').document(rid), {**d, 'creato_il': firestore.SERVER_TIMESTAMP})
        b.commit()
        print(f'   scritte: {len(docs)}')
    if not a.scrivi:
        print('ANTEPRIMA: niente scritto')


# ── i PDF sul server del corpus ────────────────────────────────────────────────────────────────────────────────────

def pdf_d04():
    """i PDF riscaricati di D04 (gli atti non PDF restano quelli di luglio, gia' sul server)"""
    reg = leggi_json(D4/'markdown_d04_registro.json')
    return [d['origine'] for d in reg['documenti']
            if d.get('esito') == 'scritto' and str(d.get('origine', '')).endswith('.pdf')]


def url_pdf(percorso):
    return SERVIZIO_PDF + '/'.join(urllib.parse.quote(s) for s in percorso.split('/'))


def ssh(cmd):
    return subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=30', SERVER_PDF, cmd],
                          capture_output=True, text=True, check=False)


def servito(percorso):
    """(codice http, byte) del PDF come lo serve il servizio del corpus"""
    p = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code} %{size_download}', '--max-time', '120',
                        con_gettone(url_pdf(percorso))], capture_output=True, text=True, check=False)
    codice, _, n = p.stdout.strip().partition(' ')
    return codice, int(n or 0)


def fase_pdf(a):
    esiti = []
    for f in pdf_d04():
        loc = QUI/f
        if not loc.exists():
            esiti.append({'file': f, 'esito': 'manca sul Mac'})
            continue
        rem = f'{RADICE_PDF}/{f}'
        c = ssh(f'test -e {shlex.quote(rem)} && stat -c %s {shlex.quote(rem)} || echo assente')
        if c.returncode == 255:
            raise SystemExit(f'server del corpus irraggiungibile: {c.stderr[:200]}')
        gia = c.stdout.strip()
        if gia != 'assente':
            uguale = gia == str(loc.stat().st_size)
            esito = 'gia sul server' if uguale else f'gia sul server, DIVERSO ({gia} byte): non toccato'
        elif not a.scrivi:
            esito = 'da caricare'
        else:
            ssh(f'mkdir -p {shlex.quote(str(pathlib.PurePosixPath(rem).parent))}')
            tmp = rem + '.d04-tmp'
            ok = subprocess.run(['scp', '-q', '-p', str(loc), f'{SERVER_PDF}:{shlex.quote(tmp)}'],
                                check=False).returncode == 0
            # mai sopra un file che c'e' gia': il nome vero si prende solo se e' ancora libero
            q, qt = shlex.quote(rem), shlex.quote(tmp)
            mv = ssh(f'test -e {q} || mv {qt} {q}; rm -f {qt}')
            esito = 'caricato' if ok and mv.returncode == 0 else 'caricamento fallito'
        x = {'file': f, 'byte': loc.stat().st_size, 'esito': esito}
        if a.scrivi or esito.startswith('gia'):
            x['servito'] = servito(f)
        esiti.append(x)
        print(x['esito'], x.get('servito', ''), f[-80:])
    scrivi_json(D4/'pdf_d04.json', {'data': time.strftime('%Y-%m-%d %H:%M'), 'pdf': esiti})
    if a.scrivi:
        male = [x for x in esiti if x.get('servito') != ('200', x['byte'])]
        print(f'PDF di D04: {len(esiti)}, serviti con la lunghezza giusta {len(esiti) - len(male)}')
        if male:
            raise SystemExit(f'{len(male)} PDF non serviti bene: {[x["file"][-60:] for x in male[:3]]}')
    return 0


# ── i contesti, le righe dei lettori, le coppie per T01 ────────────────────────────────────────────────────────────

def fase_contesti(a):
    """le righe per i lettori con classifica_lessicali.prepara, dalla banca dati (dopo `scrivi`)"""
    import classifica_lessicali as cl
    from google.cloud import firestore
    db = firestore.Client(project='climpact-drp')
    for caso in casi_d04():
        ids = [x['id'] for x in righe_d04(caso)]
        docs = []
        for i in ids:
            d = db.collection('corpus_rows').document(i).get()
            if not d.exists:
                raise SystemExit(f"{i}: non e' in banca dati")
            docs.append({**d.to_dict(), '_id': i})
        tmp = D4/f'_esportate_{caso}.json'
        scrivi_json(tmp, docs)
        cl.RIGHE = D4/f'lessicali_{caso}_righe_d04.jsonl'
        cl.prepara(str(tmp), caso)
        tmp.unlink()
        fatte = {x['id'] for x in leggi_jsonl(cl.RIGHE)}
        if fatte != set(ids):
            raise SystemExit(f'{caso}: righe per i lettori {len(fatte)} su {len(ids)}')


def unisci_righe(vecchie, nuove):
    """le righe di prima (senza quelle che si rifanno) e poi le nuove, nell'ordine: [riga JSON con a capo]"""
    ids = {json.loads(r)['id'] for r in nuove}
    return [r for r in vecchie if json.loads(r)['id'] not in ids] + list(nuove)


def fase_aggiungi(a):
    """le righe D04 in coda a training/lessicali_<caso>_righe.jsonl (il file che leggono i lettori, la mappa dei
    paragrafi e le pagine attorno), con la copia di prima accanto (righe S06 comprese)"""
    for caso in casi_d04():
        vivo = T/f'lessicali_{caso}_righe.jsonl'
        with open(D4/f'lessicali_{caso}_righe_d04.jsonl', encoding='utf-8') as h:
            nuove = [r if r.endswith('\n') else r + '\n' for r in h if r.strip()]
        prima = D4/f'lessicali_{caso}_righe.prima-d04.jsonl'
        if not prima.exists():
            shutil.copy(vivo, prima)
        with open(prima, encoding='utf-8') as h:
            vecchie = [r if r.endswith('\n') else r + '\n' for r in h if r.strip()]
        tutte = unisci_righe(vecchie, nuove)
        tmp = vivo.with_suffix('.jsonl.tmp')
        tmp.write_text(''.join(tutte), encoding='utf-8')
        tmp.replace(vivo)
        print(caso, 'righe di prima', len(tutte) - len(nuove), '+ D04', len(nuove), '->', vivo.relative_to(QUI))


def pagine_con_punteggio(caso):
    """le pagine che hanno gia' un punteggio T01 (quelli di D04 stessi esclusi: le coppie si rifanno tutte)"""
    gia = set()
    for f in r6.file_punteggi(caso):
        if f.name.endswith('_punteggi_d04.jsonl'):
            continue
        with open(f, encoding='utf-8') as h:
            for riga in h:
                x = json.loads(riga)
                if x['dove'] == 'vicina':
                    gia.add(x['pagina_id'])
    return gia


def fase_coppie(a):
    from prepara_training import SEGNAPOSTO
    out = []
    for caso in casi_d04():
        maschera, principi = r6.maschera_e_principi(caso)
        righe = leggi_jsonl(D4/f'lessicali_{caso}_righe_d04.jsonl')
        serve = r6.pagine_attorno(righe) - pagine_con_punteggio(caso)
        proprie = {f"{r['document_id']}#p{int(r['pagina'])}" for r in righe if int(r.get('pagina') or 0)}
        testi = r6.testi_pagine(serve | proprie)
        # la pagina di ogni riga deve stare nell'indice vivo: senza, la fase indice non e' stata fatta
        manca = sorted(proprie - set(testi))
        if manca:
            raise SystemExit(f"{caso}: pagine delle righe D04 assenti dall'indice vivo (fase indice?): {manca[:3]}")
        pag = {k: v for k, v in testi.items() if k in serve}
        senza = 0
        for r in righe:
            br = r6.brano(r['contesto'], maschera)
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
    scrivi_jsonl(D4/'d04_coppie.jsonl', out)
    print('coppie', len(out))


# ── T01 nel modo recas-ferma (lo schema di S06) ────────────────────────────────────────────────────────────────────

def fase_prepara_ferma(a):
    import punteggi_t01_s06 as t01
    righe = leggi_jsonl(D4/'d04_coppie.jsonl')
    prova_coppie, _ = t01.campione_prova(t01.PROVA_N)
    scrivi_jsonl(FERMA_COPPIE, t01.coppie_ferma(righe, prova_coppie))
    print(f'{len(righe)} coppie di D04 + {len(prova_coppie)} della prova -> {FERMA_COPPIE.relative_to(QUI)}')


def fase_raccogli_ferma(a):
    """dopo il calcolo su ReCaS: punteggi ricomposti, prova contro le H100 (le 300 coppie di S06), file per caso"""
    import punteggi_t01_s06 as t01
    coppie = leggi_jsonl(FERMA_COPPIE)
    m = t01.ricomponi(coppie, [leggi_jsonl(D4/f'd04_punteggi_{k}.jsonl') for k in range(a.pezzi)])
    prova_coppie, ref = t01.campione_prova(t01.PROVA_N)
    e = t01.esito_prova([m[t01.chiave(q, d)] for q, d in prova_coppie], ref)
    e.update({'data': time.strftime('%Y-%m-%d %H:%M'), 'dispositivo': 'recas-ferma (H100, ripresa_punteggi.py)',
              'riferimento': 'training/principi/s05_coppie.jsonl con s05_punteggi_0.jsonl (H100, ciclo S05 del 02/10)',
              'seme_del_campione': 20261003})
    scrivi_json(D4/'t01_prova_recas-ferma.json', e)
    print('prova T01 contro le H100:', json.dumps(e, ensure_ascii=False))
    d04 = [x for x in coppie if x['caso'] != 'prova']
    with open(D4/'t01_memoria_ferma.jsonl', 'w', encoding='utf-8') as h:
        for x in d04:
            k = t01.chiave(x['q'], x['d'])
            h.write(json.dumps({'k': k, 's': m[k]}) + '\n')
    if not e['passa']:
        return 1
    t01.scrivi_punteggi(d04, m, etichetta='d04')
    return 0


# ── fuori e dentro le code ─────────────────────────────────────────────────────────────────────────────────────────

def mosse_rimetti(righe):
    """([(id, campi)], incomplete): le righe D04 non giudicate, ancora fuori dalle code e complete tornano a chi le
    aveva in attesa; le incomplete restano fuori"""
    mosse, incomplete = [], []
    for i, r in righe:
        if r.get('esito') or not r.get('assegnato_a_in_attesa') or not e_d04(r):
            continue
        if r6.completa(r):
            mosse.append((i, {'assegnato_a': r['assegnato_a_in_attesa'], 'assegnato_a_in_attesa': None}))
        else:
            incomplete.append(i)
    return mosse, incomplete


def fase_rimetti(a):
    from google.cloud import firestore
    db = firestore.Client(project='climpact-drp')
    righe = []
    for x in righe_d04():
        d = db.collection('corpus_rows').document(x['id']).get()
        if d.exists:
            righe.append((d.id, d.to_dict()))
    mosse, incomplete = mosse_rimetti(righe)
    print(f'righe D04 {len(righe)}, da rimettere nelle code {len(mosse)}, '
          f'senza tutte le proposte (restano fuori) {len(incomplete)}')
    (D4/'restano_fuori_dalle_code.txt').write_text(''.join(i + '\n' for i in incomplete), encoding='utf-8')
    if not a.scrivi:
        print('ANTEPRIMA: niente scritto')
        return
    b = db.batch()
    for rid, campi in mosse:
        b.update(db.collection('corpus_rows').document(rid), {**campi, 'assegnato_a_in_attesa': firestore.DELETE_FIELD})
    b.commit()
    print('rimesse', len(mosse))


def fase_verifica(a):
    """un file di proposte calcolate a secco (--salva di carica_lessicali/carica_ripresa) tocca solo righe di D04"""
    salvate = leggi_json(a.file)
    fuori = r6.fuori_da_s06(salvate, [x['id'] for x in righe_d04()])
    print(f'{a.file}: {len(salvate)} righe, fuori da D04 {len(fuori)}')
    if fuori:
        raise SystemExit(f'righe che non sono di D04: {fuori[:5]}')


FASI = {'indice': fase_indice, 'righe': fase_righe, 'scrivi': fase_scrivi, 'pdf': fase_pdf, 'contesti': fase_contesti,
        'aggiungi': fase_aggiungi, 'coppie': fase_coppie, 'prepara-ferma': fase_prepara_ferma,
        'raccogli-ferma': fase_raccogli_ferma, 'rimetti': fase_rimetti, 'verifica': fase_verifica}

if __name__ == '__main__':
    import giornale  # il giornale delle operazioni: ogni esecuzione, i file, le scritture, gli errori
    giornale.avvia()
    ap = argparse.ArgumentParser()
    ap.add_argument('fase', choices=list(FASI))
    ap.add_argument('--scrivi', action='store_true')
    ap.add_argument('--file', default='', help='verifica: il file JSON salvato da un caricatore con --salva')
    ap.add_argument('--pezzi', type=int, default=4, help='raccogli-ferma: quanti pezzi (uno per GPU)')
    a = ap.parse_args()
    sys.exit(FASI[a.fase](a) or 0)
