"""La sentenza di un caso nuovo nel corpus (tools/carica_sentenza_caso.py).

PDF piccoli fatti qui con PyMuPDF: uno a testo nativo e uno scansione (solo immagini, senza strato di testo).
Tutto in una radice finta sotto tmp_path: niente del corpus vero viene scritto. Il confronto con una sentenza vera
del Sabin (KlimaSeniorinnen) gira solo se il suo PDF e il suo Markdown sono sul disco.
"""

from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

import pytest

RADICE_VERA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE_VERA / 'tools'))
sys.path.insert(0, str(RADICE_VERA))

fitz = pytest.importorskip('fitz')
C = pytest.importorskip('carica_sentenza_caso')

PAROLE = ('The Court notes that the applicant association has standing and that the State has failed to adopt '
          'adequate measures against climate change, in breach of its positive obligations under Article 8 of the '
          'Convention, as the margin of appreciation is narrower in this field of general interest. ')


def pagina_lunga(n: int) -> str:
    """Un testo di una pagina con un numero diverso per pagina (circa 700 caratteri)."""
    return f'Paragraph {n}. ' + PAROLE * 3


def crea_pdf_nativo(percorso: Path, pagine: int = 3) -> Path:
    doc = fitz.open()
    for n in range(1, pagine + 1):
        pg = doc.new_page()
        pg.insert_textbox(fitz.Rect(40, 40, 555, 800), pagina_lunga(n), fontsize=11)
    doc.save(percorso)
    doc.close()
    return percorso


def crea_pdf_scansione(percorso: Path, pagine: int = 2) -> Path:
    """Le pagine sono immagini: nessuna parola nello strato di testo."""
    sorgente = fitz.open()
    doc = fitz.open()
    for n in range(1, pagine + 1):
        s = sorgente.new_page()
        s.insert_textbox(fitz.Rect(40, 40, 555, 800), pagina_lunga(n), fontsize=14)
        immagine = s.get_pixmap(dpi=150).tobytes('png')
        pg = doc.new_page()
        pg.insert_image(pg.rect, stream=immagine)
    doc.save(percorso)
    doc.close()
    sorgente.close()
    return percorso


class OcrFinto:
    """Un motore OCR che restituisce un testo noto: prova la scelta della fonte senza Vision."""

    def __init__(self, testo: str = PAROLE * 3):
        self.testo, self.chiamate = testo, 0

    def riconosci(self, _pagina) -> str:
        self.chiamate += 1
        return self.testo


@pytest.fixture
def radice(tmp_path: Path) -> Path:
    """Una radice con un solo documento del Sabin (id con la coda a 4 esadecimali) e il suo manifest."""
    r = tmp_path / 'radice'
    (r / 'markdown' / 'altro-caso_aaaa').mkdir(parents=True)
    (r / 'markdown' / 'altro-caso_aaaa' / 'a.md').write_text(
        "---\ndocument_id: 'altro-caso-judgment_beef'\ncase_id: 'altro-caso_aaaa'\nsha256_pdf: 'ab'\n---\n\ntesto\n",
        encoding='utf-8')
    (r / 'manifest.jsonl').write_text(json.dumps(
        {'sha256': 'ab', 'docs': [{'document_id': 'altro-caso-judgment_beef', 'case_id': 'altro-caso_aaaa'}]}) + '\n')
    return r


@pytest.fixture
def dati() -> C.DatiCaso:
    return C.DatiCaso(nome='Example Seniors Association v. Ruritania', corte='Supreme Court of Ruritania',
                      data_decisione='2025-06-12', lingua='English', numeri_causa=['No. 12/2024'])


def test_slug() -> None:
    assert C.slug('Ruritania: Société c. État & Co. - judgment') == 'ruritania-societe-c-etat-co-judgment'
    assert C.slug('') == ''
    lungo = C.slug('parola ' * 40, 50)
    assert len(lungo) <= 50 and not lungo.endswith('-')


def test_convenzione_degli_id(radice: Path, dati: C.DatiCaso, tmp_path: Path) -> None:
    pdf = crea_pdf_nativo(tmp_path / 's.pdf')
    p = C.CaricatoreSentenza(radice).prepara(dati, pdf, None)
    sha = C.impronta_file(pdf)
    assert p.ids.document_id == f'example-seniors-association-v-ruritania-judgment_x{sha[:4]}'
    assert re.fullmatch(r'example-seniors-association-v-ruritania_x[0-9a-f]{4}', p.ids.case_id)
    # la «x» non puo' comparire in un id del Sabin (slug + '_' + 4 esadecimali)
    assert not re.search(r'_[0-9a-f]{4}$', p.ids.document_id)


