"""IL SEGUITO RILETTO SUI PRINCIPI PROPOSTI (L07, 30/09/2026).

   Dal 30/09 i principi proposti sulle righe da giudicare vengono da L04, il seguito da L05 (§63.35). Ma L05 ha deciso
   il seguito ragionando sui suoi principi: dove i principi sono cambiati, una pagina poteva risultare «seguito» di un
   principio che la riga non propone. Il PI: «la macchina deve fare tutto». Qui DeepSeek rilegge SOLO la domanda del
   seguito, con le istruzioni di L05 (fascicolo, regola delle note, prova copiata alla lettera), dando come fissati i
   principi che la riga propone oggi. Solo sulle righe con pagine candidate i cui principi sono cambiati.

   Fasi:
     prepara  Mac  -> training/principi/<caso>_seguito_righe.jsonl (dalla banca dati: principi proposti oggi)
     leggi    GPU  -> training/principi/<caso>_seguito_l07.jsonl
"""
import argparse, concurrent.futures as cf, datetime, json, pathlib, sys, threading, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
QUI = pathlib.Path(__file__).resolve().parent.parent
P = QUI/'training'/'principi'

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

I PRINCIPI CHE QUESTA CITAZIONE PRENDE sono gia' stabiliti: {presi}. Non rimetterli in discussione.

PAGINE VICINE DELLO STESSO ATTO (possibile seguito della ripresa, senza il nome del caso):
{vicine}

DOMANDA. Per ogni pagina vicina: prosegue LA STESSA RIPRESA? Si', solo se sviluppa uno dei principi presi dalla
citazione (quelli stabiliti sopra) dentro lo stesso ragionamento avviato dalla citazione. No, se parla d'altro,
oppure se regge lo stesso tema su un'altra fonte (CEDU generale, Accordo di Parigi, un altro caso) senza legame con
la citazione. GUARDA LE NOTE: se la frase della pagina vicina ha una sua nota che la attribuisce a un'altra fonte, non
prosegue. Il principio di una pagina che prosegue e' uno di quelli stabiliti sopra.

