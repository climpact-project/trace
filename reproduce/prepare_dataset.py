"""The TRACE 0.1 dataset files (Zenodo, DOI 10.5281/zenodo.23082590): citations, team judgments, README, SHA256SUMS.

Original: `pubblicazione/trace-0.1/prepara_dati_zenodo.py` of the TRACE working tree (1/10/2026, six judgments since
3/10/2026; team judgments since 7/10/2026), with `team_judgments.py` next to it (here `reproduce/team_judgments.py`). The
computation is the same; the paths are arguments, Firestore is optional, and the private uid -> pseudonym file is
written only when asked. Italian strings that are data (labels written into the outputs, messages) are unchanged.

The data are released under CC BY-NC 4.0 (the more prudent of the two licences on the Sabin Center site), so they sit
in a Zenodo record of their own, apart from the code and models (MIT).

`build` reads the rich map data (`dati_ricchi.json`: the citations of the six judgments), `casi.json` (the judgments:
name, court, date, in date order) and `globo/dati.js` (the English labels, document types, courts, principles), leaves
out the citations the team discarded, and writes into --out-dir:
  trace-0.1-citations.csv     one row per citation
  trace-0.1-citations.jsonl   the same, one JSON object per line (real lists)
  trace-0.1-team-judgments.csv / .jsonl   the team judgments, discarded citations included (07/10/2026). They are
                              built from Firestore, read only (corpus_rows and their `revisioni`), or taken from a
                              published team-judgments JSONL with --team-judgments-from
  README.md                   fields, licence, how to read the review status
  SHA256SUMS.txt

Nothing is written by hand: the judgments, the code prefixes and the sentences on the state of the review and of the
majority vote (R11) come from the data.

`check` needs only the published dataset: it recounts from trace-0.1-citations.jsonl and trace-0.1-team-judgments.jsonl
the figures the README and the technical report quote (citations, documents, checked rows, five readings, rules, team
judgments counted and not counted) and checks SHA256SUMS.txt.

Usage:
  python reproduce/prepare_dataset.py build --map-dir pubblicazione/mappa --out-dir zenodo-dati \\
      [--team-judgments-from trace-0.1-team-judgments.jsonl | --firestore-project climpact-drp] [--private-map FILE]
  python reproduce/prepare_dataset.py check --dataset <folder of the Zenodo dataset>
"""
# The build code keeps the frozen original line for line, so that the two can be compared: its names, long lines and
# file handling are not restyled.
# ruff: noqa: E501, F541, N803, N806, N812, SIM115
import argparse
import ast
import csv
import hashlib
import json
import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import team_judgments as TJ

# the document type when the filing is missing from the globe data: from the Italian word of the rich map data
ATTO_EN = {'decisione': 'Decision', 'atto introduttivo': 'Application', 'replica': 'Reply', 'memoria': 'Brief',
           'amicus': 'Amicus brief', 'ordinanza': 'Order', 'istanza': 'Motion', 'avviso': 'Notice',
           'comunicato': 'Press release', 'relazione': 'Report', 'altro': 'Other filing'}
FILE_PUBBLICATI = ['trace-0.1-citations.csv', 'trace-0.1-citations.jsonl', 'trace-0.1-team-judgments.csv',
                   'trace-0.1-team-judgments.jsonl', 'README.md']


def leggi_firestore(GIUDIZI, progetto):
    """READ ONLY: the rows of the six judgments and the second reviews (corpus_rows/<id>/revisioni/<uid>)"""
    from google.cloud import firestore
    db = firestore.Client(project=progetto)
    rr, rev = {}, {}
    for caso in GIUDIZI:
        for d in db.collection('corpus_rows').where(filter=firestore.FieldFilter('caso_citato', '==', caso)).stream():
            rr[d.id] = json.loads(json.dumps(d.to_dict(), default=str))
    for d in db.collection_group('revisioni').stream():
        rev.setdefault(d.reference.parent.parent.id, {})[d.id] = json.loads(json.dumps(d.to_dict(), default=str))
    nomi = {}
    for u in {x.get('validato_da') for x in rr.values()} | {(x.get('settembre') or {}).get('validato_da') for x in rr.values()} \
            | {k for v in rev.values() for k in v}:
        if u:
            nomi[u] = db.collection('users').document(u).get().to_dict() or {}
    return rr, rev, nomi


