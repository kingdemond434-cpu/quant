"""Bad-read streaks and keep-alive residents in process_health (Hourly pass, 2026-11-18).

The principal's rule: a job that fails or produces nothing three runs in a row is fixed that pass.
process_health now carries the streak itself, and a keep-alive trigger refused because its
resident is alive is not counted as a failure."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops"))
import process_health as ph  # noqa: E402


def _row(name: str, verdict: str, code: int | None = 0, resident: bool = False) -> dict[str, Any]:
    return {"name": name, "verdict": verdict, "last_result_code": code, "resident": resident}


def test_a_streak_counts_consecutive_bad_reads_and_resets_on_a_good_one() -> None:
    prev: dict[str, Any] | None = None
    for i, verdict in enumerate(["STALE", "FAILING", "NO_ARTIFACT"]):
        rows = [_row("MT5-X", verdict, 1)]
        ph.streaks(rows, prev, f"t{i}")
        prev = {"processes": rows}
    assert rows[0]["bad_reads"] == 3 and rows[0]["bad_since"] == "t0"
    rows = [_row("MT5-X", "OK")]
    ph.streaks(rows, prev, "t3")
    assert rows[0]["bad_reads"] == 0 and rows[0]["bad_since"] is None


def test_a_refused_keep_alive_is_its_resident_alive_not_a_failure() -> None:
    rows = [_row("MT5-Forest-China", "UNCONTRACTED", ph.REFUSED, resident=True),
            _row("MT5-MergeDocket", "UNCONTRACTED", ph.REFUSED, resident=False)]
    ph.streaks(rows, {"processes": [dict(r, bad_reads=2, bad_since="t0") for r in rows]}, "t3")
    assert rows[0]["bad_reads"] == 0
    assert rows[1]["bad_reads"] == 3 and rows[1]["bad_since"] == "t0"


def test_a_stale_resident_still_counts() -> None:
    rows = [_row("MT5-Forest-China", "STALE", ph.REFUSED, resident=True)]
    ph.streaks(rows, None, "t0")
    assert rows[0]["bad_reads"] == 1


def test_keep_alive_detection_reads_the_manifest_trigger() -> None:
    m = ph._manifest()
    assert m, "the box manifest must parse"
    keep = [n for n, a in m.items() if ph.is_resident(a.get("trigger", ""))]
    assert "MT5-Forest-China" in keep and "MT5-Dept-Data" in keep
    assert not ph.is_resident(m["MT5-AllocatorFast"]["trigger"])


def test_the_report_publishes_the_three_in_a_row_list(monkeypatch: Any, tmp_path: Path) -> None:
    rows = [{"TaskName": "\\MT5-AllocatorFast", "Scheduled Task State": "Enabled",
             "Status": "Ready", "Last Run Time": "now", "Next Run Time": "later",
             "Last Result": "1"}]
    monkeypatch.setattr(ph, "_tasks", lambda: (rows, "OK schtasks"))
    monkeypatch.setattr(ph, "_contracts", lambda: {})
    monkeypatch.setattr(ph, "_read_report", lambda: {"processes": [
        {"name": "MT5-AllocatorFast", "bad_reads": 2, "bad_since": "earlier"}]})
    doc = ph.build()
    row = next(r for r in doc["processes"] if r["name"] == "MT5-AllocatorFast")
    assert row["verdict"] == "FAILING" and row["bad_reads"] == 3
    assert doc["bad_3_in_a_row"] == ["MT5-AllocatorFast"]
