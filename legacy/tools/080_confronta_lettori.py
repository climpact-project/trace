"""CONFRONTO FRA LETTORI E RIORDINATORE sulle stesse righe di prova.

   Per DeepSeek il punteggio e' il numero di letture che dicono RIPRESA (0-3);
   per il riordinatore Qwen3-Reranker-4B addestrato (§61.1) la media dei tre
   semi dopo due passate. Si misura ciascuno da solo e la loro somma di ranghi,
   senza pesi imparati: dice se il riordinatore aggiunge qualcosa al lettore.
"""
import json, pathlib, sys
import numpy as np
QUI = pathlib.Path(__file__).resolve().parent.parent
T = QUI/'training'
sys.path.insert(0, str(QUI/'tools'))
_m_prova_unita = __import__('109_prova_unita')
auc = _m_prova_unita.auc
prime = _m_prova_unita.prime

righe = [x for x in (json.loads(l) for l in open(T/'urgenda_decisione_prova_corrette_larghe.jsonl', encoding='utf-8'))
         if x['frammento'] and x.get('finestra_larga')]
ids = [x['id'] for x in righe]; y = np.array([x['etichetta'] for x in righe])
rr = np.mean([json.load(open(T/f'lora_qwen_rr4b_{s}'/'passata_2'/'punteggi_prova.json')) for s in (1, 2, 3)], 0)
rango = lambda s: np.argsort(np.argsort(s)) / (len(s) - 1)
print(f'righe {len(y)}, vere {y.sum()}')
print(f'  {"riordinatore Qwen 4B addestrato":45s} AUC {auc(y, rr):.3f}  prime 20 {100*prime(y, rr, 20):.0f}%')
for v in sys.argv[1:] or ['2', '3', '4']:
    p = T/f'deepseek_api_v{v}_prova.jsonl'
    if not p.exists():
        continue
    d = {x['id']: x for x in (json.loads(l) for l in open(p, encoding='utf-8'))}
    voti = np.array([d[i]['voti_ripresa'] if i in d else np.nan for i in ids], float)
    m = ~np.isnan(voti)
    print(f'  {"DeepSeek v"+v+", voti su 3":45s} AUC {auc(y[m], voti[m]):.3f}  prime 20 {100*prime(y[m], voti[m] + 1e-6*rr[m], 20):.0f}%  (righe {m.sum()})')
    s = rango(voti[m] + 1e-6*rr[m]) + rango(rr[m])
    print(f'  {"DeepSeek v"+v+" + riordinatore, ranghi sommati":45s} AUC {auc(y[m], s):.3f}  prime 20 {100*prime(y[m], s, 20):.0f}%')
