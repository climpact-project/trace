#!/bin/bash
# IL GUARDIANO DI D04 (03/10/2026). Ogni 10 minuti da launchd (it.climpact.d04, RunAtLoad: anche dopo un riavvio).
# Lancia tools/ciclo_d04.sh SOLO quando il ciclo S06 ha finito tutto:
#   - l'ultima riga di esito del suo log (training/s06/ciclo_s06.log) e' «FINITO»;
#   - il suo plist non e' piu' in ~/Library/LaunchAgents: il ciclo lo sposta per ultimo, quindi ha chiuso davvero.
# Se l'ultimo esito di S06 e' «FERMO» (e S06 ha chiuso), D04 non parte e lo si scrive una volta; la coda torna libera
# per il confronto dei decisori (il segno training/s06/coda_occupata, reso immutabile il 03/10 perche' il confronto
# non passasse fra S06 e D04, si toglie), e si continua a guardare: se S06 viene ripreso e finisce, D04 parte.
# Il ciclo D04 sposta questo plist in tools/launchd/spenti/ quando finisce o si ferma.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd "$HOME/sabin-corpus" || exit 0
mkdir -p training/d04
L=training/d04/attesa.log
SL=training/s06/ciclo_s06.log
SP=$HOME/Library/LaunchAgents/it.climpact.s06.plist
LUCCHETTO=training/s06/coda_occupata

# gia' cominciato (riavvio a meta'): si riprende senza guardare S06
test -f training/d04/passi/inizio && exec /bin/bash tools/ciclo_d04.sh

test -f "$SP" && exit 0
ultimo=$(grep -E '^[0-9]{2}/[0-9]{2} [0-9]{2}:[0-9]{2} (FINITO$|FERMO)' "$SL" 2>/dev/null | tail -1)
case "$ultimo" in
  *FINITO) ;;
  *FERMO*)
    grep -qF "S06 fermo: ${ultimo}" $L 2>/dev/null || {
      echo "$(date '+%d/%m %H:%M') S06 fermo: ${ultimo} (D04 non parte)" >> $L
      if [ -e $LUCCHETTO ]; then
        chflags nouchg $LUCCHETTO; rm -f $LUCCHETTO
        echo "$(date '+%d/%m %H:%M') coda di nuovo libera per il confronto dei decisori" >> $L
      fi
      .venv/bin/python tools/giornale.py evento --nome attesa_d04 --testo "ciclo S06 fermo: D04 aspetta, coda libera per i decisori" 2>/dev/null; }
    exit 0;;
  *) exit 0;;
esac
echo "$(date '+%d/%m %H:%M') S06 finito e chiuso: parte il ciclo D04" >> $L
exec /bin/bash tools/ciclo_d04.sh
