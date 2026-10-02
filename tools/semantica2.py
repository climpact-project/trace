"""LA RICERCA SEMANTICA RIFATTA: RIPRESE SENZA CITAZIONE, CERCATE CON I PASSAGGI VERI (29/09/2026, deciso col PI).

   La ricerca di luglio cercava con sonde scritte a mano e trovava soprattutto lo stesso tema da altre fonti (circa una
   ripresa vera ogni cento pagine candidate). Qui le domande sono le frasi degli atti che le citazioni di Urgenda
   sostengono davvero (`frase_sostenuta` di L05, dove le due letture concordano su almeno un principio), col nome del
   caso e gli ECLI mascherati. Si cerca in tutto il corpus, senza limite di paese, solo negli atti successivi alla
   prima pronuncia (24/06/2015) che NON nominano Urgenda da nessuna parte (quelli li copre la ricerca per nome). Le
   pagine trovate passano dal reranker (T01) sul principio della domanda; le migliori le legge DeepSeek con istruzioni
   proprie (L06): riprende il ragionamento di Urgenda, lo prende da un'altra fonte, o e' solo lo stesso tema? L'ordine
   di lettura mette prima gli atti che citano un intermediario (Neubauer, KlimaSeniorinnen, Shell, Greenpeace Nordic):
   e' li' che il ragionamento puo' essere passato senza il nome.

   Fasi:
     domande   Mac -> training/semantica2/urgenda_domande.jsonl e urgenda_atti_ammessi.json
     cerca     GPU -> training/semantica2/urgenda_candidate.jsonl (pplx-embed-v1-4b sull'indice delle pagine)
     coppie    Mac -> training/principi/semantica2_urgenda_coppie.jsonl (per `ripresa_punteggi.py punteggi`)
     scegli    Mac -> training/semantica2/urgenda_da_leggere.jsonl (le migliori per principio, con il testo)
     leggi     GPU -> training/semantica2/urgenda_letture.jsonl (DeepSeek, L06, due letture con il ragionamento)
"""
import sys, pathlib as _pl
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
import argparse, collections, concurrent.futures as cf, glob, gzip, json, pathlib, re, sys, threading, time
QUI = pathlib.Path(__file__).resolve().parent.parent
S = QUI/'training'/'semantica2'
P = QUI/'training'/'principi'
sys.path.insert(0, str(QUI/'tools'))
DATA_MIN = '2015-06-24'                     # Urgenda; per gli altri casi la data della decisione nel file del caso
INTERMEDIARI = {'urgenda': ['Urgenda', '19/00135'],
                'neubauer': ['Neubauer', 'Klimabeschluss', '2656/18'],
                'future-generations': ['Generaciones Futuras', 'STC4360', 'STC 4360'],
                'klimaseniorinnen': ['KlimaSeniorinnen', 'Klimaseniorinnen', '53600/20'],
                'idh-oc-32-25': ['OC-32/25', 'AO-32/25', 'OC-32/2025'],
                'cig-parere-clima': ['Obligations of States in respect of Climate Change', 'ICJ Advisory Opinion'],
                'shell': ['Milieudefensie', 'Royal Dutch Shell'],
                'greenpeace-nordic': ['Greenpeace Nordic', 'People v Arctic Oil', 'Natur og Ungdom']}
# 02/10/2026: la stessa ricerca per i tre casi nuovi. Gli intermediari di un caso sono tutti gli altri (mai se stesso),
# la soglia di data e' `data_decisione` del file del caso, la lettura di partenza e' la v2 (L05) di quel caso.


def front(testo):
    m = re.match(r'^---\n(.*?)\n---', testo, re.S)
    meta = {}
    for l in (m.group(1).splitlines() if m else []):
        if ':' in l:
            k, v = l.split(':', 1); meta[k.strip()] = v.strip().strip("'\"")
    return meta


