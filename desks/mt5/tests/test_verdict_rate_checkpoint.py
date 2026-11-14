"""THE VERDICT-RATE STREAM RESUMES, AND COUNTS EXACTLY WHAT A FULL READ COUNTS (2026-11-14).

On the box the gate ledger had outgrown its 150 s read: every pass overran after ~1.24 M of
~1.64 M rows, so verdicts/hour and the drain ETA read UNMEASURED. `_verdict_counts` now reads
the writer's own rows without a JSON parse and keeps a checkpoint so a pass reads only the tail,
and a pass that runs out of time keeps its progress. These tests pin the counts to a full
stream's, row for row, across every way the checkpoint can be wrong.
"""
from __future__ import annotations

import json
import random
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import judging_throughput as jt  # noqa: E402

NOW = datetime(2026, 11, 14, 0, 42, 43, 500000, tzinfo=UTC)
CUTS = {"regime": "2026-11-12T03:00:00+00:00"}
VOLATILE = ("resumed_from_row", "checkpoint")


def _writer_row(at: str, cell: str, gate: str, passed: bool = False,
                status: str | None = None, family: str | None = "carry") -> dict:
    """The exact layout `external_gauntlet._append_gate_ledger` writes."""
    row = {"at": at, "cell": cell, "graph_id": "", "sym": "EURUSD", "family": family,
           "passed": passed, "terminal_gate": gate, "downstream_status": status}
    if gate == "UNKNOWN":
        row.update({"unknown_reason": "too_rare", "failed_gates": [], "days": 3})
    return row


