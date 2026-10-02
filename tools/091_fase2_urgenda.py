"""FASE 2 SU URGENDA: la catena nuova sul corpus intero, solo su FILE (§63.15 del documento unico, diario §31.5).

   Tre passi dopo `078_cerca_pagine.py` (retriever Perplexity con l'adattatore scelto, prime 500 pagine per sonda):
     riordina    GPU. Il riordinatore Qwen3-Reranker-4B con il nostro adattatore (tre semi, passata 2, media),
                 istruzione «ripresa», 2.560 token: lo stesso percorso del maestro di `041_distilla.py voti`.
                 -> training/fase2/riordino_urgenda.csv
     prepara_ds  CPU. Le prime N pagine per sonda secondo il riordinatore; una pagina che sta fra le prime N di
                 piu' sonde si legge UNA volta, con la sonda per cui il riordinatore le da' il voto piu' alto
                 (le altre sonde restano scritte nella colonna delle sonde). Righe nello stesso formato della
                 prova del lettore: `finestra` = la pagina, `finestra_larga` = pagina prima, pagina, pagina dopo
                 (pagine dell'indice, spazi compressi, come nelle 133 righe di prova).
                 -> training/urgenda_decisione_fase2_corrette_larghe.jsonl (la legge `086_deepseek_api.py --parti fase2`)
     combina     Mac. Riordinatore e DeepSeek per ranghi medi (come `079_combina_lettori.py`), confronto con le righe
                 di Firestore (copia locale in SOLA LETTURA), i quattro numeri per il PI.
                 -> training/fase2_urgenda_candidati.csv, training/fase2/esiti_fase2_urgenda.json

   NON scrive niente sulla piattaforma. Sono proposte della macchina: i giudizi umani restano la verita' di
   riferimento, e la fase 1 (la catena di luglio) non si butta.
"""
import argparse, collections, csv, gzip, json, pathlib, re, sys, time
import numpy as np
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
T = QUI/'training'; F2 = T/'fase2'; F2.mkdir(parents=True, exist_ok=True)
PAGINE = QUI/'index'/'pagine'/'pagine.jsonl.gz'


def sonde(caso='urgenda'):
    import yaml
    conf = yaml.safe_load(open(QUI/'cited-cases'/f'{caso}.yaml', encoding='utf-8'))
    S = {q['id']: ' '.join(q['testo'].split()) for q in conf.get('semantic_queries') or []}
    S.update({q['id'] + '__alt': ' '.join(q['probe_alternativa'].split())
              for q in conf.get('semantic_queries') or [] if q.get('probe_alternativa')})
    return S


def testi_pagine(serve, vicine=False):
    """id pagina -> testo; con vicine=True anche la pagina prima e quella dopo dello stesso documento."""
    out = {}; prec = None; attesa = None
    with gzip.open(PAGINE, 'rt', encoding='utf-8') as f:
        for l in f:
            x = json.loads(l)
            if attesa is not None:
                if x['doc'] == out[attesa]['doc']:
                    out[attesa]['dopo'] = x['testo']
                attesa = None
            if x['id'] in serve:
                out[x['id']] = {'doc': x['doc'], 'testo': x['testo'],
                                'prima': prec['testo'] if (vicine and prec and prec['doc'] == x['doc']) else ''}
                if vicine:
                    attesa = x['id']
            prec = x
    return out


