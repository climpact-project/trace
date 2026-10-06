"""IL RERANKER CHE RAGIONA E IL LETTORE CHE RAGIONA (04/10/2026, il PI: «il modello deve ragionare molto di piu', con
mille regole importanti; il reranker non deve dare solo un punteggio, deve ragionare anche lui»).

Misura sulle 137 righe col nome giudicate dal team che hanno le cinque letture (training/misure/GIURIA-2026-10-04.md).
Il giudizio del team non entra MAI in una domanda: le domande si costruiscono solo dai file d'ingresso delle letture
(contesto, pagine, paragrafi, punteggi), dal testo dell'atto, dai metadati del corpus e dalle regole; i giudizi si
leggono solo in `misure`, da training/misure/giuria_2026-10-04.json. SOLA LETTURA della banca dati (solo in `atti`).

La catena misurata (decisa dal PI il 04/10/2026, dopo tre versioni):
  1. RR, il RERANKER CHE RAGIONA (prima di DeepSeek, Qwen3.8-27B col ragionamento, 1 H100, nella coda del lavoro dei
     precedenti): legge la pagina della citazione e il suo contesto con metadati e struttura dell'atto e per OGNI principio
     del caso dice si'/no/incerto con la ragione e le parole esatte dell'atto (verificate con R14/R16). Le pagine attorno:
     cammina dalla pagina della citazione verso l'esterno, nelle due direzioni, dentro la finestra di 10 pagine; per ogni
     pagina si'/no/incerto con ragione e parole di aggancio; si ferma in una direzione dopo due «no» di fila.
       RRP  un principio per chiamata (puntuale, alla Rank1)        RRL  tutti i principi in una chiamata (a lista)
       RRC  il cammino delle pagine
     Confronto: T01 (TRACE-Reranker 0.1, solo punteggio) con le soglie di oggi (principi >= 0,5 come «suggerimenti»;
     pagine: R10, punteggio >= 0,5 entro +-10).
  2. L12, il LETTORE CHE RAGIONA (DeepSeek V4 Flash, ragionamento «high»): metadati dell'atto sempre, regole del codebook e
     dei principi, una lista di controllo campo per campo con un autocontrollo finale; decide ogni campo.
       D1  contesto di oggi (pagina della citazione con la precedente e la successiva, pagine R10 intere) + proposte T01
       D2  atto intero (o ripiego) + proposte T01
       D3  atto intero (o ripiego) + proposte ragionate di RR (si costruisce quando arrivano gli esiti di RR)
     A0 (oggi) = le cinque letture L02/L03 + L05 composte con R15, dal file della giuria.
  3. Clef e Clef-flash dopo DeepSeek: le stesse domande tipizzate, come controllo indipendente (richieste in `clef`).

Fasi:
  contesto     che cosa vede oggi il lettore sulle 137 righe (caratteri, pagine, tagli, token delle domande)
  lunghezze    lunghezza degli atti in token di DeepSeek, per caso, contro il contesto servito
  prepara      le richieste RRP, RRL, RRC (Qwen) e D1, D2 (DeepSeek, 65.536) + D2L (DeepSeek, 262.144)
  prepara-d3   le richieste D3 dagli esiti di RR
  clef         le richieste per Clef/Clef-flash dagli esiti di DeepSeek
  manda        copia richieste e corridore su ReCaS e mette i blocchi nelle code (z_ragiona_* dopo L11 e S07)
  prendi       riporta gli esiti
  misure       le misure contro il team -> training/ragionamento/misure.json e RISULTATI.md
  avanza       prendi + prepara-d3 + manda + misure, quando serve (da launchd)
Uso: .venv/bin/python tools/ragionamento.py FASE
"""
import argparse, collections, csv, gzip, hashlib, json, math, pathlib, random, re, statistics, subprocess, sys, time

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI / 'tools'))
T = QUI / 'training'
R = T / 'ragionamento'
RQ = R / 'richieste'
ES = R / 'esiti'
GIURIA = T / 'misure' / 'giuria_2026-10-04.json'
BOZZA = QUI / 'cited-cases' / 'regole-principi-BOZZA.yaml'
BOZZA_TIPO = QUI / 'docs' / 'codebook-sostanziale-descrittiva-BOZZA.md'
TOK_DS = R / 'tokenizer_dsv4' / 'tokenizer.json'
TOK_QWEN = pathlib.Path.home() / 'decisori-fuori-drive' / 'modelli' / 'qwen3.8-27b-tok' / 'tokenizer.json'
CASI = ['urgenda', 'neubauer', 'future-generations', 'klimaseniorinnen', 'cig-parere-clima', 'idh-oc-32-25']
REMOTO = 'trace/misure/ragionamento'
CODA_QWEN = 'trace/misure/precedenti/coda'        # la coda del lavoro Qwen3.8-27B dell'agente dei precedenti
CODA_DS = 'coda-ds4'
FINESTRA = 10
TETTO_PAGINA = 12000           # il tetto dell'indice delle pagine (L11)
CTX_DS = 65536                 # --max-model-len del DeepSeek di oggi (chat/vllm2.sh)
CTX_DS_LUNGO = 262144          # --max-model-len proposto (chat/vllm_lungo.sh), sotto i 295.535 token di KV misurati
USCITA_DS = 24000              # tetto della risposta di DeepSeek col ragionamento «high»
USCITA_DS_LUNGO = 32000
USCITA_QWEN = {'RRP': 6000, 'RRL': 12000, 'RRC': 5000}
MARGINE = 1024
INIZIO, FINE = '[[INIZIO DEL BRANO SEGNALATO]]', '[[FINE DEL BRANO SEGNALATO]]'
PAGINA_RE = re.compile(r'<!--\s*page\s+(\d+)\s*-->')
TIPI = ('menzione_in_catena', 'descrittiva', 'sostanziale', 'distinguente', 'critica', 'implicita')
CHI = ('corte', 'parte', 'interveniente', 'amicus', 'procuratore', 'non_determinabile')


# ── utilita' ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def jl(f):
    op = gzip.open if str(f).endswith('.gz') else open
    out = []
    if not pathlib.Path(f).exists():
        return out
    with op(f, 'rt', encoding='utf-8') as h:
        for x in h:
            try:
                out.append(json.loads(x))
            except ValueError:
                pass                    # riga troncata (lavoro interrotto a meta')
    return out


def per_id(f, chiave='id'):
    return {x[chiave]: x for x in jl(f)}


def scrivi_jl(f, righe):
    f = pathlib.Path(f); f.parent.mkdir(parents=True, exist_ok=True)
    op = gzip.open if str(f).endswith('.gz') else open
    with op(f, 'wt', encoding='utf-8') as h:
        for x in righe:
            h.write(json.dumps(x, ensure_ascii=False) + '\n')


def corto(p):
    return str(p).strip().split('.')[-1]


def spazi(t):
    return ' '.join(str(t or '').split())


def breve(t, n):
    t = spazi(t)
    return t if len(t) <= n else t[:n].rsplit(' ', 1)[0] + ' [...]'


_TOK = {}


def ntok(testo, quale='ds'):
    from tokenizers import Tokenizer
    if quale not in _TOK:
        _TOK[quale] = Tokenizer.from_file(str(TOK_DS if quale == 'ds' else TOK_QWEN))
    return len(_TOK[quale].encode(testo).ids)


def ssh(cmd, check=True):
    for _ in range(10):
        p = subprocess.run(['ssh', '-o', 'ConnectTimeout=30', '-o', 'BatchMode=yes', 'recas', cmd], capture_output=True, text=True)
        if p.returncode != 255:
            if check and p.returncode:
                raise RuntimeError(f'recas: {cmd[:100]}: {p.stderr[:300]}')
            return p.stdout
        time.sleep(30)
    raise RuntimeError('recas irraggiungibile')


def scp(a, b):
    subprocess.run(['scp', '-q', str(a), str(b)], check=True)


# ── le righe (SENZA i giudizi del team) ──────────────────────────────────────────────────────────────────────────────

INSIEME = R / 'insieme.json'          # le righe della prova, SENZA giudizi (fase insieme)
VERITA = R / 'verita.json'            # i giudizi del team: li legge SOLO la fase misure
INGRESSI = R / 'ingressi.json.gz'      # contesto, pagine R10, paragrafi, punteggi T01 di ogni riga (fase insieme)


def gruppo_di(x, giuria):
    if x['id'] in giuria:
        return 'giuria137'
    if x.get('esito') == 'confermata':
        return 'confermata'
    if x.get('esito') == 'scartata':
        return 'scartata_semantica' if x.get('proposto_rete') == 'semantica' else 'scartata_nome'
    if x.get('luglio'):
        return 'luglio'
    return 'senza_esito'


def fase_insieme(a):
    """TUTTE le righe giudicate dal team dei sei casi (coordinatore, 04/10/2026): esito (confermate e scartate, col nome e
    semantiche), giudizi di luglio (campo `luglio`), validate senza esito (validato_il). SOLA LETTURA della banca dati.
    Le 120 righe della codifica doppia alla cieca restano fuori da ogni addestramento (qui non sono giudicate: 0 in comune,
    controllato). Scrive tre file separati: insieme (senza giudizi), verita (solo giudizi), ingressi (per le domande)."""
    from google.cloud import firestore
    db = firestore.Client(project='climpact-drp')
    J = json.load(open(GIURIA, encoding='utf-8'))['righe']
    giuria = {k for k, e in J.items() if e.get('giudicata') and e.get('letta')}
    righe = {}
    for caso in CASI:
        for d in db.collection('corpus_rows').where(filter=firestore.FieldFilter('caso_citato', '==', caso)).stream():
            x = d.to_dict(); x['id'] = d.id
            if x.get('esito') or x.get('luglio') or x.get('validato_il'):
                righe[d.id] = x
    cieco = json.dumps(json.load(open(T / 'cieco_doppio_2026-10-03.json', encoding='utf-8')))
    fuori = [k for k in righe if k in cieco]
    for k in fuori:
        righe.pop(k)
    ins, ver = {}, {}
    for k, x in righe.items():
        g = gruppo_di(x, giuria)
        ins[k] = {'caso': x['caso_citato'], 'document_id': x['document_id'], 'file': x.get('file'), 'char_start': x.get('char_start'),
                  'pagina': x.get('proposto_pagina'), 'forma': x.get('proposto_forma_trovata'), 'rete': x.get('proposto_rete'),
                  'citazione_testuale': x.get('proposto_citazione_testuale'), 'ocr': bool((x.get('provenienza') or {}).get('ocr')),
                  'gruppo': g, 'case_name': x.get('case_name'), 'tipo_atto': x.get('tipo_atto'), 'data': str(x.get('data') or '')[:10],
                  # la proposta che la riga ha in banca dati: la base per le righe senza le cinque letture (P0)
                  'proposta': {kk: x.get(kk) for kk in ('proposto_tipo_citazione', 'proposto_chi_parla', 'proposto_principi',
                                                         'proposto_estensione', 'proposto_proposizione') if kk in x}}
        lu = x.get('luglio') or {}
        ver[k] = {'gruppo': g, 'esito': x.get('esito') or lu.get('esito') or None, 'tipo': x.get('validato_tipo_citazione') or None,
                  'chi': x.get('validato_chi_parla') or lu.get('validato_chi_parla') or None,
                  'principi': sorted({corto(p) for p in x.get('validato_principi') or [] if str(p).strip()}) if x.get('validato_principi') is not None else None,
                  'pagine': sorted(int(p) for p in x.get('validato_estensione') or []) if x.get('validato_estensione') is not None else None,
                  'pagine_viste': sorted(int(v['pagina']) for v in x.get('proposto_estensione') or [] if isinstance(v, dict) and 'pagina' in v),
                  'motivo_scarto': x.get('motivo_scarto') or lu.get('motivo_scarto') or None,
                  'luglio_sonde': lu.get('validato_sonde'), 'luglio_provenienza': lu.get('validata_provenienza'),
                  'validato_il': str(x.get('validato_il') or lu.get('validato_il') or '')}
    json.dump(ins, open(INSIEME, 'w', encoding='utf-8'), ensure_ascii=False, default=str)
    json.dump(ver, open(VERITA, 'w', encoding='utf-8'), ensure_ascii=False, default=str)
    # i file degli atti (anche per le righe nuove)
    F = json.load(open(R / 'file_atti.json', encoding='utf-8'))
    F.update({x['document_id']: x['file'] for x in ins.values() if x.get('file')})
    json.dump(F, open(R / 'file_atti.json', 'w', encoding='utf-8'))
    _FILE_ATTI.clear()
    ing = costruisci_ingressi(ins)
    scrivi_jl(INGRESSI, [{'id': k, **v} for k, v in ing.items()])
    print(len(ins), 'righe:', dict(collections.Counter(x['gruppo'] for x in ins.values())), '| fuori (cieco doppio):', len(fuori),
          '| ingressi:', dict(collections.Counter(v['origine'] for v in ing.values())))


def punteggi_caso(caso):
    """i punteggi T01 del caso (brano per riga, vicina per pagina), come leggi_ripresa.prepara"""
    import sonde as S
    P = T / 'principi'
    brano = collections.defaultdict(dict); vicina = collections.defaultdict(dict)
    tutti = (sorted(P.glob(f'{caso}_punteggi_*.jsonl')) + sorted(P.glob(f'{caso}_finestra_punteggi_*.jsonl'))) if S.storica(caso) \
        else sorted(P.glob(f'{caso}{S.suf(caso)}_punteggi_*.jsonl'))
    for f in [f for f in tutti if '_ocr' not in f.name] + [f for f in tutti if '_ocr' in f.name]:
        for x in jl(f):
            if x['dove'] == 'brano':
                brano[x['riga']][x['principio']] = x['punteggio']
            else:
                vicina[x['pagina_id']][x['principio']] = x['punteggio']
    return brano, vicina


def costruisci_ingressi(ins):
    """Per le righe gia' lette nel ciclo delle cinque letture o in S06 si prende il loro ingresso L05 (contesto, pagine R10,
    paragrafi, punteggi T01). Per le altre si rifa' con gli stessi strumenti: contesto di classifica_lessicali.contesto
    (pagina della citazione con la fine della precedente e l'inizio della successiva), pagine R10 dai punteggi T01 della
    finestra se ci sono, paragrafi dalla mappa (<caso>_da_paragrafi). Le righe semantiche non hanno il nome: il segno ⟦ ⟧
    resta vuoto e il brano segnalato e' quello della ricerca per descrizione."""
    import classifica_lessicali as CL, sonde as S
    from posizione_dopo_ocr import traduci
    from freni import leggibile
    out = {}
    for caso in CASI:
        mie = {k: x for k, x in ins.items() if x['caso'] == caso}
        if not mie:
            continue
        s = S.SERIE_IN_USO.get(caso, '')
        ids_ok = {corto(q['id']) for q in caso_conf(caso)['semantic_queries']}
        pronti = per_id(T / 'principi' / f'{caso}_ripresa_righe_{s}cinque.jsonl')
        pronti.update({k: v for k, v in per_id(T / 'principi' / f'{caso}_ripresa_righe_{s}s06.jsonl').items() if k not in pronti})
        par = per_id(T / 'principi' / f'{caso}_da_paragrafi{S.suf(caso)}.jsonl')
        brano, vicina = punteggi_caso(caso)
        fr = forme(caso)
        for k, x in mie.items():
            if k in pronti:
                out[k] = {**pronti[k], 'origine': 'L05 (cinque letture o S06)', 'rete': x['rete']}
                continue
            if not x.get('file') or not (QUI / x['file']).exists():
                out[k] = None; continue
            cs, _ = traduci(x['file'], int(x['char_start']), fr, x.get('ocr'))
            pag, ctx, trovato = CL.contesto(x['file'], cs, x.get('forma') or '', x.get('citazione_testuale') or '', fr or re.compile('(?!)'))
            p = int(pag or x.get('pagina') or 0)
            fm, pg = atto(x['document_id'])
            cand = []
            for kk in range(p - FINESTRA, p + FINESTRA + 1):
                pid = f"{x['document_id']}#p{kk}"
                if kk != p and kk > 0 and pid in vicina and max(vicina[pid].values()) >= 0.5:
                    cand.append(kk)
            if x['rete'] == 'semantica':
                ctx = ctx.replace('⟦⟧', '')            # senza il nome il segno resterebbe vuoto in mezzo a una parola
            out[k] = {'id': k, 'document_id': x['document_id'], 'case_name': x.get('case_name'), 'tipo_atto': x.get('tipo_atto'),
                      'data': x.get('data'), 'pagina': p, 'forma': x.get('forma'), 'contesto': ctx,
                      'principi_paragrafi': (par.get(k) or {}).get('principi', []), 'paragrafi': (par.get(k) or {}).get('paragrafi', []),
                      'punteggi_brano': {pp: v for pp, v in brano.get(k, {}).items() if corto(pp) in ids_ok},
                      'vicine': [{'pagina': kk, 'punteggi': vicina[f"{x['document_id']}#p{kk}"], 'testo': pg.get(kk, '')[:TETTO_PAGINA]}
                                 for kk in cand if kk in pg and leggibile(pg.get(kk, ''))[0]],
                      'origine': 'rifatto qui' + ('' if trovato or x['rete'] == 'semantica' else ' (nome non ritrovato)'), 'rete': x['rete']}
    return out


