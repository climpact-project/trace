# TRACE

**Tracing how climate judgments are taken up in later litigation.** TRACE is developed by the CLIMPACT project (University of Bari).

This repository holds the code, the case files, the codebook and the registry of versions behind TRACE. It is a research release under active development. It is private until the release of TRACE 0.1 (12 October 2026) and opens with it.

## What TRACE does

For any climate judgment (the *cited case*; so far Urgenda, Neubauer and Future Generations), TRACE finds every later filing that cites it and records, for each citation, what the citing text does with it. Every step has a version code (see below).

1. **Documents (D01).** The Climate Litigation Database, read through its public API, with the text of every page.
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
| D | data | D01 the database snapshot (public API) |
| S | name search | S01 first version (replaced), S02 corrected (in use) |
| R | rules without a model | R01 paragraph map, R02 composition, R03 choice of the nearby pages to read |
| L | readings by an external model | L01 (replaced), L02 Urgenda, L03 Neubauer and Future Generations, L04 uptake reading (the principles), L05 uptake reading with the dossier (continuation, quotations, supported sentence), L06 experiment (not in use), L07 continuation reread on the proposed principles |
| T | models trained by the project | T01 TRACE-Reranker 0.1, T02 TRACE-Reader v0, T03 TRACE-Reader v1 |

`versioni/registro.json` lists every version with its base model and revision, fingerprints, training data, settings, instructions and code, what changed from the previous version, and whether it is in use. Every proposal on a citation carries the code of the version that made it; every judgment records who decided, when, with which codebook, and what the person was shown. Model cards: `MODEL-CARDS.md`. The registry is the single source: where this README, the model cards or the public page differ from it, the registry is right.

## Contents

- `tools/`: **start here.** The pipeline, every file numbered in reading order: corpus and OCR, the cited case (probes, paragraph map), name search, type of citation, principle taken up and surrounding pages, checks, uptakes without the name, measurements, registry and publication, the automatic cycles, and the history of earlier experiments (list below and in `tools/LEGGIMI.md`). Updated on 2 October 2026: six cited cases (Urgenda, Neubauer, Future Generations, KlimaSeniorinnen, the ICJ climate advisory opinion, IACtHR OC-32/25), OCR of unreadable pages, probe tests, the stability of the external reader, the semantic search for uptakes without the name.
- `cited-cases/`: for each cited case, the forms of its name and its principles (the case file, `*.yaml`; series of probes in `*-P0N.yaml`), the dossier given to the reader (`*-fascicolo.md`) and the paragraph map (`*-mappa-paragrafi.yaml`).
- `codebook/citazioni.yaml`: the coding categories and the rules for hard cases (version 0.4-pilot: ten pages before and ten after the citation, the «surrounding pages»).
- `versioni/`: the registry of versions and, for each version, the copies of its instructions and code. The instructions are the exact texts given to the models where they were saved at run time; where a text is reconstructed the entry says so (`reconstructed`). The SHA-256 fingerprints in the registry are those of the executed files.

Code comments are in Italian, the working language of the team, as are the instructions given to the language models, the case files and the codebook.

## The tools in reading order

Every file in `tools/` carries its number in reading order, by phase (`tools/LEGGIMI.md`). On the team's machine the same files run without the number (the running cycles call them by name); here the imports are rewritten for the numbered names (`tools/046_pubblica_repo.py` does it), and the frozen copies in `versioni/` keep the names they ran with.


**1. Il corpus: dal PDF al testo, OCR, indice delle pagine**

1. [`001_build_markdown.py`](tools/001_build_markdown.py)
2. [`002_diagnosi_testo.py`](tools/002_diagnosi_testo.py)
3. [`003_ripara_ocr.py`](tools/003_ripara_ocr.py)
4. [`004_pdf_ricercabili.py`](tools/004_pdf_ricercabili.py)
5. [`005_applica_ocr.py`](tools/005_applica_ocr.py)
6. [`006_posizione_dopo_ocr.py`](tools/006_posizione_dopo_ocr.py)
7. [`007_build_chunks.py`](tools/007_build_chunks.py)
8. [`008_build_index.py`](tools/008_build_index.py)
9. [`009_riaggancia_frammenti.py`](tools/009_riaggancia_frammenti.py)
10. [`010_indice_pagine.py`](tools/010_indice_pagine.py)

