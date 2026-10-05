#!/usr/bin/env python3
"""S08, IL CARICAMENTO DELLE RIGHE NUOVE (05/10/2026).

    python tools/carica_righe_s08.py                # ANTEPRIMA: conti, due righe intere, verifiche. Non scrive niente.
    python tools/carica_righe_s08.py --scrivi       # copia_prima, poi scrittura a lotti di 400 (lo lancia la coordinatrice)

LE RIGHE. Sono le 376 citazioni «nuove» recuperate da S08 (rete descrittiva senza il filtro della pagina, esito «nuova» in
training/s08/recuperate_2026-10-04.tsv): citazioni dello stesso caso che S07 perdeva perche' la pagina aveva gia' il nome o
una riga. Diventano righe di `corpus_rows` IDENTICHE per forma alle righe descrittive di S07 (`recupero_s07.documenti`):
stessi campi di `pubblica.documento`, `proposto_rete` «descrittiva», codice dopo il piu' alto del caso, riga FUORI DALLE CODE
(`assegnato_a_in_attesa`, la rimette nelle code chi la completa: `recupero_s07.py rimetti`), id da `pubblica.id_riga`.

LE DIFFERENZE DA S07 (tutte e sole):
  - `provenienza.estrazione` e `esecuzione_id` dicono S08; `causa_s07` e' sostituita da `causa_s08` = «S08_stessa_pagina»;
  - il verdetto di C04 (`c04_resta`, `c04_motivo`) e' un INDIZIO scritto sulla riga, NON un'esclusione: C04 scarta per
    sbaglio la citazione di Children of Austria p. 29 (la data del Klimabeschluss, «2021»), e S08 sta prima di C04 nel ciclo;
  - `s08_vicina_*`: la riga viva piu' vicina dello stesso atto e caso entro `SOGLIA_S08` caratteri (codice, id, distanza):
    cosi' la coppia S08 si forma da sola, senza ricalcolarla dalla fotografia.

LE COPIE (05/10/2026, il PI: «allinealo al migliore»): come S07, una citazione trovata in due copie dello stesso documento
(lo stesso atto pubblicato sotto piu' cause) e' UNA: classe `Copie`, con le regole e le funzioni di recupero_s06/recupero_s07
(impronte, frammento, scelta della copia dalla scheda del catalogo, atti di D04 e righe di S06 rimandati). La scrittura
rifiuta comunque ogni id gia' in banca. La banca si legge DAL VIVO, mai da una fotografia.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime
import gzip
import json
import pathlib
import random
import sys

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI / 'tools'))
sys.path.insert(0, str(QUI))
csv.field_size_limit(10**9)

import coppie_vicine as CV  # noqa: E402
import rete_descrittiva as RD  # noqa: E402

B = CV.B
S8 = QUI / 'training' / 's08'
TSV = S8 / 'recuperate_2026-10-04.tsv'
SCANSIONE = S8 / 'scansione_2026-10-04.json'
DATA = '2026-10-05'
ESTRAZIONE = 'S08'
CAUSA = 'S08_stessa_pagina'
SOGLIA = CV.SOGLIA_S08
PREFISSI = {'urgenda': 'URG', 'neubauer': 'NEU', 'future-generations': 'FGC', 'klimaseniorinnen': 'KLS',
            'cig-parere-clima': 'ICJ', 'idh-oc-32-25': 'IAC'}
MOTIVO = ("citazione sulla stessa pagina di un'altra riga dello stesso caso, che la deduplica della pagina di S07 "
          "perdeva, recuperata da S08 (coppie vicine, 05/10/2026)")
LOTTO = 400
ATTIVE = ('lessicale', 'entrambe', 'descrittiva')   # le reti vive, come tools/unisci_c03.py
# il caso di prova (caso, fine dell'atto, pagina, char_start della riga NUOVA, char_start della riga viva con cui fa coppia):
# Children of Austria p. 29 e BMW p. 10
ATTESE = (('neubauer', '_6a3b', 29, 69272, 70664), ('neubauer', '_d48d', 10, 57336, 58268))


def ora():
    return datetime.datetime.now().strftime('%Y%m%d_%H%M%S')


def db_():
    from google.cloud import firestore
    return firestore.Client(project='climpact-drp')


class Banca:
    """La banca dati VIVA, in sola lettura (`google.cloud.firestore`, progetto climpact-drp, collezione corpus_rows)."""

    def __init__(self, db=None):
        self.db = db or db_()

    def caso(self, caso):
        """[(id, dict)] di un caso"""
        from google.cloud import firestore
        return [(d.id, d.to_dict()) for d in self.db.collection('corpus_rows')
                .where(filter=firestore.FieldFilter('caso_citato', '==', caso)).stream()]

    def tutta(self, casi=CV.CASI):
        """{id: riga} dei casi indicati, con i valori resi serializzabili"""
        return {i: json.loads(json.dumps(r, default=str)) for c in casi for i, r in self.caso(c)}

    def esiste(self, ids):
        """gli id che esistono GIA' (lettura per id: non dipende dal caso)"""
        ids = list(ids)
        gia = set()
        for k in range(0, len(ids), 300):
            refs = [self.db.collection('corpus_rows').document(i) for i in ids[k:k + 300]]
            gia |= {d.id for d in self.db.get_all(refs) if d.exists}
        return gia


