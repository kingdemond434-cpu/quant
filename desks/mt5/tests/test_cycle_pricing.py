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
    # The factory contracts are a price source read from the desk's reports; a test must never
    # price off what the box wrote this hour.
    monkeypatch.setattr(cp, "_factory_prices", lambda: ({}, "isolated"), raising=True)
    monkeypatch.setattr(cp, "_alpha_rank_prices", lambda: ({}, "isolated"), raising=True)


BASES = {f"leg{i}": 600 for i in range(10)}


def _spare_ledger(wall_s: float = 60.0) -> str:
    """One recent compute-ledger row: the `rest` clock is measured and nearly idle, so its spare
    is MEASURED. The grant above base comes out of that spare and out of nothing else."""
    from datetime import UTC, datetime
    row = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"), "run": "leg0",
           "wall_s": wall_s, "outcome": "ok"}
    return json.dumps(row) + "\n"


def _board(values: dict[str, float]) -> dict[str, Any]:
    """A META_CONTROLLER.json whose delta_elog board prices the given KINDS."""
    return {"boards": {"delta_elog": {"status": "OK",
                                      "rows": [{"kind": k, "delta_elog_per_day": v}
                                               for k, v in values.items()]}}}


def test_a_winner_gets_more_and_the_loser_keeps_its_scout_floor(
        tmp_path: Path, monkeypatch: Any) -> None:
    _isolate(tmp_path, monkeypatch, meta={}, bandit={}, policy={}, ledger=_spare_ledger())
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
    # NEVER REDUCE MINING (standing order 2026-09-29): the floor is 1.0, so no leg loses seconds.
    assert cp.FLOOR >= 1.0
    for name, v in legs.items():
        assert v["factor"] >= 1.0 and v["planned_s"] >= v["base_s"], f"{name} was cut"
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
    _isolate(tmp_path, monkeypatch, meta={}, bandit={}, policy={}, ledger=_spare_ledger())
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


# ------------------------------------------------------------------ I3: jobs that declare
def test_a_leg_declares_cpu_deadline_and_evsi_and_the_order_reads_them(
        tmp_path: Path, monkeypatch: Any) -> None:
    """I3's two halves, joined. `job_lock.record_spec` accepted mb/cpu/deadline_s/evsi since the
    row's first half and NOTHING EVER CALLED IT; `admission_order` sorted on those four fields
    and nothing ever called that either. `applied_budget` now declares and `order` now ranks."""
    # THE SAME MODULE OBJECT `cycle_pricing` REACHES. `declare_spec` imports
    # `research.job_lock` first; `import job_lock` is a second, independent instance of the same
    # file, and monkeypatching that one leaves the real LOCK_ROOT in place -- the test would then
    # write into the desk's own lock directory and read back nothing.
    from research import job_lock as jl  # type: ignore[import-not-found]

    monkeypatch.setattr(jl, "LOCK_ROOT", tmp_path / "locks", raising=True)
    rec = {"leg": "legA", "base_s": 300, "applied_s": 420, "score": 3.5}
    cp.declare_spec("legA", rec)
    cp.declare_spec("legB", {"leg": "legB", "base_s": 300, "applied_s": 120, "score": 0.1})
    got = jl.declared_spec("legA")
    assert got["cpu"] == 1
    assert got["deadline_s"] == 420.0
    assert got["evsi"] == 3.5
    assert isinstance(got["mb"], int) and got["mb"] > 0
    # The scheduler can now rank two competing jobs, which is the whole of I3's gap sentence.
    assert [n for n, _s in jl.admission_order(["legB", "legA"])] == ["legA", "legB"]
    # And the cycle's own order uses it as the tie-break when the board prices both alike.
    table = {"legA": {"score": 1.0, "stale_h": 0.0}, "legB": {"score": 1.0, "stale_h": 0.0}}
    assert cp.order(["legB", "legA"], legs=table) == ["legA", "legB"]


def test_declaring_never_costs_the_leg_that_declared(tmp_path: Path, monkeypatch: Any) -> None:
    """A declaration that raised would take down the leg it was added to schedule."""
    from research import job_lock as jl  # type: ignore[import-not-found]

    monkeypatch.setattr(jl, "record_spec", lambda *_a, **_k: (_ for _ in ()).throw(OSError("x")),
                        raising=True)
    cp.declare_spec("legC", {"leg": "legC", "applied_s": 60, "score": 1.0})   # must not raise


# ------------------------------------------------ Tier-1 #10: spare compute, never a throttle
def _priced(monkeypatch: Any, prices: dict[str, float]) -> None:
    monkeypatch.setattr(cp, "_kind_legs", lambda: {}, raising=True)
    monkeypatch.setattr(cp, "_meta_prices", lambda: (dict(prices), ""), raising=True)
    monkeypatch.setattr(cp, "_bandit_prices", dict, raising=True)
    monkeypatch.setattr(cp, "_policy_factors", lambda: ({}, False), raising=True)
    monkeypatch.setattr(cp, "_evig_prices", lambda: ({}, "isolated"), raising=True)


def test_no_leg_is_ever_below_its_base(tmp_path: Path, monkeypatch: Any) -> None:
    """The principal's order: no miner is starved. The worst-priced leg keeps its whole base."""
    _isolate(tmp_path, monkeypatch, meta={}, bandit={}, policy={}, ledger=_spare_ledger())
    _priced(monkeypatch, {f"leg{i}": float(i) for i in range(10)})
    plan = cp.build_plan(BASES)
    assert cp.FLOOR == 1.0
    for leg, v in plan["legs"].items():
        assert v["planned_s"] >= v["base_s"], f"{leg} was cut below its base"
        assert v["factor"] >= 1.0 and v["price_factor"] >= 1.0


