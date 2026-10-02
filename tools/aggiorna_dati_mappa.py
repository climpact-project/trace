"""I DATI DELLA MAPPA DALLA BANCA DATI (01/10/2026).

   `pubblicazione/mappa/dati_ricchi.json` era stato costruito una volta, a mano, il 30/09. Le citazioni aggiunte dopo
   (URG-1737..1740, NEU-1622, NEU-1623) non c'erano, e quelle rilette sul testo OCR avevano ancora il testo rotto. Qui
   ogni citazione della coda Uptakes (reti lessicale ed entrambe; non le fuse ne' le escluse) si rigenera dalla
   banca dati: proposte o giudizio, seguito, frase, passaggio e spiegazioni. Restano com'erano i campi che la banca dati
   non ha (i paragrafi delle sentenze, i documenti, le traduzioni). Una citazione che esce dalla coda esce dalla mappa
   (la regola del PI: «ogni notte si tolgono quelle che il team scarta»; le scartate restano, con stato discarded).
   Prima di scrivere confronta campo per campo con il file di oggi e stampa le differenze.

   La mappa cresce (01/10/2026, il PI: «deve crescere nei mesi e nelle settimane» e «entrare in relazione con gli
   altri»). I casi non sono piu' scritti qui: vengono da `pubblicazione/mappa/casi.json`, uno per voce. Per ogni caso
   si rigenerano anche: gli ATTI (un atto nuovo prende nome, tipo, data e giurisdizioni dal manifest del corpus e la
   sede dalla tabella delle sedi gia' note o da `sedi_aggiunte.json`; i conteggi per caso si rifanno dalle citazioni),
   le SENTENZE (da casi.json) e i PRINCIPI (dalle sonde della serie in uso, `sonde.py`; i principi di serie
   precedenti restano finche' qualche citazione li porta).

   Uso:  .venv/bin/python tools/aggiorna_dati_mappa.py [--scrivi]
"""
import argparse, collections, json, pathlib, re, shutil, sys
import yaml
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
import cerca, sonde as S
M = QUI/'pubblicazione'/'mappa'
F = M/'dati_ricchi.json'
CASI = json.load(open(M/'casi.json', encoding='utf-8'))['casi']
PREF = {c['id']: c['id'] for c in CASI}


def voce(r):
    giudicata = r.get('esito') in ('confermata', 'scartata')
    pr = r.get('validato_principi') if r.get('esito') == 'confermata' and r.get('validato_principi') is not None else r.get('proposto_principi')
    pr = [p for p in (pr or []) if p not in ('nessuno', 'altro')]
    tipo = (r.get('validato_tipo_citazione') if giudicata and r.get('validato_tipo_citazione') else r.get('proposto_tipo_citazione')) or None
    # la frase si mostra salvo che sia inventata (copiata dal prompt): «non trovata» resta, con il suo esito nelle spiegazioni
    frase = ' '.join(str(r.get('proposto_frase_sostenuta') or '').split()) if r.get('proposto_frase_esito') != 'inventata' else ''
    pv = r.get('provenienza') or {}
    return {
        'codice': r['codice'], 'caso': r['caso_citato'], 'doc': r['document_id'], 'pagina': r.get('proposto_pagina'),
        'principi': pr, 'tipo': tipo, 'esito': r.get('esito'),
        'seguito': sorted(e['pagina'] for e in (r.get('proposto_estensione') or []) if e.get('prosegue')),
        'frase': frase, 'passaggio': r.get('proposto_citazione_testuale') or '',
        'chi_parla': r.get('proposto_chi_parla'), 'posizione': r.get('proposto_posizione'),
        'paragrafi': r.get('proposto_paragrafi') or [],
        'stato': {'confermata': 'verified', 'scartata': 'discarded'}.get(r.get('esito'), 'proposed'),
        'spiega': {
            'proposizione_it': r.get('proposto_proposizione') or '', 'motivo_principi_it': r.get('proposto_principi_motivo') or '',
            'nota_tipo_it': r.get('proposto_note') or '', 'fonti_principi': r.get('proposto_principi_fonti') or {},
            'punteggi_principi': r.get('proposto_punteggi_principi') or {},
            'seguito': r.get('proposto_estensione') or [],
            'provenienza': {k: (v if not isinstance(v, dict) else v) for k, v in pv.items()},
            'confidenza': r.get('proposto_confidenza'), 'corroborazione': r.get('corroborazione'),
            'chi_cita': r.get('proposto_chi_cita'), 'sede': r.get('proposto_sede'),
            'frase_testuale': r.get('proposto_frase_testuale'), 'altro_it': r.get('proposto_principio_altro') or ''}}


