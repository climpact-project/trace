"""LE PROPOSTE DEL SISTEMA NUOVO SULLE RIGHE LESSICALI: PRINCIPIO RIPRESO E SEGUITO NELLE PAGINE VICINE (27/09/2026).

   Scrive sulle righe lessicali SENZA esito (nessun giudizio umano si tocca) i campi che la scheda nuova legge
   (§63.25, codebook 0.3-pilot, dimensioni 6 e 7):
     proposto_principi         i principi spuntati in partenza: quelli dei paragrafi citati (mappa dei paragrafi)
                               piu' quelli della prima lettura di DeepSeek; ["nessuno"] se la lettura dice nessuno
                               e nessun paragrafo ne regge uno;
     proposto_principi_fonti   per ogni principio da dove viene: paragrafo, lettura, reranker (punteggio del brano
                               >= 0,5: vicino nelle parole, mostrato come indizio anche se non spuntato);
     proposto_principio_altro  la frase della lettura quando dice «altro»;
     proposto_estensione       le pagine vicine proposte, con prosegue si'/no, principio e frase della lettura;
     proposto_paragrafi        i paragrafi citati riconosciuti;
     proposto_principi_motivo  il commento della lettura di DeepSeek alle sue scelte (voluto dal PI);
     proposto_ripresa_lettore  chi ha proposto.
   Sono proposte: le etichette per addestrare vengono dalle persone o dalla mappa dei paragrafi, mai da DeepSeek.

   Uso:  .venv/bin/python tools/carica_ripresa.py --caso urgenda            anteprima
         .venv/bin/python tools/carica_ripresa.py --caso urgenda --scrivi   scrive
"""
import argparse, collections, hashlib, json, pathlib, re
QUI = pathlib.Path(__file__).resolve().parent.parent
P = QUI/'training'/'principi'
SOGLIA_RERANKER = 0.5


def proposta(caso, rid, ids, par, brano, ds, cand, tipo=''):
    """I campi proposti per una riga (senza toccare nulla)."""
    l = (ds.get(rid) or {}).get('letture') or [{}]
    l1 = l[0] if isinstance(l[0], dict) else {}
    fonti = collections.defaultdict(list)
    for p in par.get(rid, {}).get('principi', []):
        fonti[p].append('paragrafo')
    lett = [p for p in (l1.get('principi') or []) if isinstance(p, str)]
    for p in lett:
        if p in ids:
            fonti[p].append('lettura')
    for p, s in brano.get(rid, {}).items():
        if s >= SOGLIA_RERANKER:
            fonti[p].append('reranker')
    spuntati = [p for p in ids if 'paragrafo' in fonti[p] or 'lettura' in fonti[p]]
    altro = ' '.join(str(l1.get('altro') or '').split())
    if 'altro' in lett and altro:
        spuntati.append('altro')
    if not spuntati and 'nessuno' in lett:
        spuntati = ['nessuno']
    # UNA MENZIONE IN CATENA NON PRENDE NESSUN PRINCIPIO (codebook, dimensione 6). Le due letture di DeepSeek erano
    # separate, e una citazione letta come «in catena» arrivava con principi spuntati: 287 righe il 28/09/2026,
    # segnalato dal PI. Gli indizi (paragrafo, reranker) restano nelle fonti, visibili ma non spuntati.
    in_catena = tipo == 'menzione_in_catena'
    if in_catena:
        spuntati = ['nessuno']
    vic = []
    pagine_cand = {v['pagina'] for v in (cand.get(rid) or {}).get('vicine', [])}
    # LA FRASE E' DAVVERO DELLA PAGINA? (PI, 28/09/2026: una «prova» in italiano scambiata per il testo dell'atto).
    # Solo il 53-64% delle frasi di DeepSeek sulle pagine vicine e' copiato dalla pagina: le altre sono sue.
    norm = lambda t: re.sub(r'\W+', ' ', str(t).lower()).strip()
    testi = {v['pagina']: norm(v.get('testo', '')) for v in (cand.get(rid) or {}).get('vicine', [])}
    for v in (l1.get('vicine') or []):
        try:
            n = int(v.get('pagina'))
        except (TypeError, ValueError):
            continue
        if n in pagine_cand:
            prova = ' '.join(str(v.get('prova') or '').split())[:300]
            vic.append({'pagina': n, 'prosegue': bool(v.get('prosegue')), 'principio': v.get('principio') or '',
                        'prova': prova, 'testuale': bool(prova) and norm(prova)[:60] in testi.get(n, '')})
    # NIENTE SEGUITO SENZA PRINCIPIO (PI, 28/09/2026, memoriale per la Corte interamericana p. 51 -> p. 54): se la
    # citazione non prende nessun principio (in catena, o «nessuno»), non c'e' niente che prosegua. Le pagine restano
    # elencate, nessuna spuntata.
    if spuntati == ['nessuno']:
        vic = [dict(v, prosegue=False) for v in vic]
    # LA PROVENIENZA (registro delle versioni, `tools/registro_versioni.py`): per ogni principio le versioni che lo
    # hanno proposto; V05 al posto di V04 dove c'e' la seconda lettura.
    lettura = 'V05' if (ds.get(rid) or {}).get('seconda') else 'V04'
    codici = {'paragrafo': 'V01', 'lettura': lettura, 'reranker': 'V06'}
    prov = {'provenienza.principi': {k: sorted({codici[f] for f in v}) for k, v in fonti.items() if v},
            'provenienza.seguito': lettura if vic else '', 'provenienza.composizione': 'V07',
            'provenienza.estrazione': 'V00', 'provenienza.corpus': 'D01',
            'proposto_punteggi_principi': {k: round(float(x), 4) for k, x in brano.get(rid, {}).items()},
            'proposto_testo_impronta': hashlib.sha256(((cand.get(rid) or {}).get('contesto') or '').encode('utf-8')).hexdigest()}
    # LA FRASE DELL'ATTO CHE LA CITAZIONE SOSTIENE (V05, 28/09/2026): copiata dalla lettura, con la verifica che sia
    # davvero nella pagina (serve a evidenziarla nel PDF e a decidere il principio sulla frase giusta).
    frase = ' '.join(str(l1.get('frase_sostenuta') or '').split())[:600]
    ctx = norm((cand.get(rid) or {}).get('contesto') or '')
    if frase:
        prov['proposto_frase_sostenuta'] = frase
        prov['proposto_frase_testuale'] = norm(frase)[:60] in ctx
    return {**prov, 'proposto_principi': spuntati, 'proposto_principi_fonti': {k: v for k, v in fonti.items() if v},
            'proposto_principio_altro': altro if 'altro' in spuntati else '', 'proposto_estensione': vic,
            'proposto_paragrafi': par.get(rid, {}).get('paragrafi', []),
            # il commento della lettura alle sue scelte (PI, 27/09/2026): si mostra a chi valida accanto alla proposta
            'proposto_principi_motivo': ('Menzione in catena: nessun principio proposto. ' if in_catena else '')
                                        + ' '.join(str(l1.get('motivo') or '').split())[:400],
            'proposto_ripresa_lettore': 'mappa dei paragrafi + DeepSeek V4 Flash 0731 + TRACE-Reranker, 27/09/2026'}


