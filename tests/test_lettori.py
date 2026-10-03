"""The readers: prompts byte-identical to the live builders, same records, ``--solo-vuote``, order, k readings.

Two references:

- the prompts the harness recorded for every sample row (``prove/attesi/0[567]_*/deepseek_prompt.jsonl``, written by
  the live builders through the fake DeepSeek);
- the live ``leggi`` functions themselves, run on a synthetic root under ``tmp_path`` with a scripted DeepSeek client:
  the harness copy (commit 8650281) against ``compat=True``, today's ``tools/`` against ``compat=False``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import threading
import time
import types
from pathlib import Path
from typing import Any

import pytest
from conftest import ATTESI, CAMPIONE, CASI, attesi_file, attesi_jsonl, richiede_attesi, richiede_campione

from tracepipe.config import Config
from tracepipe.deepseek import ClienteDeepSeek
from tracepipe.istruzioni import MODULO_PAGINE_ATTORNO, MODULO_PRINCIPI, MODULO_TIPO, blocchi_codebook, modulo_tipo
from tracepipe.lettori import LettorePagineAttorno, LettorePrincipi, LettoreTipo, ordine_conservato

# the instructions


@richiede_campione
def test_istruzioni_come_gli_strumenti(vivi, vivi_oggi) -> None:
    for mod in (vivi, vivi_oggi):
        cl, lr, l4 = mod('classifica_lessicali'), mod('leggi_ripresa'), mod('leggi_l04')
        assert cl.MODULO == MODULO_TIPO
        assert lr.MODULO == MODULO_PAGINE_ATTORNO
        assert l4.istruzioni_l04() == MODULO_PRINCIPI
    cl = vivi('classifica_lessicali')
    cb = cl.codebook()
    assert blocchi_codebook(cb[0]) == cb[1:]
    import yaml

    for caso in CASI:
        conf = yaml.safe_load((CAMPIONE / 'cited-cases' / f'{caso}.yaml').read_text(encoding='utf-8'))
        assert modulo_tipo(caso, conf) == cl.modulo(caso)


# prompts of every sample row, as recorded by the harness

PASSI = {
    '05': ('05_classifica_leggi', 'rif'),
    '06': ('06_leggi_ripresa_leggi', 'rif'),
    '07': ('07_leggi_l04_leggi', 'rifl04'),
}


def _lettore(passo: str, caso: str) -> Any:
    config = Config(radice=CAMPIONE)
    cli = ClienteDeepSeek(None, 'deepseek-v4-flash')
    if passo == '05':
        return LettoreTipo(config, caso, cli, gruppo='tutte', etichetta='rif')
    if passo == '06':
        return LettorePagineAttorno(config, caso, cli, etichetta='rif')
    return LettorePrincipi(config, caso, cli, etichetta='rifl04')


def _righe_del_banco(passo: str, caso: str) -> list[dict[str, Any]]:
    if passo == '05':
        return attesi_jsonl(attesi_file(f'01_classifica_prepara_{caso}', f'training/lessicali_{caso}_righe.jsonl'))
    suf = (
        '_' + Config(radice=CAMPIONE).serie(caso)
        if caso in ('neubauer', 'future-generations', 'cig-parere-clima')
        else ''
    )
    return attesi_jsonl(
        attesi_file(f'04_leggi_ripresa_prepara_{caso}', f'training/principi/{caso}_ripresa_righe{suf}.jsonl')
    )


@richiede_attesi
@pytest.mark.parametrize('caso', CASI)
@pytest.mark.parametrize('passo', sorted(PASSI))
def test_prompt_identici_per_ogni_riga_del_campione(passo: str, caso: str) -> None:
    nome, _ = PASSI[passo]
    registrati = attesi_jsonl(ATTESI / f'{nome}_{caso}' / 'deepseek_prompt.jsonl')
    per_riga: dict[str, set[str]] = {}
    for x in registrati:
        per_riga.setdefault(x['riga'], set()).add(x['testo'])
    lettore = _lettore(passo, caso)
    lettore.prepara()
    righe = _righe_del_banco(passo, caso)
    assert len(righe) == len(per_riga)
    for r in righe:
        assert per_riga[r['id']] == {lettore.prompt(r)}, r['id']


@richiede_campione
def test_prompt_tipo_come_il_costruttore_vivo(vivi) -> None:
    """The type builder is a plain function live: compared on every row of the sample files."""
    cl = vivi('classifica_lessicali')
    cb = cl.codebook()
    for caso in CASI:
        lettore = LettoreTipo(Config(radice=CAMPIONE), caso, ClienteDeepSeek(None, 'm'))
        lettore.prepara()
        fascicolo = (CAMPIONE / 'cited-cases' / f'{caso}-fascicolo.md').read_text(encoding='utf-8')
        for riga in (CAMPIONE / 'training' / f'lessicali_{caso}_righe.jsonl').read_text(encoding='utf-8').split('\n'):
            if not riga:
                continue
            r = json.loads(riga)
            assert lettore.prompt(r) == cl.prompt(r, fascicolo, cb, caso)


# the live readers against the package, on a synthetic root


class ClienteCopione:
    """A deterministic DeepSeek: the answer depends only on the prompt and on how many times it was asked.

    In round 1 some prompts get empty answers until the high cap is spent (the reading is saved empty); in round 2
    every answer is good. Small deterministic sleeps shuffle the order in which the threads finish.
    """

    def __init__(self, tipo: str, giro: int = 1) -> None:
        self.tipo, self.giro = tipo, giro
        self.n: dict[str, int] = {}
        self.blocco = threading.Lock()
        self.ricevute: list[dict[str, Any]] = []
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self.create))

    def create(self, model: str, messages: list[dict[str, str]], max_tokens: int, extra_body: Any, **kw: Any) -> Any:
        testo = messages[0]['content']
        with self.blocco:
            k = self.n.get(testo, 0)
            self.n[testo] = k + 1
            self.ricevute.append({'max_tokens': max_tokens, 'extra_body': extra_body, **kw})
        h = int(hashlib.sha256(f'{testo}|{k}'.encode()).hexdigest(), 16)
        hp = int(hashlib.sha256(testo.encode()).hexdigest(), 16)
        time.sleep((h % 5) / 1000)
        vuota = (self.giro == 1 and hp % 3 == 0 and k < 4) or (h % 7 == 0)
        rag = 'r' * (h % 9000)
        if vuota:
            contenuto, fine = '', 'length'
        elif self.tipo == 'tipo':
            tipi = ['menzione_in_catena', 'descrittiva', 'sostanziale']
            if h % 11 == 0:  # broken JSON: unescaped quotes, recovered field by field
                contenuto = '{"tipo_citazione": "sostanziale", "proposizione": "dice "x" e altro", "motivo": "m"}'
            else:
                contenuto = json.dumps(
                    {
                        'riferimento': 'caso',
                        'tipo_citazione': tipi[h % 3],
                        'chi_parla': 'parte',
                        'proposizione': f'p{h % 100}',
                        'motivo': 'perche',
                    }
                )
            fine = 'stop'
        else:
            contenuto = json.dumps(
                {
                    'frase_sostenuta': 'f',
                    'principi': [f'p{h % 3}'],
                    'altro': '',
                    'motivo': 'm',
                    'vicine': [{'pagina': 1, 'prosegue': bool(h % 2), 'principio': '', 'prova': 'x'}],
                }
            )
            fine = 'stop'
        msg = types.SimpleNamespace(content=contenuto, reasoning_content=rag, model_extra={})
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=msg, finish_reason=fine)],
            usage=types.SimpleNamespace(prompt_tokens=len(testo) // 4, completion_tokens=h % 8000),
        )


def _radice(tmp: Path, caso: str, n: int = 9) -> Path:
    """A root with the sample case files and codebook (links) and ``n`` sample rows of the case."""
    r = tmp / 'radice'
    (r / 'training' / 'principi').mkdir(parents=True)
    (r / 'chat').mkdir()
    (r / 'chat' / 'chiave').write_text('finta\n')
    for d in ('cited-cases', 'codebook'):
        (r / d).symlink_to(CAMPIONE / d)
    righe = _righe_del_banco('05', caso)[:n]
    with open(r / 'training' / f'lessicali_{caso}_righe.jsonl', 'w', encoding='utf-8') as f:
        for x in righe:
            f.write(json.dumps(x, ensure_ascii=False) + '\n')
    righe = _righe_del_banco('06', caso)[:n]
    for e in ('', '_rif', '_l04nuove'):
        with open(r / 'training' / 'principi' / f'{caso}_ripresa_righe{e}.jsonl', 'w', encoding='utf-8') as f:
            for x in righe:
                f.write(json.dumps(x, ensure_ascii=False) + '\n')
    return r


def _argomenti(radice: Path, caso: str, **kw: Any) -> argparse.Namespace:
    a = {
        'caso': caso,
        'chiave_file': str(radice / 'chat' / 'chiave'),
        'base_url': 'http://127.0.0.1:9/v1',
        'modello': 'deepseek-v4-flash',
        'letture': 2,
        'paralleli': 4,
        'solo_vuote': False,
        'gruppo': 'tutte',
        'solo_id': '',
        'max_righe': 0,
        'kwargs_modello': '',
        'sforzo': 'low',
        'etichetta': '',
        'uscita_suffisso': '',
        'temperatura': None,
        'seme': None,
    }
    a.update(kw)
    return argparse.Namespace(**a)


def _vivo(monkeypatch, moduli, cliente: ClienteCopione, quale: str, radice: Path, a: argparse.Namespace) -> Path:
    """Run a live ``leggi`` with its root moved to ``radice`` and the scripted client; returns the output file."""
    so = moduli['sonde']
    monkeypatch.setattr(so, 'QUI', radice)
    monkeypatch.setitem(sys.modules, 'openai', types.SimpleNamespace(OpenAI=lambda **kw: cliente))
    monkeypatch.setitem(sys.modules, 'chiamata_deepseek', moduli['chiamata_deepseek'])
    monkeypatch.setattr(moduli['chiamata_deepseek'].time, 'sleep', lambda s: None)
    if quale == 'tipo':
        cl = moduli['classifica_lessicali']
        uscita = radice / 'training' / f'lessicali_{a.caso}_deepseek{"_" + a.etichetta if a.etichetta else ""}.jsonl'
        monkeypatch.setattr(cl, 'QUI', radice)
        monkeypatch.setattr(cl, 'RIGHE', radice / 'training' / f'lessicali_{a.caso}_righe.jsonl')
        monkeypatch.setattr(cl, 'USCITA', uscita)
        assert tmp_sotto(uscita, radice)
        cl.leggi(a)
        return uscita
    lr = moduli['leggi_ripresa']
    monkeypatch.setattr(lr, 'QUI', radice)
    monkeypatch.setattr(lr, 'P', radice / 'training' / 'principi')
    if quale == 'principi':
        monkeypatch.setattr(lr, 'MODULO', moduli['leggi_l04'].istruzioni_l04(MODULO_PAGINE_ATTORNO))
    suf = f'_{a.etichetta}' if a.etichetta else ''
    uscita = radice / 'training' / 'principi' / f'{a.caso}_ripresa_deepseek{suf}{a.uscita_suffisso}.jsonl'
    assert tmp_sotto(uscita, radice)
    lr.leggi(a)
    return uscita


def tmp_sotto(p: Path, radice: Path) -> bool:
    return radice in p.parents


def _pacchetto(quale: str, radice: Path, cliente: ClienteCopione, compat: bool, a: argparse.Namespace) -> Path:
    cli = ClienteDeepSeek(
        cliente, a.modello, temperature=a.temperatura, seed=a.seme, dormi=lambda s: None, compat=compat
    )
    kw = {
        'letture': a.letture,
        'paralleli': a.paralleli,
        'etichetta': a.etichetta,
        'solo_vuote': a.solo_vuote,
        'compat': compat,
        'stampa': lambda s: None,
    }
    config = Config(radice=radice)
    if quale == 'tipo':
        lettore = LettoreTipo(config, a.caso, cli, gruppo=a.gruppo, **kw)
    elif quale == 'principi':
        lettore = LettorePrincipi(config, a.caso, cli, **kw)
    else:
        lettore = LettorePagineAttorno(config, a.caso, cli, **kw)
    lettore.esegui()
    return lettore.file_uscita


def _leggi(f: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in f.read_text(encoding='utf-8').split('\n') if x]


@pytest.fixture
def moduli_banco(vivi) -> dict[str, Any]:
    return {n: vivi(n) for n in ('sonde', 'chiamata_deepseek', 'classifica_lessicali', 'leggi_ripresa', 'leggi_l04')}


@pytest.fixture
def moduli_oggi(vivi, vivi_oggi) -> dict[str, Any]:
    out = {n: vivi_oggi(n) for n in ('chiamata_deepseek', 'classifica_lessicali', 'leggi_ripresa', 'leggi_l04')}
    out['sonde'] = vivi('sonde')
    return out


CASI_PROVA = [
    ('tipo', 'neubauer', ''),
    ('tipo', 'urgenda', 'rif'),
    ('pagine-attorno', 'neubauer', 'rif'),
    ('pagine-attorno', 'urgenda', ''),
    ('principi', 'future-generations', 'l04nuove'),
]


@richiede_attesi
@pytest.mark.parametrize(('quale', 'caso', 'etichetta'), CASI_PROVA)
@pytest.mark.parametrize('letture', [2, 3])
def test_come_il_lettore_del_banco(monkeypatch, moduli_banco, tmp_path, quale, caso, etichetta, letture) -> None:
    """compat=True: the same lines, in the same order, as the harness readers; then ``--solo-vuote`` the same."""
    rv, rp = _radice(tmp_path / 'v', caso), _radice(tmp_path / 'p', caso)
    a = _argomenti(rv, caso, etichetta=etichetta, letture=letture)
    fv = _vivo(monkeypatch, moduli_banco, ClienteCopione(quale), quale, rv, a)
    fp = _pacchetto(quale, rp, ClienteCopione(quale), True, _argomenti(rp, caso, etichetta=etichetta, letture=letture))
    vivo, nuovo = _leggi(fv), _leggi(fp)
    assert nuovo == vivo
    assert any(y.get('grezzo') == '' for x in vivo for y in x['letture']), 'the script leaves some readings empty'
    assert all(len(x['letture']) == letture for x in nuovo)
    # the second round redoes only the empty readings, keeps the good ones, appends the rewritten rows
    a2 = _argomenti(rv, caso, etichetta=etichetta, letture=letture, solo_vuote=True)
    _vivo(monkeypatch, moduli_banco, ClienteCopione(quale, giro=2), quale, rv, a2)
    _pacchetto(
        quale,
        rp,
        ClienteCopione(quale, giro=2),
        True,
        _argomenti(rp, caso, etichetta=etichetta, letture=letture, solo_vuote=True),
    )
    vivo2, nuovo2 = _leggi(fv), _leggi(fp)
    assert nuovo2 == vivo2
    rifatte = vivo2[len(vivo) :]
    assert rifatte and all('rifatte_vuote' in x for x in rifatte)


@richiede_attesi
@pytest.mark.parametrize(('quale', 'caso', 'etichetta'), CASI_PROVA)
def test_come_il_lettore_di_oggi(monkeypatch, moduli_oggi, tmp_path, quale, caso, etichetta) -> None:
    """compat=False against today's tools/: identical lines, call record and tokens included.

    On 02/10/2026 evening the live readers had ``tok.append(...)`` / ``chiamate.append(...)`` swallowed by a
    comment; fixed the same evening, so the live readers and the package must now write the same records.
    """
    rv, rp = _radice(tmp_path / 'v', caso), _radice(tmp_path / 'p', caso)
    kw = {'etichetta': etichetta, 'temperatura': 0.0, 'seme': 7}
    fv = _vivo(monkeypatch, moduli_oggi, ClienteCopione(quale), quale, rv, _argomenti(rv, caso, **kw))
    cp = ClienteCopione(quale)
    fp = _pacchetto(quale, rp, cp, False, _argomenti(rp, caso, **kw))
    vivo, nuovo = _leggi(fv), _leggi(fp)
    assert nuovo == vivo
    for x in nuovo:
        assert len(x['chiamate']) == 2
        for c in x['chiamate']:
            assert list(c)[-3:] == ['modello', 'istruzioni_sha256', 'parametri']
            assert c['parametri']['temperature'] == 0.0 and c['parametri']['seed'] == 7
    assert all(r['temperature'] == 0.0 and r['seed'] == 7 for r in cp.ricevute)
    # the reasoning is saved whole
    assert any(len(r) > 6000 for x in nuovo for r in x['ragionamenti'])


@richiede_attesi
def test_ordine_dei_fili_e_righe_scelte(tmp_path) -> None:
    """Many threads, shuffled finishing order: the lines follow the input rows; group, ids and max rows filter."""
    r = _radice(tmp_path, 'neubauer', n=20)
    righe = _leggi(r / 'training' / 'lessicali_neubauer_righe.jsonl')
    f = _pacchetto('tipo', r, ClienteCopione('tipo'), False, _argomenti(r, 'neubauer', paralleli=16))
    uscita = _leggi(f)
    assert [x['id'] for x in uscita] == [x['id'] for x in righe]
    assert ordine_conservato(righe, uscita)
    # a second run does nothing: every row is done
    _pacchetto('tipo', r, ClienteCopione('tipo'), False, _argomenti(r, 'neubauer'))
    assert len(_leggi(f)) == len(righe)
    ids = r / 'ids.txt'
    ids.write_text('\n'.join(x['id'] for x in righe[:3]))
    cli = ClienteDeepSeek(ClienteCopione('tipo'), 'm', dormi=lambda s: None)
    t = LettoreTipo(Config(radice=r), 'neubauer', cli, gruppo='validate', solo_id=str(ids), stampa=lambda s: None)
    assert all(x['gruppo'] == 'validate' and x['id'] in ids.read_text() for x in t.righe())
    t = LettoreTipo(Config(radice=r), 'neubauer', cli, gruppo='tutte', max_righe=4, stampa=lambda s: None)
    assert len(t.righe()) == 4


@richiede_attesi
def test_righe_a_schermo(tmp_path) -> None:
    r = _radice(tmp_path, 'neubauer', n=5)
    righe: list[str] = []
    cli = ClienteDeepSeek(ClienteCopione('L05'), 'm', dormi=lambda s: None)
    t = iter([0.0, 3.4])
    LettorePagineAttorno(
        Config(radice=r), 'neubauer', cli, etichetta='rif', stampa=righe.append, orologio=lambda: next(t)
    ).esegui()
    assert righe == ['5 righe, 0 fatte, 5 da fare', 'fatto in 3s']


def test_lettura_tenuta_come_vivo() -> None:
    """The live idioms for the readings kept by ``--solo-vuote`` (missing lists, short lists, empty readings)."""
    cli = ClienteDeepSeek(None, 'm')
    t = LettoreTipo(Config(radice=Path('/x')), 'urgenda', cli)
    p = LettorePagineAttorno(Config(radice=Path('/x')), 'urgenda', cli)
    buona, vuota = {'tipo_citazione': 'descrittiva'}, {'esito': 'ILLEGGIBILE', 'grezzo': ''}
    assert t.lettura_tenuta({'letture': [buona]}, 0) == (buona, '', 0, {'tenuta': True})
    assert t.lettura_tenuta({'letture': [buona, vuota]}, 1) is None
    assert t.lettura_tenuta({'letture': [buona]}, 1) is None
    assert p.lettura_tenuta({'letture': [buona], 'chiamate': [None]}, 0) == (buona, '', {'tenuta': True})
    assert p.lettura_tenuta({'letture': [buona], 'ragionamenti': ['r'], 'chiamate': [{'x': 1}]}, 0) == (
        buona,
        'r',
        {'x': 1},
    )
    assert p.lettura_tenuta({'letture': [vuota]}, 0) is None


# --aggiungi-letture (02/10/2026): top every row up to k valid readings of the very same prompt


@richiede_attesi
@pytest.mark.parametrize(('quale', 'caso', 'etichetta'), CASI_PROVA)
def test_aggiungi_letture_come_il_lettore_di_oggi(monkeypatch, moduli_oggi, tmp_path, quale, caso, etichetta) -> None:
    """Round 1: two readings (some empty); round 2 with ``--aggiungi-letture --letture 5``: the valid readings of the
    same prompt are kept, the rest added, a reading of another prompt is not kept. Live and package identical."""
    rv, rp = _radice(tmp_path / 'v', caso), _radice(tmp_path / 'p', caso)
    fv = _vivo(monkeypatch, moduli_oggi, ClienteCopione(quale), quale, rv, _argomenti(rv, caso, etichetta=etichetta))
    fp = _pacchetto(quale, rp, ClienteCopione(quale), False, _argomenti(rp, caso, etichetta=etichetta))
    assert _leggi(fp) == _leggi(fv)
    # one reading of the first row made with another prompt: it must not be kept
    for f in (fv, fp):
        righe = _leggi(f)
        righe[0]['chiamate'][0] = dict(righe[0]['chiamate'][0], istruzioni_sha256='altra domanda')
        f.write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in righe), encoding='utf-8')
    prima = _leggi(fv)
    kw = {'etichetta': etichetta, 'letture': 5, 'aggiungi_letture': True}
    _vivo(monkeypatch, moduli_oggi, ClienteCopione(quale, giro=2), quale, rv, _argomenti(rv, caso, **kw))
    cli = ClienteDeepSeek(ClienteCopione(quale, giro=2), 'deepseek-v4-flash', dormi=lambda s: None)
    config = Config(radice=rp)
    gen = {'letture': 5, 'paralleli': 4, 'etichetta': etichetta, 'aggiungi_letture': True, 'stampa': lambda s: None}
    if quale == 'tipo':
        LettoreTipo(config, caso, cli, gruppo='tutte', **gen).esegui()
    elif quale == 'principi':
        LettorePrincipi(config, caso, cli, **gen).esegui()
    else:
        LettorePagineAttorno(config, caso, cli, **gen).esegui()
    vivo, nuovo = _leggi(fv), _leggi(fp)
    assert nuovo == vivo
    aggiunte = vivo[len(prima) :]
    assert len(aggiunte) == len(prima)
    for vecchia, x in zip(prima, aggiunte, strict=True):
        assert len(x['letture']) == 5 and len(x['chiamate']) == 5
        buone = [y for y in vecchia['letture'] if not (isinstance(y, dict) and y.get('grezzo') == '')]
        scartata = vecchia is prima[0] and x['aggiunte']['scartate_domanda_cambiata'] == 1
        assert x['aggiunte']['tenute'] == len(buone) - (1 if scartata else 0)
        assert x['aggiunte']['nuove'] == 5 - x['aggiunte']['tenute']
    assert aggiunte[0]['aggiunte']['scartate_domanda_cambiata'] in (0, 1)
    # a third round finds every row complete
    _vivo(monkeypatch, moduli_oggi, ClienteCopione(quale, giro=2), quale, rv, _argomenti(rv, caso, **kw))
    assert len(_leggi(fv)) == len(vivo)


def test_aggiungi_e_solo_vuote_insieme_no() -> None:
    with pytest.raises(ValueError):
        LettoreTipo(
            Config(radice=Path('/x')), 'urgenda', ClienteDeepSeek(None, 'm'), solo_vuote=True, aggiungi_letture=True
        )
