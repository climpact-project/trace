"""R13 (04/10/2026): an L05 reading that answers with an EMPTY principle list votes «nessuno».

Up to R12 such a reading did not vote, against the measurement of the five readings (stabilita_deepseek.principi:
[] is the empty set, not a failed reading). On the stored readings of 04/10/2026, 8,894 of 32,474 valid readings had
`principi: []`, almost all with a reason saying «no principle of the case», and 718 unjudged rows had no valid
reading at all. The brakes (tools/freni.py) were not involved: these tests also check that R13 does not get around them.
The package (tracepipe.maggioranza, tracepipe.composizione): the same cases as the tests of the live tools.
"""

from __future__ import annotations

from typing import Any

import pytest

IDS = ['c.dovere_protezione', 'c.budget_residuo', 'c.liberta_intertemporale']
TESTI = {
    'c.dovere_protezione': ('Dovere di protezione', 'Lo Stato ha un dovere di protezione della vita e della salute'),
    'c.budget_residuo': ('Budget residuo', 'Il budget residuo di emissioni va distribuito fra le generazioni'),
    'c.liberta_intertemporale': ('Liberta intertemporale', 'Le liberta future vanno protette oggi dal legislatore'),
}
PAGINA_4 = 'the reduction burden cannot be shifted to the future generations without a plan for the time after 2030'
CONTESTO = (
    '===== PAGINA DELLA CITAZIONE =====\nThe court held, citing Neubauer, that the state must protect '
    'freedom over time and distribute the remaining budget fairly.'
)
FRASE = 'the state must protect freedom over time and distribute the remaining budget fairly'
RID = 'neubauer__doc__1'
CAND = {
    RID: {
        'pagina': 3,
        'contesto': CONTESTO,
        'vicine': [{'pagina': 4, 'punteggi': {'c.budget_residuo': 0.91}, 'testo': PAGINA_4}],
    }
}
VUOTA = {'grezzo': '', 'esito': 'ILLEGGIBILE'}


def _l05(
    principi: Any,
    frase: str = FRASE,
    prova4: str = 'the reduction burden cannot be shifted to the future generations',
    prosegue4: bool = False,
    **kw: Any,
) -> dict[str, Any]:
    y = {
        'frase_sostenuta': frase,
        'principi': principi,
        'altro': '',
        'motivo': f'motivo {principi}',
        'vicine': [{'pagina': 4, 'prosegue': prosegue4, 'principio': 'budget_residuo', 'prova': prova4}],
    }
    y.update(kw)
    return y


class _ComeStrumento:
    """The package composition called with the argument order of ``tools/carica_ripresa.proposta_r11``."""

    def __init__(self, testi: dict[str, tuple[str, str]], sonde: str, mappa: str) -> None:
        self.testi, self.sonde, self.mappa = testi, sonde, mappa

    def proposta_r11(
        self,
        caso: str,
        rid: str,
        ids: list[str],
        par: Any,
        brano: Any,
        ds: Any,
        cand: Any,
        vt: Any = None,
        tipo_fs: str = '',
        composizione: str = 'R11',
        lettura: str = 'L05',
    ) -> Any:
        from tracepipe.composizione import ComposizioneMaggioranza

        c = ComposizioneMaggioranza(
            ids=ids, principi_testo=self.testi, codice_sonde=self.sonde, codice_mappa=self.mappa
        )
        return c.proposta_r11(rid, par, brano, ds, cand, vt, tipo_fs, composizione, lettura)

    @staticmethod
    def uguale_a_oggi(r: Any, campi: Any) -> bool:
        from tracepipe.composizione import uguale_a_oggi

        return uguale_a_oggi(r, campi)


@pytest.fixture
def vivi() -> tuple[Any, Any]:
    from tracepipe import maggioranza

    return maggioranza, _ComeStrumento(dict(TESTI), 'P05', 'R07')


def _can(q: str) -> str:
    return q


def _proposta(cr: Any, letture: list[Any], composizione: str) -> dict[str, Any] | None:
    ds = {RID: {'id': RID, 'data': '2026-10-03', 'letture': letture}}
    return cr.proposta_r11('neubauer', RID, IDS, {}, {}, ds, CAND, None, 'descrittiva', composizione)


@pytest.mark.parametrize(
    ('lettura', 'atteso'),
    [
        ({'principi': []}, True),
        ({'principi': ''}, True),
        ({'principi': '  '}, True),
        ({'principi': ['nessuno']}, False),
        ({'principi': ['c.budget_residuo']}, False),
        ({'principi': None}, False),  # the field without a value is not an answer
        ({'frase_sostenuta': 'x'}, False),  # nor is a reply without the field
        ({'principi': {}}, False),
        ('principi', False),
        (None, False),
    ],
)
def test_elenco_vuoto(vivi, lettura: Any, atteso: bool) -> None:
    m, _ = vivi
    assert m.elenco_vuoto(lettura) is atteso