def riordina(entrata, uscita, pezzo=0, pezzi=1, rr='training/lora_qwen_rr4b_{seme}/passata_2'):
    import torch
    from peft import PeftModel
    _m_prova_riordinatori = __import__('027_prova_riordinatori')
    QwenRiordinatore = _m_prova_riordinatori.QwenRiordinatore
    ISTR = _m_prova_riordinatori.ISTR
    S = sonde()
    righe = list(csv.DictReader(open(entrata, encoding='utf-8')))
    coppie = sorted({(r['sonda'], r['pagina_id']) for r in righe})
    # IN PARALLELO SU PIU' GPU: ogni lavoro prende una coppia ogni `pezzi` (26/09/2026)
    coppie = [c for i, c in enumerate(coppie) if i % pezzi == pezzo]
    testo = testi_pagine({p for _, p in coppie})
    # UNA PAGINA CHE NON STA NELL'INDICE non si legge (pagine sotto i 200 caratteri, 26/09/2026): si dice quante,
    # invece di fermare tutto su un KeyError.
    mancano = sorted({p for _, p in coppie if p not in testo})
    if mancano:
        print(f'pagine fuori dall\'indice: {len(mancano)} (per esempio {mancano[:3]})', flush=True)
    coppie = [c for c in coppie if c[1] in testo]
    print(f'candidati {len(righe)}, coppie sonda-pagina {len(coppie)}, pagine {len(testo)}', flush=True)
    punti = []
    for seme in (1, 2, 3):
        t0 = time.time(); q = QwenRiordinatore('Qwen/Qwen3-Reranker-4B')
        # l'adattatore del riordinatore in uso (apprendimento attivo: cambia quando uno nuovo lo batte)
        q.m = PeftModel.from_pretrained(q.m, str(QUI/rr.replace('{seme}', str(seme))))
        punti.append(q.punteggi([(S[s], testo[p]['testo']) for s, p in coppie], ISTR['ripresa'], 2560)); q.libera()
        print(f'  riordinatore seme {seme}: {time.time()-t0:.0f}s', flush=True)
    P = np.mean(punti, 0); base = {(r['sonda'], r['pagina_id']): r for r in righe}
    with open(uscita, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['sonda', 'pagina_id', 'document_id', 'case_id', 'pagina', 'posto_retriever', 'punteggio_retriever',
                    'riordino_seme1', 'riordino_seme2', 'riordino_seme3', 'riordino'])
        for k, (s, p) in enumerate(coppie):
            b = base[(s, p)]
            w.writerow([s, p, b['document_id'], b['case_id'], b['pagina'], b['posto'], b['punteggio'],
                        *[round(float(x[k]), 5) for x in punti], round(float(P[k]), 5)])
    print(f'-> {uscita}; sopra 0,5: {int((P > .5).sum())} su {len(P)}', flush=True)


def prepara_ds(entrata, n, parte='fase2', gia_lette=''):
    S = sonde()
    righe = list(csv.DictReader(open(entrata, encoding='utf-8')))
    per = collections.defaultdict(list)
    for r in righe:
        per[r['sonda']].append(r)
    scelte = {}
    for s, v in per.items():
        for r in sorted(v, key=lambda r: -float(r['riordino']))[:n]:
            p = r['pagina_id']
            if p not in scelte or float(r['riordino']) > float(scelte[p]['riordino']):
                scelte[p] = r
    lette = set()
    for fl in [x for x in gia_lette.split(',') if x]:
        if pathlib.Path(fl).exists():
            lette |= {json.loads(l)['id'].split('|', 1)[1] for l in open(fl, encoding='utf-8')}
    prima = len(scelte); scelte = {p: r for p, r in scelte.items() if p not in lette}
    print(f'pagine scelte {prima}, gia\' lette da DeepSeek {prima - len(scelte)}, da leggere {len(scelte)}', flush=True)
    testo = testi_pagine(set(scelte), vicine=True)
    spazi = lambda t: re.sub(r'\s+', ' ', t).strip()
    fuori = T/f'urgenda_decisione_{parte}_corrette_larghe.jsonl'
    with open(fuori, 'w', encoding='utf-8') as f:
        for p, r in sorted(scelte.items(), key=lambda t: -float(t[1]['riordino'])):
            x = testo[p]
            f.write(json.dumps({'id': f"{r['sonda']}|{p}", 'etichetta': 0, 'sonda_id': r['sonda'], 'case_id': r['case_id'],
                                'document_id': r['document_id'], 'pagina': r['pagina'], 'sonda_testo': S[r['sonda']],
                                'finestra': x['testo'],
                                'finestra_larga': spazi(' '.join(t for t in (x['prima'], x['testo'], x.get('dopo', '')) if t))},
                               ensure_ascii=False) + '\n')
    print(f'prime {n} per sonda: {sum(min(n, len(v)) for v in per.values())} coppie, {len(scelte)} pagine distinte -> {fuori}', flush=True)


# ── combina (Mac) ─────────────────────────────────────────────────────────

