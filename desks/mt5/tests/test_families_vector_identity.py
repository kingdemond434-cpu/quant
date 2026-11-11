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
import json
import sys
from collections.abc import Iterator
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


@pytest.fixture(autouse=True)
def _no_box_marker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
    """Every test here reads a marker path of its own, never the checkout's real one: a box that
    has measured a MISMATCH must not turn these identity tests into old-against-old."""
    marker = tmp_path / "VECTOR_FAMILIES_MISMATCH.json"
    monkeypatch.setattr(families_vector, "MARKER", marker)
    families_vector._forget_marker()
    yield marker
    families_vector._forget_marker()


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
    for off in ("0", "00", "0.0", "-0", "false", "OFF", " no ", "Disabled", "FALSE"):
        monkeypatch.setenv(families_vector.ENV, off)
        assert not families_vector.enabled(), off
    for on in ("1", "true", "yes", "on", "", "2", "0.5"):
        monkeypatch.setenv(families_vector.ENV, on)
        assert families_vector.enabled(), on


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


def _box_check():
    scripts = DESK / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import check_vector_families
    return check_vector_families


def test_box_check_unreadable_parquet_is_unmeasured(monkeypatch: pytest.MonkeyPatch,
                                                    tmp_path: Path) -> None:
    chk = _box_check()
    (tmp_path / "EURUSD_H1.parquet").write_bytes(b"not a parquet")
    monkeypatch.setattr(chk, "UNIVERSE", tmp_path)
    report = chk.run()
    assert report["verdict"] == "UNMEASURED" and report["unreadable"]
    monkeypatch.setattr(chk, "run", lambda: report)
    assert chk.main([]) == 2


def test_box_check_vacuous_pass_is_unmeasured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every case raising (0 signals) or no fast path engaging must not read IDENTICAL."""
    _frame("EURUSD_H1")
    chk = _box_check()
    monkeypatch.setattr(chk, "CHARTS", ("EURUSD_H1",))
    monkeypatch.setattr(chk, "HOSTILE", [])
    monkeypatch.setattr(chk, "CASES", [("ict_fvg", {"ema_slow": "34"})])   # raises both ways
    report = chk.run()
    assert report["signals"] == 0 and report["verdict"] == "UNMEASURED", report
    monkeypatch.setattr(chk, "CASES", [("ict_fvg", {})])
    real = families_vector.ict_fvg_emit
    monkeypatch.setattr(families_vector, "ict_fvg_emit", lambda **_: None)  # fast path declines
    report = chk.run()
    assert report["signals"] > 0 and report["not_engaged"] == ["ict_fvg"]
    assert report["verdict"] == "UNMEASURED"
    monkeypatch.setattr(families_vector, "ict_fvg_emit", real)
    report = chk.run()
    assert report["verdict"] == "IDENTICAL" and report["fast_path_engaged"].get("ict_fvg", 0) > 0


def _daily_cycle():
    research = DESK / "research"
    if str(research) not in sys.path:
        sys.path.insert(0, str(research))
    import daily_cycle
    return daily_cycle


def _fake_child(monkeypatch: pytest.MonkeyPatch, dc, chk, report: Path, outcome: str) -> list:
    """Stand in for the check's child process: write the report a real run would, or fail the way
    a real run can. Returns the drift events emitted."""
    from datetime import UTC, datetime, timedelta

    monkeypatch.setattr(chk, "REPORT", report)
    monkeypatch.setattr(dc, "dlog", lambda msg: None)

    def child(script: Path, out: Path) -> int:
        assert out == report and script.name == "check_vector_families.py"
        if outcome == "crash":
            raise RuntimeError("probe")
        if outcome == "timeout":
            import subprocess
            raise subprocess.TimeoutExpired(["check"], dc.VECTOR_CHECK_TIMEOUT_S)
        when = datetime.now(UTC)
        if outcome == "stale_mismatch":                 # last week's MISMATCH, nothing written now
            when -= timedelta(days=7)
        verdict, rc = {"mismatch": ("MISMATCH", 1), "stale_mismatch": ("MISMATCH", 1),
                       "identical": ("IDENTICAL", 0), "unmeasured": ("UNMEASURED", 2),
                       "raised_rc1": ("UNMEASURED", 1)}[outcome]
        if outcome == "raised_rc1":                     # an uncaught raise in the child: rc 1,
            return 1                                    # and no fresh report
        report.write_text(json.dumps({
            "generated_at": when.isoformat(), "verdict": verdict, "host": "probe",
            "mismatches": [{"family": "ict_fvg", "why": "probe"}] if rc == 1 else [],
            "unmeasured_because": ["probe"] if rc == 2 else []}), encoding="utf-8")
        return rc
    monkeypatch.setattr(dc, "_run_vector_check", child)
    seen: list[dict] = []
    from libs.ops import events
    monkeypatch.setattr(events, "emit", lambda kind, path=None, **f: seen.append({"kind": kind,
                                                                                  **f}))
    return seen


def _tiny_frame() -> pd.DataFrame:
    idx = pd.date_range("2026-01-05", periods=24 * 20, freq="h", tz="UTC")
    rng = np.random.default_rng(7)
    close = 1.1 + np.cumsum(rng.normal(0, 1e-3, len(idx)))
    return pd.DataFrame({"open": close, "high": close + 2e-3, "low": close - 2e-3,
                         "close": close, "spread": 1.0}, index=idx)


def _ict_fast_calls(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Spy on the ict_fvg fast path: how often the family asked it."""
    calls: list[int] = []
    real = families_vector.ict_fvg_emit

    def spy(**kw: object) -> object:
        calls.append(1)
        return real(**kw)
    monkeypatch.setattr(families_vector, "ict_fvg_emit", spy)
    return calls


