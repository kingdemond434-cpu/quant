"""The fourteen traditions, each a parallel scientist attacking the same residual.

ONE INTERFACE, FOURTEEN MATHEMATICS. Every scientist implements

    propose(panel, budget_s, rng) -> list[MathObject]

and reports, by name, what it could NOT measure (`self.unmeasured`) and how large its search
actually was (`self.evaluated`, `self.distinct`) so `burden` can charge it. A scientist that finds
nothing and says why is doing its job; a scientist that returns [] in silence is a defect.

THE EXECUTABLE PROJECTION, and why every tradition has one. A tradition's native object often
reads a state variable it invented this hour -- a Hawkes intensity, a graph eigenvalue, a
persistence entropy. `mt5desk.family_formula` can only be handed the desk's own bar terminals, so
an object over a minted column is a REGISTERED DISCOVERY and not a tradeable recipe. Each
scientist therefore also emits at least one object expressed purely over bar terminals whose
WINDOWS AND SIGN ITS OWN NUMERICS CHOSE -- the spectral scientist's band edges come from its
Welch peak, the control scientist's lags from its ARX fit, the transport scientist's window from
where the distribution actually moved. The invention is not weakened into a moving-average
crossover; the crossover's parameters are the invention's output, and the gap between the two is
named in the object's notes rather than hidden.

NO NEW DEPENDENCIES. numpy and scipy only (pandas is never needed here). Every heavy step is
bounded by a subsample cap and a deadline, because this runs on the box that holds the live
terminal and an unbounded pairwise distance matrix is how a research organ takes a trading box
down.
"""
from __future__ import annotations

import math
import time
from typing import Any

import numpy as np

from . import grammar as G
from .base import (
    CLOUD_CAP,
    UNMEASURED,
    Scientist,
    _corr,
    _finite,
    _nearest_window,
    _quiet,
    _z,
)
from .objects import MathObject, Panel, Variable
from .physics import PHYSICS_CORE_REGISTRY
from .physics_ext import PHYSICS_EXT_REGISTRY
from .scientists_ext import EXTRA_REGISTRY, EXTRA_TRADITIONS

#: The principal's fourteen, in his order, then the second cohort from his sandbox lists
#: (2026-09-22). `math_lab` reads this for the allocation floor.
CORE_TRADITIONS: tuple[str, ...] = (
    "symbolic_regression", "dynamical_systems", "stochastic_processes", "spectral",
    "information_theory", "geometry", "optimal_transport", "graph_theory", "topology",
    "causal", "combinatorics", "control_theory", "game_theory_ecology", "meta_mathematics",
)
TRADITIONS: tuple[str, ...] = CORE_TRADITIONS + EXTRA_TRADITIONS

