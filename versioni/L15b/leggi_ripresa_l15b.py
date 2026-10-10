"""L15b, SECONDO TENTATIVO DELLA DOMANDA A PASSI COL FASCICOLO (10/10/2026, S09, in prova).

L15 (tools/leggi_ripresa_l15.py) sulla taratura: falsi positivi 3,1% ma proposte sulle vere 36,8% e positivi persi 25,3%
(training/misure/PONTE-L15-DOMANDA-NUOVA-2026-10-10.md). Dalle risposte NO sulle citazioni vere col nome tolto, due cause nella
DOMANDA: (1) un paragrafo senza sonda nel fascicolo viene trattato come luogo comune; (2) la decisione indicata senza il nome («the
ICJ found», «la Corte Suprema colombiana del 5 aprile 2018», «paragrafo 403») viene trattata come nome o come fonte alternativa.
L15b cambia SOLO i passi 2, 4 e la voce NO del passo 6 (diff con L15 in versioni/L15b/istruzioni.txt); tutto il resto (fascicolo,
paragrafo, finestra, JSON, freni compreso quello di coerenza, letture, impostazioni) e' identico a L15. Stessa taratura, stessa
regola, stesse correzioni dei dati: e' il SECONDO tentativo e si dichiara tale.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import leggi_ripresa_l15 as L15  # noqa: E402

CODICE = 'L15b'
MODULO = """Sei un giurista che cerca le RIPRESE IMPLICITE di una sentenza climatica negli atti successivi.
La decisione e' {nome_caso} (del {data_caso}). Una ricerca per nome non l'ha trovata nell'atto qui sotto: l'atto non la nomina.

FASCICOLO DEL CASO. E' il materiale di riferimento su questa decisione: i suoi principi con le definizioni, gli elementi
distintivi, le fonti concorrenti che dicono cose simili, i falsi amici, i casi che contano come ripresa e quelli che non contano.
Usalo nei passi 1, 2 e 4.
=== INIZIO FASCICOLO ===
{fascicolo}
=== FINE FASCICOLO ===

