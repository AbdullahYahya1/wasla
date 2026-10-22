import threading

import pytest
from PIL import Image
from wamove.model import Archive, Chat, Kind, Media, Message

from wasla.engine import build
from wasla.engine.android import Cancelled


def photo(path, size=(400, 300), color=(200, 30, 30)):
    Image.new("RGB", size, color).save(path, "JPEG")
    return path


def message(key, kind, path):
    return Message(key_id=key, from_me=False, timestamp_ms=1, kind=kind, media=Media(android_path=path))


def test_image_thumb_is_square_and_reports_original_size(tmp_path):
    source = photo(tmp_path / "a.jpg", (400, 300))
    target = tmp_path / "a.thumb"
    assert build.image_thumb(str(source), target) == (400, 300)
    with Image.open(target) as im:
        assert im.size == (72, 72) and im.format == "JPEG"


def test_image_thumb_unreadable_file(tmp_path):
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"not an image")
    assert build.image_thumb(str(bad), tmp_path / "bad.thumb") is None


def test_jobs_are_unique_per_file(tmp_path):
    media = tmp_path / "Media"
    (media / "WhatsApp Images").mkdir(parents=True)
    photo(media / "WhatsApp Images" / "IMG-1.jpg")
    chat = Chat(jid="1@s.whatsapp.net", messages=[
        message("a", Kind.IMAGE, "Media/WhatsApp Images/IMG-1.jpg"),
        message("b", Kind.IMAGE, "Media/WhatsApp Images/IMG-1.jpg"),
        message("c", Kind.VOICE, "Media/WhatsApp Voice Notes/PTT-1.opus"),
        message("d", Kind.IMAGE, "Media/WhatsApp Images/missing.jpg"),
    ])
    jobs = build.thumbnail_jobs(Archive(chats=[chat]), media)
    assert jobs == [(Kind.IMAGE, str(media / "WhatsApp Images" / "IMG-1.jpg"))]


def test_make_thumbnails_counts_and_caches(tmp_path):
    files = [str(photo(tmp_path / f"{i}.jpg")) for i in range(12)]
    seen = []
    cache = build.make_thumbnails([(Kind.IMAGE, f) for f in files], tmp_path / "cache", seen.append,
                                  threading.Event(), workers=4)
    assert sorted(seen) == list(range(1, 13))
    assert all(made.is_file() and size == (400, 300) for made, size in cache.values())


def test_make_thumbnails_can_be_cancelled(tmp_path):
    files = [str(photo(tmp_path / f"{i}.jpg")) for i in range(30)]
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(Cancelled):
        build.make_thumbnails([(Kind.IMAGE, f) for f in files], tmp_path / "cache", lambda n: None, cancel, 2)


def test_writer_uses_the_cache(tmp_path):
    made = tmp_path / "cached.thumb"
    made.write_bytes(b"jpeg")
    writer = build.ProgressWriter.__new__(build.ProgressWriter)
    writer.thumbnails = tmp_path / "thumbs"
    writer.thumbnails.mkdir()
    writer.cache = {"/m/a.jpg": (made, (10, 20)), "/m/b.mp4": (made, None), "/m/c.jpg": (None, None)}
    target, size = writer._thumbnail(Kind.IMAGE, "/m/a.jpg", "n1")
    assert target == writer.thumbnails / "n1.thumb" and target.read_bytes() == b"jpeg" and size == (10, 20)
    assert writer._thumbnail(Kind.VIDEO, "/m/b.mp4", "n2") == (writer.thumbnails / "n2.thumb", None)
    assert writer._thumbnail(Kind.IMAGE, "/m/c.jpg", "n3") is None


def test_estimate_has_every_phase():
    est = build.estimate(558855, 28444, 136642, 23_300_000_000, 10)
    assert list(est) == ["read", "thumbnails", "chats", "media", "check"]
    assert 20 < est["thumbnails"] < 40
