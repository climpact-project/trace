#!/bin/bash
# CICLO S06 (03/10/2026, col si' del PI: «ok va bene»): le copie di S05 in un atto di un'altra causa tornano righe, con
# lo stesso trattamento delle altre righe di oggi. Lo lancia il guardiano tools/launchd/attesa_s06.sh (launchd,
# it.climpact.s06) quando il ciclo delle cinque letture ha scritto FINITO e ha chiuso; da li' riparte anche dopo un
# riavvio del Mac: ogni passo finito lascia un segno in training/s06/passi/ e non si rifa'.
#
#   1. T01: i punteggi del brano delle righe e delle pagine attorno ancora senza punteggio, nel modo scritto in
#      training/s06/t01_modo.txt (recas-ferma, la scelta del 03/10: lo schema di coda-ds2/fatti/punteggi_dentro.sh del
#      01/10, vLLM fermato e riacceso sempre; oppure mac | recas-accanto, vedi tools/punteggi_t01_s06.py); senza
#      scelta il ciclo aspetta qui (esce con 3 e il guardiano lo rilancia dopo dieci minuti): niente e' ancora scritto;
#   2. registro: la voce S06 in versioni/registro.json e SOLO lei su trace_versioni;
#   3. le righe in corpus_rows, FUORI DALLE CODE (assegnato_a_in_attesa), poi i loro contesti dalla banca dati, nei
#      file dei lettori, mappa dei paragrafi;
#   4. pagine attorno R10, cinque letture del tipo e cinque L05 nelle code di DeepSeek (tools/letture_s06.py);
#   5. R11: prova a secco (solo righe di S06, controllato), rapporto, scrittura;
#   6. le righe complete tornano nelle code; controllo di completezza;
#   7. mappa, archivio delle letture, giornale.
# LA CODA PRIMA A S06: finche' esiste training/s06/coda_occupata il confronto dei decisori
# (training/decisori/recas/guida.sh) non mette blocchi nelle code di DeepSeek; il ciclo lo toglie a letture finite, o
# se si ferma.
# Scritture in banca dati: solo le righe di S06 (creazione, proposte, campo di attesa) e la voce S06 del registro; la
# mappa va su Storage, l'archivio e il giornale nelle loro collezioni.
# ALLA FINE (FINITO o FERMO) il plist esce da ~/Library/LaunchAgents (in tools/launchd/spenti/): un plist dimenticato
# li' riparte a ogni riavvio del Mac.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd ~/sabin-corpus || exit 1
unset TRACE_SONDE
S=training/s06; LOG=$S/ciclo_s06.log; PASSI=$S/passi
ETICHETTA=it.climpact.s06; PLIST=$HOME/Library/LaunchAgents/$ETICHETTA.plist
PY=.venv/bin/python
mkdir -p $S $PASSI
serie() { case $1 in neubauer|future-generations) echo P05;; cig-parere-clima) echo P09;; *) echo "";; esac; }

fase() { echo "$(date '+%d/%m %H:%M') $*" >> $LOG; $PY tools/giornale.py evento --nome ciclo_s06 --testo "$*" 2>/dev/null; }
ESITO=""
fine() { # a FINITO o FERMO il plist esce da LaunchAgents; in attesa della scelta su T01 resta (il guardiano rilancia)
  [ "$ESITO" = "attesa" ] && return
  if [ -f "$PLIST" ]; then mkdir -p tools/launchd/spenti; mv "$PLIST" "tools/launchd/spenti/$ETICHETTA.plist.fatto-$(date +%Y-%m-%d_%H%M)"; fi
  echo "$(date '+%d/%m %H:%M') plist tolto da LaunchAgents" >> $LOG
  $PY tools/giornale.py invia >/dev/null 2>&1
  launchctl bootout gui/$(id -u)/$ETICHETTA 2>/dev/null
}
trap fine EXIT
ferma() { ESITO=fermo; rm -f $S/coda_occupata; fase "FERMO: $*"; exit 1; }
fatto() { test -f $PASSI/$1; }
segna() { date '+%d/%m %H:%M' > $PASSI/$1; }
prova() { local n=$1 attesa=$2; shift 2; local i
  for i in $(seq 1 $n); do "$@" && return 0; fase "tentativo $i di $n fallito: $*"; [ $i -lt $n ] && sleep $attesa; done
  return 1; }
