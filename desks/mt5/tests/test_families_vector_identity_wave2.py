"""FASTER FAMILIES, SAME SIGNALS, WAVE 2: the same-skeleton breakout and reversion families,
`regime_transition`'s emission and the forced-flow calendar's per-call memo.

`test_families_vector_identity.py` pins wave 1. This file pins the next thirteen families moved
onto `mt5desk.families_vector` (level_breakout, engulfing_reversal, momentum_volgate,
adx_channel_hybrid, mean_reversion_rsi, mean_reversion_bollinger, trend_ma_cross, pullback_entry,
range_reversion, vol_transition, vol_mean_reversion, spread_state, htf_anchor_trend), the
per-position emission after `regime_transition`'s memoised hazard path, and the per-call memo of
`research.forced_flow_calendar`'s registry helpers. Each original loop stays in place verbatim
and runs when `MT5_VECTOR_FAMILIES=0`; the fast path only skips bars that cannot emit.

Same standard as wave 1: real parquets, parameters reaching every branch, the same Signal list
(length, order, every field equal AND of the same type, floats by IEEE bytes, Timestamps by
value, unit and tz), and inputs the fast path was not written for falling back to the original.
The exhaustive proof (docket rows through the sealed `build_cell`, every local parquet on a
random grid, both pandas versions) ships with the bundle in `patches/judge_vector_families/wave2`.
"""
from __future__ import annotations

import dataclasses
import itertools
import sys
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import families, families_vector, family_forced_flow  # noqa: E402
from mt5desk import families_orthogonal as fo  # noqa: E402

UNIVERSE = DESK / "data" / "universe"
CHARTS = ("EURUSD_H1", "XAUUSD_H1", "AUDCAD_M15", "XAUUSD_M5")


@pytest.fixture(autouse=True)
def _no_box_marker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
    """A tmp fail-closed marker path per test, never the checkout's real one (v1.4)."""
    marker = tmp_path / "VECTOR_FAMILIES_MISMATCH.json"
    monkeypatch.setattr(families_vector, "MARKER", marker)
    families_vector._forget_marker()
    yield marker
    families_vector._forget_marker()


@pytest.fixture(scope="module")
def frames() -> dict[str, pd.DataFrame]:
    out = {c: pd.read_parquet(UNIVERSE / f"{c}.parquet") for c in CHARTS
           if (UNIVERSE / f"{c}.parquet").exists()}
    if len(out) < 2:
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


T = {"atr_n": [20, 10], "ttl_bars": [12], "rr": [1.8, 2.0]}

#: One grid per family. Every combination is enumerated; each test walks a stride of it so the
#: file stays a fence, not the proof.
GRIDS: dict[str, dict[str, list]] = {
    "level_breakout": {"level": ["pdh", "week", "pwh"], "signal_hour": [0, 7, 13],
                       "vol_filter": ["all", "high"], "vol_gate_q": [0.5, 1.0],
                       "range_filter": ["all", "small"], "spread_gate": [False, True], **T},
    "engulfing_reversal": {"n": [1, 2, 3, 5], **T},
    "momentum_volgate": {"mom_n": [3, 6, 12], "vol_gate_q": [0.0, 0.4, 0.8],
                         "mom_thresh": [0.0005, 0.0012, 0.005], **T},
    "adx_channel_hybrid": {"channel": [20, 34], "adx_n": [7, 11], "adx_lag": [0, 10],
                           "stop_atr": [1.0, 1.5], **T},
    "mean_reversion_rsi": {"rsi_n": [7, 14, 21], "oversold": [20, 30], "overbought": [70, 80],
                           **T},
    "mean_reversion_bollinger": {"bb_n": [10, 20, 50], "bb_k": [1.0, 2.0, 3.0], **T},
    "trend_ma_cross": {"fast_ema": [5, 12, 20], "slow_ema": [12, 26, 50], **T},
    "pullback_entry": {"rsi_n": [7, 14], "trend_ema": [20, 50], "rsi_pullback": [30, 40],
                       "rsi_bounce": [50, 55], **T},
    "range_reversion": {"range_n": [10, 20, 48], "threshold_pct": [0.002, 0.01, 0.03], **T},
    "vol_transition": {"fast": [6, 12], "slow": [48, 96], "ratio_in": [1.2, 1.6, 2.0],
                       "stop_atr": [1.5], **T},
    "vol_mean_reversion": {"lookback": [48, 96], "z_in": [-2.5, -1.5, -0.5], "stop_atr": [1.0],
                           **T},
    "spread_state": {"mode": ["spike_reversion", "calm_continuation"], "norm_window": [60, 240],
                     "spike_pct": [0.9, 0.98], "calm_pct": [0.1, 0.4], "active_pct": [0.6, 0.8],
                     "min_move_atr": [0.0, 0.5], "hold_bars": [4, 8]},
    "htf_anchor_trend": {"anchor_mult": [3, 4, 6], "anchor_n": [20, 50], "entry_fast": [12],
                         "entry_slow": [36], "max_hold_bars": [60, 120],
                         "expansion_mult": [0.0, 1.25, 4.0], "exit_on_anchor_flip": [True, False]},
}