def test_cinque_elenchi_vuoti_votano_nessuno(vivi) -> None:
    m, _ = vivi
    letture = [_l05([]) for _ in range(5)]
    assert m.voto_principi(letture, IDS, _can, m.soglia_due) is None  # R12: no valid reading
    vp = m.voto_principi(letture, IDS, _can, m.soglia_due, vuota_vota=True)  # R13
    assert vp['n'] == 5 and vp['maggioranza'] == ['nessuno'] and vp['voti'] == {'nessuno': 5}


def test_un_principio_solo_contro_quattro_elenchi_vuoti(vivi) -> None:
    m, _ = vivi
    letture = [_l05(['c.budget_residuo'])] + [_l05([]) for _ in range(4)]
    r12 = m.voto_principi(letture, IDS, _can, m.soglia_due)
    assert r12['n'] == 1 and r12['maggioranza'] == ['c.budget_residuo']  # 1 of 1: proposed
    r13 = m.voto_principi(letture, IDS, _can, m.soglia_due, vuota_vota=True)
    assert r13['n'] == 5 and r13['maggioranza'] == ['nessuno']  # 1 of 5: not proposed
    assert r13['voti'] == {'c.budget_residuo': 1, 'nessuno': 4}


def test_letture_fallite_non_votano_neanche_con_r13(vivi) -> None:
    m, _ = vivi
    letture = [VUOTA, {'grezzo': '', 'esito': 'ILLEGGIBILE'}, {'frase_sostenuta': FRASE}, {'principi': None}, _l05([])]
    vp = m.voto_principi(letture, IDS, _can, m.soglia_due, vuota_vota=True)
    assert vp['n'] == 1 and [k for k, _, _ in vp['insiemi']] == [4]


def test_r11_e_r12_invariati(vivi) -> None:
    _m, cr = vivi
    letture = [_l05(['c.budget_residuo'])] + [_l05([]) for _ in range(4)]
    for comp in ('R11', 'R12'):
        out = _proposta(cr, letture, comp)
        assert out['provenienza.letture']['principi'] == 1 and out['proposto_principi'] == ['c.budget_residuo']
    assert _proposta(cr, [_l05([]) for _ in range(5)], 'R12') is None


def test_r13_proposta_nessuno_con_provenienza(vivi) -> None:
    _, cr = vivi
    out = _proposta(cr, [_l05([], prosegue4=True) for _ in range(5)], 'R13')
    assert out['proposto_principi'] == ['nessuno'] and out['proposto_principi_da_lettura'] == ['nessuno']
    assert out['provenienza.composizione'] == 'R13' and out['provenienza.letture']['principi'] == 5
    assert out['proposto_principi_voti'] == {'nessuno': '5/5'}
    assert not any(v['prosegue'] for v in out['proposto_estensione'])  # no principle, no page continues
    assert out['proposto_frase_esito'] == 'trovata' and '(R13)' in out['proposto_ripresa_lettore']


def test_r13_non_scavalca_i_freni(vivi) -> None:
    """MUST FAIL: a principle voted with the proof copied from the prompt (the principle's own text) keeps the brakes'
    verdict: the supporting sentence is «inventata», the principle is flagged without proof, the page is not ticked."""
    _, cr = vivi
    dal_prompt = TESTI['c.budget_residuo'][1]
    falsa = [_l05(['c.budget_residuo'], frase=dal_prompt, prova4=dal_prompt, prosegue4=True) for _ in range(3)]
    out = _proposta(cr, [*falsa, _l05([]), _l05([])], 'R13')
    assert out['proposto_principi'] == ['c.budget_residuo'] and out['provenienza.letture']['principi'] == 5
    assert out['proposto_frase_esito'] == 'inventata'
    assert out['proposto_prova_mancante'] and out['proposto_principi_senza_prova'] == ['c.budget_residuo']
    pag = out['proposto_estensione'][0]
    assert pag['prova_esito'] == 'inventata' and not pag['prosegue']
    # and a proof that is simply not on the page («non trovata») stays not found
    altrove = [
        _l05(
            ['c.budget_residuo'],
            frase='a sentence that is on no page of this document at all',
            prosegue4=True,
            prova4='a proof sentence that is on no page of this document either',
        )
        for _ in range(3)
    ]
    out = _proposta(cr, [*altrove, _l05([]), _l05([])], 'R13')
    assert out['proposto_frase_esito'] == 'non trovata' and out['proposto_prova_mancante']
    assert not out['proposto_estensione'][0]['prosegue']
