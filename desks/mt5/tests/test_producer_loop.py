"""The producer loop (LOOP_COVERAGE L1): funnel, kill classes, remedies, rails, retirement.

Every input is synthetic or redirected into `tmp_path`; nothing here reads or writes box state.
"""
from __future__ import annotations

import importlib
import json
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import producer_loop as pl  # noqa: E402

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)


def _sandbox(tmp: Path, monkeypatch: Any, *, conversion: Any = None, provenance: Any = None,
             shadow: Any = None, yield_doc: Any = None, audit: Any = None) -> None:
    for name, rel in (("OUT", "reports/PRODUCER_LOOP.json"),
                      ("LEDGER", "data/producer_loop_ledger.jsonl"),
                      ("ATTEMPTS", "data/producer_loop_attempts.jsonl"),
                      ("STATE", "data/producer_loop_state.json"),
                      ("ARCHIVE", "data/producer_loop_archive"),
                      ("WEIGHTS", "data/PRODUCER_WEIGHTS.json"),
                      ("PRESCRIPTIONS", "data/PRODUCER_PRESCRIPTIONS.json"),
                      ("CONVERSION", "reports/PRODUCER_CONVERSION.json"),
                      ("PROVENANCE", "data/certificate_provenance.json"),
                      ("SHADOW", "reports/shadow/shadow_state.json"),
                      ("YIELD_REPORT", "reports/PRODUCER_YIELD.json"),
                      ("VERDICTS", "data/gate_verdict_ledger.jsonl"),
                      ("REGISTRY", "data/alpha_registry.sqlite"),
                      ("BLOCKERS", "docs/productivity_blockers.json")):
        monkeypatch.setattr(pl, name, tmp / rel)
    monkeypatch.setattr(pl, "DESK", tmp)
    for path, doc in ((pl.CONVERSION, conversion), (pl.PROVENANCE, provenance),
                      (pl.SHADOW, shadow), (pl.YIELD_REPORT, yield_doc)):
        if doc is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(doc), "utf-8")
    monkeypatch.setattr(pl, "_dead_audit", lambda: audit or {"producers": [],
                                                             "source": "test"})


def _conv(**rows: tuple[int, int, int]) -> dict[str, Any]:
    return {"producers": [{"producer": k, "discoveries": 0, "candidates": c, "judged": j,
                           "certificates": n} for k, (c, j, n) in rows.items()]}


# -------------------------------------------------------------------------- kill-class mapping

def test_kill_class_mapping_is_explicit_and_unmapped_is_counted() -> None:
    assert pl.kill_class("deflated_sharpe") == pl.NO_OOS_EDGE
    assert pl.kill_class("lockbox") == pl.NO_OOS_EDGE
    assert pl.kill_class("stress_costs", "EURUSD") == pl.COSTS
    assert pl.kill_class("stress_costs", "USDZAR") == pl.EXOTIC_UNIVERSE
    assert pl.kill_class("NOT_RUN_DATA_MISSING") == pl.DEAD_DATA
    assert pl.kill_class("too_rare") == pl.TOO_FEW_TRADES
    assert pl.kill_class("NOT_RUN_BUILD_BUDGET_DEFERRED") == pl.PENDING
    assert pl.kill_class("a_gate_nobody_declared") == pl.UNMAPPED
    # through the judge's own terminal rule: an unmeasured row, a ruled row, a legacy row
    assert pl.classify({"cell": "EURUSD.carry.p=1", "passed": False,
                        "unknown_reason": "too_rare"}) == pl.TOO_FEW_TRADES
    assert pl.classify({"cell": "EURUSD.carry.p=1", "passed": False,
                        "terminal_gate": "walk_forward"}) == pl.NO_OOS_EDGE
    assert pl.classify({"cell": "EURUSD.carry.p=1", "passed": False,
                        "terminal_gate": "UNKNOWN",
                        "downstream_status": "NOT_RUN_BUILD_FAILED"}) == pl.DEAD_DATA
    assert pl.classify({"cell": "EURUSD.carry.p=1", "passed": False,
                        "terminal_gate": "brand_new_gate"}) == pl.UNMAPPED
    # an UNMAPPED dominant kill never prescribes and is never dropped from the histogram
    rx = pl.choose_remedy("CERTIFY", {pl.UNMAPPED: 9, pl.COSTS: 1}, replacement=None,
                          is_seat=False, exotic_share=None)
    assert rx["remedy"] is None and rx["dominant_kill_class"] == pl.UNMAPPED


def test_the_daily_diagnosis_builds_a_histogram_with_unmapped_and_duplicates(
        tmp_path: Path, monkeypatch: Any) -> None:
    _sandbox(tmp_path, monkeypatch)
    pl.REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(pl.REGISTRY)
    con.execute("create table research_candidates (symbol, family, params_json, producer)")
    rows = [("EURUSD", "carry", json.dumps({"a": i}), "minerx") for i in range(3)]
    rows += [("EURUSD", "carry", json.dumps({"a": 0}), "minerx"),        # a duplicate
             ("USDZAR", "carry", json.dumps({"a": 9}), "minerx")]       # an exotic
    con.executemany("insert into research_candidates values (?,?,?,?)", rows)
    con.commit()
    con.close()
    from research.frontier_identity import cell_id
    ids = [cell_id({"sym": "EURUSD", "family": "carry", "params": {"a": i}}) for i in range(3)]
    ledger = [{"cell": ids[0], "passed": False, "terminal_gate": "deflated_sharpe"},
              {"cell": ids[1], "passed": False, "terminal_gate": "mystery_gate"},
              {"cell": ids[2], "passed": False, "terminal_gate": "in_sample_screen"},
              {"cell": ids[2], "passed": False, "unknown_reason": "too_rare"}]   # latest wins
    pl.VERDICTS.write_text("\n".join(json.dumps(r) for r in ledger), "utf-8")
    d = pl.diagnose()
    h = d["producers"]["minerx"]["histogram"]
    assert h == {pl.NO_OOS_EDGE: 1, pl.UNMAPPED: 1, pl.TOO_FEW_TRADES: 1,
                 pl.DUPLICATE: 1, pl.EXOTIC_UNIVERSE: 1}


