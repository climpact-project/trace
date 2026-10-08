"""The four views of Corpus > Coordination > Tools built on the Mac (tools/stato_viste.py, tools/stato_corpus.py):
data changes log, release state, document health, ReCaS jobs. Everything on fake data in ``tmp_path``; nothing is
written to Firestore and ReCaS is never called."""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
import stato_corpus as SC  # noqa: E402
import stato_viste as V  # noqa: E402


def _radice(tmp_path: Path) -> Path:
    (tmp_path / 'versioni').mkdir()
    (tmp_path / 'versioni' / 'registro.json').write_text(json.dumps([
        {'codice': 'R11', 'nome': 'Proposals by majority vote of five readings'},
        {'codice': 'C03', 'nome': 'Body text and footnote, and translations of the same filing, counted once'},
        {'codice': 'S07', 'nome': 'Name search: footnote-aware grouping, descriptive references, same-page dedup'},
    ]))
    (tmp_path / 'versioni' / 'BOZZA-controlli-C01-C07.json').write_text(json.dumps([{'codice': 'C01', 'nome': 'Copies in the same case counted once'}]))
    g = tmp_path / 'giornale' / 'Mac'
    g.mkdir(parents=True)
    voci = [
        # cinque casi caricati con R11 in due minuti: un'operazione sola
        *[{'tipo': 'fine', 'strumento': 'carica_ripresa.py', 'argomenti': ['--caso', c, '--composizione', 'R11', '--etichetta', e, '--scrivi'],
           'inizio': f'2026-10-07T05:1{i}:00+02:00', 'fine': f'2026-10-07T05:1{i}:30+02:00',
           'firestore': {'corpus_rows': {'set': 0, 'update': 10 + i, 'delete': 0, 'campi': ['proposto_principi']}}, 'esito': 'ok'}
          for i, (c, e) in enumerate([('urgenda', 's07'), ('neubauer', 'P05s07')])],
        # una prova a secco: il giornale conta, ma senza --scrivi non e' una scrittura
        {'tipo': 'fine', 'strumento': 'escludi_righe.py', 'argomenti': ['--da-file', 'x_C01.tsv'], 'inizio': '2026-10-04T11:56:00+02:00',
         'firestore': {'corpus_rows': {'set': 0, 'update': 69, 'delete': 0, 'campi': []}}},
        {'tipo': 'fine', 'strumento': 'escludi_righe.py', 'argomenti': ['--da-file', 'training/x_C01.tsv', '--da', "si' del PI del 04/10", '--scrivi'],
         'inizio': '2026-10-04T15:18:00+02:00', 'fine': '2026-10-04T15:19:00+02:00',
         'firestore': {'corpus_rows': {'set': 0, 'update': 152, 'delete': 0, 'campi': ['proposto_rete']}}, 'esito': 'ok'},
        {'tipo': 'fine', 'strumento': 'unisci_c03.py', 'argomenti': ['--vivo', '--scrivi'], 'inizio': '2026-10-05T07:01:00+02:00',
         'firestore': {'corpus_rows': {'set': 0, 'update': 1311, 'delete': 0, 'campi': []}}, 'esito': 'ok'},
        {'tipo': 'fine', 'strumento': 'prova_giornale.py', 'argomenti': [], 'inizio': '2026-10-02T16:52:00+02:00',
         'firestore': {'corpus_rows': {'set': 0, 'update': 1, 'delete': 0, 'campi': []}}},
        {'tipo': 'fine', 'strumento': 'cerca.py', 'argomenti': [], 'inizio': '2026-10-03T10:00:00+02:00', 'firestore': {}},
    ]
    (g / '2026-10.jsonl').write_text('\n'.join(json.dumps(v) for v in voci) + '\n')
    r = tmp_path / 'giornale' / 'ricostruito'
    r.mkdir()
    (r / '2026-10-01_02.jsonl').write_text(json.dumps({
        'tipo': 'ricostruita', 'inizio': '2026-10-01T04:06:00Z', 'esito': 'ok', 'strumento': 'carica_ripresa.py',
        'comando': 'cd ~/sabin-corpus && .venv/bin/python tools/carica_ripresa.py --caso urgenda --principi-da-l04 --scrivi 2>&1 | tail'}) + '\n')
    e = tmp_path / 'training' / 'esclusioni'
    e.mkdir(parents=True)
    with gzip.open(e / 'prima_escludi_righe_urgenda_2026-10-04_151830.json.gz', 'wt') as f:
        json.dump({'righe': {}}, f)
    with gzip.open(e / 'prima_escludi_righe_urgenda_2026-10-01_101010.json.gz', 'wt') as f:   # di un altro giorno: non c'entra
        json.dump({'righe': {}}, f)
    return tmp_path


