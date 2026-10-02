"""TERZO LIVELLO — l'LLM che legge il CONTESTO e risponde sull'ATTRIBUZIONE.

   PERCHE' ESISTE. Il recupero e il riordino rispondono alla domanda «questo
   passaggio afferma questa proposizione?». Misurato il 22/09/2026, il guasto
   ricorrente dei falsi positivi e' un altro: il passaggio AFFERMA davvero la
   proposizione, ma la fonda su un'altra fonte — la Costituzione coreana, la
   Carta canadese, l'Accordo di Parigi, il CBDR, un altro caso climatico. La
   domanda che serve non e' di somiglianza, e' «DA DOVE LA PRENDE?», e la
   risposta sta nel contesto: nelle note, nei richiami, nelle fonti nominate
   intorno al passaggio. Un punteggio non la vede per costruzione; un lettore
   si'.

   L'USCITA NON E' UN PUNTEGGIO, E' UNA RISPOSTA CON LA CITAZIONE IN MANO.
   Il modello deve riportare VERBATIM il pezzo di testo su cui fonda il suo
   giudizio. Cosi' ogni riga si puo' controllare a mano, cosa che un numero non
   consente: e' la differenza fra un risultato che regge in revisione e uno no.

   TRE ESITI, non due:
     RIPRESA      il passaggio fa propria la proposizione del caso citato
     ALTRA_FONTE  afferma la stessa proposizione ma la fonda altrove
     NON_AFFERMA  non afferma la proposizione
   La categoria di mezzo e' quella che il progetto perdeva: contata come «no»
   dal giudizio umano, ma per una ragione precisa che va registrata, perche'
   e' un dato sulla circolazione del principio.
"""
import argparse, json, pathlib, re, sys

QUI = pathlib.Path(__file__).resolve().parent.parent

SCHEDA_CASO = """CASO CITATO: Urgenda Foundation c. Stato dei Paesi Bassi.
Tribunale dell'Aja 2015, Corte d'appello 2018, Corte di cassazione olandese (Hoge Raad) 2019.
Elementi propri di quel caso, utili a riconoscerne la ripresa:
- la via civilistica olandese: dovere di diligenza sociale (zorgplicht), atto illecito
  ex art. 6:162 del codice civile olandese, criteri Kelderluik sulla messa in pericolo;
- gli artt. 2 e 8 CEDU letti come obbligo positivo dello Stato contro un rischio
  climatico reale e immediato benche' differito nel tempo e diffuso nella popolazione;
- la responsabilita' per la propria quota: il contributo modesto non esonera
  ("no reduction is negligible", il rifiuto della difesa della goccia nel mare);
- il minimo quantificato ricavato dal consenso scientifico e internazionale
  (riduzione di almeno il 25% entro il 2020 rispetto al 1990);
- l'ordine di risultato che lascia allo Stato la scelta dei mezzi, distinto
  dall'ordine di legiferare con un contenuto determinato."""

ISTRUZIONI = """Sei un giurista che codifica la circolazione di un precedente giudiziario.

{scheda}

PROPOSIZIONE CERCATA:
{proposizione}

PASSAGGIO DA ESAMINARE (pagina di un atto o di una decisione di un ALTRO caso):
---
{passaggio}
---

Rispondi a queste domande, in quest'ordine, e SOLO con un oggetto JSON.

1. "afferma": il passaggio afferma la proposizione cercata? true oppure false.
2. "fondamento": se la afferma, su che cosa la fonda? Elenca le fonti che il
   passaggio NOMINA o su cui si appoggia: articoli di costituzioni nazionali,
   trattati, pareri di organi internazionali, altri casi, dottrina. Lista di stringhe brevi.
3. "citazione": riporta VERBATIM dal passaggio, senza cambiare una parola, il
   pezzo piu' breve che giustifica la tua risposta sul fondamento. Stringa.
4. "esito": una sola parola fra
   - "RIPRESA"     : fa propria la proposizione cosi' come viene dal caso citato
                     (anche senza nominarlo, purche' il ragionamento sia quello)
   - "ALTRA_FONTE" : afferma la stessa proposizione ma la fonda espressamente
                     su un'altra fonte, non riconducibile al caso citato
   - "NON_AFFERMA" : non afferma la proposizione cercata
5. "motivo": una frase, al massimo venticinque parole.

Non aggiungere niente fuori dal JSON."""


