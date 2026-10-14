"""THE GEOMETRY STATE GATES on synthetic data: the Student-t Fisher-Rao distance (checked against
the Fisher metric integrated numerically), the absorption ratio and its standardised shift, their
point-in-time reads, the mechanism-fixed tail per class and the proposer's grid.

The panel loader and the base-family lookup are monkeypatched, so nothing here reads the desk's
own bar store or writes its reports. The proposer tests reuse test_state_gates' `_contracting`
and `_two_symbol_proposer`, which write real contract files: the charged set is read off them.
"""
from __future__ import annotations

import json
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


def _stamps(n: int) -> pd.DatetimeIndex:
    return pd.date_range(T0, periods=n, freq="h").as_unit("ns")


def _bars(close: np.ndarray) -> pd.DataFrame:
    idx = _stamps(len(close))
    return pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999,
                         "close": close, "tick_volume": 1.0}, index=idx)


def _fake_base(times: list[pd.Timestamp]):
    def fn(d: pd.DataFrame, **_kw) -> list[Signal]:
        return [Signal(time=t, side=1, stop=0.9, target=1.2, ttl_bars=12, tag="fake")
                for t in times if t in d.index]
    return fn


def _panel_from_returns(rets: np.ndarray) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """(T x N) returns -> {symbol: (ns stamps, closes)} on one continuous hourly clock."""
    n = rets.shape[0] + 1
    st = _stamps(n).asi8.astype("int64")
    closes = np.exp(np.vstack([np.zeros(rets.shape[1]), np.cumsum(rets, axis=0)]))
    return {f"S{j:03d}": (st, closes[:, j].astype("float64")) for j in range(rets.shape[1])}


def _factor_panel(n_sym: int, n_bars: int, *, beta: float, seed: int = 0):
    rng = np.random.default_rng(seed)
    f = rng.normal(0, 0.001, (n_bars, 1))
    e = rng.normal(0, 0.001, (n_bars, n_sym))
    # A slow swing in the factor loading so AR moves through time and its sd is not zero.
    swing = 1.0 + 0.8 * np.sin(np.arange(n_bars) / 90.0)[:, None]
    return _panel_from_returns(beta * swing * f + e)


# ------------------------------------------------------------------ (a) Fisher-Rao distance ----
def test_fr_distance_is_zero_on_identical_fits_and_symmetric() -> None:
    assert float(fsg.fisher_rao_t(0.001, 0.01, 0.001, 0.01)) == pytest.approx(0.0, abs=1e-12)
    rng = np.random.default_rng(1)
    for _ in range(20):
        m1, m2 = rng.normal(0, 0.01, 2)
        s1, s2 = rng.uniform(0.001, 0.02, 2)
        assert float(fsg.fisher_rao_t(m1, s1, m2, s2)) == pytest.approx(
            float(fsg.fisher_rao_t(m2, s2, m1, s1)), rel=1e-12)


def test_fr_distance_grows_with_a_mean_or_a_scale_shift() -> None:
    shifts = np.linspace(0.0, 0.05, 11)
    by_mean = fsg.fisher_rao_t(0.0, 0.01, shifts, 0.01)
    by_scale = fsg.fisher_rao_t(0.0, 0.01, 0.0, 0.01 + shifts)
    assert np.all(np.diff(by_mean) > 0) and np.all(np.diff(by_scale) > 0)
    # A pure scale change is sqrt(b) * |log(s2 / s1)| (the vertical geodesic).
    b = 2 * 5.0 / 8.0
    assert float(fsg.fisher_rao_t(0.0, 0.01, 0.0, 0.03)) == pytest.approx(
        np.sqrt(b) * np.log(3.0), rel=1e-12)


def _numeric_fisher_info(nu: float) -> np.ndarray:
    """The 2x2 Fisher information of t_nu(mu, sigma) at (0, 1), integrated numerically from
    finite-difference scores of the log density -- independent of the closed form."""
    from scipy import integrate, stats

    h = 1e-5

    def score(x: float) -> np.ndarray:
        lp = lambda m, s: stats.t.logpdf(x, nu, loc=m, scale=s)  # noqa: E731
        return np.array([(lp(h, 1.0) - lp(-h, 1.0)) / (2 * h),
                         (lp(0.0, 1.0 + h) - lp(0.0, 1.0 - h)) / (2 * h)])

    out = np.zeros((2, 2))
    for i in range(2):
        for j in range(2):
            out[i, j] = integrate.quad(
                lambda x, i=i, j=j: score(x)[i] * score(x)[j] * stats.t.pdf(x, nu),
                -np.inf, np.inf, limit=200)[0]
    return out


