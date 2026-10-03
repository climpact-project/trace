#!/usr/bin/env python3
"""LA RICERCA PER NOME S05 (02/10/2026): `cerca.py` (S03) piu' la normalizzazione del testo.

    python tools/cerca_s05.py --caso cited-cases/urgenda-S05.yaml --solo-lessicale --uscita index/nomi_urgenda_2026-10-02-S05.csv

COPIA DI `cerca.py`, che resta com'era: la ricerca in uso in piattaforma e' S03 finche' il PI non decide il cambio.
Cambia SOLO la rete lessicale (le funzioni `forma_regex`, `e_nome`, `leggi_caso` e la colonna `forma_trovata`); la
rete semantica, l'unione, il filtro della data, la deduplica e il resto sono le righe di `cerca.py`, identiche.

PERCHE'. La misura del 2/10/2026 (training/misure/PERDITE-RICERCA-NOME.md, punto 2) ha trovato pagine che citano il
caso con una forma dichiarata, ma spezzata: «Klimabe-\nschluss», «Klimaseni-\norinnen», «Future Generations v. Ministry
of the\nEnvironment», «AO‑32/25» col trattino tipografico. Lette 50 pagine, 48 vere. `cerca.py` non passava da
`textnorm`: le forme latine si cercavano carattere per carattere.

COME, senza cambiare le posizioni. `textnorm.normalize` accorcia il testo (toglie la sillabazione), quindi le posizioni
nel testo normalizzato non sono quelle del file, e la posizione fa parte dell'identificativo della riga. Qui si fa il
contrario: si lascia il testo com'e' e si rende tollerante l'espressione regolare di ogni forma, con le stesse regole di
`textnorm.normalize`:
  - fra due lettere della stessa parola si ammette la sillabazione di fine riga (trattino, trattino morbido o trattino
    unificatore, poi l'a capo: «Klimabe-\nschluss») e i caratteri invisibili (spazio a larghezza zero, trattino morbido);
  - dove la forma ha uno spazio si ammette qualunque spazio, anche piu' d'uno, anche l'a capo e lo spazio unificatore;
  - un trattino della forma vale per ogni trattino o lineetta (‐ ‑ ‒ – — ― −), anche seguito da un a capo;
  - apostrofi e virgolette curve valgono come quelle dritte; una lettera accentata vale anche scomposta (NFD).
La corrispondenza si trova sul testo ORIGINALE, quindi `char_start` e' la posizione nel file come in S03: le righe
gia' in piattaforma si ritrovano allo stesso identificativo (prova: tests/test_cerca_s05.py e la prova sui sei casi).
Le forme in giapponese, cinese e coreano restano come in S03 (spazio o a capo fra un carattere e l'altro).

FORME A PAROLA INTERA (campo `forme_parola_intera` del file del caso, nuovo in S05): le forme elencate li' valgono solo
se non sono attaccate ad altre lettere. Serve alle sigle: «VKS» (KlimaSeniorinnen negli atti inglesi) non deve
corrispondere dentro un'altra parola. Le forme restano tutte anche in `forme`, che gli altri strumenti leggono.

Per il resto vale la descrizione di `cerca.py`, qui sotto.

---------------------------------------------------------------------------------------------------------------------
LO STRUMENTO DI RICERCA — quello che usano i ricercatori.

    python tools/cerca.py --caso cited-cases/urgenda.yaml

Fa girare le DUE RETI sullo stesso caso citato, unisce i risultati e
produce il CSV dei candidati da leggere.

    rete lessicale   corrispondenza esatta ed ESAUSTIVA sulle forme
                     dichiarate. Non e' una graduatoria: restituisce TUTTE
                     le occorrenze. Se ne restituisse le prime cento e le
                     menzioni fossero duecento, cento andrebbero perdute
                     senza che nulla lo segnali.
    rete semantica   i passaggi vicini di significato alle semantic
                     queries, per trovare chi riprende il ragionamento
                     SENZA nominarlo. Qui la graduatoria serve.

PERCHE' RESIDENTE. Con `--interattivo` il modello resta caricato e le
domande successive costano due secondi invece di trenta. Se ogni ricerca
avviasse un processo nuovo si pagherebbe il caricamento ogni volta, e lo
strumento verrebbe abbandonato dopo tre giorni.

I PREFISSI SI LEGGONO DAL MANIFESTO, MAI RISCRITTI A MANO. `e5` e'
asimmetrico: i passaggi vanno marcati `passage: `, le domande `query: `.
Se l'indice e' costruito con l'uno e le domande poste senza l'altro, non
si rompe niente — si ottengono risultati plausibili e sbagliati, per
sempre. Il manifesto li registra proprio perche' questo non accada.

LA FINESTRA DI LETTURA E' LA PAGINA, non un numero di caratteri. Negli
atti giuridici la citazione che stabilisce a chi si attribuisce un
principio puo' stare in una nota in fondo alla pagina, lontana dalla frase
che sostiene. Con una finestra di seicento caratteri quella nota resta
fuori, e chi legge non puo' applicare la regola "una paternita' dichiarata
esclude" — classificando come richiamo implicito un passaggio che cita
apertamente qualcun altro.
"""

import argparse
import csv
import datetime
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import textnorm  # noqa: E402  le regole di normalizzazione del corpus (S05)
MD = HERE / 'markdown'
INDEX = HERE / 'index'
PAGE_RE = re.compile(r'<!--\s*page\s+(\d+)\s*-->')

# Quanto contesto attorno all'occorrenza finisce nella colonna verbatim.
# La finestra di LETTURA e' un'altra cosa ed e' piu' ampia: vedi sopra.
PRIMA, DOPO = 200, 260


from dimensioni import (dimensioni as calcola_dimensioni,
                        posizione as posizione_pdf, chiudi_pdf)

# ── Il caso citato ──────────────────────────────────────────────────────

def _uno_spazio(v):
    """Un blocco YAML su piu' righe arriva con gli a-capo dentro: la sonda
    e' UNA frase, non un paragrafo, e gli a-capo non devono finire nel
    vettore."""
    return re.sub(r'\s+', ' ', str(v or '')).strip()


