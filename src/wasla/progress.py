"""Percent and time-left from a stream of "done so far" numbers."""
from __future__ import annotations

import time


class Rate:
    """Smooths the speed with an exponential moving average so the time left does not jump around."""

    def __init__(self, total: float, smoothing: float = 0.25, warmup_s: float = 2.0):
        self.total = max(float(total), 0.0)
        self.smoothing = smoothing
        self.warmup_s = warmup_s
        self._start: float | None = None
        self._last: tuple[float, float] | None = None
        self._speed: float | None = None
        self._samples = 0

    def update(self, done: float, now: float | None = None) -> tuple[float, float | None]:
        now = time.monotonic() if now is None else now
        done = min(max(float(done), 0.0), self.total) if self.total else float(done)
        pct = 100.0 * done / self.total if self.total else 0.0
        if self._start is None:
            self._start = now
        if self._last is not None:
            elapsed = now - self._last[1]
            if elapsed > 0:
                speed = (done - self._last[0]) / elapsed
                self._speed = speed if self._speed is None else \
                    self.smoothing * speed + (1 - self.smoothing) * self._speed
                self._samples += 1
        self._last = (done, now)
        if self._samples < 3 or now - self._start < self.warmup_s or not self._speed or self._speed <= 0:
            return pct, None
        return pct, max(self.total - done, 0.0) / self._speed
