"""LA LETTURA L06 (30/09/2026, prova): le istruzioni di L05 con la regola del PASSAGGIO al posto della frase sola.

   L05 (29/09) decideva il principio sulla sola frase a cui e' agganciata la nota. Il controllo del 30/09 (giudizio alla
   cieca su 120 righe di Urgenda) ha mostrato che cosi' si perdono riprese vere: un giudice riprende il principio con
   parole sue, qualche riga prima o dopo la nota (il PI: «un giudice potrebbe dirlo in modo diverso»). L06 tiene tutto
   il resto di L05 (fascicolo del caso, regola delle note, copia alla lettera, frase sostenuta, finestra larga) e decide
   il principio sul ragionamento in cui sta la citazione. Entra nella piattaforma solo se sulle righe giudicate dal PI
   fa almeno quanto L04.

   Uso (su ReCaS, con DeepSeek acceso):
     .venv/bin/python tools/099_leggi_l06.py leggi --caso urgenda --etichetta l06prova --letture 4
   legge training/principi/<caso>_ripresa_righe_l06prova.jsonl, scrive <caso>_ripresa_deepseek_l06prova.jsonl
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
L = __import__('031_leggi_ripresa')

VECCHIA_1 = """DOMANDA 1. Quali principi del caso questa citazione prende, cioe' usa, applica, discute o respinge? Anche piu'
d'uno. "nessuno" se la citazione non prende nessun principio (elenco di precedenti, solo descrizione dei fatti o
dell'esito, esempio di contenzioso). "altro" se prende qualcosa che non e' nella lista: scrivilo in una frase."""
NUOVA_1 = """DOMANDA 1. Quali principi del caso questa citazione prende, cioe' usa, applica, discute o respinge? Anche piu'
d'uno. Decidi sul RAGIONAMENTO in cui sta la citazione: la frase agganciata alla nota e le frasi dello stesso
ragionamento, prima e dopo, anche quando riprendono il principio con parole diverse da quelle del caso. Non decidere
sull'argomento generale della pagina, e non contare un principio che il passaggio nomina soltanto di sfuggita.
"nessuno" se la citazione non prende nessun principio (elenco di precedenti, solo descrizione dei fatti o
dell'esito, esempio di contenzioso). "altro" se prende qualcosa che non e' nella lista: scrivilo in una frase."""
VECCHIA_3 = """caso, oppure la frase che contiene la citazione. Copiala ALLA LETTERA, nella sua lingua, massimo 60 parole. Il principio
si decide su questa frase, non sull'argomento della pagina."""
NUOVA_3 = """caso, oppure la frase che contiene la citazione. Copiala ALLA LETTERA, nella sua lingua, massimo 60 parole. Serve a
indicare il punto nel testo; il principio si decide sul ragionamento (domanda 1), non su questa frase sola."""

assert L.MODULO.count(VECCHIA_1) == 1 and L.MODULO.count(VECCHIA_3) == 1
L.MODULO = L.MODULO.replace(VECCHIA_1, NUOVA_1).replace(VECCHIA_3, NUOVA_3)

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument('fase', choices=['leggi'])
    ap.add_argument('--caso', default='urgenda'); ap.add_argument('--letture', type=int, default=4)
    ap.add_argument('--uscita-suffisso', default=''); ap.add_argument('--etichetta', default='l06prova')
    ap.add_argument('--paralleli', type=int, default=48); ap.add_argument('--modello', default='deepseek-v4-flash')
    ap.add_argument('--base-url', default='http://127.0.0.1:8000/v1'); ap.add_argument('--chiave-file', default=str(L.QUI/'chat'/'chiave'))
    L.leggi(ap.parse_args())
