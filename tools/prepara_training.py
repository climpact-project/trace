"""RICUCITURA DEL CAMPIONE UMANO PER L'ADDESTRAMENTO.

   I giudizi salvati da `salva_giudizi.py` portano il TITOLO della sonda, non
   il suo testo: il testo vive in `cited-cases/<caso>.yaml` e si legge con lo
   stesso lettore della pipeline (`leggi_caso`), non riscritto a mano. Qui si
   uniscono le due cose e si scrivono i due insiemi di addestramento.

   DUE COMPITI, DUE CAMPIONI DIVERSI.
     A. categoria   — solo rete lessicale: che lavoro fa la citazione nel testo.
     B. decisione   — solo rete semantica: il passaggio afferma quella sonda?
   La categoria sulle righe semantiche NON esiste (rimossa il 22/09/2026): era
   un fraintendimento del compito, non un dato.

   MASCHERAMENTO. Il nome del caso e i codici ECLI si sostituiscono con un
   segnaposto, usando le `forme` dichiarate nel file del caso — le stesse che
   la rete lessicale cerca. Senza, il modello impara la scorciatoia «se il nome
   non c'e' e' implicita» e in produzione, dove nessun candidato semantico ha
   il nome, etichetterebbe tutto allo stesso modo.

   DIVISIONE CONGELATA, RAGGRUPPATA PER CASO CITANTE. Lo stesso passaggio
   compare fino a nove volte e uno stesso documento porta fino a sedici righe:
   dividere a caso metterebbe lo stesso testo da entrambe le parti e il
   punteggio di prova sarebbe gonfiato. Si divide per `case_id` e si scrive su
   disco, perche' ogni esperimento successivo deve usare la stessa divisione.
"""
import json, pathlib, random, re, sys, collections
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from cerca import leggi_caso

QUI = pathlib.Path(__file__).resolve().parent.parent
CASO = 'urgenda'
SEGNAPOSTO = '⟦CASO_CITATO⟧'
QUOTA_PROVA = 0.30
SEME = 20260922


def mascheratore(forme):
    """Un'espressione sola con tutte le forme del caso, piu' i codici ECLI.

    Le forme si ordinano per lunghezza decrescente: «State of the Netherlands
    v. Urgenda Foundation» deve essere consumata prima di «Urgenda», altrimenti
    resta un residuo riconoscibile."""
    pezzi = sorted({f for f in forme if len(f) > 3}, key=len, reverse=True)
    pat = '|'.join(re.escape(f) for f in pezzi)
    pat += r'|ECLI:[A-Z]{2}:[A-Z]+:\d{4}:\d+|\b\d{2}/\d{5}\b|\b200\.\d{3}\.\d{3}/\d{2}\b'
    return re.compile(pat, re.I)


