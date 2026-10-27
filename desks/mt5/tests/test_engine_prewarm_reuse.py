"""The judge's pre-warm replays every cell twice on one path; the second arm must be byte-identical.

`mt5desk.engine.run_backtest` keeps the cost-independent half of its last call (`_LegMemo`) and
counts financing nights on integers (`_rollover_nights_ns`). Both are speed only: these tests pin
that every Trade -- every float bit, every timestamp, every refusal -- is what the un-memoised
engine returns, on the 1x -> 3x call pattern the judge uses and on the patterns that must miss.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from mt5desk import engine  # noqa: E402
from mt5desk.engine import Costs, Signal, run_backtest  # noqa: E402

UNIVERSE = DESK / "data" / "universe" / "universe.json"


def _frame(n: int, seed: int, tz: str | None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2019-03-01", periods=n, freq="h", tz=tz)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.003, n)))
    opn = np.r_[close[0], close[:-1]]
    hi = np.maximum(opn, close) * (1 + np.abs(rng.normal(0, 0.002, n)))
    lo = np.minimum(opn, close) * (1 - np.abs(rng.normal(0, 0.002, n)))
    return pd.DataFrame({"open": opn, "high": hi, "low": lo, "close": close,
                         "spread": rng.integers(5, 40, n)}, index=idx)


def _signals(df: pd.DataFrame, seed: int, k: int) -> list[Signal]:
    rng = random.Random(seed)  # noqa: S311 -- deterministic fixture
    out = []
    for _ in range(k):
        i = rng.randrange(1, len(df) - 3)
        px = float(df["close"].iloc[i])
        side = rng.choice((1, -1))
        d = px * rng.uniform(0.002, 0.02)
        kind = rng.randrange(6)
        s = Signal(time=df.index[i], side=side, stop=px - side * d,
                   target=px + side * d * rng.uniform(0.5, 3.0),
                   ttl_bars=rng.choice((4, 12, 48, 200)), tag="t")
        if kind == 1:                                   # resting stop/limit trigger
            s.trigger = px + side * d * rng.uniform(-0.5, 0.5)
            s.wait_bars = rng.choice((1, 4, 12))
        elif kind == 2:                                 # bank + runner trail
            s.bank_frac, s.bank_protect_k, s.runner_trail_k = 0.5, 0.2, 2.0
        elif kind == 3:                                 # stall-tightened trail, no bank
            s.runner_trail_k, s.trail_tighten_k, s.trail_stall_bars = 3.0, 1.0, 3
        elif kind == 4:                                 # pyramid
            s.add_every_r, s.add_max, s.add_frac = 0.5, 3, 0.5
        elif kind == 5:                                 # unexecutable bracket -> refusal
            s.stop = px + side * d
        out.append(s)
    out.sort(key=lambda s: s.time)
    return out


def _costs() -> list[tuple[Costs, Costs]]:
    meta = json.loads(UNIVERSE.read_text("utf-8")) if UNIVERSE.exists() else {}
    pairs = [(Costs(), Costs().stressed(3.0))]
    for sym in ("EURUSD", "GBPMXN", "XAUUSD", "USDJPY", "US500", "EURZAR"):
        if sym in meta:
            pairs.append((Costs.from_symbol(meta[sym]), Costs.from_symbol(meta[sym], mult=3.0)))
    return pairs


def _bits(res) -> list[tuple]:
    rows = []
    for t in res.trades:
        rows.append((t.entry_time, str(t.entry_time.tz), t.exit_time, t.side,
                     float(t.entry).hex(), float(t.exit).hex(), float(t.stop).hex(),
                     float(t.target).hex(), t.bars_held, float(t.r_multiple).hex(),
                     type(t.r_multiple).__name__, t.reason, float(t.units).hex(), t.adds))
    return [res.signal_count, json.dumps(res.geometry_rejections, sort_keys=True, default=str),
            rows]


def _fresh(df, sigs, costs, monkeypatch) -> list:
    monkeypatch.setenv("MT5_ENGINE_LEG_MEMO", "0")
    try:
        return _bits(run_backtest(df, sigs, costs))
    finally:
        monkeypatch.delenv("MT5_ENGINE_LEG_MEMO", raising=False)


@pytest.mark.parametrize("tz", [None, "UTC", "Europe/Athens"])
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_the_second_cost_arm_is_byte_identical_to_a_fresh_walk(tz, seed, monkeypatch):
    df = _frame(3_000, seed, tz)
    sigs = _signals(df, seed, 400)
    for c1, c3 in _costs():
        want1 = _fresh(df, sigs, c1, monkeypatch)
        want3 = _fresh(df, sigs, c3, monkeypatch)
        engine._LEGS.slot = None
        got1 = _bits(run_backtest(df, sigs, c1))            # walks and stores
        assert engine._LEGS.slot is not None and engine._LEGS.slot[1] is sigs
        got3 = _bits(run_backtest(df, sigs, c3))            # prices the stored legs
        got1b = _bits(run_backtest(df, sigs, c1))           # and again, the other way round
        assert got1 == want1
        assert got3 == want3
        assert got1b == want1


def test_the_memo_actually_skips_the_walk(monkeypatch):
    df = _frame(2_000, 9, "UTC")
    sigs = _signals(df, 9, 200)
    engine._LEGS.slot = None
    run_backtest(df, sigs, Costs())
    calls = []
    real = engine.np.searchsorted

    def spy(a, v, *k, **kw):
        calls.append(len(v) if hasattr(v, "__len__") else 1)
        return real(a, v, *k, **kw)
    monkeypatch.setattr(engine.np, "searchsorted", spy)
    run_backtest(df, sigs, Costs(spread_per_lot=48.0))
    assert calls and calls[0] == 0          # no signal located: the loop never ran


def test_a_mutated_signal_or_another_list_or_frame_walks_again(monkeypatch):
    df = _frame(2_000, 4, None)
    sigs = _signals(df, 4, 200)
    c = Costs()
    engine._LEGS.slot = None
    run_backtest(df, sigs, c)
    sigs[5].stop = sigs[5].stop * 0.99                  # mutated in place: same list object
    assert engine._LEGS.lookup(df, sigs, None) is None
    assert _bits(run_backtest(df, sigs, c)) == _fresh(df, sigs, c, monkeypatch)
    twin = list(sigs)                                   # equal content, another list
    assert engine._LEGS.lookup(df, twin, None) is None
    df2 = df.copy()
    assert engine._LEGS.lookup(df2, sigs, None) is None
    assert engine._LEGS.lookup(df, sigs, 10) is None    # another max_hold_bars
    sigs.append(sigs[-1])                               # grown in place
    assert engine._LEGS.lookup(df, sigs, None) is None


def test_off_switch_never_stores(monkeypatch):
    monkeypatch.setenv("MT5_ENGINE_LEG_MEMO", "0")
    engine._LEGS.slot = None
    df = _frame(500, 5, None)
    run_backtest(df, _signals(df, 5, 30), Costs())
    assert engine._LEGS.slot is None


def test_no_signals_and_no_trades_are_fine():
    df = _frame(300, 6, "UTC")
    engine._LEGS.slot = None
    assert run_backtest(df, [], Costs()).trades == []
    assert run_backtest(df, [], Costs(spread_per_lot=1.0)).trades == []


def _ts_pairs(n: int, seed: int):
    rng = random.Random(seed)  # noqa: S311 -- deterministic fixture
    zones = [None, "UTC", "Europe/Athens", "America/New_York", "Asia/Tokyo"]
    for _ in range(n):
        base = rng.randrange(-5 * 365 * 86_400, 60 * 365 * 86_400)
        a = pd.Timestamp(base, unit="s") + pd.Timedelta(microseconds=rng.randrange(10**6))
        b = a + pd.Timedelta(seconds=rng.randrange(-3 * 86_400, 40 * 86_400))
        za, zb = rng.choice(zones), rng.choice(zones)
        yield ((a.tz_localize("UTC").tz_convert(za) if za else a),
               (b.tz_localize("UTC").tz_convert(zb) if zb else b))
    # the edges: equal, the rollover instant itself, a Wednesday triple, DST changes
    r = pd.Timestamp("2026-10-21 21:00")
    for a, b in [(r, r), (r - pd.Timedelta(1, "ns"), r), (r, r + pd.Timedelta(1, "ns")),
                 (r - pd.Timedelta(days=9), r + pd.Timedelta(days=9)),
                 (pd.Timestamp("2026-03-29 00:30", tz="Europe/Athens"),
                  pd.Timestamp("2026-03-30 23:30", tz="Europe/Athens")),
                 (pd.Timestamp("2026-10-25 02:30", tz="Europe/Athens", ambiguous=True),
                  pd.Timestamp("2026-11-02 05:00", tz="Europe/Athens")),
                 (pd.Timestamp("1969-12-31 20:59"), pd.Timestamp("1970-01-08 21:00"))]:
        yield a, b


def test_integer_nights_equal_rollovers_between_everywhere():
    n = 0
    for a, b in _ts_pairs(40_000, 11):
        want = engine.rollovers_between(a, b)
        got = engine._rollover_nights_ns(a.value, b.value)
        assert type(got) is float
        assert got == want, (a, b, got, want)
        n += 1
    assert n > 40_000
