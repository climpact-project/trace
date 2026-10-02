#!/bin/bash
# 01/10/2026: la pipeline dei tre casi nuovi (KlimaSeniorinnen, parere della CIG, OC-32/25) appena ReCaS da' i punteggi.
# Per ogni caso: punteggi del reranker (finestra intera, R08) -> pagine vicine -> letture L04 (principi) e L05 (seguito,
# con il fascicolo) sul secondo DeepSeek (coda coda-ds2) -> caricamento in piattaforma. Alla fine i due controlli.
# I casi nuovi usano la loro prima serie di sonde (P06, P07, P08): file senza suffisso, letture con etichetta «v2» (L05)
# e «l04nuove» (L04), le stesse che carica_ripresa.py legge per i casi di sempre.
cd ~/sabin-corpus; P=training/principi; LOG=training/ocr/rilettura/ciclo_casi_nuovi.log
pronto_punteggi() { # alias pezzi
  ssh -o ConnectTimeout=25 recas "for k in \$(seq 0 \$(($2-1))); do grep -q '^fine' ~/trace/$1_punteggi_\$k.out 2>/dev/null || exit 1; done" 2>/dev/null
}
fase() { echo "$(date +%H:%M) $*" | tee -a $LOG; }
for spec in klimaseniorinnen:kls:4 cig-parere-clima:icj:2 idh-oc-32-25:iac:2; do
  IFS=: read caso alias pezzi <<< "$spec"
  until pronto_punteggi $alias $pezzi; do sleep 120; done
  fase "$caso: punteggi pronti"
  for k in $(seq 0 $((pezzi-1))); do
    until scp -q recas:trace/training/principi/${alias}_punteggi_$k.jsonl $P/${caso}_punteggi_$k.jsonl; do sleep 30; done
  done
  .venv/bin/python - $caso <<'E'
import sys, pathlib, shutil
sys.path.insert(0, 'tools')
import leggi_ripresa as LR
caso = sys.argv[1]; P = pathlib.Path('training/principi')
LR.prepara(caso)
for suf in ('v2', 'l04nuove'):
    shutil.copy(P/f'{caso}_ripresa_righe.jsonl', P/f'{caso}_ripresa_righe_{suf}.jsonl')
# carica_ripresa legge sempre il file base della lettura: per un caso nuovo e' vuoto, le letture stanno in v2 e l04nuove
(P/f'{caso}_ripresa_deepseek.jsonl').touch()
E
  until scp -q $P/${caso}_ripresa_righe_v2.jsonl $P/${caso}_ripresa_righe_l04nuove.jsonl recas:trace/training/principi/; do sleep 30; done
  ssh recas "cat > ~/trace/chat/coda-ds2/${alias}_letture.sh" <<E
# $caso: principi (L04) e seguito (L05) con le sonde distintive, finestra intera
H=/lustrehome/climpact/trace; C=\$H/chat; cd \$H
A="--base-url http://127.0.0.1:8000/v1 --chiave-file \$C/chiave --modello deepseek-v4-flash --paralleli 32"
\$H/venv/bin/python -u tools/leggi_ripresa.py leggi --caso $caso --etichetta v2 --letture 2 \$A > \$C/log/${alias}_L05.log 2>&1 &
\$H/venv/bin/python -u tools/leggi_l04.py leggi --caso $caso --etichetta l04nuove --letture 2 \$A > \$C/log/${alias}_L04.log 2>&1 &
wait; echo FINITO > \$C/log/${alias}_letture_fine.txt
E
  fase "$caso: letture in coda"
done
for spec in klimaseniorinnen:kls cig-parere-clima:icj idh-oc-32-25:iac; do
  IFS=: read caso alias <<< "$spec"
  until ssh -o ConnectTimeout=25 recas "test -s ~/trace/chat/log/${alias}_letture_fine.txt" 2>/dev/null; do sleep 120; done
  for s in v2 l04nuove; do until scp -q recas:trace/training/principi/${caso}_ripresa_deepseek_$s.jsonl $P/; do sleep 30; done; done
  for i in 1 2 3 4; do .venv/bin/python tools/carica_ripresa.py --caso $caso --principi-da-l04 --scrivi > /tmp/ciclo_$alias.txt 2>&1 && break; sleep 30; done
  fase "$caso: caricato $(grep -E '^scritte' /tmp/ciclo_$alias.txt) $(grep -E 'con principio|con seguito' /tmp/ciclo_$alias.txt | tr -d '\n ')"
done
for i in 1 2 3; do .venv/bin/python tools/controllo_completezza.py --scrivi > /tmp/ciclo_controllo.txt 2>&1 && break; sleep 30; done
.venv/bin/python tools/controllo_finestra.py > /tmp/ciclo_finestra.txt 2>&1
fase "controlli fatti"; cat /tmp/ciclo_controllo.txt /tmp/ciclo_finestra.txt | tee -a $LOG
echo "CICLO CASI NUOVI FINITO"
