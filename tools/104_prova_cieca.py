"""PROVA AL CIECO — il mazzo, le risposte, e lo spoglio finale.

   Cento righe proposte dal riordinatore addestrato e cento prese a sorte dalla
   STESSA fascia (nessun nome del caso nella pagina) e dallo stesso tratto di
   classifica (recupero fra il 501esimo e il 2000esimo posto), mescolate. Chi
   giudica non sa da quale gruppo viene una riga; nemmeno chi gliela mostra,
   perche' la chiave sta in un file separato che si apre solo allo spoglio.

   Il controllo e' la ragione d'essere della prova: senza, un 40% di risposte
   affermative non direbbe se e' merito del riordinatore o se quella fascia
   rende il 40% comunque.

       python3 tools/104_prova_cieca.py mostra 7
       python3 tools/104_prova_cieca.py rispondi 7 no "concetti di diritto canadese"
       python3 tools/104_prova_cieca.py spoglio
"""
import json, pathlib, sys, collections

QUI = pathlib.Path(__file__).resolve().parent.parent/'training'
MAZZO = json.loads((QUI/'prova_cieca_mazzo.json').read_text(encoding='utf-8'))
PR = QUI/'prova_cieca_risposte.json'


def risposte():
    return json.loads(PR.read_text(encoding='utf-8'))


def mostra(n, quanto=2600):
    x = MAZZO[n-1]
    print(f'RIGA {n} di {len(MAZZO)}')
    print(f'SONDA: {x["sonda"]}')
    print(f'TESTO SONDA: {x["sonda_testo"]}')
    print(f'CASO: {x["case_id"]}')
    print(f'DOC: {x["document_id"]}')
    print(f'\nFINESTRA:\n{x["finestra"][:quanto]}')


def main():
    cmd = sys.argv[1]
    if cmd == 'mostra':
        mostra(int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 2600)
    elif cmd == 'rispondi':
        n, esito = sys.argv[2], sys.argv[3]
        assert esito in ('si', 'no', 'incerto'), esito
        r = risposte()
        r[n] = {'esito': esito, 'nota': sys.argv[4] if len(sys.argv) > 4 else ''}
        PR.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8')
        c = collections.Counter(v['esito'] for v in r.values())
        print(f'registrata la {n}: {esito}. Fatte {len(r)}/{len(MAZZO)} — '
              f'si {c["si"]}, no {c["no"]}, incerte {c["incerto"]}')
        prossima = next((i for i in range(1, len(MAZZO)+1) if str(i) not in r), None)
        if prossima:
            print(); mostra(prossima)
    elif cmd == 'spoglio':
        chiave = json.loads((QUI/'prova_cieca_chiave.json').read_text(encoding='utf-8'))
        r = risposte()
        g = collections.defaultdict(collections.Counter)
        for n, v in r.items():
            g[chiave[n]['gruppo']][v['esito']] += 1
        print('gruppo  giudicate   si    no  incerte   resa')
        for k in ('A', 'B'):
            c = g[k]; tot = sum(c.values())
            nome = 'A (modello)' if k == 'A' else 'B (a sorte) '
            print(f'{nome}  {tot:6d} {c["si"]:6d} {c["no"]:5d} {c["incerto"]:7d}   '
                  f'{100*c["si"]/tot:.0f}%' if tot else f'{nome}  nessuna')
    else:
        raise SystemExit('mostra | rispondi | spoglio')


if __name__ == '__main__':
    main()
