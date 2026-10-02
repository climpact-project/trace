#!/bin/bash
# 02/10/2026: le 15 righe toccate dalla seconda OCR (103 documenti, piu' le pagine coreane e giapponesi rese in lettere
# latine): 3 righe nuove di Urgenda e 12 righe gia' in piattaforma la cui pagina, o le pagine attorno, sono cambiate.
# Si rileggono da capo sul testo nuovo e le letture nuove PRENDONO IL POSTO di quelle fatte sul testo illeggibile:
# tipo (etichetta ocr3, caricato con --sovrascrivi), punteggi T01 (<caso>[_P05]_punteggi_ocr3, caricati per ultimi),
# pagine attorno, principi e pagine attorno di DeepSeek (Urgenda: dentro le letture ocr2/l04ocr2; Neubauer: dentro
# P05/l04P05, la sua serie in uso). Da launchd: sopravvive alla chiusura della sessione.
cd ~/sabin-corpus; P=training/principi; O=training/ocr; LOG=$O/ciclo_ocr3.log
fase() { echo "$(date '+%d/%m %H:%M') $*" >> $LOG; }
r() { ssh -o ConnectTimeout=30 -o BatchMode=yes recas "$@"; }
prendi() { until scp -q "recas:trace/$1" "$1"; do sleep 60; done; }
manda() { until scp -q "$1" "recas:trace/$1"; do sleep 60; done; }
fase inizio
for c in urgenda neubauer; do manda training/lessicali_${c}_righe.jsonl; manda $O/righe_ocr3_$c.txt; done
manda $P/ocr3_coppie.jsonl
r 'cat > ~/trace/chat/coda-ds2/ocr3_tipo_punteggi.sh' <<'X'
H=/lustrehome/climpact; C=$H/trace/chat; CH=$(cat $C/chiave); cd $H/trace
export HOME=$H HF_HOME=$H/trace/hf TMPDIR=$H/trace/tmp
A="--base-url http://127.0.0.1:8000/v1 --chiave-file $C/chiave --modello deepseek-v4-flash --paralleli 16"
for c in urgenda neubauer; do venv/bin/python -u tools/024_classifica_lessicali.py leggi --caso $c --gruppo tutte --letture 2 --etichetta ocr3 --solo-id training/ocr/righe_ocr3_$c.txt $A; done > $C/log/ocr3_tipo.log 2>&1
riaccendi() {
  if ! pgrep -u climpact -f "vllm serve" > /dev/null; then echo "riaccendo vLLM $(date)"; nohup $C/vllm2.sh > $C/log/vllm2.log 2>&1 & fi
  until curl -s -m 5 -H "Authorization: Bearer $CH" http://127.0.0.1:8000/v1/models | grep -q deepseek; do sleep 30; done
  echo "vLLM pronto $(date)"
}
trap riaccendi EXIT
pkill -u climpact -f "vllm serve"; sleep 60
GPU=(${CUDA_VISIBLE_DEVICES//,/ })
CUDA_VISIBLE_DEVICES=${GPU[0]} venv/bin/python -u tools/028_ripresa_punteggi.py punteggi --caso ocr3 --pezzo 0 --pezzi 1 > $H/trace/ocr3_punteggi.out 2>&1
echo "fine $(date)" >> $H/trace/ocr3_punteggi.out
X
fase "tipo e punteggi in coda"
until r "grep -q '^fine' ~/trace/ocr3_punteggi.out" 2>/dev/null; do sleep 120; done
for c in urgenda neubauer; do prendi training/lessicali_${c}_deepseek_ocr3.jsonl; done
prendi $P/ocr3_punteggi_0.jsonl
# il tipo: le letture nuove prendono il posto delle vecchie
for c in urgenda neubauer; do for i in 1 2 3; do .venv/bin/python tools/025_carica_lessicali.py --caso $c --etichetta ocr3 --sovrascrivi --scrivi >> $LOG 2>&1 && break; sleep 30; done; done
fase "tipo caricato"
# i punteggi divisi per caso: Urgenda (serie storica) e Neubauer (serie P05 in uso)
.venv/bin/python - <<'X' >> $LOG 2>&1
import json, pathlib
P = pathlib.Path('training/principi')
coppie = [json.loads(l) for l in open(P/'ocr3_coppie.jsonl')]
punti = [json.loads(l) for l in open(P/'ocr3_punteggi_0.jsonl')]
out = {'urgenda': open(P/'urgenda_punteggi_ocr3.jsonl', 'w'), 'neubauer': open(P/'neubauer_P05_punteggi_ocr3.jsonl', 'w')}
for c, s in zip(coppie, punti):
    out[c['caso']].write(json.dumps(s, ensure_ascii=False) + '\n')
print('punteggi ocr3 divisi', len(punti))
X
# pagine attorno e righe da leggere
.venv/bin/python -c "import sys; sys.path.insert(0,'tools'); import leggi_ripresa as LR; LR.prepara('urgenda'); LR.prepara('neubauer')" >> $LOG 2>&1
.venv/bin/python - <<'X' >> $LOG 2>&1
import json, pathlib
P = pathlib.Path('training/principi'); O = pathlib.Path('training/ocr')
for c, base in (('urgenda', 'urgenda_ripresa_righe.jsonl'), ('neubauer', 'neubauer_ripresa_righe_P05.jsonl')):
    ids = set(O.joinpath(f'righe_ocr3_{c}.txt').read_text().split())
    righe = [l for l in open(P/base) if json.loads(l)['id'] in ids]
    for et in (('ocr3', 'l04ocr3') if c == 'urgenda' else ('P05ocr3', 'l04P05ocr3')):
        open(P/f'{c}_ripresa_righe_{et}.jsonl', 'w').writelines(righe)
    print(c, 'righe da leggere', len(righe))
X
for f in urgenda_ripresa_righe_ocr3 urgenda_ripresa_righe_l04ocr3 neubauer_ripresa_righe_P05ocr3 neubauer_ripresa_righe_l04P05ocr3; do manda $P/$f.jsonl; done
manda $P/urgenda_punteggi_ocr3.jsonl; manda $P/neubauer_P05_punteggi_ocr3.jsonl
r 'cat > ~/trace/chat/coda-ds2/ocr3_letture.sh' <<'X'
H=/lustrehome/climpact/trace; C=$H/chat; cd $H
A="--base-url http://127.0.0.1:8000/v1 --chiave-file $C/chiave --modello deepseek-v4-flash --paralleli 16"
$H/venv/bin/python -u tools/031_leggi_ripresa.py leggi --caso urgenda --etichetta ocr3 --letture 2 $A > $C/log/ocr3_letture.log 2>&1
$H/venv/bin/python -u tools/032_leggi_l04.py leggi --caso urgenda --etichetta l04ocr3 --letture 2 $A >> $C/log/ocr3_letture.log 2>&1
TRACE_SONDE=P05 $H/venv/bin/python -u tools/031_leggi_ripresa.py leggi --caso neubauer --etichetta P05ocr3 --letture 2 $A >> $C/log/ocr3_letture.log 2>&1
TRACE_SONDE=P05 $H/venv/bin/python -u tools/032_leggi_l04.py leggi --caso neubauer --etichetta l04P05ocr3 --letture 2 $A >> $C/log/ocr3_letture.log 2>&1
echo FINITO > $C/log/ocr3_fine.txt
X
fase "letture in coda"
until r 'test -s ~/trace/chat/log/ocr3_fine.txt' 2>/dev/null; do sleep 120; done
for f in urgenda_ripresa_deepseek_ocr3 urgenda_ripresa_deepseek_l04ocr3 neubauer_ripresa_deepseek_P05ocr3 neubauer_ripresa_deepseek_l04P05ocr3; do prendi $P/$f.jsonl; done
# le letture nuove prendono il posto delle vecchie nei file che il caricamento legge (copia di prima accanto)
.venv/bin/python - <<'X' >> $LOG 2>&1
import json, pathlib, shutil
P = pathlib.Path('training/principi')
for nuovo, dentro in (('urgenda_ripresa_deepseek_ocr3', 'urgenda_ripresa_deepseek_ocr2'), ('urgenda_ripresa_deepseek_l04ocr3', 'urgenda_ripresa_deepseek_l04ocr2'),
                      ('neubauer_ripresa_deepseek_P05ocr3', 'neubauer_ripresa_deepseek_P05'), ('neubauer_ripresa_deepseek_l04P05ocr3', 'neubauer_ripresa_deepseek_l04P05')):
    N = {json.loads(l)['id']: l for l in open(P/f'{nuovo}.jsonl')}
    f = P/f'{dentro}.jsonl'; shutil.copy(f, P/f'{dentro}.prima-ocr3.jsonl')
    vecchie = [l for l in open(f) if json.loads(l)['id'] not in N]
    open(f, 'w').writelines(vecchie + list(N.values()))
    print(dentro, 'sostituite o aggiunte', len(N))
X
for c in urgenda neubauer; do for i in 1 2 3 4; do .venv/bin/python tools/035_carica_ripresa.py --caso $c --principi-da-l04 --scrivi > /tmp/ocr3_carica_$c.txt 2>&1 && break; sleep 30; done; fase "$c caricato: $(grep -E '^scritte' /tmp/ocr3_carica_$c.txt)"; done
for i in 1 2 3; do .venv/bin/python tools/036_controllo_completezza.py --scrivi > /tmp/ocr3_controllo.txt 2>&1 && break; sleep 30; done
.venv/bin/python tools/037_controllo_finestra.py > /tmp/ocr3_finestra.txt 2>&1
cat /tmp/ocr3_controllo.txt /tmp/ocr3_finestra.txt >> $LOG; fase FINITO
launchctl bootout gui/$(id -u)/it.climpact.ocr3 2>/dev/null
