"""The loaders that write the machine proposals on the platform rows (``caricatori``: loaders).

- :class:`CaricatoreTipo`: the citation type of the DeepSeek reading (``tools/carica_lessicali.py``);
- :class:`CaricatoreRipresa`: principles, surrounding pages and supported sentence composed by
  :class:`tracepipe.composizione.Composizione` (``tools/carica_ripresa.py``).

Both read the rows of the case from a :class:`tracepipe.banca.BancaDati`, never touch a row with a human verdict, and
write only with ``scrivi=True`` (the live ``--scrivi``), in batches of 400 ``update`` operations, in stream order: the
same writes, with the same content, in the same order as the live scripts. The screen lines are the live ones.
"""

from __future__ import annotations

import collections
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .banca import LOTTO, BancaDati, Scrittura
from .composizione import Composizione, ComposizioneMaggioranza, IngressiComposizione, IngressiMaggioranza
from .config import Config

CATEGORIE = frozenset({'menzione_in_catena', 'descrittiva', 'sostanziale', 'distinguente', 'critica', 'implicita'})
"""The citation types of the codebook (tools/carica_lessicali.py CAT)."""
CHI_PARLA = frozenset({'corte', 'parte', 'interveniente', 'amicus', 'non_determinabile'})
"""Who speaks (tools/carica_lessicali.py CHI)."""
LETTORE_URGENDA = (
    'DeepSeek V4 Flash 0731, codebook 0.2-pilot con la regola sulle note (26/09/2026), seconda lettura 27/09/2026'
)
LETTORE_ALTRI = 'DeepSeek V4 Flash 0731, codebook 0.3-pilot, 28/09/2026'
RIFERIMENTI = {
    'fondazione_urgenda': 'la fondazione Urgenda come soggetto, non la sentenza',
    'soggetto_omonimo': "la persona, la parte o l'organizzazione che porta il nome, non la sentenza",
    'indice_o_elenco': 'indice, tavola delle fonti o elenco senza testo',
    'omonimo': 'altro significato della parola',
    'non_determinabile': 'non determinabile',
}
"""What the name is when it is not the case (tools/carica_lessicali.py RIF)."""
PREFISSO_NOTA = 'DeepSeek, due letture:'
PREFISSO_R11 = 'DeepSeek, letture a maggioranza'

Stampa = Callable[[str], None]


def _stampa(testo: str) -> None:
    print(testo, flush=True)


@dataclass
class EsitoCaricamento:
    """What a loader decided: the writes (row id, fields) and the counts it prints."""

    scritture: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    conti: collections.Counter[str] = field(default_factory=collections.Counter)
    scritte: int = 0


class Caricatore:
    """Shared by the two loaders: rows of the case, batched writes, screen lines.

    Args:
        config: paths.
        caso: the cited case.
        banca: the platform database.
        scrivi: write (``--scrivi``); otherwise a preview.
        stampa: where the screen lines go.
    """

    COLLEZIONE = 'corpus_rows'
    TAGLIO_ESEMPIO = 600

    def __init__(
        self, config: Config, caso: str, banca: BancaDati, scrivi: bool = False, stampa: Stampa = _stampa
    ) -> None:
        self.config = config
        self.caso = caso
        self.banca = banca
        self.scrivi = scrivi
        self.stampa = stampa

    def righe(self) -> list[tuple[str, dict[str, Any]]]:
        """The platform rows of the case, in stream (id) order."""
        return list(self.banca.righe(self.COLLEZIONE, [('caso_citato', '==', self.caso)]))

    def mostra(self, esito: EsitoCaricamento) -> None:
        self.stampa(json.dumps(dict(esito.conti), ensure_ascii=False, indent=1))
        if esito.scritture:
            self.stampa('example: ' + json.dumps(esito.scritture[0][1], ensure_ascii=False)[: self.TAGLIO_ESEMPIO])

    def dopo_conti(self, esito: EsitoCaricamento) -> None:
        """Between the counts and the writes (``--salva`` of the ripresa loader)."""

    def scrivi_tutto(self, esito: EsitoCaricamento) -> int:
        return self.banca.scrivi_a_lotti(
            [Scrittura('update', self.COLLEZIONE, rid, campi) for rid, campi in esito.scritture], dimensione=LOTTO
        )

    def calcola(self) -> EsitoCaricamento:
        raise NotImplementedError

    def esegui(self) -> EsitoCaricamento:
        """Compute, print, and write if asked."""
        esito = self.calcola()
        self.mostra(esito)
        self.dopo_conti(esito)
        if not self.scrivi:
            self.stampa('PREVIEW: nothing written')
            return esito
        esito.scritte = self.scrivi_tutto(esito)
        self.stampa(f'written {esito.scritte} rows')
        return esito


