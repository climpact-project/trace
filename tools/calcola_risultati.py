"""I RISULTATI DI TRACE PER LA PAGINA PUBBLICA, CALCOLATI DALLA BANCA DATI (29/09/2026, richiesta del PI).

   Sulla pagina /site/data/trace i risultati non stanno nel codice: stanno nel documento `trace_risultati/corrente`,
   che questo programma calcola dalle righe cosi' come sono, e che la pagina mostra solo quando il PI lo approva
   (`approvato`). Ogni cifra porta: il valore in percentuale (regola del PI: niente piccoli numeri assoluti sulla
   pagina), la base (quante righe, solo in banca dati), le versioni da cui vengono le proposte misurate, e che cosa
   misura. Ogni ricalcolo lascia una copia in `trace_risultati/<data e ora>`: si vede come sono cambiati i numeri.
   Le frasi della sezione (`testi`) e l'approvazione si cambiano dal portale; il ricalcolo le conserva, ma toglie
   l'approvazione se le cifre cambiano (un numero nuovo si approva di nuovo).

   Le misure, per ogni caso, solo sulle citazioni col nome giudicate nella scheda Uptakes:
     - quante delle righe trovate per nome il team conferma come citazioni del caso;
     - come si distribuiscono i tipi di citazione confermati (catena, descrittiva, sostanziale, distinguente, critica);
     - accordo fra la macchina e il team sul tipo: su tutte le giudicate, e a parte sulle righe viste alla cieca
       (la misura pulita: la persona non ha visto la proposta);
     - principi: in quante citazioni confermate la macchina aveva proposto almeno uno dei principi confermati;
     - seguito: quante pagine di seguito proposte il team conferma;
     - avanzamento: quante citazioni sono gia' giudicate.
   Sotto una base minima (MINIMO righe) la cifra si calcola ma porta `poche_righe`: la pagina non la mostra.

   Uso:  .venv/bin/python tools/calcola_risultati.py [--scrivi]
"""
import argparse, collections, datetime, json
from google.cloud import firestore

CASI = {'urgenda': 'Urgenda', 'neubauer': 'Neubauer', 'future-generations': 'Future Generations'}
TIPI = {'menzione_in_catena': 'chain mention', 'descrittiva': 'descriptive', 'sostanziale': 'substantive',
        'distinguente': 'distinguishing', 'critica': 'critical'}
MINIMO = 30


def pc(num, den):
    return round(100 * num / den, 1) if den else None


