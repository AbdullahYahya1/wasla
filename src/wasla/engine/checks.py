"""Live checks for the Connect and Get-ready steps. They only read; nothing on either phone changes."""
from __future__ import annotations

import asyncio
import re
import shutil
import time
from pathlib import Path

from wamove.android import adb
from wamove.ios import device

WHATSAPP = "net.whatsapp.WhatsApp"
WHATSAPP_BUSINESS = "net.whatsapp.WhatsAppSMB"


def android(adb_path: str | None) -> dict:
    if not adb_path:
        return {"state": "no_adb"}
    try:
        rows = [line.split() for line in adb.run("devices", "-l").splitlines()[1:] if line.strip()]
    except (adb.AdbError, OSError) as e:
        return {"state": "no_adb", "detail": str(e)}
    if not rows:
        return {"state": "missing"}
    ready = [row for row in rows if len(row) > 1 and row[1] == "device"]
    if not ready:
        status = rows[0][1] if len(rows[0]) > 1 else "unknown"
        return {"state": "unauthorized" if status == "unauthorized" else "offline", "status": status}
    if len(ready) > 1:
        return {"state": "several"}
    model = next((p.split(":", 1)[1] for p in ready[0] if p.startswith("model:")), ready[0][0])
    result = {"state": "ready", "model": model.replace("_", " ")}
    result.update(android_backup())
    return result


def android_backup() -> dict:
    """Where WhatsApp keeps its backup on the phone, and how old the newest one is."""
    try:
        root = adb.whatsapp_root()
    except adb.AdbError as e:
        text = str(e)
        return {"backup": "old_format" if "older backup format" in text else "none"}
    out = adb.shell(f'stat -c %Y "{root}/Databases/msgstore.db.crypt15" 2>/dev/null').strip()
    phone_now = adb.shell("date +%s").strip()
    stamp = int(out) if out.isdigit() else None
    now = int(phone_now) if phone_now.isdigit() else int(time.time())
    return {
        "backup": "ok",
        "root": root,
        "backup_time": stamp,
        "backup_age_s": now - stamp if stamp else None,
    }


async def _installed(lockdown) -> dict[str, bool]:
    from pymobiledevice3.services.installation_proxy import InstallationProxyService

    service = InstallationProxyService(lockdown=lockdown)
    try:
        apps = await service.get_apps(application_type="User", bundle_identifiers=[WHATSAPP, WHATSAPP_BUSINESS])
    finally:
        close = getattr(service, "close", None)
        if close:
            result = close()
            if asyncio.iscoroutine(result):
                await result
    return {WHATSAPP: WHATSAPP in apps, WHATSAPP_BUSINESS: WHATSAPP_BUSINESS in apps}


def whatsapp_installed(udid: str | None = None) -> dict[str, bool] | None:
    async def go():
        lockdown = await device._lockdown(udid)
        try:
            return await _installed(lockdown)
        finally:
            await lockdown.close()
    try:
        return asyncio.run(go())
    except Exception:
        return None


def iphone(with_apps: bool = False) -> dict:
    try:
        phone = device.phone()
    except device.DeviceError as e:
        text = str(e)
        return {"state": "untrusted" if "trust" in text else "missing"}
    except Exception as e:  # usbmuxd hiccups while the phone reboots
        return {"state": "missing", "detail": type(e).__name__}
    result = {
        "state": "ready",
        "udid": phone.udid,
        "name": _clean(phone.name),
        "ios": phone.ios,
        "used_bytes": phone.used_bytes,
        "find_my": phone.find_my,
        "encrypted": phone.encrypts_backups,
    }
    if with_apps:
        apps = whatsapp_installed(phone.udid)
        result["whatsapp"] = None if apps is None else apps[WHATSAPP]
        result["whatsapp_business"] = None if apps is None else apps[WHATSAPP_BUSINESS]
    return result


def disk(path: Path) -> dict:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return {"free_bytes": shutil.disk_usage(path).free}


def _clean(name: str) -> str:
    """Device names can carry invisible direction marks (‏⁨ … ⁩)."""
    return re.sub(r"[‎‏⁦-⁩‪-‮]", "", name or "").strip()