def test_registro(tmp_path: Path) -> None:
    rad = _radice(tmp_path)
    d = V.vista_registro(rad)
    ops = {(o['strumento'], o['giorno']): o for o in d['voci']}
    assert d['riassunto']['operazioni'] == 4                      # R11, C01, C03, la ricostruita; non la prova ne' la prova a secco
    r11 = ops[('carica_ripresa.py', '2026-10-07')]
    assert r11['righe'] == 21 and r11['esecuzioni'] == 2
    assert [c['caso'] for c in r11['casi']] == ['urgenda', 'neubauer']
    assert r11['regole'][0] == {'codice': 'R11', 'nome': 'Proposals by majority vote of five readings'}
    assert any(x['codice'] == 'S07' for x in r11['regole'])
    assert r11['approvazione']['parole'].startswith('S07')        # dalla tabella, con la sua fonte
    assert 'NOTTE-2026-10-06.md' in r11['approvazione']['fonte']
    c01 = ops[('escludi_righe.py', '2026-10-04')]
    assert c01['righe'] == 152 and c01['regole'] == [{'codice': 'C01', 'nome': 'Copies in the same case counted once'}]
    assert c01['approvazione'] == {'parole': "si' del PI del 04/10", 'fonte': 'argument --da recorded in the operations journal'}
    assert [c['percorso'] for c in c01['copie']] == ['training/esclusioni/prima_escludi_righe_urgenda_2026-10-04_151830.json.gz']
    assert 'rimetti_righe.py' in c01['annulla']
    assert ops[('unisci_c03.py', '2026-10-05')]['approvazione'] is not None
    ric = ops[('carica_ripresa.py', '2026-10-01')]
    assert ric['righe'] is None and ric['fonte'] == 'reconstructed' and ric['regole'][0]['codice'] == 'R05'
    assert ric['inizio'] == '2026-10-01T06:06'                    # ora di Roma
    assert d['riassunto']['senza_conto'] == 1
    assert [o['inizio'] for o in d['voci']] == sorted((o['inizio'] for o in d['voci']), reverse=True)
    assert len({o['id'] for o in d['voci']}) == len(d['voci'])


def test_approvazione_mai_inventata() -> None:
    op = {'strumento': 'carica_ripresa.py', 'giorno': '2026-10-04', '_args': [['--composizione', 'R12', '--scrivi']], '_chiavi': {'R12'}}
    assert V.approvazione_di(op) is None
    op['_args'] = [['--da', 'misura del 04/10']]                 # un --da che non parla del PI non e' un'approvazione
    assert V.approvazione_di(op) is None


USCITA_AGGIORNAMENTO = """ATTESA s08         [fuori] S08 deciso e caricato in corpus_rows (dopo le coppie di DeepSeek)
         manca training/s08/CARICATO.ok: S08 non ancora caricato (serve il si' del PI per scrivere)
OK    dati        [locale] dataset congelato: citazioni, giudizi del team, README, SHA256SUMS
         7,800 citazioni; impronte sbagliate: nessuna; giudizi del team: si
ROSSO  sito        [verifica] numeri del sito aggiornati e pubblicati (ramo online)
         segni «aggiornare al 10/10» rimasti: 12; numeri vecchi: ['traceContent.js: 5,861']; numero finale sul sito: NO
ROSSO  documento   [verifica] §63.103 e §63.104 uniti nel documento unico
         paragrafi da unire ancora fuori: ['63.103', '63.104']
ROSSO  coerenza    [verifica] stesso numero di citazioni ovunque, nessun numero vecchio
         7,800 citazioni; manca in: ['GitHub (README)', 'sito']; vecchi: ['sito: 5,861', 'sito: 16.791']

1 di 5 passi a posto.
"""


