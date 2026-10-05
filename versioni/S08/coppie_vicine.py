#!/usr/bin/env python3
"""S08, LE COPPIE VICINE (04/10/2026, soluzione del PI alla deduplica «stessa pagina»).

    python tools/coppie_vicine.py numeri  --banca <fotografia.json.gz> [--scansione <cache.json>] [--uscita <cartella>]
    python tools/coppie_vicine.py genera  --banca <fotografia.json.gz> --scansione <cache.json> --soglia 3000 --uscita coppie.tsv
    python tools/coppie_vicine.py prova   (la prova automatica, vedi sotto; i test veri sono in tests/test_coppie_vicine.py)

IL PROBLEMA. Due citazioni vere dello stesso caso sulla stessa pagina di uno stesso atto andavano perse (Children of Austria,
p. 29; BMW, p. 10). Le fonti della perdita sono nel codice, non una sola:
  1. `rete_descrittiva.rete` salta ogni corrispondenza descrittiva su una pagina dove il caso e' gia' nominato
     (`pagina_col_nome`) o dove c'e' gia' una riga (`pagina_con_riga`): una seconda citazione senza il nome, sulla pagina
     della prima, non diventava riga;
  2. `cerca_s05_per_atto.deduplica` butta il testo identico (400 caratteri) sullo stesso atto e sulla stessa pagina: e' lo
     strato di testo doppio del PDF, e resta (non e' una citazione in piu'); non si tocca;
  3. le regole di fusione (`fondi`): sotto 200 caratteri e' una citazione sola (nota o corpo); non si tocca.

LA SOLUZIONE DEL PI. I riferimenti allo stesso caso, nello stesso atto, a meno di una certa distanza (in caratteri) diventano
una COPPIA CANDIDATA. Ognuno ha un codice provvisorio `<codice>a`, `<codice>b` (`<codice>c` se la catena ne ha di piu'). Poi:
  - DeepSeek e il reranker leggono ognuna delle due righe con l'analisi completa (come ogni riga: L02/L03 e L05);
  - poi la COPPIA insieme con la domanda L13 (tools/leggi_coppia_l13.py): «una citazione sola o due?», cinque letture;
  - UNA: si uniscono come C03 (resta la riga del testo o quella confermata); DUE: contano due; incerta: al team.

COSA FA QUESTO FILE (a secco: non scrive in banca dati, non scrive in coda).
  - `legami`/`gruppi`: dalle righe vive (lessicale, entrambe, descrittiva) di una fotografia di corpus_rows, i legami fra righe
    CONSECUTIVE dello stesso caso e dello stesso atto a distanza di `char_start` <= soglia, e le catene (componenti connesse);
  - `scansiona`: la rete descrittiva rifatta SENZA il filtro della pagina, su tutto il corpus: le corrispondenze che oggi
    sono saltate perche' la pagina ha il nome o una riga. «assorbita» se a meno di 200 caratteri da un nome o da una riga
    (e' la stessa citazione, spiegata: S07 faceva bene), «nuova» altrimenti: e' il recupero. Le nuove si fondono fra loro con
    la stessa regola dei 200 caratteri e dei confini di nota (`cerca_s07.fondi`), e si stima con C04 (descrittiva_stretta)
    quante resterebbero. La scansione e' lenta (17.000 atti): si salva in un file e si riusa;
  - `numeri`: per ogni soglia (200, 500, 1.000, 2.000, 3.000, 5.000, 8.000, 12.000) e per caso: legami, catene, righe coinvolte,
    stessa pagina o no, quanti gia' trovati da C03; piu' le righe nuove che stanno a meno di soglia da una riga viva
    (diventano coppia) o piu' lontano (restano righe sole);
  - `genera`: l'elenco delle coppie a una soglia, con i codici provvisori, per tools/leggi_coppia_l13.py.

UN LIMITE DICHIARATO. La soglia e' un costo (ogni coppia = cinque letture di DeepSeek), non una legge naturale: si sceglie con
la misura delle coppie C03 riviste a mano (a che distanza stavano le coppie «una citazione sola»), vedi `distanze_c03` e il
rapporto S08. Non dimostra niente sulle coppie piu' lontane di quelle che C03 ha visto (C03 cerca la stessa frase entro una
pagina).
"""
import argparse
import bisect
import collections
import csv
import gzip
import json
import multiprocessing as mp
import pathlib
import re
import sys
import time

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI / 'tools'))
sys.path.insert(0, str(QUI))
import textnorm  # noqa: E402
import cerca_s07 as S7  # noqa: E402
import rete_descrittiva as RD  # noqa: E402

B = S7.BASE
CASI = ['urgenda', 'neubauer', 'future-generations', 'klimaseniorinnen', 'cig-parere-clima', 'idh-oc-32-25']
SOGLIE = (200, 500, 1000, 2000, 3000, 5000, 8000, 12000)
VIVE = ('lessicale', 'entrambe', 'descrittiva')
SOGLIA_S08 = 5000          # LA SOGLIA SCELTA (05/10/2026): vedi `Taratura` e training/misure/S08-COPPIE-VICINE-2026-10-04.md
ASSORBITA = 200            # sotto: la corrispondenza e' la stessa citazione del nome o della riga (come la fusione di 200)
LETTERE = 'abcdefghijklmnopqrstuvwxyz'
DATA = '2026-10-04'