ISTRUZIONI_CATENA = """Sei un giurista che studia come un precedente circola in altre decisioni.

{scheda}

LA CATENA DEL CASO CITATO, cioe' il percorso argomentativo che gli e' proprio:
 (a) esiste un rischio grave, noto alla scienza, che si realizzera' fra decenni
     e colpisce la popolazione nel suo insieme;
 (b) da cio' discende un OBBLIGO DI AGIRE dello Stato — per la via civilistica
     del dovere di diligenza, o per gli obblighi positivi ex artt. 2 e 8 CEDU;
 (c) l'obbligo non viene meno perche' il contributo del singolo Stato e' modesto:
     ciascuno risponde della PROPRIA QUOTA;
 (d) il contenuto minimo dell'obbligo si ricava dal consenso scientifico e dagli
     impegni internazionali, e il giudice puo' fissarlo;
 (e) l'ordine e' di risultato: lo Stato resta libero nella scelta dei mezzi.

PROPOSIZIONE CERCATA (uno degli anelli):
{proposizione}

TESTO DA ESAMINARE — piu' pagine consecutive di un atto o di una decisione di un
ALTRO caso. Leggilo per intero: il ragionamento comincia prima del punto che ci
interessa e si chiude dopo.
---
{passaggio}
---

NON decidere contando i nomi delle fonti. Un testo puo' citare l'Accordo di
Parigi, l'ICJ o una costituzione nazionale E NON DI MENO percorrere la catena
del caso citato; e puo' non citare nessuno e non percorrerla affatto. Quello che
devi stabilire e' quale PERCORSO ARGOMENTATIVO compie il testo.

Rispondi SOLO con un oggetto JSON:

1. "mossa": in una frase, che cosa fa argomentativamente questo brano — che cosa
   vuole dimostrare e con quale passaggio logico.
2. "anelli": quali degli anelli (a)-(e) il testo effettivamente percorre. Lista,
   solo le lettere, vuota se nessuno.
3. "citazione": VERBATIM dal testo, il pezzo piu' breve che mostra l'anello
   principale che hai riconosciuto. Stringa.
4. "fondamento": su che cosa il testo appoggia quel passaggio logico —
   trattati, costituzioni, altri casi, dottrina, o il ragionamento stesso. Lista.
5. "autonomo": true se il testo costruisce quel passaggio per conto suo, da fonti
   proprie, in modo che reggerebbe identico anche se il caso citato non fosse mai
   esistito; false se il passaggio dipende dal percorso del caso citato.
6. "esito": "RIPRESA" se percorre la catena del caso citato; "ALTRA_FONTE" se
   arriva a una conclusione simile per una via propria; "NON_AFFERMA" se non
   affronta la proposizione.
7. "motivo": una frase, massimo venticinque parole.

Niente fuori dal JSON."""


