"""L1.28b conversion fence -- finding without fixing is half a deliverable.

The fence must (1) FLATLINE on a week of silence over a non-empty queue, (2) flag REPAIR-MODE
above the deep-sweep backpressure line, (3) treat a missing ledger as zero conversion (never OK),
(4) count a reasoned rejection as a conversion, and (5) stay wired: the law mapped in the
enforcement matrix, the artifact folded into the max-push queue, the manifest line present.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.check_conversion import REPAIR_MODE_BACKLOG, build_report

NOW = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)


def _write_ledger(root: Path, rows: list[dict]) -> None:
    p = root / "docs/research/recommendation_ledger.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"recommendations": rows}), "utf-8")


def _row(rid: str, status: str, raised_days_ago: float, *, disposed_days_ago: float | None = None,
         due: str | None = None) -> dict:
    return {
        "id": rid, "status": status,
        "raised": (NOW - timedelta(days=raised_days_ago)).isoformat(),
        "disposed": (None if disposed_days_ago is None
                     else (NOW - timedelta(days=disposed_days_ago)).isoformat()),
        "due": due,
    }


def test_flatline_on_week_of_silence_with_backlog(tmp_path):
    _write_ledger(tmp_path, [
        _row("R1", "open", 10.0),
        _row("R2", "scheduled", 9.0),
        _row("R3", "implemented", 20.0, disposed_days_ago=9.0),  # converted, but not this week
    ])
    rep = build_report(tmp_path, NOW)
    assert rep["status"] == "FLATLINE"
    assert rep["repair_mode"] is True
    assert rep["dispositions_7d"] == 0


def test_repair_mode_above_backpressure_line(tmp_path):
    rows = [_row(f"R{i}", "open", 3.0) for i in range(REPAIR_MODE_BACKLOG + 1)]
    rows.append(_row("RX", "implemented", 5.0, disposed_days_ago=1.0))
    _write_ledger(tmp_path, rows)
    rep = build_report(tmp_path, NOW)
    assert rep["status"] == "REPAIR-MODE"
    assert rep["repair_mode"] is True
    assert rep["backlog"] == REPAIR_MODE_BACKLOG + 1


def test_ok_when_flow_keeps_pace_and_backlog_small(tmp_path):
    _write_ledger(tmp_path, [
        _row("R1", "open", 2.0, due="2026-09-01"),
        _row("R2", "implemented", 6.0, disposed_days_ago=1.0),
    ])
    rep = build_report(tmp_path, NOW)
    assert rep["status"] == "OK"
    assert rep["repair_mode"] is False


def test_missing_ledger_is_flatline_never_ok(tmp_path):
    # L1.28b(e): unmeasured conversion counts as zero conversion.
    rep = build_report(tmp_path, NOW)
    assert rep["status"] == "FLATLINE"
    assert rep["repair_mode"] is True


def test_reasoned_rejection_counts_as_conversion(tmp_path):
    _write_ledger(tmp_path, [
        _row("R1", "open", 2.0),
        _row("R2", "rejected", 6.0, disposed_days_ago=2.0),
    ])
    rep = build_report(tmp_path, NOW)
    assert rep["dispositions_7d"] == 1
    assert rep["status"] == "OK"


def test_past_due_rows_named(tmp_path):
    _write_ledger(tmp_path, [
        _row("R1", "scheduled", 10.0, due="2026-07-01"),      # overdue
        _row("R2", "scheduled", 3.0, due="2026-12-01"),       # future deadline, not due
        _row("R3", "implemented", 5.0, disposed_days_ago=1.0),
    ])
    rep = build_report(tmp_path, NOW)
    assert rep["past_due"] == 1
    assert rep["past_due_ids"] == ["R1"]


def test_untriaged_open_row_past_grace_is_past_due(tmp_path):
    """The branch that was structurally dead in production.

    add() writes `status: open, due: None` and only `dispose --status scheduled` ever sets a due,
    so ZERO rows in the live ledger had status open AND a due date -- yet the fence required a
    non-null due to consider anything past due. 28 untriaged rows were invisible, and
    run_max_push.py:239 consumes this artifact, so the desk prioritised off the lenient count."""
    _write_ledger(tmp_path, [
        _row("R1", "open", 3.0),                              # no due -- 3d > 24h grace
        _row("R2", "open", 0.5),                              # inside grace, not yet a defect
        _row("R3", "implemented", 5.0, disposed_days_ago=1.0),
    ])
    rep = build_report(tmp_path, NOW)
    assert rep["past_due_orphaned"] == 1
    assert rep["past_due_ids"] == ["R1"]


def test_row_due_today_is_past_due_not_invisible(tmp_path):
    """`"2026-07-31" < "2026-07-31"` is False, so a scheduled row was invisible for the whole day
    it came due. Six live rows sat in that blind spot."""
    _write_ledger(tmp_path, [
        _row("R1", "scheduled", 2.0, due=NOW.date().isoformat()),
        _row("R2", "implemented", 5.0, disposed_days_ago=1.0),
    ])
    rep = build_report(tmp_path, NOW)                          # NOW is 12:00, due parses to 00:00
    assert rep["past_due_overdue"] == 1
    assert rep["past_due_ids"] == ["R1"]


def test_finished_rows_are_not_backlog_forever(tmp_path):
    """`done`/`screened` are written by organs that bypass the CLI. They are completed work;
    counting them as backlog inflated the debt permanently and never counted as dispositions."""
    _write_ledger(tmp_path, [
        _row("R1", "done", 3.0),
        _row("R2", "screened", 3.0),
        _row("R3", "open", 0.5),
    ])
    rep = build_report(tmp_path, NOW)
    assert rep["backlog"] == 1                    # only the genuinely open row
    assert rep["terminal_unstamped"] == 2         # ...and the missing stamps stay VISIBLE


def test_law_is_enforced_in_matrix():
    # The law must be mapped to its fence, or it is prose (L2.0).
    src = Path("scripts/build_enforcement_matrix.py").read_text("utf-8")
    assert '"L1.28b": ["scripts/check_conversion.py"]' in src


def test_artifact_feeds_max_push_queue():
    src = Path("scripts/run_max_push.py").read_text("utf-8")
    assert "data/conversion_status.json" in src
    assert "conversion_debt" in src
    assert "_from_conversion" in src


def test_manifest_schedules_the_fence():
    manifest = Path("ops/crontab.manifest").read_text("utf-8")
    assert "scripts/check_conversion.py" in manifest


def test_doctrine_carries_the_law():
    # Every organ inherits doctrine at spawn; the law must reach them, not just the constitution.
    doctrine = Path("ops/principal_doctrine.txt").read_text("utf-8")
    assert "L1.28b" in doctrine
    assert "CONVERSION PARITY" in doctrine


def test_real_repo_ledger_produces_valid_report():
    rep = build_report(Path("."))
    assert rep["status"] in ("OK", "REPAIR-MODE", "FLATLINE")
    if rep["backlog"] is not None and rep["backlog"] > REPAIR_MODE_BACKLOG:
        assert rep["repair_mode"] is True