def carica(caso):
    import yaml
    ids = [s['id'] for s in yaml.safe_load(open(QUI/'cited-cases'/f'{caso}.yaml', encoding='utf-8'))['semantic_queries']]
    par = {json.loads(l)['id']: json.loads(l) for l in open(P/f'{caso}_da_paragrafi.jsonl', encoding='utf-8')}
    brano = collections.defaultdict(dict)
    for f in sorted(P.glob(f'{caso}_punteggi_*.jsonl')):
        for l in open(f, encoding='utf-8'):
            x = json.loads(l)
            if x['dove'] == 'brano':
                brano[x['riga']][x['principio']] = x['punteggio']
    ds = {json.loads(l)['id']: json.loads(l) for l in open(P/f'{caso}_ripresa_deepseek.jsonl', encoding='utf-8')}
    # la seconda lettura (regola delle note, 28/09/2026), dove c'e', prende il posto della prima; `v10` e' la stessa
    # lettura sulle righe aggiunte dalla ricerca corretta e su quelle la cui prima lettura non si leggeva (29/09/2026)
    for f2 in (P/f'{caso}_ripresa_deepseek_v2.jsonl', P/f'{caso}_ripresa_deepseek_v10.jsonl'):
        if f2.exists():
            ds.update({json.loads(l)['id']: dict(json.loads(l), seconda=True) for l in open(f2, encoding='utf-8')})
    cand = {json.loads(l)['id']: json.loads(l) for l in open(P/f'{caso}_ripresa_righe.jsonl', encoding='utf-8')}
    return ids, par, brano, ds, cand


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--caso', default='urgenda'); ap.add_argument('--scrivi', action='store_true')
    a = ap.parse_args()
    ids, par, brano, ds, cand = carica(a.caso)
    from google.cloud import firestore
    db = firestore.Client(project='climpact-drp')
    conti = collections.Counter(); scritture = []
    for d in db.collection('corpus_rows').where(filter=firestore.FieldFilter('caso_citato', '==', a.caso)).stream():
        r = d.to_dict()
        if r.get('proposto_rete') not in ('lessicale', 'entrambe'):
            continue
        if r.get('esito'):
            conti['gia giudicata (non toccata)'] += 1; continue
        if d.id not in ds:
            conti['senza lettura'] += 1; continue
        campi = proposta(a.caso, d.id, ids, par, brano, ds, cand, r.get('proposto_tipo_citazione') or '')
        spuntati, vic = campi['proposto_principi'], campi['proposto_estensione']
        scritture.append((d.reference, campi))
        conti['da scrivere'] += 1
        conti['con principio spuntato' if spuntati and spuntati != ['nessuno'] else ('nessuno' if spuntati else 'senza proposta')] += 1
        conti['con seguito proposto' if any(v['prosegue'] for v in vic) else 'senza seguito'] += 1
    print(json.dumps(dict(conti), ensure_ascii=False, indent=1))
    if scritture:
        print('esempio:', json.dumps(scritture[0][1], ensure_ascii=False)[:700])
    if not a.scrivi:
        print('ANTEPRIMA: niente scritto'); return
    for i in range(0, len(scritture), 400):
        b = db.batch()
        for ref, c in scritture[i:i+400]:
            b.update(ref, c)
        b.commit()
    print(f'scritte {len(scritture)} righe')


if __name__ == '__main__':
    main()