def test_a_secco_non_scrive_niente(radice: Path, dati: C.DatiCaso, tmp_path: Path) -> None:
    pdf = crea_pdf_nativo(tmp_path / 's.pdf')
    prima = sorted(str(x) for x in radice.rglob('*'))
    car = C.CaricatoreSentenza(radice)
    p = car.prepara(dati, pdf, None)
    rapporto = C.descrivi(p, scrivi=False)
    assert 'A SECCO' in rapporto and p.ids.document_id in rapporto and 'pagine       3' in rapporto
    assert p.front_matter.startswith("---\ndocument_id: '") and p.corpo.startswith('\n\n<!-- page 1 -->\n\n')
    assert sorted(str(x) for x in radice.rglob('*')) == prima


def test_scrive_i_file_e_non_si_ripete(radice: Path, dati: C.DatiCaso, tmp_path: Path) -> None:
    pdf = crea_pdf_nativo(tmp_path / 's.pdf')
    car = C.CaricatoreSentenza(radice)
    p = car.prepara(dati, pdf, None)
    reg = car.scrivi(p)
    for k in ('pdf', 'testo', 'markdown', 'indice', 'registro'):
        assert p.percorsi[k].exists(), k
    md = p.percorsi['markdown'].read_text(encoding='utf-8')
    assert re.findall(r'<!-- page (\d+) -->', md) == ['1', '2', '3']
    assert "origine_documento: 'caricata da chi chiede" in md and "pagine_ocr: ''" in md
    assert p.percorsi['pdf'].read_bytes() == pdf.read_bytes()
    assert reg['pagine'] == 3 and reg['uscite']['markdown']['sha256']
    # lo stesso PDF una seconda volta: rifiutato, e dice con quale id e' gia' dentro
    with pytest.raises(C.ErroreCaricamento, match='gia\' nel corpus come ' + re.escape(p.ids.document_id)):
        C.CaricatoreSentenza(radice).prepara(dati, pdf, None)


def test_creazione_esclusiva(radice: Path, dati: C.DatiCaso, tmp_path: Path) -> None:
    pdf = crea_pdf_nativo(tmp_path / 's.pdf')
    car = C.CaricatoreSentenza(radice)
    p = car.prepara(dati, pdf, None)
    esistente = p.percorsi['testo']
    esistente.parent.mkdir(parents=True)
    esistente.write_text('NON TOCCARE', encoding='utf-8')
    with pytest.raises(C.ErroreCaricamento, match='niente sovrascritto'):
        car.scrivi(p)
    assert esistente.read_text(encoding='utf-8') == 'NON TOCCARE'
    assert not p.percorsi['markdown'].exists()


def test_id_gia_esistente_si_passa_ai_quattro_successivi(radice: Path, dati: C.DatiCaso, tmp_path: Path) -> None:
    """Il caso «id gia' esistente»: la coda dell'impronta e' presa da un altro PDF."""
    pdf = crea_pdf_nativo(tmp_path / 's.pdf')
    sha = C.impronta_file(pdf)
    base = C.slug(dati.titolo())
    car = C.CaricatoreSentenza(radice)
    car.registro.documenti[f'{base}_x{sha[:4]}'] = 'impronta-di-un-altro-pdf'
    p = car.prepara(dati, pdf, None)
    assert p.ids.document_id == f'{base}_x{sha[4:8]}'
    # e il case_id di un caso del Sabin non si riusa mai
    base_caso = C.slug(dati.nome)
    import hashlib
    impr = hashlib.sha256(base_caso.encode()).hexdigest()
    car.registro.casi_sabin.add(f'{base_caso}_x{impr[:4]}')
    p2 = car.prepara(dati, pdf, None)
    assert p2.ids.case_id == f'{base_caso}_x{impr[4:8]}'


def test_stesso_giudizio_due_atti_riusa_il_case_id(radice: Path, dati: C.DatiCaso, tmp_path: Path) -> None:
    car = C.CaricatoreSentenza(radice)
    car.scrivi(car.prepara(dati, crea_pdf_nativo(tmp_path / 'a.pdf', 3), None))
    car2 = C.CaricatoreSentenza(radice)                      # il registro si rilegge dal disco
    p2 = car2.prepara(dati, crea_pdf_nativo(tmp_path / 'b.pdf', 4), None)
    assert p2.ids.case_gia_caricato and p2.percorsi['markdown'].parent.exists()


