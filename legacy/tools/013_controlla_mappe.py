"""IL CONTROLLO DELLE MAPPE DEI PARAGRAFI (R01) CON DEEPSEEK (29/09/2026, prima della revisione di un giurista).

   Le mappe dicono quale principio sta in ogni paragrafo delle sentenze citate; da li' vengono i principi di centinaia
   di citazioni (Neubauer 988) e parte delle etichette per misurare e addestrare il reranker. Le ha scritte un modello
   come bozza, e nessuno del gruppo le ha ancora rilette. Qui DeepSeek rilegge ogni voce col testo della pagina (o
   delle pagine) dove sta il paragrafo e dice quali principi del caso quel paragrafo enuncia, applica o sviluppa; si
   confronta con la mappa, e il giurista rivede per prime le voci dove i due non coincidono. DeepSeek non corregge
   niente: segnala.

   Fasi:
     prepara   Mac   -> training/mappe/domande.jsonl (una domanda per voce)
     leggi     GPU   -> training/mappe/letture.jsonl (due letture per voce, con il ragionamento)
     confronta Mac   -> training/mappe/confronto.json e .md (voci concordi, discordi, da rivedere per prime)
"""
import argparse, concurrent.futures as cf, gzip, json, pathlib, re, threading, time
QUI = pathlib.Path(__file__).resolve().parent.parent
M = QUI/'training'/'mappe'
CASI = ('urgenda', 'neubauer', 'future-generations')

MODULO = """Sei un giurista che controlla una MAPPA DEI PARAGRAFI di una sentenza climatica: per ogni paragrafo, quali principi del caso vi sono enunciati, applicati o sviluppati.

Il caso e' {nome}. I suoi principi (id, titolo, testo):
{principi}

Il paragrafo da controllare: «{paragrafo}» ({pronuncia}), nel documento {documento}, pagina {pagina}.
La mappa riassume il paragrafo cosi': {sintesi}
{verbatim}
Qui sotto il testo della pagina (o delle pagine) dove sta il paragrafo. Individua il paragrafo e leggilo nel suo contesto.

{testo}

DOMANDE
1. Quali principi della lista il paragrafo enuncia, applica o sviluppa? Solo quelli che il paragrafo SOSTIENE, non quelli che nomina di passaggio o che riporta come tesi di una parte senza accoglierla. Se il paragrafo riguarda solo fatti, procedura o ricevibilita', nessuno.
2. Trovi il paragrafo nella pagina? (si/no/incerto)
3. Una frase copiata ALLA LETTERA dal paragrafo che regge la tua risposta.

Rispondi SOLO con JSON: {{"principi": ["id", ...], "trovato": "si|no|incerto", "prova": "...", "motivo": "una frase"}}"""


def prepara():
    import yaml
    M.mkdir(parents=True, exist_ok=True)
    domande, serve = [], set()
    for caso in CASI:
        conf = yaml.safe_load(open(QUI/'cited-cases'/f'{caso}.yaml', encoding='utf-8'))
        mappa = yaml.safe_load(open(QUI/'cited-cases'/f'{caso}-mappa-paragrafi.yaml', encoding='utf-8'))
        for i, v in enumerate(mappa['voci']):
            pag = str(v.get('pagina') or v.get('pagina_en') or v.get('pagina_de') or '')
            nums = [int(x) for x in re.findall(r'\d+', pag)][:2]
            if len(nums) == 2:
                nums = list(range(nums[0], min(nums[1], nums[0] + 2) + 1))
            doc = v.get('documento') or (mappa.get('documenti') or {}).get('en')
            if v.get('pagina_en') and (mappa.get('documenti') or {}).get('en'):
                doc = mappa['documenti']['en']
                nn = [int(x) for x in re.findall(r'\d+', str(v['pagina_en']))][:2]
                nums = list(range(nn[0], min(nn[-1], nn[0] + 2) + 1)) if nn else []
            pid = [f'{doc}#p{n}' for n in nums]
            serve |= set(pid)
            domande.append({'id': f'{caso}#{i}', 'caso': caso, 'nome': conf.get('nome') or caso, 'pagine': pid,
                            'paragrafo': v.get('paragrafo'), 'pronuncia': v.get('pronuncia') or '', 'documento': doc,
                            'pagina': pag, 'sintesi': v.get('sintesi') or '', 'verbatim': v.get('verbatim') or '',
                            'mappa': sorted(v.get('sonde') or []),
                            'principi': [(s['id'], ' '.join(s['titolo'].split()), ' '.join(s['testo'].split())) for s in conf['semantic_queries']]})
    testi = {}
    with gzip.open(QUI/'index'/'pagine'/'pagine.jsonl.gz', 'rt', encoding='utf-8') as f:
        for l in f:
            x = json.loads(l)
            if x['id'] in serve:
                testi[x['id']] = x['testo']
    n = 0
    with open(M/'domande.jsonl', 'w', encoding='utf-8') as out:
        for d in domande:
            testo = '\n\n'.join(f'--- PAGINA {p.split("#p")[1]} ---\n{testi.get(p, "")[:9000]}' for p in d['pagine'] if p in testi)
            d['senza_testo'] = not testo
            d['domanda'] = MODULO.format(
                nome=d['nome'], principi='\n'.join(f'- {a}: {b}. {c}' for a, b, c in d['principi']),
                paragrafo=d['paragrafo'], pronuncia=d['pronuncia'], documento=d['documento'], pagina=d['pagina'],
                sintesi=d['sintesi'], verbatim=(f"Frase del paragrafo secondo la mappa: «{d['verbatim']}»" if d['verbatim'] else ''),
                testo=testo or '(testo della pagina non disponibile)')
            out.write(json.dumps(d, ensure_ascii=False) + '\n'); n += 1
    print(n, 'voci,', sum(1 for d in domande if d.get('senza_testo')), 'senza testo della pagina')


