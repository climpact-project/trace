"""IL CORRIDORE DELLE RICHIESTE DI tools/ragionamento.py (04/10/2026). Gira su ReCaS, dentro un lavoro che serve un
modello con vLLM (DeepSeek V4 Flash nelle code coda-ds*, Qwen3.8-27B nella coda del lavoro dei precedenti).

Richieste (jsonl.gz, una per riga):
  semplice  {"id", "chiave", "gruppo", "testo", "tetto"}: una chiamata
  cammino   {"id", "chiave", "modo": "cammino", "citazione", "pagine": [{"pagina", "testo", "leggibile"}], "prefisso", "passo"}:
            le pagine attorno lette dalla pagina della citazione verso l'esterno, prima indietro poi avanti, una chiamata
            per pagina; in una direzione ci si ferma dopo due «no» di fila (o alla fine della finestra o dell'atto); le
            pagine illeggibili (freno 1) si saltano e si scrivono.
Le richieste dello stesso atto vanno in fila (campo «gruppo»): vLLM riusa il prefisso in cache (istruzioni, regole, atto).
Una chiamata non supera il contesto: il tetto della risposta scende a contesto - domanda - margine (con il tokenizzatore
di DeepSeek se dato; altrimenti stima a 3 caratteri per token). Riprende da dove era (chiavi gia' scritte). Dopo
--minuti non comincia richieste nuove; scrive FINITO quando non ne resta nessuna.
"""
import argparse, concurrent.futures as cf, gzip, json, pathlib, re, sys, threading, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import chiamata_deepseek as CD  # noqa: E402

CORPI = {'deepseek-high': {'chat_template_kwargs': {'thinking': True, 'reasoning_effort': 'high'}},
         'deepseek-low': {'chat_template_kwargs': {'thinking': True, 'reasoning_effort': 'low'}},
         'qwen-pensa': {'chat_template_kwargs': {'enable_thinking': True}},
         'qwen-nopensa': {'chat_template_kwargs': {'enable_thinking': False}}}


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


