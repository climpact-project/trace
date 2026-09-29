"""DeepSeek reads the uptake: which principles an explicit citation takes, and how far it extends in the document.

   For each lexical (name-based) citation the model receives the citation page with the end of the previous
   page and the start of the next one, the list of the cited case's principles, the principles that the
   paragraph map derives from the paragraph numbers cited, and up to MAX_VICINE NEIGHBOURING PAGES of the same
   document that TRACE-Reranker scores at or above SOGLIA_VICINA for some principle. It returns:
     - which principles the citation takes (possibly several; "nessuno"; "altro" with a sentence);
     - for each neighbouring page, whether it continues the same uptake (same principle, same line of
       reasoning started by the citation), with a verbatim sentence from the page.
   Outputs are proposals for human coders, never training labels.

   Phases:
     prepara  local machine  -> training/principi/<caso>_ripresa_righe.jsonl
     leggi    GPU server, DeepSeek endpoint -> training/principi/<caso>_ripresa_deepseek.jsonl

   Usage: python tools/leggi_ripresa.py prepara|leggi [--caso urgenda] [--letture 2] [--etichetta v2]
"""
import argparse, collections, concurrent.futures as cf, datetime, gzip, json, pathlib, sys, threading, time
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
P = QUI/'training'/'principi'
SOGLIA_VICINA = 0.5
MAX_VICINE = 3
TAGLIO_VICINA = 3500


def prepara(caso):
    import yaml
    righe = [json.loads(l) for l in open(QUI/'training'/f'lessicali_{caso}_righe.jsonl', encoding='utf-8')]
    par = {json.loads(l)['id']: json.loads(l) for l in open(P/f'{caso}_da_paragrafi.jsonl', encoding='utf-8')}
    brano = collections.defaultdict(dict); vicina = collections.defaultdict(dict)
    for f in sorted(P.glob(f'{caso}_punteggi_*.jsonl')):
        for l in open(f, encoding='utf-8'):
            x = json.loads(l)
            if x['dove'] == 'brano':
                brano[x['riga']][x['principio']] = x['punteggio']
            else:
                vicina[x['pagina_id']][x['principio']] = x['punteggio']
    serve = set()
    scelte = {}
    for r in righe:
        p = int(r.get('pagina') or 0)
        cand = []
        for k in range(p - 2, p + 4):
            pid = f"{r['document_id']}#p{k}"
            if k != p and pid in vicina:
                m = max(vicina[pid].values())
                if m >= SOGLIA_VICINA:
                    cand.append((m, k, pid))
        cand = sorted(cand, reverse=True)[:MAX_VICINE]
        scelte[r['id']] = cand
        serve |= {c[2] for c in cand}
    testi = {}
    with gzip.open(QUI/'index'/'pagine'/'pagine.jsonl.gz', 'rt', encoding='utf-8') as f:
        for l in f:
            x = json.loads(l)
            if x['id'] in serve:
                testi[x['id']] = x['testo']
    n = collections.Counter()
    with open(P/f'{caso}_ripresa_righe.jsonl', 'w', encoding='utf-8') as f:
        for r in righe:
            cand = scelte[r['id']]
            n['con pagine vicine' if cand else 'senza pagine vicine'] += 1
            f.write(json.dumps({
                'id': r['id'], 'document_id': r['document_id'], 'case_name': r.get('case_name'), 'tipo_atto': r.get('tipo_atto'),
                'data': r.get('data'), 'pagina': r.get('pagina'), 'forma': r.get('forma'), 'contesto': r['contesto'],
                'principi_paragrafi': par.get(r['id'], {}).get('principi', []), 'paragrafi': par.get(r['id'], {}).get('paragrafi', []),
                'punteggi_brano': brano.get(r['id'], {}),
                'vicine': [{'pagina': k, 'punteggi': vicina[pid], 'testo': testi.get(pid, '')[:TAGLIO_VICINA]} for _, k, pid in sorted(cand, key=lambda c: c[1])],
            }, ensure_ascii=False) + '\n')
    print(dict(n), '->', P/f'{caso}_ripresa_righe.jsonl')


MODULO = """Sei un giurista che codifica le riprese di una sentenza climatica in atti successivi.
Il caso citato e' {nome_caso}.
{fascicolo}
I PRINCIPI DEL CASO (id, titolo, testo di riferimento):
{principi}

DOCUMENTO: {case_name} ({tipo_atto}, {data}), documento {document_id}.
La rete lessicale ha trovato il nome «{forma}» nel punto marcato con ⟦ ⟧, dentro il brano racchiuso fra
[[INIZIO DEL BRANO SEGNALATO]] e [[FINE DEL BRANO SEGNALATO]]. Ecco la pagina della citazione con la fine della
precedente e l'inizio della successiva:
---
{contesto}
---
{aiuto_paragrafi}
PAGINE VICINE DELLO STESSO ATTO (possibile seguito della ripresa, senza il nome del caso):
{vicine}

DOMANDA 1. Quali principi del caso questa citazione prende, cioe' usa, applica, discute o respinge? Anche piu'
d'uno. "nessuno" se la citazione non prende nessun principio (elenco di precedenti, solo descrizione dei fatti o
dell'esito, esempio di contenzioso). "altro" se prende qualcosa che non e' nella lista: scrivilo in una frase.

DOMANDA 2. Per ogni pagina vicina: prosegue LA STESSA RIPRESA? Si', solo se sviluppa uno dei principi presi
dalla citazione dentro lo stesso ragionamento avviato dalla citazione. No, se parla d'altro, oppure se regge lo
stesso tema su un'altra fonte (CEDU generale, Accordo di Parigi, un altro caso) senza legame con la citazione.
GUARDA LE NOTE: se la frase della pagina vicina ha una sua nota che la attribuisce a un'altra fonte, non prosegue.
Se la citazione non prende nessun principio (elenco, sola descrizione), nessuna pagina prosegue.

DOMANDA 3. Quale FRASE DELL'ATTO sostiene la citazione? E' la frase del testo a cui e' agganciata la nota che cita il
caso, oppure la frase che contiene la citazione. Copiala ALLA LETTERA, nella sua lingua, massimo 60 parole. Il principio
si decide su questa frase, non sull'argomento della pagina.

Rispondi SOLO con un oggetto JSON:
{{"frase_sostenuta": "frase copiata alla lettera", "principi": [id...], "altro": "", "motivo": "una frase, massimo trenta parole",
  "vicine": [{{"pagina": numero, "prosegue": true o false, "principio": "id o vuoto", "prova": "frase COPIATA ALLA LETTERA dalla pagina, nella sua lingua, massimo 25 parole; mai un tuo riassunto"}}]}}
Niente fuori dal JSON."""


