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
from freni import leggibile
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
P = QUI/'training'/'principi'
SOGLIA_VICINA = 0.5
MAX_VICINE = 3
# LA FINESTRA LARGA (29/09/2026, misura `misura_finestra.py`, §63.28): il seguito si cerca fino a 10 pagine per lato.
# Vicino alla citazione (da 2 prima a 3 dopo) basta 0,5 come prima; piu' lontano serve 0,8, la soglia a cui la
# lettura del campione ha trovato seguito vero in piu' della meta' dei casi entro 10 pagine. Al massimo 5 pagine.
LARGA = 10
SOGLIA_LONTANA = 0.8
MAX_VICINE_LARGA = 5
TAGLIO_VICINA = 3500
# L11 (04/10/2026, dal controllo dei tagli): le note stanno in fondo alla pagina e la domanda dice «GUARDA LE NOTE»;
# col taglio a 3.500 caratteri 5.371 pagine su 1.837 righe perdevano la coda (35% testo rilevante, ~10% la nota che
# attribuisce la frase). Con `pagine_intere` la pagina va intera fino al tetto dell'indice delle pagine (12.000). La
# rilettura L11 delle righe gia' lette e il tetto del contesto di vLLM (ricaduta su testa e coda della pagina) stanno in
# tools/rilettura_l11.py. TAGLIO_VICINA resta per rifare identiche le letture L05 gia' fatte.
TETTO_PAGINA = 12000
# R10 (02/10/2026, col si' del PI; misura `training/misure/PERDITE-PAGINE-ATTORNO.md`): soglia 0,5 a ogni distanza dentro
# +-10 pagine e nessun tetto. Il richiamo misurato entro +-10 passa dal 27% di R08 al 57%, a 4,6 pagine lette per citazione
# invece di 2,0. Si sceglie con `prepara --regola R10`, sempre in un file con etichetta: il file vivo resta di R08.
REGOLE_FINESTRA = ('R08', 'R10')


def soglia_finestra(regola, distanza):
    """la soglia del punteggio T01 che vale a `distanza` pagine dalla citazione"""
    if regola == 'R10':
        return SOGLIA_VICINA
    return SOGLIA_VICINA if -2 <= distanza <= 3 else SOGLIA_LONTANA


def tetto_finestra(regola):
    """quante pagine al massimo (None = nessun tetto)"""
    return None if regola == 'R10' else MAX_VICINE_LARGA


def file_righe(caso, etichetta=''):
    """le righe per il lettore: con un'etichetta quelle che `leggi --etichetta` legge; senza, il file vivo"""
    import sonde as S
    return P/f'{caso}_ripresa_righe_{etichetta}.jsonl' if etichetta else P/f'{caso}_ripresa_righe{S.suf(caso)}.jsonl'


