"""S08, the close pairs: links, clues, the L13 question, the brakes, the decision, the loader of the new rows.

Every proof has the case that MUST fail if the step is missing or wrong. Synthetic filings and rows only: nothing here
needs the platform or the filings of the corpus. The tests that compare the package with the live tools of ``tools/``
are skipped when ``tools/`` is not there (it is not in the public repository).
"""

from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path
from typing import Any

import pytest

from tracepipe.banca import BancaDatiMemoria
from tracepipe.carica_s08 import CaricaS08, Caricatore, Copie, verifiche
from tracepipe.config import Config
from tracepipe.coppia import ArchivioAtti, Coppia, lunghezza_riferimento, verdetto_indizi
from tracepipe.coppie_vicine import (
    SOGLIA_S08,
    CoppieVicine,
    Taratura,
    classifica_recuperate,
    distanza_da_righe,
)
from tracepipe.decisione_coppie import DecisioneCoppie, Decisore, ScrittureS08, VerdettoLettore
from tracepipe.lettura_coppia import (
    ESITI,
    DomandaL13,
    FreniL13,
    LettoreCoppie,
    PreparazioneL13,
    conta_token,
    esito_json,
    leggi_jsonl,
    prova_freni,
    raccogli,
    secco,
)
from tracepipe.prova_intera import FreniProvaIntera

PAROLE = 'the applicants argue that this court should follow the reasoning of the decision about climate duties '
RIEMPITIVO = PAROLE * 6
FRASE_A = (
    'The applicants rely on the reasoning of the Dutch court in Urgenda, which held that the State must cut emissions.'
)
FRASE_B = '15 Urgenda Foundation v State of the Netherlands, Hoge Raad, 20 December 2019.'
ATTO = (
    '---\ndocument_id: doc1\ncase_name: X v Y\ntipo_atto: ricorso\nlingue: English\n---\n'
    '<!-- page 1 -->\n' + RIEMPITIVO + '\n' + FRASE_A + '15\n'
    ' \n' + RIEMPITIVO + '\n \n'
    '15 Urgenda Foundation v State of the Netherlands, Hoge Raad, 20 December 2019.\n'
    '16 See also the commentary by Smith on the Dutch judgment, 2020.\n'
)


def riga(testo: str, cod: str, nth: int = 0, file: str = 'markdown/doc1.md', **kw: Any) -> dict[str, Any]:
    cs = -1
    for _ in range(nth + 1):
        cs = testo.index('Urgenda', cs + 1)
    r: dict[str, Any] = {
        'file': file,
        'char_start': cs,
        'document_id': 'doc1',
        'case_id': 'caso-1',
        'caso_citato': 'urgenda',
        'codice': cod,
        'proposto_forma_trovata': 'Urgenda',
        'proposto_rete': 'lessicale',
        'proposto_pagina': 1,
    }
    r.update(kw)
    return r


@pytest.fixture()
def radice(tmp_path: Path) -> Path:
    (tmp_path / 'markdown').mkdir()
    (tmp_path / 'markdown' / 'doc1.md').write_text(ATTO, encoding='utf-8')
    (tmp_path / 'cited-cases').mkdir()
    (tmp_path / 'cited-cases' / 'urgenda.yaml').write_text(
        "nome: Urgenda Foundation v State of the Netherlands\ndata_decisione: 2019-12-20\nforme: ['Urgenda']\n",
        encoding='utf-8',
    )
    return tmp_path


@pytest.fixture()
def atti(radice: Path) -> ArchivioAtti:
    return ArchivioAtti(radice)


def coppia_testo_nota(atti: ArchivioAtti) -> Coppia:
    a = riga(ATTO, 'U-1', 0)
    b = riga(ATTO, 'U-2', 1)
    return Coppia(a, b, atti, 'U-1__U-2')


# the links: two distant citations on one page are two rows


def test_due_righe_lontane_sulla_stessa_pagina_sono_una_coppia() -> None:
    """The loss of S07 was the same-page deduplication: with S08 the two rows become a pair to read, never one row."""
    a, b = riga(ATTO, 'U-1', 0), riga(ATTO, 'U-2', 1)
    el = CoppieVicine().elenco({'1': a, '2': b})
    assert len(el) == 1 and el[0]['stessa_pagina'] and el[0]['distanza'] > 100
    assert el[0]['id'] == 'U-1a-U-1b' and el[0]['a']['codice'] == 'U-1' and not el[0]['a']['nuova']


def test_deve_fallire_con_la_soglia_troppo_bassa() -> None:
    """The case that MUST fail: with a threshold of 50 characters the pair is not there (the loss of before)."""
    a, b = riga(ATTO, 'U-1', 0), riga(ATTO, 'U-2', 1)
    assert CoppieVicine(50).elenco({'1': a, '2': b}) == []


def test_la_soglia_scelta_e_5000() -> None:
    assert SOGLIA_S08 == 5000 and CoppieVicine().soglia == 5000


def test_tre_righe_vicine_sono_una_catena_e_due_legami() -> None:
    righe = {
        str(i): {
            'document_id': 'd',
            'caso_citato': 'urgenda',
            'proposto_rete': 'lessicale',
            'char_start': cs,
            'codice': f'U-{i}',
        }
        for i, cs in enumerate((100, 250, 400, 90000))
    }
    cv = CoppieVicine(1000)
    legami = cv.legami(cv.righe_per_atto(righe))
    assert [lg.distanza for lg in legami] == [150, 150]
    catene = cv.catene(legami)
    assert len(catene) == 1 and len(catene[0].righe) == 3
    base, prov = catene[0].codici_provvisori()
    assert (base, prov) == ('U-0', ['U-0a', 'U-0b', 'U-0c'])


def test_una_riga_senza_codice_prende_un_codice_provvisorio_nuovo() -> None:
    banca = {
        '1': {
            'document_id': 'd',
            'caso_citato': 'urgenda',
            'proposto_rete': 'lessicale',
            'char_start': 100,
            'codice': 'U-1',
        }
    }
    nuove = [{'document_id': 'd', 'caso_citato': 'urgenda', 'char_start': 500, 'chiave': 'S08-x', 'pagina': 2}]
    el = CoppieVicine().elenco(banca, nuove)
    assert el[0]['a']['codice'] == 'U-1' and el[0]['b']['nuova'] and el[0]['b']['codice'] is None
    solo_nuove = CoppieVicine().elenco(
        {}, [{**nuove[0], 'chiave': 'k1'}, {**nuove[0], 'char_start': 700, 'chiave': 'k2'}]
    )
    assert solo_nuove[0]['base'] == 'NUOVA-00001' and solo_nuove[0]['id'] == 'NUOVA-00001a-NUOVA-00001b'


