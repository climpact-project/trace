"""QUANTO PERDE LA FINESTRA DEL SEGUITO? (28/09/2026, richiesta del PI)

   Oggi il seguito di una citazione si cerca da due pagine prima a tre dopo, con al massimo tre pagine sopra 0,5 del
   TRACE-Reranker. Il PI: «c'e' qualcosa che ci perdiamo tra le riprese implicite ancorate?». Qui il reranker da' un
   punteggio a TUTTE le pagine degli atti che citano Urgenda, e a tutte quelle degli altri atti degli stessi casi
   (il ricorso cita, la replica riprende senza citare). Poi si conta dove stanno le pagine ad alto punteggio rispetto
   alle citazioni, e si prepara un campione da leggere.

   Fasi:
     prepara  Mac -> training/principi/urgenda_finestra_coppie.jsonl (poi 028_ripresa_punteggi.py punteggi --caso urgenda_finestra)
     conta    Mac, dopo i punteggi -> training/principi/urgenda_finestra_misura.json e un campione da leggere
"""
import argparse, collections, gzip, json, pathlib, random, sys
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
P = QUI/'training'/'principi'


def documenti():
    R = [json.loads(l) for l in open(QUI/'training'/'lessicali_urgenda_righe.jsonl', encoding='utf-8')]
    citano = {r['document_id'] for r in R}
    cartelle = {pathlib.Path(r.get('file') or '').parent for r in json.load(open(QUI/'training'/'fase2'/'urgenda_corpus_rows_2026-09-26.json'))
                if r.get('proposto_rete') in ('lessicale', 'entrambe') and r.get('file')}
    stessi = set()
    for c in cartelle:
        for f in (QUI/c).glob('*.md'):
            d = f.name.split('__')[0]
            if d not in citano:
                stessi.add(d)
    return R, citano, stessi


def prepara():
    import yaml
    _m_prepara_training = __import__('026_prepara_training')
    mascheratore = _m_prepara_training.mascheratore
    SEGNAPOSTO = _m_prepara_training.SEGNAPOSTO
    conf = yaml.safe_load(open(QUI/'cited-cases'/'urgenda.yaml', encoding='utf-8'))
    maschera = mascheratore([str(f) for f in conf['forme']] + [conf.get('nome', '')])
    principi = {s['id']: ' '.join(s['testo'].split()) for s in conf['semantic_queries']}
    _, citano, stessi = documenti()
    n = collections.Counter()
    with gzip.open(QUI/'index'/'pagine'/'pagine.jsonl.gz', 'rt', encoding='utf-8') as f, \
         open(P/'urgenda_finestra_coppie.jsonl', 'w', encoding='utf-8') as out:
        for l in f:
            x = json.loads(l); d = x['id'].split('#p')[0]
            gruppo = 'cita' if d in citano else ('stesso_caso' if d in stessi else None)
            if not gruppo:
                continue
            testo = maschera.sub(SEGNAPOSTO, ' '.join(x['testo'].split()))
            for pid, q in principi.items():
                out.write(json.dumps({'pagina_id': x['id'], 'gruppo': gruppo, 'dove': 'pagina', 'principio': pid, 'q': q, 'd': testo}, ensure_ascii=False) + '\n')
            n[gruppo] += 1
    print(len(citano), 'atti che citano,', len(stessi), 'altri atti degli stessi casi; pagine', dict(n))


def conta(soglia):
    R, citano, stessi = documenti()
    cit = collections.defaultdict(set)
    for r in R:
        if r.get('pagina'):
            cit[r['document_id']].add(int(r['pagina']))
    top = {}
    for f in sorted(P.glob('urgenda_finestra_punteggi_*.jsonl')):
        for l in open(f, encoding='utf-8'):
            x = json.loads(l)
            if x['punteggio'] > top.get(x['pagina_id'], (0, ''))[0]:
                top[x['pagina_id']] = (x['punteggio'], x['principio'])
    alte = {p: v for p, v in top.items() if v[0] >= soglia}
    dist = collections.Counter(); per = collections.Counter(); campione = collections.defaultdict(list)
    for p, (s, pr) in alte.items():
        d, n = p.split('#p')[0], int(p.split('#p')[1])
        if d in citano:
            dd = min((n - c for c in cit[d]), key=abs)
            if dd == 0:
                cls = 'pagina della citazione'
            elif -2 <= dd <= 3:
                cls = 'dentro la finestra'
            elif abs(dd) <= 10:
                cls = 'fuori, entro 10 pagine'
            else:
                cls = 'fuori, oltre 10 pagine'
        else:
            cls = 'altro atto dello stesso caso'
        per[cls] += 1
        if cls.startswith('fuori') or cls.startswith('altro'):
            campione[cls].append({'pagina_id': p, 'punteggio': round(s, 3), 'principio': pr, 'classe': cls})
    rnd = random.Random(7)
    scelta = [x for cls, xs in campione.items() for x in rnd.sample(xs, min(15, len(xs)))]
    out = {'soglia': soglia, 'pagine_con_punteggio': len(top), 'pagine_alte': len(alte), 'dove_stanno': dict(per), 'campione': scelta}
    (P/'urgenda_finestra_misura.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in out.items() if k != 'campione'}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('fase', choices=['prepara', 'conta']); ap.add_argument('--soglia', type=float, default=0.8)
    a = ap.parse_args()
    prepara() if a.fase == 'prepara' else conta(a.soglia)
