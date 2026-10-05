"""L13, LA DOMANDA SULLA COPPIA: «UNA CITAZIONE O DUE?» (05/10/2026, S08, coppie vicine).

Due riferimenti allo stesso caso, nello stesso atto, a meno della soglia di S08 (5.000 caratteri) sono una COPPIA CANDIDATA
(tools/coppie_vicine.py). Questo file fa leggere ogni coppia per intero, con il testo vero dell'atto fra i due punti, a DeepSeek
(cinque letture, ragionamento alto, come L05) e al reranker che ragiona (Qwen3.5-9B, tre letture): ognuno dice se i due
riferimenti sono la stessa citazione o due, con la frase esatta di ciascuno e il motivo. Poi tools/decidi_s08.py mette insieme
le letture e gli indizi deterministici (tools/coppia_s08.py). Gli indizi NON entrano mai nella domanda.

Fasi (come tools/leggi_ripresa.py):
    prepara      Mac    la domanda di ogni coppia, scritta in richieste/*.jsonl.gz; il freno 1 (`leggibile`) prima di mandare
                        il testo al modello: una finestra senza parole vere va in un elenco da rifare con l'OCR
    secco        Mac    PROVA A SECCO: costruisce le domande, conta i token, ne stampa una; non chiama nessun modello
    leggi        ReCaS  il lettore: una chiamata per coppia e per lettura (chiamata_deepseek.chiama: tre tentativi identici),
                        riprende da dove era, dopo --minuti non ricomincia, scrive FINITO
    raccogli     Mac    i FRENI 2-4 (freni.py, R14 e R16) sulle risposte: una lettura conta solo se le due frasi stanno nel testo
                        dell'atto e non sono copiate dal prompt; i voti per coppia
    prova-freni  Mac    il caso che DEVE fallire (frase inventata, frase copiata dal prompt): se passa, la prova fallisce

Niente e' scritto in banca dati. Le frasi si verificano sul testo dell'atto SENZA i segni ⟦A⟧ e ⟦B⟧ (la finestra pura
conservata nella richiesta: `coppia_s08.Coppia.finestra`).
"""
import argparse
import collections
import concurrent.futures as cf
import datetime
import gzip
import json
import pathlib
import re
import sys
import threading
import time

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI / 'tools'))
import freni  # noqa: E402

CODICE = 'L13'
LETTURE_DS = 5          # come L05 (cinque letture, tre su cinque)
LETTURE_RR = 3          # il 9B e' piu' economico ma non piu' stabile: tre letture, decisione di costo
TETTO_DS = 24000        # tetto della risposta col ragionamento alto (ragionamento.USCITA_DS)
TETTO_RR = 12000
CONTESTO = 65536
ESITI = ('una', 'due', 'incerta')
DOVE = ('testo', 'nota', 'tabella', 'altro')
SEGNI = re.compile(r'⟦/?[AB]⟧')

