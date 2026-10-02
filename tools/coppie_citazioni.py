"""LE COPPIE DALLE CITAZIONI ESPLICITE — dati per addestrare il primo modello senza giudizi umani.

   IDEA (PI, 25/09/2026). Nel corpus migliaia di atti citano una sentenza indicando il paragrafo
   («KlimaSeniorinnen, § 545», «Urgenda, para. 5.7.5»). Ogni citazione cosi' e' una coppia gia'
   pronta: il PARAGRAFO della sentenza citata (la proposizione) e la PAGINA che lo riprende. Si
   addestra la domanda a trovare la pagina partendo dal paragrafo, come fa la sonda.
   ANTI-SCORCIATOIA. Nella pagina si tolgono i nomi del caso (le `forme` del suo file): il modello
   deve riconoscere il ragionamento, non il nome — le riprese che cerchiamo il nome non ce l'hanno.
   ANTI-BARARE. Nessuna pagina dei documenti che stanno nelle righe di PROVA di Urgenda; nessuna
   pagina degli atti del caso citato stesso.
   NEGATIVI (per ogni coppia, due famiglie, per misurare quanto aggiunge ciascuna):
     facili      pagine a caso del corpus;
     concorrenti pagine che ragionano da ALTRE fonti: quelle che riprendono gli altri casi citati,
                 e quelle che si fondano sugli strumenti concorrenti (Accordo di Parigi, UNFCCC e
                 CBDR, artt. 2 e 8 CEDU) senza nominare il caso.
   Uscita: training/citazioni/coppie.jsonl, una riga per coppia.
"""
import csv, gzip, json, pathlib, random, re, sys, collections
import yaml
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
import build_chunks as B  # noqa: E402
T = QUI/'training'; C = T/'citazioni'
PAR = re.compile(r'(?m)^\s*(\d{1,4})\.\s+\S')
PIN_NUM = re.compile(r'(?:paras?\.?|paragraphs?|§§?|at|para)\s*(\d{1,4})(?![\d.,]\d)', re.I)
PIN_URG = re.compile(r'(?:paras?\.?|paragraphs?|§§?|r\.?\s?o\.?|rov\.?|at|legal ground)\s*(\d{1,2}\.\d{1,3}(?:\.\d{1,2})?)', re.I)
PIN_RN = re.compile(r'(?:para(?:graph)?s?\.?|§§?|Rn\.?|marginal (?:no|number)s?\.?|mn\.?)\s*(\d{1,3})(?![\d.])', re.I)

# caso -> (file delle occorrenze, documento della sentenza, modo)
CASI = {
    'klimaseniorinnen': ('occorrenze_klimaseniorinnen.csv', 'verein-klimaseniorinnen-schweiz-and-others-v-switzerland-judgment_f4b1', 'num'),
    'icj-clima-2025': ('occorrenze_icj-clima-2025.csv', 'request-for-an-advisory-opinion-on-the-obligations-of-states-with-respect-to-climate-change-decision_af16', 'num'),
    'itlos-2024': ('occorrenze_itlos-2024.csv', 'request-for-an-advisory-opinion-submitted-by-the-commission-of-small-island-states-on-climate-change-and-international-law-opinion_4f32', 'num'),
    'oc-32-25': ('occorrenze_oc-32-25.csv', 'request-for-an-advisory-opinion-on-the-scope-of-the-state-obligations-for-responding-to-the-climate-emergency-decision_3b51', 'num'),
    'urgenda': (None, None, 'mappa'),
    'neubauer': (None, None, 'mappa'),
    'future-generations': (None, None, 'mappa'),
}
CONCORRENTI = re.compile(r'Paris Agreement|UNFCCC|Framework Convention on Climate Change|common but differentiated|CBDR|'
                         r'Article[s]? (?:2|8) of the (?:European )?Convention|Art(?:icle|\.) (?:2|8) ECHR', re.I)


def file_di(doc_id):
    for p in (QUI/'markdown').rglob(f'*.md'):
        pass


def pagine_doc():
    """document_id -> file markdown (dall'indice delle pagine)."""
    fonte = {}
    with gzip.open(QUI/'index'/'pagine'/'pagine.jsonl.gz', 'rt', encoding='utf-8') as f:
        for l in f:
            x = json.loads(l); fonte.setdefault(x['doc'], x['file'])
    return fonte


def paragrafi(file):
    """Paragrafi numerati di una sentenza: catena crescente 1, 2, 3... (esclude anni e note)."""
    meta, corpo, base = B.leggi(QUI/file)
    ms = list(PAR.finditer(corpo)); presi = []; atteso = 1
    for m in ms:
        n = int(m.group(1))
        if atteso <= n <= atteso + 3:          # tollera qualche numero perso dall'OCR
            presi.append((n, m.start())); atteso = n + 1
    out = {}
    for (n, a), (_, b) in zip(presi, presi[1:] + [(0, len(corpo))]):
        t = re.sub(r'\s+', ' ', B.PAGE_RE.sub(' ', corpo[a:b])).strip()
        out[str(n)] = t[:1500]
    return out


def maschera(testo, forme):
    for f in sorted(forme, key=len, reverse=True):
        testo = re.sub(re.escape(f), '[the cited decision]', testo, flags=re.I)
    return testo


