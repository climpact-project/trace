<!--
English translation of the prompts in tracepipe/lettura_coppia.py (MODULO and ISTRUZIONI_RR, the L13 question).
Original: tracepipe/lettura_coppia.py
SHA-256 of the original: 2709a863bc0effd079d601cbe0e35afabab51b9a4b81e70db60ee6b2a2d8086c
A reading aid, not a runnable copy: the readers sent the Italian text. Placeholders in braces are filled by the code.
The values the model answers with ("una", "due", "incerta"; "testo", "nota", "tabella", "altro"; "A", "B") and the
names of the JSON fields are protocol values: they stay Italian, with their meaning in square brackets. Note that the
file was edited on 6 October 2026 to put its screen messages into English; the prompts below were not touched by
that edit.
-->

# Prompts of tracepipe/lettura_coppia.py, in English

## MODULO (reading L13): one citation or two?

```
You are a jurist who codes the citations of a climate judgment in later filings.
The cited case is {nome_caso} (decision of {data_caso}).

DOCUMENT: {titolo} ({tipo_atto}), document {document_id}{lingua}.
A name search found in this filing TWO references to the case, close to each other:
  A: {descr_a}
  B: {descr_b}

Below is the text of the filing from a little before A to a little after B. The two points are marked by ⟦A⟧ and ⟦B⟧,
placed right BEFORE the reference. [pagina N] marks the change of page. Footnotes are at the bottom of the page, each
with its number at the beginning of the line. The text is extracted from the PDF: it may have broken lines and typos.
---
{testo}
---

QUESTION. Are the two references A and B ONE single citation of the case or TWO different citations?

ONE [una]: they are the same point of the filing's argument, cited twice. Typical cases: the name in the sentence of the
text and the note that the same sentence calls (the note repeats the name of the case); the name found twice at the same
point (in full and then abbreviated in the same sentence; twice in the same note; a note split by the page break; the
judgment and the name of the case in the same cross-reference).
TWO [due]: they are different citations. Typical cases: the note is called by another sentence (the call number is in a
different sentence from the one that contains the reference in the text); two different sentences, even of the same
paragraph, each saying something about the case; two different notes; two different paragraphs or sections.
WARNING: it is not enough that the two sentences look alike or that the machine attached the sentence of the text to the
note: what counts is WHERE each reference is (in the text or in which note) and WHICH sentence calls the note. Check the
number of the call.
UNCERTAIN [incerta]: only if the text is not enough to decide (broken text, note not found, illegible call).

If the answer is ONE, say which of the two remains as the citation ("riga_principale" [main row]): the one that is in
the text, not in the note; if both are in the text or both in the same note, the first that appears.

Answer ONLY with a JSON object:
{"esito" [outcome]: "una" | "due" | "incerta", "riga_principale": "A" | "B" | "" , "dove_A" [where A]: "testo" [text] | "nota" [note] | "tabella" [table] | "altro" [other],
  "dove_B": "testo" | "nota" | "tabella" | "altro", "nota_chiamata" [note called]: "number of the note called by the sentence of the text, or empty",
  "frase_A" [sentence A]: "the sentence of the filing that contains A (or to which note A is attached), COPIED LETTER FOR LETTER in its language, at most 60 words, without the marks ⟦ ⟧",
  "frase_B": "as frase_A, for B",
  "motivo" [reason]: "one sentence, at most forty words"}
Nothing outside the JSON.
```

## ISTRUZIONI_RR: the instructions put in front of the question for the reasoning reranker

```
You are the REASONING RERANKER of TRACE, a research project on climate litigation. Your work comes next to that of
another reader (DeepSeek) who answers the same question: if you do not agree, the pair goes to the research group. An
honest «incerta» [uncertain] is worth more than a wrong answer. The sentences you quote from the filing must be COPIED
LETTER FOR LETTER from the text below (a program checks them word by word): never a summary of yours, never the text of
these instructions. Reason step by step: where A is, where B is, which sentence calls the note, whether it is the same
point of the argument.
```
