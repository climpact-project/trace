"""S07, LE RIGHE NUOVE DELLA RICERCA PER NOME CORRETTA E DELLA RETE DESCRITTIVA (04/10/2026, il PI: «sistemare tutto con
urgenza estrema ogni buco trovato»).

   Da dove. La revisione del 04/10/2026 (scratchpad della sessione: audit/fuse, audit/dedup, audit/forme) ha trovato
   quattro buchi dal lato della ricerca:
     1. la regola 1 dei gruppi (`fondi`) fondeva corrispondenze a meno di 200 caratteri anche attraverso le note a pie'
        di pagina: ~740 citazioni nascoste (Neubauer ~455, OC-32/25 ~159, CIG ~95, Urgenda ~48);
     2. 331 pagine citano una pronuncia senza nessuna forma dichiarata, ~250 citazioni vere: la RETE DESCRITTIVA;
     3. la deduplica dentro l'atto buttava anche le copie su un'altra pagina: 6 citazioni vere su 13;
     4. 28 righe unite per sbaglio dalla regola di unione (la nota 46 dentro la 44...).
   Corrette le regole (`cerca.fondi` e copie, `cerca_s05_per_atto.deduplica` e copie, `unisci_e_aggiungi` e
   tracepipe), rifatta la ricerca come S07: `tools/cerca_s07.py` (index/nomi_<caso>_2026-10-04-S07.csv) e
   `tools/rete_descrittiva.py` (index/descrittive_<caso>_2026-10-04-S07.csv).

   Che cosa e' una riga nuova. Un gruppo della ricerca S07 (o della rete descrittiva) che nessuna riga della piattaforma
   copre. Una riga della piattaforma (qualunque rete, anche «fusa» ed «esclusa», mai «semantica») copre il gruppo che
   contiene la sua posizione; se la sua posizione non cade dentro un gruppo, copre i gruppi delle corrispondenze nei 200
   caratteri dopo di lei che stanno nella sua stessa nota (la regola di `unisci_e_aggiungi.py`, con il confine di nota).
   Restano fuori, e si dice perche':
     - i documenti di D04 (training/d04/markdown_d04_registro.json): il ciclo D04 non e' ancora passato e si ferma se
       trova righe non sue nei suoi documenti; si rifanno dopo D04;
     - le righe di S06 (training/s06/righe_s06.jsonl) e quelle che S06 ha escluso perche' lo stesso documento
       (escluse_stesso_documento.jsonl): le tratta S06;
     - una copia dello stesso testo in un atto che e' lo STESSO DOCUMENTO (stessa impronta del PDF o stesso testo) di un
       atto che ha gia' la citazione: quale copia tiene la riga si sceglie dai METADATI DEL CATALOGO (il nome della parte
       e la corte della scheda trovati nell'atto: Kaiser contro Volkswagen, Landgericht Braunschweig, non Allhoff-Cramer,
       Landgericht Detmold), non dall'ordine dei percorsi, e la riga tenuta porta gli altri case_id in
       `stesso_documento_case_ids`;
     - un id gia' in banca dati (anche semantico).
   La causa di ogni riga nuova: `raggruppamento` (la sua posizione era dentro un gruppo di S05), `deduplica` (S05 la
   buttava come copia: nello stesso atto su un'altra pagina, in un altro atto della stessa causa, in un'altra causa),
   `forma_nuova` (solo forme di `forme_s07_aggiunte`), `descrittiva` (la rete descrittiva), `altro` (con il motivo).

   Fasi (senza --scrivi niente si scrive in banca dati):
     banca      fotografia di corpus_rows dei sei casi (solo lettura) -> training/s07/banca_<ora>.json.gz e le pagine con
                una riga per caso (per la rete descrittiva) -> training/s07/pagine_con_riga_<caso>.json
     righe      PROVA A SECCO: le righe nuove con la causa -> training/s07/righe_s07.jsonl, escluse.jsonl, conti.json,
                TABELLA.md (per caso e per causa)
     scrivi     le righe in corpus_rows FUORI DALLE CODE (assegnato_a_in_attesa), codici dopo il piu' alto del caso,
                gli stessi campi e la stessa provenienza di S06, estrazione S07
     contesti   le righe per i lettori (classifica_lessicali.prepara) -> training/s07/lessicali_<caso>_righe_s07.jsonl
     aggiungi   le righe in coda a training/lessicali_<caso>_righe.jsonl (copia di prima accanto, in training/s07/)
     coppie     le coppie per T01: brano delle righe e pagine attorno (10 prima, 10 dopo) senza punteggio
                -> training/s07/s07_coppie.jsonl
     ripristina le 28 righe unite per sbaglio tornano alla rete di prima (fusa_rete_prima), fuori dalle code fino alle
                letture; URG-1361 (confermata dal team, unita in una riga non giudicata) torna com'era e la sua
                destinazione non giudicata URG-1360 si unisce a lei (resta la riga giudicata, la regola di sempre)
     kaiser     le 7 righe di Neubauer dell'atto di Kaiser registrato anche sotto Allhoff-Cramer passano sotto Kaiser
     da_leggere training/s07/DA_LEGGERE.json: le righe da leggere (tipo e L05, cinque letture ciascuna) e le etichette
     rimetti    le righe di S07 con tutte le proposte tornano nelle code
   Ogni campo cambiato in banca dati si salva prima in training/s07/backup_<fase>_<ora>.json.

   Uso:  .venv/bin/python tools/recupero_s07.py banca|righe|scrivi|contesti|aggiungi|coppie|ripristina|kaiser|da_leggere|rimetti [--scrivi]
"""
import argparse
import collections
import csv
import datetime
import gzip
import json
import pathlib
import random
import re
import shutil
import sys

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
sys.path.insert(0, str(QUI))
csv.field_size_limit(10**9)
T = QUI/'training'
S7 = T/'s07'
P = T/'principi'
DATA = '2026-10-04'
ESTRAZIONE = 'S07'
CASI = ['urgenda', 'neubauer', 'future-generations', 'klimaseniorinnen', 'cig-parere-clima', 'idh-oc-32-25']
PREFISSI = {'urgenda': 'URG', 'neubauer': 'NEU', 'future-generations': 'FGC', 'klimaseniorinnen': 'KLS',
            'cig-parere-clima': 'ICJ', 'idh-oc-32-25': 'IAC'}
COPIA = 'copia di un altro frammento'
MOTIVI = {
    'raggruppamento': "citazione distinta che la vecchia regola dei 200 caratteri fondeva con la precedente attraverso "
                      "una nota a pie' di pagina, recuperata (S07, 04/10/2026)",
    'deduplica': "copia dello stesso testo in un'altra pagina o in un altro atto, che la deduplica di S05 buttava, "
                 "recuperata (S07, 04/10/2026)",
    'forma_nuova': 'forma semplice che mancava fra le forme del caso, aggiunta (S07, 04/10/2026)',
    'descrittiva': 'citazione senza nessuna forma del nome, trovata dalla rete descrittiva (S07, 04/10/2026)',
    'altro': 'riga della ricerca per nome S07 senza riga in piattaforma (S07, 04/10/2026)',
    'documento_nuovo': 'atto nuovo del corpus (D05, aggiornamento del 04/10/2026), ricerca per nome S07',
}
FINESTRA = 10
RETI_COPRONO = ('lessicale', 'entrambe', 'fusa', 'esclusa', 'descrittiva')

# le 28 righe unite per sbaglio (classificazione del 04/10/2026, audit/fuse/classificazione.tsv, classe «sbagliata»)
UNITE_PER_SBAGLIO = ['NEU-0022', 'NEU-0024', 'NEU-0037', 'NEU-0163', 'NEU-0329', 'NEU-0346', 'NEU-0727', 'NEU-0729',
                     'NEU-0751', 'NEU-0793', 'NEU-0795', 'NEU-0802', 'NEU-0806', 'NEU-0810', 'NEU-0821', 'NEU-0833',
                     'NEU-0858', 'NEU-0912', 'NEU-0914', 'NEU-0927', 'NEU-1003', 'NEU-1017', 'NEU-1027', 'NEU-1340',
                     'NEU-1441', 'NEU-1450', 'NEU-1484', 'URG-0389']
