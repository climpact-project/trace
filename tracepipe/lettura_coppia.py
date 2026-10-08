"""L13, the question on a close pair: «ONE CITATION OR TWO?» (``lettura_coppia``).

Class-based version of ``tools/leggi_coppia_l13.py`` (5 October 2026, S08). Two references to the same case, in the same
filing, within the threshold of S08 (5,000 characters) are a CANDIDATE PAIR (:mod:`tracepipe.coppie_vicine`). This
module has each pair read in whole, with the true text of the filing between the two points, by DeepSeek (five readings,
high reasoning, as L05) and by the reasoning reranker (Qwen3.5-9B, three readings): each says whether the two references
are the same citation or two, with the exact sentence of each and the reason. Then :mod:`tracepipe.decisione_coppie`
puts the readings and the deterministic clues (:mod:`tracepipe.coppia`) together. The clues NEVER enter the question.

The phases (as ``tools/leggi_ripresa.py``)
    ``prepara``     the question of every pair, as requests; brake 1 (:meth:`tracepipe.freni.Freni.leggibile`) before
                    the text goes to the model: a window without real words goes to a list to redo with OCR
    ``secco``       DRY RUN: builds the questions, counts the tokens; calls no model
    ``leggi``       the reader: one call per pair and per reading, resumes from where it was, after ``minuti`` it
                    starts no new call, writes FINITO
    ``raccogli``    brakes 2-4 on the answers (R14 and R16): a reading counts only if the two sentences are in the
                    text of the filing and are not copied from the prompt; the votes per pair
    ``prova_freni`` the case that MUST fail (an invented sentence, a sentence copied from the prompt): if it
                    passes, the proof fails

Nothing is written to the database. The sentences are checked on the text of the filing WITHOUT the marks ⟦A⟧ and ⟦B⟧
(the plain window kept in the request: :meth:`tracepipe.coppia.Coppia.finestra`).
"""

from __future__ import annotations

import collections
import concurrent.futures as cf
import datetime
import gzip
import json
import re
import threading
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from .config import Config, LimitiDeepSeek
from .coppia import ArchivioAtti, Coppia
from .coppie_vicine import SOGLIA_S08, CoppieVicine, Taratura, classifica_recuperate
from .deepseek import ClienteDeepSeek
from .prova_intera import FreniProvaIntera
from .righe import Riga

CODICE = 'L13'
"""The registry code of the reading."""
LETTURE_DS = 5
"""DeepSeek readings per pair (as L05: three out of five)."""
LETTURE_RR = 3
"""Reasoning-reranker readings per pair (cheaper but not more stable: a cost decision)."""
TETTO_DS = 24000
"""Cap of the DeepSeek answer with high reasoning."""
TETTO_RR = 12000
"""Cap of the reranker answer."""
CONTESTO = 65536
"""The vLLM context in tokens."""
MARGINE_CONTESTO = 512
"""Tokens left free in the context after the question and the answer."""
TETTO_MINIMO = 2000
"""Under this cap left in the context the question is too long and no call is made."""
ESITI = ('una', 'due', 'incerta')
DOVE = ('testo', 'nota', 'tabella', 'altro')
SEGNI = re.compile(r'⟦/?[AB]⟧')
CORPI: Mapping[str, Mapping[str, Any]] = {
    'deepseek-high': {'chat_template_kwargs': {'thinking': True, 'reasoning_effort': 'high'}},
    'qwen-pensa': {'chat_template_kwargs': {'enable_thinking': True}},
}
"""The ``extra_body`` of the two readers."""

