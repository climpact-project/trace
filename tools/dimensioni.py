#!/usr/bin/env python3
"""LE QUATTRO DIMENSIONI, PRECOMPILATE DAL SISTEMA.

PERCHE' ESISTE. Il disegno chiede che ogni riferimento sia descritto lungo
quattro dimensioni tenute separate: come il caso e' invocato, che cosa fa
nel ragionamento, DOVE STA nel documento, CHI lo cita. Chiedere a una
persona di deciderle a mano riga per riga non regge: dieci casi al mese
producono migliaia di righe, e il controllo manuale del 20% diventerebbe
100%.

Qui il sistema PROPONE, e chi legge conferma o corregge. Due dimensioni su
quattro si ricavano dal testo con buona affidabilita'; per la terza
(`tipo_citazione`, che cosa fa il riferimento) non c'e' segnale testuale
sufficiente e resta al lettore.

LE PROPOSTE NON SI SOVRASCRIVONO. Ogni dimensione esce in due colonne:
`<nome>_auto`, che il sistema scrive e nessuno modifica, e `<nome>`, che
nasce con lo stesso valore e che chi legge puo' correggere. Confrontandole
si misura il tasso di disaccordo fra macchina e lettore — che e' il dato
che dice se la precompilazione e' affidabile, e che sparirebbe se la
proposta venisse sovrascritta.

CIASCUNA PROPOSTA PORTA UNA CONFIDENZA. `bassa` significa che nessun indizio
e' stato trovato e il valore e' un ripiego: sono le righe da guardare per
prime.
"""

import re

# ── Dimensione: chi cita ────────────────────────────────────────────────
#
# Il tipo di atto e' gia' noto per ogni documento, quindi la parte piu'
# grossa di questa dimensione e' gratis: chi firma un atto introduttivo e'
# una parte, chi firma una decisione e' l'organo giudicante.
#
# Il caso che il tipo di atto NON risolve e' il piu' importante: dentro una
# decisione, la corte spesso riassume cio' che le parti hanno sostenuto.
# "I ricorrenti invocano Urgenda" in una sentenza non e' la corte che cita
# Urgenda. Confondere i due gonfia proprio i casi piu' discussi.

DA_TIPO_ATTO = {
    'decisione': 'corte',
    'ordinanza': 'corte',
    'atto introduttivo': 'parte',
    'replica': 'parte',
    'istanza': 'parte',
    'memoria': 'parte',
    'opposizione': 'parte',
    'amicus': 'amicus',
}

# ── Indizi di difesa riportata ──────────────────────────────────────────
#
# Le formule con cui una corte attribuisce un argomento a chi glielo ha
# proposto. Sono espressioni di rito, quindi stabili dentro ciascuna
# lingua: e' il motivo per cui si possono cercare.
#
# LE LINGUE SONO QUELLE EFFETTIVAMENTE PRESENTI NEL CORPUS. Dove manca la
# lingua, l'indizio non si trova e la confidenza scende a `bassa`: il
# sistema dichiara di non sapere invece di indovinare.

_ATTORI = (r'plaintiffs?|applicants?|claimants?|appellants?|petitioners?|'
           r'respondents?|defendants?|complainants?|intervenors?|'
           r'ricorrent[ei]|resistent[ei]|attor[ei]|convenut[oi]|'
           r'demandantes?|demandados?|recurrentes?|'
           r'requ[eé]rants?|d[eé]fendeurs?|'
           r'kl[aä]ger(?:in)?(?:nen)?|beklagten?|'
           r'eisers?|verweerders?|'
           r'autores?|r[eé]us?')

