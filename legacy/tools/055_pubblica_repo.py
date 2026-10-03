"""IL REPOSITORY PUBBLICATO, CON GLI STRUMENTI NUMERATI IN ORDINE DI LETTURA (02/10/2026, il PI: «i singoli codici devono
avere il numero avanti per capire l'ordine»).

   Sul Mac gli strumenti tengono il loro nome: li chiamano le catene in corso, ReCaS e il registro, e in Python un modulo
   che comincia con una cifra non si importa con `import`. Nel repository (github.com/climpact-project/trace) e nello zip
   del codice ogni file prende invece il suo numero, nell'ordine di `tools/ordine/LEGGIMI.md` (fasi: corpus, caso citato,
   ricerca per nome, tipo, principio e pagine attorno, controlli, riprese senza nome, misure, pubblicazione, cicli,
   storia). Perche' il codice pubblicato funzioni lo stesso:
     - `import cerca` diventa `cerca = __import__('016_cerca')`, `from freni import leggibile` diventa
       `_m_freni = __import__('033_freni')` e `leggibile = _m_freni.leggibile` (stessa indentazione);
     - ogni nome di file `X.py` nei commenti, nelle istruzioni d'uso e negli script di shell diventa `NNN_X.py`.
   Le copie congelate del registro (`versioni/`) restano coi nomi di allora: sono quello che e' girato. Alla fine si
   compila ogni file e si importano i moduli che non chiedono librerie esterne, dal repository.

   Uso:  .venv/bin/python tools/055_pubblica_repo.py [--repo ~/trace-repo]
"""
import argparse, pathlib, py_compile, re, shutil, subprocess, sys
QUI = pathlib.Path(__file__).resolve().parent.parent
T = QUI/'tools'


def ordine():
    """nome -> numero, dall'elenco di tools/ordine/LEGGIMI.md"""
    out = {}
    for l in (T/'ordine'/'LEGGIMI.md').read_text(encoding='utf-8').splitlines():
        m = re.match(r"- `(\d{3})_(.+)`", l)
        if m:
            out[m.group(2)] = f'{m.group(1)}_{m.group(2)}'
    return out


def riscrivi(testo, mappa):
    moduli = {k[:-3]: v[:-3] for k, v in mappa.items() if k.endswith('.py')}
    righe, out, i = testo.split('\n'), [], 0
    while i < len(righe):
        r = righe[i]
        m = re.match(r'^(\s*)from\s+([A-Za-z_]\w*)\s+import\s+(.*)$', r)
        if m and m.group(2) in moduli:
            ind, mod, resto = m.groups()
            resto = re.sub(r'\s+#.*$', '', resto)
            if resto.startswith('(') and ')' not in resto:
                while ')' not in resto:
                    i += 1; resto += ' ' + re.sub(r'\s+#.*$', '', righe[i].strip())
            nomi = [x.strip() for x in resto.strip('() ').split(',') if x.strip()]
            out.append(f"{ind}_m_{mod} = __import__('{moduli[mod]}')")
            for n in nomi:
                a, _, b = n.partition(' as ')
                out.append(f"{ind}{(b or a).strip()} = _m_{mod}.{a.strip()}")
            i += 1; continue
        m = re.match(r'^(\s*)import\s+([^#]+?)(\s+#.*)?$', r)
        if m and any(x.strip().split(' as ')[0].strip() in moduli for x in m.group(2).split(',')):
            ind, voci = m.group(1), [x.strip() for x in m.group(2).split(',')]
            altri, nostri = [], []
            for v in voci:
                a, _, b = v.partition(' as ')
                a, b = a.strip(), b.strip()
                (nostri if a in moduli else altri).append((a, b))
            if altri:
                out.append(ind + 'import ' + ', '.join(a + (f' as {b}' if b else '') for a, b in altri))
            for a, b in nostri:
                out.append(f"{ind}{b or a} = __import__('{moduli[a]}')")
            i += 1; continue
        out.append(r); i += 1
    testo = '\n'.join(out)
    # i nomi dei file nei testi (commenti, istruzioni d'uso, script di shell), in una passata sola
    nomi = sorted(mappa, key=len, reverse=True)
    patt = re.compile(r'(?<![\w/.-])(tools/(?:ordine/)?)?(' + '|'.join(re.escape(n) for n in nomi) + r')(?![\w])')
    return patt.sub(lambda m: (m.group(1) or '').replace('ordine/', '') + mappa[m.group(2)], testo)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--repo', default=str(pathlib.Path.home()/'trace-repo')); a = ap.parse_args()
    R = pathlib.Path(a.repo); mappa = ordine()
    assert mappa, 'manca tools/ordine/LEGGIMI.md'
    shutil.rmtree(R/'tools', ignore_errors=True); (R/'tools').mkdir()
    for nome, numerato in mappa.items():
        src = T/nome
        testo = src.read_text(encoding='utf-8')
        (R/'tools'/numerato).write_text(riscrivi(testo, mappa), encoding='utf-8')
        if nome.endswith('.sh'):
            (R/'tools'/numerato).chmod(0o755)
    leggimi = (T/'ordine'/'LEGGIMI.md').read_text(encoding='utf-8')
    leggimi = re.sub(r"I file veri stanno in .*?\n", "Ogni file porta davanti il suo numero nell'ordine di lettura. Sul Mac del gruppo gli stessi file hanno il nome senza numero (li chiamano le catene in corso); qui gli import sono riscritti per i nomi numerati, e le copie del registro in `versioni/` restano coi nomi di quando sono girate.\n", leggimi, flags=re.S)
    (R/'tools'/'LEGGIMI.md').write_text(leggimi, encoding='utf-8')
    for cartella, escludi in (('cited-cases', ('.bak', 'proposte-')), ('codebook', ()), ('versioni', ())):
        shutil.rmtree(R/cartella, ignore_errors=True)
        shutil.copytree(QUI/cartella, R/cartella, ignore=lambda d, fs: [f for f in fs if f.startswith('Icon') or any(e in f for e in escludi)])
    # controlli: ogni file compila; i moduli senza librerie esterne si importano dal repository
    errori = []
    for f in sorted((R/'tools').glob('*.py')):
        try:
            compile(f.read_text(encoding='utf-8'), str(f), 'exec')
        except SyntaxError as e:
            errori.append(f'{f.name}: riga {e.lineno} {e.msg}')
    prova = ("import sys; sys.path.insert(0, 'tools'); "
             + '; '.join(f"__import__('{mappa[n][:-3]}')" for n in ('011_sonde.py', '034_freni.py', '006_posizione_dopo_ocr.py', '016_cerca.py')))
    r = subprocess.run([sys.executable, '-c', prova], cwd=R, capture_output=True, text=True)
    print('file', len(mappa), '| errori di compilazione', len(errori), '| prova di import', 'ok' if r.returncode == 0 else r.stderr[-400:])
    for e in errori:
        print('  ', e)
    return 0 if not errori and r.returncode == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
