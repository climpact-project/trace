#!/usr/bin/env python3
"""Citation search tool used by the research team.

    python tools/cerca.py --caso cited-cases/urgenda.yaml

Runs the TWO NETWORKS on the same cited case, merges the results and writes
the CSV of candidates to read.

    lexical network   exact, EXHAUSTIVE matching on the declared name forms.
                      Not a ranking: it returns ALL occurrences. Returning
                      the top hundred when there are two hundred mentions
                      would silently lose a hundred.
    semantic network  passages semantically close to the semantic queries,
                      to find filings that take up the reasoning WITHOUT
                      naming the case. Here ranking is appropriate.

Resident mode. With `--interattivo` the model stays loaded and subsequent
queries take about two seconds instead of thirty.

Prefixes are read from the index manifest, never hard-coded. `e5` is
asymmetric: passages are prefixed `passage: `, queries `query: `. A mismatch
does not raise an error; it silently yields plausible but wrong results.
The manifest records the prefixes to prevent this.

The reading window is the PAGE, not a character count. In legal filings the
citation that attributes a principle may sit in a footnote at the bottom of
the page, far from the sentence it supports. A 600-character window would
leave that footnote out, and the reader could not apply the rule "a declared
attribution excludes" -- classifying as implicit uptake a passage that
openly cites another source.
"""

import argparse
import csv
import datetime
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
MD = HERE / 'markdown'
INDEX = HERE / 'index'
PAGE_RE = re.compile(r'<!--\s*page\s+(\d+)\s*-->')

# Context around the occurrence written to the verbatim column.
# The READING window is separate and wider: see the module docstring.
PRIMA, DOPO = 200, 260


from dimensioni import (dimensioni as calcola_dimensioni,
                        posizione as posizione_pdf, chiudi_pdf)

# ── Cited case ──────────────────────────────────────────────────────────

def _uno_spazio(v):
    """Collapse whitespace. A multi-line YAML block keeps its newlines; a
    probe is ONE sentence, and newlines must not reach the embedding."""
    return re.sub(r'\s+', ' ', str(v or '')).strip()


def leggi_caso(percorso: Path, con_alternative=False):
    """Read the query specification: lexical variants and semantic queries.

    Uses a real YAML parser. A line-based reader would attach every
    indented field (`canonical`, `seeds`, `probe_alternativa`,
    `lexical_markers`, annotations) to the probe text: on a rich case file
    the five 33-35-word probes grew to 563-961 words, beyond the model's
    512-token window, and were silently truncated.

    Only declared fields are read, each kept separate. The probe vector is
    built exclusively from `testo` (one proposition per probe). Other
    fields (`canonical`, `seeds`, `lexical_markers`, exclusion rationales)
    are not embedding material -- an embedding compresses to a point and
    does not read -- but documentation for researchers, the paper appendix
    and LLM adjudication.

    `con_alternative` adds `probe_alternativa` as a SEPARATE probe: a
    separate search whose results are merged with the main probe's. It is
    never concatenated to `testo`: results are summed, not texts. Measured
    on the five Urgenda probes: overlap between the two formulations 20-36%,
    union +64% to +80% candidates."""
    import yaml
    dati = yaml.safe_load(percorso.read_text(encoding='utf-8')) or {}
    conf = {'forme': [], 'sonde': [], 'escluse': []}

    # PyYAML parses dates into `datetime.date`. The rest of the pipeline treats
    # `data_decisione` as a string (`.strip()[:10]`), so values are normalised
    # here to keep input types from propagating.
    for chiave in ('nome', 'codebook_versione', 'data_decisione',
                   'escludi_case_id', 'case', 'versione_file'):
        if chiave in dati and dati[chiave] is not None:
            v = dati[chiave]
            if isinstance(v, (datetime.date, datetime.datetime)):
                v = v.isoformat()[:10]
            elif not isinstance(v, (list, tuple)):
                v = str(v)
            conf[chiave] = v

    conf['forme'] = [str(f).strip() for f in (dati.get('forme') or []) if str(f).strip()]

    for s in (dati.get('semantic_queries') or []):
        if not isinstance(s, dict) or not _uno_spazio(s.get('testo')):
            continue
        sid = str(s.get('id') or '').strip()
        titolo = _uno_spazio(s.get('titolo'))
        conf['sonde'].append({'id': sid, 'titolo': titolo,
                              'testo': _uno_spazio(s.get('testo'))})
        alt = _uno_spazio(s.get('probe_alternativa'))
        if con_alternative and alt:
            # Own id, so the CSV shows WHICH formulation retrieved the row:
            # needed to assess whether the second formulation adds value.
            conf['sonde'].append({'id': f'{sid}__alt', 'titolo': f'{titolo} [2a formulazione]',
                                  'testo': alt})

    for e in (dati.get('formulazioni_escluse') or []):
        if not isinstance(e, dict) or not _uno_spazio(e.get('testo')):
            continue
        conf['escluse'].append({'per': str(e.get('per') or '').strip(),
                                'id': str(e.get('id') or '').strip(),
                                'testo': _uno_spazio(e.get('testo'))})
        # The exclusion also applies to the second formulation of the same
        # proposition: same proposition, same neighbours.
        if con_alternative:
            conf['escluse'].append({'per': f"{str(e.get('per') or '').strip()}__alt",
                                    'id': str(e.get('id') or '').strip(),
                                    'testo': _uno_spazio(e.get('testo'))})
    return conf


