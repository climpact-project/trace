"""The reading helpers of `tools/stabilita_deepseek.py` (02/10/2026), copied unchanged for `krippendorff_alpha.py`.

Which readings count, and how a reading becomes a citation type or a set of principles: a failed reading (empty or
unreadable answer) is a missing value, never "no principle". L04 and TIPO name the reading files of the 02/10 re-run
sample (`*_stab.jsonl`) compared with the readings in use.
"""
# The code keeps the frozen original line for line (names are not restyled).
# ruff: noqa: E501, E741
import json

L04 = {'urgenda': 'l04nuove', 'neubauer': 'l04P05', 'future-generations': 'l04P05',
       'klimaseniorinnen': 'l04nuove', 'cig-parere-clima': 'l04nuove', 'idh-oc-32-25': 'l04nuove'}
TIPO = {'urgenda': 'v10'}                    # the type reading of the sample rows: v10 for Urgenda (the new rows), the first for the others


def principi(lettura):
    # 02/10/2026: a failed reading (empty or unreadable answer, `esito` ILLEGGIBILE with `grezzo`) is NOT "no
    # principle": it is skipped. Before, it counted as an empty set and lowered the agreement.
    if not isinstance(lettura, dict) or lettura.get('esito') == 'ILLEGGIBILE' or 'grezzo' in lettura:
        return None
    v = lettura.get('principi')
    if isinstance(v, str):
        try:
            v = json.loads(v.replace("'", '"'))
        except ValueError:
            v = [v]
    return frozenset(str(p).split('.')[-1] for p in (v or []) if str(p).split('.')[-1] not in ('nessuno', 'altro', ''))


def tipo(lettura):
    if not isinstance(lettura, dict) or lettura.get('esito') == 'ILLEGGIBILE' or 'grezzo' in lettura:
        return None
    return lettura.get('tipo_citazione')


def carica(f):
    return {json.loads(l)['id']: json.loads(l) for l in open(f, encoding='utf-8')} if f.exists() else {}


def jaccard(a, b):
    return 1.0 if not a and not b else len(a & b) / len(a | b)


