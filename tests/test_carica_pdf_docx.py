"""The viewer PDF for non-PDF filings and the existence of every file_pdf on the corpus server (08/10/2026):
the page-fidelity check of tools/carica_pdf_docx.py, the one-call server check of stato_viste.pdf_sul_server, the
«visore» step of aggiornamento_finale.py (stato_viste.controllo_visore), the health view with the server check, and
the hook in d05_testo.py. Everything on fake data in ``tmp_path``: no Word, no ssh, no Firestore."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
fitz = pytest.importorskip('fitz')
import carica_pdf_docx as C  # noqa: E402
import stato_viste as V  # noqa: E402

PAGINE = [
    'The applicants rely on several decisions of foreign courts in support of their claim against the State.',
    'In the Urgenda case the Supreme Court held that the State must reduce emissions by at least twenty five percent.',
    'The Committee notes the arguments of the parties and concludes that there has been a violation of article 17.',
]


def _markdown(pagine=PAGINE):
    testa = "---\ndocument_id: 'doc_1'\nfile_pdf: 'documents/c/doc.docx'\n---\n"
    return testa + ''.join(f'\n\n<!-- page {i} -->\n\n{t}\n' for i, t in enumerate(pagine, 1))


def _pdf(tmp_path: Path, pagine, nome='x.pdf') -> Path:
    d = fitz.open()
    for t in pagine:
        p = d.new_page()
        p.insert_textbox(fitz.Rect(50, 50, 550, 800), t, fontsize=11)
    out = tmp_path / nome
    d.save(out)
    return out


def _riga(md, codice='URG-1', parola='Urgenda', pagina=2):
    return {'codice': codice, 'char_start': md.index(parola), 'pagina': pagina}


# ─── fedelta' di pagina ─────────────────────────────────────────────────────────────────────────────────────────

def test_pagina_di_conta_i_segni_prima_del_carattere():
    md = _markdown()
    assert C.pagina_di(md, md.index('applicants')) == 1
    assert C.pagina_di(md, md.index('Urgenda')) == 2
    assert C.pagina_di(md, md.index('Committee')) == 3
    assert C.pagina_di(md, 3) is None  # front matter


def test_passi_restano_nella_pagina_della_riga():
    md = _markdown()
    for w in C.passi(md, md.index('Urgenda')):
        assert 'urgenda' in w and 'applicants' not in w and 'committee' not in w


def test_pdf_fedele_passa(tmp_path):
    md = _markdown()
    e = C.controlla_pdf(_pdf(tmp_path, PAGINE), md, [_riga(md)])
    assert e['ok'] and e['problemi'] == []
    assert (e['pagine_pdf'], e['pagine_markdown']) == (3, 3)
    assert e['righe'][0]['nel_pdf'] == [2]
    assert e['pagine_che_finiscono_come_il_markdown'] == 3


def test_passo_su_altra_pagina_ferma(tmp_path):
    """Word ha spostato il confine: la frase della riga finisce sulla pagina dopo."""
    md = _markdown()
    spostato = [PAGINE[0], 'Nothing relevant here at all, only the heading of the section.', PAGINE[1] + ' ' + PAGINE[2]]
    e = C.controlla_pdf(_pdf(tmp_path, spostato), md, [_riga(md)])
    assert not e['ok']
    assert e['righe'][0]['nel_pdf'] == [3]
    assert 'la riga dice p. 2' in e['problemi'][0]


def test_numero_di_pagine_diverso_ferma_anche_senza_righe(tmp_path):
    md = _markdown()
    e = C.controlla_pdf(_pdf(tmp_path, PAGINE + ['An extra page that the Markdown does not have.']), md, [])
    assert not e['ok'] and '4 pagine nel PDF, 3 nel Markdown' in e['problemi'][0]


def test_richiami_di_nota_staccati_non_contano(tmp_path):
    """un numero di nota che nel PDF sta altrove (o manca) non impedisce di ritrovare il passo."""
    pagine = [PAGINE[0], PAGINE[1].replace('Urgenda case', 'Urgenda 12 case'), PAGINE[2]]
    md = _markdown(pagine)
    e = C.controlla_pdf(_pdf(tmp_path, PAGINE), md, [_riga(md)])
    assert e['ok'], e['problemi']


def test_bersaglio_e_il_file_pdf_delle_righe():
    md = 'markdown/caso_1/atto__abc.md'
    assert C.bersaglio(md) == 'documents/caso_1/atto__abc.pdf'
    assert C.markdown_di(C.bersaglio(md)) == md


def test_varianti_per_formato():
    assert C.varianti('.docx') == ['salti', 'word']
    assert C.varianti('.doc') == ['word']


def test_formato_che_word_non_apre_si_dice(tmp_path):
    (tmp_path / 'documents' / 'c').mkdir(parents=True)
    (tmp_path / 'documents' / 'c' / 'x.png').write_bytes(b'png')
    (tmp_path / 'markdown' / 'c').mkdir(parents=True)
    (tmp_path / 'markdown' / 'c' / 'x.md').write_text(_markdown())
    v = C.lavora('markdown/c/x.md', {'document_id': 'd', 'file_pdf': 'documents/c/x.png'}, [], False, False, tmp_path, visore=False)
    assert v['esito'].startswith('non convertito') and '.png' in v['esito']


def test_gia_sul_server_non_si_ricarica(tmp_path):
    v = C.lavora('markdown/c/x.md', {'document_id': 'd', 'file_pdf': 'documents/c/x.docx'}, [], False, True, tmp_path, visore=False)
    assert v['esito'] == "gia' sul server"


def test_salti_veri_dai_segni_di_word(tmp_path):
    import zipfile
    xml = ('<w:document><w:body><w:p><w:r><w:t>uno</w:t></w:r></w:p>'
           '<w:p><w:r><w:lastRenderedPageBreak/><w:t>due</w:t></w:r></w:p>'
           '<w:p><w:pPr><w:sectPr/></w:pPr></w:p>'
           '<w:p><w:r><w:lastRenderedPageBreak/><w:t>tre</w:t></w:r></w:p></w:body></w:document>')
    orig = tmp_path / 'a.docx'
    with zipfile.ZipFile(orig, 'w') as z:
        z.writestr('word/document.xml', xml)
    tolti = C.copia_con_salti(orig, tmp_path / 'b.docx')
    nuovo = zipfile.ZipFile(tmp_path / 'b.docx').read('word/document.xml').decode()
    assert tolti == 1                                   # il segno dopo il cambio di sezione non diventa un salto
    assert nuovo.count('<w:br w:type="page"/>') == 1 and 'lastRenderedPageBreak' not in nuovo


# ─── esistenza sul server ───────────────────────────────────────────────────────────────────────────────────────

class _Ssh:
    def __init__(self, mancanti=(), codice=0, extra=()):
        self.chiamate, self.mancanti, self.codice, self.extra = [], set(mancanti), codice, list(extra)

    def __call__(self, cmd, input='', **kw):
        self.chiamate.append((cmd, input))
        chiesti = input.splitlines()
        out = '\n'.join([p for p in chiesti if p in self.mancanti] + self.extra)
        return subprocess.CompletedProcess(cmd, self.codice, out + '\n', 'Permission denied' if self.codice else '')


def test_esistenza_una_sola_chiamata_e_solo_i_mancanti():
    ssh = _Ssh(mancanti={'documents/b.pdf'})
    m = V.pdf_sul_server(['documents/a.pdf', 'documents/b.pdf', 'documents/a.pdf', '', None], esegui=ssh)
    assert m == ['documents/b.pdf']
    assert len(ssh.chiamate) == 1
    cmd, chiesti = ssh.chiamate[0]
    assert cmd[0] == 'ssh' and 'BatchMode=yes' in cmd and chiesti.split() == ['documents/a.pdf', 'documents/b.pdf']


def test_esistenza_percorsi_fuori_cartella_contano_mancanti_senza_chiederli():
    ssh = _Ssh()
    m = V.pdf_sul_server(['../etc/passwd', '/root/x.pdf', 'documents/a.pdf'], esegui=ssh)
    assert m == ['../etc/passwd', '/root/x.pdf']
    assert ssh.chiamate[0][1].split() == ['documents/a.pdf']


def test_esistenza_server_muto_non_e_tutto_a_posto():
    with pytest.raises(RuntimeError):
        V.pdf_sul_server(['documents/a.pdf'], esegui=_Ssh(codice=255))


def test_esistenza_risposta_inattesa_si_ferma():
    with pytest.raises(RuntimeError):
        V.pdf_sul_server(['documents/a.pdf'], esegui=_Ssh(extra=['documents/mai-chiesto.pdf']))


def test_esistenza_vuoto_non_chiama():
    ssh = _Ssh()
    assert V.pdf_sul_server([], esegui=ssh) == [] and not ssh.chiamate


# ─── il passo «visore» e la vista Document health ────────────────────────────────────────────────────────────────

def _righe():
    return [{'codice': 'A-1', 'file_pdf': 'documents/a.pdf'}, {'codice': 'A-2', 'file_pdf': 'documents/a.pdf'},
            {'codice': 'B-1', 'file_pdf': 'documents/b.pdf'}, {'codice': 'K-1', 'file_pdf': 'documents/k.pdf'}]


def _esiti(spente=('K-1',)):
    return [{'c': r['codice'], 'esito': 'NON TROVATA' if r['codice'] in spente else 'frase'} for r in _righe()]


def test_visore_verde_con_le_eccezioni_note():
    ok, spiega, d = V.controllo_visore(_righe(), _esiti(), [], eccezioni={'K-1': 'perche'})
    assert ok, spiega
    assert 'di cui note 1, nuove []' in spiega


def test_visore_rosso_se_un_pdf_manca_sul_server():
    ok, spiega, d = V.controllo_visore(_righe(), _esiti(), ['documents/a.pdf'], eccezioni={'K-1': 'perche'})
    assert not ok and d['righe_pdf_mancante'] == ['A-1', 'A-2']
    assert 'PDF mancanti sul server 1 (2 righe)' in spiega


def test_visore_rosso_se_una_riga_nuova_non_si_accende():
    ok, _, d = V.controllo_visore(_righe(), _esiti(spente=('K-1', 'B-1')), [], eccezioni={'K-1': 'perche'})
    assert not ok and d['non_accese_nuove'] == ['B-1']


def test_visore_rosso_se_una_riga_non_ha_file_pdf_o_non_si_misura():
    righe = _righe() + [{'codice': 'Z-1', 'file_pdf': ''}]
    ok, _, d = V.controllo_visore(righe, _esiti(), [], eccezioni={'K-1': 'perche'})
    assert not ok and d['senza_file_pdf'] == ['Z-1']
    esiti = [e if e['c'] != 'B-1' else {'c': 'B-1', 'esito': 'pdf mancante'} for e in _esiti()]
    ok, _, d = V.controllo_visore(_righe(), esiti, [], eccezioni={'K-1': 'perche'})
    assert not ok and d['non_misurabili'] == ['B-1']


def test_visore_eccezione_tornata_accesa_si_dice_ma_non_fa_rosso():
    ok, _, d = V.controllo_visore(_righe(), _esiti(spente=()), [], eccezioni={'K-1': 'perche'})
    assert ok and d['eccezioni_tornate_accese'] == ['K-1']


def test_eccezioni_hanno_tutte_un_perche():
    assert V.ECCEZIONI_VISORE and all(len(v) > 40 for v in V.ECCEZIONI_VISORE.values())


def test_salute_conta_i_pdf_che_mancano_sul_server(tmp_path):
    righe = {r['codice']: {**r, 'document_id': 'd', 'caso_citato': 'urgenda'} for r in _righe()}
    d = V.vista_salute(_esiti(spente=()), righe, '2026-10-08T08:00', tmp_path, mancanti_server=['documents/b.pdf'])
    assert d['riassunto']['pdf_mancanti_server'] == 1 and d['riassunto']['righe_senza_pdf_sul_server'] == 1
    assert d['riassunto']['pdf_mancanti'] == 1
    assert [x['codice'] for x in d['pdf_mancanti'] if x['dove'] == 'server'] == ['B-1']
    senza = V.vista_salute(_esiti(spente=()), righe, '2026-10-08T08:00', tmp_path)
    assert senza['riassunto']['pdf_mancanti_server'] is None and not senza['misura']['server_controllato']


def test_spiegazione_inglese_del_passo_visore():
    _, spiega, _ = V.controllo_visore(_righe(), _esiti(spente=('K-1', 'B-1')), ['documents/a.pdf'], eccezioni={'K-1': 'x'})
    en = V.spiega_en('visore', spiega)
    assert en and 'missing on the corpus server 1 (2 rows)' in en and 'new: B-1' in en


# ─── d05_testo.py chiama il passo sugli atti nuovi non PDF ─────────────────────────────────────────────────────────

def test_d05_passa_solo_i_non_pdf_scritti():
    import d05_testo as T
    visti = []

    def esegui(md, scrivi):
        visti.append((md, scrivi))
        return [{'esito': 'caricato, impronta uguale sul server'} for _ in md], 'rapporto.json'

    fatte = [{'esito': 'scritto', 'origine': 'documents/c/a.docx', 'markdown': 'markdown/c/a__1.md'},
             {'esito': 'scritto', 'origine': 'documents/c/b.pdf', 'markdown': 'markdown/c/b.md'},
             {'esito': "esiste gia' (non toccato)", 'origine': 'documents/c/c.doc', 'markdown': 'markdown/c/c.md'}]
    assert T.pdf_per_non_pdf(fatte, esegui) == 0
    assert visti == [(['markdown/c/a__1.md'], True)]


def test_d05_un_pdf_fermo_fa_uscire_con_uno():
    import d05_testo as T
    fatte = [{'esito': 'scritto', 'origine': 'documents/c/a.doc', 'markdown': 'markdown/c/a.md'}]
    assert T.pdf_per_non_pdf(fatte, lambda md, s: ([{'esito': 'fermo: nessuna variante'}], 'r')) == 1
    assert T.pdf_per_non_pdf([], lambda md, s: pytest.fail('non va chiamato')) == 0
