# TRACE 0.1 model cards

The models trained by the CLIMPACT project (University of Bari) for TRACE 0.1. Each has a version code in the TRACE registry (`versioni/registro.json`): the letter T marks a model trained by the project. They are research releases, trained and evaluated on one cited judgment, Urgenda (Supreme Court of the Netherlands, 20 December 2019, and the two earlier instances).

Every proposal the models make is shown to people, who confirm or correct it. The models never decide a citation on their own.

## T01, TRACE-Reranker 0.1

**What it does.** Scores a principle of the cited case against a text: the passage around an explicit citation, or a page near it in the same filing. In the TRACE pipeline it has two jobs:
- it gives a hint of which principle a citation takes (the hint is shown; it never ticks a principle on its own);
- it picks the nearby pages that a reader should check for the continuation of the argument. A page within two pages before and three after the citation is picked at a score of 0.5 or more; a page four to ten pages away at 0.8 or more; at most five pages per citation.

**Base model.** Qwen3-Reranker-4B (4 billion parameters, Apache-2.0), revision 22e68366.

**Adaptation.** A LoRA adapter, rank 16 on the attention projections, two epochs, three seeds averaged, with the instruction «uptake»; texts up to 2,560 tokens. The name of the cited case and its ECLI codes are masked, so the model scores the reasoning, not the name.

**Training data.** 263 judgments by the CLIMPACT team on candidate pages of Urgenda found by the semantic search, with a split between training and test frozen on 22 September 2026.

**Evaluation.**
- On the 526 citations of Urgenda that point to a paragraph of the judgment, the principle the model scores highest is one of the principles of that paragraph in 69% of cases (37% by chance).
- On a fixed test set of 133 judged rows from five citing cases never used in training, the area under the ROC curve is 0.787 (0.753 for the base model). This number measures agreement with the July labels, which mixed «same argument» and «taken from this judgment». It is not a measure of implicit uptake and should not be quoted as one.

**Limits.** Trained on labels that confused argument and source; it will be retrained on the principles confirmed by the team in the new pipeline. One cited judgment.

## T02 and T03, TRACE-Reader v0 and v1

**What they do.** The reading done by the external model (DeepSeek V4 Flash, codes L02 to L05) on a single GPU: for each explicit citation, whether it really is the cited case, the type of citation (chain mention, descriptive, substantive, distinguishing, critical), who speaks, and the proposition it supports. T03 also proposes the principles taken and the nearby pages that continue the argument.

**Base model.** Qwen3-14B (Apache-2.0), revision 40c06982.

**Adaptation.** A LoRA adapter, rank 16 on attention and MLP, two epochs, learning rate 1e-4, gradient accumulation 8; texts up to 6,144 tokens (T02) and 8,192 tokens (T03, which also reads the nearby pages).

**Training data.** 1,120 readings of Urgenda citations by DeepSeek V4 Flash (codes L02 and L04), kept only where the two readings of the same row agree on the type. Every row used to evaluate the model is excluded. **These models are distilled from a large language model: their training labels are DeepSeek's readings, not human judgments.** Human judgments are used only to evaluate them.

**Evaluation.** Agreement with the human coders on the type of citation, on 317 rows of Urgenda: T02 0.596 (Cohen's kappa 0.39), T03 0.599, DeepSeek itself 0.568. Principles: on 101 rows whose citation names a paragraph, T03 gets at least one principle right in 79% of cases (DeepSeek 86%, helped by the paragraph map in its instructions).

**Status.** Experimental. The proposals the team sees still come from DeepSeek. A Reader replaces DeepSeek only when it matches it on the rows the team judges blind (one in five rows is shown without any machine proposal), a test decided in advance.

**Limits.** One cited judgment; the human reference for the type was coded by one person.

## The retriever

TRACE-Retriever (pplx-embed-v1-4b with a LoRA adapter on the query side, weight 0.25) served the semantic search for implicit uptake without a citation. That search is paused: a check of the July results found about one real implicit uptake per hundred candidate pages. It will be redone with real citing passages as queries, and the retriever re-evaluated on that task before any release.

## Common to all

- Source corpus (code D01): Climate Litigation Database of the Sabin Center for Climate Change Law (Columbia Law School) with Climate Policy Radar, whole-database export `CCC-whole_data_dump-2026-07-26`; use authorised by Maria Antonia Tigre (Sabin Center). The texts of the filings are not redistributed.
- Hardware: NVIDIA H100 80GB, ReCaS-Bari data centre (INFN and University of Bari).
- Every version is recorded with base model revision, weight fingerprints, training data, settings, instructions and code in the TRACE registry.
- Authors: G. Naglieri, E. Buono, C. Garofalo, C. Saracino (CLIMPACT, University of Bari).
- Citation: Naglieri, G., Buono, E., Garofalo, C., Saracino, C. (2026). TRACE 0.1: tracing how climate judgments are taken up in later litigation. CLIMPACT, University of Bari. Zenodo. DOI: [pending].
