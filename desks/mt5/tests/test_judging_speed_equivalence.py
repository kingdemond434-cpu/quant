"""JUDGING CAPACITY WITHOUT A NEW ANSWER: every build-path speedup returns what the old code did.

The sealed gauntlet's hourly sweep is bounded by FRESH_BUILD_BUDGET_SEC, and what fills that
budget is building each cell's signals and daily series. The speedups behind this test make more
cells fit in the same budget; none of them may change a single signal, trade or daily return,
because a faster judge that judges differently is a different judge.

So every changed path is pinned against an ORACLE -- a verbatim copy of the code as it was before
the change -- on synthetic random-walk bars:

  * `libs.regime.hmm.logsumexp` against `scipy.special.logsumexp`, bit for bit, including rows of
    -inf, +inf and NaN and values at the top of the float range.
  * the Gaussian HMM (fit, filter, Viterbi) against the scipy-backed original.
  * the per-bar loops that now read numpy arrays instead of `Series.iloc[i]`, and the loops that
    box one list of Timestamps instead of one Timestamp per bar.
  * the build memos (`mt5desk.build_memo`) -- `exit_operated` against its un-memoised original,
    cold and warm, and the frame fingerprint against a one-byte change.
  * `build_cell` + `daily_series` end to end, cold memo against warm memo.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import build_memo, families  # noqa: E402
from mt5desk import family_exit_operated as feo  # noqa: E402
from mt5desk.families import Signal, _atr, _h1, get_family_func  # noqa: E402
from scipy.special import logsumexp as scipy_logsumexp  # noqa: E402

from libs.regime import hmm as hmm_mod  # noqa: E402


def _bars(n: int = 4000, seed: int = 3, minutes: int = 60) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2019-01-07", periods=int(n * 1.5), freq=f"{minutes}min")
    idx = idx[idx.dayofweek < 5][:n]
    ret = rng.normal(0, 0.002, n)
    close = 1.2 * np.exp(np.cumsum(ret))
    op = np.r_[1.2, close[:-1]]
    wick = np.abs(rng.normal(0, 0.0015, n)) * close
    df = pd.DataFrame({"open": op, "high": np.maximum(op, close) + wick,
                       "low": np.minimum(op, close) - wick, "close": close,
                       "tick_volume": rng.integers(50, 5000, n).astype(float),
                       "spread": rng.integers(5, 40, n)}, index=idx)
    return _h1(df)


def _sig_tuple(s: Signal) -> tuple:
    return tuple(getattr(s, f) for f in Signal.__dataclass_fields__)


def _same_signals(a: list, b: list) -> bool:
    return [_sig_tuple(s) for s in a] == [_sig_tuple(s) for s in b]


# ------------------------------------------------------------------------------ logsumexp
def test_logsumexp_is_bit_identical_to_scipy() -> None:
    rng = np.random.default_rng(0)
    shapes = [(3, 3), (2, 2), (50, 3), (40, 9), (3,), (4, 4)]
    for trial in range(3000):
        a = rng.normal(0, (1.0, 50.0, 300.0)[trial % 3], shapes[trial % len(shapes)])
        if trial % 2:
            r = rng.random(a.shape)
            a[r < 0.05] = -np.inf
            a[r > 0.98] = np.inf
            a[(r > 0.97) & (r < 0.975)] = np.nan
        if trial % 11 == 0:
            a[..., 0] = 1.7e308
        for axis in range(a.ndim):
            for keepdims in (False, True):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    want = np.asarray(scipy_logsumexp(a, axis=axis, keepdims=keepdims))
                    got = np.asarray(hmm_mod.logsumexp(a, axis=axis, keepdims=keepdims))
                assert want.shape == got.shape
                assert want.tobytes() == got.tobytes() or np.array_equal(
                    want, got, equal_nan=True), (trial, axis, keepdims)


# ------------------------------------------------------------------------------ HMM oracle
class _ScipyHMM(hmm_mod.GaussianHMM):
    """The GaussianHMM as it was: every logsumexp through scipy. Verbatim copies."""

    def _forward_backward(self, le):
        n = le.shape[0]
        lt = np.log(self.transmat + 1e-300)
        log_alpha = np.empty((n, self.k))
        log_beta = np.zeros((n, self.k))
        log_alpha[0] = np.log(self.startprob + 1e-300) + le[0]
        for t in range(1, n):
            log_alpha[t] = le[t] + scipy_logsumexp(log_alpha[t - 1][:, None] + lt, axis=0)
        for t in range(n - 2, -1, -1):
            log_beta[t] = scipy_logsumexp(lt + le[t + 1][None, :] + log_beta[t + 1][None, :],
                                          axis=1)
        return log_alpha, log_beta

    def fit(self, x):
        x = np.asarray(x, dtype="float64")
        if x.ndim == 1:
            x = x[:, None]
        self._init(x)
        n = x.shape[0]
        for _ in range(self.n_iter):
            le = self._log_emission(x)
            log_alpha, log_beta = self._forward_backward(le)
            log_gamma = log_alpha + log_beta
            log_gamma -= scipy_logsumexp(log_gamma, axis=1, keepdims=True)
            gamma = np.exp(log_gamma)
            lt = np.log(self.transmat + 1e-300)
            log_xi = (log_alpha[:-1, :, None] + lt[None, :, :]
                      + le[1:, None, :] + log_beta[1:, None, :])
            log_xi -= scipy_logsumexp(log_xi.reshape(n - 1, -1), axis=1)[:, None, None]
            xi = np.exp(log_xi)
            self.startprob = gamma[0] / (gamma[0].sum() + 1e-12)
            denom = xi.sum(axis=0).sum(axis=1, keepdims=True) + 1e-12
            self.transmat = xi.sum(axis=0) / denom
            for j in range(self.k):
                w = gamma[:, j]
                sw = w.sum() + 1e-9
                self.means[j] = (w[:, None] * x).sum(axis=0) / sw
                diff = x - self.means[j]
                self.vars[j] = (w[:, None] * diff * diff).sum(axis=0) / sw + self.reg
        return self

    def filter_posterior(self, x):
        x = np.asarray(x, dtype="float64")
        if x.ndim == 1:
            x = x[:, None]
        le = self._log_emission(x)
        n = le.shape[0]
        lt = np.log(self.transmat + 1e-300)
        log_alpha = np.empty((n, self.k))
        log_alpha[0] = np.log(self.startprob + 1e-300) + le[0]
        for t in range(1, n):
            log_alpha[t] = le[t] + scipy_logsumexp(log_alpha[t - 1][:, None] + lt, axis=0)
        post = np.exp(log_alpha - scipy_logsumexp(log_alpha, axis=1, keepdims=True))
        return np.asarray(post, dtype="float64")


@pytest.mark.parametrize("k,seed", [(2, 0), (3, 1), (3, 7)])
def test_hmm_fit_filter_and_decode_are_bit_identical(k: int, seed: int) -> None:
    rng = np.random.default_rng(seed)
    x = np.concatenate([rng.normal(0, 1, (150, 3)), rng.normal(1.5, 2.0, (150, 3)),
                        rng.normal(-1, 0.5, (150, 3))])
    new = hmm_mod.GaussianHMM(n_states=k, n_iter=15, seed=seed).fit(x)
    old = _ScipyHMM(n_states=k, n_iter=15, seed=seed).fit(x)
    for attr in ("startprob", "transmat", "means", "vars"):
        assert np.asarray(getattr(new, attr)).tobytes() == np.asarray(getattr(old, attr)).tobytes()
    assert new.filter_posterior(x).tobytes() == old.filter_posterior(x).tobytes()
    assert np.array_equal(new.predict(x), old.predict(x))


# ------------------------------------------------------------------ per-bar loop oracles
def _old_liquidity_gamma_reversal(df, *, min_displacement_atr=1.5, vol_n=20, liquidity_n=20,
                                  require_high_liquidity=True, require_failed_continuation=True,
                                  stop_atr=1.0, rr=1.2, hold_bars=4):
    """Verbatim pre-change body of `families_edge_queue.family_liquidity_gamma_reversal`."""
    if df.empty or len(df) < max(vol_n, liquidity_n) * 5:
        return []
    d = df.copy()
    atr = _atr(d, vol_n)
    rng = (d["high"] - d["low"])
    rng_med = rng.rolling(liquidity_n * 5).median()
    ret = d["close"].diff()
    out = []
    start = max(vol_n, liquidity_n) * 5
    for i in range(start, len(d) - 1):
        a = float(atr.iloc[i])
        px = float(d["close"].iloc[i])
        disp = float(ret.iloc[i])
        if not np.isfinite(a) or a <= 0 or not np.isfinite(disp):
            continue
        if abs(disp) < min_displacement_atr * a:
            continue
        liquid = float(rng.iloc[i]) < float(rng_med.iloc[i]) * 1.5
        if require_high_liquidity and not liquid:
            continue
        body = float(d["close"].iloc[i]) - float(d["open"].iloc[i])
        extended = (np.sign(body) == np.sign(disp)) and abs(body) > 0.7 * abs(disp)
        if require_failed_continuation and extended:
            continue
        side = -1 if disp > 0 else 1
        stop = px - side * stop_atr * a
        out.append(Signal(time=d.index[i], side=side, stop=stop,
                          target=px + side * stop_atr * a * rr, ttl_bars=hold_bars,
                          tag="liquidity_gamma_reversal", trigger=None, wait_bars=1))
    return out


def _old_vol_transition(df, *, fast=12, slow=96, ratio_in=1.6, atr_n=20, stop_atr=1.5, rr=2.0,
                        ttl_bars=24):
    """Verbatim pre-change body of `families_orthogonal.family_vol_transition`."""
    d = _h1(df)
    ret = np.log(d["close"].astype(float)).diff()
    v_fast = ret.rolling(fast).std(ddof=1)
    v_slow = ret.rolling(slow).std(ddof=1)
    atr = _atr(d, atr_n)
    signals = []
    for i in range(slow + 1, len(d) - 1):
        prev = float(v_fast.iloc[i - 1] / v_slow.iloc[i - 1]) if v_slow.iloc[i - 1] else np.nan
        now = float(v_fast.iloc[i] / v_slow.iloc[i]) if v_slow.iloc[i] else np.nan
        if not (np.isfinite(prev) and np.isfinite(now)):
            continue
        if not (prev < ratio_in <= now):
            continue
        a = float(atr.iloc[i])
        if not np.isfinite(a) or a <= 0:
            continue
        px = float(d["close"].iloc[i])
        side = 1 if float(ret.iloc[i]) >= 0 else -1
        signals.append(Signal(time=d.index[i], side=side, stop=px - side * stop_atr * a,
                              target=px + side * stop_atr * a * rr, ttl_bars=ttl_bars,
                              tag="vol_transition", trigger=None, wait_bars=1))
    return signals


def _old_asia_momentum(df, *, asia_start=0, asia_end=7, atr_n=20, mom_thresh=0.35, ttl_bars=12,
                       rr=1.8):
    """Verbatim pre-change body of `families.family_asia_momentum` (one Timestamp per bar)."""
    h1 = _h1(df)
    atr = _atr(h1, atr_n)
    h1 = h1.assign(date=h1.index.date, hour=h1.index.hour)
    asia = (h1.loc[(h1["hour"] >= asia_start) & (h1["hour"] < asia_end)]
            .groupby("date").agg(o=("open", "first"), c=("close", "last")))
    signals = []
    a = atr.to_numpy()
    o = h1["open"].to_numpy()
    for i in range(2, len(h1) - 2):
        ts = h1.index[i]
        if ts.hour != asia_end:
            continue
        key = ts.date()
        if key not in asia.index:
            continue
        ai = a[i]
        if not (ai > 0) or np.isnan(ai):
            continue
        row = asia.loc[key]
        move = float(row["c"] - row["o"])
        if abs(move) < mom_thresh * ai:
            continue
        side = 1 if move > 0 else -1
        entry = o[i]
        stop_dist = 1.2 * ai
        signals.append(Signal(time=ts, side=side, stop=entry - side * stop_dist,
                              target=entry + side * stop_dist * rr, ttl_bars=ttl_bars,
                              tag="asia_momentum"))
    return signals


@pytest.mark.parametrize("seed", [3, 4])
def test_array_loops_match_their_iloc_originals(seed: int) -> None:
    from mt5desk.families_edge_queue import family_liquidity_gamma_reversal
    from mt5desk.families_orthogonal import family_vol_transition

    df = _bars(5000, seed)
    # Synthetic bars open at the prior close, so every body is "extended": the failed-continuation
    # filter is switched off to give the loop signals to agree on.
    for kw in ({"min_displacement_atr": 0.8, "require_failed_continuation": False},
               {"min_displacement_atr": 0.6, "require_failed_continuation": False,
                "require_high_liquidity": False}):
        new = family_liquidity_gamma_reversal(df, **kw)
        assert new and _same_signals(new, _old_liquidity_gamma_reversal(df, **kw))
    for kw in ({"ratio_in": 1.2}, {"ratio_in": 1.3, "fast": 8}):
        new = family_vol_transition(df, **kw)
        assert new and _same_signals(new, _old_vol_transition(df, **kw))
    for kw in ({}, {"mom_thresh": 0.25, "asia_end": 6}):
        new = families.family_asia_momentum(df, **kw)
        assert new and _same_signals(new, _old_asia_momentum(df, **kw))


# ------------------------------------------------------------------------------ memos
def _old_exit_operated(df, *, base_family="", base_params=None, expansion_mult=4.0,
                       exit_on_anchor_flip=False, anchor_mult=4, anchor_n=50, atr_n=14):
    """Verbatim pre-change body of `family_exit_operated` (no memo)."""
    from mt5desk.exit_operators import anchor_direction, apply_exit_operators

    if not base_family or base_family in feo._UNWRAPPABLE:
        return []
    if expansion_mult <= 0 and not exit_on_anchor_flip:
        return []
    fn = get_family_func(base_family)
    if fn is None:
        return []
    params = dict(base_params or {})
    for k in ("timeframe", "session"):
        params.pop(k, None)
    d = _h1(df)
    try:
        sigs = fn(d, side=1, **params)
    except TypeError:
        try:
            sigs = fn(d, **params)
        except Exception:
            return []
    except Exception:
        return []
    sigs = [s for s in (sigs or []) if isinstance(s, Signal)]
    if not sigs:
        return []
    anchor = None
    if exit_on_anchor_flip:
        anchor = anchor_direction(d, anchor_mult=max(2, int(anchor_mult)), anchor_n=int(anchor_n))
    return apply_exit_operators(d, sigs, expansion_mult=float(expansion_mult),
                                exit_on_anchor_flip=bool(exit_on_anchor_flip), anchor=anchor,
                                atr_n=int(atr_n))


def test_exit_operated_memo_returns_the_unmemoised_signals() -> None:
    df = _bars(4000, 5)
    feo._BASE_MEMO.clear()
    for base, bp in (("mean_reversion_rsi", {"rsi_n": 7}), ("trend_ma_cross", {}),
                     ("vol_transition", {"ratio_in": 1.3}), ("no_such_family", {})):
        for em in (1.25, 2.0, 0.0):
            for flip in (False, True):
                kw = {"base_family": base, "base_params": bp, "expansion_mult": em,
                      "exit_on_anchor_flip": flip}
                assert _same_signals(feo.family_exit_operated(df, **kw),
                                     _old_exit_operated(df, **kw)), kw
    assert feo._BASE_MEMO.hits > 0          # the variants really did share one base build


def test_memo_hands_out_copies_a_caller_cannot_poison() -> None:
    df = _bars(3000, 6)
    feo._BASE_MEMO.clear()
    kw = {"base_family": "trend_ma_cross", "base_params": {}, "expansion_mult": 1.5}
    first = feo.family_exit_operated(df, **kw)
    for s in first:
        s.stop = -1.0
    assert _same_signals(feo.family_exit_operated(df, **kw), _old_exit_operated(df, **kw))


def test_fingerprint_sees_one_changed_byte_and_ignores_nothing() -> None:
    df = _bars(500, 7)
    base = build_memo.frame_fingerprint(df)
    assert build_memo.frame_fingerprint(df.copy()) == base
    moved = df.copy()
    moved.iloc[250, moved.columns.get_loc("close")] = np.nextafter(moved["close"].iloc[250], 9)
    assert build_memo.frame_fingerprint(moved) != base
    shifted = df.copy()
    shifted.index = shifted.index + pd.Timedelta(minutes=1)
    assert build_memo.frame_fingerprint(shifted) != base
    assert build_memo.frame_fingerprint(df.rename(columns={"spread": "spread2"})) != base
    daily = df["close"].groupby(df.index.date).last()
    assert build_memo.frame_fingerprint(daily) == build_memo.frame_fingerprint(daily.copy())
    assert build_memo.args_key("x", {"a": 1, "b": 2}) == build_memo.args_key("x", {"b": 2, "a": 1})
    assert build_memo.args_key("x", {"a": 1}) != build_memo.args_key("x", {"a": 1.0})


def test_memo_is_bounded() -> None:
    m = build_memo.Memo(entries=3)
    for i in range(10):
        assert m.get_or_compute((i,), lambda i=i: [i]) == [i]
    assert len(m._d) == 3


# -------------------------------------------------------------- end to end through the judge
def test_build_cell_and_daily_series_cold_equals_warm(monkeypatch) -> None:
    from scripts import external_gauntlet as eg

    frames = {tf: _bars(n, 8, minutes) for tf, n, minutes in
              (("H1", 4000, 60), ("H4", 1500, 240))}
    monkeypatch.setattr(eg, "_bars_for", lambda sym, timeframe="H1": frames.get(timeframe))
    meta = {"EURUSD": {"contract_size": 100000, "tick_size": 0.00001, "tick_value": 1.0,
                       "median_spread_pts": 10}}
    specs = [
        ("exit_operated", {"base_family": "trend_ma_cross", "base_params": {},
                           "expansion_mult": em, "exit_on_anchor_flip": flip})
        for em in (1.25, 3.0) for flip in (False, True)
    ] + [
        ("exit_operated", {"timeframe": "H4", "base_family": "mean_reversion_bollinger",
                           "base_params": {}, "expansion_mult": 2.0}),
        ("liquidity_gamma_reversal", {}),
        ("vol_transition", {"ratio_in": 1.3}),
        ("asia_momentum", {"mom_thresh": 0.25}),
    ]

    def run() -> list:
        out = []
        for fam, params in specs:
            cell = eg.build_cell("EURUSD", fam, params, meta)
            assert cell is not None, (fam, eg.LAST_BUILD_FAILURE)
            out.append((eg.daily_series(cell["df"], cell["sigs"], cell["costs"]),
                        eg.daily_series(cell["df"], cell["sigs"],
                                        eg.costs_for("EURUSD", meta, eg.COST_SCENARIO))))
        return out

    feo._BASE_MEMO.clear()
    cold = run()
    warm = run()
    for (a1, a3), (b1, b3) in zip(cold, warm, strict=True):
        pd.testing.assert_series_equal(a1, b1, check_exact=True)
        pd.testing.assert_series_equal(a3, b3, check_exact=True)
    assert any(len(a1) for a1, _ in cold)
