"""S08 (05/10/2026): le coppie vicine. Ogni prova ha il caso che DEVE fallire se il passo manca o e' sbagliato.

- due citazioni lontane sulla stessa pagina danno DUE righe (Children of Austria p. 29, BMW p. 10): la perdita di S07 era la
  deduplica «stessa pagina»; con S08 le due righe diventano una coppia da leggere, mai una riga sola (prova sui dati veri,
  saltata se la fotografia e la scansione non ci sono);
- una coppia testo/nota (la nota e' chiamata dalla frase del testo) da' UNA citazione;
- i freni: una frase inventata o copiata dal prompt scarta la lettura;
- la decisione: lettori d'accordo e senza indizi contrari decidono; disaccordo o indizio forte contrario va al team.
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / 'tools'))
sys.path.insert(0, str(RADICE))
sys.dont_write_bytecode = True

import coppia_s08 as CS  # noqa: E402
import coppie_vicine as CV  # noqa: E402
import decidi_s08 as D  # noqa: E402
import leggi_coppia_l13 as L13  # noqa: E402

FOTO = RADICE / 'training' / 's08' / 'banca_2026-10-04_171547.json.gz'
SCANSIONE = RADICE / 'training' / 's08' / 'scansione_2026-10-04.json'

ATTO = ('---\ndocument_id: doc1\ncase_name: X v Y\ntipo_atto: ricorso\nlingue: English\n---\n'
        '<!-- page 1 -->\n'
        'The applicants rely on the reasoning of the Dutch court in Urgenda, which held that the State must cut emissions.15\n'
        ' \n'
        'A second paragraph about something else entirely, with enough words to be a different place in the document.\n'
        ' \n'
        '15 Urgenda Foundation v State of the Netherlands, Hoge Raad, 20 December 2019.\n'
        '16 See also the commentary by Smith on the Dutch judgment, 2020.\n')


def riga(testo, cod, caso='urgenda', nth=0, **kw):
    cs = -1
    for _ in range(nth + 1):
        cs = testo.index('Urgenda', cs + 1)
    return {'file': str(kw.pop('file')), 'char_start': cs, 'document_id': 'doc1', 'caso_citato': caso, 'codice': cod,
            'proposto_forma_trovata': 'Urgenda', 'proposto_rete': 'lessicale', 'proposto_pagina': 1, **kw}


@pytest.fixture()
def atto(tmp_path):
    f = tmp_path / 'doc1.md'
    f.write_text(ATTO, encoding='utf-8')
    return f


# ── due citazioni lontane: due righe ───────────────────────────────────────────────────────────────────────────

def test_due_righe_lontane_sulla_stessa_pagina_diventano_una_coppia(atto):
    """sintetico: due righe a 1.000+ caratteri sulla stessa pagina sono un legame a 5.000, non una riga sola"""
    a, b = riga(ATTO, 'U-1', file=atto), riga(ATTO, 'U-2', nth=1, file=atto)
    banca = {'1': a, '2': b}
    el = CV.elenco_coppie(banca, CV.SOGLIA_S08)
    assert len(el) == 1 and el[0]['stessa_pagina'] and el[0]['distanza'] > 100
    assert el[0]['id'] == 'U-1a-U-1b'


def test_deve_fallire_con_soglia_troppo_bassa(atto):
    """il caso che DEVE fallire: con la soglia di 200 caratteri la coppia a distanza maggiore non c'e' (la perdita di prima)"""
    a, b = riga(ATTO, 'U-1', file=atto), riga(ATTO, 'U-2', nth=1, file=atto)
    assert CV.elenco_coppie({'1': a, '2': b}, 50) == []


def test_soglia_scelta_e_5000():
    assert CV.SOGLIA_S08 == 5000


def test_scelta_della_soglia_dal_costo():
    tab = [{'soglia': 2000, 'legami_per_unire_in_piu': None}, {'soglia': 3000, 'legami_per_unire_in_piu': 8.4},
           {'soglia': 5000, 'legami_per_unire_in_piu': 22.7}, {'soglia': 8000, 'legami_per_unire_in_piu': 236.5}]
    t = CV.Taratura.__new__(CV.Taratura)
    assert t.scegli(tab) == 5000


@pytest.mark.skipif(not (FOTO.exists() and SCANSIONE.exists()), reason='fotografia e scansione S08 non presenti')
def test_children_of_austria_p29_e_bmw_p10_danno_due_righe():
    """sui dati veri: la seconda citazione sulla pagina (persa da S07) e' una riga nuova che con la riga viva forma una coppia"""
    banca = CV.carica_banca(FOTO)
    cl = CV.classifica_recuperate(json.load(open(SCANSIONE, encoding='utf-8'))['recuperate'], banca)
    nuove = [x for x in cl if x['esito'] == 'nuova']
    doc = lambda fine: next(r['document_id'] for r in banca.values() if r['document_id'].endswith(fine))  # noqa: E731
    attese = [('neubauer', doc('_6a3b'), 69272, 70664),       # Children of Austria, p. 29
              ('neubauer', doc('_d48d'), 57336, 58268)]       # BMW, p. 10
    assert CV.prova_due_lontane(attese, banca, nuove, CV.SOGLIA_S08) == []
    # deve fallire senza le righe nuove: la deduplica di prima perdeva la seconda citazione
    assert CV.prova_due_lontane(attese, banca, (), CV.SOGLIA_S08) != []


