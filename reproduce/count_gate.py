"""THE COUNT GATE (04/10/2026, approved by the principal investigator after the precision measure of S07).

Original: `tools/porta_conteggi.py` of the TRACE working tree (frozen with TRACE 0.1). Same rule; the folder of the
reading files is an argument; `valida` and the citation categories come from `tracepipe.maggioranza` (the same code as
`tools/maggioranza.py`: `valida`, and `CATEGORIE_ORDINE` = `CAT`). Italian strings (reasons) are data.

THE RULE. A row found by the machine enters the counts (map, Ask TRACE chat, figures of the page, numbers of the video)
only when DeepSeek V4 Flash has read it and its five readings of the type say that the text cites the judgment: the field
"riferimento" is "caso" ("caso_urgenda" for Urgenda) in at least
    3 readings out of 5 for the rows found by name (lexical network or both),
    4 readings out of 5 for the rows of the descriptive network (S07, the name is not there: a wider agreement is needed).
The readings counted are the valid ones (read, not unreadable, with a type of the codebook). While the gate is closed
the row stays in the database and in the team queue, but out of every total.

THE TEAM JUDGMENT COUNTS MORE THAN THE READINGS:
  - confirmed in Uptakes: always enters (verified);
  - discarded: stays as before (on the map as "discarded", already out of the totals);
  - confirmed in the September validation (`settembre.esito` = confermata, rows put back in the queue on 29/09): enters,
    because in September the team judged exactly whether the text cites the case. The September "reclassified" rows do
    not: the field has two opposite meanings, so they go through the readings like the others.

WHERE THE VOTES COME FROM. Since 04/10 the type loader writes `proposto_riferimento_voti` on the row
({'caso': '4/5', 'omonimo': '1/5'}). Rows loaded before do not have it: for them the votes are counted from the reading
files (lessicali_<case>_deepseek_<label>.jsonl, labels in ETICHETTE, the first that has the row), also looking for the
former id of moved rows (`spostata_da.id`), and only if the reading is already loaded on the row (`proposto_tipo_voti`
or `proposto_lettore`). A row read only twice (readings of 28/09, codebook 0.3) does not reach 3 votes, except for
variant B2 below.

Command line (read only; the rows are a JSON-lines snapshot of `corpus_rows` with their `id`, not published):
  python reproduce/count_gate.py --rows righe.jsonl.gz --readings-dir training [--cases urgenda,neubauer,...]
prints, per case, how many rows enter the counts and why the others stay out.
"""
# The code keeps the frozen original line for line (names are not restyled).
# ruff: noqa: E402, E501, E741, SIM105, SIM115
import argparse
import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _common import import_tracepipe, jl

import_tracepipe()
from tracepipe import maggioranza as _m


class M:
    """`tools/maggioranza.py` as the original imports it: `valida` and the categories `CAT`."""
    valida = staticmethod(_m.valida)
    CAT = _m.CATEGORIE_ORDINE


SOGLIA = {'lessicale': 3, 'entrambe': 3, 'descrittiva': 4}
ETICHETTE = ('s07', 'd04', 'cinque', 's06', 'v2', '')   # '' and v2: the two September readings (below threshold)
CASO = ('caso', 'caso_urgenda')


def conta_letture(letture):
    """Counter of the "riferimento" of the valid readings ('caso' for caso and caso_urgenda)"""
    return collections.Counter('caso' if y.get('riferimento') in CASO else str(y.get('riferimento'))
                               for y in (letture or []) if M.valida(y) and y.get('tipo_citazione') in M.CAT)


def voti_testo(c):
    n = sum(c.values())
    return {k: f'{v}/{n}' for k, v in c.items()}


def da_testo(d):
    """{'caso': '4/5', ...} -> Counter"""
    out = collections.Counter()
    for k, v in (d or {}).items():
        try:
            out[k] = int(str(v).split('/')[0])
        except ValueError:
            pass
    return out


def letture_locali(casi, cartella, etichette=ETICHETTE):
    """{row id: Counter of the references} from the reading files; for every row the first label that has it"""
    cartella = pathlib.Path(cartella)
    out = {}
    for caso in casi:
        for et in etichette:
            f = cartella/f"lessicali_{caso}_deepseek{'_' + et if et else ''}.jsonl"
            if not f.exists():
                continue
            for l in open(f, encoding='utf-8'):
                try:
                    x = json.loads(l)
                except ValueError:
                    continue
                c = conta_letture(x.get('letture'))
                if c and x.get('id') not in out:
                    out[x['id']] = c
    return out


def voti_riga(rid, r, locali):
    """Counter of the references of the row, or None if DeepSeek has not read it yet"""
    if r.get('proposto_riferimento_voti'):
        return da_testo(r['proposto_riferimento_voti'])
    if not (r.get('proposto_tipo_voti') or r.get('proposto_lettore')):
        return None     # the readings exist locally but are not loaded in the database yet: the row waits for the load
    for k in (rid, (r.get('spostata_da') or {}).get('id')):
        if k and k in locali:
            return locali[k]
    return None


def entra(r, voti):
    """(enters the counts?, reason). `voti`: Counter of the references, or None if not read."""
    esito = r.get('esito')
    if esito == 'confermata':
        return True, 'confermata dal team'
    if esito == 'scartata':
        return True, 'scartata dal team (sulla mappa come discarded, fuori dai totali)'
    if (r.get('settembre') or {}).get('esito') == 'confermata':
        return True, 'confermata dal team a settembre'
    soglia = SOGLIA.get(r.get('proposto_rete'))
    if soglia is None:
        return False, f"rete {r.get('proposto_rete')!r}: non va nei numeri"
    if not voti:
        return False, 'non ancora letta da DeepSeek'
    n, si = sum(voti.values()), voti.get('caso', 0)
    # VARIANT B2 (proposal of 04/10): a row read only twice (28/09, codebook 0.3) with "cites the case" in both enters;
    # it stays out if either of the two says something else
    if n == 2 and si == 2 and r.get('proposto_rete') != 'descrittiva':
        return True, 'letture: cita il caso 2/2 (letture di settembre)'
    if si >= soglia:
        return True, f'letture: cita il caso {si}/{n} (soglia {soglia})'
    return False, f'letture: cita il caso {si}/{n}, ne servono {soglia}'


def main(argv=None):
    ap = argparse.ArgumentParser(description='Apply the count gate to a snapshot of the rows and count who enters.')
    ap.add_argument('--rows', required=True, help='JSON lines (.gz allowed) of corpus_rows, each with its id (not published)')
    ap.add_argument('--readings-dir', required=True, help='folder with the lessicali_<case>_deepseek_<label>.jsonl readings')
    ap.add_argument('--cases', help='comma-separated case ids (default: the cases found in the rows)')
    a = ap.parse_args(argv)
    righe = {r['id']: r for r in jl(a.rows)}
    casi = a.cases.split(',') if a.cases else sorted({r.get('caso_citato') for r in righe.values() if r.get('caso_citato')})
    locali = letture_locali(casi, a.readings_dir)
    out = {}
    for rid, r in righe.items():
        si, motivo = entra(r, voti_riga(rid, r, locali))
        d = out.setdefault(r.get('caso_citato'), {'entrano': 0, 'fuori': 0, 'motivi': collections.Counter()})
        d['entrano' if si else 'fuori'] += 1
        d['motivi'][motivo] += 1
    print(json.dumps({c: {**v, 'motivi': dict(v['motivi'])} for c, v in out.items()}, ensure_ascii=False, indent=1))
    return out


if __name__ == '__main__':
    main()
