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
    b = {"instrument": "GBPUSD", "family": "carry", "exp_r": 0.1, "n": 100, "gate_depth": 0.9}
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
