"""I CONTROLLI AUTOMATICI DELLE RIGHE (04/10/2026, il PI: «non pulizie fatte a mano una volta, una pipeline che le faccia
da sola anche in futuro»). Fase 2 della pipeline nuova (passaggio, «La pipeline nuova decisa dal PI», punto 2).

   Le regole trovate sulle righe di S07 (training/misure/S07-PRECISIONE-2026-10-04.md, S07-PULIZIA-2026-10-04.md) diventano
   passi fissi, applicati da soli a OGNI riga da giudicare, di qualunque ricerca (non solo S07). Ognuna ha un codice nel
   registro delle versioni (bozza delle voci: versioni/BOZZA-controlli-C01-C07.json):

     C01  copie della stessa causa           lo stesso brano in un altro atto della stessa causa con la sua riga: conta una
                                             volta (decisione del PI del 03/10, documento unico §63.70)
     C02  doppioni sicuri                    lo stesso allegato ripetuto nello stesso atto, il confine di nota falso, il nome
                                             nel titolo di un allegato, lo stesso riferimento col suo indirizzo web
     C03  corpo e nota, traduzioni           stessa frase sostenuta nel testo e nella nota, e la stessa citazione nella
                                             traduzione dello stesso atto: una riga sola (tools/unisci_c03.py; approvata dal
                                             PI il 04/10/2026; le coppie con una riga giudicata vanno riviste a mano)
     C04  rete descrittiva stretta           tools/descrittiva_stretta.py (solo le righe senza il nome)
     C05  porta dei conteggi B2              tools/porta_conteggi.py (in aggiorna_dati_mappa.py: chi entra nei numeri)
     C06  controllo di completezza           tools/controllo_completezza.py alla fine di ogni giro

   NIENTE SI CANCELLA. Un controllo non tocca la riga: PROPONE un'esclusione (codice, regola, motivo). La scrittura la
   fa tools/escludi_righe.py, che segna `proposto_rete: 'esclusa'` con `esclusa_regola`, `esclusa_motivo`, chi e quando,
   e la copia intera prima; tools/rimetti_righe.py la rimette. Le righe giudicate dal team (esito, o giudizio di
   settembre) non si propongono mai: dove una copia e' giudicata, esce l'altra; se lo sono tutte e due, va al team.

   QUESTO FILE NON SCRIVE IN BANCA DATI. Legge una fotografia di corpus_rows (o la banca dati in sola lettura con --vivo)
   e scrive l'elenco delle proposte, un TSV con le colonne di escludi_righe.py (`codice`, `motivo`, `regola`).

   Uso:  .venv/bin/python tools/controlli_automatici.py (--banca <fotografia.json.gz> | --vivo) --uscita <proposte.tsv>
             [--solo-nuove-dal 2026-10-04] [--regole C01,C02,C04]
"""
import argparse, bisect, collections, csv, gzip, json, pathlib, re, sys

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
import descrittiva_stretta as D  # noqa: E402  (sola lettura: testo, unita, regole C03)

C = D.C
ATTIVE = ('lessicale', 'entrambe', 'descrittiva')
FINESTRA = 80          # 160 caratteri attorno al punto: il «brano» di C01 e C02
VICINO = 30            # la riga gemella sta a meno di 30 caratteri dal brano ritrovato (le copie vere: 0-5 caratteri;
                       # a 44-119 caratteri c'era una citazione vicina ma diversa, Children of Austria NEU-0121)
FALSO_CONFINE = re.compile(r'\n[ \t]*\d{1,4}[ \t]+(?:ff?\.|et seq|\d)', re.I)


def giudicata(r):
    return bool(r.get('esito') or r.get('settembre'))


def brano(t, pos, mappa=None):
    na, pa = mappa or D_norm(t)
    j = bisect.bisect_left(pa, pos)
    return na[max(0, j - FINESTRA):j + FINESTRA], j


_norm = {}


