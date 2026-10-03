#!/bin/bash
# CICLO DELLE CINQUE LETTURE (02-03/10/2026, col si' del PI: «procedi»). Rilegge con DeepSeek TUTTE le righe col nome
# NON giudicate (comprese le 793 di S05): cinque letture del tipo (tenute quelle gia' fatte con la stessa domanda) e
# cinque letture L05 da capo sulle pagine attorno scelte con R10; poi carica le proposte con R11 (voto di maggioranza).
# Misure: training/misure/GIRI-E-DOMANDA.md (5 letture) e PERDITE-PAGINE-ATTORNO.md (R10). Regole: tools/maggioranza.py.
# Da launchd (tools/launchd/spenti/it.climpact.cinque-letture.plist), cosi' sopravvive alla sessione e ai riavvii:
# ogni passo finito lascia un segno in training/cinque/passi/ e non si rifa'; le letture riprendono da stato.json.
#
#   1. aspetta che il ciclo S05 scriva FINITO (prima non si scrive niente: le righe S05 si stanno caricando);
#   2. elenco delle righe non giudicate e fotografia delle proposte di oggi;
#   3. pagine attorno R10 e semi del tipo;
#   4. letture su ReCaS a blocchi di ~50 minuti nelle code di DeepSeek (tools/cinque_letture.py letture);
#   5. prova a secco di R11, RAPPORTO.md, conti a confronto, poi --scrivi;
#   6. controllo di completezza e della finestra;
#   7. dati della mappa rigenerati e caricati;
#   8. archivio delle letture.
# ALLA FINE, e anche se si ferma per un errore, il plist esce da ~/Library/LaunchAgents (in tools/launchd/spenti/).
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd ~/sabin-corpus || exit 1
C=training/cinque; LOG=$C/ciclo.log; PASSI=$C/passi
ETICHETTA=it.climpact.cinque-letture; PLIST=$HOME/Library/LaunchAgents/$ETICHETTA.plist
CASI="urgenda neubauer future-generations klimaseniorinnen cig-parere-clima idh-oc-32-25"
PY=.venv/bin/python
mkdir -p $C $PASSI
serie() { case $1 in neubauer|future-generations) echo P05;; cig-parere-clima) echo P09;; *) echo "";; esac; }

fase() { echo "$(date '+%d/%m %H:%M') $*" >> $LOG; $PY tools/giornale.py evento --nome ciclo_cinque_letture --testo "$*" 2>/dev/null; }
fine() { # SEMPRE, anche dopo un errore: il plist esce da LaunchAgents, poi launchd dimentica il lavoro
  if [ -f "$PLIST" ]; then mkdir -p tools/launchd/spenti; mv "$PLIST" "tools/launchd/spenti/$ETICHETTA.plist.fatto-$(date +%Y-%m-%d_%H%M)"; fi
  echo "$(date '+%d/%m %H:%M') plist tolto da LaunchAgents" >> $LOG
  $PY tools/giornale.py invia >/dev/null 2>&1
  launchctl bootout gui/$(id -u)/$ETICHETTA 2>/dev/null
}
trap fine EXIT
ferma() { fase "FERMO: $*"; exit 1; }
fatto() { test -f $PASSI/$1; }
segna() { date '+%d/%m %H:%M' > $PASSI/$1; }
# un passo con tentativi contati: riprova N volte, aspettando, poi si ferma
prova() { local n=$1 attesa=$2; shift 2; local i
  for i in $(seq 1 $n); do "$@" && return 0; fase "tentativo $i di $n fallito: $*"; [ $i -lt $n ] && sleep $attesa; done
  return 1; }
fase "inizio (pid $$)"

# ── 1. aspetta S05 ────────────────────────────────────────────────────────────────────────────────────────────────
if ! fatto s05; then
  until grep -q " FINITO" training/s05/ciclo_s05.log; do
    grep -q "FERMO" training/s05/ciclo_s05.log && ferma "il ciclo S05 si e' fermato (FERMO nel suo log): niente si scrive"
    sleep 300
  done
  segna s05; fase "S05 FINITO: si comincia"
fi

# ── 2. righe non giudicate, fotografia delle proposte di oggi ─────────────────────────────────────────────────────
if ! fatto righe; then prova 3 120 $PY tools/cinque_letture.py righe >> $LOG 2>&1 || ferma "elenco delle righe"; segna righe; fi

# ── 3. pagine attorno R10 e semi del tipo ─────────────────────────────────────────────────────────────────────────
if ! fatto prepara; then prova 2 60 $PY tools/cinque_letture.py prepara >> $LOG 2>&1 || ferma "pagine attorno R10 e semi"; segna prepara; fi

# ── 4. le letture su ReCaS (riprende da training/cinque/stato.json) ───────────────────────────────────────────────
if ! fatto letture; then
  prova 6 600 $PY tools/cinque_letture.py letture >> $LOG 2>&1 || ferma "letture (6 tentativi)"
  segna letture; fase "letture finite"
