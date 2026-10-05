"""LA RIPARAZIONE DELLE PROVE CHE R16 RESPINGE (04/10/2026, il PI: riparare invece di «non trovata»; per ora solo prova a
secco, niente scritto in banca dati).

   Una frase sostenuta o una prova delle pagine attorno che R14 trova (i primi 60 caratteri) e R16 no (non sta tutta nella
   pagina) non e' inventata da capo: l'inizio e' vero, il resto il modello l'ha riassunto, accorciato, rimontato o
   completato. Invece di darla «non trovata», si prende dal testo dell'atto la frase VERA da cui il modello e' partito:
     1. il testo: la pagina (senza i segni del sistema e del contesto) unita alla pagina dopo;
     2. i tratti veri: i tratti della prova, di almeno 20 caratteri, che stanno nel testo (confronto su lettere e cifre, in
        minuscolo, accenti ricomposti), ciascuno con la sua posizione nel testo;
     3. un solo punto dell'atto: i tratti vicini fra loro (salti di al massimo 400 caratteri, l'ordine della pagina) fanno
        un gruppo; se la prova e' rimontata da due punti lontani si tiene il gruppo che porta la menzione del caso (il nome
        segnato ⟦ ⟧ o il richiamo della sua nota), se no quello con piu' testo vero, a parita' il primo;
     4. la frase: dal confine di frase prima del gruppo al confine dopo, con il taglio delle frasi di R15
        (`frase_sostenuta.confini`, che conosce «para.», «art.», «v.», «Rn.», i richiami di nota); se il gruppo scavalca
        piu' frasi, le prende tutte, nell'ordine dell'atto;
     5. nessun tratto vero di 20 caratteri: la prova resta «non trovata» (inventata davvero). Una frase che il taglio non
        sa chiudere (oltre 200 parole, meno di 4) resta «non trovata» anche lei: niente a indovinare.
   La riga riparata porterebbe `frase_riparata: true` e il testo del modello in `frase_originale_modello` (reversibile).
"""
from __future__ import annotations

import re
import sys
import unicodedata
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import frase_sostenuta as FS  # noqa: E402
import freni as F  # noqa: E402

TRATTO = 20
SALTO_GRUPPO = 400
NOME = re.compile(r'⟦([^⟧]*)⟧')


def _pulito(t):
    """il testo dell'atto senza i segni del brano e del contesto (posizioni del testo pulito)"""
    t = unicodedata.normalize('NFC', str(t or ''))
    t = F._SEGNI.sub('', t)
    return F._SEGNI_CONTESTO.sub('\n', t)


def _compatto(t):
    """lettere e cifre in minuscolo, con la posizione di ciascuna nel testo"""
    c, pos = [], []
    for i, ch in enumerate(t):
        if ch.isalnum():
            c.append(ch.lower()); pos.append(i)
    return ''.join(c), pos


def _tratti(pc, tc):
    """[(inizio nella prova, inizio nel testo, lunghezza)]: i tratti veri, il piu' lungo da sinistra"""
    out, i, m = [], 0, len(pc)
    while i < m:
        lo, hi = TRATTO, m - i
        if hi < lo:
            break
        da = tc.find(pc[i:i + lo])
        if da < 0:
            i += 1
            continue
        while lo < hi:
            mm = (lo + hi + 1) // 2
            if tc.find(pc[i:i + mm]) >= 0:
                lo = mm
            else:
                hi = mm - 1
        out.append((i, tc.find(pc[i:i + lo]), lo))
        i += lo
    return out


def _gruppi(tratti, pos):
    g, cur = [], []
    for t in sorted(tratti, key=lambda x: x[1]):
        if cur and pos[t[1]] - pos[cur[-1][1] + cur[-1][2] - 1] > SALTO_GRUPPO:
            g.append(cur); cur = []
        cur.append(t)
    if cur:
        g.append(cur)
    return g


def _menzione(testo_orig):
    """dove sta la menzione del caso nel testo pulito: il nome segnato ⟦ ⟧ (posizione nel testo con i segni tolti)"""
    t = unicodedata.normalize('NFC', str(testo_orig or ''))
    m = NOME.search(t)
    if not m:
        return None, ''
    prima = _pulito(t[:m.start()])
    return len(prima), m.group(1)


