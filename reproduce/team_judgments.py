"""THE TEAM JUDGMENTS in the TRACE 0.1 data deposit (07/10/2026, decision of the principal investigator).

Original: `pubblicazione/trace-0.1/team_judgments.py` of the TRACE working tree (frozen with TRACE 0.1). The code below is
the same; only this docstring and the comments are in English. Italian strings are data (field values of the platform).

One row per citation judged by the team, discarded citations included (those stay out of trace-0.1-citations.csv).
Pure functions: `prepare_dataset.py` calls them with the rows read from Firestore (read only) and writes the files.

Universe: the citations of dati_ricchi.json (the same selection as the citations file) plus the citations discarded by
the team that have a citation code. Inside it, the rows with a judgment: the current one of the Uptakes queue (`esito`)
or, if the row was put back in the queue and not judged again yet, the September one (`settembre`, with outcome, judge
and date only).

Privacy: the judges come out as "coder A", "coder B"... in order of first judgment; names, uids, emails, times and free
notes do not enter the file. The uid -> pseudonym pairing is written apart, outside the published record."""
# The code keeps the frozen original line for line (names and long lines are not restyled; `json` is imported there too).
# ruff: noqa: B007, E501, F401, N803
import json

# the English labels of the discard reasons: copy of MOTIVO_ETICHETTA in the platform code
# (src/pages/tools/corpus/pipeline/ValidationTable.jsx, 07/10/2026)
MOTIVO_ETICHETTA = {
    'non_e_una_citazione': 'not a citation at all',
    'citazione_altrove': 'the case is cited elsewhere in the document, not in this passage',
    'indice_o_sommario': 'index or table of contents: the case is only listed',
    'soggetto_omonimo': 'the association or party bearing the name, not the judgment',
    'omonimo': 'another meaning of the word',
    'caso_omonimo': 'a different case with a similar name',
    'falso_positivo_semantico': 'it says something else',
    'altra_fonte': 'same idea, but taken from another source (a treaty, the IPCC, another judgment)',
    'duplicato_di_altra_riga': 'duplicate of another row',
    'testo_illeggibile': 'text unreadable',
    'fuori_perimetro': 'outside the scope of this study',
    'altro': 'something else',
}
ESITO_EN = {'confermata': 'confirmed', 'scartata': 'discarded', 'riclassificata': 'reclassified'}
CAMPI = ['citation_code', 'cited_judgment', 'outcome', 'counted_in_release', 'discard_reason', 'judgment_round',
         'machine_citation_function', 'team_citation_function', 'machine_who_speaks', 'team_who_speaks',
         'machine_where_in_text', 'team_where_in_text', 'machine_principles', 'team_principles',
         'machine_surrounding_pages', 'team_surrounding_pages', 'team_other_principle', 'blind',
         'codebook_version', 'judged_on', 'coder',
         'second_coder', 'second_outcome', 'second_function', 'second_principles', 'agreement_outcome']
LISTE = {'machine_principles', 'team_principles', 'machine_surrounding_pages', 'team_surrounding_pages',
         'second_principles'}


def _data(v):
    return str(v)[:10] if v else ''


def _principi(caso, valori, nome_principio):
    if valori is None:
        return None
    return [nome_principio(caso, p) for p in valori if p not in ('nessuno', 'altro')]


def _pagine(est, c07, solo_prosegue):
    if est is None:
        return None
    out = set()
    for e in est:
        p = e.get('pagina') if isinstance(e, dict) else e
        if isinstance(e, dict) and solo_prosegue and not e.get('prosegue', True):
            continue
        if p is not None:
            out.add(p)
    return sorted(out - c07)


def _etichetta(T, tabella, codice):
    v = T[tabella].get(codice or '', T[tabella].get('', ''))
    return v[0] if isinstance(v, list) else v