def test_righe_non_vive_o_senza_posizione_non_fanno_coppie() -> None:
    base = {'document_id': 'd', 'caso_citato': 'urgenda'}
    banca = {
        'a': {**base, 'proposto_rete': 'lessicale', 'char_start': 10, 'codice': 'U-1'},
        'b': {**base, 'proposto_rete': 'esclusa', 'char_start': 20, 'codice': 'U-2'},
        'c': {**base, 'proposto_rete': 'lessicale', 'char_start': None, 'codice': 'U-3'},
        'd': {**base, 'proposto_rete': 'descrittiva', 'char_start': '30', 'codice': 'U-4'},
    }
    el = CoppieVicine().elenco(banca)
    assert [(c['a']['codice'], c['b']['codice']) for c in el] == [('U-1', 'U-4')]


def test_prova_due_lontane_dice_quelle_che_mancano() -> None:
    a, b = riga(ATTO, 'U-1', 0), riga(ATTO, 'U-2', 1)
    banca = {'1': a, '2': b}
    attese = [('urgenda', 'doc1', a['char_start'], b['char_start'])]
    assert CoppieVicine().prova_due_lontane(attese, banca) == []
    assert CoppieVicine().prova_due_lontane(attese, {'1': a}) == attese


def test_conta_soglie() -> None:
    a, b = riga(ATTO, 'U-1', 0), riga(ATTO, 'U-2', 1)
    c03 = frozenset({frozenset(('U-1', 'U-2'))})
    n = CoppieVicine().conta_soglie({'1': a, '2': b}, c03=c03, soglie=(50, 5000))
    assert n[50]['totale'] == {}
    t = n[5000]['totale']
    assert t['legami'] == 1 and t['stessa_pagina'] == 1 and t['gia_c03'] == 1 and t['catene'] == 1 and t['righe'] == 2


def test_righe_nuove_vicine_e_classificazione() -> None:
    banca = {
        '1': {
            'document_id': 'd',
            'caso_citato': 'urgenda',
            'proposto_rete': 'lessicale',
            'char_start': 1000,
            'codice': 'U-1',
        }
    }
    per = CoppieVicine.righe_per_atto(banca)
    vicina = {'document_id': 'd', 'caso_citato': 'urgenda', 'char_start': 1100}
    lontana = {'document_id': 'd', 'caso_citato': 'urgenda', 'char_start': 60000}
    assert distanza_da_righe(vicina, per) == 100 and distanza_da_righe(lontana, per) == 59000
    assert distanza_da_righe({'document_id': 'altro', 'caso_citato': 'urgenda', 'char_start': 1}, per) is None
    r = CoppieVicine().righe_nuove_vicine([vicina, lontana], banca, soglie=(200, 5000))
    assert r == {
        200: {'vicine_a_una_riga_viva': 1, 'sole_o_lontane': 1},
        5000: {'vicine_a_una_riga_viva': 1, 'sole_o_lontane': 1},
    }
    cl = classifica_recuperate([{**vicina, 'document_id': 'd', 'pagina': 1}, {**lontana, 'dist_nome': 5000}], banca)
    assert [x['esito'] for x in cl] == ['assorbita', 'nuova']
    assert cl[0]['chiave'] == 'S08-urgenda-d-1100'


# the threshold is chosen with the numbers


def test_scelta_della_soglia_dal_costo() -> None:
    tab = [
        {'soglia': 2000, 'legami_per_unire_in_piu': None},
        {'soglia': 3000, 'legami_per_unire_in_piu': 8.4},
        {'soglia': 5000, 'legami_per_unire_in_piu': 22.7},
        {'soglia': 8000, 'legami_per_unire_in_piu': 236.5},
    ]
    assert Taratura({}, _verita_vuota()).scegli(tab) == 5000
    assert (
        Taratura({}, _verita_vuota()).scegli(tab[:3]) == 5000
    )  # the last threshold when the cost never passes the limit


def _verita_vuota(tmp: Path | None = None) -> Path:
    import tempfile

    p = Path(tempfile.mkdtemp()) / 'verita.tsv'
    p.write_text(
        'id\tdecisione\tcodice_tenuto_dalla_regola\tcodice_che_esce_per_la_regola\triga_da_tenere\n', encoding='utf-8'
    )
    return p


def test_taratura_sulle_coppie_riviste(tmp_path: Path) -> None:
    righe = {
        'a1': riga(ATTO, 'U-1', 0),
        'a2': riga(ATTO, 'U-2', 1),
        'b1': riga(ATTO, 'U-3', 0, document_id='doc2'),
        'b2': {**riga(ATTO, 'U-4', 1, document_id='doc2'), 'char_start': 90000},
    }
    verita = tmp_path / 'verita.tsv'
    with open(verita, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, delimiter='\t')
        w.writerow(['id', 'decisione', 'codice_tenuto_dalla_regola', 'codice_che_esce_per_la_regola', 'riga_da_tenere'])
        w.writerows(
            [
                ('P1', 'UNIRE', 'U-1', 'U-2', 'U-1'),
                ('P2', 'TENERE TUTTE E DUE', 'U-3', 'U-4', ''),
                ('P3', 'INCERTA', 'U-1', 'U-2', ''),
            ]
        )
    t = Taratura(righe, verita)
    assert [(d, a['codice'], b['codice']) for d, a, b, _ in t.coppie_stesso_atto()] == [
        ('UNIRE', 'U-1', 'U-2'),
        ('TENERE', 'U-3', 'U-4'),
    ]
    ris = t.misura(soglie=(50, 5000, 12000))
    assert ris['coppie'] == {'UNIRE': 1, 'TENERE': 1}
    unire = {x['soglia']: x['UNIRE']['stessa_catena'] for x in ris['tabella']}
    tenere = {x['soglia']: x['TENERE']['stessa_catena'] for x in ris['tabella']}
    assert unire == {50: 0, 5000: 1, 12000: 1} and tenere == {50: 0, 5000: 0, 12000: 0}
    assert ris['distanze']['UNIRE']['max'] == abs(righe['a1']['char_start'] - righe['a2']['char_start'])
    assert Taratura.percentili([1, 2, 3, 4, 5])['p50'] == 3


# the candidate pair and its clues