r() { ssh -o ConnectTimeout=30 -o BatchMode=yes recas "$@"; }
manda() { until scp -q "$1" "recas:trace/$2"; do sleep 60; done; }
prendi() { until scp -q "recas:trace/$1" "$2"; do sleep 60; done; }
CASI=$($PY -c "import sys; sys.path.insert(0, 'tools'); import recupero_s06 as R; print(' '.join(R.casi_s06()))")
[ -n "$CASI" ] || ferma "nessun caso con righe di S06 ($S/righe_s06.jsonl)"
fatto inizio || { segna inizio; fase "inizio (pid $$): casi $CASI"; }

# ── 1. T01 (vLLM fermato e riacceso, o gli altri modi) ────────────────────────────────────────────────────────────
if ! fatto t01; then
  MODO=$(cat $S/t01_modo.txt 2>/dev/null | tr -d ' \n')
  if [ -z "$MODO" ]; then
    grep -q "in attesa della scelta su T01" $LOG 2>/dev/null || fase "in attesa della scelta su T01: scrivere mac o recas-accanto in $S/t01_modo.txt (niente e' ancora scritto)"
    ESITO=attesa; exit 3
  fi
  prova 2 60 $PY tools/recupero_s06.py contesti --dai-documenti >> $LOG 2>&1 || ferma "contesti per T01"
  prova 2 60 $PY tools/recupero_s06.py coppie >> $LOG 2>&1 || ferma "coppie T01"
  case $MODO in
    mac)
      # serve memoria: almeno 12 GB liberi o recuperabili, altrimenti si aspetta il giro dopo del guardiano
      LIBERA=$(memory_pressure 2>/dev/null | awk -F': ' '/free percentage/ {print $2+0}')
      if [ "${LIBERA:-0}" -lt 50 ]; then
        tail -1 $LOG | grep -q "T01 sul Mac: memoria" || fase "T01 sul Mac: memoria libera ${LIBERA}%, si aspetta (si riprova ogni 10 minuti)"
        ESITO=attesa; exit 3
      fi
      prova 1 0 $PY tools/punteggi_t01_s06.py prova --dispositivo mps >> $LOG 2>&1 || ferma "T01 sul Mac: la prova contro le H100 non passa ($S/t01_prova_mps.json)"
      prova 2 300 $PY tools/punteggi_t01_s06.py punteggi --dispositivo mps >> $LOG 2>&1 || ferma "T01 sul Mac"
      ;;
    recas-accanto)
      # le coppie di S06 e 300 coppie di S05 gia' calcolate sulle H100 (la prova), in un file solo, in una coda
      $PY - <<'X' >> $LOG 2>&1 || ferma "coppie per ReCaS"
import json, sys
sys.path.insert(0, 'tools')
import punteggi_t01_s06 as T
coppie, _ = T.campione_prova(T.PROVA_N)
with open('training/s06/s06_coppie_recas.jsonl', 'w', encoding='utf-8') as f:
    for l in open('training/s06/s06_coppie.jsonl', encoding='utf-8'):
        f.write(l)
    for q, d in coppie:
        f.write(json.dumps({'caso': 'prova', 'q': q, 'd': d}, ensure_ascii=False) + '\n')
