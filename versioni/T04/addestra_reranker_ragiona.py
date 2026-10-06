"""IL RERANKER CHE RAGIONA, ADDESTRATO SUL SUO STESSO RAGIONAMENTO (05/10/2026, il PI: «prova ad addestrarlo»).

PUNTO DI PARTENZA. Il reranker che ragiona di oggi e' Qwen3.5-9B NON addestrato (lavoro RRL di tools/ragionamento.py:
tutti i principi del caso in una chiamata, col ragionamento acceso). Sulle righe giudicate dal team il suo F1 sui principi
e' 0,686 (tutte, 516 risposte) e 0,704 (le 137 della giuria); il TRACE-Reranker 0.1 (T01, solo punteggio, Qwen3-Reranker-4B
con tre LoRA del 22/09) ha 0,50-0,53. Vedi training/misure/RAGIONAMENTO-2026-10-04.md e training/ragionamento/RISULTATI.md.

IL METODO: AUTOADDESTRAMENTO SUL RAGIONAMENTO (STaR, Zelikman e altri 2022; «rejection sampling» / RFT). Si tengono le
risposte ragionate che il 9B ha gia' dato (ragionamento + JSON) quando il loro ESITO coincide col giudizio del team, e su
queste si addestra un LoRA a produrre proprio quel ragionamento e quella risposta. Il giudizio del team serve SOLO a
scegliere quali risposte tenere; non entra mai nella domanda (la domanda e' la richiesta RRL di sempre, identica a quella
che il modello vede in prova). Quando il team conferma il modello, il LoRA impara il ragionamento che ha portato a quel
verdetto; le risposte sbagliate non entrano.

CHE COSA SI TIENE (funzione `Costruttore.valuta`).
  * riga CONFERMATA dal team, con i principi giudicati: la risposta e' completa (tutti i principi del caso, una volta
    ciascuno), non troncata, senza ideogrammi nella risposta e al piu' due nel ragionamento (il 9B scivola spesso in cinese:
    il 35% dei ragionamenti ne ha almeno uno), «cita_il_caso» = si', l'insieme dei
    principi detti «si'» e' UGUALE a quello del team (nessun «incerto» fra i principi), «altro» detto solo quando il team
    lo dice;
  * riga SCARTATA dal team: «cita_il_caso» = no e nessun principio «si'» (insegna a dire no ai falsi positivi); al massimo
    una quota (--quota-scartate) delle righe tenute, perche' le scartate sono la meta' del materiale;
  * fuori sempre: le righe «riclassificata» (significato ambiguo nel campo `luglio`), le righe del campione cieco, le righe
    senza giudizio sui principi.

COME SI VALUTA, ONESTAMENTE. Validazione incrociata a GRUPPI PER ATTO: tutte le 691 righe giudicate si dividono in K
piegature (di serie 4) tenendo INSIEME le righe dello stesso atto (`document_id`); per ogni piegatura si addestra solo sulle
righe utili delle altre e si fa rispondere il modello a TUTTE le righe della piegatura (anche quelle che il filtro avrebbe
scartato: la prova non e' filtrata). Mai lo stesso atto in addestramento e in prova. Il campione cieco della giuria
(GIURIA-2026-10-04.md, sezione 5: 50 righe per livello C, D, E, piu' le 120 della codifica doppia, `training/cieco_*`) NON
entra mai in addestramento; e' la misura pulita da fare DOPO, con l'adattatore finale (--finale).
La misura usa le stesse funzioni di tools/ragionamento.py (`prf`, `bootstrap_diff_f1`, `json_risposta`): F1, precisione e
richiamo sui principi dei si' del modello, confronto appaiato con le risposte del 9B di base sulle stesse righe.

DA DICHIARARE. Tre regole della bozza dei principi (cited-cases/regole-principi-BOZZA.yaml) vengono da conti fatti SU
QUESTE righe giudicate: G05 (le citazioni descrittive del team prendono sempre un principio, 27 su 27), G06 (il principio
mancato non veniva dalla proposta vista), C05 (nei pareri consultivi gli Stati partecipanti sono «parte», 5 su 6). Sono nel
testo della domanda sia del modello di base sia di quello addestrato: la validazione per atto non le puo' ripulire, quindi
il miglioramento misurato qui e' un limite alto; vale il campione cieco. Altri limiti: pochi dati (qualche decina di righe
utili per piegatura), il rischio di adattarsi alle regole della bozza (non approvata) piu' che al ragionamento giuridico, e
tutte le risposte tenute vengono da UN solo modello (di DeepSeek se ne potranno aggiungere: stesso formato).

FASI (sottocomandi).
  costruisci    (Mac) dati.jsonl.gz: le risposte del 9B, il giudizio del team, il filtro, la piegatura; mai il giudizio nella
                domanda. Stampa quante righe utili e quante tenute.
  prova-secca   (Mac, CPU) modello minuscolo con la stessa architettura: addestra due passi, fonde, controlla che il modello
                fuso dia gli stessi numeri di quello con l'adattatore. Non carica il 9B.
  fumo          (ReCaS, GPU) un passo avanti-indietro sul 9B vero con la sequenza piu' lunga che entra in memoria.
  addestra      (ReCaS, GPU) il LoRA di una piegatura (o --finale: tutte le righe utili).
  fondi         (ReCaS, GPU) somma l'adattatore ai pesi originali -> cartella servibile con vLLM.
  richieste     (ReCaS) le richieste RRL delle righe di una piegatura, per il corridore di ragionamento_corri.py.
  misura        (Mac) le misure contro il team e contro il 9B di base.
Uso: .venv/bin/python tools/addestra_reranker_ragiona.py FASE ...
"""
import argparse
import ast
import collections
import gzip
import json
import math
import pathlib
import random
import re
import shutil
import sys
import time

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI / 'tools'))
T = QUI / 'training'
R = T / 'ragionamento'
AD = R / 'addestra'
BANCA = T / 's08' / 'banca_2026-10-04_171547.json.gz'
CASI = ['urgenda', 'neubauer', 'future-generations', 'klimaseniorinnen', 'cig-parere-clima', 'idh-oc-32-25']
CIECHI = ['cieco_doppio_2026-10-03.json', 'campione_cieco_doppio_2026-10-02.json']   # + ogni training/cieco_*.json
CJK = re.compile('[぀-ヿ㐀-鿿가-힯]')
TARGET = (r'.*language_model\.layers\.\d+\.(self_attn\.(q_proj|k_proj|v_proj|o_proj)'
          r'|linear_attn\.(in_proj_qkv|in_proj_z|out_proj)|mlp\.(gate_proj|up_proj|down_proj))')
