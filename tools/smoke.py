"""Open the real window hidden, check the UI talks to the engine, then quit. Exit 0 on success."""
import json
import sys
import tempfile
import threading
import time
from pathlib import Path

import webview

from wasla.app import UI
from wasla.bridge import Api, Paths

result = {}


def probe(window):
    for _ in range(100):
        time.sleep(0.2)
        try:
            title = window.evaluate_js("document.querySelector('h1') && document.querySelector('h1').textContent")
        except Exception:
            title = None
        if title:
            break
    result["h1"] = title
    result["stops"] = window.evaluate_js("document.querySelectorAll('.stop').length")
    result["lang"] = window.evaluate_js("document.documentElement.lang")
    window.evaluate_js("document.querySelector('[data-act=mark]').click()")
    time.sleep(1.5)
    result["after_start"] = window.evaluate_js("document.querySelector('h1').textContent")
    time.sleep(3)
    result["connect_rows"] = window.evaluate_js("document.querySelectorAll('.check').length")
    result["android_row"] = window.evaluate_js("document.querySelector('#ck-android .sub') && document.querySelector('#ck-android .sub').textContent")
    window.destroy()


with tempfile.TemporaryDirectory() as tmp:
    holder = {}
    api = Api(Paths(Path(tmp)), lambda e: holder["w"].evaluate_js(f"window.wasla && wasla.onEvent({e.to_json()})"))
    api.set_lang("en")
    window = webview.create_window("Wasla smoke", url=UI.as_uri(), js_api=api, hidden=True)
    holder["w"] = window
    webview.start(probe, window)
print(json.dumps(result, ensure_ascii=False))
sys.exit(0 if result.get("after_start") == "Plug in both phones" and result.get("stops") == 9 else 1)
