"""R16: the repair of the proofs that the whole-proof brake refuses (4 October 2026).

Twin of ``tools/ripara_prova.py`` (frozen copy ``versioni/R16/ripara_prova.py``), same logic.

A supported sentence or a surrounding-page proof that R14 finds (its first 60 characters) and R16 does not (it is not
whole in the page) is not invented from scratch: the beginning is true, the rest the model summarised, shortened,
reassembled or completed. Instead of calling it "not found", the TRUE sentence of the filing the model started from is
taken from the text:

1. the text: the page (without the marks of the system and of the context) joined to the next page;
2. the true stretches: the stretches of the proof, of at least 20 characters, that are in the text (compared on letters
   and digits, lower case, accents recomposed), each with its position in the text;
3. one place of the filing: stretches close to each other (gaps of at most 400 characters, in page order) make a group;
   if the proof is reassembled from two distant places, the group carrying the mention of the case (the name marked
   with the double brackets, or the mark of its footnote) is kept, otherwise the one with more true text, the first on
   a tie;
4. the sentence: from the sentence boundary before the group to the one after it, with the sentence cut of R15
   (:func:`tracepipe.frase_sostenuta.confini`, which knows "para.", "art.", "v.", "Rn.", footnote marks); if the group
   spans several sentences, all of them, in the order of the filing;
5. no true stretch of 20 characters: the proof stays "not found" (really invented). A sentence the cut cannot close
   (more than 200 words, fewer than 4) stays "not found" too: nothing is guessed.

The reasons are Italian strings because they are data written into the rows.
"""

from __future__ import annotations

import itertools
import re
import unicodedata

from . import frase_sostenuta as fs
from .prova_intera import _SEGNI, _SEGNI_CONTESTO, FreniProvaIntera

TRATTO = 20
SALTO_GRUPPO = 400
NOME = re.compile(r'⟦([^⟧]*)⟧')


def _pulito(t):
    """the text of the filing without the marks of the passage and of the context (positions of the clean text)"""
    t = unicodedata.normalize('NFC', str(t or ''))
    t = _SEGNI.sub('', t)
    return _SEGNI_CONTESTO.sub('\n', t)


def _compatto(t):
    """letters and digits in lower case, with the position of each in the text"""
    c, pos = [], []
    for i, ch in enumerate(t):
        if ch.isalnum():
            c.append(ch.lower())
            pos.append(i)
    return ''.join(c), pos


def _tratti(pc, tc):
    """[(start in the proof, start in the text, length)]: the true stretches, the longest from the left"""
    out, i, m = [], 0, len(pc)
    while i < m:
        lo, hi = TRATTO, m - i
        if hi < lo:
            break
        da = tc.find(pc[i : i + lo])
        if da < 0:
            i += 1
            continue
        while lo < hi:
            mm = (lo + hi + 1) // 2
            if tc.find(pc[i : i + mm]) >= 0:
                lo = mm
            else:
                hi = mm - 1
        out.append((i, tc.find(pc[i : i + lo]), lo))
        i += lo
    return out


def _gruppi(tratti, pos):
    g, cur = [], []
    for t in sorted(tratti, key=lambda x: x[1]):
        if cur and pos[t[1]] - pos[cur[-1][1] + cur[-1][2] - 1] > SALTO_GRUPPO:
            g.append(cur)
            cur = []
        cur.append(t)
    if cur:
        g.append(cur)
    return g


def _menzione(testo_orig):
    """where the mention of the case is in the clean text: the name marked ⟦ ⟧ (position in the text with the
    marks removed)"""
    t = unicodedata.normalize('NFC', str(testo_orig or ''))
    m = NOME.search(t)
    if not m:
        return None, ''
    prima = _pulito(t[: m.start()])
    return len(prima), m.group(1)


