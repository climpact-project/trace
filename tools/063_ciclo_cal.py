"""IL CICLO AUTOMATICO DELL'APPRENDIMENTO ATTIVO (27/09/2026). Gira sul Mac ogni mezz'ora (launchd).

   Metodo in `METODO-IN-UNA-PAGINA.md`, documento unico §63.22. A ogni giro guarda a che punto e' e fa UN passo:

     attesa     il blocco in piattaforma e' finito? (nessuna riga del blocco senza esito, salvo le «da discutere»)
                -> rapporto del blocco, esempi nuovi (`071_cal_dati.py`), riaddestramento su ReCaS
     addestra   il riaddestramento e' finito? -> se il nuovo riordinatore non e' peggiore, si adotta;
                riordino della lista su 8 GPU
     riordina   il riordino e' finito? -> blocco successivo scelto, passaggi su ReCaS
     passaggi   i passaggi sono pronti? -> blocco successivo in piattaforma; torna ad `attesa`
     fermo      la regola di stop e' scattata: niente piu' blocchi finche' il PI non decide

   REGOLA DI STOP, FISSATA PRIMA: ci si ferma quando due blocchi di fila portano ciascuno meno di 5 riprese
   (confermate + riclassificate) ogni 100 pagine giudicate.

   IL RAPPORTO sta sulla piattaforma, nel giro del blocco (`corpus_runs/<esecuzione>.rapporto`): il PI lo vede nel
   coordinamento. Una notifica del Mac avvisa quando un blocco nuovo e' caricato o qualcosa si ferma.
   Lo stato sta in `training/cal/stato_<caso>.json`: se il Mac si spegne, al giro dopo riparte da li'.

   Uso:  .venv/bin/python tools/063_ciclo_cal.py tick   (una volta; launchd lo chiama ogni 30 minuti)
         .venv/bin/python tools/063_ciclo_cal.py stato
"""
import argparse, datetime, json, pathlib, subprocess, sys
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
CAL = QUI/'training'/'cal'; CAL.mkdir(parents=True, exist_ok=True)
F2 = QUI/'training'/'fase2'
PY = str(QUI/'.venv'/'bin'/'python')
RECAS = 'recas'; RT = '/lustrehome/climpact/trace'
N_BLOCCO = 100
SOGLIA_STOP = 5


def log(msg):
    riga = f'{datetime.datetime.now():%Y-%m-%d %H:%M} {msg}'
    print(riga, flush=True)
    with open(CAL/'ciclo.log', 'a', encoding='utf-8') as f:
        f.write(riga + '\n')


def notifica(msg):
    try:
        subprocess.run(['osascript', '-e', f'display notification "{msg}" with title "TRACE"'], timeout=10)
    except Exception:
        pass


def ssh(cmd, timeout=120):
    r = subprocess.run(['ssh', '-o', 'BatchMode=yes', RECAS, cmd], capture_output=True, text=True,
                       timeout=timeout, stdin=subprocess.DEVNULL)
    return r.stdout.strip()


def scp_su(locale, remoto):
    subprocess.run(['scp', '-q', str(locale), f'{RECAS}:{RT}/{remoto}'], check=True, timeout=600)


def scp_giu(remoto, locale):
    r = subprocess.run(['scp', '-q', f'{RECAS}:{RT}/{remoto}', str(locale)], timeout=600)
    return r.returncode == 0


SUB = """universe = vanilla
executable = {rt}/{script}
arguments = {argomenti}
output = {rt}/log_cal/{nome}_$(Process).out
error = {rt}/log_cal/{nome}_$(Process).err
log = {rt}/log_cal/{nome}.log
request_cpus = 4
request_memory = 96 GB
request_gpus = 1
periodic_remove = (JobStatus == 2) && ((time() - EnteredCurrentStatus) > 179000)
queue {quanti}
"""


def sottometti(nome, script, argomenti, quanti=1):
    """Il file del lavoro si scrive qui e si copia: niente `$(...)` dentro una riga di ssh."""
    loc = CAL/f'{nome}.sub'
    loc.write_text(SUB.format(rt=RT, script=script, argomenti=argomenti, nome=nome, quanti=quanti), encoding='utf-8')
    ssh(f'mkdir -p {RT}/log_cal')
    scp_su(loc, f'log_cal/{nome}.sub')
    out = ssh(f'cd {RT} && condor_submit log_cal/{nome}.sub')
    cl = [w for w in out.split() if w.rstrip('.').isdigit()]
    return cl[-1].rstrip('.') if cl else ''


