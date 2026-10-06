"""A certificate that fails its own ten gates at today's costs is not promoted.

`scripts/recertify_canon.py` re-judges every standing certificate under the CURRENT cost model
and writes `reports/recertification_audit.json`; canon never shrinks from a script, so the
promoter is where the corrected measurement binds. Pinned: a fresh COST_REGRADE_FAIL refuses the
qquant candidate with a named reason; STILL_PASSES promotes as before; a stale audit is reported
and does not bind; prefixed and bare certificate names match each other.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

# The Tier S door fails closed on absent verifier inputs; these promoter tests are not about
# the door, so they run against fresh, clean verifier artifacts (desks/mt5/tests/conftest.py).
pytestmark = pytest.mark.usefixtures("fresh_tier_s_door")


_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import promoter  # noqa: E402

_KEY = "qquant.hunt16.json.AUDNZD dav_range_filter_adx SHORT afternoon NORMAL_DAY"
_SPEC = {"symbol": "AUDNZD", "selector": "afternoon", "condition": "NORMAL_DAY",
         "family": "dav_range_filter_adx", "is_universe": False, "side": "SHORT"}


@pytest.fixture(autouse=True)
def _tier_s_door_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Tier S door is granted here exactly as the gate authority and the allocator are.

    Since 7de6ccca7 (2026-09-30) `promotion_authority.block` withholds with DOOR_ERROR whenever
    REPLICATION.json (or another required verdict file) is absent or stale -- which it always is
    in a checkout, because the hourly verifiers write it on the box. That is correct fail-closed
    behaviour, pinned in `test_tier_s_door.py`; this file is about the RECERTIFICATION gate, so
    the door is opened here and its interaction is pinned once, below, with the door CLOSED.
    """
    monkeypatch.setattr(promoter, "tier_s_block", lambda _name: None)


def _audit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: str,
           age_h: float = 1.0, certificate: str = _KEY) -> None:
    p = tmp_path / "reports" / "recertification_audit.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    at = datetime.now(tz=UTC) - timedelta(hours=age_h)
    p.write_text(json.dumps({
        "audited_at": at.isoformat(timespec="seconds"),
        "rows": [{"certificate": certificate, "status": status,
                  "gates_failing_now": ["stress_costs", "expected_value"],
                  "cost_per_lot_now": 9.12}],
    }), "utf-8")
    monkeypatch.setattr(promoter, "RECERT_AUDIT", p)
    monkeypatch.setattr(promoter, "LOG", tmp_path / "logs" / "promoter.log")


def _candidate() -> dict:
    return {_KEY: {"status": "PROMOTION_CANDIDATE", "n": 60, "exp_r": 0.12}}


def _authority() -> set:
    return {(_SPEC["symbol"], _SPEC["selector"], _SPEC["condition"], _SPEC["family"], False)}


def _admitting_view(heat: float = 0.03) -> dict:
    """An allocator view that admits this candidate on dE[log W].

    CAPITAL IS THE ALLOCATOR'S (principal 2026-09-05): a promoted row is LIVE only when adding it
    to the held book raises robust growth. This file is about the RECERTIFICATION gate, so the
    marginal is granted here exactly as the gate authority is, and the criterion itself is pinned
    in `test_marginal_admission.py`.
    """
    return {"fresh": True, "why": "fixture", "at": datetime.now(tz=UTC).isoformat(),
            "candidates": {_KEY.lower(): {"delta_elogw_per_day": 0.0004, "heat_earned": heat,
                                          "admit": True, "why": "fixture: admitted"}},
            "book": {}, "zeroed": {}, "total_heat": 0.20}


def test_a_fresh_cost_regrade_failure_refuses_promotion(tmp_path, monkeypatch) -> None:
    _audit(tmp_path, monkeypatch, "COST_REGRADE_FAIL")
    monkeypatch.setattr(promoter, "load_cert_specs", lambda: {_KEY: _SPEC})
    sleeves: list[dict] = []
    q = _candidate()
    changed = promoter.promote_generic(sleeves, q, set(), _authority())
    assert changed is True
    assert sleeves == []
    assert q[_KEY]["status"] == "BLOCKED_COST_REGRADE"
    assert "stress_costs" in q[_KEY]["gate_reason"]


def test_still_passes_promotes_as_before(tmp_path, monkeypatch) -> None:
    _audit(tmp_path, monkeypatch, "STILL_PASSES")
    monkeypatch.setattr(promoter, "load_cert_specs", lambda: {_KEY: _SPEC})
    sleeves: list[dict] = []
    assert promoter.promote_generic(sleeves, _candidate(), set(), _authority(),
                                    view=_admitting_view(0.021)) is True
    assert [s["name"] for s in sleeves] == [_KEY]
    assert sleeves[0]["status"] == "LIVE"
    # And the size is the allocator's own solve, not the old flat constant.
    assert sleeves[0]["risk_frac"] == pytest.approx(0.021)
    assert sleeves[0]["risk_frac_source"] == "allocator_marginal"


def test_a_stale_audit_is_reported_not_binding(tmp_path, monkeypatch) -> None:
    _audit(tmp_path, monkeypatch, "COST_REGRADE_FAIL", age_h=promoter.RECERT_FRESH_H + 5)
    assert promoter.regrade_failures() == {}
    monkeypatch.setattr(promoter, "load_cert_specs", lambda: {_KEY: _SPEC})
    sleeves: list[dict] = []
    promoter.promote_generic(sleeves, _candidate(), set(), _authority())
    assert [s["name"] for s in sleeves] == [_KEY]


def test_a_passing_recertification_does_not_open_a_closed_tier_s_door(tmp_path,
                                                                        monkeypatch) -> None:
    # STILL_PASSES clears the recert gate only; the Tier S door still withholds the new row.
    _audit(tmp_path, monkeypatch, "STILL_PASSES")
    monkeypatch.setattr(promoter, "load_cert_specs", lambda: {_KEY: _SPEC})
    monkeypatch.setattr(promoter, "_record_tier_s_block", lambda *_a, **_kw: None)
    why = ("DOOR_ERROR: the replication check raised DoorReadError: REPLICATION.json absent: "
           "its hourly verifier has not reported; withheld until it runs clean")
    monkeypatch.setattr(promoter, "tier_s_block", lambda _name: why)
    sleeves: list[dict] = []
    q = _candidate()
    assert promoter.promote_generic(sleeves, q, set(), _authority(),
                                    view=_admitting_view(0.021)) is True
    assert sleeves == []
    assert q[_KEY]["status"] == "BLOCKED_TIER_S" and q[_KEY]["gate_reason"] == why


def test_prefixed_and_bare_certificate_names_match() -> None:
    fails = {"external.USDZAR.overnight_gap_decay.p=44136fa355b3678a": {"status": "x"}}
    assert promoter.regrade_block("USDZAR.overnight_gap_decay.p=44136fa355b3678a", fails)
    assert promoter.regrade_block("external.USDZAR.overnight_gap_decay.p=44136fa355b3678a",
                                  fails)
    assert promoter.regrade_block("USDZAR.overnight_gap_decay.asia", fails) is None
    assert promoter.regrade_block("XAUUSD.asia", {}) is None


def test_the_daily_cycle_recertifies_before_it_promotes() -> None:
    import daily_cycle
    names = [n for n, _ in daily_cycle.STEPS]
    assert names.index("shadow") < names.index("recertify") < names.index("promoter")