def test_la_finestra_ha_i_segni_ma_il_testo_puro_no(atti: ArchivioAtti) -> None:
    con, puro = coppia_testo_nota(atti).finestra()
    assert '⟦A⟧' in con and '⟦B⟧' in con and '⟦' not in puro and '[pagina 1]' in puro


def test_la_coppia_mette_prima_il_riferimento_che_viene_prima(atti: ArchivioAtti) -> None:
    a, b = riga(ATTO, 'U-1', 0), riga(ATTO, 'U-2', 1)
    c = Coppia(b, a, atti)
    assert c.a['codice'] == 'U-1' and c.id == 'U-1-U-2' and c.caso == 'urgenda'


def test_gli_indizi_della_coppia_testo_nota(atti: ArchivioAtti) -> None:
    i = coppia_testo_nota(atti).indizi()
    assert i['posizione_a'] == 'testo' and i['posizione_b'] == 'nota' and i['nota_contro_testo']
    assert i['nota_chiamata_dal_testo'] is True and i['stessa_pagina'] and not i['stessa_nota']
    assert verdetto_indizi(i) == ('una', "la nota e' chiamata dalla frase del testo", True)


def test_una_nota_che_nessuna_frase_chiama_non_e_un_indizio_forte(radice: Path, atti: ArchivioAtti) -> None:
    testo = ATTO.replace('emissions.15', 'emissions.')
    (radice / 'markdown' / 'doc2.md').write_text(testo, encoding='utf-8')
    c = Coppia(riga(testo, 'U-1', 0, file='markdown/doc2.md'), riga(testo, 'U-2', 1, file='markdown/doc2.md'), atti)
    i = c.indizi()
    assert i['nota_chiamata_dal_testo'] is False
    assert Decisore(solo_indizi=True).decidi(c).esito == 'team'


def test_due_righe_nella_stessa_nota_sono_una(atti: ArchivioAtti) -> None:
    c = Coppia(
        {**riga(ATTO, 'U-1', 1), 'char_start': ATTO.index('Urgenda Foundation')},
        {**riga(ATTO, 'U-2', 1), 'char_start': ATTO.index('Hoge Raad')},
        atti,
    )
    i = c.indizi()
    assert i['stessa_nota'] and verdetto_indizi(i) == ('una', 'stessa nota', True)


def test_due_note_diverse_sono_due_ma_l_indizio_e_debole(atti: ArchivioAtti) -> None:
    c = Coppia(
        {**riga(ATTO, 'U-1', 1), 'char_start': ATTO.index('Urgenda Foundation')},
        {**riga(ATTO, 'U-2', 1), 'char_start': ATTO.index('commentary')},
        atti,
    )
    i = c.indizi()
    assert i['due_note_diverse'] and verdetto_indizi(i) == ('due', 'due note diverse', False)


def test_nessun_indizio_se_non_c_e_niente_da_dire() -> None:
    base = {
        'stessa_nota': False,
        'nota_contro_testo': False,
        'nota_chiamata_dal_testo': None,
        'due_note_diverse': False,
        'paragrafi_diversi': False,
    }
    assert verdetto_indizi(base) == (None, '', False)
    assert verdetto_indizi({**base, 'paragrafi_diversi': True, 'nota_chiamata_dal_testo': False})[0] == 'due'


def test_la_lunghezza_del_riferimento() -> None:
    assert lunghezza_riferimento({'proposto_forma_trovata': 'Urgenda'}) == 7
    assert lunghezza_riferimento({'proposto_forma_trovata': 'descrizione: R'}) == 40
    assert lunghezza_riferimento({}) == 40


# the question L13


def test_gli_indizi_non_stanno_nella_domanda(radice: Path, atti: ArchivioAtti) -> None:
    t = DomandaL13(Config(radice=radice)).testo(coppia_testo_nota(atti))
    for parola in ('stessa_nota', 'nota_chiamata_dal_testo', 'indizio', 'stessa_frase'):
        assert parola not in t.replace('nota_chiamata": "numero', '')
    assert 'Urgenda Foundation v State of the Netherlands' in t and '2019-12-20' in t
    assert '⟦A⟧' in t and 'lingua English' in t


def test_il_reranker_ha_le_sue_istruzioni_in_testa(radice: Path, atti: ArchivioAtti) -> None:
    d = DomandaL13(Config(radice=radice))
    c = coppia_testo_nota(atti)
    assert d.testo(c, rr=True).startswith('Sei il RERANKER') and d.testo(c, rr=True).endswith(d.testo(c))


def test_la_descrizione_di_un_riferimento() -> None:
    assert DomandaL13.descrivi({'proposto_forma_trovata': 'Urgenda', 'proposto_pagina': 4}) == '«Urgenda», pagina 4'
    assert DomandaL13.descrivi({'proposto_forma_trovata': 'descrizione: R'}) == (
        'riferimento per descrizione (senza il nome), pagina non nota'
    )


# the brakes


def test_la_prova_dei_freni_passa() -> None:
    assert prova_freni() == []


def test_frase_inventata_o_copiata_dal_prompt_scarta_la_lettura(atti: ArchivioAtti) -> None:
    _, puro = coppia_testo_nota(atti).finestra()
    fr = FreniL13(puro, DomandaL13.testi_prompt())
    buona = {'esito': 'una', 'riga_principale': 'A', 'frase_A': FRASE_A, 'frase_B': FRASE_B}
    assert fr.verifica(buona) == (True, '', {'frase_A': 'trovata', 'frase_B': 'trovata'})
    inventata = {**buona, 'frase_A': FRASE_A + ' and ordered the State to pay damages to everybody'}
    assert fr.verifica(inventata)[:2] == (False, "frase non trovata nell'atto")
    copiata = {**buona, 'frase_B': "sono lo stesso punto del discorso dell'atto, citato due volte"}
    assert fr.verifica(copiata)[:2] == (False, 'frase copiata dal prompt')
    assert fr.verifica({**buona, 'esito': 'forse'})[:2] == (False, 'risposta senza esito valido')
    assert fr.verifica({**buona, 'riga_principale': ''})[:2] == (False, 'una citazione senza riga principale')
    assert fr.verifica('non un oggetto')[0] is False


def test_una_risposta_incerta_puo_non_avere_frasi_ma_non_frasi_false(atti: ArchivioAtti) -> None:
    _, puro = coppia_testo_nota(atti).finestra()
    fr = FreniL13(puro, DomandaL13.testi_prompt())
    assert fr.verifica({'esito': 'incerta'})[0] is True
    assert (
        fr.verifica({'esito': 'incerta', 'frase_A': 'una frase che nell atto non compare in nessun punto, inventata'})[
            0
        ]
        is False
    )


