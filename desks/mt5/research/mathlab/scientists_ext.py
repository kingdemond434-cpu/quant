"""The second cohort of traditions (principal's sandbox lists, 2026-09-22): fourteen more search
distributions over the same residual, each small, each numpy/scipy only.

THE POINT IS A DIFFERENT SEARCH DISTRIBUTION, NOT A LIBRARY PORT. Each class here asks the panel
a question none of the first fourteen asks -- does the ORDER of the path matter (signatures), is
there a linear operator whose modes carry the dynamics (Koopman), what sparse equation generates
the residual (SINDy), do the tails move together when the bodies do not (copulas), which window
has never been seen before (matrix profile), where did the process change (PELT), how old is
this regime and how likely is it to die (Kaplan-Meier), which lag carries information the past
of the target does not (transfer entropy), what do the cascade moments say (scattering), which
asset x feature x time mode is one thing (CP), what does a fixed random dynamical system read
out of the inputs (reservoir), how deterministic is the last window (rolling RQA), how heavy is
the tail beyond the threshold (GPD), and which event sequences precede a residual (sequential
mining). Each one is bounded by a subsample cap and a deadline, names what it could not measure,
and offers an executable projection over bar terminals so its invention can reach the gauntlet.
"""
from __future__ import annotations

import math
import time
from typing import Any

import numpy as np

from . import grammar as G
from .base import CLOUD_CAP, UNMEASURED, Scientist, _corr, _finite, _nearest_window, _quiet, _z
from .objects import MathObject, Panel, Variable


def _ffill(values: np.ndarray) -> np.ndarray:
    out = values.copy()
    last = np.nan
    for i in range(out.size):
        if np.isfinite(out[i]):
            last = out[i]
        else:
            out[i] = last
    return out


def _mint(scientist: Scientist, panel: Panel, name: str, values: np.ndarray, dataset: str,
          units: str) -> str:
    panel.mint(name, values, Variable(name=name, dataset=dataset, source="derived", units=units))
    scientist.minted.append(name)
    return name


def _quantile_bins(values: np.ndarray, bins: int) -> np.ndarray:
    edges = np.quantile(values, np.linspace(0, 1, bins + 1)[1:-1])
    return np.clip(np.digitize(values, edges), 0, bins - 1)


def _transfer_entropy(driver: np.ndarray, target: np.ndarray, lag: int, bins: int = 4
                      ) -> float | None:
    """TE(X -> Y) at `lag` = I(Y_t ; X_{t-lag} | Y_{t-1}), binned on quantiles, in nats."""
    if target.size <= lag + 200:
        return None
    y1, y0, x0 = target[lag:], target[lag - 1:-1], driver[:-lag]
    mask = np.isfinite(y1) & np.isfinite(y0) & np.isfinite(x0)
    if int(mask.sum()) < 200:
        return None
    by1, by0, bx0 = (_quantile_bins(v[mask], bins) for v in (y1, y0, x0))
    joint = np.zeros((bins, bins, bins))
    np.add.at(joint, (by1, by0, bx0), 1.0)
    joint /= max(1.0, joint.sum())
    p_y0x0, p_y1y0, p_y0 = joint.sum(0), joint.sum(2), joint.sum((0, 2))
    with _quiet():
        term = joint * np.log(np.where(
            joint > 0, (joint * p_y0[None, :, None])
            / np.maximum(p_y1y0[:, :, None] * p_y0x0[None, :, :], 1e-15), 1.0))
    return float(max(0.0, np.nansum(np.where(joint > 0, term, 0.0))))


# ===================================================================== rough-path signatures
class RoughPathSignatures(Scientist):
    """Iterated integrals to depth 3 of the (price, volume, spread) path, and an ORDER test.

    A signature is the path's coordinates in a space where order matters: S_ij - S_ji is twice the
    Levy area between two channels, and it is zero for any path whose increments could be
    reshuffled without changing anything. The order-sensitivity test compares the measured area
    against windows whose increments were permuted -- if the real path's area is no larger, the
    order carried no information and nothing built on it should be trusted.
    """

    tradition = "rough_path_signatures"
    searches_for = ("representation", "law")

    WINDOW = 24
    STRIDE = 4
    CHANNELS = ("close", "activity", "spread")

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        channels = [c for c in self.CHANNELS if c in panel.columns]
        if len(channels) < 2:
            self.note("path_channels", f"{len(channels)} of {self.CHANNELS} on the panel; a "
                                       "signature needs at least two")
            return []
        levels = np.column_stack([_z(_finite(panel.columns[c])) for c in channels])
        increments = np.diff(levels, axis=0, prepend=levels[:1])
        k, n = len(channels), panel.n
        names = ([f"S1_{a}" for a in channels]
                 + [f"S2_{a}{b}" for a in channels for b in channels]
                 + [f"S3_{channels[0]}{channels[1]}{channels[-1]}", "levy_area_01"])
        rows = np.full((n, len(names)), np.nan)
        perm_area: list[float] = []
        for t in range(self.WINDOW, n, self.STRIDE):
            if time.monotonic() >= deadline:
                self.note("signature_scan", f"budget reached at bar {t} of {n}")
                break
            block = increments[t - self.WINDOW:t]
            rows[t] = self._signature(block, k)
            shuffled = block[rng.permutation(block.shape[0])]
            perm_area.append(abs(float(self._signature(shuffled, k)[-1])))
        rows = np.column_stack([_ffill(rows[:, j]) for j in range(rows.shape[1])])
        train, _ = panel.split()
        scores = {names[j]: abs(_corr(rows[train, j], panel.epsilon[train]))
                  for j in range(len(names))}
        best = max(scores, key=lambda key: scores[key])
        real_area = float(np.nanmean(np.abs(rows[:, -1]))) if np.isfinite(rows[:, -1]).any() \
            else 0.0
        null_area = float(np.mean(perm_area)) if perm_area else 0.0
        order_matters = bool(real_area > 1.5 * null_area)
        for name in names:
            self.charge(["z", name, 240])
        column = _mint(self, panel, f"sig_{best}", rows[:, names.index(best)],
                       "mathlab:signature", f"depth-3 signature term over {channels}")
        area = _mint(self, panel, "sig_levy_area", rows[:, -1], "mathlab:signature",
                     f"Levy area between {channels[0]} and {channels[1]}")
        diagnostics = {"channels": channels, "window": self.WINDOW, "depth": 3,
                       "term_scores": {k2: round(v, 5) for k2, v in scores.items()},
                       "best_term": best, "mean_abs_levy_area": round(real_area, 6),
                       "permuted_increments_levy_area": round(null_area, 6),
                       "order_sensitive": order_matters,
                       "method": "Chen-style iterated integrals of standardised increments; the "
                                 "order test permutes each window's increments"}
        if not order_matters:
            self.note("order_sensitivity", "the Levy area of the real path is not larger than "
                                           "that of its increment-permuted twin; the path's order "
                                           "carries no measurable information here")
        out = [
            self.emit(panel, "representation", ["z", column, 240],
                      f"A SIGNATURE COORDINATE: the depth-3 iterated integral {best} of the "
                      f"({', '.join(channels)}) path over {self.WINDOW} bars",
                      diagnostics=diagnostics),
            self.emit(panel, "law", ["z", area, 240],
                      f"ORDER MATTERS ({order_matters}): the Levy area between {channels[0]} and "
                      f"{channels[1]} is {real_area:.4g} against {null_area:.4g} for permuted "
                      f"increments", diagnostics=diagnostics),
        ]
        tree, notes = self.projection(panel, 120, fast=self.WINDOW,
                                      why=f"the signature window is {self.WINDOW} bars")
        out.append(self.emit(panel, "law", tree, "the path signature, traded through bar "
                                                 "terminals", diagnostics=diagnostics,
                             notes=notes))
        return out

    @staticmethod
    def _signature(block: np.ndarray, k: int) -> np.ndarray:
        s1 = block.sum(axis=0)
        running = np.cumsum(block, axis=0)
        previous = np.vstack([np.zeros(k), running[:-1]])
        s2 = previous.T @ block
        s2_run = np.cumsum(previous[:, 0] * block[:, 1])
        s2_prev = np.concatenate([[0.0], s2_run[:-1]])
        s3 = float((s2_prev * block[:, -1]).sum())
        levy = float((s2[0, 1] - s2[1, 0]) / 2.0)
        return np.concatenate([s1, s2.ravel(), [s3, levy]])