INDIZI_DIFESA = [
    re.compile(p, re.I) for p in (
        # inglese
        rf'\b(?:the\s+)?(?:{_ATTORI})\b[^.]{{0,60}}?\b'
        r'(?:argue|argues|argued|contend|contends|submit|submits|submitted|'
        r'assert|asserts|maintain|maintains|claim|claims|rely|relies|relied|'
        r'invoke|invokes|invoked|point|points|cite|cites|cited)\b',
        rf'\baccording to (?:the\s+)?(?:{_ATTORI})\b',
        r'\b(?:it is|it was) (?:submitted|argued|contended|alleged)\b',
        r'\bcounsel for (?:the )?\w+',
        r'\bin (?:their|his|her|its) (?:submission|brief|pleadings?|'
        r'written observations|memorial)\b',
        r'\b(?:the )?(?:parties|applicants?|plaintiffs?) (?:refer|refers|referred) to\b',
        # italiano
        rf'\b(?:i|le|il|la)\s+(?:{_ATTORI})\b[^.]{{0,50}}?\b'
        r'(?:sostengono|sostiene|deducono|deduce|lamentano|lamenta|'
        r'assumono|assume|invocano|invoca|richiamano|richiama|eccepiscono)\b',
        r'\bsecondo (?:il|la|i|le)\s+\w+',
        r'\ba (?:dire|avviso|parere) (?:del|della|dei)\b',
        # spagnolo
        rf'\b(?:los|las|el|la)\s+(?:{_ATTORI})\b[^.]{{0,50}}?\b'
        r'(?:sostienen|sostiene|alegan|alega|argumentan|argumenta|'
        r'invocan|invoca|citan|cita|aducen)\b',
        r'\bseg[uú]n (?:el|la|los|las)\s+\w+',
        # francese
        rf'\b(?:les|le|la)\s+(?:{_ATTORI})\b[^.]{{0,50}}?\b'
        r'(?:soutiennent|soutient|font valoir|fait valoir|invoquent|invoque|'
        r'all[eè]guent|all[eè]gue|se pr[eé]valent)\b',
        r'\bselon (?:le|la|les)\s+\w+',
        # tedesco
        rf'\b(?:die|der|das)\s+(?:{_ATTORI})\b[^.]{{0,50}}?\b'
        r'(?:machen geltend|macht geltend|tragen vor|tr[aä]gt vor|'
        r'berufen sich|beruft sich)\b',
        r'\bnach (?:Auffassung|Ansicht) (?:der|des)\b',
        # olandese
        rf'\b(?:de|het)\s+(?:{_ATTORI})\b[^.]{{0,50}}?\b'
        r'(?:stellen|stelt|voeren aan|voert aan|beroepen zich|beroept zich)\b',
        r'\bvolgens (?:de|het)\s+\w+',
        # portoghese
        rf'\b(?:os|as|o|a)\s+(?:{_ATTORI})\b[^.]{{0,50}}?\b'
        r'(?:alegam|alega|sustentam|sustenta|invocam|invoca)\b',
        r'\bsegundo (?:o|a|os|as)\s+\w+',
    )
]

# Intestazioni che aprono una sezione dedicata alle difese: valgono per
# tutto il seguito, non solo per la frase in cui compaiono.
INTESTAZIONI_DIFESE = re.compile(
    r'^\s*(?:[IVXLC]+\.?\s*|\d+[\.\)]\s*)?'
    r'(?:(?:the\s+)?(?:parties[’\']?\s+)?'
    r'(?:submissions?|arguments?|contentions?|pleadings?|'
    r'position of the parties|arguments of the parties|'
    r'summary of (?:the )?(?:arguments|submissions))'
    r'|argomenti (?:del|delle|dei) part[ei]|le difese|posizioni delle parti'
    r'|alegaciones|argumentos de las partes'
    r'|arguments des parties|th[eè]ses des parties'
    r'|vorbringen der (?:parteien|beteiligten)'
    r'|standpunt(?:en)? van (?:de )?partijen'
    r')\s*:?\s*$', re.I | re.M)

# ── Dimensione: dove sta il riferimento ─────────────────────────────────
#
# Corpo o nota a pie' di pagina. Negli atti giuridici la nota e' il luogo
# in cui si dice A CHI si attribuisce un principio: un riferimento in nota
# e un riferimento nel corpo non pesano uguale, e sommarli e' un errore.
#
# NON E' INFALLIBILE, e non pretende di esserlo: quando la zona non si
# distingue, dichiara che non c'e' invece di indovinare.

# IL SEGNALE E' LA NUMERAZIONE CONSECUTIVA, non l'aspetto della riga.
#
# Primo tentativo, scartato: risalire dal fondo finche' le righe "sembrano
# note". Falliva su due cose viste nel corpus reale — un numero di pagina in
# ultima riga interrompeva la risalita prima di arrivare alle note, e le
# note oltre la novecentonovantanovesima (Klimaatzaak ne ha piu' di mille)
# non venivano riconosciute. In piu' l'estrazione a volte attacca le note
# alla fine dell'ultima riga di testo, e una regola per righe non le vede.
#
# Qui si cercano i marcatori ovunque nella meta' bassa della pagina e si
# tiene la piu' lunga sequenza CRESCENTE: due o piu' numeri che salgono di
# poco, ciascuno seguito da un capoverso. E' cio' che distingue una zona di
# note da un numero qualsiasi in mezzo al testo — e nessun testo continuo
# produce per caso una sequenza crescente di marcatori.