def test_rilascio() -> None:
    d = V.vista_rilascio(USCITA_AGGIORNAMENTO, 1)
    assert d['riassunto'] == {'a_posto': 1, 'totale': 5, 'pronto': False}
    assert d['numero_finale'] == 7800
    passi = {p['chiave']: p for p in d['passi']}
    assert passi['s08']['attesa'] and not passi['s08']['ok']
    assert passi['dati']['ok'] and passi['dati']['spiegazione'] == '7,800 citations; wrong fingerprints: none; team judgments: yes.'
    assert passi['documento']['spiegazione'] == 'Sections still to merge: §63.103, §63.104.'
    assert 'TRACE page of the site (online branch): 5,861' in passi['coerenza']['spiegazione']
    assert not any(p['spiegazione_in_italiano'] for p in d['passi'])
    luoghi = {x['luogo']: x for x in d['luoghi']}
    assert luoghi['Technical report']['presente'] and not luoghi['GitHub README']['presente']
    assert luoghi['TRACE page of the site (online branch)']['vecchi'] == ['5,861', '16.791']


def test_salute(tmp_path: Path) -> None:
    (tmp_path / 'training' / 'ocr').mkdir(parents=True)
    (tmp_path / 'training' / 'da_ocr_documenti.json').write_text(json.dumps({'a_1': {'rotte': 3, 'pagine': 10}, 'b_2': {'rotte': 2, 'pagine': 4}}))
    (tmp_path / 'training' / 'ocr' / 'pagine_sostituite.json').write_text(json.dumps({'a_1#p1': 'x', 'a_1#p2': 'y', 'a_1#p3': 'z', 'b_2#p1': 'w'}))
    esiti = [{'c': 'URG-1', 'doc': 'a_1', 'esito': 'frase', 'pag': 1, 'num': 10, 'lung': 900},
             {'c': 'URG-2', 'doc': 'a_1', 'esito': 'NON TROVATA', 'pag': 2, 'num': 10, 'lung': 0},
             {'c': 'NEU-3', 'doc': 'b_2', 'esito': 'pdf mancante'}]
    righe = {'URG-1': {'codice': 'URG-1', 'id': 'urgenda__a_1__1', 'file_pdf': 'documents/a.pdf'},
             'URG-2': {'codice': 'URG-2', 'id': 'urgenda__a_1__2', 'file_pdf': 'documents/a.ocr.pdf', 'file_pdf_originale': 'documents/a.pdf', 'proposto_rete': 'esclusa'},
             'NEU-3': {'codice': 'NEU-3', 'id': 'neubauer__b_2__3', 'caso_citato': 'neubauer', 'file_pdf': 'documents/b.pdf'}}
    d = V.vista_salute(esiti, righe, '2026-10-07T11:00', tmp_path)
    assert d['riassunto']['righe'] == 3 and d['riassunto']['non_accese'] == 1 and d['riassunto']['pdf_mancanti'] == 1
    assert d['non_accese'][0]['codice'] == 'URG-2' and d['non_accese'][0]['esclusa'] and d['non_accese'][0]['caso'] == 'urgenda'
    assert d['pdf_mancanti'][0]['file'] == 'documents/b.pdf'
    assert d['copie_ocr'] == [{'codice': 'URG-2', 'caso': 'urgenda', 'documento': '', 'file': 'a.ocr.pdf', 'originale': 'a.pdf', 'quando': ''}]
    assert d['pagine_vuote'][0]['codice'] == 'URG-2'
    assert d['pagine_rifatte']['sostituite'] == 4 and [x['documento'] for x in d['pagine_rifatte']['restano']] == ['b_2']


