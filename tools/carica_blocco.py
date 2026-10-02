"""APPRENDIMENTO ATTIVO CONTINUO: un blocco di pagine dalla cima della lista della catena TRACE (27/09/2026).

   Metodo in `METODO-IN-UNA-PAGINA.md`, documento unico §63.21-63.22. Tre passi:

     scegli   Mac. Dalla lista riordinata (`training/fase2/riordino_urgenda_trace.csv`) le prime N pagine che:
              non nominano il caso citato nel testo (quelle sono lavoro della rete lessicale), e non hanno nessuna
              riga in piattaforma per quel caso (lette dal vivo in Firestore, SOLA LETTURA). Per ogni pagina la
              semantic query per cui il riordinatore da' il voto piu' alto.
              -> training/fase2/<blocco>_pagine.json
     passaggi GPU (ReCaS). Per ogni pagina il passaggio da mostrare: la finestra di circa 600 caratteri piu' vicina
              alla semantic query (Perplexity originale), che il visore accende nel PDF.
              -> training/fase2/<blocco>_passaggi.json
     righe    Mac. Costruisce le righe nel formato di `pubblica.py`, stesse regole (proposte in `proposto_*`, mai
              sovrascritte). Senza --scrivi stampa una riga di esempio e i conti, e non scrive niente.
              Con --scrivi: una esecuzione nuova in `corpus_runs` e le righe in `corpus_rows`, divise fra chi ha
              righe di quel caso da fare. Le righe esistenti non si toccano mai.

   L'ORDINE IN CODA. Le righe del blocco hanno `ordine` negativo e crescente col posto in lista: in coda vengono
   prima delle righe di luglio (che hanno un ordine casuale fra 0 e 1) e nell'ordine della macchina. Chi valida
   non vede ne' il posto ne' il punteggio.
"""
import argparse, csv, gzip, json, pathlib, random, re, sys
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
F2 = QUI/'training'/'fase2'
PAGINE = QUI/'index'/'pagine'/'pagine.jsonl.gz'
PROGETTO = 'climpact-drp'


def firestore_client():
    from google.cloud import firestore
    return firestore, firestore.Client(project=PROGETTO)


def righe_del_caso(caso):
    firestore, db = firestore_client()
    q = db.collection('corpus_rows').where(filter=firestore.FieldFilter('caso_citato', '==', caso))
    return [dict(id=d.id, **d.to_dict()) for d in q.stream()]