def D_norm(f_o_t):
    """testo normalizzato (spazi uniti, minuscole) con la mappa delle posizioni, in cache per file"""
    if f_o_t in _norm:
        return _norm[f_o_t]
    t = D.testo(f_o_t)
    out, pos, sp = [], [], False
    for i, ch in enumerate(t):
        if ch.isspace():
            if not sp and out:
                out.append(' '); pos.append(i)
            sp = True
        else:
            out.append(ch.lower()); pos.append(i); sp = False
    _norm[f_o_t] = (''.join(out), pos)
    return _norm[f_o_t]


def contenuto(fa, fb, k=40, L=80):
    a, _ = D_norm(fa); b, _ = D_norm(fb)
    if len(a) < 2 * L:
        return 0.0
    passo = (len(a) - L) // (k - 1)
    return sum(1 for i in range(k) if a[i * passo:i * passo + L] in b) / k


def indice(banca):
    per_doc = collections.defaultdict(list); per_causa = collections.defaultdict(dict)
    for i, r in banca.items():
        if r.get('proposto_rete') in ATTIVE and r.get('file'):
            per_doc[(r['document_id'], r['caso_citato'])].append((i, r))
            per_causa[(r['case_id'], r['caso_citato'])][r['document_id']] = r['file']
    return per_doc, per_causa


def chi_esce(x, y, banca, per_doc=None):
    """di due righe che sono la stessa citazione, quale esce (None se sono giudicate tutte e due):
      1. mai una riga giudicata dal team;
      2. una riga nuova non scalza una vecchia: esce quella creata dopo (giorno di creato_il);
      3. lo stesso giorno, resta quella nell'atto che ha piu' righe attive di quel caso (la copia «principale»);
      4. poi esce quella nell'atto contenuto nell'altro; 5. poi il codice piu' recente."""
    (i, r), (j, s) = x, y
    if giudicata(r) and giudicata(s):
        return None
    if giudicata(r):
        return y
    if giudicata(s):
        return x
    gr, gs = str(r.get('creato_il') or '')[:10], str(s.get('creato_il') or '')[:10]
    if gr != gs and gr and gs:
        return x if gr > gs else y
    if per_doc is not None and r['document_id'] != s['document_id']:
        nr, ns = len(per_doc[(r['document_id'], r['caso_citato'])]), len(per_doc[(s['document_id'], s['caso_citato'])])
        if nr != ns:
            return x if nr < ns else y
    if r['document_id'] != s['document_id']:
        ab, ba = contenuto(r['file'], s['file']), contenuto(s['file'], r['file'])
        if abs(ab - ba) >= 0.1:
            return x if ab > ba else y
    return x if (r.get('codice') or '') > (s.get('codice') or '') else y


# ── C01 copie della stessa causa ────────────────────────────────────────────────────────────────────────────────

def c01(banca, per_doc, per_causa):
    out = {}
    for (cid, caso), docs in per_causa.items():
        if len(docs) < 2:
            continue
        for d1, f1 in docs.items():
            for i, r in per_doc[(d1, caso)]:
                b, _ = brano(D.testo(f1), int(r.get('char_start') or 0), D_norm(f1))
                if len(b) < 100:
                    continue
                for d2, f2 in docs.items():
                    if d2 == d1:
                        continue
                    nb, pb = D_norm(f2); k = nb.find(b)
                    if k < 0:
                        continue
                    p2 = pb[min(k + FINESTRA, len(pb) - 1)]
                    vic = [(abs(int(s.get('char_start') or 0) - p2), j, s) for j, s in per_doc[(d2, caso)]
                           if abs(int(s.get('char_start') or 0) - p2) < VICINO]
                    if not vic:
                        continue
                    _, j, s = min(vic, key=lambda z: z[0])
                    e = chi_esce((i, r), (j, s), banca, per_doc)
                    if e is None:
                        continue
                    altra = s if e[0] == i else r
                    out.setdefault(e[0], ('C01', f"copia nella stessa causa (decisione del PI del 03/10, §63.70): lo stesso "
                                             f"brano sta nella riga {altra.get('codice')} dell'atto {altra['document_id']}"))
    return out


