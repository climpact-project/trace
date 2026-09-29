# TRACE

**Tracing how climate judgments are taken up in later litigation.** TRACE is developed by the CLIMPACT project (University of Bari).

This repository holds the code, the case files, the codebook and the registry of versions behind TRACE. It is a research release under active development.

## What TRACE does

For any climate judgment (the *cited case*; so far Urgenda, Neubauer and Future Generations), TRACE finds every later filing that cites it and records, for each citation, what the citing text does with it.

1. **Find.** A plain text search (no AI) looks for the name of the case in every page of the Climate Litigation Database, in all the forms it takes: names, ECLI numbers, docket numbers, translations, common OCR errors. Each hit becomes a citation with a permanent code: `URG-0146`, `NEU-0412`, `FGC-0033`.
2. **Paragraph map.** When the citation points to a paragraph of the judgment (`para. 5.7.7`), a hand-written map gives the principle that paragraph holds. No model is involved.
3. **Reranker.** The TRACE-Reranker scores the passage, and the pages around it, against each principle of the case, and picks the nearby pages worth reading.
4. **Reader.** A large language model reads the citation in context (the page before and after, the case dossier, the codebook) and proposes: is it really the judgment; what the citation does (chain mention, descriptive, substantive, distinguishing, critical); who speaks; the proposition; which principles it takes; whether the argument continues on nearby pages without the name.
5. **Composition.** Fixed rules from the codebook put the proposals together (a chain mention takes no principle, and has no continuation).
6. **People.** Researchers confirm or correct every citation. Their judgments are the ground truth; model outputs are never used as labels.
7. **Training.** The corrections train the project's own models, which replace the external ones when they match them on a test decided in advance.

Implicit uptake (the reasoning taken over without the name) is searched as the *continuation* of an explicit citation in the same filing, not blindly across the corpus: a blind search found about one real implicit uptake per hundred candidate pages.

## Models

| Code | Model | Role | Status |
|---|---|---|---|
| V06 | TRACE-Reranker 0.1: Qwen3-Reranker-4B + LoRA | principle scores, nearby pages | in use; to be retrained on confirmed principles |
| V08, V09 | TRACE-Reader v0, v1: Qwen3-14B + LoRA | reads citations on one GPU | experimental; matches the external reader on citation type |
| V02-V05 | DeepSeek V4 Flash (external, MIT) | reads citations | in use as reader and as teacher |

## Codes and provenance

- A **citation code** (`URG-0146`) says which citation. It never changes.
- A **version code** (`V02`, `D01`) says how a proposal was made. `versioni/registro.json` lists every version with base model and revision, SHA-256 fingerprints of the weights, training data and date, settings, instructions and code (copies in `versioni/<code>/`), codebook, software, hardware and measures.
- Every proposal on a citation carries the code of the version that made it; every judgment records who decided, when, with which codebook, and what the person was shown.

## Contents

- `tools/`: the pipeline (search, reading, paragraph map, reranker scores, composition, codes, registry, Reader training and evaluation).
- `cited-cases/`: for each cited case, the forms of its name and its principles (`*.yaml`), the case dossier (`*-fascicolo.md`) and the paragraph map (`*-mappa-paragrafi.yaml`).
- `codebook/citazioni.yaml`: the coding categories and the rules for hard cases.
- `versioni/`: the registry of versions and the copies of instructions and code for each version. The instructions are the exact texts given to the models. The code copies differ from the executed files only in their comments; the SHA-256 fingerprints in the registry are those of the executed files.

Code comments are in English. The instructions given to the language models, the case files and the codebook are in Italian, the working language of the team, and are published exactly as they were run.

## Data

The documents come from the Climate Litigation Database of the Sabin Center for Climate Change Law (Columbia Law School) with Climate Policy Radar, whole-database export `CCC-whole_data_dump-2026-07-26`; use authorised by Maria Antonia Tigre (Sabin Center). The texts of the filings are not redistributed here. Data provided by the Sabin Center for Climate Change Law. Platform operated by Climate Policy Radar.

## Licence

Code: MIT (see `LICENSE`). Case files, codebook and registry: CC BY 4.0.

## Citation

Naglieri, G., Buono, E., Garofalo, C., Saracino, C. (2026). TRACE 0.1: tracing how climate judgments are taken up in later litigation. CLIMPACT, University of Bari. Zenodo. DOI: [pending].
