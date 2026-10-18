"""Checks the CLIMPACT identifiers and their crosswalk (ids.csv, crosswalk.csv, crosswalk.json, citations_to_cases).

Form of an identifier: CL-<type>-<six digits>-<check>, for example CL-C-000001-3 (a case) or CL-D-000003-3
(a decision). Types: C case/proceeding, D decision, F filing/document, L law or legal act, P policy, M media item,
R principle, T trace, K court, S parliamentary act, U affinity. The check is ISO 7064 Mod 11-2 (as in ORCID) over the type and the number: the type letter
counts as one symbol with its ISO 7064 / IBAN value (A = 10 ... Z = 35), then the six digits; result 0-9 or X.

Offline checks (always):
  - the check digit works (prove_cifra_controllo: examples worked out by hand, ORCID examples, and altered codes,
    including a changed type, are rejected);
  - every identifier has the right form, a reserved type and a correct check digit;
  - identifiers are unique, every decision belongs to an existing case, every merged or split identifier
    points to identifiers that exist;
  - citation-code prefixes are unique;
  - every row of the crosswalk refers to an existing identifier, and the pair (scheme, external_id) is unique;
  - towards the Sabin Center, a case has at most one exactMatch, and a Sabin case is the exactMatch of at most one
    CLIMPACT case;
  - crosswalk.json is the one that genera_crosswalk_json.py builds from the two CSV files;
  - citations_to_cases.csv has one row per TRACE 0.1 citation, unique codes, existing cases and decisions.

Online checks (skipped with --offline): every URL is fetched, and a 200 is not enough: the content must say the
expected thing (the same family id and slug on the Sabin Center, Climate Policy Radar and CCLW pages; the item on
Wikidata, not a redirect; the ECLI in the open data of rechtspraak.nl or HUDOC or on the court page; a PDF where a PDF
is expected).

It never corrects anything: it prints a report and exits with 1 if something is wrong.
Usage: python3 verifica_crosswalk.py [--offline]     (standard library only)
"""

import csv
import importlib.util
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

QUI = pathlib.Path(__file__).resolve().parent
UA = 'CLIMPACT-crosswalk-check/1.0 (+https://www.climpact.it)'
# i tipi riservati (10/10/2026); oggi si assegnano solo C e D
TIPI = {'C': 'case', 'D': 'decision', 'F': 'filing', 'L': 'law', 'P': 'policy', 'M': 'media',
        'R': 'principle', 'T': 'trace',
        'K': 'court', 'S': 'parliamentary', 'U': 'affinity'}
FORMA = re.compile(r'^CL-([A-Z])-(\d{6})-([0-9X])$')
RELAZIONI = {'exactMatch', 'closeMatch', 'narrowMatch', 'broadMatch', 'relatedMatch'}


def cifra_controllo(simboli):
    """ISO 7064 Mod 11-2 (quella di ORCID) su una stringa di cifre e lettere maiuscole: ogni lettera conta come UN
    simbolo col suo valore ISO 7064 / IBAN (A = 10 ... Z = 35). Risultato: '0'-'9' oppure 'X'."""
    totale = 0
    for c in simboli:
        totale = ((totale + (int(c) if c.isdigit() else ord(c) - 55)) * 2) % 11
    resto = (12 - totale) % 11
    return 'X' if resto == 10 else str(resto)


def nuovo_identificativo(tipo, n):
    """L'identificativo numero n del tipo dato: nuovo_identificativo('C', 1) = 'CL-C-000001-3'."""
    if tipo not in TIPI:
        raise ValueError(f'tipo non riservato: {tipo}')
    numero = f'{n:06d}'
    return f'CL-{tipo}-{numero}-{cifra_controllo(tipo + numero)}'


def valido(identificativo):
    """True se l'identificativo ha la forma giusta, un tipo riservato e la cifra di controllo giusta."""
    m = FORMA.match(identificativo)
    return bool(m) and m.group(1) in TIPI and cifra_controllo(m.group(1) + m.group(2)) == m.group(3)


