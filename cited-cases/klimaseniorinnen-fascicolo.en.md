English translation of the Italian case file used by TRACE 0.1 (klimaseniorinnen-fascicolo.md, SHA-256 7400e3f663922516e3e9437e8fa2162674c2d359934fcc18e715c10a41f2261c), made on 7 October 2026 with DeepSeek V4 Flash and not yet checked by the research team.

# KlimaSeniorinnen case file

1 October 2026, version 1, prepared by the research team from primary sources, with Claude Opus 5.5 as ancillary support (summarising, systematising and reordering), PROPOSAL for the PI. Sources used: the judgment in the corpus (European Court of Human Rights, Grand Chamber, 9 April 2024, application no. 53600/20, `verein-klimaseniorinnen-schweiz-and-others-v-switzerland-judgment_f4b1`, 260-page PDF, English text); `cited-cases/neubauer-fascicolo.md` and `cited-cases/neubauer-P05.yaml` as a model; the corpus texts citing the judgment, read through the paragraph references found by `conta_paragrafi.py`. No human judgment, no training or test files. Every quotation in inverted commas was found in the corpus with only spaces normalised; what is not found there is marked «[non verificato nel corpus]». Page = `<!-- page N -->` marker of the markdown, which coincides with the PDF page; the printed numbering of the judgment is the PDF page minus 2. § = paragraph of the Court (1-657).
Certo, fornisci il testo da tradurre.
Companion files: `klimaseniorinnen.yaml` (forms, probes, canonical), `klimaseniorinnen-mappa-paragrafi.yaml` (all paragraphs, one per entry or per group), `PROPOSTA.md` (summary and questions), `conta_paragrafi.py` (counts).

## 0. What it is for and how to read it

You are given a passage from ANOTHER case. You must state whether it takes up a proposition from KlimaSeniorinnen (RIPRESA), whether it asserts something similar based on another source (ALTRA_FONTE), or whether it does not assert it (NON_AFFERMA).

Links in the chain of argument:

- (a) Climate change is not classic environmental harm: no single source, complex chain of effects, sources in all basic activities (§§ 414-418). Environmental case law is not transferred: a tailored approach is needed (§ 422). The Court assumes as fact that climate change exists, seriously threatens rights, that States know this and can act (§ 436).
- (b) Judicial review is complementary to democratic processes and the intergenerational perspective justifies it (§§ 410-413, 419-421, 449-451).
- (c) Causation: no conditio sine qua non (§ 439). Each State has its own share of responsibility and cannot evade it by pointing to others; against «goccia nel mare» a real prospect of changing the outcome suffices (§§ 441-444).
- (d) Victim status of individuals: two criteria and a particularly high threshold (§§ 479-488). Standing of associations: three conditions, without the represented persons having to be victims (§§ 489-503).
- (e) Article 8 includes a right to effective protection from the serious effects of climate change (§ 519). The State must do its part: a primary duty of mitigation, supplemented by adaptation (§§ 544-546, 552). Article 2 remains open (§§ 507-513, 536-537).
- (f) Differentiated margin of appreciation: narrow on commitment and targets, wide on means (§ 543); overall assessment (§ 551); procedural safeguards (§§ 553-554).
- (g) Requirements of the regulatory framework: neutrality over approximately three decades, carbon budget or equivalent quantification, intermediate targets, proof of compliance, updating, timely and coherent action (§§ 547-550).
- (h) Application: Swiss gaps, no budget, missed past targets; violation of Article 8 (§§ 555-574).
- (i) Article 6: the association's action for the implementation of measures already provided for by law falls within access to court; the Swiss courts did not examine it; violation (§§ 608-640).
- (l) Article 46: no specific measure; the State chooses, under the Committee of Ministers (§ 657).

Five things to always keep in mind.

1. The applicants are five, but only the association wins. The four women do not reach the threshold of victim status (§§ 527-535, operative point 5). Whoever writes that the Court recognised elderly women as victims gets the case wrong; whoever writes that it recognised their vulnerability but not victim status cites it correctly (§ 531).
2. The right is that of Article 8, not Article 2. The Court examines the association's application «from the angle of Article 8 alone» and finds it unnecessary to examine the applicability of Article 2 (§ 537, operative point 6). The pages on Article 2 (§§ 507-513) are principles, not a decision.
3. The Court sets no figure and no measure. It does not say which percentage nor which budget: it says that a budget, or an equivalent quantification, must exist (§§ 550 (a), 570, 572). It does not indicate measures under Article 46 (§ 657). This is the clear difference from Urgenda, where the minimum is set by the court.
4. The carbon budget comes from Neubauer. Paragraph 571 says so: «The Court also finds convincing the reasoning of the GFCC, which rejected the argument that it was impossible to determine the national carbon budget, pointing to, inter alia, the principle of common but differentiated responsibilities under the UNFCCC and the Paris Agreement (see Neubauer and Others, cited in paragraph 254 above, paragraphs 215-29).» Whoever takes up the national budget from here takes up Neubauer in nested form (5.4).
5. On the same day the same Grand Chamber decided Duarte Agostinho v. Portugal and 32 States and Carême v. France, both inadmissible (§ 5). The three judgments are cited together; the paragraph numbers of each are their own (Duarte §§ 202-03, cited from § 442, belong to Duarte).

