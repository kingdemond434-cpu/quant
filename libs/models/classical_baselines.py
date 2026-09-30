"""Dependency-light classical baselines shared by scheduled research organs."""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

import numpy as np


def nelder_mead(fn: Callable[[np.ndarray], float], x0: np.ndarray, *, iters: int = 300,
                step: float = 0.2) -> tuple[np.ndarray, float]:
    """Deterministic unconstrained Nelder-Mead returning ``(argmin, minimum)``."""
    x = np.asarray(x0, dtype=float)
    simplex = [x.copy()]
    for i in range(x.size):
        point = x.copy()
        point[i] += step
        simplex.append(point)
    values = [float(fn(point)) for point in simplex]
    for _ in range(max(1, int(iters))):
        order = np.argsort(values)
        simplex = [simplex[int(i)] for i in order]
        values = [values[int(i)] for i in order]
        centroid = np.mean(simplex[:-1], axis=0)
        reflected = centroid + centroid - simplex[-1]
        reflected_value = float(fn(reflected))
        if values[0] <= reflected_value < values[-2]:
            simplex[-1], values[-1] = reflected, reflected_value
            continue
        if reflected_value < values[0]:
            expanded = centroid + 2.0 * (reflected - centroid)
            expanded_value = float(fn(expanded))
            simplex[-1], values[-1] = ((expanded, expanded_value)
                                        if expanded_value < reflected_value
                                        else (reflected, reflected_value))
            continue
        contracted = centroid + 0.5 * (simplex[-1] - centroid)
        contracted_value = float(fn(contracted))
        if contracted_value < values[-1]:
            simplex[-1], values[-1] = contracted, contracted_value
            continue
        best = simplex[0]
        simplex = [best] + [best + 0.5 * (point - best) for point in simplex[1:]]
        values = [float(fn(point)) for point in simplex]
    winner = int(np.argmin(values))
    return simplex[winner], values[winner]


class BetaBinary:
    """Beta-Bernoulli reference with an explicit fitted state and mean log score."""

    def __init__(self, alpha: float = 0.5, beta: float = 0.5) -> None:
        self.alpha0, self.beta0 = float(alpha), float(beta)
        self.state: dict[str, Any] = {"fitted": False}

    def fit(self, y: Sequence[float]) -> BetaBinary:
        values = np.asarray(y, dtype=float)
        values = values[np.isfinite(values)]
        if values.size == 0:
            self.state = {"fitted": False, "why": "no finite outcomes"}
            return self
        wins = float(np.sum(values > 0.5))
        alpha = self.alpha0 + wins
        beta = self.beta0 + float(values.size) - wins
        self.state = {"fitted": True, "n": int(values.size), "alpha": alpha, "beta": beta,
                      "p": alpha / (alpha + beta)}
        return self

    def score(self, y: Sequence[float]) -> float:
        if not self.state.get("fitted"):
            return float("nan")
        p = min(1.0 - 1e-9, max(1e-9, float(self.state["p"])))
        values = np.asarray(y, dtype=float)
        values = values[np.isfinite(values)]
        return float(np.mean((values > 0.5) * math.log(p)
                             + (values <= 0.5) * math.log(1.0 - p)))


def _seconds(value: Any) -> float:
    if isinstance(value, np.datetime64):
        return float(value.astype("datetime64[ns]").astype(np.int64)) / 1e9
    if isinstance(value, datetime):
        return value.timestamp()
    return float(value)


class HawkesIntensity:
    """Exponential Hawkes reference fitted by a small deterministic likelihood grid."""

    def __init__(self) -> None:
        self.state: dict[str, Any] = {"fitted": False, "verdict": "UNMEASURED"}

    def fit(self, event_times: Sequence[Any]) -> HawkesIntensity:
        try:
            times = np.asarray(sorted({_seconds(value) for value in event_times}), dtype=float)
        except (TypeError, ValueError, OverflowError):
            self.state = {"fitted": False, "verdict": "UNMEASURED",
                          "why": "event times are not numeric/datetime"}
            return self
        if times.size < 3 or not np.all(np.isfinite(times)) or times[-1] <= times[0]:
            self.state = {"fitted": False, "verdict": "UNMEASURED",
                          "why": f"{int(times.size)} usable event times; need at least 3"}
            return self
        times = times - times[0]
        duration = float(times[-1])
        rate = float(times.size) / duration
        median_dt = max(float(np.median(np.diff(times))), duration / (1000 * times.size), 1e-9)
        beta0 = math.log(2.0) / median_dt
        best: tuple[float, float, float, float] | None = None
        for beta in (beta0 / 4, beta0 / 2, beta0, beta0 * 2, beta0 * 4):
            for branching in np.linspace(0.0, 0.95, 40):
                mu = max(1e-12, (1.0 - float(branching)) * rate)
                alpha = float(branching) * beta
                excitation = loglik = previous = 0.0
                for stamp in times:
                    excitation *= math.exp(-beta * max(0.0, float(stamp) - previous))
                    loglik += math.log(max(1e-12, mu + alpha * excitation))
                    excitation += 1.0
                    previous = float(stamp)
                integral = mu * duration + (alpha / beta) * float(
                    np.sum(1.0 - np.exp(-beta * (duration - times))))
                candidate = (integral - loglik, float(branching), beta, mu)
                if best is None or candidate[0] < best[0]:
                    best = candidate
        assert best is not None
        nll, branching, beta, mu = best
        self.state = {"fitted": True, "verdict": "MEASURED", "n_events": int(times.size),
                      "branching_ratio": branching, "decay_halflife": math.log(2.0) / beta,
                      "mu": mu, "alpha": branching * beta, "beta": beta, "loglik": -nll}
        return self
