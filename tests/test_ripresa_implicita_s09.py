"""S09, le riprese implicite dal Ponte: la domanda L14, i freni, la taratura, la decisione, la misura, i blocchi per ReCaS.

Ogni prova ha il caso che DEVE fallire se il passo manca o e' sbagliato. Solo atti e righe sintetici: niente qui ha bisogno della
piattaforma, dei modelli o dei file del corpus. Le prove sono sui file vivi di ``tools/`` (non nel repository pubblico): si saltano
se ``tools/`` non c'e'.
"""

from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

import pytest

STRUMENTI = Path(__file__).resolve().parent.parent / 'tools'
pytestmark = pytest.mark.skipif(
    not (STRUMENTI / 'leggi_ripresa_l14.py').exists(), reason='live scripts absent: tools/ is not in the public repository'
)

if STRUMENTI.exists() and str(STRUMENTI) not in sys.path:
    sys.path.insert(0, str(STRUMENTI))


@pytest.fixture(scope='module')
def L14():
    import leggi_ripresa_l14

    return leggi_ripresa_l14


@pytest.fixture(scope='module')
def S9():
    import decidi_s09

    return decidi_s09


FINESTRA = (
    'Each state must do its part: a country cannot escape its own responsibility by pointing out that its emissions are only a '
    'small share of the global total, because every reduction counts. The court therefore orders the state to cut emissions by a '
    'quarter before 2020. Further text of the filing continues here with other arguments about procedure and costs.'
)
PASSO = 'No reduction is negligible: every country is partly responsible for its own share of the global emissions.'


class VociFinte:
    def scheda(self, id_voce):
        return {'caso': 'urgenda', 'nome_caso': 'Urgenda Foundation v. State of the Netherlands', 'data_caso': '2015-06-24',
                'etichetta': '5.7.7', 'sintesi': 'Il piccolo contributo non esonera dalla propria quota.',
                'verbatim': 'no reduction is negligible',
                'principi': [('propria_quota', 'Responsabilita per la propria quota', 'Each country is responsible for its own share.')]}


class AttiFinti:
    def meta(self, doc):
        return {'document_title': 'Atto di prova', 'tipo_atto': 'memoria', 'lingue': 'English'}


def coppia(i, tipo='test', p_si=0.5, caso='urgenda', riga='', giusta=None, q=FINESTRA):
    return {'id': f'caso__doc__{i}#w0~urgenda#{i}', 'pid': f'caso__doc__{i}#w0', 'voce': f'urgenda#{i}', 'caso': caso, 'tipo': tipo,
            'giusta': giusta, 'riga': riga or f'riga{i}', 'q': q, 'd': PASSO, 'p_si': p_si}


def raccolta(voti, previste, letture=None):
    valide = sum(voti.values())
    return {'voti': dict(voti), 'valide': valide, 'scartate': {}, 'fatte': previste, 'previste': previste,
            'letture': letture or [{'lettura': k, 'valida': True, 'json': {'esito': e, 'frase': 'f', 'motivo': 'm'}}
                                   for k, (e, n) in enumerate((e, n) for e, n in voti.items() for _ in range(n))]}


# la domanda

def test_la_domanda_porta_paragrafo_principi_e_finestra(L14):
    d = L14.DomandaL14(VociFinte(), AttiFinti(), {})
    t = d.testo(coppia(1))
    for pezzo in ('Urgenda Foundation v. State', '5.7.7', 'Il piccolo contributo', 'propria_quota', PASSO, FINESTRA[:60], 'Atto di prova'):
        assert pezzo in t
    assert t.index(PASSO) < t.index(FINESTRA[:60]) < t.index('DOMANDA.')


def test_la_domanda_non_porta_indizi_ne_giudizi(L14):
    c = coppia(2, tipo='negativo', p_si=0.987654, giusta=True)
    t = L14.DomandaL14(VociFinte(), AttiFinti(), {}).testo(c)
    for vietato in ('0.987654', '0,987654', 'negativo', 'giusta', 'coseno', 'soglia', 'P(si', 'taratura'):
        assert vietato not in t


