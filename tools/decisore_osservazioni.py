"""IL DECISORE SULLE OSSERVAZIONI — il verdetto calcolato dalle risposte del lettore.

   PERCHE' (§61.5, §61.6). Il lettore legge bene e decide male: Qwen nominava
   la fonte diversa e poi diceva «ripresa»; DeepSeek trovava piu' riprese
   contando gli anelli che col suo verdetto. Qui le risposte chiuse del modulo
   di osservazioni (versione 4: fascicolo e regole del PI) diventano numeri, e
   una regressione logistica addestrata SOLO sulle 263 righe di addestramento
   ne ricava una probabilita' di ripresa, misurata sulle 137 di prova.
   I coefficienti si leggono: dicono quale osservazione pesa e in che verso.
"""
import json, pathlib, sys
import numpy as np
from sklearn.linear_model import LogisticRegression
QUI = pathlib.Path(__file__).resolve().parent.parent
T = QUI/'training'
sys.path.insert(0, str(QUI/'tools'))
from prova_unita import auc, prime  # noqa: E402

NOMI = ['voti RIPRESA', 'voti ALTRA_FONTE', 'cita Urgenda', 'paragrafi di Urgenda', 'Urgenda fonte principale',
        'Urgenda fra le fonti', 'tramite', 'afferma', 'non autonomo', 'anelli (media)', 'parla la corte',
        'la corte riassume una parte', 'parte o amicus', 'illeggibili']


def tratti(x):
    L = [g for g in x['letture'] if g.get('esito') != 'ILLEGGIBILE']
    n = max(len(L), 1)
    m = lambda f: sum(1 for g in L if f(g)) / n
    return [m(lambda g: g.get('esito') == 'RIPRESA'), m(lambda g: g.get('esito') == 'ALTRA_FONTE'),
            m(lambda g: g.get('cita_urgenda') is True), m(lambda g: bool(g.get('paragrafi_urgenda'))),
            m(lambda g: g.get('fonte_principale') == 'Urgenda'), m(lambda g: 'Urgenda' in (g.get('fonti') or [])),
            m(lambda g: bool(g.get('tramite'))), m(lambda g: g.get('afferma') is True), m(lambda g: g.get('autonomo') is False),
            sum(len(g.get('anelli') or []) for g in L) / n / 5, m(lambda g: g.get('chi_parla') == 'corte'),
            m(lambda g: g.get('chi_parla') == 'corte_riassume_parte'),
            m(lambda g: g.get('chi_parla') in ('parte', 'interveniente_o_amicus')), (3 - len(L)) / 3]


def carica(parte):
    return [json.loads(l) for l in open(T/f'deepseek_api_v4_{parte}.jsonl', encoding='utf-8')]


tr, te = carica('addestramento'), carica('prova')
Xtr, ytr = np.array([tratti(x) for x in tr]), np.array([x['etichetta'] for x in tr])
Xte, yte = np.array([tratti(x) for x in te]), np.array([x['etichetta'] for x in te])
m = LogisticRegression(C=1.0, max_iter=2000, class_weight='balanced').fit(Xtr, ytr)
p = m.predict_proba(Xte)[:, 1]
print(f'addestramento {len(tr)} ({ytr.sum()} vere) | prova {len(te)} ({yte.sum()} vere)')
print(f'  verdetto di DeepSeek (voti RIPRESA)   AUC {auc(yte, Xte[:,0]):.3f}  prime 20 {100*prime(yte, Xte[:,0]+1e-6*p, 20):.0f}%')
print(f'  decisore sulle osservazioni          AUC {auc(yte, p):.3f}  prime 20 {100*prime(yte, p, 20):.0f}%')
for soglia in (0.3, 0.4, 0.5):
    s = p >= soglia; tp = (s & (yte == 1)).sum()
    print(f'    soglia {soglia}: propone {s.sum():3d}  precisione {tp/max(s.sum(),1):.0%}  trova {tp}/{yte.sum()} = {tp/yte.sum():.0%}')
print('  pesi (sulle righe di addestramento):')
for n, c in sorted(zip(NOMI, m.coef_[0]), key=lambda z: -abs(z[1])):
    print(f'    {n:28s} {c:+.2f}')
# con il riordinatore: righe comuni
righe = [x for x in (json.loads(l) for l in open(T/'urgenda_decisione_prova_corrette_larghe.jsonl', encoding='utf-8')) if x['frammento'] and x.get('finestra_larga')]
rr = dict(zip([x['id'] for x in righe], np.mean([json.load(open(T/f'lora_qwen_rr4b_{s}'/'passata_2'/'punteggi_prova.json')) for s in (1, 2, 3)], 0)))
ids = [x['id'] for x in te]; k = np.array([i in rr for i in ids])
r = np.array([rr.get(i, 0) for i in ids])[k]; pk, yk = p[k], yte[k]
rango = lambda s: np.argsort(np.argsort(s)) / (len(s) - 1)
print(f'  sulle {k.sum()} righe col riordinatore: riordinatore {auc(yk, r):.3f}, decisore {auc(yk, pk):.3f}, '
      f'insieme {auc(yk, rango(r)+rango(pk)):.3f} (prime 20 {100*prime(yk, rango(r)+rango(pk), 20):.0f}%)')
