#!/usr/bin/env python3
"""DAL TESTO ESTRATTO AL MARKDOWN ANNOTATO.

COSA FA E COSA NON FA. Non estrae niente: il testo c'e' gia' in `text/`,
un `.txt` per ogni PDF, e porta gia' i segni di pagina nella forma
`<!-- page N -->`. Questo script prende quel testo, gli mette in testa i
metadati presi da `metadata.csv`, e lo salva in `markdown/` con la stessa
struttura di cartelle. Il testo NON viene toccato: nemmeno uno spazio.

PERCHE' I METADATI IN TESTA A OGNI FILE E NON IN UNA TABELLA A PARTE.
Chi legge un passaggio — una persona o un modello — deve sapere subito di
che caso si tratta, in che atto e davanti a quale corte. Se quei dati
stanno in un'altra tabella, il contesto va ricostruito ogni volta con
un'altra lettura, e quando lo strumento che legge ha una finestra
limitata quella lettura in piu' e' proprio quella che non si fa. Il
riassunto del caso si ripete in tutti i documenti dello stesso caso: costa
qualche kilobyte e toglie un intero passaggio.

IL TIPO DI ATTO NON E' UN CAMPO DEL CSV. `Document Variant` ha un solo
valore utile e non serve a niente. Nel Climate Case Chart il tipo sta in
CODA AL TITOLO, dopo un trattino: "... - amicus brief", "... - order".
Qui viene estratto e ricondotto a un vocabolario chiuso (vedi FAMIGLIE):
84 valori grezzi non si raggruppano, dodici si.

Il valore grezzo resta comunque nel front matter accanto a quello
normalizzato: la normalizzazione e' un'interpretazione, e chi la vuole
rifare diversamente deve poterlo fare senza tornare al CSV.
"""

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
TEXT = HERE / 'text'
DOCS = HERE / 'documents'
OUT = HERE / 'markdown'

# Il vocabolario chiuso. La chiave e' la famiglia, i valori sono i finali
# di titolo che ci ricadono. L'ordine conta: si prende la prima famiglia
# che corrisponde, quindi le voci piu' specifiche stanno prima.
FAMIGLIE = [
    ('decisione',     ['judgment', 'decision', 'opinion', 'ruling', 'award', 'sentence']),
    ('ordinanza',     ['order', 'injunction', 'writ']),
    ('atto introduttivo', ['complaint', 'petition', 'application', 'claim', 'request',
                           'petition for review', 'notice of appeal', 'appeal']),
    ('istanza',       ['motion', 'motion to dismiss', 'motion for summary judgment',
                       'motion to intervene', 'amicus motion']),
    ('amicus',        ['amicus brief', 'amicus curiae brief', 'amici brief']),
    ('memoria',       ['brief', 'memorandum', 'submission', 'statement']),
    ('replica',       ['reply', 'response', 'opposition', 'rejoinder', 'answer']),
    ('avviso',        ['notice', 'notification']),
    ('lettera',       ['letter', 'correspondence']),
    ('relazione',     ['report', 'status report', 'expert report', 'declaration', 'affidavit']),
    ('comunicato',    ['press release']),
    # Aggiunte dopo aver guardato cosa finiva in 'altro' sul caso
    # campione: erano il 21% di quel caso, e quasi tutto era materiale
    # probatorio o di verbale — categorie vere, non residui.
    ('prova',         ['exhibit', 'appendix', 'annex', 'attachment', 'evidence']),
    ('verbale',       ['transcript', 'minutes', 'hearing transcript']),
    ('opposizione',   ['objection', 'objections']),
]