KAISER = {'da': 'allhoff-cramer-v-volkswagen-ag-complaint_edaa', 'a': 'kaiser-et-al-v-volkswagen-ag-petition_345b'}


def leggi_jsonl(f):
    with open(f, encoding='utf-8') as h:
        return [json.loads(riga) for riga in h if riga.strip()]


def scrivi_jsonl(f, xs):
    with open(f, 'w', encoding='utf-8') as h:
        for x in xs:
            h.write(json.dumps(x, ensure_ascii=False, default=str) + '\n')


def leggi_json(f):
    with open(f, encoding='utf-8') as h:
        return json.load(h)


def scrivi_json(f, x):
    with open(f, 'w', encoding='utf-8') as h:
        json.dump(x, h, ensure_ascii=False, indent=1, default=str)


def ora():
    return datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')


def leggi_csv(f):
    if not pathlib.Path(f).exists():
        return []
    with open(f, encoding='utf-8') as h:
        return list(csv.DictReader(h))


SUF = ''           # il suffisso dei CSV del lotto: '' per corpus-d04, '-d05', '-d05-scambio'...


def suffisso(lotto):
    return '' if lotto in ('', None, 'corpus-d04') else '-' + lotto.replace('_', '-')


def csv7(caso, scarti=False):
    return leggi_csv(QUI/'index'/f"nomi_{caso}_{DATA}-S07{SUF}{'.SCARTI' if scarti else ''}.csv")


def csv5(caso, scarti=False):
    return leggi_csv(QUI/'index'/f"nomi_{caso}_2026-10-02-S05{'.SCARTI' if scarti else ''}.csv")


def desc7(caso):
    return leggi_csv(QUI/'index'/f'descrittive_{caso}_{DATA}-S07{SUF}.csv')


def id_di(caso, document_id, char_start):
    from pubblica import id_riga
    return id_riga(caso, document_id, int(char_start))


def db_():
    from google.cloud import firestore
    return firestore.Client(project='climpact-drp')


# ── la banca dati ─────────────────────────────────────────────────────────────────────────────────────────────

def ultima_banca():
    fs = sorted(S7.glob('banca_*.json.gz'))
    if not fs:
        raise SystemExit('manca la fotografia della banca dati: fase banca')
    with gzip.open(fs[-1], 'rt', encoding='utf-8') as h:
        return json.load(h), fs[-1]


def fase_banca(a):
    from google.cloud import firestore
    S7.mkdir(parents=True, exist_ok=True)
    db = db_()
    banca = {}
    for caso in CASI:
        for d in db.collection('corpus_rows').where(filter=firestore.FieldFilter('caso_citato', '==', caso)).stream():
            banca[d.id] = d.to_dict()
    f = S7/f'banca_{ora()}.json.gz'
    with gzip.open(f, 'wt', encoding='utf-8') as h:
        json.dump(banca, h, ensure_ascii=False, default=str)
    for caso in CASI:
        pag = sorted({(r.get('document_id'), int(r.get('proposto_pagina') or 0)) for r in banca.values()
                      if r.get('caso_citato') == caso and r.get('document_id')})
        scrivi_json(S7/f'pagine_con_riga_{caso}.json', pag)
    print(f'fotografia: {len(banca)} righe -> {f.relative_to(QUI)}',
          dict(collections.Counter(r.get('caso_citato') for r in banca.values())))


# ── che cosa resta fuori ──────────────────────────────────────────────────────────────────────────────────────

def documenti_d04():
    f = T/'d04'/'markdown_d04_registro.json'
    if not f.exists():
        return set()
    return {d['document_id'] for d in leggi_json(f)['documenti'] if d.get('esito') == 'scritto'}


def righe_d04_preparate():
    """le righe che il ciclo D04 carichera' (training/d04/righe_d04.jsonl): coprono i loro gruppi come righe in banca"""
    f = T/'d04'/'righe_d04.jsonl'
    return leggi_jsonl(f) if f.exists() else []


def d04_scritte():
    """il ciclo D04 ha gia' scritto le sue righe? (il segno del passo, training/d04/passi/scritte)"""
    return (T/'d04'/'passi'/'scritte').exists()


def documenti_del_lotto(a):
    """i document_id a cui limitare un lotto (--documenti: un JSON con un elenco, o con la chiave «documenti» fatta di
    stringhe o di oggetti con «document_id», come training/d05/PRONTO.json); None = tutti"""
    if not getattr(a, 'documenti', ''):
        return None
    x = leggi_json(a.documenti)
    if isinstance(x, dict):
        x = x.get('documenti') or x.get('document_ids') or []
    return {d if isinstance(d, str) else d.get('document_id') for d in x}


def ids_s06():
    out = set()
    for nome in ('righe_s06.jsonl', 'escluse_stesso_documento.jsonl'):
        f = T/'s06'/nome
        if f.exists():
            out |= {x['id'] for x in leggi_jsonl(f)}
    return out


# ── i gruppi e la copertura ───────────────────────────────────────────────────────────────────────────────────

class Caso:
    """le espressioni del caso: S07 (con le forme aggiunte), S05 (per la causa), l'ancora di S03"""

    def __init__(self, caso):
        import cerca_s07 as S7m
        self.B = S7m.BASE
        f7 = QUI/'cited-cases'/f'{caso}-S07.yaml'
        self.conf7 = S7m.leggi_caso(f7)
        self.p7 = self.B.regex_caso(self.conf7)
        import cerca_s05 as S05
        self.p5 = S05.regex_caso(S05.leggi_caso(QUI/'cited-cases'/f'{caso}-S05.yaml'))
        conf3 = S05.leggi_caso(S05.file_ancora(f7))
        self.ancora = S05.regex_ancora(conf3['forme'])
        self.aggiunte = set(self.conf7.get('forme_s07_aggiunte') or [])

    def gruppi(self, testo):
        """(corrispondenze, gruppi [inizio, fine dell'ultima, [corrispondenze]]) con la regola di S07"""
        _, inizio = self.B.front_matter(testo)
        ms = self.B.corrispondenze(testo, inizio, self.p7, self.ancora)
        fuse = self.B.fondi(testo, ms)
        gr, k = [], 0
        for f in fuse:
            dentro = []
            while k < len(ms) and ms[k].start() <= f[2]:
                if ms[k].start() >= f[0].start():
                    dentro.append(ms[k])
                k += 1
            gr.append([f[0].start(), f[2], dentro])
        return ms, gr


def gruppi_coperti(testo, ms, gr, cs):
    """i gruppi (indici) che una riga della piattaforma alla posizione `cs` copre"""
    import cerca_s07 as S7m
    for i, (a, b, _) in enumerate(gr):
        if a <= cs <= b:
            return {i}
    out = set()
    for i, (a, b, dentro) in enumerate(gr):
        if any(cs <= m.start() < cs + 200 and not S7m.confine_di_nota(testo, cs, m.start()) for m in dentro):
            out.add(i)
    return out


# ── lo stesso documento: quale copia tiene la riga ────────────────────────────────────────────────────────────

_PAROLE_VUOTE = {'court', 'courts', 'regional', 'federal', 'district', 'supreme', 'constitutional', 'administrative',
                 'germany', 'netherlands', 'united', 'states', 'state', 'international', 'tribunal', 'tribunals',
                 'appeal', 'appeals', 'high', 'first', 'instance', 'superior', 'others', 'other', 'and', 'the', 'of',
                 'for', 'v', 'vs', 'et', 'al', 'inc', 'ltd', 'ag', 'gmbh', 'case', 'judgment', 'decision'}


