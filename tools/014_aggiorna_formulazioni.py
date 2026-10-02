"""LE FORMULAZIONI DI UN CASO, AGGIORNATE DA SOLE — dal file del caso e dai giudizi.

   DECISIONE DEL PI (23/09/2026). Le domande in piu' del primo modello (riprese
   e concorrenti) non si scrivono a mano a ogni giro: le ricava uno script, e
   dopo ogni validazione le rigenera. Il file del caso scritto dal ricercatore
   resta la fonte e non si tocca.

   DA DOVE VENGONO, e ciascuna lo dichiara (caso, atto, pagina):
     riprese      le frasi del caso (canonical, canonical_bis, seeds), e dopo la
                  validazione i passaggi CONFERMATI dal gruppo;
     concorrenti  le formulazioni escluse del file del caso (di provenienza e di
                  polarita'; `verbatim` o `redazionale`), e dopo la validazione i
                  passaggi BOCCIATI dal gruppo, che prendono il posto delle
                  `redazionale` della stessa sonda (e' la politica scritta nei file
                  del caso: «dopo la prima validazione le righe bocciate dal gruppo
                  sostituiscono le redazionali»).
   Solo righe di ADDESTRAMENTO se esiste una divisione del caso; altrimenti tutte le
   righe giudicate, dichiarandolo: in quel caso il caso non va usato come prova.

   USCITA: `training/formulazioni_<caso>.json` e `.html`, e un confronto con la
   versione precedente (quante entrate, quante uscite, per sonda), da mostrare al
   PI prima di usarla.

   Uso:  python3 tools/014_aggiorna_formulazioni.py --caso neubauer [--giudizi giudizi-umani-AAAA-MM-GG.json]
"""
import argparse, collections, html, json, pathlib, re
import yaml

QUI = pathlib.Path(__file__).resolve().parent.parent
T = QUI/'training'


def pulisci(t):
    return re.sub(r'\s+', ' ', t or '').strip()


def dal_file(y):
    sonde, fuori = {}, collections.defaultdict(lambda: {'ripresa': [], 'concorrenti': []})
    for q in y['semantic_queries']:
        sid = q['id']
        sonde[sid] = {'titolo': q.get('titolo', ''), 'testo': pulisci(q.get('testo'))}
        for campo in ('canonical', 'canonical_bis'):
            if q.get(campo):
                fuori[sid]['ripresa'].append({
                    'testo': pulisci(q[campo]), 'tipo': 'vera', 'origine': f'file del caso, {campo}',
                    'provenienza': {'documento': q.get(f'{campo}_documento') or q.get('canonical_documento'),
                                    'pagina': q.get(f'{campo}_pagina'), 'paragrafo': q.get(f'{campo}_paragrafo'),
                                    'atto': q.get('canonical_grado', '')}})
        for sd in q.get('seeds') or []:
            fuori[sid]['ripresa'].append({
                'testo': pulisci(sd['testo']), 'tipo': 'vera', 'origine': 'file del caso, seed',
                'provenienza': {'documento': sd.get('documento'), 'pagina': sd.get('pagina'),
                                'paragrafo': sd.get('paragrafo'), 'atto': ''}})
    for e in y.get('formulazioni_escluse') or []:
        sid = e.get('per')
        if sid not in sonde:
            continue
        fuori[sid]['concorrenti'].append({
            'testo': pulisci(e.get('testo')), 'tipo': 'vera' if e.get('origine') == 'verbatim' else 'redazionale',
            'origine': f"file del caso, esclusa di {e.get('tipo', '?')}", 'id': e.get('id'),
            'provenienza': {'documento': e.get('documento'), 'pagina': e.get('pagina'), 'fonte': e.get('fonte', '')}})
    return sonde, fuori


def dai_giudizi(caso, giudizi, fuori, sonde, divisione):
    righe = [r for r in giudizi if r.get('caso_citato') == caso and r.get('proposto_rete') == 'semantica' and r.get('esito')]
    if divisione is not None:
        righe = [r for r in righe if r['_id'] in divisione]
    titolo_a_id = {v['titolo']: k for k, v in sonde.items()}
    aggiunte = collections.Counter()
    for r in righe:
        sid = titolo_a_id.get((r.get('sonda') or '').split(' [')[0])
        if not sid:
            continue
        testo = pulisci(r.get('validato_citazione_testuale') or r.get('proposto_citazione_testuale'))
        if len(testo) < 60:
            continue
        prov = {'documento': r['document_id'], 'pagina': r.get('validato_pagina') or r.get('proposto_pagina'),
                'caso': r.get('case_name'), 'atto': r.get('tipo_atto'), 'riga': r['_id'],
                'esito_umano': r['esito'], 'nota_umana': r.get('validato_note') or ''}
        if r['esito'] == 'confermata':
            fuori[sid]['ripresa'].append({'testo': testo, 'tipo': 'vera', 'origine': 'passaggio confermato', 'provenienza': prov})
            aggiunte[(sid, 'ripresa')] += 1
        elif r['esito'] == 'scartata':
            fuori[sid]['concorrenti'].append({'testo': testo, 'tipo': 'vera', 'origine': 'passaggio bocciato', 'provenienza': prov})
            aggiunte[(sid, 'concorrenti')] += 1
    # le bocciate vere prendono il posto delle redazionali della stessa sonda
    for sid in fuori:
        if aggiunte[(sid, 'concorrenti')]:
            fuori[sid]['concorrenti'] = [f for f in fuori[sid]['concorrenti'] if f['tipo'] != 'redazionale']
    return len(righe)


