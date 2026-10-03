"""ClienteDeepSeek: same attempts, same record as tools/chiamata_deepseek.chiama, plus the request record."""

from __future__ import annotations

import copy
from types import SimpleNamespace
from typing import Any

import pytest

from tracepipe.config import LimitiDeepSeek
from tracepipe.deepseek import ClienteDeepSeek, impronta


class _RispostaError(Exception):
    pass


class _ClienteFinto:
    """Answers from a script: each step is an answer ``(content, finish_reason, tokens)`` or an exception."""

    def __init__(self, copione: list[Any], prompt_token: int | None = 1000) -> None:
        self.copione = list(copione)
        self.prompt_token = prompt_token
        self.chiamate: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw: Any) -> Any:
        self.chiamate.append(copy.deepcopy(kw))
        passo = self.copione.pop(0) if self.copione else ('', 'length', 8000)
        if isinstance(passo, Exception):
            raise passo
        contenuto, fine, token = passo
        msg = SimpleNamespace(content=contenuto, reasoning_content='ragiono', model_extra={})
        return SimpleNamespace(
            choices=[SimpleNamespace(message=msg, finish_reason=fine)],
            usage=SimpleNamespace(prompt_tokens=self.prompt_token, completion_tokens=token),
        )


EXTRA = {'chat_template_kwargs': {'thinking': True, 'reasoning_effort': 'low'}}
VUOTA = ('', 'length', 8000)
BUONA = ('{"principi": []}', 'stop', 300)
COPIONI = {
    'subito': ([BUONA], 1000),
    'seconda': ([VUOTA, BUONA], 1000),
    'tetto_alto': ([VUOTA, VUOTA, VUOTA, BUONA], 1000),
    'tetto_alto_limitato': ([VUOTA, VUOTA, VUOTA, BUONA], 55000),
    'niente_spazio': ([VUOTA, VUOTA, VUOTA, BUONA], 60000),
    'vuota_stop': ([('', 'stop', 10), ('', 'stop', 10), ('', 'stop', 10), BUONA], 1000),
    'tutto_vuoto': ([VUOTA] * 5, 1000),
    'errori_rete': ([_RispostaError('rete'), _RispostaError('rete'), BUONA], 1000),
    'tentativo_perso': ([_RispostaError('x')] * 5 + [VUOTA, VUOTA], 1000),
    'tutto_perso': ([_RispostaError('x')] * 15, 1000),
    'senza_usage': ([VUOTA, VUOTA, VUOTA, BUONA], None),
}


@pytest.mark.parametrize('nome', sorted(COPIONI))
def test_come_chiamata_deepseek_del_banco(vivi, monkeypatch: pytest.MonkeyPatch, nome: str) -> None:
    """compat=True: the record of the harness copy of ``tools/chiamata_deepseek.py`` (commit 8650281)."""
    cd = vivi('chiamata_deepseek')
    monkeypatch.setattr(cd.time, 'sleep', lambda s: None)
    copione, pt = COPIONI[nome]
    vivo_cli, nuovo_cli = _ClienteFinto(copione, pt), _ClienteFinto(copione, pt)
    atteso = cd.chiama(vivo_cli, 'deepseek-v4-flash', 'domanda', EXTRA)
    pause: list[float] = []
    nuovo = ClienteDeepSeek(nuovo_cli, 'deepseek-v4-flash', EXTRA, dormi=pause.append, compat=True).chiama('domanda')
    assert {k: v for k, v in nuovo.items() if k != 'richiesta'} == atteso
    assert nuovo_cli.chiamate == vivo_cli.chiamate
    assert pause == [5.0 * (i % 5 + 1) for i in range(len(pause))]


