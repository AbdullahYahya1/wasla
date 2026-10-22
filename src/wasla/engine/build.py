"""Add the Android chats and media to the WhatsApp-only copy of the iPhone backup (`wamove build`).

Two changes from wamove's own command, neither of which touches its database code:
- Thumbnails are made first, in parallel, into a cache, photos decoded in-process at reduced size.
  wamove makes them one at a time with `sips` while it imports: ~20 minutes for 28,444 thumbnails on the
  first real transfer, ~27 seconds this way on the same data (10-core Mac), with the same counts.
- A Writer subclass reports how many messages are in, so the window can show one overall percent.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image
from wamove.cli import CHATSTORAGE, Work, load_archive
from wamove.ios import backup as ios_backup
from wamove.ios import chatstorage, thumbs
from wamove.model import Archive, Kind

from ..events import Event
from ..progress import Phases, Rate
from .android import Cancelled, NotEnoughSpace

STEP = "prepare"
THUMB_KINDS = (Kind.IMAGE, Kind.VIDEO, Kind.GIF)
Emit = Callable[[Event], None]
Cached = tuple[Path | None, tuple[int, int] | None]


class BuildFailed(Exception):
    pass


def thumbnail_jobs(archive: Archive, media_root: Path | None) -> list[tuple[Kind, str]]:
    if media_root is None:
        return []
    seen: dict[str, Kind] = {}
    root = str(media_root)
    for chat in archive.chats:
        for message in chat.messages:
            if message.kind in THUMB_KINDS and message.media and message.media.android_path:
                local = chatstorage._locate(message.media.android_path, root)
                if local and local not in seen:
                    seen[local] = message.kind
    return [(kind, local) for local, kind in seen.items()]


def image_thumb(source: str, target: Path) -> tuple[int, int] | None:
    """Same result as wamove's `sips` crop-and-shrink, decoded at reduced size in-process (much faster).

    Falls back to `sips` for anything Pillow cannot open.
    """
    try:
        with Image.open(source) as im:
            width, height = im.size
            im.draft("RGB", (thumbs.SIDE * 2, thumbs.SIDE * 2))
            im = im.convert("RGB")
            w, h = im.size
            side = min(w, h)
            left, top = (w - side) // 2, (h - side) // 2
            im.crop((left, top, left + side, top + side)) \
              .resize((thumbs.SIDE, thumbs.SIDE), Image.Resampling.LANCZOS) \
              .save(target, "JPEG", quality=82)
        return width, height
    except Exception:
        target.unlink(missing_ok=True)
        return thumbs.image(source, target)


def _one(kind: Kind, local: str, cache: Path) -> tuple[str, Cached]:
    target = cache / (hashlib.sha1(local.encode()).hexdigest() + ".thumb")
    if kind is Kind.IMAGE:
        size = image_thumb(local, target)
        return local, ((target, size) if size else (None, None))
    return local, ((target, None) if thumbs.video(local, target) else (None, None))


def make_thumbnails(jobs: list[tuple[Kind, str]], cache: Path, on_done: Callable[[int], None],
                    cancel: threading.Event, workers: int | None = None) -> dict[str, Cached]:
    cache.mkdir(parents=True, exist_ok=True)
    results: dict[str, Cached] = {}
    workers = workers or max(2, (os.cpu_count() or 4))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_one, kind, local, cache) for kind, local in jobs]
        try:
            for done, future in enumerate(as_completed(futures), 1):
                local, made = future.result()
                results[local] = made
                on_done(done)
                if cancel.is_set():
                    raise Cancelled()
        except BaseException:
            for future in futures:
                future.cancel()
            raise
    return results


class ProgressWriter(chatstorage.Writer):
    """wamove's Writer, taking thumbnails from the cache and counting messages as chats go in."""

    def __init__(self, path: Path, lids: dict[str, str] | None, cache: dict[str, Cached],
                 on_messages: Callable[[int], None]):
        super().__init__(path, lids)
        self.cache = cache
        self.on_messages = on_messages

    def _thumbnail(self, kind, local, name):
        if self.thumbnails is None:
            return None
        if local not in self.cache:
            return super()._thumbnail(kind, local, name)
        made, size = self.cache[local]
        if made is None or not made.is_file():
            return None
        target = self.thumbnails / f"{name}.thumb"
        try:
            os.link(made, target)
        except OSError:
            shutil.copyfile(made, target)
        return (target, size) if kind is Kind.IMAGE else (target, None)

    def _import_chat(self, chat, archive, report, media_root):
        session = super()._import_chat(chat, archive, report, media_root)
        self.on_messages(len(chat.messages))
        return session