class Nuove:
    """Le righe «nuove» di S08, ricostruite dal Markdown vivo con le stesse colonne del CSV descrittivo di S07
    (`rete_descrittiva.riga_csv`): finestra, citazione, dimensioni, posizione nel PDF."""

    def __init__(self, tsv=TSV, scansione=SCANSIONE):
        self.tsv = pathlib.Path(tsv)
        self.scansione = pathlib.Path(scansione)
        self._regole = {}
        cb = (QUI / 'codebook' / 'citazioni.yaml').read_text(encoding='utf-8')
        import re
        m = re.search(r'^versione:\s*(.+)$', cb, re.M)
        self.codebook = m.group(1).strip() if m else 'assente'

    def elenco(self):
        """le righe del TSV con esito «nuova», nell'ordine del file"""
        with open(self.tsv, newline='', encoding='utf-8') as h:
            return [r for r in csv.DictReader(h, delimiter='\t') if r['esito'] == 'nuova']

    def _scansione(self):
        d = json.load(open(self.scansione, encoding='utf-8'))
        return {f'S08-{r["caso_citato"]}-{r["document_id"][-8:]}-{r["char_start"]}': r for r in d['recuperate']}

    def regole(self, caso):
        if caso not in self._regole:
            self._regole[caso] = RD.leggi_regole(QUI / 'cited-cases' / f'{caso}-S07.yaml')[0]
        return self._regole[caso]

    def riga(self, t, s):
        """la riga nel formato del CSV di S07: `t` = riga del TSV, `s` = gruppo della scansione"""
        caso = s['caso_citato']
        md = QUI / s['file']
        testo = md.read_text(encoding='utf-8', errors='replace')
        meta, inizio = B.front_matter(testo)
        cs = int(s['char_start'])
        marks = B.pagine(testo)
        blocco, off = B.blocco_pagina(testo, marks, cs)
        dim = B.calcola_dimensioni(meta, blocco, off, testo[:cs])
        # il testo che la regola ha trovato: la prima corrispondenza del gruppo, ricalcolata (la scansione non la salva)
        nome = B.regex_caso(CV.S7.leggi_caso(QUI / 'cited-cases' / f'{caso}-S07.yaml'))
        trovato = ''
        for m in RD.corrispondenze_descrittive(testo, inizio, self.regole(caso), bool(nome.search(testo, inizio))):
            if m[0] == cs:
                trovato = testo[m[0]:m[1]]
                break
        pdf = QUI / s['file'].replace('markdown/', 'documents/').replace('.md', '.pdf')
        pagina = int(s['pagina'])
        verb = RD.re.sub(r'\s+', ' ', B.PAGE_RE.sub(' ', testo[max(inizio, cs - B.PRIMA):cs + B.DOPO])).strip()
        pos, cpos = B.posizione_pdf(pdf, pagina, verb) if pdf.exists() else ('non_determinabile', 'bassa')
        conf = dim['dimensioni_confidenza']
        if cpos == 'bassa' and conf != 'bassa':
            conf = 'media'
        return {
            'case_id': meta.get('case_id', ''), 'case_name': meta.get('case_name', ''),
            'giurisdizioni': meta.get('giurisdizioni', ''), 'document_id': meta.get('document_id', ''),
            'tipo_atto': meta.get('tipo_atto', ''), 'tipo_atto_sabin': meta.get('tipo_atto_sabin', ''),
            'data': meta.get('data_deposito', ''), 'pagina': pagina, 'data_documento': B.data_documento(meta),
            'rete': 'descrittiva', 'sonda': '', 'punteggio': '', 'punteggio_riordino': '', 'copie': '', 'anteriore': '',
            'punteggio_escluse': '', 'margine': '', 'sospetto': '', 'forma_trovata': s['forma'],
            'citazione_testuale': verb, 'finestra_pagina': B.finestra_pagina(testo, marks, cs),
            'chi_cita_auto': dim['chi_cita_auto'], 'posizione_auto': pos, 'sede_auto': dim['sede_auto'],
            'dimensioni_confidenza': conf, 'chi_parla': dim['chi_cita_auto'], 'posizione': pos, 'sede': dim['sede_auto'],
            'tipo_citazione': '', 'annidata': '', 'proposizione_sostenuta': '', 'confidenza': '', 'note': '',
            'file': s['file'], 'char_start': cs, 'url_documento': meta.get('url_documento', ''),
            'codebook_versione': self.codebook, 'regola_descrittiva': s['regola_descrittiva'], 'testo_trovato': trovato,
            'caso': caso, 'chiave': t['chiave'],
            'c04_resta': t['c04_resta'] == 'True', 'c04_motivo': t['c04_motivo']}

    def righe(self):
        scan = self._scansione()
        out = []
        for t in self.elenco():
            if t['chiave'] not in scan:
                raise SystemExit(f"la riga {t['chiave']} del TSV non e' nella scansione")
            out.append(self.riga(t, scan[t['chiave']]))
        B.chiudi_pdf()
        return out