_T = {ord(k): v for k, v in {**textnorm.SPACES, **textnorm.DASHES, **textnorm.QUOTES}.items()}


def piatto_veloce(t):
    """lo stesso testo normalizzato di `rete_descrittiva.piatto_con_mappa`, senza la mappa (provato uguale su un campione:
    tests/test_coppie_vicine.py). Serve a scartare in fretta i file senza nessuna ancora."""
    return RD._SPAZI.sub(' ', RD._SILLABA.sub('', t.translate(_T)))


# ── 1. i legami fra le righe vive ────────────────────────────────────────────────────────────────────────────────

def _pos(r):
    try:
        return int(r.get('char_start'))
    except (TypeError, ValueError):
        return None


def righe_per_atto(banca, nuove=()):
    """{(document_id, caso): [(char_start, chiave, riga)]} in ordine di posizione. Righe vive (`VIVE`) con una posizione;
    `nuove`: righe recuperate dalla scansione (dict con document_id, caso_citato, char_start, pagina), senza codice."""
    per = collections.defaultdict(list)
    for i, r in banca.items():
        if r.get('proposto_rete') in VIVE and r.get('document_id') and _pos(r) is not None:
            per[(r['document_id'], r['caso_citato'])].append((_pos(r), i, r))
    for n in nuove:
        per[(n['document_id'], n['caso_citato'])].append((int(n['char_start']), n['chiave'], n))
    for v in per.values():
        v.sort(key=lambda x: (x[0], str(x[1])))
    return per


def pagina_di(r):
    for k in ('validato_pagina', 'proposto_pagina', 'pagina'):
        try:
            return int(r.get(k))
        except (TypeError, ValueError):
            pass
    return None


def legami(per, soglia):
    """i legami fra righe CONSECUTIVE (nell'ordine del testo) dello stesso atto e dello stesso caso a distanza <= soglia:
    [(distanza, (doc, caso), riga_a, riga_b)]. Con tre righe a 100 e 150 caratteri sono due legami (A-B, B-C): la catena."""
    out = []
    for k, v in per.items():
        for (pa, ia, ra), (pb, ib, rb) in zip(v, v[1:]):
            if pb - pa <= soglia:
                out.append((pb - pa, k, (ia, ra), (ib, rb)))
    return out


def gruppi(legs):
    """le catene: [[(chiave, riga), ...]] per atto e caso, righe in ordine di posizione, con almeno due righe"""
    per = collections.defaultdict(list)
    for d, k, a, b in legs:
        per[k].append((a, b))
    out = []
    for k, ls in per.items():
        cur = [ls[0][0], ls[0][1]]
        for a, b in ls[1:]:
            if a[0] == cur[-1][0]:
                cur.append(b)
            else:
                out.append((k, cur)); cur = [a, b]
        out.append((k, cur))
    return out


def codice_base(g):
    cod = sorted(str(r.get('codice')) for _, r in g if r.get('codice'))
    return cod[0] if cod else None


def codici_provvisori(g, n_nuovo=0):
    """`<codice>a`, `<codice>b`, ... sul codice piu' basso della catena; se nessuna riga ha un codice (righe nuove della
    scansione) `NUOVA-<n>`. Provvisori: non si scrivono in banca dati."""
    base = codice_base(g) or f'NUOVA-{n_nuovo:05d}'
    return base, [f'{base}{LETTERE[i] if i < 26 else "z" + str(i)}' for i in range(len(g))]


# ── 2. la scansione: la rete descrittiva senza il filtro della pagina ────────────────────────────────────────────

_G = {}


def _inizia(righe_pagina=None):
    """caricato una volta per processo: regole, regex del nome, procedimento, data della pronuncia, per ogni caso; e le pagine
    che hanno gia' una riga per nome (`righe_con_pagina`)"""
    _G['__rp__'] = righe_pagina or {}
    for caso in CASI:
        p = QUI / 'cited-cases' / f'{caso}-S07.yaml'
        conf = S7.leggi_caso(p)
        regole, altrove = RD.leggi_regole(p)
        esclusi = conf.get('escludi_case_id') or []
        esclusi = [esclusi] if isinstance(esclusi, str) else list(esclusi)
        _G[caso] = {'regole': regole, 'altrove': altrove, 'nome': B.regex_caso(conf),
                    'esclusi': [str(x).lower() for x in esclusi if str(x).strip()],
                    'dmin': str(conf.get('data_decisione') or '')[:10]}


def corrispondenze(s, idx, inizio, regole, col_nome):
    """come `rete_descrittiva.corrispondenze_descrittive`, ma sul testo normalizzato gia' pronto (s, mappa idx)"""
    trovate = []
    for r in regole:
        if r['solo_atti_col_nome'] and not col_nome:
            continue
        for m in r['ancora'].finditer(s):
            w = r['finestra']
            fin = s[max(0, m.start() - w):m.end() + w]
            if r['con'] and not all(x.search(fin) for x in r['con']):
                continue
            if r['escludi'] is not None and r['escludi'].search(fin if w else s[max(0, m.start() - 150):m.end() + 150]):
                continue
            trovate.append((inizio + idx[m.start()], inizio + idx[m.end() - 1] + 1, r['id'], m.group(0)))
    trovate.sort()
    out, fine = [], -1
    for x in trovate:
        if x[0] >= fine:
            out.append(x); fine = x[1]
    return out