MODULO = """Sei un giurista che codifica le citazioni di una sentenza climatica negli atti successivi.
Il caso citato e' {nome_caso} (decisione del {data_caso}).

DOCUMENTO: {titolo} ({tipo_atto}), documento {document_id}{lingua}.
Una ricerca per nome ha trovato in questo atto DUE riferimenti al caso, vicini fra loro:
  A: {descr_a}
  B: {descr_b}

Qui sotto il testo dell'atto da un po' prima di A fino a un po' dopo B. I due punti sono marcati da ⟦A⟧ e ⟦B⟧, messi subito
PRIMA del riferimento. [pagina N] segna il cambio di pagina. Le note a pie' di pagina stanno in fondo alla pagina, ognuna col suo
numero all'inizio della riga. Il testo e' estratto dal PDF: puo' avere righe spezzate e refusi.
---
{testo}
---

DOMANDA. I due riferimenti A e B sono UNA citazione sola del caso o DUE citazioni diverse?

UNA: sono lo stesso punto del discorso dell'atto, citato due volte. Casi tipici: il nome nella frase del testo e la nota che
quella stessa frase chiama (la nota ripete il nome del caso); il nome trovato due volte nello stesso punto (per esteso e poi
abbreviato nella stessa frase; due volte nella stessa nota; una nota spezzata dal cambio pagina; la sentenza e il nome del
caso nello stesso rinvio).
DUE: sono citazioni diverse. Casi tipici: la nota e' chiamata da un'altra frase (il numero di richiamo sta in un'altra frase,
non in quella che contiene il riferimento nel testo); due frasi diverse, anche dello stesso paragrafo, che dicono ognuna una cosa
sul caso; due note diverse; due paragrafi o due sezioni diversi.
ATTENZIONE: non basta che le due frasi si assomiglino o che la macchina abbia attaccato alla nota la frase del testo: conta DOVE
sta ciascun riferimento (nel testo o in quale nota) e QUALE frase chiama la nota. Controlla il numero del richiamo.
INCERTA: solo se il testo non basta a decidere (testo rotto, nota non trovata, richiamo illeggibile).

Se la risposta e' UNA, indica quale dei due resta come la citazione («riga_principale»): quello che sta nel testo, non nella
nota; se stanno tutti e due nel testo o tutti e due nella stessa nota, il primo che compare.

Rispondi SOLO con un oggetto JSON:
{{"esito": "una" | "due" | "incerta", "riga_principale": "A" | "B" | "" , "dove_A": "testo" | "nota" | "tabella" | "altro",
  "dove_B": "testo" | "nota" | "tabella" | "altro", "nota_chiamata": "numero della nota chiamata dalla frase del testo, o vuoto",
  "frase_A": "la frase dell'atto che contiene A (o a cui e' agganciata la nota A), COPIATA ALLA LETTERA nella sua lingua, massimo 60 parole, senza i segni ⟦ ⟧",
  "frase_B": "come frase_A, per B",
  "motivo": "una frase, massimo quaranta parole"}}
Niente fuori dal JSON."""

ISTRUZIONI_RR = """Sei il RERANKER CHE RAGIONA di TRACE, una ricerca sul contenzioso climatico. Il tuo lavoro viene accanto a quello di un
altro lettore (DeepSeek) che risponde alla stessa domanda: se non siete d'accordo la coppia va al gruppo di ricerca. Un «incerta»
onesto vale piu' di una risposta sbagliata. Le frasi che citi dall'atto devono essere COPIATE ALLA LETTERA dal testo qui sotto (le
controlla un programma parola per parola): mai un tuo riassunto, mai il testo di queste istruzioni. Ragiona passo per passo:
dove sta A, dove sta B, quale frase chiama la nota, se e' lo stesso punto del discorso.

"""


class DomandaL13:
    """La domanda L13 di una coppia: stesse parole per DeepSeek e per il reranker (il reranker ha in piu' le sue istruzioni)."""

    def __init__(self):
        import yaml
        import sonde
        self._casi = {}
        self._yaml, self._sonde = yaml, sonde

    def caso(self, caso):
        if caso not in self._casi:
            c = self._yaml.safe_load(open(self._sonde.file_caso(caso), encoding='utf-8'))
            self._casi[caso] = (c.get('nome') or caso, str(c.get('data_decisione') or ''))
        return self._casi[caso]

    @staticmethod
    def descrivi(r, lettera):
        forma = r.get('proposto_forma_trovata') or r.get('forma') or ''
        pagina = r.get('proposto_pagina') or r.get('validato_pagina') or r.get('pagina')
        dove = f'pagina {pagina}' if pagina else 'pagina non nota'
        if forma.startswith('descrizione') or not forma:
            return f'riferimento per descrizione (senza il nome), {dove}'
        return f'«{forma}», {dove}'

    def testo(self, coppia, rr=False):
        nome, data = self.caso(coppia.caso)
        meta = coppia.meta
        con_segni, _ = coppia.finestra()
        lingua = f", lingua {meta['lingue']}" if meta.get('lingue') else ''
        corpo = MODULO.format(nome_caso=nome, data_caso=data, titolo=meta.get('document_title') or meta.get('case_name') or '',
                              tipo_atto=meta.get('tipo_atto') or 'atto', document_id=meta.get('document_id') or coppia.a.get('document_id'),
                              lingua=lingua, descr_a=self.descrivi(coppia.a, 'A'), descr_b=self.descrivi(coppia.b, 'B'),
                              testo=con_segni)
        return (ISTRUZIONI_RR + corpo) if rr else corpo

    @staticmethod
    def testi_prompt():
        """i testi che stavano nel prompt e non nell'atto: una «frase» che coincide con uno di questi e' copiata dal prompt"""
        return [MODULO, ISTRUZIONI_RR]