def leggi_caso(percorso: Path, con_alternative=False):
    """La query specification: lexical variants e semantic queries.

    LETTORE YAML VERO, dal 3 settembre 2026. Prima era un lettore minimo
    scritto a mano, per non aggiungere una dipendenza a quattro macchine.
    Quel motivo non c'e' piu' (PyYAML risulta gia' installato), e il
    lettore a mano aveva un difetto che il file ricco del postdoc ha reso
    visibile: la regola era «ogni riga rientrata di sei spazi appartiene
    alla sonda che sto leggendo». Su un file che accanto alla sonda mette
    anche `canonical`, `seeds`, `probe_alternativa`, `lexical_markers` e
    le loro annotazioni, quella regola incolla tutto: misurato il
    2026-09-03 sul file `urgenda.yaml` v2, le cinque sonde da 33-35 parole
    diventavano da 563 a 961 parole, oltre la finestra di 512 token del
    modello, quindi anche troncate a meta' senza alcun segnale. Guasto del
    tipo peggiore: nessun errore, solo risultati plausibili e sbagliati.

    LEGGE SOLO CIO' CHE DICHIARA, e tiene ogni campo separato. Il vettore
    della sonda si costruisce esclusivamente da `testo` (§14: una
    proposizione per sonda). Gli altri campi del file ricco — `canonical`,
    `seeds`, `lexical_markers`, le `ragione` delle esclusioni — NON sono
    materiale per l'embedding, che comprime in un punto e non legge:
    sono materiale per il ricercatore, per l'appendice dell'articolo e per
    l'adjudicazione con LLM (guida §45.1), che invece legge.

    `con_alternative` aggiunge `probe_alternativa` come SONDA A SE',
    cioe' come ricerca separata i cui risultati si uniscono a quelli
    della sonda principale. Mai concatenata al `testo`: sommare i testi
    e' l'errore appena corretto; qui si sommano i risultati. Misurato il
    2026-09-03 sulle cinque sonde di Urgenda: sovrapposizione fra le due
    formulazioni dal 20% al 36%, unione da +64% a +80% di candidati."""
    import yaml
    dati = yaml.safe_load(percorso.read_text(encoding='utf-8')) or {}
    conf = {'forme': [], 'sonde': [], 'escluse': []}

    # PyYAML riconosce le date e restituisce un `datetime.date`, dove il
    # lettore a mano restituiva sempre testo. Il resto della pipeline tratta
    # `data_decisione` come stringa (`.strip()[:10]`, §19), quindi si
    # normalizza qui: un tipo diverso in ingresso non deve propagarsi.
    for chiave in ('nome', 'codebook_versione', 'data_decisione',
                   'escludi_case_id', 'case', 'versione_file', 'filtro_data_documento'):
        if chiave in dati and dati[chiave] is not None:
            v = dati[chiave]
            if isinstance(v, (datetime.date, datetime.datetime)):
                v = v.isoformat()[:10]
            elif not isinstance(v, (list, tuple)):
                v = str(v)
            conf[chiave] = v

    conf['forme'] = [str(f).strip() for f in (dati.get('forme') or []) if str(f).strip()]
    # S05: le forme che valgono solo a parola intera (sigle come «VKS»). Stanno anche in `forme`.
    conf['forme_parola_intera'] = [str(f).strip() for f in (dati.get('forme_parola_intera') or []) if str(f).strip()]

    for s in (dati.get('semantic_queries') or []):
        if not isinstance(s, dict) or not _uno_spazio(s.get('testo')):
            continue
        sid = str(s.get('id') or '').strip()
        titolo = _uno_spazio(s.get('titolo'))
        conf['sonde'].append({'id': sid, 'titolo': titolo,
                              'testo': _uno_spazio(s.get('testo'))})
        alt = _uno_spazio(s.get('probe_alternativa'))
        if con_alternative and alt:
            # Id proprio, cosi' nel CSV si vede QUALE formulazione ha
            # pescato la riga: e' il dato che serve per decidere se la
            # seconda formulazione paga.
            conf['sonde'].append({'id': f'{sid}__alt', 'titolo': f'{titolo} [2a formulazione]',
                                  'testo': alt})

    for e in (dati.get('formulazioni_escluse') or []):
        if not isinstance(e, dict) or not _uno_spazio(e.get('testo')):
            continue
        conf['escluse'].append({'per': str(e.get('per') or '').strip(),
                                'id': str(e.get('id') or '').strip(),
                                'testo': _uno_spazio(e.get('testo'))})
        # L'esclusa vale anche per la seconda formulazione della stessa
        # proposizione: e' la stessa proposizione, quindi gli stessi vicini.
        if con_alternative:
            conf['escluse'].append({'per': f"{str(e.get('per') or '').strip()}__alt",
                                    'id': str(e.get('id') or '').strip(),
                                    'testo': _uno_spazio(e.get('testo'))})
    return conf


# ── Il documento ────────────────────────────────────────────────────────

def front_matter(testo: str):
    meta, fine = {}, testo.find('\n---\n', 4)
    if fine < 0:
        return meta, 0
    for riga in testo[4:fine].split('\n'):
        m = re.match(r'^([a-z_0-9]+):\s*(.*)$', riga)
        if m:
            v = m.group(2).strip()
            if v.startswith("'") and v.endswith("'") and len(v) >= 2:
                v = v[1:-1].replace("''", "'")
            meta[m.group(1)] = v
    return meta, fine + 5


def pagine(testo: str):
    return [(m.start(), int(m.group(1))) for m in PAGE_RE.finditer(testo)]


def pagina_di(marks, off):
    p = 1
    for pos, n in marks:
        if pos <= off:
            p = n
        else:
            break
    return p


def blocco_pagina(testo: str, marks, off: int):
    """(testo grezzo della pagina, offset dell'occorrenza dentro di esso).

    Grezzo, cioe' senza togliere il marcatore ne' ripulire gli spazi: qui
    servono le POSIZIONI, e ogni sostituzione le sposterebbe. La versione
    ripulita, quella che finisce nel CSV, la fa `finestra_pagina`."""
    inizio, fine = 0, len(testo)
    for i, (pos, _) in enumerate(marks):
        if pos <= off:
            inizio = pos
            fine = marks[i + 1][0] if i + 1 < len(marks) else len(testo)
        else:
            break
    return testo[inizio:fine], off - inizio


def finestra_pagina(testo: str, marks, off: int):
    """Il testo della pagina in cui cade l'occorrenza, note comprese."""
    return PAGE_RE.sub(' ', blocco_pagina(testo, marks, off)[0]).strip()


# ── Rete lessicale ──────────────────────────────────────────────────────

FUSIONE = 200   # corrispondenze piu' vicine di cosi' sono UNA citazione


def e_nome(testo, m):
    """La corrispondenza nomina il caso (e non e' solo un suo identificativo)?

    Identificativi: numeri di ruolo e ECLI («19/00135», «C/09/456689», «1 BvR 2656/18», «ECLI:NL:HR:2019:2007») e il
    nome dentro un indirizzo web («www.urgenda.nl/...»). Nome: tutto il resto, comprese le scritture non latine."""
    # S05: la decisione si prende sulla forma normalizzata, cosi' una corrispondenza spezzata («Klimabe-\\nschluss») o
    # col trattino tipografico («AO‑32/25») e' nome o identificativo come la sua forma scritta per intero. Sulle
    # corrispondenze di S03 (forme esatte) la normalizzazione non cambia niente: stesso esito.
    s = forma_normalizzata(m.group(0))
    if re.search(r'[^\x00-\x7f]', s):
        return True
    if not re.search(r'[a-z]{3}', s):
        return False
    prima = testo[max(0, m.start() - 60):m.start()]
    coda = re.search(r'\S*$', prima).group(0)
    return not ('/' in coda or 'www' in coda.lower() or 'http' in coda.lower())


