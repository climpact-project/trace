"""C07 APPLICATA (04/10/2026; il PI: «si', applica C07»). Senza --scrivi e' un'ANTEPRIMA: scrive solo gli elenchi.

   PER OGNI RIGA VIVA per nome e per ogni pagina attorno marcata C07 (controlli_automatici.pagine_gia_citate: un'altra
   riga viva dello stesso caso nello stesso atto sulla pagina, per posizione o per testo, SENZA principi in comune):
     1. sulla voce di proposto_estensione: c07 = true, c07_altra_riga = <codice> (la prima), c07_segno = «also cited
        separately as ...». `prosegue` resta com'era (la lettura di DeepSeek non si cancella): la composizione e la mappa
        trattano la voce come NON seguito (aggiorna_dati_mappa.voce: da cambiare insieme, vedi sotto).
     2. principi: un principio P della riga si TOGLIE se TUTTE queste cose sono vere:
          a. P e' in proposto_principi;
          b. P viene da una pagina marcata C07 che prosegue (voce con principio == P e prosegue);
          c. P NON viene da nessun'altra pagina attorno che prosegue e non e' marcata C07;
          d. P NON e' nella mappa dei paragrafi citati dalla riga (proposto_principi_da_mappa);
          e. P NON e' retto dalle letture della riga sul suo passaggio e sulla sua frase sostenuta: in
             proposto_principi_voti ha meno di 3 voti su 5 (la soglia di R11).
        E solo se L'ALTRA RIGA HA P: la pagina porta P alla citazione B, che ce l'ha gia'. Se l'altra riga NON ha P, il
        principio NON si toglie da A e non si sposta su B: va nell'elenco per il team (C07_principi_per_il_team.tsv).
        Un principio tolto finisce in principi_tolti_c07 [{principio, pagina, altra_riga, motivo}].
     3. le righe giudicate dal team (esito, o giudizio di settembre) NON si toccano: C07_giudicate_saltate.tsv.
     4. copia intera prima (copia_prima.py); provenienza c07_da, c07_il su ogni riga scritta.

   LE PAGINE CHE DEEPSEEK DICEVA «PROSEGUE» (circa 1.190) NON si applicano in automatico: il PI le vuole rilette a mano
   (sessione «TRACE: Rilettura C07 prosegue», training/misure/C07-RILETTURA-PROSEGUE-2026-10-04.tsv). Senza --rilette
   vanno solo in C07_prosegue_da_rileggere.tsv, e i principi (che vengono solo da pagine che proseguono) non si toccano.
   Con --rilette <file> si applicano anche le pagine «prosegue» che la rilettura dice ALTRA CITAZIONE: il file ha le
   colonne codice, pagina, esito (esito «altra_citazione», o una parola che comincia con «altra»).

   Uso:  .venv/bin/python tools/applica_c07.py (--banca <fotografia.json.gz> | --vivo) --da "..." [--rilette <tsv>] [--scrivi]
"""
import argparse, collections, csv, datetime, gzip, json, pathlib, re, sys

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
import controlli_automatici as K  # noqa: E402

D = K.D
PAG = re.compile(r'<!-- page (\d+) -->')
EL = QUI/'training'/'esclusioni'
SOGLIA_VOTI = 3


def spazi(f):
    t = D.testo(f); ms = list(PAG.finditer(t)); sp = {}
    for k, m in enumerate(ms):
        sp[int(m.group(1))] = (m.end(), ms[k + 1].start() if k + 1 < len(ms) else len(t))
    return sp


def voti(r, p):
    v = (r.get('proposto_principi_voti') or {}).get(p)
    try:
        return int(str(v).split('/')[0])
    except (TypeError, ValueError):
        return 0


def giudicata(r):
    return bool(r.get('esito') or r.get('settembre'))