def segni_della_scheda(meta):
    """le parole della scheda del catalogo che, trovate nell'atto, dicono a quale causa appartiene: il nome della prima
    parte (prima di «v.», «et al.», «c.») e i nomi propri della corte (la citta': Braunschweig, Detmold)"""
    nome = re.split(r'\s+(?:v\.?|vs\.?|c\.|contre|gegen)\s+|,\s*et al\.?|\s+et al\.?', str(meta.get('case_name') or ''))[0]
    parole = {w for w in re.findall(r'[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-]{3,}', nome) if w.lower() not in _PAROLE_VUOTE}
    corte = {w for w in re.findall(r'[A-ZÀ-Ý][A-Za-zÀ-ÿ\-]{4,}', str(meta.get('giurisdizioni') or ''))
             if w.lower() not in _PAROLE_VUOTE}
    return parole, corte


def punteggio_scheda(file):
    """quante parole della scheda (parte e corte) si trovano nelle prime pagine dell'atto"""
    import cerca_s05 as S05
    testo = (QUI/file).read_text(encoding='utf-8', errors='replace')
    meta, inizio = S05.front_matter(testo)
    corpo = testo[inizio:inizio + 12000]
    parole, corte = segni_della_scheda(meta)
    return sum(1 for w in parole | corte if re.search(rf'(?<![A-Za-zÀ-ÿ]){re.escape(w)}(?![A-Za-zÀ-ÿ])', corpo))


def scegli_per_scheda(files):
    """fra copie dello stesso documento, quella la cui scheda del catalogo si ritrova nell'atto (a parita', la prima
    nell'ordine dato): l'ordine dei percorsi da solo metteva l'atto di Kaiser sotto Allhoff-Cramer"""
    punti = [(punteggio_scheda(f), -i, f) for i, f in enumerate(files)]
    return max(punti)[2], {f: p for p, _, f in punti}


# ── la prova a secco ──────────────────────────────────────────────────────────────────────────────────────────

def causa_nome(cs, doc, gruppo, inizi5, scarti5, C):
    """la causa di una riga nuova della ricerca per nome"""
    k = (doc, cs)
    if k in scarti5:
        mot = scarti5[k]
        return ('deduplica', mot) if mot.startswith(COPIA) else ('altro', mot)
    if k in inizi5:
        # un gruppo che S05 aveva gia', ma che il caricamento di S05 dava per coperto da una riga a meno di 200 caratteri
        # prima, in un'altra nota (la copertura di unisci_s05 senza il confine di nota): stessa causa, sottocausa propria
        return 'raggruppamento', 'copertura'
    dentro = gruppo[2]
    if dentro and not any(C.p5.search(m.group(0)) for m in dentro):
        return 'forma_nuova', ''
    return 'raggruppamento', ''


def sotto_deduplica(r, primo_doc, primo_case):
    if not r.get('stesso_testo_di'):
        return 'deduplica_stesso_atto'
    if primo_doc == r['document_id']:
        return 'deduplica_stesso_atto'
    return 'deduplica_altro_atto_stessa_causa' if primo_case == r['case_id'] else 'deduplica_altra_causa'


