"""The judge's intake quota (principal, 2026-11-13 19:46Z): >= 90% non-exotic trials, exotics
earning up to 10% by yield, every family reached at its exploration share, and the 2x exotic
cost bar at the blind review."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import blind_reviewer as br  # noqa: E402
import market_quota as mq  # noqa: E402

NOW = datetime(2026, 11, 13, 20, 0, tzinfo=UTC)


def _spec(sym: str, fam: str, new: bool = True) -> dict:
    return {"sym": sym, "family": fam, "_never_judged": new}


def _row(cell: str, passed: bool, at: datetime) -> str:
    return json.dumps({"cell": cell, "at": at.isoformat(timespec="seconds"), "passed": passed,
                       "terminal_gate": "PASS" if passed else "deflated_sharpe"}) + "\n"


@pytest.mark.parametrize(("sym", "group"), [
    ("USDZAR", "exotic"), ("EURNOK", "exotic"), ("USDCNH", "exotic"), ("EURUSD", "fx"),
    ("XAUUSD", "gold"), ("XAGUSD", "metals"), ("US500", "indices")])
def test_group_of_names_the_exotics_by_registry_or_currency(sym: str, group: str) -> None:
    assert mq.group_of(sym) == group


def test_group_of_registry_class_wins() -> None:
    assert mq.group_of("FOOBAR", asset_class="forex exotics") == "exotic"
    assert mq.group_of("EURUSD", asset_class="forex") == "fx"


def _ledger(tmp_path: Path, rows: list[str]) -> Path:
    p = tmp_path / "gate_verdict_ledger.jsonl"
    p.write_text("".join(rows), encoding="utf-8")
    return p


def test_scan_is_incremental_and_counts_ruled_trials_and_distinct_edges(tmp_path: Path) -> None:
    t = NOW - timedelta(hours=2)
    led = _ledger(tmp_path, [
        _row("EURUSD.carry.p=a", True, t), _row("EURUSD.carry.p=b", True, t),   # one edge
        _row("USDZAR.carry.p=c", False, t),
        json.dumps({"cell": "GBPUSD.carry.p=d", "at": t.isoformat(),
                    "terminal_gate": "UNKNOWN", "unknown_reason": "never_fires"}) + "\n",
    ])
    state = tmp_path / "scan.json"
    st = mq.scan_ledger(led, state, now=NOW)
    g = mq.yields(st, "groups")
    assert st["status"] == "MEASURED"
    assert g["fx"]["trials"] == 2 and g["fx"]["edges"] == 1           # UNKNOWN is not a trial
    assert g["exotic"]["trials"] == 1 and g["exotic"]["edges"] == 0
    with led.open("a", encoding="utf-8") as fh:
        fh.write(_row("XAUUSD.carry.p=e", True, t))
    st2 = mq.scan_ledger(led, state, now=NOW)
    assert mq.yields(st2, "groups")["gold"]["trials"] == 1
    assert mq.yields(st2, "groups")["fx"]["trials"] == 2             # not double-counted
    assert st2["families_ever"]["carry"] == 4


def test_scan_rescans_a_rewritten_ledger(tmp_path: Path) -> None:
    t = NOW - timedelta(hours=1)
    led = _ledger(tmp_path, [_row("EURUSD.carry.p=a", True, t)] * 3)
    state = tmp_path / "scan.json"
    mq.scan_ledger(led, state, now=NOW)
    led.write_text(_row("EURUSD.carry.p=a", True, t), encoding="utf-8")
    assert mq.yields(mq.scan_ledger(led, state, now=NOW), "groups")["fx"]["trials"] == 1


def test_exotic_share_is_earned_capped_and_never_zero() -> None:
    good = {"exotic": {"trials": 1000, "edges": 50, "yield": 0.05},
            "fx": {"trials": 1000, "edges": 10, "yield": 0.01},
            "_pooled": {"trials": 2000, "edges": 60, "yield": 0.03}}
    plan = mq.shares({"exotic", "fx"}, good)
    assert plan["shares"]["exotic"] == pytest.approx(mq.EXOTIC_CAP)   # capped, not 5x
    bad = {"exotic": {"trials": 5000, "edges": 0, "yield": 0.0},
           "fx": {"trials": 1000, "edges": 10, "yield": 0.01},
           "_pooled": {"trials": 6000, "edges": 10, "yield": 0.0017}}
    plan = mq.shares({"exotic", "fx"}, bad)
    assert plan["shares"]["exotic"] == pytest.approx(mq.EXOTIC_FLOOR)  # decays, never zero
    assert sum(plan["shares"].values()) == pytest.approx(1.0)


def test_gold_and_indices_get_the_breadth_gap_weight() -> None:
    flat = {"_pooled": {"trials": 0, "edges": 0, "yield": 0.0}}
    plan = mq.shares({"fx", "gold", "indices"}, flat)
    assert plan["shares"]["gold"] == pytest.approx(1.5 * plan["shares"]["fx"])
    assert plan["shares"]["indices"] == pytest.approx(1.5 * plan["shares"]["fx"])


def _quota(specs: list[dict], tmp_path: Path, st: dict | None = None) -> tuple:
    st = st or {"status": "MEASURED", "days": {}, "hours": {}, "families_ever": {}}
    return mq.apply_quota(specs, st=st, now=NOW, out_path=tmp_path / "MARKET_QUOTA.json")


def test_every_prefix_holds_at_most_ten_percent_exotic(tmp_path: Path) -> None:
    specs = ([_spec("USDZAR", "carry")] * 500 + [_spec("EURUSD", "carry")] * 300
             + [_spec("XAUUSD", "asia_momentum")] * 200)
    ordered, held, rep = _quota(specs, tmp_path)
    assert len(ordered) + len(held) == len(specs)                     # nothing dropped
    assert all(mq.is_exotic(sp["sym"]) for sp in held)
    for k in (20, 100, 400, len(ordered)):
        head = ordered[:k]
        share = sum(1 for sp in head if mq.is_exotic(sp["sym"])) / len(head)
        assert share <= mq.EXOTIC_CAP + 1.0 / k
    assert rep["intake_exotic_share"] <= mq.EXOTIC_CAP + 1e-9
    assert json.loads((tmp_path / "MARKET_QUOTA.json").read_text())["held_exotic"] == len(held)


def test_a_family_that_sorts_last_is_in_every_short_prefix(tmp_path: Path) -> None:
    # The Auditor's case: the sealed keep arrives family-BLOCKED, so a short prefix (the gate-room
    # cut) used to hold one family only.
    specs = ([_spec("EURUSD", "session_range_breakout")] * 1000
             + [_spec("EURUSD", "conditioning_model")] * 30
             + [_spec("GBPUSD", "usd_session_shock")] * 30)
    ordered, held, _ = _quota(specs, tmp_path)
    assert not held
    head = {sp["family"] for sp in ordered[:10]}
    assert head == {"session_range_breakout", "conditioning_model", "usd_session_shock"}


def test_never_judged_cells_stay_ahead_of_rejudges(tmp_path: Path) -> None:
    specs = ([_spec("EURUSD", "carry", new=False)] * 20 + [_spec("XAUUSD", "carry")] * 20)
    ordered, _, _ = _quota(specs, tmp_path)
    assert all(sp["_never_judged"] for sp in ordered[:20])


def test_order_inside_a_family_is_the_sealed_order(tmp_path: Path) -> None:
    specs = [dict(_spec("EURUSD", "carry"), i=i) for i in range(50)]
    ordered, _, _ = _quota(specs, tmp_path)
    assert [sp["i"] for sp in ordered] == list(range(50))


def test_an_exotic_only_intake_sends_nothing(tmp_path: Path) -> None:
    ordered, held, _ = _quota([_spec("USDZAR", "carry")] * 10, tmp_path)
    assert ordered == [] and len(held) == 10


def test_realised_split_flags_a_breach_and_names_never_ruled_families(tmp_path: Path) -> None:
    t = NOW - timedelta(hours=1)
    led = _ledger(tmp_path, [_row("USDZAR.carry.p=a", False, t)] * 3
                  + [_row("EURUSD.carry.p=b", False, t)] * 7)
    st = mq.scan_ledger(led, tmp_path / "s.json", now=NOW)
    out = mq.realised_split(st, now=NOW, live_families={"carry", "conditioning_model"})
    assert out["status"] == "BREACH" and out["exotic_share"] == pytest.approx(0.3)
    assert out["families_never_ruled"] == ["conditioning_model"]


def test_family_funnel_names_where_a_family_vanished() -> None:
    a, b = _spec("EURUSD", "carry"), _spec("EURUSD", "triangle")
    f = mq.family_funnel({"docket": [a, b], "sealed_keep": [a, b], "keyed": [a],
                          "cold": [a], "held_deferred": [], "built": [a]})
    assert f["not_built_this_round"] == {"triangle": "1 at sealed_keep, 0 at keyed"}


# --------------------------------------------------------------- the exotic cost bar (review)

def test_judge_vetoes_an_exotic_that_dies_at_twice_its_costs() -> None:
    cert = {"expectancy": 0.3, "t": 4.0}
    rep = {"n": 60, "expectancy": 0.3, "t": 4.0,
           "exotic_cost_bar": {"status": "MEASURED", "mult": 2.0, "spread_pts": 300,
                               "n": 60, "expectancy": -0.05, "t": -0.4}}
    verdict, why = br.judge(cert, rep, {"blocking": False})
    assert verdict == br.VETO and "EXOTIC COST BAR" in why[0]
    rep["exotic_cost_bar"]["expectancy"] = 0.1
    assert br.judge(cert, rep, {"blocking": False})[0] == br.PASS


def test_doubled_costs_double_the_charges_and_leave_a_credit() -> None:
    from mt5desk.engine import Costs
    c = Costs.from_symbol({"median_spread_pts": 100.0, "tick_size": 0.0001,
                           "contract_size": 1e5, "tick_value": 10.0})
    import dataclasses
    charged = dataclasses.replace(c, swap_per_lot_per_night=4.0)
    d = br.doubled_costs(charged)
    assert d.spread_per_lot == pytest.approx(2 * charged.spread_per_lot)
    assert d.swap_per_lot_per_night == pytest.approx(8.0)
    assert d.commission_per_lot == charged.commission_per_lot          # contractual, unchanged
    credit = dataclasses.replace(c, swap_per_lot_per_night=-4.0)
    assert br.doubled_costs(credit).swap_per_lot_per_night == pytest.approx(-4.0)


def test_cost_bar_is_silent_for_a_non_exotic() -> None:
    assert br.exotic_cost_bar(None, {}, {}, None, "EURUSD") is None


def test_exotic_certificates_are_reviewed_first(tmp_path: Path) -> None:
    keys = ["h.EURUSD.carry.p=a", "h.USDZAR.carry.p=b", "h.AUDUSD.carry.p=c"]
    order = br.order_cells(keys, tmp_path / "none.jsonl")
    assert order[0] == "h.USDZAR.carry.p=b"
