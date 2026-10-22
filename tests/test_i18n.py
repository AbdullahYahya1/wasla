import json
import re
from pathlib import Path

UI = Path(__file__).parent.parent / "src" / "wasla" / "ui"
STEPS = ["welcome", "connect", "key", "copy", "ready", "backup", "prepare", "restore", "finish"]


def strings(lang):
    text = (UI / "strings" / f"{lang}.js").read_text()
    body = text[text.index("= {") + 2:].rstrip().rstrip(";")
    return json.loads(body)


def test_both_languages_have_the_same_keys():
    en, ar = strings("en"), strings("ar")
    assert en.keys() == ar.keys()
    assert all(v.strip() for v in en.values()) and all(v.strip() for v in ar.values())


def test_placeholders_match():
    en, ar = strings("en"), strings("ar")
    for key in en:
        assert set(re.findall(r"{\w+}", en[key])) == set(re.findall(r"{\w+}", ar[key])), key


def test_every_literal_key_in_the_ui_exists():
    en = strings("en")
    js = (UI / "app.js").read_text()
    used = set(re.findall(r'\bt\("([a-z_]+\.[a-z0-9_]+)"', js)) | set(re.findall(r'"((?:[a-z]+)\.[a-z0-9_]+)"\]', js))
    used |= set(re.findall(r'\[\s*"([a-z]+\.[a-z0-9_]+)"', js))
    missing = sorted(k for k in used if k not in en and not k.endswith("_"))  # "x_" + name is checked below
    assert not missing, missing


def test_dynamic_keys_exist():
    en = strings("en")
    for step in STEPS:
        assert f"steps.{step}" in en and f"{step}.title" in en
    for folder in ("images", "video", "voice", "audio", "documents", "gifs", "stickers", "videonotes"):
        assert f"copy.f_{folder}" in en
    for phase in ("read", "thumbnails", "chats", "media", "check"):
        assert f"prepare.p_{phase}" in en


def test_every_error_code_has_a_message():
    en = strings("en")
    source = (Path(__file__).parent.parent / "src" / "wasla" / "errors.py").read_text()
    codes = set(re.findall(r'return "([a-z_]+)"', source)) | set(re.findall(r'"([a-z_]+)"\),', source))
    codes |= {"key_missing", "key_format", "key_wrong"}
    missing = sorted(c for c in codes if f"error.{c}" not in en)
    assert not missing, missing