# ── C02 doppioni ────────────────────────────────────────────────────────────────────────────────────────────────

def c02(banca, per_doc, per_causa):
    out = {}
    for (doc, caso), righe in per_doc.items():
        if not righe:
            continue
        f = righe[0][1]['file']; t = D.testo(f)
        if not t:
            continue
        na, pa = D_norm(f)
        ordinate = sorted(righe, key=lambda z: int(z[1].get('char_start') or 0))
        for n, (i, r) in enumerate(ordinate):
            a = int(r.get('char_start') or 0)
            # a. stesso atto ripetuto: lo stesso brano altrove nello stesso atto, con la sua riga, e le pagine attorno
            #    uguali per piu' della meta' (un allegato ripetuto; non una nota ripetuta a sostegno di un'altra frase)
            b, j0 = brano(t, a, (na, pa))
            if len(b) >= 100:
                for k in (na.find(b), na.rfind(b)):
                    if k < 0 or abs(k - (j0 - FINESTRA)) < 1000:
                        continue
                    p2 = pa[min(k + FINESTRA, len(pa) - 1)]
                    vic = [(abs(int(s.get('char_start') or 0) - p2), j, s) for j, s in righe
                           if j != i and abs(int(s.get('char_start') or 0) - p2) < VICINO]
                    if not vic:
                        continue
                    _, j, s = min(vic, key=lambda z: z[0])
                    z1 = na[max(0, j0 - 1500):j0 + 1500]; z2 = na[max(0, k - 1500):k + 1500]
                    pezzi = [z1[q:q + 80] for q in range(0, max(1, len(z1) - 80), 150)]
                    if pezzi and sum(1 for p in pezzi if p in z2) / len(pezzi) >= 0.5:
                        e = chi_esce((i, r), (j, s), banca, per_doc)
                        if e is not None and e[0] == i:
                            out.setdefault(i, ('C02', f"doppione (stesso_atto_ripetuto): lo stesso brano, con le pagine attorno "
                                                      f"uguali, ha gia' la riga {s.get('codice')} nello stesso atto"))
            if i in out:
                continue
            # b. confine di nota falso: la riga precedente dello stesso caso e' a meno di 200 caratteri e in mezzo c'e' solo
            #    un «numero a capo» che non e' una nota («Rn. 182 ff.,\n214 ff.», un numero di ruolo che va a capo)
            if n:
                j, s = ordinate[n - 1]; c2 = int(s.get('char_start') or 0)
                if 0 < a - c2 < 200 and FALSO_CONFINE.search(t, c2, a + 1):
                    veri = [x for x in C.INIZIO_NOTA.finditer(t, c2, a + 1) if C.e_inizio_nota(t, x)
                            and not re.match(r'(?:ff?\.|et seq|\d)', t[x.end():x.end() + 6], re.I)]
                    if not veri and not giudicata(r):
                        out[i] = ('C02', f"doppione (confine_di_nota_falso): stessa citazione della riga {s.get('codice')}, "
                                         f"separata da un numero a capo che non e' una nota")
                        continue
            # c-e. corpo e la sua nota, traduzione, titolo di un allegato: le prove della rete descrittiva stretta
            #      (tools/descrittiva_stretta.py, controlli 5, 7, 8 e 9), valide per ogni riga
            if giudicata(r):
                continue
            mot = D.identita(i, r, per_doc, per_causa, quali=('5', '9'))
            if mot:
                out[i] = ('C02', 'doppione (' + mot + ')')
    return out


# ── C03 corpo e nota, traduzioni (approvata dal PI il 04/10/2026) ─────────────────────────────────────────────────

