"""The Tier-5 residual organs: bottleneck law, research latency, alpha replenishment, the
drawdown-alpha miner, trade autopsies, portfolio bounties, the research auction and the research
dashboard -- each on synthetic inputs, a temporary registry and temporary artifacts only."""
from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import alpha_replenishment as ar  # noqa: E402
import bottleneck_law as bl  # noqa: E402
import drawdown_alpha_miner as dam  # noqa: E402
import portfolio_bounty as pb  # noqa: E402
import research_auction as ra  # noqa: E402
import research_dashboard as rd  # noqa: E402
import research_latency as rl  # noqa: E402
import trade_autopsy as ta  # noqa: E402

NOW = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)


@pytest.fixture
def registry(tmp_path: Path):
    from libs.moat import registry as rg
    p = tmp_path / "r.sqlite"
    p.touch()                      # exists -> no backup restore into the temp path
    rg.set_path(p)
    try:
        yield rg
    finally:
        rg.set_path(None)


# ------------------------------------------------------------------ bottleneck law
def test_bottleneck_binding_is_the_lowest_measured_ratio_and_shift_never_cuts() -> None:
    reg = {"discovered": 100, "converted": 60, "candidates": 60, "executable": 30, "judged": 3}
    roster = {"certified": 3, "forward": 3, "live": 1}
    trans = bl.transitions(reg, roster)
    b = bl.binding(trans)
    assert b is not None and b["stage"] == "executable->judged" and b["owner"] == "validate"
    shift = bl.compute_shift(b)
    assert shift["validate"] == round(min(2.0, 1.0 + (1.0 - 0.1)), 4)
    assert all(v >= 1.0 for v in shift.values()), "the law never cuts a department"
    # a transition with no input flow is UNMEASURED and can never bind
    trans0 = bl.transitions({"discovered": 0}, {"certified": 0, "forward": 0, "live": 0})
    assert bl.binding(trans0) is None and bl.compute_shift(None)["validate"] == 1.0


def test_bottleneck_build_reads_the_registry_and_publishes(tmp_path: Path, registry: Any) -> None:
    registry.enqueue_candidate(family="f", symbol="EURUSD", params={"a": 1}, origin="DESK")
    registry.enqueue_candidate(family="f", symbol="GBPUSD", params={"a": 2}, origin="DESK",
                               status="donated")
    doc = bl.build(now=NOW, sleeves_doc={"sleeves": [{"status": "LIVE"}, {"status": "STANDBY"}]},
                   survivors_doc={"survivors": {"a": {}, "b": {}}})
    assert doc["counts"]["candidates"] == 2 and doc["counts"]["live"] == 1
    assert doc["binding"] is not None and doc["headline"].startswith("binding")
    out = tmp_path / "B.json"
    bl.publish(doc, out)
    assert json.loads(out.read_text("utf-8"))["compute_shift"]
    assert any(m["category"] == "bottleneck_law" for m in registry.memories("bottleneck_law"))


# ------------------------------------------------------------------ research latency
def test_latency_stages_time_only_paired_stamps(registry: Any) -> None:
    did = registry.record_discovery(source_id="s1", source_type="paper", mechanism="carry",
                                    origin="EXTERNAL")
    did = did[0] if isinstance(did, tuple) else did
    registry.enqueue_candidate(family="carry", symbol="AUDJPY", params={}, origin="EXTERNAL",
                               discovery_id=str(did))
    stages = rl.registry_stages()
    by = {s["stage"]: s for s in stages}
    assert by["idea->cell"]["status"] == "MEASURED" and by["idea->cell"]["n"] == 1
    assert by["cell->verdict"]["status"] == "UNMEASURED" and by["cell->verdict"]["untimed"] == 1
    roster = rl.roster_stages(
        {"sleeves": [{"name": "A", "status": "LIVE", "promoted_at": "2026-09-10T00:00:00+00:00"}]},
        {"survivors": {"k": {"gated_at": "2026-09-01T00:00:00+00:00",
                             "shadow_spec": {"name": "A"}}}},
        {"A": "2026-09-03T00:00:00+00:00"})
    by2 = {s["stage"]: s for s in roster}
    assert by2["certified->forward"]["median_h"] == 48.0
    assert by2["forward->live"]["median_h"] == 7 * 24.0
    doc = rl.build(now=NOW, sleeves_doc={}, survivors_doc={}, first_rows={},
                   with_promotion=False)
    assert doc["n_measured_stages"] == 1 and "idea->cell" in doc["headline"]


