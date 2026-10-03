"""Composizione (R05): every branch of the live ``carica_ripresa.proposta`` on synthetic rows, output identical."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from tracepipe.composizione import Composizione, IngressiComposizione

IDS = ['c.dovere_protezione', 'c.budget_residuo', 'c.liberta_intertemporale']
TESTI = {
    'c.dovere_protezione': ('Dovere di protezione', 'Lo Stato ha un dovere di protezione della vita e della salute'),
    'c.budget_residuo': ('Budget residuo', 'Il budget residuo di emissioni va distribuito fra le generazioni'),
    'c.liberta_intertemporale': ('Liberta intertemporale', 'Le liberta future vanno protette oggi dal legislatore'),
}
PAGINA_4 = 'the reduction burden cannot be shifted to the future generations without a plan for the time after 2030'
PAGINA_5 = 'another reasoning on the paris agreement and its temperature goal applied to the national budget'
CONTESTO = (
    '===== PAGINA DELLA CITAZIONE =====\nThe court held, citing Neubauer, that the state must protect '
    'freedom over time and distribute the remaining budget fairly.'
)
CAND = {
    'pagina': 3,
    'contesto': CONTESTO,
    'vicine': [
        {'pagina': 4, 'punteggi': {'c.budget_residuo': 0.91, 'c.dovere_protezione': 0.3}, 'testo': PAGINA_4},
        {'pagina': 5, 'punteggi': {'c.liberta_intertemporale': 0.6}, 'testo': PAGINA_5},
        {'pagina': 13, 'punteggi': {}, 'testo': 'x'},
    ],
}
FRASE = 'the state must protect freedom over time and distribute the remaining budget fairly'


def _l05(**kw: Any) -> dict[str, Any]:
    base = {
        'frase_sostenuta': FRASE,
        'principi': ['c.budget_residuo'],
        'altro': '',
        'motivo': ' una  frase\n',
        'vicine': [
            {
                'pagina': 4,
                'prosegue': True,
                'principio': 'budget_residuo',
                'prova': 'the reduction burden cannot be shifted to the future generations',
            },
            {
                'pagina': 5,
                'prosegue': True,
                'principio': 'c.liberta_intertemporale',
                'prova': 'Le liberta future vanno protette oggi dal legislatore',
            },
            {'pagina': 'x', 'prosegue': True},
            {'pagina': 99, 'prosegue': True},
        ],
    }
    base.update(kw)
    return base


RIGHE: dict[str, dict[str, Any]] = {
    # rid: {ds, ds_principi, ds_seguito, par, brano, cand, tipo}
    'c__doc-a__1': {'ds': {'letture': [_l05()]}},
    'c__doc-a__2': {
        'ds': {'letture': [_l05()], 'seconda': True},
        'l04': {'letture': [{'principi': ['dovere_protezione', 'c.liberta_intertemporal'], 'motivo': 'L04'}]},
    },
    'c__doc-a__3': {
        'ds': {'letture': [_l05(principi=['c.liberta_intertemporale'])]},
        'l04': {'letture': [{'principi': []}, {'principi': ['', 'c.budget_residuo']}]},
    },
    'c__doc-a__4': {
        'ds': {'letture': [_l05(principi=[]), _l05(principi=['c.dovere_protezione'])]},
        'l04': {'letture': [{'principi': []}]},
    },
    'c__doc-a__5': {'ds': {'letture': [_l05()]}, 'l04': {'letture': [{'principi': 'nessuno'}]}},
    'c__doc-a__6': {'ds': {'letture': [_l05(principi=['altro'], altro=' una cosa   nuova ')]}},
    'c__doc-a__7': {'ds': {'letture': [_l05(principi=['altro'], altro='')]}},
    'c__doc-a__8': {'ds': {'letture': [_l05()]}, 'tipo': 'menzione_in_catena'},
    'c__doc-a__9': {'ds': {'letture': [_l05(principi=['nessuno'])]}, 'par': ['c.dovere_protezione']},
    'c__doc-ocr__10': {'ds': {'letture': [_l05(frase_sostenuta='')]}, 'brano': {'c.budget_residuo': 0.55, 'c.x': 0.2}},
    'c__doc-a__11': {'ds': {'letture': ['non un dict', _l05()]}},
    'c__doc-a__12': {
        'ds': {'letture': [_l05()]},
        'l07': {
            'letture': [
                _l05(
                    vicine=[
                        {
                            'pagina': 4,
                            'prosegue': True,
                            'principio': 'c.budget_residuo',
                            'prova': 'the reduction burden cannot be shifted to the future generations',
                        }
                    ]
                )
            ]
        },
    },
    'c__doc-a__13': {
        'ds': {'letture': [_l05(frase_sostenuta=TESTI['c.budget_residuo'][1])]},
        'cand': dict(CAND, pagina='abc'),
    },
    'c__doc-a__14': {'ds': {'letture': [_l05(principi=['cooperazione_obbligo'])]}},
    'c__doc-a__15': {
        'ds': {'letture': [_l05()]},
        'cand': dict(CAND, vicine_testo={4: 'testo diverso, la prova non c e piu in questa pagina'}),
    },
    'c__doc-a__16': {
        'ds': {'letture': [_l05(principi=['c.budget_residuo', 'budget_residuo'])]},
        'par': ['c.budget_residuo'],
        'brano': {'c.budget_residuo': 0.5},
    },
    'c__doc-a__17': {},
    'c__doc-a__18': {'ds': {'letture': []}, 'l04': {'letture': ['rotta']}},
    'c__doc-a__19': {
        'ds': {'letture': [_l05(principi=['c.dovere_protezione'])], 'seconda': True},
        'l04': {'letture': [{'principi': []}]},
    },
    'c__doc-a__20': {
        'ds': {'letture': [_l05()]},
        'l04': {'letture': [{'principi': 'c.budget_residuo; dovere_protezione'}]},
    },
}


def _ingressi() -> dict[str, Any]:
    ds = {r: x['ds'] for r, x in RIGHE.items() if 'ds' in x}
    l04 = {r: x['l04'] for r, x in RIGHE.items() if 'l04' in x}
    l07 = {r: x['l07'] for r, x in RIGHE.items() if 'l07' in x}
    par = {
        r: {'principi': x.get('par', []), 'paragrafi': ['unica:1'] if x.get('par') else []} for r, x in RIGHE.items()
    }
    brano = {r: x['brano'] for r, x in RIGHE.items() if 'brano' in x}
    cand = {r: x.get('cand', CAND) for r, x in RIGHE.items()}
    return {'ds': ds, 'l04': l04, 'l07': l07, 'par': par, 'brano': brano, 'cand': cand}


@pytest.fixture
def vivo(vivi, monkeypatch: pytest.MonkeyPatch):
    cr = vivi('carica_ripresa')
    monkeypatch.setattr(cr, 'PRINCIPI_TESTO', dict(TESTI))
    monkeypatch.setattr(cr, 'CODICI_RUN', {'sonde': 'P05', 'mappa': 'R07'})
    monkeypatch.setattr(cr, 'DOCUMENTI_OCR', {'doc-ocr'})
    return cr


def _comp(compat: bool) -> Composizione:
    return Composizione(
        ids=list(IDS),
        principi_testo=TESTI,
        codice_sonde='P05',
        codice_mappa='R07',
        documenti_ocr=frozenset({'doc-ocr'}),
        compat=compat,
    )


@pytest.fixture
def comp() -> Composizione:
    """The composition with the live defects (compat=True): the one that must equal ``carica_ripresa.proposta``."""
    return _comp(True)


@pytest.mark.parametrize('rid', sorted(RIGHE))
@pytest.mark.parametrize('modo', ['solo_l05', 'l04', 'l04_l07'])
def test_proposta_come_carica_ripresa(vivo, comp: Composizione, rid: str, modo: str) -> None:
    g = _ingressi()
    ds_p = g['l04'] if modo != 'solo_l05' else None
    ds_s = g['l07'] if modo == 'l04_l07' else None
    tipo = RIGHE[rid].get('tipo', '')
    args = (rid, IDS, g['par'], g['brano'], g['ds'], g['cand'], tipo, ds_p, ds_s)
    atteso = vivo.proposta('c', *copy.deepcopy(args))
    nuovo = comp.proposta(rid, g['par'], g['brano'], g['ds'], g['cand'], tipo, ds_p, ds_s)
    assert nuovo == atteso
    assert list(nuovo) == list(atteso)


@pytest.mark.parametrize('compat', [True, False])
def test_rami_coperti(compat: bool) -> None:
    """The synthetic rows reach the branches they were written for, with and without the live defects."""
    comp = _comp(compat)
    g = _ingressi()

    def p(rid: str, l04: bool = True, l07: bool = False) -> dict[str, Any]:
        return comp.proposta(
            rid,
            g['par'],
            g['brano'],
            g['ds'],
            g['cand'],
            RIGHE[rid].get('tipo', ''),
            g['l04'] if l04 else None,
            g['l07'] if l07 else None,
        )

    a = p('c__doc-a__1')
    assert a['proposto_principi'] == ['c.budget_residuo']
    assert [v['prosegue'] for v in a['proposto_estensione']] == [True, False]
    assert a['proposto_estensione'][1]['prova_esito'] == 'inventata'
    assert a['proposto_estensione'][0]['scelta']['punteggio'] == 0.91
    assert a['proposto_frase_esito'] == 'trovata' and a['proposto_frase_testuale'] is True
    assert p('c__doc-a__2')['proposto_principi'] == ['c.dovere_protezione', 'c.liberta_intertemporale']
    assert p('c__doc-a__3')['proposto_principi'] == ['c.budget_residuo']
    # provenance after a fallback from L04 to the L05 reading: L04 with the live defect, L05 fixed (the first L05
    # file without ``seconda`` is coded L04 in both: that is the register, not the defect)
    assert p('c__doc-a__4')['provenienza.principi'] == {'c.dovere_protezione': ['L04']}
    assert p('c__doc-a__19')['provenienza.principi'] == {'c.dovere_protezione': ['L04' if compat else 'L05']}
    # principi as a string: read char by char (no principle survives, so "nessuno") with the defect; split when fixed
    assert p('c__doc-a__5')['proposto_principi'] == ['nessuno']
    assert p('c__doc-a__20')['proposto_principi'] == (
        ['nessuno'] if compat else ['c.dovere_protezione', 'c.budget_residuo']
    )
    # the rule of each surrounding page
    assert {v['scelta']['regola'] for v in a['proposto_estensione']} == {'R03' if compat else 'R08'}
    assert p('c__doc-a__6')['proposto_principio_altro'] == 'una cosa nuova'
    assert p('c__doc-a__7')['proposto_principi'] == ['nessuno']
    catena = p('c__doc-a__8')
    assert catena['proposto_principi'] == ['nessuno'] and catena['proposto_principi_motivo'].startswith('Menzione')
    assert not any(v['prosegue'] for v in catena['proposto_estensione'])
    assert p('c__doc-a__9')['proposto_principi'] == ['c.dovere_protezione']
    ocr = p('c__doc-ocr__10')
    assert ocr['provenienza.corpus'] == 'D02'
    assert ocr['proposto_frase_sostenuta'] == '' and ocr['proposto_frase_esito'] == ''
    assert ocr['proposto_principi_fonti']['c.budget_residuo'] == ['lettura', 'reranker']
    assert p('c__doc-a__12', l07=True)['provenienza.seguito'] == 'L07'
    t13 = p('c__doc-a__13')
    assert t13['proposto_frase_esito'] == 'inventata'
    assert t13['proposto_estensione'][0]['scelta']['distanza'] is None
    assert p('c__doc-a__14')['proposto_principi'] == ['nessuno']
    assert p('c__doc-a__15')['proposto_estensione'][0]['prova_esito'] == 'non trovata'
    assert p('c__doc-a__16')['proposto_principi_fonti']['c.budget_residuo'] == [
        'paragrafo',
        'lettura',
        'lettura',
        'reranker',
    ]


def test_componi_come_main(comp: Composizione) -> None:
    """Selection of the rows to write and the counts, as the loop of ``main``."""
    g = _ingressi()
    ing = IngressiComposizione(
        par=g['par'], brano=g['brano'], ds=g['ds'], cand=g['cand'], ds_principi=g['l04'], ds_seguito=g['l07']
    )
    righe = [
        ('c__doc-a__1', {'proposto_rete': 'lessicale'}),
        ('c__doc-a__2', {'proposto_rete': 'semantica'}),
        ('c__doc-a__3', {'proposto_rete': 'entrambe', 'esito': 'confermata'}),
        ('c__doc-a__17', {'proposto_rete': 'lessicale'}),
        ('c__doc-a__8', {'proposto_rete': 'lessicale', 'proposto_tipo_citazione': 'menzione_in_catena'}),
        ('c__doc-a__12', {'proposto_rete': 'lessicale'}),
    ]
    scritture, conti = comp.componi(righe, ing)
    assert [r for r, _ in scritture] == ['c__doc-a__1', 'c__doc-a__8', 'c__doc-a__12']
    assert conti == {
        'gia giudicata (non toccata)': 1,
        'senza lettura': 1,
        'principi da L05 (manca L04)': 3,
        'da scrivere': 3,
        'con principio spuntato': 2,
        'nessuno': 1,
        'con seguito proposto': 2,
        'senza seguito': 1,
        'seguito riletto (L07)': 1,
    }
    scritture, conti = comp.componi(righe, ing, anche_senza_lettura=True)
    provvisoria = dict(scritture)['c__doc-a__17']
    assert provvisoria['proposta_provvisoria'] is True and provvisoria['proposto_principi'] == []
    assert conti['provvisoria: paragrafi e reranker, lettura in arrivo'] == 1
