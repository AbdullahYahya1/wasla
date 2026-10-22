import sqlite3
import stat
import sys
import threading
from pathlib import Path

import pytest
from wamove.cli import Work

from conftest import KEY, make_crypt15
from wasla.engine import adbtool, android

ROOT = "Android/media/com.whatsapp/WhatsApp"


@pytest.fixture
def phone(tmp_path, monkeypatch):
    sdcard = tmp_path / "phone"
    wa = sdcard / ROOT
    (wa / "Databases").mkdir(parents=True)
    (wa / "Backups").mkdir()
    (wa / "Databases" / "msgstore.db.crypt15").write_bytes(make_crypt15(KEY, b"SQLite format 3\x00" + bytes(5000)))
    (wa / "Backups" / "wa.db.crypt15").write_bytes(make_crypt15(KEY, b"SQLite format 3\x00" + bytes(10)))
    for folder, count in (("WhatsApp Images", 6), ("WhatsApp Voice Notes", 3)):
        (wa / "Media" / folder).mkdir(parents=True)
        for i in range(count):
            (wa / "Media" / folder / f"f{i}.bin").write_bytes(bytes(40_000))
    script = tmp_path / "adb"
    script.write_text(f"#!/bin/sh\nexec {sys.executable} {Path(__file__).parent / 'fake_adb.py'} \"$@\"\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    adbtool.use(str(script))
    monkeypatch.setenv("FAKE_PHONE", str(sdcard))
    return wa


def test_sample_picks_smallest_file(phone, tmp_path):
    work = Work(tmp_path / "work")
    path = android.sample(work)
    assert path.name == "wa.db.crypt15"


def test_pull_reports_progress_to_100(phone, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_DELAY", "0.05")
    work = Work(tmp_path / "work")
    events = []
    result = android.pull(work, events.append, threading.Event())
    assert work.crypt15.is_file()
    assert len(list((work.media / "WhatsApp Images").iterdir())) == 6
    assert result["media_bytes"] > 0 and result["contacts"] == 1
    pcts = [e.pct for e in events if e.pct is not None]
    assert pcts == sorted(pcts) and pcts[-1] == 100
    assert {e.phase for e in events} >= {"chats", "media"}


def test_pull_can_be_cancelled(phone, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_DELAY", "0.5")
    cancel = threading.Event()
    work = Work(tmp_path / "work")

    def emit(event):
        if event.phase == "WhatsApp Images":
            cancel.set()
    threading.Timer(1.5, cancel.set).start()
    with pytest.raises(android.Cancelled):
        android.pull(work, emit, cancel)


def test_pull_refuses_without_space(phone, tmp_path, monkeypatch):
    monkeypatch.setattr(android.shutil, "disk_usage", lambda p: type("U", (), {"free": 10})())
    with pytest.raises(android.NotEnoughSpace):
        android.pull(Work(tmp_path / "work"), lambda e: None, threading.Event())


def test_summary_counts(tmp_path):
    work = Work(tmp_path / "work")
    work.android.mkdir(parents=True)
    conn = sqlite3.connect(work.msgstore)
    conn.executescript("""
        CREATE TABLE jid (_id INTEGER PRIMARY KEY, raw_string TEXT);
        CREATE TABLE chat (_id INTEGER PRIMARY KEY, jid_row_id INTEGER, subject TEXT, created_timestamp INTEGER,
                           archived INTEGER);
        CREATE TABLE message (_id INTEGER PRIMARY KEY, chat_row_id INTEGER, from_me INTEGER, key_id TEXT,
                              timestamp INTEGER, message_type INTEGER, text_data TEXT, sender_jid_row_id INTEGER,
                              starred INTEGER);
        INSERT INTO jid VALUES (1, '966500000000@s.whatsapp.net');
        INSERT INTO chat VALUES (1, 1, NULL, NULL, 0);
        INSERT INTO message VALUES (1, 1, 1, 'A', 1400000000000, 0, 'hi', 0, 0);
        INSERT INTO message VALUES (2, 1, 0, 'B', 1500000000000, 0, 'hello', 0, 0);
    """)
    conn.commit()
    conn.close()
    stats = android.summary(work)
    assert stats["chats"] == 1 and stats["messages"] == 2 and stats["sent"] == 1
    assert stats["first_ms"] == 1400000000000 and stats["last_ms"] == 1500000000000