# ------------------------------------------------------------------------- ranking and funnel

def test_ranking_by_certificates_per_candidate_and_stage_of_death(
        tmp_path: Path, monkeypatch: Any) -> None:
    _sandbox(tmp_path, monkeypatch,
             conversion=_conv(good=(1000, 900, 20), weak=(1000, 900, 1), zero=(1000, 900, 0),
                              nojudge=(500, 0, 0)))
    doc = pl.build(now=NOW, apply=False)
    order = [x["producer"] for x in doc["producers"]]
    assert order.index("good") < order.index("weak") < order.index("zero")
    by = {x["producer"]: x for x in doc["producers"]}
    assert by["good"]["status"] == "HEALTHY" and by["good"]["stage_of_death"] is None
    assert by["weak"]["stage_of_death"] == "CERTIFY"          # a laggard
    assert by["zero"]["stage_of_death"] == "CERTIFY"
    assert by["nojudge"]["stage_of_death"] == "JUDGE"
    assert by["good"]["certificates_per_candidate"] == 0.02


def test_absent_inputs_are_unmeasured_never_zero(tmp_path: Path, monkeypatch: Any) -> None:
    _sandbox(tmp_path, monkeypatch,
             audit={"producers": [{"producer": "seatx", "verdict": "PRODUCING",
                                   "rows_in_window": 5}], "source": "test"})
    doc = pl.build(now=NOW, apply=False)
    row = {x["producer"]: x for x in doc["producers"]}["seatx"]
    assert doc["inputs"]["conversion"].startswith("UNMEASURED")
    assert doc["inputs"]["forward_clocks"].startswith("UNMEASURED")
    assert row["certificates"] == pl.UNMEASURED and row["cells_judged"] == pl.UNMEASURED
    assert row["funnel"]["forward_kept"] == pl.UNMEASURED
    assert row["kill_class_histogram"] == pl.UNMEASURED
    assert row["yield"]["edges_per_cpu_hour"] == pl.UNMEASURED
    assert row["status"] == pl.UNMEASURED and row["weight"] == 1.0
    assert doc["diagnosis"]["why"].startswith("UNMEASURED")


def test_yield_is_k_eff_times_keep_rate_per_cpu_hour_and_weights_are_two_sided(
        tmp_path: Path, monkeypatch: Any) -> None:
    born = (NOW - timedelta(days=2)).isoformat()
    prov = {"records": {
        "a1": {"cell": "EURUSD.carry.p=1", "producer": "alpha", "at": born},
        "a2": {"cell": "EURUSD.carry.p=2", "producer": "alpha", "at": born},   # a clone
        "a3": {"cell": "USDJPY.session_range_breakout.p=3", "producer": "alpha", "at": born},
        "b1": {"cell": "GBPUSD.trend.p=4", "producer": "beta", "at": born},
        "z1": {"cell": "USDZAR.carry.p=5", "producer": "beta", "at": born}}}  # exotic: no credit
    shadow = {"EURUSD.carry.asia": {"status": "ACTIVE", "cum_r": 1.0},
              "USDJPY.session_range_breakout.asia": {"status": "PROMOTION CANDIDATE"},
              "GBPUSD.trend.asia": {"status": "KILL"}}
    ydoc = {"cells_owed": {"producers": [
        {"producer": "alpha", "compute_hours_window7d": 7.0},
        {"producer": "beta", "compute_hours_window7d": 7.0},
        {"producer": "gamma", "compute_hours_window7d": 7.0}]}}
    _sandbox(tmp_path, monkeypatch, provenance=prov, shadow=shadow, yield_doc=ydoc,
             conversion=_conv(alpha=(1000, 900, 3), beta=(1000, 900, 2), gamma=(1000, 900, 0)))
    monkeypatch.setattr(pl, "_tradable", lambda s, f: True)
    # no live sleeve yet: the live stage is MEASURED (an empty book), not unreadable
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "sleeves.json").write_text(json.dumps({"sleeves": []}), "utf-8")
    (tmp_path / "data" / "fill_corpus.jsonl").write_text("", "utf-8")
    doc = pl.build(now=NOW, apply=False)
    by = {x["producer"]: x for x in doc["producers"]}
    ya, yb = by["alpha"]["yield"], by["beta"]["yield"]
    assert 2.0 <= ya["k_eff_edges"] < 3.0          # the two carry clones are not two edges
    assert ya["forward_keep_rate_used"] == 1.0 and yb["forward_keep_rate_used"] == 0.0
    assert ya["cpu_hours_window"] == 30.0
    # EXPECTED live edges: k_eff x shrunk p(cert->kept) x shrunk p(kept->live); no live edge
    # desk-wide still ranks producers (the smoothed pooled prior), and alpha outranks beta
    assert ya["edges_per_cpu_hour"] > yb["edges_per_cpu_hour"] > 0
    assert ya["live_edges_realised"] == 0 and ya["half_life_source"] == "default"
    assert by["gamma"]["yield"]["edges_per_cpu_hour"] == 0.0
    assert by["alpha"]["weight"] > by["beta"]["weight"] >= pl.WEIGHT_MIN
    assert by["gamma"]["weight"] == pl.WEIGHT_MIN
    # an unreadable live input is UNMEASURED, never zero
    (tmp_path / "data" / "sleeves.json").unlink()
    doc_u = pl.build(now=NOW, apply=False)
    assert {x["producer"]: x for x in doc_u["producers"]}["alpha"]["yield"][
        "edges_per_cpu_hour"] == pl.UNMEASURED
    (tmp_path / "data" / "sleeves.json").write_text(json.dumps({"sleeves": []}), "utf-8")
    doc = pl.build(now=NOW, apply=False)
    assert by["beta"]["stage_of_death"] == "FORWARD"
    w = json.loads(pl.write(doc) and pl.WEIGHTS.read_text())
    assert w["producers"]["gamma"]["weight"] == pl.WEIGHT_MIN


