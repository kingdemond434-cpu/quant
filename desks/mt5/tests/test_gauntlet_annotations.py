"""Certificate annotations are MEASUREMENT beside the verdict, never a gate (Tier-1 wave W1).

Items V1, V5, V8, V13, V15, V19, V21 and A8 of the Tier-1 audit. Every block records something
next to a verdict or a certificate; nothing may move a threshold, and a failure inside an
annotation must land as UNMEASURED on that annotation while the certificate is still written.
These tests pin both halves: what is recorded, and that recording it changes nothing.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from scripts import external_gauntlet as eg  # noqa: E402

SRC = (DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")


def _daily(n: int = 200, mu: float = 0.05, seed: int = 1) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(mu, 0.5, n), index=pd.bdate_range("2025-01-01", periods=n))


def _bars(days: int = 300, seed: int = 3) -> pd.DataFrame:
    """Hourly tz-aware bars, the shape `_h1` hands every family (test_validation_layer's)."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=days * 24, freq="h", tz="UTC")
    c = np.exp(np.cumsum(rng.normal(scale=0.001, size=idx.size))) * 1800
    o = np.concatenate([[c[0]], c[:-1]])
    spread = np.abs(rng.normal(scale=0.002, size=idx.size)) * c
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) + spread,
                         "low": np.minimum(o, c) - spread, "close": c}, index=idx)


# ------------------------------------------------------------------------------- the laws
def test_the_gates_and_their_constants_are_untouched() -> None:
    assert (eg.DSR_THRESHOLD, eg.PBO_THRESHOLD, eg.SPA_ALPHA) == (0.95, 0.5, 0.05)
    assert (eg.WF_SPLITS, eg.WF_MIN_STABILITY, eg.COST_SCENARIO) == (4, 0.5, 3.0)
    assert 'passed = all(s["passed"] for s in stages.values())' in SRC
    # Annotations are applied AFTER the unrunnable refusal and BEFORE the seal, on the row only.
    i_ref = SRC.index("_why = _certificate_refusal(row)")
    i_ann = SRC.index("row.update(certificate_annotations(")
    i_seal = SRC.index("survivors_all[key] = row")
    assert i_ref < i_ann < i_seal


# ------------------------------------------------------------------------------ V1 / V21
def test_gate_independence_counts_lockbox_restating_walk_forward() -> None:
    same = {"lockbox": {"lockbox_sharpe": 0.4}, "walk_forward": {"oos_sharpe": 0.4},
            "pbo": {"pbo": 0.2}, "reality_check_spa": {"p_value": 0.01}}
    diff = {**same, "lockbox": {"lockbox_sharpe": 0.3}}
    verdicts = [{"stages": same}, {"stages": same}, {"stages": diff},
                {"unmeasured": True, "stages": {"observations": {"passed": False}}}]
    gi = eg.gate_independence(verdicts)
    assert gi["lockbox_restates_walk_forward"] == {"n": 2, "of": 3}
    assert gi["pbo_spa_broadcast"]["per_matrix"] is True
    assert gi["pbo_spa_broadcast"]["distinct_pbo_values"] == 1
    assert gi["pbo_spa_broadcast"]["distinct_spa_p_values"] == 1
    assert "no pass/fail decision is changed" in gi["note"]


def test_run_gauntlet_result_carries_independence_and_the_trial_ledger(monkeypatch) -> None:
    daily = pd.Series(np.sin(np.arange(120) / 7.0) * 0.1 + 0.01,
                      index=pd.date_range("2025-01-01", periods=120, freq="D"))
    monkeypatch.setattr(eg, "daily_series", lambda *_a, **_kw: daily)
    cell = {"sym": "XAUUSD", "family": "cot_positioning", "params": {},
            "mechanism_status": "NAMED", "df": None, "sigs": [], "costs": None}
    result = eg.run_gauntlet([cell], "single-cell", {})
    gi = result["gate_independence"]
    assert gi["lockbox_restates_walk_forward"] == {"n": 1, "of": 1}
    tl = result["trial_ledger"]
    assert tl["status"] in ("MEASURED", "UNMEASURED")
    assert "cot_positioning" in tl["family_trials"]
    assert "never sets the bar" in tl["note"]
    # The sealed charge is still the only n_trials the gate saw.
    assert result["n_trials"] == result["verdicts"][0]["stages"]["deflated_sharpe"]["n_trials"]


