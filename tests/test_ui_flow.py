"""Click through all nine steps in demo mode with headless Chrome (skipped when Chrome is not installed)."""
import re
import subprocess
from pathlib import Path

import pytest

CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
UI = Path(__file__).parent.parent / "src" / "wasla" / "ui" / "index.html"


@pytest.mark.skipif(not CHROME.exists(), reason="needs Google Chrome")
@pytest.mark.parametrize("lang", ["en", "ar"])
def test_click_through_every_step(lang, tmp_path):
    out = subprocess.run([str(CHROME), "--headless=new", f"--user-data-dir={tmp_path}", "--virtual-time-budget=120000",
                          "--window-size=1080,740",  # the app window size, so the two-column layouts are used
                          "--dump-dom", f"{UI.as_uri()}?demo=1&autotest=1&lang={lang}"],
                         capture_output=True, text=True, timeout=180).stdout
    title = re.search(r"<title>([^<]*)</title>", out).group(1)
    assert title.startswith("AUTOTEST OK"), title