## 1. The ruling

### 1.1 Identity, structure, numbering

European Court of Human Rights, Grand Chamber, judgment of 9 April 2024, Verein KlimaSeniorinnen Schweiz and Others v. Switzerland, application no. 53600/20, presided over by Síofra O'Leary (p. 233). Adopted on 14 February 2024 (§ 556, which fixes the state of the legislation examined as of that date). Public hearing on 29 March 2023 (§ 9). Application lodged on 26 November 2020 (§ 289); referred to the Grand Chamber on 26 April 2022 (§ 4). The judgment is rendered in «in English and in French» (p. 233); the corpus contains only the English version. ECLI:CE:ECHR:2024:0409JUD005360020, not written in the judgment but used by 9 documents in the corpus.

Applicants: the association Verein KlimaSeniorinnen Schweiz, over 2,000 members resident in Switzerland, average age 73 years, almost 650 over 75 (§ 521), and four individual members (§§ 12-21; the second one died during the proceedings and her son continues them, §§ 273-274). Complaints: omissions by the Swiss authorities in mitigation (Arts. 2 and 8), lack of access to a court (Art. 6), lack of an effective remedy (Art. 13) (§ 3).

Structure: summary by the Registry (pp. 1-2, «Does not bind the Court»); table of contents (pp. 3-9); procedure (§§ 1-9); facts: applicants and the Swiss proceedings (§§ 10-63), facts on climate (§§ 64-120); domestic, international, European and comparative legal framework (§§ 121-272); law: preliminary issues (§§ 273-290), introductory observations (§§ 291-297), Arts. 2 and 8 (the parties' arguments §§ 298-409, the Court's assessment §§ 410-574), Art. 6 (§§ 575-640), Art. 13 (§§ 641-645), Arts. 41 and 46 (§§ 646-657); operative provisions (pp. 232-233); partly concurring and partly dissenting opinion of Judge Eicke (pp. 235-260, with its own numbering).

Operative provisions (pp. 232-233), in summary: standing of the association and examination under Art. 8 alone (16 votes to 1); victim status of the four individual applicants rejected and their applications inadmissible (unanimously); Art. 2 not examined (unanimously); violation of Art. 8 (16 to 1); Art. 6 § 1 applicable to the association (16 to 1) and violated (unanimously); Art. 13 absorbed; EUR 80,000 in costs.

### 1.2 Procedural history

Swiss proceedings (§§ 22-63). On 25 November 2016, the applicants asked the Federal Council and three offices, pursuant to Article 25a of the Federal Act on Administrative Procedure, to put an end to omissions in climate protection (§ 22). The DETEC dismissed the request on 25 April 2017 for lack of standing (§ 28). The Federal Administrative Court dismissed the appeal on 27 November 2018: the applicants were not affected more than the rest of the population, and the action was a popular action (§§ 34, 42). The Federal Supreme Court dismissed the appeal on 5 May 2020: the rights were not affected with sufficient intensity, the threshold «ben sotto 2 gradi» would not be exceeded in the short term, and the path was political (§§ 52, 56-60); Articles 6 and 13 were not applicable (§§ 61-62).

Climate facts (§§ 64-120). The applicants' arguments on the increase in heat-related mortality among elderly women (§§ 65-68) and on Swiss measures; the Government's arguments; then the facts that the Court derives mainly from the IPCC (§§ 103-120), including the importance of carbon budgets (§ 116) and the «rapidly closing window of opportunity» (§ 118). Comparative overview (§§ 235-272): France, Germany (Neubauer, §§ 254-257, with the official headnotes), Ireland, the Netherlands (Urgenda, §§ 260-261), Norway, Spain, the United Kingdom, Belgium.

Preliminary issues (§§ 273-290). Emissions «incorporate» in imported goods (about 70% of the Swiss footprint in 2015) fall within the scope of the application (§§ 279-283); they do not raise a question of jurisdiction under Article 1, because the applicants reside in Switzerland, but rather one of responsibility (§ 287).