def test_i_segni_nella_frase_non_contano(atti: ArchivioAtti) -> None:
    _, puro = coppia_testo_nota(atti).finestra()
    fr = FreniL13(puro, DomandaL13.testi_prompt())
    assert fr.frase('⟦A⟧' + FRASE_A) == 'trovata' and fr.frase('') == 'assente'


def test_esito_json_toglie_il_ragionamento_e_i_recinti() -> None:
    assert esito_json('pensiero </think>```json\n{"esito": "una"}\n```') == {'esito': 'una'}
    assert esito_json('testo senza oggetti') == {}
    assert esito_json('{rotto {"esito": "due"}') == {'esito': 'due'}
    assert set(ESITI) == {'una', 'due', 'incerta'}


def test_raccogli_conta_solo_le_letture_valide(atti: ArchivioAtti, tmp_path: Path) -> None:
    _, puro = coppia_testo_nota(atti).finestra()
    ok = {'esito': 'una', 'riga_principale': 'A', 'frase_A': FRASE_A, 'frase_B': FRASE_B}
    cattiva = {**ok, 'frase_B': 'a sentence that does not appear anywhere in the filing at all, invented'}
    f = tmp_path / 'esiti.jsonl'
    f.write_text(
        '\n'.join(json.dumps({'id': 'p', 'lettura': k, 'testo': json.dumps(j)}) for k, j in enumerate((ok, cattiva))),
        encoding='utf-8',
    )
    r = raccogli([{'id': 'p', 'puro': puro, 'letture': 2}], f)['p']
    assert r['voti'] == {'una': 1} and r['scartate'] == {"frase non trovata nell'atto": 1} and r['fatte'] == 2


def test_freni_r14_e_r16_come_il_vivo(vivi_oggi: Any) -> None:
    vivo = vivi_oggi('freni')
    nuovo = FreniProvaIntera()
    pagina = (
        "Il testo [[INIZIO DEL BRANO SEGNALATO]]della Corte afferma che la protezione del clima e' un dovere "
        'dello Stato. '
        'La Schutzbedür-\nftigkeit dei ricorrenti, '
        + 'altre parole di riempimento della pagina. ' * 8
        + '3 Nota a pie di pagina.'
    )
    casi = [
        'della Corte afferma che la protezione del clima e un dovere dello Stato',
        'della Corte afferma che la protezione del clima e un dovere dello Stato e ordina dieci milioni di danni',
        'La Schutzbedürftigkeit dei ricorrenti, altre parole di riempimento',
        'della Corte afferma ... un dovere dello Stato',
        'una frase che non compare da nessuna parte nella pagina data qui',
        'corta',
        '',
    ]
    for prova in casi:
        for kw in ({}, {'ricostruisci': True}, {'intera': True}, {'ricostruisci': True, 'intera': True}):
            assert nuovo.verifica(prova, pagina, ['testo del prompt'], **kw) == vivo.verifica(
                prova, pagina, ['testo del prompt'], **kw
            ), (prova, kw)
    assert nuovo.verifica(casi[1], pagina, intera=True) == 'non trovata'
    assert nuovo.verifica(casi[0], pagina, intera=True) == 'trovata'


def test_le_indicazioni_della_coppia_come_il_vivo(vivi_oggi: Any, radice: Path, atti: ArchivioAtti) -> None:
    vivo = vivi_oggi('coppia_s08')
    a, b = riga(ATTO, 'U-1', 0), riga(ATTO, 'U-2', 1)
    a['file'] = b['file'] = str(radice / 'markdown' / 'doc1.md')  # an absolute path: the live tool joins it to its root
    cv, cn = vivo.Coppia(a, b, 'x'), Coppia(a, b, atti, 'x')
    assert cv.indizi() == cn.indizi()
    assert cv.finestra() == cn.finestra()
    assert vivo.verdetto_indizi(cv.indizi()) == verdetto_indizi(cn.indizi())


# the preparation and the reader


def test_la_preparazione_scrive_le_richieste_leggibili(radice: Path, tmp_path: Path) -> None:
    a, b = riga(ATTO, 'U-1', 0), riga(ATTO, 'U-2', 1)
    banca = {'1': a, '2': b}
    prep = PreparazioneL13(Config(radice=radice), banca)
    uscita = tmp_path / 'richieste.jsonl.gz'
    conti = prep.prepara([{'id': 'U-1__U-2', 'a': a, 'b': b}], uscita)
    assert conti == {'richieste': 1}
    r = leggi_jsonl(uscita)[0]
    assert r['letture'] == 5 and r['tetto'] == 24000 and r['codici'] == ['U-1', 'U-2'] and '⟦' not in r['puro']
    assert r['leggibile'] and r['lettore'] == 'ds'
    rr = PreparazioneL13(Config(radice=radice), banca, 'rr').richiesta('U-1__U-2', a, b)
    assert rr['letture'] == 3 and rr['tetto'] == 12000 and rr['testo'].startswith('Sei il RERANKER')


def test_un_testo_rotto_non_arriva_al_modello(radice: Path, tmp_path: Path) -> None:
    rotto = ATTO.replace(RIEMPITIVO, '\u00d0\u00a7\u00d1\u201a\u00d0\u00be ' * 80)
    (radice / 'markdown' / 'doc9.md').write_text(rotto, encoding='utf-8')
    a, b = riga(rotto, 'U-1', 0, file='markdown/doc9.md'), riga(rotto, 'U-2', 1, file='markdown/doc9.md')
    uscita = tmp_path / 'r.jsonl.gz'
    conti = PreparazioneL13(Config(radice=radice), {}).prepara([{'id': 'x', 'a': a, 'b': b}], uscita)
    assert conti == {'illeggibile': 1} and leggi_jsonl(uscita) == []
    assert json.loads(Path(str(uscita) + '.illeggibili.json').read_text(encoding='utf-8'))[0]['id'] == 'x'


def test_l_insieme_mette_prima_la_verita_poi_i_legami(radice: Path, tmp_path: Path) -> None:
    a, b = riga(ATTO, 'U-1', 0), riga(ATTO, 'U-2', 1)
    verita = tmp_path / 'verita.tsv'
    verita.write_text(
        'id\tdecisione\tcodice_tenuto_dalla_regola\tcodice_che_esce_per_la_regola\triga_da_tenere\nP1\tUNIRE\tU-1\tU-2\tU-1\n',
        encoding='utf-8',
    )
    c = {**riga(ATTO, 'U-5', 1), 'char_start': a['char_start'] + 2000, 'document_id': 'doc1'}
    prep = PreparazioneL13(Config(radice=radice), {'1': a, '2': b, '3': c})
    insieme = prep.insieme(verita)
    assert (insieme[0]['origine'], insieme[0]['priorita']) == ('verita_c03', 0)
    assert {x['id'] for x in insieme if x['origine'] == 'legame_s08'} == {'U-2__U-5'}


