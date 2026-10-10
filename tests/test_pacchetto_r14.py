"""R14 (04/10/2026): the brakes look for the proof in the text of the filing, not in the system's markup.

The context sent to the model carries the markers of the flagged passage ([[INIZIO/FINE DEL BRANO SEGNALATO]]) and of
the name (⟦ ⟧), placed at an exact character, often inside a word. The model copies the filing's sentence without them,
and the brake called it «non trovata» (2,211 supporting sentences of 4,696 not found on 04/10/2026), or «inventata»
when the filing's sentence coincides with a probe's text (6 of 9). A word split by a hyphen at a line end did the same
(684 supporting sentences, 3,788 proofs of the surrounding pages). These tests check both repairs AND that every
case that must fail still fails. The package (tracepipe.prova_intera, tracepipe.composizione).
"""

from __future__ import annotations

from typing import Any

import pytest

INIZIO, FINE = '[[INIZIO DEL BRANO SEGNALATO]]', '[[FINE DEL BRANO SEGNALATO]]'
SONDA = (
    'Article 8 of the Convention encompasses a right for individuals to effective protection by the State '
    'authorities from serious adverse effects of climate change'
)
# KLS-0127 (Engels v. Germany): the filing quotes KlimaSeniorinnen; the marker falls inside «Convention»
PAGINA_KLS = (
    'the Court reiterates that Article 8 of the Conve' + INIZIO + 'ntion encompasses a right for individuals to '
    'effective protection by the State authorities from serious adverse effects of climate change on their life, '
    'health, well-being and quality of life (see ⟦Verein KlimaSeniorinnen Schweiz⟧ and Others, cited above) ' + FINE
)
FRASE_KLS = (
    'Article 8 of the Convention encompasses a right for individuals to effective protection by the State '
    'authorities from serious adverse effects of climate change on their life'
)
PAGINA_SILLABE = (
    'Nachdem sich das Risiko von klimabedingten Schäden gemäss ihren Angaben bereits realisiert habe, weist das '
    'Schutzbedürf-\nnis der Klägerinnen und Kläger eine besondere Dringlichkeit auf; die Gerichte über Klima\xad\n'
    'klagen entscheiden ohnehin.'
)
PROVA_SILLABE = (
    'weist das Schutzbedürfnis der Klägerinnen und Kläger eine besondere Dringlichkeit auf; die Gerichte über '
    'Klimaklagen entscheiden'
)


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
def fr() -> Any:
    from tracepipe.prova_intera import FreniProvaIntera

    return FreniProvaIntera()


def test_segni_del_brano_dentro_una_parola(fr) -> None:
    assert fr.verifica(FRASE_KLS, PAGINA_KLS, [SONDA]) == 'inventata'  # R05-R13: a false «invented»
    assert fr.verifica(FRASE_KLS, PAGINA_KLS, [SONDA], True) == 'trovata'  # R14: it is the filing's sentence


def test_segno_fra_due_parole_e_segni_del_nome(fr) -> None:
    pagina = (
        'The State must reduce its emissions ' + INIZIO + 'without delay, as held in ⟦Urgenda⟧ by the Supreme Court.'
    )
    prova = 'The State must reduce its emissions without delay, as held in Urgenda by the Supreme Court'
    assert fr.verifica(prova, pagina) == 'non trovata'
    assert fr.verifica(prova, pagina, (), True) == 'trovata'


def test_parola_spezzata_a_capo(fr) -> None:
    assert fr.verifica(PROVA_SILLABE, PAGINA_SILLABE) == 'non trovata'
    assert fr.verifica(PROVA_SILLABE, PAGINA_SILLABE, (), True) == 'trovata'
    # the text with the hyphen is still compared as it is
    assert (
        fr.verifica('weist das Schutzbedürf nis der Klägerinnen und Kläger eine besondere', PAGINA_SILLABE, (), True)
        == 'trovata'
    )