@pytest.mark.parametrize('nome', sorted(COPIONI))
@pytest.mark.parametrize(('temperatura', 'seme'), [(None, None), (0.0, 1234), (0.6, None)])
def test_come_chiamata_deepseek_di_oggi(
    vivi_oggi, monkeypatch: pytest.MonkeyPatch, nome: str, temperatura: float | None, seme: int | None
) -> None:
    """compat=False: the record of today's ``tools/chiamata_deepseek.py`` (temperature, seed, prompt hash, params)."""
    cd = vivi_oggi('chiamata_deepseek')
    monkeypatch.setattr(cd.time, 'sleep', lambda s: None)
    copione, pt = COPIONI[nome]
    vivo_cli, nuovo_cli = _ClienteFinto(copione, pt), _ClienteFinto(copione, pt)
    atteso = cd.chiama(vivo_cli, 'deepseek-v4-flash', 'domanda', EXTRA, temperatura=temperatura, seme=seme)
    nuovo = ClienteDeepSeek(
        nuovo_cli, 'deepseek-v4-flash', EXTRA, temperature=temperatura, seed=seme, dormi=lambda s: None
    ).chiama('domanda')
    assert {k: v for k, v in nuovo.items() if k != 'richiesta'} == atteso
    assert list(nuovo['chiamata']) == list(atteso['chiamata'])
    assert nuovo_cli.chiamate == vivo_cli.chiamate


def test_registro_della_richiesta() -> None:
    cli = _ClienteFinto([BUONA])
    x = ClienteDeepSeek(cli, 'deepseek-v4-flash', EXTRA, temperature=0.0, seed=7).chiama('domanda')
    assert x['richiesta'] == {
        'modello': 'deepseek-v4-flash',
        'prompt_sha256': impronta('domanda'),
        'prompt_caratteri': 7,
        'temperature': 0.0,
        'seed': 7,
        'max_tokens': 8000,
        'extra_body': EXTRA,
    }
    assert cli.chiamate[0]['temperature'] == 0.0
    assert cli.chiamate[0]['seed'] == 7


def test_senza_temperatura_e_seme_non_si_mandano() -> None:
    cli = _ClienteFinto([BUONA])
    ClienteDeepSeek(cli, 'm').chiama('d')
    assert set(cli.chiamate[0]) == {'model', 'messages', 'max_tokens', 'extra_body'}


def test_tetto_alto_nel_contesto() -> None:
    cli = _ClienteFinto([VUOTA, VUOTA, VUOTA, BUONA], prompt_token=55000)
    x = ClienteDeepSeek(cli, 'm').chiama('d')
    assert [c['max_tokens'] for c in cli.chiamate] == [8000, 8000, 8000, 65536 - 55000 - 512]
    assert x['chiamata']['riuscita'] and x['tetto'] == 65536 - 55000 - 512


def test_osservatore() -> None:
    visti = []
    ClienteDeepSeek(_ClienteFinto([BUONA]), 'm', osservatore=visti.append).chiama('d')
    assert visti[0]['riuscita'] is True

    def rotto(_: Any) -> None:
        raise RuntimeError('il giornale non rompe la lettura')

    assert ClienteDeepSeek(_ClienteFinto([BUONA]), 'm', osservatore=rotto).chiama('d')['testo']


def test_limiti_diversi() -> None:
    cli = _ClienteFinto([VUOTA, BUONA])
    x = ClienteDeepSeek(cli, 'm', limiti=LimitiDeepSeek(tetto=100, tentativi=1)).chiama('d')
    assert [c['max_tokens'] for c in cli.chiamate] == [100, 16000]
    assert x['chiamata']['tentativi'] == 2 and x['chiamata']['riuscita']


def test_json_finale_solo_alla_fine() -> None:
    """The recovery takes the JSON the reasoning ends with, never a draft in the middle (02/10/2026)."""
    from tracepipe.deepseek import json_finale

    assert json_finale('penso {"a": 1} ancora\n{"principi": ["x"]}\n```') == '{"principi": ["x"]}'
    assert json_finale('bozza {"a": 1} e poi continuo') == ''
    assert json_finale('') == ''
    assert json_finale('lista [1, 2]') == ''
