"""Lo spazio di lavoro dei casi citati (tools/casi_in_corpus.py): lo stato iniziale dai file della pipeline, la scrittura con la copia
intera prima, il congelamento che non tocca cited-cases/ (07/10/2026, opzione A del PI)."""
import copy, gzip, hashlib, json, pathlib, sys, types
import pytest

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI / 'tools'))
import casi_in_corpus as C  # noqa: E402
import casi_registro as CR  # noqa: E402

@pytest.fixture(scope='module')
def stato():
    # i titoli inglesi vengono da principi.js della piattaforma (CASI_PRINCIPI_JS o ~/climpact-drp); se non c'e', dal file
    return C.stato_iniziale()


def test_i_sei_casi_nell_ordine_del_registro(stato):
    # l'ordine e' quello della vista «Paragraph maps» (idh prima di cig), gli stessi sei casi del registro
    assert [c['slug'] for c in stato['casi']] == C.CASI and sorted(C.CASI) == sorted(CR.CASI)


def test_i_conti_sono_quelli_dei_file(stato):
    k = {c['slug']: c['conti'] for c in stato['casi']}
    assert {s: x['principi'] for s, x in k.items()} == {'urgenda': 5, 'neubauer': 7, 'future-generations': 5, 'klimaseniorinnen': 7, 'idh-oc-32-25': 8, 'cig-parere-clima': 7}
    assert k['urgenda']['voci_mappa'] == 176 and k['urgenda']['voci_con_sostegno'] == 102
    assert k['urgenda']['passaggi'] == 34
    # 08/10/2026: la mappa e' quella che la pipeline legge (sonde_P05 per Neubauer e Future Generations), non piu' il campo
    # `sonde` della serie di prima: ogni principio in uso ha voci, nessun id della mappa fuori serie, nessun «prepara» vecchio
    for s in ('neubauer', 'future-generations'):
        assert k[s]['campo_mappa'] == 'sonde_P05'
        assert k[s]['id_della_mappa_fuori_serie'] == [] and k[s]['principi_senza_voce_nella_mappa'] == []
        assert k[s]['voci_che_preparano'] == 0 and k[s]['prepara_non_portate'] == 45
    assert k['neubauer']['voci_con_sostegno'] == 94 and k['future-generations']['voci_con_sostegno'] == 33
    # gli altri tre restano sul campo `sonde`, come prima; dall'8/10/2026 la mappa della CIG ha sonde_P09 (approvata dal PI)
    assert k['klimaseniorinnen']['id_della_mappa_fuori_serie'] == [] and k['urgenda']['voci_che_preparano'] == 69
    assert k['cig-parere-clima']['campo_mappa'] == 'sonde_P09' and not k['cig-parere-clima']['avviso_mappa']


def test_ogni_principio_porta_testo_alla_lettera_e_paragrafi(stato):
    for c in stato['casi']:
        for p in c['principi']:
            assert p['descrizione'] and p['passaggi'] and p['paragrafi'], (c['slug'], p['id'])
            assert p['passaggi'][0]['tipo'] == 'canonical'
            assert p['titolo'] == p['titolo_iniziale']
            assert '\n' not in p['descrizione']


def test_le_sonde_sono_quelle_in_uso(stato):
    assert {c['slug']: c['file_sonde'] for c in stato['casi']}['neubauer'] == 'cited-cases/neubauer-P05.yaml'
    assert {c['slug']: c['file_sonde'] for c in stato['casi']}['urgenda'] == 'cited-cases/urgenda.yaml'


def test_la_mappa_e_senza_revisione_e_senza_sintesi(stato):
    t = json.dumps(stato, ensure_ascii=False)
    assert '"review"' not in t and 'sintesi' not in t
    for c in stato['casi']:
        assert [v['ordine'] for v in c['mappa']] == list(range(len(c['mappa'])))


def test_lo_stato_si_rifa_identico(stato):
    ancora = C.stato_iniziale()
    assert json.dumps(ancora, sort_keys=True) == json.dumps(stato, sort_keys=True)


# ── un Firestore finto con le sottoraccolte ──────────────────────────────────────────────────────────────────────────
class Doc:
    def __init__(self, store, path):
        self.store, self.path = store, path
        self.id = path.split('/')[-1]
        self.reference = self

    def to_dict(self):
        return copy.deepcopy(self.store.get(self.path))

    @property
    def exists(self):
        return self.path in self.store

    def get(self):
        return self

    def collection(self, nome):
        return Col(self.store, f'{self.path}/{nome}')


