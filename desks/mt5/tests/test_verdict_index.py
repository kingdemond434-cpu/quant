"""The verdict-rate read keeps an append-only index, so a pass reads only the new rows."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import judging_throughput as jt  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _row(cell: str, minutes_ago: float, gate: str = "PASSED") -> str:
    at = (NOW - timedelta(minutes=minutes_ago)).isoformat(timespec="seconds")
    return json.dumps({"cell": cell, "at": at, "terminal_gate": gate}) + "\n"


def _ledger(path: Path, rows: list[str]) -> Path:
    path.write_text("".join(rows), "utf-8")
    return path


def _strip(got: dict) -> dict:
    return {k: v for k, v in got.items() if k != "index"}


ROWS = ([_row(f"c{i}", 10 + i) for i in range(30)]
        + [_row("c3", 5), _row("c40", 3000), "not json but has no stamp\n", "\n",
           _row("c50", 20000), _row("future", -30)])


def test_an_indexed_read_equals_a_full_read(tmp_path: Path) -> None:
    led = _ledger(tmp_path / "ledger.jsonl", ROWS)
    full = jt._verdict_counts(NOW, led)
    first = jt._verdict_counts(NOW, led, index=tmp_path / "idx.npz")
    again = jt._verdict_counts(NOW, led, index=tmp_path / "idx.npz")
    assert full["status"] == first["status"] == again["status"] == "MEASURED"
    assert _strip(first) == _strip(full) == _strip(again)
    assert again["index"]["rows_read_this_pass"] == 0


def test_appended_rows_are_read_alone_and_counted_once(tmp_path: Path) -> None:
    led = _ledger(tmp_path / "ledger.jsonl", ROWS[:20])
    idx = tmp_path / "idx.npz"
    jt._verdict_counts(NOW, led, index=idx)
    with led.open("a", encoding="utf-8") as fh:
        fh.write("".join(ROWS[20:]))
    inc = jt._verdict_counts(NOW, led, index=idx)
    assert inc["index"]["rows_read_this_pass"] == len([r for r in ROWS[20:] if r.strip()])
    assert _strip(inc) == _strip(jt._verdict_counts(NOW, led))


def test_a_row_still_being_written_waits_for_its_newline(tmp_path: Path) -> None:
    led = _ledger(tmp_path / "ledger.jsonl", ROWS[:5])
    idx = tmp_path / "idx.npz"
    partial = _row("late", 1)
    with led.open("a", encoding="utf-8") as fh:
        fh.write(partial[:-10])
    jt._verdict_counts(NOW, led, index=idx)
    with led.open("a", encoding="utf-8") as fh:
        fh.write(partial[-10:])
    got = jt._verdict_counts(NOW, led, index=idx)
    assert got["counts"]["1h"] == 6
    assert _strip(got) == _strip(jt._verdict_counts(NOW, led))


def test_a_deadline_keeps_progress_and_the_next_pass_finishes(tmp_path: Path,
                                                              monkeypatch) -> None:
    led = _ledger(tmp_path / "ledger.jsonl", ROWS)
    idx = tmp_path / "idx.npz"
    monkeypatch.setattr(jt, "_DEADLINE_EVERY", 4)
    ticks = iter([0.0] + [0.0] * 3 + [10.0] * 1000)
    import time as _time
    monkeypatch.setattr(_time, "monotonic", lambda: next(ticks))
    cut = jt._verdict_counts(NOW, led, deadline_s=5.0, index=idx)
    assert cut["status"] == "UNMEASURED" and 0 < cut["index"]["offset"] < led.stat().st_size
    monkeypatch.undo()
    done = jt._verdict_counts(NOW, led, index=idx)
    assert done["index"]["resumed_from_byte"] == cut["index"]["offset"]
    assert _strip(done) == _strip(jt._verdict_counts(NOW, led))


def test_a_rewritten_ledger_discards_the_index(tmp_path: Path) -> None:
    led = _ledger(tmp_path / "ledger.jsonl", ROWS)
    idx = tmp_path / "idx.npz"
    jt._verdict_counts(NOW, led, index=idx)
    _ledger(led, [_row("x", 1)] + ROWS[1:])
    got = jt._verdict_counts(NOW, led, index=idx)
    assert got["index"]["reset"] and got["index"]["resumed_from_byte"] == 0
    assert _strip(got) == _strip(jt._verdict_counts(NOW, led))
    _ledger(led, ROWS[:3])
    shrunk = jt._verdict_counts(NOW, led, index=idx)
    assert "shrank" in shrunk["index"]["reset"]
    assert _strip(shrunk) == _strip(jt._verdict_counts(NOW, led))


def test_an_unreadable_index_falls_back_to_a_full_read(tmp_path: Path) -> None:
    led = _ledger(tmp_path / "ledger.jsonl", ROWS)
    idx = tmp_path / "idx.npz"
    idx.write_bytes(b"garbage")
    got = jt._verdict_counts(NOW, led, index=idx)
    assert "unreadable" in got["index"]["reset"]
    assert _strip(got) == _strip(jt._verdict_counts(NOW, led))
