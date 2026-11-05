"""Sandbox: check and run model code written by a language model, safely enough for a laptop.

Generated code is never imported into the agent. It goes through two gates:

1. ``check_code`` reads its syntax tree and allows only plain numeric Python: ``math`` and
   ``numpy`` imports, functions, constants, loops and arithmetic. It refuses file, process and
   network access, ``eval``/``exec``/``open``/``getattr`` and friends, classes, ``global``,
   ``with`` blocks, names and attributes that start with an underscore (the usual way out of a
   Python sandbox) and the frame and file attributes of generators, tracebacks and numpy.
2. ``run`` evaluates the function on a batch of cases in **one** child process
   (``python -I``, JSON over stdin and stdout, an empty working folder and a small
   environment). The child gives the code a reduced set of builtins whose ``__import__`` only
   returns ``math`` and ``numpy``. On Linux and macOS it also sets ``resource`` limits before
   running the code: CPU seconds, address space, no file writes, no new file descriptors and
   no new processes. Windows has no ``resource`` module, so there only the wall-clock timeout
   applies.

This is a demo sandbox, not a security boundary against a determined attacker; it stops the
mistakes and shortcuts a small model makes (reading files, importing ``os``, endless loops,
memory blow-ups) and makes every refusal a plain sentence the model can act on.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Sequence

try:  # POSIX only; Windows falls back to the timeout alone
    import resource  # noqa: F401

    HAVE_RESOURCE = True
except ImportError:  # pragma: no cover - Windows
    HAVE_RESOURCE = False

ALLOWED_MODULES = ("math", "numpy")
MAX_CODE_CHARS = 20000
MEMORY_MB = 1024

# Builtins the code may not call or name (the child does not provide them either).
FORBIDDEN_NAMES = {
    "exec",
    "eval",
    "compile",
    "open",
    "__import__",
    "getattr",
    "setattr",
    "delattr",
    "hasattr",
    "globals",
    "locals",
    "vars",
    "dir",
    "input",
    "breakpoint",
    "help",
    "exit",
    "quit",
    "memoryview",
    "type",
    "object",
    "super",
    "classmethod",
    "staticmethod",
    "property",
    "format",
    "id",
}

# Attributes that read or write files, reach other modules or format strings by attribute.
FORBIDDEN_ATTRIBUTES = {
    "format",
    "format_map",
    "load",
    "loads",
    "save",
    "savez",
    "savez_compressed",
    "savetxt",
    "loadtxt",
    "genfromtxt",
    "fromfile",
    "tofile",
    "fromregex",
    "memmap",
    "dump",
    "dumps",
    "open",
    "ctypes",
    "ctypeslib",
    "lib",
    "testing",
    "f2py",
    "distutils",
    "DataSource",
    "show_config",
    "show_runtime",
    "os",
    "sys",
    "system",
    "popen",
    "mro",
}

# Frame, code and traceback attributes (``gen.gi_frame.f_back`` walks out of any sandbox).
FORBIDDEN_PREFIXES = ("_", "f_", "gi_", "cr_", "ag_", "tb_", "co_")

FORBIDDEN_NODES = {
    ast.ClassDef: "classes are not needed",
    ast.AsyncFunctionDef: "async functions are not allowed",
    ast.Await: "await is not allowed",
    ast.AsyncFor: "async loops are not allowed",
    ast.AsyncWith: "async with is not allowed",
    ast.With: "with blocks are not allowed (they are for files and locks)",
    ast.Global: "global is not allowed; pass values as arguments",
    ast.Nonlocal: "nonlocal is not allowed",
    ast.Yield: "generators (yield) are not allowed; return a dict",
    ast.YieldFrom: "generators (yield from) are not allowed; return a dict",
}

TOP_LEVEL = (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign, ast.AnnAssign)
STATEMENT_NAMES = {
    ast.Expr: "a call or expression",
    ast.For: "a for loop",
    ast.While: "a while loop",
    ast.If: "an if block",
    ast.Try: "a try block",
}

# Builtins the generated code gets inside the child process.
SAFE_BUILTINS = [
    "abs",
    "all",
    "any",
    "bool",
    "dict",
    "divmod",
    "enumerate",
    "filter",
    "float",
    "int",
    "isinstance",
    "len",
    "list",
    "map",
    "max",
    "min",
    "pow",
    "print",
    "range",
    "reversed",
    "round",
    "set",
    "sorted",
    "str",
    "sum",
    "tuple",
    "zip",
    "ArithmeticError",
    "Exception",
    "IndexError",
    "KeyError",
    "OverflowError",
    "RuntimeError",
    "TypeError",
    "ValueError",
    "ZeroDivisionError",
]

# The child process. It imports nothing from the repository and keeps the real stdout for
# its single JSON reply; the code's own prints go to a buffer that is thrown away.
CHILD = r"""
import builtins, io, json, math, numbers, sys, traceback

