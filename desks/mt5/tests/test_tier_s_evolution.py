"""Tier S group "evolution": S05 program evolution, S06 capacity/correlation axes, S31 decision_core
driven by counterexample traces, S33 scheduling/search-policy challengers, S39 failure worlds.

Every test runs on synthetic inputs in tmp_path; none reads or writes the desk's live data.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(ROOT / "scripts"), str(DESK / "research"), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

import tier_s as ts  # noqa: E402
from mt5desk import decision_core as dc  # noqa: E402

from libs.tiers import core_drive, failure_worlds, formal, panel, qd_axes  # noqa: E402
from libs.tiers import program_evolution as pe  # noqa: E402

# ------------------------------------------------------------------------------ S39 failure worlds


def test_desk_protocol_holds_in_the_empty_world() -> None:
    res = failure_worlds.check_world([])
    assert res["verdict"] == "HOLDS" and res["complete"]


def test_toctou_world_breaks_zero_means_no_order_with_every_knob_on() -> None:
    res = failure_worlds.check_world(["recheck_send_race"])
    tr = res["violations"]["ZERO_MEANS_NO_ORDER"]
    assert tr.index("recheck_ok") < tr.index("publish(0)") < tr.index("transmit")
    assert formal.Protocol().recheck_alloc_at_send, "the knob is ON: the world, not the design"


def test_search_reports_only_minimal_worlds() -> None:
    res = failure_worlds.search(("venue_ignores_client_id", "network_duplicate", "deep_crash"),
                                max_size=3)
    dup = [m for m in res["minimal_failing_worlds"] if m["invariant"] == "NO_DUPLICATE_FILL"]
    assert [m["faults"] for m in dup] == [["network_duplicate", "venue_ignores_client_id"]]
    assert res["single_fault"]["venue_ignores_client_id"] is None
    assert res["worlds_searched"] == 7


# -------------------------------------------------------------------- S31 decision_core replays


def test_zero_allocation_trace_is_blocked_by_book_from_allocation() -> None:
    r = core_drive.drive(["init", "decide", "publish(0)", "persist", "send"], dc)
    assert r["verdict"] == "BLOCKED_BY_CORE"
    assert r["blocked_at"]["function"] == "book_from_allocation"


def test_revoked_certificate_trace_is_blocked_by_the_roster() -> None:
    r = core_drive.drive(["init", "revoke_cert", "decide", "persist", "send"], dc)
    assert r["verdict"] == "BLOCKED_BY_CORE"
    assert r["blocked_at"]["function"] == "load_sleeves_verbose"


def test_resend_before_fill_is_a_core_gap_and_after_fill_is_blocked() -> None:
    gap = core_drive.drive(["init", "decide", "send", "crash", "restart", "decide", "send",
                            "fill", "broker_fills_duplicate"], dc)
    assert gap["verdict"] == "CORE_ADMITS"
    probes = [p for st in gap["steps"] for p in st["probes"]]
    assert probes[-1]["function"] == "bar_already_traded" and probes[-1]["blocked"] is False
    ok = core_drive.drive(["init", "decide", "send", "fill", "crash", "restart", "send"], dc)
    assert ok["verdict"] == "BLOCKED_BY_CORE"
    assert ok["blocked_at"]["function"] == "bar_already_traded"


def test_failed_control_is_unmeasured_never_a_block() -> None:
    fake = SimpleNamespace(load_sleeves_verbose=lambda p: ([], []))
    r = core_drive.drive(["init", "revoke_cert", "decide", "send"], fake)
    assert r["verdict"] == "UNMEASURED"


def test_drive_all_collects_gaps_from_ablations_and_worlds() -> None:
    abl = {"runs": {"without_x": {"invariants": {"ZERO_MEANS_NO_ORDER": {
        "verdict": "VIOLATED", "trace": ["init", "decide", "publish(0)", "send"]}}}}}
    worlds = failure_worlds.search(("recheck_send_race",), max_size=1)
    out = core_drive.drive_all(core_drive.counterexamples(abl, worlds), dc)
    assert out["verdicts"]["BLOCKED_BY_CORE"] == 1
    assert out["verdicts"]["CORE_ADMITS"] == 2
    assert {g["function"] for g in out["core_gaps"]} == {"book_from_allocation",
                                                          "load_sleeves_verbose"}


# ------------------------------------------------------------------------------- S06 axes


def _returns(n: int = 600, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    a, b = rng.normal(size=n), rng.normal(size=n)
    idx = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame({"A1": a + 0.1 * rng.normal(size=n), "A2": a + 0.1 * rng.normal(size=n),
                         "B1": b + 0.1 * rng.normal(size=n), "B2": b + 0.1 * rng.normal(size=n),
                         "C": rng.normal(size=n)}, index=idx)


def test_correlation_clusters_separate_co_moving_groups() -> None:
    out = qd_axes.correlation_clusters(_returns())
    lab = out["labels"]
    assert lab["A1"] == lab["A2"] == "cc:A1" and lab["B1"] == lab["B2"] == "cc:B1"
    assert lab["C"] == "cc:C" and out["n_clusters"] == 3


def test_correlation_clusters_unmeasured_on_one_symbol() -> None:
    out = qd_axes.correlation_clusters(_returns()[["A1"]])
    assert out["status"] == "UNMEASURED" and out["labels"] == {}


def test_capacity_bands_prefer_the_capacity_report_then_liquidity() -> None:
    doc = {"rows": [{"symbol": "XAUUSD", "binding_now": True, "headroom_multiple": 2.0},
                    {"symbol": "EURUSD", "binding_now": False, "headroom_multiple": 0.05}]}
    frames = {s: pd.DataFrame({"tick_volume": [v] * 10})
              for s, v in (("XAUUSD", 1), ("A", 10), ("B", 20), ("C", 30))}
    out = qd_axes.capacity_bands(doc, frames)
    assert out["labels"]["XAUUSD"] == "floor_binding"
    assert out["source"]["XAUUSD"] == "capacity_json"
    assert out["labels"]["EURUSD"] == "clear>10x"
    assert out["labels"]["A"] == "liq_low" and out["labels"]["C"] == "liq_high"
    assert qd_axes.capacity_bands(None, {})["status"] == "UNMEASURED"


def _write_universe(d: Path, syms: dict[str, int], n: int = 800) -> None:
    d.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(3)
    base = rng.normal(size=n)
    idx = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC", name="time")
    for s, grp in syms.items():
        r = 0.001 * ((base if grp == 0 else rng.normal(size=n)) + 0.2 * rng.normal(size=n))
        c = 100 * np.exp(np.cumsum(r))
        pd.DataFrame({"open": c, "high": c * 1.001, "low": c * 0.999, "close": c,
                      "tick_volume": rng.integers(10, 1000, n)}, index=idx).to_parquet(
            d / f"{s}_H1.parquet")


def test_load_frames_keeps_timestamps(tmp_path: Path) -> None:
    _write_universe(tmp_path, {"EURUSD": 0, "GBPUSD": 0})
    fr = panel.load_frames(tmp_path)
    assert set(fr) == {"EURUSD", "GBPUSD"}
    assert isinstance(panel.log_returns(fr).index, pd.DatetimeIndex)


def test_organ_qd_carries_capacity_and_cluster_axes(tmp_path: Path, monkeypatch: Any) -> None:
    uni = tmp_path / "universe"
    _write_universe(uni, {"EURUSD": 0, "GBPUSD": 0, "USDJPY": 1})
    surv = {f"h.{s}": {"shadow_spec": {"symbol": s, "family": "session_range_breakout",
                                       "selector": "asia", "params": {"a": 1}},
                       "gates": {"expected_value": {"ev": 0.1}}}
            for s in ("EURUSD", "USDJPY")}
    monkeypatch.setattr(ts, "UNIVERSE", uni)
    monkeypatch.setattr(ts, "INTEL", tmp_path / "intel")
    monkeypatch.setattr(ts, "REPORTS", tmp_path / "reports")
    monkeypatch.setattr(ts, "survivors", lambda: surv)
    monkeypatch.setattr(ts, "shadow_rows", dict)
    monkeypatch.setattr(ts, "_may_hypothesise", lambda s: True)
    out = ts.organ_qd()
    assert "capacity" in out["axes"] and "corr_cluster" in out["axes"]
    assert out["metric"]["cluster_measured_elites"] == 2
    assert out["metric"]["capacity_measured_elites"] == 2
    assert out["corr_clusters"]["n_clusters"] == 2


# ----------------------------------------------------------------------- S05/S33 programs


def test_portfolio_program_is_scored_walk_forward() -> None:
    R = _returns(1500).to_numpy() * 0.001
    s = pe.portfolio_score(pe.INCUMBENT["portfolio"], R, 0, 1000)
    assert s["status"] == "MEASURED" and s["bars"] == 1000 - 240
    assert pe.portfolio_score(pe.INCUMBENT["portfolio"], R[:, :1], 0, 1000)["status"] == \
        "UNMEASURED"


def test_limit_execution_charges_non_fills_and_market_pays_the_spread() -> None:
    n = 400
    o = 100 + np.sin(np.arange(n))           # oscillating: a small limit offset fills often
    ohlc = {"X": {"open": o, "high": o + 1.0, "low": o - 1.0, "close": o}}
    mkt = pe.execution_score(pe.INCUMBENT["execution"], ohlc, 0.0, 1.0)
    assert mkt["shortfall_atr"] == pytest.approx(pe.HALF_SPREAD_ATR)
    lim = pe.execution_score({"order": "limit", "offset_atr": 0.1, "wait_bars": 2,
                              "atr_n": 14}, ohlc, 0.0, 1.0)
    assert lim["fitness"] > mkt["fitness"]


def test_regime_detector_scores_a_vol_switching_series() -> None:
    rng = np.random.default_rng(1)
    vol = np.repeat(rng.choice([0.001, 0.01], size=40), 100)
    c = 100 * np.exp(np.cumsum(rng.normal(size=len(vol)) * vol))
    ohlc = {"X": {"open": c, "high": c, "low": c, "close": c}}
    good = pe.regime_score({"feature": "realized_vol", "window": 24, "n_states": 2}, ohlc,
                           0.7, 1.0)
    assert good["status"] == "MEASURED" and good["fitness"] > 0.3


def _arm_days(n: int = 20) -> dict[str, dict[str, list[int]]]:
    return {f"2026-09-{i + 1:02d}": {"good": [10, 5], "bad": [30, 0]} for i in range(n)}


def test_bandit_beats_the_split_the_desk_spent() -> None:
    days = _arm_days()
    inc = pe.bandit_score(pe.INCUMBENT["scheduler"], days, 0.7, 1.0)
    greedy = pe.bandit_score({"rule": "greedy", "prior": 1.0, "half_life_days": 5.0,
                              "explore_floor": 0.0}, days, 0.7, 1.0)
    assert inc["fitness"] == pytest.approx(5 / 40)
    assert greedy["fitness"] == pytest.approx(0.5)


def test_arm_days_reads_gate_verdicts_and_graph_fates() -> None:
    rows = [{"at": "2026-09-01T00:00", "passed": True, "family": "f"},
            {"at": "2026-09-01T01:00", "passed": False, "family": "f"},
            {"at": "2026-09-01T02:00", "fate": "CERTIFIED", "family": "g"},
            {"at": "2026-09-01T03:00", "fate": "BORN", "family": "g"}]
    days = pe.arm_days(rows, lambda r: r["family"])
    assert days == {"2026-09-01": {"f": [2, 1], "g": [1, 1]}}


def test_run_persists_generations_and_reports_unmeasured() -> None:
    rep, st = pe.run(("scheduler", "regime"), {}, {"scheduler": _arm_days(), "regime": None}, 1)
    assert rep["scheduler"]["status"] == "MEASURED"
    assert rep["scheduler"]["heldout_lift"] is not None
    assert rep["regime"]["status"] == "UNMEASURED"
    _rep2, st2 = pe.run(("scheduler",), st, {"scheduler": _arm_days()}, 2)
    assert st2["scheduler"]["generation"] == 2
    assert len(st2["scheduler"]["heldout_history"]) == 2


def test_red_queen_registers_architecture_challengers(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(ts, "STATE", tmp_path)
    days = _arm_days()
    monkeypatch.setattr(ts, "_program_data", lambda kinds: {"scheduler": days,
                                                            "search_policy": days})
    monkeypatch.setattr(ts, "_real_gauntlet_attack", lambda a, g: {"status": "UNMEASURED"})
    monkeypatch.setattr(ts.red_queen, "generation", lambda *a, **k: {
        "attack_success": 0.1, "best_defender": {"balanced": 0.8}, "challenger": None,
        "next_attackers": [], "elite_attacks": []})
    (tmp_path / "program_evolution.json").write_text(json.dumps({"scheduler": {
        "champion": {"rule": "greedy", "prior": 1.0, "half_life_days": 5.0,
                     "explore_floor": 0.0}}}), "utf-8")
    out = ts.organ_red_queen()
    arch = out["architecture_challengers"]
    assert arch["scheduler"]["beats_incumbent_heldout"] is True
    assert out["metric"]["scheduler_heldout_lift"] > 0
    ch = json.loads((tmp_path / "challengers.json").read_text("utf-8"))["challengers"]
    assert any(c["component"] == "scheduler" for c in ch)


def test_formal_organ_carries_worlds_and_core_drive(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(ts, "REPORTS", tmp_path)
    small = failure_worlds.search
    monkeypatch.setattr(failure_worlds, "search",
                        lambda max_size=3: small(("recheck_send_race", "clock_skew"),
                                                 max_size=1))
    out = ts.organ_formal()
    assert out["metric"]["failure_worlds"] == 3
    assert out["metric"]["traces_driven"] >= 3
    assert out["decision_core_drive"]["verdicts"].get("BLOCKED_BY_CORE", 0) >= 1
