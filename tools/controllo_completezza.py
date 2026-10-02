"""IL CONTROLLO DI COMPLETEZZA: OGNI RIGA HA TUTTO QUELLO CHE DEVE AVERE? (29/09/2026, dopo un buco di metodo)

   Perche'. Fino al 29/09 ogni caricamento partiva da file preparati a mano: le righe che nei file non c'erano
   restavano senza proposte e nessuno se ne accorgeva (353 righe giudicate a settembre e tornate in coda, 59 righe
   aggiunte dalla ricerca corretta, 17 letture illeggibili). Qui si parte dalla BANCA DATI, non dai file: per ogni
   riga della scheda Uptakes (reti `lessicale` ed `entrambe`) si verifica che ci sia tutto, e quello che manca finisce
   in un elenco da cui si preparano le letture successive. Si lancia dopo ogni caricamento.

   Che cosa deve avere una riga di Uptakes:
     sempre         codice nel formato del caso e unico; provenienza con versioni che esistono nel registro;
                    documento e file; tipo proposto; principi proposti; punteggi del reranker sui principi
     se giudicata   chi e quando; se confermata, i principi salvati
     se unita       la riga in cui e' unita esiste e non e' unita a sua volta
   Il risultato si scrive in `trace_controlli/<data e ora>` (il portale lo mostra) e, per le righe senza proposte,
   in `training/mancanti_<caso>_<data>.txt`.

   Uso:  .venv/bin/python tools/controllo_completezza.py [--scrivi]
"""
import argparse, collections, datetime, pathlib, re
from google.cloud import firestore
QUI = pathlib.Path(__file__).resolve().parent.parent
PREFISSI = {'urgenda': 'URG', 'neubauer': 'NEU', 'future-generations': 'FGC', 'klimaseniorinnen': 'KLS', 'cig-parere-clima': 'ICJ', 'idh-oc-32-25': 'IAC'}


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
            usate = [pv.get(k) for k in ('corpus', 'estrazione', 'tipo', 'composizione', 'seguito', 'sonde')]
            # dal 01/10/2026 ogni proposta di principio dice con quale serie di sonde e' stata fatta (famiglia P)
            if not r.get('esito') and r.get('proposto_principi') and not pv.get('sonde'):
                problemi['principi proposti senza il codice delle sonde'].append(chi)
            usate += [x for v in (pv.get('principi') or {}).values() for x in v]
            for u in usate:
                if u and u not in versioni:
                    problemi[f'versione {u} assente dal registro'].append(chi)
            manca = []
            if not r.get('proposto_tipo_citazione'):
                manca.append('tipo proposto')
            # anche l'elenco VUOTO conta come mancante (revisione del 30/09/2026: 247 righe con [] passavano il controllo)
            if r.get('proposto_principi') is None or r.get('proposto_principi') == []:
                manca.append('principi proposti')
            if not r.get('proposto_punteggi_principi'):
                manca.append('punteggi del reranker')
            for m in manca:
                problemi[f'senza {m}'].append(chi)
            # ogni proposta dice da quale versione viene (il 29/09 352 tipi erano senza)
            if r.get('proposto_tipo_citazione') and not pv.get('tipo'):
                problemi['tipo proposto senza versione'].append(chi)
            if r.get('proposto_principi') and r.get('proposto_principi') != ['nessuno'] and not pv.get('principi'):
                problemi['principi proposti senza versione'].append(chi)
            if not pv.get('estrazione'):
                problemi['senza la versione della ricerca'].append(chi)
            # I FRENI (30/09/2026): nessuna proposta poggia su una prova inventata o non trovata
            for e in (r.get('proposto_estensione') or []):
                if e.get('prova_esito') == 'inventata':
                    problemi['prova inventata (copiata dal prompt)'].append(chi); break
            # solo le righe da giudicare: sulle giudicate restano le proposte che la persona ha visto (prima dei freni)
            if not r.get('esito') and any(e.get('prosegue') and not e.get('testuale') for e in (r.get('proposto_estensione') or [])):
                problemi['pagina spuntata senza prova trovata'].append(chi)
            if r.get('proposto_frase_esito') == 'inventata':
                problemi['frase sostenuta inventata'].append(chi)
            if manca and not r.get('esito') and not r.get('proposta_provvisoria'):
                mancanti.append(i)
            if r.get('proposta_provvisoria') and not r.get('esito'):
                problemi['proposta provvisoria, in attesa della lettura di DeepSeek'].append(chi)
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
