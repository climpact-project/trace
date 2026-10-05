"""LE LETTURE DA CUI R16 RICOMPONE LE PROPOSTE, IN UN FILE PER CASO (04/10/2026).

   R16 (prova intera, riparazione dal testo dell'atto, frase di R15) si applica a tutte le righe gia' lette e non giudicate:
   le righe del ciclo delle cinque letture (etichetta <serie>cinque), quelle di S06 (<serie>s06) e quelle gia' rilette da
   L11 con cinque letture valide (<serie>l11: vincono su quelle di L05, perche' hanno letto le pagine intere). Le righe di
   L11 non ancora complete restano con le letture L05 finche' L11 non le finisce. Qui si scrivono, per ogni caso:
     training/principi/<caso>_ripresa_deepseek_<serie>r16.jsonl   le letture L05/L11 (campo `lettore`: L05 o L11)
     training/principi/<caso>_ripresa_righe_<serie>r16.jsonl      le righe con le pagine attorno lette da quelle letture
     training/lessicali_<caso>_deepseek_r16.jsonl                 le letture del tipo (cinque letture e S06)
   e il caricamento e': carica_ripresa.py --caso <caso> --composizione R16 --etichetta <serie>r16 --etichetta-tipo r16.
   Rifatto ogni volta da capo dai file delle letture (si puo' rilanciare quando L11 e S07 avanzano: s07 con --anche s07).
"""
import argparse, collections, json, pathlib, sys
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
import cinque_letture as cl  # noqa: E402


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--anche', default='', help='altre etichette dopo s06 (es. s07)')
    ap.add_argument('--senza-l11', action='store_true', help="04/10/2026: senza le righe gia' rilette da L11 (si caricano tutte insieme dopo)")
    a = ap.parse_args()
    for caso in cl.CASI:
        s = cl.serie(caso)
        letture, righe, tipo, n = {}, {}, {}, collections.Counter()
        for et, lettore in [('cinque', 'L05'), ('s06', 'L05')] + [(e, 'L11') for e in a.anche.split(',') if e]:
            for i, x in cl.per_id(cl.P/f'{caso}_ripresa_deepseek_{s}{et}.jsonl').items():
                letture[i] = dict(x, lettore=lettore)
            righe.update(cl.per_id(cl.P/f'{caso}_ripresa_righe_{s}{et}.jsonl'))
            tipo.update(cl.per_id(cl.T/f'lessicali_{caso}_deepseek_{et}.jsonl'))
        for i, x in ({} if a.senza_l11 else cl.per_id(cl.P/f'{caso}_ripresa_deepseek_{s}l11.jsonl')).items():
            if cl.valide(x) >= cl.K:
                letture[i] = dict(x, lettore='L11'); n['L11'] += 1
        for i, r in cl.per_id(cl.P/f'{caso}_ripresa_righe_{s}l11.jsonl').items():
            if letture.get(i, {}).get('lettore') == 'L11':
                righe[i] = r
        with open(cl.P/f'{caso}_ripresa_deepseek_{s}r16.jsonl', 'w', encoding='utf-8') as f:
            f.writelines(json.dumps(x, ensure_ascii=False) + '\n' for x in letture.values())
        with open(cl.P/f'{caso}_ripresa_righe_{s}r16.jsonl', 'w', encoding='utf-8') as f:
            f.writelines(json.dumps(x, ensure_ascii=False) + '\n' for x in righe.values())
        with open(cl.T/f'lessicali_{caso}_deepseek_r16.jsonl', 'w', encoding='utf-8') as f:
            f.writelines(json.dumps(x, ensure_ascii=False) + '\n' for x in tipo.values())
        print(f'{caso}: letture {len(letture)} (L11 complete {n["L11"]}), righe {len(righe)}, tipo {len(tipo)}')


if __name__ == '__main__':
    main()
