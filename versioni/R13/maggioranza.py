"""R11, LA COMPOSIZIONE A MAGGIORANZA DELLE CINQUE LETTURE (02/10/2026, col si' del PI: «procedi»).

   Misura: `training/misure/GIRI-E-DOMANDA.md`. Con 5 letture per riga l'alfa di Krippendorff fra due maggioranze
   indipendenti e' 0,83 sui principi (L05) e 0,83 sul tipo, contro 0,66 e 0,67 con una lettura sola; 5 e' il primo k
   che passa la soglia 0,80, tutti i casi insieme. Le regole, una per una:

   - TIPO: vince il tipo piu' votato fra le letture valide (tipo del codebook). A PARITA' (2-2-1, 1-1-1-1-1) vince, fra
     i tipi pari, quello che compare per primo nell'ordine delle letture (lettura 1, poi 2...): regola fissa, ripetibile.
     Margine = voti del primo meno voti del secondo; la decisione e' INCERTA se il margine e' al massimo 1 (la stessa
     definizione della misura), e una parita' lo e' sempre. Chi parla, proposizione e motivo vengono dalla prima lettura
     che ha dato il tipo vincente.
   - PRINCIPI (L05): ogni lettura valida (non vuota, leggibile, con una lista di principi non vuota) vota l'insieme dei
     principi che prende (codici del caso, «altro» con la sua frase; se non ne prende nessuno, «nessuno»). Un principio
     e' proposto se lo vota la maggioranza delle letture valide: almeno 3 su 5 (3 su 4, 2 su 3...). Si scrivono i voti di
     ogni principio votato almeno una volta («4/5»). Decisione incerta se |2v - n| <= 1 (2 o 3 voti su 5). Se nessun
     principio arriva alla maggioranza, «nessuno» (come nella misura: nessun principio preso).
     R13 (04/10/2026): una lettura che risponde con l'elenco dei principi VUOTO («principi»: []) vota «nessuno», come
     nella misura delle cinque letture (stabilita_deepseek.principi: [] e' l'insieme vuoto, non una lettura fallita).
     Fino a R12 non votava: 8.894 letture su 32.474, quasi tutte con il motivo «nessun principio del caso», e 718 righe
     non giudicate senza nessuna lettura valida (vedi `vuota_vota` in voto_principi).
     Restano, come in R05: i principi della mappa dei paragrafi, «nessuno» per una menzione in catena (qui il tipo a
     maggioranza), i suggerimenti del reranker fra le fonti.
   - PAGINE ATTORNO: una pagina prosegue se lo dice la maggioranza delle letture valide e se la prova di almeno una di
     quelle letture sta davvero nella pagina (il freno del 30/09 resta un filtro sulle pagine); principio della pagina:
     il piu' votato fra le letture che dicono si'.
   - FRASE SOSTENUTA: dalla prima lettura il cui insieme di principi e' uguale a quello della maggioranza, altrimenti
     dalla prima lettura con una frase; verificata con freni.verifica come oggi.
   - PROVA MANCANTE: un principio proposto dalla sola lettura (non dai paragrafi) ha una prova se la frase sostenuta e'
     trovata nella pagina, oppure se una pagina attorno spuntata su quel principio ha la prova trovata. Senza prova il
     principio NON si toglie (la misura: toglierlo non migliora l'accordo con le persone e abbassa il richiamo): resta,
     con `proposto_prova_mancante` e l'elenco dei principi senza prova, visibile a chi valida.
"""
import collections

CAT = ('menzione_in_catena', 'descrittiva', 'sostanziale', 'distinguente', 'critica', 'implicita')
NESSUNO, ALTRO = 'nessuno', 'altro'


def vero(x):
    """un si'/no della lettura letto in modo stretto (03/10/2026, dalla revisione esterna): vale si' solo true, la stringa
    "true" (maiuscole e spazi a parte) o il numero 1; tutto il resto, compresa la stringa "false", vale no. Prima si
    usava bool(), e la stringa "false" (non vuota) valeva si'. Nelle letture salvate al 03/10: 197.892 booleani veri e
    falsi, 2 stringhe "true"; nessuna "false", quindi niente cambia sulle proposte gia' fatte."""
    if x is True:
        return True
    if isinstance(x, str):
        return x.strip().lower() == 'true'
    return type(x) is int and x == 1


def vuota(y):
    return isinstance(y, dict) and 'grezzo' in y and not str(y.get('grezzo') or '').strip()


def valida(y):
    """una lettura che e' una risposta: letta (non vuota) e non illeggibile"""
    return isinstance(y, dict) and not vuota(y) and y.get('esito') != 'ILLEGGIBILE'


def soglia(n):
    """la maggioranza di n letture valide: 3 su 5, 3 su 4, 2 su 3, 2 su 2, 1 su 1"""
    return n // 2 + 1


def incerta(v, n):
    """una decisione si/no con v voti su n e' incerta se il margine e' al massimo 1"""
    return abs(2 * v - n) <= 1


def voti_testo(v, n):
    return f'{v}/{n}'