def tipo_di(identificativo):
    m = FORMA.match(identificativo)
    return TIPI.get(m.group(1)) if m else None


def prove_cifra_controllo():
    """Esempi fatti a mano e codici alterati; restituisce l'elenco degli errori (vuoto se tutto va)."""
    errori = []
    # A MANO (resto modulo 11 a ogni passo, che non cambia il risultato):
    #   CL-C-000001: C = 12 -> 12*2 = 24 = 2; cinque zeri: 4, 8, 16 = 5, 10, 20 = 9; poi (9+1)*2 = 20 = 9;
    #                (12 - 9) % 11 = 3 -> CL-C-000001-3
    #   CL-D-000001: D = 13 -> 26 = 4; 8, 16 = 5, 10, 20 = 9, 18 = 7; (7+1)*2 = 16 = 5; 12 - 5 = 7 -> CL-D-000001-7
    #   CL-L-000001: L = 21 -> 42 = 9; 18 = 7, 14 = 3, 6, 12 = 1, 2; (2+1)*2 = 6; 12 - 6 = 6 -> CL-L-000001-6
    #   CL-C-000003: 9 dopo gli zeri; (9+3)*2 = 24 = 2; 12 - 2 = 10 -> X -> CL-C-000003-X
    attesi = {'C000001': '3', 'D000001': '7', 'L000001': '6', 'C000003': 'X',
              # gli esempi pubblicati da ORCID (stesso algoritmo su 15 cifre): 0000-0002-1825-0097, 0000-0002-1694-233X
              '000000021825009': '7', '000000021694233': 'X'}
    for simboli, cifra in attesi.items():
        if cifra_controllo(simboli) != cifra:
            errori.append(f'cifra di controllo di {simboli}: {cifra_controllo(simboli)}, attesa {cifra}')
    for buono in ('CL-C-000001-3', 'CL-D-000001-7', 'CL-L-000001-6', 'CL-C-000003-X'):
        if not valido(buono):
            errori.append(f'rifiutato un codice giusto: {buono}')
    if nuovo_identificativo('C', 1) != 'CL-C-000001-3':
        errori.append("nuovo_identificativo('C', 1) sbagliato")
    # ogni cifra cambiata, ogni scambio di due cifre vicine diverse, ogni cambio di tipo fra i tipi riservati e ogni
    # altra cifra di controllo devono essere rifiutati (i valori dei tipi riservati sono tutti diversi modulo 11)
    for tipo in TIPI:
        for n in (1, 2, 3, 4, 5, 6, 9, 123, 987654):
            giusto = nuovo_identificativo(tipo, n)
            numero, cifra = giusto[5:11], giusto[12]
            for i in range(6):
                for d in '0123456789':
                    if d != numero[i] and valido(f'CL-{tipo}-{numero[:i]}{d}{numero[i + 1:]}-{cifra}'):
                        errori.append(f'accettato un codice alterato da {giusto}')
                if i < 5 and numero[i] != numero[i + 1]:
                    scambiato = numero[:i] + numero[i + 1] + numero[i] + numero[i + 2:]
                    if valido(f'CL-{tipo}-{scambiato}-{cifra}'):
                        errori.append(f'accettato uno scambio di cifre da {giusto}')
            for altro in TIPI:
                if altro != tipo and valido(f'CL-{altro}-{numero}-{cifra}'):
                    errori.append(f'accettato un cambio di tipo da {giusto} a {altro}')
            for c in '0123456789X':
                if c != cifra and valido(f'CL-{tipo}-{numero}-{c}'):
                    errori.append(f'accettata una cifra di controllo sbagliata per {giusto}')
    for sbagliato in ('CC-000001', 'CL-000001-X', 'CL-C-000001', 'CL-C-00001-3', 'CL-c-000001-3', 'CL-C-000001-x',
                      'CL-Q-000001-' + cifra_controllo('Q000001'), 'CL-C-000001-3-D01'):
        if valido(sbagliato):
            errori.append(f'accettata una forma sbagliata: {sbagliato}')
    return errori


