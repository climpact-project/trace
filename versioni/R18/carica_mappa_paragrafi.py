"""I PRINCIPI DALLA MAPPA DEI PARAGRAFI, RICARICATI DA SOLI SULLE RIGHE VIVE (08/10/2026).

   PERCHE'. Il 06/10 un'esecuzione di principi_da_paragrafi.py con --sonde P09 ha scritto il file del parere CIG
   attraverso un collegamento (cig-parere-clima_da_paragrafi_P09.jsonl -> il file principale), e la mappa non aveva
   ancora il campo sonde_P09: le 1.592 righe ICJ sono state composte senza nessun principio dai paragrafi. L'8/10 il PI
   ha approvato la mappa P09 (codice R18). Rifare tutta la composizione (carica_ripresa.py) vorrebbe dire rileggere
   letture di giri diversi (R11, R15, R16, con etichette diverse) e cambiare anche frasi, prove e pagine: qui si cambia
   SOLO quello che dipende dalla mappa, con la stessa regola di composizione di carica_ripresa.proposta_r11 (R11-R16):
     proposto_paragrafi, proposto_principi_da_mappa, proposto_principi_fonti («paragrafo» tolto e rimesso),
     provenienza.principi (il codice della mappa al posto del vecchio), proposto_principi = principi dei paragrafi +
     principi della lettura (+ «altro»), «nessuno» se vuoto o menzione in catena; proposto_principi_senza_prova e
     proposto_prova_mancante rifatti come in proposta_r11; in proposto_estensione la regola del filtro: una pagina
     che prosegue con un principio non spuntato non prosegue, e una pagina che il filtro aveva fermato solo per
     questo (voti di maggioranza, prova trovata, principio ora spuntato) torna a proseguire.
   Le letture non si toccano: la parte della lettura e' quella che la riga porta (proposto_principi_fonti «lettura»).
   Prima di scrivere si controlla che la regola, con la mappa che la riga ha oggi, ridia proprio la proposta di oggi:
   una riga che non torna (toccata dopo da altro) non si scrive e finisce nell'elenco.

   FUORI: le righe giudicate (esito: proposte e validato_* restano come sono; nell'elenco quelle in cui la mappa
   cambierebbe la proposta), le righe escluse o non per nome/descrizione, le righe mai composte con R11-R16 (senza
   lettura: carica_ripresa non le tocca). Le righe del campione cieco si scrivono come le altre (il banco nasconde
   le proposte), e si contano a parte.

   Uso:  .venv/bin/python tools/carica_mappa_paragrafi.py --caso cig-parere-clima            ANTEPRIMA
         .venv/bin/python tools/carica_mappa_paragrafi.py --caso cig-parere-clima --scrivi   scrive (copia prima)
"""
import argparse, collections, json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import casi_registro  # noqa: E402
import maggioranza as M  # noqa: E402

QUI = pathlib.Path(__file__).resolve().parent.parent
P = QUI/'training'/'principi'
COMPOSTE = ('R11', 'R12', 'R13', 'R14', 'R15', 'R16')
RETI = ('lessicale', 'entrambe', 'descrittiva')
CODICI_MAPPA = {'R01', 'R04', 'R06', 'R07', 'R09', 'R17', 'R18'}


def componi(ids, fonti, vecchi, catena):
    """proposto_principi come in proposta_r11: paragrafo o lettura, piu' «altro» se c'era; «nessuno» se vuoto/catena"""
    sp = [p for p in ids if 'paragrafo' in fonti.get(p, []) or 'lettura' in fonti.get(p, [])]
    if 'altro' in (vecchi or []):
        sp.append('altro')
    return ['nessuno'] if (not sp or catena) else sp


def senza_prova(ids, sp, fonti, frase_esito, vic):
    return [p for p in sp if p in ids and 'lettura' in fonti.get(p, []) and 'paragrafo' not in fonti.get(p, [])
            and frase_esito != 'trovata' and not any(v.get('prosegue') and v.get('principio') == p for v in vic)]


