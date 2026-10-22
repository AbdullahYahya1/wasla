import os
import stat
import zipfile
from pathlib import Path

import pytest
from wamove.ios import device

from wasla.engine import adbtool, checks

FAKE_ADB = """#!/bin/sh
case "$1" in
  devices) printf 'List of devices attached\\n%s' "$FAKE_DEVICES" ;;
  shell)
    case "$2" in
      ls*/sdcard/*) echo "$FAKE_LS" ;;
      ls*) ;;
      stat*) echo 1700000000 ;;
      date*) echo 1700003600 ;;
    esac ;;
esac
"""


@pytest.fixture
def fake_adb(tmp_path, monkeypatch):
    path = tmp_path / "adb"
    path.write_text(FAKE_ADB)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    adbtool.use(str(path))
    monkeypatch.setenv("FAKE_LS", "msgstore.db.crypt15")
    return str(path)


def test_no_adb():
    assert checks.android(None)["state"] == "no_adb"


def test_no_phone(fake_adb, monkeypatch):
    monkeypatch.setenv("FAKE_DEVICES", "")
    assert checks.android(fake_adb)["state"] == "missing"


def test_unauthorized(fake_adb, monkeypatch):
    monkeypatch.setenv("FAKE_DEVICES", "ZY22 unauthorized usb:1-1 transport_id:3\n")
    assert checks.android(fake_adb)["state"] == "unauthorized"


def test_ready_with_backup_age(fake_adb, monkeypatch):
    monkeypatch.setenv("FAKE_DEVICES", "ZY22 device usb:1-1 product:x model:motorola_edge_40_neo device:y\n")
    result = checks.android(fake_adb)
    assert result["state"] == "ready"
    assert result["model"] == "motorola edge 40 neo"
    assert result["backup"] == "ok" and result["backup_age_s"] == 3600


def test_old_backup_format(fake_adb, monkeypatch):
    monkeypatch.setenv("FAKE_DEVICES", "ZY22 device model:x\n")
    monkeypatch.setenv("FAKE_LS", "msgstore.db.crypt14")
    assert checks.android(fake_adb)["backup"] == "old_format"


def test_iphone_untrusted(monkeypatch):
    def refuse(udid=None):
        raise device.DeviceError("the iPhone does not trust this Mac yet: unlock it and tap Trust")
    monkeypatch.setattr(device, "phone", refuse)
    assert checks.iphone()["state"] == "untrusted"


def test_iphone_ready_cleans_name(monkeypatch):
    phone = device.Phone(udid="u", name="‏iPhone ⁨Abdullah⁩", ios="27.0.1",
                         encrypts_backups=False, used_bytes=14_200_000_000, find_my=False)
    monkeypatch.setattr(device, "phone", lambda udid=None: phone)
    result = checks.iphone()
    assert result["name"] == "iPhone Abdullah" and result["find_my"] is False


def test_download_platform_tools(tmp_path):
    source = tmp_path / "src" / "platform-tools"
    source.mkdir(parents=True)
    (source / "adb").write_text("#!/bin/sh\necho 'Android Debug Bridge version 1.0.41'\n")
    archive = tmp_path / "pt.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        info = zipfile.ZipInfo("platform-tools/adb")
        info.external_attr = 0o755 << 16
        zf.writestr(info, (source / "adb").read_text())
    seen = []
    support = tmp_path / "support"
    path = adbtool.download(support, lambda done, total: seen.append((done, total)), url=archive.as_uri())
    assert Path(path) == adbtool.bundled(support) and os.access(path, os.X_OK)
    assert seen[-1][0] == seen[-1][1] > 0
    assert adbtool.find(support) == path