def versione_codebook(x: dict[str, Any]) -> str:
    """The codebook version given to the reader (tools/carica_lessicali.py ``versione_codebook``).

    Since 02/10/2026 the reading writes it; before, it is deduced from the date: 0.4-pilot from 02/10, else 0.3-pilot.
    """
    if x.get('codebook'):
        return x['codebook']
    return '0.4-pilot' if str(x.get('data') or '') >= '2026-10-02' else '0.3-pilot'


class CaricatoreTipo(Caricatore):
    """The proposed citation type, speaker and proposition of the first reading (``tools/carica_lessicali.py``).

    Writes only on lexical rows without a verdict and without a proposed type (``sovrascrivi``: also those with a
    type, when the file has a new reading for them, e.g. rows re-read on the OCR text). ``proposto_note`` keeps the
    notes of the row and replaces the note of an earlier DeepSeek reading (fix of 02/10/2026: 66 rows had two or three).

    Args:
        etichetta: the label of the readings file (``v2`` for Urgenda, empty for the first reading of the others).
        sovrascrivi: ``--sovrascrivi``.
        Other arguments: see :class:`Caricatore`.
    """

    def __init__(
        self,
        config: Config,
        caso: str,
        banca: BancaDati,
        etichetta: str = 'v2',
        sovrascrivi: bool = False,
        composizione: str = '',
        salva: str = '',
        **kw: Any,
    ) -> None:
        super().__init__(config, caso, banca, **kw)
        self.etichetta = etichetta
        self.sovrascrivi = sovrascrivi
        self.composizione = composizione
        self.salva = salva

    def dopo_conti(self, esito: EsitoCaricamento) -> None:
        if self.salva:
            with open(self.salva, 'w', encoding='utf-8') as f:
                json.dump(dict(esito.scritture), f, ensure_ascii=False, default=str)
            self.stampa(f'fields saved in {self.salva}')

    def campi_r11(self, r: dict[str, Any], x: dict[str, Any], vt: dict[str, Any]) -> dict[str, Any]:
        """The type fields with R11 (rules in :mod:`tracepipe.maggioranza`; twin of ``carica_lessicali.campi_r11``)."""
        from . import maggioranza

        p = vt['lettura']
        voti = ', '.join(f'{t} {maggioranza.voti_testo(v, vt["n"])}' for t, v in vt['voti'].items())
        nota = (
            f'{PREFISSO_R11} ({vt["n"]}): {voti}'
            + (" (parita', vince il primo nell'ordine delle letture)" if vt['parita'] else '')
            + '.'
        )
        if p.get('riferimento') and p['riferimento'] not in ('caso_urgenda', 'caso'):
            nota += (
                f" Attenzione: secondo la lettura qui il nome e' {RIFERIMENTI.get(p['riferimento'], p['riferimento'])}."
            )
        if p.get('motivo'):
            nota += f' Motivo: {" ".join(str(p["motivo"]).split())}'
        vecchia = self.note_senza_deepseek(r.get('proposto_note'))
        data = '/'.join(reversed(str(x.get('data') or '')[:10].split('-')))
        return {
            'proposto_tipo_citazione': vt['tipo'],
            'proposto_chi_parla': p.get('chi_parla') if p.get('chi_parla') in CHI_PARLA else '',
            'proposto_proposizione': ' '.join(str(p.get('proposizione') or '').split()),
            'proposto_confidenza': 'bassa' if vt['incerto'] else 'alta',
            'proposto_tipo_voti': {t: maggioranza.voti_testo(v, vt['n']) for t, v in vt['voti'].items()},
            'proposto_tipo_incerto': vt['incerto'],
            'proposto_note': (vecchia + '\n' + nota) if vecchia else nota,
            'proposto_lettore': (
                f'DeepSeek V4 Flash 0731, codebook {versione_codebook(x)}, {data}, '
                f'{vt["n"]} letture a maggioranza (R11)'
            ),
            'provenienza.tipo': 'L02' if self.caso == 'urgenda' else 'L03',
            'provenienza.tipo_composizione': 'R11',
        }

    @property
    def file_letture(self) -> Path:
        return (
            self.config.training
            / f'lessicali_{self.caso}_deepseek{"_" + self.etichetta if self.etichetta else ""}.jsonl'
        )

    @property
    def lettore(self) -> str:
        return LETTORE_URGENDA if self.caso == 'urgenda' else LETTORE_ALTRI

    def letture(self) -> dict[str, dict[str, Any]]:
        ds: dict[str, dict[str, Any]] = {}
        with open(self.file_letture, encoding='utf-8') as f:
            for riga in f:
                x = json.loads(riga)
                ds[x['id']] = x
        return ds

    @staticmethod
    def nota(p: dict[str, Any], tipi: list[Any]) -> str:
        """The note of the reading: the two types, the referent when it is not the case, the reason."""
        nota = f'{PREFISSO_NOTA} {" / ".join(t or "?" for t in tipi)}.'
        if p.get('riferimento') and p['riferimento'] not in ('caso_urgenda', 'caso'):
            nota += (
                f" Attenzione: secondo la lettura qui il nome e' {RIFERIMENTI.get(p['riferimento'], p['riferimento'])}."
            )
        if p.get('motivo'):
            nota += f' Motivo: {" ".join(str(p["motivo"]).split())}'
        return nota

    @staticmethod
    def note_senza_deepseek(note: Any) -> str:
        """The notes of the row without the lines of an earlier DeepSeek reading (two readings or R11)."""
        return '\n'.join(
            r for r in str(note or '').split('\n') if not r.startswith(PREFISSO_NOTA) and not r.startswith(PREFISSO_R11)
        ).strip()

    def campi(self, r: dict[str, Any], x: dict[str, Any], tipo: str, tipi: list[Any]) -> dict[str, Any]:
        p = x['letture'][0]
        nota = self.nota(p, tipi)
        vecchia = self.note_senza_deepseek(r.get('proposto_note'))
        if self.caso == 'urgenda' and not x.get('codebook'):
            lettore = self.lettore
        else:
            data = '/'.join(reversed(str(x.get('data') or '2026-09-28')[:10].split('-')))
            lettore = f'DeepSeek V4 Flash 0731, codebook {versione_codebook(x)}, {data}'
        return {
            'proposto_tipo_citazione': tipo,
            'proposto_chi_parla': p.get('chi_parla') if p.get('chi_parla') in CHI_PARLA else '',
            'proposto_proposizione': ' '.join(str(p.get('proposizione') or '').split()),
            'proposto_confidenza': 'alta' if len(set(tipi)) == 1 else 'bassa',
            'proposto_note': (vecchia + '\n' + nota) if vecchia else nota,
            'proposto_lettore': lettore,
            'provenienza.tipo': 'L02' if self.caso == 'urgenda' else 'L03',
        }

    def calcola(self) -> EsitoCaricamento:
        ds = self.letture()
        esito = EsitoCaricamento()
        conti = esito.conti
        for rid, r in self.righe():
            if r.get('proposto_rete') not in ('lessicale', 'entrambe', 'descrittiva'):
                continue
            if r.get('esito'):
                conti['gia giudicata (non toccata)'] += 1
                continue
            if self.composizione == 'R11':
                self.una_r11(rid, r, ds, esito)
                continue
            if r.get('proposto_tipo_citazione') and not (self.sovrascrivi and rid in ds):
                conti['tipo gia proposto (non toccata)'] += 1
                continue
            x = ds.get(rid)
            if not x:
                conti['senza lettura'] += 1
                continue
            g = x['letture']
            p = g[0]
            tipo = p.get('tipo_citazione') if p.get('tipo_citazione') in CATEGORIE else ''
            if not tipo:
                conti['lettura illeggibile'] += 1
                continue
            tipi = [y.get('tipo_citazione') for y in g]
            concordi = len(set(tipi)) == 1
            esito.scritture.append((rid, self.campi(r, x, tipo, tipi)))
            conti['da scrivere'] += 1
            conti[f'tipo {tipo}'] += 1
            conti['concordi' if concordi else 'discordi'] += 1
        return esito

    def una_r11(self, rid: str, r: dict[str, Any], ds: dict[str, dict[str, Any]], esito: EsitoCaricamento) -> None:
        from . import maggioranza

        conti = esito.conti
        x = ds.get(rid)
        if not x:
            conti['senza lettura (non toccata)'] += 1
            return
        vt = maggioranza.voto_tipo(x.get('letture') or [])
        if not vt:
            conti['nessuna lettura valida (non toccata)'] += 1
            return
        esito.scritture.append((rid, self.campi_r11(r, x, vt)))
        conti['da scrivere'] += 1
        conti[f'tipo {vt["tipo"]}'] += 1
        conti[f'letture valide {vt["n"]}'] += 1
        conti['incerto' if vt['incerto'] else 'margine almeno 2'] += 1
        conti['parita'] += vt['parita']
        if r.get('proposto_tipo_citazione') and r['proposto_tipo_citazione'] != vt['tipo']:
            conti['tipo cambiato'] += 1


