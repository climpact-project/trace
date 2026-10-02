#!/bin/bash
# Riaddestramento notturno del riordinatore sul Mac (22-23 settembre 2026).
#
# DIECI LANCI. Cinque semi con le etichette di ieri — servono a ricostruire gli
# adattatori persi con lo spegnimento del pod — e cinque con le etichette
# corrette, cioe' con le 17 righe «riclassificata» la cui nota dice che la
# citazione sta ALTROVE nel documento rimesse a falso. Il confronto fra i due
# gruppi dice se quelle etichette peggioravano il modello o solo la sua misura.
#
# Gli adattatori restano su questo disco. E' la ragione per cui si rifa' qui.
cd /Users/giuseppenagieri/sabin-corpus || exit 1
P=.venv/bin/python3
for ET in vecchie corrette; do
  [ "$ET" = vecchie ] && FLAG="" || FLAG="_corrette"
  for S in 1 2 3 4 5; do
    printf '\n════════ etichette %s — seme %d — %s ════════\n' "$ET" "$S" "$(date +%H:%M)"
    $P -u tools/069_addestra_riordino.py --batch 2 --accumula 4 --epoche 3 \
       --seme "$S" --etichette "$FLAG" 2>&1 \
       | grep --line-buffered -vE "Loading weights|it/s\]|^[[:space:]]*$"
  done
done
printf '\n════════ FINITO %s ════════\n' "$(date +%H:%M)"
