"""Il registro unico dei casi (cited-cases/casi.yaml): gli stessi valori che prima stavano scritti in cinquanta file."""
import filecmp, json, pathlib, subprocess, sys
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
import casi_registro as CR  # noqa: E402

SEI = ('urgenda', 'neubauer', 'future-generations', 'klimaseniorinnen', 'cig-parere-clima', 'idh-oc-32-25')


def test_i_sei_casi_come_scritti_prima():
    assert CR.CASI == SEI
    assert list(CR.PREFISSI.items()) == list(zip(SEI, ('URG', 'NEU', 'FGC', 'KLS', 'ICJ', 'IAC')))
    assert CR.PRIMA_SERIE == {'urgenda': 'P01', 'neubauer': 'P02', 'future-generations': 'P02', 'klimaseniorinnen': 'P06',
                              'cig-parere-clima': 'P07', 'idh-oc-32-25': 'P08'}
    assert CR.SERIE_IN_USO == {'neubauer': 'P05', 'future-generations': 'P05', 'cig-parere-clima': 'P09'}
    assert CR.SOGLIE_D05 == {'urgenda': '2015-06-24', 'neubauer': '2021-03-24', 'future-generations': '2018-02-12',
                             'klimaseniorinnen': '2024-04-09', 'cig-parere-clima': '2025-07-23', 'idh-oc-32-25': '2025-07-03'}
    assert CR.CODICE_MAPPA == {'klimaseniorinnen': 'R09', 'cig-parere-clima': 'R18', 'idh-oc-32-25': 'R09'}


def test_ogni_caso_ha_il_suo_file_e_la_mappa():
    for c in CR.TUTTI:
        assert (QUI/'cited-cases'/f'{c}.yaml').exists(), c
    mappa = json.loads((QUI/'pubblicazione'/'mappa'/'casi.json').read_text(encoding='utf-8'))['casi']
    for c in mappa:
        assert c['id'] in CR.TUTTI and c['nome'] == CR.NOMI[c['id']] and c['colore'] == CR.COLORI[c['id']]


def test_gemello_del_pacchetto_identico():
    assert filecmp.cmp(QUI/'tools'/'casi_registro.py', QUI/'tracepipe'/'casi_registro.py', shallow=False)
    from tracepipe import config
    assert config.CASI == CR.CASI and dict(config.PRIMA_SERIE) == CR.PRIMA_SERIE


def test_caso_nuovo_senza_toccare_codice(tmp_path):
    f = tmp_path/'casi.yaml'
    f.write_text((QUI/'cited-cases'/'casi.yaml').read_text(encoding='utf-8') +
                 "  - id: caso-prova\n    prefisso: PRV\n    nome: Caso prova\n    colore: \"#123456\"\n    serie_prima: P99\n"
                 "    serie_in_uso: P99\n    soglia_d05: 2030-01-01\n    codice_mappa: R09\n    attivo: si\n", encoding='utf-8')
    codice = ("import sys; sys.path.insert(0,'tools'); import casi_registro as C, sonde, controllo_finestra as F, d05_pronto as D;"
              "print(C.CASI[-1], C.PREFISSI['caso-prova'], sonde.PRIMA_SERIE['caso-prova'], sonde.SERIE_IN_USO['caso-prova'],"
              " D.SOGLIE['caso-prova'], len(C.CASI))")
    r = subprocess.run([sys.executable, '-c', codice], cwd=QUI, capture_output=True, text=True, env={'TRACE_CASI': str(f), 'PATH': ''})
    assert r.stdout.split() == ['caso-prova', 'PRV', 'P99', 'P99', '2030-01-01', '7'], r.stderr[-500:]
