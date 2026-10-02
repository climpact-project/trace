# Fascicolo del parere OC-32/25 (Corte interamericana, «Emergencia Climática y Derechos Humanos»)

1 ottobre 2026, versione 2, PROPOSTA scritta da Claude per il PI, con le otto sonde distintive approvate dal PI lo stesso giorno (la prima serie di sette sonde e' superata). Fonti usate: le quattro versioni del parere nel corpus (spagnolo `decision_28df`, 234 pp.; inglese della Corte `decision_3b51`, 219 pp.; seconda versione inglese `decision_9329`, 234 pp.; portoghese `opinion_2cd0`, 228 pp.), gli altri 39 documenti del fascicolo della richiesta (case_id `request-for-an-advisory-opinion-on-the-scope-of-the-state-obligations-for-responding-to-the-climate-emergency_fbcd`), il parere OC-23/17 (`opinion_029c`), il parere della CIG del 23 luglio 2025 (`decision_af16`, case_id `request-for-an-advisory-opinion-on-the-obligations-of-states-with-respect-to-climate-change_0213`), la sentenza KlimaSeniorinnen, la sentenza Greenpeace Nordic c. Norvegia e i 74 documenti del corpus che nominano il parere. Poi `idh-oc-32-25.yaml` e `idh-oc-32-25-mappa-paragrafi.yaml` (stessa cartella), il fascicolo di Future Generations come modello di forma, e i conteggi di `conta_paragrafi.py`. Nessun giudizio umano, nessun file di addestramento. Ogni citazione fra virgolette e' stata ritrovata nel corpus normalizzando solo gli spazi; cio' che non vi si trova e' marcato «[non verificato nel corpus]». Pagina = marcatore `<!-- page N -->` del markdown, che coincide con la pagina del PDF. Paragrafi = numeri della Corte, uguali in tutte le lingue.

## 0. A che cosa serve e come leggerlo

Ti viene dato un passaggio di un ALTRO caso. Devi dire se riprende una proposizione dell'OC-32/25 (RIPRESA), se afferma qualcosa di simile fondandolo su un'altra fonte (ALTRA_FONTE), o se non la afferma (NON_AFFERMA). Anelli della catena argomentativa, nell'ordine in cui la Corte li percorre:

- (a) fatto: l'emergenza climatica e' accertata dalla scienza, urgente, grave e complessa (§§ 42-216, punto 1);
- (b) obblighi generali: rispetto, garanzia con debida diligencia reforzada, sviluppo progressivo, diritto interno, cooperazione (§§ 217-265, punti 2-6);
- (c) diritti sostanziali nuovi o ridefiniti: la Natura soggetto di diritti, il divieto imperativo di danno irreversibile all'ecosistema comune, il diritto a un clima sano (§§ 279-316, punti 7-9);
- (d) obblighi di mitigazione: meta, strategia, imprese, vigilanza, impatto climatico (§§ 321-363, punto 10), poi natura, sviluppo sostenibile, adattamento (§§ 364-457, punti 11-12);
- (e) diritti di procedura: democrazia, scienza, informazione, partecipazione, giustizia, difensori (§§ 458-587, punti 13-18);
- (f) uguaglianza: gruppi vulnerabili e poverta' (§§ 588-629, punti 19-20).

Quattro cose da tenere a mente sempre.

1. Molto di cio' che il parere dice viene da OC-23/17, e la Corte lo dichiara. Il diritto all'ambiente sano come diritto autonomo, le sue due dimensioni, la prevenzione, la giurisdizione per il danno transfrontaliero sono riepilogati ai §§ 266-278 con rinvio a OC-23/17 e alle sentenze Lhaka Honhat, La Oroya, U'wa. La due diligence proporzionale al rischio e' OC-23/17 (§ 142, citato al § 232). Per decisione del PI le sonde portano SOLO cio' che e' proprio dell'OC-32/25, cosi' che chi lo riprende sia riconoscibile come suo debitore: il clima sano come diritto autonomo, lo jus cogens del danno irreversibile, la Natura soggetto di diritti nel diritto interamericano, la debida diligencia reforzada, la valutazione d'impatto climatico, il diritto alla scienza esteso ai saperi tradizionali con l'obbligo di contrastare la disinformazione, la protezione dello sfollamento climatico transfrontaliero, la prova agevolata del nesso causale. Cooperazione, adattamento come obbligo, uguaglianza e simili non sono sonde.

2. Nell'estate 2025 i pareri sono due, e chi cita li mette quasi sempre insieme. La Corte IDH adotta il suo il 29 maggio (pubblicato il 3 luglio), la CIG il suo il 23 luglio; l'ITLOS aveva parlato il 21 maggio 2024. La CIG cita l'OC-32/25 in blocco, senza paragrafo (§ 385, p. 119). Molte memorie scrivono «ICJ Climate AO, para. 136; IACtHR OC-32/25, para. 320». Il lessico distingue: «stringent due diligence» e «erga omnes» sono della CIG; «debida diligencia reforzada» o «enhanced due diligence» e «jus cogens» sono della Corte IDH.

3. Il parere si cita col codice, non col titolo. Le forme sono nel file del caso. Due insidie. «OC-32» senza anno nomina anche la RICHIESTA del 2023 («Solicitud de Opinión Consultiva OC-32», nota 4 del parere, p. 7). «Climate Emergency and Human Rights» e' anche il titolo della richiesta e, tradotto, di un avis della CNCDH francese del 2021. Per questo la soglia del 3 luglio 2025 va applicata sulla data del documento (prefisso del file in `url_origine`), non su `data_deposito`, che e' la data di avvio del caso.

4. La ricezione nel corpus e' oggi concentrata in un solo procedimento. Dei 511 rinvii a paragrafo trovati, 490 vengono dalle memorie alla Corte africana dei diritti dell'uomo e dei popoli sulla richiesta di parere climatico (35 documenti, febbraio-maggio 2026). Fuori di li' i rinvii puntuali sono 21, in 8 casi. Le sonde vanno misurate con e senza quel procedimento.

## 1. Il parere

### 1.1 Che cosa c'e' nel corpus

Quattro versioni, tutte con data 20250703 nel nome del file:

- `decision_28df`, originale spagnolo, 234 pp. «Redactada en español en San José, Costa Rica, el 29 de mayo de 2025» (p. 233). Fonte dei canonical.
- `decision_3b51`, traduzione inglese, 219 pp., con paginazione propria. Traduce «debida diligencia reforzada» con «enhanced due diligence».
- `decision_9329`, seconda versione inglese, 234 pp., con la stessa paginazione dello spagnolo e una traduzione diversa.
- `opinion_2cd0`, versione portoghese, 228 pp. Nel corpus porta `tipo_atto` da «opinion»: e' il parere, non un voto separato.

I voti separati (tre parzialmente dissenzienti: Hernández López, Sierra Porto, Pérez Goldberg; quattro concorrenti: Mudrovitsch, Ferrer Mac-Gregor, Pérez Manrique, Gómez) sono annunciati a p. 233 ma non sono nel corpus [non verificato nel corpus]. Un rinvio «Concurring Opinion, para. 83» rimanda a uno di loro, non al parere.

Il resto del fascicolo: la domanda di Cile e Colombia del 9 gennaio 2023 (`petition_1973`, spagnolo; `petition_bb43`, inglese), la domanda corretta (`other_d40b`), decine di osservazioni scritte e amicus del 2023-2024, e almeno due written statements alla CIG archiviati qui per errore (`other_7253`, `other_b14c`). Tutto il fascicolo e' escluso dalla ricerca.

### 1.2 Struttura

- I. Presentación (§§ 1-4, p. 5); II. Procedimiento (§§ 5-13): 263 osservazioni scritte, udienze a Bridgetown, Brasilia e Manaus nel 2024; III. Competencia (§§ 14-23).
- IV. Consideraciones preliminares (§§ 24-41): oggetto e riformulazione delle domande, struttura, fonti (la scienza come base, l'integrazione sistemica, §§ 33-38), portata.
- V. La emergencia climática (§§ 42-216, pp. 16-83): cause, impatti, risposta internazionale, diritto degli Stati OEA, contenzioso (§§ 176-180), definizione di emergenza (urgenza, gravita', complessita').
- VI. Las obligaciones de los Estados (§§ 217-629, pp. 83-228): A obblighi generali (§§ 217-265); B diritti sostanziali (§§ 266-457); C diritti di procedura (§§ 458-587); D uguaglianza (§§ 588-629).
- VII. Opinión (pp. 229-233): «decide» 1 sulla competenza e venti punti resolutivi, numerati a parte.

### 1.3 Punti resolutivi, voti e sonde

| Punto | Contenuto | Paragrafi richiamati | Voto | Sonda |
|---|---|---|---|---|
| 1 | Emergenza climatica secondo la migliore scienza | 183, 205-216 | unanimita' | nessuna (fatto) |
| 2 | Obbligo di rispetto | 219-223 | unanimita' | nessuna |
| 3 | Garanzia con debida diligencia reforzada | 225-237 | unanimita' | diligenza_rafforzata (solo §§ 231-237) |
| 4 | DESCA, massimo delle risorse | 238-243 | 6-1 | nessuna |
| 5 | Diritto interno | 244-246 | unanimita' | nessuna |
| 6 | Cooperazione | 247-265 | unanimita' | nessuna |
| 7 | Natura soggetto di diritti | 279-286 | 4-3 | natura_soggetto_diritti (solo §§ 279-283) |
| 8 | Jus cogens | 287-294 | 4-3 | jus_cogens_dano_irreversible |
| 9 | Clima sano, dimensione collettiva | 298-316 | 5-2 in parte | clima_sano_autonomo (§§ 297-304, 311-316) |
| 10 | Mitigazione: meta, strategia, imprese; vigilanza; impatto climatico | 323-351; 352-357; 358-363 | 6-1 in parte | valutazione_impatto_climatico (§§ 350, 352-363) |
| 11 | Natura e sviluppo sostenibile | 364-376 | unanimita' | nessuna |
| 12 | Adattamento | 384-391, 400-457 | 6-1 in parte | mobilita_climatica (§§ 422-434) |
| 13 | Democrazia | 460-469 | unanimita' | nessuna |
| 14 | Diritto alla scienza e ai saperi | 471-487 | 6-1 in parte | scienza_disinformazione (§§ 476-484) |
| 15 | Informazione | 501-527 | unanimita' | scienza_disinformazione (§§ 524-529) |
| 16 | Partecipazione, consulta previa | 530-539 | unanimita' | nessuna |
| 17 | Accesso alla giustizia | 542-560 | 4-3 in parte | prova_agevolata (solo §§ 552-555) |
| 18 | Difensori ambientali | 566-567, 575-587 | unanimita' | nessuna |
| 19 | Poverta' | 626-627 | unanimita' | nessuna |
| 20 | Gruppi vulnerabili | 599-604, 606-618, 628-629 | 4-3 in parte | nessuna |

Il punto resolutivo dice dove sta un tema; la sonda prende solo i paragrafi che ne enunciano l'elemento proprio. Fuori restano, dentro gli stessi punti: la garanzia e la precauzione ripetute da OC-23/17 (§§ 224-230), il danno climatico transfrontaliero (§§ 295-296), l'equita' intergenerazionale come principio (§§ 305-310), la rassegna dei diritti della natura altrove (§§ 284-286), meta e strategia di mitigazione (§§ 317-344), la due diligence d'impresa dei Principi guida ONU (§§ 345-349, 351), il diritto alla scienza in generale e i criteri della migliore scienza (§§ 471-475, 485-487), i fatti sulla mobilita' (§§ 414-421), il resto dell'accesso alla giustizia (§§ 540-551, 556-560).

### 1.4 Che cosa dice ogni sonda

**clima_sano_autonomo (§§ 297-304, 311-316).** Come in La Oroya per l'aria e l'acqua, dall'ambiente sano deriva un diritto al clima sano (§ 297). E' un diritto «independiente» con «una base con entidad propia» (§ 300, p. 110, canonical). Un clima sano e' quello di un sistema climatico libero da interferenze antropiche pericolose (§ 300). Dimensione collettiva: «el interés colectivo de las generaciones presentes y futuras de seres humanos y de otras especies» (§ 302, p. 111, canonical_bis), titolarita' indivisibile, rimedi a beneficio dell'umanita' presente e futura e della Natura; dimensione individuale come precondizione degli altri diritti (§ 303). L'equita' entra solo come parte del diritto: l'umanita' come comunita' che dura nel tempo, la cui protezione richiede equita' intra e intergenerazionale (§§ 311-313). La Natura protetta dal clima sano (§§ 314-316). Proprio: il CLIMA sano come diritto distinto, prima corte a riconoscerlo. Fuori: i §§ 305-310 (equita' intergenerazionale come principio, ripartizione degli oneri fra generazioni), presi da fonti che la Corte stessa elenca.

**jus_cogens_dano_irreversible (§§ 287-294).** La comunita' internazionale ha individuato condotte che alterano in modo irreversibile l'equilibrio dell'ecosistema comune: deforestazione su larga scala, perdita massiva di specie, inquinamento persistente, alterazione dei cicli biogeochimici, cambiamento climatico nelle sue forme estreme (§ 288). Preservare quell'equilibrio e' «una condición sine qua non para la vigencia de todos los derechos humanos» (§ 293, p. 108). Quindi le proibizioni «tienen el carácter de jus cogens» (§ 291, p. 108, canonical), per il principio di effettivita' (§§ 292, 294), e tutti gli Stati devono cooperare per far cessare le violazioni (§ 294). Votato 4-3. Proprio, senza precedenti nel corpus: la CIG parla di obblighi erga omnes per il sistema climatico (§ 440), non di jus cogens.

**natura_soggetto_diritti (§§ 279-283).** Riconoscere diritti propri agli ecosistemi protegge la loro integrita' e funzionalita' a lungo termine (§ 279). «Este reconocimiento permite superar concepciones jurídicas heredadas, que concebían a la Naturaleza exclusivamente como objeto de propiedad o recurso explotable» (§ 280, p. 102, canonical). E' compatibile con gli artt. 2 e 26 e con i principi pro natura e pro persona (§ 281); non introduce nulla di estraneo al corpus iuris interamericano (§ 282); obbligo di proteggere, restaurare e rigenerare (§ 283). Votato 4-3. Proprio: il riconoscimento come sviluppo del diritto interamericano. Fuori: i §§ 284-286, rassegna della Carta mondiale della natura, della CBD, delle risoluzioni ONU e della tendenza nazionale (Ecuador, Atrato, Amazzonia, leggi municipali brasiliane).

**diligenza_rafforzata (§§ 231-237).** L'obbligo di garanzia e' di mezzi e si misura con la due diligence, concetto variabile (§§ 231-232, con l'ITLOS). Per l'informazione disponibile, la gravita' estrema e l'urgenza, la diligenza deve essere RAFFORZATA (§ 233, p. 88, canonical; inglese della Corte «enhanced due diligence»). I rischi sono «en gran medida, previsibles» (§ 234). Il § 236 ne elenca il contenuto: valutazione esaustiva dei rischi, misure «proactivas y ambiciosas», migliore scienza, prospettiva dei diritti umani, monitoraggio, diritti di procedura, trasparenza, regolazione della due diligence d'impresa, cooperazione rafforzata. Proprio: la formula «reforzada» agganciata alla garanzia dei diritti umani. Fuori: i §§ 224-230 (garanzia, prevenzione, precauzione «aún en ausencia de certeza científica»), che ripetono OC-23/17; e la «stringent due diligence» di ITLOS e CIG, che e' altra fonte.

**valutazione_impatto_climatico (§§ 350, 352-363).** Obblighi differenziati per contributo attuale e storico delle imprese, piu' severi per i grandi emettitori (§ 350, p. 125, canonical_bis, il paragrafo piu' citato). Vigilanza stretta delle attivita' emissive, pubbliche e private, al minimo combustibili fossili, cemento, agroindustria, e piu' esigente per le imprese con maggiore responsabilita' (§ 353); organi indipendenti, sanzioni, corruzione (§§ 354-357). Valutazione d'impatto: «aquellos proyectos o actividades que impliquen el riesgo de generar emisiones significativas de GEI deben ser sometidos a una evaluación de impacto climático» (§ 359, p. 127, canonical); greenwashing (§ 360); contenuto minimo (§ 361). Proprio: l'impatto CLIMATICO come contenuto obbligatorio della VIA, dedotto dai diritti umani, e la differenziazione per contributo storico. Fuori: i §§ 345-349 e 351 (due diligence d'impresa dei Principi guida ONU, trattati di investimento), non distintivi. La Corte EDU in Greenpeace Nordic trascrive i §§ 353, 358-359 (vedi 4.11).

**scienza_disinformazione (§§ 476-484, 524-529).** Accanto alla scienza esistono saperi locali, tradizionali e indigeni (§ 476). Per interpretazione evolutiva dell'art. 14 del Protocollo di San Salvador, il diritto alla scienza comprende anche i benefici di quei saperi (§ 477, p. 174, canonical); tutti hanno diritto a misure basate sulla migliore scienza e sul riconoscimento di quei saperi (§ 478); la protezione «se extiende también a los desarrollos intelectuales y prácticos» di popoli indigeni e comunita' (§ 483, p. 176); obblighi di proteggerli e raccoglierli (§ 484). Disinformazione: gli Stati «deben abstenerse de difundir información que no esté respaldada por la mejor ciencia disponible o por saberes locales, tradicionales o indígenas pertinentes» (§ 525, p. 190) e hanno l'obbligo di misure progressive per contrastarla (§ 527, p. 191, canonical_bis), senza censura preventiva; media e piattaforme (§§ 528-529). Proprio: il diritto alla scienza che INCLUDE i saperi tradizionali, e il contrasto alla disinformazione climatica come obbligo convenzionale. Fuori: il diritto alla scienza in generale (§§ 471-475, PIDESC) e i criteri della migliore scienza con l'IPCC (§§ 485-487).

**mobilita_climatica (§§ 422-434).** Gli Stati devono prevenire, con debida diligencia reforzada, le migrazioni e gli sfollamenti forzati causati da disastri e altri impatti climatici (§ 422); predisporre strumenti per chi e' in mobilita' involontaria (§ 424), con diritti di procedura (§ 425), reinsediamento adeguato (§§ 426-427) e assistenza (§ 428); «Las relocalizaciones solo deben ocurrir en circunstancias excepcionales» (§ 429, p. 152); cooperazione (§§ 430-432). Per chi attraversa una frontiera: un quadro normativo interno di protezione giuridica e umanitaria (§ 433, p. 154, canonical), con visti umanitari, permanenze temporanee, «la protección bajo el estatus de refugiados u otros similares», «que les puedan brindar protección contra la devolución» (§ 433, p. 155); infanzia nei processi di mobilita' climatica (§ 434). Proprio: protezione complementare e non respingimento come obbligo convenzionale per lo sfollamento climatico transfrontaliero. Fuori: art. 22 e fatti (§§ 414-421).

**prova_agevolata (§§ 552-555).** La complessita' delle cause climatiche rende l'applicazione stretta delle regole probatorie un ostacolo (§ 552). Servono standard probatori alternativi per il nesso causale, fondati sul rischio generato o tollerato e sull'esposizione, «sin exigir necesariamente la prueba de un nexo causal directo», e la Corte richiama «la posibilidad de presumir el nexo causal» fra emissioni e degradazione del sistema climatico (§ 553, p. 200, canonical). Interpretazione flessibile della prova e «la inversión de la carga probatoria» (§ 554, canonical_bis); prova satellitare (§ 555). Proprio: la presunzione del nesso emissioni, sistema climatico, rischi, come standard per le cause climatiche. Gia' altrove: l'inversione dell'onere e il carico dinamico della prova nell'art. 8.3 dell'Accordo di Escazú (riportato nel corpus da un'osservazione al fascicolo).

## 2. La mappa dei paragrafi

La mappa leggibile da macchina, in 80 voci che coprono i §§ 1-629 senza buchi, e' in `idh-oc-32-25-mappa-paragrafi.yaml`.

### 2.1 Come riconoscere il rinvio

- «párr. 233», «párrs. 231-237», «para. 350», «paras 345-350», «¶ 234», «§ 547», «parágrafo 297», «Paragrafos 231-237»: paragrafi del parere, da 1 a 629, uguali in tutte le lingue.
- «operative para 3», «operative clause», «punto resolutivo 8»: punti resolutivi dell'Opinión (pp. 229-233), numerati 1-20. Non sono paragrafi. Il «decide» 1 e' la competenza.
- «Concurring Opinion, para. 120», «voto concurrente»: un voto separato, non nel corpus.
- «p. 88», «at 84»: pagina. Se il rinvio e' a pagina, controllare la versione: lo spagnolo e `decision_9329` hanno 234 pagine con la stessa paginazione; la traduzione della Corte (`decision_3b51`) ne ha 219 e resta indietro fino a 15 pagine (§ 233: p. 88 ES, p. 84 EN; § 546: p. 198 ES, p. 186 EN).
- «Series A No. 32» / «Serie A No. 32»: la serie ufficiale della Corte; da sola collide con Airey c. Irlanda (Corte EDU, 1979, «Series A no. 32»).
- «(n 31) at paras 321-322»: rinvio breve OSCOLA a una nota precedente. Lo script lo legge solo se la forma del parere precede il numero; «ibid., para. 183» non lo legge.
- «supra», «above»: rinvio interno del documento citante («see paragraph 132 above» nella sentenza Greenpeace Nordic e' un paragrafo della sentenza, non del parere).

### 2.2 Tavola sintetica

| Paragrafi | Sezione | Sonda |
|---|---|---|
| 1-216 | presentazione, procedura, competenza, fonti, fatti | nessuna |
| 217-230 | rispetto, garanzia, prevenzione, precauzione | nessuna |
| 231-237 | debida diligencia reforzada | diligenza_rafforzata |
| 238-278 | DESCA, diritto interno, cooperazione, ambiente sano (OC-23/17 ripreso) | nessuna |
| 279-283 | Natura soggetto di diritti | natura_soggetto_diritti |
| 284-286 | rassegna di strumenti e tendenza sui diritti della natura | nessuna |
| 287-294 | jus cogens | jus_cogens_dano_irreversible |
| 295-296 | sistema climatico, danno transfrontaliero | nessuna |
| 297-304 | clima sano | clima_sano_autonomo |
| 305-310 | equita' intergenerazionale come principio | nessuna |
| 311-316 | umanita' presente e futura, Natura | clima_sano_autonomo |
| 317-349 | raccordo, meta e strategia di mitigazione, due diligence d'impresa | nessuna |
| 350 | obblighi differenziati delle imprese | valutazione_impatto_climatico |
| 351 | trattati di investimento | nessuna |
| 352-363 | vigilanza, valutazione d'impatto climatico | valutazione_impatto_climatico |
| 364-421 | natura, sviluppo sostenibile, adattamento, art. 22 e fatti sulla mobilita' | nessuna |
| 422-434 | obblighi sulla mobilita' climatica | mobilita_climatica |
| 435-475 | adattamento per diritto, democrazia, diritto alla scienza in generale | nessuna |
| 476-484 | saperi locali, tradizionali e indigeni | scienza_disinformazione |
| 485-523 | migliore scienza, informazione | nessuna |
| 524-529 | disinformazione | scienza_disinformazione |
| 530-551 | partecipazione, accesso alla giustizia fino alla legittimazione | nessuna |
| 552-555 | prova | prova_agevolata |
| 556-629 | riparazione, difensori, uguaglianza, gruppi vulnerabili, poverta' | nessuna |

## 3. Le frasi piu' riprese, verbatim

Spagnolo (`decision_28df`) e inglese della Corte (`decision_3b51`). Fra parentesi il numero di rinvii nel corpus (01/10/2026).

- § 233 (17 rinvii), p. 88, canonical della diligenza rafforzata: «la Corte estima que los Estados deben actuar con una debida diligencia reforzada para cumplir con el deber de prevención derivado de la obligación de garantía». EN p. 84: «the Court finds that States must act with enhanced due diligence to comply with the obligation of prevention».
- § 234 (22 rinvii), p. 88, dentro la diligenza rafforzata: «Conforme a los avances científicos, tanto estos riesgos como la magnitud y el carácter irreversible de los daños que pueden generar son, en gran medida, previsibles.»
- § 229 (14 rinvii), p. 86, senza sonda (precauzione da OC-23/17): «Este estándar se extiende tanto a la degradación del sistema climático global como a las violaciones de derechos humanos derivadas de ésta.» EN p. 82: «This standard extends to both the degradation of the global climate system and to the resulting human rights violations.»
- § 350 (22 rinvii), p. 125: canonical_bis della valutazione d'impatto climatico. EN p. 118: «Consequently, the Court considers that States should establish differentiated obligations with regard to climate action based on the actual and historical contribution of business enterprises to climate change, and impose stricter obligations on those whose activities are major sources of GHG emissions.»
- § 359 (13 rinvii), p. 127, canonical della valutazione d'impatto climatico: «En particular, aquellos proyectos o actividades que impliquen el riesgo de generar emisiones significativas de GEI deben ser sometidos a una evaluación de impacto climático.» EN p. 120: «In particular, those projects or activities that pose a risk of generating significant GHG emissions should be subject to a climate impact assessment.»
- § 291 (10 rinvii), p. 108: canonical dello jus cogens. EN p. 102: «The prohibitions arising from the obligation to preserve our common ecosystem, as a precondition to the enjoyment of other rights that have already been identified as fundamental, are of peremptory importance and are, therefore, of a jus cogens nature.»
- § 300, p. 110: canonical del clima sano. EN p. 104: «the Court considers that recognition of a human right to a healthy climate as an independent right».
- § 326, p. 118, senza sonda (meta di mitigazione): EN p. 111: «this should be considered a minimum starting point, rather than the finishing line, when determining the mitigation target».
- § 546, p. 198, senza sonda (pro actione): EN p. 186: «judicial authorities must apply the pro actione principle with respect to the admissibility of actions, appeals filed, and requirements regarding standing».
- § 551, p. 199, senza sonda: «Por ende, este Tribunal resalta que la garantía del acceso a la justicia supone la legitimación activa de personas y entidades que no residan en el territorio del Estado.» EN p. 187: «Consequently, the Court stresses that the guarantee of access to justice involves the legal standing of people and entities that do not reside in the State’s territory.»
- § 280, p. 102: canonical della Natura. EN p. 97: «Recognition of Nature as a subject of rights also emphasizes its structural role in the vital balance of the conditions that make this planet inhabitable.»
- Senza sonda, § 566 (14 rinvii), p. 203: la Corte «reconoce la existencia de un “deber especial de protección” del Estado respecto de ellas» (i difensori ambientali).
- § 477, p. 174, canonical della scienza: «el “derecho a la ciencia” no solo comprende el acceso a beneficios que se deriven de la ciencia en sentido estricto». EN p. 163: «the Court considers that, according to an evolutionary interpretation, the “right to science” not only encompasses access to benefits obtained from science in the strict sense».
- § 527, p. 191: «los Estados tienen la obligación de adoptar medidas progresivas para contrarrestar la desinformación en materia climática». EN p. 179: «In this regard, States are required to adopt progressive measures to counter climate-related disinformation».
- § 433, p. 154, canonical della mobilita': EN p. 145: «The Court considers that States must establish an appropriate regulatory framework that provides effective legal and/or administrative mechanisms at the domestic level to guarantee the legal and humanitarian protection of persons displaced across international borders due to the impacts of climate change.»
- § 553, p. 200, canonical della prova: «la posibilidad de presumir el nexo causal». EN p. 187: «In this regard, the Court draws attention to the possibility of presuming the causal link between GHG emissions and the degradation of the climate system».
- § 554, p. 200: «la inversión de la carga probatoria». EN p. 187: «the adoption of appropriate measures – such as the reversal of the burden of proof – that allow effective access to justice to be guaranteed».

## 4. Il mondo intorno: le fonti concorrenti

### 4.1 Corte IDH, OC-23/17, «Medio Ambiente y Derechos Humanos» (15/11/2017)

Nel corpus (`a-request-for-an-advisory-opinion-from-the-inter-american-court-of-human-rights-concerning-the-interpretation-of-article-1-1-4-1-and-5-1-of-the-american-convention-on-human-rights-opinion_029c`). Diritto all'ambiente sano come diritto autonomo (§§ 62-64), due diligence proporzionale al rischio (§ 142), obbligo di regolare, supervisionare e fiscalizzare (§§ 152-155). L'OC-32/25 la cita di continuo e ne riassume la dottrina ai §§ 266-278. Regola: «ambiente sano diritto autonomo», «interdipendenza fra ambiente e diritti», «obblighi di prevenzione» senza l'elemento climatico proprio sono OC-23/17, anche se il testo nomina l'OC-32/25. E' la confusione piu' frequente: un atto brasiliano scrive «Opinion Consultiva OC-32/25. Medio ambiente y derechos humanos en el contexto de la emergencia climatica» (petizione Tenharim, p. 25), mescolando i due titoli.

### 4.2 Le sentenze della Corte IDH che il parere riprende

La Oroya c. Perù (2023: aria e acqua pulite, equita' intergenerazionale, § 297 e § 305 del parere), U'wa c. Colombia (2024: triplice crisi planetaria, § 317), Lhaka Honhat c. Argentina, Kawas Fernández c. Honduras (difensori, § 574). Chi riprende questi casi riprende la Corte, ma non questo parere [testi delle sentenze non verificati nel corpus].

### 4.3 CIG, «Obligations of States in respect of Climate Change» (23/7/2025)

Nel corpus (`request-for-an-advisory-opinion-on-the-obligations-of-states-with-respect-to-climate-change-decision_af16`). Due diligence «stringent» per le NDC e la mitigazione (§§ 138, 246), NDC capaci nell'insieme di realizzare gli obiettivi di Parigi (§ 249), regolare gli attori privati come obbligo di due diligence (§ 428), obblighi erga omnes per beni comuni globali come il sistema climatico (§ 440). Cita l'OC-32/25 una volta, in blocco (§ 385, p. 119). Regola: «stringent», «erga omnes», le NDC come strumento sono la CIG; «reforzada/enhanced», «jus cogens», «clima sano», «punto de partida mínimo» sono la Corte IDH.

### 4.4 ITLOS, parere del 21/5/2024

Due diligence «stringent» per l'inquinamento marino da gas serra; valutazione d'impatto (§ 367 del parere ITLOS, trascritto dalla Corte EDU in Greenpeace Nordic). L'OC-32/25 lo cita ai §§ 232 e 333 (note 464 e 581).

### 4.5 Corte EDU, KlimaSeniorinnen c. Svizzera (9/4/2024)

Nel corpus. Legittimazione delle associazioni (§§ 502-503), requisiti del quadro regolatorio: calendario verso la neutralita', budget di carbonio o metodo equivalente, obiettivi intermedi (§ 550). L'OC-32/25 la cita e la fa propria ai §§ 334-335 (strategia) e al § 383 (adattamento). Una meta vincolante con budget e calendario e' KlimaSeniorinnen se non c'e' la soglia MINIMA dell'1,5 °C o la misura per contributo storico.

### 4.6 Accordo di Escazú (2018, in vigore dal 22/4/2021)

Legittimazione ampia (art. 8), difensori ambientali (art. 9). Il parere lo cita ai §§ 464, 547, 564. Legittimazione ampia e protezione dei difensori fondate su Escazú sono ALTRA_FONTE.

### 4.7 I casi climatici nazionali citati dal parere

§§ 176-180: nel testo Urgenda, Friends of the Irish Environment, Neubauer, Notre Affaire à Tous, Grande-Synthe, Klimaatzaak, Leghari, Shrestha, Milieudefensie c. Shell; in nota KlimaSeniorinnen e Future Generations (STC4360-2018, note 378 e 396; vedi il fascicolo di Future Generations, 4.16). Sono catene possibili nei due sensi: un testo puo' citare Neubauer attraverso l'OC-32/25, o l'OC-32/25 accanto a Neubauer.

### 4.8 Diritti della natura altrove

Costituzione dell'Ecuador (art. 71), T-622/2016 (Atrato), STC4360-2018 (Amazzonia), Te Awa Tupua, Mar Menor, leggi municipali brasiliane (nota 538 del parere). Fonti della tendenza che il parere constata al § 286, non sue riprese.

### 4.9 CNCDH, avis «Urgence climatique et droits de l'homme» (27/5/2021)

Citato negli atti francesi contro TotalEnergies e BNP Paribas e dalla commissione coreana dei diritti umani. Stesso titolo dell'OC-32/25 in inglese («Climate emergency and human rights»), altro organo, altro anno. Falso positivo lessicale garantito.

### 4.10 Corte africana, richiesta di parere sugli obblighi climatici degli Stati africani

Il procedimento che oggi cita di piu' l'OC-32/25: 35 documenti (osservazioni di Stati, ONG, amicus; nel corpus 12 portano `tipo_atto: decisione`, difetto di metadato del nome file), 490 rinvii a 447 paragrafi diversi, febbraio-maggio 2026. Citano quasi tutto il parere, fatti compresi, e quasi sempre accanto alla CIG. Voce `parte` o `amicus`, non `corte`.

### 4.11 Chi cita l'OC-32/25 nel corpus

74 documenti lo nominano fuori dal fascicolo (36 casi); 63 sono successivi al 3/7/2025 per data del file (29 casi). Gli 11 anteriori sono falsi o riferiti alla richiesta. Con rinvio a paragrafo, dopo la soglia:

| Caso | Documento, data | Rinvii | Paragrafi | Sonde toccate |
|---|---|---|---|---|
| Corte africana, richiesta di parere | 35 atti, 2/2026-5/2026 | 490 | 447 diversi | tutte tranne prova_agevolata |
| Observatório do Clima c. IBAMA, Petrobras (Brasile, foce dell'Amazzonia) | petizione, 22/10/2025 | 5 | 223, 226, 229, 231-237, 335, 343-344 | diligenza_rafforzata |
| Instituto Preservar, AGAPAN c. Unione (Brasile, emergenza nel Rio Grande do Sul) | decisione, 22/8/2025 | 4 | 295, 299, 337, 547 | clima_sano_autonomo |
| Instituto Aimara c. Piracicaba (Brasile) | atto introduttivo, 1/2/2026 | 4 | 297, 556, 558, 559 | clima_sano_autonomo |
| Lighthiser c. Trump (USA) | amicus, 20/1/2026 | 4 | 234 | diligenza_rafforzata |
| Juliana, petizione alla Commissione interamericana | 25/9/2025 | 1 | 540-541 | nessuna |
| Tenharim Marmelos (Brasile) | atto introduttivo, 30/9/2025 | 1 | 295 | nessuna |
| Dunn c. Wisconsin PSC (USA) | replica, 22/12/2025 | 1 | 234 | diligenza_rafforzata |
| Richiesta di incostituzionalita' (Cile, deputati Melo Contreras e altri) | 24/7/2025 | 1 | 543 | nessuna |

La sentenza Bonaire (Rechtbank Den Haag, 28/1/2026) cita il § 327 nella forma breve «Advisory Opinion IACHR», ora esclusa per decisione del PI: il documento resta fra i citanti, il rinvio non si conta.

Lo nominano senza rinvio a paragrafo, fra gli altri: la CIG (23/7/2025, § 385), la Corte EDU in Greenpeace Nordic c. Norvegia (28/10/2025), il Supremo Tribunal Federal (ADI 7582, 19/12/2025), tre decisioni federali brasiliane sulla deforestazione nel PAE Antimary (agosto-ottobre 2025), la decisione Samarco (19/12/2025), i ricorsi Klimatická žaloba alla Corte EDU (2026), Dykstra (Canada), Denman (Australia), Poelina (Australia), Venner c. EPA (USA).

Caso da segnalare: Greenpeace Nordic c. Norvegia (Corte EDU, 28/10/2025). La sentenza dedica una sezione al parere (§§ 132-135): cita i §§ 45 e 47 sulle emissioni da combustibili fossili, trascrive, in tutto o in parte, i §§ 337, 353, 358 e 359, e al § 322 ne riprende la valutazione d'impatto climatico accanto all'ITLOS e alla Corte EFTA. Il conteggio automatico non vede queste riprese, perche' sono trascrizioni («“337. Given the urgency») e non rinvii «para. 337». E' la ripresa piu' autorevole fuori dalla Corte africana, e tocca la sonda valutazione_impatto_climatico (§§ 353, 358-359); il § 337 sta fra i paragrafi senza sonda.

## 5. Come si riconosce una ripresa

### 5.1 Indizi forti

- «derecho a un clima sano», «right to a healthy climate», «direito ao clima estável» (osservato nel corpus) come diritto distinto dall'ambiente sano.
- «jus cogens» o «norma imperativa» riferiti al danno irreversibile all'ecosistema comune o all'equilibrio ecologico.
- La Natura soggetto di diritti come sviluppo del diritto interamericano, compatibile con la Convenzione.
- «debida diligencia reforzada», «enhanced due diligence», «reinforced due diligence», «diligência reforçada», riferiti alla garanzia dei diritti umani nel contesto climatico.
- «evaluación de impacto climático», «climate impact assessment» come obbligo autonomo della VIA; «obligaciones diferenciadas» delle imprese «basadas en la contribución actual e histórica».
- Diritto alla scienza che comprende i saperi locali, tradizionali e indigeni; obbligo di contrastare la disinformazione climatica.
- Protezione complementare, visti umanitari, non respingimento per chi attraversa una frontiera a causa del cambiamento climatico, dedotti dai diritti umani regionali.
- Presunzione del nesso causale fra emissioni, degradazione del sistema climatico e rischi; standard probatori alternativi senza nesso diretto.
- Trascrizioni di paragrafi interi con il numero all'inizio («Eis o teor do § 547 da OC-32/25», «“359. Since the affectation»).

### 5.2 Falsi amici

- Ambiente sano come diritto autonomo, dimensione collettiva come «interés universal»: OC-23/17 (ripreso ai §§ 270-274).
- «stringent due diligence», NDC «highest possible ambition»: CIG, ITLOS, Accordo di Parigi.
- «erga omnes» per il sistema climatico: CIG, § 440.
- Budget di carbonio e calendario vincolante: KlimaSeniorinnen, Neubauer.
- Natura soggetto di diritti fondata su una costituzione, una legge o una corte nazionale: Ecuador, Atrato, Amazzonia.
- Legittimazione ampia e protezione dei difensori fondate su Escazú.
- «Climate emergency and human rights» in un atto francese: l'avis CNCDH.
- «OC-32» in un atto del 2023-2024: la richiesta, non il parere.

### 5.3 Casi incerti

Le memorie alla Corte africana citano spesso blocchi di paragrafi lunghi («paras. 393-457», «paras. 141-174 and 321») che attraversano piu' sonde o finiscono nei fatti: un rinvio a un blocco non dice quale principio e' ripreso. Gli atti brasiliani nominano la «Opinião Consultiva 32» senza paragrafo per sostenere tesi diverse (licenziamento con analisi climatica, Samarco; due diligence, Syngenta): va letto il passaggio.

### 5.4 Riprese mediate

Attraverso la CIG (che cita l'OC-32/25 in blocco) e attraverso la Corte EDU (Greenpeace Nordic, che ne trascrive quattro paragrafi). Un testo che riprende la valutazione d'impatto climatico citando Greenpeace Nordic riprende l'OC-32/25 attraverso Strasburgo.

### 5.5 Chi parla

Le voci sono quelle del codebook: `corte`, `parte`, `amicus`. Le osservazioni alla Corte africana sono atti di Stati, istituzioni e ONG in una procedura consultiva: voce `parte` o `amicus` secondo l'autore, non `corte`, anche quando il corpus le etichetta «decisione». Le decisioni vere che citano il parere oggi sono poche: CIG, Corte EDU, Rechtbank Den Haag (Bonaire), STF e giudici federali brasiliani.

## Non verificato nel corpus

- I voti separati dei sette giudici (annunciati a p. 233).
- I testi delle sentenze La Oroya, U'wa, Lhaka Honhat, Kawas Fernández (citati dal parere; non cercati nel corpus per questo fascicolo).
- La posizione del parere nella lista dei casi ancora del PI.