def _family(name: str):
    fn = getattr(families, f"family_{name}", None)
    return fn if fn is not None else fo.ORTHOGONAL_FAMILIES[name]


@pytest.mark.parametrize("name", sorted(GRIDS))
def test_family_matches_the_original_loop(monkeypatch: pytest.MonkeyPatch, frames, name) -> None:
    grid = GRIDS[name]
    combos = [dict(zip(grid, vals, strict=True)) for vals in itertools.product(*grid.values())]
    stride = max(1, len(combos) // 12)
    fn = _family(name)
    total = 0
    for k, kw in enumerate(combos[::stride]):
        chart = list(frames)[k % len(frames)]
        total += _assert_identical(monkeypatch, fn, frames[chart], **kw)
    assert total > 0, name


def test_unexpected_inputs_take_the_original_path(monkeypatch: pytest.MonkeyPatch, frames) -> None:
    df = next(iter(frames.values()))
    no_spread = df.drop(columns=["spread"]) if "spread" in df.columns else df
    reversed_ = df.iloc[::-1]
    cases = [
        ("level_breakout", df, {"signal_hour": "7"}),
        ("level_breakout", no_spread, {"spread_gate": True}),
        ("engulfing_reversal", df, {"n": 2.0}),
        ("momentum_volgate", df, {"mom_thresh": "0.001"}),
        ("mean_reversion_rsi", reversed_, {}),
        ("trend_ma_cross", df, {"rr": None}),
        ("vol_transition", reversed_, {}),
        ("spread_state", no_spread, {}),
        ("htf_anchor_trend", reversed_, {}),
    ]
    for name, frame, kw in cases:
        _assert_identical(monkeypatch, _family(name), frame, **kw)


def test_regime_transition_emission(monkeypatch: pytest.MonkeyPatch, frames) -> None:
    chart = "XAUUSD_H1" if "XAUUSD_H1" in frames else next(iter(frames))
    fn = fo.ORTHOGONAL_FAMILIES["regime_transition"]
    total = 0
    for p, age, side in itertools.product((0.1, 0.3), (0, 5), ("exhaustion", "expansion")):
        total += _assert_identical(monkeypatch, fn, frames[chart], window=300, refit_days=100,
                                   entry_p_leave=p, min_age=age, side_mode=side)
    assert total > 0


def _calendar():
    try:
        from research import forced_flow_calendar
    except ImportError:                                              # pragma: no cover
        import forced_flow_calendar  # type: ignore[no-redef]
    return forced_flow_calendar


def test_forced_flow_calendar_memo_is_identical(monkeypatch: pytest.MonkeyPatch) -> None:
    cal = _calendar()
    out = {}
    for flag in ("0", "1"):
        monkeypatch.setenv(families_vector.ENV, flag)
        out[flag] = [e.to_json() for e in cal.events(date(2019, 11, 1), date(2021, 2, 28))]
        assert getattr(cal._CALL, "memo", None) is None          # dropped when the call returns
    assert out["0"] == out["1"] and len(out["1"]) > 100


def test_forced_flow_with_and_without_the_artifact(monkeypatch: pytest.MonkeyPatch, frames,
                                                   tmp_path: Path) -> None:
    cal = _calendar()
    fixture = tmp_path / "forced_flow_calendar.json"
    monkeypatch.setenv(families_vector.ENV, "1")
    cal.write(fixture, days_ahead=30, days_back=900, today=date(2026, 10, 28))
    fn = fo.ORTHOGONAL_FAMILIES["forced_flow"]
    df = next(iter(frames.values()))
    for path in (tmp_path / "absent.json", fixture):
        monkeypatch.setattr(family_forced_flow, "CALENDAR_PATH", path)
        for kind, mode, side in itertools.product(("month_end", "fixing", "central_bank"),
                                                  ("pre_flow", "post_flow_fade"), (1, -1)):
            _assert_identical(monkeypatch, fn, df, side, event_kind=kind, mode=mode)


def _hostile_frames(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """The input classes the 2026-10-28 audit found unguarded in wave 1, for every wave-2 family."""
    df = df.iloc[:3000]
    stamps = df.index.to_numpy().copy()
    stamps[[0, 100, 1500]] = np.datetime64("NaT", "ns")
    out = {"nat": df.set_axis(pd.DatetimeIndex(stamps, tz=df.index.tz), axis=0),
           "nullable_float": df.astype(dict.fromkeys(["open", "high", "low", "close"], "Float64")),
           "nullable_all": df.convert_dtypes(),
           "object_close": df.astype({"close": object}),
           "dup_high": pd.concat([df, df[["high"]]], axis=1),
           "dup_close": pd.concat([df, df[["close"]] * 1.0001], axis=1)}
    if "spread" in df.columns:
        out["nullable_spread"] = df.astype({"spread": "Float64"})
    return out


@pytest.mark.parametrize("name", sorted(GRIDS))
def test_nat_nullable_and_duplicate_columns_take_the_original_path(
        monkeypatch: pytest.MonkeyPatch, frames, name) -> None:
    df = frames.get("EURUSD_H1", next(iter(frames.values())))
    first = {k: v[0] for k, v in GRIDS[name].items()}
    for frame in _hostile_frames(df).values():
        _assert_identical(monkeypatch, _family(name), frame)
        _assert_identical(monkeypatch, _family(name), frame, **first)


def test_regime_transition_and_forced_flow_on_hostile_frames(monkeypatch: pytest.MonkeyPatch,
                                                             frames) -> None:
    df = frames.get("EURUSD_H1", next(iter(frames.values())))
    for frame in _hostile_frames(df).values():
        _assert_identical(monkeypatch, fo.ORTHOGONAL_FAMILIES["regime_transition"], frame,
                          window=60, refit_days=30)
        _assert_identical(monkeypatch, fo.ORTHOGONAL_FAMILIES["forced_flow"], frame, 1,
                          event_kind="month_end")


def test_calendar_memo_reads_the_switch_like_families_vector(
        monkeypatch: pytest.MonkeyPatch) -> None:
    cal = _calendar()
    for raw in ("0", "00", "0.0", "false", "OFF", "no", "Disabled", "1", "true", "", "yes"):
        monkeypatch.setenv(families_vector.ENV, raw)
        assert cal._memo_active() == families_vector.enabled(), raw
    monkeypatch.delenv(families_vector.ENV, raising=False)
    assert cal._memo_active() and families_vector.enabled()


def test_calendar_memo_fails_closed_with_the_families(monkeypatch: pytest.MonkeyPatch,
                                                     tmp_path: Path,
                                                     _no_box_marker: Path) -> None:
    """The memo is a fast path too: a measured MISMATCH turns it off with the rest, through
    `families_vector.enabled()` when the desk package is loaded and through the same marker
    file when the calendar module runs on its own."""
    cal = _calendar()
    monkeypatch.setenv(families_vector.ENV, "1")
    assert cal._memo_active()
    families_vector.write_mismatch_marker({"verdict": "MISMATCH"})
    assert not cal._memo_active() and not families_vector.enabled()
    monkeypatch.setattr(families_vector, "_PROVING", True)     # the box check proving it
    assert cal._memo_active()
    monkeypatch.setattr(families_vector, "_PROVING", False)
    families_vector.clear_mismatch_marker()
    assert cal._memo_active()
    # standalone: no desk package loaded -> the restated rule reads the desk's marker path
    monkeypatch.delitem(sys.modules, "mt5desk.families_vector")
    real = cal.Path(cal.__file__).resolve().parents[1] / "data" / "VECTOR_FAMILIES_MISMATCH.json"
    assert cal._memo_active() is (not real.exists())
    monkeypatch.setenv(families_vector.ENV, "off")
    assert not cal._memo_active()


def test_box_check_hostile_list_covers_every_family() -> None:
    """Every family the box check proves on real charts is also proved on the hostile frames
    (wave-2 audit should-fix: regime_transition and forced_flow were missing)."""
    scripts = DESK / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import check_vector_families as chk
    assert {name for name, _ in chk.HOSTILE} == {name for name, _ in chk.CASES}
