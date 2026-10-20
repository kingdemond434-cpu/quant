"""rebalance_interval: forward-only, per-key, cost-measured or UNMEASURED, report-only."""
from __future__ import annotations

import json
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import rebalance_interval as RI  # noqa: E402

NOW = datetime(2026, 10, 20, tzinfo=UTC)
FS = NOW - timedelta(days=30)


def _ledger(seed: int, start: datetime, n_days: int = 30, pre: int = 0) -> list[dict[str, Any]]:
    rng = random.Random(seed)  # noqa: S311 - fixture noise
    rows = [{"entry_time": (start - timedelta(days=d + 1)).isoformat(), "r_multiple": 50.0}
            for d in range(pre)]                     # pre-forward rows: must never be read
    for h in range(0, n_days * 24, 6):
        rows.append({"entry_time": (start + timedelta(hours=h)).isoformat(),
                     "exit_time": (start + timedelta(hours=h + 2)).isoformat(),
                     "r_multiple": rng.gauss(0.05, 2.0)})
    return rows


def _world(tmp: Path, *, markout_syms=("XAUUSD", "EURUSD"), surface_syms=("XAUUSD", "EURUSD"),
           shared: bool = False, forward_start: bool = True, pre: int = 0,
           cost_age_h: float = 1.0, slip_r: float = -0.05, fx_days: int = 30) -> dict[str, Path]:
    sd = tmp / "shadow"
    sd.mkdir()
    sleeves = [{"name": "gold_a", "symbol": "XAUUSD", "status": "LIVE", "risk_frac": 0.01},
               {"name": "fx_b", "symbol": "EURUSD", "status": "LIVE", "risk_frac": 0.01},
               {"name": "old", "symbol": "EURUSD", "status": "RETIRED", "risk_frac": 0.0}]
    if forward_start:
        for s in sleeves:
            s["forward_start"] = FS.isoformat()
    if shared:
        sleeves.append({"name": "gold_a#rr=2", "symbol": "XAUUSD", "status": "STANDBY"})
    (tmp / "sleeves.json").write_text(json.dumps({"sleeves": sleeves}))
    (sd / "ledger_gold_a.json").write_text(json.dumps(_ledger(1, FS, pre=pre)))
    (sd / "ledger_fx_b.json").write_text(json.dumps(_ledger(2, FS, n_days=fx_days, pre=pre)))
    stamp = (NOW - timedelta(hours=cost_age_h)).isoformat()
    blk = {"clean": {"r": {"mean": slip_r}, "pts": {"mean": 2.0}}, "n_clean": 40}
    (tmp / "markout.json").write_text(json.dumps(
        {"at": stamp, "slip": {"by_symbol": dict.fromkeys(markout_syms, blk)}}))
    (tmp / "surface.json").write_text(json.dumps(
        {"built_at": stamp,
         "symbols": {s: {"pooled_median_spread_pts": 10.0} for s in surface_syms}}))
    return {"shadow_dir": sd, "sleeves_path": tmp / "sleeves.json",
            "markout_path": tmp / "markout.json", "surface_path": tmp / "surface.json"}


def test_measured_book_chooses_highest_net_gain(tmp_path: Path) -> None:
    doc = RI.build(NOW, **_world(tmp_path))
    assert doc["status"] == RI.MEASURED and doc["report_only"] is True
    assert "ASSUMPTION" in doc["assumptions"]["risk_unit_is"]
    names = [c["interval"] for c in doc["candidates"]]
    assert names == ["every_pass", "daily", "every_2_days", "weekly", "drift_10pct",
                     "drift_20pct"]
    best = max(doc["candidates"], key=lambda c: c["net_gain_elogw_per_day"])
    if best["net_gain_elogw_per_day"] <= 0:
        assert doc["chosen"] == RI.HOLD and "hold stands" in doc["why"]
    elif doc["p_beats_runner_up"] >= RI.WIN_PROB:
        assert doc["chosen"] == best["interval"]
    else:
        assert doc["chosen"] is None and doc["verdict"] == "no_clear_winner"
    for c in doc["candidates"]:
        assert abs(c["gross_gain_elogw_per_day"] - c["cost_elogw_per_day"]
                   - c["net_gain_elogw_per_day"]) < 1e-12
        assert c["cost_elogw_per_day"] >= 0.0
    # spread in R = 10 pts * |0.05/2| / 2 ; slip 0.05
    assert abs(doc["symbols"]["XAUUSD"]["cost_r"] - (0.05 + 0.125)) < 1e-9


