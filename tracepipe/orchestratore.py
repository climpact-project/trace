"""The cycles of the pipeline in Python (``orchestratore``), replacing the shell chains ``tools/ciclo_*.sh``.

A cycle is a list of declared steps (:class:`Passo`). :class:`Orchestratore` runs them in order and keeps, in a state
file, what each step did: a step that finished is never run again (a cycle restarted after a crash resumes from the
first step not finished), and every attempt is counted, across restarts, against the step's limit. Every copy to or
from the remote machine is checked: the remote SHA-256 and line count must equal the local ones. The log and the
state live in the project folder (``giornale/cicli/``), not in ``/tmp``, which the Mac empties.

The remote side goes through a :class:`Trasporto`: :class:`TrasportoSsh` (``ssh``/``scp`` to ReCaS, as the shell
chains) or :class:`TrasportoFinto` (a local folder playing the remote, for the tests). The local side (loaders and
checks) goes through a function ``esegui_locale(argv) -> exit code`` (default: :func:`tracepipe.cli.main`).

:class:`CicloVuote` is ``tools/ciclo_vuote.sh`` (02/10/2026), the most complete chain: back up the readings on ReCaS,
send the tools and the files, queue the re-readings of the empty readings (``--solo-vuote``) on the two DeepSeek
queues, wait for both, take the files back only if they have the same rows and no more empty readings, reload the
proposals of the re-read rows, run the checks.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .letture import LETTURE_PROTOCOLLO, vuota

# transport


class CopiaRovinataError(RuntimeError):
    """A copy whose hash or line count differs on the two sides."""


class Trasporto(Protocol):
    """The remote machine as the cycles use it."""

    def esegui(self, comando: str) -> tuple[int, str]:
        """Run a shell command remotely: (exit code, output)."""

    def manda(self, locale: Path, remoto: str) -> None:
        """Copy a local file to the remote path (relative to the remote project folder)."""

    def prendi(self, remoto: str, locale: Path) -> None:
        """Copy a remote file to a local path."""

    def scrivi(self, remoto: str, testo: str) -> None:
        """Write a text file remotely."""

    def impronta(self, remoto: str) -> tuple[str, int] | None:
        """(SHA-256, lines) of a remote file, ``None`` if it does not exist."""


def impronta_locale(p: Path) -> tuple[str, int]:
    """(SHA-256, lines) of a local file."""
    dati = p.read_bytes()
    return hashlib.sha256(dati).hexdigest(), dati.count(b'\n')


class TrasportoSsh:
    """``ssh``/``scp`` to the remote host (``recas``), files under ``~/<cartella>`` (``trace``).

    Never used by the tests. Commands are the ones of the shell chains (``ConnectTimeout=30``, ``BatchMode=yes``).
    """

    def __init__(self, host: str = 'recas', cartella: str = 'trace', timeout: int = 600) -> None:
        self.host = host
        self.cartella = cartella
        self.timeout = timeout

    def _ssh(self, comando: str, ingresso: str | None = None) -> tuple[int, str]:
        r = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=30', '-o', 'BatchMode=yes', self.host, comando],
            input=ingresso,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=False,
        )
        return r.returncode, r.stdout + r.stderr

    def esegui(self, comando: str) -> tuple[int, str]:
        return self._ssh(comando)

    def manda(self, locale: Path, remoto: str) -> None:
        r = subprocess.run(
            ['scp', '-q', str(locale), f'{self.host}:{self.cartella}/{remoto}'], timeout=self.timeout, check=False
        )
        if r.returncode:
            raise CopiaRovinataError(f'scp verso {remoto}: uscita {r.returncode}')

    def prendi(self, remoto: str, locale: Path) -> None:
        r = subprocess.run(
            ['scp', '-q', f'{self.host}:{self.cartella}/{remoto}', str(locale)], timeout=self.timeout, check=False
        )
        if r.returncode:
            raise CopiaRovinataError(f'scp da {remoto}: uscita {r.returncode}')

    def scrivi(self, remoto: str, testo: str) -> None:
        codice, out = self._ssh(f'cat > ~/{self.cartella}/{shlex.quote(remoto)}', testo)
        if codice:
            raise RuntimeError(f'scrittura di {remoto}: {out[-300:]}')

    def impronta(self, remoto: str) -> tuple[str, int] | None:
        q = shlex.quote(remoto)
        codice, out = self._ssh(f'cd ~/{self.cartella} && test -f {q} && sha256sum {q} && wc -l < {q}')
        if codice:
            return None
        righe = out.split()
        return righe[0], int(righe[-1])


class TrasportoFinto:
    """A local folder playing the remote machine (tests).

    Args:
        cartella: the remote project folder.
        comandi: ``{prefix: function(command) -> (code, output)}`` for :meth:`esegui`; unknown commands answer 0.
        guasti: remote paths whose next copies arrive damaged (one damaged copy per entry).
    """

    def __init__(
        self,
        cartella: Path,
        comandi: Mapping[str, Callable[[str], tuple[int, str]]] | None = None,
        guasti: Iterable[str] = (),
    ) -> None:
        self.cartella = Path(cartella)
        self.comandi = dict(comandi or {})
        self.guasti = list(guasti)
        self.storia: list[tuple[str, str]] = []

    def esegui(self, comando: str) -> tuple[int, str]:
        self.storia.append(('esegui', comando))
        for prefisso, f in self.comandi.items():
            if comando.startswith(prefisso):
                return f(comando)
        return 0, ''

    def _guasto(self, remoto: str) -> bool:
        if remoto in self.guasti:
            self.guasti.remove(remoto)
            return True
        return False

    def manda(self, locale: Path, remoto: str) -> None:
        self.storia.append(('manda', remoto))
        d = self.cartella / remoto
        d.parent.mkdir(parents=True, exist_ok=True)
        dati = locale.read_bytes()
        d.write_bytes(dati[: len(dati) // 2] if self._guasto(remoto) else dati)

    def prendi(self, remoto: str, locale: Path) -> None:
        self.storia.append(('prendi', remoto))
        dati = (self.cartella / remoto).read_bytes()
        locale.write_bytes(dati[: len(dati) // 2] if self._guasto(remoto) else dati)

    def scrivi(self, remoto: str, testo: str) -> None:
        self.storia.append(('scrivi', remoto))
        d = self.cartella / remoto
        d.parent.mkdir(parents=True, exist_ok=True)
        d.write_text(testo, encoding='utf-8')

    def impronta(self, remoto: str) -> tuple[str, int] | None:
        p = self.cartella / remoto
        return impronta_locale(p) if p.exists() else None


# steps and state


@dataclass
class Passo:
    """A declared step of a cycle.

    Attributes:
        nome: unique within the cycle.
        azione: the work; receives the orchestrator, returns a JSON-able summary (kept in the state) or ``None``.
        tentativi: attempts allowed, counted across restarts.
        pausa_s: sleep between attempts.
    """

    nome: str
    azione: Callable[[Orchestratore], Any]
    tentativi: int = 1
    pausa_s: float = 30.0


@dataclass
class StatoCiclo:
    """The state file of a cycle: for each step ``esito`` (``fatto``, ``fallito``, ``in corso``), attempts, times."""

    percorso: Path
    passi: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def carica(cls, percorso: Path) -> StatoCiclo:
        if percorso.exists():
            return cls(percorso, json.loads(percorso.read_text(encoding='utf-8')).get('passi', {}))
        return cls(percorso)

    def salva(self) -> None:
        self.percorso.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.percorso.with_suffix('.tmp')
        tmp.write_text(json.dumps({'passi': self.passi}, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
        os.replace(tmp, self.percorso)

    def di(self, nome: str) -> dict[str, Any]:
        return self.passi.setdefault(nome, {'esito': None, 'tentativi': 0})

    def fatto(self, nome: str) -> bool:
        return self.passi.get(nome, {}).get('esito') == 'fatto'


class Orchestratore:
    """Runs the declared steps of a cycle with state, counted retries and checked copies.

    Args:
        nome: the cycle name (log ``giornale/cicli/<nome>.log``, state ``giornale/cicli/<nome>.stato.json``).
        radice: the project root.
        trasporto: the remote machine.
        passi: the steps, in order.
        esegui_locale: runs a ``trace`` command locally, returns the exit code.
        dormi: the sleep function (tests pass a no-op).
        orologio: the clock of the log lines.
    """

    def __init__(
        self,
        nome: str,
        radice: Path | str,
        trasporto: Trasporto,
        passi: Sequence[Passo] = (),
        esegui_locale: Callable[[list[str]], int] | None = None,
        dormi: Callable[[float], None] = time.sleep,
        orologio: Callable[[], datetime.datetime] = datetime.datetime.now,
    ) -> None:
        self.nome = nome
        self.radice = Path(radice)
        self.trasporto = trasporto
        self.passi = list(passi)
        nomi = [p.nome for p in self.passi]
        if len(set(nomi)) != len(nomi):
            raise ValueError(f'passi con lo stesso nome: {nomi}')
        self.esegui_locale = esegui_locale or _cli_locale
        self.dormi = dormi
        self.orologio = orologio
        self.cartella = self.radice / 'giornale' / 'cicli'
        self.log = self.cartella / f'{nome}.log'
        self.stato = StatoCiclo.carica(self.cartella / f'{nome}.stato.json')

    # log
    def fase(self, testo: str) -> None:
        """One log line, ``dd/mm HH:MM text`` (as the shell ``fase``)."""
        self.cartella.mkdir(parents=True, exist_ok=True)
        with open(self.log, 'a', encoding='utf-8') as f:
            f.write(f'{self.orologio():%d/%m %H:%M} {testo}\n')

    # checked copies
    def manda(self, relativo: str, tentativi: int = 5) -> tuple[str, int]:
        """Send a project file to the same relative path remotely; the remote hash and lines must match."""
        locale = self.radice / relativo
        atteso = impronta_locale(locale)
        for k in range(1, tentativi + 1):
            try:
                self.trasporto.manda(locale, relativo)
                if self.trasporto.impronta(relativo) == atteso:
                    return atteso
                self.fase(f'copia rovinata verso {relativo} (tentativo {k})')
            except CopiaRovinataError as e:
                self.fase(f'{e} (tentativo {k})')
            self.dormi(60)
        raise CopiaRovinataError(f'{relativo}: {tentativi} copie non riuscite')

    def prendi(self, relativo: str, locale: Path, tentativi: int = 5) -> tuple[str, int]:
        """Take a remote file; the local hash and lines must equal the remote ones."""
        atteso = self.trasporto.impronta(relativo)
        if atteso is None:
            raise FileNotFoundError(f'remoto: {relativo}')
        for k in range(1, tentativi + 1):
            try:
                self.trasporto.prendi(relativo, locale)
                if impronta_locale(locale) == atteso:
                    return atteso
                self.fase(f'copia rovinata da {relativo} (tentativo {k})')
            except CopiaRovinataError as e:
                self.fase(f'{e} (tentativo {k})')
            self.dormi(60)
        raise CopiaRovinataError(f'{relativo}: {tentativi} copie non riuscite')

    def remoto(self, comando: str) -> str:
        """A remote command that must succeed."""
        codice, out = self.trasporto.esegui(comando)
        if codice:
            raise RuntimeError(f'remoto, uscita {codice}: {comando[:80]} {out[-300:]}')
        return out

    def locale(self, argv: list[str]) -> None:
        """A local ``trace`` command that must succeed."""
        codice = self.esegui_locale(argv)
        if codice:
            raise RuntimeError(f'trace {" ".join(argv)}: uscita {codice}')

    # running
    def esegui(self) -> bool:
        """Run every step not done yet; returns True if the cycle finished."""
        self.fase('inizio' if not any(self.stato.fatto(p.nome) for p in self.passi) else 'ripresa')
        for p in self.passi:
            if self.stato.fatto(p.nome):
                continue
            s = self.stato.di(p.nome)
            riuscito = False
            while s['tentativi'] < p.tentativi:
                s['tentativi'] += 1
                s['esito'] = 'in corso'
                s['inizio'] = self.orologio().isoformat(timespec='seconds')
                self.stato.salva()
                try:
                    s['dati'] = p.azione(self)
                    riuscito = True
                    break
                except Exception as e:
                    s['errore'] = repr(e)[:500]
                    self.fase(f'{p.nome}: tentativo {s["tentativi"]}/{p.tentativi} fallito: {e!r}'[:400])
                    self.stato.salva()
                    if s['tentativi'] < p.tentativi:
                        self.dormi(p.pausa_s)
            s['fine'] = self.orologio().isoformat(timespec='seconds')
            if not riuscito:
                s['esito'] = 'fallito'
                self.stato.salva()
                self.fase(f'FERMO a {p.nome}: tentativi finiti ({p.tentativi})')
                return False
            s['esito'] = 'fatto'
            s.pop('errore', None)
            self.stato.salva()
            self.fase(f'{p.nome} fatto')
        self.fase('FINITO')
        return True


def _cli_locale(argv: list[str]) -> int:
    from .cli import main

    try:
        return main(argv)
    except SystemExit as e:
        return int(e.code or 0)


# the cycle of the empty readings (tools/ciclo_vuote.sh)

CASI = ('urgenda', 'neubauer', 'future-generations', 'klimaseniorinnen', 'cig-parere-clima', 'idh-oc-32-25')
L05 = {
    'urgenda': 'v2',
    'neubauer': 'P05',
    'future-generations': 'P05',
    'klimaseniorinnen': 'v2',
    'cig-parere-clima': 'P09',
    'idh-oc-32-25': 'v2',
}
L04 = (
    ('urgenda', ''),
    ('urgenda', 'l04nuove'),
    ('neubauer', 'l04P05'),
    ('future-generations', 'l04P05'),
    ('klimaseniorinnen', 'l04nuove'),
    ('cig-parere-clima', 'l04P09'),
    ('idh-oc-32-25', 'l04nuove'),
)
TIPO = {'urgenda': 'v2'}
CODE = {
    'coda-ds2': ('urgenda', 'neubauer'),
    'coda-ds3': ('future-generations', 'klimaseniorinnen', 'cig-parere-clima', 'idh-oc-32-25'),
}
STRUMENTI = (
    'tools/chiamata_deepseek.py',
    'tools/leggi_ripresa.py',
    'tools/leggi_l04.py',
    'tools/classifica_lessicali.py',
    'tools/giudica_llm.py',
    'tools/sonde.py',
)


def _suf(e: str) -> str:
    return f'_{e}' if e else ''


def bersagli() -> list[str]:
    """The reading files re-read by the cycle, in the order of the shell chain (L05, L04, type)."""
    out = [f'training/principi/{c}_ripresa_deepseek{_suf(e)}.jsonl' for c, e in L05.items()]
    out += [f'training/principi/{c}_ripresa_deepseek{_suf(e)}.jsonl' for c, e in L04]
    out += [f'training/lessicali_{c}_deepseek{_suf(TIPO.get(c, ""))}.jsonl' for c in CASI]
    return out


def ingressi() -> list[str]:
    """Every file sent before the readings: rows and readings of each target."""
    out = []
    for c, e in [*L05.items(), *L04]:
        out += [
            f'training/principi/{c}_ripresa_righe{_suf(e)}.jsonl',
            f'training/principi/{c}_ripresa_deepseek{_suf(e)}.jsonl',
        ]
    for c in CASI:
        out += [f'training/lessicali_{c}_righe.jsonl', f'training/lessicali_{c}_deepseek{_suf(TIPO.get(c, ""))}.jsonl']
    return out


def coda(
    nome: str, casi: Sequence[str], paralleli: int = 32, letture: int = LETTURE_PROTOCOLLO, seme: int | None = None
) -> str:
    """The queue script of one DeepSeek job (the shell ``scrivi_coda``).

    ``letture`` is the protocol's 5 since 03/10/2026 (the shell chain of 02/10 wrote 2: ``letture=2`` gives it back);
    with ``--solo-vuote`` a row with fewer readings is brought to ``letture``. ``seme``, when given, goes to every
    reader (and so into every call record and the journal).
    """
    a = (
        '"--base-url http://127.0.0.1:8000/v1 --chiave-file $C/chiave --modello deepseek-v4-flash --paralleli '
        + str(paralleli)
        + (f' --seme {seme}' if seme is not None else '')
        + '"'
    )
    righe = ['H=/lustrehome/climpact/trace; C=$H/chat; cd $H', f'A={a}']
    log = f' >> $C/log/vuote_{nome}.log 2>&1'
    for c in casi:
        if c in L05:
            righe.append(
                f'$H/venv/bin/python -u tools/leggi_ripresa.py leggi --caso {c} --etichetta {L05[c]} '
                f'--letture {letture} --solo-vuote $A{log}'
            )
        for cc, e in L04:
            if cc == c:
                righe.append(
                    f"$H/venv/bin/python -u tools/leggi_l04.py leggi --caso {c} --etichetta '{e}' --letture {letture} "
                    f'--solo-vuote $A{log}'
                )
        righe.append(
            f'$H/venv/bin/python -u tools/classifica_lessicali.py leggi --caso {c} --gruppo tutte --letture {letture} '
            f"--etichetta '{TIPO.get(c, '')}' --solo-vuote $A" + log
        )
    righe.append(f'echo FINITO > $C/log/vuote_{nome}_fine.txt')
    return '\n'.join(righe) + '\n'


def per_id(p: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    with open(p, encoding='utf-8') as f:
        for riga in f:
            x = json.loads(riga)
            out[x['id']] = x
    return out


def letture_vuote(righe: Mapping[str, Mapping[str, Any]]) -> int:
    return sum(1 for x in righe.values() for y in x.get('letture') or [] if vuota(y))


class CicloVuote(Orchestratore):
    """``tools/ciclo_vuote.sh`` as declared steps.

    Args:
        radice: the project root.
        trasporto: ReCaS (or the fake).
        attesa_s: seconds between two looks at the queues.
        massimo_attese: looks before giving up the wait step (a failed wait can be resumed).
        letture: readings per row asked of the readers (default: the protocol's 5; the shell chain wrote 2).
        seme: the sampling seed passed to the readers, when given; it is also written in the cycle state.
        Other arguments: see :class:`Orchestratore`.
    """

    def __init__(
        self,
        radice: Path | str,
        trasporto: Trasporto,
        attesa_s: float = 120,
        massimo_attese: int = 1440,
        letture: int = LETTURE_PROTOCOLLO,
        seme: int | None = None,
        **kw: Any,
    ) -> None:
        self.attesa_s = attesa_s
        self.massimo_attese = massimo_attese
        self.letture = letture
        self.seme = seme
        passi = [
            Passo('copia_di_sicurezza', CicloVuote.copia_di_sicurezza, tentativi=3),
            Passo('manda_strumenti', CicloVuote.manda_strumenti, tentativi=3),
            Passo('manda_file', CicloVuote.manda_file, tentativi=3),
            Passo('scrivi_code', CicloVuote.scrivi_code, tentativi=3),
            Passo('attendi_letture', CicloVuote.attendi_letture, tentativi=3),
            Passo('riprendi_file', CicloVuote.riprendi_file, tentativi=3),
        ]
        for c in CASI:
            passi += [
                Passo(f'estrai_rifatte_{c}', _per_caso(CicloVuote.estrai_rifatte, c)),
                Passo(f'carica_tipo_{c}', _per_caso(CicloVuote.carica_tipo, c), tentativi=3),
                Passo(f'carica_ripresa_{c}', _per_caso(CicloVuote.carica_ripresa, c), tentativi=3),
            ]
        passi += [
            Passo('controllo_completezza', CicloVuote.controllo_completezza, tentativi=3),
            Passo('controllo_finestra', CicloVuote.controllo_finestra),
        ]
        super().__init__('ciclo_vuote', radice, trasporto, passi, **kw)

    def copia_di_sicurezza(self) -> None:
        self.remoto(
            'mkdir -p ~/trace/training/principi/prima-vuote ~/trace/training/prima-vuote; '
            'cp ~/trace/training/principi/*_ripresa_deepseek*.jsonl ~/trace/training/principi/prima-vuote/ '
            '2>/dev/null; '
            'cp ~/trace/training/lessicali_*_deepseek*.jsonl ~/trace/training/prima-vuote/ 2>/dev/null; true'
        )

    def manda_strumenti(self) -> dict[str, Any]:
        return {f: self.manda(f)[0] for f in STRUMENTI}

    def manda_file(self) -> dict[str, Any]:
        return {f: list(self.manda(f)) for f in dict.fromkeys(ingressi())}

    def scrivi_code(self) -> dict[str, Any]:
        self.remoto('rm -f ~/trace/chat/log/vuote_coda-ds2_fine.txt ~/trace/chat/log/vuote_coda-ds3_fine.txt')
        for nome, casi in CODE.items():
            self.trasporto.scrivi(
                f'chat/{nome}/vuote_{nome}.sh', coda(nome, casi, letture=self.letture, seme=self.seme)
            )
        return {'letture': self.letture, 'seme': self.seme}

    def attendi_letture(self) -> int:
        prova = ' && '.join(f'test -s ~/trace/chat/log/vuote_{n}_fine.txt' for n in CODE)
        for k in range(1, self.massimo_attese + 1):
            if self.trasporto.esegui(prova)[0] == 0:
                return k
            self.dormi(self.attesa_s)
        raise TimeoutError(f'code non finite dopo {self.massimo_attese} sguardi')

    def riprendi_file(self) -> dict[str, Any]:
        """Take each file back only if it has the same rows and no more empty readings (backup kept)."""
        esiti = {}
        for rel in bersagli():
            f = self.radice / rel
            nuovo = f.with_suffix('.nuovo')
            self.prendi(rel, nuovo)
            a, b = per_id(f), per_id(nuovo)
            va, vb = letture_vuote(a), letture_vuote(b)
            ok = set(a) == set(b) and vb <= va
            self.fase(f'{f.name} righe {len(a)} -> {len(b)} | letture vuote {va} -> {vb} {"OK" if ok else "NON PRESO"}')
            if ok:
                shutil.copy(f, str(f) + '.prima-vuote')
                shutil.move(str(nuovo), f)
            esiti[rel] = {'righe': [len(a), len(b)], 'vuote': [va, vb], 'preso': ok}
        return esiti

    def estrai_rifatte(self, caso: str) -> int:
        e = TIPO.get(caso, '')
        tutte = per_id(self.radice / f'training/lessicali_{caso}_deepseek{_suf(e)}.jsonl')
        rifatte = [x for x in tutte.values() if x.get('rifatte_vuote')]
        with open(self.radice / f'training/lessicali_{caso}_deepseek_vuote.jsonl', 'w', encoding='utf-8') as f:
            f.writelines(json.dumps(x, ensure_ascii=False) + '\n' for x in rifatte)
        return len(rifatte)

    def carica_tipo(self, caso: str) -> None:
        self.locale(['carica', 'tipo', '--caso', caso, '--etichetta', 'vuote', '--sovrascrivi', '--scrivi'])

    def carica_ripresa(self, caso: str) -> None:
        self.locale(['carica', 'ripresa', '--caso', caso, '--principi-da-l04', '--scrivi'])

    def controllo_completezza(self) -> None:
        self.locale(['controlla', 'completezza', '--scrivi'])

    def controllo_finestra(self) -> int:
        # as the shell chain: the result is logged, an incomplete window does not stop the cycle
        return self.esegui_locale(['controlla', 'finestra'])


class CicloPulizie(Orchestratore):
    """The clean-up steps that follow the name search, as declared steps (5 October 2026).

    In the order of the cycle: C03 (body text and footnote, translations: :class:`tracepipe.unione_c03.UnioneC03`),
    C07 (a surrounding page that is a citation of its own: :class:`tracepipe.pagine_gia_citate.ApplicaC07`), the
    completeness check. Every step is a local ``trace`` command; the remote machine is not used. By default every
    step is a PREVIEW (no ``--scrivi``): the writes to the platform are asked for explicitly with ``scrivi=True``, as
    everywhere else. S08 (the close pairs) comes BEFORE these steps in the cycle but waits for the readings of L13 on
    ReCaS: it is run with ``trace coppie ...`` once they are there.

    Args:
        radice: the project root.
        da: who runs the steps (``esclusa_da``, ``c03_da``, ``c07_da``).
        scrivi: write to the platform (adds ``--scrivi`` to the three steps).
        rivisto: the list of the C03 pairs reread by hand (``--rivisto``).
        rilette: the C07 pages reread by hand (``--rilette``).
        spunte_team: the by-hand review of the pages ticked by the team (``--spunte-team``).
        Other arguments: see :class:`Orchestratore`.
    """

    def __init__(
        self,
        radice: Path | str,
        da: str,
        scrivi: bool = False,
        rivisto: str = '',
        rilette: str = '',
        spunte_team: str = '',
        trasporto: Trasporto | None = None,
        **kw: Any,
    ) -> None:
        self.da = da
        self.scrivi = scrivi
        self.rivisto = rivisto
        self.rilette = rilette
        self.spunte_team = spunte_team
        passi = [
            Passo('c03', CicloPulizie.c03),
            Passo('c07', CicloPulizie.c07),
            Passo('controllo_completezza', CicloPulizie.controllo_completezza, tentativi=3),
        ]
        super().__init__(
            'ciclo_pulizie', radice, trasporto or TrasportoFinto(Path(radice) / 'giornale' / 'nessuno'), passi, **kw
        )

    def _scrivi(self) -> list[str]:
        return ['--scrivi'] if self.scrivi else []

    def c03(self) -> None:
        argv = ['c03', '--da', self.da]
        self.locale([*argv, *(['--rivisto', self.rivisto] if self.rivisto else []), *self._scrivi()])

    def c07(self) -> None:
        argv = ['c07', '--da', self.da]
        argv += ['--rilette', self.rilette] if self.rilette else []
        argv += ['--spunte-team', self.spunte_team] if self.spunte_team else []
        self.locale([*argv, *self._scrivi()])

    def controllo_completezza(self) -> None:
        self.locale(['controlla', 'completezza', *self._scrivi()])


def _per_caso(f: Callable[[Any, str], Any], caso: str) -> Callable[[Orchestratore], Any]:
    return lambda o: f(o, caso)
