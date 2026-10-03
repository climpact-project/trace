"""The command line of the package: ``trace <command>`` (``[project.scripts] trace = 'tracepipe.cli:main'``).

Commands, each the class-based twin of a live script of ``tools/``:

=================================  ==============================================================
``trace cerca``                    ``cerca.py --solo-lessicale`` (lexical network only)
``trace unisci``                   ``unisci_e_aggiungi.py``
``trace prepara paragrafi``        ``principi_da_paragrafi.py``
``trace prepara pagine-attorno``   ``leggi_ripresa.py prepara`` (``--regola R10``)
``trace leggi tipo``               ``classifica_lessicali.py leggi`` (L02/L03)
``trace leggi principi``           ``leggi_l04.py leggi`` (L04)
``trace leggi pagine-attorno``     ``leggi_ripresa.py leggi`` (L05)
``trace carica tipo``              ``carica_lessicali.py``
``trace carica ripresa``           ``carica_ripresa.py``
``trace controlla completezza``    ``controllo_completezza.py``
``trace controlla finestra``       ``controllo_finestra.py``
=================================  ==============================================================

Same options as the live scripts, and the same convention: nothing is written to the platform without ``--scrivi``
(the readers write their reading files, as live; they never touch the platform). Global options: ``--radice`` (the
project root; default ``$TRACE_RADICE`` or the folder that contains the package), ``--compat`` (reproduce the live
defects fixed on 02/10/2026 and the harness record format), ``--senza-giornale``. Every run is written in the
operations journal (:mod:`tracepipe.giornale`).
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .config import Config
from .letture import LETTURE_PROTOCOLLO

PREDEFINITA = Path(__file__).resolve().parent.parent


def _radice(valore: str) -> Path:
    return Path(valore or os.environ.get('TRACE_RADICE') or PREDEFINITA).resolve()


# Which options reproduce which registry version (versioni/registro.json). The CSV and reading files do not record
# the flags; the operations journal does, for every run. Suggested by the external review of 03/10/2026.
VERSIONI_E_OPZIONI = """\
reproducing a registry version (see versioni/registro.json; the journal records the flags of every run):
  S05 name search (in use)        trace cerca --caso C --solo-lessicale      (duplicates removed across the corpus)
  per-filing dedup (not S05)      trace cerca ... --dedup-per-atto           (copies dropped only within a filing)
  S06 copies in another case      tools/recupero_s06.py                      (not in the package yet)
  R08 surrounding pages           trace prepara pagine-attorno --regola R08  (default)
  R10 surrounding pages (in use)  trace prepara pagine-attorno --regola R10
  L05 with five readings          trace leggi pagine-attorno --letture 5     (default; --letture 2 = before 02/10)
  R05 composition                 trace carica ripresa --composizione R05    (default)
  R11 majority of five (in use)   trace carica ripresa --composizione R11; trace carica tipo --composizione R11
  harness / old outputs           trace --compat ...   reproduces the four live defects fixed on 02/10/2026
                                                       and the old split-citation count of trace unisci (03/10/2026)
