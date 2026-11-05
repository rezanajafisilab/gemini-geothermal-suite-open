"""Model generation: a local model writes a missing component model and the sandbox tests it.

Dioscuri has no model for some components a design may need (an adsorption chiller fed by the
heat-exchanger outlet, seasonal aquifer storage for A3). For each one ``SPECS``
(``component_specs.py``) holds a ``ComponentSpec``: what the component does, its inputs and
outputs with units, the physics relations to implement (from the literature, cited per spec),
reference cases and the physics checks the code must pass.

``generate`` asks the model for the code (one JSON-schema call, prompt ``prompts/modelgen_v1``),
then ``check_model`` tests it: the sandbox rules, a run on every reference case in one child
process, and the physics checks. Whatever fails (a rule, an error with its line, a check with
the case and numbers) goes back to the model as the next message, up to ``max_attempts``
times. The result holds the code, every attempt, the model calls and the final test table.

Nothing is registered automatically. The agent shows the code and the table to the user, and
only on their approval calls ``Registry.save(result, approved_by="user")``. A registered model
is a ``.py`` file with a header (spec, model, date, test table) in a git-ignored folder, and is
only ever run through the sandbox: ``Registry.evaluate(name, cases)``.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence

from gemini_agent import sandbox
from gemini_agent.component_specs import (  # noqa: F401 - SPECS and find_spec are re-exported
    SPECS,
    ComponentSpec,
    all_checks,
    case_label,
    find_spec,
    fmt,
    run_checks,
)
from gemini_agent.contract import Check
from gemini_agent.llm import LLMCall, LLMError, ModelUnavailable

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
PROMPT_VERSION = os.environ.get("DIOSCURI_MODELGEN_PROMPT", "modelgen_v1")
ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = Path(
    os.environ.get("DIOSCURI_MODELS") or ROOT / "hackathon" / "evals" / "runs" / "generated_models"
)
NUM_PREDICT = 1500
CODE_MARKER = "# ---- code ----"

SCHEMA = {
    "type": "object",
    # The cap keeps a chatty reason from eating the output budget before the code.
    "properties": {"reason": {"type": "string", "maxLength": 200}, "code": {"type": "string"}},
    "required": ["reason", "code"],
}


# ---------------------------------------------------------------------------------------------
# Generation


@dataclass
class Attempt:
    """One answer of the model and what the tests made of it.

    Attributes
    ----------
    number : int
        1 for the first answer.
    reason : str
        The model's own summary of its code.
    code : str
        The code it wrote.
    violations : list of str
        Sandbox rules it broke (the code was not run).
    error : str
        What stopped the attempt: an unusable reply, a load error, a timeout.
    case_errors : list of str
        Errors raised on individual cases, with the case and the line.
    checks : list of Check
        Physics check results (empty when the code did not run cleanly).
    outputs : list of dict or None
        Outputs per reference case.
    sandbox_seconds : float
        Time spent checking and running the code.
    call : LLMCall, optional
        The model call that produced it.
    """

    number: int
    reason: str = ""
    code: str = ""
    violations: List[str] = field(default_factory=list)
    error: str = ""
    case_errors: List[str] = field(default_factory=list)
    checks: List[Check] = field(default_factory=list)
    outputs: List[Optional[dict]] = field(default_factory=list)
    sandbox_seconds: float = 0.0
    call: Optional[LLMCall] = None

    @property
    def failed_checks(self) -> List[Check]:
        """Return the checks that failed."""
        return [c for c in self.checks if not c.passed]

    @property
    def passed(self) -> bool:
        """Return True when the code ran cleanly and passed every check."""
        return (
            not self.violations
            and not self.error
            and not self.case_errors
            and bool(self.checks)
            and not self.failed_checks
        )

    def problems(self, rules: Optional[Dict[str, str]] = None) -> List[str]:
        """Return every problem as one plain line, the way the model is told about them.

        Parameters
        ----------
        rules : dict, optional
            ``{check name: rule}``; a failed check then also quotes its rule.

        Returns
        -------
        list of str
            One line per problem.
        """
        rules = rules or {}
        lines = [f"Sandbox rule: {v}" for v in self.violations]
        if self.error:
            lines.append(f"Error: {self.error}")
        lines += [f"Error {e}" for e in self.case_errors[:3]]
        if len(self.case_errors) > 3:
            lines.append(f"... and {len(self.case_errors) - 3} more cases raise errors")
        for c in self.failed_checks:
            rule = f" (rule: {rules[c.name]})" if c.name in rules else ""
            lines.append(f"Failed check '{c.name}'{rule}: {c.detail}")
        return lines

    def as_dict(self) -> dict:
        """Return the attempt as a plain dict for traces and events."""
        data = asdict(self)
        data["checks"] = [c.model_dump() for c in self.checks]
        data["call"] = self.call.as_dict() if self.call else None
        data["passed"] = self.passed
        return data


@dataclass
class GenerationResult:
    """The outcome of ``generate``: the code to show the user, and how it was reached.

    Attributes
    ----------
    component : str
        Spec name.
    model : str
        The model that wrote the code.
    prompt_version : str
        Prompt file stem.
    passed : bool
        True when the final code passed every test; only then may it be registered.
    code : str
        The passing code, or the best failing attempt.
    attempts : list of Attempt
        Every attempt in order.
    calls : list of LLMCall
        Every model call (tokens and seconds).
    checks : list of Check
        The check results of ``code``.
    table : list of dict
        Inputs and outputs of ``code`` at every reference case.
    """

    component: str
    model: str
    prompt_version: str
    passed: bool
    code: str
    attempts: List[Attempt]
    calls: List[LLMCall]
    checks: List[Check]
    table: List[dict]

    @property
    def tokens(self) -> Dict[str, int]:
        """Return the prompt and output tokens of all calls."""
        return {
            "prompt": sum(c.prompt_tokens for c in self.calls),
            "output": sum(c.output_tokens for c in self.calls),
        }

    @property
    def seconds(self) -> float:
        """Return the time spent in model calls and in the sandbox."""
        return round(
            sum(c.seconds for c in self.calls) + sum(a.sandbox_seconds for a in self.attempts), 3
        )

    def table_markdown(self) -> str:
        """Return the test table and the checks as Markdown, for the approval card."""
        spec = SPECS.get(self.component)
        lines = []
        if self.table:
            heads = list(self.table[0])
            units = {q.name: q.unit for q in (spec.inputs + spec.outputs)} if spec else {}
            lines.append("| " + " | ".join(f"{h} [{units.get(h, '')}]" for h in heads) + " |")
            lines.append("|" + "---|" * len(heads))
            for row in self.table:
                lines.append("| " + " | ".join(f"{row[h]:.3g}" for h in heads) + " |")
            lines.append("")
        for c in self.checks:
            lines.append(f"- {'PASS' if c.passed else 'FAIL'} {c.name}: {c.detail}")
        return "\n".join(lines)

    def as_dict(self) -> dict:
        """Return the result as a plain dict for the approval card and traces."""
        return {
            "component": self.component,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "passed": self.passed,
            "code": self.code,
            "checks": [c.model_dump() for c in self.checks],
            "table": self.table,
            "attempts": [a.as_dict() for a in self.attempts],
            "tokens": self.tokens,
            "seconds": self.seconds,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GenerationResult":
        """Rebuild a result from ``as_dict``, for example from a saved session at approval.

        Parameters
        ----------
        data : dict
            What ``as_dict`` returned.

        Returns
        -------
        GenerationResult
            The same result; ``Registry.save`` re-tests its code anyway.
        """
        attempts = []
        for a in data["attempts"]:
            fields = {k: v for k, v in a.items() if k not in ("checks", "call", "passed")}
            attempt = Attempt(**fields, checks=[Check(**c) for c in a["checks"]])
            attempt.call = LLMCall(**a["call"]) if a.get("call") else None
            attempts.append(attempt)
        return cls(
            component=data["component"],
            model=data["model"],
            prompt_version=data["prompt_version"],
            passed=bool(data["passed"]),
            code=data["code"],
            attempts=attempts,
            calls=[a.call for a in attempts if a.call],
            checks=[Check(**c) for c in data["checks"]],
            table=data["table"],
        )


def load_prompt(version: str = PROMPT_VERSION) -> str:
    """Return the system prompt of a versioned model-generation prompt file.

    Parameters
    ----------
    version : str
        File stem in ``prompts/``, for example ``"modelgen_v1"``.

    Returns
    -------
    str
        The system prompt.
    """
    return (PROMPT_DIR / f"{version}.txt").read_text(encoding="utf-8").strip()


def spec_message(spec: ComponentSpec) -> str:
    """Return the user message that asks for one component model.

    Parameters
    ----------
    spec : ComponentSpec
        The component.

    Returns
    -------
    str
        Interface, physics and the tests the code will face.
    """
    lines = [
        f"Component: {spec.title}.",
        spec.description,
        "",
        f"Write the function: def {spec.func_name}({', '.join(spec.arguments)}):",
        "",
        "Inputs (keyword arguments, plain numbers):",
    ]
    for q in spec.inputs:
        lines.append(
            f"- {q.name} [{q.unit}]: {q.description}; typical {fmt(q.low)} to {fmt(q.high)}"
        )
    lines += ["", "Return a dict with exactly these keys, each a float:"]
    lines += [f"- {q.name} [{q.unit}]: {q.description}" for q in spec.outputs]
    lines += ["", "Physics, in this order:"]
    lines += [f"{i}. {step}" for i, step in enumerate(spec.physics, 1)]
    lines += ["", f"The code is run on {len(spec.cases)} cases and must pass these tests:"]
    lines += [f"- {c.name}: {c.rule}" for c in all_checks(spec)]
    return "\n".join(lines)


def feedback(attempt: Attempt, spec: Optional[ComponentSpec] = None, limit: int = 1800) -> str:
    """Return the message that tells the model what failed, for its next attempt.

    Parameters
    ----------
    attempt : Attempt
        The attempt that failed.
    spec : ComponentSpec, optional
        When given, each failed check also quotes its rule.
    limit : int
        Character cap, so the context stays small.

    Returns
    -------
    str
        The problems, one per line, and what to send back.
    """
    rules = {c.name: c.rule for c in all_checks(spec)} if spec else {}
    text = "\n".join(
        ["Your code did not pass. Fix every problem below:"]
        + [f"- {p}" for p in attempt.problems(rules)]
        + ["Reply with the whole corrected code in the same JSON form."]
    )
    return text if len(text) <= limit else text[: limit - 4] + " ..."


def clean_code(code: str) -> str:
    """Return the code without Markdown fences and with real line breaks.

    Parameters
    ----------
    code : str
        The ``code`` field of the model's reply.

    Returns
    -------
    str
        Plain Python source.
    """
    code = code.strip()
    fence = re.match(r"^```[a-zA-Z]*\n(.*?)\n?```$", code, re.S)
    if fence:
        code = fence.group(1)
    if "\n" not in code and "\\n" in code:  # double-escaped by the model
        code = code.replace("\\n", "\n").replace('\\"', '"')
    return code.strip() + "\n"


def check_model(spec: ComponentSpec, code: str, timeout_s: float = 5.0) -> Attempt:
    """Test code against a spec: sandbox rules, a run on every reference case, the checks.

    Parameters
    ----------
    spec : ComponentSpec
        The component.
    code : str
        Python source.
    timeout_s : float
        Sandbox wall-clock limit for the batch.

    Returns
    -------
    Attempt
        Numbered 0, with no reason or call; ``passed`` says whether it may be registered.
    """
    attempt = Attempt(number=0, code=code)
    cases = [c.inputs for c in spec.cases]
    result = sandbox.run(code, spec.func_name, cases, timeout_s, arguments=spec.arguments)
    attempt.sandbox_seconds = result.seconds
    attempt.violations = result.violations
    attempt.outputs = result.outputs
    if result.violations:
        return attempt
    if result.error:
        attempt.error = result.error
        return attempt
    attempt.case_errors = [
        f"at {case_label(case)}: {err}" for case, err in zip(cases, result.errors) if err
    ]
    if not attempt.case_errors:
        attempt.checks = run_checks(spec, cases, result.outputs)
    return attempt


def iter_generate(
    spec: ComponentSpec,
    llm,
    max_attempts: int = 3,
    prompt_version: str = PROMPT_VERSION,
    timeout_s: float = 5.0,
    num_predict: int = NUM_PREDICT,
) -> Iterator[Attempt]:
    """Ask the model for the code and correct it until it passes; yield each attempt.

    The generator's return value (``StopIteration.value``, or ``result = yield from ...``)
    is the ``GenerationResult``. Each retry sends the spec, the previous answer and the
    list of problems, so the context stays the same size whatever the attempt number.

    Parameters
    ----------
    spec : ComponentSpec
        The component to write.
    llm : OllamaLLM or ScriptedLLM
        Anything with ``structured(purpose, messages, schema, num_predict)`` and ``model``.
    max_attempts : int
        Model calls at most.
    prompt_version : str
        Prompt file stem.
    timeout_s : float
        Sandbox limit per attempt.
    num_predict : int
        Output token budget per call.

    Yields
    ------
    Attempt
        Each attempt as soon as it is tested.

    Raises
    ------
    ModelUnavailable
        If the model server is down or the model is not pulled.
    """
    first = [
        {"role": "system", "content": load_prompt(prompt_version)},
        {"role": "user", "content": spec_message(spec)},
    ]
    messages = list(first)
    attempts: List[Attempt] = []
    calls: List[LLMCall] = []
    for number in range(1, max_attempts + 1):
        reply, call, error = None, None, "the reply had no code"
        try:
            reply, call = llm.structured("modelgen", messages, SCHEMA, num_predict=num_predict)
        except ModelUnavailable:
            raise
        except LLMError as err:
            call = err.call
            error = f"the reply was not valid JSON, perhaps cut off ({err})"
        if isinstance(reply, dict) and str(reply.get("code", "")).strip():
            attempt = check_model(spec, clean_code(str(reply["code"])), timeout_s)
            attempt.reason = str(reply.get("reason", ""))[:500]
        else:
            attempt = Attempt(number=0, error=error)
        attempt.number, attempt.call = number, call
        if call is not None:
            calls.append(call)
        attempts.append(attempt)
        yield attempt
        if attempt.passed:
            break
        answer = json.dumps({"reason": attempt.reason, "code": attempt.code})
        retry = (
            first
            + ([{"role": "assistant", "content": answer}] if attempt.code else [])
            + [{"role": "user", "content": feedback(attempt, spec)}]
        )
        if retry == messages:  # at temperature 0 the same prompt gives the same answer
            break
        messages = retry
    best = _best(attempts)
    table = [dict(case.inputs, **(out or {})) for case, out in zip(spec.cases, best.outputs or [])]
    return GenerationResult(
        component=spec.name,
        model=getattr(llm, "model", "unknown"),
        prompt_version=prompt_version,
        passed=best.passed,
        code=best.code,
        attempts=attempts,
        calls=calls,
        checks=best.checks,
        table=table if best.outputs and all(best.outputs) else [],
    )


def _best(attempts: Sequence[Attempt]) -> Attempt:
    """Return the passing attempt, else the latest one with the fewest problems."""
    for a in attempts:
        if a.passed:
            return a
    ranked = sorted(attempts, key=lambda a: (len(a.problems()) if a.code else 99, -a.number))
    return ranked[0]


def generate(spec: ComponentSpec, llm, max_attempts: int = 3, **kwargs) -> GenerationResult:
    """Generate and test a component model with self-correction; see ``iter_generate``.

    Parameters
    ----------
    spec : ComponentSpec
        The component to write.
    llm : OllamaLLM or ScriptedLLM
        The model.
    max_attempts : int
        Model calls at most.
    **kwargs
        ``prompt_version``, ``timeout_s`` and ``num_predict`` for ``iter_generate``.

    Returns
    -------
    GenerationResult
        Code, attempts, calls and the final test table.
    """
    steps = iter_generate(spec, llm, max_attempts, **kwargs)
    while True:
        try:
            next(steps)
        except StopIteration as done:
            return done.value


# ---------------------------------------------------------------------------------------------
# Registry


class ModelRunError(RuntimeError):
    """A registered model failed in the sandbox; the message says why."""


@dataclass
class RegisteredModel:
    """A model the user approved, as stored on disk."""

    name: str
    code: str
    meta: dict
    path: Path

    @property
    def func_name(self) -> str:
        """Return the function to call."""
        return self.meta["func_name"]

    @property
    def arguments(self) -> List[str]:
        """Return its input names."""
        return [q["name"] for q in self.meta["inputs"]]


@dataclass
class Evaluation:
    """A registered model run at some operating points, with its per-case checks.

    Attributes
    ----------
    name : str
        Registered model name.
    cases : list of dict
        The inputs used, defaults filled in.
    assumed : list of list of str
        Per case, the inputs taken from the defaults.
    outputs : list of dict
        The outputs per case.
    checks : list of Check
        Per-case physics checks of the spec on these outputs.
    warnings : list of str
        Inputs outside the range the model was tested on.
    seconds : float
        Sandbox time.
    """

    name: str
    cases: List[dict]
    assumed: List[List[str]]
    outputs: List[dict]
    checks: List[Check]
    warnings: List[str]
    seconds: float

    @property
    def passed(self) -> bool:
        """Return True when every per-case check passed."""
        return all(c.passed for c in self.checks)

    def as_dict(self) -> dict:
        """Return the evaluation as a plain dict for tool results."""
        data = asdict(self)
        data["checks"] = [c.model_dump() for c in self.checks]
        return data


class Registry:
    """Approved generated models, stored as ``.py`` files and run only through the sandbox.

    Parameters
    ----------
    folder : str or Path, optional
        Where models are kept; defaults to ``$DIOSCURI_MODELS`` or
        ``hackathon/evals/runs/generated_models`` (git-ignored).
    """

    def __init__(self, folder: Optional[Path] = None):
        """Remember the folder; nothing is written until a model is saved."""
        self.folder = Path(folder) if folder else MODELS_DIR

    def save(
        self, result: GenerationResult, approved_by: str, spec: Optional[ComponentSpec] = None
    ) -> Path:
        """Store a passing, approved model and return the path of its ``.py`` file.

        Parameters
        ----------
        result : GenerationResult
            A result with ``passed`` True.
        approved_by : str
            Who approved it, normally ``"user"`` after the agent's approval interrupt.
        spec : ComponentSpec, optional
            Defaults to ``SPECS[result.component]``.

        Returns
        -------
        Path
            The ``.py`` file; a ``.json`` file with the same stem holds the metadata.

        Raises
        ------
        ValueError
            If the result did not pass or nobody approved it.
        """
        if not approved_by:
            raise ValueError("a model is registered only after someone approves it")
        spec = spec or SPECS[result.component]
        # Re-test rather than trust the flag: the result may come back from a saved session.
        if not result.passed or not check_model(spec, result.code).passed:
            raise ValueError("only code that passed every test can be registered")
        self.folder.mkdir(parents=True, exist_ok=True)
        ignore = self.folder / ".gitignore"
        if not ignore.exists():
            ignore.write_text("# Generated models stay on this machine.\n*\n!.gitignore\n")
        date = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        meta = {
            "name": spec.name,
            "title": spec.title,
            "component": result.component,
            "func_name": spec.func_name,
            "inputs": [asdict(q) for q in spec.inputs],
            "outputs": [asdict(q) for q in spec.outputs],
            "model": result.model,
            "prompt_version": result.prompt_version,
            "attempts": len(result.attempts),
            "tokens": result.tokens,
            "date": date,
            "approved_by": approved_by,
            "checks": [c.model_dump() for c in result.checks],
            "table": result.table,
            "sources": spec.sources,
            "sha256": hashlib.sha256(result.code.encode("utf-8")).hexdigest(),
        }
        header = [
            f"# Generated model: {spec.name} ({spec.title})",
            f"# Written by {result.model} (prompt {result.prompt_version}) in "
            f"{len(result.attempts)} attempt(s); approved by {approved_by} on {date}.",
            "# Run it only through gemini_agent.sandbox (Registry.evaluate).",
            "# Inputs: " + ", ".join(f"{q.name} [{q.unit}]" for q in spec.inputs),
            "# Outputs: " + ", ".join(f"{q.name} [{q.unit}]" for q in spec.outputs),
            "# Tests:",
        ]
        header += [f"#   {line}" for line in result.table_markdown().splitlines() if line]
        header.append("# Sources: " + " | ".join(spec.sources))
        path = self.folder / f"{spec.name}.py"
        path.write_text("\n".join(header) + f"\n{CODE_MARKER}\n" + result.code, encoding="utf-8")
        path.with_suffix(".json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        return path

    def names(self) -> List[str]:
        """Return the names of the registered models."""
        if not self.folder.is_dir():
            return []
        return sorted(p.stem for p in self.folder.glob("*.json") if p.with_suffix(".py").exists())

    def load(self, name: str) -> RegisteredModel:
        """Return a registered model after checking its code is the code that was approved.

        Parameters
        ----------
        name : str
            Registered name.

        Returns
        -------
        RegisteredModel
            Code and metadata.

        Raises
        ------
        KeyError
            If no such model is registered.
        ValueError
            If the code changed since it was approved.
        """
        path = self.folder / f"{name}.py"
        if not path.exists() or not path.with_suffix(".json").exists():
            raise KeyError(f"no generated model named {name}; registered: {self.names()}")
        meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        text = path.read_text(encoding="utf-8")
        code = text.split(f"\n{CODE_MARKER}\n", 1)[-1]
        if hashlib.sha256(code.encode("utf-8")).hexdigest() != meta["sha256"]:
            raise ValueError(f"{path.name} changed after it was approved; generate it again")
        return RegisteredModel(name=name, code=code, meta=meta, path=path)

    def evaluate(self, name: str, cases: List[dict], timeout_s: float = 5.0) -> List[dict]:
        """Run a registered model at some operating points and return its outputs.

        Parameters
        ----------
        name : str
            Registered name.
        cases : list of dict
            Inputs per case; missing inputs take the spec's defaults.
        timeout_s : float
            Sandbox limit for the batch.

        Returns
        -------
        list of dict
            Outputs per case.
        """
        return self.evaluate_checked(name, cases, timeout_s).outputs

    def evaluate_checked(self, name: str, cases: List[dict], timeout_s: float = 5.0) -> Evaluation:
        """Run a registered model and check every output with the spec's per-case rules.

        Parameters
        ----------
        name : str
            Registered name.
        cases : list of dict
            Inputs per case; missing inputs take the spec's defaults.
        timeout_s : float
            Sandbox limit for the batch.

        Returns
        -------
        Evaluation
            Inputs used, which were assumed, outputs, checks and range warnings.

        Raises
        ------
        ValueError
            If a case names an input the model does not have.
        ModelRunError
            If the sandbox run fails.
        """
        model = self.load(name)
        inputs = {q["name"]: q for q in model.meta["inputs"]}
        full, assumed, warnings = [], [], []
        for case in cases:
            unknown = [k for k in case if k not in inputs]
            if unknown:
                raise ValueError(
                    f"{name} has no input {', '.join(unknown)}; its inputs are "
                    f"{', '.join(inputs)}"
                )
            filled = {k: float(case.get(k, q["default"])) for k, q in inputs.items()}
            assumed.append([k for k in inputs if k not in case])
            for k, q in inputs.items():
                lo, hi = q.get("low"), q.get("high")
                if lo is not None and hi is not None and not lo <= filled[k] <= hi:
                    warnings.append(
                        f"{k}={fmt(filled[k])} {q['unit']} is outside the tested range "
                        f"{fmt(lo)} to {fmt(hi)}"
                    )
            full.append(filled)
        run = sandbox.run(model.code, model.func_name, full, timeout_s, model.arguments)
        if not run.ok:
            first = next((e for e in run.errors if e), "")
            raise ModelRunError(
                "; ".join(x for x in [run.error, first, *run.violations] if x) or "failed"
            )
        spec = SPECS.get(model.meta["component"])
        checks = run_checks(spec, full, run.outputs, sweeps=False) if spec else []
        return Evaluation(
            name=name,
            cases=full,
            assumed=assumed,
            outputs=run.outputs,
            checks=checks,
            warnings=list(dict.fromkeys(warnings)),
            seconds=run.seconds,
        )