def estimate(messages: int, thumbs_to_make: int, media_files: int, media_bytes: int, workers: int) -> dict:
    """Rough seconds per phase, from the first real transfer on an M-series Mac."""
    return {
        "read": 10 + messages * 0.00001,
        "thumbnails": 1 + thumbs_to_make * 0.0095 / max(1, workers),
        "chats": 5 + messages * 0.00002 + media_bytes / 300e6,
        "media": media_bytes / 220e6 + media_files * 0.0004,
        "check": 10,
    }


def build(work: Work, emit: Emit, cancel: threading.Event, password: str | None = None) -> dict:
    udid = work.udid()
    pristine = work.pristine / udid
    emit(Event(STEP, "progress", pct=0, phase="read"))
    archive = load_archive(work, None)
    stats = archive.stats()
    shutil.rmtree(work.build, ignore_errors=True)
    work.build.mkdir(parents=True)
    shutil.rmtree(work.patched / udid, ignore_errors=True)
    ios_backup.clone_tree(pristine, work.patched / udid)
    media = work.media if work.media.is_dir() else None
    jobs = thumbnail_jobs(archive, media)
    workers = max(2, os.cpu_count() or 4)
    media_bytes = sum(f.stat().st_size for f in media.rglob("*") if f.is_file()) if media else 0
    needed = media_bytes + 2 * 1024**3  # every media file is written again into the restore copy
    free = shutil.disk_usage(work.root).free
    if needed > free:
        raise NotEnoughSpace(needed, free)
    phases = Phases(estimate(stats["messages"], len(jobs), stats["media"], media_bytes, workers))
    rate = Rate(100)

    def report(phase: str, fraction: float, **data) -> None:
        if cancel.is_set():
            raise Cancelled()
        pct, eta = rate.update(phases.overall(phase, fraction))
        emit(Event(STEP, "progress", pct=pct, eta_s=eta, phase=phase, data=data))

    report("read", 1.0)
    cache = make_thumbnails(jobs, work.build / "thumbcache",
                            lambda n: report("thumbnails", n / max(len(jobs), 1), done=n, total=len(jobs)),
                            cancel, workers)
    database = work.build / CHATSTORAGE
    with ios_backup.Backup(work.patched / udid, password) as target:
        for name in (CHATSTORAGE, CHATSTORAGE + "-wal"):
            target.read(name, work.build / name)
        imported = [0]

        def on_messages(count: int) -> None:
            imported[0] += count
            report("chats", imported[0] / max(stats["messages"], 1), done=imported[0], total=stats["messages"])

        writer = ProgressWriter(database, archive.lids, cache, on_messages)
        (work.build / "thumbs").mkdir()
        result = writer.import_archive(archive, media, work.build / "thumbs")
        writer.close()
        problems = chatstorage.verify(database)
        if problems:
            raise BuildFailed("; ".join(problems[:5]))
        target.put(CHATSTORAGE, database)
        empty = work.build / "empty"
        empty.write_bytes(b"")
        for suffix in ("-wal", "-shm"):
            target.put(CHATSTORAGE + suffix, empty)
        total = len(result.media_files)
        for done, item in enumerate(result.media_files, 1):
            target.put(item.relative_path, Path(item.source))
            if done % 50 == 0 or done == total:
                report("media", done / max(total, 1), done=done, total=total)
        report("check", 0.0)
        problems = target.check()
        if problems:
            raise BuildFailed("; ".join(problems[:5]))
    shutil.rmtree(work.build / "thumbcache", ignore_errors=True)
    report("check", 1.0)
    return {
        "chats_created": result.sessions_created,
        "chats_merged": result.sessions_reused,
        "messages_added": result.messages_written,
        "messages_skipped": result.messages_skipped,
        "media_found": result.media_linked,
        "media_missing": result.media_missing,
        "thumbnails": result.thumbnails,
    }
