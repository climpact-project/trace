"""Freni: the brakes, identical to tools/freni.py (synthetic cases, the whole sample index, step 15 of the harness)."""

from __future__ import annotations

import gzip
import json

import pytest
from conftest import ATTESI, CAMPIONE, attesi_jsonl, richiede_attesi, richiede_campione

from tracepipe.freni import FRENI, Freni

LATINO = ' '.join(['the court held that the state has a duty of care towards its citizens'] * 5)
CIRILLICO = ' '.join(['суд постановил что государство обязано защищать граждан от изменения климата'] * 6)
GIAPPONESE = '気候変動訴訟において裁判所は国家の義務を認めた。' * 12
THAI = 'ศาลตัดสินว่ารัฐมีหน้าที่ปกป้องประชาชนจากการเปลี่ยนแปลงสภาพภูมิอากาศ' * 5
ROTTO = ' '.join(
    [
        ' '.join(
            chr(c)
            for c in (
                0x0402,
                0x0403,
                0x201A,
                0x0453,
                0x201E,
                0x2026,
                0x2020,
                0x2021,
                0x20AC,
                0x2030,
                0x0409,
                0x2039,
                0x040A,
                0x040C,
                0x040B,
                0x040F,
            )
        )
    ]
    * 5
)
SPAZZATURA = ' '.join(['xq7 zz9 ##4 kk1 ppp qqq'] * 10)
INDICE = ' '.join(['1. Introduction .......... 3', '2. Facts .......... 7'] * 15)

TESTI = [LATINO, CIRILLICO, GIAPPONESE, THAI, ROTTO, SPAZZATURA, INDICE, '', 'troppo poche parole', None, 12345]


@pytest.mark.parametrize('testo', TESTI)
def test_leggibile_come_vivo(vivi, testo: object) -> None:
    assert FRENI.leggibile(testo) == vivi('freni').leggibile(testo)


def test_leggibile_esiti() -> None:
    assert FRENI.leggibile(LATINO)[0]
    assert FRENI.leggibile(CIRILLICO)[0]
    assert FRENI.leggibile(GIAPPONESE)[0]
    assert FRENI.leggibile(THAI)[0]
    assert not FRENI.leggibile(SPAZZATURA)[0]
    assert FRENI.leggibile('troppo poche parole') == (False, 0.0)


PROVE_ = [
    ('the state has a duty of care towards its citizens', LATINO, ()),
    ('THE STATE, has a duty   of care towards its citizens!', LATINO, ()),
    ('a sentence that is nowhere in the page at all', LATINO, ('a sentence that is nowhere in the page at all',)),
    ('a sentence that is nowhere in the page at all', LATINO, ('another prompt text entirely, not matching',)),
    ('short', LATINO, ()),
    ('', LATINO, ()),
    (None, LATINO, ()),
    ('裁判所は国家の義務を認めた。気候変動訴訟において', GIAPPONESE.replace('。', '。\n '), ()),
    ('裁判所は 国家の 義務を 認めた。 気候変動訴訟に おいて', GIAPPONESE, ()),
]


@pytest.mark.parametrize(('prova', 'pagina', 'prompt'), PROVE_)
def test_verifica_come_vivo(vivi, prova: object, pagina: str, prompt: tuple[str, ...]) -> None:
    f = vivi('freni')
    assert FRENI.verifica(prova, pagina, prompt) == f.verifica(prova, pagina, prompt)
    assert FRENI.prova_trovata(prova, pagina) == f.prova_trovata(prova, pagina)
    assert FRENI.prova_dal_prompt(prova, prompt) == f.prova_dal_prompt(prova, prompt)
    assert Freni.norm(prova) == f.norm(prova)


def test_verifica_esiti() -> None:
    assert FRENI.verifica(PROVE_[0][0], LATINO) == 'trovata'
    assert FRENI.verifica(PROVE_[2][0], LATINO, PROVE_[2][2]) == 'inventata'
    assert FRENI.verifica(PROVE_[3][0], LATINO, PROVE_[3][2]) == 'non trovata'
    assert FRENI.verifica('short', LATINO) == 'assente'
    assert FRENI.verifica(PROVE_[8][0], GIAPPONESE) == 'trovata'


@richiede_campione
def test_leggibile_su_tutto_l_indice_del_campione(vivi) -> None:
    """Every page of both sample indices (today and before OCR): same verdict and share as the live function."""
    f = vivi('freni')
    n = 0
    for nome in ('pagine.jsonl.gz', 'pagine.prima-ocr-2026-10-01.jsonl.gz'):
        with gzip.open(CAMPIONE / 'index' / 'pagine' / nome, 'rt', encoding='utf-8') as h:
            for riga in h:
                t = json.loads(riga)['testo']
                assert FRENI.leggibile(t) == f.leggibile(t)
                n += 1
    assert n > 1000


@richiede_attesi
def test_passo_15_freni_leggibile() -> None:
    """Step 15 of the harness: readability of the listed pages, today and before OCR."""
    lista = json.loads((CAMPIONE / 'fixture' / 'pagine_freni.json').read_text(encoding='utf-8'))
    voglio = set(lista)

    def testi(nome: str) -> dict[str, str]:
        t = {}
        with gzip.open(CAMPIONE / 'index' / 'pagine' / nome, 'rt', encoding='utf-8') as h:
            for riga in h:
                x = json.loads(riga)
                if x['id'] in voglio:
                    t[x['id']] = x['testo']
        return t

    oggi, prima = testi('pagine.jsonl.gz'), testi('pagine.prima-ocr-2026-10-01.jsonl.gz')
    nuovo = []
    for pid in lista:
        r = {'id': pid}
        for nome, t in (('oggi', oggi), ('prima_ocr', prima)):
            if pid in t:
                ok, quota = FRENI.leggibile(t[pid])
                r[nome] = {'leggibile': ok, 'quota': quota, 'caratteri': len(t[pid])}
            else:
                r[nome] = None
        nuovo.append(r)
    atteso = attesi_jsonl(ATTESI / '15_freni_leggibile' / 'file' / 'banco' / 'freni_leggibile.jsonl')
    assert nuovo == atteso
