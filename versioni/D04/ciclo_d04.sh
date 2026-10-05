#!/bin/bash
# CICLO D04 (preparato il 03/10/2026 per la notte, dopo S06): le 13 righe dei documenti nuovi di D04 (46 Markdown:
# 26 PDF riscaricati e 20 atti non PDF) in piattaforma, con lo stesso trattamento delle altre righe (quello di S06).
# Lo lancia il guardiano tools/launchd/attesa_d04.sh (launchd, it.climpact.d04) quando il ciclo S06 ha scritto FINITO
# e ha chiuso; riparte anche dopo un riavvio del Mac: ogni passo finito lascia un segno in training/d04/passi/.
#
#   1. l'indice delle pagine: il vivo + le pagine di D04 (la copia di prima resta in pagine.prima-D04.jsonl.gz);
#   2. le righe in corpus_rows FUORI DALLE CODE (assegnato_a_in_attesa), codici dopo il piu' alto di oggi;
#   3. i PDF riscaricati di D04 sul server del corpus, accanto agli altri, e la prova dal servizio vero;
#   4. contesti dalla banca dati, righe nei file dei lettori, mappa dei paragrafi;
#   5. T01 nel modo recas-ferma (lo schema di S06: vLLM fermato e riacceso SEMPRE dalla trap) per il brano delle righe
#      e le pagine attorno senza punteggio, con la prova contro le H100;
#   6. il registro: la voce D04 in tools/registro_versioni.py (tools/registro_d04.py) e SOLO lei su trace_versioni;
#   7. pagine attorno R10, cinque letture del tipo e cinque L05 nelle code di DeepSeek (tools/letture_d04.py);
#   8. R11: prova a secco (solo righe di D04, controllato), rapporto, scrittura;
#   9. le righe complete tornano nelle code; controllo di completezza;
#  10. mappa, archivio delle letture, giornale.
# LA CODA PRIMA A D04. training/decisori/recas/guida.sh (il confronto dei decisori) conosce un solo segno,
# training/s06/coda_occupata: finche' il file esiste non mette blocchi. Il ciclo S06 lo toglie a letture finite con
# `rm -f`; perche' il confronto non passi nel buco fra S06 e D04, il 03/10 il file e' stato reso immutabile
# (chflags uchg: `rm -f` di S06 non riesce, e S06 va avanti lo stesso). Questo ciclo lo riscrive col suo testo
# all'inizio e lo toglie (chflags nouchg, rm) a letture finite, o se si ferma.
# Scritture in banca dati: solo le 13 righe di D04 (creazione, proposte, campo di attesa) e la voce D04 del registro;
# la mappa va su Storage, l'archivio e il giornale nelle loro collezioni.
# ALLA FINE (FINITO o FERMO) il plist esce da ~/Library/LaunchAgents (in tools/launchd/spenti/).
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd ~/sabin-corpus || exit 1
unset TRACE_SONDE
D=training/d04; LOG=$D/ciclo_d04.log; PASSI=$D/passi
ETICHETTA=it.climpact.d04; PLIST=$HOME/Library/LaunchAgents/$ETICHETTA.plist
LUCCHETTO=training/s06/coda_occupata
PY=.venv/bin/python
mkdir -p $D $PASSI
serie() { case $1 in neubauer|future-generations) echo P05;; cig-parere-clima) echo P09;; *) echo "";; esac; }

fase() { echo "$(date '+%d/%m %H:%M') $*" >> $LOG; $PY tools/giornale.py evento --nome ciclo_d04 --testo "$*" 2>/dev/null; }
prendi_coda() {
  [ -e $LUCCHETTO ] && chflags nouchg $LUCCHETTO
  printf '%s\n' "Le code di DeepSeek (coda-ds2, coda-ds3) sono prima per D04 ($(date '+%d/%m/%Y %H:%M')): T01 con vLLM" \
    "fermato e riacceso, poi le cinque letture delle 13 righe di D04. Finche' questo file esiste" \
    "training/decisori/recas/guida.sh non mette blocchi del confronto dei decisori. E' immutabile (chflags uchg): lo" \
    "toglie tools/ciclo_d04.sh a letture finite o se si ferma. A mano: chflags nouchg $LUCCHETTO && rm $LUCCHETTO" > $LUCCHETTO
  chflags uchg $LUCCHETTO; }
