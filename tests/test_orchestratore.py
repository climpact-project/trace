"""The cycles in Python: declared steps, state file, counted retries, checked copies, logs in the project folder,
no step run twice. Everything against :class:`TrasportoFinto` (a local folder playing ReCaS)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tracepipe.orchestratore import (
    CASI,
    STRUMENTI,
    CicloVuote,
    CopiaRovinataError,
    Orchestratore,
    Passo,
    TrasportoFinto,
    bersagli,
    coda,
    ingressi,
)

VUOTA = {'esito': 'ILLEGGIBILE', 'grezzo': ''}
BUONA = {'tipo_citazione': 'descrittiva'}


def _scrivi_jsonl(p: Path, righe: list[dict[str, Any]]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(''.join(json.dumps(x) + '\n' for x in righe))


@pytest.fixture
def radice(tmp_path: Path) -> Path:
    r = tmp_path / 'progetto'
    for f in STRUMENTI:
        (r / f).parent.mkdir(parents=True, exist_ok=True)
        (r / f).write_text(f'# {f}\n')
    for rel in dict.fromkeys(ingressi()):
        if 'righe' in rel:
            _scrivi_jsonl(r / rel, [{'id': 'a'}, {'id': 'b'}])
        else:
            _scrivi_jsonl(r / rel, [{'id': 'a', 'letture': [VUOTA, BUONA]}, {'id': 'b', 'letture': [BUONA, BUONA]}])
    return r


class Remoto:
    """ReCaS as a folder: the queues 'finish' at the third look and rewrite the reading files."""

    def __init__(self, cartella: Path, rotto: str = '') -> None:
        self.cartella, self.rotto, self.sguardi = cartella, rotto, 0

    def guarda(self, comando: str) -> tuple[int, str]:
        self.sguardi += 1
        if self.sguardi < 3:
            return 1, ''
        for rel in bersagli():
            righe = [
                {'id': 'a', 'letture': [BUONA, BUONA], 'rifatte_vuote': '2026-10-02'},
                {'id': 'b', 'letture': [BUONA, BUONA]},
            ]
            if rel == self.rotto:
                righe = righe[:1]  # a row lost: the file must not be taken back
            _scrivi_jsonl(self.cartella / rel, righe)
        return 0, ''


def _ciclo(
    radice: Path, tmp: Path, remoto: Remoto | None = None, locale: Any = None, **kw: Any
) -> tuple[CicloVuote, Any]:
    remoto = remoto or Remoto(tmp / 'recas')
    t = TrasportoFinto(tmp / 'recas', comandi={'test -s': remoto.guarda}, guasti=kw.pop('guasti', ()))
    chiamate: list[list[str]] = []

    def esegui_locale(argv: list[str]) -> int:
        chiamate.append(argv)
        return locale(argv) if locale else 0

    c = CicloVuote(radice, t, attesa_s=0, esegui_locale=esegui_locale, dormi=lambda s: None, **kw)
    c.chiamate = chiamate  # type: ignore[attr-defined]
    return c, t


def test_ciclo_completo(radice: Path, tmp_path: Path) -> None:
    rotto = 'training/lessicali_neubauer_deepseek.jsonl'
    c, _ = _ciclo(radice, tmp_path, Remoto(tmp_path / 'recas', rotto=rotto))
    assert c.esegui() is True
    stato = json.loads((radice / 'giornale' / 'cicli' / 'ciclo_vuote.stato.json').read_text())['passi']
    assert all(v['esito'] == 'fatto' for v in stato.values()) and len(stato) == len(c.passi)
    assert stato['attendi_letture']['dati'] == 3
    # every target came back with the same rows and fewer empty readings, except the one that lost a row
    preso = stato['riprendi_file']['dati']
    assert preso[rotto] == {'righe': [2, 1], 'vuote': [1, 0], 'preso': False}
    assert all(v['preso'] for k, v in preso.items() if k != rotto)
    assert (radice / 'training/principi/urgenda_ripresa_deepseek_v2.jsonl.prima-vuote').exists()
    assert not (radice / (rotto + '.prima-vuote')).exists()
    # the rows redone are extracted for the type loader; the local commands in the order of the shell chain
    vuote = (radice / 'training' / 'lessicali_urgenda_deepseek_vuote.jsonl').read_text()
    assert json.loads(vuote)['id'] == 'a'
    assert c.chiamate[:2] == [  # type: ignore[attr-defined]
        ['carica', 'tipo', '--caso', 'urgenda', '--etichetta', 'vuote', '--sovrascrivi', '--scrivi'],
        ['carica', 'ripresa', '--caso', 'urgenda', '--principi-da-l04', '--scrivi'],
    ]
    assert c.chiamate[-2:] == [['controlla', 'completezza', '--scrivi'], ['controlla', 'finestra']]  # type: ignore[attr-defined]
    assert (tmp_path / 'recas' / 'chat' / 'coda-ds2' / 'vuote_coda-ds2.sh').read_text() == coda(
        'coda-ds2', ('urgenda', 'neubauer')
    )
    log = (radice / 'giornale' / 'cicli' / 'ciclo_vuote.log').read_text()
    assert log.splitlines()[0].endswith(' inizio') and log.splitlines()[-1].endswith(' FINITO')
    assert 'NON PRESO' in log


def test_mai_due_volte(radice: Path, tmp_path: Path) -> None:
    c, _ = _ciclo(radice, tmp_path)
    assert c.esegui()
    c2, t2 = _ciclo(radice, tmp_path)
    assert c2.esegui() is True
    assert t2.storia == [] and c2.chiamate == []  # type: ignore[attr-defined]
    assert (radice / 'giornale' / 'cicli' / 'ciclo_vuote.log').read_text().splitlines()[-2].endswith(' ripresa')


def test_tentativi_contati_anche_fra_le_riprese(radice: Path, tmp_path: Path) -> None:
    errori = {'n': 0}

    def locale(argv: list[str]) -> int:
        if argv[:2] == ['carica', 'tipo'] and 'neubauer' in argv:
            errori['n'] += 1
            return 1
        return 0

    c, _ = _ciclo(radice, tmp_path, locale=locale)
    assert c.esegui() is False
    stato = json.loads((radice / 'giornale' / 'cicli' / 'ciclo_vuote.stato.json').read_text())['passi']
    assert stato['carica_tipo_neubauer']['esito'] == 'fallito' and stato['carica_tipo_neubauer']['tentativi'] == 3
    assert errori['n'] == 3 and 'carica_ripresa_neubauer' not in stato
    # restarted: the finished steps do not run again, the failed one has no attempts left
    c2, t2 = _ciclo(radice, tmp_path, locale=locale)
    assert c2.esegui() is False and errori['n'] == 3 and t2.storia == []


def test_ripresa_dopo_un_errore_passeggero(radice: Path, tmp_path: Path) -> None:
    volte = {'n': 0}

    def locale(argv: list[str]) -> int:
        if argv[0] == 'controlla' and argv[1] == 'completezza':
            volte['n'] += 1
            return 0 if volte['n'] == 2 else 1
        return 0

    c, _ = _ciclo(radice, tmp_path, locale=locale)
    assert c.esegui() is True
    stato = json.loads((radice / 'giornale' / 'cicli' / 'ciclo_vuote.stato.json').read_text())['passi']
    assert stato['controllo_completezza'] == {**stato['controllo_completezza'], 'esito': 'fatto', 'tentativi': 2}


def test_copia_rovinata_si_rifa(radice: Path, tmp_path: Path) -> None:
    rel = 'tools/sonde.py'
    c, t = _ciclo(radice, tmp_path, guasti=[rel])
    assert c.esegui()
    assert [x for x in t.storia if x == ('manda', rel)] == [('manda', rel)] * 2
    assert f'copia rovinata verso {rel}' in (radice / 'giornale' / 'cicli' / 'ciclo_vuote.log').read_text()
    assert (tmp_path / 'recas' / rel).read_bytes() == (radice / rel).read_bytes()


def test_copia_sempre_rovinata(tmp_path: Path) -> None:
    (tmp_path / 'f.txt').write_text('uno\ndue\n')
    t = TrasportoFinto(tmp_path / 'recas', guasti=['f.txt'] * 5)
    o = Orchestratore('prova', tmp_path, t, dormi=lambda s: None)
    with pytest.raises(CopiaRovinataError):
        o.manda('f.txt')
    (tmp_path / 'recas' / 'g.txt').write_text('a\n')
    t.guasti = ['g.txt']
    assert o.prendi('g.txt', tmp_path / 'g.txt') == o.trasporto.impronta('g.txt')


def test_passi_dichiarati(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        Orchestratore('x', tmp_path, TrasportoFinto(tmp_path), [Passo('a', lambda o: 1), Passo('a', lambda o: 2)])
    c = CicloVuote(tmp_path, TrasportoFinto(tmp_path))
    nomi = [p.nome for p in c.passi]
    assert nomi[:6] == [
        'copia_di_sicurezza',
        'manda_strumenti',
        'manda_file',
        'scrivi_code',
        'attendi_letture',
        'riprendi_file',
    ]
    assert nomi[-2:] == ['controllo_completezza', 'controllo_finestra'] and len(nomi) == 8 + 3 * len(CASI)
    assert c.log.parent == tmp_path / 'giornale' / 'cicli'


def test_coda_come_la_catena() -> None:
    """The queue lines the shell chain wrote (``scrivi_coda``), for one case."""
    righe = coda('coda-ds2', ('urgenda',), letture=2).splitlines()
    assert righe[0] == 'H=/lustrehome/climpact/trace; C=$H/chat; cd $H'
    assert righe[2] == (
        '$H/venv/bin/python -u tools/leggi_ripresa.py leggi --caso urgenda --etichetta v2 --letture 2 --solo-vuote $A'
        ' >> $C/log/vuote_coda-ds2.log 2>&1'
    )
    assert righe[3].startswith("$H/venv/bin/python -u tools/leggi_l04.py leggi --caso urgenda --etichetta '' ")
    assert righe[5].startswith(
        '$H/venv/bin/python -u tools/classifica_lessicali.py leggi --caso urgenda --gruppo tutte'
    )
    assert "--etichetta 'v2' --solo-vuote $A >> $C/log/vuote_coda-ds2.log 2>&1" in righe[5]
    assert righe[-1] == 'echo FINITO > $C/log/vuote_coda-ds2_fine.txt'


def test_coda_cinque_letture_e_seme() -> None:
    """Since 03/10/2026 the queues ask the protocol's five readings; a seed, when given, goes to every reader."""
    righe = coda('coda-ds2', ('urgenda',)).splitlines()
    assert all('--letture 5 ' in r for r in righe if ' leggi ' in r)
    assert '--seme' not in righe[1]
    con = coda('coda-ds2', ('urgenda',), seme=7).splitlines()
    assert con[1].endswith('--paralleli 32 --seme 7"')
    assert con[2:] == righe[2:]