def esito_json(t):
    t = str(t or '')
    if '</think>' in t:                 # un server senza separatore del ragionamento: si guarda solo dopo il pensiero
        t = t.rsplit('</think>', 1)[1]
    t = re.sub(r'^```(?:json)?\s*|\s*```$', '', t.strip())
    i = t.find('{')
    while i >= 0:
        try:
            return json.JSONDecoder().raw_decode(t[i:])[0]
        except ValueError:
            i = t.find('{', i + 1)
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--richieste', required=True); ap.add_argument('--uscita', required=True)
    ap.add_argument('--base-url', required=True); ap.add_argument('--chiave-file', required=True)
    ap.add_argument('--modello', required=True); ap.add_argument('--ragionamento', default='deepseek-high', choices=sorted(CORPI))
    ap.add_argument('--contesto', type=int, default=65536); ap.add_argument('--paralleli', type=int, default=16)
    ap.add_argument('--minuti', type=float, default=0); ap.add_argument('--tokenizer', default='')
    ap.add_argument('--immagini', default='', help='cartella delle immagini delle pagine (richieste con «immagini»)')
    ap.add_argument('--logprobs', action='store_true', help='il punteggio del verdetto dalle probabilita\' dei token (reranker)')
    ap.add_argument('--prefissi', default='', help='scala: i testi comuni (json.gz {chiave: testo})')
    ap.add_argument('--atti', default='', help='scala: gli atti interi (json.gz {documento: testo}), al posto di @@ATTO@@')
    a = ap.parse_args()
    from openai import OpenAI
    cli = OpenAI(api_key=pathlib.Path(a.chiave_file).read_text().strip(), base_url=a.base_url, timeout=3600)
    CD.CONTESTO = a.contesto
    tok = None
    if a.tokenizer:
        from tokenizers import Tokenizer
        tok = Tokenizer.from_file(a.tokenizer)
    def ntok(t):
        return len(tok.encode(t).ids) + 64 if tok else len(t) // 3 + 64
    corpo = CORPI[a.ragionamento]
    fatte = {x.get('chiave') for x in jl(a.uscita)}
    # LA SCALA (tools/scala.py): una richiesta con «varianti» (sforzo e tetto) e «k» letture diventa una chiamata per variante e
    # per lettura, in fila: le letture della stessa domanda partono insieme e si dividono il prefisso in cache
    tutte = []
    for x in jl(a.richieste):
        if 'varianti' in x:
            for iv, (v, par) in enumerate(x['varianti'].items()):
                for k in range(x.get('k') or 1):
                    tutte.append({**x, 'chiave': f"{v}|{x['chiave']}|{k}", 'variante': v, 'lettura': k, 'sforzo': par['sforzo'],
                                  'tetto': par['tetto'], '_ordine': (x['chiave'], iv, k)})
        else:
            tutte.append({**x, '_ordine': (x['chiave'], 0, 0)})
    rq = [x for x in tutte if x['chiave'] not in fatte]
    rq.sort(key=lambda x: (x.get('priorita', 0), x.get('gruppo') or '', x['_ordine']))
    PREF, ATTI = {}, {}
    if a.prefissi:
        with gzip.open(a.prefissi, 'rt', encoding='utf-8') as h:
            PREF.update(json.load(h))
    if a.atti:
        with gzip.open(a.atti, 'rt', encoding='utf-8') as h:
            ATTI.update(json.load(h))

    def testo_di(r):
        t = PREF.get(r.get('prefisso'), '') + r['testo'] if r.get('prefisso') and r.get('modo') != 'cammino' else r['testo']
        if r.get('atto') and '@@ATTO@@' in t:
            t = t.replace('@@ATTO@@', ATTI[r['atto']])
        return t
    print(f'{len(rq)} richieste da fare ({len(fatte)} gia\' fatte), {a.modello}, {a.ragionamento}, contesto {a.contesto}', flush=True)
    t0 = time.time(); lock = threading.Lock(); stop = threading.Event()

    def verdetti(lp):
        """IL PUNTEGGIO DAL MODELLO, NON DETTO DAL MODELLO (il PI, 04/10/2026): per ogni punto dell'uscita in cui comincia il
        valore di «esito» (dopo `"esito": "`), le probabilita' dei primi token di «si», «no», «incerto» fra i 20 piu'
        probabili, rinormalizzate. In ordine di uscita: il corridore non sa a quale principio appartengono; lo dice
        l'ordine dei verdetti nel JSON finale (si tengono gli ultimi, quelli del JSON finale)."""
        import math
        out, testo = [], ''
        for t in lp or []:
            if re.search(r'"esito"\s*:\s*"$', testo):
                p = {'si': 0.0, 'no': 0.0, 'incerto': 0.0}
                for alt in (getattr(t, 'top_logprobs', None) or []):
                    k = alt.token.strip().strip('"').lower()
                    v = math.exp(alt.logprob)
                    if k and ('sì'.startswith(k) or 'si'.startswith(k) or k in ('sì', 'si')):
                        p['si'] += v
                    elif k and 'no'.startswith(k):
                        p['no'] += v
                    elif k and 'incerto'.startswith(k[:3]):
                        p['incerto'] += v
                z = sum(p.values())
                out.append({kk: round(v / z, 4) for kk, v in p.items()} if z else None)
            testo = (testo + t.token)[-200:]
        return out

    def una_con_immagini(testo, tetto, nomi, logprobs=False):
        """come CD.chiama (tre tentativi sulle risposte vuote), con le immagini nel messaggio (formato OpenAI di vLLM) e, se
        chiesto, le probabilita' dei token dei verdetti"""
        import base64
        n = ntok(testo) + 1500 * len(nomi)
        cap = min(tetto, a.contesto - n - 512)
        if cap < 2000:
            return {'testo': '', 'errore': f'domanda troppo lunga: {n} token su {a.contesto}'}
        parti = [{'type': 'text', 'text': testo}]
        for nome in nomi:
            f = pathlib.Path(a.immagini) / nome
            if not f.exists():
                return {'testo': '', 'errore': f'immagine mancante: {nome}'}
            parti.append({'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + base64.b64encode(f.read_bytes()).decode()}})
        s0 = time.time(); ultimo = {}
        for prova in range(3):
            try:
                r = cli.chat.completions.create(model=a.modello, messages=[{'role': 'user', 'content': parti if nomi else testo}],
                                                max_tokens=cap, extra_body=corpo, **({'logprobs': True, 'top_logprobs': 20} if logprobs else {}))
            except Exception as e:
                ultimo = {'testo': '', 'errore': repr(e)[:300]}; time.sleep(5 * (prova + 1)); continue
            m = r.choices[0].message
            ultimo = {'testo': m.content or '', 'ragionamento': CD._ragionamento(m), 'token': r.usage.completion_tokens,
                      'prompt_token': r.usage.prompt_tokens, 'fine': r.choices[0].finish_reason}
            if logprobs:
                lp = getattr(r.choices[0], 'logprobs', None)
                ultimo['verdetti_logprob'] = verdetti(getattr(lp, 'content', None) if lp else None)
            if ultimo['testo'].strip():
                break
            dal = CD.json_finale(ultimo['ragionamento'])
            if dal:
                ultimo['testo'] = dal; ultimo['dal_ragionamento'] = True; break
        ultimo['secondi'] = round(time.time() - s0, 1); ultimo['tentativi'] = prova + 1
        return ultimo

    def una(testo, tetto, sforzo=None):
        n = ntok(testo)
        cap = min(tetto, a.contesto - n - 512)
        if cap < 2000:
            return {'testo': '', 'errore': f'domanda troppo lunga: {n} token su {a.contesto}', 'prompt_token_stima': n}
        s = time.time()
        c = {'chat_template_kwargs': {'thinking': True, 'reasoning_effort': sforzo}} if sforzo else corpo
        x = CD.chiama(cli, a.modello, testo, c, tetto=cap)
        rag = x.get('ragionamento') or ''
        if sforzo:                      # la scala: il ragionamento puo' essere lunghissimo; si tiene la lunghezza e la coda
            rag = {'caratteri': len(rag), 'coda': rag[-3000:]}
        return {'testo': x['testo'], 'ragionamento': rag, 'token': x.get('token'),
                'prompt_token': x['chiamata'].get('prompt_token'), 'secondi': round(time.time() - s, 1), 'chiamata': x['chiamata']}

    def fai(r):
        if stop.is_set() or (a.minuti and time.time() - t0 > a.minuti * 60):
            stop.set(); return None
        s = time.time()
        if r.get('variante'):
            x = una(testo_di(r), r['tetto'], r['sforzo'])
            out = {'id': r['id'], 'chiave': r['chiave'], 'variante': r['variante'], 'tipo': r.get('tipo'), 'lettura': r['lettura'], **x}
        elif r.get('modo') != 'cammino':
            x = una_con_immagini(r['testo'], r.get('tetto') or 8000, r.get('immagini') or [], a.logprobs) if (r.get('immagini') or a.logprobs) \
                else una(r['testo'], r.get('tetto') or 8000)
            out = {'id': r['id'], 'chiave': r['chiave'], **{k: r[k] for k in ('principio',) if k in r}, **x}
        else:
            pg = {p['pagina']: p for p in r['pagine']}
            passi, fermate = [], {}
            for verso, nome in ((-1, 'prima'), (1, 'dopo')):
                no_fila, prec = 0, ''
                fermate[nome] = 'fine della finestra'
                for k in range(1, 11):
                    n = r['citazione'] + verso * k
                    if n not in pg:
                        if n < 1 or n > max(list(pg) + [r['citazione']]):
                            fermate[nome] = f'fine dell\'atto a p. {n}'; break
                        continue
                    if not pg[n].get('leggibile', True):
                        passi.append({'pagina': n, 'illeggibile': True}); continue
                    testo = r['prefisso'] + '\n\n' + r['passo'].format(precedente=prec, pagina=n, verso=nome, distanza=k, testo=pg[n]['testo'])
                    x = una_con_immagini(testo, r.get('tetto') or 5000, [], True) if a.logprobs else una(testo, r.get('tetto') or 5000)
                    j = esito_json(x.get('testo'))
                    es = str(j.get('esito', '')).strip().lower()
                    passi.append({'pagina': n, 'verso': nome, **{kk: (v[:6000] if kk == 'ragionamento' else v) for kk, v in x.items() if kk != 'chiamata'}})
                    no_fila = no_fila + 1 if es == 'no' else 0
                    prec = (f'PASSO PRECEDENTE IN QUESTA DIREZIONE: pagina {n}: {es or "senza risposta"}. '
                            f'{str(j.get("ragione") or "")[:400]}\n')
                    if no_fila == 2:
                        fermate[nome] = f'p. {n}: due «no» di fila'; break
            out = {'id': r['id'], 'chiave': r['chiave'], 'passi': passi, 'fermate': fermate,
                   'token': sum(p.get('token') or 0 for p in passi), 'secondi': round(time.time() - s, 1)}
        with lock:
            with open(a.uscita, 'a', encoding='utf-8') as f:
                f.write(json.dumps(out, ensure_ascii=False) + '\n')
        return out

    n = 0
    with cf.ThreadPoolExecutor(a.paralleli) as ex:
        for o in ex.map(fai, rq):
            if o is not None:
                n += 1
                if n % 10 == 0:
                    print(f'  {n}/{len(rq)} [{time.time() - t0:.0f}s]', flush=True)
    resto = len(rq) - n
    print(f'fatte {n} in {time.time() - t0:.0f}s; ' + ('FINITO' if resto == 0 else f'TEMPO: ne restano {resto}'), flush=True)


if __name__ == '__main__':
    main()