def leggi():
    ids = list(csv.DictReader((QUI / 'ids.csv').open(encoding='utf-8')))
    links = list(csv.DictReader((QUI / 'crosswalk.csv').open(encoding='utf-8')))
    return ids, links


def controlli_offline(ids, links):
    errori = prove_cifra_controllo()
    visti = {}
    for r in ids:
        i = r['climpact_id']
        if not FORMA.match(i):
            errori.append(f'forma sbagliata: {i}')
        elif not valido(i):
            errori.append(f'cifra di controllo sbagliata: {i}')
        if i in visti:
            errori.append(f'identificativo ripetuto: {i}')
        visti[i] = r
        if r['type'] != tipo_di(i):
            errori.append(f'{i}: type «{r["type"]}», atteso «{tipo_di(i)}»')
        if r['type'] not in ('case', 'decision'):
            errori.append(f'{i}: per ora si assegnano solo casi (C) e decisioni (D)')
        if r['type'] == 'case' and r['case_id'] != i:
            errori.append(f'{i}: il case_id di un caso e\' il caso stesso')
        if r['status'] not in ('active', 'merged', 'split'):
            errori.append(f'{i}: status «{r["status"]}» non previsto')
        if r['status'] != 'active' and not r['replaced_by']:
            errori.append(f'{i}: {r["status"]} senza replaced_by')
    for r in ids:
        if r['case_id'] not in visti or visti[r['case_id']]['type'] != 'case':
            errori.append(f'{r["climpact_id"]}: il caso {r["case_id"]} non esiste')
        for x in filter(None, r['replaced_by'].split(';')):
            if x not in visti:
                errori.append(f'{r["climpact_id"]}: replaced_by {x} non esiste')
    prefissi = [r['citation_prefix'] for r in ids if r['citation_prefix']]
    for p in sorted({p for p in prefissi if prefissi.count(p) > 1}):
        errori.append(f'prefisso ripetuto: {p}')
    coppie = {}
    sabin_esatti = {}
    for n, l in enumerate(links, 2):
        if l['climpact_id'] not in visti:
            errori.append(f'crosswalk riga {n}: {l["climpact_id"]} non e\' in ids.csv')
        if l['climpact_id'] in visti and l['case_id'] != visti[l['climpact_id']]['case_id']:
            errori.append(f'crosswalk riga {n}: case_id non corrisponde')
        if l['relation'] not in RELAZIONI:
            errori.append(f'crosswalk riga {n}: relazione «{l["relation"]}» non prevista')
        chiave = (l['scheme'], l['external_id'])
        if chiave in coppie:
            errori.append(f'crosswalk riga {n}: {chiave} ripetuto (riga {coppie[chiave]})')
        coppie[chiave] = n
        if not l['checked_on'] or not l['checked_by'] or not l['source']:
            errori.append(f'crosswalk riga {n}: manca checked_on, checked_by o source')
        if l['scheme'] == 'sabin_case' and l['relation'] == 'exactMatch':
            sabin_esatti.setdefault(l['climpact_id'], []).append(l['external_id'])
            if tipo_di(l['climpact_id']) != 'case':
                errori.append(f'crosswalk riga {n}: un caso Sabin si lega a un caso, non a una decisione')
    for i, slug in sabin_esatti.items():
        if len(slug) > 1:
            errori.append(f'{i}: {len(slug)} exactMatch verso il Sabin')
    for r in ids:
        if r['type'] == 'case' and r['status'] == 'active' and r['climpact_id'] not in sabin_esatti:
            print(f'  nota: {r["climpact_id"]} non ha un caso Sabin (ammesso, ma da sapere)')
    errori += controllo_citazioni(visti)
    spec = importlib.util.spec_from_file_location('genera', QUI / 'genera_crosswalk_json.py')
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    pubblicato = QUI / 'crosswalk.json'
    if not pubblicato.is_file() or json.loads(pubblicato.read_text(encoding='utf-8')) != g.costruisci():
        errori.append('crosswalk.json non corrisponde ai CSV: rilanciare genera_crosswalk_json.py')
    return errori


