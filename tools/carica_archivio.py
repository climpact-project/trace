"""L'ARCHIVIO DI TRACE IN BANCA DATI (29/09/2026, richiesta del PI: «vedere tutto di tutto» nel portale).

   Fino a oggi in banca dati c'erano le righe con la proposta finale e il registro delle versioni; il resto viveva
   solo nei file del Mac. Qui si carica, in collezioni a parte (le righe non si toccano):
     trace_letture/<riga>       ogni lettura della macchina su quella riga, per intero: le due letture di DeepSeek sul
                                tipo (con il ragionamento), le due sulla ripresa, le risposte del TRACE-Reader dove la
                                riga era nella prova; ciascuna col codice di versione e il file da cui viene
     trace_misure/<id>          le misure: finestra del seguito, controllo dei giudizi semantici, rilettura delle 102
                                righe, accordo di DeepSeek, prove del Reader e dei riordinatori, giudizi del PI su Uptakes
     trace_file/<id>            i file del metodo: codebook, casi, mappe dei paragrafi, fascicoli
     trace_addestramenti/<V..>  su quali righe e' stato addestrato e provato ciascun modello
   Si puo' rilanciare: sovrascrive con lo stato attuale dei file.

   Uso:  .venv/bin/python tools/carica_archivio.py [--scrivi]
"""
import argparse, collections, json, pathlib
from google.cloud import firestore
QUI = pathlib.Path(__file__).resolve().parent.parent
T = QUI/'training'
P = T/'principi'
CASI = ('urgenda', 'neubauer', 'future-generations')
MAX = 900_000  # sotto il megabyte di un documento di Firestore


def jl(f):
    return [json.loads(l) for l in open(f, encoding='utf-8')] if f.exists() else []


def letture():
    """{riga: [lettura, ...]} con versione, file e contenuto."""
    L = collections.defaultdict(list)
    fonti = []
    for c in CASI:
        tipo = 'L02' if c == 'urgenda' else 'L03'
        if c == 'urgenda':
            fonti.append((T/'lessicali_urgenda_deepseek.jsonl', 'tipo', 'L01'))
            fonti.append((T/'lessicali_urgenda_deepseek_glm.jsonl', 'tipo', 'prova di GLM-5.3-Flash (scartato)'))
            fonti.append((T/'lessicali_urgenda_deepseek_v2.jsonl', 'tipo', 'L02'))
            fonti.append((T/'lessicali_urgenda_deepseek_ocr2.jsonl', 'tipo', 'L02 (righe nuove o rilette sul testo OCR, 01/10)'))
        else:
            fonti.append((T/f'lessicali_{c}_deepseek.jsonl', 'tipo', 'L03'))
            fonti.append((T/f'lessicali_{c}_deepseek_ocr2.jsonl', 'tipo', 'L03 (righe nuove o rilette sul testo OCR, 01/10)'))
        fonti.append((T/f'lessicali_{c}_deepseek_v10.jsonl', 'tipo', f'{tipo} (righe aggiunte o rilette il 29/09)'))
        fonti.append((P/f'{c}_ripresa_deepseek.jsonl', 'ripresa', 'L04'))
        fonti.append((P/f'{c}_ripresa_deepseek_v2.jsonl', 'ripresa', 'L05'))
        fonti.append((P/f'{c}_ripresa_deepseek_v10.jsonl', 'ripresa', 'L05 (righe aggiunte o rilette il 29/09)'))
        fonti.append((P/f'{c}_ripresa_deepseek_l04nuove.jsonl', 'ripresa', 'L04 (righe che L04 non aveva letto, lette il 30/09)'))
        fonti.append((P/f'{c}_ripresa_deepseek_l06prova.jsonl', 'ripresa', 'L06 (prova del 30/09, non in piattaforma)'))
        fonti.append((P/f'{c}_seguito_l07.jsonl', 'seguito', 'L07'))
        fonti.append((P/f'{c}_ripresa_deepseek_l04ocr.jsonl', 'ripresa', 'L04 (righe trovate dopo l\'OCR, lette il 01/10)'))
        fonti.append((P/f'{c}_ripresa_deepseek_ocr.jsonl', 'ripresa', 'L05 (righe trovate dopo l\'OCR, lette il 01/10)'))
        fonti.append((P/f'{c}_ripresa_deepseek_l04ocr2.jsonl', 'ripresa', 'L04 (righe nuove o rilette sul testo OCR, 01/10)'))
        fonti.append((P/f'{c}_ripresa_deepseek_ocr2.jsonl', 'ripresa', 'L05 (righe nuove o rilette sul testo OCR, 01/10)'))
    for f, cosa, ver in fonti:
        for x in jl(f):
            e = {'cosa': cosa, 'versione': ver, 'file': str(f.relative_to(QUI)), 'data': x.get('data', ''),
                 'modello': x.get('modello', ''), 'letture': json.dumps(x.get('letture'), ensure_ascii=False)}
            # solo i ragionamenti non vuoti: fino al 29/09 il campo si leggeva col nome sbagliato e restava vuoto
            rag = [str(r)[:4000] for r in (x.get('ragionamenti') or []) if str(r).strip()]
            if rag:
                e['ragionamenti'] = rag
            L[x['id']].append(e)
    for v, f in (('T02 (TRACE-Reader v0)', 'valuta_v0_p2.jsonl'), ('T03 (TRACE-Reader v1)', 'valuta_v1_p2.jsonl'),
                 ('Qwen3-14B senza addestramento', 'valuta_base_p2.jsonl')):
        for x in jl(T/'reader'/f):
            L[x['id']].append({'cosa': 'reader', 'versione': v, 'file': f'training/reader/{f}',
                               'letture': json.dumps({k: x.get(k) for k in x if k != 'id'}, ensure_ascii=False)})
    return L