FINE_PENSIERO = '\n</think>\n\n'


# ── utilita' ────────────────────────────────────────────────────────────────────────────────────────────────────────

def jl(f):
    """righe di un file jsonl o jsonl.gz; una riga troncata (lavoro interrotto) si salta"""
    f = pathlib.Path(f)
    out = []
    if not f.exists():
        return out
    with (gzip.open if f.suffix == '.gz' else open)(f, 'rt', encoding='utf-8') as h:
        for x in h:
            try:
                out.append(json.loads(x))
            except ValueError:
                pass
    return out


def scrivi_jl(f, righe):
    f = pathlib.Path(f)
    f.parent.mkdir(parents=True, exist_ok=True)
    with (gzip.open if f.suffix == '.gz' else open)(f, 'wt', encoding='utf-8') as h:
        for x in righe:
            h.write(json.dumps(x, ensure_ascii=False) + '\n')


def corto(p):
    return str(p).strip().split('.')[-1]


def spazi(t):
    return ' '.join(str(t or '').split())


def esito_principio(x):
    """si / no / incerto. «nessuno» e' un no (ragionamento.esito3 lo conta come incerto: per i «si» non cambia nulla)"""
    x = spazi(x).lower()
    if x in ('si', 'sì', 'yes', 'true'):
        return 'si'
    if x in ('no', 'nessuno', 'false', 'non'):
        return 'no'
    return 'incerto'


def come_lista(v):
    if isinstance(v, str):
        try:
            v = ast.literal_eval(v)
        except (ValueError, SyntaxError):
            return None
    return list(v) if isinstance(v, (list, tuple, set)) else None


# ── 1. l'insieme: risposte del 9B, giudizio del team, filtro, piegature ─────────────────────────────────────────────────