General considerations (§§ 410-457). Climate change is «one of the most pressing issues of our times» and raises a question of the allocation of burdens between generations (§ 410). «Judicial intervention, including by this Court, cannot replace or provide any substitute for the action which must be taken by the legislative and executive branches of government. However, democracy cannot be reduced to the will of the majority of the electorate and elected representatives, in disregard of the requirements of the rule of law.» (§ 412). Five differences from classic environmental harm (§§ 415-421) and therefore a tailored approach: «it would be neither adequate nor appropriate to follow an approach consisting in directly transposing the existing environmental case-law to the context of climate change.» (§ 422). Future generations will bear increasing burdens without participating in decisions; the intergenerational perspective adds a justification for judicial review (§ 420). Causation in four dimensions (§§ 424-426); proof, with the particular weight of IPCC reports (§§ 427-430); effects on rights and the living instrument (§§ 431-434); Article 8 is also engaged by risks (§ 435); the Court assumes as a fact that «there are sufficiently reliable indications that anthropogenic climate change exists, that it poses a serious current and future threat to the enjoyment of human rights guaranteed under the Convention, that States are aware of it and capable of taking measures to effectively address it» (§ 436). Tenuous causal link: no «strict conditio sine qua non» (§ 439). Own share: «The Court considers that a respondent State should not evade its responsibility by pointing to the responsibility of other States, whether Contracting Parties to the Convention or not.» (§ 442), consistent with concurrent responsibility (§ 443); against the «goccia nel mare»: «what is important, and sufficient to engage the responsibility of the State, is that reasonable measures which the domestic authorities failed to take could have had a real prospect of altering the outcome or mitigating the harm» (§ 444). No right to the environment as such (§§ 445-448). Jurisdiction: «the Court’s competence in the context of climate-change litigation cannot, as a matter of principle, be excluded» and «the question is no longer whether, but how, human rights courts should address the impacts of environmental harms on the enjoyment of human rights» (§ 451). Harmonious and evolutive interpretation, within the limits of subsidiarity (§§ 452-457).

Admissibility: victim status and standing (§§ 458-503). After the recapitulation of general principles (§§ 460-477), the causal link «legally relevant» between State omissions and harm (§ 478). Then victim status in the climate context: an indefinite number of affected persons and omissions in general measures (§§ 479-480); the problem of actio popularis (§§ 481-484); the category of potential victims as «class of people» is not useful (§ 485); the two criteria of § 487: «the applicant must be subject to a high intensity of exposure to the adverse effects of climate change» and «(b) there must be a pressing need to ensure the applicant’s individual protection, owing to the absence or inadequacy of any reasonable measures to reduce harm.»; and § 488: «The threshold for fulfilling these criteria is especially high.» For associations: importance of collective action and Aarhus (§§ 489-494), distinction between victim and representation (§§ 495-498), climate as a common concern and allocation between generations (§ 499), no abstract grievance (§§ 500-501), the three conditions of § 502 and the rule that «the standing of an association to act on behalf of the members or other affected individuals within the jurisdiction concerned will not be subject to a separate requirement» of showing the victim status of those represented; § 503 on the relevance of the members' access to court.

Applicability (§§ 506-537). Art. 2: activity inherently dangerous to life (§ 509); risk «real and imminent» read in light of irreversibility (§§ 511-513), and if victim status is established «a serious risk of a significant decline in a person’s life expectancy owing to climate change ought also to trigger the applicability of Article 2.» (§ 513). Art. 8: recapitulation (§§ 514-518) and then the right (§ 519, canon of C); applicability according to the criteria of victim status and standing (§ 520). Application: the association satisfies the three conditions, also because the individual applicants did not have access to a court (§§ 521-526); the four women do not (§§ 527-535); art. 2 is not examined (§§ 536-537).

Merits of Art. 8 (§§ 538-574). Recapitulation of environmental principles (§§ 538-541). Climate protection weighs considerably (§ 542). Differentiated margin (§ 543, canon of D). The right and the duty: «Accordingly, the State’s obligation under Article 8 is to do its part to ensure such protection. In this context, the State’s primary duty is to adopt, and to effectively apply in practice, regulations and measures capable of mitigating the existing and potentially irreversible, future effects of climate change.» (§ 545). Preventing temperature increases beyond harmful levels (§ 546); each State defines its own pathway (§ 547); substantial and progressive reduction towards neutrality «within, in principle, the next three decades», and «it is incumbent on the public authorities to act in good time, in an appropriate and consistent manner» (§ 548); «in order for this to be genuinely feasible, and to avoid a disproportionate burden on future generations, immediate action needs to be taken and adequate intermediate reduction goals must be set for the period leading to net neutrality.» (§ 549); the five requirements (§ 550, canon of E); overall assessment (§ 551); adaptation (§ 552); procedural guarantees (§§ 553-554). Application: mitigation alone suffices (§ 555); the 2011 CO2 Act with minus 20% by 2020, already insufficient for the Federal Council in 2009, and the target missed with approximately minus 11% (§§ 558-559); revision rejected at the referendum of June 2021 and a gap after 2024 (§§ 560-562); 2021 NDC and the Climate Act of 30 September 2022, confirmed on 18 June 2023 but not in force, without concrete measures and with 2025-2030 uncovered (§§ 563-568); balance: the association's estimate (0.44 Gt of CO2 for a 67% probability of staying within 1.5 degrees, § 569), the Government does not have one and «the Court is not convinced that an effective regulatory framework concerning climate change could be put in place without quantifying, through a carbon budget or otherwise, national GHG emissions limitations» (§ 570); Neubauer and the indicative budgets of the European Climate Law (§ 571); conclusion on the budget (§ 572). Conclusion: «By failing to act in good time and in an appropriate and consistent manner regarding the devising, development and implementation of the relevant legislative and administrative framework, the respondent State exceeded its margin of appreciation and failed to comply with its positive obligations in the present context.» (§ 573). Violation (§ 574).

