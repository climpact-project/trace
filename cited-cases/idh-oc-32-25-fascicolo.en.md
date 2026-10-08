English translation of the Italian case file used by TRACE 0.1 (idh-oc-32-25-fascicolo.md, SHA-256 7244a97312d27c8b1f8d9db2eda8cb78158e88a2680bf60e9734359475313f6d), made on 7 October 2026 with DeepSeek V4 Flash and not yet checked by the research team.

# Case file for Advisory Opinion OC-32/25 (Inter-American Court, «Emergencia Climática y Derechos Humanos»)

1 October 2026, version 2, prepared by the research team from primary sources, with Claude Opus 5.5 as ancillary support (summarising, systematising and reordering), PROPOSAL for the PI, with the eight distinctive probes approved by the PI on the same day (the first series of seven probes is superseded). Sources used: the four versions of the opinion in the corpus (Spanish `decision_28df`, 234 pp.; Court's English `decision_3b51`, 219 pp.; second English version `decision_9329`, 234 pp.; Portuguese `opinion_2cd0`, 228 pp.), the other 39 documents in the request file (case_id `request-for-an-advisory-opinion-on-the-scope-of-the-state-obligations-for-responding-to-the-climate-emergency_fbcd`), Advisory Opinion OC-23/17 (`opinion_029c`), the ICJ opinion of 23 July 2025 (`decision_af16`, case_id `request-for-an-advisory-opinion-on-the-obligations-of-states-with-respect-to-climate-change_0213`), the KlimaSeniorinnen judgment, the Greenpeace Nordic v. Norway judgment, and the 74 documents in the corpus that name the opinion. Then `idh-oc-32-25.yaml` and `idh-oc-32-25-mappa-paragrafi.yaml` (same folder), the Future Generations file as a model of form, and the counts from `conta_paragrafi.py`. No human judgment, no training files. Every quotation in quotation marks was found in the corpus by normalizing only spaces; anything not found there is marked «[non verificato nel corpus]». Page = `<!-- page N -->` markdown marker, which coincides with the PDF page. Paragraphs = Court's numbers, identical in all languages.

## 0. What it is for and how to read it

You are given a passage from ANOTHER case. You must say whether it takes up a proposition of OC-32/25 (RIPRESA), whether it asserts something similar based on another source (ALTRA_FONTE), or whether it does not assert it (NON_AFFERMA). Links in the chain of argument, in the order in which the Court follows them:

- (a) fact: the climate emergency is established by science, urgent, serious and complex (§§ 42-216, point 1);
- (b) general obligations: respect, guarantee with debida diligencia reforzada, progressive development, domestic law, cooperation (§§ 217-265, points 2-6);
- (c) new or redefined substantive rights: Nature as subject of rights, the peremptory prohibition of irreversible harm to the common ecosystem, the right to a healthy climate (§§ 279-316, points 7-9);
- (d) mitigation obligations: target, strategy, enterprises, supervision, climate impact (§§ 321-363, point 10), then nature, sustainable development, adaptation (§§ 364-457, points 11-12);
- (e) procedural rights: democracy, science, information, participation, justice, defenders (§§ 458-587, points 13-18);
- (f) equality: vulnerable groups and poverty (§§ 588-629, points 19-20).

Four things to always keep in mind.

1. Much of what the opinion says comes from OC-23/17, and the Court says so. The right to a healthy environment as an autonomous right, its two dimensions, prevention, jurisdiction for transboundary harm are summarised at §§ 266-278 with reference to OC-23/17 and the judgments Lhaka Honhat, La Oroya, U'wa. Due diligence proportional to risk is OC-23/17 (§ 142, cited at § 232). By decision of the PI the probes carry ONLY what is specific to OC-32/25, so that whoever takes it up is recognisable as its debtor: the healthy climate as an autonomous right, the jus cogens of irreversible harm, Nature as subject of rights in Inter-American law, the debida diligencia reforzada, climate impact assessment, the right to science extended to traditional knowledge with the obligation to counter disinformation, the protection of cross-border climate displacement, the facilitated proof of the causal link. Cooperation, adaptation as an obligation, equality and the like are not probes.

2. In summer 2025 there are two opinions, and those who cite them almost always put them together. The IACtHR adopts its own on 29 May (published on 3 July), the ICJ its own on 23 July; ITLOS had spoken on 21 May 2024. The ICJ cites OC-32/25 as a block, without paragraph (§ 385, p. 119). Many memorials write «ICJ Climate AO, para. 136; IACtHR OC-32/25, para. 320». The lexicon distinguishes: «stringent due diligence» and «erga omnes» belong to the ICJ; «debida diligencia reforzada» or «enhanced due diligence» and «jus cogens» belong to the IACtHR.

3. The opinion is cited by its code, not by its title. The forms are in the case file. Two pitfalls. «OC-32» without a year also names the 2023 REQUEST («Solicitud de Opinión Consultiva OC-32», note 4 of the opinion, p. 7). «Climate Emergency and Human Rights» is also the title of the request and, translated, of a 2021 avis of the French CNCDH. For this reason the 3 July 2025 threshold must be applied to the date of the document (file prefix in `url_origine`), not to `data_deposito`, which is the date the case was initiated.

4. Reception in the corpus is currently concentrated in a single proceeding. Of the 511 paragraph references found, 490 come from the memorials to the African Court on Human and Peoples' Rights on the request for a climate advisory opinion (35 documents, February-May 2026). Outside that, the specific references are 21, in 8 cases. The probes must be measured with and without that proceeding.

## 1. The advisory opinion

### 1.1 What is in the corpus

Four versions, all with date 20250703 in the file name:

- `decision_28df`, Spanish original, 234 pp. «Redactada en español en San José, Costa Rica, el 29 de mayo de 2025» (p. 233). Source of the canonicals.
- `decision_3b51`, English translation, 219 pp., with its own pagination. Translates «debida diligencia reforzada» with «enhanced due diligence».
- `decision_9329`, second English version, 234 pp., with the same pagination as the Spanish and a different translation.
- `opinion_2cd0`, Portuguese version, 228 pp. In the corpus it bears `tipo_atto` from «opinion»: it is the opinion, not a separate vote.

The separate votes (three partially dissenting: Hernández López, Sierra Porto, Pérez Goldberg; four concurring: Mudrovitsch, Ferrer Mac-Gregor, Pérez Manrique, Gómez) are announced at p. 233 but are not in the corpus [not verified in the corpus]. A reference «Concurring Opinion, para. 83» points to one of them, not to the opinion.

The rest of the file: the application by Chile and Colombia of 9 January 2023 (`petition_1973`, Spanish; `petition_bb43`, English), the corrected application (`other_d40b`), dozens of written observations and amici from 2023-2024, and at least two written statements to the ICJ filed here by mistake (`other_7253`, `other_b14c`). The entire file is excluded from the search.

### 1.2 Structure

- I. Presentation (§§ 1-4, p. 5); II. Procedure (§§ 5-13): 263 written observations, hearings in Bridgetown, Brasilia and Manaus in 2024; III. Jurisdiction (§§ 14-23).
- IV. Preliminary considerations (§§ 24-41): subject matter and reformulation of the applications, structure, sources (science as a basis, systemic integration, §§ 33-38), scope.
- V. The climate emergency (§§ 42-216, pp. 16-83): causes, impacts, international response, OAS Member States' law, litigation (§§ 176-180), definition of emergency (urgency, gravity, complexity).
- VI. The obligations of the States (§§ 217-629, pp. 83-228): A general obligations (§§ 217-265); B substantive rights (§§ 266-457); C procedural rights (§§ 458-587); D equality (§§ 588-629).
- VII. Opinion (pp. 229-233): «decide» 1 on jurisdiction and twenty operative paragraphs, numbered separately.

### 1.3 Operative paragraphs, votes and probes

| Point | Content | Paragraphs cited | Vote | Probe |
|---|---|---|---|---|
| 1 | Climate emergency according to the best science | 183, 205-216 | unanimous | none (fact) |
| 2 | Duty of respect | 219-223 | unanimous | none |
| 3 | Guarantee with reinforced due diligence | 225-237 | unanimous | reinforced_diligence (only §§ 231-237) |
| 4 | DESCA, maximum available resources | 238-243 | 6-1 | none |
| 5 | Domestic law | 244-246 | unanimous | none |
| 6 | Cooperation | 247-265 | unanimous | none |
| 7 | Nature as subject of rights | 279-286 | 4-3 | nature_subject_of_rights (only §§ 279-283) |
| 8 | Jus cogens | 287-294 | 4-3 | jus_cogens_irreversible_harm |
| 9 | Healthy climate, collective dimension | 298-316 | 5-2 in part | healthy_climate_autonomous (§§ 297-304, 311-316) |
| 10 | Mitigation: target, strategy, enterprises; oversight; climate impact | 323-351; 352-357; 358-363 | 6-1 in part | climate_impact_assessment (§§ 350, 352-363) |
| 11 | Nature and sustainable development | 364-376 | unanimous | none |
| 12 | Adaptation | 384-391, 400-457 | 6-1 in part | climate_mobility (§§ 422-434) |
| 13 | Democracy | 460-469 | unanimous | none |
| 14 | Right to science and knowledge | 471-487 | 6-1 in part | science_disinformation (§§ 476-484) |
| 15 | Information | 501-527 | unanimous | science_disinformation (§§ 524-529) |
| 16 | Participation, prior consultation | 530-539 | unanimous | none |
| 17 | Access to justice | 542-560 | 4-3 in part | eased_evidence (only §§ 552-555) |
| 18 | Environmental defenders | 566-567, 575-587 | unanimous | none |
| 19 | Poverty | 626-627 | unanimous | none |
| 20 | Vulnerable groups | 599-604, 606-618, 628-629 | 4-3 in part | none |

The operative paragraph indicates where a topic stands; the probe takes only the paragraphs that set out its specific element. Outside, within the same points, remain: the guarantee and precaution repeated from OC-23/17 (§§ 224-230), transboundary climate harm (§§ 295-296), intergenerational equity as a principle (§§ 305-310), the review of the rights of nature elsewhere (§§ 284-286), mitigation target and strategy (§§ 317-344), the corporate due diligence of the UN Guiding Principles (§§ 345-349, 351), the right to science in general and the criteria of the best science (§§ 471-475, 485-487), the facts on mobility (§§ 414-421), and the rest of access to justice (§§ 540-551, 556-560).

### 1.4 What each probe says

**healthy_climate_autonomous (§§ 297-304, 311-316).** As in La Oroya for air and water, from a healthy environment derives a right to a healthy climate (§ 297). It is a right «independiente» with «una base con entidad propia» (§ 300, p. 110, canonical). A healthy climate is that of a climate system free from dangerous anthropogenic interference (§ 300). Collective dimension: «el interés colectivo de las generaciones presentes y futuras de seres humanos y de otras especies» (§ 302, p. 111, canonical_bis), indivisible ownership, remedies for the benefit of present and future humanity and of Nature; individual dimension as a precondition of the other rights (§ 303). Equity enters only as part of the right: humanity as a community lasting over time, whose protection requires intra- and intergenerational equity (§§ 311-313). Nature protected by the healthy climate (§§ 314-316). Distinctive: the HEALTHY CLIMATE as a distinct right, first court to recognize it. Outside: §§ 305-310 (intergenerational equity as a principle, allocation of burdens among generations), taken from sources that the Court itself lists.

**jus_cogens_irreversible_harm (§§ 287-294).** The international community has identified conduct that irreversibly alters the balance of the common ecosystem: large-scale deforestation, massive loss of species, persistent pollution, alteration of biogeochemical cycles, climate change in its extreme forms (§ 288). Preserving that balance is «una condición sine qua non para la vigencia de todos los derechos humanos» (§ 293, p. 108). Therefore the prohibitions «tienen el carácter de jus cogens» (§ 291, p. 108, canonical), under the principle of effectiveness (§§ 292, 294), and all States must cooperate to bring violations to an end (§ 294). Decided 4-3. Distinctive, without precedent in the corpus: the ICJ speaks of erga omnes obligations for the climate system (§ 440), not of jus cogens.

**nature_legal_subject (§§ 279-283).** Recognizing ecosystems' own rights protects their integrity and functionality in the long term (§ 279). «Este reconocimiento permite superar concepciones jurídicas heredadas, que concebían a la Naturaleza exclusivamente como objeto de propiedad o recurso explotable» (§ 280, p. 102, canonical). It is compatible with Articles 2 and 26 and with the pro natura and pro persona principles (§ 281); it introduces nothing foreign to the inter-American corpus juris (§ 282); obligation to protect, restore and regenerate (§ 283). Decided 4-3. Distinctive: recognition as a development of inter-American law. Outside: §§ 284-286, review of the World Charter for Nature, the CBD, UN resolutions and the national trend (Ecuador, Atrato, Amazon, Brazilian municipal laws).

**heightened_due_diligence (§§ 231-237).** The obligation of guarantee is one of means and is measured by due diligence, a variable concept (§§ 231-232, with ITLOS). Given the available information, the extreme gravity and the urgency, the diligence must be HEIGHTENED (§ 233, p. 88, canonical; the Court's English «enhanced due diligence»). The risks are «en gran medida, previsibles» (§ 234). Section 236 lists its content: comprehensive risk assessment, «proactivas y ambiciosas» measures, best science, human rights perspective, monitoring, procedural rights, transparency, regulation of corporate due diligence, enhanced cooperation. Distinctive: the formula «reforzada» linked to the guarantee of human rights. Outside: §§ 224-230 (guarantee, prevention, precaution «aún en ausencia de certeza científica»), which repeat OC-23/17; and the «stringent due diligence» of ITLOS and the ICJ, which is another source.

**climate_impact_assessment (§§ 350, 352-363).** Differentiated obligations according to companies' current and historical contribution, stricter for major emitters (§ 350, p. 125, canonical_bis, the most cited paragraph). Strict oversight of emissive activities, public and private, at minimum fossil fuels, cement, agribusiness, and more demanding for companies with greater responsibility (§ 353); independent bodies, sanctions, corruption (§§ 354-357). Impact assessment: «aquellos proyectos o actividades que impliquen el riesgo de generar emisiones significativas de GEI deben ser sometidos a una evaluación de impacto climático» (§ 359, p. 127, canonical); greenwashing (§ 360); minimum content (§ 361). Distinctive: the CLIMATE impact as mandatory content of the EIA, derived from human rights, and differentiation by historical contribution. Outside: §§ 345-349 and 351 (corporate due diligence under the UN Guiding Principles, investment treaties), not distinctive. The ECtHR in Greenpeace Nordic transcribes §§ 353, 358-359 (see 4.11).

**science_disinformation (§§ 476-484, 524-529).** Alongside science there exist local, traditional and indigenous knowledge (§ 476). By evolutionary interpretation of Article 14 of the Protocol of San Salvador, the right to science also includes the benefits of that knowledge (§ 477, p. 174, canonical); everyone has the right to measures based on the best science and on the recognition of that knowledge (§ 478); the protection «se extiende también a los desarrollos intelectuales y prácticos» of indigenous peoples and communities (§ 483, p. 176); obligations to protect and collect them (§ 484). Disinformation: States «deben abstenerse de difundir información que no esté respaldada por la mejor ciencia disponible o por saberes locales, tradicionales o indígenas pertinentes» (§ 525, p. 190) and have the obligation of progressive measures to counter it (§ 527, p. 191, canonical_bis), without prior censorship; media and platforms (§§ 528-529). Distinctive: the right to science that INCLUDES traditional knowledge, and countering climate disinformation as a conventional obligation. Outside: the right to science in general (§§ 471-475, ICESCR) and the criteria of best science with the IPCC (§§ 485-487).

**mobilita_climatica (§§ 422-434).** States must prevent, with reinforced due diligence, migration and forced displacement caused by disasters and other climate impacts (§ 422); provide instruments for those in involuntary mobility (§ 424), with procedural rights (§ 425), adequate resettlement (§§ 426-427) and assistance (§ 428); «Las relocalizaciones solo deben ocurrir en circunstancias excepcionales» (§ 429, p. 152); cooperation (§§ 430-432). For those crossing a border: a domestic regulatory framework of legal and humanitarian protection (§ 433, p. 154, canonical), with humanitarian visas, temporary stays, «la protección bajo el estatus de refugiados u otros similares», «que les puedan brindar protección contra la devolución» (§ 433, p. 155); childhood in climate mobility processes (§ 434). Own: complementary protection and non-refoulement as a conventional obligation for cross-border climate displacement. Outside: art. 22 and facts (§§ 414-421).

**prova_agevolata (§§ 552-555).** The complexity of climate cases makes the strict application of evidentiary rules an obstacle (§ 552). Alternative evidentiary standards are needed for the causal link, based on the risk generated or tolerated and on exposure, «sin exigir necesariamente la prueba de un nexo causal directo», and the Court refers to «la posibilidad de presumir el nexo causal» between emissions and degradation of the climate system (§ 553, p. 200, canonical). Flexible interpretation of evidence and «la inversión de la carga probatoria» (§ 554, canonical_bis); satellite evidence (§ 555). Own: the presumption of the link between emissions, the climate system, and risks, as a standard for climate cases. Already elsewhere: the reversal of the burden of proof and the dynamic burden of proof in art. 8.3 of the Escazú Agreement (reported in the corpus from an observation to the file).

## 2. The map of paragraphs

The machine-readable map, in 80 entries covering §§ 1-629 without gaps, is in `idh-oc-32-25-mappa-paragrafi.yaml`.

### 2.1 How to recognise the reference

- «párr. 233», «párrs. 231-237», «para. 350», «paras 345-350», «¶ 234», «§ 547», «parágrafo 297», «Paragrafos 231-237»: paragraphs of the opinion, from 1 to 629, identical in all languages.
- «operative para 3», «operative clause», «punto resolutivo 8»: operative paragraphs of the Opinión (pp. 229-233), numbered 1-20. They are not paragraphs. «decide» 1 is jurisdiction.
- «Concurring Opinion, para. 120», «voto concurrente»: a separate opinion, not in the corpus.
- «p. 88», «at 84»: page. If the reference is to a page, check the version: the Spanish and `decision_9329` have 234 pages with the same pagination; the Court's translation (`decision_3b51`) has 219 and lags behind by up to 15 pages (§ 233: p. 88 ES, p. 84 EN; § 546: p. 198 ES, p. 186 EN).
- «Series A No. 32» / «Serie A No. 32»: the Court's official series; on its own it conflicts with Airey v. Ireland (ECtHR, 1979, «Series A no. 32»).
- «(n 31) at paras 321-322»: short OSCOLA cross-reference to a previous note. The script reads it only if the form of the opinion precedes the number; «ibid., para. 183» does not read it.
- «supra», «above»: internal cross-reference of the citing document («see paragraph 132 above» in the Greenpeace Nordic judgment is a paragraph of the judgment, not of the opinion).

### 2.2 Summary table

| Paragraphs | Section | Probe |
|---|---|---|
| 1-216 | presentation, procedure, jurisdiction, sources, facts | none |
| 217-230 | respect, guarantee, prevention, precaution | none |
| 231-237 | debida diligencia reforzada | diligenza_rafforzata |
| 238-278 | DESCA, domestic law, cooperation, healthy environment (OC-23/17 reiterated) | none |
| 279-283 | Nature as subject of rights | natura_soggetto_diritti |
| 284-286 | review of instruments and trend on the rights of nature | none |
| 287-294 | jus cogens | jus_cogens_dano_irreversible |
| 295-296 | climate system, transboundary harm | none |
| 297-304 | healthy climate | clima_sano_autonomo |
| 305-310 | intergenerational equity as a principle | none |
| 311-316 | present and future humanity, Nature | clima_sano_autonomo |
| 317-349 | coordination, mitigation goal and strategy, corporate due diligence | none |
| 350 | differentiated obligations of companies | valutazione_impatto_climatico |
| 351 | investment treaties | none |
| 352-363 | supervision, climate impact assessment | valutazione_impatto_climatico |
| 364-421 | nature, sustainable development, adaptation, art. 22 and facts on mobility | none |
| 422-434 | obligations on climate mobility | mobilita_climatica |
| 435-475 | adaptation by law, democracy, right to science in general | none |
| 476-484 | local, traditional and indigenous knowledge | scienza_disinformazione |
| 485-523 | best available science, information | none |
| 524-529 | disinformation | scienza_disinformazione |
| 530-551 | participation, access to justice up to standing | none |
| 552-555 | evidence | prova_agevolata |
| 556-629 | reparation, defenders, equality, vulnerable groups, poverty | none |

## 3. The most frequently quoted passages, verbatim

Spanish (`decision_28df`) and English of the Court (`decision_3b51`). In parentheses, the number of references in the corpus (01/10/2026).

- § 233 (17 references), p. 88, canonical of enhanced due diligence: «la Corte estima que los Estados deben actuar con una debida diligencia reforzada para cumplir con el deber de prevención derivado de la obligación de garantía». EN p. 84: «the Court finds that States must act with enhanced due diligence to comply with the obligation of prevention».
- § 234 (22 references), p. 88, within enhanced due diligence: «Conforme a los avances científicos, tanto estos riesgos como la magnitud y el carácter irreversible de los daños que pueden generar son, en gran medida, previsibles.»
- § 229 (14 references), p. 86, without probe (precaution from OC-23/17): «Este estándar se extiende tanto a la degradación del sistema climático global como a las violaciones de derechos humanos derivadas de ésta.» EN p. 82: «This standard extends to both the degradation of the global climate system and to the resulting human rights violations.»
- § 350 (22 references), p. 125: canonical_bis of climate impact assessment. EN p. 118: «Consequently, the Court considers that States should establish differentiated obligations with regard to climate action based on the actual and historical contribution of business enterprises to climate change, and impose stricter obligations on those whose activities are major sources of GHG emissions.»
- § 359 (13 references), p. 127, canonical of climate impact assessment: «En particular, aquellos proyectos o actividades que impliquen el riesgo de generar emisiones significativas de GEI deben ser sometidos a una evaluación de impacto climático.» EN p. 120: «In particular, those projects or activities that pose a risk of generating significant GHG emissions should be subject to a climate impact assessment.»
- § 291 (10 references), p. 108: canonical of jus cogens. EN p. 102: «The prohibitions arising from the obligation to preserve our common ecosystem, as a precondition to the enjoyment of other rights that have already been identified as fundamental, are of peremptory importance and are, therefore, of a jus cogens nature.»
- § 300, p. 110: canonical of a healthy climate. EN p. 104: «the Court considers that recognition of a human right to a healthy climate as an independent right».
- § 326, p. 118, without probe (mitigation target): EN p. 111: «this should be considered a minimum starting point, rather than the finishing line, when determining the mitigation target».
- § 546, p. 198, without probe (pro actione): EN p. 186: «judicial authorities must apply the pro actione principle with respect to the admissibility of actions, appeals filed, and requirements regarding standing».
- § 551, p. 199, without probe: «Por ende, este Tribunal resalta que la garantía del acceso a la justicia supone la legitimación activa de personas y entidades que no residan en el territorio del Estado.» EN p. 187: «Consequently, the Court stresses that the guarantee of access to justice involves the legal standing of people and entities that do not reside in the State’s territory.»
- § 280, p. 102: canonical of Nature. EN p. 97: «Recognition of Nature as a subject of rights also emphasizes its structural role in the vital balance of the conditions that make this planet inhabitable.»
- Without probe, § 566 (14 references), p. 203: the Court «reconoce la existencia de un “deber especial de protección” del Estado respecto de ellas» (environmental defenders).
- § 477, p. 174, canonical of science: «el “derecho a la ciencia” no solo comprende el acceso a beneficios que se deriven de la ciencia en sentido estricto». EN p. 163: «the Court considers that, according to an evolutionary interpretation, the “right to science” not only encompasses access to benefits obtained from science in the strict sense».
- § 527, p. 191: «los Estados tienen la obligación de adoptar medidas progresivas para contrarrestar la desinformación en materia climática». EN p. 179: «In this regard, States are required to adopt progressive measures to counter climate-related disinformation».
- § 433, p. 154, canonical of mobility: EN p. 145: «The Court considers that States must establish an appropriate regulatory framework that provides effective legal and/or administrative mechanisms at the domestic level to guarantee the legal and humanitarian protection of persons displaced across international borders due to the impacts of climate change.»
- § 553, p. 200, canonical of evidence: «la posibilidad de presumir el nexo causal». EN p. 187: «In this regard, the Court draws attention to the possibility of presuming the causal link between GHG emissions and the degradation of the climate system».
- § 554, p. 200: «la inversión de la carga probatoria». EN p. 187: «the adoption of appropriate measures – such as the reversal of the burden of proof – that allow effective access to justice to be guaranteed».

## 4. The world around: competing sources

### 4.1 IACtHR, OC-23/17, «Medio Ambiente y Derechos Humanos» (15 November 2017)

In the corpus (`a-request-for-an-advisory-opinion-from-the-inter-american-court-of-human-rights-concerning-the-interpretation-of-article-1-1-4-1-and-5-1-of-the-american-convention-on-human-rights-opinion_029c`). Right to a healthy environment as an autonomous right (§§ 62-64), due diligence proportional to the risk (§ 142), obligation to regulate, supervise and monitor (§§ 152-155). OC-32/25 cites it continuously and summarizes its doctrine in §§ 266-278. Rule: «ambiente sano diritto autonomo», «interdipendenza fra ambiente e diritti», «obblighi di prevenzione» without the proper climate element are OC-23/17, even if the text names OC-32/25. This is the most frequent confusion: a Brazilian act writes «Opinion Consultiva OC-32/25. Medio ambiente y derechos humanos en el contexto de la emergencia climatica» (Tenharim petition, p. 25), mixing the two titles.

### 4.2 The IACtHR judgments that the advisory opinion draws on

La Oroya v. Peru (2023: clean air and water, intergenerational equity, § 297 and § 305 of the advisory opinion), U'wa v. Colombia (2024: triple planetary crisis, § 317), Lhaka Honhat v. Argentina, Kawas Fernández v. Honduras (defenders, § 574). Whoever draws on these cases draws on the Court, but not on this advisory opinion [texts of the judgments not verified in the corpus].

### 4.3 ICJ, «Obligations of States in respect of Climate Change» (23 July 2025)

In the corpus (`request-for-an-advisory-opinion-on-the-obligations-of-states-with-respect-to-climate-change-decision_af16`). Due diligence «stringent» for NDCs and mitigation (§§ 138, 246), NDCs capable as a whole of achieving the Paris goals (§ 249), regulating private actors as a due diligence obligation (§ 428), erga omnes obligations for global commons such as the climate system (§ 440). It cites OC-32/25 once, as a block (§ 385, p. 119). Rule: «stringent», «erga omnes», NDCs as an instrument are the ICJ; «reforzada/enhanced», «jus cogens», «clima sano», «punto de partida mínimo» are the IACtHR.

### 4.4 ITLOS, opinion of 21/5/2024

Due diligence «stringent» for marine pollution from greenhouse gases; impact assessment (§ 367 of the ITLOS opinion, transcribed by the ECtHR in Greenpeace Nordic). OC-32/25 cites it at §§ 232 and 333 (notes 464 and 581).

### 4.5 ECtHR, KlimaSeniorinnen v. Switzerland (9/4/2024)

In the corpus. Standing of associations (§§ 502-503), requirements of the regulatory framework: timetable towards climate neutrality, carbon budget or equivalent method, intermediate targets (§ 550). OC-32/25 cites and adopts it at §§ 334-335 (strategy) and § 383 (adaptation). A binding target with budget and timetable is KlimaSeniorinnen if there is no MINIMUM threshold of 1.5 °C or the measure for historical contribution.

### 4.6 Escazú Agreement (2018, in force since 22/4/2021)

Broad standing (art. 8), environmental defenders (art. 9). The opinion cites it at §§ 464, 547, 564. Broad standing and protection of defenders based on Escazú are ANOTHER_SOURCE.

### 4.7 The national climate cases cited by the Advisory Opinion

§§ 176-180: in the text Urgenda, Friends of the Irish Environment, Neubauer, Notre Affaire à Tous, Grande-Synthe, Klimaatzaak, Leghari, Shrestha, Milieudefensie c. Shell; in the footnote KlimaSeniorinnen and Future Generations (STC4360-2018, notes 378 and 396; see the Future Generations file, 4.16). These are possible chains in both directions: a text may cite Neubauer through OC-32/25, or OC-32/25 alongside Neubauer.

### 4.8 Rights of nature elsewhere

Constitution of Ecuador (art. 71), T-622/2016 (Atrato), STC4360-2018 (Amazon), Te Awa Tupua, Mar Menor, Brazilian municipal laws (note 538 of the opinion). Sources of the trend that the opinion notes at § 286, not its further elaborations.

### 4.9 CNCDH, opinion «Urgence climatique et droits de l'homme» (27/5/2021)

Cited in the French proceedings against TotalEnergies and BNP Paribas and by the Korean Human Rights Commission. Same title as OC-32/25 in English («Climate emergency and human rights»), another body, another year. Guaranteed lexical false positive.

### 4.10 African Court, request for an advisory opinion on the climate obligations of African States

The proceeding that today cites OC-32/25 the most: 35 documents (observations by States, NGOs, amici; in the corpus 12 bear `tipo_atto: decisione`, a metadata defect in the file name), 490 references to 447 different paragraphs, February–May 2026. They cite almost the entire opinion, including the facts, and almost always alongside the ICJ. Entry `parte` or `amicus`, not `corte`.

### 4.11 Who cites OC-32/25 in the corpus

74 documents mention it outside the file (36 cases); 63 are dated after 3/7/2025 by file date (29 cases). The 11 earlier ones are false positives or refer to the request. With paragraph reference, after the threshold:

| Case | Document, date | References | Paragraphs | Probes touched |
|---|---|---|---|---|
| African Court, request for advisory opinion | 35 documents, 2/2026-5/2026 | 490 | 447 different | all except facilitated_evidence |
| Observatório do Clima v. IBAMA, Petrobras (Brazil, Amazon River mouth) | petition, 22/10/2025 | 5 | 223, 226, 229, 231-237, 335, 343-344 | heightened_due_diligence |
| Instituto Preservar, AGAPAN v. Union (Brazil, Rio Grande do Sul emergency) | decision, 22/8/2025 | 4 | 295, 299, 337, 547 | autonomous_healthy_climate |
| Instituto Aimara v. Piracicaba (Brazil) | initiating document, 1/2/2026 | 4 | 297, 556, 558, 559 | autonomous_healthy_climate |
| Lighthiser v. Trump (USA) | amicus, 20/1/2026 | 4 | 234 | heightened_due_diligence |
| Juliana, petition to the Inter-American Commission | 25/9/2025 | 1 | 540-541 | none |
| Tenharim Marmelos (Brazil) | initiating document, 30/9/2025 | 1 | 295 | none |
| Dunn v. Wisconsin PSC (USA) | reply, 22/12/2025 | 1 | 234 | heightened_due_diligence |
| Unconstitutionality request (Chile, deputies Melo Contreras and others) | 24/7/2025 | 1 | 543 | none |

The Bonaire judgment (Rechtbank Den Haag, 28/1/2026) cites § 327 in the short form «Advisory Opinion IACHR», now excluded by decision of the PI: the document remains among the citing parties, the reference is not counted.

It is mentioned without paragraph reference, among others: the ICJ (23/7/2025, § 385), the ECtHR in Greenpeace Nordic v. Norway (28/10/2025), the Supremo Tribunal Federal (ADI 7582, 19/12/2025), three Brazilian federal decisions on deforestation in the PAE Antimary (August-October 2025), the Samarco decision (19/12/2025), the Klimatická žaloba applications to the ECtHR (2026), Dykstra (Canada), Denman (Australia), Poelina (Australia), Venner v. EPA (USA).

Case to note: Greenpeace Nordic v. Norway (ECtHR, 28/10/2025). The judgment devotes a section to the advisory opinion (§§ 132-135): it cites §§ 45 and 47 on fossil fuel emissions, transcribes, in whole or in part, §§ 337, 353, 358 and 359, and at § 322 it takes up its climate impact assessment alongside the ITLOS and the EFTA Court. The automatic count does not see these reproductions, because they are transcriptions («“337. Given the urgency») and not references «para. 337». It is the most authoritative reproduction outside the African Court, and it touches the climate_impact_assessment probe (§§ 353, 358-359); § 337 is among the paragraphs without a probe.

## 5. How to recognize a resumption

### 5.1 Strong indications

- «derecho a un clima sano», «right to a healthy climate», «direito ao clima estável» (observed in the corpus) as a right distinct from a healthy environment.
- «jus cogens» or «norma imperativa» referring to irreversible damage to the common ecosystem or to ecological balance.
- Nature as a subject of rights as a development of Inter-American law, compatible with the Convention.
- «debida diligencia reforzada», «enhanced due diligence», «reinforced due diligence», «diligência reforçada», referring to the guarantee of human rights in the climate context.
- «evaluación de impacto climático», «climate impact assessment» as an autonomous obligation of the EIA; «obligaciones diferenciadas» of companies «basadas en la contribución actual e histórica».
- Right to science encompassing local, traditional and indigenous knowledge; duty to counter climate disinformation.
- Complementary protection, humanitarian visas, non-refoulement for those crossing a border due to climate change, inferred from regional human rights.
- Presumption of the causal link between emissions, degradation of the climate system and risks; alternative evidentiary standards without a direct link.
- Transcriptions of entire paragraphs with the number at the beginning («Eis o teor do § 547 da OC-32/25», «“359. Since the affectation»).

### 5.2 False friends

- Healthy environment as an autonomous right, collective dimension as «interés universal»: OC-23/17 (referred to in §§ 270-274).
- «stringent due diligence», NDC «highest possible ambition»: ICJ, ITLOS, Paris Agreement.
- «erga omnes» for the climate system: ICJ, § 440.
- Carbon budget and binding timeline: KlimaSeniorinnen, Neubauer.
- Nature as a subject of rights based on a constitution, a law, or a national court: Ecuador, Atrato, Amazon.
- Broad standing and protection of defenders based on Escazú.
- «Climate emergency and human rights» in a French act: the CNCDH opinion.
- «OC-32» in a 2023-2024 act: the request, not the opinion.

### 5.3 Uncertain cases

The submissions to the African Court often cite long blocks of paragraphs («paras. 393-457», «paras. 141-174 and 321») that span multiple probes or end up in the facts: a reference to a block does not indicate which principle is taken up. The Brazilian pleadings name «Opinião Consultiva 32» without a paragraph to support different arguments (dismissal with climate analysis, Samarco; due diligence, Syngenta): the passage must be read.

### 5.4 Mediated references

Through the ICJ (which cites OC-32/25 as a whole) and through the ECtHR (Greenpeace Nordic, which transcribes four paragraphs of it). A text that takes up the climate impact assessment by citing Greenpeace Nordic takes up OC-32/25 through Strasbourg.

### 5.5 Who speaks

The voices are those of the codebook: `corte`, `parte`, `amicus`. The observations to the African Court are acts by States, institutions and NGOs in an advisory procedure: voice `parte` or `amicus` depending on the author, not `corte`, even when the corpus labels them «decisione». The actual decisions citing the opinion today are few: ICJ, ECtHR, Rechtbank Den Haag (Bonaire), STF and Brazilian federal judges.

## Not verified in the corpus

- The separate opinions of the seven judges (announced at p. 233).
- The texts of the judgments La Oroya, U'wa, Lhaka Honhat, Kawas Fernández (cited by the opinion; not searched in the corpus for this file).
- The position of the opinion in the list of cases still pending before the Inter-American Court.