MODULO = """Sei un giurista che codifica le citazioni di una sentenza climatica negli atti successivi.
Il caso citato e' {nome_caso} (decisione del {data_caso}).

DOCUMENTO: {titolo} ({tipo_atto}), documento {document_id}{lingua}.
Una ricerca per nome ha trovato in questo atto DUE riferimenti al caso, vicini fra loro:
  A: {descr_a}
  B: {descr_b}

Qui sotto il testo dell'atto da un po' prima di A fino a un po' dopo B. I due punti sono marcati da ⟦A⟧ e ⟦B⟧, messi subito
PRIMA del riferimento. [pagina N] segna il cambio di pagina. Le note a pie' di pagina stanno in fondo alla pagina, ognuna col suo
numero all'inizio della riga. Il testo e' estratto dal PDF: puo' avere righe spezzate e refusi.
---
{testo}
---

DOMANDA. I due riferimenti A e B sono UNA citazione sola del caso o DUE citazioni diverse?

UNA: sono lo stesso punto del discorso dell'atto, citato due volte. Casi tipici: il nome nella frase del testo e la nota che
quella stessa frase chiama (la nota ripete il nome del caso); il nome trovato due volte nello stesso punto (per esteso e poi
abbreviato nella stessa frase; due volte nella stessa nota; una nota spezzata dal cambio pagina; la sentenza e il nome del
caso nello stesso rinvio).
DUE: sono citazioni diverse. Casi tipici: la nota e' chiamata da un'altra frase (il numero di richiamo sta in un'altra frase,
non in quella che contiene il riferimento nel testo); due frasi diverse, anche dello stesso paragrafo, che dicono ognuna una cosa
sul caso; due note diverse; due paragrafi o due sezioni diversi.
ATTENZIONE: non basta che le due frasi si assomiglino o che la macchina abbia attaccato alla nota la frase del testo: conta DOVE
sta ciascun riferimento (nel testo o in quale nota) e QUALE frase chiama la nota. Controlla il numero del richiamo.
INCERTA: solo se il testo non basta a decidere (testo rotto, nota non trovata, richiamo illeggibile).

Se la risposta e' UNA, indica quale dei due resta come la citazione («riga_principale»): quello che sta nel testo, non nella
nota; se stanno tutti e due nel testo o tutti e due nella stessa nota, il primo che compare.

Rispondi SOLO con un oggetto JSON:
{{"esito": "una" | "due" | "incerta", "riga_principale": "A" | "B" | "" , "dove_A": "testo" | "nota" | "tabella" | "altro",
  "dove_B": "testo" | "nota" | "tabella" | "altro", "nota_chiamata": "numero della nota chiamata dalla frase del testo, o vuoto",
  "frase_A": "la frase dell'atto che contiene A (o a cui e' agganciata la nota A), COPIATA ALLA LETTERA nella sua lingua, massimo 60 parole, senza i segni ⟦ ⟧",
  "frase_B": "come frase_A, per B",
  "motivo": "una frase, massimo quaranta parole"}}
Niente fuori dal JSON."""  # noqa: E501  (the question is copied verbatim: its long lines are part of the prompt)

ISTRUZIONI_RR = """Sei il RERANKER CHE RAGIONA di TRACE, una ricerca sul contenzioso climatico. Il tuo lavoro viene accanto a quello di un
altro lettore (DeepSeek) che risponde alla stessa domanda: se non siete d'accordo la coppia va al gruppo di ricerca. Un «incerta»
onesto vale piu' di una risposta sbagliata. Le frasi che citi dall'atto devono essere COPIATE ALLA LETTERA dal testo qui sotto (le
controlla un programma parola per parola): mai un tuo riassunto, mai il testo di queste istruzioni. Ragiona passo per passo:
dove sta A, dove sta B, quale frase chiama la nota, se e' lo stesso punto del discorso.

"""  # noqa: E501

Stampa = Callable[[str], None]


def _stampa(testo: str) -> None:
    print(testo, flush=True)


