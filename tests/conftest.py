import os
import zlib

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from wamove.android.crypt15 import derive_aes_key

KEY = "3f1a9c07b2e45d68a0c7e19b4f2d8a63c5e07b19d84f2a6c1e93b07d5a2c8f41"


def make_crypt15(key_hex: str, plain: bytes) -> bytes:
    """A file in WhatsApp's .crypt15 layout: varint header length, protobuf header with the IV, AES-GCM body."""
    iv = os.urandom(16)
    header = b"\x0a\x10" + iv
    body = AESGCM(derive_aes_key(bytes.fromhex(key_hex))).encrypt(iv, plain, None)
    return bytes([len(header)]) + header + body


@pytest.fixture
def key_hex():
    return KEY


@pytest.fixture
def crypt15_sample(tmp_path):
    path = tmp_path / "wa.db.crypt15"
    path.write_bytes(make_crypt15(KEY, zlib.compress(b"SQLite format 3\x00" + b"\x00" * 200)))
    return path
