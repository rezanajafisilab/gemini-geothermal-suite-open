"""Model router: which local model does which job, and on which device.

Each run picks a device: ``"auto"`` uses the GPU when one is found, ``"cpu"`` keeps every
model off it (the header's GPU/CPU switch); and a model size: ``"auto"``, ``"9b"`` or ``"4b"``
(the header's model switch, 5 Nov). **Two models**: ``DIOSCURI_REASONING_MODEL``
(``qwen3.5:9b``) and ``DIOSCURI_REASONING_MODEL_CPU`` (``qwen3.5:4b``). With the size on auto
the first that fits makes every call: the 9B on the GPU, else the 4B on the GPU, else (no GPU,
or one too small for the 4B, or the CPU picked) the 9B on the CPU when the free memory holds
it, else the 4B on the CPU. A size picked is used on the device picked, whether it fits or not
(Ollama then keeps on the GPU what fits):

- **Reader**: reads every message into a form (intake). Until 4 Nov this was a third model,
  ``qwen3:1.7b``; ``DIOSCURI_MODEL`` still sets a separate reader (for benchmarks).
- **Answerer**: writes every reply from the context pack (``answer.py``), about 2-3 s an answer
  for the 9B on a GPU. ``DIOSCURI_CPU_ANSWERER=reader`` makes a separate reader write the CPU
  replies (as the 1.7B did until 31 Oct; it got source and physics questions wrong).
- **Planner and reflector** (reasoning mode only): the same model chooses the designs to study
  and the fixes to try, writing up to three short reasoning steps first.
- **Model builder**: writes code for a missing component; ``DIOSCURI_MODELGEN_MODEL`` sets
  another model.

One client a model and device, with one context window: a call with another window would make
Ollama load the model again.

The models' own "thinking" mode is used only for the answer of a hard turn on a GPU, and only
when ``DIOSCURI_THINK`` is set (4 Nov; off by default since 5 Nov), in a call of its own cut at
``answer.THINK_TOKENS``. On 28 Oct,
Qwen3.5-9B thought for over 4,000 tokens (45 s on an RTX A6000) without reaching an answer, and
on 4 Nov it used all of 3,448 tokens thinking when the format and the thinking shared one call;
three capped steps in the JSON reply took 2 s on the GPU and 8 s for the 4B model on 8 CPU
threads. The readers and the CPU never think.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from gemini_agent.llm import DEFAULT_MODEL, OllamaLLM

REASONING_GPU_MODEL = os.environ.get("DIOSCURI_REASONING_MODEL", "qwen3.5:9b")
REASONING_CPU_MODEL = os.environ.get("DIOSCURI_REASONING_MODEL_CPU", "qwen3.5:4b")
# A separate reader only when asked for; else the device's model reads too (two models only).
READER_MODEL = os.environ.get("DIOSCURI_MODEL", "")
# Writing component code: another model only when asked for (qwen3.5:4b passed both specs every
# time; the 9B is the GPU's model).
GENERATOR_MODEL = os.environ.get("DIOSCURI_MODELGEN_MODEL", "")
# The device's model writes the replies; "reader" makes a separate reader do it on the CPU.
CPU_ANSWERER = os.environ.get("DIOSCURI_CPU_ANSWERER", "reasoning")
# GPU memory each model needs, measured with Ollama 0.40 on 3 Nov: qwen3.5:9b takes 5.6 GB with
# an 8k context (6.1 GB with 16k), qwen3.5:4b 3.4 GB; the rest is room for the display. Until
# 4 Nov a 1.7 GB reader sat beside it (8.5 and 5.5 GB then): without it a 12 GB laptop GPU (RTX
# 4080 Laptop, about 8 GB free) runs the 9B.
GPU_9B_MB = 7000
GPU_4B_MB = 4500
MIN_FREE_MB = GPU_9B_MB
# The reasoning model's window. Qwen3.5-9B keeps a cache only in its 8 full-attention layers
# (of 32; the rest are linear attention with a fixed state): 8 x 4 KV heads x 256 x 2 x 2 bytes
# = 32 KiB a token, so 16,384 tokens take 0.5 GB, 0.25 GB more than 8,192, which GPU_9B_MB's
# spare room covers. The answer's context is still budgeted to about 7,000 tokens
# (``answer.budget``): the larger window is room, not a larger prompt. The 4B keeps 8,192 on
# either device, so a small GPU keeps it and its prompts stay short on the CPU (prompt time is
# most of a CPU turn). Changing a window reloads the model (ADR-0002); it is fixed per model.
REASONING_CTX = int(os.environ.get("DIOSCURI_REASONING_CTX", "16384"))
REASONING_CTX_CPU = int(os.environ.get("DIOSCURI_REASONING_CTX_CPU", "8192"))
# Memory the 9B needs on the CPU: about 6.1 GB of weights and an 8k window, and 2 GB left for
# the system and the app; below it the 4B runs on the CPU (5 Nov).
CPU_9B_MB = 8000
# The model size a run uses when it does not pick one (the header's switch): "auto" picks by fit.
SIZES = ("auto", "9b", "4b")
DEFAULT_SIZE = os.environ.get("DIOSCURI_SIZE", "auto")


@dataclass
class Hardware:
    """The GPU the reasoning model may use; an empty name means none was found."""

    gpu: str = ""
    free_mb: int = 0
    # Memory Ollama's own loaded models hold on that GPU: Ollama frees it to load ours.
    ollama_mb: int = 0
    total_mb: int = 0
    # The computer's memory a model on the CPU may have (available, plus what Ollama holds in
    # it); 0 when not known, which keeps the CPU on the 4B.
    ram_mb: int = 0

    @property
    def usable_mb(self) -> int:
        """Return the memory our models can have: what is free plus what Ollama would free."""
        usable = self.free_mb + self.ollama_mb
        return min(usable, self.total_mb) if self.total_mb else usable


def available_ram_mb() -> int:
    """Return the memory available to a new program, in MB (0 when it cannot be read).

    ``DIOSCURI_RAM_MB`` sets it. Linux reads ``MemAvailable``; Windows asks the system; macOS
    counts half the memory (it does not say what is free in one number).
    """
    given = os.environ.get("DIOSCURI_RAM_MB")
    if given:
        try:
            return int(given)
        except ValueError:
            pass
    try:
        if sys.platform.startswith("linux"):
            with open("/proc/meminfo", encoding="ascii") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        return int(line.split()[1]) // 1024
        elif sys.platform == "win32":
            import ctypes

            class Status(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            s = Status()
            s.dwLength = ctypes.sizeof(Status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s)):
                return int(s.ullAvailPhys // 2**20)
        elif sys.platform == "darwin":
            return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") // 2**20 // 2)
    except (OSError, ValueError, AttributeError):
        pass
    return 0


def ollama_ram_mb(host: Optional[str] = None) -> int:
    """Return the computer memory (MB) Ollama's loaded models hold outside the GPU (0 unknown)."""
    import httpx

    from gemini_agent.llm import DEFAULT_HOST

    url = host or DEFAULT_HOST
    url = url if url.startswith("http") else f"http://{url}"
    try:
        r = httpx.get(f"{url}/api/ps", timeout=2.0)
        models = r.json().get("models", [])
        return int(sum(m.get("size", 0) - m.get("size_vram", 0) for m in models) / 2**20)
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        return 0


