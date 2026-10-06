"""The build-failure bank records every swallowed build failure by cause, never raises, and an
empty window reads UNMEASURED (zero failures is not the reading when nothing recorded a pass)."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import build_failure_bank as bfb  # noqa: E402


def test_classify_exception_and_why() -> None:
    assert bfb.classify_exception(FileNotFoundError("x.parquet")) == "MISSING_DATA"
    assert bfb.classify_exception(ValueError("bad spec")) == "COMPILE_ERROR"
    assert bfb.classify_why("", "NOT_RUN_DATA_MISSING") == "MISSING_DATA"
    assert bfb.classify_why("", "NOT_RUN_MODIFIER") == "MODIFIER_REFUSED"
    assert bfb.classify_why("no implementation of family foo") == "UNKNOWN_FAMILY"
    assert bfb.classify_why("too few signals") == "INSUFFICIENT_SIGNALS"
    assert bfb.classify_why("something else") == "OTHER"


def test_bank_records_flushes_and_never_raises(tmp_path: Path) -> None:
    led = tmp_path / "bf.jsonl"
    b = bfb.Bank("stage_a", ledger=led)
    assert b.flush() is None                                  # nothing attempted: no row
    b.attempt(10)
    b.record("unknown_symbol", "XYZ absent", symbol="XYZ", family="orb")
    b.record("MISSING_DATA", "no bars", symbol=object(), family="orb")   # odd ident is stringified
    row = b.flush()
    assert row is not None and row["failed"] == 2 and row["attempted"] == 10
    assert row["by_cause"] == {"UNKNOWN_SYMBOL": 1, "MISSING_DATA": 1}
    assert len(led.read_text("utf-8").splitlines()) == 1
    clean = bfb.Bank("stage_b", ledger=led)
    clean.attempt(5)
    assert clean.flush()["failed"] == 0                       # zero over N is written too


def test_aggregate_ranks_fix_work_and_empty_is_unmeasured(tmp_path: Path) -> None:
    assert bfb.aggregate([], 24.0)["status"] == bfb.UNMEASURED
    led = tmp_path / "bf.jsonl"
    b = bfb.Bank("s", ledger=led)
    b.attempt(4)
    for _ in range(3):
        b.record("UNKNOWN_FAMILY", family="f1")
    b.record("COMPILE_ERROR", family="f2")
    b.flush()
    doc = bfb.build(24.0, ledger=led, gauntlet=tmp_path / "absent.json")
    assert doc["status"] == "MEASURED"
    assert doc["top_cause"] == "UNKNOWN_FAMILY"
    assert [w["rank"] for w in doc["fix_work"]] == [1, 2]
    assert doc["fix_work"][0]["owner"]
    assert doc["stages"]["s"]["failure_rate"] == 1.0


def test_old_rows_fall_outside_the_window(tmp_path: Path) -> None:
    led = tmp_path / "bf.jsonl"
    old = (datetime.now(tz=UTC) - timedelta(hours=48)).isoformat()
    led.write_text(json.dumps({"stage": "s", "at": old, "attempted": 1, "failed": 1,
                               "by_cause": {"OTHER": 1}}) + "\n", "utf-8")
    assert bfb.build(24.0, ledger=led, gauntlet=tmp_path / "x.json")["status"] == bfb.UNMEASURED


def test_main_writes_artifact(tmp_path: Path) -> None:
    out = tmp_path / "BUILD_FAILURE_BANK.json"
    assert bfb.main(["--once", "--out", str(out)]) == 0
    assert json.loads(out.read_text("utf-8"))["schema"] == bfb.SCHEMA