def _vive_di(doc_caso, vive_pagine):
    return vive_pagine.get(doc_caso, ())


def scansiona_file(args):
    """un atto: tutte le corrispondenze descrittive che la rete di S07 SALTA per la pagina (col nome o con una riga), per
    ciascun caso. Ritorna (recuperate, conti): recuperate = i gruppi (fusione dei 200 caratteri, confini di nota) con la
    distanza dal nome piu' vicino della pagina. NIENTE e' scritto: e' una lettura."""
    md = args
    righe_pagina = _G['__rp__']
    p = pathlib.Path(md)
    try:
        testo = p.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return [], {}
    meta, inizio = B.front_matter(testo)
    cid = (meta.get('case_id') or '').lower()
    doc = meta.get('document_id') or ''
    s = piatto_veloce(testo[inizio:])
    idx = None
    marks = None
    out, conti = [], collections.Counter()
    dd = B.data_documento(meta)
    for caso in CASI:
        g = _G[caso]
        if any(x in cid for x in g['esclusi']) or doc in g['altrove']:
            continue
        if not any(r['ancora'].search(s) for r in g['regole']):
            continue                                   # nessuna ancora: niente da fare (il caso comune)
        if idx is None:
            _, idx = RD.piatto_con_mappa(testo[inizio:])
            marks = B.pagine(testo)
        col_nome = bool(g['nome'].search(testo, inizio))
        ms = corrispondenze(s, idx, inizio, g['regole'], col_nome)
        if not ms:
            continue
        if dd and g['dmin'] and dd < g['dmin']:
            conti[(caso, 'anteriori')] += len(ms)
            continue
        recuperate = []
        for m in ms:
            pag = B.pagina_di(marks, m[0])
            blocco, off = B.blocco_pagina(testo, marks, m[0])
            nomi = [mm.start() for mm in g['nome'].finditer(blocco)]
            if nomi:
                conti[(caso, 'pagina_col_nome')] += 1
                recuperate.append((RD._M(m[0], m[1], m[2], m[3]), pag, min(abs(off - q) for q in nomi), 'pagina_col_nome'))
            elif (doc, pag) in righe_pagina.get(caso, ()):
                conti[(caso, 'pagina_con_riga')] += 1
                recuperate.append((RD._M(m[0], m[1], m[2], m[3]), pag, None, 'pagina_con_riga'))
            else:
                conti[(caso, 'passa_gia')] += 1
        if not recuperate:
            continue
        salva = B.e_nome
        B.e_nome = RD.e_nome_descrittiva
        try:
            fuse = B.fondi(testo, [x[0] for x in recuperate])
        finally:
            B.e_nome = salva
        info = {x[0].start(): x for x in recuperate}
        for f in fuse:
            m0 = f[0]
            membri = [x for x in recuperate if f[0].start() <= x[0].start() <= f[2]]
            dist = [x[2] for x in membri if x[2] is not None]
            out.append({
                'caso_citato': caso, 'document_id': doc, 'case_id': meta.get('case_id', ''),
                'file': str(p.relative_to(QUI)), 'char_start': m0.start(), 'pagina': info[m0.start()][1],
                'regola_descrittiva': ' + '.join(dict.fromkeys(x[0].regola for x in membri)),
                'forma': 'descrizione: ' + ' + '.join(dict.fromkeys(f'{x[0].regola}: {B.forma_normalizzata(x[0].s)}' for x in membri)),
                'motivo_salto': membri[0][3], 'dist_nome': min(dist) if dist else None,
                'data': meta.get('data_deposito', '')})
    return out, dict(conti)


def righe_con_pagina(banca):
    """{caso: {(document_id, pagina)}} delle righe per nome (lessicale/entrambe): `pagina_con_riga` di S07"""
    out = collections.defaultdict(set)
    for r in banca.values():
        if r.get('proposto_rete') in ('lessicale', 'entrambe'):
            p = pagina_di(r)
            if p is not None:
                out[r['caso_citato']].add((r['document_id'], p))
    return dict(out)


def scansiona(banca, processi=8, file=None, avanti=None):
    """la scansione di tutto il corpus (o di `file`): ([gruppi recuperati], {caso: {motivo: n}}). Lenta (minuti)."""
    files = sorted(B.MD.rglob('*.md')) if file is None else [pathlib.Path(x) for x in file]
    rp = righe_con_pagina(banca)
    lavori = [str(f) for f in files]
    tutti, conti = [], collections.defaultdict(collections.Counter)
    t0 = time.time()
    with mp.Pool(processi, initializer=_inizia, initargs=(rp,)) as pool:
        for n, (o, c) in enumerate(pool.imap_unordered(scansiona_file, lavori, chunksize=20), 1):
            tutti.extend(o)
            for (caso, k), v in c.items():
                conti[caso][k] += v
            if avanti and n % 2000 == 0:
                print(f'  {n}/{len(lavori)} atti, {time.time() - t0:.0f}s, recuperate finora {len(tutti)}', flush=True)
    tutti.sort(key=lambda x: (x['caso_citato'], x['document_id'], x['char_start']))
    return tutti, {k: dict(v) for k, v in conti.items()}