def sedi_note(documenti):
    """giurisdizioni gia' sulla mappa -> sede; le stesse parti in altro ordine valgono uguale"""
    t = {}
    for d in documenti:
        if d.get('lat') is not None:
            t[frozenset(x.strip() for x in d['giurisdizioni'].split(';') if x.strip())] = (d['sede'], d['lat'], d['lon'])
    return t


def sede(doc_id, giur, note, agg):
    parti = [x.strip() for x in (giur or '').split(';') if x.strip()]
    if doc_id in agg['atti']:
        return tuple(agg['atti'][doc_id][:3])
    if frozenset(parti) in note:
        return note[frozenset(parti)]
    for chiave, v in agg['corti'].items():
        if all(k in parti for k in chiave.split('|')):
            return tuple(v)
    return None


def nuovo_atto(doc_id, man, note, agg):
    m = man.get(doc_id)
    if not m:
        return None, 'manca nel manifest'
    giur = m['docs'].get('jurisdictions') or ''
    st = sede(doc_id, giur, note, agg)
    if not st:
        return None, f'sede non trovata: {giur!r}'
    data = cerca.data_documento({'url_origine': m['url']}) or str(m['docs'].get('filing_date') or '')[:10]
    parti = [x.strip() for x in giur.split(';') if x.strip()]
    paese = parti[0] if parti else (agg['atti'].get(doc_id) or [None] * 4)[3] or ''
    return {'id': doc_id, 'nome': m['docs']['case_name'], 'atto': m['tipo'], 'anno': data[:4], 'giur': paese,
            'casi': {}, 'url': f'https://www.climatecasechart.com/documents/{doc_id}', 'sede': st[0], 'lat': st[1], 'lon': st[2],
            'giurisdizioni': giur or paese, 'anno_causa': '', 'data_documento': data}, None


