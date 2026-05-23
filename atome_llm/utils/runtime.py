"""atome_llm.utils.runtime — operational helpers for long CPU training.

ThermalGuard reads /sys/class/thermal CPU sensors when available and
exposes a `should_pause()` heuristic so a long training loop can yield
the CPU before crossing a configured temperature. polite_training is a
context manager that wraps an optimizer step with a short backoff sleep
when the guard says so. Both are best-effort; if the sysfs files do not
exist (containers, macOS, embedded hosts), they degrade to no-ops.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path


class ThermalGuard:
    def __init__(self, max_temp_c: float = 80.0) -> None:
        self.max_temp_c = max_temp_c
        self._zones = sorted(Path("/sys/class/thermal").glob("thermal_zone*/temp")) \
            if Path("/sys/class/thermal").exists() else []

    def current_temp_c(self) -> float | None:
        """Highest CPU-zone reading in Celsius. None if no readings available."""
        readings: list[float] = []
        for z in self._zones:
            try:
                readings.append(int(z.read_text().strip()) / 1000.0)
            except Exception:
                continue
        return max(readings) if readings else None

    def should_pause(self) -> bool:
        t = self.current_temp_c()
        return t is not None and t >= self.max_temp_c


@contextmanager
def polite_training(guard: ThermalGuard, backoff_s: float = 1.0):
    """Pause briefly if the thermal guard is over its limit, then yield."""
    while guard.should_pause():
        time.sleep(backoff_s)
    yield
