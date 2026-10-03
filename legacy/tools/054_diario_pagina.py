"""LA PAGINA DEL DIARIO E DEL DOCUMENTO UNICO (29/09/2026, richiesta del PI).

   Il PI vuole il diario «sempre aperto accanto», non sepolto in un file di 4.000 righe. Questa pagina mette
   insieme, interi, i due documenti che si scrivono sempre tutti e due:
     - il diario, `sabin-corpus/METODO-RECUPERO.md`: in cima l'ultima voce, poi indietro;
     - il documento unico, `climpact-drp/docs/TRACE-RIFERIMENTO-COMPLETO.md`: nell'ordine del documento, con in cima
       le ultime sezioni aggiunte.
   Indice a sinistra, ricerca su tutti e due. Si rigenera e si ripubblica (stessa pagina privata su claude.ai)
   ogni volta che uno dei due file cambia.

   Uso:  .venv/bin/python tools/054_diario_pagina.py   -> pubblicazione/diario/diario.html
"""
import datetime, json, pathlib, re
QUI = pathlib.Path(__file__).resolve().parent.parent
DIARIO = QUI/'METODO-RECUPERO.md'
UNICO = pathlib.Path.home()/'climpact-drp'/'docs'/'TRACE-RIFERIMENTO-COMPLETO.md'
USCITA = QUI/'pubblicazione'/'diario'/'diario.html'


def voci(testo):
    """Il documento in voci: una per titolo di livello 2 o 3, fuori dai blocchi di codice."""
    out, parte, capitolo, cur, dentro = [], '', '', None, False
    for riga in testo.splitlines():
        if riga.startswith('```'):
            dentro = not dentro
        m = None if dentro else re.match(r'^(#{1,3}) (.+)$', riga)
        if m and len(m.group(1)) == 1:
            parte = m.group(2).strip()
            if cur:
                out.append(cur); cur = None
            continue
        if m:
            if cur:
                out.append(cur)
            titolo = m.group(2).strip()
            if len(m.group(1)) == 2:
                capitolo = titolo
            cur = {'livello': len(m.group(1)), 'titolo': titolo, 'parte': parte,
                   'capitolo': capitolo if len(m.group(1)) == 3 else '', 'testo': ''}
            continue
        if cur is None:
            cur = {'livello': 2, 'titolo': 'Introduzione', 'parte': parte, 'capitolo': '', 'testo': ''}
        cur['testo'] += riga + '\n'
    if cur:
        out.append(cur)
    for i, v in enumerate(out):
        v['id'] = f'v{i}'
        d = re.search(r'\((\d{1,2} [a-z]+(?: \d{4})?|[^()]*\d{1,2}/\d{1,2}/\d{4})[^()]*\)\s*$', v['titolo'])
        v['quando'] = d.group(1) if d else ''
    return out


def main():
    d = voci(DIARIO.read_text(encoding='utf-8'))
    u = voci(UNICO.read_text(encoding='utf-8'))
    dati = {'diario': d, 'unico': u, 'generata': datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}
    js = json.dumps(dati, ensure_ascii=False).replace('</', '<\\/')
    modello = (QUI/'tools'/'diario_pagina.html').read_text(encoding='utf-8')
    USCITA.parent.mkdir(parents=True, exist_ok=True)
    USCITA.write_text(modello.replace('/*DATI*/null', js), encoding='utf-8')
    print(f'diario {len(d)} voci, documento unico {len(u)} voci -> {USCITA} ({USCITA.stat().st_size // 1024} KB)')


if __name__ == '__main__':
    main()
