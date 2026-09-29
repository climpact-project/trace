"""Build the training sets from the human-coded sample.

   Judgments saved by `salva_giudizi.py` carry the probe TITLE, not its text: the
   text lives in `cited-cases/<caso>.yaml` and is read with the pipeline's own
   reader (`leggi_caso`). This script joins the two and writes both training sets.

   Two tasks, two different samples:
     A. categoria   lexical network only: what role the citation plays in the text.
     B. decisione   semantic network only: does the passage state that probe?
   Semantic rows carry no citation category.

   Masking. The case name and ECLI/docket identifiers are replaced by a placeholder,
   using the `forme` declared in the case file (the same the lexical network searches
   for). Otherwise the model learns the shortcut "no name means implicit", and in
   production, where no semantic candidate contains the name, it would label
   everything the same way.

   Frozen split, grouped by citing case. The same passage can appear up to nine
   times and one document can carry up to sixteen rows: a random split would put the
   same text on both sides and inflate the test score. The split is by `case_id` and
   is written to disk so that every later experiment uses the same split.

   Usage: python tools/prepara_training.py
"""
import json, pathlib, random, re, sys, collections
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from cerca import leggi_caso

QUI = pathlib.Path(__file__).resolve().parent.parent
CASO = 'urgenda'
SEGNAPOSTO = '⟦CASO_CITATO⟧'
QUOTA_PROVA = 0.30
SEME = 20260922


def mascheratore(forme):
    """A single regex with all name forms of the case, plus ECLI and docket identifiers.

    Forms are sorted by decreasing length so that a long form (e.g. "State of the
    Netherlands v. Urgenda Foundation") is consumed before a short one ("Urgenda");
    otherwise a recognisable residue would remain."""
    pezzi = sorted({f for f in forme if len(f) > 3}, key=len, reverse=True)
    pat = '|'.join(re.escape(f) for f in pezzi)
    pat += r'|ECLI:[A-Z]{2}:[A-Z]+:\d{4}:\d+|\b\d{2}/\d{5}\b|\b200\.\d{3}\.\d{3}/\d{2}\b'
    return re.compile(pat, re.I)


