"""Config: paths, probe series and thresholds mirror the live scripts."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from conftest import CAMPIONE, CASI, RADICE, STRUMENTI, STRUMENTI_CAMPIONE, richiede_campione

from tracepipe.config import CASI as CASI_CONFIG
from tracepipe.config import Config, LimitiDeepSeek, SerieMancanteError, SoglieFinestra


def test_radice_predefinita_e_il_progetto() -> None:
    assert Config().radice == Path(__file__).resolve().parent.parent
    c = Config(radice=Path('/x'))
    assert c.indice_pagine == Path('/x/index/pagine/pagine.jsonl.gz')
    assert c.principi == Path('/x/training/principi')
    assert c.cited_cases == Path('/x/cited-cases')
    assert c.pagine_sostituite == Path('/x/training/ocr/pagine_sostituite.json')


def test_config_immutabile() -> None:
    c = Config()
    with pytest.raises(AttributeError):
        c.radice = Path('/y')  # type: ignore[misc]


def test_casi() -> None:
    assert CASI_CONFIG == CASI


def test_soglie_finestra() -> None:
    s = SoglieFinestra()
    assert [s.soglia(d) for d in (-3, -2, 0, 3, 4)] == [0.8, 0.5, 0.5, 0.5, 0.8]
    assert (s.larga, s.max_vicine_larga, s.taglio_vicina) == (10, 5, 3500)
    r10 = SoglieFinestra.per_regola('R10')
    assert [r10.soglia(d) for d in (-10, -3, -2, 0, 3, 4, 10)] == [0.5] * 7
    assert (r10.larga, r10.max_vicine_larga, r10.regola) == (10, None, 'R10')
    assert SoglieFinestra.per_regola('R08') == s


RIFERIMENTO = '8650281'
"""The commit of ``tools/`` the harness copy was aligned to (prove/campione/fixture/sorgente.json)."""
CAMBIATI_DOPO = {
    'chiamata_deepseek',
    'classifica_lessicali',
    'leggi_ripresa',
    'leggi_l04',
    'carica_ripresa',
    'carica_lessicali',
    'freni',
    'giornale',
    'pubblica',
    'cerca',
    'unisci_e_aggiungi',
    'controllo_completezza',
}
"""Live scripts changed after the harness (02/10/2026 evening: temperature, seed, call record, full reasoning; then the
options of the five readings, default unchanged: ``--regola R10``, ``--aggiungi-letture``, ``--composizione R11``;
03/10/2026, the external review: Thai, Lao, Khmer and Myanmar in the evidence check; the journal says its own errors
on stderr and in ``giornale/errori_giornale.log`` instead of swallowing them; 04/10/2026: ``pubblica`` keeps a full
copy of the rows it overwrites, tools/copia_prima.py; S07: footnote-aware grouping in ``cerca`` and
``unisci_e_aggiungi``, R15 known to ``controllo_completezza``)."""


def _git_show(percorso: str) -> bytes | None:
    try:
        r = subprocess.run(
            ['git', '-C', str(RADICE), 'show', f'{RIFERIMENTO}:{percorso}'],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


@pytest.mark.parametrize(
    'nome',
    [
        'sonde',
        'freni',
        'chiamata_deepseek',
        'giudica_llm',
        'classifica_lessicali',
        'leggi_ripresa',
        'leggi_l04',
        'carica_ripresa',
        'carica_lessicali',
        'principi_da_paragrafi',
        'cerca',
        'unisci_e_aggiungi',
        'controllo_completezza',
        'controllo_finestra',
        'giornale',
        'dimensioni',
        'posizione_dopo_ocr',
        'pubblica',
    ],
)
@richiede_campione
def test_strumenti_del_campione_come_il_riferimento(nome: str) -> None:
    """The sample copy is ``tools/`` at the reference commit; today's ``tools/`` differs only where it was changed."""
    if not STRUMENTI_CAMPIONE.exists():
        pytest.skip('prove/campione absent')
    rif = _git_show(f'tools/{nome}.py')
    if rif is None:
        pytest.skip('git history not available')
    assert (STRUMENTI_CAMPIONE / f'{nome}.py').read_bytes() == rif
    assert ((STRUMENTI / f'{nome}.py').read_bytes() == rif) == (nome not in CAMBIATI_DOPO)


def test_costanti_come_gli_strumenti(vivi) -> None:
    lr, cd, cr = vivi('leggi_ripresa'), vivi('chiamata_deepseek'), vivi('carica_ripresa')
    s, d = SoglieFinestra(), LimitiDeepSeek()
    assert (s.larga, s.soglia_vicina, s.soglia_lontana, s.max_vicine, s.max_vicine_larga, s.taglio_vicina) == (
        lr.LARGA,
        lr.SOGLIA_VICINA,
        lr.SOGLIA_LONTANA,
        lr.MAX_VICINE,
        lr.MAX_VICINE_LARGA,
        lr.TAGLIO_VICINA,
    )
    assert (d.tetto, d.tetto_alto, d.contesto, d.margine) == (cd.TETTO, cd.TETTO_ALTO, cd.CONTESTO, cd.MARGINE)
    assert Config().soglia_reranker == cr.SOGLIA_RERANKER


def test_serie_come_sonde(vivi) -> None:
    so = vivi('sonde')
    c = Config()
    assert dict(c.serie_in_uso) == so.SERIE_IN_USO
    assert set(c.storiche) == so.STORICHE
    assert dict(c.prima_serie) == so.PRIMA_SERIE


@richiede_campione
@pytest.mark.parametrize('trace_sonde', ['', 'P02', 'P03', 'P05', 'P09'])
def test_serie_suf_storica_codice(vivi, monkeypatch: pytest.MonkeyPatch, trace_sonde: str) -> None:
    """For every case and every TRACE_SONDE, the helpers answer as tools/sonde.py (or both stop)."""
    so = vivi('sonde')
    c = Config(radice=CAMPIONE, trace_sonde=trace_sonde)
    if trace_sonde:
        monkeypatch.setenv('TRACE_SONDE', trace_sonde)
    for caso in (*CASI, None):
        try:
            atteso = (so.serie(caso), so.suf(caso), so.storica(caso))
        except SystemExit as e:
            with pytest.raises(SerieMancanteError) as err:
                c.serie(caso)
            assert str(err.value) == str(e)
            continue
        assert (c.serie(caso), c.suf(caso), c.storica(caso)) == atteso
        if caso:
            assert c.codice(caso) == so.codice(caso)
            assert c.file_caso(caso) == so.file_caso(caso)
            assert c.file_fascicolo(caso) == so.file_fascicolo(caso)


def test_da_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('TRACE_SONDE', 'P03')
    assert Config.da_ambiente().trace_sonde == 'P03'


def test_codice_mappa() -> None:
    c = Config()
    assert c.codice_mappa('neubauer') == 'R07'
    assert c.codice_mappa('urgenda') == 'R04'
    assert c.codice_mappa('cig-parere-clima') == 'R09'