Art. 6 (§§ 575-640). Recapitulation of the principles (§§ 590-607): art. 6 does not guarantee a court that can annul laws (§ 594). In the climate context the principles remain but apply according to the specific circumstances (§ 608): no action to compel Parliament to legislate (§ 609); a future harm «real and highly probable» need not be strictly imminent, and this applies especially to associations (§ 614). Application: the part of the claim concerning the implementation of measures already provided for by law falls within art. 6 (§§ 615-616, canon of the reservation); the association has a direct and sufficient link with the rights of its members (§§ 618, 621-623); for the individual applicants the outcome was not directly decisive (§§ 624-625). Merits: the Swiss courts did not examine the scientific evidence nor the association's standing (§§ 635-636), no other avenue (§ 637), «its right of access to a court was restricted in such a way and to such an extent that the very essence of the right was impaired.» (§ 638); «the Court considers it essential to emphasise the key role which domestic courts have played and will play in climate-change litigation» (§ 639). Violation (§ 640).

Arts. 13, 41 and 46 (§§ 641-657). Art. 13 absorbed for the association (§ 644). 80,000 euros for costs (§ 650). Art. 46: «the Court is unable to be detailed or prescriptive as regards any measures to be implemented in order to effectively comply with the present judgment.» (§ 657), given the differentiated margin of § 543.

Dissenting opinion of Judge Eicke (pp. 235-260). He dissents on the method and limits of evolutive interpretation, on the extension of victim status and standing, and on the «creazione» of a new right under art. 8 (citing §§ 519, 544 and 545); he votes for a violation of art. 6 with different reasoning (p. 235). It has its own numbering: a «§ 4» or a «§ 30» of Eicke is not a paragraph of the judgment.

### 1.3 Legal basis

Convention: Article 8 (sole merits criterion), Article 34 (victim status and standing), Article 6 § 1, Article 1 (jurisdiction, embedded emissions), Articles 13, 41, 46. International law as interpretive context: UNFCCC (Article 3 § 1 on common but differentiated responsibilities, Article 3 § 3 on precaution: §§ 442, 444), Paris Agreement (Article 2 § 2, global goals that «cannot of themselves suffice as a criterion», § 547), Glasgow Climate Pact and Sharm el-Sheikh Implementation Plan (§ 442), ILC Articles on Responsibility (Article 47, § 443), Aarhus Convention (§§ 490-494, 501, 602), Resolution 76/300 on the right to a healthy environment (§ 448). Science: the IPCC reports (§§ 103-120, 429, 436), with the carbon budgets at § 116. Its own case-law relied upon: Câmpeanu and Gorraiz Lizarraga (associations), Tătar, Di Sarno, Jugheli, Hardy and Maile, Cordella, Hatton (environment), O'Keeffe and Baljak (real prospect), Zubac (access to court), H.F. v. France (Article 46). National case-law cited in the assessment: only Neubauer, at § 571 (and §§ 253 and 257 at § 441); Urgenda appears in the comparative part (§§ 260-261) but not in the assessment [verified by searching for «Urgenda» in §§ 410-657: no occurrence].

### 1.4 The seven probes

> **Distinctive probes (the PI, 01/10/2026).** A probe is the element PROPER to the judgment, that which distinguishes it from other sources: it serves to recognise its origin when an act reproduces it. For this reason, F is no longer «ogni Stato risponde della propria quota» (as stated by Urgenda, Neubauer and § 442 itself) but the causal criterion of § 444, the real possibility of changing the outcome; and H is no longer the review by the courts in general but its intergenerational foundation, § 420. §§ 410-413, 419, 421, 439-443, 449-451 and 639 remain without a probe.

| Probe | Ring | Paragraphs | Canonical | Page |
|---|---|---|---|---|
| victim_high_threshold (A) | d | §§ 479-488, 527-535 | § 527 | 199 |
| standing_associations (B) | d | §§ 489-503, 521-526 | § 502 | 193 |
| art8_effective_protection (C) | e | §§ 435-436, 478, 519-520, 544-546, 552 | § 519 (bis § 545) | 198 (206) |
| differentiated_margin (D) | f, l | §§ 542-543, 551, 553-554, 657 | § 543 | 205 |
| regulatory_framework_requirements (E) | g, h | §§ 547-550, 555, 558-573 | § 550 | 207 |
| real_possibility (F) | c | § 444 | § 444 | 178 |
| intergenerational_perspective (H) | b | § 420 | § 420 | 171 |
| reservation: access_to_court_association (G) | i | §§ 608-625, 629-638 | § 616 | 223 |