def test_il_reranker_ha_in_piu_le_sue_istruzioni_e_la_stessa_domanda(L14):
    d = L14.DomandaL14(VociFinte(), AttiFinti(), {})
    ds, rr = d.testo(coppia(3)), d.testo(coppia(3), rr=True)
    assert rr.endswith(ds) and rr.startswith(L14.ISTRUZIONI_RR) and not ds.startswith(L14.ISTRUZIONI_RR)


def test_nessun_principio_e_scritto_chiaro(L14):
    class Senza(VociFinte):
        def scheda(self, id_voce):
            return {**super().scheda(id_voce), 'principi': [], 'verbatim': ''}

    t = L14.DomandaL14(Senza(), AttiFinti(), {}).testo(coppia(4))
    assert 'nessuno: la mappa non attribuisce principi' in t and 'Frase caratteristica' not in t


def test_doc_e_pagina_dai_tre_formati(L14):
    assert L14.doc_e_pagina('doc-a_1234#p101#w0') == ('doc-a_1234', 101)
    assert L14.doc_e_pagina('noto:doc-b_9#p69#w3') == ('doc-b_9', 69)
    assert L14.doc_e_pagina('urgenda__doc-c__55#w0', {'urgenda__doc-c__55#w0': {'doc': 'doc-c', 'pagina': '7'}}) == ('doc-c', 7)
    assert L14.doc_e_pagina('urgenda__doc-c__55#w0') == ('', 0)


# i freni

def freni_della(L14, finestra=FINESTRA, extra=()):
    return L14.FreniL14(finestra, L14.DomandaL14.testi_prompt() + [PASSO, *extra])


def test_la_prova_dei_freni_passa(L14):
    assert L14.prova_freni() == []


def test_una_lettura_buona_passa(L14):
    j = {'esito': 'si', 'frase': 'a country cannot escape its own responsibility by pointing out that its emissions are only a small share', 'motivo': 'x'}
    assert freni_della(L14).verifica(j)[0]


def test_la_frase_copiata_dal_paragrafo_della_decisione_non_passa(L14):
    ok, motivo, _ = freni_della(L14).verifica({'esito': 'si', 'frase': PASSO, 'motivo': 'x'})
    assert not ok and motivo == 'frase copiata dal prompt'


def test_la_frase_inventata_non_passa(L14):
    j = {'esito': 'si', 'frase': 'the court awarded ten million euros in damages to every single applicant of the case', 'motivo': 'x'}
    ok, motivo, _ = freni_della(L14).verifica(j)
    assert not ok and motivo == 'frase non trovata nella finestra'


def test_si_senza_frase_non_passa_ma_no_senza_frase_si(L14):
    fr = freni_della(L14)
    assert fr.verifica({'esito': 'si', 'frase': '', 'motivo': 'x'})[1] == 'si senza frase'
    assert fr.verifica({'esito': 'no', 'frase': '', 'motivo': 'solo il tema'})[0]
    assert fr.verifica({'esito': 'forse', 'frase': '', 'motivo': 'x'})[0]


def test_una_frase_data_deve_comunque_stare_nella_finestra(L14):
    j = {'esito': 'no', 'frase': 'the state must pay a fine of ten million euros to every applicant of the proceedings', 'motivo': 'x'}
    assert not freni_della(L14).verifica(j)[0]


def test_esito_fuori_elenco_e_risposta_vuota_non_passano(L14):
    fr = freni_della(L14)
    assert not fr.verifica({'esito': 'incerta', 'frase': '', 'motivo': 'x'})[0]
    assert not fr.verifica({})[0] and not fr.verifica('si')[0]


def test_il_freno_uno_ferma_una_finestra_rotta_e_la_mette_in_elenco(L14, tmp_path):
    rotta = 'Ð§Ñ‚Ð¾ ' * 120
    prep = L14.Preparazione(L14.DomandaL14(VociFinte(), AttiFinti(), {}))
    uscita = tmp_path / 'r.jsonl.gz'
    conti = prep.prepara([coppia(1), coppia(2, q=rotta)], uscita)
    assert conti == {'richieste': 1, 'illeggibile': 1}
    assert len(L14.jl(uscita)) == 1
    assert json.load(open(f'{uscita}.illeggibili.json'))[0]['id'].endswith('2#w0~urgenda#2')


