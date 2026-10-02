"""LETTORI COMBINATI — la pipeline 3 del §63.5: quanto rende mettere insieme i segnali.

   Sulle stesse 133 righe di prova di Urgenda ci sono tre segnali gia' calcolati:
     Q  il primo modello, Qwen3-Embedding-4B con la domanda addestrata (semi 2 e 3,
        media; il seme 1 non ha salvato i punteggi per riga);
     R  il riordinatore Qwen3-Reranker-4B addestrato (tre semi, media);
     D  DeepSeek dall'API, domande v4 (fascicolo e regole del PI), voti su 3 letture.
   Si combinano SOMMANDO I RANGHI, senza pesi imparati: con 133 righe e 32 vere
   qualunque peso scelto su queste righe sarebbe tarato sulla prova stessa. Per ogni
   combinazione: AUC, e quante vere nelle prime 20 e 40 righe (la domanda del
   validatore: se leggo le prime N, quante sono buone?). Intervallo al 95% della
   differenza con R da solo, per ricampionamento delle righe.
"""
import itertools, json, pathlib, sys
import numpy as np
QUI = pathlib.Path(__file__).resolve().parent.parent
T = QUI/'training'
sys.path.insert(0, str(QUI/'tools'))
from prova_unita import auc  # noqa: E402

righe = [x for x in (json.loads(l) for l in open(T/'urgenda_decisione_prova_corrette_larghe.jsonl', encoding='utf-8'))
         if x['frammento'] and x.get('finestra_larga')]
ids = [x['id'] for x in righe]; y = np.array([x['etichetta'] for x in righe])
q = json.load(open(T/'esiti_primo_qwen4b_solodomanda.json'))
qi = {i: k for k, i in enumerate(q['ids'])}
Q = np.array([np.mean([q['seme2_passata1'][qi[i]], q['seme3_passata1'][qi[i]]]) for i in ids])
R = np.mean([json.load(open(T/f'lora_qwen_rr4b_{s}'/'passata_2'/'punteggi_prova.json')) for s in (1, 2, 3)], 0)
d = {x['id']: x for x in (json.loads(l) for l in open(T/(sys.argv[1] if len(sys.argv) > 1 else 'deepseek_api_v4_prova.jsonl'), encoding='utf-8'))}
D = np.array([d[i]['voti_ripresa'] for i in ids], float)
from scipy.stats import rankdata
# Ranghi MEDI sui pareggi: i voti di DeepSeek sono solo 0-3, e rompere i pareggi con un
# altro segnale (come faceva confronta_lettori) presterebbe a DeepSeek l'informazione del riordinatore.
rango = lambda s: (rankdata(s) - 1) / (len(s) - 1)
segnali = {'Q': rango(Q), 'R': rango(R), 'D': rango(D)}

def prime(s, k):
    # a parita' di punteggio l'ordine e' a caso: si usa il valore atteso
    o = np.argsort(-s, kind='stable'); soglia = s[o[k-1]]
    sopra = s > soglia; pari = s == soglia
    return round(float(y[sopra].sum() + y[pari].mean() * (k - sopra.sum())), 1)

def ic(a, b, n=4000, seme=20260925):
    rnd = np.random.default_rng(seme); diff = []
    for _ in range(n):
        j = rnd.integers(0, len(y), len(y))
        if y[j].min() == y[j].max():
            continue
        diff.append(auc(y[j], a[j]) - auc(y[j], b[j]))
    return np.percentile(diff, [2.5, 97.5])

print(f'righe {len(y)}, vere {y.sum()}')
esiti = {}
for n in (1, 2, 3):
    for combo in itertools.combinations('QRD', n):
        s = sum(segnali[c] for c in combo)
        nome = ' + '.join({'Q': 'primo modello', 'R': 'riordinatore', 'D': 'DeepSeek v4'}[c] for c in combo)
        a = auc(y, s); lo, hi = ic(s, segnali['R']) if combo != ('R',) else (0, 0)
        esiti[''.join(combo)] = {'auc': a, 'prime20': prime(s, 20), 'prime40': prime(s, 40), 'ic_diff_R': [lo, hi]}
        print(f'  {nome:45s} AUC {a:.3f}  vere nelle prime 20: {prime(s, 20):4.1f}  prime 40: {prime(s, 40):4.1f}'
              + ('' if combo == ('R',) else f'   diff. da riordinatore [{lo:+.3f}, {hi:+.3f}]'))
(T/'esiti_combina_lettori.json').write_text(json.dumps(esiti, indent=1), encoding='utf-8')
