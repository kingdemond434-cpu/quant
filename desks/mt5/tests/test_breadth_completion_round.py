"""The breadth completion round (2026-10-07): CRO breadth steps verified from the cycle ledger,
the audit's file-existence rows re-anchored on code, and the MISSING rows this thread owns."""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import breadth_law_coverage as blc  # noqa: E402
import cro_breadth_steps as cbs  # noqa: E402

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


# ------------------------------------------------------------------ CRO breadth steps
def _artifacts(d: Path, *, age_h: float = 1.0) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    docs = {
        "CERTIFICATE_SATURATION.json": {"certificates": {"n_certificates": 5}, "clusters": {}},
        "BREADTH_DEBT.json": {"empty_clusters": []},
        "BREADTH_FEEDBACK.json": {"producers": {}},
        "BREADTH_LADDER.json": {"budget_split": {}},
        "JUDGE_COVERAGE.json": {"verdict": "COVERED"},
        "gate_verdict_ledger.jsonl": None,
        "EFFECTIVE_BREADTH.json": {"effective": {}},
    }
    ts = (NOW - timedelta(hours=age_h)).timestamp()
    for name, doc in docs.items():
        p = d / name
        p.write_text("" if doc is None else json.dumps(doc), "utf-8")
        os.utime(p, (ts, ts))
    return d


FULL = {"n_certificates": 9, "n_effective_certificates": 4.2, "n_saturated_clusters": 2,
        "top_debt": "carry/rates", "compute_saturated_vs_empty": [3.1, 0.4],
        "duplicate_survivor_share": 0.3, "leaking_producers": ["kimi"], "mode": "ON",
        "split": {"A": 0.4}, "new_structural_clusters": 3, "evaluator_admitted": 1200,
        "verdicts_completed": 800, "forward_streams": 3}


def _ledger(p: Path, rows: list[dict]) -> Path:
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", "utf-8")
    return p


def test_each_cro_step_reads_ran_missed_or_unmeasured(tmp_path: Path) -> None:
    rep = _artifacts(tmp_path / "rep")
    led = _ledger(tmp_path / "led.jsonl", [
        {"at": (NOW - timedelta(hours=2)).isoformat(), "lane": "noon",
         "breadth_law": {k: v for k, v in FULL.items() if k != "verdicts_completed"}}])
    doc = cbs.build(now=NOW, ledger=led, reports=rep, verdicts=rep / "gate_verdict_ledger.jsonl")
    by = {s["row"]: s for s in doc["steps"]}
    assert len(by) == 10 and doc["status"] == "MEASURED"
    assert by["BREADTH-0162"]["state"] == cbs.RAN
    assert by["BREADTH-0162"]["recorded"] == {"n_certificates": 9, "n_effective_certificates": 4.2}
    assert by["BREADTH-0170"]["state"] == cbs.MISSED
    assert doc["counts"] == {"RAN": 9, "MISSED": 1, "UNMEASURED": 0}


def test_no_ledger_old_row_or_stale_artifact_is_unmeasured_never_ran(tmp_path: Path) -> None:
    rep = _artifacts(tmp_path / "rep")
    gone = cbs.build(now=NOW, ledger=tmp_path / "absent.jsonl", reports=rep)
    assert gone["status"] == "UNMEASURED" and gone["counts"]["UNMEASURED"] == 10
    old = _ledger(tmp_path / "old.jsonl", [{"at": (NOW - timedelta(hours=72)).isoformat(),
                                            "breadth_law": FULL}])
    assert cbs.build(now=NOW, ledger=old, reports=rep)["counts"]["RAN"] == 0
    stale = _artifacts(tmp_path / "stale", age_h=48)
    led = _ledger(tmp_path / "led.jsonl", [{"at": NOW.isoformat(), "breadth_law": FULL}])
    doc = cbs.build(now=NOW, ledger=led, reports=stale,
                    verdicts=stale / "gate_verdict_ledger.jsonl")
    assert doc["counts"] == {"RAN": 0, "MISSED": 0, "UNMEASURED": 10}


