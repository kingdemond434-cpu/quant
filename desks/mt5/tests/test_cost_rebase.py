"""A cost correction must not kill a pre-registered clock forever.

MEASURED 2026-09-02: all twelve IDENTITY_BROKEN clocks had frozen
`commission_per_lot: 3.5` -- the round-turn figure that sat in a per-SIDE field. The desk
corrected it to 2.25, every cost_hash changed, and twelve clocks stopped accruing toward the
`days >= 14` bar because the desk had fixed a known error. These tests fence the narrow recovery
that fixes it and, more importantly, fence how narrow it stays.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import sleeve_registry as reg  # noqa: E402

KEY = "EURNOK.overnight_gap_decay.asia"
FROZEN = {"family": "overnight_gap_decay", "symbol": "EURNOK", "direction": "LONG",
          "timeframe": "H1", "selector": "asia", "condition": None, "params": {},
          "code_hash": "aaaa", "cost_hash": "OLD", "data_venue": "MT5:FusionMarkets-Live"}
OLD_COST = {"spread_per_lot": 153.0, "commission_per_lot": 3.5,
            "contract_oz": 1e5, "quote_per_account": 10.8}
NEW_COST = {"spread_per_lot": 775.0, "commission_per_lot": 2.25,
            "contract_oz": 1e5, "quote_per_account": 10.8}


@pytest.fixture
def registry(tmp_path, monkeypatch):
    path = tmp_path / "sleeve_registry.json"
    monkeypatch.setattr(reg, "REGISTRY", path)

    def seed(identity=None, cost=None, **row):
        path.write_text(json.dumps({"sleeves": {KEY: {
            "identity": dict(identity or FROZEN),
            "cost_fields": dict(cost or OLD_COST),
            "forward_start": "2026-08-27T07:58:09+00:00",
            "frozen_at": "2026-08-27T03:31:40+00:00",
            "status": "IDENTITY_BROKEN", **row}}}), encoding="utf-8")

    def read():
        return json.loads(path.read_text(encoding="utf-8"))["sleeves"][KEY]

    seed()
    return type("R", (), {"seed": staticmethod(seed), "read": staticmethod(read)})


def _ident(**over):
    return {**FROZEN, "cost_hash": "NEW", **over}


def test_a_cost_only_drift_is_rebased(registry) -> None:
    why = reg.rebase_cost(KEY, _ident(), NEW_COST)
    assert why and "cost model corrected" in why
    row = registry.read()
    assert row["status"] == "LIVE"
    assert row["identity"]["cost_hash"] == "NEW"
    assert row["cost_fields"] == NEW_COST


def test_forward_start_is_never_touched(registry) -> None:
    """The ratchet is the whole reason this is allowed: pre-registration protects WHICH DAYS were
    observed, and a cost correction does not un-observe a day."""
    before = registry.read()["forward_start"]
    reg.rebase_cost(KEY, _ident(), NEW_COST)
    assert registry.read()["forward_start"] == before


def test_the_old_cost_is_kept_for_audit(registry) -> None:
    reg.rebase_cost(KEY, _ident(), NEW_COST)
    assert registry.read()["cost_fields_before_rebase"] == OLD_COST


def test_a_cheaper_correction_is_flagged_not_hidden(registry) -> None:
    """A "correction" that makes a sleeve cheaper is the shape of a desk talking itself into an
    edge. It is still allowed -- and it is still findable."""
    cheaper = {**OLD_COST, "commission_per_lot": 0.10, "spread_per_lot": 1.0}
    reg.rebase_cost(KEY, _ident(), cheaper)
    assert registry.read()["cost_rebase_cheaper"] is True


def test_the_real_correction_was_dearer(registry) -> None:
    reg.rebase_cost(KEY, _ident(), NEW_COST)
    assert registry.read()["cost_rebase_cheaper"] is False


@pytest.mark.parametrize("field,value", [
    ("code_hash", "bbbb"),
    ("params", {"rr": 2.0}),
    ("symbol", "EURSEK"),
    ("direction", "SHORT"),
    ("selector", "london_am"),
    ("data_venue", "MT5:SomeOtherBroker"),
])
def test_any_other_drift_leaves_the_clock_terminal(registry, field, value) -> None:
    """SOLE-CAUSE RULE. A strategy change is still a new clock and a new window."""
    assert reg.rebase_cost(KEY, _ident(**{field: value}), NEW_COST) is None
    assert registry.read()["status"] == "IDENTITY_BROKEN"


def test_an_intact_identity_is_not_rebased(registry) -> None:
    """Nothing drifted, so there is nothing to correct -- `reconcile` owns that case."""
    assert reg.rebase_cost(KEY, dict(FROZEN), NEW_COST) is None


def test_an_unmeasured_new_cost_is_not_a_correction(registry) -> None:
    """Absence is never permission (L1.28a): an empty cost cannot re-freeze a clock."""
    assert reg.rebase_cost(KEY, _ident(), {}) is None
    assert registry.read()["status"] == "IDENTITY_BROKEN"


def test_an_unregistered_key_is_not_invented(registry) -> None:
    assert reg.rebase_cost("NOSUCH.key.asia", _ident(), NEW_COST) is None


def test_repeated_rebases_are_counted(registry) -> None:
    """A clock whose cost keeps moving is an alarm, not a healthy clock."""
    reg.rebase_cost(KEY, _ident(), NEW_COST)
    registry.seed(identity=_ident(), cost=NEW_COST, cost_rebase_count=1)
    reg.rebase_cost(KEY, _ident(cost_hash="NEWER"), {**NEW_COST, "spread_per_lot": 800.0})
    assert registry.read()["cost_rebase_count"] == 2