def test_i_documenti_del_sabin_non_si_toccano(radice: Path, dati: C.DatiCaso, tmp_path: Path) -> None:
    sabin = radice / 'markdown' / 'altro-caso_aaaa' / 'a.md'
    prima = sabin.read_bytes()
    car = C.CaricatoreSentenza(radice)
    car.scrivi(car.prepara(dati, crea_pdf_nativo(tmp_path / 's.pdf'), None))
    assert sabin.read_bytes() == prima


def test_testo_dal_json_se_e_buono(radice: Path, dati: C.DatiCaso, tmp_path: Path) -> None:
    pdf = crea_pdf_nativo(tmp_path / 's.pdf', 3)
    js = tmp_path / 'sentenza-testo.json'
    pagine_js = [f'JSON {pagina_lunga(n)}' for n in (1, 2, 3)]
    js.write_text(json.dumps({'pagine': pagine_js}), encoding='utf-8')
    p = C.CaricatoreSentenza(radice).prepara(dati, pdf, js)
    assert [x.fonte for x in p.pagine] == ['json'] * 3
    assert 'JSON Paragraph 2.' in p.corpo and '3 pagine da sentenza-testo.json' in p.metodo
    # una pagina del JSON vuota: per quella si passa al testo del PDF, le altre restano del JSON
    pagine_js[1] = ''
    js.write_text(json.dumps({'pagine': pagine_js}), encoding='utf-8')
    p = C.CaricatoreSentenza(radice).prepara(dati, pdf, js)
    assert [x.fonte for x in p.pagine] == ['json', 'pdf', 'json']


def test_json_con_altre_pagine_del_pdf_non_si_usa(radice: Path, dati: C.DatiCaso, tmp_path: Path) -> None:
    pdf = crea_pdf_nativo(tmp_path / 's.pdf', 3)
    js = tmp_path / 'sentenza-testo.json'
    js.write_text(json.dumps({'pagine': [pagina_lunga(1)] * 5}), encoding='utf-8')
    p = C.CaricatoreSentenza(radice).prepara(dati, pdf, js)
    assert all(x.fonte == 'pdf' for x in p.pagine)
    assert any('ha 5 pagine, il PDF 3' in n for n in p.note)


def test_senza_pdf_solo_json(radice: Path, dati: C.DatiCaso, tmp_path: Path) -> None:
    js = tmp_path / 'sentenza-testo.json'
    js.write_text(json.dumps({'pagine': [pagina_lunga(1), pagina_lunga(2)]}), encoding='utf-8')
    p = C.CaricatoreSentenza(radice).prepara(dati, None, js)
    assert len(p.pagine) == 2 and p.ids.document_id.endswith('_x' + p.ids.sha256_pdf[:4])


def test_scansione_va_all_ocr_pagina_per_pagina(radice: Path, dati: C.DatiCaso, tmp_path: Path) -> None:
    pdf = crea_pdf_scansione(tmp_path / 'scan.pdf', 2)
    ocr = OcrFinto()
    p = C.CaricatoreSentenza(radice, ocr).prepara(dati, pdf, None)
    assert [x.fonte for x in p.pagine] == ['ocr', 'ocr'] and ocr.chiamate == 2
    assert "pagine_ocr: '1,2'" in p.front_matter and 'OCR Vision, pagine 1,2' in p.metodo


def test_pagine_buone_non_chiamano_l_ocr(radice: Path, dati: C.DatiCaso, tmp_path: Path) -> None:
    ocr = OcrFinto()
    C.CaricatoreSentenza(radice, ocr).prepara(dati, crea_pdf_nativo(tmp_path / 's.pdf'), None)
    assert ocr.chiamate == 0


def test_ocr_illeggibile_non_sostituisce(radice: Path, dati: C.DatiCaso, tmp_path: Path) -> None:
    pdf = crea_pdf_scansione(tmp_path / 'scan.pdf', 1)
    with pytest.raises(C.ErroreCaricamento, match='nessuna parola'):
        C.CaricatoreSentenza(radice, OcrFinto('xx')).prepara(dati, pdf, None)


def test_ocr_vision_vero_su_una_scansione(radice: Path, dati: C.DatiCaso, tmp_path: Path) -> None:
    pytest.importorskip('ocrmac')
    pdf = crea_pdf_scansione(tmp_path / 'scan.pdf', 1)
    try:
        p = C.CaricatoreSentenza(radice, C.MotoreOcr('English')).prepara(dati, pdf, None)
    except Exception as e:                                    # Vision non disponibile (altra macchina, senza schermo)
        pytest.skip(f'Vision non disponibile: {e}')
    assert p.pagine[0].fonte == 'ocr'
    assert 'applicant association' in re.sub(r'\s+', ' ', p.pagine[0].testo)


