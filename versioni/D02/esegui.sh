#!/bin/sh
# OCR dei documenti della mappa con pagine illeggibili (01/10/2026): testo per pagina in <doc>.txt (pagine separate da \f)
# il PDF e' sempre quello con lo stesso nome del markdown: il 1/10 due documenti avevano preso un altro PDF della stessa cartella
cd "$(dirname "$0")/../.."
while IFS='|' read d lang pdf; do
  [ -f "training/ocr/$d.txt" ] && continue
  ocrmypdf --force-ocr -l "$lang" --sidecar "training/ocr/$d.txt" --output-type none --jobs 4 "$pdf" - >/dev/null 2>"training/ocr/$d.log" \
    && echo "fatto $d" || echo "ERRORE $d"
done < training/ocr/lista.txt