def fase_righe(a):
    import recupero_s06 as R6
    global SUF
    SUF = suffisso(a.lotto)
    # LOTTO «...scambio» (D05): copie dei documenti rifatte con l'OCR fuori da markdown/ (training/d05/markdown_ocr/) e
    # versioni nuove di un atto gia' nel corpus. Le posizioni sono quelle della copia nuova, non del Markdown vivo: la
    # copertura si guarda per PAGINA (una pagina con una riga del caso e' coperta) e le righe NON si scrivono finche' il
    # Markdown vivo non e' scambiato con la copia nuova (`attende_scambio`).
    scambio = 'scambio' in a.lotto
    banca, fb = ultima_banca()
    d04, s06 = documenti_d04(), ids_s06()
    solo = documenti_del_lotto(a)
    # LOTTI (04/10/2026): S07 gira a lotti sullo stesso corpus che cresce (D04, poi D05). Le righe dei lotti di prima
    # contano come righe gia' in piattaforma anche se non sono ancora scritte: mai una riga doppia.
    prima = [x for x in (leggi_jsonl(S7/'righe_s07.jsonl') if (S7/'righe_s07.jsonl').exists() else [])
             if x.get('lotto') != a.lotto]
    ids_prima = {x['id'] for x in prima}
    d04_righe = righe_d04_preparate()
    tutte, escluse, conti = [], [], {}
    cache_imp = {}
    for caso in CASI:
        C = Caso(caso)
        mie = {i: r for i, r in banca.items() if r.get('caso_citato') == caso}
        per_doc = collections.defaultdict(list)
        for i, r in mie.items():
            if r.get('proposto_rete') in RETI_COPRONO and r.get('document_id') and r.get('char_start') is not None:
                per_doc[r['document_id']].append((i, r))
        # le righe di D04 non ancora scritte e quelle dei lotti di prima coprono i loro gruppi
        for x in d04_righe:
            if x.get('caso') == caso and x['id'] not in mie:
                per_doc[x['document_id']].append((x['id'], {'char_start': x['char_start'], 'file': x.get('file'),
                                                            'provenienza': {'ocr': (x.get('provenienza') or {}).get('ocr')}}))
        for x in prima:
            if x['caso'] == caso and x['id'] not in mie:
                per_doc[x['riga']['document_id']].append((x['id'], {'char_start': int(x['riga']['char_start']),
                                                                    'file': x['riga']['file'], 'provenienza': {}}))
        inizi5 = {(r['document_id'], int(r['char_start'])) for r in csv5(caso)}
        scarti5 = {(r['document_id'], int(r['char_start'])): r.get('motivo_scarto') or '' for r in csv5(caso, True)}
        righe7 = csv7(caso)
        righed = desc7(caso)
        file_di = {}
        for r in righe7 + righed + csv5(caso) + csv5(caso, True):
            file_di.setdefault(r['document_id'], (r['file'], r['case_id']))
        cand = collections.defaultdict(list)          # documento -> righe del CSV S07
        for r in righe7:
            cand[r['document_id']].append(r)
        c = collections.Counter()
        nuove = []
        for doc, rr in sorted(cand.items()):
            file = rr[0]['file']
            if solo is not None and doc not in solo:
                continue
            testo = (QUI/file).read_text(encoding='utf-8', errors='replace')
            ms, gr = C.gruppi(testo)
            inizio_gr = {g[0]: i for i, g in enumerate(gr)}
            coperti = set()
            if scambio:
                pag_riga = {int(r.get('proposto_pagina') or 0) for _, r in per_doc.get(doc, [])}
                marks = C.B.pagine(testo)
                coperti = {i for i, g in enumerate(gr) if C.B.pagina_di(marks, g[0]) in pag_riga}
            for i, r in ([] if scambio else per_doc.get(doc, [])):
                from posizione_dopo_ocr import traduci
                cs, _ = traduci(r.get('file') or file, int(r['char_start']), C.p7,
                                bool((r.get('provenienza') or {}).get('ocr')) if isinstance(r.get('provenienza'), dict) else False)
                coperti |= gruppi_coperti(testo, ms, gr, cs)
            for r in rr:
                cs = int(r['char_start'])
                g = inizio_gr.get(cs)
                if g is None:
                    c['fuori: inizio non ritrovato nei gruppi'] += 1
                    continue
                if g in coperti:
                    c['gia\' in piattaforma'] += 1
                    continue
                rid = id_di(caso, doc, cs)
                if rid in banca:
                    c['fuori: id gia\' in banca dati (altra rete)'] += 1
                    escluse.append({'caso': caso, 'id': rid, 'perche': 'id gia\' in banca dati',
                                    'rete_in_banca': banca[rid].get('proposto_rete')})
                    continue
                if rid in s06:
                    c['fuori: riga di S06'] += 1
                    continue
                if rid in ids_prima:
                    c['fuori: riga di un lotto di prima'] += 1
                    continue
                causa, dettaglio = causa_nome(cs, doc, gr[g], inizi5, scarti5, C)
                # un lotto di documenti nuovi (D05): S05 non li ha mai visti, la causa e' il documento nuovo
                if solo is not None and not any(k_[0] == doc for k_ in (inizi5 | set(scarti5))):
                    causa, dettaglio = 'documento_nuovo', a.lotto
                nuove.append({'caso': caso, 'id': rid, 'causa': causa, 'dettaglio': dettaglio, 'riga': r})
        # la rete descrittiva
        for r in desc7(caso):
            doc, cs = r['document_id'], int(r['char_start'])
            if solo is not None and doc not in solo:
                continue
            rid = id_di(caso, doc, cs)
            if rid in banca or rid in s06 or rid in ids_prima:
                c['descrittiva fuori: id gia\' in banca dati'] += 1
                continue
            nuove.append({'caso': caso, 'id': rid, 'causa': 'descrittiva', 'dettaglio': r.get('regola_descrittiva', ''),
                          'riga': r})
        # LOTTI DI DOCUMENTI NUOVI: un atto nuovo che e' lo stesso documento (stesso PDF o testo) di un atto che ha gia'
        # righe del caso non porta righe nuove (la citazione c'e' gia', nell'altra copia)
        if solo is not None and not scambio:
            impr_banca = {}
            for d_, rr_ in per_doc.items():
                f_ = next((r_.get('file') for _, r_ in rr_ if r_.get('file')), None)
                if f_ and (QUI/f_).exists():
                    imp_ = R6.impronte(f_, cache_imp)
                    impr_banca.setdefault(('pdf', imp_['pdf']), d_) if imp_['pdf'] else None
                    impr_banca.setdefault(('testo', imp_['testo']), d_)
            restano = []
            for x in nuove:
                imp_ = R6.impronte(x['riga']['file'], cache_imp)
                d_ = impr_banca.get(('pdf', imp_['pdf'])) if imp_['pdf'] else None
                d_ = d_ or impr_banca.get(('testo', imp_['testo']))
                if d_ and d_ != x['riga']['document_id']:
                    escluse.append({'caso': caso, 'id': x['id'], 'causa': x['causa'],
                                    'document_id': x['riga']['document_id'], 'uguale_a_documento': d_,
                                    'perche': "stesso documento di un atto gia' in piattaforma"})
                    c["fuori: stesso documento di un atto gia' in piattaforma"] += 1
                else:
                    restano.append(x)
            nuove = restano
        # le copie: sottotipo della deduplica e lo stesso documento
        tenute = []
        prese = collections.defaultdict(list)     # testo -> [(document_id, file, case_id, impronte, nuova?)]
        for x in sorted(nuove, key=lambda x: (x['riga']['document_id'], int(x['riga']['char_start']))):
            r = x['riga']
            st = r.get('stesso_testo_di') or ''
            pdoc = st.rsplit('__', 1)[0] if st else ''
            if x['causa'] == 'raggruppamento' and x.get('dettaglio') == 'copertura':
                x['sottocausa'] = 'raggruppamento_copertura'
            if x['causa'] == 'deduplica':
                x['sottocausa'] = sotto_deduplica(r, pdoc, file_di.get(pdoc, ('', ''))[1])
            # nessuna copia, o una copia nello STESSO atto su un'altra pagina: resta (la deduplica di S07)
            if not st or pdoc == r['document_id']:
                tenute.append(x)
                continue
            k = (x['causa'] == 'descrittiva', R6.chiave_testo(r))
            if not prese[k] and pdoc in file_di:
                prese[k].append((pdoc, file_di[pdoc][0], file_di[pdoc][1], R6.impronte(file_di[pdoc][0], cache_imp)))
            mie_imp = R6.impronte(r['file'], cache_imp)
            uguale = next(((d, f, cid, perche) for d, f, cid, imp in prese[k] if d != r['document_id']
                           for perche in [R6.stesso_documento(mie_imp, imp)] if perche), None)
            if uguale:
                # stesso documento: quale copia tiene la riga lo dicono i metadati del catalogo
                scelta, punti = scegli_per_scheda([uguale[1], r['file']])
                escluse.append({'caso': caso, 'id': x['id'], 'causa': x['causa'], 'document_id': r['document_id'],
                                'case_id': r['case_id'], 'uguale_a_documento': uguale[0], 'uguale_a_case_id': uguale[2],
                                'perche': uguale[3], 'scheda_sceglie': scelta, 'punti_scheda': punti,
                                'file': r['file'], 'chiave': list(k), '_x': x})
                c['fuori: stesso documento di un atto che ha gia\' la citazione'] += 1
                continue
            tenute.append(x)
            prese[k].append((r['document_id'], r['file'], r['case_id'], mie_imp))
        # LA SCHEDA DEL CATALOGO SCEGLIE LA COPIA: se la copia esclusa e' quella che i metadati indicano (Kaiser, non
        # Allhoff-Cramer) e la copia tenuta e' una riga NUOVA di questo lotto, si scambiano. Se la copia tenuta e' gia' in
        # piattaforma resta (niente righe doppie) e lo scambio va fatto a mano: elencata in scambi_a_mano.
        for e in [e for e in escluse if e.get('caso') == caso and e.get('_x') and e['scheda_sceglie'] == e['file']]:
            k = tuple(e['chiave'])
            tenuto = next((y for y in tenute if y['riga']['document_id'] == e['uguale_a_documento']
                           and (y['causa'] == 'descrittiva', R6.chiave_testo(y['riga'])) == k), None)
            if tenuto is None:
                e['scambio'] = 'a mano: la copia tenuta e\' gia\' in piattaforma'
                continue
            tenute.remove(tenuto)
            tenute.append(e['_x'])
            escluse.remove(e)
            r0 = tenuto['riga']
            escluse.append({'caso': caso, 'id': tenuto['id'], 'causa': tenuto['causa'], 'document_id': r0['document_id'],
                            'case_id': r0['case_id'], 'uguale_a_documento': e['document_id'],
                            'uguale_a_case_id': e['case_id'], 'perche': e['perche'] + ', scelta dalla scheda del catalogo',
                            'scheda_sceglie': e['scheda_sceglie'], 'punti_scheda': e['punti_scheda']})
            c['copie scambiate dalla scheda del catalogo'] += 1
        for e in escluse:
            e.pop('_x', None)
        # gli altri case_id delle copie identiche, sulla riga tenuta
        altri = collections.defaultdict(set)
        for e in escluse:
            if e.get('caso') == caso and e.get('uguale_a_documento'):
                altri[e['uguale_a_documento']].add(e['case_id'])
        for x in tenute:
            if x['riga']['document_id'] in altri:
                x['stesso_documento_case_ids'] = sorted(altri[x['riga']['document_id']] - {x['riga']['case_id']})
        for x in tenute:
            x['lotto'] = a.lotto
            # nei documenti di D04 la riga aspetta che il ciclo D04 abbia scritto le sue (si ferma se trova righe non
            # sue nei suoi documenti): `scrivi` la salta finche' non c'e' training/d04/passi/scritte
            if scambio:
                x['attende_scambio'] = True
            if x['riga']['document_id'] in d04:
                x['attende_d04'] = True
                c['nuove in documenti di D04 (si scrivono dopo D04)'] += 1
            c['nuove: ' + (x.get('sottocausa') or x['causa'])] += 1
        tutte += tenute
        conti[caso] = dict(sorted(c.items()))
        print(caso, conti[caso], flush=True)
    scrivi_jsonl(S7/'righe_s07.jsonl', prima + tutte)
    scrivi_jsonl(S7/f'escluse_{a.lotto}.jsonl', escluse)
    scrivi_json(S7/f'conti_{a.lotto}.json', {'data': DATA, 'lotto': a.lotto, 'banca': fb.name, 'casi': conti})
    tabella(tutte, conti, a.lotto)


