"""DEEPSEEK LEGGE LA RIPRESA: QUALI PRINCIPI PRENDE LA CITAZIONE E FIN DOVE ARRIVA NELL'ATTO (27/09/2026).

   Sistema nuovo (§63.25). Per ogni citazione lessicale DeepSeek riceve la pagina della citazione con la
   precedente e la successiva, la lista dei principi del caso citato con i loro paragrafi, i principi che la
   mappa dei paragrafi ricava dai numeri citati, e fino a tre PAGINE VICINE dello stesso atto che il
   TRACE-Reranker giudica piu' vicine a un principio. Dice:
     - quali principi la citazione prende (anche piu' d'uno; «nessuno»; «altro» con una frase);
     - per ogni pagina vicina, se prosegue la stessa ripresa (stesso principio, stesso ragionamento avviato
       dalla citazione) o no, con una frase della pagina.
   Sono proposte per il team, mai etichette di addestramento (regola del progetto).

   Fasi:
     prepara  Mac  -> training/principi/<caso>_ripresa_righe.jsonl
     leggi    ReCaS, coda di DeepSeek -> training/principi/<caso>_ripresa_deepseek.jsonl
"""
import argparse, collections, concurrent.futures as cf, datetime, gzip, json, pathlib, sys, threading, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
_m_freni = __import__('034_freni')
leggibile = _m_freni.leggibile
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
P = QUI/'training'/'principi'
SOGLIA_VICINA = 0.5
MAX_VICINE = 3
# LA FINESTRA LARGA (29/09/2026, misura `100_misura_finestra.py`, §63.28): il seguito si cerca fino a 10 pagine per lato.
# Vicino alla citazione (da 2 prima a 3 dopo) basta 0,5 come prima; piu' lontano serve 0,8, la soglia a cui la
# lettura del campione ha trovato seguito vero in piu' della meta' dei casi entro 10 pagine. Al massimo 5 pagine.
LARGA = 10
SOGLIA_LONTANA = 0.8
MAX_VICINE_LARGA = 5
TAGLIO_VICINA = 3500


