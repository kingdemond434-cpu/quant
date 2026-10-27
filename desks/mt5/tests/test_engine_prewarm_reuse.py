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
from dataclasses import replace
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
    # The hour-of-entry spread table (judge image companions): its spread is read off the leg's
    # own fill/exit bar, so it must price identically from a memoised leg.
    if "spread_per_lot_by_hour" in getattr(Costs, "__dataclass_fields__", {}):
        tab = tuple(10.0 + (h * 7) % 23 for h in range(168))
        hourly = replace(Costs.from_symbol(meta.get("EURZAR", {})), spread_per_lot_by_hour=tab)
        pairs.append((hourly, hourly.stressed(3.0)))
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


def _walked(df) -> tuple:
    idx_ns = np.asarray(pd.DatetimeIndex(df.index).as_unit("ns").asi8, dtype="int64")
    return (str(getattr(df.index, "tz", None)), df["open"].to_numpy(), df["high"].to_numpy(),
            df["low"].to_numpy(), idx_ns)


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
    assert engine._LEGS.lookup(df, sigs, None, _walked(df)) is None
    assert _bits(run_backtest(df, sigs, c)) == _fresh(df, sigs, c, monkeypatch)
    twin = list(sigs)                                   # equal content, another list
    assert engine._LEGS.lookup(df, twin, None, _walked(df)) is None
    df2 = df.copy()
    assert engine._LEGS.lookup(df2, sigs, None, _walked(df2)) is None
    assert engine._LEGS.lookup(df, sigs, 10, _walked(df)) is None    # another max_hold_bars
    sigs.append(sigs[-1])                               # grown in place
    assert engine._LEGS.lookup(df, sigs, None, _walked(df)) is None


@pytest.mark.parametrize("edit", ["loc_ohlc", "replace_column", "new_index", "new_zone"])
def test_the_same_frame_edited_in_place_walks_again(edit, monkeypatch):
    # Audit SF1 (2cf8a3f43): the slot used to trust the frame's identity, so an in-place edit
    # returned the previous path's trades. It now compares copies of the walked arrays.
    df = _frame(2_000, 11, "UTC")
    sigs = _signals(df, 11, 200)
    c = Costs()
    engine._LEGS.slot = None
    run_backtest(df, sigs, c)
    if edit == "loc_ohlc":
        df.loc[df.index[100:1_900], "high"] *= 1.05
        df.loc[df.index[100:1_900], "low"] *= 0.95
    elif edit == "replace_column":
        df["open"] = df["open"].to_numpy() * 1.01
    elif edit == "new_index":
        df.index = df.index + pd.Timedelta(hours=3)
    else:
        df.index = df.index.tz_convert("Asia/Tokyo")
    assert engine._LEGS.lookup(df, sigs, None, _walked(df)) is None
    assert _bits(run_backtest(df, sigs, c)) == _fresh(df, sigs, c, monkeypatch)


def test_a_signal_restamped_in_another_zone_walks_again(monkeypatch):
    # Audit SF2: `==` on the timestamp treated the same instant in another zone as unchanged,
    # so the refusals kept the old signal_time strings.
    df = _frame(2_000, 12, "UTC")
    sigs = _signals(df, 12, 200)
    c = Costs()
    engine._LEGS.slot = None
    run_backtest(df, sigs, c)
    for s in sigs:
        s.time = s.time.tz_convert("America/New_York")
    assert engine._LEGS.lookup(df, sigs, None, _walked(df)) is None
    assert _bits(run_backtest(df, sigs, c)) == _fresh(df, sigs, c, monkeypatch)


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
                 (pd.Timestamp("2026-10-25 02:30").tz_localize("Europe/Athens", ambiguous=True),
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
