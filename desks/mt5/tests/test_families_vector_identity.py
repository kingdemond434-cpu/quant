"""FASTER FAMILIES, SAME SIGNALS: `mt5desk.families_vector` against the original loops it replaces.

About three quarters of the judge's CPU per built cell is family signal code (PREWARM_CEILING,
2026-10-27). `families_vector` makes the costliest of it fast: `formula`,
`session_range_breakout`, `failed_breakout`, `ict_fvg`, `multi_speed_trend`, and the true range
under `families._atr`, which almost every family calls. A faster judge that judges differently is
a different judge, so every one of them is pinned here against the ORIGINAL loop, which stays in
the family function verbatim and runs when `MT5_VECTOR_FAMILIES=0`.

On real parquets from `data/universe`, with parameters that reach every branch (filters, gates,
float and odd hours, crisis mode, zero thresholds), the two paths must return the same Signal
list: same length and order, every dataclass field equal AND of the same type, floats compared
by their IEEE bytes, Timestamps by value, unit and tz. Inputs the fast path was not written for
must fall back to the original, so an input that raised still raises the same exception.

The exhaustive proof (every committed docket row of these families through the sealed
`build_cell`, and every local parquet on a random branch grid) lives with the bundle in
`patches/judge_vector_families/`; this file is the standing fence on a sample of it.
"""
from __future__ import annotations

import dataclasses
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import families, families_vector  # noqa: E402
from mt5desk.family_formula import family_formula  # noqa: E402
from mt5desk.family_multi_speed_trend import family_multi_speed_trend  # noqa: E402

UNIVERSE = DESK / "data" / "universe"
CHARTS = ("EURUSD_H1", "XAUUSD_H1", "USDJPY_H1", "BTCUSD_H1", "AUDCAD_M15", "XAUUSD_M5")


def _frame(chart: str) -> pd.DataFrame:
    path = UNIVERSE / f"{chart}.parquet"
    if not path.exists():
        pytest.skip(f"{chart} parquet not in this checkout")
    return pd.read_parquet(path)


@pytest.fixture(scope="module")
def frames() -> dict[str, pd.DataFrame]:
    out = {c: pd.read_parquet(UNIVERSE / f"{c}.parquet") for c in CHARTS
           if (UNIVERSE / f"{c}.parquet").exists()}
    if len(out) < 3:
        pytest.skip("too few universe parquets in this checkout")
    return out


def _same(a: object, b: object) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, pd.Timestamp):
        assert isinstance(b, pd.Timestamp)
        return a.value == b.value and a.unit == b.unit and str(a.tz) == str(b.tz)
    if isinstance(a, (float, np.floating)):
        return np.asarray(a).tobytes() == np.asarray(b).tobytes()
    return a == b


def _run(monkeypatch: pytest.MonkeyPatch, flag: str, fn, *args, **kw):
    monkeypatch.setenv(families_vector.ENV, flag)
    try:
        return list(fn(*args, **kw) or [])
    except Exception as exc:  # the exception IS the answer being compared
        return ("raised", type(exc).__name__, str(exc))


def _assert_identical(monkeypatch: pytest.MonkeyPatch, fn, *args, **kw) -> int:
    old = _run(monkeypatch, "0", fn, *args, **kw)
    new = _run(monkeypatch, "1", fn, *args, **kw)
    if isinstance(old, tuple) or isinstance(new, tuple):
        assert old == new
        return 0
    assert len(old) == len(new), (len(old), len(new))
    for k, (x, y) in enumerate(zip(old, new, strict=True)):
        assert type(x) is type(y)
        for f in dataclasses.fields(x):
            assert _same(getattr(x, f.name), getattr(y, f.name)), (k, f.name, getattr(x, f.name),
                                                                    getattr(y, f.name))
    return len(old)


def test_switch_reads_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(families_vector.ENV, raising=False)
    assert families_vector.enabled()
    for off in ("0", "false", "OFF", " no "):
        monkeypatch.setenv(families_vector.ENV, off)
        assert not families_vector.enabled()
    monkeypatch.setenv(families_vector.ENV, "1")
    assert families_vector.enabled()


def test_true_range_is_bit_identical_on_every_local_chart(monkeypatch: pytest.MonkeyPatch) -> None:
    charts = sorted(UNIVERSE.glob("*.parquet"))
    if not charts:
        pytest.skip("no universe parquets in this checkout")
    for path in charts:
        df = families._h1(pd.read_parquet(path))
        for n in (1, 14, 20, 200):
            monkeypatch.setenv(families_vector.ENV, "0")
            old = families._atr(df, n)
            monkeypatch.setenv(families_vector.ENV, "1")
            new = families._atr(df, n)
            assert old.index.equals(new.index) and old.name == new.name, path.name
            assert old.dtype == new.dtype
            assert old.to_numpy().tobytes() == new.to_numpy().tobytes(), (path.name, n)