def scrivi_html(caso, sonde, fuori, percorso):
    e = html.escape
    out = ['<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
           f'<title>Formulazioni di {e(caso)}</title><style>body{{margin:0;background:#f7f7f5;color:#1c2230;font:16px/1.55 system-ui,sans-serif}}'
           'main{max-width:880px;margin:0 auto;padding:32px 16px}section{background:#fff;border-radius:16px;padding:20px 24px;margin:0 0 20px}'
           '.a{display:block;font-size:13px;color:#5b6475;margin-top:4px}.t{font:600 11px system-ui;text-transform:uppercase;padding:3px 7px;border-radius:999px;background:#e0efe4;color:#2c6a3e;margin-right:6px}'
           '.t.redazionale{background:#f5ebd6;color:#855700}li{margin:0 0 12px}'
           '@media (prefers-color-scheme:dark){body{background:#15181e;color:#e6e8ec}section{background:#1e222a}.a{color:#a0a8b8}}</style></head><body><main>',
           f'<h1>Formulazioni di {e(caso)}</h1>']
    for sid, s in sonde.items():
        out.append(f'<section><h2>{e(s["titolo"])}</h2><p>{e(s["testo"])}</p>')
        for parte in ('ripresa', 'concorrenti'):
            out.append(f'<h3>{"Riprese" if parte == "ripresa" else "Concorrenti"}</h3><ol>')
            for f in fuori[sid][parte]:
                p = f['provenienza']
                dove = ', '.join(str(x) for x in (p.get('caso'), p.get('atto'), p.get('documento'),
                                                   f"p. {p['pagina']}" if p.get('pagina') else None,
                                                   p.get('paragrafo'), p.get('fonte')) if x)
                out.append(f'<li><span class="t {f["tipo"]}">{f["tipo"]}</span>{e(f["testo"])}'
                           f'<span class="a">{e(f["origine"])}: {e(dove)}</span></li>')
            out.append('</ol>')
        out.append('</section>')
    out.append('</main></body></html>')
    percorso.write_text(''.join(out), encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--caso', required=True)
    ap.add_argument('--giudizi', default='', help='esportazione dei giudizi (040_salva_giudizi.py); senza, solo il file del caso')
    ap.add_argument('--divisione', default='', help='jsonl delle righe di addestramento del caso, se esiste')
    a = ap.parse_args()
    y = yaml.safe_load((QUI/'cited-cases'/f'{a.caso}.yaml').read_text(encoding='utf-8'))
    sonde, fuori = dal_file(y)
    n_giud = 0
    if a.giudizi:
        giudizi = json.loads((QUI/a.giudizi).read_text(encoding='utf-8'))
        div = None
        if a.divisione:
            div = {json.loads(l)['id'] for l in open(QUI/a.divisione, encoding='utf-8') if l.strip()}
        n_giud = dai_giudizi(a.caso, giudizi, fuori, sonde, div)
    uscita = T/f'formulazioni_{a.caso}.json'
    prima = json.loads(uscita.read_text(encoding='utf-8')) if uscita.exists() else None
    dati = {'caso': a.caso, 'versione_file_caso': y.get('versione_file'), 'righe_giudicate_usate': n_giud,
            'solo_addestramento': bool(a.divisione), 'sonde': sonde, 'formulazioni': fuori}
    uscita.write_text(json.dumps(dati, ensure_ascii=False, indent=1), encoding='utf-8')
    scrivi_html(a.caso, sonde, fuori, uscita.with_suffix('.html'))
    print(f'{a.caso}: {len(sonde)} sonde, righe giudicate usate {n_giud}')
    for sid in sonde:
        r, c = fuori[sid]['ripresa'], fuori[sid]['concorrenti']
        riga = f'  {sid:45s} riprese {len(r):3d}  concorrenti {len(c):3d} (redazionali {sum(f["tipo"] == "redazionale" for f in c)})'
        if prima:
            pr = prima['formulazioni'].get(sid, {'ripresa': [], 'concorrenti': []})
            vecchie = {f['testo'] for f in pr['ripresa'] + pr['concorrenti']}
            nuove = {f['testo'] for f in r + c}
            riga += f'  | rispetto a prima: +{len(nuove - vecchie)} -{len(vecchie - nuove)}'
        print(riga)
    print('scritto', uscita, 'e', uscita.with_suffix('.html'))


if __name__ == '__main__':
    main()