# ── una coppia testo/nota: una citazione ────────────────────────────────────────────────────────────────────

def coppia_testo_nota(atto):
    a = riga(ATTO, 'U-1', nth=0, file=atto)
    b = dict(riga(ATTO, 'U-2', nth=1, file=atto))
    return CS.Coppia(a, b, 'U-1__U-2')


def test_coppia_testo_nota_da_una(atto):
    c = coppia_testo_nota(atto)
    i = c.indizi()
    assert i['posizione_a'] == 'testo' and i['posizione_b'] == 'nota'
    assert i['nota_chiamata_dal_testo'] is True
    d = D.Decisore(solo_indizi=True).decidi(c)
    assert d.esito == 'una' and d.tenuta['codice'] == 'U-1' and d.esce['codice'] == 'U-2'


def test_nota_non_chiamata_non_e_un_indizio_forte(atto):
    """il caso che DEVE fallire: una nota che nessuna frase chiama non puo' dare «una» da sola"""
    testo = ATTO.replace('emissions.15', 'emissions.')
    f = atto.with_name('doc2.md')
    f.write_text(testo, encoding='utf-8')
    a, b = riga(testo, 'U-1', nth=0, file=f), riga(testo, 'U-2', nth=1, file=f)
    c = CS.Coppia(a, b, 'x')
    assert D.Decisore(solo_indizi=True).decidi(c).esito == 'team'


# ── la decisione con i lettori ───────────────────────────────────────────────────────────────────────────────────

def raccolta(voti, principale='A'):
    esito = max(voti, key=voti.get)
    return {'voti': voti, 'valide': sum(voti.values()),
            'letture': [{'valida': True, 'json': {'esito': esito, 'riga_principale': principale}}] * sum(voti.values())}


def test_lettori_concordi_una(atto):
    c = coppia_testo_nota(atto)
    d = D.Decisore().decidi(c, raccolta({'una': 5}), raccolta({'una': 3}))
    assert d.esito == 'una'


def test_disaccordo_va_al_team(atto):
    c = coppia_testo_nota(atto)
    d = D.Decisore().decidi(c, raccolta({'una': 5}), raccolta({'due': 3}))
    assert d.esito == 'team' and 'disaccordo' in d.motivo


def test_indizio_forte_contrario_va_al_team(atto):
    """i lettori dicono due ma la nota e' chiamata dalla frase del testo (indizio forte: una)"""
    c = coppia_testo_nota(atto)
    d = D.Decisore().decidi(c, raccolta({'due': 5}), raccolta({'due': 3}))
    assert d.esito == 'team' and 'indizio forte' in d.motivo


def test_lettura_scartata_dai_freni_va_al_team(atto):
    c = coppia_testo_nota(atto)
    d = D.Decisore().decidi(c, {'voti': {}, 'valide': 0, 'letture': []}, raccolta({'una': 3}))
    assert d.esito == 'team'


def test_incerto_va_al_team(atto):
    c = coppia_testo_nota(atto)
    d = D.Decisore().decidi(c, raccolta({'una': 2, 'due': 2, 'incerta': 1}), raccolta({'una': 3}))
    assert d.esito == 'team'


def test_due_lettori_dicono_due_senza_indizi_forti(atto):
    testo = ATTO.replace('emissions.15', 'emissions.')
    f = atto.with_name('doc3.md')
    f.write_text(testo, encoding='utf-8')
    c = CS.Coppia(riga(testo, 'U-1', nth=0, file=f), riga(testo, 'U-2', nth=1, file=f), 'x')
    assert D.Decisore().decidi(c, raccolta({'due': 4, 'una': 1}), raccolta({'due': 3})).esito == 'due'


def test_riga_scartata_dal_team_non_si_tiene(atto):
    c = coppia_testo_nota(atto)
    c.a['esito'] = 'scartata'
    t, e = D.Decisore().riga_tenuta(c)
    assert t['codice'] == 'U-2'


# ── i freni ──────────────────────────────────────────────────────────────────────────────────────────────────────

