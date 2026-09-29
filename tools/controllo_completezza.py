"""Completeness check: does every row have everything it must have?

   The check starts from the DATABASE, not from prepared files: loaders that start from hand-prepared files
   silently leave rows missing from those files without proposals. For every row in the Uptakes view (networks
   `lessicale` and `entrambe`) the script verifies that all required fields are present, and collects what is
   missing into a list from which the next readings are prepared. Run it after every load.

   Required fields of an Uptakes row:
     always          case-formatted, unique code; provenance with versions that exist in the registry;
                     document and file; proposed type; proposed principles; reranker scores on principles
     if judged       who and when; if confirmed, the saved principles
     if merged       the target row exists and is not itself merged
   The result is written to `trace_controlli/<date and time>` (shown in the portal) and, for rows without
   proposals, to `training/mancanti_<caso>_<data>.txt`.

   Usage:  .venv/bin/python tools/controllo_completezza.py [--scrivi]
"""
import argparse, collections, datetime, pathlib, re
from google.cloud import firestore
QUI = pathlib.Path(__file__).resolve().parent.parent
PREFISSI = {'urgenda': 'URG', 'neubauer': 'NEU', 'future-generations': 'FGC'}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--scrivi', action='store_true'); a = ap.parse_args()
    db = firestore.Client(project='climpact-drp')
    versioni = {d.id for d in db.collection('trace_versioni').stream()}
    oggi = datetime.datetime.now().strftime('%Y-%m-%d_%H%M')
    rapporto = {'quando': firestore.SERVER_TIMESTAMP, 'versioni_nel_registro': sorted(versioni), 'casi': {}}
    for caso, pre in PREFISSI.items():
        righe = [(d.id, d.to_dict()) for d in db.collection('corpus_rows')
                 .where(filter=firestore.FieldFilter('caso_citato', '==', caso)).stream()]
        codici = {r.get('codice'): (i, r) for i, r in righe if r.get('codice')}
        problemi = collections.defaultdict(list)
        mancanti = []
        viste = collections.Counter()
        for i, r in righe:
            rete = r.get('proposto_rete')
            if rete == 'fusa':
                t = codici.get(r.get('fusa_in'))
                if not t:
                    problemi['unita verso un codice che non esiste'].append(r.get('codice') or i)
                elif t[1].get('proposto_rete') == 'fusa':
                    problemi['unita verso una riga a sua volta unita'].append(r.get('codice') or i)
                continue
            if rete not in ('lessicale', 'entrambe'):
                continue
            cod = r.get('codice') or ''
            chi = cod or i
            viste[cod] += 1
            if not re.fullmatch(pre + r'-\d{4}', cod):
                problemi['codice mancante o sbagliato'].append(chi)
            if not r.get('document_id') or not r.get('file'):
                problemi['senza documento'].append(chi)
            pv = r.get('provenienza') or {}
            if not pv:
                problemi['senza provenienza'].append(chi)
            usate = [pv.get(k) for k in ('corpus', 'estrazione', 'tipo', 'composizione', 'seguito')]
            usate += [x for v in (pv.get('principi') or {}).values() for x in v]
            for u in usate:
                if u and u not in versioni:
                    problemi[f'versione {u} assente dal registro'].append(chi)
            manca = []
            if not r.get('proposto_tipo_citazione'):
                manca.append('tipo proposto')
            if r.get('proposto_principi') is None:
                manca.append('principi proposti')
            if not r.get('proposto_punteggi_principi'):
                manca.append('punteggi del reranker')
            for m in manca:
                problemi[f'senza {m}'].append(chi)
            # every proposal must record the version that produced it
            if r.get('proposto_tipo_citazione') and not pv.get('tipo'):
                problemi['tipo proposto senza versione'].append(chi)
            if r.get('proposto_principi') and r.get('proposto_principi') != ['nessuno'] and not pv.get('principi'):
                problemi['principi proposti senza versione'].append(chi)
            if not pv.get('estrazione'):
                problemi['senza la versione della ricerca'].append(chi)
            if manca and not r.get('esito'):
                mancanti.append(i)
            if r.get('esito'):
                if not r.get('validato_da'):
                    problemi['giudicata senza chi'].append(chi)
                if not r.get('validato_il'):
                    problemi['giudicata senza quando'].append(chi)
                if r.get('esito') == 'confermata' and r.get('validato_principi') is None:
                    problemi['confermata senza principi salvati'].append(chi)
            elif r.get('validato_da') and not r.get('da_discutere'):
                problemi['chi senza giudizio'].append(chi)
        for cod, n in viste.items():
            if cod and n > 1:
                problemi['codice doppio'].append(cod)
        tot = sum(1 for _, r in righe if r.get('proposto_rete') in ('lessicale', 'entrambe'))
        print(f'\n{caso}: {tot} righe in Uptakes')
        if not problemi:
            print('   tutto in ordine')
        for k, v in sorted(problemi.items()):
            print(f'   {k}: {len(v)}  {v[:8]}')
        if mancanti:
            f = QUI/'training'/f'mancanti_{caso}_{oggi}.txt'
            f.write_text('\n'.join(mancanti) + '\n')
            print(f'   righe da giudicare senza proposte: {len(mancanti)} -> {f.name}')
        rapporto['casi'][caso] = {'righe': tot, 'problemi': {k: {'quante': len(v), 'esempi': v[:50]} for k, v in problemi.items()},
                                  'senza_proposte_da_giudicare': len(mancanti)}
    if a.scrivi:
        db.collection('trace_controlli').document(oggi).set(rapporto)
        print(f'\nscritto trace_controlli/{oggi}')


if __name__ == '__main__':
    main()