def leggi(a):
    import yaml
    from openai import OpenAI
    from classifica_lessicali import estrai_tollerante  # noqa
    cli = OpenAI(api_key=pathlib.Path(a.chiave_file).read_text().strip(), base_url=a.base_url, timeout=1800)
    conf = yaml.safe_load(open(QUI/'cited-cases'/f'{a.caso}.yaml', encoding='utf-8'))
    principi = '\n'.join(f"- {s['id']}: {' '.join(s['titolo'].split())}. {' '.join(s['testo'].split())}" for s in conf['semantic_queries'])
    nome_caso = conf.get('nome') or a.caso
    # With --etichetta the prompt also includes the case file (what the case decided, instance by instance and
    # paragraph by paragraph); without it the model receives only the list of principles.
    fascicolo = ''
    if a.etichetta:
        testo_f = (QUI/'cited-cases'/f'{a.caso}-fascicolo.md').read_text(encoding='utf-8')
        fascicolo = ("\nQui sotto il FASCICOLO del caso, scritto per il gruppo di ricerca: serve a sapere che cosa ha deciso e con "
                     "quali paragrafi. Le domande sono quelle in fondo.\n\n" + testo_f + "\n\n========== FINE DEL FASCICOLO ==========\n")
    suf = f'_{a.etichetta}' if a.etichetta else ''
    righe = [json.loads(l) for l in open(P/f'{a.caso}_ripresa_righe{suf}.jsonl', encoding='utf-8')]
    uscita = P/f'{a.caso}_ripresa_deepseek{suf}.jsonl'
    fatte = {json.loads(l)['id'] for l in open(uscita, encoding='utf-8')} if uscita.exists() else set()
    da_fare = [r for r in righe if r['id'] not in fatte]
    print(f'{len(righe)} righe, {len(fatte)} fatte, {len(da_fare)} da fare', flush=True)

    def testo(r):
        aiuto = ''
        if r['paragrafi']:
            aiuto = (f"La citazione indica i paragrafi {', '.join(r['paragrafi'])}; secondo la mappa dei paragrafi reggono i "
                     f"principi: {', '.join(r['principi_paragrafi']) or 'nessuno (fatti o procedura)'}.\n")
        vic = '\n\n'.join(f"--- PAGINA {v['pagina']} ---\n{v['testo']}" for v in r['vicine']) or '(nessuna pagina vicina proposta)'
        return MODULO.format(fascicolo=fascicolo, nome_caso=nome_caso, principi=principi, case_name=r.get('case_name') or '', tipo_atto=r.get('tipo_atto') or 'atto',
                             data=(r.get('data') or 's.d.')[:10], document_id=r['document_id'], forma=r.get('forma') or nome_caso,
                             contesto=r['contesto'], aiuto_paragrafi=aiuto, vicine=vic)

    def chiama(t):
        ultimo = ''
        for k in range(5):
            try:
                x = cli.chat.completions.create(model=a.modello, messages=[{'role': 'user', 'content': t}], max_tokens=8000,
                                                extra_body={'chat_template_kwargs': {'thinking': True, 'reasoning_effort': 'low'}})
                return x.choices[0].message.content or ''
            except Exception as e:
                time.sleep(5 * (k + 1)); ultimo = repr(e)[:200]
        return ''

    def una(r):
        t = testo(r)
        lett = [estrai_tollerante(chiama(t)) for _ in range(a.letture)]
        return {'id': r['id'], 'data': datetime.date.today().isoformat(), 'letture': lett}

    blocco = threading.Lock(); t0 = time.time()
    with cf.ThreadPoolExecutor(a.paralleli) as ex, open(uscita, 'a', encoding='utf-8') as f:
        for n, e in enumerate(ex.map(una, da_fare), 1):
            with blocco:
                f.write(json.dumps(e, ensure_ascii=False) + '\n'); f.flush()
            if n % 50 == 0:
                print(f'  {n}/{len(da_fare)} [{time.time()-t0:.0f}s]', flush=True)
    print(f'fatto in {time.time()-t0:.0f}s', flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('fase', choices=['prepara', 'leggi'])
    ap.add_argument('--caso', default='urgenda'); ap.add_argument('--letture', type=int, default=2)
    ap.add_argument('--etichetta', default='', help="v2 (28/09): seconda lettura con la regola delle note, solo sulle righe da fare")
    ap.add_argument('--paralleli', type=int, default=48); ap.add_argument('--modello', default='deepseek-v4-flash')
    ap.add_argument('--base-url', default='http://127.0.0.1:8000/v1'); ap.add_argument('--chiave-file', default=str(QUI/'chat'/'chiave'))
    a = ap.parse_args()
    prepara(a.caso) if a.fase == 'prepara' else leggi(a)
