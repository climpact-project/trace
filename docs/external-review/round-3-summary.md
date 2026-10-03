# CLIMPACT TRACE: third round of the external code review

3 October 2026. The third round read the package after the fixes of the second round (`tracepipe/`, `tests/`, the
live tools it twins) and checked each of the three points raised in round 2 against the code.

## Verdict

The package is sound and should be kept, not rewritten. The three points of round 2 are fixed in the code, and nothing
else in the package needs to change.

## The three points of round 2, verified

1. **Deduplication of the name search.** `chiave_testo` is the key of the old inline loop, character for character;
   deduplication per filing (`dedup_per_atto`) is off by default; `copie` is counted on the kept row in both modes; the
   log line on twins in other filings counts what it says.
2. **A case left with no rows.** The CSV and the discards file no longer fail with an `IndexError`: the columns come
   from `colonne_csv()`, or from `colonne_vuote()` when there are no rows.
3. **Merging with the platform.** The union rule is the one of the live tool `tools/unisci_e_aggiungi.py`, now covered
   by tests; a platform row whose document has no file is an orphan instead of a `TypeError`.

## Two residues, and what was done

1. **The patch for the live tools was narrower than the package.** With no rows and no discards, the live
   `tools/cerca.py` and `tools/cerca_s05.py` would have written an empty header. The patch was rewritten: with no rows
   the live tools now write the full row schema (`COLONNE_CSV`, the same columns as `colonne_vuote()` in the package),
   and a test checks that the two lists are equal. The live tools are used by runs still in progress, so the patch is
   checked with `git apply --check` and applied once those runs have finished, by a script that runs the tests and
   commits.
2. **The screen count of split citations.** `trace unisci` counted as split citations also the groups with nothing to
   merge (two rows naming the case and a code row already judged: no row is turned off). The count now includes only
   groups with at least one row to merge; `--compat` keeps the old count, so that the reference harness stays equal.
   Only the printed line changes: decisions and writes are the same. The test that pinned the old count was renamed
   `test_unione_due_righe_col_nome_nessuna_fusione`, and two tests cover the count in both modes.

An earlier suggestion was also taken up: `trace --help` now says which options reproduce which version of the registry
(S05, deduplication per filing, R08 and R10, L05 with five readings, R05 and R11, `--compat`).

## Checks after round 3

- `ruff check`: clean.
- Full test suite of the team's working copy, with the private data and the live scripts: 509 passed and 1 skipped
  (this repository's own suite, 432 tests, runs the ones that need no private data).
- Reference harness in compatibility mode (`prove/esegui_pacchetto.py`, compared by `prove/confronta.py`): 298 of 298
  output files equal, 0 different, 0 missing, 0 extra; 67 of 67 journals equal.