# ── Document ────────────────────────────────────────────────────────────

def front_matter(testo: str):
    meta, fine = {}, testo.find('\n---\n', 4)
    if fine < 0:
        return meta, 0
    for riga in testo[4:fine].split('\n'):
        m = re.match(r'^([a-z_0-9]+):\s*(.*)$', riga)
        if m:
            v = m.group(2).strip()
            if v.startswith("'") and v.endswith("'") and len(v) >= 2:
                v = v[1:-1].replace("''", "'")
            meta[m.group(1)] = v
    return meta, fine + 5


def pagine(testo: str):
    return [(m.start(), int(m.group(1))) for m in PAGE_RE.finditer(testo)]


def pagina_di(marks, off):
    p = 1
    for pos, n in marks:
        if pos <= off:
            p = n
        else:
            break
    return p


def blocco_pagina(testo: str, marks, off: int):
    """Return (raw page text, offset of the occurrence within it).

    Raw, i.e. with the page marker and whitespace untouched: POSITIONS are
    needed here, and any substitution would shift them. The cleaned version
    written to the CSV is produced by `finestra_pagina`."""
    inizio, fine = 0, len(testo)
    for i, (pos, _) in enumerate(marks):
        if pos <= off:
            inizio = pos
            fine = marks[i + 1][0] if i + 1 < len(marks) else len(testo)
        else:
            break
    return testo[inizio:fine], off - inizio


def finestra_pagina(testo: str, marks, off: int):
    """Return the text of the page containing the occurrence, footnotes included."""
    return PAGE_RE.sub(' ', blocco_pagina(testo, marks, off)[0]).strip()


# ── Lexical network ─────────────────────────────────────────────────────

FUSIONE = 200   # matches closer than this are ONE citation


def e_nome(testo, m):
    """Does the match name the case (rather than being only one of its identifiers)?

    Identifiers: docket numbers and ECLI ("19/00135", "C/09/456689", "1 BvR 2656/18", "ECLI:NL:HR:2019:2007") and the
    name inside a URL ("www.urgenda.nl/..."). Name: everything else, including non-Latin scripts."""
    s = m.group(0)
    if re.search(r'[^\x00-\x7f]', s):
        return True
    if not re.search(r'[a-z]{3}', s):
        return False
    prima = testo[max(0, m.start() - 60):m.start()]
    coda = re.search(r'\S*$', prima).group(0)
    return not ('/' in coda or 'www' in coda.lower() or 'http' in coda.lower())


def fondi(testo, grezze):
    """Merge matches so that one citation yields one row. Two rules.

    1. Matches within 200 characters of the start of the group are one citation.
    2. An IDENTIFIER within 200 characters of the previous match continues the same citation. Without this rule a
       long reference ("Urgenda c. Pays-Bas, C/09/456689 / HA ZA 13-1396 ; Cour d'appel... 200.178.245/01 ;
       Hoge Raad... 19/00135") exceeds 200 characters and the trailing docket number becomes a separate row (a few
       cases on Urgenda, dozens on Neubauer with chains like "1 BvR 2656/18, 1 BvR 78/20...").
       The NAME, by contrast, always opens a new citation beyond 200 characters: consecutive footnotes
       ("324 Urgenda..., para. 5.7.5. 325 Urgenda..., paras. 5.7.5-5.7.6") are distinct citations of different
       paragraphs. A fully chained merge rule was tested and rejected for this reason."""
    fuse, fine = [], None
    for m in grezze:
        if fuse and (m.start() - fuse[-1][0].start() < FUSIONE
                     or (m.start() - fine < FUSIONE and not e_nome(testo, m))):
            fuse[-1][1].append(m.group(0))
            fuse[-1][2] = m.start()
        else:
            fuse.append([m, [m.group(0)], m.start()])
        fine = m.end()
    return fuse


