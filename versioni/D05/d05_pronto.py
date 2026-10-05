#!/usr/bin/env python3
"""D05, PASSO 5: METADATI E CONSEGNA ALLA RICERCA (04/10/2026).

   Scrive, senza toccare metadata.csv (lo leggono le catene in corso):
     training/d05/metadata_d05.csv   le righe del dump del 04/10 degli atti con un Markdown nuovo o una versione nuova,
                                     colonne del dump (come metadata.csv) piu' markdown_d05 e gruppo_d05;
     training/d05/PRONTO.json        per la ricerca S07: atti nuovi (Markdown in markdown/), versioni nuove e i 111
                                     rifatti con l'OCR (Markdown in training/d05/markdown_ocr/, accanto al vivo), indice
                                     D05, le 13 righe di D04 e i fallimenti dello scarico, con le impronte.
   NON fa la ricerca per nome e non scrive corpus_rows.

   Uso:  .venv/bin/python tools/d05_pronto.py
"""
import csv, json, re, sys
from pathlib import Path

QUI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools')); sys.path.insert(0, str(QUI))
import d05_testo as T     # noqa: E402

D05 = QUI/'training'/'d05'
SOGLIE = {'urgenda': '2015-06-24', 'neubauer': '2021-03-24', 'future-generations': '2018-02-12',
          'klimaseniorinnen': '2024-04-09', 'cig-parere-clima': '2025-07-23', 'idh-oc-32-25': '2025-07-03'}
AFRICA = 'request-for-an-advisory-opinion-on-the-human-rights-obligations-of-african-states-in-addressing-the-climate-crisis_2579'


def data_atto(u):
    m = re.search(r'/(\d{4})(\d{2})(\d{2})[_-]', u)
    return '-'.join(m.groups()) if m else ''