class Copie:
    """Le copie dello STESSO DOCUMENTO in piu' atti, con le regole di S07 (`recupero_s07.fase_righe`, 04/10/2026).

    Il Sabin Center pubblica a volte lo stesso documento sotto piu' cause (stesso PDF o stesso testo: `recupero_s06.
    impronte`). La stessa citazione trovata in due copie e' UNA citazione. Una riga nuova esce se:
      1. il suo atto e' lo stesso documento di un altro atto che ha gia' una riga viva del caso con lo stesso frammento
         (`recupero_s06.chiave_testo`): la citazione c'e' gia', nell'altra copia;
      2. fra le righe nuove, un'altra copia dello stesso frammento e' gia' presa: quale copia tiene la riga lo dicono i
         metadati del catalogo (`recupero_s07.scegli_per_scheda`), non l'ordine dei percorsi;
      3. il suo atto e' di D04 e il ciclo D04 non ha ancora scritto le sue righe (D04 si ferma se trova righe non sue),
         o il suo id e' di S06: si rifanno dopo, come in S07.
    La riga tenuta porta gli altri case_id in `stesso_documento_case_ids`. Le uscite si scrivono in
    training/s08/escluse_copie_s08.jsonl col motivo.
    """

    def __init__(self, banca_viva):
        import recupero_s06 as R6
        import recupero_s07 as R7
        self.R6, self.R7 = R6, R7
        self.banca = banca_viva
        self.cache = {}
        self.d04 = R7.documenti_d04() if not R7.d04_scritte() else set()
        self.s06 = R7.ids_s06()

    def impronte(self, file):
        return self.R6.impronte(file, self.cache) if file and (QUI / file).exists() else {'pdf': '', 'testo': ''}

    def chiave(self, r):
        return self.R6.chiave_testo({'citazione_testuale': r.get('citazione_testuale') or ''})

    def _vive(self, caso):
        """{chiave del frammento: [(document_id, case_id, impronte)]} delle righe vive del caso (qualunque rete viva)"""
        out = collections.defaultdict(list)
        for x in self.banca.values():
            if x.get('caso_citato') == caso and x.get('proposto_rete') in ATTIVE and x.get('citazione_testuale'):
                out[self.chiave(x)].append((x['document_id'], x.get('case_id'), self.impronte(x.get('file'))))
        return out

    def separa(self, righe, id_di):
        """(tenute, escluse): le righe nuove senza le copie dello stesso documento"""
        tenute, escluse, vive = [], [], {}
        prese = collections.defaultdict(list)       # (caso, frammento) -> [(document_id, file, case_id, impronte)]
        for r in sorted(righe, key=lambda r: (r['caso'], r['document_id'], int(r['char_start']))):
            rid, caso = id_di(r), r['caso']
            if r['document_id'] in self.d04 or rid in self.s06:
                escluse.append({**self._segno(r, rid), 'perche': 'atto di D04 non ancora scritto, o riga di S06'})
                continue
            if caso not in vive:
                vive[caso] = self._vive(caso)
            k, mie = self.chiave(r), self.impronte(r['file'])
            gia = next(((d, c, p) for d, c, imp in vive[caso][k] if d != r['document_id']
                        for p in [self.R6.stesso_documento(mie, imp)] if p), None)
            if gia:
                escluse.append({**self._segno(r, rid), 'uguale_a_documento': gia[0], 'uguale_a_case_id': gia[1],
                                'perche': f"{gia[2]}: la citazione c'e' gia', riga viva nell'altra copia"})
                continue
            uguale = next(((i, p) for i, (d, f, c, imp) in enumerate(prese[(caso, k)]) if d != r['document_id']
                           for p in [self.R6.stesso_documento(mie, imp)] if p), None)
            if uguale is None:
                tenute.append(r)
                prese[(caso, k)].append((r['document_id'], r['file'], r.get('case_id'), mie))
                continue
            i, perche = uguale
            altra = next(t for t in tenute if t['document_id'] == prese[(caso, k)][i][0] and self.chiave(t) == k)
            scelta, _ = self.R7.scegli_per_scheda([altra['file'], r['file']])
            tieni, esce = (r, altra) if scelta == r['file'] else (altra, r)
            if tieni is r:
                tenute[tenute.index(altra)] = r
                prese[(caso, k)][i] = (r['document_id'], r['file'], r.get('case_id'), mie)
            escluse.append({**self._segno(esce, id_di(esce)), 'uguale_a_documento': tieni['document_id'],
                            'uguale_a_case_id': tieni.get('case_id'), 'perche': perche + ', copia scelta dalla scheda'})
        altri = collections.defaultdict(set)
        for e in escluse:
            if e.get('uguale_a_documento'):
                altri[e['uguale_a_documento']].add(e['case_id'])
        for t in tenute:
            if t['document_id'] in altri:
                t['stesso_documento_case_ids'] = sorted(altri[t['document_id']] - {t.get('case_id')})
        return tenute, escluse

    @staticmethod
    def _segno(r, rid):
        return {'id': rid, 'caso': r['caso'], 'document_id': r['document_id'], 'case_id': r.get('case_id'),
                'pagina': r.get('pagina'), 'char_start': r['char_start']}


