"""The meta controller's prices ACTUALLY set the hour (Tier-1 B27).

Three properties are load-bearing and all three are laws, not preferences:
winners get more, every leg keeps a scout floor, and the hour's total is never reduced. A pricing
organ that could fail any one of them would be a brake wearing a controller's name, which the
principal's never-reduce-aggressiveness order forbids outright.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cycle_pricing as cp  # type: ignore[import-not-found]  # noqa: E402


def _isolate(tmp_path: Path, monkeypatch: Any, *, meta: dict[str, Any] | None = None,
             bandit: dict[str, Any] | None = None,
             policy: dict[str, Any] | None = None,
             ledger: str = "") -> None:
    """Point every input and the artifact at tmp_path. No test may read or write desk state."""
    for name, doc in (("META", meta), ("BANDIT", bandit), ("POLICY", policy)):
        p = tmp_path / f"{name}.json"
        if doc is not None:
            p.write_text(json.dumps(doc), encoding="utf-8")
        monkeypatch.setattr(cp, name, p, raising=True)
    lp = tmp_path / "compute_ledger.jsonl"
    lp.write_text(ledger, encoding="utf-8")
    monkeypatch.setattr(cp, "LEDGER", lp, raising=True)
    monkeypatch.setattr(cp, "OUT", tmp_path / "CYCLE_PRICING.json", raising=True)
    monkeypatch.setattr(cp, "_PLAN", None, raising=False)
    monkeypatch.setattr(cp, "_PLAN_AT", 0.0, raising=False)


BASES = {f"leg{i}": 600 for i in range(10)}


def _board(values: dict[str, float]) -> dict[str, Any]:
    """A META_CONTROLLER.json whose delta_elog board prices the given KINDS."""
    return {"boards": {"delta_elog": {"status": "OK",
                                      "rows": [{"kind": k, "delta_elog_per_day": v}
                                               for k, v in values.items()]}}}


def test_a_winner_gets_more_and_the_loser_keeps_its_scout_floor(
        tmp_path: Path, monkeypatch: Any) -> None:
    _isolate(tmp_path, monkeypatch, meta={}, bandit={}, policy={})
    monkeypatch.setattr(cp, "_kind_legs", lambda: {}, raising=True)
    monkeypatch.setattr(cp, "_meta_prices", lambda: ({"leg0": 10.0, "leg9": -5.0}, ""),
                        raising=True)
    monkeypatch.setattr(cp, "_bandit_prices", dict, raising=True)
    monkeypatch.setattr(cp, "_policy_factors", lambda: ({}, False), raising=True)
    plan = cp.build_plan(BASES)
    legs = plan["legs"]
    assert legs["leg0"]["factor"] > 1.0, "the best-priced leg was not given more"
    assert legs["leg0"]["planned_s"] > legs["leg0"]["base_s"]
    # TWO-SIDED, AND THE FLOOR IS A FLOOR. The worst-priced leg is cut, never below FLOOR x base
    # and never below the scout minimum.
    assert legs["leg9"]["factor"] >= cp.FLOOR
    assert legs["leg9"]["planned_s"] >= cp.SCOUT_MIN_S
    assert legs["leg9"]["planned_s"] >= int(legs["leg9"]["base_s"] * cp.FLOOR)
    # Unpriced legs sit at the median, not at zero and not at the bottom.
    for name in ("leg3", "leg5"):
        assert legs[name]["priced_by"] == ["unpriced:median"]
        assert legs[name]["factor"] == pytest.approx(1.0, abs=1e-6)


def test_the_hour_is_never_globally_reduced(tmp_path: Path, monkeypatch: Any) -> None:
    """The controller reallocates compute; it never hands the hour back. Checked over a spread
    of price shapes, including one where every leg is priced below the median."""
    monkeypatch.setattr(cp, "_kind_legs", lambda: {}, raising=True)
    monkeypatch.setattr(cp, "_bandit_prices", dict, raising=True)
    monkeypatch.setattr(cp, "_policy_factors", lambda: ({}, False), raising=True)
    shapes = [
        {},                                                     # nothing priced
        {f"leg{i}": float(i) for i in range(10)},               # a clean gradient
        {f"leg{i}": -float(i) for i in range(10)},              # every price negative
        {f"leg{i}": 1.0 for i in range(10)},                    # every price identical
        {"leg0": 1e9, "leg1": -1e9},                            # two wild outliers
    ]
    for n, prices in enumerate(shapes):
        (tmp_path / f"c{n}").mkdir(parents=True, exist_ok=True)
        _isolate(tmp_path / f"c{n}", monkeypatch, meta={}, bandit={}, policy={})
        monkeypatch.setattr(cp, "_meta_prices", lambda p=prices: (dict(p), ""), raising=True)
        plan = cp.build_plan(BASES)
        t = plan["totals"]
        assert t["planned_s"] >= t["base_s"], f"shape {n} reduced the hour"
        assert t["never_reduced"] is True
        for leg, v in plan["legs"].items():
            assert v["planned_s"] >= cp.SCOUT_MIN_S, f"{leg} was starved in shape {n}"


def test_ties_do_not_fan_out(tmp_path: Path, monkeypatch: Any) -> None:
    """The defect this was written for: `compute_policy` publishes every tier factor at 1.0 until
    it has measured survivors per hour, and with strict ranks 256 IDENTICAL prices spread across
    the whole range -- one leg at 2.0x and another at 0.6x on no evidence at all."""
    r = cp._rank01({f"leg{i}": 1.0 for i in range(10)})
    assert set(r.values()) == {0.5}, "identical prices produced different ranks"


def test_the_order_puts_scouts_first_then_price(tmp_path: Path, monkeypatch: Any) -> None:
    _isolate(tmp_path, monkeypatch, meta={}, bandit={}, policy={})
    monkeypatch.setattr(cp, "_kind_legs", lambda: {}, raising=True)
    monkeypatch.setattr(cp, "_meta_prices",
                        lambda: ({"leg0": 9.0, "leg1": 5.0, "leg2": 1.0}, ""), raising=True)
    monkeypatch.setattr(cp, "_bandit_prices", dict, raising=True)
    monkeypatch.setattr(cp, "_policy_factors", lambda: ({}, False), raising=True)
    # leg2 is priced LAST and has not run in a day: the scout rotation pulls it to the front, so
    # a leg priced low once is not priced low forever for want of ever running again.
    monkeypatch.setattr(cp, "_last_run_h",
                        lambda: {"leg0": 0.1, "leg1": 0.1, "leg2": 24.0}, raising=True)
    plan = cp.build_plan({"leg0": 600, "leg1": 600, "leg2": 600})
    assert plan["order"][0] == "leg2", f"the stale leg did not scout first: {plan['order']}"
    fresh = [n for n in plan["order"] if n != "leg2"]
    assert fresh == ["leg0", "leg1"], "fresh legs were not ordered by price"


def test_applied_budget_records_planned_against_applied(
        tmp_path: Path, monkeypatch: Any) -> None:
    _isolate(tmp_path, monkeypatch, meta={}, bandit={}, policy={})
    monkeypatch.setattr(cp, "_kind_legs", lambda: {}, raising=True)
    monkeypatch.setattr(cp, "_meta_prices", lambda: ({"leg0": 9.0, "leg9": -9.0}, ""),
                        raising=True)
    monkeypatch.setattr(cp, "_bandit_prices", dict, raising=True)
    monkeypatch.setattr(cp, "_policy_factors", lambda: ({}, False), raising=True)
    monkeypatch.setattr(cp, "_bases", lambda: dict(BASES), raising=True)
    ok_before, why_before = cp.authority()
    assert ok_before is False and "no leg has asked" in why_before

    secs, rec = cp.applied_budget("leg0", 600)
    assert rec["applied"] is True and secs > 600
    doc = json.loads(cp.OUT.read_text("utf-8"))
    assert doc["applied"]["leg0"]["applied_s"] == secs
    assert doc["applied"]["leg0"]["planned_s"] == doc["applied"]["leg0"]["applied_s"]
    assert doc["n_applied"] == 1
    ok_after, why_after = cp.authority()
    assert ok_after is True, why_after
    assert "leg0" in why_after


def test_an_unreadable_price_returns_the_base_and_never_raises(
        tmp_path: Path, monkeypatch: Any) -> None:
    """A cycle that stalls on a missing price is worse than one that never had prices."""
    _isolate(tmp_path, monkeypatch, meta={}, bandit={}, policy={})

    def _boom() -> dict[str, Any]:
        raise RuntimeError("no board")

    monkeypatch.setattr(cp, "plan", _boom, raising=True)
    secs, rec = cp.applied_budget("leg0", 777)
    assert secs == 777 and rec["applied"] is False and "unavailable" in rec["why"]


def test_the_hourly_cycle_asks_the_pricer_for_every_leg() -> None:
    """THE WIRING, not the library. `_producer_impl` and `_auto_leg` must both route their budget
    through `_priced_budget`, and `run_auto_legs` must order through `cycle_pricing.order` --
    otherwise the controller is advisory again and nothing in the artifact would say so."""
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert "_priced_budget(name, LEG_BUDGET_SEC.get(name, SEARCH_BUDGET_SEC))" in src, \
        "the subprocess legs no longer take their budget from the controller"
    assert "_priced_budget(leg, budget)" in src, \
        "the auto-clocked legs no longer take their budget from the controller"
    assert "cycle_pricing.order(" in src, "the auto legs are no longer ordered by price"
    assert "applied_budget_s" in src, \
        "the compute-ledger row no longer carries the applied budget (B27's consumer)"


def test_the_compute_ledger_row_carries_the_applied_budget(
        tmp_path: Path, monkeypatch: Any) -> None:
    """The named consumer: a ledger row must be able to say what the controller ALLOWED beside
    what the leg spent. Without it a leg priced down is indistinguishable from one that finished
    early, which is the measurement B27 exists to make."""
    from libs.ops import compute_ledger as cl

    monkeypatch.setattr(cl, "LEDGER", tmp_path / "compute_ledger.jsonl", raising=False)
    monkeypatch.setattr(cl, "_record_run_in_registry", lambda *_a, **_k: None, raising=True)
    run = cl.open_run("leg0", kind="hourly_cycle", applied_budget_s=1200, price_factor=2.0,
                      priced_by="meta_controller")
    row = cl.close_run(run, outcome="ok")
    assert row["applied_budget_s"] == 1200
    assert row["price_factor"] == 2.0
    assert row["priced_by"] == "meta_controller"