def c03(banca, per_doc, per_causa):
    """le coppie di tools/unisci_c03.py (stessa frase sostenuta testo/nota; traduzioni): esce la nota o la traduzione.
    Le coppie con una riga giudicata non si propongono (vanno in C03_giudicate_da_rivedere.tsv). La SCRITTURA di C03
    la fa tools/unisci_c03.py --scrivi, che mette sulla riga tenuta il campo proposto_nota_appoggio: escludi_righe.py
    non basta."""
    import unisci_c03 as U
    id_di = {r.get('codice'): i for i, r in banca.items() if r.get('codice')}
    out = {}
    for tipo, t, n, mot in U.coppie(banca):
        if giudicata(t) or giudicata(n):
            continue
        out[id_di[n['codice']]] = ('C03', 'C03 ' + mot + f' (unita_a: {t["codice"]})')
    return out


# ── C04 rete descrittiva stretta ────────────────────────────────────────────────────────────────────────────────

def c04(banca, per_doc, per_causa):
    out = {}
    for i, r in banca.items():
        if r.get('proposto_rete') == 'descrittiva' and not giudicata(r):
            resta, mot = D.giudica(i, r, banca, per_doc, per_causa)
            if not resta:
                out[i] = ('C04', "rete descrittiva stretta (tools/descrittiva_stretta.py): " + mot)
    return out


PASSI = (('C01', c01), ('C02', c02), ('C03', c03), ('C04', c04))
AUTOMATICHE = ('C01', 'C02', 'C03', 'C04')   # C03 approvata dal PI il 04/10/2026


def proponi(banca, regole=AUTOMATICHE, dal=None):
    """{id: (regola, motivo)} in ordine: C01, C02, (C03), C04 (una riga prende la prima regola che la tocca).
    Le righe uscite per una regola non fanno piu' da «riga gemella» per le regole dopo."""
    banca = dict(banca)
    tutte = {}
    for cod, passo in PASSI:
        if cod not in regole:
            continue
        per_doc, per_causa = indice(banca)
        nuove = {k: v for k, v in passo(banca, per_doc, per_causa).items() if k not in tutte}
        if dal:
            nuove = {k: v for k, v in nuove.items() if str(banca[k].get('creato_il') or '')[:10] >= dal}
        tutte.update(nuove)
        for k in nuove:
            banca[k] = dict(banca[k], proposto_rete='esclusa')
    return tutte


def leggi_vivo():
    from google.cloud import firestore   # sola lettura
    db = firestore.Client(project='climpact-drp'); banca = {}
    for caso in D.json.load(open(QUI/'pubblicazione'/'mappa'/'casi.json', encoding='utf-8'))['casi']:
        k = caso if isinstance(caso, str) else caso.get('id') or caso.get('caso')
        for d in db.collection('corpus_rows').where(filter=firestore.FieldFilter('caso_citato', '==', k)).stream():
            banca[d.id] = json.loads(json.dumps(d.to_dict(), default=str))
    return banca


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--banca', default=''); ap.add_argument('--vivo', action='store_true')
    ap.add_argument('--uscita', required=True); ap.add_argument('--solo-nuove-dal', default='')
    ap.add_argument('--regole', default=','.join(AUTOMATICHE)); a = ap.parse_args()
    banca = json.load(gzip.open(a.banca, 'rt', encoding='utf-8')) if a.banca else leggi_vivo()
    p = proponi(banca, tuple(a.regole.split(',')), a.solo_nuove_dal or None)
    with open(a.uscita, 'w', newline='', encoding='utf-8') as h:
        w = csv.writer(h, delimiter='\t'); w.writerow(['codice', 'motivo', 'regola', 'id', 'caso', 'estrazione'])
        for i, (reg, mot) in sorted(p.items(), key=lambda z: (z[1][0], banca[z[0]].get('codice') or '')):
            r = banca[i]
            w.writerow([r.get('codice'), mot, reg, i, r.get('caso_citato'), (r.get('provenienza') or {}).get('estrazione')])
    c = collections.Counter(v[0] for v in p.values())
    print('proposte di esclusione:', len(p), dict(sorted(c.items())), '->', a.uscita)
    print('per regola e ricerca:', dict(sorted(collections.Counter(
        (v[0], (banca[k].get('provenienza') or {}).get('estrazione')) for k, v in p.items()).items())))


