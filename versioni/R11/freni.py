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


_CJK = re.compile(r'[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\uf900-\ufaff]')


def prova_trovata(prova, testo_pagina):
    p = norm(prova)
    if len(p) < 20:
        return False
    # IN GIAPPONESE, CINESE E COREANO (01/10/2026): l'a capo della pagina cade anche dentro una parola («ドイ / ツ») e
    # l'OCR mette spazi attorno ai numeri («2019 年»); il modello copia la frase senza. Li' si confronta senza spazi.
    # Le scritture latine restano confrontate spazio per spazio, come prima.
    if _CJK.search(p):
        return p.replace(' ', '')[:LUNGHEZZA_CONFRONTO] in norm(testo_pagina).replace(' ', '')
    return p[:LUNGHEZZA_CONFRONTO] in norm(testo_pagina)


def prova_dal_prompt(prova, testi_prompt):
    """Vero se la prova coincide con (o e' contenuta in) uno dei testi che stavano nel prompt e non nella pagina."""
    p = norm(prova)
    if len(p) < 20:
        return False
    return any(p[:LUNGHEZZA_CONFRONTO] in norm(t) for t in (testi_prompt or []) if t)


def verifica(prova, testo_pagina, testi_prompt=()):
    """Esito di una prova: 'trovata' | 'inventata' (copiata dal prompt) | 'non trovata' | 'assente'."""
    if not prova or len(norm(prova)) < 20:
        return 'assente'
    if prova_trovata(prova, testo_pagina):
        return 'trovata'
    if prova_dal_prompt(prova, testi_prompt):
        return 'inventata'
    return 'non trovata'
