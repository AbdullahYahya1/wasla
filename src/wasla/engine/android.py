"""Copy WhatsApp's backup, contact names and media off the Android phone, then decrypt the chats.

Same files and folders as `wamove pull` and `wamove decrypt`, with progress: adb prints nothing useful
about the total, so we watch the bytes arrive on the Mac.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path

from wamove.android import adb, crypt15
from wamove.cli import Work, load_archive

from ..events import Event
from ..progress import Rate

STEP = "copy"
Emit = Callable[[Event], None]


class Cancelled(Exception):
    pass


class NotEnoughSpace(Exception):
    def __init__(self, needed: int, free: int):
        super().__init__(f"needs {needed} bytes, {free} free")
        self.needed, self.free = needed, free


def folder_bytes(path: Path) -> int:
    total = 0
    stack = [path]
    while stack:
        try:
            entries = list(os.scandir(stack.pop()))
        except (FileNotFoundError, NotADirectoryError, PermissionError):
            continue
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    stack.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
            except OSError:
                continue
    return total


def remote_sizes(root: str, folders: list[str]) -> dict[str, int]:
    return {folder: adb.remote_bytes(f"{root}/Media/{folder}") for folder in folders}


def pull_watched(remote: str, local: Path, on_bytes: Callable[[int], None], cancel: threading.Event,
                 watch: Path, interval: float = 1.0) -> None:
    """Run `adb pull` and report how many bytes have landed in `watch` until it finishes."""
    local.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen([adb._adb(), "pull", "-a", remote, str(local)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        while True:
            try:
                process.wait(timeout=interval)
                break
            except subprocess.TimeoutExpired:
                pass
            if cancel.is_set():
                process.terminate()
                process.wait()
                raise Cancelled()
            on_bytes(folder_bytes(watch))
        if process.returncode:
            error = (process.stderr.read() or b"").decode(errors="replace").strip()
            raise adb.AdbError(f"adb pull {remote} failed: {error}")
        on_bytes(folder_bytes(watch))
    finally:
        if process.poll() is None:
            process.kill()


def sample(work: Work) -> Path:
    """Copy the smallest encrypted file on the phone, to test the key quickly."""
    root = adb.whatsapp_root()
    listing = adb.shell(f'stat -c "%s %n" "{root}"/Backups/*.crypt15 "{root}"/Databases/*.crypt15 2>/dev/null')
    files = []
    for line in listing.splitlines():
        size, _, name = line.strip().partition(" ")
        if size.isdigit() and name.endswith(".crypt15"):
            files.append((int(size), name))
    if not files:
        files = [(0, f"{root}/Databases/msgstore.db.crypt15")]
    remote = min(files)[1]
    target = work.android / "sample"
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(mode=0o700, parents=True)
    adb.pull(remote, target)
    found = sorted(target.glob("*.crypt15"))
    if not found:
        raise adb.AdbError("could not copy a backup file to check the key")
    return found[0]


def pull(work: Work, emit: Emit, cancel: threading.Event) -> dict:
    root = adb.whatsapp_root()
    work.android.mkdir(mode=0o700, parents=True, exist_ok=True)
    emit(Event(STEP, "progress", pct=0, phase="chats"))
    adb.pull(f"{root}/Databases/msgstore.db.crypt15", work.crypt15.parent)
    names = adb.contacts()
    work.contacts.write_text(json.dumps(names, ensure_ascii=False, indent=1))
    folders = adb.media_dirs(root)
    sizes = remote_sizes(root, folders)
    needed = sum(sizes.values())
    already = folder_bytes(work.media) if work.media.is_dir() else 0
    free = shutil.disk_usage(work.root).free + already
    if needed > free:
        raise NotEnoughSpace(needed, free)
    shutil.rmtree(work.media, ignore_errors=True)
    rate = Rate(needed)
    finished = 0
    for folder in folders:
        if cancel.is_set():
            raise Cancelled()
        target = work.media / folder

        def report(landed: int, folder=folder) -> None:
            done = finished + min(landed, sizes[folder])
            pct, eta = rate.update(done)
            emit(Event(STEP, "progress", pct=pct, eta_s=eta, phase=folder,
                       data={"done_bytes": done, "total_bytes": needed}))

        pull_watched(f"{root}/Media/{folder}", work.media, report, cancel, target)
        finished += sizes[folder]
    emit(Event(STEP, "progress", pct=100, phase="media", data={"done_bytes": needed, "total_bytes": needed}))
    return {"contacts": len(names), "media_bytes": needed, "folders": sizes}


def decrypt(work: Work, key: bytes, emit: Emit) -> dict:
    emit(Event(STEP, "progress", pct=None, phase="decrypt"))
    crypt15.decrypt_file(work.crypt15, work.msgstore, key)
    os.chmod(work.msgstore, 0o600)
    emit(Event(STEP, "progress", pct=None, phase="read"))
    return summary(work)


def summary(work: Work) -> dict:
    archive = load_archive(work, None)
    stats = archive.stats()
    stamps = [m.timestamp_ms for c in archive.chats for m in c.messages if m.timestamp_ms]
    stats.update({
        "first_ms": min(stamps) if stamps else None,
        "last_ms": max(stamps) if stamps else None,
        "sent": sum(1 for c in archive.chats for m in c.messages if m.from_me),
    })
    return stats
