"""C03, body text and footnote counted once: the pairs, the list read by hand, the writes, the copy before.

Synthetic rows only: nothing here needs the filings or the platform. The last test compares the package with the live
``tools/unisci_c03.py`` when ``tools/`` is there (it is not in the public repository: the test is skipped).
"""

from __future__ import annotations

import copy
import csv
import json
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from tracepipe.banca import ORA_DEL_SERVER, BancaDatiMemoria
from tracepipe.config import Config
from tracepipe.copia_prima import CopiaPrima
from tracepipe.unione_c03 import (
    CoppieRivedute,
    GeneratoreCoppie,
    UnioneC03,
    appoggio,
    chi_e_il_testo,
    lingua_dall_intestazione,
    nel_testo,
)

FRASE = 'The court held that the State must reduce its emissions by 25 percent by 2020, as the judgment says.'


def riga(codice: str, cs: int, offset: list[int] | None, frase: str = FRASE, **kw: Any) -> dict[str, Any]:
    r: dict[str, Any] = {
        'codice': codice,
        'case_id': 'caso-1',
        'document_id': 'doc1',
        'caso_citato': 'neubauer',
        'proposto_rete': 'lessicale',
        'proposto_pagina': 3,
        'char_start': cs,
        'proposto_frase_sostenuta': frase,
        'file': 'markdown/doc1.md',
    }
    if offset is not None:
        r['proposto_frase_offset'] = offset
    r.update(kw)
    return r


def banca_base() -> dict[str, dict[str, Any]]:
    """A body row, the footnote it calls, two consecutive footnotes with the same sentence, and an unrelated row."""
    return {
        'neubauer__doc1__100': riga('NEU-0001', 100, [50, 200], proposto_paragrafi=['12']),
        'neubauer__doc1__900': riga(
            'NEU-0002',
            900,
            [800, 850],
            proposto_citazione_testuale='1 BVerfG, 24 March 2021, para. 182 and paragraphs 183-185.',
            proposto_paragrafi=['13'],
        ),
        'neubauer__doc2__100': riga('NEU-0003', 100, [800, 850], document_id='doc2'),
        'neubauer__doc2__400': riga('NEU-0004', 400, [800, 850], document_id='doc2'),
        'neubauer__doc3__10': riga(
            'NEU-0005', 10, [0, 5], document_id='doc3', proposto_frase_sostenuta='Another sentence'
        ),
    }


def config(tmp_path: Path) -> Config:
    return Config(radice=tmp_path)


# the pairs


def test_il_testo_e_la_riga_il_cui_punto_cade_nella_frase() -> None:
    a, b = riga('A', 100, [50, 200]), riga('B', 900, [800, 850])
    assert nel_testo(a) and not nel_testo(b)
    assert chi_e_il_testo(a, b) == (a, b)
    assert chi_e_il_testo(b, a) == (a, b)


def test_senza_offset_vale_la_posizione_corpo_poi_la_prima() -> None:
    corpo = riga('A', 500, None, proposto_posizione='corpo')
    altra = riga('B', 100, None)
    assert chi_e_il_testo(altra, corpo) == (corpo, altra)
    x, y = riga('X', 100, None), riga('Y', 300, None)
    assert chi_e_il_testo(y, x) == (x, y)


def test_testo_e_nota_con_la_stessa_frase_sono_una_coppia() -> None:
    visti: set[str] = set()
    coppie = GeneratoreCoppie().testo_nota(banca_base(), visti)
    assert [(c.tipo, c.tenuta['codice'], c.esce['codice']) for c in coppie] == [('testo_nota', 'NEU-0001', 'NEU-0002')]
    assert visti == {'NEU-0002'}
    assert 'NEU-0001' in coppie[0].motivo and 'NEU-0002' in coppie[0].motivo


def test_due_note_con_la_stessa_frase_restano_distinte() -> None:
    """The case that MUST fail the other way: two footnotes of the same sentence are two citations (rule of S07)."""
    banca = {k: v for k, v in banca_base().items() if v['document_id'] == 'doc2'}
    assert GeneratoreCoppie().testo_nota(banca, set()) == []


def test_pagine_lontane_o_frasi_diverse_non_si_uniscono() -> None:
    banca = banca_base()
    banca['neubauer__doc1__900']['proposto_pagina'] = 6
    assert GeneratoreCoppie().testo_nota(banca, set()) == []
    banca = banca_base()
    banca['neubauer__doc1__900']['proposto_frase_sostenuta'] = (
        'A different supported sentence, long enough to compare here.'
    )
    assert GeneratoreCoppie().testo_nota(banca, set()) == []


