"""N01, le controversie: i casi che il Climate Litigation Database riunisce in una raccolta (bundle) contano come un caso solo.

Regola decisa dal PI il 15/10/2026: si unisce solo cio' che il database stesso unisce (il bundle), niente legami dedotti dai
nomi. Legge l'ultimo dump in dumps/ e scrive pubblicazione/influenza/n01_controversie.json: caso -> controversia, solo per le
raccolte con almeno due casi. n01_influenza.py lo legge da solo.

Uso: .venv/bin/python tools/n01_controversie.py [--dump dumps/CCC-whole_data_dump-AAAA-MM-GG.zip]
"""
from __future__ import annotations

import argparse, collections, io, json, pathlib, zipfile

QUI = pathlib.Path(__file__).resolve().parent.parent
USCITA = QUI / 'pubblicazione' / 'influenza' / 'n01_controversie.json'


def main():
    import pandas as pd
    ap = argparse.ArgumentParser()
    ap.add_argument('--dump', default=str(sorted((QUI / 'dumps').glob('CCC-whole_data_dump-*.zip'))[-1]))
    a = ap.parse_args()
    z = zipfile.ZipFile(a.dump)
    nome = next(n for n in z.namelist() if n.endswith('.xlsx'))
    df = pd.read_excel(io.BytesIO(z.read(nome)), dtype=str, usecols=['Case ID', 'Bundle ID(s)', 'Bundle Name(s)'])
    casi = collections.defaultdict(set)
    nomi = {}
    for cid, bid, bn in df.itertuples(index=False):
        ids = [x.strip() for x in str(bid or '').split(';') if x.strip() and x.strip() != 'nan']
        ns = [x.strip() for x in str(bn or '').split(';')]
        for i, b in enumerate(ids):
            casi[b].add(cid)
            nomi.setdefault(b, ns[i] if i < len(ns) else '')
    raccolte = {b: sorted(s) for b, s in casi.items() if len(s) >= 2}
    mappa, doppi = {}, []
    for b, s in sorted(raccolte.items()):
        for cid in s:
            if cid in mappa:  # un caso in due raccolte: resta nella prima, e lo si dice
                doppi.append({'caso': cid, 'tenuta': mappa[cid], 'scartata': b})
                continue
            mappa[cid] = b
    out = {'regola': 'N01-controversie', 'decisa_il': '2026-10-15',
           'fonte': pathlib.Path(a.dump).name, 'raccolte': {b: {'nome': nomi[b], 'casi': s} for b, s in raccolte.items()},
           'caso_controversia': mappa, 'casi_in_piu_raccolte': doppi}
    USCITA.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(len(raccolte), 'raccolte con almeno due casi,', len(mappa), 'casi;', len(doppi), 'casi in piu raccolte ->', USCITA)


if __name__ == '__main__':
    main()
