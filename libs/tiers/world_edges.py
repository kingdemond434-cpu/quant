"""THE MARKET WORLD MODEL'S EDGE LIFE-CYCLE AND STRUCTURAL RESIDUALS (Tier S layer 3).

`desks/mt5/research/world_causal_graph.py` estimates lagged edges between markets. It does not say
whether an edge is STABLE, STATE-DEPENDENT, DECAYING or FALSE -- and it does not turn a broken
relationship into a hypothesis. This does both, from return panels alone:

  CLASSIFY. For each (driver -> target, lag) the relationship's coefficient is estimated in rolling
  windows and within states (a volatility regime of the driver):

      FALSE            the full-sample coefficient is insignificant after a Bonferroni charge
      STABLE           significant, the same sign in >= 80% of windows, no trend in magnitude
      DECAYING         significant early, the recent third's |beta| under half the first third's
      STATE_DEPENDENT  significant in one state and not in the other (or opposite signs)

  RESIDUALS. For every STABLE edge the model predicts the target from the driver; when the recent
  residual is extreme (|z| above a threshold) the relationship is BROKEN right now. A broken
  expected relationship is a hypothesis source that is not an indicator: "the target has not
  responded the way it always has -- does the residual predict the target's next move (catch-up)
  or the driver's (the driver was wrong)?" Each such residual is emitted as a structured hypothesis
  row for the desk's compiler to test.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import numpy.typing as npt

F = npt.NDArray[np.float64]


def _beta_t(x: F, y: F) -> tuple[float, float]:
    if len(x) < 10 or x.std() == 0 or y.std() == 0:
        return 0.0, 0.0
    xc, yc = x - x.mean(), y - y.mean()
    b = float(xc @ yc / (xc @ xc))
    resid = yc - b * xc
    s2 = float(resid @ resid) / max(1, len(x) - 2)
    se = math.sqrt(s2 / float(xc @ xc)) if s2 > 0 else 1e-12
    return b, b / se


def classify_edge(x: F, y: F, lag: int, *, n_tests: int = 1, windows: int = 6,
                  z_crit: float = 1.96) -> dict[str, Any]:
    if lag > 0:
        x, y = x[:-lag], y[lag:]
    n = min(len(x), len(y))
    x, y = x[:n], y[:n]
    b, t = _beta_t(x, y)
    # Bonferroni over the edges examined: the full-sample bar rises with the search
    from scipy.stats import norm
    bar = float(norm.ppf(1 - 0.025 / max(1, n_tests)))
    if abs(t) < bar:
        return {"class": "FALSE", "beta": b, "t": t, "bar": bar}
    chunks = np.array_split(np.arange(n), windows)
    betas = [_beta_t(x[c], y[c])[0] for c in chunks if len(c) >= 10]
    same = sum(1 for bb in betas if np.sign(bb) == np.sign(b)) / max(1, len(betas))
    third = max(1, len(betas) // 3)
    early = float(np.mean(np.abs(betas[:third]))) if betas else 0.0
    late = float(np.mean(np.abs(betas[-third:]))) if betas else 0.0
    vol = np.abs(x)
    hi = vol > np.median(vol)
    b_hi, t_hi = _beta_t(x[hi], y[hi])
    b_lo, t_lo = _beta_t(x[~hi], y[~hi])
    state_dep = (abs(t_hi) >= z_crit) != (abs(t_lo) >= z_crit) or (
        abs(t_hi) >= z_crit and abs(t_lo) >= z_crit and np.sign(b_hi) != np.sign(b_lo))
    if early > 0 and late < 0.5 * early:
        cls = "DECAYING"
    elif state_dep:
        cls = "STATE_DEPENDENT"
    elif same >= 0.8:
        cls = "STABLE"
    else:
        cls = "STATE_DEPENDENT"
    return {"class": cls, "beta": round(b, 6), "t": round(t, 3), "bar": round(bar, 3),
            "sign_consistency": round(same, 3), "early_abs_beta": round(early, 6),
            "late_abs_beta": round(late, 6), "beta_high_vol": round(b_hi, 6),
            "beta_low_vol": round(b_lo, 6)}


def classify_all(panel: Mapping[str, F], lags: Sequence[int] = (0, 1),
                 max_pairs: int = 400) -> list[dict[str, Any]]:
    names = sorted(panel)
    pairs = [(a, b, lag) for a in names for b in names if a != b for lag in lags][:max_pairs]
    out = []
    for a, b, lag in pairs:
        res = classify_edge(panel[a], panel[b], lag, n_tests=len(pairs))
        out.append({"driver": a, "target": b, "lag": lag, **res})
    return out


def residuals(panel: Mapping[str, F], edges: Sequence[Mapping[str, Any]], *,
              recent: int = 5, z_break: float = 2.5) -> list[dict[str, Any]]:
    """Broken STABLE relationships right now, as hypothesis rows."""
    out = []
    for e in edges:
        if e.get("class") != "STABLE":
            continue
        x, y = panel[str(e["driver"])], panel[str(e["target"])]
        lag = int(e["lag"])
        if lag > 0:
            x, y = x[:-lag], y[lag:]
        n = min(len(x), len(y))
        x, y = x[:n], y[:n]
        if n < 60:
            continue
        b = float(e["beta"])
        resid = y - (y.mean() + b * (x - x.mean()))
        sd = float(resid[:-recent].std()) or 1e-12
        z = float(resid[-recent:].sum() / (sd * math.sqrt(recent)))
        if abs(z) >= z_break:
            out.append({"kind": "hypothesis", "family": "structural_residual",
                        "mechanism": "broken_expected_relationship",
                        "symbols": [str(e["target"]), str(e["driver"])],
                        "driver": e["driver"], "target": e["target"], "lag": lag,
                        "beta": b, "residual_z": round(z, 3),
                        "claim": (f"{e['target']} has not responded to {e['driver']} as it has "
                                  f"(beta {b:+.3f}, lag {lag}); residual z {z:+.2f}. Test "
                                  f"catch-up in {e['target']} and reversal in {e['driver']}."),
                        "falsifier": "the residual does not predict either leg's next move "
                                     "beyond the lifetime online-FDR level"})
    out.sort(key=lambda r: -abs(float(r["residual_z"])))
    return out


def census(edges: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for e in edges:
        c = str(e.get("class"))
        out[c] = out.get(c, 0) + 1
    return out