def prepara(caso):
    import yaml
    righe = [json.loads(l) for l in open(QUI/'training'/f'lessicali_{caso}_righe.jsonl', encoding='utf-8')]
    S = __import__('011_sonde')
    par = {json.loads(l)['id']: json.loads(l) for l in open(P/f'{caso}_da_paragrafi{S.suf(caso)}.jsonl', encoding='utf-8')}
    brano = collections.defaultdict(dict); vicina = collections.defaultdict(dict)
    # anche i punteggi di tutte le pagine degli atti (la misura della finestra, per ora solo Urgenda)
    # i punteggi sul testo OCR (01/10/2026) per ultimi: prendono il posto di quelli dati alle stesse pagine illeggibili
    tutti = (sorted(P.glob(f'{caso}_punteggi_*.jsonl')) + sorted(P.glob(f'{caso}_finestra_punteggi_*.jsonl'))) if S.storica(caso) \
        else sorted(P.glob(f'{caso}{S.suf(caso)}_punteggi_*.jsonl'))   # una serie in prova: solo i suoi punteggi
    for f in [f for f in tutti if '_ocr' not in f.name] + [f for f in tutti if '_ocr' in f.name]:
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
        for k in range(p - LARGA, p + LARGA + 1):
            pid = f"{r['document_id']}#p{k}"
            if k != p and k > 0 and pid in vicina:
                m = max(vicina[pid].values())
                if m >= (SOGLIA_VICINA if -2 <= k - p <= 3 else SOGLIA_LONTANA):
                    cand.append((m, k, pid))
        cand = sorted(cand, reverse=True)[:MAX_VICINE_LARGA]
        scelte[r['id']] = cand
        serve |= {c[2] for c in cand}
    testi = {}
    with gzip.open(QUI/'index'/'pagine'/'pagine.jsonl.gz', 'rt', encoding='utf-8') as f:
        for l in f:
            x = json.loads(l)
            if x['id'] in serve:
                testi[x['id']] = x['testo']
    n = collections.Counter()
    with open(P/f'{caso}_ripresa_righe{S.suf(caso)}.jsonl', 'w', encoding='utf-8') as f:
        for r in righe:
            cand = scelte[r['id']]
            n['con pagine vicine' if cand else 'senza pagine vicine'] += 1
            f.write(json.dumps({
                'id': r['id'], 'document_id': r['document_id'], 'case_name': r.get('case_name'), 'tipo_atto': r.get('tipo_atto'),
                'data': r.get('data'), 'pagina': r.get('pagina'), 'forma': r.get('forma'), 'contesto': r['contesto'],
                'principi_paragrafi': par.get(r['id'], {}).get('principi', []), 'paragrafi': par.get(r['id'], {}).get('paragrafi', []),
                'punteggi_brano': brano.get(r['id'], {}),
                # IL FRENO 1 (30/09/2026, `034_freni.py`): una pagina senza parole vere (caratteri rotti) non arriva al modello
                'vicine': [{'pagina': k, 'punteggi': vicina[pid], 'testo': testi.get(pid, '')[:TAGLIO_VICINA]} for _, k, pid in sorted(cand, key=lambda c: c[1]) if leggibile(testi.get(pid, ''))[0]],
                'vicine_illeggibili': [k for _, k, pid in sorted(cand, key=lambda c: c[1]) if not leggibile(testi.get(pid, ''))[0]],
            }, ensure_ascii=False) + '\n')
    print(dict(n), '->', P/f'{caso}_ripresa_righe{S.suf(caso)}.jsonl')


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
    _m_classifica_lessicali = __import__('024_classifica_lessicali')
    estrai_tollerante = _m_classifica_lessicali.estrai_tollerante
    cli = OpenAI(api_key=pathlib.Path(a.chiave_file).read_text().strip(), base_url=a.base_url, timeout=1800)
    S = __import__('011_sonde')
    conf = yaml.safe_load(open(S.file_caso(a.caso), encoding='utf-8'))
    principi = '\n'.join(f"- {s['id']}: {' '.join(s['titolo'].split())}. {' '.join(s['testo'].split())}" for s in conf['semantic_queries'])
    nome_caso = conf.get('nome') or a.caso
    # IL FASCICOLO DEL CASO anche in questa lettura (PI, 28/09/2026): che cosa ha deciso il caso, grado per grado e
    # paragrafo per paragrafo. Fino a V04 la lettura della ripresa riceveva solo l'elenco dei principi.
    fascicolo = ''
    if a.etichetta:
        testo_f = S.file_fascicolo(a.caso).read_text(encoding='utf-8')
        fascicolo = ("\nQui sotto il FASCICOLO del caso, scritto per il gruppo di ricerca: serve a sapere che cosa ha deciso e con "
                     "quali paragrafi. Le domande sono quelle in fondo.\n\n" + testo_f + "\n\n========== FINE DEL FASCICOLO ==========\n")
    suf = f'_{a.etichetta}' if a.etichetta else ''
    righe = [json.loads(l) for l in open(P/f'{a.caso}_ripresa_righe{suf}.jsonl', encoding='utf-8')]
    # una seconda uscita per le stesse righe (29/09/2026: rilettura per salvare il ragionamento, perso col nome sbagliato)
    uscita = P/f'{a.caso}_ripresa_deepseek{suf}{a.uscita_suffisso}.jsonl'
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
                # IL RAGIONAMENTO SI SALVA (29/09/2026): fino a L04 si teneva solo la risposta, e il portale non poteva
                # mostrare perche' la macchina aveva proposto un principio o una pagina.
                m = x.choices[0].message
                return (m.content or ''), (getattr(m, 'reasoning_content', None) or getattr(m, 'reasoning', None) or (getattr(m, 'model_extra', None) or {}).get('reasoning') or '')
            except Exception as e:
                time.sleep(5 * (k + 1)); ultimo = repr(e)[:200]
        return '', ''

    def una(r):
        t = testo(r)
        risposte = [chiama(t) for _ in range(a.letture)]
        return {'id': r['id'], 'data': datetime.date.today().isoformat(),
                'letture': [estrai_tollerante(x) for x, _ in risposte],
                'ragionamenti': [y[:6000] for _, y in risposte]}

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
    ap.add_argument('--uscita-suffisso', default='', help='suffisso in piu\' per il file di uscita (stesso ingresso)')
    ap.add_argument('--etichetta', default='', help="v2 (28/09): seconda lettura con la regola delle note, solo sulle righe da fare")
    ap.add_argument('--paralleli', type=int, default=48); ap.add_argument('--modello', default='deepseek-v4-flash')
    ap.add_argument('--base-url', default='http://127.0.0.1:8000/v1'); ap.add_argument('--chiave-file', default=str(QUI/'chat'/'chiave'))
    a = ap.parse_args()
    prepara(a.caso) if a.fase == 'prepara' else leggi(a)