class Costruttore:
    """Costruisce `dati.jsonl.gz`: una riga per ogni riga giudicata (691) con la risposta ragionata del 9B, il giudizio del
    team (solo per scegliere e per misurare), l'esito del filtro e la piegatura. La domanda (`prompt`) si copia dalla
    richiesta RRL di sempre e si scrive solo per le righe utili."""

    def __init__(self, esiti, richieste, uscita, piegature=4, seme=20261005, quota_scartate=0.5, max_cjk=2):
        self.max_cjk = max_cjk
        self.esiti = pathlib.Path(esiti)
        self.richieste = pathlib.Path(richieste)
        self.uscita = pathlib.Path(uscita)
        self.piegature = piegature
        self.seme = seme
        self.quota_scartate = quota_scartate
        import ragionamento as RG
        self.RG = RG
        self.insieme = json.load(open(RG.INSIEME, encoding='utf-8'))
        self.verita = json.load(open(RG.VERITA, encoding='utf-8'))

    def team(self):
        """{id: {'esito', 'principi'}} dalla fotografia della banca dati del 04/10, per le sole righe dell'insieme.
        Stessa regola di ragionamento.fase_insieme; si controlla che coincida con verita.json (che legge `misure`)."""
        banca = json.load(gzip.open(BANCA, 'rt', encoding='utf-8'))
        out, diversi = {}, 0
        for k in self.insieme:
            x = banca[k]
            lu = x.get('luglio') or {}
            vp = come_lista(x.get('validato_principi')) if x.get('validato_principi') is not None else None
            out[k] = {'esito': x.get('esito') or lu.get('esito') or None,
                      'principi': sorted({corto(p) for p in vp if str(p).strip()}) if vp is not None else None}
            v = self.verita[k]
            if out[k]['esito'] != v['esito'] or out[k]['principi'] != v['principi']:
                diversi += 1
        print(f'giudizi dalla fotografia: {len(out)} righe, {diversi} diverse da verita.json')
        return out

    def esclusi(self):
        """id del campione cieco (mai in addestramento): cieco_doppio, campione_cieco_doppio e ogni training/cieco_*.json"""
        files = {T / n for n in CIECHI} | set(T.glob('cieco_*.json')) | set((T / 'misure').glob('cieco_*.json'))
        testo = ''.join(f.read_text(encoding='utf-8') for f in files if f.exists())
        return {k for k in self.insieme if k in testo}, sorted(f.name for f in files if f.exists())

    def validi(self, caso):
        return {corto(q['id']) for q in self.RG.caso_conf(caso)['semantic_queries']}

    def valuta(self, x, team, validi):
        """(utile, motivo) di una risposta del 9B contro il giudizio del team. Vedi la docstring del modulo."""
        if x is None:
            return False, 'nessuna risposta'
        if x.get('fine') != 'stop':
            return False, 'troncata'
        j = self.RG.json_risposta(x.get('testo'))
        if not isinstance(j, dict):
            return False, 'non e\' JSON'
        if not spazi(x.get('ragionamento')):
            return False, 'senza ragionamento'
        if CJK.search(str(x.get('testo'))):
            return False, 'ideogrammi nella risposta'
        if len(CJK.findall(str(x.get('ragionamento')))) > self.max_cjk:
            return False, 'ideogrammi nel ragionamento'
        cita = esito_principio((j.get('cita_il_caso') or {}).get('esito')) if isinstance(j.get('cita_il_caso'), dict) else None
        pr = {}
        for y in j.get('principi') or []:
            if isinstance(y, dict):
                pr[corto(y.get('principio'))] = esito_principio(y.get('esito'))
        if set(pr) != validi:
            return False, 'principi incompleti'
        si = {p for p, e in pr.items() if e == 'si'}
        if team['esito'] == 'scartata':
            if cita == 'no' and not si:
                return True, 'scartata: no a tutto'
            return False, 'scartata ma il modello dice si\''
        if team['esito'] != 'confermata' or team['principi'] is None:
            return False, 'senza giudizio sui principi'
        if not set(team['principi']) <= validi | {'nessuno', 'altro'}:
            return False, 'principio del team fuori caso'
        if cita != 'si':
            return False, 'confermata ma cita non e\' si\''
        if any(e == 'incerto' for e in pr.values()):
            return False, 'confermata con incerti'
        ts = set(team['principi']) - {'nessuno', 'altro'}
        if si != ts:
            return False, 'principi diversi dal team'
        if bool(spazi(j.get('altro'))) != ('altro' in team['principi']):
            return False, 'altro diverso dal team'
        return True, 'confermata: principi uguali al team'

    def assegna_piegature(self, ids):
        """gruppi per atto: ogni atto (document_id) in una sola piegatura; si riempie sempre la piu' vuota"""
        atti = collections.defaultdict(list)
        for k in ids:
            atti[self.insieme[k]['document_id']].append(k)
        rng = random.Random(self.seme)
        ordine = sorted(atti, key=lambda a: (-len(atti[a]), rng.random()))
        peso = [0] * self.piegature
        piega = {}
        for a in ordine:
            p = min(range(self.piegature), key=lambda i: (peso[i], rng.random()))
            peso[p] += len(atti[a])
            for k in atti[a]:
                piega[k] = p
        return piega

    def costruisci(self):
        team = self.team()
        cieco, files = self.esclusi()
        risposte = {x['id']: x for x in jl(self.esiti)}
        piega = self.assegna_piegature(sorted(self.insieme))
        prompt = {x['id']: x['testo'] for x in jl(self.richieste) if x['id'] in self.insieme}
        righe, motivi = [], collections.Counter()
        for k in sorted(self.insieme):
            ins = self.insieme[k]
            validi = self.validi(ins['caso'])
            x = risposte.get(k)
            utile, motivo = self.valuta(x, team[k], validi)
            if team[k]['esito'] == 'riclassificata':
                utile, motivo = False, 'riclassificata (significato ambiguo)'
            if k in cieco:
                utile, motivo = False, 'campione cieco'
            motivi[(team[k]['esito'], motivo)] += 1
            righe.append({'id': k, 'caso': ins['caso'], 'atto': ins['document_id'], 'gruppo': ins['gruppo'],
                          'piega': piega[k], 'esito_team': team[k]['esito'], 'principi_team': team[k]['principi'],
                          'validi': sorted(validi), 'ha_risposta': x is not None, 'utile': utile, 'motivo': motivo,
                          'token': int(x['token']) if x and x.get('token') else None,
                          'token_domanda': int(x['prompt_token']) if x and x.get('prompt_token') else None,
                          'risposta': x.get('testo') if x and utile else None,
                          'ragionamento': x.get('ragionamento') if x and utile else None,
                          'prompt': prompt.get(k) if utile else None})
        self.limita_scartate(righe)
        scrivi_jl(self.uscita, righe)
        self.stampa(righe, motivi, files, len(cieco))

    def limita_scartate(self, righe):
        """le scartate tenute sono al massimo quota x le confermate tenute (scelta fissa col seme: stesse righe a ogni giro)"""
        conf = [r for r in righe if r['utile'] and r['esito_team'] == 'confermata']
        sc = [r for r in righe if r['utile'] and r['esito_team'] == 'scartata']
        massimo = int(self.quota_scartate * len(conf))
        random.Random(self.seme).shuffle(sc)
        for r in sc[massimo:]:
            r.update(utile=False, motivo='scartata oltre la quota', risposta=None, ragionamento=None, prompt=None)

    def stampa(self, righe, motivi, files, n_cieco):
        utili = [r for r in righe if r['utile']]
        print(f'righe giudicate: {len(righe)} | con risposta del 9B: {sum(r["ha_risposta"] for r in righe)} | UTILI: {len(utili)}')
        print('campione cieco escluso:', n_cieco, 'righe', files)
        for (e, m), n in sorted(motivi.items(), key=lambda t: (str(t[0][0]), -t[1])):
            print(f'  team {e}: {m}: {n}')
        for p in range(self.piegature):
            ut = [r for r in utili if r['piega'] == p]
            tutte = [r for r in righe if r['piega'] == p]
            print(f'  piegatura {p}: righe {len(tutte)} (atti {len({r["atto"] for r in tutte})}), utili {len(ut)}, '
                  f'conferme {sum(r["esito_team"] == "confermata" for r in ut)}')
        print('uscita:', self.uscita)