def test_reweight_rows_moves_inside_family_slots_and_removes_nothing() -> None:
    rows = [{"family": "a", "producer": "low", "i": 0}, {"family": "b", "producer": "x", "i": 1},
            {"family": "a", "producer": "high", "i": 2}, {"family": "a", "producer": "u", "i": 3}]
    out, rep = pl.reweight_rows(rows, {"low": 0.25, "high": 2.0})
    assert [r["family"] for r in out] == ["a", "b", "a", "a"]        # interleave unchanged
    assert [r["i"] for r in out] == [2, 1, 3, 0]
    assert sorted(r["i"] for r in out) == [0, 1, 2, 3] and rep["moved"] == 3



def test_a_flagged_high_weight_row_never_jumps_ahead_of_a_clean_par_row() -> None:
    """Audit HOLD 2026-11-25: the Tier-S pre-judge demotion (layers 9/21) survives the weights."""
    flagged = {"family": "a", "producer": "high", "i": 0, "prejudge": {"flags": ["rq_defender"]}}
    clean = {"family": "a", "producer": "par", "i": 1}
    out, _ = pl.reweight_rows([flagged, clean], {"high": 4.0})
    assert [r["i"] for r in out] == [1, 0]
    # and in the merge's real order (reweight, then demote_flagged), the clean row stays ahead
    sys.path.insert(0, str(_ROOT))
    from libs.tiers import prejudge_screen as pj
    rows = [{"family": "a", "symbol": "XAUUSD", "producer": "high", "i": 0},
            {"family": "a", "symbol": "EURUSD", "producer": "par", "i": 1}]
    verdicts = {pj.identity(rows[0]): {"flags": ["invented_test"]}}
    out, _ = pl.reweight_rows(rows, {"high": 4.0})
    out, _ = pj.demote_flagged(out, verdicts)
    assert [r["i"] for r in out] == [1, 0]
    merge = (_DESK / "research" / "merge_hypotheses.py").read_text("utf-8")
    assert merge.index("_reweight(rows_out)") < merge.index("_pj.demote_flagged(")

# ----------------------------------------------------------------------------- the rails

def test_record_attempt_refuses_a_non_held_out_attempt_and_a_parameter_tweak(
        tmp_path: Path, monkeypatch: Any) -> None:
    _sandbox(tmp_path, monkeypatch)
    r = pl.record_attempt("p", pl.GRID_NARROW, ["t1"], "in_sample", judged_now=0,
                          certificates_now=0, now=NOW)
    assert not r["recorded"] and "judged_on" in r["why"]
    r = pl.record_attempt("p", "lookback=20", ["t1"], "held_out", judged_now=0,
                          certificates_now=0, now=NOW)
    assert not r["recorded"] and "fixed" in r["why"]
    r = pl.record_attempt("p", pl.GRID_NARROW, [], "held_out", judged_now=0,
                          certificates_now=0, now=NOW)
    assert not r["recorded"]
    assert not pl.ATTEMPTS.exists()


def test_record_attempt_refuses_before_the_minimum_sample_and_before_seven_days(
        tmp_path: Path, monkeypatch: Any) -> None:
    _sandbox(tmp_path, monkeypatch)
    assert pl.record_attempt("p", pl.GRID_NARROW, ["t1"], "held_out", judged_now=1000,
                             certificates_now=0, now=NOW)["recorded"]
    # enough days, too few judged since
    late = NOW + timedelta(days=8)
    r = pl.record_attempt("p", pl.GRID_WIDEN, ["t2"], "forward_shadow",
                          judged_now=1000 + pl.MIN_JUDGED_SINCE_TWEAK - 1, certificates_now=0,
                          now=late)
    assert not r["recorded"] and "minimum sample" in r["why"]
    # enough judged, too soon
    r = pl.record_attempt("p", pl.GRID_WIDEN, ["t2"], "held_out",
                          judged_now=1000 + pl.MIN_JUDGED_SINCE_TWEAK, certificates_now=0,
                          now=NOW + timedelta(days=3))
    assert not r["recorded"] and "days" in r["why"]
    # both hold
    assert pl.record_attempt("p", pl.GRID_WIDEN, ["t2"], "held_out",
                             judged_now=1000 + pl.MIN_JUDGED_SINCE_TWEAK, certificates_now=0,
                             now=late)["recorded"]


def test_the_fourth_attempt_is_refused_and_every_attempt_is_charged_as_trials(
        tmp_path: Path, monkeypatch: Any) -> None:
    _sandbox(tmp_path, monkeypatch)
    j = 1000
    for k in range(pl.MAX_ATTEMPTS):
        assert pl.record_attempt("p", pl.GRID_NARROW, [f"t{k}a", f"t{k}b"], "held_out",
                                 family="carry", judged_now=j, certificates_now=0,
                                 now=NOW + timedelta(days=8 * k))["recorded"]
        j += pl.MIN_JUDGED_SINCE_TWEAK
    r = pl.record_attempt("p", pl.GRID_NARROW, ["t9"], "held_out", judged_now=j,
                          certificates_now=0, now=NOW + timedelta(days=8 * pl.MAX_ATTEMPTS))
    assert not r["recorded"] and "MAX_ATTEMPTS" in r["why"]
    assert pl.loop_trial_counts() == (2 * pl.MAX_ATTEMPTS, {"carry": 2 * pl.MAX_ATTEMPTS})
    # ... and the lifetime experiment ledger joins exactly that file (one budget, R2)
    el = importlib.import_module("libs.research.experiment_ledger")
    assert el._loop_attempt_counts(pl.ATTEMPTS) == pl.loop_trial_counts()


