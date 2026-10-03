"""R11 (02/10/2026): the majority of the five readings, rule by rule, identical to the live tools on the same rows."""

from __future__ import annotations

import copy
import json
import random
from typing import Any

import pytest

from tracepipe import maggioranza
from tracepipe.caricatori import CaricatoreTipo
from tracepipe.composizione import ComposizioneMaggioranza
from tracepipe.config import Config

IDS = ['c.dovere_protezione', 'c.budget_residuo', 'c.liberta_intertemporale']
TESTI = {
    'c.dovere_protezione': ('Dovere di protezione', 'Lo Stato ha un dovere di protezione della vita e della salute'),
    'c.budget_residuo': ('Budget residuo', 'Il budget residuo di emissioni va distribuito fra le generazioni'),
    'c.liberta_intertemporale': ('Liberta intertemporale', 'Le liberta future vanno protette oggi dal legislatore'),
}
PAGINA_4 = 'the reduction burden cannot be shifted to the future generations without a plan for the time after 2030'
PAGINA_9 = 'another reasoning on the paris agreement and its temperature goal applied to the national budget'
CONTESTO = (
    '===== PAGINA DELLA CITAZIONE =====\nThe court held, citing Neubauer, that the state must protect '
    'freedom over time and distribute the remaining budget fairly.'
)
FRASE = 'the state must protect freedom over time and distribute the remaining budget fairly'
CAND = {
    'r1': {
        'pagina': 3,
        'contesto': CONTESTO,
        'vicine': [
            {'pagina': 4, 'punteggi': {'c.budget_residuo': 0.91, 'c.dovere_protezione': 0.3}, 'testo': PAGINA_4},
            {'pagina': 9, 'punteggi': {'c.liberta_intertemporale': 0.6}, 'testo': PAGINA_9},
        ],
    }
}
PROVA_4 = 'the reduction burden cannot be shifted to the future generations'


def _comp() -> ComposizioneMaggioranza:
    return ComposizioneMaggioranza(ids=list(IDS), principi_testo=TESTI, codice_sonde='P05', codice_mappa='R07')


def _l05(
    principi: Any, prosegue4: bool = False, prova4: str = PROVA_4, frase: str = FRASE, **kw: Any
) -> dict[str, Any]:
    y = {
        'frase_sostenuta': frase,
        'principi': principi,
        'altro': '',
        'motivo': f'motivo {principi}',
        'vicine': [
            {'pagina': 4, 'prosegue': prosegue4, 'principio': 'budget_residuo', 'prova': prova4},
            {'pagina': 9, 'prosegue': False, 'principio': '', 'prova': 'another reasoning on the paris agreement'},
        ],
    }
    y.update(kw)
    return y


VUOTA = {'esito': 'ILLEGGIBILE', 'grezzo': ''}


# the type


def test_tipo_maggioranza_e_margine() -> None:
    t = maggioranza.voto_tipo(
        [{'tipo_citazione': x} for x in ('descrittiva', 'sostanziale', 'sostanziale', 'sostanziale', 'critica')]
    )
    assert t is not None
    assert (t['tipo'], t['n'], t['margine'], t['incerto'], t['parita']) == ('sostanziale', 5, 2, False, False)
    assert t['voti'] == {'sostanziale': 3, 'descrittiva': 1, 'critica': 1}
    assert t['indice'] == 1
    t = maggioranza.voto_tipo(
        [{'tipo_citazione': x} for x in ('descrittiva', 'sostanziale', 'sostanziale', 'descrittiva', 'sostanziale')]
    )
    assert t is not None and t['margine'] == 1 and t['incerto']


def test_tipo_parita_vince_il_primo_nell_ordine_delle_letture() -> None:
    letture = [{'tipo_citazione': x} for x in ('critica', 'sostanziale', 'descrittiva', 'sostanziale', 'descrittiva')]
    t = maggioranza.voto_tipo(letture)
    assert t is not None and t['tipo'] == 'sostanziale' and t['parita'] and t['incerto'] and t['margine'] == 0
    # the order of the readings decides, not the order of the codebook
    t = maggioranza.voto_tipo(list(reversed(letture)))
    assert t is not None and t['tipo'] == 'descrittiva'


