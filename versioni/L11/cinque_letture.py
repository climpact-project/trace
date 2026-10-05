"""CINQUE LETTURE PER RIGA, IL CICLO DELLE LETTURE (02/10/2026, col si' del PI: «procedi»).

   Rilettura di tutte le righe col nome NON giudicate (senza `esito`), comprese le 793 di S05:
     - tipo: 5 letture (L02 Urgenda, L03 gli altri casi). Dove la riga ha gia' letture fatte con la stessa domanda,
       carattere per carattere (impronta SHA-256 nella lettura), si tengono e si aggiungono le mancanti; le letture del
       tipo in piattaforma fatte col codebook 0.2/0.3 (domanda diversa: oggi 0.4-pilot) non si tengono;
     - L05: 5 letture da capo, sulle pagine attorno scelte con R10 (la domanda cambia con le pagine).
   L04 non si rilegge: R11 prende i principi dalla maggioranza delle letture L05, e la domanda di L04 contiene anche
   lei le pagine attorno (non e' vero che non dipende da R10): le sue letture vecchie non si potrebbero completare.

   Il lavoro va su ReCaS nelle code di DeepSeek (coda-ds2, coda-ds3; coda-ds4 quando il lavoro di ricambio e' acceso),
   a blocchi di circa 50 minuti, uno in attesa per coda, cosi' gli script degli altri passano fra un blocco e l'altro.
   Lo stato sta in training/cinque/stato.json: il ciclo riparte da dove era dopo un riavvio del Mac.

   Fasi (le chiama tools/ciclo_cinque_letture.sh):
     righe     elenco delle righe non giudicate e fotografia delle proposte di oggi (solo lettura della banca dati)
     prepara   le pagine attorno R10 (leggi_ripresa.prepara --regola R10) e i semi del tipo (letture con la stessa domanda)
     letture   il ciclo dei blocchi fino alla fine (riprende da stato.json)
     rapporto  training/cinque/RAPPORTO.md dalle prove a secco di R11
     stato     come va
"""
import argparse, collections, datetime, gzip, hashlib, json, pathlib, subprocess, sys, time
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
T = QUI/'training'; P = T/'principi'; C = T/'cinque'
CASI = ['urgenda', 'neubauer', 'future-generations', 'klimaseniorinnen', 'cig-parere-clima', 'idh-oc-32-25']
K = 5                                  # letture per riga (GIRI-E-DOMANDA.md)
MAX_INVII = 4                          # una riga si manda al massimo 4 volte
CODE = ['coda-ds2', 'coda-ds3', 'coda-ds4']
OBIETTIVO_S = 50 * 60                  # un blocco: circa 50 minuti
PRIMO_S = 30 * 60                      # il primo blocco di ogni lettore e' piu' corto: serve a misurare
STIMA = {'tipo': 1.13, 'l05': 1.9}     # secondi per lettura per server (misura del 02/10; L05 piu' lunga con R10)
PARALLELI = 32
H = '/lustrehome/climpact/trace'
LOG = C/'ciclo.log'


def serie(caso):
    import sonde as S
    return S.SERIE_IN_USO.get(caso, '')


def etichetta_l05(caso):
    return f'{serie(caso)}cinque'


def file_tipo(caso, et='cinque'):
    return T/f'lessicali_{caso}_deepseek_{et}.jsonl'


def file_l05(caso, et=None):
    return P/f'{caso}_ripresa_deepseek_{et or etichetta_l05(caso)}.jsonl'