def domande(caso='urgenda'):
    import yaml
    from prepara_training import mascheratore, SEGNAPOSTO
    S.mkdir(parents=True, exist_ok=True)
    conf = yaml.safe_load(open(QUI/'cited-cases'/f'{caso}.yaml', encoding='utf-8'))
    maschera = mascheratore([str(f) for f in conf['forme']] + [conf.get('nome', '')])
    principi = {s['id']: ' '.join(s['testo'].split()) for s in conf['semantic_queries']}
    data_min = str(conf.get('data_decisione') or DATA_MIN)[:10] if caso != 'urgenda' else DATA_MIN
    L = [json.loads(l) for l in open(P/f'{caso}_ripresa_deepseek_v2.jsonl', encoding='utf-8')]
    per = collections.defaultdict(list)
    for x in L:
        g = [y for y in x.get('letture') or [] if isinstance(y, dict)]
        if len(g) < 2:
            continue
        comuni = set(g[0].get('principi') or []) & set(g[1].get('principi') or []) - {'nessuno', 'altro'}
        frase = ' '.join(str(g[0].get('frase_sostenuta') or '').split())
        if not comuni or len(frase) < 60:
            continue
        doc = x['id'].split('__')[1]
        for p in comuni & set(principi):
            per[p].append({'riga': x['id'], 'documento': doc, 'principio': p, 'testo': maschera.sub(SEGNAPOSTO, frase)[:1200]})
    out = []
    for p, xs in per.items():
        visti = collections.Counter(); tenute = []
        for x in xs:
            if visti[x['documento']] < 2:
                tenute.append(x); visti[x['documento']] += 1
            if len(tenute) >= 40:
                break
        out += tenute
    with open(S/f'{caso}_domande.jsonl', 'w', encoding='utf-8') as f:
        for i, x in enumerate(out):
            f.write(json.dumps(dict(x, id=f'q{i}'), ensure_ascii=False) + '\n')
    print(caso, 'domande per principio', dict(collections.Counter(x['principio'] for x in out)))
    # gli atti ammessi: successivi alla prima pronuncia, che non nominano il caso, non del caso stesso
    nominano = set()
    for f in glob.glob(str(QUI/'index'/f'nomi_{caso}_*b*.csv')):
        import csv
        for r in csv.DictReader(open(f, encoding='utf-8')):
            nominano.add(r['document_id'])
    escludi = set(conf.get('escludi_case_id') or [])
    ammessi, inter = [], collections.defaultdict(list)
    for md in (QUI/'markdown').glob('*/*.md'):
        t = md.read_text(encoding='utf-8', errors='replace')
        meta = front(t[:4000]); d = meta.get('document_id') or md.name.split('__')[0]
        if d in nominano or meta.get('case_id') in escludi:
            continue
        # la data del documento dal nome del file d'origine quando c'e' (`cerca.data_documento`), se no la data di deposito
        dd = re.search(r'/(\d{4})(\d{2})(\d{2})_', str(meta.get('url_origine') or ''))
        data = f'{dd.group(1)}-{dd.group(2)}-{dd.group(3)}' if dd and caso != 'urgenda' else (meta.get('data_deposito') or '')[:10]
        if data < data_min:
            continue
        ammessi.append(d)
        for k, forme in INTERMEDIARI.items():
            if k != caso and any(x in t for x in forme):
                inter[d].append(k)
    json.dump({'ammessi': ammessi, 'intermediari': inter}, open(S/f'{caso}_atti_ammessi.json', 'w'))
    print('atti ammessi', len(ammessi), 'di cui citano un intermediario', len(inter))


