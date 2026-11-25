"""The judge calibration loop (LOOP_COVERAGE L2): forward results flow back to the judge.

Pins: the forward/backtest ratio reads MATURED clocks only; leaks and false kills are counted;
priors are two-sided and a prior that loses leave-one-family-out is never published; a published
prior that loses on newly matured clocks reverts; a gate move is chosen leave-one-family-out and
reports its missed growth; every candidate bar is appended to the one trial count; a join family
without an audited point-in-time join is PROVISIONAL; absent inputs read UNMEASURED, never 0; the
cadence; and the leg's wiring in every registry a leg must be in.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import judge_calibration as jc  # noqa: E402

T0 = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
GATES_OK = {"in_sample_screen": {"passed": True, "sharpe": 0.3},
            "deflated_sharpe": {"passed": True, "dsr": 0.99},
            "pbo": {"passed": True, "pbo": 0.1},
            "reality_check_spa": {"passed": True, "p_value": 0.0},
            "cpcv": {"passed": True, "mean_oos_sharpe": 0.3},
            "walk_forward": {"passed": True, "oos_sharpe": 0.3, "stability": 1.0},
            "stress_costs": {"passed": True, "exp_x3": 0.2},
            "lockbox": {"passed": True, "lockbox_sharpe": 0.3}}
POLICY = {"version": "test", "dsr_threshold": 0.95, "pbo_max": 0.5, "spa_alpha": 0.05,
          "wf_min_oos_sharpe": 0.0, "cpcv_mean_oos_sharpe_min_exclusive": 0.0,
          "lockbox_oos_sharpe_min": 0.0, "expected_value_min_exclusive": 0.0}
KBD_OK = {"generated_utc": "2026-11-24T00:00:00+00:00", "certificate_inputs": {
    "providers": {"_bars": {"families": ["cross_asset_residual"], "verdict": "OK",
                            "assumed": []}}, "verdict": "OK"}}


def _cert(sym: str, fam: str, ev: float, **metrics: float) -> tuple[str, dict[str, Any]]:
    gates = {g: dict(v) for g, v in GATES_OK.items()}
    gates["expected_value"] = {"passed": True, "ev": ev}
    for g, (field, *_rest) in jc.GATE_METRICS.items():
        if field in metrics:
            gates[g][field] = metrics[field]
    return f"external.{sym}.{fam}.p=x", {
        "cell": f"{sym}.{fam}", "gates": gates,
        "shadow_spec": {"symbol": sym, "selector": "asia", "family": fam, "params": {}}}


def _clock(status: str, exp_r: float, n: int = 30) -> dict[str, Any]:
    return {"status": status, "n": n, "exp_r": exp_r, "gate_admission":
            "ORIGINAL_UNIVERSAL_10_PASS"}


def _desk(tmp: Path, certs: list[tuple[str, dict[str, Any]]], clocks: dict[str, dict[str, Any]],
          *, kbd: Any = KBD_OK, near: dict[str, Any] | None = None) -> jc.Paths:
    paths = jc.Paths.under(tmp)
    (tmp / "reports" / "shadow").mkdir(parents=True, exist_ok=True)
    (tmp / "data").mkdir(parents=True, exist_ok=True)
    paths.lanes[0].write_text(json.dumps(clocks), "utf-8")
    paths.canons[0].write_text(json.dumps({"gate_policy": POLICY,
                                           "survivors": dict(certs)}), "utf-8")
    if kbd is not None:
        paths.known_by_date.write_text(json.dumps(kbd), "utf-8")
    if near is not None:
        paths.near_miss[1].write_text(json.dumps({"candidates": near}), "utf-8")
    return paths


def _family_book(fam: str, syms: list[str], ratios: list[float], ev: float = 0.2,
                 status: str = "PROMOTION CANDIDATE") -> tuple[list, dict]:
    certs, clocks = [], {}
    for sym, r in zip(syms, ratios, strict=True):
        certs.append(_cert(sym, fam, ev))
        clocks[f"{sym}.{fam}.asia"] = _clock(status, r * ev)
    return certs, clocks


def test_forward_over_backtest_reads_matured_clocks_only(tmp_path: Path) -> None:
    certs = [_cert("EURUSD", "overnight_gap_decay", 0.2),
             _cert("GBPUSD", "overnight_gap_decay", 0.2)]
    clocks = {"EURUSD.overnight_gap_decay.asia": _clock("PROMOTION CANDIDATE", 0.3),
              # an ACTIVE clock with a huge edge must not move the ratio at all
              "GBPUSD.overnight_gap_decay.asia": _clock("ACTIVE", 5.0)}
    doc = jc.build(_desk(tmp_path, certs, clocks), now=T0, control_fraction=0)
    fam = doc["per_family"]["overnight_gap_decay"]
    assert fam["matured"] == 1 and fam["forward_over_backtest"] == 1.5
    assert doc["summary"]["immature_clocks_excluded"] == 1
    assert doc["matured_keys"] == ["EURUSD.overnight_gap_decay.asia"]


def test_leaks_and_false_kills_are_counted(tmp_path: Path) -> None:
    certs = [_cert("EURUSD", "formula", 0.2), _cert("GBPUSD", "formula", 0.2)]
    nk, nrow = _cert("AUDUSD", "formula", 0.2, dsr=0.5)      # near-miss: failed DSR only
    fk, frow = _cert("NZDUSD", "formula", 0.2, dsr=0.6)
    clocks = {"EURUSD.formula.asia": _clock("PROMOTION CANDIDATE", 0.2),
              "GBPUSD.formula.asia": _clock("KILL", -0.1),          # certified, failed: a leak
              "AUDUSD.formula.asia": _clock("PROMOTION CANDIDATE", 0.25),  # a false kill
              "NZDUSD.formula.asia": _clock("KILL", -0.05)}         # a true kill
    paths = _desk(tmp_path, certs, clocks, near={nk: nrow, fk: frow})
    doc = jc.build(paths, now=T0, control_fraction=0)
    assert doc["summary"]["leaks"] == 1
    assert doc["per_family"]["formula"]["leaks"] == 1
    assert doc["summary"]["false_kills"] == 1 and doc["false_kills"]["status"] == "MEASURED"
    fkd = doc["per_gate"]["deflated_sharpe"]["false_kills"]
    assert fkd == {"status": "MEASURED", "near_miss_matured": 2, "false_kills": 1,
                   "true_kills": 1}
    assert sum(g["leaks_narrowest_here"] for g in doc["per_gate"].values()) == 1


def test_a_clock_with_no_certificate_row_still_counts_as_a_leak(tmp_path: Path) -> None:
    clocks = {"EURUSD.carry.asia#input_symbol=EURUSD": _clock("KILL", -0.1),
              "GBPUSD.carry.asia#input_symbol=GBPUSD": _clock("PROMOTION CANDIDATE", 0.1)}
    doc = jc.build(_desk(tmp_path, [], clocks), now=T0, control_fraction=0)
    fam = doc["per_family"]["carry"]
    assert fam["leaks"] == 1 and fam["kept"] == 1
    assert fam["forward_over_backtest"] == jc.UNMEASURED      # no backtest figure to divide by
    assert doc["summary"]["unjoined_matured"] == 2 and doc["summary"]["n_matured_joined"] == 0


def test_priors_are_two_sided(tmp_path: Path) -> None:
    a = _family_book("overnight_gap_decay", ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"],
                     [1.8, 1.7, 1.9, 1.8])
    b = _family_book("formula", ["EURJPY", "GBPJPY", "AUDJPY", "NZDJPY"], [0.3, 0.35, 0.25, 0.3])
    c = _family_book("clock_transition", ["EURCHF", "GBPCHF", "AUDCHF", "NZDCHF"],
                     [1.0, 1.05, 0.95, 1.0])
    paths = _desk(tmp_path, a[0] + b[0] + c[0], {**a[1], **b[1], **c[1]})
    doc = jc.run(paths, now=T0, control_fraction=0)
    pa = doc["per_family"]["overnight_gap_decay"]["prior"]
    pb = doc["per_family"]["formula"]["prior"]
    assert pa["status"] == "PUBLISHED" and pa["prior"] > 1.0 and pa["side"] == "above_1"
    assert pb["status"] == "PUBLISHED" and pb["prior"] < 1.0 and pb["side"] == "below_1"
    prop = json.loads(paths.proposals.read_text("utf-8"))
    assert prop["priors"]["overnight_gap_decay"]["prior"] == pa["prior"]
    assert prop["status"] == "PROPOSED_NOT_APPLIED"
    assert prop["sealed_call_site"]["file"] == "desks/mt5/research/gate_policy.py"


def test_leave_one_family_out_rejects_an_overfit_prior(tmp_path: Path) -> None:
    x = _family_book("overnight_gap_decay", ["EURUSD", "GBPUSD"], [4.5, -0.5])
    b = _family_book("formula", ["EURJPY", "GBPJPY", "AUDJPY"], [1.0, 1.05, 0.95])
    c = _family_book("clock_transition", ["EURCHF", "GBPCHF", "AUDCHF"], [1.0, 0.95, 1.05])
    paths = _desk(tmp_path, x[0] + b[0] + c[0], {**x[1], **b[1], **c[1]})
    doc = jc.run(paths, now=T0, control_fraction=0)
    px = doc["per_family"]["overnight_gap_decay"]["prior"]
    assert px["fitted"] > 1.0                                  # in sample it looks like an edge
    assert px["status"] == "REJECTED_LOFO" and px["published"] is False and px["prior"] is None
    assert not px["validation"]["beats_no_prior"]
    prop = json.loads(paths.proposals.read_text("utf-8"))
    assert prop["priors"]["overnight_gap_decay"]["published"] is False


def test_a_published_prior_that_loses_on_new_clocks_reverts(tmp_path: Path) -> None:
    a = _family_book("overnight_gap_decay", ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"],
                     [1.8, 1.7, 1.9, 1.8])
    b = _family_book("formula", ["EURJPY", "GBPJPY", "AUDJPY", "NZDJPY"], [0.3, 0.35, 0.25, 0.3])
    c = _family_book("clock_transition", ["EURCHF", "GBPCHF", "AUDCHF", "NZDCHF"],
                     [1.0, 1.05, 0.95, 1.0])
    paths = _desk(tmp_path, a[0] + b[0] + c[0], {**a[1], **b[1], **c[1]})
    jc.run(paths, now=T0, control_fraction=0)
    # two new overnight clocks mature far BELOW their backtest: the >1 prior now loses
    more = _family_book("overnight_gap_decay", ["USDCAD", "USDCHF"], [0.2, 0.1])
    clocks = json.loads(paths.lanes[0].read_text("utf-8")) | more[1]
    paths.lanes[0].write_text(json.dumps(clocks), "utf-8")
    canon = json.loads(paths.canons[0].read_text("utf-8"))
    canon["survivors"].update(dict(more[0]))
    paths.canons[0].write_text(json.dumps(canon), "utf-8")
    doc = jc.run(paths, now=T0 + timedelta(hours=1), control_fraction=0)
    pa = doc["per_family"]["overnight_gap_decay"]["prior"]
    assert pa["status"] == "REVERTED" and pa["published"] is False
    prop = json.loads(paths.proposals.read_text("utf-8"))
    assert prop["history"][-1]["reverted"] == ["overnight_gap_decay"]
    assert len(prop["history"]) == 2                           # the evidence is kept


def _gate_book() -> tuple[list, dict]:
    certs, clocks = [], {}
    fams = ("overnight_gap_decay", "formula", "clock_transition")
    syms = ("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD")
    for fam in fams:
        for i, sym in enumerate(syms):
            leak = i == 0
            certs.append(_cert(sym, fam, 0.2, dsr=0.96 if leak else 0.99 + 0.001 * i))
            clocks[f"{sym}.{fam}.asia"] = _clock("KILL" if leak else "PROMOTION CANDIDATE",
                                                 -0.1 if leak else 0.2)
    return certs, clocks


def test_a_gate_move_is_chosen_leave_one_family_out_and_reports_missed_growth(
        tmp_path: Path) -> None:
    certs, clocks = _gate_book()
    doc = jc.build(_desk(tmp_path, certs, clocks), now=T0, control_fraction=0)
    mv = doc["threshold_moves"]["deflated_sharpe"]
    assert mv["move"] == "TIGHTEN" and mv["before"] == 0.95 and 0.96 < mv["after"] <= 0.991
    assert mv["lofo_error_after"] < mv["lofo_error_before"] == 3
    assert mv["missed_growth"]["keepers_rejected"] == 0
    # loosening needs rejected cells with a forward clock; none here
    assert mv["loosening"]["status"] == jc.UNMEASURED
    assert doc["summary"]["threshold_moves"] == 1                  # one move per build (R3)


def test_every_candidate_bar_is_appended_to_the_one_trial_count(tmp_path: Path) -> None:
    certs, clocks = _gate_book()
    paths = _desk(tmp_path, certs, clocks)
    paths.trials.write_text(json.dumps({"build_id": "older", "family": "formula",
                                        "trials": 7}) + "\n", "utf-8")
    doc = jc.run(paths, now=T0, control_fraction=0)
    ch = doc["trials"]
    assert ch["charged"] > 0 and ch["families"] == 3
    rows = [json.loads(ln) for ln in paths.trials.read_text("utf-8").splitlines()]
    assert rows[0] == {"build_id": "older", "family": "formula", "trials": 7}  # never rewritten
    assert {r["family"] for r in rows[1:]} == {"overnight_gap_decay", "formula",
                                               "clock_transition"}
    # the same build is never charged twice
    again = jc.charge_trials(paths.trials, doc["build_id"], doc["built_at"],
                             ["formula"], doc["threshold_moves"])
    assert again["charged"] == 0
    from libs.research import experiment_ledger as el
    total, by_fam = el._judge_calibration_counts(paths.trials)
    assert by_fam["formula"] == 7 + ch["per_family"]
    assert total == 7 + ch["charged"]


def test_a_join_family_without_an_audited_pit_join_is_provisional(tmp_path: Path) -> None:
    certs = [_cert("EURUSD", "carry", 0.2), _cert("GBPUSD", "cross_asset_residual", 0.2),
             _cert("AUDUSD", "formula", 0.2)]
    doc = jc.build(_desk(tmp_path, certs, {}), now=T0, control_fraction=0)
    fam = doc["per_family"]
    assert fam["carry"]["information"]["join"] is True
    assert fam["carry"]["certificate_status"] == "PROVISIONAL"
    assert fam["carry"]["pit_join_audit"]["status"] == "NOT_AUDITED"
    assert fam["cross_asset_residual"]["certificate_status"] == "STANDING"   # fence clears it
    assert fam["formula"]["certificate_status"] == "STANDING"
    assert fam["formula"]["pit_join_audit"]["status"] == "NOT_APPLICABLE"
    prov = doc["_proposals"]["provisional_certificates"]
    assert [p["family"] for p in prov] == ["carry"]
    # with no PIT audit artifact at all, the join family cannot stand
    doc2 = jc.build(_desk(tmp_path / "b", certs, {}, kbd=None), now=T0, control_fraction=0)
    xar = doc2["per_family"]["cross_asset_residual"]
    assert xar["pit_join_audit"]["status"] == jc.UNMEASURED
    assert xar["certificate_status"] == "PROVISIONAL"


def test_a_clean_fence_is_reopened_by_a_forward_leak_far_above_price_only(
        tmp_path: Path) -> None:
    syms = [f"S{i:02d}USD" for i in range(10)]
    clocks = {f"{s}.cross_asset_residual.asia": _clock("KILL", -0.1) for s in syms}
    clocks |= {f"{s}.formula.asia": _clock("PROMOTION CANDIDATE", 0.1) for s in syms}
    doc = jc.build(_desk(tmp_path, [], clocks), now=T0, control_fraction=0)
    xar = doc["per_family"]["cross_asset_residual"]
    assert xar["pit_join_audit"]["status"] == "REOPENED_BY_FORWARD"
    assert xar["certificate_status"] == "PROVISIONAL"


def test_absent_inputs_read_unmeasured_never_zero(tmp_path: Path) -> None:
    doc = jc.build(jc.Paths.under(tmp_path), now=T0)
    s = doc["summary"]
    assert s["false_kills"] == jc.UNMEASURED
    assert s["forward_over_backtest_all"] == jc.UNMEASURED
    assert doc["false_kills"]["status"] == jc.UNMEASURED and doc["false_kills"]["why"]
    assert all(v == jc.UNMEASURED for v in doc["inputs"]["canons"].values())
    assert all(v == jc.UNMEASURED for v in doc["inputs"]["lanes"].values())
    assert doc["inputs"]["gate_verdict_digest"] == jc.UNMEASURED
    for g in doc["per_gate"].values():
        assert g["false_kills"]["status"] == jc.UNMEASURED
        assert g["rejections_ledger"] == jc.UNMEASURED
    assert doc["trials"]["charged"] == 0


def test_cadence_rebuilds_on_a_maturity_or_after_a_week(tmp_path: Path) -> None:
    certs = [_cert("EURUSD", "formula", 0.2), _cert("GBPUSD", "formula", 0.2)]
    clocks = {"EURUSD.formula.asia": _clock("PROMOTION CANDIDATE", 0.2),
              "GBPUSD.formula.asia": _clock("ACTIVE", 0.2)}
    paths = _desk(tmp_path, certs, clocks)
    first = jc.run(paths, now=T0)
    assert first["cadence"]["recomputed"] is True
    quiet = jc.run(paths, now=T0 + timedelta(days=1))
    assert quiet["cadence"]["recomputed"] is False
    assert quiet["built_at"] == first["built_at"] and quiet["checked_at"] != first["checked_at"]
    clocks["GBPUSD.formula.asia"] = _clock("KILL", -0.1)
    paths.lanes[0].write_text(json.dumps(clocks), "utf-8")
    matured = jc.run(paths, now=T0 + timedelta(days=2))
    assert matured["cadence"]["recomputed"] is True and "matured" in matured["cadence"]["why"]
    assert jc.run(paths, now=T0 + timedelta(days=3))["cadence"]["recomputed"] is False
    weekly = jc.run(paths, now=T0 + timedelta(days=9, hours=1))
    assert weekly["cadence"]["recomputed"] is True and "day(s) old" in weekly["cadence"]["why"]


def test_controls_are_held_unchanged(tmp_path: Path) -> None:
    a = _family_book("overnight_gap_decay", ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"],
                     [1.8, 1.7, 1.9, 1.8])
    b = _family_book("formula", ["EURJPY", "GBPJPY", "AUDJPY", "NZDJPY"], [0.3, 0.35, 0.25, 0.3])
    doc = jc.build(_desk(tmp_path, a[0] + b[0], {**a[1], **b[1]}), now=T0, control_fraction=0.5)
    ctl = doc["summary"]["control_families"]
    assert len(ctl) == 1
    p = doc["per_family"][ctl[0]]["prior"]
    assert p["status"] == "CONTROL" and p["prior"] is None and p["control"] is True


def _load(name: str, rel: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_leg_is_wired_contracted_and_published() -> None:
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("judge_calibration", lambda: _producer(' in src
    assert '"judge_calibration", "research/judge_calibration.py"))' in src
    assert '"judge_calibration": jcal' in src
    core = src[src.index("CORE_LEGS: frozenset[str]"):src.index("LEG_DEPARTMENT: dict")]
    assert '"judge_calibration"' in core
    budget = src[src.index("LEG_BUDGET_SEC: dict[str, int]"):]
    assert '"judge_calibration": 180' in budget
    validate = src[src.index("# validate: the adversarial evidence lab"):
                   src.index("# macro: the cross-asset / macro brain")]
    assert '"judge_calibration"' in validate
    from libs.research import layers
    assert layers.LEG_LAYER["judge_calibration"] == "meta"
    legs = json.loads((ROOT / "docs" / "research" / "experiment_contracts.json")
                      .read_text("utf-8"))["legs"]
    assert legs["judge_calibration"]["metric"]["organ"] == "report:JUDGE_CALIBRATION.json"
    oc = _load("organ_contract_jc", "ops/organ_contract.py")
    rel, minutes, _why = oc.CONTRACTS["MT5-HourlyCore (judge calibration)"]
    assert rel == "desks/mt5/reports/JUDGE_CALIBRATION.json" and minutes == 180
    assert "!desks/mt5/reports/JUDGE_CALIBRATION.json" in (ROOT / ".gitignore").read_text("utf-8")
    sync = (DESK / "scripts" / "sync_shadow_to_git.ps1").read_text("utf-8")
    assert '"desks/mt5/reports/JUDGE_CALIBRATION.json"' in sync
    assert '"desks/mt5/data/JUDGE_CALIBRATION_PROPOSALS.json"' in sync