class Freni:
    """I freni 2-4 sulla risposta di una lettura (freni.py: R14 con la frase intera, R16). Una lettura conta solo se passa."""

    def __init__(self, puro, testi_prompt):
        self.puro, self.testi_prompt = puro, testi_prompt

    def frase(self, f):
        f = SEGNI.sub('', str(f or '')).strip()
        return freni.verifica(f, self.puro, self.testi_prompt, ricostruisci=True, intera=True) if f else 'assente'

    def verifica(self, j):
        """(ok, motivo, dettaglio): j e' il JSON della lettura"""
        if not isinstance(j, dict) or j.get('esito') not in ESITI:
            return False, 'risposta senza esito valido', {}
        det = {'frase_A': self.frase(j.get('frase_A')), 'frase_B': self.frase(j.get('frase_B'))}
        if 'inventata' in det.values():
            return False, 'frase copiata dal prompt', det
        if j['esito'] != 'incerta':
            if det['frase_A'] != 'trovata' or det['frase_B'] != 'trovata':
                return False, 'frase non trovata nell\'atto', det
            if j['esito'] == 'una' and j.get('riga_principale') not in ('A', 'B'):
                return False, 'una citazione senza riga principale', det
        else:
            for k, v in det.items():       # un'incerta puo' non avere frasi, ma una frase data deve stare nell'atto
                if v == 'non trovata':
                    return False, 'frase non trovata nell\'atto', det
        return True, '', det


def esito_json(t):
    """il primo oggetto JSON della risposta (dopo un eventuale </think>, con o senza recinti)"""
    t = str(t or '')
    if '</think>' in t:
        t = t.rsplit('</think>', 1)[1]
    t = re.sub(r'^```(?:json)?\s*|\s*```$', '', t.strip())
    i = t.find('{')
    while i >= 0:
        try:
            return json.JSONDecoder().raw_decode(t[i:])[0]
        except ValueError:
            i = t.find('{', i + 1)
    return {}


def jl(f):
    op = gzip.open if str(f).endswith('.gz') else open
    out = []
    if pathlib.Path(f).exists():
        with op(f, 'rt', encoding='utf-8') as h:
            for x in h:
                try:
                    out.append(json.loads(x))
                except ValueError:
                    pass
    return out


# ── prepara e secco (Mac) ────────────────────────────────────────────────────────────────────────────────────────