def test_dati_mancanti(radice: Path, tmp_path: Path) -> None:
    with pytest.raises(C.ErroreCaricamento, match='manca il nome'):
        C.CaricatoreSentenza(radice).prepara(C.DatiCaso(nome=''), crea_pdf_nativo(tmp_path / 's.pdf'), None)
    with pytest.raises(C.ErroreCaricamento, match='data della decisione'):
        C.CaricatoreSentenza(radice).prepara(C.DatiCaso(nome='X v. Y', data_decisione='12/06/2025'),
                                             crea_pdf_nativo(tmp_path / 's.pdf'), None)


def test_dati_dal_file_del_caso(tmp_path: Path) -> None:
    pytest.importorskip('yaml')
    f = tmp_path / 'caso.yaml'
    f.write_text("nome: 'Seniors v. Ruritania'\nnon_english_name: 'Seniors c. Ruritanie'\ncase: \"\"\ncorte: 'Supreme Court'\n"
                 "data_decisione: 2025-06-12\ndocket_numbers:\n  - 'No. 1'\nfonte_primaria:\n  - documento: 'x'\n    lingua: 'French'\n",
                 encoding='utf-8')
    d = C.DatiCaso.da_yaml(f)
    assert (d.nome, d.nome_originale, d.case_id, d.corte, d.numeri_causa, d.lingua) == (
        'Seniors v. Ruritania', 'Seniors c. Ruritanie', '', 'Supreme Court', ['No. 1'], 'French')
    assert d.data_decisione == '2025-06-12'


def test_indice_di_un_file_solo(radice: Path, dati: C.DatiCaso, tmp_path: Path) -> None:
    import indice_pagine as IP
    car = C.CaricatoreSentenza(radice)
    p = car.prepara(dati, crea_pdf_nativo(tmp_path / 's.pdf', 3), None)
    car.scrivi(p)
    righe = [json.loads(x) for x in gzip.open(p.percorsi['indice'], 'rt', encoding='utf-8')]
    assert [r['id'] for r in righe] == [f'{p.ids.document_id}#p{n}' for n in (1, 2, 3)]
    assert righe == IP.pagine_del_file(p.percorsi['markdown'], radice)
    assert not (radice / 'index' / 'pagine' / 'pagine.jsonl.gz').exists()      # l'indice vivo non si tocca
    # a secco: niente file; e non si sovrascrive
    r2, dest, h = IP.aggiungi_un_file(p.percorsi['markdown'], radice, scrivi=False)
    assert len(r2) == 3 and h == ''
    with pytest.raises(FileExistsError):
        IP.aggiungi_un_file(p.percorsi['markdown'], radice, scrivi=True)


def test_front_matter_ha_i_campi_del_sabin_nello_stesso_ordine(radice: Path, dati: C.DatiCaso, tmp_path: Path) -> None:
    p = C.CaricatoreSentenza(radice).prepara(dati, crea_pdf_nativo(tmp_path / 's.pdf'), None)
    campi = re.findall(r'^([a-z_0-9]+):', p.front_matter, re.M)
    atteso = ['document_id', 'document_title', 'tipo_atto', 'tipo_atto_sabin', 'tipo_atto_concorde', 'tipo_atto_fonte',
              'tipo_atto_origine', 'case_id', 'case_name', 'case_name_originale', 'numero_causa', 'giurisdizioni',
              'geografie', 'stato', 'categorie', 'leggi', 'data_deposito', 'anno_avvio', 'lingue', 'url_origine',
              'pagine', 'file_testo', 'file_pdf', 'sha256_pdf', 'url_documento', 'url_caso', 'riassunto_caso',
              'riassunto_documento', 'questione']
    assert campi[:len(atteso)] == atteso
    assert campi[len(atteso):] == ['origine_documento', 'id_convenzione', 'metodo_testo', 'pagine_ocr']
    assert "url_origine: 'fornito dal richiedente'" in p.front_matter
    assert "tipo_atto: 'decisione'" in p.front_matter and "data_deposito: '2025-06-12 00:00:00'" in p.front_matter


# ── Storage finto: la scelta della versione ──────────────────────────────────────────────────────────────────────────

class BlobFinto:
    def __init__(self, nome: str, contenuto: dict[str, bytes]):
        self.name, self._c = nome, contenuto

    def exists(self) -> bool:
        return self.name in self._c

    def download_to_filename(self, dest: str) -> None:
        Path(dest).write_bytes(self._c[self.name])