def build(a):
    MAPPA = pathlib.Path(a.map_dir)
    FUORI = pathlib.Path(a.out_dir)
    FUORI.mkdir(parents=True, exist_ok=True)
    r = json.load(open(MAPPA / 'dati_ricchi.json', encoding='utf-8'))
    casi = json.load(open(MAPPA / 'casi.json', encoding='utf-8'))['casi']
    s = open(MAPPA / 'globo' / 'dati.js', encoding='utf-8').read()
    g = json.loads(s[s.index('{'):s.rindex('}') + 1])
    T = g['T']
    F = {f['id']: f for f in g['F']}
    P = {p['id']: p['label'] for p in g['P']}
    for k, v in r.get('principi', {}).items():
        P.setdefault(k, v.get('titolo_en') or k)
    DOC = {d['id']: d for d in r['documenti']}
    GIUDIZI = {c['id']: c['nome'] for c in casi}
    def lista(v):
        """List fields come as lists or as Python strings ("['a', 'b']")."""
        if isinstance(v, list):
            return v
        if not v or v == 'None':
            return []
        try:
            x = ast.literal_eval(v)
            return x if isinstance(x, list) else []
        except (ValueError, SyntaxError):
            return []


    def etichetta(tabella, codice):
        v = T[tabella].get(codice or '', T[tabella].get('', ''))
        return v[0] if isinstance(v, list) else v


    def principio(caso, p):
        return P.get(p) or P.get(f'{caso}.{p}') or p


    righe = []
    for c in r['citazioni']:
        if c.get('stato') == 'discarded':
            continue
        d = DOC.get(c['doc'], {})
        f = F.get(c['doc'], {})
        prov = (c.get('spiega') or {}).get('provenienza') or {}
        # THE FIVE READINGS (07/10/2026): not only the R11 rows; the R15 and R16 compositions use five readings too.
        # The datum is provenienza.letture = {tipo: n, principi: n}, the number of valid readings written with the row:
        # "yes" only if BOTH (function and principles) have five; without the field (rows never read) "no".
        letture = prov.get('letture') or {}
        righe.append({
            'citation_code': c['codice'],
            'cited_judgment': GIUDIZI.get(c['caso'], c['caso']),
            'document_id': c['doc'],
            'document_name': f.get('name') or d.get('nome', ''),
            'document_type': f.get('type') or ATTO_EN.get(d.get('atto', ''), d.get('atto', '')),
            'document_date': d.get('data_documento') or '',
            'document_year': f.get('year') or d.get('anno', ''),
            'court': '; '.join(f.get('courts') or []) or d.get('sede', ''),
            'country': f.get('country') or d.get('giur', ''),
            'document_url': f.get('url') or d.get('url', ''),
            'page': c.get('pagina') or '',
            'citation_function': etichetta('use', c.get('tipo')),
            'who_speaks': etichetta('who', c.get('chi_parla')),
            'where_in_text': etichetta('where', c.get('posizione')),
            'principles': [principio(c['caso'], p) for p in lista(c.get('principi'))],
            'cited_paragraphs': lista(c.get('paragrafi')),
            'surrounding_pages': lista(c.get('seguito')),
            'review_status': 'checked by the team' if c.get('stato') == 'verified' else 'proposed by the machine, not yet checked',
            'found_by': prov.get('estrazione') or '',
            'corpus_version': prov.get('corpus') or '',
            'proposal_rule': prov.get('composizione') or '',
            'five_readings': 'yes' if (letture.get('tipo') == 5 and letture.get('principi') == 5) else 'no',
            # the DESCRIPTIVE NETWORK of S07 (07/10/2026): rows found without the name in the passage; precision measured apart
            'reference_kind': 'descriptive' if (c.get('spiega') or {}).get('corroborazione') == 'descrizione' else 'named',
            'sentence': c.get('frase') or '',
            'passage': c.get('passaggio') or '',
        })

    CAMPI = list(righe[0].keys())
    with open(FUORI / 'trace-0.1-citations.csv', 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPI)
        w.writeheader()
        for x in righe:
            w.writerow({k: ('; '.join(map(str, v)) if isinstance(v, list) else v) for k, v in x.items()})
    with open(FUORI / 'trace-0.1-citations.jsonl', 'w', encoding='utf-8') as fh:
        for x in righe:
            fh.write(json.dumps(x, ensure_ascii=False) + '\n')

    verificate = sum(1 for x in righe if x['review_status'].startswith('checked'))
    # THE SENTENCE ON THE REVIEW IS WRITTEN FROM THE DATA (1/10/2026): if every row is checked it says so, otherwise it
    # gives the true share.
    if verificate == len(righe):
        STATO = '- Every citation in this release was checked by the CLIMPACT team.'
    else:
        # the beta under verification, the verified share said once as a fact (3/10/2026)
        STATO = (f'- TRACE 0.1 is a beta release under verification by the CLIMPACT research team, for all six judgments: at release, '
                 f'{verificate:,} of {len(righe):,} citations have been verified, and the others are **machine proposals**. Read '
                 '`review_status` before using a row, and do not present a proposal as a finding.')
        print(f'ATTENZIONE: controllate {verificate} su {len(righe)}, il README lo dice')
    # THE FIVE READINGS (07/10/2026): the sentence "N of M unchecked rows proposed by a majority of five readings" counted
    # only proposal_rule R11, but R15 and R16 compose with the five readings too. The rows that really have them are
    # counted (field five_readings, from provenienza.letture), checked or not, and the rule is named only for what it is.
    regole = Counter(x['proposal_rule'] for x in righe if not x['review_status'].startswith('checked'))
    r11 = regole.get('R11', 0)
    da_proporre = sum(regole.values())
    cinque = sum(1 for x in righe if x['five_readings'] == 'yes')
    cinque_da_proporre = sum(1 for x in righe if x['five_readings'] == 'yes' and not x['review_status'].startswith('checked'))
    senza_cinque = len(righe) - cinque
    if cinque == len(righe):
        VOTO = (f'- Every row carries five readings of its citation function and of its principles by DeepSeek V4 Flash, a large language model with open weights run by the project at ReCaS-Bari; '
                'the proposals are the majority vote of the five readings (field `five_readings`).')
    else:
        VOTO = (f'- {cinque:,} of {len(righe):,} rows ({cinque_da_proporre:,} of the {da_proporre:,} not yet checked by the team) carry five readings by DeepSeek V4 Flash, '
                'a large language model with open weights run by the project at ReCaS-Bari, both for the function of the citation and for the principles; '
                'their proposals are the majority vote of the five readings, with the rules R11, R15 and R16 named in `proposal_rule` (all three use the five readings). '
                f'The other {senza_cinque:,} rows (field `five_readings` = no) have not had both sets of five readings yet: their proposals come from the rule named in `proposal_rule`, and they are to be read five times.')
    documenti = len({x['document_id'] for x in righe})
    nomi = [GIUDIZI[c['id']] for c in casi]
    elenco_nomi = ', '.join(nomi[:-1]) + ' and ' + nomi[-1]
    prefissi = sorted({x['citation_code'].split('-')[0] + '-' for x in righe})
    scartate = sum(1 for c in r['citazioni'] if c.get('stato') == 'discarded')


    if a.team_judgments_from:
        # from files: the published team judgments (trace-0.1-team-judgments.jsonl) instead of the Firestore rows; the
        # uid -> pseudonym pairing is not known, so the private file cannot be written
        GRUPPO = [json.loads(x) for x in open(a.team_judgments_from, encoding='utf-8')]
        PSEUDONIMI, UTENTI = {}, {}
    else:
        RIGHE_VIVE, REVISIONI, UTENTI = leggi_firestore(GIUDIZI, a.firestore_project)
        GRUPPO, PSEUDONIMI = TJ.costruisci(RIGHE_VIVE, REVISIONI, {c['codice'] for c in r['citazioni']}, GIUDIZI, T, principio,
                                            stati={c['codice']: c.get('stato') for c in r['citazioni']})
    GJ = TJ.conta(GRUPPO)
    # counted_in_release (09/10/2026): the counted judgments must be exactly the checked rows of the citations file plus
    # the discarded rows of the rich map data, i.e. the figures of the report; the others must all fall in one of the
    # three classes
    assert GJ['counted_confirmed'] == verificate and GJ['counted_discarded'] == scartate and GJ['counted_reclassified'] == 0, GJ
    assert GJ['counted'] + GJ['not_counted_september'] + GJ['not_counted_second_review'] + GJ['not_counted_outside'] == GJ['rows'], GJ
    _contati = {x['citation_code'] for x in GRUPPO if x['counted_in_release'] == 'yes' and x['outcome'] == 'confirmed'}
    assert _contati == {x['citation_code'] for x in righe if x['review_status'].startswith('checked')}, 'controllate e giudizi contati divergono'
    _sett_conf = sum(1 for x in GRUPPO if x['counted_in_release'] == 'no' and x['judgment_round'] == 'September pilot screen' and x['outcome'] == 'confirmed')
    _sett_ricl = GJ['not_counted_september'] - _sett_conf


    def _n(k, uno, molti):
        return f'{k:,} {uno if k == 1 else molti}'


    with open(FUORI / 'trace-0.1-team-judgments.csv', 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=TJ.CAMPI)
        w.writeheader()
        for x in GRUPPO:
            w.writerow(TJ.csv_riga(x))
    with open(FUORI / 'trace-0.1-team-judgments.jsonl', 'w', encoding='utf-8') as fh:
        for x in GRUPPO:
            fh.write(json.dumps(x, ensure_ascii=False) + '\n')
    # the uid -> pseudonym pairing is written only where --private-map says (originally training/, outside git), never
    # in the deposit
    if a.private_map and PSEUDONIMI:
        pathlib.Path(a.private_map).write_text(json.dumps({p: {'uid': u, 'nome': (UTENTI.get(u) or {}).get('name') or ' '.join(
            y for y in ((UTENTI.get(u) or {}).get('first_name'), (UTENTI.get(u) or {}).get('last_name')) if y),
            'email': (UTENTI.get(u) or {}).get('email')} for u, p in PSEUDONIMI.items()}, ensure_ascii=False, indent=1), encoding='utf-8')
    print('giudizi del team', GJ)
    LEGGIMI = f"""# CLIMPACT TRACE 0.1, dataset

The citations of six climate judgments and advisory opinions ({elenco_nomi}) found by CLIMPACT TRACE 0.1 in later climate litigation.

- {len(righe):,} citations in {documenti:,} documents.
{STATO}
{VOTO}
- {scartate:,} citations the team discarded are left out of the citations file; they are listed, with the reason, in the team judgments file.
- {GJ['rows']:,} team judgments ({GJ['confirmed']:,} confirmed, {GJ['discarded']:,} discarded, {GJ['reclassified']:,} reclassified), {GJ['blind']:,} of them given blind and {GJ['double_coded']:,} double-coded, by {GJ['coders']} anonymous coders. {GJ['counted']:,} of them ({GJ['counted_confirmed']:,} confirmed, {GJ['counted_discarded']:,} discarded) are the judgments this release counts, marked `counted_in_release` = yes: they are the base of the precision checked by the team in the technical report.

## Files

- `trace-0.1-citations.csv`: one row per citation. Lists are joined with "; ".
- `trace-0.1-citations.jsonl`: the same rows as JSON, one per line, with real lists.
- `trace-0.1-team-judgments.csv`: one row per citation judged by the CLIMPACT team, discarded citations included. Lists are joined with "; ".
- `trace-0.1-team-judgments.jsonl`: the same rows as JSON, with real lists.

## Fields

| field | meaning |
|---|---|
| citation_code | permanent code of the citation in TRACE ({', '.join(prefissi)}) |
| cited_judgment | the judgment or advisory opinion cited |
| document_id, document_name, document_type, document_date, document_year | the citing document |
| court, country | where the citing document comes from |
| document_url | the document in the Sabin Center Climate Litigation Database |
| page | page of the citing document where the citation is |
| citation_function | what the citation does with the judgment (Substantive, Descriptive, Distinguishing, Critical, Chain mention) |
| who_speaks | who makes the citation (the court, a party, an amicus curiae, an intervener) |
| where_in_text | body of the text or footnote |
| principles | principles of the cited judgment the citation takes up, as proposed by the machine or checked by the team |
| cited_paragraphs | paragraphs of the cited judgment named in the citation |
| surrounding_pages | pages up to ten before or after the citation where the filing develops the same principle without naming the judgment |
| review_status | checked by the team, or proposed by the machine and not yet checked |
| found_by | version code of the name search that found the citation (an S code; every code is listed with its name in the technical report) |
| corpus_version | version code of the document text the citation was read on (a D code, listed with its name in the technical report) |
| proposal_rule | version code of the rule that put the machine proposals together (an R code, listed with its name in the technical report) |
| reference_kind | named if the passage names the judgment; descriptive if the row was found by the descriptive network of the name search S07, which looks for references that describe the judgment (its court, year and subject, or a short form such as "BVerfG, a.a.O.") without naming it. The technical report gives the precision of the descriptive rows apart |
| five_readings | yes if the function of the citation and its principles were both read five times by DeepSeek V4 Flash and the proposal is their majority vote (rules R11, R15 and R16 all do this), no for the rows that have not had both sets of five readings yet |
| sentence, passage | the citing sentence and the passage around it, from the citing document |

## Team judgments

`trace-0.1-team-judgments.csv` gives, for each citation the team judged, what the machine proposed next to what the team decided, so that agreement between the two can be measured. It covers the same citations as the citations file plus the ones the team discarded.

| field | meaning |
|---|---|
| citation_code, cited_judgment | the citation and the judgment cited, as in the citations file |
| outcome | confirmed, discarded (not a citation of the judgment), or reclassified (the passage was kept under another reading) |
| counted_in_release | yes if the release counts the judgment (see below), no otherwise |
| discard_reason | for discarded citations, the reason the coder gave, as a short English label |
| judgment_round | the screen of the platform where the judgment was given: the September pilot screen (outcome, coder and date only) or the Uptakes screen (all fields) |
| machine_citation_function, team_citation_function | what the citation does with the judgment, as proposed and as decided |
| machine_who_speaks, team_who_speaks | who makes the citation, as proposed and as decided |
| machine_where_in_text, team_where_in_text | body of the text or footnote. The coders' form records the part of the filing instead (party filing, reasoning, dissent), not body or footnote, so the team column is empty |
| machine_principles, team_principles | principles of the cited judgment taken up, as names, as proposed and as decided |
| machine_surrounding_pages, team_surrounding_pages | page numbers where the filing develops the same principle without naming the judgment, as proposed and as decided |
| team_other_principle | a principle outside the list, in the coder's words |
| blind | yes if the coder gave the judgment without the machine proposal on the screen, no if it was visible; empty for the September pilot screen |
| codebook_version | version of the coding guide the coder followed |
| judged_on | date of the judgment (no time) |
| coder | pseudonym of the coder (coder A, coder B, ...), numbered by the date of each coder's first judgment and stable across the file |
| second_coder, second_outcome, second_function, second_principles, agreement_outcome | for double-coded citations, the second coder's pseudonym, outcome, citation function and principles, and whether the two outcomes agree (yes or no) |

For a discarded citation the team columns for function, speaker, principles and pages are empty: the coders do not judge them once the citation is discarded. A team column is also empty when the judgment came from the September pilot screen, which did not record it. The machine columns show the proposals as they were made, so for citations the team judged they can be compared with the decision.

`counted_in_release` says which judgments this release counts. It is yes for {GJ['counted']:,} judgments: the {GJ['counted_confirmed']:,} confirmations of the citations marked "checked by the team" in the citations file and the {GJ['counted_discarded']:,} discards of citations of this release. They are the {GJ['counted']:,} citations judged by the team on which the technical report gives the precision ({GJ['counted_confirmed']:,} confirmed, {GJ['counted_discarded']:,} discarded); the counts of the whole file above include the others. It is no for {GJ['rows'] - GJ['counted']:,} judgments: {_n(GJ['not_counted_september'], 'judgment', 'judgments')} given on the September pilot screen ({_sett_conf:,} confirmed, {_sett_ricl:,} reclassified), whose citations were put back in the review queue on 29 September 2026 and stay machine proposals in the citations file until the team judges them again on the Uptakes screen; {_n(GJ['not_counted_second_review'], 'confirmation', 'confirmations')} given by a coder other than the one the row is assigned to, before the assigned coder judged it, while the release takes the review status from the assigned coder's judgment, so these citations are still machine proposals in the citations file; and {_n(GJ['not_counted_outside'], 'discard of a row', 'discards of rows')} outside the review queue of this release, which is not among its citations.

Not published: the coders' names, accounts and emails (the coders appear only as pseudonyms, so that no judgment can be traced to a person), the time spent on each row, and the free-text notes the coders wrote, which can name people and were written as working notes, not for publication. The pseudonyms cannot be linked to people from this record.

## Source and licence

The citing documents come from the Sabin Center for Climate Change Law, Climate Litigation Database (climatecasechart.com), with Climate Policy Radar, read through its public API. The sentences and passages are short excerpts of those documents. Following the Center's terms, this dataset is released under **Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)**. The code and models of TRACE are a separate record, under the MIT licence. The technical report in both records describes every version code.

## Citation

Naglieri, G., Buono, E., Garofalo, C., Saracino, C., Dell'Atti, L., Rojas Verdugo, G. A. (2026). CLIMPACT TRACE 0.1: Traceable Reception and Attribution in Climate-law Evidence. CLIMPACT, University of Bari. Zenodo.
"""
    (FUORI / 'README.md').write_text(LEGGIMI, encoding='utf-8')

    with open(FUORI / 'SHA256SUMS.txt', 'w', encoding='utf-8') as fh:
        for nome in ['trace-0.1-citations.csv', 'trace-0.1-citations.jsonl', 'trace-0.1-team-judgments.csv',
                     'trace-0.1-team-judgments.jsonl', 'README.md']:
            fh.write(hashlib.sha256((FUORI / nome).read_bytes()).hexdigest() + '  ' + nome + '\n')
    print(f'citazioni {len(righe)}, documenti {documenti}, controllate {verificate}, scartate {scartate}, R11 {r11} su {da_proporre}, cinque letture {cinque} (non controllate {cinque_da_proporre}), campi {len(CAMPI)}')