def test_lifetime_trial_report_reads_the_ledger_and_never_invents_zero(monkeypatch,
                                                                       tmp_path) -> None:
    from libs.research import experiment_ledger as el
    led = tmp_path / "EXPERIMENT_LEDGER.json"
    led.write_text(json.dumps({"generated_utc": "t", "lifetime_trials": 30727,
                               "by_family": {"carry": 12, "discovered": 20341}}), "utf-8")
    monkeypatch.setattr(el, "OUT", led)
    rep = eg.lifetime_trial_report(["carry", "discovered", "asia_momentum"])
    assert rep["status"] == "MEASURED" and rep["lifetime_trials"] == 30727
    assert rep["family_trials"] == {"asia_momentum": None, "carry": 12, "discovered": 20341}
    assert rep["families_absent_from_ledger"] == ["asia_momentum"]

    absent = tmp_path / "absent.json"
    monkeypatch.setattr(el, "OUT", absent)
    rep = eg.lifetime_trial_report(["carry"])
    assert rep["status"] == "UNMEASURED" and rep["lifetime_trials"] is None
    assert rep["family_trials"] == {"carry": None}
    assert "pf_allocator" in rep["why"]
    assert not absent.exists(), "the judge must never write another organ's ledger"


# ------------------------------------------------------------------------------------ V8
def test_stage0_prefilter_reports_what_the_filter_would_decide() -> None:
    assert eg.stage0_prefilter("good", _daily(mu=0.3))["verdict"] == "ESCALATE"
    rej = eg.stage0_prefilter("bad", _daily(mu=-0.3))
    assert rej["verdict"] == "REJECT" and rej["reason"] == "wrong-sign-insample"
    assert eg.stage0_prefilter("empty", pd.Series(dtype=float))["verdict"] == "UNJUDGED"


def test_stage0_calendar_fills_inactive_days_with_zero() -> None:
    ds = pd.Series([1.0, 2.0], index=[date(2025, 1, 6), date(2025, 1, 10)])  # Mon .. Fri
    cal = eg._calendar_series(ds)
    assert len(cal) == 5 and cal.sum() == 3.0 and int((cal == 0).sum()) == 3


def test_stage0_summary_removes_nothing_and_ledgers_by_decision(tmp_path) -> None:
    summary, by_cell = eg.stage0_new_summary(), {}
    bad = {"sym": "EURUSD", "family": "carry", "params": {"input_symbol": "3M"}}
    good = {"sym": "EURUSD", "family": "vol_transition", "params": {}}
    eg.stage0_record(summary, by_cell, bad, "H1", _daily(mu=-0.3))
    eg.stage0_record(summary, by_cell, good, "H1", _daily(mu=0.3))
    assert summary["rejected"] == 1 and summary["escalated"] == 1
    cid_bad = eg.cell_id({**bad, "timeframe": "H1"})
    cid_good = eg.cell_id({**good, "timeframe": "H1"})
    verdicts = [{"cell": cid_bad, "passed": False, "stages": {"x": {"passed": False}}},
                {"cell": cid_good, "passed": True, "stages": {"x": {"passed": True}}},
                {"cell": "never-cached", "passed": True, "stages": {}}]
    led = tmp_path / "led.jsonl"
    block = eg.stage0_summary(summary, by_cell, verdicts, led)
    assert block["mode"] == "report-only" and block["cells_removed_from_docket"] == 0
    assert block["rejected"] == 1 and block["why_counts"] == {"wrong-sign-insample": 1}
    assert block["agreement_with_gauntlet"]["REJECT"]["gauntlet_fail"] == 1
    assert block["agreement_with_gauntlet"]["ESCALATE"]["gauntlet_pass"] == 1
    assert verdicts[0]["stage0"] == {"verdict": "REJECT", "reason": "wrong-sign-insample"}
    assert "stage0" not in verdicts[2]
    assert "REPORT-ONLY" in block["note"] and "No cell was removed" in block["note"]
    rows = [json.loads(ln) for ln in led.read_text("utf-8").splitlines()]
    assert len(rows) == 2 == block["ledger_rows_appended"]
    assert {r["verdict"] for r in rows} == {"REJECT", "ESCALATE"}
    assert all(r["mode"] == "report-only" and r["cells_removed_from_docket"] == 0
               and r["n"] == 1 and len(r["sample_cells"]) == 1 for r in rows)


