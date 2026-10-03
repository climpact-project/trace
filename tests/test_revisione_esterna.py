"""The four defects found by the external review of 03/10/2026, each pinned by a case (package and live tools agree)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

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
    import importlib.util

    if not (ATTORNO / 'chiamata_deepseek.py').exists():
        pytest.skip('the live tools are not in this copy (showcase: they are in legacy/tools)')
    spec = importlib.util.spec_from_file_location('_chiamata_viva', ATTORNO / 'chiamata_deepseek.py')
    assert spec is not None and spec.loader is not None
    chiamata_viva = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(
        chiamata_viva
    )  # caricato a parte: non tocca sys.path (le altre prove usano le copie del banco)
    vivo = chiamata_viva.chiama(_cliente(COPIONE), 'm', 'domanda', {})
    assert vivo['testo'] == '{"principi": []}' and vivo['chiamata']['storia'][0]['troncata'] is True


def test_prova_in_thai_con_gli_spazi_dell_ocr() -> None:
    prova = 'ศาลตัดสินว่ารัฐต้องคุ้มครองสิทธิในชีวิตจากการเปลี่ยนแปลงสภาพภูมิอากาศ'
    pagina = 'ศาล ตัดสิน ว่า รัฐ ต้อง คุ้มครอง สิทธิ ใน ชีวิต จาก การ เปลี่ยนแปลง สภาพ ภูมิอากาศ อย่าง เคร่งครัด'
    assert FRENI.prova_trovata(prova, pagina)


# second round of the review (03/10/2026): strict yes/no, malformed row ids, the two sources of the principles


@pytest.fixture
def r11_vivi(vivi_oggi) -> tuple[Any, Any, Any]:
    return vivi_oggi('maggioranza'), vivi_oggi('carica_ripresa'), vivi_oggi('carica_lessicali')


SI = [True, 'true', ' TRUE ', 'True', 1]
NO = [False, 'false', 'False', ' false ', 0, None, '', 'yes', 'si', 2, 1.0, [], {}, 'true!']


def test_vero_stretto() -> None:
    from tracepipe.letture import vero

    assert all(vero(x) for x in SI)
    assert not any(vero(x) for x in NO)
    assert maggioranza.vero is vero


def test_vero_come_lo_strumento_vivo(r11_vivi) -> None:
    from tracepipe.letture import vero

    mv = r11_vivi[0]
    for x in SI + NO:
        assert mv.vero(x) is vero(x), x


def test_pagina_con_prosegue_stringa_false_non_si_spunta() -> None:
    """Five readings say ``"prosegue": "false"`` with a found evidence: a string "false" is a no (bool() said yes)."""
    letture = [_l05(['c.budget_residuo'], prosegue4='false')] * 5
    p4 = next(v for v in _proposta(letture)['proposto_estensione'] if v['pagina'] == 4)
    assert p4['voti'] == '0/5' and not p4['prosegue']
    letture = [_l05(['c.budget_residuo'], prosegue4='true')] * 3 + [_l05(['c.budget_residuo'])] * 2
    p4 = next(v for v in _proposta(letture)['proposto_estensione'] if v['pagina'] == 4)
    assert p4['voti'] == '3/5' and p4['prosegue']


def test_r05_pagina_con_prosegue_stringa_false() -> None:
    from tests.test_maggioranza import CAND, _comp

    lv = {'vicine': [{'pagina': 4, 'prosegue': 'false', 'principio': 'budget_residuo', 'prova': PROVA_4}]}
    assert _comp().estensione(CAND['r1'], lv)[0]['prosegue'] is False
    lv['vicine'][0]['prosegue'] = 'true'
    assert _comp().estensione(CAND['r1'], lv)[0]['prosegue'] is True


def test_prosegue_stringhe_come_gli_strumenti_vivi(r11_vivi, monkeypatch) -> None:
    import json
    import random

    from tests.test_maggioranza import CAND, IDS, TESTI, _comp

    _, cr, _ = r11_vivi
    monkeypatch.setattr(cr, 'PRINCIPI_TESTO', dict(TESTI))
    monkeypatch.setattr(cr, 'DOCUMENTI_OCR', set())
    monkeypatch.setitem(cr.CODICI_RUN, 'sonde', 'P05')
    monkeypatch.setitem(cr.CODICI_RUN, 'mappa', 'R07')
    rnd = random.Random(3)
    rid = 'neubauer__doc__1'
    for _ in range(100):
        letture = [_l05(['c.budget_residuo'], prosegue4=rnd.choice(SI + NO)) for _ in range(5)]
        ds = {rid: {'id': rid, 'data': '2026-10-03', 'letture': letture}}
        vivo = cr.proposta_r11('neubauer', rid, IDS, {}, {}, ds, {rid: CAND['r1']}, None, 'sostanziale')
        nuovo = _comp().proposta_r11(rid, {}, {}, ds, {rid: CAND['r1']}, None, 'sostanziale')
        assert json.dumps(vivo, ensure_ascii=False) == json.dumps(nuovo, ensure_ascii=False)


def test_id_malformato_saltato_e_contato(capsys) -> None:
    """A row id without '__' raised IndexError and stopped the whole case: now it is skipped, said and counted."""
    from tests.test_maggioranza import CAND, _comp
    from tracepipe.composizione import IngressiMaggioranza, documento_di

    assert documento_di('urgenda__doc_1__40') == 'doc_1' and documento_di('senza-trattini') == ''
    buona = 'neubauer__doc__1'
    letture = [_l05(['c.budget_residuo'])] * 5
    ing = IngressiMaggioranza(
        par={},
        brano={},
        ds={i: {'id': i, 'data': '2026-10-03', 'letture': letture} for i in ('rotta{x}', buona)},
        cand={i: CAND['r1'] for i in ('rotta{x}', buona)},
        tipi={},
    )
    righe = [('rotta{x}', {'proposto_rete': 'lessicale'}), (buona, {'proposto_rete': 'lessicale'})]
    scritture, conti = _comp().componi_r11(righe, ing)
    assert [i for i, _ in scritture] == [buona]
    assert conti['id malformato (saltata)'] == 1 and conti['da scrivere'] == 1
    err = capsys.readouterr().err
    assert 'rotta(x)' in err and '{' not in err  # the chain reads the counts from the first '{' of the output
    # the R11 proposal itself no longer raises on such an id
    ds = {'senza': {'letture': letture}}
    assert _comp().proposta_r11('senza', {}, {}, ds, {'senza': CAND['r1']}) is not None


def test_id_malformato_come_lo_strumento_vivo(r11_vivi, capsys) -> None:
    import collections

    from tracepipe.composizione import documento_di, id_malformato

    _, cr, _ = r11_vivi
    for rid in ('urgenda__d__1', 'a__b', 'senza', '', 'x{y}'):
        cv, cp = collections.Counter(), collections.Counter()
        assert cr.id_malformato(rid, cv) == id_malformato(rid, cp)
        assert cv == cp and cr.documento_di(rid) == documento_di(rid)
    err = capsys.readouterr().err
    assert '{' not in err


def test_due_fonti_dei_principi_separate() -> None:
    """R11 writes the paragraph map and the reading majority apart, before the chain-mention rule."""
    par = {'r1': {'principi': ['c.dovere_protezione'], 'paragrafi': ['unica:5']}}
    letture = [_l05(['c.budget_residuo'])] * 3 + [_l05(['nessuno'])] * 2
    out = _proposta(letture, par=par)
    assert out['proposto_principi_da_mappa'] == ['c.dovere_protezione']
    assert out['proposto_principi_da_lettura'] == ['c.budget_residuo']
    assert sorted(out['proposto_principi']) == sorted(['c.dovere_protezione', 'c.budget_residuo'])
    assert out['provenienza.letture'] == {'principi': 5, 'tipo': 0}
    catena = _proposta(letture, tipo='menzione_in_catena', par=par)
    assert catena['proposto_principi'] == ['nessuno']
    assert catena['proposto_principi_da_mappa'] == ['c.dovere_protezione']
    assert catena['proposto_principi_da_lettura'] == ['c.budget_residuo']
    nessuno = _proposta([_l05(['nessuno'])] * 5)
    assert nessuno['proposto_principi_da_mappa'] == [] and nessuno['proposto_principi_da_lettura'] == ['nessuno']


def test_letture_valide_su_ogni_riga_r11() -> None:
    from tests.test_maggioranza import CAND, _comp
    from tracepipe.composizione import IngressiMaggioranza

    ids = [f'neubauer__d{k}__1' for k in range(4)]
    letture = [
        [_l05(['c.budget_residuo'])] * 5,
        [_l05(['nessuno'])] * 3 + [{'esito': 'ILLEGGIBILE', 'grezzo': ''}] * 2,
        [_l05(['c.budget_residuo'])],
        [{'esito': 'ILLEGGIBILE', 'grezzo': ''}] * 5,
    ]
    ing = IngressiMaggioranza(
        par={},
        brano={},
        ds={i: {'id': i, 'letture': y} for i, y in zip(ids, letture, strict=True)},
        cand={i: CAND['r1'] for i in ids},
        tipi={},
    )
    scritture, conti = _comp().componi_r11([(i, {'proposto_rete': 'lessicale'}) for i in ids], ing)
    assert [c['provenienza.letture']['principi'] for _, c in scritture] == [5, 3, 1]
    assert conti['nessuna lettura valida (non toccata)'] == 1


def test_nessuna_coppia_di_sonde_entro_la_soglia_dei_refusi() -> None:
    """``canonico`` brings a typo back to the closest id at difflib 0.85: two real ids of one series that close would
    collapse into each other. Checked on every probe series of the six cases (03/10/2026: the closest pair is 0.59)."""
    import difflib
    import itertools

    import yaml

    cartella = ATTORNO.parent / 'cited-cases'
    serie = [
        f
        for f in sorted(cartella.glob('*.yaml'))
        if not any(x in f.name for x in ('mappa-paragrafi', '-S0', 'icj-clima', 'itlos'))
    ]
    if not serie:
        pytest.skip('cited-cases/ absent')
    for f in serie:
        ids = [
            s['id'].split('.')[-1] for s in yaml.safe_load(f.read_text(encoding='utf-8')).get('semantic_queries') or []
        ]
        assert len(set(ids)) == len(ids), f.name
        for a, b in itertools.combinations(ids, 2):
            assert difflib.SequenceMatcher(None, a, b).ratio() < 0.85, (f.name, a, b)