def righe_giuria():
    """{id: (caso, documento)} di tutte le righe della prova (insieme.json), SENZA giudizi."""
    ins = json.load(open(INSIEME, encoding='utf-8'))
    return {k: (x['caso'], x['document_id']) for k, x in ins.items()}


def gruppi():
    return {k: x['gruppo'] for k, x in json.load(open(INSIEME, encoding='utf-8')).items()}


_ING = {}


def ingressi():
    if not _ING:
        _ING.update({x['id']: x for x in jl(INGRESSI) if x.get('contesto')})
    return _ING


# ── l'atto: pagine, metadati, struttura ─────────────────────────────────────────────────────────────────────────────

_CSV = {}


def tabella(nome, chiave):
    if nome not in _CSV:
        f = QUI / 'metadata' / nome if nome != 'metadata.csv' else QUI / 'metadata.csv'
        csv.field_size_limit(10 ** 9)
        d = collections.defaultdict(list)
        with open(f, encoding='utf-8', newline='') as h:
            for r in csv.DictReader(h):
                d[r.get(chiave)].append(r)
        _CSV[nome] = d
    return _CSV[nome]


_FILE_ATTI = {}


def file_atto(doc):
    """il markdown dell'atto, dal campo «file» delle righe in banca dati (training/ragionamento/file_atti.json, fase atti)"""
    if not _FILE_ATTI:
        _FILE_ATTI.update(json.load(open(T / 'ragionamento' / 'file_atti.json', encoding='utf-8')))
    return QUI / _FILE_ATTI[doc]


_ATTI = {}


def atto(doc):
    """front matter, pagine {numero: testo} in ordine (in memoria dopo la prima lettura)"""
    if doc not in _ATTI:
        _ATTI[doc] = _atto(doc)
    return _ATTI[doc]


def _atto(doc):
    import yaml
    t = file_atto(doc).read_text(encoding='utf-8', errors='replace')
    fm = {}
    if t.startswith('---'):
        fine = t.find('\n---', 3)
        try:
            fm = yaml.safe_load(t[3:fine]) or {}
        except Exception:
            fm = {}
        t = t[fine + 4:]
    marks = [(m.start(), m.end(), int(m.group(1))) for m in PAGINA_RE.finditer(t)]
    pagine = collections.OrderedDict()
    if not marks:
        pagine[1] = t
    for i, (a, b, n) in enumerate(marks):
        fine = marks[i + 1][0] if i + 1 < len(marks) else len(t)
        pagine[n] = (pagine.get(n, '') + t[b:fine]).strip('\n')
    return fm, pagine


def metadati(doc, fm):
    """I metadati dell'atto, tutti quelli che il corpus ha: front matter, voce dell'autore, tipo e riassunto della fonte,
    cronologia del caso."""
    righe = []
    def m(nome, v):
        v = spazi(v)
        if v and v.lower() not in ('nan', 'none'):
            righe.append(f'- {nome}: {v}')
    m('titolo del documento', fm.get('document_title'))
    m('tipo di atto (corpus)', fm.get('tipo_atto'))
    m('tipo di atto (Sabin Center)', fm.get('tipo_atto_sabin'))
    m('tipo di atto dal nome del file', fm.get('tipo_atto_fonte'))
    m('caso del documento', fm.get('case_name'))
    m('nome originale del caso', fm.get('case_name_originale'))
    m('numero di causa', fm.get('numero_causa'))
    m('giurisdizioni e corte', fm.get('giurisdizioni'))
    m('paese', fm.get('geografie'))
    m('stato del caso', fm.get('stato'))
    m('data di deposito', str(fm.get('data_deposito') or '')[:10])
    m('anno di avvio del caso', fm.get('anno_avvio'))
    m('lingua', fm.get('lingue'))
    m('pagine', fm.get('pagine'))
    for r in tabella('document_voice.csv', 'document_id').get(doc, [])[:1]:
        m("voce dell'autore secondo il corpus (corte, parte, amicus, procedurale...)", f"{r.get('voice')} (da {r.get('voice_source')})")
    for r in tabella('metadata.csv', 'Document ID').get(doc, [])[:1]:
        m('tipo di documento (Sabin Center)', r.get('Document Type'))
        m('variante', r.get('Document Variant'))
        m('riassunto del documento (Sabin Center)', breve(r.get('Document Summary'), 1500))
    m('riassunto del caso (Sabin Center)', breve(fm.get('riassunto_caso'), 2500))
    ev = tabella('case_events.csv', 'case_id').get(fm.get('case_id') or '', [])
    if ev:
        m('cronologia del caso', '; '.join(f"{e.get('event_date')} {e.get('event_type')}" for e in ev[:30]))
    return '\n'.join(righe)


TITOLO_RE = re.compile(
    r'^\s{0,6}(?:(?:[IVXLC]{1,6}|[A-Z]|\d{1,3}(?:\.\d{1,3}){0,3})[\.\)]\s+\S.{2,110}'
    r'|(?:PART|CHAPTER|SECTION|TITLE|ARTICLE|PARTIE|CHAPITRE|TITRE|SECTION|CAPÍTULO|CAPITULO|TÍTULO|SECCIÓN|PARTE|CAPITOLO|'
    r'TEIL|ABSCHNITT|KAPITEL|HOOFDSTUK|DEEL)\b.{0,110}'
    r'|[A-ZÀ-ÖØ-Þ][A-ZÀ-ÖØ-Þ0-9 ,;:\'’\-–—()&/]{6,110})\s*$')


def titoli(pagine):
    """I titoli di sezione, cercati a regola (il markdown e' testo piatto): righe brevi, staccate, numerate (I., A., 1.2)
    o tutte maiuscole, o che cominciano con PART/CHAPTER/SECTION e simili in piu' lingue. Euristica dichiarata."""
    out = []
    for n, t in pagine.items():
        righe = t.split('\n')
        for i, r in enumerate(righe):
            s = r.strip()
            if not (4 <= len(s) <= 120) or not TITOLO_RE.match(r):
                continue
            if len(s.split()) > 14 or s.endswith((',', ';')) or re.fullmatch(r'[\d\W]+', s):
                continue
            if sum(c.isalpha() for c in s) < 4:
                continue
            out.append((n, s))
    # via le righe ripetute in ogni pagina (intestazioni di stampa)
    conta = collections.Counter(s for _, s in out)
    return [(n, s) for n, s in out if conta[s] <= 3]


def struttura(tit, pagina, n=80):
    """l'elenco dei titoli, i piu' vicini alla citazione se sono troppi"""
    if len(tit) > n:
        tit = sorted(sorted(tit, key=lambda x: abs(x[0] - pagina))[:n])
    return '\n'.join(f'- p. {p}: {breve(s, 120)}' for p, s in tit) or '(nessun titolo riconosciuto)'


def forme(caso):
    import yaml, sonde as S
    c = yaml.safe_load(open(S.file_caso(caso), encoding='utf-8'))
    f = sorted({str(x) for x in c.get('forme') or [] if len(str(x)) >= 4}, key=len, reverse=True)
    return re.compile('|'.join(re.escape(x) for x in f), re.I) if f else None


def sezione(tit, pagina):
    """le pagine della sezione che contiene la citazione: dall'ultimo titolo prima al primo dopo"""
    prima = [p for p, _ in tit if p <= pagina]
    dopo = [p for p, _ in tit if p > pagina]
    return (max(prima) if prima else pagina, (min(dopo) if dopo else pagina + 1))


_TOK_PAGINE = {}


def testo_atto(doc, caso, pagina, budget, quale='ds', pagine_obbligate=()):
    """L'ATTO INTERO se sta nel budget di token; altrimenti il RIPIEGO (regola fissa, in ordine di priorita'): prima e
    ultima pagina (intestazione, parti, corte, firme), la pagina della citazione con la precedente e la successiva, le
    pagine obbligate (le candidate del seguito), la sezione della citazione intera, le pagine che nominano il caso, le
    pagine piu' vicine alla citazione, il resto in ordine. Le pagine scelte vanno in ordine di documento, con il segno
    delle pagine omesse. Ritorna (testo, info)."""
    fm, pg = atto(doc)
    tit = titoli(pg)
    chiave = (doc, quale)
    if chiave not in _TOK_PAGINE:
        _TOK_PAGINE[chiave] = {n: ntok(t, quale) + 8 for n, t in pg.items()}
    tok = _TOK_PAGINE[chiave]
    intero = sum(tok.values())
    def fmt(scelte):
        out, prec = [], None
        for n in sorted(scelte):
            if prec is not None and n != prec + 1:
                out.append(f'[... pagine {prec + 1}-{n - 1} omesse ...]')
            out.append(f'[pagina {n}]\n{pg[n]}')
            prec = n
        ult = max(pg)
        if prec is not None and prec < ult:
            out.append(f'[... pagine {prec + 1}-{ult} omesse ...]')
        return '\n\n'.join(out)
    if intero <= budget:
        return fmt(pg.keys()), {'modo': 'intero', 'token_atto': intero, 'pagine': len(pg), 'pagine_date': len(pg), 'titoli': len(tit)}
    fr = forme(caso)
    ordine = []
    nn = sorted(pg)
    ordine += [nn[0], nn[-1]]
    ordine += [p for p in (pagina, pagina - 1, pagina + 1) if p in pg]
    ordine += [p for p in pagine_obbligate if p in pg]
    a, b = sezione(tit, pagina)
    ordine += [p for p in range(a, b) if p in pg and abs(p - pagina) <= 25]
    if fr:
        ordine += [p for p in nn if fr.search(pg[p])]
    ordine += sorted(nn, key=lambda p: (abs(p - pagina), p))
    scelte, usati = [], 0
    strut = ntok(struttura(tit, pagina), quale) + 200
    for p in dict.fromkeys(ordine):
        if usati + tok[p] + strut > budget:
            if p in (pagina,):          # la pagina della citazione deve esserci: si taglia attorno al brano
                continue
            continue
        scelte.append(p); usati += tok[p]
    testo = ('STRUTTURA DELL\'ATTO (titoli di sezione riconosciuti, con la pagina):\n' + struttura(tit, pagina) +
             '\n\nL\'ATTO NON STA INTERO NEL CONTESTO: seguono le pagine scelte con una regola fissa (prima e ultima pagina, '
             'la citazione e le pagine accanto, le pagine candidate, la sezione della citazione, le pagine che nominano il caso, '
             'le piu\' vicine); le altre sono segnate come omesse.\n\n' + fmt(scelte))
    return testo, {'modo': 'ripiego', 'token_atto': intero, 'pagine': len(pg), 'pagine_date': len(scelte), 'titoli': len(tit),
                   'citazione_presente': pagina in scelte}


# ── le regole ────────────────────────────────────────────────────────────────────────────────────────────────────────

def bozza():
    import yaml
    return yaml.safe_load(open(BOZZA, encoding='utf-8'))


def caso_conf(caso):
    import yaml, sonde as S
    return yaml.safe_load(open(S.file_caso(caso), encoding='utf-8'))


def mappa_voci(caso):
    import yaml, sonde as S
    m = yaml.safe_load(open(QUI / 'cited-cases' / f'{caso}-mappa-paragrafi.yaml', encoding='utf-8'))
    chiave = f'sonde_{S.serie(caso)}' if S.serie(caso) else 'sonde'
    out = collections.defaultdict(list)
    for v in m['voci']:
        for p in (v.get(chiave) if chiave in v else v.get('sonde')) or []:
            out[corto(p)].append(v)
    return out


def regole_principio(caso, s, B=None, mappa=None, lungo=True):
    B = B or bozza()
    mappa = mappa if mappa is not None else mappa_voci(caso)
    c = corto(s['id'])
    r = [f"### PRINCIPIO «{c}»: {spazi(s['titolo'])}",
         f"Definizione (dal file del caso, approvata): {spazi(s['testo'])}"]
    if s.get('probe_alternativa'):
        r.append(f"Altra formulazione (dal file del caso): {spazi(s['probe_alternativa'])}")
    if s.get('probe_es'):
        r.append(f"Formulazione in spagnolo (dal file del caso): {spazi(s['probe_es'])}")
    if s.get('elemento_proprio'):
        r.append(f"Elemento proprio, che distingue questo caso dalle altre fonti (dal file del caso, approvato): {spazi(s['elemento_proprio'])}")
    if s.get('esclusione_di_provenienza'):
        r.append(f"Esclusione di provenienza (dal file del caso, approvata): {spazi(s['esclusione_di_provenienza'])}")
    if s.get('paragrafi'):
        r.append(f"Paragrafi della decisione che lo reggono: {spazi(s['paragrafi'])}")
    if s.get('canonical'):
        r.append(f"Passo canonico ({s.get('canonical_grado') or ''} par. {s.get('canonical_paragrafo')}, p. {s.get('canonical_pagina')}): "
                 f"«{breve(s['canonical'], 1400 if lungo else 600)}»")
    for sd in (s.get('seeds') or [])[: (4 if lungo else 2)]:
        r.append(f"Altro passo della decisione (par. {sd.get('paragrafo')}): «{breve(sd.get('testo'), 450)}»")
    if s.get('lexical_markers'):
        r.append('Formule tipiche (dal file del caso): ' + '; '.join(f"{k}: {', '.join(v)}" for k, v in s['lexical_markers'].items()))
    voci = mappa.get(c) or []
    if voci:
        r.append('Paragrafi della mappa per questo principio (dalla mappa dei paragrafi):')
        for v in voci[: (10 if lungo else 5)]:
            par = v.get('paragrafo') or v.get('paragrafi')
            dove = v.get('pronuncia') or ''
            r.append(f"  - par. {par} {dove}: {breve(v.get('sintesi'), 280)}" + (f" «{breve(v.get('verbatim'), 220)}»" if v.get('verbatim') else ''))
    bz = (B.get('principi') or {}).get(c) or {}
    for k, nome in (('includere', 'Quando si prende'), ('escludere', 'Quando no'), ('confini', 'Confini con gli altri principi del caso'),
                    ('controesempi', 'Controesempi')):
        if bz.get(k):
            r.append(f'{nome} (BOZZA, non approvata): ' + ' | '.join(spazi(x) for x in bz[k]))
    if bz.get('formule'):
        r.append('Formule tipiche di chi cita (BOZZA, non approvata): ' + '; '.join(f"{k}: {', '.join(v)}" for k, v in bz['formule'].items()))
    return '\n'.join(r)


def regole_generali(B=None):
    B = B or bozza()
    return '\n'.join(f"- {g['id']} ({g['fonte']}): {spazi(g['testo'])}" for g in B['regole_generali'])


def regole_chi(B=None):
    import yaml
    B = B or bozza()
    cb = yaml.safe_load(open(QUI / 'codebook' / 'citazioni.yaml', encoding='utf-8'))
    codici = '\n'.join(f'- "{c["codice"]}": {c["nome"]}' for c in cb['chi_parla'])
    return codici + '\nRegole:\n' + '\n'.join(f"- {g['id']} ({g['fonte']}): {spazi(g['testo'])}" for g in B['chi_parla_regole'])


