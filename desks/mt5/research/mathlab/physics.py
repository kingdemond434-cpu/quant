"""THE PHYSICS WING OF THE CIVILIZATION, first cohort: ten traditions of physical reasoning over
the same residual the mathematicians read.

A PHYSICIST ASKS A DIFFERENT QUESTION OF THE SAME PANEL. The mathematician asks what function
explains the residual; the physicist asks what ENSEMBLE it is drawn from, whether its path is
REVERSIBLE, how it DIFFUSES, what it looks like after COARSE-GRAINING, whether its bursts are
CRITICAL, what ATTRACTOR it lives on, whether it is CHAOTIC or merely noisy, how it RESPONDS to
an impulse, what CONTINUUM field the order flow is, and whether its increments are INTERMITTENT
the way a turbulent cascade is. Each answer is a number with an error bar, and each tradition
turns its number into the five things the civilization searches for -- a relationship, a
representation, a mechanism, a law, a search method -- through the same `Scientist` contract
and the same search-burden judge as the mathematicians. Nothing here is a fitted model to be
trusted; every object goes to the desk's own gauntlet.

Every tradition is numpy only, bounded by a deadline and a subsample cap, names what it could
not measure, and offers an executable projection over bar terminals so an invention over a
minted state variable can still reach the compiler.
"""
from __future__ import annotations

import math
import time
from typing import Any

import numpy as np

from . import grammar as G
from .base import CLOUD_CAP, UNMEASURED, Scientist, _corr, _finite, _nearest_window, _quiet, _z
from .objects import MathObject, Panel
from .scientists_ext import _mint, _quantile_bins


# ------------------------------------------------------------------------------- helpers
def _horizon_bars(panel: Panel) -> int:
    return max(1, int("".join(ch for ch in str(panel.horizon) if ch.isdigit()) or 1))


def _realised(scientist: Scientist, panel: Panel, name: str = "eps_realised"
              ) -> tuple[str, np.ndarray]:
    """The residual lagged by the horizon: the last value that was KNOWABLE at the bar."""
    if name in panel.columns:
        return name, _finite(panel.columns[name])
    lag = _nearest_window(_horizon_bars(panel))
    lagged = G.evaluate(["lag", "__e__", lag], {"__e__": _finite(panel.epsilon)}, panel.n)
    _mint(scientist, panel, name, lagged, f"mathlab:{scientist.tradition}",
          f"the residual lagged by the {lag}-bar horizon: the last realised value")
    return name, _finite(lagged)


def _loglog_fit(xs: Any, ys: Any) -> tuple[float, float, float] | None:
    """(slope, intercept, r2) of log y on log x over the points where both are positive."""
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y) & (x > 0) & (y > 0)
    if int(mask.sum()) < 3:
        return None
    lx, ly = np.log(x[mask]), np.log(y[mask])
    slope, intercept = np.polyfit(lx, ly, 1)
    fitted = slope * lx + intercept
    ss = float(((ly - ly.mean()) ** 2).sum())
    r2 = 1.0 - float(((ly - fitted) ** 2).sum()) / ss if ss > 1e-15 else 0.0
    return float(slope), float(intercept), float(r2)


def _train_corr(panel: Panel, values: np.ndarray) -> float:
    train, _ = panel.split()
    return _corr(values[train], panel.epsilon[train])


def _side(corr: float) -> str:
    return "follow" if corr >= 0 else "fade"


def _acf(x: np.ndarray, k: int) -> float:
    if k <= 0 or x.size <= k + 8:
        return 0.0
    return _corr(x[k:], x[:-k])


def _fluct(series: np.ndarray) -> np.ndarray:
    """The STATIONARY fluctuation of a column, standardised, for use as a DRIVER.

    Linear response and deconvolution are theories of fluctuations about a stationary state.
    A price LEVEL is a near unit root, and the correlation between two near unit roots is the
    classic spurious regression -- it is large, it is meaningless, and on this desk's panels it
    is what lets `high` beat the column that actually carries the impulse. So a column whose
    one-lag autocorrelation exceeds 0.98 is DIFFERENCED before it may act as a driver, and every
    driver is then divided by its own standard deviation so that drivers compete on shape and
    never on scale. The transform is recorded in the diagnostics that use it, never silent.
    """
    v = np.nan_to_num(_finite(series)).astype(float)
    if v.size > 16 and abs(_acf(v, 1)) > 0.98:
        v = np.concatenate([[0.0], np.diff(v)])
    v = np.asarray(v - float(np.mean(v)), dtype=float)
    sd = float(np.std(v))
    return np.asarray(v / sd, dtype=float) if sd > 1e-15 else v


def _fluct_kind(series: np.ndarray) -> str:
    v = np.nan_to_num(_finite(series)).astype(float)
    return "differenced" if v.size > 16 and abs(_acf(v, 1)) > 0.98 else "level"


def _kurtosis(x: np.ndarray) -> float:
    v = x[np.isfinite(x)]
    if v.size < 8:
        return 0.0
    sd = float(np.std(v))
    return float(np.mean(((v - v.mean()) / sd) ** 4) - 3.0) if sd > 1e-15 else 0.0


def _era_values(panel: Panel, fn: Any, k: int = 4) -> list[float | None]:
    eras = panel.eras(k)
    out: list[float | None] = []
    for e in range(k):
        rows = np.flatnonzero(eras == e)
        try:
            value = fn(rows) if rows.size >= 60 else None
        except Exception:
            value = None
        out.append(float(value) if value is not None and math.isfinite(float(value)) else None)
    return out


def _spread(values: list[float | None]) -> float | None:
    finite = [v for v in values if v is not None and math.isfinite(v)]
    return float(max(finite) - min(finite)) if len(finite) >= 2 else None


