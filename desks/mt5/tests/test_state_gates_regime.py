"""THE VOLATILITY-MODEL STATE GATES on synthetic data: the 2-state Markov-switching variance
model (recovery, label order, degenerate fits, the filtered probability's point-in-time read
across a refit boundary) and the roughness H of daily realised variance (recovery on exact
fractional Gaussian noise, complete days only, a day counted once its last slot has printed),
the mechanism-fixed tail per class and the proposer's grid.

The base-family lookup is monkeypatched, so nothing here reads the desk's own bar store or
writes its reports. The proposer test reuses test_state_gates' `_two_symbol_proposer`, which
writes real contract files: the charged set is read off them.
"""
from __future__ import annotations

import json
import math
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

import test_state_gates as base_tests  # noqa: E402
from mt5desk import family_state_gates as fsg  # noqa: E402
from mt5desk.families import Signal  # noqa: E402

T0 = pd.Timestamp("2026-01-05 00:00", tz="UTC")
HOUR = 3600 * 10**9
#: Small settings so the brute-force tests stay fast; the defaults are exercised elsewhere.
MS_FAST = {"fit_window": 400, "refit": 168, "max_iter": 60}


def _stamps(n: int) -> pd.DatetimeIndex:
    return pd.date_range(T0, periods=n, freq="h").as_unit("ns")


def _bars(close: np.ndarray, index: pd.DatetimeIndex | None = None) -> pd.DataFrame:
    idx = _stamps(len(close)) if index is None else index
    return pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999,
                         "close": close, "tick_volume": 1.0}, index=idx)


def _fake_base(times: list[pd.Timestamp]):
    def fn(d: pd.DataFrame, **_kw) -> list[Signal]:
        return [Signal(time=t, side=1, stop=0.9, target=1.2, ttl_bars=12, tag="fake")
                for t in times if t in d.index]
    return fn


def _two_state(n: int, *, sd=(0.001, 0.003), stay=(0.99, 0.97), seed: int = 0):
    rng = np.random.default_rng(seed)
    s = np.zeros(n, dtype=int)
    u = rng.random(n)
    for t in range(1, n):
        s[t] = s[t - 1] if u[t] < stay[s[t - 1]] else 1 - s[t - 1]
    return rng.normal(0.0, 1.0, n) * np.where(s == 1, sd[1], sd[0]), s


def _close_from(r: np.ndarray) -> np.ndarray:
    return np.exp(np.concatenate([[0.0], np.cumsum(r)]))


# ------------------------------------------------------------- (a) Markov-switching variance ---
def test_a_two_state_process_is_recovered() -> None:
    x, s = _two_state(8000, seed=3)
    th = fsg.ms_fit(x[None, :])[0]
    mu0, mu1, v0, v1, a00, a11 = th
    assert abs(mu0) < 1e-4 and abs(mu1) < 3e-4                   # state means near 0
    assert math.sqrt(v0) == pytest.approx(0.001, rel=0.06)
    assert math.sqrt(v1) == pytest.approx(0.003, rel=0.06)
    assert a00 == pytest.approx(0.99, abs=0.01) and a11 == pytest.approx(0.97, abs=0.02)
    # The filtered regime reads the true one on most bars.
    lo = fsg.ms_filter_logodds(x, th)
    assert ((lo > 0) == (s == 1)).mean() > 0.9


def test_states_are_always_ordered_by_variance(monkeypatch) -> None:
    for seed in range(4):
        x, _ = _two_state(3000, seed=seed)
        th = fsg.ms_fit(np.vstack([x, x[::-1], -x]))
        assert np.all(th[:, 2] < th[:, 3])
    # An EM that lands on the swapped labelling is reordered, transition probabilities with it.
    real = fsg._ms_em_step

    def swapped(x, th, floor):
        new, ll = real(x, th, floor)
        return new[:, [1, 0, 3, 2, 5, 4]], ll

    monkeypatch.setattr(fsg, "_ms_em_step", swapped)
    x, _ = _two_state(3000, seed=1)
    th = fsg.ms_fit(x[None, :], max_iter=7)[0]
    assert th[2] < th[3]
    monkeypatch.setattr(fsg, "_ms_em_step", real)
    ref = fsg.ms_fit(x[None, :], max_iter=7)[0]
    assert np.allclose(np.sort(th[2:4]), np.sort(ref[2:4]), rtol=1e-6)


