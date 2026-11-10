"""The causal-graph fence: RED fails anywhere, absence and staleness fail only where the leg is
scheduled, and a clean checkout is UNMEASURED rather than a pass."""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import check_world_causal_graph as c  # noqa: E402

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


def _rep(verdict: str, age_h: float = 0.5, **extra: object) -> dict:
    return {"generated_at": (NOW - timedelta(hours=age_h)).isoformat(),
            "zero_admission": {"verdict": verdict, "runs": 3, "admitted_total": 0,
                               "why": "3 consecutive passes", **extra}}


def test_absent_is_unmeasured_on_a_checkout_and_a_failure_on_the_box() -> None:
    assert c.judge(None, require_state=False, now=NOW)["status"] == "UNMEASURED"
    assert c.judge(None, require_state=True, now=NOW)["status"] == "FAIL"


def test_red_fails_with_or_without_state() -> None:
    for req in (False, True):
        res = c.judge(_rep("RED"), require_state=req, now=NOW)
        assert res["status"] == "FAIL" and "RED" in res["why"]


def test_watch_and_ok_pass_and_a_stale_report_fails_only_on_the_box() -> None:
    assert c.judge(_rep("WATCH"), require_state=True, now=NOW)["status"] == "OK"
    assert c.judge(_rep("OK"), require_state=True, now=NOW)["status"] == "OK"
    stale = _rep("OK", age_h=c.STALE_H + 1)
    assert c.judge(stale, require_state=True, now=NOW)["status"] == "FAIL"
    assert c.judge(stale, require_state=False, now=NOW)["status"] == "OK"


def test_a_report_from_the_older_organ_has_no_block_and_is_not_a_pass() -> None:
    old = {"generated_at": NOW.isoformat(), "edges_admitted": 0}
    assert c.judge(old, require_state=False, now=NOW)["status"] == "UNMEASURED"
    assert c.judge(old, require_state=True, now=NOW)["status"] == "FAIL"


def test_the_cli_exits_zero_when_there_is_no_report(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(c, "REPORT", tmp_path / "absent.json")
    assert c.main([]) == 0
    assert "UNMEASURED" in capsys.readouterr().out
    assert c.main(["--require-state"]) == 1