def main():
    conf = leggi_caso(QUI/'cited-cases'/f'{CASO}.yaml', con_alternative=True)
    testo_di = {}
    for s in conf['sonde']:
        testo_di[s['titolo']] = {'id': s['id'], 'testo': s['testo']}
    maschera = mascheratore(conf['forme'] + [conf.get('nome', '')])

    # Il FRAMMENTO ORIGINALE, quello che il riordinatore lesse davvero.
    # I giudizi portano `proposto_citazione_testuale` troncata a 460 caratteri,
    # ma il riordinatore ricevette il frammento intero (mediana 1.290 caratteri).
    # Senza, il confronto con i punteggi archiviati non sarebbe alla pari.
    # Recuperato da `index/chunks.jsonl` per (document_id, char_start):
    # ci sono tutte e 390 le righe della rete semantica pura. Le righe
    # lessicali non ne hanno uno, perche' nascono da una ricerca testuale sul
    # markdown e non da un frammento dell'indice.
    orig = {}
    po = QUI/'training'/'frammenti_originali.json'
    if po.exists():
        orig = json.loads(po.read_text(encoding='utf-8'))

    giudizi = sorted(QUI.glob('giudizi-umani-*.json'))[-1]
    righe = json.loads(giudizi.read_text(encoding='utf-8'))
    print(f'giudizi: {giudizi.name} ({len(righe)} righe)')
    print(f'sonde con testo: {len(testo_di)}   forme per il mascheramento: {len(conf["forme"])}')

    senza_testo = collections.Counter()
    A, B = [], []
    for r in righe:
        rete = r.get('proposto_rete') or ''
        son = (r.get('sonda') or '').strip()
        sd = testo_di.get(son)
        comune = {
            'id': r['_id'], 'case_id': r.get('case_id'), 'document_id': r.get('document_id'),
            'rete': rete, 'tipo_atto': r.get('tipo_atto'), 'anno': str(r.get('data'))[:4],
            'passaggio': maschera.sub(SEGNAPOSTO, str(r.get('proposto_citazione_testuale') or '')),
            'finestra': maschera.sub(SEGNAPOSTO, str(r.get('finestra_pagina') or '')),
            'frammento': maschera.sub(SEGNAPOSTO, str((orig.get(r['_id']) or {}).get('testo') or '')),
        }
        if rete in ('lessicale', 'entrambe'):
            cat = r.get('validato_tipo_citazione')
            if cat:
                A.append({**comune, 'categoria': cat,
                          'chi_parla': r.get('validato_chi_parla'),
                          'forma_trovata': r.get('proposto_forma_trovata')})
        if rete in ('semantica', 'entrambe'):
            if not sd:
                senza_testo[son[:50]] += 1
                continue
            val = r.get('validato_sonde') or []
            if isinstance(val, str):
                val = [val]
            # positiva solo se la sonda PROPOSTA e' fra quelle validate e non e' scartata
            pos = r['esito'] != 'scartata' and son in val
            B.append({**comune, 'sonda_id': sd['id'], 'sonda_titolo': son,
                      'sonda_testo': sd['testo'], 'etichetta': int(pos),
                      'esito': r['esito'],
                      'punteggio': r.get('punteggio'), 'riordino': r.get('punteggio_riordino'),
                      'margine': r.get('margine'), 'sospetto': r.get('sospetto') or '',
                      'corroborazione': r.get('corroborazione'),
                      'note': r.get('validato_note') or ''})
    if senza_testo:
        print('  ATTENZIONE, sonde senza testo nel file del caso:', senza_testo.most_common())

    # ── divisione per caso citante, bilanciata sulle etichette ──
    #
    # Raggruppare per caso NON basta: i casi sono di taglia molto diversa (da 1
    # a 31 righe) e una scelta a sorte porta in prova una composizione diversa
    # da quella di addestramento — misurato il 22/09/2026: 38% di positive in
    # prova contro 24% in addestramento, e «sostanziale» dal 35% al 55%. Un
    # punteggio di prova su una composizione diversa non si puo' confrontare
    # con niente. Si assegna quindi un caso per volta, dal piu' grosso al piu'
    # piccolo, mettendolo dalla parte che AVVICINA le due composizioni.
    casi = sorted({x['case_id'] for x in A} | {x['case_id'] for x in B})
    voci = collections.defaultdict(collections.Counter)   # caso -> conteggi per classe
    for x in A:
        voci[x['case_id']]['A:' + x['categoria']] += 1
    for x in B:
        voci[x['case_id']]['B:' + str(x['etichetta'])] += 1
    totale = collections.Counter()
    for c in casi:
        totale.update(voci[c])
    classi = sorted(totale)

    # Obiettivo: per OGNI classe, la prova deve contenerne circa QUOTA_PROVA.
    # Si assegna un caso per volta, dal piu' grosso al piu' piccolo, alla parte
    # che lascia la prova piu' vicina a quel bersaglio classe per classe. Un
    # criterio sulla composizione media non basterebbe: premierebbe sempre la
    # parte gia' piu' grande, che per forza somiglia di piu' al totale.
    bersaglio = {k: totale[k] * QUOTA_PROVA for k in classi}

    def costo(acc):
        return sum(abs(acc[k] - bersaglio[k]) for k in classi)

    ordine = sorted(casi, key=lambda c: (-sum(voci[c].values()), c))
    prova, acc_p = set(), collections.Counter()
    for c in ordine:
        v = voci[c]
        if costo(acc_p + v) < costo(acc_p):
            prova.add(c); acc_p.update(v)
    for x in A + B:
        x['parte'] = 'prova' if x['case_id'] in prova else 'addestramento'

    fuori = QUI/'training'
    fuori.mkdir(exist_ok=True)
    for nome, dati in (('categoria', A), ('decisione', B)):
        for parte in ('addestramento', 'prova'):
            sub = [x for x in dati if x['parte'] == parte]
            p = fuori/f'{CASO}_{nome}_{parte}.jsonl'
            p.write_text('\n'.join(json.dumps(x, ensure_ascii=False) for x in sub), encoding='utf-8')
            print(f'  {p.name:42s} {len(sub):4d} righe')
    (fuori/'divisione.json').write_text(json.dumps({
        'seme': SEME, 'quota_prova': QUOTA_PROVA, 'giudizi': giudizi.name,
        'casi_di_prova': sorted(prova), 'casi_totali': len(casi)}, indent=1), encoding='utf-8')

    print('\n— compito A, categoria (rete lessicale) —')
    for parte in ('addestramento', 'prova'):
        sub = [x for x in A if x['parte'] == parte]
        print(f'  {parte:14s} {len(sub):4d}  ' + str(collections.Counter(x['categoria'] for x in sub).most_common()))
    print('— compito B, decisione (rete semantica) —')
    for parte in ('addestramento', 'prova'):
        sub = [x for x in B if x['parte'] == parte]
        p = sum(x['etichetta'] for x in sub)
        print(f'  {parte:14s} {len(sub):4d}  positive {p} ({100*p/len(sub):.0f}%), negative {len(sub)-p}')
    senza_fr = [x for x in B if not x['frammento']]
    print(f'frammento originale: presente su {len(B)-len(senza_fr)} righe di B su {len(B)}'
          + (f' (mancano {len(senza_fr)}, tutte «entrambe»)' if senza_fr else ''))
    resti = [x for x in A + B if SEGNAPOSTO not in x['finestra']]
    print(f'\nmascheramento: {len(A)+len(B)-len(resti)} righe su {len(A)+len(B)} contengono il segnaposto nella finestra')


if __name__ == '__main__':
    main()
