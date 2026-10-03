"""The cited case: :class:`CasoCitato`, its probe series :class:`SerieSonde`, its paragraph map :class:`MappaParagrafi`.

A *cited case* (``caso citato``: Urgenda, Neubauer...) is described by ``cited-cases/<case>.yaml``: its name, the
lexical forms under which it is cited (``forme``) and its *probes* (``sonde``, the ``semantic_queries``: the
principles of the case, one proposition each). A *probe series* (``serie di sonde``, P01...P09) is a versioned set of
probes; a series on trial lives in ``cited-cases/<case>-<series>.yaml``. The *paragraph map* (``mappa dei
paragrafi``, ``cited-cases/<case>-mappa-paragrafi.yaml``, written by hand) says which principles each paragraph of
the judgment carries; ``tools/principi_da_paragrafi.py`` uses it to read the principles off the paragraph numbers a
citation gives.
"""

from __future__ import annotations

import collections
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .config import Config

# lexical forms (tools/cerca.py)

CJK = re.compile(r'[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\uf900-\ufaff]')
"""Japanese, Chinese and Korean characters (tools/cerca.py CJK)."""


def forma_regex(forma: str) -> str:
    """A lexical form as a regular expression (tools/cerca.py ``forma_regex``).

    For Japanese, Chinese and Korean forms a space or a line break is allowed between characters (in those texts a
    line break can fall inside a word); Latin-script forms stay exact.
    """
    if not CJK.search(forma):
        return re.escape(forma)
    return r'\s*'.join(re.escape(c) for c in forma if not c.isspace())


MENZIONE_URGENDA = re.compile(r'urgenda|ECLI:NL:(?:HR|GHDHA|RBDHA):20(?:19|18|15):\d+', re.I)
"""How a mention of Urgenda is found by the paragraph map (tools/principi_da_paragrafi.py)."""


def _yaml(percorso: Path) -> Any:
    with open(percorso, encoding='utf-8') as f:
        return yaml.safe_load(f)


def _uno_spazio(t: Any) -> str:
    """Collapse every run of whitespace to one space (the probes are written over several YAML lines)."""
    return ' '.join(str(t).split())


# probes


@dataclass(frozen=True)
class Sonda:
    """One probe (``sonda``): a principle of the cited case.

    Attributes:
        id: the principle id (``neubauer.budget_residuo``).
        titolo: the title.
        testo: the proposition.
        paragrafi: the paragraphs that define it, as written in the file (may be empty).
    """

    id: str
    titolo: str = ''
    testo: str = ''
    paragrafi: str = ''


@dataclass(frozen=True)
class SerieSonde:
    """The probes of a case in one series (``serie di sonde``).

    Attributes:
        caso: the cited case.
        codice: the register code of the series (``P05``; ``P01``/``P02`` for the historical files).
        file: the YAML file the probes were read from.
        sonde: the probes in file order.
    """

    caso: str
    codice: str
    file: Path
    sonde: tuple[Sonda, ...] = ()

    @classmethod
    def carica(cls, config: Config, caso: str) -> SerieSonde:
        """The probes of the series in use for ``caso`` (``config.file_caso``)."""
        f = config.file_caso(caso)
        sq = _yaml(f)['semantic_queries']
        sonde = tuple(
            Sonda(
                id=s['id'], titolo=s.get('titolo', ''), testo=s.get('testo', ''), paragrafi=s.get('paragrafi', '') or ''
            )
            for s in sq
        )
        return cls(caso=caso, codice=config.codice(caso), file=f, sonde=sonde)

    @property
    def ids(self) -> list[str]:
        """Principle ids in file order (duplicates kept, as ``tools/carica_ripresa.carica``)."""
        return [s.id for s in self.sonde]

    def testi(self) -> dict[str, tuple[str, str]]:
        """``id -> (title, text)`` with whitespace collapsed (tools/carica_ripresa.py PRINCIPI_TESTO)."""
        return {s.id: (_uno_spazio(s.titolo), _uno_spazio(s.testo)) for s in self.sonde}

    def testi_prompt(self) -> list[str]:
        """Every title and text that goes into a prompt: what invented evidence would be copied from."""
        t = self.testi()
        return [x for k in self.ids for x in (t.get(k) or ())]

    def elenco_prompt(self) -> str:
        """The principle list of the L05 prompt (tools/leggi_ripresa.py ``leggi``)."""
        return '\n'.join(f'- {s.id}: {_uno_spazio(s.titolo)}. {_uno_spazio(s.testo)}' for s in self.sonde)