# le richieste

def test_le_richieste_hanno_priorita_gruppo_letture_e_nessuna_verita(L14, tmp_path):
    prep = L14.Preparazione(L14.DomandaL14(VociFinte(), AttiFinti(), {}))
    tar = coppia(1, tipo='test', giusta=True, p_si=0.9)
    pool = coppia(2, tipo='pool')
    ds = prep.richiesta(tar, rr=False, priorita=0)
    rr = prep.richiesta(pool, rr=True, priorita=1)
    assert (ds['priorita'], ds['letture'], ds['tetto'], ds['lettore']) == (0, 5, 24000, 'ds')
    assert (rr['priorita'], rr['letture'], rr['tetto'], rr['lettore']) == (1, 3, 12000, 'rr')
    assert re.fullmatch(r'[0-9a-f]{8}', ds['gruppo'])
    # nella richiesta non c'e' il tipo della coppia, ne' il giudizio, ne' il punteggio del Ponte
    assert not {'tipo', 'giusta', 'p_si', 'sopra_soglia'} & set(ds)
    assert ds['puro'] == FINESTRA


def test_la_taratura_ha_priorita_zero_e_il_pool_uno(L14, tmp_path):
    prep = L14.Preparazione(L14.DomandaL14(VociFinte(), AttiFinti(), {}))
    uscita = tmp_path / 'r.jsonl.gz'
    prep.prepara([coppia(1, 'pool'), coppia(2, 'test', giusta=True), coppia(3, 'noto')], uscita)
    p = {r['id'].split('~')[0]: r['priorita'] for r in L14.jl(uscita)}
    assert p == {'caso__doc__1#w0': 1, 'caso__doc__2#w0': 0, 'caso__doc__3#w0': 0}


# la scelta della taratura

def prova_coppie():
    c = []
    for k in range(40):                       # test: 20 urgenda e 20 neubauer, tutti con la voce giusta sopra soglia (k pari) o sotto (k dispari)
        c.append(coppia(k, 'test', 0.5 if k % 2 == 0 else 0.01, 'urgenda' if k < 20 else 'neubauer', giusta=True))
        c.append(coppia(100 + k, 'test', 0.9, 'urgenda' if k < 20 else 'neubauer', riga=f'riga{k}', giusta=False))
    for k in range(10):                       # negativo: 5 righe con due finestre sopra soglia, 5 sotto
        for w in range(2):
            c.append({**coppia(200 + 2 * k + w, 'negativo', 0.4 + w / 10 if k < 5 else 0.02, riga=f'neg{k}')})
    for k in range(3):
        c.append(coppia(300 + k, 'noto', (0.01, 0.02, 0.5)[k]))
    return c


def test_la_taratura_prende_solo_la_voce_giusta_sopra_soglia(L14):
    scelte = L14.Taratura(0.0851, per_caso=100).scegli(prova_coppie())
    test = [c for c in scelte if c['tipo'] == 'test']
    assert test and all(c['giusta'] and c['p_si'] >= 0.0851 for c in test)
    assert len(test) == 20                     # 40 righe, la meta' con la voce giusta sopra soglia


def test_la_taratura_ha_un_tetto_per_caso_e_il_seme_la_fissa(L14):
    a = L14.Taratura(0.0851, per_caso=4, seme=1).scegli(prova_coppie())
    b = L14.Taratura(0.0851, per_caso=4, seme=1).scegli(prova_coppie())
    c = L14.Taratura(0.0851, per_caso=4, seme=2).scegli(prova_coppie())
    n = lambda x: sorted(y['id'] for y in x if y['tipo'] == 'test')  # noqa: E731
    assert n(a) == n(b) and n(a) != n(c)
    assert len(n(a)) == 8                      # 4 per ognuno dei due casi


def test_i_negativi_sono_uno_per_riga_e_solo_sopra_soglia(L14):
    neg = [c for c in L14.Taratura(0.0851).scegli(prova_coppie()) if c['tipo'] == 'negativo']
    assert len(neg) == 5 and len({c['riga'] for c in neg}) == 5 and all(c['p_si'] >= 0.0851 for c in neg)
    assert all(c['p_si'] == pytest.approx(0.5) for c in neg)       # la migliore delle due finestre