def test_il_secco_non_chiama_nessun_modello() -> None:
    rich = [{'id': 'p', 'testo': 'domanda ' * 100}, {'id': 'q', 'testo': 'x' * 300000}]
    righe: list[str] = []
    ris = secco(rich, None, 1, righe.append)
    assert ris['richieste'] == 2 and ris['non_entrano_nel_contesto'] == 1 and ris['metodo_token'].startswith('stima')
    assert 'domanda' in righe[1] and conta_token('a' * 30) == 74


class ClienteFinto:
    """An OpenAI-like client that answers ``{"esito": "una"}`` and counts the calls."""

    def __init__(self) -> None:
        self.chiamate = 0
        self.chat = self
        self.completions = self

    def create(self, **kw: Any) -> Any:
        from types import SimpleNamespace

        self.chiamate += 1
        m = SimpleNamespace(content='{"esito": "una"}', reasoning_content='ragiono')
        return SimpleNamespace(
            choices=[SimpleNamespace(message=m, finish_reason='stop')],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        )


def test_il_lettore_scrive_una_riga_per_lettura_e_riprende(tmp_path: Path) -> None:
    rq = tmp_path / 'r.jsonl.gz'
    with gzip.open(rq, 'wt', encoding='utf-8') as h:
        h.write(json.dumps({'id': 'p1', 'chiave': 'p1', 'testo': 'domanda', 'letture': 3, 'tetto': 8000}) + '\n')
    cliente = ClienteFinto()
    righe: list[str] = []
    lettore = LettoreCoppie(cliente, 'm', paralleli=2, stampa=righe.append)
    uscita = tmp_path / 'u.jsonl'
    assert lettore.leggi(rq, uscita) is True
    assert len(leggi_jsonl(uscita)) == 3 and cliente.chiamate == 3 and righe[-1].endswith('FINITO (finished)')
    assert {x['codice'] for x in leggi_jsonl(uscita)} == {'L13'}
    assert lettore.leggi(rq, uscita) is True and cliente.chiamate == 3  # a second run does nothing


def test_il_lettore_si_ferma_dopo_i_minuti(tmp_path: Path) -> None:
    rq = tmp_path / 'r.jsonl.gz'
    with gzip.open(rq, 'wt', encoding='utf-8') as h:
        h.write(json.dumps({'id': 'p1', 'chiave': 'p1', 'testo': 'domanda', 'letture': 3, 'tetto': 8000}) + '\n')
    tempo = iter(range(0, 10_000, 1000))
    lettore = LettoreCoppie(
        ClienteFinto(), 'm', paralleli=1, minuti=1, stampa=lambda t: None, orologio=lambda: next(tempo)
    )
    assert lettore.leggi(rq, tmp_path / 'u.jsonl') is False


def test_una_domanda_troppo_lunga_non_chiama_il_modello(tmp_path: Path) -> None:
    rq = tmp_path / 'r.jsonl.gz'
    with gzip.open(rq, 'wt', encoding='utf-8') as h:
        h.write(json.dumps({'id': 'p1', 'chiave': 'p1', 'testo': 'x' * 400_000, 'letture': 1, 'tetto': 8000}) + '\n')
    cliente = ClienteFinto()
    LettoreCoppie(cliente, 'm', stampa=lambda t: None).leggi(rq, tmp_path / 'u.jsonl')
    assert cliente.chiamate == 0
    assert 'domanda troppo lunga' in leggi_jsonl(tmp_path / 'u.jsonl')[0]['errore']


# the decision


def raccolta(voti: dict[str, int], principale: str = 'A') -> dict[str, Any]:
    esito = max(voti, key=lambda k: voti[k])
    return {
        'voti': voti,
        'valide': sum(voti.values()),
        'letture': [{'valida': True, 'json': {'esito': esito, 'riga_principale': principale}}] * sum(voti.values()),
    }


def test_il_verdetto_di_un_lettore() -> None:
    v = VerdettoLettore('ds', 3)
    assert v.verdetto(raccolta({'una': 5})) == ('una', {'una': 5})
    assert v.verdetto(raccolta({'una': 2, 'due': 2, 'incerta': 1}))[0] == 'incerta'  # a tie
    assert v.verdetto(raccolta({'una': 2, 'incerta': 1}))[0] == 'incerta'  # below the minimum
    assert v.verdetto({'voti': {}, 'valide': 0, 'letture': []}) == (None, {})
    assert v.verdetto(None) == (None, {})
    assert VerdettoLettore.principale(raccolta({'una': 3}, 'B')) == 'B' and VerdettoLettore.principale(None) == ''


def test_lettori_concordi_e_nessun_indizio_contrario_unisce(atti: ArchivioAtti) -> None:
    d = Decisore().decidi(coppia_testo_nota(atti), raccolta({'una': 5}), raccolta({'una': 3}))
    assert d.esito == 'una' and d.tenuta['codice'] == 'U-1' and d.esce['codice'] == 'U-2'
    assert d.riga()['tiene'] == 'U-1' and d.riga()['esce'] == 'U-2' and d.riga()['ds'] == 'una'


def test_disaccordo_va_al_team(atti: ArchivioAtti) -> None:
    d = Decisore().decidi(coppia_testo_nota(atti), raccolta({'una': 5}), raccolta({'due': 3}))
    assert d.esito == 'team' and 'disaccordo' in d.motivo


def test_un_indizio_forte_contrario_va_al_team(atti: ArchivioAtti) -> None:
    """The readers say two but the note is called by the sentence of the body text (a strong clue: one)."""
    d = Decisore().decidi(coppia_testo_nota(atti), raccolta({'due': 5}), raccolta({'due': 3}))
    assert d.esito == 'team' and 'indizio forte' in d.motivo


def test_una_lettura_scartata_dai_freni_o_incerta_va_al_team(atti: ArchivioAtti) -> None:
    c = coppia_testo_nota(atti)
    assert Decisore().decidi(c, {'voti': {}, 'valide': 0, 'letture': []}, raccolta({'una': 3})).esito == 'team'
    assert Decisore().decidi(c, raccolta({'una': 2, 'due': 2, 'incerta': 1}), raccolta({'una': 3})).esito == 'team'


