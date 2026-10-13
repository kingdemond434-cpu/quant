"""A policy retirement is reversed when the policy is lifted, and only then (2026-10-13).

THE DEFECT THIS PINS. `_apply_live_policy` retired every row outside `live_symbols`, and nothing
returned it when the principal widened the policy, so certified sleeves stayed out of the
allocator's reach for good. The restore goes to STANDBY, never LIVE: capital still needs the
allocator's admission streak and every door the promoter runs.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(DESK))
import promoter  # noqa: E402
from mt5desk import executables, live_policy  # noqa: E402
from prop import e8_executor  # noqa: E402

CELL = "external.GBPMXN.overnight_gap_decay.p=44136fa355b3678a"


def _row(name: str = "gbpmxn_overnight_gap_decay_asia_p_44136fa355b3678a", *,
         cell: str = CELL, symbol: str = "GBPMXN", family: str = "overnight_gap_decay",
         retired_by: str = "principal_gold_only_2026-09-16") -> dict:
    return {"name": name, "symbol": symbol, "family": family, "selector": "asia",
            "exec": "family_market", "status": "RETIRED", "risk_frac": 0.0,
            "retired_by": retired_by, "retired_at": "2026-09-16T21:46:31+00:00",
            "retire_reason": "principal 2026-09-16: keep only the gold sleeves",
            "admit_scan": "2026-09-16T21:02:29+00:00", "admit_streak": 2,
            "certificate": {"cell": cell}}


@pytest.fixture
def doors(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Every door open unless a test closes one; the live policy is '*' with no bans."""
    state: dict = {"refuse": lambda row, pol: None, "gap": None, "tier_s": None,
                   "veto": None, "regrade": {}}
    monkeypatch.setattr(live_policy, "policy", lambda: object())
    monkeypatch.setattr(live_policy, "refuse", lambda row, pol=None: state["refuse"](row, pol))
    monkeypatch.setattr(executables, "executor_gap", lambda *a, **k: state["gap"])
    monkeypatch.setattr(promoter, "tier_s_block", lambda *_: state["tier_s"])
    monkeypatch.setattr(promoter, "blind_review_veto", lambda *_: state["veto"])
    monkeypatch.setattr(promoter, "regrade_failures", lambda: state["regrade"])
    monkeypatch.setattr(promoter, "note_door", lambda *_, **__: None)
    monkeypatch.setattr(promoter, "plog", lambda *_: None)
    return state


def test_a_lifted_policy_retirement_returns_to_standby_at_zero_risk(doors: dict) -> None:
    row = _row()
    assert promoter.restore_lifted_policy_retirements([row], certified={CELL}) == 1
    assert row["status"] == "STANDBY" and row["risk_frac"] == 0.0
    assert row["admit_streak"] == 0 and "admit_scan" not in row, \
        "the admission streak restarts: capital takes fresh consecutive scans"
    assert "retired_by" not in row and "retire_reason" not in row
    assert row["policy_retirement"]["retired_by"] == "principal_gold_only_2026-09-16"
    assert row["restored_by"] == "policy_lifted"


def test_a_policy_that_still_refuses_keeps_the_row_retired(doors: dict) -> None:
    doors["refuse"] = lambda row, pol: "USDJPY admits only [] for live capital"
    row = _row(retired_by="live_policy")
    assert promoter.restore_lifted_policy_retirements([row], certified={CELL}) == 0
    assert row["status"] == "RETIRED"


@pytest.mark.parametrize("retired_by", ["", "decay_monitor", "evidence", None])
def test_an_evidence_retirement_is_never_restored(doors: dict, retired_by) -> None:
    row = _row(retired_by=retired_by)
    assert promoter.restore_lifted_policy_retirements([row], certified={CELL}) == 0
    assert row["status"] == "RETIRED"


def test_a_certificate_no_longer_in_the_survivors_is_not_restored(doors: dict) -> None:
    row = _row()
    assert promoter.restore_lifted_policy_retirements([row], certified={"other.cell"}) == 0
    assert promoter.restore_lifted_policy_retirements([row], certified=set()) == 0
    assert row["status"] == "RETIRED"


@pytest.mark.parametrize("door", ["tier_s", "veto", "gap", "regrade"])
def test_every_promotion_door_still_binds(doors: dict, door: str) -> None:
    doors[door] = {CELL: {"gates_failing_now": ["stress_costs"]}} if door == "regrade" \
        else "refused"
    row = _row()
    assert promoter.restore_lifted_policy_retirements([row], certified={CELL}) == 0
    assert row["status"] == "RETIRED"


def test_one_certificate_is_never_two_sleeves(doors: dict) -> None:
    principal = {"name": "audchf_x_principal_20261007", "status": "LIVE",
                 "principal_source": "audchf_x", "principal_certificate": "cert.a",
                 "certificate": {"cell": "cert.a"}}
    source = _row("audchf_x", cell="cert.a", symbol="AUDCHF")
    twin_a = _row("chfnok_a", cell="cert.b", symbol="CHFNOK", family="carry")
    twin_b = _row("chfnok_b", cell="cert.b", symbol="CHFNOK", family="carry")
    rows = [principal, source, twin_b, twin_a]
    assert promoter.restore_lifted_policy_retirements(rows, certified={"cert.a", "cert.b"}) == 1
    assert source["status"] == "RETIRED", "the principal identity already carries this cert"
    assert [twin_a["status"], twin_b["status"]] == ["STANDBY", "RETIRED"]


def test_the_live_file_opens_the_universe_and_keeps_every_other_ban() -> None:
    pol = live_policy.policy()
    assert "*" in pol.live_symbols
    assert "discovered" in pol.banned_families
    assert "M15" in pol.banned_timeframes.get("*", frozenset())
    assert "scalp_market" in pol.banned_execs
    assert pol.live_sleeves.get("USDJPY") == frozenset()
    assert pol.live_sleeves.get("CHFNOK") == frozenset()
    gbpmxn = {"name": "gbpmxn_overnight_gap_decay_asia_p_44136fa355b3678a", "symbol": "GBPMXN",
              "family": "overnight_gap_decay", "exec": "family_market"}
    assert live_policy.refuse(gbpmxn, pol) is None
    assert live_policy.refuse({**gbpmxn, "family": "discovered"}, pol)
    assert live_policy.refuse({**gbpmxn, "symbol": "CHFNOK"}, pol)


@pytest.mark.parametrize("budget, base, lot, charged", [
    (1000.0, 0.10, 0.13, 1300.0),   # a 1.3x lean carries 1.3x the budget
    (1000.0, 0.10, 0.07, 700.0),    # and a damped one less
    (1000.0, 0.0, 0.05, 1000.0),    # unmeasurable ratio charges the budget as it was
    (1000.0, 0.10, 0.0, 1000.0),
])
def test_e8_floor_is_charged_what_the_multiplied_lot_risks(budget, base, lot, charged) -> None:
    assert e8_executor.charged_risk_usd(budget, base, lot) == pytest.approx(charged)
