"""A Tier S hold that was a DOOR_ERROR goes back to the promoter; a hold on evidence does not.

Measured 2026-11-10: eight main-lane rows sat at BLOCKED_TIER_S on one DOOR_ERROR
(REPLICATION.json stale). The door passed all eight later, but the promoter reads only rows at
PROMOTION CANDIDATE, so it never asked again. The forward clock now hands such a row back; the
promoter runs every door on it again, so nothing here decides a promotion.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import shadow_forward as sf  # noqa: E402

_KEY = "GBPNOK.overnight_gap_decay.asia"
_STALE = ("DOOR_ERROR: the replication check raised DoorReadError: REPLICATION.json stale or "
          "undated (> 6h): its hourly verifier has stopped reporting; withheld until it runs clean")


@pytest.fixture(autouse=True)
def _quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sf, "slog", lambda *_a: None)


def _held(**kw: object) -> dict:
    return {"status": "BLOCKED_TIER_S", "gate_reason": _STALE, "n": 31, "exp_r": 0.21,
            "max_dd_r": -4.0, **kw}


def test_a_door_error_hold_is_handed_back_as_a_candidate() -> None:
    st = _held()
    assert sf.reopen_door_error(_KEY, st) is True
    assert st["status"] == "PROMOTION CANDIDATE" and "gate_reason" not in st
    assert st["tier_s_reopened"][0]["was"].startswith("DOOR_ERROR")


@pytest.mark.parametrize("why", [
    "REPLICATION_MISMATCH: re-execution of GBPNOK returned MISMATCH",
    "ONLINE_FDR_OVER_BUDGET: admitted after the lifetime budget was spent",
    "IMMUNE_FREEZE: the production certifier got easier to fool", ""])
def test_a_hold_that_is_not_a_door_error_is_left_alone(why: str) -> None:
    st = _held(gate_reason=why)
    assert sf.reopen_door_error(_KEY, st) is False
    assert st["status"] == "BLOCKED_TIER_S"


@pytest.mark.parametrize(("exp_r", "dd"), [(0.01, -4.0), (0.21, -30.0), (None, -4.0)])
def test_a_record_below_the_clocks_own_clause_stays_held(exp_r, dd) -> None:
    st = _held(exp_r=exp_r, max_dd_r=dd)
    assert sf.reopen_door_error(_KEY, st) is False
    assert st["status"] == "BLOCKED_TIER_S"


@pytest.mark.parametrize("status", ["ACTIVE", "KILL", "PROMOTION CANDIDATE",
                                    "BLOCKED_BLIND_REVIEW", "BLOCKED_COST_REGRADE"])
def test_only_tier_s_holds_are_touched(status: str) -> None:
    st = _held(status=status)
    assert sf.reopen_door_error(_KEY, st) is False and st["status"] == status


def test_the_reopen_history_is_bounded() -> None:
    st = _held(tier_s_reopened=[{"at": "x", "was": "y"}] * 30)
    sf.reopen_door_error(_KEY, st)
    assert len(st["tier_s_reopened"]) == 20


def test_the_promoter_runs_the_tier_s_door_on_every_candidate_it_reads() -> None:
    # The reopen is safe only because the candidate path re-asks the door. Pin that it does.
    src = (_DESK / "research" / "promoter.py").read_text("utf-8")
    loop = src.index("for key, st in shadow.items():")
    filt = src.index('if st.get("status") != "PROMOTION CANDIDATE":', loop)
    assert src.index("_ts = tier_s_block(key)", filt) > filt
