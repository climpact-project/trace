#!/usr/bin/env bash
# COSTRUZIONE DELL'INDICE SULLA MACCHINA IN AFFITTO.
#
# Gira sul pod, non qui. Fa tutto in una volta perche' ogni minuto di
# quella macchina si paga: niente passaggi interattivi, niente attese fra
# un comando e l'altro.
#
# COSA SI ASPETTA DI TROVARE (caricati prima via scp):
#   /workspace/chunks.jsonl.gz   i frammenti compressi (472 MB)
#   /workspace/build_index.py    l'indicizzatore
set -euo pipefail
cd /workspace

echo "== 1. ambiente =="
python -c "import torch; print('torch', torch.__version__, '| cuda', torch.cuda.is_available(), '|', torch.cuda.get_device_name(0) if torch.cuda.is_available() else '-')"
pip install -q --no-input sentence-transformers 2>&1 | tail -2

echo
echo "== 2. frammenti =="
mkdir -p index
[ -f index/chunks.jsonl ] || gunzip -c chunks.jsonl.gz > index/chunks.jsonl
wc -l < index/chunks.jsonl

echo
echo "== 3. prova di velocita su 2.000 frammenti =="
# Serve a sapere SUBITO quanto durera' il lavoro intero, invece di
# scoprirlo dopo mezz'ora. Se il numero e' assurdo, si ferma qui.
python 008_build_index.py --prova 2000 --batch 128

echo
echo "== 4. costruzione =="
time python 008_build_index.py --batch 128

echo
echo "== 5. esito =="
ls -la index/vettori.npy index/ids.json index/manifesto.json
cat index/manifesto.json
