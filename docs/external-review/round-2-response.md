# CLIMPACT TRACE: reply to the second-round review

3 October 2026. The bundle under review now is `trace-codice-giro3.zip`. Its plain-text twin is
`trace-codice-giro3.txt`. Both use a new name so that you can tell them apart from the earlier rounds. They contain
the same files as the second round: `pyproject.toml`, `tracepipe/`, `tests/`, `tools/{maggioranza,chiamata_deepseek,freni}.py`
and `tools/cerca_s05_per_atto.py`.

Every point below was checked against the code. New tests are in `tests/test_ricerca_giro3.py` unless another file is
named. They use synthetic data only.

## 1. Deduplication in `RicercaPerNome.esegui`

**(a) Constructor argument, CLI flag, default. Not a defect.** `dedup_per_atto` was already a constructor argument
(`dedup_per_atto=False` in `RicercaPerNome`) and a CLI flag (`trace cerca --dedup-per-atto`, `store_true`). The default
is the old global deduplication. A `--compat` harness run reproduces the expected outputs, with the result given at the
end of this note.
Tests: `test_deduplica_predefinita_come_il_vecchio_ciclo` runs 300 random row sets. For each one, the default
`deduplica` gives the same kept rows, discards and `copie` as a verbatim copy of the old inline loop.

**(b) CSV fields. The twin case is not a defect. The empty case was a defect and is fixed.** With `per_atto`,
`stesso_testo_di` is set on every kept row: it is `''` on the first passage with a given text. This means the first
row always has the key, and `DictWriter` cannot raise a `ValueError`. In the default mode no row has the key.

The real hole was a different one. If the date filter or the deduplication left a case with no rows, `righe[0]` raised
an `IndexError`, both for the CSV and for the SCARTI file.

The fix:
- the columns now come from `colonne_csv()`, the keys of all rows in order of first appearance. On a normal run this
  equals `list(righe[0].keys())`. A key found only on a later row becomes a column instead of an error;
- with no rows, the columns come from `RicercaPerNome.colonne_vuote()`. This is the `riga_csv` schema without
  `verbatim_intero`, plus `stesso_testo_di` with `per_atto`;
- SCARTI uses the same column list plus `motivo_scarto`.

A discard has no key of its own apart from `motivo_scarto`. Its `verbatim_intero` is left out on purpose, as in the
CSV, and a column it lacks (for example `stesso_testo_di`) is written empty.
Tests: `test_colonne_csv`, `test_csv_con_gemelle_per_atto` (the CSV header ends with `stesso_testo_di`, and SCARTI's
header is the CSV header plus `motivo_scarto`), `test_csv_su_tutto_il_corpus`,
`test_caso_svuotato_dal_filtro[False|True]` (every row is filtered out as earlier than the decision: the CSV has a
header only and the SCARTI file holds four rows), and `test_caso_senza_occorrenze`.

**(c) `copie` on the kept row. Not a defect.** The kept row's count goes up for each copy, in both modes. With
`per_atto` it counts copies in the same filing only.
Tests: `test_deduplica_su_tutto_il_corpus_copie_sulla_riga_tenuta`,
`test_deduplica_per_atto_stesso_atto_scartato_altro_atto_tenuto`, and the end-to-end CSV tests (`copie` = 3 globally,
2 per filing).

**(d) The 400-character key. Not a defect.** `chiave_testo` is the old key, character for character: whitespace is
collapsed, the text is stripped and lowercased, then cut at 400 characters after normalisation. `per_atto` uses the
same key paired with `document_id`, so it never compares the full passage. This is now stated in the docstring.
Tests: `test_chiave_di_400_caratteri_come_il_vecchio_ciclo` includes texts that differ only after character 400.
`test_deduplica_predefinita_come_il_vecchio_ciclo` covers the default mode. The per-filing mode is covered by the
existing `tests/test_ricerca.py::test_deduplica_per_atto_come_la_copia_viva`, which runs 200 random sets against
`tools/cerca_s05_per_atto.deduplica`. The two modes on the same rows:
same filing discarded, other filing kept with `stesso_testo_di`, as in
`test_deduplica_per_atto_stesso_atto_scartato_altro_atto_tenuto`.

**(e) The `gemelle` log line. Not a defect.** The line reads "stesso testo in un altro atto: N righe tenute, con
stesso_testo_di", so it counts kept rows that point to another filing, as it says. Discarded copies are printed
separately ("duplicati : N righe erano copie dello stesso testo").
Tests: both lines are checked in `test_csv_con_gemelle_per_atto` (1 twin, 1 duplicate).

## 2. `UnioneRighe.confronta`

**Judged code row with a single name row. This is the rule, not a defect. The code is unchanged and a test now
covers it.** Take a group where the old fusion rule split one citation into a NAME row and a CODE row (an ECLI or a
docket number), and a person has already judged the code row. The judged row is kept and the name row is merged into
it (`fusa_in`). The tool that wrote the platform rows (`tools/unisci_e_aggiungi.py`) does the same. A person's
judgement is never discarded, and both rows are the same citation. When the group has more than one name row, none of
them is turned off.
Tests: `test_unione_gruppo_misto_gia_giudicato`, `test_unione_gruppo_misto_non_giudicato` (nothing judged: the name
row stays), `test_unione_due_righe_col_nome_restano`, and the existing `tests/test_ricerca.py::test_unione_come_unisci`,
which compares the result with the live tool.

**`radice / file_di[doc]` without a file. This was a defect and is fixed.** A platform row with no `file`, in a
document the search does not have, raised a `TypeError` on `None`. It now counts as an orphan, the same as a missing
file. Runs where every document has a file are unaffected.
Test: `test_unione_riga_senza_file`.

**`list(righe[0].keys())` on an empty case. This was a defect and is fixed.** See 1(b).

## 3. Bundle name

This round's bundle is named `trace-codice-giro3.zip` and `trace-codice-giro3.txt`.

## Live scripts

The scripts in `tools/` that wrote the data have the same two holes: the empty case in `cerca.py` and `cerca_s05.py`,
and the missing file in `unisci_e_aggiungi.py`. They are in use tonight, or recorded in the version register, so they
are not changed in place. The fix is in `correzioni-strumenti-vivi-giro3.patch`, written and not yet applied.
`tools/cerca_s05_per_atto.py` is not in use, so it was fixed directly (`colonne_csv`, test
`test_colonne_della_copia_per_atto`). None of the runs that produced TRACE 0.1 had an empty case or a platform row
without a file, because either one would have stopped the run.

## Checks

- ruff check on `tracepipe/`: clean (correction of 10 October 2026: this line also said `tests/`, which is not
  ruff-clean). ruff format: `tracepipe/` and the new tests are formatted.
  `tests/test_recupero_s06.py` is not formatted yet: it belongs to a chain that is running now, and it will be
  formatted when that chain finishes.
- full pytest: 506 passed and 1 skipped. Of these, 15 are in `tests/test_ricerca_giro3.py`.
- harness in `--compat` mode (`prove/esegui_pacchetto.py`, compared by `prove/confronta.py`): all 298 files are equal
  to the expected outputs, with 0 different, 0 missing and 0 extra. All 67 journals are equal (compared without tool
  name and arguments). Steps 13 (search) and 14 (merge) are included for all the judgments TRACE 0.1 follows.
