"""Links every citation of the TRACE 0.1 dataset to the CLIMPACT identifier of the cited case
(citations_to_cases.csv and citations_to_cases.json).

The TRACE 0.1 dataset is not changed: this is a separate file. The case comes from the prefix of citation_code
(the trace_citation_prefix rows of crosswalk.csv). The decision is written only when the sentence of the citation
itself determines it, and decision_basis says how:
  - "only decision of the case": the case has one decision (Neubauer, KlimaSeniorinnen, the two advisory opinions);
  - "identifier in the sentence": the sentence carries an identifier of one decision only (an ECLI, a docket number,
    STC4360-2018);
otherwise decision_id stays empty. Court names or years in the sentence are not used: they are not identifiers, and
a sentence can name a court while citing the case as a whole.

Usage: python3 genera_citazioni_casi.py [path of trace-0.1-citations.jsonl]
"""

import csv
import json
import pathlib
import sys

QUI = pathlib.Path(__file__).resolve().parent
PREDEFINITO = QUI.parent / 'trace-0.1' / 'zenodo-dati' / 'trace-0.1-citations.jsonl'
DOI_DATASET = '10.5281/zenodo.23082590'
COLONNE = ['citation_code', 'case_id', 'decision_id', 'decision_basis', 'document_id', 'document_url', 'dataset_doi']


def segni_delle_decisioni(ids, links):
    """{decision_id: [stringhe che identificano solo quella decisione]}, dagli ECLI e dai numeri della tabella."""
    segni = {r['climpact_id']: [] for r in ids if r['type'] == 'decision'}
    for l in links:
        if l['climpact_id'] in segni and l['scheme'] in ('ecli', 'court_number'):
            x = l['external_id']
            segni[l['climpact_id']].append(x)
            if x.startswith('ECLI:'):
                segni[l['climpact_id']].append(x[len('ECLI:'):])   # citato anche senza il prefisso
    return segni


def costruisci(percorso):
    ids = list(csv.DictReader((QUI / 'ids.csv').open(encoding='utf-8')))
    links = list(csv.DictReader((QUI / 'crosswalk.csv').open(encoding='utf-8')))
    caso_del_prefisso = {l['external_id']: l['climpact_id'] for l in links if l['scheme'] == 'trace_citation_prefix'}
    decisioni = {}
    for r in ids:
        if r['type'] == 'decision' and r['status'] == 'active':
            decisioni.setdefault(r['case_id'], []).append(r['climpact_id'])
    segni = segni_delle_decisioni(ids, links)
    righe = []
    for riga in percorso.open(encoding='utf-8'):
        if not riga.strip():
            continue
        c = json.loads(riga)
        caso = caso_del_prefisso[c['citation_code'].rsplit('-', 1)[0]]
        decisione, base = '', ''
        if len(decisioni.get(caso, [])) == 1:
            decisione, base = decisioni[caso][0], 'only decision of the case'
        else:
            frase = ' '.join((c.get('sentence') or '').split())
            trovate = sorted({d for d in decisioni.get(caso, []) if any(s in frase for s in segni[d])})
            if len(trovate) == 1:
                decisione, base = trovate[0], 'identifier in the sentence'
        righe.append({'citation_code': c['citation_code'], 'case_id': caso, 'decision_id': decisione,
                      'decision_basis': base, 'document_id': c['document_id'], 'document_url': c['document_url'],
                      'dataset_doi': DOI_DATASET})
    return righe


def main():
    percorso = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else PREDEFINITO
    righe = costruisci(percorso)
    with (QUI / 'citations_to_cases.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=COLONNE)
        w.writeheader()
        w.writerows(righe)
    documento = {
        'name': 'CLIMPACT TRACE 0.1: citations linked to CLIMPACT case identifiers',
        'description': 'One row for each citation of the TRACE 0.1 dataset, with the CLIMPACT identifier of the cited '
                       'case and, where the citation itself determines it, of the cited decision. Rules: RULES.md.',
        'dataset': 'CLIMPACT TRACE 0.1 citations',
        'dataset_doi': 'https://doi.org/' + DOI_DATASET,
        'license': 'https://creativecommons.org/licenses/by/4.0/',
        'publisher': 'CLIMPACT, University of Bari Aldo Moro',
        'rows': len(righe),
        'citations': [{k: v for k, v in r.items() if k != 'dataset_doi'} for r in righe],
    }
    (QUI / 'citations_to_cases.json').write_text(json.dumps(documento, ensure_ascii=False, indent=1) + '\n',
                                                 encoding='utf-8')
    con_decisione = sum(1 for r in righe if r['decision_id'])
    print(f'{len(righe)} citazioni, {con_decisione} con la decisione')


if __name__ == '__main__':
    main()