def test_success_law_never_counts_certificates_alone() -> None:
    def row(n: float, k: float) -> dict:
        return {"at": NOW.isoformat(), "breadth_law": {"n_certificates": n,
                                                       "n_effective_certificates": k}}
    assert cbs.success_law([row(5, 3), row(9, 3)])["verdict"] == "NOT_SUCCESS_NOMINAL_ONLY"
    assert cbs.success_law([row(5, 3), row(5, 3.5)])["verdict"] == "SUCCESS_EFFECTIVE"
    assert cbs.success_law([row(5, 3), row(5, 3)])["verdict"] == "NO_BREADTH_GAIN"
    assert cbs.success_law([row(5, 3)])["verdict"] == "UNMEASURED"
    # a stringified breadth_law (the ledger has carried JSON-in-a-string) still parses
    s = {"at": NOW.isoformat(), "breadth_law": json.dumps({"n_certificates": 9,
                                                           "n_effective_certificates": 3})}
    assert cbs.success_law([row(5, 3), s])["verdict"] == "NOT_SUCCESS_NOMINAL_ONLY"


def test_alpha_breadth_pass_publishes_the_cro_step_report(tmp_path: Path, monkeypatch) -> None:
    import alpha_breadth as ab
    import breadth_debt as bd
    monkeypatch.setattr(ab, "OUT", tmp_path / "EFFECTIVE_BREADTH.json")
    monkeypatch.setattr(bd, "_lane_factors", lambda: None)
    out = ab.breadth_debt_pass({"status": "UNMEASURED"})
    assert (tmp_path / "CRO_BREADTH_STEPS.json").exists()
    assert set(out["cro_breadth_steps"]["counts"]) == {"RAN", "MISSED", "UNMEASURED"}


# ------------------------------------------------------------------ coverage, re-anchored
def test_no_owned_row_reads_covered_on_file_existence_alone() -> None:
    doc = blc.build()
    for r in doc["rows"]:
        if r.get("evidence"):
            assert r["status"] != blc.COVERED, r["id"]
    cro = [r for r in doc["rows"] if "0162" <= r["id"][-4:] <= "0172"]
    assert len(cro) == 11 and all(r["status"] == blc.COVERED for r in cro)
    assert all(any("cro_breadth_steps.py" in w for w in r["where"]) for r in cro)


# ------------------------------------------------------------------ the funnel per candidate
def test_funnel_credits_each_stage_only_after_the_earlier_one(tmp_path: Path) -> None:
    import breadth_funnel as bfn
    docket = [
        {"symbol": "EURUSD", "family": "carry", "params": {"rr": 1.5}, "selector": "asia",
         "producer": "kimi", "breadth_order": {"rank": 0, "dup": 0}},
        {"symbol": "GBPUSD", "family": "carry", "params": {"rr": 1.5}, "selector": "asia",
         "producer": "kimi", "breadth_order": {"rank": 1, "dup": 1}},
        {"symbol": "XAUUSD", "family": "srb", "params": "{'rr': 2.0}", "selector": "asia",
         "producer": "miner"},
    ]
    cid = {r["symbol"]: bfn._cell_id({"sym": r["symbol"], "family": r["family"],
                                      "params": bfn._params(r)}) for r in docket}
    vm = {cid["EURUSD"]: True, cid["GBPUSD"]: False, cid["XAUUSD"]: True}
    shadow = {"EURUSD.asia": {}, "GBPUSD.asia": {}}
    sleeves = {"sleeves": [{"symbol": "EURUSD", "family": "carry", "status": "LIVE"},
                           {"symbol": "XAUUSD", "family": "srb", "status": "RETIRED"}]}
    sat = {"forward_independence": {"status": "MEASURED", "pairs": [
        {"a": "EURUSD_carry_asia", "b": "USDJPY_carry_asia", "state": "INDEPENDENT"}]}}
    doc = bfn.build(docket=docket, verdict_map=vm, shadow=shadow, sleeves=sleeves,
                    saturation=sat)
    assert doc["stages"] == {"generated": 3, "structurally_novel": 1, "evaluator_admitted": 3,
                             "survives": 2, "forward_enrolled": 1,
                             "prospective_independence": 1, "promoted_live": 1}
    assert doc["by_producer"]["kimi"]["survives"] == 1
    top = doc["candidates"][0]
    assert top["producer"] == "kimi" and top["stage"] == "promoted_live"
    # GBPUSD is enrolled forward but never survived: no forward credit without the verdict
    gbp = next(c for c in doc["candidates"] if c["cell"] == cid["GBPUSD"])
    assert gbp["stages"]["forward_enrolled"] is False


