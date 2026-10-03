"""A DeepSeek call that is never lost in silence (``tools/chiamata_deepseek.py``, 02/10/2026).

Until 02/10 every reader had its own ``chiama``: five retries on network errors, and an empty answer was saved empty
without saying why. Measured on 02/10: in the vLLM logs 32,000 requests all succeeded and none was refused for
context, yet 10-29% of the L05 readings, up to 10% of the L04 and 1-4% of the type readings were empty, with the
reasoning present and the answer missing: DeepSeek spent the answer cap (8,000 tokens) reasoning.

The policy, decided with the PI and reproduced by :meth:`ClienteDeepSeek.chiama`:

1. up to three IDENTICAL attempts (same instructions, same cap);
2. if the answer is still truncated after them (``finish_reason == 'length'``), one last attempt with the cap raised
   to 16,000 tokens, never beyond the room left in the vLLM context (65,536 tokens minus the prompt);
3. every reading carries how it went: attempts, finish reason, cap, error if any.

Since the evening of 02/10/2026 the live ``chiama`` takes an optional temperature and seed and its ``chiamata`` record
also carries ``modello``, ``istruzioni_sha256`` (SHA-256 of the prompt) and ``parametri`` (``max_tokens``,
``temperature``, ``seed``, ``extra_body``): :meth:`ClienteDeepSeek.chiama` writes the same keys, in the same order.
With ``compat=True`` it writes the record of the harness tools (commit 8650281, before that change), without them.
Beyond the live record it returns the extra key ``richiesta`` (model, prompt hash and length, sampling parameters),
which the readers do not save.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import time
from collections.abc import Callable
from typing import Any

from .config import LimitiDeepSeek


def json_finale(testo_ragionamento: str) -> str:
    """The JSON the reasoning ends with, or ``''``: same rule as ``tools/chiamata_deepseek.json_finale`` (02/10/2026).

    An empty answer that stopped normally is recovered from a complete JSON object that is the very last thing in the
    reasoning (only whitespace or code fences after it); never a draft in the middle of the reasoning.
    """
    t = (testo_ragionamento or '').rstrip()
    while t.endswith('```'):
        t = t[:-3].rstrip()
    if not t.endswith('}'):
        return ''
    dec = json.JSONDecoder()
    i = t.rfind('{')
    while i >= 0:
        try:
            obj, fine = dec.raw_decode(t, i)
        except ValueError:
            obj, fine = None, -1
        if fine == len(t) and isinstance(obj, dict):
            return t[i:fine]
        i = t.rfind('{', 0, i)
    return ''


def ragionamento(messaggio: Any) -> str:
    """The reasoning text of an answer message, wherever the server put it."""
    return (
        getattr(messaggio, 'reasoning_content', None)
        or getattr(messaggio, 'reasoning', None)
        or (getattr(messaggio, 'model_extra', None) or {}).get('reasoning')
        or ''
    )


def impronta(testo: str) -> str:
    """SHA-256 of the prompt text (UTF-8), in hexadecimal."""
    return hashlib.sha256(testo.encode('utf-8')).hexdigest()


class ClienteDeepSeek:
    """A DeepSeek (vLLM, OpenAI-compatible) client with the retry policy of 02/10/2026 (``cliente``: client).

    Args:
        cli: an ``openai.OpenAI`` client (or anything with ``chat.completions.create``).
        modello: the model name sent to the server (``deepseek-v4-flash``).
        extra_body: the ``extra_body`` of every request (``chat_template_kwargs``...).
        limiti: caps and attempts.
        temperature: sampling temperature; ``None`` (the live behaviour) leaves it to the server and does not send it.
        seed: sampling seed; ``None`` (the live behaviour) does not send it.
        dormi: the sleep function between network retries (``time.sleep``; tests pass a no-op).
        osservatore: called with the ``chiamata`` record after every call. The live code calls
            ``giornale.chiamata_deepseek`` here; :class:`tracepipe.giornale.Giornale` is passed by the CLI.
        compat: write the ``chiamata`` record of the harness tools (without ``modello``, ``istruzioni_sha256`` and
            ``parametri``, added live on 02/10/2026 evening).
    """

    def __init__(
        self,
        cli: Any,
        modello: str,
        extra_body: dict[str, Any] | None = None,
        limiti: LimitiDeepSeek | None = None,
        temperature: float | None = None,
        seed: int | None = None,
        dormi: Callable[[float], None] = time.sleep,
        osservatore: Callable[[dict[str, Any]], None] | None = None,
        compat: bool = False,
    ) -> None:
        self.cli = cli
        self.modello = modello
        self.extra_body = extra_body
        self.limiti = limiti or LimitiDeepSeek()
        self.temperature = temperature
        self.seed = seed
        self.dormi = dormi
        self.osservatore = osservatore
        self.compat = compat

    def _parametri(self, cap: int) -> dict[str, Any]:
        """Keyword arguments of one request; temperature and seed only when set."""
        kw: dict[str, Any] = {'max_tokens': cap, 'extra_body': self.extra_body}
        if self.temperature is not None:
            kw['temperature'] = self.temperature
        if self.seed is not None:
            kw['seed'] = self.seed
        return kw

    def _richiesta(self, testo: str, tetto: int) -> dict[str, Any]:
        """What was asked: the record the live code does not keep."""
        return {
            'modello': self.modello,
            'prompt_sha256': impronta(testo),
            'prompt_caratteri': len(testo),
            'temperature': self.temperature,
            'seed': self.seed,
            'max_tokens': tetto,
            'extra_body': copy.deepcopy(self.extra_body),
        }

    def _crea(self, testo: str, cap: int, storia: list[dict[str, Any]]) -> Any | None:
        """One attempt, retried on network or server errors; ``None`` if every retry failed."""
        for prova in range(self.limiti.errori_rete):
            try:
                return self.cli.chat.completions.create(
                    model=self.modello, messages=[{'role': 'user', 'content': testo}], **self._parametri(cap)
                )
            except Exception as e:  # network or server: retried, and the error stays written
                storia.append({'tetto': cap, 'errore': repr(e)[:300]})
                self.dormi(self.limiti.pausa_rete_s * (prova + 1))
        return None

    def _tetto_alto(self, cap: int, prompt_token: int | None) -> int | None:
        """The raised cap for the last attempt, if there is room for it in the context."""
        if not prompt_token:
            return None
        alto = min(self.limiti.tetto_alto, self.limiti.contesto - prompt_token - self.limiti.margine)
        return alto if alto > cap else None

    def chiama(self, testo: str, tetto: int | None = None, tentativi: int | None = None) -> dict[str, Any]:
        """Ask ``testo``; return the answer with its record.

        Keys: ``testo``, ``ragionamento``, ``token``, ``fine``, ``tetto``, ``chiamata`` (as live) and ``richiesta``.
        ``chiamata`` is the live record: ``tentativi`` (attempts made, network errors included), ``fine`` (finish
        reason), ``tetto`` (cap of the last answer), ``prompt_token``, ``riuscita`` (non-empty answer), ``storia``
        (one entry per attempt or network error), then ``modello``, ``istruzioni_sha256`` and ``parametri`` (the cap
        asked first, temperature, seed, extra_body) unless ``compat``.
        """
        tetto = self.limiti.tetto if tetto is None else tetto
        tentativi = self.limiti.tentativi if tentativi is None else tentativi
        storia: list[dict[str, Any]] = []
        prompt_token: int | None = None
        ultimo: dict[str, Any] | None = None
        piano = [tetto] * tentativi
        k = 0
        while k < len(piano):
            cap = piano[k]
            r = self._crea(testo, cap, storia)
            if r is None:
                k += 1
                continue
            c = r.choices[0]
            m = c.message
            prompt_token = getattr(r.usage, 'prompt_tokens', None) or prompt_token
            ultimo = {
                'testo': m.content or '',
                'ragionamento': ragionamento(m),
                'token': getattr(r.usage, 'completion_tokens', 0),
                'fine': c.finish_reason,
                'tetto': cap,
            }
            storia.append({'tetto': cap, 'fine': c.finish_reason, 'token': ultimo['token']})
            # empty answer that stopped normally: the JSON the reasoning ends with counts as the answer (not in compat)
            if not self.compat and not ultimo['testo'].strip() and c.finish_reason == 'stop':
                dal = json_finale(ultimo['ragionamento'])
                if dal:
                    ultimo['testo'] = dal
                    ultimo['dal_ragionamento'] = True
                    storia[-1]['dal_ragionamento'] = True
            # truncated but not empty (03/10/2026, external review): a cut text that does not end with valid JSON is
            # not an answer; it is kept aside and retried as if empty (then, if needed, the raised cap)
            if (
                not self.compat
                and ultimo['testo'].strip()
                and c.finish_reason == 'length'
                and not json_finale(ultimo['testo'])
            ):
                ultimo['testo_troncato'] = ultimo['testo']
                ultimo['testo'] = ''
                storia[-1]['troncata'] = True
            if ultimo['testo'].strip():
                break
            k += 1
            # after the identical attempts, if truncated: a single one with the raised cap
            if k == tentativi and c.finish_reason == 'length':
                alto = self._tetto_alto(cap, prompt_token)
                if alto is not None:
                    piano.append(alto)
        esito = ultimo or {'testo': '', 'ragionamento': '', 'token': 0, 'fine': None, 'tetto': tetto}
        esito['chiamata'] = {
            'tentativi': len(storia),
            'fine': esito.get('fine'),
            'tetto': esito.get('tetto'),
            'prompt_token': prompt_token,
            'riuscita': bool(esito['testo'].strip()),
        }
        if not self.compat:  # same key order as the live record: right after ``riuscita``
            esito['chiamata']['dal_ragionamento'] = bool(esito.get('dal_ragionamento'))
        esito['chiamata']['storia'] = storia
        if not self.compat:
            esito['chiamata'].update(
                {
                    'modello': self.modello,
                    'istruzioni_sha256': impronta(testo),
                    'parametri': {
                        'max_tokens': tetto,
                        'temperature': self.temperature,
                        'seed': self.seed,
                        'extra_body': self.extra_body,
                    },
                }
            )
        esito['richiesta'] = self._richiesta(testo, tetto)
        if self.osservatore is not None:
            with contextlib.suppress(Exception):  # the journal must never break a reading (as in the live code)
                self.osservatore(esito['chiamata'])
        return esito
