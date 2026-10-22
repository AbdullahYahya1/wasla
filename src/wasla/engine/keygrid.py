"""The 64-digit key: clean it up, and find the reading order that opens the backup.

WhatsApp shows the key as a grid of 16 groups, 4 per row. On a phone set to Arabic the grid is laid out
right to left, so people who read it left to right type each row backwards. We try the likely orders
against a small encrypted file from the phone and keep the one that opens it.
"""
from __future__ import annotations

import re
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from wamove.android.crypt15 import Crypt15Error, _header, derive_aes_key


class KeyProblem(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def normalize(text: str) -> str:
    return re.sub(r"[\s\-:_.,|]", "", text or "").lower()


def candidates(text: str) -> list[tuple[str, str]]:
    key = normalize(text)
    if not re.fullmatch(r"[0-9a-f]{64}", key):
        raise KeyProblem("key_format")
    groups = [key[i:i + 4] for i in range(0, 64, 4)]
    rows = [groups[i:i + 4] for i in range(0, 16, 4)]
    orders = {
        "as_typed": groups,
        "rows_rtl": [g for row in rows for g in reversed(row)],
        "columns": [rows[r][c] for c in range(4) for r in range(4)],
        "reversed": list(reversed(groups)),
    }
    found: dict[str, str] = {}
    for name, order in orders.items():
        found.setdefault("".join(order), name)
    return [(name, value) for value, name in found.items()]


def opens(data: bytes, key: bytes) -> bool:
    """True when the AES-GCM tag checks out, which only happens with the right key."""
    try:
        offset, ivs = _header(data)
    except Crypt15Error:
        return False
    body = data[offset:]
    gcm = AESGCM(derive_aes_key(key))
    for iv in ivs:
        for trailer in (0, 16):
            try:
                gcm.decrypt(iv, body[:len(body) - trailer], None)
                return True
            except InvalidTag:
                continue
    return False


def find_working_key(text: str, sample: Path) -> tuple[str, bytes]:
    data = sample.read_bytes()
    for name, value in candidates(text):
        key = bytes.fromhex(value)
        if opens(data, key):
            return name, key
    raise KeyProblem("key_wrong")
