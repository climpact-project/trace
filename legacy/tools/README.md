# The TRACE tools in reading order (2 October 2026)

English companion of [`LEGGIMI.md`](LEGGIMI.md), the Italian index of these scripts. The scripts themselves are kept
exactly as they ran for the TRACE 0.1 data, so their comments, messages and prompts are in Italian, the working
language of the team (see [A note on language](../../README.md#a-note-on-language) for the glossary). The file names
stay Italian; the English meaning is given next to each.

Every file carries its number in the reading order. On the team's Mac the same files have the name without the number
(the running chains call them by that name); here the imports are rewritten for the numbered names, and the copies of
the registry in `versioni/` keep the names they had when they ran.

## 1. The corpus: from PDF to text, OCR, page index

| File | Meaning |
|---|---|
| `001_build_markdown.py` | build the page-marked Markdown from the PDFs |
| `002_diagnosi_testo.py` | diagnosis of the extracted text |
| `003_ripara_ocr.py` | repair OCR |
| `004_pdf_ricercabili.py` | searchable PDFs |
| `005_applica_ocr.py` | apply the OCR text |
| `006_posizione_dopo_ocr.py` | position of the rows after OCR |
| `007_build_chunks.py` | build chunks |
| `008_build_index.py` | build the index |
| `009_riaggancia_frammenti.py` | reattach fragments |
| `010_indice_pagine.py` | page index |

## 2. The cited case: probes, paragraph map, forms of the name

| File | Meaning |
|---|---|
| `011_sonde.py` | probes (the principles of a case) |
| `012_principi_da_paragrafi.py` | principles from paragraphs |
| `013_controlla_mappe.py` | check the maps |
| `014_aggiorna_formulazioni.py` | update the formulations |
| `015_formulazioni_provenienza.py` | provenance of the formulations |

## 3. The name search and the rows on the platform

| File | Meaning |
|---|---|
| `016_cerca.py` | search |
| `017_estrai_citazioni.py` | extract citations |
| `018_unisci_e_aggiungi.py` | merge and add |
| `019_cerca_in_ocr.py` | search in OCR text |
| `020_pubblica.py` | publish (to the platform) |
| `021_assegna_codici.py` | assign codes |
| `022_coda_uptakes.py` | queue of the Uptakes |

## 4. The type of citation (L03 reading by DeepSeek)

| File | Meaning |
|---|---|
| `023_giudica_llm.py` | judge with the language model |
| `024_classifica_lessicali.py` | classify the lexical rows |
| `025_carica_lessicali.py` | load the lexical rows |

## 5. The principle taken up and the surrounding pages (TRACE-Reranker, readings L04 and L05)

| File | Meaning |
|---|---|
| `026_prepara_training.py` | prepare the training data |
| `027_prova_riordinatori.py` | test the rerankers |
| `028_ripresa_punteggi.py` | uptake scores |
| `029_coppie_ocr.py` | OCR pairs |
| `030_prepara_l05.py` | prepare L05 |
| `031_leggi_ripresa.py` | read the uptake |
| `032_leggi_l04.py` | read L04 |
| `033_leggi_seguito.py` | read the continuation |
| `034_freni.py` | brakes (checks on the answers) |
| `035_carica_ripresa.py` | load the uptake |

## 6. The checks

| File | Meaning |
|---|---|
| `036_controllo_completezza.py` | completeness check |
| `037_controllo_finestra.py` | window check |
| `038_controllo_scarti.py` | check of the discards |
| `039_freni_prova.py` | brakes test |
| `040_salva_giudizi.py` | save the judgments |

## 7. Uptake without the name (semantic search, L06 reading)

| File | Meaning |
|---|---|
| `041_distilla.py` | distil |
| `042_semantica2.py` | semantic search, second version |
| `043_unisci_candidati.py` | merge candidates |

## 8. The measures: probes, stability

| File | Meaning |
|---|---|
| `044_prova_sonde_reranker.py` | test the probes with the reranker |
| `045_prova_sonde_alternative.py` | test alternative probes |
| `046_confronta_sonde.py` | compare probes |
| `047_stabilita_deepseek.py` | stability of DeepSeek |

## 9. Registry, results, map, diary

| File | Meaning |
|---|---|
| `048_registro_versioni.py` | registry of versions |
| `049_calcola_risultati.py` | compute results |
| `050_carica_archivio.py` | load the archive |
| `051_aggiorna_dati_mappa.py` | update the data of the map |
| `052_traduci_mappa.py` | translate the map |
| `053_pacchetto_pagina_trace.py` | package for the TRACE page |
| `054_diario_pagina.py` | diary page |
| `055_pubblica_repo.py` | publish the repository |

## 10. The automatic cycles (launchd on the Mac, ReCaS queue)

| File | Meaning |
|---|---|
| `056_ciclo_casi_nuovi.sh` | cycle for new cases |
| `057_ciclo_p05.sh` | cycle for probes P05 |
| `058_ciclo_p09_cig.sh` | cycle for probes P09, ICJ |
| `059_ciclo_semantica_casi_nuovi.sh` | semantic cycle for new cases |
| `060_ciclo_ocr3.sh` | OCR cycle 3 |
| `061_ciclo_ocr3_rifai.sh` | OCR cycle 3, redone |
| `062_ciclo_giapponese.sh` | Japanese cycle |
| `063_ciclo_cal.py` | calibration cycle |
| `064_carica_blocco.py` | load a block |

## 11. History: tests and models of July to September, no longer in the pipeline (the training of models T01 and T03 is here)

| File | Meaning |
|---|---|
| `065_addestra_categoria.py` | train the category model |
| `066_addestra_citazioni.py` | train on citations |
| `067_addestra_primo_qwen.py` | train the first Qwen |
| `068_addestra_recupero.py` | train retrieval |
| `069_addestra_riordino.py` | train the reranker |
| `070_audit_giudizi.py` | audit of the judgments |
| `071_cal_dati.py` | calibration data |
| `072_cal_riordinatore.py` | calibration of the reranker |
| `073_cartella_condivisa.py` | shared folder |
| `074_cartella_ricerca_manuale.py` | folder for manual search |
| `075_catalogo_e5_indice.py` | e5 catalogue index |
| `076_catalogo_parziale.py` | partial catalogue |
| `077_categoria_llm.py` | category by language model |
| `078_cerca_pagine.py` | search pages |
| `079_combina_lettori.py` | combine readers |
| `080_confronta_lettori.py` | compare readers |
| `081_confronta_modelli.py` | compare models |
| `082_confronta_posti.py` | compare places |
| `083_coppie_citazioni.py` | citation pairs |
| `084_crea_prova.py` | create a test |
| `085_decisore_osservazioni.py` | decision maker on observations |
| `086_deepseek_api.py` | DeepSeek API |
| `087_deepseek_giro2.py` | DeepSeek, round 2 |
| `088_deepseek_giro3.py` | DeepSeek, round 3 |
| `089_deepseek_tutto.py` | DeepSeek, everything |
| `090_dimensioni.py` | dimensions |
| `091_fase2_urgenda.py` | phase 2, Urgenda |
| `092_finestra_coppie_remoto.py` | window of pairs, remote |
| `093_gara_jina.py` | contest: Jina |
| `094_gara_modelli.py` | contest: models |
| `095_gara_parte2.py` | contest: part 2 |
| `096_gara_terza.py` | contest: third |
| `097_giudica_deepseek.py` | judge with DeepSeek |
| `098_gpu_costruisci.sh` | build on the GPU |
| `099_leggi_l06.py` | read L06 |
| `100_misura_finestra.py` | measure the window |
| `101_notte.sh` | the night run |
| `102_pausa_semantiche.py` | pause the semantic rows |
| `103_prepara_distilla_ds.py` | prepare distillation from DeepSeek |
| `104_prova_cieca.py` | blind test |
| `105_prova_implicita.py` | implicit uptake test |
| `106_prova_pipeline_primo.py` | first pipeline test |
| `107_prova_prefissi.py` | prefix test |
| `108_prova_recupero_grande.py` | large retrieval test |
| `109_prova_unita.py` | unit test |
| `110_puntamento.py` | pointing |
| `111_quanto_leggere.py` | how much to read |
| `112_reader.py` | reader |
| `113_rivedi_altrove.py` | review elsewhere |
| `114_rivedi_dopo_l05.py` | review after L05 |
| `115_scrivi_revisione.py` | write the review |
| `116_settembre_in_uptakes.py` | September in the Uptakes |
| `117_sezioni_atto.py` | sections of a filing |
| `118_sezioni_llm.py` | sections by language model |