req = json.loads(sys.stdin.read())
reply_to = sys.stdout
modules = {"math": math}
if req["numpy"]:
    import numpy
    modules["numpy"] = numpy
applied = []
if req["limits"]:
    try:
        import resource
    except ImportError:
        resource = None
    if resource is not None:
        def limit(name, value, label):
            kind = getattr(resource, name, None)
            if kind is None:
                return
            try:
                resource.setrlimit(kind, (value, value))
                applied.append(label)
            except (ValueError, OSError):
                pass
        limit("RLIMIT_CPU", req["cpu_s"], "CPU %d s" % req["cpu_s"])
        limit("RLIMIT_AS", req["memory_mb"] * 1048576, "memory %d MB" % req["memory_mb"])
        limit("RLIMIT_FSIZE", 0, "no file writes")
        limit("RLIMIT_NOFILE", 3, "no new files or sockets")
        limit("RLIMIT_NPROC", 0, "no new processes")

def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level == 0 and name in modules:
        return modules[name]
    raise ImportError("import of %s is not allowed" % name)

safe = {n: getattr(builtins, n) for n in req["builtins"]}
safe["__import__"] = guarded_import
space = {"__builtins__": safe, "__name__": "generated"}

def where(err):
    lines = [f.lineno for f in traceback.extract_tb(err.__traceback__)
             if f.filename == "<generated>"]
    text = "%s: %s" % (type(err).__name__, err)
    text = text[:300]
    return ("line %d: %s" % (lines[-1], text)) if lines else text

reply = {"limits": applied, "outputs": [], "errors": [], "error": ""}
sys.stdout = io.StringIO()
try:
    exec(compile(req["code"], "<generated>", "exec"), space)
    func = space[req["func_name"]]
except BaseException as err:
    reply["error"] = "loading the code failed: " + where(err)
else:
    for case in req["cases"]:
        try:
            value = func(**case)
            if not isinstance(value, dict):
                raise TypeError("the function returned %s, not a dict" % type(value).__name__)
            if len(value) > 100:
                raise ValueError("the function returned more than 100 outputs")
            out = {}
            for key, number in value.items():
                if not isinstance(key, str):
                    raise TypeError("output names must be strings")
                if isinstance(number, bool) or not isinstance(number, numbers.Real):
                    raise TypeError("output %r is %s, not a number"
                                    % (key, type(number).__name__))
                out[key] = float(number)
            reply["outputs"].append(out)
            reply["errors"].append("")
        except BaseException as err:
            reply["outputs"].append(None)
            reply["errors"].append(where(err))