fi

# ── 5. R11: prova a secco, rapporto, conti, scrittura ─────────────────────────────────────────────────────────────
conta() { $PY -c "import json,sys; t=open(sys.argv[1]).read(); i=t.find('{'); d=json.JSONDecoder().raw_decode(t[i:])[0]; print(d.get('da scrivere',0))" "$1"; }
if ! fatto secco; then
  for c in $CASI; do s=$(serie $c)
    prova 3 60 $PY tools/carica_lessicali.py --caso $c --etichetta cinque --composizione R11 --salva $C/secco_tipo_$c.json > $C/secco_tipo_$c.txt 2>&1 || ferma "prova a secco del tipo $c"
    prova 3 60 $PY tools/carica_ripresa.py --caso $c --composizione R11 --etichetta ${s}cinque --etichetta-tipo cinque --salva $C/secco_ripresa_$c.json > $C/secco_ripresa_$c.txt 2>&1 || ferma "prova a secco della ripresa $c"
    n=$(wc -l < $C/righe_$c.txt | tr -d ' '); t=$(conta $C/secco_tipo_$c.txt); p=$(conta $C/secco_ripresa_$c.txt)
    fase "prova a secco $c: righe non giudicate $n, tipo da scrivere $t, ripresa da scrivere $p"
    # meno del 95% delle righe con una proposta nuova vuol dire letture mancanti: non si carica
    [ $((t * 100)) -ge $((n * 95)) ] && [ $((p * 100)) -ge $((n * 95)) ] || ferma "$c: proposte nuove troppo poche ($t e $p su $n)"
  done
  prova 3 60 $PY tools/cinque_letture.py rapporto >> $LOG 2>&1 || ferma "rapporto"
  segna secco
fi
if ! fatto scrittura; then
  for c in $CASI; do s=$(serie $c)
    if [ ! -f $PASSI/tipo_$c ]; then
      prova 4 30 $PY tools/carica_lessicali.py --caso $c --etichetta cinque --composizione R11 --scrivi > $C/scrivi_tipo_$c.txt 2>&1 || ferma "scrittura del tipo $c"
      segna tipo_$c
    fi
    if [ ! -f $PASSI/ripresa_$c ]; then
      prova 4 30 $PY tools/carica_ripresa.py --caso $c --composizione R11 --etichetta ${s}cinque --etichetta-tipo cinque --scrivi > $C/scrivi_ripresa_$c.txt 2>&1 || ferma "scrittura della ripresa $c"
      segna ripresa_$c
    fi
    a=$(conta $C/secco_tipo_$c.txt); b=$(conta $C/scrivi_tipo_$c.txt); x=$(conta $C/secco_ripresa_$c.txt); y=$(conta $C/scrivi_ripresa_$c.txt)
    fase "$c caricato con R11: tipo $b (a secco $a), ripresa $y (a secco $x); $(grep -E '^scritte' $C/scrivi_ripresa_$c.txt)"
    # la differenza sono le righe giudicate nel frattempo: piu' del 2% e' un'anomalia da guardare (il caricamento resta)
    [ $(( (a - b) * 100 )) -le $(( a * 2 )) ] && [ $(( (x - y) * 100 )) -le $(( x * 2 )) ] || fase "ATTENZIONE $c: conti diversi dalla prova a secco oltre il 2%"
  done
  segna scrittura
fi

# ── 6. i controlli ────────────────────────────────────────────────────────────────────────────────────────────────
if ! fatto controlli; then
  prova 3 60 $PY tools/controllo_completezza.py --scrivi > $C/controllo_completezza.txt 2>&1 || fase "ATTENZIONE: controllo di completezza fallito"
  $PY tools/controllo_finestra.py > $C/controllo_finestra.txt 2>&1
  cat $C/controllo_completezza.txt $C/controllo_finestra.txt >> $LOG
  segna controlli
fi

# ── 7. la mappa ───────────────────────────────────────────────────────────────────────────────────────────────────
if ! fatto mappa; then
  mappa() { $PY tools/aggiorna_dati_mappa.py --scrivi && (cd pubblicazione/mappa && ../../.venv/bin/python costellazione/prepara.py && ../../.venv/bin/python globo/prepara.py) && sh tools/mappa/carica-mappa-dati.sh; }
  prova 3 300 mappa >> $LOG 2>&1 && segna mappa || fase "ATTENZIONE: mappa non rigenerata"
fi

# ── 8. l'archivio delle letture ───────────────────────────────────────────────────────────────────────────────────
if ! fatto archivio; then
  prova 3 300 $PY tools/carica_archivio.py --scrivi >> $LOG 2>&1 && segna archivio || fase "ATTENZIONE: archivio non caricato"
fi
fase FINITO
# (il trap `fine` toglie il plist da ~/Library/LaunchAgents e chiude il lavoro in launchd)
