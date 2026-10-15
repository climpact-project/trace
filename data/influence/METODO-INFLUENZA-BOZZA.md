# TRACE: misurare l'influenza di una decisione e dei suoi principi

Bozza di metodo, 11/10/2026, da discutere col PI. Versione beta, codice di regola proposto **N01**.

Quello che segue è un metodo nostro. Le slide di Young servono solo come termine di confronto: non le ho ancora viste (vedi la fine). Ogni scelta qui sotto parte da come sono fatti i dati di TRACE, e ogni cifra citata è stata letta oggi da `corpus_rows`.

## 1. Il punto di partenza: che cosa dicono i dati

Righe vive, dopo le esclusioni già fatte dalla pipeline (rete esclusa o fusa, righe scartate):

| Decisione | Righe | Documenti | Casi | Righe validate | Accordo proposta/validazione sul tipo |
|---|---|---|---|---|---|
| Urgenda | 1661 | 344 | 141 | 194 confermate | 66% |
| Neubauer | 2391 | 211 | 102 | 83 | 76% |
| Future Generations | 217 | 93 | 50 | 53 | 83% |
| KlimaSeniorinnen | 1258 | 114 | 59 | 54 | 74% |
| Parere CIG | 1419 | 107 | 40 | 21 | 77% |
| Parere Corte IDH | 1216 | 93 | 39 | 9 | 89% su 9 |

Da qui escono quattro fatti, e il metodo nasce da loro.

1. **La riga misura la lunghezza, non l'influenza.** Un solo atto arriva a 197 righe (KlimaSeniorinnen). I dieci documenti più lunghi fanno il 27% delle righe di Urgenda e il 67% di quelle del parere della Corte IDH. Se si sommano righe, vince chi scrive ricorsi lunghi.
2. **Le parti parlano molto più delle corti.** Su Urgenda la corte parla in 298 righe su 1661, mentre le parti ne hanno 1064. Mescolare le due voci in un solo numero vuol dire misurare soprattutto l'attività degli avvocati.
3. **La lettura della macchina sbaglia in modo misurabile.** Dove una persona ha validato, la macchina aveva visto giusto il tipo di citazione nel 66–89% dei casi, e chi parla nel 69–94%. Alla prova cieca dei principi la proposta scende a 0,54. Un indice che ignora questo errore è più preciso di quanto sia vero.
4. **Le sei decisioni non hanno la stessa copertura né la stessa età.** Urgenda ha dieci anni di ricezione ed è quasi completa. I due pareri hanno pochi mesi e una copertura parziale. Un totale grezzo li metterebbe in fila come se partissero alla pari.

## 2. Le scelte, una per una

### 2.1 L'unità è il caso, non la riga

L'influenza si conta **sul caso citante**, cioè sulla controversia, e sul documento solo come livello intermedio. Le righe interne a un documento dicono *come* cita, non *quanto*.

- Perché il caso: più atti della stessa controversia (ricorso, replica, decisione) non sono più casi influenzati. Contarli a parte moltiplica la stessa ricezione.
- Alternativa scartata: un tetto di 3 righe per documento. È arbitrario, lascia ancora il peso agli atti lunghi e non risolve gli atti multipli dello stesso caso.
- La riga resta l'unità di **prova**: ogni cifra si apre sulle righe che la sostengono, come oggi nella mappa.
- **La controversia è quella del database** (decisione del PI, 15/10/2026). I casi che il Climate Litigation Database riunisce in una stessa raccolta (bundle) contano come un caso solo; nessun legame dedotto dai nomi. Tabella in `n01_controversie.json`, rifatta da `tools/n01_controversie.py` sull'ultimo dump. Al 15/10 tocca solo Juliana v. United States: 8 schede, un caso.
- **Filtro di sensibilità «senza USA»** (15/10/2026). L'indice principale conta tutti gli atti; `--senza-usa` toglie gli atti di corti statunitensi (le decisioni citate restano) e serve da prova di robustezza, non da correzione.

### 2.2 Una scala ordinale di ricezione al posto di un prodotto di pesi

Per ogni coppia caso–decisione si registra il **gradino più alto** raggiunto:

| Gradino | Che cosa vuol dire | Regola sui campi (validato prima di proposto) |
|---|---|---|
| R1 Menzione | il nome compare, senza uso argomentativo | tipo menzione in catena, descrittiva o vuoto, e chi parla non è la corte |
| R2 Mobilitazione | una parte, un amicus o un interveniente la usa per argomentare | tipo sostanziale, distinguente o critica, e chi parla non è la corte |
| R3 Attenzione giudiziale | la corte la nomina | chi parla è la corte, fuori dal gradino R4 |
| R4 Ricezione giudiziale | la corte la usa nella motivazione | chi parla è la corte, sede in motivazione, tipo sostanziale, distinguente o critica |

Su Urgenda oggi i 141 casi stanno così: 26 in R1, 53 in R2, 32 in R3 e 30 in R4.

Perché una scala e non un peso moltiplicato:
- I tre fattori del brief (tipo × voce × atto, per esempio 0,8 × 0,4 × 0,6) danno numeri che nessuno sa leggere: che cosa vuol dire 0,19? Un gradino invece si dice in una frase e si verifica sul testo.
- Il prodotto presume che i fattori siano indipendenti e confrontabili su una sola scala, e non lo sono. Una corte che menziona soltanto e una parte che argomenta a fondo non stanno sulla stessa retta.
- Sull'ordine dei gradini c'è accordo (la motivazione di una corte pesa più del ricorso di una parte). Sulla loro distanza non ce n'è. La scala dichiara solo quello che sappiamo.
- Il tipo di atto non entra nella scala, perché è già dentro chi parla e la sede. Contarlo anche come fattore lo peserebbe due volte.

### 2.3 Tre misure separate, nessun numero unico come risultato principale

Per ogni decisione si pubblicano tre misure, e mai fuse in partenza:

- **Portata.** Casi e giurisdizioni che arrivano almeno a R1, e la curva cumulata per anni trascorsi dalla decisione.
- **Mobilitazione.** Casi che arrivano a R2 o più: quanto la decisione serve a chi litiga.
- **Ricezione giudiziale.** Casi che arrivano a R4, e corti distinte. È la misura che si avvicina di più all'influenza in senso stretto.

Un indice composto esiste solo come strumento di sensibilità (§3), mai come classifica di testa. La ragione è semplice: «quanto è influente» non è una domanda sola, e una sola cifra nasconderebbe proprio quello che il giurista vuole vedere.

### 2.4 Il segno resta fuori dalla misura

Distinguere o criticare una decisione è comunque un segno di influenza, quindi vale come uso argomentativo (R2 e R4). L'adesione o il distacco si mostrano a parte, come **profilo**: quota di adesioni, di distinzioni e di critiche fra i casi in R4. Su Urgenda le citazioni distinguenti sono 100 e le critiche 17. Messe dentro il peso, sparirebbero.

### 2.5 L'influenza di un principio

Un principio conta per un caso se almeno una riga di quel caso lo porta, al gradino più alto raggiunto da quelle righe.

- Le righe che portano più principi danno un caso a **ciascuno** dei principi, senza dividerlo. Divisione per n e punteggi della macchina restano come varianti di sensibilità. Il motivo è che dividere fa dipendere il peso di un principio da quanti altri la macchina ha attaccato alla stessa riga, il che è un artefatto della lettura.
- «Nessuno» e «altro» si contano e si mostrano, perché dicono quanta ricezione non si lega a un principio della decisione.
- Le righe con principi senza prova nel testo (`proposto_principi_senza_prova`) restano fuori dalla variante principale.
- I principi si confrontano **dentro** la stessa decisione, non fra decisioni diverse, perché i cataloghi dei principi sono diversi.

### 2.6 Confrontare decisioni di età e copertura diverse

- Ogni decisione porta la sua **copertura**, dichiarata accanto alla cifra: Urgenda è quasi completa, le altre cinque sono parziali.
- Il confronto si fa a **parità di anni dalla decisione** (casi a R4 entro 1, 2, 5 anni), mai sul totale.
- La serie per anno usa le date dei documenti già ricostruite per la mappa. Il campo `data` di `corpus_rows` è spesso solo l'anno del caso: per esempio, 168 righe di Urgenda hanno una data anteriore alla sentenza del 2015.

### 2.7 L'errore di lettura entra nella misura

La lettura della macchina sbaglia, quindi ogni cifra si accompagna alla sua incertezza:

- **Due conti sempre affiancati:** tutte le righe e solo le validate, con la quota validata.
- **Correzione per l'errore di classificazione.** Sulle righe validate si stima quanto spesso la proposta della macchina cambia gradino, cioè una matrice di confusione dei gradini. Poi si ricostruisce la distribuzione dei casi fra i gradini corretta per quell'errore, con un intervallo. Così le righe validate non servono solo da campione a parte, ma tarano tutte le altre.
- **Ricampionamento per casi** (bootstrap sui casi citanti) per l'incertezza di campionamento.

## 3. La sensibilità

È il cuore della proposta. Ci sono tre fonti di arbitrio, e ognuna si sottopone a prova.

1. **Le soglie della scala.** Si sposta il confine fra i gradini: la corte che cita fuori dalla motivazione conta come R4? La descrittiva conta come uso? Per ogni variante si riportano i casi in R4 e la classifica dei principi.
2. **I pesi, se si vuole un indice composto.** Non si fissano numeri. Si estraggono a caso migliaia di pesi che rispettano **solo l'ordine** dei gradini (R4 ≥ R3 ≥ R2 ≥ R1 ≥ 0), in modo uniforme su tutte le combinazioni ammesse. Per ogni decisione e per ogni principio si riporta la mediana, l'intervallo 5–95% e la **probabilità di restare nella stessa posizione**. Se un principio resta primo nel 95% delle estrazioni, lo si dice. Se cambia posto, si dice anche questo.
   - Alternativa scartata: moltiplicare pesi fissi per un fattore in [0,5; 1,5]. Esplora solo un intorno dei numeri scelti da noi, non tutte le scelte ragionevoli, e quindi fa sembrare stabile un risultato che dipende dalla prima scelta.
3. **La lettura.** Si rifanno le misure (a) togliendo le righe a bassa confidenza o col tipo incerto, (b) sulle sole validate, (c) con la correzione per l'errore del §2.7.

L'esito pubblicato è una tabella sola: per ogni affermazione («il principio X è il più ripreso dalle corti»), in quante delle varianti regge.

## 4. La rete

- **Oggi.** La rete è a due livelli: casi citanti → sei decisioni. È la rete che la mappa disegna già. Su questa rete misure come PageRank o hub/authority non hanno senso, perché i sei nodi citati non citano a loro volta, e quindi non si calcolano.
- **Fra le sei.** Gli archi in cui il caso citante è esso stesso una delle sei decisioni (per esempio KlimaSeniorinnen che cita Urgenda) si mostrano come grafo, senza misure.
- **Co-ricezione.** Quanti casi ricevono due decisioni insieme, al gradino R4 e a qualunque gradino, con l'indice di Jaccard. È sottostimata finché la copertura delle cinque decisioni è parziale, e lo si scrive.
- **Domani.** Le decisioni giudiziarie in R4 diventano a loro volta bersagli della ricerca per nome. Quando la rete ha un secondo livello, la centralità si calcola con la stessa scala e la stessa sensibilità.

## 5. Limiti, scritti prima dei risultati

- Il corpus non è l'universo delle decisioni. Raccoglie quello che il database di origine conserva, con più atti di parte per alcuni paesi e meno decisioni tradotte per altri. Le cifre descrivono la ricezione **nel corpus**.
- La citazione esplicita non è l'unica forma d'influenza. La rete semantica (riprese senza nome) entra, ma resta più incerta.
- La validazione è parziale e diseguale: dal 12% delle righe su Urgenda a meno dell'1% sul parere della Corte IDH.
- Una citazione dice che una decisione è stata usata, non che abbia causato l'esito. Le parole pubbliche lo dicono così.

## 6. Dove va

- **Sito.** Le tre misure e la tabella di sensibilità entrano nel pannello Numbers della mappa e nella scheda di ogni decisione. La scala R1–R4 diventa un filtro della mappa che già esiste. Niente vista separata.
- **Report tecnico.** Una sezione nuova con questo testo, le formule e la tabella di sensibilità.
- **Report non tecnico.** Una pagina sola: le tre domande (quanto arriva lontano, quanto serve a chi litiga, quanto le corti la usano) e perché non c'è una classifica unica.
- **Dati.** Una scheda N01 in `trace_versioni`, le misure in `trace_misure`, e lo sha256 dello script e del file delle soglie.

## 7. Da decidere col PI

1. La scala R1–R4 e i suoi confini.
2. Se pubblicare un indice composto (solo come prova di sensibilità) oppure nessuno.
3. Il confronto con Young: appena ho le sue slide, aggiungo una sezione su dove il nostro metodo coincide, dove diverge e perché.
