"""The four defects found by the external review of 03/10/2026, each pinned by a case (package and live tools agree)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from tests.test_maggioranza import PROVA_4, _l05, _proposta
from tracepipe import maggioranza
from tracepipe.deepseek import ClienteDeepSeek
from tracepipe.freni import FRENI

ATTORNO = Path(__file__).resolve().parent.parent / 'tools'


def test_principio_unanime_con_uno_quasi_preso_non_e_incerto() -> None:
    """A at 5/5 and B at 2/5: the row is not uncertain (B stays listed as uncertain), and the type is not touched."""
    letture = [_l05(['c.budget_residuo', 'c.dovere_protezione'])] * 2 + [_l05(['c.budget_residuo'])] * 3
    out = _proposta(letture, vt=maggioranza.voto_tipo([{'tipo_citazione': 'sostanziale'}] * 5))
    assert out['proposto_principi_voti']['c.budget_residuo'] == '5/5'
    assert 'c.dovere_protezione' in out['proposto_principi_incerti']
    assert out['proposto_incerta'] is False
    assert 'proposto_confidenza' not in out


def test_nessun_principio_preso_ma_uno_vicino_e_incerto() -> None:
    letture = [_l05(['c.budget_residuo'])] * 2 + [_l05(['nessuno'])] * 3
    assert _proposta(letture)['proposto_incerta'] is True


def test_pagina_non_spuntata_con_la_prova_di_un_altro_principio() -> None:
    """Three readings say page 4 continues on A without a found evidence, one on B with it: not ticked."""

    def con(principio: str, prova: str) -> dict[str, Any]:
        y = _l05(['c.budget_residuo', 'c.dovere_protezione'], prosegue4=True, prova4=prova)
        y['vicine'][0]['principio'] = principio
        return y

    letture = (
        [con('dovere_protezione', 'una frase che non sta nella pagina vicina')] * 3
        + [con('budget_residuo', PROVA_4)]
        + [_l05(['c.budget_residuo', 'c.dovere_protezione'])]
    )
    p4 = next(v for v in _proposta(letture)['proposto_estensione'] if v['pagina'] == 4)
    assert p4['principio'] == 'c.dovere_protezione'
    assert not p4['prosegue']


def _cliente(copione: list[tuple[str, str, int]]) -> Any:
    passi = list(copione)

    def create(**kw: Any) -> Any:
        contenuto, fine, token = passi.pop(0)
        msg = SimpleNamespace(content=contenuto, reasoning_content='ragiono', model_extra={})
        return SimpleNamespace(
            choices=[SimpleNamespace(message=msg, finish_reason=fine)],
            usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=token),
        )

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


COPIONE = [('{"principi": ["c.budget', 'length', 8000), ('{"principi": []}', 'stop', 300)]


def test_risposta_troncata_non_vuota_si_ritenta() -> None:
    esito = ClienteDeepSeek(_cliente(COPIONE), 'm', {}, dormi=lambda s: None).chiama('domanda')
    assert esito['testo'] == '{"principi": []}'
    assert esito['chiamata']['tentativi'] == 2
    assert esito['chiamata']['storia'][0]['troncata'] is True


def test_risposta_troncata_come_lo_strumento_vivo() -> None:
    sys.path.insert(0, str(ATTORNO))
    import chiamata_deepseek

    vivo = chiamata_deepseek.chiama(_cliente(COPIONE), 'm', 'domanda', {})
    assert vivo['testo'] == '{"principi": []}' and vivo['chiamata']['storia'][0]['troncata'] is True


def test_prova_in_thai_con_gli_spazi_dell_ocr() -> None:
    prova = 'ศาลตัดสินว่ารัฐต้องคุ้มครองสิทธิในชีวิตจากการเปลี่ยนแปลงสภาพภูมิอากาศ'
    pagina = 'ศาล ตัดสิน ว่า รัฐ ต้อง คุ้มครอง สิทธิ ใน ชีวิต จาก การ เปลี่ยนแปลง สภาพ ภูมิอากาศ อย่าง เคร่งครัด'
    assert FRENI.prova_trovata(prova, pagina)