PARAGRAFO DELLA DECISIONE: {etichetta}.
Sintesi della mappa dei paragrafi (scritta da noi, non e' testo della decisione): {sintesi}
{verbatim}Principi che la mappa attribuisce a questo paragrafo:
{principi}
Testo del paragrafo (il passo della decisione piu' vicino alla pagina dell'atto):
---
{passo}
---

PAGINA DELL'ATTO: {titolo} ({tipo_atto}), documento {document_id}{lingua}, pagina {pagina}.
Data dell'atto: {data_atto}
Qui sotto una finestra di circa 1.200 caratteri di quella pagina, estratta dal PDF: puo' avere righe spezzate, refusi, note a pie'
di pagina mescolate al testo; il nome della decisione e i numeri dei paragrafi possono mancare.
---
{finestra}
---

DOMANDA. La finestra RIPRENDE il paragrafo, cioe' usa la proposizione PROPRIA di questa decisione senza nominarla?
Una ripresa implicita si riconosce solo da cio' che questa decisione dice e le altre fonti non dicono. Ragiona in questi passi,
nell'ordine, prima di rispondere:

1. PROPOSIZIONE SPECIFICA. Scrivi in una frase che cosa dice questo paragrafo che le altre fonti non dicono: la regola, il criterio,
   la formula o la conseguenza propria di questa decisione. Confrontala con i principi e le loro definizioni nel fascicolo: se il
   paragrafo corrisponde a un principio, usa quella definizione; se il paragrafo racconta solo fatti, scienza o norme, dillo.
2. DISTINTIVA O LUOGO COMUNE. Distintiva e' la proposizione propria di questa decisione: la sua regola, il suo criterio, la sua
   formula, la sua applicazione o la sua conclusione su quel punto, anche se il fascicolo non ne fa una sonda (un paragrafo senza
   sonda nel fascicolo NON e' per questo un luogo comune). Luogo comune e' solo cio' che si trova uguale altrove e che il fascicolo
   indica fra le fonti concorrenti o i falsi amici: scienza del clima e rapporti IPCC, effetti del riscaldamento sulla salute o
   sugli ecosistemi, diritti umani in generale, testi e storia dei trattati (UNFCCC, Kyoto, Parigi, Montreal), bilancio di
   carbonio, urgenza di ridurre. Se e' un luogo comune, da questa finestra non si puo' riconoscere una ripresa di QUESTA
   decisione: la risposta e' NO.
3. FRASE DELLA FINESTRA. Trova nella finestra la frase che afferma la STESSA proposizione specifica del passo 1 (non lo stesso tema)
   e copiala alla lettera, nella sua lingua. Se non c'e', la risposta e' NO.
4. FONTI ALTERNATIVE. La finestra attribuisce l'idea a qualcun ALTRO (un esperto, l'IPCC o un altro rapporto scientifico,
   un'altra corte o un'altra decisione, una legge, un trattato), o la stessa idea viene da una fonte comune che anche la decisione
   usa (lo stesso perito, lo stesso rapporto)? Il fascicolo elenca le fonti concorrenti. Se si', la risposta e' NO, o FORSE se la
   formulazione resta propria di questa decisione. QUESTA decisione indicata senza il nome (la corte che l'ha emessa, la data, il
   tipo di pronuncia, un numero di paragrafo) NON e' una fonte alternativa: e' la decisione stessa, che la ricerca per nome non ha
   trovato; non scriverla in fonte_alternativa e non e' un motivo per rispondere NO.
5. CRONOLOGIA. Se la data dell'atto e' anteriore alla data della decisione, l'atto non puo' riprenderla: la risposta e' NO. Se la
   data non e' nota, guarda se la finestra parla di fatti successivi o anteriori alla decisione.
6. Solo ora l'esito:
   SI: la proposizione e' distintiva, la finestra la afferma, la applica o argomenta da essa (anche con altre parole o in un'altra
   lingua), nessuna fonte alternativa la spiega, la cronologia e' compatibile.
   NO: luogo comune, solo il tema in comune, un'altra proposizione, un'altra fonte, cronologia incompatibile, un indice, una
   bibliografia, un testo rotto. Se la finestra indica questa decisione senza il nome (corte, data, paragrafo), decidi sulla
   proposizione come per ogni altra finestra e scrivilo nel motivo.
   FORSE: la proposizione e' distintiva e compatibile, ma la finestra non basta per deciderlo.
   Se non sei sicuro scegli FORSE, non SI.

Rispondi SOLO con un oggetto JSON, con i campi in quest'ordine:
{{"proposizione_specifica": "passo 1, una frase", "principio": "l'id del principio del fascicolo a cui corrisponde, o vuoto", "distintiva": "si" | "no", "frase_finestra": "passo 3: la frase della FINESTRA COPIATA ALLA LETTERA nella sua lingua, massimo 60 parole; vuota se non c'e'", "fonte_alternativa": "passo 4: la fonte a cui la finestra attribuisce l'idea; vuoto se nessuna", "cronologia": "compatibile" | "incompatibile" | "non nota", "esito": "si" | "no" | "forse", "motivo": "una frase, massimo quaranta parole"}}
Niente fuori dal JSON."""


def usa():
    """sostituisce la domanda e il codice nel modulo di L15 (che fa tutto il resto)"""
    L15.MODULO = MODULO
    L15.CODICE = CODICE


if __name__ == '__main__':
    usa()
    if sys.argv[1:2] == ['prepara']:
        # solo la taratura (le stesse 249 coppie), in un file suo
        import json
        R = L15.QUI / 'training' / 'ponte_impl' / 's09' / 'richieste'
        from tokenizers import Tokenizer
        tok = Tokenizer.from_file(str(L15.QUI / 'training' / 'ragionamento' / 'tokenizer_dsv4' / 'tokenizer.json'))
        dati = L15.L14.Dati()
        dom = L15.DomandaL15(L15.L14.Voci(), L15.L14.Atti(), dati.prove())
        tutte = {c['id']: c for c in dati.coppie_prova()}
        ids = [r['id'] for r in L15.L14.jl(R / 'ponte_impl_l14_ds_taratura.jsonl.gz')]
        print(json.dumps(L15.scrivi([L15.richiesta(dom, tutte[i], tok) for i in ids], R / 'ponte_impl_l15b_ds_taratura.jsonl.gz')))
    else:
        L15.main()
