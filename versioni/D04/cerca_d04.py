#!/usr/bin/env python3
"""D04, PASSO 4: LA RICERCA PER NOME S05 SOLO SUI 46 DOCUMENTI NUOVI DI D04, A SECCO (03/10/2026).

   Stessa ricerca e stessa regola delle righe nuove del caricamento S05, senza riscriverle:
     - la ricerca e' `cerca_s05.main` (rete lessicale, filtro della data, deduplica, corpo o nota dal PDF), con i file
       dei casi vivi `cited-cases/<caso>.yaml` (= i file S05, controllato) e le forme di S03 come ancora; l'unica
       differenza e' che la rete lessicale legge solo i Markdown scritti da `build_markdown_d04.py`
       (training/d04/markdown_d04_registro.json);
     - la deduplica vale anche contro il corpus di prima: una riga il cui testo (le stesse 400 lettere della chiave di
       `cerca_s05`) e' gia' nel CSV S05 del caso e' una copia, e va negli scarti come nella ricerca intera;
     - le righe nuove con la regola di `unisci_s05.py`: gruppi di corrispondenze (`cerca_s05.fondi`), coperti da una riga
       gia' in piattaforma dello stesso documento nei 200 caratteri dal suo inizio (anche le «esclusa»); quelle non
       coperte prendono il codice dopo il piu' alto del caso, la persona a turno fra chi ha righe del caso da fare, una
       su cinque alla cieca; provenienza `corpus: D04`, `estrazione: S05`.
   Firestore si LEGGE soltanto (righe esistenti, codici, persone). Niente si scrive in banca dati: il caricamento e'
   un passo a parte, dopo il si' del PI.

   Uscite in training/d04/: nomi_<caso>_D04.csv (+ .SCARTI.csv, dove dal 04/10/2026 vanno anche le copie del corpus di
   prima, `scrivi_copie_negli_scarti`), <caso>_righe_nuove.jsonl, <caso>_confronto.json.

   Uso:  .venv/bin/python tools/cerca_d04.py [--caso urgenda]
"""
import argparse, collections, csv, json, random, re, sys
from pathlib import Path

QUI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools')); sys.path.insert(0, str(QUI))
import cerca as S03                      # noqa: E402
import cerca_s05 as S05                  # noqa: E402
from pubblica import documento, id_riga  # noqa: E402
from posizione_dopo_ocr import traduci   # noqa: E402
from unisci_s05 import PREFISSI          # noqa: E402

D04 = QUI/'training'/'d04'
DATA = '2026-10-03'
CSV_S05 = '2026-10-02'


def markdown_d04():
    reg = json.load(open(D04/'markdown_d04_registro.json', encoding='utf-8'))
    return [d['markdown'] for d in reg['documenti'] if d.get('esito') == 'scritto']


def chiave(t):
    return re.sub(r'\s+', ' ', t).strip().lower()[:400]      # la chiave della deduplica di cerca_s05.main


def cerca(caso, file):
    """cerca_s05.main con la rete lessicale limitata ai Markdown di D04."""
    vivo = QUI/'cited-cases'/f'{caso}.yaml'
    assert vivo.read_bytes() == (QUI/'cited-cases'/f'{caso}-S05.yaml').read_bytes(), f'{vivo} non e\' il file S05'
    originale = S05.rete_lessicale
    S05.rete_lessicale = lambda *a, **k: originale(*a, **{**k, 'file': file})
    uscita = D04/f'nomi_{caso}_D04.csv'
    argv = sys.argv
    sys.argv = ['cerca_s05.py', '--caso', str(vivo), '--solo-lessicale', '--uscita', str(uscita.relative_to(QUI))]
    try:
        S05.main()
    except IndexError:
        print('   nessuna citazione nei Markdown di D04')      # cerca_s05.main non sa scrivere un CSV vuoto
    finally:
        S05.rete_lessicale, sys.argv = originale, argv
    return uscita