def regole_tipo():
    """definizioni del codebook 0.5 (approvate) + le domande in ordine della BOZZA sostanziale/descrittiva (non approvata)"""
    import classifica_lessicali as CL
    cb, tipi, _, limiti = CL.codebook()
    t = BOZZA_TIPO.read_text(encoding='utf-8')
    a = t.find('## Le domande, in ordine'); b = t.find('## Esempi')
    dom = t[a:b].strip() if a >= 0 and b > a else ''
    return (f'Categorie del codebook (versione {cb["versione"]}, approvate), esclusive:\n{tipi}\n\nCasi limite del codebook:\n{limiti}\n\n'
            'Criterio per decidere (BOZZA del 03/10/2026, docs/codebook-sostanziale-descrittiva-BOZZA.md, non approvata):\n' + dom)


# ── le domande ───────────────────────────────────────────────────────────────────────────────────────────────────────

def brano(r, prima=1500, dopo=1500):
    ctx = r['contesto']
    a, b = ctx.find(INIZIO), ctx.find(FINE)
    if a < 0 or b < 0:
        return ctx[:4000]
    return ctx[max(0, a - prima): b + len(FINE) + dopo]


def blocco_riga(r, caso, conf):
    if r.get('rete') == 'semantica':
        return (f"IL BRANO DA GIUDICARE. Documento {r['document_id']}, pagina {r.get('pagina')}. La ricerca PER DESCRIZIONE "
                f"(semantica) ha segnalato il brano fra {INIZIO} e {FINE} come possibile RIPRESA del caso {conf.get('nome')} "
                f"(decisione del {conf.get('data_decisione')}): il nome del caso NON compare nel brano. Prima di tutto va deciso "
                "se il brano riprende davvero quel caso (anche senza nominarlo) o un'altra fonte, o non c'entra.")
    return (f"LA CITAZIONE DA GIUDICARE. Documento {r['document_id']}, pagina {r.get('pagina')}. La rete lessicale ha trovato "
            f"«{r.get('forma') or conf.get('nome')}» nel punto marcato con ⟦ ⟧, dentro il brano fra {INIZIO} e {FINE}. "
            f"Il caso citato e' {conf.get('nome')} (decisione del {conf.get('data_decisione')}).")


def aiuto_paragrafi(r):
    if not r.get('paragrafi'):
        return 'La citazione non indica numeri di paragrafo riconosciuti dalla mappa.'
    return (f"La citazione indica i paragrafi {', '.join(r['paragrafi'])}; secondo la mappa dei paragrafi reggono i principi: "
            f"{', '.join(corto(p) for p in r['principi_paragrafi']) or 'nessuno (fatti o procedura)'}.")


ISTR_RR = """Sei il RERANKER CHE RAGIONA di TRACE, una ricerca sul contenzioso climatico. Il tuo lavoro viene PRIMA del lettore
finale (un altro modello che legge l'atto intero e decide): tu gli passi proposte motivate. Un tuo «no» sbagliato fa
perdere un principio per sempre; un «incerto» viene riletto. Quindi: quando non sei sicuro, rispondi «incerto».
Le parole che citi dall'atto devono essere COPIATE ALLA LETTERA dal testo dell'atto qui sotto (le controlla un programma
parola per parola): mai un tuo riassunto, mai il testo delle regole o della definizione del principio.
Alla fine del ragionamento, per ogni verdetto dai anche un PUNTEGGIO da 0 a 1 (la probabilita' che la risposta giusta sia «si»):
serve a ordinare e a scegliere una soglia, e viene mostrato accanto al tuo ragionamento."""


def domanda_rr_principi(r, caso, conf, meta, strut, principi_testo, uno=None):
    """RRP (uno=il principio) e RRL (tutti)"""
    if uno:
        q = (f"DOMANDA. La citazione prende il principio «{uno}»? Prendere = usa, applica, discute, respinge o riferisce la "
             "ragione del caso su quel punto (regole generali G01-G08). Ragiona passo per passo: (1) quale frase la citazione "
             "sostiene; (2) che cosa attribuisce al caso; (3) se e' il principio, alla luce di definizione, elemento proprio, "
             "esclusioni e confini; (4) controlla i controesempi.\n"
             'Rispondi SOLO con un oggetto JSON: {"principio": "' + uno + '", "esito": "si" | "no" | "incerto", '
             '"ragione": "massimo 60 parole", "parole": "le parole dell\'atto che prendono il principio, copiate alla lettera, '
             'massimo 40 parole; vuoto se no", "punteggio": numero da 0 a 1, quanto e\' probabile che la citazione prenda il principio}')
    else:
        q = ("DOMANDA. Per OGNI principio dell'elenco (nessuno escluso): la citazione lo prende? Prendere = usa, applica, "
             "discute, respinge o riferisce la ragione del caso su quel punto (regole generali G01-G08). Per ognuno ragiona: "
             "quale frase la citazione sostiene, che cosa attribuisce al caso, se e' quel principio alla luce di definizione, "
             "elemento proprio, esclusioni e confini.\n"
             "Prima pero': il brano CITA o RIPRENDE davvero il caso (non un indice, non un omonimo, non un'altra fonte)?\n"
             'Rispondi SOLO con un oggetto JSON: {"cita_il_caso": {"esito": "si" | "no" | "incerto", "ragione": "massimo 40 parole", "punteggio": numero da 0 a 1}, '
             '"principi": [{"principio": "id", "esito": "si" | "no" | "incerto", '
             '"ragione": "massimo 40 parole", "parole": "parole dell\'atto copiate alla lettera, massimo 40; vuoto se no", '
             '"punteggio": numero da 0 a 1}, ...], '
             '"altro": "una frase se la citazione prende qualcosa che non e\' nell\'elenco, altrimenti vuoto"}')
    blocchi_riga = ['METADATI DELL\'ATTO CHE CITA:\n' + meta,
                    'STRUTTURA DELL\'ATTO (titoli di sezione riconosciuti, con la pagina):\n' + strut,
                    blocco_riga(r, caso, conf),
                    'LA PAGINA DELLA CITAZIONE, con la fine della precedente e l\'inizio della successiva:\n---\n' + r['contesto'] + '\n---',
                    aiuto_paragrafi(r)]
    regole = f"I PRINCIPI DEL CASO CITATO ({conf.get('nome')}), con le loro regole:\n" + principi_testo
    # l'ordine conta per la cache dei prefissi di vLLM: a lista le regole (uguali per tutto il caso) vanno prima della riga;
    # un principio alla volta la riga (uguale per i 5-8 principi) va prima delle regole del principio
    corpo = ([regole] + blocchi_riga) if not uno else (blocchi_riga + [f"IL PRINCIPIO DA GIUDICARE ({conf.get('nome')}), con le sue regole:\n" + principi_testo])
    return '\n\n'.join([ISTR_RR, 'REGOLE GENERALI SUI PRINCIPI:\n' + regole_generali()] + corpo + [q])


def domanda_rr_cammino(r, caso, conf, meta, strut):
    """il prefisso comune del cammino; il corridore aggiunge la pagina e il passo precedente (MODELLO_PASSO)"""
    return '\n\n'.join([
        ISTR_RR,
        'COMPITO: le PAGINE ATTORNO. Si legge l\'atto come un lettore, dalla pagina della citazione verso l\'esterno, una pagina '
        'alla volta. Per la pagina che ti do decidi se CONTINUA IL RAGIONAMENTO SUL CASO CITATO avviato dalla citazione (o lo '
        'prepara, se e\' prima): stesso punto, stesso argomento. Indizi di aggancio: rinvii espliciti («that judgment», «the '
        'Court further held», «ibid.», «supra»), la stessa sezione o lo stesso titolo d\'argomento, paragrafi numerati che '
        'proseguono lo stesso punto, note che citano di nuovo il caso. NON continua se l\'atto e\' passato ad altro argomento '
        'o regge lo stesso tema su un\'altra fonte (un altro caso, un trattato): GUARDA LE NOTE, una frase con una sua nota '
        'che la attribuisce a un\'altra fonte non continua (codebook 0.5, approvato).',
        f"Il caso citato: {conf.get('nome')}. Principi del caso (solo i titoli): " +
        '; '.join(f"{corto(s['id'])}: {spazi(s['titolo'])}" for s in conf['semantic_queries']),
        'METADATI DELL\'ATTO CHE CITA:\n' + meta,
        'STRUTTURA DELL\'ATTO (titoli di sezione riconosciuti, con la pagina):\n' + strut,
        blocco_riga(r, caso, conf),
        'LA PAGINA DELLA CITAZIONE, con la fine della precedente e l\'inizio della successiva:\n---\n' + r['contesto'] + '\n---'])


MODELLO_PASSO = """{precedente}
LA PAGINA DA GIUDICARE: pagina {pagina} ({verso} della citazione, a {distanza} pagine).
---
{testo}
---
Rispondi SOLO con un oggetto JSON: {{"pagina": {pagina}, "esito": "si" | "no" | "incerto", "principio": "id del principio che continua, o vuoto",
"ragione": "massimo 50 parole", "parole": "le parole di aggancio della pagina, copiate alla lettera, massimo 30 parole; vuoto se no",
"punteggio": numero da 0 a 1, quanto e' probabile che la pagina continui il ragionamento}}"""


ISTR_L12 = """Sei un giurista che codifica citazioni giurisprudenziali per TRACE, una ricerca sul contenzioso climatico. Devi
RAGIONARE A LUNGO e con ordine, seguendo la LISTA DI CONTROLLO in fondo, campo per campo, e alla fine CONTROLLARE la tua
risposta contro le regole, correggendola se ne violi una. I metadati e la struttura dell'atto vanno usati: chi ha scritto
l'atto, che tipo di atto e', in che fase del procedimento, in che sezione sta la citazione."""


def lista_controllo(conf, ids_principi, candidate, rete=''):
    nome = conf.get('nome')
    if rete == 'semantica':
        uno = f"""1. RIPRENDE IL CASO? Il brano riprende il ragionamento di {nome} (anche senza nominarlo: tipo «implicita»; o lo nomina
   altrove nella pagina), oppure regge lo stesso tema su un'altra fonte (un altro caso, un trattato, una legge), oppure non
   c'entra? «caso» (ripresa del caso), «altra_fonte», «non_pertinente», «non_determinabile». Se non e' «caso», gli altri
   campi si danno lo stesso ma i principi sono tutti «no»."""
    else:
        uno = f"""1. CITA IL CASO? Il punto ⟦ ⟧ e' {nome} (una delle sue pronunce) o altro: «caso», «soggetto_omonimo» (la persona o
   l'organizzazione che porta il nome, non la sentenza), «indice_o_elenco» (indice, sommario, tavola delle fonti, elenco
   degli allegati: regola del codebook 0.5 sulle pagine d'indice), «omonimo», «non_determinabile»."""
    return f"""LISTA DI CONTROLLO (rispondi a ogni punto ragionando sul testo; poi il JSON).
{uno}
2. QUALE DECISIONE ESATTAMENTE: grado, data, paragrafi citati (dal testo e dalla nota), se si capisce.
3. TIPO DI CITAZIONE: segui le domande in ordine del criterio (1-6) e la prova della cancellazione; scrivi quale domanda
   decide. La nota prende il tipo della frase del corpo a cui e' agganciata.
4. CHI PARLA: guarda metadati (tipo di atto, voce dell'autore), prima e ultima pagina (intestazione, firme), titolo della
   sezione; poi le regole C01-C06. Distingui la corte che decide dalla corte che riassume una difesa.
5. PROPOSIZIONE: una frase in italiano, che cosa il testo dice che il caso ha stabilito o che cosa ne ricava.
6. FRASE SOSTENUTA: la frase dell'atto a cui e' agganciata la nota che cita il caso, o la frase che contiene la citazione,
   COPIATA ALLA LETTERA nella sua lingua (massimo 60 parole). Il principio si decide su questa frase (G01).
7. PRINCIPI: per OGNI principio dell'elenco ({', '.join(ids_principi)}) si', no o incerto, con la ragione e le parole
   dell'atto copiate alla lettera. Regole G01-G08. Le proposte del reranker sono un aiuto, non una decisione: puoi
   rovesciarle, dicendo perche'.
8. PAGINE ATTORNO: per ogni pagina candidata ({', '.join(str(p) for p in candidate) or 'nessuna'}) prosegue la stessa ripresa?
   Si', solo se sviluppa un principio preso dalla citazione dentro lo stesso ragionamento; no se parla d'altro o regge lo
   stesso tema su un'altra fonte (guarda le note). Se vedi nell'atto un'altra pagina entro 10 dalla citazione che prosegue,
   aggiungila. La prova: parole della pagina copiate alla lettera.
9. AUTOCONTROLLO: rileggi la risposta contro le regole (tipo, chi parla, G01-G08, pagine) e correggi.

Rispondi SOLO con un oggetto JSON:
{{"riferimento": "...", "decisione_citata": "...", "tipo_citazione": "uno dei 6 codici", "regola_tipo": "quale domanda del criterio decide, una frase",
  "chi_parla": "uno dei codici", "chi_parla_perche": "una frase", "proposizione": "...", "frase_sostenuta": "alla lettera",
  "principi": [{{"principio": "id", "esito": "si" | "no" | "incerto", "ragione": "massimo 40 parole", "parole": "alla lettera, massimo 40"}}, ...],
  "altro": "una frase o vuoto",
  "pagine": [{{"pagina": numero, "prosegue": true | false, "principio": "id o vuoto", "prova": "alla lettera, massimo 25 parole"}}, ...],
  "autocontrollo": [{{"regola": "...", "rispettata": true | false, "correzione": "..."}}, ...]}}
Niente fuori dal JSON."""


def proposte_t01(r):
    sc = sorted(((corto(p), v) for p, v in (r.get('punteggi_brano') or {}).items()), key=lambda x: -x[1])
    pg = [(v['pagina'], max(v['punteggi'].values()) if v.get('punteggi') else None) for v in r.get('vicine') or []]
    return ('PROPOSTE DEL RERANKER (T01, TRACE-Reranker 0.1: solo un punteggio da 0 a 1 fra il principio e il brano, senza '
            'ragionamento; addestrato su etichette di luglio, da usare come indizio debole):\n'
            '- principi: ' + '; '.join(f'{p} {v:.2f}' for p, v in sc) + '\n'
            '- pagine attorno scelte da R10 (punteggio massimo di un principio almeno 0,5, entro 10 pagine): ' +
            ('; '.join(f'p. {p} ({s:.2f})' for p, s in pg) if pg else 'nessuna'))


def proposte_rr(rr, modello='Qwen'):
    """il testo delle proposte ragionate di RR (principi da RRP o RRL, pagine dal cammino RRC), con l'esito della verifica"""
    out = [f'PROPOSTE DEL RERANKER CHE RAGIONA ({modello}, un passo prima di te; le parole sono state controllate da un '
           'programma: «trovate» = sono davvero nell\'atto). Sono proposte: decidi tu.']
    for p in rr.get('principi') or []:
        out.append(f"- principio {p['principio']}: {p['esito']}. {breve(p.get('ragione'), 300)}" +
                   (f" Parole: «{breve(p.get('parole'), 300)}» ({p.get('verifica')})" if p.get('parole') else ''))
    if rr.get('altro'):
        out.append(f"- altro: {breve(rr['altro'], 200)}")
    for p in rr.get('pagine') or []:
        out.append(f"- pagina {p['pagina']}: {p['esito']}" + (f" (principio {p.get('principio')})" if p.get('principio') else '') +
                   f". {breve(p.get('ragione'), 250)}" + (f" Parole: «{breve(p.get('parole'), 200)}» ({p.get('verifica')})" if p.get('parole') else ''))
    if rr.get('fermate'):
        out.append('- il cammino si e\' fermato: ' + '; '.join(f'{k}: {v}' for k, v in rr['fermate'].items()))
    return '\n'.join(out)