def main():
    random.seed(20260925)
    fonte = pagine_doc()
    prova = {json.loads(l)['document_id'] if 'document_id' in json.loads(l) else json.loads(l)['doc']
             for l in open(T/'urgenda_decisione_prova_corrette_larghe.jsonl', encoding='utf-8')}
    testo_pagina = {}
    def pagina(doc, n):
        k = (doc, n)
        if k not in testo_pagina:
            file = fonte.get(doc)
            if not file:
                return None
            meta, corpo, base = B.leggi(QUI/file); marks = B.pagine(corpo)
            confini = marks + [(len(corpo), None)]
            for (a, num), (b, _) in zip(confini, confini[1:]):
                testo_pagina[(doc, num)] = re.sub(r'[ \t]+', ' ', B.PAGE_RE.sub(' ', corpo[a:b])).strip()[:12000]
        return testo_pagina.get(k)
    coppie = []; conti = collections.Counter()
    for caso, (occ, sentenza, modo) in CASI.items():
        conf = yaml.safe_load(open(QUI/'cited-cases'/f'{caso}.yaml', encoding='utf-8'))
        forme = [str(f) for f in (conf.get('forme') or []) if len(str(f)) >= 4]
        escludi = set(conf.get('escludi_case_id') or [])
        if modo == 'num':
            par = paragrafi(fonte[sentenza]); righe = list(csv.DictReader(open(C/occ, encoding='utf-8')))
            print(f'{caso}: sentenza con {len(par)} paragrafi, {len(righe)} occorrenze', flush=True)
            def proposizioni(x):
                return [par[n] for n in set(PIN_NUM.findall(x['citazione_testuale'] or '')) if n in par and int(n) >= 10]
        else:
            mappa = yaml.safe_load(open(QUI/'cited-cases'/f'{caso}-mappa-paragrafi.yaml', encoding='utf-8'))['voci']
            idx = collections.defaultdict(list)
            for v in mappa:
                mm = re.match(r'(?:Rn\.?\s*)?([\d.]+)', str(v.get('paragrafo', '')))
                if mm and v.get('verbatim'):
                    idx[mm.group(1).rstrip('.')].append(v['verbatim'])
            cand = sorted(QUI.glob(f'index/candidati_{caso}*.csv'))[-1] if caso != 'urgenda' else QUI/'index'/'candidati_urgenda.csv'
            righe = [x for x in csv.DictReader(open(cand, encoding='utf-8')) if x['rete'] in ('lessicale', 'entrambe')]
            pin = PIN_URG if caso == 'urgenda' else PIN_RN
            print(f'{caso}: mappa con {len(idx)} paragrafi, {len(righe)} occorrenze', flush=True)
            def proposizioni(x):
                t = (x.get('citazione_testuale') or '') + ' ' + (x.get('finestra_pagina') or '')[:3000]
                return [q for n in set(pin.findall(t)) for q in idx.get(n, [])]
        for x in righe:
            doc = x['document_id']
            if doc in prova or x.get('case_id') in escludi or doc == sentenza:
                conti[caso, 'esclusa'] += 1; continue
            # MENZIONE IN CATENA: una nota che elenca molte sentenze non riprende nessun ragionamento.
            # Si scarta se accanto alla citazione compaiono almeno altre tre citazioni di casi o paragrafi.
            ctx = x.get('citazione_testuale') or ''
            if len(re.findall(r'\bv\.?\s|\bparas?\.|§', ctx)) >= 4 or len(re.findall(r'\(\d{4}\)|\d{4}\)', ctx)) >= 4:
                conti[caso, 'in catena'] += 1; continue
            qs = proposizioni(x)
            if not qs:
                conti[caso, 'senza paragrafo'] += 1; continue
            p = pagina(doc, int(x['pagina']))
            if not p or len(p) < 200:
                conti[caso, 'pagina mancante'] += 1; continue
            for q in qs:
                coppie.append({'caso': caso, 'domanda': q, 'pagina': maschera(p, forme), 'doc': doc, 'n_pagina': int(x['pagina'])})
                conti[caso, 'coppie'] += 1
    # doppioni (stessa proposizione, stessa pagina)
    visti = set(); uniche = []
    for c in coppie:
        k = (c['domanda'][:200], c['doc'], c['n_pagina'])
        if k not in visti:
            visti.add(k); uniche.append(c)
    print('conti:', dict(conti)); print(f'coppie {len(coppie)}, uniche {len(uniche)}', flush=True)
    # negativi concorrenti: pagine che si fondano su Parigi/UNFCCC/CBDR/CEDU senza nominare nessuno dei casi citati
    tutte_forme = [f for caso in CASI for f in map(str, yaml.safe_load(open(QUI/'cited-cases'/f'{caso}.yaml', encoding='utf-8')).get('forme') or []) if len(f) >= 4]
    patt_casi = re.compile('|'.join(re.escape(f) for f in tutte_forme), re.I)
    conc = []; facili = []
    with gzip.open(QUI/'index'/'pagine'/'pagine.jsonl.gz', 'rt', encoding='utf-8') as f:
        for l in f:
            x = json.loads(l)
            if x['doc'] in prova:
                continue
            if random.random() < 0.02:
                facili.append(x['testo'])
            if len(conc) < 20000 and CONCORRENTI.search(x['testo']) and not patt_casi.search(x['testo']):
                conc.append(x['testo'])
    print(f'negativi: facili {len(facili)}, concorrenti {len(conc)}', flush=True)
    with open(C/'coppie.jsonl', 'w', encoding='utf-8') as f:
        for c in uniche:
            f.write(json.dumps(c, ensure_ascii=False) + '\n')
    json.dump({'facili': facili[:8000], 'concorrenti': conc}, open(C/'negativi.json', 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump({f'{a}|{b}': v for (a, b), v in conti.items()}, open(C/'conti.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
