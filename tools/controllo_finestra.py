"""IL CONTROLLO DELLA FINESTRA (01/10/2026).

   Perche'. La regola R03 sceglie le pagine da far leggere fino a 10 pagine prima e 10 dopo la citazione, ma solo fra
   le pagine che hanno un punteggio del reranker. Fino al 01/10 i punteggi c'erano su tutta la finestra solo per
   Urgenda: per Neubauer e Future Generations lo strumento li dava da 2 pagine prima a 3 dopo, e Future Generations non
   vedeva quasi mai oltre. Il controllo di completezza guardava se le righe avevano proposte, non se la finestra era
   stata cercata. Qui, per ogni caso e con la serie di sonde in uso (`sonde.py`), si contano le pagine della finestra
   che esistono nel corpus e non hanno punteggio. L'operazione e' finita solo con zero pagine mancanti.

   Uso:  .venv/bin/python tools/controllo_finestra.py
"""
import glob, gzip, json, pathlib, sys, collections
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
import sonde as S
P = QUI/'training'/'principi'
LARGA = 10


def main():
    esistenti = set()
    with gzip.open(QUI/'index'/'pagine'/'pagine.jsonl.gz', 'rt', encoding='utf-8') as f:
        for l in f:
            esistenti.add(json.loads(l)['id'])
    totale = 0
    for caso in ['urgenda', 'neubauer', 'future-generations', 'klimaseniorinnen', 'cig-parere-clima', 'idh-oc-32-25']:
        suf = S.suf(caso)
        file = (glob.glob(str(P/f'{caso}_punteggi_*.jsonl')) + glob.glob(str(P/f'{caso}_finestra_punteggi_*.jsonl'))) if S.storica(caso) \
            else glob.glob(str(P/f'{caso}{suf}_punteggi_*.jsonl'))
        con = set()
        for fn in file:
            for l in open(fn, encoding='utf-8'):
                x = json.loads(l)
                if x['dove'] != 'brano':
                    con.add(x['pagina_id'])
        manca = collections.Counter(); righe_con_buchi = 0
        for l in open(QUI/'training'/f'lessicali_{caso}_righe.jsonl', encoding='utf-8'):
            r = json.loads(l); p = int(r.get('pagina') or 0); buchi = 0
            for k in range(p - LARGA, p + LARGA + 1):
                pid = f"{r['document_id']}#p{k}"
                if k != p and k > 0 and pid in esistenti and pid not in con:
                    manca[pid] += 1; buchi += 1
            righe_con_buchi += bool(buchi)
        totale += len(manca)
        print(f'{caso} (sonde {S.codice(caso)}): pagine della finestra senza punteggio {len(manca)}, citazioni con buchi {righe_con_buchi}')
    print('FINESTRA COMPLETA' if totale == 0 else f'FINESTRA INCOMPLETA: {totale} pagine senza punteggio')
    return 0 if totale == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