def cerca(a):
    import numpy as np, torch, torch.nn.functional as F
    from transformers import AutoTokenizer, AutoModel
    from distilla import MODELLI, indice
    NOME, POOL, PQ, CART = MODELLI['pplx4b']
    Q = [json.loads(l) for l in open(S/f'{a.caso}_domande.jsonl', encoding='utf-8')]
    amm = json.load(open(S/f'{a.caso}_atti_ammessi.json'))
    ok = set(amm['ammessi'])
    V, ids = indice(CART)
    tenute = np.array([i.split('#')[0] in ok for i in ids])
    Vt = torch.from_numpy(V).cuda(); del V
    tok = AutoTokenizer.from_pretrained(NOME, padding_side='left', trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    m = AutoModel.from_pretrained(NOME, torch_dtype=torch.bfloat16, trust_remote_code=True).cuda().eval()
    E = []
    with torch.no_grad():
        for i in range(0, len(Q), 16):
            e = tok([PQ + q['testo'] for q in Q[i:i+16]], padding=True, truncation=True, max_length=512, return_tensors='pt').to('cuda')
            hs = m(**e).last_hidden_state
            mk = e['attention_mask'].unsqueeze(-1).to(hs.dtype); h = (hs * mk).sum(1) / mk.sum(1)
            E.append(F.normalize(h.float(), dim=-1))
    E = torch.cat(E).half()
    maschera = torch.from_numpy(tenute).cuda()
    migliori = collections.defaultdict(dict)  # principio -> pagina -> (punteggio, domanda)
    for q, e in zip(Q, E):
        sc = (Vt @ e).float(); sc[~maschera] = -9
        top = torch.topk(sc, a.k)
        for s, i in zip(top.values.cpu().numpy(), top.indices.cpu().numpy()):
            pid = ids[i]; cur = migliori[q['principio']].get(pid)
            if not cur or s > cur[0]:
                migliori[q['principio']][pid] = (float(s), q['id'])
    with open(S/f'{a.caso}_candidate.jsonl', 'w', encoding='utf-8') as f:
        for p, dd in migliori.items():
            for pid, (s, qid) in sorted(dd.items(), key=lambda kv: -kv[1][0])[:a.per_principio]:
                f.write(json.dumps({'principio': p, 'pagina_id': pid, 'punteggio': round(s, 4), 'domanda': qid}) + '\n')
    print({p: min(len(d), a.per_principio) for p, d in migliori.items()}, flush=True)


def coppie(caso='urgenda'):
    import yaml
    from prepara_training import mascheratore, SEGNAPOSTO
    conf = yaml.safe_load(open(QUI/'cited-cases'/f'{caso}.yaml', encoding='utf-8'))
    maschera = mascheratore([str(f) for f in conf['forme']] + [conf.get('nome', '')])
    principi = {s['id']: ' '.join(s['testo'].split()) for s in conf['semantic_queries']}
    C = [json.loads(l) for l in open(S/f'{caso}_candidate.jsonl', encoding='utf-8')]
    serve = {c['pagina_id'] for c in C}; testi = {}
    with gzip.open(QUI/'index'/'pagine'/'pagine.jsonl.gz', 'rt', encoding='utf-8') as f:
        for l in f:
            x = json.loads(l)
            if x['id'] in serve:
                testi[x['id']] = x['testo']
    with open(P/f'semantica2_{caso}_coppie.jsonl', 'w', encoding='utf-8') as f:
        for c in C:
            f.write(json.dumps({'q': principi[c['principio']], 'd': maschera.sub(SEGNAPOSTO, ' '.join(testi.get(c['pagina_id'], '').split()))[:9000],
                                'pagina_id': c['pagina_id'], 'dove': 'pagina', 'principio': c['principio']}, ensure_ascii=False) + '\n')
    print(len(C), 'coppie')


MODULO = """Sei un giurista che studia come le sentenze climatiche vengono riprese nei processi successivi.
Il caso studiato e' {nome}. Il principio in questione:
- {pid}: {ptitolo}. {ptesto}

Qui sotto una pagina di un atto successivo ({case_name}, {tipo_atto}, {data}). L'atto NON nomina mai {nome}: e' stato scelto perche' la pagina somiglia a passaggi di altri atti che citano {nome} per questo principio.
{intermediari}
--- PAGINA {pagina} ---
{testo}
--- FINE ---

DOMANDE
1. "giudizio": la pagina
   - "ripresa": sviluppa lo STESSO ragionamento del principio, con i suoi passaggi caratteristici, senza attribuirlo a nessuna fonte o attribuendolo a una fonte che a sua volta lo prende da {nome};
   - "altra_fonte": sviluppa un argomento simile ma lo attribuisce a un'altra fonte (un altro caso, un trattato, un rapporto) che non deriva da {nome};
   - "stesso_tema": parla dello stesso tema senza il ragionamento del principio;
   - "fuori_tema".
2. "fonte": se la pagina attribuisce l'argomento a una fonte, quale (altrimenti "").
3. "prova": una frase copiata ALLA LETTERA dalla pagina che regge il giudizio.
4. "motivo": una frase.

Rispondi SOLO con JSON: {{"giudizio": "...", "fonte": "...", "prova": "...", "motivo": "..."}}"""


def scegli(caso='urgenda', n=200):
    import yaml
    conf = yaml.safe_load(open(QUI/'cited-cases'/f'{caso}.yaml', encoding='utf-8'))
    pr = {s['id']: s for s in conf['semantic_queries']}
    amm = json.load(open(S/f'{caso}_atti_ammessi.json'))
    punti = {}
    for f in glob.glob(str(P/f'semantica2_{caso}_punteggi_*.jsonl')):
        for l in open(f):
            x = json.loads(l); punti[(x['pagina_id'], x['principio'])] = x['punteggio']
    C = [json.loads(l) for l in open(S/f'{caso}_candidate.jsonl', encoding='utf-8')]
    for c in C:
        c['reranker'] = punti.get((c['pagina_id'], c['principio']))
    per = collections.defaultdict(list)
    for c in C:
        if c['reranker'] is not None:
            per[c['principio']].append(c)
    scelte = []
    for p, xs in per.items():
        xs.sort(key=lambda c: -c['reranker']); scelte += xs[:n]
    serve = {c['pagina_id'] for c in scelte}; testi = {}; meta = {}
    with gzip.open(QUI/'index'/'pagine'/'pagine.jsonl.gz', 'rt', encoding='utf-8') as f:
        for l in f:
            x = json.loads(l)
            if x['id'] in serve:
                testi[x['id']] = x['testo']; meta[x['id']] = x.get('file', '')
    # prima gli atti che citano un intermediario, poi il punteggio
    scelte.sort(key=lambda c: (0 if amm['intermediari'].get(c['pagina_id'].split('#')[0]) else 1, -c['reranker']))
    # IL FRENO 1 (30/09/2026, `freni.py`): le pagine illeggibili non si leggono; vanno in `<caso>_da_ocr.txt`
    from freni import leggibile
    rotte = sorted({c['pagina_id'] for c in scelte if not leggibile(testi.get(c['pagina_id'], ''))[0]})
    (S/f'{caso}_da_ocr.txt').write_text('\n'.join(rotte) + '\n', encoding='utf-8')
    scelte = [c for c in scelte if c['pagina_id'] not in rotte]
    print(len(rotte), 'pagine illeggibili escluse ->', S/f'{caso}_da_ocr.txt')
    with open(S/f'{caso}_da_leggere.jsonl', 'w', encoding='utf-8') as f:
        for c in scelte:
            d = c['pagina_id'].split('#')[0]; s = pr[c['principio']]
            inter = amm['intermediari'].get(d) or []
            f.write(json.dumps(dict(c, intermediari=inter, domanda_ds=MODULO.format(
                nome=conf.get('nome') or caso, pid=s['id'], ptitolo=' '.join(s['titolo'].split()), ptesto=' '.join(s['testo'].split()),
                case_name=d, tipo_atto='', data='', pagina=c['pagina_id'].split('#p')[1],
                intermediari=(f"L'atto cita invece: {', '.join(inter)}." if inter else ''),
                testo=testi.get(c['pagina_id'], '')[:9000])), ensure_ascii=False) + '\n')
    print(len(scelte), 'pagine da leggere, con intermediario', sum(1 for c in scelte if amm['intermediari'].get(c['pagina_id'].split('#')[0])))


def leggi(a):
    from openai import OpenAI
    from classifica_lessicali import estrai_tollerante
    cli = OpenAI(api_key=pathlib.Path(a.chiave_file).read_text().strip(), base_url=a.base_url, timeout=1800)
    D = [json.loads(l) for l in open(S/f'{a.caso}_da_leggere.jsonl', encoding='utf-8')]
    uscita = S/f'{a.caso}_letture.jsonl'
    fatte = {(json.loads(l)['pagina_id'], json.loads(l)['principio']) for l in open(uscita, encoding='utf-8')} if uscita.exists() else set()
    da_fare = [d for d in D if (d['pagina_id'], d['principio']) not in fatte]
    print(len(D), 'pagine,', len(da_fare), 'da fare', flush=True)

    def chiama(t):
        for k in range(5):
            try:
                x = cli.chat.completions.create(model=a.modello, messages=[{'role': 'user', 'content': t}], max_tokens=6000,
                                                extra_body={'chat_template_kwargs': {'thinking': True, 'reasoning_effort': 'low'}})
                m = x.choices[0].message
                return (m.content or ''), (getattr(m, 'reasoning', None) or getattr(m, 'reasoning_content', None) or '')
            except Exception:
                time.sleep(5 * (k + 1))
        return '', ''

    def una(d):
        r = [chiama(d['domanda_ds']) for _ in range(2)]
        return {'pagina_id': d['pagina_id'], 'principio': d['principio'], 'reranker': d['reranker'], 'intermediari': d['intermediari'],
                'letture': [estrai_tollerante(x) for x, _ in r], 'ragionamenti': [y[:6000] for _, y in r]}

    blocco = threading.Lock()
    with cf.ThreadPoolExecutor(a.paralleli) as ex, open(uscita, 'a', encoding='utf-8') as f:
        for n, e in enumerate(ex.map(una, da_fare), 1):
            with blocco:
                f.write(json.dumps(e, ensure_ascii=False) + '\n'); f.flush()
            if n % 50 == 0:
                print(n, flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('fase', choices=['domande', 'cerca', 'coppie', 'scegli', 'leggi'])
    ap.add_argument('--caso', default='urgenda'); ap.add_argument('--k', type=int, default=300)
    ap.add_argument('--per-principio', type=int, default=3000); ap.add_argument('--n', type=int, default=200)
    ap.add_argument('--paralleli', type=int, default=48); ap.add_argument('--modello', default='deepseek-v4-flash')
    ap.add_argument('--base-url', default='http://127.0.0.1:8000/v1'); ap.add_argument('--chiave-file', default=str(QUI/'chat'/'chiave'))
    a = ap.parse_args()
    if a.fase == 'domande': domande(a.caso)
    elif a.fase == 'cerca': cerca(a)
    elif a.fase == 'coppie': coppie(a.caso)
    elif a.fase == 'scegli': scegli(a.caso, a.n)
    else: leggi(a)
