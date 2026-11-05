"""Small-model calls through Ollama, with fixed settings and a record of every call.

ADR-0002: at most two model calls per question, grammar-constrained JSON for the first one,
the same options on every call (changing ``num_ctx``, ``num_thread`` or ``num_batch``
reloads the model) and every call's tokens and durations logged. Only local open-weight
models are used: the client talks to a local Ollama server, never to a hosted API.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass
from typing import Callable, List, Optional, Sequence, Tuple, Union

# GEMINI's .env names its chat model LLM_MODEL_VERSION; ours wins when both are set.
DEFAULT_MODEL = (
    os.environ.get("DIOSCURI_MODEL") or os.environ.get("LLM_MODEL_VERSION") or "qwen3:1.7b"
)
DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")


# A formula's LaTeX in a JSON string: "\text{ °C}" is read as a tab and "ext{ °C}", "\frac" as
# a form feed (2 Nov: "86.1	ext{ °C}" in a reply). Commands that start with a JSON escape's
# letter get their backslash escaped before the JSON is read.
LATEX_IN_JSON = re.compile(
    r"(?<!\\)\\(?=(?:text|textbf|times|theta|tau|frac|beta|begin|bar|rho|right|rightarrow|"
    r"neq|nabla)(?![a-zA-Z]))"
)


def latex_escapes(content: str) -> str:
    """Return a model's JSON with LaTeX commands kept whole (a text command, not a tab)."""
    return LATEX_IN_JSON.sub(r"\\\\", content)


# The context guard (4 Nov). A prompt longer than the window is cut by Ollama without a word:
# on 3 Nov a 55,000-character answer prompt came back as 4,098 prompt tokens, its rules gone,
# and 11 of 266 answer prompts were within 1,400 tokens of the 8,192 window (no room to answer).
# Qwen's tokenizers give every digit its own token, so number-heavy blocks run at 2.8-3.1
# characters a token and prose at about 4. Digits and non-ASCII characters count one token
# each, the rest one per 3.6 characters: 0-15 % above the counts measured on qwen3.5:9b.
DIGIT = re.compile(r"\d")
NON_ASCII = re.compile(r"[^\x00-\x7f]")
CHARS_PER_TOKEN = 3.6  # letters, spaces and punctuation
MESSAGE_TOKENS = 6  # each chat message's role and markers
IMAGE_TOKENS = 1200  # an image sent with a message (a vision model's tiles, roughly)
GUARD_MARGIN = 48  # tokens kept free beyond the prompt and the answer


def estimate_tokens(text: str) -> int:
    """Return about how many tokens ``text`` takes (a little more rather than less)."""
    text = text or ""
    digits = len(DIGIT.findall(text))
    wide = len(NON_ASCII.findall(text))
    return int(digits + wide + (len(text) - digits - wide) / CHARS_PER_TOKEN) + 1


def prompt_tokens(messages: Sequence[dict]) -> int:
    """Return about how many tokens a chat's messages take (``estimate_tokens`` each)."""
    total = 0
    for m in messages:
        total += estimate_tokens(str(m.get("content") or "")) + MESSAGE_TOKENS
        total += IMAGE_TOKENS * len(m.get("images") or [])
    return total


# The model's own thinking (``think=True``, 4 Nov): kept out of the answer, and only its start
# and end in the trace (``LLMCall.thinking``).
THINKING_HEAD = 900
THINKING_TAIL = 300
THINK_TAG = re.compile(r"^\s*<think>(.*?)</think>\s*", re.S)


def shorten_thinking(text: str) -> str:
    """Return a model's thinking for the trace: its start and its end, the middle left out."""
    text = (text or "").strip()
    if len(text) <= THINKING_HEAD + THINKING_TAIL + 20:
        return text
    gone = len(text) - THINKING_HEAD - THINKING_TAIL
    return f"{text[:THINKING_HEAD]} … [{gone} characters left out] … {text[-THINKING_TAIL:]}"


def room(llm, num_predict: int) -> int:
    """Return the prompt tokens a model's window leaves after ``num_predict`` and a margin."""
    ctx = int((getattr(llm, "options", None) or {}).get("num_ctx", 8192))
    return ctx - num_predict - GUARD_MARGIN