def test_degenerate_windows_are_refused() -> None:
    assert np.isnan(fsg.ms_fit(np.zeros((1, 500)))).all()           # flat: no fit
    x, _ = _two_state(500, seed=2)
    holed = x.copy()
    holed[10] = np.nan
    assert np.isnan(fsg.ms_fit(holed[None, :])).all()               # unreadable: no fit
    # Mostly zero returns with a few moves: the calm state collapses onto its variance floor.
    # That is a stalled feed, not a regime -- NO FIT (audit M-2), never a floored finite one
    # whose likelihood ratio reads 1e6 after the next move.
    sparse = np.zeros(1000)
    sparse[::50] = np.random.default_rng(0).normal(0, 0.01, 20)
    assert np.isnan(fsg.ms_fit(sparse[None, :])).all()
    # A real two-state window with ~10% stalls mixed in is refused the same way when (and only
    # when) its calm state lands on the floor; a clean one keeps its stay probabilities inside.
    x, _ = _two_state(2000, seed=12)
    stalled = x.copy()
    stalled[np.random.default_rng(1).random(2000) < 0.10] = 0.0
    th = fsg.ms_fit(np.vstack([x, stalled]))
    assert np.isfinite(th[0]).all()
    assert fsg.MS_P_MIN <= th[0, 4] <= 1 - fsg.MS_P_MIN
    floor = fsg.MS_VAR_FLOOR * stalled.var()
    assert np.isnan(th[1]).all() or th[1, 2] > floor * (1 + 1e-6)
    lo = fsg.ms_filter_logodds(stalled, th[1]) if np.isfinite(th[1]).all() else np.zeros(1)
    assert np.nanmax(np.abs(lo)) < 1e3                 # never the 7e3..1e6 of a floored fit


def test_a_row_fit_does_not_depend_on_its_batch() -> None:
    xs_ = [_two_state(600, seed=k)[0] for k in range(5)]
    together = fsg.ms_fit(np.vstack(xs_))
    for k, x in enumerate(xs_):
        assert np.allclose(fsg.ms_fit(x[None, :])[0], together[k], rtol=1e-10, atol=1e-15)


def test_the_filter_is_the_hamilton_filter_not_the_smoother() -> None:
    """Brute force in linear space: alpha_t = (alpha_{t-1} A) * f(x_t), normalised; the gate's
    log-odds is log(alpha_t[high] / alpha_t[low]) -- no data after t enters."""
    x, _ = _two_state(300, seed=5)
    th = fsg.ms_fit(x[None, :])[0]
    mu, var, a00, a11 = th[:2], th[2:4], th[4], th[5]
    A = np.array([[a00, 1 - a00], [1 - a11, a11]])
    pi1 = (1 - a00) / (2 - a00 - a11)
    pred = np.array([1 - pi1, pi1])
    lo = fsg.ms_filter_logodds(x, th)
    for t in range(len(x)):
        dens = np.exp(-0.5 * (x[t] - mu) ** 2 / var) / np.sqrt(2 * np.pi * var)
        filt = pred * dens / (pred * dens).sum()
        assert lo[t] == pytest.approx(math.log(filt[1] / filt[0]), rel=1e-7, abs=1e-7)
        pred = filt @ A