def detect_hardware() -> Hardware:
    """Return the GPU with the most free memory, if any (``DIOSCURI_GPU=0`` hides it).

    NVIDIA cards are found with ``nvidia-smi``; Apple silicon shares its memory with the GPU,
    so two thirds of the RAM count as free. Other GPUs are still used by Ollama, but are not
    detected here, so reasoning then picks the CPU model.

    Returns
    -------
    Hardware
        Name and free memory (MB) of the GPU, or an empty record.
    """
    if os.environ.get("DIOSCURI_GPU") == "0":
        return Hardware()
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.free,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout
        rows = [line.rsplit(",", 2) for line in out.strip().splitlines() if line.count(",") >= 2]
        name, free, total = max(rows, key=lambda r: int(r[1]))
        # With one GPU, what Ollama holds is on it; with several it is not counted.
        held = ollama_vram_mb() if len(rows) == 1 else 0
        return Hardware(name.strip(), int(free), held, int(total), _ram())
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    if sys.platform == "darwin" and platform.machine() == "arm64":
        ram_mb = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") // 2**20
        return Hardware("Apple GPU", int(ram_mb * 2 / 3), ram_mb=_ram())
    return Hardware(ram_mb=_ram())


def _ram() -> int:
    """Return the memory a model on the CPU may have: available, plus what Ollama holds."""
    ram = available_ram_mb()
    return ram + ollama_ram_mb() if ram else 0


