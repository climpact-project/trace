"""I PASSAGGI PER LA PAGINA PUBBLICA DI TRACE 0.1 (27/09/2026).

   Sola lettura da Firestore. Scrive `pubblicazione/trace-0.1/passaggi.json` per la sessione che costruisce la
   pagina in Open Data:
     - `paragrafi_urgenda`: le cinque domande semantiche, con il paragrafo di Urgenda da cui vengono;
     - `confermate`: le riprese semantiche di Urgenda CONFERMATE dal team (esito confermata o riclassificata);
     - `provvisorie`: pagine del blocco 1 in lingue diverse dall'inglese, NON ancora giudicate: servono solo a
       provare l'impaginazione su lunghezze e scritture vere, mai come risultati.
   Il testo non inglese riceve una traduzione di lavoro da Cloud Translation del progetto (`gloss_en`).
"""
import json, pathlib, re, subprocess, urllib.request
import yaml
from google.cloud import firestore

QUI = pathlib.Path(__file__).resolve().parent.parent
USCITA = QUI/'pubblicazione'/'trace-0.1'/'passaggi.json'
TITOLI_EN = {
    'propria_quota': 'Responsibility for its own share: a small contribution is no excuse',
    'obblighi_positivi': 'Positive obligations under Articles 2 and 8 ECHR against a deferred and diffuse climate risk',
    'dovere_diligenza': 'Civil-law duty of care: insufficient mitigation as a wrong against citizens',
    'ordine_non_legge': 'An order to achieve a result is not an order to legislate',
    'target_giudiziale': 'A court may set a quantified minimum drawn from scientific and international consensus',
}
NOMINA = re.compile(r'urgenda|ECLI:NL:HR:2019:2007|ECLI:NL:GHDHA:2018:2591|ECLI:NL:RBDHA:2015:7145', re.I)
GRADO_EN = {'Hoge Raad, 20 dicembre 2019': 'Supreme Court of the Netherlands, 20 December 2019',
            'Rechtbank Den Haag, 24 giugno 2015': 'District Court of The Hague, 24 June 2015'}


def traduci(testi):
    tok = subprocess.run(['gcloud', 'auth', 'print-access-token'], capture_output=True, text=True, check=True).stdout.strip()
    out = []
    for i in range(0, len(testi), 50):
        corpo = json.dumps({'contents': testi[i:i+50], 'targetLanguageCode': 'en', 'mimeType': 'text/plain'}).encode()
        rq = urllib.request.Request('https://translation.googleapis.com/v3/projects/climpact-drp:translateText', data=corpo,
                                    headers={'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json',
                                             'x-goog-user-project': 'climpact-drp'})
        out += json.load(urllib.request.urlopen(rq))['translations']
    return out


def main():
    conf = yaml.safe_load(open(QUI/'cited-cases'/'urgenda.yaml', encoding='utf-8'))
    per_titolo = {}
    paragrafi = []
    for s in conf['semantic_queries']:
        per_titolo[' '.join(s['titolo'].split())] = s['id']
        paragrafi.append({'id': s['id'], 'title': TITOLI_EN[s['id']], 'paragraph': s.get('canonical_paragrafo'),
                          'court': GRADO_EN.get(s.get('canonical_grado'), s.get('canonical_grado')),
                          'text': ' '.join(s['canonical'].split()), 'query': ' '.join(s['testo'].split())})

    def sonda_id(t):
        t = ' '.join(t.replace('[2a formulazione]', '').split())
        return per_titolo.get(t, t)

    db = firestore.Client(project='climpact-drp')
    righe = [dict(_id=d.id, **d.to_dict()) for d in db.collection('corpus_rows')
             .where(filter=firestore.FieldFilter('caso_citato', '==', 'urgenda')).stream()]
    conferme = []
    for r in righe:
        if r.get('proposto_rete') not in ('semantica', 'entrambe') or r.get('esito') not in ('confermata', 'riclassificata'):
            continue
        v = r.get('validato_sonde') or []
        v = [v] if isinstance(v, str) else v
        conferme.append({
            'row_id': r['_id'], 'case': r.get('case_name'), 'jurisdictions': [g.strip() for g in (r.get('giurisdizioni') or '').split(';') if g.strip()],
            'year_in_database': str(r.get('data') or '')[:4], 'document_type_it': r.get('tipo_atto'), 'document_id': r['document_id'],
            'page': r.get('validato_pagina') or r.get('proposto_pagina'),
            'found_by': 'semantic and lexical' if r.get('proposto_rete') == 'entrambe' else 'semantic',
            'matches': sorted({sonda_id(x) for x in v}),
            'passage': ' '.join(str(r.get('validato_citazione_testuale') or r.get('proposto_citazione_testuale') or '').split()),
            'proposition': ' '.join(str(r.get('validato_proposizione') or r.get('proposto_proposizione') or '').split()),
            'source_url': r.get('url_documento'), 'esito': r['esito'],
            'validated_citation_type': r.get('validato_tipo_citazione') or ''})
    for x in conferme:
        x['passage_names_urgenda'] = bool(NOMINA.search(x['passage']))
        # SULLA MAPPA DELLE RIPRESE IMPLICITE solo le righe confermate: «riclassificata» vuol dire sia «ripresa buona,
        # domanda sbagliata» sia «non e' una ripresa» (Carvalho, Western Watersheds, Shell p. 87...), e la differenza
        # sta solo nella nota in prosa. Fuori anche le righe col nome di Urgenda nel brano o con un tipo di citazione
        # esplicita dato dal validatore: sono citazioni, non riprese implicite.
        x['on_implicit_map'] = (x['esito'] == 'confermata' and not x['passage_names_urgenda']
                                and not x['validated_citation_type'] and bool(x['matches']))
    blocco = json.load(open(QUI/'training'/'fase2'/'urgenda_blocco1_passaggi.json', encoding='utf-8'))
    provv = [{'document_id': x['document_id'], 'page': x['pagina'], 'rank_in_trace_list': x['posto_lista'],
              'query': x['sonda'].replace('__alt', ''), 'passage': ' '.join(x['passaggio'].split())} for x in blocco]
    tutti = conferme + provv
    tr = traduci([x['passage'] for x in tutti])
    for x, t in zip(tutti, tr):
        x['language'] = t.get('detectedLanguageCode')
        if x['language'] != 'en':
            x['gloss_en'] = t['translatedText']
    provv = [x for x in provv if x['language'] != 'en']
    USCITA.parent.mkdir(parents=True, exist_ok=True)
    USCITA.write_text(json.dumps({
        'nota': ('on_implicit_map = the only rows to show as implicit uptakes. '
                 'confermate = judged by the team (confirmed or reclassified). provvisorie = NOT yet judged, first block of '
                 'the new chain: layout testing only, never to be shown as findings. gloss_en = machine working translation. '
                 'year_in_database comes from the Sabin database and is not always the document date.'),
        'paragrafi_urgenda': paragrafi, 'confermate': conferme, 'provvisorie': provv}, ensure_ascii=False, indent=1), encoding='utf-8')
    print(len(conferme), 'confermate,', len(provv), 'provvisorie non inglesi ->', USCITA)


if __name__ == '__main__':
    main()