lascia_coda() { if [ -e $LUCCHETTO ]; then chflags nouchg $LUCCHETTO; rm -f $LUCCHETTO; fi; }
ESITO=""
fine() { # sempre: la coda torna libera se le letture non sono finite; a FINITO o FERMO il plist esce da LaunchAgents
  fatto letture || lascia_coda
  # interrotto da fuori (riavvio del Mac): il plist resta, il guardiano riparte dai passi segnati
  [ -n "$ESITO" ] || return
  if [ -f "$PLIST" ]; then mkdir -p tools/launchd/spenti; mv "$PLIST" "tools/launchd/spenti/$ETICHETTA.plist.fatto-$(date +%Y-%m-%d_%H%M)"; fi
  echo "$(date '+%d/%m %H:%M') plist tolto da LaunchAgents" >> $LOG
  $PY tools/giornale.py invia >/dev/null 2>&1
  launchctl bootout gui/$(id -u)/$ETICHETTA 2>/dev/null
}
trap fine EXIT
ferma() { ESITO=fermo; lascia_coda; fase "FERMO: $*"; exit 1; }
fatto() { test -f $PASSI/$1; }
segna() { date '+%d/%m %H:%M' > $PASSI/$1; }
prova() { local n=$1 attesa=$2; shift 2; local i
  for i in $(seq 1 $n); do "$@" && return 0; fase "tentativo $i di $n fallito: $*"; [ $i -lt $n ] && sleep $attesa; done
  return 1; }
r() { ssh -o ConnectTimeout=30 -o BatchMode=yes recas "$@"; }
manda() { until scp -q "$1" "recas:trace/$2"; do sleep 60; done; }
prendi() { until scp -q "recas:trace/$1" "$2"; do sleep 60; done; }

if ! fatto inizio; then segna inizio; fase "inizio (pid $$)"; fi
fatto letture || prendi_coda

# ── 1. l'indice delle pagine con le pagine di D04 ─────────────────────────────────────────────────────────────────
if ! fatto indice; then
  prova 2 60 $PY tools/recupero_d04.py indice --scrivi >> $LOG 2>&1 || ferma "indice delle pagine D04"
  segna indice; fase "indice delle pagine: il vivo ha le pagine di D04 (copia di prima in index/pagine/pagine.prima-D04.jsonl.gz)"
fi

# ── 2. le righe in banca dati, fuori dalle code ───────────────────────────────────────────────────────────────────
if ! fatto righe; then prova 2 60 $PY tools/recupero_d04.py righe >> $LOG 2>&1 || ferma "righe D04 (ricontrollo)"; segna righe; fi
CASI=$($PY -c "import sys; sys.path.insert(0, 'tools'); import recupero_d04 as R; print(' '.join(R.casi_d04()))")
[ -n "$CASI" ] || ferma "nessun caso con righe di D04 ($D/righe_d04.jsonl)"
if ! fatto scritte; then
  prova 3 60 $PY tools/recupero_d04.py scrivi --scrivi >> $LOG 2>&1 || ferma "scrittura delle righe D04"
  segna scritte; fase "righe D04 scritte in corpus_rows, fuori dalle code: $(wc -l < $D/righe_d04.jsonl | tr -d ' ') ($CASI)"
fi

# ── 3. i PDF sul server del corpus (non ferma il ciclo: le righe si aprono anche senza, dal sito della fonte) ───────
if ! fatto pdf; then
  if prova 3 300 $PY tools/recupero_d04.py pdf --scrivi >> $LOG 2>&1; then segna pdf; fase "PDF di D04 sul server del corpus, serviti"
  else fase "ATTENZIONE: PDF di D04 non caricati o non serviti ($D/pdf_d04.json)"; fi
fi

