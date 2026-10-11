# CLIMPACT identifiers

One stable identifier for every object that CLIMPACT works on (cases and decisions now; later filings, laws, policies, media items, principles and traces), with a public crosswalk to the identifiers that other databases and the courts use. This folder starts with the cases cited in CLIMPACT TRACE 0.1 and their decisions.

This folder is published separately from TRACE 0.1. The TRACE 0.1 dataset, its Zenodo records and its report are unchanged.

| File | Content |
|---|---|
| `ids.csv` | the register of assigned identifiers, one per row, never deleted |
| `crosswalk.csv` | the crosswalk: one row for each link between a CLIMPACT identifier and an external identifier |
| `crosswalk.json` | the same crosswalk as JSON-LD (schema.org and SKOS), built by `genera_crosswalk_json.py` |
| `citations_to_cases.csv`, `citations_to_cases.json` | every citation of the TRACE 0.1 dataset (DOI [10.5281/zenodo.23082590](https://doi.org/10.5281/zenodo.23082590)) linked to its case and, where determined, its decision; built by `genera_citazioni_casi.py` |
| `verifica_crosswalk.py` | the check: check-digit tests, form and uniqueness offline; online, every URL and what it contains |

Licence: all files of this folder are released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The TRACE 0.1 dataset keeps its own licence.

## The cases and their decisions

| Case | Name | TRACE 0.1 citation codes | Climate Case Chart page | Wikidata |
|---|---|---|---|---|
| CL-C-000001-3 | Urgenda Foundation v. State of the Netherlands | URG- | urgenda-foundation-v-state-of-the-netherlands_3297 | Q79372212 |
| CL-C-000002-1 | Neubauer et al. v. Germany | NEU- | neubauer-et-al-v-germany_0a3e | Q118901973 |
| CL-C-000003-X | Future Generations v. Ministry of the Environment and Others | FGC- | future-generations-v-ministry-of-the-environment-and-others_f076 | not found |
| CL-C-000004-8 | Verein KlimaSeniorinnen Schweiz and Others v. Switzerland | KLS- | verein-klimaseniorinnen-schweiz-and-others-v-switzerland_6852 | Q125453801 |
| CL-C-000005-6 | Obligations of States in respect of Climate Change (ICJ advisory proceedings) | ICJ- | request-for-an-advisory-opinion-on-the-obligations-of-states-with-respect-to-climate-change_0213 | Q135448119 |
| CL-C-000006-4 | Climate Emergency and Human Rights (Inter-American Court advisory proceedings) | IAC- | request-for-an-advisory-opinion-on-the-scope-of-the-state-obligations-for-responding-to-the-climate-emergency_fbcd | not found |

| Decision | Case | Court and date | ECLI or court number |
|---|---|---|---|
| CL-D-000001-7 | CL-C-000001-3 | District Court of The Hague, 24 June 2015 | ECLI:NL:RBDHA:2015:7145 |
| CL-D-000002-5 | CL-C-000001-3 | Hague Court of Appeal, 9 October 2018 | ECLI:NL:GHDHA:2018:2591 |
| CL-D-000003-3 | CL-C-000001-3 | Supreme Court of the Netherlands, 20 December 2019 | ECLI:NL:HR:2019:2006 |
| CL-D-000004-1 | CL-C-000002-1 | Federal Constitutional Court, First Senate, 24 March 2021 | ECLI:DE:BVerfG:2021:rs20210324.1bvr265618 (Wikidata Q120442604) |
| CL-D-000005-X | CL-C-000003-X | Superior Tribunal of Bogota, 12 February 2018 | 11001-22-03-000-2018-00319-00 (no ECLI in Colombia) |
| CL-D-000006-8 | CL-C-000003-X | Supreme Court of Justice of Colombia, 5 April 2018 | STC4360-2018 |
| CL-D-000007-6 | CL-C-000004-8 | European Court of Human Rights, Grand Chamber, 9 April 2024 | ECLI:CE:ECHR:2024:0409JUD005360020 |
| CL-D-000008-4 | CL-C-000005-6 | International Court of Justice, advisory opinion, 23 July 2025 | General List No. 187 (the ICJ does not use ECLI) |
| CL-D-000009-2 | CL-C-000006-4 | Inter-American Court of Human Rights, 29 May 2025 | OC-32/25 (the Court does not use ECLI) |

The often-quoted ECLI:NL:HR:2019:2007 is the English translation of the 2019 Urgenda judgment, which the Dutch judiciary publishes under its own ECLI; the original is ECLI:NL:HR:2019:2006. Both are in the crosswalk.

## Form

`CL-<type>-<six digits>-<check>`, for example `CL-C-000001-3`.

- `CL`: CLIMPACT.
- **Type**: one capital letter, reserved now so that one scheme covers every object:

| Type | Object | Status |
|---|---|---|
| C | case (proceeding) | assigned |
| D | decision: judgment, order or advisory opinion | assigned |
| F | filing or document of the corpus | reserved |
| L | law or legal act | reserved |
| P | policy | reserved |
| M | media item | reserved |
| R | principle of the codebook | reserved |
| T | trace: the record of one citation or reception (from TRACE 0.2) | reserved |

- **Number**: six digits, in sequence within each type.
- **Check digit**: ISO 7064 Mod 11-2, the algorithm of ORCID, computed over the type and the number. The type letter counts as one symbol with its ISO 7064 / IBAN value (A = 10 ... Z = 35), followed by the six digits; the result is 0-9 or X. So `CL-C-000001` and `CL-L-000001` have different check digits. The check catches every single wrong digit, every swap of two adjacent digits, and every change between reserved types (their values are all different modulo 11).

Worked example, `CL-C-000001`, with the remainder modulo 11 taken at each step: C = 12, so (0 + 12) x 2 = 24, remainder 2; five zeros: 4, 8, 16 = 5, 10, 20 = 9; then (9 + 1) x 2 = 20 = 9; check (12 - 9) mod 11 = 3, hence `CL-C-000001-3`. `cifra_controllo()`, `valido()` and `nuovo_identificativo()` in `verifica_crosswalk.py` compute and verify it, with tests.

The identifier carries no country, court, classification or year, so it has no reason to change. Its form cannot be confused with a Climate Case Chart slug or with a TRACE 0.1 citation code.

**Stable address**: `https://www.climpact.it/id/<identifier>`, for example `https://www.climpact.it/id/CL-C-000001-3`. The type is inside the identifier, so the address does not repeat it. The longer form `https://www.climpact.it/id/<type>/<identifier>` (type as a word: case, decision, filing, law, policy, media, principle, trace) redirects to the short one. An identifier that does not exist returns 404.

## Assignment

- **In sequence within each type**, when the object first appears in a trace, in the research platform, or in a published file.
- **Never reused.** A wrong, merged or split identifier stays in the register with its status.
- **Merge** (two identifiers turn out to be the same object): the older one (lower number) stays; the other gets `status = merged` and `replaced_by`, and its address redirects to the remaining one.
- **Split** (one identifier covered two objects): two new identifiers; the old one gets `status = split` and `replaced_by` with both.
- The TRACE 0.1 cases got numbers 1 to 6 in the order of the TRACE case register; their decisions got numbers 1 to 9 in the same order, and by date within each case.

## Case and decision

A citation often names the case without saying which decision ("the Urgenda case"); others cite one decision precisely (the 2019 Supreme Court judgment, by its ECLI). Both levels exist:

- the **case** (C) is the proceeding: the dispute between the same parties in the same forum, from the claim to the last decision. It is what Climate Case Chart calls a case and what the TRACE 0.1 citation codes point to;
- a **decision** (D) is a judgment, order or advisory opinion. It has its own identifier because it can be cited on its own and has its own ECLI. Its case is recorded in `ids.csv` (column `case_id`) and in the JSON (the decisions of each case).

## Hard cases

- **Several instances of one proceeding** (Urgenda 2015, 2018, 2019): one case, one decision per instance. Opinions of the Advocate General are not decisions.
- **Original and translation with separate ECLIs** (the Netherlands): one decision; the original is `exactMatch`, the translation `closeMatch`.
- **First instance and appeal** (Future Generations: Superior Tribunal of Bogota, Supreme Court): one case, two decisions.
- **Joined complaints** (Neubauer: four constitutional complaints decided together): one case, one decision; the four docket numbers are `narrowMatch`.
- **One dispute in different forums** (KlimaSeniorinnen: the Swiss domestic proceeding and the Strasbourg case, two cases in the Climate Litigation Database too): two cases, linked with `relatedMatch`. The TRACE case is the Strasbourg one; the Swiss one will get its own identifier when it first appears.
- **Advisory opinions** (ICJ, Inter-American Court): the advisory proceeding is the case, the opinion is its decision. These courts do not use ECLI: their docket number and official URL are used instead.
- **A decision known by many names** (Klimabeschluss, Neubauer, 1 BvR 2656/18): names are search forms, never new identifiers.
- **Two external records for the same thing** (two Wikidata items for Neubauer): one `exactMatch`, the other `closeMatch` with a note.

## TRACE 0.1 citations

The codes `URG-0001`, `NEU-…`, `FGC-…`, `KLS-…`, `IAC-…`, `ICJ-…` stay as published. From TRACE 0.2 a trace gets a T identifier, and the 0.1 codes remain valid as its aliases. Each prefix is the citation-code prefix of one case (`scheme = trace_citation_prefix` in the crosswalk). New cited cases get a unique prefix of three or four letters. Grouping is always done on the case identifier, never on the prefix.

`citations_to_cases.csv` has one row for each of the 7,893 citations of TRACE 0.1: `citation_code`, `case_id`, `decision_id`, `decision_basis`, `document_id` (the filing in the Climate Litigation Database that cites), `document_url`, `dataset_doi`. The case comes from the citation-code prefix. `decision_id` is filled only when it is determined: the case has one decision (`decision_basis = only decision of the case`), or the citing sentence carries an identifier of one decision only, such as an ECLI or a docket number (`identifier in the sentence`). Court names or years in the sentence are not used. For Urgenda and Future Generations most citations name the case without an identifier, and their decision stays empty.

## The crosswalk

Columns: `climpact_id`, `case_id`, `scheme`, `external_id`, `url`, `relation`, `note`, `source`, `checked_on`, `checked_by`.

Schemes: `sabin_case` (the case page on climatecasechart.com, not the pages of single filings), `cpr_family` (Climate Policy Radar family), `cclw` (Climate Change Laws of the World), `ecli`, `hudoc`, `wikidata`, `court_number`, `court_url`, `trace_citation_prefix`.

Relations (SKOS): `exactMatch` the same thing; `closeMatch` the same thing in another form (translation, duplicate record); `narrowMatch` a part of it; `relatedMatch` related, not the same.

- A case has at most one `exactMatch` towards Climate Case Chart, and a Climate Case Chart case is the `exactMatch` of at most one CLIMPACT case.
- The pair (scheme, external identifier) is unique in the whole table.
- Every link says where it was read, when, and by whom.

The Climate Case Chart database is served by Climate Policy Radar: the same case has the same slug on climatecasechart.com, app.climatepolicyradar.org and climate-laws.org, with family identifier `Sabin.family.<n>.0`. Climate Change Laws of the World has no separate litigation record for these cases, and the crosswalk says so rather than inventing one.

## Check

```
python3 verifica_crosswalk.py --offline   # check-digit tests, form, uniqueness, consistency of the files
python3 verifica_crosswalk.py             # also every URL and its content
```

A 200 answer is not enough: the check reads the family identifier and slug on the Climate Case Chart, Climate Policy Radar and CCLW pages, asks Wikidata whether the item exists and is not a redirect, looks up Dutch ECLIs in the open data of rechtspraak.nl, and looks for the ECLI on the German court page. Sites that refuse automated requests (HUDOC at present) are reported for a manual check, not as errors. The script never corrects anything.

## Not found (10 October 2026)

- Wikidata: no item for Future Generations or for Advisory Opinion OC-32/25.
- ECLI: none exists for the Colombian, ICJ and Inter-American decisions.
- No official online text of the first-instance Future Generations judgment (Superior Tribunal of Bogota, 12 February 2018).
- No separate Climate Change Laws of the World record for any of the cases TRACE 0.1 follows.

All links were checked on 10 October 2026 by an automated check of the CLIMPACT team, still to be reviewed by a person.
