# TRACE 0.1 model cards

The models trained by the CLIMPACT project (University of Bari) for TRACE 0.1, and the large language model whose readings make the proposals today, DeepSeek V4 Flash. Each has a version code in the TRACE registry (`versioni/registro.json`): the letter T marks a model trained by the project. They are research releases: T01, T02 and T03 were trained and evaluated on one cited judgment, Urgenda (Supreme Court of the Netherlands, 20 December 2019, and the two earlier instances), and used since on six cited cases; T04 was trained on four cited judgments (74 of its 94 examples from Urgenda).

Every proposal is open to the research team, who confirm or correct it: at release 414 of the 7,893 citations are verified, and the others are machine proposals. The models never decide a citation on their own.

Cards updated on 30 September 2026, after an independent review of the registry and of these texts, on 3 October 2026 for the rules and data versions that changed since (R10, R11, S05, D02, D03), and on 5 October 2026 for the readings and the reasoning reranker on trial (L13 and below), and on 6 October 2026 for T04, the reasoning reranker trained by the project. The registry is the single source: where a card and the registry differ, the registry is right.

## T01, TRACE-Reranker 0.1

**What it does.** Scores a principle of the cited case against a text: the passage around an explicit citation, or a page near it in the same filing. In the TRACE pipeline it has two jobs:
- it gives a hint of which principle a citation takes (the hint is shown; it never ticks a principle on its own);
- it scores the pages near the citation, up to ten pages before and after, so that a rule can choose which ones DeepSeek V4 Flash should read for the continuation of the argument.

The choice of pages is not part of the model. It is a rule in the registry, and the rule has changed twice:
- R03, Choice of the nearby pages to read (29 September 2026): a page from two pages before to three after the citation is chosen at a score of 0.5 or more, a page further away at 0.8 or more, at most five pages per citation.
- R08, Choice of the nearby pages, over the full window for every case (1 October 2026): the same thresholds, with T01 scores on every page of the window for every case (before, pages four to ten had scores only for Urgenda).
- R10, Choice of the surrounding pages: 0.5 at every distance within 10 pages, no cap (2 October 2026, used by the five-reading cycle): a page within ten pages before or after the citation is chosen when its best score on a principle is 0.5 or more, at any distance, with no limit on the number of pages; unreadable pages stay out. Measured with DeepSeek V4 Flash as a blind judge of which pages carry the uptake on (the instruction of L07, Surrounding pages reread on the proposed principles, at temperature 0, with pages of every rule mixed so that the judge does not know which rule chose them; the research team is verifying these pages), R10 brings 57% of those pages to DeepSeek V4 Flash (95% interval 51-63%, bootstrap by filing) against 27% (20-34%) for R08, at 4.6 pages per citation instead of 2.0. Absolute shares are as good as that judge; the comparison between the rules is firmer, because the same judge read every page blind.

Changing the rule does not retrain T01.

**Base model.** Qwen3-Reranker-4B (4 billion parameters, Apache-2.0), revision 22e68366.

**Adaptation.** A LoRA adapter, rank 16 on the attention projections, two epochs, three seeds averaged, with the instruction «uptake»; texts up to 2,560 tokens. The name of the cited case and its ECLI codes are masked, so the model scores the reasoning, not the name.

**Training data.** 263 judgments by the CLIMPACT team on candidate pages of Urgenda found by the July semantic search, with a split between training and test rows frozen on 22 September 2026. A rereading of those judgments found that most of them recorded «same argument», not «taken from this judgment».

**Evaluation.**
- On the 526 citations of Urgenda that point to a paragraph of the judgment, the principle the model scores highest is one of the principles of that paragraph in 69% of cases (37% by chance). This is the only measure of T01 taken against a label that does not depend on a model.
- On the fixed test rows (133 judged rows from five citing cases never used in training), the area under the ROC curve is 0.787 (0.753 for the base model). This number measures agreement with the July labels, which mixed «same argument» and «taken from this judgment». It is not a measure of implicit uptake and should not be quoted as one.

**Limits.** Trained on labels that confused argument and source; it will be retrained on the principles confirmed by the team in the new pipeline. One cited judgment.

## T02 and T03, TRACE-Reader v0 and v1

**What they do.** The reading done by DeepSeek V4 Flash (codes L02 to L05 and L07), on a single GPU: for each explicit citation, whether it really is the cited case, the type of citation (chain mention, descriptive, substantive, distinguishing, critical), who speaks, and the proposition it supports. T03 also proposes the principles taken and the nearby pages that continue the argument.

**Base model.** Qwen3-14B (Apache-2.0), revision 40c06982.