def in_coda(cluster):
    return bool(cluster) and bool(ssh(f'condor_q {cluster} -af ClusterId'))


def carica_stato(caso):
    p = CAL/f'stato_{caso}.json'
    if p.exists():
        return json.loads(p.read_text(encoding='utf-8'))
    return {'caso': caso, 'fase': 'attesa', 'blocco_n': 1, 'rr': 'training/lora_qwen_rr4b_{seme}/passata_2',
            'auc_rr': None, 'rese': {}, 'lista': 'training/fase2/riordino_urgenda_trace.csv'}


def salva_stato(st):
    (CAL/f'stato_{st["caso"]}.json').write_text(json.dumps(st, indent=1, ensure_ascii=False), encoding='utf-8')


def nome_blocco(st, n=None):
    return f"{st['caso']}_blocco{n or st['blocco_n']}"


def esecuzione(st, n=None):
    n = n or st['blocco_n']
    return f"{st['caso']}__trace_blocco{n}_{datetime.date.today():%Y-%m-%d}" if n > 1 else f"{st['caso']}__trace_blocco1_2026-09-27"


def rapporto_blocco(st):
    """I conti del blocco appena finito, dalla piattaforma."""
    _m_carica_blocco = __import__('064_carica_blocco')
    righe_del_caso = _m_carica_blocco.righe_del_caso
    b = nome_blocco(st)
    righe = [x for x in righe_del_caso(st['caso']) if x.get('blocco') == b]
    giud = [x for x in righe if x.get('esito')]
    rip = [x for x in giud if x['esito'] in ('confermata', 'riclassificata')]
    nuove = [x for x in righe if x.get('fase') == 2]
    return {
        'blocco': b, 'righe': len(righe), 'giudicate': len(giud), 'riprese': len(rip),
        'scartate': sum(1 for x in giud if x['esito'] == 'scartata'),
        'da_discutere': sum(1 for x in righe if x.get('da_discutere') and not x.get('esito')),
        'precisione': round(len(rip) / len(giud), 3) if giud else None,
        'riprese_pagine_nuove': sum(1 for x in rip if x.get('fase') == 2), 'pagine_nuove': len(nuove),
        'riprese_pagine_luglio': sum(1 for x in rip if x.get('fase') != 2), 'pagine_luglio': len(righe) - len(nuove),
        'da_fare': sum(1 for x in righe if not x.get('esito') and not x.get('da_discutere')),
    }


def scrivi_rapporto(st, r):
    from google.cloud import firestore
    db = firestore.Client(project='climpact-drp')
    db.collection('corpus_runs').document(st['esecuzione_blocco']).set(
        {'rapporto': {**r, 'aggiornato': firestore.SERVER_TIMESTAMP}}, merge=True)


