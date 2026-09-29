"""Audit of human coding decisions on semantic-network rows for Urgenda, using DeepSeek as a second reader.

   Every Urgenda row proposed by the semantic network ('semantica' or 'entrambe') that has a human outcome
   (confirmed, reclassified, discarded) is re-read by the model. For each row the model first gives its own
   blind reading of the page, and only then sees the human decision and states whether and how it diverges.
   No validator name enters the prompt; nothing is written back to the platform.

   Phases:
     prepara  local machine, read-only from Firestore: the judged page plus the end of the previous page and the
              start of the next one (page index), and the human decision.  -> training/audit/urgenda_giudizi.jsonl
     leggi    GPU server, DeepSeek endpoint; two readings per row.       -> training/audit/urgenda_giudizi_deepseek.jsonl

   Usage: python tools/audit_giudizi.py prepara | leggi [--letture N] [--sforzo low] [--paralleli N]
"""
import argparse, collections, concurrent.futures as cf, datetime, gzip, json, pathlib, sys, threading, time
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
A = QUI/'training'/'audit'
RIGHE = A/'urgenda_giudizi.jsonl'
USCITA = A/'urgenda_giudizi_deepseek.jsonl'
MODELLO = 'DeepSeek-V4-Flash-0731'
PRIMA, DOPO = 5000, 5000
VERDETTI = ['RIPRESA_IMPLICITA', 'CITAZIONE_ESPLICITA', 'STESSO_ARGOMENTO', 'NON_PERTINENTE', 'CRONOLOGIA_IMPOSSIBILE', 'DUBBIO']
ERRORI = ['nessuno', 'holding_sbagliato', 'era_citazione_esplicita', 'argomento_da_altra_fonte',
          'menzione_descrittiva_presa_per_ripresa', 'pagina_non_pertinente_confermata', 'scartata_ma_era_ripresa',
          'nota_contraddice_esito', 'altro']


def prepara():
    import yaml
    from google.cloud import firestore
    conf = yaml.safe_load(open(QUI/'cited-cases'/'urgenda.yaml', encoding='utf-8'))
    tit = {' '.join(s['titolo'].split()): s['id'] for s in conf['semantic_queries']}
    sid = lambda t: tit.get(' '.join(str(t).replace('[2a formulazione]', '').split()), str(t))
    db = firestore.Client(project='climpact-drp')
    righe = [dict(_id=d.id, **d.to_dict()) for d in db.collection('corpus_rows')
             .where(filter=firestore.FieldFilter('caso_citato', '==', 'urgenda')).stream()]
    g = [r for r in righe if r.get('esito') and r.get('proposto_rete') in ('semantica', 'entrambe')]
    serve = {}
    for r in g:
        p = int(r.get('validato_pagina') or r.get('proposto_pagina') or 0)
        serve[r['_id']] = (r['document_id'], p)
    ids = {f'{d}#p{p+k}' for d, p in serve.values() for k in (-1, 0, 1)}
    pag = {}
    with gzip.open(QUI/'index'/'pagine'/'pagine.jsonl.gz', 'rt', encoding='utf-8') as f:
        for l in f:
            x = json.loads(l)
            if x['id'] in ids:
                pag[x['id']] = x['testo']
    A.mkdir(parents=True, exist_ok=True)
    n = collections.Counter()
    with open(RIGHE, 'w', encoding='utf-8') as f:
        for r in g:
            d, p = serve[r['_id']]
            centro = pag.get(f'{d}#p{p}', '')
            n['pagina trovata' if centro else 'pagina mancante'] += 1
            pezzi = []
            if pag.get(f'{d}#p{p-1}'):
                pezzi.append('===== PAGINA PRECEDENTE (fine) =====\n' + pag[f'{d}#p{p-1}'][-PRIMA:])
            pezzi.append(f'===== PAGINA {p} (quella giudicata) =====\n' + (centro or '[testo non disponibile]'))
            if pag.get(f'{d}#p{p+1}'):
                pezzi.append('===== PAGINA SUCCESSIVA (inizio) =====\n' + pag[f'{d}#p{p+1}'][:DOPO])
            v = r.get('validato_sonde') or []
            v = [v] if isinstance(v, str) else v
            vi = r.get('validato_il')
            f.write(json.dumps({
                'id': r['_id'], 'document_id': d, 'pagina': p, 'case_name': r.get('case_name'), 'tipo_atto': r.get('tipo_atto'),
                'data': str(r.get('data') or '')[:10], 'rete': r.get('proposto_rete'), 'sonda_proposta': sid(r.get('sonda') or ''),
                'validatore': r.get('validato_da'), 'validato_il': vi.isoformat() if hasattr(vi, 'isoformat') else str(vi or ''),
                'doppia_codifica': r.get('doppia_codifica'), 'passaggio_mostrato': r.get('proposto_citazione_testuale') or '',
                'umano': {'esito': r['esito'], 'holding': sorted({sid(x) for x in v}), 'motivo_scarto': r.get('motivo_scarto') or '',
                          'provenienza': r.get('validata_provenienza') or '', 'pertinenza': r.get('validato_pertinenza_sonda') or '',
                          'tipo_citazione': r.get('validato_tipo_citazione') or '', 'nota': r.get('validato_note') or '',
                          'proposizione': r.get('validato_proposizione') or ''},
                'contesto': '\n\n'.join(pezzi)}, ensure_ascii=False) + '\n')
            n[r['esito']] += 1
    print(dict(n), '->', RIGHE)


