"""QUALE SERIE DI SONDE (01/10/2026). Le sonde di un caso citato hanno un codice di versione (famiglia P del registro):
P01 Urgenda, P02 Neubauer e Future Generations del 23/09, P03 le sonde del PI del 01/10. I file dei casi
(`cited-cases/<caso>.yaml`) portano le sonde IN USO in piattaforma; una serie in prova sta in `cited-cases/<caso>-<P>.yaml`
e si sceglie con la variabile d'ambiente TRACE_SONDE (per esempio TRACE_SONDE=P03). In prova anche i file che ne
discendono hanno il suffisso: `<caso>_da_paragrafi_P03.jsonl`, `<caso>_P03_punteggi_*.jsonl`, `<caso>_ripresa_righe_P03.jsonl`.
Cosi' le due serie non si mescolano mai: era successo che le sonde nuove finissero nei file vivi mentre la piattaforma
usava le vecchie."""
import os, pathlib
QUI = pathlib.Path(__file__).resolve().parent.parent


# LA SERIE IN USO PER CASO (01/10/2026: P05 adottata per Neubauer e Future Generations, il PI). Senza TRACE_SONDE vale
# questa. P01 e P02 sono le serie storiche: i loro file derivati non hanno suffisso.
SERIE_IN_USO = {'neubauer': 'P05', 'future-generations': 'P05', 'cig-parere-clima': 'P09'}
STORICHE = {'P01', 'P02'}


def serie(caso=None):
    s = os.environ.get('TRACE_SONDE', '') or (SERIE_IN_USO.get(caso, '') if caso else '')
    if s and caso and not (QUI/'cited-cases'/f'{caso}-{s}.yaml').exists():
        raise SystemExit(f'TRACE_SONDE={s}: manca cited-cases/{caso}-{s}.yaml')
    return s


def file_caso(caso):
    s = serie(caso)
    return QUI/'cited-cases'/(f'{caso}-{s}.yaml' if s else f'{caso}.yaml')


def file_fascicolo(caso):
    s = serie(caso)
    f = QUI/'cited-cases'/f'{caso}-fascicolo-{s}.md'
    return f if s and f.exists() else QUI/'cited-cases'/f'{caso}-fascicolo.md'


def suf(caso=None):
    s = serie(caso)
    return f'_{s}' if s and s not in STORICHE else ''


def codice(caso):
    return serie(caso) or PRIMA_SERIE.get(caso, 'P02')


# la prima serie di sonde di ogni caso, quella dei file senza suffisso
PRIMA_SERIE = {'urgenda': 'P01', 'neubauer': 'P02', 'future-generations': 'P02', 'klimaseniorinnen': 'P06', 'cig-parere-clima': 'P07', 'idh-oc-32-25': 'P08'}


def storica(caso=None):
    """Vero se la serie scelta e' una delle storiche (file derivati senza suffisso, letture di prima)."""
    return serie(caso) in ('',) or serie(caso) in STORICHE
