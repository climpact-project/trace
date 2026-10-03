# TRACE 0.1 model cards

The models trained by the CLIMPACT project (University of Bari) for TRACE 0.1. Each has a version code in the TRACE registry (`versioni/registro.json`): the letter T marks a model trained by the project. They are research releases, trained and evaluated on one cited judgment, Urgenda (Supreme Court of the Netherlands, 20 December 2019, and the two earlier instances), and used since on six cited cases.

Every proposal the models make is shown to people, who confirm or correct it. The models never decide a citation on their own.

Cards updated on 30 September 2026, after an independent review of the registry and of these texts, and on 3 October 2026 for the rules and data versions that changed since (R10, R11, S05, D02, D03). The registry is the single source: where a card and the registry differ, the registry is right.

## T01, TRACE-Reranker 0.1

**What it does.** Scores a principle of the cited case against a text: the passage around an explicit citation, or a page near it in the same filing. In the TRACE pipeline it has two jobs:
- it gives a hint of which principle a citation takes (the hint is shown; it never ticks a principle on its own);
- it scores the pages near the citation, up to ten pages before and after, so that a rule can choose which ones the external reader should read for the continuation of the argument.

The choice of pages is not part of the model. It is a rule in the registry, and the rule has changed twice:
- R03, Choice of the nearby pages to read (29 September 2026): a page from two pages before to three after the citation is chosen at a score of 0.5 or more, a page further away at 0.8 or more, at most five pages per citation.
- R08, Choice of the nearby pages, over the full window for every case (1 October 2026): the same thresholds, with T01 scores on every page of the window for every case (before, pages four to ten had scores only for Urgenda).
- R10, Choice of the surrounding pages: 0.5 at every distance within 10 pages, no cap (2 October 2026, used by the five-reading cycle): a page within ten pages before or after the citation is chosen when its best score on a principle is 0.5 or more, at any distance, with no limit on the number of pages; unreadable pages stay out. Measured with the external reader as a blind judge of which pages carry the uptake on, R10 brings 57% of those pages to the reader (95% interval 51-63%, bootstrap by filing) against 27% (20-34%) for R08, at 4.6 pages per citation instead of 2.0. The judge is the external reader, not the team: the comparison between the rules is more solid than the absolute shares.

Changing the rule does not retrain T01.

**Base model.** Qwen3-Reranker-4B (4 billion parameters, Apache-2.0), revision 22e68366.

**Adaptation.** A LoRA adapter, rank 16 on the attention projections, two epochs, three seeds averaged, with the instruction «uptake»; texts up to 2,560 tokens. The name of the cited case and its ECLI codes are masked, so the model scores the reasoning, not the name.

**Training data.** 263 judgments by the CLIMPACT team on candidate pages of Urgenda found by the July semantic search, with a split between training and test rows frozen on 22 September 2026. A rereading of those judgments found that most of them recorded «same argument», not «taken from this judgment».

**Evaluation.**
- On the 526 citations of Urgenda that point to a paragraph of the judgment, the principle the model scores highest is one of the principles of that paragraph in 69% of cases (37% by chance). This is the only measure of T01 taken against a label that does not depend on a model.
- On the fixed test rows (133 judged rows from five citing cases never used in training), the area under the ROC curve is 0.787 (0.753 for the base model). This number measures agreement with the July labels, which mixed «same argument» and «taken from this judgment». It is not a measure of implicit uptake and should not be quoted as one.

**Limits.** Trained on labels that confused argument and source; it will be retrained on the principles confirmed by the team in the new pipeline. One cited judgment.

## T02 and T03, TRACE-Reader v0 and v1

**What they do.** The reading done by the external reader (DeepSeek V4 Flash, codes L02 to L05 and L07) on a single GPU: for each explicit citation, whether it really is the cited case, the type of citation (chain mention, descriptive, substantive, distinguishing, critical), who speaks, and the proposition it supports. T03 also proposes the principles taken and the nearby pages that continue the argument.

**Base model.** Qwen3-14B (Apache-2.0), revision 40c06982.

**Adaptation.** A LoRA adapter, rank 16 on attention and MLP, two epochs, learning rate 1e-4, gradient accumulation 8; texts up to 6,144 tokens (T02) and 8,192 tokens (T03, which also reads the nearby pages).

**Training data.** 1,120 readings of Urgenda citations by DeepSeek V4 Flash (codes L02 and L04), kept only where the two readings of the same row agree on the type. Every row used to evaluate the model is excluded. **These models are distilled from a large language model: their training labels are DeepSeek's readings, not human judgments.** Human judgments are used only to evaluate them.

