"""LE CITAZIONI COL NOME: UNIRE QUELLE SPEZZATE E AGGIUNGERE QUELLE MANCANTI (29/09/2026).

   Due difetti di `cerca.py`, trovati leggendo le pagine che il reranker metteva fuori dalla finestra:
   - il taglio del riordinatore e il filtro della data colpivano anche le righe «entrambe», cioe' righe che nominano
     il caso: su Urgenda 49 citazioni esplicite scartate, 40 mai arrivate in piattaforma (la sentenza Shell,
     KlimaSeniorinnen, Gloucester); mancavano poi le forme coreana e giapponese del nome;
   - la fusione delle corrispondenze vicine misurava la distanza solo dalla PRIMA corrispondenza del gruppo, cosi' un
     riferimento lungo («Urgenda, C/09/456689, HA ZA 13-1396, 200.178.245/01, ECLI...») diventava due righe: ora un
     identificativo vicino alla corrispondenza precedente continua la citazione (`cerca.fondi`).
   Corretto `cerca.py`, rifatta la ricerca per nome (`index/nomi_<caso>_2026-09-29b.csv`). Qui si confronta con la
   piattaforma, dal vivo:
   - gruppo della ricerca nuova senza righe in piattaforma -> RIGA NUOVA, con codice dopo il piu' alto del caso,
     assegnata a turno a chi ha righe del caso da fare, una su cinque alla cieca come le altre;
   - gruppo con due o piu' righe in piattaforma -> CITAZIONE SPEZZATA: resta la riga gia' giudicata (o la prima);
     le altre escono dalla coda con `proposto_rete = 'fusa'`, e tengono codice, dati e un segno per rimetterle
     (`fusa_in`, `fusa_rete_prima`). Niente si cancella; nessun giudizio si tocca.
   Senza --scrivi stampa i conti e non scrive niente.

   Uso:  .venv/bin/python tools/unisci_e_aggiungi.py [--caso urgenda] [--scrivi]
"""
import argparse, collections, csv, json, random, re, sys, pathlib
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
import cerca
from pubblica import documento, id_riga

PREFISSI = {'urgenda': 'URG', 'neubauer': 'NEU', 'future-generations': 'FGC'}
DATA = '2026-09-29'
ESECUZIONE = 'nomi__2026-09-29'