def test_true_range_edges_match(monkeypatch: pytest.MonkeyPatch) -> None:
    idx = pd.date_range("2024-01-01", periods=8, freq="h", tz="UTC")
    df = pd.DataFrame({"high": [1.0, np.nan, np.inf, 2.0, np.nan, 3.0, -np.inf, 1.5],
                       "low": [0.5, np.nan, 1.0, np.nan, np.nan, 3.0, 1.0, 1.5],
                       "close": [0.7, 1.0, np.nan, 1.5, np.nan, 3.0, np.inf, 1.5]}, index=idx)
    for n in (1, 3):
        monkeypatch.setenv(families_vector.ENV, "0")
        old = families._atr(df, n)
        monkeypatch.setenv(families_vector.ENV, "1")
        new = families._atr(df, n)
        assert old.to_numpy().tobytes() == new.to_numpy().tobytes()
    # Non-float columns and duplicated stamps take the original path.
    assert families_vector.true_range(df.astype({"high": "float32"})) is None
    assert families_vector.true_range(df.iloc[[0, 0, 1]]) is None


SRB_GRID = list(itertools.product(
    [(7, None, None), (3, None, None), (8, 13, None), (12, 16, 18), (22, 2, None), (7.0, None, 9)],
    [False, True],                                   # spread_gate
    ["none", "aligned"],                             # trend_filter
    ["all", "small", "large"],                       # range_filter
    ["all", "low", "high"],                          # vol_filter
    ["off", "prev_day"],                             # midpoint_filter
))


def test_session_range_breakout(monkeypatch: pytest.MonkeyPatch, frames) -> None:
    total = 0
    for k, (win, gate, trend, rng_f, vol_f, mid_f) in enumerate(SRB_GRID[::7]):
        chart = list(frames)[k % len(frames)]
        rs, re_, sa = win
        total += _assert_identical(
            monkeypatch, families.family_session_range_breakout, frames[chart],
            range_start=rs, range_end=re_, signal_at=sa, wait_bars=12, rr=2.5,
            spread_gate=gate, trend_filter=trend, range_filter=rng_f, vol_filter=vol_f,
            midpoint_filter=mid_f)
    assert total > 1000


def test_failed_breakout(monkeypatch: pytest.MonkeyPatch, frames) -> None:
    total = 0
    grid = itertools.product([(7, 13, 14, 17), [0, 1, 2], (7.0, 13), tuple(range(24))],
                             [0.0, 0.05, 0.3], [False, True])
    for k, (hours, pierce, gate) in enumerate(grid):
        chart = list(frames)[k % len(frames)]
        total += _assert_identical(monkeypatch, families.family_failed_breakout, frames[chart],
                                   signal_hours=hours, min_pierce_atr=pierce, spread_gate=gate,
                                   level="pdh", rr=1.6)
    assert total > 1000


def test_ict_fvg(monkeypatch: pytest.MonkeyPatch, frames) -> None:
    total = 0
    for k, (fast, slow, atr_n) in enumerate(itertools.product([5, 8], [3, 21, 55], [10, 50])):
        chart = list(frames)[k % len(frames)]
        total += _assert_identical(monkeypatch, families.family_ict_fvg, frames[chart],
                                   ema_fast=fast, ema_slow=slow, atr_n=atr_n, rr=2.0)
    assert total > 1000


def test_multi_speed_trend(monkeypatch: pytest.MonkeyPatch, frames) -> None:
    total = 0
    grid = itertools.product([(10, 21, 63, 126, 252), [5, 10, 21, 63], (1, 2, 5)],
                             [1, 5], [0.3, 0.6, 1.0], [False, True])
    for k, (speeds, hold, agree, crisis) in enumerate(grid):
        chart = list(frames)[k % len(frames)]
        total += _assert_identical(monkeypatch, family_multi_speed_trend, frames[chart],
                                   speeds=speeds, hold_days=hold, min_agreement=agree,
                                   crisis_only=crisis)
    assert total > 200


FORMULA_EXPRS = ("div(open, bars_since_min(high, 5))", "sub(close, open)",
                 ["sub", "high", "low"], ["neg", ["delta", "spread", 5]],
                 ["ts_rank", "spread", 240], "close")


def test_formula(monkeypatch: pytest.MonkeyPatch, frames) -> None:
    total = 0
    grid = itertools.product(FORMULA_EXPRS, [0.0, 1.5], [1, 8], ["follow", "fade"])
    for k, (expr, ez, hold, mode) in enumerate(grid):
        chart = list(frames)[k % len(frames)]
        total += _assert_identical(monkeypatch, family_formula, frames[chart], expr=expr,
                                   norm=240, entry_z=ez, hold_bars=hold, side_mode=mode)
    assert total > 1000