# ── 2. addestramento LoRA (ReCaS, 1 GPU) ────────────────────────────────────────────────────────────────────────────────

class Addestratore:
    """LoRA su Qwen3.5-9B (o sul modellino della prova secca) sul ragionamento + risposta. La perdita e' solo sui token
    della risposta del modello (ragionamento, «</think>» e JSON); la domanda e' contesto."""

    def __init__(self, pesi, dati, tokenizzatore=None, rango=16, lr=1e-4, epoche=3, accumulo=8, max_token=28000,
                 seme=20261005, dtype='bfloat16', prova=False):
        import torch
        self.torch = torch
        self.pesi = pathlib.Path(pesi)
        self.dati = jl(dati)
        self.tokenizzatore = tokenizzatore or pesi
        self.rango, self.lr, self.epoche, self.accumulo = rango, lr, epoche, accumulo
        self.max_token = max_token
        self.seme = seme
        self.dtype = getattr(torch, dtype)
        self.prova = prova                           # prova secca: sequenze corte, nessuna scelta di memoria
        self.dev = 'cuda' if torch.cuda.is_available() else 'cpu'
        self._tok = None

    @property
    def tok(self):
        if self._tok is None:
            from transformers import AutoTokenizer
            self._tok = AutoTokenizer.from_pretrained(str(self.tokenizzatore))
        return self._tok

    def token(self, r):
        """(token della domanda, token della risposta) di una riga utile. La domanda e' quella che vede vLLM col ragionamento
        acceso (`<|im_start|>assistant\\n<think>\\n` in fondo); la risposta e' ragionamento + chiusura + JSON + fine turno."""
        dom = self.tok.apply_chat_template([{'role': 'user', 'content': r['prompt']}], tokenize=False,
                                           add_generation_prompt=True, enable_thinking=True)
        ris = r['ragionamento'].strip() + FINE_PENSIERO + r['risposta'].strip() + '<|im_end|>'
        a = self.tok(dom, add_special_tokens=False)['input_ids']
        b = self.tok(ris, add_special_tokens=False)['input_ids']
        if self.prova:                               # solo per la prova secca: ultime 400 della domanda, prime 96 della risposta
            a, b = a[-400:], b[:96]
        return a, b

    def esempi(self, piega):
        """righe utili fuori dalla piegatura (piega = None: tutte, per l'adattatore finale)"""
        sel = [r for r in self.dati if r['utile'] and (piega is None or r['piega'] != piega)]
        if self.prova:
            sel = sel[:4]
        out, troppo = [], 0
        for r in sel:
            a, b = self.token(r)
            if len(a) + len(b) > self.max_token:
                troppo += 1
                continue
            out.append({'id': r['id'], 'dom': a, 'ris': b})
        print(f'esempi: {len(out)} (piegatura tenuta fuori: {piega}); scartati per lunghezza > {self.max_token}: {troppo}', flush=True)
        return out

    def modello(self):
        from peft import LoraConfig, get_peft_model
        from transformers import AutoModelForImageTextToText
        torch = self.torch
        torch.manual_seed(self.seme)
        m = AutoModelForImageTextToText.from_pretrained(str(self.pesi), dtype=self.dtype).to(self.dev)
        m.config.use_cache = False
        m = get_peft_model(m, LoraConfig(r=self.rango, lora_alpha=2 * self.rango, lora_dropout=0.0 if self.prova else 0.05,
                                         target_modules=TARGET))
        if not self.prova:
            m.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
            m.enable_input_require_grads()
        m.print_trainable_parameters()
        return m

    @staticmethod
    def _ce(testa, h, t):
        return __import__('torch').nn.functional.cross_entropy(testa(h).float(), t, reduction='sum')

    def perdita(self, m, e, pezzo=1024):
        """media sui token della risposta. I logits (248.000 voci per token) si calcolano solo sulla risposta e a pezzi di
        `pezzo` token, ciascuno ricalcolato nel passo indietro: tutti insieme, su 8.000 token, occuperebbero circa 20 GB."""
        torch = self.torch
        from torch.utils.checkpoint import checkpoint
        dentro = m.base_model.model                                  # Qwen3_5ForConditionalGeneration (sotto peft)
        ids = torch.tensor([e['dom'] + e['ris']], device=self.dev)
        n, d = ids.shape[1], len(e['dom'])
        with torch.autocast(self.dev, dtype=torch.bfloat16, enabled=(self.dev == 'cuda')):
            h = dentro.model(input_ids=ids).last_hidden_state[0, d - 1:n - 1]    # la posizione p predice il token p + 1
            bersaglio = ids[0, d:]
            somma = 0.0
            for i in range(0, len(bersaglio), pezzo):
                somma = somma + checkpoint(self._ce, dentro.lm_head, h[i:i + pezzo], bersaglio[i:i + pezzo], use_reentrant=False)
        return somma / len(bersaglio)

    def fumo(self, uscita, lunghezze=(28000, 22000, 16000, 10000)):
        """Un passo avanti-indietro con la sequenza piu' lunga che entra: dice quale `max_token` usare e quanti token al
        secondo. Scrive `uscita` (json). La domanda si accorcia dall'inizio, la risposta resta."""
        torch = self.torch
        ut = [r for r in self.dati if r['utile']]
        r = max(ut, key=lambda r: (r['token'] or 0))
        a, b = self.token(r)
        b = b[:7000]
        m = self.modello()
        m.train()                                   # senza train() il controllo dei punti di ripristino (checkpoint) non agisce
        for L in lunghezze:
            e = {'dom': a[-max(L - len(b), 1000):], 'ris': b}
            esito = self._un_passo(m, e, L)
            if esito:
                print('FUMO OK', esito, flush=True)
                json.dump(esito, open(uscita, 'w'))
                return True
        print('FUMO: nessuna lunghezza entra', flush=True)
        return False

    def _un_passo(self, m, e, L):
        torch = self.torch
        try:
            torch.cuda.reset_peak_memory_stats()
            t0 = time.time()
            self.perdita(m, e).backward()
            torch.cuda.synchronize()
            dt = time.time() - t0
            n = len(e['dom']) + len(e['ris'])
            return {'max_token': L, 'token_sequenza': n, 'secondi': round(dt, 1), 'token_al_secondo': round(n / dt),
                    'picco_GiB': round(torch.cuda.max_memory_allocated() / 2 ** 30, 1)}
        except torch.cuda.OutOfMemoryError as ex:
            print(f'FUMO: memoria finita a {L} token ({str(ex).splitlines()[0][:160]}), provo piu\' corto', flush=True)
        m.zero_grad(set_to_none=True)
        import gc
        gc.collect()
        torch.cuda.empty_cache()
        return None

    def addestra(self, piega, uscita):
        """addestra e scrive l'adattatore (solo i pesi LoRA) in `uscita`"""
        torch = self.torch
        es = self.esempi(piega)
        if not es:
            raise SystemExit('nessun esempio')
        m = self.modello()
        par = [p for p in m.parameters() if p.requires_grad]
        opt = torch.optim.AdamW(par, lr=self.lr, weight_decay=0.0)
        passi = math.ceil(len(es) / self.accumulo) * self.epoche
        sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda i: min(1.0, (i + 1) / max(1, passi // 20)) *
                                                  0.5 * (1 + math.cos(math.pi * min(1.0, i / max(1, passi)))))
        rng = random.Random(self.seme)
        t0, fatti = time.time(), 0
        m.train()
        for ep in range(self.epoche):
            rng.shuffle(es)
            somma = 0.0
            for i, e in enumerate(es):
                L = self.perdita(m, e)
                (L / self.accumulo).backward()
                somma += L.item()
                fatti += len(e['dom']) + len(e['ris'])
                if (i + 1) % self.accumulo == 0 or i + 1 == len(es):
                    torch.nn.utils.clip_grad_norm_(par, 1.0)
                    opt.step()
                    sched.step()
                    opt.zero_grad(set_to_none=True)
                if (i + 1) % 10 == 0:
                    print(f'  epoca {ep + 1} esempio {i + 1}/{len(es)} perdita media {somma / (i + 1):.4f} '
                          f'{fatti / (time.time() - t0):.0f} token/s', flush=True)
            print(f'epoca {ep + 1}/{self.epoche}: perdita {somma / len(es):.4f}, {time.time() - t0:.0f} s', flush=True)
        from peft import get_peft_model_state_dict
        stato = {k: v.detach().cpu() for k, v in get_peft_model_state_dict(m).items()}
        pathlib.Path(uscita).parent.mkdir(parents=True, exist_ok=True)
        torch.save({'pesi': stato, 'rango': self.rango, 'alpha': 2 * self.rango, 'esempi': [e['id'] for e in es],
                    'piega_tenuta_fuori': piega, 'epoche': self.epoche, 'lr': self.lr}, uscita)
        print('adattatore scritto:', uscita, f'({len(stato)} tensori)', flush=True)
        return m


# ── 3. fusione dell'adattatore nei pesi originali ───────────────────────────────────────────────────────────────────────

class Fonditore:
    """Somma W += (alpha / r) B A ai pesi del checkpoint ORIGINALE, tensore per tensore, e riscrive le stesse cartelle di
    file (stessi nomi dei tensori, stesso config): vLLM lo legge come ha letto il 9B di base."""

    def __init__(self, pesi, adattatore, uscita):
        self.pesi, self.adattatore, self.uscita = pathlib.Path(pesi), pathlib.Path(adattatore), pathlib.Path(uscita)

    def fondi(self):
        import torch
        from safetensors.torch import load_file, save_file
        ad = torch.load(self.adattatore, map_location='cpu')
        A, B = {}, {}
        for k, v in ad['pesi'].items():
            m = k.replace('base_model.model.', '', 1)
            if '.lora_A.' in m:
                A[m.split('.lora_A.')[0]] = v
            elif '.lora_B.' in m:
                B[m.split('.lora_B.')[0]] = v
        scala = ad['alpha'] / ad['rango']
        dev = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.uscita.mkdir(parents=True, exist_ok=True)
        for f in self.pesi.iterdir():
            if f.is_file() and f.suffix != '.safetensors':
                shutil.copy(f, self.uscita / f.name)
        usati = 0
        for f in sorted(self.pesi.glob('*.safetensors')):
            t = load_file(str(f))
            for nome in list(t):
                mod = nome[:-len('.weight')] if nome.endswith('.weight') else None
                if mod in A:
                    w = t[nome].to(dev).float() + scala * (B[mod].to(dev).float() @ A[mod].to(dev).float())
                    t[nome] = w.to(t[nome].dtype).cpu()
                    usati += 1
            save_file(t, str(self.uscita / f.name), metadata={'format': 'pt'})
        if usati != len(A):
            raise SystemExit(f'fusione incompleta: {usati} tensori sommati su {len(A)} moduli LoRA')
        print(f'fuso: {usati} tensori in {self.uscita}', flush=True)


# ── 4. le richieste della piegatura (per il corridore) ─────────────────────────────────────────────────────────────────

def richieste_piegatura(dati, richieste, piega, uscita):
    """le richieste RRL delle righe della piegatura (TUTTE: la prova non e' filtrata), da dare a ragionamento_corri.py"""
    ids = {r['id'] for r in jl(dati) if r['piega'] == piega}
    rq = [x for x in jl(richieste) if x['id'] in ids]
    scrivi_jl(uscita, rq)
    print(f'piegatura {piega}: {len(rq)} richieste su {len(ids)} righe -> {uscita}')


# ── 5. le misure ───────────────────────────────────────────────────────────────────────────────────────────────────────

class Misuratore:
    """F1, precisione e richiamo sui principi (insieme dei «si'») del modello addestrato e del 9B di base contro il team,
    con le funzioni di tools/ragionamento.py; confronto appaiato sulle stesse righe e intervallo al 95% ricampionando
    gli atti. Riferimenti: 9B di base 0,686 (tutte) e 0,704 (137); T01 0,526 (tutte) e 0,498 (137)."""

    def __init__(self, base, addestrato, dati, uscita):
        import ragionamento as RG
        self.RG = RG
        self.base, self.addestrato = pathlib.Path(base), pathlib.Path(addestrato)
        self.dati = {r['id']: r for r in jl(dati)}
        self.uscita = pathlib.Path(uscita)
        self.V = json.load(open(RG.VERITA, encoding='utf-8'))
        self.ins = json.load(open(RG.INSIEME, encoding='utf-8'))
        self.validi = {k: set(r['validi']) | {'altro', 'nessuno'} for k, r in self.dati.items()}
        self.atti = {k: r['atto'] for k, r in self.dati.items()}

    def estrai(self, f):
        """{id: {'cita', 'principi' (i si'), 'principi_incerti'}} da un file di esiti nel formato del lavoro RRL"""
        out = {}
        for x in jl(f):
            j = self.RG.json_risposta(x.get('testo'))
            if not isinstance(j, dict) or x['id'] not in self.dati:
                continue
            pr = {corto(y.get('principio')): esito_principio(y.get('esito')) for y in j.get('principi') or [] if isinstance(y, dict)}
            ci = j.get('cita_il_caso') if isinstance(j.get('cita_il_caso'), dict) else {}
            out[x['id']] = {'cita': esito_principio(ci.get('esito')) if ci else None,
                            'principi': {p for p, e in pr.items() if e == 'si'} | ({'altro'} if spazi(j.get('altro')) else set()),
                            'incerti': {p for p, e in pr.items() if e == 'incerto'}}
        return out

    def principi(self, E, righe):
        tp = fp = fn = 0
        for k in righe:
            v = self.V[k]
            if k not in E or v['esito'] != 'confermata' or v['principi'] is None or not set(v['principi']) <= self.validi[k]:
                continue
            ts = set(v['principi']) - {'nessuno', 'altro'}
            ms = E[k]['principi'] - {'nessuno', 'altro'}
            tp += len(ts & ms)
            fp += len(ms - ts)
            fn += len(ts - ms)
        return self.RG.prf(tp, fp, fn)

    def cita(self, E, righe):
        c = collections.Counter((self.V[k]['esito'], E[k]['cita']) for k in righe
                                if k in E and self.V[k]['esito'] in ('confermata', 'scartata'))
        sc = c[('scartata', 'si')] + c[('scartata', 'no')] + c[('scartata', 'incerto')]
        return {'confermata_si': c[('confermata', 'si')], 'confermata_non_si': c[('confermata', 'no')] + c[('confermata', 'incerto')],
                'scartata_si': c[('scartata', 'si')], 'scartata_non_si': sc - c[('scartata', 'si')],
                'falsi_positivi_sulle_scartate': round(c[('scartata', 'si')] / sc, 3) if sc else None}

    def misura(self):
        B, F = self.estrai(self.base), self.estrai(self.addestrato)
        tutte = sorted(self.ins)
        giuria = [k for k in tutte if self.ins[k]['gruppo'] == 'giuria137']
        appaiate = [k for k in tutte if k in B and k in F]
        M = {'righe_base': len(B), 'righe_addestrato': len(F), 'appaiate': len(appaiate), 'insiemi': {}}
        for nome, righe in (('appaiate', appaiate), ('giuria137 (appaiate)', [k for k in giuria if k in B and k in F]),
                            ('addestrato, tutte le sue', tutte)):
            M['insiemi'][nome] = {'addestrato': {'principi': self.principi(F, righe), 'cita': self.cita(F, righe)},
                                  'base': {'principi': self.principi(B, righe), 'cita': self.cita(B, righe)}}
        M['differenza_f1_appaiate'] = self.RG.bootstrap_diff_f1(self.V, F, B, appaiate, self.validi, self.atti)
        M['differenza_f1_giuria137'] = self.RG.bootstrap_diff_f1(self.V, F, B, [k for k in giuria if k in B and k in F],
                                                                self.validi, self.atti)
        M['per_piegatura'] = {}
        for p in sorted({r['piega'] for r in self.dati.values()}):
            rr = [k for k in appaiate if self.dati[k]['piega'] == p]
            M['per_piegatura'][p] = {'righe': len(rr), 'addestrato': self.principi(F, rr)['f1'], 'base': self.principi(B, rr)['f1']}
        # le righe di prova che erano anche «utili» non sono mai servite: si guarda quanto il modello le ritrova
        M['ritrovate_utili'] = sum(1 for k in appaiate if self.dati[k]['utile'] and F[k]['principi'] == B[k]['principi'])
        json.dump(M, open(self.uscita, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
        for nome, v in M['insiemi'].items():
            for chi in ('base', 'addestrato'):
                p = v[chi]['principi']
                print(f'{nome:28s} {chi:11s} P {p["precisione"]} R {p["richiamo"]} F1 {p["f1"]}  | cita: {v[chi]["cita"]}')
        print('differenza di F1 (addestrato - base), appaiate, per atto:', M['differenza_f1_appaiate'],
              '| giuria137:', M['differenza_f1_giuria137'])
        print('per piegatura:', M['per_piegatura'])
        print('scritto', self.uscita)


# ── 6. la prova secca: modello minuscolo, stessa architettura ─────────────────────────────────────────────────────────

def prova_secca(dati, tokenizzatore, cartella):
    """Sul Mac, senza il 9B. Costruisce un Qwen3.5 minuscolo (4 strati, 3 lineari e 1 completo, come il 9B in piccolo) con
    il vero vocabolario, scrive il checkpoint con save_pretrained, addestra DUE esempi veri (accorciati), fonde l'adattatore
    nel checkpoint e controlla che il modello fuso e quello con l'adattatore diano gli stessi logit."""
    import torch
    from transformers import AutoModelForImageTextToText, Qwen3_5Config
    cartella = pathlib.Path(cartella)
    if cartella.exists():
        shutil.rmtree(cartella)
    torch.manual_seed(1)
    cfg = Qwen3_5Config(
        text_config=dict(vocab_size=248320, hidden_size=64, intermediate_size=128, num_hidden_layers=4, num_attention_heads=4,
                         num_key_value_heads=2, head_dim=16, linear_key_head_dim=16, linear_value_head_dim=16,
                         linear_num_key_heads=2, linear_num_value_heads=4, full_attention_interval=4,
                         layer_types=['linear_attention'] * 3 + ['full_attention'], max_position_embeddings=4096,
                         rope_parameters={'rope_type': 'default', 'rope_theta': 10000, 'partial_rotary_factor': 0.5,
                                          'mrope_section': [2, 1, 1], 'mrope_interleaved': True}),
        vision_config=dict(depth=1, hidden_size=32, intermediate_size=64, num_heads=2, out_hidden_size=64))
    AutoModelForImageTextToText.from_config(cfg).save_pretrained(str(cartella / 'originale'))
    for f in pathlib.Path(tokenizzatore).iterdir():
        if f.name in ('tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja', 'vocab.json', 'merges.txt'):
            shutil.copy(f, cartella / 'originale' / f.name)
    originale = cartella / 'originale'
    ad = Addestratore(originale, dati, rango=4, epoche=1, accumulo=2, dtype='float32', prova=True)
    m = ad.addestra(None, cartella / 'adattatore.pt')
    Fonditore(originale, cartella / 'adattatore.pt', cartella / 'fuso').fondi()
    ids = torch.tensor([ad.token(next(r for r in ad.dati if r['utile']))[0][-60:]])
    m.eval()
    with torch.no_grad():
        con_adattatore = m(input_ids=ids).logits
        fuso = AutoModelForImageTextToText.from_pretrained(str(cartella / 'fuso'), dtype=torch.float32)(input_ids=ids).logits
        base = AutoModelForImageTextToText.from_pretrained(str(originale), dtype=torch.float32)(input_ids=ids).logits
    d_fuso = (con_adattatore - fuso).abs().max().item()
    d_base = (con_adattatore - base).abs().max().item()
    print(f'PROVA SECCA: differenza massima adattatore/fuso {d_fuso:.2e}; adattatore/base {d_base:.2e}')
    if not (d_fuso < 1e-3 and d_base > 10 * d_fuso):
        raise SystemExit('PROVA SECCA FALLITA: il fuso non coincide con l\'adattatore (o l\'adattatore non ha cambiato nulla)')
    print('PROVA SECCA OK')


# ── riga di comando ───────────────────────────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('fase', choices=['costruisci', 'prova-secca', 'fumo', 'addestra', 'fondi', 'richieste', 'misura'])
    ap.add_argument('--esiti', default=str(AD / 'q9_rrl.jsonl'), help='costruisci: le risposte del 9B (RRL) da ReCaS')
    ap.add_argument('--richieste', default=str(R / 'richieste' / 'rrl.jsonl.gz'))
    ap.add_argument('--dati', default=str(AD / 'dati.jsonl.gz'))
    ap.add_argument('--piegature', type=int, default=4)
    ap.add_argument('--quota-scartate', type=float, default=0.5)
    ap.add_argument('--max-cjk', type=int, default=2, help='ideogrammi tollerati nel ragionamento (nella risposta: zero)')
    ap.add_argument('--pesi', help='cartella dei pesi (Qwen3.5-9B) o del modellino')
    ap.add_argument('--tokenizzatore', help='se diverso da --pesi')
    ap.add_argument('--piega', type=int, default=None, help='la piegatura tenuta fuori')
    ap.add_argument('--finale', action='store_true', help='addestra su TUTTE le righe utili (nessuna tenuta fuori)')
    ap.add_argument('--adattatore', help='file dell\'adattatore (uscita di addestra, ingresso di fondi)')
    ap.add_argument('--uscita')
    ap.add_argument('--rango', type=int, default=16)
    ap.add_argument('--lr', type=float, default=1e-4)
    ap.add_argument('--epoche', type=int, default=3)
    ap.add_argument('--accumulo', type=int, default=8)
    ap.add_argument('--max-token', type=int, default=28000)
    ap.add_argument('--base', default=str(AD / 'q9_rrl.jsonl'))
    ap.add_argument('--addestrato', help='misura: gli esiti del modello addestrato (tutte le piegature insieme)')
    a = ap.parse_args()
    if a.fase == 'costruisci':
        Costruttore(a.esiti, a.richieste, a.uscita or a.dati, a.piegature, quota_scartate=a.quota_scartate,
                   max_cjk=a.max_cjk).costruisci()
    elif a.fase == 'prova-secca':
        prova_secca(a.dati, a.tokenizzatore or a.pesi, a.uscita or '/tmp/prova_secca_ragiona')
    elif a.fase == 'richieste':
        richieste_piegatura(a.dati, a.richieste, a.piega, a.uscita)
    elif a.fase == 'fondi':
        Fonditore(a.pesi, a.adattatore, a.uscita).fondi()
    elif a.fase == 'misura':
        Misuratore(a.base, a.addestrato, a.dati, a.uscita or AD / 'misura.json').misura()
    else:
        ad = Addestratore(a.pesi, a.dati, a.tokenizzatore, a.rango, a.lr, a.epoche, a.accumulo, a.max_token)
        if a.fase == 'fumo':
            sys.exit(0 if ad.fumo(a.uscita) else 1)
        ad.addestra(None if a.finale else a.piega, a.adattatore or a.uscita)   # lo script del lavoro passa --adattatore


if __name__ == '__main__':
    main()
