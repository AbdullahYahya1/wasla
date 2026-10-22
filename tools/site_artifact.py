"""Turn site/index.html into a claude.ai artifact page (no document wrapper, Google Fonts) for previewing."""
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
out = Path(sys.argv[1])
html = (ROOT / "site" / "index.html").read_text()
html = re.sub(r"<!doctype html>\s*|<html[^>]*>\s*|</html>\s*|<head>\s*|</head>\s*|<body>\s*|</body>\s*", "", html)
html = re.sub(r'<meta charset="utf-8">\s*|<meta name="viewport"[^>]*>\s*', "", html)
html = html.replace("<!--FONT-->", '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
                    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Readex+Pro:wght@300..700&display=swap">')
html = re.sub(r'@font-face \{ font-family: "Readex Pro"; src: url\("fonts/ReadexPro.ttf"\)[^}]*\}\n', "", html)
out.mkdir(parents=True, exist_ok=True)
(out / "index.html").write_text(html)
shutil.copytree(ROOT / "site" / "img", out / "img", dirs_exist_ok=True)
print(out / "index.html")
