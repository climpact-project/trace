"""I FRENI CONTRO LE RISPOSTE INVENTATE (30/09/2026, il PI: «e' gravissimo, va posto un freno»).

   Il 30/09 la rilettura ha trovato che DeepSeek, davanti a 130 pagine illeggibili (caratteri rotti), aveva risposto
   lo stesso, e in 5 casi aveva messo come «frase copiata dalla pagina» il testo del principio che stava nel prompt.
   La macchina risponde sempre, anche quando non dovrebbe: il freno sta nel codice, non nelle istruzioni.

   Quattro sbarramenti, da usare in ogni lettura:
     1. `leggibile(testo)`        prima di leggere: una pagina senza abbastanza parole vere non arriva al modello;
     2. `prova_trovata(prova, t)` dopo la risposta: la prova citata deve stare nella pagina, parola per parola;
     3. `prova_dal_prompt(...)`   la «prova» che coincide con un testo del prompt (principi, istruzioni) e' inventata;
     4. `verifica(lettura, ...)`  mette insieme i tre e restituisce l'esito, da contare nel controllo di completezza.
   Ogni sbarramento e' provato su un caso che DEVE fallire (`tools/freni_prova.py`)."""
import re

SOGLIA_LEGGIBILE = 0.5      # quota minima di token che sono parole vere (vedi `leggibile`)
MIN_PAROLE = 40             # sotto questo numero di parole la pagina e' vuota, non «illeggibile»
LUNGHEZZA_CONFRONTO = 60    # caratteri normalizzati con cui si cerca una prova nella pagina

_norm_re = re.compile(r'[^\w]+', re.U)


def norm(t):
    return _norm_re.sub(' ', str(t or '').lower()).strip()


def leggibile(testo):
    """(True/False, quota) - quota di token che sembrano parole di una lingua: lettere, lunghezza 2-25, almeno una vocale."""
    testo = str(testo or '')
    # LE SCRITTURE SENZA SPAZI (coreano, giapponese, cinese: 01/10/2026, il primo freno scambiava per rotte pagine
    # coreane perfette): si misura sui caratteri, non sulle parole. Leggibile se almeno il 60% dei caratteri non spazio
    # sono lettere e la pagina ne ha almeno 200.
    car = [c for c in testo if not c.isspace()]
    # 02/10/2026: anche thai, lao, khmer e birmano si scrivono senza spazi fra le parole: si misurano sui caratteri come
    # le scritture dell'Asia orientale (prima una pagina thai perfetta era «illeggibile»)
    cjk = sum(1 for c in car if c.isalpha() and (ord(c) > 0x2E7F or 0x0E00 <= ord(c) <= 0x0EFF or 0x1000 <= ord(c) <= 0x109F
                                                    or 0x1780 <= ord(c) <= 0x17FF))
    if car and cjk / len(car) > 0.3:
        lett = sum(1 for c in car if c.isalpha())
        quota = lett / len(car)
        return (len(car) >= 200 and quota >= 0.6), round(quota, 3)
    # i token di sola punteggiatura (puntini degli indici, trattini) non contano: un indice non e' una pagina rotta
    tok = [t for t in re.split(r'\s+', testo) if t and re.search(r'\w', t)]
    if len(tok) < MIN_PAROLE:
        return False, 0.0
    parole = 0
    for t in tok:
        s = re.sub(r'[^\w]', '', t)
        if not s.isalpha() or len(s) > 25:
            continue
        # 02/10/2026: OGNI scrittura non latina conta come parola, non solo quelle oltre U+2E7F. Prima cirillico, greco,
        # armeno, ebraico, arabo e devanagari non avevano vocali latine e finivano «illeggibili»: 69 pagine perfette in
        # 9 documenti del corpus (cause ucraine, kazake, bulgare, nepalesi), nessuno con citazioni dei sei casi.
        if any(ord(ch) >= 0x0370 for ch in s):       # scritture non latine (cirillico, greco, arabo, devanagari, CJK...)
            if len(s) >= 2 or ord(s[0]) > 0x2E7F:    # lettere sparse una per una («Ђ Ѓ ‚ ѓ»): spazzatura di codifica
                parole += 1
        elif len(s) >= 3 and re.search(r'[aeiouyàèéìòùäöüáíóúãõâêôîûœæ]', s, re.I):
            parole += 1                              # latino: almeno tre lettere e una vocale (fuori le lettere sparse)
    quota = parole / len(tok)
    return quota >= SOGLIA_LEGGIBILE, round(quota, 3)


# 03/10/2026: anche thai, lao, khmer e birmano, come nel controllo di leggibilita' (scritture senza spazi fra le parole)
_CJK = re.compile(r'[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\uf900-\ufaff\u0e00-\u0eff\u1000-\u109f\u1780-\u17ff]')


