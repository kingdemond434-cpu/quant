"""THE EIGHT TIER-5 RESIDUAL ORGANS, each judged on the arithmetic it exists to do.

One test per organ, on pure functions with fixtures -- no registry, no tracked file, no clock.
What every one of them asserts beyond its own numbers: the organ NEVER cuts. A bounty is a
research REQUEST, an auction bid is two-sided and floored above zero, the bottleneck shift is
>= 1 for the department that binds and exactly 1.0 elsewhere, and the monoculture reading is
reported with `capped` false (GROWTH_GOVERNANCE Rule 1; the principal's 2026-09-08 order).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK / "research"), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import alpha_replenishment  # noqa: E402
import bottleneck_law  # noqa: E402
import drawdown_alpha_miner  # noqa: E402
import portfolio_bounty  # noqa: E402
import research_auction  # noqa: E402
import research_dashboard  # noqa: E402
import research_latency  # noqa: E402
import trade_autopsy  # noqa: E402


# ---------------------------------------------------------------- portfolio bounty (mandate 90)
def test_bounties_name_the_payoff_the_book_lacks_and_absence_is_unmeasured() -> None:
    rows, _unmeasured = portfolio_bounty.bounties(
        alloc={}, exposure={"book": {"usd_beta": 0.9, "gold_beta": 0.05}},
        regimes={"uncovered": ["risk_off_high_vol", "carry_unwind"], "n_uncovered": 2},
        drawdown={"crisis_cluster_empty": True, "candidates": []},
        dd_miner={"windows": {"live": [{"start": "2026-09-01", "end": "2026-09-05",
                                        "depth_r": 3.2}]}, "candidates": []},
        ortho={}, session={}, sleeves={}, universe={})
    kinds = {r["kind"] for r in rows}
    assert "drawdown_positive" in kinds, "an empty crisis cluster is the bounty this organ is for"
    assert "regime_uncovered" in kinds
    assert len([r for r in rows if r["kind"] == "regime_uncovered"]) == 2
    assert all(r["status"] == "open" and r["targets"] for r in rows), "a bounty routes somewhere"
    assert all("need" in r and r["evidence"] for r in rows), "a request with no reading is opinion"
    # absence is a verdict, never a silent zero
    _, missing = portfolio_bounty.bounties({}, {}, {}, {}, {}, {}, {}, {}, {})
    assert any("DRAWDOWN_ALPHA" in m for m in missing)
    assert any("REGIME_COVERAGE" in m for m in missing)


# --------------------------------------------------------------- research auction (mandate 110)
def test_auction_is_two_sided_and_never_clears_a_department_to_zero() -> None:
    hours = {"discovery": 10.0, "validate": 2.0, "intel": 4.0}
    yields = {"discovery": 10, "validate": 40, "intel": 0}
    rows = research_auction.bids(("discovery", "validate", "intel"), hours, yields,
                                 bounty={"bounties": [{"targets": ["validate"]}]},
                                 bottleneck={"compute_shift": {"validate": 2.0}},
                                 replenish={"gap": 3.0, "n_live": 3})
    assert rows["validate"]["bid"] > rows["discovery"]["bid"], \
        "the department that converts hours into enqueued work outbids the one that burns them"
    assert rows["intel"]["productivity"] < 1.0
    assert "nothing enqueued" in rows["intel"]["productivity_basis"]
    shares = research_auction.clear(rows)
    assert min(shares.values()) >= research_auction.FLOOR > 0.0, "no department is cleared to zero"
    assert max(shares.values()) <= research_auction.CEIL
    assert max(shares.values()) > 1.0, "a winner is funded ABOVE par: the auction is two-sided"
    # an unmeasured world is par everywhere, not a cut
    flat = research_auction.clear(research_auction.bids(
        ("a", "b"), {}, {}, bounty={}, bottleneck={}, replenish={}))
    assert set(flat.values()) == {1.0}


# ----------------------------------------------------------- bottleneck law (mandate 131 / 132)
def test_bottleneck_is_the_slowest_measured_stage_and_the_shift_only_adds() -> None:
    reg = {"discovered": 100, "converted": 90, "candidates": 80, "executable": 40, "judged": 4}
    roster = {"certified": 2, "forward": 2, "live": 1}
    trans = bottleneck_law.transitions(reg, roster)
    bind = bottleneck_law.binding(trans)
    assert bind is not None and bind["stage"] == "executable->judged"
    assert bind["backlog"] == 36 and 0.0 < float(bind["ratio"]) < 0.2
    shift = bottleneck_law.compute_shift(bind)
    assert shift[bind["owner"]] > 1.0, "compute moves TOWARD the binding stage"
    assert all(v == 1.0 for d, v in shift.items() if d != bind["owner"]), \
        "no department is shifted below par to pay for it"
    assert max(shift.values()) <= bottleneck_law.MAX_SHIFT
    # a funnel with no counts is UNMEASURED, not a bottleneck at zero
    assert bottleneck_law.binding(bottleneck_law.transitions({}, {})) is None
    assert set(bottleneck_law.compute_shift(None).values()) == {1.0}


# -------------------------------------------------------- drawdown-alpha miner (mandate 136)
def test_drawdown_episodes_and_the_multiplicity_charge_on_the_search() -> None:
    days = [("2026-09-01", 1.0), ("2026-09-02", -2.0), ("2026-09-03", -1.5),
            ("2026-09-04", 0.5), ("2026-09-05", 3.0), ("2026-09-06", -0.6)]
    eps = drawdown_alpha_miner.episodes(days, min_depth=1.0)
    assert eps and eps[0]["start"] == "2026-09-02" and eps[0]["trough"] == "2026-09-03"
    assert eps[0]["recovered"] is True and eps[0]["depth_r"] >= 3.0
    assert all(eps[i]["depth_r"] >= eps[i + 1]["depth_r"] for i in range(len(eps) - 1))
    assert drawdown_alpha_miner.episodes([], min_depth=1.0) == []
    # a sleeve searched against many windows is charged for the search
    assert drawdown_alpha_miner.expected_max_z(1) == 0.0
    assert drawdown_alpha_miner.expected_max_z(500) > drawdown_alpha_miner.expected_max_z(20) > 1.0
    thin = drawdown_alpha_miner._stats([0.4], [])
    assert thin["status"] == "UNMEASURED", "one observation inside a drawdown is not evidence"


# ------------------------------------------------------------- win/loss autopsy (mandate 97/98)
def test_every_closed_deal_gets_attribution_counterfactual_and_a_lesson() -> None:
    deal = {"deal": "77", "sleeve": "gold_asia", "symbol": "XAUUSD", "side": 0, "volume": 0.02,
            "contract_size": 100.0, "risk_quote": 20.0, "pl_quote": -30.0,
            "commission": -1.0, "swap": -0.5, "entry_price": 2401.0, "fill_price": 2389.0,
            "sl": 2390.0, "tp": 2425.0, "time": "2026-09-20T07:10:00+00:00"}
    decision = {"decision_id": "d1", "price": 2400.0, "world_state_id": "w7", "regime": "trend"}
    row = trade_autopsy.autopsy(deal, decision, shadow_exp=0.15)
    a, c = row["attribution"], row["counterfactual"]
    assert row["outcome"] == "loss" and row["lesson"] == "loss_beyond_stop"
    assert a["r_net"] < a["r_gross"], "costs make the net worse than the gross"
    assert a["cost_r"] < 0 and a["slippage_r"] != "UNMEASURED", "the fill is judged against intent"
    assert c["opposite_side_r"] == -a["r_net"] and c["stopped_out_r"] == -1.0
    assert c["excess_over_forward_expectancy"] < 0 and c["held_to_tp_r"] != "UNMEASURED"
    assert row["state"]["world_state_id"] == "w7" and row["state"]["regime"] == "trend"
    # no decision and no risk: the row still exists, and says what it could not measure
    bare = trade_autopsy.autopsy({"deal": "78", "r_unreconstructible": True}, None, None)
    assert bare["lesson"] == "unreconstructible"
    assert bare["attribution"]["cost_r"] == "UNMEASURED"
    assert bare["counterfactual"]["excess_over_forward_expectancy"] == "UNMEASURED"
    assert bare["state"]["regime"] == "UNMEASURED"


# ---------------------------------------------------------- research latency (mandate 133)
def test_latency_reports_percentiles_and_names_what_is_untimed() -> None:
    row = research_latency.summarise("idea->cell", [1.0, 2.0, 3.0, 40.0], untimed=7,
                                     why="", basis="registry")
    assert row["status"] == "MEASURED" and row["n"] == 4 and row["untimed"] == 7
    assert row["median_h"] == 2.5 and row["p90_h"] == 40.0 and row["max_h"] == 40.0
    empty = research_latency.summarise("forward->live", [], untimed=12,
                                       why="no promotion carries both stamps", basis="roster")
    assert empty["status"] == "UNMEASURED" and empty["why"] and empty["n"] == 0


# ------------------------------------------------------- alpha replenishment (mandate 134)
def test_required_survivors_follow_the_books_measured_decay() -> None:
    hls, unmeasured = alpha_replenishment.half_lives({"sleeves": [
        {"half_life_days": 30.0}, {"decay_lambda": 0.0231}, {"decay_p": 0.5}, {}]})
    assert len(hls) == 3 and unmeasured == 1
    assert 29.0 < hls[1] < 31.0, "a per-day hazard becomes log2/lambda days"
    doc = alpha_replenishment.build(
        posterior={"sleeves": [{"half_life_days": 14.0}, {"half_life_days": 14.0}]},
        survivors={"survivors": []}, decay={},
        sleeves={"sleeves": [{"status": "LIVE", "promoted_at": "2000-01-01T00:00:00+00:00"},
                             {"status": "LIVE"}, {"status": "STANDBY"}]})
    assert doc["status"] == "SHORT" and doc["required_per_week"] > 0 and doc["gap"] > 0
    assert doc["n_live"] == 2 and doc["n_forward"] == 1
    assert doc["decay"]["median_half_life_days"] == 14.0
    blind = alpha_replenishment.build(posterior={}, survivors={}, decay={}, sleeves={})
    assert blind["status"] == "UNMEASURED" and blind["required_per_week"] is None, \
        "an unmeasured decay is an unmeasured target, never a target of zero"


# ------------------------------------------------------- research dashboard (mandate 162)
def test_dashboard_reports_monoculture_and_never_caps_the_leader() -> None:
    hot = research_dashboard.lineage_concentration({"survivors": [
        {"cell": "XAUUSD session_range_breakout H1"}] * 9 + [{"family": "carry"}]})
    assert hot["status"] == "MEASURED" and hot["n_survivors"] == 10 and hot["n_families"] == 2
    assert hot["top_family"] == "session_range_breakout" and hot["top_share"] == 0.9
    assert 0.8 < hot["hhi"] <= 1.0 and hot["capped"] is False
    even = research_dashboard.lineage_concentration(
        {"survivors": {str(i): {"family": f"f{i}"} for i in range(4)}})
    assert even["hhi"] == 0.25 and even["capped"] is False
    blank = research_dashboard.lineage_concentration({})
    assert blank["status"] == research_dashboard.UNMEASURED and blank["capped"] is False


def test_dashboard_renders_the_markdown_it_publishes() -> None:
    md = research_dashboard.render({"at": "2026-09-22T00:00:00+00:00", "headline": "24/24",
                                    "metrics": {"live_sleeves": {"value": 40,
                                                                 "status": "MEASURED"}},
                                    "organs": {"bottleneck_law": "binding executable->judged"}})
    assert md.startswith("#") and "live_sleeves" in md and "2026-09-22" in md
    assert "bottleneck_law" in md, "the dashboard JOINS the hour's organs, it does not restate one"
