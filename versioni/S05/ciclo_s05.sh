#!/bin/bash
# CICLO S05 (scritto il 02/10/2026, NON lanciato): carica in piattaforma le righe nuove della ricerca per nome S05 e
# fa le letture che le altre righe hanno gia': tipo (L03; per Urgenda L02, come scrive carica_lessicali.py), principi
# (L04) e pagine attorno (L05) con DeepSeek, punteggi T01 sul brano e sulle pagine attorno ancora senza punteggio.
# Poi i due controlli. Modellato su ciclo_ocr3.sh, ciclo_ocr3_rifai.sh e ciclo_giapponese.sh; da launchd
# (tools/launchd/spenti/it.climpact.s05.plist), cosi' sopravvive alla chiusura della sessione.
#
# SI LANCIA SOLO DOPO IL SI' DEL PI, e dopo tre passi a mano che il ciclo controlla e senza i quali si ferma:
#   1. il registro: applicare tools/registro_versioni_S05.patch e scrivere S05 e D03 in trace_versioni
#        git apply tools/registro_versioni_S05.patch && .venv/bin/python tools/registro_versioni.py --scrivi
#      (controllo_completezza.py segnala come difetto ogni riga la cui provenienza nomina una versione non registrata);
#   2. i file dei casi: S05 diventa la ricerca in uso (le letture, la mappa dei paragrafi e i contesti leggono il
#      file vivo); il file di S03 resta accanto con la data
#        for c in urgenda neubauer future-generations klimaseniorinnen cig-parere-clima idh-oc-32-25; do
#          cp cited-cases/$c.yaml cited-cases/$c-S03-2026-10-02.yaml.bak && cp cited-cases/$c-S05.yaml cited-cases/$c.yaml; done
#   3. l'indice delle pagine con le pagine dei 277 Markdown nuovi (servono per le pagine attorno)
#        cp index/pagine/pagine.jsonl.gz index/pagine/pagine.prima-S05.jsonl.gz && cp index/pagine/pagine.s05.jsonl.gz index/pagine/pagine.jsonl.gz
#      (se nel frattempo l'indice vivo e' cambiato, rifare prima `build_markdown_s05.py --scrivi`: l'impronta del vivo
#      copiato sta in training/s05/markdown_s05_registro.json).
# Poi: cp tools/launchd/spenti/it.climpact.s05.plist ~/Library/LaunchAgents/ && launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/it.climpact.s05.plist
#
# Righe: tools/unisci_s05.py --scrivi aggiunge SOLO le righe nuove (stessa regola e stessa assegnazione dei codici di
# unisci_e_aggiungi.py; le righe esistenti non si uniscono ne' si toccano). Le letture nuove hanno etichette proprie
# (s05) e poi si aggiungono ai file che il caricamento legge, con la copia di prima accanto (come ciclo_ocr3.sh).
# ALLA FINE, e anche se si ferma prima per un errore, il plist esce da ~/Library/LaunchAgents: un plist dimenticato li'
# riparte a ogni riavvio del Mac (successo il 02/10/2026).
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd ~/sabin-corpus || exit 1
P=training/principi; T=training; S=training/s05; LOG=$S/ciclo_s05.log
ETICHETTA=it.climpact.s05; PLIST=$HOME/Library/LaunchAgents/$ETICHETTA.plist
CASI="urgenda neubauer future-generations klimaseniorinnen cig-parere-clima idh-oc-32-25"
# la serie di sonde in uso per caso (sonde.SERIE_IN_USO) e le etichette delle letture che carica_ripresa.py legge
serie() { case $1 in neubauer|future-generations) echo P05;; cig-parere-clima) echo P09;; *) echo "";; esac; }
l05_file() { s=$(serie $1); if [ -n "$s" ]; then echo ${1}_ripresa_deepseek_$s; else echo ${1}_ripresa_deepseek_v2; fi; }
l04_file() { s=$(serie $1); if [ -n "$s" ]; then echo ${1}_ripresa_deepseek_l04$s; else echo ${1}_ripresa_deepseek_l04nuove; fi; }
suf() { s=$(serie $1); [ -n "$s" ] && echo _$s; }