def test_cost_unmeasured_symbol_is_unmeasured(tmp_path: Path) -> None:
    doc = RI.build(NOW, **_world(tmp_path, surface_syms=("XAUUSD",)))
    assert doc["symbols"]["EURUSD"]["status"] == RI.UNMEASURED
    fx = next(s for s in doc["sleeves"] if s["symbol"] == "EURUSD")
    assert fx["status"] == RI.UNMEASURED and "cost UNMEASURED" in fx["why"]
    assert doc["status"] == RI.UNMEASURED and doc["chosen"] is None


def test_missing_markout_is_unmeasured_not_zero(tmp_path: Path) -> None:
    doc = RI.build(NOW, **_world(tmp_path, markout_syms=()))
    assert all(v["status"] == RI.UNMEASURED for v in doc["symbols"].values())
    assert doc["status"] == RI.UNMEASURED


def test_shared_ledger_is_unmeasured(tmp_path: Path) -> None:
    doc = RI.build(NOW, **_world(tmp_path, shared=True))
    gold = next(s for s in doc["sleeves"] if s["sleeve"] == "gold_a")
    assert gold["status"] == RI.UNMEASURED and "SHARED" in gold["why"]


def test_no_forward_start_is_unmeasured(tmp_path: Path) -> None:
    doc = RI.build(NOW, **_world(tmp_path, forward_start=False))
    assert all(s["status"] == RI.UNMEASURED for s in doc["sleeves"])


def test_pre_forward_rows_are_never_read(tmp_path: Path) -> None:
    a_dir = tmp_path / "a"
    a_dir.mkdir()
    a = RI.build(NOW, **_world(a_dir))
    b_dir = tmp_path / "b"
    b_dir.mkdir()
    b = RI.build(NOW, **_world(b_dir, pre=20))
    assert a["candidates"] == b["candidates"]
    assert a["sleeves"][0]["n_forward"] == b["sleeves"][0]["n_forward"]