def ripara(prova, testo_pagina, seguito=''):
    """-> dict(esito='riparata'|'non trovata', frase, tratti, gruppi, motivo). Si prova prima sul CORPO del testo (senza le
    righe di nota, cosi' la frase continua oltre il blocco delle note e oltre il salto di pagina); se senza le note i tratti
    veri sono meno (una riga del corpo che comincia con un numero di paragrafo sembra una nota), sul testo intero."""
    pc, _ = _compatto(_pulito(prova))
    if len(pc) < TRATTO:
        return {'esito': 'non trovata', 'frase': '', 'motivo': 'prova troppo corta'}
    scelte = []
    for corpo in (True, False):
        base = _pulito(testo_pagina)
        seg = _pulito(seguito) if seguito else ''
        if corpo:
            base, seg = F._senza_note(base), F._senza_note(seg)
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
    # LE FRASI RIMONTATE ALL'INCONTRARIO (NEU-1406, 04/10/2026): nel gruppo i tratti stanno nell'ordine della pagina; se
    # nella prova vengono in un altro ordine, il modello ha rimontato due frasi. Si tengono i tratti nell'ordine giusto con
    # piu' testo (la sottosequenza crescente piu' pesante) e la riparazione e' incerta.
    ordine = sorted(scelto, key=lambda x: x[1])
    if any(y[0] < x[0] for x, y in zip(ordine, ordine[1:])):
        migliore = {}
        for k, x in enumerate(ordine):
            prima = [migliore[j] for j in range(k) if ordine[j][0] < x[0]]
            base_k = max(prima, key=lambda m: m[0]) if prima else (0, [])
            migliore[k] = (base_k[0] + x[2], base_k[1] + [x])
        scelto = max(migliore.values(), key=lambda m: m[0])[1]
        incerta.append('frase rimontata dal modello in un altro ordine')
    a = pos[scelto[0][1]]
    b = pos[scelto[-1][1] + scelto[-1][2] - 1] + 1
    tg = FS.confini(testo)
    inizio = max([x for x in tg if x <= a] or [0])
    fine = min([x for x in tg if x >= b] or [len(testo)])
    # IL SALTO DI PAGINA A META' FRASE (NEU-1030, 04/10/2026): la frase arriva in fondo alla pagina senza chiudersi e il
    # suo seguito non e' fra i tratti veri della pagina dopo (la pagina dopo comincia con altro: testata, nota, una frase
    # che non c'entra). Si taglia alla fine della pagina e la riparazione e' incerta: il seguito non si puo' confermare.
    if seg and b <= len(base) < fine:
        fine = len(base)
        incerta.append('la frase continua oltre la pagina e il seguito non si ritrova')
    coperti = sum(x[2] for x in scelto)
    if coperti < 0.6 * len(pc):
        incerta.append(f'la frase dell\'atto copre solo {100 * coperti // len(pc)}% della prova')
    # I SALTI DELLA PAGINA FRA DUE TRATTI VERI che cominciano con un numero (un blocco di note, il numero di pagina col
    # seguito sulla pagina dopo: «... verplicht is om 288 Urgenda, 5.2.4. 289 ... 163 tegen dit gevaar») non sono la
    # frase: si tolgono. Il resto della frase resta com'e' nell'atto.
    via = []
    ordinati = sorted(scelto, key=lambda x: x[1])
    for x, y in zip(ordinati, ordinati[1:]):
        e = pos[x[1] + x[2] - 1] + 1; s2 = pos[y[1]]
        salto = testo[e:s2]
        if len(salto) > 12 and re.match(r'\s*[(\[]?\d', salto):
            via.append((e, s2))
    pezzo = ''
    k = inizio
    for e, s2 in via:
        pezzo += testo[k:e] + ' '
        k = s2
    pezzo += testo[k:fine]
    pezzo, _ = FS._togli_etichetta(pezzo)
    frase = FS.ricuci(pezzo).strip()
    frase = re.sub(r'([.!?]\]?[”"’»)]*)\d{1,3}$', r'\1', frase)
    parole = len([w for w in frase.split() if re.search(r'[^\W\d_]', w)]) if not FS._CJK.search(frase) else len(frase) // 2
    if parole > FS.MAX_PAROLE or parole < FS.MIN_PAROLE:
        return {'esito': 'non trovata', 'frase': '', 'motivo': f'frase di {parole} parole: taglio incerto'}
    return {'esito': 'riparata', 'frase': frase, 'gruppi': len(gr), 'tratti': len(tr), 'nome': nome,
            'incerta': '; '.join(incerta),
            'dalla_pagina_dopo': inizio >= len(base), 'senza_note': corpo, 'salti_tolti': len(via), 'motivo': ''}
