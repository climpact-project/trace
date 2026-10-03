#!/usr/bin/env python3
"""PORTA I RISULTATI DELLA RICERCA DENTRO LA PIATTAFORMA.

E' l'anello che mancava. La ricerca produce un CSV su disco; il portale
Corpus (corpus.climpact.it) legge da Firestore. Finche' i due non si
parlano, qualcuno deve caricare un file a mano dopo ogni ricerca — e con
dieci casi al mese, quattro persone e un CSV da duemila righe, prima o poi
si carica la versione sbagliata e nessuno se ne accorge.

COSA SCRIVE

  corpus_rows   una riga per occorrenza. L'identificativo e'
                `caso__documento__posizione`, lo stesso che usa il portale:
                rilanciare la ricerca AGGIORNA le righe invece di
                triplicarle.
  corpus_runs   la descrizione di cio' che ha prodotto quelle righe —
                versione del codebook, indice, modello, prefissi, soglia,
                search strategy completa, conteggi, scarti. Senza, fra sei
                mesi due risultati discordanti sullo stesso caso sono
                indistinguibili da due indici diversi.

LE PROPOSTE DELLA MACCHINA VANNO IN CAMPI `proposto_`, MAI SOVRASCRITTI.
Il portale ci scrive accanto i `validato_`. E' da quella coppia che si
ricava l'accordo macchina-umano, cioe' il numero su cui regge la parte
automatica in sede di revisione. Le regole di Firestore lo impongono
(`proposteIntatte()`), quindi non e' una gentilezza: e' un vincolo.

GLI SCARTI SI PUBBLICANO, MA IN UNA COLLEZIONE LORO (`corpus_discarded`).
I candidati che il sistema ha tolto da solo — copie, documenti anteriori
alla decisione citata, punteggio del riordinatore sotto soglia — sono
decisioni prese dal modello e da nessun altro: se restassero su disco, il
controllo del 20% non li vedrebbe mai e una soglia che butta via roba buona
resterebbe invisibile per costruzione.

Ma NON vanno in `corpus_rows`. Provato e corretto il 31 luglio 2026: messi
li', finivano in coda a validare insieme alle citazioni vere, e la tabella
del portale non ha modo di distinguerli — qualcuno li avrebbe confermati
come citazioni trovate, gonfiando proprio il numero che finisce in ICIC
come indice di impatto. Stanno a parte, e il portale dovra' pescarne una
quota per il campione.

CREDENZIALI. Quelle applicative gia' sulla macchina del PI
(~/.config/gcloud/application_default_credentials.json, progetto
climpact-drp). Non si passa da Firebase Auth: qui non c'e' un utente, c'e'
una pipeline.

NON PUBBLICA DA SOLO. La ricerca non chiama questo strumento: si lancia
quando si decide che quel giro e' buono. Un portale in cui le righe
cambiano mentre qualcuno le sta validando non e' utilizzabile.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
PROGETTO = 'climpact-drp'

RETI = ('lessicale', 'semantica', 'entrambe')
CONFIDENZE = ('alta', 'media', 'bassa')


def id_riga(caso, document_id, char_start):
    """LO STESSO IDENTIFICATIVO CHE CALCOLA IL PORTALE, carattere per
    carattere. Se divergesse, ogni ripubblicazione creerebbe righe nuove
    accanto alle vecchie invece di aggiornarle — e il conteggio delle
    citazioni, che e' l'indice di impatto, raddoppierebbe in silenzio."""
    grezzo = f'{caso}__{document_id}__{char_start}'
    return re.sub(r'[/\s]+', '_', grezzo)[:400]


def strato_di(tipo, confidenza, rete):
    """Anche questo deve combaciare: e' la chiave su cui il portale
    stratifica il campione e pondera la precisione."""
    return '|'.join([tipo or 'ignoto', confidenza or 'ignota', rete or 'ignota'])


def integrale(tipo, confidenza, rete):
    """Le righe da verificare TUTTE, non a campione."""
    return tipo == 'implicita' or confidenza == 'bassa' or rete == 'semantica'


def documento(r, caso, scartata=''):
    pagina = int(r['pagina']) if str(r.get('pagina', '')).strip().isdigit() else 0
    inizio = int(r['char_start']) if str(r.get('char_start', '')).strip().lstrip('-').isdigit() else 0
    tipo = r.get('tipo_citazione') or ''
    conf = r.get('confidenza') or ''
    rete = r.get('rete') or ''
    d = {
        'caso_citato': caso,
        'case_id': r.get('case_id', ''), 'case_name': r.get('case_name', ''),
        'giurisdizioni': r.get('giurisdizioni', ''),
        'document_id': r.get('document_id', ''),
        'tipo_atto': r.get('tipo_atto', ''),
        'tipo_atto_sabin': r.get('tipo_atto_sabin', ''),
        'data': r.get('data', ''), 'url_documento': r.get('url_documento', ''),
        'file': r.get('file', ''),
        # IL PERCORSO DEL PDF, ACCANTO A QUELLO DEL MARKDOWN.
        # `file` punta al testo estratto: chiederlo al server come PDF da
        # 404, e il portale ripiega sul lettore di serie con l'avviso
        # "In-app preview unavailable". Verificato che il servizio serve
        # `documents/<caso>/<documento>.pdf` con 200 application/pdf.
        'file_pdf': re.sub(r'\.md$', '.pdf',
                           re.sub(r'^markdown/', 'documents/', r.get('file', ''))),
        'char_start': inizio,
        # ── le proposte della macchina, mai sovrascritte ──────────────
        'proposto_pagina': pagina,
        'proposto_forma_trovata': r.get('forma_trovata', ''),
        'proposto_citazione_testuale': r.get('citazione_testuale', ''),
        # LA FINESTRA DI LETTURA — la pagina INTERA in cui cade
        # l'occorrenza, note comprese. Non e' ridondante rispetto al PDF:
        # e' cio' che permette di stabilire chi parla restando nella
        # tabella. Negli atti giuridici la nota che dice a chi si
        # attribuisce un principio sta spesso a pie' di pagina, lontana
        # dalla frase che sostiene: con una finestra corta resterebbe
        # fuori, e si classificherebbe come richiamo implicito un passaggio
        # che cita apertamente qualcun altro.
        # Media 3.334 caratteri, massimo 12.344: molto sotto il limite di
        # un megabyte per documento di Firestore.
        'finestra_pagina': r.get('finestra_pagina', ''),
        'proposto_tipo_citazione': tipo,
        'proposto_chi_parla': r.get('chi_parla', ''),
        'proposto_annidata': str(r.get('annidata', '')).lower() == 'true',
        'proposto_proposizione': r.get('proposizione_sostenuta', ''),
        'proposto_confidenza': conf,
        'proposto_rete': rete,
        'proposto_note': r.get('note', ''),
        # ── le tre dimensioni precompilate ───────────────────────────
        # Stessa logica: la proposta sta in `proposto_`, la correzione del
        # lettore andra' accanto. Il portale non le mostrava ancora perche'
        # non esistevano: da qui in poi ci sono.
        'proposto_posizione': r.get('posizione_auto', ''),
        'proposto_sede': r.get('sede_auto', ''),
        'proposto_chi_cita': r.get('chi_cita_auto', ''),
        'dimensioni_confidenza': r.get('dimensioni_confidenza', ''),
        # ── come e' stata trovata ────────────────────────────────────
        'sonda': r.get('sonda', ''),
        'punteggio': _num(r.get('punteggio')),
        'punteggio_riordino': _num(r.get('punteggio_riordino')),
        'punteggio_escluse': _num(r.get('punteggio_escluse')),
        'margine': _num(r.get('margine')),
        'sospetto': r.get('sospetto', ''),
        'copie': int(r['copie']) if str(r.get('copie', '')).strip().isdigit() else 1,
        'anteriore': (r.get('anteriore') or '') == 'si',
        'codebook_versione': r.get('codebook_versione', ''),
        # ── stato della validazione ──────────────────────────────────
        'esito': None, 'validato_da': None, 'validato_il': None,
        'nel_campione': False, 'integrale': integrale(tipo, conf, rete),
        'doppia_codifica': False,
        'strato': strato_di(tipo, conf, rete),
        'scartato': bool(scartata),
        'motivo_scarto': scartata,
    }
    return d


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def leggi(percorso: Path):
    if not percorso.exists():
        return []
    with percorso.open(encoding='utf-8') as f:
        return list(csv.DictReader(f))


def provenienza(caso: str):
    """Tutto cio' che ha prodotto queste righe, in un posto solo."""
    man = {}
    f = HERE / 'index' / 'manifesto.json'
    if f.exists():
        man = json.loads(f.read_text(encoding='utf-8'))
    cb = HERE / 'codebook' / 'citazioni.yaml'
    testo_cb = cb.read_text(encoding='utf-8') if cb.exists() else ''
    m = re.search(r'^versione:\s*(.+)$', testo_cb, re.M)
    ma = re.search(r'^approvato_da:\s*([^#\n]+)', testo_cb, re.M)
    caso_file = HERE / 'cited-cases' / f'{caso}.yaml'
    return {
        'caso_citato': caso,
        'codebook_versione': m.group(1).strip() if m else '',
        'codebook_approvato_da': (ma.group(1).strip() if ma else 'null'),
        'codebook_approvato': bool(ma and ma.group(1).strip() not in ('null', '', 'None')),
        'indice': {
            'modello': man.get('modello', ''),
            'costruito': man.get('costruito', ''),
            'frammenti': man.get('frammenti', 0),
            'impronta_pesi': man.get('impronta_pesi', ''),
            'impronta_frammenti': man.get('impronta_frammenti', ''),
            'prefisso_passaggio': man.get('prefisso_passaggio', ''),
            'prefisso_domanda': man.get('prefisso_domanda', ''),
            'prefisso_domanda_nota': man.get('prefisso_domanda_nota', ''),
            'parametri_frammentazione': man.get('parametri_frammentazione', {}),
        },
        # LA SEARCH STRATEGY PER INTERO, formulazioni escluse comprese: chi
        # rifa' la ricerca deve poter vedere non solo cosa abbiamo cercato,
        # ma anche cosa abbiamo deciso di NON far contare.
        'search_strategy': (caso_file.read_text(encoding='utf-8')
                            if caso_file.exists() else ''),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--caso', required=True)
    ap.add_argument('--csv', default='')
    ap.add_argument('--prova', action='store_true',
                    help='non scrive niente: dice solo cosa scriverebbe')
    args = ap.parse_args()

    base = Path(args.csv) if args.csv else HERE / 'index' / f'candidati_{args.caso}.csv'
    if not base.exists():
        print(f'Manca {base}. Lancia prima:  tools/016_cerca.py --caso {args.caso}')
        return 1
    scarti_f = base.with_name(base.stem + '.SCARTI.csv')

    righe = leggi(base)
    scarti = leggi(scarti_f)
    print(f'righe    : {len(righe):,}   ({base.name})')
    print(f'scarti   : {len(scarti):,}   ({scarti_f.name if scarti else "assente"})')

    # ── DUE CAMPI CHE DECIDONO COME SI LEGGE LA CODA ──────────────────
    #
    # `corroborazione` — il criterio che il metodo propone da sempre (§14,
    # terzo criterio per la categoria `implicita`) e che nessuno aveva mai
    # costruito: se un documento nomina il caso citato DA QUALCHE PARTE, una
    # riformulazione non attribuita al suo interno e' plausibilmente
    # collegata; se il caso non lo nomina mai, molto meno.
    # Non e' un'opinione della macchina: e' un fatto sul documento, e lo sa
    # gia' la rete lessicale, che sul nome e' esaustiva. Va scritto sulla
    # riga perche' chi valida lo legga MENTRE giudica — misurato il
    # 2026-09-03 sui primi 19 giudizi umani, tutti caduti senza saperlo nel
    # quarto non corroborato, quello con riordino mediano 0,221 contro 0,511.
    #
    # `ordine` — un numero casuale stabile. L'ordinamento della coda era per
    # identificativo di documento, cioe' in pratica ALFABETICO per nome del
    # caso: non e' mischiato, e' raggruppato. I primi tre pareri consultivi
    # di corti internazionali cominciano tutti per «A Request...»/«Request...»
    # e occupavano da soli l'inizio della coda. Chi apriva il portale
    # passava la prima sessione sul materiale peggiore senza che nulla glielo
    # dicesse, e quello che misurava su quelle righe non valeva per il resto.
    # Con un ordine casuale le prime cinquanta righe sono un campione vero.
    import random as _random
    cita_doc = {r['document_id'] for r in righe if r.get('rete') in ('lessicale', 'entrambe')}
    cita_caso = {r['case_id'] for r in righe if r.get('rete') in ('lessicale', 'entrambe')}

    def corroborazione(r):
        if r.get('rete') in ('lessicale', 'entrambe'):
            return 'nome_presente'
        if r.get('document_id') in cita_doc:
            return 'documento_lo_cita'
        if r.get('case_id') in cita_caso:
            return 'caso_lo_cita'
        return 'mai_nominato'

    docs, scartati, rifiutate, collisioni = {}, {}, [], []
    for origine, elenco in ((''.strip(), righe), ('scarto', scarti)):
        for i, r in enumerate(elenco):
            problemi = []
            if not r.get('document_id'):
                problemi.append('manca document_id')
            if not r.get('citazione_testuale'):
                problemi.append('manca citazione_testuale')
            if not str(r.get('pagina', '')).strip().isdigit():
                problemi.append(f"pagina non valida: {r.get('pagina')!r}")
            if r.get('rete') and r['rete'] not in RETI:
                problemi.append(f"rete sconosciuta: {r['rete']!r}")
            if r.get('confidenza') and r['confidenza'] not in CONFIDENZE:
                problemi.append(f"confidenza sconosciuta: {r['confidenza']!r}")
            if problemi:
                rifiutate.append((i + 2, origine or 'righe', problemi))
                continue
            d = documento(r, args.caso, r.get('motivo_scarto', '') if origine else '')
            d['corroborazione'] = corroborazione(r)
            # Il seme e' l'identificativo della riga, non l'orologio: due
            # pubblicazioni della stessa riga danno lo stesso numero, quindi
            # la coda non si rimescola sotto le mani di chi sta lavorando.
            rid = id_riga(args.caso, d['document_id'], d['char_start'])
            d['ordine'] = _random.Random(rid).random()
            # UNA RIGA TENUTA NON VIENE MAI SOPRAFFATTA DA UNO SCARTO.
            # Stesso documento e stessa posizione possono comparire in
            # entrambi i file (una riga trovata da tutte e due le reti, la
            # cui variante semantica e' finita sotto soglia): senza questa
            # riga lo scarto sovrascriverebbe la riga buona, e nel portale
            # sparirebbe una citazione vera marcandola come scartata.
            if origine:
                # Uno scarto che coincide con una riga tenuta non e' uno
                # scarto: la riga buona vince e lo scarto si lascia cadere.
                if rid in docs:
                    collisioni.append(rid)
                    continue
                scartati[rid] = d
            else:
                docs[rid] = d

    # UN'IMPORTAZIONE CHE SCARTA IN SILENZIO E' PEGGIO DI UNA CHE FALLISCE.
    if rifiutate:
        print(f'\nRIFIUTATE: {len(rifiutate)}')
        for n, dove, p in rifiutate[:10]:
            print(f'  {dove} riga {n}: {"; ".join(p)}')
        if len(rifiutate) > 10:
            print(f'  … e altre {len(rifiutate) - 10}')

    if collisioni:
        print(f'\n{len(collisioni)} scarti coincidevano con righe tenute: '
              'ha prevalso la riga tenuta')

    prov = provenienza(args.caso)
    print(f"\nrighe da validare     : {len(docs):,}")
    print(f"scarti (a parte)      : {len(scartati):,}")
    print(f"codebook              : {prov['codebook_versione']} "
          f"(approvato da {prov['codebook_approvato_da']})")
    print(f"indice                : {prov['indice']['modello']} "
          f"{prov['indice']['frammenti']:,} frammenti "
          f"del {prov['indice']['costruito'][:10]}")
    if args.prova:
        print('\n--prova: non e stato scritto niente.')
        return 0

    try:
        from google.cloud import firestore
    except ImportError:
        print('\nManca la libreria. Installala con:')
        print('  ./.venv/bin/pip install google-cloud-firestore')
        return 1
    db = firestore.Client(project=PROGETTO)

    esecuzione = f"{args.caso}__{prov['indice']['costruito'][:19].replace(':', '')}"
    db.collection('corpus_runs').document(esecuzione).set({
        **prov,
        'righe': len(righe), 'scarti': len(scarti), 'rifiutate': len(rifiutate),
        'quando': firestore.SERVER_TIMESTAMP,
        'origine': 'pipeline',
    })

    # ── IL LAVORO UMANO NON SI TOCCA MAI ─────────────────────────────
    #
    # Difetto trovato il 3 settembre 2026, prima che facesse danno: la riga
    # costruita da questo strumento contiene ANCHE lo stato della
    # validazione azzerato (`esito: None`, `validato_da: None`, e cosi'
    # via), e la scrittura e' un `set(..., merge=True)`. `merge=True`
    # conserva i campi ASSENTI dal dizionario, non quelli presenti: un
    # campo presente e messo a None sovrascrive. Conseguenza: rilanciare la
    # ricerca su un caso GIA' VALIDATO azzerava il giudizio dei
    # ricercatori, l'appartenenza al campione e l'assegnazione del lavoro.
    # Silenzioso, irreversibile, e sarebbe scattato esattamente al secondo
    # giro sul primo caso lavorato a mano — cioe' nel momento di massimo
    # danno possibile.
    #
    # Rimedio: questi campi si scrivono SOLO alla creazione di una riga
    # nuova. Su una riga che esiste gia' vengono tolti dal carico, quindi
    # `merge=True` li lascia come sono. Le proposte della macchina
    # (`proposto_*`, punteggi, margini) continuano ad aggiornarsi: sono sue
    # e devono seguire l'ultima esecuzione. Anche `creato_il` resta quello
    # della prima volta: e' la data di creazione della riga, e riscriverla
    # a ogni pubblicazione la trasformerebbe in «ultima pubblicazione»,
    # perdendo il dato di quando quella riga e' comparsa. Chi ha prodotto
    # le proposte correnti lo dice `esecuzione_id`, che invece si aggiorna.
    CAMPI_UMANI = ('esito', 'validato_da', 'validato_il', 'nel_campione',
                   'doppia_codifica', 'assegnato_a')
    esistenti = {d.id for d in db.collection('corpus_rows')
                 .where(filter=firestore.FieldFilter('caso_citato', '==', args.caso))
                 .select([]).stream()}
    print(f'righe gia in banca dati per questo caso: {len(esistenti):,} '
          '(su queste lo stato della validazione non viene toccato)')

    # A LOTTI DI 450: il limite di Firestore e' 500 operazioni per lotto, e
    # sforarlo fa fallire l'intero lotto, non la singola riga.
    def versa(collezione, voci, etichetta, proteggi=False):
        n = 0
        elenco = list(voci.items())
        for i in range(0, len(elenco), 450):
            lotto = db.batch()
            for rid, d in elenco[i:i + 450]:
                extra = {'esecuzione_id': esecuzione}
                if proteggi and rid in esistenti:
                    d = {k: v for k, v in d.items() if k not in CAMPI_UMANI}
                else:
                    extra['creato_il'] = firestore.SERVER_TIMESTAMP
                lotto.set(db.collection(collezione).document(rid),
                          {**d, **extra}, merge=True)
            lotto.commit()
            n += len(elenco[i:i + 450])
            print(f'  {etichetta} {n:,}/{len(elenco):,}', flush=True)
        return n

    scritte = versa('corpus_rows', docs, 'righe', proteggi=True)
    versa('corpus_discarded', scartati, 'scarti')

    # RIPULISCE GLI SCARTI FINITI PER ERRORE FRA LE RIGHE DA VALIDARE.
    # Serve una volta sola, ma resta: se qualcuno ripubblicasse con una
    # versione vecchia dello strumento, la coda tornerebbe sporca.
    vecchi = [d.id for d in db.collection('corpus_rows')
              .where(filter=firestore.FieldFilter('caso_citato', '==', args.caso))
              .where(filter=firestore.FieldFilter('scartato', '==', True))
              .stream()]
    for i in range(0, len(vecchi), 450):
        lotto = db.batch()
        for rid in vecchi[i:i + 450]:
            lotto.delete(db.collection('corpus_rows').document(rid))
        lotto.commit()
    if vecchi:
        print(f'  tolti {len(vecchi):,} scarti dalla coda di validazione')

    # IL CONTROLLO DEGLI SCARTI, SEMPRE (decisione del PI, 23/09/2026): una
    # parte a caso di cio' che la macchina ha scartato entra nella coda senza
    # segni, e il cruscotto conta quante citazioni vere c'erano. Vedi
    # `038_controllo_scarti.py`.
    _m_controllo_scarti = __import__('038_controllo_scarti')
    aggiungi_controllo = _m_controllo_scarti.aggiungi_controllo
    aggiungi_controllo(db, args.caso)

    print(f'\nscritte {scritte:,} righe in corpus_rows')
    print(f'scritti {len(scartati):,} scarti in corpus_discarded')
    print(f'esecuzione registrata in corpus_runs: {esecuzione}')
    print('Il portale le vede su corpus.climpact.it')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