def rete_lessicale(forme, escludi='', tipi=None):
    """Every occurrence, in every document. Exhaustive by construction.

    Nearby matches are MERGED: a filing often writes "the court
    (ECLI:..., case C/09/...) in Urgenda" -- one citation, three matches.
    Counting them separately inflates the data non-uniformly: it inflates
    most the filings that cite in full, i.e. those that give weight to the
    precedent."""
    patt = re.compile('|'.join(re.escape(f) for f in forme), re.I)
    # `escludi_case_id` may be a scalar or a LIST (one proceeding can be split
    # across several case_ids, e.g. Juliana). Both are accepted; otherwise a
    # list would reach `.lower()` and fail, or an `in` on a list would
    # silently exclude the wrong documents.
    esclusi = [escludi] if isinstance(escludi, str) else list(escludi or [])
    esclusi = [str(x).lower() for x in esclusi if str(x).strip()]
    fuori = []
    for md in sorted(MD.rglob('*.md')):
        testo = md.read_text(encoding='utf-8', errors='replace')
        meta, inizio = front_matter(testo)
        cid = (meta.get('case_id') or '').lower()
        if any(x in cid for x in esclusi):
            continue
        if tipi and (meta.get('tipo_atto') or '').strip().lower() not in tipi:
            continue
        grezze = list(patt.finditer(testo, inizio))
        if not grezze:
            continue
        marks = pagine(testo)
        fuse = fondi(testo, grezze)
        for m, forme_qui, _ in fuse:
            blocco, off_rel = blocco_pagina(testo, marks, m.start())
            fuori.append({
                'dim': calcola_dimensioni(meta, blocco, off_rel, testo[:m.start()]),
                'meta': meta, 'file': str(md.relative_to(HERE)),
                'char_start': m.start(),
                'pagina': pagina_di(marks, m.start()),
                'forma': ' + '.join(dict.fromkeys(forme_qui)),
                'verbatim': re.sub(r'\s+', ' ', PAGE_RE.sub(
                    ' ', testo[max(inizio, m.start() - PRIMA):m.start() + DOPO])).strip(),
                'finestra': finestra_pagina(testo, marks, m.start()),
                'rete': 'lessicale', 'punteggio': '',
            })
    return fuori


# ── Semantic network ────────────────────────────────────────────────────

class Semantica:
    """Keeps the model and the index in memory between queries."""

    def __init__(self):
        man = json.loads((INDEX / 'manifesto.json').read_text(encoding='utf-8'))
        self.man = man
        self.pre_q = man.get('prefisso_domanda', '')
        print(f"  indice   : {man['frammenti']:,} frammenti, {man['modello']}", flush=True)
        print(f"  costruito: {man['costruito']}", flush=True)
        t0 = time.time()
        self.V = np.load(INDEX / 'vettori.npy', mmap_mode='r')
        self.ids = json.loads((INDEX / 'ids.json').read_text(encoding='utf-8'))
        from sentence_transformers import SentenceTransformer
        import torch
        dev = ('cuda' if torch.cuda.is_available()
               else 'mps' if torch.backends.mps.is_available() else 'cpu')
        self.m = SentenceTransformer(man['modello'], device=dev)
        self.m.max_seq_length = man.get('max_token', 512)
        print(f'  caricato in {time.time() - t0:.0f}s su {dev}', flush=True)
        # Chunks map back to document and page.
        self.fr = {}
        with (INDEX / 'chunks.jsonl').open(encoding='utf-8') as f:
            for riga in f:
                d = json.loads(riga)
                self.fr[d['id']] = d

    def cerca(self, sonde, k=100, escluse=()):
        """Return candidates, and how similar each is to what does NOT count.

        EXCLUDED FORMULATIONS do not filter, they measure. Each probe may
        declare one or more formulations that resemble it but say something
        else -- e.g. the ordinary civil-law duty of care, which appears in
        thousands of judgments unrelated to the cited case. Each candidate
        then carries two scores and their difference.

        NOTHING IS DISCARDED AUTOMATICALLY. A candidate closer to an
        excluded formulation than to the probe is still returned, with a
        negative `margine` and `sospetto` set: these rows should be read
        first. Discarding them silently would hide exactly the cases where
        the probe is poorly written -- the information needed to rewrite
        it."""
        Q = self.m.encode([self.pre_q + s['testo'] for s in sonde],
                          normalize_embeddings=True, convert_to_numpy=True,
                          show_progress_bar=False).astype(np.float16)
        per_sonda = {}
        if escluse:
            E = self.m.encode([self.pre_q + e['testo'] for e in escluse],
                              normalize_embeddings=True, convert_to_numpy=True,
                              show_progress_bar=False).astype(np.float16)
            for i, e in enumerate(escluse):
                per_sonda.setdefault(e['per'], []).append((e, E[i]))
        fuori = []
        for i, s in enumerate(sonde):
            punt = self.V @ Q[i]
            mie = per_sonda.get(s['id'], [])
            for j in np.argsort(-punt)[:k]:
                d = self.fr.get(self.ids[j])
                if not d:
                    continue
                p_escl, quale = 0.0, ''
                for e, vec in mie:
                    v = float(self.V[j] @ vec)
                    if v > p_escl:
                        p_escl, quale = v, e['id'] or e['per']
                r = {'frammento': d, 'sonda': s['titolo'] or s['id'],
                     'punteggio': round(float(punt[j]), 4)}
                if mie:
                    r['punteggio_escluse'] = round(p_escl, 4)
                    r['margine'] = round(float(punt[j]) - p_escl, 4)
                    r['sospetto'] = (f'piu vicino a: {quale}'
                                     if r['margine'] <= 0 else '')
                fuori.append(r)
        return fuori


