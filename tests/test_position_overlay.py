"""position_overlay: the exit-overlay family -- each policy on a hand-built path, the
never-extends / never-uses-the-exit-bar rule, cost delta, purged walk-forward, the trial charge
(once per cell, ever) and the end-to-end report with a planted edge and with no ledgers."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import position_overlay as po  # noqa: E402

T0 = datetime(2026, 1, 5, tzinfo=UTC)


def _bars(closes: list[float], *, spread: list[float] | None = None, point: float = 1e-5,
          rng: float = 0.0002) -> po.Bars:
    c = np.asarray(closes, dtype=float)
    o = np.concatenate([[c[0]], c[:-1]])
    t = np.array([int((T0 + timedelta(hours=i)).timestamp()) for i in range(len(c))])
    sp = np.asarray(spread if spread is not None else [10.0] * len(c), dtype=float)
    return po.Bars(t=t, o=o, h=np.maximum(o, c) + rng, lo=np.minimum(o, c) - rng, c=c,
                   spread=sp, point=point)


def _trade(i0: int, i1: int, *, entry: float, exit_: float, side: int = 1,
           risk: float = 0.001) -> po.Trade:
    r = side * (exit_ - entry) / risk
    return po.Trade("s", "EURUSD", T0 + timedelta(hours=i0), T0 + timedelta(hours=i1), side,
                    entry, exit_, r, False, risk)


def test_time_stop_exits_at_close_of_kth_bar_inside_the_trade() -> None:
    b = _bars([1.0 + 0.0001 * i for i in range(30)])
    tr = _trade(2, 20, entry=1.0002, exit_=1.0020)
    px, i, frac = po.pol_time_stop(b, tr, 3)  # type: ignore[misc]
    assert (i, frac) == (4, 1.0) and px == b.c[4]
    assert po.pol_time_stop(b, tr, 50) is None          # never extends past the baseline


def test_window_never_uses_the_bar_holding_the_baseline_exit() -> None:
    b = _bars([1.0] * 30)
    tr = _trade(2, 5, entry=1.0, exit_=1.0)
    assert list(po._window(b, tr)) == [2, 3, 4]


def test_breakeven_arms_at_close_and_fills_at_entry_next_bars() -> None:
    path = [1.0, 1.0, 1.0012, 1.0015, 1.0005, 0.9990, 0.9980, 0.9970]
    b = _bars(path + [0.997] * 5)
    tr = _trade(1, 10, entry=1.0, exit_=0.9990)          # baseline lost 1R
    px, i, _ = po.pol_breakeven(b, tr, 1.0)  # type: ignore[misc]
    assert px == 1.0 and i == 5
    costs = po.CostModel(None)
    assert po.overlay_r(tr, (px, i, 1.0), b, costs) > tr.r


def test_atr_trail_never_loosens_and_partial_closes_half() -> None:
    up = [1.0 + 0.0003 * i for i in range(30)] + [1.0087 - 0.0005 * i for i in range(10)]
    b = _bars(up)
    tr = _trade(16, 39, entry=b.c[16], exit_=b.c[38] - 0.002)
    ex = po.pol_atr_trail(b, tr, 2.0)
    assert ex is not None and ex[1] > 29
    pt = po.pol_partial(b, tr, 1.0)
    assert pt is not None and pt[2] == 0.5


def test_adverse_spread_and_regime_exit() -> None:
    sp = [10.0] * 60 + [50.0] + [10.0] * 9
    b = _bars([1.0] * 70, spread=sp)
    tr = _trade(40, 69, entry=1.0, exit_=1.0)
    ex = po.pol_adverse_spread(b, tr, 3.0)
    assert ex is not None and ex[1] == 60
    z = {(T0 + timedelta(days=1)).date().isoformat(): -2.5}
    tr2 = _trade(1, 60, entry=1.0, exit_=1.0)
    ex2 = po.pol_regime_exit(b, tr2, 2.0, z)
    assert ex2 is not None and datetime.fromtimestamp(int(b.t[ex2[1]]), tz=UTC).date() \
        == (T0 + timedelta(days=2)).date()
    assert po.pol_regime_exit(b, tr2, 2.0, {}) is None


def test_cost_delta_charges_the_overlay_exit_hour() -> None:
    b = _bars([1.0] * 10, spread=[100.0] * 10)
    tr = _trade(0, 9, entry=1.0, exit_=1.0)
    c = po.CostModel(None)
    r = po.overlay_r(tr, (1.0, 3, 1.0), b, c)
    assert r == 0.0 and c.basis == {"bar_spread"}     # same spread both sides -> no delta


def test_walk_forward_is_purged_and_needs_min_train() -> None:
    ts = [_trade(30 * i, 30 * i + 2, entry=1.0, exit_=1.0) for i in range(40)]
    lifts = {1.0: [0.1] * 40, 2.0: [-0.1] * 40}
    d, chosen, _ = po.walk_forward(ts, lifts)
    assert chosen and set(chosen) == {1.0} and all(x == 0.1 for x in d)
    assert len(d) < 40 - po.MIN_TRAIN + 1                # embargo drops near neighbours


def test_charge_once_per_cell_ever(tmp_path: Path) -> None:
    ch, tl = tmp_path / "c.json", tmp_path / "t.jsonl"
    assert po.charge(["a", "b"], charged=ch, trials=tl) == (2, 2)
    assert po.charge(["a", "b", "c"], charged=ch, trials=tl) == (1, 3)
    rows = [json.loads(x) for x in tl.read_text().splitlines()]
    assert sum(r["tests_run"] for r in rows) == 3
    assert rows[0]["by_family"] == {"position_overlay": 2}


def test_run_without_ledgers_is_unmeasured(tmp_path: Path) -> None:
    doc = po.run(tmp_path / "shadow", tmp_path / "out.json", universe_dir=tmp_path,
                 sleeves=tmp_path / "none.json", charged=tmp_path / "c.json",
                 trials=tmp_path / "t.jsonl", surface={}, load_frame=False)
    assert doc["status"] == po.UNMEASURED and doc["survivors"] == [] and doc["n_trades"] == 0


def test_run_end_to_end_finds_a_planted_breakeven_edge(tmp_path: Path) -> None:
    """Every trade runs to +1.5R, then collapses to -1R by its baseline exit: breakeven at +1R
    must lift every trade, survive the walk-forward and clear the DSR bar."""
    rng = np.random.default_rng(7)
    n_tr, span = 80, 12
    closes: list[float] = []
    rows = []
    risk = 0.001
    for k in range(n_tr):
        base = 1.0 + float(rng.normal(0, 0.0005))
        leg = ([base] * 3 + [base + risk * x for x in (0.4, 0.9, 1.3, 1.5, 1.1, 0.4)]
               + [base - risk * 0.6, base - risk, base - risk])
        i0 = len(closes)
        closes += leg
        rows.append({"entry_time": str(T0 + timedelta(hours=i0 + 2)),
                     "exit_time": str(T0 + timedelta(hours=i0 + span - 1)), "side": 1,
                     "entry": base, "exit": base - risk,
                     "r_multiple": -1.0 + float(rng.normal(0, 0.01)),
                     "phase": "forward" if k > 50 else "historical"})
        closes += [base] * 30                             # gap > embargo between trades
    idx = pd.DatetimeIndex([T0 + timedelta(hours=i) for i in range(len(closes))], name="time")
    c = np.asarray(closes)
    o = np.concatenate([[c[0]], c[:-1]])
    pd.DataFrame({"open": o, "high": np.maximum(o, c) + 1e-5, "low": np.minimum(o, c) - 1e-5,
                  "close": c, "spread": 5.0}, index=idx).to_parquet(tmp_path / "EURUSD_H1.parquet")
    (tmp_path / "universe.json").write_text(json.dumps({"EURUSD": {"tick_size": 1e-5}}))
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    (shadow / "ledger_EURUSD_test.json").write_text(json.dumps(rows))
    (tmp_path / "sleeves.json").write_text(json.dumps(
        {"sleeves": [{"name": "EURUSD_test", "symbol": "EURUSD", "status": "LIVE"}]}))
    doc = po.run(shadow, tmp_path / "out.json", universe_dir=tmp_path,
                 sleeves=tmp_path / "sleeves.json", charged=tmp_path / "c.json",
                 trials=tmp_path / "t.jsonl", surface={}, load_frame=False)
    pol = doc["sleeves"]["EURUSD_test"]["policies"]
    assert pol["regime_exit"]["status"] == po.UNMEASURED
    assert pol["breakeven"]["survivor"] is True
    assert pol["breakeven"]["oos_lift_r_per_trade"] > 0.5
    assert any(s["policy"] == "breakeven" for s in doc["survivors"])
    assert doc["trials"]["newly_charged"] == sum(len(v) for v in po.GRID.values())
    again = po.run(shadow, None, universe_dir=tmp_path, sleeves=tmp_path / "sleeves.json",
                   charged=tmp_path / "c.json", trials=tmp_path / "t.jsonl", surface={},
                   load_frame=False)
    assert again["trials"]["newly_charged"] == 0


def _ledger_row(h: int) -> dict:
    return {"entry_time": str(T0 + timedelta(hours=h)),
            "exit_time": str(T0 + timedelta(hours=h + 3)),
            "side": 1, "entry": 1.0, "exit": 1.001, "r_multiple": 1.0, "phase": "forward"}


def test_registry_names_join_to_clock_ledger_stems(tmp_path: Path) -> None:
    """Real-style registry names never equal the ledger stems the clocks write; the join is on
    identity (symbol + window / family + selector), and archives / .pre_ snapshots are skipped."""
    shadow = tmp_path / "shadow"
    (shadow / "archived_runtime_windows").mkdir(parents=True)
    rows = json.dumps([_ledger_row(0), _ledger_row(10)])
    for name in ("ledger_XAUUSD_asia.json", "ledger_AUDCHF_overnight_gap_decay_asia.json",
                 "ledger_XAUUSD_asia.pre_20260901.json",
                 "archived_runtime_windows/ledger_XAUUSD_london_am.json",
                 "ledger_EURUSD_orphan.json"):
        (shadow / name).write_text(rows)
    (tmp_path / "sleeves.json").write_text(json.dumps({"sleeves": [
        {"name": "gold_asia_v2", "symbol": "XAUUSD", "window": "asia", "status": "STANDBY",
         "canonical_identity": "UNIDENTIFIABLE"},
        {"name": "gold_london_am_v2", "symbol": "XAUUSD", "window": "london_am",
         "status": "STANDBY"},
        {"name": "audchf_overnight_gap_decay_asia_p_44136fa355b3678a_principal_20261007",
         "symbol": "AUDCHF", "family": "overnight_gap_decay", "selector": "asia",
         "canonical_identity": "audchf|overnight_gap_decay|asia", "status": "LIVE"},
        {"name": "xauusd_session_range_breakout_asia_5_wb_12", "symbol": "XAUUSD",
         "family": "session_range_breakout", "selector": "asia", "status": "LIVE",
         "canonical_identity": "xauusd|session_range_breakout|asia"}]}))
    reg = po.certified_sleeves(tmp_path / "sleeves.json")
    assert "XAUUSD_asia" in po.ledger_stems(reg["xauusd_session_range_breakout_asia_5_wb_12"])
    got = po.load_trades(shadow, reg)
    assert sorted(got) == ["AUDCHF_overnight_gap_decay_asia", "XAUUSD_asia"]
    assert all(len(v) == 2 for v in got.values())
    assert got["AUDCHF_overnight_gap_decay_asia"][0].symbol == "AUDCHF"


def test_survivor_bar_is_the_fixed_tier_s_n5() -> None:
    d = list(np.random.default_rng(3).normal(0.3, 1.0, 60))
    v = po._dsr(d, 20)
    assert v["n_trials"] == 5 and v["n_forward"] == 20 and v["n_historical"] == 40


def test_fill_risk_median_is_past_only() -> None:
    a = po.Trade("s", "EURUSD", T0, T0 + timedelta(hours=1), 1, 1.0, 1.0, 0.0, False)
    b = po.Trade("s", "EURUSD", T0 + timedelta(hours=2), T0 + timedelta(hours=3), 1,
                 1.0, 1.002, 1.0, False)
    po._fill_risk([a, b])
    assert a.risk == 0.0 and abs(b.risk - 0.002) < 1e-12
