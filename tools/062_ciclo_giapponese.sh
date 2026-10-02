#!/bin/bash
# 02/10/2026: le 10 citazioni col nome trovate dopo aver aggiunto le forme giapponesi (ricorso Climate Justice Case,
# 58b2: KlimaSeniorinnen «気候保護のためのシニア女性», parere della CIG «本ICJ 勧告的意見»): tipo, punteggi T01 (brano e
# pagine attorno ancora senza punteggio), pagine attorno, letture L05 e L04 (le letture dei casi riprendono da dove
# erano: si aggiungono solo le righe nuove), caricamento, controlli. Da launchd.
cd ~/sabin-corpus; P=training/principi; O=training/ocr; LOG=$O/ciclo_giapponese.log
fase() { echo "$(date '+%d/%m %H:%M') $*" >> $LOG; }
r() { ssh -o ConnectTimeout=30 -o BatchMode=yes recas "$@"; }
prendi() { until scp -q "recas:trace/$1" "$1"; do sleep 60; done; }
manda() { until scp -q "$1" "recas:trace/$1"; do sleep 60; done; }
fase inizio
r 'mkdir -p ~/trace/training/ocr ~/trace/training/principi'
for c in klimaseniorinnen cig-parere-clima; do manda training/lessicali_${c}_righe.jsonl; manda $O/righe_giapponese_$c.txt; done
manda $P/giapponese_coppie.jsonl
r 'cat > ~/trace/chat/coda-ds3/giapp_tipo_punteggi.sh' <<'X'
H=/lustrehome/climpact; C=$H/trace/chat; CH=$(cat $C/chiave); cd $H/trace
export HOME=$H HF_HOME=$H/trace/hf TMPDIR=$H/trace/tmp
A="--base-url http://127.0.0.1:8000/v1 --chiave-file $C/chiave --modello deepseek-v4-flash --paralleli 16"
for c in klimaseniorinnen cig-parere-clima; do venv/bin/python -u tools/024_classifica_lessicali.py leggi --caso $c --gruppo tutte --letture 2 --solo-id training/ocr/righe_giapponese_$c.txt $A; done > $C/log/giapp_tipo.log 2>&1
riaccendi() {
  if ! pgrep -u climpact -f "vllm serve" > /dev/null; then echo "riaccendo vLLM $(date)"; nohup $C/vllm2.sh > $C/log/vllm3.log 2>&1 & fi
  until curl -s -m 5 -H "Authorization: Bearer $CH" http://127.0.0.1:8000/v1/models | grep -q deepseek; do sleep 30; done
  echo "vLLM pronto $(date)"
}
trap riaccendi EXIT
pkill -u climpact -f "vllm serve"; sleep 60
GPU=(${CUDA_VISIBLE_DEVICES//,/ })
CUDA_VISIBLE_DEVICES=${GPU[0]} venv/bin/python -u tools/028_ripresa_punteggi.py punteggi --caso giapponese --pezzo 0 --pezzi 1 > $H/trace/giapp_punteggi.out 2>&1
echo "fine $(date)" >> $H/trace/giapp_punteggi.out
X
fase "tipo e punteggi in coda"
until r "grep -q '^fine' ~/trace/giapp_punteggi.out" 2>/dev/null; do sleep 120; done
for c in klimaseniorinnen cig-parere-clima; do prendi training/lessicali_${c}_deepseek.jsonl; done
prendi $P/giapponese_punteggi_0.jsonl
for c in klimaseniorinnen cig-parere-clima; do for i in 1 2 3; do .venv/bin/python tools/025_carica_lessicali.py --caso $c --etichetta "" --scrivi >> $LOG 2>&1 && break; sleep 30; done; done
fase "tipo caricato"
.venv/bin/python - <<'X' >> $LOG 2>&1
import json, pathlib
P = pathlib.Path('training/principi')
coppie = [json.loads(l) for l in open(P/'giapponese_coppie.jsonl')]
punti = [json.loads(l) for l in open(P/'giapponese_punteggi_0.jsonl')]
out = {'klimaseniorinnen': open(P/'klimaseniorinnen_punteggi_giapp.jsonl', 'w'), 'cig-parere-clima': open(P/'cig-parere-clima_P09_punteggi_giapp.jsonl', 'w')}
for c, s in zip(coppie, punti):
    out[c['caso']].write(json.dumps(s, ensure_ascii=False) + '\n')
print('punteggi divisi', len(punti))
X
.venv/bin/python -c "import sys; sys.path.insert(0,'tools'); import leggi_ripresa as LR; LR.prepara('klimaseniorinnen'); LR.prepara('cig-parere-clima')" >> $LOG 2>&1
.venv/bin/python - <<'X' >> $LOG 2>&1
import json, pathlib
P = pathlib.Path('training/principi'); O = pathlib.Path('training/ocr')
for c, base, etichette in (('klimaseniorinnen', 'klimaseniorinnen_ripresa_righe.jsonl', ('v2', 'l04nuove')),
                           ('cig-parere-clima', 'cig-parere-clima_ripresa_righe_P09.jsonl', ('P09', 'l04P09'))):
    ids = set(O.joinpath(f'righe_giapponese_{c}.txt').read_text().split())
    nuove = [l for l in open(P/base) if json.loads(l)['id'] in ids]
    for et in etichette:
        f = P/f'{c}_ripresa_righe_{et}.jsonl'
        tenute = [l for l in open(f) if json.loads(l)['id'] not in ids]
        open(f, 'w').writelines(tenute + nuove)
    print(c, 'righe aggiunte alle letture', len(nuove))
X
for f in klimaseniorinnen_ripresa_righe_v2 klimaseniorinnen_ripresa_righe_l04nuove cig-parere-clima_ripresa_righe_P09 cig-parere-clima_ripresa_righe_l04P09; do manda $P/$f.jsonl; done
manda $P/klimaseniorinnen_punteggi_giapp.jsonl; manda $P/cig-parere-clima_P09_punteggi_giapp.jsonl
r 'cat > ~/trace/chat/coda-ds3/giapp_letture.sh' <<'X'
H=/lustrehome/climpact/trace; C=$H/chat; cd $H
A="--base-url http://127.0.0.1:8000/v1 --chiave-file $C/chiave --modello deepseek-v4-flash --paralleli 16"
$H/venv/bin/python -u tools/031_leggi_ripresa.py leggi --caso klimaseniorinnen --etichetta v2 --letture 2 $A > $C/log/giapp_letture.log 2>&1
$H/venv/bin/python -u tools/032_leggi_l04.py leggi --caso klimaseniorinnen --etichetta l04nuove --letture 2 $A >> $C/log/giapp_letture.log 2>&1
TRACE_SONDE=P09 $H/venv/bin/python -u tools/031_leggi_ripresa.py leggi --caso cig-parere-clima --etichetta P09 --letture 2 $A >> $C/log/giapp_letture.log 2>&1
TRACE_SONDE=P09 $H/venv/bin/python -u tools/032_leggi_l04.py leggi --caso cig-parere-clima --etichetta l04P09 --letture 2 $A >> $C/log/giapp_letture.log 2>&1
echo FINITO > $C/log/giapp_fine.txt
X
fase "letture in coda"
until r 'test -s ~/trace/chat/log/giapp_fine.txt' 2>/dev/null; do sleep 120; done
for f in klimaseniorinnen_ripresa_deepseek_v2 klimaseniorinnen_ripresa_deepseek_l04nuove cig-parere-clima_ripresa_deepseek_P09 cig-parere-clima_ripresa_deepseek_l04P09; do prendi $P/$f.jsonl; done
for c in klimaseniorinnen cig-parere-clima; do for i in 1 2 3 4; do .venv/bin/python tools/035_carica_ripresa.py --caso $c --principi-da-l04 --scrivi > /tmp/giapp_carica_$c.txt 2>&1 && break; sleep 30; done; fase "$c caricato: $(grep -E '^scritte' /tmp/giapp_carica_$c.txt)"; done
for i in 1 2 3; do .venv/bin/python tools/036_controllo_completezza.py --scrivi > /tmp/giapp_controllo.txt 2>&1 && break; sleep 30; done
.venv/bin/python tools/037_controllo_finestra.py > /tmp/giapp_finestra.txt 2>&1
cat /tmp/giapp_controllo.txt /tmp/giapp_finestra.txt >> $LOG; fase FINITO
launchctl bootout gui/$(id -u)/it.climpact.giapponese 2>/dev/null
