"""C03: CORPO E NOTA, TRADUZIONI, CONTATI UNA VOLTA (04/10/2026; il PI: «assolutamente va fatto e va detto che e' stato
applicato C03»). Senza --scrivi e' un'ANTEPRIMA: scrive solo gli elenchi, niente in banca dati.

   LE COPPIE.
     testo/nota   due righe vive per nome dello stesso caso, nello stesso atto, a non piu' di una pagina di distanza, con
                  la stessa frase sostenuta (testo normalizzato, rapidfuzz ratio >= 95, almeno 40 caratteri): sono la
                  menzione nel testo e la nota che la stessa frase chiama (o la stessa citazione trovata due volte).
                  DUE NOTE con la stessa frase (note consecutive) restano distinte: si unisce solo se una e' nel testo.
                  RIGA DEL TESTO = quella il cui punto (char_start) cade dentro la frase sostenuta (proposto_frase_offset);
                  altrimenti quella con proposto_posizione «corpo»; altrimenti la prima nell'atto.
     traduzione   la prova 8 di tools/descrittiva_stretta.py: stesso atto in un'altra lingua della stessa causa, pagine
                  entro il 15%, stesso punto relativo entro il 3%, meta' dei numeri attorno in comune.
                  SI TIENE la riga nella LINGUA ORIGINALE DELL'ATTO: quella la cui lingua (riconosciuta dal testo) e' la
                  prima di `lingue` nell'intestazione del Markdown della causa; se nessuna o tutte e due, la prima
                  (codice piu' basso).
   Una coppia in cui il team ha giudicato una delle due righe (esito, o giudizio di settembre) NON si scrive: va in
   training/esclusioni/C03_giudicate_da_rivedere.tsv, da rivedere una per una.

   CHE COSA SCRIVE con --scrivi (copia intera prima, con copia_prima.py; se non si rilegge, niente scritto):
     sulla riga che esce   proposto_rete 'esclusa', esclusa_rete_prima, esclusa_regola 'C03', unita_a <codice tenuto>,
                           esclusa_motivo, esclusa_da, esclusa_il
     sulla riga tenuta     testo/nota: proposto_nota_appoggio {codice, testo, paragrafi} e proposto_paragrafi uniti;
                           traduzione: proposto_traduzioni_unite [codici]; c03_da, c03_il (provenienza)
   Si rimette con tools/rimetti_righe.py (che toglie i campi esclusa_*; unita_a e i campi d'appoggio restano da togliere a
   mano, sono descritti qui).

   Uso:  .venv/bin/python tools/unisci_c03.py (--banca <fotografia.json.gz> | --vivo) --da "..." [--scrivi]
"""
import argparse, collections, csv, datetime, gzip, json, pathlib, re, sys, unicodedata

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
import descrittiva_stretta as D  # noqa: E402
from rapidfuzz import fuzz  # noqa: E402

ATTIVE = ('lessicale', 'entrambe', 'descrittiva')
LINGUE = {'english': 'en', 'german': 'de', 'french': 'fr', 'spanish': 'es', 'portuguese': 'pt', 'dutch': 'nl',
          'italian': 'it', 'korean': 'ko', 'japanese': 'ja', 'chinese': 'zh'}
PARAGRAFI = re.compile(r'(?:para(?:s|graph)?s?\.?|¶¶?|§§?|Rn\.|Rdnr\.|par\.|r\.o\.)\s*(\d+(?:\.\d+)*(?:\s*[-–]\s*\d+)?)', re.I)
ELENCHI = QUI/'training'/'esclusioni'


def norm(s):
    s = unicodedata.normalize('NFKC', s or '').lower()
    return re.sub(r'\s+', ' ', re.sub(r'[^\w]+', ' ', s)).strip()


def giudicata(r):
    return bool(r.get('esito') or r.get('settembre'))


def nel_testo(r):
    o = r.get('proposto_frase_offset')
    try:
        return isinstance(o, list) and len(o) == 2 and int(o[0]) <= int(r.get('char_start') or -1) <= int(o[1])
    except (TypeError, ValueError):
        return False


def chi_e_il_testo(x, y):
    """(testo, nota) fra due righe della stessa citazione"""
    if nel_testo(x) != nel_testo(y):
        return (x, y) if nel_testo(x) else (y, x)
    if (x.get('proposto_posizione') == 'corpo') != (y.get('proposto_posizione') == 'corpo'):
        return (x, y) if x.get('proposto_posizione') == 'corpo' else (y, x)
    return (x, y) if int(x.get('char_start') or 0) <= int(y.get('char_start') or 0) else (y, x)


def lingua_originale(r):
    t = D.testo(r['file'])[:6000]
    m = re.search(r"^lingue:\s*'?([^'\n]*)", t, re.M)
    prima = (m.group(1).split(';')[0].strip().lower() if m else '')
    return LINGUE.get(prima)


