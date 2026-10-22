import time

import pytest
from wamove.android import adb, crypt15
from wamove.ios import backup as ios_backup
from wamove.ios import device

from wasla import bridge
from wasla.engine import android, iphone, keygrid
from wasla.errors import friendly


def wait(api, timeout=5):
    end = time.time() + timeout
    while api.busy() and time.time() < end:
        time.sleep(0.01)


@pytest.fixture
def api(tmp_path):
    events = []
    a = bridge.Api(bridge.Paths(tmp_path / "support"), events.append)
    a.events = events
    return a


@pytest.mark.parametrize("exc,code", [
    (adb.AdbError("no Android phone found: turn on USB debugging, plug it in and allow this Mac"), "no_android"),
    (adb.AdbError("the Android phone is 'unauthorized': unlock it and accept the USB debugging prompt"),
     "android_unauthorized"),
    (adb.AdbError("the phone only has an older backup format: in WhatsApp turn on ..."), "old_backup_format"),
    (adb.AdbError("no WhatsApp backup on the phone: in WhatsApp open ..."), "no_backup_on_android"),
    (crypt15.Crypt15Error("the key does not open this backup; make a new backup"), "key_wrong"),
    (keygrid.KeyProblem("key_format"), "key_format"),
    (device.DeviceError("no iPhone found: plug it in and unlock it"), "no_iphone"),
    (device.DeviceError("the iPhone does not trust this Mac yet: unlock it and tap Trust"), "iphone_untrusted"),
    (iphone.FindMyOn(), "find_my_on"),
    (iphone.PasswordNeeded(), "password_needed"),
    (ios_backup.BackupError("the backup password is wrong"), "password_wrong"),
    (android.NotEnoughSpace(10, 5), "no_space"),
    (android.Cancelled(), "cancelled"),
    (type("ConnectionTerminatedError", (Exception,), {})(), "iphone_disconnected"),
    (ValueError("boom"), "unknown"),
])
def test_friendly_codes(exc, code):
    assert friendly(exc)[0] == code


def test_job_success_marks_state_and_emits_done(api, monkeypatch):
    monkeypatch.setattr(bridge.iphone, "backup", lambda work, emit, password: {"udid": "U", "entries": 3})
    assert api.start("backup")
    wait(api)
    assert api._state.done("backup") and api._state.get("backup")["entries"] == 3
    assert api.events[-1].kind == "done" and api.events[-1].step == "backup"


def test_job_failure_emits_error_code(api, monkeypatch):
    def fail(*a):
        raise iphone.FindMyOn()
    monkeypatch.setattr(bridge.iphone, "restore", fail)
    api.start("restore")
    wait(api)
    assert api.events[-1].kind == "error" and api.events[-1].data["code"] == "find_my_on"
    assert not api._state.done("restore")


def test_copy_without_key_asks_for_it(api):
    api.start("copy")
    wait(api)
    assert api.events[-1].data["code"] == "key_missing"


def test_only_one_job_at_a_time(api, monkeypatch):
    monkeypatch.setattr(bridge.iphone, "backup", lambda *a: time.sleep(0.3) or {})
    assert api.start("backup")
    assert not api.start("prepare")
    wait(api)


def test_restore_cannot_be_cancelled(api, monkeypatch):
    monkeypatch.setattr(bridge.iphone, "restore", lambda *a: time.sleep(0.2) or {})
    api.start("restore")
    api.cancel()
    assert not api._cancel.is_set()
    wait(api)


def test_key_is_kept_in_memory_only(api, monkeypatch, crypt15_sample, key_hex, tmp_path):
    monkeypatch.setattr(bridge.android, "sample", lambda work: crypt15_sample)
    api.check_key(key_hex)
    wait(api)
    assert api.get_state()["has_key"]
    assert api._state.get("key")["order"] == "as_typed"
    stored = (tmp_path / "support").rglob("*")
    assert not any(key_hex in p.read_text(errors="ignore") for p in stored if p.is_file())


def test_links_are_allowlisted(api, monkeypatch):
    opened = []
    monkeypatch.setattr(bridge.webbrowser, "open", opened.append)
    api.open_url("https://support.apple.com/en-us/101973")
    api.open_url("file:///etc/passwd")
    assert opened == ["https://support.apple.com/en-us/101973"]


def test_cleanup_keeps_the_iphone_backup_by_default(api):
    for folder in (api._work.android, api._work.full, api._work.pristine):
        folder.mkdir(parents=True)
    api.cleanup()
    assert api._work.full.is_dir() and not api._work.android.exists() and not api._work.pristine.exists()
