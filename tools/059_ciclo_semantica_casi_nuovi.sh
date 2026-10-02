#!/bin/bash
# 02/10/2026: la ricerca delle riprese SENZA NOME per i tre casi nuovi (042_semantica2.py), dal Mac sotto launchd perche'
# sopravviva alla chiusura della sessione (lezione del 01/10: il ciclo nella sessione e' morto e i casi non si sono
# caricati). Le fasi GPU entrano dalla coda del lavoro di DeepSeek nuovo (coda-ds3), mai da lavori a parte.
#   cerca (GPU, gia' in coda: sem_cerca.sh) -> coppie (Mac) -> punteggi T01 (GPU) -> scegli (Mac) -> leggi L06 (GPU)
cd ~/sabin-corpus; S=training/semantica2; P=training/principi; LOG=$S/ciclo_casi_nuovi.log
CASI="klimaseniorinnen cig-parere-clima idh-oc-32-25"
fase() { echo "$(date '+%d/%m %H:%M') $*" >> $LOG; }
r() { ssh -o ConnectTimeout=30 -o BatchMode=yes recas "$@"; }
prendi() { until scp -q "recas:trace/$1" "$1"; do sleep 60; done; }
manda() { until scp -q "$1" "recas:trace/$1"; do sleep 60; done; }
fase "inizio"
# 1. candidati
for c in $CASI; do until r "grep -q '^fine' ~/trace/sem_cerca_$c.out" 2>/dev/null; do sleep 120; done; prendi $S/${c}_candidate.jsonl; done
fase "candidati: $(for c in $CASI; do echo -n "$c $(wc -l < $S/${c}_candidate.jsonl) "; done)"
# 2. coppie per il reranker
for c in $CASI; do .venv/bin/python tools/042_semantica2.py coppie --caso $c >> $LOG 2>&1; manda $P/semantica2_${c}_coppie.jsonl; done
# 3. punteggi T01 dentro il lavoro: vLLM fermo, un processo per GPU (12 pezzi su 4 GPU), vLLM riacceso in ogni caso
r 'cat > ~/trace/chat/coda-ds3/sem_punteggi.sh' <<'X'
H=/lustrehome/climpact; C=$H/trace/chat; CH=$(cat $C/chiave); cd $H/trace
export HOME=$H HF_HOME=$H/trace/hf TMPDIR=$H/trace/tmp
riaccendi() {
  if ! pgrep -u climpact -f "vllm serve" > /dev/null; then echo "riaccendo vLLM $(date)"; nohup $C/vllm2.sh > $C/log/vllm3.log 2>&1 & fi
  until curl -s -m 5 -H "Authorization: Bearer $CH" http://127.0.0.1:8000/v1/models | grep -q deepseek; do sleep 30; done
  echo "vLLM pronto $(date)"
}
trap riaccendi EXIT
echo "fermo vLLM $(date)"; pkill -u climpact -f "vllm serve"; sleep 60
GPU=(${CUDA_VISIBLE_DEVICES//,/ })
pezzo() { CUDA_VISIBLE_DEVICES=${GPU[$1]} venv/bin/python -u tools/028_ripresa_punteggi.py punteggi --caso semantica2_$2 --pezzo $3 --pezzi 4 > $H/trace/sem_rr_$2_$3.out 2>&1; echo "fine $(date)" >> $H/trace/sem_rr_$2_$3.out; }
for g in 0 1 2 3; do ( for c in klimaseniorinnen cig-parere-clima idh-oc-32-25; do pezzo $g $c $g; done ) & done
wait; echo "punteggi finiti $(date)"
X
fase "punteggi in coda"
for c in $CASI; do for k in 0 1 2 3; do until r "grep -q '^fine' ~/trace/sem_rr_${c}_$k.out" 2>/dev/null; do sleep 120; done; prendi $P/semantica2_${c}_punteggi_$k.jsonl; done; done
fase "punteggi presi"
# 4. le pagine da far leggere
for c in $CASI; do .venv/bin/python tools/042_semantica2.py scegli --caso $c --n 200 >> $LOG 2>&1; manda $S/${c}_da_leggere.jsonl; done
# 5. la lettura di DeepSeek (L06)
r 'cat > ~/trace/chat/coda-ds3/sem_leggi.sh' <<'X'
H=/lustrehome/climpact; C=$H/trace/chat; cd $H/trace
for c in klimaseniorinnen cig-parere-clima idh-oc-32-25; do
  $H/trace/venv/bin/python -u tools/042_semantica2.py leggi --caso $c --paralleli 32 --base-url http://127.0.0.1:8000/v1 --chiave-file $C/chiave --modello deepseek-v4-flash
done > $C/log/sem_leggi.log 2>&1
echo FINITO > $C/log/sem_leggi_fine.txt
X
fase "letture in coda"
until r "test -s ~/trace/chat/log/sem_leggi_fine.txt" 2>/dev/null; do sleep 120; done
for c in $CASI; do prendi $S/${c}_letture.jsonl; done
fase "letture prese: $(for c in $CASI; do echo -n "$c $(wc -l < $S/${c}_letture.jsonl) "; done)"
launchctl bootout gui/$(id -u)/it.climpact.semantica-casi-nuovi 2>/dev/null