class Col:
    def __init__(self, store, path):
        self.store, self.path = store, path

    def document(self, i):
        return Doc(self.store, f'{self.path}/{i}')

    def stream(self):
        n = self.path.count('/') + 1
        return [Doc(self.store, p) for p in sorted(self.store) if p.startswith(self.path + '/') and p.count('/') == n]


class Lotto:
    def __init__(self, db):
        self.db, self.ops = db, []

    def set(self, rif, dati, merge=False):
        self.ops.append((rif.path, dati, merge))

    def delete(self, rif):
        self.ops.append((rif.path, None, False))

    def commit(self):
        for p, d, merge in self.ops:
            if d is None:
                self.db.store.pop(p, None)
            elif merge:
                self.db.store[p] = {**self.db.store.get(p, {}), **copy.deepcopy(d)}
            else:
                self.db.store[p] = copy.deepcopy(d)
        self.db.commiti += 1
        self.ops = []


class Db:
    def __init__(self, store=None):
        self.store, self.commiti = store if store is not None else {}, 0

    def collection(self, nome):
        return Col(self.store, nome)

    def batch(self):
        return Lotto(self)


FS = types.SimpleNamespace(SERVER_TIMESTAMP='ORA')


def test_scrivi_fa_la_copia_prima_e_scrive_tutto(stato, tmp_path, monkeypatch):
    monkeypatch.setattr(C, 'USCITA', tmp_path)
    db = Db({'corpus_casi/urgenda': {'slug': 'urgenda', 'gia': 'qui'}})
    scritto = C.scrivi(stato, db, FS) or db.store
    # la copia intera c'e', si rilegge, e contiene quello che c'era prima
    copie = list(tmp_path.glob('prima_*.json.gz'))
    assert len(copie) == 1
    prima = json.loads(gzip.open(copie[0], 'rt', encoding='utf-8').read())
    assert prima['urgenda']['_'] == {'slug': 'urgenda', 'gia': 'qui'}
    # un caso che esisteva non si tocca; gli altri cinque si scrivono
    assert db.store['corpus_casi/urgenda'] == {'slug': 'urgenda', 'gia': 'qui'}
    assert not [p for p in db.store if p.startswith('corpus_casi/urgenda/')]
    neu = caso = next(c for c in stato['casi'] if c['slug'] == 'neubauer')
    assert db.store['corpus_casi/neubauer']['slug'] == 'neubauer'
    assert len([p for p in db.store if p.startswith('corpus_casi/neubauer/principi/')]) == len(neu['principi'])
    assert len([p for p in db.store if p.startswith('corpus_casi/neubauer/mappa/')]) == len(neu['mappa'])
    d = db.store['corpus_casi/neubauer/principi/neubauer.liberta_intertemporale']
    assert d['rev'] == 1 and d['modificato_da']['uid'] == 'pipeline' and d['modificato_il'] == 'ORA'
    assert db.store['corpus_casi/neubauer/mappa/n0000']['rev'] == 1
    # nessuna voce di storia: la storia comincia dalla prima modifica (revisione 2)
    assert not [p for p in db.store if '/modifiche/' in p]
    assert db.commiti >= 5
    del scritto


# ── congelare ────────────────────────────────────────────────────────────────────────────────────────────────────────
def stato_firestore(stato, slug, modifica=None):
    c = copy.deepcopy(next(x for x in stato['casi'] if x['slug'] == slug))
    ps = [{**p, 'rev': 1} for p in c['principi']]
    mp = [{**v, 'rev': 1} for v in c['mappa']]
    if modifica:
        modifica(ps, mp)
    return {'principi': ps, 'mappa': mp, 'modifiche': [{'chi': {'uid': 'u1', 'nome': 'Maria Dicosola'}, 'campo': 'x'}]}


def registro():
    return json.load(open(QUI / 'versioni' / 'registro.json'))


def mtime_cited():
    return {str(p): p.stat().st_mtime_ns for p in (QUI / 'cited-cases').glob('*.yaml')}


def test_congelare_senza_modifiche_non_fa_niente(stato, tmp_path):
    e = C.congela('neubauer', stato_firestore(stato, 'neubauer'), registro(), applica=True, dest=tmp_path)
    assert e.get('nessun_cambiamento') and e['file'] == []
    assert not list(tmp_path.rglob('*.yaml'))


