"""iPhone backup, restore and undo, as `wamove backup/restore/rollback` do them, with progress and prompts.

pymobiledevice3 logs a warning when the iPhone shows its passcode prompt; we turn that into a
"need passcode" event so the window can show a big banner.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
from collections.abc import Callable
from pathlib import Path

from wamove.cli import CHATSTORAGE, Work
from wamove.ios import backup as ios_backup
from wamove.ios import device

from ..events import Event
from ..progress import Rate
from .android import NotEnoughSpace

Emit = Callable[[Event], None]
LOGGER = "pymobiledevice3.services.mobilebackup2"


class FindMyOn(Exception):
    pass


class PasswordNeeded(Exception):
    pass


class WhatsAppMissing(Exception):
    pass


def _progress(step: str, emit: Emit) -> Callable[[float], None]:
    rate = Rate(100)

    def report(percent: float) -> None:
        pct, eta = rate.update(percent)
        emit(Event(step, "progress", pct=pct, eta_s=eta, phase="phone"))
    return report


def backup(work: Work, emit: Emit, password: str | None = None, udid: str | None = None) -> dict:
    step = "backup"
    phone = device.phone(udid)
    work.root.mkdir(mode=0o700, parents=True, exist_ok=True)
    free = shutil.disk_usage(work.root).free
    if phone.used_bytes and phone.used_bytes > free:
        raise NotEnoughSpace(phone.used_bytes, free)
    if phone.encrypts_backups and not password:
        raise PasswordNeeded()
    sink = _Sink(step, emit)
    handler = _Handler(sink)
    logger = logging.getLogger(LOGGER)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        emit(Event(step, "progress", pct=0, phase="phone"))
        _run_backup(work.full, udid, _progress(step, emit))
    finally:
        logger.removeHandler(handler)
    full = work.full / phone.udid
    emit(Event(step, "progress", pct=None, phase="copy"))
    for stale in (work.pristine / phone.udid, work.patched / phone.udid):
        shutil.rmtree(stale, ignore_errors=True)
    ios_backup.clone_tree(full, work.pristine / phone.udid)
    with ios_backup.Backup(work.pristine / phone.udid, password) as saved:
        saved.prune()
        if not saved.get(CHATSTORAGE):
            raise WhatsAppMissing()
        count = saved.count()
    emit(Event(step, "progress", pct=100, phase="copy"))
    return {"udid": phone.udid, "entries": count, "used_bytes": phone.used_bytes}


def restore(work: Work, emit: Emit, source: str = "patched", password: str | None = None,
            udid: str | None = None) -> dict:
    step = "restore" if source == "patched" else "undo"
    root = work.patched if source == "patched" else work.pristine
    found = work.udid()
    if not (root / found / "Manifest.db").is_file():
        raise FileNotFoundError(f"nothing to restore in {root}")
    phone = device.phone(udid)
    if phone.find_my:
        raise FindMyOn()
    sink = _Sink(step, emit)
    handler = _Handler(sink)
    logger = logging.getLogger(LOGGER)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        emit(Event(step, "progress", pct=0, phase="phone"))
        _run_restore(root, found, password, udid, _progress(step, emit))
    finally:
        logger.removeHandler(handler)
    emit(Event(step, "progress", pct=100, phase="phone"))
    return {"used_bytes_before": phone.used_bytes}


class _Sink:
    def __init__(self, step: str, emit: Emit):
        self.step, self.emit = step, emit


class _Handler(logging.Handler):
    def __init__(self, sink: _Sink):
        super().__init__(logging.INFO)
        self.sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        try:
            text = record.getMessage()
        except Exception:
            return
        if "enter the device passcode" in text:
            self.sink.emit(Event(self.sink.step, "need", data={"what": "passcode"}))
        elif "passcode prompt dismissed" in text:
            self.sink.emit(Event(self.sink.step, "clear", data={"what": "passcode"}))
        elif "cancelled the backup" in text:
            self.sink.emit(Event(self.sink.step, "log", data={"what": "cancelled_on_phone"}))


def _run_backup(root: Path, udid: str | None, progress: Callable[[float], None]) -> None:
    async def go() -> None:
        lockdown = await device._lockdown(udid)
        try:
            service = await device._service(lockdown)
            try:
                await service.backup(full=True, backup_directory=root, progress_callback=progress)
            finally:
                await service.close()
        finally:
            await lockdown.close()

    root.mkdir(parents=True, exist_ok=True)
    asyncio.run(go())


def _run_restore(root: Path, source: str, password: str | None, udid: str | None,
                 progress: Callable[[float], None]) -> None:
    async def go() -> None:
        lockdown = await device._lockdown(udid)
        try:
            service = await device._service(lockdown)
            try:
                await service.restore(
                    backup_directory=root,
                    system=True,
                    reboot=True,
                    copy=False,
                    settings=True,
                    remove=False,
                    password=password or "",
                    source=source,
                    progress_callback=progress,
                    skip_apps=True,
                )
            finally:
                await service.close()
        finally:
            await lockdown.close()

    asyncio.run(go())