**2. Il caso citato: sonde, mappa dei paragrafi, forme del nome**

11. [`011_sonde.py`](tools/011_sonde.py)
12. [`012_principi_da_paragrafi.py`](tools/012_principi_da_paragrafi.py)
13. [`013_controlla_mappe.py`](tools/013_controlla_mappe.py)
14. [`014_aggiorna_formulazioni.py`](tools/014_aggiorna_formulazioni.py)
15. [`015_formulazioni_provenienza.py`](tools/015_formulazioni_provenienza.py)

**3. La ricerca per nome e le righe in piattaforma**

16. [`016_cerca.py`](tools/016_cerca.py)
17. [`017_estrai_citazioni.py`](tools/017_estrai_citazioni.py)
18. [`018_unisci_e_aggiungi.py`](tools/018_unisci_e_aggiungi.py)
19. [`019_cerca_in_ocr.py`](tools/019_cerca_in_ocr.py)
20. [`020_pubblica.py`](tools/020_pubblica.py)
21. [`021_assegna_codici.py`](tools/021_assegna_codici.py)
22. [`022_coda_uptakes.py`](tools/022_coda_uptakes.py)

**4. Il tipo di citazione (lettura L03 di DeepSeek)**

23. [`023_giudica_llm.py`](tools/023_giudica_llm.py)
24. [`024_classifica_lessicali.py`](tools/024_classifica_lessicali.py)
25. [`025_carica_lessicali.py`](tools/025_carica_lessicali.py)

**5. Il principio ripreso e le pagine attorno (TRACE-Reranker, letture L04 e L05)**

26. [`026_prepara_training.py`](tools/026_prepara_training.py)
27. [`027_prova_riordinatori.py`](tools/027_prova_riordinatori.py)
28. [`028_ripresa_punteggi.py`](tools/028_ripresa_punteggi.py)
29. [`029_coppie_ocr.py`](tools/029_coppie_ocr.py)
30. [`030_prepara_l05.py`](tools/030_prepara_l05.py)
31. [`031_leggi_ripresa.py`](tools/031_leggi_ripresa.py)
32. [`032_leggi_l04.py`](tools/032_leggi_l04.py)
33. [`033_leggi_seguito.py`](tools/033_leggi_seguito.py)
34. [`034_freni.py`](tools/034_freni.py)
35. [`035_carica_ripresa.py`](tools/035_carica_ripresa.py)

**6. I controlli**

36. [`036_controllo_completezza.py`](tools/036_controllo_completezza.py)
37. [`037_controllo_finestra.py`](tools/037_controllo_finestra.py)
38. [`038_controllo_scarti.py`](tools/038_controllo_scarti.py)
39. [`039_freni_prova.py`](tools/039_freni_prova.py)
40. [`040_salva_giudizi.py`](tools/040_salva_giudizi.py)

**7. Le riprese senza il nome (ricerca semantica, lettura L06)**

41. [`041_distilla.py`](tools/041_distilla.py)
42. [`042_semantica2.py`](tools/042_semantica2.py)
43. [`043_unisci_candidati.py`](tools/043_unisci_candidati.py)

**8. Le misure: sonde, stabilita'**

44. [`044_prova_sonde_reranker.py`](tools/044_prova_sonde_reranker.py)
45. [`045_prova_sonde_alternative.py`](tools/045_prova_sonde_alternative.py)
46. [`046_confronta_sonde.py`](tools/046_confronta_sonde.py)
47. [`047_stabilita_deepseek.py`](tools/047_stabilita_deepseek.py)

**9. Registro, risultati, mappa, diario**

48. [`048_registro_versioni.py`](tools/048_registro_versioni.py)
49. [`049_calcola_risultati.py`](tools/049_calcola_risultati.py)
50. [`050_carica_archivio.py`](tools/050_carica_archivio.py)
51. [`051_aggiorna_dati_mappa.py`](tools/051_aggiorna_dati_mappa.py)
52. [`052_traduci_mappa.py`](tools/052_traduci_mappa.py)
53. [`053_pacchetto_pagina_trace.py`](tools/053_pacchetto_pagina_trace.py)
54. [`054_diario_pagina.py`](tools/054_diario_pagina.py)
55. [`055_pubblica_repo.py`](tools/055_pubblica_repo.py)