@pytest.mark.parametrize("outcome", ["mismatch", "unmeasured", "crash", "timeout",
                                     "stale_mismatch", "raised_rc1"])
def test_daily_drift_monitor_never_fails_the_cycle(monkeypatch: pytest.MonkeyPatch,
                                                   tmp_path: Path, outcome: str) -> None:
    """The daily leg is a shadow: anything but IDENTICAL is a loud event, never a raise."""
    dc, chk = _daily_cycle(), _box_check()
    seen = _fake_child(monkeypatch, dc, chk, tmp_path / "VECTOR_FAMILIES_CHECK.json", outcome)
    dc._vector_families_check()                         # must not raise
    assert len(seen) == 1 and seen[0]["kind"] == "vector_families_drift"
    assert seen[0]["verdict"] == ("MISMATCH" if outcome == "mismatch" else "UNMEASURED")


def test_mismatch_fails_closed_to_the_original_loops(monkeypatch: pytest.MonkeyPatch,
                                                     tmp_path: Path,
                                                     _no_box_marker: Path) -> None:
    """MISMATCH writes the marker with the evidence; with the switch ON, every family then takes
    its original loop until the marker goes."""
    dc, chk = _daily_cycle(), _box_check()
    seen = _fake_child(monkeypatch, dc, chk, tmp_path / "r.json", "mismatch")
    monkeypatch.setenv(families_vector.ENV, "1")
    calls = _ict_fast_calls(monkeypatch)
    df = _tiny_frame()
    families.family_ict_fvg(df)
    assert calls and families_vector.enabled()
    dc._vector_families_check()
    assert _no_box_marker.exists() and seen[0]["marker"] == "written"
    evidence = json.loads(_no_box_marker.read_text(encoding="utf-8"))
    assert evidence["verdict"] == "MISMATCH" and evidence["mismatches"][0]["family"] == "ict_fvg"
    calls.clear()
    families.family_ict_fvg(df)
    assert calls == [] and not families_vector.enabled()
    mode = families_vector.mode()
    assert mode["env_enabled"] and mode["mismatch_marker"] and not mode["enabled"]


def test_marker_is_read_through_a_short_cache(monkeypatch: pytest.MonkeyPatch,
                                              _no_box_marker: Path) -> None:
    """`enabled()` runs per family call, so it stats the marker at most once per TTL; a marker
    written by ANOTHER process is seen once the TTL lapses."""
    monkeypatch.setenv(families_vector.ENV, "1")
    clock = [1000.0]
    monkeypatch.setattr(families_vector.time, "monotonic", lambda: clock[0])
    assert families_vector.enabled()
    _no_box_marker.write_text("{}", encoding="utf-8")       # another process, behind our back
    assert families_vector.enabled()                        # within the TTL: last look stands
    clock[0] += families_vector.MARKER_TTL_S
    assert not families_vector.enabled()
    _no_box_marker.unlink()
    clock[0] += families_vector.MARKER_TTL_S
    assert families_vector.enabled()