def test_due_lettori_che_dicono_due_senza_indizi_forti_contano_due(radice: Path, atti: ArchivioAtti) -> None:
    testo = ATTO.replace('emissions.15', 'emissions.')
    (radice / 'markdown' / 'doc3.md').write_text(testo, encoding='utf-8')
    c = Coppia(
        riga(testo, 'U-1', 0, file='markdown/doc3.md'), riga(testo, 'U-2', 1, file='markdown/doc3.md'), atti, 'x'
    )
    d = Decisore().decidi(c, raccolta({'due': 4, 'una': 1}), raccolta({'due': 3}))
    assert d.esito == 'due' and d.tenuta is None


def test_la_riga_che_resta(atti: ArchivioAtti) -> None:
    dec = Decisore()
    c = coppia_testo_nota(atti)
    assert dec.riga_tenuta(c)[0]['codice'] == 'U-1'  # the body text
    c.a['esito'] = 'scartata'
    assert dec.riga_tenuta(c)[0]['codice'] == 'U-2'  # the team discarded the other
    c.a['esito'] = 'confermata'
    assert dec.riga_tenuta(c)[0]['codice'] == 'U-1'
    c2 = coppia_testo_nota(atti)
    c2.b['esito'] = 'confermata'
    assert dec.riga_tenuta(c2)[0]['codice'] == 'U-2'  # confirmed beats body text
    # both in the body text: the main row named by the readers, then the first
    a = {**riga(ATTO, 'U-1', 0), 'char_start': ATTO.index('The applicants')}
    b = {**riga(ATTO, 'U-2', 0), 'char_start': ATTO.index('which held')}
    c3 = Coppia(a, b, atti)
    assert dec.riga_tenuta(c3, 'B')[0]['codice'] == 'U-2' and dec.riga_tenuta(c3)[0]['codice'] == 'U-1'


def test_senza_lettori_decide_solo_l_indizio_forte(atti: ArchivioAtti) -> None:
    d = Decisore(solo_indizi=True).decidi(coppia_testo_nota(atti))
    assert d.esito == 'una' and d.motivo.startswith('solo indizi')


# the prepared writes, never executed


def test_le_scritture_preparate_chiudono_le_catene_e_rinviano_le_righe_nuove(atti: ArchivioAtti) -> None:
    banca = {
        'r1': {**riga(ATTO, 'U-1', 0), 'proposto_paragrafi': ['1']},
        'r2': {**riga(ATTO, 'U-2', 1), 'proposto_citazione_testuale': 'See para. 12', 'proposto_paragrafi': ['2']},
        'r3': {**riga(ATTO, 'U-3', 1), 'char_start': 1},
    }
    c12 = coppia_testo_nota(atti)
    d1 = Decisore(solo_indizi=True).decidi(c12)
    d2 = type(d1)('x', 'una', 'm', banca['r2'], banca['r3'])  # r2 keeps r3, and r2 goes out in d1: chain
    d3 = type(d1)('y', 'una', 'm', banca['r1'], {'codice': None})  # a new row without a code: postponed
    d4 = type(d1)('z', 'due', 'm')
    scritture, saltate = ScrittureS08(banca, 'S08').prepara([d1, d2, d3, d4])
    assert saltate == {'scrittura rinviata: riga nuova senza codice in banca': 1}
    assert scritture['r2']['esclusa_regola'] == 'S08' and scritture['r2']['unita_a'] == 'U-1'
    assert scritture['r3']['unita_a'] == 'U-1'  # the chain closes on the final row
    assert scritture['r1']['s08_da'] == 'S08' and len(scritture['r1']['proposto_nota_appoggio']) == 2
    assert scritture['r1']['proposto_paragrafi'] == ['1', '2']
    assert 'esclusa_il' not in scritture['r2']  # the timestamp is set by whoever writes


def test_la_decisione_scrive_solo_i_file_a_secco(radice: Path, tmp_path: Path) -> None:
    a, b = riga(ATTO, 'U-1', 0), riga(ATTO, 'U-2', 1)
    banca = {'r1': a, 'r2': b}
    dc = DecisioneCoppie(Config(radice=radice), banca, stampa=lambda t: None)
    richieste = [{'id': 'U-1__U-2', 'codici': ['U-1', 'U-2']}, {'id': 'nuova', 'codici': ['U-1', None]}]
    ds, rr = {'U-1__U-2': raccolta({'una': 5})}, {'U-1__U-2': raccolta({'una': 3})}
    decisioni, scritture, saltate = dc.decidi(richieste, ds, rr, tmp_path / 'out')
    assert [d.esito for d in decisioni] == ['una'] and saltate == {}
    assert set(scritture) == {'r1', 'r2'}
    assert (
        (tmp_path / 'out' / 'decisioni_s08.tsv').read_text(encoding='utf-8').splitlines()[1].startswith('U-1__U-2\tuna')
    )
    assert (
        json.loads((tmp_path / 'out' / 'scritture_s08_A_SECCO.json').read_text(encoding='utf-8'))['scritture'].keys()
        == scritture.keys()
    )


def test_leggi_richieste_da_json_e_da_jsonl_gz(tmp_path: Path) -> None:
    (tmp_path / 'r.json').write_text('[{"id": "a"}]', encoding='utf-8')
    with gzip.open(tmp_path / 'r.jsonl.gz', 'wt', encoding='utf-8') as h:
        h.write('{"id": "b"}\n')
    assert DecisioneCoppie.leggi_richieste(tmp_path / 'r.json') == [{'id': 'a'}]
    assert DecisioneCoppie.leggi_richieste(tmp_path / 'r.jsonl.gz') == [{'id': 'b'}]


def test_la_valutazione_conta_giuste_sbagliate_e_al_team(radice: Path, tmp_path: Path) -> None:
    a, b = riga(ATTO, 'U-1', 0), riga(ATTO, 'U-2', 1)
    verita = tmp_path / 'verita.tsv'
    with open(verita, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, delimiter='\t')
        w.writerow(['id', 'decisione', 'codice_tenuto_dalla_regola', 'codice_che_esce_per_la_regola', 'riga_da_tenere'])
        w.writerow(['P1', 'UNIRE', 'U-1', 'U-2', 'U-1'])
    dc = DecisioneCoppie(Config(radice=radice), {'r1': a, 'r2': b}, stampa=lambda t: None)
    v = dc.valuta(verita, solo_indizi=True)
    assert v.conti['matrice'] == {'una->una': 1} and v.conti['decise_giuste'] == 1 and v.conti['al_team'] == 0
    assert v.conti['precisione_sulle_decise'] == 1.0 and v.conti['riga_tenuta_giusta_sulle_unire'] == '1/1'
    sbagliata = dc.valuta(verita, {'U-1__U-2': raccolta({'due': 5})}, {'U-1__U-2': raccolta({'due': 3})})
    assert sbagliata.conti['matrice'] == {'una->team': 1}  # the strong clue says one: to the team, not a wrong «due»


