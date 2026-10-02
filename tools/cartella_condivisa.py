#!/usr/bin/env python3
"""LA CARTELLA DA CONDIVIDERE CON IL GRUPPO.

Raccoglie in un posto solo tutto cio' che serve a un ricercatore per
lavorare, e nient'altro. Chi la riceve la copia sul proprio Mac ed e'
operativo.

PERCHE' UNA CARTELLA A PARTE E NON L'INTERA CARTELLA DI LAVORO. Quella
contiene registri, copie di riserva, file temporanei, prove abbandonate:
roba che a chi lavora non serve e che genera solo la domanda "questo cosa
e'?". Qui c'e' il necessario, e la guida che lo spiega.

COSA CONTIENE
  modello/          i pesi dei due modelli, non scaricati da internet
  index/            l'indice, gli identificativi, il manifesto, i frammenti
  markdown/         il testo dei documenti con i metadati
  documents/        i PDF, ricercabili
  cited-cases/      le query specification dei casi gia' impostati
  codebook/         come classificare
  tools/            il comando di ricerca e cio' che gli serve
  docs/GUIDA.md     come funziona
  INSTALLA.sh       prepara l'ambiente sulla macchina di chi la riceve

COSA NON CONTIENE, di proposito: le copie di riserva (`.pdf.orig`,
`.txt.pre-ocr`), i registri di lavorazione, gli strumenti di costruzione
del corpus. Restano nella cartella di lavoro, dove servono a dimostrare la
provenienza.

CLONI APFS. I file si copiano con `cp -c`: sui volumi APFS condividono i
blocchi finche' nessuno li modifica, quindi la cartella e' separata a tutti
gli effetti ma sul disco non occupa altri venti gigabyte. Copiandola su un
disco esterno o su un'altra macchina diventa una copia vera.
"""

import shutil
import subprocess
import sys
from pathlib import Path

SORGENTE = Path.home() / 'sabin-corpus'
RICERCA = Path.home() / 'sabin-ricerca-manuale'
DEST = Path.home() / 'climpact-corpus-condiviso'

INSTALLA = '''#!/usr/bin/env bash
# Prepara questa macchina a usare la pipeline. Si lancia una volta.
#
# Cosa fa: crea un ambiente Python isolato (per non toccare quello di
# sistema), installa le due librerie che servono, e verifica che l'indice
# sia leggibile e coerente con il suo manifesto.
#
# I pesi del modello sono gia' qui dentro (cartella `modello/`): non si
# scaricano, e sono esattamente quelli con cui l'indice e' stato costruito.
set -euo pipefail
cd "$(dirname "$0")"

command -v python3.12 >/dev/null || { echo "Serve python3.12 (brew install python@3.12)"; exit 1; }

# I PESI SONO QUI DENTRO, non si scaricano: cosi' sono ESATTAMENTE quelli
# con cui l'indice e' stato costruito. Un deposito pubblico puo' cambiare,
# e pesi diversi darebbero risultati diversi senza alcun segnale.
export HF_HOME="$(pwd)/modello"
export HF_HUB_OFFLINE=1

echo "== ambiente isolato =="
[ -d .venv ] || python3.12 -m venv .venv
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q torch sentence-transformers numpy pymupdf

echo
echo "== verifica dell'indice =="
./.venv/bin/python - <<'PY'
import json, hashlib
from pathlib import Path
import numpy as np
man = json.loads(Path('index/manifesto.json').read_text(encoding='utf-8'))
V = np.load('index/vettori.npy', mmap_mode='r')
ids = json.loads(Path('index/ids.json').read_text(encoding='utf-8'))
print(f"  modello   : {man['modello']}")
print(f"  costruito : {man['costruito']}")
print(f"  vettori   : {V.shape[0]:,} x {V.shape[1]}  ({V.nbytes/1e9:.2f} GB)")
print(f"  pesi      : impronta {man.get('impronta_pesi','?')}")
print(f"  prefissi  : passaggi {man.get('prefisso_passaggio','?')!r}  domande {man.get('prefisso_domanda','?')!r}")
assert V.shape[0] == len(ids) == man['frammenti'], 'indice e identificativi non corrispondono'
impronta = hashlib.sha256(Path('index/chunks.jsonl').read_bytes()).hexdigest()[:32]
if impronta != man.get('impronta_frammenti'):
    print('  ATTENZIONE: i frammenti non sono quelli con cui e stato costruito l indice.')
    print('  Le posizioni non corrispondono piu: chiedere un indice aggiornato.')
else:
    print('  frammenti : corrispondono al manifesto')
PY

echo
echo "Pronto. Per cercare:"
echo "  ./.venv/bin/python tools/cerca.py --caso urgenda"
echo
echo "La prima ricerca carica i due modelli e ci mette un minuto. Le altre no."
'''


