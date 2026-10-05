"""S08, LA COPPIA CANDIDATA: il testo dell'atto attorno ai due riferimenti e gli INDIZI DETERMINISTICI (05/10/2026).

Serve a tre strumenti, che devono vedere la stessa coppia nello stesso modo:
  tools/leggi_coppia_l13.py   la domanda L13 a DeepSeek e al reranker che ragiona (cinque letture);
  tools/decidi_s08.py         la decisione che mette insieme le letture e gli indizi;
  tools/coppie_vicine.py      l'elenco delle coppie e la taratura della soglia.

Una `Coppia` nasce da due righe vive della banca dati (o righe nuove della scansione) dello stesso caso e dello stesso atto.
NIENTE e' scritto in banca dati: e' tutto lettura di una fotografia (`training/s08/banca_*.json.gz`) e dei file Markdown.

GLI INDIZI (`Coppia.indizi`) NON ENTRANO MAI NEL PROMPT: servono a misurare le letture a parte e a rimandare al team le
coppie in cui le letture e gli indizi forti si contraddicono. Sono tutti dichiarati con la loro precisione misurata sulle 850
coppie C03 riviste a mano (training/misure/S08-COPPIE-VICINE-2026-10-04.md, `coppie_vicine.py taratura`).
"""
import functools
import pathlib
import re
import sys
import unicodedata

from rapidfuzz import fuzz

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI / 'tools'))
import cerca_s05_per_atto as B  # noqa: E402

ATTORNO = 1500          # caratteri di atto prima del primo riferimento e dopo l'ultimo
TETTO_FINESTRA = 26000  # la finestra non supera questo (due riferimenti lontanissimi: si tagliano i bordi, mai il mezzo)
SOGLIA_FRASE = 95       # R15: stessa frase se il rapporto rapidfuzz e' almeno questo (come unisci_c03)
MIN_FRASE = 40          # caratteri minimi della frase sostenuta per il confronto
LUNGHEZZA_NOME = 160    # caratteri dopo il nome confrontati per «stesse parole»
PAGINA = re.compile(r'<!--\s*page\s+(\d+)\s*-->')
VUOTA = re.compile(r'\n[ \t]*\n')


def norm(s):
    """minuscolo, senza accenti dispersi e senza segni: il confronto delle frasi (stesso criterio di unisci_c03.norm)"""
    s = unicodedata.normalize('NFKC', s or '').lower()
    return re.sub(r'\s+', ' ', re.sub(r'[^\w]+', ' ', s)).strip()


@functools.lru_cache(maxsize=64)
def leggi_atto(file):
    """(testo intero del file Markdown, front matter, offset in cui finisce, segni di pagina). In cache: le coppie dello stesso
    atto lo riusano."""
    testo = (QUI / file).read_text(encoding='utf-8', errors='replace')
    meta, inizio = B.front_matter(testo)
    return testo, meta, inizio, B.pagine(testo)


def pulisci_pagine(t):
    """il segno di pagina com'e' nel prompt delle altre letture: [pagina N]"""
    return PAGINA.sub(lambda m: f'[pagina {m.group(1)}]', t)


def pagina_riga(r):
    """la pagina della riga: validata dal team, altrimenti proposta, altrimenti dal segno di pagina del file"""
    for k in ('validato_pagina', 'proposto_pagina', 'pagina'):
        try:
            return int(r.get(k))
        except (TypeError, ValueError):
            pass
    return None


def lunghezza_riferimento(r):
    """quanti caratteri occupa il riferimento che comincia a `char_start`: la forma trovata dalla rete lessicale; per la rete
    descrittiva (il nome non c'e') la lunghezza della descrizione, al massimo 60"""
    f = r.get('proposto_forma_trovata') or ''
    if f and not f.startswith('descrizione'):
        return len(f)
    return 40


