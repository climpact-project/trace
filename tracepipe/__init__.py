"""TRACE pipeline, class-based rewrite of ``tools/`` (``tracepipe``; phase 1 foundation, phase 2 runs and cycles).

Every class reproduces a live script of ``tools/`` exactly; acceptance is mechanical against the reference harness
in ``prove/`` (``prove/esegui_pacchetto.py`` and ``prove/confronta.py``). Domain names stay in Italian where they are
the project's vocabulary.

Phase 1, logic:

- :mod:`.config`: :class:`Config` (paths, cases, probe series, thresholds, DeepSeek caps);
- :mod:`.corpus`: :class:`Pagina`, :class:`Documento`, :class:`IndicePagine` (page index), :class:`PosizioniDopoOcr`;
- :mod:`.caso`: :class:`CasoCitato` (cited case), :class:`SerieSonde` (probe series), :class:`MappaParagrafi`;
- :mod:`.freni`: :class:`Freni` (brakes against invented answers);
- :mod:`.deepseek`: :class:`ClienteDeepSeek` (DeepSeek client with the retry policy and the call record);
- :mod:`.letture`: :class:`Lettura` (reading) and the answer parsers;
- :mod:`.pagine_attorno`: :class:`SceltaPagineAttorno` (choice of the surrounding pages, R08);
- :mod:`.composizione`: :class:`Composizione` (composition of the proposals, R05).

Phase 2, runs:

- :mod:`.banca`: :class:`BancaDati` (platform database), :class:`BancaDatiFirestore`, :class:`BancaDatiMemoria`;
- :mod:`.giornale`: :class:`Giornale` (operations journal);
- :mod:`.istruzioni` and :mod:`.lettori`: :class:`LettoreTipo` (L02/L03), :class:`LettorePrincipi` (L04),
  :class:`LettorePagineAttorno` (L05);
- :mod:`.caricatori`: :class:`CaricatoreTipo`, :class:`CaricatoreRipresa`;
- :mod:`.controlli`: :class:`ControlloCompletezza`, :class:`ControlloFinestra`;
- :mod:`.dimensioni` and :mod:`.ricerca`: :class:`RicercaPerNome` (lexical network), :class:`UnioneRighe`;
- :mod:`.orchestratore`: :class:`Orchestratore`, :class:`CicloVuote` (the shell cycles in Python);
- :mod:`.cli`: the ``trace`` command.

Phase 3, clean-up steps (4 and 5 October 2026), each the class-based twin of a tool of ``tools/``:

- :mod:`.righe` and :mod:`.copia_prima`: what the steps share about a row, and :class:`CopiaPrima` (the full copy
  kept before every write, :class:`CopiaNonRiuscitaError` if it cannot be read back);
- :mod:`.unione_c03`: C03, body text and footnote, translations, counted once (:class:`UnioneC03`,
  :class:`GeneratoreCoppie`, :class:`CoppieRivedute`);
- :mod:`.pagine_gia_citate`: C07, a surrounding page that is a citation of its own (:class:`ApplicaC07`,
  :class:`RiconoscitorePagine`);
- :mod:`.coppia`, :mod:`.coppie_vicine`, :mod:`.lettura_coppia`, :mod:`.decisione_coppie`, :mod:`.carica_s08`: S08,
  the close pairs: the candidate pair and its clues (:class:`Coppia`), the links and the threshold
  (:class:`CoppieVicine`, :class:`Taratura`), question L13 and its readers (:class:`DomandaL13`,
  :class:`LettoreCoppie`), the decision (:class:`Decisore`, never writes) and the loader of the new rows
  (:class:`CaricaS08`);
- :mod:`.prova_intera`: :class:`FreniProvaIntera`, the brakes of R14 and R16 (the whole proof, no system marks).

``compat=True`` (``trace --compat``) reproduces four live defects fixed in the package on 02/10/2026 (a row without a
page searched from page 0, provenance L04 after a fallback to L05, ``principi`` as a string, rule R03 on each page),
the record format of the harness tools and the old screen count of split citations in ``trace unisci`` (groups with
nothing to merge included; changed on 03/10/2026); the default ``compat=False`` is the fixed behaviour.
"""

from .banca import BancaDati, BancaDatiFirestore, BancaDatiMemoria
from .carica_s08 import CaricaS08
from .caricatori import CaricatoreRipresa, CaricatoreTipo
from .caso import CasoCitato, MappaParagrafi, SerieSonde, Sonda
from .composizione import Composizione, IngressiComposizione
from .config import Config, LimitiDeepSeek, SoglieFinestra
from .controlli import ControlloCompletezza, ControlloFinestra
from .copia_prima import CopiaNonRiuscitaError, CopiaPrima
from .coppia import Coppia
from .coppie_vicine import CoppieVicine, Taratura
from .corpus import Documento, IndicePagine, Pagina, PosizioniDopoOcr
from .decisione_coppie import Decisione, DecisioneCoppie, Decisore
from .deepseek import ClienteDeepSeek
from .freni import FRENI, Freni
from .giornale import Giornale
from .lettori import Lettore, LettorePagineAttorno, LettorePrincipi, LettoreTipo
from .lettura_coppia import DomandaL13, LettoreCoppie
from .letture import Lettura, estrai, estrai_tollerante, vuota
from .orchestratore import CicloVuote, Orchestratore, Passo, TrasportoFinto, TrasportoSsh
from .pagine_attorno import Punteggi, SceltaPagineAttorno
from .pagine_gia_citate import ApplicaC07, RiconoscitorePagine
from .prova_intera import FreniProvaIntera
from .ricerca import RicercaPerNome, UnioneRighe
from .unione_c03 import CoppieRivedute, GeneratoreCoppie, UnioneC03

__all__ = [
    'FRENI',
    'ApplicaC07',
    'BancaDati',
    'BancaDatiFirestore',
    'BancaDatiMemoria',
    'CaricaS08',
    'CaricatoreRipresa',
    'CaricatoreTipo',
    'CasoCitato',
    'CicloVuote',
    'ClienteDeepSeek',
    'Composizione',
    'Config',
    'ControlloCompletezza',
    'ControlloFinestra',
    'CopiaNonRiuscitaError',
    'CopiaPrima',
    'Coppia',
    'CoppieRivedute',
    'CoppieVicine',
    'Decisione',
    'DecisioneCoppie',
    'Decisore',
    'Documento',
    'DomandaL13',
    'Freni',
    'FreniProvaIntera',
    'GeneratoreCoppie',
    'Giornale',
    'IndicePagine',
    'IngressiComposizione',
    'Lettore',
    'LettoreCoppie',
    'LettorePagineAttorno',
    'LettorePrincipi',
    'LettoreTipo',
    'Lettura',
    'LimitiDeepSeek',
    'MappaParagrafi',
    'Orchestratore',
    'Pagina',
    'Passo',
    'PosizioniDopoOcr',
    'Punteggi',
    'RicercaPerNome',
    'RiconoscitorePagine',
    'SceltaPagineAttorno',
    'SerieSonde',
    'SoglieFinestra',
    'Sonda',
    'Taratura',
    'TrasportoFinto',
    'TrasportoSsh',
    'UnioneC03',
    'UnioneRighe',
    'estrai',
    'estrai_tollerante',
    'vuota',
]

__version__ = '0.2.0'
