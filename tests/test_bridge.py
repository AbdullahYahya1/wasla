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
    monkeypatch.setattr(bridge.iphone, "backup_phone", lambda work, emit, password: "PHONE")
    monkeypatch.setattr(bridge.iphone, "keep_whatsapp", lambda work, emit, ph, password: {"udid": "U", "entries": 3})
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
    monkeypatch.setattr(bridge.iphone, "backup_phone", lambda *a: time.sleep(0.3) or "PHONE")
    monkeypatch.setattr(bridge.iphone, "keep_whatsapp", lambda *a: {})
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


def test_retry_after_wrong_password_skips_the_phone_backup(api, monkeypatch, tmp_path):
    phone_backups = []
    ph = bridge.device.Phone(udid="U1", name="", ios="", encrypts_backups=True, used_bytes=1, find_my=False)
    monkeypatch.setattr(bridge.iphone, "backup_phone", lambda *a: phone_backups.append(1) or ph)
    monkeypatch.setattr(bridge.device, "phone", lambda udid=None: ph)
    (api._work.full / "U1").mkdir(parents=True)
    (api._work.full / "U1" / "Manifest.db").write_bytes(b"")

    def keep(work, emit, ph, password):
        if password != "right":
            raise ios_backup.BackupError("the backup password is wrong")
        return {"entries": 1}
    monkeypatch.setattr(bridge.iphone, "keep_whatsapp", keep)
    api.set_password("wrong")
    api.start("backup")
    wait(api)
    assert api.events[-1].data["code"] == "password_wrong"
    assert not api.get_state()["has_password"]  # the window asks again
    api.set_password("right")
    api.start("backup")
    wait(api)
    assert api.events[-1].kind == "done" and phone_backups == [1]


def test_checks_wait_while_a_job_runs(api, monkeypatch):
    monkeypatch.setattr(bridge.iphone, "restore", lambda *a: time.sleep(0.3) or {})
    monkeypatch.setattr(bridge.checks, "iphone", lambda **k: pytest.fail("must not poll during a job"))
    api.start("restore")
    assert api.check_iphone() is None and api.check_connect() is None and api.check_ready() is None
    wait(api)


def test_double_start_from_two_threads_runs_one_job(api, monkeypatch):
    import threading
    runs = []
    monkeypatch.setattr(bridge.build, "build", lambda *a: runs.append(1) or time.sleep(0.2) or {})
    threads = [threading.Thread(target=api.start, args=("prepare",)) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wait(api)
    assert runs == [1]


def test_whatsapp_missing_retry_backs_up_the_iphone_again(api, monkeypatch):
    phone_backups = []
    monkeypatch.setattr(bridge.iphone, "backup_phone", lambda *a: phone_backups.append(1) or "PHONE")

    def keep(work, emit, ph, password):
        raise iphone.WhatsAppMissing()
    monkeypatch.setattr(bridge.iphone, "keep_whatsapp", keep)
    for _ in range(2):
        api.start("backup")
        wait(api)
    assert phone_backups == [1, 1]  # the old backup has no WhatsApp in it, so it is never reused


def test_job_that_cannot_start_caffeinate_still_reports(api, monkeypatch):
    def broken(on):
        if on:
            raise OSError("fork failed")
    monkeypatch.setattr(api, "_stay_awake", broken)
    monkeypatch.setattr(bridge.iphone, "restore", lambda *a: {})
    api.start("restore")
    wait(api)
    assert api.events[-1].kind == "error" and not api.busy()


def test_not_busy_by_the_time_the_window_hears_done(api, monkeypatch):
    seen = []
    api._emit = bridge.Emitter(lambda e: seen.append((e.kind, api.busy())))
    monkeypatch.setattr(bridge.iphone, "restore", lambda *a: {})
    api.start("restore")
    wait(api)
    assert seen[-1] == ("done", False)