def tabella(tutte, conti, lotto=''):
    cause = ['documento_nuovo', 'raggruppamento', 'raggruppamento_copertura', 'descrittiva', 'deduplica_stesso_atto', 'deduplica_altro_atto_stessa_causa',
             'deduplica_altra_causa', 'forma_nuova', 'altro']
    per = collections.Counter((x['caso'], x.get('sottocausa') or x['causa']) for x in tutte)
    righe = ['| caso | ' + ' | '.join(cause) + ' | totale |', '|' + '---|' * (len(cause) + 2)]
    for caso in CASI:
        righe.append(f'| {caso} | ' + ' | '.join(str(per[(caso, k)]) for k in cause)
                     + f' | {sum(per[(caso, k)] for k in cause)} |')
    righe.append('| tutti | ' + ' | '.join(str(sum(per[(c, k)] for c in CASI)) for k in cause) + f' | {len(tutte)} |')
    testo = (f'# S07, prova a secco ({DATA}), lotto {lotto}\n\nRighe nuove per caso e per causa (nessuna scritta). Cause: '
             'raggruppamento = la vecchia regola dei 200 caratteri la fondeva con la citazione precedente attraverso una '
             "nota; raggruppamento_copertura = S05 aveva il gruppo, ma il caricamento lo dava per coperto da una riga a meno "
             "di 200 caratteri in un'altra nota; descrittiva = rete descrittiva; deduplica_* = S05 la buttava come copia (stesso atto su un'altra "
             "pagina / altro atto della stessa causa / altra causa); forma_nuova = solo forme aggiunte in S07.\n\n"
             + '\n'.join(righe) + '\n\nFuori, per caso:\n\n'
             + '\n'.join(f'- {c}: ' + ', '.join(f'{k} {v}' for k, v in conti.get(c, {}).items() if not k.startswith('nuove'))
                         for c in CASI) + '\n')
    (S7/f'TABELLA_{lotto}.md').write_text(testo, encoding='utf-8')
    print(testo)


# ── la scrittura ──────────────────────────────────────────────────────────────────────────────────────────────

LOTTO = None      # --lotto: le fasi dopo `righe` lavorano solo sulle righe di quel lotto (None = tutte)


def righe_s07(caso=None, lotto=None):
    lotto = lotto or LOTTO
    return [x for x in leggi_jsonl(S7/'righe_s07.jsonl')
            if (caso is None or x['caso'] == caso) and (lotto is None or x.get('lotto') == lotto)]


def casi_s07():
    return [c for c in CASI if righe_s07(c)]


def documenti(caso, righe, esistenti, nuovi_md, data=DATA):
    """I documenti di corpus_rows delle righe di S07 di un caso, come S06 (`recupero_s06.documenti`): stessi campi,
    stessa assegnazione a turno fra chi ha righe del caso da fare, una su cinque alla cieca, chi le lavorera' in
    `assegnato_a_in_attesa`; in piu' la causa, il segno della rete descrittiva, `stesso_testo_di`,
    `stesso_documento_case_ids`."""
    from posizione_dopo_ocr import PRIMA
    from pubblica import documento
    pre = PREFISSI[caso]
    gia = [int(m.group(1)) for _, r in esistenti
           for m in [re.fullmatch(rf'{pre}-(\d+)', str(r.get('codice') or ''))] if m]
    n = max(gia, default=0)
    chi = sorted({r.get('assegnato_a') or r.get('assegnato_a_in_attesa') for _, r in esistenti
                  if r.get('proposto_rete') in ('lessicale', 'entrambe') and not r.get('esito')
                  and (r.get('assegnato_a') or r.get('assegnato_a_in_attesa'))})
    rnd = random.Random(f'{caso}-{data}-{ESTRAZIONE}')
    ids = {i for i, _ in esistenti}
    out = {}
    for k, x in enumerate(sorted(righe, key=lambda x: (x['riga']['document_id'], int(x['riga']['char_start'])))):
        r = dict(x['riga'])
        d = documento(r, caso)
        rid = x['id']
        if rid in ids:
            raise ValueError(f"riga gia' in banca dati: {rid}")
        n += 1
        prov = {'corpus': 'D03' if r['file'] in nuovi_md else 'D01', 'estrazione': ESTRAZIONE, 'tipo': '',
                'principi': {}, 'composizione': '', 'seguito': ''}
        if (PRIMA/pathlib.Path(r['file']).name).exists():
            prov['ocr'] = data
        causa = x['causa']
        d.update({'corroborazione': 'descrizione' if causa == 'descrittiva' else 'nome_presente',
                  'ordine': random.Random(rid).random(), 'codice': f'{pre}-{n:04d}',
                  'assegnato_a_in_attesa': chi[k % len(chi)] if chi else None,
                  'campione_cieco': rnd.random() < 0.20, 'incerta': False, 'provenienza': prov,
                  'motivo_aggiunta': MOTIVI.get(causa, MOTIVI['altro']), 'causa_s07': x.get('sottocausa') or causa,
                  'esecuzione_id': f'{caso}__nomi__{data}-{ESTRAZIONE}'})
        if causa == 'descrittiva':
            d.update({'proposto_rete': 'descrittiva', 'trovata_per_descrizione': True,
                      'regola_descrittiva': r.get('regola_descrittiva', ''),
                      'testo_trovato': r.get('testo_trovato', '')})
        else:
            d['proposto_rete'] = 'lessicale'
        if r.get('stesso_testo_di'):
            d['stesso_testo_di'] = r['stesso_testo_di']
        if x.get('stesso_documento_case_ids'):
            d['stesso_documento_case_ids'] = x['stesso_documento_case_ids']
        out[rid] = d
    return out


def leggi_caso_db(db, caso):
    from google.cloud import firestore
    return [(d.id, d.to_dict()) for d in db.collection('corpus_rows')
            .where(filter=firestore.FieldFilter('caso_citato', '==', caso)).stream()]


def fase_scrivi(a):
    import recupero_s06 as R6
    from google.cloud import firestore
    db = db_()
    nuovi_md = R6.markdown_d03()
    s06, d04 = ids_s06(), documenti_d04()
    for caso in casi_s07():
        esistenti = leggi_caso_db(db, caso)
        gia = {i for i, r in esistenti if (r.get('provenienza') or {}).get('estrazione') == ESTRAZIONE}
        righe = [x for x in righe_s07(caso) if x['id'] not in gia]
        aspettano = [x for x in righe if (x.get('attende_d04') and not d04_scritte()) or x.get('attende_scambio')]
        if aspettano:
            print(f"{caso}: {len(aspettano)} righe aspettano il ciclo D04 o lo scambio del Markdown (non si scrivono ora)")
            righe = [x for x in righe if x not in aspettano]
        if gia:
            print(f"{caso}: {len(gia)} righe S07 gia' in banca dati, restano come sono")
        # i controlli di S06 e D04, rifatti sulla banca dati di adesso
        ids = {i for i, _ in esistenti}
        doppie = [x['id'] for x in righe if x['id'] in ids or x['id'] in s06
                  or (x['riga']['document_id'] in d04 and not d04_scritte())]
        if doppie:
            raise SystemExit(f'{caso}: {len(doppie)} righe gia\' in banca dati, di S06 o in documenti di D04: {doppie[:5]}')
        if not righe:
            continue
        docs = documenti(caso, righe, esistenti, nuovi_md)
        codici = sorted(d['codice'] for d in docs.values())
        print(f'{caso}: {len(docs)} righe nuove, codici {codici[0]}..{codici[-1]}, fuori dalle code (in attesa '
              f'per {len({d["assegnato_a_in_attesa"] for d in docs.values()})} persone)', flush=True)
        scrivi_json(S7/f'documenti_{caso}.json', docs)
        if not a.scrivi:
            continue
        w = list(docs.items())
        for i in range(0, len(w), 400):
            b = db.batch()
            for rid, d in w[i:i + 400]:
                b.create(db.collection('corpus_rows').document(rid), {**d, 'creato_il': firestore.SERVER_TIMESTAMP})
            b.commit()
        print(f'   scritte: {len(w)}', flush=True)
    if not a.scrivi:
        print('ANTEPRIMA: niente scritto')