class DomandaL13:
    """The L13 question of a pair: the same words for DeepSeek and for the reranker (which has instructions of its own).

    Args:
        config: where the case files are (name and decision date of the cited case).
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self._casi: dict[str, tuple[str, str]] = {}

    def caso(self, caso: str) -> tuple[str, str]:
        """``(name, decision date)`` of the cited case, from the case file."""
        if caso not in self._casi:
            c = yaml.safe_load(self.config.file_caso(caso).read_text(encoding='utf-8')) or {}
            self._casi[caso] = (c.get('nome') or caso, str(c.get('data_decisione') or ''))
        return self._casi[caso]

    @staticmethod
    def descrivi(riga: Riga) -> str:
        """How a reference is described to the reader: the form found and the page, or «by description»."""
        forma = riga.get('proposto_forma_trovata') or riga.get('forma') or ''
        pagina = riga.get('proposto_pagina') or riga.get('validato_pagina') or riga.get('pagina')
        dove = f'pagina {pagina}' if pagina else 'pagina non nota'
        if forma.startswith('descrizione') or not forma:
            return f'riferimento per descrizione (senza il nome), {dove}'
        return f'«{forma}», {dove}'

    def testo(self, coppia: Coppia, rr: bool = False) -> str:
        """The question; with ``rr`` the instructions of the reasoning reranker come first."""
        nome, data = self.caso(coppia.caso)
        meta = coppia.meta
        con_segni, _ = coppia.finestra()
        lingua = f', lingua {meta["lingue"]}' if meta.get('lingue') else ''
        corpo = MODULO.format(
            nome_caso=nome,
            data_caso=data,
            titolo=meta.get('document_title') or meta.get('case_name') or '',
            tipo_atto=meta.get('tipo_atto') or 'atto',
            document_id=meta.get('document_id') or coppia.a.get('document_id'),
            lingua=lingua,
            descr_a=self.descrivi(coppia.a),
            descr_b=self.descrivi(coppia.b),
            testo=con_segni,
        )
        return (ISTRUZIONI_RR + corpo) if rr else corpo

    @staticmethod
    def testi_prompt() -> list[str]:
        """The texts that were in the prompt and not in the filing: a «sentence» equal to one of them was copied from
        the prompt."""
        return [MODULO, ISTRUZIONI_RR]


class FreniL13:
    """Brakes 2-4 on the answer of a reading (R14 with the whole sentence, R16). A reading counts only if it passes.

    Args:
        puro: the plain text of the window (without the marks ⟦A⟧ ⟦B⟧).
        testi_prompt: the texts that were in the prompt.
        freni: the brakes (default :class:`tracepipe.prova_intera.FreniProvaIntera`).
    """

    def __init__(self, puro: str, testi_prompt: Sequence[str], freni: FreniProvaIntera | None = None) -> None:
        self.puro = puro
        self.testi_prompt = list(testi_prompt)
        self.freni = freni or FreniProvaIntera()

    def frase(self, f: object) -> str:
        """The outcome of a sentence: ``trovata``, ``inventata``, ``non trovata`` or ``assente``."""
        f = SEGNI.sub('', str(f or '')).strip()
        if not f:
            return 'assente'
        return self.freni.verifica(f, self.puro, self.testi_prompt, ricostruisci=True, intera=True)

    def verifica(self, j: Any) -> tuple[bool, str, dict[str, str]]:
        """``(ok, reason, detail)``; ``j`` is the JSON of the reading."""
        if not isinstance(j, dict) or j.get('esito') not in ESITI:
            return False, 'risposta senza esito valido', {}
        det = {'frase_A': self.frase(j.get('frase_A')), 'frase_B': self.frase(j.get('frase_B'))}
        if 'inventata' in det.values():
            return False, 'frase copiata dal prompt', det
        if j['esito'] != 'incerta':
            if det['frase_A'] != 'trovata' or det['frase_B'] != 'trovata':
                return False, "frase non trovata nell'atto", det
            if j['esito'] == 'una' and j.get('riga_principale') not in ('A', 'B'):
                return False, 'una citazione senza riga principale', det
        else:
            for (
                v
            ) in det.values():  # an uncertain answer may have no sentences, but a given sentence must be in the filing
                if v == 'non trovata':
                    return False, "frase non trovata nell'atto", det
        return True, '', det


def esito_json(testo: object) -> dict[str, Any]:
    """The first JSON object of the answer (after a ``</think>``, with or without fences); ``{}`` if none."""
    t = str(testo or '')
    if '</think>' in t:
        t = t.rsplit('</think>', 1)[1]
    t = re.sub(r'^```(?:json)?\s*|\s*```$', '', t.strip())
    i = t.find('{')
    while i >= 0:
        try:
            return json.JSONDecoder().raw_decode(t[i:])[0]
        except ValueError:
            i = t.find('{', i + 1)
    return {}


def leggi_jsonl(percorso: Path | str) -> list[dict[str, Any]]:
    """The lines of a JSONL file (gzipped if the name ends in ``.gz``); a missing file or a broken line is skipped."""
    p = Path(percorso)
    out: list[dict[str, Any]] = []
    if p.exists():
        with gzip.open(p, 'rt', encoding='utf-8') if str(p).endswith('.gz') else open(p, encoding='utf-8') as h:
            for x in h:
                try:
                    out.append(json.loads(x))
                except ValueError:
                    continue
    return out


def conta_token(testo: str, tokenizer: Any = None) -> int:
    """Tokens of a text: with a ``tokenizers`` tokenizer the real count plus 64, else 3 characters per token plus 64."""
    if tokenizer is None:
        return len(testo) // 3 + 64
    return len(tokenizer.encode(testo).ids) + 64


class PreparazioneL13:
    """From the pairs to the requests: one request is one pair, with the readings and the plain text for the brakes.

    Args:
        config: paths.
        banca: ``{id: row}`` snapshot.
        lettore: ``'ds'`` (DeepSeek) or ``'rr'`` (reasoning reranker).
        freni: the brakes (brake 1, readability).
    """

    def __init__(
        self, config: Config, banca: Mapping[str, Riga], lettore: str = 'ds', freni: FreniProvaIntera | None = None
    ) -> None:
        self.config = config
        self.banca = banca
        self.lettore = lettore
        self.domanda = DomandaL13(config)
        self.atti = ArchivioAtti(config.radice)
        self.freni = freni or FreniProvaIntera()

    def richiesta(self, id_coppia: str, a: Riga, b: Riga, priorita: int = 1, gruppo: str = '') -> dict[str, Any]:
        """The request of one pair."""
        c = Coppia(a, b, self.atti, id_coppia)
        _, puro = c.finestra()
        ok, quota = self.freni.leggibile(puro)  # BRAKE 1: no broken text to the model
        rr = self.lettore == 'rr'
        return {
            'id': id_coppia,
            'chiave': id_coppia,
            'gruppo': gruppo or a.get('document_id', ''),
            'priorita': priorita,
            'testo': self.domanda.testo(c, rr),
            'letture': LETTURE_RR if rr else LETTURE_DS,
            'tetto': TETTO_RR if rr else TETTO_DS,
            'puro': puro,
            'leggibile': ok,
            'quota_parole': quota,
            'caso': c.caso,
            'atto': a.get('document_id', ''),
            'codici': [a.get('codice'), b.get('codice')],
            'char': [c.pa, c.pb],
            'lettore': self.lettore,
        }

    def insieme(self, verita: Path | str, soglia: int = SOGLIA_S08, scansione: Path | str = '') -> list[dict[str, Any]]:
        """The pairs to read: first (priority 0) the pairs of the C03 TRUTH with both rows in the same filing, which
        measure the readers; then (priority 1) the links of S08 at the threshold, the new rows of the scan included
        (WITHOUT the filter of C04: S08 comes BEFORE C01-C04 in the cycle, and C04's estimate on invented rows discarded
        the citation of Children of Austria p. 29), without repeating the pairs already in the truth.

        Returns ``[{id, a, b, priorita, origine, verita}]`` with ``a`` and ``b`` rows."""
        out: list[dict[str, Any]] = []
        viste: set[frozenset[str]] = set()
        for d, a, b, _ in Taratura(self.banca, verita).coppie_stesso_atto():
            ca, cb = a['codice'], b['codice']
            viste.add(frozenset((ca, cb)))
            out.append({'id': f'{ca}__{cb}', 'a': a, 'b': b, 'priorita': 0, 'origine': 'verita_c03', 'verita': d})
        nuove: list[dict[str, Any]] = []
        if scansione and Path(scansione).exists():
            rec = json.loads(Path(scansione).read_text(encoding='utf-8'))['recuperate']
            nuove = [x for x in classifica_recuperate(rec, self.banca) if x['esito'] == 'nuova']
        riga = {x['chiave']: x for x in nuove}
        for c in CoppieVicine(soglia).elenco(self.banca, nuove):
            ra = self.banca.get(c['a']['chiave']) or riga[c['a']['chiave']]
            rb = self.banca.get(c['b']['chiave']) or riga[c['b']['chiave']]
            ca, cb = ra.get('codice') or c['a']['chiave'], rb.get('codice') or c['b']['chiave']
            if frozenset((ca, cb)) in viste:
                continue
            out.append({'id': f'{ca}__{cb}', 'a': ra, 'b': rb, 'priorita': 1, 'origine': 'legame_s08', 'verita': None})
        return out

    def prepara(self, coppie: Iterable[Mapping[str, Any]], uscita: Path | str, priorita: int = 1) -> dict[str, int]:
        """Write the readable requests to ``uscita`` (jsonl.gz), the unreadable ones to ``<uscita>.illeggibili.json``.

        Returns the counts."""
        n: collections.Counter[str] = collections.Counter()
        illeggibili: list[dict[str, Any]] = []
        with gzip.open(uscita, 'wt', encoding='utf-8') as h:
            for x in coppie:
                r = self.richiesta(x['id'], x['a'], x['b'], x.get('priorita', priorita))
                if not r['leggibile']:
                    n['illeggibile'] += 1
                    illeggibili.append({'id': r['id'], 'atto': r['atto'], 'quota_parole': r['quota_parole']})
                    continue
                n['richieste'] += 1
                h.write(json.dumps(r, ensure_ascii=False) + '\n')
        Path(str(uscita) + '.illeggibili.json').write_text(
            json.dumps(illeggibili, ensure_ascii=False), encoding='utf-8'
        )
        return dict(n)


def secco(
    richieste: Sequence[Mapping[str, Any]], tokenizer: Any = None, stampa: int = 1, scrivi: Stampa = _stampa
) -> dict[str, Any]:
    """DRY RUN: no model. Returns ``{richieste, median and maximum tokens, how many do not fit the context}``."""
    nt = sorted(conta_token(r['testo'], tokenizer) for r in richieste)
    fuori = sum(1 for n in nt if n > CONTESTO - 4000)
    for r in richieste[:stampa]:
        scrivi('=' * 30 + f' {r["id"]} ' + '=' * 30)
        scrivi(r['testo'])
    return {
        'richieste': len(nt),
        'token_mediana': nt[len(nt) // 2] if nt else 0,
        'token_massimo': nt[-1] if nt else 0,
        'token_totale': sum(nt),
        'non_entrano_nel_contesto': fuori,
        'metodo_token': 'tokenizer DeepSeek' if tokenizer else 'stima 3 caratteri/token',
    }


class LettoreCoppie:
    """The reader: one call per (pair, reading). It resumes from where it was; after ``minuti`` it starts no new call.

    Args:
        cliente_openai: an ``openai.OpenAI`` client (or anything with ``chat.completions.create``).
        modello: the model name sent to the server.
        ragionamento: ``'deepseek-high'`` or ``'qwen-pensa'`` (:data:`CORPI`).
        contesto: the context of the server in tokens.
        paralleli: calls in parallel.
        minuti: minutes after which no new call starts (0: no limit).
        tokenizer: a ``tokenizers`` tokenizer for the real token count.
        osservatore: called with the ``chiamata`` record after every call (the journal).
        stampa: where the screen lines go.
        orologio: the clock (seconds), for the time limit.
    """

    def __init__(
        self,
        cliente_openai: Any,
        modello: str,
        ragionamento: str = 'deepseek-high',
        contesto: int = CONTESTO,
        paralleli: int = 16,
        minuti: float = 0,
        tokenizer: Any = None,
        osservatore: Callable[[dict[str, Any]], None] | None = None,
        stampa: Stampa = _stampa,
        orologio: Callable[[], float] = time.time,
    ) -> None:
        self.modello = modello
        self.contesto = contesto
        self.paralleli = paralleli
        self.minuti = minuti
        self.tokenizer = tokenizer
        self.stampa = stampa
        self.orologio = orologio
        self.cliente = ClienteDeepSeek(
            cliente_openai,
            modello,
            extra_body=dict(CORPI[ragionamento]),
            limiti=LimitiDeepSeek(contesto=contesto),
            osservatore=osservatore,
        )

    def tetto(self, richiesta: Mapping[str, Any]) -> tuple[int, int]:
        """``(question tokens, cap of the answer)``: the cap of the request, never beyond what the context leaves."""
        n = conta_token(richiesta['testo'], self.tokenizer)
        return n, min(richiesta.get('tetto') or TETTO_DS, self.contesto - n - MARGINE_CONTESTO)

    def lavori(
        self, richieste: Sequence[Mapping[str, Any]], fatte: set[str]
    ) -> list[tuple[int, str, str, int, Mapping[str, Any]]]:
        """The readings still to do, by priority, group, key and reading number."""
        lavori = []
        for r in richieste:
            for k in range(r.get('letture') or 1):
                if f'{r["chiave"]}|{k}' not in fatte:
                    lavori.append((r.get('priorita', 0), r.get('gruppo') or '', r['chiave'], k, r))
        lavori.sort(key=lambda x: x[:4])
        return lavori

    def leggi(self, richieste_file: Path | str, uscita: Path | str) -> bool:
        """Run the readings; returns True if every reading is done (FINITO), False if time ran out."""
        uscita = Path(uscita)
        fatte = {x['chiave'] for x in leggi_jsonl(uscita)}
        lavori = self.lavori(leggi_jsonl(richieste_file), fatte)
        self.stampa(
            f'{len(lavori)} readings to do ({len(fatte)} already done), {self.modello}, context {self.contesto}'
        )
        t0, blocco, stop = self.orologio(), threading.Lock(), threading.Event()

        def una(lav: tuple[int, str, str, int, Mapping[str, Any]]) -> dict[str, Any] | None:
            _, _, chiave, k, r = lav
            if stop.is_set() or (self.minuti and self.orologio() - t0 > self.minuti * 60):
                stop.set()
                return None
            n, cap = self.tetto(r)
            if cap < TETTO_MINIMO:
                x: dict[str, Any] = {'testo': '', 'errore': f'domanda troppo lunga: {n} token su {self.contesto}'}
            else:
                x = self.cliente.chiama(r['testo'], tetto=cap)
            rag = x.get('ragionamento') or ''
            out = {
                'id': r['id'],
                'chiave': f'{chiave}|{k}',
                'lettura': k,
                'testo': x.get('testo', ''),
                'token': x.get('token'),
                'ragionamento': {'caratteri': len(rag), 'coda': rag[-3000:]},
                'chiamata': x.get('chiamata'),
                'errore': x.get('errore'),
                'data': datetime.date.today().isoformat(),
                'lettore': self.modello,
                'codice': CODICE,
            }
            with blocco, open(uscita, 'a', encoding='utf-8') as f:
                f.write(json.dumps(out, ensure_ascii=False) + '\n')
            return out

        fatte_ora = 0
        with cf.ThreadPoolExecutor(self.paralleli) as ex:
            for o in ex.map(una, lavori):
                if o is not None:
                    fatte_ora += 1
                    if fatte_ora % 25 == 0:
                        self.stampa(f'  {fatte_ora}/{len(lavori)} [{self.orologio() - t0:.0f}s]')
        resto = len(lavori) - fatte_ora
        self.stampa(
            f'done {fatte_ora} in {self.orologio() - t0:.0f}s; '
            + ('FINITO (finished)' if resto == 0 else f'TIME: {resto} left')
        )
        return resto == 0


def raccogli(richieste: Iterable[Mapping[str, Any]], esiti: Path | str) -> dict[str, dict[str, Any]]:
    """``{id: {voti, valide, scartate, fatte, previste, letture}}``: brakes 2-4 on every reading.

    ``richieste`` gives the plain text of the filing and the texts of the prompt."""
    per: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for x in leggi_jsonl(esiti):
        per[x['id']].append(x)
    out: dict[str, dict[str, Any]] = {}
    for r in richieste:
        fr = FreniL13(r['puro'], DomandaL13.testi_prompt())
        voti: collections.Counter[str] = collections.Counter()
        motivi: collections.Counter[str] = collections.Counter()
        lett: list[dict[str, Any]] = []
        for x in sorted(per.get(r['id'], []), key=lambda y: y['lettura']):
            j = esito_json(x.get('testo'))
            ok, motivo, det = fr.verifica(j)
            lett.append(
                {'lettura': x['lettura'], 'valida': ok, 'motivo_scarto': motivo, 'verifica_frasi': det, 'json': j}
            )
            if ok:
                voti[j['esito']] += 1
            else:
                motivi[motivo] += 1
        out[r['id']] = {
            'voti': dict(voti),
            'valide': sum(voti.values()),
            'scartate': dict(motivi),
            'fatte': len(lett),
            'previste': r.get('letture'),
            'letture': lett,
        }
    return out


def prova_freni(freni: FreniProvaIntera | None = None) -> list[tuple[str, str]]:
    """THE CASE THAT MUST FAIL: the cases in which a brake did NOT stop what it had to (empty: the proof passes)."""
    freni = freni or FreniProvaIntera()
    atto = (
        '[pagina 4] La Corte ha ritenuto che lo Stato debba ridurre le emissioni almeno del 25 per cento entro '
        'il 2020, come stabilito nella sentenza Urgenda.1 Nel testo seguente si discute della responsabilita '
        'dello Stato.\n'
        '1 Urgenda Foundation v The State of the Netherlands, Hoge Raad, 20 December 2019.\n'
    )
    fr = FreniL13(atto, DomandaL13.testi_prompt(), freni)
    buona = {
        'esito': 'una',
        'riga_principale': 'A',
        'frase_A': 'La Corte ha ritenuto che lo Stato debba ridurre le emissioni almeno del 25 per cento entro '
        'il 2020, come stabilito nella sentenza Urgenda.',
        'frase_B': '1 Urgenda Foundation v The State of the Netherlands, Hoge Raad, 20 December 2019.',
    }
    casi: list[tuple[str, dict[str, Any], bool]] = [
        ('lettura buona deve passare', buona, True),
        (
            "frase inventata (finale che nell'atto non c'e')",
            {**buona, 'frase_A': buona['frase_A'] + ' e ha ordinato un risarcimento di dieci milioni'},
            False,
        ),
        (
            'frase copiata dal prompt',
            {**buona, 'frase_B': "sono lo stesso punto del discorso dell'atto, citato due volte"},
            False,
        ),
        ('esito fuori elenco', {**buona, 'esito': 'forse'}, False),
        ('una senza riga principale', {**buona, 'riga_principale': ''}, False),
    ]
    sbagliati: list[tuple[str, str]] = []
    for nome, j, deve_passare in casi:
        ok, motivo, _ = fr.verifica(j)
        if ok != deve_passare:
            sbagliati.append((nome, motivo))
    # brake 1: a window of broken characters does not reach the model
    if freni.leggibile('\u00d0\u00a7\u00d1\u201a\u00d0\u00be ' * 80)[0]:
        sbagliati.append(('freno 1: testo rotto lasciato passare', ''))
    return sbagliati