class Caricatore:
    """Trasforma le righe nuove in documenti di `corpus_rows`, uguali per forma a quelli di S07."""

    def __init__(self, banca_viva):
        self.banca = banca_viva                     # {id: riga} dal vivo
        self.per_atto = CV.righe_per_atto(banca_viva)

    @staticmethod
    def id_di(r):
        from pubblica import id_riga
        return id_riga(r['caso'], r['document_id'], int(r['char_start']))

    def vicina(self, r, soglia=SOGLIA):
        """la riga viva piu' vicina dello stesso atto e caso entro `soglia` caratteri: (codice, id, distanza) o None"""
        v = self.per_atto.get((r['document_id'], r['caso'])) or []
        cs = int(r['char_start'])
        best = min(((abs(p - cs), i) for p, i, _ in v), default=None)
        if best is None or best[0] > soglia:
            return None
        i = best[1]
        return self.banca[i].get('codice') or '', i, best[0]

    def documenti(self, righe):
        """{id: documento} per tutte le righe, come `recupero_s07.documenti` (codici dopo il piu' alto del caso)"""
        from posizione_dopo_ocr import PRIMA
        from pubblica import documento
        import recupero_s06 as R6
        import re
        nuovi_md = R6.markdown_d03()
        out = {}
        for caso in sorted({r['caso'] for r in righe}):
            esist = [(i, x) for i, x in self.banca.items() if x.get('caso_citato') == caso]
            pre = PREFISSI[caso]
            n = max((int(m.group(1)) for _, x in esist
                     for m in [re.fullmatch(rf'{pre}-(\d+)', str(x.get('codice') or ''))] if m), default=0)
            chi = sorted({x.get('assegnato_a') or x.get('assegnato_a_in_attesa') for _, x in esist
                          if x.get('proposto_rete') in ('lessicale', 'entrambe') and not x.get('esito')
                          and (x.get('assegnato_a') or x.get('assegnato_a_in_attesa'))})
            rnd = random.Random(f'{caso}-{DATA}-{ESTRAZIONE}')
            mie = sorted((r for r in righe if r['caso'] == caso), key=lambda r: (r['document_id'], int(r['char_start'])))
            for k, r in enumerate(mie):
                rid = self.id_di(r)
                if rid in self.banca:
                    raise ValueError(f"riga gia' in banca dati: {rid}")
                d = documento(dict(r), caso)
                n += 1
                prov = {'corpus': 'D03' if r['file'] in nuovi_md else 'D01', 'estrazione': ESTRAZIONE, 'tipo': '',
                        'principi': {}, 'composizione': '', 'seguito': ''}
                if (PRIMA / pathlib.Path(r['file']).name).exists():
                    prov['ocr'] = DATA
                d.update({'corroborazione': 'descrizione', 'ordine': random.Random(rid).random(),
                          'codice': f'{pre}-{n:04d}', 'assegnato_a_in_attesa': chi[k % len(chi)] if chi else None,
                          'campione_cieco': rnd.random() < 0.20, 'incerta': False, 'provenienza': prov,
                          'motivo_aggiunta': MOTIVO, 'causa_s08': CAUSA, 'esecuzione_id': f'{caso}__nomi__{DATA}-{ESTRAZIONE}',
                          'proposto_rete': 'descrittiva', 'trovata_per_descrizione': True,
                          'regola_descrittiva': r.get('regola_descrittiva', ''), 'testo_trovato': r.get('testo_trovato', ''),
                          'c04_resta': r['c04_resta'], 'c04_motivo': r['c04_motivo']})
                if r.get('stesso_documento_case_ids'):
                    d['stesso_documento_case_ids'] = r['stesso_documento_case_ids']
                v = self.vicina(r)
                if v:
                    d.update({'s08_vicina_codice': v[0], 's08_vicina_id': v[1], 's08_vicina_distanza': v[2]})
                out[rid] = d
        return out