def domanda_l12(r, caso, conf, meta, corpo_contesto, proposte, candidate):
    ids = [corto(s['id']) for s in conf['semantic_queries']]
    B = bozza(); mappa = mappa_voci(caso)
    principi_testo = '\n\n'.join(regole_principio(caso, s, B, mappa, lungo=False) for s in conf['semantic_queries'])
    # l'ordine conta per la cache dei prefissi di vLLM: istruzioni e regole (uguali per il caso), poi l'atto (uguale per
    # tutte le righe dello stesso atto), poi la riga
    return '\n\n'.join([
        ISTR_L12,
        'REGOLE DEL TIPO DI CITAZIONE:\n' + regole_tipo(),
        'CHI PARLA (codici del codebook 0.5):\n' + regole_chi(B),
        'REGOLE GENERALI SUI PRINCIPI:\n' + regole_generali(B),
        f"I PRINCIPI DEL CASO CITATO ({conf.get('nome')}, decisione del {conf.get('data_decisione')}), con le loro regole:\n" + principi_testo,
        'METADATI DELL\'ATTO CHE CITA:\n' + meta,
        corpo_contesto,
        blocco_riga(r, caso, conf),
        'IL BRANO DELLA CITAZIONE (con i segni; la pagina intera e\' sopra):\n---\n' + brano(r) + '\n---',
        aiuto_paragrafi(r),
        proposte,
        lista_controllo(conf, ids, candidate, r.get('rete', ''))])


def contesto_oggi(r):
    """D1: la pagina della citazione con la precedente e la successiva (come L02-L05) e le pagine R10 INTERE (come L11)"""
    fm, pg = atto(r['document_id'])
    vic = '\n\n'.join(f"--- PAGINA {v['pagina']} ---\n{pg.get(v['pagina'], v['testo'])[:TETTO_PAGINA]}" for v in r.get('vicine') or [])
    return ('LA PAGINA DELLA CITAZIONE, con la fine della precedente e l\'inizio della successiva:\n---\n' + r['contesto'] +
            '\n---\n\nPAGINE ATTORNO CANDIDATE (scelte da R10), intere:\n' + (vic or '(nessuna)'))


# ── prepara ──────────────────────────────────────────────────────────────────────────────────────────────────────────

def immagine_citazione(doc, p):
    return f'{doc}__p{p}.jpg'


def richiesta_d(rid, nome, ctx, usc, proposte, cand, priorita, gruppo):
    """una domanda al lettore che ragiona (L12) con l'atto intero o il ripiego, nel budget del contesto servito"""
    caso, doc = righe_giuria()[rid]; r = ingressi()[rid]
    conf = caso_conf(caso); fm, pg = atto(doc); meta = metadati(doc, fm); p = int(r.get('pagina') or 0)
    fisso = ntok(domanda_l12(r, caso, conf, meta, '', proposte, cand)) + 300
    corpo, inf = testo_atto(doc, caso, p, ctx - usc - MARGINE - fisso, 'ds', cand)
    t = domanda_l12(r, caso, conf, meta, 'L\'ATTO CHE CITA:\n' + corpo, proposte, cand)
    return {'id': rid, 'chiave': f'{nome}|{rid}', 'gruppo': gruppo, 'priorita': priorita, 'testo': t, 'token': ntok(t), 'atto': inf,
            'ctx': ctx, 'tetto': usc}