def test_tipo_solo_letture_valide() -> None:
    t = maggioranza.voto_tipo([VUOTA, {'tipo_citazione': 'non_un_tipo'}, {'tipo_citazione': 'implicita'}, None])
    assert t is not None and (t['tipo'], t['n'], t['margine']) == ('implicita', 1, 1)
    assert maggioranza.voto_tipo([VUOTA, {'esito': 'ILLEGGIBILE', 'grezzo': 'x'}]) is None


# the principles


def test_principi_tre_su_cinque_e_voti() -> None:
    letture = [
        _l05(['c.budget_residuo']),
        _l05(['budget_residuo', 'c.dovere_protezione']),
        _l05(['c.budget_residuo']),
        _l05(['nessuno']),
        _l05([]),  # an empty list is not an answer
    ]
    vp = maggioranza.voto_principi(letture, IDS, _comp().canonico)
    assert vp is not None
    assert vp['n'] == 4 and vp['soglia'] == 3
    assert vp['maggioranza'] == ['c.budget_residuo']
    assert vp['voti'] == {'c.dovere_protezione': 1, 'c.budget_residuo': 3, 'nessuno': 1}
    # |2v - n| <= 1 with n = 4: only v = 2 (none here)
    assert vp['incerti'] == []


def test_principi_nessuno_se_nessuno_arriva_alla_maggioranza() -> None:
    letture = [_l05(['c.budget_residuo']), _l05(['c.budget_residuo']), _l05(['c.dovere_protezione'])]
    letture += [_l05(['c.dovere_protezione']), _l05(['c.liberta_intertemporale'])]
    vp = maggioranza.voto_principi(letture, IDS, _comp().canonico)
    assert vp is not None and vp['maggioranza'] == ['nessuno']
    assert vp['incerti'] == ['c.dovere_protezione', 'c.budget_residuo']


def test_principi_altro_con_frase_e_stringa() -> None:
    letture = [_l05('c.budget_residuo, altro', altro='una cosa fuori elenco')] * 3 + [_l05(['altro'])] * 2
    vp = maggioranza.voto_principi(letture, IDS, _comp().canonico)
    assert vp is not None and vp['maggioranza'] == ['c.budget_residuo', 'altro']
    assert vp['voti']['nessuno'] == 2  # "altro" without its sentence is not "altro"


# the composition


RID = 'neubauer__doc__1'


def _proposta(letture: list[Any], tipo: str = 'sostanziale', par: dict | None = None, vt: Any = None) -> dict[str, Any]:
    ds = {RID: {'id': RID, 'data': '2026-10-03', 'letture': letture}}
    par = {RID: par['r1']} if par else {}
    out = _comp().proposta_r11(RID, par, {RID: {'c.dovere_protezione': 0.7}}, ds, {RID: CAND['r1']}, vt, tipo)
    assert out is not None
    return out


def test_pagina_prosegue_a_maggioranza_con_la_prova() -> None:
    letture = [_l05(['c.budget_residuo'], prosegue4=True)] * 3 + [_l05(['c.budget_residuo'])] * 2
    out = _proposta(letture)
    p4 = next(v for v in out['proposto_estensione'] if v['pagina'] == 4)
    assert p4['prosegue'] and p4['voti'] == '3/5' and p4['principio'] == 'c.budget_residuo'
    assert p4['scelta']['regola'] == 'R10' and p4['scelta']['soglia'] == 0.5
    assert out['provenienza.scelta_vicine'] == 'R10' and out['provenienza.composizione'] == 'R11'
    # two of five: listed, not ticked
    out = _proposta([_l05(['c.budget_residuo'], prosegue4=True)] * 2 + [_l05(['c.budget_residuo'])] * 3)
    assert not next(v for v in out['proposto_estensione'] if v['pagina'] == 4)['prosegue']
    # majority but no evidence found in the page: the brake keeps the page unticked
    out = _proposta(
        [_l05(['c.budget_residuo'], prosegue4=True, prova4='una frase che non sta nella pagina vicina')] * 5
    )
    p4 = next(v for v in out['proposto_estensione'] if v['pagina'] == 4)
    assert not p4['prosegue'] and p4['prova_esito'] == 'non trovata'