def test_parking_after_max_failed_remedies_keeps_the_producer_at_the_floor(
        tmp_path: Path, monkeypatch: Any) -> None:
    _sandbox(tmp_path, monkeypatch, conversion=_conv(
        good=(1000, 900, 20), dud=(1000, 1000 + pl.MAX_ATTEMPTS * pl.MIN_JUDGED_SINCE_TWEAK, 0)))
    rows = []
    for k in range(pl.MAX_ATTEMPTS):
        rows.append({"producer": "dud", "remedy": pl.GRID_NARROW, "trial_ids": [f"t{k}"],
                     "judged_on": "held_out", "attempt": k + 1,
                     "at": (NOW - timedelta(days=30 - 8 * k)).isoformat(),
                     "judged_at_attempt": 1000 + k * pl.MIN_JUDGED_SINCE_TWEAK,
                     "certificates_at_attempt": 0, "controls": {}})
    pl.ATTEMPTS.parent.mkdir(parents=True, exist_ok=True)
    pl.ATTEMPTS.write_text("\n".join(json.dumps(r) for r in rows), "utf-8")
    doc = pl.write(pl.build(now=NOW, apply=False))
    dud = {x["producer"]: x for x in doc["producers"]}["dud"]
    assert dud["status"] == "PARKED" and dud["weight"] == pl.WEIGHT_MIN > 0   # never cut
    assert len(dud["remedies_evaluated"]) == pl.MAX_ATTEMPTS
    assert all(o["outcome"].startswith("FAILED") for o in dud["remedies_evaluated"])
    assert "before_certs_per_judged" in dud["remedies_evaluated"][0]      # R7
    assert dud["retest_at"][:10] == (NOW + timedelta(days=pl.RETEST_AFTER_DAYS)).date().isoformat()
    arch = json.loads((tmp_path / dud["archive"]).read_text())
    assert arch["retirements"][0]["attempts"] and arch["retirements"][0]["retest_at"]
    w = json.loads(pl.WEIGHTS.read_text())
    assert w["producers"]["dud"]["weight"] == pl.WEIGHT_MIN
    # a later pass keeps it parked until the re-test date, and refuses a remedy meanwhile
    doc2 = pl.build(now=NOW + timedelta(days=1), apply=False)
    assert {x["producer"]: x for x in doc2["producers"]}["dud"]["status"] == "PARKED"
    state = json.loads(pl.STATE.read_text())
    r = pl.record_attempt("dud", pl.GRID_WIDEN, ["t9"], "held_out", judged_now=10_000,
                          certificates_now=0, now=NOW + timedelta(days=1),
                          retest_at=state["retired"]["dud"]["retest_at"])
    assert not r["recorded"] and "re-test" in r["why"]


def test_a_worse_remedy_is_reverted_against_its_controls(tmp_path: Path,
                                                         monkeypatch: Any) -> None:
    att = {"producer": "p", "remedy": pl.INSTRUMENT_REMAP, "attempt": 1, "trial_ids": ["t"],
           "at": (NOW - timedelta(days=10)).isoformat(), "judged_at_attempt": 1000,
           "certificates_at_attempt": 10,
           "controls": {"producers": ["c"], "judged": 1000, "certificates": 10}}
    conv = {"c": {"judged": 1300, "certificates": 13}}
    ev = pl.evaluate(att, 1300, 10, conv, NOW)
    assert ev is not None and ev["outcome"] == "FAILED_REVERTED"
    assert ev["before_certs_per_judged"] == 0.01 and ev["after_certs_per_judged"] == 0.0
    assert pl.evaluate(att, 1100, 10, conv, NOW) is None            # sample not reached
    good = pl.evaluate(att, 1300, 16, conv, NOW)
    assert good is not None and good["outcome"] == "SUCCEEDED"


def test_a_config_remedy_is_applied_as_a_prescription_and_charged(
        tmp_path: Path, monkeypatch: Any) -> None:
    _sandbox(tmp_path, monkeypatch, conversion=_conv(good=(1000, 900, 20), ex=(1000, 0, 0)))
    st = {"diagnosis": {"available": True, "at": NOW.isoformat(), "producers": {
        "ex": {"histogram": {pl.EXOTIC_UNIVERSE: 800}, "exotic_share": 0.8,
               "dominant_family": "carry"}}}}
    pl.STATE.parent.mkdir(parents=True, exist_ok=True)
    pl.STATE.write_text(json.dumps(st), "utf-8")
    doc = pl.write(pl.build(now=NOW, force=False, apply=True))
    ex = {x["producer"]: x for x in doc["producers"]}["ex"]
    assert ex["stage_of_death"] == "JUDGE" and ex["remedy"] == pl.INSTRUMENT_REMAP
    # the cached diagnosis is fresh, so this pass did NOT recompute and applied nothing
    assert doc["diagnosis"]["recomputed_this_pass"] is False and "attempt_recorded" not in ex
    monkeypatch.setattr(pl, "diagnose", lambda **_: st["diagnosis"])
    doc = pl.write(pl.build(now=NOW + timedelta(hours=25), apply=True))
    ex = {x["producer"]: x for x in doc["producers"]}["ex"]
    assert ex["status"] == "FIX_QUEUED" and ex["attempt_recorded"] is True
    rx = json.loads(pl.PRESCRIPTIONS.read_text())["producers"]["ex"]
    assert rx["remedy"] == pl.INSTRUMENT_REMAP and rx["directive"]["universe"] == "non_exotic"
    assert pl.loop_trial_counts()[0] == 1


