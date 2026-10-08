<!--
English translation of the prompts in tracepipe/istruzioni.py
(MODULO_TIPO, MODULO_PAGINE_ATTORNO; the L04 prompt is MODULO_PAGINE_ATTORNO without three additions, see below).
Original: tracepipe/istruzioni.py
SHA-256 of the original: 3fc5c207be9d8d646aea1daedd42d11fda1900f0b7f7b36eadf0be17e0ef557a
A reading aid, not a runnable copy: the readers sent the Italian text. Placeholders in braces ({fascicolo}, {forma}...)
are filled by the code. The codes the model must answer with (the values of "riferimento", "tipo_citazione",
"chi_parla", and the names of the JSON fields) are protocol values written to the database: they stay Italian in the
translation, with their meaning in square brackets.
-->

# Prompts of tracepipe/istruzioni.py, in English

## MODULO_TIPO (readings L02 for Urgenda and L03 for the other cases): type of citation

```
You are a jurist who codes case-law citations for a research project on climate litigation.
The cited case is URGENDA: Stichting Urgenda v. State of the Netherlands (Rechtbank Den Haag 24/6/2015,
Gerechtshof Den Haag 9/10/2018, Hoge Raad 20/12/2019). Whoever cites any of the three instances cites Urgenda.

Below you find the CASE FILE, written for the research group: it only serves to know what Urgenda decided and with
which paragraphs. The questions of this task are NOT those of the case file: they are the ones at the bottom.

{fascicolo}   [the case file]

========== END OF THE CASE FILE ==========

CODEBOOK OF THE PROJECT (version {versione}). Categories of the TYPE OF CITATION, exclusive (one per passage):
{tipi}   [one line per type: code, name, definition, clues]

WHO SPEAKS (who states the passage):
{chi}

Borderline cases and rules of the codebook:
{limiti}

DOCUMENT: {case_name} ({tipo_atto}, {data}), document {document_id}.
The lexical net found the name «{forma}» at the point marked with ⟦ ⟧, inside the passage enclosed between
{inizio} and {fine}. I give you the page of the citation with the end of the previous page and the beginning of the
next. READ IT IN FULL, notes included: the reasoning starts before the passage and ends after it, and only the
context says what the text does with Urgenda and who is speaking (the court, a party that the court summarises, an
amicus...).
---
{contesto}   [the context]
---

Answer ONLY with a JSON object with these fields, in this order:
1. "riferimento" [reference]: what «{forma}» is at this point. One of: "caso_urgenda" [the case or one of its
   rulings], "fondazione_urgenda" [the foundation as a subject, not the judgment: for example a party in another
   proceeding], "indice_o_elenco" [index, table of authorities, bibliography, heading, list without text],
   "omonimo" [another meaning of the word], "non_determinabile" [cannot be determined].
2. "tipo_citazione" [type of citation]: EXACTLY ONE of the codes of the codebook: "menzione_in_catena" [chain
   mention], "descrittiva" [descriptive], "sostanziale" [substantive], "distinguente" [distinguishing], "critica"
   [critical], "implicita" [implicit]. Even if "riferimento" is not "caso_urgenda", choose the closest category (usually
   "menzione_in_catena").
3. "chi_parla" [who speaks]: one of the codes of WHO SPEAKS: "corte" [court], "parte" [party], "interveniente"
   [intervener], "amicus", "non_determinabile".
4. "proposizione" [proposition]: ONE sentence in Italian: the proposition that the passage attributes to Urgenda or
   draws from it (what the text says Urgenda established, or what it derives from it). Empty string if there is none.
5. "paragrafi_urgenda" [Urgenda paragraphs]: paragraph numbers of Urgenda cited in the passage, a list (empty if none).
6. "motivo" [reason]: one sentence, thirty words at most, that justifies type and speaker with the context.

Nothing outside the JSON.
```

For the other cases the Urgenda lines become generic (the case name and decision date replace the first paragraph;
"caso_urgenda" becomes "caso", "fondazione_urgenda" becomes "soggetto_omonimo" [namesake subject: the person, party or
organisation that bears the name, not the judgment, for example an activist or a party in another proceeding], and
"paragrafi_urgenda" becomes "paragrafi_caso" [paragraphs of the case]); see `modulo_tipo`.

## MODULO_PAGINE_ATTORNO (reading L05): principles taken up, surrounding pages, supported sentence

```
You are a jurist who codes the uptakes of a climate judgment in later filings.
The cited case is {nome_caso}.
{fascicolo}   [the case file]
THE PRINCIPLES OF THE CASE (id, title, reference text):
{principi}

DOCUMENT: {case_name} ({tipo_atto}, {data}), document {document_id}.
The lexical net found the name «{forma}» at the point marked with ⟦ ⟧, inside the passage enclosed between
[[INIZIO DEL BRANO SEGNALATO]] [start of the flagged passage] and [[FINE DEL BRANO SEGNALATO]] [end of the flagged
passage]. Here is the page of the citation with the end of the previous one and the beginning of the next:
---
{contesto}
---
{aiuto_paragrafi}   [help from the paragraph map]
NEARBY PAGES OF THE SAME FILING (possible continuation of the uptake, without the name of the case):
{vicine}

QUESTION 1. Which principles of the case does this citation take, that is, use, apply, discuss or reject? More than
one is possible. "nessuno" [none] if the citation takes no principle (list of precedents, only a description of the
facts or of the outcome, example of litigation). "altro" [other] if it takes something that is not in the list: write it
in one sentence.

QUESTION 2. For each nearby page: does THE SAME UPTAKE continue? Yes, only if it develops one of the principles taken
by the citation within the same reasoning started by the citation. No, if it talks about something else, or if it
supports the same theme on another source (general ECHR, Paris Agreement, another case) with no link to the citation.
LOOK AT THE NOTES: if the sentence of the nearby page has a note of its own that attributes it to another source, it
does not continue.
If the citation takes no principle (list, description only), no page continues.

QUESTION 3. Which SENTENCE OF THE FILING supports the citation? It is the sentence of the text to which the note citing
the case is attached, or the sentence that contains the citation. Copy it LETTER FOR LETTER, in its language, at most
60 words. The principle is decided on this sentence, not on the topic of the page.

Answer ONLY with a JSON object:
{"frase_sostenuta": "sentence copied letter for letter", "principi": [id...], "altro": "", "motivo": "one sentence, at most thirty words",
  "vicine": [{"pagina": number, "prosegue": true or false, "principio": "id or empty", "prova": "sentence COPIED LETTER FOR LETTER from the page, in its language, at most 25 words; never a summary of yours"}]}
Nothing outside the JSON.
```

JSON field names: `frase_sostenuta` [supported sentence], `principi` [principles], `altro` [other], `motivo` [reason],
`vicine` [nearby pages], `pagina` [page], `prosegue` [continues], `principio` [principle], `prova` [evidence].

## L04 (the principles reading of 27 September 2026)

The L04 prompt is the L05 one without three additions of 28 September: the case file (`{fascicolo}`), the rule of the
notes ("LOOK AT THE NOTES...") with the evidence copied word for word, and question 3 on the supported sentence (and so
without the field `frase_sostenuta`). In L04 the field `prova` reads: "sentence quoted from the page, at most 25
words". It is built by `istruzioni_l04()` from the L05 text.