# the cited case


@dataclass(frozen=True)
class CasoCitato:
    """A cited case and the way its name is found in a text (``caso citato``).

    Attributes:
        caso: the case key (``urgenda``, ``neubauer``...).
        nome: the full name.
        forme: the lexical forms of the base case file, as written.
        data_decisione: the decision date as text (YAML dates become ``YYYY-MM-DD``).
        dati: the whole base case file.
    """

    caso: str
    nome: str = ''
    forme: tuple[str, ...] = ()
    data_decisione: str = ''
    dati: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def carica(cls, config: Config, caso: str) -> CasoCitato:
        """Read ``cited-cases/<caso>.yaml`` (the base file: forms do not depend on the probe series)."""
        d = _yaml(config.cited_cases / f'{caso}.yaml') or {}
        dd = d.get('data_decisione')
        dd = dd.isoformat()[:10] if hasattr(dd, 'isoformat') else str(dd or '')
        return cls(
            caso=caso, nome=str(d.get('nome') or ''), forme=tuple(d.get('forme') or ()), data_decisione=dd, dati=d
        )

    def forme_lunghe(self) -> list[str]:
        """Distinct forms of at least four characters, longest first (shorter ones are too ambiguous).

        Ties keep the order of ``sorted`` on a set, which is the order the live scripts get from the same set.
        """
        return sorted({str(f) for f in self.forme if len(str(f)) >= 4}, key=len, reverse=True)

    def nome_re(self) -> re.Pattern[str]:
        """How the name is found around a row (tools/classifica_lessicali.py ``prepara``).

        Urgenda is found as ``urgenda`` alone; the other cases by their long forms. Japanese, Chinese and Korean
        forms are appended with :func:`forma_regex`.
        """
        forme = self.forme_lunghe()
        r = (
            re.compile('|'.join(re.escape(f) for f in forme), re.I)
            if self.caso != 'urgenda'
            else re.compile(r'urgenda', re.I)
        )
        asiatiche = [f for f in forme if CJK.search(f)]
        if asiatiche:
            r = re.compile(r.pattern + '|' + '|'.join(forma_regex(f) for f in asiatiche), re.I)
        return r

    def menzione_re(self) -> re.Pattern[str]:
        """How a mention is found by the paragraph map (tools/principi_da_paragrafi.py ``main``).

        Urgenda also by its ECLI numbers; the other cases by their long forms, without the CJK variant.
        """
        if self.caso == 'urgenda':
            return MENZIONE_URGENDA
        return re.compile('|'.join(re.escape(f) for f in self.forme_lunghe()), re.I)


# the paragraph map

# A paragraph reference: the marker, then numbers, ranges and lists ("paras. 5.7.5-5.7.6", "Rn. 254").
PAR = re.compile(
    r'(?:paras?\.?|paragraphs?|p[áa]rrs?\.?|par[áa]grafos?|§§?|¶¶?|r\.\s?o\.|rov\.|rn\.|randnummer'
    r'|margin\s+(?:nos?\.|numbers?))\s*'
    r'((?:\d{1,3}(?:\.\d{1,3}){0,2})(?!\d)'
    r'(?:\s*(?:[-\u2013]|to|and|&|,)\s*\d{1,3}(?:\.\d{1,3}){0,2}(?![\d/]))*)',
    re.I,
)
# Which Urgenda judgment a reference points at, decided from the nearby words.
CORTE = (
    ('hoge_raad_2019', re.compile(r'supreme court|hoge raad|\bHR\b|2019', re.I)),
    ('hof_2018', re.compile(r'court of appeal|gerechtshof|\bhof\b|2018', re.I)),
    ('rechtbank_2015', re.compile(r'district court|rechtbank|2015', re.I)),
)
_SEGNO = re.compile(r'^\s*(?:§§?|paras?\.?|Rn\.|p[áa]rrs?\.?)\s*', re.I)
_PAGINA_CITAZIONE = '===== PAGINA DELLA CITAZIONE ====='
_PAGINA_SUCCESSIVA = '===== PAGINA SUCCESSIVA'