def nuovi_campi(r, ids, par, codice, uniti=()):
    """-> (campi da scrivere, note) o (None, motivo) se la riga non torna. `uniti`: i paragrafi delle righe unite a questa
    (C03, S08: unita_a = il suo codice), che restano in proposto_paragrafi come li unisce unisci_c03/scrivi_s08"""
    fonti0 = {k: list(v) for k, v in (r.get('proposto_principi_fonti') or {}).items()}
    catena = str(r.get('proposto_principi_motivo') or '').startswith('Menzione in catena')
    pp0 = r.get('proposto_principi')
    if componi(ids, fonti0, pp0, catena) != pp0:
        return None, 'la regola non ridà la proposta di oggi'
    da_par = set(par.get('principi', []))
    fonti = collections.defaultdict(list)
    for p in sorted(set(fonti0) | da_par, key=lambda q: (ids.index(q) if q in ids else len(ids), q)):
        for f in ('paragrafo', 'lettura', 'reranker'):
            if (f == 'paragrafo' and p in da_par) or (f != 'paragrafo' and f in fonti0.get(p, [])):
                fonti[p].append(f)
        for f in fonti0.get(p, []):
            if f not in ('paragrafo', 'lettura', 'reranker') and f not in fonti[p]:
                fonti[p].append(f)
    fonti = {k: v for k, v in fonti.items() if v}
    sp = componi(ids, fonti, pp0, catena)
    vic0 = r.get('proposto_estensione') or []
    vic, riprese = [], []
    for v in vic0:
        v = dict(v)
        pr = v.get('principio')
        if sp == ['nessuno']:
            v['prosegue'] = False
        elif v.get('prosegue') and pr and pr not in sp:
            v['prosegue'] = False
        elif not v.get('prosegue') and pr in sp and pr not in (pp0 or []) and v.get('prova_esito') == 'trovata' and v.get('testuale'):
            try:
                k, n = (int(x) for x in str(v.get('voti')).split('/'))
            except ValueError:
                k, n = 0, 0
            if n and k >= M.soglia(n):      # la maggioranza e la prova trovata: il filtro l'aveva fermata solo per il principio
                v['prosegue'] = True; riprese.append(v.get('pagina'))
        vic.append(v)
    sp_senza = senza_prova(ids, sp, fonti, r.get('proposto_frase_esito'), vic)
    prov0 = ((r.get('provenienza') or {}).get('principi') or {})
    prov = {}
    for p, ff in fonti.items():
        tenere = [x for x in prov0.get(p, []) if x not in CODICI_MAPPA]
        prov[p] = sorted(set(tenere) | ({codice} if 'paragrafo' in ff else set()))
    if 'altro' in sp and 'altro' not in prov and 'altro' in prov0:
        prov['altro'] = prov0['altro']
    campi = {'proposto_paragrafi': sorted(set(par.get('paragrafi', [])) | set(uniti)) if uniti else par.get('paragrafi', []),
             'proposto_principi_da_mappa': [p for p in ids if 'paragrafo' in fonti.get(p, [])],
             'proposto_principi_fonti': fonti, 'provenienza.principi': prov, 'proposto_principi': sp,
             'proposto_principi_senza_prova': sp_senza, 'proposto_prova_mancante': bool(sp_senza),
             'proposto_estensione': vic}
    return campi, {'riprese': riprese}


def valore_oggi(r, k):
    if k.startswith('provenienza.'):
        return (r.get('provenienza') or {}).get(k.split('.', 1)[1])
    return r.get(k)


def uguale(a, b):
    return json.dumps(a, sort_keys=True, ensure_ascii=False, default=str) == json.dumps(b, sort_keys=True, ensure_ascii=False, default=str)