# ============================================================================ Koopman / DMD
class KoopmanDMD(Scientist):
    """Dynamic mode decomposition of the delay-embedded residual: the linear operator's modes.

    Koopman's premise is that a nonlinear system is linear in the right observables; delay
    coordinates are the cheapest such observables. The dominant mode's eigenvalue says whether
    the residual's dynamics grow, decay or oscillate, and at what period, and its projection is a
    state variable fitted on the training slice and applied forward.
    """

    tradition = "koopman_dmd"
    searches_for = ("representation", "law")

    DELAY = 8
    RANK = 4

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        series = _z(_finite(panel.epsilon))
        n, d = panel.n, self.DELAY
        hankel = np.column_stack([series[d - 1 - i: n - i] for i in range(d)])   # rows = time
        train, _ = panel.split()
        rows = train[train >= d - 1] - (d - 1)
        if rows.size < 200:
            self.note("dmd", f"{rows.size} delay vectors on the training slice")
            return []
        x, y = hankel[rows[:-1]].T, hankel[rows[1:]].T
        u, sing, vt = np.linalg.svd(x, full_matrices=False)
        rank = int(min(self.RANK, int((sing > 1e-8 * sing[0]).sum())))
        if rank < 2:
            self.note("dmd_rank", f"numerical rank {rank} of the snapshot matrix")
            return []
        u_r, s_r, v_r = u[:, :rank], sing[:rank], vt[:rank].T
        a_tilde = u_r.T @ y @ v_r / s_r
        lambdas, w = np.linalg.eig(a_tilde)
        modes = (y @ v_r / s_r) @ w
        order = np.argsort(-np.abs(lambdas))
        lambdas, modes = lambdas[order], modes[:, order]
        angle = np.abs(np.angle(lambdas))
        periods = np.where(angle > 1e-9, 2 * np.pi / np.maximum(angle, 1e-9), np.inf)
        oscillating = [i for i in range(rank) if 2.0 < periods[i] < 1e4]
        dominant = oscillating[0] if oscillating else 0
        projection = np.full(n, np.nan)
        pinv = np.linalg.pinv(modes)
        coefficients = (pinv @ hankel.T)[dominant]
        projection[d - 1:] = np.real(coefficients)
        column = _mint(self, panel, "dmd_mode1", projection, "mathlab:koopman",
                       "real part of the delay vector's coordinate on the dominant DMD mode")
        self.evaluated += rank
        diagnostics = {"delay": d, "rank": rank,
                       "eigenvalue_moduli": [round(float(v), 6) for v in np.abs(lambdas)],
                       "periods_bars": [None if not np.isfinite(p) else round(float(p), 3)
                                        for p in periods],
                       "dominant_mode": int(dominant),
                       "stable": bool(np.max(np.abs(lambdas)) < 1.0 + 1e-9),
                       "method": "exact DMD on Hankel snapshots of the residual, rank-truncated "
                                 "SVD, fitted on the training slice and applied forward"}
        period = float(periods[dominant]) if np.isfinite(periods[dominant]) else 24.0
        out = [
            self.emit(panel, "representation", ["z", column, 240],
                      f"A KOOPMAN COORDINATE: the residual's delay vector projected on DMD mode "
                      f"{dominant} (|lambda| {abs(lambdas[dominant]):.4f}, period "
                      f"{period:.2f} bars)", diagnostics=diagnostics),
            self.emit(panel, "law", ["curv", "close", _nearest_window(max(2.0, period / 2))],
                      f"the dominant mode's period {period:.1f} bars fixes the curvature spacing",
                      diagnostics=diagnostics),
        ]
        if time.monotonic() < deadline:
            tree, notes = self.projection(panel, 120, fast=max(2, int(period / 2)),
                                          why=f"DMD mode {dominant} has period {period:.1f}")
            out.append(self.emit(panel, "law", tree, "the Koopman mode, traded through bar "
                                                     "terminals", diagnostics=diagnostics,
                                 notes=notes))
        _ = rng
        return out


# ======================================================================================= SINDy
class SINDy(Scientist):
    """Sparse identification of the governing equation: d(state)/dt = sparse combination of a
    library, by sequentially thresholded least squares. The equation is the discovery.

    The state is the LAST REALISED residual (lagged by the horizon, so it is knowable), the
    24-bar return z-score and the 24-bar dispersion z-score. The library holds polynomials to
    degree three, a sine and an absolute value. What survives thresholding is written out as an
    equation and every term's magnitude rides in the diagnostics; the executable projection keeps
    only the SIGNS, because a constant multiplier is not a thing the trade grammar can say.
    """

    tradition = "sindy"
    searches_for = ("law", "relationship")

    LAMBDA = 0.08
    ITERATIONS = 10

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        overlap = max(1, int("".join(ch for ch in str(panel.horizon) if ch.isdigit()) or 1))
        lagged = G.evaluate(["lag", "__e__", _nearest_window(overlap)],
                            {"__e__": _finite(panel.epsilon)}, panel.n)
        state = _mint(self, panel, "eps_realised", lagged, "mathlab:sindy",
                      f"the residual lagged by the {overlap}-bar horizon: the last realised value")
        needed = [c for c in ("ret", "range") if c in panel.columns]
        if len(needed) < 2:
            self.note("state_variables", "the panel lacks ret or range")
            return []
        y = G.evaluate(["z", "ret", 24], panel.columns, panel.n)
        w = G.evaluate(["z", "range", 24], panel.columns, panel.n)
        x = _z(np.nan_to_num(lagged))
        y, w = np.nan_to_num(y), np.nan_to_num(w)
        library = {"1": np.ones(panel.n), "x": x, "y": y, "w": w, "x^2": x * x, "x*y": x * y,
                   "x*w": x * w, "y^2": y * y, "x^3": x ** 3, "sin(x)": np.sin(x),
                   "|x|": np.abs(x)}
        target = np.concatenate([np.diff(x), [np.nan]])
        train, _ = panel.split()
        rows = train[np.isfinite(target[train])]
        if rows.size < 300:
            self.note("sindy", f"{rows.size} usable training rows")
            return []
        theta = np.column_stack([library[k][rows] for k in library])
        scale = np.maximum(np.std(theta, axis=0), 1e-9)
        scale[0] = 1.0
        theta_n = theta / scale
        coef = np.linalg.lstsq(theta_n, target[rows], rcond=None)[0]
        active = np.ones(coef.size, dtype=bool)
        for _ in range(self.ITERATIONS):
            small = np.abs(coef) < self.LAMBDA
            coef[small] = 0.0
            active = ~small
            if not active.any():
                break
            coef[active] = np.linalg.lstsq(theta_n[:, active], target[rows], rcond=None)[0]
            self.evaluated += 1
        fitted = theta_n @ coef
        r2 = 1.0 - float(((target[rows] - fitted) ** 2).sum()
                         / max(1e-12, float(((target[rows] - target[rows].mean()) ** 2).sum())))
        terms = {k: round(float(c), 6) for k, c in zip(library, coef, strict=False) if c != 0.0}
        equation = " + ".join(f"{v:+.4f}*{k}" for k, v in terms.items()) or "0"
        diagnostics = {"equation": f"dx = {equation}", "terms": terms, "r2_train": round(r2, 6),
                       "library": list(library), "lambda": self.LAMBDA,
                       "sparsity": f"{len(terms)}/{len(library)}",
                       "method": "STLSQ on a standardised polynomial/sine/abs library; x is the "
                                 "realised residual, y the 24-bar return z, w the 24-bar range z"}
        if not terms:
            self.note("sparse_equation", f"every coefficient fell below lambda={self.LAMBDA}; no "
                                         "governing equation survives thresholding")
            return []
        mapping = {"y": ["z", "ret", 24], "w": ["z", "range", 24],
                   "y^2": ["mul", ["z", "ret", 24], ["z", "ret", 24]]}
        parts = [["neg", mapping[k]] if v < 0 else mapping[k]
                 for k, v in terms.items() if k in mapping]
        executable = parts[0] if parts else None
        for part in parts[1:]:
            executable = ["add", executable, part]
        out = [
            self.emit(panel, "law", ["z", state, 240] if executable is None else executable,
                      f"A SPARSE GOVERNING EQUATION: dx = {equation} (R^2 {r2:.4f} on the "
                      f"training slice, {len(terms)} of {len(library)} library terms survive); "
                      f"the executable form keeps the signs of the bar-expressible terms only",
                      diagnostics=diagnostics),
        ]
        dominant = max(terms, key=lambda k: abs(terms[k]))
        out.append(self.emit(panel, "relationship", mapping.get(dominant, ["z", state, 240]),
                             f"the dominant term of the equation is {dominant} "
                             f"({terms[dominant]:+.4f})",
                             side_mode="follow" if terms[dominant] >= 0 else "fade",
                             diagnostics=diagnostics))
        if time.monotonic() < deadline:
            tree, notes = self.projection(panel, 24, why=f"the equation's dominant term is "
                                                         f"{dominant}")
            out.append(self.emit(panel, "law", tree, "the governing equation, traded through "
                                                     "bar terminals", diagnostics=diagnostics,
                                 notes=notes))
        _ = rng
        return out