def verifiche(docs, righe, gia):
    """[(descrizione, esito, dettaglio)]: nessun id gia' in banca, id unici, i due casi di prova presenti"""
    v = [('nessun id gia\' in banca (lettura dal vivo)', not gia, f'{len(gia)} gia\' presenti'),
         ('id e codici unici', len(docs) == len(righe) and len({d['codice'] for d in docs.values()}) == len(docs),
          f'{len(docs)} documenti per {len(righe)} righe')]
    for caso, fine, pagina, inizio, viva in ATTESE:
        trov = [d for d in docs.values() if d['caso_citato'] == caso and d['document_id'].endswith(fine)
                and d['proposto_pagina'] == pagina and d['char_start'] == inizio
                and d.get('s08_vicina_id', '').endswith(f'__{viva}')]
        v.append((f'{caso} ...{fine} p. {pagina} (char {inizio}, coppia con la viva a {viva}) presente', len(trov) == 1,
                  trov[0]['codice'] + (f" (vicina {trov[0]['s08_vicina_codice']} a {trov[0]['s08_vicina_distanza']})"
                                       if trov and 's08_vicina_codice' in trov[0] else '') if trov else 'mancante'))
    return v


def anteprima(docs, gia, righe):
    per = collections.Counter(d['caso_citato'] for d in docs.values())
    con = collections.Counter(d['caso_citato'] for d in docs.values() if 's08_vicina_id' in d)
    print(f'{len(docs)} righe nuove (esito «nuova» del TSV)')
    for caso in CV.CASI:
        print(f'  {caso:20s} {per[caso]:4d}   con una riga viva entro {SOGLIA}: {con[caso]:4d}   sole: {per[caso] - con[caso]:4d}')
    print(f'  TOTALE               {len(docs):4d}   con una riga viva entro {SOGLIA}: {sum(con.values()):4d}   '
          f'sole: {len(docs) - sum(con.values()):4d}')
    print(f"  indizio C04: resta {sum(1 for d in docs.values() if d['c04_resta'])}, "
          f"scarterebbe {sum(1 for d in docs.values() if not d['c04_resta'])} (indizio, non esclusione)")
    for rid in list(docs)[:2]:
        print(f'\n--- {rid}\n' + json.dumps(docs[rid], ensure_ascii=False, indent=1, default=str))
    print()
    ok = True
    for descr, esito, det in verifiche(docs, righe, gia):
        print(('OK    ' if esito else 'FALLITA ') + f'{descr}: {det}')
        ok &= esito
    return ok