MODULO = """Sei un giurista che controlla la codifica di una ricerca sul contenzioso climatico.
Il caso citato e' URGENDA: Stichting Urgenda c. Stato dei Paesi Bassi (Rechtbank Den Haag 24/6/2015,
Gerechtshof Den Haag 9/10/2018, Hoge Raad 20/12/2019).

{fascicolo}

========== FINE DEL FASCICOLO ==========

I CINQUE PRINCIPI DI URGENDA che la ricerca cerca (id, paragrafo, testo):
{principi}

LA DOMANDA DELLA RICERCA. Una RIPRESA IMPLICITA e' una pagina che prende il ragionamento di Urgenda SENZA
nominare il caso, e in cui c'e' un segno concreto che il ragionamento VIENE da Urgenda: formule tipiche o
parafrasi vicine («partial responsibility», «do its part», ogni Stato risponde della propria quota, la difesa
della piccola quota respinta nei termini di Urgenda, il rischio reale che si concretizza fra decenni e colpisce
la popolazione in generale, il minimo del 25-40% ricavato dal consenso dell'IPCC, l'ordine di prendere misure
che non e' ordine di legiferare), oppure la stessa catena di passaggi. LO STESSO ARGOMENTO NON BASTA: se il
ragionamento poggia su altre fonti (giurisprudenza CEDU generale come Oneryildiz, Budayeva, Tatar; Accordo di
Parigi, UNFCCC; altre corti come Neubauer, KlimaSeniorinnen, Leghari) e niente rimanda a Urgenda, non e' una
ripresa di Urgenda.

DOCUMENTO: {case_name} ({tipo_atto}, anno {data}), documento {document_id}, pagina {pagina}.
---
{contesto}
---

PRIMA PARTE, LA TUA LETTURA. Leggi la pagina giudicata per intero, note comprese, e decidi da solo:
- "verdetto": uno fra "RIPRESA_IMPLICITA", "CITAZIONE_ESPLICITA" (la pagina nomina Urgenda o la indica in modo
  riconoscibile: «la Corte suprema olandese», «il tribunale dell'Aia», un numero ECLI:NL), "STESSO_ARGOMENTO",
  "NON_PERTINENTE" (la pagina non tratta nessuno dei cinque principi: indici, intestazioni, altro tema),
  "CRONOLOGIA_IMPOSSIBILE" (il documento e' chiaramente anteriore alla pronuncia che riprenderebbe), "DUBBIO";
- "principio": l'id del principio di Urgenda che la pagina tocca davvero, o "" se nessuno;
- "prova": una frase testuale della pagina, al massimo 25 parole, che sostiene il verdetto, o "";
- "altra_fonte": se il verdetto e' STESSO_ARGOMENTO, la fonte su cui la pagina poggia davvero, altrimenti "";
- "motivo": una frase, massimo trenta parole.

SECONDA PARTE, IL GIUDIZIO DELLA PERSONA. Solo dopo aver scritto la prima parte, e senza cambiarla, guarda che
cosa ha deciso la persona che ha codificato questa riga:
{umano}
(«confermata» = la persona dice che la pagina e' una ripresa di Urgenda sul principio indicato; «riclassificata»
= la persona ha cambiato qualcosa, e la nota dice che cosa; «scartata» = la persona dice che non e' una ripresa.)
- "accordo": true se la tua lettura e quella della persona dicono la stessa cosa sulla domanda della ricerca
  (e' o non e' una ripresa implicita di Urgenda, e su quale principio), altrimenti false;
- "errore": se non c'e' accordo, l'errore piu' probabile della persona, uno fra "holding_sbagliato",
  "era_citazione_esplicita", "argomento_da_altra_fonte", "menzione_descrittiva_presa_per_ripresa",
  "pagina_non_pertinente_confermata", "scartata_ma_era_ripresa", "nota_contraddice_esito", "altro";
  "nessuno" se c'e' accordo;
- "spiegazione": una frase, massimo trenta parole, su che cosa la persona ha visto o non ha visto.

Rispondi SOLO con un oggetto JSON con i campi in quest'ordine: verdetto, principio, prova, altra_fonte, motivo,
accordo, errore, spiegazione. Niente fuori dal JSON."""