X
      if ! test -f $PASSI/t01_in_coda; then
        r 'mkdir -p ~/trace/training/s06 && rm -f ~/trace/training/s06/t01_recas.fine'
        manda $S/s06_coppie_recas.jsonl training/s06/s06_coppie_recas.jsonl
        manda tools/punteggi_t01_s06.py tools/punteggi_t01_s06.py
        { echo '# T01 per le righe di S06 ACCANTO a vLLM (tools/ciclo_s06.sh, 03/10/2026): vLLM NON si ferma.'
          echo 'H=/lustrehome/climpact/trace; cd $H; export HOME=/lustrehome/climpact HF_HOME=$H/hf TMPDIR=$H/tmp'
          echo 'B=$H/hf/hub/models--Qwen--Qwen3-Reranker-4B/snapshots/22e683669bc0f0bd69640a1354a6d0aebcfeede5'
          echo 'venv/bin/python -u tools/punteggi_t01_s06.py punteggi --dispositivo cuda-accanto --base $B --coppie training/s06/s06_coppie_recas.jsonl --memoria training/s06/t01_memoria_recas.jsonl --solo-memoria > training/s06/t01_recas.out 2>&1'
          echo 'echo "fine $? $(date +%s)" > training/s06/t01_recas.fine.tmp && mv training/s06/t01_recas.fine.tmp training/s06/t01_recas.fine'
        } > $S/t01_recas.sh
        manda $S/t01_recas.sh chat/coda-ds2/s06_t01.sh.tmp
        r 'mv ~/trace/chat/coda-ds2/s06_t01.sh.tmp ~/trace/chat/coda-ds2/s06_t01.sh'
        segna t01_in_coda; fase "T01 accanto a vLLM in coda (coda-ds2)"
      fi
      until r 'test -s ~/trace/training/s06/t01_recas.fine' 2>/dev/null; do sleep 120; done
      r 'cat ~/trace/training/s06/t01_recas.fine' | grep -q '^fine 0 ' || { r 'tail -5 ~/trace/training/s06/t01_recas.out' >> $LOG; ferma "T01 accanto a vLLM: il calcolo su ReCaS non e' finito bene (training/s06/t01_recas.out su ReCaS)"; }
      prendi training/s06/t01_memoria_recas.jsonl $S/t01_memoria_recas.jsonl
      $PY - <<'X' >> $LOG 2>&1 || ferma "T01 accanto a vLLM: la prova contro le H100 non passa ($S/t01_prova_cuda-accanto.json)"