def test_diagnosis_is_daily_unless_forced(tmp_path: Path, monkeypatch: Any) -> None:
    _sandbox(tmp_path, monkeypatch)
    calls: list[int] = []

    def fake(**_: Any) -> dict[str, Any]:
        calls.append(1)
        return {"available": True, "producers": {}}

    monkeypatch.setattr(pl, "diagnose", fake)
    pl.write(pl.build(now=NOW))
    pl.write(pl.build(now=NOW + timedelta(hours=23)))
    assert len(calls) == 1
    pl.write(pl.build(now=NOW + timedelta(hours=23), force=True))
    pl.write(pl.build(now=NOW + timedelta(hours=48)))
    assert len(calls) == 3


def test_a_code_level_remedy_names_its_owner(tmp_path: Path, monkeypatch: Any) -> None:
    _sandbox(tmp_path, monkeypatch, conversion=_conv(good=(1000, 900, 20), dud=(1000, 900, 0)))
    st = {"diagnosis": {"available": True, "at": NOW.isoformat(), "producers": {
        "dud": {"histogram": {pl.NO_OOS_EDGE: 700, pl.COSTS: 10}, "exotic_share": 0.0}}}}
    pl.STATE.parent.mkdir(parents=True, exist_ok=True)
    pl.STATE.write_text(json.dumps(st), "utf-8")
    pl.BLOCKERS.parent.mkdir(parents=True, exist_ok=True)
    pl.BLOCKERS.write_text(json.dumps({"dud": {"why": "x" * 30, "owner": "thread-42"}}))
    row = {x["producer"]: x for x in pl.build(now=NOW).get("producers", [])}["dud"]
    assert row["status"] == "CODE_FIX_NEEDED" and row["remedy"] == pl.GRID_NARROW
    assert row["owner_thread"] == "thread-42"