def ripara(prova, testo_pagina, seguito=''):
    """-> dict(esito='riparata'|'non trovata', frase, tratti, gruppi, motivo). It is tried first on the BODY of the text
    (without the footnote lines, so the sentence continues past the footnote block and past the page break); if without
    the footnotes the true stretches are fewer (a body line starting with a paragraph number looks like a footnote), on
    the whole text."""
    pc, _ = _compatto(_pulito(prova))
    if len(pc) < TRATTO:
        return {'esito': 'non trovata', 'frase': '', 'motivo': 'prova troppo corta'}
    scelte = []
    for corpo in (True, False):
        base = _pulito(testo_pagina)
        seg = _pulito(seguito) if seguito else ''
        if corpo:
            base, seg = FreniProvaIntera.senza_note(base), FreniProvaIntera.senza_note(seg)
        testo = base + ('\n' + seg if seg else '')
        tc, pos = _compatto(testo)
        tr = _tratti(pc, tc)
        scelte.append((sum(x[2] for x in tr), corpo, base, testo, tc, pos, tr))
    _, corpo, base, testo, tc, pos, tr = max(scelte, key=lambda x: (x[0], x[1]))
    if not tr:
        return {'esito': 'non trovata', 'frase': '', 'motivo': 'nessun tratto vero di 20 caratteri'}
    gr = _gruppi(tr, pos)
    dove, nome = _menzione(testo_pagina)

    def peso(g):
        a, b = pos[g[0][1]], pos[g[-1][1] + g[-1][2] - 1]
        vicino = dove is not None and a - 600 <= dove <= b + 600
        return (vicino, sum(x[2] for x in g), -a)

    scelto = max(gr, key=peso)
    incerta = []
    # THE SENTENCES REASSEMBLED IN REVERSE (NEU-1406, 04/10/2026): in the group the stretches are in page order; if in
    # the proof they come in another order, the model has reassembled two sentences. The stretches in the right order
    # with the most text are kept (the heaviest increasing subsequence) and the repair is uncertain.
    ordine = sorted(scelto, key=lambda x: x[1])
    if any(y[0] < x[0] for x, y in itertools.pairwise(ordine)):
        migliore = {}
        for k, x in enumerate(ordine):
            prima = [migliore[j] for j in range(k) if ordine[j][0] < x[0]]
            base_k = max(prima, key=lambda m: m[0]) if prima else (0, [])
            migliore[k] = (base_k[0] + x[2], base_k[1] + [x])
        scelto = max(migliore.values(), key=lambda m: m[0])[1]
        incerta.append('frase rimontata dal modello in un altro ordine')
    a = pos[scelto[0][1]]
    b = pos[scelto[-1][1] + scelto[-1][2] - 1] + 1
    tg = fs.confini(testo)
    inizio = max([x for x in tg if x <= a] or [0])
    fine = min([x for x in tg if x >= b] or [len(testo)])
    # THE PAGE BREAK MID-SENTENCE (NEU-1030, 04/10/2026): the sentence reaches the bottom of the page without closing
    # and its continuation is not among the true stretches of the next page (the next page starts with something else:
    # header, footnote, a sentence that has nothing to do with it). It is cut at the end of the page and the repair is
    # uncertain: the continuation cannot be confirmed.
    if seg and b <= len(base) < fine:
        fine = len(base)
        incerta.append('la frase continua oltre la pagina e il seguito non si ritrova')
    coperti = sum(x[2] for x in scelto)
    if coperti < 0.6 * len(pc):
        incerta.append(f"la frase dell'atto copre solo {100 * coperti // len(pc)}% della prova")
    # THE GAPS OF THE PAGE BETWEEN TWO TRUE STRETCHES that start with a number (a block of footnotes, the page number
    # with the continuation on the next page: «... verplicht is om 288 Urgenda, 5.2.4. 289 ... 163 tegen dit gevaar»)
    # are not the sentence: they are removed. The rest of the sentence stays as it is in the filing.
    via = []
    ordinati = sorted(scelto, key=lambda x: x[1])
    for x, y in itertools.pairwise(ordinati):
        e = pos[x[1] + x[2] - 1] + 1
        s2 = pos[y[1]]
        salto = testo[e:s2]
        if len(salto) > 12 and re.match(r'\s*[(\[]?\d', salto):
            via.append((e, s2))
    pezzo = ''
    k = inizio
    for e, s2 in via:
        pezzo += testo[k:e] + ' '
        k = s2
    pezzo += testo[k:fine]
    pezzo, _ = fs._togli_etichetta(pezzo)
    frase = fs.ricuci(pezzo).strip()
    frase = re.sub(r'([.!?]\]?[”"’»)]*)\d{1,3}$', r'\1', frase)
    parole = (
        len([w for w in frase.split() if re.search(r'[^\W\d_]', w)]) if not fs._CJK.search(frase) else len(frase) // 2
    )
    if parole > fs.MAX_PAROLE or parole < fs.MIN_PAROLE:
        return {'esito': 'non trovata', 'frase': '', 'motivo': f'frase di {parole} parole: taglio incerto'}
    return {
        'esito': 'riparata',
        'frase': frase,
        'gruppi': len(gr),
        'tratti': len(tr),
        'nome': nome,
        'incerta': '; '.join(incerta),
        'dalla_pagina_dopo': inizio >= len(base),
        'senza_note': corpo,
        'salti_tolti': len(via),
        'motivo': '',
    }