The ranges do not overlap. Why certain paragraphs are where they are:

- §§ 435-436 and 478 go to art. 8 (C) and not to the general part or to victim status: § 519 expressly refers to them as the foundation of the right («see paragraphs 435, 436 and 478 above»), and § 545 refers to §§ 435 and 519.
- § 499 remains with the associations (B), although its central sentence concerns the merits (States must also protect those who will be affected in the future): the opening and conclusion concern standing. In the corpus it is also cited for urgency, together with § 436 (Greenpeace Nordic v. Norway, ECtHR). Question to the PI.
- § 551 (overall assessment) and §§ 553-554 (procedural guarantees) go to the margin (D): both are formulated by the Court as a measure of compliance with the margin («overstepped its relevant margin», § 551; «especially material in determining whether the respondent State has remained within its margin of appreciation», § 553).
- § 657 goes to the margin (D): the reason for not indicating measures is the «differentiated margin of appreciation» of § 543.
- § 639 (role of national judges in climate litigation) remains without a probe: it says nothing specific to the judgment.
- §§ 439-443 (tenuous link, own share, concurrent responsibility) remain without a probe: the own share is from Urgenda. Probe F is only § 444. § 440 (threshold of risk gravity) remains without a probe.

Axes not promoted to probes, but to be recognised: the tailored approach (§§ 414-418, 422); the evidence and weight of the IPCC (§§ 427-434); art. 2 (§§ 507-513, 536-537); embedded emissions (§§ 279-287); access to court (reservation G). The recapitulations (§§ 460-477, 514-518, 538-541, 590-607, 626-628, 652-656) carry no probes: they summarise previous case law.

### 1.5 Boundary points

- Victims: women are NOT victims (§§ 533-535). Their belonging to a particularly exposed group «would not, in itself, be sufficient» (§ 531). Those who cite the case to say that elderly women are climate victims are wrong; those who cite it for the high threshold cite it correctly.
- Associations: standing as representatives, not as victims (§§ 496, 498). The association cannot invoke its own health (§ 496).
- Art. 2: not examined (§ 537). § 513 is a conditional principle («ought also to trigger»), not a decision.
- No figures: the Court does not say by how much to reduce nor which budget (§§ 550, 572, 657). Those who write that the Court imposed a budget or a percentage on Switzerland are wrong; the figures in §§ 558-569 are Swiss facts or estimates by the association.
- Margin: reduced only on targets; on means it remains wide (§ 543), even after a referendum (§ 561). Those who cite the case to say that the State no longer has any margin in climate matters cite it wrongly.
- Jurisdiction: embedded emissions do not raise an issue of extraterritorial jurisdiction (§ 287). The extraterritorial issue is decided in Duarte Agostinho, not here.
- Art. 6: only for the implementation of measures already provided for by law, not for requests to legislate (§§ 615-616). Only for the association (§§ 623-625).

## 2. The map of paragraphs

To decipher a precise reference. The complete, machine-readable map is in `klimaseniorinnen-mappa-paragrafi.yaml` (111 entries, all paragraphs 1-657 plus the operative part and separate opinion).

### 2.1 How to read a reference

- Numbers from 1 to 657 = paragraphs of the judgment. The forms observed in the corpus: «§ 550», «§§ 487-488», «§550, 570 and 573», «para. 543», «paras. 439 to 444», «¶ 545», «párr. 429», «par. 431», «r.o. 420» (rechtsoverweging, in Dutch texts), «Rn. 550» (German briefs), «bodu 542» (Czech), «at [507]–[509]» (New Zealand, Australia). Abbreviated ranges: «§§ 487-88» = 487-488.
- Wide ranges («§§ 410-51», «paras 436–574», «§§ 133-231») cite a section, not a principle: in `conta_paragrafi.py` they are counted separately (references «puntuali» = at most 15 paragraphs).
- The French version has the same numbering [not verified in the corpus: French is not present].
- Eicke's concurring opinion has its own small numbers; the printed pages of the judgment (1-232) are the PDF page minus 2.
- References to Duarte Agostinho (§§ 1-230 approx.) and Carême, decided on the same day, often appear in the same footnote: a «§ 213» after «Duarte» belongs to Duarte. The script truncates the window at the name of another case.
- Recurring errors: «53600/02» and «53600:20» (in the case file itself), «Klirnaseniorinnen» (OCR, Uniterre).
- Before 9/4/2024, a reference to paragraphs cannot concern the judgment: it concerns the application, the observations, or the Swiss judgments.

### 2.2 Essential table

