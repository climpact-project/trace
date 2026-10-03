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

   Uso:  .venv/bin/python tools/035_carica_ripresa.py --caso urgenda            anteprima
         .venv/bin/python tools/035_carica_ripresa.py --caso urgenda --scrivi   scrive
"""
import argparse, collections, hashlib, json, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
_m_freni = __import__('034_freni')
verifica = _m_freni.verifica
QUI = pathlib.Path(__file__).resolve().parent.parent
P = QUI/'training'/'principi'
SOGLIA_RERANKER = 0.5


def proposta(caso, rid, ids, par, brano, ds, cand, tipo='', ds_principi=None, ds_seguito=None):
    """I campi proposti per una riga (senza toccare nulla)."""
    l = (ds.get(rid) or {}).get('letture') or [{}]
    l1 = l[0] if isinstance(l[0], dict) else {}
    # I PRINCIPI DA L04, IL RESTO DA L05 (30/09/2026, col si' del PI): L05 decide il principio sulla sola frase della
    # nota e, contro i giudizi del PI, fa peggio di L04 (§63.35); le sue prove copiate, la frase sostenuta e la finestra
    # larga restano. Dove L04 non c'e' (righe aggiunte dopo, letture illeggibili) i principi restano di L05.
    lp_ = ((ds_principi or {}).get(rid) or {}).get('letture') or []
    lp = lp_[0] if lp_ and isinstance(lp_[0], dict) else None
    da_l04 = lp is not None
    lp = lp if da_l04 else l1
    # UNA LETTURA CON L'ELENCO VUOTO NON E' UNA RISPOSTA (revisione del 30/09/2026: 247 righe in coda con principi []).
    # Si passa alla seconda lettura della stessa versione, poi alla lettura L05; se tutte sono vuote vale «nessuno».
    def vuota(x):
        return not [q for q in (x.get('principi') or []) if isinstance(q, str) and q]
    if vuota(lp):
        for alt in list(lp_[1:]) + [x for x in l if isinstance(x, dict)]:
            if isinstance(alt, dict) and not vuota(alt):
                lp = alt; break
    fonti = collections.defaultdict(list)
    for p in par.get(rid, {}).get('principi', []):
        fonti[p].append('paragrafo')
    lett = [p for p in (lp.get('principi') or []) if isinstance(p, str)]
    # IL NOME SENZA IL PREFISSO DEL CASO (revisione del 30/09/2026): DeepSeek scrive «vorwirkung_...» per
    # «neubauer.vorwirkung_...» e la composizione lo buttava via (82 letture di Neubauer, 26 di Future Generations).
    def canonico(q):
        if q in ids:
            return q
        trovato = next((i for i in ids if i.endswith('.' + q)), None)
        if trovato:
            return trovato
        # I REFUSI (01/10/2026): «dovere_oggetto_posteri», «neubaurer.liberta_intertemporale», «diritti_generazioni_futuri»
        # (4 letture su 3.488): si riporta al codice valido piu' vicino solo se la somiglianza e' molto alta
        import difflib
        corto = {i.split('.')[-1]: i for i in ids}
        m = difflib.get_close_matches(q.split('.')[-1], list(corto), n=1, cutoff=0.85)
        return corto[m[0]] if m else q
    lett = [canonico(p) for p in lett]
    for p in lett:
        if p in ids:
            fonti[p].append('lettura')
    for p, s in brano.get(rid, {}).items():
        if s >= SOGLIA_RERANKER:
            fonti[p].append('reranker')
    spuntati = [p for p in ids if 'paragrafo' in fonti[p] or 'lettura' in fonti[p]]
    altro = ' '.join(str(lp.get('altro') or '').split())
    if 'altro' in lett and altro:
        spuntati.append('altro')
    # 02/10/2026: anche quando le letture danno solo codici che non sono sonde («cooperazione_obbligo» per una citazione
    # sul dovere di cooperare, ICJ-0629): nessuna sonda ripresa, cioe' «nessuno», non una riga senza proposta
    if not spuntati and ('nessuno' in lett or not [q for q in lett if q in ids]):
        spuntati = ['nessuno']
    # UNA MENZIONE IN CATENA NON PRENDE NESSUN PRINCIPIO (codebook, dimensione 6). Le due letture di DeepSeek erano
    # separate, e una citazione letta come «in catena» arrivava con principi spuntati: 287 righe il 28/09/2026,
    # segnalato dal PI. Gli indizi (paragrafo, reranker) restano nelle fonti, visibili ma non spuntati.
    in_catena = tipo == 'menzione_in_catena'
    if in_catena:
        spuntati = ['nessuno']
    vic = []
    pagine_cand = {v['pagina'] for v in (cand.get(rid) or {}).get('vicine', [])}
    punti_vicine = {v['pagina']: v.get('punteggi') or {} for v in (cand.get(rid) or {}).get('vicine', [])}
    try:
        pag_cit = int((cand.get(rid) or {}).get('pagina') or 0)
    except (TypeError, ValueError):
        pag_cit = 0
    # LA FRASE E' DAVVERO DELLA PAGINA? (PI, 28/09/2026: una «prova» in italiano scambiata per il testo dell'atto).
    # Solo il 53-64% delle frasi di DeepSeek sulle pagine vicine e' copiato dalla pagina: le altre sono sue.
    norm = lambda t: re.sub(r'\W+', ' ', str(t).lower()).strip()
    testi_prompt = [t for k in ids for t in (PRINCIPI_TESTO.get(k) or ())]
    testi = {v['pagina']: norm(v.get('testo', '')) for v in (cand.get(rid) or {}).get('vicine', [])}
    # IL SEGUITO RILETTO SUI PRINCIPI DI OGGI (L07, 30/09/2026): dove i principi sono cambiati, la lettura del seguito
    # fatta sui principi proposti prende il posto di quella di L05.
    ls_ = ((ds_seguito or {}).get(rid) or {}).get('letture') or []
    lv = ls_[0] if ls_ and isinstance(ls_[0], dict) and 'vicine' in ls_[0] else l1
    for v in (lv.get('vicine') or []):
        try:
            n = int(v.get('pagina'))
        except (TypeError, ValueError):
            continue
        if n in pagine_cand:
            prova = ' '.join(str(v.get('prova') or '').split())[:300]
            # PERCHE' IL RERANKER HA SCELTO QUESTA PAGINA (29/09/2026, il PI: «non leggo il perche'»): il punteggio piu'
            # alto di T01, il principio che l'ha dato, la distanza dalla citazione e la soglia che valeva a quella distanza.
            pv = punti_vicine.get(n) or {}
            migliore = max(pv.items(), key=lambda kv: kv[1]) if pv else (None, None)
            dist = n - pag_cit if pag_cit else None
            # il nome del principio a volte torna senza il prefisso del caso («vorwirkung_...» per «neubauer.vorwirkung_...»)
            pr_v = v.get('principio') or ''
            pr_v = pr_v if (not pr_v or pr_v in ids) else next((i for i in ids if i.endswith('.' + pr_v)), pr_v)
            # IL FRENO (30/09/2026, `034_freni.py`): una pagina prosegue solo se la prova sta davvero nella pagina; una prova
            # copiata dal prompt (il testo di un principio) e' inventata e la pagina non si spunta mai.
            esito_prova = verifica(prova, (cand.get(rid) or {}).get('vicine_testo', {}).get(n) or next((w.get('testo', '') for w in (cand.get(rid) or {}).get('vicine', []) if w['pagina'] == n), ''), testi_prompt)
            vic.append({'pagina': n, 'prosegue': bool(v.get('prosegue')) and esito_prova == 'trovata', 'principio': pr_v,
                        'prova': prova, 'testuale': esito_prova == 'trovata', 'prova_esito': esito_prova,
                        'scelta': {'punteggio': round(float(migliore[1]), 3) if migliore[1] is not None else None,
                                   'principio': migliore[0] or '', 'distanza': dist,
                                   'soglia': (0.5 if dist is not None and -2 <= dist <= 3 else 0.8), 'versione': 'T01', 'regola': 'R03'}})
    # NIENTE SEGUITO SENZA PRINCIPIO (PI, 28/09/2026, memoriale per la Corte interamericana p. 51 -> p. 54): se la
    # citazione non prende nessun principio (in catena, o «nessuno»), non c'e' niente che prosegua. Le pagine restano
    # elencate, nessuna spuntata.
    if spuntati == ['nessuno']:
        vic = [dict(v, prosegue=False) for v in vic]
    # NIENTE SEGUITO SU UN PRINCIPIO CHE LA RIGA NON PROPONE (30/09/2026, R02): la regola del codebook dice che una
    # pagina prosegue solo se sviluppa uno dei principi presi dalla citazione. Dal 30/09 principi (L04) e seguito
    # (L05/L07) vengono da letture diverse: una pagina spuntata su un altro principio resta elencata, non spuntata.
    else:
        vic = [dict(v, prosegue=False) if (v['prosegue'] and v['principio'] and v['principio'] not in spuntati) else v for v in vic]
    # LA PROVENIENZA (registro delle versioni, `tools/048_registro_versioni.py`): per ogni principio le versioni che lo
    # hanno proposto; V05 al posto di V04 dove c'e' la seconda lettura.
    lettura = 'L05' if (ds.get(rid) or {}).get('seconda') else 'L04'
    codici = {'paragrafo': CODICI_RUN['mappa'], 'lettura': 'L04' if (da_l04 and ds_principi is not None) else lettura, 'reranker': 'T01'}
    prin_prov = {k: sorted({codici[f] for f in v}) for k, v in fonti.items() if v}
    # «altro» (un principio fuori dalla lista) viene solo dalla lettura: anche lui dice da quale versione viene
    if 'altro' in (spuntati or []) and 'altro' not in prin_prov:
        prin_prov['altro'] = [codici['lettura']]
    prov = {'provenienza.principi': prin_prov,
            'provenienza.seguito': ('L07' if lv is not l1 else lettura) if vic else '', 'provenienza.composizione': 'R05',
            # QUALI SONDE (01/10/2026): l'insieme dei principi con cui sono state fatte le proposte (P01 Urgenda, P02/P03)
            'provenienza.sonde': CODICI_RUN['sonde'],
            'provenienza.scelta_vicine': 'R08' if vic else '',   # R08 dal 01/10/2026: punteggi su tutta la finestra
            # `estrazione` e `corpus` non si riscrivono: li mette chi crea la riga (S01 le righe della prima ricerca,
            # S02 quelle aggiunte dalla ricerca corretta). Fino al 29/09 qui si scriveva S01 su tutte.
            'proposto_punteggi_principi': {k: round(float(x), 4) for k, x in brano.get(rid, {}).items()},
            **({'provenienza.corpus': 'D02'} if rid.split('__')[1] in DOCUMENTI_OCR else {}),
            'proposto_testo_impronta': hashlib.sha256(((cand.get(rid) or {}).get('contesto') or '').encode('utf-8')).hexdigest()}
    # LA FRASE DELL'ATTO CHE LA CITAZIONE SOSTIENE (V05, 28/09/2026): copiata dalla lettura, con la verifica che sia
    # davvero nella pagina (serve a evidenziarla nel PDF e a decidere il principio sulla frase giusta).
    frase = ' '.join(str(l1.get('frase_sostenuta') or '').split())[:600]
    ctx = norm((cand.get(rid) or {}).get('contesto') or '')
    if frase:
        prov['proposto_frase_sostenuta'] = frase
        prov['proposto_frase_testuale'] = norm(frase)[:60] in ctx
        prov['proposto_frase_esito'] = verifica(frase, (cand.get(rid) or {}).get('contesto') or '', testi_prompt)
    return {**prov, 'proposto_principi': spuntati, 'proposto_principi_fonti': {k: v for k, v in fonti.items() if v},
            'proposto_principio_altro': altro if 'altro' in spuntati else '', 'proposto_estensione': vic,
            'proposto_paragrafi': par.get(rid, {}).get('paragrafi', []),
            # il commento della lettura alle sue scelte (PI, 27/09/2026): si mostra a chi valida accanto alla proposta
            'proposto_principi_motivo': ('Menzione in catena: nessun principio proposto. ' if in_catena else '')
                                        + ' '.join(str(lp.get('motivo') or '').split())[:400],
            'proposto_ripresa_lettore': 'mappa dei paragrafi + DeepSeek V4 Flash 0731 + TRACE-Reranker, 27/09/2026'}


def load_l04(caso):
    S = __import__('011_sonde')
    if not S.storica(caso):   # una serie di sonde nuova (P03 e seguenti): solo le sue letture L04
        f = P/f'{caso}_ripresa_deepseek_l04{S.serie(caso)}.jsonl'
        return {json.loads(l)['id']: json.loads(l) for l in open(f, encoding='utf-8')} if f.exists() else {}
    # L04 del 27/09, piu' le righe che non aveva letto, lette il 30/09 con le stesse istruzioni (`032_leggi_l04.py`)
    out = {json.loads(l)['id']: json.loads(l) for l in open(P/f'{caso}_ripresa_deepseek.jsonl', encoding='utf-8')}
    # `l04ocr2`: le righe rilette sul testo OCR (01/10/2026), che prendono il posto della lettura sulla pagina illeggibile
    for nuove in (P/f'{caso}_ripresa_deepseek_l04nuove.jsonl', P/f'{caso}_ripresa_deepseek_l04ocr.jsonl', P/f'{caso}_ripresa_deepseek_l04ocr2.jsonl'):
        if nuove.exists():
            out.update({json.loads(l)['id']: json.loads(l) for l in open(nuove, encoding='utf-8')})
    return out


PRINCIPI_TESTO = {}


def carica(caso):
    import yaml
    S = __import__('011_sonde')
    sq = yaml.safe_load(open(S.file_caso(caso), encoding='utf-8'))['semantic_queries']
    ids = [s['id'] for s in sq]
    PRINCIPI_TESTO.update({s['id']: (' '.join(s['titolo'].split()), ' '.join(s['testo'].split())) for s in sq})
    par = {json.loads(l)['id']: json.loads(l) for l in open(P/f'{caso}_da_paragrafi{S.suf(caso)}.jsonl', encoding='utf-8')}
    brano = collections.defaultdict(dict)
    for f in sorted(P.glob(f'{caso}{S.suf(caso)}_punteggi_*.jsonl')):
        for l in open(f, encoding='utf-8'):
            x = json.loads(l)
            if x['dove'] == 'brano':
                brano[x['riga']][x['principio']] = x['punteggio']
    if not S.storica(caso):   # una serie di sonde nuova (P03 e seguenti): solo le sue letture L05
        f = P/f'{caso}_ripresa_deepseek_{S.serie(caso)}.jsonl'
        ds = {json.loads(l)['id']: dict(json.loads(l), seconda=True) for l in open(f, encoding='utf-8')} if f.exists() else {}
        cand = {json.loads(l)['id']: json.loads(l) for l in open(P/f'{caso}_ripresa_righe{S.suf(caso)}.jsonl', encoding='utf-8')}
        return ids, par, brano, ds, cand
    ds = {json.loads(l)['id']: json.loads(l) for l in open(P/f'{caso}_ripresa_deepseek.jsonl', encoding='utf-8')}
    # la seconda lettura (regola delle note, 28/09/2026), dove c'e', prende il posto della prima; `v10` e' la stessa
    # lettura sulle righe aggiunte dalla ricerca corretta e su quelle la cui prima lettura non si leggeva (29/09/2026)
    # `ocr`: la lettura L05 delle righe trovate dopo l'OCR dei documenti con pagine illeggibili (01/10/2026)
    # `ocr2`: le righe gia' in banca dati rilette sul testo OCR (01/10/2026): vincono su tutte le letture di prima
    for f2 in (P/f'{caso}_ripresa_deepseek_v2.jsonl', P/f'{caso}_ripresa_deepseek_v10.jsonl', P/f'{caso}_ripresa_deepseek_ocr.jsonl',
               P/f'{caso}_ripresa_deepseek_ocr2.jsonl'):
        if f2.exists():
            ds.update({json.loads(l)['id']: dict(json.loads(l), seconda=True) for l in open(f2, encoding='utf-8')})
    cand = {json.loads(l)['id']: json.loads(l) for l in open(P/f'{caso}_ripresa_righe{S.suf(caso)}.jsonl', encoding='utf-8')}
    return ids, par, brano, ds, cand


# I CODICI DI QUESTO GIRO (01/10/2026): sonde e mappa dei paragrafi dipendono dal caso; i documenti rifatti con l'OCR
# portano il corpus D02.
CODICI_RUN = {'sonde': '', 'mappa': 'R04'}
DOCUMENTI_OCR = {k.split('#')[0] for k in json.load(open(QUI/'training'/'ocr'/'pagine_sostituite.json', encoding='utf-8'))} \
    if (QUI/'training'/'ocr'/'pagine_sostituite.json').exists() else set()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--caso', default='urgenda'); ap.add_argument('--scrivi', action='store_true')
    ap.add_argument('--principi-da-l04', action='store_true', help='principi dalla lettura L04, il resto da L05 (30/09/2026)')
    ap.add_argument('--anche-senza-lettura', action='store_true',
                    help="01/10/2026: anche le righe che DeepSeek non ha ancora letto, con i principi dei paragrafi e i punteggi del reranker (proposta provvisoria)")
    ap.add_argument('--salva', default='', help="file JSON in cui salvare le proposte calcolate, senza scriverle (per i confronti, 01/10/2026)")
    a = ap.parse_args()
    ids, par, brano, ds, cand = carica(a.caso)
    ds_principi = load_l04(a.caso) if a.principi_da_l04 else None
    S = __import__('011_sonde')
    CODICI_RUN.update({'sonde': S.codice(a.caso), 'mappa': {'P03': 'R06', 'P05': 'R07'}.get(S.serie(a.caso)) or {'klimaseniorinnen': 'R09', 'cig-parere-clima': 'R09', 'idh-oc-32-25': 'R09'}.get(a.caso, 'R04')})
    f7 = P/f'{a.caso}_seguito_l07.jsonl' if S.storica(a.caso) else P/'_nessuno.jsonl'
    ds_seguito = {json.loads(l)['id']: json.loads(l) for l in open(f7, encoding='utf-8')} if (a.principi_da_l04 and f7.exists()) else None
    # una rilettura L07 fatta sulla pagina illeggibile non vale per le righe rilette sul testo OCR (01/10/2026)
    f_ocr2 = P/f'{a.caso}_ripresa_deepseek_ocr2.jsonl'
    if ds_seguito and f_ocr2.exists():
        for l in open(f_ocr2, encoding='utf-8'):
            ds_seguito.pop(json.loads(l)['id'], None)
    from google.cloud import firestore
    db = firestore.Client(project='climpact-drp')
    conti = collections.Counter(); scritture = []
    for d in db.collection('corpus_rows').where(filter=firestore.FieldFilter('caso_citato', '==', a.caso)).stream():
        r = d.to_dict()
        if r.get('proposto_rete') not in ('lessicale', 'entrambe'):
            continue
        if r.get('esito'):
            conti['gia giudicata (non toccata)'] += 1; continue
        if d.id not in ds and not a.anche_senza_lettura:
            conti['senza lettura'] += 1; continue
        if d.id not in ds:
            conti['provvisoria: paragrafi e reranker, lettura in arrivo'] += 1
        campi = proposta(a.caso, d.id, ids, par, brano, ds, cand, r.get('proposto_tipo_citazione') or '', ds_principi, ds_seguito)
        # PROPOSTA PROVVISORIA (01/10/2026): senza lettura di DeepSeek, solo paragrafi e reranker; si sostituisce da sola
        campi['proposta_provvisoria'] = d.id not in ds
        # senza lettura «nessuno» non e' una proposta: la macchina non ha ancora letto. Resta vuota fino alla lettura.
        if campi['proposta_provvisoria'] and campi.get('proposto_principi') == ['nessuno']:
            campi['proposto_principi'] = []
        if ds_seguito is not None and d.id in ds_seguito:
            conti['seguito riletto (L07)'] += 1
        if ds_principi is not None:
            conti['principi da L04' if d.id in ds_principi else 'principi da L05 (manca L04)'] += 1
        spuntati, vic = campi['proposto_principi'], campi['proposto_estensione']
        scritture.append((d.reference, campi))
        conti['da scrivere'] += 1
        conti['con principio spuntato' if spuntati and spuntati != ['nessuno'] else ('nessuno' if spuntati else 'senza proposta')] += 1
        conti['con seguito proposto' if any(v['prosegue'] for v in vic) else 'senza seguito'] += 1
    print(json.dumps(dict(conti), ensure_ascii=False, indent=1))
    if scritture:
        print('esempio:', json.dumps(scritture[0][1], ensure_ascii=False)[:700])
    if a.salva:
        json.dump({ref.id: c for ref, c in scritture}, open(a.salva, 'w', encoding='utf-8'), ensure_ascii=False, default=str)
        print('proposte salvate in', a.salva)
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