def test_the_filtered_probability_is_point_in_time_across_a_refit_boundary() -> None:
    x, _ = _two_state(1500, seed=7)
    close = _close_from(x)
    k, w = MS_FAST["refit"], MS_FAST["fit_window"]
    # T0 is a Monday 00:00 UTC; the grid instants are Saturday 00:00 UTC, i.e. bar 120 + 168 m.
    g = 120 + 3 * k                                   # 624: g - 1 still reads the full fit at 456
    assert g >= w and fsg.ms_grid_bars(_stamps(1500).asi8, [g, g - 1])[0] == g
    pos = np.array([w - 1, g - 1, g, g + 1, g + k - 1, g + k, 1400])
    full = fsg.markov_vol_state(_stamps(len(close)), close, pos, **MS_FAST)
    assert np.isnan(full[0]) and np.all(np.isfinite(full[1:]))
    for p, v in zip(pos[1:], full[1:], strict=True):
        cut = fsg.markov_vol_state(_stamps(p + 1), close[: p + 1], [p], **MS_FAST)
        assert cut[0] == pytest.approx(v, abs=1e-10)
        shocked = close.copy()
        shocked[p + 1:] *= np.exp(np.random.default_rng(int(p)).normal(0, 0.05,
                                                                       len(close) - p - 1))
        fsg._MS_MEMO.clear()
        assert fsg.markov_vol_state(_stamps(len(shocked)), shocked, [p], **MS_FAST)[0] == pytest.approx(v, abs=1e-10)
    # Bar g - 1 reads the fit of the PREVIOUS grid point, bar g its own: a return at bar g moves
    # the reading at g and never the one at g - 1.
    moved = close.copy()
    moved[g:] *= 1.02
    after = fsg.markov_vol_state(_stamps(len(moved)), moved, [g - 1, g], **MS_FAST)
    assert after[0] == pytest.approx(full[1], abs=1e-10) and after[1] != pytest.approx(full[2])


# ----------------------------------------------------------------- (b) rough volatility (H) ---
def _fgn(h: float, n: int, seed: int) -> np.ndarray:
    """Exact fractional Gaussian noise by the Cholesky factor of its Toeplitz covariance."""
    k = np.arange(n, dtype="float64")
    gam = 0.5 * ((k + 1) ** (2 * h) - 2 * k ** (2 * h) + np.abs(k - 1) ** (2 * h))
    cov = gam[np.abs(np.subtract.outer(np.arange(n), np.arange(n)))]
    return np.linalg.cholesky(cov) @ np.random.default_rng(seed).normal(size=n)


@pytest.mark.parametrize("h", [0.1, 0.5])
def test_h_is_recovered_from_an_exact_fbm_log_vol(h: float) -> None:
    long = [fsg.hurst_of_log_rv(np.cumsum(_fgn(h, 1000, s)), window=1000)[-1] for s in range(4)]
    assert float(np.mean(long)) == pytest.approx(h, abs=0.04)
    # At the registered 250-day window each read is noisier but centred on H.
    at250 = fsg.hurst_of_log_rv(np.cumsum(_fgn(h, 1000, 11)), window=250)
    assert float(np.nanmean(at250)) == pytest.approx(h, abs=0.06)


def _daily_bars(log_sigma: np.ndarray, *, per_day: int = 24, seed: int = 0):
    """H1 bars whose day d has volatility exp(log_sigma[d]): returns sigma_d / sqrt(per_day) * z."""
    rng = np.random.default_rng(seed)
    days = pd.date_range(T0, periods=len(log_sigma), freq="D")
    idx = pd.DatetimeIndex(np.concatenate(
        [(d + pd.to_timedelta(np.arange(per_day), unit="h")).as_unit("ns").asi8 for d in days]),
        tz="UTC")
    sd = np.repeat(np.exp(log_sigma) / math.sqrt(per_day), per_day)
    return idx, _close_from(rng.normal(size=len(idx) - 1) * sd[1:])


def test_rough_and_persistent_log_vol_read_apart_through_h1_bars() -> None:
    reads = {}
    for h in (0.1, 0.5):
        x = 0.3 * np.cumsum(_fgn(h, 300, 3))
        idx, close = _daily_bars(np.log(0.004) + x - x.mean())
        out = fsg.rough_vol_state(idx, close, [int(idx[-1].value)])
        assert np.isfinite(out[0])
        reads[h] = float(out[0])
    assert reads[0.1] < reads[0.5] - 0.15