def distanza_da_righe(rec, per_vive):
    """la distanza dalla riga viva piu' vicina dello stesso atto e caso (None se non ce n'e')"""
    v = per_vive.get((rec['document_id'], rec['caso_citato'])) or []
    if not v:
        return None
    pos = [x[0] for x in v]
    j = bisect.bisect_left(pos, rec['char_start'])
    return min(abs(pos[k] - rec['char_start']) for k in (j - 1, j) if 0 <= k < len(pos))


def classifica_recuperate(recuperate, banca):
    """«assorbita» (a meno di 200 caratteri da un nome o da una riga viva) o «nuova»; aggiunge `dist_riga`, `esito`"""
    per_vive = righe_per_atto(banca)
    out = []
    for i, r in enumerate(recuperate):
        dr = distanza_da_righe(r, per_vive)
        dn = r.get('dist_nome')
        m = min(x for x in (dr, dn) if x is not None) if (dr is not None or dn is not None) else None
        out.append(dict(r, chiave=f'S08-{r["caso_citato"]}-{r["document_id"][-8:]}-{r["char_start"]}', dist_riga=dr,
                        esito='assorbita' if (m is not None and m < ASSORBITA) else 'nuova'))
    return out


def stima_c04(nuove, banca):
    """quante delle righe NUOVE passerebbero C04 (descrittiva stretta, tools/descrittiva_stretta.py): {chiave: (resta, motivo)}.
    A secco: righe finte in memoria, mai in banca dati. Le altre righe vive servono alle regole 7 e 8 (corpo e nota,
    traduzioni)."""
    import descrittiva_stretta as D
    import controlli_automatici as CA
    per_doc, per_causa = CA.indice(banca)
    esito = {}
    for n in nuove:
        r = {'file': n['file'], 'char_start': n['char_start'], 'caso_citato': n['caso_citato'], 'document_id': n['document_id'],
             'case_id': n['case_id'], 'proposto_rete': 'descrittiva', 'proposto_forma_trovata': n['forma'],
             'regola_descrittiva': n['regola_descrittiva'], 'data': n.get('data'), 'codice': n['chiave']}
        try:
            esito[n['chiave']] = D.giudica(n['chiave'], r, banca, per_doc, per_causa)
        except Exception as e:  # un file illeggibile non ferma la stima: resta, e lo si dice
            esito[n['chiave']] = (True, f'non giudicabile: {e!r}'[:80])
    return esito


# ── 3. i numeri a ogni soglia ────────────────────────────────────────────────────────────────────────────────────

def coppie_c03(banca):
    """{(codice, codice)} le coppie testo/nota che C03 gia' trova (stessa frase sostenuta): sono un sottoinsieme delle vicine"""
    import unisci_c03 as U
    return {frozenset((t['codice'], n['codice'])) for tipo, t, n, _ in U.coppie(banca) if tipo == 'testo_nota'}


def conta_soglie(banca, nuove=(), c03=frozenset(), soglie=SOGLIE):
    """{soglia: {caso: {...}}} e il totale. Per ogni soglia:
       legami          coppie di righe consecutive (le domande L13)
       catene          i gruppi (una catena di k righe = k-1 legami)
       righe           righe vive coinvolte
       stessa_pagina   legami con le due righe sulla stessa pagina (la perdita di S07)
       gia_c03         legami che C03 trova gia' (stessa frase)
       nuovi_legami    legami con almeno una riga NUOVA (recuperata, non in banca)
    `nuove` = le righe «nuove» della scansione (non assorbite)."""
    out = {}
    per = righe_per_atto(banca, nuove)
    for s in soglie:
        legs = legami(per, s)
        gr = gruppi(legs)
        d = collections.defaultdict(lambda: collections.Counter())
        for dist, (doc, caso), (ia, ra), (ib, rb) in legs:
            c = d[caso]
            c['legami'] += 1
            pa, pb = pagina_di(ra), pagina_di(rb)
            if pa is not None and pa == pb:
                c['stessa_pagina'] += 1
            ca, cb = ra.get('codice'), rb.get('codice')
            if ca and cb and frozenset((ca, cb)) in c03:
                c['gia_c03'] += 1
            if not ca or not cb:
                c['nuovi_legami'] += 1
        for k, g in gr:
            c = d[k[1]]
            c['catene'] += 1
            c['righe'] += len(g)
            c['catena_piu_lunga'] = max(c['catena_piu_lunga'], len(g))
        tot = collections.Counter()
        for c in d.values():
            for k, v in c.items():
                tot[k] = max(tot[k], v) if k == 'catena_piu_lunga' else tot[k] + v
        out[s] = {'per_caso': {k: dict(v) for k, v in d.items()}, 'totale': dict(tot)}
    return out