def fondi(testo, grezze):
    """UNA CITAZIONE, UNA RIGA. Due regole.

    1. Corrispondenze a meno di 200 caratteri dall'inizio del gruppo sono una citazione (la regola di sempre).
    2. Dal 29/9/2026: un IDENTIFICATIVO a meno di 200 caratteri dalla corrispondenza precedente continua la stessa
       citazione. Prima un riferimento lungo («Urgenda c. Pays-Bas, C/09/456689 / HA ZA 13-1396 ; Cour d'appel...
       200.178.245/01 ; Hoge Raad... 19/00135») superava i 200 caratteri e il numero di ruolo in fondo diventava una
       riga a se': in piattaforma 3 casi su Urgenda e decine su Neubauer (la catena «1 BvR 2656/18, 1 BvR 78/20...»).
       Il NOME invece apre sempre una citazione nuova oltre i 200 caratteri: note consecutive («324 Urgenda..., para.
       5.7.5. 325 Urgenda..., paras. 5.7.5-5.7.6») sono citazioni distinte, di paragrafi diversi. Una regola che
       fondeva tutto a catena e' stata provata e scartata lo stesso giorno per questo."""
    fuse, fine = [], None
    for m in grezze:
        if fuse and (m.start() - fuse[-1][0].start() < FUSIONE
                     or (m.start() - fine < FUSIONE and not e_nome(testo, m))):
            fuse[-1][1].append(m.group(0))
            fuse[-1][2] = m.start()
        else:
            fuse.append([m, [m.group(0)], m.start()])
        fine = m.end()
    return fuse


CJK = re.compile(r'[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\uf900-\ufaff]')


def forma_regex(f):
    """La forma come espressione regolare. Per le forme in giapponese, cinese e coreano si ammette uno spazio o un a capo
    fra un carattere e l'altro: in quei testi l'a capo cade anche dentro una parola («ノイバウ\\nアー», atto giapponese
    climate-justice-case-complaint_58b2 p. 115, trovato l'1/10/2026).

    S05: anche le forme in alfabeto latino diventano tolleranti, con le regole di `textnorm.normalize` (vedi in testa).
    Le posizioni restano quelle del testo originale."""
    if CJK.search(f):
        return r'\s*'.join(re.escape(c) for c in f if not c.isspace())
    f = unicodedata.normalize('NFC', f)
    out, prec = [], ''
    for c in f:
        if c.isspace():
            if prec != ' ':
                out.append(SPAZIO)
            prec = ' '
            continue
        if prec.isalpha() and c.isalpha():
            out.append(DENTRO_PAROLA)
        if c in TRATTINI:
            out.append(TRATTINO)
        elif c in APOSTROFI:
            out.append(APOSTROFO)
        elif c in VIRGOLETTE:
            out.append(VIRGOLETTA)
        else:
            scomposta = unicodedata.normalize('NFD', c)
            out.append(re.escape(c) if scomposta == c else f'(?:{re.escape(c)}|{re.escape(scomposta)})')
        prec = c
    return ''.join(out)


# Le regole di `textnorm` scritte come pezzi di espressione regolare (S05).
INVISIBILI = '­​‌‍﻿'                       # trattino morbido, spazi a larghezza zero
SILLABAZIONE = '-‐‑­'                                # trattini con cui si va a capo dentro una parola
TRATTINI = '-‐‑‒–—―−'
APOSTROFI = "'‘’‚‛′ʼ`´"
VIRGOLETTE = '"“”„‟″«»'
DENTRO_PAROLA = f'(?:[{SILLABAZIONE}][ \\t]*\\r?\\n\\s*|[{INVISIBILI}])?'
SPAZIO = f'[\\s{INVISIBILI}]+'
TRATTINO = f'[{re.escape(TRATTINI)}](?:[ \\t]*\\r?\\n\\s*)?'
APOSTROFO = f'[{re.escape(APOSTROFI)}]'
VIRGOLETTA = f'[{re.escape(VIRGOLETTE)}]'
LETTERA_ACCANTO = r'[^\W\d_]'


def forma_normalizzata(s):
    """La corrispondenza come la si legge: sillabazione tolta, spazi e trattini unificati (per `forma_trovata` e per
    `e_nome`). Su una forma esatta di S03 restituisce la stessa stringa."""
    t = textnorm.normalize(s)
    t = t.replace('­', '')
    t = re.sub(f'[{INVISIBILI}]', '', t)
    return re.sub(r'\s+', ' ', t)


def regex_caso(conf):
    """L'espressione unica della rete lessicale di un caso, nell'ordine delle forme del file (come S03)."""
    intere = set(conf.get('forme_parola_intera') or [])
    pezzi = []
    for f in conf['forme']:
        r = forma_regex(f)
        if f in intere:
            r = f'(?<!{LETTERA_ACCANTO})(?:{r})(?!{LETTERA_ACCANTO})'
        pezzi.append(r)
    return re.compile('|'.join(pezzi), re.I)


def data_documento(meta):
    """AAAA-MM-GG dal nome del file d'origine («.../2024/20240417_...»), altrimenti stringa vuota."""
    m = re.search(r'/(\d{4})(\d{2})(\d{2})_', str(meta.get('url_origine') or ''))
    return f'{m.group(1)}-{m.group(2)}-{m.group(3)}' if m else ''


def regex_ancora(forme):
    """L'espressione ESATTA di S03 (`cerca.forma_regex`) sulle forme della ricerca precedente."""
    import cerca as S03
    return re.compile('|'.join(S03.forma_regex(f) for f in forme), re.I)


def corrispondenze(testo, inizio, patt, ancora=None):
    """Le corrispondenze del nome in un testo, in ordine.

    LE CORRISPONDENZE DI S03 RESTANO QUELLE (S05). Con `ancora` (l'espressione esatta della ricerca precedente) si
    tengono TUTTE le sue corrispondenze, identiche per inizio e fine, e delle nuove solo quelle che non si
    sovrappongono a nessuna di esse. Senza questa regola una forma nuova piu' lunga potrebbe cominciare prima di una
    corrispondenza di S03 e inghiottirla («ICJ in its Advisory Opinion of 23 July 2025»: la forma nuova parte da
    «ICJ», quella di S03 da «Advisory»): la riga gia' in piattaforma non si ritroverebbe e ne nascerebbe una doppia.
    Se l'espressione tollerante non trova niente non trova niente nemmeno quella esatta (ogni forma esatta e' un caso
    della sua forma tollerante): il secondo passaggio si fa solo sui file con almeno una corrispondenza."""
    nuove = list(patt.finditer(testo, inizio))
    if not nuove or ancora is None:
        return nuove
    vecchie = list(ancora.finditer(testo, inizio))
    if not vecchie:
        return nuove
    import bisect
    inizi = [m.start() for m in vecchie]
    tenute = []
    for m in nuove:
        k = bisect.bisect_right(inizi, m.start()) - 1
        sovrapposta = ((k >= 0 and vecchie[k].end() > m.start())
                       or (k + 1 < len(vecchie) and vecchie[k + 1].start() < m.end()))
        if not sovrapposta:
            tenute.append(m)
    return sorted(vecchie + tenute, key=lambda m: m.start())


