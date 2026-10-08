# translations/

English renderings of the Italian texts that the TRACE 0.1 readers were given. They are **reading aids, not runnable
copies**: the originals stay in Italian because the models read them, and every original is fingerprinted. Each
translated file says at the top which original it translates and the SHA-256 of that original at the time of the
translation; `tools/pubblica_vetrina.py` checks that the fingerprint still matches the file published in this
repository, so a translation that no longer matches its original is flagged.

| Translation | Original | What it is |
|---|---|---|
| [`prompts/istruzioni.en.md`](prompts/istruzioni.en.md) | `tracepipe/istruzioni.py` | the prompts of the type reading (L02, L03) and of the uptake reading (L05; L04 derived) |
| [`prompts/lettura_coppia.en.md`](prompts/lettura_coppia.en.md) | `tracepipe/lettura_coppia.py` | the L13 question (one citation or two?) and the instructions of the reasoning reranker |
| [`codebook/citazioni.en.yaml`](codebook/citazioni.en.yaml) | `codebook/citazioni.yaml` | the codebook in use (0.5-pilot) |
| [`t04/1_intestazione_e_regole_generali.en.txt`](t04/1_intestazione_e_regole_generali.en.txt) | `prompt/1_intestazione_e_regole_generali.txt` in the T04 package | T04 prompt: instruction and general rules G01 to G08 |
| [`t04/4_domanda_e_formato_risposta.en.txt`](t04/4_domanda_e_formato_risposta.en.txt) | `prompt/4_domanda_e_formato_risposta.txt` in the T04 package | T04 prompt: the question and the format of the answer |

The third file of the T04 prompt folder, `esempi_di_addestramento_id.txt`, is a list of 94 identifiers of rows of the
registry of citations, not text: there is nothing to translate.

Rules of the translation: the codes the models answer with (`caso_urgenda`, `sostanziale`, `una`, `si`...) and the
names of the JSON fields are protocol values written to the database, so they stay Italian, with their meaning in
square brackets; placeholders in braces are those of the code; quotations in English, German, French... inside the
originals are unchanged. Not translated here: the frozen prompts in `versioni/` (they are the copies that carry the
fingerprints of the registry; most are earlier states of the texts above), the case files and paragraph maps in
`cited-cases/` (translation in progress), and the text of the filings. A glossary of the Italian terms that remain in
identifiers is in the [README](../README.md#a-note-on-language) of the repository.
