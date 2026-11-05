"""AG-UI events as plain dicts (the wire format: camelCase keys, ``type`` in capitals).

The agent yields these; the server only has to serialise each one as a server-sent event
(``data: <json>``). Keeping them as dicts keeps ``ag-ui-protocol`` out of the agent core,
so the core still runs with numpy, scipy and pydantic alone.

Custom events used by the Dioscuri UI (``type`` ``CUSTOM``, by ``name``):

- ``usage``: one model call's tokens and seconds.
- ``clarification``: the one clarifying question (``intro`` and ``questions``).
- ``result``: the result card of the recommended design.
- ``checks``: the verifier checks of that design.
- ``suggestions``: follow-up prompts to offer as chips.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


def _event(kind: str, **fields: Any) -> Dict[str, Any]:
    out = {"type": kind, "timestamp": int(time.time() * 1000)}
    out.update({k: v for k, v in fields.items() if v is not None})
    return out


def run_started(thread_id: str, run_id: str) -> dict:
    """Return a ``RUN_STARTED`` event."""
    return _event("RUN_STARTED", threadId=thread_id, runId=run_id)


def run_finished(
    thread_id: str,
    run_id: str,
    interrupt: Optional[str] = None,
    usage: Optional[List[dict]] = None,
    result: Optional[dict] = None,
) -> dict:
    """Return a ``RUN_FINISHED`` event; ``interrupt`` names the reason when the run waits.

    Parameters
    ----------
    thread_id, run_id : str
        Identifiers of the conversation and of this run.
    interrupt : str, optional
        ``"clarification"`` when the run stops to ask the user something.
    usage : list of dict, optional
        Token usage per model (AG-UI ``TokenUsage``).
    result : dict, optional
        Run summary (behaviour, timings) for traces and evals.

    Returns
    -------
    dict
        The event.
    """
    outcome = (
        {"type": "interrupt", "interrupts": [{"id": f"{run_id}-ask", "reason": interrupt}]}
        if interrupt
        else {"type": "success"}
    )
    return _event(
        "RUN_FINISHED",
        threadId=thread_id,
        runId=run_id,
        outcome=outcome,
        usage=usage,
        result=result,
    )


def run_error(message: str, code: str = "agent_error") -> dict:
    """Return a ``RUN_ERROR`` event."""
    return _event("RUN_ERROR", message=message, code=code)


def step_started(name: str, label: str, kind: str, code: Optional[str] = None) -> dict:
    """Return a ``STEP_STARTED`` event; the metadata is what the UI's step row shows.

    Parameters
    ----------
    name : str
        Stable step id, for example ``"simulate"``.
    label : str
        Row text, for example ``"Simulate the year"``.
    kind : {"model", "tool", "check", "ask", "plan"}
        What the step does (``model`` rows get the "model call" chip).
    code : str, optional
        The call shown as code, for example ``simulate_year(A1, A2, A4)``.

    Returns
    -------
    dict
        The event.
    """
    return _event(
        "STEP_STARTED", stepName=name, metadata={"label": label, "kind": kind, "code": code}
    )


def step_finished(name: str, seconds: float, **extra: Any) -> dict:
    """Return a ``STEP_FINISHED`` event with the step's duration and any extra detail."""
    return _event("STEP_FINISHED", stepName=name, metadata=dict(extra, seconds=round(seconds, 3)))


def tool_call(call_id: str, name: str, args_json: str, result_json: str) -> List[dict]:
    """Return the four AG-UI events of one tool call (start, args, end, result).

    Parameters
    ----------
    call_id : str
        Unique id of the call.
    name : str
        Tool name.
    args_json : str
        Arguments as JSON.
    result_json : str
        Result as JSON.

    Returns
    -------
    list of dict
        ``TOOL_CALL_START``, ``TOOL_CALL_ARGS``, ``TOOL_CALL_END``, ``TOOL_CALL_RESULT``.
    """
    return [
        _event("TOOL_CALL_START", toolCallId=call_id, toolCallName=name),
        _event("TOOL_CALL_ARGS", toolCallId=call_id, delta=args_json),
        _event("TOOL_CALL_END", toolCallId=call_id),
        _event(
            "TOOL_CALL_RESULT",
            messageId=f"{call_id}-result",
            toolCallId=call_id,
            content=result_json,
            role="tool",
        ),
    ]


def text_message(message_id: str, text: str) -> List[dict]:
    """Return the three events of an assistant text message."""
    return [
        _event("TEXT_MESSAGE_START", messageId=message_id, role="assistant"),
        _event("TEXT_MESSAGE_CONTENT", messageId=message_id, delta=text),
        _event("TEXT_MESSAGE_END", messageId=message_id),
    ]


def custom(name: str, value: Any) -> dict:
    """Return a ``CUSTOM`` event (see the module docstring for the names in use)."""
    return _event("CUSTOM", name=name, value=value)
