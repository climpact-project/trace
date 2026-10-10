# A synthetic example

Everything in this folder is invented, for trying the code without the corpus: the cited case
*Example Foundation v. State of Exempla*, its three principles, two short filings that cite it, the five readings per
citation and the platform rows. No real filing, judgment or reading is copied here.

The folder has the layout of a project root, so every command takes it with `--radice`:

```
cited-cases/example-foundation.yaml        the cited case: name forms and three principles (own_share, duty_of_care, court_order)
cited-cases/casi.yaml                      its registry entry (TRACE_CASI=... for the commands that need the registry)
markdown/                                  two filings with <!-- page N --> marks: a judgment (4 pages), a petition (3 pages)
training/principi/example-foundation_ripresa_deepseek_cinque.jsonl   five readings per citation (L05)
training/principi/example-foundation_ripresa_righe_cinque.jsonl      the citations with their surrounding pages
training/principi/example-foundation_da_paragrafi.jsonl              the paragraph map applied to the citations
training/principi/example-foundation_punteggi_0.jsonl                reranker scores of the flagged passages
training/lessicali_example-foundation_deepseek_cinque.jsonl          five type readings per citation
training/principi/example-foundation_ripresa_deepseek.jsonl, ..._ripresa_righe.jsonl   the same, one reading (R05)
rows.json                                  the platform rows, {row id: fields}
```

What the four citations exercise:

- judgment, p. 2 (body): page 3 does not name the case but develops the duty of care; the readings copy a true
  sentence of page 3 and add an invented ending;
- judgment, p. 4 (footnote, with the identifier `EX:SC:2019:88`, one citation): `court_order` is in 2 of 5 readings;
- petition, p. 1: a chain mention, all five readings answer with an empty principle list;
- petition, p. 2 (footnote): the readings summarise the supported sentence instead of copying it.

## Commands

From the root of the repository, with the package installed (`pip install -e '.[pdf]'`):

```
trace --radice examples/synthetic --senza-giornale cerca --caso example-foundation --solo-lessicale --uscita /tmp/x.csv
trace --radice examples/synthetic --senza-giornale carica ripresa --caso example-foundation \
      --composizione R16 --etichetta cinque --fotografia examples/synthetic/rows.json
```

`--composizione` takes R05 (without `--etichetta`) and R11 to R16. `--fotografia` reads the rows from the file into
memory: it is a preview, `--scrivi` is refused. `--salva out.json` keeps the computed fields. Without
`--senza-giornale` a run is written in the operations journal, `examples/synthetic/giornale/`.

## Expected results

- `cerca`: 4 rows in 2 documents (pages 2 and 4 of the judgment, 1 and 2 of the petition).
- R11: judgment p. 4 takes `own_share` only, not uncertain; the chain mention is not touched (no valid reading).
- R12: judgment p. 4 takes `own_share` and `court_order` (votes `2/5`) and is flagged uncertain (`proposto_incerta`).
- R13: the chain mention gets `["nessuno"]`.
- R15: petition p. 2 gets the sentence extracted from the text, method `nota→corpo`: "Such knowledge gives rise to a
  duty to act with reasonable care and without delay against the risk to the petitioners." (the summarised sentence of
  the readings was "non trovata").
- R16: on judgment p. 2 the proof of page 3 with the invented ending is refused as not whole and repaired from the page
  text: "The duty of care owed by the Republic to its residents requires it to take reasonable and timely measures
  against a known and serious risk." (`prova_riparata`, the model's proof kept in `prova_modello`).

`tests/test_esempio_sintetico.py` checks all of this.
