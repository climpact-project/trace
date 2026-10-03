"""The corpus seen page by page: :class:`Pagina`, :class:`Documento`, :class:`IndicePagine`.

The page index ``index/pagine/pagine.jsonl.gz`` (built by ``tools/indice_pagine.py``) has one JSON line per page::

    {"id": "<document_id>#p<n>", "doc": "<document_id>", "file": "markdown/...", "pagina": n, "da": 0, "a": 0,
     "testo": "..."}

The production index is about 400 MB compressed, so it is always streamed, and readers ask only for the pages they
need, exactly as ``tools/leggi_ripresa.py`` does. When an id appears twice the last line wins (same as the live
dictionary update).
"""

from __future__ import annotations

import gzip
import json
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Pagina:
    """One page of a document (``pagina``, Italian for page).

    Attributes:
        id: ``<document_id>#p<n>``.
        doc: the document id.
        file: the markdown file of the document, relative to the root.
        numero: the page number (``pagina`` in the index).
        da: start offset of the page in the markdown file.
        a: end offset of the page in the markdown file.
        testo: the page text.
    """

    id: str
    doc: str = ''
    file: str = ''
    numero: int = 0
    da: int = 0
    a: int = 0
    testo: str = ''

    @staticmethod
    def id_di(document_id: str, numero: int) -> str:
        """The page id used by the index and the reranker scores: ``<document_id>#p<n>``."""
        return f'{document_id}#p{numero}'

    @classmethod
    def da_dict(cls, x: dict[str, Any]) -> Pagina:
        """A page from one line of the index."""
        return cls(
            id=x['id'],
            doc=x.get('doc', ''),
            file=x.get('file', ''),
            numero=int(x.get('pagina') or 0),
            da=int(x.get('da') or 0),
            a=int(x.get('a') or 0),
            testo=x.get('testo', ''),
        )


@dataclass
class Documento:
    """A document of the corpus (``documento``) as the set of its indexed pages.

    Attributes:
        id: the document id.
        file: the markdown file.
        pagine: pages by number.
    """

    id: str
    file: str = ''
    pagine: dict[int, Pagina] = field(default_factory=dict)

    def pagina(self, numero: int) -> Pagina | None:
        """The page with that number, or ``None``."""
        return self.pagine.get(numero)

    def testo(self, numero: int) -> str:
        """The text of a page, empty if the page is not indexed."""
        p = self.pagine.get(numero)
        return p.testo if p else ''


class IndicePagine:
    """Streaming reader of ``index/pagine/pagine.jsonl.gz`` (``indice delle pagine``)."""

    def __init__(self, percorso: Path | str) -> None:
        self.percorso = Path(percorso)

    def righe(self) -> Iterator[dict[str, Any]]:
        """Every line of the index, decoded, in file order."""
        with gzip.open(self.percorso, 'rt', encoding='utf-8') as f:
            for riga in f:
                yield json.loads(riga)

    def testi(self, ids: Iterable[str]) -> dict[str, str]:
        """Text of the requested pages (``tools/leggi_ripresa.prepara``): missing ids are absent, last line wins."""
        voglio = set(ids)
        out: dict[str, str] = {}
        if not voglio:
            # NOTE: the live code streams the whole index even when no page is needed; the result is the same.
            return out
        for x in self.righe():
            if x['id'] in voglio:
                out[x['id']] = x['testo']
        return out

    def pagine(self, ids: Iterable[str]) -> dict[str, Pagina]:
        """The requested pages as :class:`Pagina` objects."""
        voglio = set(ids)
        return {x['id']: Pagina.da_dict(x) for x in self.righe() if x['id'] in voglio}

    def documento(self, document_id: str) -> Documento:
        """All indexed pages of one document."""
        d = Documento(id=document_id)
        for x in self.righe():
            if x.get('doc') == document_id:
                p = Pagina.da_dict(x)
                d.pagine[p.numero] = p
                d.file = d.file or p.file
        return d


# positions after the OCR (tools/posizione_dopo_ocr.py)

PAGINA_MD = re.compile(r'<!--\s*page\s+(\d+)\s*-->')
"""A page mark of the markdown files."""


def pagine_md(testo: str) -> list[tuple[int, int, int]]:
    """``(start, end, page number)`` of every page of a markdown text."""
    m = [(x.start(), int(x.group(1))) for x in PAGINA_MD.finditer(testo)]
    return [(a, (m[i + 1][0] if i + 1 < len(m) else len(testo)), n) for i, (a, n) in enumerate(m)]


class PosizioniDopoOcr:
    """The position of a row in a document redone with OCR (``tools/posizione_dopo_ocr.py``, 01/10/2026).

    The OCR replaced unreadable pages, so the old ``char_start`` (part of the row id, never changed in the database)
    no longer points at the cited name. The copy of before is in ``training/ocr/prima/<file name>``: an unchanged page
    keeps the same offset from its start; on a redone page the name is searched again (the same occurrence in order,
    else the first; the page start if the name is gone). Rows born after the OCR already have the new position.

    Args:
        radice: the project root.
    """

    def __init__(self, radice: Path | str) -> None:
        self.radice = Path(radice)
        self.prima = self.radice / 'training' / 'ocr' / 'prima'

    def traduci(self, file: str, cs: int, nome_re: re.Pattern[str], nata_dopo_ocr: bool = False) -> tuple[int, str]:
        """``(position in today's file, how it was found)``."""
        vecchio = self.prima / Path(file).name
        if nata_dopo_ocr or not vecchio.exists():
            return cs, 'invariata'
        tv = vecchio.read_text(encoding='utf-8', errors='replace')
        tn = (self.radice / file).read_text(encoding='utf-8', errors='replace')
        pv = [p for p in pagine_md(tv) if p[0] <= cs]
        if not pv:
            return cs, 'prima delle pagine'
        a, b, n = pv[-1]
        nuove = {p[2]: p for p in pagine_md(tn)}
        if n not in nuove:
            return cs, f'pagina {n} assente nel file nuovo'
        na, nb, _ = nuove[n]
        if tv[a:b] == tn[na:nb]:
            return na + (cs - a), 'stessa pagina, spostata'
        k = len(list(nome_re.finditer(tv, a, cs)))
        occ = list(nome_re.finditer(tn, na, nb))
        if not occ:
            return na, f'pagina {n} rifatta, nome non ritrovato'
        return (occ[k] if k < len(occ) else occ[0]).start(), f'pagina {n} rifatta, nome ritrovato'