def main():
    reg = json.load(open(T.REG, encoding='utf-8'))
    idx = T.righe_dump()
    sha = T.sha_file
    scritti = [v for v in reg['nuovi'] if v['esito'] == 'scritto']
    # metadati
    righe = []
    for v in scritti:
        r = dict(T.riga_per(idx, v['document_id'], v['url']))
        r['markdown_d05'], r['gruppo_d05'] = v['markdown'], v['gruppo']
        righe.append(r)
    meta = D05/'metadata_d05.csv'
    with open(meta, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(righe[0].keys()))
        w.writeheader(); w.writerows(righe)
    caso = {r['Document ID']: r.get('Case ID', '') for r in righe}

    def voce(v):
        u = v['url']
        return {'document_id': v['document_id'], 'altri_id': v.get('altri_id', []), 'case_id': caso.get(v['document_id'], ''),
                'markdown': v['markdown'], 'sha256_markdown': v['sha256_markdown'], 'url': u, 'data_atto': data_atto(u),
                'geo': 'nonUS' if '/non-us-case-documents/' in u else 'US', 'pagine': v['pagine'],
                'pagine_ocr': v.get('pagine_ocr') or [], 'africa': caso.get(v['document_id']) == AFRICA}
    nuovi = [voce(v) for v in scritti if v['gruppo'] == 'nuovo']
    versioni = [dict(voce(v), nota="versione nuova di un atto che ha gia' un Markdown (URL cambiata alla fonte, byte "
                                    "diversi): pagine nell'indice D05 con id '<doc>@<8 cifre>#p<n>'")
                for v in scritti if v['gruppo'] == 'versione_nuova']
    rifatti = [{'document_id': v['document_id'], 'markdown_d05': v['markdown'], 'markdown_vivo': v['markdown_vivo'],
                'sha256_markdown': v['sha256_markdown'], 'sha256_markdown_vivo': v['sha256_markdown_vivo'],
                'pagine': v['pagine'], 'pagine_ocr': v['pagine_ocr']} for v in reg['scansioni'] if v['esito'] == 'scritto']
    falliti = []
    for l in open(QUI/'failures.tsv', encoding='utf-8'):
        p = l.rstrip('\n').split('\t')
        if len(p) >= 7 and p[3].startswith('2026-10-04'):
            falliti.append({'url': p[0], 'errore': p[2], 'quando': p[3], 'tentativi': p[5].split('=')[-1],
                            'document_ids': p[6].split(';')})
    gruppi = {}
    for c, s in SOGLIE.items():
        gruppi[c] = {g: sum(1 for x in nuovi + versioni if x['geo'] == g and x['data_atto'] >= s) for g in ('US', 'nonUS')}
    pronto = {
        'codice': 'D05', 'nome': "aggiornamento del corpus del 04/10/2026", 'data': '2026-10-04',
        'dump': {'file': 'dumps/CCC-whole_data_dump-2026-10-04.zip', 'sha256': sha(T.DUMP)},
        'indice_pagine': {'index/pagine/pagine.d05.jsonl.gz': reg['indice']['uscite']['index/pagine/pagine.d05.jsonl.gz'],
                          'index/pagine/pagine.d05.aggiunte.jsonl.gz': reg['indice']['uscite']['index/pagine/pagine.d05.aggiunte.jsonl.gz'],
                          'righe': reg['indice']['righe_d05'], 'base': 'pagine.d04.jsonl.gz (D04)'},
        'come_cercare': ("Atti nuovi e versioni nuove: i Markdown in 'markdown' (per i nuovi gia' in markdown/, quindi anche in "
                         "una ricerca su tutto markdown/ lanciata da adesso; la ricerca S07 in corso li ha fuori perche' l'elenco "
                         "dei file si fa all'avvio). I 111 rifatti: cercare su 'markdown_d05' (in training/d05/markdown_ocr/), "
                         "stesso front matter e stesso document_id del Markdown vivo, che resta com'era finche' non si decide lo "
                         "scambio; una riga gia' in banca su quei documenti ha char_start del Markdown vivo. Le righe di D04 "
                         "(13, gia' preparate, mai caricate): training/d04/righe_d04.jsonl."),
        'atti_nuovi': nuovi, 'versioni_nuove': versioni, 'rifatti_con_ocr': rifatti,
        'd04': {'righe': 'training/d04/righe_d04.jsonl', 'sha256_righe': sha(QUI/'training'/'d04'/'righe_d04.jsonl'),
                'n_righe': sum(1 for _ in open(QUI/'training'/'d04'/'righe_d04.jsonl', encoding='utf-8')),
                'registro_markdown': 'training/d04/markdown_d04_registro.json'},
        'falliti_allo_scarico': falliti,
        'conti': {'atti_nuovi': len(nuovi), 'versioni_nuove': len(versioni), 'rifatti_con_ocr': len(rifatti),
                  'pagine_ocr_sostituite_nei_111': sum(len(x['pagine_ocr']) for x in rifatti),
                  'pagine_ocr_sostituite_nei_nuovi': sum(len(x['pagine_ocr']) for x in nuovi + versioni),
                  'pagine_nuovi': sum(x['pagine'] for x in nuovi + versioni),
                  'memorie_africane_nuove': sum(x['africa'] for x in nuovi),
                  'nonUS_dopo_2025_07_23': sum(1 for x in nuovi + versioni if x['geo'] == 'nonUS' and x['data_atto'] >= '2025-07-23'),
                  'per_caso_dopo_la_decisione': gruppi, 'falliti': len(falliti)},
        'metadati': {'training/d05/metadata_d05.csv': sha(meta)},
        'registro': {'training/d05/markdown_d05_registro.json': sha(T.REG)},
    }
    tmp = D05/'PRONTO.json.nuovo'
    tmp.write_text(json.dumps(pronto, ensure_ascii=False, indent=1), encoding='utf-8')
    tmp.replace(D05/'PRONTO.json')
    print(json.dumps(pronto['conti'], ensure_ascii=False, indent=1))


if __name__ == '__main__':
    import giornale  # il giornale delle operazioni: ogni esecuzione, i file, le scritture, gli errori
    giornale.avvia()
    raise SystemExit(main())
