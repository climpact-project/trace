"""The scores of TRACE-Reranker 0.1 (code T01): one score between a principle and a text (``punteggio``: score).

Package twin of ``tools/ripresa_punteggi.py`` (frozen copy ``versioni/T01/ripresa_punteggi.py``) and of the
``QwenRiordinatore`` class of ``tools/prova_riordinatori.py`` (frozen copy ``versioni/T01/prova_riordinatori.py``).
Two steps, as live:

- **prepara** (prepare, on the Mac): the (principle, text) pairs of a case. For every lexical row the text is the
  flagged passage with ``ALLARGA`` (800) characters before and after; then every surrounding page of the same filing,
  once even when several rows need it. The name of the cited case and the ECLI codes are masked as in training.
- **punteggi** (scores, one GPU per piece): Qwen3-Reranker-4B with each of the three LoRA adapters (seeds 1-3), the
  probability of «yes» against «no» at the last position, mean of the three seeds rounded to 5 decimals.

The pure parts (instruction, prompt, masking, passages, logits to score, mean and rounding) need nothing beyond the
standard library and are tested without weights. The model part imports ``torch``, ``transformers`` and ``peft``
only when it runs: importing :mod:`tracepipe` or ``trace --help`` does not need them.

Output, as live: the pairs file ``training/principi/<case>_coppie.jsonl`` (lines ``{riga, dove: brano, pagina,
principio, q, d}`` then ``{pagina_id, dove: vicina, principio, q, d}``) and the score files
``training/principi/<case>_punteggi_<piece>.jsonl`` (lines ``{riga|pagina_id, dove, pagina, principio, punteggio}``).

Window of the surrounding pages: the frozen T01 copy of 27/09/2026 took from 2 pages before to 3 after; the live
script takes 10 before and 10 after since 01/10/2026 (rule R03/R10). The default here is the live one
(:data:`PRIMA`, :data:`DOPO`); ``--prima 2 --dopo 3`` reproduces the frozen one.

Golden check (10/10/2026, one H100 NVL at ReCaS, torch 2.13 + transformers 5.17 + peft 0.21, bf16): ``punteggi
calcola`` on the first 800 pairs of piece 0/4 of the Urgenda pairs of 27/09/2026 gives the 800 published scores of
``urgenda_punteggi_0.jsonl`` identical to the 5th decimal. On Apple MPS (bf16) the same code differs by up to 0.016.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import sys
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Config

# ── constants (verbatim from the frozen code) ─────────────────────────────────────────────────────────────────

MODELLO_BASE = 'Qwen/Qwen3-Reranker-4B'
"""The base model of T01 (versioni/registro.json)."""
REVISIONE_BASE = '22e683669bc0f0bd69640a1354a6d0aebcfeede5'
"""The Hugging Face revision of the base model (versioni/registro.json)."""
ADATTATORI = 'training/lora_qwen_rr4b_{seme}/passata_2'
"""The three LoRA adapters, one per seed, relative to the project root (``--adattatore`` of the live script)."""
SEMI: tuple[int, ...] = (1, 2, 3)
MAX_LUNGHEZZA = 2560
"""Token cap of a whole prompt (prefix, instruction, query, document, suffix)."""
LOTTO = 8
"""Pairs per forward pass in ``punteggi`` (the live script; ``QwenRiordinatore.punteggi`` defaults to 4)."""
DECIMALI = 5

ALLARGA = 800
"""Characters kept before and after the flagged passage."""
PRIMA, DOPO = 10, 10
"""Surrounding pages before and after the citation page (live since 01/10/2026; the frozen T01 copy had 2 and 3)."""

INIZIO = '[[INIZIO DEL BRANO SEGNALATO]]'
FINE = '[[FINE DEL BRANO SEGNALATO]]'
SEGNAPOSTO = '⟦CASO_CITATO⟧'
"""What replaces the case name and the ECLI codes (tools/prepara_training.py)."""

ISTRUZIONE = (
    'Judge whether the Document adopts, as its own reasoning, the legal proposition '
    'in the Query as established in the cited judgment, rather than merely discussing '
    'the same topic or deriving a similar conclusion from other legal sources such as '
    'treaties, national constitutions, regional human rights instruments or other cases.'
)
"""``ISTR['ripresa']`` (uptake) of tools/prova_riordinatori.py: the instruction T01 was trained and is used with."""
ISTRUZIONE_DI_SERIE = 'Given a web search query, retrieve relevant passages that answer the query'
"""``ISTR['di_serie']``: the stock instruction of Qwen3-Reranker (not used by T01)."""

PREFISSO = (
    '<|im_start|>system\nJudge whether the Document meets the requirements based on the Query '
    'and the Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'
)
SUFFISSO = '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'

_ECLI_E_RUOLI = r'|ECLI:[A-Z]{2}:[A-Z]+:\d{4}:\d+|\b\d{2}/\d{5}\b|\b200\.\d{3}\.\d{3}/\d{2}\b'

CHIAVI_USCITA = ('riga', 'pagina_id', 'dove', 'pagina', 'principio')
"""The keys of a pair copied to its score line, in this order."""


# ── masking and pairs (pure) ──────────────────────────────────────────────────────────────────────────────────


def mascheratore(forme: Iterable[str]) -> re.Pattern[str]:
    """One case-insensitive pattern with every form of the case, plus ECLI codes and docket numbers.

    Forms of 3 characters or fewer are dropped; the others are sorted by decreasing length, so that «State of the
    Netherlands v. Urgenda Foundation» is consumed before «Urgenda» (tools/prepara_training.py ``mascheratore``).
    """
    pezzi = sorted({f for f in forme if len(f) > 3}, key=len, reverse=True)
    pat = '|'.join(re.escape(f) for f in pezzi)
    pat += _ECLI_E_RUOLI
    return re.compile(pat, re.I)


def maschera_caso(conf: Mapping[str, Any]) -> re.Pattern[str]:
    """The masking pattern of a case file: its ``forme`` (forms) plus its ``nome`` (name)."""
    return mascheratore([str(f) for f in conf['forme']] + [conf.get('nome', '')])


def maschera(testo: str, pattern: re.Pattern[str]) -> str:
    """Whitespace collapsed to single spaces, then every match replaced by :data:`SEGNAPOSTO`."""
    return pattern.sub(SEGNAPOSTO, ' '.join(testo.split()))


def principi_del_caso(conf: Mapping[str, Any]) -> dict[str, str]:
    """``{principle id: text}`` from the ``semantic_queries`` of a case file, whitespace collapsed."""
    return {s['id']: ' '.join(s['testo'].split()) for s in conf['semantic_queries']}


def brano(contesto: str, pattern: re.Pattern[str], allarga: int = ALLARGA) -> str | None:
    """The flagged passage of a row with ``allarga`` characters around it, markers removed, masked.

    Returns ``None`` when one of the two markers is missing (the live script skips the row).
    """
    a, b = contesto.find(INIZIO), contesto.find(FINE)
    if a < 0 or b < 0:
        return None
    t = contesto[max(0, a - allarga) : b + len(FINE) + allarga]
    t = t.replace(INIZIO, '').replace(FINE, '').replace('⟦', '').replace('⟧', '')
    return maschera(t, pattern)


def pagine_attorno(righe: Iterable[Mapping[str, Any]], prima: int = PRIMA, dopo: int = DOPO) -> dict[str, set[str]]:
    """``{page id: {row ids}}``: the surrounding pages each row needs (``<document_id>#p<n>``).

    From ``prima`` pages before to ``dopo`` after the citation page, the page itself and pages below 1 excluded; rows
    without a page need none.
    """
    serve: dict[str, set[str]] = {}
    for r in righe:
        p = int(r.get('pagina') or 0)
        if p:
            for k in range(p - prima, p + dopo + 1):
                if k != p and k > 0:
                    serve.setdefault(f'{r["document_id"]}#p{k}', set()).add(r['id'])
    return serve


def coppie_brano(
    righe: Iterable[Mapping[str, Any]], principi: Mapping[str, str], pattern: re.Pattern[str]
) -> Iterator[dict[str, Any]]:
    """One pair per (row, principle) on the flagged passage, rows in order, principles in file order."""
    for r in righe:
        d = brano(r['contesto'], pattern)
        if d is None:
            continue
        for pid, q in principi.items():
            yield {'riga': r['id'], 'dove': 'brano', 'pagina': r.get('pagina'), 'principio': pid, 'q': q, 'd': d}


def coppie_vicine(
    pagine: Mapping[str, str], principi: Mapping[str, str], pattern: re.Pattern[str]
) -> Iterator[dict[str, Any]]:
    """One pair per (surrounding page, principle), pages in the given order (that of the page index)."""
    for pagid, testo in pagine.items():
        d = maschera(testo, pattern)
        for pid, q in principi.items():
            yield {'pagina_id': pagid, 'dove': 'vicina', 'principio': pid, 'q': q, 'd': d}


def leggi_pagine(indice: Path, servono: Iterable[str]) -> dict[str, str]:
    """``{page id: text}`` of the requested pages, in the order of the page index (gzipped JSONL)."""
    voglio = set(servono)
    pag: dict[str, str] = {}
    with gzip.open(indice, 'rt', encoding='utf-8') as f:
        for riga in f:
            x = json.loads(riga)
            if x['id'] in voglio:
                pag[x['id']] = x['testo']
    return pag


@dataclass
class EsitoPrepara:
    """What :func:`prepara` wrote."""

    righe: int
    pagine: int
    coppie: int
    uscita: Path


def prepara(
    conf: Mapping[str, Any],
    righe: Sequence[Mapping[str, Any]],
    indice_pagine: Path,
    uscita: Path,
    prima: int = PRIMA,
    dopo: int = DOPO,
) -> EsitoPrepara:
    """Write the pairs file of a case: the passage pairs first, then the surrounding-page pairs.

    Args:
        conf: the case file (``forme``, ``nome``, ``semantic_queries``).
        righe: the lexical rows (``training/lessicali_<case>_righe.jsonl``).
        indice_pagine: the page index (``index/pagine/pagine.jsonl.gz``).
        uscita: the pairs file to write.
        prima, dopo: the window of the surrounding pages.
    """
    pattern = maschera_caso(conf)
    principi = principi_del_caso(conf)
    pag = leggi_pagine(indice_pagine, pagine_attorno(righe, prima, dopo))
    uscita.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(uscita, 'w', encoding='utf-8') as f:
        for c in (*coppie_brano(righe, principi, pattern), *coppie_vicine(pag, principi, pattern)):
            f.write(json.dumps(c, ensure_ascii=False) + '\n')
            n += 1
    return EsitoPrepara(len(righe), len(pag), n, uscita)


# ── prompt and score (pure) ───────────────────────────────────────────────────────────────────────────────────


def testo_coppia(q: str, d: str, istruzione: str = ISTRUZIONE) -> str:
    """The user part of the prompt, before tokenisation and truncation (``QwenRiordinatore.codifica``)."""
    return f'<Instruct>: {istruzione}\n<Query>: {q}\n<Document>: {d}'


def prompt_intero(q: str, d: str, istruzione: str = ISTRUZIONE) -> str:
    """The whole prompt as text, when it fits the token cap.

    The model sees the token sequence ``encode(PREFISSO) + encode(testo_coppia)[:cap] + encode(SUFFISSO)``: the three
    parts are tokenised separately and only the middle one is truncated. This string is for reading and testing.
    """
    return PREFISSO + testo_coppia(q, d, istruzione) + SUFFISSO


def punteggio_da_logit(logit_no: float, logit_si: float) -> float:
    """Probability of «yes» from the two logits: ``exp(log_softmax([no, yes])[1])``, i.e. ``sigmoid(yes - no)``."""
    m = max(logit_no, logit_si)
    log_z = m + math.log(math.exp(logit_no - m) + math.exp(logit_si - m))
    return math.exp(logit_si - log_z)


def media_semi(per_seme: Sequence[Sequence[float]]) -> list[float]:
    """The mean over seeds of each pair's score (``np.mean(S, 0)``, summed in seed order)."""
    if not per_seme:
        return []
    n = len(per_seme[0])
    if any(len(s) != n for s in per_seme):
        raise ValueError('every seed must score the same pairs')
    return [sum(float(s[i]) for s in per_seme) / len(per_seme) for i in range(n)]


def arrotonda(x: float) -> float:
    """The published precision: 5 decimals."""
    return round(float(x), DECIMALI)


def riga_punteggio(coppia: Mapping[str, Any], punteggio: float) -> dict[str, Any]:
    """The score line of a pair: its identifying keys plus ``punteggio``, rounded."""
    return {k: coppia[k] for k in CHIAVI_USCITA if k in coppia} | {'punteggio': arrotonda(punteggio)}


def pezzo_di(coppie: Sequence[Any], pezzo: int, pezzi: int) -> list[Any]:
    """The share of piece ``pezzo`` out of ``pezzi`` (``coppie[pezzo::pezzi]``, one GPU job each)."""
    return list(coppie[pezzo::pezzi])


def percorso_adattatore(schema: str, seme: int, radice: Path | None = None) -> Path:
    """The adapter of a seed: ``{seme}`` replaced, relative paths under ``radice``."""
    p = Path(schema.replace('{seme}', str(seme))).expanduser()
    return p if p.is_absolute() or radice is None else radice / p


# ── the model (torch, transformers and peft imported only here) ───────────────────────────────────────────────


def dispositivo_automatico() -> str:
    """``cuda`` if available, else ``mps``, else ``cpu``."""
    import torch

    if torch.cuda.is_available():
        return 'cuda'
    if getattr(torch.backends, 'mps', None) is not None and torch.backends.mps.is_available():
        return 'mps'
    return 'cpu'


class RiordinatoreQwen:
    """Qwen3-Reranker with an optional LoRA adapter (``QwenRiordinatore`` of tools/prova_riordinatori.py).

    Args:
        modello: a local folder or a Hugging Face id of the base model.
        adattatore: a LoRA adapter folder, or ``None`` for the base model alone.
        dispositivo: ``cuda``, ``mps``, ``cpu`` or ``auto``.
        precisione: the torch dtype name of the weights (``bfloat16`` as live).
        revisione: the Hugging Face revision, used only when ``modello`` is not a local folder.
    """

    def __init__(
        self,
        modello: str,
        adattatore: str | Path | None = None,
        dispositivo: str = 'auto',
        precisione: str = 'bfloat16',
        revisione: str | None = REVISIONE_BASE,
    ) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.dispositivo = dispositivo_automatico() if dispositivo == 'auto' else dispositivo
        kw: dict[str, Any] = {}
        if revisione and not Path(modello).expanduser().is_dir():
            kw['revision'] = revisione
        nome = str(Path(modello).expanduser()) if Path(modello).expanduser().is_dir() else modello
        self.tok = AutoTokenizer.from_pretrained(nome, padding_side='left', **kw)
        m = AutoModelForCausalLM.from_pretrained(nome, dtype=getattr(torch, precisione), **kw)
        m = m.to(self.dispositivo)
        if adattatore is not None:
            from peft import PeftModel

            m = PeftModel.from_pretrained(m, str(adattatore))
        self.m: Any = m.eval()
        self.si = self.tok.convert_tokens_to_ids('yes')
        self.no = self.tok.convert_tokens_to_ids('no')
        self.pre = self.tok.encode(PREFISSO, add_special_tokens=False)
        self.suf = self.tok.encode(SUFFISSO, add_special_tokens=False)

    def codifica(self, coppie: Sequence[tuple[str, str]], istruzione: str, max_lunghezza: int) -> Any:
        """Tokenise a batch: the middle text truncated to fit, then prefix and suffix, left padding."""
        testi = [testo_coppia(q, d, istruzione) for q, d in coppie]
        enc = self.tok(
            testi,
            padding=False,
            truncation='longest_first',
            return_attention_mask=False,
            max_length=max_lunghezza - len(self.pre) - len(self.suf),
        )
        enc['input_ids'] = [self.pre + ids + self.suf for ids in enc['input_ids']]
        return self.tok.pad(enc, padding=True, return_tensors='pt').to(self.dispositivo)

    def logit_si_no(self, enc: Any) -> Any:
        """The ``[no, yes]`` logits at the last position, in float32."""
        import torch

        lg = self.m(**enc).logits[:, -1, :]
        return torch.stack([lg[:, self.no], lg[:, self.si]], dim=1).float()

    def punteggi(
        self,
        coppie: Sequence[tuple[str, str]],
        istruzione: str = ISTRUZIONE,
        max_lunghezza: int = MAX_LUNGHEZZA,
        lotto: int = LOTTO,
        avanzamento: Callable[[int, int], None] | None = None,
    ) -> list[float]:
        """The probability of «yes» of every (query, document) pair, in order."""
        import torch

        out: list[float] = []
        with torch.no_grad():
            for i in range(0, len(coppie), lotto):
                z = torch.log_softmax(
                    self.logit_si_no(self.codifica(coppie[i : i + lotto], istruzione, max_lunghezza)), dim=1
                )
                out += z[:, 1].exp().cpu().tolist()
                if avanzamento:
                    avanzamento(len(out), len(coppie))
        return out

    def libera(self) -> None:
        """Drop the model and free the device memory."""
        import gc

        import torch

        del self.m
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        if getattr(torch.backends, 'mps', None) is not None and torch.backends.mps.is_available():
            torch.mps.empty_cache()


def punteggi_t01(
    coppie: Sequence[Mapping[str, Any]],
    modello: str,
    adattatori: Sequence[str | Path],
    *,
    lotto: int = LOTTO,
    max_lunghezza: int = MAX_LUNGHEZZA,
    dispositivo: str = 'auto',
    precisione: str = 'bfloat16',
    revisione: str | None = REVISIONE_BASE,
    log: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    """The T01 score lines of ``coppie``: one model per adapter (base reloaded each time, as live), mean, rounded."""
    testi = [(c['q'], c['d']) for c in coppie]
    per_seme: list[list[float]] = []
    for ad in adattatori:
        r = RiordinatoreQwen(modello, ad, dispositivo=dispositivo, precisione=precisione, revisione=revisione)
        per_seme.append(r.punteggi(testi, ISTRUZIONE, max_lunghezza, lotto=lotto))
        r.libera()
        if log:
            log(f'  adapter {ad} done')
    return [riga_punteggio(c, s) for c, s in zip(coppie, media_semi(per_seme), strict=True)]


# ── command line (wired by tracepipe.cli) ─────────────────────────────────────────────────────────────────────


def aggiungi_parser(sub: Any) -> argparse.ArgumentParser:
    """Add ``punteggi`` (T01 scores) to the subcommands ``sub``: ``punteggi prepara`` and ``punteggi calcola``."""
    p = sub.add_parser('punteggi', help='T01 (TRACE-Reranker 0.1): the principle-text pairs and their scores')
    ps = p.add_subparsers(dest='cosa', required=True)
    pp = ps.add_parser('prepara', help='the pairs of a case (ripresa_punteggi.py prepara)')
    pp.add_argument('--caso', required=True)
    pp.add_argument('--righe', default='', help='the lexical rows (default training/lessicali_<case>_righe.jsonl)')
    pp.add_argument('--uscita', default='', help='the pairs file (default training/principi/<case>_coppie.jsonl)')
    pp.add_argument('--prima', type=int, default=PRIMA, help='surrounding pages before the citation (frozen T01: 2)')
    pp.add_argument('--dopo', type=int, default=DOPO, help='surrounding pages after the citation (frozen T01: 3)')
    pc = ps.add_parser('calcola', help='the scores of the pairs (ripresa_punteggi.py punteggi)')
    pc.add_argument('--caso', default='', help='only for the default file names')
    pc.add_argument('--coppie', default='', help='the pairs file (default training/principi/<case>_coppie.jsonl)')
    pc.add_argument(
        '--uscita', default='', help='the scores file (default training/principi/<case>_punteggi_<piece>.jsonl)'
    )
    pc.add_argument('--modello-base', default=MODELLO_BASE, help='a local folder or a Hugging Face id')
    pc.add_argument('--revisione', default=REVISIONE_BASE, help='Hugging Face revision (ignored for a local folder)')
    pc.add_argument('--adattatori', default=ADATTATORI, help='adapter folder with {seme}, relative to the root')
    pc.add_argument('--semi', default=','.join(map(str, SEMI)))
    pc.add_argument('--lotto', type=int, default=LOTTO)
    pc.add_argument('--max-lunghezza', type=int, default=MAX_LUNGHEZZA)
    pc.add_argument('--pezzo', type=int, default=0)
    pc.add_argument('--pezzi', type=int, default=1)
    pc.add_argument('--dispositivo', default='auto', choices=['auto', 'cuda', 'mps', 'cpu'])
    pc.add_argument('--precisione', default='bfloat16', choices=['bfloat16', 'float16', 'float32'])
    pc.add_argument('--limite', type=int, default=0, help='score only the first N pairs of the piece (a trial)')
    return p


def _leggi_jsonl(percorso: Path) -> list[dict[str, Any]]:
    with open(percorso, encoding='utf-8') as f:
        return [json.loads(x) for x in f if x.strip()]


def esegui(args: argparse.Namespace, config: Config | None = None) -> int:
    """Run ``punteggi prepara`` or ``punteggi calcola``; returns the exit code."""
    config = config or Config.da_ambiente(getattr(args, 'radice', '') or None)
    if args.cosa == 'prepara':
        import yaml

        conf = yaml.safe_load(config.file_caso(args.caso).read_text(encoding='utf-8'))
        righe = _leggi_jsonl(Path(args.righe) if args.righe else config.training / f'lessicali_{args.caso}_righe.jsonl')
        uscita = Path(args.uscita) if args.uscita else config.principi / f'{args.caso}_coppie.jsonl'
        e = prepara(conf, righe, config.indice_pagine, uscita, args.prima, args.dopo)
        print(f'{e.righe} rows, {e.pagine} surrounding pages, {e.coppie} pairs -> {e.uscita}')
        return 0
    if args.cosa == 'calcola':
        if not args.coppie and not args.caso:
            print('give --coppie or --caso', file=sys.stderr)
            return 2
        coppie_file = Path(args.coppie) if args.coppie else config.principi / f'{args.caso}_coppie.jsonl'
        uscita = Path(args.uscita) if args.uscita else config.principi / f'{args.caso}_punteggi_{args.pezzo}.jsonl'
        if not args.uscita and not args.caso:
            print('give --uscita or --caso', file=sys.stderr)
            return 2
        coppie = pezzo_di(_leggi_jsonl(coppie_file), args.pezzo, args.pezzi)
        if args.limite:
            coppie = coppie[: args.limite]
        semi = [int(s) for s in str(args.semi).split(',') if s.strip()]
        adattatori = [percorso_adattatore(args.adattatori, s, config.radice) for s in semi]
        print(f'piece {args.pezzo}/{args.pezzi}: {len(coppie)} pairs', flush=True)
        righe = punteggi_t01(
            coppie,
            args.modello_base,
            adattatori,
            lotto=args.lotto,
            max_lunghezza=args.max_lunghezza,
            dispositivo=args.dispositivo,
            precisione=args.precisione,
            revisione=args.revisione,
            log=lambda m: print(m, flush=True),
        )
        uscita.parent.mkdir(parents=True, exist_ok=True)
        with open(uscita, 'w', encoding='utf-8') as f:
            for r in righe:
                f.write(json.dumps(r) + '\n')
        print(f'{len(righe)} scores -> {uscita}', flush=True)
        return 0
    return 2
