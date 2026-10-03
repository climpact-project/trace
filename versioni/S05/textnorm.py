#!/usr/bin/env python3
"""
Normalizzazione del testo, condivisa da tutto cio' che cerca dentro il corpus.

Il 70% dei documenti contiene caratteri tipograficamente invisibili ma
letteralmente diversi dai loro equivalenti ASCII: spazi unificatori, spazi a
larghezza zero, trattini di vario tipo, virgolette curve. Una ricerca di
"Urgenda v. State" non trova "Urgenda\\xa0v.\\xa0State", e il fallimento e'
silenzioso: non un errore, semplicemente zero risultati che sembrano plausibili.

Ogni ricerca nel corpus DEVE passare da qui, altrimenti perde riscontri veri
senza dare segno di averlo fatto.
"""

import re
import unicodedata

# Spazi non-ASCII -> spazio normale. Lo zero-width space sparisce del tutto:
# non e' uno spazio, e' un punto di interruzione di riga, quindi sostituirlo con
# uno spazio spezzerebbe parole altrimenti integre.
SPACES = {
    " ": " ",   # no-break space
    " ": " ",   # narrow no-break space
    " ": " ",   # thin space
    " ": " ",   # figure space
    " ": " ", " ": " ", " ": " ", " ": " ",
    " ": " ", " ": " ", " ": " ", "　": " ",
    "​": "",    # zero-width space
    "‌": "", "‍": "", "﻿": "",
    "­": "",    # soft hyphen: marca di sillabazione, non un trattino vero
}

# Trattini e lineette -> trattino ASCII.
DASHES = {
    "‐": "-", "‑": "-", "‒": "-", "–": "-",
    "—": "-", "―": "-", "−": "-",
}

# Virgolette curve -> dritte. Nei nomi di caso compaiono spesso apostrofi curvi.
QUOTES = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "′": "'", "″": '"', "«": '"', "»": '"',
}

_TABLE = str.maketrans({**SPACES, **DASHES, **QUOTES})

_HYPHEN_BREAK = re.compile(r"(\w)-\s*\n\s*(\w)")
_MULTISPACE = re.compile(r"[ \t]{2,}")

# Artefatto di export da Excel: il ritorno a capo (CR, 0x0D) viene serializzato
# come la stringa letterale '_x000D_'. Compare nel 34,2% dei Case Summary del
# dump. Non e' testo: se resta, finisce dentro i passaggi citati e dentro
# qualunque cosa venga dato in pasto a un modello linguistico.
_EXCEL_CR = re.compile(r"_x000[Dd]_\s*")


def normalize(text, join_hyphenation=True, collapse_spaces=True):
    """Testo confrontabile, con gli offset il piu' possibile preservati.

    join_hyphenation ricongiunge le parole spezzate a fine riga ('emis-\\nsions'
    -> 'emissions'): senza, un nome di caso a cavallo di due righe non si trova.
    Va disattivato quando gli offset devono corrispondere esattamente al file
    originale, perche' accorcia il testo.
    """
    if not text:
        return ""
    t = unicodedata.normalize("NFC", text)
    t = _EXCEL_CR.sub(" ", t)
    t = t.translate(_TABLE)
    if join_hyphenation:
        t = _HYPHEN_BREAK.sub(r"\1\2", t)
    if collapse_spaces:
        t = _MULTISPACE.sub(" ", t)
    return t


def flexible_pattern(phrase):
    """Regex che ritrova una frase anche se nel PDF e' spezzata o spaziata male.

    Ogni spazio diventa 'uno o piu' spazi, eventualmente con un a capo in mezzo',
    perche' nei PDF i nomi di caso vanno spessissimo a capo. I punti sono
    letterali ('v.' non deve valere come 'vx'), il resto e' citato.
    """
    parts = [re.escape(p) for p in phrase.split()]
    return re.compile(r"\s*\n?\s*".join(parts), re.I)


if __name__ == "__main__":
    probe = "OPINION OF ADVOCATE GENERAL"
    print("prima:", repr(probe))
    print("dopo :", repr(normalize(probe)))
    assert "OPINION OF ADVOCATE GENERAL" in normalize(probe)

    broken = "Urgenda Foundation v. State of the\nNetherlands"
    assert flexible_pattern("State of the Netherlands").search(broken)

    hyph = "greenhouse gas emis-\nsions reduction"
    assert "emissions" in normalize(hyph)

    print("autotest superati")