def main():
    import sonde as S
    import yaml
    ap = argparse.ArgumentParser(); ap.add_argument('--caso', required=True); ap.add_argument('--scrivi', action='store_true')
    ap.add_argument('--elenco', default='', help='file JSON con il dettaglio (righe, giudicate, pagine riprese)')
    a = ap.parse_args(); caso = a.caso
    ids = [q['id'] for q in yaml.safe_load(open(S.file_caso(caso), encoding='utf-8'))['semantic_queries']]
    fpar = P/f'{caso}_da_paragrafi{S.suf(caso)}.jsonl'
    if fpar.is_symlink():
        raise SystemExit(f'{fpar} e\' un collegamento: niente scritto (il difetto del 06/10)')
    par = {json.loads(l)['id']: json.loads(l) for l in open(fpar, encoding='utf-8')}
    codice = {'P03': 'R06', 'P05': 'R07'}.get(S.serie(caso)) or casi_registro.CODICE_MAPPA.get(caso, 'R04')
    from google.cloud import firestore
    db = firestore.Client(project='climpact-drp')
    righe = {d.id: (d.reference, d.to_dict()) for d in db.collection('corpus_rows').where(filter=firestore.FieldFilter('caso_citato', '==', caso)).stream()}
    # LE RIGHE UNITE (08/10/2026): unisci_c03 e scrivi_s08 mettono nella riga tenuta anche i paragrafi della riga che esce;
    # qui si tengono (quelli che la riga che esce porta e quelli che la mappa nuova le da')
    uniti = collections.defaultdict(set)
    for rid, (_, r) in righe.items():
        if r.get('unita_a'):
            uniti[r['unita_a']] |= set(r.get('proposto_paragrafi') or []) | set(par.get(rid, {}).get('paragrafi', []))
    conti = collections.Counter(); per_sonda = collections.defaultdict(collections.Counter)
    scritture, prima, elenco = [], {}, {'giudicate_con_mappa_diversa': [], 'non_tornano': [], 'pagine_riprese': [], 'mai_composte_con_mappa': []}
    for rid, (ref, r) in sorted(righe.items()):
        if r.get('proposto_rete') not in RETI:
            conti['esclusa o fuori rete (non toccata)'] += 1; continue
        pz = par.get(rid, {})
        if r.get('esito'):
            conti['giudicata (non toccata)'] += 1
            if set(pz.get('principi', [])) != set(r.get('proposto_principi_da_mappa') or []):
                elenco['giudicate_con_mappa_diversa'].append({'id': rid, 'codice': r.get('codice'), 'esito': r.get('esito'),
                                                              'proposto_principi': r.get('proposto_principi'), 'mappa': pz.get('principi', []),
                                                              'validato_principi': r.get('validato_principi')})
            continue
        if (r.get('provenienza') or {}).get('composizione') not in COMPOSTE or r.get('proposto_principi') is None:
            conti['mai composta con R11-R16 (non toccata)'] += 1
            if pz.get('principi'):
                elenco['mai_composte_con_mappa'].append({'id': rid, 'codice': r.get('codice'), 'mappa': pz['principi']})
            continue
        campi, nota = nuovi_campi(r, ids, pz, codice, uniti.get(r.get('codice'), ()))
        if campi is None:
            conti['non torna (non toccata)'] += 1; elenco['non_tornano'].append({'id': rid, 'codice': r.get('codice'), 'motivo': nota}); continue
        cambiati = [k for k, v in campi.items() if not uguale(valore_oggi(r, k), v)]
        if not cambiati:
            conti['invariata'] += 1; continue
        vecchi, nuovi = set(r.get('proposto_principi') or []), set(campi['proposto_principi'])
        cieca = bool(r.get('campione_cieco'))
        if vecchi != nuovi:
            conti['proposto_principi cambia'] += 1
            conti['proposto_principi cambia, campione cieco'] += cieca
            for p in nuovi - vecchi:
                per_sonda[p]['aggiunta'] += 1
            for p in vecchi - nuovi:
                per_sonda[p]['tolta'] += 1
        if nota['riprese']:
            elenco['pagine_riprese'].append({'id': rid, 'codice': r.get('codice'), 'pagine': nota['riprese']})
            conti['pagine attorno che tornano a proseguire'] += len(nota['riprese'])
        conti['da scrivere'] += 1; conti['da scrivere, campione cieco'] += cieca
        conti['con principio dai paragrafi'] += bool(campi['proposto_principi_da_mappa'])
        scritture.append((ref, campi)); prima[rid] = r
    print(json.dumps(dict(conti), ensure_ascii=False, indent=1))
    print('per sonda:', json.dumps({k: dict(v) for k, v in sorted(per_sonda.items())}, ensure_ascii=False, indent=1))
    print('giudicate in cui la mappa cambierebbe la proposta:', len(elenco['giudicate_con_mappa_diversa']))
    if a.elenco:
        json.dump({'conti': dict(conti), 'per_sonda': {k: dict(v) for k, v in per_sonda.items()}, **elenco},
                  open(a.elenco, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
        print('dettaglio in', a.elenco)
    if not a.scrivi:
        print('ANTEPRIMA: niente scritto'); return
    if not scritture:
        return
    import copia_prima    # la copia intera di prima: se non riesce, niente scritto
    copia_prima.salva('carica_mappa_paragrafi', caso, prima, {ref.id: c for ref, c in scritture}, ciclo='ripresa')
    for i in range(0, len(scritture), 400):
        b = db.batch()
        for ref, c in scritture[i:i + 400]:
            b.update(ref, c)
        b.commit()
    print(f'scritte {len(scritture)} righe')
    # rilettura: ogni campo scritto dev'essere quello calcolato
    male = 0
    for ref, c in scritture:
        r = ref.get().to_dict()
        male += any(not uguale(valore_oggi(r, k), v) for k, v in c.items())
    print('rilettura:', 'tutte uguali' if not male else f'{male} righe diverse da quanto scritto')
    if male:
        raise SystemExit(1)


if __name__ == '__main__':
    import giornale  # il giornale delle operazioni (02/10/2026)
    giornale.avvia()
    main()