# ==================================================================== 1. statistical mechanics
class StatisticalMechanics(Scientist):
    """The residual as an ensemble: a temperature, an energy, and whether they are related the
    way a canonical ensemble says they must be.

    Temperature is the rolling variance of the realised residual; energy is its square. In a
    canonical ensemble <E>/T is one in every subsystem (equipartition), the distribution of the
    scaled energy is Gaussian, and a specific heat d<E>/dT of one is what "temperature explains
    the energy" means. A session whose ratio is off, a Laplace ensemble that fits better than
    the Gaussian, or a specific heat far from one is a measurement, and each becomes an object.
    """

    tradition = "statistical_mechanics"
    searches_for = ("representation", "law", "mechanism")

    WINDOW = 48

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        state, x = _realised(self, panel)
        with _quiet():
            temperature = G.evaluate(["rstd", state, self.WINDOW], panel.columns, panel.n) ** 2
        temp = _mint(self, panel, "temperature", temperature, "mathlab:statistical_mechanics",
                     "residual^2")
        train, _ = panel.split()
        ok = train[np.isfinite(temperature[train]) & (temperature[train] > 1e-15)]
        if ok.size < 200:
            self.note("temperature", f"{ok.size} training rows carry a finite temperature")
            return []
        with _quiet():
            z = x[ok] / np.sqrt(temperature[ok])
        ll_gauss = float(-0.5 * np.mean(z ** 2) - 0.5 * math.log(2 * math.pi))
        b = max(1e-9, float(np.mean(np.abs(z))))
        ll_laplace = float(-np.mean(np.abs(z)) / b - math.log(2 * b))
        ratios: dict[str, float] = {}
        if panel.session is not None:
            for s in sorted(set(panel.session[ok].tolist())):
                rows = ok[panel.session[ok] == s]
                if rows.size >= 40:
                    ratios[str(s)] = round(float(np.mean(x[rows] ** 2)
                                                 / np.mean(temperature[rows])), 4)
        energy24 = G.evaluate(["rmean", ["mul", state, state], 24], panel.columns, panel.n)
        heat = _corr(energy24[ok], temperature[ok])
        equipartition = _spread(list(ratios.values())) if ratios else None
        diagnostics = {"log_likelihood_per_row": {"gaussian": round(ll_gauss, 5),
                                                  "laplace": round(ll_laplace, 5)},
                       "equipartition_ratio_by_session": ratios,
                       "equipartition_spread": equipartition, "specific_heat_corr": round(heat, 4),
                       "temperature_window": self.WINDOW,
                       "method": "canonical-ensemble fit: T = rolling variance of the realised "
                                 "residual, E = its square; Gaussian vs Laplace energy"}
        out = [self.emit(panel, "representation", ["z", temp, 240],
                         f"TEMPERATURE: the {self.WINDOW}-bar variance of the realised residual "
                         f"as an ensemble state; specific-heat correlation {heat:+.3f}",
                         diagnostics=diagnostics)]
        law_tree = ["div", ["rmean", ["mul", state, state], 24], temp]
        out.append(self.emit(panel, "law", law_tree,
                             "EQUIPARTITION: <E>/T per session " + (
                                 ", ".join(f"{k}={v}" for k, v in ratios.items()) or UNMEASURED)
                             + (f"; spread {equipartition:.3f}" if equipartition is not None
                                else ""),
                             diagnostics=diagnostics))
        heating = G.evaluate(["diff", temp, 24], panel.columns, panel.n)
        corr = _train_corr(panel, np.nan_to_num(heating))
        out.append(self.emit(panel, "relationship", ["diff", temp, 24],
                             f"HEATING: the 24-bar change of temperature reads the residual "
                             f"with training IC {corr:+.4f}", side_mode=_side(corr),
                             diagnostics=diagnostics))
        if ll_laplace > ll_gauss + 0.02:
            out.append(self.emit(panel, "mechanism", ["abs", ["z", state, self.WINDOW]],
                                 f"NOT A CANONICAL-GAUSSIAN ENSEMBLE: the Laplace energy fits "
                                 f"{ll_laplace - ll_gauss:.3f} nats/row better -- a "
                                 f"superstatistical mixture of temperatures, i.e. the variance "
                                 f"itself is a process", diagnostics=diagnostics))
        if time.monotonic() < deadline:
            tree, notes = self.projection(panel, self.WINDOW,
                                          why=f"temperature is measured over {self.WINDOW} bars")
            out.append(self.emit(panel, "relationship", tree, "temperature state, traded through "
                                                               "bar terminals",
                                 diagnostics=diagnostics, notes=notes))
        _ = rng
        return out


# ==================================================================== 2. nonequilibrium
class Nonequilibrium(Scientist):
    """Entropy production and time-asymmetry: is the path reversible?

    A stationary Markov chain's entropy production rate is the relative entropy between the
    forward and the time-reversed path measures, sum_ij pi_i P_ij ln(P_ij / P_ji); it is zero
    for any process in detailed balance and positive for one that is driven. The Ramsey-Rothman
    asymmetry E[x_t^2 x_{t-k}] - E[x_t x_{t-k}^2] is the third-moment version of the same
    question, and it is expressible in the trade grammar, so the invention can be traded.
    """

    tradition = "nonequilibrium"
    searches_for = ("law", "representation", "mechanism")

    BINS = 4

    @classmethod
    def entropy_production(cls, series: np.ndarray) -> float | None:
        v = series[np.isfinite(series)]
        if v.size < 120:
            return None
        bins = _quantile_bins(v, cls.BINS)
        counts = np.zeros((cls.BINS, cls.BINS))
        np.add.at(counts, (bins[:-1], bins[1:]), 1.0)
        rows = counts.sum(1, keepdims=True)
        with _quiet():
            p = np.where(rows > 0, counts / np.maximum(rows, 1e-12), 0.0)
        pi = rows[:, 0] / max(1.0, rows.sum())
        both = (p > 0) & (p.T > 0)
        with _quiet():
            ratio = np.where(both, p / np.maximum(p.T, 1e-15), 1.0)
            term = np.where(both, pi[:, None] * p * np.log(ratio), 0.0)
        return float(max(0.0, term.sum()))

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        if "ret" not in panel.columns:
            self.note("ret", "the panel carries no return column")
            return []
        r = _finite(panel.columns["ret"])
        _state, x = _realised(self, panel)
        train, _ = panel.split()
        sigma = self.entropy_production(r[train])
        sigma_shuffled = self.entropy_production(rng.permutation(r[train]))
        sigma_eps = self.entropy_production(x[train])
        if sigma is None:
            self.note("entropy_production", "fewer than 120 usable training returns")
            return []
        per_era = _era_values(panel, lambda rows: self.entropy_production(r[rows]))
        asym: dict[int, float] = {}
        sd = max(1e-12, float(np.std(x[train])))
        for k in (2, 3, 5):
            a, b = x[train][k:], x[train][:-k]
            asym[k] = float((np.mean(a * a * b) - np.mean(a * b * b)) / sd ** 3)
        by_session: dict[str, float | None] = {}
        if panel.session is not None:
            for s in sorted(set(panel.session[train].tolist())):
                rows = train[panel.session[train] == s]
                by_session[str(s)] = self.entropy_production(r[rows])
        diagnostics = {"entropy_production_nats": round(sigma, 6),
                       "entropy_production_shuffled": (round(sigma_shuffled, 6)
                                                       if sigma_shuffled is not None else None),
                       "entropy_production_residual": (round(sigma_eps, 6)
                                                       if sigma_eps is not None else None),
                       "per_era": per_era,
                       "by_session": {k: (round(v, 6) if v is not None else None)
                                      for k, v in by_session.items()},
                       "ramsey_rothman_asymmetry": {str(k): round(v, 5) for k, v in asym.items()},
                       "bins": self.BINS,
                       "method": "KL(forward || reversed) of a quantile-binned Markov chain; "
                                 "third-moment time-reversal asymmetry"}
        irreversible = sigma_shuffled is not None and sigma > 2.0 * sigma_shuffled
        asym_tree = ["rmean", ["sub", ["mul", ["mul", "ret", "ret"], ["lag", "ret", 2]],
                               ["mul", "ret", ["mul", ["lag", "ret", 2], ["lag", "ret", 2]]]], 48]
        out = [self.emit(panel, "law", asym_tree,
                         f"{'IRREVERSIBLE' if irreversible else 'REVERSIBLE WITHIN NOISE'}: "
                         f"entropy production {sigma:.5f} nats/step against {sigma_shuffled} for "
                         f"the shuffled path; per era {per_era}",
                         diagnostics=diagnostics),
               self.emit(panel, "representation", ["z", asym_tree, 240],
                         "the 48-bar time-reversal asymmetry of returns as a state variable",
                         diagnostics=diagnostics)]
        values = np.nan_to_num(G.evaluate(asym_tree, panel.columns, panel.n))
        corr = _train_corr(panel, values)
        out.append(self.emit(panel, "relationship", asym_tree,
                             f"the arrow of time reads the residual with training IC {corr:+.4f}",
                             side_mode=_side(corr), diagnostics=diagnostics))
        finite_sessions = {k: v for k, v in by_session.items() if v is not None}
        if len(finite_sessions) >= 2:
            hot = max(finite_sessions, key=lambda k: finite_sessions[k])
            cold = min(finite_sessions, key=lambda k: finite_sessions[k])
            if finite_sessions[hot] > 2.0 * max(1e-9, finite_sessions[cold]):
                out.append(self.emit(panel, "mechanism", ["abs", asym_tree],
                                     f"DISSIPATION HAS A CLOCK: the {hot} session produces "
                                     f"{finite_sessions[hot]:.5f} nats/step against "
                                     f"{finite_sessions[cold]:.5f} in {cold}; the driven hours are "
                                     f"where the residual is manufactured",
                                     diagnostics=diagnostics))
        _ = deadline
        return out