def test_unmeasured_spare_grants_nothing(tmp_path: Path, monkeypatch: Any) -> None:
    """A price is not a measurement of capacity: with no ledger row every leg runs at base."""
    _isolate(tmp_path, monkeypatch, meta={}, bandit={}, policy={})
    _priced(monkeypatch, {"leg0": 10.0, "leg9": -5.0})
    plan = cp.build_plan(BASES)
    assert plan["spare"]["status"] == "UNMEASURED"
    assert plan["legs"]["leg0"]["price_factor"] > 1.0
    assert plan["legs"]["leg0"]["planned_s"] == 600 and plan["spare_granted_s"] == 0


def test_the_grant_never_exceeds_the_measured_spare(tmp_path: Path, monkeypatch: Any) -> None:
    """A clock that is nearly full grants pro rata out of what is left, never more."""
    busy = (cp.CLOCK_S - 100.0) * cp.SPARE_WINDOW_H          # 100 s of spare per hour
    _isolate(tmp_path, monkeypatch, meta={}, bandit={}, policy={}, ledger=_spare_ledger(busy))
    _priced(monkeypatch, {f"leg{i}": float(i) for i in range(10)})
    plan = cp.build_plan(BASES)
    spare = plan["spare"]["spare_s"]["rest"]
    assert spare == pytest.approx(100.0, abs=0.5)
    assert 0 < plan["spare_granted_s"] <= spare + len(BASES)  # rounding, one second per leg
    assert all(v["planned_s"] >= v["base_s"] for v in plan["legs"].values())


def test_the_factory_contracts_are_a_price_source(tmp_path: Path, monkeypatch: Any) -> None:
    _isolate(tmp_path, monkeypatch, meta={}, bandit={}, policy={}, ledger=_spare_ledger())
    _priced(monkeypatch, {})
    monkeypatch.setattr(cp, "_factory_prices", lambda: ({"leg3": 0.9, "leg4": 0.1}, ""),
                        raising=True)
    plan = cp.build_plan(BASES)
    assert "factory_contracts" in plan["legs"]["leg3"]["priced_by"]
    assert plan["sources"]["factory_contracts"] is True
    assert plan["legs"]["leg3"]["planned_s"] > plan["legs"]["leg3"]["base_s"]
    assert plan["legs"]["leg4"]["planned_s"] == plan["legs"]["leg4"]["base_s"]


def test_the_north_star_prices_legs_directly(tmp_path: Path, monkeypatch: Any) -> None:
    """Effective independent alpha rank per compute hour is its own price source: the leg that
    buys the most independent alpha per hour is given more, and no leg is cut."""
    _isolate(tmp_path, monkeypatch, meta={}, bandit={}, policy={}, ledger=_spare_ledger())
    monkeypatch.setattr(cp, "_kind_legs", lambda: {}, raising=True)
    monkeypatch.setattr(cp, "_meta_prices", lambda: ({}, "none"), raising=True)
    monkeypatch.setattr(cp, "_bandit_prices", dict, raising=True)
    monkeypatch.setattr(cp, "_policy_factors", lambda: ({}, False), raising=True)
    monkeypatch.setattr(cp, "_alpha_rank_prices",
                        lambda: ({"leg2": 0.9, "leg4": 0.1, "leg6": 0.0}, ""), raising=True)
    plan = cp.build_plan(BASES)
    legs = plan["legs"]
    assert "alpha_rank" in legs["leg2"]["priced_by"]
    assert legs["leg2"]["factor"] > 1.0
    assert plan["sources"]["alpha_rank"] is True
    for name, v in legs.items():
        assert v["factor"] >= 1.0 and v["planned_s"] >= v["base_s"], f"{name} was cut"


def test_factory_contracts_publish_leg_independent_alpha(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    import factory_contracts as fc  # type: ignore[import-not-found]
    p = tmp_path / "FC.json"
    p.write_text(json.dumps({"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                             "leg_independent_alpha": {"deepen": 0.3, "mine": 0.1}}), "utf-8")
    got, why = fc.leg_alpha_rank(p)
    assert got == {"deepen": 0.3, "mine": 0.1} and why == ""
    p.write_text(json.dumps({"at": datetime.now(tz=UTC).isoformat(timespec="seconds")}), "utf-8")
    assert fc.leg_alpha_rank(p)[0] == {}


def test_alpha_rank_binds_both_ways_inside_the_floor(tmp_path: Path, monkeypatch: Any) -> None:
    """Bottom-quartile alpha rank withdraws a boost the other sources gave; top-quartile alpha
    rank earns a boost the other sources withheld; nothing ever drops below its base."""
    _isolate(tmp_path, monkeypatch, meta={}, bandit={}, policy={}, ledger=_spare_ledger())
    monkeypatch.setattr(cp, "_kind_legs", lambda: {}, raising=True)
    monkeypatch.setattr(cp, "_meta_prices",
                        lambda: ({"leg2": 1.0, "leg4": 0.0, "leg6": 0.5}, "ok"), raising=True)
    monkeypatch.setattr(cp, "_bandit_prices", dict, raising=True)
    monkeypatch.setattr(cp, "_policy_factors", lambda: ({}, False), raising=True)
    monkeypatch.setattr(cp, "_alpha_rank_prices",
                        lambda: ({"leg2": 0.0, "leg4": 1.0, "leg6": 0.5}, ""), raising=True)
    legs = cp.build_plan(BASES)["legs"]
    assert legs["leg2"]["price_factor"] == 1.0 and "capped" in legs["leg2"]["alpha_rank_bound"]
    assert legs["leg4"]["price_factor"] > 1.0 and "raised" in legs["leg4"]["alpha_rank_bound"]
    for name, v in legs.items():
        assert v["factor"] >= 1.0 and v["planned_s"] >= v["base_s"], f"{name} was cut"