def test_i_noti_entrano_tutti_anche_sotto_soglia_e_si_segna(L14):
    noti = [c for c in L14.Taratura(0.0851).scegli(prova_coppie()) if c['tipo'] == 'noto']
    assert len(noti) == 3 and [c['sopra_soglia'] for c in sorted(noti, key=lambda c: c['p_si'])] == [False, False, True]


# i lettori e la decisione

def test_un_lettore_vale_con_la_maggioranza_minima(S9):
    ds = S9.Lettore('DS', 3, 5)
    assert ds.verdetto(raccolta({'si': 3, 'no': 2}, 5))[0] == 'si'
    assert ds.verdetto(raccolta({'si': 2, 'no': 2, 'forse': 1}, 5))[0] == 'forse'       # parita'
    assert ds.verdetto(raccolta({'si': 2}, 5))[0] == 'forse'                              # meno del minimo
    assert ds.verdetto(raccolta({}, 5))[0] is None


def test_il_9b_scarta_con_certezza_solo_con_tre_no_validi(S9):
    rr = S9.Lettore('9B', 2)
    assert rr.scarto_certo(raccolta({'no': 3}, 3))
    assert not rr.scarto_certo(raccolta({'no': 2}, 3))                 # due letture valide su tre: non basta
    assert not rr.scarto_certo(raccolta({'no': 2, 'forse': 1}, 3))
    assert not rr.scarto_certo(raccolta({'no': 2, 'si': 1}, 3))
    assert not rr.scarto_certo(None)


@pytest.mark.parametrize(
    ('rr', 'ds', 'esito', 'da'),
    [
        ({'no': 3}, None, 'fuori', '9B'),                       # il 9B scarta, DeepSeek non legge
        ({'no': 3}, {'si': 5}, 'fuori', '9B'),                  # anche se DeepSeek dice si: il 9B ha scartato con certezza
        ({'si': 3}, {'si': 4, 'no': 1}, 'proposta', ''),
        ({'si': 2, 'forse': 1}, {'si': 3, 'forse': 2}, 'proposta', ''),
        ({'si': 3}, {'no': 5}, 'team', ''),                     # disaccordo
        ({'no': 2, 'forse': 1}, {'si': 5}, 'team', ''),         # il 9B dice no ma non con certezza, DeepSeek si
        ({'forse': 3}, {'si': 5}, 'team', ''),                  # un lettore dice forse
        ({'si': 3}, {'forse': 3, 'si': 2}, 'team', ''),
        ({'no': 2, 'forse': 1}, {'no': 4, 'forse': 1}, 'fuori', 'lettori'),
        ({'si': 3}, {}, 'team', ''),                            # DeepSeek: tutte le letture scartate dai freni
        ({}, {'si': 5}, 'team', ''),                            # 9B: tutte le letture scartate dai freni
    ],
)
def test_la_decisione(S9, rr, ds, esito, da):
    r = raccolta(rr, 3)
    d = raccolta(ds, 5) if ds is not None else None
    x = S9.Decisore().decidi('c1', r, d)
    assert (x.esito, x.da) == (esito, da)


def test_senza_letture_complete_si_aspetta(S9):
    dec = S9.Decisore()
    assert dec.decidi('c', None, None).esito == 'attesa_rr'
    parziale = {**raccolta({'si': 2}, 3), 'fatte': 2}
    assert dec.decidi('c', parziale, None).esito == 'attesa_rr'
    assert dec.decidi('c', raccolta({'si': 3}, 3), None).esito == 'attesa_ds'
    assert dec.decidi('c', raccolta({'si': 3}, 3), {**raccolta({'si': 4}, 5), 'fatte': 4}).esito == 'attesa_ds'


def test_la_proposta_porta_la_frase_e_non_conta(S9):
    x = S9.Decisore().decidi('c1', raccolta({'si': 3}, 3), raccolta({'si': 5}, 5))
    assert x.esito == 'proposta' and x.extra['frase_ds'] == 'f' and 'non contata' in x.motivo


# la misura

