#!/usr/bin/env python3
"""LA RETE DESCRITTIVA (S07, 04/10/2026): le pagine che citano una delle sei pronunce SENZA nessuna forma dichiarata.

    python tools/rete_descrittiva.py --caso neubauer [--uscita index/descrittive_neubauer_2026-10-04-S07.csv]

PERCHE'. La revisione del 04/10/2026 (scratchpad della sessione, audit/forme: scan.py, conteggi.json, il campione letto)
ha trovato 331 pagine che citano una pronuncia senza nessuna forma del nome, ~250 citazioni vere: «BVerfG, a.a.O.»
nelle ordinanze sui ricorsi dei Länder, «독일 연방헌법재판소» nei ricorsi coreani, «IACtHR Advisory Opinion (2025),
para. 350», «ICJ, Climate AO, Joint Declaration...». La rete per nome non le vede per costruzione.

COME. Le regole stanno nel file del caso, `cited-cases/<caso>-S07.yaml`, chiave `rete_descrittiva` (vedi la testa di
quel blocco): un'ancora, le parole che devono stare a meno di `finestra` caratteri, un'eventuale `escludi`, e
`solo_atti_col_nome`. Si applicano al testo NORMALIZZATO (le regole di `textnorm.normalize`: spazi e trattini
tipografici, sillabazione di fine riga tolta, spazi uniti), e la posizione si riporta a quella del file con una mappa
carattere per carattere: `char_start` e' la posizione nel Markdown, come per la rete per nome.
Fuori, come nella misura:
  - gli atti del procedimento stesso (`escludi_case_id`, `atti_del_procedimento_altrove`);
  - gli atti datati prima della pronuncia (la data del documento dal nome del file d'origine; senza data si tengono);
  - le pagine dove il caso e' gia' nominato (una forma della ricerca per nome S07 nella pagina) o ha gia' una riga in
    piattaforma (`--pagine-con-riga`, un JSON di coppie [document_id, pagina], lo prepara tools/recupero_s07.py).
Le corrispondenze vicine si raggruppano con la stessa regola della rete per nome (`cerca_s07.fondi`: 200 caratteri, mai
attraverso una nota a pie' di pagina). Una riga ha `rete = descrittiva`, `forma_trovata` = «descrizione: <regola>:
<testo>», `regola_descrittiva` = gli id delle regole. La deduplica e' quella di S07 (stesso atto, stessa pagina).

Uscita: un CSV con le stesse colonne della ricerca per nome (piu' `regola_descrittiva`), e il .SCARTI.csv.
"""
import argparse
import collections
import csv
import json
import re
import sys
import time
from pathlib import Path

QUI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI / 'tools'))
sys.path.insert(0, str(QUI))
import textnorm  # noqa: E402
import cerca_s07 as S7  # noqa: E402

B = S7.BASE
DATA = '2026-10-04'
INV = '­​‌‍﻿'


# ── il testo normalizzato con la mappa delle posizioni ────────────────────────────────────────────────────────────

_TAB = {**textnorm.SPACES, **textnorm.DASHES, **textnorm.QUOTES}
_SILLABA = re.compile(r'(?<=\w)-[ \t]*\r?\n\s*(?=\w)')
_SPAZI = re.compile(r'\s+')


def _togli(s, idx, patt, con=''):
    """sostituisce ogni corrispondenza di `patt` con `con` (al massimo un carattere), tenendo la mappa"""
    out, oi, prec = [], [], 0
    for m in patt.finditer(s):
        out.append(s[prec:m.start()]); oi.extend(idx[prec:m.start()])
        if con:
            out.append(con); oi.append(idx[m.start()])
        prec = m.end()
    out.append(s[prec:]); oi.extend(idx[prec:])
    return ''.join(out), oi