def test_funnel_absent_inputs_read_unmeasured_never_zero(tmp_path: Path) -> None:
    import breadth_funnel as bfn
    doc = bfn.build(docket=[{"symbol": "EURUSD", "family": "carry", "params": {}}],
                    verdict_map=None, shadow=None, sleeves=None, saturation={},
                    now=NOW)
    assert doc["stages"]["generated"] == 1
    for s in bfn.STAGES[1:]:
        assert doc["stages"][s] is None, s
        assert s in doc["unmeasured"]
    gone = bfn.build(docket={"not": "a list"}, verdict_map=None)
    assert gone["status"] == "UNMEASURED"
    p = bfn.publish(doc, tmp_path / "BREADTH_FUNNEL.json")
    assert json.loads(p.read_text("utf-8"))["n_candidates"] == 1


def test_funnel_names_each_producers_failures_by_terminal_gate() -> None:
    import breadth_funnel as bfn
    docket = [{"symbol": s, "family": "carry", "params": {"rr": 1.5}, "producer": "kimi"}
              for s in ("EURUSD", "GBPUSD", "AUDUSD")]
    cid = {r["symbol"]: bfn._cell_id({"sym": r["symbol"], "family": "carry",
                                      "params": bfn._params(r)}) for r in docket}
    vm = {cid["EURUSD"]: {"passed": False, "gate": "deflated_sharpe"},
          cid["GBPUSD"]: {"passed": False, "gate": "deflated_sharpe"},
          cid["AUDUSD"]: {"passed": True, "gate": None}}
    doc = bfn.build(docket=docket, verdict_map=vm, shadow={}, sleeves={"sleeves": []},
                    saturation={})
    f = doc["failures_by_producer"]["kimi"]
    assert f["by_terminal_gate"] == {"deflated_sharpe": 2}
    assert {e["cell"] for e in f["examples"]} == {cid["EURUSD"], cid["GBPUSD"]}


# ------------------------------------------------------------------ QD niche records
def test_qd_niche_records_best_of_each_kind_and_unmeasured_with_reason() -> None:
    import qd_frontier as qd
    a = {"instrument": "EURUSD", "family": "carry", "exp_r": 0.2, "n": 25, "gate_depth": 0.6}
    b = {"instrument": "GBPUSD", "family": "carry", "exp_r": 0.05, "n": 100, "gate_depth": 0.9}
    key = qd.niche_key(qd.niche_of(a))
    assert key == qd.niche_key(qd.niche_of(b))
    niches = {key: {"elite": None, "n_cells_tried": 2}, "empty": {"elite": None,
                                                                   "n_cells_tried": 0}}
    n = qd.niche_records(niches, {"a": a, "b": b}, None,
                         delta_elogw={("GBPUSD", "carry"): 0.0004},
                         capacity_terms=lambda s, ax: {"terms": {"capacity": 2.0 if s ==
                                                                 "EURUSD" else 1.0,
                                                                 "turnover": 1.0,
                                                                 "liquidity": 0.5}})
    r = niches[key]["records"]
    assert n == 2  # the empty niche still records its trial spend (cells tried, labelled)
    assert niches["empty"]["records"]["effective_trial_spend_basis"].startswith("cells tried")
    assert r["best_robustness"] == 0.9 and r["best_capacity"] == 2.0
    assert r["best_execution"] == 0.5 and r["best_marginal_delta_elogw"] == 0.0004
    assert r["best_forward_evidence"] == 1.0 and r["remaining_uncertainty"] == 0.2
    assert r["local_saturation"] is None and "local_saturation" in niches[key][
        "records_unmeasured"]
    e = niches["empty"]
    assert e["records"]["best_forward_evidence"] is None
    assert "best_forward_evidence" in e["records_unmeasured"]


