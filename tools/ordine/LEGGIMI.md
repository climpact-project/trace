# Gli strumenti di TRACE in ordine di lettura (02/10/2026)

I file veri stanno in `tools/` col loro nome: gli script si importano l'uno con l'altro, e in Python un nome che comincia con un numero non si importa. Qui ogni voce numerata e' un collegamento al file vero; si puo' anche lanciare da qui.

## 1. Il corpus: dal PDF al testo, OCR, indice delle pagine

- `001_build_markdown.py`
- `002_diagnosi_testo.py`
- `003_ripara_ocr.py`
- `004_pdf_ricercabili.py`
- `005_applica_ocr.py`
- `006_posizione_dopo_ocr.py`
- `007_build_chunks.py`
- `008_build_index.py`
- `009_riaggancia_frammenti.py`
- `010_indice_pagine.py`

## 2. Il caso citato: sonde, mappa dei paragrafi, forme del nome

- `011_sonde.py`
- `012_principi_da_paragrafi.py`
- `013_controlla_mappe.py`
- `014_aggiorna_formulazioni.py`
- `015_formulazioni_provenienza.py`

## 3. La ricerca per nome e le righe in piattaforma

- `016_cerca.py`
- `017_estrai_citazioni.py`
- `018_unisci_e_aggiungi.py`
- `019_cerca_in_ocr.py`
- `020_pubblica.py`
- `021_assegna_codici.py`
- `022_coda_uptakes.py`

## 4. Il tipo di citazione (lettura L03 di DeepSeek)

- `023_giudica_llm.py`
- `024_classifica_lessicali.py`
- `025_carica_lessicali.py`

## 5. Il principio ripreso e le pagine attorno (TRACE-Reranker, letture L04 e L05)

- `026_prepara_training.py`
- `027_prova_riordinatori.py`
- `028_ripresa_punteggi.py`
- `029_coppie_ocr.py`
- `030_prepara_l05.py`
- `031_leggi_ripresa.py`
- `032_leggi_l04.py`
- `033_leggi_seguito.py`
- `034_freni.py`
- `035_carica_ripresa.py`

## 6. I controlli

- `036_controllo_completezza.py`
- `037_controllo_finestra.py`
- `038_controllo_scarti.py`
- `039_freni_prova.py`
- `040_salva_giudizi.py`

## 7. Le riprese senza il nome (ricerca semantica, lettura L06)

- `041_distilla.py`
- `042_semantica2.py`
- `043_unisci_candidati.py`

## 8. Le misure: sonde, stabilita'

- `044_prova_sonde_reranker.py`
- `045_prova_sonde_alternative.py`
- `046_confronta_sonde.py`
- `047_stabilita_deepseek.py`

## 9. Registro, risultati, mappa, diario

- `048_registro_versioni.py`
- `049_calcola_risultati.py`
- `050_carica_archivio.py`
- `051_aggiorna_dati_mappa.py`
- `052_traduci_mappa.py`
- `053_pacchetto_pagina_trace.py`
- `054_diario_pagina.py`

## 10. I cicli automatici (launchd sul Mac, coda di ReCaS)

- `055_ciclo_casi_nuovi.sh`
- `056_ciclo_p05.sh`
- `057_ciclo_p09_cig.sh`
- `058_ciclo_semantica_casi_nuovi.sh`
- `059_ciclo_ocr3.sh`
- `060_ciclo_ocr3_rifai.sh`
- `061_ciclo_giapponese.sh`
- `062_ciclo_cal.py`
- `063_carica_blocco.py`

## 11. Storia: prove e modelli di luglio-settembre, non piu' nella pipeline (l'addestramento dei modelli T01 e T03 e' qui)

- `064_addestra_categoria.py`
- `065_addestra_citazioni.py`
- `066_addestra_primo_qwen.py`
- `067_addestra_recupero.py`
- `068_addestra_riordino.py`
- `069_audit_giudizi.py`
- `070_cal_dati.py`
- `071_cal_riordinatore.py`
- `072_cartella_condivisa.py`
- `073_cartella_ricerca_manuale.py`
- `074_catalogo_e5_indice.py`
- `075_catalogo_parziale.py`
- `076_categoria_llm.py`
- `077_cerca_pagine.py`
- `078_combina_lettori.py`
- `079_confronta_lettori.py`
- `080_confronta_modelli.py`
- `081_confronta_posti.py`
- `082_coppie_citazioni.py`
- `083_crea_prova.py`
- `084_decisore_osservazioni.py`
- `085_deepseek_api.py`
- `086_deepseek_giro2.py`
- `087_deepseek_giro3.py`
- `088_deepseek_tutto.py`
- `089_dimensioni.py`
- `090_fase2_urgenda.py`
- `091_finestra_coppie_remoto.py`
- `092_gara_jina.py`
- `093_gara_modelli.py`
- `094_gara_parte2.py`
- `095_gara_terza.py`
- `096_giudica_deepseek.py`
- `097_gpu_costruisci.sh`
- `098_leggi_l06.py`
- `099_misura_finestra.py`
- `100_notte.sh`
- `101_pausa_semantiche.py`
- `102_prepara_distilla_ds.py`
- `103_prova_cieca.py`
- `104_prova_implicita.py`
- `105_prova_pipeline_primo.py`
- `106_prova_prefissi.py`
- `107_prova_recupero_grande.py`
- `108_prova_unita.py`
- `109_puntamento.py`
- `110_quanto_leggere.py`
- `111_reader.py`
- `112_rivedi_altrove.py`
- `113_rivedi_dopo_l05.py`
- `114_scrivi_revisione.py`
- `115_settembre_in_uptakes.py`
- `116_sezioni_atto.py`
- `117_sezioni_llm.py`