# ── 4. contesti, file dei lettori, mappa dei paragrafi ────────────────────────────────────────────────────────────
if ! fatto lettori; then
  prova 3 60 $PY tools/recupero_d04.py contesti >> $LOG 2>&1 || ferma "contesti dalla banca dati"
  prova 2 60 $PY tools/recupero_d04.py aggiungi >> $LOG 2>&1 || ferma "righe nei file dei lettori"
  for c in $CASI; do s=$(serie $c)
    $PY tools/principi_da_paragrafi.py --caso $c ${s:+--sonde $s} >> $LOG 2>&1 || ferma "mappa dei paragrafi $c"
  done
  segna lettori; fase "righe D04 nei file dei lettori, mappa dei paragrafi pronta"
fi

# ── 5. T01 nel modo recas-ferma ───────────────────────────────────────────────────────────────────────────────────
if ! fatto t01; then
  if ! fatto t01_in_coda; then
    prova 2 60 $PY tools/recupero_d04.py coppie >> $LOG 2>&1 || ferma "coppie T01"
    $PY tools/recupero_d04.py prepara-ferma >> $LOG 2>&1 || ferma "coppie per ReCaS"
    r 'mkdir -p ~/trace/training/d04 ~/trace/training/principi && rm -f ~/trace/training/d04/t01_ferma.fine ~/trace/training/principi/d04_punteggi_*.jsonl'
    manda training/principi/d04_coppie.jsonl training/principi/d04_coppie.jsonl
    cat > $D/t01_ferma.sh <<'Y'