import json, pathlib, sys
sys.path.insert(0, 'tools')
import punteggi_t01_s06 as T
m = T.leggi_memoria(pathlib.Path('training/s06/t01_memoria_recas.jsonl'))
coppie, ref = T.campione_prova(T.PROVA_N)
e = T.esito_prova([m[T.chiave(q, d)] for q, d in coppie], ref)
e.update({'dispositivo': 'cuda-accanto', 'riferimento': 'training/principi/s05_coppie.jsonl con s05_punteggi_0.jsonl (H100, ciclo S05 del 02/10)'})
json.dump(e, open('training/s06/t01_prova_cuda-accanto.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('prova T01 accanto a vLLM', e)
righe = [json.loads(l) for l in open('training/s06/s06_coppie.jsonl', encoding='utf-8')]
T.scrivi_punteggi(righe, {T.chiave(x['q'], x['d']): m[T.chiave(x['q'], x['d'])] for x in righe})
sys.exit(0 if e['passa'] else 1)
X
      ;;
    recas-ferma)
      # lo schema del 01/10 (coda-ds2/fatti/punteggi_dentro.sh): vLLM fermato, ripresa_punteggi.py un processo per
      # GPU, vLLM riacceso SEMPRE dalla trap, che scrive il segno di fine solo quando vLLM risponde di nuovo
      if ! test -f $PASSI/t01_in_coda; then
        $PY tools/punteggi_t01_s06.py prepara-ferma >> $LOG 2>&1 || ferma "coppie per ReCaS"
        r 'mkdir -p ~/trace/training/s06 ~/trace/training/principi && rm -f ~/trace/training/s06/t01_ferma.fine ~/trace/training/principi/s06_punteggi_*.jsonl'
        manda training/principi/s06_coppie.jsonl training/principi/s06_coppie.jsonl
        cat > $S/t01_ferma.sh <<'Y'
# T01 PER LE RIGHE DI S06 (tools/ciclo_s06.sh, 03/10/2026): come coda-ds2/fatti/punteggi_dentro.sh del 01/10. Si ferma
# vLLM, si calcolano i punteggi con ripresa_punteggi.py (un processo per GPU) e si riaccende vLLM IN OGNI CASO (trap):
# finche' questo script gira il lavoro non controlla se vLLM e' acceso, quindi le GPU restano nostre. Il segno di fine
# (training/s06/t01_ferma.fine) si scrive solo quando vLLM risponde di nuovo.
H=/lustrehome/climpact; C=$H/trace/chat; CH=$(cat $C/chiave); cd $H/trace
export HOME=$H HF_HOME=$H/trace/hf TMPDIR=$H/trace/tmp
F=training/s06/t01_ferma
riaccendi() {
  if ! pgrep -u climpact -f "vllm serve" > /dev/null; then
    echo "riaccendo vLLM $(date)"; nohup $C/vllm2.sh > $C/log/vllm2_s06.log 2>&1 &
  fi
  until curl -s -m 5 -H "Authorization: Bearer $CH" http://127.0.0.1:8000/v1/models | grep -q deepseek; do sleep 30; done
  echo "vLLM pronto $(date)"
  echo "fine $(cat $F.esito 2>/dev/null || echo 9) $(cat $F.pezzi 2>/dev/null || echo 0) $(date +%s)" > $F.fine.tmp && mv $F.fine.tmp $F.fine
}
trap riaccendi EXIT
mkdir -p training/s06; rm -f $F.esito $F.pezzi
echo "fermo vLLM $(date)"; pkill -u climpact -f "vllm serve"; sleep 60
nvidia-smi --query-gpu=index,memory.used --format=csv,noheader
GPU=(${CUDA_VISIBLE_DEVICES//,/ }); N=${#GPU[@]}; echo $N > $F.pezzi
pids=()
for k in $(seq 0 $((N - 1))); do
  CUDA_VISIBLE_DEVICES=${GPU[$k]} venv/bin/python -u tools/ripresa_punteggi.py punteggi --caso s06 --pezzo $k --pezzi $N > training/s06/t01_pezzo_$k.out 2>&1 &
  pids+=($!)
done
esito=0; for p in "${pids[@]}"; do wait $p || esito=1; done
echo $esito > $F.esito
echo "punteggi finiti $(date), esito $esito"
Y
        manda $S/t01_ferma.sh chat/coda-ds2/s06_t01.sh.tmp
        r 'mv ~/trace/chat/coda-ds2/s06_t01.sh.tmp ~/trace/chat/coda-ds2/s06_t01.sh'
        segna t01_in_coda; fase "T01 in coda (coda-ds2): vLLM si ferma per il calcolo e si riaccende"
      fi
      until r 'test -s ~/trace/training/s06/t01_ferma.fine' 2>/dev/null; do sleep 120; done
      FIN=$(r 'cat ~/trace/training/s06/t01_ferma.fine')
      fase "T01 su ReCaS finito e vLLM di nuovo acceso: $FIN"
      set -- $FIN
      [ "$2" = "0" ] || { r 'tail -3 ~/trace/training/s06/t01_pezzo_*.out' >> $LOG 2>&1; ferma "T01 su ReCaS: il calcolo non e' finito bene (training/s06/t01_pezzo_*.out su ReCaS)"; }
      NP=$3
      for k in $(seq 0 $((NP - 1))); do prendi training/principi/s06_punteggi_$k.jsonl $S/s06_punteggi_$k.jsonl; done
      $PY tools/punteggi_t01_s06.py raccogli-ferma --pezzi $NP >> $LOG 2>&1 || ferma "T01 su ReCaS: la prova contro le H100 non passa o i punteggi non tornano ($S/t01_prova_recas-ferma.json)"
      ;;
    *) ferma "modo di T01 sconosciuto in $S/t01_modo.txt: $MODO";;
  esac
  segna t01; fase "T01 fatto ($MODO)"
fi

# ── 2. il registro: la voce S06 ───────────────────────────────────────────────────────────────────────────────────
if ! fatto registro; then
  prova 3 60 $PY tools/registro_versioni.py --scrivi --solo S06 >> $LOG 2>&1 || ferma "registro S06"
  $PY -c "from google.cloud import firestore; import sys; sys.exit(0 if firestore.Client(project='climpact-drp').collection('trace_versioni').document('S06').get().exists else 1)" \
    || ferma "S06 non e' in trace_versioni"
  segna registro; fase "S06 nel registro (versioni/registro.json e trace_versioni/S06)"
fi

# ── 3. le righe in banca dati, fuori dalle code; contesti, file dei lettori, mappa dei paragrafi ───────────────────
if ! fatto righe_ricontrollate; then
  prova 2 60 $PY tools/recupero_s06.py righe >> $LOG 2>&1 || ferma "righe S06 (prova a secco rifatta)"
  segna righe_ricontrollate
fi
if ! fatto scritte; then
  prova 3 60 $PY tools/recupero_s06.py scrivi --scrivi >> $LOG 2>&1 || ferma "scrittura delle righe S06"
  segna scritte; fase "righe S06 scritte in corpus_rows, fuori dalle code: $(wc -l < $S/righe_s06.jsonl | tr -d ' ')"
fi
if ! fatto lettori; then
  prova 3 60 $PY tools/recupero_s06.py contesti >> $LOG 2>&1 || ferma "contesti dalla banca dati"
  prova 2 60 $PY tools/recupero_s06.py aggiungi >> $LOG 2>&1 || ferma "righe nei file dei lettori"
  for c in $CASI; do s=$(serie $c)
    $PY tools/principi_da_paragrafi.py --caso $c ${s:+--sonde $s} >> $LOG 2>&1 || ferma "mappa dei paragrafi $c"
  done
  # le coppie rifatte sui contesti presi dalla banca dati: se qualcosa e' cambiato, i punteggi mancanti si rifanno
  prova 2 60 $PY tools/recupero_s06.py coppie >> $LOG 2>&1 || ferma "coppie T01 dopo la scrittura"
  $PY - <<'X' >> $LOG 2>&1 || ferma "punteggi T01 mancanti dopo la scrittura (contesti cambiati): rifare il passo t01"
import json, pathlib, sys
sys.path.insert(0, 'tools')
import punteggi_t01_s06 as T
m = {}
for f in sorted(pathlib.Path('training/s06').glob('t01_memoria*.jsonl')):
    if 'prova' not in f.name:
        m.update(T.leggi_memoria(f))
righe = [json.loads(l) for l in open('training/s06/s06_coppie.jsonl', encoding='utf-8')]
manca = [x for x in righe if T.chiave(x['q'], x['d']) not in m]
print('coppie T01', len(righe), 'senza punteggio', len(manca))
if manca:
    sys.exit(1)
T.scrivi_punteggi(righe, {T.chiave(x['q'], x['d']): m[T.chiave(x['q'], x['d'])] for x in righe})
X
  segna lettori; fase "righe S06 nei file dei lettori, mappa dei paragrafi e punteggi T01 pronti"
fi

# ── 4. pagine attorno R10 e cinque letture nelle code di DeepSeek ─────────────────────────────────────────────────
if ! fatto righe_lettura; then prova 3 120 $PY tools/letture_s06.py righe >> $LOG 2>&1 || ferma "righe da leggere"; segna righe_lettura; fi
if ! fatto prepara; then prova 2 60 $PY tools/letture_s06.py prepara >> $LOG 2>&1 || ferma "pagine attorno R10"; segna prepara; fi
if ! fatto letture; then
  prova 6 600 $PY tools/letture_s06.py letture >> $LOG 2>&1 || ferma "letture (6 tentativi)"
  segna letture; rm -f $S/coda_occupata; fase "letture finite: la coda torna libera per il confronto dei decisori"
fi

# ── 5. R11: prova a secco (solo righe di S06), rapporto, scrittura ────────────────────────────────────────────────
conta() { $PY -c "import json,sys; t=open(sys.argv[1]).read(); i=t.find('{'); d=json.JSONDecoder().raw_decode(t[i:])[0]; print(d.get('da scrivere',0))" "$1"; }
if ! fatto secco; then
  for c in $CASI; do s=$(serie $c)
    prova 3 60 $PY tools/carica_lessicali.py --caso $c --etichetta s06 --composizione R11 --salva $S/secco_tipo_$c.json > $S/secco_tipo_$c.txt 2>&1 || ferma "prova a secco del tipo $c"
    prova 3 60 $PY tools/carica_ripresa.py --caso $c --composizione R11 --etichetta ${s}s06 --etichetta-tipo s06 --salva $S/secco_ripresa_$c.json > $S/secco_ripresa_$c.txt 2>&1 || ferma "prova a secco della ripresa $c"
    # solo righe di S06: le altre righe non si toccano
    $PY tools/recupero_s06.py verifica --file $S/secco_tipo_$c.json >> $LOG 2>&1 || ferma "$c: la prova a secco del tipo tocca righe non di S06"
    $PY tools/recupero_s06.py verifica --file $S/secco_ripresa_$c.json >> $LOG 2>&1 || ferma "$c: la prova a secco della ripresa tocca righe non di S06"
    n=$(grep -c . $S/righe_$c.txt); t=$(conta $S/secco_tipo_$c.txt); p=$(conta $S/secco_ripresa_$c.txt)
    fase "prova a secco $c: righe S06 non giudicate $n, tipo da scrivere $t, ripresa da scrivere $p"
    [ $((t * 100)) -ge $((n * 95)) ] && [ $((p * 100)) -ge $((n * 95)) ] || ferma "$c: proposte nuove troppo poche ($t e $p su $n)"
  done
  prova 3 60 $PY tools/letture_s06.py rapporto >> $LOG 2>&1 || ferma "rapporto"
  segna secco
fi
if ! fatto scrittura; then
  for c in $CASI; do s=$(serie $c)
    if [ ! -f $PASSI/tipo_$c ]; then
      prova 4 30 $PY tools/carica_lessicali.py --caso $c --etichetta s06 --composizione R11 --scrivi > $S/scrivi_tipo_$c.txt 2>&1 || ferma "scrittura del tipo $c"
      segna tipo_$c
    fi
    if [ ! -f $PASSI/ripresa_$c ]; then
      prova 4 30 $PY tools/carica_ripresa.py --caso $c --composizione R11 --etichetta ${s}s06 --etichetta-tipo s06 --scrivi > $S/scrivi_ripresa_$c.txt 2>&1 || ferma "scrittura della ripresa $c"
      segna ripresa_$c
    fi
    fase "$c caricato con R11: tipo $(conta $S/scrivi_tipo_$c.txt), ripresa $(conta $S/scrivi_ripresa_$c.txt)"
  done
  segna scrittura
fi

# ── 6. nelle code le righe complete; controllo di completezza ─────────────────────────────────────────────────────
if ! fatto rimesse; then
  prova 3 60 $PY tools/recupero_s06.py rimetti --scrivi >> $LOG 2>&1 || ferma "righe S06 nelle code"
  segna rimesse; fase "righe S06 complete nelle code; restano fuori: $(grep -c . $S/restano_fuori_dalle_code.txt)"
fi
if ! fatto controlli; then
  prova 3 60 $PY tools/controllo_completezza.py > $S/controllo_completezza.txt 2>&1 || fase "ATTENZIONE: controllo di completezza fallito"
  cat $S/controllo_completezza.txt >> $LOG
  n=$(grep -E 'righe da giudicare senza proposte' $S/controllo_completezza.txt | awk -F': ' '{s += $2+0} END {print s+0}')
  fase "controllo di completezza: righe da giudicare senza proposte $n (righe S06 fuori dalle code: $(grep -c . $S/restano_fuori_dalle_code.txt))"
  segna controlli
fi

# ── 7. mappa, archivio, giornale ──────────────────────────────────────────────────────────────────────────────────
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
