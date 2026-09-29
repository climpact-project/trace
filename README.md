# TRACE

**Tracing how climate judgments are taken up in later litigation.** TRACE is developed by the CLIMPACT project (University of Bari).

This repository holds the code, the case files, the codebook and the registry of versions behind TRACE. It is a research release under active development.

## What TRACE does

For any climate judgment (the *cited case*; so far Urgenda, Neubauer and Future Generations), TRACE finds every later filing that cites it and records, for each citation, what the citing text does with it. Every step has a version code (see below).

1. **Documents (D01).** The Climate Litigation Database, whole-database export, with the text of every page.
2. **Name search (S02).** A plain text search, with no AI, looks for the name of the case in every page, in all the forms it takes: names, ECLI numbers, docket numbers, translations, other scripts, common OCR errors. Each hit becomes a citation with a permanent code: `URG-0146`, `NEU-0412`, `FGC-0033`.
3. **Paragraph map (R01).** When the citation points to a paragraph of the judgment (`para. 5.7.7`), a hand-written map gives the principle that paragraph holds. No model is involved.
4. **Citation reading (L02, L03).** A large language model (DeepSeek V4 Flash) reads the citation in context and proposes: is it really the judgment; what the citation does (chain mention, descriptive, substantive, distinguishing, critical); who speaks; the proposition it supports.
5. **Reranker (T01).** The project's own model scores the passage, and the pages around it (up to ten pages on each side), against each principle of the case, and picks the nearby pages worth reading.
6. **Uptake reading (L04, L05).** The language model reads the citation with the case dossier and the pages picked by the reranker, and proposes which principles the citation takes and which nearby pages continue the argument, quoting the text verbatim.
7. **Composition (R02).** Fixed rules from the codebook put the proposals together (a chain mention takes no principle and has no continuation).
8. **People.** Researchers confirm or correct every citation; one row in five is shown without any machine proposal, to measure the machine. Human judgments are the reference for every measure.
9. **Training (T01, T02, T03).** The project's own models are trained to take over the reading; they replace the external model only when they match it on the rows judged blind.

Implicit uptake (the reasoning taken over without the name) is searched as the *continuation* of an explicit citation in the same filing, not blindly across the corpus: a blind search found about one real implicit uptake per hundred candidate pages.

## Version codes

A **citation code** (`URG-0146`) says which citation; it never changes. A **version code** says how a proposal was made: the exact model and revision, the exact instructions, the settings, the data and the code. The letter says what kind of thing it is:

| Letter | Kind | Codes |
|---|---|---|
| D | data | D01 the database export |
| S | name search | S01 first version (replaced), S02 corrected (in use) |
| R | rules without a model | R01 paragraph map, R02 composition |
| L | readings by an external model | L01 (replaced), L02 Urgenda, L03 Neubauer and Future Generations, L04 uptake reading, L05 uptake reading with the case dossier |
| T | models trained by the project | T01 TRACE-Reranker 0.1, T02 TRACE-Reader v0, T03 TRACE-Reader v1 |

`versioni/registro.json` lists every version with its base model and revision, fingerprints, training data, settings, instructions and code, what changed from the previous version, and whether it is in use. Every proposal on a citation carries the code of the version that made it; every judgment records who decided, when, with which codebook, and what the person was shown. Model cards: `MODEL-CARDS.md`.

## Contents

- `tools/`: the pipeline (search, reading, paragraph map, reranker scores, composition, codes, registry, Reader training and evaluation).
- `cited-cases/`: for each cited case, the forms of its name and its principles (`*.yaml`), the case dossier (`*-fascicolo.md`) and the paragraph map (`*-mappa-paragrafi.yaml`).
- `codebook/citazioni.yaml`: the coding categories and the rules for hard cases.
- `versioni/`: the registry of versions and, for each version, the copies of its instructions and code. The instructions are the exact texts given to the models. The code copies differ from the executed files only in their comments; the SHA-256 fingerprints in the registry are those of the executed files.

Code comments are in English. The instructions given to the language models, the case files and the codebook are in Italian, the working language of the team, and are published exactly as they were run.

## Data

The documents come from the Climate Litigation Database of the Sabin Center for Climate Change Law (Columbia Law School) with Climate Policy Radar, whole-database export `CCC-whole_data_dump-2026-07-26`; use authorised by Maria Antonia Tigre (Sabin Center). The texts of the filings are not redistributed here. Data provided by the Sabin Center for Climate Change Law. Platform operated by Climate Policy Radar.

## Licence

Code: MIT (see `LICENSE`). Case files, codebook and registry: CC BY 4.0.

## Citation

Naglieri, G., Buono, E., Garofalo, C., Saracino, C. (2026). TRACE 0.1: tracing how climate judgments are taken up in later litigation. CLIMPACT, University of Bari. Zenodo. DOI: [pending].
