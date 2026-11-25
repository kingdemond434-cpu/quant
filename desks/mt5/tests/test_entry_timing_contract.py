"""The judge's entry contract: fill at the open of the bar AFTER the signal, never at its close.

Pinned 2026-11-25 after INTRADAY_GAP_1125 named "signal on bar close, filled at that same close in
the judge vs the next tick in shadow" as the most likely cause of the M5 forward gap. The trace
refuted it. Judge and forward clock call the same `mt5desk.engine.run_backtest`, and it fills at
`o[i0 + 1]`. These tests keep it that way, and they test the independent reference fill in
`scripts/entry_timing_probe.py` that the box measurement uses.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pandas as pd
import pytest
from mt5desk.engine import Costs, Signal, run_backtest

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"


def _probe():
    spec = importlib.util.spec_from_file_location(
        "entry_timing_probe", ROOT / "scripts" / "entry_timing_probe.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FREE = Costs(spread_per_lot=0.0, commission_per_lot=0.0, contract_oz=1.0)


def _bars(rows: list[tuple[float, float, float, float]], freq: str = "5min") -> pd.DataFrame:
    idx = pd.date_range("2026-01-05 00:00", periods=len(rows), freq=freq, tz="UTC")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)


def _bounce() -> tuple[pd.DataFrame, Signal]:
    """A bar that closes on its low and a next bar that opens back where the drop began.

    Buying the signal bar's own close (0.90) and closing at the time exit (1.00) is +2R. Buying
    the next bar's open (1.00) closes flat at the same exit. Only a close fill earns the
    bounce.
    """
    df = _bars([(1.00, 1.002, 0.998, 1.00)] * 3
               + [(1.00, 1.00, 0.90, 0.90)]                 # signal bar: closes on its low
               + [(1.00, 1.005, 0.995, 1.00)] * 6)
    sig = Signal(time=df.index[3], side=1, stop=0.85, target=1.01, ttl_bars=3, tag="bounce")
    return df, sig


def test_the_engine_fills_the_next_bars_open_not_the_signal_bars_close() -> None:
    df, sig = _bounce()
    (t,) = run_backtest(df, [sig], FREE).trades
    assert t.entry_time == df.index[4]
    assert t.entry == pytest.approx(1.00)                  # o[t+1], not c[t] = 0.90
    assert t.r_multiple == pytest.approx(0.0, abs=1e-9)    # the bounce is not captured


def test_the_close_fill_counterfactual_can_tell_the_difference() -> None:
    """The leak test can fail: a close fill of the same signal books the bounce."""
    df, sig = _bounce()
    p = _probe()
    close = p.reference_fills(df, [sig], FREE, entry="signal_close")["trades"]
    nxt = p.reference_fills(df, [sig], FREE)["trades"]
    assert close[0][1] == pytest.approx(0.10 / 0.05)
    assert nxt[0][1] == pytest.approx(0.0, abs=1e-9)


def test_a_bar_touching_stop_and_target_is_a_stop_in_engine_and_reference() -> None:
    df = _bars([(1.00, 1.001, 0.999, 1.00)] * 2
               + [(1.00, 1.10, 0.90, 1.00)]                 # entry bar spans both levels
               + [(1.00, 1.001, 0.999, 1.00)] * 3)
    sig = Signal(time=df.index[1], side=1, stop=0.95, target=1.05, ttl_bars=3, tag="tie")
    (t,) = run_backtest(df, [sig], FREE).trades
    assert t.reason == "stop" and t.r_multiple == pytest.approx(-1.0)
    (ref,) = _probe().reference_fills(df, [sig], FREE)["trades"]
    assert ref[2] == "stop" and ref[1] == pytest.approx(-1.0)
    short = Signal(time=df.index[1], side=-1, stop=1.05, target=0.95, ttl_bars=3, tag="tie")
    assert run_backtest(df, [short], FREE).trades[0].reason == "stop"
    assert _probe().reference_fills(df, [short], FREE)["trades"][0][2] == "stop"


def test_the_reference_buys_the_ask_and_short_exits_trigger_on_the_ask() -> None:
    p = _probe()
    spread = Costs(spread_per_lot=0.01, commission_per_lot=0.0, contract_oz=1.0)
    flat = _bars([(1.00, 1.00, 1.00, 1.00)] * 8)
    long_ = Signal(time=flat.index[1], side=1, stop=0.90, target=1.10, ttl_bars=2, tag="l")
    (lt,) = p.reference_fills(flat, [long_], spread)["trades"]
    assert lt[1] == pytest.approx(-0.01 / 0.10)            # bought 1.01, sold 1.00 bid
    # A short whose stop the BID never reaches but the ASK (bid + 0.01) does.
    df = _bars([(1.00, 1.00, 1.00, 1.00)] * 2
               + [(1.00, 1.045, 1.00, 1.00)]                # bid high 1.045, ask high 1.055
               + [(1.00, 1.00, 1.00, 1.00)] * 4)
    short = Signal(time=df.index[1], side=-1, stop=1.05, target=0.90, ttl_bars=3, tag="s")
    (st,) = p.reference_fills(df, [short], spread)["trades"]
    assert st[2] == "stop" and st[1] == pytest.approx(-1.0)
    # The engine agrees since FILL_RULES fill-2026-11-25-a (it used to trigger short exits on the
    # bid, so this read `!= "stop"`): the short is stopped at the ask, for exactly -1R.
    (et,) = run_backtest(df, [short], spread).trades
    assert et.reason == "stop" and et.r_multiple == pytest.approx(st[1])


def test_a_gapped_buy_stop_fills_at_the_open_in_the_reference() -> None:
    """A buy stop the bar opened above fills at that open, 1.03, in the reference and, since
    FILL_RULES fill-2026-11-25-a, in the engine too. The engine used to reclassify it as a limit
    and fill it at the 1.02 trigger, a price the market never offered (this test pinned that)."""
    df = _bars([(1.00, 1.001, 0.999, 1.00)] * 2
               + [(1.03, 1.035, 1.015, 1.03)]               # opens above a 1.02 buy stop
               + [(1.03, 1.031, 1.029, 1.03)] * 4)
    sig = Signal(time=df.index[1], side=1, stop=0.97, target=1.20, ttl_bars=3, tag="brk",
                 trigger=1.02, wait_bars=1)
    eng = run_backtest(df, [sig], FREE).trades[0]
    (ref,) = _probe().reference_fills(df, [sig], FREE)["trades"]
    assert eng.entry == pytest.approx(1.03)                 # the open, not the trigger
    assert ref[1] == pytest.approx(eng.r_multiple)


def test_judge_and_forward_clock_share_one_fill_engine() -> None:
    """Both import `run_backtest` from `mt5desk.engine` and neither defines a fill of its own."""
    imp = re.compile(r"from mt5desk\.engine import [^\n]*\brun_backtest\b")
    for rel in ("scripts/external_gauntlet.py", "research/shadow_forward.py"):
        src = (DESK / rel).read_text(encoding="utf-8")
        assert imp.search(src), rel
        assert not re.search(r"^def (run_backtest|simulate\w*|_?fill_trades?)\(", src, re.M), rel


def test_the_probe_writes_only_its_own_report(tmp_path, monkeypatch) -> None:
    p = _probe()
    assert p.OUT.name == "ENTRY_TIMING_PROBE.json" and p.OUT.parent.name == "reports"
    state = tmp_path / "shadow_state.json"
    state.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(p, "SHADOW_STATE", state)
    out = tmp_path / "out" / "ENTRY_TIMING_PROBE.json"
    assert p.main(["--out", str(out), "--per-tf", "0"]) == 0
    assert sorted(x.name for x in out.parent.iterdir()) == ["ENTRY_TIMING_PROBE.json"]