class CaricatoreRipresa(Caricatore):
    """The proposals of principles, surrounding pages and sentence (``tools/carica_ripresa.py``, rule R05).

    Args:
        principi_da_l04: principles from the L04 reading, the rest from L05 (``--principi-da-l04``).
        anche_senza_lettura: also rows DeepSeek has not read (provisional proposal, ``--anche-senza-lettura``).
        salva: a JSON file where the computed proposals are saved (``--salva``), relative to the working folder.
        compat: the live defects fixed on 02/10/2026 (see :class:`tracepipe.composizione.Composizione`).
        Other arguments: see :class:`Caricatore`.
    """

    TAGLIO_ESEMPIO = 700

    def __init__(
        self,
        config: Config,
        caso: str,
        banca: BancaDati,
        principi_da_l04: bool = False,
        anche_senza_lettura: bool = False,
        salva: str = '',
        compat: bool = False,
        composizione: str = 'R05',
        etichetta: str = '',
        etichetta_tipo: str = 'cinque',
        **kw: Any,
    ) -> None:
        super().__init__(config, caso, banca, **kw)
        self.principi_da_l04 = principi_da_l04
        self.anche_senza_lettura = anche_senza_lettura
        self.salva = salva
        self.compat = compat
        self.composizione = composizione
        self.etichetta = etichetta
        self.etichetta_tipo = etichetta_tipo

    def calcola(self) -> EsitoCaricamento:
        if self.composizione == 'R11':
            r11 = ComposizioneMaggioranza.per_caso(self.config, self.caso, compat=self.compat)
            ing = IngressiMaggioranza.carica(
                self.config, self.caso, self.etichetta, self.etichetta_tipo, pagine_intere=not self.compat
            )
            scritture, conti = r11.componi_r11(self.righe(), ing)
            return EsitoCaricamento(scritture=scritture, conti=conti)
        composizione = Composizione.per_caso(self.config, self.caso, compat=self.compat)
        ingressi = IngressiComposizione.carica(
            self.config, self.caso, principi_da_l04=self.principi_da_l04, pagine_intere=not self.compat
        )
        scritture, conti = composizione.componi(self.righe(), ingressi, self.anche_senza_lettura)
        return EsitoCaricamento(scritture=scritture, conti=conti)

    def dopo_conti(self, esito: EsitoCaricamento) -> None:
        if self.salva:
            with open(self.salva, 'w', encoding='utf-8') as f:
                json.dump(dict(esito.scritture), f, ensure_ascii=False, default=str)
            self.stampa(f'proposals saved in {self.salva}')