def test_identical_clears_the_marker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                                     _no_box_marker: Path) -> None:
    dc, chk = _daily_cycle(), _box_check()
    families_vector.write_mismatch_marker({"verdict": "MISMATCH"})
    monkeypatch.setenv(families_vector.ENV, "1")
    assert not families_vector.enabled()
    seen = _fake_child(monkeypatch, dc, chk, tmp_path / "r.json", "identical")
    dc._vector_families_check()
    assert seen == [] and not _no_box_marker.exists() and families_vector.enabled()
    calls = _ict_fast_calls(monkeypatch)
    families.family_ict_fvg(_tiny_frame())
    assert calls


@pytest.mark.parametrize("outcome", ["unmeasured", "crash", "timeout", "stale_mismatch",
                                     "raised_rc1"])
@pytest.mark.parametrize("marked", [True, False])
def test_unmeasured_leaves_the_marker_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                                                _no_box_marker: Path, outcome: str,
                                                marked: bool) -> None:
    """No measurement, no change: a standing marker stays (with its evidence), an absent one is
    not invented -- a stale MISMATCH report and a bare rc 1 included."""
    dc, chk = _daily_cycle(), _box_check()
    if marked:
        families_vector.write_mismatch_marker({"verdict": "MISMATCH", "tag": "standing"})
    before = _no_box_marker.read_bytes() if marked else None
    seen = _fake_child(monkeypatch, dc, chk, tmp_path / "r.json", outcome)
    dc._vector_families_check()
    assert seen[0]["verdict"] == "UNMEASURED" and seen[0]["marker"] == "unchanged"
    assert _no_box_marker.exists() is marked
    if marked:
        assert _no_box_marker.read_bytes() == before


def test_daily_leg_runs_the_check_in_a_child_with_a_timeout(monkeypatch: pytest.MonkeyPatch,
                                                            tmp_path: Path) -> None:
    import subprocess

    dc = _daily_cycle()
    monkeypatch.setattr(dc, "dlog", lambda msg: None)
    got: dict = {}

    def fake_run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess:
        got.update(cmd=cmd, **kw)
        return subprocess.CompletedProcess(cmd, 2, stdout="check_vector_families: UNMEASURED\n",
                                           stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    script = DESK / "scripts" / "check_vector_families.py"
    assert dc._run_vector_check(script, tmp_path / "r.json") == 2
    assert got["cmd"][:2] == [sys.executable, str(script)]
    assert got["cmd"][2:] == ["--out", str(tmp_path / "r.json"), "--quiet"]
    assert got["timeout"] == dc.VECTOR_CHECK_TIMEOUT_S and got["check"] is False


def test_box_check_restores_everything_when_it_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Whatever raises mid-check, the module attributes, the switch and the proving flag are
    back as they were (the v1.3 should-fix: restore() in a finally)."""
    _frame("EURUSD_H1")
    chk = _box_check()
    before = {a: getattr(families_vector, a) for a in dir(families_vector)
              if a.endswith("_emit") or a == "true_range"}
    monkeypatch.setenv(families_vector.ENV, "yes")

    def boom(*_: object, **__: object) -> None:
        assert families_vector._PROVING
        raise RuntimeError("probe")
    monkeypatch.setattr(chk, "_call", boom)
    with pytest.raises(RuntimeError, match="probe"):
        chk.run()
    after = {a: getattr(families_vector, a) for a in before}
    assert after == before and families_vector._PROVING is False
    import os
    assert os.environ[families_vector.ENV] == "yes"


def test_box_check_proves_the_fast_path_while_a_marker_stands(
        monkeypatch: pytest.MonkeyPatch, _no_box_marker: Path) -> None:
    """A marker must not make the check compare the original with itself, or it could never be
    cleared: the check still reaches every fast path, and reports the box's real mode."""
    _frame("EURUSD_H1")
    chk = _box_check()
    families_vector.write_mismatch_marker({"verdict": "MISMATCH"})
    monkeypatch.delenv(families_vector.ENV, raising=False)
    report = chk.run()
    assert report["verdict"] == "IDENTICAL", report["unmeasured_because"]
    assert report["mode_as_found"]["mismatch_marker"] and not report["mode_as_found"]["enabled"]
    assert families_vector._PROVING is False and not families_vector.enabled()
