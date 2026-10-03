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

``compat=True`` (``trace --compat``) reproduces four live defects fixed in the package on 02/10/2026 (a row without a
page searched from page 0, provenance L04 after a fallback to L05, ``principi`` as a string, rule R03 on each page) and
the record format of the harness tools; the default ``compat=False`` is the fixed behaviour.
"""

from .banca import BancaDati, BancaDatiFirestore, BancaDatiMemoria
from .caricatori import CaricatoreRipresa, CaricatoreTipo
from .caso import CasoCitato, MappaParagrafi, SerieSonde, Sonda
from .composizione import Composizione, IngressiComposizione
from .config import Config, LimitiDeepSeek, SoglieFinestra
from .controlli import ControlloCompletezza, ControlloFinestra
from .corpus import Documento, IndicePagine, Pagina, PosizioniDopoOcr
from .deepseek import ClienteDeepSeek
from .freni import FRENI, Freni
from .giornale import Giornale
from .lettori import Lettore, LettorePagineAttorno, LettorePrincipi, LettoreTipo
from .letture import Lettura, estrai, estrai_tollerante, vuota
from .orchestratore import CicloVuote, Orchestratore, Passo, TrasportoFinto, TrasportoSsh
from .pagine_attorno import Punteggi, SceltaPagineAttorno
from .ricerca import RicercaPerNome, UnioneRighe

__all__ = [
    'FRENI',
    'BancaDati',
    'BancaDatiFirestore',
    'BancaDatiMemoria',
    'CaricatoreRipresa',
    'CaricatoreTipo',
    'CasoCitato',
    'CicloVuote',
    'ClienteDeepSeek',
    'Composizione',
    'Config',
    'ControlloCompletezza',
    'ControlloFinestra',
    'Documento',
    'Freni',
    'Giornale',
    'IndicePagine',
    'IngressiComposizione',
    'Lettore',
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
    'SceltaPagineAttorno',
    'SerieSonde',
    'SoglieFinestra',
    'Sonda',
    'TrasportoFinto',
    'TrasportoSsh',
    'UnioneRighe',
    'estrai',
    'estrai_tollerante',
    'vuota',
]

__version__ = '0.2.0'