def righe_nuove_vicine(nuove, banca, soglie=SOGLIE):
    """per ogni soglia: quante righe nuove stanno a meno di soglia da una riga viva dello stesso atto (diventano coppia) e
    quante piu' lontano (restano righe sole, senza domanda L13)"""
    per_vive = righe_per_atto(banca)
    out = {}
    d = [distanza_da_righe(n, per_vive) for n in nuove]
    for s in soglie:
        vicine = sum(1 for x in d if x is not None and x <= s)
        out[s] = {'vicine_a_una_riga_viva': vicine, 'sole_o_lontane': len(d) - vicine}
    return out


def distanze_c03(decisioni, banca):
    """dalle coppie C03 riviste a mano (UNIRE = una citazione sola, TENERE = due), la distanza in caratteri fra i due nomi,
    per dire a che soglia si trovano le coppie «una sola». Non misura le coppie piu' lontane di una pagina."""
    cod = {r.get('codice'): r for r in banca.values() if r.get('codice')}
    out = {'UNIRE': [], 'TENERE': []}
    for r in decisioni:
        if r.get('tipo') == 'traduzione' or r['id'].startswith('T'):
            continue
        a, b = cod.get(r.get('riga_da_tenere') or r.get('codice_tenuto_dalla_regola')), cod.get(r.get('riga_che_esce') or r.get('codice_che_esce_per_la_regola'))
        if not a or not b or a['document_id'] != b['document_id']:
            continue
        d = abs(_pos(a) - _pos(b))
        out['UNIRE' if r['decisione'] == 'UNIRE' else 'TENERE'].append(d)
    return out


# ── 4. l'elenco delle coppie (per L13) ───────────────────────────────────────────────────────────────────────────

def elenco_coppie(banca, soglia, nuove=()):
    """[{id, base, caso, atto, distanza, stessa_pagina, a:{codice_prov, riga}, b:{...}}] un elemento per LEGAME, con il
    codice provvisorio di catena (`<base>a`, `<base>b`, `<base>c`)."""
    per = righe_per_atto(banca, nuove)
    legs = legami(per, soglia)
    gr = gruppi(legs)
    prov = {}
    n_nuovo = 0
    for k, g in gr:
        if not codice_base(g):
            n_nuovo += 1
        base, cp = codici_provvisori(g, n_nuovo)
        for (ch, r), c in zip(g, cp):
            prov[(k, ch)] = (base, c)
    out = []
    for dist, k, (ia, ra), (ib, rb) in legs:
        base, ca = prov[(k, ia)]
        _, cb = prov[(k, ib)]
        pa, pb = pagina_di(ra), pagina_di(rb)
        out.append({'id': f'{ca}-{cb}', 'base': base, 'caso': k[1], 'atto': k[0], 'distanza': dist,
                    'stessa_pagina': pa is not None and pa == pb,
                    'a': {'prov': ca, 'chiave': ia, 'codice': ra.get('codice'), 'char_start': _pos(ra), 'pagina': pa,
                          'nuova': not ra.get('codice')},
                    'b': {'prov': cb, 'chiave': ib, 'codice': rb.get('codice'), 'char_start': _pos(rb), 'pagina': pb,
                          'nuova': not rb.get('codice')}})
    out.sort(key=lambda x: (x['caso'], x['atto'], x['a']['char_start']))
    return out


# ── il verbo `prova`: la prova automatica, a mano (la stessa dei test) ───────────────────────────────────────────

def prova_due_lontane(coppie_attese, banca, nuove=(), soglia=12000):
    """LA PROVA DEL PASSO (voce S08 del registro): se su una pagina ci sono due citazioni lontane e ne esce una sola, FALLISCE.
    `coppie_attese`: [(caso, document_id, char_a, char_b)]. Ognuna deve uscire come un legame di `elenco_coppie` a `soglia`.
    Ritorna l'elenco di quelle mancanti (vuoto = la prova passa)."""
    el = elenco_coppie(banca, soglia, nuove)
    viste = {(c['caso'], c['atto'], c['a']['char_start'], c['b']['char_start']) for c in el}
    return [x for x in coppie_attese if (x[0], x[1], min(x[2], x[3]), max(x[2], x[3])) not in viste]


# ── 5. la taratura della soglia sulle coppie C03 riviste a mano ──────────────────────────────────────────────────

VERITA = QUI / 'training' / 'misure' / 'C03-REVISIONE-COPPIE-2026-10-04.tsv'