@dataclass
class LLMCall:
    """Tokens and timing of one model call.

    ``seconds`` is the wall time; Ollama splits it into loading the model
    (``load_seconds``), reading the prompt (``prompt_seconds``, short when the prompt prefix
    is cached) and writing the answer (``output_seconds``).
    """

    purpose: str
    model: str
    prompt_tokens: int = 0
    output_tokens: int = 0
    seconds: float = 0.0
    load_seconds: float = 0.0
    prompt_seconds: float = 0.0
    output_seconds: float = 0.0
    ok: bool = True
    error: str = ""
    estimated_tokens: int = 0  # the guard's estimate of the prompt, before it was sent
    num_ctx: int = 0  # the window the call ran in
    # Sent with the model's own thinking (``think=True``): what it thought, shortened, and about
    # how many of ``output_tokens`` it took (Ollama counts thinking and answer together).
    think: bool = False
    thinking: str = ""
    thinking_tokens: int = 0

    def as_dict(self) -> dict:
        """Return the record as a plain dict for traces and events."""
        return asdict(self)


class LLMError(RuntimeError):
    """A model call failed or returned something unusable; ``call`` says what it cost."""

    def __init__(self, message: str, call: Optional[LLMCall] = None):
        """Keep the call record so the failed call is still counted.

        Parameters
        ----------
        message : str
            What went wrong.
        call : LLMCall, optional
            The record of the failed call.
        """
        super().__init__(message)
        self.call = call


class ModelUnavailable(LLMError):
    """The model server is not running, or the model is not pulled; no answer was possible."""


class ContextOverflow(LLMError):
    """The prompt would not fit the model's window with its answer: it was not sent.

    Ollama would cut the prompt's start without a word (the rules first); callers trim their
    lowest-value context before calling (``room``), so this is the last guard.
    """


def unavailable_hint(model: str, error: str) -> str:
    """Return what to do about a model that could not be reached.

    Parameters
    ----------
    model : str
        The configured model tag.
    error : str
        The error text of the failed call.

    Returns
    -------
    str
        The command that fixes it, or "" when the model was only too slow (ask again).
    """
    reason = unavailable_reason(error)
    return {"not_pulled": f"ollama pull {model}", "timeout": ""}.get(reason, "ollama serve")


def unavailable_reason(error: str) -> str:
    """Return ``"not_pulled"``, ``"timeout"`` or ``"not_running"`` for a failed call's error."""
    text = error.lower()
    if "not found" in text:
        return "not_pulled"
    if "timed out" in text or "timeout" in text:
        return "timeout"
    return "not_running"