def test_wilson_valori_noti(S9):
    assert S9.Intervalli.wilson(0, 10) == [0.0, 0.278]
    assert S9.Intervalli.wilson(5, 10) == [0.237, 0.763]
    assert S9.Intervalli.wilson(1, 0) is None


def test_precisione_alla_prevalenza(S9):
    # sensibilita' 0,8 e falsi positivi 0,1: al 50% la precisione e' 0,8/(0,8+0,1)
    assert S9.Intervalli.precisione(0.8, 0.1, 0.5) == pytest.approx(0.889, abs=0.001)
    # a prevalenza bassa scende molto
    assert S9.Intervalli.precisione(0.8, 0.1, 0.02) < 0.15


def taratura_finta(n_test=60, n_noto=4, n_neg=100):
    t = {f't{i}': {'tipo': 'test'} for i in range(n_test)}
    t |= {f'n{i}': {'tipo': 'noto'} for i in range(n_noto)}
    t |= {f'x{i}': {'tipo': 'negativo'} for i in range(n_neg)}
    return t


def decisioni(S9, mappa):
    return {i: S9.Decisione(i, e, 'm', d) for i, (e, d) in mappa.items()}


def test_la_misura_conta_e_applica_il_criterio_scritto_prima(S9):
    t = taratura_finta()
    m = {i: ('proposta', '') for i in t if i.startswith('t')}                    # tutte le vere diventano proposta
    m |= {i: ('proposta', '') for i in t if i.startswith('n')}
    m |= {f'x{k}': ('proposta', '') for k in range(3)}                             # 3% di falsi positivi
    m |= {f'x{k}': ('fuori', '9B') for k in range(3, 100)}
    ris = S9.Misura(t, decisioni(S9, m), {}, {}).calcola()
    assert ris['proposta_sui_test'][:3] == [60, 60, 1.0]
    assert ris['proposta_sui_negativi'][:3] == [3, 100, 0.03]
    assert ris['criterio']['passa']
    assert ris['criterio']['condizioni']['falsi positivi sui negativi']['passa']
    assert ris['precisione_a_prevalenza']['50%']['stima'] > 0.9


def test_il_criterio_non_passa_con_troppi_falsi_positivi(S9):
    t = taratura_finta()
    m = {i: ('proposta', '') for i in t}                                           # tutto e' proposta, anche i negativi
    ris = S9.Misura(t, decisioni(S9, m), {}, {}).calcola()
    assert not ris['criterio']['passa'] and not ris['criterio']['condizioni']['falsi positivi sui negativi']['passa']


def test_il_criterio_non_passa_se_il_9b_perde_troppi_positivi(S9):
    t = taratura_finta()
    m = {i: ('proposta', '') for i in t if i.startswith(('t', 'n'))}
    for k in range(20):
        m[f't{k}'] = ('fuori', '9B')
    m |= {f'x{k}': ('fuori', 'lettori') for k in range(100)}
    ris = S9.Misura(t, decisioni(S9, m), {}, {}).calcola()
    assert not ris['criterio']['condizioni']['perdita del 9B sui positivi']['passa']
    assert not ris['criterio']['passa']


def test_il_criterio_non_passa_con_campione_piccolo_o_letture_in_attesa(S9):
    t = taratura_finta(n_test=10, n_neg=20)
    m = {i: ('proposta', '') for i in t if i[0] in 'tn'} | {i: ('fuori', 'lettori') for i in t if i[0] == 'x'}
    ris = S9.Misura(t, decisioni(S9, m), {}, {}).calcola()
    assert not ris['criterio']['condizioni']['negativi letti (minimo)']['passa'] and not ris['criterio']['passa']
    t = taratura_finta()
    m = {i: ('attesa_ds', '') for i in t}
    assert not S9.Misura(t, decisioni(S9, m), {}, {}).calcola()['criterio']['condizioni']['letture finite (nessuna in attesa)']['passa']


def test_le_coppie_senza_decisione_contano_come_illeggibili(S9):
    t = taratura_finta()
    m = {i: ('fuori', 'lettori') for i in list(t)[:-5]}
    ris = S9.Misura(t, decisioni(S9, m), {}, {}).calcola()
    assert ris['illeggibili'][:2] == [5, len(t)]