@pytest.mark.parametrize("nu", [3.0, 5.0, 12.0])
def test_fr_distance_matches_the_numerically_integrated_metric(nu: float) -> None:
    info = _numeric_fisher_info(nu)
    a, b = (nu + 1) / (nu + 3), 2 * nu / (nu + 3)
    assert info[0, 0] == pytest.approx(a, rel=1e-5)
    assert info[1, 1] == pytest.approx(b, rel=1e-5)
    assert abs(info[0, 1]) < 1e-6

    # Integrate the NUMERIC metric (info / sigma^2) along the half-plane geodesic -- a semicircle
    # centred on the axis in (x, sigma) with x = mu sqrt(a/b) -- and compare with the closed form.
    m1, s1, m2, s2 = -0.02, 0.01, 0.015, 0.025
    k = np.sqrt(a / b)
    x1, x2 = m1 * k, m2 * k
    c = ((x2 ** 2 + s2 ** 2) - (x1 ** 2 + s1 ** 2)) / (2 * (x2 - x1))
    r = np.hypot(x1 - c, s1)
    th = np.linspace(np.arctan2(s1, x1 - c), np.arctan2(s2, x2 - c), 200_001)
    mu, sg = (c + r * np.cos(th)) / k, r * np.sin(th)
    dmu, dsg = np.diff(mu), np.diff(sg)
    smid = 0.5 * (sg[1:] + sg[:-1])
    ds = np.sqrt((info[0, 0] * dmu ** 2 + 2 * info[0, 1] * dmu * dsg + info[1, 1] * dsg ** 2)
                 / smid ** 2)
    numeric = float(ds.sum())
    closed = float(fsg.fisher_rao_t(m1, s1, m2, s2, nu=nu))
    assert numeric == pytest.approx(closed, rel=1e-4)
    # ...and a straight segment between the same two laws is no shorter (it is not a geodesic).
    lin = np.linspace(0, 1, 200_001)
    mu, sg = m1 + (m2 - m1) * lin, s1 + (s2 - s1) * lin
    dmu, dsg, smid = np.diff(mu), np.diff(sg), 0.5 * (sg[1:] + sg[:-1])
    straight = float(np.sqrt((info[0, 0] * dmu ** 2 + info[1, 1] * dsg ** 2) / smid ** 2).sum())
    assert straight > closed


def test_t_fit_recovers_location_and_scale() -> None:
    rng = np.random.default_rng(4)
    x = 0.002 + 0.01 * rng.standard_t(5.0, size=(4, 20_000))
    mu, sg = fsg.t_fit(x, nu=5.0)
    assert np.allclose(mu, 0.002, atol=3e-4) and np.allclose(sg, 0.01, rtol=0.03)
    _, flat = fsg.t_fit(np.zeros((1, 50)))
    assert np.isnan(flat[0])


# ----------------------------------------------------------------------- (b) point in time ----
def test_truncating_after_t_leaves_the_fr_drift_unchanged() -> None:
    close = np.exp(np.cumsum(np.random.default_rng(2).standard_t(5, 2000) * 0.001))
    pos = np.array([239, 240, 700, 1500, 1999])
    full = fsg.fisher_rao_drift(close, pos, window=120)
    assert np.isnan(full[0]) and np.all(np.isfinite(full[1:]))
    for p, v in zip(pos[1:], full[1:], strict=True):
        cut = fsg.fisher_rao_drift(close[: p + 1], [p], window=120)
        assert cut[0] == pytest.approx(v, abs=1e-12)
    # A later shock does not move an earlier reading.
    shocked = close.copy()
    shocked[1501:] *= 1.5
    assert fsg.fisher_rao_drift(shocked, [1500])[0] == pytest.approx(full[3], abs=1e-12)