class ClientFinto:
    """Gli stessi tre metodi che `DepositoStorage` usa; scrive solo in lettura, come il vero."""

    def __init__(self, contenuto: dict[str, bytes]):
        self.c = contenuto

    def list_blobs(self, _bucket: str, prefix: str = ''):
        return [BlobFinto(n, self.c) for n in sorted(self.c) if n.startswith(prefix)]

    def bucket(self, _nome: str):
        return self

    def blob(self, nome: str) -> BlobFinto:
        return BlobFinto(nome, self.c)


def test_deposito_sceglie_l_ocr_piu_alto(tmp_path: Path) -> None:
    g = 'GETTONEDIPROVA1234'
    c = {f'trace-casi/{g}/sentenza.pdf': b'radice', f'trace-casi/{g}/sentenza-testo.json': b'{"pagine": []}',
         f'trace-casi/{g}/ocr-1/sentenza.pdf': b'uno', f'trace-casi/{g}/ocr-2/sentenza.pdf': b'due',
         f'trace-casi/{g}/ocr-10/sentenza.pdf': b'dieci', f'trace-casi/{g}/ocr-10/sentenza-testo.json': b'{"pagine": []}'}
    dep = C.DepositoStorage(ClientFinto(c))
    assert dep.cartella(g) == f'trace-casi/{g}/ocr-10/'
    assert dep.cartella(g, 'root') == f'trace-casi/{g}/' and dep.cartella(g, 'ocr-2') == f'trace-casi/{g}/ocr-2/'
    pdf, js, pref = dep.scarica(g, tmp_path / 'giu')
    assert pdf.read_bytes() == b'dieci' and js is not None and pref.endswith('ocr-10/')
    pdf, js, _ = dep.scarica(g, tmp_path / 'giu2', 'ocr-2')
    assert pdf.read_bytes() == b'due' and js is None        # il json di un'altra cartella non e' di questo PDF
    assert C.DepositoStorage(ClientFinto({f'trace-casi/{g}/sentenza.pdf': b'r'})).cartella(g) == f'trace-casi/{g}/'


def test_deposito_rifiuta_gettoni_e_versioni_strani(tmp_path: Path) -> None:
    dep = C.DepositoStorage(ClientFinto({}))
    for brutto in ('../altro', 'corto', 'a/b/c/d/e/f/g/h'):
        with pytest.raises(C.ErroreCaricamento, match='gettone'):
            dep.cartella(brutto)
    with pytest.raises(C.ErroreCaricamento, match='versione'):
        dep.cartella('GETTONEDIPROVA1234', '../x')
    with pytest.raises(C.ErroreCaricamento, match='non c\'e\' sentenza.pdf'):
        dep.scarica('GETTONEDIPROVA1234', tmp_path / 'x')


# ── una sentenza vera del Sabin ──────────────────────────────────────────────────────────────────────────────────────

KLS_PDF = next(iter((RADICE_VERA / 'documents' / 'verein-klimaseniorinnen-schweiz-and-others-v-switzerland_6852').glob('*judgment.pdf')), None) \
    if (RADICE_VERA / 'documents').exists() else None
KLS_MD = next(iter((RADICE_VERA / 'markdown' / 'verein-klimaseniorinnen-schweiz-and-others-v-switzerland_6852').glob('*judgment.md')), None) \
    if (RADICE_VERA / 'markdown').exists() else None


@pytest.mark.skipif(KLS_PDF is None or KLS_MD is None, reason='KlimaSeniorinnen: PDF e Markdown del Sabin non sono sul disco')
def test_klimaseniorinnen_uguale_al_markdown_del_sabin(tmp_path: Path) -> None:
    """Il testo ricavato dal PDF vero e' identico, byte per byte, al corpo del Markdown che c'e' nel corpus; e il
    front matter ha gli stessi 29 campi. Il documento e' gia' nel corpus: lo si toglie dal registro di prova."""
    r = tmp_path / 'radice'
    (r / 'markdown').mkdir(parents=True)
    car = C.CaricatoreSentenza(r)
    dati = C.DatiCaso(nome='Verein KlimaSeniorinnen Schweiz and Others v. Switzerland', corte='ECtHR',
                      data_decisione='2024-04-09', lingua='English', numeri_causa=['Application no. 53600/20'])
    p = car.prepara(dati, KLS_PDF, None)
    orig = KLS_MD.read_text(encoding='utf-8')
    corpo = orig[orig.index('\n---\n', 4) + 6:]
    assert p.corpo == corpo
    assert len(p.pagine) == 260 and all(x.fonte == 'pdf' for x in p.pagine)
    campi_sabin = re.findall(r'^([a-z_0-9]+):', orig[:orig.index('\n---\n', 4)], re.M)
    assert re.findall(r'^([a-z_0-9]+):', p.front_matter, re.M)[:len(campi_sabin)] == campi_sabin
