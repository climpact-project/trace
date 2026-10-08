"""Cited case, probe series and paragraph map, against the live functions."""

from __future__ import annotations

import re

import pytest
from conftest import CAMPIONE, CASI, SERIE, richiede_campione

from tracepipe.caso import CJK, CasoCitato, MappaParagrafi, SerieSonde, forma_regex
from tracepipe.config import Config


@pytest.fixture(scope='module')
def config() -> Config:
    return Config(radice=CAMPIONE)


def test_forma_regex() -> None:
    assert forma_regex('Urgenda v. State') == re.escape('Urgenda v. State')
    r = re.compile(forma_regex('ノイバウアー'))
    assert r.search('ノイバウ\nアー')
    assert r.search('ノイ バウアー')
    assert not re.search(forma_regex('Neubauer'), 'Neu bauer')


def test_come_cerca(vivi) -> None:
    ce = vivi('cerca')
    for f in ('Urgenda', 'Neubauer et al.', '우르헨다', 'アジェンダ 財団', 'BVerfG, 24.3.2021'):
        assert forma_regex(f) == ce.forma_regex(f)
    assert CJK.pattern == ce.CJK.pattern


@pytest.mark.parametrize(
    ('testo', 'atteso'),
    [
        ('4.11-4.19', ['4.11', '4.12', '4.13', '4.14', '4.15', '4.16', '4.17', '4.18', '4.19']),
        ('5.7.5', ['5.7.5']),
        ('117 - 119', ['117', '118', '119']),
        ('4.19-4.11', ['4.19', '4.11']),
        ('1-100', ['1', '100']),
        ('4.1-5.2', ['4.1', '5.2']),
        ('Leitsatz 1', []),
        (254, ['254']),
    ],
)
def test_espandi(vivi, testo: object, atteso: list[str]) -> None:
    assert MappaParagrafi.espandi(testo) == atteso == vivi('principi_da_paragrafi').espandi(testo)


@pytest.mark.parametrize('testo', ['5.7.5-5.7.7, 5.8 and 6', '117 to 119 & 122', '4.83', '4.83\u20134.85', 'x, 3'])
def test_numeri(vivi, testo: str) -> None:
    assert MappaParagrafi.numeri(testo) == vivi('principi_da_paragrafi').numeri(testo)


def test_regex_come_principi_da_paragrafi(vivi) -> None:
    pp = vivi('principi_da_paragrafi')
    from tracepipe import caso

    # the en dash is written as an escape in the package (ruff RUF001): same pattern once unescaped
    assert caso.PAR.pattern.replace('\\u2013', '\u2013') == pp.PAR.pattern
    assert caso.PAR.flags == pp.PAR.flags
    assert caso.MENZIONE_URGENDA.pattern == pp.MENZIONE_URGENDA.pattern
    assert [(c, r.pattern) for c, r in caso.CORTE] == [(c, r.pattern) for c, r in pp.CORTE]


@richiede_campione
@pytest.mark.parametrize('caso', CASI)
def test_mappa_come_viva(vivi, config: Config, caso: str) -> None:
    pp = vivi('principi_da_paragrafi')
    campi = ['sonde'] + ([f'sonde_{SERIE[caso]}'] if caso in SERIE else [])
    for campo in campi:
        assert MappaParagrafi.leggi_mappa(config, caso, campo) == pp.mappa(caso, campo)


@richiede_campione
@pytest.mark.parametrize('caso', CASI)
def test_nome_re_come_prepara(vivi, config: Config, caso: str) -> None:
    """The regex built like tools/classifica_lessicali.prepara and the harness's step 16."""
    import yaml

    ce = vivi('cerca')
    conf = yaml.safe_load((CAMPIONE / 'cited-cases' / f'{caso}.yaml').read_text(encoding='utf-8'))
    forme = sorted({str(f) for f in conf['forme'] if len(str(f)) >= 4}, key=len, reverse=True)
    r = re.compile('|'.join(re.escape(f) for f in forme), re.I) if caso != 'urgenda' else re.compile(r'urgenda', re.I)
    asiatiche = [f for f in forme if ce.CJK.search(f)]
    if asiatiche:
        r = re.compile(r.pattern + '|' + '|'.join(ce.forma_regex(f) for f in asiatiche), re.I)
    c = CasoCitato.carica(config, caso)
    assert c.nome_re().pattern == r.pattern
    assert c.nome_re().flags == r.flags
    menzione = pp_menzione(vivi, caso, forme)
    assert c.menzione_re().pattern == menzione.pattern