def famiglia(coda: str) -> str:
    """La famiglia del tipo di atto, o 'altro' se non riconosciuto.

    'altro' e' un esito onesto e va lasciato visibile: raggruppare a forza
    un atto che non si e' capito lo farebbe sparire dentro una categoria
    sbagliata, ed e' peggio che vederlo in un mucchio chiamato 'altro'."""
    c = (coda or '').strip().lower()
    if not c:
        return 'non indicato'
    for nome, voci in FAMIGLIE:
        if c in voci:
            return nome
    # CORRISPONDENZA PARZIALE: VINCE LA PIU' LUNGA, non la prima in elenco.
    #
    # QUI C'ERA UN ERRORE MISURATO. Prima si scorreva FAMIGLIE in ordine e
    # si prendeva la prima corrispondenza: 'motion for summary judgment 1'
    # incontrava 'judgment' (decisione) prima di 'motion for summary
    # judgment' (istanza), e un'istanza veniva classificata come decisione.
    # Sono i 105 casi in cui titolo e nome file "discordavano" — non
    # discordavano i dati, sbagliavo io.
    # La regola giusta e' che la formula piu' specifica batte quella
    # generica, e la specificita' si misura in lunghezza.
    best = None
    for nome, voci in FAMIGLIE:
        for v in voci:
            if v in c and (best is None or len(v) > best[0]):
                best = (len(v), nome)
    return best[1] if best else 'altro'


def coda_titolo(titolo: str) -> str:
    """Il pezzo dopo l'ultimo trattino, che nel CCC e' il tipo di atto."""
    parti = re.split(r'\s+-\s+', titolo or '')
    return parti[-1].strip() if len(parti) > 1 else ''


def coda_url(url: str) -> str:
    """IL RIPIEGO: il tipo di atto letto dal nome del file di origine.

    Un titolo su cinque non ha il trattino, e per quelli il tipo sarebbe
    'non indicato'. Ma l'indirizzo del PDF sul sito del Sabin finisce quasi
    sempre con il tipo — `..._status-report.pdf`, `..._complaint.pdf`,
    `..._order.pdf`: e' la loro convenzione di archiviazione, ed e' un
    secondo testimone indipendente dal titolo.
    Si prende solo l'ultimo segmento dopo il trattino basso, perche' prima
    ci sono data e numero di ruolo."""
    m = re.search(r'/([^/]+)\.pdf(?:$|\?)', url or '', re.I)
    if not m:
        return ''
    nome = m.group(1)
    pezzo = nome.rsplit('_', 1)[-1] if '_' in nome else nome
    return pezzo.replace('-', ' ').strip()


def coda_intestazione(txt: Path) -> str:
    """IL TERZO TESTIMONE: il documento che dichiara cosa e'.

    Un atto giudiziario porta la propria natura scritta nell'intestazione
    della prima pagina — "MOTION TO DISMISS", "ORDER", "COMPLAINT" — quasi
    sempre in maiuscolo e su una riga sua. E' la fonte piu' autorevole
    delle tre, perche' viene da chi l'atto l'ha depositato e non da chi lo
    ha catalogato dopo; ma e' anche l'unica che costa una lettura, quindi
    si interpella solo quando titolo e nome del file hanno taciuto.

    Si guarda SOLO la prima pagina: piu' avanti nel testo le stesse parole
    compaiono nei riferimenti ad altri atti ("in its motion to dismiss, the
    defendant argued...") e classificherebbero il documento con il nome di
    un altro.
    """
    try:
        testa = txt.read_text(encoding='utf-8', errors='replace')[:6000]
    except OSError:
        return ''
    # Ci si ferma al secondo segno di pagina: oltre non e' piu' intestazione.
    taglio = re.search(r'<!--\s*page\s+2\s*-->', testa)
    if taglio:
        testa = testa[:taglio.start()]
    # Le righe brevi e in maiuscolo sono le candidate: nell'intestazione di
    # un atto il tipo sta su una riga sua, non dentro un periodo.
    candidate = [l.strip() for l in testa.split('\n')
                 if 3 < len(l.strip()) <= 70 and l.strip() == l.strip().upper()]
    for riga in candidate:
        pulita = re.sub(r'[^A-Za-z ]+', ' ', riga).strip().lower()
        if famiglia(pulita) not in ('non indicato', 'altro'):
            return pulita
    return ''