# IL TESTO DELL'ATTO SOTTO I SEGNI DEL SISTEMA (04/10/2026, R14). Il contesto mandato al modello porta i segni del brano
# ([[INIZIO/FINE DEL BRANO SEGNALATO]], `classifica_lessicali.py`) e del nome (⟦ ⟧), messi a un carattere preciso, spesso
# dentro una parola («Conve[[INIZIO DEL BRANO SEGNALATO]]ntion»): il modello copia la frase dell'atto senza i segni e il
# freno la dava «non trovata» (2.211 frasi sostenute su 4.696 non trovate al 04/10), o «inventata» quando la frase dell'atto
# coincide col testo di una sonda (6 su 9). Togliendo i segni senza mettere niente al loro posto torna il testo dell'atto.
_SEGNI = re.compile(r'\[\[(?:INIZIO|FINE) DEL BRANO SEGNALATO\]\]|[\u27e6\u27e7]')
# LA PAROLA SPEZZATA A CAPO (04/10/2026, R14): «Schutzbedürf-\nnis» nella pagina, «Schutzbedürfnis» nella frase copiata
# (684 frasi sostenute e 3.788 prove delle pagine attorno non trovate per questo, al 04/10). Si ricuce solo un trattino
# seguito da un a capo fra due lettere; il testo con il trattino resta confrontato com'e'.
_A_CAPO = re.compile(r'(?<=\w)[-\u00ad\u2010]\s*\n\s*(?=\w)')


def testi_atto(testo_pagina):
    """il testo della pagina com'e', senza i segni del sistema, e senza i segni con le parole spezzate a capo ricucite"""
    t = str(testo_pagina or '')
    s = _SEGNI.sub('', t)
    return [t, s, _A_CAPO.sub('', s)]


def prova_trovata(prova, testo_pagina, ricostruisci=False):
    """`ricostruisci` (R14, 04/10/2026): cerca la prova anche nel testo dell'atto senza i segni del sistema e con le parole
    spezzate a capo ricucite (`testi_atto`). Senza, il freno e' quello di prima (R05-R13), parola per parola."""
    p = norm(prova)
    if len(p) < 20:
        return False
    if ricostruisci:
        return any(prova_trovata(prova, t) for t in testi_atto(testo_pagina))
    # IN GIAPPONESE, CINESE E COREANO (01/10/2026): l'a capo della pagina cade anche dentro una parola («ドイ / ツ») e
    # l'OCR mette spazi attorno ai numeri («2019 年»); il modello copia la frase senza. Li' si confronta senza spazi.
    # Le scritture latine restano confrontate spazio per spazio, come prima.
    if _CJK.search(p):
        return p.replace(' ', '')[:LUNGHEZZA_CONFRONTO] in norm(testo_pagina).replace(' ', '')
    return p[:LUNGHEZZA_CONFRONTO] in norm(testo_pagina)


# ── R16: LA PROVA INTERA (04/10/2026, dal controllo dei tagli; si' del PI) ──────────────────────────────────────────
# Fino a R14 si cercavano nella pagina solo i primi 60 caratteri normalizzati della prova: una prova con l'inizio vero e
# la fine inventata passava. Con R16 (`intera=True`) la prova passa solo se passa R14 E se e' nella pagina PER INTERO:
#   - ogni tratto fra due puntini di omissione («...», «[...]», «…») si cerca per conto suo;
#   - senza spazi (parole spezzate dall'a capo: «frei heit»), e anche senza i numeri a se' della pagina (richiami di nota
#     fra le parole) e senza le cifre incollate a una parola, nella pagina e nella prova («domestic237»);
#   - sul testo della pagina unito alla pagina DOPO, anche senza le righe di nota: la frase continua dopo le note;
#   - senza i segni del contesto (===== PAGINA ... =====, [pagina N]);
#   - se non c'e' tutta: il 90% dei caratteri della prova in tratti di almeno 20 caratteri che stanno nella pagina: un finale
#     inventato non passa; un taglio muto nel mezzo passa se i due pezzi sono lunghi (limite dichiarato);
#   - lettere con l'accento scritto a parte («ü») ricomposte (NFC);
#   - solo nei documenti rifatti con l'OCR (D02): una lettera diversa per parola (il modello corregge un refuso dell'OCR).
# Misura sulle letture L05 del 03/10 (circa 119.000 prove e frasi trovate da R14): 768 non passano piu' (0,6%); su 20 lette,
# 15 non sono copie alla lettera (finali inventati, commenti aggiunti, parole tolte senza i puntini), 2 o 3 sono rifiuti a
# torto (intestazione della pagina dopo, caratteri rotti), 1 una riga d'indice troppo corta per essere una prova.
# Misura e campioni: training/misure/R16-PROVA-INTERA.md. Prova che deve fallire: tools/freni_prova.py.
_OMISSIONE = re.compile(r'\s*(?:\[\s*(?:\.\s*){2,}\]|\(\s*(?:\.\s*){2,}\)|(?:\.\s*){3,}|…|\[…\]|\(…\))\s*')
COPERTURA_INTERA = 0.9          # almeno il 90% della prova in tratti trovati
TRATTO_INTERO = 20
_NUMERI_SOLI = re.compile(r'(?<!\S)\d+(?!\S)')
_CIFRE_INCOLLATE = re.compile(r'(?<=[^\W\d_])\d+')
_RIGA_NOTA = re.compile(r'^\s*\(?\d{1,4}[\).]?\s+\S.*$', re.M)