def scegli(caso, lista, n, blocco):
    best, sonda = {}, {}
    for r in csv.DictReader(open(lista, encoding='utf-8')):
        v = float(r['riordino'])
        if v > best.get(r['pagina_id'], -1):
            best[r['pagina_id']] = v; sonda[r['pagina_id']] = r['sonda']
    esistenti = righe_del_caso(caso)
    pr = lambda x: str(x.get('validato_pagina') or x.get('proposto_pagina') or '').strip()
    gia = {f"{x['document_id']}#p{pr(x)}" for x in esistenti} | {f"{x['document_id']}#p{x.get('proposto_pagina')}" for x in esistenti}
    ordine = sorted(best, key=lambda p: -best[p])
    guarda = set(ordine[:max(4000, n * 20)])
    testi = {}
    with gzip.open(PAGINE, 'rt', encoding='utf-8') as f:
        for l in f:
            x = json.loads(l)
            if x['id'] in guarda:
                testi[x['id']] = x
    nome = re.compile(caso.replace('-', '[ -]'), re.I)
    scelte, saltate = [], {'nomina il caso': 0, 'gia in piattaforma': 0, 'fuori indice': 0}
    for posto, p in enumerate(ordine, 1):
        if len(scelte) >= n:
            break
        x = testi.get(p)
        if not x:
            saltate['fuori indice'] += 1; continue
        if nome.search(x['testo']):
            saltate['nomina il caso'] += 1; continue
        if p in gia:
            saltate['gia in piattaforma'] += 1; continue
        scelte.append({'pagina_id': p, 'document_id': x['doc'], 'file': x['file'], 'pagina': x['pagina'],
                       'da': x['da'], 'sonda': sonda[p], 'voto': round(best[p], 5), 'posto_lista': posto})
    uscita = F2/f'{blocco}_pagine.json'
    json.dump(scelte, open(uscita, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{len(scelte)} pagine -> {uscita}; saltate {saltate}; ultima al posto {scelte[-1]["posto_lista"]}')


def passaggi(caso, blocco):
    """GPU: la finestra di ~600 caratteri piu' vicina alla semantic query, con Perplexity originale."""
    import torch, torch.nn.functional as F, yaml
    from transformers import AutoTokenizer, AutoModel
    conf = yaml.safe_load(open(QUI/'cited-cases'/f'{caso}.yaml', encoding='utf-8'))
    S = {q['id']: ' '.join(q['testo'].split()) for q in conf['semantic_queries']}
    S.update({q['id'] + '__alt': ' '.join(q['probe_alternativa'].split())
              for q in conf['semantic_queries'] if q.get('probe_alternativa')})
    scelte = json.load(open(F2/f'{blocco}_pagine.json', encoding='utf-8'))
    serve = {s['pagina_id'] for s in scelte}; testo = {}
    with gzip.open(PAGINE, 'rt', encoding='utf-8') as f:
        for l in f:
            x = json.loads(l)
            if x['id'] in serve:
                testo[x['id']] = x['testo']
    NOME = 'perplexity-ai/pplx-embed-v1-4b'
    tok = AutoTokenizer.from_pretrained(NOME, padding_side='left', trust_remote_code=True)
    m = AutoModel.from_pretrained(NOME, dtype=torch.bfloat16, trust_remote_code=True).cuda().eval()

    def vettori(testi):
        out = []
        for i in range(0, len(testi), 32):
            e = tok(testi[i:i+32], padding=True, truncation=True, max_length=512, return_tensors='pt').to('cuda')
            with torch.no_grad():
                hs = m(**e).last_hidden_state
            mk = e['attention_mask'].unsqueeze(-1).to(hs.dtype)
            out.append(F.normalize(((hs*mk).sum(1)/mk.sum(1)).float(), dim=-1))
        return torch.cat(out)
    fuori = []
    for s in scelte:
        t = testo[s['pagina_id']]
        fin = [(i, t[i:i+600]) for i in range(0, max(1, len(t) - 200), 300)]
        q = vettori([S[s['sonda']]])[0]
        V = vettori([w for _, w in fin])
        k = int(torch.argmax(V @ q))
        a, w = fin[k]
        # si comincia e si finisce su uno spazio, per non tagliare una parola a meta'
        a2 = t.find(' ', a) + 1 if a else 0
        w = t[a2:a + 600]; w = w[:w.rfind(' ')] if ' ' in w[-40:] else w
        fuori.append({**s, 'passaggio': w.strip(), 'scarto_in_pagina': a2})
    json.dump(fuori, open(F2/f'{blocco}_passaggi.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{len(fuori)} passaggi -> {F2/f"{blocco}_passaggi.json"}')


def righe(caso, blocco, esecuzione, scrivi, file_passaggi=None):
    import build_chunks as B
    from pubblica import id_riga
    import yaml
    conf = yaml.safe_load(open(QUI/'cited-cases'/f'{caso}.yaml', encoding='utf-8'))
    etichetta = {q['id']: ' '.join(str(q.get('titolo') or q['id']).split()) for q in conf['semantic_queries']}
    scelte = json.load(open(file_passaggi or F2/f'{blocco}_passaggi.json', encoding='utf-8'))
    esistenti = righe_del_caso(caso)
    cita_doc = {x['document_id'] for x in esistenti if x.get('proposto_rete') in ('lessicale', 'entrambe')}
    cita_caso = {x.get('case_id') for x in esistenti if x.get('proposto_rete') in ('lessicale', 'entrambe')}
    # CHI VALIDA QUESTO CASO: chi ha righe assegnate ancora da fare. Il blocco si divide a turno fra loro.
    chi = sorted({x['assegnato_a'] for x in esistenti if x.get('assegnato_a') and not x.get('esito')})
    docs = {}
    for k, s in enumerate(scelte):
        meta, corpo, base = B.leggi(QUI/s['file'])
        start = int(s['da']) + int(s['scarto_in_pagina'])
        sid = s['sonda'].split('__')[0]
        corr = ('documento_lo_cita' if s['document_id'] in cita_doc
                else 'caso_lo_cita' if meta.get('case_id') in cita_caso else 'mai_nominato')
        rid = id_riga(caso, s['document_id'], start)
        docs[rid] = {
            'caso_citato': caso, 'case_id': meta.get('case_id', ''), 'case_name': meta.get('case_name', ''),
            'giurisdizioni': meta.get('giurisdizioni', ''), 'document_id': s['document_id'],
            'tipo_atto': meta.get('tipo_atto', ''), 'tipo_atto_sabin': meta.get('tipo_atto_sabin', ''),
            'data': meta.get('data_deposito', ''),
            'url_documento': f"https://www.climatecasechart.com/documents/{s['document_id']}",
            'file': s['file'], 'file_pdf': meta.get('file_pdf') or re.sub(r'\.md$', '.pdf', re.sub(r'^markdown/', 'documents/', s['file'])),
            'char_start': start,
            'proposto_pagina': int(s['pagina']), 'proposto_forma_trovata': '',
            'proposto_citazione_testuale': s['passaggio'], 'finestra_pagina': '',
            'proposto_tipo_citazione': '', 'proposto_chi_parla': '', 'proposto_annidata': False,
            'proposto_proposizione': '', 'proposto_confidenza': '', 'proposto_rete': 'semantica',
            'proposto_note': '',
            'sonda': etichetta.get(sid, sid) + (' [2a formulazione]' if s['sonda'].endswith('__alt') else ''),
            'punteggio': None, 'punteggio_riordino': s['voto'], 'punteggio_escluse': None, 'margine': None,
            'sospetto': '', 'copie': 1, 'anteriore': False, 'codebook_versione': '0.2-pilot',
            'esito': None, 'validato_da': None, 'validato_il': None, 'nel_campione': False, 'integrale': True,
            'doppia_codifica': False, 'strato': 'ignoto|ignota|semantica', 'scartato': False, 'motivo_scarto': '',
            'corroborazione': corr,
            'ordine': -1.0 + (s.get('posto_blocco', k) + 1) / 10000.0,
            'assegnato_a': chi[k % len(chi)] if chi else None,
            'fase': 2, 'blocco': blocco, 'posto_lista': s['posto_lista'],
        }
    doppioni = [r for r in docs if r in {x['id'] for x in esistenti}]
    print(f'righe {len(docs)}; gia esistenti (non si toccano) {len(doppioni)}; validatori {len(chi)}')
    esempio = next(iter(docs.values()))
    print(json.dumps({k: esempio[k] for k in ('case_name', 'document_id', 'proposto_pagina', 'sonda', 'corroborazione',
                                                'proposto_citazione_testuale')}, ensure_ascii=False, indent=1))
    if not scrivi:
        print('\nnon scritto niente (manca --scrivi)')
        return
    firestore, db = firestore_client()
    db.collection('corpus_runs').document(esecuzione).set({
        'caso_citato': caso, 'origine': 'catena TRACE, apprendimento attivo', 'blocco': blocco,
        'righe_scritte': len(docs) - len(doppioni), 'quando': firestore.SERVER_TIMESTAMP,
        'codebook_versione': '0.2-pilot',
        'indice_modello': 'pplx-embed-v1-4b + Qwen3-Embedding-4B (pagine)',
        'indice_data': '2026-09-26', 'indice_frammenti': 569218, 'indice_unita': 'pages',
        'indice': {'modello': 'pplx-embed-v1-4b (Perplexity) e Qwen3-Embedding-4B, non addestrati, sulle pagine',
                   'costruito': '2026-09-26 (Perplexity), 2026-09-25 (Qwen)',
                   'unita': 'pagine intere (fino a 2.048 token), almeno 200 caratteri', 'pagine': 569218,
                   'profondita': '10.000 pagine per formulazione, 10 formulazioni, per ciascun retriever'},
        'retriever': 'TRACE-Retriever: pplx-embed-v1-4b + LoRA sui giudizi, WiSE-FT 0,25; con Qwen3-Embedding-4B non addestrato; 10.000 pagine per formulazione',
        'riordinatore': 'TRACE-Reranker: Qwen3-Reranker-4B + LoRA, tre semi',
        'copertura_note': 'pagine che non nominano il caso e senza righe in piattaforma, dalla cima della lista',
        'in_sospeso': '',
        'search_strategy': (QUI/'cited-cases'/f'{caso}.yaml').read_text(encoding='utf-8'),
    })
    elenco = [(r, d) for r, d in docs.items() if r not in doppioni]
    for i in range(0, len(elenco), 450):
        lotto = db.batch()
        for rid, d in elenco[i:i+450]:
            lotto.set(db.collection('corpus_rows').document(rid),
                      {**d, 'esecuzione_id': esecuzione, 'creato_il': firestore.SERVER_TIMESTAMP})
        lotto.commit()
    print(f'scritte {len(elenco)} righe, esecuzione {esecuzione}')


def prepara_blocco(caso, lista, n, blocco):
    """IL BLOCCO SUCCESSIVO (ciclo automatico): le prime N pagine della lista che nessuno ha giudicato, che non
    nominano il caso (lavoro della rete lessicale) e che non hanno righe lessicali. Scrive la lista intera del
    blocco (`<blocco>_lista.json`) e, per le pagine senza nessuna riga in piattaforma, i dati per scegliere il
    passaggio (`<blocco>_pagine.json`, lo legge `passaggi`)."""
    best, sonda = {}, {}
    for r in csv.DictReader(open(lista, encoding='utf-8')):
        v = float(r['riordino'])
        if v > best.get(r['pagina_id'], -1):
            best[r['pagina_id']] = v; sonda[r['pagina_id']] = r['sonda']
    ordine = sorted(best, key=lambda p: -best[p])
    esistenti = righe_del_caso(caso)
    pr = lambda x: str(x.get('validato_pagina') or x.get('proposto_pagina') or '').strip()
    chiavi = lambda x: {f"{x['document_id']}#p{pr(x)}", f"{x['document_id']}#p{x.get('proposto_pagina')}"}
    giudicate, lessicali, qualunque = set(), set(), set()
    for x in esistenti:
        k = chiavi(x); qualunque |= k
        if x.get('esito') or x.get('da_discutere'):
            giudicate |= k
        if x.get('proposto_rete') == 'lessicale':
            lessicali |= k
    guarda = set(ordine[:max(6000, n * 40)]); testi = {}
    with gzip.open(PAGINE, 'rt', encoding='utf-8') as f:
        for l in f:
            x = json.loads(l)
            if x['id'] in guarda:
                testi[x['id']] = x
    nome = re.compile(caso.replace('-', '[ -]'), re.I)
    scelte, da_creare = [], []
    for posto, p in enumerate(ordine, 1):
        if len(scelte) >= n:
            break
        x = testi.get(p)
        if not x or nome.search(x['testo']) or p in giudicate or p in lessicali:
            continue
        scelte.append(p)
        if p not in qualunque:
            da_creare.append({'pagina_id': p, 'document_id': x['doc'], 'file': x['file'], 'pagina': x['pagina'],
                              'da': x['da'], 'sonda': sonda[p], 'voto': round(best[p], 5), 'posto_lista': posto})
    json.dump(scelte, open(F2/f'{blocco}_lista.json', 'w', encoding='utf-8'))
    json.dump(da_creare, open(F2/f'{blocco}_pagine.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{blocco}: {len(scelte)} pagine, {len(da_creare)} da creare')
    return len(scelte)


def componi(caso, blocco, esecuzione, scrivi, lista_blocco, lista_intera):
    """IL BLOCCO VERO (27/09/2026, decisione del PI): le prime N pagine della lista che nessuno ha giudicato,
    qualunque macchina le abbia trovate. Quelle che hanno gia' una riga di luglio da fare NON si duplicano: la
    loro riga sale in cima alla coda (`ordine` negativo) e porta scritto il blocco. Per le altre si crea la riga.
    Poi tutte le righe di luglio ancora da fare prendono l'ordine della lista nuova; quelle che la lista nuova
    non contiene vanno in fondo. Si tocca solo `ordine` e `blocco`: niente di cio' che e' stato scritto."""
    firestore, db = firestore_client()
    ordine_blocco = json.load(open(lista_blocco, encoding='utf-8'))
    best = {}
    for r in csv.DictReader(open(lista_intera, encoding='utf-8')):
        best[r['pagina_id']] = max(best.get(r['pagina_id'], -1), float(r['riordino']))
    rango = {p: k for k, p in enumerate(sorted(best, key=lambda p: -best[p]), 1)}
    esistenti = righe_del_caso(caso)
    pr = lambda x: str(x.get('validato_pagina') or x.get('proposto_pagina') or '').strip()
    # SOLO LE SEMANTICHE: le lessicali hanno un altro lavoro (il tipo di citazione) e la loro coda non si tocca.
    da_fare = [x for x in esistenti if not x.get('esito') and not x.get('da_discutere') and x.get('proposto_rete') != 'lessicale']
    per_pagina = {}
    for x in da_fare:
        per_pagina.setdefault(f"{x['document_id']}#p{pr(x)}", []).append(x)
    posto_blocco = {p: k for k, p in enumerate(ordine_blocco)}
    spostate, nuove_pagine = [], []
    for p in ordine_blocco:
        (spostate if p in per_pagina else nuove_pagine).append(p)
    aggiorna = {}
    for p in spostate:
        for x in per_pagina[p]:
            aggiorna[x['id']] = {'ordine': -1.0 + (posto_blocco[p] + 1) / 10000.0, 'blocco': blocco}
    n_luglio_lista = n_luglio_fondo = 0
    for x in da_fare:
        if x['id'] in aggiorna:
            continue
        p = f"{x['document_id']}#p{pr(x)}"
        if p in rango:
            aggiorna[x['id']] = {'ordine': rango[p] / (len(rango) + 1.0)}; n_luglio_lista += 1
        else:
            aggiorna[x['id']] = {'ordine': 1.0 + random.Random(x['id']).random()}; n_luglio_fondo += 1
    print(f'blocco: {len(ordine_blocco)} pagine, {len(spostate)} con riga di luglio (sale in cima), {len(nuove_pagine)} da creare')
    print(f'righe di luglio da fare: {len(da_fare)}; riordinate secondo la lista {n_luglio_lista}; in fondo {n_luglio_fondo}')
    # le pagine da creare: i passaggi gia' scelti, nello stesso ordine della lista
    passaggi = {x['pagina_id']: x for x in json.load(open(F2/f'{blocco}_passaggi.json', encoding='utf-8'))}
    mancano = [p for p in nuove_pagine if p not in passaggi]
    if mancano:
        print(f'ATTENZIONE: {len(mancano)} pagine senza passaggio, non create: {mancano[:3]}')
    scelte = [{**passaggi[p], 'posto_blocco': posto_blocco[p]} for p in nuove_pagine if p in passaggi]
    json.dump(scelte, open(F2/f'{blocco}_passaggi_da_creare.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if not scrivi:
        print('non scritto niente (manca --scrivi)')
        return
    elenco = list(aggiorna.items())
    for i in range(0, len(elenco), 450):
        lotto = db.batch()
        for rid, d in elenco[i:i+450]:
            lotto.update(db.collection('corpus_rows').document(rid), d)
        lotto.commit()
    print(f'aggiornate {len(elenco)} righe esistenti (solo ordine e blocco)')
    righe(caso, blocco, esecuzione, True, file_passaggi=F2/f'{blocco}_passaggi_da_creare.json')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('fase', choices=['scegli', 'passaggi', 'righe', 'componi', 'prepara'])
    ap.add_argument('--lista-blocco', default=str(F2/'urgenda_blocco1_lista.json'))
    ap.add_argument('--caso', default='urgenda')
    ap.add_argument('--lista', default=str(F2/'riordino_urgenda_trace.csv'))
    ap.add_argument('--n', type=int, default=100)
    ap.add_argument('--blocco', default='urgenda_blocco1')
    ap.add_argument('--esecuzione', default='urgenda__trace_blocco1_2026-09-27')
    ap.add_argument('--scrivi', action='store_true')
    a = ap.parse_args()
    if a.fase == 'scegli':
        scegli(a.caso, a.lista, a.n, a.blocco)
    elif a.fase == 'passaggi':
        passaggi(a.caso, a.blocco)
    elif a.fase == 'prepara':
        prepara_blocco(a.caso, a.lista, a.n, a.blocco)
    elif a.fase == 'componi':
        componi(a.caso, a.blocco, a.esecuzione, a.scrivi, a.lista_blocco, a.lista)
    else:
        righe(a.caso, a.blocco, a.esecuzione, a.scrivi)