def pp_menzione(vivi, caso: str, forme: list[str]) -> re.Pattern[str]:
    pp = vivi('principi_da_paragrafi')
    return pp.MENZIONE_URGENDA if caso == 'urgenda' else re.compile('|'.join(re.escape(f) for f in forme), re.I)


@richiede_campione
@pytest.mark.parametrize('caso', CASI)
def test_serie_sonde(config: Config, caso: str) -> None:
    import yaml

    s = SerieSonde.carica(config, caso)
    sq = yaml.safe_load(config.file_caso(caso).read_text(encoding='utf-8'))['semantic_queries']
    assert s.ids == [x['id'] for x in sq]
    assert s.testi() == {x['id']: (' '.join(x['titolo'].split()), ' '.join(x['testo'].split())) for x in sq}
    assert s.codice == config.codice(caso)
    attesa = '\n'.join(f'- {x["id"]}: {" ".join(x["titolo"].split())}. {" ".join(x["testo"].split())}' for x in sq)
    assert s.elenco_prompt() == attesa


def test_trovati_sintetico() -> None:
    """A synthetic citation page: paragraphs after the name, cut at the semicolon, judgment from nearby words."""
    per = {
        'hoge_raad_2019': {'5.7.5': ['urgenda.a'], '6.1': ['urgenda.b']},
        'hof_2018': {'5.7.5': ['urgenda.c'], '45': ['urgenda.d']},
    }
    m = MappaParagrafi('urgenda', per, re.compile(r'urgenda', re.I))
    ctx = (
        '===== PAGINA PRECEDENTE (fine) =====\nUrgenda, para. 45\n\n'
        '===== PAGINA DELLA CITAZIONE =====\nSee Supreme Court, Urgenda, paras. 5.7.5 and 6.1; Other case para. 45\n'
        '===== PAGINA SUCCESSIVA (inizio) =====\nUrgenda para. 45'
    )
    r = m.principi_riga({'id': 'x', 'contesto': ctx})
    assert r == {
        'id': 'x',
        'paragrafi': ['hoge_raad_2019:5.7.5', 'hoge_raad_2019:6.1'],
        'principi': ['urgenda.a', 'urgenda.b'],
        'metodo': 'mappa dei paragrafi',
    }


def test_sottopunti_come_vivi(vivi_oggi) -> None:
    """Sub-points of the operative clause (08/10/2026): same reading as the live script."""
    pp = vivi_oggi('principi_da_paragrafi')
    for dopo in ['(3)(B)(a), (3)(E). 404', ' (3)(A)(f).', '(A).', ', 273', '(2019)']:
        assert MappaParagrafi.sottopunti(dopo) == pp.sottopunti(dopo)
    tab = {'457': [], '457(3)(B)(a)': ['x'], '457(3)': ['y']}
    for n, s, atteso in [('457', '(3)(B)(a)', '457(3)(B)(a)'), ('457', '(B)(a)', '457(3)(B)(a)'), ('457', '(3)(E)', None),
                         ('457', '(3)', '457(3)'), ('45', '(2019)', None)]:
        assert MappaParagrafi.sottopunto(tab, n, s) == atteso == pp.sottopunto(tab, n, s)
    m = MappaParagrafi('c', {'unica': tab}, re.compile(r'ICJ'))
    r = m.principi_riga({'id': 'x', 'contesto': '===== PAGINA DELLA CITAZIONE =====\nICJ ¶¶ 457(B)(a), (3)(E).'})
    assert r['paragrafi'] == ['unica:457', 'unica:457(3)(B)(a)'] and r['principi'] == ['x']