def test_una_frase_corta_non_conta() -> None:
    banca = {
        'a': riga('NEU-0001', 100, [50, 200], frase='Too short'),
        'b': riga('NEU-0002', 900, [800, 850], frase='Too short'),
    }
    assert GeneratoreCoppie().testo_nota(banca, set()) == []


def test_una_pagina_illeggibile_fa_fallire_il_confronto_in_silenzio() -> None:
    banca = banca_base()
    banca['neubauer__doc1__900']['proposto_pagina'] = 'tre'
    assert GeneratoreCoppie().testo_nota(banca, set()) == []


def test_solo_le_righe_vive_con_un_codice_entrano() -> None:
    banca = banca_base()
    banca['neubauer__doc1__900']['proposto_rete'] = 'esclusa'
    assert GeneratoreCoppie().testo_nota(banca, set()) == []
    banca = banca_base()
    del banca['neubauer__doc1__900']['codice']
    assert GeneratoreCoppie().testo_nota(banca, set()) == []


class TraduzioneFinta:
    """A translation rule that pairs NEU-0003 with NEU-0005 and knows the original language of the filing."""

    def __init__(self, originale: str | None) -> None:
        self.originale = originale

    def prepara(self, banca: Any) -> None:
        self.preparata = True

    def codice_altra_riga(self, rid: str, riga: Any) -> str | None:
        return {'NEU-0003': 'NEU-0005', 'NEU-0005': 'NEU-0003'}.get(riga['codice'])

    def lingua_del_testo(self, file: str) -> str | None:
        return 'de' if file.endswith('doc3.md') else 'en'

    def lingua_originale(self, riga: Any) -> str | None:
        return self.originale


def test_traduzione_tiene_la_riga_nella_lingua_originale() -> None:
    banca = banca_base()
    banca['neubauer__doc3__10']['file'] = 'markdown/doc3.md'
    coppie = GeneratoreCoppie(TraduzioneFinta('de')).coppie(banca)
    tra = [c for c in coppie if c.tipo == 'traduzione']
    assert len(tra) == 1 and tra[0].tenuta['codice'] == 'NEU-0005' and tra[0].esce['codice'] == 'NEU-0003'
    assert 'lingua originale dell atto (de)' in tra[0].motivo


def test_traduzione_senza_lingua_nota_tiene_il_codice_piu_basso() -> None:
    banca = banca_base()
    banca['neubauer__doc3__10']['file'] = 'markdown/doc3.md'
    tra = [c for c in GeneratoreCoppie(TraduzioneFinta(None)).coppie(banca) if c.tipo == 'traduzione']
    assert tra[0].tenuta['codice'] == 'NEU-0003' and 'la prima' in tra[0].motivo


def test_senza_la_regola_delle_traduzioni_non_ce_ne_sono() -> None:
    assert [c for c in GeneratoreCoppie().coppie(banca_base()) if c.tipo == 'traduzione'] == []


def test_lingua_dall_intestazione() -> None:
    assert lingua_dall_intestazione("---\nlingue: 'German; English'\n---\ntesto") == 'de'
    assert lingua_dall_intestazione('---\nlingue: Klingon\n---\n') is None
    assert lingua_dall_intestazione('niente intestazione') is None


def test_appoggio_porta_codice_testo_e_paragrafi() -> None:
    n = banca_base()['neubauer__doc1__900']
    a = appoggio(banca_base()['neubauer__doc1__100'], n)
    assert a['codice'] == 'NEU-0002'
    assert a['testo'].startswith('1 BVerfG')
    assert a['paragrafi'] == ['para. 182', 'paragraphs 183-185']


# the list read by hand


def scrivi_elenco(percorso: Path, righe: list[tuple[str, str, str, str]]) -> Path:
    with open(percorso, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, delimiter='\t')
        w.writerow(['tipo', 'codice_tenuto', 'codice_che_esce', 'motivo'])
        w.writerows(righe)
    return percorso


def test_una_catena_si_chiude_sulla_riga_finale(tmp_path: Path) -> None:
    """A keeps B, B keeps C: B goes out, so C is kept by A."""
    banca = {
        'a': riga('NEU-0010', 1, None, document_id='d9'),
        'b': riga('NEU-0011', 2, None, document_id='d9'),
        'c': riga('NEU-0012', 3, None, document_id='d9'),
    }
    elenco = scrivi_elenco(
        tmp_path / 'catena.tsv',
        [('testo_nota', 'NEU-0010', 'NEU-0011', 'm1'), ('testo_nota', 'NEU-0011', 'NEU-0012', 'm2')],
    )
    coppie = CoppieRivedute(lambda t: None).coppie(banca, elenco)
    assert [(c.tenuta['codice'], c.esce['codice']) for c in coppie] == [
        ('NEU-0010', 'NEU-0011'),
        ('NEU-0010', 'NEU-0012'),
    ]