# ------------------------------------------------------------------ alpha replenishment
def test_replenishment_target_follows_measured_decay() -> None:
    posterior = {"sleeves": [{"half_life_days": 14.0}, {"decay_p": "UNMEASURED"},
                             {"decay_lambda": math.log(2) / 14.0}]}
    live = [{"status": "LIVE", "promoted_at": (NOW - timedelta(days=2)).isoformat()}] + \
           [{"status": "LIVE", "promoted_at": (NOW - timedelta(days=30)).isoformat()}] * 3
    doc = ar.build(now=NOW, posterior=posterior, sleeves={"sleeves": live},
                   survivors={"survivors": {"x": {"gated_at": (NOW - timedelta(days=1)).isoformat()}}},
                   decay={"actions_taken": []})
    assert doc["decay"]["n_half_lives"] == 2 and doc["decay"]["n_unmeasured"] == 1
    assert doc["required_per_week"] == round(4 * (1 - math.exp(-7 / 14.0)), 3)
    assert doc["achieved"] == {"certified_7d": 1, "promoted_live_7d": 1, "retired_7d": 0,
                               "net_replenishment": 1}
    assert doc["status"] == "SHORT" and doc["gap"] > 0
    unm = ar.build(now=NOW, posterior={"sleeves": []}, sleeves={"sleeves": live},
                   survivors={}, decay={})
    assert unm["status"] == "UNMEASURED" and unm["required_per_week"] is None


# ------------------------------------------------------------------ drawdown-alpha miner
def _days(start: datetime, values: list[float]) -> list[tuple[str, float]]:
    return [((start + timedelta(days=i)).date().isoformat(), v) for i, v in enumerate(values)]


def test_episodes_are_peak_to_recovery_and_deepest_first() -> None:
    days = _days(NOW, [1, 1, -1, -1, -1, 1, 1, 1, 1, -2, -2, 1])
    eps = dam.episodes(days, min_depth=1.0)
    assert eps[0]["depth_r"] == 4.0 and eps[0]["recovered"] is False
    assert eps[1]["depth_r"] == 3.0 and eps[1]["recovered"] is True
    assert eps[1]["start"] == days[2][0] and eps[1]["end"] == days[7][0]


def test_miner_finds_a_sleeve_that_pays_inside_the_live_drawdown(tmp_path: Path,
                                                                  registry: Any) -> None:
    start = NOW - timedelta(days=40)
    live = _days(start, [0.5] * 10 + [-1.0] * 12 + [0.5] * 18)
    forward: list[tuple[str, str, float]] = []
    for i in range(40):
        day = (start + timedelta(days=i)).date().isoformat()
        forward.append(("payer", day, 1.5 if 10 <= i < 22 else -0.2))
        forward.append(("noise", day, 0.1 if i % 2 else -0.1))
    doc = dam.build(now=NOW, live=live, forward=forward)
    assert doc["windows"]["live"] and doc["n_tests"] > 0
    cands = {(r["basis"], r["sleeve"]) for r in doc["candidates"]}
    assert ("live", "payer") in cands
    assert all(r["verdict"] in ("CANDIDATE", "WATCH", "NONE", "UNMEASURED") for r in doc["rows"])
    assert doc["missions"] and doc["missions"][0]["source"] == "drawdown_alpha_miner"
    out = tmp_path / "D.json"
    dam.publish(doc, out, write_queue=False)
    assert out.exists() and doc["publish"]["registry_memories"] >= 1


# ------------------------------------------------------------------ trade autopsy
def _deal(**kw: Any) -> dict[str, Any]:
    base = {"time": "2026-09-07T17:04:15+00:00", "sleeve": "gold_asia", "symbol": "XAUUSD",
            "side": 0, "pl_quote": 37.68, "r_multiple": 0.0, "volume": 0.01, "commission": -0.02,
            "swap": 0.0, "deal": 1, "fill_price": 4351.42, "entry_price": 4395.1, "sl": 4360.0,
            "tp": 4460.0, "r_unreconstructible": False, "contract_size": 100.0,
            "risk_quote": -35.1, "account": 1, "server": "x", "account_kind": "live"}
    base.update(kw)
    return base


