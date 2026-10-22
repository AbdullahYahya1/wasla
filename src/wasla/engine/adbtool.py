"""Find adb, or download Google's platform-tools into Wasla's own folder.

Google's license does not let us ship adb inside the app, so the first time it is needed Wasla fetches the
official zip from dl.google.com. wamove's adb helpers are pointed at whichever adb we use.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path

from wamove.android import adb as wamove_adb

URL = "https://dl.google.com/android/repository/platform-tools-latest-darwin.zip"


def bundled(support: Path) -> Path:
    return support / "platform-tools" / "adb"


def find(support: Path) -> str | None:
    own = bundled(support)
    if own.is_file() and os.access(own, os.X_OK):
        return str(own)
    found = shutil.which("adb")
    if found:
        return found
    return next((p for p in wamove_adb.FALLBACK_ADB if os.path.isfile(p)), None)


def use(path: str) -> None:
    """Make wamove's adb module run this adb."""
    wamove_adb._adb = lambda: path


def download(support: Path, on_progress: Callable[[int, int], None], url: str = URL) -> str:
    support.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=support) as scratch:
        archive = Path(scratch) / "platform-tools.zip"
        with urllib.request.urlopen(url, timeout=60) as response, archive.open("wb") as out:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            while chunk := response.read(256 * 1024):
                out.write(chunk)
                done += len(chunk)
                on_progress(done, total)
        target = support / "platform-tools"
        shutil.rmtree(target, ignore_errors=True)
        with zipfile.ZipFile(archive) as zf:
            for member in zf.infolist():
                if not member.filename.startswith("platform-tools/") or ".." in member.filename:
                    continue
                zf.extract(member, support)
                mode = member.external_attr >> 16
                if mode:
                    os.chmod(support / member.filename, mode)
    adb = bundled(support)
    os.chmod(adb, 0o755)
    subprocess.run([str(adb), "version"], capture_output=True, check=True, timeout=30)
    return str(adb)
