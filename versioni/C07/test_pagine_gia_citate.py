"""C07, a surrounding page that is a citation of its own: marks, principles, the ticked pages of the team, the writes.

Synthetic filings and rows only. The last tests compare the package with the live ``tools/controlli_automatici.py`` and
``tools/applica_c07.py`` when ``tools/`` is there (it is not in the public repository: they are skipped).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from tracepipe.banca import BancaDatiMemoria
from tracepipe.config import Config
from tracepipe.copia_prima import CopiaPrima
from tracepipe.pagine_gia_citate import (
    ApplicaC07,
    RiconoscitorePagine,
    RisultatoC07,
    TutteLeRilette,
    segno_c07,
    spazi_pagine,
    voti,
)

TESTO = (
    '---\ndocument_id: doc1\n---\n'
    '<!-- page 1 -->\nThe applicants rely on the Neubauer decision about the reduction path.\n'
    '<!-- page 2 -->\nA second, separate reference to the decision, with its own reasoning about the burden.\n'
    '<!-- page 3 -->\nSomething else, about costs.\n'
)
FRASE_B = 'A second, separate reference to the decision, with its own reasoning about the burden.'
PROVA = 'a second separate reference to the decision with its own reasoning about the burden'


def posizione(frammento: str) -> int:
    return TESTO.index(frammento)


def riga(codice: str, frammento: str, **kw: Any) -> dict[str, Any]:
    r: dict[str, Any] = {
        'codice': codice,
        'document_id': 'doc1',
        'caso_citato': 'neubauer',
        'proposto_rete': 'lessicale',
        'file': 'markdown/doc1.md',
        'char_start': posizione(frammento),
        'proposto_principi': ['p.a'],
    }
    r.update(kw)
    return r


def estensione(pagina: int, prosegue: bool = False, **kw: Any) -> dict[str, Any]:
    return {'pagina': pagina, 'prosegue': prosegue, 'principio': 'p.a', 'prova': 'x', **kw}


def banca_base(**kw_a: Any) -> dict[str, dict[str, Any]]:
    """Row A on page 1 looks at page 2; row B (another principle) sits on page 2."""
    return {
        'a': riga('NEU-0001', 'The applicants', proposto_estensione=[estensione(2), estensione(3)], **kw_a),
        'b': riga('NEU-0002', 'A second, separate', proposto_principi=['p.b']),
    }


def atti(tmp_path: Path) -> Config:
    (tmp_path / 'markdown').mkdir(exist_ok=True)
    (tmp_path / 'markdown' / 'doc1.md').write_text(TESTO, encoding='utf-8')
    return Config(radice=tmp_path)


class Prova(NamedTuple):
    passo: ApplicaC07
    db: BancaDatiMemoria
    detto: list[str]


def passo(tmp_path: Path, banca: dict[str, Any], scrivi: bool = False, **kw: Any) -> Prova:
    db = BancaDatiMemoria({'corpus_rows': banca})
    detto: list[str] = []
    a = ApplicaC07(
        atti(tmp_path),
        db,
        'prova',
        scrivi=scrivi,
        copia=CopiaPrima(tmp_path, cartella=tmp_path / 'copie', stampa=lambda t: None),
        stampa=detto.append,
        **kw,
    )
    return Prova(a, db, detto)


def test_spazi_pagine_vanno_da_un_segno_al_successivo() -> None:
    sp = spazi_pagine(TESTO)
    assert sorted(sp) == [1, 2, 3]
    assert TESTO[sp[2][0] : sp[2][1]].startswith('\nA second, separate')
    assert sp[3][1] == len(TESTO)
    assert spazi_pagine('niente pagine') == {}


def test_voti_legge_n_su_cinque() -> None:
    assert voti({'proposto_principi_voti': {'p': '3/5'}}, 'p') == 3
    assert voti({'proposto_principi_voti': {'p': 'x'}}, 'p') == 0
    assert voti({}, 'p') == 0


def test_il_segno_nomina_le_altre_righe() -> None:
    assert segno_c07(['NEU-0002', 'NEU-0003']) == 'also cited separately as NEU-0002, NEU-0003'


# the recogniser


def test_un_altra_riga_sulla_pagina_la_marca_per_posizione() -> None:
    b = banca_base()
    sp = spazi_pagine(TESTO)
    marcate = RiconoscitorePagine().pagine(b['a'], b.values(), sp)
    assert list(marcate) == [2]
    assert marcate[2].posizione and not marcate[2].testo and not marcate[2].seguito
    assert marcate[2].codici == ('NEU-0002',) and marcate[2].segno == 'also cited separately as NEU-0002'


def test_la_prova_uguale_alla_frase_dell_altra_riga_marca_per_testo() -> None:
    """The other row is NOT on the page (its point is elsewhere), but its sentence is the proof of the page."""
    b = banca_base()
    b['a']['proposto_estensione'][0]['prova'] = PROVA
    b['b']['char_start'] = posizione('Something else')  # on page 3
    b['b']['proposto_frase_sostenuta'] = (
        'A second, separate reference to the decision, with its own reasoning about the burden.'
    )
    marcate = RiconoscitorePagine().pagine(b['a'], b.values(), spazi_pagine(TESTO))
    assert marcate[2].testo and not marcate[2].posizione
    # the case that MUST fail: a short proof never matches by text
    b['a']['proposto_estensione'][0]['prova'] = 'too short'
    assert 2 not in RiconoscitorePagine().pagine(b['a'], b.values(), spazi_pagine(TESTO))


def test_un_principio_in_comune_lascia_la_pagina_candidata() -> None:
    b = banca_base()
    b['b']['proposto_principi'] = ['p.a', 'p.c']
    marcate = RiconoscitorePagine().pagine(b['a'], b.values(), spazi_pagine(TESTO))
    assert marcate[2].seguito


def test_nessuno_non_e_un_principio_in_comune() -> None:
    b = banca_base()
    b['a']['proposto_principi'] = ['nessuno']
    b['b']['proposto_principi'] = ['nessuno']
    assert not RiconoscitorePagine().pagine(b['a'], b.values(), spazi_pagine(TESTO))[2].seguito


def test_le_righe_non_vive_non_contano() -> None:
    b = banca_base()
    b['b']['proposto_rete'] = 'esclusa'
    assert RiconoscitorePagine().pagine(b['a'], b.values(), spazi_pagine(TESTO)) == {}


# the step


def test_la_pagina_marcata_segna_la_voce_e_non_cancella_la_lettura(tmp_path: Path) -> None:
    banca = banca_base()
    banca['a']['proposto_estensione'][0]['prosegue'] = False
    p = passo(tmp_path, banca)
    ris = p.passo.esegui()
    voce = ris.scritture['a']['proposto_estensione'][0]
    assert voce['c07'] is True and voce['c07_altra_riga'] == 'NEU-0002' and 'NEU-0002' in voce['c07_segno']
    assert 'c07' not in ris.scritture['a']['proposto_estensione'][1]
    assert ris.segni == 1 and p.db.scritture == []
    assert banca['a']['proposto_estensione'][0].get('c07') is None  # the snapshot is untouched


def test_le_pagine_che_proseguono_aspettano_la_rilettura(tmp_path: Path) -> None:
    banca = banca_base()
    banca['a']['proposto_estensione'][0]['prosegue'] = True
    ris = passo(tmp_path, banca).passo.esegui()
    assert ris.scritture == {} and ris.da_rileggere == [('NEU-0001', 2, 'NEU-0002', '')]
    # reread by hand as another citation: now it is applied, and `prosegue` stays as DeepSeek read it
    ris = passo(tmp_path, banca, rilette={('NEU-0001', 2)}).passo.esegui()
    voce = ris.scritture['a']['proposto_estensione'][0]
    assert voce['c07'] and voce['prosegue'] is True and ris.da_rileggere == []


def test_l_ipotesi_tutte_non_si_usa_con_scrivi(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        passo(tmp_path, banca_base(), scrivi=True, ipotesi_tutte=True)
    assert 'x' in TutteLeRilette()


def test_le_righe_giudicate_non_si_toccano(tmp_path: Path) -> None:
    banca = banca_base(esito='confermata')
    ris = passo(tmp_path, banca).passo.esegui()
    assert ris.scritture == {} and ris.saltate == [('NEU-0001', 2, 'NEU-0002', 'confermata')]


def test_il_principio_che_l_altra_riga_non_ha_resta_e_va_al_team(tmp_path: Path) -> None:
    banca = banca_base(proposto_principi_voti={'p.a': '1/5'})
    banca['a']['proposto_estensione'][0] = estensione(2, prosegue=True)
    ris = passo(tmp_path, banca, rilette={('NEU-0001', 2)}).passo.esegui()
    assert 'proposto_principi' not in ris.scritture['a'] and ris.tolti == []
    assert ris.per_il_team == [('NEU-0001', 'p.a', 2, 'NEU-0002', 'p.b')]


def test_il_principio_si_toglie_solo_con_tutte_le_condizioni(tmp_path: Path) -> None:
    """Reachable only by calling the check directly: a marked page means no shared principle, so the other row cannot
    hold P. The conditions are still written down, and each one keeps the principle when it fails."""
    p = passo(tmp_path, {}).passo
    per_codice = {'NEU-0002': {'codice': 'NEU-0002', 'proposto_principi': ['p.a']}}
    pagina = dict(estensione(2, prosegue=True), c07=True, c07_altra_riga='NEU-0002')

    def prova(**kw: Any) -> dict[str, Any]:
        r = {'codice': 'NEU-0001', 'proposto_principi': ['p.a'], 'proposto_principi_voti': {'p.a': '1/5'}, **kw}
        return p.principi_da_togliere(r, [pagina], per_codice, RisultatoC07())

    campi = prova()
    assert campi['proposto_principi'] == ['nessuno'] and campi['principi_tolti_c07'][0]['altra_riga'] == 'NEU-0002'
    assert 'p. 2' in campi['principi_tolti_c07'][0]['motivo'] and '1/5' in campi['principi_tolti_c07'][0]['motivo']
    assert prova(proposto_principi_voti={'p.a': '3/5'}) == {}  # held by the readings
    assert prova(proposto_principi_da_mappa=['p.a']) == {}  # in the map of the cited paragraphs


def test_le_spunte_del_team_si_tolgono_con_la_traccia(tmp_path: Path) -> None:
    banca = banca_base(esito='confermata', validato_estensione=[2, 3])
    rev = tmp_path / 'rev.tsv'
    with open(rev, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, delimiter='\t')
        w.writerow(['riga', 'pagina_attorno', 'team_spunta_seguito', 'revisione', 'altre_righe_sulla_pagina', 'motivo'])
        w.writerows(
            [
                ('NEU-0001', 2, 'si', 'ALTRA CITAZIONE', 'NEU-0002, NEU-0009', 'letta a mano'),
                ('NEU-0001', 3, 'no', 'ALTRA CITAZIONE', 'NEU-0002', 'non spuntata dal team'),
                ('NEU-9999', 2, 'si', 'ALTRA CITAZIONE', 'NEU-0002', 'riga assente'),
                ('NEU-0001', 2, 'si', 'ALTRA CITAZIONE', 'NEU-0002', 'gia tolta due volte'),
            ]
        )
    p = passo(tmp_path, banca, revisione=rev)
    ris = p.passo.esegui()
    c = ris.scritture['a']
    assert c['validato_estensione'] == [3]
    voce = c['proposto_estensione'][0]
    assert voce['c07'] and voce['c07_altra_riga'] == 'NEU-0002'
    assert c['c07_spunte_tolte'][0]['pagina'] == 2 and c['c07_spunte_tolte'][0]['motivo'] == 'C07 letta a mano'
    assert 'esito' not in c and 'validato_principi' not in c  # the verdict and the principles stay the team's
    assert any('saltate (riga assente): 1' in x for x in p.detto)
    assert any("saltate (spunta gia' tolta): 1" in x for x in p.detto)


def test_scrive_la_copia_prima_poi_le_righe(tmp_path: Path) -> None:
    banca = banca_base()
    p = passo(tmp_path, banca, scrivi=True)
    ris = p.passo.esegui()
    assert len(p.db.scritture) == 1 and p.db.scritture[0]['op'] == 'update'
    dati = p.db.scritture[0]['dati']
    assert dati['c07_da'] == 'prova' and dati['c07_il'] == '__SERVER_TIMESTAMP__'
    copie = list((tmp_path / 'copie').glob('prima_applica_c07_*.json.gz'))
    assert len(copie) == 1 and set(CopiaPrima.leggi(copie[0])['righe']) == set(ris.scritture)
    assert 'proposto_estensione' in CopiaPrima.leggi(copie[0])['righe']['a']['prima']


def test_gli_elenchi_e_gli_esempi_si_scrivono_anche_in_anteprima(tmp_path: Path) -> None:
    p = passo(tmp_path, banca_base())
    p.passo.esegui()
    cartella = tmp_path / 'training' / 'esclusioni'
    for nome in (
        'C07_principi_tolti',
        'C07_principi_per_il_team',
        'C07_giudicate_saltate',
        'C07_prosegue_da_rileggere',
    ):
        assert (cartella / f'{nome}.tsv').read_text(encoding='utf-8').splitlines()[0].startswith('codice')
    esempi = (cartella / 'C07_esempi.tsv').read_text(encoding='utf-8').splitlines()
    assert 'altra citazione NEU-0002' in esempi[1]
    assert p.detto[-1] == 'ANTEPRIMA: niente scritto in banca dati'


def test_con_la_fotografia_non_serve_la_banca(tmp_path: Path) -> None:
    foto = tmp_path / 'foto.json'
    foto.write_text(json.dumps(banca_base()), encoding='utf-8')
    assert passo(tmp_path, {}, fotografia=foto).passo.esegui().segni == 1


def test_leggi_rilette_prende_solo_le_altre_citazioni(tmp_path: Path) -> None:
    f = tmp_path / 'rilette.tsv'
    f.write_text(
        'codice\tpagina\tesito\nNEU-0001\t2\taltra_citazione\nNEU-0001\t3\tprosegue\nNEU-0003\t4\t ALTRA\n',
        encoding='utf-8',
    )
    assert ApplicaC07.leggi_rilette(f) == {('NEU-0001', 2), ('NEU-0003', 4)}


# the same as the live tools


def test_le_pagine_marcate_come_il_vivo(vivi_oggi: Any) -> None:
    vivo = vivi_oggi('controlli_automatici')
    b = banca_base()
    b['a']['proposto_estensione'][0]['prova'] = PROVA
    b['c'] = riga(
        'NEU-0003',
        'Something else',
        proposto_frase_sostenuta=FRASE_B,
        proposto_principi=['p.a'],
    )
    sp = spazi_pagine(TESTO)
    atteso = vivo.pagine_gia_citate(b['a'], list(b.values()), sp)
    nuovo = RiconoscitorePagine().pagine(b['a'], b.values(), sp)
    assert atteso and set(nuovo) == set(atteso)
    for pagina, v in atteso.items():
        n = nuovo[pagina]
        assert (list(n.codici), n.posizione, n.testo, n.seguito, n.segno) == (
            v['codici'],
            v['posizione'],
            v['testo'],
            v['seguito'],
            v['segno'],
        )


def test_le_spunte_del_team_come_il_vivo(vivi_oggi: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vivo = vivi_oggi('applica_c07')
    banca = banca_base(esito='confermata', validato_estensione=[2, 3])
    rev = tmp_path / 'rev.tsv'
    rev.write_text(
        'riga\tpagina_attorno\tteam_spunta_seguito\trevisione\taltre_righe_sulla_pagina\tmotivo\n'
        'NEU-0001\t2\tsi\tALTRA CITAZIONE\tNEU-0002\tletta a mano\n',
        encoding='utf-8',
    )
    assert vivo.spunte_team(banca, str(rev)) == ApplicaC07(
        Config(radice=tmp_path), BancaDatiMemoria(), 'x'
    ).spunte_del_team(banca, rev)
