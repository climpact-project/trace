"""L11: L05 CON LE PAGINE ATTORNO INTERE (04/10/2026, il PI: «sistemare tutto con urgenza estrema ogni buco trovato»).

   Il buco (controllo dei tagli del 04/10): L05 riceveva ogni pagina attorno tagliata a 3.500 caratteri
   (TAGLIO_VICINA di tools/leggi_ripresa.py). Le note stanno in fondo alla pagina e la domanda dice «GUARDA LE NOTE»:
   5.371 pagine tagliate su 1.837 righe non giudicate; nel campione il 35% perde testo rilevante e circa il 10% la
   nota che attribuisce la frase.

   L11 = L05 con le stesse istruzioni, carattere per carattere, e le stesse pagine attorno (R10), ma ogni pagina INTERA
   fino al tetto dell'indice delle pagine (12.000 caratteri, tools/indice_pagine.py). Si parte dalle righe R10 gia'
   lette dal ciclo delle cinque letture (training/principi/<caso>_ripresa_righe_<serie>cinque.jsonl) e si cambia SOLO
   il testo delle pagine attorno: contesto, paragrafi, punteggi e scelta delle pagine restano quelli.

   IL TETTO DEL CONTESTO: la domanda deve stare nel contesto di vLLM (65.536 token) lasciando la risposta (8.000) e,
   se possibile, il tentativo col tetto alto (16.000). I token si stimano dai caratteri con il rapporto MISURATO sulle
   letture L05 del 03/10 (prompt_token di vLLM contro la lunghezza della domanda, percentile peggiore per caso, fase
   `misura`). Se la domanda intera non ci sta, si ricade (regola fissa, `stringi`): le pagine piu' lunghe si accorciano
   un passo alla volta tenendo testa e coda della pagina (le note stanno in fondo) attorno a un segno «[...]», fino a
   starci; mai sotto i 3.500 caratteri di L05. Ogni riga dice nel campo `l11` come sono state date le pagine.

   Le righe da rileggere: quelle del ciclo delle cinque letture ancora senza `esito` in banca dati (si ricontrolla) con
   almeno una pagina attorno tagliata. Si leggono per prime quelle che hanno perso piu' testo.

   Il motore e' quello del ciclo delle cinque letture (`tools/cinque_letture.py`, importato, non toccato): blocchi di
   circa 50 minuti nelle code di DeepSeek su ReCaS, ripartibili fra un lavoro e l'altro (stato in training/l11/), con lo
   stesso lettore gia' su ReCaS (tools/leggi_ripresa.py leggi --aggiungi-letture: le letture valide gia' prese con la
   stessa domanda si tengono). Si cambiano solo cartella, etichette (<serie>l11), casi e numerazione dei blocchi (da
   cinque_9901). LA PRECEDENZA DELLE CODE: un blocco di circa 22 minuti per coda, messo solo se la coda e' vuota; i
   blocchi di S06 e D04 (cinque_9xx) nella stessa coda passano prima per ordine alfabetico: aspettano al massimo un
   blocco. Il confronto dei decisori (training/decisori/recas/guida.sh) e' fermo fino alla fine.

   Fasi:
     misura    rapporto caratteri/token per caso dalle letture L05 del 03/10, e controllo che la domanda rifatta qui sia
               identica (SHA-256) a quella letta da DeepSeek
     righe     training/l11/righe_<caso>.txt (righe non giudicate con pagine tagliate, per testo perso decrescente)
     prepara   training/principi/<caso>_ripresa_righe_<serie>l11.jsonl (pagine intere, tetto del contesto)
     letture   il ciclo dei blocchi (riprende da training/l11/stato.json)
     stato     come va
"""
import argparse, collections, gzip, hashlib, json, pathlib, statistics, subprocess, sys, time

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
import cinque_letture as cl  # noqa: E402

ETICHETTA = 'l11'
C11 = cl.T/'l11'
PRIMO_BLOCCO = 9900            # il primo blocco si chiama cinque_9901 (cinque 001-, S06 901-, D04 961-): nella stessa coda
                               # i server prendono gli script in ordine alfabetico, e cinque_9901 viene dopo cinque_9xx (S06, D04)
