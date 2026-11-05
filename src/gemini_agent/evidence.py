"""What a turn costs to run: GPU energy measured while it runs, and the models' GPU memory.

The organisers ask for evidence of what the agent uses (tokens, time, energy). Tokens and time
come from each model call (``llm.LLMCall``); energy is measured here: ``nvidia-smi`` reports
each GPU's power draw every 250 ms while a turn runs, and the samples are added up (W × s →
Wh). It is the whole GPU's draw, idle power and other programs included, so it is an upper
bound for the turn. CPU energy is not measured (Linux reads it only as root); on a machine
without an NVIDIA GPU, or on the CPU switch, nothing is measured and nothing is claimed.

``model_memory_mb`` gives the GPU memory the local models hold (Ollama's runners and this
process): the number the 16 GB laptop profile is checked against.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from typing import Dict, List, Optional


class PowerMeter:
    """Sample the GPUs' power draw from ``start`` to ``stop``; ``stop`` returns the energy.

    Parameters
    ----------
    interval_ms : int
        Time between samples.
    """

    def __init__(self, interval_ms: int = 250):
        """Prepare the meter; nothing runs until ``start``."""
        self.interval_ms = interval_ms
        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._last: Dict[str, float] = {}  # GPU index -> time of its last sample
        self._joules = 0.0
        self._peak_mb = 0.0
        self._samples = 0
        self._started = 0.0

    @staticmethod
    def available() -> bool:
        """Return True when an NVIDIA GPU can be read (and ``DIOSCURI_GPU`` does not hide it)."""
        return os.environ.get("DIOSCURI_GPU") != "0" and shutil.which("nvidia-smi") is not None

    def start(self) -> "PowerMeter":
        """Start sampling (does nothing when no GPU can be read)."""
        if not self.available():
            return self
        try:
            self._proc = subprocess.Popen(
                [
                    "nvidia-smi",
                    "--query-gpu=index,power.draw,memory.used",
                    "--format=csv,noheader,nounits",
                    f"-lms={self.interval_ms}",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except OSError:
            self._proc = None
            return self
        self._started = time.perf_counter()
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()
        return self

    def _read(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        for line in self._proc.stdout:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) != 3:
                continue
            try:
                gpu, watts, mb = parts[0], float(parts[1]), float(parts[2])
            except ValueError:
                continue
            now = time.perf_counter()
            # Each sample stands for the time since that GPU's last one (the first: one step).
            dt = now - self._last.get(gpu, now - self.interval_ms / 1000)
            self._last[gpu] = now
            self._joules += watts * dt
            self._peak_mb = max(self._peak_mb, mb)
            self._samples += 1

    def stop(self) -> Optional[dict]:
        """Stop sampling; return ``{"gpu_wh", "seconds", "samples", "source"}`` or None."""
        if self._proc is None:
            return None
        self._proc.terminate()
        try:
            self._proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._proc = None
        if not self._samples:
            return None
        return {
            "gpu_wh": round(self._joules / 3600, 3),
            "seconds": round(time.perf_counter() - self._started, 2),
            "samples": self._samples,
            "source": "nvidia-smi power.draw, whole GPU (an upper bound)",
        }


def model_memory_mb() -> Optional[float]:
    """Return the GPU memory (MB) Ollama's model runners and this process hold, or None."""
    if not PowerMeter.available():
        return None
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-compute-apps=pid,process_name,used_memory",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    total, mine = 0.0, str(os.getpid())
    rows: List[List[str]] = [[p.strip() for p in ln.split(",")] for ln in out.splitlines()]
    for row in rows:
        if len(row) == 3 and ("ollama" in row[1].lower() or row[0] == mine):
            try:
                total += float(row[2])
            except ValueError:
                continue
    return total