class OllamaLLM:
    """A local model served by Ollama.

    Parameters
    ----------
    model : str
        Ollama model tag, for example ``qwen3:1.7b``.
    host : str, optional
        Ollama server URL; defaults to ``$OLLAMA_HOST`` or the local server.
    device : {"auto", "cpu"}
        ``"cpu"`` keeps every layer on the CPU (``num_gpu=0``) with ``num_thread`` threads,
        which is how the judges' laptops run it.
    num_ctx : int
        Context window; fixed for every call so the model never reloads.
    num_thread : int
        CPU threads when ``device="cpu"``.
    seed : int
        Sampling seed (temperature is 0 anyway).
    timeout : float
        Seconds before a call is abandoned.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        host: Optional[str] = None,
        device: str = "auto",
        num_ctx: int = 4096,
        num_thread: int = 8,
        seed: int = 42,
        timeout: float = 300.0,
    ):
        """Create the client; no request is sent until the first call."""
        from ollama import Client

        self.model = model
        self.device = device
        self._client = Client(host=host or DEFAULT_HOST, timeout=timeout)
        self.options = {"temperature": 0, "seed": seed, "num_ctx": num_ctx}
        if device == "cpu":
            self.options.update(num_gpu=0, num_thread=num_thread)
        self._think_supported = True

    def _chat(
        self, purpose: str, messages: Sequence[dict], fmt, num_predict: int
    ) -> Tuple[str, LLMCall]:
        """Send one chat call and return the answer (the message's content) and its record."""
        content, _, call = self._send(purpose, messages, fmt, num_predict)
        return content, call

    def _send(
        self, purpose: str, messages: Sequence[dict], fmt, num_predict: int, think: bool = False
    ) -> Tuple[str, str, LLMCall]:
        """Send one chat call; return the answer, the model's thinking and the call record.

        ``think`` lets the model think first; the thinking is never part of the answer, and the
        record keeps it shortened. Without ``think`` the model is told not to think.
        """
        from ollama import ResponseError

        ctx = int(self.options.get("num_ctx", 0))
        estimate = prompt_tokens(messages)
        if ctx and estimate > ctx - num_predict - GUARD_MARGIN:
            call = LLMCall(
                purpose,
                self.model,
                ok=False,
                error=f"prompt of about {estimate} tokens does not fit the {ctx}-token window "
                f"with {num_predict} to write: not sent",
                estimated_tokens=estimate,
                num_ctx=ctx,
            )
            raise ContextOverflow(call.error, call)
        kwargs = dict(
            model=self.model,
            messages=list(messages),
            keep_alive=-1,
            options=dict(self.options, num_predict=num_predict),
        )
        if fmt is not None:
            kwargs["format"] = fmt
        start = time.perf_counter()
        thinks = bool(think) and self._think_supported
        try:
            if self._think_supported:
                try:
                    resp = self._client.chat(think=thinks, **kwargs)
                except ResponseError as err:
                    if "think" not in str(err).lower():
                        raise
                    self._think_supported = thinks = False
                    resp = self._client.chat(**kwargs)
            else:
                resp = self._client.chat(**kwargs)
        except Exception as err:  # connection refused, model missing, timeout
            call = LLMCall(
                purpose,
                self.model,
                seconds=round(time.perf_counter() - start, 3),
                ok=False,
                error=f"{type(err).__name__}: {err}",
            )
            raise ModelUnavailable(call.error, call) from err
        call = LLMCall(
            purpose,
            self.model,
            prompt_tokens=resp.prompt_eval_count or 0,
            output_tokens=resp.eval_count or 0,
            seconds=round(time.perf_counter() - start, 3),
            load_seconds=round((resp.load_duration or 0) / 1e9, 3),
            prompt_seconds=round((resp.prompt_eval_duration or 0) / 1e9, 3),
            output_seconds=round((resp.eval_duration or 0) / 1e9, 3),
            estimated_tokens=estimate,
            num_ctx=ctx,
        )
        if ctx and call.prompt_tokens + call.output_tokens >= ctx - 2:
            # The window filled up (the estimate was short): say so in the trace.
            call.error = f"the {ctx}-token window was full; the prompt or the answer was cut"
        content = resp.message.content or ""
        thinking = getattr(resp.message, "thinking", None) or ""
        tagged = THINK_TAG.match(content)
        if tagged:  # a server that leaves the thinking in the content: never part of the answer
            thinking, content = (thinking + "\n" + tagged.group(1)).strip(), content[tagged.end() :]
        if thinks or thinking:
            call.think = thinks
            call.thinking = shorten_thinking(thinking)
            call.thinking_tokens = estimate_tokens(thinking) if thinking else 0
        return content, thinking, call

    def structured(
        self, purpose: str, messages: Sequence[dict], schema: dict, num_predict: int = 256
    ) -> Tuple[dict, LLMCall]:
        """Return the model's answer constrained to a JSON schema.

        Parameters
        ----------
        purpose : str
            Short label for the trace, for example ``"intake"``.
        messages : sequence of dict
            Chat messages (``role`` and ``content``).
        schema : dict
            JSON schema the output must follow (Ollama ``format``).
        num_predict : int
            Output token budget.

        Returns
        -------
        tuple of (dict, LLMCall)
            The parsed JSON and the call record.

        Raises
        ------
        LLMError
            If the server fails or the output is not valid JSON.
        """
        content, call = self._chat(purpose, messages, schema, num_predict)
        try:
            return json.loads(latex_escapes(content)), call
        except json.JSONDecodeError as err:
            call.ok, call.error = False, f"invalid JSON: {content[:120]!r}"
            raise LLMError(call.error, call) from err

    def think(
        self, purpose: str, messages: Sequence[dict], num_predict: int
    ) -> Tuple[str, str, LLMCall]:
        """Let the model think about the messages, with no format; return what it thought.

        A thinking model given a JSON format and a budget may think until the budget is gone
        and write no JSON at all (4 Nov: qwen3.5:9b used all of 3,448 tokens thinking on a
        trade-off question). So the thinking is a call of its own, cut at ``num_predict``,
        and the formatted answer is a second call that reads it.

        Returns
        -------
        tuple of (str, str, LLMCall)
            The thinking (whole, possibly cut off), any answer written after it, and the call
            record (the thinking shortened in it).
        """
        content, thinking, call = self._send(purpose, messages, None, num_predict, think=True)
        return thinking, content, call

    def text(
        self, purpose: str, messages: Sequence[dict], num_predict: int = 150
    ) -> Tuple[str, LLMCall]:
        """Return a free-text answer, used only for the short optional explanation.

        Parameters
        ----------
        purpose : str
            Short label for the trace.
        messages : sequence of dict
            Chat messages.
        num_predict : int
            Output token budget.

        Returns
        -------
        tuple of (str, LLMCall)
            The text and the call record.
        """
        return self._chat(purpose, messages, None, num_predict)

    def available(self) -> Tuple[bool, str]:
        """Return whether the server answers and has the model pulled, and why not.

        Returns
        -------
        tuple of (bool, str)
            ``(True, "")`` when ready; otherwise ``False`` and the command that fixes it.
        """
        try:
            listed = self._client.list()
        except Exception:  # noqa: BLE001 - any failure means "not reachable"
            return False, "ollama serve"
        names = {m.model for m in listed.models}
        tag = self.model if ":" in self.model else self.model + ":latest"
        if tag not in names:
            return False, f"ollama pull {self.model}"
        return True, ""

    def warm(self) -> LLMCall:
        """Load the model into memory so the first real question does not pay for it.

        Returns
        -------
        LLMCall
            The record of the warm-up call.
        """
        _, call = self._chat("warm-up", [{"role": "user", "content": "ok"}], None, 1)
        return call


Script = Union[Callable[[str, Sequence[dict]], Union[dict, str]], List[Union[dict, str]]]


class ScriptedLLM:
    """Stand-in model for tests: replies come from a list (in order) or from a function.

    Parameters
    ----------
    script : list or callable
        Either the replies in call order, or ``f(purpose, messages) -> reply``. A reply
        is a dict for structured calls or a string for text calls; an ``Exception``
        instance in the list is raised instead (a ``ConnectionError`` as
        ``ModelUnavailable``).
    model : str
        Name recorded in call records.
    """

    def __init__(self, script: Script, model: str = "scripted"):
        """Store the script."""
        self.model = model
        self._script = script
        self.calls: List[LLMCall] = []

    def _next(self, purpose: str, messages: Sequence[dict]):
        if callable(self._script):
            reply = self._script(purpose, messages)
        else:
            reply = self._script.pop(0)
        call = LLMCall(purpose, self.model, prompt_tokens=100, output_tokens=20, seconds=0.01)
        self.calls.append(call)
        if isinstance(reply, Exception):
            call.ok, call.error = False, str(reply)
            gone = isinstance(reply, (ConnectionError, ModelUnavailable))
            raise (ModelUnavailable if gone else LLMError)(str(reply), call)
        return reply, call

    def available(self) -> Tuple[bool, str]:
        """Return ``(True, "")``: a script is always there."""
        return True, ""

    def structured(
        self, purpose: str, messages: Sequence[dict], schema: dict, num_predict: int = 256
    ) -> Tuple[dict, LLMCall]:
        """Return the next scripted dict."""
        return self._next(purpose, messages)

    def text(
        self, purpose: str, messages: Sequence[dict], num_predict: int = 150
    ) -> Tuple[str, LLMCall]:
        """Return the next scripted string."""
        return self._next(purpose, messages)

    def think(
        self, purpose: str, messages: Sequence[dict], num_predict: int
    ) -> Tuple[str, str, LLMCall]:
        """Return the next scripted string as the model's thinking (no answer after it)."""
        thought, call = self._next(purpose, messages)
        call.think, call.thinking = True, str(thought)
        return str(thought), "", call