# ── Reranker ────────────────────────────────────────────────────────────

class Riordinatore:
    """Cross-encoder that reads the probe and the passage TOGETHER and
    scores whether the passage ASSERTS that proposition.

    Rationale. The semantic network compresses each text into a single
    point, which captures WHAT IS BEING DISCUSSED but not the structure of
    the proposition: who the subject is, whether it states an obligation or
    a fact, whether it affirms or denies. Hence "China's share is 11.6% of
    global emissions" and "each State is responsible for its own share and
    cannot evade it" end up close: same topic, but one is a statistic and
    the other a norm, and the embedding cannot tell them apart.

    A cross-encoder places the two texts SIDE BY SIDE and reads them
    jointly, so it sees sentence structure.

    Measured on probe `propria_quota`:

        0.9504  the norm ("each State is responsible for its own share...")
        0.7308  common but differentiated responsibilities (excluded formulation)
        0.0833  the Chinese emission-share statistic
        0.0086  an EPA regulation repeated sixty times

    The statistic and the noise drop by an order of magnitude. The excluded
    formulation does NOT -- it stays high, correctly, since it is a close
    proposition; that case is handled by the excluded-formulation margin,
    not by the reranker.

    No GPU and no new index are required: it only scores the few hundred
    candidates already retrieved by the semantic network, not the 1.2
    million chunks. About half a second for four pairs on a laptop."""

    MODELLO = 'BAAI/bge-reranker-v2-m3'

    def __init__(self):
        from sentence_transformers import CrossEncoder
        t0 = time.time()
        self.m = CrossEncoder(self.MODELLO, max_length=1024)
        print(f'  riordinatore caricato in {time.time() - t0:.0f}s', flush=True)

    def punteggi(self, coppie):
        import numpy as _np
        if not coppie:
            return []
        out = self.m.predict(coppie, show_progress_bar=False)
        return [float(x) for x in _np.asarray(out).reshape(-1)]


# ── Confidence of the semantic proposal ─────────────────────────────────
#
# Confidence is a machine proposal derived from the reranker score, in the
# same group as the embedding and reranker scores; it is not a
# self-assessment by the reader. A single field cannot hold both, so it is
# written by the machine from its score.
#
# Thresholds were measured on the 216 semantic candidates of the Urgenda
# run (`punteggio_riordino`). The observed minimum is 0.051, just above the
# discard threshold (0.05): below that, a candidate never reaches this
# point. Median 0.40, 75th percentile 0.65. Thresholds 0.2 and 0.6 split the
# set into three groups of comparable size.
def confidenza_da_riordino(v):
    if v is None or v == '':
        return ''
    try:
        v = float(v)
    except (TypeError, ValueError):
        return ''
    if v >= 0.6:
        return 'alta'
    if v >= 0.2:
        return 'media'
    return 'bassa'