def giudizio_attuale(r):
    """(outcome, who, when, round) of the most recent judgment of the row, or None"""
    if r.get('esito') in ESITO_EN:
        return r['esito'], r.get('validato_da'), r.get('validato_il'), 'uptakes'
    s = r.get('settembre') or {}
    if s.get('esito') in ESITO_EN:
        return s['esito'], s.get('validato_da'), s.get('validato_il'), 'september'
    return None


def contata(esito, stato):
    """THE RULE OF THE TECHNICAL REPORT (09/10/2026). The sealed report counts as "judged by the team" the citations of
    the release that the rich map data mark verified (the "checked by the team" of the citations file) plus the
    discarded ones: 414 + 16 = 430. Left out, as the README says: the September rows put back in the queue on 29/09
    (proposed on purpose until judged again), the confirmations recorded only as a second review without a judgment on
    the row (the map reads the row's `esito`, not the reviews), and the discards of rows that left the Uptakes queue
    (they are not in the rich map data)."""
    return (esito == 'confermata' and stato == 'verified') or (esito == 'scartata' and stato == 'discarded')


def costruisci(righe, revisioni, codici_citazioni, giudizi, T, nome_principio, stati=None):
    """righe: {id: row of corpus_rows}; revisioni: {id: {uid: document}}; codici_citazioni: the codes of the citations
    file (all states); giudizi: {case: name}; stati: {code: state in the rich map data} for counted_in_release
    (None: empty field). Returns (published_rows, {uid: pseudonym})."""
    grezze = []
    for rid, r in righe.items():
        cod = r.get('codice')
        g = giudizio_attuale(r)
        rev = sorted((revisioni.get(rid) or {}).values(), key=lambda d: str(d.get('quando')))
        if not g and rev and rev[0].get('esito') in ESITO_EN:
            # the row has no judgment of its assigned coder yet: the first judgment is the review's
            d = rev[0]
            r = {**r, **{k: v for k, v in d.items() if k.startswith('validato_') or k in ('esito', 'motivo_scarto')},
                 'validato_da': d.get('chi'), 'validato_il': d.get('quando'), '_senza_titolare': d.get('chi')}
            g = giudizio_attuale(r)
        if not cod or not g:
            continue
        if cod not in codici_citazioni and g[0] != 'scartata':
            continue
        grezze.append((rid, r, g))
    # pseudonyms: by date of first judgment, second coders included
    primo = {}
    def vedi(uid, quando):
        if uid and quando and (uid not in primo or str(quando) < primo[uid]):
            primo[uid] = str(quando)
    for rid, r, g in grezze:
        vedi(g[1], g[2])
        for uid, d in (revisioni.get(rid) or {}).items():
            vedi(d.get('chi') or uid, d.get('quando'))
    ordine = sorted(primo, key=lambda u: (primo[u], u))
    pseudo = {u: 'coder ' + (chr(65 + i) if i < 26 else chr(65 + i // 26 - 1) + chr(65 + i % 26)) for i, u in enumerate(ordine)}
    out = []
    for rid, r, (esito, chi, quando, giro) in sorted(grezze, key=lambda x: x[1]['codice']):
        caso = r.get('caso_citato')
        c07 = {e['pagina'] for e in (r.get('proposto_estensione') or []) if e.get('c07') and e.get('pagina') is not None}
        attuale = giro == 'uptakes'
        scartata = esito == 'scartata'
        ctx = r.get('validato_contesto') or {}
        if attuale and ctx.get('proposte_mostrate') is not None:
            cieca = ctx['proposte_mostrate'] is False
        elif attuale and r.get('campione_cieco') is not None:
            cieca = bool(r['campione_cieco'])
        else:
            cieca = None
        # the team does not judge type, speaker and pages of a citation it discards
        team = attuale and not scartata
        riga = {
            'citation_code': r['codice'], 'cited_judgment': giudizi.get(caso, caso), 'outcome': ESITO_EN[esito],
            'counted_in_release': '' if stati is None else ('yes' if contata(esito, stati.get(r['codice'])) else 'no'),
            'discard_reason': MOTIVO_ETICHETTA.get(r.get('motivo_scarto'), r.get('motivo_scarto') or '') if scartata else '',
            'judgment_round': 'Uptakes screen' if attuale else 'September pilot screen',
            'machine_citation_function': _etichetta(T, 'use', r.get('proposto_tipo_citazione')),
            'team_citation_function': _etichetta(T, 'use', r.get('validato_tipo_citazione')) if team and r.get('validato_tipo_citazione') else '',
            'machine_who_speaks': _etichetta(T, 'who', r.get('proposto_chi_parla')),
            'team_who_speaks': _etichetta(T, 'who', r.get('validato_chi_parla')) if team and r.get('validato_chi_parla') else '',
            'machine_where_in_text': _etichetta(T, 'where', r.get('proposto_posizione')),
            # the team's form records the part of the filing (`validato_sede`), not body/footnote: no judgment to publish
            'team_where_in_text': '',
            'machine_principles': _principi(caso, r.get('proposto_principi'), nome_principio) or [],
            'team_principles': _principi(caso, r.get('validato_principi'), nome_principio) if team else None,
            'machine_surrounding_pages': _pagine(r.get('proposto_estensione') or [], c07, True),
            'team_surrounding_pages': _pagine(r.get('validato_estensione'), c07, True) if team else None,
            'team_other_principle': (r.get('validato_principio_altro') or '') if team else '',
            'blind': ('yes' if cieca else 'no') if cieca is not None else '',
            'codebook_version': (r.get('validato_codebook_versione') or ctx.get('codebook') or '') if attuale else '',
            'judged_on': _data(quando), 'coder': pseudo.get(chi, ''),
            'second_coder': '', 'second_outcome': '', 'second_function': '', 'second_principles': None, 'agreement_outcome': '',
        }
        seconde = sorted((d for d in (revisioni.get(rid) or {}).values() if d.get('chi') != r.get('_senza_titolare')),
                         key=lambda d: str(d.get('quando')))
        if seconde:
            d = seconde[0]
            riga.update({
                'second_coder': pseudo.get(d.get('chi'), ''), 'second_outcome': ESITO_EN.get(d.get('esito'), ''),
                'second_function': _etichetta(T, 'use', d.get('validato_tipo_citazione')) if d.get('esito') != 'scartata' and d.get('validato_tipo_citazione') else '',
                'second_principles': _principi(caso, d.get('validato_principi'), nome_principio) if d.get('esito') != 'scartata' else None,
                'agreement_outcome': 'yes' if ESITO_EN.get(d.get('esito')) == riga['outcome'] else 'no'})
        out.append(riga)
    return out, pseudo


def csv_riga(x):
    return {k: ('; '.join(map(str, v)) if isinstance(v, list) else ('' if v is None else v)) for k, v in x.items()}


def conta(righe):
    c = {'rows': len(righe), 'blind': sum(1 for x in righe if x['blind'] == 'yes'),
         'double_coded': sum(1 for x in righe if x['second_coder']),
         'coders': len({x['coder'] for x in righe} | {x['second_coder'] for x in righe} - {''})}
    for o in ('confirmed', 'discarded', 'reclassified'):
        c[o] = sum(1 for x in righe if x['outcome'] == o)
        c['counted_' + o] = sum(1 for x in righe if x['outcome'] == o and x['counted_in_release'] == 'yes')
    c['counted'] = sum(1 for x in righe if x['counted_in_release'] == 'yes')
    # the judgments not counted, by reason (the three classes of the rule in contata())
    c['not_counted_september'] = sum(1 for x in righe if x['counted_in_release'] == 'no' and x['judgment_round'] == 'September pilot screen')
    c['not_counted_second_review'] = sum(1 for x in righe if x['counted_in_release'] == 'no' and x['judgment_round'] == 'Uptakes screen' and x['outcome'] != 'discarded')
    c['not_counted_outside'] = sum(1 for x in righe if x['counted_in_release'] == 'no' and x['judgment_round'] == 'Uptakes screen' and x['outcome'] == 'discarded')
    return c