def tick(caso):
    st = carica_stato(caso)
    st.setdefault('esecuzione_blocco', esecuzione(st))
    f = st['fase']
    if f == 'fermo':
        log('fermo: la regola di stop e\' scattata, aspetto il PI'); return
    if f == 'attesa':
        r = rapporto_blocco(st)
        if r['righe'] == 0:
            log(f"{nome_blocco(st)}: nessuna riga in piattaforma"); return
        scrivi_rapporto(st, r)
        if r['da_fare'] > 0:
            log(f"{nome_blocco(st)}: {r['da_fare']} righe ancora da fare"); return
        log(f"{nome_blocco(st)} finito: {r['riprese']} riprese su {r['giudicate']} giudicate")
        st['rese'][str(st['blocco_n'])] = r['riprese'] / max(1, r['giudicate']) * 100
        ultimi = [st['rese'][k] for k in sorted(st['rese'], key=int)][-2:]
        if len(ultimi) == 2 and all(x < SOGLIA_STOP for x in ultimi):
            st['fase'] = 'fermo'; salva_stato(st)
            scrivi_rapporto(st, {**r, 'stop': True})
            notifica(f"Stop: due blocchi di fila sotto {SOGLIA_STOP} riprese su 100"); return
        subprocess.run([PY, str(QUI/'tools'/'071_cal_dati.py'), '--caso', caso], check=True, timeout=1800)
        scp_su(CAL/f'{caso}_cal_addestramento.jsonl', f'training/cal/{caso}_cal_addestramento.jsonl')
        et = f"b{st['blocco_n']}"
        st['job'] = sottometti(f'addestra_{et}', 'cal_addestra.sh', f"{et} {st['rr']}"); st['etichetta'] = et
        st['fase'] = 'addestra'; salva_stato(st)
        log(f'riaddestramento sottomesso ({st["job"]})'); return
    if f == 'addestra':
        if in_coda(st['job']):
            log('riaddestramento in corso'); return
        if not scp_giu(f"training/cal/esito_{st['etichetta']}.json", CAL/f"esito_{st['etichetta']}.json"):
            st['fase'] = 'errore'; salva_stato(st); notifica('Riaddestramento fallito: guardare su ReCaS'); return
        es = json.loads((CAL/f"esito_{st['etichetta']}.json").read_text())
        st['ultimo_addestramento'] = es; st['rr'] = es['adattatore']; st['auc_rr'] = es['auc_nuovo'] if es['adottato'] else es['auc_in_uso']
        scrivi_rapporto(st, {**rapporto_blocco(st), 'riordinatore': es})
        st['job'] = sottometti(f"riordina_{st['etichetta']}", 'cal_riordina.sh', f"$(Process) {st['rr']} {st['etichetta']}", quanti=8)
        st['fase'] = 'riordina'; salva_stato(st)
        log(f"riordinatore {'adottato' if es['adottato'] else 'NON adottato'} ({es['auc_in_uso']} -> {es['auc_nuovo']}); riordino sottomesso"); return
    if f == 'riordina':
        if in_coda(st['job']):
            log('riordino in corso'); return
        import csv
        righe, campi = [], None
        for i in range(8):
            loc = F2/f"riordino_{caso}_cal_{st['etichetta']}_{i}.csv"
            if not scp_giu(f"training/fase2/riordino_{caso}_cal_{st['etichetta']}_{i}.csv", loc):
                st['fase'] = 'errore'; salva_stato(st); notifica('Riordino fallito: guardare su ReCaS'); return
            r = list(csv.DictReader(open(loc, encoding='utf-8'))); campi = campi or list(r[0].keys()); righe += r
        lista = F2/f"riordino_{caso}_cal_{st['etichetta']}.csv"
        with open(lista, 'w', newline='', encoding='utf-8') as fh:
            w = csv.DictWriter(fh, fieldnames=campi); w.writeheader(); w.writerows(righe)
        st['lista'] = str(lista.relative_to(QUI))
        n = st['blocco_n'] + 1
        _m_carica_blocco = __import__('064_carica_blocco')
        prepara_blocco = _m_carica_blocco.prepara_blocco
        prepara_blocco(caso, lista, N_BLOCCO, nome_blocco(st, n))
        scp_su(F2/f'{nome_blocco(st, n)}_pagine.json', f'training/fase2/{nome_blocco(st, n)}_pagine.json')
        st['job'] = sottometti(f'passaggi_{n}', 'cal_passaggi.sh', nome_blocco(st, n))
        st['fase'] = 'passaggi'; salva_stato(st)
        log(f'blocco {n} scelto; passaggi sottomessi'); return
    if f == 'passaggi':
        if in_coda(st['job']):
            log('passaggi in corso'); return
        n = st['blocco_n'] + 1; b = nome_blocco(st, n)
        if not scp_giu(f'training/fase2/{b}_passaggi.json', F2/f'{b}_passaggi.json'):
            st['fase'] = 'errore'; salva_stato(st); notifica('Passaggi falliti: guardare su ReCaS'); return
        _m_carica_blocco = __import__('064_carica_blocco')
        componi = _m_carica_blocco.componi
        ese = esecuzione(st, n)
        componi(caso, b, ese, True, str(F2/f'{b}_lista.json'), str(QUI/st['lista']))
        st['blocco_n'] = n; st['esecuzione_blocco'] = ese; st['fase'] = 'attesa'; st['job'] = ''
        salva_stato(st)
        scrivi_rapporto(st, rapporto_blocco(st))
        notifica(f'Blocco {n} di {caso} in piattaforma')
        log(f'blocco {n} in piattaforma ({ese})'); return
    log(f'fase {f}: niente da fare (errore da guardare a mano)')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('azione', choices=['tick', 'stato']); ap.add_argument('--caso', default='urgenda')
    a = ap.parse_args()
    if a.azione == 'tick':
        tick(a.caso)
    else:
        print(json.dumps(carica_stato(a.caso), indent=1, ensure_ascii=False))