def test_coppie_rivedute_saltano_quello_che_non_si_puo_scrivere(tmp_path: Path) -> None:
    banca = banca_base()
    banca['z'] = riga('NEU-0012', 3, None, document_id='d9', esito='scartata')
    banca['w'] = riga('NEU-0013', 4, None, document_id='d9', proposto_rete='esclusa')
    elenco = scrivi_elenco(
        tmp_path / 'rivisto.tsv',
        [
            ('testo_nota', 'NEU-0001', 'NEU-0002', 'm1'),  # good
            ('testo_nota', 'NEU-0003', 'NEU-0002', 'm2'),  # NEU-0002 would go out twice
            ('testo_nota', 'NEU-0012', 'NEU-0004', 'm3'),  # the kept row is discarded by the team
            ('testo_nota', 'NEU-0001', 'NEU-0013', 'm4'),  # the row that goes out is already excluded
            ('testo_nota', 'NEU-0001', 'NEU-9999', 'm5'),  # missing row
        ],
    )
    detto: list[str] = []
    coppie = CoppieRivedute(detto.append).coppie(banca, elenco)
    assert [(c.tenuta['codice'], c.esce['codice']) for c in coppie] == [('NEU-0001', 'NEU-0002')]
    assert sorted(detto) == sorted(
        [
            "saltate (riga che esce gia' in un'altra coppia): 1",
            'saltate (riga da tenere non viva o scartata): 1',
            "saltate (riga che esce gia' esclusa): 1",
            'saltate (riga assente o catena chiusa su se stessa): 1',
        ]
    )


def test_una_riga_non_si_unisce_a_se_stessa(tmp_path: Path) -> None:
    elenco = scrivi_elenco(tmp_path / 'giro.tsv', [('testo_nota', 'NEU-0001', 'NEU-0001', 'a')])
    detto: list[str] = []
    assert CoppieRivedute(detto.append).coppie(banca_base(), elenco) == []
    assert detto == ['saltate (riga assente o catena chiusa su se stessa): 1']


# the step


class Prova(NamedTuple):
    """The step under test, its database and the lines it printed."""

    passo: UnioneC03
    db: BancaDatiMemoria
    detto: list[str]


def passo(tmp_path: Path, banca: dict[str, Any], scrivi: bool = False, **kw: Any) -> Prova:
    db = BancaDatiMemoria({'corpus_rows': banca})
    detto: list[str] = []
    u = UnioneC03(
        config(tmp_path),
        db,
        'prova',
        scrivi=scrivi,
        copia=CopiaPrima(tmp_path, cartella=tmp_path / 'copie', stampa=lambda t: None),
        stampa=detto.append,
        **kw,
    )
    return Prova(u, db, detto)


def test_anteprima_scrive_gli_elenchi_e_niente_in_banca(tmp_path: Path) -> None:
    p = passo(tmp_path, banca_base())
    esito = p.passo.esegui()
    assert len(esito.libere) == 1 and p.db.scritture == [] and esito.copia is None
    elenco = tmp_path / 'training' / 'esclusioni' / 'C03_da_scrivere.tsv'
    assert elenco.read_text(encoding='utf-8').splitlines()[1].startswith('testo_nota\tNEU-0001\tNEU-0002')
    assert (tmp_path / 'training' / 'esclusioni' / 'C03_giudicate_da_rivedere.tsv').exists()
    assert p.detto[-1] == 'ANTEPRIMA: niente scritto in banca dati'
    esclusa = esito.scritture['neubauer__doc1__900']
    assert esclusa['esclusa_il'] is ORA_DEL_SERVER


def test_le_coppie_con_una_riga_giudicata_vanno_all_elenco_da_rivedere(tmp_path: Path) -> None:
    banca = banca_base()
    banca['neubauer__doc1__900']['esito'] = 'confermata'
    u, _, _ = passo(tmp_path, banca)
    esito = u.esegui()
    assert esito.libere == [] and len(esito.giudicate) == 1 and esito.scritture == {}
    riga_giudicata = (tmp_path / 'training/esclusioni/C03_giudicate_da_rivedere.tsv').read_text().splitlines()[1]
    assert riga_giudicata.split('\t')[3:5] == ['', 'confermata']


