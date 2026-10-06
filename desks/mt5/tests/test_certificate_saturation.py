"""Anti-saturation law (2026-10-05): the certificate saturation map and every organ reading it.

Each consumer is proven here against a synthetic canon shaped like the box's: hundreds of
certificates that are parameter variants of one mechanism on one factor. Breadth decides ORDER and
BUDGET; nothing in this file may show a row dropped or a gate moved.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import breadth_ladder as bl  # noqa: E402
import breadth_rotation as brot  # noqa: E402
import certificate_saturation as cs  # noqa: E402
import docket_keff as dk  # noqa: E402
import judge_coverage as jc  # noqa: E402
import portfolio_bounty as pb  # noqa: E402
import research_auction as ra  # noqa: E402

from libs.research import breadth_credit as bc  # noqa: E402

USD = ("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD")
PAIRS = (*USD, "USDCHF", "USDJPY")


def _cert(sym: str, fam: str, params: dict, sel: str = "london", sharpe: float = 0.2) -> dict:
    return {"sym": sym, "cell": f"{sym}.{fam}", "gated_at": "2026-09-01T00:00:00+00:00",
            "gates": {"walk_forward": {"oos_sharpe": sharpe}},
            "shadow_spec": {"symbol": sym, "selector": sel, "family": fam, "condition": None,
                            "params": params}}


def _canon_840() -> dict:
    """840 certificates: one mechanism, seven FX pairs, 120 parameter variants each."""
    sv = {}
    for i in range(840):
        sv[f"c{i}"] = _cert(PAIRS[i % 7], "session_range_breakout",
                            {"rr": 1 + (i // 7) % 10 * 0.25, "wait_bars": 4 + (i // 70)})
    return {"survivors": sv}


def _build(canon: dict, **kw) -> dict:
    args = {"shadow": {}, "sleeves": {}, "judged": {}, "coupling_tab": {}, "residual": {},
            "forward_daily": {}, "book": {}, "previous": {}, "loader": lambda s: None}
    args.update(kw)
    return cs.build(canon=canon, **args)


@pytest.fixture(scope="module")
def sat() -> dict:
    return _build(_canon_840())


# ------------------------------------------------------------------ the map itself
def test_box_shaped_canon_saturates_and_reports_n_effective_beside_n_cert(sat: dict) -> None:
    cert = sat["certificates"]
    assert sat["status"] == cs.MEASURED
    assert cert["n_certificates"] == 840
    # 840 nominal certificates are fewer than two effective bets: variants count once
    assert cert["n_effective_certificates"] < 2.5
    assert cert["n_strategy_variants"] == 7
    assert cert["effective_over_nominal"] < 0.01
    states = {k: v["state"] for k, v in sat["clusters"].items()}
    usd = [k for k in states if "/USD/" in k]
    assert usd and states[usd[0]] == "SATURATED"
    assert cert["n_saturated_clusters"] >= 1
    # unmeasured forward evidence never reads as zero streams
    assert cert["n_independent_forward_streams"] is None


def test_empty_canon_is_unmeasured_not_zero() -> None:
    doc = cs.build(canon={"survivors": {}})
    assert doc["status"] == cs.UNMEASURED
    assert doc["certificates"]["n_effective_certificates"] is None


def test_novelty_credit_is_the_preregistered_monotone_function() -> None:
    assert cs.novelty_credit(0.0) == 1.0
    assert cs.novelty_credit(3.0) == pytest.approx(0.5)
    vals = [cs.novelty_credit(x) for x in (0, 1, 2, 5, 40)]
    assert vals == sorted(vals, reverse=True)


def test_same_factor_rename_is_a_duplicate_and_a_new_factor_is_not(sat: dict) -> None:
    sc = cs.Scorer(sat)
    rename = sc.score_row({"symbol": "USDSEK", "family": "session_range_breakout",
                           "params": {"rr": 2.0}, "selector": "london", "source": "miner_x"})
    clone = sc.score_row({"symbol": "EURUSD", "family": "session_range_breakout",
                          "params": {"rr": 9.0}, "selector": "london", "source": "miner_x"})
    gold = sc.score_row({"symbol": "XAUUSD", "family": "session_range_breakout",
                         "params": {"rr": 2.0}, "selector": "london", "source": "miner_x"})
    fresh = sc.score_row({"symbol": "UKOIL", "family": "overnight_gap_decay", "params": {},
                          "source": "miner_y"})
    assert rename["duplicate"] and clone["duplicate"]
    assert rename["novelty_credit"] < 0.5 and clone["novelty_credit"] < 0.5
    assert not gold["duplicate"] and "E" in gold["exceptions"]
    assert gold["novelty_credit"] > rename["novelty_credit"]
    assert fresh["novelty_credit"] == 1.0 and not fresh["saturated_ground"]


def test_quality_rows_take_the_quality_channel_not_the_duplicate_tail(sat: dict) -> None:
    sc = cs.Scorer(sat)
    q = sc.score_row({"symbol": "EURUSD", "family": "session_range_breakout",
                      "params": {"rr": 3.0}, "selector": "london", "source": "execution_cost"})
    assert q["channel"] == "QUALITY" and not q["duplicate"] and "G" in q["exceptions"]


def test_unknown_axis_agrees() -> None:
    a = cs.axes_of("EURUSD", "session_range_breakout", {}, timeframe="H1", session="london")
    b = dict(a)
    b["regime"] = cs.UNKNOWN
    assert cs.similarity(a, b) == pytest.approx(1.0)


# ------------------------------------------------------------------ forward evidence
def _days(n: int) -> list[str]:
    return [f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}" for i in range(n)]


def test_forward_dependence_needs_its_sample_floor() -> None:
    rng = np.random.default_rng(0)
    a, b = rng.normal(size=120), rng.normal(size=120)
    d = _days(120)
    full = cs.forward_dependence({"x": dict(zip(d, a, strict=True)),
                                  "y": dict(zip(d, a + 0.01 * b, strict=True)),
                                  "z": dict(zip(d, b, strict=True))})
    states = {(p["a"], p["b"]): p["state"] for p in full["pairs"]}
    assert states[("x", "y")] == "DEPENDENT" and states[("x", "z")] == "INDEPENDENT"
    assert full["n_independent_streams"] == 2
    short = cs.forward_dependence({"x": dict(zip(d[:10], a[:10], strict=True)),
                                   "y": dict(zip(d[:10], a[:10], strict=True))})
    assert short["status"] == cs.UNMEASURED and short["n_independent_streams"] is None


def test_forward_dependence_revokes_structural_credit_only_on_evidence() -> None:
    canon = {"survivors": {"a": _cert("EURUSD", "session_range_breakout", {}),
                           "b": _cert("XAUUSD", "overnight_gap_decay", {}, sel="asia")}}
    base = _build(canon)
    rng = np.random.default_rng(1)
    x = rng.normal(size=120)
    d = _days(120)
    same = {"EURUSD_session_range_breakout_london": dict(zip(d, x, strict=True)),
            "XAUUSD_overnight_gap_decay_asia": dict(zip(d, x, strict=True))}
    rev = _build(canon, forward_daily=same)
    assert rev["revocations"]
    assert (rev["certificates"]["n_effective_certificates"]
            < base["certificates"]["n_effective_certificates"])
    low = {k: dict(list(v.items())[:10]) for k, v in same.items()}
    kept = _build(canon, forward_daily=low)
    assert not kept["revocations"]
    assert (kept["certificates"]["n_effective_certificates"]
            == base["certificates"]["n_effective_certificates"])


def test_empty_cluster_prior_decays_with_meaningful_effort() -> None:
    doc = _build(_canon_840(), judged={("USDCAD", "lead_lag"): 3000, ("EURUSD", "lead_lag"): 3000})
    pri = doc["empty_cluster_priors"]["cross_asset_lead_lag"]
    assert pri["status"] == "SEARCHED_EMPTY" and pri["decay"] < 1.0
    decay, _why = dk.empty_prior_decay(doc)
    assert decay["cross_asset_lead_lag"] == pri["decay"]
    untouched = _build(_canon_840())["empty_cluster_priors"]["cross_asset_lead_lag"]
    assert untouched["decay"] == 1.0


def test_docket_keff_absent_map_leaves_every_bonus_whole() -> None:
    decay, why = dk.empty_prior_decay({}, read_artifacts=False)
    assert decay == {} and "full weight" in why


# ------------------------------------------------------------------ docket order
def _docket() -> list[dict]:
    rows = []
    for i in range(60):
        rows.append({"_cell": f"dup{i}", "family": "session_range_breakout", "symbol": USD[i % 5],
                     "params": {"rr": 1 + i}, "selector": "london", "source": "miner_x",
                     "premortem": {"p_survivor": 0.5},
                     "first_seen": f"2026-10-01T{i // 60:02d}:{i % 60:02d}"})
    for i in range(10):
        rows.append({"_cell": f"q{i}", "family": "session_range_breakout", "symbol": "EURUSD",
                     "params": {"rr": 50 + i}, "selector": "london", "source": "execution_cost",
                     "premortem": {"p_survivor": 0.5}, "first_seen": f"2026-10-02T00:{i:02d}"})
    for i in range(10):
        rows.append({"_cell": f"new{i}", "family": "session_range_breakout",
                     "symbol": ("XAUUSD", "US500")[i % 2], "params": {"rr": 1 + i},
                     "selector": "london", "source": "miner_y",
                     "premortem": {"p_survivor": 0.5}, "first_seen": f"2026-10-03T00:{i:02d}"})
    return rows


def test_stamp_never_drops_and_coverage_order_sends_duplicates_to_the_tail(sat: dict) -> None:
    rows = _docket()
    ev = cs.stamp(rows, sat)
    assert ev["status"] == cs.MEASURED
    assert all("_sat" in r and "_dup" in r and "_satq" in r for r in rows)
    out = jc.coverage_order(rows, {"session_range_breakout": 1}, quality=0.2)
    assert len(out) == len(rows) and {r["_cell"] for r in out} == {r["_cell"] for r in rows}
    head = [r["_cell"] for r in out[:20]]
    # every non-duplicate breadth row precedes every strong duplicate
    last_new = max(i for i, r in enumerate(out) if r["_cell"].startswith("new"))
    first_dup = min(i for i, r in enumerate(out) if r.get("_dup"))
    assert last_new < first_dup
    # the quality channel holds its protected share of the head
    assert sum(1 for c in head if c.startswith("q")) >= 3
    # and the legacy order is still one flag away
    legacy = jc.coverage_order(rows, {"session_range_breakout": 1}, use_saturation=False)
    assert len(legacy) == len(rows)


def test_unstamped_rows_rank_exactly_as_before() -> None:
    rows = _docket()
    a = [r["_cell"] for r in jc.coverage_order([dict(r) for r in rows], {"x": 1})]
    b = [r["_cell"] for r in jc.coverage_order([dict(r) for r in rows], {"x": 1},
                                               use_saturation=False)]
    assert a == b


def test_stamp_feedback_names_each_producers_duplicate_share(sat: dict, tmp_path: Path,
                                                             monkeypatch) -> None:
    rows = _docket()
    ev = cs.stamp(rows, sat)
    prod = ev["producers"]
    assert prod["miner_x"]["duplicate_share"] > 0.5
    assert prod["miner_y"]["duplicate_share"] == 0.0
    monkeypatch.setattr(cs, "load", lambda *a, **k: (sat, "fresh"))
    path = tmp_path / "BREADTH_FEEDBACK.json"
    for _ in range(cs.RETARGET_PATIENCE):
        cs.write_feedback(ev, path=path)
    doc = json.loads(path.read_text("utf-8"))
    states = {k: v["state"] for k, v in doc["producers"].items()}
    assert states["miner_x"] == "PARK_CANDIDATE" and states["miner_y"] != "PARK_CANDIDATE"
    assert doc["duplicate_share"] is not None


def test_quality_share_reads_the_ladder_split(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(jc, "REPORTS", tmp_path)
    assert jc.quality_share() == jc.QUALITY_SHARE_DEFAULT
    (tmp_path / "BREADTH_LADDER.json").write_text(
        json.dumps({"budget_split": {"split": {"B": 0.37}}}), "utf-8")
    assert jc.quality_share() == pytest.approx(0.37)
    (tmp_path / "BREADTH_LADDER.json").write_text(
        json.dumps({"budget_split": {"split": {"B": 0.99}}}), "utf-8")
    assert jc.quality_share() == jc.QUALITY_SHARE_BOUNDS[1]


def test_family_factor_uses_the_effective_basis(sat: dict) -> None:
    rows = _docket()
    cs.stamp(rows, sat)
    rows.append({"family": "overnight_gap_decay", "symbol": "UKOIL", "_sat": 1.0})
    f = cs.family_factor(rows)
    assert f["overnight_gap_decay"] > f["session_range_breakout"]


# ------------------------------------------------------------------ producers
def test_rotation_tier_puts_fresh_ground_first(sat: dict) -> None:
    sc = cs.Scorer(sat)
    assert brot.saturation_tier("UKOIL", "session_range_breakout", sc) \
        < brot.saturation_tier("EURUSD", "session_range_breakout", sc)
    assert brot.saturation_tier("EURUSD", "session_range_breakout", None) == 0.0


def test_bandit_duplicate_tax_lowers_the_arms_credit() -> None:
    fb = {"producers": {"src_a": {"rows": 400, "duplicate_candidates": 360},
                        "src_b": {"rows": 400, "duplicate_candidates": 0},
                        "src_tiny": {"rows": 2, "duplicate_candidates": 2}}}
    dups = bc.duplicate_shares(fb, lambda s: {"src_a": "arm_a", "src_b": "arm_b",
                                              "src_tiny": "arm_t"}.get(s), min_rows=50)
    assert dups["arm_a"]["share"] == pytest.approx(0.9) and "arm_t" not in dups
    doc = {"effective": {"n_nominal": 30, "effective_breadth": 4.0}}
    assert bc.book_state(doc)["status"] == bc.MEASURED
    taxed = bc.credits(["arm_a", "arm_b"], doc=doc, duplicates=dups)
    plain = bc.credits(["arm_a", "arm_b"], doc=doc)
    assert taxed["arms"]["arm_a"]["rho_to_book"] > plain["arms"]["arm_a"]["rho_to_book"]
    assert taxed["credit"]["arm_a"] <= plain["credit"]["arm_a"]


def test_deepseek_seat_receives_facts_not_rankings(sat: dict, monkeypatch) -> None:
    brief = cs.producer_brief("deepseek", doc=sat, feedback={})
    assert brief["desk_owns"]["n_certificates"] == 840
    assert brief["saturated_clusters"] and brief["open_breadth_debts"]
    from libs.ops.deepseek_cycle import cold_context
    kept = cold_context({"desk_breadth": brief})
    assert "desk_breadth" not in kept["removed_keys"]


# ------------------------------------------------------------------ budget and bounties
def test_budget_split_floors_caps_and_stall_heat() -> None:
    calm = bl.budget_split({"fired": [], "mode": "BALANCED"})
    assert calm["split"] == bl.BASE_SPLIT
    hot = bl.budget_split({"fired": ["stall", "duplicates_rising"], "mode": "EXPLORE"})
    assert hot["split"]["A"] > calm["split"]["A"] and hot["split"]["C"] > calm["split"]["C"]
    for split in (calm["split"], hot["split"]):
        assert sum(split.values()) == pytest.approx(1.0, abs=1e-3)
        assert all(bl.SPLIT_FLOOR - 1e-9 <= v <= bl.SPLIT_CAP + 1e-9 for v in split.values())
    extreme = bl._clamp_split({"A": 1000.0, "B": 1e-6, "C": 1e-6, "D": 1e-6})
    assert extreme["A"] == bl.SPLIT_CAP and min(extreme.values()) >= bl.SPLIT_FLOOR


def test_temperature_reads_measured_inputs_only() -> None:
    t = bl.temperature({"status": "UNMEASURED", "why": "x"}, {}, {}, {}, [])
    assert t["mode"] == "BALANCED" and not t["fired"] and len(t["unmeasured"]) == 5
    t = bl.temperature({"status": "MEASURED", "per_hour": 0.0}, {}, {}, {}, [])
    assert t["mode"] == "EXPLORE"
    t = bl.temperature({"status": "MEASURED", "per_hour": 0.2},
                       {"certificates": {"median_validated_edge_recent": 0.1,
                                         "median_validated_edge_prior": 0.2}}, {}, {}, [])
    assert t["mode"] == "DEEPEN"
    hist = [{"n_structural_clusters": 3, "n_effective_certificates": 2.0},
            {"n_structural_clusters": 9, "n_effective_certificates": 2.0}]
    t = bl.temperature({"status": "MEASURED", "per_hour": 0.2}, {}, {}, {}, hist)
    assert t["mode"] == "FALSIFY"


def test_research_budget_factor_follows_the_split() -> None:
    hot = {"factors": {}, "budget_split": bl.budget_split({"fired": ["stall"]})}
    assert bl.budget_factor("frontier_unknowns", hot) > 1.0
    assert bl.budget_factor("deepen", hot) < 1.0
    assert bl.budget_factor("deepen", {}) == 1.0
    assert bl.FACTOR_CLIP[0] <= bl.budget_factor("breadth_sweep", hot) <= bl.FACTOR_CLIP[1]


def test_breadth_debts_become_bounties_that_raise_auction_bids(sat: dict) -> None:
    rows, _unmeasured = pb.bounties({}, {}, {}, {}, {}, {}, {}, {}, {}, sat)
    debts = [b for b in rows if b["kind"] == "breadth_debt"]
    assert 0 < len(debts) <= pb.MAX_PER_KIND
    _, absent = pb.bounties({}, {}, {}, {}, {}, {}, {}, {}, {}, {})
    assert "CERTIFICATE_SATURATION.breadth_debts absent" in absent
    deps = ("discovery", "validate")
    with_b = ra.bids(deps, {}, {}, {"bounties": debts}, {}, {})
    without = ra.bids(deps, {}, {}, {"bounties": []}, {}, {})
    assert with_b["discovery"]["bid"] > without["discovery"]["bid"]
    assert with_b["validate"]["bid"] == without["validate"]["bid"]


def test_saturation_map_round_trips_through_publish_and_load(sat: dict, tmp_path: Path) -> None:
    path = cs.publish(sat, tmp_path / "CERTIFICATE_SATURATION.json")
    doc, why = cs.load(path)
    assert why == "fresh" and doc is not None
    assert doc["certificates"]["n_certificates"] == 840
    stale, why = cs.load(path, now=datetime(2030, 1, 1, tzinfo=UTC))
    assert stale is None and "old" in why


# ------------------------------------------------------------------ the clock and the hurdle
def test_alpha_fitness_exposure_reads_the_saturation_map(sat: dict, monkeypatch) -> None:
    from libs.research import alpha_fitness as af
    from research import certificate_saturation as rcs
    monkeypatch.setattr(rcs, "_DEFAULT", [rcs.Scorer(sat)])
    crowded = af._saturation_exposure("session_range_breakout", {"instrument": "EURUSD"})
    empty = af._saturation_exposure("overnight_gap_decay", {"instrument": "UKOIL"})
    assert crowded is not None and empty is not None
    assert crowded[0] > 0.5 and empty[0] == 0.0
    assert af._saturation_exposure("session_range_breakout", {}) is None


def test_alpha_breadth_leg_publishes_the_map(sat: dict, tmp_path: Path, monkeypatch) -> None:
    import alpha_breadth as ab

    from research import certificate_saturation as rcs
    monkeypatch.setattr(rcs, "build", lambda **k: dict(sat))
    monkeypatch.setattr(rcs, "REPORT", tmp_path / "CERTIFICATE_SATURATION.json")
    monkeypatch.setattr(ab, "daily_sleeve_returns", lambda: {})
    monkeypatch.setattr(ab, "_daily_panel", lambda syms: ({}, {}))
    out = ab.certificate_saturation_pass()
    assert out["status"] == cs.MEASURED
    assert out["certificates"]["n_certificates"] == 840
    published = json.loads((tmp_path / "CERTIFICATE_SATURATION.json").read_text("utf-8"))
    assert published["certificates"]["n_effective_certificates"] is not None
    assert "book_breadth" in published


def test_timeframe_session_tier_composes_after_saturation_and_never_filters(sat: dict) -> None:
    rows = _docket()
    cs.stamp(rows, sat)
    q = {"session_range_breakout": 1}
    neutral = [r["_cell"] for r in jc.coverage_order(rows, q, quality=0.0,
                                                     tf_key=lambda r: 0)]
    # no census -> the PR #200 key is neutral and the order is unchanged
    census = brot.tf_session_key({})
    assert [r["_cell"] for r in jc.coverage_order(rows, q, quality=0.0,
                                                  tf_key=census)] == neutral
    # US500 rows sit in an under-target bucket: they lead their saturation tier, duplicates stay
    # behind every non-duplicate, and nothing is dropped
    tiered = jc.coverage_order(rows, q, quality=0.0,
                               tf_key=lambda r: 0 if r.get("symbol") == "US500" else 1)
    assert len(tiered) == len(rows)
    assert tiered[0]["symbol"] == "US500"
    last_clean = max(i for i, r in enumerate(tiered) if not r.get("_dup"))
    first_dup = min(i for i, r in enumerate(tiered) if r.get("_dup"))
    assert last_clean < first_dup