class Taratura:
    """LA SOGLIA SI SCEGLIE CON I NUMERI (05/10/2026, il PI: «ogni scelta motivata, serve per il paper»).

    La verita' sono le 850 coppie C03 riviste a mano il 04/10: 693 UNIRE (una citazione sola), 156 TENERE TUTTE E DUE e 1 INCERTA
    (N450, tornata incerta, fuori dal conto). Qui contano le 692 coppie con le due righe NELLO STESSO ATTO (le 157 traduzioni
    stanno in due atti diversi: S08 lavora dentro un atto, le traduzioni restano a C03 e alla sua prova 8).

    Che cosa si misura:
      distanze     i caratteri fra i due nomi, per UNIRE e per TENERE (percentili);
      copertura    per ogni soglia, quante UNIRE e quante TENERE diventano una coppia candidata, in due modi: la coppia di
                   righe a distanza <= soglia, e le due righe nella stessa catena (S08 le legherebbe, anche con una riga in mezzo);
      costo        i legami (= domande L13, ognuna cinque letture di DeepSeek) a ogni soglia sulla fotografia, e i legami in piu'
                   per ogni UNIRE in piu' fra una soglia e la successiva.
    La soglia scelta e' la prima oltre la quale le UNIRE in piu' costano piu' di `COSTO_MASSIMO` legami l'una: e' una
    DECISIONE DI COSTO, non una soglia trovata nei dati (le distanze delle UNIRE e delle TENERE si sovrappongono: la distanza
    non separa le due classi, serve solo a decidere dove smettere di guardare).

    UN LIMITE DICHIARATO. Le coppie C03 nascono dalla stessa frase sostenuta a non piu' di una pagina di distanza: la verita' e'
    «censurata» a una pagina e non dice niente sulle UNIRE piu' lontane. Per questo la soglia non e' il massimo delle UNIRE viste
    (5.834 caratteri) ma un po' meno: oltre una pagina (mediana `pagina_mediana`) C03 non cercava."""

    COSTO_MASSIMO = 50            # legami in piu' per ogni UNIRE in piu': oltre, non vale la pena (decisione di costo)

    def __init__(self, banca, verita=VERITA):
        self.banca = banca
        self.cod = {r.get('codice'): r for r in banca.values() if r.get('codice')}
        self.righe = list(csv.DictReader(open(verita, encoding='utf-8'), delimiter='\t'))

    def coppie_stesso_atto(self):
        """[(decisione, riga_a, riga_b, id)] per le coppie con le due righe nello stesso atto; decisione UNIRE o TENERE"""
        out = []
        for r in self.righe:
            a = self.cod.get(r['codice_tenuto_dalla_regola'])
            b = self.cod.get(r['codice_che_esce_per_la_regola'])
            if not a or not b or a['document_id'] != b['document_id']:
                continue
            d = {'UNIRE': 'UNIRE', 'TENERE TUTTE E DUE': 'TENERE'}.get(r['decisione'])
            if d:
                out.append((d, a, b, r['id']))
        return out

    @staticmethod
    def percentili(v):
        v = sorted(v)
        return {f'p{p}': v[min(len(v) - 1, int(len(v) * p / 100))] for p in (5, 25, 50, 75, 90, 95, 99)} | {'min': v[0], 'max': v[-1]}

    def catene_a(self, soglia):
        """{riga: indice di catena} a questa soglia (le righe vive, componenti connesse dei legami)"""
        per = righe_per_atto(self.banca)
        legs = legami(per, soglia)
        cat = {}
        for n, (k, g) in enumerate(gruppi(legs)):
            for ch, _ in g:
                cat[ch] = n
        return cat

    def pagina_mediana(self, campione=400):
        """la lunghezza mediana di una pagina in caratteri, su un campione di atti: dice quanto e' una pagina"""
        import statistics
        lun = []
        for r in list(self.banca.values())[:3000]:
            if r.get('file') and len(lun) < campione and r.get('proposto_rete') in VIVE:
                try:
                    t = (QUI / r['file']).read_text(encoding='utf-8', errors='replace')
                except OSError:
                    continue
                seg = [m.start() for m in re.finditer(r'<!--\s*page\s+\d+\s*-->', t)]
                lun += [b - a for a, b in zip(seg, seg[1:])]
        return int(statistics.median(lun)) if lun else None

    def misura(self, soglie=SOGLIE):
        cp = self.coppie_stesso_atto()
        dist = {'UNIRE': [], 'TENERE': []}
        for d, a, b, _ in cp:
            dist[d].append(abs(_pos(a) - _pos(b)))
        n = {k: len(v) for k, v in dist.items()}
        per = righe_per_atto(self.banca)
        chiave = {id(r): i for i, r in self.banca.items()}
        tabella = []
        prec_leg = prec_unire = 0
        for s in soglie:
            leg = legami(per, s)
            cat = self.catene_a(s)
            coppie_chiave = {frozenset((ia, ib)) for _, _, (ia, _), (ib, _) in leg}
            riga = {'soglia': s, 'legami': len(leg), 'catene': len(gruppi(leg))}
            for d in ('UNIRE', 'TENERE'):
                entro = sum(1 for x in dist[d] if x <= s)
                vicine = sum(1 for dd, a, b, _ in cp if dd == d and frozenset((chiave[id(a)], chiave[id(b)])) in coppie_chiave)
                stessa = sum(1 for dd, a, b, _ in cp if dd == d and cat.get(chiave[id(a)]) is not None
                             and cat.get(chiave[id(a)]) == cat.get(chiave[id(b)]))
                riga[d] = {'a_distanza': entro, 'consecutive': vicine, 'stessa_catena': stessa,
                           'quota_stessa_catena': round(stessa / n[d], 4)}
            riga['legami_per_unire_in_piu'] = None
            if tabella:
                dun = riga['UNIRE']['stessa_catena'] - tabella[-1]['UNIRE']['stessa_catena']
                riga['legami_per_unire_in_piu'] = round((riga['legami'] - tabella[-1]['legami']) / dun, 1) if dun > 0 else None
            tabella.append(riga)
        scelta = self.scegli(tabella)
        return {'coppie': n, 'distanze': {k: self.percentili(v) for k, v in dist.items()}, 'tabella': tabella,
                'soglia_scelta': scelta, 'pagina_mediana': self.pagina_mediana(), 'costo_massimo': self.COSTO_MASSIMO}

    def scegli(self, tabella):
        """la prima soglia dopo la quale la successiva costa piu' di COSTO_MASSIMO legami per ogni UNIRE in piu' (o non ne aggiunge)"""
        for prima, dopo in zip(tabella, tabella[1:]):
            c = dopo['legami_per_unire_in_piu']
            if c is None or c > self.COSTO_MASSIMO:
                return prima['soglia']
        return tabella[-1]['soglia']

    def indizi(self, soglia=SOGLIA_S08):
        """la precisione di ogni indizio forte sulle coppie della verita': per ogni regola di `coppia_s08.verdetto_indizi`,
        quante volte scatta e quante volte ha ragione (UNIRE = «una», TENERE = «due»)"""
        import coppia_s08 as CS
        conti = collections.defaultdict(collections.Counter)
        tot = collections.Counter()
        for d, a, b, i in self.coppie_stesso_atto():
            ind = CS.Coppia(a, b, i).indizi()
            esito, motivo, forte = CS.verdetto_indizi(ind)
            tot[d] += 1
            if esito:
                giusto = (esito == 'una') == (d == 'UNIRE')
                conti[motivo]['scatta'] += 1
                conti[motivo]['giusta' if giusto else 'sbagliata'] += 1
                conti[motivo]['forte'] = int(forte)
        return {m: dict(c) | {'precisione': round(c['giusta'] / c['scatta'], 4)} for m, c in conti.items()} | {'_coppie': dict(tot)}


