# ruff: noqa: E501, E731, SIM115, E401, B007, RUF005, RUF015  (internal check script, kept as it ran on 10/10/2026)
"""Golden check of the rules R15 and R16 (with R12-R14 inside them): the package recomputes, row by row, the proposals
that the frozen tools wrote on 4 October 2026 and compares them with the state the rows had right after.

Inputs (level c, not published): the five DeepSeek readings and the rows of each case (training/principi/), the type
readings, the copies taken before every write (training/<cycle>/prima_*.json.gz), the snapshot of 7 October
(training/t04_tutte/..._righe_intere.json.gz) and the restricted corpus (markdown and PDF of the filings, level b).
Usage: TRACE_ROOT=/path/to/private/root python reproduce/golden_rules.py [case,case...]
MAPPA_DEL_4=1 uses the paragraph map of the ICJ opinion as it was on 4 October (the R18 map came on 8 October).
Result on 10/10/2026: R15 7,473 rows recomputed, 7,184 compared, 0 different; R16 483, 472 compared, 0 different
(the others have no later state to compare with).
"""

import collections
import glob
import gzip
import json
import os
import pathlib
import sys

from tracepipe.composizione import ComposizioneMaggioranza, IngressiMaggioranza
from tracepipe.config import Config

R = pathlib.Path(os.environ.get('TRACE_ROOT', '.')).resolve()
T = R / 'training'
CASI = (
    sys.argv[1].split(',')
    if len(sys.argv) > 1
    else ['urgenda', 'neubauer', 'future-generations', 'klimaseniorinnen', 'cig-parere-clima', 'idh-oc-32-25']
)
SER = {'neubauer': 'P05', 'future-generations': 'P05', 'cig-parere-clima': 'P09'}


def g(f):
    return json.load(gzip.open(f))




def copia(pat):
    fs = sorted(glob.glob(str(T / pat)))
    assert len(fs) == 1, (pat, fs)
    return g(fs[0])


# later snapshots, chronological (full proposto_* state of the rows they touched)
DOPO = []
for pat in [
    'cinque/prima_carica_ripresa_R11_*_2026-10-04_083*',
    'cinque/prima_carica_ripresa_R16_*',
    'esclusioni/prima_escludi_righe_*_2026-10-04_*',
    'esclusioni/prima_unisci_c03_*',
    'esclusioni/prima_applica_c07_*',
    'cinque/prima_carica_lessicali_*_2026-10-07_*',
    'cinque/prima_carica_ripresa_R11_*_2026-10-07_*',
    'esclusioni/prima_segna_altre_citazioni_tutti_2026-10-07_*',
]:
    for f in sorted(glob.glob(str(T / pat))):
        d = g(f)
        DOPO.append((d['quando'], f.split('/')[-1], {k: v['prima'] for k, v in d['righe'].items()}))
FULL = g(T / 't04_tutte/prima_carica_segnale_t04_tutti_2026-10-07_154907_righe_intere.json.gz')
FULL = FULL.get('righe', FULL)
DOPO.append(('2026-10-07T15:49', 'full', FULL))
DOPO.sort(key=lambda x: x[0])


def dopo(rid, quando):
    for q, nome, rr in DOPO:
        if q > quando and rid in rr:
            return nome, rr[rid]
    return None, None


STAT = ('file', 'char_start', 'file_pdf')
AUDIT = g(T / 'misure/audit_filtri_2026-10-04/corpus_rows_2026-10-04_0609.json.gz')
VIVE = {}
for l in gzip.open(T / 'letture_vive/corpus_rows_2026-10-08.jsonl.gz', 'rt'):
    x = json.loads(l)
    VIVE[x['id']] = x


def statici(rid):
    x = AUDIT.get(rid) or FULL.get(rid) or VIVE.get(rid)
    return {k: x[k] for k in STAT if x and k in x}


def norm_est(e):
    return [
        {k: v for k, v in x.items() if not k.startswith('c07') and k not in ('altra_citazione', 'altre_citazioni')}
        for x in (e or [])
    ]


CAMPI_SKIP = {'proposto_paragrafi'}  # C03 rewrites them on merged rows


def confronta(out, att, conti, diff, rid, fase):
    bad = []
    for k, v in out.items():
        if k.startswith('provenienza.'):
            top, sub = k.split('.', 1)
            w = (att.get('provenienza') or {}).get(sub)
        else:
            w = att.get(k)
        if k == 'proposto_estensione':
            v, w = norm_est(v), norm_est(w)
        if json.dumps(v, sort_keys=True, ensure_ascii=False, default=str) != json.dumps(
            w, sort_keys=True, ensure_ascii=False, default=str
        ):
            bad.append(k)
    if bad:
        conti[f'{fase} righe diverse'] += 1
        for k in bad:
            conti[f'{fase} campo diverso {k}'] += 1
        diff.append((fase, rid, bad))
    else:
        conti[f'{fase} righe uguali'] += 1


def main():
    conti = collections.Counter()
    diff = []
    finali = {}
    for caso in CASI:
        os.environ.pop('TRACE_SONDE', None)
        cfg = Config(radice=R)
        comp = ComposizioneMaggioranza.per_caso(cfg, caso)
        s = SER.get(caso, '')
        for fase, et, eti_tipo, kw in (
            ('R15', s + 'cinque', 'cinque', {}),
            ('R16', s + 'r16', 'r16', {'solo_cambiate': True, 'tieni_frase': True}),
        ):
            cp = copia(f'cinque/prima_carica_ripresa_{fase}_{caso}_*')
            righe = [(rid, {**statici(rid), **v['prima']}) for rid, v in cp['righe'].items()]
            ing = IngressiMaggioranza.carica(cfg, caso, et, eti_tipo, pagine_intere=True)
            if os.environ.get('MAPPA_DEL_4') and caso == 'cig-parere-clima':
                # the paragraph map of the ICJ opinion as it was on 04/10 (empty for P09; the R18 map came on 08/10)
                from tracepipe.pagine_attorno import per_id

                ing.par = per_id(T / 'mappa_cig_P09/cig-parere-clima_da_paragrafi.vuoto-2026-10-06.jsonl')
            scr, c = comp.componi_r11(righe, ing, composizione=fase, etichetta=et, **kw)
            scr = dict(scr)
            conti[f'{fase} righe nella copia'] += len(righe)
            conti[f'{fase} scritte dal pacchetto'] += len(scr)
            for rid, _ in righe:
                if rid not in scr:
                    conti[f'{fase} non scritta dal pacchetto'] += 1
                    diff.append((fase, rid, ['non scritta']))
                    continue
                finali.setdefault(rid, {}).update(scr[rid])
                nome, att = dopo(rid, cp['quando'])
                if att is None:
                    conti[f'{fase} senza stato dopo'] += 1
                    continue
                confronta(scr[rid], att, conti, diff, rid, fase)
                finali.setdefault(rid, {}).update(scr[rid])
        print(caso, dict((k, v) for k, v in conti.items()), file=sys.stderr, flush=True)
    json.dump(
        {'conti': conti, 'diff': diff},
        open(f'esito_{"_".join(CASI)}{os.environ.get("MAPPA_DEL_4", "")}.json', 'w'),
        ensure_ascii=False,
        default=str,
        indent=0,
    )
    json.dump(
        finali,
        open(f'finali_{"_".join(CASI)}{os.environ.get("MAPPA_DEL_4", "")}.x', 'w'),
        ensure_ascii=False,
        default=str,
    )
    for k, v in sorted(conti.items()):
        print(k, v)


main()