def gruppi_del_documento(md, patt):
    """Corrispondenze del nome e gruppi con la stessa regola di `cerca.fondi`.
    Ritorna (testo, corrispondenze, gruppo di ogni corrispondenza, inizio di ogni gruppo)."""
    testo = md.read_text(encoding='utf-8', errors='replace')
    meta, inizio = cerca.front_matter(testo)
    ms = list(patt.finditer(testo, inizio))
    fuse = cerca.fondi(testo, ms)
    di, g, starts = {}, -1, []
    inizi = {f[0].start() for f in fuse}
    for m in ms:
        if m.start() in inizi:
            g += 1; starts.append(m.start())
        di[m.start()] = g
    return testo, ms, di, starts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--caso', default='')
    ap.add_argument('--scrivi', action='store_true')
    a = ap.parse_args()
    from google.cloud import firestore
    db = firestore.Client(project='climpact-drp')
    rapporto = {}
    for caso in ([a.caso] if a.caso else list(PREFISSI)):
        pre = PREFISSI[caso]
        conf = cerca.leggi_caso(QUI/'cited-cases'/f'{caso}.yaml')
        patt = re.compile('|'.join(re.escape(f) for f in conf['forme']), re.I)
        tutte = [(d.reference, d.to_dict()) for d in db.collection('corpus_rows')
                 .where(filter=firestore.FieldFilter('caso_citato', '==', caso)).stream()]
        nominali = [(ref, r) for ref, r in tutte if r.get('proposto_rete') in ('lessicale', 'entrambe')]
        nuove_csv = list(csv.DictReader(open(QUI/'index'/f'nomi_{caso}_{DATA}b.csv', encoding='utf-8')))
        per_doc = collections.defaultdict(list)
        for ref, r in nominali:
            per_doc[r['document_id']].append((ref, r))
        csv_doc = collections.defaultdict(dict)
        for r in nuove_csv:
            csv_doc[r['document_id']][int(r['char_start'])] = r
        file_di = {r['document_id']: r['file'] for r in nuove_csv}
        for ref, r in nominali:
            file_di.setdefault(r['document_id'], r.get('file'))

        # COME SI LEGGE UNA RIGA DELLA PIATTAFORMA. Una riga copre le corrispondenze a meno di 200 caratteri dal suo
        # inizio (la regola con cui e' nata). Se fra queste c'e' il NOME del caso, la riga rappresenta il gruppo di
        # quel nome e resta com'e'. Se ci sono SOLO identificativi (numeri di ruolo, ECLI, il nome dentro un indirizzo
        # web), e' la coda di una citazione spezzata e si unisce alla riga che rappresenta il suo gruppo. Un gruppo
        # della ricerca nuova che nessuna riga copre e' una citazione mancante e si aggiunge.
        da_aggiungere, spezzate, orfane, piu_nomi = [], [], [], 0
        for doc in sorted(set(per_doc) | set(csv_doc)):
            md = QUI/file_di[doc]
            if not md.exists():
                orfane += per_doc.get(doc, [])
                continue
            testo, ms, gruppo_di, starts = gruppi_del_documento(md, patt)
            coperti, rapp, code = set(), collections.defaultdict(list), collections.defaultdict(list)
            for ref, r in per_doc.get(doc, []):
                cs = int(r.get('char_start') or -1)
                cov = [m for m in ms if cs <= m.start() < cs + cerca.FUSIONE]
                if not cov:
                    orfane.append((ref, r)); continue
                coperti |= {gruppo_di[m.start()] for m in cov}
                nomi = [m for m in cov if cerca.e_nome(testo, m)]
                (rapp if nomi else code)[gruppo_di[(nomi or cov)[0].start()]].append((ref, r))
            for g in sorted(set(rapp) | set(code)):
                if len(rapp[g]) > 1:
                    piu_nomi += 1
                tutte_g = sorted(rapp[g] + code[g], key=lambda x: int(x[1]['char_start']))
                if not code[g] or len(tutte_g) < 2:
                    continue
                # Resta la riga GIUDICATA: prima fra quelle col nome, poi fra le code (URG-1664 era giudicata e la
                # riga col nome URG-1663 no: si tiene la 1664). Altrimenti la prima riga col nome.
                base = rapp[g] or code[g]
                giudicate = [x for x in base if x[1].get('esito')] or [x for x in code[g] if x[1].get('esito')]
                tieni = giudicate[0] if giudicate else sorted(base, key=lambda x: int(x[1]['char_start']))[0]
                via = [x for x in code[g] if x[0].id != tieni[0].id]
                if tieni in code[g] and len(rapp[g]) == 1:
                    via += rapp[g]
                spezzate.append((tieni, via, sum(1 for x in tutte_g if x[1].get('esito'))))
            for g, g0 in enumerate(starts):
                if g not in coperti:
                    riga = csv_doc[doc].get(g0)
                    if riga is not None:
                        da_aggiungere.append(riga)

        # IL CODICE: dopo il piu' alto del caso, contando anche le righe gia' unite (il numero non torna mai).
        gia = [int(m.group(1)) for _, r in tutte for m in [re.fullmatch(rf'{pre}-(\d+)', str(r.get('codice') or ''))] if m]
        n = max(gia, default=0)
        chi = sorted({r['assegnato_a'] for _, r in nominali if r.get('assegnato_a') and not r.get('esito')})
        rnd = random.Random(f'{caso}-{DATA}')
        esistenti = {ref.id for ref, _ in tutte}
        docs = {}
        for k, r in enumerate(sorted(da_aggiungere, key=lambda x: (x['document_id'], int(x['char_start'])))):
            d = documento(r, caso)
            rid = id_riga(caso, d['document_id'], d['char_start'])
            if rid in esistenti:
                orfane.append((None, {'document_id': d['document_id'], 'char_start': d['char_start'], 'id': rid}))
                continue
            n += 1
            d.update({
                'corroborazione': 'nome_presente', 'ordine': random.Random(rid).random(), 'codice': f'{pre}-{n:04d}',
                'assegnato_a': chi[k % len(chi)] if chi else None, 'campione_cieco': rnd.random() < 0.20,
                'incerta': False, 'provenienza': {'corpus': 'D01', 'estrazione': 'S02', 'tipo': '', 'principi': {},
                                                  'composizione': '', 'seguito': ''},
                'motivo_aggiunta': r.get('motivo_mancava', ''),
            })
            docs[rid] = d

        print(f'\n== {caso}: in piattaforma {len(nominali)} righe col nome; ricerca nuova {len(nuove_csv)} citazioni')
        print(f'   da aggiungere {len(docs)} (codici {pre}-{n - len(docs) + 1:04d}..{pre}-{n:04d}), validatori {len(chi)}, '
              f'alla cieca {sum(d["campione_cieco"] for d in docs.values())}')
        print(f'   citazioni spezzate {len(spezzate)}: righe da unire {sum(len(x[1]) for x in spezzate)}, '
              f'con una riga giudicata {sum(1 for x in spezzate if x[2])}, con PIU\' righe giudicate {sum(1 for x in spezzate if x[2] > 1)}')
        print(f'   righe della piattaforma senza gruppo nella ricerca nuova (non si toccano): {len(orfane)}; '
              f'gruppi con piu\' righe che nominano il caso (restano tutte): {piu_nomi}')
        for ref, r in orfane[:5]:
            print('     ', r.get('codice'), r['document_id'][:60], r.get('char_start'))
        rapporto[caso] = {'aggiunte': [(d['codice'], d['document_id'], d['proposto_pagina'], d['proposto_forma_trovata'])
                                       for d in docs.values()],
                          'unite': [(t[1].get('codice'), [x[1].get('codice') for x in via]) for t, via, _ in spezzate],
                          'orfane': [r.get('codice') for _, r in orfane]}
        if not a.scrivi:
            continue
        w = [(db.collection('corpus_rows').document(rid), d, 'nuova') for rid, d in docs.items()]
        for (tref, t), via, _ in spezzate:
            for ref, r in via:
                w.append((ref, {'proposto_rete': 'fusa', 'fusa_rete_prima': r.get('proposto_rete'),
                                'fusa_in': t.get('codice'), 'fusa_il': DATA,
                                'fusa_motivo': 'stessa citazione spezzata in due righe dalla vecchia regola di fusione'}, 'unisci'))
        for i in range(0, len(w), 400):
            b = db.batch()
            for ref, d, tipo in w[i:i + 400]:
                if tipo == 'nuova':
                    b.create(ref, {**d, 'esecuzione_id': f'{caso}__{ESECUZIONE}', 'creato_il': firestore.SERVER_TIMESTAMP})
                else:
                    b.update(ref, d)
            b.commit()
        db.collection('corpus_runs').document(f'{caso}__{ESECUZIONE}').set({
            'caso_citato': caso, 'origine': 'ricerca per nome rifatta (cerca.py corretto: niente tagli semantici sulle '
                                            'righe col nome, fusione dalla corrispondenza precedente, forme coreana e giapponese)',
            'righe_aggiunte': len(docs), 'righe_unite': sum(len(x[1]) for x in spezzate),
            'quando': firestore.SERVER_TIMESTAMP, 'forme': len(conf['forme']),
            'search_strategy': (QUI/'cited-cases'/f'{caso}.yaml').read_text(encoding='utf-8'),
        })
        print(f'   scritte: {len(docs)} nuove, {sum(len(x[1]) for x in spezzate)} unite')
    json.dump(rapporto, open(QUI/'training'/f'nomi_unisci_aggiungi_{DATA}.json', 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    sys.exit(main())
