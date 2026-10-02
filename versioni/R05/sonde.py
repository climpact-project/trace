"""QUALE SERIE DI SONDE (01/10/2026). Le sonde di un caso citato hanno un codice di versione (famiglia P del registro):
P01 Urgenda, P02 Neubauer e Future Generations del 23/09, P03 le sonde del PI del 01/10. I file dei casi
(`cited-cases/<caso>.yaml`) portano le sonde IN USO in piattaforma; una serie in prova sta in `cited-cases/<caso>-<P>.yaml`
e si sceglie con la variabile d'ambiente TRACE_SONDE (per esempio TRACE_SONDE=P03). In prova anche i file che ne
discendono hanno il suffisso: `<caso>_da_paragrafi_P03.jsonl`, `<caso>_P03_punteggi_*.jsonl`, `<caso>_ripresa_righe_P03.jsonl`.
Cosi' le due serie non si mescolano mai: era successo che le sonde nuove finissero nei file vivi mentre la piattaforma
usava le vecchie."""
import os, pathlib
QUI = pathlib.Path(__file__).resolve().parent.parent


def serie(caso=None):
    s = os.environ.get('TRACE_SONDE', '')
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
    return f'_{s}' if s else ''


def codice(caso):
    return serie(caso) or ('P01' if caso == 'urgenda' else 'P02')