def combina(riordino, ds_file, righe_fs, n_letture, etichetta=''):
    from scipy.stats import rankdata
    S = sonde()
    rr = list(csv.DictReader(open(riordino, encoding='utf-8')))
    # per pagina: tutte le sonde in cui compare, e la migliore secondo il riordinatore
    pag = {}
    for r in rr:
        p = r['pagina_id']; v = float(r['riordino'])
        d = pag.setdefault(p, {'pagina_id': p, 'document_id': r['document_id'], 'case_id': r['case_id'], 'pagina': r['pagina'],
                               'sonde': {}, 'posto_retriever_min': 10**9})
        d['sonde'][r['sonda']] = v; d['posto_retriever_min'] = min(d['posto_retriever_min'], int(r['posto_retriever']))
    for d in pag.values():
        d['sonda_migliore'], d['riordino'] = max(d['sonde'].items(), key=lambda t: t[1])
    ds = {}
    for l in (l for fl in ds_file.split(',') for l in open(fl, encoding='utf-8')):
        x = json.loads(l); s, p = x['id'].split('|', 1)
        esiti = [g.get('esito') for g in x['letture']]
        ds[p] = {'sonda_letta': s, 'voti_ripresa': x['voti_ripresa'], 'letture': len(esiti),
                 'illeggibili': sum(e not in ('RIPRESA', 'ALTRA_FONTE', 'NON_AFFERMA') for e in esiti),
                 'esiti': esiti, 'chi_parla': [g.get('chi_parla') for g in x['letture']],
                 'cita_urgenda': [g.get('cita_urgenda') for g in x['letture']],
                 'motivo': next((g.get('motivo') for g in x['letture'] if g.get('esito') == 'RIPRESA'), x['letture'][0].get('motivo') if x['letture'] else '')}
    # rango combinato: sulle pagine lette da DeepSeek, media dei ranghi (ranghi medi ai pareggi) del
    # riordinatore e della frazione di letture «RIPRESA»; nessun peso imparato (§63.3-bis).
    lette = [p for p in pag if p in ds]
    R = np.array([pag[p]['riordino'] for p in lette]); D = np.array([ds[p]['voti_ripresa'] / max(ds[p]['letture'], 1) for p in lette])
    rg = lambda s: (rankdata(s) - 1) / (len(s) - 1)
    C = (rg(R) + rg(D)) / 2
    for p, c in zip(lette, C):
        pag[p]['combinato'] = float(c)
    ordine = sorted(lette, key=lambda p: (-pag[p]['combinato'], -pag[p]['riordino'])) + \
        sorted([p for p in pag if p not in ds], key=lambda p: -pag[p]['riordino'])
    # ── Firestore (copia locale, sola lettura): che cosa e' gia' stato proposto e giudicato
    fs = json.load(open(righe_fs, encoding='utf-8'))
    pagina_riga = lambda x: str(x.get('validato_pagina') or x.get('proposto_pagina') or '').strip()
    per_pag = collections.defaultdict(list)
    for x in fs:
        per_pag[f"{x['document_id']}#p{pagina_riga(x)}"].append(x)
    giudicata = lambda x: bool(x.get('esito'))
    sem = lambda x: x.get('proposto_rete') in ('semantica', 'entrambe')
    fuori = T/f'fase2_urgenda_candidati{etichetta}.csv'
    with open(fuori, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['posto', 'pagina_id', 'document_id', 'case_id', 'pagina', 'sonde', 'sonda_migliore', 'riordino',
                    'deepseek_sonda_letta', 'deepseek_voti_ripresa', 'deepseek_letture', 'deepseek_chi_parla', 'deepseek_motivo',
                    'rango_combinato', 'giudicata_da_persone', 'esiti_umani', 'esiti_umani_semantici', 'proposta_fase1',
                    'righe_lessicali_sulla_pagina', 'nuova'])
        for k, p in enumerate(ordine, 1):
            d = pag[p]; g = ds.get(p); fr = per_pag.get(p, [])
            es = collections.Counter(x['esito'] for x in fr if giudicata(x))
            ess = collections.Counter(x['esito'] for x in fr if giudicata(x) and sem(x))
            fase1 = any(sem(x) for x in fr)
            d.update(posto=k, giudicata=bool(es), fase1=fase1, conferme_sem=ess.get('confermata', 0), nuova=not fr)
            w.writerow([k, p, d['document_id'], d['case_id'], d['pagina'],
                        ';'.join(f'{s}:{v:.3f}' for s, v in sorted(d['sonde'].items(), key=lambda t: -t[1])),
                        d['sonda_migliore'], round(d['riordino'], 4),
                        g['sonda_letta'] if g else '', g['voti_ripresa'] if g else '', g['letture'] if g else '',
                        ';'.join(sorted({str(c) for c in g['chi_parla'] if c})) if g else '', (g['motivo'] or '') if g else '',
                        round(d['combinato'], 4) if 'combinato' in d else '',
                        'si' if es else 'no', ';'.join(f'{e}:{c}' for e, c in es.items()), ';'.join(f'{e}:{c}' for e, c in ess.items()),
                        'si' if fase1 else 'no', sum(1 for x in fr if x.get('proposto_rete') == 'lessicale'),
                        'si' if not fr else 'no'])
    # ── i quattro numeri
    conf_pag = {f"{x['document_id']}#p{pagina_riga(x)}" for x in fs if sem(x) and x.get('esito') == 'confermata'}
    conf_sonda = collections.defaultdict(set)
    for x in fs:
        if sem(x) and x.get('esito') == 'confermata':
            conf_sonda[f"{x['document_id']}#p{pagina_riga(x)}"].add(x.get('sonda'))
    escluse = {x['document_id'] for x in fs if x['case_id'].startswith('urgenda-foundation')}
    posto = {p: pag[p]['posto'] for p in ordine}
    trovate = {k: sorted(p for p in conf_pag if posto.get(p, 10**9) <= k) for k in (100, 200, 500, len(ordine))}
    # anche per frammento (righe) e non solo per pagina, e le righe di prova a parte
    prova = [json.loads(l) for l in open(T/'urgenda_decisione_prova_corrette_larghe.jsonl', encoding='utf-8')]
    doc_prova = {x['document_id'] for x in prova}
    esiti = {
        'data': time.strftime('%Y-%m-%d'),
        'pagine_candidate': len(ordine),
        'coppie_sonda_pagina': len(rr),
        'pagine_lette_da_deepseek': len(lette),
        'letture_per_pagina': n_letture,
        'pagine_con_righe_gia_giudicate': sum(pag[p]['giudicata'] for p in ordine),
        'pagine_proposte_in_fase1': sum(pag[p]['fase1'] for p in ordine),
        'pagine_nuove_mai_proposte_in_fase1': sum(not pag[p]['fase1'] for p in ordine),
        'pagine_senza_nessuna_riga_urgenda': sum(pag[p]['nuova'] for p in ordine),
        'pagine_confermate_semantiche_totali': len(conf_pag),
        'pagine_confermate_fuori_dal_corpus_indice': sorted(p for p in conf_pag if p.split('#')[0] in escluse),
        'confermate_nei_primi': {str(k): len(v) for k, v in trovate.items()},
        'confermate_nei_primi_delle_pagine_lette': {str(k): sum(1 for p in conf_pag if pag.get(p, {}).get('posto', 10**9) <= k and p in ds) for k in (100, 200, 500)},
        'confermate_mai_candidate': sorted(p for p in conf_pag if p not in posto),
        'posti_delle_confermate': {p: posto.get(p) for p in sorted(conf_pag, key=lambda p: posto.get(p, 10**9))},
        'confermate_nei_documenti_di_prova': {p: posto.get(p) for p in conf_pag if p.split('#')[0] in doc_prova},
        'nuove_nei_primi': {str(k): sum(1 for p in ordine[:k] if not pag[p]['fase1']) for k in (100, 200, 500)},
        'deepseek_almeno_meta_ripresa': sum(1 for p in lette if ds[p]['voti_ripresa'] * 2 >= ds[p]['letture'] and ds[p]['letture']),
        'deepseek_letture_illeggibili': sum(ds[p]['illeggibili'] for p in lette),
    }
    (F2/f'esiti_fase2_urgenda{etichetta}.json').write_text(json.dumps(esiti, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in esiti.items() if k not in ('posti_delle_confermate',)}, ensure_ascii=False, indent=1))
    print(f'-> {fuori}')