# ------------------------------------------------------------------ briefs carry both
def test_briefs_carry_each_producers_failures_and_the_repertoire(tmp_path: Path) -> None:
    import certificate_saturation as cs
    (tmp_path / "BREADTH_FUNNEL.json").write_text(json.dumps({
        "at": NOW.isoformat(), "failures_by_producer": {"kimi": {
            "by_terminal_gate": {"deflated_sharpe": 3}, "examples": [{"cell": "c1"}]}}}),
        "utf-8")
    (tmp_path / "QD_FRONTIER.json").write_text(json.dumps({
        "at": NOW.isoformat(), "summary": {"niches_occupied": 2, "niches_empty": 9},
        "niches": {"n1": {"elite": {"instrument": "EURUSD", "family": "carry"},
                          "n_cells_tried": 4, "records": {"best_forward_evidence": 1.2}}}}),
        "utf-8")
    doc = {"certificates": {"n_certificates": 4, "n_effective_certificates": 2},
           "clusters": {}}
    fb = {"producers": {"kimi_hunt": {"rows": 10, "state": "OK"}}}
    p = cs.publish_briefs(doc=doc, feedback=fb, path=tmp_path / "PRODUCER_BRIEFS.json")
    assert p is not None
    out = json.loads(p.read_text("utf-8"))
    assert out["producers"]["kimi_hunt"]["failures"]["by_terminal_gate"] == {
        "deflated_sharpe": 3}
    assert out["desk"]["repertoire"]["niches_occupied"] == 2
    lines = cs.brief_lines("kimi", path=p)
    assert any("failed at" in ln and "deflated_sharpe=3" in ln for ln in lines)
    assert any(ln.startswith("repertoire: 2 niches occupied") for ln in lines)
    # absent artifacts: the repertoire reads UNMEASURED and no failure record is invented
    (tmp_path / "QD_FRONTIER.json").unlink()
    (tmp_path / "BREADTH_FUNNEL.json").unlink()
    out = json.loads(cs.publish_briefs(doc=doc, feedback=fb,
                                       path=tmp_path / "PRODUCER_BRIEFS.json").read_text("utf-8"))
    assert out["desk"]["repertoire"]["status"] == "UNMEASURED"
    assert "failures" not in out["producers"]["kimi_hunt"]


# ------------------------------------------------------------------ the owned MISSING rows
def test_retarget_names_a_region_and_a_representation() -> None:
    import certificate_saturation as cs
    clusters = {
        "trend_persistence/price_only/forex/USD/london|hourly|intraday": {
            "hierarchy": {"L1": "trend_persistence", "L3": "forex",
                          "L5": "london|hourly|intraday"},
            "remaining_unexplored_axes": {"session": ["asia"], "regime": ["high_vol"],
                                          "horizon": ["multi_day"]}},
        "range_reversion/price_only/indices/RISK/ny|daily|multi_day": {
            "hierarchy": {"L1": "range_reversion", "L3": "indices", "L5": "ny|daily|multi_day"},
            "remaining_unexplored_axes": {}},
    }
    top = {"trend_persistence/price_only/forex/USD/london|hourly|intraday": 9}
    r = cs.retarget_axes(top, clusters)
    assert "trend_persistence in forex @session=asia" in r["retarget_regions"]
    assert "trend_persistence in indices" in r["retarget_regions"]
    assert "trend_persistence @horizon=multi_day" in r["retarget_representations"]
    assert "trend_persistence @chart=daily" in r["retarget_representations"]
    assert "trend_persistence @chart=hourly" not in r["retarget_representations"]
    assert cs.retarget_axes(top, {})["retarget_regions"] == "UNMEASURED"


def test_generator_demonstrations_unmeasured_is_never_not_demonstrated() -> None:
    import breadth_funnel as bfn
    d = bfn.demonstrations({"kimi": {"structurally_novel": 3, "evaluator_admitted": 2,
                                     "survives": 0, "prospective_independence": None}})
    k = d["kimi"]
    assert k["novel_outputs"] == "DEMONSTRATED" and k["evaluation"] == "DEMONSTRATED"
    assert k["conversion"] == "NOT_DEMONSTRATED"
    assert k["independent_survivor"] == "UNMEASURED" and k["all_demonstrated"] is False