def coppie(banca):
    """[(tipo, tenuta, esce, motivo)] su tutte le righe vive per nome"""
    per = collections.defaultdict(list)
    for i, r in banca.items():
        if r.get('proposto_rete') in ATTIVE and r.get('codice'):
            per[(r['document_id'], r['caso_citato'])].append(r)
    out, visti = [], set()
    # testo/nota: stessa frase sostenuta
    for (doc, caso), rr in per.items():
        fr = [(r, norm(r.get('proposto_frase_sostenuta'))) for r in rr]
        fr = [(r, f) for r, f in fr if len(f) >= 40]
        for a in range(len(fr)):
            for c in range(a + 1, len(fr)):
                x, fx = fr[a]; y, fy = fr[c]
                try:
                    if abs(int(x.get('proposto_pagina') or 0) - int(y.get('proposto_pagina') or 0)) > 1:
                        continue
                except (TypeError, ValueError):
                    continue
                if fx != fy and fuzz.ratio(fx, fy) < 95:
                    continue
                t, n = chi_e_il_testo(x, y)
                # due NOTE con la stessa frase (note consecutive chiamate dalla stessa frase) sono citazioni distinte,
                # come vuole la regola di S07: restano tutte e due. Si unisce solo se una e' nel testo.
                if not (nel_testo(t) or t.get('proposto_posizione') == 'corpo'):
                    continue
                if n['codice'] in visti:
                    continue
                visti.add(n['codice'])
                out.append(('testo_nota', t, n, f"stessa frase sostenuta di {t['codice']} (p. {t.get('proposto_pagina')}): "
                                               f"la nota {n['codice']} e' la stessa citazione del testo"))
    # traduzioni
    per_doc, per_causa = collections.defaultdict(list), collections.defaultdict(dict)
    for i, r in banca.items():
        if r.get('proposto_rete') in ATTIVE and r.get('file'):
            per_doc[(r['document_id'], r['caso_citato'])].append((i, r))
            per_causa[(r['case_id'], r['caso_citato'])][r['document_id']] = r['file']
    cod = {r.get('codice'): r for r in banca.values() if r.get('codice')}
    for i, r in banca.items():
        if r.get('proposto_rete') not in ATTIVE or r.get('codice') in visti:
            continue
        m = D.identita(i, r, per_doc, per_causa, quali=('8',))
        if not m:
            continue
        altra = cod.get(re.search(r'stesso punto di (\S+)', m).group(1))
        if not altra or altra.get('codice') in visti:
            continue
        lo = lingua_originale(r)
        la, lb = D.lingua(r['file']), D.lingua(altra['file'])
        if lo and (la == lo) != (lb == lo):
            tieni, esce = (r, altra) if la == lo else (altra, r)
            regola = f'lingua originale dell atto ({lo})'
        else:
            tieni, esce = sorted((r, altra), key=lambda z: z['codice'])
            regola = 'lingua originale non nota o uguale: la prima'
        if esce['codice'] in visti:
            continue
        visti.add(esce['codice'])
        out.append(('traduzione', tieni, esce, f"traduzione dello stesso atto: la stessa citazione e' {tieni['codice']} "
                                              f"in {D.lingua(tieni['file'])} ({regola})"))
    return out


def coppie_rivedute(banca, elenco):
    """[(tipo, tenuta, esce, motivo)] dalle coppie RILETTE A MANO (05/10/2026, il PI: si scrive solo il deciso a mano).

    `elenco` e' training/esclusioni/C03_da_scrivere_RIVISTO.tsv (da training/misure/c03_revisione_coppie_2026-10-04/
    unisci.py): solo le coppie UNIRE, con la riga da tenere scelta leggendo l'atto. La regola automatica qui non decide
    niente: sbagliava la lingua originale in 46 traduzioni su 105 (l'intestazione mette l'inglese per primo).
    Controlli: una riga che esce in due coppie esce una volta; una catena (A tiene B, B tiene C) si chiude sulla riga
    finale; una riga gia' esclusa, scartata dal team o assente non si tiene mai e la coppia si salta, detto a schermo.
    """
    cod = {r.get('codice'): r for r in banca.values() if r.get('codice')}
    righe = list(csv.DictReader(open(elenco, encoding='utf-8'), delimiter='\t'))
    tenuta_di = {x['codice_che_esce']: x['codice_tenuto'] for x in righe}

    def finale(c, passi=0):
        return finale(tenuta_di[c], passi + 1) if c in tenuta_di and passi < 10 else c

    out, visti, saltate = [], set(), collections.Counter()
    for x in righe:
        t, n = cod.get(finale(x['codice_tenuto'])), cod.get(x['codice_che_esce'])
        if not t or not n or t is n:
            saltate['riga assente o catena chiusa su se stessa'] += 1; continue
        if n['codice'] in visti:
            saltate['riga che esce gia\' in un\'altra coppia'] += 1; continue
        if t.get('proposto_rete') not in ATTIVE or t.get('esito') == 'scartata':
            saltate['riga da tenere non viva o scartata'] += 1; continue
        if n.get('proposto_rete') not in ATTIVE:
            saltate['riga che esce gia\' esclusa'] += 1; continue
        visti.add(n['codice'])
        out.append((x['tipo'], t, n, x['motivo']))
    for k, v in saltate.items():
        print(f'saltate ({k}): {v}')
    return out