def principi_in_uso(vecchi, usati):
    """le sonde della serie in uso di ogni caso; i principi di prima restano se una citazione li porta ancora"""
    out = {}
    for c in CASI:
        y = yaml.safe_load(open(S.file_caso(c['id']), encoding='utf-8'))
        for q in y.get('semantic_queries') or []:
            out[q['id']] = {'caso': c['id'], 'titolo_it': ' '.join(str(q.get('titolo') or '').split()),
                            'titolo_en': c['principi_en'].get(q['id'], ''), 'testo': ' '.join(str(q.get('testo') or '').split())}
    for k, v in vecchi.items():
        if k not in out and k in usati:
            out[k] = {**v, 'titolo_en': next((c['principi_en'].get(k, '') for c in CASI if c['id'] == v.get('caso')), '')}
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--scrivi', action='store_true'); ap.add_argument('--righe', default='')
    a = ap.parse_args()
    if a.righe:
        righe = json.load(open(a.righe, encoding='utf-8'))
    else:
        from google.cloud import firestore
        db = firestore.Client(project='climpact-drp'); righe = {}
        for caso in PREF:  # ogni caso di casi.json
            for d in db.collection('corpus_rows').where(filter=firestore.FieldFilter('caso_citato', '==', caso)).stream():
                righe[d.id] = json.loads(json.dumps(d.to_dict(), default=str))
    dati = json.load(open(F, encoding='utf-8'))
    vecchie = {c['codice']: c for c in dati['citazioni']}
    nuove = {}
    for rid, r in righe.items():
        if r.get('proposto_rete') in ('lessicale', 'entrambe') and r.get('codice'):
            nuove[r['codice']] = voce(r)
    # atti: quelli di prima tengono i loro campi, i nuovi vengono dal manifest; i conteggi si rifanno dalle citazioni
    tipi = {}
    for rid, r in righe.items():
        if r.get('codice') in nuove: tipi.setdefault(r['document_id'], r.get('tipo_atto') or 'altro')
    man = {}
    for l in open(QUI/'manifest.jsonl', encoding='utf-8'):
        m = json.loads(l)
        for d in m.get('docs') or []:
            if d['document_id'] in tipi: man[d['document_id']] = {'url': m['url'], 'docs': d, 'tipo': tipi[d['document_id']]}
    agg = json.load(open(M/'sedi_aggiunte.json', encoding='utf-8')); note = sedi_note(dati['documenti'])
    conta = collections.defaultdict(collections.Counter)
    for v in nuove.values(): conta[v['doc']][v['caso']] += 1
    per_id = {d['id']: d for d in dati['documenti']}; documenti, problemi = [], []
    for doc_id in sorted(conta, key=lambda i: (i not in per_id, i)):
        d = per_id.get(doc_id)
        if d is None:
            d, errore = nuovo_atto(doc_id, man, note, agg)
            if errore: problemi.append(f'{doc_id}: {errore}'); continue
        d = {**d, 'casi': {c['id']: conta[doc_id][c['id']] for c in CASI if conta[doc_id][c['id']]}}
        documenti.append(d)
    print('atti', len(dati['documenti']), '->', len(documenti), '| nuovi', sum(1 for d in documenti if d['id'] not in per_id),
          '| senza piu\' citazioni', sum(1 for i in per_id if i not in conta))
    for x in problemi: print('  ATTO FUORI DALLA MAPPA', x)
    usati = {p for v in nuove.values() for p in v['principi']}
    principi = principi_in_uso(dati.get('principi') or {}, usati)
    senza = sorted(usati - set(principi))
    print('principi', len(dati.get('principi') or {}), '->', len(principi), '| portati da citazioni ma senza scheda', senza[:8])
    sentenze = {c['id']: {k: c[k] for k in ('nome', 'colore', 'corte', 'data', 'sede', 'lat', 'lon', 'case_id', 'pronuncia')} for c in CASI}
    diff = collections.Counter(); esempi = {}
    for c, v in nuove.items():
        o = vecchie.get(c)
        if not o:
            diff['citazione nuova'] += 1; continue
        for k in v:
            if k == 'spiega':
                for kk in v['spiega']:
                    if v['spiega'][kk] != (o.get('spiega') or {}).get(kk):
                        diff[f'spiega.{kk}'] += 1; esempi.setdefault(f'spiega.{kk}', c)
            elif v[k] != o.get(k):
                diff[k] += 1; esempi.setdefault(k, c)
    uscite = [c for c in vecchie if c not in nuove]
    print('citazioni oggi', len(vecchie), '| dalla banca dati', len(nuove), '| uscite dalla coda', len(uscite), uscite[:10])
    for k, n in diff.most_common():
        print(f'  {k}: {n}  (es. {esempi.get(k, "")})')
    if problemi:
        print('ANTEPRIMA: atti senza sede, niente scritto (aggiungerli a sedi_aggiunte.json)'); return
    if not a.scrivi:
        print('ANTEPRIMA: niente scritto'); return
    shutil.copy(F, F.with_name(F.stem + '.prima-aggiornamento.json'))
    ordine = [c['codice'] for c in dati['citazioni'] if c['codice'] in nuove] + sorted(c for c in nuove if c not in vecchie)
    dati['citazioni'] = [nuove[c] for c in ordine]
    dati['documenti'], dati['principi'], dati['sentenze'] = documenti, principi, sentenze
    json.dump(dati, open(F, 'w', encoding='utf-8'), ensure_ascii=False)
    print('scritto', F, len(dati['citazioni']), 'citazioni')


if __name__ == '__main__':
    main()
