"""LE CINQUE LETTURE DELLE RIGHE DI S06 (03/10/2026): lo stesso trattamento di tutte le altre righe di oggi.

   Il motore e' quello del ciclo delle cinque letture, `tools/cinque_letture.py`: cinque letture del tipo (L02 Urgenda,
   L03 gli altri casi) e cinque letture L05 sulle pagine attorno scelte con R10 (soglia 0,5 a ogni distanza dentro +-10
   pagine, senza tetto), a blocchi di circa 50 minuti nelle code interne dei lavori di DeepSeek su ReCaS (coda-ds2,
   coda-ds3; coda-ds4 col lavoro di ricambio acceso), con gli stessi strumenti gia' su ReCaS. Quel file non si tocca
   (gira nel ciclo delle cinque letture): qui lo si importa e si cambiano solo
     - la cartella del ciclo: training/s06/ (stato.json, ciclo.log, blocchi/, righe_<caso>.txt);
     - le etichette: le letture si raccolgono in training/lessicali_<caso>_deepseek_s06.jsonl (tipo) e in
       training/principi/<caso>_ripresa_deepseek_<serie>s06.jsonl (L05), le righe R10 in
       <caso>_ripresa_righe_<serie>s06;
     - i casi: solo quelli con righe di S06;
     - la numerazione dei blocchi: da cinque_901 in su, per non incontrare i blocchi del ciclo delle cinque letture
       nelle cartelle di ReCaS (training/cinque/fatti, training/cinque/vivo).
   Gli strumenti su ReCaS (classifica_lessicali.py, leggi_ripresa.py, chiamata_deepseek.py, freni.py, sonde.py) NON
   si rimandano: sono quelli con cui sono state lette oggi le altre righe; se ne scrive l'impronta nel log. Si manda
   solo il file delle righe dei lettori dei casi di S06 (training/lessicali_<caso>_righe.jsonl), che ora ha anche le
   righe nuove.

   Fasi (le chiama tools/ciclo_s06.sh):
     righe     training/s06/righe_<caso>.txt: le righe di S06 non ancora giudicate (dalla banca dati)
     prepara   le pagine attorno R10 delle righe di S06 (leggi_ripresa.prepara, poi solo le righe di S06 nel file)
     letture   il ciclo dei blocchi fino alla fine (riprende da training/s06/stato.json)
     rapporto  training/s06/RAPPORTO.md dalle prove a secco di R11
"""
import argparse
import json
import pathlib
import subprocess
import sys

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
import cinque_letture as cl  # noqa: E402

ETICHETTA = 's06'
C6 = cl.T/'s06'
PRIMO_BLOCCO = 900          # il primo blocco si chiama cinque_901
STRUMENTI = ('tools/classifica_lessicali.py', 'tools/leggi_ripresa.py', 'tools/leggi_l04.py',
             'tools/chiamata_deepseek.py', 'tools/freni.py', 'tools/sonde.py', 'tools/giudica_llm.py',
             'codebook/citazioni.yaml')


def etichetta_l05(caso):
    return f'{cl.serie(caso)}{ETICHETTA}'


def file_tipo(caso, et=ETICHETTA):
    return cl.T/f'lessicali_{caso}_deepseek_{et}.jsonl'


def giornale(testo):
    subprocess.run([sys.executable, str(QUI/'tools'/'giornale.py'), 'evento', '--nome', 'ciclo_s06', '--testo', testo],
                   capture_output=True)


def casi():
    import recupero_s06
    return recupero_s06.casi_s06()


def configura():
    """il motore delle cinque letture sulle righe di S06 (vedi in testa)"""
    C6.mkdir(parents=True, exist_ok=True)
    cl.C, cl.LOG, cl.CASI = C6, C6/'ciclo.log', casi()
    cl.etichetta_l05, cl.file_tipo, cl.giornale = etichetta_l05, file_tipo, giornale


def fase_righe(a):
    import recupero_s06
    from google.cloud import firestore
    configura()
    db = firestore.Client(project='climpact-drp')
    for caso in cl.CASI:
        ids = []
        for x in recupero_s06.righe_s06(caso):
            d = db.collection('corpus_rows').document(x['id']).get()
            if not d.exists:
                raise SystemExit(f"{x['id']}: non e' in banca dati")
            if not d.to_dict().get('esito'):
                ids.append(x['id'])
        (C6/f'righe_{caso}.txt').write_text('\n'.join(sorted(ids)) + '\n', encoding='utf-8')
        cl.scrivi_log(f'righe S06 non giudicate {caso}: {len(ids)}')


def fase_prepara(a):
    import statistics

    import leggi_ripresa
    configura()
    for caso in cl.CASI:
        et = etichetta_l05(caso)
        leggi_ripresa.prepara(caso, 'R10', et)
        f = leggi_ripresa.file_righe(caso, et)
        ids = set(cl.righe_di(caso))
        with open(f, encoding='utf-8') as h:
            tenute = [riga for riga in h if riga.strip() and json.loads(riga)['id'] in ids]
        if len(tenute) != len(ids):
            raise SystemExit(f'{caso}: righe R10 {len(tenute)} su {len(ids)}')
        # solo le righe di S06 nel file con l'etichetta: le altre righe hanno gia' le loro (etichetta cinque)
        f.write_text(''.join(tenute), encoding='utf-8')
        n = [len(json.loads(riga)['vicine']) for riga in tenute]
        cl.scrivi_log(f'R10 {caso}: {len(n)} righe, pagine attorno per citazione media {statistics.mean(n):.2f}, '
                      f'massimo {max(n)}, senza pagine attorno {sum(1 for x in n if not x)}')


def fase_letture(a):
    configura()
    st = cl.carica_stato()
    if st['n'] == 0:
        # gli strumenti restano quelli di oggi su ReCaS (vedi in testa): se ne scrive l'impronta, con quella locale
        rem = cl.r('cd ~/trace && sha256sum ' + ' '.join(STRUMENTI), check=False)
        loc = subprocess.run(['shasum', '-a', '256', *STRUMENTI], cwd=QUI, capture_output=True, text=True).stdout
        cl.scrivi_log('strumenti su ReCaS (impronte):\n' + rem.strip() + '\nsul Mac:\n' + loc.strip())
        for caso in cl.CASI:
            cl.manda(cl.T/f'lessicali_{caso}_righe.jsonl', f'training/lessicali_{caso}_righe.jsonl')
        cl.r('mkdir -p ~/trace/training/cinque/fatti ~/trace/training/cinque/vivo')
        st['n'] = PRIMO_BLOCCO
        cl.salva_stato(st)
        cl.scrivi_log(f'righe dei lettori su ReCaS ({", ".join(cl.CASI)}); blocchi da cinque_{PRIMO_BLOCCO + 1}')
    cl.fase_letture(a)


def fase_rapporto(a):
    configura()
    cl.fase_rapporto(a)


if __name__ == '__main__':
    import giornale
    giornale.avvia()
    ap = argparse.ArgumentParser()
    ap.add_argument('fase', choices=['righe', 'prepara', 'letture', 'rapporto'])
    a = ap.parse_args()
    {'righe': fase_righe, 'prepara': fase_prepara, 'letture': fase_letture, 'rapporto': fase_rapporto}[a.fase](a)