MOTIVO_COPIA_PRIMA = 'copia di un frammento del corpus di prima (CSV S05 del caso)'


def scrivi_copie_negli_scarti(out, copie):
    """LE COPIE TOLTE VANNO NEGLI SCARTI, come promette la testa del file (S07, 04/10/2026: fino a oggi si contavano e
    basta, e una copia tolta non lasciava traccia). In coda a <uscita>.SCARTI.csv, con lo stesso intestazione se il file
    c'e' gia' (lo scrive cerca_s05.main), col motivo `MOTIVO_COPIA_PRIMA`. Ritorna quante ne ha scritte."""
    if not copie:
        return 0
    fs = out.with_name(out.stem + '.SCARTI.csv')
    if fs.exists() and fs.stat().st_size:
        with open(fs, encoding='utf-8') as h:
            campi = next(csv.reader(h))
        modo = 'a'
    else:
        campi = list(dict.fromkeys([k for r in copie for k in r] + ['motivo_scarto']))
        modo = 'w'
    with open(fs, modo, newline='', encoding='utf-8') as h:
        w = csv.DictWriter(h, fieldnames=campi, extrasaction='ignore')
        if modo == 'w':
            w.writeheader()
        for r in copie:
            w.writerow({**{k: r.get(k, '') for k in campi}, 'motivo_scarto': MOTIVO_COPIA_PRIMA})
    print(f'   copie del corpus di prima negli scarti: {len(copie)} -> {fs.name}')
    return len(copie)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--caso', default=''); a = ap.parse_args()
    from google.cloud import firestore
    db = firestore.Client(project='climpact-drp')       # solo letture
    file = markdown_d04()
    print(f'{len(file)} Markdown di D04')
    riepilogo = {}
    for caso in ([a.caso] if a.caso else list(PREFISSI)):
        pre = PREFISSI[caso]
        out = cerca(caso, file)
        righe_csv = list(csv.DictReader(open(out, encoding='utf-8'))) if out.exists() else []
        # deduplica contro il corpus di prima
        prima = {chiave(r['citazione_testuale']) for r in csv.DictReader(open(QUI/'index'/f'nomi_{caso}_{CSV_S05}-S05.csv', encoding='utf-8'))}
        copie = [r for r in righe_csv if chiave(r['citazione_testuale']) in prima]
        righe_csv = [r for r in righe_csv if chiave(r['citazione_testuale']) not in prima]
        scrivi_copie_negli_scarti(out, copie)
        conf5 = S05.leggi_caso(QUI/'cited-cases'/f'{caso}.yaml')
        conf3 = S03.leggi_caso(S05.file_ancora(QUI/'cited-cases'/f'{caso}-S05.yaml'))
        patt5, ancora = S05.regex_caso(conf5), S05.regex_ancora(conf3['forme'])
        tutte = [(d.reference, d.to_dict()) for d in db.collection('corpus_rows')
                 .where(filter=firestore.FieldFilter('caso_citato', '==', caso)).stream()]
        nominali = [(ref, r) for ref, r in tutte if r.get('proposto_rete') in ('lessicale', 'entrambe')]
        escluse = [(ref, r) for ref, r in tutte if r.get('proposto_rete') == 'esclusa']
        per_doc = collections.defaultdict(list)
        for ref, r in nominali + escluse:
            per_doc[r['document_id']].append((ref, r))
        csv_doc = collections.defaultdict(dict)
        for r in righe_csv:
            csv_doc[r['document_id']][int(r['char_start'])] = r
        da_aggiungere, gia_coperte = [], 0
        for doc, per_inizio in sorted(csv_doc.items()):
            md = QUI/next(iter(per_inizio.values()))['file']
            testo = md.read_text(encoding='utf-8', errors='replace')
            meta, inizio = S03.front_matter(testo)
            ms = S05.corrispondenze(testo, inizio, patt5, ancora)
            starts = [f[0].start() for f in S05.fondi(testo, ms)]
            gruppo_di, g = {}, -1
            for m in ms:
                if m.start() in set(starts):
                    g += 1
                gruppo_di[m.start()] = g
            coperti = set()
            for ref, r in per_doc.get(doc, []):          # righe gia' in piattaforma per lo stesso documento (attese: nessuna)
                cs = int(r.get('char_start') or -1)
                if cs >= 0:
                    cs, _ = traduci(r.get('file') or str(md.relative_to(QUI)), cs, ancora, bool((r.get('provenienza') or {}).get('ocr')))
                coperti |= {gruppo_di[m.start()] for m in ms if cs <= m.start() < cs + S03.FUSIONE}
            for gg, g0 in enumerate(starts):
                riga = per_inizio.get(g0)
                if riga is None:
                    continue
                if gg in coperti:
                    gia_coperte += 1; continue
                da_aggiungere.append(riga)
        gia = [int(m.group(1)) for _, r in tutte for m in [re.fullmatch(rf'{pre}-(\d+)', str(r.get('codice') or ''))] if m]
        n = max(gia, default=0)
        chi = sorted({r['assegnato_a'] for _, r in nominali if r.get('assegnato_a') and not r.get('esito')})
        rnd = random.Random(f'{caso}-{DATA}-D04')
        esistenti = {ref.id for ref, _ in tutte}
        uscita, id_doppi = [], []
        for k, r in enumerate(sorted(da_aggiungere, key=lambda x: (x['document_id'], int(x['char_start'])))):
            d = documento(r, caso)
            rid = id_riga(caso, d['document_id'], d['char_start'])
            if rid in esistenti:
                id_doppi.append(rid); continue
            n += 1
            d.update({'corroborazione': 'nome_presente', 'ordine': random.Random(rid).random(), 'codice': f'{pre}-{n:04d}',
                      'assegnato_a': chi[k % len(chi)] if chi else None, 'campione_cieco': rnd.random() < 0.20, 'incerta': False,
                      'provenienza': {'corpus': 'D04', 'estrazione': 'S05', 'tipo': '', 'principi': {}, 'composizione': '', 'seguito': ''},
                      'motivo_aggiunta': 'documento senza Markdown fino al 03/10/2026 (D04: riscaricato o non PDF)'})
            uscita.append({'id': rid, 'codice_provvisorio': d['codice'], 'causa': 'markdown_nuovo_d04',
                           **{k2: v for k2, v in d.items() if k2 != 'codice'}})
        with open(D04/f'{caso}_righe_nuove.jsonl', 'w', encoding='utf-8') as f:
            for x in uscita:
                f.write(json.dumps(x, ensure_ascii=False, default=str) + '\n')
        conto = {'caso': caso, 'data': DATA, 'markdown_d04': len(file), 'citazioni_nel_csv': len(righe_csv) + len(copie),
                 'copie_di_righe_del_corpus_di_prima': len(copie), 'gia_coperte_in_piattaforma': gia_coperte,
                 'righe_nuove': len(uscita), 'id_gia_esistenti': id_doppi,
                 'documenti': dict(collections.Counter(x['document_id'] for x in uscita)),
                 'codici_provvisori': [uscita[0]['codice_provvisorio'], uscita[-1]['codice_provvisorio']] if uscita else None,
                 'codice_piu_alto_in_piattaforma': f'{pre}-{max(gia, default=0):04d}'}
        json.dump(conto, open(D04/f'{caso}_confronto.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        riepilogo[caso] = {k: conto[k] for k in ('citazioni_nel_csv', 'copie_di_righe_del_corpus_di_prima', 'righe_nuove', 'documenti')}
        print(f'== {caso}: righe nuove {len(uscita)} (copie del corpus di prima {len(copie)}, gia\' coperte {gia_coperte})', conto['documenti'])
    if not a.caso:
        json.dump(riepilogo, open(D04/'riepilogo.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    import giornale  # il giornale delle operazioni: ogni esecuzione, i file, le scritture, gli errori
    giornale.avvia()
    raise SystemExit(main())
