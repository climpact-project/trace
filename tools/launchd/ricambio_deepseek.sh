#!/bin/bash
# 02/10/2026: sottomette su ReCaS il DeepSeek di ricambio (chat5.sub -> avvio4.sh), una volta sola, poi si toglie da launchd.
# Perche' dal Mac: ReCaS toglie i lavori in hold da piu' di 20 minuti, quindi non si puo' sottomettere prima e aspettare.
LOG=~/sabin-corpus/training/ocr/rilettura/ricambio_deepseek.log
echo "$(date) inizio" >> $LOG
for i in $(seq 1 20); do
  if ssh -o ConnectTimeout=30 -o BatchMode=yes recas 'cd ~/trace/chat && condor_submit chat5.sub' >> $LOG 2>&1; then
    echo "$(date) sottomesso" >> $LOG
    launchctl bootout gui/$(id -u)/it.climpact.ricambio-deepseek 2>/dev/null
    exit 0
  fi
  sleep 120
done
echo "$(date) NON sottomesso dopo 20 tentativi" >> $LOG
