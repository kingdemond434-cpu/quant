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
    need = fsg.live_h1_bars("markov_vol_gated", {**params, "base_family": "trend_ma_cross"})
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
    need = fsg.live_h1_bars("rough_vol_gated", {"base_family": "mean_reversion_rsi"})
    assert need is not None and need < len(idx) - 1000
    full, live = _edge_decisions(fsg.family_rough_vol_gated, df, times, need, every=8,
                                 base_family="mean_reversion_rsi")
    assert full == live and any(full) and not all(full)


def test_fisher_gate_decides_the_same_on_the_live_read(monkeypatch) -> None:
    idx = _weekday_index(840)
    df = _bars(_close(len(idx), 7), idx)
    times = list(idx[-3000::17])
    monkeypatch.setattr(fsg, "get_family_func", lambda name: _fake_base(times))
    need = fsg.live_h1_bars("fisher_rao_gated", {"base_family": "trend_ma_cross"})
    assert need is not None and need < len(idx) - 1000
    full, live = _edge_decisions(fsg.family_fisher_rao_gated, df, times, need,
                                 base_family="trend_ma_cross")
    assert full == live and any(full) and not all(full)


def test_entropy_gate_decides_the_same_on_the_live_read(monkeypatch) -> None:
    idx = _weekday_index(200)
    df = _bars(_close(len(idx), 9), idx)
    times = list(idx[2500::7])
    monkeypatch.setattr(fsg, "get_family_func", lambda name: _fake_base(times))
    need = fsg.live_h1_bars("entropy_gated", {"base_family": "trend_ma_cross"})
    assert need is not None and need < len(idx) - 500
    full, live = _edge_decisions(fsg.family_entropy_gated, df, times, need,
                                 base_family="trend_ma_cross", threshold=0.0)
    assert full == live and any(full) and not all(full)


# ------------------------------------------------- (c) REAL bases on REAL bars (audit of #403) ---
UNIVERSE = _DESK / "data" / "universe"


def _real(symbol: str) -> pd.DataFrame:
    path = UNIVERSE / f"{symbol}_H1.parquet"
    if not path.exists():
        pytest.skip(f"no {symbol} bars on this host")
    d = pd.read_parquet(path)
    return d.sort_index()


def _real_bases() -> list[str]:
    import state_gate_proposer as sgp
    return sorted({b for w in fsg.STATE_GATE_FAMILIES for b in sgp.bases_for(w)})


OWN_BAR_WRAPPERS = ("fisher_rao_gated", "markov_vol_gated", "rough_vol_gated", "entropy_gated")