def test_prova_mancante_segnalata_non_tolta() -> None:
    letture = [_l05(['c.liberta_intertemporale'], frase='una frase che non sta nella pagina della citazione')] * 5
    out = _proposta(letture)
    assert out['proposto_principi'] == ['c.liberta_intertemporale']
    assert out['proposto_prova_mancante'] and out['proposto_principi_senza_prova'] == ['c.liberta_intertemporale']
    # with the sentence found in the page the evidence is there
    out = _proposta([_l05(['c.liberta_intertemporale'])] * 5)
    assert not out['proposto_prova_mancante'] and out['proposto_frase_esito'] == 'trovata'
    # a principle from the paragraph map needs no evidence from the reading
    par = {'r1': {'principi': ['c.liberta_intertemporale'], 'paragrafi': ['unica:5']}}
    out = _proposta(letture, par=par)
    assert not out['proposto_prova_mancante']


def test_paragrafi_restano_e_catena_nessuno() -> None:
    par = {'r1': {'principi': ['c.dovere_protezione'], 'paragrafi': ['unica:5']}}
    out = _proposta([_l05(['c.budget_residuo'])] * 5, par=par)
    assert out['proposto_principi'] == ['c.dovere_protezione', 'c.budget_residuo']
    assert out['provenienza.principi'] == {
        'c.dovere_protezione': ['R07', 'T01'],
        'c.budget_residuo': ['L05'],
    }
    vt = maggioranza.voto_tipo([{'tipo_citazione': 'menzione_in_catena'}] * 5)
    out = _proposta([_l05(['c.budget_residuo'], prosegue4=True)] * 5, par=par, vt=vt)
    assert out['proposto_principi'] == ['nessuno']
    assert out['proposto_principi_motivo'].startswith('Menzione in catena')
    assert not any(v['prosegue'] for v in out['proposto_estensione'])
    assert out['proposto_confidenza'] == 'alta' and not out['proposto_incerta']


def test_frase_dalla_lettura_della_maggioranza_e_incerta() -> None:
    letture = [
        _l05(['c.dovere_protezione'], frase='prima frase che non coincide con la maggioranza dei principi'),
        _l05(['c.budget_residuo']),
        _l05(['c.budget_residuo']),
        _l05(['c.budget_residuo']),
        _l05(['c.dovere_protezione']),
    ]
    vt = maggioranza.voto_tipo([{'tipo_citazione': 'sostanziale'}] * 5)
    out = _proposta(letture, vt=vt)
    assert out['proposto_frase_sostenuta'] == FRASE
    assert out['proposto_principi_voti'] == {'c.dovere_protezione': '2/5', 'c.budget_residuo': '3/5'}
    assert out['proposto_principi_incerti'] == ['c.dovere_protezione', 'c.budget_residuo']
    assert out['proposto_incerta'] and out['proposto_confidenza'] == 'bassa'
    assert out['provenienza.letture'] == {'principi': 5, 'tipo': 5}


def test_senza_letture_valide_nessuna_proposta() -> None:
    ds = {'r1': {'letture': [VUOTA, _l05([])]}}
    assert _comp().proposta_r11('r1', {}, {}, ds, CAND) is None


# identical to the live tools


@pytest.fixture
def r11_vivi(vivi_oggi) -> tuple[Any, Any, Any]:
    return vivi_oggi('maggioranza'), vivi_oggi('carica_ripresa'), vivi_oggi('carica_lessicali')


