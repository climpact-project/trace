"""LE PROPOSTE DI DEEPSEEK SULLE RIGHE LESSICALI VANNO IN PIATTAFORMA (27/09/2026, decisione del PI).

   PERCHE'. La seconda lettura concorda con i validatori solo al 57% (§63.23), ma il PI ha deciso: meglio avere
   la proposta che no. Le persone la confermano o la correggono, e sono proprio le correzioni i dati con cui
   addestrare un classificatore; senza proposta non c'e' niente da correggere.

   CHE COSA SCRIVE, solo sulle righe lessicali di Urgenda SENZA esito e senza tipo gia' proposto (non tocca
   nessun giudizio umano e non sovrascrive):
     proposto_tipo_citazione, proposto_chi_parla, proposto_proposizione   dalla prima lettura;
     proposto_confidenza   'alta' se le due letture danno lo stesso tipo, altrimenti 'bassa';
     proposto_note         in coda alle note gia' presenti: le due letture, il riferimento, il motivo;
     proposto_lettore      modello e codebook della lettura.
   La piattaforma riempie gia' il modulo dalla proposta (`bozzaIniziale`): chi conferma non riscrive.

   Uso:  .venv/bin/python tools/025_carica_lessicali.py            anteprima, non scrive
         .venv/bin/python tools/025_carica_lessicali.py --scrivi   scrive
"""
import argparse, collections, json, pathlib
QUI = pathlib.Path(__file__).resolve().parent.parent
LETTURE = QUI/'training'/'lessicali_urgenda_deepseek_v2.jsonl'
CAT = {'menzione_in_catena', 'descrittiva', 'sostanziale', 'distinguente', 'critica', 'implicita'}
CHI = {'corte', 'parte', 'interveniente', 'amicus', 'non_determinabile'}
LETTORE = 'DeepSeek V4 Flash 0731, codebook 0.2-pilot con la regola sulle note (26/09/2026), seconda lettura 27/09/2026'
RIF = {'fondazione_urgenda': 'la fondazione Urgenda come soggetto, non la sentenza',
       'soggetto_omonimo': 'la persona, la parte o l\'organizzazione che porta il nome, non la sentenza',
       'indice_o_elenco': 'indice, tavola delle fonti o elenco senza testo', 'omonimo': 'altro significato della parola',
       'non_determinabile': 'non determinabile'}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--scrivi', action='store_true'); ap.add_argument('--caso', default='urgenda')
    ap.add_argument('--etichetta', default='v2', help="la lettura da caricare: per Urgenda la v2, per gli altri casi la prima (etichetta vuota)")
    ap.add_argument('--sovrascrivi', action='store_true',
                    help="01/10/2026: le righe del file prendono la lettura nuova anche se avevano gia' un tipo proposto "
                         "(righe rilette sul testo OCR: la lettura di prima era fatta su una pagina illeggibile)")
    a = ap.parse_args()
    letture = QUI/'training'/f"lessicali_{a.caso}_deepseek{'_' + a.etichetta if a.etichetta else ''}.jsonl"
    lettore = LETTORE if a.caso == 'urgenda' else 'DeepSeek V4 Flash 0731, codebook 0.3-pilot, 28/09/2026'
    from google.cloud import firestore
    db = firestore.Client(project='climpact-drp')
    ds = {}
    for l in open(letture, encoding='utf-8'):
        x = json.loads(l); ds[x['id']] = x
    conti = collections.Counter(); scritture = []
    for d in db.collection('corpus_rows').where(filter=firestore.FieldFilter('caso_citato', '==', a.caso)).stream():
        r = d.to_dict()
        if r.get('proposto_rete') not in ('lessicale', 'entrambe'):
            continue
        if r.get('esito'):
            conti['gia giudicata (non toccata)'] += 1; continue
        if r.get('proposto_tipo_citazione') and not (a.sovrascrivi and d.id in ds):
            conti['tipo gia proposto (non toccata)'] += 1; continue
        x = ds.get(d.id)
        if not x:
            conti['senza lettura'] += 1; continue
        g = x['letture']; p = g[0]
        tipo = p.get('tipo_citazione') if p.get('tipo_citazione') in CAT else ''
        if not tipo:
            conti['lettura illeggibile'] += 1; continue
        tipi = [y.get('tipo_citazione') for y in g]
        concordi = len(set(tipi)) == 1
        nota = f"DeepSeek, due letture: {' / '.join(t or '?' for t in tipi)}."
        if p.get('riferimento') and p['riferimento'] not in ('caso_urgenda', 'caso'):
            nota += f" Attenzione: secondo la lettura qui il nome e' {RIF.get(p['riferimento'], p['riferimento'])}."
        if p.get('motivo'):
            nota += f" Motivo: {' '.join(str(p['motivo']).split())}"
        vecchia = (r.get('proposto_note') or '').strip()
        campi = {'proposto_tipo_citazione': tipo,
                 'proposto_chi_parla': p.get('chi_parla') if p.get('chi_parla') in CHI else '',
                 'proposto_proposizione': ' '.join(str(p.get('proposizione') or '').split()),
                 'proposto_confidenza': 'alta' if concordi else 'bassa',
                 'proposto_note': (vecchia + '\n' + nota) if vecchia else nota,
                 # la data e' quella della lettura della riga (01/10/2026: prima era fissa al 28/09 per tutti i casi tranne Urgenda)
                 'proposto_lettore': lettore if a.caso == 'urgenda' else f"DeepSeek V4 Flash 0731, codebook 0.3-pilot, {'/'.join(reversed(str(x.get('data') or '2026-09-28')[:10].split('-')))}",
                 # la versione che ha letto il tipo (registro: L02 Urgenda, L03 gli altri casi), dal 29/09 scritta qui
                 'provenienza.tipo': 'L02' if a.caso == 'urgenda' else 'L03'}
        scritture.append((d.reference, campi))
        conti['da scrivere'] += 1; conti[f'tipo {tipo}'] += 1; conti['concordi' if concordi else 'discordi'] += 1
    print(json.dumps(dict(conti), ensure_ascii=False, indent=1))
    if scritture:
        print('esempio:', json.dumps(scritture[0][1], ensure_ascii=False)[:600])
    if not a.scrivi:
        print('ANTEPRIMA: niente scritto'); return
    for i in range(0, len(scritture), 400):
        b = db.batch()
        for ref, c in scritture[i:i+400]:
            b.update(ref, c)
        b.commit()
    print(f'scritte {len(scritture)} righe')


if __name__ == '__main__':
    main()