def test_stage0_is_wired_on_the_cached_branch_and_drops_nothing() -> None:
    i_loop = SRC.index("for spec in eligible_specs:")
    assert SRC.index("_stage0 = stage0_new_summary()") < i_loop
    i_cached = SRC.index("ds1, ds3 = cached")
    assert SRC.index("stage0_record(_stage0, _stage0_verdicts, spec, spec_tf, ds1)") > i_cached
    assert 'result["pre_filter"] = _safe(' in SRC
    loop_src = SRC[i_loop:SRC.index("if cache_hits:")]
    assert "REJECT" not in loop_src, "the build loop must not act on a Stage 0 verdict"


# ----------------------------------------------------------------------------------- V13
def test_certificate_complexity_counts_free_params_and_conditions() -> None:
    ds = _daily(n=100)
    c = eg.certificate_complexity(
        "discovered", {"feature": "ext_resid_EURMXN_z", "band": [0.9, 1.0], "horizon": 1,
                       "side": 1, "timeframe": "H1"}, ds)
    assert c["status"] == "MEASURED" and c["n_params"] == 4 and c["n_conditions"] == 2
    assert c["condition_keys"] == ["band", "feature"]
    assert c["expression_nodes"] is None and "leaf" in c["expression_nodes_why"]
    span = (ds.index[-1] - ds.index[0]).days + 1
    assert c["turnover_per_day"] == pytest.approx(100 / span)
    assert "active trading days" in c["turnover_basis"]
    c2 = eg.certificate_complexity("relative_value", {"peer_symbol": "GBPUSD"}, ds)
    assert c2["n_params"] == 0, "input identity keys are not free parameters"
    c3 = eg.certificate_complexity("evolved", {"expr": ["add", ["neg", "x"], "y"]}, None)
    assert c3["expression_nodes"] == 4 and c3["turnover_per_day"] is None


def test_complexity_turnover_prefers_engine_trades() -> None:
    class _T:
        def __init__(self, t: str) -> None:
            self.entry_time = pd.Timestamp(t, tz="UTC")
    trades = [_T("2025-01-01"), _T("2025-01-01"), _T("2025-01-10")]
    c = eg.certificate_complexity("carry", {}, _daily(), trades)
    assert c["turnover_per_day"] == pytest.approx(3 / 10)
    assert "engine trades" in c["turnover_basis"]


# ----------------------------------------------------------------------------------- V15
def test_certificate_baselines_scores_against_the_symbols_own_bars() -> None:
    frame = _bars(days=400)
    ds = pd.Series(0.2, index=pd.bdate_range("2024-02-01", "2024-12-01")[::3])
    b = eg.certificate_baselines("XAUUSD", ds, frame, None, seed=1)
    assert b["status"] == "MEASURED" and b["n_days"] >= 30
    bh = b["buy_and_hold"]
    assert {"strategy_sharpe", "buy_hold_sharpe", "beats_buy_hold_sharpe"} <= set(bh)
    assert bh["beats_buy_hold_sharpe"] == (bh["strategy_sharpe"] > bh["buy_hold_sharpe"])
    assert "excess_over" not in json.dumps(b), "total-return excess is incommensurable with R"
    m = b["monkey"]
    assert m["n_baselines"] >= 200 and 0.0 <= m["beat_rate"] <= 1.0
    assert "active-day indicator" in m["positions_basis"]
    assert set(b["exposure_timing"]) == {"exposure_share", "timing_share", "time_in_market"}
    json.dumps(b, allow_nan=False)   # never a bare NaN token on a certificate
    assert eg.certificate_baselines("XAUUSD", ds, None)["status"] == "UNMEASURED"
    empty = pd.Series(dtype=float)
    assert eg.certificate_baselines("XAUUSD", empty, frame)["status"] == "UNMEASURED"