CITAZIONI_01 = 7893   # righe del dataset TRACE 0.1 (DOI 10.5281/zenodo.23082590)


def controllo_citazioni(visti):
    """citations_to_cases.csv/.json: una riga per citazione della 0.1, codici unici, casi e decisioni esistenti."""
    errori = []
    f = QUI / 'citations_to_cases.csv'
    if not f.is_file():
        return ['manca citations_to_cases.csv']
    righe = list(csv.DictReader(f.open(encoding='utf-8')))
    if len(righe) != CITAZIONI_01:
        errori.append(f'citations_to_cases.csv: {len(righe)} righe, attese {CITAZIONI_01}')
    codici = [r['citation_code'] for r in righe]
    if len(set(codici)) != len(codici):
        errori.append(f'citations_to_cases.csv: {len(codici) - len(set(codici))} codici ripetuti')
    prefissi = {r['citation_prefix']: r['climpact_id'] for r in visti.values() if r['citation_prefix']}
    for r in righe:
        c = r['citation_code']
        if r['case_id'] not in visti or visti[r['case_id']]['type'] != 'case':
            errori.append(f'{c}: caso {r["case_id"]} inesistente')
        elif prefissi.get(c.rsplit('-', 1)[0]) != r['case_id']:
            errori.append(f'{c}: il prefisso non e\' quello del caso {r["case_id"]}')
        if r['decision_id'] and (r['decision_id'] not in visti or visti[r['decision_id']]['case_id'] != r['case_id']):
            errori.append(f'{c}: decisione {r["decision_id"]} inesistente o di un altro caso')
        if bool(r['decision_id']) != bool(r['decision_basis']):
            errori.append(f'{c}: decision_id e decision_basis non vanno insieme')
        if not r['document_id'] or not r['document_url'].startswith('https://www.climatecasechart.com/documents/'):
            errori.append(f'{c}: atto mancante o indirizzo non del Sabin')
    j = QUI / 'citations_to_cases.json'
    if not j.is_file():
        errori.append('manca citations_to_cases.json')
    else:
        dj = json.loads(j.read_text(encoding='utf-8'))
        if [x['citation_code'] for x in dj['citations']] != codici or dj['rows'] != len(righe):
            errori.append('citations_to_cases.json non corrisponde al CSV: rilanciare genera_citazioni_casi.py')
    return errori[:50]


def scarica(url, dati=None, intestazioni=None):
    req = urllib.request.Request(url, data=dati, headers={'User-Agent': UA, **(intestazioni or {})})
    for tentativo in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.headers.get('Content-Type', ''), r.read(), r.geturl()
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503) and tentativo < 2:
                time.sleep(5 * (tentativo + 1))
                continue
            return e.code, '', b'', url
        except Exception as e:  # rete, timeout
            if tentativo == 2:
                return 0, str(e), b'', url
            time.sleep(5)


def famiglia(corpo):
    m = re.search(rb'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', corpo, re.S)
    if not m:
        return None
    return json.loads(m.group(1))['props']['pageProps'].get('family') or {}


class NonControllabile(Exception):
    """Il sito rifiuta i programmi (403): il legame si controlla a mano, non e' un errore del legame."""


def hudoc(filtro):
    q = urllib.parse.urlencode({'query': f'contentsitename:ECHR AND ({filtro})',
                                'select': 'itemid,ecli,docname', 'sort': '', 'start': 0, 'length': 50})
    stato, _, corpo, _ = scarica('https://hudoc.echr.coe.int/app/query/results?' + q)
    if stato == 403:
        raise NonControllabile('HUDOC rifiuta le richieste dei programmi: controllare a mano')
    if stato != 200:
        return []
    return [x['columns'] for x in json.loads(corpo).get('results', [])]