@pytest.mark.parametrize("symbol", ["EURUSD", "BTCUSD"])
@pytest.mark.parametrize("wrapper", OWN_BAR_WRAPPERS)
def test_every_real_base_decides_the_same_on_the_live_read(wrapper: str, symbol: str) -> None:
    """Must-fix 1: the synthetic base above hid a base family whose own warm-up outran 400 bars.
    Here every base the proposer can wrap runs on real bars, and at eight frame ends over the
    last 200 days the wrapper keeps exactly the same last signal on the full history as on the
    `live_h1_bars` read alone -- the read the gateway now fetches."""
    import state_gate_proposer as sgp
    full = _real(symbol)
    fn = fsg.STATE_GATE_FAMILIES[wrapper]
    params = {k: v for k, v in sgp.DEFAULTS[wrapper].items()}
    checked = kept = 0
    for base in sgp.bases_for(wrapper):
        need = fsg.live_h1_bars(wrapper, {"base_family": base, **params})
        assert need is not None, (wrapper, base)
        _d, sigs = fsg.base_signals(full, base, {})
        times = sorted({pd.Timestamp(x.time) for x in sigs
                        if pd.Timestamp(x.time) >= full.index[-1] - pd.Timedelta(days=200)})
        for t_end in times[:: max(1, len(times) // 8)][:8]:
            upto = full.loc[:t_end]
            a = t_end in {x.time for x in fn(upto, base_family=base, **params)}
            b = t_end in {x.time for x in fn(upto.iloc[-need:], base_family=base, **params)}
            assert a == b, (wrapper, base, symbol, str(t_end))
            checked += 1
            kept += a
    assert checked >= 20


def test_the_recorded_base_reads_are_the_measured_ones() -> None:
    """state_gate_base_reads.json changes what the gateway reads, so it must be what the
    measurement says TODAY: re-measured here, on the same real bars, and compared."""
    import state_gate_base_parity as sgbp
    if not all((UNIVERSE / f"{s}_H1.parquet").exists() for s in sgbp.SYMBOLS):
        pytest.skip("reference bars absent on this host")
    now = sgbp.measure()
    rec = fsg.base_reads()
    assert now["status"] == rec.get("status") == "MEASURED"
    assert now["bases"] == rec["bases"]
    assert sorted(rec["bases"]) == _real_bases()
    assert rec["rank_span_days"] == fsg.RANK_SPAN_DAYS


def test_a_base_without_a_measured_read_is_refused_by_name() -> None:
    """multi_speed_trend kept 16 signals on the full frame and 0 on a 400-bar read: a base the
    measurement does not cover is never traded on a read it was not proven on."""
    ex = pytest.importorskip("mt5desk.executables")
    p = {"base_family": "multi_speed_trend"}
    why = fsg.live_refusal("fisher_rao_gated", p)
    assert why and "multi_speed_trend" in why
    assert fsg.live_h1_bars("fisher_rao_gated", p) is None
    assert ex.state_gate_gap("fisher_rao_gated", p) == why
    assert fsg.live_refusal("fisher_rao_gated", {"base_family": "trend_ma_cross",
                                                 "base_params": {"fast": 3}})
    for base in _real_bases():
        assert ex.state_gate_gap("fisher_rao_gated", {"base_family": base}) is None
    assert ex.state_gate_gap("trend_ma_cross", {}) is None       # not a wrapper: untouched


def test_the_promoter_asks_the_state_gate_question() -> None:
    import promoter
    assert promoter._state_gate_gap("fisher_rao_gated", {"base_family": "multi_speed_trend"})
    assert promoter._state_gate_gap("fisher_rao_gated", {"base_family": "trend_ma_cross"}) is None
    assert promoter._state_gate_gap("session_range_breakout", {}) is None
    src = (_DESK / "research" / "promoter.py").read_text("utf-8")
    assert src.count("_state_gate_gap(family,") == 2      # both promotion paths


# ------------------------------------------------------------------- (d) the gateway's read ---
def test_every_wrapper_declares_its_live_read() -> None:
    for fam in fsg.STATE_GATE_FAMILIES:
        need = fsg.live_h1_bars(fam, {"base_family": "trend_ma_cross"})
        assert isinstance(need, int) and need > fsg.BASE_H1_BARS, fam
    assert fsg.live_h1_bars("trend_ma_cross") is None
    # A certificate's own params move its read: a longer fit window needs more bars.
    base = {"base_family": "trend_ma_cross"}
    assert fsg.live_h1_bars("markov_vol_gated", {**base, "fit_window": 3000}) \
        == fsg.live_h1_bars("markov_vol_gated", base) + 1000


_GATEWAY_PROBE = """
import sys, types, json
sys.path[:0] = [sys.argv[1], sys.argv[2]]
from unittest import mock
import numpy as np
stub = types.ModuleType("MetaTrader5")
stub.__getattr__ = lambda name: mock.MagicMock(name="MetaTrader5." + name)
sys.modules["MetaTrader5"] = stub
import mt5desk.gateway as gw
from mt5desk import family_state_gates as fsg
out = {}
base = {"base_family": "trend_ma_cross"}
p = {**base, "fit_window": 2000, "refit": 168}
out["chart"] = list(gw._family_chart({"family": "markov_vol_gated", "params": p}))[::2]
out["want"] = fsg.live_h1_bars("markov_vol_gated", p)
out["other"] = gw._family_chart({"family": "trend_ma_cross", "params": {}})[2]
# MUST-FIX 3: a LOSSY row (chart only) is sized from the certificate's recovered params.
rec = {**base, "fit_window": 3000, "refit": 168, "timeframe": "H1"}
gw._params_match_certificate = lambda s, f, pr: False
gw._params_from_certificate = lambda s: (rec, "")
out["lossy"] = gw._state_gate_bars({"family": "markov_vol_gated", "params": {"timeframe": "H1"}})
out["lossy_want"] = fsg.live_h1_bars("markov_vol_gated", rec)
gw._params_match_certificate = lambda s, f, pr: True
out["unmeasured"] = gw._state_gate_bars({"family": "fisher_rao_gated",
                                         "params": {"base_family": "multi_speed_trend"}})
# MUST-FIX 2: the panel store is checked against the terminal's last CLOSED bar.
H = 3600 * 10**9
st = np.arange(100, dtype="int64") * H
panel = {"AAA": (st, np.ones(100)), "BBB": (st[:-2], np.ones(98))}
fsg.load_panel = lambda: panel
def rates(sym, tf, pos, n):
    t = np.array([(99 * 3600,), (100 * 3600,)], dtype=[("time", "i8")])
    return None if sym == "NONE" else t
stub.copy_rates_from_pos = rates
D = 99 * H                                   # the decision bar: the traded symbol's closed bar
out["lag"] = gw._panel_store_lag({"family": "sync_gated"}, D)
panel.pop("BBB")
out["current"] = gw._panel_store_lag({"family": "sync_gated"}, D)
out["own_bars"] = gw._panel_store_lag({"family": "fisher_rao_gated"}, D)
# MUST-FIX 1 (5341bfe53): a member whose market closed at 90h has a final, CLOSED bar at 90h that
# refresh_tail dropped; its [-2] (89h) is in the store, and the old check passed that read.
panel["CLOSED"] = (np.arange(90, dtype="int64") * H, np.ones(90))
def closed_rates(sym, tf, pos, n):
    if sym == "CLOSED":
        return np.array([(89 * 3600,), (90 * 3600,)], dtype=[("time", "i8")])
    return rates(sym, tf, pos, n)
stub.copy_rates_from_pos = closed_rates
out["weekend"] = gw._panel_store_lag({"family": "sync_gated"}, D)
panel.clear()
out["empty"] = gw._panel_store_lag({"family": "sync_gated"}, D)
print(json.dumps(out, default=str))
"""


def test_the_gateway_reads_what_the_certificate_needs() -> None:
    """Against the real gateway module with the terminal stubbed, in a subprocess so the stub
    never leaks: the chart read, a lossy row sized off its certificate, an unmeasured base
    refused, and the panel store checked against the terminal."""
    import json
    import subprocess
    proc = subprocess.run([sys.executable, "-c", _GATEWAY_PROBE, str(_ROOT), str(_DESK)],
                          cwd=str(_ROOT), capture_output=True, text=True, timeout=300,
                          check=False)
    assert proc.returncode == 0, proc.stderr[-3000:]
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    assert out["chart"][0] == "H1" and out["chart"][1] == out["want"] > 400
    assert out["other"] == 400                       # every other family's read is unchanged
    assert out["lossy"] == [True, out["lossy_want"], ""]
    assert out["lossy_want"] == out["want"] + 1000
    is_gate, need, why = out["unmeasured"]
    assert is_gate and need is None and "multi_speed_trend" in why
    assert out["lag"] and "BBB(2h)" in out["lag"] and "1 of 2" in out["lag"]
    assert out["current"] is None and out["own_bars"] is None
    assert out["weekend"] and "CLOSED(1h)" in out["weekend"]
    assert out["empty"] and "UNMEASURED" in out["empty"]


def test_the_gateway_refuses_by_name_and_never_shrinks_the_read() -> None:
    src = (_DESK / "mt5desk" / "gateway.py").read_text("utf-8")
    for stage in ('"not_live_reproducible"', '"short_history"', '"panel_store_lag"'):
        assert stage in src, stage
        # every refusal is journalled, so the wait is priced rather than silent (5341bfe53 MF2)
        assert f"journal_refusal(name, s[\"symbol\"], side, {stage}" in src, stage
    assert "len(h1) < gate_need" in src
    tree = ast.parse(src)
    fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    call = ast.get_source_segment(src, fns["_family_call_params"]) or ""
    gate = ast.get_source_segment(src, fns["_state_gate_bars"]) or ""
    assert "_resolved_family_params(s, family)" in call
    assert "_resolved_family_params(s, fam)" in gate


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
    need = fsg.live_h1_bars("sync_gated", {"base_family": "trend_ma_cross"})
    assert need is not None and need < n - 1000
    full, live = _edge_decisions(fsg.family_sync_gated, df, times, need, every=3,
                                 base_family="trend_ma_cross")
    assert full == live and any(full) and not all(full)
    # and the 400-bar read the gateway used to make does NOT reproduce it
    _f, short = _edge_decisions(fsg.family_sync_gated, df, times, fsg.BASE_H1_BARS, every=3,
                                base_family="trend_ma_cross")
    assert short != full