def test_a_secco_non_scrive_niente_e_non_tocca_cited_cases(stato, tmp_path):
    prima = mtime_cited()

    def m(ps, mp):
        ps[0]['descrizione'] = ps[0]['descrizione'] + ' And one more clause.'
        mp[5]['supported'] = [ps[0]['id']]
    e = C.congela('neubauer', stato_firestore(stato, 'neubauer', m), registro(), applica=False, dest=tmp_path)
    # R18 e' la mappa P09 della CIG (08/10/2026): la prossima mappa e' R19
    assert e['file'] == ['versioni/P10/neubauer-P10.yaml', 'versioni/R19/neubauer-mappa-paragrafi.yaml']
    assert not list(tmp_path.rglob('*'))
    assert mtime_cited() == prima


def test_applica_scrive_versioni_nuove_con_il_loro_codice_e_la_proposta(stato, tmp_path):
    import yaml
    prima = mtime_cited()
    base = yaml.safe_load(open(QUI / 'cited-cases' / 'neubauer-P05.yaml', encoding='utf-8'))

    def m(ps, mp):
        ps[1]['descrizione'] = 'A new description of the pathway after 2030.'
        ps[1]['titolo'] = 'A better English title'
        ps[2]['passaggi'] = ps[2]['passaggi'] + [{'id': 'seed1', 'tipo': 'seed', 'testo': 'Another passage word for word.', 'paragrafo': 'Rn. 99', 'pagina': '30', 'documento': 'd', 'nota': ''}]
        mp[5]['supported'] = [ps[0]['id']]
    e = C.congela('neubauer', stato_firestore(stato, 'neubauer', m), registro(), applica=True, dest=tmp_path, oggi='2026-10-20')
    assert mtime_cited() == prima, 'cited-cases/ non si tocca'
    nuovo = yaml.safe_load((tmp_path / 'versioni/P10/neubauer-P10.yaml').read_text(encoding='utf-8'))
    q = {x['id']: x for x in nuovo['semantic_queries']}
    b = {x['id']: x for x in base['semantic_queries']}
    assert q['neubauer.percorso_dopo_2030']['testo'].strip() == 'A new description of the pathway after 2030.'
    assert q['neubauer.percorso_dopo_2030']['titolo_en'] == 'A better English title'
    assert q['neubauer.percorso_dopo_2030']['titolo'] == b['neubauer.percorso_dopo_2030']['titolo'], 'il titolo del file non cambia'
    assert q['neubauer.budget_residuo']['seeds'][0]['testo'] == 'Another passage word for word.'
    # quello che non e' cambiato e' identico al file di partenza
    for i in b:
        if i not in ('neubauer.percorso_dopo_2030', 'neubauer.budget_residuo'):
            assert q[i] == b[i], i
    mappa = yaml.safe_load((tmp_path / 'versioni/R19/neubauer-mappa-paragrafi.yaml').read_text(encoding='utf-8'))
    assert mappa['voci'][5]['sonde_P05'] == ['liberta_intertemporale']
    assert mappa['voci'][5]['sonde'] == ['art20a_giustiziabile_autovincolo'], 'il campo della serie di prima non si tocca'
    vecchia = yaml.safe_load(open(QUI / 'cited-cases' / 'neubauer-mappa-paragrafi.yaml', encoding='utf-8'))['voci']
    assert [v.get('prepara') for v in mappa['voci']] == [v.get('prepara') for v in vecchia], 'il prepara non portato resta com era'
    assert len(mappa['voci']) == len(yaml.safe_load(open(QUI / 'cited-cases' / 'neubauer-mappa-paragrafi.yaml', encoding='utf-8'))['voci'])
    # la proposta di registro e i titoli inglesi da portare in principi.js
    prop = json.loads((tmp_path / 'versioni/P10/registro-proposta-neubauer.json').read_text(encoding='utf-8'))
    voce = prop['voci_del_registro'][0]
    assert voce['codice'] == 'P10' and voce['rispetto_a'] == 'P05' and voce['in_uso'] == 'proposta'
    assert voce['istruzioni'][0]['sha256'] == hashlib.sha256((tmp_path / 'versioni/P10/neubauer-P10.yaml').read_bytes()).hexdigest()
    assert 'Maria Dicosola' in voce['compito']
    assert prop['titoli_inglesi_da_portare_in_principi_js'][0]['titolo'] == 'A better English title'
    assert (QUI / 'versioni' / 'P10').exists() is False, 'il repository vero non e\' stato toccato'
    del e


