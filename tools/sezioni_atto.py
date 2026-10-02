"""L'ALBERO DELLE SEZIONI DI UN ATTO, SENZA MODELLO (29/09/2026, prova tipo PageIndex).

   PageIndex (VectifyAI) costruisce l'indice di un documento lungo e ci naviga dentro. Per TRACE serve a una cosa
   precisa: dire se la pagina con punteggio alto sta nella STESSA SEZIONE della citazione (seguito vero) o altrove
   (stesso tema). Solo 67 dei 314 atti che citano Urgenda hanno l'indice dentro il PDF; per gli altri lo si ricava
   dai titoli: righe brevi in un carattere piu' grande del corpo, o in grassetto e numerate («V.1.2», «A.», «3.»).
   Lo si misura sugli atti che l'indice ce l'hanno: quanti titoli veri ritrova e quanti ne inventa.

   Uso:  .venv/bin/python tools/sezioni_atto.py misura      (titoli ricavati contro l'indice del PDF)
         .venv/bin/python tools/sezioni_atto.py finestra    (pagine alte: stessa sezione della citazione?)
"""
import collections, glob, json, pathlib, re, statistics, sys
import fitz
QUI = pathlib.Path(__file__).resolve().parent.parent
T = QUI/'training'

NUMERO = re.compile(r'^\s*((\d+(\.\d+)*\.?)|([IVXLC]+\.)|([A-Z]\.)|(\([a-z0-9]+\))|(§\s*\d+))\s+\S')


def titoli(pdf):
    """[(livello, titolo, pagina)] come get_toc(). Livello 1 = carattere piu' grande fra i titoli."""
    doc = fitz.open(pdf)
    righe, corpi = [], []
    for n, pg in enumerate(doc, 1):
        for b in pg.get_text('dict')['blocks']:
            for l in b.get('lines', []):
                sp = [s for s in l['spans'] if s['text'].strip()]
                if not sp:
                    continue
                t = ' '.join(s['text'].strip() for s in sp)
                size = max(s['size'] for s in sp)
                bold = all(('Bold' in s['font']) or (s['flags'] & 16) for s in sp)
                corpi += [round(x['size'], 1) for x in sp for _ in x['text']]
                righe.append((n, t, round(size, 1), bold))
    if not corpi:
        return []
    corpo = statistics.mode(corpi)
    out = []
    for n, t, size, bold in righe:
        parole = len(t.split())
        if parole == 0 or parole > 14 or t.endswith((',', ';')) or re.fullmatch(r'[\d\s./-]+', t):
            continue
        grande = size >= corpo * 1.15
        numerato = bool(NUMERO.match(t))
        if grande and (bold or numerato or t.isupper()) or (bold and numerato):
            out.append((size, t, n))
    if not out:
        return []
    taglie = sorted({s for s, _, _ in out}, reverse=True)
    return [(min(taglie.index(s) + 1, 3), t, n) for s, t, n in out]


def sezione(toc, p, livello=None):
    best = None
    for i, (lv, _, pg) in enumerate(toc):
        if livello and lv > livello:
            continue
        if pg <= p:
            best = i
    return best


def pdf_di():
    F = json.load(open(T/'fase2'/'urgenda_corpus_rows_2026-09-26.json'))
    return {x['document_id']: QUI/x['file_pdf'] for x in F if x.get('file_pdf')}


def misura():
    R = [json.loads(l) for l in open(T/'lessicali_urgenda_righe.jsonl')]
    P = pdf_di()
    ok = trovati = veri = inventati = 0
    for d in sorted({r['document_id'] for r in R}):
        if d not in P or not P[d].exists():
            continue
        vero = fitz.open(P[d]).get_toc()
        if len(vero) < 3:
            continue
        mio = titoli(P[d])
        pv = {(pg) for _, _, pg in vero}
        pm = {(pg) for _, _, pg in mio}
        ok += 1
        veri += len(pv); trovati += len(pv & pm); inventati += len(pm - pv)
    print(f'atti con indice: {ok}; pagine con un titolo vero {veri}, ritrovate {trovati} ({trovati / max(veri, 1):.0%}); '
          f'pagine con titoli ricavati che l\'indice non ha {inventati}')


if __name__ == '__main__':
    {'misura': misura}[sys.argv[1]]()