def main():
    conf = leggi_caso(QUI/'cited-cases'/f'{CASO}.yaml', con_alternative=True)
    testo_di = {}
    for s in conf['sonde']:
        testo_di[s['titolo']] = {'id': s['id'], 'testo': s['testo']}
    maschera = mascheratore(conf['forme'] + [conf.get('nome', '')])

    # The ORIGINAL chunk actually scored by the reranker. Judgments carry
    # `proposto_citazione_testuale` truncated to 460 characters, while the reranker
    # saw the full chunk (median 1,290 characters); without it, comparison with the
    # archived scores would not be like for like. Recovered from `index/chunks.jsonl`
    # by (document_id, char_start). Lexical rows have none, since they come from a
    # text search on the markdown rather than from an index chunk.
    orig = {}
    po = QUI/'training'/'frammenti_originali.json'
    if po.exists():
        orig = json.loads(po.read_text(encoding='utf-8'))

    giudizi = sorted(QUI.glob('giudizi-umani-*.json'))[-1]
    righe = json.loads(giudizi.read_text(encoding='utf-8'))
    print(f'giudizi: {giudizi.name} ({len(righe)} righe)')
    print(f'sonde con testo: {len(testo_di)}   forme per il mascheramento: {len(conf["forme"])}')

    senza_testo = collections.Counter()
    A, B = [], []
    for r in righe:
        rete = r.get('proposto_rete') or ''
        son = (r.get('sonda') or '').strip()
        sd = testo_di.get(son)
        comune = {
            'id': r['_id'], 'case_id': r.get('case_id'), 'document_id': r.get('document_id'),
            'rete': rete, 'tipo_atto': r.get('tipo_atto'), 'anno': str(r.get('data'))[:4],
            'passaggio': maschera.sub(SEGNAPOSTO, str(r.get('proposto_citazione_testuale') or '')),
            'finestra': maschera.sub(SEGNAPOSTO, str(r.get('finestra_pagina') or '')),
            'frammento': maschera.sub(SEGNAPOSTO, str((orig.get(r['_id']) or {}).get('testo') or '')),
        }
        if rete in ('lessicale', 'entrambe'):
            cat = r.get('validato_tipo_citazione')
            if cat:
                A.append({**comune, 'categoria': cat,
                          'chi_parla': r.get('validato_chi_parla'),
                          'forma_trovata': r.get('proposto_forma_trovata')})
        if rete in ('semantica', 'entrambe'):
            if not sd:
                senza_testo[son[:50]] += 1
                continue
            val = r.get('validato_sonde') or []
            if isinstance(val, str):
                val = [val]
            # positive only if the PROPOSED probe is among the validated ones and the row is not discarded
            pos = r['esito'] != 'scartata' and son in val
            B.append({**comune, 'sonda_id': sd['id'], 'sonda_titolo': son,
                      'sonda_testo': sd['testo'], 'etichetta': int(pos),
                      'esito': r['esito'],
                      'punteggio': r.get('punteggio'), 'riordino': r.get('punteggio_riordino'),
                      'margine': r.get('margine'), 'sospetto': r.get('sospetto') or '',
                      'corroborazione': r.get('corroborazione'),
                      'note': r.get('validato_note') or ''})
    if senza_testo:
        print('  ATTENZIONE, sonde senza testo nel file del caso:', senza_testo.most_common())

    # ── split by citing case, balanced on labels ──
    #
    # Grouping by case alone is not enough: cases differ widely in size (1 to 31
    # rows), and a random assignment gave a test set with a different label mix
    # (measured: 38% positives in test vs 24% in training). A test score on a
    # different composition is not comparable. Cases are therefore assigned one at
    # a time, largest first, to the side that brings the compositions closer.
    casi = sorted({x['case_id'] for x in A} | {x['case_id'] for x in B})
    voci = collections.defaultdict(collections.Counter)   # case -> counts per class
    for x in A:
        voci[x['case_id']]['A:' + x['categoria']] += 1
    for x in B:
        voci[x['case_id']]['B:' + str(x['etichetta'])] += 1
    totale = collections.Counter()
    for c in casi:
        totale.update(voci[c])
    classi = sorted(totale)

    # Target: for EVERY class, the test side should hold about QUOTA_PROVA of it.
    # Each case goes to the side that leaves the test set closest to that target,
    # class by class. A criterion on average composition would always favour the
    # larger side, which necessarily resembles the total more closely.
    bersaglio = {k: totale[k] * QUOTA_PROVA for k in classi}

    def costo(acc):
        return sum(abs(acc[k] - bersaglio[k]) for k in classi)

    ordine = sorted(casi, key=lambda c: (-sum(voci[c].values()), c))
    prova, acc_p = set(), collections.Counter()
    for c in ordine:
        v = voci[c]
        if costo(acc_p + v) < costo(acc_p):
            prova.add(c); acc_p.update(v)
    for x in A + B:
        x['parte'] = 'prova' if x['case_id'] in prova else 'addestramento'

    fuori = QUI/'training'
    fuori.mkdir(exist_ok=True)
    for nome, dati in (('categoria', A), ('decisione', B)):
        for parte in ('addestramento', 'prova'):
            sub = [x for x in dati if x['parte'] == parte]
            p = fuori/f'{CASO}_{nome}_{parte}.jsonl'
            p.write_text('\n'.join(json.dumps(x, ensure_ascii=False) for x in sub), encoding='utf-8')
            print(f'  {p.name:42s} {len(sub):4d} righe')
    (fuori/'divisione.json').write_text(json.dumps({
        'seme': SEME, 'quota_prova': QUOTA_PROVA, 'giudizi': giudizi.name,
        'casi_di_prova': sorted(prova), 'casi_totali': len(casi)}, indent=1), encoding='utf-8')

    print('\n— compito A, categoria (rete lessicale) —')
    for parte in ('addestramento', 'prova'):
        sub = [x for x in A if x['parte'] == parte]
        print(f'  {parte:14s} {len(sub):4d}  ' + str(collections.Counter(x['categoria'] for x in sub).most_common()))
    print('— compito B, decisione (rete semantica) —')
    for parte in ('addestramento', 'prova'):
        sub = [x for x in B if x['parte'] == parte]
        p = sum(x['etichetta'] for x in sub)
        print(f'  {parte:14s} {len(sub):4d}  positive {p} ({100*p/len(sub):.0f}%), negative {len(sub)-p}')
    senza_fr = [x for x in B if not x['frammento']]
    print(f'frammento originale: presente su {len(B)-len(senza_fr)} righe di B su {len(B)}'
          + (f' (mancano {len(senza_fr)}, tutte «entrambe»)' if senza_fr else ''))
    resti = [x for x in A + B if SEGNAPOSTO not in x['finestra']]
    print(f'\nmascheramento: {len(A)+len(B)-len(resti)} righe su {len(A)+len(B)} contengono il segnaposto nella finestra')


if __name__ == '__main__':
    main()