MISURE = [
    ('finestra-seguito', 'La finestra del seguito: dove stanno le pagine con punteggio alto', 'training/principi/urgenda_finestra_misura.json'),
    ('finestra-campione', 'Finestra: le 28 pagine fuori finestra lette', 'training/principi/urgenda_finestra_campione.json'),
    ('controllo-giudizi-semantici', 'Controllo di 400 giudizi semantici con DeepSeek', 'training/audit/sintesi.json'),
    ('rilettura-102-righe', 'Rilettura delle 102 righe «confermate» della ripresa implicita', 'pubblicazione/trace-0.1/rilettura/RAPPORTO-GIUDIZI.md'),
    ('rilettura-102-righe-esiti', 'Rilettura delle 102 righe: esiti riga per riga', 'pubblicazione/trace-0.1/rilettura/esito_tutto.json'),
    ('giudizi-pi-uptakes', 'Giudizi nella scheda Uptakes: che cosa e\' stato tenuto delle proposte', 'training/principi/giudizi_uptakes_2026-09-28.json'),
    ('deepseek-tipo-urgenda-prima', 'DeepSeek sul tipo, Urgenda, prima lettura: accordo con i validatori', 'training/lessicali_urgenda_deepseek_misure.json'),
    ('deepseek-tipo-urgenda-v02', 'DeepSeek sul tipo, Urgenda, L02: accordo con i validatori', 'training/lessicali_urgenda_deepseek_v2_misure.json'),
    ('deepseek-tipo-neubauer', 'DeepSeek sul tipo, Neubauer (L03)', 'training/lessicali_neubauer_deepseek_misure.json'),
    ('deepseek-tipo-fg', 'DeepSeek sul tipo, Future Generations (L03)', 'training/lessicali_future-generations_deepseek_misure.json'),
    ('glm-tipo-urgenda', 'GLM-5.3-Flash sul tipo, Urgenda (scartato)', 'training/lessicali_urgenda_deepseek_glm_misure.json'),
    ('reader-v0-prova', 'TRACE-Reader v0 sulla prova (risposte)', 'training/reader/valuta_v0_p2.jsonl'),
    ('reader-v1-prova', 'TRACE-Reader v1 sulla prova (risposte)', 'training/reader/valuta_v1_p2.jsonl'),
    ('reader-base-prova', 'Qwen3-14B senza addestramento sulla prova (risposte)', 'training/reader/valuta_base_p2.jsonl'),
    ('combina-lettori', 'Combinazioni di lettori', 'training/esiti_combina_lettori.json'),
    ('riordino', 'Riordinatore: prove', 'training/esiti_riordino.json'),
    ('primo-qwen4b', 'Riordinatore Qwen3-4B: prima prova', 'training/esiti_primo_qwen4b.json'),
    ('divisione-prova', 'La divisione congelata fra addestramento e prova (22/09)', 'training/divisione.json'),
]
for k in range(1, 6):
    MISURE.append((f'riordino-{k}', f'Riordinatore: seme {k}', f'training/esiti_riordino_{k}.json'))
    MISURE.append((f'riordino-corrette-{k}', f'Riordinatore su etichette corrette: seme {k}', f'training/esiti_riordino_corrette_{k}.json'))