def test_il_markdown_della_misura_dichiara_i_limiti_e_il_criterio(S9):
    t = taratura_finta()
    m = {i: ('proposta' if i[0] in 'tn' else 'fuori', '') for i in t}
    testo = S9.Misura.markdown(S9.Misura(t, decisioni(S9, m), {}, {}).calcola(), '2026-10-05')
    assert 'scritto prima dei risultati' in testo and 'Cosa non dimostra' in testo and 'non decide' in testo


# le scritture a secco

def test_scrivi_non_e_abilitato_e_firestore_non_e_importato(S9, L14):
    for modulo in (S9, L14):
        sorgente = Path(modulo.__file__).read_text(encoding='utf-8')
        assert not re.search(r'^\s*(import|from)\s+(firebase|google\.cloud)', sorgente, re.M)
        assert not re.search(r'\.set\(|\.commit\(|firestore_client', sorgente)
    assert "--scrivi non e' abilitato" in Path(S9.__file__).read_text(encoding='utf-8')


def test_le_scritture_a_secco_hanno_il_formato_delle_semantiche_e_non_contano(S9, tmp_path, monkeypatch):
    md = tmp_path / 'markdown' / 'caso-x_1'
    md.mkdir(parents=True)
    corpo = 'Premessa del documento con altre parole.\n\n<!-- page 3 -->\n\n' + FINESTRA + '\n\nFine.\n'
    (md / 'atto-prova_ab12__atto-prova.md').write_text(
        "---\ndocument_id: 'atto-prova_ab12'\ndocument_title: 'Atto'\ntipo_atto: 'memoria'\ncase_id: 'caso-x_1'\ncase_name: 'X v. Y'\n---\n" + corpo,
        encoding='utf-8')
    sc = S9.Scritture(radice=tmp_path)
    sc.voci = VociFinte()
    c = {'id': 'atto-prova_ab12#p3#w0~urgenda#5', 'pid': 'atto-prova_ab12#p3#w0', 'voce': 'urgenda#5', 'caso': 'urgenda', 'q': FINESTRA}
    d = S9.Decisione(c['id'], 'proposta', 'm', voti_ds='{"si": 5}', voti_rr='{"si": 3}')
    scr, saltate = sc.prepara([(c, d, raccolta({'si': 3}, 3), raccolta({'si': 5}, 5))])
    assert saltate == {} and len(scr) == 1
    rid, riga = next(iter(scr.items()))
    assert rid == f"urgenda__atto-prova_ab12__{riga['char_start']}"
    assert riga['proposto_rete'] == 'semantica' and riga['esito'] is None
    assert riga['proposta_s09'] and riga['fuori_dai_conteggi']
    assert riga['proposto_pagina'] == 3 and riga['s09']['codice'] == 'S09' and riga['s09']['principi_mappa'] == ['propria_quota']
    testo = (tmp_path / riga['file']).read_text(encoding='utf-8')
    assert testo[riga['char_start']:].startswith('Each state must do its part')


def test_una_riga_gia_in_banca_non_si_tocca(S9, tmp_path):
    md = tmp_path / 'markdown' / 'caso-x_1'
    md.mkdir(parents=True)
    (md / 'a_ab12__a.md').write_text("---\ndocument_id: 'a_ab12'\n---\n<!-- page 1 -->\n" + FINESTRA + '\n', encoding='utf-8')
    c = {'id': 'a_ab12#p1#w0~urgenda#5', 'pid': 'a_ab12#p1#w0', 'voce': 'urgenda#5', 'caso': 'urgenda', 'q': FINESTRA}
    d = S9.Decisione(c['id'], 'proposta', 'm')
    primo = S9.Scritture(radice=tmp_path)
    primo.voci = VociFinte()
    rid = next(iter(primo.prepara([(c, d, None, None)])[0]))
    secondo = S9.Scritture([rid], radice=tmp_path)
    secondo.voci = VociFinte()
    scr, saltate = secondo.prepara([(c, d, None, None)])
    assert scr == {} and saltate == {"riga gia' in banca dati": 1}


# la raccolta, la lettura e i blocchi