def rete_lessicale(forme, escludi='', tipi=None, intere=(), forme_ancora=None, file=None):
    """Ogni occorrenza, in ogni documento. Esaustiva per costruzione.

    Le corrispondenze ravvicinate si FONDONO: un atto scrive spesso
    "il tribunale (ECLI:..., causa C/09/...) nel caso Urgenda" — una
    citazione, tre corrispondenze. Contarle separatamente gonfia il dato,
    e non in modo uniforme: gonfia di piu' gli atti che citano per esteso,
    cioe' quelli che danno peso al precedente.

    S05: `forme_ancora` sono le forme della ricerca precedente (S03), le cui corrispondenze restano identiche (vedi
    `corrispondenze`); `file` limita la ricerca a un elenco di Markdown (per le prove)."""
    patt = regex_caso({'forme': forme, 'forme_parola_intera': list(intere)})
    ancora = regex_ancora(forme_ancora) if forme_ancora else None
    # `escludi_case_id` era uno scalare nel file del pilota ed e' una LISTA
    # nel file v2 (un giudizio puo' essere spezzato in piu' case_id, come
    # Juliana). Si accettano tutti e due, altrimenti il file nuovo passerebbe
    # una lista a `.lower()` e la ricerca morirebbe — o peggio, con un `in`
    # su lista, escluderebbe in silenzio la cosa sbagliata.
    esclusi = [escludi] if isinstance(escludi, str) else list(escludi or [])
    esclusi = [str(x).lower() for x in esclusi if str(x).strip()]
    fuori = []
    for md in (sorted(MD.rglob('*.md')) if file is None else [Path(x) if Path(x).is_absolute() else HERE / x for x in file]):
        testo = md.read_text(encoding='utf-8', errors='replace')
        meta, inizio = front_matter(testo)
        cid = (meta.get('case_id') or '').lower()
        if any(x in cid for x in esclusi):
            continue
        if tipi and (meta.get('tipo_atto') or '').strip().lower() not in tipi:
            continue
        grezze = corrispondenze(testo, inizio, patt, ancora)
        if not grezze:
            continue
        marks = pagine(testo)
        fuse = fondi(testo, grezze)
        for m, forme_qui, _ in fuse:
            blocco, off_rel = blocco_pagina(testo, marks, m.start())
            fuori.append({
                'dim': calcola_dimensioni(meta, blocco, off_rel, testo[:m.start()]),
                'meta': meta, 'file': str(md.relative_to(HERE)),
                'char_start': m.start(),
                'pagina': pagina_di(marks, m.start()),
                'forma': ' + '.join(dict.fromkeys(forma_normalizzata(x) for x in forme_qui)),
                'verbatim': re.sub(r'\s+', ' ', PAGE_RE.sub(
                    ' ', testo[max(inizio, m.start() - PRIMA):m.start() + DOPO])).strip(),
                'finestra': finestra_pagina(testo, marks, m.start()),
                'rete': 'lessicale', 'punteggio': '',
            })
    return fuori


def file_ancora(percorso):
    """Il file del caso della ricerca precedente (S03), le cui corrispondenze restano identiche.

    Prima `cited-cases/ancora-S03/<caso>.yaml`: la copia esatta del file vivo di S03 fatta il 02/10/2026, che resta
    giusta anche dopo che il file S05 avra' preso il posto del file vivo (allora `cited-cases/<caso>.yaml` sarebbe S05,
    e una forma nuova potrebbe di nuovo coprire una corrispondenza di S03). Se manca, `cited-cases/<caso>.yaml`."""
    p = Path(percorso)
    base = re.sub(r'-S\d\d$', '', p.stem)
    copia = p.parent / 'ancora-S03' / (base + '.yaml')
    return copia if copia.exists() else p.with_name(base + '.yaml')


# ── Rete semantica ──────────────────────────────────────────────────────

class Semantica:
    """Tiene il modello e l'indice in memoria fra una domanda e l'altra."""

    def __init__(self):
        man = json.loads((INDEX / 'manifesto.json').read_text(encoding='utf-8'))
        self.man = man
        self.pre_q = man.get('prefisso_domanda', '')
        print(f"  indice   : {man['frammenti']:,} frammenti, {man['modello']}", flush=True)
        print(f"  costruito: {man['costruito']}", flush=True)
        t0 = time.time()
        self.V = np.load(INDEX / 'vettori.npy', mmap_mode='r')
        self.ids = json.loads((INDEX / 'ids.json').read_text(encoding='utf-8'))
        from sentence_transformers import SentenceTransformer
        import torch
        dev = ('cuda' if torch.cuda.is_available()
               else 'mps' if torch.backends.mps.is_available() else 'cpu')
        self.m = SentenceTransformer(man['modello'], device=dev)
        self.m.max_seq_length = man.get('max_token', 512)
        print(f'  caricato in {time.time() - t0:.0f}s su {dev}', flush=True)
        # I frammenti servono per risalire a documento e pagina.
        self.fr = {}
        with (INDEX / 'chunks.jsonl').open(encoding='utf-8') as f:
            for riga in f:
                d = json.loads(riga)
                self.fr[d['id']] = d

    def cerca(self, sonde, k=100, escluse=()):
        """I candidati, e quanto ciascuno somiglia a cio' che NON conta.

        LE FORMULAZIONI ESCLUSE non filtrano, misurano. Per ogni sonda si
        dichiarano una o piu' formulazioni che le somigliano ma dicono
        altro — il dovere di diligenza civilistico ordinario, per esempio,
        che compare in mille sentenze senza avere nulla a che fare con il
        caso citato. Ogni candidato porta allora due punteggi e la loro
        differenza.

        NON SI SCARTA NIENTE AUTOMATICAMENTE. Un candidato piu' vicino a
        una formulazione esclusa che alla sonda esce lo stesso, con
        `margine` negativo e `sospetto` valorizzato: sono le righe da
        leggere per prime. Scartarle in silenzio nasconderebbe proprio i
        casi in cui la sonda e' scritta male — che e' l informazione che
        serve per riscriverla."""
        Q = self.m.encode([self.pre_q + s['testo'] for s in sonde],
                          normalize_embeddings=True, convert_to_numpy=True,
                          show_progress_bar=False).astype(np.float16)
        per_sonda = {}
        if escluse:
            E = self.m.encode([self.pre_q + e['testo'] for e in escluse],
                              normalize_embeddings=True, convert_to_numpy=True,
                              show_progress_bar=False).astype(np.float16)
            for i, e in enumerate(escluse):
                per_sonda.setdefault(e['per'], []).append((e, E[i]))
        fuori = []
        for i, s in enumerate(sonde):
            punt = self.V @ Q[i]
            mie = per_sonda.get(s['id'], [])
            for j in np.argsort(-punt)[:k]:
                d = self.fr.get(self.ids[j])
                if not d:
                    continue
                p_escl, quale = 0.0, ''
                for e, vec in mie:
                    v = float(self.V[j] @ vec)
                    if v > p_escl:
                        p_escl, quale = v, e['id'] or e['per']
                r = {'frammento': d, 'sonda': s['titolo'] or s['id'],
                     'punteggio': round(float(punt[j]), 4)}
                if mie:
                    r['punteggio_escluse'] = round(p_escl, 4)
                    r['margine'] = round(float(punt[j]) - p_escl, 4)
                    r['sospetto'] = (f'piu vicino a: {quale}'
                                     if r['margine'] <= 0 else '')
                fuori.append(r)
        return fuori