# ============================================================================ tail dependence
class TailDependence(Scientist):
    """Empirical-copula tail coefficients: do the extremes move together when the bodies do not?

    lambda_U(q) = P(V > q | U > q) and lambda_L(q) = P(V < 1-q | U < 1-q) on the ranks, against a
    block-permutation null. Independence gives 1 - q; a coefficient well above it in ONE tail is
    an asymmetry a correlation cannot see.
    """

    tradition = "tail_dependence"
    searches_for = ("mechanism", "law")

    Q = 0.90
    PERMUTATIONS = 80

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        train, _ = panel.split()
        target = panel.epsilon[train]
        results: list[dict[str, Any]] = []
        for name in self.top_columns(panel, 8):
            if time.monotonic() >= deadline:
                break
            values = panel.columns[name][train]
            mask = np.isfinite(values) & np.isfinite(target)
            if int(mask.sum()) < 300:
                continue
            upper, lower = self._tails(values[mask], target[mask])
            null = [max(self._tails(np.roll(values[mask], int(rng.integers(24, mask.sum() - 24))),
                                    target[mask]))
                    for _ in range(self.PERMUTATIONS)]
            p = float((np.sum(np.asarray(null) >= max(upper, lower)) + 1)
                      / (self.PERMUTATIONS + 1))
            self.charge(["z", name, 240])
            results.append({"column": name, "lambda_upper": round(upper, 5),
                            "lambda_lower": round(lower, 5), "asymmetry": round(upper - lower, 5),
                            "independence": round(1.0 - self.Q, 5), "p": round(p, 5)})
        if not results:
            self.note("tail_coefficients", "no column had 300 finite training rows")
            return []
        results.sort(key=lambda r: -max(r["lambda_upper"], r["lambda_lower"]))
        best = results[0]
        side = "upper" if best["lambda_upper"] >= best["lambda_lower"] else "lower"
        diagnostics = {"q": self.Q, "rows": results, "null": f"{self.PERMUTATIONS} block shifts",
                       "method": "empirical copula on ranks; tail coefficient at q; the null "
                                 "rolls the driver in blocks"}
        if best["p"] > 0.10:
            self.note("tail_dependence", f"the strongest tail coefficient ({best['column']}, "
                                         f"{side}) does not beat its block-permutation null")
        col = best["column"]
        gate = ["gt", ["z", col, 240], 1.28] if side == "upper" else ["lt", ["z", col, 240], -1.28]
        out = [
            self.emit(panel, "mechanism", ["mul", gate, ["z", "ret", 24]],
                      f"TAIL CO-MOVEMENT: when {col} is in its {side} tail the residual is too "
                      f"(lambda_{side[0].upper()} {best['lambda_' + side]:.3f} vs {1 - self.Q:.2f} "
                      f"under independence, p={best['p']:.3f}); the relation is claimed in the "
                      f"tail only", diagnostics=diagnostics),
            self.emit(panel, "law", ["z", col, 240],
                      f"TAIL ASYMMETRY {best['asymmetry']:+.3f}: upper and lower coefficients "
                      f"differ, which a correlation cannot express",
                      side_mode="follow" if best["asymmetry"] >= 0 else "fade",
                      diagnostics=diagnostics),
        ]
        tree, notes = self.projection(panel, 240, why=f"the tail-dependent column is {col}")
        out.append(self.emit(panel, "mechanism", tree, "tail co-movement, traded through bar "
                                                       "terminals", diagnostics=diagnostics,
                             notes=notes))
        return out

    def _tails(self, x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
        u = np.argsort(np.argsort(x)) / max(1, x.size - 1)
        v = np.argsort(np.argsort(y)) / max(1, y.size - 1)
        hi = u > self.Q
        lo = u < 1.0 - self.Q
        upper = float((v[hi] > self.Q).mean()) if hi.any() else 0.0
        lower = float((v[lo] < 1.0 - self.Q).mean()) if lo.any() else 0.0
        return upper, lower


# ============================================================================= matrix profile
class MatrixProfile(Scientist):
    """Motifs and discords: the subsequence that recurs most, and the one that never has.

    The matrix profile is each window's distance to its nearest non-trivial neighbour. Its
    minimum pair is a motif, its maximum a discord. The causal column `mp_novelty` is each
    window's distance to its nearest PAST neighbour -- how unprecedented the last day is.
    """

    tradition = "matrix_profile"
    searches_for = ("representation", "mechanism")

    M = 24
    LOOKBACK = 720
    STRIDE = 4

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        series = _z(_finite(panel.epsilon))
        n, m = panel.n, self.M
        starts = np.arange(0, n - m, max(1, (n - m) // CLOUD_CAP))
        windows = np.stack([series[s:s + m] for s in starts])
        with _quiet():
            windows = (windows - windows.mean(1, keepdims=True)) / np.maximum(
                windows.std(1, keepdims=True), 1e-9)
        dist = np.sqrt(np.maximum(((windows[:, None, :] - windows[None, :, :]) ** 2).sum(-1), 0))
        exclusion = np.abs(starts[:, None] - starts[None, :]) < m // 2
        dist[exclusion] = np.inf
        profile = dist.min(axis=1)
        finite = np.isfinite(profile)
        if not finite.any():
            self.note("matrix_profile", "every window fell inside another's exclusion zone")
            return []
        motif = int(np.argmin(np.where(finite, profile, np.inf)))
        discord = int(np.argmax(np.where(finite, profile, -np.inf)))
        novelty = np.full(n, np.nan)
        for t in range(m + m, n, self.STRIDE):
            if time.monotonic() >= deadline:
                self.note("novelty_scan", f"budget reached at bar {t} of {n}")
                break
            current = series[t - m:t]
            current = (current - current.mean()) / max(1e-9, current.std())
            lo = max(0, t - m - self.LOOKBACK)
            past = np.stack([series[s:s + m] for s in range(lo, t - m, 2)])
            past = (past - past.mean(1, keepdims=True)) / np.maximum(past.std(1, keepdims=True),
                                                                     1e-9)
            novelty[t] = float(np.sqrt(((past - current) ** 2).sum(1)).min())
        column = _mint(self, panel, "mp_novelty", _ffill(novelty), "mathlab:matrix_profile",
                       f"z-normalised distance of the last {m} bars to their nearest past twin")
        self.evaluated += int(starts.size)
        diagnostics = {"m": m, "windows": int(starts.size),
                       "motif_pair": [int(starts[motif]), int(starts[int(np.argmin(dist[motif]))])],
                       "motif_distance": round(float(profile[motif]), 6),
                       "discord_start": int(starts[discord]),
                       "discord_distance": round(float(profile[discord]), 6),
                       "method": "brute-force z-normalised Euclidean matrix profile on a capped "
                                 "subsample; novelty is measured against the past only"}
        out = [
            self.emit(panel, "representation", ["z", column, 240],
                      f"UNPRECEDENTEDNESS AS A COLUMN: the last {m} bars' distance to their "
                      f"nearest past twin; the global discord starts at bar "
                      f"{int(starts[discord])} (distance {profile[discord]:.3f}) and the motif "
                      f"recurs at distance {profile[motif]:.3f}", diagnostics=diagnostics),
            self.emit(panel, "mechanism", ["mul", ["sign", ["diff", "close", m]],
                                           ["z", column, 240]],
                      "a move that has no precedent in the last 720 bars is a different regime "
                      "from one that has one", diagnostics=diagnostics),
        ]
        tree, notes = self.projection(panel, self.LOOKBACK // 3, fast=m,
                                      why=f"the motif length is {m} bars")
        out.append(self.emit(panel, "mechanism", tree, "the motif scale, traded through bar "
                                                       "terminals", diagnostics=diagnostics,
                             notes=notes))
        _ = rng
        return out


# ============================================================================== change points
class ChangePoint(Scientist):
    """PELT on an L2 cost: where the residual's mean actually changed, exactly and pruned.

    The offline segmentation is reported as a diagnostic because it reads the whole sample; the
    CAUSAL column is a CUSUM alarm age whose threshold was set on the training slice, which is
    the only change-point object a bar at time t may read.
    """

    tradition = "change_point"
    searches_for = ("law", "representation")

    MIN_SEGMENT = 24
    CAP = 1500

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        series = _finite(panel.epsilon)
        stride = max(1, panel.n // self.CAP)
        sample = series[::stride]
        breaks = self._pelt(sample, deadline)
        if breaks is None:
            self.note("pelt", "budget reached before the segmentation finished")
            return []
        points = [int(b * stride) for b in breaks]
        segments = np.split(series, points) if points else [series]
        means = [round(float(s.mean()), 6) for s in segments if s.size]
        train, _ = panel.split()
        sigma = float(np.std(series[train])) or 1e-9
        threshold = 4.0 * sigma
        age = self._cusum_age(series, sigma, threshold)
        column = _mint(self, panel, "cusum_alarm_age", age, "mathlab:change_point",
                       "bars since the last two-sided CUSUM alarm (threshold set on train)")
        self.evaluated += max(1, len(points))
        lengths = [int(s.size) for s in segments if s.size]
        diagnostics = {"change_points": points[:40], "n_segments": len(segments),
                       "segment_means": means[:40], "median_segment_bars": int(np.median(lengths)),
                       "cusum_threshold": round(threshold, 6),
                       "method": "PELT with an L2 (mean-shift) cost and a BIC penalty in "
                                 f"long-run-variance units on a stride-{stride} sample; the "
                                 "causal column is a CUSUM age"}
        if len(points) == 0:
            self.note("change_points", "PELT found no change point under the BIC penalty")
        window = _nearest_window(max(2, int(np.median(lengths))))
        out = [
            self.emit(panel, "law", ["z", column, 240],
                      f"REGIME AGE: {len(points)} change points in the residual's mean, median "
                      f"segment {int(np.median(lengths))} bars; the CUSUM age says how long the "
                      f"current level has held", diagnostics=diagnostics),
            self.emit(panel, "representation", ["curv", column, 24],
                      "the acceleration of the alarm age: a fresh alarm is a break, an ageing "
                      "one a settled level", diagnostics=diagnostics),
        ]
        tree, notes = self.projection(panel, window, why=f"the median segment is "
                                                         f"{int(np.median(lengths))} bars")
        out.append(self.emit(panel, "law", tree, "segment length, traded through bar terminals",
                             diagnostics=diagnostics, notes=notes))
        _ = rng
        return out

    def _pelt(self, x: np.ndarray, deadline: float) -> list[int] | None:
        n = x.size
        cum, cum2 = np.concatenate([[0.0], np.cumsum(x)]), np.concatenate([[0.0], np.cumsum(x * x)])
        # THE PENALTY IS SCALED BY THE LONG-RUN VARIANCE, NOT THE MARGINAL ONE. A residual with
        # an AR(1) coefficient of 0.9 wanders for dozens of bars, and an L2 mean-shift cost
        # priced at the marginal variance reads every wander as a break (measured: eleven
        # breaks on a series with one). The Newey-West long-run variance is what the mean of an
        # autocorrelated segment actually varies by, and it is the right unit for the BIC term.
        penalty = 2.0 * math.log(max(2, n)) * self._long_run_variance(x)

        def cost(a: int, b: int) -> float:
            length = b - a
            total = cum[b] - cum[a]
            return float(cum2[b] - cum2[a] - total * total / length)

        best = np.full(n + 1, np.inf)
        best[0] = -penalty
        last = np.zeros(n + 1, dtype=int)
        candidates = np.asarray([0], dtype=int)
        for t in range(self.MIN_SEGMENT, n + 1):
            if (t & 63) == 0 and time.monotonic() >= deadline:
                return None
            length = t - candidates
            eligible = length >= self.MIN_SEGMENT
            if not eligible.any():
                candidates = np.append(candidates, t)
                continue
            total = cum[t] - cum[candidates]
            costs = cum2[t] - cum2[candidates] - total * total / np.maximum(length, 1)
            scores = np.where(eligible, best[candidates] + costs + penalty, np.inf)
            pick = int(np.argmin(scores))
            value = float(scores[pick])
            best[t], last[t] = value, int(candidates[pick])
            # PRUNE ONLY WHAT HAS BEEN ELIGIBLE. A candidate younger than the minimum segment
            # has never competed; judging it on a segment shorter than the rule allows would
            # discard the true change point in the twenty-three bars after it happens, which is
            # exactly where a mean shift looks like nothing yet.
            keep = (~eligible) | (best[candidates] + costs <= value)
            candidates = np.append(candidates[keep], t)
        _ = cost
        breaks: list[int] = []
        t = n
        while t > 0:
            s = int(last[t])
            if s == 0:
                break
            breaks.append(s)
            t = s
        return sorted(breaks)

    @staticmethod
    def _long_run_variance(x: np.ndarray) -> float:
        """Newey-West (Bartlett) long-run variance, never below the marginal variance."""
        centred = x - x.mean()
        n = centred.size
        gamma0 = float(centred @ centred) / max(1, n)
        bandwidth = int(4 * (n / 100.0) ** (2.0 / 9.0)) if n > 100 else 1
        total = gamma0
        for k in range(1, min(bandwidth, n - 1) + 1):
            gamma_k = float(centred[k:] @ centred[:-k]) / max(1, n)
            total += 2.0 * (1.0 - k / (bandwidth + 1.0)) * gamma_k
        return float(max(total, gamma0, 1e-9))

    @staticmethod
    def _cusum_age(x: np.ndarray, sigma: float, threshold: float) -> np.ndarray:
        up = down = 0.0
        age = 0
        out = np.zeros(x.size)
        drift = 0.5 * sigma
        for i, v in enumerate(x):
            up = max(0.0, up + v - drift)
            down = max(0.0, down - v - drift)
            age += 1
            if up > threshold or down > threshold:
                up = down = 0.0
                age = 0
            out[i] = age
        return out


# ============================================================================ survival hazard
class SurvivalHazard(Scientist):
    """Kaplan-Meier on regime durations: how old is this regime, and how likely is it to die now?

    Runs of the regime label are lifetimes; the last run is right-censored. The survival curve
    is estimated on the training runs, and the causal column is the hazard AT THE CURRENT AGE of
    the current regime -- a number a bar at time t can know.
    """

    tradition = "survival_hazard"
    searches_for = ("representation", "mechanism")

    MIN_RUNS = 5

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        if panel.regime is None:
            self.note("regime_labels", "the panel carries no regime labels; the world model's "
                                       "regime column would measure it")
            return []
        labels = np.asarray(panel.regime).astype(str)
        runs: list[tuple[str, int, int, bool]] = []
        start = 0
        for i in range(1, panel.n + 1):
            if i == panel.n or labels[i] != labels[start]:
                runs.append((labels[start], start, i - start, i == panel.n))
                start = i
        train_cut = int(panel.n * 0.6)
        complete = [r for r in runs if r[1] + r[2] <= train_cut and not r[3]]
        if len(complete) < self.MIN_RUNS:
            self.note("regime_runs", f"{len(complete)} complete regime runs on the training "
                                     f"slice, fewer than {self.MIN_RUNS}")
            return []
        curves = {label: self._kaplan_meier([r[2] for r in complete if r[0] == label])
                  for label in sorted({r[0] for r in complete})}
        age = np.zeros(panel.n)
        hazard = np.full(panel.n, np.nan)
        for label, s, length, _censored in runs:
            for k in range(length):
                age[s + k] = k + 1
                hazard[s + k] = self._hazard_at(curves.get(label), k + 1)
        _mint(self, panel, "regime_age", age, "mathlab:survival", "bars since the regime began")
        column = _mint(self, panel, "hazard_now", hazard, "mathlab:survival",
                       "Kaplan-Meier hazard of the current regime at its current age")
        self.evaluated += len(curves)
        medians = {k: v["median"] for k, v in curves.items()}
        diagnostics = {"runs_total": len(runs), "runs_complete_train": len(complete),
                       "median_survival_bars": medians,
                       "survival": {k: v["curve"][:12] for k, v in curves.items()},
                       "method": "Kaplan-Meier on regime run lengths (last run censored), "
                                 "fitted on training runs; hazard read at the current age"}
        median_all = float(np.median([m for m in medians.values() if m])) if any(
            medians.values()) else 24.0
        out = [
            self.emit(panel, "representation", ["z", column, 240],
                      f"REGIME MORTALITY: the hazard of the current regime at its current age, "
                      f"median survival {medians}", diagnostics=diagnostics),
            self.emit(panel, "mechanism",
                      ["mul", ["neg", ["sign", ["diff", "close", 24]]], ["z", column, 240]],
                      "an old regime with a rising hazard is faded, a young one is not",
                      diagnostics=diagnostics),
        ]
        if time.monotonic() < deadline:
            tree, notes = self.projection(panel, max(2.0, median_all),
                                          why=f"median regime survival is {median_all:.0f} bars")
            out.append(self.emit(panel, "mechanism", tree, "regime survival, traded through bar "
                                                           "terminals", diagnostics=diagnostics,
                                 notes=notes))
        _ = rng
        return out

    @staticmethod
    def _kaplan_meier(durations: list[int]) -> dict[str, Any]:
        times = sorted(set(durations))
        alive = len(durations)
        survival = 1.0
        curve: list[tuple[int, float, float]] = []
        for t in times:
            died = durations.count(t)
            h = died / alive if alive else 0.0
            survival *= 1.0 - h
            curve.append((t, round(survival, 6), round(h, 6)))
            alive -= died
        median = next((t for t, s, _ in curve if s <= 0.5), None)
        return {"curve": curve, "median": median}

    @staticmethod
    def _hazard_at(curve: dict[str, Any] | None, age: int) -> float:
        if not curve:
            return np.nan
        rows = [h for t, _, h in curve["curve"] if t <= age]
        return float(rows[-1]) if rows else 0.0


# ========================================================================= transfer entropy
class TransferEntropyScan(Scientist):
    """Lagged, binned transfer entropy from every top column, against a block-permutation null.

    The first cohort's information theorist asks whether a column carries information. This one
    asks WHEN: which lag of which driver reduces the residual's uncertainty beyond its own past,
    scanning a ladder of lags so the answer is a delay and not merely a name.
    """

    tradition = "transfer_entropy"
    searches_for = ("law", "relationship")

    LAGS = (1, 2, 3, 5, 8, 12, 24)
    PERMUTATIONS = 60

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        train, _ = panel.split()
        target = _finite(panel.epsilon[train])
        table: list[dict[str, Any]] = []
        for name in self.top_columns(panel, 6):
            driver = _finite(panel.columns[name][train])
            for lag in self.LAGS:
                if time.monotonic() >= deadline:
                    break
                value = _transfer_entropy(driver, target, lag)
                self.charge(["lag", name, _nearest_window(lag)])
                if value is not None:
                    table.append({"column": name, "lag": lag, "te_nats": round(value, 6)})
        if not table:
            self.note("transfer_entropy", "no (column, lag) pair had 200 aligned rows")
            return []
        table.sort(key=lambda r: -r["te_nats"])
        best = table[0]
        driver = _finite(panel.columns[best["column"]][train])
        null = []
        for _ in range(self.PERMUTATIONS):
            rolled = np.roll(driver, int(rng.integers(24, max(25, driver.size - 24))))
            value = _transfer_entropy(rolled, target, best["lag"])
            if value is not None:
                null.append(value)
        p = float((np.sum(np.asarray(null) >= best["te_nats"]) + 1) / (len(null) + 1)) if null \
            else None
        diagnostics = {"table": table[:14], "best": best, "permutation_p": p,
                       "null": f"{self.PERMUTATIONS} block shifts of the driver",
                       "method": "binned TE(X_{t-lag} -> Y_t | Y_{t-1}) over a lag ladder"}
        if p is None or p > 0.10:
            self.note("transfer_entropy_null", f"the best pair {best} does not beat its "
                                               "block-permutation null")
        direction = _corr(np.roll(driver, best["lag"])[best["lag"]:], target[best["lag"]:])
        out = [
            self.emit(panel, "law" if (p is not None and p <= 0.05) else "relationship",
                      ["lag", best["column"], _nearest_window(best["lag"])],
                      f"INFORMATION ARRIVES WITH A DELAY: {best['column']} at lag {best['lag']} "
                      f"carries {best['te_nats']:.5f} nats about the residual beyond its own past "
                      f"(p={p})", side_mode="follow" if direction >= 0 else "fade",
                      diagnostics=diagnostics),
        ]
        tree, notes = self.projection(panel, 120, fast=best["lag"],
                                      why=f"the information-bearing lag is {best['lag']}")
        out.append(self.emit(panel, "relationship", tree, "the information lag, traded through "
                                                          "bar terminals",
                             diagnostics=diagnostics, notes=notes))
        return out


# ========================================================================= wavelet scattering
class WaveletScattering(Scientist):
    """A Haar scattering cascade: |x * psi_j| averaged, then |(|x * psi_j|) * psi_k| averaged.

    Every coefficient path is written IN THE GRAMMAR -- a Haar detail at scale a is
    rmean(x, a) - lag(rmean(x, a), a), the modulus is abs, the averaging is rmean -- so the
    invention is executable exactly as measured, with no projection needed.
    """

    tradition = "wavelet_scattering"
    searches_for = ("representation", "relationship")

    SCALES = (2, 8, 24)
    AVERAGE = 120

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        base = "ret" if "ret" in panel.columns else "close"
        train, _ = panel.split()
        paths: dict[str, Any] = {}
        for a in self.SCALES:
            first = ["abs", ["sub", ["rmean", base, a], ["lag", ["rmean", base, a], a]]]
            paths[f"S1[{a}]"] = ["rmean", first, self.AVERAGE]
            for b in self.SCALES:
                if b > a:
                    second = ["abs", ["sub", ["rmean", first, b], ["lag", ["rmean", first, b], b]]]
                    paths[f"S2[{a},{b}]"] = ["rmean", second, self.AVERAGE]
        scores: dict[str, float] = {}
        moments: dict[str, dict[str, float]] = {}
        for name, tree in paths.items():
            if time.monotonic() >= deadline:
                break
            values = G.evaluate(tree, panel.columns, panel.n)
            self.charge(tree)
            scores[name] = _corr(values[train], panel.epsilon[train])
            finite = values[np.isfinite(values)]
            moments[name] = {"mean": round(float(finite.mean()), 8) if finite.size else None,
                             "std": round(float(finite.std()), 8) if finite.size else None}
        if not scores:
            self.note("scattering", "budget reached before any path was evaluated")
            return []
        best = max(scores, key=lambda k: abs(scores[k]))
        first_order = [k for k in scores if k.startswith("S1")]
        second_order = [k for k in scores if k.startswith("S2")]
        diagnostics = {"scales": self.SCALES, "average": self.AVERAGE,
                       "path_ic": {k: round(v, 5) for k, v in scores.items()},
                       "moments": moments, "best_path": best,
                       "method": "Haar scattering to order two, each path an expression in the "
                                 "grammar"}
        out = [
            self.emit(panel, "representation", paths[best],
                      f"A SCATTERING COEFFICIENT: path {best} of the Haar cascade over {base} "
                      f"(IC {scores[best]:+.4f} on the training slice)",
                      side_mode="follow" if scores[best] >= 0 else "fade",
                      diagnostics=diagnostics),
        ]
        # A FIRST-ORDER PATH IS ALWAYS OFFERED: it sits inside alpha_grammar's depth bound and is
        # therefore executable as written, where a second-order path (depth 8) is a recorded
        # discovery the family cannot yet be handed.
        best_first = max(first_order, key=lambda k: abs(scores[k])) if first_order else None
        if best_first is not None and best_first != best:
            out.append(self.emit(panel, "representation", paths[best_first],
                                 f"the best FIRST-ORDER path {best_first} (IC "
                                 f"{scores[best_first]:+.4f}), executable as written",
                                 side_mode="follow" if scores[best_first] >= 0 else "fade",
                                 diagnostics=diagnostics))
        if first_order and second_order:
            a, b = first_order[0], second_order[0]
            out.append(self.emit(panel, "relationship", ["div", paths[b], paths[a]],
                                 f"the second-order to first-order energy ratio {b}/{a}: how "
                                 f"much of the modulus at scale {self.SCALES[0]} is itself "
                                 f"modulated", diagnostics=diagnostics))
        _ = rng
        return out


# ======================================================================= tensor decomposition
class TensorDecomposition(Scientist):
    """CP decomposition (rank 2, ALS) of the asset x feature x time tensor of the peer set.

    A rank-one component is ONE market mode: a loading over assets, a loading over features, and
    a weight over time. The time weights of the first component, refitted causally onto the
    fixed asset and feature loadings, are the market-mode state variable.
    """

    tradition = "tensor_decomposition"
    searches_for = ("representation", "law")

    RANK = 2
    ITERATIONS = 20

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        assets = {k: _finite(v) for k, v in panel.peers.items() if np.asarray(v).size == panel.n}
        if len(assets) < 3:
            self.note("tensor_assets", f"{len(assets)} aligned peer series; a tensor needs three")
            return []
        names = sorted(assets)
        block = np.stack([assets[k] for k in names])                              # a x t
        with _quiet():
            block = (block - block.mean(1, keepdims=True)) / np.maximum(block.std(1, keepdims=True),
                                                                        1e-12)
        # assets x features x time
        features = np.stack([block, np.abs(block), np.sign(block) * block ** 2], axis=1)
        train, _ = panel.split()
        tensor = features[:, :, train]
        a_load = rng.normal(size=(len(names), self.RANK))
        f_load = rng.normal(size=(3, self.RANK))
        t_load = rng.normal(size=(train.size, self.RANK))
        unfold = {0: tensor.reshape(len(names), -1),
                  1: np.transpose(tensor, (1, 0, 2)).reshape(3, -1),
                  2: np.transpose(tensor, (2, 0, 1)).reshape(train.size, -1)}
        for _ in range(self.ITERATIONS):
            if time.monotonic() >= deadline:
                self.note("cp_als", "budget reached before ALS converged")
                break
            a_load = self._als_step(unfold[0], f_load, t_load)
            f_load = self._als_step(unfold[1], a_load, t_load)
            t_load = self._als_step(unfold[2], a_load, f_load)
            self.evaluated += 1
        design = self._khatri_rao(a_load, f_load)                                  # (a*f) x R
        weights = np.linalg.lstsq(design, features.reshape(len(names) * 3, panel.n), rcond=None)[0]
        column = _mint(self, panel, "cp_mode1", weights[0], "mathlab:tensor",
                       "time weight of the first CP component on fixed asset/feature loadings")
        fitted = design @ t_load.T
        r2 = 1.0 - float(((unfold[2].T - fitted) ** 2).sum()
                         / max(1e-12, float((unfold[2] ** 2).sum())))
        diagnostics = {"assets": names, "features": ["r", "|r|", "sign(r) r^2"], "rank": self.RANK,
                       "asset_loadings": {n: [round(float(v), 5) for v in a_load[i]]
                                          for i, n in enumerate(names)},
                       "feature_loadings": [[round(float(v), 5) for v in row] for row in f_load],
                       "fit_r2_train": round(r2, 6),
                       "method": "CP-ALS on the training slice; time weights refitted causally"}
        out = [
            self.emit(panel, "representation", ["z", column, 240],
                      f"A MARKET MODE: the first CP component's time weight over {len(names)} "
                      f"assets x 3 features (train R^2 {r2:.3f})", diagnostics=diagnostics),
            self.emit(panel, "law", ["curv", column, 24],
                      "the mode's acceleration: a market mode that is speeding up is a different "
                      "state from one that merely exists", diagnostics=diagnostics),
        ]
        tree, notes = self.projection(panel, 120, why="the CP mode's loadings fix the assets")
        out.append(self.emit(panel, "law", tree, "the market mode, traded through bar terminals",
                             diagnostics=diagnostics, notes=notes))
        return out

    @staticmethod
    def _khatri_rao(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        return np.einsum("ir,jr->ijr", a, b).reshape(-1, a.shape[1])

    def _als_step(self, unfolded: np.ndarray, left: np.ndarray, right: np.ndarray) -> np.ndarray:
        kr = self._khatri_rao(left, right)
        gram = (left.T @ left) * (right.T @ right) + 1e-6 * np.eye(self.RANK)
        return np.linalg.solve(gram, (unfolded @ kr).T).T


# ========================================================================= reservoir computing
class ReservoirComputing(Scientist):
    """An echo-state network: a fixed random dynamical system whose state is read out by ridge.

    The reservoir is never trained; only the linear readout is, on the training slice. What it
    offers is a NONLINEAR MEMORY of the inputs that no hand-written feature encodes, and the
    readout's held-out IC is the only claim it makes.
    """

    tradition = "reservoir_computing"
    searches_for = ("representation", "relationship")

    UNITS = 120
    LEAK = 0.3
    RADIUS = 0.9
    RIDGE = 1e-2
    WASHOUT = 100

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        inputs = self.top_columns(panel, 3)
        u = np.column_stack([np.nan_to_num(_z(_finite(panel.columns[c]))) for c in inputs])
        n, k = u.shape
        w_in = rng.uniform(-0.5, 0.5, size=(self.UNITS, k))
        w = rng.normal(size=(self.UNITS, self.UNITS)) * (rng.random((self.UNITS, self.UNITS)) < 0.1)
        radius = float(np.max(np.abs(np.linalg.eigvals(w))))
        w *= self.RADIUS / max(radius, 1e-9)
        states = np.zeros((n, self.UNITS))
        x = np.zeros(self.UNITS)
        for t in range(n):
            x = (1 - self.LEAK) * x + self.LEAK * np.tanh(w @ x + w_in @ u[t])
            states[t] = x
            if t % 500 == 0 and time.monotonic() >= deadline:
                self.note("reservoir_run", f"budget reached at bar {t} of {n}")
                return []
        train, test = panel.split()
        fit = train[train >= self.WASHOUT]
        design = np.column_stack([np.ones(fit.size), states[fit]])
        gram = design.T @ design + self.RIDGE * np.eye(design.shape[1])
        beta = np.linalg.solve(gram, design.T @ np.nan_to_num(panel.epsilon[fit]))
        readout = np.column_stack([np.ones(n), states]) @ beta
        readout[:self.WASHOUT] = np.nan
        column = _mint(self, panel, "esn_readout", readout, "mathlab:reservoir",
                       f"ridge readout of a {self.UNITS}-unit echo-state network over {inputs}")
        self.evaluated += 1
        ic_train = _corr(readout[fit], panel.epsilon[fit])
        ic_test = _corr(readout[test], panel.epsilon[test]) if test.size else 0.0
        diagnostics = {"inputs": inputs, "units": self.UNITS, "leak": self.LEAK,
                       "spectral_radius": self.RADIUS, "ridge": self.RIDGE,
                       "ic_train": round(ic_train, 5), "ic_test": round(ic_test, 5),
                       "method": "leaky echo-state reservoir, fixed; ridge readout fitted on the "
                                 "training slice after a washout"}
        out = [
            self.emit(panel, "representation", ["z", column, 240],
                      f"A RESERVOIR MEMORY: the readout of a fixed random dynamical system driven "
                      f"by {inputs} (train IC {ic_train:+.4f}, test IC {ic_test:+.4f})",
                      diagnostics=diagnostics),
            self.emit(panel, "relationship", ["diff", column, 2],
                      "the readout's own change: where the reservoir's memory is turning",
                      diagnostics=diagnostics),
        ]
        tree, notes = self.projection(panel, 120, why=f"the reservoir reads {inputs}")
        out.append(self.emit(panel, "relationship", tree, "the reservoir state, traded through "
                                                          "bar terminals",
                             diagnostics=diagnostics, notes=notes))
        return out


# =================================================================== recurrence quantification
class RecurrenceQuantification(Scientist):
    """Rolling RQA: recurrence rate, determinism, laminarity and diagonal-line entropy per window.

    The first cohort's dynamicist measures the whole sample once. This is the ROLLING search: in
    the last 120 bars, how deterministic was the residual, and how much of that determinism was
    laminar (stuck) rather than moving? Both become columns.
    """

    tradition = "recurrence_quantification"
    searches_for = ("representation", "law")

    WINDOW = 120
    STRIDE = 12
    DIM = 3
    TAU = 2

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        series = _finite(panel.epsilon)
        n = panel.n
        det = np.full(n, np.nan)
        lam = np.full(n, np.nan)
        entropy = np.full(n, np.nan)
        rate = np.full(n, np.nan)
        windows = 0
        for t in range(self.WINDOW, n, self.STRIDE):
            if time.monotonic() >= deadline:
                self.note("rqa_scan", f"budget reached at bar {t} of {n}")
                break
            span = (self.DIM - 1) * self.TAU
            block = series[t - self.WINDOW:t]
            cloud = np.column_stack([block[i * self.TAU: i * self.TAU + block.size - span]
                                     for i in range(self.DIM)])
            dist = np.sqrt(((cloud[:, None, :] - cloud[None, :, :]) ** 2).sum(-1))
            positive = dist[dist > 0]
            if positive.size == 0:
                continue
            eps = float(np.percentile(positive, 10))
            rec = (dist <= eps) & (dist > 0)
            rate[t] = float(rec.mean())
            det[t], entropy[t] = self._diagonal(rec)
            lam[t] = self._vertical(rec)
            windows += 1
        if windows == 0:
            self.note("rqa", "no window produced a recurrence matrix")
            return []
        col_det = _mint(self, panel, "rqa_det", _ffill(det), "mathlab:rqa",
                        "determinism of the last 120 bars' recurrence plot")
        col_lam = _mint(self, panel, "rqa_lam", _ffill(lam), "mathlab:rqa",
                        "laminarity of the last 120 bars' recurrence plot")
        self.evaluated += windows
        diagnostics = {"window": self.WINDOW, "stride": self.STRIDE, "dim": self.DIM,
                       "tau": self.TAU, "windows": windows,
                       "mean_recurrence_rate": round(float(np.nanmean(rate)), 6),
                       "mean_determinism": round(float(np.nanmean(det)), 6),
                       "mean_laminarity": round(float(np.nanmean(lam)), 6),
                       "mean_diagonal_entropy": round(float(np.nanmean(entropy)), 6),
                       "method": "rolling recurrence matrices at the 10th-percentile radius; DET "
                                 "and ENTR from diagonal lines >= 2, LAM from vertical lines >= 2"}
        out = [
            self.emit(panel, "representation", ["z", col_det, 240],
                      f"ROLLING DETERMINISM: mean DET {float(np.nanmean(det)):.3f}, mean LAM "
                      f"{float(np.nanmean(lam)):.3f} over {windows} windows",
                      diagnostics=diagnostics),
            self.emit(panel, "law", ["sub", ["z", col_det, 240], ["z", col_lam, 240]],
                      "determinism that is NOT laminarity: structure that moves rather than "
                      "sticks", diagnostics=diagnostics),
        ]
        tree, notes = self.projection(panel, self.WINDOW, why="the RQA window is 120 bars")
        out.append(self.emit(panel, "law", tree, "rolling recurrence, traded through bar "
                                                 "terminals", diagnostics=diagnostics,
                             notes=notes))
        _ = rng
        return out

    @staticmethod
    def _diagonal(rec: np.ndarray, min_line: int = 2) -> tuple[float, float]:
        total = int(rec.sum())
        if total == 0:
            return 0.0, 0.0
        lengths: list[int] = []
        n = rec.shape[0]
        for offset in range(1, n):
            run = 0
            for value in np.diagonal(rec, offset):
                if value:
                    run += 1
                elif run:
                    lengths.append(run)
                    run = 0
            if run:
                lengths.append(run)
        long = [x for x in lengths if x >= min_line]
        det = float(2 * sum(long) / total)
        if not long:
            return det, 0.0
        counts = np.bincount(long)[min_line:]
        p = counts / counts.sum()
        p = p[p > 0]
        return det, float(-(p * np.log(p)).sum())

    @staticmethod
    def _vertical(rec: np.ndarray, min_line: int = 2) -> float:
        total = int(rec.sum())
        if total == 0:
            return 0.0
        on_line = 0
        for column in rec.T:
            run = 0
            for value in column:
                run = run + 1 if value else 0
                if run >= min_line:
                    on_line += 1
        return float(on_line / total)


# ============================================================================= extreme value
class ExtremeValue(Scientist):
    """Peaks over threshold with a generalised Pareto fit: how heavy is the tail, really?

    The shape parameter xi is the discovery: xi > 0 is a heavy tail with a finite number of
    moments, xi ~ 0 exponential, xi < 0 bounded. The extremal index from runs declustering says
    whether exceedances arrive alone or in clusters, which is what a stop needs to know.
    """

    tradition = "extreme_value"
    searches_for = ("mechanism", "law")

    Q = 0.95
    RUN = 4

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        base = "ret" if "ret" in panel.columns else None
        magnitude = np.abs(_finite(panel.columns[base])) if base else np.abs(_finite(panel.epsilon))
        train, _ = panel.split()
        threshold = float(np.quantile(magnitude[train], self.Q))
        exceed = magnitude > threshold
        excess = magnitude[train][exceed[train]] - threshold
        if excess.size < 30:
            self.note("gpd_fit", f"{excess.size} exceedances on the training slice, fewer than 30")
            return []
        try:
            from scipy.stats import genpareto
            xi, _loc, sigma = genpareto.fit(excess, floc=0.0)
        except Exception as exc:
            self.note("gpd_fit", f"scipy.stats.genpareto unavailable ({type(exc).__name__})")
            return []
        self.evaluated += 1
        hits = np.flatnonzero(exceed[train])
        clusters = 1 + int((np.diff(hits) > self.RUN).sum()) if hits.size else 0
        theta = clusters / max(1, hits.size)
        rate = 1.0 - self.Q
        with _quiet():
            level_1000 = threshold + (sigma / xi) * ((1000 * rate) ** xi - 1.0) if abs(xi) > 1e-9 \
                else threshold + sigma * math.log(1000 * rate)
        rate_column = G.evaluate(["rmean", "__x__", 240], {"__x__": exceed.astype(float)}, panel.n)
        column = _mint(self, panel, "evt_exceedance_rate", rate_column, "mathlab:evt",
                       f"fraction of the last 240 bars beyond the {self.Q:.0%} threshold")
        diagnostics = {"series": base or "epsilon", "q": self.Q, "threshold": round(threshold, 8),
                       "n_exceedances_train": int(excess.size), "xi": round(float(xi), 5),
                       "sigma": round(float(sigma), 8), "heavy_tail": bool(xi > 0),
                       "extremal_index": round(theta, 4), "clusters": clusters,
                       "return_level_1000_bars": round(float(level_1000), 8),
                       "method": "POT with a GPD fitted by MLE (floc=0); runs declustering with "
                                 f"run length {self.RUN}"}
        out = [
            self.emit(panel, "mechanism", ["mul", ["sign", ["diff", "close", 2]],
                                           ["z", column, 240]],
                      f"TAIL STATE: xi={float(xi):+.3f} ({'heavy' if xi > 0 else 'light'} tail), "
                      f"extremal index {theta:.2f} (exceedances arrive in clusters of "
                      f"{1 / max(theta, 1e-9):.1f}); the current exceedance rate gates the sign",
                      diagnostics=diagnostics),
            self.emit(panel, "law", ["z", column, 240],
                      f"the 1000-bar return level is {float(level_1000):.5g}; a rate above its "
                      f"own normal means the tail is being visited", diagnostics=diagnostics),
        ]
        if time.monotonic() < deadline:
            tree, notes = self.projection(panel, 240, fast=self.RUN,
                                          why=f"the declustering run length is {self.RUN} bars")
            out.append(self.emit(panel, "mechanism", tree, "the tail state, traded through bar "
                                                           "terminals", diagnostics=diagnostics,
                                 notes=notes))
        _ = rng
        return out


# ================================================================ sequential pattern mining
class SequentialPatternMining(Scientist):
    """Frequent event sequences, each tested for the residual that follows it, under BH FDR.

    Bars become symbols (U/D/F for the 24-bar state, J for a jump); contiguous sequences of two
    and three symbols are counted; every frequent one is a hypothesis about the residual after
    it, and Benjamini-Hochberg across the whole enumeration decides which survive. The
    executable form of a survivor is the product of the signs its symbols name.
    """

    tradition = "sequential_pattern_mining"
    searches_for = ("relationship", "mechanism")

    MIN_SUPPORT = 40
    Q = 0.10

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        if "ret" not in panel.columns:
            self.note("events", "the panel carries no ret column to symbolise")
            return []
        state = G.evaluate(["z", "ret", 24], panel.columns, panel.n)
        jump = G.evaluate(["div", ["abs", "ret"], ["rstd", "ret", 48]], panel.columns, panel.n)
        symbols = np.where(state > 0.5, "U", np.where(state < -0.5, "D", "F"))
        symbols = np.where(jump > 3.0, "J", symbols).astype(str)
        train, _ = panel.split()
        target = panel.epsilon
        tested: list[dict[str, Any]] = []
        for length in (2, 3):
            counts: dict[tuple[str, ...], list[int]] = {}
            for t in train:
                if t < length:
                    continue
                seq = tuple(symbols[t - length + 1:t + 1])
                if any(s not in ("U", "D", "J") for s in seq):
                    continue
                counts.setdefault(seq, []).append(int(t))
            for seq, where in counts.items():
                if time.monotonic() >= deadline:
                    break
                self.evaluated += 1
                if len(where) < self.MIN_SUPPORT:
                    continue
                after = target[np.asarray(where)]
                after = after[np.isfinite(after)]
                if after.size < self.MIN_SUPPORT:
                    continue
                sd = float(after.std()) or 1e-12
                t_stat = float(after.mean() / (sd / math.sqrt(after.size)))
                tested.append({"sequence": list(seq), "support": int(after.size),
                               "mean_epsilon": round(float(after.mean()), 8),
                               "t": round(t_stat, 4),
                               "p": round(math.erfc(abs(t_stat) / math.sqrt(2.0)), 8)})
        self.distinct |= {"".join(r["sequence"]) for r in tested}
        if not tested:
            self.note("sequences", f"no sequence reached support {self.MIN_SUPPORT}")
            return []
        ordered = sorted(tested, key=lambda r: r["p"])
        cut = 0
        for rank, row in enumerate(ordered, start=1):
            if row["p"] <= self.Q * rank / len(ordered):
                cut = rank
        survivors = ordered[:cut]
        diagnostics = {"enumerated": len(tested), "survivors_after_fdr": len(survivors),
                       "q": self.Q, "top": ordered[:6],
                       "alphabet": "U/D = 24-bar z above/below 0.5, J = |ret| > 3 sd(48), "
                                   "F = flat",
                       "method": "contiguous sequences of length 2-3 on the training slice; BH "
                                 "FDR across the whole enumeration"}
        if not survivors:
            self.note("fdr", f"{len(tested)} frequent sequences and none survived BH at "
                             f"q={self.Q}")
            return []
        out: list[MathObject | None] = []
        for row in survivors[:2]:
            factors = []
            for i, symbol in enumerate(reversed(row["sequence"])):
                lagged = ["sign", ["diff", "close", 24]] if i == 0 else \
                    ["sign", ["lag", ["diff", "close", 24], _nearest_window(i)]]
                factors.append(lagged if symbol in ("U", "J") else ["neg", lagged])
            tree = factors[0]
            for factor in factors[1:]:
                tree = ["mul", tree, factor]
            out.append(self.emit(
                panel, "relationship", tree,
                f"SEQUENCE {''.join(row['sequence'])}: the residual after it averages "
                f"{row['mean_epsilon']:+.6f} on {row['support']} occurrences (t={row['t']:+.2f}, "
                f"p={row['p']:.5f}), surviving BH at q={self.Q} over {len(tested)} sequences",
                side_mode="follow" if row["mean_epsilon"] >= 0 else "fade",
                diagnostics={**diagnostics, "sequence": row}))
        _ = rng
        return out


EXTRA_REGISTRY: dict[str, type[Scientist]] = {
    "rough_path_signatures": RoughPathSignatures,
    "koopman_dmd": KoopmanDMD,
    "sindy": SINDy,
    "tail_dependence": TailDependence,
    "matrix_profile": MatrixProfile,
    "change_point": ChangePoint,
    "survival_hazard": SurvivalHazard,
    "transfer_entropy": TransferEntropyScan,
    "wavelet_scattering": WaveletScattering,
    "tensor_decomposition": TensorDecomposition,
    "reservoir_computing": ReservoirComputing,
    "recurrence_quantification": RecurrenceQuantification,
    "extreme_value": ExtremeValue,
    "sequential_pattern_mining": SequentialPatternMining,
}
EXTRA_TRADITIONS: tuple[str, ...] = tuple(EXTRA_REGISTRY)
_ = UNMEASURED