def scrivi_log(testo):
    C.mkdir(parents=True, exist_ok=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(f"{datetime.datetime.now().strftime('%d/%m %H:%M')} {testo}\n")
    print(testo, flush=True)


def giornale(testo):
    subprocess.run([sys.executable, str(QUI/'tools'/'giornale.py'), 'evento', '--nome', 'ciclo_cinque_letture', '--testo', testo],
                   capture_output=True)


def per_id(f):
    out = {}
    if not pathlib.Path(f).exists():
        return out
    with open(f, encoding='utf-8') as h:
        for l in h:
            try:
                x = json.loads(l)
            except ValueError:
                continue                # una riga troncata (lavoro interrotto a meta' scrittura)
            out[x['id']] = x
    return out


def valide(x):
    from chiamata_deepseek import valida
    return sum(1 for y in (x or {}).get('letture') or [] if valida(y))


# ── ssh ─────────────────────────────────────────────────────────────────────────────────────────────────────────────

def r(cmd, check=True):
    for i in range(30):
        p = subprocess.run(['ssh', '-o', 'ConnectTimeout=30', '-o', 'BatchMode=yes', 'recas', cmd], capture_output=True, text=True)
        if p.returncode != 255:
            if check and p.returncode != 0:
                raise RuntimeError(f'recas: {cmd[:120]}: {p.stderr[:300]}')
            return p.stdout
        time.sleep(60)
    raise RuntimeError('recas irraggiungibile da 30 minuti')


def manda(locale, remoto=None):
    remoto = remoto or str(pathlib.Path(locale).resolve().relative_to(QUI))
    for i in range(30):
        if subprocess.run(['scp', '-q', str(locale), f'recas:trace/{remoto}']).returncode == 0:
            return
        time.sleep(60)
    raise RuntimeError(f'scp fallito: {locale}')


def prendi_n(remoto, locale, righe):
    """il file si prende solo quando ha le righe attese (lezione del 02/10: file presi a meta')"""
    for i in range(60):
        if subprocess.run(['scp', '-q', f'recas:trace/{remoto}', str(locale)]).returncode == 0 \
                and sum(1 for _ in open(locale, 'rb')) == righe:
            return
        time.sleep(30)
    raise RuntimeError(f'{remoto}: non arriva con {righe} righe')


# ── righe ───────────────────────────────────────────────────────────────────────────────────────────────────────────

def fase_righe(a):
    from google.cloud import firestore
    db = firestore.Client(project='climpact-drp')
    C.mkdir(parents=True, exist_ok=True)
    foto = {}
    for caso in CASI:
        ids = []
        for d in db.collection('corpus_rows').where(filter=firestore.FieldFilter('caso_citato', '==', caso)).stream():
            x = d.to_dict()
            if x.get('proposto_rete') not in ('lessicale', 'entrambe') or x.get('esito'):
                continue
            ids.append(d.id)
            foto[d.id] = {k: x.get(k) for k in ('codice', 'proposto_tipo_citazione', 'proposto_principi', 'proposto_confidenza',
                                                 'provenienza')}
            foto[d.id]['pagine_prosegue'] = sorted(v.get('pagina') for v in (x.get('proposto_estensione') or []) if v.get('prosegue'))
        (C/f'righe_{caso}.txt').write_text('\n'.join(sorted(ids)) + '\n', encoding='utf-8')
        scrivi_log(f'righe non giudicate {caso}: {len(ids)}')
    json.dump(foto, open(C/'proposte_prima.json', 'w', encoding='utf-8'), ensure_ascii=False, default=str)
    scrivi_log(f'righe non giudicate in tutto: {len(foto)} (fotografia delle proposte di oggi in proposte_prima.json)')


def righe_di(caso):
    return [l for l in (C/f'righe_{caso}.txt').read_text(encoding='utf-8').split() if l]


# ── prepara ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def fase_prepara(a):
    import statistics
    import leggi_ripresa as LR
    import classifica_lessicali as CL
    from chiamata_deepseek import valida
    for caso in CASI:
        LR.prepara(caso, 'R10', etichetta_l05(caso))
        f = P/f'{caso}_ripresa_righe_{etichetta_l05(caso)}.jsonl'
        r10 = per_id(f)
        tenere = set(righe_di(caso))
        manca = tenere - set(r10)
        if manca:
            # senza contesto (file mancante): non si possono leggere, la proposta di oggi resta; elenco a parte
            (C/f'righe_{caso}.senza_contesto.txt').write_text('\n'.join(sorted(manca)) + '\n', encoding='utf-8')
            (C/f'righe_{caso}.txt').write_text('\n'.join(sorted(tenere - manca)) + '\n', encoding='utf-8')
            scrivi_log(f'ATTENZIONE {caso}: {len(manca)} righe non giudicate senza contesto, escluse (righe_{caso}.senza_contesto.txt)')
            tenere -= manca
        n = [len(r10[i]['vicine']) for i in tenere]
        scrivi_log(f'R10 {caso}: {len(n)} righe, pagine attorno per citazione media {statistics.mean(n):.2f}, massimo {max(n)}')
    # i semi del tipo: le letture valide gia' fatte con la domanda di oggi, carattere per carattere
    cb = CL.codebook()
    for caso in CASI:
        fasc = (QUI/'cited-cases'/f'{caso}-fascicolo.md').read_text(encoding='utf-8')
        righe = {x['id']: x for x in (json.loads(l) for l in open(T/f'lessicali_{caso}_righe.jsonl', encoding='utf-8'))}
        tenere = [i for i in righe_di(caso) if i in righe]
        h = {i: hashlib.sha256(CL.prompt(righe[i], fasc, cb, caso).encode('utf-8')).hexdigest() for i in tenere}
        pool = collections.defaultdict(list); visti = collections.defaultdict(set)
        for f in sorted(T.glob(f'lessicali_{caso}_deepseek*.jsonl')):
            if f.name.endswith('_misure.json') or '_cinque' in f.name or '_cq' in f.name:
                continue
            for l in open(f, encoding='utf-8'):
                try:
                    x = json.loads(l)
                except ValueError:
                    continue
                i = x.get('id')
                if i not in h:
                    continue
                for k, y in enumerate(x.get('letture') or []):
                    c = (x.get('chiamate') or [None] * 99)[k] if k < len(x.get('chiamate') or []) else None
                    if not (valida(y) and isinstance(c, dict) and c.get('istruzioni_sha256') == h[i]):
                        continue
                    rag = ((x.get('ragionamenti') or [])[k:k + 1] or [''])[0]
                    chiave = hashlib.sha256(json.dumps([y, rag], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                    if chiave in visti[i]:
                        continue
                    visti[i].add(chiave)
                    pool[i].append((y, rag, ((x.get('token') or [])[k:k + 1] or [0])[0], c, x.get('data'), x.get('codebook')))
        with open(C/f'semi_tipo_{caso}.jsonl', 'w', encoding='utf-8') as out:
            for i, v in pool.items():
                v = v[:K]
                out.write(json.dumps({'id': i, 'modello': 'DeepSeek-V4-Flash-0731', 'data': v[0][4], 'gruppo': righe[i].get('gruppo'),
                                      'codebook': v[0][5], 'letture': [z[0] for z in v], 'ragionamenti': [z[1] for z in v],
                                      'token': [z[2] for z in v], 'chiamate': [z[3] for z in v], 'semi': True}, ensure_ascii=False) + '\n')
        scrivi_log(f'semi del tipo {caso}: {len(pool)} righe con letture della stessa domanda '
                   f'({sum(min(len(v), K) for v in pool.values())} letture tenute), {len(tenere) - len(pool)} da capo')


# ── letture ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def carica_stato():
    f = C/'stato.json'
    if f.exists():
        return json.loads(f.read_text(encoding='utf-8'))
    return {'blocchi': {}, 'n': 0, 'invii': {}, 'stima': dict(STIMA), 'misure': []}


def salva_stato(st):
    tmp = C/'stato.json.tmp'
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding='utf-8'); tmp.replace(C/'stato.json')


def maestri():
    """le letture raccolte finora: {lettore: {caso: {id: record}}}"""
    return {'tipo': {c: per_id(file_tipo(c)) for c in CASI}, 'l05': {c: per_id(file_l05(c)) for c in CASI}}


def da_fare(st, M):
    """le righe ancora senza K letture valide, non in volo, mandate meno di MAX_INVII volte"""
    in_volo = {(b['lettore'], c, i) for b in st['blocchi'].values() if b['stato'] in ('inviato', 'iniziato')
               for c, ids in b['righe'].items() for i in ids}
    out = {'tipo': collections.OrderedDict(), 'l05': collections.OrderedDict()}
    finite = collections.Counter()
    for lettore in out:
        for caso in CASI:
            for i in righe_di(caso):
                v = valide(M[lettore][caso].get(i))
                if v >= K:
                    finite[lettore] += 1; continue
                if (lettore, caso, i) in in_volo or st['invii'].get(f'{lettore}|{i}', 0) >= MAX_INVII:
                    continue
                out[lettore].setdefault(caso, []).append((i, K - v))
    return out, finite


def semi_tipo(caso):
    return per_id(C/f'semi_tipo_{caso}.jsonl')


def nuovo_blocco(st, M, coda, lettore=None):
    fare, _ = da_fare(st, M)
    resto = {l: sum(n for v in fare[l].values() for _, n in v) * st['stima'][l] for l in fare}
    if lettore is None:
        # il primo blocco di ciascun lettore subito (per misurare), poi quello con piu' lavoro
        mai = [l for l in ('l05', 'tipo') if resto[l] and not any(b['lettore'] == l for b in st['blocchi'].values())]
        lettore = mai[0] if mai else max(resto, key=resto.get)
    if not resto.get(lettore):
        return None
    primo = not any(b['lettore'] == lettore for b in st['blocchi'].values())
    budget = (PRIMO_S if primo else OBIETTIVO_S) / st['stima'][lettore]       # letture nel blocco
    st['n'] += 1
    nome = f'cinque_{st["n"]:03d}'
    righe, letture = collections.OrderedDict(), 0
    for caso, v in fare[lettore].items():
        for i, n in v:
            if letture + n > budget and letture:
                break
            righe.setdefault(caso, []).append(i); letture += n
        if letture >= budget:
            break
    # i file del blocco: identificativi (tipo), righe R10 (L05), semi (le letture valide gia' raccolte)
    d = C/'blocchi'/nome; d.mkdir(parents=True, exist_ok=True)
    righe_semi = {}
    cmd = []
    for caso, ids in righe.items():
        s = serie(caso)
        if lettore == 'tipo':
            sem = semi_tipo(caso)
            ff = d/f'{nome}_{caso}.txt'; ff.write_text('\n'.join(ids) + '\n', encoding='utf-8')
            uscita = d/f'lessicali_{caso}_deepseek_{nome}.jsonl'
            n = 0
            with open(uscita, 'w', encoding='utf-8') as f:
                for i in ids:
                    x = M['tipo'][caso].get(i) or sem.get(i)
                    if x and valide(x):
                        f.write(json.dumps(x, ensure_ascii=False) + '\n'); n += 1
            righe_semi[caso] = n
            manda(ff, f'training/cinque/{ff.name}'); manda(uscita, f'training/{uscita.name}')
            cmd.append(f'TRACE_SONDE= $H/venv/bin/python -u tools/classifica_lessicali.py leggi --caso {caso} --gruppo tutte '
                       f'--letture {K} --aggiungi-letture --etichetta {nome} --solo-id training/cinque/{ff.name} $A >> $C/log/{nome}.log 2>&1')
        else:
            tutte = per_id(P/f'{caso}_ripresa_righe_{etichetta_l05(caso)}.jsonl')
            ff = d/f'{caso}_ripresa_righe_{nome}.jsonl'
            ff.write_text(''.join(json.dumps(tutte[i], ensure_ascii=False) + '\n' for i in ids), encoding='utf-8')
            uscita = d/f'{caso}_ripresa_deepseek_{nome}.jsonl'
            n = 0
            with open(uscita, 'w', encoding='utf-8') as f:
                for i in ids:
                    x = M['l05'][caso].get(i)
                    if x and valide(x):
                        f.write(json.dumps(x, ensure_ascii=False) + '\n'); n += 1
            righe_semi[caso] = n
            manda(ff, f'training/principi/{ff.name}'); manda(uscita, f'training/principi/{uscita.name}')
            cmd.append(f'TRACE_SONDE={s} $H/venv/bin/python -u tools/leggi_ripresa.py leggi --caso {caso} --letture {K} '
                       f'--aggiungi-letture --etichetta {nome} $A >> $C/log/{nome}.log 2>&1')
    uscite = [f'training/lessicali_{c}_deepseek_{nome}.jsonl' if lettore == 'tipo' else f'training/principi/{c}_ripresa_deepseek_{nome}.jsonl'
              for c in righe]
    sh = [f'# CINQUE LETTURE (tools/cinque_letture.py), blocco {nome}: {lettore}, {sum(map(len, righe.values()))} righe, '
          f'circa {letture} letture. Al massimo ~{int(letture * st["stima"][lettore] / 60)} minuti.',
          f'H={H}; C=$H/chat; cd $H; B={nome}', 'CH=$(cat $C/chiave)',
          f'A="--base-url http://127.0.0.1:8000/v1 --chiave-file $C/chiave --modello deepseek-v4-flash --paralleli {PARALLELI}"',
          'mkdir -p training/cinque/fatti training/cinque/vivo',
          '# DeepSeek deve rispondere prima di cominciare (dopo un lavoro che lo ha spento e riacceso)',
          'until curl -s -m 5 -H "Authorization: Bearer $CH" http://127.0.0.1:8000/v1/models | grep -q deepseek; do sleep 30; done',
          'echo "$(date +%s) $(hostname)" > training/cinque/vivo/$B.inizio',
          '( while true; do touch training/cinque/vivo/$B; sleep 60; done ) & BATTITO=$!',
          'trap "kill $BATTITO 2>/dev/null" EXIT',
          *cmd,
          '{ echo "fine $(date +%s)"; for f in ' + ' '.join(uscite) + '; do echo "$f $(wc -l < $f)"; done; } > training/cinque/fatti/$B.tmp '
          '&& mv training/cinque/fatti/$B.tmp training/cinque/fatti/$B.fatto']
    (d/f'{nome}.sh').write_text('\n'.join(sh) + '\n', encoding='utf-8')
    manda(d/f'{nome}.sh', f'chat/{coda}/{nome}.sh.tmp')
    r(f'mv ~/trace/chat/{coda}/{nome}.sh.tmp ~/trace/chat/{coda}/{nome}.sh')
    for caso, ids in righe.items():
        for i in ids:
            st['invii'][f'{lettore}|{i}'] = st['invii'].get(f'{lettore}|{i}', 0) + 1
    st['blocchi'][nome] = {'lettore': lettore, 'coda': coda, 'stato': 'inviato', 'inviato': time.time(), 'righe': righe,
                           'semi': righe_semi, 'letture_previste': letture}
    salva_stato(st)
    scrivi_log(f'{nome} in {coda}: {lettore}, {sum(map(len, righe.values()))} righe ({", ".join(f"{c} {len(v)}" for c, v in righe.items())}), '
               f'{letture} letture, stima {letture * st["stima"][lettore] / 60:.0f} minuti')
    return nome


def unisci(st, nome, M, finito, fine=None):
    """le righe nuove del blocco (dopo i semi) si aggiungono ai file raccolti; vale l'ultima riga di ogni identificativo"""
    b = st['blocchi'][nome]; d = C/'blocchi'/nome
    nuove_letture = 0; righe_scritte = 0
    for caso, ids in b['righe'].items():
        if b['lettore'] == 'tipo':
            remoto, locale, maestro = f'training/lessicali_{caso}_deepseek_{nome}.jsonl', d/f'preso_tipo_{caso}.jsonl', file_tipo(caso)
        else:
            remoto, locale, maestro = f'training/principi/{caso}_ripresa_deepseek_{nome}.jsonl', d/f'preso_l05_{caso}.jsonl', file_l05(caso)
        if finito:
            prendi_n(remoto, locale, finito[remoto])
        else:
            subprocess.run(['scp', '-q', f'recas:trace/{remoto}', str(locale)])
            if not locale.exists():
                continue
        righe = open(locale, encoding='utf-8').read().split('\n')[b['semi'][caso]:]
        buone = []
        for l in righe:
            try:
                x = json.loads(l)
            except ValueError:
                continue
            buone.append(json.dumps(x, ensure_ascii=False) + '\n'); nuove_letture += (x.get('aggiunte') or {}).get('nuove', 0)
            M[b['lettore']][caso][x['id']] = x
        with open(maestro, 'a', encoding='utf-8') as f:
            f.writelines(buone)
        righe_scritte += len(buone)
    return nuove_letture, righe_scritte


def controlla(st, M):
    """i blocchi in volo: finiti, iniziati, morti, fermi in una coda che nessuno serve"""
    fatti = set(r('ls ~/trace/training/cinque/fatti 2>/dev/null', check=False).split())
    vivi = {}
    for l in r('cd ~/trace/training/cinque/vivo 2>/dev/null && for f in *; do [ -e "$f" ] && echo "$f $(date -r "$f" +%s)"; done', check=False).split('\n'):
        k, _, v = l.strip().rpartition(' ')
        if k and v.isdigit():
            vivi[k] = int(v)
    adesso = int(r('date +%s').strip())
    in_coda = {}
    for coda in CODE:
        for f in r(f'ls ~/trace/chat/{coda} 2>/dev/null', check=False).split():
            if f.startswith('cinque_') and f.endswith('.sh'):
                in_coda[f[:-3]] = coda
    for nome, b in st['blocchi'].items():
        if b['stato'] in ('finito', 'morto'):
            continue
        if f'{nome}.fatto' in fatti:
            testo = r(f'cat ~/trace/training/cinque/fatti/{nome}.fatto')
            fine = int(testo.split('\n')[0].split()[1])
            attesi = {x.split()[0]: int(x.split()[1]) for x in testo.split('\n')[1:] if x.strip()}
            inizio = int(r(f'cat ~/trace/training/cinque/vivo/{nome}.inizio').split()[0])
            nuove, righe = unisci(st, nome, M, attesi)
            sec = fine - inizio
            b.update(stato='finito', secondi=sec, letture_nuove=nuove)
            if nuove:
                misura = sec / nuove
                st['misure'].append({'blocco': nome, 'lettore': b['lettore'], 'letture': nuove, 'secondi': sec, 's_per_lettura': round(misura, 3)})
                ultime = [m['s_per_lettura'] for m in st['misure'] if m['lettore'] == b['lettore']][-3:]
                st['stima'][b['lettore']] = round(sum(ultime) / len(ultime), 3)
            scrivi_log(f'{nome} finito ({b["lettore"]}, {b["coda"]}): {righe} righe, {nuove} letture nuove in {sec / 60:.0f} minuti, '
                       f'{(sec / nuove if nuove else 0):.2f} s per lettura; stima ora {st["stima"][b["lettore"]]} s')
            if len([m for m in st['misure'] if m['lettore'] == b['lettore']]) == 1:
                giornale(f'cinque letture, primo blocco {b["lettore"]}: {(sec / nuove if nuove else 0):.2f} s per lettura per server')
            salva_stato(st); continue
        if f'{nome}.inizio' in vivi and b['stato'] == 'inviato':
            b['stato'] = 'iniziato'; b['iniziato'] = time.time(); salva_stato(st)
            scrivi_log(f'{nome} iniziato ({b["coda"]})')
        if b['stato'] == 'iniziato' and adesso - vivi.get(nome, adesso) > 15 * 60:
            nuove, righe = unisci(st, nome, M, None)
            b.update(stato='morto', letture_nuove=nuove); salva_stato(st)
            scrivi_log(f'{nome} MORTO (nessun battito da 15 minuti): prese {righe} righe; le altre tornano da fare')
            giornale(f'cinque letture: blocco {nome} interrotto, righe rimandate')
            continue
        if b['stato'] == 'inviato' and nome not in in_coda and f'{nome}.inizio' not in vivi:
            # preso da un server ma non ancora iniziato (aspetta DeepSeek): si aspetta, ma non piu' di 3 ore
            if time.time() - b['inviato'] > 3 * 3600:
                b.update(stato='morto', letture_nuove=0); salva_stato(st)
                scrivi_log(f'{nome} MORTO: preso da un server ma mai iniziato in 3 ore; le righe tornano da fare')
            continue
    return in_coda


def ricambio_acceso():
    out = r("condor_q -run -af ClusterId Cmd 2>/dev/null", check=False)
    return any(l.strip().endswith('avvio5.sh') for l in out.split('\n'))


def fase_letture(a):
    st = carica_stato(); M = maestri()
    if st['n'] == 0:
        for f in ('tools/classifica_lessicali.py', 'tools/leggi_ripresa.py', 'tools/leggi_l04.py', 'tools/chiamata_deepseek.py',
                  'tools/freni.py', 'tools/sonde.py', 'tools/giornale.py', 'tools/giudica_llm.py', 'codebook/citazioni.yaml'):
            manda(QUI/f, f)
        for caso in CASI:
            manda(T/f'lessicali_{caso}_righe.jsonl', f'training/lessicali_{caso}_righe.jsonl')
        r('mkdir -p ~/trace/training/cinque/fatti ~/trace/training/cinque/vivo')
        scrivi_log('strumenti e righe su ReCaS')
    ultimo_giro = 0
    while True:
        in_coda = controlla(st, M)
        fare, finite = da_fare(st, M)
        in_volo = [n for n, b in st['blocchi'].items() if b['stato'] in ('inviato', 'iniziato')]
        if not in_volo and not any(fare[l] for l in fare):
            break
        # un blocco in attesa per coda; coda-ds4 solo col lavoro di ricambio acceso
        code = CODE[:2] + (CODE[2:] if ricambio_acceso() else [])
        attesa = {b['coda'] for n, b in st['blocchi'].items() if b['stato'] == 'inviato'}
        # un blocco fermo da piu' di 20 minuti in una coda che nessuno serve passa a una coda libera
        for n, b in st['blocchi'].items():
            if b['stato'] == 'inviato' and n in in_coda and time.time() - b['inviato'] > 20 * 60:
                libere = [q for q in code if q not in attesa and q != b['coda']]
                if libere:
                    p = subprocess.run(['ssh', '-o', 'BatchMode=yes', 'recas', f'mv ~/trace/chat/{b["coda"]}/{n}.sh ~/trace/chat/{libere[0]}/{n}.sh'])
                    if p.returncode == 0:
                        scrivi_log(f'{n} spostato da {b["coda"]} a {libere[0]} (fermo da 20 minuti)')
                        attesa.discard(b['coda']); attesa.add(libere[0]); b['coda'] = libere[0]; b['inviato'] = time.time(); salva_stato(st)
        for q in code:
            if q not in attesa and any(fare[l] for l in fare):
                if nuovo_blocco(st, M, q):
                    attesa.add(q)
                fare, finite = da_fare(st, M)
        if time.time() - ultimo_giro > 3600:
            tot = {l: sum(len(righe_di(c)) for c in CASI) for l in ('tipo', 'l05')}
            scrivi_log(f'avanzamento: tipo {finite["tipo"]}/{tot["tipo"]}, L05 {finite["l05"]}/{tot["l05"]} righe con {K} letture; '
                       f'stima s/lettura {st["stima"]}')
            ultimo_giro = time.time()
        time.sleep(120)
    fare, finite = da_fare(st, M)
    rinunce = {l: [f'{c}:{i}' for c in CASI for i in righe_di(c) if valide(M[l][c].get(i)) < K] for l in ('tipo', 'l05')}
    scrivi_log(f'letture finite: tipo {finite["tipo"]} righe complete, L05 {finite["l05"]}; senza {K} letture valide dopo '
               f'{MAX_INVII} invii: tipo {len(rinunce["tipo"])}, L05 {len(rinunce["l05"])}')
    json.dump(rinunce, open(C/'senza_cinque_letture.json', 'w'), indent=1)


# ── rapporto ────────────────────────────────────────────────────────────────────────────────────────────────────────

def fase_rapporto(a):
    from google.cloud import firestore
    db = firestore.Client(project='climpact-drp')
    st = carica_stato()
    righe_md = ['# Cinque letture per riga: che cosa cambia (rapporto prima del caricamento)', '',
                f"Scritto da `tools/cinque_letture.py rapporto` il {datetime.datetime.now().strftime('%d/%m/%Y alle %H:%M')}, "
                'dalle prove a secco di R11 (la composizione a maggioranza delle cinque letture, regole in `tools/maggioranza.py`) '
                'confrontate con le proposte che le righe hanno oggi in piattaforma. Solo righe col nome non giudicate.', '',
                'Che cosa vuol dire ogni colonna:', '',
                '- **righe**: righe non giudicate del caso; **nuove proposte**: quelle che il caricamento riscrive '
                '(le altre restano come sono: manca una lettura valida);',
                '- **tipo cambiato**: il tipo a maggioranza (R11) e\' diverso dal tipo proposto oggi;',
                '- **principi cambiati**: l\'insieme dei principi proposti e\' diverso da oggi (oggi: R05, principi da L04);',
                '- **seguito cambiato**: le pagine attorno spuntate come seguito sono diverse da oggi (oggi R08, ora R10 a maggioranza);',
                '- **incerte**: il tipo o almeno un principio decisi con margine di un voto al massimo;',
                '- **prova mancante**: almeno un principio proposto dalla sola lettura senza una frase trovata nella pagina.', '']
    tab = ['| caso | righe | nuove proposte | tipo cambiato | principi cambiati | seguito cambiato | incerte | prova mancante |',
           '|---|---|---|---|---|---|---|---|']
    tot = collections.Counter()
    for caso in CASI:
        tipo = json.load(open(C/f'secco_tipo_{caso}.json', encoding='utf-8'))
        rip = json.load(open(C/f'secco_ripresa_{caso}.json', encoding='utf-8'))
        oggi = {}
        for d in db.collection('corpus_rows').where(filter=firestore.FieldFilter('caso_citato', '==', caso)).stream():
            oggi[d.id] = d.to_dict()
        # le righe giudicate dopo la prova a secco: il caricamento vero le salta (rilegge la banca dati)
        giudicate = [i for i in set(tipo) | set(rip) if (oggi.get(i) or {}).get('esito')]
        if giudicate:
            scrivi_log(f'{caso}: {len(giudicate)} righe giudicate dopo la prova a secco: il caricamento le salta')
        n = len(righe_di(caso)); c = collections.Counter()
        for i in set(tipo) | set(rip):
            o = oggi.get(i) or {}
            c['nuove'] += 1
            if i in tipo and tipo[i]['proposto_tipo_citazione'] != o.get('proposto_tipo_citazione'):
                c['tipo'] += 1
            if i in rip:
                x = rip[i]
                if sorted(x['proposto_principi']) != sorted(o.get('proposto_principi') or []):
                    c['principi'] += 1
                pros = sorted(v['pagina'] for v in x['proposto_estensione'] if v['prosegue'])
                if pros != sorted(v.get('pagina') for v in (o.get('proposto_estensione') or []) if v.get('prosegue')):
                    c['seguito'] += 1
                c['incerte'] += bool(x.get('proposto_incerta')); c['prova'] += bool(x.get('proposto_prova_mancante'))
            elif i in tipo and tipo[i].get('proposto_tipo_incerto'):
                c['incerte'] += 1
        pc = lambda k: f'{c[k]} ({100 * c[k] / max(c["nuove"], 1):.0f}%)'
        tab.append(f'| {caso} | {n} | {c["nuove"]} | {pc("tipo")} | {pc("principi")} | {pc("seguito")} | {pc("incerte")} | {pc("prova")} |')
        tot.update(c); tot['righe'] += n
    pc = lambda k: f'{tot[k]} ({100 * tot[k] / max(tot["nuove"], 1):.0f}%)'
    tab.append(f'| tutti | {tot["righe"]} | {tot["nuove"]} | {pc("tipo")} | {pc("principi")} | {pc("seguito")} | {pc("incerte")} | {pc("prova")} |')
    misure = st.get('misure') or []
    per = collections.defaultdict(list)
    for m in misure:
        per[m['lettore']].append(m)
    dopo = ['', '## Le letture', '']
    for l, nome in (('tipo', 'tipo (L02/L03)'), ('l05', 'L05 con le pagine attorno R10')):
        mm = per.get(l) or []
        if mm:
            dopo.append(f"- {nome}: {sum(m['letture'] for m in mm)} letture nuove in {len(mm)} blocchi, "
                        f"{sum(m['secondi'] for m in mm) / max(sum(m['letture'] for m in mm), 1):.2f} s per lettura per server.")
    if (C/'senza_cinque_letture.json').exists():
        rin = json.load(open(C/'senza_cinque_letture.json'))
        dopo.append(f"- Righe rimaste senza cinque letture valide dopo {MAX_INVII} invii: tipo {len(rin['tipo'])}, L05 {len(rin['l05'])} "
                    "(si caricano con le letture valide che hanno, a maggioranza di quelle).")
    (C/'RAPPORTO.md').write_text('\n'.join(righe_md + tab + dopo) + '\n', encoding='utf-8')
    scrivi_log('RAPPORTO.md scritto: ' + tab[-1])


def fase_stato(a):
    st = carica_stato(); M = maestri()
    fare, finite = da_fare(st, M)
    print(json.dumps({'finite': finite, 'da_fare': {l: sum(len(v) for v in fare[l].values()) for l in fare},
                      'stima': st['stima'], 'blocchi': collections.Counter(b['stato'] for b in st['blocchi'].values()),
                      'misure': st['misure'][-6:]}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    import giornale as G
    G.avvia()
    ap = argparse.ArgumentParser(); ap.add_argument('fase', choices=['righe', 'prepara', 'letture', 'rapporto', 'stato'])
    a = ap.parse_args()
    {'righe': fase_righe, 'prepara': fase_prepara, 'letture': fase_letture, 'rapporto': fase_rapporto, 'stato': fase_stato}[a.fase](a)