# ------------------------------------------------------------------------------------ V5
def test_replay2_agreement_measures_the_second_engine_on_plain_signals() -> None:
    """Hand-built signals inside replay2's stated contract (next-open fill, intrabar stop and
    target, TTL, no trigger/bank/trail/pyramid): the two engines must agree, and the record
    must say so with the numbers the certificate carries."""
    from mt5desk.engine import Costs, Signal, run_backtest
    d = _bars(days=400)
    sig = []
    for i in range(100, len(d) - 100, 120):
        px = float(d["close"].iloc[i])
        sig.append(Signal(time=d.index[i], side=1 if i % 240 else -1, stop=px * 0.99,
                          target=px * 1.015, ttl_bars=24, tag="t", trigger=None, wait_bars=1))
    assert len(sig) >= 20
    costs = Costs(spread_per_lot=0.0, commission_per_lot=0.0, contract_oz=100.0)
    ctx = {"ok": True, "df": d, "sigs": sig, "costs": costs,
           "trades": list(run_backtest(d, sig, costs).trades)}
    a = eg.replay2_agreement(ctx)
    assert a["status"] == "MEASURED" and a["n_trades_both"] > 0
    assert a["max_abs_r_gap"] is not None and a["max_abs_r_gap"] <= 0.02
    assert a["n_engine"] == a["n_replay"] and a["agree_within_tolerance"]
    assert a["cost_price_units"] == 0.0 and a["n_signals"] == len(sig)


def test_replay2_agreement_is_unmeasured_without_a_rebuilt_cell() -> None:
    a = eg.replay2_agreement({"ok": False, "why": "budget spent"})
    assert a["status"] == "UNMEASURED" and "budget spent" in a["why"]


# ----------------------------------------------------------------------------------- V19
def test_p_forward_success_is_the_funnel_posterior_or_unmeasured(tmp_path) -> None:
    hyp = tmp_path / "desks" / "mt5" / "data" / "hypotheses"
    hyp.mkdir(parents=True)
    (hyp / "external_survivors.json").write_text(
        json.dumps([{"family": "carry"}] * 10 + [{"family": "vol_transition"}] * 5), "utf-8")
    rep = tmp_path / "desks" / "mt5" / "reports"
    (rep / "shadow").mkdir(parents=True)
    (rep / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps(
        {"survivors": {"external.a": {"shadow_spec": {"family": "carry"}}}}), "utf-8")
    (rep / "shadow" / "external_shadow_state.json").write_text(json.dumps({"sleeves": {
        "k1": {"identity": {"family": "carry"}, "status": "PROMOTION CANDIDATE"},
        "k2": {"identity": {"family": "carry"}, "status": "RUNNING"}}}), "utf-8")
    priors = eg.forward_success_priors(tmp_path)
    p = eg.p_forward_success("carry", priors)
    assert p["status"] == "RECORDED_PREDICTION" and p["stage"] == "forward_survived"
    a, b = p["beta"]                       # recorded to 4 dp; `p` is taken from the exact pair
    assert p["p"] == pytest.approx(a / (a + b), abs=1e-3)
    assert p["denominator_known"] is True
    assert p["counts"]["forward_enrolled"] == 2 and p["counts"]["forward_survived"] == 1
    assert p["p_certified_stage"]["p"] is not None and "not a gate" in p["basis"]
    u = eg.p_forward_success("asia_momentum", priors)
    assert u["status"] == "UNMEASURED" and "no funnel record" in u["why"]
    assert eg.p_forward_success("carry", {"_error": "boom"})["status"] == "UNMEASURED"


# ------------------------------------------------------------------------------------ A8
def test_release_stamp_reads_the_sealed_record_first(monkeypatch, tmp_path) -> None:
    from libs.ops import release
    rec = tmp_path / "RELEASE.json"
    rec.write_text(json.dumps({"release_id": "abc123def456", "canon_sha256": "f" * 64,
                               "code_sha": "c" * 40, "sealed": True}), "utf-8")
    monkeypatch.setattr(release, "RELEASE", rec)
    s = eg.release_stamp()
    assert s["release_id"] == "abc123def456" and s["canon_sha256"] == "f" * 64
    assert s["release_basis"]["sealed"] is True and "load" in s["release_basis"]["source"]
    assert s["release_basis"]["code_sha"] == "c" * 40 and s["release_basis"]["why"] is None