def prepara(caso, regola='R08', etichetta='', pagine_intere=False):
    import yaml
    if regola not in REGOLE_FINESTRA:
        raise SystemExit(f'regola sconosciuta: {regola}')
    if regola != 'R08' and not etichetta:
        raise SystemExit(f'{regola} vuole --etichetta: il file vivo delle righe resta di R08')
    righe = [json.loads(l) for l in open(QUI/'training'/f'lessicali_{caso}_righe.jsonl', encoding='utf-8')]
    import sonde as S
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
                if m >= soglia_finestra(regola, k - p):
                    cand.append((m, k, pid))
        cand = sorted(cand, reverse=True)[:tetto_finestra(regola)]
        scelte[r['id']] = cand
        serve |= {c[2] for c in cand}
    testi = {}
    with gzip.open(QUI/'index'/'pagine'/'pagine.jsonl.gz', 'rt', encoding='utf-8') as f:
        for l in f:
            x = json.loads(l)
            if x['id'] in serve:
                testi[x['id']] = x['testo']
    n = collections.Counter()
    uscita = file_righe(caso, etichetta)
    with open(uscita, 'w', encoding='utf-8') as f:
        for r in righe:
            cand = scelte[r['id']]
            n['con pagine vicine' if cand else 'senza pagine vicine'] += 1
            f.write(json.dumps({
                'id': r['id'], 'document_id': r['document_id'], 'case_name': r.get('case_name'), 'tipo_atto': r.get('tipo_atto'),
                'data': r.get('data'), 'pagina': r.get('pagina'), 'forma': r.get('forma'), 'contesto': r['contesto'],
                'principi_paragrafi': par.get(r['id'], {}).get('principi', []), 'paragrafi': par.get(r['id'], {}).get('paragrafi', []),
                'punteggi_brano': brano.get(r['id'], {}),
                # IL FRENO 1 (30/09/2026, `freni.py`): una pagina senza parole vere (caratteri rotti) non arriva al modello
                'vicine': [{'pagina': k, 'punteggi': vicina[pid], 'testo': testi.get(pid, '')[:TETTO_PAGINA if pagine_intere else TAGLIO_VICINA]} for _, k, pid in sorted(cand, key=lambda c: c[1]) if leggibile(testi.get(pid, ''))[0]],
                'vicine_illeggibili': [k for _, k, pid in sorted(cand, key=lambda c: c[1]) if not leggibile(testi.get(pid, ''))[0]],
            }, ensure_ascii=False) + '\n')
    print(dict(n), '->', uscita)


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
    import sonde as S
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
    # --solo-vuote (02/10/2026): si rifanno solo le letture rimaste vuote (risposta troncata dal tetto, salvata vuota
    # senza dirlo); le letture buone della stessa riga restano. La riga riscritta si accoda: vale l'ultima.
    from chiamata_deepseek import chiama as chiama_ds, vuota, tenute
    esistenti = {}
    if uscita.exists():
        for l in open(uscita, encoding='utf-8'):
            x = json.loads(l); esistenti[x['id']] = x
    aggiungi = getattr(a, 'aggiungi_letture', False)
    if aggiungi and getattr(a, 'solo_vuote', False):
        raise SystemExit('--aggiungi-letture e --solo-vuote insieme no')
    if getattr(a, 'solo_vuote', False):
        da_fare = [r for r in righe if r['id'] in esistenti and any(vuota(y) for y in esistenti[r['id']].get('letture') or [])]
    elif aggiungi:
        da_fare = None      # dopo, quando la domanda di ogni riga si sa costruire
    else:
        da_fare = [r for r in righe if r['id'] not in esistenti]
    fatte = set(esistenti)

    def testo(r):
        aiuto = ''
        if r['paragrafi']:
            aiuto = (f"La citazione indica i paragrafi {', '.join(r['paragrafi'])}; secondo la mappa dei paragrafi reggono i "
                     f"principi: {', '.join(r['principi_paragrafi']) or 'nessuno (fatti o procedura)'}.\n")
        vic = '\n\n'.join(f"--- PAGINA {v['pagina']} ---\n{v['testo']}" for v in r['vicine']) or '(nessuna pagina vicina proposta)'
        return MODULO.format(fascicolo=fascicolo, nome_caso=nome_caso, principi=principi, case_name=r.get('case_name') or '', tipo_atto=r.get('tipo_atto') or 'atto',
                             data=(r.get('data') or 's.d.')[:10], document_id=r['document_id'], forma=r.get('forma') or nome_caso,
                             contesto=r['contesto'], aiuto_paragrafi=aiuto, vicine=vic)

    # --aggiungi-letture (02/10/2026, cinque letture per riga): si tengono le letture valide gia' fatte con la STESSA
    # domanda, carattere per carattere (impronta SHA-256 scritta da chiamata_deepseek in ogni lettura), e si aggiungono
    # quelle che mancano fino a --letture. Le letture fatte con un'altra domanda (codebook, pagine attorno o contesto
    # cambiati) non si tengono: la riga si rilegge da capo.
    if aggiungi:
        tenute_di = {r['id']: tenute(esistenti.get(r['id']), testo(r)) for r in righe}
        da_fare = [r for r in righe if len(tenute_di[r['id']][0]) < a.letture]
        print(f"aggiunte: {sum(1 for r in da_fare if tenute_di[r['id']][0])} righe da completare, "
              f"{sum(1 for r in da_fare if not tenute_di[r['id']][0])} da capo, "
              f"{sum(tenute_di[r['id']][1] for r in da_fare)} letture scartate perche' la domanda e' cambiata", flush=True)
    print(f'{len(righe)} righe, {len(fatte)} fatte, {len(da_fare)} da fare', flush=True)

    def chiama(t):
        # la chiamata comune (chiamata_deepseek.py): tre tentativi identici, poi il tetto alto solo se troncata
        return chiama_ds(cli, a.modello, t, {'chat_template_kwargs': {'thinking': True, 'reasoning_effort': 'low'}},
                        temperatura=getattr(a, 'temperatura', None), seme=getattr(a, 'seme', None))

    def una(r):
        t = testo(r)
        if aggiungi:
            return una_aggiunta(r, t)
        prima = esistenti.get(r['id']) if getattr(a, 'solo_vuote', False) else None
        lett, rag, chiamate = [], [], []
        for k in range(a.letture):
            vecchia = (prima.get('letture') or [None] * a.letture)[k] if prima and k < len(prima.get('letture') or []) else None
            if prima and vecchia is not None and not vuota(vecchia):
                lett.append(vecchia); rag.append(((prima.get('ragionamenti') or [''] * a.letture)[k:k + 1] or [''])[0])
                chiamate.append(((prima.get('chiamate') or [None] * a.letture)[k:k + 1] or [None])[0] or {'tenuta': True})
                continue
            x = chiama(t)
            # il ragionamento intero (02/10/2026: prima tagliato a 6.000 caratteri)
            lett.append(estrai_tollerante(x['testo'])); rag.append(x['ragionamento']); chiamate.append(x['chiamata'])
        out = {'id': r['id'], 'data': datetime.date.today().isoformat(), 'letture': lett, 'ragionamenti': rag, 'chiamate': chiamate}
        if prima:
            out['rifatte_vuote'] = datetime.date.today().isoformat()
        return out

    def una_aggiunta(r, t):
        prima = esistenti.get(r['id']) or {}
        tenute_k, scartate = tenute_di[r['id']]
        lett = [prima['letture'][k] for k in tenute_k]
        rag = [((prima.get('ragionamenti') or [])[k:k + 1] or [''])[0] for k in tenute_k]
        chiamate = [prima['chiamate'][k] for k in tenute_k]
        for _ in range(a.letture - len(tenute_k)):
            x = chiama(t)
            lett.append(estrai_tollerante(x['testo'])); rag.append(x['ragionamento']); chiamate.append(x['chiamata'])
        return {'id': r['id'], 'data': datetime.date.today().isoformat(), 'letture': lett, 'ragionamenti': rag, 'chiamate': chiamate,
                'aggiunte': {'tenute': len(tenute_k), 'nuove': a.letture - len(tenute_k), 'scartate_domanda_cambiata': scartate,
                             'data': datetime.date.today().isoformat()}}

    blocco = threading.Lock(); t0 = time.time()
    with cf.ThreadPoolExecutor(a.paralleli) as ex, open(uscita, 'a', encoding='utf-8') as f:
        for n, e in enumerate(ex.map(una, da_fare), 1):
            with blocco:
                f.write(json.dumps(e, ensure_ascii=False) + '\n'); f.flush()
            if n % 50 == 0:
                print(f'  {n}/{len(da_fare)} [{time.time()-t0:.0f}s]', flush=True)
    print(f'fatto in {time.time()-t0:.0f}s', flush=True)