# ── i contesti, i file dei lettori, le coppie per T01 ────────────────────────────────────────────────────────────

def fase_contesti(a):
    """le righe per i lettori con classifica_lessicali.prepara, dalla banca dati. prepara legge solo le reti
    `lessicale` ed `entrambe`: alle righe descrittive si passa la rete «lessicale» SOLO nel file temporaneo, e la
    forma e' il testo trovato (cosi' il segno ⟦ ⟧ cade sulla descrizione); nel file dei lettori la rete torna
    «descrittiva»."""
    import classifica_lessicali as cl
    db = db_()
    for caso in casi_s07():
        ids = [x['id'] for x in righe_s07(caso)]
        docs = []
        for i in ids:
            d = db.collection('corpus_rows').document(i).get()
            if not d.exists:
                raise SystemExit(f"{i}: non e' in banca dati")
            x = {**d.to_dict(), '_id': i}
            if x.get('proposto_rete') == 'descrittiva':
                x['proposto_rete'] = 'lessicale'
                x['proposto_forma_trovata'] = x.get('testo_trovato') or x.get('proposto_forma_trovata')
            docs.append(x)
        tmp = S7/f'_esportate_{caso}.json'
        scrivi_json(tmp, docs)
        cl.RIGHE = S7/f"lessicali_{caso}_righe_s07_{LOTTO or 'tutti'}.jsonl"
        cl.prepara(str(tmp), caso)
        tmp.unlink()
        descr = {i for i in ids if i in {x['_id'] for x in docs if x.get('trovata_per_descrizione')}}
        righe = leggi_jsonl(cl.RIGHE)
        for r in righe:
            if r['id'] in descr:
                r['proposto_rete'] = 'descrittiva'
        scrivi_jsonl(cl.RIGHE, righe)
        if {x['id'] for x in righe} != set(ids):
            raise SystemExit(f'{caso}: righe per i lettori {len(righe)} su {len(ids)}')


def fase_aggiungi(a):
    """le righe di S07 in coda a training/lessicali_<caso>_righe.jsonl (il file dei lettori, della mappa dei paragrafi
    e delle pagine attorno), con la copia di prima in training/s07/; una riga gia' presente si sostituisce. Il file si
    scrive accanto e si sposta (os.replace)."""
    for caso in casi_s07():
        vivo = T/f'lessicali_{caso}_righe.jsonl'
        with open(S7/f"lessicali_{caso}_righe_s07_{LOTTO or 'tutti'}.jsonl", encoding='utf-8') as h:
            nuove = {json.loads(riga)['id']: riga if riga.endswith('\n') else riga + '\n' for riga in h if riga.strip()}
        prima = S7/f'lessicali_{caso}_righe.prima-s07.jsonl'
        if not prima.exists():
            shutil.copy(vivo, prima)
        with open(vivo, encoding='utf-8') as h:
            vecchie = [riga for riga in h if riga.strip() and json.loads(riga)['id'] not in nuove]
        tmp = vivo.with_suffix('.jsonl.s07tmp')
        tmp.write_text(''.join(vecchie) + ''.join(nuove.values()), encoding='utf-8')
        tmp.replace(vivo)
        print(caso, 'righe di prima', len(vecchie), '+ S07', len(nuove), '->', vivo.relative_to(QUI))


def pagine_con_punteggio(caso):
    """le pagine che hanno gia' un punteggio T01 (tutti i file dei punteggi del caso, S06 compreso)"""
    import recupero_s06 as R6
    gia = set()
    for f in R6.file_punteggi(caso):
        with open(f, encoding='utf-8') as h:
            for riga in h:
                x = json.loads(riga)
                if x['dove'] == 'vicina':
                    gia.add(x['pagina_id'])
    return gia


def fase_coppie(a):
    import recupero_s06 as R6
    out = []
    for caso in casi_s07():
        maschera, principi = R6.maschera_e_principi(caso)
        righe = leggi_jsonl(S7/f"lessicali_{caso}_righe_s07_{LOTTO or 'tutti'}.jsonl")
        pag = R6.testi_pagine(R6.pagine_attorno(righe) - pagine_con_punteggio(caso))
        senza = 0
        from prepara_training import SEGNAPOSTO
        for r in righe:
            br = R6.brano(r['contesto'], maschera)
            if br is None:
                senza += 1
                continue
            out += [{'caso': caso, 'riga': r['id'], 'dove': 'brano', 'pagina': r.get('pagina'), 'principio': pid,
                     'q': q, 'd': br} for pid, q in principi.items()]
        for pagid in sorted(pag):
            d = maschera.sub(SEGNAPOSTO, ' '.join(pag[pagid].split()))
            out += [{'caso': caso, 'pagina_id': pagid, 'dove': 'vicina', 'principio': pid, 'q': q, 'd': d}
                    for pid, q in principi.items()]
        print(caso, 'righe', len(righe), 'senza brano segnato', senza, 'pagine attorno senza punteggio', len(pag))
        if senza:
            raise SystemExit(f'{caso}: {senza} righe senza brano segnato: niente punteggi del brano')
    scrivi_jsonl(S7/f"s07_coppie_{LOTTO or 'tutti'}.jsonl", out)
    print('coppie', len(out))


# ── le 28 righe unite per sbaglio, URG-1361, Kaiser ───────────────────────────────────────────────────────────

def per_codice(db, codici):
    from google.cloud import firestore
    out = {}
    for c in codici:
        q = db.collection('corpus_rows').where(filter=firestore.FieldFilter('codice', '==', c)).get()
        if len(q) != 1:
            raise SystemExit(f'{c}: {len(q)} righe con questo codice')
        out[c] = (q[0].reference, q[0].to_dict())
    return out