sys.stdout = reply_to
reply_to.write(json.dumps(reply))
reply_to.flush()
"""


@dataclass
class SandboxResult:
    """What happened when generated code ran on a batch of cases.

    Attributes
    ----------
    ok : bool
        True when the code passed ``check_code``, loaded, and returned a dict of numbers for
        every case.
    outputs : list of dict or None
        One output dict per case, ``None`` where that case raised.
    errors : list of str
        One error text per case, empty where the case ran.
    error : str
        What stopped the whole run (rule violations, a load error, a timeout, a crash).
    seconds : float
        Wall time of the check and the child process.
    violations : list of str
        Rule violations found by ``check_code``; the code was not run if any.
    timed_out : bool
        True when the child was stopped by the timeout.
    limits : list of str
        Limits that were in force, for example ``["timeout 5 s", "CPU 6 s", ...]``.
    """

    ok: bool
    outputs: List[Optional[dict]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    error: str = ""
    seconds: float = 0.0
    violations: List[str] = field(default_factory=list)
    timed_out: bool = False
    limits: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        """Return the result as a plain dict for traces and events."""
        return asdict(self)


def _where(node: ast.AST) -> str:
    return f"line {getattr(node, 'lineno', '?')}: "


def _module_root(name: str) -> str:
    return name.split(".")[0]


def _check_import(node: ast.AST) -> List[str]:
    out = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name not in ALLOWED_MODULES:
                hint = (
                    f" (import {_module_root(alias.name)} and use {alias.name})"
                    if _module_root(alias.name) in ALLOWED_MODULES
                    else ""
                )
                out.append(
                    f"{_where(node)}import of {alias.name} is not allowed; only "
                    f"{' and '.join(ALLOWED_MODULES)} may be imported{hint}."
                )
    elif isinstance(node, ast.ImportFrom):
        if node.level or node.module not in ALLOWED_MODULES:
            out.append(
                f"{_where(node)}import from {node.module or '.'} is not allowed; only "
                f"{' and '.join(ALLOWED_MODULES)} may be imported."
            )
        for alias in node.names:
            if alias.name == "*":
                out.append(f"{_where(node)}'from ... import *' is not allowed; name what you use.")
            elif _bad_attribute(alias.name):
                out.append(f"{_where(node)}importing {alias.name} is not allowed.")
    return out


def _bad_attribute(name: str) -> bool:
    return name in FORBIDDEN_ATTRIBUTES or name.startswith(FORBIDDEN_PREFIXES)


def _check_signature(func: ast.FunctionDef, arguments: Sequence[str]) -> List[str]:
    args = func.args
    out = []
    if args.vararg or args.kwarg or args.posonlyargs:
        out.append(
            f"{_where(func)}{func.name} must take named arguments only (no *args, **kwargs or /)."
        )
    names = [a.arg for a in args.args + args.kwonlyargs]
    if sorted(names) != sorted(arguments):
        out.append(
            f"{_where(func)}{func.name} must take exactly these arguments: "
            f"{', '.join(arguments)} (it takes {', '.join(names) or 'none'})."
        )
    return out


def check_code(code: str, func_name: str, arguments: Optional[Sequence[str]] = None) -> List[str]:
    """Return every way the code breaks the sandbox rules, as plain sentences.

    Allowed: ``import math`` and ``import numpy`` (also ``as`` and ``from ... import``), one
    top-level function named ``func_name`` plus helper functions, constant assignments,
    a module docstring, loops, conditions, comprehensions, lambdas and ``try``. Forbidden:
    any other import, the builtins in ``FORBIDDEN_NAMES`` (``open``, ``eval``, ``exec``,
    ``getattr``, ``globals``, ...), names and attributes starting with an underscore, the
    file and module attributes in ``FORBIDDEN_ATTRIBUTES`` (``np.load``, ``arr.tofile``,
    ``str.format``, ...), frame attributes (``gi_frame``, ``f_back``, ...), classes,
    ``global``/``nonlocal``, ``with`` blocks, generators, async code and top-level statements
    other than imports, functions and constants.

    Parameters
    ----------
    code : str
        Python source of the generated model.
    func_name : str
        The function the caller will run.
    arguments : sequence of str, optional
        If given, the function must take exactly these named arguments.

    Returns
    -------
    list of str
        One sentence per violation; empty when the code may run.
    """
    if len(code) > MAX_CODE_CHARS:
        return [f"The code is {len(code)} characters; keep it under {MAX_CODE_CHARS}."]
    try:
        tree = ast.parse(code)
    except SyntaxError as err:
        return [f"The code does not parse: {err.msg} (line {err.lineno})."]
    out: List[str] = []
    for i, stmt in enumerate(tree.body):
        docstring = i == 0 and isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)
        if not docstring and not isinstance(stmt, TOP_LEVEL):
            found = STATEMENT_NAMES.get(type(stmt), type(stmt).__name__.lower())
            out.append(
                f"{_where(stmt)}only imports, constants and functions may sit at the top level "
                f"(found {found}); put the work inside {func_name}."
            )
    defs = [s for s in tree.body if isinstance(s, ast.FunctionDef) and s.name == func_name]
    if not defs:
        out.append(f"There is no top-level function named {func_name}.")
    elif len(defs) > 1:
        out.append(f"{func_name} is defined {len(defs)} times; define it once.")
    elif arguments is not None:
        out.extend(_check_signature(defs[0], arguments))
    for node in ast.walk(tree):
        for kind, why in FORBIDDEN_NODES.items():
            if isinstance(node, kind):
                out.append(f"{_where(node)}{why}.")
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            out.extend(_check_import(node))
        elif isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES or node.id.startswith("__"):
                out.append(f"{_where(node)}{node.id} is not allowed.")
        elif isinstance(node, ast.Attribute):
            if _bad_attribute(node.attr):
                out.append(f"{_where(node)}the attribute .{node.attr} is not allowed.")
        elif isinstance(node, (ast.FunctionDef, ast.Lambda)):
            if isinstance(node, ast.FunctionDef) and node.decorator_list:
                out.append(f"{_where(node)}decorators are not allowed.")
            if isinstance(node, ast.FunctionDef) and node.name.startswith("_"):
                out.append(f"{_where(node)}function names may not start with an underscore.")
            for a in node.args.args + node.args.kwonlyargs + node.args.posonlyargs:
                if a.arg.startswith("__"):
                    out.append(f"{_where(node)}argument {a.arg} is not allowed.")
    # Report each sentence once, in line order (sentences without a line come first).
    return sorted(dict.fromkeys(out), key=_line_of)


def _line_of(sentence: str) -> int:
    head = sentence.split(":", 1)[0]
    return int(head[5:]) if head.startswith("line ") and head[5:].isdigit() else 0


def uses_numpy(code: str) -> bool:
    """Return True when the code imports numpy, so the child loads it (about 0.1 s)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name == "numpy" for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.module == "numpy":
            return True
    return False


