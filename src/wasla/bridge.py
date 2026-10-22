"""What the window can ask for. Each long job runs on one worker thread and reports through events."""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
import traceback
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from wamove.cli import Work

from . import __version__
from .engine import adbtool, android, build, checks, iphone, keygrid
from .errors import friendly
from .events import Emitter, Event
from .state import STEPS, State

ALLOWED_LINKS = ("https://github.com/", "https://support.apple.com/", "https://faq.whatsapp.com/",
                 "https://apps.apple.com/", "https://wasla.app/")


@dataclass
class Paths:
    support: Path

    @property
    def work(self) -> Path:
        return self.support / "work"

    @property
    def state(self) -> Path:
        return self.work / "state.json"

    @classmethod
    def default(cls) -> Paths:
        return cls(Path.home() / "Library" / "Application Support" / "Wasla")


class Api:
    def __init__(self, paths: Paths, send: Callable[[Event], None] | None = None):
        self._paths = paths
        self._work = Work(paths.work)
        self._state = State(paths.state).load()
        self._emit = Emitter(send or (lambda e: None))
        self._job: threading.Thread | None = None
        self._job_name: str | None = None
        self._cancel = threading.Event()
        self._key: bytes | None = None
        self._password: str | None = None
        self._awake: subprocess.Popen | None = None
        self._adb = adbtool.find(paths.support)
        if self._adb:
            adbtool.use(self._adb)

    # ----- small calls -------------------------------------------------------------------------------

    def get_state(self) -> dict:
        return {
            "version": __version__,
            "steps": self._state.data["steps"],
            "current": self._state.current(),
            "lang": self._state.data.get("lang"),
            "busy": self._job_name if self.busy() else None,
            "has_key": self._key is not None,
            "has_password": self._password is not None,
            "work": str(self._paths.work),
        }

    def set_lang(self, lang: str) -> None:
        if lang in ("ar", "en"):
            self._state.data["lang"] = lang
            self._state.save()

    def mark(self, step: str, data: dict | None = None) -> dict:
        if step in ("welcome", "connect", "ready", "finish"):
            self._state.mark(step, **(data or {}))
        return self.get_state()

    def go_back(self, step: str) -> dict:
        if step in STEPS and not self.busy():
            self._state.reset_from(step)
        return self.get_state()

    def check_connect(self) -> dict:
        return {
            "android": checks.android(self._adb),
            "iphone": checks.iphone(),
            "disk": checks.disk(self._paths.work),
        }

    def check_ready(self) -> dict:
        return {"iphone": checks.iphone(with_apps=True), "android": checks.android(self._adb)}

    def check_iphone(self) -> dict:
        return checks.iphone()

    def set_password(self, password: str) -> None:
        self._password = password or None

    def open_url(self, url: str) -> None:
        if isinstance(url, str) and url.startswith(ALLOWED_LINKS):
            webbrowser.open(url)

    def show_folder(self) -> None:
        self._paths.work.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(self._paths.work)], check=False)

    def busy(self) -> bool:
        return self._job is not None and self._job.is_alive()

    def cancel(self) -> None:
        if self._job_name in ("restore", "undo"):
            return  # stopping a restore halfway leaves the iPhone mid-restore; let it finish
        self._cancel.set()

    # ----- jobs ----------------------------------------------------------------------------------------

    def install_adb(self) -> bool:
        def job():
            def on_progress(done, total):
                self._emit(Event("adb", "progress", pct=100 * done / total if total else None,
                                data={"done_bytes": done, "total_bytes": total}))
            self._adb = adbtool.download(self._paths.support, on_progress)
            adbtool.use(self._adb)
            return {}
        return self._start("adb", job, mark=False)

    def check_key(self, text: str) -> bool:
        def job():
            keygrid.candidates(text)  # format problems first, before touching the phone
            self._emit(Event("key", "progress", pct=None, phase="sample"))
            sample = android.sample(self._work)
            order, key = keygrid.find_working_key(text, sample)
            self._key = key
            return {"order": order}
        return self._start("key", job)

    def start(self, step: str) -> bool:
        jobs = {
            "copy": self._copy,
            "backup": lambda: iphone.backup(self._work, self._emit, self._password),
            "prepare": lambda: build.build(self._work, self._emit, self._cancel, self._password),
            "restore": lambda: iphone.restore(self._work, self._emit, "patched", self._password),
            "undo": lambda: iphone.restore(self._work, self._emit, "pristine", self._password),
        }
        if step not in jobs:
            return False
        return self._start(step, jobs[step], mark=step != "undo")

    def cleanup(self, keep_iphone_backup: bool = True) -> dict:
        """Delete the private copies once the user is happy. The full iPhone backup is kept unless asked."""
        if self.busy():
            return {"ok": False}
        targets = [self._work.android, self._work.build, self._work.patched, self._work.pristine]
        if not keep_iphone_backup:
            targets.append(self._work.full)
        for target in targets:
            shutil.rmtree(target, ignore_errors=True)
        self._key = None
        self._state.mark("finish", cleaned=True, kept_backup=keep_iphone_backup)
        return {"ok": True, "free": checks.disk(self._paths.work)["free_bytes"]}

    def _copy(self) -> dict:
        if self._key is None:
            raise keygrid.KeyProblem("key_missing")
        result = android.pull(self._work, self._emit, self._cancel)
        summary = android.decrypt(self._work, self._key, self._emit)
        return {**result, **summary}

    def _start(self, name: str, work: Callable[[], dict], mark: bool = True) -> bool:
        if self.busy():
            return False
        self._cancel.clear()
        self._job_name = name

        def run():
            self._stay_awake(True)
            started = time.time()
            try:
                result = work() or {}
                result["seconds"] = round(time.time() - started)
                if mark:
                    self._state.mark(name, **result)
                self._emit(Event(name, "done", pct=100, data=result))
            except BaseException as exc:  # noqa: BLE001 - every failure must reach the window
                code, data = friendly(exc)
                if code == "unknown":
                    data["trace"] = traceback.format_exc()[-2000:]
                self._emit(Event(name, "error", data={"code": code, **data}))
            finally:
                self._stay_awake(False)

        self._job = threading.Thread(target=run, name=f"wasla-{name}", daemon=True)
        self._job.start()
        return True

    def _stay_awake(self, on: bool) -> None:
        """Keep the Mac from sleeping mid-copy (and the display on, so the user sees prompts)."""
        if on and self._awake is None and shutil.which("caffeinate"):
            self._awake = subprocess.Popen(["caffeinate", "-dimsu", "-w", str(os.getpid())])
        elif not on and self._awake is not None:
            self._awake.terminate()
            self._awake = None