def fase_ripristina(a):
    from google.cloud import firestore
    db = db_()
    righe = per_codice(db, UNITE_PER_SBAGLIO + ['URG-1361', 'URG-1360'])
    mosse, backup = [], {}
    for c in UNITE_PER_SBAGLIO:
        ref, r = righe[c]
        if r.get('esito'):
            print(f'{c}: giudicata, non si tocca'); continue
        if r.get('proposto_rete') != 'fusa':
            print(f"{c}: non e' piu' unita ({r.get('proposto_rete')}), non si tocca"); continue
        campi = {'proposto_rete': r.get('fusa_rete_prima') or 'lessicale',
                 'fusione_annullata': {'fusa_in': r.get('fusa_in'), 'fusa_il': r.get('fusa_il'),
                                       'fusa_motivo': r.get('fusa_motivo'), 'fusa_rete_prima': r.get('fusa_rete_prima'),
                                       'annullata_il': DATA,
                                       'motivo': "nota a pie' di pagina distinta da quella della riga di destinazione "
                                                 "(revisione del 04/10/2026, audit/fuse/classificazione.tsv)"},
                 'fusa_in': firestore.DELETE_FIELD, 'fusa_il': firestore.DELETE_FIELD,
                 'fusa_motivo': firestore.DELETE_FIELD, 'fusa_rete_prima': firestore.DELETE_FIELD}
        # fuori dalle code fino alle cinque letture, come le righe nuove (le proposte che ha sono del 27-28/09)
        if r.get('assegnato_a'):
            campi['assegnato_a_in_attesa'] = r['assegnato_a']
            campi['assegnato_a'] = None
        mosse.append((c, ref, campi))
        backup[ref.id] = {k: r.get(k) for k in ('codice', 'proposto_rete', 'fusa_in', 'fusa_il', 'fusa_motivo',
                                                'fusa_rete_prima', 'assegnato_a', 'assegnato_a_in_attesa', 'esito')}
    # URG-1361: confermata dal team il 09/09, unita il 29/09 in URG-1360 non giudicata. Torna com'era (riga lessicale
    # con il suo giudizio, nelle code come prima), e URG-1360 (stessa nota 79, non giudicata) si unisce a lei.
    ref61, r61 = righe['URG-1361']
    ref60, r60 = righe['URG-1360']
    if r61.get('proposto_rete') == 'fusa' and r61.get('fusa_in') == 'URG-1360':
        mosse.append(('URG-1361', ref61, {
            'proposto_rete': r61.get('fusa_rete_prima') or 'lessicale',
            'fusione_annullata': {'fusa_in': r61.get('fusa_in'), 'fusa_il': r61.get('fusa_il'),
                                  'fusa_motivo': r61.get('fusa_motivo'), 'fusa_rete_prima': r61.get('fusa_rete_prima'),
                                  'annullata_il': DATA,
                                  'motivo': 'riga confermata dal team (09/09) unita in una riga non giudicata: torna '
                                            'com\'era (revisione del 04/10/2026)'},
            'fusa_in': firestore.DELETE_FIELD, 'fusa_il': firestore.DELETE_FIELD,
            'fusa_motivo': firestore.DELETE_FIELD, 'fusa_rete_prima': firestore.DELETE_FIELD}))
        backup[ref61.id] = {k: r61.get(k) for k in ('codice', 'proposto_rete', 'fusa_in', 'fusa_il', 'fusa_motivo',
                                                    'fusa_rete_prima', 'esito')}
        if not r60.get('esito') and r60.get('proposto_rete') in ('lessicale', 'entrambe'):
            mosse.append(('URG-1360', ref60, {
                'proposto_rete': 'fusa', 'fusa_rete_prima': r60.get('proposto_rete'), 'fusa_in': 'URG-1361',
                'fusa_il': DATA, 'fusa_motivo': "stessa nota 79 della riga URG-1361, confermata dal team: resta la riga "
                                                "giudicata (revisione del 04/10/2026)"}))
            backup[ref60.id] = {k: r60.get(k) for k in ('codice', 'proposto_rete', 'fusa_in', 'fusa_il',
                                                        'fusa_motivo', 'fusa_rete_prima', 'esito')}
    else:
        print('URG-1361: non e\' piu\' unita in URG-1360, non si tocca')
    for c, ref, campi in mosse:
        print(c, {k: ('DELETE' if not isinstance(v, (str, dict, type(None), bool, int)) else v)
                  for k, v in campi.items() if k != 'fusione_annullata'})
    f = S7/f'backup_ripristina_{ora()}.json'
    scrivi_json(f, backup)
    print('copia di prima:', f.relative_to(QUI))
    scrivi_json(S7/'ripristinate.json', [{'codice': c, 'id': ref.id} for c, ref, _ in mosse])
    if not a.scrivi:
        print('ANTEPRIMA: niente scritto'); return
    b = db.batch()
    for _, ref, campi in mosse:
        b.update(ref, campi)
    b.commit()
    print('scritte', len(mosse))


def fase_kaiser(a):
    """Le righe di Neubauer dell'atto allhoff-cramer-v-volkswagen-ag-complaint_edaa: e' l'atto di citazione di Kaiser e
    altri contro Volkswagen (Landgericht Braunschweig, «1. Martin Kaiser»), registrato da Sabin due volte (stesso PDF,
    sha256 6d69b897...). La ricerca le ha messe sotto Allhoff-Cramer perche' il suo percorso viene prima nell'ordine
    alfabetico. Ogni riga NON giudicata si ricrea sotto kaiser-et-al-v-volkswagen-ag-petition_345b, allo stesso punto
    del testo (la posizione cambia solo per la lunghezza dell'intestazione), con lo stesso codice e le stesse proposte;
    la riga vecchia esce dalla coda come «esclusa» con il segno `spostata_in`, e il suo codice diventa <codice>-spostata
    (il codice resta uno solo). Le righe giudicate non si toccano."""
    import cerca_s05 as S05
    from google.cloud import firestore
    from pubblica import id_riga
    db = db_()
    righe = [(d.reference, d.to_dict()) for d in db.collection('corpus_rows')
             .where(filter=firestore.FieldFilter('document_id', '==', KAISER['da'])).stream()]
    righe = [(ref, r) for ref, r in righe if r.get('caso_citato') == 'neubauer']
    f_da = next(iter({r['file'] for _, r in righe}))
    f_a = next(pathlib.Path(QUI/'markdown').rglob(f"{KAISER['a']}__*.md")).relative_to(QUI)
    t_da = (QUI/f_da).read_text(encoding='utf-8', errors='replace')
    t_a = (QUI/f_a).read_text(encoding='utf-8', errors='replace')
    meta_a, ini_a = S05.front_matter(t_a)
    _, ini_da = S05.front_matter(t_da)
    assert t_da[ini_da:] == t_a[ini_a:], 'i due Markdown non hanno lo stesso testo'
    scelta, punti = scegli_per_scheda([str(f_da), str(f_a)])
    print('scheda del catalogo:', punti, '->', scelta)
    if scelta != str(f_a):
        raise SystemExit('i metadati non scelgono Kaiser: niente si sposta')
    nuove, vecchie, backup = {}, [], {}
    for ref, r in sorted(righe, key=lambda x: x[1]['codice']):
        if r.get('esito'):
            print(r['codice'], 'giudicata: non si tocca'); continue
        if r.get('proposto_rete') == 'esclusa':
            print(r['codice'], "gia' esclusa: non si tocca"); continue
        cs = int(r['char_start']) - ini_da + ini_a
        assert t_a[cs:cs + 30] == t_da[int(r['char_start']):int(r['char_start']) + 30]
        nid = id_riga('neubauer', KAISER['a'], cs)
        d = {k: v for k, v in r.items() if k != 'creato_il'}
        d.update({'document_id': KAISER['a'], 'char_start': cs, 'case_id': meta_a.get('case_id', ''),
                  'case_name': meta_a.get('case_name', ''), 'giurisdizioni': meta_a.get('giurisdizioni', ''),
                  'tipo_atto': meta_a.get('tipo_atto', ''), 'tipo_atto_sabin': meta_a.get('tipo_atto_sabin', ''),
                  'data': meta_a.get('data_deposito', ''), 'url_documento': meta_a.get('url_documento', ''),
                  'file': str(f_a), 'file_pdf': re.sub(r'\.md$', '.pdf', re.sub(r'^markdown/', 'documents/', str(f_a))),
                  'spostata_da': {'id': ref.id, 'document_id': KAISER['da'], 'case_id': r.get('case_id'),
                                  'char_start': r.get('char_start'), 'il': DATA,
                                  'motivo': "stesso PDF registrato sotto Allhoff-Cramer: l'atto e' di Kaiser e altri "
                                            "(Landgericht Braunschweig), lo dicono i metadati del catalogo"},
                  'stesso_documento_case_ids': [r.get('case_id')]})
        nuove[nid] = d
        vecchie.append((ref, r, nid))
        backup[ref.id] = r
    print(f'da spostare: {len(nuove)}', [(r["codice"], ref.id.split("__")[-1], nid.split("__")[-1]) for ref, r, nid in vecchie])
    f = S7/f'backup_kaiser_{ora()}.json'
    scrivi_json(f, backup)
    print('copia di prima:', f.relative_to(QUI))
    esistono = [i for i in nuove if db.collection('corpus_rows').document(i).get().exists]
    if esistono:
        raise SystemExit(f"righe gia' sotto Kaiser: {esistono}")
    if not a.scrivi:
        print('ANTEPRIMA: niente scritto'); return
    b = db.batch()
    for nid, d in nuove.items():
        b.create(db.collection('corpus_rows').document(nid), {**d, 'creato_il': firestore.SERVER_TIMESTAMP})
    for ref, r, nid in vecchie:
        b.update(ref, {'proposto_rete': 'esclusa', 'esclusa_rete_prima': r.get('proposto_rete'),
                       'esclusa_motivo': f"riga spostata sotto Kaiser e altri contro Volkswagen ({nid}): stesso PDF "
                                         "registrato due volte, l'atto e' di Kaiser (revisione del 04/10/2026)",
                       'esclusa_da': 'recupero_s07 (revisione del 04/10/2026)', 'esclusa_il': firestore.SERVER_TIMESTAMP,
                       'spostata_in': nid, 'codice_prima': r.get('codice'), 'codice': f"{r.get('codice')}-spostata"})
    b.commit()
    scrivi_json(S7/'kaiser_spostate.json', [{'codice': r['codice'], 'da': ref.id, 'a': nid} for ref, r, nid in vecchie])
    print('spostate', len(vecchie))


