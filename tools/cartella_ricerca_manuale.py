#!/usr/bin/env python3
"""LA CARTELLA PER LA RICERCA MANUALE.

A CHE SERVE. Il controllo umano — il 20% delle righe che una persona
verifica — si fa aprendo il documento. Chi lo fa non deve navigare dentro
la cartella di lavoro del corpus, che contiene anche i registri, i
frammenti, gli originali di riserva e gli strumenti: deve avere davanti
due cose sole, i PDF e i Markdown, con la stessa struttura di cartelle che
compare nel CSV.

COSA CONTIENE:
  documents/  i PDF, tutti RICERCABILI (i 562 riparati hanno lo strato di
              testo aggiunto da noi; gli altri lo avevano gia')
  markdown/   il testo con i metadati in testa, un file per documento

COSA NON CONTIENE, di proposito: i `.pdf.orig` e i `.txt.pre-ocr`, cioe' le
copie di riserva. Restano nella cartella di lavoro, dove servono a
dimostrare la provenienza. Qui darebbero solo il doppio dei file e il
dubbio su quale aprire.

PERCHE' `cp -c` E NON UNA COPIA NORMALE. Su APFS crea un CLONE: i due file
condividono gli stessi blocchi finche' nessuno li modifica. La cartella e'
a tutti gli effetti separata — la si puo' spostare, comprimere, mandare a
un collega — ma sul disco non occupa altri sedici gigabyte. Copiandola su
un'altra macchina o su un disco esterno diventa una copia vera.
"""

import shutil
import subprocess
import sys
from pathlib import Path

SORGENTE = Path.home() / 'sabin-corpus'
DESTINAZIONE = Path.home() / 'sabin-ricerca-manuale'

LEGGIMI = """# Corpus Sabin — cartella per la ricerca manuale

Serve alla **verifica a mano** delle citazioni: si apre il documento
indicato dal CSV, alla pagina indicata, e si controlla.

## Cosa c'è

- **`documents/`** — i PDF. Tutti ricercabili: si può cercare dentro con
  Cmd+F, selezionare e copiare. 562 di essi erano scansioni senza testo o
  con la codifica dei caratteri rotta, e hanno uno strato di testo
  aggiunto da noi con OCR; l'aspetto della pagina non è cambiato.
- **`markdown/`** — lo stesso testo in forma leggibile, con in testa i
  metadati del documento (caso, giurisdizione, tipo di atto, date,
  indirizzi, riassunto del caso) e i segni di pagina `<!-- page N -->`.

Le due cartelle hanno la **stessa struttura**: una sottocartella per caso,
e dentro un file per documento con lo stesso nome. Le colonne `file` del
CSV puntano qui.

## Come si usa

Dal CSV delle citazioni prendi `file` e `pagina`. Apri il PDF
corrispondente in `documents/` (stesso percorso, estensione `.pdf`) alla
pagina indicata, e cerca il testo della colonna `citazione_testuale`.

Se preferisci leggere il testo senza il PDF, il file `.md` in `markdown/`
contiene lo stesso contenuto: cerca il segno `<!-- page N -->` per trovare
la pagina.

## Cosa NON c'è

Le copie di riserva (`.pdf.orig`, `.txt.pre-ocr`) e gli strumenti restano
nella cartella di lavoro `~/sabin-corpus`. Qui ci sono solo i documenti.

## Attenzione

Per i 562 documenti con OCR aggiunto, la ricerca dentro il PDF funziona
**su questi file locali**. La pagina corrispondente sul sito del Sabin
serve il PDF originale, che quello strato di testo non ce l'ha.
"""


def copia(src: Path, dst: Path, escludi_suffissi):
    """Sincronizza la cartella, clonando su APFS quando possibile.

    Torna (nuovi, aggiornati): la distinzione conta, perche' 'aggiornati'
    sono documenti che qualcuno poteva avere gia' aperto nella versione
    precedente."""
    n = 0
    aggiornati = []
    for f in sorted(src.rglob('*')):
        if not f.is_file():
            continue
        if any(f.name.endswith(s) for s in escludi_suffissi):
            continue
        if f.name in ('Icon\r', 'Icon', '.DS_Store'):
            continue
        out = dst / f.relative_to(src)
        out.parent.mkdir(parents=True, exist_ok=True)
        # SINCRONIZZA, NON SOLO COPIA.
        #
        # Prima si saltava tutto cio' che esisteva gia', e la cartella
        # restava ferma alla prima costruzione. Ma i file cambiano: un
        # documento riparato con l'OCR riscrive il suo `.txt`, quindi il
        # Markdown, quindi il PDF. E i file qui dentro sono CLONI APFS —
        # condividono i blocchi finche' nessuno scrive, e appena l'originale
        # cambia le due copie divergono in silenzio.
        # Senza questo confronto si aprirebbe un documento vecchio credendolo
        # aggiornato: il guasto peggiore, perche' non da' alcun segno.
        if out.exists():
            so, sd = f.stat(), out.stat()
            if so.st_size == sd.st_size and int(so.st_mtime) <= int(sd.st_mtime):
                continue
            out.unlink()
            aggiornati.append(str(out.relative_to(dst)))
        try:
            # -c chiede il clone APFS; se il volume non lo supporta, `cp`
            # fallisce e si ricade sulla copia normale.
            subprocess.run(['cp', '-c', str(f), str(out)], check=True,
                           capture_output=True)
        except subprocess.CalledProcessError:
            shutil.copy2(f, out)
        n += 1
        if n % 2000 == 0:
            print(f'    {n:,} file…', flush=True)
    return n, aggiornati


def main():
    if not SORGENTE.is_dir():
        print(f'Non trovo {SORGENTE}')
        return 1
    DESTINAZIONE.mkdir(parents=True, exist_ok=True)

    print('PDF (esclusi gli originali di riserva)…', flush=True)
    a, agg_a = copia(SORGENTE / 'documents', DESTINAZIONE / 'documents', ('.orig', '.tmp'))
    print(f'  {a:,} copiati, di cui {len(agg_a):,} AGGIORNATI')

    print('Markdown…', flush=True)
    b, agg_b = copia(SORGENTE / 'markdown', DESTINAZIONE / 'markdown', ())
    print(f'  {b:,} copiati, di cui {len(agg_b):,} AGGIORNATI')

    if agg_a or agg_b:
        (DESTINAZIONE / 'AGGIORNAMENTI.txt').write_text(
            'File sostituiti nell\'ultima sincronizzazione\n'
            '(erano gia\' presenti in una versione precedente)\n\n'
            + '\n'.join(sorted(agg_a + agg_b)), encoding='utf-8')
        print(f"\n  elenco dei sostituiti: {DESTINAZIONE / 'AGGIORNAMENTI.txt'}")

    (DESTINAZIONE / 'LEGGIMI.md').write_text(LEGGIMI, encoding='utf-8')

    du = subprocess.run(['du', '-sh', str(DESTINAZIONE)],
                        capture_output=True, text=True)
    print(f'\ncartella : {DESTINAZIONE}')
    print(f'occupata : {du.stdout.split()[0] if du.stdout else "?"}'
          '  (clonata: sul disco pesa quasi nulla finche non si modifica)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
