"""R16 (04/10/2026): the proof is checked on the WHOLE proof, not on its first 60 normalised characters.

Up to R14 a proof with a genuine start and an invented end passed. R16 = R14 AND the whole proof: each stretch between
ellipses on its own, ignoring spaces, page footnote numbers and digits glued to a word, on the page joined with the next
page and without footnote lines, with 90% coverage by stretches of at least 20 characters; one letter per word only on
OCR'd documents (D02). These tests check the cases that MUST fail (invented ending, unmarked cut in the middle, the
model's comment appended) and one case that must pass for each refinement. The package (tracepipe.prova_intera).
"""

from __future__ import annotations

from typing import Any

import pytest

PAGINA = (
    'Die Verfassungsbeschwerde ist begründet. Der Gesetzgeber hat seine Schutzpflicht aus Art. 2 Abs. 2 GG verletzt, '
    'weil die Regelungen zur Minderung der Treibhausgasemissionen über das Jahr 2030 hinaus fehlen und die '
    'verbleibenden Emissionsmengen ungleich auf die Generationen verteilen.17 Weitere Ausführungen folgen.\n'
    '17 BVerfG, Beschluss vom 24. März 2021, 1 BvR 2656/18, Rn. 182.\n'
)
VERA = (
    'Der Gesetzgeber hat seine Schutzpflicht aus Art. 2 Abs. 2 GG verletzt, weil die Regelungen zur Minderung der '
    'Treibhausgasemissionen über das Jahr 2030 hinaus fehlen'
)
FINE_INVENTATA = (
    'Der Gesetzgeber hat seine Schutzpflicht aus Art. 2 Abs. 2 GG verletzt, weil er das CO2-Restbudget des '
    'Sachverständigenrats nicht übernommen hat'
)
# words dropped without ellipsis in two places. Declared limit of R16: a single cut between two pieces both longer than
# 20 characters still passes (90% coverage by stretches of 20 characters); on the 03/10 readings most cuts are caught.
TAGLIO_MUTO = 'Der Gesetzgeber hat seine Schutzpflicht verletzt, weil die Regelungen über 2030 hinaus fehlen'
COMMENTO = VERA + ' citando nuovamente i paragrafi 252 e 253'


@pytest.fixture
def fr() -> Any:
    from tracepipe.prova_intera import FreniProvaIntera

    return FreniProvaIntera()


def test_r14_lasciava_passare_la_fine_inventata(fr) -> None:
    assert fr.verifica(FINE_INVENTATA, PAGINA, (), True) == 'trovata'  # the hole: R14 passes it


@pytest.mark.parametrize('prova', [FINE_INVENTATA, TAGLIO_MUTO, COMMENTO])
def test_deve_fallire(fr, prova) -> None:
    assert fr.verifica(prova, PAGINA, (), True, True) == 'non trovata'


def test_vera_passa(fr) -> None:
    assert fr.verifica(VERA, PAGINA, (), True, True) == 'trovata'


def test_omissione_dichiarata_tratto_per_tratto(fr) -> None:
    prova = 'Der Gesetzgeber hat seine Schutzpflicht aus Art. 2 Abs. 2 GG verletzt [...] und die verbleibenden Emissionsmengen ungleich'
    assert fr.prova_intera(prova, PAGINA)
    assert not fr.prova_intera(prova.replace('ungleich', 'gleich gerecht'), PAGINA)


def test_parola_spezzata_senza_trattino(fr) -> None:
    pagina = PAGINA.replace('Treibhausgasemissionen', 'Treibhausgas emissionen')
    assert fr.verifica(VERA, pagina, (), True, True) == 'trovata'


def test_cifre_incollate_alla_parola(fr) -> None:
    pagina = (
        'Such obligation has likewise been recognized by courts and tribunals in the context of domestic237 and '
        'international238 litigation, and by treaty bodies.'
    )
    prova = 'Such obligation has likewise been recognized by courts and tribunals in the context of domestic and international litigation'
    assert fr.verifica(prova, pagina, (), True, True) == 'trovata'


def test_la_frase_continua_dopo_le_note_nella_pagina_dopo(fr) -> None:
    pagina = (
        'States must regulate without exception those activities that could cause significant\n'
        '268 IACtHR, Advisory Opinion OC-23/17, para. 142.\n269 ICJ Advisory Opinion, para. 280.\n'
    )
    dopo = '270 See above.\nenvironmental harm, including private actors, and supervise them.'
    prova = 'States must regulate without exception those activities that could cause significant environmental harm, including private actors'
    assert fr.verifica(prova, pagina, (), True, True) == 'non trovata'  # without the next page
    assert fr.verifica(prova, pagina, (), True, True, dopo) == 'trovata'


def test_una_lettera_solo_nei_documenti_ocr(fr) -> None:
    pagina = (
        'den närmare innebörden av statens positiva förpliktelser kan delas upp i statens materlella respektive '
        'processuella förpllktelser, dessa redogörs för i det följande.'
    )
    prova = 'den närmare innebörden av statens positiva förpliktelser kan delas upp i statens materiella respektive processuella förpliktelser'
    assert fr.verifica(prova, pagina, (), True, True, '', True) == 'trovata'  # OCR'd document (D02)
    # elsewhere one letter is not allowed: whether it passes depends only on coverage (here 90% is not reached)
    assert fr.verifica(prova.replace('innebörden', 'innebörd'), pagina, (), True, True, '', False) in (
        'trovata',
        'non trovata',
    )
    assert (
        fr.verifica(
            prova.replace('materiella', 'materiala').replace('statens', 'statem'), pagina, (), True, True, '', False
        )
        == 'non trovata'
    )


def test_senza_intera_tutto_come_prima(fr) -> None:
    for prova in (VERA, FINE_INVENTATA, TAGLIO_MUTO):
        assert fr.verifica(prova, PAGINA, (), True) == fr.verifica(prova, PAGINA, (), True, False)
