"""Small helpers shared by the scripts of `reproduce/`.

Nothing here computes a figure. The helpers replace what the original measurement tools imported from `tools/` in
the project working tree (not published): the case registry (`tools/casi_registro.py`, read here with
`tracepipe.casi_registro.leggi`, the same parser), the choice of the probe series of a case (`tools/sonde.py`, same
code, with the project root as an argument instead of the location of the file) and the JSON-lines readers.

The project root (`--root` or the TRACE_ROOT environment variable) is the folder that holds `cited-cases/`,
`training/`, `index/` and the other inputs of a measure, laid out as in the TRACE working tree. Every script also takes
the single files as arguments, so the root is only the default place where they are looked for.
"""

from __future__ import annotations

import contextlib
import gzip
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def project_root(value: str | os.PathLike | None = None) -> pathlib.Path:
    """The project root: the argument, else TRACE_ROOT, else the current folder."""
    return pathlib.Path(value or os.environ.get('TRACE_ROOT') or '.').resolve()


def import_tracepipe():
    """Make `tracepipe` importable when the script runs from a checkout of the repository (not installed)."""
    try:
        import tracepipe  # noqa: F401
    except ImportError:
        # the repository root is the parent of reproduce/ (in the TRACE working tree: some levels further up)
        for d in HERE.parents:
            if (d / 'tracepipe' / '__init__.py').is_file():
                sys.path.insert(0, str(d))
                break


class Cases:
    """The case registry of `cited-cases/casi.yaml`, as `tools/casi_registro.py` exposes it (CASI, SERIE_IN_USO,
    PRIMA_SERIE), read with the parser of `tracepipe.casi_registro`."""

    def __init__(self, root: pathlib.Path, index_file: str | os.PathLike | None = None):
        import_tracepipe()
        from tracepipe import casi_registro
        self.root = pathlib.Path(root)
        path = pathlib.Path(index_file) if index_file else (
            pathlib.Path(os.environ['TRACE_CASI']) if os.environ.get('TRACE_CASI')
            else self.root / 'cited-cases' / 'casi.yaml')
        voci = casi_registro.leggi(path)
        attivo = {v['id']: v['attivo'].lower() not in ('no', 'n', 'false', '0') for v in voci}
        self.CASI = tuple(v['id'] for v in voci if attivo[v['id']])
        self.PRIMA_SERIE = {v['id']: v['serie_prima'] for v in voci if v['serie_prima']}
        self.SERIE_IN_USO = {v['id']: v['serie_in_uso'] for v in voci if v['serie_in_uso']}


class Probes:
    """`tools/sonde.py` with the project root as an argument: which probe series a case uses (the TRACE_SONDE
    environment variable, else the series in use of the registry), and the files that follow from it."""

    STORICHE = frozenset({'P01', 'P02'})

    def __init__(self, root: pathlib.Path, cases: Cases):
        self.QUI = pathlib.Path(root)
        self.SERIE_IN_USO = dict(cases.SERIE_IN_USO)
        self.PRIMA_SERIE = dict(cases.PRIMA_SERIE)

    def serie(self, caso=None):
        s = os.environ.get('TRACE_SONDE', '') or (self.SERIE_IN_USO.get(caso, '') if caso else '')
        if s and caso and not (self.QUI/'cited-cases'/f'{caso}-{s}.yaml').exists():
            raise SystemExit(f'TRACE_SONDE={s}: manca cited-cases/{caso}-{s}.yaml')
        return s

    def file_caso(self, caso):
        s = self.serie(caso)
        return self.QUI/'cited-cases'/(f'{caso}-{s}.yaml' if s else f'{caso}.yaml')

    def file_fascicolo(self, caso):
        s = self.serie(caso)
        f = self.QUI/'cited-cases'/f'{caso}-fascicolo-{s}.md'
        return f if s and f.exists() else self.QUI/'cited-cases'/f'{caso}-fascicolo.md'

    def suf(self, caso=None):
        s = self.serie(caso)
        return f'_{s}' if s and s not in self.STORICHE else ''

    def codice(self, caso):
        return self.serie(caso) or self.PRIMA_SERIE.get(caso, 'P02')

    def storica(self, caso=None):
        """True if the chosen series is one of the historical ones (derived files without suffix)."""
        return self.serie(caso) in ('',) or self.serie(caso) in self.STORICHE


def jl(f):
    """Rows of a .jsonl or .jsonl.gz file; a truncated line (interrupted job) is skipped; a missing file gives []."""
    op = gzip.open if str(f).endswith('.gz') else open
    if not pathlib.Path(f).exists():
        return []
    out = []
    with op(f, 'rt', encoding='utf-8') as h:
        for x in h:
            with contextlib.suppress(ValueError):
                out.append(json.loads(x))
    return out