**10. I cicli automatici (launchd sul Mac, coda di ReCaS)**

56. [`056_ciclo_casi_nuovi.sh`](tools/056_ciclo_casi_nuovi.sh)
57. [`057_ciclo_p05.sh`](tools/057_ciclo_p05.sh)
58. [`058_ciclo_p09_cig.sh`](tools/058_ciclo_p09_cig.sh)
59. [`059_ciclo_semantica_casi_nuovi.sh`](tools/059_ciclo_semantica_casi_nuovi.sh)
60. [`060_ciclo_ocr3.sh`](tools/060_ciclo_ocr3.sh)
61. [`061_ciclo_ocr3_rifai.sh`](tools/061_ciclo_ocr3_rifai.sh)
62. [`062_ciclo_giapponese.sh`](tools/062_ciclo_giapponese.sh)
63. [`063_ciclo_cal.py`](tools/063_ciclo_cal.py)
64. [`064_carica_blocco.py`](tools/064_carica_blocco.py)

**11. Storia: prove e modelli di luglio-settembre, non piu' nella pipeline (l'addestramento dei modelli T01 e T03 e' qui)**

65. [`065_addestra_categoria.py`](tools/065_addestra_categoria.py)
66. [`066_addestra_citazioni.py`](tools/066_addestra_citazioni.py)
67. [`067_addestra_primo_qwen.py`](tools/067_addestra_primo_qwen.py)
68. [`068_addestra_recupero.py`](tools/068_addestra_recupero.py)
69. [`069_addestra_riordino.py`](tools/069_addestra_riordino.py)
70. [`070_audit_giudizi.py`](tools/070_audit_giudizi.py)
71. [`071_cal_dati.py`](tools/071_cal_dati.py)
72. [`072_cal_riordinatore.py`](tools/072_cal_riordinatore.py)
73. [`073_cartella_condivisa.py`](tools/073_cartella_condivisa.py)
74. [`074_cartella_ricerca_manuale.py`](tools/074_cartella_ricerca_manuale.py)
75. [`075_catalogo_e5_indice.py`](tools/075_catalogo_e5_indice.py)
76. [`076_catalogo_parziale.py`](tools/076_catalogo_parziale.py)
77. [`077_categoria_llm.py`](tools/077_categoria_llm.py)
78. [`078_cerca_pagine.py`](tools/078_cerca_pagine.py)
79. [`079_combina_lettori.py`](tools/079_combina_lettori.py)
80. [`080_confronta_lettori.py`](tools/080_confronta_lettori.py)
81. [`081_confronta_modelli.py`](tools/081_confronta_modelli.py)
82. [`082_confronta_posti.py`](tools/082_confronta_posti.py)
83. [`083_coppie_citazioni.py`](tools/083_coppie_citazioni.py)
84. [`084_crea_prova.py`](tools/084_crea_prova.py)
85. [`085_decisore_osservazioni.py`](tools/085_decisore_osservazioni.py)
86. [`086_deepseek_api.py`](tools/086_deepseek_api.py)
87. [`087_deepseek_giro2.py`](tools/087_deepseek_giro2.py)
88. [`088_deepseek_giro3.py`](tools/088_deepseek_giro3.py)
89. [`089_deepseek_tutto.py`](tools/089_deepseek_tutto.py)
90. [`090_dimensioni.py`](tools/090_dimensioni.py)
91. [`091_fase2_urgenda.py`](tools/091_fase2_urgenda.py)
92. [`092_finestra_coppie_remoto.py`](tools/092_finestra_coppie_remoto.py)
93. [`093_gara_jina.py`](tools/093_gara_jina.py)
94. [`094_gara_modelli.py`](tools/094_gara_modelli.py)
95. [`095_gara_parte2.py`](tools/095_gara_parte2.py)
96. [`096_gara_terza.py`](tools/096_gara_terza.py)
97. [`097_giudica_deepseek.py`](tools/097_giudica_deepseek.py)
98. [`098_gpu_costruisci.sh`](tools/098_gpu_costruisci.sh)
99. [`099_leggi_l06.py`](tools/099_leggi_l06.py)
100. [`100_misura_finestra.py`](tools/100_misura_finestra.py)
101. [`101_notte.sh`](tools/101_notte.sh)
102. [`102_pausa_semantiche.py`](tools/102_pausa_semantiche.py)
103. [`103_prepara_distilla_ds.py`](tools/103_prepara_distilla_ds.py)
104. [`104_prova_cieca.py`](tools/104_prova_cieca.py)
105. [`105_prova_implicita.py`](tools/105_prova_implicita.py)
106. [`106_prova_pipeline_primo.py`](tools/106_prova_pipeline_primo.py)
107. [`107_prova_prefissi.py`](tools/107_prova_prefissi.py)
108. [`108_prova_recupero_grande.py`](tools/108_prova_recupero_grande.py)
109. [`109_prova_unita.py`](tools/109_prova_unita.py)
110. [`110_puntamento.py`](tools/110_puntamento.py)
111. [`111_quanto_leggere.py`](tools/111_quanto_leggere.py)
112. [`112_reader.py`](tools/112_reader.py)
113. [`113_rivedi_altrove.py`](tools/113_rivedi_altrove.py)
114. [`114_rivedi_dopo_l05.py`](tools/114_rivedi_dopo_l05.py)
115. [`115_scrivi_revisione.py`](tools/115_scrivi_revisione.py)
116. [`116_settembre_in_uptakes.py`](tools/116_settembre_in_uptakes.py)
117. [`117_sezioni_atto.py`](tools/117_sezioni_atto.py)
118. [`118_sezioni_llm.py`](tools/118_sezioni_llm.py)

