import pytest

from wasla.engine.keygrid import KeyProblem, candidates, find_working_key, normalize


def grid_typed_left_to_right(key: str) -> str:
    """What someone types when the phone shows the grid right to left and they read it left to right."""
    groups = [key[i:i + 4] for i in range(0, 64, 4)]
    rows = [groups[i:i + 4] for i in range(0, 16, 4)]
    return "\n".join(" ".join(reversed(row)) for row in rows)


def test_normalize_strips_separators():
    assert normalize(" AB-cd:12\n34 ") == "abcd1234"


def test_candidates_reject_wrong_length():
    with pytest.raises(KeyProblem) as e:
        candidates("1234")
    assert e.value.code == "key_format"


def test_candidates_reject_non_hex():
    with pytest.raises(KeyProblem):
        candidates("z" * 64)


def test_candidates_are_unique():
    names = [n for n, _ in candidates("0" * 64)]
    assert names == ["as_typed"]


def test_key_typed_correctly(key_hex, crypt15_sample):
    name, key = find_working_key(key_hex, crypt15_sample)
    assert name == "as_typed" and key.hex() == key_hex


def test_key_from_arabic_grid_read_left_to_right(key_hex, crypt15_sample):
    name, key = find_working_key(grid_typed_left_to_right(key_hex), crypt15_sample)
    assert name == "rows_rtl" and key.hex() == key_hex


def test_wrong_key(crypt15_sample):
    with pytest.raises(KeyProblem) as e:
        find_working_key("1" * 64, crypt15_sample)
    assert e.value.code == "key_wrong"


def test_arabic_grid_typed_left_to_right():
    """A grid as an Arabic phone shows it (each row right to left), typed left to right."""
    typed = "5d68 b2e4 9c07 3f1a 8a63 4f2d e19b a0c7 2a6c d84f 7b19 c5e0 8f41 5a2c b07d 1e93"
    rtl = dict(candidates(typed))["rows_rtl"]
    assert rtl == "3f1a9c07b2e45d68a0c7e19b4f2d8a63c5e07b19d84f2a6c1e93b07d5a2c8f41"
