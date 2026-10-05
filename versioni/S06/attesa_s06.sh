#!/bin/bash
# IL GUARDIANO DI S06 (03/10/2026). Ogni 10 minuti da launchd (it.climpact.s06, RunAtLoad: anche dopo un riavvio).
# Lancia tools/ciclo_s06.sh SOLO quando il ciclo delle cinque letture ha finito tutto, caricamento compreso:
#   - l'ultima riga di esito del suo log (training/cinque/ciclo.log) e' «FINITO» (non basta « FINITO» in mezzo: il
#     log contiene anche «S05 FINITO: si comincia»); se e' «FERMO», non parte niente e lo si scrive una volta;
#   - il passo di scrittura delle proposte e' segnato (training/cinque/passi/scrittura): il caricamento della sera e'
#     il passo 5 dello stesso ciclo (carica_lessicali/carica_ripresa --scrivi), dopo le letture;
#   - il suo plist non e' piu' in ~/Library/LaunchAgents: il ciclo lo sposta per ultimo, quindi ha chiuso davvero.
# Prima di allora non si mette niente nelle code di ReCaS e non si scrive niente. Il ciclo S06 sposta questo plist in
# tools/launchd/spenti/ quando finisce o si ferma; mentre aspetta la scelta del PI su T01 esce con 3 e il plist resta.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd "$HOME/sabin-corpus" || exit 0
mkdir -p training/s06
L=training/s06/attesa.log
CL=training/cinque/ciclo.log
CP=$HOME/Library/LaunchAgents/it.climpact.cinque-letture.plist

ultimo=$(grep -E '^[0-9]{2}/[0-9]{2} [0-9]{2}:[0-9]{2} (FINITO$|FERMO)' "$CL" 2>/dev/null | tail -1)
case "$ultimo" in
  *FERMO*)
    grep -q "cinque letture ferme" $L 2>/dev/null || {
      echo "$(date '+%d/%m %H:%M') cinque letture ferme («${ultimo}»): S06 non parte" >> $L
      .venv/bin/python tools/giornale.py evento --nome attesa_s06 --testo "ciclo delle cinque letture fermo: S06 aspetta" 2>/dev/null; }
    exit 0;;
  *FINITO) ;;
  *) exit 0;;
esac
test -f training/cinque/passi/scrittura || exit 0
test -f "$CP" && exit 0
echo "$(date '+%d/%m %H:%M') cinque letture finite e caricate: parte il ciclo S06" >> $L
exec /bin/bash tools/ciclo_s06.sh
