"""Turn whatever went wrong into one of a few codes the window knows how to explain."""
from __future__ import annotations

from wamove.android import adb, crypt15, msgstore
from wamove.cli import Failure
from wamove.ios import backup as ios_backup
from wamove.ios import chatstorage, device

from .engine import android, build, iphone, keygrid

ADB_MESSAGES = (
    ("no Android phone found", "no_android"),
    ("accept the USB debugging prompt", "android_unauthorized"),
    ("adb not found", "no_adb"),
    ("older backup format", "old_backup_format"),
    ("no WhatsApp backup on the phone", "no_backup_on_android"),
    ("more than one Android device", "several_android"),
)
DISCONNECTED = ("ConnectionTerminated", "NoDeviceConnected", "ConnectionFailed", "DeviceNotFound",
                "MuxException", "BrokenPipe", "ConnectionReset", "ConnectionAbortedError")


def friendly(exc: BaseException) -> tuple[str, dict]:
    text = str(exc)
    if isinstance(exc, android.Cancelled):
        return "cancelled", {}
    if isinstance(exc, (android.NotEnoughSpace, iphone.NotEnoughSpace)):
        return "no_space", {"needed": exc.needed, "free": exc.free}
    if isinstance(exc, keygrid.KeyProblem):
        return exc.code, {}
    if isinstance(exc, adb.AdbError):
        for needle, code in ADB_MESSAGES:
            if needle in text:
                return code, {}
        return "android_copy_failed", {"detail": text[:300]}
    if isinstance(exc, crypt15.Crypt15Error):
        if "does not open" in text:
            return "key_wrong", {}
        if "64-digit" in text:
            return "key_format", {}
        return "android_backup_damaged", {"detail": text[:300]}
    if isinstance(exc, msgstore.MsgstoreError):
        return "android_whatsapp_old", {}
    if isinstance(exc, device.DeviceError):
        if "trust" in text:
            return "iphone_untrusted", {}
        if "no iPhone" in text:
            return "no_iphone", {}
        return "iphone_error", {"detail": text[:300]}
    if isinstance(exc, iphone.NothingToRestore):
        return "nothing_to_restore", {}
    if isinstance(exc, Failure):
        return "earlier_step_missing", {"detail": text[:300]}
    if isinstance(exc, iphone.FindMyOn):
        return "find_my_on", {}
    if isinstance(exc, iphone.PasswordNeeded):
        return "password_needed", {}
    if isinstance(exc, iphone.WhatsAppMissing):
        return "whatsapp_missing_on_iphone", {}
    if isinstance(exc, ios_backup.BackupError):
        if "password is wrong" in text:
            return "password_wrong", {}
        if "password is needed" in text:
            return "password_needed", {}
        return "iphone_backup_problem", {"detail": text[:300]}
    if isinstance(exc, (build.BuildFailed, chatstorage.ChatStorageError)):
        return "build_failed", {"detail": text[:300]}
    names = {cls.__name__ for cls in type(exc).__mro__}
    if any(any(marker in name for marker in DISCONNECTED) for name in names):
        return "iphone_disconnected", {}
    if isinstance(exc, OSError) and getattr(exc, "errno", None) == 28:
        return "no_space", {}
    return "unknown", {"detail": f"{type(exc).__name__}: {text}"[:300]}
