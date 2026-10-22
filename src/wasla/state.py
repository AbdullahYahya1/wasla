"""Which steps are finished, kept in the work folder so Wasla can carry on after a restart."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

STEPS = ("welcome", "connect", "key", "copy", "ready", "backup", "prepare", "restore", "finish")


class State:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict = {"steps": {}, "lang": None}
        self._lock = threading.RLock()  # the job thread and the window's calls both save

    def load(self) -> State:
        try:
            self.data = json.loads(self.path.read_text())
            self.data.setdefault("steps", {})
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return self

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            tmp = self.path.with_name(f"{self.path.name}.{threading.get_ident()}.tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1))
            os.replace(tmp, self.path)

    def done(self, step: str) -> bool:
        return step in self.data["steps"]

    def get(self, step: str) -> dict:
        return self.data["steps"].get(step, {})

    def mark(self, step: str, **stats) -> None:
        with self._lock:
            self.data["steps"][step] = {"at": time.time(), **stats}
            self.save()

    def reset_from(self, step: str) -> None:
        with self._lock:
            later = STEPS[STEPS.index(step):]
            self.data["steps"] = {k: v for k, v in self.data["steps"].items() if k not in later}
            self.save()

    def current(self) -> str:
        return next((s for s in STEPS if not self.done(s)), STEPS[-1])
