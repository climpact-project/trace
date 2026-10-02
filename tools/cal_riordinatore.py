"""IL RIORDINATORE SI RIADDESTRA SUI GIUDIZI NUOVI (apprendimento attivo, 27/09/2026). GPU, ReCaS.

   Addestramento: la divisione congelata del 22/09 PIU' gli esempi dei blocchi (`cal_dati.py`). Esame: sempre le
   stesse righe di prova (`urgenda_decisione_prova_corrette_larghe.jsonl`), mai viste. Stessa ricetta del
   TRACE-Reranker (§58.7, §63.10): Qwen3-Reranker-4B, LoRA rango 16, istruzione «ripresa», 2.560 token, tre semi,
   due passate.

   REGOLA FISSATA PRIMA: il nuovo adattatore si adotta solo se i tre semi insieme fanno sull'esame un'AUC non
   inferiore a quella dell'adattatore in uso, misurata nello stesso lavoro. Altrimenti resta quello di prima.

   Uso:  python tools/cal_riordinatore.py --etichetta b1 --attuale 'training/lora_qwen_rr4b_{seme}/passata_2'
         -> training/cal/esito_<etichetta>.json
"""
import argparse, json, pathlib, sys
import numpy as np
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
from prova_riordinatori import QwenRiordinatore, ISTR, carica, auc, addestra_qwen  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--caso', default='urgenda')
    ap.add_argument('--etichetta', required=True)
    ap.add_argument('--attuale', required=True)
    ap.add_argument('--passate', type=int, default=2)
    a = ap.parse_args()
    from peft import PeftModel
    tr, te = carica('addestramento'), carica('prova')
    cal = [json.loads(l) for l in open(QUI/'training'/'cal'/f'{a.caso}_cal_addestramento.jsonl', encoding='utf-8') if l.strip()]
    for x in tr + te + cal:
        x['etichetta'] = int(x['etichetta'])
    y = np.array([x['etichetta'] for x in te])
    print(f'addestramento {len(tr)} + blocchi {len(cal)} ({sum(x["etichetta"] for x in cal)} positive) | esame {len(te)} ({y.sum()} vere)', flush=True)
    coppie = [(x['sonda_testo'], x['finestra']) for x in te]
    # L'ADATTATORE IN USO, misurato qui, sulle stesse righe
    S0 = []
    for seme in (1, 2, 3):
        q = QwenRiordinatore('Qwen/Qwen3-Reranker-4B')
        q.m = PeftModel.from_pretrained(q.m, str(QUI/a.attuale.replace('{seme}', str(seme))))
        S0.append(q.punteggi(coppie, ISTR['ripresa'], 2560)); q.libera()
    auc0 = auc(y, np.mean(S0, 0))
    print(f'adattatore in uso: AUC {auc0:.3f}', flush=True)
    S1 = []
    for seme in (1, 2, 3):
        cart = QUI/'training'/f'lora_qwen_rr4b_{a.etichetta}_{seme}'; cart.mkdir(parents=True, exist_ok=True)
        S1.append(addestra_qwen('Qwen/Qwen3-Reranker-4B', tr + cal, te, y, ISTR['ripresa'], 2560, seme,
                                epoche=a.passate, salva=cart))
    auc1 = auc(y, np.mean(S1, 0))
    adotta = bool(auc1 >= auc0)
    esito = {'etichetta': a.etichetta, 'esempi_blocchi': len(cal), 'auc_in_uso': round(auc0, 4), 'auc_nuovo': round(auc1, 4),
             'adottato': adotta,
             'adattatore': f'training/lora_qwen_rr4b_{a.etichetta}_{{seme}}/passata_{a.passate}' if adotta else a.attuale}
    (QUI/'training'/'cal').mkdir(exist_ok=True)
    (QUI/'training'/'cal'/f'esito_{a.etichetta}.json').write_text(json.dumps(esito, indent=1), encoding='utf-8')
    print(json.dumps(esito), flush=True)
    print('fine')


if __name__ == '__main__':
    main()