# SECONDA VERSIONE (23/09/2026, sera), scritta dopo aver letto gli errori di
# DeepSeek V4 Flash con ISTRUZIONI_CATENA: delle 15 riprese vere mancate, quasi
# tutte erano giudicate ALTRA_FONTE o NON_AFFERMA con motivi come «fonda
# l'obbligo sulla CEDU, non sulla via civilistica olandese» o «il testo non
# cita Urgenda». Tutti e due sono letture sbagliate del caso e della
# categoria: la via CEDU e' uno dei due binari di Urgenda (Corte d'appello
# 2018, Hoge Raad 2019), e la ripresa implicita e' proprio quella che non nomina
# il caso (codebook, categoria `implicita`). E nella pipeline decisa dal PI
# (§59.1) i validatori leggono tutto quello che l'LLM propone: una ripresa
# persa non si recupera, un falso positivo costa un minuto. La domanda ora lo
# dice. Gli errori letti erano sulle righe di prova: per questo la versione
# nuova si misura ANCHE sulle 257 di addestramento, mai lette, e si
# riportano i due numeri.
ISTRUZIONI_CATENA_V2 = ISTRUZIONI_CATENA.replace(
    "NON decidere contando i nomi delle fonti.",
    """TRE AVVERTENZE, prima di decidere.
- Il caso citato ha DUE binari, e tutti e due sono suoi: la via civilistica
  olandese (dovere di diligenza) E gli obblighi positivi degli artt. 2 e 8 CEDU,
  che sono il fondamento della Corte d'appello 2018 e della Cassazione 2019. Un
  testo che fonda l'obbligo dello Stato sui diritti umani non e' per cio' solo
  su un'altra via.
- Il fatto che il testo NON nomini il caso citato non e' un motivo per
  escludere la ripresa: la ripresa implicita e' proprio quella che lo segue
  senza nominarlo. Conta il percorso, non il nome.
- ALTRA_FONTE vuol dire che il testo arriva a una conclusione simile per un
  percorso DIVERSO, che non passa per gli anelli del caso citato. Se il testo
  percorre due o piu' anelli nello stesso ordine logico, e' una ripresa anche
  se cita fonti diverse accanto.
Nel dubbio fra RIPRESA e ALTRA_FONTE scegli RIPRESA: un giurista leggera' comunque
ogni testo che segnali, mentre una ripresa che scarti e' persa.

NON decidere contando i nomi delle fonti.""")


def costruisci(r, versione=1):
    larga = r.get('finestra_larga')
    if larga:
        return (ISTRUZIONI_CATENA_V2 if versione == 2 else ISTRUZIONI_CATENA).format(scheda=SCHEDA_CASO, proposizione=r['sonda_testo'],
                                        passaggio=larga[:28000])
    return ISTRUZIONI.format(scheda=SCHEDA_CASO, proposizione=r['sonda_testo'],
                             passaggio=r['finestra'][:9000])


def estrai(testo):
    m = re.search(r'\{.*\}', testo, re.S)
    if not m:
        return {'esito': 'ILLEGGIBILE', 'grezzo': testo[:200]}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {'esito': 'ILLEGGIBILE', 'grezzo': m.group(0)[:200]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ingresso', required=True)
    ap.add_argument('--uscita', required=True)
    ap.add_argument('--modello', default='Qwen/Qwen3-32B-FP8')
    ap.add_argument('--max-righe', type=int, default=0)
    a = ap.parse_args()

    righe = [json.loads(x) for x in open(a.ingresso, encoding='utf-8') if x.strip()]
    if a.max_righe:
        righe = righe[:a.max_righe]
    print(f'righe da giudicare: {len(righe)}', flush=True)

    from vllm import LLM, SamplingParams
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(a.modello)
    llm = LLM(model=a.modello, max_model_len=16384, gpu_memory_utilization=0.90,
              enforce_eager=False)
    prompts = [tok.apply_chat_template([{'role': 'user', 'content': costruisci(r)}],
                                       tokenize=False, add_generation_prompt=True,
                                       enable_thinking=False) for r in righe]
    out = llm.generate(prompts, SamplingParams(temperature=0.0, max_tokens=900))
    fuori = []
    for r, o in zip(righe, out):
        g = estrai(o.outputs[0].text)
        fuori.append({'id': r['id'], **{k: r[k] for k in ('etichetta', 'sonda_titolo', 'case_id') if k in r},
                      'llm': g})
    pathlib.Path(a.uscita).write_text(json.dumps(fuori, ensure_ascii=False, indent=1), encoding='utf-8')
    import collections
    print('\nesiti:', collections.Counter(x['llm'].get('esito') for x in fuori).most_common())
    print('scritto', a.uscita)


if __name__ == '__main__':
    main()
