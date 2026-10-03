"""LE RIGHE NUOVE DELLA RICERCA PER NOME S05: CONFRONTO CON LA PIATTAFORMA (02/10/2026).

   La stessa regola di `unisci_e_aggiungi.py` (S02/S03), con la ricerca S05 (`cerca_s05.py`, file dei casi
   `cited-cases/<caso>-S05.yaml`, CSV `index/nomi_<caso>_<data>-S05.csv`):
   - le corrispondenze del nome in ogni documento si raggruppano con la regola di `cerca.fondi`; le corrispondenze di
     S03 restano identiche (`cerca_s05.corrispondenze`, con le forme di S03 come ancora: `cited-cases/ancora-S03/`);
   - una riga della piattaforma (reti `lessicale` ed `entrambe`) copre le corrispondenze nei 200 caratteri dal suo
     inizio; nei documenti rifatti con l'OCR la sua posizione si traduce con `posizione_dopo_ocr.traduci`;
   - un gruppo che nessuna riga copre e che sta nel CSV (non tolto dal filtro della data ne' dalla deduplica) e' una
     RIGA NUOVA: codice dopo il piu' alto del caso, assegnata a turno a chi ha righe del caso da fare, una su cinque
     alla cieca. Stessa assegnazione di `unisci_e_aggiungi.py`.
   Due differenze, volute:
   - le righe gia' marcate `esclusa` (altre persone di nome Neubauer, per esempio) COPRONO il loro gruppo: altrimenti
     la regola le rimetterebbe in coda come righe nuove. `unisci_e_aggiungi.py` guarda solo `lessicale` ed `entrambe`;
   - NIENTE si unisce. Dove S05 lega due righe esistenti in un gruppo solo (una corrispondenza nuova in mezzo),
     `unisci_e_aggiungi.py` marcherebbe la seconda come `fusa`. Qui lo si conta e lo si elenca, ma le righe gia' in
     piattaforma restano come sono: le decisioni sulle righe esistenti non si prendono di passaggio.

   Per ogni riga nuova si scrive anche la CAUSA, cioe' il cambio minimo che la fa trovare:
     markdown_nuovo     il documento e' fra i 277 Markdown scritti da `build_markdown_s05.py`;
     gia_S03            una forma di S03 la trova gia' esatta: la riga manca in piattaforma per altre ragioni;
     normalizzazione    una forma di S03, ma spezzata, con spazi o trattini diversi (la trova solo la normalizzazione);
     forme_riammesse    «VKS», «Urgence climatique et (les) droits de l'homme»;
     forme_nuove        le forme proposte dalla misura e provate nel campione.

   Senza --scrivi non scrive niente in banca dati (Firestore si legge soltanto) e produce:
     training/s05/<caso>_righe_nuove.jsonl   le righe che si aggiungerebbero, con causa e codice provvisorio
     training/s05/<caso>_confronto.json      conti, righe orfane (in piattaforma ma non ritrovate), gruppi legati
   Con --scrivi (lo fa `ciclo_s05.sh`, dopo il si' del PI) aggiunge le righe nuove con `provenienza.estrazione = 'S05'`.

   Uso:  .venv/bin/python tools/unisci_s05.py [--caso urgenda] [--scrivi]
"""
import argparse, collections, csv, json, random, re, sys, pathlib
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
import cerca as S03                      # noqa: E402
import cerca_s05 as S05                  # noqa: E402
from pubblica import documento, id_riga  # noqa: E402
from posizione_dopo_ocr import traduci   # noqa: E402

PREFISSI = {'urgenda': 'URG', 'neubauer': 'NEU', 'future-generations': 'FGC', 'klimaseniorinnen': 'KLS', 'cig-parere-clima': 'ICJ', 'idh-oc-32-25': 'IAC'}
DATA = '2026-10-02'
USCITA = QUI/'training'/'s05'
RIAMMESSE = {'VKS', "Urgence climatique et droits de l'homme", "Urgence climatique et les droits de l'homme"}
CAUSE = ('markdown_nuovo', 'gia_S03', 'normalizzazione', 'forme_riammesse', 'forme_nuove')


def markdown_nuovi():
    f = QUI/'training'/'s05'/'markdown_s05_registro.json'
    if not f.exists():
        return set()
    return {d['markdown'] for d in json.load(open(f, encoding='utf-8'))['documenti'] if d.get('esito') == 'scritto'}