# ── il passaggio a chi legge ──────────────────────────────────────────────────────────────────────────────────

def fase_da_leggere(a):
    db = db_()
    out = {'data': DATA, 'estrazione': ESTRAZIONE,
           'che_cosa': "Righe di S07 (ricerca per nome: gruppi che non attraversano le note, rete descrittiva, deduplica "
                       "per pagina) e righe ripristinate, tutte FUORI DALLE CODE (assegnato_a_in_attesa) finche' non hanno "
                       "le proposte. Ognuna vuole cinque letture del tipo (L02 Urgenda, L03 gli altri casi) e cinque L05 "
                       "sulle pagine attorno R10, con R11/R12 e i freni, come S06; poi `recupero_s07.py rimetti --scrivi` e "
                       "tools/controllo_completezza.py.",
           'file': {'contesti': 'training/s07/lessicali_<caso>_righe_s07_<lotto>.jsonl (anche in coda a '
                                'training/lessicali_<caso>_righe.jsonl)',
                    'coppie_t01': 'training/s07/s07_coppie_<lotto>.jsonl (punteggi ancora da calcolare: T01, poi R10)',
                    'righe': 'training/s07/righe_s07.jsonl'},
           'attenzione': ["le righe con etichetta «descrittiva» hanno proposto_rete = 'descrittiva': i caricatori e i "
                          "controlli che leggono solo ('lessicale', 'entrambe') vanno allargati (carica_lessicali.py:91, "
                          "carica_ripresa, controllo_completezza.py, classifica_lessicali.prepara) e il portale (pipelineStore.js, "
                          "filtro 'lessicali' = ['lessicale', 'entrambe']) non le mostra in Uptakes finche' non si aggiunge "
                          "'descrittiva'",
                          "nelle righe descrittive il nome del caso NON c'e': il segno ⟦ ⟧ cade sulla descrizione "
                          "(testo_trovato); il prompt dice «la rete lessicale ha trovato il nome»: per queste righe va detto "
                          "che e' una descrizione"],
           'righe': []}
    # IL FILE SI ALLUNGA A LOTTI (04/10/2026): le righe dei lotti di prima restano, quelle di questo lotto si rifanno
    vecchio = leggi_json(S7/'DA_LEGGERE.json') if (S7/'DA_LEGGERE.json').exists() else {'righe': []}
    lotto = LOTTO or 'tutti'
    out['righe'] = [x for x in vecchio['righe'] if x.get('lotto') != lotto
                    and not (LOTTO is None and x.get('lotto') != 'ripristino')]
    out['lotti'] = sorted({x.get('lotto') for x in out['righe']} | {lotto})
    for caso in casi_s07():
        for x in righe_s07(caso):
            d = db.collection('corpus_rows').document(x['id']).get()
            r = d.to_dict() if d.exists else {}
            out['righe'].append({'id': x['id'], 'caso': caso, 'codice': r.get('codice'),
                                 'etichette': ['S07', x.get('sottocausa') or x['causa']]
                                 + (['descrittiva', f"regola {r.get('regola_descrittiva')}"] if x['causa'] == 'descrittiva' else [])
                                 + (['stesso_testo_di'] if r.get('stesso_testo_di') else []),
                                 'rete': r.get('proposto_rete'), 'pagina': r.get('proposto_pagina'),
                                 'document_id': r.get('document_id'), 'nella_banca_dati': d.exists,
                                 'lotto': x.get('lotto'), 'attende_d04': bool(x.get('attende_d04')) and not d.exists})
    f = S7/'ripristinate.json'
    if f.exists() and LOTTO in (None, 'ripristino'):
        out['righe'] = [x for x in out['righe'] if x.get('lotto') != 'ripristino']
        for x in leggi_json(f):
            d = db.collection('corpus_rows').document(x['id']).get().to_dict()
            if d.get('esito') or d.get('proposto_rete') == 'fusa':
                continue
            out['righe'].append({'id': x['id'], 'caso': d.get('caso_citato'), 'codice': d.get('codice'),
                                 'etichette': ['fusione_annullata'], 'rete': d.get('proposto_rete'),
                                 'pagina': d.get('proposto_pagina'), 'document_id': d.get('document_id'),
                                 'nella_banca_dati': True, 'lotto': 'ripristino'})
    out['conti'] = dict(collections.Counter(e for r in out['righe'] for e in r['etichette'][:2]))
    out['per_caso'] = dict(collections.Counter(r['caso'] for r in out['righe']))
    out['per_lotto'] = dict(collections.Counter(r.get('lotto') for r in out['righe']))
    scrivi_json(S7/'DA_LEGGERE.json', out)
    print('DA_LEGGERE.json:', len(out['righe']), 'righe', out['per_caso'], out['conti'])


def completa(r):
    return (bool(r.get('proposto_tipo_citazione')) and r.get('proposto_principi') not in (None, [])
            and bool(r.get('proposto_punteggi_principi')) and not r.get('proposta_provvisoria'))


def fase_rimetti(a):
    """le righe di DA_LEGGERE.json non giudicate, fuori dalle code e complete tornano a chi le aveva in attesa"""
    from google.cloud import firestore
    db = db_()
    ids = [x['id'] for x in leggi_json(S7/'DA_LEGGERE.json')['righe']]
    mosse, incomplete, backup = [], [], {}
    for i in ids:
        ref = db.collection('corpus_rows').document(i)
        r = ref.get().to_dict() or {}
        if r.get('esito') or not r.get('assegnato_a_in_attesa'):
            continue
        if completa(r):
            mosse.append((ref, {'assegnato_a': r['assegnato_a_in_attesa'], 'assegnato_a_in_attesa': firestore.DELETE_FIELD}))
            backup[i] = {'assegnato_a': r.get('assegnato_a'), 'assegnato_a_in_attesa': r.get('assegnato_a_in_attesa')}
        else:
            incomplete.append(i)
    print(f'da rimettere nelle code {len(mosse)}, senza tutte le proposte (restano fuori) {len(incomplete)}')
    (S7/'restano_fuori_dalle_code.txt').write_text(''.join(i + '\n' for i in incomplete), encoding='utf-8')
    scrivi_json(S7/f'backup_rimetti_{ora()}.json', backup)
    if not a.scrivi:
        print('ANTEPRIMA: niente scritto'); return
    for k in range(0, len(mosse), 400):
        b = db.batch()
        for ref, campi in mosse[k:k + 400]:
            b.update(ref, campi)
        b.commit()
    print('rimesse', len(mosse))


FASI = {'banca': fase_banca, 'righe': fase_righe, 'scrivi': fase_scrivi, 'contesti': fase_contesti,
        'aggiungi': fase_aggiungi, 'coppie': fase_coppie, 'ripristina': fase_ripristina, 'kaiser': fase_kaiser,
        'da_leggere': fase_da_leggere, 'rimetti': fase_rimetti}

if __name__ == '__main__':
    import giornale
    giornale.avvia()
    ap = argparse.ArgumentParser()
    ap.add_argument('fase', choices=list(FASI))
    ap.add_argument('--scrivi', action='store_true')
    ap.add_argument('--lotto', default='', help="il lotto (righe: obbligatorio; le altre fasi: solo le sue righe)")
    ap.add_argument('--documenti', default='', help='righe: limita il lotto a questi document_id (JSON)')
    a = ap.parse_args()
    S7.mkdir(parents=True, exist_ok=True)
    if a.fase == 'righe' and not a.lotto:
        raise SystemExit('righe vuole --lotto (es. corpus-d04, d05)')
    LOTTO = a.lotto or None
    FASI[a.fase](a)