fase() { echo "$(date '+%d/%m %H:%M') $*" >> $LOG; .venv/bin/python tools/giornale.py evento --nome ciclo_s05 --testo "$*" 2>/dev/null; }
r() { ssh -o ConnectTimeout=30 -o BatchMode=yes recas "$@"; }
prendi() { until scp -q "recas:trace/$1" "$1"; do sleep 60; done; }
manda() { until scp -q "$1" "recas:trace/$1"; do sleep 60; done; }
prendi_n() { # file righe_attese: si prende solo quando e' completo (lezione del 02/10: file presi a meta')
  until [ "$(r "wc -l < ~/trace/$1" 2>/dev/null | tr -d ' ')" = "$2" ]; do sleep 60; done
  until scp -q "recas:trace/$1" "$1" && [ "$(wc -l < "$1" | tr -d ' ')" = "$2" ]; do sleep 30; done; }
fine() { # SEMPRE, anche dopo un errore: il plist esce da LaunchAgents, poi launchd dimentica il lavoro
  if [ -f "$PLIST" ]; then mkdir -p tools/launchd/spenti; mv "$PLIST" "tools/launchd/spenti/$ETICHETTA.plist.fatto-$(date +%Y-%m-%d_%H%M)"; fi
  echo "$(date '+%d/%m %H:%M') plist tolto da LaunchAgents" >> $LOG
  .venv/bin/python tools/giornale.py invia >/dev/null 2>&1
  launchctl bootout gui/$(id -u)/$ETICHETTA 2>/dev/null
}
trap fine EXIT
ferma() { fase "FERMO: $*"; exit 1; }
mkdir -p $S
fase inizio

# ── 0. i tre passi a mano sono stati fatti? ───────────────────────────────────────────────────────────────────────
for c in $CASI; do cmp -s cited-cases/$c.yaml cited-cases/$c-S05.yaml || ferma "cited-cases/$c.yaml non e' il file S05 (passo 2)"; done
cmp -s index/pagine/pagine.jsonl.gz index/pagine/pagine.s05.jsonl.gz || ferma "l'indice delle pagine non e' quello S05 (passo 3)"
.venv/bin/python - <<'X' || ferma "S05 o D03 mancano in trace_versioni (passo 1)"
from google.cloud import firestore
db = firestore.Client(project='climpact-drp')
assert all(db.collection('trace_versioni').document(c).get().exists for c in ('S05', 'D03'))
X
fase "controlli iniziali passati"

# ── 1. le righe nuove (la stessa prova a secco di prima, poi la scrittura) ────────────────────────────────────────
# la prova a secco rifatta sulla banca dati di oggi, in una cartella sua (quella rivista dal PI resta com'e')
.venv/bin/python tools/unisci_s05.py --uscita $S/carico > $S/unisci_prova_prima_della_scrittura.txt 2>&1 || ferma "unisci_s05 a secco"
for c in $CASI; do
  for i in 1 2 3; do .venv/bin/python tools/unisci_s05.py --caso $c --uscita $S/carico --scrivi >> $LOG 2>&1 && break; sleep 30; done
done
fase "righe nuove scritte: $(grep -h '^   scritte' $LOG | tr -d '\n')"

# ── 2. le righe da leggere: esportazione della banca dati, contesti, elenco delle righe nuove ─────────────────────
.venv/bin/python - $CASI <<'X' >> $LOG 2>&1 || ferma "esportazione delle righe"
import json, sys, pathlib
from google.cloud import firestore
db = firestore.Client(project='climpact-drp'); S = pathlib.Path('training/s05')
for caso in sys.argv[1:]:
    righe, nuove = [], []
    for d in db.collection('corpus_rows').where(filter=firestore.FieldFilter('caso_citato', '==', caso)).stream():
        r = d.to_dict(); r['_id'] = d.id; righe.append(r)
        if (r.get('provenienza') or {}).get('estrazione') == 'S05' and str(r.get('esecuzione_id', '')).endswith('-S05'):
            nuove.append(d.id)
    json.dump(righe, open(S/f'{caso}_corpus_rows_s05.json', 'w', encoding='utf-8'), ensure_ascii=False, default=str)
    (S/f'righe_s05_{caso}.txt').write_text('\n'.join(sorted(nuove)) + '\n', encoding='utf-8')
    print(caso, 'righe', len(righe), 'nuove S05', len(nuove))
X
for c in $CASI; do
  .venv/bin/python tools/classifica_lessicali.py prepara --caso $c --righe-firestore $S/${c}_corpus_rows_s05.json >> $LOG 2>&1 || ferma "prepara $c"
  s=$(serie $c); .venv/bin/python tools/principi_da_paragrafi.py --caso $c ${s:+--sonde $s} >> $LOG 2>&1 || ferma "paragrafi $c"