nothing is written to the platform without --scrivi.
"""


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog='trace',
        description='TRACE pipeline (pacchetto tracepipe)',
        epilog=VERSIONI_E_OPZIONI,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument('--radice', default='', help='la radice del progetto (predefinita: $TRACE_RADICE o ~/sabin-corpus)')
    ap.add_argument(
        '--compat', action='store_true', help='i difetti vivi corretti il 02/10/2026 (per il banco di prova)'
    )
    ap.add_argument('--senza-giornale', action='store_true', help='non scrive nel giornale delle operazioni')
    sub = ap.add_subparsers(dest='comando', required=True)

    c = sub.add_parser('cerca', help='la ricerca per nome (rete lessicale)')
    c.add_argument('--caso', required=True)
    c.add_argument('--uscita', default='')
    c.add_argument('--solo-lessicale', action='store_true')
    c.add_argument('--con-alternative', action='store_true')
    c.add_argument('--solo-decisioni', action='store_true')
    c.add_argument('--tipo-atto', default='')
    c.add_argument('--con-anteriori', action='store_true')
    c.add_argument('--k', type=int, default=100, help='(rete semantica: non usato)')
    c.add_argument(
        '--dedup-per-atto',
        action='store_true',
        help='copie tolte solo dentro lo stesso atto; fra atti diversi restano, con stesso_testo_di (non in uso)',
    )

    u = sub.add_parser('unisci', help='unire le citazioni spezzate e aggiungere le mancanti')
    u.add_argument('--caso', default='')
    u.add_argument('--data', default='2026-09-29')
    u.add_argument('--scrivi', action='store_true')

    p = sub.add_parser('prepara', help='le righe per i lettori')
    ps = p.add_subparsers(dest='cosa', required=True)
    pp = ps.add_parser('paragrafi', help='la mappa dei paragrafi')
    pp.add_argument('--caso', default='urgenda')
    pp.add_argument('--sonde', default='')
    pa = ps.add_parser('pagine-attorno', help='le pagine attorno scelte dal reranker (R08, o R10)')
    pa.add_argument('--caso', default='urgenda')
    pa.add_argument(
        '--regola', default='R08', choices=['R08', 'R10'], help='R10: soglia 0,5 a ogni distanza, senza tetto'
    )
    pa.add_argument('--etichetta', default='', help='il file <caso>_ripresa_righe_<etichetta>.jsonl (R10 la vuole)')

    lg = sub.add_parser('leggi', help='le letture di DeepSeek')
    ls = lg.add_subparsers(dest='lettore', required=True)
    for nome, etichetta in (('tipo', ''), ('principi', 'l04nuove'), ('pagine-attorno', '')):
        x = ls.add_parser(nome)
        x.add_argument('--caso', default='urgenda')
        x.add_argument(
            '--letture',
            type=int,
            default=LETTURE_PROTOCOLLO,
            help=f'letture per riga (predefinite {LETTURE_PROTOCOLLO}, il protocollo misurato di R11)',
        )
        x.add_argument('--paralleli', type=int, default=48)
        x.add_argument('--etichetta', default=etichetta)
        x.add_argument('--solo-vuote', action='store_true')
        x.add_argument(
            '--aggiungi-letture',
            action='store_true',
            help='fino a --letture letture valide, tenendo quelle con la stessa domanda',
        )
        x.add_argument('--temperatura', type=float, default=None)
        x.add_argument('--seme', type=int, default=None, help='seme del campionamento: se dato, va nel giornale')
        x.add_argument('--modello', default='deepseek-v4-flash')
        x.add_argument('--base-url', default='http://127.0.0.1:8000/v1')
        x.add_argument('--chiave-file', default='')
        if nome == 'tipo':
            x.add_argument('--gruppo', default='validate', choices=['validate', 'non_validate', 'tutte'])
            x.add_argument('--sforzo', default='low')
            x.add_argument('--kwargs-modello', default='')
            x.add_argument('--solo-id', default='')
            x.add_argument('--max-righe', type=int, default=0)
        else:
            x.add_argument('--uscita-suffisso', default='')

    ca = sub.add_parser('carica', help='le proposte in piattaforma')
    cs = ca.add_subparsers(dest='cosa', required=True)
    ct = cs.add_parser('tipo')
    ct.add_argument('--caso', default='urgenda')
    ct.add_argument('--etichetta', default='v2')
    ct.add_argument('--sovrascrivi', action='store_true')
    ct.add_argument('--composizione', default='', choices=['', 'R11'], help='R11: il tipo a maggioranza delle letture')
    ct.add_argument('--salva', default='')
    ct.add_argument('--scrivi', action='store_true')
    cr = cs.add_parser('ripresa')
    cr.add_argument('--caso', default='urgenda')
    cr.add_argument('--principi-da-l04', action='store_true')
    cr.add_argument('--anche-senza-lettura', action='store_true')
    cr.add_argument('--salva', default='')
    cr.add_argument('--composizione', default='R05', choices=['R05', 'R11'], help='R11: maggioranza delle letture L05')
    cr.add_argument('--etichetta', default='', help='R11: le letture e le righe con questa etichetta')
    cr.add_argument('--etichetta-tipo', default='cinque', help='R11: le letture del tipo con questa etichetta')
    cr.add_argument('--scrivi', action='store_true')

    co = sub.add_parser('controlla', help='i controlli dopo ogni caricamento')
    cs2 = co.add_subparsers(dest='cosa', required=True)
    cc = cs2.add_parser('completezza')
    cc.add_argument('--scrivi', action='store_true')
    cs2.add_parser('finestra')
    return ap


def nome_strumento(a: argparse.Namespace) -> str:
    """What runs, for the journal: ``tracepipe leggi pagine-attorno``."""
    parti = ['tracepipe', a.comando]
    for k in ('cosa', 'lettore'):
        if getattr(a, k, None):
            parti.append(getattr(a, k))
    return ' '.join(parti)


def _cliente(a: argparse.Namespace, config: Config, giornale: Any) -> Any:
    from .deepseek import ClienteDeepSeek

    chiave = Path(a.chiave_file or (config.radice / 'chat' / 'chiave')).read_text().strip()
    from openai import OpenAI

    cli = OpenAI(api_key=chiave, base_url=a.base_url, timeout=1800)
    return ClienteDeepSeek(
        cli,
        a.modello,
        temperature=a.temperatura,
        seed=a.seme,
        osservatore=giornale.chiamata_deepseek if giornale else None,
        compat=a.compat,
    )


def _banca(giornale: Any) -> Any:
    from .banca import BancaDatiFirestore

    return BancaDatiFirestore(osservatore=giornale.scrittura_firestore if giornale else None)


def esegui(a: argparse.Namespace, config: Config, giornale: Any) -> int:
    """Run the command; returns the exit code."""
    if a.comando == 'cerca':
        from .ricerca import RicercaPerNome

        if not a.solo_lessicale:
            print('la rete semantica non fa parte del pacchetto: --solo-lessicale, o tools/cerca.py', file=sys.stderr)
            return 2
        r = RicercaPerNome(
            config,
            a.caso,
            uscita=a.uscita,
            solo_decisioni=a.solo_decisioni,
            tipo_atto=a.tipo_atto,
            con_anteriori=a.con_anteriori,
            con_alternative=a.con_alternative,
            dedup_per_atto=a.dedup_per_atto,
        )
        return r.esegui().codice
    if a.comando == 'unisci':
        from .ricerca import UnioneRighe

        UnioneRighe(
            config, _banca(giornale), data=a.data, casi=[a.caso] if a.caso else (), scrivi=a.scrivi, compat=a.compat
        ).esegui()
        return 0
    if a.comando == 'prepara':
        return _prepara(a, config)
    if a.comando == 'leggi':
        from .lettori import LETTORI

        kw: dict[str, Any] = {
            'letture': a.letture,
            'paralleli': a.paralleli,
            'etichetta': a.etichetta,
            'solo_vuote': a.solo_vuote,
            'aggiungi_letture': a.aggiungi_letture,
            'compat': a.compat,
        }
        if giornale is not None:
            # the seed and the temperature, when given, go in the journal too (03/10/2026, external review); every
            # call record already carries them (``chiamata.parametri``)
            if a.seme is not None:
                giornale.parametro('seme', a.seme)
            if a.temperatura is not None:
                giornale.parametro('temperatura', a.temperatura)
        if a.lettore == 'tipo':
            kw.update(
                gruppo=a.gruppo,
                solo_id=a.solo_id,
                max_righe=a.max_righe,
                sforzo=a.sforzo,
                kwargs_modello=a.kwargs_modello,
            )
        else:
            kw['uscita_suffisso'] = a.uscita_suffisso
        LETTORI[a.lettore](config, a.caso, _cliente(a, config, giornale), **kw).esegui()
        return 0
    if a.comando == 'carica':
        from .caricatori import CaricatoreRipresa, CaricatoreTipo

        banca = _banca(giornale)
        if a.cosa == 'tipo':
            CaricatoreTipo(
                config,
                a.caso,
                banca,
                etichetta=a.etichetta,
                sovrascrivi=a.sovrascrivi,
                composizione=a.composizione,
                salva=a.salva,
                scrivi=a.scrivi,
            ).esegui()
        else:
            CaricatoreRipresa(
                config,
                a.caso,
                banca,
                principi_da_l04=a.principi_da_l04,
                anche_senza_lettura=a.anche_senza_lettura,
                salva=a.salva,
                compat=a.compat,
                composizione=a.composizione,
                etichetta=a.etichetta,
                etichetta_tipo=a.etichetta_tipo,
                scrivi=a.scrivi,
            ).esegui()
        return 0
    if a.comando == 'controlla':
        from .controlli import ControlloCompletezza, ControlloFinestra

        if a.cosa == 'completezza':
            ControlloCompletezza(config, _banca(giornale), scrivi=a.scrivi).esegui()
            return 0
        return ControlloFinestra(config, compat=a.compat).esegui()
    raise AssertionError(a.comando)


def _prepara(a: argparse.Namespace, config: Config) -> int:
    import json

    if a.cosa == 'paragrafi':
        from .caso import MappaParagrafi
        from .pagine_attorno import leggi_jsonl

        uscita = config.principi / f'{a.caso}_da_paragrafi{"_" + a.sonde if a.sonde else ""}.jsonl'
        mappa = MappaParagrafi.carica(config, a.caso, a.sonde)
        out, conti = mappa.principi_righe(leggi_jsonl(config.training / f'lessicali_{a.caso}_righe.jsonl'))
    else:
        from .pagine_attorno import SceltaPagineAttorno

        if a.regola != 'R08' and not a.etichetta:
            print(f'{a.regola} vuole --etichetta: il file vivo delle righe resta di R08', file=sys.stderr)
            return 2
        out, conti = SceltaPagineAttorno.prepara_caso(config, a.caso, compat=a.compat, regola=a.regola)
        uscita = SceltaPagineAttorno.file_uscita(config, a.caso, a.etichetta)
    uscita.parent.mkdir(parents=True, exist_ok=True)
    with open(uscita, 'w', encoding='utf-8') as f:
        for x in out:
            f.write(json.dumps(x, ensure_ascii=False) + '\n')
    print(dict(conti), '->', uscita, flush=True)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """``trace ...``; returns the exit code (``sys.exit(main())``)."""
    argv = list(sys.argv[1:] if argv is None else argv)
    a = parser().parse_args(argv)
    config = Config.da_ambiente(_radice(a.radice))
    if a.senza_giornale:
        return esegui(a, config, None)
    from .giornale import Giornale

    with Giornale(config.radice, nome_strumento(a), argv) as g:
        return esegui(a, config, g)


if __name__ == '__main__':
    sys.exit(main())
