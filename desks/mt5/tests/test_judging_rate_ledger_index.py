"""The verdict rate reads only what was appended, and agrees with a full read.

Measured 2026-10-29: on the saturated box the full ledger stream overran its 150 s deadline after
483,328 rows, so JUDGING_RATE.json said UNMEASURED pass after pass. The index keeps the read
position, the cells already judged and the stamps the windows need.
"""
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for p in (DESK, DESK / "research", DESK.parents[1]):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import judging_throughput as jt  # noqa: E402

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
KEYS = ("status", "rows_total", "rows_unstamped", "last_verdict_at", "counts",
        "first_terminal_counts", "first_terminal_cells", "per_hour", "first_terminal_per_hour")


def _row(at: datetime, cell: str, passed: bool = False, gate: str = "deflated_sharpe") -> str:
    return json.dumps({"at": at.isoformat(timespec="seconds"), "cell": cell, "passed": passed,
                       "terminal_gate": gate, "downstream_status": "RULED"}) + "\n"


def _rows(n: int, start: datetime, step_h: float) -> list[str]:
    return [_row(start + timedelta(hours=i * step_h), f"C{i % 7}") for i in range(n)]


def _same(a: dict, b: dict) -> None:
    assert {k: a.get(k) for k in KEYS} == {k: b.get(k) for k in KEYS}


def test_the_index_agrees_with_a_full_read(tmp_path) -> None:
    led = tmp_path / "ledger.jsonl"
    led.write_text("".join(_rows(400, NOW - timedelta(days=10), 0.6)) + "not json\n\n",
                   encoding="utf-8")
    _same(jt._verdict_counts_indexed(NOW, led), jt._verdict_counts(NOW, led))


def test_a_second_pass_reads_only_the_appended_rows(tmp_path) -> None:
    led = tmp_path / "ledger.jsonl"
    led.write_text("".join(_rows(300, NOW - timedelta(days=9), 0.5)), encoding="utf-8")
    first = jt._verdict_counts_indexed(NOW - timedelta(hours=3), led)
    size0 = first["index"]["offset"]
    with led.open("a", encoding="utf-8") as fh:
        fh.write("".join(_row(NOW - timedelta(minutes=m), f"N{m}") for m in (90, 30, 5)))
    got = jt._verdict_counts_indexed(NOW, led)
    assert got["index"]["rebuilt"] is None and got["index"]["offset"] > size0
    _same(got, jt._verdict_counts(NOW, led))
    assert got["counts"]["1h"] == 2 and got["first_terminal_counts"]["1h"] == 2


def test_a_half_written_row_waits_for_its_newline(tmp_path) -> None:
    led = tmp_path / "ledger.jsonl"
    whole = _row(NOW - timedelta(minutes=10), "A")
    led.write_text(whole + whole[:20], encoding="utf-8")
    got = jt._verdict_counts_indexed(NOW, led)
    assert got["rows_total"] == 1 and got["index"]["offset"] == len(whole.encode())
    led.write_text(whole + _row(NOW - timedelta(minutes=5), "B"), encoding="utf-8")
    _same(jt._verdict_counts_indexed(NOW, led), jt._verdict_counts(NOW, led))


def test_an_overrun_keeps_its_progress_and_the_next_pass_finishes(tmp_path, monkeypatch) -> None:
    led = tmp_path / "ledger.jsonl"
    led.write_text("".join(_rows(20_000, NOW - timedelta(days=3), 0.003)), encoding="utf-8")
    monkeypatch.setattr(jt, "_DEADLINE_EVERY", 1000)
    ticks = iter(range(10**6))
    monkeypatch.setattr("time.monotonic", lambda: float(next(ticks)))
    cut = jt._verdict_counts_indexed(NOW, led, deadline_s=5.0)
    assert cut["status"] == jt.UNMEASURED and 0 < cut["index"]["offset"] < led.stat().st_size
    monkeypatch.undo()
    done = jt._verdict_counts_indexed(NOW, led, deadline_s=600.0)
    assert done["status"] == "MEASURED" and done["index"]["rebuilt"] is None
    _same(done, jt._verdict_counts(NOW, led))


def test_a_rewritten_ledger_rebuilds_the_index(tmp_path) -> None:
    led = tmp_path / "ledger.jsonl"
    led.write_text("".join(_rows(50, NOW - timedelta(days=2), 0.5)), encoding="utf-8")
    jt._verdict_counts_indexed(NOW, led)
    led.write_text("".join(_rows(5, NOW - timedelta(hours=5), 0.5)), encoding="utf-8")
    got = jt._verdict_counts_indexed(NOW, led)
    assert got["index"]["rebuilt"] in ("ledger head changed", "ledger shrank")
    _same(got, jt._verdict_counts(NOW, led))