class Preparazione:
    """Dalle coppie (elenco di dict con `id`, `a`, `b` come in `coppie_vicine.elenco_coppie`, o dalle coppie C03 riviste) alle
    richieste. Una richiesta = una coppia, con `letture` e il testo puro per i freni."""

    def __init__(self, banca, lettore='ds'):
        self.banca, self.lettore = banca, lettore
        self.domanda = DomandaL13()

    def richiesta(self, id_coppia, a, b, priorita=1, gruppo=''):
        import coppia_s08 as CS
        c = CS.Coppia(a, b, id_coppia)
        con, puro = c.finestra()
        ok, quota = freni.leggibile(puro)             # FRENO 1: niente testo rotto al modello
        rr = self.lettore == 'rr'
        return {'id': id_coppia, 'chiave': id_coppia, 'gruppo': gruppo or a.get('document_id', ''), 'priorita': priorita,
                'testo': self.domanda.testo(c, rr), 'letture': LETTURE_RR if rr else LETTURE_DS,
                'tetto': TETTO_RR if rr else TETTO_DS, 'puro': puro, 'leggibile': ok, 'quota_parole': quota,
                'caso': c.caso, 'atto': a.get('document_id', ''), 'codici': [a.get('codice'), b.get('codice')],
                'char': [c.pa, c.pb], 'lettore': self.lettore}

    def insieme(self, soglia, scansione=''):
        """Le coppie da leggere: prima (priorita 0) le coppie della VERITA' C03 con le due righe nello stesso atto, che servono a
        misurare i lettori; poi (priorita 1) i legami di S08 alla soglia, comprese le righe nuove della scansione (dopo C04), senza
        ripetere le coppie gia' nella verita'. Ritorna [{id, a, b, priorita, origine}] con a e b righe (dict)."""
        import coppie_vicine as CV
        out, viste = [], set()
        for d, a, b, i in CV.Taratura(self.banca).coppie_stesso_atto():
            ca, cb = a['codice'], b['codice']
            viste.add(frozenset((ca, cb)))
            out.append({'id': f'{ca}__{cb}', 'a': a, 'b': b, 'priorita': 0, 'origine': 'verita_c03', 'verita': d})
        nuove = []
        if scansione and pathlib.Path(scansione).exists():
            rec = json.load(open(scansione, encoding='utf-8'))['recuperate']
            cl = CV.classifica_recuperate(rec, self.banca)
            # TUTTE le righe nuove, senza il filtro di C04: S08 sta PRIMA dei controlli C01-C04 nel ciclo (S08-AGGANCIO.patch), e la
            # stima di C04 su righe finte scartava proprio la citazione di Children of Austria p. 29 (la data del Klimabeschluss).
            nuove = [x for x in cl if x['esito'] == 'nuova']
        riga = {x['chiave']: x for x in nuove}
        for c in CV.elenco_coppie(self.banca, soglia, nuove):
            ra = self.banca.get(c['a']['chiave']) or riga[c['a']['chiave']]
            rb = self.banca.get(c['b']['chiave']) or riga[c['b']['chiave']]
            ca, cb = ra.get('codice') or c['a']['chiave'], rb.get('codice') or c['b']['chiave']
            if frozenset((ca, cb)) in viste:
                continue
            out.append({'id': f'{ca}__{cb}', 'a': ra, 'b': rb, 'priorita': 1, 'origine': 'legame_s08', 'verita': None})
        return out

    def prepara(self, coppie, uscita, priorita=1):
        """scrive le richieste leggibili in `uscita` (jsonl.gz) e le illeggibili in `<uscita>.illeggibili.json`; ritorna i conti"""
        n, illeggibili = collections.Counter(), []
        with gzip.open(uscita, 'wt', encoding='utf-8') as h:
            for x in coppie:
                p = x.get('priorita', priorita)
                r = self.richiesta(x['id'], x['a'], x['b'], p)
                if not r['leggibile']:
                    n['illeggibile'] += 1
                    illeggibili.append({'id': r['id'], 'atto': r['atto'], 'quota_parole': r['quota_parole']})
                    continue
                n['richieste'] += 1
                h.write(json.dumps(r, ensure_ascii=False) + '\n')
        json.dump(illeggibili, open(str(uscita) + '.illeggibili.json', 'w', encoding='utf-8'), ensure_ascii=False)
        return dict(n)


def conta_token(testo, tok=None):
    if tok is None:
        return len(testo) // 3 + 64
    return len(tok.encode(testo).ids) + 64