def test_an_incomplete_day_is_excluded() -> None:
    idx, close = _daily_bars(np.full(40, np.log(0.006)), seed=1)
    keep = np.ones(len(idx), dtype=bool)
    day = idx.as_unit("ns").asi8 // (24 * HOUR)
    short_day = day[24 * 10]
    keep[(day == short_day) & (np.arange(len(idx)) % 24 >= 6)] = False   # day 10: 6 bars of 24
    days, rv = fsg.daily_realised_variance(idx[keep], close[keep])
    got = set((days // (24 * HOUR)).tolist())
    assert short_day not in got
    assert int(day[0]) not in got                    # the file's first day has no first return
    assert len(got) == 40 - 2 and np.all(rv > 0)
    # A nine-hour session is judged against its own sessions: every full one is complete.
    nine = np.ones(len(idx), dtype=bool)
    nine[np.arange(len(idx)) % 24 >= 9] = False
    days9, _ = fsg.daily_realised_variance(idx[nine], close[nine])
    assert len(days9) == 40 - 1


def test_a_day_counts_only_once_its_last_slot_has_printed() -> None:
    rng = np.random.default_rng(4)
    idx, close = _daily_bars(np.log(0.006) + 0.5 * np.cumsum(rng.normal(0, 0.3, 80)), seed=2)
    kw = {"window": 30, "max_lag": 5}
    days, rv = fsg.daily_realised_variance(idx, close)
    h = fsg.hurst_of_log_rv(np.log(rv), **kw)
    d50 = int(days[49])                                # the 50th complete day
    noon, last = d50 + 12 * HOUR, d50 + 23 * HOUR
    got = fsg.rough_vol_state(idx, close, [noon, last], **kw)
    assert got[0] == pytest.approx(h[48]) and got[1] == pytest.approx(h[49])
    for t in (noon, last):                             # and truncation after t changes nothing
        cut = idx.as_unit("ns").asi8 <= t
        assert fsg.rough_vol_state(idx[cut], close[cut], [t], **kw)[0] == pytest.approx(
            fsg.rough_vol_state(idx, close, [t], **kw)[0], abs=1e-12)


# --------------------------------------------------------------- (c) the tail fixed by class ---
def _brute(states: list[float], high: bool, q: float = 1 / 3, need: int = 30) -> list[int]:
    out = []
    for k in range(need, len(states)):
        below = sum(1 for h in states[:k] if h < states[k]) / k
        if (below >= 1 - q) if high else (below <= q):
            out.append(k)
    return out


BASES = ["trend_ma_cross", "session_range_breakout", "mean_reversion_rsi"]


@pytest.mark.parametrize("base", BASES)
def test_markov_gate_keeps_its_class_tail_by_brute_force(monkeypatch, base) -> None:
    x, _ = _two_state(3000, seed=8)
    close = _close_from(x)
    idx = _stamps(len(close))
    pos = list(range(120 + 2 * MS_FAST["refit"], len(close), 37))   # 456: the first full fit
    times = [idx[p] for p in pos]
    monkeypatch.setattr(fsg, "get_family_func", lambda name: _fake_base(times))
    kept = [s.time for s in fsg.family_markov_vol_gated(_bars(close), base_family=base,
                                                        **MS_FAST)]
    st = [float(fsg.markov_vol_state(_stamps(p + 1), close[: p + 1], [p], **MS_FAST)[0]) for p in pos]
    assert np.all(np.isfinite(st))
    # trend/breakout keep the BOTTOM tail (calm), reversion the TOP tail (high variance)
    top = fsg.mechanism_class(base) in fsg.SYNC_LOW
    expect = [times[k] for k in _brute(st, high=top)]
    assert kept == expect and 0 < len(kept) < len(times) // 2


@pytest.mark.parametrize("base", BASES)
def test_rough_gate_keeps_its_class_tail_by_brute_force(monkeypatch, base) -> None:
    x = 0.5 * np.cumsum(_fgn(0.3, 420, 6))
    idx, close = _daily_bars(np.log(0.004) + x - x.mean(), seed=6)
    pos = list(range(24 * 260 + 5, len(close), 29))
    times = [idx[p] for p in pos]
    monkeypatch.setattr(fsg, "get_family_func", lambda name: _fake_base(times))
    kept = [s.time for s in fsg.family_rough_vol_gated(_bars(close, idx), base_family=base)]
    st = []
    for p in pos:
        t = int(idx[p].value)
        st.append(float(fsg.rough_vol_state(idx[: p + 1], close[: p + 1], [t])[0]))
    assert np.all(np.isfinite(st))
    # trend/breakout keep the TOP tail of H (persistent), reversion the BOTTOM (rough)
    top = fsg.mechanism_class(base) in fsg.SYNC_HIGH
    expect = [times[k] for k in _brute(st, high=top)]
    assert kept == expect and 0 < len(kept) < len(times) - 30


def test_other_classes_and_wrappers_return_nothing(monkeypatch) -> None:
    x, _ = _two_state(3000, seed=9)
    close = _close_from(x)
    idx = _stamps(len(close))
    monkeypatch.setattr(fsg, "get_family_func", lambda name: _fake_base([idx[2900]]))
    bars = _bars(close)
    for fn in (fsg.family_markov_vol_gated, fsg.family_rough_vol_gated):
        assert fn(bars, base_family="dow_effect") == []
        for inner in ("markov_vol_gated", "rough_vol_gated", "sync_gated"):
            assert fn(bars, base_family=inner) == []


# ---------------------------------------------------------------------- (d) the proposer ---
def test_proposer_mints_each_cell_once_including_crypto(monkeypatch, tmp_path) -> None:
    P, _, charged = base_tests._two_symbol_proposer(monkeypatch, tmp_path)
    syms = ["BTCUSD", "EURUSD", "XAUUSD"]
    monkeypatch.setattr(P, "store_symbols", lambda: syms)
    monkeypatch.setattr(P, "sync_applies", lambda sym: sym != "BTCUSD")
    monkeypatch.setattr(P, "MINT_ROWS_PER_PASS", 1500)
    grid, refused = P.build_grid(syms)
    keys = [(c["family"], c["params"]["base_family"], c["symbol"]) for c in grid]
    assert len(keys) == len(set(keys))
    for w in ("markov_vol_gated", "rough_vol_gated"):
        assert w in P.WRAPPERS and w in P.CLASS_DIRECTED and w not in P.PANEL_WRAPPERS
        assert P.bases_for(w) == P.bases_for("sync_gated")
        mine = [k for k in keys if k[0] == w]
        assert len(mine) == len(P.bases_for(w)) * len(syms)        # minted on crypto too
        assert len([k for k in mine if k[2] == "BTCUSD"]) == len(P.bases_for(w))
        for c in grid:
            if c["family"] == w:
                assert {k: c["params"][k] for k in P.DEFAULTS[w]} == P.DEFAULTS[w]
                assert c["falsifier"] and c["params"]["base_params"] == {}
        assert not any(r.startswith(w) for r in refused)
    expect = sum(len(P.bases_for(w)) * (len(syms) - (w in P.PANEL_WRAPPERS))
                 for w in P.WRAPPERS)
    assert len(grid) == expect

    for _ in range(3):
        assert P.main(["--once"]) == 0
    assert charged == [len(grid)]                  # one charge, on the first pass only
    rows = []
    for f in sorted((tmp_path / "intel").glob("discoveries_*.json")):
        rows += json.loads(f.read_text("utf-8"))["discoveries"]
    assert sorted(P.cell_key(r) for r in rows) == sorted(P.cell_key(c) for c in grid)
    charged_set, bad = P.charged_cells(tmp_path / "intel")
    assert not bad and charged_set == {P.cell_key(c) for c in grid}


def test_regime_families_are_registered_where_the_gauntlet_looks() -> None:
    from mt5desk.families_orthogonal import FAMILY_INPUTS, FAMILY_TIMEFRAMES, ORTHOGONAL_FAMILIES
    from mt5desk.family_alt_series import _UNWRAPPABLE
    from research.axis_registry import FAMILY_TABLE
    from research.orthogonal_sweep import NOT_SOURCED_HERE

    from research import alpha_genome as ag
    for fam in ("markov_vol_gated", "rough_vol_gated"):
        assert fam in ORTHOGONAL_FAMILIES and fam in FAMILY_INPUTS and fam in FAMILY_TABLE
        assert fam in _UNWRAPPABLE and fam in NOT_SOURCED_HERE
        assert FAMILY_TIMEFRAMES[fam][0] == ("H1",)
        assert ag.MECHANISM_CLASS[fam] == "regime"


# ------------------------------------------------------------------- audit of #399 (c19611bf9) ---
def test_the_refit_grid_is_anchored_to_time_not_to_the_frame() -> None:
    """M-1: cutting leading bars re-phased a frame-counted grid (0% of states identical after a
    1-bar cut). On the time grid, every reading whose fit window still fits inside the cut frame
    is BITWISE identical, whatever the cut."""
    x, _ = _two_state(3000, seed=21)
    close = _close_from(x)
    idx = _stamps(len(close))
    pos = np.arange(900, len(close), 7)
    full = fsg.markov_vol_state(idx, close, pos, **MS_FAST)
    assert np.isfinite(full).mean() > 0.95
    for cut in (1, 37, 100, 168, 400):
        fsg._MS_MEMO.clear()
        got = fsg.markov_vol_state(idx[cut:], close[cut:], pos - cut, **MS_FAST)
        both = np.isfinite(got)
        assert both.mean() > 0.8, cut
        assert np.array_equal(got[both], full[both]), cut
        # and a reading the cut frame cannot hold is NaN, never a re-phased number
        g = fsg.ms_grid_bars(idx.asi8, pos)
        assert np.all(~both[g - cut < MS_FAST["fit_window"]])


def test_the_grid_follows_stamps_across_a_gap() -> None:
    """A weekend gap or a missing day moves bar COUNTS, never the grid instant."""
    idx = _stamps(2000)
    holed = idx.delete(np.arange(300, 340))           # 40 bars missing mid-file
    g_full = fsg.ms_grid_bars(idx.asi8, [1900])[0]
    g_holed = fsg.ms_grid_bars(holed.asi8, [1860])[0]
    assert idx[g_full] == holed[g_holed]


def test_the_fit_memo_holds_a_digest_not_the_window() -> None:
    """SF-2: 50,000 keys of a raw 16 KB window were ~800 MB."""
    fsg._MS_MEMO.clear()
    x, _ = _two_state(1200, seed=22)
    close = _close_from(x)
    fsg.markov_vol_state(_stamps(len(close)), close, [1100], **MS_FAST)
    assert fsg._MS_MEMO
    for key in fsg._MS_MEMO:
        assert isinstance(key[0], bytes) and len(key[0]) == 16


def test_a_stalled_day_is_not_a_day_of_variance() -> None:
    """SF-1: a day of unchanged closes but one tick read log RV -41 and moved H."""
    idx, close = _daily_bars(np.full(40, np.log(0.006)), seed=23)
    day = idx.as_unit("ns").asi8 // (24 * HOUR)
    stalled = close.copy()
    d = day[24 * 12]
    rows = np.flatnonzero(day == d)
    stalled[rows[1:]] = stalled[rows[0]]              # every return of day 12 after its first is 0
    stalled[rows[-1] + 1:] *= stalled[rows[0]] / close[rows[-1]]
    days, _ = fsg.daily_realised_variance(idx, stalled)
    assert d not in set((days // (24 * HOUR)).tolist())
    assert len(days) == 40 - 2


def test_the_h1_only_wrappers_refuse_another_chart(monkeypatch) -> None:
    """SF-4: the hour-counted grid and the 23:00 day close hold only on H1."""
    x, _ = _two_state(3000, seed=24)
    close = _close_from(x)
    m15 = pd.date_range(T0, periods=len(close), freq="15min").as_unit("ns")
    monkeypatch.setattr(fsg, "get_family_func", lambda name: _fake_base(list(m15[2000::50])))
    bars = _bars(close, m15)
    assert not fsg.is_h1(m15) and fsg.is_h1(_stamps(50))
    for fn in (fsg.family_markov_vol_gated, fsg.family_rough_vol_gated):
        assert fn(bars, base_family="trend_ma_cross") == []


def test_no_state_gate_is_live_executable_until_its_history_is() -> None:
    """SF-3: the gateway reads 400 H1 bars; every wrapper ranks against the whole frame's earlier
    signals. A certificate would trade a gate it was not certified on, so the promoter's own
    boundary names why instead of writing a LIVE row the gateway cannot reproduce."""
    ex = pytest.importorskip("mt5desk.executables")
    for fam in fsg.STATE_GATE_FAMILIES:
        assert ex.population_of(fam) == "orthogonal"
        gap = ex.executor_gap(fam)
        assert gap == fsg.LIVE_READ_GAP and "400 H1" in gap
        assert not ex.gateway_can_execute(fam)
    # The reason quotes the gateway's own read: if that literal moves, this refusal is re-judged.
    import ast
    tree = ast.parse((_DESK / "mt5desk" / "gateway.py").read_text("utf-8"))
    bars = [ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
            and any(getattr(t, "id", "") == "_FAMILY_H1_BARS" for t in n.targets)]
    assert bars == [400]
