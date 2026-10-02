# Fascicolo del caso KlimaSeniorinnen

1 ottobre 2026, versione 1, PROPOSTA per il PI. Fonti usate: la sentenza del corpus (Corte europea dei diritti dell'uomo, Grande Camera, 9 aprile 2024, ricorso n. 53600/20, `verein-klimaseniorinnen-schweiz-and-others-v-switzerland-judgment_f4b1`, 260 pagine di PDF, testo inglese); `cited-cases/neubauer-fascicolo.md` e `cited-cases/neubauer-P05.yaml` come modello; i testi del corpus che citano la sentenza, letti attraverso i rinvii a paragrafo trovati da `conta_paragrafi.py`. Nessun giudizio umano, nessun file di addestramento o di prova. Ogni citazione fra virgolette e' stata ritrovata nel corpus con i soli spazi normalizzati; cio' che non vi si trova e' marcato «[non verificato nel corpus]». Pagina = marcatore `<!-- page N -->` del markdown, che coincide con la pagina del PDF; la numerazione stampata della sentenza e' la pagina del PDF meno 2. § = paragrafo della Corte (1-657).

Compagni: `klimaseniorinnen.yaml` (forme, sonde, canonical), `klimaseniorinnen-mappa-paragrafi.yaml` (tutti i paragrafi, uno per voce o per gruppo), `PROPOSTA.md` (riassunto e domande), `conta_paragrafi.py` (conteggi).

## 0. A che cosa serve e come leggerlo

Ti viene dato un passaggio di un ALTRO caso. Devi dire se riprende una proposizione di KlimaSeniorinnen (RIPRESA), se afferma qualcosa di simile fondandolo su un'altra fonte (ALTRA_FONTE), o se non la afferma (NON_AFFERMA).

Anelli della catena argomentativa:

- (a) Il cambiamento climatico non e' un danno ambientale classico: nessuna fonte unica, catena di effetti complessa, fonti in tutte le attivita' di base (§§ 414-418). Non si trasferisce la giurisprudenza ambientale: serve un approccio su misura (§ 422). La Corte assume come fatto che il cambiamento climatico esiste, minaccia gravemente i diritti, che gli Stati lo sanno e possono agire (§ 436).
- (b) Il controllo dei giudici e' complementare ai processi democratici e la prospettiva intergenerazionale lo giustifica (§§ 410-413, 419-421, 449-451).
- (c) Causalita': niente conditio sine qua non (§ 439). Ogni Stato ha la propria quota di responsabilita' e non si sottrae indicando gli altri; contro la «goccia nel mare» basta una prospettiva reale di cambiare l'esito (§§ 441-444).
- (d) Qualita' di vittima dei singoli: due criteri e soglia particolarmente alta (§§ 479-488). Legittimazione delle associazioni: tre condizioni, senza che i rappresentati debbano essere vittime (§§ 489-503).
- (e) L'art. 8 comprende un diritto alla protezione effettiva dagli effetti gravi del cambiamento climatico (§ 519). Lo Stato deve fare la sua parte: dovere primario di mitigazione, integrato dall'adattamento (§§ 544-546, 552). L'art. 2 resta aperto (§§ 507-513, 536-537).
- (f) Margine di apprezzamento differenziato: ridotto sull'impegno e sugli obiettivi, ampio sui mezzi (§ 543); valutazione d'insieme (§ 551); garanzie procedurali (§§ 553-554).
- (g) Requisiti del quadro regolatorio: neutralita' in circa tre decenni, bilancio di carbonio o quantificazione equivalente, obiettivi intermedi, prova del rispetto, aggiornamento, azione tempestiva e coerente (§§ 547-550).
- (h) Applicazione: lacune svizzere, nessun bilancio, obiettivi passati mancati; violazione dell'art. 8 (§§ 555-574).
- (i) Art. 6: l'azione dell'associazione per l'attuazione delle misure gia' previste dalla legge rientra nell'accesso al giudice; i giudici svizzeri non l'hanno esaminata; violazione (§§ 608-640).
- (l) Art. 46: nessuna misura specifica; lo Stato sceglie, sotto il Comitato dei Ministri (§ 657).

Cinque cose da tenere a mente sempre.

1. Le ricorrenti sono cinque, ma vince solo l'associazione. Le quattro donne non raggiungono la soglia della qualita' di vittima (§§ 527-535, dispositivo punto 5). Chi scrive che la Corte ha riconosciuto le donne anziane come vittime sbaglia il caso; chi scrive che ha riconosciuto la loro vulnerabilita' ma non la qualita' di vittima lo cita giusto (§ 531).
2. Il diritto e' quello dell'art. 8, non dell'art. 2. La Corte esamina il ricorso dell'associazione «from the angle of Article 8 alone» e ritiene non necessario esaminare l'applicabilita' dell'art. 2 (§ 537, dispositivo punto 6). Le pagine sull'art. 2 (§§ 507-513) sono principi, non decisione.
3. La Corte non fissa nessuna cifra e nessuna misura. Non dice quale percentuale ne' quale bilancio: dice che un bilancio, o una quantificazione equivalente, deve esistere (§§ 550 (a), 570, 572). Non indica misure ex art. 46 (§ 657). E' la differenza netta con Urgenda, dove il minimo lo fissa il giudice.
4. Il bilancio di carbonio viene da Neubauer. Il § 571 lo dice: «The Court also finds convincing the reasoning of the GFCC, which rejected the argument that it was impossible to determine the national carbon budget, pointing to, inter alia, the principle of common but differentiated responsibilities under the UNFCCC and the Paris Agreement (see Neubauer and Others, cited in paragraph 254 above, paragraphs 215-29).» Chi riprende di qui il bilancio nazionale riprende Neubauer in forma annidata (5.4).
5. Lo stesso giorno la stessa Grande Camera ha deciso Duarte Agostinho c. Portogallo e 32 Stati e Carême c. Francia, entrambi irricevibili (§ 5). Le tre pronunce si citano insieme; i numeri di paragrafo di ciascuna sono propri (Duarte §§ 202-03, citati dal § 442, sono di Duarte).

## 1. La pronuncia

### 1.1 Identita', struttura, numerazione

Corte europea dei diritti dell'uomo, Grande Camera, sentenza del 9 aprile 2024, Verein KlimaSeniorinnen Schweiz and Others v. Switzerland, ricorso n. 53600/20, presieduta da Síofra O'Leary (p. 233). Adottata il 14 febbraio 2024 (§ 556, che fissa a quella data lo stato della legislazione esaminata). Udienza pubblica il 29 marzo 2023 (§ 9). Ricorso depositato il 26 novembre 2020 (§ 289); rimessione alla Grande Camera il 26 aprile 2022 (§ 4). La sentenza e' resa «in English and in French» (p. 233); nel corpus c'e' solo l'inglese. ECLI:CE:ECHR:2024:0409JUD005360020, non scritto nella sentenza ma usato da 9 documenti del corpus.

Ricorrenti: l'associazione Verein KlimaSeniorinnen Schweiz, oltre 2.000 socie residenti in Svizzera, eta' media 73 anni, quasi 650 sopra i 75 (§ 521), e quattro socie (§§ 12-21; la seconda e' morta durante il giudizio e il figlio prosegue, §§ 273-274). Lamentele: omissioni delle autorita' svizzere nella mitigazione (artt. 2 e 8), mancato accesso al giudice (art. 6), mancanza di un ricorso effettivo (art. 13) (§ 3).

Struttura: sommario della Cancelleria (pp. 1-2, «Does not bind the Court»); indice (pp. 3-9); procedura (§§ 1-9); fatti: ricorrenti e giudizio svizzero (§§ 10-63), fatti sul clima (§§ 64-120); quadro giuridico interno, internazionale, europeo, comparato (§§ 121-272); diritto: questioni preliminari (§§ 273-290), osservazioni introduttive (§§ 291-297), artt. 2 e 8 (tesi §§ 298-409, valutazione §§ 410-574), art. 6 (§§ 575-640), art. 13 (§§ 641-645), artt. 41 e 46 (§§ 646-657); dispositivo (pp. 232-233); voto in parte concorde e in parte dissenziente del giudice Eicke (pp. 235-260, numerazione propria).

Dispositivo (pp. 232-233), in sintesi: legittimazione dell'associazione ed esame sotto il solo art. 8 (16 voti a 1); qualita' di vittima delle quattro ricorrenti respinta e loro ricorsi irricevibili (unanimita'); art. 2 non esaminato (unanimita'); violazione dell'art. 8 (16 a 1); art. 6 § 1 applicabile all'associazione (16 a 1) e violato (unanimita'); art. 13 assorbito; 80.000 euro di spese.

### 1.2 Percorso

Giudizio svizzero (§§ 22-63). Il 25 novembre 2016 le ricorrenti chiedono al Consiglio federale e a tre uffici, in base all'art. 25a della legge sulla procedura amministrativa, di porre fine a omissioni nella protezione del clima (§ 22). Il DATEC respinge il 25 aprile 2017 per difetto di legittimazione (§ 28). Il Tribunale amministrativo federale respinge il ricorso il 27 novembre 2018: le ricorrenti non sono toccate piu' del resto della popolazione, l'azione e' popolare (§§ 34, 42). Il Tribunale federale respinge il 5 maggio 2020: i diritti non sono toccati con intensita' sufficiente, il limite «ben sotto 2 gradi» non sarebbe superato a breve, la via e' politica (§§ 52, 56-60); artt. 6 e 13 non applicabili (§§ 61-62).

Fatti sul clima (§§ 64-120). Le tesi delle ricorrenti sull'aumento della mortalita' da calore delle donne anziane (§§ 65-68) e sulle misure svizzere; le tesi del Governo; poi i fatti che la Corte trae soprattutto dall'IPCC (§§ 103-120), fra cui l'importanza dei bilanci di carbonio (§ 116) e la «rapidly closing window of opportunity» (§ 118). Quadro comparato (§§ 235-272): Francia, Germania (Neubauer, §§ 254-257, con le massime ufficiali), Irlanda, Paesi Bassi (Urgenda, §§ 260-261), Norvegia, Spagna, Regno Unito, Belgio.

Questioni preliminari (§§ 273-290). Le emissioni «incorporate» nelle merci importate (circa il 70% dell'impronta svizzera nel 2015) rientrano nel ricorso (§§ 279-283); non pongono una questione di giurisdizione ex art. 1, perche' le ricorrenti risiedono in Svizzera, ma di responsabilita' (§ 287).

Considerazioni generali (§§ 410-457). Il cambiamento climatico e' «one of the most pressing issues of our times» e pone una questione di ripartizione dei pesi fra generazioni (§ 410). «Judicial intervention, including by this Court, cannot replace or provide any substitute for the action which must be taken by the legislative and executive branches of government. However, democracy cannot be reduced to the will of the majority of the electorate and elected representatives, in disregard of the requirements of the rule of law.» (§ 412). Cinque differenze dal danno ambientale classico (§§ 415-421) e quindi un approccio su misura: «it would be neither adequate nor appropriate to follow an approach consisting in directly transposing the existing environmental case-law to the context of climate change.» (§ 422). Le generazioni future porteranno pesi crescenti senza partecipare alle decisioni; la prospettiva intergenerazionale aggiunge una giustificazione al controllo giudiziario (§ 420). Causalita' in quattro dimensioni (§§ 424-426); prova, con il peso particolare dei rapporti IPCC (§§ 427-430); effetti sui diritti e strumento vivente (§§ 431-434); l'art. 8 e' toccato anche dai rischi (§ 435); la Corte assume come fatto che «there are sufficiently reliable indications that anthropogenic climate change exists, that it poses a serious current and future threat to the enjoyment of human rights guaranteed under the Convention, that States are aware of it and capable of taking measures to effectively address it» (§ 436). Nesso causale tenue: niente «strict conditio sine qua non» (§ 439). Quota propria: «The Court considers that a respondent State should not evade its responsibility by pointing to the responsibility of other States, whether Contracting Parties to the Convention or not.» (§ 442), coerente con la responsabilita' concorrente (§ 443); contro la «goccia nel mare»: «what is important, and sufficient to engage the responsibility of the State, is that reasonable measures which the domestic authorities failed to take could have had a real prospect of altering the outcome or mitigating the harm» (§ 444). Nessun diritto all'ambiente in quanto tale (§§ 445-448). La competenza: «the Court’s competence in the context of climate-change litigation cannot, as a matter of principle, be excluded» e «the question is no longer whether, but how, human rights courts should address the impacts of environmental harms on the enjoyment of human rights» (§ 451). Interpretazione armonica ed evolutiva, nei limiti della sussidiarieta' (§§ 452-457).

Ammissibilita': qualita' di vittima e legittimazione (§§ 458-503). Dopo la ricapitolazione dei principi generali (§§ 460-477), il nesso causale «legally relevant» fra omissioni dello Stato e danno (§ 478). Poi la qualita' di vittima nel clima: numero indefinito di colpiti e omissioni nelle misure generali (§§ 479-480); il problema dell'actio popularis (§§ 481-484); la categoria delle vittime potenziali come «class of people» non serve (§ 485); i due criteri del § 487: «the applicant must be subject to a high intensity of exposure to the adverse effects of climate change» e «(b) there must be a pressing need to ensure the applicant’s individual protection, owing to the absence or inadequacy of any reasonable measures to reduce harm.»; e il § 488: «The threshold for fulfilling these criteria is especially high.» Per le associazioni: importanza dell'azione collettiva e di Aarhus (§§ 489-494), distinzione fra vittima e rappresentanza (§§ 495-498), clima come preoccupazione comune e ripartizione fra generazioni (§ 499), niente lagnanza astratta (§§ 500-501), le tre condizioni del § 502 e la regola che «the standing of an association to act on behalf of the members or other affected individuals within the jurisdiction concerned will not be subject to a separate requirement» di mostrare la qualita' di vittima dei rappresentati; il § 503 sul rilievo dell'accesso al giudice dei membri.

Applicabilita' (§§ 506-537). Art. 2: attivita' per sua natura pericolosa per la vita (§ 509); rischio «real and imminent» letto alla luce dell'irreversibilita' (§§ 511-513), e se la qualita' di vittima e' accertata «a serious risk of a significant decline in a person’s life expectancy owing to climate change ought also to trigger the applicability of Article 2.» (§ 513). Art. 8: ricapitolazione (§§ 514-518) e poi il diritto (§ 519, canonical di C); applicabilita' secondo i criteri di vittima e di legittimazione (§ 520). Applicazione: l'associazione soddisfa le tre condizioni, anche perche' le singole non hanno avuto accesso a un giudice (§§ 521-526); le quattro donne no (§§ 527-535); l'art. 2 non si esamina (§§ 536-537).

Merito dell'art. 8 (§§ 538-574). Ricapitolazione dei principi ambientali (§§ 538-541). La protezione del clima pesa in modo considerevole (§ 542). Margine differenziato (§ 543, canonical di D). Il diritto e il dovere: «Accordingly, the State’s obligation under Article 8 is to do its part to ensure such protection. In this context, the State’s primary duty is to adopt, and to effectively apply in practice, regulations and measures capable of mitigating the existing and potentially irreversible, future effects of climate change.» (§ 545). Prevenire aumenti di temperatura oltre livelli dannosi (§ 546); ogni Stato definisce il proprio percorso (§ 547); riduzione sostanziale e progressiva verso la neutralita' «within, in principle, the next three decades», e «it is incumbent on the public authorities to act in good time, in an appropriate and consistent manner» (§ 548); «in order for this to be genuinely feasible, and to avoid a disproportionate burden on future generations, immediate action needs to be taken and adequate intermediate reduction goals must be set for the period leading to net neutrality.» (§ 549); i cinque requisiti (§ 550, canonical di E); valutazione d'insieme (§ 551); adattamento (§ 552); garanzie procedurali (§§ 553-554). Applicazione: basta la mitigazione (§ 555); legge sul CO2 del 2011 con meno 20% al 2020, gia' insufficiente per il Consiglio federale nel 2009, e obiettivo mancato con circa meno 11% (§§ 558-559); revisione respinta al referendum del giugno 2021 e vuoto dopo il 2024 (§§ 560-562); NDC 2021 e legge sul clima del 30 settembre 2022, confermata il 18 giugno 2023 ma non in vigore, senza misure concrete e con il 2025-2030 scoperto (§§ 563-568); bilancio: la stima dell'associazione (0,44 Gt di CO2 per il 67% di probabilita' di stare entro 1,5 gradi, § 569), il Governo non ne ha uno e «the Court is not convinced that an effective regulatory framework concerning climate change could be put in place without quantifying, through a carbon budget or otherwise, national GHG emissions limitations» (§ 570); Neubauer e i bilanci indicativi della legge europea sul clima (§ 571); conclusione sul bilancio (§ 572). Conclusione: «By failing to act in good time and in an appropriate and consistent manner regarding the devising, development and implementation of the relevant legislative and administrative framework, the respondent State exceeded its margin of appreciation and failed to comply with its positive obligations in the present context.» (§ 573). Violazione (§ 574).

Art. 6 (§§ 575-640). Ricapitolazione dei principi (§§ 590-607): l'art. 6 non garantisce un giudice che annulli le leggi (§ 594). Nel clima i principi restano ma si applicano secondo la specificita' (§ 608): niente azione per costringere il Parlamento a legiferare (§ 609); un danno futuro «real and highly probable» non deve essere strettamente imminente, e cio' vale specialmente per le associazioni (§ 614). Applicazione: la parte dell'azione sull'attuazione delle misure gia' previste dalla legge rientra nell'art. 6 (§§ 615-616, canonical della riserva); l'associazione ha un legame diretto e sufficiente con i diritti delle socie (§§ 618, 621-623); per le singole l'esito non era direttamente decisivo (§§ 624-625). Merito: i giudici svizzeri non hanno esaminato le prove scientifiche ne' la legittimazione dell'associazione (§§ 635-636), nessun'altra via (§ 637), «its right of access to a court was restricted in such a way and to such an extent that the very essence of the right was impaired.» (§ 638); «the Court considers it essential to emphasise the key role which domestic courts have played and will play in climate-change litigation» (§ 639). Violazione (§ 640).

Art. 13, 41 e 46 (§§ 641-657). Art. 13 assorbito per l'associazione (§ 644). 80.000 euro per le spese (§ 650). Art. 46: «the Court is unable to be detailed or prescriptive as regards any measures to be implemented in order to effectively comply with the present judgment.» (§ 657), dato il margine differenziato del § 543.

Voto separato del giudice Eicke (pp. 235-260). Dissente sul metodo e sui limiti dell'interpretazione evolutiva, sull'estensione della qualita' di vittima e della legittimazione, e sulla «creazione» di un nuovo diritto sotto l'art. 8 (cita i §§ 519, 544 e 545); vota per la violazione dell'art. 6 con un ragionamento diverso (p. 235). Ha una numerazione propria: un «§ 4» o un «§ 30» di Eicke non e' un paragrafo della sentenza.

### 1.3 Fondamento

Convenzione: art. 8 (unico parametro del merito), art. 34 (qualita' di vittima e legittimazione), art. 6 § 1, art. 1 (giurisdizione, emissioni incorporate), artt. 13, 41, 46. Diritto internazionale come contesto interpretativo: UNFCCC (art. 3 § 1 per le responsabilita' comuni ma differenziate, art. 3 § 3 per la precauzione: §§ 442, 444), Accordo di Parigi (art. 2 § 2, obiettivi globali che «cannot of themselves suffice as a criterion», § 547), Patto di Glasgow e Piano di Sharm el-Sheikh (§ 442), Articoli della CDI sulla responsabilita' (art. 47, § 443), Convenzione di Aarhus (§§ 490-494, 501, 602), Risoluzione 76/300 sul diritto a un ambiente sano (§ 448). Scienza: i rapporti IPCC (§§ 103-120, 429, 436), con i bilanci di carbonio al § 116. Giurisprudenza propria richiamata: Câmpeanu e Gorraiz Lizarraga (associazioni), Tătar, Di Sarno, Jugheli, Hardy and Maile, Cordella, Hatton (ambiente), O'Keeffe e Baljak (prospettiva reale), Zubac (accesso al giudice), H.F. c. Francia (art. 46). Giurisprudenza nazionale citata nella valutazione: solo Neubauer, al § 571 (e i §§ 253 e 257 al § 441); Urgenda compare nella parte comparata (§§ 260-261) ma non nella valutazione [controllato cercando «Urgenda» nei §§ 410-657: nessuna occorrenza].

### 1.4 Le sette sonde

> **Sonde distintive (il PI, 01/10/2026).** Una sonda e' l'elemento PROPRIO della sentenza, cio' che la distingue dalle altre fonti: serve a riconoscerne la provenienza quando un atto lo riprende. Per questo F non e' piu' «ogni Stato risponde della propria quota» (lo dicono Urgenda, Neubauer e il § 442 stesso) ma il criterio causale del § 444, la possibilita' reale di cambiare l'esito; e H non e' piu' il controllo dei giudici in generale ma il suo fondamento intergenerazionale, § 420. I §§ 410-413, 419, 421, 439-443, 449-451 e 639 restano senza sonda.

| Sonda | Anello | Paragrafi | Canonical | Pagina |
|---|---|---|---|---|
| vittima_soglia_alta (A) | d | §§ 479-488, 527-535 | § 527 | 199 |
| legittimazione_associazioni (B) | d | §§ 489-503, 521-526 | § 502 | 193 |
| art8_protezione_effettiva (C) | e | §§ 435-436, 478, 519-520, 544-546, 552 | § 519 (bis § 545) | 198 (206) |
| margine_differenziato (D) | f, l | §§ 542-543, 551, 553-554, 657 | § 543 | 205 |
| requisiti_quadro_regolatorio (E) | g, h | §§ 547-550, 555, 558-573 | § 550 | 207 |
| possibilita_reale (F) | c | § 444 | § 444 | 178 |
| prospettiva_intergenerazionale (H) | b | § 420 | § 420 | 171 |
| riserva: accesso_giudice_associazione (G) | i | §§ 608-625, 629-638 | § 616 | 223 |

Gli intervalli non si sovrappongono. Perche' certi paragrafi stanno dove stanno:

- §§ 435-436 e 478 vanno all'art. 8 (C) e non alla parte generale o alla qualita' di vittima: il § 519 li richiama espressamente come fondamento del diritto («see paragraphs 435, 436 and 478 above»), e il § 545 richiama i §§ 435 e 519.
- § 499 resta alle associazioni (B), benche' la sua frase centrale sia di merito (gli Stati devono proteggere anche chi sara' colpito in futuro): apertura e conclusione riguardano la legittimazione. Nel corpus e' citato anche per l'urgenza, insieme al § 436 (Greenpeace Nordic c. Norvegia, Corte EDU). Domanda al PI.
- § 551 (valutazione d'insieme) e §§ 553-554 (garanzie procedurali) vanno al margine (D): entrambi sono formulati dalla Corte come misura del rispetto del margine («overstepped its relevant margin», § 551; «especially material in determining whether the respondent State has remained within its margin of appreciation», § 553).
- § 657 va al margine (D): la ragione per non indicare misure e' il «differentiated margin of appreciation» del § 543.
- § 639 (ruolo dei giudici nazionali nel contenzioso climatico) resta senza sonda: non dice nulla di proprio della sentenza.
- §§ 439-443 (nesso tenue, quota propria, responsabilita' concorrente) restano senza sonda: la quota propria e' di Urgenda. La sonda F e' solo il § 444. Il § 440 (soglia di gravita' del rischio) resta senza sonda.

Assi non promossi a sonda, ma da riconoscere: l'approccio su misura (§§ 414-418, 422); la prova e il peso dell'IPCC (§§ 427-434); l'art. 2 (§§ 507-513, 536-537); le emissioni incorporate (§§ 279-287); l'accesso al giudice (riserva G). Le ricapitolazioni (§§ 460-477, 514-518, 538-541, 590-607, 626-628, 652-656) non portano sonde: riassumono la giurisprudenza precedente.

### 1.5 Punti di confine

- Vittime: le donne NON sono vittime (§§ 533-535). La loro appartenenza a un gruppo particolarmente esposto «would not, in itself, be sufficient» (§ 531). Chi cita il caso per dire che le anziane sono vittime del clima sbaglia; chi lo cita per la soglia alta lo cita giusto.
- Associazioni: legittimazione come rappresentanti, non come vittime (§§ 496, 498). L'associazione non puo' invocare la propria salute (§ 496).
- Art. 2: non esaminato (§ 537). Il § 513 e' un principio condizionale («ought also to trigger»), non una decisione.
- Nessuna cifra: la Corte non dice di quanto ridurre ne' quale bilancio (§§ 550, 572, 657). Chi scrive che la Corte ha imposto alla Svizzera un bilancio o una percentuale sbaglia; le cifre dei §§ 558-569 sono fatti svizzeri o stime dell'associazione.
- Margine: ridotto solo sugli obiettivi; sui mezzi resta ampio (§ 543), anche dopo un referendum (§ 561). Chi cita il caso per dire che lo Stato non ha piu' margine in materia climatica lo cita male.
- Giurisdizione: le emissioni incorporate non pongono una questione di giurisdizione extraterritoriale (§ 287). La questione extraterritoriale e' decisa in Duarte Agostinho, non qui.
- Art. 6: solo per l'attuazione delle misure gia' previste dalla legge, non per le richieste di legiferare (§§ 615-616). Solo per l'associazione (§§ 623-625).

## 2. La mappa dei paragrafi

Per decifrare un rinvio preciso. La mappa completa, leggibile da macchina, e' in `klimaseniorinnen-mappa-paragrafi.yaml` (111 voci, tutti i paragrafi 1-657 piu' dispositivo e voto separato).

### 2.1 Come leggere un rinvio

- Numeri da 1 a 657 = paragrafi della sentenza. Le forme osservate nel corpus: «§ 550», «§§ 487-488», «§550, 570 and 573», «para. 543», «paras. 439 to 444», «¶ 545», «párr. 429», «par. 431», «r.o. 420» (rechtsoverweging, nei testi olandesi), «Rn. 550» (memorie tedesche), «bodu 542» (ceco), «at [507]–[509]» (Nuova Zelanda, Australia). Intervalli abbreviati: «§§ 487-88» = 487-488.
- Gli intervalli larghi («§§ 410-51», «paras 436–574», «§§ 133-231») citano una sezione, non un principio: in `conta_paragrafi.py` sono contati a parte (rinvii «puntuali» = al piu' 15 paragrafi).
- La versione francese ha la stessa numerazione [non verificato nel corpus: il francese non c'e'].
- Il voto di Eicke ha numeri propri, piccoli; le pagine stampate della sentenza (1-232) sono la pagina del PDF meno 2.
- Rinvii a Duarte Agostinho (§§ 1-230 circa) e Carême, decisi lo stesso giorno, stanno spesso nella stessa nota: un «§ 213» dopo «Duarte» e' di Duarte. Lo script tronca la finestra al nome di un altro caso.
- Errori ricorrenti: «53600/02» e «53600:20» (negli atti del caso stesso), «Klirnaseniorinnen» (OCR, Uniterre).
- Prima del 9/4/2024 un rinvio a paragrafi non puo' riguardare la sentenza: riguarda il ricorso, le osservazioni o le sentenze svizzere.

### 2.2 Tavola essenziale

| §§ | Pagine | Contenuto | Sonda |
|---|---|---|---|
| 1-409 | 10-167 | Procedura, fatti, diritto applicabile, tesi delle parti e degli intervenienti | nessuna |
| 410-413 | 168-169 | Clima come questione urgente; complementarita' fra giudici e democrazia | - |
| 414-418, 422-423 | 169-172 | Differenze dal danno ambientale classico; approccio su misura | nessuna |
| 419-421 | 170-171 | Problema policentrico; prospettiva intergenerazionale e controllo giudiziario | H solo il § 420 |
| 424-434 | 172-175 | Causalita', prova, IPCC, strumento vivente | nessuna |
| 435-436 | 175 | Art. 8 e rischi; i fatti assunti dalla Corte | C |
| 437-438, 440 | 175-176 | Causalita' e obblighi positivi; soglia di gravita' | nessuna |
| 439, 441-444 | 176-178 | Nesso tenue; quota propria; «drop in the ocean» | F solo il § 444 |
| 445-448 | 178-179 | Nessun diritto all'ambiente in quanto tale | nessuna |
| 449-451 | 179-180 | Diritto e politica; competenza non esclusa | - |
| 452-477 | 180-186 | Interpretazione; principi generali su vittime e associazioni | nessuna |
| 478 | 186 | Nesso causale giuridicamente rilevante | C |
| 479-488 | 186-189 | Qualita' di vittima nel clima: due criteri, soglia alta | A |
| 489-503 | 189-194 | Legittimazione delle associazioni: tre condizioni | B |
| 504-518 | 194-198 | Obiezioni; art. 2 nel clima; art. 8 (ricapitolazione) | nessuna |
| 519-520 | 198 | Diritto alla protezione effettiva ex art. 8 | C |
| 521-526 | 198-199 | Applicazione: l'associazione ha legittimazione | B |
| 527-535 | 199-201 | Applicazione: le quattro donne non sono vittime | A |
| 536-541 | 201-205 | Art. 2 non esaminato; principi ambientali (ricapitolazione) | nessuna |
| 542-543 | 205 | Peso della protezione del clima; margine differenziato | D |
| 544-546 | 205-206 | Diritto, «do its part», dovere primario di mitigazione | C |
| 547-550 | 206-207 | Percorso proprio, tre decenni, obiettivi intermedi, cinque requisiti | E |
| 551 | 207 | Valutazione d'insieme | D |
| 552 | 207-208 | Adattamento | C |
| 553-554 | 208 | Garanzie procedurali | D |
| 555, 558-573 | 208-213 | Applicazione e conclusione sull'art. 8 | E |
| 574 | 213 | Violazione dell'art. 8 | nessuna |
| 575-607, 626-628 | 213-226 | Art. 6: tesi e principi generali | nessuna |
| 608-625, 629-638 | 221-228 | Art. 6 nel clima e applicazione | riserva G |
| 639 | 228-229 | Ruolo chiave dei giudici nazionali | - |
| 640-656 | 229-231 | Violazione art. 6; artt. 13, 41, 46 | nessuna |
| 657 | 232 | Nessuna misura specifica, margine differenziato | D |

## 3. Le frasi piu' riprese, verbatim

Tutte dal testo inglese `judgment_f4b1`, ritrovate con i soli spazi normalizzati.

1. § 519, p. 198: «Article 8 must be seen as encompassing a right for individuals to effective protection by the State authorities from serious adverse effects of climate change on their life, health, well-being and quality of life.»
2. § 545, p. 206: «Accordingly, the State’s obligation under Article 8 is to do its part to ensure such protection. In this context, the State’s primary duty is to adopt, and to effectively apply in practice, regulations and measures capable of mitigating the existing and potentially irreversible, future effects of climate change.»
3. § 543, p. 205 (ultime due frasi): «As regards the former aspect, the nature and gravity of the threat and the general consensus as to the stakes involved in ensuring the overarching goal of effective climate protection through overall GHG reduction targets in accordance with the Contracting Parties’ accepted commitments to achieve carbon neutrality, call for a reduced margin of appreciation for the States. As regards the latter aspect, namely their choice of means, including operational choices and policies adopted in order to meet internationally anchored targets and commitments in the light of priorities and resources, the States should be accorded a wide margin of appreciation.»
4. § 550 (a), p. 207: «adopt general measures specifying a target timeline for achieving carbon neutrality and the overall remaining carbon budget for the same time frame, or another equivalent method of quantification of future GHG emissions, in line with the overarching goal for national and/or global climate-change mitigation commitments».
5. § 549, p. 207: «in order for this to be genuinely feasible, and to avoid a disproportionate burden on future generations, immediate action needs to be taken and adequate intermediate reduction goals must be set for the period leading to net neutrality.»
6. § 570, p. 212: «the Court is not convinced that an effective regulatory framework concerning climate change could be put in place without quantifying, through a carbon budget or otherwise, national GHG emissions limitations».
7. § 488, p. 189: «The threshold for fulfilling these criteria is especially high.»
8. § 442, p. 177: «The Court considers that a respondent State should not evade its responsibility by pointing to the responsibility of other States, whether Contracting Parties to the Convention or not.»
9. § 444, p. 178: «what is important, and sufficient to engage the responsibility of the State, is that reasonable measures which the domestic authorities failed to take could have had a real prospect of altering the outcome or mitigating the harm».
10. § 436, p. 175: «there are sufficiently reliable indications that anthropogenic climate change exists, that it poses a serious current and future threat to the enjoyment of human rights guaranteed under the Convention, that States are aware of it and capable of taking measures to effectively address it».
11. § 451, p. 180: «the question is no longer whether, but how, human rights courts should address the impacts of environmental harms on the enjoyment of human rights».
12. § 573, p. 213: «By failing to act in good time and in an appropriate and consistent manner regarding the devising, development and implementation of the relevant legislative and administrative framework, the respondent State exceeded its margin of appreciation and failed to comply with its positive obligations in the present context.»

## 4. Il mondo intorno: le fonti concorrenti e chi cita

### 4.1 Urgenda (Rechtbank 2015, Gerechtshof 2018, Hoge Raad 2019)

Riassunta ai §§ 260-261, non citata nella valutazione. Le stesse conclusioni in altra forma: obblighi positivi degli artt. 2 e 8 contro il rischio climatico (il principio di Urgenda sugli obblighi positivi, vicino a C); la propria quota (il principio di Urgenda della propria quota, Hoge Raad 5.7.5-5.7.8: ora NON e' una sonda di questo caso, la F e' solo il § 444). Differenze nette: in Urgenda il giudice fissa il minimo (25% al 2020); qui la Corte non fissa nulla e lascia ampio margine sui mezzi. Un testo che dice «each country is responsible for its own share» citando la Hoge Raad e' ALTRA_FONTE; con «drop in the ocean», «real prospect» o «common but differentiated responsibilities» e il § 442 o 444 e' KlimaSeniorinnen.

### 4.2 Neubauer (BVerfG, 24 marzo 2021)

Riassunta ai §§ 254-257 con le massime ufficiali; citata nella valutazione al § 571 (bilancio di carbonio, Rn. 215-229) e richiamata al § 441 (rinvio ai §§ 253 e 257). Due vicinanze: il bilancio nazionale (il principio di Neubauer sul budget residuo, contro E), e la ragione istituzionale del controllo (Neubauer Rn. 206, cicli elettorali e generazioni senza voce, contro H). Nel fascicolo di Neubauer (4.2) KlimaSeniorinnen e' gia' segnato come falso amico: le due cartelle devono dire la stessa cosa da lati opposti.

### 4.3 Duarte Agostinho c. Portogallo e 32 Stati; Carême c. Francia (Corte EDU, GC, 9 aprile 2024)

Stessa composizione, stesso giorno (§ 5), entrambi irricevibili. KlimaSeniorinnen cita Duarte ai §§ 287 e 442-443. Duarte cita KlimaSeniorinnen per i §§ 410-422, 487-488, 544-554 (rinvii trovati nel corpus); Carême per i §§ 487-488 (la qualita' di vittima). Chi applica i due criteri citando Carême riprende KlimaSeniorinnen in forma annidata. La negazione della giurisdizione extraterritoriale e' di Duarte, non di questa sentenza.

### 4.4 Il giudizio svizzero (DATEC 2017, Tribunale amministrativo federale A-2992/2017, Tribunale federale 1C_37/2019)

Nel corpus sotto un case_id proprio (11 documenti), escluso. Le sue tesi (azione popolare, toccate non piu' del resto della popolazione, c'e' ancora tempo) sono quelle che la Corte respinge (§§ 618, 635). Un testo che le enuncia riprende la polarita' opposta.

### 4.5 La Corte EDU dopo il 9 aprile 2024

Nel corpus citano la sentenza con rinvii a paragrafo: Greenpeace Nordic c. Norvegia (sentenza, 25 rinvii: §§ 436 e 499, 502, 527, 543, 550, 554, 555), Engels c. Germania (§ 519), De Conto c. Italia e Uricchio c. Italia (§§ 487-88, 513), Müllner c. Austria (comunicato: §§ 460-472, 478-488, 527-535, 538-574, 594-640), il ricorso Klimatická žaloba ČR c. Repubblica ceca (§§ 502, 541, 546, 549, 550, 573, 619). Sono riprese da parte dello stesso giudice: contano come RIPRESA se la Corte adotta il principio.

### 4.6 Corti nazionali e atti nazionali

Con rinvii a paragrafo (conteggio dello script): Greenpeace Paesi Bassi e otto cittadini di Bonaire c. Paesi Bassi (decisione 51 rinvii, memoria 25; quasi tutte le sonde), le due memorie di Greenpeace e Germanwatch al Bundesverfassungsgericht (§§ 538, 543, 550, 569, 573 fra gli altri), Steinmetz e altri c. Germania III (Rn. 473, 475, 479, 490, 498 fra gli altri), Milieudefensie c. ING (§§ 420, 434, 436, 439-444, 478, 519), Hugues Falys e altri c. TotalEnergies (§§ 410, 412, 429, 436, 439-440, 444, 546-553, 571-574), Uniterre c. DATEC (§§ 439, 478, 496, 502, 573), Asmania c. Holcim (§ 435), Coolglass c. An Bord Pleanála (§ 573), Smith c. Attorney-General (§§ 439, 507-509, 573), Aurora, Anton Foley c. Svezia (§§ 594, 607-609, 627), Klimatická žaloba ČR (Corte municipale di Praga, § 542), Poslední generace c. Praga (§ 499), We Are Nature Brussels (§ 462), Liao e altri e Lee e altri (Taiwan, §§ 434, 442, 548, 550, 569), Denman (Australia, «at [315], [444]», «at [415]-[417]»). Gli esiti di questi giudizi non sono stati verificati per questo fascicolo.

### 4.7 Pareri consultivi

Le richieste e gli atti dei pareri della Corte africana, della Corte interamericana (OC-32/25) e della Corte internazionale di giustizia citano la sentenza: §§ 410, 420, 429, 431, 436, 442, 444, 499, 519, 545-552 fra gli altri. Se i pareri stessi la riprendano e come [non verificato nel corpus per questo fascicolo].

### 4.8 IPCC, UNFCCC, Parigi, Aarhus

L'IPCC e' la fonte dei fatti (§§ 103-120, 429, 436): chi cita i dati IPCC cita l'IPCC. Le responsabilita' comuni ma differenziate sono dell'UNFCCC e di Parigi (§ 442): ALTRA_FONTE se il testo non usa la quota propria nel senso del § 442. La legittimazione ampia delle ONG ambientaliste e' di Aarhus e del diritto UE (§§ 490-494), che la Corte usa come riferimento ma non applica (§ 501).

## 5. Come si riconosce una ripresa

### 5.1 Indizi forti

- Nome, 53600/20, ECLI, «Verein KlimaSeniorinnen», «Aînées pour le climat», o una forma di `klimaseniorinnen.yaml`; «the Strasbourg Court» o «ECtHR» con data 9/4/2024 in contesto climatico.
- Un paragrafo della tavola senza nome: decifralo con 2.1.
- Le formule della sezione 3: «high intensity of exposure», «pressing need to ensure ... individual protection», «especially high», «genuinely qualified and representative», «effective protection by the State authorities from serious adverse effects of climate change», «do its part», «primary duty», «reduced margin» con «wide margin» e la coppia obiettivi/mezzi, «overall remaining carbon budget» con «equivalent method of quantification», «intermediate ... reduction targets and pathways», «act in good time, in an appropriate and consistent manner», «disproportionate burden on future generations», «drop in the ocean» con «real prospect», «no longer whether, but how».
- Due o piu' anelli nell'ordine della sentenza (vittima e legittimazione, poi art. 8, poi margine, poi requisiti).

### 5.2 Falsi amici

Urgenda (artt. 2 e 8, propria quota, minimo fissato dal giudice); Neubauer (bilancio nazionale, liberta' intertemporale, generazioni future senza voce); Duarte Agostinho (giurisdizione, esaurimento); Carême (stessi criteri di vittima, applicati: annidata); la giurisprudenza ambientale della Corte (Tătar, Cordella, Hatton, Jugheli: obblighi positivi, margine ampio); Aarhus e CJEU (legittimazione delle ONG); IPCC (cifre e bilanci); UNFCCC e Parigi (responsabilita' differenziate, soglie). Polarita': chi enuncia le tesi respinte (azione popolare, nessun effetto individuale, c'e' ancora tempo, «drop in the ocean», nessun metodo per il bilancio, solo via politica) non riprende la sentenza; chi le respinge con le parole della sentenza si'.

### 5.3 Casi incerti

- Bilancio di carbonio dopo il 9/4/2024: con «overall remaining carbon budget», «or another equivalent method of quantification», i cinque requisiti o 53600/20 e' KlimaSeniorinnen; con «remaining national CO2 budget», «albeit not precisely quantifiable», «special duty of care» e' Neubauer.
- Generazioni future: con «disproportionate burden on future generations» e obiettivi intermedi e' E; con «short-term interests» e «judicial review» e' H; con «intertemporal guarantees of freedom» e' Neubauer; con titolarita' di diritti dei posteri e' la Colombia.
- Vulnerabilita' delle donne anziane al calore (§§ 510-511, 529-530): fatto riconosciuto, non principio. Senza i criteri del § 487 non e' A.
- «Do its part»: e' il § 545 (C). Un testo che lo usa per dire che ogni Stato risponde della propria quota anche se piccola va letto su F.

### 5.4 Riprese mediate

Il § 571 poggia dichiaratamente su Neubauer (Rn. 215-229): chi riprende il bilancio nazionale da qui riprende Neubauer in forma annidata, e va detto. Il § 442 poggia su Duarte Agostinho §§ 202-03 (stesso giorno). Nella direzione opposta: Carême, Duarte, Greenpeace Nordic, De Conto, Uricchio, Engels e Müllner poggiano su KlimaSeniorinnen; chi riprende i criteri da loro riprende KlimaSeniorinnen in forma annidata. Le due decisioni del Comitato dei Ministri sull'esecuzione (6/3/2025 e 17/9/2025) ripetono la formula del § 545 ma sono atti del caso, esclusi.

### 5.5 Chi parla

Nella sentenza parlano anche le parti (§§ 298-364) e gli intervenienti (§§ 365-409): un rinvio a quei paragrafi riprende una tesi, non la Corte. Il voto di Eicke e' una voce dissenziente. Il sommario delle pp. 1-2 e il comunicato stampa sono della Cancelleria («Does not bind the Court»). Valgono le tre regole del gruppo del 23/9/2026 su che cosa conta come ripresa (fascicolo di Neubauer, 5.6): conta anche se la stessa ragione e' applicata a un'impresa, anche se la dice una parte o un interveniente, anche se la corte la riassume come argomento di una parte, dicendo sempre chi la porta.

## Non verificato nel corpus

- Il testo francese della sentenza (ufficiale come l'inglese) e quindi le formule francesi delle sonde.
- «Anziane per il clima» come nome italiano dell'associazione e le altre forme PREVISTE in `klimaseniorinnen.yaml`.
- Le date e gli esiti dei giudizi del corpus elencati in 4.5-4.7, letti qui solo per i rinvii a paragrafo.
- Se i pareri consultivi del 2025 (CIG, Corte interamericana) riprendano la sentenza nel testo finale e in quali paragrafi.
- Che la versione francese abbia la stessa numerazione dei paragrafi.