BLOCCO_S = 22 * 60             # blocchi di circa 22 minuti (04/10: i blocchi di S06 aspettano al massimo un blocco)
TETTO_PAGINA = 12000           # il tetto dell'indice delle pagine (tools/indice_pagine.py)
TAGLIO_L05 = 3500              # TAGLIO_VICINA di L05: sotto non si scende mai
CONTESTO, RISPOSTA, ALTO, MARGINE = 65536, 8000, 16000, 512
OBIETTIVO_TOKEN = CONTESTO - ALTO - MARGINE        # 49.024: ci sta anche il tentativo col tetto alto
MASSIMO_TOKEN = CONTESTO - RISPOSTA - MARGINE      # 57.024: oltre, la lettura non si puo' fare
SEGNO = '\n[...]\n'
STIMA_L11 = 2.6                # s per lettura per server prima della prima misura (L05 R10: 1,85; pagine piu' lunghe)


def serie(caso):
    return cl.serie(caso)


def etichetta_l11(caso):
    return f'{serie(caso)}{ETICHETTA}'


def file_righe_l05(caso):
    return cl.P/f'{caso}_ripresa_righe_{serie(caso)}cinque.jsonl'


def file_righe_l11(caso):
    return cl.P/f'{caso}_ripresa_righe_{etichetta_l11(caso)}.jsonl'


def giornale(testo):
    subprocess.run([sys.executable, str(QUI/'tools'/'giornale.py'), 'evento', '--nome', 'rilettura_l11', '--testo', testo],
                   capture_output=True)


def casi():
    f = C11/'casi.txt'
    return f.read_text(encoding='utf-8').split() if f.exists() else list(cl.CASI)


def configura():
    C11.mkdir(parents=True, exist_ok=True)
    cl.C, cl.LOG, cl.CASI = C11, C11/'ciclo.log', casi()
    cl.etichetta_l05, cl.giornale = etichetta_l11, giornale
    cl.OBIETTIVO_S = cl.PRIMO_S = BLOCCO_S
    cl.file_tipo = lambda caso, et=None: C11/f'nessun_tipo_{caso}.jsonl'    # L11 non legge il tipo


# ── la domanda, rifatta come la fa tools/leggi_ripresa.py leggi (controllata con lo SHA-256 in `misura`) ──────────

_cache = {}


def parti_fisse(caso):
    if caso in _cache:
        return _cache[caso]
    import os
    import yaml
    vecchia = os.environ.get('TRACE_SONDE')
    os.environ['TRACE_SONDE'] = serie(caso)
    try:
        import sonde as S
        conf = yaml.safe_load(open(S.file_caso(caso), encoding='utf-8'))
        principi = '\n'.join(f"- {s['id']}: {' '.join(s['titolo'].split())}. {' '.join(s['testo'].split())}" for s in conf['semantic_queries'])
        nome_caso = conf.get('nome') or caso
        testo_f = S.file_fascicolo(caso).read_text(encoding='utf-8')
    finally:
        if vecchia is None:
            os.environ.pop('TRACE_SONDE', None)
        else:
            os.environ['TRACE_SONDE'] = vecchia
    fascicolo = ("\nQui sotto il FASCICOLO del caso, scritto per il gruppo di ricerca: serve a sapere che cosa ha deciso e con "
                 "quali paragrafi. Le domande sono quelle in fondo.\n\n" + testo_f + "\n\n========== FINE DEL FASCICOLO ==========\n")
    _cache[caso] = (principi, nome_caso, fascicolo)
    return _cache[caso]


def domanda(caso, r):
    import leggi_ripresa as LR
    principi, nome_caso, fascicolo = parti_fisse(caso)
    aiuto = ''
    if r['paragrafi']:
        aiuto = (f"La citazione indica i paragrafi {', '.join(r['paragrafi'])}; secondo la mappa dei paragrafi reggono i "
                 f"principi: {', '.join(r['principi_paragrafi']) or 'nessuno (fatti o procedura)'}.\n")
    vic = '\n\n'.join(f"--- PAGINA {v['pagina']} ---\n{v['testo']}" for v in r['vicine']) or '(nessuna pagina vicina proposta)'
    return LR.MODULO.format(fascicolo=fascicolo, nome_caso=nome_caso, principi=principi, case_name=r.get('case_name') or '',
                            tipo_atto=r.get('tipo_atto') or 'atto', data=(r.get('data') or 's.d.')[:10], document_id=r['document_id'],
                            forma=r.get('forma') or nome_caso, contesto=r['contesto'], aiuto_paragrafi=aiuto, vicine=vic)


