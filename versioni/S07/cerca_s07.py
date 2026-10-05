#!/usr/bin/env python3
"""LA RICERCA PER NOME S07 (04/10/2026, il PI: «sistemare tutto con urgenza estrema ogni buco trovato»).

    python tools/cerca_s07.py --caso cited-cases/neubauer-S07.yaml --uscita index/nomi_neubauer_2026-10-04-S07.csv

E' `cerca_s05_per_atto.main` (la ricerca S05 con la deduplica per atto), con tre cose diverse, tutte trovate dalla
revisione del 04/10/2026 (scratchpad della sessione, audit/fuse, audit/dedup, audit/forme):

  1. I GRUPPI NON ATTRAVERSANO LE NOTE A PIE' DI PAGINA (`fondi`, regola 3, ora in tutte le copie: cerca.py,
     cerca_s05.py, cerca_s05_per_atto.py, tracepipe/ricerca.py). Prima due note consecutive a meno di 200 caratteri
     («157 BVerfG, Beschluss ... Rn. 198. 158 BVerfG, Beschluss ... Rn. 198.») diventavano una riga sola: ~740
     citazioni nascoste.
  2. LA DEDUPLICA BUTTA UNA COPIA SOLO NELLO STESSO ATTO E SULLA STESSA PAGINA (`deduplica`): lo strato di testo doppio
     di un PDF. Ogni altra copia resta con `stesso_testo_di`. Prima si buttava anche una copia su un'altra pagina dello
     stesso atto: 6 citazioni vere su 13, fra cui i tre ordini del DISPOSITIVO della sentenza Agapan (pp. 145-146).
  3. LE FORME SEMPLICI CHE MANCAVANO (`forme_s07_aggiunte` del file del caso -S07: «NL:RBDHA:2015:7145/7196» senza
     ECLI, «Advisory Opinion, ICJ»), cercate come le altre forme.

La rete descrittiva (le pagine che citano la pronuncia senza nessuna forma) e' un'ALTRA rete, in
`tools/rete_descrittiva.py`, con le regole dichiarate nello stesso file -S07 del caso. Le corrispondenze di S03 restano
identiche (l'ancora: `cited-cases/ancora-S03/<caso>.yaml`), quindi le righe gia' in piattaforma si ritrovano allo
stesso identificativo. Il confronto con la piattaforma e le righe nuove: `tools/recupero_s07.py`.
"""
import sys
from pathlib import Path

QUI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI / 'tools'))
sys.path.insert(0, str(QUI))
import cerca_s05_per_atto as BASE  # noqa: E402

_leggi_caso = BASE.leggi_caso


def leggi_caso(percorso, con_alternative=False):
    """`leggi_caso` di S05 piu' le forme di `forme_s07_aggiunte` (in coda alle forme, cosi' l'ordine di S05 resta)."""
    import yaml
    percorso = Path(percorso)
    conf = _leggi_caso(percorso, con_alternative)
    dati = yaml.safe_load(Path(percorso).read_text(encoding='utf-8')) or {}
    nuove = [str(f).strip() for f in (dati.get('forme_s07_aggiunte') or []) if str(f).strip()]
    conf['forme'] = list(dict.fromkeys(conf['forme'] + nuove))
    conf['forme_s07_aggiunte'] = nuove
    return conf


BASE.leggi_caso = leggi_caso
fondi = BASE.fondi
deduplica = BASE.deduplica
confine_di_nota = BASE.confine_di_nota
main = BASE.main

def limita_ai_file(elenco):
    """S07 A LOTTI (04/10/2026): la rete lessicale legge solo i Markdown dell'elenco (i documenti nuovi di D05, o le
    copie rifatte con l'OCR in training/d05/markdown_ocr/), come cerca_d04.py"""
    originale = BASE.rete_lessicale
    BASE.rete_lessicale = lambda *a, **k: originale(*a, **{**k, 'file': list(elenco)})


if __name__ == '__main__':
    import giornale  # il giornale delle operazioni: ogni esecuzione, i file, le scritture, gli errori
    giornale.avvia()
    if '--file-elenco' in sys.argv:
        import json
        i = sys.argv.index('--file-elenco')
        limita_ai_file(json.load(open(sys.argv[i + 1], encoding='utf-8')))
        del sys.argv[i:i + 2]
    raise SystemExit(main())
