"""REVISIONE DELLE 20 RIGHE «CITAZIONE ALTROVE» — una alla volta, con il PI.

   PERCHE'. Il 22/09/2026 queste righe semantiche, segnate `riclassificata`
   dai validatori con note come «Urgenda e' citata ma in altri punti», sono
   state contate come «no» e poi etichettate `citazione_altrove`. Il 23/09 il
   PI ha trovato che una di esse (Neubauer, p. 43) riprende lo stesso
   argomento che un altro validatore aveva confermato nella stessa ordinanza.
   Un caso e' una classe: si rivedono tutte e venti.

   USO
     python3 tools/rivedi_altrove.py mostra N
     python3 tools/rivedi_altrove.py rispondi N si|no|altra:<sonda> [nota]
     python3 tools/rivedi_altrove.py spoglio

   Le risposte si scrivono in `riclassificate-rivedute-2026-09-23.json`; la
   banca dati non si tocca da qui.
"""
import json, pathlib, re, sys, textwrap

QUI = pathlib.Path(__file__).resolve().parent.parent
USCITA = QUI/'riclassificate-rivedute-2026-09-23.json'


def dati():
    b = json.loads((QUI/'riclassificate-citazione-altrove-2026-09-22.json').read_text(encoding='utf-8'))
    g = {r['_id']: r for r in json.loads((QUI/'giudizi-umani-2026-09-22.json').read_text(encoding='utf-8'))}
    pag = {}
    for p in ('addestramento', 'prova'):
        for l in open(QUI/'training'/f'urgenda_decisione_{p}_corrette.jsonl', encoding='utf-8'):
            x = json.loads(l)
            pag[x['id']] = (p, x.get('finestra') or '', x.get('sonda_testo') or '')
    return list(b.items()), g, pag


def norm(s):
    return re.sub(r'\s+', ' ', re.sub(r'-\s*\n\s*', '', s or '')).strip()


def mostra(n):
    righe, g, pag = dati()
    k, v = righe[n-1]
    r = g[k]
    parte, pagina, sonda = pag.get(k, ('?', '', ''))
    cit = next((h['campi'].get('validato_citazione_testuale') for h in r.get('_storia') or []
                if h.get('azione') == 'valida' and h['campi'].get('validato_citazione_testuale')), r.get('validato_citazione_testuale'))
    cit, testo = norm(cit), norm(pagina).replace('⟦CASO_CITATO⟧', 'Urgenda')
    i = testo.find(cit[:60]) if cit else -1
    contesto = testo[max(0, i-900): i+len(cit)+900] if i >= 0 else testo[:2200]
    print(f'RIGA {n} di {len(righe)}   ({parte})')
    print(f'{r["case_name"]}, {r.get("tipo_atto")}, p. {r.get("validato_pagina")}  [{r.get("giurisdizioni")}]')
    print(f'\nSONDA: {v["sonda"]}\n{textwrap.fill(norm(sonda), 100)}')
    print(f'\nNOTA DEL VALIDATORE: {v.get("validato_note") or "(nessuna)"}')
    print(f'\nPASSAGGIO SEGNALATO:\n{textwrap.fill(cit, 100)}')
    print(f'\nCONTESTO SULLA PAGINA:\n{textwrap.fill(contesto, 100)}')


def rispondi(n, esito, nota):
    righe, _, _ = dati()
    k, v = righe[n-1]
    d = json.loads(USCITA.read_text(encoding='utf-8')) if USCITA.exists() else {}
    d[k] = {'n': n, 'esito_pi': esito, 'nota_pi': nota, 'sonda': v['sonda'], 'nota_validatore': v.get('validato_note')}
    USCITA.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'registrata riga {n}: {esito}')


def spoglio():
    d = json.loads(USCITA.read_text(encoding='utf-8')) if USCITA.exists() else {}
    import collections
    print(len(d), 'risposte:', collections.Counter(x['esito_pi'].split(':')[0] for x in d.values()))


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'mostra':
        mostra(int(a[1]))
    elif a[0] == 'rispondi':
        rispondi(int(a[1]), a[2], ' '.join(a[3:]))
    else:
        spoglio()
