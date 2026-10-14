"""LIVE PARITY OF THE STATE GATES: the gate a certificate was earned under is the gate the
gateway computes.

Every wrapper ranks its state against the states at the base's earlier signals. Unbounded, that
history ran back to the frame's first bar, so the gateway's 400-bar read ranked against a
different history than the replay and the certificate described a strategy nobody could trade.
Now the rank history is bounded to `RANK_SPAN_DAYS` of market time, `live_h1_bars` says how many
bars hold it, the gateway reads that many for these families and refuses a short read by name,
and a panel that is not current at t reads None in the replay and on the box alike.

The proof below is the one that matters: for each wrapper, the decision at the frame's last
signal bar is IDENTICAL on the full history and on the last `live_h1_bars` bars alone.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_HERE = Path(__file__).resolve().parent
_DESK = _HERE.parent
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import family_state_gates as fsg  # noqa: E402
from mt5desk.families import Signal  # noqa: E402

T0 = pd.Timestamp("2023-01-02 00:00", tz="UTC")       # a Monday
HOUR = 3600 * 10**9
DAY = 24 * HOUR


def _sig(t: pd.Timestamp) -> Signal:
    return Signal(time=t, side=1, stop=0.9, target=1.2, ttl_bars=12, tag="fake")


def _fake_base(times: list[pd.Timestamp]):
    def fn(d: pd.DataFrame, **_kw) -> list[Signal]:
        return [_sig(t) for t in times if t in d.index]
    return fn


def _bars(close: np.ndarray, index: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999,
                         "close": close, "tick_volume": 1.0}, index=index)


def _weekday_index(days: int) -> pd.DatetimeIndex:
    """H1 stamps Monday..Friday only, as an FX symbol prints."""
    idx = pd.date_range(T0, periods=days * 24, freq="h").as_unit("ns")
    return idx[idx.dayofweek < 5]


def _close(n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    regime = np.repeat(rng.choice([0.0006, 0.0018], size=n // 200 + 1), 200)[:n]
    vol = regime * np.exp(0.3 * np.sin(np.arange(n) / 500.0))
    return np.exp(np.cumsum(rng.normal(0.0, 1.0, n) * vol))


# ----------------------------------------------------------------- (a) the bounded rank span ---
def test_a_reading_older_than_the_span_leaves_the_history() -> None:
    """Brute force: kept iff the reading ranks in its tail among readings at EARLIER signal bars
    inside the trailing span only."""
    rng = np.random.default_rng(1)
    times = [T0 + pd.Timedelta(hours=int(h)) for h in np.cumsum(rng.integers(5, 60, 400))]
    vals = {int(t.value): float(v) for t, v in zip(times, rng.normal(size=len(times)),
                                                    strict=True)}
    span = 60.0
    for top in (True, False):
        kept = fsg.keep_in_tail([_sig(t) for t in times], lambda k, s: vals[k], keep_top=top,
                                span_days=span)
        expect = []
        for t in times:
            k = int(t.value)
            hist = [vals[int(u.value)] for u in times
                    if k - span * DAY <= int(u.value) < k]
            if len(hist) < 30:
                continue
            below = sum(h < vals[k] for h in hist) / len(hist)
            if (below >= 1.0 - 1.0 / 3.0) if top else (below <= 1.0 / 3.0):
                expect.append(t)
        assert [s.time for s in kept] == expect and expect


def test_the_span_is_the_one_constant_everywhere() -> None:
    import inspect
    assert inspect.signature(fsg.keep_in_tail).parameters["span_days"].default \
        == fsg.RANK_SPAN_DAYS == 365


# ------------------------------------------------------------- (b) the decision at the edge ---
def _edge_decisions(fn, df: pd.DataFrame, times: list[pd.Timestamp], need: int, *,
                    ends: int = 40, every: int = 1, **kw) -> tuple[list[bool], list[bool]]:
    """For several frame ends: was the frame's LAST signal kept, on the full history and on the
    last `need` bars of the same frame? Each end is a live pass seeing that bar."""
    full, live = [], []
    for t_end in times[-ends * every::every]:
        upto = df.loc[:t_end]
        k_full = {s.time for s in fn(upto, **kw)}
        k_live = {s.time for s in fn(upto.iloc[-need:], **kw)}
        full.append(t_end in k_full)
        live.append(t_end in k_live)
    return full, live


def test_markov_gate_decides_the_same_on_the_live_read(monkeypatch) -> None:
    params = {"fit_window": 400, "refit": 168, "max_iter": 40}
    idx = _weekday_index(720)
    close = _close(len(idx), 3)
    df = _bars(close, idx)
    times = list(idx[4000::23])
    monkeypatch.setattr(fsg, "get_family_func", lambda name: _fake_base(times))
    need = fsg.live_h1_bars("markov_vol_gated", params)
    assert need is not None and need < len(idx) - 2000
    full, live = _edge_decisions(fsg.family_markov_vol_gated, df, times, need,
                                 base_family="trend_ma_cross", **params)
    assert full == live and any(full) and not all(full)


def test_rough_gate_decides_the_same_on_the_live_read(monkeypatch) -> None:
    rng = np.random.default_rng(5)
    idx = _weekday_index(1150)
    day = (idx.asi8 // DAY)
    _, inv = np.unique(day, return_inverse=True)
    # Log vol alternates, in 60-day blocks, between a random walk (persistent, H near 0.5) and
    # i.i.d. noise (rough, H near 0), so H moves both ways and the gate keeps and drops.
    n_days = inv.max() + 1
    log_sig = np.empty(n_days)
    for b0 in range(0, n_days, 60):
        seg = slice(b0, min(n_days, b0 + 60))
        m = seg.stop - seg.start
        walk = (b0 // 60) % 2 == 0
        log_sig[seg] = (np.cumsum(rng.normal(0, 0.15, m)) - 0.0) if walk \
            else rng.normal(0, 0.4, m)
    sd = 0.001 * np.exp(log_sig - log_sig.mean())[inv.ravel()]
    close = np.exp(np.cumsum(rng.normal(size=len(idx)) * sd))
    df = _bars(close, idx)
    times = list(idx[len(idx) // 2::31])
    monkeypatch.setattr(fsg, "get_family_func", lambda name: _fake_base(times))
    need = fsg.live_h1_bars("rough_vol_gated")
    assert need is not None and need < len(idx) - 1000
    full, live = _edge_decisions(fsg.family_rough_vol_gated, df, times, need, every=8,
                                 base_family="mean_reversion_rsi")
    assert full == live and any(full) and not all(full)


def test_fisher_gate_decides_the_same_on_the_live_read(monkeypatch) -> None:
    idx = _weekday_index(840)
    df = _bars(_close(len(idx), 7), idx)
    times = list(idx[-3000::17])
    monkeypatch.setattr(fsg, "get_family_func", lambda name: _fake_base(times))
    need = fsg.live_h1_bars("fisher_rao_gated")
    assert need is not None and need < len(idx) - 1000
    full, live = _edge_decisions(fsg.family_fisher_rao_gated, df, times, need,
                                 base_family="trend_ma_cross")
    assert full == live and any(full) and not all(full)


def test_entropy_gate_decides_the_same_on_the_live_read(monkeypatch) -> None:
    idx = _weekday_index(200)
    df = _bars(_close(len(idx), 9), idx)
    times = list(idx[2500::7])
    monkeypatch.setattr(fsg, "get_family_func", lambda name: _fake_base(times))
    need = fsg.live_h1_bars("entropy_gated")
    assert need is not None and need < len(idx) - 500
    full, live = _edge_decisions(fsg.family_entropy_gated, df, times, need,
                                 base_family="trend_ma_cross", threshold=0.0)
    assert full == live and any(full) and not all(full)


# ----------------------------------------------------------------- (c) the panel is current ---
def _panel(n: int, k: int, seed: int, end: pd.Timestamp | None = None
           ) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    rng = np.random.default_rng(seed)
    idx = pd.date_range(end=end or (T0 + pd.Timedelta(hours=n - 1)), periods=n, freq="h")
    st = idx.as_unit("ns").asi8
    common = rng.normal(0, 0.001, n)
    return {f"S{j:02d}": (st, np.exp(np.cumsum(0.7 * common + rng.normal(0, 0.001, n))))
            for j in range(k)}


def test_a_lagging_panel_reads_no_state() -> None:
    """Three hours behind t is a bar store that has not caught up, not a market at t. The replay
    has the bar at t; a box whose store lags reads None rather than a three-hour-old state."""
    panel = _panel(1200, 24, 11)
    last = pd.Timestamp(int(panel["S00"][0][-1]), tz="UTC")
    assert fsg.kuramoto_r(panel, last) is not None
    assert fsg.kuramoto_r(panel, last + pd.Timedelta(hours=1)) is not None
    assert fsg.kuramoto_r(panel, last + pd.Timedelta(hours=3)) is None
    assert fsg.aligned_returns(panel, last, window=360, min_members=20) is not None
    assert fsg.aligned_returns(panel, last + pd.Timedelta(hours=3), window=360,
                               min_members=20) is None


# ------------------------------------------------------------------- (d) the gateway's read ---
def test_every_wrapper_declares_its_live_read() -> None:
    for fam in fsg.STATE_GATE_FAMILIES:
        need = fsg.live_h1_bars(fam)
        assert isinstance(need, int) and need > fsg.BASE_H1_BARS, fam
    assert fsg.live_h1_bars("trend_ma_cross") is None
    # A certificate's own params move its read: a longer fit window needs more bars.
    assert fsg.live_h1_bars("markov_vol_gated", {"fit_window": 3000}) \
        == fsg.live_h1_bars("markov_vol_gated") + 1000


def test_state_gates_are_executable_and_the_gateway_reads_their_span() -> None:
    ex = pytest.importorskip("mt5desk.executables")
    for fam in fsg.STATE_GATE_FAMILIES:
        assert ex.executor_gap(fam) is None, fam
    src = (_DESK / "mt5desk" / "gateway.py").read_text("utf-8")
    tree = ast.parse(src)
    fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    chart = ast.get_source_segment(src, fns["_family_chart"]) or ""
    assert "_state_gate_bars(s)" in chart and "live_h1_bars" in \
        (ast.get_source_segment(src, fns["_state_gate_bars"]) or "")
    # and the short read is refused by name, never computed on a shorter history
    assert '"short_history"' in src and "len(h1) < gate_need" in src


_CHART_PROBE = """
import sys, types, json
sys.path[:0] = [sys.argv[1], sys.argv[2]]
from unittest import mock
stub = types.ModuleType("MetaTrader5")
stub.__getattr__ = lambda name: mock.MagicMock(name="MetaTrader5." + name)
sys.modules["MetaTrader5"] = stub
import mt5desk.gateway as gw
from mt5desk import family_state_gates as fsg
p = {"base_family": "trend_ma_cross", "fit_window": 2000, "refit": 168}
_tf, _c, gate = gw._family_chart({"family": "markov_vol_gated", "params": p})
_tf, _c, other = gw._family_chart({"family": "trend_ma_cross", "params": {}})
print(json.dumps([_tf, gate, fsg.live_h1_bars("markov_vol_gated", p), other]))
"""


def test_the_gateway_chart_returns_the_wrappers_read() -> None:
    """Run against the real gateway module with the terminal stubbed (as the import probe
    does), in a subprocess so the stub never leaks into this process."""
    import json
    import subprocess
    proc = subprocess.run([sys.executable, "-c", _CHART_PROBE, str(_ROOT), str(_DESK)],
                          cwd=str(_ROOT),
                          capture_output=True, text=True, timeout=300, check=False)
    assert proc.returncode == 0, proc.stderr[-3000:]
    tf, gate, want, other = json.loads(proc.stdout.strip().splitlines()[-1])
    assert tf == "H1" and gate == want and gate > 400
    assert other == 400                              # every other family's read is unchanged


def test_sync_gate_decides_the_same_on_the_live_read(monkeypatch) -> None:
    """A panel wrapper reads its panel from the bar store, so the frame needs only the base's
    read behind the earliest ranked signal and every bar of the rank span."""
    idx = _weekday_index(900)
    rng = np.random.default_rng(13)
    st = idx.asi8
    n = len(idx)
    drive = rng.normal(0, 0.001, n) * np.repeat(rng.choice([0.2, 2.0], n // 300 + 1), 300)[:n]
    panel = {f"S{j:02d}": (st, np.exp(np.cumsum(drive + rng.normal(0, 0.001, n))))
             for j in range(16)}
    monkeypatch.setattr(fsg, "load_panel", lambda: panel)
    df = _bars(panel["S00"][1], idx)
    times = list(idx[n // 2::41])
    monkeypatch.setattr(fsg, "get_family_func", lambda name: _fake_base(times))
    need = fsg.live_h1_bars("sync_gated")
    assert need is not None and need < n - 1000
    full, live = _edge_decisions(fsg.family_sync_gated, df, times, need, every=3,
                                 base_family="trend_ma_cross")
    assert full == live and any(full) and not all(full)
    # and the 400-bar read the gateway used to make does NOT reproduce it
    _f, short = _edge_decisions(fsg.family_sync_gated, df, times, fsg.BASE_H1_BARS, every=3,
                                base_family="trend_ma_cross")
    assert short != full
