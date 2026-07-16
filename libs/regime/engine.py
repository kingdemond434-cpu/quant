"""Regime engine -- fits HMM + GMM, characterises the latent states into market regimes, and emits
the live regime with confidence and the risk / leverage multipliers every downstream module reads.

A latent state is just an index; this maps it onto an economically meaningful label (bull/bear x
vol tier) from the real per-state mean return and volatility, then derives a LEVERAGE MULTIPLIER
that only de-risks (<=1.0): smaller in high-vol / bear regimes, full in calm bull regimes. The HMM
(temporal) and GMM (clustering) are cross-checked -- agreement => high confidence.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from libs.regime.bayesian import BayesianRegimeFilter
from libs.regime.features import regime_features
from libs.regime.gmm import fit_gmm
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
    for j in range(k):
        trend = "bull" if stats[j]["mean_ret"] >= 0 else "bear"
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
        """Live regime: HMM state label, confidence, GMM agreement, leverage multiplier."""
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
        return {
            "regime": ch["label"], "trend": ch["trend"], "vol_tier": ch["vol_tier"],
            "confidence": round(conf, 3),
            "leverage_multiplier": ch["leverage_multiplier"],
            "risk_multiplier": ch["leverage_multiplier"],
            "hmm_state": j, "gmm_regime": gmm_label, "hmm_gmm_agree": agree,
            "n_states": self.k,
        }
