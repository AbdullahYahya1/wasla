"""Screenshot the UI in demo mode with headless Chrome: python tools/screens.py [name=query ...]"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "src" / "wasla" / "ui" / "index.html"
OUT = ROOT / "shots"

SCENES = {
    "welcome": "step=welcome",
    "connect": "step=connect",
    "connect-wait": "step=connect&scene=waiting&open=usb",
    "key": "step=key",
    "key-done": "step=key&scene=done",
    "key-error": "step=key&scene=error&code=key_wrong",
    "copy-run": "step=copy&scene=running&pct=37",
    "copy-done": "step=copy&scene=done",
    "ready": "step=ready&scene=findmy&open=grey",
    "backup-pass": "step=backup&scene=running&pct=3&need=passcode",
    "prepare-run": "step=prepare&scene=running&pct=41",
    "prepare-done": "step=prepare&scene=done",
    "restore": "step=restore",
    "restore-run": "step=restore&scene=running&pct=62",
    "finish": "step=finish",
    "help": "step=welcome&help=1",
    "unknown": "step=prepare&scene=error&code=unknown",
}


def shoot(name: str, query: str, lang: str, theme: str, size=(1080, 740), scale: int = 1, out: Path | None = None) -> Path:
    target = (out or OUT) / f"{name}-{lang}-{theme}{'@2x' if scale == 2 else ''}.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    url = f"{UI.as_uri()}?demo=1&lang={lang}&theme={theme}&{query}"
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run([CHROME, "--headless=new", f"--user-data-dir={profile}", "--hide-scrollbars", "--disable-gpu",
                        f"--force-device-scale-factor={scale}", f"--window-size={size[0]},{size[1]}", "--virtual-time-budget=4000",
                        f"--screenshot={target}", url], capture_output=True, timeout=60)
    return target


if __name__ == "__main__":
    picks = sys.argv[1:] or list(SCENES)
    for pick in picks:
        name, _, rest = pick.partition(":")
        langs = [rest.split("/")[0]] if rest else ["en", "ar"]
        themes = [rest.split("/")[1]] if "/" in rest else ["light"]
        for lang in langs:
            for theme in themes:
                print(shoot(name, SCENES[name], lang, theme))
