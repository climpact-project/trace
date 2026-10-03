"""Righe per far votare a DeepSeek le pagine della distillazione (secondo maestro, §5 del diario).
   Stesso formato delle righe di Urgenda, cosi' le legge `086_deepseek_api.py --parti distilla`.
   L'etichetta non esiste (sono pagine mai giudicate): vale 0 solo per non rompere il riepilogo."""
import gzip, json, pathlib, sys
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
_m_distilla = __import__('041_distilla')
sonde_e_domande = _m_distilla.sonde_e_domande
testi, _, _ = sonde_e_domande()
voti = json.load(open(QUI/'training'/'distilla'/'voti.json'))
serve = {v['pagina'] for v in voti}; testo = {}
with gzip.open(QUI/'index'/'pagine'/'pagine.jsonl.gz', 'rt', encoding='utf-8') as f:
    for l in f:
        x = json.loads(l)
        if x['id'] in serve:
            testo[x['id']] = x['testo']
with open(QUI/'training'/'urgenda_decisione_distilla_corrette_larghe.jsonl', 'w', encoding='utf-8') as f:
    for v in voti:
        s = v['sonda']
        f.write(json.dumps({'id': f"{s}|{v['pagina']}", 'etichetta': 0, 'sonda_id': s, 'case_id': '',
                            'sonda_testo': sorted(testi[s])[0], 'finestra': testo[v['pagina']]}, ensure_ascii=False) + '\n')
print('righe', len(voti))
