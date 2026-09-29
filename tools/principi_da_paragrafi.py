"""Principles taken by an explicit citation, derived from the paragraphs it cites. No model involved.

   Each explicit citation is coded with the principle(s) of the cited case it takes up. When the citation
   gives a paragraph number (e.g. "Urgenda, para. 5.7.7", "§ 5.6.2", "r.o. 4.83"), the hand-written and
   hand-checked paragraph map (`cited-cases/<caso>-mappa-paragrafi.yaml`) gives the answer. This is the most
   reliable label available and does not come from a language model, so it may be used for training
   (project rule: labels come from people or rules, never from LLM verdicts).

   Method. On the citation page every mention of the case is located; paragraph numbers are searched in the
   following 250 characters. The decision instance (Rechtbank 2015, Hof 2018, Hoge Raad 2019) is inferred
   from nearby words (court names, years); failing that, from the number itself when it exists in only one
   decision. Ranges in the map (e.g. "4.11-4.19") are expanded.

   Usage:  .venv/bin/python tools/principi_da_paragrafi.py [--caso urgenda]
           -> training/principi/<caso>_da_paragrafi.jsonl
"""
import collections, json, pathlib, re
import yaml
QUI = pathlib.Path(__file__).resolve().parent.parent
MENZIONE_URGENDA = re.compile(r'urgenda|ECLI:NL:(?:HR|GHDHA|RBDHA):20(?:19|18|15):\d+', re.I)
PAR = re.compile(r'(?:paras?\.?|paragraphs?|§§?|¶¶?|r\.\s?o\.|rov\.|rn\.|randnummer|margin\s+(?:nos?\.|numbers?))\s*'
                 r'((?:\d{1,3}(?:\.\d{1,3}){0,2})(?!\d)(?:\s*(?:[-–]|to|and|&|,)\s*\d{1,3}(?:\.\d{1,3}){0,2}(?![\d/]))*)', re.I)
# Components allow up to three digits (\d{1,3}) so that e.g. "Rn. 254" or "4.109" are not truncated.
CORTE = [('hoge_raad_2019', re.compile(r'supreme court|hoge raad|\bHR\b|2019', re.I)),
         ('hof_2018', re.compile(r'court of appeal|gerechtshof|\bhof\b|2018', re.I)),
         ('rechtbank_2015', re.compile(r'district court|rechtbank|2015', re.I))]


def chiave(n):
    return tuple(int(x) for x in n.split('.'))


def espandi(p):
    p = str(p).strip()
    m = re.fullmatch(r'(\d+(?:\.\d+)*)\s*-\s*(\d+(?:\.\d+)*)', p)
    if not m:
        return [p] if re.fullmatch(r'\d+(?:\.\d+)*', p) else []
    a, b = chiave(m.group(1)), chiave(m.group(2))
    if len(a) != len(b) or a[:-1] != b[:-1] or b[-1] < a[-1] or b[-1] - a[-1] > 60:
        return [m.group(1), m.group(2)]
    return ['.'.join(map(str, a[:-1] + (k,))) for k in range(a[-1], b[-1] + 1)]


def mappa(caso='urgenda'):
    """Decision -> paragraph -> principles. In the Neubauer and Future Generations maps principles are written
    without the case prefix used in the case-file ids, so it is added here. Single-decision cases use 'unica'."""
    per = collections.defaultdict(dict)
    for v in yaml.safe_load(open(QUI/'cited-cases'/f'{caso}-mappa-paragrafi.yaml', encoding='utf-8'))['voci']:
        pr = v.get('pronuncia') or 'unica'
        sonde = [s if caso == 'urgenda' or s.startswith(caso + '.') else f'{caso}.{s}' for s in (v.get('sonde') or [])]
        for n in espandi(v['paragrafo']):
            per[pr][n] = sorted(set(per[pr].get(n, [])) | set(sonde))
    return per


def numeri(testo):
    out = []
    for pezzo in re.split(r'\s*(?:,|and|&)\s*', testo):
        m = re.fullmatch(r'(\d+(?:\.\d+)*)\s*(?:[-–]|to)\s*(\d+(?:\.\d+)*)', pezzo.strip())
        out += espandi(f'{m.group(1)}-{m.group(2)}') if m else ([pezzo.strip()] if re.fullmatch(r'\d+(?:\.\d+)*', pezzo.strip()) else [])
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument('--caso', default='urgenda'); caso = ap.parse_args().caso
    USCITA = QUI/'training'/'principi'/f'{caso}_da_paragrafi.jsonl'
    per = mappa(caso)
    if caso == 'urgenda':
        MENZIONE = MENZIONE_URGENDA
    else:
        conf = yaml.safe_load(open(QUI/'cited-cases'/f'{caso}.yaml', encoding='utf-8'))
        forme = sorted({str(f) for f in conf['forme'] if len(str(f)) >= 4}, key=len, reverse=True)
        MENZIONE = re.compile('|'.join(re.escape(f) for f in forme), re.I)
    righe = [json.loads(l) for l in open(QUI/'training'/f'lessicali_{caso}_righe.jsonl', encoding='utf-8')]
    conti = collections.Counter(); USCITA.parent.mkdir(parents=True, exist_ok=True)
    with open(USCITA, 'w', encoding='utf-8') as f:
        for r in righe:
            ctx = r['contesto']
            i = ctx.find('===== PAGINA DELLA CITAZIONE =====')
            j = ctx.find('===== PAGINA SUCCESSIVA', i + 1)
            pag = ctx[i: j if j > 0 else None] if i >= 0 else ctx
            trovati = []
            for m in MENZIONE.finditer(pag):
                fin = pag[m.start(): m.end() + 250]
                # The reference ends at the semicolon: what follows is usually another case with its own paragraphs
                # ("Neubauer, para. 136; Friends of the Irish Environment paras. 7.6 ..."). PAR deliberately omits
                # "at" and "nos.", which would capture page and docket numbers ("Case Nos. 1 BvR ...").
                fin = fin.split(';')[0]
                for p in PAR.finditer(fin):
                    nums = numeri(p.group(1))
                    corte = next((c for c, rx in CORTE if rx.search(pag[max(0, m.start() - 120): m.end() + 250])), None) if caso == 'urgenda' else None
                    for n in nums:
                        dove = [corte] if corte and n in per[corte] else [c for c in per if n in per[c]]
                        if len(dove) == 1:
                            trovati.append((dove[0], n, tuple(per[dove[0]][n])))
            sonde = sorted({s for _, _, ss in trovati for s in ss})
            stato = 'nessun paragrafo' if not trovati else ('paragrafo senza principio' if not sonde else 'principio dai paragrafi')
            conti[stato] += 1
            f.write(json.dumps({'id': r['id'], 'paragrafi': sorted({f'{c}:{n}' for c, n, _ in trovati}), 'principi': sonde,
                                'metodo': 'mappa dei paragrafi'}, ensure_ascii=False) + '\n')
    print(dict(conti), '->', USCITA)


if __name__ == '__main__':
    main()