def check(a):
    """Recount from the published dataset the figures of its README and of the technical report."""
    D = pathlib.Path(a.dataset)
    righe = [json.loads(x) for x in open(D / 'trace-0.1-citations.jsonl', encoding='utf-8')]
    GRUPPO = [json.loads(x) for x in open(D / 'trace-0.1-team-judgments.jsonl', encoding='utf-8')]
    controllate = [x for x in righe if x['review_status'].startswith('checked')]
    da_proporre = [x for x in righe if not x['review_status'].startswith('checked')]
    out = {
        'citations': len(righe),
        'documents': len({x['document_id'] for x in righe}),
        'checked_by_the_team': len(controllate),
        'five_readings': sum(1 for x in righe if x['five_readings'] == 'yes'),
        'five_readings_not_checked': sum(1 for x in da_proporre if x['five_readings'] == 'yes'),
        'not_checked': len(da_proporre),
        'proposal_rule_not_checked': dict(sorted(Counter(x['proposal_rule'] for x in da_proporre).items())),
        'reference_kind': dict(sorted(Counter(x['reference_kind'] for x in righe).items())),
        'per_judgment': dict(Counter(x['cited_judgment'] for x in righe)),
        'team_judgments': TJ.conta(GRUPPO),
    }
    # the same consistency checks as `build`: the counted confirmations are exactly the checked citations
    contati = {x['citation_code'] for x in GRUPPO if x['counted_in_release'] == 'yes' and x['outcome'] == 'confirmed'}
    out['counted_confirmations_equal_checked_citations'] = contati == {x['citation_code'] for x in controllate}
    somme = D / 'SHA256SUMS.txt'
    if somme.exists():
        esiti = {}
        for riga in somme.read_text(encoding='utf-8').split('\n'):
            if riga.strip():
                h, nome = riga.split(None, 1)
                f = D / nome.strip()
                esiti[nome.strip()] = f.exists() and hashlib.sha256(f.read_bytes()).hexdigest() == h
        out['sha256sums_match'] = esiti
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description='The TRACE 0.1 dataset files: build them, or recount the published ones.')
    sub = ap.add_subparsers(dest='fase', required=True)
    b = sub.add_parser('build', help='write the dataset files from the rich map data (not published) and the team judgments')
    b.add_argument('--map-dir', required=True, help='folder with dati_ricchi.json, casi.json and globo/dati.js')
    b.add_argument('--out-dir', required=True, help='where the dataset files are written')
    g = b.add_mutually_exclusive_group()
    g.add_argument('--team-judgments-from', help='published trace-0.1-team-judgments.jsonl: use it instead of Firestore')
    g.add_argument('--firestore-project', default='climpact-drp', help='Firestore project read (read only) by default')
    b.add_argument('--private-map', help='write here the uid -> pseudonym pairing (never in the deposit); default: not written')
    c = sub.add_parser('check', help='recount the figures from the published dataset (public files only)')
    c.add_argument('--dataset', required=True, help='folder of the Zenodo dataset (DOI 10.5281/zenodo.23082590)')
    a = ap.parse_args(argv)
    if a.fase == 'build':
        build(a)
    else:
        check(a)


if __name__ == '__main__':
    main()
