"""Regime engine -- fits HMM + GMM, characterises the latent states into market regimes, and emits
the live regime with confidence and the risk / leverage multipliers every downstream module reads.

A latent state is just an index; this maps it onto an economically meaningful label (bull/bear x
vol tier) from the real per-state mean return and volatility, then derives a LEVERAGE MULTIPLIER
that only de-risks (<=1.0): smaller in high-vol / bear regimes, full in calm bull regimes. The HMM
(temporal) and GMM (clustering) are cross-checked -- agreement => high confidence, disagreement
dampens confidence (it can only fall on disagreement, never rise).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from libs.regime.bayesian import BayesianRegimeFilter
from libs.regime.features import regime_features
from libs.regime.gmm import fit_gmm, gmm_posteriors
from libs.regime.hmm import GaussianHMM

_VOL_FACTOR = {"high_vol": 0.5, "mid_vol": 0.8, "low_vol": 1.0}
_TREND_FACTOR = {"bull": 1.0, "bear": 0.75}


def _characterise(states: np.ndarray, raw_ret: np.ndarray, k: int) -> dict[int, dict[str, object]]:
    """Label each state from its real mean return + volatility (bull/bear x vol tier)."""
    stats = {}
    for j in range(k):
        mask = states == j
        r = raw_ret[mask]
        stats[j] = {"mean_ret": float(np.mean(r)) if r.size else 0.0,
                    "vol": float(np.std(r)) if r.size > 1 else 0.0, "n": int(mask.sum())}
    vol_order = sorted(range(k), key=lambda j: stats[j]["vol"])  # low -> high
    tier = {}
    for rank, j in enumerate(vol_order):
        tier[j] = "low_vol" if rank == 0 else ("high_vol" if rank == k - 1 else "mid_vol")
    out: dict[int, dict[str, object]] = {}
    # TREND IS RELATIVE TO THE OTHER STATES, NOT TO ZERO -- and this is the difference between a
    # regime label that carries information and one that restates the asset's drift.
    #
    # MEASURED 2026-09-02 on XAUUSD, 2,181 daily closes: gold rose over the window, so EVERY HMM
    # state had a positive mean return and every one was labelled "bull". The GMM, clustering the
    # same features differently, produced bear/low_vol, bull/mid_vol and bear/high_vol. The two
    # models therefore disagreed on the trend axis for two states out of three, `hmm_gmm_agree`
    # went False, and `current()` returned confidence 0.000 -- on every single call.
    #
    # Downstream that made the entire regime layer inert: the allocator's world sampler mixes
    # over regime probabilities weighted by this confidence, so it fell back to empirical
    # frequency on every pass and the regime axis cost compute while contributing nothing.
    #
    # A state is bullish RELATIVE to the regime set it belongs to. Splitting at the cross-state
    # median mean makes the label informative for an asset with any drift, up or down, and makes
    # the two models comparable -- they are then both answering "which of these states is the
    # strong one", rather than one answering "did the price rise" and the other "did this cluster
    # rise". The vol axis was already relative (ranked low/mid/high) and always worked.
    _pivot = float(np.median([stats[j]["mean_ret"] for j in range(k)])) if k else 0.0
    for j in range(k):
        trend = "bull" if stats[j]["mean_ret"] >= _pivot else "bear"
        vt = tier[j]
        lev = max(0.2, min(1.0, _VOL_FACTOR[vt] * _TREND_FACTOR[trend]))
        out[j] = {"label": f"{trend}/{vt}", "trend": trend, "vol_tier": vt,
                  "mean_ret": round(stats[j]["mean_ret"], 6), "vol": round(stats[j]["vol"], 6),
                  "days": stats[j]["n"], "leverage_multiplier": round(lev, 3)}
    return out


class RegimeEngine:
    def __init__(self, *, n_states: int = 3, seed: int = 0) -> None:
        self.k = n_states
        self.seed = seed
        self.hmm = GaussianHMM(n_states=n_states, seed=seed)
        self.gmm: Any = None                   # sklearn GaussianMixture (untyped) once fitted
        self.x: np.ndarray = np.zeros((0, 3))
        self.hmm_states: np.ndarray = np.zeros(0, dtype="int64")
        self.hmm_char: dict[int, dict[str, object]] = {}
        self.gmm_char: dict[int, dict[str, object]] = {}
        self.posteriors: np.ndarray = np.zeros((0, n_states))

    def fit(self, close: pd.Series) -> RegimeEngine:
        x, raw = regime_features(close)
        self.x = x
        self.hmm.fit(x)
        self.hmm_states = self.hmm.predict(x)
        self.posteriors = self.hmm.filter_posterior(x)
        self.hmm_char = _characterise(self.hmm_states, raw, self.k)
        self.gmm = fit_gmm(x, n_states=self.k, seed=self.seed)
        gmm_states = self.gmm.predict(x)
        self.gmm_char = _characterise(gmm_states, raw, self.k)
        return self

    def make_filter(self) -> BayesianRegimeFilter:
        """Online Bayesian filter seeded from the fitted HMM (for incremental live updates)."""
        return BayesianRegimeFilter(self.hmm.transmat, self.hmm.means, self.hmm.vars,
                                    self.hmm.startprob)

    def current(self) -> dict[str, object]:
        """Live regime: HMM state label, confidence, GMM agreement, leverage multiplier.

        On HMM/GMM disagreement the confidence is dampened; the regime label is untouched.
        """
        if self.hmm_states.size == 0:
            return {"regime": "unknown", "confidence": 0.0, "leverage_multiplier": 1.0}
        j = int(self.hmm_states[-1])
        ch = self.hmm_char[j]
        conf = float(self.posteriors[-1].max())
        gmm_label = "—"
        if self.gmm is not None:
            gj = int(self.gmm.predict(self.x[-1:])[0])
            gmm_label = str(self.gmm_char[gj]["label"])
        agree = gmm_label == ch["label"]
        if self.gmm is not None and not agree:
            # Cross-model disagreement MUST dampen confidence (strictly conservative: this
            # branch can only LOWER conf, never raise it, and only fires on a genuine
            # disagreement -- an unfitted GMM is "no second opinion", not a contradiction).
            # Scale the HMM posterior by the GMM's own posterior mass on the HMM's label; on
            # disagreement the winning GMM component carries a different label, so this factor
            # is strictly < 1 and a confident contradiction drives conf towards 0.
            # AGREEMENT IS PER AXIS, NOT ON THE CONCATENATED STRING. This required an exact
            # match on "trend/vol_tier", so if the GMM's state set simply did not CONTAIN the
            # HMM's label the factor was exactly 0 -- however much the two models actually
            # agreed. MEASURED 2026-09-02 on XAUUSD: the HMM's current state was bull/high_vol
            # and the GMM's high-vol state was bear/high_vol, so `same` was empty, the factor was
            # 0, and confidence came back 0.000 on every call. Two models clustering continuous
            # features into three states will rarely produce identical label SETS, so an exact
            # string match makes confidence zero almost always -- and a confidence that is always
            # zero is not a measurement, it is a switch stuck off.
            #
            # The vol tier and the trend are separate claims and are scored separately: the GMM's
            # posterior mass on states sharing the HMM's vol tier, and on states sharing its
            # trend. Agreeing on volatility while differing on direction is partial agreement and
            # is dampened, not annihilated. Total contradiction still drives the factor to 0,
            # which is the conservative property the original was reaching for, and this branch
            # can still only ever LOWER confidence.
            gp = gmm_posteriors(self.gmm, self.x[-1:])[0]
            same_vol = [m for m in range(self.k)
                        if str(self.gmm_char[m]["vol_tier"]) == str(ch["vol_tier"])]
            same_trend = [m for m in range(self.k)
                          if str(self.gmm_char[m]["trend"]) == str(ch["trend"])]
            agree_vol = float(gp[same_vol].sum()) if same_vol else 0.0
            agree_trend = float(gp[same_trend].sum()) if same_trend else 0.0
            conf *= 0.5 * (agree_vol + agree_trend)
        return {
            "regime": ch["label"], "trend": ch["trend"], "vol_tier": ch["vol_tier"],
            "confidence": round(conf, 3),
            "leverage_multiplier": ch["leverage_multiplier"],
            "risk_multiplier": ch["leverage_multiplier"],
            "hmm_state": j, "gmm_regime": gmm_label, "hmm_gmm_agree": agree,
            "n_states": self.k,
        }
