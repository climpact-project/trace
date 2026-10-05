"""LE CINQUE LETTURE DELLE RIGHE DI D04 (03/10/2026): lo stesso trattamento delle righe di S06 e di tutte le altre.

   Come `tools/letture_s06.py`, di cui e' la copia per D04 (quel file non si tocca: e' nella catena di S06). Il motore
   e' `tools/cinque_letture.py` (non si tocca: e' nella catena delle cinque letture), importato; cambiano solo
     - la cartella del ciclo: training/d04/ (stato.json, ciclo.log, blocchi/, righe_<caso>.txt);
     - le etichette: training/lessicali_<caso>_deepseek_d04.jsonl (tipo) e
       training/principi/<caso>_ripresa_deepseek_<serie>d04.jsonl (L05), le righe R10 in
       <caso>_ripresa_righe_<serie>d04;
     - i casi: solo quelli con righe di D04;
     - la numerazione dei blocchi: da cinque_961 in su (le cinque letture usano 001-..., S06 901-...).
   Gli strumenti su ReCaS (lettori, chiamata, freni, sonde, codebook) NON si rimandano: sono quelli con cui sono state
   lette le altre righe; se ne scrive l'impronta nel log. Si manda solo il file delle righe dei lettori dei casi di D04.

   Fasi (le chiama tools/ciclo_d04.sh): righe | prepara | letture | rapporto (come letture_s06.py)
"""
import argparse
import json
import pathlib
import subprocess
import sys

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
import cinque_letture as cl  # noqa: E402

ETICHETTA = 'd04'
C4 = cl.T/'d04'
PRIMO_BLOCCO = 960          # il primo blocco si chiama cinque_961
STRUMENTI = ('tools/classifica_lessicali.py', 'tools/leggi_ripresa.py', 'tools/leggi_l04.py',
             'tools/chiamata_deepseek.py', 'tools/freni.py', 'tools/sonde.py', 'tools/giudica_llm.py',
             'codebook/citazioni.yaml')


def etichetta_l05(caso):
    return f'{cl.serie(caso)}{ETICHETTA}'


def file_tipo(caso, et=ETICHETTA):
    return cl.T/f'lessicali_{caso}_deepseek_{et}.jsonl'


def giornale(testo):
    subprocess.run([sys.executable, str(QUI/'tools'/'giornale.py'), 'evento', '--nome', 'ciclo_d04', '--testo', testo],
                   capture_output=True, check=False)


def casi():
    import recupero_d04
    return recupero_d04.casi_d04()


def configura():
    """il motore delle cinque letture sulle righe di D04 (vedi in testa)"""
    C4.mkdir(parents=True, exist_ok=True)
    cl.C, cl.LOG, cl.CASI = C4, C4/'ciclo.log', casi()
    cl.etichetta_l05, cl.file_tipo, cl.giornale = etichetta_l05, file_tipo, giornale


def fase_righe(a):
    import recupero_d04
    from google.cloud import firestore
    configura()
    db = firestore.Client(project='climpact-drp')
    for caso in cl.CASI:
        ids = []
        for x in recupero_d04.righe_d04(caso):
            d = db.collection('corpus_rows').document(x['id']).get()
            if not d.exists:
                raise SystemExit(f"{x['id']}: non e' in banca dati")
            if not d.to_dict().get('esito'):
                ids.append(x['id'])
        (C4/f'righe_{caso}.txt').write_text('\n'.join(sorted(ids)) + '\n', encoding='utf-8')
        cl.scrivi_log(f'righe D04 non giudicate {caso}: {len(ids)}')


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
        # solo le righe di D04 nel file con l'etichetta: le altre righe hanno gia' le loro
        f.write_text(''.join(tenute), encoding='utf-8')
        n = [len(json.loads(riga)['vicine']) for riga in tenute]
        cl.scrivi_log(f'R10 {caso}: {len(n)} righe, pagine attorno per citazione media {statistics.mean(n):.2f}, '
                      f'massimo {max(n)}, senza pagine attorno {sum(1 for x in n if not x)}')


def fase_letture(a):
    configura()
    st = cl.carica_stato()
    if st['n'] == 0:
        rem = cl.r('cd ~/trace && sha256sum ' + ' '.join(STRUMENTI), check=False)
        loc = subprocess.run(['shasum', '-a', '256', *STRUMENTI], cwd=QUI, capture_output=True, text=True,
                             check=False).stdout
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
    import giornale as g
    g.avvia()
    ap = argparse.ArgumentParser()
    ap.add_argument('fase', choices=['righe', 'prepara', 'letture', 'rapporto'])
    a = ap.parse_args()
    {'righe': fase_righe, 'prepara': fase_prepara, 'letture': fase_letture, 'rapporto': fase_rapporto}[a.fase](a)
