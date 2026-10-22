# PyInstaller spec for Wasla.app. Build with: packaging/build.sh
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).parent
VERSION = "1.0.0"

datas = [(str(ROOT / "src" / "wasla" / "ui"), "wasla/ui")]
binaries = []
hiddenimports = collect_submodules("wamove") + collect_submodules("wasla")
for package in ("pymobiledevice3", "webview"):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [str(ROOT / "packaging" / "launch.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "numpy", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Wasla", console=False,
          argv_emulation=False, target_arch=None, codesign_identity=None, entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Wasla")
app = BUNDLE(
    coll,
    name="Wasla.app",
    icon=str(ROOT / "packaging" / "Wasla.icns"),
    bundle_identifier="com.kerneltics.wasla",
    version=VERSION,
    info_plist={
        "CFBundleDisplayName": "Wasla",
        "CFBundleName": "Wasla",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.utilities",
        "NSHumanReadableCopyright": "Free software under the GNU GPL v3. Built on wamove.",
        "CFBundleDevelopmentRegion": "en",
        "CFBundleLocalizations": ["en", "ar"],
    },
)
