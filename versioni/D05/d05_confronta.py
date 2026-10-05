#!/usr/bin/env python3
"""D05, PASSO 1: IL DUMP CORRENTE CONTRO IL CORPUS SUL DISCO (04/10/2026).

   Non confronta dump con dump (come `check_updates.py`): confronta OGNI riga del dump corrente con quello che il
   corpus ha davvero. Un atto c'e' solo se un Markdown porta il suo `document_id` nel front matter e il suo
   `url_origine` e' l'indirizzo che il dump da' oggi. L'audit del 04/10 ha mostrato che il manifest non basta: righe
   `http: 0` con l'impronta di un altro file, indirizzi «gia' fatti» perche' scaricati per un altro atto.

   Classi (una per riga del dump con un indirizzo):
     ok                     Markdown con lo stesso document_id e lo stesso indirizzo
     url_cambiata           Markdown con lo stesso document_id ma un altro indirizzo (versione nuova alla fonte?)
     scaricato_senza_md     (document_id, indirizzo) scaricato davvero (http 200), ma nessun Markdown
     url_ereditata          indirizzo scaricato per ALTRI atti, mai per questo (load_done per URL lo saltava)
     solo_http0             indirizzo nel manifest solo con righe http 0 (impronta del file di un altro atto)
     fallito                indirizzo solo in failures.tsv
     mai_scaricato          indirizzo mai visto
   Uscite: training/d05/confronto.json (ogni riga, con classe e data dell'atto dal nome del file) e
   training/d05/da-scaricare-d05.csv (le righe del dump di tutte le classi tranne ok, colonne del dump).

   Uso:  .venv/bin/python tools/d05_confronta.py dumps/CCC-whole_data_dump-2026-10-04.zip
"""
import collections, csv, json, re, sys, unicodedata
from pathlib import Path

csv.field_size_limit(10 ** 9)
QUI = Path(__file__).resolve().parent.parent
D05 = QUI/'training'/'d05'
SOGLIE = {'urgenda': '2015-06-24', 'neubauer': '2021-03-24', 'future-generations': '2018-02-12',
          'klimaseniorinnen': '2024-04-09', 'cig-parere-clima': '2025-07-23', 'idh-oc-32-25': '2025-07-03'}
AFRICA = 'request-for-an-advisory-opinion-on-the-human-rights-obligations-of-african-states-in-addressing-the-climate-crisis_2579'


def nfc(s):
    return unicodedata.normalize('NFC', s or '').strip()


def leggi_dump(z):
    """CSV o XLSX: la lettura di `check_updates.read_dump`, la stessa dei confronti di prima."""
    sys.path.insert(0, str(QUI))
    import check_updates
    return check_updates.read_dump(Path(z))[0]


def markdown():
    """document_id -> [(url_origine, sha256_pdf, file)] dal front matter di ogni Markdown."""
    out = collections.defaultdict(list)
    for p in QUI.joinpath('markdown').rglob('*.md'):
        with p.open(encoding='utf-8', errors='replace') as f:
            testa = f.read(8000)
        g = lambda k: (re.search(rf"^{k}: '?(.*?)'?$", testa, re.M) or [None, ''])[1].replace("''", "'")
        did = g('document_id')
        if did:
            out[did].append((nfc(g('url_origine')), g('sha256_pdf'), str(p.relative_to(QUI))))
    return out


def data_atto(u):
    m = re.search(r'/(\d{4})(\d{2})(\d{2})[_-]', u)
    return '-'.join(m.groups()) if m else ''


def geo(u):
    return 'nonUS' if '/non-us-case-documents/' in u else 'US'


def main():
    dump = Path(sys.argv[1])
    righe = leggi_dump(dump)
    md = markdown()
    coppie_200, url_200, url_0 = set(), set(), set()
    for f in [QUI/'manifest.jsonl'] + sorted(QUI.glob('manifest_supplemento_*.jsonl')):
        for l in open(f, encoding='utf-8'):
            r = json.loads(l)
            u = nfc(r.get('url'))
            if r.get('status') != 'ok':
                continue
            if r.get('http') == 200:
                url_200.add(u)
                for d in r.get('docs') or []:
                    coppie_200.add((d['document_id'], u))
            elif r.get('http') == 0:
                url_0.add(u)
    falliti = {}
    for l in open(QUI/'failures.tsv', encoding='utf-8'):
        p = l.rstrip('\n').split('\t')
        if p and p[0]:
            falliti[nfc(p[0])] = p[-1]
    voci, conti, da_scaricare = [], collections.Counter(), []
    for r in righe:
        did, u = (r.get('Document ID') or '').strip(), nfc(r.get('Document Content URL'))
        if not u.lower().startswith('http'):
            conti['senza indirizzo'] += 1
            continue
        mm = md.get(did, [])
        if any(x[0] == u for x in mm):
            c = 'ok'
        elif mm:
            c = 'url_cambiata'
        elif (did, u) in coppie_200:
            c = 'scaricato_senza_md'
        elif u in url_200:
            c = 'url_ereditata'
        elif u in url_0:
            c = 'solo_http0'
        elif u in falliti:
            c = 'fallito'
        else:
            c = 'mai_scaricato'
        conti[c] += 1
        if c == 'ok':
            continue
        voci.append({'document_id': did, 'case_id': r.get('Case ID', ''), 'url': u, 'classe': c, 'data_atto': data_atto(u),
                     'geo': geo(u), 'titolo': r.get('Document Title', ''), 'aggiunto': r.get('Date Added to System', ''),
                     'lingue': r.get('Language(s)', ''), 'markdown_esistenti': mm, 'errore_precedente': falliti.get(u, ''),
                     'africa': r.get('Case ID', '') == AFRICA})
        da_scaricare.append(r)
    D05.mkdir(parents=True, exist_ok=True)
    json.dump({'dump': dump.name, 'righe_dump': len(righe), 'conti': conti, 'voci': voci},
              open(D05/'confronto.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    with open(D05/'da-scaricare-d05.csv', 'w', newline='', encoding='utf8') as f:
        w = csv.DictWriter(f, fieldnames=list(righe[0].keys()))
        w.writeheader(); w.writerows(da_scaricare)
    print(dump.name, 'righe', len(righe))
    for k, v in conti.most_common():
        print(f'  {v:>6}  {k}')
    nuovi = [v for v in voci if v['classe'] != 'url_cambiata']
    print('atti senza Markdown:', len(nuovi), 'di cui Africa', sum(v['africa'] for v in nuovi),
          '| nonUS dopo il 23/07/2025:', sum(1 for v in nuovi if v['geo'] == 'nonUS' and v['data_atto'] >= '2025-07-23'))
    for caso, s in SOGLIE.items():
        print(f'  {caso:20s} dopo {s}: US {sum(1 for v in nuovi if v["geo"]=="US" and v["data_atto"]>=s):4d}'
              f'  nonUS {sum(1 for v in nuovi if v["geo"]=="nonUS" and v["data_atto"]>=s):4d}')


if __name__ == '__main__':
    main()