# the loader of the new rows


class RegoleFinte:
    """The copy rules: two files with the same text are the same document."""

    def __init__(self, d04: set[str] | None = None, s06: set[str] | None = None) -> None:
        self.d04, self.s06 = d04 or set(), s06 or set()

    def documenti_d04(self) -> set[str]:
        return self.d04

    def ids_s06(self) -> set[str]:
        return self.s06

    def impronte(self, file: str) -> dict[str, str]:
        return {'pdf': '', 'testo': file.split('__')[0]}

    def chiave_testo(self, riga: Any) -> str:
        return str(riga['citazione_testuale'])

    def stesso_documento(self, a: Any, b: Any) -> str:
        return 'stesso testo' if a['testo'] and a['testo'] == b['testo'] else ''

    def scegli_per_scheda(self, files: Any) -> tuple[str, str]:
        return sorted(files)[0], 'scheda'


def riga_nuova(cs: int, caso: str = 'neubauer', doc: str = 'atto-x_aaaa', **kw: Any) -> dict[str, Any]:
    r = {
        'case_id': 'caso-x_1',
        'case_name': 'X v Y',
        'giurisdizioni': 'Austria',
        'document_id': doc,
        'tipo_atto': 'ricorso',
        'data': '2024-01-01',
        'pagina': 29,
        'rete': 'descrittiva',
        'forma_trovata': 'descrizione: R: Klimabeschluss',
        'citazione_testuale': 'una frase',
        'finestra_pagina': 'pagina',
        'file': 'markdown/atto.md',
        'char_start': cs,
        'regola_descrittiva': 'R',
        'testo_trovato': 'Klimabeschluss',
        'caso': caso,
        'chiave': f'S08-{caso}-{doc[-8:]}-{cs}',
        'c04_resta': True,
        'c04_motivo': 'passa',
    }
    r.update(kw)
    return r


def banca_viva() -> dict[str, dict[str, Any]]:
    base = {'caso_citato': 'neubauer', 'proposto_rete': 'lessicale'}
    return {
        'neubauer__atto-x_aaaa__70664': {
            **base,
            'document_id': 'atto-x_aaaa',
            'char_start': 70664,
            'codice': 'NEU-0121',
            'assegnato_a': 'u1',
        },
        'neubauer__altro_bbbb__100': {
            **base,
            'document_id': 'altro_bbbb',
            'char_start': 100,
            'codice': 'NEU-0300',
            'assegnato_a': 'u2',
        },
    }


def test_la_riga_s08_ha_la_forma_di_una_riga_descrittiva() -> None:
    d = next(iter(Caricatore(banca_viva(), '2026-10-05').documenti([riga_nuova(69272)]).values()))
    assert d['proposto_rete'] == 'descrittiva' and d['trovata_per_descrizione'] is True
    assert d['provenienza']['estrazione'] == 'S08' and d['causa_s08'] == 'S08_stessa_pagina'
    assert d['esecuzione_id'] == 'neubauer__nomi__2026-10-05-S08' and d['corroborazione'] == 'descrizione'
    assert d['codice'] == 'NEU-0301' and d['esito'] is None and d['incerta'] is False
    assert d['assegnato_a_in_attesa'] in ('u1', 'u2') and 'assegnato_a' not in d
    assert d['proposto_pagina'] == 29 and d['file_pdf'] == 'markdown/atto.md'.replace(
        'markdown/', 'documents/'
    ).replace('.md', '.pdf')


def test_la_riga_viva_piu_vicina_forma_la_coppia() -> None:
    c = Caricatore(banca_viva(), '2026-10-05')
    assert c.vicina(riga_nuova(69272)) == ('NEU-0121', 'neubauer__atto-x_aaaa__70664', 1392)
    assert c.vicina(riga_nuova(60000)) is None  # beyond 5,000 characters: alone
    assert c.vicina(riga_nuova(69272, doc='altro_bbbb')) is None  # a farther row of another filing does not count
    assert c.vicina(riga_nuova(200, doc='altro_bbbb')) == ('NEU-0300', 'neubauer__altro_bbbb__100', 100)
    assert c.vicina(riga_nuova(69272, doc='nessuno')) is None
    d = next(iter(c.documenti([riga_nuova(69272)]).values()))
    assert d['s08_vicina_codice'] == 'NEU-0121' and d['s08_vicina_distanza'] == 1392


def test_c04_e_un_indizio_non_una_esclusione() -> None:
    d = next(
        iter(
            Caricatore(banca_viva(), '2026-10-05')
            .documenti([riga_nuova(69272, c04_resta=False, c04_motivo='data')])
            .values()
        )
    )
    assert d['c04_resta'] is False and d['c04_motivo'] == 'data'


def test_codici_progressivi_e_nessun_id_doppio() -> None:
    c = Caricatore(banca_viva(), '2026-10-05')
    docs = c.documenti([riga_nuova(10), riga_nuova(20), riga_nuova(30)])
    assert sorted(d['codice'] for d in docs.values()) == ['NEU-0301', 'NEU-0302', 'NEU-0303']
    with pytest.raises(ValueError, match='already in the database'):
        c.documenti([riga_nuova(70664)])  # the id is already in the database: the write refuses


def test_il_campione_cieco_e_l_ocr_seguono_i_dati(tmp_path: Path) -> None:
    (tmp_path / 'atto.md').write_text('prima dell ocr', encoding='utf-8')
    c = Caricatore(banca_viva(), '2026-10-05', nuovi_md={'markdown/atto.md'}, ocr_prima=tmp_path)
    docs = c.documenti([riga_nuova(i) for i in range(1, 51)])
    assert all(d['provenienza']['corpus'] == 'D03' and d['provenienza']['ocr'] == '2026-10-05' for d in docs.values())
    ciechi = sum(1 for d in docs.values() if d['campione_cieco'])
    assert 1 <= ciechi <= 25
    assert c.documenti([riga_nuova(i) for i in range(1, 51)]).keys() == docs.keys()