def test_trials_per_new_independent_survivor_kpi() -> None:
    import alpha_breadth as ab
    t0 = NOW - timedelta(days=3)
    rows = [{"at": t0.isoformat(), "effective_trials_spent_total": 1000.0,
             "n_independent_forward_streams": 4},
            {"at": NOW.isoformat(), "effective_trials_spent_total": 1600.0,
             "n_independent_forward_streams": 6}]
    k = ab.trials_per_independent_survivor(rows)
    assert k["status"] == "MEASURED" and k["value"] == 300.0
    rows[1]["n_independent_forward_streams"] = 4
    k = ab.trials_per_independent_survivor(rows)
    assert k["status"] == "NO_NEW_INDEPENDENT_SURVIVOR" and k["value"] is None
    assert k["trials_spent"] == 600.0
    assert ab.trials_per_independent_survivor(rows[:1])["status"] == "UNMEASURED"
    sat = {"clusters": {"a": {"economic_cluster": "e1", "effective_trials_spent": 50},
                        "b": {"economic_cluster": "e1", "effective_trials_spent": 50},
                        "c": {"economic_cluster": "e2", "effective_trials_spent": 7}}}
    assert ab.effective_trials_total(sat) == 57.0
    assert ab.effective_trials_total({"clusters": {}}) is None


def test_reopen_triggers_name_the_type_and_reason_and_baseline_never_fires() -> None:
    import certificate_saturation as cs
    assert cs.reopen_triggers(None, {"new_dataset": "a,b"}) == []
    fired = cs.reopen_triggers({"new_dataset": "a,b", "broker_change": "S|X,Y",
                                "cost_change": "X:1:0:0"},
                               {"new_dataset": "a,b,c", "broker_change": "S|X,Y",
                                "cost_change": "X:2:0:0"})
    types = {f["type"]: f["reason"] for f in fired}
    assert set(types) == {"new_dataset", "cost_change"}
    assert "'c'" in types["new_dataset"]


def test_payoff_shapes_and_mode_structures() -> None:
    import breadth_debt as bd
    doc = {"clusters": {
        "k1": {"hierarchy": {"L1": "trend_persistence", "L2": "price_only"},
               "certificate_count": 5, "effective_certificate_count": 2.0,
               "families": ["relative_value"]},
        "k2": {"hierarchy": {"L1": "carry_rollover", "L2": "carry"},
               "certificate_count": 1, "effective_certificate_count": 1.0}}}
    ps = bd.payoff_shapes(doc)
    assert ps["status"] == "MEASURED"
    assert "convex_trend" not in ps["missing_payoff_shapes"]
    assert "spread_convergence" in ps["missing_payoff_shapes"]
    assert ps["low_overlap_order"][-1] == "convex_trend"
    st = bd._structures(doc)
    assert "relative_value" not in st["relative_value_structures"]
    assert "pca_residual" in st["cross_asset_residual_structures"]
    assert bd.payoff_shapes({})["status"] == "UNMEASURED"


def test_bounty_terms_never_shrink_and_reprice_as_niches_fill() -> None:
    import certificate_saturation as cs
    sizes = {"forex": 60, "indices": 15}
    empty = cs.bounty_terms("indices", "carry_rollover", sizes, {}, {"carry_rollover": 100},
                            {"carry_rollover": 1})
    filled = cs.bounty_terms("indices", "carry_rollover", sizes, {"indices": 4},
                             {"carry_rollover": 100}, {"carry_rollover": 1})
    assert 1.0 <= filled["capacity_potential"] < empty["capacity_potential"] <= 2.0
    assert empty["difficulty"] == 1.99
    none = cs.bounty_terms("bonds", "x", {}, {}, {}, {})
    assert none["capacity_potential"] == 1.0 and none["difficulty"] == 1.0
    assert none["capacity_status"] == "UNMEASURED" and none["difficulty_status"] == "UNMEASURED"


