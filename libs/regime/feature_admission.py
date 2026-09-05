"""ADX, Hurst, ACF, variance ratio -- as CANDIDATE features that must earn a place in the model.

The article's rule was "ADX > 25 means trend". That is a feature made into an authority by fiat.
Here the same quantities are computed as observation columns and offered to the regime engine,
and the engine is asked ONE question, walk-forward: does its predictive log-likelihood on unseen
days improve when the column is present? If not, the column goes to the graveyard, exactly as a
state dimension does in `state_admission`. Nothing joins the model because it is famous.

THE TEST. The HMM is fitted on a training block with and without the candidate column, then the
forward filter is run on the next block and the one-step-ahead predictive log-likelihood of each
day's observation is accumulated. The likelihood is evaluated on the BASE columns only in both
cases -- the candidate must improve the model's account of return, vol and trend, not merely add
a column it can also predict. Blocks walk forward; the paired difference is deflated by the
number of candidates tried.

THE FEATURES, all causal and all standardised on the training block:
    adx         Wilder's ADX over `n` bars -- trend strength without direction
    hurst       rescaled-range exponent over a trailing window -- persistence vs reversion
    acf1        lag-1 autocorrelation of returns over a trailing window
    vratio      Lo-MacKinlay variance ratio at lag q -- the random-walk test as a state
    eff         trend efficiency: |net move| / sum |moves| -- how direct the path was
    vov         vol of vol: the std of rolling realised vol
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

if TYPE_CHECKING:  # annotation only; `judge` imports the model lazily at call time
    from libs.regime.hmm import GaussianHMM

CANDIDATES = ("adx", "hurst", "acf1", "vratio", "eff", "vov")
N_BLOCKS = 4
ADMIT_T = 2.0


def adx(close: pd.Series, high: pd.Series | None = None, low: pd.Series | None = None,
        n: int = 14) -> pd.Series:
    """Wilder's ADX. With closes only, high/low are approximated by the close itself, which
    makes it a directional-movement index on closes -- weaker, and labelled as such."""
    h = close if high is None else high
    lo = close if low is None else low
    up = h.diff()
    dn = -lo.diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([(h - lo), (h - close.shift()).abs(), (lo - close.shift()).abs()],
                   axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / n, adjust=False).mean()
    pdi = 100 * pd.Series(plus_dm, index=close.index).ewm(alpha=1.0 / n, adjust=False).mean() / atr
    mdi = 100 * pd.Series(minus_dm, index=close.index).ewm(alpha=1.0 / n, adjust=False).mean() / atr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1.0 / n, adjust=False).mean().fillna(0.0)


def hurst(close: pd.Series, window: int = 100) -> pd.Series:
    r = np.log(close).diff()

    def _h(x: np.ndarray) -> float:
        x = x[np.isfinite(x)]
        if x.size < 20:
            return np.nan
        y = np.cumsum(x - x.mean())
        rs = (y.max() - y.min()) / (x.std(ddof=1) or 1e-12)
        return math.log(rs) / math.log(x.size) if rs > 0 else np.nan
    return r.rolling(window).apply(_h, raw=True).fillna(0.5)


def acf1(close: pd.Series, window: int = 60) -> pd.Series:
    r = np.log(close).diff()
    return r.rolling(window).apply(
        lambda x: float(np.corrcoef(x[:-1], x[1:])[0, 1]) if np.isfinite(x).all() and
        x.std() > 0 else np.nan, raw=True).fillna(0.0)


def vratio(close: pd.Series, q: int = 5, window: int = 120) -> pd.Series:
    r = np.log(close).diff()

    def _vr(x: np.ndarray) -> float:
        x = x[np.isfinite(x)]
        if x.size < q * 4:
            return np.nan
        v1 = x.var(ddof=1)
        if v1 <= 0:
            return np.nan
        xq = np.convolve(x, np.ones(q), mode="valid")
        return float(xq.var(ddof=1) / (q * v1))
    return r.rolling(window).apply(_vr, raw=True).fillna(1.0)


def eff(close: pd.Series, window: int = 20) -> pd.Series:
    net = (close - close.shift(window)).abs()
    path = close.diff().abs().rolling(window).sum()
    return (net / path.replace(0, np.nan)).fillna(0.0)


def vov(close: pd.Series, window: int = 20) -> pd.Series:
    rv = np.log(close).diff().rolling(window).std()
    return rv.rolling(window).std().fillna(0.0)


FEATURES: dict[str, Callable[[pd.Series], pd.Series]] = {
    "adx": lambda c: adx(c), "hurst": lambda c: hurst(c), "acf1": lambda c: acf1(c),
    "vratio": lambda c: vratio(c), "eff": lambda c: eff(c), "vov": lambda c: vov(c),
}


@dataclass(frozen=True)
class FeatureVerdict:
    feature: str
    verdict: str
    ll_gain_per_day: float
    t_paired: float
    t_deflated: float
    n_test_days: int
    why: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"feature": self.feature, "verdict": self.verdict,
                "ll_gain_per_day": round(self.ll_gain_per_day, 6),
                "t_paired": round(self.t_paired, 3), "t_deflated": round(self.t_deflated, 3),
                "n_test_days": self.n_test_days, "why": self.why}


def _predictive_ll(hmm: GaussianHMM, x_train: np.ndarray, x_test: np.ndarray,
                   base_cols: int) -> np.ndarray:
    """One-step-ahead log-likelihood of each test day's BASE observation under the filter.

    The filter is run over train then test; the predictive distribution for day t is the
    filtered state at t-1 pushed through the transition matrix, and the observation scored is
    the base columns only, so the candidate is judged on what it does for the account of the
    base features rather than on predicting itself.
    """
    x_all = np.vstack([x_train, x_test])
    post = hmm.filter_posterior(x_all)
    means = np.asarray(hmm.means)[:, :base_cols]
    var = np.asarray(hmm.vars)[:, :base_cols]
    n_tr = x_train.shape[0]
    out = np.empty(x_test.shape[0])
    for i in range(x_test.shape[0]):
        t = n_tr + i
        prior = post[t - 1] @ hmm.transmat
        obs = x_all[t, :base_cols]
        ll_state = -0.5 * np.sum((obs[None, :] - means) ** 2 / var + np.log(2 * np.pi * var),
                                 axis=1)
        m = ll_state.max()
        out[i] = m + math.log(float(np.sum(prior * np.exp(ll_state - m))) + 1e-300)
    return out


def judge(close: pd.Series, feature: str, candidates_tried: int = 1) -> FeatureVerdict:
    from libs.regime.engine import RegimeEngine
    from libs.regime.features import raw_regime_features, standardise
    from libs.regime.hmm import GaussianHMM

    base = raw_regime_features(close)
    fn = FEATURES.get(feature)
    if fn is None:
        return FeatureVerdict(feature, "UNKNOWN", 0.0, 0.0, 0.0, 0, "no such feature")
    extra = fn(close).to_numpy(dtype=float)[:, None]
    both = np.hstack([base, extra])
    n = base.shape[0]
    edges = [int(n * i / N_BLOCKS) for i in range(N_BLOCKS + 1)]
    gains: list[np.ndarray] = []
    for b in range(1, N_BLOCKS):
        tr, te = slice(edges[0], edges[b]), slice(edges[b], edges[b + 1])
        if edges[b] - edges[0] < 250 or edges[b + 1] - edges[b] < 60:
            continue
        try:
            mu0, sd0 = base[tr].mean(axis=0), base[tr].std(axis=0) + 1e-9
            mu1, sd1 = both[tr].mean(axis=0), both[tr].std(axis=0) + 1e-9
            h0 = GaussianHMM(n_states=RegimeEngine().k).fit(standardise(base[tr], mu0, sd0))
            h1 = GaussianHMM(n_states=RegimeEngine().k).fit(standardise(both[tr], mu1, sd1))
            ll0 = _predictive_ll(h0, standardise(base[tr], mu0, sd0),
                                 standardise(base[te], mu0, sd0), base.shape[1])
            ll1 = _predictive_ll(h1, standardise(both[tr], mu1, sd1),
                                 standardise(both[te], mu1, sd1), base.shape[1])
        except Exception as exc:
            return FeatureVerdict(feature, "UNJUDGED", 0.0, 0.0, 0.0, 0,
                                  f"{type(exc).__name__}: {exc}")
        gains.append(ll1 - ll0)
    if not gains:
        return FeatureVerdict(feature, "UNJUDGED", 0.0, 0.0, 0.0, 0, "too little history")
    d = np.concatenate(gains)
    d = d[np.isfinite(d)]
    if d.size < 60:
        return FeatureVerdict(feature, "UNJUDGED", 0.0, 0.0, 0.0, int(d.size),
                              "fewer than 60 scored days")
    sd = float(d.std(ddof=1))
    t = float(d.mean() / (sd / math.sqrt(d.size))) if sd > 0 else 0.0
    from libs.regime.state_admission import _expected_max_z
    t_def = t - _expected_max_z(max(1, candidates_tried)) if t > 0 else t
    if t_def >= ADMIT_T:
        v, why = "ADMIT", "improves one-step predictive likelihood of the base observations"
    elif t <= -ADMIT_T:
        v, why = "GRAVEYARD", "measurably worsens the model's account of unseen days"
    else:
        v, why = "RETAIN_SHRUNK", "no measurable improvement"
    return FeatureVerdict(feature, v, float(d.mean()), t, t_def, int(d.size), why)


def judge_all(close: pd.Series, features: tuple[str, ...] = CANDIDATES,
              ) -> dict[str, FeatureVerdict]:
    return {f: judge(close, f, candidates_tried=len(features)) for f in features}
