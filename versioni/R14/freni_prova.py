"""LA PROVA DEI FRENI su casi che DEVONO fallire (30/09/2026): le pagine rotte fra le 1.000 della semantica e le
   risposte inventate (prova copiata dal principio nel prompt). Se questa prova passa, i freni vedono quel che devono."""
import gzip, json, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from freni import leggibile, verifica
if __name__ == '__main__':
    import giornale  # il giornale delle operazioni (02/10/2026)
    giornale.avvia()
QUI = pathlib.Path(__file__).resolve().parent.parent
S = QUI/'training'/'semantica2'
D = [json.loads(l) for l in open(S/'urgenda_da_leggere.jsonl', encoding='utf-8')]
serve = {d['pagina_id'] for d in D}
testi = {}
# 02/10/2026: le pagine DI PRIMA dell'OCR. Dal 02/10 l'indice ha il testo OCR al posto delle pagine rotte (Multnomah
# compreso): la prova deve restare sulle pagine rotte vere, se no non prova piu' niente.
with gzip.open(QUI/'index'/'pagine'/'pagine.prima-ocr-2026-10-01.jsonl.gz', 'rt', encoding='utf-8') as f:
    for l in f:
        x = json.loads(l)
        if x['id'] in serve: testi[x['id']] = x['testo']
rotte = {pid for pid in serve if not leggibile(testi.get(pid, ''))[0]}
print('freno 1, pagine illeggibili:', len(rotte), 'su', len(serve))
multnomah = [pid for pid in serve if 'multnomah' in pid]
assert sum(1 for pid in multnomah if pid in rotte) >= 15, 'il freno 1 deve prendere le pagine rotte di County of Multnomah'
assert 40 <= len(rotte) <= 170, 'il freno 1 deve trovare le pagine rotte (circa 60 pagine, 130 letture)'
# i testi che stavano nel prompt: il principio (titolo e testo) dentro domanda_ds
prompt_di = {}
for d in D:
    m = re.search(r'Il principio in questione:\n(.*?)\n\n', d.get('domanda_ds', ''), re.S)
    prompt_di[d['pagina_id']] = [m.group(1)] if m else []
L = [json.loads(l) for l in open(S/'urgenda_letture.jsonl', encoding='utf-8')]
c = {'trovata': 0, 'non trovata': 0, 'inventata': 0, 'assente': 0}; inventate_su_rotte = 0
for x in L:
    pid = x['pagina_id']
    for lett in x.get('letture') or []:
        if not isinstance(lett, dict): continue
        e = verifica(lett.get('prova'), testi.get(pid, ''), prompt_di.get(pid, []))
        c[e] += 1
        if e == 'inventata' and pid in rotte: inventate_su_rotte += 1
print('freni 2 e 3, prove:', c, '| inventate su pagine rotte:', inventate_su_rotte)
assert c['inventata'] >= 3, 'il freno 3 deve trovare le prove copiate dal prompt'
assert c['non trovata'] > 0
# R14 (04/10/2026): la prova cercata anche nel testo dell'atto senza i segni del sistema e con le parole spezzate a capo
# ricucite. Deve trovare tutto quello che trovava prima e continuare a fallire dove deve: le stesse prove inventate.
c14 = {'trovata': 0, 'non trovata': 0, 'inventata': 0, 'assente': 0}; perse = 0
for x in L:
    pid = x['pagina_id']
    for lett in x.get('letture') or []:
        if not isinstance(lett, dict): continue
        e0 = verifica(lett.get('prova'), testi.get(pid, ''), prompt_di.get(pid, []))
        e = verifica(lett.get('prova'), testi.get(pid, ''), prompt_di.get(pid, []), True)
        c14[e] += 1
        perse += e0 == 'trovata' and e != 'trovata'
print('R14, prove:', c14, '| trovate prima e non piu\':', perse)
assert perse == 0, 'R14 non deve perdere prove trovate'
assert c14['inventata'] == c['inventata'], 'R14 deve vedere le stesse prove copiate dal prompt'
assert c14['non trovata'] > 0
print('FRENI OK: falliscono dove devono')