def test_edge_pareto_marks_dominated_rows_in_shadow_only() -> None:
    import edge_pareto as ep
    import numpy as np
    pts = np.array([[1, 1, 1, 1], [0.5, 1, 1, 1], [2, 0, 1, 1]], dtype=float)
    assert ep.dominated_mask(pts).tolist() == [False, True, False]
    docket = [
        {"symbol": "EURUSD", "family": "carry", "params": {"timeframe": "H1"},
         "breadth_order": {"rank": 0, "dup": 0, "sat": 0.9}},
        {"symbol": "EURUSD", "family": "carry", "params": {"timeframe": "H1"},
         "breadth_order": {"rank": 1, "dup": 0, "sat": 0.2}},
        {"symbol": "GBPUSD", "family": "carry", "params": {"timeframe": "H1"}},
    ]
    doc = ep.build(docket=docket,
                   capacity=lambda s, tf: {"terms": {"capacity": None, "liquidity": 1.0}})
    if doc["status"] == "MEASURED":
        assert doc["n_dominated"] == 1 and doc["compute_shift_shadow"]["live"] is False
        assert doc["unmeasured_by_objective"].get("independence") == 1
    else:  # the family table names no mechanism for `carry` on this clone
        assert doc["why"]
    gone = ep.build(docket={"x": 1})
    assert gone["status"] == "UNMEASURED" and gone["mode"] == "SHADOW"


def test_profile_distance_is_reported_beside_and_never_inside_overlap_score() -> None:
    import numpy as np
    import stream_overlap as so
    rng = np.random.default_rng(7)
    days = [f"2026-0{1 + i // 28}-{1 + i % 28:02d}" for i in range(200)]
    xa = rng.normal(size=200) * (rng.random(200) < 0.6)
    xb = rng.normal(size=200) * (rng.random(200) < 0.3)
    a, b = dict(zip(days, xa, strict=True)), dict(zip(days, xb, strict=True))
    common = {d: (a[d] + b[d]) / 2 for d in days}
    o = so.pair_overlap(a, b, common=common)
    pf = o["profile"]
    for k in ("holding_time_ks", "turnover_gap", "spectral_distance",
              "factor_residual_distance"):
        assert pf[k] is not None and 0.0 <= pf[k] <= 1.0, k
    no_prof = so.pair_overlap(a, b)
    assert no_prof["overlap_score"] == o["overlap_score"]
    assert no_prof["profile"]["factor_residual_distance"] is None


def test_failure_hedge_prices_up_never_down(tmp_path: Path) -> None:
    import certificate_saturation as cs
    hurts = list(cs.MECHANISM_FAILURE["trend_persistence"])
    same = cs.failure_hedge(["htf_anchor_trend"], hurts)
    assert cs.failure_hedge([], None)["multiplier"] == 1.0
    assert same["multiplier"] >= 1.0
    import axis_registry as ar
    other = next(f for f, v in ar.FAMILY_TABLE.items()
                 if v[0] in cs.MECHANISM_FAILURE
                 and not set(cs.MECHANISM_FAILURE[v[0]]) & set(hurts))
    h = cs.failure_hedge([other], hurts)
    assert h["multiplier"] == cs.FAILURE_HEDGE and other in h["fails_differently"]
    (tmp_path / "m.json").write_text(json.dumps({"failure_modes": {"hurts_book": hurts}}),
                                     "utf-8")
    assert cs.book_hurts(tmp_path / "m.json") == hurts
    assert cs.book_hurts(tmp_path / "absent.json") is None


def test_portfolio_bounty_posts_failure_mode_hedges() -> None:
    import certificate_saturation as cs
    import portfolio_bounty as pb
    hurts = list(cs.MECHANISM_FAILURE["trend_persistence"])
    un: list[str] = []
    rows = pb._failure_mode_bounties({"failure_modes": {"hurts_book": hurts},
                                      "clusters": {}}, un)
    assert rows and all(r["kind"] == "failure_mode_hedge" for r in rows)
    assert all(not set(r["evidence"]["fails_on"]) & set(hurts) for r in rows)
    un2: list[str] = []
    assert pb._failure_mode_bounties({}, un2) == [] and un2