def test_raccogli_conta_solo_le_letture_che_passano_i_freni(L14, tmp_path):
    prep = L14.Preparazione(L14.DomandaL14(VociFinte(), AttiFinti(), {}))
    r = prep.richiesta(coppia(1), rr=False, priorita=0)
    buona = json.dumps({'esito': 'si', 'frase': 'a country cannot escape its own responsibility by pointing out that its emissions are only a small share',
                        'motivo': 'x'})
    copiata = json.dumps({'esito': 'si', 'frase': PASSO, 'motivo': 'x'})
    no = json.dumps({'esito': 'no', 'frase': '', 'motivo': 'tema'})
    esiti = tmp_path / 'e.jsonl'
    esiti.write_text('\n'.join(json.dumps({'id': r['id'], 'lettura': k, 'testo': t}) for k, t in enumerate([buona, '<think>x</think>' + buona, copiata, no, 'non json'])),
                     encoding='utf-8')
    ris = L14.raccogli([r], esiti)[r['id']]
    assert ris['voti'] == {'si': 2, 'no': 1} and ris['valide'] == 3 and ris['fatte'] == 5
    assert ris['scartate'] == {'frase copiata dal prompt': 1, 'risposta senza esito valido': 1}


def test_leggi_scrive_il_codice_l14_senza_toccare_il_lettore_di_s08(L14, monkeypatch):
    visto = {}
    monkeypatch.setattr(L14.L13, 'leggi', lambda a: visto.update(codice=L14.L13.CODICE, a=a))
    monkeypatch.setattr(L14.L13, 'CODICE', 'L13')
    L14.leggi('args')
    assert visto == {'codice': 'L14', 'a': 'args'}


def test_i_blocchi_si_alternano_e_non_stanno_davanti_alla_scala(L14):
    b = L14.Blocchi()
    voci = b.voci()
    ds = voci[b.DS_TARATURA]
    assert ds[1] == 'attesa_ds'
    testo = ds[0]
    assert '--ragionamento deepseek-high' in testo and '--minuti 25' in testo and '--paralleli 32' in testo
    assert f'cp $0 $G/attesa_ds/{b.DS_TARATURA}.sh' in testo and 'mv $f $H/trace/chat/coda-ds4/' in testo
    assert 'a_scala_e0e3' not in testo and 'FINITO log/a_scala' not in testo        # non aspetta la scala: si alterna
    assert 'scrivi' not in testo.lower().replace('scritto', '')


def test_i_blocchi_del_9b_vengono_dopo_quelli_degli_altri_e_la_taratura_prima_del_pool(L14):
    b = L14.Blocchi()
    voci = b.voci()
    nomi = sorted(n for n, (_, dove) in voci.items() if dove == 'coda9b')
    assert nomi == [b.RR_TARATURA, b.RR_POOL]
    assert all(n > '50_rr9_s08_coppie' for n in nomi) and b.RR_TARATURA < b.RR_POOL
    assert b.DS_TARATURA > 'b_s08_coppie_l13'
    rr = voci[b.RR_TARATURA][0]
    assert '--ragionamento qwen-pensa' in rr and 'richieste/ponte_impl_l14_rr_taratura.jsonl.gz' in rr and 'esiti/q9_ponte_impl_l14_taratura.jsonl' in rr


def test_il_blocco_del_pool_di_deepseek_si_manda_solo_dopo_la_misura(L14):
    b = L14.Blocchi()
    assert b.DS_POOL not in b.voci() and list(b.voci(pool_ds=True)) == [b.DS_POOL]
    assert b.RICHIESTE['ds_pool'] in b.voci(pool_ds=True)[b.DS_POOL][0]


def test_i_blocchi_non_toccano_i_file_degli_altri(L14, tmp_path):
    scritti = L14.Blocchi().scrivi(tmp_path)
    assert {p.name for p in scritti} == {f'{n}.sh' for n in (L14.Blocchi.DS_TARATURA, L14.Blocchi.RR_TARATURA, L14.Blocchi.RR_POOL)}
    nomi_altrui = ('b_s08_coppie_l13', '50_rr9_s08_coppie', 'a_scala_e0e3', '40_rr9_punto')
    for p in scritti:
        assert not any(n in p.name for n in nomi_altrui)