done
fase "contesti e paragrafi pronti"

# ── 3. le coppie per T01: brano delle righe nuove e pagine attorno (10 prima, 10 dopo) ancora senza punteggio ─────
.venv/bin/python - $CASI <<'X' >> $LOG 2>&1 || ferma "coppie T01"
import gzip, json, os, sys, pathlib
sys.path.insert(0, 'tools')
import yaml, sonde as SO, ripresa_punteggi as RP
from prepara_training import mascheratore, SEGNAPOSTO
P, S = pathlib.Path('training/principi'), pathlib.Path('training/s05')
out = open(P/'s05_coppie.jsonl', 'w', encoding='utf-8'); n = 0
for caso in sys.argv[1:]:
    nuove = set((S/f'righe_s05_{caso}.txt').read_text().split())
    conf = yaml.safe_load(open(SO.file_caso(caso), encoding='utf-8'))
    vive = yaml.safe_load(open(f'cited-cases/{caso}.yaml', encoding='utf-8'))      # = file S05 (controllato al passo 0)
    maschera = mascheratore(sorted({str(f) for f in list(conf['forme']) + list(vive['forme'])}) + [conf.get('nome', '')])
    principi = {s['id']: ' '.join(s['testo'].split()) for s in conf['semantic_queries']}
    gia = set()
    for f in P.glob(f'{caso}{SO.suf(caso)}_punteggi_*.jsonl'):
        for l in open(f, encoding='utf-8'):
            x = json.loads(l)
            if x['dove'] == 'vicina': gia.add(x['pagina_id'])
    righe = [json.loads(l) for l in open(f'training/lessicali_{caso}_righe.jsonl', encoding='utf-8')]
    righe = [r for r in righe if r['id'] in nuove]
    serve = {f"{r['document_id']}#p{k}" for r in righe if int(r.get('pagina') or 0)
             for k in range(int(r['pagina']) - RP.PRIMA, int(r['pagina']) + RP.DOPO + 1) if k > 0 and k != int(r['pagina'])} - gia
    pag = {}
    with gzip.open('index/pagine/pagine.jsonl.gz', 'rt', encoding='utf-8') as f:
        for l in f:
            x = json.loads(l)
            if x['id'] in serve: pag[x['id']] = x['testo']
    for r in righe:
        ctx = r['contesto']; a, b = ctx.find('[[INIZIO DEL BRANO SEGNALATO]]'), ctx.find('[[FINE DEL BRANO SEGNALATO]]')
        if a < 0 or b < 0: continue
        br = ctx[max(0, a - RP.ALLARGA): b + len('[[FINE DEL BRANO SEGNALATO]]') + RP.ALLARGA]
        br = br.replace('[[INIZIO DEL BRANO SEGNALATO]]', '').replace('[[FINE DEL BRANO SEGNALATO]]', '').replace('⟦', '').replace('⟧', '')
        br = maschera.sub(SEGNAPOSTO, ' '.join(br.split()))
        for pid, q in principi.items():
            out.write(json.dumps({'caso': caso, 'riga': r['id'], 'dove': 'brano', 'pagina': r.get('pagina'), 'principio': pid, 'q': q, 'd': br}, ensure_ascii=False) + '\n'); n += 1
    for pagid, testo in pag.items():
        d = maschera.sub(SEGNAPOSTO, ' '.join(testo.split()))
        for pid, q in principi.items():
            out.write(json.dumps({'caso': caso, 'pagina_id': pagid, 'dove': 'vicina', 'principio': pid, 'q': q, 'd': d}, ensure_ascii=False) + '\n'); n += 1
    print(caso, 'righe nuove', len(righe), 'pagine attorno senza punteggio', len(pag))
out.close(); print('coppie', n)
X
NCOPPIE=$(wc -l < $P/s05_coppie.jsonl | tr -d ' ')
fase "coppie T01: $NCOPPIE"

# ── 4. in coda su ReCaS: tipo (DeepSeek) e punteggi T01 (una GPU, vLLM spento e poi riacceso, come ocr3) ──────────
r 'mkdir -p ~/trace/training/principi ~/trace/training/s05 ~/trace/cited-cases'
for f in tools/classifica_lessicali.py tools/leggi_ripresa.py tools/leggi_l04.py tools/chiamata_deepseek.py tools/sonde.py tools/freni.py \
         tools/ripresa_punteggi.py tools/posizione_dopo_ocr.py tools/giornale.py; do manda $f; done
