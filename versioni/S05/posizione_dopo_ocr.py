"""LE POSIZIONI DELLE RIGHE NEI DOCUMENTI RIFATTI CON L'OCR (01/10/2026).

   Perche'. L'1/10 l'OCR ha sostituito 127 pagine illeggibili in sei documenti (training/ocr/pagine_sostituite.json).
   Il testo nuovo ha una lunghezza diversa, quindi nei file markdown di quei sei documenti la posizione di una riga
   (`char_start`) scritta PRIMA dell'OCR non punta piu' al nome citato. `char_start` fa parte dell'id della riga,
   quindi in banca dati NON si cambia: si traduce qui, ogni volta che un passo deve ritrovare il nome nel file.

   Come. La copia di prima sta in training/ocr/prima/<file>. Dalla posizione vecchia si ricava la pagina e lo scarto
   dentro la pagina. Se la pagina non e' cambiata, la posizione nuova e' inizio della pagina nuova + lo stesso scarto.
   Se la pagina e' stata rifatta, si cerca il nome nella pagina nuova: la stessa occorrenza in ordine (la seconda
   resta la seconda), altrimenti la prima; se il nome non c'e' si torna l'inizio della pagina e lo si dice.
   Le righe nate dopo l'OCR (provenienza.ocr) hanno gia' la posizione nuova e non si toccano.

   Uso:  from posizione_dopo_ocr import traduci
         cs, come = traduci(file, char_start, nome_re, nata_dopo_ocr)
"""
import pathlib, re
QUI = pathlib.Path(__file__).resolve().parent.parent
PRIMA = QUI/'training'/'ocr'/'prima'
PAGE_RE = re.compile(r'<!--\s*page\s+(\d+)\s*-->')


def _pagine(testo):
    m = [(x.start(), int(x.group(1))) for x in PAGE_RE.finditer(testo)]
    return [(a, (m[i+1][0] if i + 1 < len(m) else len(testo)), n) for i, (a, n) in enumerate(m)]


def traduci(file, cs, nome_re, nata_dopo_ocr=False):
    """(posizione nel file di oggi, come e' stata trovata)."""
    vecchio = PRIMA/pathlib.Path(file).name
    if nata_dopo_ocr or not vecchio.exists():
        return cs, 'invariata'
    tv = vecchio.read_text(encoding='utf-8', errors='replace')
    tn = (QUI/file).read_text(encoding='utf-8', errors='replace')
    pv = [p for p in _pagine(tv) if p[0] <= cs]
    if not pv:                       # prima del primo segno di pagina: il testo li' non e' cambiato
        return cs, 'prima delle pagine'
    a, b, n = pv[-1]
    nuove = {p[2]: p for p in _pagine(tn)}
    if n not in nuove:
        return cs, f'pagina {n} assente nel file nuovo'
    na, nb, _ = nuove[n]
    if tv[a:b] == tn[na:nb]:
        return na + (cs - a), 'stessa pagina, spostata'
    k = len(list(nome_re.finditer(tv, a, cs)))      # quante occorrenze del nome vengono prima, nella pagina vecchia
    occ = list(nome_re.finditer(tn, na, nb))
    if not occ:
        return na, f'pagina {n} rifatta, nome non ritrovato'
    return (occ[k] if k < len(occ) else occ[0]).start(), f'pagina {n} rifatta, nome ritrovato'