| §§ | Pages | Content | Probe |
|---|---|---|---|
| 1-409 | 10-167 | Procedure, facts, applicable law, arguments of the parties and interveners | none |
| 410-413 | 168-169 | Climate as an urgent issue; complementarity between courts and democracy | - |
| 414-418, 422-423 | 169-172 | Differences from classic environmental damage; tailored approach | none |
| 419-421 | 170-171 | Polycentric problem; intergenerational perspective and judicial review | H only § 420 |
| 424-434 | 172-175 | Causation, evidence, IPCC, living instrument | none |
| 435-436 | 175 | Art. 8 and risks; facts assumed by the Court | C |
| 437-438, 440 | 175-176 | Causation and positive obligations; threshold of severity | none |
| 439, 441-444 | 176-178 | Tenuous link; own share; «drop in the ocean» | F only § 444 |
| 445-448 | 178-179 | No right to the environment as such | none |
| 449-451 | 179-180 | Law and politics; competence not excluded | - |
| 452-477 | 180-186 | Interpretation; general principles on victims and associations | none |
| 478 | 186 | Legally relevant causal link | C |
| 479-488 | 186-189 | Victim status in climate: two criteria, high threshold | A |
| 489-503 | 189-194 | Standing of associations: three conditions | B |
| 504-518 | 194-198 | Objections; Art. 2 in climate; Art. 8 (recapitulation) | none |
| 519-520 | 198 | Right to effective protection under Art. 8 | C |
| 521-526 | 198-199 | Application: the association has standing | B |
| 527-535 | 199-201 | Application: the four women are not victims | A |
| 536-541 | 201-205 | Art. 2 not examined; environmental principles (recapitulation) | none |
| 542-543 | 205 | Weight of climate protection; differentiated margin | D |
| 544-546 | 205-206 | Law, «do its part», primary duty of mitigation | C |
| 547-550 | 206-207 | Own pathway, three decades, intermediate targets, five requirements | E |
| 551 | 207 | Overall assessment | D |
| 552 | 207-208 | Adaptation | C |
| 553-554 | 208 | Procedural guarantees | D |
| 555, 558-573 | 208-213 | Application and conclusion on Art. 8 | E |
| 574 | 213 | Violation of Art. 8 | none |
| 575-607, 626-628 | 213-226 | Art. 6: arguments and general principles | none |
| 608-625, 629-638 | 221-228 | Art. 6 in climate and application | reserve G |
| 639 | 228-229 | Key role of national courts | - |
| 640-656 | 229-231 | Violation of Art. 6; Arts. 13, 41, 46 | none |
| 657 | 232 | No specific measure, differentiated margin | D |

## 3. The most frequently reused sentences, verbatim

All from the English text `judgment_f4b1`, found with only spaces normalized.

1. § 519, p. 198: «Article 8 must be seen as encompassing a right for individuals to effective protection by the State authorities from serious adverse effects of climate change on their life, health, well-being and quality of life.»
2. § 545, p. 206: «Accordingly, the State’s obligation under Article 8 is to do its part to ensure such protection. In this context, the State’s primary duty is to adopt, and to effectively apply in practice, regulations and measures capable of mitigating the existing and potentially irreversible, future effects of climate change.»
3. § 543, p. 205 (last two sentences): «As regards the former aspect, the nature and gravity of the threat and the general consensus as to the stakes involved in ensuring the overarching goal of effective climate protection through overall GHG reduction targets in accordance with the Contracting Parties’ accepted commitments to achieve carbon neutrality, call for a reduced margin of appreciation for the States. As regards the latter aspect, namely their choice of means, including operational choices and policies adopted in order to meet internationally anchored targets and commitments in the light of priorities and resources, the States should be accorded a wide margin of appreciation.»
4. § 550 (a), p. 207: «adopt general measures specifying a target timeline for achieving carbon neutrality and the overall remaining carbon budget for the same time frame, or another equivalent method of quantification of future GHG emissions, in line with the overarching goal for national and/or global climate-change mitigation commitments».
5. § 549, p. 207: «in order for this to be genuinely feasible, and to avoid a disproportionate burden on future generations, immediate action needs to be taken and adequate intermediate reduction goals must be set for the period leading to net neutrality.»
6. § 570, p. 212: «the Court is not convinced that an effective regulatory framework concerning climate change could be put in place without quantifying, through a carbon budget or otherwise, national GHG emissions limitations».
7. § 488, p. 189: «The threshold for fulfilling these criteria is especially high.»
8. § 442, p. 177: «The Court considers that a respondent State should not evade its responsibility by pointing to the responsibility of other States, whether Contracting Parties to the Convention or not.»
9. § 444, p. 178: «what is important, and sufficient to engage the responsibility of the State, is that reasonable measures which the domestic authorities failed to take could have had a real prospect of altering the outcome or mitigating the harm».
10. § 436, p. 175: «there are sufficiently reliable indications that anthropogenic climate change exists, that it poses a serious current and future threat to the enjoyment of human rights guaranteed under the Convention, that States are aware of it and capable of taking measures to effectively address it».
11. § 451, p. 180: «the question is no longer whether, but how, human rights courts should address the impacts of environmental harms on the enjoyment of human rights».
12. § 573, p. 213: «By failing to act in good time and in an appropriate and consistent manner regarding the devising, development and implementation of the relevant legislative and administrative framework, the respondent State exceeded its margin of appreciation and failed to comply with its positive obligations in the present context.»