# =============================================================== 1. symbolic regression / GP
class SymbolicRegression(Scientist):
    """Invent f(x1, x2, ...) by genetic programming over the grammar, not select from a menu.

    Fitness is the VALIDATION t-statistic minus an MDL charge, measured on an inner split of the
    training slice so the held-out slice `burden` judges on is never touched by the search. That
    separation is the entire difference between this and curve fitting.
    """

    tradition = "symbolic_regression"
    searches_for = ("relationship", "representation")

    POPULATION = 48
    ELITES = 6

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        pool = self.top_columns(panel, 12)
        train, _ = panel.split()
        inner = int(train.size * 0.7)
        fit_idx, val_idx = train[:inner], train[inner:]
        if val_idx.size < 60:
            self.note("inner_validation", f"{val_idx.size} rows after the inner split; "
                                          "the GP cannot separate fit from selection")
            return []

        def fitness(tree: Any) -> float:
            self.charge(tree)
            values = G.evaluate(tree, panel.columns, panel.n)
            # DEFINED ON BOTH HALVES OR NOT AT ALL: an expression whose warm-up eats the fit slice
            # would be selected on validation rows alone, which is selection without a sample.
            if int(np.isfinite(values[fit_idx]).sum()) < max(30, fit_idx.size // 4):
                return -9.9
            r = abs(_corr(values[val_idx], panel.epsilon[val_idx]))
            if not math.isfinite(r) or r <= 0.0:
                return -9.9
            t = r * math.sqrt(max(3.0, val_idx.size) - 2.0) / math.sqrt(max(1e-9, 1 - r * r))
            return t - 0.45 * math.sqrt(2.0 * math.log(1.0 + G.nodes(tree) + G.parameters(tree)))

        # A HALL OF FAME ACROSS GENERATIONS, not the last population. A GP converges: by
        # generation twenty the population is one expression and its near-clones, and reading the
        # answer off the final generation throws away the best tree the search ever held. The
        # fame table keeps the best DISTINCT canonical forms whenever they appear.
        fame: dict[str, float] = {}
        trees: dict[str, Any] = {}
        # A SECOND TABLE FOR TRADEABLE TREES, filtered from the SAME evaluations (no extra
        # search, no extra charge): the best invention the formula family can actually be handed
        # -- bar terminals only, no threshold/log/sqrt/constant, inside alpha_grammar's depth and
        # unit algebra -- must reach the output even when a dataset column wins the open table.
        bar_fame: dict[str, float] = {}
        bar_only = set(self.bar_columns(panel))

        def remember(tree: Any, score: float) -> None:
            key = G.to_str(G.simplify(tree))
            if G.nodes(tree) >= 2 and score > fame.get(key, -math.inf):
                fame[key] = score
                trees[key] = tree
                if G.variables_in(tree) <= bar_only and score > bar_fame.get(key, -math.inf) \
                        and G.tradeable(tree)[0] is not None:
                    bar_fame[key] = score

        population = [G.random_expr(rng, pool, 3) for _ in range(self.POPULATION)]
        scored = [(fitness(t), t) for t in population]
        for tree, (score, _) in zip(population, scored, strict=False):
            remember(tree, score)
        generations = 0
        while time.monotonic() < deadline and generations < 24:
            generations += 1
            scored.sort(key=lambda r: -r[0])
            elites = [t for _, t in scored[:self.ELITES]]
            children: list[Any] = list(elites)
            # IMMIGRATION, deliberately. A quarter of every generation is a fresh draw, because a
            # population bred only from its own elites stops searching and starts polishing.
            immigrants = max(1, self.POPULATION // 4)
            while len(children) < self.POPULATION and time.monotonic() < deadline:
                if len(children) >= self.POPULATION - immigrants:
                    children.append(G.random_expr(rng, pool, 3))
                    continue
                a = self._tournament(scored, rng)
                if rng.random() < 0.5:
                    children.append(G.crossover(a, self._tournament(scored, rng), rng))
                else:
                    children.append(G.mutate(a, rng, pool))
            scored = [(fitness(t), t) for t in children]
            for tree, (score, _) in zip(children, scored, strict=False):
                remember(tree, score)

        out: list[MathObject | None] = []
        ordered = sorted(fame, key=lambda k: -fame[k])[:4]
        best_bar = max(bar_fame, key=lambda k: bar_fame[k]) if bar_fame else None
        if best_bar is not None and best_bar not in ordered:
            ordered.append(best_bar)
        for key in ordered:
            if fame[key] <= 0.0:
                continue
            tree = trees[key]
            direction = _corr(G.evaluate(tree, panel.columns, panel.n)[val_idx],
                              panel.epsilon[val_idx])
            obj = self.emit(
                panel, "relationship", tree,
                f"E[eps_t | {key}] separates on the validation slice with IC {direction:+.4f}; "
                f"the expression was INVENTED by genetic programming over "
                f"{len(pool)} panel variables, not selected from a feature menu",
                side_mode="follow" if direction >= 0 else "fade",
                diagnostics={"generations": generations, "population": self.POPULATION,
                             "hall_of_fame": len(fame), "bar_only_hall_of_fame": len(bar_fame),
                             "validation_t": round(fame[key], 4), "pool": pool,
                             "bar_only": key == best_bar})
            if obj is not None:
                out.append(obj)
        if best_bar is None:
            self.note("tradeable_expression", "no tree the formula family could be handed earned "
                                              "a place in the hall of fame; every winner used a "
                                              "dataset column, a threshold, a log or a constant")
        if not out:
            self.note("symbolic_search", f"{generations} generations over {len(fame)} distinct "
                                         "canonical forms produced no expression with positive "
                                         "complexity-penalised validation evidence")
        return out

    @staticmethod
    def _tournament(scored: list[tuple[float, Any]], rng: np.random.Generator, size: int = 3
                    ) -> Any:
        """Best of `size` uniform draws: selection pressure without collapsing the population."""
        picks = [scored[int(rng.integers(len(scored)))] for _ in range(max(1, size))]
        return max(picks, key=lambda r: r[0])[1]


# ================================================================= 2. dynamical systems
class DynamicalSystems(Scientist):
    """Takens embedding, recurrence quantification and a Lyapunov exponent proxy.

    The question is whether the residual path lives on a low-dimensional attractor: if states that
    were close stay close, the next move is partly determined by where the system IS rather than
    by what just happened, and `recurrence_density` is that state made into a column.
    """

    tradition = "dynamical_systems"
    searches_for = ("representation", "law", "mechanism")

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        series = _finite(panel.epsilon)
        tau = self._first_min_acf(series)
        dim = 3
        cloud, index = self._embed(series, dim, tau)
        if cloud.shape[0] < 120:
            self.note("takens_embedding", f"{cloud.shape[0]} embedded points at dim {dim} "
                                          f"lag {tau}; a longer panel would measure it")
            return []
        step = max(1, cloud.shape[0] // CLOUD_CAP)
        sub = cloud[::step]
        dist = np.sqrt(((sub[:, None, :] - sub[None, :, :]) ** 2).sum(-1))
        eps = float(np.percentile(dist[dist > 0], 10)) if (dist > 0).any() else 0.0
        recurrent = (dist <= eps) & (dist > 0)
        rate = float(recurrent.mean())
        determinism = self._determinism(recurrent)
        lyap = self._lyapunov(sub, dist, eps)

        density = self._recurrence_density(series, dim, tau, eps, index, panel.n)
        name = panel.mint("recurrence_density", density,
                          Variable(name="recurrence_density", dataset="mathlab:recurrence",
                                   source="derived", units="fraction of past states within eps"))
        self.minted.append(name)
        diagnostics = {"embedding_dim": dim, "lag": tau, "recurrence_rate": round(rate, 6),
                       "determinism": round(determinism, 6),
                       "lyapunov_proxy": None if lyap is None else round(lyap, 6),
                       "epsilon_radius": round(eps, 8), "points": int(sub.shape[0])}
        if lyap is None:
            self.note("lyapunov_proxy", "no neighbour pair stayed measurable for 8 steps")

        out = [
            self.emit(panel, "representation", ["z", name, 240],
                      f"a NEW STATE VARIABLE: the fraction of the last 240 phase-space states "
                      f"within {eps:.4g} of the current one, from a dim-{dim} lag-{tau} Takens "
                      f"embedding of the residual (recurrence rate {rate:.4f}, determinism "
                      f"{determinism:.4f})", diagnostics=diagnostics),
            self.emit(panel, "law", ["curv", "close", _nearest_window(max(2, tau))],
                      f"CURVATURE, not level: x_t - 2 x_(t-{tau}) + x_(t-{2 * tau}) is the "
                      f"discrete second derivative along the trajectory, and the embedding says "
                      f"the attractor's lag is {tau}", diagnostics=diagnostics),
        ]
        if time.monotonic() < deadline:
            tree, notes = self.projection(panel, 240, fast=max(2, tau),
                                          why=f"lag {tau} is the first autocorrelation minimum "
                                              f"of the residual path")
            out.append(self.emit(panel, "mechanism", tree,
                                 "the attractor's own lag, traded through bar terminals",
                                 diagnostics=diagnostics, notes=notes))
        _ = rng
        return out

    @staticmethod
    def _first_min_acf(series: np.ndarray, max_lag: int = 48) -> int:
        best, value = 1, math.inf
        for lag in range(1, min(max_lag, series.size // 4)):
            r = _corr(series[lag:], series[:-lag])
            if r < value:
                best, value = lag, r
            elif r > value:
                break
        return max(1, best)

    @staticmethod
    def _embed(series: np.ndarray, dim: int, tau: int) -> tuple[np.ndarray, np.ndarray]:
        span = (dim - 1) * tau
        if series.size <= span + 8:
            return np.empty((0, dim)), np.empty(0, dtype=int)
        rows = series.size - span
        cloud = np.column_stack([series[i * tau:i * tau + rows] for i in range(dim)])
        return cloud, np.arange(span, series.size)

    @staticmethod
    def _determinism(recurrent: np.ndarray, min_line: int = 2) -> float:
        total = int(recurrent.sum())
        if total == 0:
            return 0.0
        on_line = 0
        n = recurrent.shape[0]
        for offset in range(1, n):
            diag = np.diagonal(recurrent, offset)
            run = 0
            for value in diag:
                run = run + 1 if value else 0
                if run >= min_line:
                    on_line += 1
        return float(2 * on_line / total)

    @staticmethod
    def _lyapunov(cloud: np.ndarray, dist: np.ndarray, eps: float, horizon: int = 8
                  ) -> float | None:
        n = cloud.shape[0]
        if n < horizon + 10 or eps <= 0:
            return None
        masked = dist + np.eye(n) * 1e9
        neighbour = np.argmin(masked, axis=1)
        rates: list[float] = []
        for i in range(n - horizon):
            j = int(neighbour[i])
            if j >= n - horizon:
                continue
            d0 = float(dist[i, j])
            d1 = float(np.linalg.norm(cloud[i + horizon] - cloud[j + horizon]))
            if d0 > 1e-12 and d1 > 1e-12:
                rates.append(math.log(d1 / d0) / horizon)
        return float(np.mean(rates)) if len(rates) >= 20 else None

    @staticmethod
    def _recurrence_density(series: np.ndarray, dim: int, tau: int, eps: float,
                            index: np.ndarray, n: int, look: int = 240) -> np.ndarray:
        out = np.full(n, np.nan, dtype=float)
        cloud, _ = DynamicalSystems._embed(series, dim, tau)
        if cloud.shape[0] == 0 or eps <= 0:
            return out
        for position in range(1, cloud.shape[0]):
            start = max(0, position - look)
            past = cloud[start:position]
            d = np.sqrt(((past - cloud[position]) ** 2).sum(-1))
            row = int(index[position]) if position < index.size else None
            if row is not None and row < n:
                out[row] = float((d <= eps).mean())
        return out


# =============================================================== 3. stochastic processes
class StochasticProcesses(Scientist):
    """OU half-life, bipower jump detection, and a Hawkes intensity fitted by MLE on event times.

    Three latent processes, three objects: a mean-reverting level with a measured half-life, a
    jump component separated from diffusion by bipower variation, and a SELF-EXCITING intensity
    whose branching ratio says how much of the next event is caused by the last one.
    """

    tradition = "stochastic_processes"
    searches_for = ("mechanism", "representation", "law")

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        eps = _finite(panel.epsilon)
        rho = [_corr(eps[k:], eps[:-k]) for k in range(1, 7)]
        rho1, rho2 = rho[0], rho[1]
        # NOISE-ROBUST, ON PURPOSE. A mean-reverting level observed through independent noise is
        # ARMA(1,1), and its lag-1 autocorrelation is the OU coefficient SHRUNK by the noise
        # share; the ratio rho(k+1)/rho(k) cancels the shrinkage, because every rho(k) for k >= 1
        # is c * phi^k. The MEDIAN of the ratios over k = 1..5 also survives a short moving-
        # average contamination (a shock that feeds back at lag 3 corrupts one ratio, not the
        # median). The raw lag-1 value is reported beside it, never instead of it.
        ratios = [rho[k + 1] / rho[k] for k in range(5)
                  if rho[k] > 0.05 and rho[k + 1] > 0.0 and rho[k + 1] / rho[k] < 1.0]
        phi = float(np.median(ratios)) if ratios else rho1
        half_life = (-math.log(2.0) / math.log(phi)) if 0.0 < phi < 1.0 else None
        if half_life is None:
            self.note("ou_half_life", f"OU coefficient {phi:.4f} is outside (0, 1); the "
                                      "residual is not mean-reverting at this horizon")

        ret = panel.columns.get("ret")
        jumps: np.ndarray | None = None
        bpv = None
        if ret is None:
            self.note("bipower_variation", "the panel carries no `ret` column")
        else:
            r = _finite(ret)
            absr = np.abs(r)
            with _quiet():
                bpv_series = (math.pi / 2.0) * G.evaluate(
                    ["rmean", "__x__", 48],
                    {"__x__": absr * np.concatenate([[0.0], absr[:-1]])}, r.size)
                threshold = 3.0 * np.sqrt(np.maximum(bpv_series, 1e-18))
                jumps = (absr > threshold) & np.isfinite(threshold)
                bpv = float(np.nanmean(bpv_series))

        hawkes: dict[str, Any] = {"status": UNMEASURED}
        intensity: np.ndarray | None = None
        if jumps is not None and int(jumps.sum()) >= 25:
            hawkes, intensity = self._hawkes(np.flatnonzero(jumps).astype(float), panel.n)
        elif jumps is not None:
            self.note("hawkes_fit", f"{int(jumps.sum())} jump events, fewer than the 25 a "
                                    "self-exciting intensity can be identified from")

        diagnostics = {"ar1": round(rho1, 6), "ar2": round(rho2, 6), "ou_phi": round(phi, 6),
                       "autocorrelation": [round(r, 6) for r in rho],
                       "ou_estimator": "median of rho(k+1)/rho(k), k=1..5: robust to observation "
                                       "noise and to a short MA contamination",
                       "ou_half_life_bars": None if half_life is None else round(half_life, 4),
                       "bipower_variation": bpv,
                       "n_jumps": None if jumps is None else int(jumps.sum()),
                       "hawkes": hawkes}

        out: list[MathObject | None] = []
        window = _nearest_window(half_life * 4) if half_life else 48
        out.append(self.emit(
            panel, "mechanism", ["neg", ["z", "ret", window]],
            f"AN ORNSTEIN-UHLENBECK LEVEL: the residual's OU coefficient is {phi:.4f} (lag-1 "
            f"autocorrelation {rho1:.4f}), a "
            f"half-life of {half_life if half_life else float('nan'):.2f} bars, so the "
            f"{window}-bar z-score is faded", side_mode="follow", diagnostics=diagnostics))
        if intensity is not None:
            name = panel.mint("hawkes_intensity", intensity,
                              Variable(name="hawkes_intensity", dataset="mathlab:hawkes",
                                       source="derived", units="conditional event intensity"))
            self.minted.append(name)
            out.append(self.emit(
                panel, "representation", ["z", name, 240],
                f"A LATENT PROCESS AS A COLUMN: the conditional intensity of a self-exciting "
                f"jump process fitted by maximum likelihood on {int(jumps.sum())} bipower jump "
                f"times, branching ratio {hawkes.get('branching_ratio')}", diagnostics=diagnostics))
        if time.monotonic() < deadline:
            tree, notes = self.projection(panel, window, fast=max(2, int(half_life or 4)),
                                          why=f"the window is 4 OU half-lives ({window} bars)")
            out.append(self.emit(panel, "law", tree,
                                 "the fitted half-life, traded through bar terminals",
                                 diagnostics=diagnostics, notes=notes))
        _ = rng
        return out

    def _hawkes(self, events: np.ndarray, n: int) -> tuple[dict[str, Any], np.ndarray | None]:
        """Exponential-kernel Hawkes by MLE: lambda(t) = mu + sum alpha exp(-beta (t - t_i))."""
        horizon = float(n)

        def neg_loglik(theta: np.ndarray) -> float:
            mu, alpha, beta = np.exp(theta)
            if not np.isfinite([mu, alpha, beta]).all() or beta <= 1e-9:
                return 1e12
            total, state, previous = 0.0, 0.0, 0.0
            for t in events:
                state = (state + 1.0) * math.exp(-beta * (t - previous)) if previous else 0.0
                previous = t
                rate = mu + alpha * state
                if rate <= 1e-12:
                    return 1e12
                total += math.log(rate)
            compensator = mu * horizon + (alpha / beta) * float(
                np.sum(1.0 - np.exp(-beta * (horizon - events))))
            return float(compensator - total)

        try:
            from scipy.optimize import minimize
        except Exception as exc:
            self.note("hawkes_fit", f"scipy.optimize unavailable ({type(exc).__name__})")
            return {"status": UNMEASURED, "why": "scipy.optimize unavailable"}, None
        start = np.log([max(1e-6, events.size / horizon), 0.4, 0.08])
        result = minimize(neg_loglik, start, method="Nelder-Mead",
                          options={"maxiter": 400, "xatol": 1e-3, "fatol": 1e-3})
        mu, alpha, beta = (float(v) for v in np.exp(result.x))
        branching = alpha / beta if beta > 1e-9 else None
        detail = {"status": "MEASURED", "mu": round(mu, 8), "alpha": round(alpha, 8),
                  "beta": round(beta, 8),
                  "branching_ratio": None if branching is None else round(branching, 6),
                  "log_likelihood": round(-float(result.fun), 4), "n_events": int(events.size),
                  "stationary": bool(branching is not None and branching < 1.0),
                  "method": "Nelder-Mead MLE on the exact exponential-kernel log-likelihood"}
        series = np.full(n, np.nan, dtype=float)
        state, previous = 0.0, 0.0
        pointer = 0
        for t in range(n):
            while pointer < events.size and events[pointer] <= t:
                state = (state + 1.0) * math.exp(-beta * (events[pointer] - previous))
                previous = float(events[pointer])
                pointer += 1
            decay = math.exp(-beta * (t - previous)) if previous else 0.0
            series[t] = mu + alpha * state * decay
        return detail, series


# ======================================================================== 4. spectral
class Spectral(Scientist):
    """Welch band power and a Haar decomposition: where in FREQUENCY the residual lives.

    The output is not "there is a 24-hour cycle". It is a pair of window lengths straddling the
    measured peak, which is a band-pass filter the desk can actually trade, and the band powers
    that chose them.
    """

    tradition = "spectral"
    searches_for = ("representation", "relationship")

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        # TWO SERIES, ONE QUESTION. Periodic structure may live in the residual (what the world
        # model missed) or in the price path itself (what the residual is measured against);
        # both are scanned, and the series with the SHARPER peak -- the larger share of its own
        # power in the peak bin -- decides the band. Both readings ride in the diagnostics.
        candidates = {"epsilon": _finite(panel.epsilon)}
        if "ret" in panel.columns:
            candidates["ret"] = _finite(panel.columns["ret"])
        readings: dict[str, dict[str, Any]] = {}
        for label, series in candidates.items():
            spectrum = self._psd(series)
            if spectrum is None:
                continue
            freqs, power = spectrum
            peak_bin = int(np.argmax(power))
            readings[label] = {"freqs": freqs, "power": power,
                               "peak_period": float(1.0 / freqs[peak_bin]),
                               "sharpness": float(power[peak_bin] / (power.sum() or 1.0))}
        if not readings:
            self.note("spectrum", "no positive frequency bin in the residual or the price path")
            return []
        chosen = max(readings, key=lambda k: readings[k]["sharpness"])
        freqs, power = readings[chosen]["freqs"], readings[chosen]["power"]
        peak = readings[chosen]["peak_period"]
        total = float(power.sum()) or 1.0
        edges = [0.0, 1 / 48.0, 1 / 8.0, 0.5]
        bands = {f"period_{int(1 / max(edges[i + 1], 1e-9))}_to_"
                 f"{int(1 / max(edges[i], 1e-9)) if edges[i] else 'inf'}":
                 round(float(power[(freqs >= edges[i]) & (freqs < edges[i + 1])].sum() / total), 6)
                 for i in range(len(edges) - 1)}
        haar = self._haar_energy(series)
        diagnostics = {"peak_period_bars": round(peak, 3), "peak_series": chosen,
                       "peaks": {k: {"period_bars": round(v["peak_period"], 3),
                                     "sharpness": round(v["sharpness"], 6)}
                                 for k, v in readings.items()},
                       "band_share": bands, "haar_level_energy": haar,
                       "method": "Welch PSD on the residual AND the price path, the sharper peak "
                                 "deciding the band, plus a Haar multiresolution energy ladder"}

        slow = _nearest_window(peak)
        fast = _nearest_window(max(2.0, peak / 4.0))
        band = ["sub", ["rmean", "close", fast], ["rmean", "close", slow]]
        out = [
            self.emit(panel, "representation", band,
                      f"A BAND-PASS COORDINATE: the Welch peak sits at {peak:.1f} bars, so the "
                      f"{fast}-bar mean minus the {slow}-bar mean isolates the band the residual's "
                      f"power is actually in ({max(bands, key=lambda k: bands[k])} carries "
                      f"{max(bands.values()):.3f} of it)", diagnostics=diagnostics),
            self.emit(panel, "relationship", ["z", band, 240],
                      f"the band-pass coordinate normalised over 240 bars; Haar level energies "
                      f"{haar}", diagnostics=diagnostics),
        ]
        if time.monotonic() < deadline and "range" in panel.columns:
            out.append(self.emit(
                panel, "relationship", ["mul", ["sign", band], ["z", "range", slow]],
                f"the band's SIGN gated by the {slow}-bar dispersion state",
                diagnostics=diagnostics))
        _ = rng
        return out

    def _psd(self, series: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
        try:
            from scipy.signal import welch
            freqs, power = welch(series, nperseg=min(512, max(64, series.size // 8)))
        except Exception as exc:
            self.note("welch_psd", f"scipy.signal unavailable ({type(exc).__name__}); "
                                   "falling back to the raw periodogram")
            power = np.abs(np.fft.rfft(series - series.mean())) ** 2
            freqs = np.fft.rfftfreq(series.size)
        usable = freqs > 0
        if not usable.any():
            return None
        return freqs[usable], power[usable]

    @staticmethod
    def _haar_energy(series: np.ndarray, levels: int = 5) -> dict[str, float]:
        """Haar multiresolution energy, written out rather than imported: no new dependency."""
        signal = series.astype(float).copy()
        out: dict[str, float] = {}
        total = float((signal ** 2).sum()) or 1.0
        for level in range(1, levels + 1):
            if signal.size < 2:
                break
            even = signal[: signal.size - signal.size % 2].reshape(-1, 2)
            approx = even.sum(axis=1) / math.sqrt(2.0)
            detail = (even[:, 0] - even[:, 1]) / math.sqrt(2.0)
            out[f"level_{level}"] = round(float((detail ** 2).sum() / total), 6)
            signal = approx
        return out


# ================================================================ 5. information theory
class InformationTheory(Scientist):
    """Binned mutual information and transfer entropy, each against its own permutation null.

    MI asks whether a variable carries information about the residual AT ALL, linear or not.
    Transfer entropy asks whether it carries information the residual's OWN past does not already
    have -- which is the only version of the question worth an hour of the gauntlet's time.
    """

    tradition = "information_theory"
    searches_for = ("relationship", "law")

    BINS = 8
    PERMUTATIONS = 120

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        train, _ = panel.split()
        target = panel.epsilon
        scored: list[tuple[float, float, float, str]] = []
        for name in self.top_columns(panel, 14):
            if time.monotonic() >= deadline:
                self.note("information_scan", f"budget reached after {len(scored)} columns")
                break
            x, y = panel.columns[name][train], target[train]
            mi = self._mutual_information(x, y)
            te = self._transfer_entropy(panel.columns[name], target)
            p = self._permutation_p(x, y, mi, rng)
            self.charge(["z", name, 240])
            scored.append((mi, te, p, name))
        if not scored:
            self.note("mutual_information", "no column produced a measurable estimate")
            return []
        scored.sort(key=lambda r: -r[0])

        out: list[MathObject | None] = []
        for mi, te, p, name in scored[:3]:
            direction = _corr(panel.columns[name][train], target[train])
            diagnostics = {"mutual_information_nats": round(mi, 6),
                           "transfer_entropy_nats": None if te is None else round(te, 6),
                           "permutation_p": round(p, 5), "bins": self.BINS,
                           "null": f"{self.PERMUTATIONS} block permutations of the driver"}
            kind = "law" if (te is not None and te > 0 and p <= 0.05) else "relationship"
            out.append(self.emit(
                panel, kind, ["z", name, 240],
                f"I({name}; eps) = {mi:.5f} nats (p={p:.4f}); transfer entropy "
                f"{name} -> eps = {te if te is not None else float('nan'):.5f} nats, so the "
                f"variable carries information the residual's own past does not",
                side_mode="follow" if direction >= 0 else "fade", diagnostics=diagnostics))
        best = scored[0]
        tree, notes = self.projection(panel, 120, why=f"the highest-MI column was {best[3]}")
        out.append(self.emit(panel, "relationship", tree,
                             "the information-bearing state, traded through bar terminals",
                             diagnostics={"top_column": best[3]}, notes=notes))
        return out

    def _bin(self, values: np.ndarray) -> np.ndarray | None:
        v = np.asarray(values, dtype=float)
        v = v[np.isfinite(v)]
        if v.size < 64 or float(np.std(v)) < 1e-12:
            return None
        edges = np.quantile(np.asarray(values, dtype=float)[np.isfinite(values)],
                            np.linspace(0, 1, self.BINS + 1)[1:-1])
        return np.digitize(np.asarray(values, dtype=float), edges)

    def _mutual_information(self, x: np.ndarray, y: np.ndarray) -> float:
        mask = np.isfinite(x) & np.isfinite(y)
        bx, by = self._bin(x[mask]), self._bin(y[mask])
        if bx is None or by is None:
            return 0.0
        joint, _, _ = np.histogram2d(bx, by, bins=[self.BINS, self.BINS])
        joint = joint / max(1.0, joint.sum())
        px, py = joint.sum(1, keepdims=True), joint.sum(0, keepdims=True)
        with np.errstate(divide="ignore", invalid="ignore"):
            terms = joint * np.log(np.where(joint > 0, joint / np.maximum(px * py, 1e-15), 1.0))
        mi = float(np.nansum(np.where(joint > 0, terms, 0.0)))
        # Miller-Madow: the plug-in estimator is biased UP by (cells - 1) / (2 n).
        cells = int((joint > 0).sum())
        return max(0.0, mi - (cells - 1) / (2.0 * max(1, int(mask.sum()))))

    def _transfer_entropy(self, driver: np.ndarray, target: np.ndarray) -> float | None:
        """TE(X -> Y) = I(Y_t+1 ; X_t | Y_t), binned, as H(Y1|Y0) - H(Y1|Y0,X0)."""
        y1, y0, x0 = target[1:], target[:-1], driver[:-1]
        mask = np.isfinite(y1) & np.isfinite(y0) & np.isfinite(x0)
        if int(mask.sum()) < 200:
            return None
        bins = max(3, self.BINS // 2)
        by1, by0, bx0 = (self._quantile_bins(v[mask], bins) for v in (y1, y0, x0))
        joint = np.zeros((bins, bins, bins))
        np.add.at(joint, (by1, by0, bx0), 1.0)
        joint /= max(1.0, joint.sum())
        p_y0x0 = joint.sum(0)
        p_y1y0 = joint.sum(2)
        p_y0 = joint.sum((0, 2))
        with np.errstate(divide="ignore", invalid="ignore"):
            term = joint * np.log(
                np.where(joint > 0,
                         (joint * p_y0[None, :, None])
                         / np.maximum(p_y1y0[:, :, None] * p_y0x0[None, :, :], 1e-15), 1.0))
        return float(max(0.0, np.nansum(np.where(joint > 0, term, 0.0))))

    @staticmethod
    def _quantile_bins(values: np.ndarray, bins: int) -> np.ndarray:
        edges = np.quantile(values, np.linspace(0, 1, bins + 1)[1:-1])
        return np.clip(np.digitize(values, edges), 0, bins - 1)

    def _permutation_p(self, x: np.ndarray, y: np.ndarray, observed: float,
                       rng: np.random.Generator) -> float:
        n = x.size
        if n < 120:
            return 1.0
        hits = 0
        for _ in range(self.PERMUTATIONS):
            shift = int(rng.integers(24, max(25, n - 24)))
            if self._mutual_information(np.roll(x, shift), y) >= observed:
                hits += 1
        return float((hits + 1) / (self.PERMUTATIONS + 1))


# ======================================================================== 6. geometry
class Geometry(Scientist):
    """PCA intrinsic dimension and a local neighbourhood dimension: is the state space smaller?

    A market-state space with twenty columns and an intrinsic dimension of three has seventeen
    columns of redundancy, and the three coordinates that survive are a representation nobody
    wrote down. The principal component is FITTED ON THE TRAINING SLICE ONLY and applied forward,
    so the column is causal by construction.
    """

    tradition = "geometry"
    searches_for = ("representation", "law")

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        names = self.top_columns(panel, 12)
        matrix, names = panel.matrix(names)
        if matrix.shape[1] < 3:
            self.note("pca", f"{matrix.shape[1]} usable columns, fewer than the 3 an intrinsic "
                             "dimension can be estimated from")
            return []
        train, _ = panel.split()
        block = np.column_stack([_z(matrix[train, j]) for j in range(matrix.shape[1])])
        try:
            _, singular, right = np.linalg.svd(block, full_matrices=False)
        except np.linalg.LinAlgError as exc:
            self.note("pca", f"SVD did not converge ({type(exc).__name__})")
            return []
        variance = singular ** 2 / max(1e-12, float((singular ** 2).sum()))
        dim90 = int(np.searchsorted(np.cumsum(variance), 0.90) + 1)
        participation = float((variance.sum() ** 2) / max(1e-12, float((variance ** 2).sum())))
        local = self._local_dimension(block[::max(1, block.shape[0] // CLOUD_CAP)])
        if local is None:
            self.note("local_dimension", "fewer than 60 embedded points after subsampling")

        with _quiet():
            centre = np.nanmean(matrix[train], axis=0)
            scale = np.nanstd(matrix[train], axis=0)
        centre = np.nan_to_num(centre)
        scale = np.nan_to_num(scale)
        scale[scale < 1e-12] = 1.0
        pc1 = ((matrix - centre) / scale) @ right[0]
        name = panel.mint("pc1", pc1,
                          Variable(name="pc1", dataset="mathlab:pca",
                                   source="derived", units="first principal coordinate"))
        self.minted.append(name)
        loadings = {n: round(float(w), 5) for n, w in
                    sorted(zip(names, right[0], strict=False),
                           key=lambda r: -abs(r[1]))[:6]}
        diagnostics = {"columns": len(names), "dim90": dim90,
                       "participation_ratio": round(participation, 4),
                       "local_dimension": None if local is None else round(local, 4),
                       "explained_variance": [round(float(v), 5) for v in variance[:6]],
                       "pc1_loadings": loadings,
                       "fit": "SVD on the TRAINING slice only, applied forward"}
        out = [
            self.emit(panel, "representation", ["z", name, 240],
                      f"A HIDDEN LOW-DIMENSIONAL COORDINATE: {len(names)} market-state columns "
                      f"have intrinsic dimension {dim90} at 90% variance (participation ratio "
                      f"{participation:.2f}, local dimension "
                      f"{local if local is not None else float('nan'):.2f}); pc1 loads on "
                      f"{list(loadings)[:3]}", diagnostics=diagnostics),
            self.emit(panel, "law", ["curv", name, 24],
                      "the curvature of the manifold coordinate: where the state is ACCELERATING "
                      "along the low-dimensional direction, not where it sits",
                      diagnostics=diagnostics),
        ]
        if time.monotonic() < deadline:
            tree, notes = self.projection(panel, 240, why=f"intrinsic dimension {dim90}")
            out.append(self.emit(panel, "representation", tree,
                                 "the manifold coordinate, traded through bar terminals",
                                 diagnostics=diagnostics, notes=notes))
        _ = rng
        return out

    @staticmethod
    def _local_dimension(cloud: np.ndarray, k: int = 12) -> float | None:
        """Levina-Bickel maximum-likelihood intrinsic dimension from kNN distance ratios."""
        n = cloud.shape[0]
        if n < 60:
            return None
        dist = np.sqrt(((cloud[:, None, :] - cloud[None, :, :]) ** 2).sum(-1))
        dist.sort(axis=1)
        near = dist[:, 1:k + 1]
        with np.errstate(divide="ignore", invalid="ignore"):
            ratios = np.log(np.maximum(near[:, -1:], 1e-12) / np.maximum(near[:, :-1], 1e-12))
        per_point = (k - 2) / np.maximum(ratios.sum(axis=1), 1e-12)
        good = per_point[np.isfinite(per_point)]
        return float(np.median(good)) if good.size >= 20 else None


# =================================================================== 7. optimal transport
class OptimalTransport(Scientist):
    """1-D and sliced Wasserstein: what moved in the WHOLE DISTRIBUTION, not in the mean.

    A correlation that is stable while the distribution's tail doubles is a correlation about to
    stop being true. `w1_drift` is the distance between the last window's distribution and the
    one before it, computed causally and forward-filled between strides.
    """

    tradition = "optimal_transport"
    searches_for = ("representation", "law", "mechanism")

    WINDOW = 120
    STRIDE = 12

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        try:
            from scipy.stats import wasserstein_distance
        except Exception as exc:
            self.note("wasserstein", f"scipy.stats unavailable ({type(exc).__name__})")
            return []
        names = self.top_columns(panel, 8)
        regimes = panel.regime if panel.regime is not None else np.array(["all"] * panel.n)
        labels = [r for r in np.unique(regimes) if int((regimes == r).sum()) >= 120]
        by_regime: dict[str, float] = {}
        if len(labels) >= 2:
            for name in names:
                values = panel.columns[name]
                worst = 0.0
                for i, a in enumerate(labels):
                    for b in labels[i + 1:]:
                        left = values[(regimes == a) & np.isfinite(values)]
                        right = values[(regimes == b) & np.isfinite(values)]
                        if left.size >= 60 and right.size >= 60:
                            worst = max(worst, float(wasserstein_distance(
                                _z(left), _z(right))))
                by_regime[name] = round(worst, 6)
                self.charge(["z", name, self.WINDOW])
        else:
            self.note("regime_transport",
                      f"{len(labels)} regimes carry 120 rows; a regime-labelled residual store "
                      f"would measure the distributional shift")
        sliced = self._sliced(panel, names, rng)
        mover = max(by_regime, key=lambda k: by_regime[k]) if by_regime else names[0]

        drift = self._drift(panel.columns[mover], wasserstein_distance)
        name = panel.mint("w1_drift", drift,
                          Variable(name="w1_drift", dataset="mathlab:transport",
                                   source="derived",
                                   units=f"1-D Wasserstein between consecutive {self.WINDOW}-bar "
                                         f"windows of {mover}"))
        self.minted.append(name)
        diagnostics = {"regime_w1": by_regime, "sliced_w1_between_eras": sliced,
                       "largest_mover": mover, "window": self.WINDOW, "stride": self.STRIDE,
                       "method": "scipy.stats.wasserstein_distance; sliced W1 over 64 random "
                                 "projections of the standardised column matrix"}
        out = [
            self.emit(panel, "representation", ["z", name, 240],
                      f"A DISTRIBUTIONAL STATE VARIABLE: W1 between consecutive {self.WINDOW}-bar "
                      f"windows of {mover}, the column whose whole distribution moves most "
                      f"between regimes (W1 {by_regime.get(mover, float('nan')):.4f})",
                      diagnostics=diagnostics),
            self.emit(panel, "law", ["gt", ["z", name, 240], 1.5],
                      "AN INVARIANT WITH A SWITCH: the relation is claimed only while the "
                      "distribution is moving more than 1.5 sd faster than its own normal drift",
                      diagnostics=diagnostics),
        ]
        if time.monotonic() < deadline:
            tree, notes = self.projection(panel, self.WINDOW,
                                          why=f"the transport window is {self.WINDOW} bars and "
                                              f"{mover} is the largest mover")
            out.append(self.emit(panel, "mechanism", tree,
                                 "the distributional shift, traded through bar terminals",
                                 diagnostics=diagnostics, notes=notes))
        return out

    def _sliced(self, panel: Panel, names: list[str], rng: np.random.Generator,
                projections: int = 64) -> float | None:
        matrix, used = panel.matrix(names)
        if matrix.shape[1] < 2:
            self.note("sliced_wasserstein", "fewer than two columns to project")
            return None
        eras = panel.eras(2)
        first, second = matrix[eras == 0], matrix[eras == 1]
        if first.shape[0] < 60 or second.shape[0] < 60:
            return None
        try:
            from scipy.stats import wasserstein_distance
        except Exception:
            return None
        block_a = np.nan_to_num(first)
        block_b = np.nan_to_num(second)
        directions = rng.normal(size=(projections, len(used)))
        directions /= np.maximum(np.linalg.norm(directions, axis=1, keepdims=True), 1e-12)
        return round(float(np.mean([wasserstein_distance(block_a @ d, block_b @ d)
                                    for d in directions])), 6)

    def _drift(self, values: np.ndarray, distance: Any) -> np.ndarray:
        n = values.size
        out = np.full(n, np.nan, dtype=float)
        last = np.nan
        for t in range(2 * self.WINDOW, n):
            if (t - 2 * self.WINDOW) % self.STRIDE == 0:
                recent = values[t - self.WINDOW:t]
                prior = values[t - 2 * self.WINDOW:t - self.WINDOW]
                recent = recent[np.isfinite(recent)]
                prior = prior[np.isfinite(prior)]
                if recent.size >= 30 and prior.size >= 30:
                    last = float(distance(recent, prior))
            out[t] = last
        return out


# ====================================================================== 8. graph theory
class GraphTheory(Scientist):
    """Rolling correlation networks over the peers: synchronisation, centrality, communities.

    The principal's example lives here -- "a relation that exists only when a graph eigenvalue
    measuring cross-asset synchronisation crosses a threshold". `graph_sync` is the largest
    eigenvalue of the trailing correlation matrix divided by the node count, so 1.0 is one market
    moving as one asset and 1/k is k independent ones.
    """

    tradition = "graph_theory"
    searches_for = ("representation", "relationship", "mechanism")

    WINDOW = 120
    STRIDE = 8
    MIN_PEERS = 3

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        peers = {k: np.asarray(v, dtype=float) for k, v in panel.peers.items()
                 if np.asarray(v).size == panel.n}
        if len(peers) < self.MIN_PEERS:
            self.note("correlation_network", f"{len(peers)} peer series on the panel, fewer than "
                                             f"{self.MIN_PEERS}; the graph needs the hypothesis "
                                             f"universe's H1 bars for more symbols")
            return []
        names = sorted(peers)
        block = np.column_stack([peers[n] for n in names])
        sync, centrality, community = self._rolling(block, names, panel.target)
        minted = panel.mint("graph_sync", sync,
                            Variable(name="graph_sync", dataset="mathlab:graph", source="derived",
                                     units="largest correlation eigenvalue / node count"))
        self.minted.append(minted)
        panel.mint("graph_centrality", centrality,
                   Variable(name="graph_centrality", dataset="mathlab:graph", source="derived",
                            units="eigenvector centrality of the target node"))
        self.minted.append("graph_centrality")
        with _quiet():
            mean_sync = float(np.nanmean(sync))
            mean_centrality = float(np.nanmean(centrality))
        diagnostics = {"nodes": len(names), "window": self.WINDOW, "stride": self.STRIDE,
                       "mean_sync": round(mean_sync, 6),
                       "community_changes": int(community),
                       "mean_centrality": round(mean_centrality, 6),
                       "method": "largest eigenvalue and leading eigenvector of the trailing "
                                 "correlation matrix; community change = sign flips of the "
                                 "Fiedler partition between consecutive windows"}
        out = [
            self.emit(panel, "representation", ["z", minted, 240],
                      f"AN EVOLVING NETWORK AS A COLUMN: cross-asset synchronisation over "
                      f"{len(names)} nodes, mean {mean_sync:.4f}, "
                      f"{int(community)} community changes", diagnostics=diagnostics),
            self.emit(panel, "relationship",
                      ["mul", ["gt", ["z", minted, 240], 1.0], ["z", "ret", 24]],
                      "THE RELATION EXISTS ONLY ABOVE A THRESHOLD: the 24-bar residual state is "
                      "claimed only while the synchronisation eigenvalue is more than one sd "
                      "above its own trailing normal", diagnostics=diagnostics),
        ]
        if time.monotonic() < deadline:
            tree, notes = self.projection(panel, self.WINDOW,
                                          why=f"the network window is {self.WINDOW} bars over "
                                              f"{len(names)} nodes")
            out.append(self.emit(panel, "mechanism", tree,
                                 "cross-asset synchronisation, traded through bar terminals",
                                 diagnostics=diagnostics, notes=notes))
        _ = rng
        return out

    def _rolling(self, block: np.ndarray, names: list[str], target: str
                 ) -> tuple[np.ndarray, np.ndarray, int]:
        n, k = block.shape
        sync = np.full(n, np.nan, dtype=float)
        centrality = np.full(n, np.nan, dtype=float)
        node = names.index(target) if target in names else 0
        previous: np.ndarray | None = None
        changes = 0
        last_sync, last_central = np.nan, np.nan
        for t in range(self.WINDOW, n):
            if (t - self.WINDOW) % self.STRIDE == 0:
                window = block[t - self.WINDOW:t]
                with _quiet():
                    window = np.nan_to_num(window - np.nanmean(window, axis=0))
                    sd = np.nanstd(window, axis=0)
                    sd[sd < 1e-12] = 1.0
                    corr = np.corrcoef((window / sd).T)
                corr = np.nan_to_num(corr, nan=0.0)
                values, vectors = np.linalg.eigh(corr)
                leading = np.abs(vectors[:, -1])
                last_sync = float(values[-1] / max(1, k))
                last_central = float(leading[node] / max(1e-12, float(leading.sum())))
                partition = np.sign(vectors[:, -2]) if k >= 2 else np.ones(k)
                if previous is not None and not np.array_equal(partition, previous) \
                        and not np.array_equal(partition, -previous):
                    changes += 1
                previous = partition
            sync[t] = last_sync
            centrality[t] = last_central
        return sync, centrality, changes


# ========================================================================== 9. topology
class Topology(Scientist):
    """0-dimensional persistence from single-linkage merge heights, and its stability under noise.

    A structure that survives both noise and a change of parameters is the only kind worth
    trading. The barcode is compared against a jittered rerun, and the maximum bar displacement is
    the stability number the object carries.
    """

    tradition = "topology"
    searches_for = ("representation", "law")

    WINDOW = 240
    STRIDE = 24

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        try:
            from scipy.cluster.hierarchy import linkage
        except Exception as exc:
            self.note("persistence", f"scipy.cluster unavailable ({type(exc).__name__})")
            return []
        series = _finite(panel.epsilon)
        cloud, _ = DynamicalSystems._embed(series, 3, 4)
        if cloud.shape[0] < 120:
            self.note("point_cloud", f"{cloud.shape[0]} embedded points; a longer panel would "
                                     "measure the barcode")
            return []
        step = max(1, cloud.shape[0] // CLOUD_CAP)
        sub = cloud[::step]
        heights = np.sort(linkage(sub, method="single")[:, 2])
        entropy = self._persistence_entropy(heights)
        scale = float(np.std(sub)) or 1.0
        jittered = np.sort(linkage(sub + rng.normal(0.0, 0.05 * scale, sub.shape),
                                   method="single")[:, 2])
        size = min(heights.size, jittered.size)
        stability = float(np.max(np.abs(heights[:size] - jittered[:size])) / scale)

        column = self._rolling_entropy(series, linkage)
        name = panel.mint("persistence_entropy", column,
                          Variable(name="persistence_entropy", dataset="mathlab:topology",
                                   source="derived", units="entropy of 0-dim merge heights"))
        self.minted.append(name)
        diagnostics = {"points": int(sub.shape[0]), "bars": int(heights.size),
                       "persistence_entropy": round(entropy, 6),
                       "longest_bar": round(float(heights[-1] / scale), 6),
                       "noise_displacement": round(stability, 6),
                       "stable": bool(stability < 0.5),
                       "method": "0-dim persistence as single-linkage merge heights; stability "
                                 "as the maximum bar displacement under 5% gaussian noise"}
        out = [
            self.emit(panel, "representation", ["z", name, 240],
                      f"A TOPOLOGICAL STATE VARIABLE: the entropy of the 0-dim barcode over a "
                      f"trailing {self.WINDOW}-bar embedding, {entropy:.4f} on the full cloud",
                      diagnostics=diagnostics),
            self.emit(panel, "law", ["curv", name, 24],
                      f"a structure that SURVIVES noise: the barcode moves {stability:.3f} scale "
                      f"units under 5% jitter, so its acceleration is a claim about persistent "
                      f"structure rather than about the sample", diagnostics=diagnostics),
        ]
        if time.monotonic() < deadline:
            tree, notes = self.projection(panel, self.WINDOW,
                                          why=f"the barcode window is {self.WINDOW} bars")
            out.append(self.emit(panel, "law", tree,
                                 "persistent structure, traded through bar terminals",
                                 diagnostics=diagnostics, notes=notes))
        return out

    @staticmethod
    def _persistence_entropy(heights: np.ndarray) -> float:
        total = float(heights.sum())
        if total <= 0:
            return 0.0
        p = heights / total
        p = p[p > 0]
        return float(-(p * np.log(p)).sum())

    def _rolling_entropy(self, series: np.ndarray, linkage: Any) -> np.ndarray:
        n = series.size
        out = np.full(n, np.nan, dtype=float)
        last = np.nan
        for t in range(self.WINDOW, n):
            if (t - self.WINDOW) % self.STRIDE == 0:
                cloud, _ = DynamicalSystems._embed(series[t - self.WINDOW:t], 3, 4)
                if cloud.shape[0] >= 40:
                    last = self._persistence_entropy(
                        np.sort(linkage(cloud[::2], method="single")[:, 2]))
            out[t] = last
        return out


# ============================================================== 10. causal mathematics
class Causal(Scientist):
    """Conditional independence and INVARIANCE ACROSS ENVIRONMENTS, in the spirit of ICP.

    A coefficient that is the same in every regime is a candidate structural relationship; one
    that changes with the environment is a description of the environment. Partial correlation
    removes the other top drivers before the question is asked, so a variable cannot inherit its
    significance from a confounder already on the panel.
    """

    tradition = "causal"
    searches_for = ("law", "relationship")

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        names = self.top_columns(panel, 8)
        train, _ = panel.split()
        environments = (panel.regime if panel.regime is not None else
                        np.asarray([str(e) for e in panel.eras(4)]))
        labels = [e for e in np.unique(environments) if int((environments == e).sum()) >= 120]
        if len(labels) < 2:
            self.note("invariance", f"{len(labels)} environments carry 120 rows; invariant causal "
                                    "prediction needs at least two")
        out: list[MathObject | None] = []
        rows: list[dict[str, Any]] = []
        for name in names:
            if time.monotonic() >= deadline:
                self.note("causal_scan", f"budget reached after {len(rows)} columns")
                break
            others = [c for c in names if c != name][:4]
            partial = self._partial_correlation(panel, name, others, train)
            spread, per_env = self._invariance(panel, name, environments, labels)
            self.charge(["z", name, 240])
            rows.append({"column": name, "partial_correlation": round(partial, 6),
                         "invariance_spread": None if spread is None else round(spread, 6),
                         "per_environment_beta": per_env})
        if not rows:
            return out
        rows.sort(key=lambda r: (r["invariance_spread"] if r["invariance_spread"] is not None
                                 else 9e9, -abs(r["partial_correlation"])))
        for row in rows[:2]:
            invariant = (row["invariance_spread"] is not None and row["invariance_spread"] < 1.0)
            out.append(self.emit(
                panel, "law" if invariant else "relationship", ["z", row["column"], 240],
                f"{'INVARIANT' if invariant else 'ENVIRONMENT-DEPENDENT'}: the coefficient of "
                f"{row['column']} on the residual varies by "
                f"{row['invariance_spread']} standard errors across {len(labels)} environments, "
                f"and its partial correlation given the other top drivers is "
                f"{row['partial_correlation']:+.5f}",
                side_mode="follow" if row["partial_correlation"] >= 0 else "fade",
                diagnostics={"rows": rows, "environments": [str(x) for x in labels],
                             "method": "partial correlation by linear residualisation; "
                                       "invariance as the max |beta_e - beta| / se across "
                                       "environments (invariant causal prediction)"}))
        tree, notes = self.projection(panel, 240, why=f"the most invariant column was "
                                                      f"{rows[0]['column']}")
        out.append(self.emit(panel, "law", tree,
                             "the invariant relationship, traded through bar terminals",
                             diagnostics={"top": rows[0]}, notes=notes))
        _ = rng
        return out

    @staticmethod
    def _residualise(y: np.ndarray, controls: np.ndarray) -> np.ndarray:
        if controls.size == 0:
            return y
        design = np.column_stack([np.ones(y.size), np.nan_to_num(controls)])
        beta, *_ = np.linalg.lstsq(design, np.nan_to_num(y), rcond=None)
        return y - design @ beta

    def _partial_correlation(self, panel: Panel, name: str, others: list[str],
                             index: np.ndarray) -> float:
        if index.size < 64:
            return 0.0
        controls = np.column_stack([panel.columns[c][index] for c in others]) if others \
            else np.empty((index.size, 0))
        x = self._residualise(_finite(panel.columns[name][index]), controls)
        y = self._residualise(_finite(panel.epsilon[index]), controls)
        return _corr(x, y)

    def _invariance(self, panel: Panel, name: str, environments: np.ndarray,
                    labels: list[Any]) -> tuple[float | None, dict[str, float]]:
        betas: dict[str, float] = {}
        errors: list[float] = []
        for label in labels:
            mask = environments == label
            x = _finite(panel.columns[name][mask])
            y = _finite(panel.epsilon[mask])
            if x.size < 60 or float(np.std(x)) < 1e-12:
                continue
            design = np.column_stack([np.ones(x.size), x])
            beta, *_ = np.linalg.lstsq(design, y, rcond=None)
            residual = y - design @ beta
            se = math.sqrt(max(1e-18, float(residual @ residual) / max(1, x.size - 2)
                               / max(1e-18, float(((x - x.mean()) ** 2).sum()))))
            betas[str(label)] = round(float(beta[1]), 8)
            errors.append(se)
        if len(betas) < 2:
            return None, betas
        values = np.asarray(list(betas.values()), dtype=float)
        se = float(np.mean(errors)) if errors else 0.0
        return float(np.max(np.abs(values - values.mean())) / max(1e-12, se)), betas


# ================================================================== 11. combinatorics
class Combinatorics(Scientist):
    """Bounded enumeration of event-interaction configurations, under Benjamini-Hochberg FDR.

    Humans do not enumerate "London AND high-vol AND the 48-bar dispersion in its top tercile".
    A machine can, and the reason it usually should not is that enumeration without FDR control
    produces a winner from noise every time. The enumeration is bounded, the p-values are
    circular-block, and the discovery threshold is BH at q = 0.10 across the WHOLE enumeration.
    """

    tradition = "combinatorics"
    searches_for = ("relationship", "mechanism")

    MAX_CONFIGURATIONS = 400
    Q = 0.10

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        atoms = self._atoms(panel)
        if len(atoms) < 2:
            self.note("atoms", f"{len(atoms)} usable indicator atoms; sessions, regimes and the "
                               "top columns are all that the panel offers")
            return []
        train, _ = panel.split()
        target = panel.epsilon
        tested: list[dict[str, Any]] = []
        keys = list(atoms)
        for i, a in enumerate(keys):
            for j in range(i + 1, len(keys)):
                for k in range(j + 1, len(keys) + 1):
                    combo = [a, keys[j]] + ([keys[k]] if k < len(keys) else [])
                    if len(tested) >= self.MAX_CONFIGURATIONS or time.monotonic() >= deadline:
                        break
                    mask = np.ones(panel.n, dtype=bool)
                    for atom in combo:
                        mask &= atoms[atom]
                    rows = mask[train]
                    self.evaluated += 1
                    if int(rows.sum()) < 60:
                        continue
                    inside = target[train][rows]
                    inside = inside[np.isfinite(inside)]
                    if inside.size < 60:
                        continue
                    sd = float(np.std(inside)) or 1e-12
                    t = float(inside.mean() / (sd / math.sqrt(inside.size)))
                    p = math.erfc(abs(t) / math.sqrt(2.0))
                    tested.append({"configuration": combo, "n": int(inside.size),
                                   "mean_epsilon": round(float(inside.mean()), 8),
                                   "t": round(t, 4), "p": round(p, 8)})
                if len(tested) >= self.MAX_CONFIGURATIONS:
                    break
            if len(tested) >= self.MAX_CONFIGURATIONS:
                break
        if not tested:
            self.note("enumeration", "no configuration reached 60 training rows")
            return []
        survivors = self._bh(tested)
        self.distinct |= {"&".join(sorted(r["configuration"])) for r in tested}
        diagnostics = {"enumerated": len(tested), "survivors_after_fdr": len(survivors),
                       "q": self.Q, "top": tested[:5],
                       "method": "bounded enumeration with Benjamini-Hochberg FDR across the "
                                 "whole enumeration, not per configuration"}
        if not survivors:
            self.note("fdr", f"{len(tested)} configurations enumerated and none survived "
                             f"Benjamini-Hochberg at q={self.Q} -- the enumeration's own "
                             f"multiplicity is what refused them")
        out: list[MathObject | None] = []
        for row in survivors[:2]:
            window = _nearest_window(48)
            out.append(self.emit(
                panel, "relationship", ["mul", ["z", "ret", window],
                                        ["sign", ["diff", "close", window]]],
                f"CONFIGURATION {' AND '.join(row['configuration'])}: mean residual "
                f"{row['mean_epsilon']:+.6f} on n={row['n']} (t={row['t']:+.2f}, p={row['p']:.5f}) "
                f"survives BH at q={self.Q} across {len(tested)} enumerated configurations",
                side_mode="follow" if row["mean_epsilon"] >= 0 else "fade",
                diagnostics={**diagnostics, "configuration": row},
                notes=["the configuration's session/regime coordinates ride in the payload; the "
                       "formula family takes no session parameter, so the donated recipe is the "
                       "price-only projection and the cell coordinates are the discovery"]))
        _ = rng
        return out

    def _atoms(self, panel: Panel) -> dict[str, np.ndarray]:
        out: dict[str, np.ndarray] = {}
        if panel.session is not None:
            for label in np.unique(panel.session)[:4]:
                mask = panel.session == label
                if int(mask.sum()) >= 120:
                    out[f"session={label}"] = mask
        else:
            self.note("session_atoms", "the panel carries no session labels")
        if panel.regime is not None:
            for label in np.unique(panel.regime)[:4]:
                mask = panel.regime == label
                if int(mask.sum()) >= 120:
                    out[f"regime={label}"] = mask
        else:
            self.note("regime_atoms", "the panel carries no regime labels")
        for name in self.top_columns(panel, 4):
            values = G.evaluate(["z", name, 240], panel.columns, panel.n)
            mask = np.isfinite(values) & (values > 0.5)
            if int(mask.sum()) >= 120:
                out[f"{name}>0.5sd"] = mask
        return out

    def _bh(self, tested: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ordered = sorted(tested, key=lambda r: r["p"])
        m = len(ordered)
        cut = 0
        for rank, row in enumerate(ordered, start=1):
            if row["p"] <= self.Q * rank / m:
                cut = rank
        return ordered[:cut]


# ================================================================== 12. control theory
class ControlTheory(Scientist):
    """ARX system identification and impulse responses: how the residual RESPONDS to a shock.

    y_t = sum a_i y_{t-i} + sum b_j u_{t-j} + e_t, fitted by least squares on the training slice.
    The impulse response says how long a shock takes to decay and whether it overshoots; the
    largest root of the AR polynomial says whether the loop is stable at all.
    """

    tradition = "control_theory"
    searches_for = ("mechanism", "law")

    AR_ORDER = 4
    EX_ORDER = 4

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        shock_name = next((c for c in ("ret", "range", "activity") if c in panel.columns), None)
        if shock_name is None:
            self.note("arx", "the panel carries none of ret / range / activity as a shock input")
            return []
        train, _ = panel.split()
        y = _finite(panel.epsilon)
        u = _z(_finite(panel.columns[shock_name]))
        lags = max(self.AR_ORDER, self.EX_ORDER)
        rows = train[train >= lags]
        if rows.size < 200:
            self.note("arx", f"{rows.size} usable training rows after {lags} lags")
            return []
        design = np.column_stack(
            [np.ones(rows.size)]
            + [y[rows - i] for i in range(1, self.AR_ORDER + 1)]
            + [u[rows - j] for j in range(1, self.EX_ORDER + 1)])
        beta, *_ = np.linalg.lstsq(design, y[rows], rcond=None)
        a = beta[1:1 + self.AR_ORDER]
        b = beta[1 + self.AR_ORDER:]
        self.evaluated += self.AR_ORDER + self.EX_ORDER
        response = self._impulse(a, b, steps=48)
        roots = np.roots(np.concatenate([[1.0], -a]))
        spectral_radius = float(np.max(np.abs(roots))) if roots.size else float("nan")
        peak = int(np.argmax(np.abs(response))) + 1
        settle = next((i + 1 for i in range(len(response) - 1, -1, -1)
                       if abs(response[i]) > 0.1 * abs(response[peak - 1])), len(response))
        diagnostics = {"input": shock_name, "ar_order": self.AR_ORDER, "ex_order": self.EX_ORDER,
                       "ar_coefficients": [round(float(v), 6) for v in a],
                       "exogenous_coefficients": [round(float(v), 6) for v in b],
                       "spectral_radius": round(spectral_radius, 6),
                       "stable": bool(spectral_radius < 1.0),
                       "impulse_peak_bar": peak, "settling_bars": int(settle),
                       "impulse_response": [round(float(v), 8) for v in response[:12]],
                       "method": "least-squares ARX identification; impulse response by recursion"}
        if spectral_radius >= 1.0:
            self.note("arx_stability", f"spectral radius {spectral_radius:.3f} >= 1; the "
                                       "identified loop is not stable and the settling time is "
                                       "not defined")

        dominant = int(np.argmax(np.abs(b))) + 1 if b.size else 1
        window = _nearest_window(max(2, settle))
        out = [
            self.emit(panel, "mechanism",
                      ["mul", ["sign", ["lag", shock_name, _nearest_window(dominant)]],
                       ["z", shock_name, window]],
                      f"A DYNAMIC RESPONSE: a shock in {shock_name} peaks in the residual at bar "
                      f"{peak} and settles by bar {settle}; the dominant exogenous lag is "
                      f"{dominant} and the loop's spectral radius is {spectral_radius:.3f}",
                      side_mode="follow" if (b.size and b[dominant - 1] >= 0) else "fade",
                      diagnostics=diagnostics),
            self.emit(panel, "law", ["curv", shock_name, window],
                      f"the second difference of the input over the {window}-bar settling time: "
                      f"the loop responds to the shock's ACCELERATION, not its level",
                      diagnostics=diagnostics),
        ]
        if time.monotonic() < deadline:
            tree, notes = self.projection(panel, window, fast=dominant,
                                          why=f"the settling time is {settle} bars and the "
                                              f"dominant exogenous lag is {dominant}")
            out.append(self.emit(panel, "mechanism", tree,
                                 "the identified response, traded through bar terminals",
                                 diagnostics=diagnostics, notes=notes))
        _ = rng
        return out

    @staticmethod
    def _impulse(a: np.ndarray, b: np.ndarray, steps: int = 48) -> np.ndarray:
        out = np.zeros(steps)
        for t in range(steps):
            value = float(b[t]) if t < b.size else 0.0
            for i, coefficient in enumerate(a, start=1):
                if t - i >= 0:
                    value += float(coefficient) * out[t - i]
            out[t] = value
        return out


# ============================================================ 13. game theory / ecology
class GameTheoryEcology(Scientist):
    """The footprints other systematic participants leave: crowding, response, herd / anti-herd.

    The positioning axis is used when the panel has one (COT, positioning surveys). When it does
    not, the substitution is NAMED -- activity and range are a crowding PROXY, not positioning,
    and an object that rests on the proxy says so in its own statement rather than in a footnote.
    """

    tradition = "game_theory_ecology"
    searches_for = ("mechanism", "relationship")

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        axis = next((c for c in panel.names
                     if any(tag in f"{c} {panel.meta.get(c, Variable(c, c)).dataset}".lower()
                            for tag in ("cot", "position", "crowd", "net_long", "sentiment"))),
                    None)
        proxy = False
        if axis is None:
            axis = next((c for c in ("activity", "range", "flow") if c in panel.columns), None)
            proxy = True
            self.note("positioning_axis", "no COT / positioning column on the panel; activity is "
                                          "used as a CROWDING PROXY and every object here says so. "
                                          "Ingesting the CFTC axis for this instrument would "
                                          "measure it properly")
        if axis is None:
            self.note("crowding", "the panel carries neither a positioning axis nor a proxy")
            return []
        train, _ = panel.split()
        delta = G.evaluate(["diff", axis, 24], panel.columns, panel.n)
        crowding = G.evaluate(["z", axis, 240], panel.columns, panel.n)
        response = _corr(delta[train], panel.epsilon[train])
        herd = _corr(delta[24:], delta[:-24])
        extreme = np.isfinite(crowding) & (np.abs(crowding) > 1.5)
        unwind = (_corr(crowding[train][extreme[train]], panel.epsilon[train][extreme[train]])
                  if int(extreme[train].sum()) >= 60 else None)
        if unwind is None:
            self.note("crowded_unwind", f"{int(extreme[train].sum())} training rows beyond 1.5 sd "
                                        "of the positioning state; fewer than the 60 needed")
        self.evaluated += 3
        diagnostics = {"axis": axis, "is_proxy": proxy,
                       "positioning_response": round(response, 6),
                       "herding_autocorrelation": round(herd, 6),
                       "behaviour": "herding" if herd > 0 else "anti-herding",
                       "crowded_unwind_ic": None if unwind is None else round(unwind, 6),
                       "method": "participant-class footprint: response of the residual to the "
                                 "24-bar change in the positioning axis, the axis's own "
                                 "autocorrelation as herd/anti-herd, and the conditional relation "
                                 "beyond 1.5 sd of crowding"}
        label = "a CROWDING PROXY (activity), not positioning" if proxy else "the positioning axis"
        out = [
            self.emit(panel, "mechanism", ["neg", ["z", axis, 240]],
                      f"A CROWDED INVENTORY UNWINDS: {label} {axis} is faded at extremes; the "
                      f"residual's response to a 24-bar change is {response:+.5f} and the axis "
                      f"is {'herding' if herd > 0 else 'anti-herding'} "
                      f"(autocorrelation {herd:+.4f})", diagnostics=diagnostics),
            self.emit(panel, "relationship",
                      ["mul", ["sign", ["diff", axis, 24]], ["z", "ret", 48]],
                      f"THE OTHER PARTICIPANTS' FOOTPRINT: the direction of the {label}'s 24-bar "
                      f"change times the 48-bar residual state", diagnostics=diagnostics),
        ]
        if time.monotonic() < deadline:
            tree, notes = self.projection(panel, 240, fast=24,
                                          why=f"the positioning axis is {axis}"
                                              f"{' (a proxy)' if proxy else ''}")
            out.append(self.emit(panel, "mechanism", tree,
                                 "participant crowding, traded through bar terminals",
                                 diagnostics=diagnostics, notes=notes))
        _ = rng
        return out


# ============================================================== 14. meta-mathematics
class MetaMathematics(Scientist):
    """Invent new TRANSFORMS, OBJECTIVES and SEARCH OPERATORS from the measured ROI table.

    This is the tradition that changes the other thirteen. It reads what actually earned -- the
    per-tradition ROI the lab wrote last pass -- and emits `search_method` objects: a new composed
    transform built from the operators the earning traditions used, a new objective function
    stated as a formula, and a new search operator with the windows that survived. Each is
    REGISTERED, so the next pass can pick it up, and each carries a falsifiable expression so that
    a search method is held to the same evidence bar as a signal.
    """

    tradition = "meta_mathematics"
    searches_for = ("search_method", "representation")

    def __init__(self, roi: dict[str, float] | None = None,
                 operators_used: dict[str, int] | None = None) -> None:
        super().__init__()
        self.roi = dict(roi or {})
        self.operators_used = dict(operators_used or {})

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        if not self.roi:
            self.note("roi_table", "no per-tradition ROI has been published yet; the first pass "
                                   "invents from the grammar's own operator census instead, and "
                                   "data/math_allocation.json will carry ROI from the next pass on")
        # UNMEASURED IS None, NOT ZERO, and None does not sort: the earners are the traditions
        # with a MEASURED ROI, ranked; an unpriced tradition is neither an earner nor a loser.
        priced = {k: float(v) for k, v in self.roi.items() if isinstance(v, (int, float))}
        earners = sorted(priced, key=lambda k: -priced[k])[:3]
        census = self.operators_used or {"z": 3, "curv": 2, "diff": 2}
        top_ops = sorted(census, key=lambda k: -census[k])[:2]
        base = next((c for c in ("close", "ret") if c in panel.columns), panel.names[0])
        window = _nearest_window(240)

        composed = ["z", ["curv", base, 24], window]
        if len(top_ops) >= 2 and top_ops[0] in G.WINDOWED and top_ops[1] in G.WINDOWED:
            composed = [top_ops[0], [top_ops[1], base, 24], window]
        objective_tree = ["div", ["abs", ["z", base, window]], ["rstd", base, window]]
        operator_tree = ["sub", ["z", base, window], ["z", base, _nearest_window(window / 2)]]

        diagnostics = {"roi_read": self.roi, "top_traditions": earners,
                       "operator_census": census,
                       "objective": "held-out t per MDL bit per sqrt(2 ln effective trials) -- "
                                    "the same three terms burden.py scores, expressed as a rate "
                                    "so a tradition can be compared at different search sizes",
                       "search_operator": "window-ladder mutation: a window argument moves to its "
                                          "NEIGHBOUR in grammar.WINDOWS rather than being "
                                          "resampled, so the perturbation test and the search "
                                          "move in the same space"}
        out = [
            self.emit(panel, "search_method", composed,
                      f"A NEW TRANSFORM: compose {top_ops[0] if top_ops else 'z'} over "
                      f"{top_ops[1] if len(top_ops) > 1 else 'curv'} -- the two operators the "
                      f"earning traditions {earners or ['(none priced yet)']} actually used -- "
                      f"and register it so the next pass can draw it as one move",
                      diagnostics=diagnostics),
            self.emit(panel, "search_method", objective_tree,
                      "A NEW OBJECTIVE: value per unit of description length per unit of search, "
                      "so a tradition that finds a simple law from a small search outranks one "
                      "that finds a complicated law from a large one at equal t",
                      diagnostics=diagnostics),
        ]
        if time.monotonic() < deadline:
            out.append(self.emit(
                panel, "search_method", operator_tree,
                "A NEW SEARCH OPERATOR: the window-ladder move, whose own expression is the "
                "difference between a window and its neighbour -- if the ladder is a real "
                "structure this expression carries evidence, and if it is not, it does not",
                diagnostics=diagnostics))
        _ = rng
        return out


#: tradition -> class. `math_lab` builds one instance per tradition per pass.
REGISTRY: dict[str, type[Scientist]] = {
    "symbolic_regression": SymbolicRegression,
    "dynamical_systems": DynamicalSystems,
    "stochastic_processes": StochasticProcesses,
    "spectral": Spectral,
    "information_theory": InformationTheory,
    "geometry": Geometry,
    "optimal_transport": OptimalTransport,
    "graph_theory": GraphTheory,
    "topology": Topology,
    "causal": Causal,
    "combinatorics": Combinatorics,
    "control_theory": ControlTheory,
    "game_theory_ecology": GameTheoryEcology,
    "meta_mathematics": MetaMathematics,
}


REGISTRY.update(EXTRA_REGISTRY)
# THE PHYSICS WING (2026-09-22) is registered here so `build` is the one door every leg uses;
# it is NOT appended to TRADITIONS, which stays the twenty-eight mathematical traditions --
# `math_lab.all_traditions()` and `physics_lab` read `PHYSICS_TRADITIONS` as their own
# department, allocated and budgeted beside the mathematics, never diluted into it.
REGISTRY.update(PHYSICS_CORE_REGISTRY)
REGISTRY.update(PHYSICS_EXT_REGISTRY)
PHYSICS_TRADITIONS: tuple[str, ...] = (*PHYSICS_CORE_REGISTRY, *PHYSICS_EXT_REGISTRY)


def build(tradition: str, **kwargs: Any) -> Scientist:
    """One scientist, by name. Unknown names raise: a silent no-op tradition is a dark organ."""
    cls = REGISTRY.get(tradition)
    if cls is None:
        raise KeyError(f"unknown tradition {tradition!r}; known: {sorted(REGISTRY)}")
    return cls(**kwargs) if tradition == "meta_mathematics" else cls()
