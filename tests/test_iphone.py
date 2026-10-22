import logging
import plistlib

import pytest
from wamove.cli import Work
from wamove.ios import device

from wasla.engine import iphone


def fake_backup(root, encrypted=False):
    (root / "UDID1").mkdir(parents=True)
    (root / "UDID1" / "Manifest.db").write_bytes(b"")
    (root / "UDID1" / "Manifest.plist").write_bytes(plistlib.dumps({"IsEncrypted": encrypted}))


def phone(**over):
    values = dict(udid="UDID1", name="iPhone", ios="27.0.1", encrypts_backups=False,
                  used_bytes=1000, find_my=False)
    values.update(over)
    return device.Phone(**values)


def test_passcode_prompt_becomes_an_event():
    events = []
    handler = iphone._Handler(iphone._Sink("backup", events.append))
    logger = logging.getLogger(iphone.LOGGER)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        logger.warning("Please enter the device passcode to continue the backup")
        logger.info("Device passcode prompt dismissed")
    finally:
        logger.removeHandler(handler)
    assert [(e.kind, e.data["what"]) for e in events] == [("need", "passcode"), ("clear", "passcode")]


def test_restore_refuses_while_find_my_is_on(tmp_path, monkeypatch):
    work = Work(tmp_path)
    fake_backup(work.pristine)
    fake_backup(work.patched)
    monkeypatch.setattr(device, "phone", lambda udid=None: phone(find_my=True))
    called = []
    monkeypatch.setattr(iphone, "_run_restore", lambda *a: called.append(a))
    with pytest.raises(iphone.FindMyOn):
        iphone.restore(work, lambda e: None)
    assert not called


def test_restore_reports_progress(tmp_path, monkeypatch):
    work = Work(tmp_path)
    for root in (work.pristine, work.patched):
        fake_backup(root)
    asked = []
    monkeypatch.setattr(device, "phone", lambda udid=None: asked.append(udid) or phone())

    def fake_restore(root, source, password, udid, progress):
        assert root == work.patched and source == "UDID1"
        for pct in (0, 25, 50, 100):
            progress(pct)
    monkeypatch.setattr(iphone, "_run_restore", fake_restore)
    events = []
    iphone.restore(work, events.append)
    assert events[-1].pct == 100
    assert asked == ["UDID1"]  # only the iPhone the backup came from


def test_undo_restores_the_untouched_copy(tmp_path, monkeypatch):
    work = Work(tmp_path)
    fake_backup(work.pristine)
    monkeypatch.setattr(device, "phone", lambda udid=None: phone())
    seen = []
    monkeypatch.setattr(iphone, "_run_restore", lambda root, *a: seen.append(root))
    iphone.restore(work, lambda e: None, source="pristine")
    assert seen == [work.pristine]


def test_backup_asks_for_password_first(tmp_path, monkeypatch):
    monkeypatch.setattr(device, "phone", lambda udid=None: phone(encrypts_backups=True))
    monkeypatch.setattr(iphone, "_run_backup", lambda *a: pytest.fail("should not start"))
    with pytest.raises(iphone.PasswordNeeded):
        iphone.backup(Work(tmp_path), lambda e: None)


def test_backup_needs_space(tmp_path, monkeypatch):
    monkeypatch.setattr(device, "phone", lambda udid=None: phone(used_bytes=10**15))
    with pytest.raises(iphone.NotEnoughSpace):
        iphone.backup(Work(tmp_path), lambda e: None)


def test_encrypted_restore_without_password_stops_before_the_phone(tmp_path, monkeypatch):
    work = Work(tmp_path)
    fake_backup(work.pristine, encrypted=True)
    fake_backup(work.patched, encrypted=True)
    monkeypatch.setattr(device, "phone", lambda udid=None: pytest.fail("must not touch the phone"))
    with pytest.raises(iphone.PasswordNeeded):
        iphone.restore(work, lambda e: None)


def test_undo_after_cleanup_says_nothing_to_restore(tmp_path):
    with pytest.raises(iphone.NothingToRestore):
        iphone.restore(Work(tmp_path), lambda e: None, source="pristine")