# ==================================================================== 3. anomalous diffusion
class AnomalousDiffusion(Scientist):
    """The mean squared displacement law <|X(t+tau) - X(t)|^2> ~ tau^alpha, fitted in logs.

    alpha = 1 is Brownian; below it the path is sub-diffusive (mean-reverting, trapped), above
    it super-diffusive (persistent, Levy-flight-like). The exponent is measured on the price path
    and on the cumulative residual, per era, and a rolling estimate from the ratio of two
    dispersion windows is minted as a state variable the trade grammar can read.
    """

    tradition = "anomalous_diffusion"
    searches_for = ("law", "representation", "relationship")

    LAGS = (1, 2, 3, 5, 8, 12, 24, 48)

    @classmethod
    def exponent(cls, path: np.ndarray) -> tuple[float, float, list[float]] | None:
        msd = [float(np.mean((path[tau:] - path[:-tau]) ** 2)) for tau in cls.LAGS
               if path.size > tau + 60]
        fit = _loglog_fit(cls.LAGS[:len(msd)], msd)
        return (fit[0], fit[2], msd) if fit is not None else None

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        if "ret" not in panel.columns or "close" not in panel.columns:
            self.note("ret", "the panel carries no return or close column")
            return []
        r = np.nan_to_num(_finite(panel.columns["ret"]))
        _state, x = _realised(self, panel)
        train, _ = panel.split()
        price = self.exponent(np.cumsum(r[train]))
        resid = self.exponent(np.cumsum(x[train]))
        if price is None:
            self.note("msd", "fewer than three usable lags on the training slice")
            return []
        per_era = _era_values(panel, lambda rows: (self.exponent(np.cumsum(r[rows]))
                                                   or (None,))[0])
        with _quiet():
            d24 = G.evaluate(["rstd", ["diff", "close", 24], 120], panel.columns, panel.n)
            d3 = G.evaluate(["rstd", ["diff", "close", 3], 120], panel.columns, panel.n)
            rolling = 2.0 * np.log(d24 / d3) / math.log(8.0)
        name = _mint(self, panel, "diffusion_exponent", rolling, "mathlab:anomalous_diffusion",
                     "dimensionless")
        alpha = price[0]
        regime = "sub-diffusive" if alpha < 0.9 else ("super-diffusive" if alpha > 1.1
                                                       else "Brownian")
        diagnostics = {"alpha_price": round(alpha, 4), "r2_price": round(price[1], 4),
                       "alpha_residual": round(resid[0], 4) if resid else None,
                       "msd_price": [round(v, 10) for v in price[2]], "lags": list(self.LAGS),
                       "per_era_alpha": per_era, "regime": regime,
                       "method": "MSD in logs over eight lags; rolling exponent from the "
                                 "24-bar / 3-bar dispersion ratio over 120 bars"}
        ratio_tree = ["div", ["rstd", ["diff", "close", 24], 120],
                      ["rstd", ["diff", "close", 3], 120]]
        out = [self.emit(panel, "law", ratio_tree,
                         f"DIFFUSION EXPONENT alpha = {alpha:.3f} ({regime}; R^2 {price[1]:.3f}); "
                         f"per era {per_era}", diagnostics=diagnostics),
               self.emit(panel, "representation", ["z", name, 240],
                         "the rolling diffusion exponent as a state variable",
                         diagnostics=diagnostics)]
        if alpha < 1.0:
            gate: Any = ["lt", name, 1.0]
            side = "fade"
        else:
            gate = ["gt", name, 1.0]
            side = "follow"
        tree = ["mul", ["sign", ["diff", "close", 8]], gate]
        values = np.nan_to_num(G.evaluate(tree, panel.columns, panel.n))
        corr = _train_corr(panel, values)
        out.append(self.emit(panel, "relationship", tree,
                             f"momentum gated by the diffusion regime ({regime}): {side} it; "
                             f"training IC {corr:+.4f}",
                             side_mode=side, diagnostics=diagnostics))
        _ = (deadline, rng)
        return out