def causa(md_rel, gruppo, ancora, forme3, regole5, nuovi_md):
    """Il cambio minimo che fa trovare il gruppo (vedi in testa)."""
    if md_rel in nuovi_md:
        return 'markdown_nuovo', []
    if any(ancora.fullmatch(m.group(0)) for m in gruppo):
        return 'gia_S03', []
    trovate = []
    for m in gruppo:
        for f, rx in regole5:
            if rx.fullmatch(m.group(0)):
                trovate.append(f)
                break
    if any(f in forme3 for f in trovate):
        return 'normalizzazione', trovate
    if any(f in RIAMMESSE for f in trovate):
        return 'forme_riammesse', trovate
    return 'forme_nuove', trovate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--caso', default='')
    ap.add_argument('--scrivi', action='store_true')
    ap.add_argument('--data', default=DATA)
    ap.add_argument('--uscita', default='', help="cartella dei file prodotti (predefinita: training/s05)")
    a = ap.parse_args()
    global USCITA
    if a.uscita:
        USCITA = pathlib.Path(a.uscita) if pathlib.Path(a.uscita).is_absolute() else QUI/a.uscita
    data, esecuzione = a.data, f'nomi__{a.data}-S05'
    from google.cloud import firestore
    db = firestore.Client(project='climpact-drp')
    USCITA.mkdir(parents=True, exist_ok=True)
    nuovi_md = markdown_nuovi()
    for caso in ([a.caso] if a.caso else list(PREFISSI)):
        pre = PREFISSI[caso]
        f5 = QUI/'cited-cases'/f'{caso}-S05.yaml'
        # le forme di S03 dalla copia fissa (cited-cases/ancora-S03/): dopo il cambio il file vivo sara' quello S05
        conf5, conf3 = S05.leggi_caso(f5), S03.leggi_caso(S05.file_ancora(f5))
        patt5 = S05.regex_caso(conf5)
        ancora = S05.regex_ancora(conf3['forme'])
        forme3 = set(conf3['forme'])
        intere = set(conf5.get('forme_parola_intera') or [])
        regole5 = [(f, re.compile((f'(?<!{S05.LETTERA_ACCANTO})(?:{S05.forma_regex(f)})(?!{S05.LETTERA_ACCANTO})'
                                   if f in intere else S05.forma_regex(f)), re.I)) for f in conf5['forme']]
        tutte = [(d.reference, d.to_dict()) for d in db.collection('corpus_rows')
                 .where(filter=firestore.FieldFilter('caso_citato', '==', caso)).stream()]
        nominali = [(ref, r) for ref, r in tutte if r.get('proposto_rete') in ('lessicale', 'entrambe')]
        escluse = [(ref, r) for ref, r in tutte if r.get('proposto_rete') == 'esclusa']
        nuove_csv = list(csv.DictReader(open(QUI/'index'/f'nomi_{caso}_{data}-S05.csv', encoding='utf-8')))
        per_doc = collections.defaultdict(list)
        for ref, r in nominali + escluse:
            per_doc[r['document_id']].append((ref, r))
        csv_doc = collections.defaultdict(dict)
        for r in nuove_csv:
            csv_doc[r['document_id']][int(r['char_start'])] = r
        file_di = {r['document_id']: r['file'] for r in nuove_csv}
        for ref, r in nominali + escluse:
            file_di.setdefault(r['document_id'], r.get('file'))

        da_aggiungere, orfane, legate, gia_insieme, non_tradotte, coperti_da_esclusa = [], [], [], [], [], 0
        for doc in sorted(set(per_doc) | set(csv_doc)):
            md = QUI/file_di[doc]
            if not md.exists():
                orfane += [(ref, r, 'file del documento assente') for ref, r in per_doc.get(doc, [])]
                continue
            testo = md.read_text(encoding='utf-8', errors='replace')
            meta, inizio = S03.front_matter(testo)
            ms = S05.corrispondenze(testo, inizio, patt5, ancora)
            fuse = S05.fondi(testo, ms)
            inizi = {f[0].start() for f in fuse}
            gruppo_di, starts, g = {}, [], -1
            for m in ms:
                if m.start() in inizi:
                    g += 1; starts.append(m.start())
                gruppo_di[m.start()] = g
            membri = collections.defaultdict(list)
            for m in ms:
                membri[gruppo_di[m.start()]].append(m)
            # i gruppi di S03 sullo stesso testo: servono a dire quali gruppi con piu' righe nascono da S05
            m3 = list(ancora.finditer(testo, inizio))
            g3_di, k3 = {}, -1
            inizi3 = {f[0].start() for f in S03.fondi(testo, m3)}
            for m in m3:
                if m.start() in inizi3:
                    k3 += 1
                g3_di[m.start()] = k3
            coperti, per_gruppo = set(), collections.defaultdict(list)
            for ref, r in per_doc.get(doc, []):
                grezzo = int(r.get('char_start') or -1)
                cs = grezzo
                if cs >= 0:
                    cs, _ = traduci(file_di[doc], cs, ancora, bool((r.get('provenienza') or {}).get('ocr')))
                cov = [m for m in ms if cs <= m.start() < cs + S03.FUSIONE]
                if not cov and cs != grezzo and any(m.start() == grezzo for m in ms):
                    # RIGA NATA SUL TESTO OCR SENZA `provenienza.ocr` (URG-1741..1743, 02/10/2026): la sua posizione e' gia'
                    # quella del testo nuovo, e tradurla di nuovo la sposta. Se una corrispondenza comincia esattamente li',
                    # la riga e' quella: si ritrova al suo id. (`unisci_e_aggiungi.py` la darebbe per orfana e non la
                    # riaggiungerebbe solo perche' l'id esiste gia'.)
                    cov = [m for m in ms if grezzo <= m.start() < grezzo + S03.FUSIONE]
                    non_tradotte.append(r.get('codice'))
                if not cov:
                    if r.get('proposto_rete') != 'esclusa':
                        orfane.append((ref, r, 'nessuna corrispondenza nei 200 caratteri dal suo inizio'))
                    continue
                gg = {gruppo_di[m.start()] for m in cov}
                if r.get('proposto_rete') == 'esclusa':
                    coperti_da_esclusa += len(gg - coperti)
                coperti |= gg
                if r.get('proposto_rete') != 'esclusa':
                    per_gruppo[gruppo_di[cov[0].start()]].append((ref, r, {g3_di.get(m.start()) for m in cov} - {None}))
            for gg, righe in per_gruppo.items():
                if len(righe) > 1:
                    # gia' cosi' in S03 (piu' righe nello stesso gruppo: `unisci_e_aggiungi.py` le lascia tutte) o legate da S05?
                    g3 = set().union(*(x[2] for x in righe))
                    (legate if len(g3) > 1 else gia_insieme).append({
                        'documento': doc, 'gruppo_da': starts[gg], 'righe': [x[1].get('codice') for x in righe],
                        'giudicate': [x[1].get('codice') for x in righe if x[1].get('esito')]})
            for gg, g0 in enumerate(starts):
                if gg in coperti:
                    continue
                riga = csv_doc[doc].get(g0)
                if riga is None:
                    continue          # tolta dal filtro della data o copia di un'altra (negli SCARTI del CSV), come in S03
                c, forme_c = causa(file_di[doc], membri[gg], ancora, forme3, regole5, nuovi_md)
                da_aggiungere.append((riga, c, forme_c))

        gia = [int(m.group(1)) for _, r in tutte for m in [re.fullmatch(rf'{pre}-(\d+)', str(r.get('codice') or ''))] if m]
        n = max(gia, default=0)
        chi = sorted({r['assegnato_a'] for _, r in nominali if r.get('assegnato_a') and not r.get('esito')})
        rnd = random.Random(f'{caso}-{data}-S05')
        esistenti = {ref.id for ref, _ in tutte}
        docs, uscita = {}, []
        for k, (r, c, forme_c) in enumerate(sorted(da_aggiungere, key=lambda x: (x[0]['document_id'], int(x[0]['char_start'])))):
            d = documento(r, caso)
            rid = id_riga(caso, d['document_id'], d['char_start'])
            if rid in esistenti:
                orfane.append((None, {'document_id': d['document_id'], 'char_start': d['char_start'], 'id': rid}, 'id gia\' esistente'))
                continue
            n += 1
            d.update({
                'corroborazione': 'nome_presente', 'ordine': random.Random(rid).random(), 'codice': f'{pre}-{n:04d}',
                'assegnato_a': chi[k % len(chi)] if chi else None, 'campione_cieco': rnd.random() < 0.20,
                'incerta': False,
                'provenienza': {'corpus': 'D03' if r['file'] in nuovi_md else 'D01', 'estrazione': 'S05', 'tipo': '',
                                'principi': {}, 'composizione': '', 'seguito': ''},
                'motivo_aggiunta': {'markdown_nuovo': 'documento senza Markdown fino al 02/10/2026',
                                    'gia_S03': 'forma esatta di S03, riga mancante in piattaforma',
                                    'normalizzazione': 'forma di S03 spezzata o con spazi e trattini diversi',
                                    'forme_riammesse': 'forma riammessa in S05', 'forme_nuove': 'forma nuova di S05'}[c],
            })
            docs[rid] = d
            uscita.append({'id': rid, 'codice_provvisorio': d['codice'], 'causa': c, 'forme_s05': forme_c,
                           **{k2: v for k2, v in d.items() if k2 != 'codice'}})

        conti = collections.Counter(x['causa'] for x in uscita)
        print(f'\n== {caso}: in piattaforma {len(nominali)} righe col nome (+{len(escluse)} escluse); S05 {len(nuove_csv)} citazioni nel CSV')
        print(f'   righe nuove {len(docs)}: ' + ', '.join(f'{c} {conti.get(c, 0)}' for c in CAUSE))
        print(f'   righe della piattaforma non ritrovate: {len(orfane)}; ritrovate alla posizione non tradotta: {len(non_tradotte)}; '
              f'gruppi coperti solo da righe escluse: {coperti_da_esclusa}')
        print(f'   gruppi con piu\' righe: gia\' in S03 {len(gia_insieme)}, legati da una corrispondenza S05 {len(legate)} (NON uniti)')
        for ref, r, perche in orfane[:8]:
            print('     ', r.get('codice'), r['document_id'][:60], r.get('char_start'), perche)
        with open(USCITA/f'{caso}_righe_nuove.jsonl', 'w', encoding='utf-8') as f:
            for x in uscita:
                f.write(json.dumps(x, ensure_ascii=False, default=str) + '\n')
        json.dump({'caso': caso, 'data': data, 'righe_col_nome_in_piattaforma': len(nominali), 'righe_escluse_in_piattaforma': len(escluse),
                   'citazioni_S05_nel_csv': len(nuove_csv), 'righe_nuove': len(docs), 'per_causa': {c: conti.get(c, 0) for c in CAUSE},
                   'orfane': [{'codice': r.get('codice'), 'id': ref.id if ref else r.get('id'), 'document_id': r['document_id'],
                               'char_start': r.get('char_start'), 'rete': r.get('proposto_rete'), 'esito': r.get('esito'), 'perche': perche}
                              for ref, r, perche in orfane],
                   'ritrovate_alla_posizione_non_tradotta': non_tradotte,
                   'gruppi_legati_da_S05_non_uniti': legate, 'gruppi_con_piu_righe_gia_in_S03': len(gia_insieme),
                   'gruppi_coperti_solo_da_righe_escluse': coperti_da_esclusa,
                   'codici_provvisori': [min((x['codice_provvisorio'] for x in uscita), default=None),
                                         max((x['codice_provvisorio'] for x in uscita), default=None)]},
                  open(USCITA/f'{caso}_confronto.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
        if not a.scrivi:
            continue
        w = [(db.collection('corpus_rows').document(rid), d) for rid, d in docs.items()]
        for i in range(0, len(w), 400):
            b = db.batch()
            for ref, d in w[i:i + 400]:
                b.create(ref, {**d, 'esecuzione_id': f'{caso}__{esecuzione}', 'creato_il': firestore.SERVER_TIMESTAMP})
            b.commit()
        db.collection('corpus_runs').document(f'{caso}__{esecuzione}').set({
            'caso_citato': caso,
            'origine': (f'ricerca per nome S05 del {data}: testo normalizzato (sillabazione, a capo, trattini tipografici), '
                        'Markdown dei 277 documenti che ne erano senza, forme riammesse e forme nuove provate; solo aggiunte'),
            'righe_aggiunte': len(docs), 'righe_unite': 0, 'per_causa': {c: conti.get(c, 0) for c in CAUSE},
            'quando': firestore.SERVER_TIMESTAMP, 'forme': len(conf5['forme']),
            'search_strategy': f5.read_text(encoding='utf-8'),
        })
        print(f'   scritte: {len(docs)} nuove')


if __name__ == '__main__':
    import giornale  # il giornale delle operazioni: ogni esecuzione, i file, le scritture, gli errori
    giornale.avvia()
    sys.exit(main())
