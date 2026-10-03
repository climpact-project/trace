#!/bin/bash
# 02/10/2026: la catena ocr3 aveva preso da ReCaS i file dei punteggi (60 righe su 1.061) e del tipo (10 su 11) prima
# che fossero finiti. Qui si rifa' la parte dopo, e ogni file si prende solo quando ha il numero di righe atteso.
cd ~/sabin-corpus; P=training/principi; O=training/ocr; LOG=$O/ciclo_ocr3_rifai.log
fase() { echo "$(date '+%d/%m %H:%M') $*" >> $LOG; }
r() { ssh -o ConnectTimeout=30 -o BatchMode=yes recas "$@"; }
prendi_n() { # file righe_attese
  until [ "$(r "wc -l < ~/trace/$1" 2>/dev/null)" = "$2" ]; do sleep 60; done
  until scp -q "recas:trace/$1" "$1" && [ "$(wc -l < "$1" | tr -d ' ')" = "$2" ]; do sleep 30; done; }
manda() { until scp -q "$1" "recas:trace/$1"; do sleep 60; done; }
fase inizio
prendi_n training/lessicali_urgenda_deepseek_ocr3.jsonl 11; prendi_n training/lessicali_neubauer_deepseek_ocr3.jsonl 4
for c in urgenda neubauer; do for i in 1 2 3; do .venv/bin/python tools/025_carica_lessicali.py --caso $c --etichetta ocr3 --sovrascrivi --scrivi >> $LOG 2>&1 && break; sleep 30; done; done
fase "tipo ricaricato"
prendi_n $P/ocr3_punteggi_0.jsonl $(wc -l < $P/ocr3_coppie.jsonl | tr -d ' ')
.venv/bin/python - <<'X' >> $LOG 2>&1
import json, pathlib
P = pathlib.Path('training/principi')
coppie = [json.loads(l) for l in open(P/'ocr3_coppie.jsonl')]
punti = [json.loads(l) for l in open(P/'ocr3_punteggi_0.jsonl')]
assert len(coppie) == len(punti)
out = {'urgenda': open(P/'urgenda_punteggi_ocr3.jsonl', 'w'), 'neubauer': open(P/'neubauer_P05_punteggi_ocr3.jsonl', 'w')}
n = {'urgenda': 0, 'neubauer': 0}
for c, s in zip(coppie, punti):
    assert c['principio'] == s['principio'] and c.get('riga') == s.get('riga') and c.get('pagina_id') == s.get('pagina_id')
    out[c['caso']].write(json.dumps(s, ensure_ascii=False) + '\n'); n[c['caso']] += 1
print('punteggi ocr3 divisi', n)
X
.venv/bin/python -c "import sys; sys.path.insert(0,'tools'); import leggi_ripresa as LR; LR.prepara('urgenda'); LR.prepara('neubauer')" >> $LOG 2>&1
.venv/bin/python - <<'X' >> $LOG 2>&1
import json, pathlib
P = pathlib.Path('training/principi'); O = pathlib.Path('training/ocr')
for c, base in (('urgenda', 'urgenda_ripresa_righe.jsonl'), ('neubauer', 'neubauer_ripresa_righe_P05.jsonl')):
    ids = set(O.joinpath(f'righe_ocr3_{c}.txt').read_text().split())
    righe = [l for l in open(P/base) if json.loads(l)['id'] in ids]
    for et in (('ocr3', 'l04ocr3') if c == 'urgenda' else ('P05ocr3', 'l04P05ocr3')):
        open(P/f'{c}_ripresa_righe_{et}.jsonl', 'w').writelines(righe)
    print(c, 'righe da rileggere', len(righe))