@pytest.mark.parametrize('ricostruisci', [False, True])
def test_devono_fallire(fr, ricostruisci: bool) -> None:
    """MUST FAIL with and without R14: copied from the prompt, from another page, paraphrased, too short, empty."""
    pagina = 'The Court found that the applicants had standing and that ' + INIZIO + 'the State failed to act. ' + FINE
    assert fr.verifica(SONDA, pagina, [SONDA], ricostruisci) == 'inventata'
    assert fr.verifica(PROVA_SILLABE, pagina, [SONDA], ricostruisci) == 'non trovata'
    assert (
        fr.verifica(
            'The court held that the applicants lacked standing and the State acted lawfully', pagina, [], ricostruisci
        )
        == 'non trovata'
    )
    assert fr.verifica('the State failed', pagina, [], ricostruisci) == 'assente'
    assert fr.verifica('', pagina, [], ricostruisci) == 'assente'
    # R14 never rejects what R05-R13 accepted: the page as it is stays one of the texts searched (on 04/10/2026, 804
    # supporting sentences were copied with the markers inside, 4 of them found only that way)
    marcata = 'that ' + INIZIO + 'the State failed to act'
    assert fr.verifica(marcata, pagina, [], False) == fr.verifica(marcata, pagina, [], True) == 'trovata'
    # joining a split word never joins two words that were separated by a plain space or a hyphen without a line end
    assert not fr.prova_trovata('the applicantshad standing and that the State failed to act', pagina, True)


def test_cjk_invariato(fr) -> None:
    pagina = '気候変動訴訟において裁判所はドイ\nツの連邦憲法裁判所の決定を引用し、国家の義務を認めた。' * 2
    prova = '気候変動訴訟において裁判所はドイツの連邦憲法裁判所の決定を引用し、国家の義務を認めた'
    assert fr.verifica(prova, pagina) == fr.verifica(prova, pagina, (), True) == 'trovata'


def test_senza_ricostruisci_e_il_freno_di_prima(fr) -> None:
    """the default is the R05-R13 brake, character for character, on the cases above"""
    for prova, pagina in ((FRASE_KLS, PAGINA_KLS), (PROVA_SILLABE, PAGINA_SILLABE), (SONDA, PAGINA_KLS)):
        p = fr.norm(prova)
        atteso = p[: fr.lunghezza_confronto] in fr.norm(pagina)
        assert fr.prova_trovata(prova, pagina) is atteso


@pytest.fixture
def cr() -> Any:
    return _ComeStrumento({'k.art8': ('Art 8', SONDA)}, 'P06', 'R09')


def test_composizione_r14_sulla_riga_kls_0127(cr) -> None:
    rid = 'klimaseniorinnen__engels__1'
    cand = {
        rid: {
            'pagina': 5,
            'contesto': PAGINA_KLS,
            'vicine': [{'pagina': 6, 'punteggi': {'k.art8': 0.9}, 'testo': PAGINA_SILLABE}],
        }
    }
    y = {
        'frase_sostenuta': FRASE_KLS,
        'principi': ['k.art8'],
        'altro': '',
        'motivo': 'm',
        'vicine': [{'pagina': 6, 'prosegue': True, 'principio': 'art8', 'prova': PROVA_SILLABE}],
    }
    ds = {rid: {'id': rid, 'data': '2026-10-03', 'letture': [dict(y) for _ in range(5)]}}
    prima = cr.proposta_r11('klimaseniorinnen', rid, ['k.art8'], {}, {}, ds, cand, None, 'sostanziale', 'R13')
    dopo = cr.proposta_r11('klimaseniorinnen', rid, ['k.art8'], {}, {}, ds, cand, None, 'sostanziale', 'R14')
    assert prima['proposto_frase_esito'] == 'inventata' and prima['proposto_prova_mancante']
    assert not prima['proposto_frase_testuale'] and not prima['proposto_estensione'][0]['prosegue']
    assert dopo['proposto_frase_esito'] == 'trovata' and not dopo['proposto_prova_mancante']
    assert dopo['proposto_frase_testuale'] and dopo['proposto_estensione'][0]['prosegue']
    assert dopo['provenienza.composizione'] == 'R14' and dopo['proposto_principi'] == prima['proposto_principi'] == [
        'k.art8'
    ]


def test_uguale_a_oggi(cr) -> None:
    campi = {
        'provenienza.composizione': 'R14',
        'proposto_ripresa_lettore': 'x',
        'proposto_principi': ['a'],
        'proposto_estensione': [{'pagina': 3, 'prosegue': False, 'scelta': {'punteggio': 0.5}}],
    }
    oggi = {
        'provenienza': {'composizione': 'R12'},
        'proposto_ripresa_lettore': 'y',
        'proposto_principi': ['a'],
        'proposto_estensione': [{'scelta': {'punteggio': 0.5}, 'prosegue': False, 'pagina': 3}],
    }
    assert cr.uguale_a_oggi(oggi, campi)
    assert not cr.uguale_a_oggi(dict(oggi, proposto_principi=['b']), campi)
    assert not cr.uguale_a_oggi({k: v for k, v in oggi.items() if k != 'proposto_estensione'}, campi)
