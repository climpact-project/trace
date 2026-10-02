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

- `tools/ordine/`: **start here.** The tools in reading order, numbered by phase: corpus and OCR, the cited case (probes, paragraph map), name search, type of citation, principle taken up and surrounding pages, checks, uptakes without the name, measurements, registry and publication, the automatic cycles, and the history of earlier experiments. `LEGGIMI.md` lists them. Each numbered entry is the same file as in `tools/`.
- `tools/`: the pipeline, with the names the scripts import each other by (a Python module cannot start with a digit). Updated on 2 October 2026: six cited cases (Urgenda, Neubauer, Future Generations, KlimaSeniorinnen, the ICJ climate advisory opinion, IACtHR OC-32/25), OCR of unreadable pages, probe tests, the stability of the external reader, the semantic search for uptakes without the name.
- `cited-cases/`: for each cited case, the forms of its name and its principles (the case file, `*.yaml`; series of probes in `*-P0N.yaml`), the dossier given to the reader (`*-fascicolo.md`) and the paragraph map (`*-mappa-paragrafi.yaml`).
- `codebook/citazioni.yaml`: the coding categories and the rules for hard cases (version 0.4-pilot: ten pages before and ten after the citation, the «surrounding pages»).
- `versioni/`: the registry of versions and, for each version, the copies of its instructions and code. The instructions are the exact texts given to the models where they were saved at run time; where a text is reconstructed the entry says so (`reconstructed`). The SHA-256 fingerprints in the registry are those of the executed files.

Code comments are in Italian, the working language of the team, as are the instructions given to the language models, the case files and the codebook.

## The tools in reading order

Numbered by phase; each link opens the file in `tools/`. The same order is in `tools/ordine/` (numbered links) and inside the code archive.


**1. Il corpus: dal PDF al testo, OCR, indice delle pagine**

1. [`build_markdown.py`](tools/build_markdown.py)
2. [`diagnosi_testo.py`](tools/diagnosi_testo.py)
3. [`ripara_ocr.py`](tools/ripara_ocr.py)
4. [`pdf_ricercabili.py`](tools/pdf_ricercabili.py)
5. [`applica_ocr.py`](tools/applica_ocr.py)
6. [`posizione_dopo_ocr.py`](tools/posizione_dopo_ocr.py)
7. [`build_chunks.py`](tools/build_chunks.py)
8. [`build_index.py`](tools/build_index.py)
9. [`riaggancia_frammenti.py`](tools/riaggancia_frammenti.py)
10. [`indice_pagine.py`](tools/indice_pagine.py)

**2. Il caso citato: sonde, mappa dei paragrafi, forme del nome**

11. [`sonde.py`](tools/sonde.py)
12. [`principi_da_paragrafi.py`](tools/principi_da_paragrafi.py)
13. [`controlla_mappe.py`](tools/controlla_mappe.py)
14. [`aggiorna_formulazioni.py`](tools/aggiorna_formulazioni.py)
15. [`formulazioni_provenienza.py`](tools/formulazioni_provenienza.py)

**3. La ricerca per nome e le righe in piattaforma**

16. [`cerca.py`](tools/cerca.py)
17. [`estrai_citazioni.py`](tools/estrai_citazioni.py)
18. [`unisci_e_aggiungi.py`](tools/unisci_e_aggiungi.py)
19. [`cerca_in_ocr.py`](tools/cerca_in_ocr.py)
20. [`pubblica.py`](tools/pubblica.py)
21. [`assegna_codici.py`](tools/assegna_codici.py)
22. [`coda_uptakes.py`](tools/coda_uptakes.py)

**4. Il tipo di citazione (lettura L03 di DeepSeek)**

23. [`giudica_llm.py`](tools/giudica_llm.py)
24. [`classifica_lessicali.py`](tools/classifica_lessicali.py)
25. [`carica_lessicali.py`](tools/carica_lessicali.py)

**5. Il principio ripreso e le pagine attorno (TRACE-Reranker, letture L04 e L05)**

26. [`prepara_training.py`](tools/prepara_training.py)
27. [`prova_riordinatori.py`](tools/prova_riordinatori.py)
28. [`ripresa_punteggi.py`](tools/ripresa_punteggi.py)
29. [`coppie_ocr.py`](tools/coppie_ocr.py)
30. [`prepara_l05.py`](tools/prepara_l05.py)
31. [`leggi_ripresa.py`](tools/leggi_ripresa.py)
32. [`leggi_l04.py`](tools/leggi_l04.py)
33. [`leggi_seguito.py`](tools/leggi_seguito.py)
34. [`freni.py`](tools/freni.py)
35. [`carica_ripresa.py`](tools/carica_ripresa.py)

**6. I controlli**

36. [`controllo_completezza.py`](tools/controllo_completezza.py)
37. [`controllo_finestra.py`](tools/controllo_finestra.py)
38. [`controllo_scarti.py`](tools/controllo_scarti.py)
39. [`freni_prova.py`](tools/freni_prova.py)
40. [`salva_giudizi.py`](tools/salva_giudizi.py)

**7. Le riprese senza il nome (ricerca semantica, lettura L06)**

41. [`distilla.py`](tools/distilla.py)
42. [`semantica2.py`](tools/semantica2.py)
43. [`unisci_candidati.py`](tools/unisci_candidati.py)

**8. Le misure: sonde, stabilita'**

44. [`prova_sonde_reranker.py`](tools/prova_sonde_reranker.py)
45. [`prova_sonde_alternative.py`](tools/prova_sonde_alternative.py)
46. [`confronta_sonde.py`](tools/confronta_sonde.py)
47. [`stabilita_deepseek.py`](tools/stabilita_deepseek.py)