X
for f in urgenda_ripresa_righe_ocr3 urgenda_ripresa_righe_l04ocr3 neubauer_ripresa_righe_P05ocr3 neubauer_ripresa_righe_l04P05ocr3; do manda $P/$f.jsonl; done
manda $P/urgenda_punteggi_ocr3.jsonl; manda $P/neubauer_P05_punteggi_ocr3.jsonl
# le letture di prima (sulle pagine attorno scelte coi punteggi incompleti) si mettono da parte: si rileggono tutte e 15
r 'cd ~/trace/training/principi && for f in urgenda_ripresa_deepseek_ocr3 urgenda_ripresa_deepseek_l04ocr3 neubauer_ripresa_deepseek_P05ocr3 neubauer_ripresa_deepseek_l04P05ocr3; do [ -f $f.jsonl ] && mv $f.jsonl $f.punteggi-incompleti.jsonl; done; rm -f ~/trace/chat/log/ocr3b_fine.txt'
r 'cat > ~/trace/chat/coda-ds2/ocr3b_letture.sh' <<'X'
H=/lustrehome/climpact/trace; C=$H/chat; cd $H
A="--base-url http://127.0.0.1:8000/v1 --chiave-file $C/chiave --modello deepseek-v4-flash --paralleli 16"
$H/venv/bin/python -u tools/031_leggi_ripresa.py leggi --caso urgenda --etichetta ocr3 --letture 2 $A > $C/log/ocr3b_letture.log 2>&1
$H/venv/bin/python -u tools/032_leggi_l04.py leggi --caso urgenda --etichetta l04ocr3 --letture 2 $A >> $C/log/ocr3b_letture.log 2>&1
TRACE_SONDE=P05 $H/venv/bin/python -u tools/031_leggi_ripresa.py leggi --caso neubauer --etichetta P05ocr3 --letture 2 $A >> $C/log/ocr3b_letture.log 2>&1
TRACE_SONDE=P05 $H/venv/bin/python -u tools/032_leggi_l04.py leggi --caso neubauer --etichetta l04P05ocr3 --letture 2 $A >> $C/log/ocr3b_letture.log 2>&1
echo FINITO > $C/log/ocr3b_fine.txt
X
fase "letture in coda"
until r 'test -s ~/trace/chat/log/ocr3b_fine.txt' 2>/dev/null; do sleep 60; done
prendi_n $P/urgenda_ripresa_deepseek_ocr3.jsonl 11; prendi_n $P/urgenda_ripresa_deepseek_l04ocr3.jsonl 11
prendi_n $P/neubauer_ripresa_deepseek_P05ocr3.jsonl 4; prendi_n $P/neubauer_ripresa_deepseek_l04P05ocr3.jsonl 4
.venv/bin/python - <<'X' >> $LOG 2>&1
import json, pathlib
P = pathlib.Path('training/principi')
for nuovo, dentro in (('urgenda_ripresa_deepseek_ocr3', 'urgenda_ripresa_deepseek_ocr2'), ('urgenda_ripresa_deepseek_l04ocr3', 'urgenda_ripresa_deepseek_l04ocr2'),
                      ('neubauer_ripresa_deepseek_P05ocr3', 'neubauer_ripresa_deepseek_P05'), ('neubauer_ripresa_deepseek_l04P05ocr3', 'neubauer_ripresa_deepseek_l04P05')):
    N = {json.loads(l)['id']: l for l in open(P/f'{nuovo}.jsonl')}
    f = P/f'{dentro}.jsonl'
    vecchie = [l for l in open(f) if json.loads(l)['id'] not in N]
    open(f, 'w').writelines(vecchie + list(N.values()))
    print(dentro, 'sostituite o aggiunte', len(N))
X
for c in urgenda neubauer; do for i in 1 2 3 4; do .venv/bin/python tools/035_carica_ripresa.py --caso $c --principi-da-l04 --scrivi > /tmp/ocr3b_carica_$c.txt 2>&1 && break; sleep 30; done; fase "$c caricato: $(grep -E '^scritte' /tmp/ocr3b_carica_$c.txt)"; done
for i in 1 2 3; do .venv/bin/python tools/036_controllo_completezza.py --scrivi > /tmp/ocr3b_controllo.txt 2>&1 && break; sleep 30; done
.venv/bin/python tools/037_controllo_finestra.py > /tmp/ocr3b_finestra.txt 2>&1
cat /tmp/ocr3b_controllo.txt /tmp/ocr3b_finestra.txt >> $LOG; fase FINITO
launchctl bootout gui/$(id -u)/it.climpact.ocr3b 2>/dev/null