class Coppia:
    """Due righe vive dello stesso atto e dello stesso caso. `a` viene prima nel testo di `b`."""

    def __init__(self, a, b, id_coppia='', caso=''):
        if int(a['char_start']) > int(b['char_start']):
            a, b = b, a
        self.a, self.b = a, b
        self.id = id_coppia or f"{a.get('codice')}-{b.get('codice')}"
        self.caso = caso or a.get('caso_citato', '')
        self.file = a['file']
        self.testo, self.meta, self.inizio, self.segni = leggi_atto(self.file)
        self.pa, self.pb = int(a['char_start']), int(b['char_start'])

    # ── la finestra di testo dell'atto ───────────────────────────────────────────────────────────────────────────

    def intervallo(self):
        """(da, a) in caratteri del file: dal primo riferimento meno ATTORNO fino all'ultimo piu' ATTORNO; allargato ai segni di
        pagina; se supera il tetto si tagliano i due bordi"""
        da = max(self.inizio, self.pa - ATTORNO)
        a = min(len(self.testo), self.pb + lunghezza_riferimento(self.b) + ATTORNO)
        if a - da > TETTO_FINESTRA:
            extra = (a - da - TETTO_FINESTRA)
            da, a = da + extra // 2, a - (extra - extra // 2)
        return da, a

    def finestra(self):
        """(testo con i segni ⟦A⟧ e ⟦B⟧ per il modello, testo puro per i freni). I segni stanno PRIMA del riferimento, mai dentro
        una parola: il testo puro e' il testo dell'atto com'e' (con [pagina N]), quello su cui i freni cercano le frasi."""
        da, a = self.intervallo()
        puro = pulisci_pagine(self.testo[da:a])
        pezzi, cur = [], da
        for p, marca in ((self.pa, '⟦A⟧'), (self.pb, '⟦B⟧')):
            pezzi.append(self.testo[cur:p])
            pezzi.append(marca)
            cur = p
        pezzi.append(self.testo[cur:a])
        return pulisci_pagine(''.join(pezzi)), puro

    # ── gli indizi deterministici ────────────────────────────────────────────────────────────────────────────────

    def _nota_di(self, pos):
        """(numero della nota che contiene `pos`, dove comincia) o (None, None) se `pos` sta nel testo.
        Si guarda il TESTO, non `proposto_posizione` (sbagliata in molte righe: «segnata corpo ma e' la nota 111»): `pos` e' in una
        nota se l'ultimo inizio di nota prima di lui (un numero a inizio riga, filtrato da `e_inizio_nota`) sta nella stessa
        pagina e fra i due non c'e' una riga vuota, cioe' un cambio di paragrafo (le note stanno una sotto l'altra)."""
        da = max(self.inizio, pos - 4000)
        ultimo = None
        for x in B.INIZIO_NOTA.finditer(self.testo, da, min(len(self.testo), pos + 1)):
            if x.end() > pos:
                break
            if B.e_inizio_nota(self.testo, x):
                ultimo = x
        if ultimo is None:
            return None, None
        fra = self.testo[ultimo.end():pos]
        if VUOTA.search(fra) or PAGINA.search(fra):
            return None, None
        return (ultimo.group(1) or ultimo.group(3) or ultimo.group(2)), ultimo.end()

    def _posizione(self, r):
        """«nota» se il punto del riferimento e' dentro una nota a pie' di pagina, altrimenti «testo»"""
        return 'nota' if self._nota_di(int(r['char_start']))[0] else 'testo'

    def _frase_della_riga(self, r):
        """l'intervallo della frase della riga: `proposto_frase_offset` se c'e', altrimenti 350 caratteri attorno al nome"""
        o = r.get('proposto_frase_offset')
        try:
            if isinstance(o, list) and len(o) == 2:
                return int(o[0]), int(o[1])
        except (TypeError, ValueError):
            pass
        c = int(r['char_start'])
        return max(self.inizio, c - 200), c + 150

    def _nota_chiamata(self, nota, testo_r):
        """la nota di `nota` (la riga in nota) e' chiamata dalla frase di `testo_r`? Il richiamo e' il numero della nota
        attaccato alla fine di una parola o di un segno nella frase («…1990)15.»): cerca il numero e guarda che non sia una
        cifra qualunque (un anno, un numero di paragrafo)."""
        n, _ = self._nota_di(int(nota['char_start']))
        if not n:
            return None
        d, a = self._frase_della_riga(testo_r)
        a = min(len(self.testo), a + 40)
        frase = self.testo[d:a]
        return bool(re.search(r'(?<=[^\W\d_\s.,;:])' + n + r'(?![\d])|(?<=[\)\]\.\,\;\:”"»’\'])' + n + r'(?![\d])', frase))

    def indizi(self):
        a, b = self.a, self.b
        fa, fb = norm(a.get('proposto_frase_sostenuta')), norm(b.get('proposto_frase_sostenuta'))
        pos_a, pos_b = self._posizione(a), self._posizione(b)
        entro = self.testo[self.pa:self.pb]
        na, _ = self._nota_di(self.pa) if pos_a == 'nota' else (None, None)
        nb, _ = self._nota_di(self.pb) if pos_b == 'nota' else (None, None)
        confine = B.confine_di_nota(self.testo, self.pa + lunghezza_riferimento(a), self.pb)
        par_a, par_b = set(a.get('proposto_paragrafi') or []), set(b.get('proposto_paragrafi') or [])
        ia = {
            'distanza': self.pb - self.pa,
            'pagine': abs((pagina_riga(a) or 0) - (pagina_riga(b) or 0)) if pagina_riga(a) and pagina_riga(b) else None,
            'stessa_pagina': pagina_riga(a) == pagina_riga(b) and pagina_riga(a) is not None,
            'posizione_a': pos_a, 'posizione_b': pos_b,
            'stessa_frase': bool(len(fa) >= MIN_FRASE and len(fb) >= MIN_FRASE and (fa == fb or fuzz.ratio(fa, fb) >= SOGLIA_FRASE)),
            'nota_contro_testo': {pos_a, pos_b} == {'testo', 'nota'},
            'confine_di_nota_fra_le_due': confine,
            'stesso_paragrafo': VUOTA.search(entro) is None,
            'stessa_nota': bool(na and nb and na == nb and not confine),
            'due_note_diverse': bool(pos_a == 'nota' and pos_b == 'nota' and confine),
            'paragrafi_in_comune': bool(par_a & par_b),
            'paragrafi_diversi': bool(par_a and par_b and not (par_a & par_b)),
            'stesse_parole': round(fuzz.ratio(norm(self.testo[self.pa:self.pa + LUNGHEZZA_NOME]),
                                              norm(self.testo[self.pb:self.pb + LUNGHEZZA_NOME])) / 100, 3),
        }
        if ia['nota_contro_testo']:
            nota, testo_r = (a, b) if pos_a == 'nota' else (b, a)
            ia['nota_chiamata_dal_testo'] = self._nota_chiamata(nota, testo_r)
        else:
            ia['nota_chiamata_dal_testo'] = None
        return ia

    def dove(self, r):
        """«testo» o «nota» (o «incerta»): dove sta il riferimento secondo la banca dati"""
        return self._posizione(r)