def piatto_con_mappa(t):
    """(testo normalizzato, mappa): mappa[i] e' la posizione nel testo originale del carattere i del normalizzato.
    Le regole di textnorm.normalize (spazi, trattini e virgolette tipografiche; caratteri invisibili tolti; sillabazione
    di fine riga ricongiunta) e in piu' gli spazi uniti, come la misura del 04/10 (audit/forme/scan.py `piatto`)."""
    out, idx = [], []
    for i, c in enumerate(t):
        c2 = _TAB.get(c, c)
        if c2 == '' or c in INV:
            continue
        out.append(c2); idx.append(i)
    s = ''.join(out)
    s, idx = _togli(s, idx, _SILLABA)
    s, idx = _togli(s, idx, _SPAZI, ' ')
    return s, idx


# ── le regole ──────────────────────────────────────────────────────────────────────────────────────────────────

def leggi_regole(percorso):
    import yaml
    dati = yaml.safe_load(Path(percorso).read_text(encoding='utf-8')) or {}
    rd = dati.get('rete_descrittiva') or {}
    regole = []
    for r in rd.get('regole') or []:
        regole.append({'id': r['id'], 'ancora': re.compile(r['ancora'], re.I),
                       'con': [re.compile(x, re.I) for x in (r.get('con') or [])],
                       'finestra': int(r.get('finestra') or 0),
                       'escludi': re.compile(r['escludi'], re.I) if r.get('escludi') else None,
                       'solo_atti_col_nome': bool(r.get('solo_atti_col_nome'))})
    altrove = {str(x.get('documento')) for x in (dati.get('atti_del_procedimento_altrove') or []) if x.get('documento')}
    return regole, altrove


def corrispondenze_descrittive(testo, inizio, regole, col_nome):
    """[(posizione nel file, fine nel file, id della regola, testo trovato)] in ordine, senza sovrapposizioni (a parita'
    di inizio vince la prima regola). `col_nome`: l'atto cita gia' il caso col nome (per `solo_atti_col_nome`)."""
    s, idx = piatto_con_mappa(testo[inizio:])
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
            a = inizio + idx[m.start()]
            b = inizio + idx[m.end() - 1] + 1
            trovate.append((a, b, r['id'], m.group(0)))
    trovate.sort()
    out, fine = [], -1
    for x in trovate:
        if x[0] >= fine:
            out.append(x); fine = x[1]
    return out


class _M:
    """una corrispondenza descrittiva con l'interfaccia di re.Match che serve a `fondi`"""
    def __init__(self, a, b, regola, s):
        self._a, self._b, self.regola, self.s = a, b, regola, s

    def start(self):
        return self._a

    def end(self):
        return self._b

    def group(self, _=0):
        return self.s


def e_nome_descrittiva(testo, m):
    return True     # una descrizione apre sempre una citazione oltre i 200 caratteri, come un nome


# ── la rete ────────────────────────────────────────────────────────────────────────────────────────────────────