def _ledger(n: int = 4000, seed: int = 11) -> bytes:
    rnd = random.Random(seed)
    lines: list[str] = []
    # The writer stamps each append batch with one `now`: a few hundred distinct seconds.
    batches = sorted(rnd.randint(-120, 9 * 86400) for _ in range(300))
    for i in range(n):
        at = (NOW - timedelta(seconds=batches[i * len(batches) // n])).isoformat(
            timespec="seconds")
        cell = f"fam{rnd.randint(0, 9)}|SYM{rnd.randint(0, 40)}|{rnd.randint(0, n // 3)}"
        row = _writer_row(at, cell, rnd.choice(["UNKNOWN", "dsr", "oos", "", "cost"]),
                          passed=rnd.random() < 0.05,
                          status=rnd.choice([None, None, "NOT_RUN: data", "ok"]),
                          family=rnd.choice([None, "carry", 'we"ird']))
        r = rnd.random()
        if r < 0.03:
            row["at"] = at.replace("+00:00", "Z")                     # another stamp form
        elif r < 0.05:
            row["cell"] = cell + "\\esc"                               # an escaped name
        elif r < 0.07:
            row = {"cell": row.pop("cell"), **row}                     # another key order
        elif r < 0.08:
            row["passed"] = 1                                          # a non-bool
        lines.append(json.dumps(row))
        if r > 0.995:
            lines.append("not json " + at)                             # a torn row
        if r > 0.99:
            lines.append("")                                           # a blank line
    return ("\n".join(lines) + "\n").encode("utf-8")


def _strip(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k not in VOLATILE}


def _slow(monkeypatch: pytest.MonkeyPatch, path: Path) -> dict:
    """The original stream: no fast path, no checkpoint."""
    with monkeypatch.context() as m:
        m.setattr(jt, "_FAST_ROW", re.compile(r"(?!)"))
        return jt._verdict_counts(NOW, path, extra_cuts=CUTS)


def test_the_fast_path_counts_exactly_what_the_json_parse_counts(tmp_path, monkeypatch):
    led = tmp_path / "gate_verdict_ledger.jsonl"
    led.write_bytes(_ledger())
    fast = jt._verdict_counts(NOW, led, extra_cuts=CUTS)
    slow = _slow(monkeypatch, led)
    assert fast == slow and fast["status"] == "MEASURED"
    assert fast["first_terminal_counts"]["7d"] > 0 and fast["rows_unstamped"] > 0


def test_the_writers_own_row_takes_the_fast_path_and_nothing_else_does():
    row = json.dumps(_writer_row("2026-11-13T10:00:00+00:00", "c|1", "dsr")) + "\n"
    assert jt._FAST_ROW.match(row)
    for other in (row.replace("+00:00", "Z"), row.replace('"c|1"', '"c\\\\1"'),
                  row.replace('"passed": false', '"passed": 0'),
                  row.replace("10:00:00+00:00", "10:00:00.5+00:00"),
                  json.dumps({"cell": "c|1", "at": "2026-11-13T10:00:00+00:00"})):
        assert not jt._FAST_ROW.match(other)


def test_a_growing_ledger_read_through_its_checkpoint_counts_as_a_full_read(tmp_path,
                                                                            monkeypatch):
    data = _ledger()
    led, ck = tmp_path / "gate_verdict_ledger.jsonl", tmp_path / "ck.json"
    # Grow it in uneven steps, one of them ending mid-line (a writer caught mid-append).
    for cut in (len(data) // 5, len(data) // 5 + 17, len(data) // 2, len(data)):
        led.write_bytes(data[:cut])
        got = jt._verdict_counts(NOW, led, extra_cuts=CUTS, checkpoint=ck)
        assert _strip(got) == _slow(monkeypatch, led)
        assert got["checkpoint"] == "saved"
    again = jt._verdict_counts(NOW, led, extra_cuts=CUTS, checkpoint=ck)
    assert again["resumed_from_row"] == again["rows_total"]       # nothing left to read
    assert _strip(again) == _slow(monkeypatch, led)


def test_an_overrun_keeps_its_progress_and_the_next_pass_resumes(tmp_path, monkeypatch):
    led, ck = tmp_path / "gate_verdict_ledger.jsonl", tmp_path / "ck.json"
    led.write_bytes(_ledger(n=30_000))
    monkeypatch.setattr(jt, "_DEADLINE_EVERY", 1000)
    clock = iter(range(10**6))
    monkeypatch.setattr("time.monotonic", lambda: float(next(clock)))
    # Every deadline check reads a later tick than the last, so each pass stops at its first
    # check after the first block of rows: the stream advances 1000 rows a pass.
    passes, got = 0, {"status": jt.UNMEASURED}
    while got["status"] != "MEASURED":
        got = jt._verdict_counts(NOW, led, extra_cuts=CUTS, checkpoint=ck, deadline_s=0.5)
        passes += 1
        if got["status"] != "MEASURED":
            assert "never a partial count" in got["why"]
            assert got["checkpoint"].startswith("saved at row")
        assert passes < 100
    monkeypatch.undo()
    assert passes > 3
    assert _strip(got) == _slow(monkeypatch, led)


def test_a_future_stamp_is_reread_once_its_time_has_come(tmp_path, monkeypatch):
    led, ck = tmp_path / "gate_verdict_ledger.jsonl", tmp_path / "ck.json"
    early = (NOW - timedelta(hours=2)).isoformat(timespec="seconds")
    soon = (NOW + timedelta(minutes=5)).isoformat(timespec="seconds")
    led.write_text("".join(json.dumps(r) + "\n" for r in (
        _writer_row(early, "a", "dsr"), _writer_row(soon, "b", "dsr"),
        _writer_row(early, "b", "oos"))), "utf-8")
    first = jt._verdict_counts(NOW, led, checkpoint=ck)
    assert first["rows_unstamped"] == 1 and first["first_terminal_counts"]["24h"] == 2
    later = NOW + timedelta(minutes=10)
    resumed = jt._verdict_counts(later, led, checkpoint=ck)
    assert resumed["resumed_from_row"] == 1                          # it re-read the future row
    assert _strip(resumed) == jt._verdict_counts(later, led)


@pytest.mark.parametrize("damage", ["rewritten", "shrunk", "cells_short", "schema", "torn"])
def test_a_checkpoint_that_no_longer_describes_the_ledger_is_discarded(tmp_path, monkeypatch,
                                                                       damage):
    data = _ledger()
    led, ck = tmp_path / "gate_verdict_ledger.jsonl", tmp_path / "ck.json"
    led.write_bytes(data)
    jt._verdict_counts(NOW, led, extra_cuts=CUTS, checkpoint=ck)
    if damage == "rewritten":
        led.write_bytes(b"\n" + data)
    elif damage == "shrunk":
        led.write_bytes(data[: len(data) // 3])
    elif damage == "cells_short":
        cells = ck.with_suffix(".cells")
        cells.write_bytes(cells.read_bytes()[:-1])
    elif damage == "schema":
        doc = json.loads(ck.read_text("utf-8"))
        ck.write_text(json.dumps({**doc, "schema": "other/9"}), "utf-8")
    else:
        ck.write_text("{not json", "utf-8")
    got = jt._verdict_counts(NOW, led, extra_cuts=CUTS, checkpoint=ck)
    assert got["resumed_from_row"] == 0
    assert _strip(got) == _slow(monkeypatch, led)


def test_the_desks_own_ledger_keeps_its_checkpoint_beside_it(tmp_path, monkeypatch):
    led = tmp_path / "gate_verdict_ledger.jsonl"
    led.write_bytes(_ledger(n=500))
    monkeypatch.setattr(jt, "GATE_LEDGER", led)
    jt._verdict_counts(NOW)
    assert (tmp_path / jt.VERDICT_CKPT_NAME).exists()
    assert (tmp_path / jt.VERDICT_CKPT_NAME).with_suffix(".cells").exists()
    explicit = tmp_path / "other.jsonl"
    explicit.write_bytes(_ledger(n=50))
    assert "checkpoint" not in jt._verdict_counts(NOW, explicit)    # an explicit path keeps none


def test_an_unwritable_checkpoint_never_costs_the_count(tmp_path, monkeypatch):
    led = tmp_path / "gate_verdict_ledger.jsonl"
    led.write_bytes(_ledger(n=500))
    ck = tmp_path / "no_such_dir" / "ck.json"
    got = jt._verdict_counts(NOW, led, extra_cuts=CUTS, checkpoint=ck)
    assert got["status"] == "MEASURED" and got["checkpoint"].startswith("not saved (")
    assert _strip(got) == _slow(monkeypatch, led)