def cmd_taratura(a):
    banca = carica_banca(a.banca)
    t = Taratura(banca, a.verita)
    ris = t.misura()
    ris['indizi'] = t.indizi()
    out = pathlib.Path(a.uscita); out.mkdir(parents=True, exist_ok=True)
    json.dump(ris, open(out / f'taratura_{DATA}.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({k: ris[k] for k in ('coppie', 'distanze', 'soglia_scelta', 'pagina_mediana')}, ensure_ascii=False, indent=1))
    print('| soglia | legami | UNIRE nella stessa catena | TENERE nella stessa catena | legami per UNIRE in piu\' |\n|---:|---:|---:|---:|---:|')
    for r in ris['tabella']:
        print(f"| {r['soglia']} | {r['legami']} | {r['UNIRE']['stessa_catena']}/{ris['coppie']['UNIRE']} ({r['UNIRE']['quota_stessa_catena']:.1%}) | "
              f"{r['TENERE']['stessa_catena']}/{ris['coppie']['TENERE']} | {r['legami_per_unire_in_piu']} |")
    print(json.dumps(ris['indizi'], ensure_ascii=False, indent=1))


# ── la riga di comando ───────────────────────────────────────────────────────────────────────────────────────────

def carica_banca(p):
    return json.load(gzip.open(p, 'rt', encoding='utf-8'))


def _tabella(num, nuove_vicine, nuove_stats):
    righe = ['| soglia (caratteri) | legami = domande L13 | catene | righe coinvolte | stessa pagina | gia\' trovati da C03 | catena piu\' lunga | righe nuove vicine a una riga viva | righe nuove sole |',
             '|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for s in SOGLIE:
        t = num[s]['totale']; nv = nuove_vicine.get(s, {})
        righe.append(f"| {s:,} | {t.get('legami', 0)} | {t.get('catene', 0)} | {t.get('righe', 0)} | {t.get('stessa_pagina', 0)} | "
                     f"{t.get('gia_c03', 0)} | {t.get('catena_piu_lunga', 0)} | {nv.get('vicine_a_una_riga_viva', '-')} | {nv.get('sole_o_lontane', '-')} |"
                     .replace(',', '.'))
    return '\n'.join(righe)


def cmd_numeri(a):
    banca = carica_banca(a.banca)
    out = pathlib.Path(a.uscita); out.mkdir(parents=True, exist_ok=True)
    cache = pathlib.Path(a.scansione) if a.scansione else out / f'scansione_{DATA}.json'
    if cache.exists() and not a.rifai:
        d = json.load(open(cache, encoding='utf-8'))
        rec, conti = d['recuperate'], d['conti']
        print(f'scansione letta da {cache} ({len(rec)} gruppi)')
    else:
        t0 = time.time()
        rec, conti = scansiona(banca, a.processi, avanti=True)
        json.dump({'data': DATA, 'recuperate': rec, 'conti': conti, 'secondi': round(time.time() - t0)},
                  open(cache, 'w', encoding='utf-8'), ensure_ascii=False)
        print(f'scansione fatta in {time.time() - t0:.0f}s: {len(rec)} gruppi -> {cache}')
    cl = classifica_recuperate(rec, banca)
    nuove = [x for x in cl if x['esito'] == 'nuova']
    c04 = stima_c04(nuove, banca)
    tengono = [x for x in nuove if c04[x['chiave']][0]]
    for x in cl:
        x['c04_resta'] = c04.get(x['chiave'], (None, ''))[0]
        x['c04_motivo'] = c04.get(x['chiave'], (None, ''))[1]
    c03 = coppie_c03(banca)
    num = conta_soglie(banca, (), c03)
    num_con_nuove = conta_soglie(banca, tengono, c03)
    nv = righe_nuove_vicine(tengono, banca)
    nv_tutte = righe_nuove_vicine(nuove, banca)
    ris = {'data': DATA, 'righe_vive': sum(1 for r in banca.values() if r.get('proposto_rete') in VIVE),
           'conti_scansione': conti,
           'recuperate_gruppi': len(cl), 'assorbite': sum(1 for x in cl if x['esito'] == 'assorbita'),
           'nuove': len(nuove), 'nuove_dopo_c04': len(tengono),
           'nuove_per_caso': dict(collections.Counter(x['caso_citato'] for x in nuove)),
           'nuove_dopo_c04_per_caso': dict(collections.Counter(x['caso_citato'] for x in tengono)),
           'soglie_solo_righe_vive': {str(s): v for s, v in num.items()},
           'soglie_con_le_nuove': {str(s): v for s, v in num_con_nuove.items()},
           'nuove_vicine_a_una_riga_viva': {str(s): v for s, v in nv.items()},
           'nuove_senza_c04_vicine': {str(s): v for s, v in nv_tutte.items()}}
    json.dump(ris, open(out / f'numeri_{DATA}.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    with open(out / f'recuperate_{DATA}.tsv', 'w', newline='', encoding='utf-8') as h:
        w = csv.writer(h, delimiter='\t')
        w.writerow(['chiave', 'caso', 'atto', 'pagina', 'char_start', 'esito', 'dist_nome', 'dist_riga', 'c04_resta', 'c04_motivo', 'regole', 'forma'])
        for x in cl:
            w.writerow([x['chiave'], x['caso_citato'], x['document_id'], x['pagina'], x['char_start'], x['esito'], x['dist_nome'], x['dist_riga'],
                        x['c04_resta'], x['c04_motivo'], x['regola_descrittiva'], x['forma'][:160]])
    print(json.dumps({k: ris[k] for k in ('righe_vive', 'recuperate_gruppi', 'assorbite', 'nuove', 'nuove_dopo_c04', 'nuove_per_caso')}, ensure_ascii=False))
    print(_tabella(num, nv, None))
    print('\ncon le righe nuove (dopo C04):')
    print(_tabella(num_con_nuove, nv, None))


def cmd_genera(a):
    banca = carica_banca(a.banca)
    nuove = []
    if a.scansione and pathlib.Path(a.scansione).exists():
        d = json.load(open(a.scansione, encoding='utf-8'))
        cl = classifica_recuperate(d['recuperate'], banca)
        nu = [x for x in cl if x['esito'] == 'nuova']
        c04 = stima_c04(nu, banca)
        nuove = [x for x in nu if c04[x['chiave']][0]]
    el = elenco_coppie(banca, a.soglia, nuove)
    with open(a.uscita, 'w', newline='', encoding='utf-8') as h:
        w = csv.writer(h, delimiter='\t')
        w.writerow(['id_coppia', 'caso', 'atto', 'distanza', 'stessa_pagina', 'a_prov', 'a_codice', 'a_pagina', 'a_char', 'b_prov', 'b_codice', 'b_pagina', 'b_char'])
        for c in el:
            w.writerow([c['id'], c['caso'], c['atto'], c['distanza'], int(c['stessa_pagina']), c['a']['prov'], c['a']['codice'] or '',
                        c['a']['pagina'], c['a']['char_start'], c['b']['prov'], c['b']['codice'] or '', c['b']['pagina'], c['b']['char_start']])
    print(f'{len(el)} coppie a {a.soglia} caratteri -> {a.uscita}')


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='verbo', required=True)
    n = sp.add_parser('numeri'); n.add_argument('--banca', required=True); n.add_argument('--scansione', default='')
    n.add_argument('--uscita', default=str(QUI / 'training' / 's08')); n.add_argument('--processi', type=int, default=8)
    n.add_argument('--rifai', action='store_true', help='rifa\' la scansione anche se il file c\'e\'')
    g = sp.add_parser('genera'); g.add_argument('--banca', required=True); g.add_argument('--scansione', default='')
    g.add_argument('--soglia', type=int, required=True); g.add_argument('--uscita', required=True)
    t = sp.add_parser('taratura'); t.add_argument('--banca', required=True); t.add_argument('--verita', default=str(VERITA))
    t.add_argument('--uscita', default=str(QUI / 'training' / 's08'))
    a = ap.parse_args()
    {'numeri': cmd_numeri, 'genera': cmd_genera, 'taratura': cmd_taratura}[a.verbo](a)


if __name__ == '__main__':
    main()