def test_rebalancing_harvests_pumping_without_cost() -> None:
    # Two anti-correlated sleeves that each go nowhere: hold drifts, constant mix pumps.
    start = NOW - timedelta(days=20)
    a, b = [], []
    for h in range(0, 20 * 24, 1):
        x = 30.0 if (h // 1) % 2 == 0 else -27.0
        a.append((start + timedelta(hours=h), x))
        b.append((start + timedelta(hours=h), -x))
    res = RI.evaluate({"a": a, "b": b}, {"a": 1.0, "b": 1.0}, {"a": 0.0, "b": 0.0}, start, NOW)
    every = next(c for c in res["candidates"] if c["interval"] == "every_pass")
    assert every["gross_gain_elogw_per_day"] >= 0.0
    assert every["cost_elogw_per_day"] == 0.0


def test_wired_hourly_layer_graph_and_dashboard() -> None:
    root = DESK.parents[1]
    hc = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_producer("rebalance_interval", "research/rebalance_interval.py")' in hc
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["rebalance_interval"] == "timing"
    from libs.ops import capability_graph as CG
    node = next(n for n in CG.NODES if n.name == "rebalance_interval")
    assert "desks/mt5/reports/REBALANCE_INTERVAL.json" in node.writes
    dash = (DESK / "research" / "desk_dashboard_state.py").read_text("utf-8")
    assert 'Src("desks/mt5/reports/REBALANCE_INTERVAL.json"' in dash
    # report-only: nothing that sizes reads it
    for organ in ("desks/mt5/research/pf_allocator.py", "desks/mt5/mt5desk/decision_core.py",
                  "desks/mt5/research/promoter.py"):
        p = root / organ
        assert p.exists(), f"{organ} moved: the report-only fence must follow it"
        text = p.read_text("utf-8", errors="replace")
        assert "REBALANCE_INTERVAL" not in text and "rebalance_interval" not in text


def test_stale_cost_is_unmeasured(tmp_path: Path) -> None:
    doc = RI.build(NOW, **_world(tmp_path, cost_age_h=100.0))
    assert doc["cost_freshness"]["status"] == RI.UNMEASURED
    assert doc["status"] == RI.UNMEASURED


def test_nonpositive_or_nonfinite_cost_is_unmeasured() -> None:
    sur = {"symbols": {"X": {"pooled_median_spread_pts": 10.0}}}
    for r in (0.0, float("nan"), float("inf")):
        m = {"slip": {"by_symbol": {"X": {"clean": {"r": {"mean": r}, "pts": {"mean": 2.0}}}}}}
        assert RI.symbol_cost("X", m, sur)["status"] == RI.UNMEASURED
    m = {"slip": {"by_symbol": {"X": {"clean": {"r": {"mean": -0.05}, "pts": {"mean": 2.0}}}}}}
    for sp in (0.0, -3.0, float("nan")):
        bad = {"symbols": {"X": {"pooled_median_spread_pts": sp}}}
        assert RI.symbol_cost("X", m, bad)["status"] == RI.UNMEASURED


def test_silent_ledger_is_unmeasured_and_book_partial(tmp_path: Path) -> None:
    w = _world(tmp_path, fx_days=5)
    doc = RI.build(NOW, **w)
    fx = next(s for s in doc["sleeves"] if s["sleeve"] == "fx_b")
    assert fx["status"] == RI.UNMEASURED and "silent" in fx["why"]
    assert doc["status"] == RI.UNMEASURED      # one measured sleeve left


def test_partial_when_some_sleeves_unmeasured(tmp_path: Path) -> None:
    w = _world(tmp_path)
    doc_s = json.loads(w["sleeves_path"].read_text())
    doc_s["sleeves"].append({"name": "c_nofs", "symbol": "XAUUSD", "status": "LIVE",
                             "risk_frac": 0.01})
    doc_s["sleeves"].append({"name": "d", "symbol": "EURUSD", "status": "LIVE",
                             "risk_frac": 0.01, "forward_start": FS.isoformat()})
    w["sleeves_path"].write_text(json.dumps(doc_s))
    (w["shadow_dir"] / "ledger_d.json").write_text(json.dumps(_ledger(3, FS)))
    doc = RI.build(NOW, **w)
    assert doc["status"] == RI.PARTIAL and "3 of 4" in doc["why"]


def test_trade_is_booked_at_exit_not_entry() -> None:
    start = NOW - timedelta(days=10)
    rows = [{"entry_time": (start + timedelta(hours=1)).isoformat(),
             "exit_time": (start + timedelta(hours=30)).isoformat(), "r_multiple": 1.0},
            {"entry_time": (start + timedelta(hours=2)).isoformat(), "r_multiple": 9.0}]
    tr, no_exit = RI.forward_trades(rows, start)
    assert no_exit == 1 and tr == [(start + timedelta(hours=30), 1.0)]
    grid = RI.hourly_returns({"a": tr}, start, NOW)
    assert grid[30] == {"a": RI.RISK_UNIT} and grid[1] == {}


def test_hold_chosen_when_nothing_beats_it() -> None:
    start = NOW - timedelta(days=10)
    a = [(start + timedelta(hours=h), 0.1) for h in range(0, 240, 3)]
    res = RI.evaluate({"a": a, "b": list(a)}, {"a": 1.0, "b": 1.0}, {"a": 5.0, "b": 5.0},
                      start, NOW)
    assert res["chosen"] == RI.HOLD and "hold stands" in res["why"]