def _letture_a_caso(rnd: random.Random) -> list[Any]:
    scelte = [
        ['c.budget_residuo'],
        ['budget_residuo', 'c.dovere_protezione'],
        ['nessuno'],
        [],
        'c.liberta_intertemporale; altro',
        ['cooperazione_obbligo'],
        ['c.dovere_protezion'],
    ]
    out: list[Any] = []
    for _ in range(5):
        if rnd.random() < 0.1:
            out.append(copy.deepcopy(VUOTA))
            continue
        y = _l05(
            rnd.choice(scelte),
            prosegue4=rnd.random() < 0.6,
            prova4=rnd.choice([PROVA_4, 'Il budget residuo di emissioni va distribuito fra le generazioni', 'x']),
            frase=rnd.choice([FRASE, '', 'altra frase che non sta nella pagina della citazione per niente']),
            altro=rnd.choice(['', 'fuori elenco']),
        )
        if rnd.random() < 0.3:
            y['vicine'][1] = {
                'pagina': 9,
                'prosegue': True,
                'principio': 'c.liberta_intertemporale',
                'prova': PAGINA_9[:70],
            }
        out.append(y)
    return out


def test_come_gli_strumenti_vivi(r11_vivi, monkeypatch) -> None:
    mv, cr, cl = r11_vivi
    monkeypatch.setattr(cr, 'PRINCIPI_TESTO', dict(TESTI))
    monkeypatch.setattr(cr, 'DOCUMENTI_OCR', set())
    monkeypatch.setitem(cr.CODICI_RUN, 'sonde', 'P05')
    monkeypatch.setitem(cr.CODICI_RUN, 'mappa', 'R07')
    rnd = random.Random(20261003)
    tipi = ['menzione_in_catena', 'descrittiva', 'sostanziale', 'critica']
    car = CaricatoreTipo(Config(radice=__import__('pathlib').Path('/x')), 'neubauer', None, composizione='R11')
    for i in range(300):
        letture = _letture_a_caso(rnd)
        lt = [
            {'tipo_citazione': rnd.choice(tipi), 'chi_parla': 'corte', 'motivo': f'm{i}', 'riferimento': 'caso'}
            for _ in range(5)
        ]
        if rnd.random() < 0.2:
            lt[0] = copy.deepcopy(VUOTA)
        vt_v, vt_p = mv.voto_tipo(lt), maggioranza.voto_tipo(lt)
        assert vt_v == vt_p
        par = {'r1': {'principi': ['c.dovere_protezione'], 'paragrafi': ['unica:5']}} if i % 3 == 0 else {}
        ds = {'r1': {'id': 'r1', 'data': '2026-10-03', 'letture': letture}}
        brano = {'r1': {'c.dovere_protezione': rnd.random()}}
        rid = 'neubauer__doc__1'
        ds = {rid: ds['r1']}
        cand = {rid: CAND['r1']}
        par = {rid: par['r1']} if par else {}
        brano = {rid: brano['r1']}
        vivo = cr.proposta_r11('neubauer', rid, IDS, par, brano, ds, cand, vt_v, 'descrittiva')
        nuovo = _comp().proposta_r11(rid, par, brano, ds, cand, vt_p, 'descrittiva')
        assert json.dumps(vivo, ensure_ascii=False) == json.dumps(nuovo, ensure_ascii=False)
        if vt_v:
            r = {'proposto_note': 'nota\nDeepSeek, due letture: a / b.\nDeepSeek, letture a maggioranza (5): x.'}
            x = {'id': rid, 'data': '2026-10-03', 'codebook': '0.4-pilot', 'letture': lt}
            assert cl.campi_r11('neubauer', r, x, vt_v) == car.campi_r11(r, x, vt_p)
            assert car.campi_r11(r, x, vt_p)['proposto_note'].split('\n')[0] == 'nota'
