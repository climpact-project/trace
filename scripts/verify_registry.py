"""Check the frozen copies in versioni/ against the SHA-256 fingerprints of the registry.

Every version in versioni/registro.json lists the instructions and code it ran with: the original path, the frozen
copy kept in this repository, and the SHA-256 of the file as executed. This script recomputes each fingerprint.

    python scripts/verify_registry.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    registry = json.loads((ROOT / 'versioni' / 'registro.json').read_text(encoding='utf-8'))
    ok, different, not_here, elsewhere = 0, [], [], []
    for version in registry:
        for field in ('istruzioni', 'codice_sorgente'):
            for entry in version.get(field) or []:
                copy, fingerprint = entry.get('copia'), entry.get('sha256')
                if not copy or not fingerprint:
                    continue
                path = ROOT / copy
                if not copy.startswith('versioni/'):
                    elsewhere.append(f'{version["codice"]}: {copy}')
                elif not path.is_file():
                    not_here.append(f'{version["codice"]}: {copy}')
                elif hashlib.sha256(path.read_bytes()).hexdigest() == fingerprint:
                    ok += 1
                else:
                    different.append(f'{version["codice"]}: {copy}')
    print(f'{len(registry)} versions; frozen copies matching their fingerprint: {ok}; different: {len(different)}')
    for line in different:
        print('  DIFFERENT', line)
    for line in not_here:
        print('  MISSING', line)
    for line in elsewhere:
        print('  kept outside this repository, as the entry says:', line)
    return 1 if different or not_here else 0


if __name__ == '__main__':
    sys.exit(main())
