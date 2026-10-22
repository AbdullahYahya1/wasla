"""Draw the Wasla app icon from the same SVG mark as the in-app logo, and build Wasla.icns.

The mark is a trip: a white origin dot, a dashed amber route, and an amber destination ring.
Chrome rasterizes the SVG so the icon matches the logo exactly.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

MARK = ('<path d="M7.5 19.5C8.5 5 23.5 5 24.5 18" fill="none" stroke="#FFB41F" stroke-width="2.4" '
        'stroke-linecap="round" stroke-dasharray="0.6 4.12 0.6 4.12 0.6 4.12 0.6 4.12 0.6 40" stroke-dashoffset="-4.8"/>'
        '<circle cx="7.5" cy="19.5" r="2.7" fill="#fff"/>'
        '<circle cx="24.5" cy="19.5" r="4.6" fill="#FFB41F"/>'
        '<circle cx="24.5" cy="19.5" r="1.9" fill="#1B2140"/>')

ICON = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">
<defs><filter id="s" x="-20%" y="-20%" width="140%" height="140%">
<feDropShadow dx="0" dy="14" stdDeviation="16" flood-color="#000" flood-opacity=".32"/></filter>
<linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#232B55"/><stop offset="1" stop-color="#171C38"/></linearGradient></defs>
<rect x="100" y="100" width="824" height="824" rx="185" fill="url(#g)" filter="url(#s)"/>
<g transform="translate(100 100) scale(25.75)">{MARK}</g></svg>"""


def render(svg: str, out: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "icon.html"
        page.write_text(f"<html><body style='margin:0;background:transparent'>{svg}</body></html>")
        subprocess.run([CHROME, "--headless=new", f"--user-data-dir={tmp}/p", "--hide-scrollbars",
                        "--default-background-color=00000000", "--window-size=1024,1024",
                        f"--screenshot={out}", page.as_uri()], capture_output=True, timeout=60, check=True)


def main(out_dir: Path = HERE) -> None:
    master_path = out_dir / "icon-1024.png"
    (out_dir / "icon.svg").write_text(ICON)
    render(ICON, master_path)
    master = Image.open(master_path).convert("RGBA")
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "Wasla.iconset"
        iconset.mkdir()
        for base in (16, 32, 128, 256, 512):
            master.resize((base, base), Image.LANCZOS).save(iconset / f"icon_{base}x{base}.png")
            master.resize((base * 2, base * 2), Image.LANCZOS).save(iconset / f"icon_{base}x{base}@2x.png")
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(out_dir / "Wasla.icns")], check=True)
    print(out_dir / "Wasla.icns")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE)