def copia_prima(db, ids):
    """copia di sicurezza delle righe che si toccano: qui sono tutte NUOVE (create, mai aggiornate), quindi la copia e' l'elenco
    degli id che verranno creati, per poterli cancellare uno per uno se serve tornare indietro"""
    f = S8 / f'copia_prima_carica_s08_{ora()}.json'
    f.write_text(json.dumps({'data': DATA, 'creati': sorted(ids)}, indent=1), encoding='utf-8')
    return f


def scrivi(db, docs):
    from google.cloud import firestore
    w = list(docs.items())
    for i in range(0, len(w), LOTTO):
        b = db.batch()
        for rid, d in w[i:i + LOTTO]:
            b.create(db.collection('corpus_rows').document(rid), {**d, 'creato_il': firestore.SERVER_TIMESTAMP})
        b.commit()
        print(f'   scritte: {min(i + LOTTO, len(w))}/{len(w)}', flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--scrivi', action='store_true', help='scrive davvero (senza: SOLO anteprima)')
    a = ap.parse_args()
    banca = Banca()
    viva = banca.tutta()
    righe = Nuove().righe()
    car = Caricatore(viva)
    righe, escluse = Copie(viva).separa(righe, car.id_di)
    with open(S8 / 'escluse_copie_s08.jsonl', 'w', encoding='utf-8') as h:
        for e in escluse:
            h.write(json.dumps(e, ensure_ascii=False, default=str) + '\n')
    print(f'copie dello stesso documento e righe rimandate (D04, S06): {len(escluse)} escluse, '
          f'{collections.Counter(e["perche"].split(":")[0] for e in escluse).most_common()}')
    docs = car.documenti(righe)
    gia = banca.esiste(docs)
    (S8 / 'documenti_s08_da_scrivere.json').write_text(json.dumps(docs, ensure_ascii=False, default=str), encoding='utf-8')
    ok = anteprima(docs, gia, righe)
    if not a.scrivi:
        print('\nANTEPRIMA: niente scritto')
        return 0 if ok else 1
    if not ok:
        raise SystemExit('verifiche fallite: non scrivo')
    print('copia di sicurezza:', copia_prima(banca.db, docs).relative_to(QUI))
    scrivi(banca.db, docs)
    return 0


if __name__ == '__main__':
    import giornale
    giornale.avvia()
    raise SystemExit(main())
