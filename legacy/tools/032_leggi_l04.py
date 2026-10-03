"""LA LETTURA L04 COM'ERA IL 27/09/2026, per le righe che L04 non ha mai letto (30/09/2026).

   Il 30/09 il PI ha deciso di rimettere i principi di L04 sulle righe da giudicare (§63.35). 70 righe (aggiunte dalla
   ricerca corretta S02, o con la prima lettura illeggibile) L04 non le aveva mai lette: si leggono qui con le istruzioni
   di L04 vere. Le istruzioni si ricavano da quelle di oggi togliendo le tre aggiunte del 28/09: il fascicolo del caso,
   la regola delle note con la prova copiata alla lettera, e la domanda 3 sulla frase sostenuta (che decideva il principio
   sulla sola frase della nota). Verificato sulla storia del repository: la versione del 28/09 alle 22:03 non ha la
   domanda 3. Fino al 30/09 il registro riportava per L04 istruzioni con la domanda 3: sbagliate, corrette.

   Uso (su ReCaS, con DeepSeek acceso):
     .venv/bin/python tools/032_leggi_l04.py leggi --caso urgenda --etichetta l04nuove
   legge training/principi/<caso>_ripresa_righe_l04nuove.jsonl, scrive <caso>_ripresa_deepseek_l04nuove.jsonl
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
L = __import__('031_leggi_ripresa')

DOMANDA_3 = """DOMANDA 3. Quale FRASE DELL'ATTO sostiene la citazione? E' la frase del testo a cui e' agganciata la nota che cita il
caso, oppure la frase che contiene la citazione. Copiala ALLA LETTERA, nella sua lingua, massimo 60 parole. Il principio
si decide su questa frase, non sull'argomento della pagina.

"""
NOTE = """
GUARDA LE NOTE: se la frase della pagina vicina ha una sua nota che la attribuisce a un'altra fonte, non prosegue.
Se la citazione non prende nessun principio (elenco, sola descrizione), nessuna pagina prosegue."""


def istruzioni_l04(modulo=None):
    m = modulo or L.MODULO
    for vecchio, nuovo in [("\n{fascicolo}", ''), (NOTE, ''), (DOMANDA_3, ''),
                           ('{{"frase_sostenuta": "frase copiata alla lettera", "principi"', '{{"principi"'),
                           ('"prova": "frase COPIATA ALLA LETTERA dalla pagina, nella sua lingua, massimo 25 parole; mai un tuo riassunto"',
                            '"prova": "frase testuale della pagina, massimo 25 parole"')]:
        assert m.count(vecchio) == 1, vecchio[:40]
        m = m.replace(vecchio, nuovo)
    return m


if __name__ == '__main__':
    import argparse
    L.MODULO = istruzioni_l04()
    ap = argparse.ArgumentParser(); ap.add_argument('fase', choices=['leggi'])
    ap.add_argument('--caso', default='urgenda'); ap.add_argument('--letture', type=int, default=2)
    ap.add_argument('--uscita-suffisso', default=''); ap.add_argument('--etichetta', default='l04nuove')
    ap.add_argument('--paralleli', type=int, default=48); ap.add_argument('--modello', default='deepseek-v4-flash')
    ap.add_argument('--base-url', default='http://127.0.0.1:8000/v1'); ap.add_argument('--chiave-file', default=str(L.QUI/'chat'/'chiave'))
    L.leggi(ap.parse_args())
