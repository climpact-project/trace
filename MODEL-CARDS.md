# TRACE 0.1 model cards

The models trained by the CLIMPACT project (University of Bari) for TRACE 0.1. Each has a version code in the TRACE registry (`versioni/registro.json`): the letter T marks a model trained by the project. They are research releases, trained and evaluated on one cited judgment, Urgenda (Supreme Court of the Netherlands, 20 December 2019, and the two earlier instances).

Every proposal the models make is shown to people, who confirm or correct it. The models never decide a citation on their own.

Cards updated on 30 September 2026, after an independent review of the registry and of these texts. The registry is the single source: where a card and the registry differ, the registry is right.

## T01, TRACE-Reranker 0.1

**What it does.** Scores a principle of the cited case against a text: the passage around an explicit citation, or a page near it in the same filing. In the TRACE pipeline it has two jobs:
- it gives a hint of which principle a citation takes (the hint is shown; it never ticks a principle on its own);
- it scores the pages near the citation, up to ten pages before and after, so that a rule can choose which ones the external reader should read for the continuation of the argument.

The choice of pages is not part of the model. It is the rule R03 in the registry: a page from two pages before to three after the citation is chosen at a score of 0.5 or more, a page further away at 0.8 or more, at most five pages per citation. The 0.8 threshold was measured on the pages read at four to ten pages from the citation; the 0.5 threshold is inherited and still to be calibrated on the team's judgments. Calibrating R03 does not retrain T01.

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

## The retriever

TRACE-Retriever (pplx-embed-v1-4b with a LoRA adapter on the query side, weight 0.25) served the July semantic search for implicit uptake without a citation. That search is paused: a check of the July results found about one real implicit uptake per hundred candidate pages. The retriever is **not part of this release**: it has no version code, no code copy and no weight fingerprint in the registry, and it is not in the Zenodo deposit. It will be redone with real citing passages as queries and re-evaluated on that task before any release, and it will enter the registry with a T code at that point.

## Limits common to all the figures

- **The agreement figures computed by the platform are not a blind measure.** The results the platform computes today (machine and team agree on the type in about 93% of judged rows, a proposed principle is confirmed in about 97%, a proposed continuation page in about 94%) are measured on judgments that people gave with the machine's proposals visible on the screen. A person who sees a ticked principle and leaves it ticked counts as agreement. These figures describe how often people changed a proposal, not how often the machine is right. Rows judged without any machine proposal are being judged now; a blind figure will be published only when that sample has a base.
- The human reference rows are not frozen: the set of rows judged by the principal investigator grew from 38 (28 September) to 43 (30 September), and comparisons between readings (L04, L05, L06) were made on bases of 35 to 38 rows. Those comparisons are provisional until the reference rows are frozen in a dated file.
- The instructions given to the external reader are exact copies where they were saved at run time (L05, L06, L07). For L04 the text is reconstructed after the fact from the current file, and for L02 and L03 the text is regenerated from the current case file and codebook: the registry says so in each entry (`ricostruita`).

## Common to all

- Source corpus (code D01): Climate Litigation Database of the Sabin Center for Climate Change Law (Columbia Law School) with Climate Policy Radar, whole-database export `CCC-whole_data_dump-2026-07-26`; use authorised by Maria Antonia Tigre (Sabin Center). The texts of the filings are not redistributed.
- Hardware: NVIDIA H100 80GB, ReCaS-Bari data centre (INFN and University of Bari).
- Every version is recorded with base model revision, weight fingerprints, training data, settings, instructions and code in the TRACE registry, with a note where a text is reconstructed rather than copied.
- Terms used here: «external reader» is DeepSeek V4 Flash (codes L); «TRACE-Reader» is T02 and T03; «uptake» is the relation between a citation and the cited case; «continuation» is a nearby page that carries the same uptake on; «case file» is the list of a case's principles (`cited-cases/*.yaml`); «dossier» is the case summary given to the reader (`*-fascicolo.md`); «test rows» is the fixed evaluation set; «judged without proposals» is the one-in-five sample shown with no machine proposal.
- Authors: G. Naglieri, E. Buono, C. Garofalo, C. Saracino (CLIMPACT, University of Bari).
- Citation: Naglieri, G., Buono, E., Garofalo, C., Saracino, C. (2026). TRACE 0.1: A Language Model for Climate Litigation Research. CLIMPACT, University of Bari. Zenodo. DOI: [pending].