def calcola(banca, rilette=None):
    """(scritture {id: campi}, tolti [..], per_il_team [..], saltate [..], segni)"""
    per = collections.defaultdict(list)
    for i, r in banca.items():
        if r.get('document_id') and r.get('proposto_rete') in K.ATTIVE:
            per[(r['document_id'], r['caso_citato'])].append(r)
    cod = {r.get('codice'): r for r in banca.values() if r.get('codice')}
    cache = {}
    scritture, tolti, team, saltate, da_rileggere = {}, [], [], [], []
    segni = 0
    for i, r in banca.items():
        if r.get('proposto_rete') not in K.ATTIVE or not r.get('proposto_estensione'):
            continue
        f = r['file']
        if f not in cache:
            cache[f] = spazi(f)
        m = K.pagine_gia_citate(r, per[(r['document_id'], r['caso_citato'])], cache[f])
        m = {p: v for p, v in m.items() if not v['seguito']}            # solo principio diverso (decisione del PI)
        prosegue = {e.get('pagina') for e in r['proposto_estensione'] if e.get('prosegue')}
        for p in [p for p in m if p in prosegue]:
            if rilette is None or (r['codice'], p) not in rilette:
                da_rileggere.append((r['codice'], p, m[p]['codici'][0], r.get('esito') or ('settembre' if r.get('settembre') else '')))
                del m[p]
        if not m:
            continue
        if giudicata(r):
            for p, v in m.items():
                saltate.append((r['codice'], p, v['codici'][0], r.get('esito') or 'settembre'))
            continue
        est = [dict(e) for e in r['proposto_estensione']]
        for e in est:
            if e.get('pagina') in m:
                v = m[e['pagina']]
                e['c07'] = True; e['c07_altra_riga'] = v['codici'][0]; e['c07_segno'] = v['segno']; segni += 1
        princ = list(r.get('proposto_principi') or [])
        mappa = set(r.get('proposto_principi_da_mappa') or [])
        da_altre = {e.get('principio') for e in est if e.get('prosegue') and not e.get('c07')}
        nuovi, via = [], []
        for P in princ:
            pag_c07 = [e for e in est if e.get('c07') and e.get('prosegue') and e.get('principio') == P]
            if not pag_c07 or P in da_altre or P in mappa or voti(r, P) >= SOGLIA_VOTI:
                nuovi.append(P); continue
            e = pag_c07[0]; B = cod.get(e['c07_altra_riga']) or {}
            if P in K._principi(B):
                via.append({'principio': P, 'pagina': e['pagina'], 'altra_riga': B.get('codice'),
                            'motivo': f"C07: viene solo dalla p. {e['pagina']}, che e' la citazione {B.get('codice')} "
                                      f"(ha gia' questo principio); non retto da mappa dei paragrafi ne' letture ({voti(r, P)}/5)"})
            else:
                nuovi.append(P)
                team.append((r['codice'], P, e['pagina'], e['c07_altra_riga'], ';'.join(sorted(K._principi(B)))))
        c = {'proposto_estensione': est}
        if via:
            c['proposto_principi'] = nuovi or ['nessuno']
            c['principi_tolti_c07'] = via
            tolti += [(r['codice'], r['caso_citato'], x['principio'], x['pagina'], x['altra_riga']) for x in via]
        scritture[i] = c
    return scritture, tolti, team, saltate, segni, da_rileggere