def test_prova_dei_freni_passa():
    assert L13.prova_freni() == []


def test_frase_inventata_scarta_la_lettura(atto):
    c = coppia_testo_nota(atto)
    con, puro = c.finestra()
    fr = L13.Freni(puro, L13.DomandaL13.testi_prompt())
    buona = {'esito': 'una', 'riga_principale': 'A', 'frase_A': 'The applicants rely on the reasoning of the Dutch court in Urgenda, '
             'which held that the State must cut emissions.', 'frase_B': '15 Urgenda Foundation v State of the Netherlands, Hoge Raad, 20 December 2019.'}
    assert fr.verifica(buona)[0]
    assert not fr.verifica({**buona, 'frase_A': buona['frase_A'] + ' and ordered the State to pay damages to everybody'})[0]


def test_finestra_ha_i_segni_ma_il_testo_puro_no(atto):
    con, puro = coppia_testo_nota(atto).finestra()
    assert '⟦A⟧' in con and '⟦B⟧' in con and '⟦' not in puro


def test_gli_indizi_non_stanno_nella_domanda(atto):
    t = L13.DomandaL13().testo(coppia_testo_nota(atto))
    for parola in ('stessa_nota', 'nota_chiamata_dal_testo', 'indizio', 'stessa_frase'):
        assert parola not in t.replace('nota_chiamata": "numero', '')


def test_raccolta_conta_solo_le_letture_valide(atto, tmp_path):
    c = coppia_testo_nota(atto)
    con, puro = c.finestra()
    rq = [{'id': 'p', 'puro': puro, 'letture': 2}]
    ok = {'esito': 'una', 'riga_principale': 'A', 'frase_A': 'The applicants rely on the reasoning of the Dutch court in Urgenda, which '
          'held that the State must cut emissions.', 'frase_B': '15 Urgenda Foundation v State of the Netherlands, Hoge Raad, 20 December 2019.'}
    cattiva = {**ok, 'frase_B': 'a sentence that does not appear anywhere in the filing at all, invented'}
    f = tmp_path / 'esiti.jsonl'
    f.write_text('\n'.join(json.dumps({'id': 'p', 'lettura': k, 'testo': json.dumps(j)}) for k, j in enumerate((ok, cattiva))), encoding='utf-8')
    r = L13.raccogli(rq, f)['p']
    assert r['voti'] == {'una': 1} and r['scartate'] == {"frase non trovata nell'atto": 1}


def test_leggi_scrive_una_riga_per_lettura_e_riprende(atto, tmp_path, monkeypatch):
    """il corridore con un modello finto: tre letture per coppia, FINITO, e alla seconda corsa non rifa' niente"""
    import types
    import chiamata_deepseek as CD
    import openai
    monkeypatch.setattr(openai, 'OpenAI', lambda **k: object())
    monkeypatch.setattr(CD, 'chiama', lambda *a, **k: {'testo': '{"esito": "una"}', 'ragionamento': 'x' * 10, 'token': 5, 'chiamata': {}})
    rq = tmp_path / 'r.jsonl.gz'
    with gzip.open(rq, 'wt', encoding='utf-8') as h:
        h.write(json.dumps({'id': 'p1', 'chiave': 'p1', 'testo': 'domanda', 'letture': 3, 'tetto': 8000}) + '\n')
    chiave = tmp_path / 'chiave'
    chiave.write_text('k')
    a = types.SimpleNamespace(richieste=str(rq), uscita=str(tmp_path / 'u.jsonl'), base_url='http://x', chiave_file=str(chiave),
                              modello='m', ragionamento='deepseek-high', contesto=65536, paralleli=2, minuti=0, tokenizer='')
    L13.leggi(a)
    assert len(L13.jl(a.uscita)) == 3
    L13.leggi(a)
    assert len(L13.jl(a.uscita)) == 3


# ── S08: il caricamento delle 376 righe nuove (tools/carica_righe_s08.py) ───────────────────────────────────

import carica_righe_s08 as CR  # noqa: E402
import recupero_s07 as R7  # noqa: E402


def riga_nuova(cs, caso='neubauer', doc='atto-x_aaaa', resta=True):
    """una riga nuova nel formato che `Nuove.riga` produce (le colonne del CSV descrittivo di S07)"""
    return {'case_id': 'caso-x_1', 'case_name': 'X v Y', 'giurisdizioni': 'Austria', 'document_id': doc,
            'tipo_atto': 'ricorso', 'tipo_atto_sabin': '', 'data': '2024-01-01', 'pagina': 29, 'rete': 'descrittiva',
            'forma_trovata': 'descrizione: R: Klimabeschluss', 'citazione_testuale': 'una frase', 'finestra_pagina': 'pagina',
            'file': 'markdown/inesistente/atto.md', 'char_start': cs, 'url_documento': 'https://x', 'codebook_versione': '0.5',
            'regola_descrittiva': 'R', 'testo_trovato': 'Klimabeschluss', 'posizione_auto': 'corpo', 'caso': caso,
            'chiave': f'S08-{caso}-{doc[-8:]}-{cs}', 'c04_resta': resta, 'c04_motivo': 'passa' if resta else 'data'}


