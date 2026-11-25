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
    doc = pl.build(now=NOW, apply=False)
    by = {x["producer"]: x for x in doc["producers"]}
    ya, yb = by["alpha"]["yield"], by["beta"]["yield"]
    assert 2.0 <= ya["k_eff_edges"] < 3.0          # the two carry clones are not two edges
    assert ya["forward_keep_rate_used"] == 1.0 and yb["forward_keep_rate_used"] == 0.0
    assert ya["cpu_hours_window"] == 30.0
    assert ya["edges_per_cpu_hour"] > 0 and yb["edges_per_cpu_hour"] == 0.0
    assert by["alpha"]["weight"] == 1.0            # the median of the positive yields
    assert by["beta"]["weight"] == pl.WEIGHT_MIN and by["gamma"]["weight"] == pl.WEIGHT_MIN
    assert by["beta"]["stage_of_death"] == "FORWARD"
    w = json.loads(pl.write(doc) and pl.WEIGHTS.read_text())
    assert w["producers"]["beta"]["weight"] == pl.WEIGHT_MIN


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