def spunte_team(banca, revisione):
    """{id: campi} per le righe GIUDICATE: le pagine spuntate «seguito» dal team che la revisione a mano dice citazione a se'.

    Il PI (05/10/2026): «se sono delle citazioni in loro non ha senso che restino li' spuntate». `revisione` e'
    training/misure/C07-REVISIONE-SEGUITI-2026-10-04.tsv (229 pagine lette una per una il 04/10): si prendono solo quelle
    con team_spunta_seguito = si e revisione = ALTRA CITAZIONE. Sulla riga: la pagina esce da validato_estensione, la voce
    di proposto_estensione prende il segno C07 con il codice dell'altra riga, e c07_spunte_tolte tiene la traccia
    {pagina, altra_riga, motivo} per rimetterla a mano. Niente altro cambia (principi e giudizio restano del team).
    """
    id_di = {r.get('codice'): i for i, r in banca.items() if r.get('codice')}
    scritture, saltate = {}, collections.Counter()
    for x in csv.DictReader(open(revisione, encoding='utf-8'), delimiter='\t'):
        if x['team_spunta_seguito'] != 'si' or not x['revisione'].upper().startswith('ALTRA'):
            continue
        i = id_di.get(x['riga'])
        if i is None:
            saltate['riga assente'] += 1; continue
        r, p = banca[i], int(x['pagina_attorno'])
        c = scritture.setdefault(i, {'validato_estensione': list(r.get('validato_estensione') or []),
                                     'proposto_estensione': [dict(e) for e in r.get('proposto_estensione') or []],
                                     'c07_spunte_tolte': list(r.get('c07_spunte_tolte') or [])})
        if p not in c['validato_estensione']:
            saltate['spunta gia\' tolta'] += 1; continue
        altra = x['altre_righe_sulla_pagina'].split(',')[0].strip()
        c['validato_estensione'].remove(p)
        for e in c['proposto_estensione']:
            if e.get('pagina') == p:
                e['c07'] = True; e['c07_altra_riga'] = altra; e['c07_segno'] = f'also cited separately as {altra}'
        c['c07_spunte_tolte'].append({'pagina': p, 'altra_riga': altra, 'motivo': 'C07 ' + x['motivo'][:300]})
    for k, v in saltate.items():
        print(f'spunte del team saltate ({k}): {v}')
    return scritture


def leggi_vivo():
    from google.cloud import firestore   # sola lettura
    db = firestore.Client(project='climpact-drp'); banca = {}
    for caso in ('urgenda', 'neubauer', 'future-generations', 'klimaseniorinnen', 'cig-parere-clima', 'idh-oc-32-25'):
        for d in db.collection('corpus_rows').where(filter=firestore.FieldFilter('caso_citato', '==', caso)).stream():
            banca[d.id] = json.loads(json.dumps(d.to_dict(), default=str))
    return banca