def leggi(a):
    from openai import OpenAI
    import yaml
    from classifica_lessicali import estrai_tollerante  # noqa
    cli = OpenAI(api_key=pathlib.Path(a.chiave_file).read_text().strip(), base_url=a.base_url, timeout=1800)
    fascicolo = (QUI/'cited-cases'/'urgenda-fascicolo.md').read_text(encoding='utf-8')
    conf = yaml.safe_load(open(QUI/'cited-cases'/'urgenda.yaml', encoding='utf-8'))
    principi = '\n'.join(f"- {s['id']} (par. {s.get('canonical_paragrafo')}): {' '.join(s['canonical'].split())}"
                         for s in conf['semantic_queries'])
    righe = [json.loads(l) for l in open(RIGHE, encoding='utf-8')]
    fatte = {json.loads(l)['id'] for l in open(USCITA, encoding='utf-8')} if USCITA.exists() else set()
    da_fare = [r for r in righe if r['id'] not in fatte]
    print(f'{len(righe)} righe, {len(fatte)} gia\' fatte, {len(da_fare)} da fare', flush=True)

    def umano(u):
        parti = [f"esito: {u['esito']}", f"principio indicato: {', '.join(u['holding']) or 'nessuno'}"]
        for k, n in (('motivo_scarto', 'motivo dello scarto'), ('provenienza', 'provenienza indicata'), ('pertinenza', 'pertinenza indicata'),
                     ('tipo_citazione', 'tipo di citazione'), ('proposizione', 'proposizione'), ('nota', 'nota')):
            if u.get(k):
                parti.append(f"{n}: {' '.join(str(u[k]).split())}")
        return '\n'.join(parti)

    def chiama(testo):
        ultimo = ''
        for t in range(5):
            try:
                r = cli.chat.completions.create(model=a.modello, messages=[{'role': 'user', 'content': testo}], max_tokens=8000,
                                                extra_body={'chat_template_kwargs': {'thinking': True, 'reasoning_effort': a.sforzo}})
                m = r.choices[0].message
                return {'testo': m.content or '', 'ragionamento': getattr(m, 'reasoning_content', '') or ''}
            except Exception as e:
                time.sleep(5 * (t + 1)); ultimo = repr(e)[:200]
        return {'testo': '', 'errore': ultimo, 'ragionamento': ''}

    def una(r):
        testo = MODULO.format(fascicolo=fascicolo, principi=principi, case_name=r.get('case_name') or '', tipo_atto=r.get('tipo_atto') or 'atto',
                              data=r.get('data') or 's.d.', document_id=r['document_id'], pagina=r['pagina'], contesto=r['contesto'],
                              umano=umano(r['umano']))
        lett = [chiama(testo) for _ in range(a.letture)]
        return {'id': r['id'], 'modello': MODELLO, 'data': datetime.date.today().isoformat(),
                'letture': [estrai_tollerante(x['testo']) for x in lett], 'ragionamenti': [x['ragionamento'][:3000] for x in lett]}

    blocco = threading.Lock(); t0 = time.time()
    with cf.ThreadPoolExecutor(a.paralleli) as ex, open(USCITA, 'a', encoding='utf-8') as f:
        for n, e in enumerate(ex.map(una, da_fare), 1):
            with blocco:
                f.write(json.dumps(e, ensure_ascii=False) + '\n'); f.flush()
            if n % 20 == 0:
                print(f'  {n}/{len(da_fare)} [{time.time()-t0:.0f}s]', flush=True)
    print(f'fatto in {time.time()-t0:.0f}s', flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('fase', choices=['prepara', 'leggi'])
    ap.add_argument('--letture', type=int, default=2)
    ap.add_argument('--sforzo', default='low')
    ap.add_argument('--paralleli', type=int, default=48)
    ap.add_argument('--modello', default='deepseek-v4-flash')
    ap.add_argument('--base-url', default='http://127.0.0.1:8000/v1')
    ap.add_argument('--chiave-file', default=str(QUI/'chat'/'chiave'))
    a = ap.parse_args()
    prepara() if a.fase == 'prepara' else leggi(a)