**Evaluation.** Agreement with the human coders on the type of citation, on 317 rows of Urgenda: T02 0.596 (Cohen's kappa 0.39), T03 0.599, DeepSeek itself 0.568. Principles: on 101 rows whose citation names a paragraph, T03 gets at least one principle right in 79% of cases (DeepSeek 86%, helped by the paragraph map in its instructions). These 317 rows were judged with DeepSeek's proposals visible to the coder: the figures measure agreement with judgments taken in that condition, not a blind agreement.

**Status.** Experimental. The proposals the team sees still come from the external reader. The adoption rule has changed once, and both rules are kept with their dates:
- Rule of 27 September 2026, fixed before the model was trained: on the 317 rows of Urgenda with a type given by people, if TRACE-Reader matches or beats the external reader, it makes the proposals. TRACE-Reader v0 scored 0.596 against DeepSeek's 0.568 and passed this test. It was **not** adopted, because those rows had been judged with DeepSeek's proposals visible, and the principal investigator asked for a measure taken without proposals.
- Rule of 30 September 2026: TRACE-Reader replaces the external reader only when it matches it on the rows the team judges without any machine proposal (one row in five among those queued since 29 September 2026). No such row with a comparable type exists yet, so this test has not been run.

**Limits.** One cited judgment; the human reference for the type was coded by one person, with the external reader's proposals visible.

## The external reader: five readings and a majority vote (R11)

The proposals the team sees come from the external reader, DeepSeek V4 Flash, under the rule R11, Proposals by majority vote of five readings, decided on 2 October 2026 and being applied (rows composed under it carry `R11` in their provenance). Each row is read five times: the type of citation by the citation reading (L02 for Urgenda, L03 for the other cases) and the principles and surrounding pages by the uptake reading with the dossier (L05; under the earlier rule R05 the principles came from L04).

- A type, a principle or a surrounding page is proposed when the majority of the valid readings votes for it (3 of 5). The votes are written next to each proposal («4/5»). With no principle reaching the majority the proposal is «none».
- A decision is uncertain when the margin is at most one vote; uncertain rows are marked and get a low confidence. A tie on the type goes to the first tied type in reading order, so the result is repeatable.
- A surrounding page is proposed only when the evidence quoted by the readings is really on the page.
- A principle proposed by the readings without evidence found on the page is kept and flagged, not dropped: dropping did not improve agreement with the team and lowered recall.

Why five: between two independent majorities, on 300 rows of all six cases, Krippendorff's alpha is 0.66 with one reading, 0.78 with three and 0.83 with five on the principles, and 0.67, 0.78 and 0.83 on the type; five is the first number of readings above 0.80, a threshold declared in advance as a convention. Below 0.80 even at five readings: the principles of KlimaSeniorinnen (0.68), the type for the ICJ advisory opinion (0.72) and for the Inter-American Court advisory opinion (0.76).

## The retriever

TRACE-Retriever (pplx-embed-v1-4b with a LoRA adapter on the query side, weight 0.25) served the July semantic search for implicit uptake without a citation. That search is paused: a check of the July results found about one real implicit uptake per hundred candidate pages. The retriever is **not part of this release**: it has no version code, no code copy and no weight fingerprint in the registry, and it is not in the Zenodo deposit. It will be redone with real citing passages as queries and re-evaluated on that task before any release, and it will enter the registry with a T code at that point.

## Limits common to all the figures

- **The agreement figures computed by the platform are not a blind measure.** The results the platform computes today (machine and team agree on the type in about 93% of judged rows, a proposed principle is confirmed in about 97%, a proposed continuation page in about 94%) are measured on judgments that people gave with the machine's proposals visible on the screen. A person who sees a ticked principle and leaves it ticked counts as agreement. These figures describe how often people changed a proposal, not how often the machine is right. Rows judged without any machine proposal are being judged now; a blind figure will be published only when that sample has a base.
- The human reference rows are not frozen: the set of rows judged by the principal investigator grew from 38 (28 September) to 43 (30 September), and comparisons between readings (L04, L05, L06) were made on bases of 35 to 38 rows. Those comparisons are provisional until the reference rows are frozen in a dated file.
- The instructions given to the external reader are exact copies where they were saved at run time (L05, L06, L07). For L04 the text is reconstructed after the fact from the current file, and for L02 and L03 the text is regenerated from the current case file and codebook: the registry says so in each entry (`ricostruita`).

## Common to all

- Source corpus: Climate Litigation Database of the Sabin Center for Climate Change Law (Columbia Law School) with Climate Policy Radar, read through its public API. Three data versions: D01, Documents: Climate Litigation Database, public API snapshot (26 July 2026); D02, Documents: D01 with OCR text of unreadable pages (3,171 pages in 94 filings from 2 October 2026); D03, Documents: D02 with Markdown for 277 filings of the 19/09/2026 update. The texts of the filings are not redistributed.
- Name search: S05, Name search on normalised text, with readmitted and new forms (in use from 2 October 2026). It finds every citation found by the earlier version S03 at the same position and adds new ones only: on a reading of the new rows, 155 of 163 were real citations (95.1%, Wilson 95% interval 90.6-97.5%).
- Hardware: NVIDIA H100 80GB, ReCaS-Bari data centre (INFN and University of Bari).
- Every version is recorded with base model revision, weight fingerprints, training data, settings, instructions and code in the TRACE registry, with a note where a text is reconstructed rather than copied.
- Terms used here: «external reader» is DeepSeek V4 Flash (codes L); «TRACE-Reader» is T02 and T03; «uptake» is the relation between a citation and the cited case; «continuation» is a nearby page that carries the same uptake on; «case file» is the list of a case's principles (`cited-cases/*.yaml`); «dossier» is the case summary given to the reader (`*-fascicolo.md`); «test rows» is the fixed evaluation set; «judged without proposals» is the one-in-five sample shown with no machine proposal.
- Authors: G. Naglieri, E. Buono, C. Garofalo, C. Saracino, L. Dell'Atti (CLIMPACT, University of Bari).
- Citation: Naglieri, G., Buono, E., Garofalo, C., Saracino, C., Dell'Atti, L. (2026). CLIMPACT TRACE 0.1: Traceable Reception and Attribution in Climate-law Evidence. CLIMPACT, University of Bari. Zenodo. DOI reserved: 10.5281/zenodo.23082522 (active on publication).