USCITA_RECAS = """@@condor
1920306 0 2 4 slot1_1@wn-gpu-3-7-34.recas.ba.infn.it /lustrehome/climpact/trace/chat/avvio6.sh undefined 1791220521 1791267324 1791267324
1921882 0 1 4 undefined /lustrehome/climpact/trace/chat/avvio6.sh undefined 1791268573 1791354463 1791354473
1939481 0 2 2 slot1_2@wn-gpu-3-5-33.recas.ba.infn.it /lustrehome/climpact/trace/chat/presidio.sh 2 1791362769 1791362770 1791362770
@@ora
1791366370
@@coda coda-gpu2
@@fatti
@@presidi
07/10 10:46 avvio wn-gpu-3-5-33 lavoro x GPU=a,b
@@coda coda-ds4
b_s08_coppie_l13.sh
@@fatti
b_s08_coppie_l13.sh
@@ds ricambio_lungo_1920306.out
fine b_s08_coppie_l13 Wed Oct  7 11:13:33 CEST 2026 esito 0
inizio b_s08_coppie_l13 (coda-ds4) Wed Oct  7 11:13:43 CEST 2026
@@s08 b_s08_coppie_l13.log
  125/9261 [399s]
@@fine
"""


def test_recas() -> None:
    d = V.vista_recas(USCITA_RECAS)
    assert d['riassunto'] == {'lavori': 3, 'in_corso': 2, 'gpu_in_uso': 6, 'gpu_in_attesa': 4, 'script_in_attesa': 1}
    l = {x['id']: x for x in d['lavori']}
    assert l['1920306.0']['ore_in_corso'] == 27.5 and l['1920306.0']['ore_al_limite'] == 22.5
    assert l['1939481.0']['ruolo'].endswith('coda-gpu2') and l['1939481.0']['nodo'] == 'wn-gpu-3-5-33'
    assert l['1921882.0']['stato'] == 'idle' and l['1921882.0']['in_coda_da_ore'] == 27.2
    assert d['deepseek'][0]['in_corso']['script'] == 'b_s08_coppie_l13'
    assert d['avanzamenti'] == [{'tipo': 'S08', 'file': 'b_s08_coppie_l13.log', 'fatte': 125, 'totale': 9261}]
    assert 'condor_rm' not in V.COMANDO_RECAS and 'condor_submit' not in V.COMANDO_RECAS and ' rm ' not in V.COMANDO_RECAS


def test_documenti_e_parti() -> None:
    piccolo, parti = SC.documenti('recas', {'riassunto': {'lavori': 1}, 'lavori': []}, 't')
    assert parti == [] and piccolo['parti'] == 0 and piccolo['dati']['riassunto'] == {'lavori': 1}
    dati = {'riassunto': {'operazioni': 300}, 'voci': [{'id': i, 'testo': 'x' * 1000} for i in range(300)]}
    testa, parti = SC.documenti('registro', dati, 't', tetto=60_000)
    assert testa['parti'] == len(parti) > 1 and testa['parti_chiave'] == 'voci' and 'voci' not in testa['dati']
    assert [v['id'] for p in parti for v in p['voci']] == list(range(300))
    assert all(SC._byte(p) <= 61_000 for p in parti)


def test_prova_non_scrive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(SC, 'CARTELLA', tmp_path)
    monkeypatch.setitem(SC.COSTRUTTORI, 'recas', lambda: V.vista_recas(USCITA_RECAS))
    scritto = []
    monkeypatch.setattr(SC, 'scrivi', lambda *a: scritto.append(a))
    assert SC.main(['--vista', 'recas']) == 0
    assert scritto == [] and (tmp_path / 'recas.json').exists() and not (tmp_path / 'ultimo.json').exists()
    assert SC.main(['--vista', 'recas', '--scrivi']) == 0 and len(scritto) == 1
    assert SC.main(['--vista', 'recas', '--scrivi', '--ciclo']) == 0 and len(scritto) == 1   # intervallo non passato