def test_sandbox_plan_hedge_only_ever_adds_share() -> None:
    from libs.research import sandbox_rotation as rot
    rows = {s: {"last_at": NOW.isoformat(), "roi": 1.0} for s in ("a", "b")}
    base = rot.plan(["a", "b"], rows, budget_s=10_000, floor_s=10, at=NOW.timestamp())
    hed = rot.plan(["a", "b"], rows, budget_s=10_000, floor_s=10, at=NOW.timestamp(),
                   hedge={"a": 1.5, "b": 0.2})
    assert hed["shares"]["a"] >= base["shares"]["a"]
    assert hed["failure_hedge"] == {"a": 1.5}


def test_qd_distance_reads_the_forward_profile() -> None:
    import qd_frontier as qd
    sat = {"groups": [{"sig": ["x"] * 30, "n": 1}], "forward_independence": {"pairs": [
        {"a": "EURUSD_carry_asia", "b": "GBPUSD_carry_asia", "state": "UNMEASURED",
         "rho": 0.1, "profile": {"turnover_gap": 0.3, "holding_time_ks": 0.4}}]}}
    bd = qd.behavioural_distance({"instrument": "EURUSD", "family": "carry"}, sat)
    c = bd["components"]
    assert c["turnover"]["value"] == 0.3 and c["holding_time_distribution"]["value"] == 0.4
    assert c["spectral_signature"]["value"] is None
    assert c["pnl_correlation"]["value"] is None


# ------------------------------------------------------------------ anchors must be live code
def _stub_tree(root: Path, kind: str) -> int:
    """Every anchored .py file replaced by its own text held as a string: an assigned
    triple-quoted `_STUB`, or a dead function returning one string per line."""
    paths = {a.partition("::")[0] for _s, _st, anchors, _n in blc.CLASSIFICATION
             for a in anchors if a.partition("::")[0].endswith(".py")}
    for rel in paths:
        src = (ROOT / rel).read_text("utf-8", errors="replace")
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if kind == "stub":
            body = src.replace("\\", "/").replace('"""', "'''")
            dst.write_text(f'_STUB = """\n{body}\n"""\n', "utf-8")
        else:
            lines = "".join(f"        {ln!r},\n" for ln in src.splitlines())
            dst.write_text(f"def _never_called():\n    return (\n{lines}    )\n", "utf-8")
    return len(paths)


def test_a_string_stub_recovers_no_row(tmp_path: Path) -> None:
    assert _stub_tree(tmp_path, "stub") > 10
    doc = blc.build(root=tmp_path)
    got = [r["id"] for r in doc["rows"] if r["status"] in (blc.COVERED, blc.COVERED_SHADOW)]
    assert got == []


def test_a_dead_function_returning_anchor_strings_recovers_no_row(tmp_path: Path) -> None:
    _stub_tree(tmp_path, "dead")
    doc = blc.build(root=tmp_path)
    got = [r["id"] for r in doc["rows"] if r["status"] in (blc.COVERED, blc.COVERED_SHADOW)]
    assert got == []


def test_dead_code_and_strings_never_resolve_but_live_code_does(tmp_path: Path) -> None:
    (tmp_path / "m.py").write_text(
        'X = "breadth_marker_alpha"\n'
        "def _unused():\n"
        "    return compute_marker_beta()\n"
        "def used():\n"
        "    return 1\n"
        "    compute_marker_gamma()\n"
        "def compute_marker_delta():\n"
        "    return used()\n"
        "VALUE = compute_marker_delta()\n"
        'R = {"field_marker": 1}\n'
        "print(VALUE, R, X)\n", "utf-8")
    blc._FILES.clear()
    blc._CODE.clear()
    assert blc.resolve("m.py::breadth_marker_alpha", tmp_path) is None     # assigned string
    assert blc.resolve("m.py::compute_marker_beta", tmp_path) is None      # dead function
    assert blc.resolve("m.py::compute_marker_gamma", tmp_path) is None     # after return
    assert blc.resolve("m.py::VALUE = compute_marker_delta", tmp_path) == "m.py:9"
    assert blc.resolve("m.py::\"field_marker\"", tmp_path) == "m.py:10"    # a dict key