def test_truncating_after_t_leaves_the_absorption_shift_unchanged() -> None:
    panel = _factor_panel(24, 1000, beta=1.0, seed=5)
    t = int(_stamps(1001)[900].value)
    cut = {s: (st[st <= t], cl[: int((st <= t).sum())]) for s, (st, cl) in panel.items()}
    full_v = fsg.absorption_shift(panel, t)
    assert full_v is not None and np.isfinite(full_v)
    assert fsg.absorption_shift(cut, t) == pytest.approx(full_v, abs=1e-12)
    assert fsg.absorption_ratio(cut, t) == pytest.approx(fsg.absorption_ratio(panel, t),
                                                         abs=1e-12)


# --------------------------------------------------------------------- (c) absorption ratio ----
def test_a_one_factor_panel_reads_ar_near_one() -> None:
    panel = _factor_panel(25, 500, beta=20.0, seed=1)
    ar = fsg.absorption_ratio(panel, _stamps(501)[450])
    assert ar is not None and ar > 0.95


def test_an_iid_panel_reads_ar_near_k_over_n() -> None:
    n = 25
    k = -(-n // 5)
    reads = []
    for seed in range(6):
        rets = np.random.default_rng(seed).normal(0, 0.001, (500, n))
        ar = fsg.absorption_ratio(_panel_from_returns(rets), _stamps(501)[450])
        assert ar is not None
        reads.append(ar)
    # Sample eigenvalues spread (Marchenko-Pastur), so the top k read a little above k/N.
    assert k / n <= float(np.mean(reads)) < k / n + 0.12


def test_absorption_ratio_of_uses_ceil_n_over_five() -> None:
    rets = np.random.default_rng(0).normal(size=(400, 21))
    eig = np.sort(np.linalg.eigvalsh(np.corrcoef(rets, rowvar=False)))[::-1]
    assert fsg.absorption_ratio_of(rets) == pytest.approx(eig[:5].sum() / eig.sum())


def test_fewer_than_twenty_panel_members_drops_the_signal(monkeypatch) -> None:
    small = _factor_panel(19, 1000, beta=1.0)
    t = _stamps(1001)[900]
    assert fsg.aligned_returns(small, t) is None
    assert fsg.absorption_ratio(small, t) is None and fsg.absorption_shift(small, t) is None
    # Enough members, but most lack a full window at t: still dropped.
    short = {**_factor_panel(10, 1000, beta=1.0),
             **{f"Y{j}": (st[-200:], cl[-200:])
                for j, (st, cl) in enumerate(_factor_panel(15, 1000, beta=1.0).values())}}
    assert fsg.aligned_returns(short, t) is None
    monkeypatch.setattr(fsg, "get_family_func", lambda name: _fake_base([t]))
    monkeypatch.setattr(fsg, "load_absorption_panel", lambda: small)
    assert fsg.family_absorption_gated(_bars(np.linspace(1.0, 1.1, 1001)),
                                       base_family="trend_ma_cross", min_history=0) == []


def test_a_stale_member_is_out_of_the_panel() -> None:
    panel = _factor_panel(20, 1000, beta=1.0)
    t = int(_stamps(1001)[900].value)
    st, cl = panel["S000"]
    gone = int(np.searchsorted(st, t - 100 * HOUR))
    panel["S000"] = (st[:gone], cl[:gone])           # last bar 100 h before t > MAX_STALE_HOURS
    assert fsg.aligned_returns(panel, t) is None      # 19 fresh members left


# ------------------------------------------------------------- (d) the tail fixed by class ----
def _brute(states: list[float], high: bool, q: float = 1 / 3, need: int = 30) -> list[int]:
    out = []
    for k in range(need, len(states)):
        below = sum(1 for h in states[:k] if h < states[k]) / k
        if (below >= 1 - q) if high else (below <= q):
            out.append(k)
    return out


@pytest.mark.parametrize("base", ["trend_ma_cross", "session_range_breakout",
                                  "mean_reversion_rsi"])
def test_fisher_rao_gate_keeps_its_class_tail_by_brute_force(monkeypatch, base) -> None:
    n = 3000
    close = np.exp(np.cumsum(np.random.default_rng(9).standard_t(5, n) * 0.001))
    idx = _stamps(n)
    pos = list(range(260, n, 41))
    times = [idx[p] for p in pos]
    monkeypatch.setattr(fsg, "get_family_func", lambda name: _fake_base(times))
    kept = [s.time for s in fsg.family_fisher_rao_gated(_bars(close), base_family=base)]
    d = [float(fsg.fisher_rao_drift(close[: p + 1], [p], window=120)[0]) for p in pos]
    # trend/breakout keep the BOTTOM tail (slow drift), reversion the TOP tail (fast drift)
    top = fsg.mechanism_class(base) in fsg.SYNC_LOW
    expect = [times[k] for k in _brute(d, high=top)]
    assert kept == expect and 0 < len(kept) < len(times) // 2


def _scripted_absorption(monkeypatch, base: str, shifts: list[float]):
    idx = _stamps(1000)
    times = [idx[100 + 8 * k] for k in range(len(shifts))]
    by = {t.value: v for t, v in zip(times, shifts, strict=True)}
    monkeypatch.setattr(fsg, "get_family_func", lambda name: _fake_base(times))
    monkeypatch.setattr(fsg, "load_absorption_panel", lambda: _factor_panel(20, 50, beta=1.0))
    monkeypatch.setattr(fsg, "absorption_shift", lambda panel, t, **_k: by[int(t)])
    out = fsg.family_absorption_gated(_bars(np.linspace(1.0, 1.1, 1000)), base_family=base)
    return times, [s.time for s in out]


@pytest.mark.parametrize("base", ["trend_ma_cross", "session_range_breakout",
                                  "mean_reversion_rsi"])
def test_absorption_gate_keeps_its_class_tail_by_brute_force(monkeypatch, base) -> None:
    shifts = list(np.random.default_rng(7).normal(0, 1, 60))
    times, kept = _scripted_absorption(monkeypatch, base, shifts)
    top = fsg.mechanism_class(base) in fsg.SYNC_HIGH       # trend/breakout keep the TOP tail
    assert kept == [times[k] for k in _brute(shifts, high=top)]
    assert 0 < len(kept) < 30


def test_a_rising_shift_is_all_trend_and_no_reversion(monkeypatch) -> None:
    shifts = [0.05 * k for k in range(45)]
    times, kept = _scripted_absorption(monkeypatch, "trend_ma_cross", shifts)
    assert kept == times[30:]
    _, kept = _scripted_absorption(monkeypatch, "mean_reversion_rsi", shifts)
    assert kept == []


def test_other_classes_and_wrappers_return_nothing(monkeypatch) -> None:
    idx = _stamps(1000)
    monkeypatch.setattr(fsg, "get_family_func", lambda name: _fake_base([idx[900]]))
    monkeypatch.setattr(fsg, "load_absorption_panel", lambda: _factor_panel(20, 999, beta=1.0))
    bars = _bars(np.linspace(1.0, 1.1, 1000))
    for fn in (fsg.family_fisher_rao_gated, fsg.family_absorption_gated):
        assert fn(bars, base_family="dow_effect") == []
        for inner in ("fisher_rao_gated", "absorption_gated", "sync_gated"):
            assert fn(bars, base_family=inner) == []


def test_two_signals_on_one_bar_never_rank_against_each_other() -> None:
    t = [_stamps(100)[k] for k in range(40)]
    sigs = [Signal(time=x, side=1, stop=0.9, target=1.2, ttl_bars=12, tag="f") for x in t]
    sigs.append(Signal(time=t[-1], side=-1, stop=1.2, target=0.9, ttl_bars=12, tag="f"))
    vals = {int(x.value): float(k) for k, x in enumerate(t)}
    kept = fsg.keep_in_tail(sigs, lambda key, s: vals[key], keep_top=True, min_history=30)
    assert [s.time for s in kept].count(t[-1]) == 2


# ------------------------------------------------------------------------ (e) the proposer ----
def test_proposer_mints_each_cell_once_and_gives_crypto_no_absorption(monkeypatch,
                                                                       tmp_path) -> None:
    P, _, charged = base_tests._two_symbol_proposer(monkeypatch, tmp_path)
    syms = ["BTCUSD", "EURUSD", "XAUUSD"]
    monkeypatch.setattr(P, "store_symbols", lambda: syms)
    monkeypatch.setattr(P, "sync_applies", lambda sym: sym != "BTCUSD")
    monkeypatch.setattr(P, "MINT_ROWS_PER_PASS", 1500)
    grid, refused = P.build_grid(syms)
    keys = [(c["family"], c["params"]["base_family"], c["symbol"]) for c in grid]
    assert len(keys) == len(set(keys))
    assert {"fisher_rao_gated", "absorption_gated"} <= {c["family"] for c in grid}
    for w in ("fisher_rao_gated", "absorption_gated"):
        assert P.bases_for(w) == P.bases_for("sync_gated")
        for c in grid:
            if c["family"] == w:
                assert {k: c["params"][k] for k in P.DEFAULTS[w]} == P.DEFAULTS[w]
    assert not [k for k in keys if k[0] == "absorption_gated" and k[2] == "BTCUSD"]
    assert not [k for k in keys if k[0] == "sync_gated" and k[2] == "BTCUSD"]
    assert len([k for k in keys if k[0] == "fisher_rao_gated" and k[2] == "BTCUSD"]) == len(
        P.bases_for("fisher_rao_gated"))
    assert refused["absorption_gated:off_panel_session"] == len(P.bases_for("absorption_gated"))
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


def test_geometry_families_are_registered_where_the_gauntlet_looks() -> None:
    from mt5desk.families_orthogonal import FAMILY_INPUTS, FAMILY_TIMEFRAMES, ORTHOGONAL_FAMILIES
    from mt5desk.family_alt_series import _UNWRAPPABLE
    from research.axis_registry import FAMILY_TABLE
    from research.orthogonal_sweep import NOT_SOURCED_HERE

    from research import alpha_genome as ag
    for fam in ("fisher_rao_gated", "absorption_gated"):
        assert fam in ORTHOGONAL_FAMILIES and fam in FAMILY_INPUTS and fam in FAMILY_TABLE
        assert fam in _UNWRAPPABLE and fam in NOT_SOURCED_HERE
        assert FAMILY_TIMEFRAMES[fam][0] == ("H1",)
        assert ag.MECHANISM_CLASS[fam] == "regime"


def test_a_frozen_feed_is_no_fit_not_a_distance() -> None:
    """Audit SF-1: a window mostly of exactly-zero returns collapsed sigma and read a 21.1
    distance that the reversion arm kept; it must be NaN, which keeps no signal."""
    rng = np.random.default_rng(3)
    live = rng.standard_t(5, size=240) * 1e-3
    frozen = live.copy()
    frozen[rng.random(240) < 0.85] = 0.0
    mu, sig = fsg.t_fit(np.vstack([live, frozen, np.zeros(240)]))
    assert np.isfinite(sig[0]) and sig[0] > 0
    assert np.isnan(sig[1]) and np.isnan(sig[2])
    d = fsg.fisher_rao_t(mu[0], sig[0], mu[1], sig[1])
    assert np.all(np.isnan(d))


def test_absorption_pins_blas_to_one_thread_for_the_call_only() -> None:
    """Audit SF-2: the eigen-decomposition runs single-threaded inside its own scope, and the
    process's BLAS threading is left exactly as it was afterwards."""
    threadpoolctl = pytest.importorskip("threadpoolctl")
    seen: list[int] = []
    real = np.linalg.eigvalsh

    def spy(a: np.ndarray) -> np.ndarray:
        seen.extend(i["num_threads"] for i in threadpoolctl.threadpool_info()
                    if i["user_api"] == "blas")
        return real(a)

    before = [i["num_threads"] for i in threadpoolctl.threadpool_info() if i["user_api"] == "blas"]
    r = np.random.default_rng(4).standard_normal((360, 12))
    mp = pytest.MonkeyPatch()
    mp.setattr(np.linalg, "eigvalsh", spy)
    try:
        ar = fsg.absorption_ratio_of(r)
    finally:
        mp.undo()
    after = [i["num_threads"] for i in threadpoolctl.threadpool_info() if i["user_api"] == "blas"]
    assert ar is not None and 0 < ar <= 1
    assert all(n == 1 for n in seen)
    assert after == before