def cifra(id_, etichetta, num, den, versioni, misura):
    return {'id': id_, 'etichetta': etichetta, 'valore': pc(num, den), 'numeratore': num, 'base': den,
            'versioni': sorted(set(v for v in versioni if v)), 'misura': misura, 'poche_righe': den < MINIMO}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--scrivi', action='store_true'); a = ap.parse_args()
    db = firestore.Client(project='climpact-drp')
    casi = {}
    for caso, nome in CASI.items():
        righe = [d.to_dict() for d in db.collection('corpus_rows').where(filter=firestore.FieldFilter('caso_citato', '==', caso)).stream()]
        nom = [r for r in righe if r.get('proposto_rete') in ('lessicale', 'entrambe')]
        giud = [r for r in nom if r.get('esito') and (r.get('validato_principi') is not None or r.get('esito') == 'scartata'
                                                         or (r.get('validato_contesto') or {}).get('scheda') == 'riprese')]
        conf = [r for r in giud if r.get('esito') == 'confermata']
        cieche = [r for r in conf if (r.get('validato_contesto') or {}).get('cieco') or r.get('campione_cieco')]
        vers_tipo = [(r.get('provenienza') or {}).get('tipo') for r in conf]
        c = []
        c.append(cifra('conferma', 'Name hits confirmed as citations of the judgment', len(conf), len(giud),
                       [(r.get('provenienza') or {}).get('estrazione') for r in giud], 'confirmed / judged, explicit citations'))
        conta = collections.Counter(r.get('validato_tipo_citazione') or r.get('proposto_tipo_citazione') for r in conf)
        for t, en in TIPI.items():
            c.append(cifra(f'tipo_{t}', f'Confirmed citations that are {en}', conta.get(t, 0), len(conf), [], 'share of confirmed citations'))
        con_tipo = [r for r in conf if r.get('proposto_tipo_citazione') and r.get('validato_tipo_citazione')]
        c.append(cifra('accordo_tipo', 'Machine and team agree on the type of citation',
                       sum(1 for r in con_tipo if r['proposto_tipo_citazione'] == r['validato_tipo_citazione']), len(con_tipo),
                       vers_tipo, 'same type proposed and confirmed, all judged rows'))
        cb = [r for r in cieche if r.get('proposto_tipo_citazione') and r.get('validato_tipo_citazione')]
        c.append(cifra('accordo_tipo_cieco', 'Machine and team agree on the type, on rows judged blind',
                       sum(1 for r in cb if r['proposto_tipo_citazione'] == r['validato_tipo_citazione']), len(cb),
                       [(r.get('provenienza') or {}).get('tipo') for r in cb], 'the person did not see the proposal'))
        pr = [r for r in conf if r.get('validato_principi') and set(r['validato_principi']) - {'nessuno'} and r.get('proposto_principi')]
        c.append(cifra('principi', 'Citations where the machine proposed a principle the team confirmed',
                       sum(1 for r in pr if set(r['proposto_principi']) & set(r['validato_principi'])), len(pr),
                       [x for r in pr for v in ((r.get('provenienza') or {}).get('principi') or {}).values() for x in v],
                       'at least one proposed principle confirmed'))
        prop = [(r, {v['pagina'] for v in (r.get('proposto_estensione') or []) if v.get('prosegue')}) for r in conf]
        prop = [(r, p) for r, p in prop if p and r.get('validato_estensione') is not None]
        n_prop = sum(len(p) for _, p in prop)
        n_ok = sum(len(p & {(e['pagina'] if isinstance(e, dict) else e) for e in r['validato_estensione']}) for r, p in prop)
        c.append(cifra('seguito', 'Proposed continuation pages confirmed by the team', n_ok, n_prop,
                       [(r.get('provenienza') or {}).get('seguito') for r, _ in prop], 'pages, not citations'))
        c.append(cifra('avanzamento', 'Explicit citations judged so far', len(giud), len(nom), [], 'progress of the team'))
        casi[caso] = {'nome': nome, 'cifre': c}
        print(f'\n{nome}: {len(nom)} citazioni, giudicate in Uptakes {len(giud)}, confermate {len(conf)}, alla cieca {len(cieche)}')
        for x in c:
            print(f"   {x['etichetta']}: {x['valore']}% ({x['numeratore']}/{x['base']}){' POCHE RIGHE' if x['poche_righe'] else ''} {' '.join(x['versioni'])}")
    if not a.scrivi:
        return
    ref = db.collection('trace_risultati').document('corrente')
    prima = ref.get().to_dict() or {}
    cambiate = json.dumps({k: [(x['id'], x['valore']) for x in v['cifre']] for k, v in casi.items()}) != \
        json.dumps({k: [(x['id'], x['valore']) for x in v['cifre']] for k, v in (prima.get('casi') or {}).items()})
    testi = prima.get('testi') or {
        'titolo': 'What TRACE has found so far',
        'lead': 'Figures computed from the database on the citations the team has judged. They change as the judging goes on; each carries the codes of the versions whose proposals it measures.',
        'nota': 'Explicit citations only. Implicit uptake without a citation is not measured here.',
    }
    # L'AVVERTENZA (revisione del 30/09/2026): le cifre di accordo sono misurate con le proposte della macchina davanti a chi
    # giudica, salvo quelle «alla cieca»; finche' le righe cieche sono poche, la pagina lo deve dire.
    doc = {'casi': casi, 'testi': testi, 'calcolato_il': firestore.SERVER_TIMESTAMP, 'minimo_righe': MINIMO,
           'avvertenza': ('Agreement figures are measured on rows judged with the machine\'s proposals in view, except those '
                          'marked "judged blind". They say how often the team confirmed the proposal, not how often the '
                          'machine would have been right on its own. Blind rows are being judged now.'),
           'approvato': bool(prima.get('approvato')) and not cambiate,
           'approvato_da': prima.get('approvato_da') if not cambiate else None,
           'approvato_il': prima.get('approvato_il') if not cambiate else None}
    ref.set(doc)
    db.collection('trace_risultati').document(datetime.datetime.now().strftime('%Y-%m-%d_%H%M')).set({**doc, 'copia': True})
    print('\nscritto trace_risultati/corrente', '(cifre cambiate: approvazione tolta)' if cambiate and prima.get('approvato') else '')


if __name__ == '__main__':
    main()