# ==================================================================== 4. renormalisation
class Renormalisation(Scientist):
    """Coarse-graining: block the returns at scales 1, 2, 4, ... 32 and watch the moments flow.

    Variance scaling gives the Hurst exponent; the decay of excess kurtosis under blocking gives
    the scale at which the Gaussian fixed point is reached (the crossover scale); the flow of the
    residual's lag-one autocorrelation under decimation says whether memory is a relevant or an
    irrelevant operator. The crossover scale is then handed to the search as an operator: search
    at the scale where the process is simplest.
    """

    tradition = "renormalisation"
    searches_for = ("law", "representation", "search_method")

    SCALES = (1, 2, 4, 8, 16, 32)

    @staticmethod
    def blocks(values: np.ndarray, b: int) -> np.ndarray:
        n = (values.size // b) * b
        return values[:n].reshape(-1, b).sum(1) if b > 1 else values.copy()

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        if "ret" not in panel.columns:
            self.note("ret", "the panel carries no return column")
            return []
        r = np.nan_to_num(_finite(panel.columns["ret"]))
        _state, x = _realised(self, panel)
        train, _ = panel.split()
        flow: list[dict[str, Any]] = []
        for b in self.SCALES:
            rb, xb = self.blocks(r[train], b), self.blocks(x[train], b)
            if rb.size < 40:
                break
            flow.append({"scale": b, "var": float(np.var(rb)), "kurtosis": _kurtosis(rb),
                         "phi_residual": _acf(xb, 1), "phi_ret": _acf(rb, 1)})
        if len(flow) < 3:
            self.note("coarse_graining", "fewer than three scales carry 40 blocks")
            return []
        hurst = _loglog_fit([f["scale"] for f in flow], [f["var"] for f in flow])
        kurt = _loglog_fit([f["scale"] for f in flow if f["kurtosis"] > 0],
                           [f["kurtosis"] for f in flow if f["kurtosis"] > 0])
        crossover = next((f["scale"] for f in flow if f["kurtosis"] < 0.5), None)
        memory = [round(f["phi_residual"], 4) for f in flow]
        diagnostics = {"flow": [{k: (round(v, 8) if isinstance(v, float) else v)
                                 for k, v in f.items()} for f in flow],
                       "hurst": round(hurst[0] / 2.0, 4) if hurst else None,
                       "kurtosis_decay_gamma": round(-kurt[0], 4) if kurt else None,
                       "gaussian_crossover_scale": crossover, "memory_flow": memory,
                       "method": "block sums at six scales; variance and excess-kurtosis "
                                 "scaling fitted in logs; lag-one autocorrelation under "
                                 "decimation"}
        ratio_tree = ["div", ["rstd", "ret", 48], ["rstd", "ret", 8]]
        out = [self.emit(panel, "law", ratio_tree,
                         f"SCALING: H = {diagnostics['hurst']} from variance flow; excess "
                         f"kurtosis decays with exponent {diagnostics['kurtosis_decay_gamma']}; "
                         f"Gaussian crossover at scale {crossover}; residual memory under "
                         f"decimation {memory}", diagnostics=diagnostics),
               self.emit(panel, "representation", ["z", ratio_tree, 240],
                         "the coarse-to-fine dispersion ratio as a state variable",
                         diagnostics=diagnostics)]
        scale = _nearest_window(crossover or 24)
        out.append(self.emit(panel, "search_method", ["rmean", "ret", scale],
                             f"SEARCH AT THE FIXED-POINT SCALE: coarse-grain returns over {scale} "
                             f"bars before searching; below that scale the kurtosis is not "
                             f"Gaussian and above it the memory operator has flowed to "
                             f"{memory[-1]}", diagnostics=diagnostics))
        if time.monotonic() < deadline:
            tree, notes = self.projection(panel, min(240, scale * 4), fast=scale,
                                          why=f"the crossover scale is {scale} bars")
            values = np.nan_to_num(G.evaluate(tree, panel.columns, panel.n))
            corr = _train_corr(panel, values)
            out.append(self.emit(panel, "relationship", tree,
                                 f"momentum at the crossover scale, training IC {corr:+.4f}",
                                 side_mode=_side(corr), diagnostics=diagnostics, notes=notes))
        _ = rng
        return out


# ==================================================================== 5. criticality
class Criticality(Scientist):
    """Avalanche statistics: are the residual's bursts power-law distributed, and is the
    cascade near its critical branching ratio?

    An avalanche is a maximal run of bars whose realised residual magnitude exceeds its median.
    Sizes are fitted by the continuous power-law MLE alpha = 1 + n / sum ln(s / s_min) and
    compared with an exponential alternative by the log-likelihood ratio; the branching ratio is
    the mean magnitude carried from one bar of an avalanche to the next. A power law with a
    branching ratio near one is a system at criticality, where the next burst's size has no
    typical scale -- which is exactly the regime a fixed stop is mis-sized for.
    """

    tradition = "criticality"
    searches_for = ("law", "mechanism", "relationship")

    @staticmethod
    def avalanches(magnitude: np.ndarray, threshold: float
                   ) -> tuple[np.ndarray, np.ndarray, float]:
        active = magnitude > threshold
        sizes: list[float] = []
        durations: list[int] = []
        ratios: list[float] = []
        i = 0
        n = magnitude.size
        while i < n:
            if not active[i]:
                i += 1
                continue
            j = i
            while j < n and active[j]:
                j += 1
            sizes.append(float(magnitude[i:j].sum()))
            durations.append(j - i)
            if j - i >= 2:
                with _quiet():
                    ratios.extend((magnitude[i + 1:j]
                                   / np.maximum(magnitude[i:j - 1], 1e-12)).tolist())
            i = j
        branching = float(np.mean(ratios)) if ratios else float("nan")
        return np.asarray(sizes), np.asarray(durations, dtype=float), branching

    @staticmethod
    def power_law(sizes: np.ndarray) -> dict[str, float] | None:
        if sizes.size < 30:
            return None
        s_min = float(np.quantile(sizes, 0.5))
        tail = sizes[sizes >= s_min]
        if tail.size < 15 or s_min <= 0:
            return None
        logs = np.log(tail / s_min)
        alpha = 1.0 + tail.size / max(1e-12, float(logs.sum()))
        lam = 1.0 / max(1e-12, float(np.mean(tail - s_min)))
        ll_pl = np.log(alpha - 1.0) - np.log(s_min) - alpha * logs
        ll_exp = np.log(lam) - lam * (tail - s_min)
        diff = ll_pl - ll_exp
        llr = float(diff.sum())
        z = llr / max(1e-12, math.sqrt(tail.size) * float(np.std(diff)))
        return {"alpha": float(alpha), "s_min": s_min, "n_tail": float(tail.size),
                "llr_vs_exponential": llr, "llr_z": float(z)}

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        state, x = _realised(self, panel)
        train, _ = panel.split()
        magnitude = np.abs(x[train])
        threshold = float(np.median(magnitude))
        sizes, durations, branching = self.avalanches(magnitude, threshold)
        fit = self.power_law(sizes)
        if fit is None:
            self.note("avalanches", f"{sizes.size} avalanches on the training slice, fewer than "
                                    "the 30 an exponent needs")
            return []
        sd_fit = _loglog_fit(durations[durations > 0], sizes[durations > 0])
        per_era = _era_values(panel, lambda rows: (self.power_law(self.avalanches(
            np.abs(x[rows]), threshold)[0]) or {}).get("alpha"))
        critical = fit["llr_z"] > 1.0 and abs(branching - 1.0) < 0.25
        diagnostics: dict[str, Any] = {
                       **{k: round(v, 5) for k, v in fit.items()},
                       "branching_ratio": round(branching, 4) if math.isfinite(branching) else None,
                       "size_duration_exponent": round(sd_fit[0], 4) if sd_fit else None,
                       "avalanches": int(sizes.size), "threshold": round(threshold, 8),
                       "per_era_alpha": per_era, "critical": bool(critical),
                       "method": "runs above the median magnitude; power-law MLE vs exponential "
                                 "by log-likelihood ratio; branching = mean carried magnitude"}
        gate = ["gt", ["abs", ["z", "ret", 24]], 2.0]
        out = [self.emit(panel, "law", gate,
                         f"AVALANCHE SIZES: alpha = {fit['alpha']:.3f} over {int(fit['n_tail'])} "
                         f"tail events, LLR vs exponential z = {fit['llr_z']:+.2f}, branching "
                         f"{diagnostics['branching_ratio']}; per era {per_era}",
                         diagnostics=diagnostics)]
        if critical:
            out.append(self.emit(panel, "mechanism", ["mul", ["abs", ["z", "ret", 24]],
                                                      ["rstd", state, 24]],
                                 f"NEAR-CRITICAL CASCADE: power-law sizes (z {fit['llr_z']:+.2f}) "
                                 f"with branching ratio {branching:.3f} -- the next burst has no "
                                 f"typical size, so a fixed-width stop is mis-sized by "
                                 f"construction", diagnostics=diagnostics))
        after = np.nan_to_num(G.evaluate(gate, panel.columns, panel.n))
        hits = train[after[train] > 0.5]
        if hits.size >= 20:
            mean_after = float(np.mean(panel.epsilon[hits]))
            se = float(np.std(panel.epsilon[hits]) / math.sqrt(hits.size))
            side = _side(mean_after)
            out.append(self.emit(panel, "relationship", ["mul", ["sign", "ret"], gate],
                                 f"AFTER AN EXTREME BAR (|z| > 2, {hits.size} training events) the "
                                 f"residual averages {mean_after:+.6f} (se {se:.6f}): {side} it",
                                 side_mode=side, diagnostics=diagnostics))
        else:
            self.note("post_avalanche", f"{hits.size} extreme bars on the training slice")
        _ = (deadline, rng)
        return out


# ==================================================================== 6. Takens reconstruction
class TakensReconstruction(Scientist):
    """Delay embedding chosen by the data: the delay at the first minimum of the lagged mutual
    information, the dimension at which false nearest neighbours vanish, and the largest
    Lyapunov exponent by Rosenstein's nearest-neighbour divergence.

    The state variable minted is EMBEDDING NOVELTY: how far the current delay vector is from
    the nearest of the previous 240 -- a state the system has never visited is one where no
    reconstructed law applies, which is information the search should have.
    """

    tradition = "takens_reconstruction"
    searches_for = ("representation", "law", "mechanism")

    MAX_DIM = 6
    MAX_DELAY = 12
    LOOKBACK = 240

    @staticmethod
    def _binned_mi(a: np.ndarray, b: np.ndarray, bins: int = 8) -> float:
        ba, bb = _quantile_bins(a, bins), _quantile_bins(b, bins)
        joint = np.zeros((bins, bins))
        np.add.at(joint, (ba, bb), 1.0)
        joint /= max(1.0, joint.sum())
        pa, pb = joint.sum(1, keepdims=True), joint.sum(0, keepdims=True)
        with _quiet():
            ratio = np.where(joint > 0, joint / np.maximum(pa * pb, 1e-15), 1.0)
            term = np.where(joint > 0, joint * np.log(ratio), 0.0)
        return float(term.sum())

    def delay(self, x: np.ndarray) -> tuple[int, list[float]]:
        mis = [self._binned_mi(x[tau:], x[:-tau]) for tau in range(1, self.MAX_DELAY + 1)]
        for i in range(1, len(mis) - 1):
            if mis[i] < mis[i - 1] and mis[i] <= mis[i + 1]:
                return i + 1, mis
        return int(np.argmin(mis)) + 1, mis

    @staticmethod
    def embed(x: np.ndarray, m: int, tau: int) -> np.ndarray:
        n = x.size - (m - 1) * tau
        return np.column_stack([x[i * tau:i * tau + n] for i in range(m)])

    def false_neighbours(self, x: np.ndarray, tau: int) -> tuple[int, list[float]]:
        fractions: list[float] = []
        for m in range(1, self.MAX_DIM + 1):
            big = self.embed(x, m + 1, tau)
            small = big[:, :m]
            if small.shape[0] < 50:
                break
            d = np.sqrt(((small[:, None, :] - small[None, :, :]) ** 2).sum(-1))
            np.fill_diagonal(d, np.inf)
            nn = d.argmin(1)
            with _quiet():
                growth = (np.abs(big[:, m] - big[nn, m])
                          / np.maximum(d[np.arange(d.shape[0]), nn], 1e-12))
            fractions.append(float(np.mean(growth > 10.0)))
            if fractions[-1] < 0.1:
                return m, fractions
        return (len(fractions) or 1), fractions

    def lyapunov(self, x: np.ndarray, m: int, tau: int, steps: int = 8
                 ) -> tuple[float | None, list[float]]:
        emb = self.embed(x, m, tau)
        n = emb.shape[0] - steps
        if n < 60:
            return None, []
        d = np.sqrt(((emb[:n, None, :] - emb[None, :n, :]) ** 2).sum(-1))
        idx = np.arange(n)
        d[np.abs(idx[:, None] - idx[None, :]) < max(1, m * tau)] = np.inf
        nn = d.argmin(1)
        curve: list[float] = []
        for k in range(steps + 1):
            with _quiet():
                dist = np.sqrt(((emb[idx + k] - emb[nn + k]) ** 2).sum(-1))
                curve.append(float(np.mean(np.log(np.maximum(dist, 1e-12)))))
        slope = float(np.polyfit(np.arange(steps + 1), curve, 1)[0])
        return slope, curve

    def novelty(self, x: np.ndarray, m: int, tau: int, deadline: float) -> np.ndarray:
        emb = self.embed(x, m, tau)
        offset = x.size - emb.shape[0]
        out = np.full(x.size, np.nan)
        for t in range(self.LOOKBACK, emb.shape[0]):
            if (t & 255) == 0 and time.monotonic() > deadline:
                break
            window = emb[t - self.LOOKBACK:t]
            out[offset + t] = float(np.sqrt(((window - emb[t]) ** 2).sum(1)).min())
        return out

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        state, x_full = _realised(self, panel)
        x = _z(np.nan_to_num(x_full))
        train, _ = panel.split()
        sample = x[train][-CLOUD_CAP:]
        tau, mis = self.delay(sample)
        m, fnn = self.false_neighbours(sample, tau)
        lam, curve = self.lyapunov(sample, m, tau)
        novelty = self.novelty(x, m, tau, deadline)
        name = _mint(self, panel, "embedding_novelty", novelty, "mathlab:takens_reconstruction",
                     "residual sd")
        diagnostics = {"delay": tau, "dimension": m,
                       "mutual_information_by_lag": [round(v, 5) for v in mis],
                       "false_neighbour_fraction": [round(v, 4) for v in fnn],
                       "lyapunov_max": round(lam, 5) if lam is not None else None,
                       "divergence_curve": [round(v, 4) for v in curve],
                       "sample": int(sample.size), "lookback": self.LOOKBACK,
                       "method": "first minimum of lagged MI; Kennel false nearest neighbours; "
                                 "Rosenstein divergence slope; novelty = distance to the nearest "
                                 "of the previous 240 delay vectors"}
        if lam is None:
            self.note("lyapunov", "fewer than 60 embedded points after the divergence horizon")
        out = [self.emit(panel, "representation", ["z", name, 240],
                         f"EMBEDDING NOVELTY in the (m={m}, tau={tau}) reconstruction: how far "
                         f"the current state is from anything seen in the last {self.LOOKBACK} "
                         f"bars", diagnostics=diagnostics),
               self.emit(panel, "law", ["rstd", state, _nearest_window(m * tau)],
                         f"RECONSTRUCTION: delay {tau}, dimension {m} (FNN {fnn}), largest "
                         f"Lyapunov exponent {diagnostics['lyapunov_max']} per bar",
                         diagnostics=diagnostics)]
        if lam is not None and lam > 0.05:
            out.append(self.emit(panel, "mechanism", ["z", name, 48],
                                 f"SENSITIVE DEPENDENCE: lambda_max = {lam:.4f}/bar, a "
                                 f"predictability horizon of about {1.0 / lam:.1f} bars beyond "
                                 f"which any reconstructed law is noise", diagnostics=diagnostics))
        corr = _train_corr(panel, np.nan_to_num(novelty))
        out.append(self.emit(panel, "relationship", ["z", name, 240],
                             f"novel states read the residual with training IC {corr:+.4f}",
                             side_mode=_side(corr), diagnostics=diagnostics))
        _ = rng
        return out


# ==================================================================== 7. chaos tests
class ChaosTests(Scientist):
    """The 0-1 test for chaos (Gottwald-Melbourne) and a phase-randomised surrogate test.

    The 0-1 test drives a translation variable with the series and asks whether its mean
    square displacement grows linearly (K near 1, chaotic) or stays bounded (K near 0, regular).
    The surrogate test keeps the power spectrum and randomises the phases nineteen times: a
    nonlinear statistic that the surrogates cannot reproduce is structure a linear-Gaussian model
    cannot hold, whatever K says. Both are reported; neither is a fit.
    """

    tradition = "chaos_tests"
    searches_for = ("law", "mechanism", "relationship")

    SURROGATES = 19
    CS = 8

    @classmethod
    def zero_one(cls, x: np.ndarray, rng: np.random.Generator) -> tuple[float, list[float]]:
        n = x.size
        ncut = max(10, min(100, n // 10))
        js = np.arange(n)
        ks: list[float] = []
        for c in rng.uniform(0.2, math.pi - 0.2, cls.CS):
            p = np.cumsum(x * np.cos(js * c))
            q = np.cumsum(x * np.sin(js * c))
            ms = [float(np.mean((p[k:] - p[:-k]) ** 2 + (q[k:] - q[:-k]) ** 2))
                  for k in range(1, ncut + 1)]
            ks.append(_corr(np.arange(1, ncut + 1, dtype=float), np.asarray(ms)))
        return float(np.median(ks)), ks

    @staticmethod
    def asymmetry(x: np.ndarray) -> float:
        a, b = x[1:], x[:-1]
        sd = max(1e-12, float(np.std(x)))
        return float((np.mean(a * a * b) - np.mean(a * b * b)) / sd ** 3)

    @classmethod
    def surrogate_p(cls, x: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
        spectrum = np.fft.rfft(x - x.mean())
        original = abs(cls.asymmetry(x))
        beats = 0
        for _ in range(cls.SURROGATES):
            phases = rng.uniform(0, 2 * math.pi, spectrum.size)
            phases[0] = 0.0
            surrogate = np.fft.irfft(np.abs(spectrum) * np.exp(1j * phases), n=x.size)
            beats += int(abs(cls.asymmetry(surrogate)) >= original)
        return (1.0 + beats) / (1.0 + cls.SURROGATES), original

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        _state, x_full = _realised(self, panel)
        x = _z(np.nan_to_num(x_full))
        train, _ = panel.split()
        sample = x[train][-4 * CLOUD_CAP:]
        if sample.size < 200:
            self.note("chaos", f"{sample.size} training rows")
            return []
        k_stat, ks = self.zero_one(sample, rng)
        p_surr, asym = self.surrogate_p(sample, rng)
        per_era = _era_values(panel, lambda rows: self.zero_one(x[rows][-4 * CLOUD_CAP:],
                                                                np.random.default_rng(1))[0])
        verdict = ("CHAOTIC" if k_stat > 0.8 else ("REGULAR" if k_stat < 0.2 else "MIXED"))
        diagnostics = {"k_statistic": round(k_stat, 4), "k_by_c": [round(v, 4) for v in ks],
                       "surrogate_p": round(p_surr, 4), "asymmetry": round(asym, 5),
                       "surrogates": self.SURROGATES, "per_era_k": per_era,
                       "verdict": verdict, "sample": int(sample.size),
                       "method": "0-1 test over eight translation frequencies; phase-randomised "
                                 "surrogates against the time-reversal asymmetry"}
        curvature = ["curv", "close", 5]
        out = [self.emit(panel, "law", curvature,
                         f"0-1 TEST K = {k_stat:.3f} ({verdict}); surrogate p = {p_surr:.3f} for "
                         f"the third-moment asymmetry; per era {per_era}",
                         diagnostics=diagnostics)]
        if p_surr < 0.1:
            out.append(self.emit(panel, "mechanism", ["mul", curvature, ["abs", ["z", "ret", 24]]],
                                 f"NONLINEAR STRUCTURE A LINEAR-GAUSSIAN MODEL CANNOT HOLD: none "
                                 f"of {self.SURROGATES} spectrum-preserving surrogates reproduces "
                                 f"the asymmetry {asym:+.4f} (p {p_surr:.3f})",
                                 diagnostics=diagnostics))
        values = np.nan_to_num(G.evaluate(curvature, panel.columns, panel.n))
        corr = _train_corr(panel, values)
        out.append(self.emit(panel, "relationship", curvature,
                             f"price curvature reads the residual with training IC {corr:+.4f}",
                             side_mode=_side(corr), diagnostics=diagnostics))
        _ = deadline
        return out


# ==================================================================== 8. linear response
class LinearResponse(Scientist):
    """Fluctuation-dissipation: the residual's response to an impulse in a driver, against the
    driver's own autocorrelation, and Onsager reciprocity between the two directions.

    The impulse response h_k = cov(eps_t, d_{t-k}) / var(d) is what a kick in the driver does to
    the residual k bars later; the fluctuation-dissipation theorem says that for a system in
    equilibrium h_k is proportional to the driver's autocorrelation rho_k. A response that
    tracks the fluctuation is a passive system; one that does not is driven. Reciprocity asks
    whether the residual kicks the driver back as hard -- when it does not, the arrow points.
    """

    tradition = "linear_response"
    searches_for = ("relationship", "law", "mechanism")

    LAGS = (2, 3, 5, 8, 12)

    def _fdt(self, panel: Panel, driver: str, rows: np.ndarray) -> float:
        series = _fluct(panel.columns[driver])
        eps = np.nan_to_num(panel.epsilon)
        responses = [float(np.cov(eps[rows[rows >= k]], series[rows[rows >= k] - k])[0, 1])
                     for k in self.LAGS]
        fluct = [_acf(series[rows], k) for k in self.LAGS]
        return _corr(np.asarray(responses), np.asarray(fluct))

    def _screen(self, panel: Panel, state: str, train: np.ndarray, keep: int = 8) -> list[str]:
        """Candidate drivers ranked by their strongest LAGGED correlation with the residual."""
        eps = np.nan_to_num(panel.epsilon)
        scored: list[tuple[float, str]] = []
        for c in panel.names:
            if c == state:
                continue
            series = _fluct(panel.columns[c])
            if float(np.var(series[train])) < 1e-15:
                continue
            best = max(abs(_corr(eps[train[train >= k]], series[train[train >= k] - k]))
                       for k in self.LAGS)
            scored.append((best, c))
        scored.sort(key=lambda r: (-r[0], r[1]))
        return [c for _, c in scored[:keep]]

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        state, x = _realised(self, panel)
        train, _ = panel.split()
        # A LAGGED response is not ranked by a CONTEMPORANEOUS correlation: the column that
        # kicks the residual five bars from now need not move with it today, and on a panel of
        # thirteen columns the one carrying a planted impulse ranked LAST by same-bar |corr|.
        # So the screen is the scientist's own question -- the strongest LAGGED correlation of
        # the driver's stationary fluctuation with the residual, over the same lag grid.
        drivers = self._screen(panel, state, train)
        if not drivers:
            self.note("drivers", "no column to kick")
            return []
        best: dict[str, Any] | None = None
        table: dict[str, Any] = {}
        eps = panel.epsilon
        for d in drivers:
            series = _fluct(panel.columns[d])
            var = float(np.var(series[train]))
            if var < 1e-15:
                continue
            responses: dict[int, float] = {}
            fluct: dict[int, float] = {}
            back: dict[int, float] = {}
            for k in self.LAGS:
                rows = train[train >= k]
                a, b = eps[rows], series[rows - k]
                mask = np.isfinite(a)
                if int(mask.sum()) < 60:
                    continue
                responses[k] = float(np.cov(a[mask], b[mask])[0, 1] / var)
                fluct[k] = _acf(series[train], k)
                back[k] = float(np.cov(series[rows], x[rows - k])[0, 1]
                                / max(1e-15, float(np.var(x[train]))))
            if len(responses) < 3:
                continue
            fdt = _corr(np.asarray([responses[k] for k in responses]),
                        np.asarray([fluct[k] for k in responses]))
            k_star = max(responses, key=lambda k: abs(responses[k]))
            rows = train[train >= k_star]
            t = abs(_corr(eps[rows], series[rows - k_star])) * math.sqrt(max(1, rows.size))
            reciprocity = abs(responses[k_star]) / max(1e-12, abs(back.get(k_star, 0.0)))
            table[d] = {"impulse_response": {str(k): round(v, 6) for k, v in responses.items()},
                        "fluctuation": {str(k): round(v, 4) for k, v in fluct.items()},
                        "fdt_corr": round(fdt, 4), "best_lag": k_star, "t": round(t, 3),
                        "reciprocity_ratio": round(reciprocity, 4),
                        "driver_transform": _fluct_kind(panel.columns[d])}
            if best is None or t > best["t"]:
                best = {"driver": d, "lag": k_star, "sign": responses[k_star], "t": t,
                        "fdt": fdt, "reciprocity": reciprocity}
            self.evaluated += 1
        if best is None:
            self.note("impulse_response", "no driver carried three usable lags")
            return []
        driver = str(best["driver"])
        per_era_fdt = _era_values(panel, lambda rows: self._fdt(panel, driver, rows))
        diagnostics = {"table": table, "best": {k: (round(v, 5) if isinstance(v, float) else v)
                                                for k, v in best.items()},
                       "per_era_fdt": per_era_fdt,
                       "driver_transform": _fluct_kind(panel.columns[driver]),
                       "drivers_scanned": drivers,
                       "method": "lagged covariance impulse response vs driver autocorrelation, "
                                 "on the STATIONARY fluctuation of each driver (a near unit root "
                                 "is differenced first, so no spurious level regression can win "
                                 "the scan); reciprocity = forward over backward response"}
        tree = ["lag", driver, _nearest_window(best["lag"])]
        side = _side(best["sign"])
        out = [self.emit(panel, "relationship", tree,
                         f"IMPULSE RESPONSE: a kick in {driver} moves the residual "
                         f"{best['sign']:+.6f} per unit variance {best['lag']} bars later "
                         f"(t {best['t']:.2f}): {side}", side_mode=side, diagnostics=diagnostics),
               self.emit(panel, "law", ["rmean", driver, _nearest_window(best["lag"])],
                         f"FLUCTUATION-DISSIPATION: response tracks fluctuation with correlation "
                         f"{best['fdt']:+.3f} across five lags; per era {per_era_fdt}",
                         diagnostics=diagnostics)]
        if best["reciprocity"] > 3.0:
            out.append(self.emit(panel, "mechanism", tree,
                                 f"RECIPROCITY BROKEN: {driver} drives the residual "
                                 f"{best['reciprocity']:.1f}x harder than the residual drives it "
                                 f"back -- a one-way transmission, not a shared shock",
                                 side_mode=side, diagnostics=diagnostics))
        _ = (deadline, rng)
        return out


# ==================================================================== 9. field / continuum
class FieldContinuum(Scientist):
    """The order book as a continuum: a density of ticks per unit price range, its gradient,
    and a continuity equation for the flow of activity.

    Fusion publishes tick counts and bar ranges, not a book, so the density field is
    activity / range -- ticks per unit of price travelled, the retail-feed proxy for how much
    liquidity the bar met per unit move. The flux is density times drift (body); the continuity
    residual d(rho)/dt + d(rho v)/dt is what a conserved flow would leave at zero, and how far
    it is from zero relative to a body-shuffled null says whether activity is conserved or
    injected.
    """

    tradition = "field_continuum"
    searches_for = ("representation", "law", "relationship", "mechanism")

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        needed = [c for c in ("activity", "range", "body") if c in panel.columns]
        if len(needed) < 3:
            self.note("field", f"the panel lacks { {'activity', 'range', 'body'} - set(needed)}")
            return []
        with _quiet():
            density = G.evaluate(["div", "activity", "range"], panel.columns, panel.n)
        if not np.isfinite(density).any() or float(np.nanstd(density)) < 1e-12:
            self.note("density", "activity / range is constant or undefined on this panel")
            return []
        _mint(self, panel, "density", density, "mathlab:field_continuum",
              "ticks per unit relative range")
        density_tree = ["div", "activity", "range"]
        continuity_tree = ["add", ["diff", density_tree, 2],
                           ["diff", ["mul", density_tree, "body"], 2]]
        with _quiet():
            continuity = G.evaluate(continuity_tree, panel.columns, panel.n)
            shuffled = dict(panel.columns)
            shuffled["body"] = rng.permutation(np.nan_to_num(panel.columns["body"]))
            null = G.evaluate(continuity_tree, shuffled, panel.n)
        train, _ = panel.split()
        with _quiet():
            var_c = float(np.nanvar(continuity[train]))
            var_null = float(np.nanvar(null[train]))
        ratio = var_c / var_null if var_null > 1e-15 else None
        per_era = _era_values(panel, lambda rows: float(np.nanvar(continuity[rows])
                                                        / max(1e-15, np.nanvar(null[rows]))))
        gradient = np.nan_to_num(G.evaluate(["diff", density_tree, 3], panel.columns, panel.n))
        corr_grad = _train_corr(panel, gradient)
        corr_density = _train_corr(panel, np.nan_to_num(G.evaluate(["z", density_tree, 48],
                                                                   panel.columns, panel.n)))
        conserved = "conserved" if ratio is not None and ratio < 0.8 else "not conserved"
        diagnostics = {"continuity_variance_ratio": round(ratio, 4) if ratio is not None else None,
                       "per_era_ratio": per_era, "density_ic_train": round(corr_density, 4),
                       "gradient_ic_train": round(corr_grad, 4),
                       "method": "density = activity / range; flux = density x body; continuity "
                                 "residual vs a body-shuffled null"}
        out = [self.emit(panel, "representation", density_tree,
                         "LIQUIDITY DENSITY: ticks per unit of relative range, the continuum "
                         "field a retail feed can see", diagnostics=diagnostics),
               self.emit(panel, "relationship", ["z", density_tree, 48],
                         f"density state reads the residual with training IC {corr_density:+.4f}",
                         side_mode=_side(corr_density), diagnostics=diagnostics),
               self.emit(panel, "law", continuity_tree,
                         f"CONTINUITY: the flow residual carries "
                         f"{diagnostics['continuity_variance_ratio']} of the shuffled-drift "
                         f"variance ({conserved}); per era {per_era}", diagnostics=diagnostics)]
        if abs(corr_grad) > abs(corr_density):
            out.append(self.emit(panel, "mechanism", ["diff", density_tree, 3],
                                 f"PRESSURE GRADIENT: the change of density predicts the residual "
                                 f"better than its level ({corr_grad:+.4f} vs "
                                 f"{corr_density:+.4f}); "
                                 f"liquidity arriving, not liquidity present, is the force",
                                 side_mode=_side(corr_grad), diagnostics=diagnostics))
        _ = deadline
        return out


# ==================================================================== 10. turbulence
class Turbulence(Scientist):
    """Structure functions S_q(tau) = <|X(t+tau) - X(t)|^q> and their scaling exponents zeta(q).

    A monofractal path has zeta(q) linear in q (zeta(q) = qH); intermittency is the concavity
    zeta(4) - 2 zeta(2) < 0, the signature of a multiplicative cascade in which large-scale
    dispersion feeds small-scale dispersion. The cascade direction is measured directly as the
    asymmetry of the lagged cross-correlation between coarse and fine magnitudes: coarse
    predicting fine is the direct cascade, the opposite is the inverse one.
    """

    tradition = "turbulence"
    searches_for = ("law", "representation", "mechanism", "relationship")

    QS = (1, 2, 3, 4, 6)
    TAUS = (1, 2, 3, 5, 8, 12, 24, 48)

    @classmethod
    def structure(cls, path: np.ndarray, q: float) -> list[float]:
        return [float(np.mean(np.abs(path[tau:] - path[:-tau]) ** q)) for tau in cls.TAUS]

    @classmethod
    def intermittency(cls, path: np.ndarray) -> float | None:
        z4 = _loglog_fit(cls.TAUS, cls.structure(path, 4))
        z2 = _loglog_fit(cls.TAUS, cls.structure(path, 2))
        return z4[0] - 2.0 * z2[0] if z4 and z2 else None

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        if "ret" not in panel.columns:
            self.note("ret", "the panel carries no return column")
            return []
        r = np.nan_to_num(_finite(panel.columns["ret"]))
        train, _ = panel.split()
        path = np.cumsum(r[train])
        zetas: dict[int, float] = {}
        ess: dict[int, float] = {}
        s3 = self.structure(path, 3)
        for q in self.QS:
            sq = self.structure(path, q)
            fit = _loglog_fit(self.TAUS, sq)
            if fit is None:
                continue
            zetas[q] = fit[0]
            ess_fit = _loglog_fit(s3, sq)
            if ess_fit is not None:
                ess[q] = ess_fit[0]
        if len(zetas) < 3:
            self.note("structure_functions", "fewer than three moments fitted")
            return []
        intermittency = zetas.get(4, 0.0) - 2.0 * zetas.get(2, 0.0)
        with _quiet():
            coarse = np.abs(np.nan_to_num(G.evaluate(["diff", "close", 24], panel.columns,
                                                     panel.n)))
        fine = np.abs(r)
        k = 5
        rows = train[train >= k]
        direct = _corr(coarse[rows - k], fine[rows])
        inverse = _corr(fine[rows - k], coarse[rows])
        per_era = _era_values(panel, lambda rows_: self.intermittency(np.cumsum(r[rows_])))
        kind = "multifractal" if intermittency < -0.05 else "monofractal within noise"
        diagnostics = {"zeta": {str(q): round(v, 4) for q, v in zetas.items()},
                       "ess_slope_vs_q3": {str(q): round(v, 4) for q, v in ess.items()},
                       "intermittency": round(intermittency, 4),
                       "cascade_direct_corr": round(direct, 4),
                       "cascade_inverse_corr": round(inverse, 4),
                       "per_era_intermittency": per_era,
                       "method": "structure functions over eight lags fitted in logs; extended "
                                 "self-similarity against S_3; coarse/fine magnitude cross-"
                                 "correlation asymmetry at lag 5"}
        ratio_tree = ["div", ["rstd", "ret", 5], ["rstd", "ret", 48]]
        out = [self.emit(panel, "law", ratio_tree,
                         f"STRUCTURE FUNCTIONS: zeta = {diagnostics['zeta']}; intermittency "
                         f"{intermittency:+.4f} ({kind}); per era {per_era}",
                         diagnostics=diagnostics),
               self.emit(panel, "representation", ["z", ratio_tree, 240],
                         "the fine-to-coarse dispersion ratio: where in the cascade the tape is",
                         diagnostics=diagnostics)]
        if abs(direct - inverse) > 0.05:
            which = "DIRECT" if direct > inverse else "INVERSE"
            out.append(self.emit(panel, "mechanism", ["mul", ["abs", ["diff", "close", 24]],
                                                      ["rstd", "ret", 5]],
                                 f"{which} CASCADE: coarse->fine correlation {direct:+.3f} against "
                                 f"fine->coarse {inverse:+.3f}; dispersion flows "
                                 f"{'down' if which == 'DIRECT' else 'up'} the scales",
                                 diagnostics=diagnostics))
        values = np.nan_to_num(G.evaluate(ratio_tree, panel.columns, panel.n))
        corr = _train_corr(panel, values)
        out.append(self.emit(panel, "relationship", ratio_tree,
                             f"the cascade state reads the residual with training IC {corr:+.4f}",
                             side_mode=_side(corr), diagnostics=diagnostics))
        _ = (deadline, rng)
        return out


PHYSICS_CORE_REGISTRY: dict[str, type[Scientist]] = {
    "statistical_mechanics": StatisticalMechanics,
    "nonequilibrium": Nonequilibrium,
    "anomalous_diffusion": AnomalousDiffusion,
    "renormalisation": Renormalisation,
    "criticality": Criticality,
    "takens_reconstruction": TakensReconstruction,
    "chaos_tests": ChaosTests,
    "linear_response": LinearResponse,
    "field_continuum": FieldContinuum,
    "turbulence": Turbulence,
}