# ── Il riordinatore ─────────────────────────────────────────────────────

class Riordinatore:
    """LEGGE LA SONDA E IL PASSAGGIO INSIEME, e dice se quel passaggio
    AFFERMA quella proposizione.

    PERCHE' SERVE. La rete semantica comprime ogni testo in un punto solo, e
    quel punto cattura DI COSA SI PARLA. Non ha dove mettere la struttura
    della proposizione: chi e' il soggetto, se c'e' un obbligo o una
    constatazione, se la frase afferma o nega. Percio' "la quota cinese e'
    l'11,6% delle emissioni globali" e "ogni Stato risponde della propria
    quota e non puo' sottrarsi" finiscono vicini: parlano della stessa cosa.
    Una e' una statistica, l'altra una norma, e il vettore non lo distingue.

    Questo modello e' fatto in modo diverso: non produce due punti da
    confrontare, mette i due testi UNO ACCANTO ALL'ALTRO e li legge insieme.
    E' l'unico della famiglia che vede la struttura della frase.

    MISURATO sul caso che aveva insospettito il PI, sonda `propria_quota`:

        0,9504  la norma  ("ogni Stato risponde della propria quota…")
        0,7308  responsabilita comuni ma differenziate (formulazione esclusa)
        0,0833  la statistica cinese sulle quote di emissione
        0,0086  il regolamento EPA ripetuto sessanta volte

    La statistica e il rumore crollano di un ordine di grandezza. La
    formulazione esclusa NO — resta alta, ed e' corretto che sia cosi':
    e' davvero una proposizione vicina. A quella pensa il confronto con le
    formulazioni escluse, non il riordinatore.

    NON SERVE UNA GPU E NON SERVE UN INDICE NUOVO: guarda solo le poche
    centinaia di candidati che la rete semantica ha gia' tirato su, non i
    1,2 milioni di frammenti. Mezzo secondo per quattro coppie su un
    portatile."""

    MODELLO = 'BAAI/bge-reranker-v2-m3'

    def __init__(self):
        from sentence_transformers import CrossEncoder
        t0 = time.time()
        self.m = CrossEncoder(self.MODELLO, max_length=1024)
        print(f'  riordinatore caricato in {time.time() - t0:.0f}s', flush=True)

    def punteggi(self, coppie):
        import numpy as _np
        if not coppie:
            return []
        out = self.m.predict(coppie, show_progress_bar=False)
        return [float(x) for x in _np.asarray(out).reshape(-1)]


# ── La confidenza sulla proposta semantica ────────────────────────────
#
# Il piano la mette nello stesso gruppo di `punteggio embedding, punteggio
# reranker`: e' una proposta della macchina, non un'autovalutazione di chi
# legge. Fino ad ora restava vuota — vedi METODO-RECUPERO per la storia —
# e il codebook la trattava come un giudizio umano ("se sei incerto,
# confidenza: bassa"), cosa che il piano non prevedeva. Le due cose non
# possono coesistere sullo stesso campo: o lo scrive la macchina dal suo
# punteggio, o lo scrive la persona come autovalutazione. Qui si sceglie
# la prima, perche' e' quella scritta nel piano.
#
# Le soglie non sono a caso: misurate sui 216 candidati semantici della
# run Urgenda (`punteggio_riordino`, la stessa colonna che il riordinatore
# scrive qui sotto). Il minimo osservato e' 0,051 — un pelo sopra la soglia
# di scarto (0,05): sotto quella soglia il candidato non arriva nemmeno a
# questa riga. La mediana e' 0,40, il 75-esimo percentile 0,65. Le soglie
# 0,2 e 0,6 dividono l'insieme in tre gruppi di dimensione paragonabile,
# invece di lasciarne uno vuoto e uno enorme.
def confidenza_da_riordino(v):
    if v is None or v == '':
        return ''
    try:
        v = float(v)
    except (TypeError, ValueError):
        return ''
    if v >= 0.6:
        return 'alta'
    if v >= 0.2:
        return 'media'
    return 'bassa'


