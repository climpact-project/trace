"""QUALE PRINCIPIO PRENDE UNA CITAZIONE, E FIN DOVE ARRIVA LA RIPRESA: I PUNTEGGI DEL TRACE-RERANKER (27/09/2026).

   Sistema nuovo (§63.25): l'unita' di lavoro e' la ripresa, che parte da una citazione esplicita e si allarga
   alle pagine vicine dello stesso atto che sviluppano lo stesso principio senza il nome. Il reranker addestrato
   (Qwen3-Reranker-4B + LoRA, tre semi) da' un punteggio a ogni coppia principio-testo:
     - il BRANO della citazione (il passaggio segnalato dalla rete lessicale, con 800 caratteri prima e dopo);
     - ogni PAGINA VICINA dello stesso documento, da due pagine prima a tre dopo.
   Il nome del caso e gli ECLI si mascherano come nell'addestramento. Sono proposte: le decide il team.

   Fasi:
     prepara  Mac: training/principi/urgenda_coppie.jsonl
     punteggi ReCaS, una GPU per pezzo: training/principi/urgenda_punteggi_<pezzo>.jsonl
"""
import argparse, gzip, json, pathlib, sys
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
P = QUI/'training'/'principi'
# LA FINESTRA INTERA (01/10/2026). Fino a oggi qui c'era 2 prima e 3 dopo, mentre la regola R03 sceglie fino a 10
# pagine prima e dopo: le pagine da 4 a 10 avevano un punteggio solo per Urgenda (misura della finestra del 29/09) e,
# per caso, dove un'altra citazione dello stesso atto era vicina. Future Generations non vedeva quasi mai oltre.
PRIMA, DOPO = 10, 10
ALLARGA = 800


def prepara(caso):
    import yaml
    from prepara_training import mascheratore, SEGNAPOSTO
    import sonde as S   # la serie di sonde scelta con TRACE_SONDE (01/10/2026); senza, quella in uso
    conf = yaml.safe_load(open(S.file_caso(caso), encoding='utf-8'))
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
    # le pagine vicine una volta sola, anche se servono a piu' righe
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