## 4. The world around: competing sources and who cites them

### 4.1 Urgenda (Rechtbank 2015, Gerechtshof 2018, Hoge Raad 2019)

Summarised at §§ 260-261, not cited in the assessment. The same conclusions in another form: positive obligations under Articles 2 and 8 against climate risk (the Urgenda principle on positive obligations, close to C); its own share (the Urgenda principle of its own share, Hoge Raad 5.7.5-5.7.8: now NOT a probe of this case, F is only § 444). Clear differences: in Urgenda the court sets the minimum (25% by 2020); here the Court sets nothing and leaves a wide margin on the means. A text saying «each country is responsible for its own share» citing the Hoge Raad is ANOTHER_SOURCE; with «drop in the ocean», «real prospect» or «common but differentiated responsibilities» and § 442 or 444 it is KlimaSeniorinnen.

### 4.2 Neubauer (BVerfG, 24 March 2021)

Summarised at §§ 254-257 with the official headnotes; cited in the assessment at § 571 (carbon budget, Rn. 215-229) and referred to at § 441 (reference to §§ 253 and 257). Two affinities: the national budget (the Neubauer principle on the remaining budget, against E), and the institutional reason for review (Neubauer Rn. 206, electoral cycles and generations without a voice, against H). In the Neubauer file (4.2) KlimaSeniorinnen is already marked as a false friend: the two folders must say the same thing from opposite sides.

### 4.3 Duarte Agostinho v. Portugal and 32 States; Carême v. France (ECtHR, GC, 9 April 2024)

Same composition, same day (§ 5), both inadmissible. KlimaSeniorinnen cites Duarte at §§ 287 and 442-443. Duarte cites KlimaSeniorinnen for §§ 410-422, 487-488, 544-554 (references found in the corpus); Carême for §§ 487-488 (victim status). Those applying the two criteria by citing Carême take up KlimaSeniorinnen in nested form. The denial of extraterritorial jurisdiction is from Duarte, not from this judgment.

### 4.4 The Swiss judgment (DETEC 2017, Federal Administrative Court A-2992/2017, Federal Supreme Court 1C_37/2019)

In the corpus under its own case_id (11 documents), excluded. Its arguments (popular action, not affected more than the rest of the population, there is still time) are those that the Court rejects (§§ 618, 635). A text that sets them out takes up the opposite polarity.

### 4.5 The ECtHR after 9 April 2024

In the corpus, they cite the judgment with paragraph references: Greenpeace Nordic v. Norway (judgment, 25 references: §§ 436 and 499, 502, 527, 543, 550, 554, 555), Engels v. Germany (§ 519), De Conto v. Italy and Uricchio v. Italy (§§ 487-88, 513), Müllner v. Austria (communicated case: §§ 460-472, 478-488, 527-535, 538-574, 594-640), the application Klimatická žaloba ČR v. Czech Republic (§§ 502, 541, 546, 549, 550, 573, 619). They are taken up by the same court: they count as a FOLLOW-UP if the Court adopts the principle.

### 4.6 National courts and national acts

With references to paragraph (script count): Greenpeace Netherlands and eight residents of Bonaire v. Netherlands (decision 51 references, brief 25; almost all probes), the two briefs by Greenpeace and Germanwatch to the Federal Constitutional Court (§§ 538, 543, 550, 569, 573 among others), Steinmetz and others v. Germany III (Rn. 473, 475, 479, 490, 498 among others), Milieudefensie v. ING (§§ 420, 434, 436, 439-444, 478, 519), Hugues Falys and others v. TotalEnergies (§§ 410, 412, 429, 436, 439-440, 444, 546-553, 571-574), Uniterre v. DATEC (§§ 439, 478, 496, 502, 573), Asmania v. Holcim (§ 435), Coolglass v. An Bord Pleanála (§ 573), Smith v. Attorney-General (§§ 439, 507-509, 573), Aurora, Anton Foley v. Sweden (§§ 594, 607-609, 627), Klimatická žaloba ČR (Municipal Court of Prague, § 542), Poslední generace v. Prague (§ 499), We Are Nature Brussels (§ 462), Liao and others and Lee and others (Taiwan, §§ 434, 442, 548, 550, 569), Denman (Australia, «at [315], [444]», «at [415]-[417]»). The outcomes of these proceedings have not been verified for this file.

### 4.7 Advisory opinions