for c in $CASI; do manda cited-cases/$c.yaml; manda training/lessicali_${c}_righe.jsonl; manda $S/righe_s05_$c.txt; done
manda $P/s05_coppie.jsonl
r 'rm -f ~/trace/chat/log/s05_fine.txt ~/trace/s05_punteggi.out'
{ echo 'H=/lustrehome/climpact; C=$H/trace/chat; CH=$(cat $C/chiave); cd $H/trace'
  echo 'export HOME=$H HF_HOME=$H/trace/hf TMPDIR=$H/trace/tmp'
  echo 'A="--base-url http://127.0.0.1:8000/v1 --chiave-file $C/chiave --modello deepseek-v4-flash --paralleli 16"'
  for c in $CASI; do echo "venv/bin/python -u tools/classifica_lessicali.py leggi --caso $c --gruppo tutte --letture 2 --etichetta s05 --solo-id training/s05/righe_s05_$c.txt \$A >> \$C/log/s05_tipo.log 2>&1"; done
  cat <<'Y'
riaccendi() {
  if ! pgrep -u climpact -f "vllm serve" > /dev/null; then echo "riaccendo vLLM $(date)"; nohup $C/vllm2.sh > $C/log/vllm2.log 2>&1 & fi
  until curl -s -m 5 -H "Authorization: Bearer $CH" http://127.0.0.1:8000/v1/models | grep -q deepseek; do sleep 30; done
  echo "vLLM pronto $(date)"
}
trap riaccendi EXIT
pkill -u climpact -f "vllm serve"; sleep 60
GPU=(${CUDA_VISIBLE_DEVICES//,/ })
CUDA_VISIBLE_DEVICES=${GPU[0]} venv/bin/python -u tools/ripresa_punteggi.py punteggi --caso s05 --pezzo 0 --pezzi 1 > $H/trace/s05_punteggi.out 2>&1
echo "fine $(date)" >> $H/trace/s05_punteggi.out
Y
} | r 'cat > ~/trace/chat/coda-ds2/s05_tipo_punteggi.sh'
fase "tipo e punteggi in coda (coda-ds2)"
until r "grep -q '^fine' ~/trace/s05_punteggi.out" 2>/dev/null; do sleep 120; done
for c in $CASI; do prendi training/lessicali_${c}_deepseek_s05.jsonl; done      # il tipo e' finito prima dei punteggi, nello stesso lavoro
prendi_n $P/s05_punteggi_0.jsonl $NCOPPIE
for c in $CASI; do for i in 1 2 3; do .venv/bin/python tools/carica_lessicali.py --caso $c --etichetta s05 --scrivi >> $LOG 2>&1 && break; sleep 30; done; done
fase "tipo caricato"
# i punteggi divisi per caso, nel file che leggi_ripresa.prepara e carica_ripresa.py leggono (<caso>[_serie]_punteggi_s05)
.venv/bin/python - <<'X' >> $LOG 2>&1 || ferma "punteggi divisi"
import json, pathlib, sys
sys.path.insert(0, 'tools'); import sonde as SO
P = pathlib.Path('training/principi')
coppie = [json.loads(l) for l in open(P/'s05_coppie.jsonl')]
punti = [json.loads(l) for l in open(P/'s05_punteggi_0.jsonl')]
assert len(coppie) == len(punti)
out, n = {}, {}
for c, s in zip(coppie, punti):
    assert c['principio'] == s['principio'] and c.get('riga') == s.get('riga') and c.get('pagina_id') == s.get('pagina_id')
    caso = c['caso']
    if caso not in out:
        out[caso] = open(P/f'{caso}{SO.suf(caso)}_punteggi_s05.jsonl', 'w'); n[caso] = 0
    out[caso].write(json.dumps(s, ensure_ascii=False) + '\n'); n[caso] += 1
print('punteggi s05 divisi', n)
X
fase "punteggi T01 divisi per caso"

# ── 5. pagine attorno e letture L05 e L04 delle righe nuove, in coda ──────────────────────────────────────────────
.venv/bin/python - $CASI <<'X' >> $LOG 2>&1 || ferma "righe da leggere"
import json, pathlib, sys
sys.path.insert(0, 'tools'); import sonde as SO, leggi_ripresa as LR
P, S = pathlib.Path('training/principi'), pathlib.Path('training/s05')
for caso in sys.argv[1:]:
    LR.prepara(caso)
    ids = set((S/f'righe_s05_{caso}.txt').read_text().split())
    nuove = [l for l in open(P/f'{caso}_ripresa_righe{SO.suf(caso)}.jsonl') if json.loads(l)['id'] in ids]
    s = SO.serie(caso)
    for et in ((f'{s}s05', f'l04{s}s05') if s else ('s05', 'l04s05')):
        open(P/f'{caso}_ripresa_righe_{et}.jsonl', 'w').writelines(nuove)
    print(caso, 'righe nuove da leggere', len(nuove))
X
for c in $CASI; do s=$(serie $c); for et in ${s}s05 l04${s}s05; do manda $P/${c}_ripresa_righe_$et.jsonl; done; done
for f in $P/*_punteggi_s05.jsonl; do manda $f; done
{ echo 'H=/lustrehome/climpact/trace; C=$H/chat; cd $H'
  echo 'A="--base-url http://127.0.0.1:8000/v1 --chiave-file $C/chiave --modello deepseek-v4-flash --paralleli 16"'
  for c in $CASI; do s=$(serie $c)
    echo "TRACE_SONDE=$s \$H/venv/bin/python -u tools/leggi_ripresa.py leggi --caso $c --etichetta ${s}s05 --letture 2 \$A >> \$C/log/s05_letture.log 2>&1"
    echo "TRACE_SONDE=$s \$H/venv/bin/python -u tools/leggi_l04.py leggi --caso $c --etichetta l04${s}s05 --letture 2 \$A >> \$C/log/s05_letture.log 2>&1"
  done
  echo 'echo FINITO > $C/log/s05_fine.txt'
} | r 'cat > ~/trace/chat/coda-ds2/s05_letture.sh'
fase "letture L05 e L04 in coda (coda-ds2)"
until r 'test -s ~/trace/chat/log/s05_fine.txt' 2>/dev/null; do sleep 120; done
for c in $CASI; do s=$(serie $c); prendi $P/${c}_ripresa_deepseek_${s}s05.jsonl; prendi $P/${c}_ripresa_deepseek_l04${s}s05.jsonl; done
# le letture nuove si aggiungono ai file che carica_ripresa.py legge, con la copia di prima accanto
for c in $CASI; do s=$(serie $c)
  .venv/bin/python - $P/${c}_ripresa_deepseek_${s}s05.jsonl $P/$(l05_file $c).jsonl $P/${c}_ripresa_deepseek_l04${s}s05.jsonl $P/$(l04_file $c).jsonl <<'X' >> $LOG 2>&1 || ferma "letture aggiunte $c"
import json, shutil, sys, pathlib
for nuovo, dentro in ((sys.argv[1], sys.argv[2]), (sys.argv[3], sys.argv[4])):
    N = {json.loads(l)['id']: l for l in open(nuovo)}
    f = pathlib.Path(dentro)
    vecchie = [l for l in open(f)] if f.exists() else []
    if f.exists(): shutil.copy(f, f.with_name(f.stem + '.prima-s05.jsonl'))
    gia = {json.loads(l)['id'] for l in vecchie}
    assert not (gia & set(N)), f'{f.name}: righe nuove gia\' lette'
    open(f, 'w').writelines(vecchie + [l if l.endswith('\n') else l + '\n' for l in N.values()])
    print(f.name, 'aggiunte', len(N))
X
done
for c in $CASI; do for i in 1 2 3 4; do .venv/bin/python tools/carica_ripresa.py --caso $c --principi-da-l04 --scrivi > $S/carica_$c.txt 2>&1 && break; sleep 30; done
  fase "$c caricato: $(grep -E '^scritte' $S/carica_$c.txt)"; done

# ── 6. i controlli ────────────────────────────────────────────────────────────────────────────────────────────────
for i in 1 2 3; do .venv/bin/python tools/controllo_completezza.py --scrivi > $S/controllo_completezza.txt 2>&1 && break; sleep 30; done
.venv/bin/python tools/controllo_finestra.py > $S/controllo_finestra.txt 2>&1
cat $S/controllo_completezza.txt $S/controllo_finestra.txt >> $LOG
fase FINITO
# (il trap `fine` toglie il plist da ~/Library/LaunchAgents e chiude il lavoro in launchd)
