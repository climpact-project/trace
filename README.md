# TRACE

**Tracing how climate judgments are taken up in later litigation.** TRACE is developed by the CLIMPACT project (University of Bari).

This repository holds the code, the case files, the codebook and the registry of versions behind TRACE. It is a research release under active development. It is private until the release of TRACE 0.1 (12 October 2026) and opens with it.

## What TRACE does

For any climate judgment (the *cited case*; so far Urgenda, Neubauer and Future Generations), TRACE finds every later filing that cites it and records, for each citation, what the citing text does with it. Every step has a version code (see below).

1. **Documents (D01).** The Climate Litigation Database, whole-database export, with the text of every page.
2. **Name search (S02).** A plain text search, with no AI, looks for the name of the case in every page, in all the forms it takes: names, ECLI numbers, docket numbers, translations, other scripts, common OCR errors. Each hit becomes a citation with a permanent code: `URG-0146`, `NEU-0412`, `FGC-0033`. Most rows in the platform were found by the first version of the search (S01) and found again by S02, which added and merged the rows the first version had missed or split.
3. **Paragraph map (R01).** When the citation points to a paragraph of the judgment (`para. 5.7.7`), a hand-written map gives the principle that paragraph holds. No model is involved.
4. **Citation reading (L02, L03).** The external reader (DeepSeek V4 Flash) reads the citation in context and proposes: is it really the judgment; what the citation does (chain mention, descriptive, substantive, distinguishing, critical); who speaks; the proposition it supports.
5. **Reranker (T01) and the choice of pages (R03).** The project's own model scores the passage, and the pages around it (up to ten pages on each side), against each principle of the case. A rule (R03) turns the scores into the few nearby pages worth reading: two before to three after the citation at a score of 0.5 or more, further away at 0.8 or more, at most five pages.
6. **Uptake reading (L04, L05, L07).** The external reader reads the citation with the pages picked by R03 and proposes which principles the citation takes and which nearby pages continue the argument, quoting the text verbatim. Since 30 September 2026 the principles shown to the team come from L04 (the first reading, without the case dossier), the continuation, the quotations and the supported sentence from L05 (the reading with the dossier), and where L04 and L05 disagree on the principles the continuation is reread by L07 with the L04 principles given as fixed. L06 was an experiment (principle decided on the whole passage) and is not in use.
7. **Composition (R02).** Fixed rules from the codebook put the proposals together (a chain mention takes no principle and has no continuation). The rules write only on rows nobody has judged.
8. **People.** Researchers confirm or correct every citation. One row in five, drawn among the rows queued from 29 September 2026, is shown without any machine proposal, to measure the machine. Human judgments are the reference for every measure of a model; judgments given with the proposals visible are not a blind measure (see Limits).
9. **Training (T01, T02, T03).** The project's own models are trained to take over the reading: the reranker on people's judgments, TRACE-Reader on the external reader's readings (distillation). The rule for adopting TRACE-Reader has changed once and both rules are kept with their dates in the registry and in `MODEL-CARDS.md`: TRACE-Reader v0 passed the test fixed on 27 September (0.596 against the external reader's 0.568 on 317 rows) but was not adopted, because those rows had been judged with the external reader's proposals visible; it now replaces the external reader only when it matches it on the rows judged without proposals, a test that has not yet been run.

Implicit uptake (the reasoning taken over without the name) is searched first as the *continuation* of an explicit citation in the same filing. A search across the whole corpus, with models trained on the team's judgments, comes after this first stage: the blind search of July found about one real implicit uptake per hundred candidate pages.

## Version codes

A **citation code** (`URG-0146`) says which citation; it never changes. A **version code** says how a proposal was made: the exact model and revision, the instructions, the settings, the data and the code. The letter says what kind of thing it is:

| Letter | Kind | Codes |
|---|---|---|
| D | data | D01 the database export |
| S | name search | S01 first version (replaced), S02 corrected (in use) |
| R | rules without a model | R01 paragraph map, R02 composition, R03 choice of the nearby pages to read |
| L | readings by an external model | L01 (replaced), L02 Urgenda, L03 Neubauer and Future Generations, L04 uptake reading (the principles), L05 uptake reading with the dossier (continuation, quotations, supported sentence), L06 experiment (not in use), L07 continuation reread on the proposed principles |
| T | models trained by the project | T01 TRACE-Reranker 0.1, T02 TRACE-Reader v0, T03 TRACE-Reader v1 |

