"""Le sintesi di TRACE 0.1 e il sigillo di verifica (07/10/2026, decisioni del PI).

- ogni [[chiave]] dei due testi delle sintesi (italiano in build-sintesi.mjs, inglese in testo-sintesi-en.mjs) si risolve
  dai fatti (numeri-sintesi.mjs): nessuna cifra scritta a mano, nessuna chiave senza valore;
- i testi delle sintesi e del resoconto non portano le parole vietate (giurista, avvocati, «to be confirmed by»);
- il sigillo: un codice solo senza chiave vale per il PDF principale, un codice di forma sbagliata o una chiave
  sconosciuta fermano la build;
- il README del dataset conta le righe con le cinque letture come la colonna five_readings del CSV.
Servono node e i file letti da fatti.mjs (il dataset in zenodo-dati/, fuori da git): se mancano, la prova si salta."""
import csv
import json
import re
import subprocess
from pathlib import Path

import pytest

QUI = Path(__file__).resolve().parent.parent
T01 = QUI / 'pubblicazione' / 'trace-0.1'
REPORT = T01 / 'report'
DATI = T01 / 'zenodo-dati'
pytestmark = pytest.mark.skipif(not (DATI / 'trace-0.1-citations.csv').exists(), reason='dataset di TRACE 0.1 non generato (zenodo-dati/ e\' fuori da git)')


def node(codice, **env):
    import os
    r = subprocess.run(['node', '--input-type=module', '-e', codice], capture_output=True, text=True, cwd=REPORT, env={**os.environ, **env}, timeout=300)
    return r


def test_ogni_chiave_delle_sintesi_ha_un_valore():
    chiavi = {'it': sorted(set(re.findall(r'\[\[([a-z0-9.-]+)\]\]', (REPORT / 'build-sintesi.mjs').read_text()))),
              'en': sorted(set(re.findall(r'\[\[([a-z0-9.-]+)\]\]', (REPORT / 'testo-sintesi-en.mjs').read_text())))}
    tutte = sorted(set(chiavi['it']) | set(chiavi['en']))
    # la chiave dei DOI del livello 3 e quelle di S08 finale possono mancare per scelta (indice non ancora depositato, S08 non finale)
    opzionali = {'doi.pub', 'doi.ris', 'n.s08dec', 'n.s08una', 'n.s08due', 'n.s08team'}
    codice = f"""
import {{ calcola }} from './fatti.mjs';
import {{ numeriSintesi }} from './numeri-sintesi.mjs';
const S = calcola({{ avviso: () => {{}} }});
const V = numeriSintesi(S, () => {{}});
const manca = {json.dumps(tutte)}.filter((k) => !V[k]);
console.log(JSON.stringify(manca));
"""
    r = node(codice)
    assert r.returncode == 0, r.stderr[-1500:]
    manca = [k for k in json.loads(r.stdout.strip().splitlines()[-1]) if k not in opzionali]
    assert manca == [], f'chiavi senza valore: {manca}'
    a_mano = [k for k in tutte if re.match(r'\d', k)]
    assert a_mano == [], f'cifre scritte a mano nel testo delle sintesi: {a_mano}'


def test_niente_parole_vietate_nei_testi():
    vietate = re.compile(r'jurist|lawyer|giurist|avvocat|to be confirmed by|\bDraft\b|·', re.I)
    for nome in ('build-sintesi.mjs', 'testo-sintesi-en.mjs', 'fatti.mjs', 'contenuto.js'):
        testo = (REPORT / nome).read_text()
        # le righe di commento del codice possono nominarle (le regole del PI): solo il testo dei documenti conta
        righe = [r for r in testo.splitlines() if not r.lstrip().startswith(('//', '*', '/*')) and not re.search(r'forbidden|vietat', r)]
        trovate = [r.strip()[:90] for r in righe if vietate.search(r)]
        assert trovate == [], f'{nome}: {trovate}'


def test_sigillo_codici():
    codice = """
import { createRequire } from 'node:module';
import { codiciDaUsare } from './sigillo.mjs';
const DV = { normalizzaCodice: (x) => String(x).toUpperCase().replace(/[^A-Z0-9]/g, ''), formaValida: (c) => /^[A-Z0-9]{12}$/.test(c), VERIFY_LENGTH: 12 };
const prova = (v, def = 'report-print') => { process.env.TRACE_VERIFICA = v; try { return JSON.stringify(codiciDaUsare('/nonesiste', DV, def)); } catch (e) { return 'ERRORE ' + e.message.slice(0, 40); } };
console.log(prova('abcd-efgh-2345'));
console.log(prova('summary=ABCDEFGH2345, report=ZZZZZZZZZZZZ'));
console.log(prova('XYZ'));
console.log(prova('nonesiste=ABCDEFGH2345'));
console.log(prova(''));
"""
    r = node(codice)
    assert r.returncode == 0, r.stderr[-1500:]
    righe = r.stdout.strip().splitlines()
    assert json.loads(righe[0]) == {'report-print': 'ABCDEFGH2345'}
    assert json.loads(righe[1]) == {'summary': 'ABCDEFGH2345', 'report': 'ZZZZZZZZZZZZ'}
    assert righe[2].startswith('ERRORE') and righe[3].startswith('ERRORE')
    assert json.loads(righe[4]) == {}


def test_readme_dati_conta_le_cinque_letture_come_il_csv():
    righe = list(csv.DictReader(open(DATI / 'trace-0.1-citations.csv', encoding='utf-8')))
    assert 'five_readings' in righe[0] and 'reference_kind' in righe[0]
    si = sum(1 for r in righe if r['five_readings'] == 'yes')
    readme = (DATI / 'README.md').read_text()
    assert f'{si:,} of {len(righe):,} rows' in readme
    assert set(r['five_readings'] for r in righe) <= {'yes', 'no'}
    assert set(r['reference_kind'] for r in righe) <= {'named', 'descriptive'}
