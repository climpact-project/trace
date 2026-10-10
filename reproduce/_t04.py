"""Load the frozen copy of T04 (versioni/T04/) so that it runs outside the TRACE working tree.

The frozen files compute their project root from their own location (`QUI = parent.parent`), and import two helpers
from the working tree's `tools/`: `chiamata_deepseek.json_finale` (in `ragionamento.json_risposta`) and `sonde`
(in `ragionamento.caso_conf`). Here, as `tools/t04_tutte.t04()` already did for the TRACE 0.1 measures, the line that
sets the root is replaced by the root given as an argument before the file is executed, and the two helpers are given
as small modules with the same code: `json_finale` is copied unchanged from `chiamata_deepseek.py` (the same function in
the published copies versioni/L13/ and versioni/R11/), `sonde` is `_common.Probes`. Nothing else in the frozen code is
touched, and its SHA-256 can be checked against the registry entry T04 (versioni/registro.json) with `check_sha256`.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import types

HERE = pathlib.Path(__file__).resolve().parent
RADICE_ORIGINALE = 'QUI = pathlib.Path(__file__).resolve().parent.parent'


def default_t04_dir() -> pathlib.Path:
    """versioni/T04 of the repository (next to reproduce/), or of the TRACE working tree."""
    for d in HERE.parents:
        if (d / 'versioni' / 'T04' / 'ragionamento.py').is_file():
            return d / 'versioni' / 'T04'
    return HERE.parent / 'versioni' / 'T04'


def default_registry() -> pathlib.Path:
    return default_t04_dir().parent / 'registro.json'


def json_finale(ragionamento):
    """Copied unchanged from chiamata_deepseek.json_finale (02/10/2026): the JSON at the end of the reasoning, taken
    only if it is the last thing written (after it only spaces or ``` fences), never a draft in the middle."""
    import json
    t = (ragionamento or '').rstrip()
    while t.endswith('```'):
        t = t[:-3].rstrip()
    if not t.endswith('}'):
        return ''
    dec = json.JSONDecoder()
    i = t.rfind('{')
    while i >= 0:
        try:
            obj, fine = dec.raw_decode(t, i)
            if fine == len(t) and isinstance(obj, dict):
                return t[i:fine]
        except ValueError:
            pass
        i = t.rfind('{', 0, i)
    return ''


def install_helpers(root: pathlib.Path) -> None:
    """Register `chiamata_deepseek` (json_finale only) and `sonde` (for the given root) as modules."""
    sys.path.insert(0, str(HERE))
    from _common import Cases, Probes
    cd = types.ModuleType('chiamata_deepseek')
    cd.json_finale = json_finale
    sys.modules['chiamata_deepseek'] = cd
    try:
        probes = Probes(root, Cases(root))
    except FileNotFoundError:
        probes = None
    so = types.ModuleType('sonde')
    for nome in ('serie', 'file_caso', 'file_fascicolo', 'suf', 'codice', 'storica'):
        if probes is not None:
            setattr(so, nome, getattr(probes, nome))
    sys.modules['sonde'] = so


def frozen(name: str, path: pathlib.Path, root: pathlib.Path) -> types.ModuleType:
    """Execute a frozen file as module `name`, with its project root set to `root`."""
    src = path.read_text(encoding='utf-8')
    if RADICE_ORIGINALE not in src:
        raise SystemExit(f'{path}: the root line was not found; is this the frozen copy?')
    src = src.replace(RADICE_ORIGINALE, f'QUI = pathlib.Path({str(root)!r})')
    m = types.ModuleType(name)
    m.__file__ = str(path)
    sys.modules[name] = m
    exec(compile(src, str(path), 'exec'), m.__dict__)
    return m


def load(t04_dir: pathlib.Path, root: pathlib.Path, verita=None, insieme=None):
    """(RG, AR): frozen ragionamento.py (registered as `ragionamento`, the name the training script imports) and
    addestra_reranker_ragiona.py. `verita` and `insieme` override RG.VERITA and RG.INSIEME (team judgments and rows of
    the measure), which otherwise are <root>/training/ragionamento/verita.json and insieme.json."""
    t04_dir, root = pathlib.Path(t04_dir), pathlib.Path(root)
    install_helpers(root)
    rg = frozen('ragionamento', t04_dir / 'ragionamento.py', root)
    if verita:
        rg.VERITA = pathlib.Path(verita)
    if insieme:
        rg.INSIEME = pathlib.Path(insieme)
    ar = frozen('addestra_reranker_ragiona', t04_dir / 'addestra_reranker_ragiona.py', root)
    return rg, ar


def check_sha256(t04_dir: pathlib.Path, registry: pathlib.Path) -> dict[str, bool]:
    """{file: matches} for the frozen files that the registry entry T04 lists with a SHA-256 (code and prompts)."""
    voce = next(x for x in json.loads(pathlib.Path(registry).read_text(encoding='utf-8')) if x.get('codice') == 'T04')
    out = {}
    for x in voce.get('codice_sorgente', []) + voce.get('istruzioni', []):
        nome = pathlib.Path(x.get('copia') or x['file']).name
        f = pathlib.Path(t04_dir) / nome
        out[nome] = f.is_file() and hashlib.sha256(f.read_bytes()).hexdigest() == x['sha256']
    return out
