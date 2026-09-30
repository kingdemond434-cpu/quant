"""The cert-to-forward meter reads the clocks, and a silent engine is loud."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import forward_enrolment as fe  # noqa: E402
import research_productivity as rp  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _run() -> dict:
    return {"symbol": "EURUSD", "family": "session_range_breakout", "selector": "asia",
            "side": "LONG", "params": {"rr": 2.0}}


def test_active_clock_with_an_old_tick_is_engine_silent() -> None:
    run = _run()
    key = fe._run_key(run)
    old = (NOW - timedelta(days=7)).isoformat()
    body = fe.census([run], {key: {"status": "ACTIVE", "last_attempt_at": old}}, {}, now=NOW)
    assert body["n_accruing"] == 0 and body["n_silent"] == 1 and body["n_blocked"] == 1
    assert body["blocked_by_status"] == {fe.ENGINE_SILENT: 1}
    assert body["blocked"][0]["status"] == "ACTIVE", "the engine's own status is kept"


def test_fresh_tick_and_no_tick_still_accrue() -> None:
    run = _run()
    key = fe._run_key(run)
    fresh = (NOW - timedelta(minutes=20)).isoformat()
    body = fe.census([run], {key: {"status": "ACTIVE", "last_attempt_at": fresh}}, {}, now=NOW)
    assert body["n_accruing"] == 1 and body["n_silent"] == 0
    body = fe.census([run], {key: {"status": "ACTIVE"}}, {}, now=NOW)
    assert body["n_accruing"] == 1, "no stamp is not proof of silence"


def test_forward_stage_reads_clocks_not_backups(tmp_path: Path) -> None:
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    rows = {"a": {"status": "ACTIVE", "last_attempt_at": (NOW - timedelta(hours=1)).isoformat()},
            "b": {"status": "ACTIVE", "last_attempt_at": (NOW - timedelta(days=9)).isoformat()}}
    (shadow / "shadow_state.json").write_text(json.dumps(rows), "utf-8")
    census = tmp_path / "FORWARD_ENROLMENT.json"
    census.write_text(json.dumps({"status": "MEASURED", "at": NOW.isoformat(),
                                  "n_certificates": 3, "n_enrolled": 3, "n_accruing": 2,
                                  "n_blocked": 1, "n_missing": 0}), "utf-8")
    canon = [{"shadow_spec": {"family": "session_range_breakout"}},
             {"shadow_spec": {"family": "carry"}},
             {"shadow_spec": {"family": "overnight_gap_decay"}},
             {"shadow_spec": {"family": "discovered"}}]
    out = rp.forward_stage(canon, moat_ledgers=[], shadow_dir=shadow, enrolment=census, now=NOW)
    assert out["banned_family_certificates"] == 1
    assert out["forward_eligible_certificates"] == 3
    assert out["clocks_ticked_24h"] == 1 and out["clocks_ticked_7d"] == 1
    assert out["n_accruing"] == 2 and out["moat_backup_ledgers"] == 0


def test_forward_stage_is_unmeasured_without_a_census(tmp_path: Path) -> None:
    out = rp.forward_stage([{"shadow_spec": {"family": "carry"}}], shadow_dir=tmp_path,
                           enrolment=tmp_path / "absent.json", now=NOW)
    assert out["n_accruing"] == "UNMEASURED" and out["clock_rows"] == "UNMEASURED"