def rete(percorso_caso, pagine_con_riga=frozenset(), file=None, conf=None):
    """Le righe della rete descrittiva di un caso, nella forma di `rete_lessicale` (dim, meta, file, char_start, ...)."""
    conf = conf or S7.leggi_caso(percorso_caso)
    regole, altrove = leggi_regole(percorso_caso)
    nome = B.regex_caso(conf)
    esclusi = conf.get('escludi_case_id') or []
    esclusi = [esclusi] if isinstance(esclusi, str) else list(esclusi)
    esclusi = [str(x).lower() for x in esclusi if str(x).strip()]
    dmin = str(conf.get('data_decisione') or '')[:10]
    fuori, conti = [], collections.Counter()
    files = sorted(B.MD.rglob('*.md')) if file is None else [Path(x) if Path(x).is_absolute() else QUI / x for x in file]
    for md in files:
        testo = md.read_text(encoding='utf-8', errors='replace')
        meta, inizio = B.front_matter(testo)
        cid = (meta.get('case_id') or '').lower()
        if any(x in cid for x in esclusi) or meta.get('document_id') in altrove:
            continue
        dd = B.data_documento(meta)
        col_nome = bool(nome.search(testo, inizio))
        ms = corrispondenze_descrittive(testo, inizio, regole, col_nome)
        if not ms:
            continue
        if dd and dmin and dd < dmin:
            conti['anteriori'] += len(ms)
            continue
        marks = B.pagine(testo)
        ms = [_M(*x) for x in ms]
        # le pagine col nome del caso: la rete per nome le copre gia'
        tenute = []
        for m in ms:
            pag = B.pagina_di(marks, m.start())
            blocco, off = B.blocco_pagina(testo, marks, m.start())
            if nome.search(blocco):
                conti['pagina_col_nome'] += 1
                continue
            if (meta.get('document_id'), pag) in pagine_con_riga:
                conti['pagina_con_riga'] += 1
                continue
            tenute.append(m)
        if not tenute:
            continue
        salva_e_nome = B.e_nome
        B.e_nome = e_nome_descrittiva
        try:
            fuse = B.fondi(testo, tenute)
        finally:
            B.e_nome = salva_e_nome
        for f in fuse:
            m = f[0]
            regole_qui = [x.regola for x in tenute if f[0].start() <= x.start() <= f[2]]
            blocco, off_rel = B.blocco_pagina(testo, marks, m.start())
            conti['gruppi'] += 1
            fuori.append({
                'dim': B.calcola_dimensioni(meta, blocco, off_rel, testo[:m.start()]),
                'meta': meta, 'file': str(md.relative_to(QUI)),
                'char_start': m.start(),
                'pagina': B.pagina_di(marks, m.start()),
                'forma': 'descrizione: ' + ' + '.join(dict.fromkeys(
                    f'{x.regola}: {B.forma_normalizzata(x.s)}' for x in tenute if f[0].start() <= x.start() <= f[2])),
                'regola_descrittiva': ' + '.join(dict.fromkeys(regole_qui)),
                'testo_trovato': testo[m.start():m.end()],
                'verbatim': re.sub(r'\s+', ' ', B.PAGE_RE.sub(
                    ' ', testo[max(inizio, m.start() - B.PRIMA):m.start() + B.DOPO])).strip(),
                'finestra': B.finestra_pagina(testo, marks, m.start()),
                'rete': 'descrittiva', 'punteggio': '',
            })
    return fuori, conti


