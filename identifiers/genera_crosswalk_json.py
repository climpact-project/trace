"""Builds crosswalk.json (JSON-LD, schema.org + SKOS) from ids.csv and crosswalk.csv.

The two CSV files are the source: they are edited by hand, this script only rewrites the JSON.
Usage: python3 genera_crosswalk_json.py   (from this folder, standard library only)
"""

import csv
import json
import pathlib

QUI = pathlib.Path(__file__).resolve().parent
BASE = 'https://www.climpact.it/id/'


def uri(climpact_id):
    return BASE + climpact_id   # il tipo e' dentro l'identificativo: /id/<id>; /id/<tipo>/<id> rimanda qui


def costruisci():
    ids = list(csv.DictReader((QUI / 'ids.csv').open(encoding='utf-8')))
    links = list(csv.DictReader((QUI / 'crosswalk.csv').open(encoding='utf-8')))
    per_id = {}
    for link in links:
        per_id.setdefault(link['climpact_id'], []).append({
            'scheme': link['scheme'],
            'externalId': link['external_id'],
            **({'url': link['url']} if link['url'] else {}),
            'relation': 'skos:' + link['relation'],
            **({'note': link['note']} if link['note'] else {}),
            'source': link['source'],
            'checkedOn': link['checked_on'],
            'checkedBy': link['checked_by'],
        })

    def nodo(r):
        n = {
            '@id': uri(r['climpact_id']),
            '@type': 'schema:Legislation' if r['type'] == 'decision' else 'skos:Concept',
            'identifier': r['climpact_id'],
            'name': r['label'],
            'date': r['date'],
            'court': r['court'],
            'status': r['status'],
        }
        if r['replaced_by']:
            n['replacedBy'] = [uri(x) for x in r['replaced_by'].split(';')]
        if r['citation_prefix']:
            n['citationCodePrefix'] = r['citation_prefix']
        if r['first_release']:
            n['firstRelease'] = r['first_release']
        n['links'] = per_id.get(r['climpact_id'], [])
        return n

    casi = []
    for r in ids:
        if r['type'] == 'case':
            caso = nodo(r)
            caso['decisions'] = [nodo(d) for d in ids if d['type'] == 'decision' and d['case_id'] == r['climpact_id']]
            casi.append(caso)
    return {
        '@context': {
            'schema': 'https://schema.org/',
            'skos': 'http://www.w3.org/2004/02/skos/core#',
            'dcterms': 'http://purl.org/dc/terms/',
            'identifier': 'schema:identifier',
            'name': 'schema:name',
            'date': 'schema:dateCreated',
            'license': {'@id': 'schema:license', '@type': '@id'},
            'url': {'@id': 'schema:url', '@type': '@id'},
            'decisions': {'@id': 'schema:hasPart', '@container': '@list'},
            'replacedBy': {'@id': 'dcterms:isReplacedBy', '@type': '@id'},
        },
        'name': 'CLIMPACT case identifiers: crosswalk to external identifiers',
        'description': 'One CLIMPACT identifier per case (CL-C-000001-3) and per decision (CL-D-000001-7), with the '
                       'equivalent identifiers in the Sabin Center Climate Litigation Database, Climate Policy Radar, '
                       'Climate Change Laws of the World, ECLI, Wikidata and the courts. Rules: RULES.md.',
        'publisher': 'CLIMPACT, University of Bari Aldo Moro',
        'license': 'https://creativecommons.org/licenses/by/4.0/',
        'dateModified': max(link['checked_on'] for link in links),
        'cases': casi,
    }


if __name__ == '__main__':
    (QUI / 'crosswalk.json').write_text(json.dumps(costruisci(), ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('crosswalk.json scritto')
