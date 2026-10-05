"""Prova a secco della riparazione delle prove respinte da R16 (tools/ripara_prova.py), 04/10/2026. Niente scritto in banca dati
(si legge solo il codice delle righe). Scrive training/misure/R16-RIPARAZIONE.md e R16-riparazione.json."""
import json, sys, collections, random, gzip, re, pathlib
R = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(R/'tools'))
import freni as F, ripara_prova as RP
Q = R/'training'/'principi'
OCR = {k.split('#')[0] for k in json.load(open(R/'training'/'ocr'/'pagine_sostituite.json'))}
casi = {'urgenda': '', 'neubauer': 'P05', 'future-generations': 'P05', 'klimaseniorinnen': '', 'cig-parere-clima': 'P09', 'idh-oc-32-25': ''}
righe = {}; serve = set()
for c, s in casi.items():
    for l in open(Q/f'{c}_ripresa_righe_{s}cinque.jsonl'):
        x = json.loads(l); righe[(c, x['id'])] = x
        for v in x['vicine']:
            serve.add(f"{x['document_id']}#p{v['pagina']}"); serve.add(f"{x['document_id']}#p{v['pagina'] + 1}")
testi = {}
with gzip.open(R/'index'/'pagine'/'pagine.jsonl.gz', 'rt') as f:
    for l in f:
        x = json.loads(l)
        if x['id'] in serve:
            testi[x['id']] = x['testo'][:12000]
casi_r = []
for c, s in casi.items():
    for l in open(Q/f'{c}_ripresa_deepseek_{s}cinque.jsonl'):
        try:
            x = json.loads(l)
        except ValueError:
            continue
        r = righe.get((c, x['id']))
        if not r:
            continue
        d = r['document_id']; ocr = d in OCR
        pag = {}
        for v in r['vicine']:
            t = v['testo']; full = testi.get(f"{d}#p{v['pagina']}", '')
            if full.startswith(t[:200]) and len(full) > len(t):
                t = full
            pag[v['pagina']] = (t, testi.get(f"{d}#p{v['pagina'] + 1}", ''))
        for y in x.get('letture') or []:
            if not isinstance(y, dict):
                continue
            it = []
            if y.get('frase_sostenuta'):
                it.append(('frase', str(y['frase_sostenuta']), r['contesto'], ''))
            for v in y.get('vicine') or []:
                if isinstance(v, dict) and v.get('prova') and v.get('pagina') in pag:
                    it.append(('prova', str(v['prova']), *pag[v['pagina']]))
            for k, p, t, seg in it:
                if F.prova_trovata(p, t, True) and not F.prova_intera(p, t, seg, ocr):
                    casi_r.append((c, x['id'], k, p, t, seg))
print('respinte da R16:', len(casi_r))


def nota_della_menzione(contesto):
    """il numero della nota in cui sta il nome segnato, se il nome e' in una riga di nota («12 See ⟦Urgenda⟧ ...»)"""
    i = contesto.find('⟦')
    if i < 0:
        return None
    riga = contesto[contesto.rfind('\n', 0, i) + 1:i]
    m = re.match(r'\s*\(?(\d{1,4})[\).]?\s', riga)
    return m.group(1) if m else None


def menziona(frase, contesto, nome):
    f = frase.lower()
    parole = [w for w in re.findall(r'[^\W\d_]{4,}', (nome or '').lower())]
    if parole and any(w in f for w in parole):
        return True
    n = nota_della_menzione(contesto)
    return bool(n and re.search(rf'(?<=[^\W\d_]|[.,;:)”"’»\]]){n}(?!\d)', frase))


out = []; conti = collections.defaultdict(collections.Counter)
for c, rid, k, p, t, seg in casi_r:
    e = RP.ripara(p, t, seg)
    conti[c][f'{k} {e["esito"]}'] += 1
    rec = {'caso': c, 'id': rid, 'cosa': k, 'modello': p, 'esito': e['esito'], 'riparata': e.get('frase', ''), 'motivo': e.get('motivo', ''),
           'gruppi': e.get('gruppi'), 'dalla_pagina_dopo': e.get('dalla_pagina_dopo'), 'salti_tolti': e.get('salti_tolti'), 'senza_note': e.get('senza_note')}
    if k == 'frase' and e['esito'] == 'riparata':
        rec['menziona'] = menziona(e['frase'], t, e.get('nome'))
        conti[c]['frase riparata senza menzione' if not rec['menziona'] else 'frase riparata con menzione'] += 1
    out.append(rec)
from google.cloud import firestore
db = firestore.Client(project='climpact-drp')
ids = sorted({o['id'] for o in out}); cod = {}
for i in range(0, len(ids), 300):
    for d in db.get_all([db.collection('corpus_rows').document(x) for x in ids[i:i + 300]], field_paths=['codice']):
        if d.exists:
            cod[d.id] = (d.to_dict() or {}).get('codice')
for o in out:
    o['codice'] = cod.get(o['id'])
json.dump(out, open(R/'training'/'misure'/'R16-riparazione.json', 'w'), ensure_ascii=False, indent=1)
tot = collections.Counter()
for c in conti:
    tot.update(conti[c])
random.seed(20261004)
camp = random.sample([o for o in out if o['esito'] == 'riparata'], 15)
md = ['# R16: la riparazione delle prove respinte (prova a secco, 04/10/2026)', '',
      'Niente scritto in banca dati. Codice: `tools/ripara_prova.py` (taglio delle frasi di R15, `frase_sostenuta.confini`); '
      'prova: `training/misure/R16-riparazione.py`; ogni caso in `R16-riparazione.json`.', '',
      'Dati: le letture L05 del ciclo delle cinque letture (03/10), pagine attorno intere e pagina dopo dall\'indice; '
      'le prove e frasi che R14 trova e R16 respinge.', '',
      '| caso | frasi riparate | frasi non trovate | prove riparate | prove non trovate | frasi riparate senza la menzione del caso |',
      '|---|---|---|---|---|---|']
for c in casi:
    k = conti[c]
    md.append(f"| {c} | {k['frase riparata']} | {k['frase non trovata']} | {k['prova riparata']} | {k['prova non trovata']} | {k['frase riparata senza menzione']} |")
md.append(f"| tutti | {tot['frase riparata']} | {tot['frase non trovata']} | {tot['prova riparata']} | {tot['prova non trovata']} | {tot['frase riparata senza menzione']} |")
md += ['', '«Menzione del caso»: la frase riparata contiene una parola del nome segnato ⟦ ⟧ nel contesto, o il richiamo della nota '
       'in cui sta il nome. Vale per le frasi sostenute; le prove delle pagine attorno, per definizione, stanno su pagine senza il nome.', '',
       '## 15 esempi a caso (seme 20261004)', '']
for o in camp:
    md += [f"### {o['codice'] or o['id']} ({o['caso']}, {'frase sostenuta' if o['cosa'] == 'frase' else 'prova di una pagina attorno'})", '',
           f"- DeepSeek: «{o['modello']}»", f"- dall'atto: «{o['riparata']}»"]
    if o['cosa'] == 'frase':
        md.append(f"- menzione del caso nella frase riparata: {'si' if o.get('menziona') else 'NO'}")
    if o.get('gruppi', 1) and o['gruppi'] > 1:
        md.append(f"- la prova del modello veniva da {o['gruppi']} punti dell'atto: tenuto quello con la menzione o con piu' testo vero")
    md.append('')
(R/'training'/'misure'/'R16-RIPARAZIONE.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
print(dict(tot))