# T01 PER LE RIGHE DI D04 (tools/ciclo_d04.sh): come lo script di S06 (tools/ciclo_s06.sh, recas-ferma) e come
# coda-ds2/fatti/punteggi_dentro.sh del 01/10. Si ferma vLLM, si calcolano i punteggi con ripresa_punteggi.py (un
# processo per GPU) e si riaccende vLLM IN OGNI CASO (trap): finche' questo script gira il lavoro non controlla se vLLM
# e' acceso, quindi le GPU restano nostre. Il segno di fine (training/d04/t01_ferma.fine) si scrive solo quando vLLM
# risponde di nuovo.
H=/lustrehome/climpact; C=$H/trace/chat; CH=$(cat $C/chiave); cd $H/trace
export HOME=$H HF_HOME=$H/trace/hf TMPDIR=$H/trace/tmp
F=training/d04/t01_ferma
riaccendi() {
  if ! pgrep -u climpact -f "vllm serve" > /dev/null; then
    echo "riaccendo vLLM $(date)"; nohup $C/vllm2.sh > $C/log/vllm2_d04.log 2>&1 &
  fi
  until curl -s -m 5 -H "Authorization: Bearer $CH" http://127.0.0.1:8000/v1/models | grep -q deepseek; do sleep 30; done
  echo "vLLM pronto $(date)"
  echo "fine $(cat $F.esito 2>/dev/null || echo 9) $(cat $F.pezzi 2>/dev/null || echo 0) $(date +%s)" > $F.fine.tmp && mv $F.fine.tmp $F.fine
}
trap riaccendi EXIT
mkdir -p training/d04; rm -f $F.esito $F.pezzi
echo "fermo vLLM $(date)"; pkill -u climpact -f "vllm serve"; sleep 60
nvidia-smi --query-gpu=index,memory.used --format=csv,noheader
GPU=(${CUDA_VISIBLE_DEVICES//,/ }); N=${#GPU[@]}; echo $N > $F.pezzi
pids=()
for k in $(seq 0 $((N - 1))); do
  CUDA_VISIBLE_DEVICES=${GPU[$k]} venv/bin/python -u tools/ripresa_punteggi.py punteggi --caso d04 --pezzo $k --pezzi $N > training/d04/t01_pezzo_$k.out 2>&1 &
  pids+=($!)
done
esito=0; for p in "${pids[@]}"; do wait $p || esito=1; done
echo $esito > $F.esito
echo "punteggi finiti $(date), esito $esito"
Y
    manda $D/t01_ferma.sh chat/coda-ds2/d04_t01.sh.tmp
    r 'mv ~/trace/chat/coda-ds2/d04_t01.sh.tmp ~/trace/chat/coda-ds2/d04_t01.sh'
    segna t01_in_coda; fase "T01 in coda (coda-ds2): vLLM si ferma per il calcolo e si riaccende"
  fi
  until r 'test -s ~/trace/training/d04/t01_ferma.fine' 2>/dev/null; do sleep 120; done
  FIN=$(r 'cat ~/trace/training/d04/t01_ferma.fine')
  fase "T01 su ReCaS finito e vLLM di nuovo acceso: $FIN"
  set -- $FIN
  [ "$2" = "0" ] || { r 'tail -3 ~/trace/training/d04/t01_pezzo_*.out' >> $LOG 2>&1; ferma "T01 su ReCaS: il calcolo non e' finito bene (training/d04/t01_pezzo_*.out su ReCaS)"; }
  NP=$3
  for k in $(seq 0 $((NP - 1))); do prendi training/principi/d04_punteggi_$k.jsonl $D/d04_punteggi_$k.jsonl; done
  $PY tools/recupero_d04.py raccogli-ferma --pezzi $NP >> $LOG 2>&1 || ferma "T01 su ReCaS: la prova contro le H100 non passa o i punteggi non tornano ($D/t01_prova_recas-ferma.json)"
  segna t01; fase "T01 fatto (recas-ferma)"
fi

# ── 6. il registro: la voce D04 ───────────────────────────────────────────────────────────────────────────────────
if ! fatto registro; then
  prova 2 60 $PY tools/registro_d04.py --scrivi >> $LOG 2>&1 || ferma "voce D04 in tools/registro_versioni.py"
  prova 3 60 $PY tools/registro_versioni.py --scrivi --solo D04 >> $LOG 2>&1 || ferma "registro D04"
  $PY -c "from google.cloud import firestore; import sys; sys.exit(0 if firestore.Client(project='climpact-drp').collection('trace_versioni').document('D04').get().exists else 1)" \
    || ferma "D04 non e' in trace_versioni"
  segna registro; fase "D04 nel registro (versioni/registro.json e trace_versioni/D04)"
fi

# ── 7. pagine attorno R10 e cinque letture nelle code di DeepSeek ─────────────────────────────────────────────────
if ! fatto righe_lettura; then prova 3 120 $PY tools/letture_d04.py righe >> $LOG 2>&1 || ferma "righe da leggere"; segna righe_lettura; fi
if ! fatto prepara; then prova 2 60 $PY tools/letture_d04.py prepara >> $LOG 2>&1 || ferma "pagine attorno R10"; segna prepara; fi
if ! fatto letture; then
  prova 6 600 $PY tools/letture_d04.py letture >> $LOG 2>&1 || ferma "letture (6 tentativi)"
  segna letture; lascia_coda; fase "letture finite: la coda torna libera per il confronto dei decisori"
fi

# ── 8. R11: prova a secco (solo righe di D04), rapporto, scrittura ────────────────────────────────────────────────
conta() { $PY -c "import json,sys; t=open(sys.argv[1]).read(); i=t.find('{'); d=json.JSONDecoder().raw_decode(t[i:])[0]; print(d.get('da scrivere',0))" "$1"; }
if ! fatto secco; then
  for c in $CASI; do s=$(serie $c)
    prova 3 60 $PY tools/carica_lessicali.py --caso $c --etichetta d04 --composizione R11 --salva $D/secco_tipo_$c.json > $D/secco_tipo_$c.txt 2>&1 || ferma "prova a secco del tipo $c"
    prova 3 60 $PY tools/carica_ripresa.py --caso $c --composizione R11 --etichetta ${s}d04 --etichetta-tipo d04 --salva $D/secco_ripresa_$c.json > $D/secco_ripresa_$c.txt 2>&1 || ferma "prova a secco della ripresa $c"
    # solo righe di D04: le altre righe non si toccano
    $PY tools/recupero_d04.py verifica --file $D/secco_tipo_$c.json >> $LOG 2>&1 || ferma "$c: la prova a secco del tipo tocca righe non di D04"
    $PY tools/recupero_d04.py verifica --file $D/secco_ripresa_$c.json >> $LOG 2>&1 || ferma "$c: la prova a secco della ripresa tocca righe non di D04"
    n=$(grep -c . $D/righe_$c.txt); t=$(conta $D/secco_tipo_$c.txt); p=$(conta $D/secco_ripresa_$c.txt)
    fase "prova a secco $c: righe D04 non giudicate $n, tipo da scrivere $t, ripresa da scrivere $p"
    [ $((t * 100)) -ge $((n * 95)) ] && [ $((p * 100)) -ge $((n * 95)) ] || ferma "$c: proposte nuove troppo poche ($t e $p su $n)"
  done
  prova 3 60 $PY tools/letture_d04.py rapporto >> $LOG 2>&1 || ferma "rapporto"
  segna secco
fi
if ! fatto scrittura; then
  for c in $CASI; do s=$(serie $c)
    if [ ! -f $PASSI/tipo_$c ]; then
      prova 4 30 $PY tools/carica_lessicali.py --caso $c --etichetta d04 --composizione R11 --scrivi > $D/scrivi_tipo_$c.txt 2>&1 || ferma "scrittura del tipo $c"
      segna tipo_$c
    fi
    if [ ! -f $PASSI/ripresa_$c ]; then
      prova 4 30 $PY tools/carica_ripresa.py --caso $c --composizione R11 --etichetta ${s}d04 --etichetta-tipo d04 --scrivi > $D/scrivi_ripresa_$c.txt 2>&1 || ferma "scrittura della ripresa $c"
      segna ripresa_$c
    fi
    fase "$c caricato con R11: tipo $(conta $D/scrivi_tipo_$c.txt), ripresa $(conta $D/scrivi_ripresa_$c.txt)"
  done
  segna scrittura
fi

# ── 9. nelle code le righe complete; controllo di completezza ─────────────────────────────────────────────────────
if ! fatto rimesse; then
  prova 3 60 $PY tools/recupero_d04.py rimetti --scrivi >> $LOG 2>&1 || ferma "righe D04 nelle code"
  segna rimesse; fase "righe D04 complete nelle code; restano fuori: $(grep -c . $D/restano_fuori_dalle_code.txt)"
fi
if ! fatto controlli; then
  prova 3 60 $PY tools/controllo_completezza.py > $D/controllo_completezza.txt 2>&1 || fase "ATTENZIONE: controllo di completezza fallito"
  cat $D/controllo_completezza.txt >> $LOG
  n=$(grep -E 'righe da giudicare senza proposte' $D/controllo_completezza.txt | awk -F': ' '{s += $2+0} END {print s+0}')
  # le righe D04 fra quelle senza proposte (i file mancanti_<caso>_<ora>.txt scritti da questo controllo)
  m=$($PY - <<'X'
import json, pathlib
d = pathlib.Path('training/d04')
ids = {json.loads(l)['id'] for l in open(d/'righe_d04.jsonl', encoding='utf-8') if l.strip()}
dopo = (d/'passi'/'rimesse').stat().st_mtime
mancanti = set()
for f in pathlib.Path('training').glob('mancanti_*.txt'):
    if f.stat().st_mtime >= dopo:
        mancanti |= set(f.read_text(encoding='utf-8').split())
print(len(ids & mancanti))
X
)
  fase "controllo di completezza: righe da giudicare senza proposte $n in tutto, di D04 ${m:-0} (righe D04 fuori dalle code: $(grep -c . $D/restano_fuori_dalle_code.txt))"
  [ "$n" = "0" ] || fase "ATTENZIONE: il controllo di completezza non e' a zero ($n righe senza proposte; di D04 ${m:-0})"
  segna controlli
fi

# ── 10. mappa, archivio, giornale ─────────────────────────────────────────────────────────────────────────────────
if ! fatto mappa; then
  # dal 03/10/2026 col lucchetto condiviso col ciclo it.climpact.trace-vivo, e coi PDF del visore (tools/mappa/rigenera_mappa.sh)
  mappa() { sh tools/mappa/rigenera_mappa.sh; }
  prova 3 300 mappa >> $LOG 2>&1 && segna mappa || fase "ATTENZIONE: mappa non rigenerata"
fi
if ! fatto archivio; then
  prova 3 300 $PY tools/carica_archivio.py --scrivi >> $LOG 2>&1 && segna archivio || fase "ATTENZIONE: archivio non caricato"
fi
$PY tools/giornale.py raccogli >> $LOG 2>&1
ESITO=finito; fase FINITO
# (il trap `fine` toglie il plist da ~/Library/LaunchAgents e chiude il lavoro in launchd)
