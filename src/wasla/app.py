"""The Wasla window."""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import webview

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
    logging.basicConfig(level=logging.WARNING)
    holder: dict = {}

    def send(event: Event) -> None:
        window = holder.get("window")
        if window is not None:
            window.evaluate_js(f"window.wasla && wasla.onEvent({event.to_json()})")

    api = Api(Paths.default(), send)
    if not api._state.data.get("lang"):
        api.set_lang(mac_language())

    window = webview.create_window(
        "Wasla",
        url=str(UI),
        js_api=api,
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
    webview.start(debug=bool(os.environ.get("WASLA_DEBUG")), private_mode=True)


if __name__ == "__main__":
    sys.exit(main())