def appoggio(t, n):
    testo = n.get('proposto_citazione_testuale') or n.get('finestra_pagina') or ''
    par = sorted({m.group(0).strip() for m in PARAGRAFI.finditer(testo[:1500])})
    return {'codice': n['codice'], 'testo': re.sub(r'\s+', ' ', testo)[:1200], 'paragrafi': par}


def leggi_vivo():
    from google.cloud import firestore   # sola lettura
    db = firestore.Client(project='climpact-drp'); banca = {}
    for caso in ('urgenda', 'neubauer', 'future-generations', 'klimaseniorinnen', 'cig-parere-clima', 'idh-oc-32-25'):
        for d in db.collection('corpus_rows').where(filter=firestore.FieldFilter('caso_citato', '==', caso)).stream():
            banca[d.id] = json.loads(json.dumps(d.to_dict(), default=str))
    return banca


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--banca', default=''); ap.add_argument('--vivo', action='store_true')
    ap.add_argument('--da', required=True); ap.add_argument('--scrivi', action='store_true')
    ap.add_argument('--uscita', default=str(ELENCHI/'C03_da_scrivere.tsv'))
    ap.add_argument('--giudicate', default=str(ELENCHI/'C03_giudicate_da_rivedere.tsv'))
    ap.add_argument('--rivisto', default='', help="elenco riletto a mano (C03_da_scrivere_RIVISTO.tsv): si scrive solo "
                                                  "quello, giudicate comprese (gia' riviste una per una)")
    a = ap.parse_args()
    banca = json.load(gzip.open(a.banca, 'rt', encoding='utf-8')) if a.banca else leggi_vivo()
    id_di = {r.get('codice'): i for i, r in banca.items() if r.get('codice')}
    if a.rivisto:
        cc = coppie_rivedute(banca, a.rivisto)
        libere, giud = cc, []
        a.uscita = str(ELENCHI/'C03_da_scrivere_RIVISTO_controllato.tsv')
    else:
        cc = coppie(banca)
        libere = [c for c in cc if not (giudicata(c[1]) or giudicata(c[2]))]
        giud = [c for c in cc if giudicata(c[1]) or giudicata(c[2])]
    for f, el in ((a.uscita, libere), (a.giudicate, giud)):
        with open(f, 'w', newline='', encoding='utf-8') as h:
            w = csv.writer(h, delimiter='\t')
            w.writerow(['tipo', 'codice_tenuto', 'codice_che_esce', 'giudizio_tenuto', 'giudizio_che_esce', 'motivo'])
            for tipo, t, n, mot in el:
                w.writerow([tipo, t['codice'], n['codice'], t.get('esito') or ('settembre' if t.get('settembre') else ''),
                            n.get('esito') or ('settembre' if n.get('settembre') else ''), mot])
    k = collections.Counter(c[0] for c in libere); g = collections.Counter(c[0] for c in giud)
    print(f'coppie: {len(cc)} | da scrivere {len(libere)} {dict(k)} | giudicate, da rivedere {len(giud)} {dict(g)}')
    print('elenchi:', a.uscita, a.giudicate)
    if not a.scrivi:
        print('ANTEPRIMA: niente scritto in banca dati'); return
    from google.cloud import firestore
    import copia_prima
    db = firestore.Client(project='climpact-drp'); prima, campi = {}, {}
    ora = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
    for tipo, t, n, mot in libere:
        it, ine = id_di[t['codice']], id_di[n['codice']]
        prima[ine] = banca[ine]; prima.setdefault(it, banca[it])
        campi[ine] = {'proposto_rete': 'esclusa', 'esclusa_rete_prima': n.get('proposto_rete'), 'esclusa_regola': 'C03',
                      'unita_a': t['codice'], 'esclusa_motivo': 'C03 ' + mot, 'esclusa_da': a.da,
                      'esclusa_il': firestore.SERVER_TIMESTAMP}
        ct = campi.setdefault(it, {'c03_da': a.da, 'c03_il': firestore.SERVER_TIMESTAMP})
        if tipo == 'testo_nota':
            ct.setdefault('proposto_nota_appoggio', []).append(appoggio(t, n))
            ct['proposto_paragrafi'] = sorted(set(ct.get('proposto_paragrafi') or t.get('proposto_paragrafi') or [])
                                              | set(n.get('proposto_paragrafi') or []))
        else:
            ct.setdefault('proposto_traduzioni_unite', []).append(n['codice'])
    p = copia_prima.salva('unisci_c03', 'tutti', prima, campi, ciclo='esclusioni')
    b = db.batch(); k = 0
    for rid, c in campi.items():
        b.update(db.collection('corpus_rows').document(rid), c); k += 1
        if k % 400 == 0:
            b.commit(); b = db.batch()
    b.commit(); print('scritte', len(campi), 'righe | copia', p, '|', ora)


if __name__ == '__main__':
    if '--scrivi' in sys.argv:
        import giornale
        giornale.avvia()
    main()