# ── misura ──────────────────────────────────────────────────────────────────────────────────────────────────────────

def fase_misura(a):
    configura()
    out = {}
    for caso in cl.CASI:
        righe = cl.per_id(file_righe_l05(caso))
        ratio, uguali, diverse = [], 0, 0
        n = 0
        with open(cl.file_l05(caso, f'{serie(caso)}cinque'), encoding='utf-8') as h:
            for l in h:
                try:
                    x = json.loads(l)
                except ValueError:
                    continue
                r = righe.get(x['id'])
                if not r:
                    continue
                t = domanda(caso, r); sha = hashlib.sha256(t.encode('utf-8')).hexdigest()
                for c in x.get('chiamate') or []:
                    if not isinstance(c, dict) or not c.get('prompt_token'):
                        continue
                    if c.get('istruzioni_sha256') == sha:
                        uguali += 1; ratio.append(len(t) / c['prompt_token'])
                    else:
                        diverse += 1
                n += 1
                if n >= a.campione:
                    break
        ratio.sort()
        out[caso] = {'letture_uguali': uguali, 'letture_diverse': diverse, 'caratteri_per_token_min': round(ratio[0], 3) if ratio else None,
                     'p01': round(ratio[max(0, len(ratio) // 100)], 3) if ratio else None,
                     'mediana': round(statistics.median(ratio), 3) if ratio else None}
        cl.scrivi_log(f'misura {caso}: {out[caso]}')
    json.dump(out, open(C11/'misura_token.json', 'w'), indent=1)


def caratteri_per_token(caso):
    m = json.load(open(C11/'misura_token.json'))[caso]
    return m['caratteri_per_token_min']          # il caso peggiore misurato: la stima dei token e' per eccesso


# ── righe ───────────────────────────────────────────────────────────────────────────────────────────────────────────

def pagine_intere(ids):
    testi = {}
    with gzip.open(QUI/'index'/'pagine'/'pagine.jsonl.gz', 'rt', encoding='utf-8') as f:
        for l in f:
            x = json.loads(l)
            if x['id'] in ids:
                testi[x['id']] = x['testo']
    return testi


def fase_righe(a):
    from google.cloud import firestore
    configura()
    cl.CASI = list(cl.CASI)
    db = firestore.Client(project='climpact-drp')
    tagliate = {}
    serve = set()
    righe_l05 = {}
    for caso in cl.CASI:
        tenere = set((cl.T/'cinque'/f'righe_{caso}.txt').read_text(encoding='utf-8').split())
        righe_l05[caso] = {i: x for i, x in cl.per_id(file_righe_l05(caso)).items() if i in tenere}
        for i, x in righe_l05[caso].items():
            for v in x['vicine']:
                if len(v['testo']) >= TAGLIO_L05:
                    serve.add(f"{x['document_id']}#p{v['pagina']}")
    testi = pagine_intere(serve)
    con = []
    conti = {}
    for caso in cl.CASI:
        persi = {}
        for i, x in righe_l05[caso].items():
            p = sum(len(testi.get(f"{x['document_id']}#p{v['pagina']}", '')[:TETTO_PAGINA]) - len(v['testo'])
                    for v in x['vicine'] if len(v['testo']) >= TAGLIO_L05)
            if p > 0:
                persi[i] = p
        # ancora senza esito in banca dati (le giudicate non si toccano)
        ids = list(persi)
        giudicate = set()
        for k in range(0, len(ids), 300):
            for d in db.get_all([db.collection('corpus_rows').document(i) for i in ids[k:k + 300]], field_paths=['esito']):
                if not d.exists or (d.to_dict() or {}).get('esito'):
                    giudicate.add(d.id)
        ordine = sorted((i for i in persi if i not in giudicate), key=lambda i: -persi[i])
        (C11/f'righe_{caso}.txt').write_text('\n'.join(ordine) + ('\n' if ordine else ''), encoding='utf-8')
        conti[caso] = {'righe_tagliate': len(persi), 'giudicate_nel_frattempo': len(giudicate), 'da_rileggere': len(ordine),
                       'caratteri_persi': sum(persi[i] for i in ordine)}
        if ordine:
            con.append(caso)
        cl.scrivi_log(f'righe L11 {caso}: {conti[caso]}')
    (C11/'casi.txt').write_text(' '.join(con) + '\n', encoding='utf-8')
    json.dump(conti, open(C11/'conti_righe.json', 'w'), indent=1)
    cl.scrivi_log(f"righe L11 in tutto: {sum(c['da_rileggere'] for c in conti.values())}")


# ── prepara ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def accorcia(t, n):
    """testa e coda della pagina (le note stanno in fondo), n caratteri in tutto"""
    if len(t) <= n:
        return t
    testa = n * 2 // 5
    return t[:testa] + SEGNO + t[len(t) - (n - testa - len(SEGNO)):]


def stringi(caso, r, interi, rapporto):
    """le pagine intere; se la domanda non sta nel contesto, le piu' lunghe si accorciano un passo alla volta"""
    tetto = TETTO_PAGINA
    while True:
        r['vicine'] = [dict(v, testo=accorcia(interi[k], tetto)) for k, v in enumerate(r['vicine'])]
        token = len(domanda(caso, r)) / rapporto
        if token <= OBIETTIVO_TOKEN or tetto <= TAGLIO_L05:
            return tetto, round(token)
        tetto = max(TAGLIO_L05, tetto - 500)


def fase_prepara(a):
    configura()
    tot = collections.Counter()
    for caso in cl.CASI:
        ids = cl.righe_di(caso)
        r05 = cl.per_id(file_righe_l05(caso))
        serve = {f"{r05[i]['document_id']}#p{v['pagina']}" for i in ids for v in r05[i]['vicine']}
        testi = pagine_intere(serve)
        rapporto = caratteri_per_token(caso)
        c = collections.Counter(); token = []
        with open(file_righe_l11(caso), 'w', encoding='utf-8') as f:
            for i in ids:
                r = json.loads(json.dumps(r05[i]))
                interi = []
                for v in r['vicine']:
                    pid = f"{r['document_id']}#p{v['pagina']}"
                    if pid not in testi:
                        raise SystemExit(f'{caso} {i}: pagina {pid} non trovata nell\'indice')
                    t = testi[pid][:TETTO_PAGINA]
                    if not t.startswith(v['testo'][:200]):
                        raise SystemExit(f'{caso} {i}: la pagina {pid} non comincia come quella letta da L05')
                    interi.append(t)
                tetto, tk = stringi(caso, r, interi, rapporto)
                r['l11'] = {'pagine': 'intere' if tetto == TETTO_PAGINA else f'testa e coda, {tetto} caratteri al massimo',
                            'token_stimati': tk, 'tetto_pagina': tetto,
                            'caratteri_vicine': sum(len(v['testo']) for v in r['vicine'])}
                c['intere' if tetto == TETTO_PAGINA else 'accorciate'] += 1
                if tk > MASSIMO_TOKEN:
                    c['oltre il contesto'] += 1
                token.append(tk)
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
        tot.update(c)
        cl.scrivi_log(f'prepara L11 {caso}: {dict(c)}, token stimati mediana {statistics.median(token):.0f}, massimo {max(token)} '
                      f'-> {file_righe_l11(caso).name}')
    cl.scrivi_log(f'prepara L11: {dict(tot)}')


# ── letture ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def maestri():
    return {'tipo': {c: {} for c in cl.CASI}, 'l05': {c: cl.per_id(cl.file_l05(c)) for c in cl.CASI}}


def s06_ha_finito_le_letture():
    s = cl.T/'s06'
    return (s/'passi'/'letture').exists() or 'FERMO' in ((s/'ciclo_s06.log').read_text(encoding='utf-8') if (s/'ciclo_s06.log').exists() else '')


def code_vuote(code):
    out = cl.r('for q in ' + ' '.join(code) + '; do echo "$q $(ls ~/trace/chat/$q/*.sh 2>/dev/null | wc -l)"; done', check=False)
    return {l.split()[0] for l in out.strip().split('\n') if len(l.split()) == 2 and l.split()[1] == '0'}


def fase_letture(a):
    configura()
    st = cl.carica_stato()
    if st['n'] < PRIMO_BLOCCO and not st['blocchi']:
        st['n'] = PRIMO_BLOCCO; st['stima'] = {'tipo': 1.2, 'l05': STIMA_L11}
        rem = cl.r('cd ~/trace && sha256sum tools/leggi_ripresa.py tools/chiamata_deepseek.py tools/freni.py tools/sonde.py', check=False)
        cl.scrivi_log('lettore su ReCaS (impronte, non si rimanda):\n' + rem.strip())
        cl.r('mkdir -p ~/trace/training/cinque/fatti ~/trace/training/cinque/vivo')
        cl.salva_stato(st)
    M = maestri()
    # 04/10, 06:40 (il coordinatore, per il PI): non si aspetta S06. Si comincia subito, un blocco per coda e solo in una
    # coda vuota; i blocchi di S06 e D04 nella stessa coda passano prima (ordine alfabetico, vedi PRIMO_BLOCCO).
    cl.scrivi_log('comincio subito (blocchi da circa 22 minuti, uno per coda, solo in coda vuota)')
    ultimo_giro = 0
    while True:
        cl.controlla(st, M)
        fare, finite = cl.da_fare(st, M)
        in_volo = [n for n, b in st['blocchi'].items() if b['stato'] in ('inviato', 'iniziato')]
        if not in_volo and not fare['l05']:
            break
        code = cl.CODE[:2] + (cl.CODE[2:] if cl.ricambio_acceso() else [])
        attesa = {b['coda'] for b in st['blocchi'].values() if b['stato'] == 'inviato'}
        if fare['l05']:
            vuote = code_vuote(code)
            for q in code:
                if q in vuote and q not in attesa and fare['l05']:
                    if cl.nuovo_blocco(st, M, q, lettore='l05'):
                        attesa.add(q)
                    fare, finite = cl.da_fare(st, M)
        if time.time() - ultimo_giro > 1800:
            tot = sum(len(cl.righe_di(c)) for c in cl.CASI)
            resto = sum(n for v in fare['l05'].values() for _, n in v)
            cl.scrivi_log(f'avanzamento L11: {finite["l05"]}/{tot} righe con {cl.K} letture; letture ancora da mandare {resto}; '
                          f's/lettura {st["stima"]["l05"]}')
            ultimo_giro = time.time()
        time.sleep(120)
    fare, finite = cl.da_fare(st, M)
    rinunce = [f'{c}:{i}' for c in cl.CASI for i in cl.righe_di(c) if cl.valide(M['l05'][c].get(i)) < cl.K]
    json.dump(rinunce, open(C11/'senza_cinque_letture.json', 'w'), indent=1)
    cl.scrivi_log(f'letture L11 finite: {finite["l05"]} righe complete, {len(rinunce)} senza {cl.K} letture valide')
    (C11/'FINITO').write_text(time.strftime('%d/%m %H:%M') + '\n', encoding='utf-8')
    giornale(f'L11: letture finite, {finite["l05"]} righe complete')


def fase_stato(a):
    configura()
    st = cl.carica_stato(); M = maestri()
    fare, finite = cl.da_fare(st, M)
    print(json.dumps({'finite': finite['l05'], 'da_fare': sum(len(v) for v in fare['l05'].values()),
                      'letture_da_mandare': sum(n for v in fare['l05'].values() for _, n in v), 'stima': st['stima'],
                      'blocchi': collections.Counter(b['stato'] for b in st['blocchi'].values()),
                      'misure': st['misure'][-6:]}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    import giornale as G
    G.avvia()
    ap = argparse.ArgumentParser()
    ap.add_argument('fase', choices=['misura', 'righe', 'prepara', 'letture', 'stato'])
    ap.add_argument('--campione', type=int, default=400)
    a = ap.parse_args()
    {'misura': fase_misura, 'righe': fase_righe, 'prepara': fase_prepara, 'letture': fase_letture, 'stato': fase_stato}[a.fase](a)