def solo_riordino(riordino, righe_fs):
    """Senza DeepSeek: a che posto il solo riordinatore mette le pagine confermate e quelle scartate dalle persone
    (usata per la prova del k di 5.000, §63.15)."""
    best = {}
    for r in csv.DictReader(open(riordino, encoding='utf-8')):
        best[r['pagina_id']] = max(best.get(r['pagina_id'], 0.0), float(r['riordino']))
    posto = {p: k for k, p in enumerate(sorted(best, key=lambda p: -best[p]), 1)}
    fs = json.load(open(righe_fs, encoding='utf-8'))
    pr = lambda x: str(x.get('validato_pagina') or x.get('proposto_pagina') or '').strip()
    sem = lambda x: x.get('proposto_rete') in ('semantica', 'entrambe')
    conf = {f"{x['document_id']}#p{pr(x)}" for x in fs if sem(x) and x.get('esito') == 'confermata'}
    scar = {f"{x['document_id']}#p{pr(x)}" for x in fs if sem(x) and x.get('esito') == 'scartata'} - conf
    prova = {json.loads(l)['document_id'] for l in open(T/'urgenda_decisione_prova_corrette_larghe.jsonl', encoding='utf-8')}
    fase1 = {f"{x['document_id']}#p{pr(x)}" for x in fs if sem(x)}
    soglie = (100, 200, 500, 1000, len(posto))
    out = {'file': str(riordino), 'pagine': len(posto),
           'confermate': {str(k): sum(1 for p in conf if posto.get(p, 10**9) <= k) for k in soglie},
           'confermate_prova': {str(k): sum(1 for p in conf if p.split('#')[0] in prova and posto.get(p, 10**9) <= k) for k in soglie},
           'scartate': {str(k): sum(1 for p in scar if posto.get(p, 10**9) <= k) for k in soglie},
           'nuove_fase1': {str(k): sum(1 for p, n in posto.items() if n <= k and p not in fase1) for k in soglie}}
    print(json.dumps(out, indent=1))
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('fase', choices=['riordina', 'prepara_ds', 'combina', 'solo_riordino'])
    ap.add_argument('--candidati', default=str(T/'candidati_pagine_urgenda_pplx4b.csv'))
    ap.add_argument('--riordino', default=str(F2/'riordino_urgenda.csv'))
    ap.add_argument('--n', type=int, default=100, help='pagine per sonda da far leggere a DeepSeek (decisione di costo)')
    ap.add_argument('--deepseek', default=str(T/'deepseek_fase2_v4_fase2.jsonl'))
    ap.add_argument('--righe-firestore', default=str(F2/'urgenda_corpus_rows_2026-09-26.json'))
    ap.add_argument('--letture', type=int, default=5)
    ap.add_argument('--etichetta', default='', help='suffisso dei file di uscita di combina')
    ap.add_argument('--parte', default='fase2', help='nome delle righe per 086_deepseek_api.py --parti')
    ap.add_argument('--gia-lette', default='', help='file .jsonl di DeepSeek gia\' fatti: quelle pagine non si rileggono')
    ap.add_argument('--pezzo', type=int, default=0); ap.add_argument('--pezzi', type=int, default=1)
    ap.add_argument('--rr', default='training/lora_qwen_rr4b_{seme}/passata_2', help='adattatore del riordinatore, con {seme}')
    a = ap.parse_args()
    if a.fase == 'riordina':
        riordina(a.candidati, a.riordino, a.pezzo, a.pezzi, a.rr)
    elif a.fase == 'prepara_ds':
        prepara_ds(a.riordino, a.n, a.parte, a.gia_lette)
    elif a.fase == 'solo_riordino':
        json.dump(solo_riordino(a.riordino, a.righe_firestore), open(F2/f'solo_riordino{a.etichetta}.json', 'w'), indent=1)
    else:
        combina(a.riordino, a.deepseek, a.righe_firestore, a.letture, a.etichetta)