def test_le_verifiche_dicono_fallita_se_un_id_c_e_gia() -> None:
    docs = Caricatore(banca_viva(), '2026-10-05').documenti([riga_nuova(10)])
    v = verifiche(docs, [riga_nuova(10)], {'x'})
    assert not v[0][1]  # id already in the database
    assert not all(x[1] for x in verifiche(docs, [riga_nuova(10)], set()))  # the two proof cases are missing


def test_le_verifiche_trovano_i_due_casi_di_prova() -> None:
    banca = {
        'neubauer__aaaa_6a3b__70664': {
            'caso_citato': 'neubauer',
            'proposto_rete': 'lessicale',
            'document_id': 'aaaa_6a3b',
            'char_start': 70664,
            'codice': 'NEU-1',
        },
        'neubauer__bbbb_d48d__58268': {
            'caso_citato': 'neubauer',
            'proposto_rete': 'lessicale',
            'document_id': 'bbbb_d48d',
            'char_start': 58268,
            'codice': 'NEU-2',
        },
    }
    nuove = [riga_nuova(69272, doc='aaaa_6a3b', pagina=29), riga_nuova(57336, doc='bbbb_d48d', pagina=10)]
    docs = Caricatore(banca, '2026-10-05').documenti(nuove)
    assert all(x[1] for x in verifiche(docs, nuove, set()))


def test_le_copie_dello_stesso_documento_sono_una_citazione() -> None:
    banca = {
        'v': {
            'caso_citato': 'neubauer',
            'proposto_rete': 'lessicale',
            'document_id': 'viva',
            'citazione_testuale': 'frase1',
            'file': 'T__v.md',
            'case_id': 'c-v',
            'codice': 'NEU-1',
            'char_start': 1,
        },
    }
    copie = Copie(banca, RegoleFinte(d04={'d04doc'}, s06=set()))
    nuove = [
        riga_nuova(10, doc='copia', citazione_testuale='frase1', file='T__c.md'),  # same text as the live row elsewhere
        riga_nuova(20, doc='unica', citazione_testuale='frase2', file='U__u.md'),
        riga_nuova(30, doc='da_d04', citazione_testuale='frase3', file='D__d.md'),
    ]
    nuove[2]['document_id'] = 'd04doc'
    tenute, escluse = copie.separa(nuove, Caricatore.id_di)
    assert [r['document_id'] for r in tenute] == ['unica']
    perche = {e['document_id']: e['perche'] for e in escluse}
    assert perche['copia'].startswith('stesso testo') and 'D04' in perche['d04doc']


def test_due_copie_nuove_dello_stesso_frammento_ne_tengono_una_scelta_dalla_scheda() -> None:
    copie = Copie({}, RegoleFinte())
    a = riga_nuova(10, doc='aaa', citazione_testuale='f', file='T__a.md', case_id='c-a')
    b = riga_nuova(10, doc='bbb', citazione_testuale='f', file='T__b.md', case_id='c-b')
    tenute, escluse = copie.separa([b, a], Caricatore.id_di)
    assert [t['document_id'] for t in tenute] == ['aaa']  # the record picks the first path, not the order of arrival
    assert tenute[0]['stesso_documento_case_ids'] == ['c-b']
    assert escluse[0]['document_id'] == 'bbb' and 'copia scelta dalla scheda' in escluse[0]['perche']


class Sorgente:
    def __init__(self, righe: list[dict[str, Any]]) -> None:
        self._righe = righe

    def righe(self) -> list[dict[str, Any]]:
        return self._righe


def carica(
    tmp_path: Path, righe: list[dict[str, Any]], scrivi: bool = False, db: BancaDatiMemoria | None = None
) -> tuple[Any, BancaDatiMemoria, list[str]]:
    db = db or BancaDatiMemoria({'corpus_rows': banca_viva()})
    detto: list[str] = []
    c = CaricaS08(Config(radice=tmp_path), db, Sorgente(righe), RegoleFinte(), scrivi=scrivi, stampa=detto.append)
    return c, db, detto


def test_la_prova_d_anteprima_non_scrive_niente(tmp_path: Path) -> None:
    righe = [riga_nuova(10), riga_nuova(20)]
    c, db, detto = carica(tmp_path, righe)
    esito = c.esegui()
    assert len(esito.documenti) == 2 and db.scritture == [] and esito.scritti == 0 and esito.copia is None
    assert detto[-1] == '\nPREVIEW: nothing written'
    assert (tmp_path / 'training' / 's08' / 'escluse_copie_s08.jsonl').exists()
    assert (tmp_path / 'training' / 's08' / 'documenti_s08_da_scrivere.json').exists()
    assert any('TOTAL' in x for x in detto) and any(
        x.startswith('FAILED') for x in detto
    )  # the proof cases are absent


def test_non_scrive_se_le_verifiche_falliscono(tmp_path: Path) -> None:
    c, db, _ = carica(tmp_path, [riga_nuova(10)], scrivi=True)
    with pytest.raises(RuntimeError, match='checks failed'):
        c.esegui()
    assert db.scritture == []


def test_scrive_le_righe_nuove_con_create_e_la_lista_degli_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tracepipe.carica_s08 as modulo

    monkeypatch.setattr(modulo, 'ATTESE', ())  # no proof cases in this synthetic filing
    righe = [riga_nuova(10), riga_nuova(20)]
    c, db, _ = carica(tmp_path, righe, scrivi=True)
    esito = c.esegui()
    assert esito.scritti == 2 and esito.copia is not None
    assert sorted(json.loads(esito.copia.read_text(encoding='utf-8'))['creati']) == sorted(esito.documenti)
    assert {s['op'] for s in db.scritture} == {'create'} and {s['doc_id'] for s in db.scritture} == set(esito.documenti)
    assert all(s['dati']['creato_il'] == '__SERVER_TIMESTAMP__' for s in db.scritture)


def test_un_id_gia_in_banca_blocca_la_scrittura(tmp_path: Path) -> None:
    c, db, _ = carica(tmp_path, [riga_nuova(70664)], scrivi=True)
    with pytest.raises(ValueError, match='already in the database'):
        c.esegui()
    assert db.scritture == []


def test_la_banca_sa_dire_quali_id_esistono() -> None:
    db = BancaDatiMemoria({'corpus_rows': banca_viva()})
    assert db.esistenti('corpus_rows', ['neubauer__altro_bbbb__100', 'non_c_e']) == {'neubauer__altro_bbbb__100'}
    assert db.esistenti('altra', ['x']) == set()