def riga_csv(r, cb_versione):
    """la riga del CSV, con le colonne della ricerca per nome (cerca_s05.main) piu' `regola_descrittiva`"""
    m = r['meta']
    return {
        'case_id': m.get('case_id', ''), 'case_name': m.get('case_name', ''), 'giurisdizioni': m.get('giurisdizioni', ''),
        'document_id': m.get('document_id', ''), 'tipo_atto': m.get('tipo_atto', ''),
        'tipo_atto_sabin': m.get('tipo_atto_sabin', ''), 'data': m.get('data_deposito', ''), 'pagina': r['pagina'],
        'data_documento': B.data_documento(m), 'rete': 'descrittiva', 'sonda': '', 'punteggio': '',
        'punteggio_riordino': '', 'copie': '', 'anteriore': '', 'punteggio_escluse': '', 'margine': '', 'sospetto': '',
        'forma_trovata': r['forma'], 'citazione_testuale': r['verbatim'], 'finestra_pagina': r['finestra'],
        'chi_cita_auto': r['dim']['chi_cita_auto'], 'posizione_auto': '', 'sede_auto': r['dim']['sede_auto'],
        'dimensioni_confidenza': r['dim']['dimensioni_confidenza'], 'chi_parla': r['dim']['chi_cita_auto'],
        'posizione': '', 'sede': r['dim']['sede_auto'], 'tipo_citazione': '', 'annidata': '',
        'proposizione_sostenuta': '', 'confidenza': '', 'note': '', 'file': r['file'], 'char_start': r['char_start'],
        'url_documento': m.get('url_documento', ''), 'codebook_versione': cb_versione,
        'regola_descrittiva': r['regola_descrittiva'], 'testo_trovato': r.get('testo_trovato', ''),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--caso', required=True)
    ap.add_argument('--uscita', default='')
    ap.add_argument('--pagine-con-riga', default='', help='JSON: [[document_id, pagina], ...] delle righe del caso')
    ap.add_argument('--senza-pdf', action='store_true', help='non leggere corpo/nota dal PDF (prove)')
    ap.add_argument('--file-elenco', default='', help='JSON: i Markdown da leggere (un lotto), invece di tutto markdown/')
    a = ap.parse_args()
    percorso = Path(a.caso) if Path(a.caso).exists() else QUI / 'cited-cases' / f'{a.caso}-S07.yaml'
    caso = re.sub(r'-S\d\d$', '', percorso.stem)
    pcr = frozenset()
    if a.pagine_con_riga:
        pcr = frozenset((d, int(p)) for d, p in json.load(open(a.pagine_con_riga, encoding='utf-8')))
    cb = (QUI / 'codebook' / 'citazioni.yaml').read_text(encoding='utf-8')
    mv = re.search(r'^versione:\s*(.+)$', cb, re.M)
    cbv = mv.group(1).strip() if mv else 'assente'
    t0 = time.time()
    fuori, conti = rete(percorso, pcr, file=json.load(open(a.file_elenco, encoding='utf-8')) if a.file_elenco else None)
    print(f'{caso}: rete descrittiva {len(fuori)} gruppi in {time.time() - t0:.0f}s', dict(conti), flush=True)
    righe = [riga_csv(r, cbv) for r in fuori]
    scarti = []
    righe = S7.deduplica(righe, scarti)
    if not a.senza_pdf:
        for r in righe:
            pdf = QUI / r['file'].replace('markdown/', 'documents/').replace('.md', '.pdf')
            pos, cpos = B.posizione_pdf(pdf, int(r['pagina']), r['citazione_testuale']) if pdf.exists() \
                else ('non_determinabile', 'bassa')
            r['posizione_auto'] = r['posizione'] = pos
            if cpos == 'bassa' and r['dimensioni_confidenza'] != 'bassa':
                r['dimensioni_confidenza'] = 'media'
        B.chiudi_pdf()
    righe.sort(key=lambda x: (x['case_name'], x['document_id'], x['pagina']))
    out = QUI / (a.uscita or f'index/descrittive_{caso}_{DATA}-S07.csv')
    campi = list(riga_csv({'meta': {}, 'pagina': 0, 'forma': '', 'verbatim': '', 'finestra': '', 'file': '',
                           'char_start': 0, 'regola_descrittiva': '',
                           'dim': {'chi_cita_auto': '', 'sede_auto': '', 'dimensioni_confidenza': ''}}, '').keys()) \
        + ['stesso_testo_di']
    with open(out, 'w', newline='', encoding='utf-8') as h:
        w = csv.DictWriter(h, fieldnames=campi, extrasaction='ignore')
        w.writeheader(); w.writerows(righe)
    with open(out.with_name(out.stem + '.SCARTI.csv'), 'w', newline='', encoding='utf-8') as h:
        w = csv.DictWriter(h, fieldnames=campi + ['motivo_scarto'], extrasaction='ignore')
        w.writeheader(); w.writerows(scarti)
    print(f'{caso}: righe {len(righe)}, copie sulla stessa pagina {len(scarti)}, documenti '
          f'{len({r["document_id"] for r in righe})}, regole {dict(collections.Counter(r["regola_descrittiva"] for r in righe))}'
          f' -> {out.relative_to(QUI)}')
    json.dump({'caso': caso, 'righe': len(righe), 'conti': dict(conti)},
              open(out.with_suffix('.conti.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    import giornale  # il giornale delle operazioni: ogni esecuzione, i file, le scritture, gli errori
    giornale.avvia()
    raise SystemExit(main())