def secco(richieste, tokenizer=None, stampa=1):
    """PROVA A SECCO: nessun modello. Ritorna {richieste, token mediani e massimi, quante non entrano nel contesto}."""
    tok = None
    if tokenizer and pathlib.Path(tokenizer).exists():
        from tokenizers import Tokenizer
        tok = Tokenizer.from_file(str(tokenizer))
    nt = sorted(conta_token(r['testo'], tok) for r in richieste)
    fuori = sum(1 for n in nt if n > CONTESTO - 4000)
    for r in richieste[:stampa]:
        print('=' * 30, r['id'], '=' * 30)
        print(r['testo'])
    return {'richieste': len(nt), 'token_mediana': nt[len(nt) // 2] if nt else 0, 'token_massimo': nt[-1] if nt else 0,
            'token_totale': sum(nt), 'non_entrano_nel_contesto': fuori, 'metodo_token': 'tokenizer DeepSeek' if tok else 'stima 3 caratteri/token'}


# ── leggi (ReCaS) ────────────────────────────────────────────────────────────────────────────────────────────────

CORPI = {'deepseek-high': {'chat_template_kwargs': {'thinking': True, 'reasoning_effort': 'high'}},
         'qwen-pensa': {'chat_template_kwargs': {'enable_thinking': True}}}


def leggi(a):
    """il lettore: una chiamata per (coppia, lettura). Riprende da dove era; dopo --minuti non comincia chiamate nuove."""
    from openai import OpenAI
    import chiamata_deepseek as CD
    cli = OpenAI(api_key=pathlib.Path(a.chiave_file).read_text().strip(), base_url=a.base_url, timeout=3600)
    CD.CONTESTO = a.contesto
    tok = None
    if a.tokenizer:
        from tokenizers import Tokenizer
        tok = Tokenizer.from_file(a.tokenizer)
    corpo = CORPI[a.ragionamento]
    fatte = {x['chiave'] for x in jl(a.uscita)}
    lavori = []
    for r in jl(a.richieste):
        for k in range(r.get('letture') or 1):
            if f"{r['chiave']}|{k}" not in fatte:
                lavori.append((r.get('priorita', 0), r.get('gruppo') or '', r['chiave'], k, r))
    lavori.sort(key=lambda x: x[:4])
    print(f'{len(lavori)} letture da fare ({len(fatte)} gia\' fatte), {a.modello}, {a.ragionamento}, contesto {a.contesto}', flush=True)
    t0, lock, stop = time.time(), threading.Lock(), threading.Event()

    def una(lav):
        _, _, chiave, k, r = lav
        if stop.is_set() or (a.minuti and time.time() - t0 > a.minuti * 60):
            stop.set()
            return None
        n = conta_token(r['testo'], tok)
        cap = min(r.get('tetto') or TETTO_DS, a.contesto - n - 512)
        if cap < 2000:
            x = {'testo': '', 'errore': f'domanda troppo lunga: {n} token su {a.contesto}'}
        else:
            x = CD.chiama(cli, a.modello, r['testo'], corpo, tetto=cap)
        rag = x.get('ragionamento') or ''
        out = {'id': r['id'], 'chiave': f'{chiave}|{k}', 'lettura': k, 'testo': x.get('testo', ''), 'token': x.get('token'),
               'ragionamento': {'caratteri': len(rag), 'coda': rag[-3000:]}, 'chiamata': x.get('chiamata'),
               'errore': x.get('errore'), 'data': datetime.date.today().isoformat(), 'lettore': a.modello, 'codice': CODICE}
        with lock, open(a.uscita, 'a', encoding='utf-8') as f:
            f.write(json.dumps(out, ensure_ascii=False) + '\n')
        return out

    n = 0
    with cf.ThreadPoolExecutor(a.paralleli) as ex:
        for o in ex.map(una, lavori):
            if o is not None:
                n += 1
                if n % 25 == 0:
                    print(f'  {n}/{len(lavori)} [{time.time() - t0:.0f}s]', flush=True)
    resto = len(lavori) - n
    print(f'fatte {n} in {time.time() - t0:.0f}s; ' + ('FINITO' if resto == 0 else f'TEMPO: ne restano {resto}'), flush=True)


# ── raccogli (Mac) ───────────────────────────────────────────────────────────────────────────────────────────────

def raccogli(richieste, esiti):
    """{id: {voti, valide, scartate, motivi_scarto, letture:[...]}}: i freni 2-4 su ogni lettura. `richieste` serve per il testo
    puro dell'atto e per i testi del prompt."""
    per = collections.defaultdict(list)
    for x in jl(esiti):
        per[x['id']].append(x)
    out = {}
    for r in richieste:
        fr = Freni(r['puro'], DomandaL13.testi_prompt())
        voti, motivi, lett = collections.Counter(), collections.Counter(), []
        for x in sorted(per.get(r['id'], []), key=lambda y: y['lettura']):
            j = esito_json(x.get('testo'))
            ok, motivo, det = fr.verifica(j)
            lett.append({'lettura': x['lettura'], 'valida': ok, 'motivo_scarto': motivo, 'verifica_frasi': det, 'json': j})
            if ok:
                voti[j['esito']] += 1
            else:
                motivi[motivo] += 1
        out[r['id']] = {'voti': dict(voti), 'valide': sum(voti.values()), 'scartate': dict(motivi), 'fatte': len(lett),
                        'previste': r.get('letture'), 'letture': lett}
    return out


# ── prova dei freni: il caso che DEVE fallire ───────────────────────────────────────────────────────────────────

def prova_freni():
    """Ritorna l'elenco dei casi in cui un freno NON ha fermato quello che doveva (vuoto = la prova passa)."""
    atto = ('[pagina 4] La Corte ha ritenuto che lo Stato debba ridurre le emissioni almeno del 25 per cento entro il 2020, come '
            'stabilito nella sentenza Urgenda.1 Nel testo seguente si discute della responsabilita dello Stato.\n'
            '1 Urgenda Foundation v The State of the Netherlands, Hoge Raad, 20 December 2019.\n')
    fr = Freni(atto, DomandaL13.testi_prompt())
    buona = {'esito': 'una', 'riga_principale': 'A', 'frase_A': 'La Corte ha ritenuto che lo Stato debba ridurre le emissioni '
             'almeno del 25 per cento entro il 2020, come stabilito nella sentenza Urgenda.', 'frase_B': '1 Urgenda Foundation v The '
             'State of the Netherlands, Hoge Raad, 20 December 2019.'}
    prima = MODULO.split('DOMANDA.')[1].split('UNA:')[0] + ' ' + ISTRUZIONI_RR
    casi = [('lettura buona deve passare', buona, True),
            ('frase inventata (finale che nell\'atto non c\'e\')', {**buona, 'frase_A': buona['frase_A'] + ' e ha ordinato un risarcimento di dieci milioni'}, False),
            ('frase copiata dal prompt', {**buona, 'frase_B': 'sono lo stesso punto del discorso dell\'atto, citato due volte'}, False),
            ('esito fuori elenco', {**buona, 'esito': 'forse'}, False),
            ('una senza riga principale', {**buona, 'riga_principale': ''}, False)]
    sbagliati = []
    for nome, j, deve_passare in casi:
        ok, motivo, _ = fr.verifica(j)
        if ok != deve_passare:
            sbagliati.append((nome, motivo))
    # il freno 1: una finestra di caratteri rotti non arriva al modello
    if freni.leggibile('Ð§Ñ‚Ð¾ ' * 80)[0]:
        sbagliati.append(('freno 1: testo rotto lasciato passare', ''))
    if not prima:
        sbagliati.append(('prompt vuoto', ''))
    return sbagliati


# ── i blocchi per le code di ReCaS ───────────────────────────────────────────────────────────────────────────────

class Blocchi:
    """Gli script per le code di ReCaS (stesso schema di tools/ragionamento.py `blocco`). Si scrivono qui, si mandano con `manda`;
    uno script di un lavoro che gira non si tocca MAI (bash lo legge a pezzi): questi sono file nuovi con nomi nuovi.
      DeepSeek  ~/trace/chat/coda-ds4/b_s08_coppie_l13.sh: il nome sta dopo a_scala_e0e3.sh; all'avvio guarda se la scala E0-E3 ha
                scritto FINITO nel suo log; se no, si rimette in attesa (attesa_ds) e passa il turno a un altro blocco, come
                `blocco_ds`; se si', lavora al massimo 25 minuti, poi si rimette in attesa e passa il turno.
      Qwen3.5-9B  ~/trace/misure/ragionamento/coda9b/50_rr9_s08_coppie.sh: dopo 30_ e 40_ (script in ordine di nome)."""

    G = '$H/trace/misure/ragionamento'
    DS_NOME, RR_NOME = 'b_s08_coppie_l13', '50_rr9_s08_coppie'
    PESI9 = 'Qwen/Qwen3.5-9B@c202236235762e1c871ad0ccb60c8ee5ba337b9a'

    def ds(self):
        n = self.DS_NOME
        return f"""# S08 / L13 (tools/leggi_coppia_l13.py, 05/10/2026): le coppie vicine lette da DeepSeek, cinque letture, ragionamento alto; prima le
# coppie della verita' C03 (priorita 0), poi i legami di S08; aspetta FINITO della scala E0-E3; al massimo 25 minuti per turno
H=/lustrehome/climpact; G={self.G}; cd $G
CH=$(cat $H/trace/chat/chiave)
if ! grep -q FINITO log/a_scala_e0e3.log 2>/dev/null; then
  echo "la scala E0-E3 non ha finito: mi rimetto in attesa e passo il turno"
  cp $0 $G/attesa_ds/{n}.sh
  f=$(ls -tr $G/attesa_ds/*.sh 2>/dev/null | grep -v {n}.sh | head -1); [ -n "$f" ] && mv $f $H/trace/chat/coda-ds4/
  exit 0
fi
until curl -s -m 5 -H "Authorization: Bearer $CH" http://127.0.0.1:8000/v1/models | grep -q deepseek; do sleep 30; done
$H/trace/venv/bin/python -u tools/leggi_coppia_l13.py leggi --richieste richieste/s08_l13_ds.jsonl.gz --uscita esiti/deepseek_s08_l13.jsonl \\
  --base-url http://127.0.0.1:8000/v1 --chiave-file $H/trace/chat/chiave --modello deepseek-v4-flash --ragionamento deepseek-high \\
  --contesto 65536 --paralleli 32 --minuti 25 --tokenizer $G/tokenizer_dsv4/tokenizer.json >> log/{n}.log 2>&1
grep -q FINITO log/{n}.log || cp $0 $G/attesa_ds/{n}.sh
f=$(ls -tr $G/attesa_ds/*.sh 2>/dev/null | head -1); [ -n "$f" ] && mv $f $H/trace/chat/coda-ds4/
"""

    def rr(self):
        n = self.RR_NOME
        return f"""# S08 / L13 (tools/leggi_coppia_l13.py, 05/10/2026): le coppie vicine lette dal reranker che ragiona (Qwen3.5-9B, tre letture); se il tempo del lavoro finisce prima, rimette se stesso in coda
H=/lustrehome/climpact; G={self.G}; cd $G
CH=$(cat $H/trace/chat/chiave)
RESTO=${{RESTO:-300}}
for p in ${{PORTA:-}} 8000 8001 8002 8003 8080; do curl -s -m 3 -H "Authorization: Bearer $CH" http://127.0.0.1:$p/v1/models | grep -q qwen3.5-9b && {{ PORTA=$p; break; }}; done
[ -n "$PORTA" ] || {{ echo "nessun server qwen3.5-9b: rimetto il blocco in coda"; cp $0 $(dirname $0)/../$(basename $0); exit 0; }}
$H/trace/venv/bin/python -u tools/leggi_coppia_l13.py leggi --richieste richieste/s08_l13_rr.jsonl.gz --uscita esiti/q9_s08_l13.jsonl \\
  --base-url http://127.0.0.1:$PORTA/v1 --chiave-file $H/trace/chat/chiave --modello qwen3.5-9b --ragionamento qwen-pensa \\
  --contesto 65536 --paralleli 16 --minuti $RESTO --tokenizer $H/trace/pesi/{self.PESI9}/tokenizer.json >> log/{n}.log 2>&1
grep -q FINITO log/{n}.log || cp $0 $(dirname $0)/../{n}.sh
"""

    def scrivi(self, cartella):
        cartella = pathlib.Path(cartella)
        cartella.mkdir(parents=True, exist_ok=True)
        (cartella / f'{self.DS_NOME}.sh').write_text(self.ds(), encoding='utf-8')
        (cartella / f'{self.RR_NOME}.sh').write_text(self.rr(), encoding='utf-8')
        return [cartella / f'{self.DS_NOME}.sh', cartella / f'{self.RR_NOME}.sh']


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='fase', required=True)
    s = sp.add_parser('secco'); s.add_argument('--richieste', required=True); s.add_argument('--tokenizer', default='')
    s.add_argument('--stampa', type=int, default=1)
    sp.add_parser('prova-freni')
    pr = sp.add_parser('prepara'); pr.add_argument('--banca', required=True); pr.add_argument('--scansione', default='')
    pr.add_argument('--soglia', type=int, default=5000); pr.add_argument('--lettore', choices=['ds', 'rr'], default='ds')
    pr.add_argument('--uscita', required=True)
    lg = sp.add_parser('leggi')
    lg.add_argument('--richieste', required=True); lg.add_argument('--uscita', required=True)
    lg.add_argument('--base-url', required=True); lg.add_argument('--chiave-file', required=True)
    lg.add_argument('--modello', required=True); lg.add_argument('--ragionamento', default='deepseek-high', choices=sorted(CORPI))
    lg.add_argument('--contesto', type=int, default=CONTESTO); lg.add_argument('--paralleli', type=int, default=16)
    lg.add_argument('--minuti', type=float, default=0); lg.add_argument('--tokenizer', default='')
    bl = sp.add_parser('blocchi'); bl.add_argument('--uscita', required=True)
    rc = sp.add_parser('raccogli'); rc.add_argument('--richieste', required=True); rc.add_argument('--esiti', required=True)
    rc.add_argument('--uscita', required=True)
    a = ap.parse_args()
    if a.fase == 'prepara':
        import coppie_vicine as CV
        prep = Preparazione(CV.carica_banca(a.banca), a.lettore)
        coppie = prep.insieme(a.soglia, a.scansione)
        print(len(coppie), 'coppie:', dict(collections.Counter(c['origine'] for c in coppie)))
        print(prep.prepara(coppie, a.uscita), '->', a.uscita)
    elif a.fase == 'blocchi':
        for f in Blocchi().scrivi(a.uscita):
            print(f)
    elif a.fase == 'secco':
        print(json.dumps(secco(jl(a.richieste), a.tokenizer, a.stampa), ensure_ascii=False))
    elif a.fase == 'prova-freni':
        sb = prova_freni()
        print('PROVA DEI FRENI:', 'PASSA' if not sb else f'FALLISCE {sb}')
        sys.exit(1 if sb else 0)
    elif a.fase == 'leggi':
        leggi(a)
    else:
        ris = raccogli(jl(a.richieste), a.esiti)
        json.dump(ris, open(a.uscita, 'w', encoding='utf-8'), ensure_ascii=False)
        print(len(ris), 'coppie ->', a.uscita)


if __name__ == '__main__':
    main()
