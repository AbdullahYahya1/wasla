#!/usr/bin/env python3
"""A pretend `adb` for tests: the phone's /sdcard is the folder in $FAKE_PHONE."""
import os
import shutil
import subprocess
import sys
import time

phone = os.environ.get("FAKE_PHONE", "/nonexistent")
args = sys.argv[1:]


def local(remote: str) -> str:
    return remote.replace("/sdcard", phone, 1)


if args[:1] == ["devices"]:
    print("List of devices attached")
    print(os.environ.get("FAKE_DEVICES", "ZY22 device usb:1 model:Fake_Phone device:x"))
elif args[:1] == ["pull"]:
    remote, target = args[-2], args[-1]
    source = local(remote)
    if not os.path.exists(source):
        print(f"adb: error: remote object '{remote}' does not exist", file=sys.stderr)
        sys.exit(1)
    dest = os.path.join(target, os.path.basename(source))
    if os.path.isdir(source):
        os.makedirs(dest, exist_ok=True)
        for name in sorted(os.listdir(source)):
            shutil.copy2(os.path.join(source, name), os.path.join(dest, name))
            time.sleep(float(os.environ.get("FAKE_DELAY", "0")))
    else:
        os.makedirs(target, exist_ok=True)
        shutil.copy2(source, dest)
elif args[:1] == ["shell"]:
    command = args[1]
    if command.startswith("content query"):
        print("Row: 0 display_name=Sara, data1=+966 50 000 0000")
    elif command.startswith("stat -c"):
        import glob
        import shlex
        paths = [p for p in shlex.split(command.split("2>")[0])[3:]]
        for pattern in paths:
            for path in sorted(glob.glob(local(pattern))):
                st = os.stat(path)
                if "%n" in command:
                    print(st.st_size, path.replace(phone, "/sdcard"))
                else:
                    print(int(st.st_mtime))
    else:
        command = command.replace("/sdcard", phone).replace("/storage/emulated/0", "/nonexistent")
        out = subprocess.run(["/bin/sh", "-c", command], capture_output=True, text=True)
        sys.stdout.write(out.stdout.replace(phone, "/sdcard"))