# ── Unione e uscita ─────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    # IL NOME BASTA. `--caso urgenda` invece del percorso intero: chi lo
    # usa dieci volte al mese non deve ricordarsi dove stanno i file.
    ap.add_argument('--caso', required=True,
                    help='nome del caso citato (es. urgenda) o percorso del file')
    # IL CODEBOOK NON SI PASSA: e' uno solo e vale per tutti i casi. Se si
    # potesse indicarne uno diverso a ogni ricerca, quattro persone
    # userebbero quattro criteri — che e' esattamente cio' che il codebook
    # esiste per impedire. Si sostituisce solo con una revisione.
    ap.add_argument('--uscita', default='')
    ap.add_argument('--k', type=int, default=100, help='candidati per semantic query')
    ap.add_argument('--solo-lessicale', action='store_true')
    ap.add_argument('--con-alternative', action='store_true',
                    help='usa anche `probe_alternativa` come sonda a se stante '
                         '(ricerca separata, risultati uniti). Misurato il '
                         '2026-09-03: +64-80%% di candidati, sovrapposizione 20-36%%.')
    # ISOLARE LE SOLE DECISIONI. Un caso invocato dai ricorrenti in
    # ventisette paesi e adottato da corti in sette non e' la stessa cosa,
    # e la differenza fra quei due numeri e' un risultato — non un
    # dettaglio. Il corpus contiene sia gli atti sia le decisioni: qui si
    # sceglie su cosa contare.
    ap.add_argument('--solo-decisioni', action='store_true',
                    help='solo decisioni e ordinanze: cio che le corti hanno adottato')
    ap.add_argument('--senza-riordino', action='store_true',
                    help='salta il riordinatore (piu veloce, molto piu rumore)')
    ap.add_argument('--soglia-riordino', type=float, default=0.05,
                    help='sotto questo punteggio il candidato semantico non entra')
    ap.add_argument('--con-anteriori', action='store_true',
                    help='tiene anche i documenti anteriori alla decisione citata')
    ap.add_argument('--ancora', default='',
                    help="S05: il file del caso della ricerca precedente, le cui corrispondenze restano identiche "
                         "(predefinito: cited-cases/<caso>.yaml per <caso>-S05.yaml; 'nessuna' per non usarla)")
    ap.add_argument('--tipo-atto', default='',
                    help="tipi di atto separati da virgola (es. 'atto introduttivo,replica')")
    args = ap.parse_args()

    # Il nome corto si risolve nella cartella dei casi citati.
    percorso = Path(args.caso)
    if not percorso.exists():
        percorso = HERE / 'cited-cases' / f'{args.caso}.yaml'
    if not percorso.exists():
        disponibili = sorted(p.stem for p in (HERE / 'cited-cases').glob('*.yaml'))
        print(f'Caso citato non trovato: {args.caso}')
        print(f'Disponibili: {", ".join(disponibili) or "nessuno"}')
        return 1
    conf = leggi_caso(percorso, con_alternative=args.con_alternative)

    tipi = None
    if args.solo_decisioni:
        tipi = {'decisione', 'ordinanza'}
    elif args.tipo_atto:
        tipi = {t.strip().lower() for t in args.tipo_atto.split(',') if t.strip()}

    # IL CODEBOOK VIAGGIA CON I PASSAGGI, non resta in un file che qualcuno
    # forse aprira'. Le sue istruzioni di lettura si scrivono accanto al
    # CSV: chi legge — persona o modello — le ha davanti insieme al testo
    # da classificare. E' la condizione perche' quattro persone applichino
    # lo stesso criterio anche lavorando in giorni diversi.
    cb_file = HERE / 'codebook' / 'citazioni.yaml'
    cb_testo = cb_file.read_text(encoding='utf-8') if cb_file.exists() else ''
    m = re.search(r'^versione:\s*(.+)$', cb_testo, re.M)
    cb_versione = m.group(1).strip() if m else 'assente'
    m = re.search(r'^approvato_da:\s*(.+)$', cb_testo, re.M)
    cb_approvato = (m.group(1).strip() if m else 'null')
    print(f'codebook    : {cb_versione}', end='')
    if cb_approvato in ('null', '', 'None'):
        print('   NON ANCORA APPROVATO — le codifiche prodotte ora non sono definitive')
    else:
        print(f'   approvato da {cb_approvato}')
    nome = conf.get('nome', Path(args.caso).stem)
    print(f'caso citato : {nome}')
    print(f'forme       : {len(conf["forme"])}')
    print(f'sonde       : {len(conf["sonde"])}')
    if tipi:
        print(f'FILTRO      : solo {", ".join(sorted(tipi))}')
    print(flush=True)

    print('rete lessicale (esaustiva)…', flush=True)
    t0 = time.time()
    fa = None
    if args.ancora != 'nessuna':
        pa = Path(args.ancora) if args.ancora else file_ancora(percorso)
        if pa.exists() and pa.resolve() != percorso.resolve():
            fa = leggi_caso(pa)['forme']
            print(f'ancora      : {pa.name} ({len(fa)} forme: le sue corrispondenze restano identiche)', flush=True)
    less = rete_lessicale(conf['forme'], conf.get('escludi_case_id', ''), tipi, conf.get('forme_parola_intera', ()), fa)
    print(f'  {len(less):,} occorrenze in {time.time() - t0:.0f}s\n', flush=True)

    sem = []
    if not args.solo_lessicale and conf['sonde']:
        print('rete semantica…', flush=True)
        S = Semantica()
        t0 = time.time()
        sem = S.cerca(conf['sonde'], k=args.k, escluse=conf.get('escluse', ()))
        print(f'  {len(sem):,} candidati in {time.time() - t0:.0f}s\n', flush=True)

    # UNIONE. Un passaggio trovato da entrambe le reti e' UNA riga, con
    # `rete = entrambe`: sapere da dove viene serve a stimare quanto del
    # risultato dipende da quale strumento.
    # SOVRAPPOSIZIONE VERA, NON BLOCCHI.
    #
    # Prima si raggruppava per `char_start // 400`: due citazioni distinte
    # che cadevano nello stesso blocco si fondevano, e due vicinissime a
    # cavallo di un confine restavano separate. La perdita non era
    # uniforme — dipendeva da dove cadeva la griglia — ed e' esattamente il
    # tipo di errore che non si vede guardando i risultati.
    # Qui un candidato semantico si unisce a un'occorrenza lessicale solo
    # se il suo FRAMMENTO la contiene davvero.
    per_file = {}
    for r in less:
        per_file.setdefault(r['file'], []).append(r)

    unite = list(less)
    for r in sem:
        d = r['frammento']
        a, b = d['char_start'], d.get('char_end', d['char_start'] + 1100)
        dentro = None
        for l in per_file.get(d['file'], []):
            if a <= l['char_start'] < b:
                dentro = l
                break
        if dentro is not None:
            dentro['rete'] = 'entrambe'
            if not dentro.get('punteggio'):
                dentro['punteggio'] = r['punteggio']
                dentro['sonda'] = r['sonda']
                for c in ('punteggio_escluse', 'margine', 'sospetto'):
                    if c in r:
                        dentro[c] = r[c]
            continue
        testo = (HERE / d['file']).read_text(encoding='utf-8', errors='replace')
        meta, _ = front_matter(testo)
        if tipi and (meta.get('tipo_atto') or '').strip().lower() not in tipi:
            continue
        marks = pagine(testo)
        blocco, off_rel = blocco_pagina(testo, marks, d['char_start'])
        unite.append({
            'dim': calcola_dimensioni(meta, blocco, off_rel, testo[:d['char_start']]),
            'meta': meta, 'file': d['file'], 'char_start': d['char_start'],
            'pagina': d.get('pagina', 1), 'forma': '',
            'verbatim': re.sub(r'\s+', ' ', d['testo'])[:460],
            # IL TESTO INTERO, PER CHI DEVE GIUDICARE E NON LEGGERE.
            # I 460 caratteri qui sopra sono una misura da COLONNA: servono
            # perche' `citazione_testuale` resti leggibile in un CSV e in una
            # tabella. Il riordinatore pero' non legge una colonna: valuta se
            # il passaggio risponde alla sonda, ed e' proprio il contesto la
            # cosa per cui e' stato introdotto (vedi 14.3). Alimentato con il
            # testo tagliato ne vedeva circa un terzo -- 460 caratteri sono
            # ~115 token contro i 1024 che dichiara di poter leggere.
            # Due campi invece di un compromesso: uno si legge, l'altro si
            # giudica.
            'verbatim_intero': re.sub(r'\s+', ' ', d['testo']),
            'finestra': finestra_pagina(testo, marks, d['char_start']),
            'rete': 'semantica', 'punteggio': r['punteggio'], 'sonda': r['sonda'],
            **{c: r[c] for c in ('punteggio_escluse', 'margine', 'sospetto')
               if c in r},
        })

    righe = []
    for r in unite:
        m = r['meta']
        righe.append({
            'case_id': m.get('case_id', ''), 'case_name': m.get('case_name', ''),
            'giurisdizioni': m.get('giurisdizioni', ''),
            'document_id': m.get('document_id', ''),
            'tipo_atto': m.get('tipo_atto', ''),
            'tipo_atto_sabin': m.get('tipo_atto_sabin', ''),
            'data': m.get('data_deposito', ''), 'pagina': r['pagina'],
            # LA DATA DEL DOCUMENTO (01/10/2026): `data_deposito` e' spesso la data d'inizio della causa; il file
            # d'origine del Climate Litigation Database comincia invece con la data di deposito dell'atto (AAAAMMGG_).
            'data_documento': data_documento(m),
            'rete': r['rete'], 'sonda': r.get('sonda', ''),
            'punteggio': r['punteggio'],
            'punteggio_riordino': '',
            'copie': '',
            'anteriore': '',
            'punteggio_escluse': r.get('punteggio_escluse', ''),
            'margine': r.get('margine', ''),
            'sospetto': r.get('sospetto', ''),
            'forma_trovata': r['forma'],
            'citazione_testuale': r['verbatim'],
            # Viaggia con la riga solo per arrivare al riordinatore, e viene
            # tolta prima di scrivere il CSV: non e' una colonna, e' materia
            # prima di un calcolo. Vedi la pulizia poco prima della scrittura.
            'verbatim_intero': r.get('verbatim_intero', ''),
            'finestra_pagina': r['finestra'],
            # PROPOSTE DELLA MACCHINA — non si modificano. Servono a
            # misurare il disaccordo con il lettore: se venissero
            # sovrascritte, quel dato sparirebbe.
            'chi_cita_auto': r['dim']['chi_cita_auto'],
            'posizione_auto': '',
            'sede_auto': r['dim']['sede_auto'],
            'dimensioni_confidenza': r['dim']['dimensioni_confidenza'],
            # DECISIONE DEL LETTORE — nascono gia' compilate con la
            # proposta, cosi' nel caso ordinario non c'e' nulla da
            # scrivere: si corregge solo dove la proposta e' sbagliata.
            'chi_parla': r['dim']['chi_cita_auto'],
            'posizione': '',
            'sede': r['dim']['sede_auto'],
            # Queste no: nessun segnale testuale le decide.
            'tipo_citazione': '', 'annidata': '',
            'proposizione_sostenuta': '', 'confidenza': '', 'note': '',
            'file': r['file'], 'char_start': r['char_start'],
            'url_documento': m.get('url_documento', ''),
            'codebook_versione': cb_versione,
        })
    # ── IL FILTRO TEMPORALE ─────────────────────────────────────────
    #
    # Un atto depositato PRIMA della decisione citata non puo' riprenderla.
    # E' una verita' di calendario, non una stima, ed e' il filtro piu'
    # forte che abbiamo: esatto, gratuito, e nessun modello lo puo' imitare.
    #
    # NON SI BUTTANO VIA. Un documento anteriore che esprime la stessa
    # proposizione non e' rumore: e' la prova che il principio esisteva gia'
    # prima, cioe' un argomento CONTRO la derivazione. Vanno letti a parte,
    # e con `--con-anteriori` restano nel CSV principale.
    # Le reti che hanno trovato il NOME del caso: occorrenze letterali, non ipotesi.
    NOMINALI = ('lessicale', 'entrambe')
    scarti = []
    anteriori = []
    dmin = (conf.get('data_decisione') or '').strip()[:10]
    if dmin and not args.con_anteriori:
        tenute = []
        for r in righe:
            d = (r.get('data') or '').strip()[:10]
            # Le righe col nome (lessicali ed «entrambe») non passano da qui: il
            # filtro e' delle ipotesi semantiche. Fino al 29/9/2026 guardava solo
            # `lessicale`, e le «entrambe» anteriori finivano negli scarti.
            if r['rete'] not in NOMINALI and d and d < dmin:
                r['anteriore'] = 'si'
                r['motivo_scarto'] = f'anteriore al {dmin}'
                anteriori.append(r)
                scarti.append(r)
            # PER I CASI CON `filtro_data_documento: true` (01/10/2026, il PI: KlimaSeniorinnen si cerca solo dopo la
            # pronuncia) anche le righe col nome: un atto depositato prima della decisione puo' nominare il ricorso
            # pendente o le decisioni interne, non la pronuncia. Vale la data del documento, non quella della causa.
            elif conf.get('filtro_data_documento') and r.get('data_documento') and r['data_documento'] < dmin:
                r['anteriore'] = 'si'
                r['motivo_scarto'] = f"documento del {r['data_documento']}, anteriore alla pronuncia del {dmin}"
                anteriori.append(r)
                scarti.append(r)
            else:
                tenute.append(r)
        righe = tenute

    # ── LA DEDUPLICA ────────────────────────────────────────────────
    #
    # Il 6% dei frammenti del corpus e' testo ripetuto: lo stesso atto
    # depositato piu' volte, gli stessi allegati. Misurato, il piu' ripetuto
    # compare SESSANTA volte. Presentarli come sessanta candidati distinti
    # gonfia il conteggio e costringe a leggere sessanta volte la stessa
    # pagina. Si tiene il primo e si registra quante copie aveva.
    visti, uniche = {}, []
    for r in righe:
        k = re.sub(r'\s+', ' ', r['citazione_testuale']).strip().lower()[:400]
        if k in visti:
            visti[k]['copie'] = int(visti[k].get('copie') or 1) + 1
            r['motivo_scarto'] = 'copia di un altro frammento'
            scarti.append(r)
            continue
        r['copie'] = 1
        visti[k] = r
        uniche.append(r)
    duplicati = len(righe) - len(uniche)
    righe = uniche

    # ── IL RIORDINO ─────────────────────────────────────────────────
    #
    # Solo sui candidati semantici: quelli lessicali sono occorrenze
    # letterali del nome, non ipotesi da vagliare.
    scartati_riordino = 0
    if not args.senza_riordino and any(r['rete'] != 'lessicale' for r in righe):
        print('\nriordino dei candidati semantici…', flush=True)
        testi_sonda = {(s.get('titolo') or s['id']): s['testo'] for s in conf['sonde']}
        da_riordinare = [r for r in righe if r['rete'] != 'lessicale' and r.get('sonda')]
        try:
            R = Riordinatore()
            t0 = time.time()
            # SI PASSA IL FRAMMENTO INTERO, non la colonna troncata: vedi il
            # commento su `verbatim_intero`. Il ripiego su
            # `citazione_testuale` copre le righe che non hanno il campo
            # (ad esempio prodotte da una versione precedente): meglio
            # riordinare su poco che non riordinare affatto.
            coppie = [[testi_sonda.get(r['sonda'], r['sonda']),
                       r.get('verbatim_intero') or r['citazione_testuale']]
                      for r in da_riordinare]
            for r, v in zip(da_riordinare, R.punteggi(coppie), strict=True):
                r['punteggio_riordino'] = round(v, 4)
                # Non si sovrascrive una confidenza gia' scritta a mano da
                # una revisione precedente: solo il campo ancora vuoto viene
                # proposto dalla macchina.
                if not r.get('confidenza'):
                    r['confidenza'] = confidenza_da_riordino(r['punteggio_riordino'])
            print(f'  {len(coppie):,} coppie in {time.time() - t0:.0f}s', flush=True)
            prima = len(righe)
            tenute = []
            for r in righe:
                # IL TAGLIO NON TOCCA MAI LE RIGHE COL NOME. Fino al 29/9/2026 la
                # condizione era `rete == 'lessicale'`: le righe trovate da
                # entrambe le reti, cioe' che nominano il caso E somigliano a una
                # sonda, venivano tagliate se il riordinatore dava poco. Su
                # Urgenda (giro del 3/9) erano 49 citazioni esplicite, 20 mai
                # arrivate in piattaforma: la sentenza Shell, KlimaSeniorinnen,
                # Gloucester. Il punteggio resta scritto sulla riga, come indizio.
                if (r['rete'] in NOMINALI
                        or r.get('punteggio_riordino', 1.0) >= args.soglia_riordino):
                    tenute.append(r)
                else:
                    r['motivo_scarto'] = (
                        f"riordino {r.get('punteggio_riordino')} < {args.soglia_riordino}")
                    scarti.append(r)
            righe = tenute
            scartati_riordino = prima - len(righe)
        except Exception as e:
            print(f'  riordinatore non disponibile ({e}) — si prosegue senza',
                  flush=True)

    righe.sort(key=lambda x: (x['file'], x['pagina']))

    # DOVE STA IL RIFERIMENTO — si legge dal PDF, non dal markdown.
    # Ordinate per file, ogni PDF si apre una volta sola.
    print('\ncorpo o nota (dal PDF)…', flush=True)
    t0 = time.time()
    try:
        import fitz  # noqa: F401
    except ImportError:
        print('  FERMO: manca PyMuPDF, la colonna corpo/nota non si puo')
        print('  calcolare. Installalo e rilancia:')
        print('    ./.venv/bin/pip install pymupdf')
        return 1
    for r in righe:
        pdf = HERE / r['file'].replace('markdown/', 'documents/').replace('.md', '.pdf')
        if pdf.exists():
            pos, cpos = posizione_pdf(pdf, int(r['pagina']), r['citazione_testuale'])
        else:
            pos, cpos = 'non_determinabile', 'bassa'
        r['posizione_auto'] = pos
        r['posizione'] = pos
        if cpos == 'bassa' and r['dimensioni_confidenza'] != 'bassa':
            r['dimensioni_confidenza'] = 'media'
    chiudi_pdf()
    print(f'  {time.time() - t0:.0f}s', flush=True)

    righe.sort(key=lambda x: (x['case_name'], x['document_id'], x['pagina']))

    out = HERE / (args.uscita or f'index/candidati_{Path(args.caso).stem}.csv')
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', newline='', encoding='utf-8') as f:
        # SI TOGLIE IL TESTO INTERO PRIMA DI SCRIVERE. Le colonne del CSV si
        # ricavano dalle chiavi della prima riga, quindi un campo di servizio
        # dimenticato qui diventa una colonna in tutti i file prodotti -- con
        # dentro il frammento per esteso, ripetuto accanto alla sua versione
        # leggibile. Serviva al riordinatore, che ha gia' finito.
        for _r in righe:
            _r.pop('verbatim_intero', None)
        w = csv.DictWriter(f, fieldnames=list(righe[0].keys()))
        w.writeheader()
        w.writerows(righe)

    import collections
    c = collections.Counter(r['rete'] for r in righe)
    print(f'RIGHE      : {len(righe):,}')
    for k, v in c.most_common():
        print(f'  {k:12s}: {v:,}')
    print(f'documenti  : {len({r["document_id"] for r in righe}):,}')
    d = collections.Counter(r['sede_auto'] for r in righe)
    print('sede (proposta):')
    for k, v in d.most_common():
        print(f'  {k:18s}: {v:,}')
    n = collections.Counter(r['posizione_auto'] for r in righe)
    print(f"posizione  : corpo {n.get('corpo', 0):,}   nota {n.get('nota', 0):,}")
    if dmin and not args.con_anteriori:
        print(f'anteriori  : {len(anteriori):,} candidati in documenti '
              f'precedenti al {dmin} — tolti (con --con-anteriori restano)')
    if duplicati:
        print(f'duplicati  : {duplicati:,} righe erano copie dello stesso testo')
    if scartati_riordino:
        print(f'riordino   : {scartati_riordino:,} candidati sotto '
              f'{args.soglia_riordino} — tolti')
    sosp = sum(1 for r in righe if r['sospetto'])
    if sosp:
        print(f'SOSPETTE   : {sosp:,} righe piu vicine a una formulazione '
              f'esclusa che alla sonda — da leggere per prime')
    b = sum(1 for r in righe if r['dimensioni_confidenza'] == 'bassa')
    if b:
        print(f'da guardare per prime: {b:,} righe con confidenza bassa')
    print(f'casi       : {len({r["case_id"] for r in righe}):,}')
    print(f'uscita     : {out}')

    # ── GLI SCARTI NON SPARISCONO ───────────────────────────────────────
    #
    # PERCHE'. Il controllo manuale del 20% verifica come e' stata
    # classificata una riga CHE E' GIA' NEL CSV. Non guarda mai cio' che la
    # macchina ha tolto prima: i candidati sotto soglia, gli anteriori, le
    # copie. Se quelle righe sparissero, sarebbero decisioni prese dal
    # modello e da nessun altro, e nessun controllo previsto dal metodo le
    # toccherebbe mai.
    #
    # Quindi si scrivono, con il motivo. Il campione del 20% deve
    # comprenderne una quota: e' l'unico modo di accorgersi se la soglia sta
    # buttando via roba buona.
    if scarti:
        fs = out.with_name(out.stem + '.SCARTI.csv')
        campi = list(righe[0].keys()) + ['motivo_scarto']
        with fs.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=campi, extrasaction='ignore')
            w.writeheader()
            for r in scarti:
                r.setdefault('copie', '')
                r.setdefault('anteriore', '')
                w.writerow({k: r.get(k, '') for k in campi})
        import collections as _c
        print(f'scarti     : {fs}')
        for k, v in _c.Counter(
                r.get('motivo_scarto', '?').split(' ')[0] for r in scarti
        ).most_common():
            print(f'   {v:>6,}  {k}')

    # Le istruzioni di lettura, accanto al CSV.
    istr = re.search(r'^istruzioni_lettura:\s*\|(.*)$', cb_testo, re.M | re.S)
    if istr:
        gemello = out.with_suffix('.ISTRUZIONI.md')
        gemello.write_text(
            f'# Come classificare — codebook {cb_versione}\n\n'
            f'Caso citato: **{nome}**\n\n'
            f'Righe da classificare: {len(righe):,}\n\n'
            + '\n'.join(l[2:] if l.startswith('  ') else l
                        for l in istr.group(1).split(chr(10))).strip()
            + '\n\n---\n\nCategorie e casi limite: `codebook/citazioni.yaml`.\n',
            encoding='utf-8')
        print(f'istruzioni : {gemello}')
    return 0


if __name__ == '__main__':
    import giornale  # il giornale delle operazioni (02/10/2026): ogni esecuzione, i file, le scritture, gli errori
    giornale.avvia()
    raise SystemExit(main())