if __name__ == '__main__':
    main()


# ── C07 pagine attorno che sono gia' una citazione propria (04/10/2026, caso ICJ-0154, decisione del PI) ──────────
#
# DUE CONTROLLI, basta uno: (1) POSIZIONE, il punto del nome (char_start) di un'altra riga viva per nome dello stesso
# caso nello stesso atto cade nella pagina candidata; (2) TESTO, la prova della pagina (proposto_estensione[].prova) e'
# la frase sostenuta, la frase della lettura o la citazione testuale dell'altra riga (rapidfuzz partial_ratio >= 90).
# DECISIONE DEL PI: se l'altra riga ha principi diversi (nessuno in comune), la pagina NON e' seguito: e' un'altra
# citazione collegata, si segna «also cited separately as <codice>», non conta come seguito e conta una volta sola nei
# numeri. Se un principio e' in comune, resta candidata e decide DeepSeek, col segno visibile.
# Misura a secco (training/misure/S07-PULIZIA-2026-10-04.md, «C07»): 17.871 pagine marcate su 27.263; 9.892 con principi
# diversi; il team ne aveva spuntate 43 come seguito (training/registri/C07_giudicate_spuntate_come_seguito_2026-10-04.tsv).

import functools


@functools.lru_cache(maxsize=200000)
def _n(s):
    import unicodedata
    s = unicodedata.normalize('NFKC', s or '').lower()
    return re.sub(r'\s+', ' ', re.sub(r'[^\w]+', ' ', s)).strip()


def _principi(r):
    return (set(r.get('validato_principi') or []) | set(r.get('proposto_principi') or [])) - {'nessuno'}


def pagine_gia_citate(riga, righe_stesso_atto, spazi_pagine):
    """{pagina: {'codici': [...], 'posizione': bool, 'testo': bool, 'seguito': bool, 'segno': str}}.
    `righe_stesso_atto`: le righe dello stesso document_id e caso; `spazi_pagine`: {pagina: (inizio, fine)} nel Markdown."""
    from rapidfuzz import fuzz
    altre = [s for s in righe_stesso_atto if s.get('codice') != riga.get('codice') and s.get('proposto_rete') in ATTIVE]
    out = {}
    for e in riga.get('proposto_estensione') or []:
        p = e.get('pagina')
        if p not in spazi_pagine:
            continue
        a, z = spazi_pagine[p]; pr = _n(e.get('prova')); trov = []
        for s in altre:
            pos = s.get('char_start') not in (None, '') and a <= int(s['char_start']) < z
            txt = False
            if len(pr) >= 30 and not pos:
                for x in (s.get('proposto_frase_sostenuta'), s.get('proposto_frase_lettura'), s.get('proposto_citazione_testuale')):
                    x = _n(x)
                    if len(x) >= 40 and (fuzz.partial_ratio(pr, x, score_cutoff=90) if len(pr) <= len(x) else fuzz.partial_ratio(x, pr, score_cutoff=90)):
                        txt = True; break
            if pos or txt:
                trov.append((s, pos, txt))
        if not trov:
            continue
        stesso = any(_principi(riga) & _principi(s) for s, _, _ in trov)
        cod = sorted(s.get('codice') for s, _, _ in trov)
        out[p] = {'codici': cod, 'posizione': any(x[1] for x in trov), 'testo': any(x[2] for x in trov),
                  'seguito': stesso, 'segno': segno_c07(cod)}
    return out


def segno_c07(codici):
    """il testo che pannello, domanda a DeepSeek e dati della mappa mostrano accanto alla pagina (inglese)"""
    return 'also cited separately as ' + ', '.join(codici)