if __name__ == '__main__':
    import giornale  # il giornale delle operazioni (02/10/2026): ogni esecuzione, i file, le scritture, gli errori
    giornale.avvia()
    ap = argparse.ArgumentParser(); ap.add_argument('fase', choices=['prepara', 'leggi'])
    ap.add_argument('--caso', default='urgenda'); ap.add_argument('--letture', type=int, default=2)
    ap.add_argument('--uscita-suffisso', default='', help='suffisso in piu\' per il file di uscita (stesso ingresso)')
    ap.add_argument('--solo-vuote', action='store_true', help='02/10/2026: rifa\' solo le letture rimaste vuote, tiene le buone')
    ap.add_argument('--aggiungi-letture', action='store_true',
                    help="02/10/2026: porta ogni riga a --letture letture valide, tenendo quelle gia' fatte con la stessa domanda")
    ap.add_argument('--regola', default='R08', choices=['R08', 'R10'],
                    help="prepara: la scelta delle pagine attorno (R10, 02/10/2026: soglia 0,5 a ogni distanza, senza tetto; vuole --etichetta)")
    ap.add_argument('--pagine-intere', action='store_true',
                    help="prepara, L11 (04/10/2026): pagine attorno intere fino a 12.000 caratteri invece del taglio a 3.500 di L05")
    ap.add_argument('--etichetta', default='', help="v2 (28/09): seconda lettura con la regola delle note, solo sulle righe da fare")
    ap.add_argument('--paralleli', type=int, default=48); ap.add_argument('--modello', default='deepseek-v4-flash')
    # temperatura e seme fissi (02/10/2026): per il giro riproducibile; se non dati, i valori del modello come prima
    ap.add_argument('--temperatura', type=float, default=None); ap.add_argument('--seme', type=int, default=None)
    ap.add_argument('--base-url', default='http://127.0.0.1:8000/v1'); ap.add_argument('--chiave-file', default=str(QUI/'chat'/'chiave'))
    a = ap.parse_args()
    prepara(a.caso, a.regola, a.etichetta, a.pagine_intere) if a.fase == 'prepara' else leggi(a)