def test_scrive_la_copia_prima_poi_le_due_righe(tmp_path: Path) -> None:
    u, db, _ = passo(tmp_path, banca_base(), scrivi=True)
    esito = u.esegui()
    assert esito.copia is not None and esito.copia.exists()
    copia = CopiaPrima.leggi(esito.copia)
    assert set(copia['righe']) == {'neubauer__doc1__100', 'neubauer__doc1__900'}
    assert copia['righe']['neubauer__doc1__900']['prima']['proposto_rete'] == 'lessicale'
    assert 'esclusa_il' in copia['righe']['neubauer__doc1__900']['assenti']
    scritte = {s['doc_id']: s for s in db.scritture}
    assert {s['op'] for s in scritte.values()} == {'update'}
    esce, tiene = scritte['neubauer__doc1__900']['dati'], scritte['neubauer__doc1__100']['dati']
    assert esce['proposto_rete'] == 'esclusa' and esce['esclusa_regola'] == 'C03' and esce['unita_a'] == 'NEU-0001'
    assert esce['esclusa_da'] == 'prova' and esce['esclusa_motivo'].startswith('C03 stessa frase')
    assert tiene['c03_da'] == 'prova' and tiene['proposto_paragrafi'] == ['12', '13']
    assert tiene['proposto_nota_appoggio'][0]['codice'] == 'NEU-0002'


def test_se_la_copia_non_si_scrive_non_si_scrive_niente(tmp_path: Path) -> None:
    from tracepipe.copia_prima import CopiaNonRiuscitaError

    u, db, _ = passo(tmp_path, banca_base(), scrivi=True)
    (tmp_path / 'copie').write_text('un file al posto della cartella', encoding='utf-8')
    with pytest.raises(CopiaNonRiuscitaError):
        u.esegui()
    assert db.scritture == []


def test_con_la_fotografia_non_serve_la_banca(tmp_path: Path) -> None:
    foto = tmp_path / 'foto.json'
    foto.write_text(json.dumps(banca_base()), encoding='utf-8')
    u, _, _ = passo(tmp_path, {}, fotografia=foto)
    assert len(u.esegui().libere) == 1


def test_con_rivisto_si_scrive_solo_l_elenco_riletto(tmp_path: Path) -> None:
    banca = banca_base()
    banca['neubauer__doc1__900']['esito'] = 'confermata'  # judged: the automatic rule would not touch it
    elenco = scrivi_elenco(tmp_path / 'r.tsv', [('testo_nota', 'NEU-0001', 'NEU-0002', 'riletta a mano')])
    u, db, _ = passo(tmp_path, banca, scrivi=True, rivisto=elenco)
    esito = u.esegui()
    assert [c.esce['codice'] for c in esito.libere] == ['NEU-0002']
    assert esito.giudicate == []
    assert (tmp_path / 'training/esclusioni/C03_da_scrivere_RIVISTO_controllato.tsv').exists()
    assert db.scritture[0]['dati']['esclusa_motivo'] == 'C03 riletta a mano'


def test_le_traduzioni_rivedute_vanno_nel_campo_delle_unite(tmp_path: Path) -> None:
    banca = banca_base()
    elenco = scrivi_elenco(tmp_path / 'r.tsv', [('traduzione', 'NEU-0001', 'NEU-0005', 'tradotto')])
    u, _, _ = passo(tmp_path, banca, rivisto=elenco)
    esito = u.esegui()
    assert esito.scritture['neubauer__doc1__100']['proposto_traduzioni_unite'] == ['NEU-0005']
    assert 'proposto_nota_appoggio' not in esito.scritture['neubauer__doc1__100']


def test_la_banca_letta_non_cambia(tmp_path: Path) -> None:
    banca = banca_base()
    prima = copy.deepcopy(banca)
    passo(tmp_path, banca)[0].esegui()
    assert banca == prima


# the same as the live tool


def test_le_coppie_testo_nota_come_il_vivo(vivi_oggi: Any) -> None:
    vivo = vivi_oggi('unisci_c03')
    banca = banca_base()
    atteso = [(t['codice'], n['codice'], mot) for tipo, t, n, mot in vivo.coppie(banca) if tipo == 'testo_nota']
    nuovo = [(c.tenuta['codice'], c.esce['codice'], c.motivo) for c in GeneratoreCoppie().testo_nota(banca, set())]
    assert nuovo == atteso and nuovo
    assert vivo.appoggio(banca['neubauer__doc1__100'], banca['neubauer__doc1__900']) == appoggio(
        banca['neubauer__doc1__100'], banca['neubauer__doc1__900']
    )
