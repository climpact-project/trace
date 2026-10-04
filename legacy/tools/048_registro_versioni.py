"""IL REGISTRO DELLE VERSIONI DI TRACE (28/09/2026, richiesta del PI).

   Ogni cosa che produce proposte o dati ha un codice corto (V00, V01, ..., D01) e una scheda con tutto quello che
   serve a verificarla: modello di partenza e revisione, impronte SHA-256 dei pesi, dati e data di addestramento,
   impostazioni, istruzioni (testo e impronta), codice (copia e impronta), codebook, programmi, macchina, misure.
   Le citazioni portano, accanto a ogni proposta, il codice della versione che l'ha prodotta (`provenienza`):
   il codice della citazione (URG-0146) dice QUALE citazione, i codici di versione dicono COME ci si e' arrivati.

   Copie: `versioni/<codice>/` contiene gli script e le istruzioni al momento della registrazione (sabin-corpus
   non e' sotto git). Le impronte si calcolano da queste copie. Sono copie esatte solo dove il testo e' stato salvato
   al momento della lettura: dove e' ricostruito o rigenerato dopo (L04; il testo di L02 e L03, che `modulo()` rifa'
   dai file di oggi) la voce `istruzioni` lo dice nel campo `ricostruita` (revisione del 30/09/2026, punto 3).

   NOMI UNICI (revisione del 30/09/2026, punto 10): nei testi del registro si usano SOLO le lettere (S02, L04...), mai
   i codici V, che restano nel campo `alias`. «Ripresa» e' la relazione fra citazione e caso; «seguito» e' la pagina
   vicina che la prosegue; «versione» per L02/L05 (mai «seconda lettura»), «lettura 1 / lettura 2» per le ripetizioni
   per riga; «righe di prova» per il test set, «citazione testuale» per la frase copiata, «esperimento» per L06;
   «senza proposte» (campione), «seconda opinione», «Test» (sezione), mai «cieco» da solo; DeepSeek V4 Flash
   (L) si chiama col suo nome, mai «lettore esterno» (04/10/2026), «TRACE-Reader» = T02/T03; «file del caso» = lo yaml, «fascicolo» = il dossier; «principi» e non
   sonde; «esecuzione» per un giro.

   Scrive su Firestore la collezione `trace_versioni` (lettura ai membri del Corpus, scrittura solo da qui).

   Uso:  .venv/bin/python tools/048_registro_versioni.py [--scrivi]
"""
import argparse, hashlib, json, pathlib, shutil, sys
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
VER = QUI/'versioni'

SOFTWARE_RECAS = {'torch': '2.14.0', 'transformers': '5.17.0', 'peft': '0.21.0', 'huggingface_hub': '1.33.0',
                  'openai (client)': '3.19.2', 'vLLM': '0.30.0 (immagine vllm/vllm-openai:v0.30.0)'}
MACCHINA = 'NVIDIA H100 80GB HBM3, cluster HTCondor ReCaS-Bari (INFN, Universita di Bari)'


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def sha_testo(t):
    return hashlib.sha256(t.encode('utf-8')).hexdigest()


def fisso(codice, *nomi):
    """Una copia GIA' salvata in versioni/<codice>/ (non si ricopia dai file di oggi, che sono cambiati dopo)."""
    return [{'file': f'versioni/{codice}/{n}', 'sha256': sha(VER/codice/n)} for n in nomi]


# LE COPIE SONO CONGELATE (01/10/2026). Fino a oggi ogni giro del registro ricopiava i file vivi nelle cartelle delle
# versioni: cosi' una versione del 28/09 finiva per contenere il codice cambiato il 01/10 (successo a L02, L03, L05, R02,
# R03; copie ricostruite, quelle sovrascritte in versioni/_sovrascritte-2026-10-01/). Ora una copia si scrive solo la
# prima volta; se il file vivo e' diverso lo si dice in CAMBIATI_DOPO, e una versione nuova si fa con un codice nuovo.
CAMBIATI_DOPO = []


def copia(codice, *file):
    d = VER/codice; d.mkdir(parents=True, exist_ok=True)
    out = []
    for f in file:
        f = QUI/f
        dest = d/f.name
        if not dest.exists():
            shutil.copy2(f, dest)
        elif sha(dest) != sha(f):
            CAMBIATI_DOPO.append(f'{codice}: {f.relative_to(QUI)}')
        out.append({'file': str(f.relative_to(QUI)), 'copia': str(dest.relative_to(QUI)), 'sha256': sha(dest)})
    return out


def salva_testo(codice, nome, testo):
    d = VER/codice; d.mkdir(parents=True, exist_ok=True)
    if not (d/nome).exists():
        (d/nome).write_text(testo, encoding='utf-8')
    elif (d/nome).read_text(encoding='utf-8') != testo:
        CAMBIATI_DOPO.append(f'{codice}: {nome} (testo rigenerato diverso dalla copia)')
    return {'file': f'versioni/{codice}/{nome}', 'sha256': sha(d/nome)}