The requests and documents of the advisory opinions of the African Court, the Inter-American Court (OC-32/25), and the International Court of Justice cite the judgment: §§ 410, 420, 429, 431, 436, 442, 444, 499, 519, 545-552 among others. Whether the opinions themselves take it up and how [not verified in the corpus for this file].

### 4.8 IPCC, UNFCCC, Paris, Aarhus

The IPCC is the source of the facts (§§ 103-120, 429, 436): whoever cites IPCC data cites the IPCC. Common but differentiated responsibilities derive from the UNFCCC and Paris (§ 442): ANOTHER_SOURCE if the text does not use its own share within the meaning of § 442. The broad standing of environmental NGOs derives from Aarhus and EU law (§§ 490-494), which the Court uses as a reference but does not apply (§ 501).

## 5. How to recognise a revival

### 5.1 Strong indications

- Name, 53600/20, ECLI, «Verein KlimaSeniorinnen», «Aînées pour le climat», or a form of `klimaseniorinnen.yaml`; «the Strasbourg Court» or «ECtHR» dated 9/4/2024 in a climate context.
- A paragraph of the table without a name: decipher it with 2.1.
- The formulas in section 3: «high intensity of exposure», «pressing need to ensure ... individual protection», «especially high», «genuinely qualified and representative», «effective protection by the State authorities from serious adverse effects of climate change», «do its part», «primary duty», «reduced margin» with «wide margin» and the objectives/means pair, «overall remaining carbon budget» with «equivalent method of quantification», «intermediate ... reduction targets and pathways», «act in good time, in an appropriate and consistent manner», «disproportionate burden on future generations», «drop in the ocean» with «real prospect», «no longer whether, but how».
- Two or more rings in the order of the judgment (victim status and standing, then Article 8, then margin of appreciation, then requirements).

### 5.2 False friends

Urgenda (Arts. 2 and 8, own share, minimum set by the court); Neubauer (national carbon budget, intertemporal freedom, future generations without a voice); Duarte Agostinho (jurisdiction, exhaustion); Carême (same victim criteria, applied: nested); the Court's environmental case law (Tătar, Cordella, Hatton, Jugheli: positive obligations, wide margin); Aarhus and the CJEU (standing of NGOs); IPCC (figures and budgets); UNFCCC and Paris (differentiated responsibilities, thresholds). Polarity: those who set out the rejected arguments (actio popularis, no individual effect, there is still time, «drop in the ocean», no method for the budget, only a political path) do not take up the judgment; those who reject them in the words of the judgment do.

### 5.3 Uncertain cases

- Carbon budget after 9/4/2024: with «overall remaining carbon budget», «or another equivalent method of quantification», the five requirements or 53600/20 is KlimaSeniorinnen; with «remaining national CO2 budget», «albeit not precisely quantifiable», «special duty of care» it is Neubauer.
- Future generations: with «disproportionate burden on future generations» and intermediate targets it is E; with «short-term interests» and «judicial review» it is H; with «intertemporal guarantees of freedom» it is Neubauer; with the rights-holding capacity of posterity it is Colombia.
- Vulnerability of elderly women to heat (§§ 510-511, 529-530): recognized fact, not principle. Without the criteria of § 487 it is not A.
- «Do its part»: it is § 545 (C). A text using it to say that each State is responsible for its own share even if small must be read under F.

### 5.4 Mediated reliance

§ 571 is expressly based on Neubauer (paras. 215-229): whoever relies on the national carbon budget from there relies on Neubauer in nested form, and this must be stated. § 442 is based on Duarte Agostinho §§ 202-03 (same day). In the opposite direction: Carême, Duarte, Greenpeace Nordic, De Conto, Uricchio, Engels and Müllner rely on KlimaSeniorinnen; whoever relies on the criteria from them relies on KlimaSeniorinnen in nested form. The two decisions of the Committee of Ministers on execution (6 March 2025 and 17 September 2025) repeat the formula of § 545 but are acts of the case, excluded.

### 5.5 Who is speaking

In the judgment, the parties also speak (§§ 298-364) and the interveners (§§ 365-409): a reference to those paragraphs restates a thesis, not the Court. Judge Eicke's dissent is a dissenting voice. The summary on pp. 1-2 and the press release are from the Registry («Does not bind the Court»). The three rules of the group of 23/9/2026 on what counts as a restatement apply (Neubauer file, 5.6): it counts even if the same reason is applied to an undertaking, even if it is put forward by a party or an intervener, even if the court summarises it as a party's argument, always stating who advances it.

## Not verified in the corpus

- The French text of the judgment (official as is the English) and therefore the French wording of the probes.
- «Anziane per il clima» as the Italian name of the association and the other forms PROVIDED FOR in `klimaseniorinnen.yaml`.
- The dates and outcomes of the judgments in the corpus listed in 4.5-4.7, read here only for the references to paragraphs.
- Whether the 2025 advisory opinions (ICJ, Inter-American Court) take up the judgment in the final text and in which paragraphs.
- That the French version has the same paragraph numbering.
