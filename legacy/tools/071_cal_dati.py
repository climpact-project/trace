"""I GIUDIZI NUOVI DIVENTANO ESEMPI PER IL RIORDINATORE (apprendimento attivo, 27/09/2026).

   Legge da Firestore (SOLA LETTURA) tutte le righe semantiche di un caso gia' giudicate che NON stanno nella
   divisione congelata del 22/09 (`urgenda_decisione_{addestramento,prova}_corrette_larghe.jsonl`) e le scrive nel
   formato di quella divisione, cosi' `072_cal_riordinatore.py` le aggiunge all'addestramento. Stesse regole di
   `026_prepara_training.py`:
     - positiva solo se la riga non e' scartata e la sonda proposta sta fra quelle attribuite dalle persone;
     - il nome del caso e i codici ECLI mascherati;
     - NESSUNA riga di un caso citante che sta nella prova: le 133 righe di prova restano l'esame fisso, e un
       atto dello stesso caso in addestramento lo renderebbe piu' facile.
   La finestra e' la pagina dell'indice (per le righe dei blocchi `finestra_pagina` e' vuota).

   Uso:  .venv/bin/python tools/071_cal_dati.py --caso urgenda  -> training/cal/<caso>_cal_addestramento.jsonl
"""
import argparse, collections, gzip, json, pathlib, sys
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
_m_cerca = __import__('016_cerca')
leggi_caso = _m_cerca.leggi_caso
_m_prepara_training = __import__('026_prepara_training')
mascheratore = _m_prepara_training.mascheratore
SEGNAPOSTO = _m_prepara_training.SEGNAPOSTO

T = QUI/'training'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--caso', default='urgenda'); a = ap.parse_args()
    conf = leggi_caso(QUI/'cited-cases'/f'{a.caso}.yaml', con_alternative=True)
    testo_di = {' '.join(s['titolo'].split()): {'id': s['id'], 'testo': s['testo']} for s in conf['sonde']}
    maschera = mascheratore(conf['forme'] + [conf.get('nome', '')])
    fissa = [json.loads(l) for p in ('addestramento', 'prova')
             for l in open(T/f'{a.caso}_decisione_{p}_corrette_larghe.jsonl', encoding='utf-8') if l.strip()]
    ids_fissi = {x['id'] for x in fissa}
    casi_prova = {json.loads(l)['case_id'] for l in open(T/f'{a.caso}_decisione_prova_corrette_larghe.jsonl', encoding='utf-8') if l.strip()}

    from google.cloud import firestore
    db = firestore.Client(project='climpact-drp')
    righe = [dict(_id=d.id, **d.to_dict()) for d in db.collection('corpus_rows')
             .where(filter=firestore.FieldFilter('caso_citato', '==', a.caso)).stream()]
    giud = [r for r in righe if r.get('proposto_rete') in ('semantica', 'entrambe')
            and r.get('esito') in ('confermata', 'riclassificata', 'scartata')]
    conti = collections.Counter()
    serve, scelte = set(), []
    for r in giud:
        if r['_id'] in ids_fissi:
            conti['gia nella divisione congelata'] += 1; continue
        if r.get('case_id') in casi_prova:
            conti['caso citante della prova (escluso)'] += 1; continue
        son = ' '.join((r.get('sonda') or '').split())
        if son not in testo_di:
            conti['sonda sconosciuta'] += 1; continue
        pagina = r.get('validato_pagina') or r.get('proposto_pagina')
        serve.add(f"{r['document_id']}#p{pagina}"); scelte.append((r, son, pagina))
    pagine = {}
    with gzip.open(QUI/'index'/'pagine'/'pagine.jsonl.gz', 'rt', encoding='utf-8') as f:
        for l in f:
            x = json.loads(l)
            if x['id'] in serve:
                pagine[x['id']] = x['testo']
    fuori = []
    for r, son, pagina in scelte:
        fin = r.get('finestra_pagina') or pagine.get(f"{r['document_id']}#p{pagina}") or ''
        if not fin:
            conti['pagina senza testo'] += 1; continue
        val = r.get('validato_sonde') or []
        val = [' '.join(v.split()) for v in ([val] if isinstance(val, str) else val)]
        pos = r['esito'] != 'scartata' and son in val
        fin = maschera.sub(SEGNAPOSTO, fin)
        fuori.append({'id': r['_id'], 'case_id': r.get('case_id'), 'document_id': r['document_id'], 'rete': r.get('proposto_rete'),
                      'sonda_id': testo_di[son]['id'], 'sonda_titolo': son, 'sonda_testo': testo_di[son]['testo'],
                      'etichetta': int(pos), 'esito': r['esito'], 'blocco': r.get('blocco') or '',
                      'passaggio': maschera.sub(SEGNAPOSTO, str(r.get('proposto_citazione_testuale') or '')),
                      'frammento': maschera.sub(SEGNAPOSTO, str(r.get('proposto_citazione_testuale') or '')) or fin[:1200],
                      'finestra': fin, 'finestra_larga': fin, 'parte': 'cal'})
        conti['esempi'] += 1; conti[f'etichetta {int(pos)}'] += 1
    (T/'cal').mkdir(exist_ok=True)
    uscita = T/'cal'/f'{a.caso}_cal_addestramento.jsonl'
    with open(uscita, 'w', encoding='utf-8') as f:
        for x in fuori:
            f.write(json.dumps(x, ensure_ascii=False) + '\n')
    print(json.dumps(dict(conti), ensure_ascii=False), '->', uscita)


if __name__ == '__main__':
    main()