def registro():
    CL = __import__('024_classifica_lessicali')
    LR = __import__('031_leggi_ripresa')
    R = []
    R.append({'codice': 'D01', 'tipo': 'corpus', 'nome': 'Climate Litigation Database, whole-database export',
              'compito': 'I documenti: atti, pagine, testo estratto. Tutte le citazioni vengono da qui.',
              'data': '2026-07-26', 'stato': 'in uso',
              'fonte': 'Sabin Center for Climate Change Law (Columbia Law School) con Climate Policy Radar, letto dalle API pubbliche',
              'versione': 'CCC-whole_data_dump-2026-07-26',
              'pesi': [{'file': 'CCC-whole_data_dump-2026-07-26.zip', 'sha256': sha(QUI/'CCC-whole_data_dump-2026-07-26.zip')}],
              'note': '16.791 atti, 569.218 pagine indicizzate. Testo estratto con OCR dove serve (METHODOLOGY.md).'})
    R.append({'codice': 'S01', 'tipo': 'regola', 'nome': 'Ricerca per nome, prima versione (con la rete semantica di luglio)',
              'compito': "Trova le citazioni (nome del caso nelle sue forme) ed estrae pagina e passaggio. Da qui vengono le righe e il passaggio mostrato.",
              'data': '2026-07-31',
              # Urgenda: il file di PRIMA del 29/09 (le forme coreana e giapponese sono di S02).
              # copie dei file dei casi di prima delle forme aggiunte con S02 (Urgenda, 29/09) e S03 (Neubauer, 01/10); Future
              # Generations e' invariato dal 23/09. I file esatti del giro di Urgenda del 3/09 non sono stati conservati.
              'istruzioni': fisso('S01', 'istruzioni/urgenda.yaml', 'istruzioni/neubauer.yaml', 'istruzioni/future-generations.yaml'),
              'stato': 'sostituita da S02 per le righe col nome (29/09/2026); la ricerca semantica di luglio e\' in pausa dal 27/09/2026',
              'note': "Le forme del nome stanno nei file dei casi (74 per Urgenda). Righe di Urgenda dall'esecuzione del 3/09, di Neubauer e Future Generations dal 23/09. Due difetti, corretti in S02: i filtri semantici (riordinatore, data) toccavano anche le righe 'entrambe' che nominano il caso; i riferimenti lunghi venivano spezzati in due righe."})
    R.append({'codice': 'S02', 'tipo': 'regola', 'nome': 'Ricerca per nome corretta',
              'compito': "Trova le citazioni col nome del caso. Nessun filtro semantico sulle righe col nome; un identificativo (numero di ruolo, ECLI, indirizzo web) vicino alla corrispondenza precedente continua la stessa citazione; forme coreana e giapponese di Urgenda.",
              'data': '2026-09-29', 'stato': 'sostituita da S03 il 01/10/2026 (le righe che ha aggiunto restano, con la loro provenienza)',
              # dal 01/10/2026 i file vivi sono quelli di S03: qui le copie di prima (forme e codice del 29/09)
              'istruzioni': fisso('S02', 'istruzioni/urgenda.yaml', 'istruzioni/neubauer.yaml', 'istruzioni/future-generations.yaml'),
              'codice_sorgente': fisso('S02', '016_cerca.py', '018_unisci_e_aggiungi.py', '021_assegna_codici.py'),
              'misure': [{'nome': 'righe aggiunte', 'valore': 'Urgenda 58, Neubauer 10, Future Generations 2'},
                         {'nome': 'righe unite (stessa citazione in due righe)', 'valore': 'Urgenda 9, Neubauer 33'},
                         {'nome': 'righe gia\' giudicate ritrovate', 'valore': 'tutte (Urgenda 380, Neubauer 12, Future Generations 5)'}],
              'note': "Le righe unite restano in banca dati con proposto_rete 'fusa' e fusa_in. Le righe aggiunte non hanno ancora le letture della macchina."})
    R.append({'codice': 'S03', 'tipo': 'regola', 'nome': 'Ricerca per nome sul testo OCR, con altre forme giapponesi e coreane',
              'compito': ("Come S02, su 158 pagine illeggibili rifatte con l'OCR in 7 documenti (coreano, cinese tradizionale, spagnolo). "
                          "Forme nuove: アージェンダ事件, アージェンダ財団 (Urgenda), ノイバウアー, 노이바우어 (Neubauer). Per le forme in giapponese, "
                          "cinese e coreano si ammette uno spazio o un a capo fra un carattere e l'altro (in quei testi l'a capo cade anche dentro "
                          "un nome); le forme latine restano esatte. Nei documenti rifatti la posizione delle righe vecchie si traduce nel testo "
                          "nuovo (006_posizione_dopo_ocr.py) invece di cambiarla, perche' fa parte dell'identificativo."),
              'data': '2026-10-01', 'stato': 'in uso: righe aggiunte in piattaforma',
              # le forme della ricerca: i file dei casi di quel momento (le sonde sono cambiate dopo, alle 9:45: P03)
              'istruzioni': fisso('S03', 'istruzioni/urgenda.yaml', 'istruzioni/neubauer.yaml', 'istruzioni/future-generations.yaml'),
              'codice_sorgente': copia('S03', 'tools/016_cerca.py', 'tools/018_unisci_e_aggiungi.py', 'tools/006_posizione_dopo_ocr.py',
                                       'tools/005_applica_ocr.py', 'training/ocr/esegui.sh', 'training/ocr/lista.txt',
                                       'tools/024_classifica_lessicali.py'),
              'misure': [{'nome': 'pagine rifatte con l\'OCR', 'valore': '158 in 7 documenti'},
                         {'nome': 'controllo del PDF prima dell\'OCR (impronta sha256_pdf, nome, pagine, somiglianza)',
                          'valore': 'i 7 PDF giusti passano, i 2 PDF sbagliati del primo giro sono rifiutati'},
                         {'nome': 'righe aggiunte', 'valore': 'Urgenda 4 (URG-1737 a URG-1740), Neubauer 2 (NEU-1622, NEU-1623)'},
                         {'nome': 'righe gia\' in banca dati rilette sul testo OCR', 'valore': '12'}],
              'note': ("URG-1737 e' stata trovata col codice di S02 sul testo OCR del primo giro (provenienza.ocr); le altre cinque con S03. "
                       "Il primo giro di OCR aveva preso due PDF sbagliati: documento unico §63.39.")})
    R.append({'codice': 'D02', 'tipo': 'corpus', 'nome': "D01 con il testo OCR delle pagine illeggibili di 7 atti",
              'compito': ("Come D01, ma 158 pagine illeggibili (caratteri rotti) di 7 atti in coreano, cinese tradizionale e spagnolo "
                          "hanno il testo rifatto con l'OCR (ocrmypdf), solo dove la pagina vecchia era illeggibile e la nuova leggibile. "
                          "Il PDF passa prima quattro controlli: impronta sha256_pdf dell'intestazione del testo (o della copia .orig), "
                          "nome, numero di pagine, somiglianza."),
              'data': '2026-10-01', 'stato': 'in uso per le righe di quei 7 atti',
              'codice_sorgente': copia('D02', 'tools/005_applica_ocr.py', 'training/ocr/esegui.sh', 'training/ocr/lista.txt'),
              'pesi': [{'file': 'training/ocr/pagine_sostituite.json', 'sha256': sha(QUI/'training/ocr/pagine_sostituite.json')},
                       {'file': 'index/pagine/pagine.prima-ocr-2026-10-01.jsonl.gz', 'sha256': sha(QUI/'index/pagine/pagine.prima-ocr-2026-10-01.jsonl.gz'), 'nota': "l'indice delle pagine di D01, prima dell'OCR"}],
              'misure': [{'nome': 'controllo del PDF', 'valore': 'i 7 PDF giusti passano, i 2 PDF sbagliati del primo giro sono rifiutati'},
                         {'nome': 'pagine che restano illeggibili anche dopo l\'OCR', 'valore': 'per esempio pp. 7-12 della petizione taiwanese Lee'}],
              'note': "Le righe lette sul testo OCR portano provenienza.corpus = D02. Copie del testo di prima: training/ocr/prima/."})
    import yaml as _y
    def sonde_di(path):
        return [{k: q.get(k) for k in ('id', 'titolo', 'testo', 'paragrafi', 'esclusione_di_provenienza', 'canonical_paragrafo', 'canonical_pagina')
                 if q.get(k) is not None} for q in _y.safe_load(open(QUI/path, encoding='utf-8'))['semantic_queries']]
    R.append({'codice': 'P01', 'tipo': 'sonde', 'nome': 'Sonde di Urgenda',
              'compito': "I cinque principi di Urgenda contro cui il reranker da' i punteggi e fra cui la lettura sceglie.",
              'data': '2026-09-02', 'stato': 'in uso',
              'istruzioni': [salva_testo('P01', 'sonde.json', json.dumps({'urgenda': sonde_di('cited-cases/urgenda.yaml')}, ensure_ascii=False, indent=1))]})
    R.append({'codice': 'P02', 'tipo': 'sonde', 'nome': 'Sonde di Neubauer e Future Generations, prima serie',
              'compito': 'Sei principi di Neubauer e sette di STC4360-2018, scritti il 23/09/2026.',
              'data': '2026-09-23', 'stato': 'sostituita da P05 il 01/10/2026; i suoi file restano (cited-cases/<caso>-P02.yaml, file derivati senza suffisso)',
              'istruzioni': [salva_testo('P02', 'sonde.json', json.dumps({c: sonde_di(f'cited-cases/prima-sonde-2026-10-01/{c}.yaml') for c in ('neubauer', 'future-generations')}, ensure_ascii=False, indent=1))]})
    R.append({'codice': 'P03', 'tipo': 'sonde', 'nome': 'Sonde di Neubauer e Future Generations, seconda serie (PI)',
              'compito': ("Sette principi di Neubauer e cinque di STC4360-2018, del PI il 01/10/2026, con i paragrafi su cui poggiano; "
                          "decisioni prese sui conti delle citazioni (documento unico §63.40)."),
              'data': '2026-10-01', 'stato': 'in prova: letture e punteggi in file a parte, la piattaforma non cambia fino al confronto con P02',
              'istruzioni': [salva_testo('P03', 'sonde.json', json.dumps({c: sonde_di(f'cited-cases/{c}-P03.yaml') for c in ('neubauer', 'future-generations')}, ensure_ascii=False, indent=1))]})
    R.append({'codice': 'P04', 'tipo': 'sonde', 'nome': 'Sonde di Neubauer e Future Generations, P03 corretta (primo giro)',
              'compito': ("P03 con i testi delle sonde deboli riscritti dopo la prova del reranker e, per Neubauer, i paragrafi "
                          "riassegnati (Rn. 148-152 a vita e salute, Rn. 195-198 al budget, dovere verso i posteri su Rn. 146 e 193)."),
              'data': '2026-10-01', 'stato': 'superata da P05 (passo intermedio della prova)',
              'istruzioni': [salva_testo('P04', 'sonde.json', json.dumps({c: sonde_di(f'cited-cases/{c}-P04.yaml') for c in ('neubauer', 'future-generations')}, ensure_ascii=False, indent=1))],
              'misure': [{'nome': 'Neubauer, reranker sulla meta\' di verifica', 'valore': '155 su 296 (52%); P03 140 su 296 (47%)'}]})
    R.append({'codice': 'P05', 'tipo': 'sonde', 'nome': 'Sonde di Neubauer e Future Generations, P03 corretta (secondo giro)',
              'compito': ("P04 con l'ammissibilita' di Neubauer ristretta al suo punto proprio (Rn. 89-95, 101, 108-112, 129-137) e i "
                          "paragrafi di merito discussi nell'ammissibilita' passati a vita e salute e alla liberta' intertemporale."),
              'data': '2026-10-01', 'stato': "in uso dal 01/10/2026 alle 12:18 (il PI: il team deve giudicare con le sonde nuove); letture di DeepSeek in corso, nel frattempo proposte provvisorie dai paragrafi e dal reranker",
              'istruzioni': [salva_testo('P05', 'sonde.json', json.dumps({c: sonde_di(f'cited-cases/{c}-P05.yaml') for c in ('neubauer', 'future-generations')}, ensure_ascii=False, indent=1))],
              'misure': [{'nome': 'Neubauer, reranker sulla meta\' di verifica (citazioni divise per documento)', 'valore': '164 su 297 (55%); caso fortuito 14%'},
                         {'nome': 'Future Generations, rimedio strutturale primo del reranker', 'valore': '37 citazioni su 154 (con P03: 72)'}]})
    R.append({'codice': 'R07', 'tipo': 'regola', 'nome': 'Mappa dei paragrafi con le sonde P05',
              'compito': "Come R06, con le sonde P05 (campo sonde_P05; per Neubauer gli intervalli di Randnummer di P05).",
              'data': '2026-10-01', 'stato': 'in uso con P05',
              'istruzioni': copia('R07', 'cited-cases/neubauer-mappa-paragrafi.yaml', 'cited-cases/future-generations-mappa-paragrafi.yaml', 'cited-cases/neubauer-P05.yaml', 'cited-cases/future-generations-P05.yaml'),
              'codice_sorgente': copia('R07', 'tools/012_principi_da_paragrafi.py', 'tools/044_prova_sonde_reranker.py')})
    for cod, caso, nome, data in (('P06', 'klimaseniorinnen', 'Sonde di KlimaSeniorinnen (CEDU, 9/4/2024)', '2026-10-01'),
                                  ('P07', 'cig-parere-clima', 'Sonde del parere della CIG sul clima (23/7/2025)', '2026-10-01'),
                                  ('P08', 'idh-oc-32-25', 'Sonde dell\'Opinion consultiva OC-32/25 della Corte interamericana', '2026-10-01')):
        R.append({'codice': cod, 'tipo': 'sonde', 'nome': nome,
                  'compito': ("Sonde DISTINTIVE (il PI, 01/10/2026): l'elemento proprio della decisione, cio' che la distingue dalle altre "
                              "fonti, cosi' che una ripresa ne riveli la provenienza; non una copertura dei capitoli. Proposte da agenti che "
                              "hanno letto la decisione, riviste col PI, frasi della decisione verificate alla lettera nel corpus."),
                  'data': data, 'stato': 'superata dalla P09 il 02/10/2026' if cod == 'P07' else 'in uso',
                  'istruzioni': [salva_testo(cod, 'sonde.json', json.dumps({caso: sonde_di(f'cited-cases/{caso}.yaml')}, ensure_ascii=False, indent=1))]
                                + copia(cod, f'cited-cases/{caso}.yaml', f'cited-cases/{caso}-fascicolo.md')})
    R.append({'codice': 'P09', 'tipo': 'sonde', 'nome': "Sonde del parere della CIG, con l'obiettivo di 1,5 °C riscritto",
              'compito': ("Come P07, salvo la sonda obiettivo_1_5: tre formulazioni alternative per ciascuna delle sette sonde deboli dei casi "
                          "nuovi (A la frase della decisione, B corta, C come la riassume chi cita) provate col TRACE-Reranker; scelta sulla "
                          "meta' di sviluppo, misura sulla meta' di verifica. Solo la C dell'1,5 migliora; le altre restano."),
              'data': '2026-10-02', 'stato': 'in uso dal 02/10/2026',
              'istruzioni': [salva_testo('P09', 'sonde.json', json.dumps({'cig-parere-clima': sonde_di('cited-cases/cig-parere-clima-P09.yaml')}, ensure_ascii=False, indent=1))]
                            + copia('P09', 'cited-cases/cig-parere-clima-P09.yaml', 'training/confronto_sonde/alternative_2026-10-02.yaml'),
              'codice_sorgente': copia('P09', 'tools/045_prova_sonde_alternative.py', 'tools/044_prova_sonde_reranker.py'),
              'misure': [{'nome': 'CIG, reranker sulla meta\' di verifica', 'valore': '34 su 73 (47%) con P07, 36 su 73 (49%) con P09; caso fortuito 14%'},
                         {'nome': 'obiettivo 1,5 °C, verifica', 'valore': '1 su 9 con P07, 4 su 9 con P09'},
                         {'nome': 'le altre sei sonde deboli (NDC, lex specialis, erga omnes, clima sano, diligenza rafforzata, art. 8)', 'valore': 'nessuna alternativa fa meglio sulla meta\' di sviluppo: restano'}]})
    R.append({'codice': 'R09', 'tipo': 'regola', 'nome': 'Mappe dei paragrafi dei casi nuovi; rimandi in spagnolo e portoghese',
              'compito': ("La mappa dei paragrafi di KlimaSeniorinnen, del parere della CIG e di OC-32/25 (solo i paragrafi con l'elemento "
                          "proprio portano una sonda). Lo strumento riconosce ora anche «párr.», «parágrafo» e mappe scritte «§§ 1-9» o «párrs. 1-9»."),
              'data': '2026-10-01', 'stato': 'in uso',
              'codice_sorgente': copia('R09', 'tools/012_principi_da_paragrafi.py'),
              'istruzioni': copia('R09', 'cited-cases/klimaseniorinnen-mappa-paragrafi.yaml', 'cited-cases/cig-parere-clima-mappa-paragrafi.yaml', 'cited-cases/idh-oc-32-25-mappa-paragrafi.yaml'),
              'misure': [{'nome': 'citazioni con un principio dai paragrafi', 'valore': 'KlimaSeniorinnen 289, CIG 334, Corte interamericana 195'},
                         {'nome': 'effetto sui casi di prima del riconoscimento di «párr.»', 'valore': 'Urgenda +1, Neubauer +2, Future Generations +2 citazioni con un paragrafo'}]})
    R.append({'codice': 'R08', 'tipo': 'regola', 'nome': 'Scelta delle pagine vicine sulla finestra intera, per ogni caso',
              'compito': ("Come R03 (fino a 10 pagine prima e dopo, soglie 0,5 e 0,8, al massimo 5 pagine), ma con i punteggi del reranker "
                          "su TUTTE le pagine della finestra di ogni citazione. Con R03 lo strumento dei punteggi arrivava da 2 pagine "
                          "prima a 3 dopo: le pagine da 4 a 10 avevano un punteggio solo per Urgenda e, per caso, dove un'altra "
                          "citazione era vicina."),
              'data': '2026-10-01', 'stato': 'in uso',
              'codice_sorgente': copia('R08', 'tools/028_ripresa_punteggi.py', 'tools/031_leggi_ripresa.py', 'tools/037_controllo_finestra.py'),
              'misure': [{'nome': 'pagine della finestra senza punteggio prima della correzione', 'valore': 'Neubauer 3.651, Future Generations 1.354, Urgenda 22'},
                         {'nome': 'citazioni con pagine vicine cambiate', 'valore': 'Neubauer 154, Future Generations 4'},
                         {'nome': 'citazioni con pagine attorno proposte', 'valore': 'Neubauer da 544 a 560, Future Generations da 8 a 9'}]})
    R.append({'codice': 'R05', 'tipo': 'regola', 'nome': 'Composizione delle proposte, con il freno corretto per le scritture asiatiche',
              'compito': ("Come R02, piu': le righe rilette sul testo OCR prendono il posto delle letture fatte sulla pagina illeggibile "
                          "(tipo, principi, seguito, punteggi del reranker); il freno sulle prove confronta senza spazi le frasi in "
                          "giapponese, cinese e coreano, dove l'a capo cade dentro le parole."),
              'data': '2026-10-01', 'stato': 'in uso',
              'codice_sorgente': copia('R05', 'tools/035_carica_ripresa.py', 'tools/025_carica_lessicali.py', 'tools/034_freni.py', 'tools/031_leggi_ripresa.py', 'tools/011_sonde.py'),
              'misure': [{'nome': 'freno sulle prove, prova che deve passare e che deve fallire', 'valore': 'giapponese: prova vera trovata; prova di un\'altra pagina, frase inventata e frase dal prompt rifiutate; 039_freni_prova.py OK'},
                         {'nome': 'prove trovate su tutte le letture di Urgenda', 'valore': '1.751 (prima 1.725); inventate 13 (invariate)'},
                         {'nome': 'citazioni con pagine attorno proposte', 'valore': 'Urgenda 410 (prima 404), Neubauer 589 (prima 586)'}]})
    R.append({'codice': 'R06', 'tipo': 'regola', 'nome': 'Mappa dei paragrafi con le sonde P03',
              'compito': ("Come R04, con le sonde P03: per Neubauer ogni Randnummer degli intervalli scritti nel file del caso porta la sua "
                          "sonda; per STC4360-2018 le voci passano dalle sonde vecchie alle nuove, piu' gli ordini al rimedio strutturale."),
              'data': '2026-10-01', 'stato': 'in prova con P03',
              'codice_sorgente': copia('R06', 'tools/012_principi_da_paragrafi.py'),
              'istruzioni': copia('R06', 'cited-cases/neubauer-mappa-paragrafi.yaml', 'cited-cases/future-generations-mappa-paragrafi.yaml', 'cited-cases/neubauer-P03.yaml', 'cited-cases/future-generations-P03.yaml'),
              'misure': [{'nome': 'citazioni di Neubauer con un principio dai paragrafi', 'valore': '998 (con P02 e R04: 895)'}]})
    R.append({'codice': 'L01', 'tipo': 'lettore', 'nome': 'DeepSeek V4 Flash 0731, lettura delle citazioni, prima versione',
              'compito': "Come L02, senza la regola sulle note a pie' di pagina. Due letture per riga, su tutte le citazioni di Urgenda.",
              'data': '2026-09-26', 'stato': 'superata da L02 (le letture restano in archivio)',
              'note': "Sostituita perche' DeepSeek e i validatori divergevano soprattutto in nota (accordo 0,32 in nota contro 0,60 nel corpo)."})
    R.append({'codice': 'R03', 'tipo': 'regola', 'nome': 'Scelta delle pagine vicine da far leggere',
              'compito': "Sopra i punteggi di T01: una pagina fino a 10 prima o dopo la citazione entra nella lettura della ripresa se il suo punteggio piu' alto su un principio e' almeno 0,5 (da 2 pagine prima a 3 dopo) o 0,8 (piu' lontano); al massimo 5 pagine per citazione.",
              'data': '2026-09-29', 'stato': 'in uso',
              'codice_sorgente': copia('R03', 'tools/031_leggi_ripresa.py'),
              'misure': [{'nome': 'soglia 0,8 per le pagine lontane', 'valore': 'misurata: sulle pagine lette fra 4 e 10 pagine dalla citazione, sopra 0,8 piu\' della meta\' e\' seguito vero'},
                         {'nome': 'soglia 0,5 per le pagine vicine', 'valore': 'non misurata: ereditata dal sistema precedente, da calibrare sui giudizi del team'}],
              'note': ("Una regola, non un modello: calibrarla non riaddestra T01. Se T01 si riaddestra, le soglie si ricalibrano. Il codebook "
                       "0.3-pilot (dimensione 7) scrive ancora la finestra {prima: 2, dopo: 3}: va aggiornato a 10 nella prossima versione del "
                       "codebook, non nel file registrato per L02 e L03, la cui impronta non si tocca.")})
    R.append({'codice': 'R01', 'tipo': 'regola', 'nome': 'Mappa dei paragrafi',
              'compito': 'Principio preso da una citazione che indica il paragrafo («para. 5.7.7»): nessun modello, etichetta usabile per addestrare.',
              'data': '2026-09-28', 'stato': 'in uso',
              'codice_sorgente': copia('R01', 'tools/012_principi_da_paragrafi.py'),
              # dal 01/10/2026 le mappe vive sono quelle riviste (R04): la copia di R01 e' quella di prima della revisione
              'istruzioni': copia('R01', 'cited-cases/prima-revisione-mappe-2026-10-01/urgenda-mappa-paragrafi.yaml', 'cited-cases/prima-revisione-mappe-2026-10-01/neubauer-mappa-paragrafi.yaml', 'cited-cases/prima-revisione-mappe-2026-10-01/future-generations-mappa-paragrafi.yaml'),
              'misure': [{'nome': 'citazioni con un principio dai paragrafi', 'valore': 'Urgenda 526, Neubauer 1.011, Future Generations 13'}],
              'note': 'Corretta il 28/09/2026: leggeva numeri di due cifre sole e oltrepassava il punto e virgola (documento unico §63.25). Sostituita da R04 il 01/10/2026.'})
    R.append({'codice': 'R04', 'tipo': 'regola', 'nome': 'Mappa dei paragrafi, rivista',
              'compito': 'Come R01, con le mappe rilette sul testo dei paragrafi: una voce porta un principio solo se il paragrafo lo enuncia, applica o sviluppa; fatti, tesi di parte, riassunti narrativi e premesse vanno in «prepara» e non danno principi.',
              'data': '2026-10-01', 'stato': 'in uso',
              'codice_sorgente': copia('R04', 'tools/012_principi_da_paragrafi.py'),
              'istruzioni': copia('R04', 'cited-cases/urgenda-mappa-paragrafi.yaml', 'cited-cases/neubauer-mappa-paragrafi.yaml', 'cited-cases/future-generations-mappa-paragrafi.yaml'),
              'misure': [{'nome': 'voci rilette (discordi o incerte nel controllo di DeepSeek del 29/09)', 'valore': '276: 128 confermate, 126 spostate in prepara, 19 cambiate, 3 sonde tolte'},
                         {'nome': 'citazioni con un principio dai paragrafi', 'valore': 'Urgenda 490, Neubauer 895, Future Generations 11'}],
              'note': 'Revisione fatta da un modello leggendo il testo intero dei paragrafi come un giurista, il 30/09/2026 (`pubblicazione/mappa/REVISIONE-MAPPE-GIURISTA.md`); da confermare dal giurista del team. Ogni voce cambiata porta il campo `rivista` con le sonde di prima.'})
    # IL TESTO DI L02 E L03 NON E' UNA COPIA SALVATA AL MOMENTO DELLA LETTURA: `CL.modulo()` lo rigenera a ogni giro
    # del registro dai file di oggi (codebook 0.3-pilot del 28/09 17:08, fascicolo). L02 ha girato il 27/09 e le righe
    # portano «codebook 0.2-pilot»: la scheda lo dichiara (revisione del 30/09/2026, punto 3).
    RIGENERATO = ("testo rigenerato da classifica_lessicali.modulo() con i file di oggi, non salvato al momento della lettura: "
                  "il codebook registrato e' il file del 28/09/2026 17:08 (0.3-pilot), mentre le letture di L02 sono del 27/09 "
                  "e le righe portano «codebook 0.2-pilot»")
    for cod, caso, data, nota in (('L02', 'urgenda', '2026-09-27', 'Versione con la regola del PI sulle note a pie\' di pagina (§63.23).'),
                                  ('L03', 'neubauer', '2026-09-28', 'Stesse istruzioni, generalizzate al caso: il nome puo\' essere anche la persona (Luisa Neubauer). Vale anche per Future Generations.')):
        testo = CL.modulo(caso)
        R.append({'codice': cod, 'tipo': 'lettore', 'nome': 'DeepSeek V4 Flash 0731, lettura delle citazioni',
                  'compito': 'Per ogni citazione: e\' davvero il caso? tipo di citazione, chi parla, proposizione, motivo. Due letture per riga.',
                  'casi': ['urgenda'] if caso == 'urgenda' else ['neubauer', 'future-generations'],
                  'data': data, 'stato': 'in uso',
                  'modello_base': {'nome': 'deepseek-ai/DeepSeek-V4-Flash-0731', 'revisione': '7872f01b1d1fe23eabc4c98b48bffcef5a386062',
                                   'indice_pesi_sha256': '98efab455cf08dfbbbaaba6f570e1bf10bf927d2b4c3c453a59c2f6f0e3be92b', 'licenza': 'MIT'},
                  'addestramento': None,
                  'impostazioni': {'letture': 2, 'ragionamento': 'acceso, sforzo basso', 'max_token_risposta': 8000, 'in_parallelo': 48},
                  'istruzioni': [dict(salva_testo(cod, 'istruzioni.txt', testo), ricostruita=RIGENERATO),
                                 *copia(cod, f'cited-cases/{caso}-fascicolo.md'),
                                 dict(copia(cod, 'codebook/citazioni.yaml')[0], versione='0.3-pilot',
                                      nota='file del 28/09/2026 17:08, posteriore alle letture di L02 (27/09) e di L03 del 28/09 mattina')],
                  'codice_sorgente': copia(cod, 'tools/024_classifica_lessicali.py'),
                  'software': SOFTWARE_RECAS, 'macchina': MACCHINA,
                  'misure': [{'nome': 'accordo sul tipo con i validatori (Urgenda, 317 righe, prima lettura)', 'valore': '0,568 (kappa 0,36)'}] if caso == 'urgenda' else [],
                  'note': nota})
    base_lr = LR.MODULO
    # LE ISTRUZIONI DI L04 SONO RICOSTRUITE (corrette il 30/09/2026): non furono salvate al momento delle letture.
    # `032_leggi_l04.py` le ricava dal file di oggi togliendo le tre aggiunte del 28/09 (fascicolo, regola delle note con
    # citazione testuale, domanda 3 sulla frase sostenuta). Che la domanda 3 non ci fosse lo dicono i file di uscita:
    # nessuna lettura L04 ha il campo `frase_sostenuta`. Fino al 30/09 il registro teneva per errore la domanda 3.
    # IL CODICE CHE HA GIRATO IL 27-28/09 non e' stato conservato tale e quale: la copia piu' vicina e'
    # `versioni/V04/leggi_ripresa.py` (file del 28/09 22:57: finestra stretta, da 2 pagine prima a 3 dopo, al massimo
    # 3 pagine, senza ragionamento salvato; il suo testo delle istruzioni ha gia' la domanda 3). Le righe mai lette da
    # L04 sono state lette il 30/09 con `tools/032_leggi_l04.py`, che importa il `031_leggi_ripresa.py` di oggi: stesse
    # istruzioni, ma finestra larga (R03). Il file di oggi NON e' il codice di L04 (revisione del 30/09/2026, punto 3).
    _m_leggi_l04 = __import__('032_leggi_l04')
    istruzioni_l04 = _m_leggi_l04.istruzioni_l04
    prima = istruzioni_l04(base_lr)
    RICOSTRUITA_L04 = ("testo ricostruito il 30/09/2026 da tools/032_leggi_l04.py (il file di oggi senza le tre aggiunte del 28/09); "
                       "il testo dato al modello il 27-28/09 non fu salvato. Che la domanda 3 mancasse lo prova l'assenza del campo "
                       "frase_sostenuta in tutte le letture L04")
    (VER/'L04').mkdir(parents=True, exist_ok=True)
    shutil.copy2(VER/'V04'/'031_leggi_ripresa.py', VER/'L04'/'031_leggi_ripresa.py')
    R.append({'codice': 'L04', 'tipo': 'lettore', 'nome': 'DeepSeek V4 Flash 0731, lettura della ripresa',
              'compito': 'Quali principi prende la citazione, e quali pagine vicine proseguono la ripresa, con una citazione testuale e un commento.',
              'data': '2026-09-27', 'stato': 'in uso per i principi dal 30/09/2026 (col si\' del PI, §63.35): i principi proposti sulle righe da giudicare vengono di nuovo da L04; tutto il resto della riga da L05 (o L07 per il seguito)',
              'modello_base': {'nome': 'deepseek-ai/DeepSeek-V4-Flash-0731', 'revisione': '7872f01b1d1fe23eabc4c98b48bffcef5a386062', 'licenza': 'MIT'},
              'istruzioni': [dict(salva_testo('L04', 'istruzioni.txt', prima), ricostruita=RICOSTRUITA_L04)],
              'codice_sorgente': [{'file': 'versioni/L04/leggi_ripresa.py', 'sha256': sha(VER/'L04'/'031_leggi_ripresa.py'),
                                   'nota': "copia di versioni/V04/leggi_ripresa.py (file del 28/09/2026 22:57), la piu' vicina al codice delle "
                                           "letture del 27-28/09: finestra stretta (da 2 pagine prima a 3 dopo, al massimo 3 pagine). Il codice "
                                           "esatto di quelle letture non e' stato conservato"},
                                  dict(copia('L04', 'tools/032_leggi_l04.py')[0],
                                       nota="la lettura del 30/09/2026 delle righe che L04 non aveva mai letto: stesse istruzioni, ma importa il "
                                            "031_leggi_ripresa.py di oggi, quindi finestra larga (R03, fino a 5 pagine fra 10)")],
              'software': SOFTWARE_RECAS, 'macchina': MACCHINA,
              'note': ("Letture: Urgenda il 27/09/2026 (file delle 20:49); Neubauer e Future Generations il 28/09/2026 alle 15:32, con un "
                       "testo che puo' differire da quello di Urgenda (non salvato). Citazioni testuali copiate dalla pagina nel 64% dei casi "
                       "(misurato il 30/09 su Urgenda). Dal 30/09 e' di nuovo la fonte dei principi proposti sulle righe da giudicare (col si' "
                       "del PI, §63.35). Le righe che non aveva letto sono state lette il 30/09 con `tools/032_leggi_l04.py`; la revisione del "
                       "30/09 sera conta ancora 38 righe da giudicare senza nessuna lettura L04 (15 Urgenda, 23 Neubauer) e 207 con elenco "
                       "vuoto di principi, che il controllo di completezza non segnala.")})
    R.append({'codice': 'L05', 'tipo': 'lettore', 'nome': 'DeepSeek V4 Flash 0731, lettura della ripresa, seconda versione',
              'compito': 'Come L04, con il fascicolo del caso e due regole: una frase con una nota a un\'altra fonte non prosegue; la citazione testuale va copiata alla lettera. In piu\' la domanda 3: la frase dell\'atto che la citazione sostiene.',
              'data': '2026-09-28', 'stato': 'in uso dal 29/09/2026 sera per il seguito, le citazioni testuali e la frase sostenuta (finestra fino a 10 pagine, R03). Per i principi no, dal 30/09: decide sulla sola frase della nota e contro i giudizi del PI fa peggio di L04 (§63.35)',
              'modello_base': {'nome': 'deepseek-ai/DeepSeek-V4-Flash-0731', 'revisione': '7872f01b1d1fe23eabc4c98b48bffcef5a386062', 'licenza': 'MIT'},
              'istruzioni': [salva_testo('L05', 'istruzioni.txt', base_lr),
                             *copia('L05', 'cited-cases/urgenda-fascicolo.md', 'cited-cases/neubauer-fascicolo.md', 'cited-cases/future-generations-fascicolo.md')],
              'codice_sorgente': copia('L05', 'tools/031_leggi_ripresa.py'),
              'software': SOFTWARE_RECAS, 'macchina': MACCHINA,
              'note': ("Istruzioni del 28/09/2026 sera; letture eseguite il 29/09/2026. La regola delle note nasce da un caso segnalato dal PI: "
                       "memoriale per la Corte interamericana, p. 51 e p. 54 (Klimaatzaak alla nota 205).")})
    # L06 E L07 (30/09/2026, §63.35): la prova della regola del passaggio, e il seguito riletto sui principi di L04.
    leggi_l06 = __import__('099_leggi_l06')
    leggi_seguito = __import__('033_leggi_seguito')
    DS = {'nome': 'deepseek-ai/DeepSeek-V4-Flash-0731', 'revisione': '7872f01b1d1fe23eabc4c98b48bffcef5a386062', 'licenza': 'MIT'}
    R.append({'codice': 'L06', 'tipo': 'lettore', 'nome': 'DeepSeek V4 Flash 0731, lettura della ripresa, prova col passaggio',
              'compito': 'Come L05, ma il principio si decide sul ragionamento in cui sta la citazione, non sulla sola frase della nota.',
              'data': '2026-09-30', 'stato': 'esperimento su 120 righe di Urgenda (4 letture): non batte L04 contro i giudizi del PI, non entra in piattaforma',
              'modello_base': DS, 'istruzioni': [salva_testo('L06', 'istruzioni.txt', LR.MODULO.replace(leggi_l06.VECCHIA_1, leggi_l06.NUOVA_1).replace(leggi_l06.VECCHIA_3, leggi_l06.NUOVA_3))],
              'codice_sorgente': copia('L06', 'tools/099_leggi_l06.py'), 'software': SOFTWARE_RECAS, 'macchina': MACCHINA,
              # LA BASE (revisione del 30/09/2026, punto 4): l'insieme delle righe giudicate dal PI non e' congelato (38 il 28/09,
              # 43 il 30/09 sera) e le 120 righe dell'esperimento ne contengono 35 delle 38. Le cifre «14 / 18 su 38» del documento
              # unico non si riproducono su quella base; il ricalcolo della revisione da' 13 / 17 su 35 (L04 25 su 38).
              'misure': [{'nome': 'principi identici ai giudizi del PI del 28/09 (una lettura / 2 letture su 4)',
                          'valore': '13 / 17 sulle 35 righe del PI presenti fra le 120 (ricalcolo del 30/09 sera); L04 sulle stesse 38 righe: 25. Il documento unico riporta 14 / 18 e L04 26 su una base non fissata; le righe giudicate dal PI vanno congelate in un file con data prima di ogni nuova misura'}],
              'note': "Esperimento, non versione in uso: i giudizi del PI usati come riferimento sono stati dati con le proposte davanti."})
    R.append({'codice': 'L07', 'tipo': 'lettore', 'nome': 'DeepSeek V4 Flash 0731, pagine attorno rilette sui principi proposti',
              'compito': 'Solo la domanda del seguito, con le istruzioni di L05, dando come fissati i principi che la riga propone (da L04).',
              'data': '2026-09-30', 'stato': 'in uso dal 30/09/2026 sulle righe da giudicare dove i principi di L04 sono diversi da quelli di L05 e ci sono pagine candidate',
              'modello_base': DS, 'istruzioni': [salva_testo('L07', 'istruzioni.txt', leggi_seguito.MODULO)],
              'codice_sorgente': copia('L07', 'tools/033_leggi_seguito.py'), 'software': SOFTWARE_RECAS, 'macchina': MACCHINA})
    R.append({'codice': 'T01', 'tipo': 'modello', 'nome': 'TRACE-Reranker 0.1',
              'compito': 'Punteggio fra un principio e un testo (brano della citazione, pagine vicine): propone i principi e le pagine vicine da leggere.',
              'data': '2026-09-22', 'stato': 'in uso',
              'modello_base': {'nome': 'Qwen/Qwen3-Reranker-4B', 'revisione': '22e683669bc0f0bd69640a1354a6d0aebcfeede5', 'licenza': 'Apache-2.0'},
              'pesi': [{'file': f'training/lora_qwen_rr4b_{s}/passata_2/adapter_model.safetensors', 'sha256': h}
                       for s, h in ((1, '2dd2ab9afcd00914139949f82686926135fea6c05ec505e5567c09f628d11ebf'),
                                    (2, 'b5fa8fbd073a32295f04bf88380b4e4635995001c49b21a4115453a7bd62997e'),
                                    (3, 'e8cc3e5fc5822a6d01d46ddb3002eb5722bb6a1d0066ec2b35b7539e77d061e2'))],
              'addestramento': {'data': '2026-09-22', 'dati': '263 giudizi del team sulle righe semantiche di Urgenda (divisione congelata del 22/09)',
                                'righe': 263, 'impostazioni': 'LoRA rango 16 su q,k,v,o; 2 passate; tre semi mediati; istruzione «ripresa»; 2.560 token'},
              'codice_sorgente': copia('T01', 'tools/027_prova_riordinatori.py', 'tools/028_ripresa_punteggi.py'),
              'software': SOFTWARE_RECAS, 'macchina': MACCHINA,
              'misure': [{'nome': 'principio col punteggio piu alto fra quelli della mappa dei paragrafi (Urgenda, 526 citazioni)', 'valore': '0,69 (a caso 0,37)'},
                         {'nome': 'AUC sulle 133 righe di prova semantiche', 'valore': '0,787: NON e\' una misura della ripresa implicita (§63.24)'}],
              'note': 'Addestrato su etichette di luglio che confondevano argomento e fonte (§63.24): da riaddestrare sui principi confermati.'})
    R.append({'codice': 'R02', 'tipo': 'regola', 'nome': 'Composizione delle proposte',
              'compito': 'Mette insieme R01, le letture L02-L05 e L07 e i punteggi di T01 nelle proposte che il team vede, con le regole del codebook.',
              'data': '2026-09-28', 'stato': 'sostituita da R05 il 01/10/2026 (regola aggiunta il 30/09/2026)',
              'codice_sorgente': copia('R02', 'tools/035_carica_ripresa.py', 'tools/025_carica_lessicali.py', 'tools/034_freni.py'),
              'regole': ['principi spuntati: quelli del paragrafo (R01) e della lettura (L04 dal 30/09; prima L05); il reranker (T01) e\' un indizio, non spunta',
                         'menzione in catena: principio «nessuno», gli indizi restano visibili',
                         'nessun seguito spuntato se la citazione non prende nessun principio',
                         'la frase sotto una pagina vicina e\' mostrata come citazione testuale solo se si ritrova nella pagina',
                         'dal 30/09/2026: una pagina spuntata su un principio che la riga non propone resta elencata, non si toglie'],
              'note': ("Scrive solo sulle righe senza esito: i giudizi del team non si toccano. Difetto aperto (revisione del 30/09/2026, punto 2): "
                       "i principi scritti dal lettore senza il prefisso del caso vengono scartati in silenzio nel confronto con gli id del file "
                       "del caso; la correzione del prefisso c'e' solo per le pagine del seguito.")})
    for cod, v, passata, misura, data in (('T02', 'v0', 2, 'tipo 0,596 (kappa 0,39) sulle 317 righe; DeepSeek 0,568', '2026-09-27'),
                                          ('T03', 'v1', 2, 'tipo 0,599; principi: almeno uno giusto 0,79 sulle 101 righe col paragrafo (DeepSeek 0,86, ma aiutato)', '2026-09-28')):
        R.append({'codice': cod, 'tipo': 'modello', 'nome': f'TRACE-Reader {v}',
                  'compito': 'Il lavoro di DeepSeek su una GPU sola: tipo, chi parla, proposizione, motivo' + (', principi e pagine vicine' if v == 'v1' else ''),
                  'data': data, 'stato': 'sperimentale (le proposte in piattaforma vengono ancora da DeepSeek)',
                  'modello_base': {'nome': 'Qwen/Qwen3-14B', 'revisione': '40c069824f4251a91eefaf281ebe4c544efd3e18', 'licenza': 'Apache-2.0'},
                  'pesi': [{'file': f'training/reader/lora_reader_{v}/passata_{passata}/adapter_model.safetensors',
                            'sha256': {'v0': 'c3829c9f0de871621c2651ec344091f67b53650c9ad5c283bd7a0cbac0f059a9', 'v1': '49dddaaf0efda006f2bc2e9963448921043f38d4d1690a93006bff4b8fac666c'}[v]}],
                  'addestramento': {'data': data, 'dati': '1.120 letture di DeepSeek (L02, L04) su citazioni di Urgenda con due letture concordi sul tipo; esclusa ogni riga di prova',
                                    'righe': 1120, 'impostazioni': 'LoRA rango 16 su attenzione e MLP; 2 passate; lr 1e-4; accumulo 8; ' + ('6.144' if v == 'v0' else '8.192') + ' token'},
                  'codice_sorgente': copia(cod, 'tools/112_reader.py'),
                  'software': SOFTWARE_RECAS, 'macchina': MACCHINA,
                  'misure': [{'nome': 'accordo con i validatori (righe giudicate con le proposte di DeepSeek davanti)', 'valore': misura}],
                  # LA REGOLA DI ADOZIONE, CON LE DATE (revisione del 30/09/2026, punto 5): la regola del 27/09 e' stata superata e non
                  # applicata; quella del 30/09 non si puo' ancora misurare. Si tengono tutte e due.
                  'regola_di_adozione': [
                      {'data': '2026-09-27', 'regola': "sulle 317 righe di Urgenda con un tipo dato dalle persone, se TRACE-Reader eguaglia o supera DeepSeek V4 Flash fa lui le proposte (§63.26)",
                       'esito': "TRACE-Reader v0 0,596 contro DeepSeek 0,568: superata, ma NON applicata, perche' quelle 317 righe erano state giudicate con le proposte di DeepSeek davanti e il PI ha voluto una misura senza proposte"},
                      {'data': '2026-09-30', 'regola': "sostituisce DeepSeek V4 Flash solo se lo eguaglia sulle righe che il team giudica senza proposte (campione di una su cinque); righe con un tipo confrontabile al 30/09 sera: zero",
                       'esito': 'in attesa dei giudizi senza proposte'}],
                  'note': "Distillazione da DeepSeek, dichiarata. Le etichette umane di prova sono di una persona sola e sono state date con le proposte di DeepSeek davanti."})
    # CHE COSA CAMBIA RISPETTO ALLA VERSIONE DI PRIMA (29/09/2026, il PI: «le V sembra che indichino piu' cose»).
    # Una V e' una ricetta: modello, istruzioni, impostazioni, dati. Qui si dice in una frase che cosa la distingue.
    CAMBIA = {
        'S02': ('S01', "niente filtri semantici sulle righe col nome; un riferimento lungo resta una citazione; forme coreana e giapponese"),
        'D02': ('D01', "158 pagine illeggibili di 7 atti rifatte con l'OCR, dal PDF controllato con l'impronta"),
        'P03': ('P02', "le sonde del PI: Neubauer da 6 a 7 (due nuove: vita e salute, ammissibilita'), STC4360-2018 da 7 a 5"),
        'R05': ('R02', "precedenza alle righe rilette sul testo OCR; freno sulle prove senza spazi nelle scritture asiatiche"),
        'R06': ('R04', "le sonde P03; Neubauer per Randnummer"),
        'R07': ('R06', "le sonde P05"),
        'R08': ('R03', "i punteggi su tutta la finestra di 10 pagine prima e dopo, per ogni caso"),
        'R09': ('R07', "mappe dei tre casi nuovi; rimandi a paragrafo in spagnolo e portoghese"),
        'P04': ('P03', "testi delle sonde deboli riscritti, paragrafi di Neubauer riassegnati"),
        'P05': ('P04', "ammissibilita' di Neubauer ristretta al suo punto proprio"),
        'S03': ('S02', "testo OCR delle pagine illeggibili (PDF controllato con l'impronta); altre forme giapponesi e coreane; l'a capo ammesso dentro i nomi in quelle scritture"),
        'L02': ('L01', "stesso modello e stesse impostazioni; le istruzioni aggiungono la regola sulle note a pie' di pagina"),
        'L03': ('L02', "stesse istruzioni, generalizzate agli altri casi: il nome puo' essere una persona o una parte"),
        'L05': ('L04', "stesso modello; le istruzioni aggiungono il fascicolo del caso, la regola delle note, la frase alla lettera e la frase sostenuta"),
        'R04': ('R01', "voci rilette sul testo dei paragrafi: fatti, tesi di parte e premesse passano a «prepara»"),
        'L06': ('L05', "il principio si decide sul passaggio, non sulla sola frase della nota"),
        'L07': ('L05', "solo la domanda delle pagine attorno, con i principi della riga dati come fissati"),
        'T03': ('T02', "stessa base e stesso metodo; impara anche i principi e le pagine vicine, con testi piu' lunghi (8.192 token)"),
    }
    # LE CINQUE FAMIGLIE (29/09/2026, il PI: «forse non ha senso chiamare V tutto»). Il codice di prima resta
    # come `alias`, cosi' quello che e' stato scritto con i codici V si legge ancora.
    VECCHI = {'S01': 'V00', 'S02': 'V10', 'R01': 'V01', 'R02': 'V07', 'L01': 'V02a', 'L02': 'V02', 'L03': 'V03',
              'L04': 'V04', 'L05': 'V05', 'T01': 'V06', 'T02': 'V08', 'T03': 'V09'}
    FAMIGLIE = {'D': 'dati', 'P': 'sonde (i principi di un caso citato)', 'S': 'ricerca per nome', 'R': 'regola senza modello', 'L': 'lettura di DeepSeek V4 Flash, modello linguistico grande',
                'T': 'modello TRACE addestrato da noi'}
    # NOMI CHE SI CAPISCONO DA SOLI (29/09/2026, il PI: «non capisco piu' nulla»): che cosa fa, per quale caso, e se
    # e' in uso. `in_uso` dice in una parola se le proposte che si vedono oggi vengono da li'.
    NOMI = {
        'D01': ('Documents: Climate Litigation Database, public API snapshot', 'in uso'),
        'S01': ('Name search, first version', 'sostituita'),
        'S02': ('Name search, corrected', 'sostituita'),
        'S03': ('Name search on OCR text, more Japanese and Korean forms', 'in uso'),
        'D02': ('Documents: D01 with OCR text of unreadable pages', 'in uso'),
        'P01': ('Probes of Urgenda', 'in uso'),
        'P02': ('Probes of Neubauer and Future Generations, first set', 'sostituita'),
        'P03': ('Probes of Neubauer and Future Generations, second set (PI)', 'superata da P05'),
        'R05': ('Rules that put the proposals together, with the brake for Asian scripts', 'in uso'),
        'R06': ('Paragraph map with the second set of probes', 'superata'),
        'R07': ('Paragraph map with probes P05', 'in uso'),
        'R08': ('Choice of the nearby pages, over the full window for every case', 'in uso'),
        'R09': ('Paragraph maps of the three new cases; Spanish and Portuguese paragraph references', 'in uso'),
        'P06': ('Probes of KlimaSeniorinnen', 'in uso'),
        'P07': ('Probes of the ICJ climate advisory opinion', 'superata'),
        'P09': ('Probes of the ICJ climate advisory opinion, 1.5°C probe rewritten', 'in uso'),
        'P08': ('Probes of IACtHR advisory opinion OC-32/25', 'in uso'),
        'P04': ('Probes of Neubauer and Future Generations, second set corrected (first round)', 'superata'),
        'P05': ('Probes of Neubauer and Future Generations, second set corrected (second round)', 'in uso'),
        'R01': ('Paragraph map, first version', 'sostituita'),
        'R04': ('Paragraph map, reviewed', 'in uso'),
        'R02': ('Rules that put the proposals together', 'sostituita'),
        'R03': ('Choice of the nearby pages to read', 'sostituita'),
        'L01': ('Citation reading, first version', 'non piu\' in uso'),
        'L02': ('Citation reading, Urgenda', 'in uso'),
        'L03': ('Citation reading, Neubauer and Future Generations', 'in uso'),
        'L04': ('Uptake reading, first version: the principles', 'in uso'),
        'L05': ('Uptake reading with the case dossier: surrounding pages, quotes, supported sentence', 'in uso'),
        'L06': ('Uptake reading, test: principle decided on the whole passage', 'sperimentale'),
        'L07': ('Surrounding pages reread on the proposed principles', 'in uso'),
        'T01': ('TRACE-Reranker 0.1', 'in uso'),
        'T02': ('TRACE-Reader v0', 'sperimentale'),
        'T03': ('TRACE-Reader v1', 'sperimentale'),
    }
    # LE IMPOSTAZIONI E IL SOFTWARE DI OGNI PASSO (30/09/2026, il PI: «ognuno deve dire lo strumento che si usa,
    # specificamente e con dettaglio»). Prima mancavano le impostazioni delle letture della ripresa, il software dei
    # passi fatti sul Mac e il codice della prima ricerca per nome.
    SOFTWARE_MAC = {'python': '3.14.6', 'google-cloud-firestore': '2.28.0', 'PyYAML': '6.0.3', 'pymupdf': '1.28.0',
                    'regex': '2026.7.19', 'numpy': '2.5.1'}
    MACCHINA_MAC = 'Apple M5 Pro, macOS 27.0 (Mac del gruppo di ricerca)'
    lettura = lambda n: {'letture': n, 'ragionamento': 'acceso, sforzo basso', 'max_token_risposta': 8000, 'in_parallelo': 48,
                         'temperatura': 'quella predefinita del modello'}
    for v in R:
        if v['codice'] in ('L04', 'L05', 'L06', 'L07') and not v.get('impostazioni'):
            v['impostazioni'] = lettura({'L04': 2, 'L05': 2, 'L06': 4, 'L07': 1}[v['codice']])
        if v['codice'] in ('S01', 'S02', 'S03', 'R01', 'R02', 'R03'):
            v.setdefault('software', SOFTWARE_MAC)
            v.setdefault('macchina', MACCHINA_MAC)
        if v['codice'] == 'L01':
            v.setdefault('software', SOFTWARE_RECAS)
            if not v.get('codice_sorgente'):
                v['note'] = (v.get('note') or '') + " Il codice di questa prima lettura non e' stato conservato a parte: e' `024_classifica_lessicali.py` prima della regola delle note (L02)."
        if v['codice'] == 'S01' and not v.get('codice_sorgente'):
            v['codice_sorgente'] = [{'file': 'versioni/S01/cerca.py', 'sha256': sha(VER/'S01'/'016_cerca.py')}]
            v['note'] = (v.get('note') or '') + (" Codice: `016_cerca.py` com'era il 28/09/2026 (storia del repository), l'ultima versione prima "
                                                 "delle correzioni di S02; i giri del 3/09 e del 23/09 possono aver usato una revisione precedente.")
    for v in R:
        v['nome_tecnico'] = v['nome']
        v['nome'], v['in_uso'] = NOMI[v['codice']]
    for v in R:
        v['alias'] = VECCHI.get(v['codice'], '')
        v['famiglia'] = FAMIGLIE[v['codice'][0]]
        if v['codice'] in CAMBIA:
            v['rispetto_a'], v['cambia'] = CAMBIA[v['codice']]
        if v['codice'] == 'L01':
            v['modello_base'] = next(x['modello_base'] for x in R if x['codice'] == 'L02')
            v['impostazioni'] = next(x.get('impostazioni') for x in R if x['codice'] == 'L02')
            v['macchina'] = MACCHINA
    return R


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--scrivi', action='store_true'); a = ap.parse_args()
    R = registro()
    (VER/'registro.json').write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding='utf-8')
    print(len(R), 'voci ->', VER/'registro.json')
    if CAMBIATI_DOPO:
        print('FILE CAMBIATI DOPO LA LORO VERSIONE (la copia resta quella della versione; se il cambio conta, serve un codice nuovo):')
        for x in CAMBIATI_DOPO:
            print('  ', x)
    if a.scrivi:
        from google.cloud import firestore
        db = firestore.Client(project='climpact-drp')
        b = db.batch()
        for v in R:
            b.set(db.collection('trace_versioni').document(v['codice']), v)
            # il documento col codice vecchio resta, e rimanda al nuovo
            if v.get('alias'):
                b.set(db.collection('trace_versioni').document(v['alias']),
                      {'codice': v['alias'], 'alias_di': v['codice'], 'nome': v['nome'], 'famiglia': v['famiglia']})
        b.commit(); print('scritte su trace_versioni')


if __name__ == '__main__':
    main()
