"""TRACE-Reranker scores for uptakes: which principle a citation takes, and how far the uptake extends.

   The unit of analysis is the uptake: it starts from an explicit citation and extends to neighbouring pages of
   the same document that develop the same principle without naming the case. The fine-tuned reranker
   (Qwen3-Reranker-4B + LoRA, scores averaged over three seeds) scores every principle-text pair for:
     - the citation PASSAGE (the span flagged by the lexical network, plus ALLARGA characters before and after);
     - every NEIGHBOURING PAGE of the same document, from PRIMA pages before to DOPO pages after.
   The case name and ECLI identifiers are masked as in training. Scores are proposals for human coders.

   Phases:
     prepara  local machine: training/principi/<caso>_coppie.jsonl
     punteggi GPU, one GPU per shard: training/principi/<caso>_punteggi_<pezzo>.jsonl

   Usage: python tools/ripresa_punteggi.py prepara|punteggi [--caso urgenda] [--pezzo i --pezzi n] [--adattatore DIR]
"""
import argparse, gzip, json, pathlib, sys
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
P = QUI/'training'/'principi'
PRIMA, DOPO = 2, 3
ALLARGA = 800


def prepara(caso):
    import yaml
    from prepara_training import mascheratore, SEGNAPOSTO
    conf = yaml.safe_load(open(QUI/'cited-cases'/f'{caso}.yaml', encoding='utf-8'))
    maschera = mascheratore([str(f) for f in conf['forme']] + [conf.get('nome', '')])
    principi = {s['id']: ' '.join(s['testo'].split()) for s in conf['semantic_queries']}
    righe = [json.loads(l) for l in open(QUI/'training'/f'lessicali_{caso}_righe.jsonl', encoding='utf-8')]
    serve = {}
    for r in righe:
        p = int(r.get('pagina') or 0)
        if p:
            for k in range(p - PRIMA, p + DOPO + 1):
                if k != p and k > 0:
                    serve.setdefault(f"{r['document_id']}#p{k}", set()).add(r['id'])
    pag = {}
    with gzip.open(QUI/'index'/'pagine'/'pagine.jsonl.gz', 'rt', encoding='utf-8') as f:
        for l in f:
            x = json.loads(l)
            if x['id'] in serve:
                pag[x['id']] = x['testo']
    P.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(P/f'{caso}_coppie.jsonl', 'w', encoding='utf-8') as f:
        for r in righe:
            ctx = r['contesto']
            a, b = ctx.find('[[INIZIO DEL BRANO SEGNALATO]]'), ctx.find('[[FINE DEL BRANO SEGNALATO]]')
            if a < 0 or b < 0:
                continue
            brano = ctx[max(0, a - ALLARGA): b + len('[[FINE DEL BRANO SEGNALATO]]') + ALLARGA]
            brano = brano.replace('[[INIZIO DEL BRANO SEGNALATO]]', '').replace('[[FINE DEL BRANO SEGNALATO]]', '').replace('⟦', '').replace('⟧', '')
            brano = maschera.sub(SEGNAPOSTO, ' '.join(brano.split()))
            for pid, q in principi.items():
                f.write(json.dumps({'riga': r['id'], 'dove': 'brano', 'pagina': r.get('pagina'), 'principio': pid, 'q': q, 'd': brano}, ensure_ascii=False) + '\n'); n += 1
    # each neighbouring page is scored once, even when it serves several rows
    with open(P/f'{caso}_coppie.jsonl', 'a', encoding='utf-8') as f:
        for pagid, testo in pag.items():
            d = maschera.sub(SEGNAPOSTO, ' '.join(testo.split()))
            for pid, q in principi.items():
                f.write(json.dumps({'pagina_id': pagid, 'dove': 'vicina', 'principio': pid, 'q': q, 'd': d}, ensure_ascii=False) + '\n'); n += 1
    print(f'{len(righe)} righe, {len(pag)} pagine vicine, {n} coppie -> {P}/{caso}_coppie.jsonl')


def punteggi(caso, pezzo, pezzi, adattatore):
    import numpy as np
    from peft import PeftModel
    from prova_riordinatori import QwenRiordinatore, ISTR
    C = [json.loads(l) for l in open(P/f'{caso}_coppie.jsonl', encoding='utf-8')]
    C = C[pezzo::pezzi]
    coppie = [(x['q'], x['d']) for x in C]
    print(f'pezzo {pezzo}/{pezzi}: {len(C)} coppie', flush=True)
    S = []
    for seme in (1, 2, 3):
        q = QwenRiordinatore('Qwen/Qwen3-Reranker-4B')
        q.m = PeftModel.from_pretrained(q.m, str(QUI/adattatore.replace('{seme}', str(seme))))
        S.append(q.punteggi(coppie, ISTR['ripresa'], 2560, lotto=8)); q.libera()
        print(f'  seme {seme} fatto', flush=True)
    m = np.mean(S, 0)
    with open(P/f'{caso}_punteggi_{pezzo}.jsonl', 'w', encoding='utf-8') as f:
        for x, s in zip(C, m):
            f.write(json.dumps({k: x[k] for k in ('riga', 'pagina_id', 'dove', 'pagina', 'principio') if k in x} | {'punteggio': round(float(s), 5)}) + '\n')
    print('fine', flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('fase', choices=['prepara', 'punteggi'])
    ap.add_argument('--caso', default='urgenda'); ap.add_argument('--pezzo', type=int, default=0); ap.add_argument('--pezzi', type=int, default=1)
    ap.add_argument('--adattatore', default='training/lora_qwen_rr4b_{seme}/passata_2')
    a = ap.parse_args()
    prepara(a.caso) if a.fase == 'prepara' else punteggi(a.caso, a.pezzo, a.pezzi, a.adattatore)