def verdetto_indizi(i):
    """IL GIUDIZIO DEGLI INDIZI: (esito, motivo, forte). `esito` e' «una», «due» o None (nessun indizio); `forte` dice se
    l'indizio ha una precisione misurata di almeno 0,97 sulle 692 coppie C03 riviste a mano dello stesso atto
    (`coppie_vicine.py taratura`, rapporto S08): solo un indizio forte puo' mandare al team una coppia su cui le letture
    sono d'accordo. Gli indizi deboli restano nel rapporto e nel file delle decisioni, ma non comandano.
      una  forte  stessa nota: le due righe sono nella stessa nota, senza un inizio di nota fra loro;
      una  forte  riga del testo e riga in nota: la nota e' chiamata dalla frase del testo (il richiamo e' attaccato alla frase);
      due  debole due note diverse (c'e' un inizio di nota fra le due righe in nota): note consecutive restano distinte;
      due  debole la nota non e' chiamata dalla frase e i paragrafi citati sono diversi."""
    if i['stessa_nota']:
        return 'una', 'stessa nota', True
    if i['nota_contro_testo'] and i['nota_chiamata_dal_testo']:
        return 'una', 'la nota e\' chiamata dalla frase del testo', True
    if i['due_note_diverse']:
        return 'due', 'due note diverse', False
    if i['paragrafi_diversi'] and i['nota_chiamata_dal_testo'] is False:
        return 'due', 'nota non chiamata e paragrafi citati diversi', False
    return None, '', False