def yaml_scalar(v) -> str:
    """Uno scalare YAML sicuro.

    Si virgoletta SEMPRE e si raddoppiano gli apici interni: i titoli di
    causa contengono due punti, virgole, parentesi e apostrofi — cioe' tutta
    la punteggiatura che rompe un YAML scritto a mano. Un front matter
    malformato non da' errore: viene semplicemente ignorato, e i metadati
    spariscono senza che nessuno se ne accorga."""
    s = '' if v is None else str(v)
    # GLI STESSI SEPARATORI CHE ROMPONO I BLOCCHI ROMPONO ANCHE GLI SCALARI.
    #
    # La correzione fatta su `blocco()` copre i campi multiriga (i riassunti).
    # Ma un a capo anomalo dentro uno scalare — `stato`, che contiene la
    # descrizione libera dell'ultimo evento e viene da celle di Excel — lo
    # spezza allo stesso modo: qui si normalizzavano `\r` e `\n` e nient'altro.
    # Misurato: 66 documenti avevano il campo `stato` corrotto.
    #
    # Negli scalari il separatore diventa uno SPAZIO, non un a capo: un
    # valore su una riga sola deve restare su una riga sola.
    for sep in ('\r\n', '\r', '\n', '\u2028', '\u2029', '\x0b', '\x0c', '\x85'):
        s = s.replace(sep, ' ')
    s = s.replace('_x000D_', ' ')
    s = ' '.join(s.split())
    return "'" + s.replace("'", "''") + "'"


def blocco(v) -> str:
    """Il riassunto del caso, che e' lungo e va a capo: blocco letterale.

    DUE INSIDIE, ENTRAMBE INCONTRATE SUL CORPUS VERO.

    1. IL RITORNO A CAPO SOLITARIO. Qui si normalizzava il solo `\r\n`; un
       `\r` da solo — che i CSV esportati da Excel contengono — sopravviveva
       DENTRO la riga. Python lo considera un carattere qualunque e scrive
       tutto su una riga sola; YAML invece lo legge come un'interruzione, e
       cio' che segue si ritrova a colonna 1, fuori dal blocco indentato.
       Il front matter si rompe e il documento sparisce.

    2. `_x000D_`. E' la forma in cui Excel scrive un a capo dentro una cella:
       non e' un carattere di controllo, sono sette lettere. Restava nel
       testo, e comparendo a inizio riga faceva fallire l'analisi.

    Misurato: 13 documenti su 16.791 (tre fascicoli brasiliani) non venivano
    scritti in forma leggibile e non comparivano in nessuna ricerca. E' il
    caso descritto al paragrafo 3.3: un front matter malformato non da'
    errore, viene ignorato in silenzio."""
    s = ('' if v is None else str(v))
    # TUTTE le forme di a capo. Oltre a `\r`, il corpus contiene `\u2028`
    # (separatore di riga Unicode): Python non lo considera un a capo, YAML
    # si'. Restando dentro la riga, manda fuori dal blocco rientrato tutto
    # cio' che lo segue — e il documento sparisce senza errore.
    for sep in ('\r\n', '\r', '\u2028', '\u2029', '\x0b', '\x0c', '\x85'):
        s = s.replace(sep, '\n')
    s = s.replace('_x000D_', '')
    s = s.strip()
    if not s:
        return "''"
    # Rientro a quattro spazi ESATTI: in un blocco letterale il rientro lo
    # fissa la prima riga, e una riga successiva meno rientrata finisce fuori
    # dal blocco. Togliendo prima gli spazi iniziali, ogni riga entra allo
    # stesso livello qualunque cosa arrivasse dal CSV.
    righe = [l.strip() for l in s.split('\n')]
    return '|\n' + '\n'.join(('    ' + l if l else '') for l in righe)


