#!/bin/bash
# 02/10/2026: la serie P09 del parere della CIG (P07 con la sonda dell'1,5 riscritta, prova delle alternative).
# Punteggi T01 solo per la sonda nuova (le altre sei identiche a P07, stesso modello), pagine attorno (R08), letture
# L05 e L04 con TRACE_SONDE=P09, caricamento, controlli. Da launchd: sopravvive alla chiusura della sessione.
cd ~/sabin-corpus; P=training/principi; C=cig-parere-clima; LOG=$P/ciclo_p09_cig.log
fase() { echo "$(date '+%d/%m %H:%M') $*" >> $LOG; }
r() { ssh -o ConnectTimeout=30 -o BatchMode=yes recas "$@"; }
prendi() { until scp -q "recas:trace/$1" "$1"; do sleep 60; done; }
manda() { until scp -q "$1" "recas:trace/$1"; do sleep 60; done; }
fase inizio
# 1. punteggi della sonda nuova, dentro il lavoro vecchio (vLLM fermo e riacceso)
r 'cat > ~/trace/chat/coda-ds2/p09_punteggi.sh' <<'X'
H=/lustrehome/climpact; C=$H/trace/chat; CH=$(cat $C/chiave); cd $H/trace
export HOME=$H HF_HOME=$H/trace/hf TMPDIR=$H/trace/tmp
riaccendi() {
  if ! pgrep -u climpact -f "vllm serve" > /dev/null; then echo "riaccendo vLLM $(date)"; nohup $C/vllm2.sh > $C/log/vllm2.log 2>&1 & fi
  until curl -s -m 5 -H "Authorization: Bearer $CH" http://127.0.0.1:8000/v1/models | grep -q deepseek; do sleep 30; done
  echo "vLLM pronto $(date)"
}
trap riaccendi EXIT
pkill -u climpact -f "vllm serve"; sleep 60
GPU=(${CUDA_VISIBLE_DEVICES//,/ })
for k in 0 1 2 3; do ( CUDA_VISIBLE_DEVICES=${GPU[$k]} venv/bin/python -u tools/ripresa_punteggi.py punteggi --caso cig-parere-clima_P09obiettivo --pezzo $k --pezzi 4 > $H/trace/p09_$k.out 2>&1; echo "fine $(date)" >> $H/trace/p09_$k.out ) & done
wait
X
for k in 0 1 2 3; do until r "grep -q '^fine' ~/trace/p09_$k.out" 2>/dev/null; do sleep 60; done; prendi $P/${C}_P09obiettivo_punteggi_$k.jsonl; done
fase "punteggi della sonda nuova presi"
# 2. i punteggi P09: quelli di P07 con la sonda dell'1,5 sostituita
.venv/bin/python - <<'X' >> $LOG 2>&1
import glob, json, pathlib
P = pathlib.Path('training/principi'); c = 'cig-parere-clima'
nuovi = [json.loads(l) for f in sorted(glob.glob(str(P/f'{c}_P09obiettivo_punteggi_*.jsonl'))) for l in open(f)]
vecchi = [json.loads(l) for f in sorted(glob.glob(str(P/f'{c}_punteggi_[0-9].jsonl'))) for l in open(f)]
tenuti = [x for x in vecchi if not x['principio'].endswith('obiettivo_1_5')]
with open(P/f'{c}_P09_punteggi_0.jsonl', 'w') as f:
    for x in tenuti + nuovi: f.write(json.dumps(x, ensure_ascii=False) + '\n')
print('P09: tenuti', len(tenuti), 'nuovi', len(nuovi), 'tolti', len(vecchi) - len(tenuti))
X
# 3. le pagine attorno con la serie P09, e le letture
TRACE_SONDE=P09 .venv/bin/python -c "import sys; sys.path.insert(0,'tools'); import leggi_ripresa as LR; LR.prepara('$C')" >> $LOG 2>&1
cp $P/${C}_ripresa_righe_P09.jsonl $P/${C}_ripresa_righe_l04P09.jsonl
manda $P/${C}_ripresa_righe_P09.jsonl; manda $P/${C}_ripresa_righe_l04P09.jsonl; manda $P/${C}_P09_punteggi_0.jsonl
r 'cat > ~/trace/chat/coda-ds2/p09_letture.sh' <<'X'
H=/lustrehome/climpact/trace; C=$H/chat; cd $H; export TRACE_SONDE=P09
A="--base-url http://127.0.0.1:8000/v1 --chiave-file $C/chiave --modello deepseek-v4-flash --paralleli 32"
$H/venv/bin/python -u tools/leggi_ripresa.py leggi --caso cig-parere-clima --etichetta P09 --letture 2 $A > $C/log/p09_L05.log 2>&1 &
$H/venv/bin/python -u tools/leggi_l04.py leggi --caso cig-parere-clima --etichetta l04P09 --letture 2 $A > $C/log/p09_L04.log 2>&1 &
wait; echo FINITO > $C/log/p09_fine.txt
X
fase "letture in coda"
until r 'test -s ~/trace/chat/log/p09_fine.txt' 2>/dev/null; do sleep 120; done
prendi $P/${C}_ripresa_deepseek_P09.jsonl; prendi $P/${C}_ripresa_deepseek_l04P09.jsonl
fase "letture prese: $(wc -l < $P/${C}_ripresa_deepseek_P09.jsonl) L05, $(wc -l < $P/${C}_ripresa_deepseek_l04P09.jsonl) L04"
# 4. caricamento con P09 e controlli
for i in 1 2 3 4; do TRACE_SONDE=P09 .venv/bin/python tools/carica_ripresa.py --caso $C --principi-da-l04 --scrivi > /tmp/p09_carica.txt 2>&1 && break; sleep 30; done
fase "caricato: $(grep -E '^scritte' /tmp/p09_carica.txt) $(grep -E 'senza proposta' /tmp/p09_carica.txt | tr -d ' ')"
fase "FINITO: resta da mettere P09 in uso in sonde.py, nel registro e controllare"
launchctl bootout gui/$(id -u)/it.climpact.p09-cig 2>/dev/null