_MARCATORE = re.compile(
    r"(?:(?<=^)|(?<=[\s.\)\]\u201d\"'\u2019]))"   # a inizio riga o dopo una chiusura
    r'[\(\[]?(\d{1,4})[\)\].,:]?[ \t]+'      # il numero della nota
    r'(?=[A-Z“"\(\[«\u00C0-\u024F])',        # e un capoverso che comincia
    re.M)


# IL SEGNALE NON STA NEL MARKDOWN, STA NEL PDF.
#
# Due tentativi sul testo estratto, entrambi scartati dopo averli misurati:
#
#   1. risalire dal fondo della pagina finche' le righe "sembrano note".
#      Un numero di pagina in ultima riga interrompeva la risalita, e le
#      note oltre la millesima (Klimaatzaak) non erano riconosciute.
#   2. cercare sequenze di numeri crescenti. Trovava note nel 70% delle
#      pagine — assurdo — perche' anche "[31] [32] [33]" e' una sequenza
#      crescente: la numerazione dei paragrafi imita quella delle note.
#      Filtrando per posizione e densita' scendeva al 15%, ma leggendo i
#      risultati restavano dentro i numeri di paragrafo degli atti
#      ("45. DOE estimates...") e le citazioni di legge ("42 U.S.C. §").
#
# Cio' che distingue davvero una nota da una riga di testo e' il CORPO DEL
# CARATTERE e la POSIZIONE SULLA PAGINA — e l'estrazione in markdown
# appiattisce entrambi. Nel PDF ci sono, e si leggono.
#
# QUANTO COSTA. Un PDF si apre una volta per documento, non per riga: per
# un caso da duemila righe sono qualche centinaio di aperture.
#
# DOVE NON FUNZIONA, E LO DICE. I 668 documenti rifatti con OCR hanno uno
# strato di testo generato da tesseract, che assegna a tutta la pagina lo
# stesso corpo: li' il segnale non esiste e la risposta e'
# `non_determinabile`. Sono il 4% del corpus.

_PDF_APERTI = {}


def _pagine_note(pdf, npag):
    """(testo del corpo, testo delle note) di una pagina. None se il PDF
    non distingue i due — pagina piatta, o OCR."""
    import statistics
    try:
        import fitz
    except ImportError:
        # NON SI RIPIEGA IN SILENZIO. Senza PyMuPDF la dimensione corpo/nota
        # sparisce e ogni riga esce `non_determinabile`: chi lavora non se ne
        # accorge e perde una colonna per mesi. Successo davvero, provando la
        # cartella condivisa il 31 luglio 2026 — l'installatore non lo
        # installava e il passaggio sui PDF durava zero secondi.
        raise RuntimeError(
            'PyMuPDF non e installato: la colonna corpo/nota non si puo '
            'calcolare. Installalo con  ./.venv/bin/pip install pymupdf')
    chiave = str(pdf)
    d = _PDF_APERTI.get(chiave)
    if d is None:
        try:
            d = fitz.open(pdf)
        except Exception:
            _PDF_APERTI[chiave] = False
            return None
        _PDF_APERTI[chiave] = d
    if d is False or npag < 1 or npag > d.page_count:
        return None
    try:
        pg = d[npag - 1]
        alt = pg.rect.height
        righe = []
        for blocco in pg.get_text('dict')['blocks']:
            for l in blocco.get('lines', []):
                t = ''.join(sp['text'] for sp in l['spans'])
                if not t.strip():
                    continue
                dim = statistics.median(
                    [sp['size'] for sp in l['spans']
                     for _ in range(max(1, len(sp['text'])))])
                righe.append((l['bbox'][1], dim, t))
    except Exception:
        return None
    if len(righe) < 4:
        return None
    corpo_dim = statistics.median(
        [dim for _, dim, t in righe for _ in range(len(t))])
    # PAGINA PIATTA: un solo corpo di carattere. Non c'e' niente da
    # distinguere — e' il caso dei PDF rifatti con OCR.
    if not any(dim < corpo_dim * 0.94 for _, dim, _ in righe):
        return None
    note, testo = [], []
    for y, dim, t in righe:
        (note if (dim < corpo_dim * 0.94 and y > alt * 0.55) else testo).append(t)
    if not note:
        return '\n'.join(testo), ''
    return '\n'.join(testo), '\n'.join(note)


def _norm(t):
    return re.sub(r'[^a-z0-9]+', '', t.lower())


def posizione(pdf, npag, ago: str):
    """corpo | nota | non_determinabile.

    `ago` e' un pezzo del testo dell'occorrenza: si guarda in quale dei due
    blocchi della pagina cade."""
    out = _pagine_note(pdf, npag)
    if out is None:
        return 'non_determinabile', 'bassa'
    corpo_t, note_t = out
    if not note_t:
        return 'corpo', 'alta'
    a = _norm(ago)[:70]
    if len(a) < 24:
        return 'non_determinabile', 'bassa'
    in_note = a in _norm(note_t)
    in_corpo = a in _norm(corpo_t)
    if in_note and not in_corpo:
        return 'nota', 'alta'
    if in_corpo and not in_note:
        return 'corpo', 'alta'
    return 'non_determinabile', 'bassa'


