import json

from wasla.events import Emitter, Event
from wasla.progress import Rate
from wasla.state import State


def test_rate_percent_and_eta():
    rate = Rate(1000, warmup_s=0)
    assert rate.update(0, now=0) == (0.0, None)
    for t in range(1, 6):
        pct, eta = rate.update(100 * t, now=t)
    assert pct == 50.0
    assert abs(eta - 5.0) < 0.01


def test_rate_waits_before_guessing():
    rate = Rate(100, warmup_s=10)
    rate.update(0, now=0)
    for t in range(1, 5):
        _, eta = rate.update(t, now=t)
    assert eta is None


def test_rate_clamps_and_handles_zero_total():
    assert Rate(10).update(50, now=0)[0] == 100.0
    assert Rate(0).update(5, now=0)[0] == 0.0


def test_emitter_throttles_progress_but_not_other_events():
    seen = []
    clock = iter([0.0, 0.05, 0.2, 0.21])
    emit = Emitter(seen.append, min_interval=0.12, clock=lambda: next(clock))
    emit(Event("copy", "progress", pct=1))
    emit(Event("copy", "progress", pct=2))
    emit(Event("copy", "progress", pct=3))
    emit(Event("copy", "progress", pct=4))
    emit(Event("copy", "progress", pct=100))
    emit(Event("copy", "done"))
    assert [e.pct for e in seen if e.kind == "progress"] == [1, 3, 100]
    assert seen[-1].kind == "done"


def test_event_json_keeps_arabic():
    assert "نسخ" in Event("copy", "log", data={"text": "نسخ"}).to_json()


def test_state_round_trip_and_reset(tmp_path):
    path = tmp_path / "state.json"
    state = State(path).load()
    assert state.current() == "welcome"
    for step in ("welcome", "connect", "key", "copy"):
        state.mark(step, n=1)
    again = State(path).load()
    assert again.done("copy") and again.get("copy")["n"] == 1
    assert again.current() == "ready"
    again.reset_from("key")
    assert not again.done("key") and not again.done("copy") and again.done("connect")
    assert not list(tmp_path.glob("*.tmp"))
    assert json.loads(path.read_text())["steps"].keys() == {"welcome", "connect"}


def test_state_survives_bad_file(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{oops")
    assert State(path).load().current() == "welcome"


def test_phases_weighted_overall():
    from wasla.progress import Phases
    phases = Phases({"a": 10, "b": 30, "c": 60})
    assert phases.overall("a", 0) == 0
    assert phases.overall("a", 1) == 10
    assert phases.overall("b", 0.5) == 25
    assert phases.overall("c", 1) == 100
    assert phases.overall("c", 2) == 100
