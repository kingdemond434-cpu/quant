"""The anti-conservatism engine must not manufacture the conservatism it hunts.

TWO DEFECTS OF ONE CLASS, both measured live on 2026-08-20, both in the direction that pushes
capital forward -- which is the dangerous one for an artifact whose own rule tells its reader to
"close it same-cycle".

(1) STALE INPUT. `promotion_latency` read web/cashcarry_shadow.json with a bare `_load()` and no
    freshness contract. The artifact was 65h old and still carried `fast_track = ELIGIBLE ...` from
    forward day 52, so the audit published ACT-NOW / "NONE -- pure foregone growth". Re-running the
    producer took seconds and INVERTED the verdict: day 55, `regime evidence PENDING (events 0,
    funding-vol 5e-05 vs bar 7e-05)` -- the window sits in the calmest quartile, the one thing
    REGIME EVIDENCE v2 exists to refuse. The desk's only published conservatism defect was an
    artifact of a stale read (L1.44).

(2) A LATCHED RAIL READ AS TIMIDITY. R0274 fixed exactly this for check #1 -- "the audit could not
    tell timidity from a latched kill switch, and that is the more dangerous direction" -- and the
    fix was never carried to checks #2 and #4. So the class returned on new input: the sleeve named
    by check #4 is the cash-and-carry, whose executor carries `_PERMANENTLY_RETIRED = True`
    (run_cashcarry_executor.py:64, principal order 2026-08-19) on a universe the MT5 mandate
    permanently closed.

THE THIRD TEST IS THE LOAD-BEARING ONE. A fix that made this check quiet would be a welded gate
(L1.63) wearing a repair's clothes -- and welding shut the desk's only anti-timidity detector is a
far worse outcome than the bug. `test_gate_still_fires_when_nothing_justifies_it` is the positive
control: no rail, fresh clock, eligible sleeve -> the defect MUST still be published.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import scripts.run_growth_audit as G


def _desk(root: Path, *, shadow_age_h: float, fast_track: str, rail: bool) -> None:
    """A minimal desk on disk: the four artifacts main() reads, plus an optional latched rail."""
    (root / "web").mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(parents=True, exist_ok=True)
    stamp = (datetime.now(tz=UTC) - timedelta(hours=shadow_age_h)).isoformat()
    (root / "web" / "cashcarry_shadow.json").write_text(
        json.dumps({"updated": stamp, "fast_track": fast_track}), "utf-8")
    # Deployed 0 against authorized capital -> check #1 is a GAP, so a latched rail has something
    # to justify and the run exercises the same override path in both places.
    (root / "web" / "cashcarry_live.json").write_text(
        json.dumps({"deployed_notional": 0.0}), "utf-8")
    (root / "web" / "live_combined.json").write_text(
        json.dumps({"spot": {"usdt": 9968.0}}), "utf-8")
    (root / "web" / "leverage.json").write_text(
        json.dumps({"sleeves": {"cash_and_carry": {"confidence": 0.0,
                                                   "recommended_leverage": 0.25,
                                                   "ruin_cap": 2.05}}}), "utf-8")
    (root / "data" / "live_deployment_policy.json").write_text(
        json.dumps({"status": "ARMED"}), "utf-8")
    (root / "data" / "cashcarry_config.json").write_text(json.dumps({"capital": 200.0}), "utf-8")
    if rail:
        (root / "data" / "CASHCARRY_KILL").write_text("live_guard freeze: pager ladder", "utf-8")


def _run(tmp_path: Path, monkeypatch, **kw) -> dict:
    _desk(tmp_path, **kw)
    monkeypatch.chdir(tmp_path)
    G.main()
    return json.loads((tmp_path / "web" / "growth_audit.json").read_text("utf-8"))


def _item(out: dict, check: str) -> dict:
    return next(i for i in out["items"] if i["check"] == check)


_ELIGIBLE = "ELIGIBLE (>=40d + NW-t>=1.65 + fwd>=0.5xbt + regime evidence) -> live-promotable"


def test_gate_still_fires_when_nothing_justifies_it(tmp_path, monkeypatch):
    """POSITIVE CONTROL. Fresh clock, eligible sleeve, no rail -> the defect MUST be published.

    Without this the other two tests are satisfied by a check that simply never fires, which is
    the failure mode (a welded gate) that would be strictly worse than the bug being fixed.
    """
    out = _run(tmp_path, monkeypatch, shadow_age_h=1.0, fast_track=_ELIGIBLE, rail=False)
    it = _item(out, "promotion_latency")
    assert it["verdict"] == "ACT-NOW"
    assert it["justified_by"].startswith("NONE")
    assert "promotion_latency" in out["conservatism_defects"]


def test_stale_forward_clock_refuses_to_license_a_promotion(tmp_path, monkeypatch):
    """(1) A clock older than its contract resolves to UNMEASURED, never to ACT-NOW."""
    out = _run(tmp_path, monkeypatch,
               shadow_age_h=G._SHADOW_MAX_AGE_H + 29.0, fast_track=_ELIGIBLE, rail=False)
    it = _item(out, "promotion_latency")
    assert it["verdict"] == "UNMEASURED"
    assert it["justified_by"].startswith("UNMEASURED")
    # The whole point: a stale ELIGIBLE must not reach the list an organ acts on.
    assert "promotion_latency" not in out["conservatism_defects"]
    assert "STALE READ REFUSED" in it["utilized"]


def test_latched_rail_is_never_reported_as_timidity(tmp_path, monkeypatch):
    """(2) R0274 generalised: a rail-clamped book is not a conservatism defect, in ANY check.

    UPDATED 2026-09-05. The verdict is now RETIRED rather than ACT-NOW, and that is the 2026-08-27
    half of this file's argument taking effect rather than a regression. R0274 says a rail may
    change a JUSTIFICATION but never a VERDICT, because a temporary clamp lifts and leaves a real
    gap behind it. That reasoning needs a lifting condition to exist. The cash-carry executor was
    deleted with the crypto-exchange universe, so there is no condition under which this book ever
    trades again -- and "ACT-NOW: promote this sleeve" would be a standing instruction to move a
    dead book toward capital on a universe the mandate closed for good.

    What is still asserted, and is the property that matters: the rail alone never launders the
    gap into health. `conservatism_defects` stays empty for a permanently-retired sleeve, exactly
    as it did for a clamped one.
    """
    out = _run(tmp_path, monkeypatch, shadow_age_h=1.0, fast_track=_ELIGIBLE, rail=True)
    it = _item(out, "promotion_latency")
    assert it["verdict"] == "RETIRED", "a deleted executor is retired, not merely clamped"
    assert out["conservatism_defects"] == []


@pytest.mark.parametrize("rail", [True, False])
def test_rail_override_never_launders_a_non_none_justification(rail):
    """The override may only ever convert a NONE claim; it can never manufacture health."""
    clamp = {"rail": "R", "detail": "d", "lifting_condition": "L"} if rail else None
    assert G._rail_override("evidence clock", clamp, "x") == "evidence clock"
    assert G._rail_override("human (one-time...)", clamp, "x").startswith("human")
