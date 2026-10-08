# ruff: noqa: E501
"""The screen lines of the live scripts (Italian) rendered the way the package prints them (English, 06/10/2026).

The package was put into English on screen; the live scripts of ``tools/`` and the recorded outputs of the reference
harness (``prove/attesi``) still print the Italian text. The twin tests compare the two outputs line by line: they
translate the live one with :func:`in_inglese` first. Only the lines that carry a message are rewritten, numbers and
paths stay; a line that matches no rule is left as it is (so a message missed here shows up as a failing test).
"""

from __future__ import annotations

import re

_REGOLE: list[tuple[str, str]] = [
    # carica_*.py / caricatori
    (r"^ANTEPRIMA: niente scritto in banca dati$", "PREVIEW: nothing written to the database"),
    (r"^ANTEPRIMA: niente scritto$", "PREVIEW: nothing written"),
    (r"^scritte (\d+) righe$", r"written \1 rows"),
    (r"^esempio: ", "example: "),
    (r"^campi salvati in ", "fields saved in "),
    (r"^proposte salvate in ", "proposals saved in "),
    # controllo_completezza / controllo_finestra
    (r"^(\n?)(\w[\w-]*): (\d+) righe in Uptakes$", r"\1\2: \3 rows in Uptakes"),
    (r"^   tutto in ordine$", "   all in order"),
    (r"^   righe da giudicare senza proposte: (\d+) -> ", r"   rows to judge without proposals: \1 -> "),
    (r"^scritto trace_controlli/", "written trace_controlli/"),
    (r"^(\S+) \(sonde (\w+)\): pagine della finestra senza punteggio (\d+), citazioni con buchi (\d+)$",
     r"\1 (probes \2): window pages without a score \3, citations with gaps \4"),
    (r"^FINESTRA COMPLETA$", "WINDOW COMPLETE"),
    (r"^FINESTRA INCOMPLETA: (\d+) pagine senza punteggio$", r"WINDOW INCOMPLETE: \1 pages without a score"),
    # lettori
    (r"^(\d+) righe, (\d+) fatte, (\d+) da fare$", r"\1 rows, \2 done, \3 to do"),
    (r"^(\w+): (\d+) righe, (\d+) gia' fatte in tutto, (\d+) da fare$", r"\1: \2 rows, \3 already done in all, \4 to do"),
    (r"^fatto in (\d+)s$", r"done in \1s"),
    (r"^aggiunte: (\d+) righe da completare, (\d+) da capo, (\d+) letture scartate perche' la domanda e' cambiata$",
     r"additions: \1 rows to complete, \2 from scratch, \3 readings dropped because the question changed"),
    # unione_c03
    (r"^saltate \((.*)\): ", r"skipped (\1): "),
    (r"^coppie: (\d+) \| da scrivere (\d+) (.*) \| giudicate, da rivedere (\d+) (.*)$",
     r"pairs: \1 | to write \2 \3 | judged, to review \4 \5"),
    (r"^elenchi: ", "lists: "),
    (r"^scritte (\d+) righe \| copia ", r"written \1 rows | copy "),
    # pagine_gia_citate
    (r"^spunte del team saltate \((.*)\): ", r"team ticks skipped (\1): "),
    (r"^spunte del team tolte: (\d+) pagine su (\d+) righe giudicate$", r"team ticks removed: \1 pages on \2 judged rows"),
    (r"^righe toccate (\d+) \| segni (.*) \| principi tolti (\d+) \| per il team (\d+) \| giudicate saltate (\d+) righe "
     r"\((\d+) pagine\) \| «prosegue» tenute a parte (\d+)$",
     r"rows touched \1 | marks \2 | principles removed \3 | for the team \4 | judged skipped \5 rows (\6 pages) | "
     r"«prosegue» (continues) kept aside \7"),
    (r"^tolti per caso: ", "removed per case: "),
    (r"^tolti per principio: ", "removed per principle: "),
    (r"^ESEMPIO ", "EXAMPLE "),
    (r"^scritte (\d+) \| copia ", r"written \1 | copy "),
    # carica_s08
    (r"^(\d+) righe nuove \(esito «nuova» del TSV\)$", r"\1 new rows (outcome «nuova» of the TSV)"),
    (r"^  (\S+)\s+(\d+)   con una riga viva entro (\d+): +(\d+)   sole: +(\d+)$",
     lambda m: f"  {m[1]:20s} {m[2]:>4s}   with a live row within {m[3]}: {m[4]:>4s}   alone: {m[5]:>4s}"),
    (r"^  indizio C04: resta (\d+), scarterebbe (\d+) \(indizio, non esclusione\)$",
     r"  C04 clue: \1 stay, \2 would be discarded (a clue, not an exclusion)"),
    (r"^FALLITA ", "FAILED "),
    (r"^OK    ", "OK     "),
    (r"^copie dello stesso documento e righe rimandate \(D04, S06\): (\d+) escluse, ",
     r"copies of the same document and deferred rows (D04, S06): \1 excluded, "),
    (r"^copia di sicurezza: ", "safety copy: "),
    (r"^   scritte: (\d+)/(\d+)$", r"   written: \1/\2"),
    (r"^   scritte: (\d+) nuove, (\d+) unite$", r"   written: \1 new, \2 merged"),
    (r"^copia prima della scrittura: (.*) \((\d+) righe\)$", r"copy before writing: \1 (\2 rows)"),
    # L13
    (r"^(\d+) letture da fare \((\d+) gia' fatte\), (.*), contesto (\d+)$", r"\1 readings to do (\2 already done), \3, context \4"),
    (r"^fatte (\d+) in (\d+)s; FINITO$", r"done \1 in \2s; FINITO (finished)"),
    (r"^fatte (\d+) in (\d+)s; TEMPO: ne restano (\d+)$", r"done \1 in \2s; TIME: \3 left"),
    (r"^(.*) scritture preparate: (.*) \(A SECCO: niente scritto\)$", r"\1 writes prepared: \2 (DRY RUN: nothing written)"),
    # ricerca (cerca.py / unisci_e_aggiungi.py)
    (r"^Caso citato non trovato: ", "Cited case not found: "),
    (r"^Disponibili: (.*)$", lambda m: "Available: " + ("none" if m[1] == "nessuno" else m[1])),
    (r"^codebook    : (.*)   NON ANCORA APPROVATO — le codifiche prodotte ora non sono definitive$",
     r"codebook    : \1   NOT YET APPROVED: the codings produced now are not final"),
    (r"^codebook    : (.*)   approvato da (.*)$", r"codebook    : \1   approved by \2"),
    (r"^caso citato : ", "cited case  : "),
    (r"^forme       : ", "forms       : "),
    (r"^sonde       : ", "probes      : "),
    (r"^FILTRO      : solo ", "FILTER      : only "),
    (r"^rete lessicale \(esaustiva\)…$", "lexical network (exhaustive)…"),
    (r"^  ([\d,]+) occorrenze in (\d+)s$", r"  \1 occurrences in \2s"),
    (r"^stesso testo in un altro atto: ([\d,]+) righe tenute, con stesso_testo_di$",
     r"same text in another filing: \1 rows kept, with stesso_testo_di"),
    (r"^corpo o nota \(dal PDF\)…$", "body or footnote (from the PDF)…"),
    (r"^  FERMO: manca PyMuPDF, la colonna corpo/nota non si puo$", "  STOPPED: PyMuPDF is missing, the body/footnote column cannot"),
    (r"^  calcolare\. Installalo e rilancia:$", "  be computed. Install it and run again:"),
    (r"^RIGHE      : ", "ROWS       : "),
    (r"^documenti  : ", "documents   : "),
    (r"^sede \(proposta\):$", "seat (proposed):"),
    (r"^posizione  : corpo ([\d,]+)   nota ([\d,]+)$", r"position    : corpo (body) \1   nota (footnote) \2"),
    (r"^anteriori  : ([\d,]+) candidati in documenti precedenti al (\S+) — tolti \(con --con-anteriori restano\)$",
     r"earlier     : \1 candidates in documents before \2, removed (with --con-anteriori they stay)"),
    (r"^duplicati  : ([\d,]+) righe erano copie dello stesso testo$", r"duplicates  : \1 rows were copies of the same text"),
    (r"^SOSPETTE   : ([\d,]+) righe piu vicine a una formulazione esclusa che alla sonda — da leggere per prime$",
     r"SUSPECT     : \1 rows closer to an excluded formulation than to the probe, to be read first"),
    (r"^da guardare per prime: ([\d,]+) righe con confidenza bassa$", r"to look at first: \1 rows with low confidence"),
    (r"^casi       : ", "cases       : "),
    (r"^uscita     : ", "output      : "),
    (r"^scarti     : ", "discards    : "),
    (r"^istruzioni : ", "instructions: "),
    (r"^== (\S+): in piattaforma (\d+) righe col nome; ricerca nuova (\d+) citazioni$",
     r"== \1: on the platform \2 rows with the name; new search \3 citations"),
    (r"^   da aggiungere (\d+) \(codici (.*)\), validatori (.*), alla cieca (\d+)$",
     r"   to add \1 (codes \2), validators \3, blind \4"),
    (r"^   citazioni spezzate (\d+): righe da unire (\d+), con una riga giudicata (\d+), con PIU' righe giudicate (\d+)$",
     r"   split citations \1: rows to merge \2, with one judged row \3, with MORE than one judged row \4"),
    (r"^   righe della piattaforma senza gruppo nella ricerca nuova \(non si toccano\): (\d+); "
     r"gruppi con piu' righe che nominano il caso \(restano tutte\): (\d+)$",
     r"   platform rows with no group in the new search (left alone): \1; groups with several rows that name the case "
     r"(all stay): \2"),
]
_COMPILATE = [(re.compile(p), r) for p, r in _REGOLE]


def in_inglese(testo: str) -> str:
    """The text of a live script's screen output with its message lines in the package's English."""
    righe = []
    for riga in testo.split('\n'):
        for rx, r in _COMPILATE:
            nuova, n = rx.subn(r, riga, count=1)
            if n:
                riga = nuova
                break
        righe.append(riga)
    return '\n'.join(righe)
