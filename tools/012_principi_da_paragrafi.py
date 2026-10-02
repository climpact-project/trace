"""IL PRINCIPIO CHE UNA CITAZIONE PRENDE, DAI PARAGRAFI CHE CITA (27/09/2026). Senza nessun modello.

   PERCHE'. Nel sistema nuovo (§63.25) ogni citazione esplicita dice quale principio del caso citato
   prende. Quando la citazione indica il paragrafo («Urgenda, para. 5.7.7», «§ 5.6.2», «r.o. 4.83»), la
   mappa dei paragrafi (`cited-cases/<caso>-mappa-paragrafi.yaml`, scritta e controllata a mano il 23/09)
   da' la risposta: e' l'etichetta piu' sicura che abbiamo, e non viene da un modello linguistico, quindi
   si puo' usare per addestrare (regola del progetto: le etichette vengono da persone o da regole, mai
   dai verdetti di un LLM).

   COME. Nella pagina della citazione si cerca ogni menzione del caso; nei 250 caratteri che seguono si
   cercano i numeri di paragrafo. La pronuncia (Rechtbank 2015, Hof 2018, Hoge Raad 2019) si decide dalle
   parole vicine («Supreme Court», «District Court», «Court of Appeal», gli anni); se mancano, dal numero
   stesso quando esiste in una sola pronuncia. Gli intervalli della mappa («4.11-4.19») si espandono.

   Uso:  .venv/bin/python tools/012_principi_da_paragrafi.py  -> training/principi/urgenda_da_paragrafi.jsonl
"""
import collections, json, pathlib, re
import yaml
QUI = pathlib.Path(__file__).resolve().parent.parent
MENZIONE_URGENDA = re.compile(r'urgenda|ECLI:NL:(?:HR|GHDHA|RBDHA):20(?:19|18|15):\d+', re.I)
PAR = re.compile(r'(?:paras?\.?|paragraphs?|p[áa]rrs?\.?|par[áa]grafos?|§§?|¶¶?|r\.\s?o\.|rov\.|rn\.|randnummer|margin\s+(?:nos?\.|numbers?))\s*'
                 r'((?:\d{1,3}(?:\.\d{1,3}){0,2})(?!\d)(?:\s*(?:[-–]|to|and|&|,)\s*\d{1,3}(?:\.\d{1,3}){0,2}(?![\d/]))*)', re.I)
# 28/09/2026: erano \d{1,2}, e «Rn. 254» diventava 25, «4.109» diventava 4.10 (trovato su Neubauer, che arriva a Rn. 270).
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


def mappa(caso='urgenda', campo='sonde'):
    """Pronuncia -> paragrafo -> principi. Nelle mappe di Neubauer e Future Generations i principi sono scritti
    senza il prefisso del caso che hanno negli id dei file dei casi: qui si aggiunge. Neubauer ha una pronuncia sola."""
    per = collections.defaultdict(dict)
    for v in yaml.safe_load(open(QUI/'cited-cases'/f'{caso}-mappa-paragrafi.yaml', encoding='utf-8'))['voci']:
        pr = v.get('pronuncia') or 'unica'
        sonde = [s if caso == 'urgenda' or s.startswith(caso + '.') else f'{caso}.{s}' for s in (v.get(campo) or [])]
        # «§§ 1-9», «§ 527», «para. 5.7.7» (mappe dal 01/10/2026): il segno davanti al numero non conta
        # il campo si chiama «paragrafo» o «paragrafi»; davanti al numero «§§», «para.», «Rn.», «párrs.» (01/10/2026)
        par_ = str(v.get('paragrafo', v.get('paragrafi', '')))
        for n in espandi(re.sub(r'^\s*(?:§§?|paras?\.?|Rn\.|p[áa]rrs?\.?)\s*', '', par_, flags=re.I)):
            per[pr][n] = sorted(set(per[pr].get(n, [])) | set(sonde))
    # LE SONDE DEL 01/10/2026 DI NEUBAUER SONO DEFINITE PER RANDNUMMER (il PI: «Rn. 117-122, 183-194»): ogni Rn degli
    # intervalli scritti nel file del caso porta la sonda, anche dove la mappa non ha una voce per quel numero.
    if campo.startswith('sonde_P') and caso == 'neubauer':
        for q in yaml.safe_load(open(QUI/'cited-cases'/f"{caso}-{campo.split('_')[1]}.yaml", encoding='utf-8'))['semantic_queries']:
            testo = q.get('paragrafi', '').split(';')[0]
            nums = {n for a, b in re.findall(r'(\d+)\s*-\s*(\d+)', testo) for n in range(int(a), int(b) + 1)}
            nums |= {int(x) for x in re.findall(r'(?<![\d-])(\d+)(?![\d-])', testo)}
            for n in nums:
                per['unica'][str(n)] = sorted(set(per['unica'].get(str(n), [])) | {q['id']})
    return per


def numeri(testo):
    out = []
    for pezzo in re.split(r'\s*(?:,|and|&)\s*', testo):
        m = re.fullmatch(r'(\d+(?:\.\d+)*)\s*(?:[-–]|to)\s*(\d+(?:\.\d+)*)', pezzo.strip())
        out += espandi(f'{m.group(1)}-{m.group(2)}') if m else ([pezzo.strip()] if re.fullmatch(r'\d+(?:\.\d+)*', pezzo.strip()) else [])
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument('--caso', default='urgenda')
    ap.add_argument('--sonde', default='', help="'P03': le sonde del PI del 01/10/2026 (campo sonde_P03 delle mappe), in un file a parte")
    a = ap.parse_args(); caso = a.caso
    USCITA = QUI/'training'/'principi'/f"{caso}_da_paragrafi{'_' + a.sonde if a.sonde else ''}.jsonl"
    per = mappa(caso, 'sonde_' + a.sonde if a.sonde else 'sonde')
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
                # IL RIFERIMENTO FINISCE AL PUNTO E VIRGOLA: dopo c'e' di solito un altro caso con i suoi paragrafi
                # («Neubauer, para. 136; Friends of the Irish Environment paras. 7.6 ...»). Tolti anche «at» e «nos.»,
                # che prendevano pagine e numeri di ruolo («Case Nos. 1 BvR ...»). 28/09/2026.
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