def fase_prepara(a):
    """Le richieste di tutta la batteria (prova a secco: si contano i token, nessuna GPU)."""
    RQ.mkdir(parents=True, exist_ok=True)
    ing = ingressi(); ids = righe_giuria(); gr = gruppi()
    B = bozza()
    from freni import leggibile
    rrp, rrl, rri, rrc, dp, dt, dtl, info = [], [], [], [], [], [], [], {}
    # prima le 137 righe della giuria (priorita' 0): se un lavoro si ferma a meta', quel sottoinsieme e' gia' completo
    ordine = sorted(ids, key=lambda k: (gr[k] != 'giuria137', ids[k][0], ids[k][1], k))
    for rid in ordine:
        caso, doc = ids[rid]; r = ing[rid]
        conf = caso_conf(caso); mappa = mappa_voci(caso)
        fm, pg = atto(doc)
        meta = metadati(doc, fm)
        p = int(r.get('pagina') or 0)
        strut = struttura(titoli(pg), p, 60)
        gruppo = f'{caso}|{doc}'; pr = 0 if gr[rid] == 'giuria137' else 1
        tutti = '\n\n'.join(regole_principio(caso, q, B, mappa) for q in conf['semantic_queries'])
        t = domanda_rr_principi(r, caso, conf, meta, strut, tutti)
        rrl.append({'id': rid, 'chiave': f'RRL|{rid}', 'gruppo': gruppo, 'priorita': pr, 'tetto': USCITA_QWEN['RRL'], 'testo': t})
        # R2: la stessa domanda con l'IMMAGINE della pagina della citazione (il reranker deve vedere la pagina)
        ti = t.replace('LA PAGINA DELLA CITAZIONE, con la fine della precedente',
                       "Ti do anche l'IMMAGINE della pagina della citazione (pagina " + str(p) + "): guardala, soprattutto le note "
                       "a pie' di pagina, i titoli e a quale frase e' agganciato il richiamo di nota. Le parole che copi vanno prese dal "
                       "testo qui sotto.\nLA PAGINA DELLA CITAZIONE, con la fine della precedente", 1)
        rri.append({'id': rid, 'chiave': f'RRI|{rid}', 'gruppo': gruppo, 'priorita': pr, 'tetto': USCITA_QWEN['RRL'], 'testo': ti,
                    'immagini': [immagine_citazione(doc, p)]})
        for q in conf['semantic_queries']:
            c = corto(q['id'])
            rrp.append({'id': rid, 'chiave': f'RRP|{rid}|{c}', 'gruppo': gruppo, 'priorita': pr, 'tetto': USCITA_QWEN['RRP'], 'principio': c,
                        'testo': domanda_rr_principi(r, caso, conf, meta, strut, regole_principio(caso, q, B, mappa), uno=c)})
        pagine = []
        for k in range(p - FINESTRA, p + FINESTRA + 1):
            if k != p and k in pg:
                ok = leggibile(pg[k])[0]
                pagine.append({'pagina': k, 'testo': pg[k][:TETTO_PAGINA] if ok else '', 'leggibile': ok})
        rrc.append({'id': rid, 'chiave': f'RRC|{rid}', 'gruppo': gruppo, 'priorita': pr, 'tetto': USCITA_QWEN['RRC'], 'modo': 'cammino',
                    'citazione': p, 'pagine': pagine, 'prefisso': domanda_rr_cammino(r, caso, conf, meta, strut),
                    'passo': MODELLO_PASSO, 'r10': [v['pagina'] for v in r.get('vicine') or []]})
        # DeepSeek coi soli punteggi di T01: DP (contesto di oggi), DT (atto intero o ripiego, 65.536), DTL (262.144)
        cand = [v['pagina'] for v in r.get('vicine') or []]
        prop = proposte_t01(r)
        t1 = domanda_l12(r, caso, conf, meta, contesto_oggi(r), prop, cand)
        dp.append({'id': rid, 'chiave': f'DP|{rid}', 'gruppo': gruppo, 'priorita': pr, 'testo': t1, 'token': ntok(t1), 'tetto': USCITA_DS})
        x = richiesta_d(rid, 'DT', CTX_DS, USCITA_DS, prop, cand, pr, gruppo); dt.append(x)
        y = richiesta_d(rid, 'DTL', CTX_DS_LUNGO, USCITA_DS_LUNGO, prop, cand, pr, gruppo); dtl.append(y)
        info[rid] = {'DT': x['atto'], 'DTL': y['atto'], 'gruppo': gr[rid]}
    for nome, xs in (('rrl', rrl), ('rri', rri), ('rrp', rrp), ('rrc', rrc), ('dp', dp), ('dt', dt), ('dtl', dtl)):
        scrivi_jl(RQ / f'{nome}.jsonl.gz', xs)
    json.dump(info, open(R / 'atti_info.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    secco(a)


def secco(a):
    """La prova a secco: token di ogni richiesta (tokenizzatore di DeepSeek per DeepSeek, di Qwen3.8 per Qwen) e quanto
    entra intero; scrive training/ragionamento/secco.json (le stime di tempo GPU stanno nel documento della misura)."""
    out = {}
    info = json.load(open(R / 'atti_info.json', encoding='utf-8'))
    for nome, quale in (('rrl', 'qwen'), ('rri', 'qwen'), ('rrp', 'qwen'), ('rrc', 'qwen'), ('dp', 'ds'), ('dt', 'ds'), ('dtl', 'ds')):
        X = jl(RQ / f'{nome}.jsonl.gz')
        if nome == 'rrc':
            pref = [ntok(x['prefisso'], quale) for x in X]
            pag = [ntok(pp['testo'], quale) for x in X for pp in x['pagine'] if pp['testo']]
            out[nome] = {'richieste': len(X), 'pagine_nella_finestra_media': round(statistics.mean(len(x['pagine']) for x in X), 2),
                         'prefisso_token_mediana': statistics.median(pref), 'pagina_token_mediana': statistics.median(pag),
                         'righe_137': sum(1 for x in X if x.get('priorita') == 0)}
            continue
        tk = [x.get('token') or ntok(x['testo'], quale) for x in X]
        out[nome] = {'richieste': len(X), 'righe_137': sum(1 for x in X if x.get('priorita') == 0), 'token_mediana': statistics.median(tk),
                     'token_p90': sorted(tk)[int(.9 * len(tk))], 'token_max': max(tk), 'token_somma': sum(tk)}
    for nome in ('DT', 'DTL'):
        v = [x[nome] for x in info.values()]
        out[nome + '_atto'] = {'intero': sum(1 for x in v if x['modo'] == 'intero'), 'ripiego': sum(1 for x in v if x['modo'] == 'ripiego'),
                               'intero_137': sum(1 for k, x in info.items() if x['gruppo'] == 'giuria137' and x[nome]['modo'] == 'intero')}
    gruppi_atto = collections.Counter(x['gruppo'] for x in jl(RQ / 'dt.jsonl.gz'))
    out['atti_distinti'] = len(gruppi_atto); out['righe_per_atto_media'] = round(statistics.mean(gruppi_atto.values()), 2)
    json.dump(out, open(R / 'secco.json', 'w', encoding='utf-8'), indent=1)
    print(json.dumps(out, indent=1))


def fase_prepara_dr(a):
    """DR (il D1 della batteria): atto intero o ripiego + metadati + regole + proposte RAGIONATE del reranker (principi a
    lista RRL o, con --immagine, RRI; pagine dal cammino RRC) del modello --rr (q9 = Qwen3.5-9B, q27 = Qwen3.8-27B)."""
    ids = righe_giuria(); gr = gruppi()
    quale = 'RRI' if a.immagine else 'RRL'
    rr = esiti_rr(quale, a.rr)
    nome_modello = {'q9': 'Qwen3.5-9B', 'q27': 'Qwen3.8-27B'}[a.rr]
    ctx, usc, nome = (CTX_DS_LUNGO, USCITA_DS_LUNGO, 'DRL') if a.lungo else (CTX_DS, USCITA_DS, 'DR')
    out = []
    for rid in sorted(rr, key=lambda k: (gr[k] != 'giuria137', ids[k][0], ids[k][1], k)):
        caso, doc = ids[rid]
        cand = sorted(pp['pagina'] for pp in rr[rid].get('pagine') or [] if pp['esito'] in ('si', 'incerto'))
        out.append(richiesta_d(rid, nome, ctx, usc, proposte_rr(rr[rid], nome_modello), cand, 0 if gr[rid] == 'giuria137' else 1, f'{caso}|{doc}'))
    f = RQ / f"{nome.lower()}_{a.rr}.jsonl.gz"
    scrivi_jl(f, out)
    print(len(out), 'richieste', f.name)
    return f


def immagini(a):
    """le immagini delle pagine della citazione (150 dpi, PyMuPDF), come la prova dei precedenti; quelle che ha gia' fatto
    quella prova si copiano. Fuori da Drive: ~/decisori-fuori-drive/ragionamento/pagine. Poi un tar per ReCaS."""
    import fitz, shutil
    dove = pathlib.Path.home() / 'decisori-fuori-drive' / 'ragionamento' / 'pagine'; dove.mkdir(parents=True, exist_ok=True)
    loro = pathlib.Path.home() / 'decisori-fuori-drive' / 'precedenti' / 'pagine'
    ing = ingressi(); ids = righe_giuria(); c = collections.Counter()
    for rid, (caso, doc) in ids.items():
        p = int(ing[rid].get('pagina') or 0); nome = immagine_citazione(doc, p)
        if (dove / nome).exists():
            c['gia'] += 1; continue
        if (loro / nome).exists():
            shutil.copy(loro / nome, dove / nome); c['dalla prova dei precedenti'] += 1; continue
        fm, _ = atto(doc)
        pdf = QUI / str(fm.get('file_pdf') or '')
        try:
            d = fitz.open(pdf)
            d[p - 1].get_pixmap(dpi=150).save(str(dove / nome), jpg_quality=85); c['fatte'] += 1
        except Exception as e:
            c['mancanti'] += 1; print('manca', rid, nome, repr(e)[:120])
    subprocess.run(['tar', '-cf', str(R / 'pagine.tar'), '-C', str(dove), '.'], check=True)
    print(dict(c), '->', R / 'pagine.tar')


# ── esiti e verifica delle parole ────────────────────────────────────────────────────────────────────────────────────

def json_risposta(t):
    from chiamata_deepseek import json_finale
    t = str(t or '')
    if '</think>' in t:
        t = t.rsplit('</think>', 1)[1]
    t = re.sub(r'^```(?:json)?\s*|\s*```$', '', str(t or '').strip())
    try:
        return json.loads(t)
    except ValueError:
        j = json_finale(t)
        if j:
            try:
                return json.loads(j)
            except ValueError:
                pass
        i = t.find('{')
        if i >= 0:
            try:
                return json.JSONDecoder().raw_decode(t[i:])[0]
            except ValueError:
                pass
    return None


def esito3(x):
    x = spazi(x).lower()
    return 'si' if x in ('si', 'sì', 'yes', 'true') else 'no' if x in ('no', 'false') else 'incerto'


_TESTI = {}


def testo_doc(doc):
    if doc not in _TESTI:
        fm, pg = atto(doc)
        _TESTI[doc] = pg
    return _TESTI[doc]


def verifica_parole(parole, doc, pagine=None, testi_prompt=()):
    """R14 + R16 sul testo dell'atto: sulle pagine indicate (con la successiva come seguito) o sull'atto intero"""
    from freni import verifica
    pg = testo_doc(doc)
    if pagine:
        for p in pagine:
            if p in pg:
                e = verifica(parole, pg[p], testi_prompt, ricostruisci=True, intera=True, seguito=pg.get(p + 1, ''))
                if e == 'trovata':
                    return e
        tutto = '\n'.join(pg[p] for p in pagine if p in pg)
    else:
        tutto = '\n'.join(pg.values())
    return verifica(parole, tutto, testi_prompt, ricostruisci=True, intera=True)


def testi_regole(caso):
    conf = caso_conf(caso)
    out = []
    for s in conf['semantic_queries']:
        out += [s.get('testo'), s.get('canonical'), s.get('probe_alternativa'), s.get('probe_es')] + [d.get('testo') for d in s.get('seeds') or []]
    return [x for x in out if x]


MODELLI_RR = {'q9': 'Qwen3.5-9B', 'q27': 'Qwen3.8-27B'}


def numero(x):
    try:
        v = float(x)
        return v if 0 <= v <= 1 else None
    except (TypeError, ValueError):
        return None


def punteggio_token(v):
    """il punteggio dalle probabilita' dei token del verdetto: P(si) + 0,5 P(incerto) (regola dichiarata)"""
    return round(v['si'] + 0.5 * v['incerto'], 4) if v else None


def auc(coppie):
    """area sotto la curva ROC (Mann-Whitney, con i pari a meta') da [(punteggio, vero 0/1)]"""
    pos = [s for s, y in coppie if y]; neg = [s for s, y in coppie if not y]
    if not pos or not neg:
        return None
    vinte = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return round(vinte / (len(pos) * len(neg)), 3)


def calibrazione(coppie, bins=10):
    """Brier e ECE (10 classi uguali)"""
    if not coppie:
        return {}
    brier = sum((s - y) ** 2 for s, y in coppie) / len(coppie)
    ece = 0.0
    for b in range(bins):
        g = [(s, y) for s, y in coppie if b / bins <= s < (b + 1) / bins or (b == bins - 1 and s == 1)]
        if g:
            ece += len(g) / len(coppie) * abs(sum(s for s, _ in g) / len(g) - sum(y for _, y in g) / len(g))
    return {'brier': round(brier, 4), 'ece': round(ece, 4), 'n': len(coppie), 'auc': auc(coppie)}


def esiti_rr(quale, modello):
    """{id: {'cita', 'principi', 'pagine', 'fermate', 'lette'}} dagli esiti del reranker che ragiona (modello q9 o q27;
    quale = RRL, RRI o RRP per i principi; le pagine sempre dal cammino RRC), con la verifica delle parole (R14+R16)"""
    ids = righe_giuria(); ing = ingressi()
    out = collections.defaultdict(lambda: {'principi': [], 'pagine': [], 'fermate': {}, 'cita': None})
    for x in jl(ES / f'{modello}_{quale.lower()}.jsonl'):
        rid = x['id']
        if rid not in ids:
            continue
        caso, doc = ids[rid]; p = int(ing[rid].get('pagina') or 0)
        j = json_risposta(x.get('testo'))
        if not isinstance(j, dict):
            continue
        lst = [j] if quale == 'RRP' else (j.get('principi') or [])
        lst = [y for y in lst if isinstance(y, dict)]
        ci = j.get('cita_il_caso') if isinstance(j.get('cita_il_caso'), dict) else {}
        # i verdetti in ordine d'uscita: «cita_il_caso» poi i principi (RRL, RRI); uno solo (RRP). Si tengono gli ultimi.
        vl = [v for v in (x.get('verdetti_logprob') or [])]
        nv = len(lst) + (1 if ci and quale != 'RRP' else 0)
        vl = vl[-nv:] if len(vl) >= nv else [None] * nv
        if ci and quale != 'RRP':
            vci, vl = vl[0], vl[1:]
        else:
            vci = None
        for y, v in zip(lst, vl):
            c = corto(y.get('principio') or x.get('principio') or '')
            parole = y.get('parole') or ''
            out[rid]['principi'].append({'principio': c, 'esito': esito3(y.get('esito')), 'ragione': y.get('ragione'), 'parole': parole,
                                         'punteggio_detto': numero(y.get('punteggio')), 'punteggio_token': punteggio_token(v),
                                         'verifica': verifica_parole(parole, doc, [p - 1, p, p + 1], testi_regole(caso)) if parole else 'assente'})
        if quale != 'RRP':
            out[rid]['cita'] = {'esito': esito3(ci.get('esito')), 'ragione': ci.get('ragione'), 'punteggio_detto': numero(ci.get('punteggio')),
                                'punteggio_token': punteggio_token(vci)} if ci else None
            if j.get('altro'):
                out[rid]['altro'] = j['altro']
    for x in jl(ES / f'{modello}_rrc.jsonl'):
        rid = x['id']
        if rid not in ids:
            continue
        caso, doc = ids[rid]
        for passo in x.get('passi') or []:
            if passo.get('illeggibile'):
                continue
            j = json_risposta(passo.get('testo')) or {}
            if not isinstance(j, dict):     # una risposta che e' un numero o un elenco, non un oggetto (06/10/2026)
                j = {}
            parole = j.get('parole') or ''
            vl = passo.get('verdetti_logprob') or []
            out[rid]['pagine'].append({'pagina': passo['pagina'], 'esito': esito3(j.get('esito')), 'principio': corto(j.get('principio') or ''),
                                       'punteggio_detto': numero(j.get('punteggio')), 'punteggio_token': punteggio_token(vl[-1] if vl else None),
                                       'ragione': j.get('ragione'), 'parole': parole,
                                       'verifica': verifica_parole(parole, doc, [passo['pagina']]) if parole else 'assente'})
        out[rid]['fermate'] = x.get('fermate') or {}
        out[rid]['lette'] = len([q for q in x.get('passi') or [] if not q.get('illeggibile')])
    return dict(out)


def esiti_ds(nome):
    """{id: risposta JSON con le parole verificate} per dp, dt, dtl, dr_q9, dr_q27, drl_q9..."""
    ids = righe_giuria(); ing = ingressi()
    out = {}
    for x in jl(ES / f'deepseek_{nome}.jsonl'):
        rid = x['id']
        if rid not in ids:
            continue
        caso, doc = ids[rid]
        j = json_risposta(x.get('testo'))
        if not isinstance(j, dict):
            out[rid] = None; continue
        p = int(ing[rid].get('pagina') or 0)
        for y in j.get('principi') or []:
            if isinstance(y, dict) and y.get('parole'):
                y['verifica'] = verifica_parole(y['parole'], doc, [p - 1, p, p + 1], testi_regole(caso))
        for y in j.get('pagine') or []:
            if isinstance(y, dict) and y.get('prova'):
                try:
                    y['verifica'] = verifica_parole(y['prova'], doc, [int(y.get('pagina'))])
                except (TypeError, ValueError):
                    y['verifica'] = 'non trovata'
        if j.get('frase_sostenuta'):
            j['_verifica_frase'] = verifica_parole(j['frase_sostenuta'], doc, [p - 1, p, p + 1], testi_regole(caso))
        j['_token'] = x.get('token'); j['_secondi'] = x.get('secondi'); j['_prompt_token'] = x.get('prompt_token')
        out[rid] = j
    return out


# ── Clef e Clef-flash dopo DeepSeek ──────────────────────────────────────────────────────────────────────────────────

def domande_clef(caso, conf, pagine):
    """le stesse domande tipizzate dei campi di DeepSeek (formato System One di tools/decisori_clef.py)"""
    import decisori_domande as dd
    q = dd.domande_piccoli(caso)
    q['esito'] = {'type': 'choice', 'instructions': f"Che cosa e' il nome nel punto marcato con ⟦ ⟧?",
                  'criteria': {'caso': f"il caso {conf.get('nome')} o una delle sue pronunce",
                               'soggetto_omonimo': "la persona o l'organizzazione che porta il nome, non la sentenza",
                               'indice_o_elenco': "indice, sommario, tavola delle fonti o elenco degli allegati",
                               'omonimo': 'un altro significato della parola', 'non_determinabile': 'non si capisce'}}
    q['chi'] = {'type': 'choice', 'instructions': 'Chi enuncia la frase che usa il caso nel brano segnalato?',
                'criteria': {'corte': "l'organo giudicante che decide", 'parte': "una parte del giudizio (anche la corte che ne riassume la difesa; "
                             "nei pareri consultivi gli Stati e le organizzazioni partecipanti)", 'interveniente': 'un terzo intervenuto',
                             'amicus': 'un amicus curiae', 'procuratore': 'procuratore generale, avvocato generale o pubblico ministero',
                             'non_determinabile': 'non si capisce'}}
    for k in pagine:
        q[f's:{k}'] = {'type': 'noul', 'instructions': f"La pagina {k} dello stesso atto prosegue la stessa ripresa della citazione, "
                       "cioe' sviluppa un principio preso dalla citazione dentro lo stesso ragionamento? (No se parla d'altro o regge lo "
                       "stesso tema su un'altra fonte; guarda le note.)"}
    return q


def fase_clef(a):
    """Richieste per Clef/Clef-flash su tutte le righe della prova, DOPO DeepSeek: stato = metadati, contesto della citazione, pagine
    candidate intere (quelle di R10, di DeepSeek e del reranker che ragiona), regole brevi dei principi. Senza la
    risposta di DeepSeek (controllo indipendente). Tetto: 60.000 token col tokenizzatore di Qwen (Clef ne ha 65.536)."""
    ing = ingressi(); ids = righe_giuria()
    E = {}
    for nome in ('dr_q9', 'dr_q27', 'dt', 'dp'):
        for k, j in esiti_ds(nome).items():
            if j:
                E.setdefault(k, set()).update(int(y['pagina']) for y in j.get('pagine') or [] if isinstance(y, dict) and str(y.get('pagina', '')).isdigit())
    rr = {}
    for m in ('q27', 'q9'):
        if (ES / f'{m}_rrc.jsonl').exists():
            for k, v in esiti_rr('RRL', m).items():
                rr.setdefault(k, v)
    out = []
    gr = gruppi()
    for rid in sorted(ids, key=lambda k: (gr[k] != 'giuria137', k)):
        caso, doc = ids[rid]; r = ing[rid]; conf = caso_conf(caso)
        fm, pg = atto(doc)
        cand = sorted({v['pagina'] for v in r.get('vicine') or []} | E.get(rid, set()) |
                      {p['pagina'] for p in (rr.get(rid) or {}).get('pagine') or [] if p['esito'] in ('si', 'incerto')})
        cand = [k for k in cand if k in pg]
        principi = '\n'.join(f"- {corto(s['id'])}: {spazi(s['titolo'])}. {spazi(s['testo'])}" +
                             (f" Elemento proprio: {breve(s['elemento_proprio'], 500)}" if s.get('elemento_proprio') else '')
                             for s in conf['semantic_queries'])
        def stato(taglio):
            vic = '\n\n'.join(f'--- PAGINA {k} ---\n{pg[k][:taglio]}' for k in cand)
            return '\n\n'.join([f"Ricerca TRACE sul contenzioso climatico. Il caso citato e' {conf.get('nome')}.",
                                 'METADATI DELL\'ATTO CHE CITA:\n' + metadati(doc, fm),
                                 'PRINCIPI DEL CASO CITATO:\n' + principi,
                                 blocco_riga(r, caso, conf),
                                 'LA PAGINA DELLA CITAZIONE, con la fine della precedente e l\'inizio della successiva:\n' + r['contesto'],
                                 'PAGINE ATTORNO DA GIUDICARE:\n' + (vic or '(nessuna)')])
        taglio = TETTO_PAGINA
        st = stato(taglio)
        while ntok(st, 'qwen') > 60000 and taglio > 1500:
            taglio = int(taglio * 0.8); st = stato(taglio)
        out.append({'id': rid, 'state': st, 'questions': domande_clef(caso, conf, cand), 'taglio_pagine': taglio})
    scrivi_jl(RQ / 'clef_giuria.jsonl.gz', out)
    print(len(out), 'richieste per Clef; pagine tagliate in', sum(1 for x in out if x['taglio_pagine'] < TETTO_PAGINA))


# ── misure ───────────────────────────────────────────────────────────────────────────────────────────────────────────

def wilson(k, n, z=1.96):
    if not n:
        return (None, None)
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(max(0.0, c - h), 3), round(min(1.0, c + h), 3))


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else None; r = tp / (tp + fn) if tp + fn else None
    f = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
    return {'tp': tp, 'fp': fp, 'fn': fn, 'precisione': round(p, 3) if p is not None else None,
            'richiamo': round(r, 3) if r is not None else None, 'f1': round(f, 3) if f is not None else None}


def bootstrap_diff(righe, f, volte=2000, seme=20261004):
    """intervallo al 95% della differenza f(braccio) - f(base) ricampionando gli atti; f: lista di (atto, valore)"""
    atti = collections.defaultdict(list)
    for a, v in righe:
        atti[a].append(v)
    k = sorted(atti); rng = random.Random(seme); q = []
    for _ in range(volte):
        vv = [v for x in (rng.choice(k) for _ in k) for v in atti[x]]
        if vv:
            q.append(sum(vv) / len(vv))
    q.sort()
    return (round(q[int(.025 * len(q))], 3), round(q[int(.975 * len(q)) - 1], 3)) if q else (None, None)


def valori_ds(j):
    """i campi decisi da una risposta del lettore che ragiona"""
    pr = {corto(y.get('principio')) for y in j.get('principi') or [] if isinstance(y, dict) and esito3(y.get('esito')) == 'si'}
    if spazi(j.get('altro')):
        pr.add('altro')
    pg = set()
    for y in j.get('pagine') or []:
        try:
            if isinstance(y, dict) and str(y.get('prosegue')).strip().lower() == 'true':
                pg.add(int(y['pagina']))
        except (TypeError, ValueError):
            pass
    return {'cita': str(j.get('riferimento')).strip() in ('caso', 'caso_urgenda'), 'tipo': j.get('tipo_citazione'), 'chi': j.get('chi_parla'),
            'principi': pr, 'pagine': pg,
            'incerti': {corto(y.get('principio')) for y in j.get('principi') or [] if isinstance(y, dict) and esito3(y.get('esito')) == 'incerto'},
            'token': j.get('_token'), 'secondi': j.get('_secondi'), 'prompt_token': j.get('_prompt_token')}


def metriche(V, b, insieme_righe, ids_validi, atti):
    """le misure di un braccio b {id: valori} contro la verita' V, sulle righe date"""
    m = {'righe_con_risposta': sum(1 for k in insieme_righe if b.get(k))}
    # cita il caso (o lo riprende, per le semantiche): le scartate misurano i falsi positivi
    c = collections.Counter()
    for k in insieme_righe:
        v = V[k]
        if not b.get(k) or v['esito'] not in ('confermata', 'scartata'):
            continue
        c[(v['esito'] == 'confermata', bool(b[k]['cita']))] += 1
    m['cita'] = {'vere_dette_si': c[(True, True)], 'vere_dette_no': c[(True, False)], 'scartate_dette_si': c[(False, True)],
                 'scartate_dette_no': c[(False, False)],
                 'falsi_positivi_sulle_scartate': round(c[(False, True)] / (c[(False, True)] + c[(False, False)]), 3) if c[(False, True)] + c[(False, False)] else None,
                 'richiamo_sulle_confermate': round(c[(True, True)] / (c[(True, True)] + c[(True, False)]), 3) if c[(True, True)] + c[(True, False)] else None}
    for campo in ('tipo', 'chi'):
        v = [b[k][campo] == V[k][campo] for k in insieme_righe if b.get(k) and V[k].get(campo) and V[k]['esito'] == 'confermata' and b[k].get(campo)]
        m[campo] = {'giuste': sum(v), 'n': len(v), 'quota': round(sum(v) / len(v), 3) if v else None, 'wilson': wilson(sum(v), len(v))}
    tp = fp = fn = 0; uguali = []
    for k in insieme_righe:
        v = V[k]
        if not b.get(k) or v['esito'] != 'confermata' or v['principi'] is None or not set(v['principi']) <= ids_validi[k]:
            continue
        ts = set(v['principi']) - {'nessuno', 'altro'}; ms = set(b[k]['principi']) - {'nessuno', 'altro'}
        tp += len(ts & ms); fp += len(ms - ts); fn += len(ts - ms)
        uguali.append((set(v['principi']) - {'nessuno'}) == (set(b[k]['principi']) - {'nessuno'}))
    m['principi'] = prf(tp, fp, fn)
    m['principi']['insieme_uguale'] = round(sum(uguali) / len(uguali), 3) if uguali else None
    m['principi']['n_righe'] = len(uguali)
    tp = fp = fn = 0
    for k in insieme_righe:
        v = V[k]
        if not b.get(k) or v['esito'] != 'confermata' or v['pagine'] is None:
            continue
        viste = set(v['pagine_viste'] or [])
        ts = set(v['pagine']) & viste; ms = set(b[k]['pagine']) & viste
        tp += len(ts & ms); fp += len(ms - ts); fn += len(ts - ms)
    m['pagine'] = prf(tp, fp, fn)
    return m


def f1_principi(V, b, righe, ids_validi):
    tp = fp = fn = 0
    for k in righe:
        v = V[k]
        if not b.get(k) or v['esito'] != 'confermata' or v['principi'] is None or not set(v['principi']) <= ids_validi[k]:
            continue
        ts = set(v['principi']) - {'nessuno', 'altro'}; ms = set(b[k]['principi']) - {'nessuno', 'altro'}
        tp += len(ts & ms); fp += len(ms - ts); fn += len(ts - ms)
    return 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else None


def bootstrap_diff_f1(V, b1, b0, righe, ids_validi, atti, volte=1000, seme=20261004):
    """intervallo al 95% della differenza di F1 sui principi (b1 - b0), ricampionando gli atti citanti"""
    per = collections.defaultdict(list)
    for k in righe:
        if b1.get(k) and b0.get(k):
            per[atti[k]].append(k)
    chiavi = sorted(per); rng = random.Random(seme); q = []
    for _ in range(volte):
        rr = [k for x in (rng.choice(chiavi) for _ in chiavi) for k in per[x]]
        f1, f0 = f1_principi(V, b1, rr, ids_validi), f1_principi(V, b0, rr, ids_validi)
        if f1 is not None and f0 is not None:
            q.append(f1 - f0)
    q.sort()
    return (round(q[int(.025 * len(q))], 3), round(q[int(.975 * len(q)) - 1], 3)) if q else (None, None)


_PT01 = {}


def pagine_t01(caso):
    if caso not in _PT01:
        _PT01[caso] = punteggi_caso(caso)[1]
    return _PT01[caso]


def fase_misure(a):
    """Le misure contro il team, su TUTTE le righe giudicate e, a parte, sulle 137 della giuria. I giudizi si leggono qui e
    solo qui (verita.json)."""
    V = json.load(open(VERITA, encoding='utf-8'))
    ins = json.load(open(INSIEME, encoding='utf-8'))
    ing = ingressi(); ids = righe_giuria()
    atti = {k: x['document_id'] for k, x in ins.items()}
    ids_validi = {k: {corto(q['id']) for q in caso_conf(ins[k]['caso'])['semantic_queries']} | {'altro', 'nessuno'} for k in ins}
    insiemi = {'tutte': sorted(ins), 'giuria137': sorted(k for k, x in ins.items() if x['gruppo'] == 'giuria137'),
               'col_nome': sorted(k for k, x in ins.items() if x['rete'] != 'semantica'),
               'semantiche': sorted(k for k, x in ins.items() if x['rete'] == 'semantica')}
    bracci = {}
    # A0: le cinque letture di oggi (solo le 137), dal file della giuria
    J = json.load(open(GIURIA, encoding='utf-8'))['righe']
    bracci['A0 cinque letture (R15)'] = {k: {'cita': (e.get('g_rif') or {}).get('caso', 0) >= 3, 'tipo': e.get('tipo'), 'chi': e.get('chi'),
                                            'principi': set(e.get('l_principi') or []) - {'nessuno'}, 'pagine': set(e.get('l_pagine') or [])}
                                        for k, e in J.items() if k in ins and e.get('letta')}
    # P0: la proposta in banca dati (tutte le righe; una riga in banca e' gia' una proposta «cita»)
    P0 = {}
    for k, x in ins.items():
        pp = x.get('proposta') or {}
        P0[k] = {'cita': True, 'tipo': pp.get('proposto_tipo_citazione'), 'chi': pp.get('proposto_chi_parla'),
                 'principi': {corto(q) for q in pp.get('proposto_principi') or []} - {'nessuno'},
                 'pagine': {int(v['pagina']) for v in pp.get('proposto_estensione') or [] if isinstance(v, dict) and v.get('prosegue') and 'pagina' in v}}
    bracci['P0 proposta in banca dati'] = P0
    for nome in ('dp', 'dt', 'dtl', 'dr_q9', 'dr_q27', 'drl_q9', 'drl_q27', 'dri_q9', 'dri_q27'):
        E = esiti_ds(nome)
        if E:
            bracci[{'dp': 'DP DeepSeek, contesto di oggi + T01', 'dt': 'DT DeepSeek, atto (65k) + T01', 'dtl': 'DTL DeepSeek, atto (262k) + T01'}.get(
                nome, f"D1 DeepSeek, atto + reranker che ragiona ({nome})")] = {k: (valori_ds(j) if j else None) for k, j in E.items()}
    M = {'scritto': time.strftime('%d/%m/%Y %H:%M'), 'insiemi': {n: len(v) for n, v in insiemi.items()}, 'bracci': {}}
    for nome, b in bracci.items():
        M['bracci'][nome] = {n: metriche(V, b, righe, ids_validi, atti) for n, righe in insiemi.items()}
        tk = [b[k]['token'] for k in b if b.get(k) and b[k].get('token')]
        if tk:
            M['bracci'][nome]['costo'] = {'token_uscita_mediana': statistics.median(tk), 'token_uscita_media': round(statistics.mean(tk)),
                                          'token_domanda_mediana': statistics.median([b[k]['prompt_token'] for k in b if b.get(k) and b[k].get('prompt_token')] or [0]),
                                          'secondi_mediana': statistics.median([b[k]['secondi'] for k in b if b.get(k) and b[k].get('secondi')] or [0])}
    # differenze col bootstrap per atto (F1 dei principi)
    diff = {}
    for nome in bracci:
        if nome.startswith(('D', 'P0')):
            for base, insieme in (('A0 cinque letture (R15)', 'giuria137'), ('P0 proposta in banca dati', 'tutte')):
                if nome != base:
                    diff[f'{nome} - {base} ({insieme})'] = bootstrap_diff_f1(V, bracci[nome], bracci[base], insiemi[insieme], ids_validi, atti)
    M['differenze_f1_principi'] = diff
    # i reranker: che cosa passa a DeepSeek (principi e pagine), su tutte e sulle 137
    rer = {}
    for n, righe in insiemi.items():
        r_n = {}
        conf_r = [k for k in righe if V[k]['esito'] == 'confermata' and V[k]['principi'] is not None and set(V[k]['principi']) <= ids_validi[k]]
        def prf_principi(passa):
            tp = fp = fn = 0
            for k in conf_r:
                ts = set(V[k]['principi']) - {'nessuno', 'altro'}; ms = passa(k)
                if ms is None:
                    continue
                tp += len(ts & ms); fp += len(ms - ts); fn += len(ts - ms)
            return prf(tp, fp, fn)
        for soglia in (0.5, 0.2):
            r_n[f'R0 T01 principi >= {soglia}'] = prf_principi(lambda k: {corto(p) for p, v in (ing[k].get('punteggi_brano') or {}).items() if v >= soglia} if ing[k].get('punteggi_brano') else None)
        conf_p = [k for k in righe if V[k]['esito'] == 'confermata' and V[k]['pagine'] is not None]
        def prf_pagine(passa, lette=None):
            tp = fp = fn = 0; nl = []
            for k in conf_p:
                viste = set(V[k]['pagine_viste'] or []); ts = set(V[k]['pagine']) & viste
                ms = passa(k)
                if ms is None:
                    continue
                ms &= viste
                tp += len(ts & ms); fp += len(ms - ts); fn += len(ts - ms)
                if lette:
                    nl.append(lette(k))
            o = prf(tp, fp, fn)
            if nl:
                o['pagine_lette_o_passate_media'] = round(statistics.mean(nl), 2)
            return o
        r_n['R0 T01 + R10 pagine'] = prf_pagine(lambda k: {v['pagina'] for v in ing[k].get('vicine') or []}, lambda k: len(ing[k].get('vicine') or []))
        for m in MODELLI_RR:
            for quale in ('RRL', 'RRI', 'RRP'):
                if not (ES / f'{m}_{quale.lower()}.jsonl').exists():
                    continue
                E = esiti_rr(quale, m)
                for modo in ('si', 'si+incerto'):
                    r_n[f'{m} {quale} principi {modo}'] = prf_principi(
                        lambda k: ({y['principio'] for y in E[k]['principi'] if y['esito'] == 'si' or (modo != 'si' and y['esito'] == 'incerto')} if k in E else None))
                if quale != 'RRP':
                    c = collections.Counter()
                    for k in righe:
                        if k in E and E[k].get('cita') and V[k]['esito'] in ('confermata', 'scartata'):
                            c[(V[k]['esito'], E[k]['cita']['esito'])] += 1
                    r_n[f'{m} {quale} cita il caso'] = {f'{a}_{b}': v for (a, b), v in c.items()}
            if (ES / f'{m}_rrc.jsonl').exists():
                E = esiti_rr('RRL', m)
                for modo in ('si', 'si+incerto'):
                    r_n[f'{m} RRC pagine {modo}'] = prf_pagine(
                        lambda k: ({y['pagina'] for y in E[k]['pagine'] if y['esito'] == 'si' or (modo != 'si' and y['esito'] == 'incerto')} if k in E else None),
                        lambda k: E[k].get('lette', 0) if k in E else 0)
        # LA QUALITA' DEI PUNTEGGI (il PI, 04/10/2026): AUC, Brier ed ECE del punteggio di ogni verdetto contro il team, per
        # T01 (punteggio di oggi) e per il reranker che ragiona (dai token e detto), sugli stessi principi e pagine
        brano_t01 = {k: {corto(p): v for p, v in (ing[k].get('punteggi_brano') or {}).items()} for k in conf_r}
        cp = []
        for k in conf_p:
            sc = pagine_t01(ins[k]['caso'])
            for pg in V[k]['pagine_viste'] or []:
                v = sc.get(f"{ins[k]['document_id']}#p{pg}")
                if v:
                    cp.append((max(v.values()), int(pg in set(V[k]['pagine']))))
        r_n['punteggi pagine T01'] = calibrazione(cp)
        r_n['punteggi principi T01'] = calibrazione([(brano_t01[k][p], int(p in V[k]['principi'])) for k in conf_r for p in brano_t01[k]])
        for m in MODELLI_RR:
            for quale in ('RRL', 'RRI', 'RRP'):
                if (ES / f'{m}_{quale.lower()}.jsonl').exists():
                    E = esiti_rr(quale, m)
                    for tipo in ('punteggio_token', 'punteggio_detto'):
                        cp = [(y[tipo], int(y['principio'] in V[k]['principi'])) for k in conf_r if k in E for y in E[k]['principi'] if y.get(tipo) is not None]
                        cp_t01 = [(brano_t01[k][y['principio']], int(y['principio'] in V[k]['principi'])) for k in conf_r if k in E
                                  for y in E[k]['principi'] if y.get(tipo) is not None and y['principio'] in brano_t01[k]]
                        r_n[f'punteggi principi {m} {quale} {tipo}'] = {**calibrazione(cp), 'T01_sulle_stesse': calibrazione(cp_t01)}
            if (ES / f'{m}_rrc.jsonl').exists():
                E = esiti_rr('RRL', m)
                _, vic = (None, None)
                for tipo in ('punteggio_token', 'punteggio_detto'):
                    cp = [(y[tipo], int(y['pagina'] in set(V[k]['pagine']))) for k in conf_p if k in E for y in E[k]['pagine']
                          if y.get(tipo) is not None and y['pagina'] in set(V[k]['pagine_viste'] or [])]
                    r_n[f'punteggi pagine {m} RRC {tipo}'] = calibrazione(cp)
        rer[n] = r_n
    M['reranker'] = rer
    # la verifica delle parole (R14+R16) di DeepSeek e del reranker
    fr = {}
    for nome in ('dp', 'dt', 'dtl', 'dr_q9', 'dr_q27'):
        E = esiti_ds(nome)
        if E:
            fr[nome] = {'principi': dict(collections.Counter(y.get('verifica') for j in E.values() if j for y in j.get('principi') or [] if isinstance(y, dict) and y.get('parole'))),
                        'frase_sostenuta': dict(collections.Counter(j.get('_verifica_frase') for j in E.values() if j and j.get('frase_sostenuta')))}
    M['verifica_parole'] = fr
    # costo per file d'esito
    costo = {}
    for f in sorted(ES.glob('*.jsonl')):
        X = jl(f)
        if not X or f.name.startswith('clef'):
            continue
        per = collections.defaultdict(lambda: [0, 0.0, 0, 0])
        for x in X:
            q = per[x['id']]
            q[0] += x.get('token') or 0; q[1] += x.get('secondi') or 0
            q[2] += sum(p.get('prompt_token') or 0 for p in x.get('passi') or []) or (x.get('prompt_token') or 0)
            q[3] += len(x.get('passi') or []) or 1
        v = list(per.values())
        costo[f.stem] = {'righe': len(v), 'chiamate': sum(q[3] for q in v),
                         'token_uscita_per_riga_mediana': statistics.median(q[0] for q in v),
                         'token_domanda_per_riga_mediana': statistics.median(q[2] for q in v),
                         'secondi_di_chiamata_per_riga_mediana': round(statistics.median(q[1] for q in v), 1)}
    M['costo'] = costo
    # Clef e Clef-flash dopo DeepSeek
    cl = {}
    for modello in ('clef', 'clef-flash'):
        f = ES / f'clef_giuria_{modello}.jsonl'
        if not f.exists():
            continue
        C = {x['id']: x.get('risposte') or {} for x in jl(f) if not x.get('errore')}
        for nome, b in bracci.items():
            if not nome.startswith('D'):
                continue
            c = collections.Counter()
            for k in insiemi['tutte']:
                v = V[k]
                if k not in C or not b.get(k):
                    continue
                q = C[k]
                if 'esito' in q and v['esito'] in ('confermata', 'scartata'):
                    c[('cita', (q['esito'].get('choice') == 'caso') != b[k]['cita'], b[k]['cita'] != (v['esito'] == 'confermata'))] += 1
                if v['esito'] != 'confermata':
                    continue
                for campo in ('tipo', 'chi'):
                    if campo in q and v.get(campo) and b[k].get(campo):
                        c[(campo, q[campo].get('choice') != b[k][campo], b[k][campo] != v[campo])] += 1
                if v['principi'] is not None and set(v['principi']) <= ids_validi[k]:
                    for qid, x in q.items():
                        if qid.startswith('p:'):
                            pr = qid[2:]; si_c = (x.get('noul') or 0) >= 0.5; si_d = pr in b[k]['principi']
                            c[('principi', si_c != si_d, si_d != (pr in set(v['principi'])))] += 1
                if v['pagine'] is not None:
                    viste = set(v['pagine_viste'] or [])
                    for qid, x in q.items():
                        if qid.startswith('s:') and int(qid[2:]) in viste:
                            pg = int(qid[2:]); si_c = (x.get('noul') or 0) >= 0.5; si_d = pg in b[k]['pagine']
                            c[('pagine', si_c != si_d, si_d != (pg in set(v['pagine'])))] += 1
            out = {}
            for campo in ('cita', 'tipo', 'chi', 'principi', 'pagine'):
                fl = c[(campo, True, True)] + c[(campo, True, False)]; err = c[(campo, True, True)] + c[(campo, False, True)]
                out[campo] = {'decisioni': sum(v for kk, v in c.items() if kk[0] == campo), 'segnalate': fl, 'segnalate_e_sbagliate': c[(campo, True, True)],
                              'precisione_del_segnale': round(c[(campo, True, True)] / fl, 3) if fl else None,
                              'errori_di_deepseek': err, 'errori_trovati': round(c[(campo, True, True)] / err, 3) if err else None}
            cl[f'{modello} dopo {nome}'] = out
    M['clef'] = cl
    json.dump(M, open(R / 'misure.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=list)
    scrivi_risultati(M)


def scrivi_risultati(M):
    righe = ['# RAGIONAMENTO: risultati (generato da tools/ragionamento.py misure, non si scrive a mano)', '',
             f"Scritto il {M['scritto']}. Righe: " + ', '.join(f'{n} {v}' for n, v in M['insiemi'].items()) + '.', '']
    for ins in ('tutte', 'giuria137', 'col_nome', 'semantiche'):
        righe += [f'## Lettore, righe: {ins}', '',
                  '| braccio | risposte | cita: falsi positivi sulle scartate | cita: richiamo | tipo | chi parla | principi P | R | F1 | insieme uguale | pagine P | R | F1 |',
                  '|---|---|---|---|---|---|---|---|---|---|---|---|---|']
        for nome, mm in M['bracci'].items():
            m = mm[ins]
            if not m['righe_con_risposta']:
                continue
            righe.append(f"| {nome} | {m['righe_con_risposta']} | {m['cita']['falsi_positivi_sulle_scartate']} | {m['cita']['richiamo_sulle_confermate']} | "
                         f"{m['tipo']['quota']} ({m['tipo']['n']}) | {m['chi']['quota']} ({m['chi']['n']}) | {m['principi']['precisione']} | "
                         f"{m['principi']['richiamo']} | {m['principi']['f1']} | {m['principi']['insieme_uguale']} ({m['principi']['n_righe']}) | "
                         f"{m['pagine']['precisione']} | {m['pagine']['richiamo']} | {m['pagine']['f1']} |")
        righe.append('')
    if M.get('differenze_f1_principi'):
        righe += ['Differenze di F1 sui principi, intervallo al 95% ricampionando gli atti: ' +
                  '; '.join(f'{k}: {v}' for k, v in M['differenze_f1_principi'].items()), '']
    for ins in ('tutte', 'giuria137'):
        righe += [f'## Reranker, righe: {ins}', '', '| reranker | precisione | richiamo | F1 | pagine lette o passate (media) |', '|---|---|---|---|---|']
        for nome, m in M['reranker'][ins].items():
            if 'precisione' in m:
                righe.append(f"| {nome} | {m['precisione']} | {m['richiamo']} | {m['f1']} | {m.get('pagine_lette_o_passate_media', '')} |")
            else:
                righe.append(f'| {nome} | {json.dumps(m, ensure_ascii=False)} | | | |')
        righe.append('')
    righe += ['Verifica delle parole (R14+R16): ' + json.dumps(M.get('verifica_parole'), ensure_ascii=False), '',
              'Costo per file d\'esito: ' + json.dumps(M.get('costo'), ensure_ascii=False), '']
    if M.get('clef'):
        righe += ['## Clef dopo DeepSeek', '', '| controllo | campo | decisioni | segnalate | segnalate e sbagliate | precisione del segnale | errori di DeepSeek trovati |',
                  '|---|---|---|---|---|---|---|']
        for nome, o in M['clef'].items():
            for campo, v in o.items():
                righe.append(f"| {nome} | {campo} | {v['decisioni']} | {v['segnalate']} | {v['segnalate_e_sbagliate']} | {v['precisione_del_segnale']} | "
                             f"{v['errori_trovati']} ({v['errori_di_deepseek']}) |")
    (R / 'RISULTATI.md').write_text('\n'.join(righe) + '\n', encoding='utf-8')
    print('\n'.join(righe[:60]))


# ── contesto e lunghezze (misure senza GPU) ──────────────────────────────────────────────────────────────────────────

def fase_contesto(a):
    import leggi_ripresa as LR
    ing = ingressi()
    c = collections.Counter(); ch = []; nv = []; tagliate = 0; vic_tot = 0
    for k, r in ing.items():
        ch.append(len(r['contesto'])); nv.append(len(r.get('vicine') or []))
        fm, pg = atto(r['document_id'])
        for v in r.get('vicine') or []:
            vic_tot += 1
            if len(pg.get(v['pagina'], '')) > LR.TAGLIO_VICINA:
                tagliate += 1
        c['con paragrafi'] += bool(r.get('paragrafi'))
    print(json.dumps({'righe': len(ing), 'caratteri del contesto (mediana, max)': (statistics.median(ch), max(ch)),
                      'pagine R10 per riga (media, max)': (round(statistics.mean(nv), 2), max(nv)),
                      'pagine R10 oltre i 3.500 caratteri (tagliate in L05)': f'{tagliate}/{vic_tot}', **c}, ensure_ascii=False, indent=1))


def fase_lunghezze(a):
    L = json.load(open(R / 'lunghezze_atti.json', encoding='utf-8'))
    tok, righe = L['token_atto'], L['righe']
    def pct(v, p):
        v = sorted(v); return v[min(len(v) - 1, int(p * len(v)))]
    out = {}
    for caso in CASI + ['tutti']:
        coppie = [(d, n) for cd, n in righe.items() for c, d in [cd.split('|', 1)] if caso in (c, 'tutti') and d in tok]
        v = [tok[d] for d, _ in coppie]
        out[caso] = {'atti': len(v), 'mediana': pct(v, .5), 'p75': pct(v, .75), 'p90': pct(v, .9), 'p95': pct(v, .95), 'max': max(v),
                     **{f'entro_{b // 1000}k': {'atti': round(sum(x <= b for x in v) / len(v), 3),
                                                'righe': round(sum(n for d, n in coppie if tok[d] <= b) / sum(n for _, n in coppie), 3)}
                        for b in (23000, 40000, 100000, 200000)}}
    json.dump(out, open(R / 'lunghezze_sintesi.json', 'w'), indent=1)
    print(json.dumps(out, indent=1))


# ── ReCaS ────────────────────────────────────────────────────────────────────────────────────────────────────────────
#
# Dove gira che cosa (nessun lavoro GPU pagato; si aspetta ReCaS):
#   Qwen3.8-27B  la coda del lavoro dei precedenti (1916344, ~/trace/misure/precedenti/coda): 6x_rr27_*, dopo i loro 10-50
#   Qwen3.5-9B   un lavoro gemello da 1 H100 (tools/recas_ragionamento/ragiona9b.sh, coda ~/trace/misure/ragionamento/coda9b),
#                stesso schema della coda dei precedenti; i pesi non addestrati li scarica un lavoro CPU (scarica9b.sh)
#   Clef         nella coda del lavoro gemello, come voce «__libera» (il lavoro spegne vLLM, Clef usa la GPU, poi riaccende)
#   DeepSeek     coda-ds4, un blocco alla volta, nomi z_ragiona_* (dopo cinque_99xx di L11 e cinque_995xx di S07); ogni blocco
#                lavora al massimo 25 minuti, poi si rimette in attesa e passa il turno; i blocchi aspettano in
#                ~/trace/misure/ragionamento/attesa_ds e passano il turno a rotazione. I blocchi col contesto lungo (E4, E5, DTL) vanno in coda_lungo, servita solo dal lavoro di prova lavori/lungo_prova.sh (non un ricambio).

Q9 = 'trace/misure/ragionamento/coda9b'
PESI9 = 'Qwen/Qwen3.5-9B@c202236235762e1c871ad0ccb60c8ee5ba337b9a'
PESI27 = 'Qwen/Qwen3.8-27B@1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0'

BLOCCO = """# RAGIONAMENTO (tools/ragionamento.py, 04/10/2026): {nome}. {nota}
H=/lustrehome/climpact; G=$H/trace/misure/ragionamento; cd $G
CH=$(cat $H/trace/chat/chiave)
{attesa}
$H/trace/venv/bin/python -u tools/ragionamento_corri.py --richieste richieste/{richieste} --uscita esiti/{uscita} \\
  --base-url {base} --chiave-file $H/trace/chat/chiave --modello {modello} --ragionamento {ragionamento} \\
  --contesto {contesto} --paralleli {paralleli} --minuti {minuti} {tok} {img} >> log/{nome}.log 2>&1
{dopo}
"""

TROVA_QWEN = ('for p in ${{PORTA:-}} 8000 8001 8002 8003 8080; do curl -s -m 3 -H "Authorization: Bearer $CH" '
              'http://127.0.0.1:$p/v1/models | grep -q {servito} && {{ PORTA=$p; break; }}; done\n'
              '[ -n "$PORTA" ] || {{ echo "nessun server {servito}: rimetto il blocco in coda"; cp $0 $(dirname $0)/../$(basename $0); exit 0; }}')


def blocco(nome, richieste, uscita, server, minuti, nota, dopo='', immagini=False, extra=''):
    img = extra
    if server == 'deepseek':
        base, mod, rag, ctx, par = 'http://127.0.0.1:8000/v1', 'deepseek-v4-flash', 'deepseek-high', CTX_DS, 32
        att = 'until curl -s -m 5 -H "Authorization: Bearer $CH" http://127.0.0.1:8000/v1/models | grep -q deepseek; do sleep 30; done'
        tok = '--tokenizer $G/tokenizer_dsv4/tokenizer.json'; mi = minuti
    elif server == 'deepseek-lungo':
        # solo nel lavoro di prova col contesto lungo (lavori/lungo_prova.sh, coda ragionamento/coda_lungo): RESTO dal lavoro
        base, mod, rag, ctx, par = 'http://127.0.0.1:8000/v1', 'deepseek-v4-flash', 'deepseek-high', CTX_DS_LUNGO, 16
        att = ('until curl -s -m 5 -H "Authorization: Bearer $CH" http://127.0.0.1:8000/v1/models | grep -q deepseek; do sleep 30; done\n'
               'curl -s -m 5 -H "Authorization: Bearer $CH" http://127.0.0.1:8000/v1/models | grep -q \'"max_model_len":262144\' || '
               '{ echo "server senza contesto lungo: rimetto il blocco"; cp $0 $G/coda_lungo/' + nome + '.sh; exit 0; }\n'
               f'RESTO=${{RESTO:-{minuti}}}')
        tok = '--tokenizer $G/tokenizer_dsv4/tokenizer.json'; mi = '$RESTO'
    else:
        servito = 'qwen3.8-27b' if server == 'q27' else 'qwen3.5-9b'
        base, mod, rag, ctx, par = 'http://127.0.0.1:$PORTA/v1', servito, 'qwen-pensa', 65536, 16
        att = f'RESTO=${{RESTO:-{minuti}}}\n' + TROVA_QWEN.format(servito=servito)
        tok = f'--tokenizer $H/trace/pesi/{PESI27 if server == "q27" else PESI9}/tokenizer.json'; mi = '$RESTO'
        if immagini:
            # le immagini delle pagine (pagine.tar, fatte sul Mac): il lavoro gemello le apre in $IMG; nella coda del 27B si
            # aprono qui, sul disco del nodo
            att += ('\nIMGR=${_CONDOR_SCRATCH_DIR:-/tmp/climpact-$$}/ragionamento_pagine; '
                    '[ -e $IMGR/.pronte ] || { mkdir -p $IMGR && tar -xf $G/pagine.tar -C $IMGR && touch $IMGR/.pronte; }')
            img = '--immagini $IMGR'
        img += ' --logprobs'
    return BLOCCO.format(nome=nome, nota=nota, attesa=att, richieste=richieste, uscita=uscita, base=base, modello=mod,
                         ragionamento=rag, contesto=ctx, paralleli=par, minuti=mi, tok=tok, dopo=dopo, img=img)


# a turno: il blocco che aspetta da piu' tempo (un blocco che si rimette in attesa va in fondo)
DS_AVANTI = 'f=$(ls -tr $G/attesa_ds/*.sh 2>/dev/null | head -1); [ -n "$f" ] && mv $f $H/trace/chat/coda-ds4/'


def blocco_ds(nome, richieste, uscita, nota, extra=''):
    return blocco(nome, richieste, uscita, 'deepseek', 25, nota + '; al massimo 25 minuti per turno, poi si rimette in attesa e '
                  'riparte da dove era', dopo=f'grep -q FINITO log/{nome}.log || cp $0 $G/attesa_ds/{nome}.sh\n{DS_AVANTI}', extra=extra)


def blocco_lungo(nome, richieste, uscita, nota, extra=''):
    return blocco(nome, richieste, uscita, 'deepseek-lungo', 600, nota + '; nel lavoro di prova col contesto lungo',
                  dopo=f'grep -q FINITO log/{nome}.log || cp $0 $G/coda_lungo/{nome}.sh', extra=extra)


SCALA_EXTRA = '--prefissi $G/scala/prefissi.json.gz'
SCALA_EXTRA_LUNGO = '--prefissi $G/scala/prefissi.json.gz --atti $G/scala/atti_lunghi.json.gz'


def manda_scala():
    """la scala delle leve (tools/scala.py): E0-E3 nella coda di DeepSeek a turno, E4 nel lavoro di prova col contesto lungo"""
    S_ = R / 'scala'
    ssh(f'mkdir -p ~/{REMOTO}/scala ~/{REMOTO}/coda_lungo/fatti')
    for f in ('scala_base.jsonl.gz', 'scala_lunga.jsonl.gz', 'prefissi.json.gz', 'atti_lunghi.json.gz'):
        scp(S_ / f, f'recas:{REMOTO}/scala/{f}')
    loc = R / 'blocchi'
    nome = 'z_ragiona_00_scala'
    (loc / f'{nome}.sh').write_text(blocco_ds(nome, '../scala/scala_base.jsonl.gz', 'deepseek_scala.jsonl',
                                              'scala delle leve E0-E3 (cinque letture, sforzo low/high/max, metadati)', SCALA_EXTRA), encoding='utf-8')
    manda_file(loc / f'{nome}.sh', f'{REMOTO}/attesa_ds/{nome}.sh')
    nome = '10_scala_e4'
    (loc / f'{nome}.sh').write_text(blocco_lungo(nome, '../scala/scala_lunga.jsonl.gz', 'deepseek_scala_lunga.jsonl',
                                                 'scala delle leve E4 (atto intero)', SCALA_EXTRA_LUNGO), encoding='utf-8')
    manda_file(loc / f'{nome}.sh', f'{REMOTO}/coda_lungo/{nome}.sh')
    nome = '30_dtl'
    (loc / f'{nome}.sh').write_text(blocco_lungo(nome, 'dtl.jsonl.gz', 'deepseek_dtl.jsonl', 'L12 con l\'atto intero (262.144) + punteggi T01'), encoding='utf-8')
    manda_file(loc / f'{nome}.sh', f'{REMOTO}/coda_lungo/{nome}.sh')
    ssh(f'rm -f ~/{REMOTO}/attesa_lungo/z_ragiona_11_dtl.sh', check=False)
    # i blocchi gia' in attesa o in coda-ds4 col vecchio modo di passare il turno si riscrivono (non stanno girando)
    for nome, rq, us, nota in (('z_ragiona_02_dt', 'dt.jsonl.gz', 'deepseek_dt.jsonl', 'L12 atto intero o ripiego + punteggi T01 (controllo)'),
                               ('z_ragiona_03_dp', 'dp.jsonl.gz', 'deepseek_dp.jsonl', 'L12 contesto di oggi + punteggi T01 (controllo)')):
        (loc / f'{nome}.sh').write_text(blocco_ds(nome, rq, us, nota), encoding='utf-8')
        dove = ssh(f'ls ~/trace/chat/coda-ds4/{nome}.sh ~/{REMOTO}/attesa_ds/{nome}.sh 2>/dev/null', check=False).split()
        for d in dove:
            manda_file(loc / f'{nome}.sh', d.replace('/lustrehome/climpact/', ''))
    for f in ('lungo_prova.sh', 'lungo_prova.sub'):
        manda_file(QUI / 'tools' / 'recas_ragionamento' / f, f'{REMOTO}/lavori/{f}')
    ssh(f'chmod +x ~/{REMOTO}/lavori/*.sh')
    q = ssh('condor_q climpact -af ClusterId JobStatus Cmd', check=False)
    if 'lungo_prova.sh' not in q and SI_LUNGO.exists():
        print(ssh(f'cd ~/{REMOTO}/lavori && condor_submit lungo_prova.sub'))


# IL SERVER DI PROVA COL CONTESTO LUNGO (lavori/lungo_prova.sub) e' un lavoro con 4 GPU in piu' su ReCaS: si sottomette
# SOLO se esiste questo segno, scritto a mano col si' del PI (04/10/2026, sessione «TRACE: Prove ReCaS e pipeline»:
# senza il segno E4/E5 restano pronti in scala/pronti_lungo e non entrano in coda_lungo).
SI_LUNGO = R / 'SI_DEL_PI_LUNGO'
PRONTI_LUNGO = f'{REMOTO}/scala/pronti_lungo'


def voce_qwen(nome, richieste, uscita, server, nota, immagini=False):
    return blocco(nome, richieste, uscita, server, 300, nota + '; se il tempo del lavoro finisce prima, rimette se stesso in coda',
                  dopo=f'grep -q FINITO log/{nome}.log || cp $0 $(dirname $0)/../{nome}.sh', immagini=immagini)


VOCE_CLEF = """# RAGIONAMENTO (tools/ragionamento.py, 04/10/2026): Clef-flash e Clef DOPO DeepSeek (C1), sulle richieste
# richieste/clef_giuria.jsonl.gz (tools/ragionamento.py clef). Voce «__libera»: il lavoro gemello spegne vLLM prima e lo
# riaccende dopo, Clef usa la GPU da solo. Stesso programma della prova dei decisori (misure/decisori/tools/decisori_clef.py).
H=/lustrehome/climpact; T=$H/trace; G=$T/misure/ragionamento; cd $T/misure/decisori
S=${_CONDOR_SCRATCH_DIR:-/tmp/climpact-$$}; RESTO=${RESTO:-300}; T0=$(date +%s)
export HOME=$H HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1
for M in clef-flash@17f0b0ad64efb65d273590632833508766b2aae6 clef@2f3de3dd85f379784083b0814d997ab627200f0c; do
  N=${M%%@*}; W=$T/pesi/Cloudflare/$M; L=$S/$N; mkdir -p $L
  ( cd $W && ls | grep -v '^model-' | xargs -I{} cp -r {} $L/ ; ls model-*.safetensors | xargs -P 6 -I{} cp {} $L/ ); rm -rf $L/.cache $L/.completo
  m=$(( RESTO - ($(date +%s) - T0) / 60 - 5 )); [ $m -gt 5 ] || break
  $T/venv/bin/python -u tools/decisori_clef.py --cartella $L --richieste $G/richieste/clef_giuria.jsonl.gz \\
    --uscita $G/esiti/clef_giuria_$N.jsonl --minuti $m >> $G/log/90_clef.log 2>&1
  rm -rf $L
done
n=$(zcat $G/richieste/clef_giuria.jsonl.gz | wc -l)
[ "$(cat $G/esiti/clef_giuria_clef.jsonl 2>/dev/null | wc -l)" -ge "$n" ] && echo FINITO >> $G/log/90_clef.log || cp $0 $(dirname $0)/../$(basename $0)
"""


def manda_file(f, remoto):
    scp(f, f'recas:{remoto}.tmp'); ssh(f'mv ~/{remoto}.tmp ~/{remoto}')


def fase_manda(a):
    """Tutta la batteria nelle code (vedi sopra). Toglie prima SOLO le voci di questa misura messe stamattina con i nomi vecchi."""
    ssh(f'mkdir -p ~/{REMOTO}/richieste ~/{REMOTO}/esiti ~/{REMOTO}/log ~/{REMOTO}/tools ~/{REMOTO}/attesa_ds ~/{REMOTO}/attesa_lungo '
        f'~/{REMOTO}/tokenizer_dsv4 ~/{REMOTO}/lavori ~/{Q9}/fatti')
    ssh('rm -f ~/trace/misure/precedenti/coda/60_rr_lista_qwen.sh ~/trace/misure/precedenti/coda/61_rr_cammino_qwen.sh '
        '~/trace/misure/precedenti/coda/62_rr_punto_qwen.sh ~/trace/chat/coda-ds4/z_ragiona_01_d2.sh '
        f'~/{REMOTO}/attesa_ds/z_ragiona_02_d1.sh ~/{REMOTO}/attesa_lungo/z_ragiona_11_d2l.sh '
        f'~/{REMOTO}/richieste/d1.jsonl.gz ~/{REMOTO}/richieste/d2.jsonl.gz ~/{REMOTO}/richieste/d2l.jsonl.gz', check=False)
    for f in sorted(RQ.glob('*.jsonl.gz')):
        scp(f, f'recas:{REMOTO}/richieste/{f.name}')
    for f in ('ragionamento_corri.py', 'chiamata_deepseek.py'):
        scp(QUI / 'tools' / f, f'recas:{REMOTO}/tools/{f}')
    scp(TOK_DS, f'recas:{REMOTO}/tokenizer_dsv4/tokenizer.json')
    if (R / 'pagine.tar').exists():
        scp(R / 'pagine.tar', f'recas:{REMOTO}/pagine.tar')
    for f in ('ragiona9b.sh', 'ragiona9b.sub', 'scarica9b.sh', 'scarica9b.sub'):
        manda_file(QUI / 'tools' / 'recas_ragionamento' / f, f'{REMOTO}/lavori/{f}')
    ssh(f'chmod +x ~/{REMOTO}/lavori/*.sh')
    loc = R / 'blocchi'; loc.mkdir(parents=True, exist_ok=True)
    voci = []
    if a.qwen:
        # 27B nella coda dei precedenti; 9B nella coda gemella. Prima l'immagine (R2), poi il testo (R1), il cammino (R3), i
        # principi uno alla volta (RRP)
        for srv, cartella, pref in (('q27', 'trace/misure/precedenti/coda', '6'), ('q9', Q9, '')):
            nomi = [('immagine', 'rri.jsonl.gz', True, 'R2 reranker che ragiona, testo e immagine della pagina'),
                    ('lista', 'rrl.jsonl.gz', False, 'R1 reranker che ragiona, solo testo, tutti i principi in una chiamata'),
                    ('cammino', 'rrc.jsonl.gz', False, 'R3 pagine attorno a piedi, stop dopo due no'),
                    ('punto', 'rrp.jsonl.gz', False, 'R1 variante: un principio per chiamata')]
            for i, (tipo, rq, img, nota) in enumerate(nomi):
                nome = (f'6{i}_rr27_{tipo}' if srv == 'q27' else f'{i + 1}0_rr9_{tipo}')
                us = f'{srv}_{rq.split(".")[0]}.jsonl'
                (loc / f'{nome}.sh').write_text(voce_qwen(nome, rq, us, srv, nota + f" ({MODELLI_RR[srv]})", img), encoding='utf-8')
                manda_file(loc / f'{nome}.sh', f'{cartella}/{nome}.sh'); voci.append(f'{cartella}/{nome}.sh')
    if a.deepseek:
        for nome, rq, us, nota in (('z_ragiona_02_dt', 'dt.jsonl.gz', 'deepseek_dt.jsonl', 'L12 atto intero o ripiego + punteggi T01 (controllo)'),
                                   ('z_ragiona_03_dp', 'dp.jsonl.gz', 'deepseek_dp.jsonl', 'L12 contesto di oggi + punteggi T01 (controllo)')):
            (loc / f'{nome}.sh').write_text(blocco_ds(nome, rq, us, nota), encoding='utf-8')
            manda_file(loc / f'{nome}.sh', f'{REMOTO}/attesa_ds/{nome}.sh')
        if not ssh('ls ~/trace/chat/coda-ds4/z_ragiona_*.sh 2>/dev/null', check=False).strip():
            ssh(f'f=$(ls ~/{REMOTO}/attesa_ds/*.sh | head -1); mv $f ~/trace/chat/coda-ds4/')
        nome = 'z_ragiona_11_dtl'
        (loc / f'{nome}.sh').write_text(blocco(nome, 'dtl.jsonl.gz', 'deepseek_dtl.jsonl', 'deepseek-lungo', 40,
                                               'L12 con l\'atto intero (contesto 262.144) + punteggi T01',
                                               dopo=f'grep -q FINITO log/{nome}.log || cp $0 $G/attesa_lungo/{nome}.sh'), encoding='utf-8')
        manda_file(loc / f'{nome}.sh', f'{REMOTO}/attesa_lungo/{nome}.sh')
    if a.scala:
        manda_scala()
    if a.lavori:
        q = ssh('condor_q climpact -af ClusterId JobStatus Cmd', check=False)
        if not ssh(f'ls ~/trace/pesi/{PESI9}/.completo 2>/dev/null', check=False).strip() and 'scarica9b.sh' not in q:
            print(ssh(f'cd ~/{REMOTO}/lavori && condor_submit scarica9b.sub'))
        if 'ragiona9b.sh' not in q:
            print(ssh(f'cd ~/{REMOTO}/lavori && condor_submit ragiona9b.sub'))
    print(ssh(f'ls ~/{Q9} ~/trace/misure/precedenti/coda ~/trace/chat/coda-ds4 ~/{REMOTO}/attesa_ds ~/{REMOTO}/attesa_lungo; '
              'condor_q climpact -af ClusterId JobStatus RequestGpus Cmd'))


def fase_prendi(a):
    ES.mkdir(parents=True, exist_ok=True)
    subprocess.run(f"scp -q 'recas:{REMOTO}/esiti/*.jsonl' {ES}/", shell=True)
    for f in sorted(ES.glob('*.jsonl')):
        print(f.name, len(jl(f)))


def completo(f, n):
    return len({x['id'] for x in jl(ES / f)}) >= n


def fase_avanza(a):
    """Da launchd ogni 30 minuti, senza mani: prende gli esiti; quando il reranker 9B (o 27B) ha finito i principi e il
    cammino, prepara D1 (dr_<modello>) e lo mette per primo nell'attesa di DeepSeek; quando D1 ha finito, prepara le
    richieste di Clef e mette la voce in coda gemella (e risottomette il lavoro gemello se non c'e'); quando gira un server
    di prova col contesto lungo se coda_lungo ha blocchi e nessun lavoro; prepara E5 della scala; rifa' le misure."""
    fase_prendi(a)
    n = len(righe_giuria()); stato = json.load(open(R / 'avanza.json')) if (R / 'avanza.json').exists() else {}
    loc = R / 'blocchi'; loc.mkdir(parents=True, exist_ok=True)
    for m, pos in (('q9', '01'), ('q27', '04')):
        quale = 'RRI' if completo(f'{m}_rri.jsonl', n) else 'RRL' if completo(f'{m}_rrl.jsonl', n) else None
        if quale and completo(f'{m}_rrc.jsonl', n) and not stato.get(f'dr_{m}'):
            f = fase_prepara_dr(argparse.Namespace(rr=m, immagine=quale == 'RRI', lungo=False))
            scp(f, f'recas:{REMOTO}/richieste/{f.name}')
            nome = f'z_ragiona_{pos}_dr_{m}'
            (loc / f'{nome}.sh').write_text(blocco_ds(nome, f.name, f'deepseek_dr_{m}.jsonl',
                                                      f'D1: L12 atto + reranker che ragiona ({MODELLI_RR[m]}, {quale} + RRC)'), encoding='utf-8')
            manda_file(loc / f'{nome}.sh', f'{REMOTO}/attesa_ds/{nome}.sh')
            if not ssh('ls ~/trace/chat/coda-ds4/z_ragiona_*.sh 2>/dev/null', check=False).strip():
                ssh(f'f=$(ls ~/{REMOTO}/attesa_ds/*.sh | head -1); [ -n "$f" ] && mv $f ~/trace/chat/coda-ds4/', check=False)
            stato[f'dr_{m}'] = {'da': quale, 'quando': time.strftime('%d/%m %H:%M')}
            print('D1 preparato da', m, quale)
    if not stato.get('clef') and any(completo(f'deepseek_dr_{m}.jsonl', n) for m in ('q9', 'q27')):
        fase_clef(a)
        scp(RQ / 'clef_giuria.jsonl.gz', f'recas:{REMOTO}/richieste/clef_giuria.jsonl.gz')
        (loc / '90_clef__libera.sh').write_text(VOCE_CLEF, encoding='utf-8')
        manda_file(loc / '90_clef__libera.sh', f'{Q9}/90_clef__libera.sh')
        stato['clef'] = time.strftime('%d/%m %H:%M')
    q = ssh('condor_q climpact -af ClusterId JobStatus Cmd', check=False)
    if ssh(f'ls ~/{Q9}/*.sh 2>/dev/null', check=False).strip() and 'ragiona9b.sh' not in q and \
            ssh(f'ls ~/trace/pesi/{PESI9}/.completo 2>/dev/null', check=False).strip():
        print(ssh(f'cd ~/{REMOTO}/lavori && condor_submit ragiona9b.sub'))     # un solo lavoro gemello alla volta
    # E5 della scala: appena il reranker 9B ha principi e cammino, nel lavoro di prova col contesto lungo
    if not stato.get('e5') and stato.get('dr_q9') and (R / 'scala' / 'scala_lunga.jsonl.gz').exists():
        subprocess.run([sys.executable, str(QUI / 'tools' / 'scala.py'), 'prepara-e5', '--rr', 'q9'], check=True)
        scp(R / 'scala' / 'scala_e5_q9.jsonl.gz', f'recas:{REMOTO}/scala/scala_e5_q9.jsonl.gz')
        scp(R / 'scala' / 'prefissi.json.gz', f'recas:{REMOTO}/scala/prefissi.json.gz')
        nome = '05_scala_e5'
        (loc / f'{nome}.sh').write_text(blocco_lungo(nome, '../scala/scala_e5_q9.jsonl.gz', 'deepseek_scala_e5.jsonl',
                                                     'scala delle leve E5 (atto intero + reranker che ragiona)', SCALA_EXTRA_LUNGO), encoding='utf-8')
        testo = (loc / f'{nome}.sh').read_text(encoding='utf-8').replace('tools/ragionamento_corri.py', 'tools/scala_corri.py')
        (loc / f'{nome}.sh').write_text(testo, encoding='utf-8')
        ssh(f'mkdir -p ~/{PRONTI_LUNGO}', check=False)
        manda_file(loc / f'{nome}.sh', (f'{REMOTO}/coda_lungo/{nome}.sh' if SI_LUNGO.exists() else f'{PRONTI_LUNGO}/{nome}.sh'))
        stato['e5'] = time.strftime('%d/%m %H:%M')
    if SI_LUNGO.exists() and ssh(f'ls ~/{REMOTO}/coda_lungo/*.sh 2>/dev/null', check=False).strip() and 'lungo_prova.sh' not in q \
            and not stato.get('lungo_prova'):
        print(ssh(f'cd ~/{REMOTO}/lavori && condor_submit lungo_prova.sub'))   # un solo lavoro di prova, una volta sola
        stato['lungo_prova'] = time.strftime('%d/%m %H:%M')
    json.dump(stato, open(R / 'avanza.json', 'w'), indent=1)
    if any(ES.glob('*.jsonl')):
        fase_misure(a)
    if any(ES.glob('deepseek_scala*.jsonl')):
        subprocess.run([sys.executable, str(QUI / 'tools' / 'scala.py'), 'misure'], check=False)
    attesi = [f'{m}_{q}.jsonl' for m in MODELLI_RR for q in ('rri', 'rrl', 'rrc', 'rrp')] + \
        [f'deepseek_{d}.jsonl' for d in ('dt', 'dp', 'dr_q9', 'dr_q27', 'dtl')] + ['deepseek_scala.jsonl', 'deepseek_scala_lunga.jsonl', 'deepseek_scala_e5.jsonl']
    mancano = [f for f in attesi if not completo(f, n)]
    if not mancano and (ES / 'clef_giuria_clef.jsonl').exists() and len(jl(ES / 'clef_giuria_clef.jsonl')) >= n:
        (R / 'FINITO').write_text(time.strftime('%d/%m/%Y %H:%M') + '\n', encoding='utf-8')
    print('mancano ancora:', mancano)


if __name__ == '__main__':
    import giornale
    giornale.avvia()
    ap = argparse.ArgumentParser()
    ap.add_argument('fase', choices=['insieme', 'contesto', 'lunghezze', 'prepara', 'secco', 'immagini', 'prepara-dr', 'clef', 'manda',
                                     'prendi', 'misure', 'avanza'])
    ap.add_argument('--qwen', action='store_true'); ap.add_argument('--deepseek', action='store_true')
    ap.add_argument('--lavori', action='store_true', help='manda: sottomette il lavoro gemello 9B e lo scaricamento dei pesi se mancano')
    ap.add_argument('--lungo', action='store_true'); ap.add_argument('--immagine', action='store_true')
    ap.add_argument('--scala', action='store_true', help='manda: la scala delle leve (tools/scala.py)')
    ap.add_argument('--rr', default='q9', choices=['q9', 'q27'])
    a = ap.parse_args()
    {'insieme': fase_insieme, 'contesto': fase_contesto, 'lunghezze': fase_lunghezze, 'prepara': fase_prepara, 'secco': secco,
     'immagini': immagini, 'prepara-dr': fase_prepara_dr, 'clef': fase_clef, 'manda': fase_manda, 'prendi': fase_prendi,
     'misure': fase_misure, 'avanza': fase_avanza}[a.fase](a)
