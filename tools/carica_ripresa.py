"""Load uptake proposals onto lexical rows: principles taken up and continuation on nearby pages.

   Writes onto lexical rows WITHOUT a judgment (no human judgment is modified) the fields read by the annotation
   view (codebook 0.3-pilot, dimensions 6 and 7):
     proposto_principi         principles pre-selected: those of the cited paragraphs (paragraph map) plus those
                               of the first DeepSeek reading; ["nessuno"] if the reading says none and no cited
                               paragraph supports one;
     proposto_principi_fonti   source of each principle: paragraph, reading, reranker (passage score >= 0.5:
                               lexically close, shown as a hint even when not selected);
     proposto_principio_altro  the reading's sentence when it answers "altro";
     proposto_estensione       proposed nearby pages, with continues yes/no, principle and evidence sentence;
     proposto_paragrafi        the recognised cited paragraphs;
     proposto_principi_motivo  the reading's rationale for its choices;
     proposto_ripresa_lettore  the proposing system.
   These are proposals only: training labels come from human annotators or from the paragraph map, never from
   DeepSeek.

   Usage:  .venv/bin/python tools/carica_ripresa.py --caso urgenda            preview
           .venv/bin/python tools/carica_ripresa.py --caso urgenda --scrivi   write
"""
import argparse, collections, hashlib, json, pathlib, re
QUI = pathlib.Path(__file__).resolve().parent.parent
P = QUI/'training'/'principi'
SOGLIA_RERANKER = 0.5


def proposta(caso, rid, ids, par, brano, ds, cand, tipo=''):
    """Return the proposed fields for one row (read-only)."""
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
    # A chain mention takes up no principle (codebook, dimension 6). The type and uptake readings are separate
    # calls, so the rule is enforced here. Hints (paragraph, reranker) stay in the sources, visible but unselected.
    in_catena = tipo == 'menzione_in_catena'
    if in_catena:
        spuntati = ['nessuno']
    vic = []
    pagine_cand = {v['pagina'] for v in (cand.get(rid) or {}).get('vicine', [])}
    # Check that the evidence sentence is actually on the page: only 53-64% of DeepSeek's evidence sentences for
    # nearby pages are verbatim copies; the rest are paraphrases or translations.
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
    # No continuation without a principle: if the citation takes up no principle (chain mention, or "nessuno"),
    # nothing can continue. Pages stay listed, none selected.
    if spuntati == ['nessuno']:
        vic = [dict(v, prosegue=False) for v in vic]
    # Provenance (version registry, `tools/registro_versioni.py`): for each principle, the versions that proposed
    # it; L05 instead of L04 where the second reading exists.
    lettura = 'L05' if (ds.get(rid) or {}).get('seconda') else 'L04'
    codici = {'paragrafo': 'R01', 'lettura': lettura, 'reranker': 'T01'}
    prov = {'provenienza.principi': {k: sorted({codici[f] for f in v}) for k, v in fonti.items() if v},
            'provenienza.seguito': lettura if vic else '', 'provenienza.composizione': 'R02',
            # `estrazione` and `corpus` are not rewritten here: they are set when the row is created (S01 for rows
            # from the first search, S02 for rows added by the corrected search).
            'proposto_punteggi_principi': {k: round(float(x), 4) for k, x in brano.get(rid, {}).items()},
            'proposto_testo_impronta': hashlib.sha256(((cand.get(rid) or {}).get('contesto') or '').encode('utf-8')).hexdigest()}
    # The sentence of the filing supported by the citation (L05): copied from the reading and checked against the
    # page text (used to highlight it in the PDF and to decide the principle on the right sentence).
    frase = ' '.join(str(l1.get('frase_sostenuta') or '').split())[:600]
    ctx = norm((cand.get(rid) or {}).get('contesto') or '')
    if frase:
        prov['proposto_frase_sostenuta'] = frase
        prov['proposto_frase_testuale'] = norm(frase)[:60] in ctx
    return {**prov, 'proposto_principi': spuntati, 'proposto_principi_fonti': {k: v for k, v in fonti.items() if v},
            'proposto_principio_altro': altro if 'altro' in spuntati else '', 'proposto_estensione': vic,
            'proposto_paragrafi': par.get(rid, {}).get('paragrafi', []),
            # the reading's rationale, shown to the validator next to the proposal
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
    # The second reading (footnote rule), where present, replaces the first; `v10` is the same reading applied to
    # rows added by the corrected search and to rows whose first reading was unparseable.
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