def controllo_online(l, famiglie):
    """None se va bene, altrimenti il motivo."""
    schema, ext, url = l['scheme'], l['external_id'], l['url']
    if schema == 'wikidata':
        stato, _, corpo, _ = scarica('https://www.wikidata.org/w/api.php?action=wbgetentities&props=info&format=json&ids=' + ext)
        if stato != 200:
            return f'API di Wikidata: {stato}'
        e = json.loads(corpo).get('entities', {}).get(ext, {})
        if 'missing' in e:
            return 'elemento inesistente'
        if e.get('id') != ext:
            return f'reindirizzato a {e.get("id")}'
    if schema == 'ecli' and ext.startswith('ECLI:NL:'):
        stato, _, corpo, _ = scarica('https://data.rechtspraak.nl/uitspraken/content?return=META&id=' + ext)
        if stato != 200 or ext.encode() not in corpo:
            return f'rechtspraak.nl non conosce {ext} ({stato})'
    if schema == 'ecli' and ext.startswith('ECLI:CE:ECHR:'):
        if not any(c.get('ecli') == ext for c in hudoc(f'ecli:"{ext}"')):
            return 'HUDOC non conosce l\'ECLI'
    if schema == 'hudoc':
        if not any(c.get('itemid') == ext for c in hudoc(f'itemid:"{ext}"')):
            return 'HUDOC non conosce l\'itemid'
    if not url:
        return None
    if 'hudoc.echr.coe.int' in url or 'uitspraken.rechtspraak.nl' in url:
        # pagine che si riempiono nel browser: il contenuto si e' gia' controllato sopra con le loro API
        stato, _, _, _ = scarica(url)
        if stato == 403:
            raise NonControllabile('il sito rifiuta le richieste dei programmi: controllare a mano')
        return None if stato == 200 else f'HTTP {stato}'
    stato, tipo, corpo, finale = scarica(url)
    if stato != 200:
        return f'HTTP {stato} {tipo}'
    if schema in ('sabin_case', 'cpr_family', 'cclw'):
        f = famiglia(corpo)
        slug = url.rstrip('/').rsplit('/', 1)[1]
        if not f:
            return 'pagina senza dati del caso'
        if f.get('slug') != slug:
            return f'la pagina indica lo slug {f.get("slug")}'
        if schema == 'sabin_case':
            famiglie[slug] = f.get('import_id')
        elif f.get('import_id') != ext:
            return f'import_id {f.get("import_id")} invece di {ext}'
        elif famiglie.get(slug) not in (None, ext):
            return 'import_id diverso da quello della pagina Sabin'
    if schema == 'ecli' and ext.startswith('ECLI:DE:') and ext.encode() not in corpo:
        return 'l\'ECLI non compare nella pagina della corte'
    if url.lower().endswith('.pdf') and not (corpo[:5] == b'%PDF-' and len(corpo) > 10000):
        return f'non e\' un PDF ({tipo}, {len(corpo)} byte)'
    return None


def main():
    ids, links = leggi()
    errori = controlli_offline(ids, links)
    print(f'{len(ids)} identificativi, {len(links)} legami: {len(errori)} errori nei controlli senza rete')
    if '--offline' not in sys.argv:
        famiglie, avvisi = {}, []
        # le pagine Sabin prima, cosi' Climate Policy Radar e CCLW si confrontano con loro
        ordine = sorted(links, key=lambda l: l['scheme'] != 'sabin_case')
        controllati = 0
        for l in ordine:
            if not l['url'] and l['scheme'] not in ('wikidata', 'ecli', 'hudoc'):
                continue
            try:
                motivo = controllo_online(l, famiglie)
            except NonControllabile as e:
                avvisi.append(f'{l["climpact_id"]} {l["scheme"]} {l["external_id"]}: {e}')
                continue
            controllati += 1
            if motivo:
                errori.append(f'{l["climpact_id"]} {l["scheme"]} {l["external_id"]}: {motivo}')
            time.sleep(0.5)
        print(f'{controllati} legami controllati in rete')
        for a in avvisi:
            print('  DA CONTROLLARE A MANO', a)
    for e in errori:
        print('  ERRORE', e)
    print('esito:', 'tutto in ordine' if not errori else f'{len(errori)} errori')
    return 1 if errori else 0


if __name__ == '__main__':
    sys.exit(main())