for v in ('finestra_larga', 'pagina_piu_mezza', 'senzaform', 'solodomanda'):
    MISURE.append((f'primo-qwen4b-{v}', f'Riordinatore Qwen3-4B: variante {v.replace("_", " ")}', f'training/esiti_primo_qwen4b_{v}.json'))

FILE = [('codebook', 'Codebook delle citazioni', 'codebook/citazioni.yaml')]
for c in CASI:
    FILE += [(f'{c}-caso', f'Caso {c}: forme del nome e principi', f'cited-cases/{c}.yaml'),
             (f'{c}-mappa', f'Caso {c}: mappa dei paragrafi', f'cited-cases/{c}-mappa-paragrafi.yaml'),
             (f'{c}-fascicolo', f'Caso {c}: fascicolo', f'cited-cases/{c}-fascicolo.md')]


def addestramenti():
    ids = lambda f: [x['id'] for x in jl(T/'reader'/f)]
    div = json.load(open(T/'divisione.json', encoding='utf-8'))
    return {
        'T01': {'descrizione': 'TRACE-Reranker 0.1: giudizi del team sulle righe semantiche di Urgenda, divisione congelata del 22/09',
                'divisione': json.dumps(div, ensure_ascii=False)},
        'T02': {'descrizione': 'TRACE-Reader v0: letture di DeepSeek concordi sul tipo; la prova e\' esclusa',
                'righe_addestramento': ids('urgenda_addestramento.jsonl'), 'righe_prova': ids('urgenda_prova.jsonl')},
        'T03': {'descrizione': 'TRACE-Reader v1: come v0, con pagine vicine e principi; la prova e\' esclusa',
                'righe_addestramento': ids('urgenda_addestramento_v1.jsonl'), 'righe_prova': ids('urgenda_prova_v1.jsonl')},
    }


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--scrivi', action='store_true'); a = ap.parse_args()
    db = firestore.Client(project='climpact-drp')
    codici = {d.id: d.to_dict().get('codice') for d in db.collection('corpus_rows').select(['codice']).stream()}
    L = letture()
    print('righe con letture', len(L), collections.Counter(e['versione'] for v in L.values() for e in v))
    scr = []
    for rid, v in L.items():
        doc = {'riga': rid, 'caso': rid.split('__')[0], 'codice': codici.get(rid), 'letture': v}
        while len(json.dumps(doc, ensure_ascii=False).encode()) > MAX:
            for e in doc['letture']:
                if e.get('ragionamenti'):
                    e['ragionamenti'] = [r[:len(r) // 2] for r in e['ragionamenti']]
        scr.append(('trace_letture', rid.replace('/', '_')[:1400], doc))
    for mid, titolo, f in MISURE:
        p = QUI/f
        if not p.exists():
            print('manca', f); continue
        t = p.read_text(encoding='utf-8')
        doc = {'titolo': titolo, 'file': f, 'byte': len(t.encode()), 'formato': p.suffix.lstrip('.'),
               'modificato': p.stat().st_mtime}
        doc['testo'] = t if len(t.encode()) <= MAX else t[:MAX // 2]
        doc['tagliato'] = len(t.encode()) > MAX
        scr.append(('trace_misure', mid, doc))
    # ogni file citato dal registro (istruzioni date ai modelli, codice eseguito): cosi' dal portale si apre
    reg = json.load(open(QUI/'versioni'/'registro.json', encoding='utf-8'))
    gia = {f for _, _, f in FILE}
    for v in reg:
        for campo, nome in (('istruzioni', 'Istruzioni'), ('codice_sorgente', 'Codice')):
            for x in v.get(campo) or []:
                f = x['file']
                if f not in gia and (QUI/f).exists():
                    gia.add(f)
                    FILE.append((f.replace('/', '__'), f"{nome} di {v['codice']}: {f.split('/')[-1]}", f))
    for fid, titolo, f in FILE:
        p = QUI/f
        t = p.read_text(encoding='utf-8')
        scr.append(('trace_file', fid, {'titolo': titolo, 'file': f, 'testo': t[:MAX], 'byte': len(t.encode())}))
    for cod, d in addestramenti().items():
        scr.append(('trace_addestramenti', cod, d))
    print('documenti da scrivere', collections.Counter(c for c, _, _ in scr))
    if not a.scrivi:
        return
    for i in range(0, len(scr), 50):
        b = db.batch()
        for c, k, d in scr[i:i + 50]:
            b.set(db.collection(c).document(k), {**d, 'caricato_il': firestore.SERVER_TIMESTAMP})
        b.commit()
    print('scritto')


if __name__ == '__main__':
    main()