def impronta(p: Path) -> str:
    """L'impronta del PDF di origine, calcolata solo se non gia' nota.

    Il registro dello scarico la porta gia' per ogni file: ricalcolarla
    vorrebbe dire rileggere 16 GB senza motivo. Questa funzione resta come
    ripiego per i file che nel registro non ci fossero.

    A che serve l'impronta: sapere, fra un anno, se il documento su cui si
    e' lavorato e' ancora quello. Se la fonte sostituisce un file, i numeri
    di pagina possono non corrispondere piu', e questo dev'essere
    rilevabile invece che silenzioso."""
    if not p or not p.exists():
        return ''
    h = hashlib.sha256()
    with p.open('rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


def indice_manifest():
    """Percorso del PDF -> Document ID, dal registro dello scarico.

    QUESTA E' LA CHIAVE GIUSTA, ed e' stata trovata dopo due tentativi
    sbagliati. Il nome del file NON basta: e' troncato a una sessantina di
    caratteri e il troncamento asporta proprio il suffisso che rende
    univoco l'identificativo. Agganciando per nome si copriva il 43%;
    aggiungendo un confronto per prefisso dentro il caso si arrivava al
    73%, con il 14% ambiguo — e i documenti persi non erano distribuiti a
    caso, perche' il troncamento colpisce i titoli lunghi, che nella fonte
    sono tipicamente le sintesi redazionali delle decisioni.

    `manifest.jsonl` e' il registro prodotto durante lo scarico: per ogni
    file scaricato riporta l'indirizzo di origine, il percorso locale, i
    documenti che quel file serve e la sua impronta. E' una mappatura
    esatta, non una somiglianza. Copertura misurata: 16.791 su 16.791.

    Un file puo' servire piu' documenti (un atto depositato in piu'
    fascicoli): si registrano tutti, e il primo e' quello che porta i
    metadati principali.
    """
    m = {}
    with (HERE / 'manifest.jsonl').open(encoding='utf-8') as f:
        for riga in f:
            try:
                r = json.loads(riga)
            except ValueError:
                continue
            if r.get('path') and r.get('docs'):
                m[r['path']] = r
    return m


def indice_metadati():
    """metadata.csv indicizzato per Document ID."""
    idx = {}
    with (HERE / 'metadata.csv').open(encoding='utf-8') as f:
        for r in csv.DictReader(f):
            did = (r.get('Document ID') or '').strip()
            if did:
                idx[did] = r
    return idx


def front_matter(r: dict, txt: Path, pdf: Path, pagine: int, sha: str = '') -> str:
    # L'ORDINE DELLE FONTI DEL TIPO DI ATTO.
    #
    # LA PRIMA E' UNA COLONNA DEL CSV, e per un po' non l'avevo vista:
    # `Document Type` e' valorizzata al 99,9% con un vocabolario gia'
    # pulito. E' la classificazione ufficiale del Sabin, quindi e' anche
    # piu' difendibile di qualunque euristica nostra: se un revisore chiede
    # come sono stati classificati gli atti, la risposta e' "come li ha
    # classificati la fonte".
    #
    # MA HA UN DIFETTO DA 4.079 RIGHE. In quelle, `Document Type` contiene
    # 'Filing Year For Action' — un valore finito nella colonna sbagliata a
    # monte, e la stessa stringa compare anche in `Document Summary`. Non e'
    # un tipo di atto e va trattato come un buco, non come una categoria.
    #
    # Per quel quarto di corpus restano le tre fonti misurate: nome del
    # file (91,7%), titolo (71,5%), intestazione della prima pagina.
    # Misurato su tutti i 17.223 documenti: il nome del file da' il tipo nel
    # 91,7% dei casi, il titolo nel 71,5%, e dove ci sono entrambi
    # concordano nel 99,1%. Quindi si parte dal nome del file.
    # Terzo livello: il documento stesso. Un atto giudiziario dichiara la
    # propria natura nell'intestazione della prima pagina, ed e' la fonte
    # piu' autorevole delle tre — ma anche la piu' cara da leggere, quindi
    # si usa solo quando le altre due non hanno risposto.
    # DUE ETICHETTE, E NON SE NE SCEGLIE UNA.
    #
    # `Document Type` e' la classificazione ufficiale del Sabin ed e'
    # valorizzata al 99,9%. Ma su parecchi casi e' un'etichetta DI CASO e
    # non di documento: in `juliana-v-united-states_522f` tutti e 151 i
    # documenti — decisioni, relazioni, prove — risultano 'Motion'.
    # Verificato, non supposto.
    #
    # La classificazione derivata dal singolo documento (nome del file,
    # titolo, intestazione della prima pagina) e' piu' fine ma e' nostra.
    # Tenerle entrambe permette a chi analizza di scegliere, e soprattutto
    # rende VISIBILE il disaccordo, che e' un'informazione: dove le due
    # divergono, la classificazione e' incerta e va guardata.
    ufficiale = (r.get('Document Type') or '').strip()
    if ufficiale.lower() == 'filing year for action':
        ufficiale = ''          # valore finito nella colonna sbagliata a monte

    coda = coda_url(r.get('Document Content URL', ''))
    fonte = 'nome file'
    if famiglia(coda) in ('non indicato', 'altro'):
        alt = coda_titolo(r.get('Document Title', ''))
        if famiglia(alt) not in ('non indicato', 'altro'):
            coda, fonte = alt, 'titolo'
    if famiglia(coda) in ('non indicato', 'altro'):
        alt = coda_intestazione(txt)
        if famiglia(alt) not in ('non indicato', 'altro'):
            coda, fonte = alt, 'intestazione'
    if famiglia(coda) in ('non indicato', 'altro') and ufficiale:
        coda, fonte = ufficiale, 'csv'

    fam_uff = famiglia(ufficiale) if ufficiale else 'non indicato'
    fam_der = famiglia(coda)
    concorde = ('si' if fam_uff == fam_der
                else ('non confrontabile' if fam_uff == 'non indicato' else 'no'))
    if famiglia(coda) in ('non indicato', 'altro'):
        alt = coda_titolo(r.get('Document Title', ''))
        if famiglia(alt) not in ('non indicato', 'altro'):
            coda, fonte = alt, 'titolo'
    if famiglia(coda) in ('non indicato', 'altro'):
        alt = coda_intestazione(txt)
        if famiglia(alt) not in ('non indicato', 'altro'):
            coda, fonte = alt, 'intestazione'
    campi = [
        ('document_id',    yaml_scalar(r.get('Document ID'))),
        ('document_title', yaml_scalar(r.get('Document Title'))),
        ('tipo_atto',      yaml_scalar(fam_der)),
        ('tipo_atto_sabin', yaml_scalar(ufficiale)),
        ('tipo_atto_concorde', yaml_scalar(concorde)),
        ('tipo_atto_fonte', yaml_scalar(coda)),
        # Da dove viene il tipo: dal titolo o dal nome del file. Serve a
        # sapere quanta parte della classificazione poggia sul ripiego.
        ('tipo_atto_origine', yaml_scalar(fonte)),
        ('case_id',        yaml_scalar(r.get('Case ID'))),
        ('case_name',      yaml_scalar(r.get('Case Name'))),
        ('case_name_originale', yaml_scalar(r.get('Non-English Case Name'))),
        ('numero_causa',   yaml_scalar(r.get('Case Number'))),
        ('giurisdizioni',  yaml_scalar(r.get('Jurisdictions'))),
        ('geografie',      yaml_scalar(r.get('Geographies'))),
        ('stato',          yaml_scalar(r.get('Status'))),
        ('categorie',      yaml_scalar(r.get('Case Categories'))),
        ('leggi',          yaml_scalar(r.get('Principal Laws'))),
        ('data_deposito',  yaml_scalar(r.get('Document Filing Date'))),
        ('anno_avvio',     yaml_scalar(r.get('Case Filing Year for Action'))),
        ('lingue',         yaml_scalar(r.get('Language(s)'))),
        ('url_origine',    yaml_scalar(r.get('Document Content URL'))),
        ('pagine',         str(pagine)),
        ('file_testo',     yaml_scalar(str(txt.relative_to(HERE)))),
        ('file_pdf',       yaml_scalar(str(pdf.relative_to(HERE)) if pdf and pdf.exists() else '')),
        # Dal registro dello scarico quando c'e'; ricalcolata solo se manca.
        ('sha256_pdf',     yaml_scalar(sha or impronta(pdf))),
        # Le pagine sul sito del Sabin: sono quelle che si aprono per il
        # controllo a mano, e nel CSV sono valorizzate al 100%.
        ('url_documento',  yaml_scalar(r.get('Document URL'))),
        ('url_caso',       yaml_scalar(r.get('Case URL'))),
        ('riassunto_caso', blocco(r.get('Case Summary'))),
        ('riassunto_documento', blocco(
            '' if (r.get('Document Summary') or '').strip() == 'Filing Year For Action'
            else r.get('Document Summary'))),
        # La questione giuridica formulata dal Sabin. C'e' solo sul 22%
        # dei documenti, ma dove c'e' e' una descrizione sostanziale gia'
        # scritta: come sonda per la ricerca semantica vale piu' di una
        # frase inventata da noi.
        ('questione',      blocco(r.get('At Issue'))),
    ]
    return '---\n' + '\n'.join(f'{k}: {v}' for k, v in campi) + '\n---\n\n'


def main(argv):
    solo_caso = argv[1] if len(argv) > 1 else None
    man = indice_manifest()
    idx = indice_metadati()
    OUT.mkdir(exist_ok=True)

    fatti = saltati = senza_meta = vuoti = 0
    for txt in sorted(TEXT.rglob('*.txt')):
        caso = txt.parent.name
        if solo_caso and caso != solo_caso:
            continue
        corpo = txt.read_text(encoding='utf-8', errors='replace')
        # LA SOGLIA E' ZERO, NON DUECENTO.
        #
        # Prima si scartava tutto cio' che stava sotto i 200 caratteri, e
        # cadevano 52 documenti. Guardati uno per uno, NON erano guasti:
        # sono ordinanze di una pagina — "MOTION GRANTED. Signed by Judge
        # X." e la data — stipulazioni, avvisi di deposito. Sessanta
        # caratteri perche' il documento dice davvero solo quello.
        #
        # Una soglia arbitraria che scarta documenti veri e' peggio del
        # problema che voleva risolvere: lasciava 52 PDF senza il loro
        # Markdown, cioe' una discrepanza fra due conteggi che qualcuno
        # prima o poi nota e deve reinvestigare.
        # Restano fuori solo i file SENZA ALCUN testo, che sono davvero
        # PDF corrotti e come tali vanno censiti.
        if not re.sub(r'<!--.*?-->', '', corpo).strip():
            vuoti += 1
            continue

        # LA CHIAVE E' IL PERCORSO, NON IL NOME. Il file di testo rispecchia
        # quello del PDF: stesso percorso relativo, altra estensione. Da li'
        # il registro dello scarico da' il Document ID esatto.
        pdf_rel = 'documents/' + str(txt.relative_to(TEXT)).replace('.txt', '.pdf')
        voce = man.get(pdf_rel)
        r = None
        sha = ''
        if voce:
            sha = voce.get('sha256') or ''
            for d in (voce.get('docs') or []):
                cand = idx.get((d.get('document_id') or '').strip())
                if cand:
                    r = cand
                    break
        if not r:
            senza_meta += 1
            saltati += 1
            continue

        pagine = len(re.findall(r'<!--\s*page\s+\d+\s*-->', corpo))
        pdf = HERE / pdf_rel

        dest = OUT / caso / (txt.stem + '.md')
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(front_matter(r, txt, pdf, pagine, sha) + corpo, encoding='utf-8')
        fatti += 1

    print(f'scritti      : {fatti}')
    print(f'saltati      : {saltati} (di cui senza metadati: {senza_meta})')
    print(f'testo vuoto  : {vuoti}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