class FinteRecas:
    """un ReCaS finto: registra cosa viene copiato e cosa c'e' gia'"""

    def __init__(self, L14, presenti=()):
        self.presenti, self.copiati, self.comandi = set(presenti), [], []
        self.recas = L14.Recas()
        self.recas.ssh = self.ssh
        self.recas.scp = lambda locale, remoto: self.copiati.append(remoto)

    def ssh(self, comando):
        self.comandi.append(comando)
        if comando.startswith('ls '):
            return '\n'.join(p for p in comando[3:].replace(' 2>/dev/null', '').split() if any(x in p for x in self.presenti))
        return ''


def test_manda_non_sovrascrive_uno_script_gia_in_coda_o_in_corso(L14, tmp_path):
    b = L14.Blocchi()
    (tmp_path / 'richieste').mkdir()
    f = FinteRecas(L14, presenti=[b.RR_TARATURA])
    esito = f.recas.manda(tmp_path)
    assert esito[b.RR_TARATURA].startswith("gia' presente") and esito[b.DS_TARATURA] == 'messo' and esito[b.RR_POOL] == 'messo'
    assert not any(b.RR_TARATURA in c and c.endswith('.tmp') for c in f.copiati)
    assert any(c.endswith(f'attesa_ds/{b.DS_TARATURA}.sh.tmp') for c in f.copiati)
    assert any(c.endswith(f'coda9b/{b.RR_POOL}.sh.tmp') for c in f.copiati)
    assert not any(re.search(r'\brm\b|\bkill\b|condor_rm', c) for c in f.comandi)


def test_manda_non_tocca_mai_la_coda_di_deepseek_direttamente(L14, tmp_path):
    (tmp_path / 'richieste').mkdir()
    f = FinteRecas(L14)
    f.recas.manda(tmp_path)
    assert not any('coda-ds4/' in c and c.endswith('.tmp') for c in f.copiati)       # va in attesa_ds, non davanti alla scala


# il pool: dal 9B a DeepSeek

def test_prepara_ds_manda_a_deepseek_solo_quelle_che_il_9b_non_scarta(L14, S9, tmp_path, monkeypatch):
    dati = [coppia(i, 'pool') for i in range(4)]
    prep = L14.Preparazione(L14.DomandaL14(VociFinte(), AttiFinti(), {}))
    (tmp_path / 'richieste').mkdir()
    prep.prepara(dati, tmp_path / 'richieste' / L14.Blocchi.RICHIESTE['rr_pool'], rr=True)
    ris = {dati[0]['id']: raccolta({'no': 3}, 3), dati[1]['id']: raccolta({'no': 2, 'forse': 1}, 3), dati[2]['id']: raccolta({'si': 3}, 3),
           dati[3]['id']: raccolta({}, 3)}
    f = tmp_path / 'rr.json'
    f.write_text(json.dumps(ris), encoding='utf-8')

    class DatiFinti:
        def pool(self):
            return dati

        def prove(self):
            return {}

    monkeypatch.setattr(L14, 'Dati', DatiFinti)
    monkeypatch.setattr(L14, 'Voci', VociFinte)
    monkeypatch.setattr(L14, 'Atti', AttiFinti)
    L14.comando_prepara_ds(type('A', (), {'uscita': str(tmp_path), 'rr': str(f)})())
    ids = {r['id'] for r in L14.jl(tmp_path / 'richieste' / L14.Blocchi.RICHIESTE['ds_pool'])}
    assert ids == {dati[1]['id'], dati[2]['id'], dati[3]['id']}
    assert all(r['letture'] == 5 for r in L14.jl(tmp_path / 'richieste' / L14.Blocchi.RICHIESTE['ds_pool']))


def test_le_richieste_scritte_sono_gzip_valide(L14, tmp_path):
    prep = L14.Preparazione(L14.DomandaL14(VociFinte(), AttiFinti(), {}))
    f = tmp_path / 'r.jsonl.gz'
    prep.prepara([coppia(1)], f)
    with gzip.open(f, 'rt', encoding='utf-8') as h:
        assert json.loads(h.readline())['testo'].startswith('Sei un giurista')