def test_autopsy_lessons_and_attribution() -> None:
    win = ta.autopsy(_deal(), None, shadow_exp=0.2)
    assert win["outcome"] == "win" and win["attribution"]["r_net"] == round(37.68 / 35.1, 4)
    assert win["counterfactual"]["opposite_side_r"] == -win["attribution"]["r_net"]
    assert win["counterfactual"]["excess_over_forward_expectancy"] == round(37.68 / 35.1 - 0.2, 4)
    loss = ta.autopsy(_deal(deal=2, pl_quote=-50.0), None, None)
    assert loss["lesson"] == "loss_beyond_stop"
    costly = ta.autopsy(_deal(deal=3, pl_quote=-1.0, commission=-0.8), None, None)
    assert costly["lesson"] == "cost_dominated"
    unrec = ta.autopsy(_deal(deal=4, r_unreconstructible=True, risk_quote=0.0), None, None)
    assert unrec["lesson"] == "unreconstructible" and unrec["attribution"]["cost_r"] == "UNMEASURED"
    dec = {"decision_id": "d1", "symbol": "XAUUSD", "sleeve": "gold_asia", "price": 4394.1,
           "decided_at": "2026-09-07T04:00:00+00:00", "world_state_id": "w1", "regime": "bull"}
    joined = ta.autopsy(_deal(deal=5), ta.match_decision(_deal(deal=5), [dec]), None)
    assert joined["state"]["world_state_id"] == "w1"
    assert joined["attribution"]["slippage_r"] == round(-(4395.1 - 4394.1) * 100 * 0.01 / 35.1, 4)


def test_autopsy_build_is_idempotent_and_appends(tmp_path: Path, registry: Any) -> None:
    deals = [_deal(deal=1), _deal(deal=2, pl_quote=-20.0)]
    doc = ta.build(now=NOW, deals=deals, decisions=[], sleeves_doc={"sleeves": [
        {"name": "gold_asia", "shadow_exp": 0.3}]}, done=set())
    assert doc["n_new"] == 2 and doc["root_causes"]["gold_asia"]["n"] == 2
    assert "verdict" in doc["root_causes"]["gold_asia"]
    ledger = tmp_path / "autopsies.jsonl"
    ta.publish(doc, tmp_path / "T.json", ledger)
    assert len(ledger.read_text("utf-8").splitlines()) == 2
    again = ta.build(now=NOW, deals=deals, decisions=[], sleeves_doc={},
                     done=ta.existing_deals(ledger))
    assert again["n_new"] == 0 and again["n_already_autopsied"] == 2


# ------------------------------------------------------------------ portfolio bounty
def _bounty_inputs() -> dict[str, dict[str, Any]]:
    return {
        "alloc": {"heat": {"shortfall": 0.03, "target": 0.2, "free_optimum": 0.39}},
        "exposure": {"book": {"gold": 0.8, "usd": 0.1, "carry": 0.1}, "n_eff_factor_bets": 1.4},
        "regimes": {"uncovered": ["global=bear|session=ASIA"], "n_uncovered": 1},
        "drawdown": {"crisis_cluster_empty": True, "candidates": []},
        "dd_miner": {"windows": {"live": [{"start": "2026-09-01", "end": "2026-09-05",
                                           "depth_r": 3.0}]}, "candidates": []},
        "ortho": {"hidden_dependence_pairs": [{"a": "x", "b": "y", "tail_lift": 2.5,
                                               "pearson": 0.0, "co_drawdown": 0.2}]},
        "session": {"dark_bands": ["00-04"], "held_heat": 0.18},
        "sleeves": {"sleeves": [{"symbol": "XAUUSD", "status": "LIVE"}]},
        "universe": {"XAUUSD": {"asset_class": "metals"}, "EURUSD": {"asset_class": "fx"}},
    }


