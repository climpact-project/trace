"""IL REGISTRO UNICO DEI CASI CITATI (06/10/2026). Legge cited-cases/casi.yaml: e' l'unico posto dove sta l'elenco dei
casi di TRACE e i loro attributi (prefisso dei codici, serie delle sonde, soglia di D05, codice della mappa...).
Prima la lista dei sei casi era scritta dentro una cinquantina di file; ora gli strumenti fanno `import
casi_registro as CR` e usano CR.CASI, CR.PREFISSI, CR.PRIMA_SERIE, CR.SERIE_IN_USO, CR.SOGLIE_D05, CR.CODICE_MAPPA,
CR.NOMI, CR.COLORI.

Un CASO NUOVO: una voce in fondo a cited-cases/casi.yaml e il suo cited-cases/<id>.yaml; niente codice da toccare.
L'ORDINE del file e' l'ordine dei casi in tutti gli output. Per le prove: TRACE_CASI=<altro file indice> usa quello (le
sonde e i file di un caso finto si provano cosi', senza toccare il repository).

Il file si legge con un lettore minimo (elenco piatto di "chiave: valore", nessuna dipendenza: gira anche dove PyYAML
non c'e').

DOVE STA IL FILE (10/10/2026): TRACE_CASI se c'e'; altrimenti cited-cases/casi.yaml accanto al pacchetto (la copia del
repository, come prima), poi sotto TRACE_RADICE, poi nella cartella corrente. Se non c'e' da nessuna parte l'import non
si rompe (con `pip install .` il pacchetto sta in site-packages e `trace --help` deve rispondere): il registro resta
vuoto e CASI, PREFISSI ecc. sono vuoti; `leggi()` chiamata da sola alza l'errore col percorso.

Gemello nel pacchetto: tracepipe/casi_registro.py (stessa logica; tests/test_casi_registro.py li confronta)."""

import os
import pathlib

QUI = pathlib.Path(__file__).resolve().parent.parent
CAMPI = ('id', 'prefisso', 'nome', 'colore', 'serie_prima', 'serie_in_uso', 'soglia_d05', 'codice_mappa', 'attivo')


def file_indice():
    if os.environ.get('TRACE_CASI'):
        return pathlib.Path(os.environ['TRACE_CASI'])
    radici = [pathlib.Path(os.environ['TRACE_RADICE'])] if os.environ.get('TRACE_RADICE') else []
    for radice in [QUI, *radici, pathlib.Path.cwd()]:
        if (radice / 'cited-cases' / 'casi.yaml').is_file():
            return radice / 'cited-cases' / 'casi.yaml'
    return QUI / 'cited-cases' / 'casi.yaml'


def _valore(s):
    s = s.strip()
    if s[:1] in ('"', "'") and s[-1:] == s[:1] and len(s) >= 2:
        return s[1:-1]
    if ' #' in s:
        s = s.split(' #', 1)[0].rstrip()
    return s


def leggi(percorso=None):
    """Le voci del file indice, nell'ordine del file: lista di dict (tutti i campi, testo; vuoto se non scritto)."""
    percorso = pathlib.Path(percorso) if percorso else file_indice()
    voci, cur = [], None
    for n, riga in enumerate(percorso.read_text(encoding='utf-8').splitlines(), 1):
        if not riga.strip() or riga.lstrip().startswith('#') or riga.strip() == 'casi:':
            continue
        t = riga.strip()
        if t.startswith('- '):
            cur = {c: '' for c in CAMPI}
            voci.append(cur)
            t = t[2:]
        if cur is None or ':' not in t:
            raise ValueError(f'{percorso}:{n}: riga non valida: {riga!r}')
        k, v = t.split(':', 1)
        if k.strip() not in CAMPI:
            raise ValueError(f'{percorso}:{n}: campo sconosciuto «{k.strip()}»')
        cur[k.strip()] = _valore(v)
    ids = [v['id'] for v in voci]
    if len(set(ids)) != len(ids) or not all(ids):
        raise ValueError(f'{percorso}: id mancanti o doppi')
    return voci


def _tutti():
    percorso = file_indice()
    return leggi(percorso) if percorso.is_file() else []


VOCI = _tutti()
ATTIVO = {v['id']: v['attivo'].lower() not in ('no', 'n', 'false', '0') for v in VOCI}
CASI = tuple(v['id'] for v in VOCI if ATTIVO[v['id']])
TUTTI = tuple(v['id'] for v in VOCI)                      # anche i casi non attivi
PREFISSI = {v['id']: v['prefisso'] for v in VOCI if ATTIVO[v['id']]}
NOMI = {v['id']: v['nome'] for v in VOCI}
COLORI = {v['id']: v['colore'] for v in VOCI}
PRIMA_SERIE = {v['id']: v['serie_prima'] for v in VOCI if v['serie_prima']}
SERIE_IN_USO = {v['id']: v['serie_in_uso'] for v in VOCI if v['serie_in_uso']}
SOGLIE_D05 = {v['id']: v['soglia_d05'] for v in VOCI if ATTIVO[v['id']] and v['soglia_d05']}
CODICE_MAPPA = {v['id']: v['codice_mappa'] for v in VOCI if v['codice_mappa']}


def prefisso(caso):
    return PREFISSI[caso]