def test_release_stamp_falls_back_to_the_tree_then_to_none_with_why(monkeypatch,
                                                                     tmp_path) -> None:
    from libs.ops import release
    monkeypatch.setattr(release, "RELEASE", tmp_path / "absent.json")
    monkeypatch.setattr(release, "build", lambda write=True, **_k: {
        "release_id": "wt0000000000", "canon_sha256": None, "sealed": False, "live_sha": "x"})
    s = eg.release_stamp()
    assert s["release_id"] == "wt0000000000" and s["canon_sha256"] is None
    assert "working tree" in s["release_basis"]["source"]
    assert s["release_basis"]["sealed"] is False

    def _boom(*_a, **_k):
        raise RuntimeError("no git here")
    monkeypatch.setattr(release, "load", _boom)
    s = eg.release_stamp()
    assert s["release_id"] is None and s["canon_sha256"] is None
    assert "no git here" in s["release_basis"]["why"]


# -------------------------------------------------------------- the certificate block itself
def _cell_and_verdict() -> tuple[dict, dict]:
    cell = {"sym": "EURUSD", "family": "carry", "params": {"input_symbol": "3M"},
            "timeframe": "H1", "_cached_ds": _daily(n=120)}
    v = {"cell": eg.cell_id(cell), "sym": "EURUSD", "family": "carry", "passed": True,
         "stages": {"x": {"passed": True}}}
    return cell, v


def test_annotations_never_break_a_certificate_and_record_unmeasured_on_failure(
        monkeypatch) -> None:
    monkeypatch.setattr(eg, "build_cell", lambda *_a, **_k: None)   # the rebuild fails
    monkeypatch.setattr(eg, "_bars_for", lambda *_a, **_k: None)    # and there are no bars
    cell, v = _cell_and_verdict()
    release = {"release_id": None, "canon_sha256": None,
               "release_basis": {"source": None, "why": "none"}}
    out = eg.certificate_annotations(v, cell, {}, priors={"_error": "census absent"},
                                     release=release, deadline=time.time() + 60)
    assert {"release_id", "canon_sha256", "release_basis", "p_forward_success",
            "replay2_agreement", "complexity", "baselines"} <= set(out)
    assert out["replay2_agreement"]["status"] == "UNMEASURED"
    assert "build_cell" in out["replay2_agreement"]["why"]
    assert out["baselines"]["status"] == "UNMEASURED"
    assert out["p_forward_success"]["status"] == "UNMEASURED"
    assert out["complexity"]["status"] == "MEASURED" and out["complexity"]["n_params"] == 0
    assert v["stages"] == {"x": {"passed": True}}, "the verdict is untouched"


def test_annotation_budget_exhaustion_is_recorded_not_skipped(monkeypatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(eg, "build_cell", lambda *_a, **_k: calls.append(1))
    monkeypatch.setattr(eg, "_bars_for", lambda *_a, **_k: None)
    cell, v = _cell_and_verdict()
    out = eg.certificate_annotations(v, cell, {}, priors={}, release={},
                                     deadline=time.time() - 1)
    assert calls == [], "no rebuild once the annotation budget is spent"
    assert "annotation budget" in out["replay2_agreement"]["why"]
    assert out["complexity"]["status"] == "MEASURED"   # series-based annotations still land


def test_an_annotation_that_raises_lands_as_unmeasured_for_that_key_only(monkeypatch) -> None:
    def _kaboom(*_a, **_k):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(eg, "certificate_complexity", _kaboom)
    monkeypatch.setattr(eg, "build_cell", lambda *_a, **_k: None)
    monkeypatch.setattr(eg, "_bars_for", lambda *_a, **_k: None)
    cell, v = _cell_and_verdict()
    out = eg.certificate_annotations(v, cell, {}, priors={}, release={},
                                     deadline=time.time() + 60)
    assert out["complexity"]["status"] == "UNMEASURED" and "kaboom" in out["complexity"]["why"]
    assert out["p_forward_success"]["status"] == "UNMEASURED"   # the others are still recorded