def voto_tipo(letture):
    """Il tipo a maggioranza. None se nessuna lettura da' un tipo del codebook."""
    valide = [(k, y) for k, y in enumerate(letture or []) if valida(y) and y.get('tipo_citazione') in CAT]
    if not valide:
        return None
    voti = collections.Counter(y['tipo_citazione'] for _, y in valide)
    ordine = []
    for _, y in valide:
        if y['tipo_citazione'] not in ordine:
            ordine.append(y['tipo_citazione'])
    alto = max(voti.values())
    pari = [t for t in ordine if voti[t] == alto]
    tipo = pari[0]                      # a parita': il primo nell'ordine delle letture
    secondo = max([v for t, v in voti.items() if t != tipo] or [0])
    margine = alto - secondo
    k, rapp = next((k, y) for k, y in valide if y['tipo_citazione'] == tipo)
    return {'tipo': tipo, 'n': len(valide), 'voti': {t: voti[t] for t in sorted(ordine, key=lambda t: (-voti[t], ordine.index(t)))},
            'margine': margine, 'parita': len(pari) > 1, 'incerto': margine <= 1, 'lettura': rapp, 'indice': k}


def principi_lettura(y, ids, canonico):
    """i codici che una lettura L05 prende, gia' riportati al codice valido; una stringa si divide su virgole e punti e virgola"""
    import re
    pr = y.get('principi') or []
    if isinstance(pr, str):
        pr = [q.strip() for q in re.split(r'[,;]', pr) if q.strip()]
    return [canonico(q) for q in pr if isinstance(q, str) and q]


def insieme(y, ids, canonico):
    """l'insieme che una lettura vota: i suoi principi del caso, «altro» se lo dice con una frase, altrimenti «nessuno»"""
    lett = principi_lettura(y, ids, canonico)
    s = [p for p in ids if p in lett]
    if ALTRO in lett and ' '.join(str(y.get('altro') or '').split()):
        s.append(ALTRO)
    return s or [NESSUNO]


def soglia_due(n):
    """R12 (proposta del 04/10/2026, non ancora in uso): un principio e' proposto se lo prendono almeno 2 letture valide
    (1 se ce n'e' una sola; 2 su 2 come prima). Misura: tools/r12_varianti.py. Solo i principi: le pagine restano a maggioranza."""
    return min(2, soglia(n))


def elenco_vuoto(y):
    """R13 (04/10/2026): la lettura ha risposto con l'elenco dei principi vuoto: «principi» c'e' ed e' [] o una stringa
    vuota. Non basta un campo mancante o None (risposta senza il campo: non e' una risposta), ne' un elenco di non-stringhe."""
    if not isinstance(y, dict) or 'principi' not in y:
        return False
    pr = y.get('principi')
    return (isinstance(pr, list) and not pr) or (isinstance(pr, str) and not pr.strip())


def voto_principi(letture, ids, canonico, soglia_principi=None, vuota_vota=False):
    """I voti delle letture L05 valide. Fino a R12 una lettura con la lista dei principi vuota non era una risposta (R05) e
    non votava. `vuota_vota` (R13, 04/10/2026): la lista vuota vota «nessuno», come nella misura (GIRI-E-DOMANDA.md).
    `soglia_principi` (R12): la funzione n -> voti minimi per proporre un principio; None = maggioranza (R11). Il campo
    'soglia' del risultato resta la maggioranza: e' quella che usano le pagine attorno."""
    valide = [(k, y) for k, y in enumerate(letture or []) if valida(y)
              and (principi_lettura(y, ids, canonico) or (vuota_vota and elenco_vuoto(y)))]
    n = len(valide)
    if not n:
        return None
    insiemi = [(k, y, insieme(y, ids, canonico)) for k, y in valide]
    voti = collections.Counter(p for _, _, s in insiemi for p in s)
    t = soglia_principi(n) if soglia_principi else soglia(n)
    presi = [p for p in ids if voti[p] >= t] + ([ALTRO] if voti[ALTRO] >= t else [])
    maggioranza = presi or [NESSUNO]
    ordine = [p for p in ids if voti[p]] + [p for p in (ALTRO, NESSUNO) if voti[p]]
    return {'n': n, 'soglia': soglia(n), 'soglia_principi': t, 'insiemi': insiemi, 'voti': {p: voti[p] for p in ordine}, 'maggioranza': maggioranza,
            'incerti': [p for p in ordine if incerta(voti[p], n)]}


def lettura_scelta(vp):
    """la lettura da cui vengono frase sostenuta, motivo e «altro»: la prima con l'insieme uguale alla maggioranza,
    altrimenti la prima con una frase, altrimenti la prima valida"""
    for _, y, s in vp['insiemi']:
        if sorted(s) == sorted(vp['maggioranza']):
            return y
    for _, y, _ in vp['insiemi']:
        if ' '.join(str(y.get('frase_sostenuta') or '').split()):
            return y
    return vp['insiemi'][0][1]


def frase_scelta(vp):
    """la frase sostenuta: dalla prima lettura con l'insieme della maggioranza, altrimenti dalla prima con una frase"""
    for _, y, s in vp['insiemi']:
        if sorted(s) == sorted(vp['maggioranza']) and ' '.join(str(y.get('frase_sostenuta') or '').split()):
            return y
    for _, y, _ in vp['insiemi']:
        if ' '.join(str(y.get('frase_sostenuta') or '').split()):
            return y
    return {}


def voto_pagine(vp, principio_pagina):
    """Per ogni pagina giudicata: le letture che dicono che prosegue (k, voce), in ordine. {pagina: [(k, voce)...]}"""
    out = collections.defaultdict(list)
    for k, y, _ in vp['insiemi']:
        visti = set()
        for v in (y.get('vicine') if isinstance(y.get('vicine'), list) else []):
            if not isinstance(v, dict):
                continue
            try:
                n = int(v.get('pagina'))
            except (TypeError, ValueError):
                continue
            if n in visti:
                continue
            visti.add(n)
            out[n].append((k, v))
    return out