def test_unexpected_inputs_take_the_original_path(monkeypatch: pytest.MonkeyPatch) -> None:
    df = _frame("EURUSD_H1")
    no_spread = df.drop(columns=["spread"])
    cases = [
        (families.family_session_range_breakout, df, {"range_start": "7"}),
        (families.family_session_range_breakout, df, {"range_start": True}),
        (families.family_session_range_breakout, no_spread, {"spread_gate": True}),
        (families.family_failed_breakout, df, {"signal_hours": 7}),
        (families.family_failed_breakout, df, {"signal_hours": ("7", "13")}),
        (families.family_failed_breakout, no_spread, {"spread_gate": True}),
        (families.family_ict_fvg, df, {"ema_slow": 34.0}),
        (family_formula, df, {"expr": "sub(close, open)", "stop_atr": "2"}),
        (family_formula, df, {"expr": "sub(close, open)", "hold_bars": None}),
        (family_multi_speed_trend, df, {"stop_atr": "2.5"}),
        (family_multi_speed_trend, df.iloc[::-1], {}),
    ]
    for fn, frame, kw in cases:
        _assert_identical(monkeypatch, fn, frame, **kw)


def _hostile_frames(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """The input classes the 2026-10-28 audit found unguarded, plus their neighbours."""
    df = df.iloc[:3000]
    out: dict[str, pd.DataFrame] = {}
    stamps = df.index.to_numpy().copy()
    stamps[[0, 100, 1500]] = np.datetime64("NaT", "ns")
    out["nat"] = df.set_axis(pd.DatetimeIndex(stamps, tz=df.index.tz), axis=0)
    ohlc = ["open", "high", "low", "close"]
    out["nullable_float"] = df.astype(dict.fromkeys(ohlc, "Float64"))
    out["nullable_all"] = df.convert_dtypes()
    out["object_close"] = df.astype({"close": object})
    if "spread" in df.columns:
        out["nullable_spread"] = df.astype({"spread": "Float64"})
    out["dup_high"] = pd.concat([df, df[["high"]]], axis=1)
    out["dup_close"] = pd.concat([df, df[["close"]] * 1.0001], axis=1)
    return out


HOSTILE_CASES = (
    (lambda: families.family_session_range_breakout, {"midpoint_filter": "prev_day"}),
    (lambda: families.family_session_range_breakout,
     {"range_filter": "large", "spread_gate": True}),
    (lambda: families.family_failed_breakout, {}),
    (lambda: families.family_failed_breakout, {"spread_gate": True, "level": "pwh"}),
    (lambda: families.family_ict_fvg, {}),
    (lambda: family_multi_speed_trend, {"hold_days": 1, "min_agreement": 0.5}),
    (lambda: family_formula, {"expr": "sub(close, open)", "entry_z": 0.5}),
    (lambda: family_formula, {"expr": ["neg", ["delta", "spread", 5]]}),
)


def test_nat_nullable_and_duplicate_columns_take_the_original_path(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """NaT stamps, nullable/extension/object dtypes and duplicated column labels: the original
    loop answers (same signals, or the same exception) for every wave-1 family and for `_atr`."""
    hostile = _hostile_frames(_frame("EURUSD_H1"))
    for label, frame in hostile.items():
        for get_fn, kw in HOSTILE_CASES:
            _assert_identical(monkeypatch, get_fn(), frame, **kw)
        for n in (1, 14):
            old = _run(monkeypatch, "0", lambda f, k: [families._atr(f, k)], frame, n)
            new = _run(monkeypatch, "1", lambda f, k: [families._atr(f, k)], frame, n)
            if isinstance(old, tuple) or isinstance(new, tuple):
                assert old == new, label
            else:
                assert old[0].index.equals(new[0].index), label
                assert old[0].dtype == new[0].dtype, label
                assert old[0].to_numpy().tobytes() == new[0].to_numpy().tobytes(), label


def test_duplicate_high_raises_the_original_error(monkeypatch: pytest.MonkeyPatch) -> None:
    df = _frame("EURUSD_H1").iloc[:500]
    dup = pd.concat([df, df[["high"]]], axis=1)
    old = _run(monkeypatch, "0", lambda f: [families._atr(f, 14)], dup)
    new = _run(monkeypatch, "1", lambda f: [families._atr(f, 14)], dup)
    assert isinstance(old, tuple) == isinstance(new, tuple)
    if isinstance(old, tuple):
        assert old == new


def test_fast_path_exceptions_are_counted_and_answered_by_the_original(
        monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    df = _frame("EURUSD_H1").iloc[:2000]
    monkeypatch.setenv(families_vector.ENV, "0")
    want = families.family_ict_fvg(df)

    def boom(**_: object) -> None:
        raise RuntimeError("probe")
    monkeypatch.setattr(families_vector, "ict_fvg_emit", boom)
    monkeypatch.setattr(families_vector, "_FALLBACKS", {})
    monkeypatch.setenv(families_vector.ENV, "1")
    with caplog.at_level("WARNING", logger="mt5desk.families_vector"):
        got = [families.family_ict_fvg(df) for _ in range(3)]
    assert all(g == want for g in got)
    assert families_vector.fallback_counts() == {"ict_fvg": 3}
    assert sum("ict_fvg fast path raised" in r.getMessage() for r in caplog.records) == 1
    assert families_vector.mode()["fallbacks"] == {"ict_fvg": 3}