def _child_env() -> Dict[str, str]:
    """Return a small environment: one BLAS thread, and what Windows needs to start Python."""
    env = {
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONIOENCODING": "utf-8",
    }
    for key in ("PATH", "SYSTEMROOT", "SystemRoot", "TEMP", "TMP"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def run(
    code: str,
    func_name: str,
    cases: List[dict],
    timeout_s: float = 5.0,
    arguments: Optional[Sequence[str]] = None,
    memory_mb: int = MEMORY_MB,
) -> SandboxResult:
    """Check the code, then evaluate ``func_name(**case)`` for every case in one child process.

    Parameters
    ----------
    code : str
        Python source of the generated model.
    func_name : str
        The function to call.
    cases : list of dict
        Keyword arguments for each call (JSON-serialisable numbers).
    timeout_s : float
        Wall-clock limit for the whole batch, including Python start-up (about 0.05 s, plus
        0.1 s when the code imports numpy).
    arguments : sequence of str, optional
        If given, the function must take exactly these named arguments.
    memory_mb : int
        Address-space limit of the child where ``resource`` exists.

    Returns
    -------
    SandboxResult
        Outputs and errors per case, or why nothing ran.
    """
    start = time.perf_counter()
    limits = [f"timeout {timeout_s:g} s"]
    violations = check_code(code, func_name, arguments)
    if violations:
        return SandboxResult(
            ok=False,
            error="the code breaks the sandbox rules, so it was not run",
            violations=violations,
            seconds=round(time.perf_counter() - start, 3),
            limits=limits,
        )
    request = json.dumps(
        {
            "code": code,
            "func_name": func_name,
            "cases": cases,
            "numpy": uses_numpy(code),
            "limits": HAVE_RESOURCE,
            "cpu_s": int(timeout_s) + 1,
            "memory_mb": int(memory_mb),
            "builtins": SAFE_BUILTINS,
        }
    )
    with tempfile.TemporaryDirectory(prefix="dioscuri-sandbox-") as folder:
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-c", CHILD],
                input=request,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout_s,
                cwd=folder,
                env=_child_env(),
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                ok=False,
                error=f"stopped after {timeout_s:g} s: an endless loop or very slow code",
                seconds=round(time.perf_counter() - start, 3),
                timed_out=True,
                limits=limits,
            )
    seconds = round(time.perf_counter() - start, 3)
    try:
        reply = json.loads(proc.stdout)
    except json.JSONDecodeError:
        tail = proc.stderr.strip().splitlines()[-1:] or [""]
        return SandboxResult(
            ok=False,
            error=(
                f"the child process stopped without a reply (exit code {proc.returncode}; "
                f"a CPU or memory limit, or a crash) {tail[0][:200]}"
            ).strip(),
            seconds=seconds,
            limits=limits,
        )
    errors = reply["errors"]
    ok = not reply["error"] and len(errors) == len(cases) and not any(errors)
    return SandboxResult(
        ok=ok,
        outputs=reply["outputs"],
        errors=errors,
        error=reply["error"],
        seconds=seconds,
        limits=limits + reply["limits"],
    )
