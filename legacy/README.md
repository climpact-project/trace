# legacy: the code that produced the TRACE 0.1 data

These are the scripts that produced the data of TRACE 0.1, exactly as they ran on 2 October 2026: 118 files, each
numbered in reading order, with the index in [`tools/LEGGIMI.md`](tools/LEGGIMI.md) (in Italian, the team's working
language). They are kept unchanged as the record of what was run.

**The package [`tracepipe/`](../tracepipe) is the maintained version.** Each of its classes reproduces one of these
scripts, and a reference harness checks that they give the same outputs (see the main README, «How to verify»).

Notes for reading them:

- On the team's machine the same files run without the number; here the imports are rewritten for the numbered names.
- Comments, prompts and messages are in Italian.
- They expect the corpus folders (`markdown/`, `index/`, `training/`) next to `tools/`, and they talk to the CLIMPACT
  platform database (Firestore) and to a DeepSeek V4 Flash server; neither is part of this repository.
- The versions that came after 2 October (R10 surrounding pages, R11 majority vote of five readings, S05 name search on
  normalised text, D03 documents) are not in this folder: their exact code is frozen in [`versioni/`](../versioni),
  next to the registry entry that describes them.