def test_bounties_name_every_missing_payoff_shape_and_absent_inputs() -> None:
    doc = pb.build(now=NOW, **_bounty_inputs())
    kinds = doc["by_kind"]
    assert set(kinds) == {"drawdown_positive", "regime_uncovered", "factor_concentration",
                          "asset_class_absent", "session_dark", "heat_shortfall",
                          "tail_dependence"}
    fx = [b for b in doc["bounties"] if b["kind"] == "asset_class_absent"]
    assert fx and fx[0]["bounty_id"] == "bounty:asset_class_absent:fx"
    assert all(b["status"] == "open" and b["targets"] for b in doc["bounties"])
    assert doc["missions"][0]["mission_id"] == doc["bounties"][0]["bounty_id"]
    assert doc["unmeasured"] == []
    empty = pb.build(now=NOW, alloc={}, exposure={}, regimes={}, drawdown={}, dd_miner={},
                     ortho={}, session={}, sleeves={}, universe={})
    assert empty["n_open"] == 0 and len(empty["unmeasured"]) >= 5


def test_bounty_publish_writes_registry_and_event(tmp_path: Path, registry: Any,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.ops import events
    monkeypatch.setattr(events, "PATH", tmp_path / "events.jsonl")
    doc = pb.build(now=NOW, **_bounty_inputs())
    pb.publish(doc, tmp_path / "P.json", write_queue=False)
    assert doc["publish"]["registry_memories"] == doc["n_open"]
    rows = [json.loads(x) for x in (tmp_path / "events.jsonl").read_text("utf-8").splitlines()]
    assert rows and rows[-1]["kind"] == "PORTFOLIO_BOUNTY" and rows[-1]["n"] == doc["n_open"]
    assert len(registry.memories("portfolio_bounty")) == doc["n_open"]


# ------------------------------------------------------------------ research auction
def test_auction_is_two_sided_clipped_and_demand_aware() -> None:
    depts = ("discovery", "validate", "intel", "meta")
    hours = {"discovery": 10.0, "validate": 10.0, "intel": 10.0, "meta": 10.0}
    yields = {"discovery": 40, "validate": 40, "intel": 40, "meta": 40}
    flat = ra.clear(ra.bids(depts, hours, yields, {}, {}, {}))
    assert all(f == 1.0 for f in flat.values())
    shifted = ra.bids(depts, hours, yields, {"bounties": [{"targets": ["intel"]}] * 2},
                      {"compute_shift": {"validate": 1.9}}, {"gap": 2.0, "n_live": 4})
    f = ra.clear(shifted)
    assert f["validate"] > 1.0 and f["intel"] > 1.0 and f["meta"] < 1.0
    assert all(0.5 <= v <= 2.0 for v in f.values())
    logs = [math.log(v) for v in f.values()]
    assert abs(sum(logs)) < 0.6, "two-sided: winners are paid by losers, not by inflation"
    doc = ra.build(now=NOW, bounty={}, bottleneck={}, replenish={}, hours=hours, yields=yields,
                   departments=depts)
    assert doc["epoch_id"] == "2026-09-22T12" and doc["proposals"][0]["kind"] == \
        "research_budget_factor"


# ------------------------------------------------------------------ research dashboard
def test_dashboard_joins_and_renders(tmp_path: Path) -> None:
    doc = rd.build(now=NOW, gates={"n_cells": 10, "n_judged": 8, "survivors_passing_all": 1,
                                   "swept_at": NOW.isoformat()},
                   survivors={"survivors": {"a": {}}},
                   breadth={"effective": {"effective_breadth": 2.5}},
                   sleeves={"sleeves": [{"status": "LIVE"}, {"status": "STANDBY"}]},
                   organs={"portfolio_bounty": {"headline": "3 open"}}, with_registry=False)
    m = doc["metrics"]
    assert m["survivors"] == 1 and m["live_sleeves"] == 1 and m["forward_clocks"] == 1
    assert m["gauntlet_verdicts_per_day"] == 8 and m["effective_independent_bets"] == 2.5
    assert m["sources_alive"] == "UNMEASURED"
    assert doc["organs"]["portfolio_bounty"] == "3 open"
    assert doc["organs"]["research_auction"] == "UNMEASURED"
    page = rd.render(doc)
    assert page.startswith("# Research dashboard (derived") and "| survivors | 1 |" in page
    md = tmp_path / "RD.md"
    md.write_text(page, "utf-8")
    assert md.read_text("utf-8").count("|") > 40