def _chiave(n: str) -> tuple[int, ...]:
    return tuple(int(x) for x in n.split('.'))


class MappaParagrafi:
    """Judgment -> paragraph -> principles, and the principles a citation takes from the paragraphs it cites.

    Args:
        caso: the cited case.
        per: ``{judgment: {paragraph: [principle ids]}}``; Neubauer and the others have one judgment, ``unica``.
        menzione: how a mention of the case is found in the citation page.
    """

    METODO = 'mappa dei paragrafi'

    def __init__(self, caso: str, per: Mapping[str, Mapping[str, list[str]]], menzione: re.Pattern[str]) -> None:
        self.caso = caso
        self.per = per
        self.menzione = menzione

    @classmethod
    def carica(cls, config: Config, caso: str, serie: str = '') -> MappaParagrafi:
        """Read the map; ``serie`` (``'P05'``) uses the field ``sonde_<serie>`` instead of ``sonde``."""
        campo = 'sonde_' + serie if serie else 'sonde'
        per = cls.leggi_mappa(config, caso, campo)
        # Urgenda is found by name and ECLI without reading its case file (as live: the file is not opened)
        menzione = MENZIONE_URGENDA if caso == 'urgenda' else CasoCitato.carica(config, caso).menzione_re()
        return cls(caso, per, menzione)

    @staticmethod
    def espandi(p: Any) -> list[str]:
        """``'4.11-4.19'`` -> every paragraph of the range; a single number -> itself; anything else -> nothing.

        Ranges whose ends differ in depth or prefix, run backwards, or span more than 60 numbers give their two ends.
        """
        p = str(p).strip()
        m = re.fullmatch(r'(\d+(?:\.\d+)*)\s*-\s*(\d+(?:\.\d+)*)', p)
        if not m:
            return [p] if re.fullmatch(r'\d+(?:\.\d+)*', p) else []
        a, b = _chiave(m.group(1)), _chiave(m.group(2))
        if len(a) != len(b) or a[:-1] != b[:-1] or b[-1] < a[-1] or b[-1] - a[-1] > 60:
            return [m.group(1), m.group(2)]
        return ['.'.join(map(str, (*a[:-1], k))) for k in range(a[-1], b[-1] + 1)]

    @classmethod
    def numeri(cls, testo: str) -> list[str]:
        """The paragraph numbers of a reference (``'5.7.5-5.7.7, 5.8 and 6'``)."""
        out: list[str] = []
        for pezzo in re.split(r'\s*(?:,|and|&)\s*', testo):
            m = re.fullmatch(r'(\d+(?:\.\d+)*)\s*(?:[-\u2013]|to)\s*(\d+(?:\.\d+)*)', pezzo.strip())
            if m:
                out += cls.espandi(f'{m.group(1)}-{m.group(2)}')
            elif re.fullmatch(r'\d+(?:\.\d+)*', pezzo.strip()):
                out.append(pezzo.strip())
        return out

    @classmethod
    def leggi_mappa(cls, config: Config, caso: str, campo: str = 'sonde') -> dict[str, dict[str, list[str]]]:
        """The map from the YAML file (tools/principi_da_paragrafi.py ``mappa``).

        In the maps of Neubauer and Future Generations the principles are written without the case prefix their ids
        have in the case files: it is added here. The Neubauer series of 01/10/2026 are defined by Randnummer
        (``paragrafi`` of each probe): every Rn of those ranges carries the probe, even where the map has no entry.
        """
        per: dict[str, dict[str, list[str]]] = collections.defaultdict(dict)
        for v in _yaml(config.cited_cases / f'{caso}-mappa-paragrafi.yaml')['voci']:
            pr = v.get('pronuncia') or 'unica'
            sonde = [
                s if caso == 'urgenda' or s.startswith(caso + '.') else f'{caso}.{s}' for s in (v.get(campo) or [])
            ]
            par_ = str(v.get('paragrafo', v.get('paragrafi', '')))
            for n in cls.espandi(_SEGNO.sub('', par_)):
                per[pr][n] = sorted(set(per[pr].get(n, [])) | set(sonde))
        if campo.startswith('sonde_P') and caso == 'neubauer':
            for q in _yaml(config.cited_cases / f'{caso}-{campo.split("_")[1]}.yaml')['semantic_queries']:
                testo = q.get('paragrafi', '').split(';')[0]
                nums = {n for a, b in re.findall(r'(\d+)\s*-\s*(\d+)', testo) for n in range(int(a), int(b) + 1)}
                nums |= {int(x) for x in re.findall(r'(?<![\d-])(\d+)(?![\d-])', testo)}
                for n in nums:
                    per['unica'][str(n)] = sorted(set(per['unica'].get(str(n), [])) | {q['id']})
        return per

    @staticmethod
    def pagina_citazione(contesto: str) -> str:
        """The citation page out of a row context (from its header to the next page header)."""
        i = contesto.find(_PAGINA_CITAZIONE)
        j = contesto.find(_PAGINA_SUCCESSIVA, i + 1)
        return contesto[i : j if j > 0 else None] if i >= 0 else contesto

    def _corte(self, pag: str, m: re.Match[str]) -> str | None:
        """The Urgenda judgment named around a mention (only for Urgenda)."""
        if self.caso != 'urgenda':
            return None
        intorno = pag[max(0, m.start() - 120) : m.end() + 250]
        return next((c for c, rx in CORTE if rx.search(intorno)), None)

    def trovati(self, contesto: str) -> list[tuple[str, str, tuple[str, ...]]]:
        """``(judgment, paragraph, principles)`` for every paragraph cited after a mention of the case.

        After each mention the reference is searched in the next 250 characters, cut at the first semicolon (after it
        there is usually another case with its own paragraphs). A paragraph that exists in several judgments counts
        only if the judgment is named nearby.
        """
        pag = self.pagina_citazione(contesto)
        out: list[tuple[str, str, tuple[str, ...]]] = []
        for m in self.menzione.finditer(pag):
            fin = pag[m.start() : m.end() + 250].split(';')[0]
            for p in PAR.finditer(fin):
                nums = self.numeri(p.group(1))
                corte = self._corte(pag, m)
                for n in nums:
                    in_corte = corte is not None and n in self.per.get(corte, {})
                    dove = [corte] if in_corte else [c for c in self.per if n in self.per[c]]
                    if len(dove) == 1:
                        out.append((dove[0], n, tuple(self.per[dove[0]][n])))
        return out

    def principi_riga(self, riga: Mapping[str, Any]) -> dict[str, Any]:
        """The output line of ``tools/principi_da_paragrafi.py`` for one row."""
        t = self.trovati(riga['contesto'])
        return {
            'id': riga['id'],
            'paragrafi': sorted({f'{c}:{n}' for c, n, _ in t}),
            'principi': sorted({s for _, _, ss in t for s in ss}),
            'metodo': self.METODO,
        }

    def principi_righe(
        self, righe: Iterable[Mapping[str, Any]]
    ) -> tuple[list[dict[str, Any]], collections.Counter[str]]:
        """Output lines for every row, with the counts printed by the live script."""
        conti: collections.Counter[str] = collections.Counter()
        out = []
        for r in righe:
            x = self.principi_riga(r)
            stato = (
                'nessun paragrafo'
                if not x['paragrafi']
                else ('paragrafo senza principio' if not x['principi'] else 'principio dai paragrafi')
            )
            conti[stato] += 1
            out.append(x)
        return out, conti