def test_an_extra_cut_older_than_the_kept_rows_rebuilds(tmp_path) -> None:
    led = tmp_path / "ledger.jsonl"
    led.write_text("".join(_rows(200, NOW - timedelta(days=20), 2.0)), encoding="utf-8")
    jt._verdict_counts_indexed(NOW, led)
    cuts = {"regime": (NOW - timedelta(days=15)).isoformat()}
    got = jt._verdict_counts_indexed(NOW, led, extra_cuts=cuts)
    assert got["index"]["rebuilt"] == "a cut predates the rows the index kept"
    _same(got, jt._verdict_counts(NOW, led, extra_cuts=cuts))


def test_a_test_ledger_never_shares_the_box_index(tmp_path) -> None:
    led = tmp_path / "ledger.jsonl"
    led.write_text(_row(NOW - timedelta(minutes=1), "A"), encoding="utf-8")
    jt._verdict_counts_indexed(NOW, led)
    assert (tmp_path / "ledger.jsonl.rate_index.json").exists()
    assert jt.LEDGER_INDEX.parent.name == "data"


# ------------------------------------------------- audit HOLD of 6fd8ac95f (MF1, S1, S2, S3)

def test_a_row_appended_during_the_pass_is_read_by_the_next_one_as_first(tmp_path) -> None:
    led = tmp_path / "ledger.jsonl"
    led.write_text("".join(_rows(50, NOW - timedelta(days=2), 0.5)), encoding="utf-8")
    with led.open("a", encoding="utf-8") as fh:
        # Stamped after `now` by a judge appending while the pass reads, then an older row.
        fh.write(_row(NOW + timedelta(seconds=30), "LATE") + _row(NOW, "AFTER"))
    got = jt._verdict_counts_indexed(NOW, led)
    assert got["index"]["stopped_at_a_row_appended_this_pass"] is True
    later = NOW + timedelta(minutes=5)
    nxt = jt._verdict_counts_indexed(later, led)
    _same(nxt, jt._verdict_counts(later, led))
    assert nxt["first_terminal_counts"]["1h"] == 2       # LATE and AFTER, neither lost


def test_a_stamp_beyond_the_skew_bound_is_read_past(tmp_path) -> None:
    led = tmp_path / "ledger.jsonl"
    led.write_text(_row(NOW + timedelta(days=3), "SKEW") + _row(NOW - timedelta(minutes=5), "B"),
                   encoding="utf-8")
    got = jt._verdict_counts_indexed(NOW, led)
    assert got["index"]["offset"] == led.stat().st_size
    assert got["rows_unstamped"] == 1 and got["counts"]["1h"] == 1


def test_a_malformed_index_rebuilds_instead_of_staying_unmeasured(tmp_path) -> None:
    led = tmp_path / "ledger.jsonl"
    led.write_text("".join(_rows(30, NOW - timedelta(days=1), 0.5)), encoding="utf-8")
    jt._verdict_counts_indexed(NOW, led)
    ip = led.with_name(led.name + ".rate_index.json")
    for bad in ({"offset": "abc"}, {"first_cells": 5}, {"recent": [[1]]}):
        doc = json.loads(ip.read_text("utf-8"))
        doc.update(bad)
        ip.write_text(json.dumps(doc), "utf-8")
        got = jt._verdict_counts_indexed(NOW, led)
        assert got["status"] == "MEASURED", bad
        assert str(got["index"]["rebuilt"]).startswith("index unreadable"), bad
        _same(got, jt._verdict_counts(NOW, led))


def test_a_rewrite_that_keeps_the_head_is_caught(tmp_path) -> None:
    led = tmp_path / "ledger.jsonl"
    rows = _rows(200, NOW - timedelta(days=2), 0.2)
    led.write_text("".join(rows), encoding="utf-8")
    jt._verdict_counts_indexed(NOW, led)
    # Compacted: the same head, a different tail of the same length or longer.
    led.write_text("".join(rows[:100]) + "".join(
        _row(NOW - timedelta(minutes=m), f"Z{m}") for m in range(1, 101)), encoding="utf-8")
    got = jt._verdict_counts_indexed(NOW, led)
    assert got["index"]["rebuilt"] == "the bytes the index last read were rewritten"
    _same(got, jt._verdict_counts(NOW, led))


def test_the_index_stores_digests_as_one_blob(tmp_path) -> None:
    led = tmp_path / "ledger.jsonl"
    led.write_text("".join(_row(NOW - timedelta(minutes=i), f"K{i}") for i in range(500)),
                   encoding="utf-8")
    jt._verdict_counts_indexed(NOW, led)
    doc = json.loads(led.with_name(led.name + ".rate_index.json").read_text("utf-8"))
    assert doc["schema"] == 2 and isinstance(doc["first_cells"], str)
    assert len(jt._unpack_digests(doc["first_cells"])) == 500
    assert all(isinstance(a, int) for a, _ in doc["recent"])
