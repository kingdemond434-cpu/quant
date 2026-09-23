"""THE FENCE'S THREE TEETH, each pinned against the silence it exists to break.

Three fences already read this ledger and all three were green through 281.7 hours of it not
being written at all, so "another ledger check" is only worth its lines if it fails on things
they cannot see:

  * STALE   -- the ledger past its own cadence, graded only where the clock is supposed to run;
  * ORPHAN  -- an OPEN row with no owner and no next action, everywhere, always;
  * RATCHET -- the OPEN count above its floor with nothing recorded to explain the rise.

Every fixture is a tmp_path tree; `build_report(root)` takes the root for that reason.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_ROOT / "scripts"))

import check_recommendation_flow as F  # noqa: E402


def _write(root: Path, rows: list[dict[str, Any]], *, drained_h_ago: float = 0.0,
           ratchet: dict[str, Any] | None = None) -> None:
    p = root / "docs" / "research" / "recommendation_ledger.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    stamp = (datetime.now(tz=UTC) - timedelta(hours=drained_h_ago)).isoformat()
    for r in rows:
        r.setdefault("raised", stamp)
    p.write_text(json.dumps({"last_drain_at": stamp, "recommendations": rows}, indent=1,
                            ensure_ascii=False), "utf-8")
    if ratchet is not None:
        q = root / "desks" / "mt5" / "data" / "recommendation_ratchet.json"
        q.parent.mkdir(parents=True, exist_ok=True)
        q.write_text(json.dumps(ratchet), "utf-8")


def _open(rid: str, **kw: Any) -> dict[str, Any]:
    row = {"id": rid, "status": "open", "summary": "x", "owner": "MT5-Gauntlet",
           "next_action": "BT-1 -- do the thing"}
    row.update(kw)
    return row


def test_a_healthy_ledger_passes(tmp_path: Path) -> None:
    _write(tmp_path, [_open("R1")], ratchet={"floor": 1, "rises": []})
    rep = F.build_report(tmp_path, require_state=True)
    assert rep["status"] == "OK" and not rep["failures"]


def test_a_stale_ledger_fails_where_the_clock_is_supposed_to_run(tmp_path: Path) -> None:
    """THE 281.7-HOUR SILENCE. Nothing in the counts changes; only the clock says anything."""
    _write(tmp_path, [_open("R1")], drained_h_ago=281.7, ratchet={"floor": 1, "rises": []})
    rep = F.build_report(tmp_path, require_state=True)
    assert rep["status"] == "FAIL"
    assert any("stale" in f for f in rep["failures"])
    assert rep["ledger_stale_h"] > F.CADENCE_H


def test_staleness_is_reported_not_fatal_without_state(tmp_path: Path) -> None:
    """A fresh clone's ledger is as old as its last commit; failing there is crying wolf."""
    _write(tmp_path, [_open("R1")], drained_h_ago=281.7, ratchet={"floor": 1, "rises": []})
    rep = F.build_report(tmp_path, require_state=False)
    assert rep["failures"] == []
    assert any("stale" in u for u in rep["unmeasured"])


def test_an_open_row_with_no_owner_fails_everywhere(tmp_path: Path) -> None:
    _write(tmp_path, [_open("R1"), _open("R2", owner=None)], ratchet={"floor": 2, "rises": []})
    rep = F.build_report(tmp_path, require_state=False)
    assert rep["status"] == "FAIL"
    assert rep["n_open_without_owner"] == 1
    assert "R2" in rep["open_without_owner"]


def test_an_open_row_with_an_owner_but_no_next_action_still_fails(tmp_path: Path) -> None:
    """An owner with nothing to do is a name on a row, which is what backlog already had."""
    _write(tmp_path, [_open("R1", next_action="   ")], ratchet={"floor": 1, "rises": []})
    rep = F.build_report(tmp_path, require_state=False)
    assert rep["status"] == "FAIL" and rep["n_open_without_owner"] == 1


def test_the_open_ratchet_cannot_rise_without_a_recorded_reason(tmp_path: Path) -> None:
    _write(tmp_path, [_open(f"R{i}") for i in range(5)], ratchet={"floor": 2, "rises": []})
    rep = F.build_report(tmp_path, require_state=False)
    assert rep["status"] == "FAIL"
    assert any("ratchet floor" in f for f in rep["failures"])


def test_a_rise_with_a_recorded_reason_is_legal(tmp_path: Path) -> None:
    """Rows may ARRIVE. What may not happen is rows arriving with nobody noticing."""
    _write(tmp_path, [_open(f"R{i}") for i in range(5)],
           ratchet={"floor": 2, "rises": [{"at": "2026-09-23T00:00:00+00:00", "from": 2, "to": 5,
                                           "reason": "intake: 3 rows from the CEO docket"}]})
    rep = F.build_report(tmp_path, require_state=False)
    assert rep["status"] == "OK" and not rep["failures"]


def test_a_rise_recorded_with_an_empty_reason_is_not_a_reason(tmp_path: Path) -> None:
    _write(tmp_path, [_open(f"R{i}") for i in range(5)],
           ratchet={"floor": 2, "rises": [{"at": "x", "from": 2, "to": 5, "reason": "  "}]})
    rep = F.build_report(tmp_path, require_state=False)
    assert rep["status"] == "FAIL"


def test_an_unseeded_ratchet_is_unmeasured_not_a_pass_and_not_a_failure(tmp_path: Path) -> None:
    _write(tmp_path, [_open("R1")])
    rep = F.build_report(tmp_path, require_state=False)
    assert rep["failures"] == []
    assert any("ratchet" in u for u in rep["unmeasured"])


def test_an_unreadable_ledger_is_a_failure_never_an_empty_pass(tmp_path: Path) -> None:
    p = tmp_path / "docs" / "research" / "recommendation_ledger.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("<<<<<<< HEAD", "utf-8")
    rep = F.build_report(tmp_path, require_state=False)
    assert rep["status"] == "UNREADABLE" and rep["failures"]


def test_the_fence_is_wired_into_the_law_gate_both_ways() -> None:
    """UNWIRED OR IDLE IS A DEFECT (III.16) -- including for the fence that measures it."""
    src = (_ROOT / "scripts" / "run_law_gate.py").read_text("utf-8")
    assert '("check_recommendation_flow.py", ())' in src
    assert '("check_recommendation_flow.py", ("--require-state",))' in src