## Limits

- **No agreement figure published so far is a blind measure.** The figures the platform computes (machine and team agree on the type in about 93% of judged rows, a proposed principle is confirmed in about 97%, a proposed continuation page in about 94%) come from judgments given with the machine's proposals visible on the screen: leaving a ticked principle ticked counts as agreement. They say how often people changed a proposal, not how often the machine is right. Rows shown without any proposal are being judged now, and a blind figure will be published only when that sample has a base.
- The rows judged by the principal investigator, used to compare the readings L04, L05 and L06, are not frozen (38 on 28 September, 43 on 30 September) and were judged with the proposals visible. Those comparisons are provisional.
- The models of 0.1 were trained on labels that are being corrected (T01) or on the external reader's readings (T02, T03). One cited judgment.

## Terms

One name for each thing, in every document of this release: **uptake** (the relation between a citation and the cited case) and **continuation** (a nearby page that carries the same uptake on); **version** for L02 or L05 (never «second reading») and **reading 1, reading 2** for the two readings of one row; **test rows** for the fixed evaluation set, **quotation** for the sentence copied from the page, **Tests** for the platform section, **experiment** for L06; **judged without proposals** for the one-in-five sample, **second opinion** for double coding, never «blind» alone; **external reader** for DeepSeek (codes L) and **TRACE-Reader** for T02 and T03, never «Reader» alone; **case file** for `cited-cases/*.yaml` and **dossier** for `*-fascicolo.md`; **principles** (the field `semantic_queries` keeps its technical name); **name search** for the step, **explicit citation** for what it finds; **composition (R02)** for the rule and **loading** for the act of writing; **run** for one execution of a tool.

## Data

The documents come from the Climate Litigation Database of the Sabin Center for Climate Change Law (Columbia Law School) with Climate Policy Radar, read through its public API (snapshot of 26 July 2026). The texts of the filings are not redistributed here. Data provided by the Sabin Center for Climate Change Law. Platform operated by Climate Policy Radar.

## Licence

Code: MIT (see `LICENSE`). Case files, codebook and registry: CC BY 4.0.

## Citation

Naglieri, G., Buono, E., Garofalo, C., Saracino, C., Dell'Atti, L. (2026). CLIMPACT TRACE 0.1: Traceable Reception and Attribution in Climate-law Evidence. CLIMPACT, University of Bari. Zenodo. DOI: [pending].