def esempi(banca, scr, a, n=10):
    """10 esempi con prima e dopo (seme fisso): prima quelli con un principio tolto, poi a caso"""
    import random
    ids = sorted(scr); random.Random(20261004).shuffle(ids)
    ids = sorted(ids, key=lambda i: 0 if scr[i].get('principi_tolti_c07') else 1)[:n]
    suf = '_IPOTESI' if a.ipotesi_tutte else ''
    with open(EL/f'C07_esempi{suf}.tsv', 'w', newline='', encoding='utf-8') as h:
        w = csv.writer(h, delimiter='\t'); w.writerow(['codice', 'pagine_prima', 'pagine_dopo', 'principi_prima', 'principi_dopo'])
        for i in ids:
            r, c = banca[i], scr[i]
            pre = ', '.join(f"p.{e['pagina']}{' (seguito)' if e.get('prosegue') else ''}" for e in r['proposto_estensione'])
            dop = ', '.join(f"p.{e['pagina']}" + (f" (altra citazione {e['c07_altra_riga']}, non seguito)" if e.get('c07') else (' (seguito)' if e.get('prosegue') else ''))
                            for e in c['proposto_estensione'])
            row = [r['codice'], pre, dop, ';'.join(r.get('proposto_principi') or []), ';'.join(c.get('proposto_principi', r.get('proposto_principi') or []))]
            w.writerow(row); print('ESEMPIO', ' | '.join(row))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--banca', default=''); ap.add_argument('--vivo', action='store_true')
    ap.add_argument('--da', required=True); ap.add_argument('--rilette', default=''); ap.add_argument('--ipotesi-tutte', action='store_true', help="SOLO ANTEPRIMA: come se la rilettura dicesse ALTRA CITAZIONE su tutte le «prosegue» (tetto massimo)"); ap.add_argument('--scrivi', action='store_true')
    ap.add_argument('--spunte-team', default='', help='C07-REVISIONE-SEGUITI-2026-10-04.tsv: toglie le spunte «seguito» del team '
                                                      'sulle pagine che la revisione a mano dice citazione a se\' (decisione del PI del 05/10)')
    a = ap.parse_args()
    banca = json.load(gzip.open(a.banca, 'rt', encoding='utf-8')) if a.banca else leggi_vivo()
    ril = None
    if a.rilette:
        ril = {(x['codice'], int(x['pagina'])) for x in csv.DictReader(open(a.rilette, encoding='utf-8'), delimiter='\t')
               if (x.get('esito') or '').strip().lower().startswith('altra')}
    if a.ipotesi_tutte:
        if a.scrivi:
            sys.exit('--ipotesi-tutte non si usa con --scrivi')
        class _Tutte(set):
            def __contains__(self, x): return True
        ril = _Tutte()
    scr, tolti, team, saltate, segni, da_ril = calcola(banca, ril)
    if a.spunte_team:
        sp = spunte_team(banca, a.spunte_team)
        assert not set(sp) & set(scr), 'una riga giudicata e\' finita anche fra quelle della regola'
        print(f'spunte del team tolte: {sum(len(c["c07_spunte_tolte"]) - len(banca[i].get("c07_spunte_tolte") or []) for i, c in sp.items())} '
              f'pagine su {len(sp)} righe giudicate')
        scr.update(sp)
    EL.mkdir(parents=True, exist_ok=True)
    for nome, testa, el in (('C07_principi_tolti.tsv', ['codice', 'caso', 'principio', 'pagina', 'altra_riga'], tolti),
                            ('C07_principi_per_il_team.tsv', ['codice', 'principio', 'pagina', 'altra_riga', 'principi_altra'], team),
                            ('C07_giudicate_saltate.tsv', ['codice', 'pagina', 'altra_riga', 'giudizio'], saltate),
                            ('C07_prosegue_da_rileggere.tsv', ['codice', 'pagina', 'altra_riga', 'giudizio'], da_ril)):
        with open(EL/nome, 'w', newline='', encoding='utf-8') as h:
            w = csv.writer(h, delimiter='\t'); w.writerow(testa); w.writerows(el)
    print(f'righe toccate {len(scr)} | segni {segni} | principi tolti {len(tolti)} | per il team {len(team)} | '
          f'giudicate saltate {len({x[0] for x in saltate})} righe ({len(saltate)} pagine) | «prosegue» tenute a parte {len(da_ril)}')
    print('tolti per caso:', dict(collections.Counter(x[1] for x in tolti)))
    print('tolti per principio:', collections.Counter(x[2] for x in tolti).most_common())
    esempi(banca, scr, a)
    if not a.scrivi:
        print('ANTEPRIMA: niente scritto in banca dati'); return
    from google.cloud import firestore
    import copia_prima
    db = firestore.Client(project='climpact-drp')
    for c in scr.values():
        c['c07_da'] = a.da; c['c07_il'] = firestore.SERVER_TIMESTAMP
    p = copia_prima.salva('applica_c07', 'tutti', {i: banca[i] for i in scr}, scr, ciclo='esclusioni')
    b = db.batch(); k = 0
    for rid, c in scr.items():
        b.update(db.collection('corpus_rows').document(rid), c); k += 1
        if k % 400 == 0:
            b.commit(); b = db.batch()
    b.commit(); print('scritte', len(scr), '| copia', p, '|', datetime.datetime.now().strftime('%d/%m/%Y %H:%M'))


if __name__ == '__main__':
    if '--scrivi' in sys.argv:
        import giornale
        giornale.avvia()
    main()
