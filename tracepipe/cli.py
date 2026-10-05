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
``trace c03``                      ``unisci_c03.py`` (body text and footnote, translations, counted once)
``trace c07``                      ``applica_c07.py`` (a surrounding page that is a citation of its own)
``trace coppie elenco``            ``coppie_vicine.py genera`` (S08 close pairs)
``trace coppie taratura``          ``coppie_vicine.py taratura`` (the S08 threshold, with the numbers)
``trace coppie prepara``           ``leggi_coppia_l13.py prepara`` (L13 requests)
``trace coppie secco``             ``leggi_coppia_l13.py secco``
``trace coppie leggi``             ``leggi_coppia_l13.py leggi``
``trace coppie raccogli``          ``leggi_coppia_l13.py raccogli``
``trace coppie prova-freni``       ``leggi_coppia_l13.py prova-freni``
``trace coppie decidi``            ``decidi_s08.py decidi`` (never writes)
``trace coppie valuta``            ``decidi_s08.py valuta``
=================================  ==============================================================

Same options as the live scripts, and the same convention: nothing is written to the platform without ``--scrivi``
(the readers write their reading files, as live; they never touch the platform). The S08 decision never writes (as
live: it is enabled only with the PI's yes); loading the new S08 rows is :class:`tracepipe.carica_s08.CaricaS08`.
Global options: ``--radice`` (the project root; default ``$TRACE_RADICE`` or the folder that contains the package),
``--compat`` (reproduce the live
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
from .coppie_vicine import SOGLIA_S08
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

    c3 = sub.add_parser('c03', help='C03: testo e nota, traduzioni, contati una volta')
    c3.add_argument('--da', required=True, help='chi lo lancia (esclusa_da, c03_da)')
    c3.add_argument(
        '--rivisto', default='', help='elenco riletto a mano (C03_da_scrivere_RIVISTO.tsv): si scrive solo quello'
    )
    c3.add_argument('--fotografia', default='', help='una fotografia di corpus_rows invece della banca viva')
    c3.add_argument('--scrivi', action='store_true')

    c7 = sub.add_parser('c07', help="C07: una pagina attorno che e' un'altra citazione")
    c7.add_argument('--da', required=True, help='chi lo lancia (c07_da)')
    c7.add_argument('--rilette', default='', help='le pagine «prosegue» rilette a mano (colonne codice, pagina, esito)')
    c7.add_argument('--spunte-team', default='', help='C07-REVISIONE-SEGUITI: toglie le spunte «seguito» del team')
    c7.add_argument('--fotografia', default='', help='una fotografia di corpus_rows invece della banca viva')
    c7.add_argument(
        '--ipotesi-tutte', action='store_true', help='SOLO ANTEPRIMA: tutte le «prosegue» come altra citazione'
    )
    c7.add_argument('--scrivi', action='store_true')

    cp = sub.add_parser('coppie', help='S08: le coppie vicine e la domanda L13 (una citazione o due?)')
    cps = cp.add_subparsers(dest='cosa', required=True)
    ce = cps.add_parser('elenco')
    ce.add_argument('--fotografia', required=True)
    ce.add_argument('--scansione', default='')
    ce.add_argument('--soglia', type=int, default=SOGLIA_S08)
    ce.add_argument('--uscita', required=True)
    ct2 = cps.add_parser('taratura')
    ct2.add_argument('--fotografia', required=True)
    ct2.add_argument('--verita', required=True)
    ct2.add_argument('--uscita', default='')
    cpr = cps.add_parser('prepara')
    cpr.add_argument('--fotografia', required=True)
    cpr.add_argument('--verita', required=True)
    cpr.add_argument('--scansione', default='')
    cpr.add_argument('--soglia', type=int, default=SOGLIA_S08)
    cpr.add_argument('--lettore', choices=['ds', 'rr'], default='ds')
    cpr.add_argument('--uscita', required=True)
    cse = cps.add_parser('secco')
    cse.add_argument('--richieste', required=True)
    cse.add_argument('--tokenizer', default='')
    cse.add_argument('--stampa', type=int, default=1)
    cle = cps.add_parser('leggi')
    cle.add_argument('--richieste', required=True)
    cle.add_argument('--uscita', required=True)
    cle.add_argument('--base-url', required=True)
    cle.add_argument('--chiave-file', required=True)
    cle.add_argument('--modello', required=True)
    cle.add_argument('--ragionamento', default='deepseek-high', choices=['deepseek-high', 'qwen-pensa'])
    cle.add_argument('--contesto', type=int, default=65536)
    cle.add_argument('--paralleli', type=int, default=16)
    cle.add_argument('--minuti', type=float, default=0)
    cle.add_argument('--tokenizer', default='')
    cra = cps.add_parser('raccogli')
    cra.add_argument('--richieste', required=True)
    cra.add_argument('--esiti', required=True)
    cra.add_argument('--uscita', required=True)
    cps.add_parser('prova-freni')
    cde = cps.add_parser('decidi')
    cde.add_argument('--fotografia', required=True)
    cde.add_argument('--richieste', required=True)
    cde.add_argument('--ds', default='')
    cde.add_argument('--rr', default='')
    cde.add_argument('--uscita', required=True)
    cde.add_argument('--da', default='S08')
    cva = cps.add_parser('valuta')
    cva.add_argument('--fotografia', required=True)
    cva.add_argument('--verita', required=True)
    cva.add_argument('--ds', default='')
    cva.add_argument('--rr', default='')
    cva.add_argument('--uscita', default='')
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
    if a.comando == 'c03':
        from .unione_c03 import UnioneC03

        UnioneC03(
            config,
            _banca(giornale),
            a.da,
            rivisto=a.rivisto,
            fotografia=a.fotografia,
            scrivi=a.scrivi,
        ).esegui()
        return 0
    if a.comando == 'c07':
        return _c07(a, config, giornale)
    if a.comando == 'coppie':
        return _coppie(a, config)
    raise AssertionError(a.comando)


def _c07(a: argparse.Namespace, config: Config, giornale: Any) -> int:
    from .pagine_gia_citate import ApplicaC07

    if a.ipotesi_tutte and a.scrivi:
        print('--ipotesi-tutte non si usa con --scrivi', file=sys.stderr)
        return 2
    ApplicaC07(
        config,
        _banca(giornale),
        a.da,
        rilette=ApplicaC07.leggi_rilette(a.rilette) if a.rilette else None,
        revisione=a.spunte_team,
        fotografia=a.fotografia,
        ipotesi_tutte=a.ipotesi_tutte,
        scrivi=a.scrivi,
    ).esegui()
    return 0


def _coppie(a: argparse.Namespace, config: Config) -> int:
    import json

    from . import lettura_coppia as lc
    from .coppie_vicine import CoppieVicine, Taratura, classifica_recuperate
    from .unione_c03 import carica_fotografia

    if a.cosa == 'prova-freni':
        sbagliati = lc.prova_freni()
        print('PROVA DEI FRENI:', 'PASSA' if not sbagliati else f'FALLISCE {sbagliati}')
        return 1 if sbagliati else 0
    if a.cosa == 'secco':
        tok = None
        if a.tokenizer and Path(a.tokenizer).exists():
            from tokenizers import Tokenizer

            tok = Tokenizer.from_file(a.tokenizer)
        print(json.dumps(lc.secco(lc.leggi_jsonl(a.richieste), tok, a.stampa), ensure_ascii=False))
        return 0
    if a.cosa == 'leggi':
        from openai import OpenAI

        tok = None
        if a.tokenizer:
            from tokenizers import Tokenizer

            tok = Tokenizer.from_file(a.tokenizer)
        cli = OpenAI(api_key=Path(a.chiave_file).read_text().strip(), base_url=a.base_url, timeout=3600)
        lettore = lc.LettoreCoppie(
            cli,
            a.modello,
            a.ragionamento,
            contesto=a.contesto,
            paralleli=a.paralleli,
            minuti=a.minuti,
            tokenizer=tok,
        )
        lettore.leggi(a.richieste, a.uscita)
        return 0
    if a.cosa == 'raccogli':
        ris = lc.raccogli(lc.leggi_jsonl(a.richieste), a.esiti)
        Path(a.uscita).write_text(json.dumps(ris, ensure_ascii=False), encoding='utf-8')
        print(len(ris), 'coppie ->', a.uscita)
        return 0
    banca = carica_fotografia(a.fotografia)
    if a.cosa == 'elenco':
        nuove: list[dict[str, Any]] = []
        if a.scansione and Path(a.scansione).exists():
            rec = json.loads(Path(a.scansione).read_text(encoding='utf-8'))['recuperate']
            nuove = [x for x in classifica_recuperate(rec, banca) if x['esito'] == 'nuova']
        el = CoppieVicine(a.soglia).elenco(banca, nuove)
        _scrivi_elenco(Path(a.uscita), el)
        print(f'{len(el)} coppie a {a.soglia} caratteri -> {a.uscita}')
        return 0
    if a.cosa == 'taratura':
        from .coppia import ArchivioAtti

        t = Taratura(banca, a.verita)
        ris = t.misura() | {'indizi': t.indizi(ArchivioAtti(config.radice))}
        if a.uscita:
            Path(a.uscita).mkdir(parents=True, exist_ok=True)
            (Path(a.uscita) / 'taratura.json').write_text(
                json.dumps(ris, ensure_ascii=False, indent=1), encoding='utf-8'
            )
        print(json.dumps({k: ris[k] for k in ('coppie', 'distanze', 'soglia_scelta')}, ensure_ascii=False, indent=1))
        return 0
    if a.cosa == 'prepara':
        prep = lc.PreparazioneL13(config, banca, a.lettore)
        coppie = prep.insieme(a.verita, a.soglia, a.scansione)
        print(len(coppie), 'coppie')
        print(prep.prepara(coppie, a.uscita), '->', a.uscita)
        return 0
    return _decisioni(a, config, banca)


def _scrivi_elenco(percorso: Path, elenco: Sequence[dict[str, Any]]) -> None:
    import csv

    with open(percorso, 'w', newline='', encoding='utf-8') as h:
        w = csv.writer(h, delimiter='\t')
        w.writerow(
            [
                *['id_coppia', 'caso', 'atto', 'distanza', 'stessa_pagina'],
                *['a_prov', 'a_codice', 'a_pagina', 'a_char', 'b_prov', 'b_codice', 'b_pagina', 'b_char'],
            ]
        )
        for c in elenco:
            a, b = c['a'], c['b']
            w.writerow(
                [
                    *[c['id'], c['caso'], c['atto'], c['distanza'], int(c['stessa_pagina'])],
                    *[a['prov'], a['codice'] or '', a['pagina'], a['char_start']],
                    *[b['prov'], b['codice'] or '', b['pagina'], b['char_start']],
                ]
            )


def _decisioni(a: argparse.Namespace, config: Config, banca: dict[str, Any]) -> int:
    import json

    from .decisione_coppie import DecisioneCoppie

    def raccolta(p: str) -> Any:
        return json.loads(Path(p).read_text(encoding='utf-8')) if p else None

    dc = DecisioneCoppie(config, banca, getattr(a, 'da', 'S08'))
    if a.cosa == 'decidi':
        dc.decidi(dc.leggi_richieste(a.richieste), raccolta(a.ds), raccolta(a.rr), a.uscita)
        return 0
    ds, rr = raccolta(a.ds), raccolta(a.rr)
    v = dc.valuta(a.verita, ds, rr, solo_indizi=not (ds and rr))
    if a.uscita:
        Path(a.uscita).mkdir(parents=True, exist_ok=True)
        (Path(a.uscita) / 'valutazione.json').write_text(
            json.dumps(v.conti, ensure_ascii=False, indent=1), encoding='utf-8'
        )
    print(json.dumps(v.conti, ensure_ascii=False, indent=1))
    return 0


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
