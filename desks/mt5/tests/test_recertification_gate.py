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

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import promoter  # noqa: E402

_KEY = "qquant.hunt16.json.AUDNZD dav_range_filter_adx SHORT afternoon NORMAL_DAY"
_SPEC = {"symbol": "AUDNZD", "selector": "afternoon", "condition": "NORMAL_DAY",
         "family": "dav_range_filter_adx", "is_universe": False, "side": "SHORT"}


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
    assert promoter.promote_generic(sleeves, _candidate(), set(), _authority()) is True
    assert [s["name"] for s in sleeves] == [_KEY]
    assert sleeves[0]["status"] == "LIVE"


def test_a_stale_audit_is_reported_not_binding(tmp_path, monkeypatch) -> None:
    _audit(tmp_path, monkeypatch, "COST_REGRADE_FAIL", age_h=promoter.RECERT_FRESH_H + 5)
    assert promoter.regrade_failures() == {}
    monkeypatch.setattr(promoter, "load_cert_specs", lambda: {_KEY: _SPEC})
    sleeves: list[dict] = []
    promoter.promote_generic(sleeves, _candidate(), set(), _authority())
    assert [s["name"] for s in sleeves] == [_KEY]


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