def chiudi_pdf():
    for d in _PDF_APERTI.values():
        if d:
            try:
                d.close()
            except Exception:
                pass
    _PDF_APERTI.clear()


# ── Dimensione: sede del passaggio ──────────────────────────────────────

DISSENSO = re.compile(
    r'\b(?:dissenting|dissent(?:s|ed)?|in dissent|'
    r'opini[oó]n disidente|voto (?:particular|disidente|razonado)|'
    r'opinion dissidente|abweichende meinung|sondervotum|'
    r'opinione dissenziente|dissenso)\b', re.I)
CONCORRENTE = re.compile(
    r'\b(?:concurring|concurrence|opini[oó]n concurrente|'
    r'opinion concordante|opinione concorrente)\b', re.I)


def dimensioni(meta, pagina: str, off_in_pagina: int, prima: str):
    """Le proposte per un'occorrenza. Non decide: propone.

    `pagina`  il testo dell'intera pagina in cui cade l'occorrenza
    `off_in_pagina`  dove cade, dentro quel testo
    `prima`   il testo che precede l'occorrenza nel documento (contesto
              lungo, per le intestazioni di sezione e le opinioni separate)
    """
    tipo = (meta.get('tipo_atto') or '').strip().lower()
    base = DA_TIPO_ATTO.get(tipo, 'non_determinabile')

    # SEDE ---------------------------------------------------------------
    # Si guarda vicino: la formula che attribuisce l'argomento a una parte
    # sta nella stessa frase o in quella prima, non tre pagine sopra.
    vicino = pagina[max(0, off_in_pagina - 420):off_in_pagina + 120]
    coda = prima[-9000:]

    sede, conf_sede = 'motivazione', 'bassa'
    if base == 'corte':
        if any(p.search(vicino) for p in INDIZI_DIFESA):
            sede, conf_sede = 'difese_riportate', 'alta'
        else:
            # L'intestazione di sezione vale fino alla successiva: si
            # guarda quale delle due e' piu' vicina all'occorrenza.
            ints = list(INTESTAZIONI_DIFESE.finditer(coda))
            if ints:
                dopo = coda[ints[-1].end():]
                # Se dopo l'intestazione ricompare una sezione di
                # motivazione, l'indizio e' scaduto.
                if not re.search(r'^\s*(?:[IVXLC]+\.?\s*|\d+[\.\)]\s*)?'
                                 r'(?:reasons|analysis|discussion|findings|'
                                 r'the court[’\']?s assessment|motivazione|'
                                 r'considerato in diritto|fundamentos|'
                                 r'motifs|entscheidungsgr[uü]nde|beoordeling)'
                                 r'\s*:?\s*$', dopo, re.I | re.M):
                    sede, conf_sede = 'difese_riportate', 'media'
            if sede == 'motivazione':
                conf_sede = 'media'
        if DISSENSO.search(coda[-4000:]):
            sede, conf_sede = 'dissenso', 'media'
        elif CONCORRENTE.search(coda[-4000:]):
            sede, conf_sede = 'concorrente', 'media'
    elif base in ('parte', 'amicus'):
        # In un atto di parte non esiste una "motivazione": il documento e'
        # per intero l'argomento di chi lo deposita.
        sede, conf_sede = 'atto_di_parte', 'alta'
    else:
        # Lettere, avvisi, relazioni, comunicati: non hanno una struttura
        # processuale da cui dedurre la sede. Dirlo e' piu' utile che
        # inventare una categoria.
        sede, conf_sede = 'non_determinabile', 'bassa'

    # CHI CITA -----------------------------------------------------------
    # Se la corte sta riportando una difesa, chi cita e' la parte — ed e'
    # la correzione che vale di piu', perche' altrimenti ogni riassunto di
    # difesa verrebbe contato come citazione della corte.
    chi = base
    conf_chi = 'alta' if base != 'non_determinabile' else 'bassa'
    if base == 'corte' and sede == 'difese_riportate':
        chi = 'parte'
        conf_chi = conf_sede

    conf = min((conf_chi, conf_sede),
               key=lambda c: {'alta': 2, 'media': 1, 'bassa': 0}[c])
    return {
        'chi_cita_auto': chi,
        'sede_auto': sede,
        'dimensioni_confidenza': conf,
    }
