"""The Wasla window."""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import webview

from . import __version__
from .bridge import Api, Paths
from .events import Event

UI = Path(__file__).parent / "ui" / "index.html"


def mac_language() -> str:
    try:
        out = subprocess.run(["defaults", "read", "-g", "AppleLanguages"], capture_output=True, text=True,
                             timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return "en"
    first = next((line.strip(' ",()') for line in out.splitlines() if line.strip(' ",()')), "en")
    return "ar" if first.startswith("ar") else "en"


def main() -> None:
    # A Finder-launched app gets a bare PATH; ffmpeg (video thumbnails) usually lives in Homebrew.
    os.environ["PATH"] = os.pathsep.join([os.environ.get("PATH", "/usr/bin:/bin"), "/opt/homebrew/bin",
                                          "/usr/local/bin"])
    logs = Path.home() / "Library" / "Logs" / "Wasla"
    logs.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(logs / "wasla.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.WARNING, handlers=[handler])
    logging.getLogger("wasla").setLevel(logging.INFO)
    logging.getLogger("wasla").info("Wasla %s starting", __version__)
    holder: dict = {}

    def send(event: Event) -> None:
        window = holder.get("window")
        if window is not None:
            window.evaluate_js(f"window.wasla && wasla.onEvent({event.to_json()})")

    api = Api(Paths.default(), send)
    if not api._state.data.get("lang"):
        api.set_lang(mac_language())

    smoke = os.environ.get("WASLA_SMOKE")  # packaged-app self test: write a report there and quit
    window = webview.create_window(
        "Wasla",
        url=str(UI),
        js_api=api,
        hidden=bool(smoke),
        width=1080,
        height=740,
        min_size=(920, 640),
        background_color="#0E1513",
        text_select=False,
    )
    holder["window"] = window

    def closing():
        if api.busy() and api._job_name in ("restore", "undo", "backup"):
            return window.create_confirmation_dialog(
                "Wasla", "The iPhone is still being backed up or restored. Quit anyway?") is True
        return True

    window.events.closing += closing
    if smoke:
        webview.start(_self_test, (window, api, Path(smoke)), private_mode=True)
    else:
        webview.start(debug=bool(os.environ.get("WASLA_DEBUG")), private_mode=True)


def _self_test(window, api: Api, report: Path) -> None:
    import time

    result: dict = {}
    try:
        for _ in range(100):
            time.sleep(0.2)
            if window.evaluate_js("document.querySelectorAll('.stop').length") == 9:
                break
        result["h1"] = window.evaluate_js("document.querySelector('h1').textContent")
        result["font"] = window.evaluate_js("document.fonts.check('16px \"Readex Pro\"')")
        result["checks"] = api.check_connect()
        result["ok"] = True
    except Exception as exc:  # noqa: BLE001
        result["error"] = repr(exc)
    report.write_text(json.dumps(result, ensure_ascii=False, default=str))
    window.destroy()


if __name__ == "__main__":
    sys.exit(main())
