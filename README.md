<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/trace-lockup-dark.png">
    <img alt="TRACE 0.1 Beta" src="assets/trace-lockup.png" width="460">
  </picture>
</p>

<h3 align="center">Traceable Reception and Attribution in Climate-law Evidence</h3>

<p align="center">Following climate judgments into the litigation that comes after them.</p>

<p align="center">
  <a href="LICENSE"><img alt="Licence: MIT" src="https://img.shields.io/badge/licence-MIT-2e84ff"></a>
  <img alt="Python 3.11 or later" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-1c2636">
  <a href="#how-to-verify"><img alt="Tests: pytest" src="https://img.shields.io/badge/tests-pytest-0a9edc"></a>
  <a href="https://github.com/astral-sh/ruff"><img alt="Code style: ruff" src="https://img.shields.io/badge/code%20style-ruff-261230"></a>
</p>

<p align="center"><sub>DOI reserved: 10.5281/zenodo.23082522 (active on publication)</sub></p>

> **Beta.** TRACE 0.1 is a first release. Every proposal it makes is checked by the CLIMPACT research team, and the
> figures it publishes are provisional until the rows judged without machine proposals have a base (see [Limits](#limits)).
> The proposals come from **DeepSeek V4 Flash** (DeepSeek-V4-Flash-0731, MIT licence), a large language model with open
> weights that we run with vLLM on four NVIDIA H100 GPUs at ReCaS-Bari (INFN and University of Bari): it reads each
> citation five times and the majority decides (R11, Proposals by majority vote of five readings). The codes L are its
> readings.

For a climate judgment (the *cited case*), TRACE finds every later filing that cites it, in the Climate Litigation
Database, and records for each citation what the citing text does with it: which principles of the judgment it takes
up, and on which nearby pages the argument continues. TRACE works for any judgment that has a case file; TRACE 0.1,
the first release, follows six: Urgenda, Neubauer, Future Generations, KlimaSeniorinnen, the ICJ climate advisory
opinion and the Inter-American Court advisory opinion OC-32/25. It is built to grow beyond judgments, to laws, policies
and the other sources through which climate-law reasoning travels (see [What comes next](#what-comes-next)).

Every step leaves a **version code** (`L05`, `R11`, `T01`...) on what it proposes. The codes, with the exact models,
instructions, settings, data and code of each version, are in [`versioni/registro.json`](versioni/registro.json): the
registry is the single source, and where this page differs from it the registry is right.

<p align="center"><img alt="TRACE 0.1: Traceable Reception and Attribution in Climate-law Evidence. A general method to trace how climate judgments are received in later litigation; TRACE 0.1 applies it to six landmark judgments." src="assets/banner.png" width="100%"></p>

## Index

The pipeline step by step: what each step does, the class of the maintained package that does it, the scripts that did
it for the TRACE 0.1 data, and the versions in the registry.

| Step | `tracepipe` | `legacy/tools` | Versions |
|---|---|---|---|
| **1. Corpus**<br>Turns each filing into page-marked text, OCRs unreadable pages, builds the page index. | `corpus`: IndicePagine, Documento, Pagina, PosizioniDopoOcr | [`001`](legacy/tools/001_build_markdown.py) to [`010`](legacy/tools/010_indice_pagine.py) | **D01** Documents: Climate Litigation Database, public API snapshot<br>**D02** Documents: D01 with OCR text of unreadable pages<br>**D03** Documents: D02 with Markdown for 277 filings of the 19/09/2026 update |
| **2. Cited case**<br>The forms of the name of each judgment, its principles (the *probes*), the map from its paragraphs to its principles. | `caso`: CasoCitato, SerieSonde, MappaParagrafi<br>`config`: Config | [`011`](legacy/tools/011_sonde.py) to [`015`](legacy/tools/015_formulazioni_provenienza.py) | **P01** Probes of Urgenda<br>**P05** Probes of Neubauer and Future Generations, second set corrected (second round)<br>**P06** Probes of KlimaSeniorinnen<br>**P08** Probes of IACtHR advisory opinion OC-32/25<br>**P09** Probes of the ICJ climate advisory opinion, 1.5°C probe rewritten<br>**R04** Paragraph map, reviewed<br>**R07** Paragraph map with probes P05<br>**R09** Paragraph maps of the three new cases; Spanish and Portuguese paragraph references |
| **3. Name search**<br>Finds the name of the case in every page, in all its forms, with no AI. Each hit becomes a citation with a permanent code (`URG-0146`). | `ricerca`: RicercaPerNome, UnioneRighe<br>`dimensioni`: PosizioneNelPdf | [`016`](legacy/tools/016_cerca.py) to [`022`](legacy/tools/022_coda_uptakes.py); S05 in [`versioni/S05`](versioni/S05) | **S01** Name search, first version<br>**S02** Name search, corrected<br>**S03** Name search on OCR text, more Japanese and Korean forms<br>**S05** Name search on normalised text, with readmitted and new forms (in use) |
| **4. Citations counted once**<br>The same citation can reach the database twice: in the body text and again in the footnote that the same sentence calls, in two translations of one filing, or as a surrounding page that holds a citation of its own. Rules mark one of the two; nothing is deleted. | `unione_c03`: UnioneC03, GeneratoreCoppie, CoppieRivedute<br>`pagine_gia_citate`: ApplicaC07, RiconoscitorePagine<br>`copia_prima`: CopiaPrima | (came after the legacy scripts) | **C03** Body text and footnote, and translations of the same filing, counted once (applied 5 October 2026)<br>**C07** Surrounding page that is already a citation of its own: also cited separately (applied 5 October 2026) |
| **5. Close pairs** (on trial)<br>Two references to the same case in the same filing, less than 5,000 characters apart, are read together: one citation or two? Not applied: nothing is written to the platform. | `coppia`: Coppia<br>`coppie_vicine`: CoppieVicine, Taratura<br>`lettura_coppia`: DomandaL13, LettoreCoppie<br>`decisione_coppie`: Decisore<br>`carica_s08`: CaricaS08<br>`prova_intera`: FreniProvaIntera | (came after the legacy scripts) | **S08** Close pairs: two references to the same case in the same filing, read together (on trial, not applied)<br>**L13** Reading of a close pair: one citation or two (on trial, not applied) |
| **6. Type of citation**<br>DeepSeek V4 Flash, a large language model, says what each citation does: chain mention, descriptive, substantive, distinguishing, critical. | `lettori`: LettoreTipo<br>`istruzioni`<br>`deepseek`: ClienteDeepSeek<br>`letture`: Lettura | [`023`](legacy/tools/023_giudica_llm.py) to [`025`](legacy/tools/025_carica_lessicali.py) | **L02** Citation reading, Urgenda<br>**L03** Citation reading, every case except Urgenda |
| **7. Surrounding pages**<br>TRACE-Reranker scores the pages up to ten before and after the citation; a fixed rule picks the ones to read. T04, a reasoning reranker trained by the project, is published as a new model (see below); T01 stays the one in use. | `pagine_attorno`: Punteggi, SceltaPagineAttorno | [`026`](legacy/tools/026_prepara_training.py) to [`029`](legacy/tools/029_coppie_ocr.py), [`031`](legacy/tools/031_leggi_ripresa.py); R10 in [`versioni/R10`](versioni/R10) | **T01** TRACE-Reranker 0.1<br>**R08** Choice of the nearby pages, over the full window for every case<br>**R10** Choice of the surrounding pages: 0.5 at every distance within 10 pages, no cap |
| **8. Uptake reading**<br>DeepSeek V4 Flash proposes the principles taken up, the pages that continue the argument and the quotations; brakes in the code reject quotations not on the page. | `lettori`: LettorePrincipi, LettorePagineAttorno<br>`freni`: Freni | [`030`](legacy/tools/030_prepara_l05.py) to [`034`](legacy/tools/034_freni.py) | **L04** Uptake reading, first version: the principles<br>**L05** Uptake reading with the case dossier: surrounding pages, quotes, supported sentence<br>**L07** Surrounding pages reread on the proposed principles |
| **9. Composition**<br>Fixed rules turn the readings into proposals, only on rows nobody has judged. From 2 October: five readings per row, majority vote. | `composizione`: Composizione, ComposizioneMaggioranza<br>`maggioranza`<br>`caricatori`: CaricatoreTipo, CaricatoreRipresa<br>`banca`: BancaDati | [`025`](legacy/tools/025_carica_lessicali.py), [`035`](legacy/tools/035_carica_ripresa.py); R11 in [`versioni/R11`](versioni/R11) | **R05** Rules that put the proposals together, with the brake for Asian scripts<br>**R11** Proposals by majority vote of five readings (decided 2 October 2026, being applied) |
| **10. Checks**<br>After every load: every row complete, every page of the window scored. | `controlli`: ControlloCompletezza, ControlloFinestra | [`036`](legacy/tools/036_controllo_completezza.py) to [`039`](legacy/tools/039_freni_prova.py) |  |
| **11. People**<br>Researchers confirm or correct every citation; one row in five is shown without machine proposals. | (the platform) | [`040`](legacy/tools/040_salva_giudizi.py) | Codebook 0.5-pilot ([`codebook/`](codebook)) |
| **12. Uptake without the name**<br>Experiment, paused: filings that take up the reasoning without naming the judgment. | (legacy only) | [`041`](legacy/tools/041_distilla.py) to [`043`](legacy/tools/043_unisci_candidati.py) | **S04** Semantic search without the name, redone with the supported sentences<br>**L06** Uptake reading, test: principle decided on the whole passage<br>**L09** Uptake reading without the name: takes up the reasoning, from another source, or same topic only |
| **13. Measures**<br>Probe tests, stability of DeepSeek V4 Flash. | (legacy only) | [`044`](legacy/tools/044_prova_sonde_reranker.py) to [`047`](legacy/tools/047_stabilita_deepseek.py) |  |
| **14. Models**<br>Training of the project's own models. | (legacy only) | [`065`](legacy/tools/065_addestra_categoria.py) to [`069`](legacy/tools/069_addestra_riordino.py); history to [`118`](legacy/tools/118_sezioni_llm.py) | **T01** TRACE-Reranker 0.1<br>**T02** TRACE-Reader v0<br>**T03** TRACE-Reader v1<br>**T04** TRACE-Reranker, reasoning (new model; training script [`tools/addestra_reranker_ragiona.py`](versioni/T04/addestra_reranker_ragiona.py)) |
| **15. Registry and journal**<br>The registry of versions, the results, the journal of every run. | `giornale`: Giornale | [`048`](legacy/tools/048_registro_versioni.py) to [`055`](legacy/tools/055_pubblica_repo.py) | all: [`versioni/registro.json`](versioni/registro.json) |
| **16. Cycles**<br>The automatic chains: steps in order, resume after a crash, checked copies to and from the GPU cluster. | `orchestratore`: Orchestratore, CicloVuote<br>`cli` | [`056`](legacy/tools/056_ciclo_casi_nuovi.sh) to [`064`](legacy/tools/064_carica_blocco.py) |  |

Model cards for T01, T02, T03, T04, the untrained reasoning reranker and L13: [`MODEL-CARDS.md`](MODEL-CARDS.md). The reading order of all 118 legacy scripts:
[`legacy/tools/LEGGIMI.md`](legacy/tools/LEGGIMI.md).

## Applied and on trial (5 October 2026)

Two rules that count a citation once were **applied** to the platform on 5 October 2026. Everything else in this
section is on trial: no row of the platform has been changed by it.

**Applied**

- **C03, body text and footnote, and translations of the same filing, counted once.** The same citation reached the
  database twice: in the body text and again in the footnote that the same sentence calls, or in two translations of one
  filing. The 850 candidate pairs were reread one by one on 4 October 2026, each with the exact sentence that supports
  the decision: 693 to merge (550 body text and footnote, 143 translations), 156 to keep as two citations, 1 uncertain.
  On 5 October at 07:01 the merge was written for **691 rows**: 550 body-text and footnote pairs and 141 translations.
  Only the pairs reread one by one were written: the rule that proposes the pairs took the wrong original language in 46
  of the 105 translations it tried (it reads the first language in the header of the filing), so it generates candidates
  and decides nothing. Two footnotes that carry the same sentence stay two citations. Nothing is deleted: an excluded row
  keeps all its fields and can be restored.
- **C07, a surrounding page that is already a citation of its own.** A page that DeepSeek V4 Flash reads as «the
  argument continues» may hold another citation of the same judgment, with a row of its own. If the two rows share no
  principle, the page is not a continuation: it is marked «also cited separately as `<code>`» and no longer counts as
  one in the figures. On 5 October at 07:49 the mark was written on **8,113 pages of 2,778 rows**. The reading of
  DeepSeek V4 Flash («continues») is not erased: the mark sits next to it, because a page can continue the argument and
  also hold another citation. On 71 pages that the research team had ticked as continuations on 40 judged rows, the
  pages were reread one by one (229 pages in all, 71 of the ticked ones are a citation of their own): the tick was removed
  and a trace kept to put it back; the team's verdict and principles were not touched. **No principle was removed.**

Both steps write a full copy of the rows before the first write, and stop without writing if the copy cannot be read back
(`tracepipe.copia_prima`).

**On trial, not applied**

- **S08, close pairs.** The citations of one case in one filing that are less than 5,000 characters apart become a
  candidate pair (the threshold is a cost decision, not a natural limit: the distances of the pairs to merge and of
  the pairs to keep overlap, and the pairs reread for C03 only reach back one page). Each pair would be read by
  DeepSeek V4 Flash (five readings) and by a second reader (three readings): one citation, two, or doubt; doubt goes
  to the team. It would also recover 376 citations that the same-page deduplication of the name search lost (two true
  citations on one page: Children of Austria, p. 29; BMW, p. 10): 353 remain once 23 copies of the same document are
  removed. They are not written to the platform.
- **L13, the reading of a close pair** (the question «one citation or two?»), with the two readers above.
- **A reasoning reranker, trained (T04).** Qwen3.5-9B with a LoRA adapter trained by the project on its own reasoning, kept
  where it matched the team's verdict (94 examples). On the 137 rows of the jury set, with adapters that had not seen the
  filing, it reaches an F1 of 0.756 on the principles against 0.730 for the untrained 9B (difference +0.03, 95%
  interval -0.033 to +0.079: **not proven**), and 0.50 for T01 and 0.70 for the five readings of DeepSeek V4 Flash. It is
  published as a new model, **not used to produce the data of TRACE 0.1**; rereading the corpus with it is the plan for
  TRACE 0.2. Three rules of its draft instructions were derived from the same judged rows (G05, G06 and one on advisory
  opinions), so the figure is optimistic. T01 stays the reranker in use. The untrained 9B it comes from was tried first
  (F1 0.72 on the same rows). Details and cautions in [`MODEL-CARDS.md`](MODEL-CARDS.md).

## Install

```
git clone https://github.com/climpact-project/trace.git
cd trace
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Python 3.11 or later. The runtime dependencies are PyYAML and RapidFuzz; `.[pdf]` adds PyMuPDF (the body-or-footnote
column of the name search reads the PDF); `.[deepseek]` adds the OpenAI client for the readers and `.[firestore]` the
platform database client.

## Quick start

The `trace` command runs one step at a time. **Nothing is written to the platform without `--scrivi`**: without it every
command is a dry run that prints what it would do (the readers write their own reading files and never touch the
platform).

```
trace --help
export TRACE_RADICE=/path/to/corpus          # the folder with markdown/, index/, cited-cases/, codebook/
trace cerca --caso urgenda --solo-lessicale  # name search: the candidate citations, as a CSV
trace unisci --caso urgenda                  # dry run: the citations it would merge or add
trace prepara pagine-attorno --caso urgenda --regola R10 --etichetta prova
trace leggi pagine-attorno --caso urgenda --letture 5 --etichetta prova   # needs a DeepSeek server
trace carica ripresa --caso urgenda --composizione R11 --etichetta prova  # dry run of the composition
trace controlla completezza
```

Comments and docstrings are in English. The names of modules, classes, functions and command options are Italian, the
team's working language, and so were the screen messages until 6 October 2026, when they were put into English (the
`--help` of every command too); see [A note on language](#a-note-on-language) for the glossary.

## A note on language

The instructions, case files, codebook and prompts that produced the TRACE 0.1 data are in Italian, the working language of the team. They are published exactly as they ran: each is fingerprinted (SHA-256) in `versioni/registro.json`, and translating them would change the text the models read and break the match with the registry. Where useful, an English rendering sits next to them in [`translations/`](translations/); it is a reading aid, not a runnable copy. Package names, command options and registry fields are Italian identifiers; the glossary below gives their English meaning. Labels in the published data are in English.

What is in English, and what is not:

| In English | Italian, kept as it ran |
|---|---|
| This page, the model cards, the citation file, `docs/`, `scripts/`; comments and docstrings of `tracepipe/`; screen messages and `--help` of `trace`; the Zenodo data (every column), the corpus index READMEs; the English registry fields `*_en` | Names of modules, functions, classes and command options (renaming them would break every import and every documented command); the prompts the readers sent (`tracepipe/istruzioni.py`, `tracepipe/lettura_coppia.py`); the codebook (`codebook/`); the case files (`cited-cases/`); `versioni/` and `legacy/tools/`, frozen as they ran; values written to the platform database (`una`, `due`, `incerta`, `testo`, `nota`...), which are protocol codes |

English renderings of the prompts and the codebook are in `translations/` (each file says at the top which original it translates and the SHA-256 of that original). The quotations from the filings (`canonical`, `testo`, `verbatim` in the case files, `sentence` and `passage` in the data) are in the language of the filing and are never translated. The case files and the paragraph maps are in Italian, as the readers used them, with the quotations from the filings in their original language; English translations sit next to them in `cited-cases/` (`*.en.md`, `*.en.yaml`), each stating the SHA-256 of the Italian file it translates.

**Glossary of the Italian terms that remain in identifiers, options and frozen files**

| Italian | English | Italian | English |
|---|---|---|---|
| `caso` | case (the cited judgment) | `atto` | filing (any document of the corpus) |
| `riga` | row (one citation in the database) | `ripresa` | uptake (what a citation takes from the case) |
| `pagine attorno` | surrounding pages (10 before, 10 after) | `banca dati` | database (the platform's) |
| `fascicolo` | case file, or dossier of a case | `mappa dei paragrafi` | paragraph map |
| `sonda` | probe (a principle of the case, with its text) | `principio` | principle |
| `freni` | brakes (checks that stop an unsupported answer) | `lettore` | reader (a model that reads a citation) |
| `lettura` | reading | `registro` | registry (`versioni/registro.json`) |
| `versioni` | versions | `codebook` | codebook (coding categories and rules) |
| `cerca` | search | `unisci` | merge |
| `prepara` | prepare | `leggi` | read |
| `carica` | load (to the platform) | `controlla` | check |
| `coppie` | pairs | `taratura` | calibration |
| `scrivi` / `--scrivi` | write / the flag that writes to the platform | `fotografia` | snapshot (of the database) |
| `solo-lessicale` | lexical network only (name search) | `etichetta` | label (of a run) |
| `giornale` | journal (log of every run) | `composizione` | composition (rules that turn readings into proposals) |
| `tipo_atto` | type of document (filing type) | `tipo_citazione` | type of citation |
| `chi_parla` | who speaks | `corte` / `parte` | court / party |
| `una` / `due` / `incerta` | one / two / uncertain (answer of L13) | `si` / `no` / `incerto` | yes / no / uncertain |
| `corpo` / `nota` | body text / footnote | `menzione_in_catena` | chain mention |
| `descrittiva` | descriptive | `sostanziale` | substantive |
| `distinguente` | distinguishing | `critica` | critical |
| `implicita` | implicit | `prosegue` | continues (the argument continues on the page) |
| `compito`, `stato`, `note`, `nota`, `cambia`, `limiti`, `regole`, `esito` | task, status, notes, note, what changes, limits, rules, outcome (registry fields; English counterparts end in `_en`) | `BOZZA, non approvata` | DRAFT, not approved by the principal investigator |

## What you need to run it

- **The corpus texts.** The filings are not redistributed here (terms of the Sabin Center for Climate Change Law). They
  are public on the Climate Litigation Database; [`legacy/tools/001_build_markdown.py`](legacy/tools/001_build_markdown.py)
  turns the downloaded PDFs into the page-marked text the pipeline reads, and the public corpus index (see
  [Data](#data)) lists every document with its source URL and the SHA-256 of the PDF used, with a script that rebuilds
  and verifies the page text.
- **DeepSeek V4 Flash**, the large language model that reads the citations (codes L). We serve it with vLLM on four
  NVIDIA H100 GPUs at ReCaS-Bari; the weights come from the official DeepSeek release (DeepSeek-V4-Flash-0731, MIT
  licence). The readers call it through an OpenAI-compatible endpoint (`--base-url`, key in `chat/chiave`).
- **TRACE-Reranker (T01).** A LoRA adapter on Qwen3-Reranker-4B; the adapter is to be published on Zenodo with the
  release.
- **TRACE-Reranker, reasoning (T04).** A LoRA adapter on Qwen3.5-9B (revision c2022362, Apache-2.0), in `peft` format,
  published on Zenodo with the release with its prompt, its measurement and a check that it fits the base model.
- **The platform database**, only to load proposals (`--scrivi`): any implementation of `tracepipe.banca.BancaDati`.
  The tests use the in-memory one.

## What is not in this repository

| What | Why | Where to get it |
|---|---|---|
| Texts of the filings | Sabin Center terms; party filings can carry their authors' rights | The Climate Litigation Database; the corpus index, tiers 1 to 3 below |
| Model weights (T01, T02, T03, T04) | Size | Zenodo, to be published with the release |
| DeepSeek V4 Flash weights | Third-party model | The official DeepSeek release (MIT) |
| Readings, scores, human judgments | Platform data with filing text in them | Released as data on Zenodo, to be published with the release |
| The reference harness sample (`prove/campione`) | Filing texts and platform data | Not redistributed; described under [How to verify](#how-to-verify) |
| Keys and credentials | | Never in the repository |

## Data

The corpus index of TRACE 0.1 (corpus version D03: 577,121 pages of 16,993 documents, 6,482 citations found by the
name search) is released in three tiers, to be published with the release:

| Tier | Access | Documents | Pages | What it holds |
|---|---|---:|---:|---|
| 1. Public index, no text | public, CC BY-NC 4.0 | 16,993 | 577,121 | every page and document without its text: identifiers, character offsets, the SHA-256 of the page text, OCR and readability flags, the position of every citation, and a script that rebuilds the page text from the original PDFs and verifies it page by page |
| 2. Public-authority documents | public | 4,259 | 103,832 | the page text of documents issued by courts and other public authorities, which are free of copyright; Westlaw and LexisNexis prints, unofficial translations, United Kingdom documents and attached exhibits are left out |
| 3. Full index | restricted, on request | 16,993 | 577,121 | the page index with the text of every page, party filings and OCR text included, to verify TRACE results |

Of the 559,499 pages whose text comes from the PDF's own text layer, 559,072 rebuild byte for byte from tier 1.

**Team judgments.** The data record also carries `trace-0.1-team-judgments.csv` (and a `.jsonl` with real lists): one row
per citation judged by the CLIMPACT team, discarded citations included with the reason for the discard. For the function
of the citation, who speaks, where it sits, the principles and the surrounding pages it gives two columns each, the
machine proposal (`machine_*`) and the team's decision (`team_*`), and it adds the outcome (confirmed, discarded or
reclassified), `blind` (whether the judgment was given without the proposal on the screen), the codebook version, the
date and a pseudonymous `coder` (coder A, coder B...). For double-coded citations it adds the second coder's outcome,
function and principles and whether the outcomes agree. Not published: coders' names, accounts and emails (coders
appear only as pseudonyms), the time spent on each row and the free-text notes.

**DOIs.** Reserved on Zenodo; they become active when the records are published, by the release of 12 October 2026.

| Record | DOI |
|---|---|
| TRACE 0.1, code (the DOI to cite) | 10.5281/zenodo.23082522 |
| TRACE 0.1, data | 10.5281/zenodo.23082590 |
| Corpus index, tiers 1 and 2 (public) | 10.5281/zenodo.23116958 |
| Corpus index, tier 3 (restricted, on request) | 10.5281/zenodo.23116960 |

**How to request tier 3.** Write to the project (CLIMPACT, University of Bari, trace@climpact.it) saying who you are,
your institution and which TRACE results you want to verify. If the request fits, the research team grants access to a
restricted Zenodo record (DOI 10.5281/zenodo.23116960); the file is never sent by email. Conditions: research use
only; no redistribution of the file or of any substantial part of it, and no publication of the text of party
filings; keep it securely and delete it when the verification is over; cite the source, «Climate Litigation Database, Sabin Center for Climate Change Law and
Climate Policy Radar», and CLIMPACT TRACE 0.1.

The documents come from the Climate Litigation Database of the Sabin Center for Climate Change Law (Columbia Law
School) with Climate Policy Radar, read through its public API (snapshot of 26 July 2026, update of 19 September 2026).
Data provided by the Sabin Center for Climate Change Law. Platform operated by Climate Policy Radar.

## How to verify

- **Tests.** `pytest` from a fresh clone runs the tests that need no private data; the ones that need the harness
  sample or the live scripts are skipped, each with its reason. On the team's machine, with the private data, the
  whole suite of this repository runs (558 tests).
- **Reference harness.** Every class of `tracepipe` reproduces a legacy script. A harness, kept with the private data,
  runs the legacy scripts and the package on a fixed sample (180 rows from the six cases, filing texts included, with
  the database, DeepSeek V4 Flash and the clock replaced by recorded fakes) and compares every output file: 298 of
  298 files and 67 of 67 journals equal, in compatibility mode. The sample is not redistributed because it contains
  filing texts.
- **External review.** The code of `tracepipe` went through an independent external code review, in three rounds, on
  3 October 2026. Round 1 led to five fixes: the uncertainty of a row is computed only on the decisions actually
  adopted; the confidence of the type is no longer overwritten; a surrounding page is ticked only with evidence for the
  winning principle; answers cut short but not empty are retried; and the evidence check works without spaces for
  Thai, Lao, Khmer and Myanmar. Round 2 led to strict yes/no answers, malformed row identifiers skipped and counted,
  principles from the paragraph map and from the readings kept apart, errors of the journal reported, five readings by
  default, and a case left with no rows or a row whose file is missing handled without failing. Round 3 asked for no
  further change to the package beyond two small ones: the help of `trace` now says which options reproduce which
  version, and the screen count of split citations counts only the groups with something to merge. After the fixes the
  full suite of the team's working copy, live scripts included, passes (509 passed, 1 skipped) and the harness gives the
  same result as before (298 of 298 files, 67 of 67 journals). The review concluded that the package is sound and should be kept, not rewritten.
  The response to round 2 and a summary of round 3 are in [`docs/external-review/`](docs/external-review/).
- **Registry fingerprints.** Every version lists the SHA-256 of the instructions and code it ran with, and keeps a frozen
  copy in `versioni/`:

  ```
  python scripts/verify_registry.py
  ```

## What TRACE shows

<p align="center"><img alt="How TRACE follows a judgment: find every citation by name, map the judgment, score the surrounding pages, read five times and keep the majority, people verify" src="assets/gallery/how-it-works.png" width="100%"></p>

<p align="center"><img alt="The six judgments of TRACE 0.1, with the citations found by name and the documents they are in" src="assets/gallery/six-judgments.png" width="100%"></p>

<p align="center"><img alt="Every proposal carries the code of the version that made it, and the registry records what each code ran with" src="assets/gallery/version-codes.png" width="100%"></p>

## Repository

```
tracepipe/      the pipeline package (maintained)
tests/          its tests
legacy/tools/   the 118 scripts that produced the TRACE 0.1 data
versioni/       the registry, and a frozen copy of each version's code
cited-cases/    case files, probe series, dossiers, paragraph maps (in Italian, as used; English translations next to them, *.en.md / *.en.yaml)
codebook/       coding categories and rules for hard cases
translations/   English renderings of the Italian prompts and codebook (reading aids, next to the frozen originals)
scripts/        verify_registry.py
assets/         images of this page
```

## Limits

- **No agreement figure published so far is a blind measure.** The figures the platform computes come from judgments
  given with the machine's proposals visible: they say how often people changed a proposal, not how often the machine
  is right. Rows judged without any proposal are being judged now; a blind figure will be published when that sample
  has a base.
- The models of 0.1 were trained on labels that are being corrected (T01) or on the readings of DeepSeek V4 Flash
  (T02, T03: distillation from DeepSeek V4 Flash), and on one cited judgment, Urgenda. T04 was trained on 94 answers of the
  untrained Qwen3.5-9B that matched the team's verdict, from four cited judgments (74 of them Urgenda).
- The human reference rows used to compare readings are not frozen; those comparisons are provisional.
- C03 and C07 were applied on pairs and pages reread one by one; the registry keeps the rule, the numbers and the code,
  and every excluded row can be restored. S08 and L13 are on trial, and T04 is new: the
  figures given for them are measured on rows the team already judged, and T04's figure is optimistic and not proven
  (see its model card).

## What comes next

Next: TRACE 0.2. The whole corpus read again with our own reasoning reranker, trained on our team's judgments and released open with TRACE 0.1.

- **More judgments.** Any judgment can be followed once its case file is written: the forms of its name, its
  principles, a map of its paragraphs. New judgments are added release by release, including those other
  researchers ask for.
- **Beyond judgments: laws, policies and other sources.** The same method will follow how judgments and their
  principles reach legislation and policy, starting with Climate Change Laws of the World (Grantham Research
  Institute with Climate Policy Radar), and then the other sources where climate-law reasoning travels.
- **Uptake without the name.** A second stage will find where a judgment's reasoning is taken up without the
  judgment being named, retrained on the research team's judgments.
- **A reader of our own.** A model trained on the team's judgments and frozen, so that anyone can rerun TRACE and
  get the same answer.
- **Measured blind.** Agreement figures computed on citations the team judged without seeing any proposal.
- **TRACE for other researchers.** CLIMPACT's own computing power to run TRACE on research requests: other
  judgments, other corpora, own collections of documents. Requests are open on the
  [TRACE page](https://www.climpact.it/site/data/trace).

## How to cite

> Naglieri, G., Buono, E., Garofalo, C., Saracino, C., Dell'Atti, L., Rojas Verdugo, G. A. (2026). *CLIMPACT TRACE 0.1: Traceable Reception
> and Attribution in Climate-law Evidence.* CLIMPACT, University of Bari. Zenodo. DOI reserved: 10.5281/zenodo.23082522
> (active on publication).

The data and the corpus index have DOIs of their own: data 10.5281/zenodo.23082590; corpus index
10.5281/zenodo.23116958 (tiers 1 and 2, public) and 10.5281/zenodo.23116960 (tier 3, restricted). All four are
reserved and active on publication.

Machine-readable citation: [`CITATION.cff`](CITATION.cff).

## Licence

Code: MIT ([`LICENSE`](LICENSE)). Case files, codebook and registry: CC BY 4.0.

## Credits

TRACE is developed by **CLIMPACT** at the University of Bari Aldo Moro. The models were trained and the readings
computed on the **ReCaS-Bari** data centre of INFN and the University of Bari.

<table>
  <tr>
    <td align="center"><sub>Developed at</sub></td>
    <td align="center"><sub>Computed on</sub></td>
  </tr>
  <tr>
    <td align="center">
      <picture>
        <source media="(prefers-color-scheme: dark)" srcset="assets/logos/climpact-wordmark-white.svg">
        <img alt="Climpact" src="assets/logos/climpact-wordmark-cielo.svg" height="40">
      </picture>
      &nbsp;&nbsp;&nbsp;
      <picture>
        <source media="(prefers-color-scheme: dark)" srcset="assets/logos/uniba-white.png">
        <img alt="University of Bari Aldo Moro" src="assets/logos/uniba-blu.png" height="52">
      </picture>
    </td>
    <td align="center">
      <picture>
        <source media="(prefers-color-scheme: dark)" srcset="assets/logos/recas-bari-white.png">
        <img alt="ReCaS-Bari" src="assets/logos/recas-bari-colour.png" height="44">
      </picture>
      &nbsp;&nbsp;&nbsp;
      <picture>
        <source media="(prefers-color-scheme: dark)" srcset="assets/logos/infn-white.png">
        <img alt="INFN" src="assets/logos/infn-colour.png" height="56">
      </picture>
    </td>
  </tr>
</table>