**Adaptation.** A LoRA adapter, rank 16 on attention and MLP, two epochs, learning rate 1e-4, gradient accumulation 8; texts up to 6,144 tokens (T02) and 8,192 tokens (T03, which also reads the nearby pages).

**Training data.** 1,120 readings of Urgenda citations by DeepSeek V4 Flash (codes L02 and L04), kept only where the two readings of the same row agree on the type. Every row used to evaluate the model is excluded. **These models are distilled from DeepSeek V4 Flash, a large language model: their training labels are DeepSeek's readings, not human judgments.** Human judgments are used only to evaluate them.

**Evaluation.** Agreement with the human coders on the type of citation, on 317 rows of Urgenda: T02 0.596 (Cohen's kappa 0.39), T03 0.599, DeepSeek itself 0.568. Principles: on 101 rows whose citation names a paragraph, T03 gets at least one principle right in 79% of cases (DeepSeek 86%, helped by the paragraph map in its instructions). These 317 rows were judged with DeepSeek's proposals visible to the coder: the figures measure agreement with judgments taken in that condition, not a blind agreement.

**Status.** Experimental. The proposals the team sees still come from DeepSeek V4 Flash. The adoption rule has changed once, and both rules are kept with their dates:
- Rule of 27 September 2026, fixed before the model was trained: on the 317 rows of Urgenda with a type given by people, if TRACE-Reader matches or beats DeepSeek V4 Flash, it makes the proposals. TRACE-Reader v0 scored 0.596 against DeepSeek's 0.568 and passed this test. It was **not** adopted, because those rows had been judged with DeepSeek's proposals visible, and the principal investigator asked for a measure taken without proposals.
- Rule of 30 September 2026: TRACE-Reader replaces DeepSeek V4 Flash only when it matches it on the rows the team judges without any machine proposal (one row in five among those queued since 29 September 2026). No such row with a comparable type exists yet, so this test has not been run.

**Limits.** One cited judgment; the human reference for the type was coded by the research team with DeepSeek's proposals visible. Blind and double-coded judgments by the team are in progress.

## DeepSeek V4 Flash: five readings and a majority vote (R11)

DeepSeek V4 Flash (deepseek-ai/DeepSeek-V4-Flash-0731, MIT licence) is a large language model with open weights, not trained by the project. We run it with vLLM on NVIDIA H100 GPUs at ReCaS-Bari (INFN and University of Bari); the codes L are its readings. The proposals the team sees come from DeepSeek V4 Flash, under the rule R11, Proposals by majority vote of five readings, decided on 2 October 2026 and applied in this release, and under R15 and R16, which, like R12 (a principle needs two votes) on which they are built, propose a principle with 2 of 5 readings and flag the row as uncertain, and take the supporting sentence and the evidence from the text of the filing (rows carry the rule in their provenance); under R11 a principle needs a majority, 3 of 5. Each row is read five times: the type of citation by the citation reading (L02 for Urgenda, L03 for the other cases) and the principles and surrounding pages by the uptake reading with the dossier (L05; under the earlier rule R05 the principles came from L04).

- A type, a principle or a surrounding page is proposed when the majority of the valid readings votes for it (3 of 5). The votes are written next to each proposal («4/5»). With no principle reaching the majority the proposal is «none».
- A decision is uncertain when the margin is at most one vote; uncertain rows are marked and get a low confidence. A tie on the type goes to the first tied type in reading order, so the result is repeatable.
- A surrounding page is proposed only when the evidence quoted by the readings is really on the page.
- A principle proposed by the readings without evidence found on the page is kept and flagged, not dropped: dropping did not improve agreement with the team and lowered recall.

Why five: between two independent majorities, on 300 rows of all six cases, Krippendorff's alpha is 0.66 with one reading, 0.78 with three and 0.83 with five on the principles, and 0.67, 0.78 and 0.83 on the type; five is the first number of readings above 0.80, a threshold declared in advance as a convention. Below 0.80 even at five readings: the principles of KlimaSeniorinnen (0.68), the type for the ICJ advisory opinion (0.72) and for the Inter-American Court advisory opinion (0.76).

## L13, the reading of a close pair (applied with S08 on 8 October 2026)

**What it does.** For two references to the same cited case in the same filing, less than 5,000 characters apart (the close pairs of S08), the reader gets the true text of the filing from before the first to after the second reference, with the two points marked, and says whether they are **one citation or two**, which one stays, where each sits (body text or footnote), which footnote the sentence calls, and the exact sentence of each. The clues that the code computes (same note, footnote called by the sentence) are never in the question: they are used afterwards, to measure the readings and to send to the team the pairs in which the readings and a strong clue contradict each other.

**Readers.** DeepSeek V4 Flash (the same model as L05, high reasoning, five readings, three of five decide) and Qwen3.5-9B, as released (three readings, two of three decide). Where the two readers agree and no strong clue contradicts them, the pair is merged (as in C03) or kept as two; otherwise it goes to the team. A reading counts only if the two sentences it quotes are in the text of the filing and are not copied from the prompt (the brakes of R14 and R16).

**Status.** Applied with S08 on 8 October 2026: of the 6,290 pairs decided, 222 were merged, 791 were sent to the research team (1,398 «To review» requests) and 4,612 stay two rows. The pairs of C03 reread one by one (850, 692 of them with both rows in the same filing) are the truth on which the readers were measured; the strong clues alone, on those 692 pairs, decide 401 (58%) and are right in 397 (99.0%), and leave 291 to the team.

**Limits.** The truth is cut at one page: C03 looked for the same sentence within one page, so it says nothing about pairs farther apart, and the threshold of 5,000 characters is a cost decision, not a measured boundary.

## A reasoning reranker (Qwen3.5-9B, not trained): on trial, not in use

**What it is.** Qwen3.5-9B (revision c2022362), as released and **not trained by the project**, with reasoning on. For every principle of the cited case it writes a reasoning and answers yes, no or uncertain, quotes the words of the filing it relies on and gives a score taken from the probabilities of the verdict tokens. It was tried as a possible replacement for T01 in choosing the principles. **T01 stays the reranker in use for the surrounding pages, and the proposals still come from DeepSeek V4 Flash.**

**Measured** on the 691 citations the research team has judged, and on the 137 of them that form the jury set. The figures are on the principles (precision, recall, F1 against the principles the team confirmed):

| | F1, 137 rows | F1, all answered rows |
|---|---:|---:|
| Reasoning reranker, 9B on the text | 0.70 (precision 0.73, recall 0.68) | 0.70 |
| T01, score of 0.5 or more | 0.50 | 0.53 |
| The five readings of DeepSeek V4 Flash | 0.70 | 0.70 |

The score is better than T01's at ranking (AUC 0.86 against 0.75 on the same decisions, 137 rows) and worse calibrated (expected calibration error 0.13 against 0.06).

**Cautions.**
- **The figure is optimistic.** Three rules of the draft instructions given to the 9B were derived from counts taken on these same judged rows (G05: the team's descriptive citations always take a principle, 27 of 27; G06: the missed principle did not come from the proposal that was shown; the third: in advisory opinions the participating States are a «party», 5 of 6). No judgment of a row enters the question of that row, but the effect of these rules on these rows is overstated. The clean measure is the blind sample, which the team has not judged yet. These rules were drafts when the models were trained; the principal investigator approved them on 6 October 2026, after training.
- **Two of the planned trials have run:** the 9B on the text, and the 9B with the image of the page (F1 0.68 on the 55 rows it covers). The walk through the surrounding pages, the form with one principle per call and the larger model have not.
- The model slips into Chinese or Japanese in the middle of a sentence: 35% of its 526 reasonings contain at least one such character, and 56 answers have one in the final JSON. It is a reason not to rely on it as it is.
- The team's judgments are the reference, and some were given with machine proposals visible: they measure agreement with the team, not a blind agreement.
- A LoRA adaptation of the 9B on its own answers that match the team's verdict has been trained and measured: it is **T04**, the next card.

## T04, TRACE-Reranker, reasoning (new in this release)

**What it does.** The same task as the untrained 9B above: for a citation of the cited case, and for **every principle of the case**, it writes a short reasoning and answers yes, no or uncertain, with the words of the filing it relies on (copied letter by letter, checked by the brakes of R14 and R16) and a score from 0 to 1. Where T01 gives only a score, T04 gives the reasoning behind each verdict, so that a person can read why.

**Status.** Published with TRACE 0.1 as a new model, **not used to produce any datum of this release**: the proposals of TRACE 0.1 come from DeepSeek V4 Flash (R11) and T01. Rereading the corpus with T04 is the plan for TRACE 0.2 (a reasoning reranker, DeepSeek V4 Flash at high reasoning, and a decision step after DeepSeek when the rule allows). Until then T01 stays the reranker in use for the surrounding pages.

**Base model.** Qwen3.5-9B (9 billion parameters, Apache-2.0), revision c2022362, with reasoning on.

**Adaptation.** A LoRA adapter (rank 16, alpha 32, dropout 0.05) on the attention, linear-attention and MLP projections of the language model: 40,108,032 trainable parameters, three epochs, learning rate 1e-4 with cosine decay, eight examples per update, sequences of up to 28,000 tokens, loss only on the answer (reasoning, closing and JSON). About 20 minutes on an NVIDIA H100 at ReCaS-Bari, 5 October 2026. The adapter is in `peft` format; the folder includes a check that it fits the base model.

**Training data.** Self-training on the model's own reasoning (STaR, Zelikman and others, 2022): the base 9B had answered 526 of the 691 citations the research team judged; where its verdict on the principles matched the team's, the answer with its reasoning was kept. 94 examples remain: 63 confirmed by the team with principles equal to the team's and 31 rejected by the team to which the model had said no to everything. By cited case: Urgenda 74, Future Generations 14, KlimaSeniorinnen 3, Neubauer 3; 81 filings. Left out: answers with Chinese or Japanese characters in the JSON or more than two in the reasoning, answers with an uncertain among the principles, incomplete or truncated answers and rows marked «reclassified». The judgment of the team only chooses which answers to keep; it is never in the question. The blind samples are not among the 691.

**Instructions.** The question of the reasoning reranker (instruction, general rules G01 to G08, principles of the case with their rules, the citation, its page, the question and the JSON format). Rules G05 to G08 were **drafts when T04 was trained** (5 October 2026), and the prompt marks them so («BOZZA, non approvata»), as it does several parts of the case files; **the principal investigator approved rules G05 to G08 on 6 October 2026, after training**. The fixed blocks are in the folder `prompt/`.

**Evaluation.** Cross-validation by filing: four fold adapters, each trained on three quarters of the filings, answered the quarter it had not seen, and are compared with the untrained 9B on the same rows. F1 on the principles against the principles the team confirmed:

| | T04 method | Untrained 9B | Difference in F1 (95% interval, resampling filings) |
|---|---:|---:|---:|
| 485 rows answered by both | 0.740 | 0.708 | +0.03 (-0.005 to +0.070) |
| the 137 rows of the jury set | 0.756 (precision 0.780, recall 0.733) | 0.730 (0.727, 0.733) | +0.03 (-0.033 to +0.079) |

For reference, T01 has an F1 of about 0.50 on these judgments and the five readings of DeepSeek V4 Flash 0.70 (from different runs and sets, not strictly like for like). **The gain over the untrained 9B is small and not proven: both intervals include zero.**

**Across seeds.** That figure comes from one training seed. Over 5 trainings with different seeds (the original and 4 more; the others planned belong to TRACE 0.2) the F1 on the principles is 0.718 on average (standard deviation 0.023, from 0.686 to 0.740) against 0.706 for the untrained model: the difference is +0.012 on average, positive for 3 of 5 seeds, with a 95% interval across seeds of -0.011 to +0.036; on the 137 rows of the jury set the mean is 0.720 and the difference -0.002 (-0.034 to +0.031). By the rule written before the results, T04 (TRACE-Reranker, reasoning) is **on a par with the untrained model**: the gain lies within the variation between identical trainings, and the single-seed F1 of 0.740 is not its typical value. The standard deviation between seeds, 0.023, is the smallest effect a later comparison between adapters can claim.

**Second training, in progress.** A second training of T04 started on 9 October 2026 and is in progress: it learns also from the rows where the untrained model was wrong, from the judgments of the research team (of the 691 judged citations, the 427 that the first training could not use), with the model writing the reasoning that leads to the team's answer (the rationalisation step of STaR), on several seeds and with the same cross-validation by filing; a separate arm, with the rows on which the five readings of DeepSeek V4 Flash agree as machine labels, declared as such, is planned. It has no result yet, and its outcome belongs to the next release.

**Limits.**
- **Few examples:** 94, from four cited judgments, 74 of them Urgenda.
- **The figure is optimistic.** Three rules of the instructions (approved by the principal investigator on 6 October 2026, after training) were derived from counts taken on these same judged rows (G05, G06, and C05 on advisory opinions). The cross-validation by filing cannot clean them. The clean measure is on blind rows, too few in this set to give one.
- **The published adapter has no measure of its own.** The figures are those of the fold adapters; the published one is trained on all 94 examples with the same recipe.
- **Selection of the easy:** the examples are answers that already agree with the team; the difficult rows have none.
- **Language:** the model slips into Chinese or Japanese in the middle of a sentence, and the training did not cure it: 36% of the reasonings of the fold adapters (250 of 691) and 10% of their JSON answers (70) contain such characters, against 35% and 11% for the untrained model.
- The team's judgments are the reference, and some were given with machine proposals visible: they measure agreement with the team, not a blind agreement.

Next: TRACE 0.2. The whole corpus read again with our own reasoning reranker, trained on our team's judgments and released open with TRACE 0.1.

## The retriever

TRACE-Retriever (pplx-embed-v1-4b with a LoRA adapter on the query side, weight 0.25) served the July semantic search for implicit uptake without a citation. That search is paused: a check of the July results found about one real implicit uptake per hundred candidate pages. The retriever is **not part of this release**: it has no version code, no code copy and no weight fingerprint in the registry, and it is not in the Zenodo deposit. It will be redone with real citing passages as queries and re-evaluated on that task before any release, and it will enter the registry with a T code at that point.

## Limits common to all the figures

- **The agreement figures computed by the platform are not a blind measure.** The results the platform computes today (machine and team agree on the type in about 93% of judged rows, a proposed principle is confirmed in about 97%, a proposed continuation page in about 94%) are measured on judgments that people gave with the machine's proposals visible on the screen. A person who sees a ticked principle and leaves it ticked counts as agreement. These figures describe how often people changed a proposal, not how often the machine is right. Rows judged without any machine proposal are being judged now; a blind figure will be published only when that sample has a base.
- The human reference rows are not frozen: the set of rows judged by the principal investigator grew from 38 (28 September) to 43 (30 September), and comparisons between readings (L04, L05, L06) were made on bases of 35 to 38 rows. Those comparisons are provisional until the reference rows are frozen in a dated file.
- The instructions given to DeepSeek V4 Flash are exact copies where they were saved at run time (L05, L06, L07). For L04 the text is reconstructed after the fact from the current file, and for L02 and L03 the text is regenerated from the current case file and codebook: the registry says so in each entry (`ricostruita`).

## Common to all

- Source corpus: Climate Litigation Database of the Sabin Center for Climate Change Law (Columbia Law School) with Climate Policy Radar, read through its public API. Three data versions: D01, Documents: Climate Litigation Database, public API snapshot (26 July 2026); D02, Documents: D01 with OCR text of unreadable pages (3,171 pages in 94 filings from 2 October 2026); D03, Documents: D02 with Markdown for 277 filings of the 19/09/2026 update. The texts of the filings are not redistributed.
- Name search: the rows of this release come from S01, S02, S03, S05, S06, S07 (Name search: footnote-aware grouping, descriptive references, same-page dedup) and S08 (Close pairs); S05, Name search on normalised text, with readmitted and new forms (in use from 2 October 2026). It finds every citation found by the earlier version S03 at the same position and adds new ones only: on a reading of the new rows, 155 of 163 were real citations (95.1%, Wilson 95% interval 90.6-97.5%).
- Hardware: NVIDIA H100 80GB, ReCaS-Bari data centre (INFN and University of Bari); DeepSeek V4 Flash runs on them with vLLM.
- Every version is recorded with base model revision, weight fingerprints, training data, settings, instructions and code in the TRACE registry, with a note where a text is reconstructed rather than copied.
- T04 (6 October 2026) is trained on answers of the untrained Qwen3.5-9B that matched the team's verdict: its reasoning is its own, selected by the team's judgment, and no judgment of a row is ever in the question of that row.
- Rules and readings added on 5 October 2026: C03 and C07 (applied on 5 October), S08 and L13 (applied on 8 October), described in the [README](README.md#applied-and-on-trial-5-and-8-october-2026) and in the registry.
- Terms used here: «DeepSeek V4 Flash» is the large language model that reads the citations (codes L); «TRACE-Reader» is T02 and T03, distilled from it; «uptake» is the relation between a citation and the cited case; «continuation» is a nearby page that carries the same uptake on; «case file» is the list of a case's principles (`cited-cases/*.yaml`); «dossier» is the case summary given to DeepSeek V4 Flash (`*-fascicolo.md`); «test rows» is the fixed evaluation set; «judged without proposals» is the one-in-five sample shown with no machine proposal.
- Authors: G. Naglieri, E. Buono, C. Garofalo, C. Saracino, L. Dell'Atti, G. A. Rojas Verdugo (CLIMPACT, University of Bari).
- Citation: Naglieri, G., Buono, E., Garofalo, C., Saracino, C., Dell'Atti, L., Rojas Verdugo, G. A. (2026). CLIMPACT TRACE 0.1: Traceable Reception and Attribution in Climate-law Evidence. CLIMPACT, University of Bari. Zenodo. DOI reserved: 10.5281/zenodo.23082522 (active on publication).