def banca_finta():
    return {'neubauer__atto-x_aaaa__70664': {'caso_citato': 'neubauer', 'document_id': 'atto-x_aaaa', 'char_start': 70664,
                                              'codice': 'NEU-0121', 'proposto_rete': 'lessicale', 'proposto_pagina': 29,
                                              'assegnato_a': 'u1'},
            'neubauer__altro_bbbb__100': {'caso_citato': 'neubauer', 'document_id': 'altro_bbbb', 'char_start': 100,
                                          'codice': 'NEU-0300', 'proposto_rete': 'lessicale', 'proposto_pagina': 1,
                                          'assegnato_a': 'u2'}}


def test_riga_s08_ha_la_forma_di_una_riga_descrittiva_di_s07():
    """stessi campi di `recupero_s07.documenti` per una riga descrittiva; cambiano solo causa e provenienza"""
    b = banca_finta()
    r = riga_nuova(69272)
    s8 = CR.Caricatore(b).documenti([r])
    esist = list(b.items())
    s7 = R7.documenti('neubauer', [{'caso': 'neubauer', 'id': CR.Caricatore.id_di(r), 'causa': 'descrittiva',
                                    'riga': dict(r)}], esist, set())
    d8, d7 = next(iter(s8.values())), next(iter(s7.values()))
    assert set(d7) - set(d8) == {'causa_s07'}
    assert set(d8) - set(d7) == {'causa_s08', 'c04_resta', 'c04_motivo', 's08_vicina_codice', 's08_vicina_id',
                                 's08_vicina_distanza'}
    assert d8['proposto_rete'] == 'descrittiva' and d8['trovata_per_descrizione'] is True
    assert d8['provenienza']['estrazione'] == 'S08' and d8['causa_s08'] == 'S08_stessa_pagina'
    assert d8['esecuzione_id'].endswith('-S08') and d8['corroborazione'] == 'descrizione'
    assert d8['codice'] == 'NEU-0301' and d8['esito'] is None
    assert d8['assegnato_a_in_attesa'] in ('u1', 'u2') and 'assegnato_a' not in d8


def test_la_riga_viva_piu_vicina_entro_5000_forma_la_coppia():
    c = CR.Caricatore(banca_finta())
    assert c.vicina(riga_nuova(69272)) == ('NEU-0121', 'neubauer__atto-x_aaaa__70664', 1392)
    assert c.vicina(riga_nuova(60000)) is None                       # oltre 5.000 caratteri: sola
    assert c.vicina(riga_nuova(69272, doc='altro_bbbb')) is None     # un altro atto non conta


def test_c04_e_un_indizio_non_un_esclusione():
    """una riga che C04 scarterebbe (Children of Austria p. 29) si carica lo stesso, con il suo motivo scritto"""
    d = next(iter(CR.Caricatore(banca_finta()).documenti([riga_nuova(69272, resta=False)]).values()))
    assert d['c04_resta'] is False and d['c04_motivo'] == 'data'


def test_nessun_id_doppio_e_codici_progressivi():
    c = CR.Caricatore(banca_finta())
    docs = c.documenti([riga_nuova(10), riga_nuova(20), riga_nuova(30)])
    assert len(docs) == 3
    assert sorted(d['codice'] for d in docs.values()) == ['NEU-0301', 'NEU-0302', 'NEU-0303']
    with pytest.raises(ValueError):
        c.documenti([riga_nuova(70664)])          # l'id c'e' gia' in banca: la scrittura si rifiuta


def test_verifiche_dicono_fallita_se_un_id_c_e_gia():
    c = CR.Caricatore(banca_finta())
    docs = c.documenti([riga_nuova(10)])
    righe = [riga_nuova(10)]
    v = CR.verifiche(docs, righe, {'x'})
    assert not v[0][1]                          # id gia' in banca
    assert not all(x[1] for x in CR.verifiche(docs, righe, set()))   # mancano i due casi di prova


@pytest.mark.skipif(not CR.TSV.exists(), reason='TSV S08 non presente')
def test_il_tsv_ha_376_nuove_e_chiavi_uniche():
    n = CR.Nuove().elenco()
    assert len(n) == 376 and len({r['chiave'] for r in n}) == 376