# ── Merge and output ────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    # A short case name (`--caso urgenda`) is accepted instead of the full path.
    ap.add_argument('--caso', required=True,
                    help='nome del caso citato (es. urgenda) o percorso del file')
    # The codebook is not a parameter: there is a single codebook for all
    # cases, so every annotator applies the same criteria. It changes only
    # through a revision.
    ap.add_argument('--uscita', default='')
    ap.add_argument('--k', type=int, default=100, help='candidati per semantic query')
    ap.add_argument('--solo-lessicale', action='store_true')
    ap.add_argument('--con-alternative', action='store_true',
                    help='usa anche `probe_alternativa` come sonda a se stante '
                         '(ricerca separata, risultati uniti). Misurato il '
                         '2026-09-03: +64-80%% di candidati, sovrapposizione 20-36%%.')
    # Restrict to court decisions. A case invoked by claimants in many
    # countries but adopted by courts in few is a different finding, and the
    # gap between the two counts is itself a result. The corpus contains both
    # party filings and decisions; this option selects what to count.
    ap.add_argument('--solo-decisioni', action='store_true',
                    help='solo decisioni e ordinanze: cio che le corti hanno adottato')
    ap.add_argument('--senza-riordino', action='store_true',
                    help='salta il riordinatore (piu veloce, molto piu rumore)')
    ap.add_argument('--soglia-riordino', type=float, default=0.05,
                    help='sotto questo punteggio il candidato semantico non entra')
    ap.add_argument('--con-anteriori', action='store_true',
                    help='tiene anche i documenti anteriori alla decisione citata')
    ap.add_argument('--tipo-atto', default='',
                    help="tipi di atto separati da virgola (es. 'atto introduttivo,replica')")
    args = ap.parse_args()

    # A short name is resolved in the cited-cases folder.
    percorso = Path(args.caso)
    if not percorso.exists():
        percorso = HERE / 'cited-cases' / f'{args.caso}.yaml'
    if not percorso.exists():
        disponibili = sorted(p.stem for p in (HERE / 'cited-cases').glob('*.yaml'))
        print(f'Caso citato non trovato: {args.caso}')
        print(f'Disponibili: {", ".join(disponibili) or "nessuno"}')
        return 1
    conf = leggi_caso(percorso, con_alternative=args.con_alternative)

    tipi = None
    if args.solo_decisioni:
        tipi = {'decisione', 'ordinanza'}
    elif args.tipo_atto:
        tipi = {t.strip().lower() for t in args.tipo_atto.split(',') if t.strip()}

    # The codebook travels with the passages: its reading instructions are
    # written next to the CSV, so every reader (human or model) has them
    # alongside the text to classify and applies the same criteria.
    cb_file = HERE / 'codebook' / 'citazioni.yaml'
    cb_testo = cb_file.read_text(encoding='utf-8') if cb_file.exists() else ''
    m = re.search(r'^versione:\s*(.+)$', cb_testo, re.M)
    cb_versione = m.group(1).strip() if m else 'assente'
    m = re.search(r'^approvato_da:\s*(.+)$', cb_testo, re.M)
    cb_approvato = (m.group(1).strip() if m else 'null')
    print(f'codebook    : {cb_versione}', end='')
    if cb_approvato in ('null', '', 'None'):
        print('   NON ANCORA APPROVATO — le codifiche prodotte ora non sono definitive')
    else:
        print(f'   approvato da {cb_approvato}')
    nome = conf.get('nome', Path(args.caso).stem)
    print(f'caso citato : {nome}')
    print(f'forme       : {len(conf["forme"])}')
    print(f'sonde       : {len(conf["sonde"])}')
    if tipi:
        print(f'FILTRO      : solo {", ".join(sorted(tipi))}')
    print(flush=True)

    print('rete lessicale (esaustiva)…', flush=True)
    t0 = time.time()
    less = rete_lessicale(conf['forme'], conf.get('escludi_case_id', ''), tipi)
    print(f'  {len(less):,} occorrenze in {time.time() - t0:.0f}s\n', flush=True)

    sem = []
    if not args.solo_lessicale and conf['sonde']:
        print('rete semantica…', flush=True)
        S = Semantica()
        t0 = time.time()
        sem = S.cerca(conf['sonde'], k=args.k, escluse=conf.get('escluse', ()))
        print(f'  {len(sem):,} candidati in {time.time() - t0:.0f}s\n', flush=True)

    # MERGE. A passage found by both networks is ONE row, with
    # `rete = entrambe`: recording the source allows estimating how much of
    # the result depends on which tool.
    # Merging uses true overlap, not fixed blocks: grouping by
    # `char_start // 400` would merge distinct citations in the same block
    # and split adjacent ones across a boundary, a non-uniform loss that
    # depends on grid alignment. A semantic candidate is merged with a
    # lexical occurrence only if its CHUNK actually contains it.
    per_file = {}
    for r in less:
        per_file.setdefault(r['file'], []).append(r)

    unite = list(less)
    for r in sem:
        d = r['frammento']
        a, b = d['char_start'], d.get('char_end', d['char_start'] + 1100)
        dentro = None
        for l in per_file.get(d['file'], []):
            if a <= l['char_start'] < b:
                dentro = l
                break
        if dentro is not None:
            dentro['rete'] = 'entrambe'
            if not dentro.get('punteggio'):
                dentro['punteggio'] = r['punteggio']
                dentro['sonda'] = r['sonda']
                for c in ('punteggio_escluse', 'margine', 'sospetto'):
                    if c in r:
                        dentro[c] = r[c]
            continue
        testo = (HERE / d['file']).read_text(encoding='utf-8', errors='replace')
        meta, _ = front_matter(testo)
        if tipi and (meta.get('tipo_atto') or '').strip().lower() not in tipi:
            continue
        marks = pagine(testo)
        blocco, off_rel = blocco_pagina(testo, marks, d['char_start'])
        unite.append({
            'dim': calcola_dimensioni(meta, blocco, off_rel, testo[:d['char_start']]),
            'meta': meta, 'file': d['file'], 'char_start': d['char_start'],
            'pagina': d.get('pagina', 1), 'forma': '',
            'verbatim': re.sub(r'\s+', ' ', d['testo'])[:460],
            # Full chunk text for the reranker. The 460 characters above are a
            # COLUMN width, to keep `citazione_testuale` readable in a CSV.
            # The reranker judges whether the passage answers the probe, and
            # context is what it is for: fed the truncated text (~115 tokens)
            # it would see about a third of what it can read (1024 tokens).
            # Two fields: one for reading, one for scoring.
            'verbatim_intero': re.sub(r'\s+', ' ', d['testo']),
            'finestra': finestra_pagina(testo, marks, d['char_start']),
            'rete': 'semantica', 'punteggio': r['punteggio'], 'sonda': r['sonda'],
            **{c: r[c] for c in ('punteggio_escluse', 'margine', 'sospetto')
               if c in r},
        })

    righe = []
    for r in unite:
        m = r['meta']
        righe.append({
            'case_id': m.get('case_id', ''), 'case_name': m.get('case_name', ''),
            'giurisdizioni': m.get('giurisdizioni', ''),
            'document_id': m.get('document_id', ''),
            'tipo_atto': m.get('tipo_atto', ''),
            'tipo_atto_sabin': m.get('tipo_atto_sabin', ''),
            'data': m.get('data_deposito', ''), 'pagina': r['pagina'],
            'rete': r['rete'], 'sonda': r.get('sonda', ''),
            'punteggio': r['punteggio'],
            'punteggio_riordino': '',
            'copie': '',
            'anteriore': '',
            'punteggio_escluse': r.get('punteggio_escluse', ''),
            'margine': r.get('margine', ''),
            'sospetto': r.get('sospetto', ''),
            'forma_trovata': r['forma'],
            'citazione_testuale': r['verbatim'],
            # Carried only for the reranker and removed before the CSV is
            # written: it is input to a computation, not a column.
            'verbatim_intero': r.get('verbatim_intero', ''),
            'finestra_pagina': r['finestra'],
            # MACHINE PROPOSALS -- never modified. They are used to measure
            # disagreement with the reader; overwriting them would lose it.
            'chi_cita_auto': r['dim']['chi_cita_auto'],
            'posizione_auto': '',
            'sede_auto': r['dim']['sede_auto'],
            'dimensioni_confidenza': r['dim']['dimensioni_confidenza'],
            # READER DECISIONS -- pre-filled with the proposal, so the
            # reader only corrects where the proposal is wrong.
            'chi_parla': r['dim']['chi_cita_auto'],
            'posizione': '',
            'sede': r['dim']['sede_auto'],
            # Not pre-filled: no textual signal determines these.
            'tipo_citazione': '', 'annidata': '',
            'proposizione_sostenuta': '', 'confidenza': '', 'note': '',
            'file': r['file'], 'char_start': r['char_start'],
            'url_documento': m.get('url_documento', ''),
            'codebook_versione': cb_versione,
        })
    # ── Temporal filter ─────────────────────────────────────────────
    #
    # A filing dated BEFORE the cited decision cannot take it up. This is a
    # calendar fact, not an estimate: exact, free, and not reproducible by
    # any model.
    #
    # Earlier documents are not thrown away. An earlier document expressing
    # the same proposition is evidence that the principle pre-existed, i.e.
    # an argument AGAINST derivation. They are written to the discard file
    # with their reason, and kept in the main CSV with `--con-anteriori`.
    # Networks that found the case NAME: literal occurrences, not hypotheses.
    NOMINALI = ('lessicale', 'entrambe')
    scarti = []
    anteriori = []
    dmin = (conf.get('data_decisione') or '').strip()[:10]
    if dmin and not args.con_anteriori:
        tenute = []
        for r in righe:
            d = (r.get('data') or '').strip()[:10]
            # Name rows ('lessicale' and 'entrambe') are exempt: the filter
            # applies only to semantic hypotheses.
            if r['rete'] not in NOMINALI and d and d < dmin:
                r['anteriore'] = 'si'
                r['motivo_scarto'] = f'anteriore al {dmin}'
                anteriori.append(r)
                scarti.append(r)
            else:
                tenute.append(r)
        righe = tenute

    # ── Deduplication ───────────────────────────────────────────────
    #
    # About 6% of corpus chunks are repeated text: the same filing lodged
    # several times, the same annexes; the most repeated appears sixty
    # times. Presenting them as distinct candidates inflates counts and
    # forces repeated reading. The first is kept and its copy count recorded.
    visti, uniche = {}, []
    for r in righe:
        k = re.sub(r'\s+', ' ', r['citazione_testuale']).strip().lower()[:400]
        if k in visti:
            visti[k]['copie'] = int(visti[k].get('copie') or 1) + 1
            r['motivo_scarto'] = 'copia di un altro frammento'
            scarti.append(r)
            continue
        r['copie'] = 1
        visti[k] = r
        uniche.append(r)
    duplicati = len(righe) - len(uniche)
    righe = uniche

    # ── Reranking ───────────────────────────────────────────────────
    #
    # Semantic candidates only: lexical ones are literal occurrences of the
    # name, not hypotheses to screen.
    scartati_riordino = 0
    if not args.senza_riordino and any(r['rete'] != 'lessicale' for r in righe):
        print('\nriordino dei candidati semantici…', flush=True)
        testi_sonda = {(s.get('titolo') or s['id']): s['testo'] for s in conf['sonde']}
        da_riordinare = [r for r in righe if r['rete'] != 'lessicale' and r.get('sonda')]
        try:
            R = Riordinatore()
            t0 = time.time()
            # The FULL chunk is passed, not the truncated column (see
            # `verbatim_intero`). The fallback to `citazione_testuale` covers
            # rows without that field (e.g. from an earlier version).
            coppie = [[testi_sonda.get(r['sonda'], r['sonda']),
                       r.get('verbatim_intero') or r['citazione_testuale']]
                      for r in da_riordinare]
            for r, v in zip(da_riordinare, R.punteggi(coppie)):
                r['punteggio_riordino'] = round(v, 4)
                # A confidence already set manually is not overwritten; only
                # an empty field receives the machine proposal.
                if not r.get('confidenza'):
                    r['confidenza'] = confidenza_da_riordino(r['punteggio_riordino'])
            print(f'  {len(coppie):,} coppie in {time.time() - t0:.0f}s', flush=True)
            prima = len(righe)
            tenute = []
            for r in righe:
                # The cut NEVER applies to name rows, including 'entrambe' rows
                # (which name the case AND resemble a probe): cutting them on a
                # low reranker score would drop explicit citations. The score
                # stays on the row as a hint.
                if (r['rete'] in NOMINALI
                        or r.get('punteggio_riordino', 1.0) >= args.soglia_riordino):
                    tenute.append(r)
                else:
                    r['motivo_scarto'] = (
                        f"riordino {r.get('punteggio_riordino')} < {args.soglia_riordino}")
                    scarti.append(r)
            righe = tenute
            scartati_riordino = prima - len(righe)
        except Exception as e:
            print(f'  riordinatore non disponibile ({e}) — si prosegue senza',
                  flush=True)

    righe.sort(key=lambda x: (x['file'], x['pagina']))

    # Body or footnote position is read from the PDF, not the markdown.
    # Rows are sorted by file so each PDF is opened once.
    print('\ncorpo o nota (dal PDF)…', flush=True)
    t0 = time.time()
    try:
        import fitz  # noqa: F401
    except ImportError:
        print('  FERMO: manca PyMuPDF, la colonna corpo/nota non si puo')
        print('  calcolare. Installalo e rilancia:')
        print('    ./.venv/bin/pip install pymupdf')
        return 1
    for r in righe:
        pdf = HERE / r['file'].replace('markdown/', 'documents/').replace('.md', '.pdf')
        if pdf.exists():
            pos, cpos = posizione_pdf(pdf, int(r['pagina']), r['citazione_testuale'])
        else:
            pos, cpos = 'non_determinabile', 'bassa'
        r['posizione_auto'] = pos
        r['posizione'] = pos
        if cpos == 'bassa' and r['dimensioni_confidenza'] != 'bassa':
            r['dimensioni_confidenza'] = 'media'
    chiudi_pdf()
    print(f'  {time.time() - t0:.0f}s', flush=True)

    righe.sort(key=lambda x: (x['case_name'], x['document_id'], x['pagina']))

    out = HERE / (args.uscita or f'index/candidati_{Path(args.caso).stem}.csv')
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', newline='', encoding='utf-8') as f:
        # Remove the full chunk text before writing: CSV columns are derived
        # from the first row's keys, so a leftover service field would become
        # a column in every output file. It was only needed by the reranker.
        for _r in righe:
            _r.pop('verbatim_intero', None)
        w = csv.DictWriter(f, fieldnames=list(righe[0].keys()))
        w.writeheader()
        w.writerows(righe)

    import collections
    c = collections.Counter(r['rete'] for r in righe)
    print(f'RIGHE      : {len(righe):,}')
    for k, v in c.most_common():
        print(f'  {k:12s}: {v:,}')
    print(f'documenti  : {len({r["document_id"] for r in righe}):,}')
    d = collections.Counter(r['sede_auto'] for r in righe)
    print('sede (proposta):')
    for k, v in d.most_common():
        print(f'  {k:18s}: {v:,}')
    n = collections.Counter(r['posizione_auto'] for r in righe)
    print(f"posizione  : corpo {n.get('corpo', 0):,}   nota {n.get('nota', 0):,}")
    if dmin and not args.con_anteriori:
        print(f'anteriori  : {len(anteriori):,} candidati in documenti '
              f'precedenti al {dmin} — tolti (con --con-anteriori restano)')
    if duplicati:
        print(f'duplicati  : {duplicati:,} righe erano copie dello stesso testo')
    if scartati_riordino:
        print(f'riordino   : {scartati_riordino:,} candidati sotto '
              f'{args.soglia_riordino} — tolti')
    sosp = sum(1 for r in righe if r['sospetto'])
    if sosp:
        print(f'SOSPETTE   : {sosp:,} righe piu vicine a una formulazione '
              f'esclusa che alla sonda — da leggere per prime')
    b = sum(1 for r in righe if r['dimensioni_confidenza'] == 'bassa')
    if b:
        print(f'da guardare per prime: {b:,} righe con confidenza bassa')
    print(f'casi       : {len({r["case_id"] for r in righe}):,}')
    print(f'uscita     : {out}')

    # ── Discards are kept ─────────────────────────────────────────────
    #
    # Rationale. The 20% manual check verifies how a row ALREADY IN THE CSV
    # was classified; it never sees what the machine removed earlier
    # (below-threshold candidates, earlier documents, copies). If those rows
    # vanished they would be decisions made by the model alone, outside any
    # check in the method.
    #
    # They are therefore written with their reason. The 20% sample must
    # include a share of them: it is the only way to detect a threshold
    # discarding good material.
    if scarti:
        fs = out.with_name(out.stem + '.SCARTI.csv')
        campi = list(righe[0].keys()) + ['motivo_scarto']
        with fs.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=campi, extrasaction='ignore')
            w.writeheader()
            for r in scarti:
                r.setdefault('copie', '')
                r.setdefault('anteriore', '')
                w.writerow({k: r.get(k, '') for k in campi})
        import collections as _c
        print(f'scarti     : {fs}')
        for k, v in _c.Counter(
                r.get('motivo_scarto', '?').split(' ')[0] for r in scarti
        ).most_common():
            print(f'   {v:>6,}  {k}')

    # Reading instructions, written next to the CSV.
    istr = re.search(r'^istruzioni_lettura:\s*\|(.*)$', cb_testo, re.M | re.S)
    if istr:
        gemello = out.with_suffix('.ISTRUZIONI.md')
        gemello.write_text(
            f'# Come classificare — codebook {cb_versione}\n\n'
            f'Caso citato: **{nome}**\n\n'
            f'Righe da classificare: {len(righe):,}\n\n'
            + '\n'.join(l[2:] if l.startswith('  ') else l
                        for l in istr.group(1).split(chr(10))).strip()
            + '\n\n---\n\nCategorie e casi limite: `codebook/citazioni.yaml`.\n',
            encoding='utf-8')
        print(f'istruzioni : {gemello}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