def test_the_leg_is_wired_registered_and_contracted() -> None:
    hc = importlib.import_module("research.hourly_cycle")
    from libs.research.layers import LEG_LAYER
    assert "producer_loop" in hc.CORE_LEGS
    assert hc.department_of("producer_loop") == "meta"
    assert LEG_LAYER["producer_loop"] == "meta"
    assert hc.LEG_BUDGET_SEC["producer_loop"] >= 120
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("producer_loop"' in src and '"producer_loop": plp' in src
    contracts = json.loads((_ROOT / "docs" / "research" / "experiment_contracts.json")
                           .read_text("utf-8"))
    assert contracts["legs"]["producer_loop"]["metric"]["organ"] == "report:PRODUCER_LOOP.json"
    oc = (_ROOT / "ops" / "organ_contract.py").read_text("utf-8")
    assert '"desks/mt5/reports/PRODUCER_LOOP.json", 180' in oc
    merge = (_DESK / "research" / "merge_hypotheses.py").read_text("utf-8")
    assert "from research.producer_loop import reweight_rows" in merge


# ------------------------------------------------------------------------- successor producers

def _row(name: str, status: str = "HEALTHY", *, score: Any = 1.0, judged: Any = 1000,
         hist: Any = None, weight: float = 1.0) -> dict[str, Any]:
    return {"producer": name, "status": status, "score": score, "cells_judged": judged,
            "kill_class_histogram": hist if hist is not None else {pl.COSTS: 9, pl.NO_OOS_EDGE: 2},
            "weight": weight, "yield": {"edges_per_cpu_hour": 0.0}}


def test_a_parked_producer_spawns_exactly_one_successor_on_its_kill_class_axis() -> None:
    by = {"dud": _row("dud", "PARKED", weight=pl.WEIGHT_MIN), "good": _row("good")}
    d, rep, _ = pl.plan_successors(by, {}, now=NOW, pooled_yield=None, zero_cert=[])
    assert list(d) == ["dud~s1"]
    s1 = d["dud~s1"]
    assert s1["axis"] == pl.AXES_BY_KILL_CLASS[pl.COSTS][0] == pl.LOW_TURNOVER
    assert s1["parent"] == "dud" and s1["root"] == "dud" and s1["status"] == "LIVE"
    assert rep[0]["successor"] == "dud~s1" and rep[0]["parent_weight"] >= pl.WEIGHT_MIN
    # a second pass with the parent still parked does not spawn a duplicate
    by["dud~s1"] = _row("dud~s1", "UNMEASURED", score=pl.UNMEASURED, judged=pl.UNMEASURED)
    d2, _, _ = pl.plan_successors(by, d, now=NOW + timedelta(days=1), pooled_yield=None,
                                  zero_cert=[])
    assert sorted(d2) == ["dud~s1"] and d2["dud~s1"]["status"] == "LIVE"


def test_a_parked_successor_hands_the_lineage_the_next_untried_axis() -> None:
    by = {"dud": _row("dud", "PARKED"), "dud~s1": _row("dud~s1", "PARKED")}
    d = {"dud~s1": {"root": "dud", "parent": "dud", "generation": 1, "axis": pl.LOW_TURNOVER,
                    "status": "LIVE"}}
    d2, _, _ = pl.plan_successors(by, d, now=NOW, pooled_yield=None, zero_cert=[])
    assert d2["dud~s1"]["status"] == "PARKED"                      # closed, still a seed
    assert d2["dud~s2"]["parent"] == "dud~s1" and d2["dud~s2"]["generation"] == 2
    assert d2["dud~s2"]["axis"] == pl.AXES_BY_KILL_CLASS[pl.COSTS][1]      # next untried
    assert sum(1 for v in d2.values() if v["status"] == "LIVE") == 1        # one live per lineage
    # two failed close variants in a row: the next slot is a FRESH design
    by["dud~s2"] = _row("dud~s2", "PARKED")
    d3, _, _ = pl.plan_successors(by, d2, now=NOW, pooled_yield=None, zero_cert=[])
    assert d3["dud~s3"]["axis"] == pl.FRESH_DESIGN


def test_successor_rows_are_tagged_non_exotic_executable_and_never_touch_the_parent(
        monkeypatch: Any) -> None:
    import copy
    monkeypatch.setattr(pl, "_tradable", lambda s, f: True)
    monkeypatch.setattr(pl, "_peers", lambda s: ["AUDUSD", "USDZAR", "GBPUSD"])
    monkeypatch.setattr(pl, "_is_exotic", lambda s: s.upper() in ("USDZAR", "USDTRY"))
    parents = [{"symbol": "EURUSD", "family": "carry", "params": {"timeframe": "H1", "hold": 4},
                "producer": "dud", "id": "x1", "prejudge": {"flags": ["f"]}},
               {"symbol": "USDTRY", "family": "carry", "params": {"timeframe": "H1"},
                "producer": "dud"}]
    snap = copy.deepcopy(parents)
    for axis in (pl.LOW_TURNOVER, pl.WIDER_UNIVERSE, pl.REGIME_CONDITIONED,
                 pl.NON_EXOTIC_REMAP):
        kids = pl.successor_rows(parents, {"name": "dud~s1", "root": "dud", "parent": "dud",
                                           "generation": 1, "axis": axis},
                                 existing={pl.row_identity(r) for r in parents})
        assert kids, axis
        assert len(kids) <= pl.MAX_SUCCESSOR_ROWS
        for k in kids:
            assert k["producer"] == "dud~s1" and k["successor_of"] == "dud"
            assert k["design_axis"] == axis and k["origin"] == pl.SUCCESSOR_ORIGIN
            assert k["claim_family"] == "lineage:dud"
            assert k["family"] == "carry" and isinstance(k["params"], dict)
            assert k["symbol"] not in ("USDZAR", "USDTRY")             # exotics stay banned
            assert "id" not in k and "prejudge" not in k               # the parent's identity
            assert pl.row_identity(k) not in {pl.row_identity(r) for r in parents}
            assert pl.row_producer(k) == "dud~s1"
    reg = pl.successor_rows(parents, {"name": "dud~s1", "root": "dud",
                                      "axis": pl.REGIME_CONDITIONED})
    assert {k["params"]["regime"] for k in reg} <= {"high_vol", "low_vol"}  # cell_modifiers
    assert parents == snap                                         # never removed or altered
    assert pl.successor_rows(parents, {"name": "d", "root": "d",
                                       "axis": pl.DATA_SOURCE_SWAP}) == []


def test_the_fresh_design_takes_another_under_covered_family_and_keeps_the_lineage(
        monkeypatch: Any) -> None:
    monkeypatch.setattr(pl, "_tradable", lambda s, f: True)
    monkeypatch.setattr(pl, "_all_symbols", lambda: {})
    parents = [{"symbol": "EURUSD", "family": "carry", "params": {}, "producer": "miner_x"}]
    pool = [
        *parents,
        {"symbol": "XAUUSD", "family": "session_range_breakout", "params": {"a": 1},
         "producer": "alpha_registry", "source_id": "src:paper:ssrn"},
        {"symbol": "GBPUSD", "family": "trend", "params": {"b": 2}, "producer": "brain"},
        {"symbol": "GBPUSD", "family": "lonely", "params": {}, "producer": "some_miner"}]
    kids = pl.successor_rows(parents, {"name": "miner_x~s1", "root": "miner_x",
                                       "parent": "miner_x", "generation": 1,
                                       "axis": pl.FRESH_DESIGN},
                             pool=pool, coverage={"session_range_breakout": 50, "trend": 3},
                             existing={pl.row_identity(r) for r in pool})
    assert kids and {k["family"] for k in kids} == {"trend"}        # least judged, from the brain
    assert all(k["design_axis"] == pl.FRESH_DESIGN and k["symbol"] == "EURUSD" for k in kids)
    assert all(k["claim_family"] == "lineage:miner_x" for k in kids)
    assert pl.next_axis(None, [], "miner_x", 1, [])[0] == pl.FRESH_DESIGN    # its hashed slot


def test_a_lineage_is_one_trial_group_and_its_count_only_goes_up() -> None:
    from libs.research import trial_ledger as tl
    parent = [{"symbol": s, "family": f, "params": {"lookback": n}, "producer": "dud",
               "timeframe": "H1"}
              for s, f, n in (("EURUSD", "carry", 10), ("EURUSD", "trend", 20),
                              ("GBPUSD", "carry", 30))]
    plain = [dict(r) for r in parent]
    for r in parent:
        pl.stamp_lineage(r, "dud")
    g1 = [{**r, "params": {**r["params"], "regime": "high_vol"}, "producer": "dud~s1"}
          for r in parent]
    g2 = [{**r, "symbol": "AUDUSD", "producer": "dud~s2"} for r in g1]
    groups = {tl.trial_from_record(r).group for r in parent + g1 + g2}
    assert groups == {"lineage:dud"}
    # grouping the lineage never lowers the charge: same nominal, effective >= unstamped
    unstamped = plain + [{k: v for k, v in r.items() if k not in ("claim_family", "breadth_unit")}
                         for r in g1 + g2]
    a = tl.effective_independent_tests(parent + g1 + g2)
    b = tl.effective_independent_tests(unstamped)
    assert a.n_nominal == b.n_nominal and a.n_effective >= b.n_effective - 1e-9
    # lineage_trials: cumulative over parent + successors, ratcheted
    by = {"dud": _row("dud", judged=500), "dud~s1": _row("dud~s1", judged=300)}
    d = {"dud~s1": {"root": "dud", "parent": "dud", "generation": 1, "axis": pl.LOW_TURNOVER,
                    "status": "LIVE"}}
    _, _, t1 = pl.plan_successors(by, d, now=NOW, pooled_yield=None, zero_cert=[])
    assert t1["dud"]["lineage_trials"] == 800
    by["dud~s1"]["cells_judged"] = pl.UNMEASURED
    _, _, t2 = pl.plan_successors(by, d, now=NOW, pooled_yield=None, zero_cert=[],
                                  prev_trials=t1)
    assert t2["dud"]["lineage_trials"] == 800                      # never subtracted


def test_extend_docket_appends_successor_rows_and_merge_runs_it_before_the_intake(
        monkeypatch: Any) -> None:
    monkeypatch.setattr(pl, "_tradable", lambda s, f: True)
    monkeypatch.setattr(pl, "certificates_by_producer", lambda: {})
    rows = [{"symbol": "EURUSD", "family": "carry", "params": {"timeframe": "H1"},
             "producer": "dud"},
            {"symbol": "GBPUSD", "family": "trend", "params": {}, "producer": "other"}]
    d = {"dud~s1": {"root": "dud", "parent": "dud", "generation": 1,
                    "axis": pl.REGIME_CONDITIONED, "status": "LIVE"}}
    out, rep = pl.extend_docket(list(rows), designs=d)
    assert out[:2] == rows and rep["minted"] == 2 == len(out) - 2
    assert rows[0]["claim_family"] == "lineage:dud"                # the parent joins its lineage
    assert "claim_family" not in rows[1]
    merge = (_DESK / "research" / "merge_hypotheses.py").read_text("utf-8")
    i_ext = merge.index("_extend(rows_out, coverage=judged)")
    assert i_ext < merge.index("order_docket(rows_out") < merge.index("_reweight(rows_out)") \
        < merge.index("_pj.demote_flagged(")


def test_weights_follow_the_staged_score_and_never_fall_below_the_floor() -> None:
    from libs.research import live_yield as lv
    b = lv.blend_stages({
        "parent": {"certs_odds": 0.1, "expected_live": 0.1, "realised_elog": -0.5,
                   "n_forward": 40, "n_live_trades": 60},
        "succ": {"certs_odds": 1.0, "expected_live": 1.0, "realised_elog": 0.4,
                 "n_forward": 40, "n_live_trades": 60},
        "fresh": {"certs_odds": None, "expected_live": None, "realised_elog": None}})
    assert b["succ"]["relative"] > b["parent"]["relative"]
    assert b["parent"]["relative"] < 0                     # a negative realised Elog bites ...
    w = min(pl.WEIGHT_MAX, max(pl.WEIGHT_MIN, b["parent"]["relative"]))
    assert w == pl.WEIGHT_MIN                              # ... but never below the floor
    assert b["fresh"]["relative"] is None                  # unmeasured -> par in build
    assert lv.stage_weight(30, "realised_elog") == 1.0 and lv.stage_weight(10, "realised_elog") \
        == 10 / 40


def test_live_yield_shrinks_to_the_pool_credits_independence_and_reads_decay() -> None:
    from libs.research import live_yield as lv
    prior = {"p_cert_to_kept": 0.5, "p_kept_to_live": 0.2}
    few = lv.expected_one(10.0, 1, 0, 0, prior)
    assert 0.5 < few["stage_rates"]["p_cert_to_kept"] < 1.0           # shrunk, not 1/1
    many = lv.expected_one(10.0, 40, 10, 0, prior)
    assert many["stage_rates"]["p_cert_to_kept"] == 0.8                # own rate at n >= min
    assert lv.expected_one(10.0, 40, 10, 5, prior)["expected_live"] >= 5   # realised dominates
    assert lv.expected_one(10.0, None, None, None, prior)["expected_live"] == lv.UNMEASURED
    book = {("EURUSD", "carry", "fx_usd")}
    dup = lv.independence_credit({("EURUSD", "carry", "fx_usd")}, book | {("EURUSD", "carry",
                                                                           "fx_usd")})
    new = lv.independence_credit({("XAUUSD", "trend", "commodity")}, book)
    assert new["credit"] > 0.5 and new["basis"].startswith("PROXY")
    assert dup["credit"] <= new["credit"]
    dec = lv.read_decay({"verdicts": {"a": {"verdict": "FADE"},
                                      "b": {"verdict": "HEALTHY", "half_life_days": 40.0}}})
    assert dec is not None and dec["a"]["decaying"] and dec["b"]["half_life_days"] == 40.0
    assert lv.half_life(["b"], dec) == (40.0, "measured")
    assert lv.half_life(["a"], dec) == (lv.DEFAULT_HALF_LIFE_D, "default")
    el = lv.realised_elog({"s": {"risk_frac": 0.01}}, half_life_d=90.0, now=NOW,
                          trades_of=lambda n: [{"r_multiple": -1.0, "time": NOW.isoformat(),
                                                "risk_quote": 100.0, "commission": -1.0}])
    assert el["elog"] < 0 and el["n_trades"] == 1
    assert pl._spawn_trigger({"status": "HEALTHY", "score": 2.0,
                              "yield": {"decaying_live_edges": ["a"]}})


def test_two_sandbox_systems_are_two_producers(tmp_path: Path, monkeypatch: Any) -> None:
    reg_row = {"producer": "alpha_registry", "generator": "sandbox:qlib", "family": "f"}
    assert pl.row_producer(reg_row) == "sandbox:qlib"
    assert pl.row_producer({"producer": "alpha_registry", "source_id": "sandbox:rd_agent"}) \
        == "sandbox:rd_agent"
    out, _ = pl.reweight_rows([{**reg_row, "i": 0},
                               {"producer": "alpha_registry", "generator": "sandbox:alpha101",
                                "family": "f", "i": 1}],
                              {"sandbox:alpha101": 4.0, "sandbox:qlib": 0.25})
    assert [r["i"] for r in out] == [1, 0]                 # each system its own weight
    _sandbox(tmp_path, monkeypatch, conversion=_conv(**{"sandbox:qlib": (1000, 900, 9),
                                                        "sandbox:alpha101": (1000, 900, 0)}))
    monkeypatch.setattr(pl, "SANDBOX_STATE", tmp_path / "data" / "sandbox_runner_state.json")
    doc = pl.build(now=NOW, apply=False)
    fed = {x["producer"]: x for x in doc["federation"]}
    assert {"sandbox:qlib", "sandbox:alpha101", "sandbox:rd_agent"} <= set(fed)
    assert fed["sandbox:qlib"]["cpu_source"] == pl.UNMEASURED    # no compute clock given
    assert [x["rank"] for x in doc["federation"]] == list(range(1, len(doc["federation"]) + 1))


def test_every_producer_gets_a_gap_target_and_gap_coverage(tmp_path: Path,
                                                         monkeypatch: Any) -> None:
    _sandbox(tmp_path, monkeypatch, conversion=_conv(a=(1000, 900, 1)))
    monkeypatch.setattr(pl, "_all_symbols", lambda: {"fx_usd": ["EURUSD"],
                                                     "commodity": ["XAUUSD"]})
    diag = {"available": True, "at": NOW.isoformat(), "producers": {"a": {
        "histogram": {pl.PASSED: 1, pl.NO_OOS_EDGE: 40},
        "buckets": {"class:fx_usd": [41, 1], "class:commodity": [40, 0], "tf:H1": [81, 1]},
        "combos": {"fx_usd|H1||carry": [41, 1], "commodity|H1||trend": [40, 0]},
        "families": ["carry", "trend"], "passed_cells": [["EURUSD", "carry", "fx_usd", "H1", ""]],
        "exotic_share": 0.0}}}
    pl.STATE.parent.mkdir(parents=True, exist_ok=True)
    pl.STATE.write_text(json.dumps({"diagnosis": diag}), "utf-8")
    doc = pl.write(pl.build(now=NOW, apply=False))
    assert doc["zero_cert_classes"] == ["class:commodity"]
    pr = doc["producers"][0]["pass_rate"]
    assert pr["class:fx_usd"]["pass_rate"] == round(1 / 41, 6)
    gaps = doc["coverage_gaps"]
    assert "commodity" in gaps["classes"] and "families" in gaps
    gt = json.loads(pl.PRESCRIPTIONS.read_text())["gap_target"]["a"]
    assert gt["gap_share"] == pl.GAP_SHARE and "commodity" in gt["classes"]
    assert "families" in gt
    gc = doc["gap_coverage"]["a"]
    assert gc["gap_row_share"] > 0 and "independence_credit" in gc
    assert doc["producers"][0]["failed_volume_share"] == round(899 / 900, 6)


def test_a_lineage_groups_trials_but_breadth_counts_per_parent_cell(monkeypatch: Any) -> None:
    from libs.research import claim_selection as cs
    from libs.research import trial_ledger as tl
    monkeypatch.setattr(pl, "_tradable", lambda s, f: True)
    monkeypatch.setattr(pl, "_all_symbols", lambda: {})
    parents = [{"symbol": s, "family": "carry", "params": {"timeframe": "H1", "n": i},
                "producer": "dud"} for i, s in enumerate(("EURUSD", "GBPUSD", "AUDUSD"))]
    for r in parents:
        pl.stamp_lineage(r, "dud")
        cs.stamp(r)                         # the merge's later claim-selection pass
    assert cs.breadth(parents)["breadth_units"] == 3          # the parent keeps 3 units
    kids = pl.successor_rows(parents, {"name": "dud~s1", "root": "dud", "parent": "dud",
                                       "generation": 1, "axis": pl.REGIME_CONDITIONED})
    variants = [next(k for k in kids if k["breadth_unit"] == cs.breadth_unit(p))
                for p in parents]
    assert len(variants) == 3
    fresh = pl.successor_rows(parents, {"name": "dud~s2", "root": "dud", "parent": "dud~s1",
                                        "generation": 2, "axis": pl.FRESH_DESIGN},
                              pool=[{"symbol": "EURUSD", "family": "trend", "params": {},
                                     "producer": "brain"}])[:1]
    assert len(fresh) == 1
    for r in variants + fresh:
        cs.stamp(r)
    assert cs.breadth(parents + variants)["breadth_units"] == 3      # variants add 0
    assert cs.breadth(parents + variants + fresh)["breadth_units"] == 4   # fresh adds 1
    groups = {tl.trial_from_record(r).group for r in parents + variants + fresh}
    assert groups == {"lineage:dud"}                                  # one trial lineage


def test_exotic_check_fails_closed_when_the_policy_is_unreadable(monkeypatch: Any) -> None:
    """Audit should-fix 2026-11-25: an import fault must never let an exotic symbol through."""
    import builtins
    real = builtins.__import__

    def boom(name: str, *a: Any, **k: Any) -> Any:
        if name == "research.universe_policy":
            raise ImportError("policy unreadable")
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", boom)
    assert pl._is_exotic("EURUSD") is True