def leggi(a):
    from openai import OpenAI
    sys_path = str(QUI/'tools')
    import sys; sys.path.insert(0, sys_path)
    _m_classifica_lessicali = __import__('024_classifica_lessicali')
    estrai_tollerante = _m_classifica_lessicali.estrai_tollerante
    cli = OpenAI(api_key=pathlib.Path(a.chiave_file).read_text().strip(), base_url=a.base_url, timeout=1800)
    D = [json.loads(l) for l in open(M/'domande.jsonl', encoding='utf-8')]
    uscita = M/'letture.jsonl'
    fatte = {json.loads(l)['id'] for l in open(uscita, encoding='utf-8')} if uscita.exists() else set()
    da_fare = [d for d in D if d['id'] not in fatte]
    print(len(D), 'voci,', len(da_fare), 'da fare', flush=True)

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
        r = [chiama(d['domanda']) for _ in range(2)]
        return {'id': d['id'], 'letture': [estrai_tollerante(x) for x, _ in r], 'ragionamenti': [y[:6000] for _, y in r]}

    blocco = threading.Lock()
    with cf.ThreadPoolExecutor(a.paralleli) as ex, open(uscita, 'a', encoding='utf-8') as f:
        for n, e in enumerate(ex.map(una, da_fare), 1):
            with blocco:
                f.write(json.dumps(e, ensure_ascii=False) + '\n'); f.flush()
            if n % 50 == 0:
                print(n, flush=True)


def confronta():
    D = {json.loads(l)['id']: json.loads(l) for l in open(M/'domande.jsonl', encoding='utf-8')}
    L = {json.loads(l)['id']: json.loads(l) for l in open(M/'letture.jsonl', encoding='utf-8')}
    righe, conti = [], {}
    for i, d in D.items():
        l = L.get(i)
        if not l:
            continue
        lett = [x for x in l['letture'] if isinstance(x, dict)]
        ds = [set(x.get('principi') or []) for x in lett]
        mappa = set(d['mappa'])
        concordi = len(ds) == 2 and ds[0] == ds[1]
        esito = ('concorde' if concordi and ds[0] == mappa else
                 'discorde' if concordi else 'deepseek incerto')
        conti[(d['caso'], esito)] = conti.get((d['caso'], esito), 0) + 1
        righe.append({'id': i, 'caso': d['caso'], 'paragrafo': d['paragrafo'], 'pagina': d['pagina'], 'mappa': sorted(mappa),
                      'deepseek': [sorted(x) for x in ds], 'esito': esito, 'trovato': [x.get('trovato') for x in lett],
                      'prova': (lett[0].get('prova') if lett else ''), 'motivo': (lett[0].get('motivo') if lett else ''),
                      'ragionamento': (l.get('ragionamenti') or [''])[0][:3000]})
    json.dump(righe, open(M/'confronto.json', 'w'), ensure_ascii=False, indent=1)
    for k, v in sorted(conti.items()):
        print(k, v)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('fase', choices=['prepara', 'leggi', 'confronta'])
    ap.add_argument('--paralleli', type=int, default=48); ap.add_argument('--modello', default='deepseek-v4-flash')
    ap.add_argument('--base-url', default='http://127.0.0.1:8000/v1'); ap.add_argument('--chiave-file', default=str(QUI/'chat'/'chiave'))
    a = ap.parse_args()
    {'prepara': prepara, 'confronta': confronta}.get(a.fase, lambda: leggi(a))()