def copia(src: Path, dst: Path, escludi=()):
    n = 0
    for f in sorted(src.rglob('*')):
        if not f.is_file():
            continue
        if any(f.name.endswith(s) for s in escludi):
            continue
        if f.name in ('.DS_Store', 'Icon', 'Icon\r'):
            continue
        out = dst / f.relative_to(src)
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            so, sd = f.stat(), out.stat()
            if so.st_size == sd.st_size and int(so.st_mtime) <= int(sd.st_mtime):
                continue
            out.unlink()
        try:
            subprocess.run(['cp', '-c', str(f), str(out)], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            shutil.copy2(f, out)
        n += 1
        if n % 2000 == 0:
            print(f'    {n:,}…', flush=True)
    return n


def main():
    DEST.mkdir(parents=True, exist_ok=True)

    # L'indice: senza `vettori.npy` la rete semantica non funziona, ma la
    # lessicale si' — quindi si copia cio' che c'e' e si dice cosa manca.
    print('indice…', flush=True)
    (DEST / 'index').mkdir(exist_ok=True)
    mancanti = []
    for nome in ('vettori.npy', 'ids.json', 'manifesto.json', 'chunks.jsonl'):
        f = SORGENTE / 'index' / nome
        if not f.exists():
            mancanti.append(nome)
            continue
        out = DEST / 'index' / nome
        if out.exists() and out.stat().st_size == f.stat().st_size:
            continue
        out.unlink(missing_ok=True)
        try:
            subprocess.run(['cp', '-c', str(f), str(out)], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            shutil.copy2(f, out)
        print(f'  {nome}: {f.stat().st_size/1e9:.2f} GB')

    for nome, src in (('markdown', RICERCA / 'markdown'),
                      ('documents', RICERCA / 'documents')):
        if src.is_dir():
            print(f'{nome}…', flush=True)
            print(f'  {copia(src, DEST / nome, (".orig", ".tmp", ".pre-ocr")):,} file')

    # IL MODELLO VIAGGIA CON LA CARTELLA, non si scarica.
    #
    # Si scaricherebbe da solo alla prima ricerca. Ma un deposito pubblico
    # puo' essere aggiornato: chi lo scaricasse fra sei mesi potrebbe
    # ricevere pesi diversi da quelli con cui l'indice e' stato costruito,
    # e i risultati cambierebbero SENZA CHE NESSUNO SE NE ACCORGA — le
    # posizioni continuerebbero a esistere, i punteggi sarebbero altri.
    #
    # Il manifesto registra l'impronta dei pesi; l'installatore la
    # verifica. Ma la verifica serve a poco se poi non c'e' modo di
    # ottenere i pesi giusti: per questo viaggiano qui dentro.
    # DUE MODELLI, non uno. Il secondo e' il riordinatore: senza, la
    # ricerca semantica funziona ma restituisce anche le statistiche al
    # posto delle norme, ed e' esattamente il rumore che il gruppo non deve
    # doversi leggere.
    cache = Path.home() / '.cache' / 'huggingface' / 'hub'
    for nome_hf in ('models--intfloat--multilingual-e5-large',
                    'models--BAAI--bge-reranker-v2-m3'):
        sorgente_modello = cache / nome_hf
        if sorgente_modello.is_dir():
            print(f'{nome_hf.split("--")[-1]}…', flush=True)
            # La cache cerca i pesi in `<HF_HOME>/hub/<nome>`: un livello
            # sbagliato e il modello non viene trovato — e in modalita'
            # offline non c'e' ricaduta, la ricerca non parte.
            n = copia(sorgente_modello, DEST / 'modello' / 'hub' / nome_hf)
            print(f'  {n:,} file')
        else:
            print(f'{nome_hf}: non in cache — verra scaricato al primo uso')

    print('configurazione e strumenti…', flush=True)
    for cart in ('cited-cases', 'codebook', 'docs'):
        if (SORGENTE / cart).is_dir():
            copia(SORGENTE / cart, DEST / cart)
    (DEST / 'tools').mkdir(exist_ok=True)
    for t in ('cerca.py', 'dimensioni.py'):
        shutil.copy2(SORGENTE / 'tools' / t, DEST / 'tools' / t)

    inst = DEST / 'INSTALLA.sh'
    inst.write_text(INSTALLA, encoding='utf-8')
    inst.chmod(0o755)

    du = subprocess.run(['du', '-sh', str(DEST)], capture_output=True, text=True)
    print(f'\ncartella : {DEST}')
    print(f'occupata : {du.stdout.split()[0] if du.stdout else "?"}')
    if mancanti:
        print(f'\nMANCANO ANCORA: {", ".join(mancanti)}')
        print('Senza `vettori.npy` funziona solo la rete lessicale.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
