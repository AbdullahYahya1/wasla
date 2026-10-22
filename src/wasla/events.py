"""Events the engine sends to the window, and a throttle so the UI is not flooded."""
from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Literal

Kind = Literal["progress", "log", "done", "error", "need", "clear"]


@dataclass
class Event:
    step: str
    kind: Kind
    pct: float | None = None
    eta_s: float | None = None
    phase: str | None = None
    data: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


class Emitter:
    """Passes events to `sink`, dropping progress updates that come faster than `min_interval`."""

    def __init__(self, sink: Callable[[Event], None], min_interval: float = 0.12,
                 clock: Callable[[], float] = time.monotonic):
        self.sink = sink
        self.min_interval = min_interval
        self.clock = clock
        self._last: dict[tuple[str, str | None], float] = {}
        self._lock = threading.Lock()

    def emit(self, event: Event) -> None:
        if event.kind == "progress" and (event.pct is None or event.pct < 100):
            key = (event.step, event.phase)
            now = self.clock()
            with self._lock:
                if now - self._last.get(key, -1e9) < self.min_interval:
                    return
                self._last[key] = now
        self.sink(event)

    def __call__(self, event: Event) -> None:
        self.emit(event)