Rispondi SOLO con un oggetto JSON:
{{"vicine": [{{"pagina": numero, "prosegue": true o false, "principio": "id o vuoto", "prova": "frase COPIATA ALLA LETTERA dalla pagina, nella sua lingua, massimo 25 parole; mai un tuo riassunto"}}]}}
Niente fuori dal JSON."""


def prepara(caso):
    from google.cloud import firestore
    istantanea = json.load(open(QUI/'training'/'istantanea_proposte_prima_di_l04_2026-09-30.json', encoding='utf-8'))
    db = firestore.Client(project='climpact-drp')
    serve = {}
    for d in db.collection('corpus_rows').where(filter=firestore.FieldFilter('caso_citato', '==', caso)).stream():
        r = d.to_dict()
        if r.get('proposto_rete') not in ('lessicale', 'entrambe') or r.get('esito') or not r.get('proposto_estensione'):
            continue
        ora = [p for p in (r.get('proposto_principi') or []) if p not in ('nessuno',)]
        prima = set((istantanea.get(d.id) or {}).get('proposto_principi') or [])
        if set(r.get('proposto_principi') or []) == prima or not ora:
            continue   # principi uguali a quelli su cui L05 ha letto il seguito, oppure nessun principio: niente seguito
        serve[d.id] = {'presi': ora, 'altro': r.get('proposto_principio_altro') or ''}
    n = 0
    with open(P/f'{caso}_seguito_righe.jsonl', 'w', encoding='utf-8') as f:
        for l in open(P/f'{caso}_ripresa_righe_v2.jsonl', encoding='utf-8'):
            x = json.loads(l)
            if x['id'] in serve:
                f.write(json.dumps({**x, **serve[x['id']]}, ensure_ascii=False) + '\n'); n += 1
    print(caso, 'da rileggere', len(serve), 'scritte', n)


def leggi(a):
    import yaml
    from openai import OpenAI
    _m_classifica_lessicali = __import__('024_classifica_lessicali')
    estrai_tollerante = _m_classifica_lessicali.estrai_tollerante
    cli = OpenAI(api_key=pathlib.Path(a.chiave_file).read_text().strip(), base_url=a.base_url, timeout=1800)
    conf = yaml.safe_load(open(QUI/'cited-cases'/f'{a.caso}.yaml', encoding='utf-8'))
    titoli = {s['id']: ' '.join(s['titolo'].split()) for s in conf['semantic_queries']}
    principi = '\n'.join(f"- {s['id']}: {' '.join(s['titolo'].split())}. {' '.join(s['testo'].split())}" for s in conf['semantic_queries'])
    nome_caso = conf.get('nome') or a.caso
    testo_f = (QUI/'cited-cases'/f'{a.caso}-fascicolo.md').read_text(encoding='utf-8')
    fascicolo = ("\nQui sotto il FASCICOLO del caso, scritto per il gruppo di ricerca: serve a sapere che cosa ha deciso e con "
                 "quali paragrafi. Le domande sono quelle in fondo.\n\n" + testo_f + "\n\n========== FINE DEL FASCICOLO ==========\n")
    righe = [json.loads(l) for l in open(P/f'{a.caso}_seguito_righe.jsonl', encoding='utf-8')]
    uscita = P/f'{a.caso}_seguito_l07.jsonl'
    fatte = {json.loads(l)['id'] for l in open(uscita, encoding='utf-8')} if uscita.exists() else set()
    da_fare = [r for r in righe if r['id'] not in fatte]
    print(f'{len(righe)} righe, {len(fatte)} fatte, {len(da_fare)} da fare', flush=True)

    def testo(r):
        presi = '; '.join((f"{p} ({titoli[p]})" if p in titoli else f"altro: {r.get('altro') or ''}") for p in r['presi'])
        vic = '\n\n'.join(f"--- PAGINA {v['pagina']} ---\n{v['testo']}" for v in r['vicine']) or '(nessuna pagina vicina proposta)'
        return MODULO.format(fascicolo=fascicolo, nome_caso=nome_caso, principi=principi, case_name=r.get('case_name') or '',
                             tipo_atto=r.get('tipo_atto') or 'atto', data=(r.get('data') or 's.d.')[:10], document_id=r['document_id'],
                             forma=r.get('forma') or nome_caso, contesto=r['contesto'], presi=presi, vicine=vic)

    def chiama(t):
        for k in range(5):
            try:
                x = cli.chat.completions.create(model=a.modello, messages=[{'role': 'user', 'content': t}], max_tokens=8000,
                                                extra_body={'chat_template_kwargs': {'thinking': True, 'reasoning_effort': 'low'}})
                m = x.choices[0].message
                return (m.content or ''), (getattr(m, 'reasoning_content', None) or getattr(m, 'reasoning', None) or (getattr(m, 'model_extra', None) or {}).get('reasoning') or '')
            except Exception:
                time.sleep(5 * (k + 1))
        return '', ''

    def una(r):
        risposte = [chiama(testo(r)) for _ in range(a.letture)]
        return {'id': r['id'], 'data': datetime.date.today().isoformat(), 'presi': r['presi'],
                'letture': [estrai_tollerante(x) for x, _ in risposte], 'ragionamenti': [y[:6000] for _, y in risposte]}

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
    ap.add_argument('--caso', default='urgenda'); ap.add_argument('--letture', type=int, default=1)
    ap.add_argument('--paralleli', type=int, default=48); ap.add_argument('--modello', default='deepseek-v4-flash')
    ap.add_argument('--base-url', default='http://127.0.0.1:8000/v1'); ap.add_argument('--chiave-file', default=str(QUI/'chat'/'chiave'))
    a = ap.parse_args()
    prepara(a.caso) if a.fase == 'prepara' else leggi(a)