def test_il_file_nuovo_lo_legge_il_lettore_della_pipeline(stato, tmp_path):
    import cerca
    def m(ps, mp):
        ps[0]['descrizione'] = 'A different probe sentence for the first principle of the case.'
    C.congela('neubauer', stato_firestore(stato, 'neubauer', m), registro(), applica=True, dest=tmp_path)
    nuovo = cerca.leggi_caso(tmp_path / 'versioni/P10/neubauer-P10.yaml')
    vecchio = cerca.leggi_caso(QUI / 'cited-cases' / 'neubauer-P05.yaml')
    assert len(nuovo['sonde']) == len(vecchio['sonde']) == 7
    assert nuovo['sonde'][0]['testo'].startswith('A different probe')
    assert nuovo['sonde'][1]['testo'] == vecchio['sonde'][1]['testo']
    assert nuovo['forme'] == vecchio['forme'] and nuovo['escluse'] == vecchio['escluse']


def test_un_codice_gia_preso_si_rifiuta(stato, tmp_path):
    def m(ps, mp):
        ps[0]['descrizione'] = 'Something else entirely, to make a change.'
    C.congela('neubauer', stato_firestore(stato, 'neubauer', m), registro(), applica=True, dest=tmp_path)
    # il secondo congelamento prende il codice dopo, non sovrascrive
    e2 = C.congela('neubauer', stato_firestore(stato, 'neubauer', m), registro(), applica=True, dest=tmp_path)
    assert e2['file'][0] == 'versioni/P11/neubauer-P11.yaml'
    with pytest.raises(SystemExit):
        C.congela('neubauer', stato_firestore(stato, 'neubauer', m), registro(), applica=True, dest=tmp_path, codice_sonde='P10')


# ── riscrivere la mappa (08/10/2026) ─────────────────────────────────────────────────────────────────────────────────
def db_scritto(stato, tmp_path, monkeypatch):
    monkeypatch.setattr(C, 'USCITA', tmp_path)
    db = Db()
    C.scrivi(stato, db, FS)
    # la mappa com'era il 08/10 alle 04:52: il campo `sonde` della serie di prima
    for p in [p for p in db.store if p.startswith('corpus_casi/neubauer/mappa/')]:
        db.store[p]['supported'] = ['neubauer.schutzpflicht_clima']
    return db


def test_riscrivi_mappa_a_secco_non_tocca_niente(stato, tmp_path, monkeypatch):
    db = db_scritto(stato, tmp_path, monkeypatch)
    prima = copy.deepcopy(db.store)
    assert C.riscrivi_mappa(stato, db, FS, ['neubauer'], applica=False) is None
    assert db.store == prima


def test_riscrivi_mappa_scrive_solo_la_mappa_di_quei_casi(stato, tmp_path, monkeypatch):
    db = db_scritto(stato, tmp_path, monkeypatch)
    prima = copy.deepcopy(db.store)
    f = C.riscrivi_mappa(stato, db, FS, ['neubauer'], applica=True)
    assert f and json.loads(gzip.open(f, 'rt', encoding='utf-8').read())['neubauer']['mappa']['n0000']['supported'] == ['neubauer.schutzpflicht_clima']
    neu = next(c for c in stato['casi'] if c['slug'] == 'neubauer')
    for v in neu['mappa']:
        assert db.store[f"corpus_casi/neubauer/mappa/{C.id_voce_mappa(v)}"]['supported'] == v['supported']
    assert db.store['corpus_casi/neubauer']['campo_mappa'] == 'sonde_P05' and db.store['corpus_casi/neubauer']['slug'] == 'neubauer'
    for p in prima:
        if not p.startswith('corpus_casi/neubauer/mappa/') and p != 'corpus_casi/neubauer':
            assert db.store[p] == prima[p], p


def test_riscrivi_mappa_si_ferma_se_qualcuno_ha_modificato(stato, tmp_path, monkeypatch):
    db = db_scritto(stato, tmp_path, monkeypatch)
    db.store['corpus_casi/neubauer/modifiche/m_n0003__2'] = {'campo': 'supported'}
    prima = copy.deepcopy(db.store)
    with pytest.raises(SystemExit):
        C.riscrivi_mappa(stato, db, FS, ['future-generations', 'neubauer'], applica=True)
    assert db.store == prima
    del db.store['corpus_casi/neubauer/modifiche/m_n0003__2']
    db.store['corpus_casi/neubauer/principi/neubauer.budget_residuo']['rev'] = 2
    with pytest.raises(SystemExit):
        C.riscrivi_mappa(stato, db, FS, ['neubauer'], applica=True)