`versioni/registro.json` lists every version with its base model and revision, fingerprints, training data, settings, instructions and code, what changed from the previous version, and whether it is in use. Every proposal on a citation carries the code of the version that made it; every judgment records who decided, when, with which codebook, and what the person was shown. Model cards: `MODEL-CARDS.md`. The registry is the single source: where this README, the model cards or the public page differ from it, the registry is right.

## Contents

- `tools/`: the pipeline (search, reading, paragraph map, reranker scores, composition, codes, registry, TRACE-Reader training and evaluation). The copies here are those of 29 September 2026; the tools added on 30 September (`leggi_l04.py`, the rereading of the rows L04 had never read; `leggi_l06.py`, the L06 experiment; `leggi_seguito.py`, L07) follow with the next update, and their fingerprints are already in the registry.
- `cited-cases/`: for each cited case, the forms of its name and its principles (the case file, `*.yaml`), the dossier given to the reader (`*-fascicolo.md`) and the paragraph map (`*-mappa-paragrafi.yaml`).
- `codebook/citazioni.yaml`: the coding categories and the rules for hard cases. Its window for the continuation (two pages before, three after) is the one of the readings of 27 and 28 September; since 29 September the pages are chosen by R03 up to ten pages away, and the codebook will say so in its next version (the file here is the one whose fingerprint L02 and L03 record).
- `versioni/`: the registry of versions and, for each version, the copies of its instructions and code. The instructions are the exact texts given to the models where they were saved at run time (L05, L06, L07). For L04 the text is reconstructed after the fact (the file of 30 September without the three additions of 28 September; the readings prove that question 3 was absent, since none has the field `frase_sostenuta`), and for L02 and L03 it is regenerated from the current case file and codebook: each of these entries says so in its `instructions` (`reconstructed`). The code copies differ from the executed files only in their comments; the SHA-256 fingerprints in the registry are those of the executed files. For L04 the registered code is the closest surviving copy of what ran on 27 and 28 September (narrow window), plus `leggi_l04.py` for the rereading of 30 September.

Code comments are in English. The instructions given to the language models, the case files and the codebook are in Italian, the working language of the team.

## Limits

- **No agreement figure published so far is a blind measure.** The figures the platform computes (machine and team agree on the type in about 93% of judged rows, a proposed principle is confirmed in about 97%, a proposed continuation page in about 94%) come from judgments given with the machine's proposals visible on the screen: leaving a ticked principle ticked counts as agreement. They say how often people changed a proposal, not how often the machine is right. Rows shown without any proposal are being judged now, and a blind figure will be published only when that sample has a base.
- The rows judged by the principal investigator, used to compare the readings L04, L05 and L06, are not frozen (38 on 28 September, 43 on 30 September) and were judged with the proposals visible. Those comparisons are provisional.
- The models of 0.1 were trained on labels that are being corrected (T01) or on the external reader's readings (T02, T03). One cited judgment.

## Terms

One name for each thing, in every document of this release: **uptake** (the relation between a citation and the cited case) and **continuation** (a nearby page that carries the same uptake on); **version** for L02 or L05 (never «second reading») and **reading 1, reading 2** for the two readings of one row; **test rows** for the fixed evaluation set, **quotation** for the sentence copied from the page, **Tests** for the platform section, **experiment** for L06; **judged without proposals** for the one-in-five sample, **second opinion** for double coding, never «blind» alone; **external reader** for DeepSeek (codes L) and **TRACE-Reader** for T02 and T03, never «Reader» alone; **case file** for `cited-cases/*.yaml` and **dossier** for `*-fascicolo.md`; **principles** (the field `semantic_queries` keeps its technical name); **name search** for the step, **explicit citation** for what it finds; **composition (R02)** for the rule and **loading** for the act of writing; **run** for one execution of a tool.

## Data

The documents come from the Climate Litigation Database of the Sabin Center for Climate Change Law (Columbia Law School) with Climate Policy Radar, whole-database export `CCC-whole_data_dump-2026-07-26`; use authorised by Maria Antonia Tigre (Sabin Center). The texts of the filings are not redistributed here. Data provided by the Sabin Center for Climate Change Law. Platform operated by Climate Policy Radar.

## Licence

Code: MIT (see `LICENSE`). Case files, codebook and registry: CC BY 4.0.

## Citation

Naglieri, G., Buono, E., Garofalo, C., Saracino, C. (2026). CLIMPACT TRACE 0.1: Traceable Reception and Attribution in Climate-law Evidence. CLIMPACT, University of Bari. Zenodo. DOI: [pending].
