"""R15 (04/10/2026): the supported sentence is extracted from the text, not copied by the model.

`tools/frase_sostenuta.py` finds the footnote that carries the citation, its marker in the body (same page or up to
two pages before) and the full body sentence around the marker; for a citation in the body, the sentence around the
name. These tests build small filings (a PDF made here with PyMuPDF, and its markdown exactly as the corpus builds it:
`get_text('text')` after a `<!-- page N -->` marker) and check both what must be found AND what must fail: no marker,
a doubled marker, a footnote line without a number, a run-on «sentence», a name in a running header give «ambiguo» and
no sentence, never a guess.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

fitz = pytest.importorskip('fitz')


@pytest.fixture
def fs(vivi_oggi) -> Any:
    return vivi_oggi('frase_sostenuta')


def _atto(tmp_path: Path, pagine: list[list[tuple]], nome: str = 'atto') -> tuple[Path, Path]:
    """pagine: per pagina, voci (x, y, testo, corpo). Ritorna (markdown, pdf)."""
    doc = fitz.open()
    for voci in pagine:
        pg = doc.new_page(width=595, height=842)
        for x, y, testo, corpo in voci:
            pg.insert_text((x, y), testo, fontsize=corpo, fontname='helv')
    pdf = tmp_path / f'{nome}.pdf'
    doc.save(str(pdf))
    doc = fitz.open(str(pdf))
    md = "---\ndocument_id: 'prova'\n---\n" + ''.join(
        f'\n<!-- page {k + 1} -->\n\n' + doc[k].get_text('text') for k in range(doc.page_count))
    f = tmp_path / f'{nome}.md'
    f.write_text(md, encoding='utf-8')
    return f, pdf


def _righe_corpo(testi: list[str], y0: int = 80, passo: int = 16, corpo: float = 11) -> list[tuple]:
    return [(72, y0 + k * passo, t, corpo) for k, t in enumerate(testi)]


def _pos(md: Path, ago: str, dopo: int = 0) -> int:
    t = md.read_text(encoding='utf-8')
    i = t.index(ago, dopo)
    return i


# ── found ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_nota_al_corpo_sulla_stessa_pagina(fs, tmp_path: Path) -> None:
    corpo = _righe_corpo([
        'The Court recalled its earlier findings on the matter. Climate change is a threat to the',
        'enjoyment of human rights, as held by the Dutch Supreme Court, para. 5.7.7 of its ruling.',
        'Another sentence follows here and has nothing to do with it.',
    ])
    fine_riga = 72 + fitz.get_text_length(corpo[1][2], fontname='helv', fontsize=11)
    marcatore = [(fine_riga + 0.5, 80 + 16 - 4, '12', 6)]   # in apice subito dopo «ruling.»
    note = [(72, 760, '12', 6), (80, 763, 'Urgenda Foundation v. The Netherlands, ECLI:NL:HR:2019:2007.', 8)]
    md, pdf = _atto(tmp_path, [corpo + marcatore + note])
    e = fs.estrai(str(md), _pos(md, 'Urgenda Foundation'), str(pdf))
    assert e['metodo'] == 'nota→corpo', e
    assert e['nota'] == 12
    assert e['frase'].startswith('Climate change is a threat to the enjoyment of human rights')
    assert e['frase'].endswith('para. 5.7.7 of its ruling.')        # «para.» does not cut the sentence
    assert '12' not in e['frase']
    assert e['pagine'] == [1]


def test_frase_nel_corpo_ricucita_oltre_il_salto_di_pagina(fs, tmp_path: Path) -> None:
    p1 = _righe_corpo(['First a short sentence ends here. In Urgenda v. Netherlands the court ordered the State to',
                       'reduce emissions by at least 25 per cent by the end of 2020, a holding that other courts'])
    p2 = _righe_corpo(['have since followed in several jurisdictions. A new sentence starts on the second page.'])
    md, pdf = _atto(tmp_path, [p1, p2])
    e = fs.estrai(str(md), _pos(md, 'Urgenda'), str(pdf))
    assert e['metodo'] == 'corpo', e
    assert e['frase'] == ('In Urgenda v. Netherlands the court ordered the State to reduce emissions by at least 25 per '
                          'cent by the end of 2020, a holding that other courts have since followed in several jurisdictions.')
    assert e['pagine'] == [1, 2]


def test_numero_del_paragrafo_fuori_dalla_frase(fs, tmp_path: Path) -> None:
    p1 = _righe_corpo(['325. The previous paragraph ends here.',
                       '326. The foreign courts agree: the Dutch Supreme Court in Urgenda, Rn. 5.7.7, held the same.'])
    md, pdf = _atto(tmp_path, [p1])
    e = fs.estrai(str(md), _pos(md, 'Urgenda'), str(pdf))
    assert e['metodo'] == 'corpo'
    assert e['frase'] == 'The foreign courts agree: the Dutch Supreme Court in Urgenda, Rn. 5.7.7, held the same.'


def test_solo_testo_nota_col_richiamo_unico(fs, tmp_path: Path) -> None:
    md = tmp_path / 'ocr.md'
    md.write_text("---\nx: 'y'\n---\n\n<!-- page 1 -->\n\nThe State has a duty of care towards its citizens.7 Other text "
                  "follows in this paragraph.\n\n7 See Urgenda, para. 4.83.\n", encoding='utf-8')
    e = fs.estrai(str(md), _pos(md, 'Urgenda'))
    assert e['metodo'] == 'nota→corpo', e
    assert e['frase'] == 'The State has a duty of care towards its citizens.'


# ── must fail: «ambiguo», never a guess ───────────────────────────────────────────────────────────────────────────

def test_deve_fallire_nota_senza_richiamo(fs, tmp_path: Path) -> None:
    corpo = _righe_corpo(['The Court recalled its earlier findings on the matter at some length today.'])
    note = [(72, 760, '12', 6), (80, 763, 'Urgenda Foundation v. The Netherlands, ECLI:NL:HR:2019:2007.', 8)]
    md, pdf = _atto(tmp_path, [corpo + note])
    e = fs.estrai(str(md), _pos(md, 'Urgenda Foundation'), str(pdf))
    assert e['metodo'] == 'ambiguo' and e['frase'] == '' and e['inizio'] is None
    assert 'non trovato' in e['motivo']


def test_deve_fallire_richiamo_ripetuto(fs, tmp_path: Path) -> None:
    md = tmp_path / 'doppio.md'
    md.write_text("---\nx: 'y'\n---\n\n<!-- page 1 -->\n\nThe State has a duty of care.7 And the court agreed with "
                  "this.7 Nothing else.\n\n7 See Urgenda, para. 4.83.\n", encoding='utf-8')
    e = fs.estrai(str(md), _pos(md, 'Urgenda'))
    assert e['metodo'] == 'ambiguo' and e['frase'] == ''


def test_deve_fallire_nota_senza_numero(fs, tmp_path: Path) -> None:
    corpo = _righe_corpo(['The Court recalled its earlier findings on the matter at some length today.'])
    note = [(80, 763, 'Urgenda Foundation v. The Netherlands, ECLI:NL:HR:2019:2007.', 8)]
    md, pdf = _atto(tmp_path, [corpo + note])
    e = fs.estrai(str(md), _pos(md, 'Urgenda Foundation'), str(pdf))
    assert e['metodo'] == 'ambiguo' and e['frase'] == ''


def test_deve_fallire_frase_senza_fine(fs, tmp_path: Path) -> None:
    lunga = ' '.join(['word'] * 230)
    md = tmp_path / 'lunga.md'
    md.write_text("---\nx: 'y'\n---\n\n<!-- page 1 -->\n\nShort start. The Urgenda case " + lunga + ' end.\n',
                  encoding='utf-8')
    e = fs.estrai(str(md), _pos(md, 'Urgenda'))
    assert e['metodo'] == 'ambiguo' and 'taglio incerto' in e['motivo']


def test_deve_fallire_nome_nella_testata(fs, tmp_path: Path) -> None:
    pagine = [[(72, 40, f'Urgenda v. Netherlands brief {k}', 9)] + _righe_corpo([f'Body text of page {k} ends here.'])
              for k in range(1, 5)]
    md, pdf = _atto(tmp_path, pagine)
    e = fs.estrai(str(md), _pos(md, 'Urgenda', _pos(md, '<!-- page 2')), str(pdf))
    assert e['metodo'] == 'ambiguo' and e['frase'] == ''


def test_deve_fallire_solo_testo_oltre_la_pagina(fs, tmp_path: Path) -> None:
    md = tmp_path / 'oltre.md'
    md.write_text("---\nx: 'y'\n---\n\n<!-- page 1 -->\n\nShort start. In Urgenda the court ordered the State\n\n"
                  "<!-- page 2 -->\n\nto reduce emissions. Next.\n", encoding='utf-8')
    e = fs.estrai(str(md), _pos(md, 'Urgenda'))
    assert e['metodo'] == 'ambiguo' and e['frase'] == ''


# ── sentence segmentation on legal text ───────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('testo, attese', [
    # abbreviations and citations do not cut
    ('The Court, para. 5.7.7, and Rn. 242 f. agreed with art. 2. The next one starts here.',
     ['The Court, para. 5.7.7, and Rn. 242 f. agreed with art. 2.', 'The next one starts here.']),
    # German dates and ordinals
    ('Mit Beschluss vom 24. März 2021 hat das Gericht entschieden. Danach gilt es.',
     ['Mit Beschluss vom 24. März 2021 hat das Gericht entschieden.', 'Danach gilt es.']),
    # a period inside brackets closes the quoted sentence
    ('the court opined that “[t]he state may not evade it[.]” The court continued: more.',
     ['the court opined that “[t]he state may not evade it[.]”', 'The court continued: more.']),
    # elision and spaced ellipsis do not cut
    ('As held in Urgenda: “[…] After all, any emission counts . . . and so on.” Next sentence here.',
     ['As held in Urgenda: “[…] After all, any emission counts . . . and so on.”', 'Next sentence here.']),
    # a lowercase outline label opens a sentence
    ('in the context of the African region. k. The outcome here would differ.',
     ['in the context of the African region.', 'k. The outcome here would differ.']),
    # nothing cuts inside parentheses
    ('It follows (S. VAN DROOGHENBROECK, "Urgenda? Entre réparation", p. 750). Then more.',
     ['It follows (S. VAN DROOGHENBROECK, "Urgenda? Entre réparation", p. 750).', 'Then more.']),
])
def test_confini_delle_frasi(fs, testo: str, attese: list[str]) -> None:
    tg = fs.confini(testo)
    pezzi = [testo[a:b].strip() for a, b in zip(tg, tg[1:]) if testo[a:b].strip()]
    assert pezzi == attese