**9. Registro, risultati, mappa, diario**

48. [`registro_versioni.py`](tools/registro_versioni.py)
49. [`calcola_risultati.py`](tools/calcola_risultati.py)
50. [`carica_archivio.py`](tools/carica_archivio.py)
51. [`aggiorna_dati_mappa.py`](tools/aggiorna_dati_mappa.py)
52. [`traduci_mappa.py`](tools/traduci_mappa.py)
53. [`pacchetto_pagina_trace.py`](tools/pacchetto_pagina_trace.py)
54. [`diario_pagina.py`](tools/diario_pagina.py)

**10. I cicli automatici (launchd sul Mac, coda di ReCaS)**

55. [`ciclo_casi_nuovi.sh`](tools/ciclo_casi_nuovi.sh)
56. [`ciclo_p05.sh`](tools/ciclo_p05.sh)
57. [`ciclo_p09_cig.sh`](tools/ciclo_p09_cig.sh)
58. [`ciclo_semantica_casi_nuovi.sh`](tools/ciclo_semantica_casi_nuovi.sh)
59. [`ciclo_ocr3.sh`](tools/ciclo_ocr3.sh)
60. [`ciclo_ocr3_rifai.sh`](tools/ciclo_ocr3_rifai.sh)
61. [`ciclo_giapponese.sh`](tools/ciclo_giapponese.sh)
62. [`ciclo_cal.py`](tools/ciclo_cal.py)
63. [`carica_blocco.py`](tools/carica_blocco.py)

**11. Storia: prove e modelli di luglio-settembre, non piu' nella pipeline (l'addestramento dei modelli T01 e T03 e' qui)**

64. [`addestra_categoria.py`](tools/addestra_categoria.py)
65. [`addestra_citazioni.py`](tools/addestra_citazioni.py)
66. [`addestra_primo_qwen.py`](tools/addestra_primo_qwen.py)
67. [`addestra_recupero.py`](tools/addestra_recupero.py)
68. [`addestra_riordino.py`](tools/addestra_riordino.py)
69. [`audit_giudizi.py`](tools/audit_giudizi.py)
70. [`cal_dati.py`](tools/cal_dati.py)
71. [`cal_riordinatore.py`](tools/cal_riordinatore.py)
72. [`cartella_condivisa.py`](tools/cartella_condivisa.py)
73. [`cartella_ricerca_manuale.py`](tools/cartella_ricerca_manuale.py)
74. [`catalogo_e5_indice.py`](tools/catalogo_e5_indice.py)
75. [`catalogo_parziale.py`](tools/catalogo_parziale.py)
76. [`categoria_llm.py`](tools/categoria_llm.py)
77. [`cerca_pagine.py`](tools/cerca_pagine.py)
78. [`combina_lettori.py`](tools/combina_lettori.py)
79. [`confronta_lettori.py`](tools/confronta_lettori.py)
80. [`confronta_modelli.py`](tools/confronta_modelli.py)
81. [`confronta_posti.py`](tools/confronta_posti.py)
82. [`coppie_citazioni.py`](tools/coppie_citazioni.py)
83. [`crea_prova.py`](tools/crea_prova.py)
84. [`decisore_osservazioni.py`](tools/decisore_osservazioni.py)
85. [`deepseek_api.py`](tools/deepseek_api.py)
86. [`deepseek_giro2.py`](tools/deepseek_giro2.py)
87. [`deepseek_giro3.py`](tools/deepseek_giro3.py)
88. [`deepseek_tutto.py`](tools/deepseek_tutto.py)
89. [`dimensioni.py`](tools/dimensioni.py)
90. [`fase2_urgenda.py`](tools/fase2_urgenda.py)
91. [`finestra_coppie_remoto.py`](tools/finestra_coppie_remoto.py)
92. [`gara_jina.py`](tools/gara_jina.py)
93. [`gara_modelli.py`](tools/gara_modelli.py)
94. [`gara_parte2.py`](tools/gara_parte2.py)
95. [`gara_terza.py`](tools/gara_terza.py)
96. [`giudica_deepseek.py`](tools/giudica_deepseek.py)
97. [`gpu_costruisci.sh`](tools/gpu_costruisci.sh)
98. [`leggi_l06.py`](tools/leggi_l06.py)
99. [`misura_finestra.py`](tools/misura_finestra.py)
100. [`notte.sh`](tools/notte.sh)
101. [`pausa_semantiche.py`](tools/pausa_semantiche.py)
102. [`prepara_distilla_ds.py`](tools/prepara_distilla_ds.py)
103. [`prova_cieca.py`](tools/prova_cieca.py)
104. [`prova_implicita.py`](tools/prova_implicita.py)
105. [`prova_pipeline_primo.py`](tools/prova_pipeline_primo.py)
106. [`prova_prefissi.py`](tools/prova_prefissi.py)
107. [`prova_recupero_grande.py`](tools/prova_recupero_grande.py)
108. [`prova_unita.py`](tools/prova_unita.py)
109. [`puntamento.py`](tools/puntamento.py)
110. [`quanto_leggere.py`](tools/quanto_leggere.py)
111. [`reader.py`](tools/reader.py)
112. [`rivedi_altrove.py`](tools/rivedi_altrove.py)
113. [`rivedi_dopo_l05.py`](tools/rivedi_dopo_l05.py)
114. [`scrivi_revisione.py`](tools/scrivi_revisione.py)
115. [`settembre_in_uptakes.py`](tools/settembre_in_uptakes.py)
116. [`sezioni_atto.py`](tools/sezioni_atto.py)
117. [`sezioni_llm.py`](tools/sezioni_llm.py)

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