def _n16(t):
    import unicodedata
    return _CIFRE_INCOLLATE.sub('', norm(unicodedata.normalize('NFC', str(t or ''))))


def _tratti(prova):
    return [p for p in (_n16(x) for x in _OMISSIONE.split(str(prova or ''))) if p]


def _copertura(p, t):
    """quota dei caratteri di p coperta da tratti di almeno TRATTO_INTERO caratteri che stanno in t (il piu' lungo da sinistra)"""
    i = cop = 0
    m = len(p)
    while i < m:
        lo, hi = TRATTO_INTERO, m - i
        if hi < lo or p[i:i + lo] not in t:
            i += 1
            continue
        while lo < hi:
            mm = (lo + hi + 1) // 2
            if p[i:i + mm] in t:
                lo = mm
            else:
                hi = mm - 1
        cop += lo
        i += lo
    return cop / max(m, 1)


_SEGNI_CONTESTO = re.compile(r'^=====.*=====\s*$|\[pagina \d+\]', re.M)   # classifica_lessicali.contesto


def _senza_note(t):
    return _RIGA_NOTA.sub(' ', t)


def _testi_r16(testo_pagina, seguito=''):
    base = [_SEGNI_CONTESTO.sub(' ', t) for t in testi_atto(testo_pagina)]
    if seguito:
        return base + [t + '\n' + seguito for t in base] + [_senza_note(t) + '\n' + _senza_note(seguito) for t in base]
    return base + [_senza_note(t) for t in base]


def _una_lettera(a, b):
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1 or min(len(a), len(b)) < 4:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) <= 1
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:]


def _con_refusi(tratti, t):
    w = t.split()
    for p in tratti:
        q = p.split()
        if q and not any(all(_una_lettera(x, y) for x, y in zip(q, w[i:i + len(q)])) for i in range(len(w) - len(q) + 1)):
            return False
    return True


def prova_intera(prova, testo_pagina, seguito='', ocr=False):
    """R16: la prova e' nella pagina per intero (vedi sopra). `seguito`: il testo della pagina dopo; `ocr`: documento D02."""
    tr = _tratti(prova)
    if sum(len(x) for x in tr) < 20:
        return False
    senza = [x.replace(' ', '') for x in tr]
    compatti = []
    for testo in _testi_r16(testo_pagina, seguito):
        n = _n16(testo)
        for t in (n, _NUMERI_SOLI.sub(' ', n)):
            if all(x in t for x in tr) or (ocr and _con_refusi(tr, t)):
                return True
            t = t.replace(' ', '')
            if all(x in t for x in senza):
                return True
            compatti.append(t)
    # la copertura per tratti solo dopo i confronti esatti, e una volta per testo diverso
    if len(senza) == 1:
        for t in dict.fromkeys(compatti):
            if _copertura(senza[0], t) >= COPERTURA_INTERA:
                return True
    return False


def prova_dal_prompt(prova, testi_prompt):
    """Vero se la prova coincide con (o e' contenuta in) uno dei testi che stavano nel prompt e non nella pagina."""
    p = norm(prova)
    if len(p) < 20:
        return False
    return any(p[:LUNGHEZZA_CONFRONTO] in norm(t) for t in (testi_prompt or []) if t)


def verifica(prova, testo_pagina, testi_prompt=(), ricostruisci=False, intera=False, seguito='', ocr=False):
    """Esito di una prova: 'trovata' | 'inventata' (copiata dal prompt) | 'non trovata' | 'assente'.
    `ricostruisci` (R14): vedi `prova_trovata`. `intera` (R16, vale con R14): la prova deve stare anche per intero
    (`prova_intera`, con `seguito` e `ocr`). Il controllo sul prompt non cambia."""
    if not prova or len(norm(prova)) < 20:
        return 'assente'
    if prova_trovata(prova, testo_pagina, ricostruisci or intera) and (not intera or prova_intera(prova, testo_pagina, seguito, ocr)):
        return 'trovata'
    if prova_dal_prompt(prova, testi_prompt):
        return 'inventata'
    return 'non trovata'