def ollama_vram_mb(host: Optional[str] = None) -> int:
    """Return the GPU memory (MB) of the models Ollama has loaded now (0 when it cannot say)."""
    import httpx

    from gemini_agent.llm import DEFAULT_HOST

    url = host or DEFAULT_HOST
    url = url if url.startswith("http") else f"http://{url}"
    try:
        r = httpx.get(f"{url}/api/ps", timeout=2.0)
        return int(sum(m.get("size_vram", 0) for m in r.json().get("models", [])) / 2**20)
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        return 0


class Router:
    """Hands out the model clients for each role and device.

    Parameters
    ----------
    fast : OllamaLLM, optional
        A separate reader for the default device; by default ``DIOSCURI_MODEL`` when set, else
        the device's model reads.
    device : {"auto", "cpu"}
        The default device, used when a run does not choose one.
    host : str, optional
        Ollama server URL.
    hardware : Hardware, optional
        What was detected; found with ``detect_hardware`` when omitted.
    """

    def __init__(
        self,
        fast: Optional[OllamaLLM] = None,
        device: str = "auto",
        host: Optional[str] = None,
        hardware: Optional[Hardware] = None,
        size: str = DEFAULT_SIZE,
    ):
        """Detect the hardware; clients are created on first use and then reused."""
        self.device = device
        self.size = size if size in SIZES else "auto"
        self.hardware = detect_hardware() if hardware is None else hardware
        self._host = host
        self._clients: Dict[Tuple[str, str, int], OllamaLLM] = {}
        self._own_reader = fast is not None or bool(READER_MODEL)
        if fast is not None:
            self.fast = fast
        elif READER_MODEL:
            self.fast = self._client(READER_MODEL, device)
        else:
            self.fast = self.reasoning(device)

    @property
    def reasoning_on_gpu(self) -> bool:
        """Return True when the GPU reasoning model (9B) fits on the detected GPU."""
        return self.hardware.usable_mb >= GPU_9B_MB

    @property
    def small_on_gpu(self) -> bool:
        """Return True when at least the CPU reasoning model (4B) fits on the detected GPU."""
        return bool(self.hardware.gpu) and self.hardware.usable_mb >= GPU_4B_MB

    @property
    def big_on_cpu(self) -> bool:
        """Return True when the 9B fits in the computer's memory (for the CPU)."""
        return self.hardware.ram_mb >= CPU_9B_MB

    def runs_on_gpu(self, device: Optional[str] = None, size: Optional[str] = None) -> bool:
        """Return True when the models of this choice run on the GPU (else on the CPU)."""
        size = size or self.size
        if not self.on_gpu(device):
            return False
        return size != "auto" or self.reasoning_on_gpu or self.small_on_gpu

    def on_gpu(self, device: Optional[str] = None) -> bool:
        """Return True when ``device`` lets models use a detected GPU."""
        return (device or self.device) != "cpu" and bool(self.hardware.gpu)

    def _big(self, device: Optional[str], size: Optional[str] = None) -> bool:
        return self.reasoning(device, size).model == REASONING_GPU_MODEL

    def _client(self, model: str, device: str, num_ctx: int = 4096) -> OllamaLLM:
        key = (model, "cpu" if device == "cpu" else "auto", num_ctx)
        if key not in self._clients:
            self._clients[key] = OllamaLLM(
                model=model, host=self._host, device=key[1], num_ctx=num_ctx
            )
        return self._clients[key]

    def reader(self, device: Optional[str] = None, size: Optional[str] = None) -> OllamaLLM:
        """Return the model that reads every message: the device's model, unless one is set."""
        device = device or self.device
        if not self._own_reader:
            return self.reasoning(device, size)
        if device == self.device:
            return self.fast
        return self._client(READER_MODEL or self.fast.model or DEFAULT_MODEL, device)

    def reasoning(self, device: Optional[str] = None, size: Optional[str] = None) -> OllamaLLM:
        """Return the model of this choice: device and size.

        With the size on auto, the first that fits of the 9B on the GPU, the 4B on the GPU, the
        9B on the CPU and the 4B on the CPU.
        """
        size = size if size in SIZES else self.size
        if self.runs_on_gpu(device, size):
            if size == "9b" or (size == "auto" and self.reasoning_on_gpu):
                return self._client(REASONING_GPU_MODEL, "auto", REASONING_CTX)
            return self._client(REASONING_CPU_MODEL, "auto", REASONING_CTX_CPU)
        if size == "9b" or (size == "auto" and self.big_on_cpu):
            return self._client(REASONING_GPU_MODEL, "cpu", REASONING_CTX_CPU)
        return self._client(REASONING_CPU_MODEL, "cpu", REASONING_CTX_CPU)

    def why(self, device: Optional[str] = None, size: Optional[str] = None) -> str:
        """Return in a sentence why the reasoning model runs where it does."""
        hw = self.hardware
        size = size if size in SIZES else self.size
        model = self.reasoning(device, size).model
        if size != "auto":
            picked = f"{model} is picked in the header"
        else:
            picked = ""
        if (device or self.device) == "cpu":
            where = "CPU is picked in the header: every model runs on the CPU"
        elif not hw.gpu:
            where = "No GPU found: the models run on the CPU"
        else:
            have = f"{hw.usable_mb / 1000:.1f} GB of the GPU's memory can be used"
            if size != "auto":
                where = have
            elif self.reasoning_on_gpu:
                where = f"{have}; {REASONING_GPU_MODEL} needs about {GPU_9B_MB / 1000:.1f} GB"
            elif self.small_on_gpu:
                where = (
                    f"{have}; {REASONING_GPU_MODEL} needs about {GPU_9B_MB / 1000:.1f} GB, so "
                    f"{REASONING_CPU_MODEL} runs on the GPU instead"
                )
            else:
                where = (
                    f"{have}; {REASONING_CPU_MODEL} needs about {GPU_4B_MB / 1000:.1f} GB, so "
                    "the models run on the CPU"
                )
        if size == "auto" and not self.runs_on_gpu(device, size):
            ram = (
                f"{hw.ram_mb / 1000:.1f} GB of memory is free"
                if hw.ram_mb
                else "free memory unknown"
            )
            fits = "fits" if self.big_on_cpu else "does not fit"
            where += f"; {ram}, so {REASONING_GPU_MODEL} {fits} (about {CPU_9B_MB / 1000:.0f} GB)"
        return (f"{picked}; {where}" if picked else where) + "."

    def answerer(
        self, device: Optional[str] = None, reasoning: bool = False, size: Optional[str] = None
    ) -> OllamaLLM:
        """Return the model that writes the replies: the reasoning model, on either device."""
        if self._big(device, size) or reasoning or CPU_ANSWERER != "reader":
            return self.reasoning(device, size)
        return self.reader(device, size)

    def generator(self, device: Optional[str] = None, size: Optional[str] = None) -> OllamaLLM:
        """Return the model that writes code for missing components: the device's model."""
        if not GENERATOR_MODEL:
            return self.reasoning(device, size)
        return self._client(GENERATOR_MODEL, "auto" if self.on_gpu(device) else "cpu")

    def device_of(self, llm, device: Optional[str] = None) -> str:
        """Return ``"gpu"`` or ``"cpu"``: where a client of this router runs."""
        return (
            "cpu" if getattr(llm, "device", "auto") == "cpu" or not self.on_gpu(device) else "gpu"
        )

    def info(self, device: Optional[str] = None, size: Optional[str] = None) -> dict:
        """Return each role's model and device, for the health check and the header."""
        roles = {
            "fast": self.reader(device, size),
            "answer": self.answerer(device, size=size),
            "answer_reasoning": self.answerer(device, reasoning=True, size=size),
            "reasoning": self.reasoning(device, size),
            "generator": self.generator(device, size),
        }
        out = {k: {"model": c.model, "device": self.device_of(c, device)} for k, c in roles.items()}
        out["gpu"] = self.hardware.gpu
        out["why"] = self.why(device, size)
        return out

    def profiles(self) -> dict:
        """Return ``info`` for every choice of the header's switches.

        "auto" and "cpu" with the default size, and "auto:9b", "auto:4b", "cpu:9b", "cpu:4b".
        """
        out = {"auto": self.info("auto"), "cpu": self.info("cpu")}
        for device in ("auto", "cpu"):
            for size in ("9b", "4b"):
                out[f"{device}:{size}"] = self.info(device, size)
        return out
