"""THE ENGINES: the machinery the scientists share, each a bounded numpy procedure that turns a
panel (or a set of objects) into a finding with its own trial count and its own UNMEASURED list.

A SCIENTIST HAS A QUESTION; AN ENGINE HAS A METHOD. Law discovery (sparse regression over a
library, SINDy-style, with pysindy behind a guard), ODE/PDE discovery, rejection ABC,
MDL scoring, probabilistic model competition (evidence / BIC / time-ordered CV),
latent-to-symbolic, counterfactual simulation, experimental discrimination (which slice of the
data makes the competing models disagree most), synthetic calibration and the ADVERSARIAL
SYNTHETIC WORLD (a fake law planted so that it holds in-sample only, which the judge must
reject), independent civilizations (disjoint seeds, compared only by the judge), method
tournaments, distributed science (a budget split by department), formal maths behind a sympy
guard, differentiable science behind a JAX guard with a numpy fallback, and primitive invention
from recurring subexpressions.

EVERY ENGINE RETURNS AN `EngineResult` AND NEVER RAISES through `run_engine`: a failing engine
costs its own slice of the budget and is reported FAILED with the exception named. Optional
libraries are imported through `libs.research.adapters.library`, which returns None rather
than raising, and an engine that needs one it cannot get records UNMEASURED by name.
"""
from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from . import burden as B
from . import grammar as G
from .base import Scientist, _corr, _finite, _quiet, _z
from .objects import MathObject, Panel, Variable
from .physics import _acf, _kurtosis, _realised

UNMEASURED = "UNMEASURED"


def _library(name: str) -> Any | None:
    try:
        from libs.research.adapters import library
        return library(name)
    except Exception:
        return None


@dataclass
class EngineResult:
    """What one engine produced, with what it could not measure and what it cost."""

    engine: str
    status: str = "OK"
    trials: int = 0
    findings: list[dict[str, Any]] = field(default_factory=list)
    unmeasured: list[str] = field(default_factory=list)
    compute_s: float = 0.0
    counts: dict[str, int] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)

    def note(self, what: str, why: str) -> None:
        self.unmeasured.append(f"{what}: {why}")

    def to_row(self) -> dict[str, Any]:
        return {"engine": self.engine, "status": self.status, "trials": self.trials,
                "findings": self.findings, "unmeasured": self.unmeasured,
                "compute_s": round(self.compute_s, 3), "counts": self.counts,
                "summary": self.summary}


# --------------------------------------------------------------------------- shared numerics
def _ols(design: np.ndarray, y: np.ndarray, ridge: float = 1e-6) -> np.ndarray:
    gram = design.T @ design + ridge * np.eye(design.shape[1])
    return np.asarray(np.linalg.solve(gram, design.T @ y), dtype=float)


def _r2(y: np.ndarray, yhat: np.ndarray) -> float:
    ss = float(((y - y.mean()) ** 2).sum())
    return 1.0 - float(((y - yhat) ** 2).sum()) / ss if ss > 1e-15 else 0.0


def _stlsq(theta: np.ndarray, target: np.ndarray, lam: float, iterations: int = 10
           ) -> np.ndarray:
    coef = np.linalg.lstsq(theta, target, rcond=None)[0]
    for _ in range(iterations):
        small = np.abs(coef) < lam
        coef[small] = 0.0
        active = ~small
        if not active.any():
            break
        coef[active] = np.linalg.lstsq(theta[:, active], target, rcond=None)[0]
    return np.asarray(coef, dtype=float)


def feature_library(panel: Panel, state: str) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """The standardised library every law engine reads: x (realised residual), y (return z),
    w (range z), u (activity z) and their degree-two products. Names map to grammar trees."""
    x = _z(np.nan_to_num(_finite(panel.columns[state])))
    trees: dict[str, Any] = {"x": ["z", state, 240], "y": ["z", "ret", 24],
                             "w": ["z", "range", 24], "u": ["z", "activity", 24]}
    with _quiet():
        cols = {"x": x}
        for name in ("y", "w", "u"):
            var = trees[name][1]
            if var in panel.columns:
                cols[name] = np.nan_to_num(G.evaluate(trees[name], panel.columns, panel.n))
    lib: dict[str, np.ndarray] = {"1": np.ones(panel.n)}
    lib.update(cols)
    names = list(cols)
    for i, a in enumerate(names):
        for b_ in names[i:]:
            lib[f"{a}*{b_}"] = cols[a] * cols[b_]
    lib["|x|"] = np.abs(x)
    lib["sin(x)"] = np.sin(x)
    return lib, trees


def library_tree(term: str, trees: dict[str, Any]) -> Any | None:
    """The grammar tree of a library term, or None when the grammar cannot say it."""
    if term in trees:
        return trees[term]
    if term == "|x|":
        return ["abs", trees["x"]]
    if "*" in term:
        a, b_ = term.split("*", 1)
        if a in trees and b_ in trees:
            return ["mul", trees[a], trees[b_]]
    return None


# =========================================================================== 1. law discovery
LAMBDAS = (0.02, 0.05, 0.1, 0.2)


def law_discovery(panel: Panel, *, budget_s: float = 30.0, rng: np.random.Generator | None = None,
                  target: np.ndarray | None = None) -> EngineResult:
    """Sparse regression of the residual on a polynomial library: E[eps | features]."""
    res = EngineResult("law_discovery")
    deadline = time.monotonic() + max(0.5, budget_s)
    holder = _Holder()
    state, _x = _realised(holder, panel)
    lib, trees = feature_library(panel, state)
    y = np.nan_to_num(panel.epsilon) if target is None else np.nan_to_num(target)
    train, test = panel.split()
    theta = np.column_stack([lib[k] for k in lib])
    scale = np.maximum(np.std(theta[train], axis=0), 1e-9)
    scale[0] = 1.0
    theta_n = theta / scale
    best: dict[str, Any] | None = None
    for lam in LAMBDAS:
        if time.monotonic() > deadline:
            res.note("lambda_grid", f"deadline reached before lambda={lam}")
            break
        coef = _stlsq(theta_n[train], y[train], lam)
        res.trials += 1
        fitted = theta_n @ coef
        terms = {k: round(float(c), 6) for k, c in zip(lib, coef, strict=False) if c != 0.0}
        row: dict[str, Any] = {"lambda": lam, "terms": terms, "active": len(terms),
               "r2_train": round(_r2(y[train], fitted[train]), 5),
               "r2_test": round(_r2(y[test], fitted[test]), 5) if test.size else None,
               "equation": "eps = " + (" + ".join(f"{v:+.4f}*{k}" for k, v in terms.items())
                                       or "0"),
               "mdl_bits": round(len(terms) * math.log2(max(2, train.size)), 3)}
        res.findings.append(row)
        if terms and (best is None or (row["r2_test"] or -9) > (best["r2_test"] or -9)):
            best = row
    ps = _library("pysindy")
    if ps is None:
        res.note("pysindy", "not importable here; the numpy STLSQ above is what ran")
    else:  # pragma: no cover - optional dependency
        try:
            X = np.column_stack([lib[k] for k in ("x", "y", "w") if k in lib])[train]
            model = ps.SINDy(optimizer=ps.STLSQ(threshold=0.1),
                             feature_library=ps.PolynomialLibrary(degree=2))
            model.fit(X, t=1.0)
            res.findings.append({"pysindy": [str(e) for e in model.equations(precision=3)]})
            res.trials += 1
        except Exception as exc:
            res.note("pysindy", f"{type(exc).__name__}: {exc}"[:200])
    res.summary = {"best": best, "library": list(lib), "trees": {k: G.to_str(v) for k, v in
                                                                trees.items() if v[1] in
                                                                panel.columns}}
    res.counts = {"equations": len(res.findings), "active_terms": len((best or {}).get("terms",
                                                                                          {}))}
    if best is None:
        res.status = UNMEASURED
        res.note("law", "every coefficient fell below every lambda")
    return res


class _Holder(Scientist):
    """A minimal scientist so `_realised` can mint on an engine's behalf."""

    tradition = "engines"


# ====================================================================== 2. ODE / PDE discovery
def ode_pde_discovery(panel: Panel, *, budget_s: float = 30.0,
                      rng: np.random.Generator | None = None) -> EngineResult:
    """ODE: sparse regression of the smoothed state's derivative on a degree-two library.
    PDE: the cross-section of peers ordered by correlation as a 1-D field u(i, t), fitted to
    u_t = a u_xx + b u_x + c u."""
    res = EngineResult("ode_pde_discovery")
    holder = _Holder()
    state, _x = _realised(holder, panel)
    lib, trees = feature_library(panel, state)
    names = [k for k in ("x", "y", "w") if k in lib]
    train, test = panel.split()
    with _quiet():
        smooth = {k: np.nan_to_num(G.evaluate(["rmean", "__v__", 3], {"__v__": lib[k]}, panel.n))
                  for k in names}
    theta = np.column_stack([lib[k] for k in lib if k != "sin(x)"])
    scale = np.maximum(np.std(theta[train], axis=0), 1e-9)
    scale[0] = 1.0
    theta_n = theta / scale
    keys = [k for k in lib if k != "sin(x)"]
    for k in names:
        deriv = np.gradient(smooth[k])
        coef = _stlsq(theta_n[train], deriv[train], 0.05)
        res.trials += 1
        fitted = theta_n @ coef
        terms = {kk: round(float(c), 6) for kk, c in zip(keys, coef, strict=False) if c != 0.0}
        res.findings.append({"kind": "ode", "state": k, "terms": terms,
                             "equation": f"d{k}/dt = " + (" + ".join(f"{v:+.4f}*{kk}" for kk, v
                                                                     in terms.items()) or "0"),
                             "r2_train": round(_r2(deriv[train], fitted[train]), 5),
                             "r2_test": round(_r2(deriv[test], fitted[test]), 5)
                             if test.size else None})
    nodes = sorted(panel.peers) if len(panel.peers) >= 3 else []
    if nodes:
        field_ = np.column_stack([_z(np.nan_to_num(_finite(panel.peers[k]))) for k in nodes])
        order = np.argsort([-_corr(field_[train, i], np.nan_to_num(panel.epsilon)[train])
                            for i in range(len(nodes))])
        u = field_[:, order]
        u_t = np.gradient(u, axis=0)
        u_x = np.gradient(u, axis=1)
        u_xx = np.gradient(u_x, axis=1)
        design = np.column_stack([u_xx[train].ravel(), u_x[train].ravel(), u[train].ravel()])
        coef = _ols(design, u_t[train].ravel())
        res.trials += 1
        design_test = np.column_stack([u_xx[test].ravel(), u_x[test].ravel(), u[test].ravel()])
        res.findings.append({"kind": "pde", "nodes": [nodes[i] for i in order],
                             "equation": f"u_t = {coef[0]:+.4f} u_xx {coef[1]:+.4f} u_x "
                                         f"{coef[2]:+.4f} u",
                             "coefficients": {"diffusion": round(float(coef[0]), 6),
                                              "advection": round(float(coef[1]), 6),
                                              "reaction": round(float(coef[2]), 6)},
                             "r2_train": round(_r2(u_t[train].ravel(), design @ coef), 5),
                             "r2_test": round(_r2(u_t[test].ravel(), design_test @ coef), 5)
                             if test.size else None})
    else:
        res.note("pde", "fewer than three peers; no spatial axis to discretise")
    res.counts = {"ode": sum(1 for f in res.findings if f["kind"] == "ode"),
                  "pde": sum(1 for f in res.findings if f["kind"] == "pde")}
    _ = (budget_s, rng, trees)
    return res


# ====================================================================== 3. ABC inference
def abc_inference(panel: Panel, *, budget_s: float = 30.0,
                  rng: np.random.Generator | None = None, draws: int | None = None
                  ) -> EngineResult:
    """Rejection ABC for an Ornstein-Uhlenbeck law of the realised residual, vectorised over
    draws; `sbi` behind a guard, reported UNMEASURED when absent."""
    res = EngineResult("abc_inference")
    rng = rng or np.random.default_rng(0)
    holder = _Holder()
    _state, x = _realised(holder, panel)
    train, _ = panel.split()
    obs = np.nan_to_num(x[train])
    if obs.size < 200:
        res.status = UNMEASURED
        res.note("observed", f"{obs.size} training rows")
        return res
    sd = max(1e-9, float(np.std(obs)))
    summary_obs = np.asarray([_acf(obs, 1), float(np.std(obs)) / sd, _kurtosis(obs)])
    n = draws or int(min(3000, max(300, budget_s * 400)))
    length = min(600, obs.size)
    theta = rng.uniform(0.0, 1.0, n)
    sigma = rng.uniform(0.2, 2.0, n) * sd
    paths = np.zeros((n, length))
    noise = rng.normal(0.0, 1.0, (n, length))
    for t in range(1, length):
        paths[:, t] = paths[:, t - 1] * (1.0 - theta) + sigma * noise[:, t]
    res.trials = n
    with _quiet():
        centred = paths - paths.mean(1, keepdims=True)
        var = np.maximum((centred ** 2).mean(1), 1e-18)
        acf1 = (centred[:, 1:] * centred[:, :-1]).mean(1) / var
        std_ratio = np.sqrt(var) / sd
        kurt = (centred ** 4).mean(1) / var ** 2 - 3.0
    stats = np.column_stack([acf1, std_ratio, kurt])
    scale = np.maximum(stats.std(0), 1e-9)
    dist = np.sqrt((((stats - summary_obs) / scale) ** 2).sum(1))
    accept = dist <= np.quantile(dist, 0.05)
    post_theta, post_sigma = theta[accept], sigma[accept] / sd
    res.findings.append({"model": "OU: x_{t+1} = (1 - theta) x_t + sigma e",
                         "theta_posterior": {"mean": round(float(post_theta.mean()), 4),
                                             "sd": round(float(post_theta.std()), 4),
                                             "ci90": [round(float(v), 4) for v in
                                                      np.quantile(post_theta, [0.05, 0.95])]},
                         "sigma_over_sd_posterior": {"mean": round(float(post_sigma.mean()), 4),
                                                     "sd": round(float(post_sigma.std()), 4)},
                         "accepted": int(accept.sum()), "draws": n,
                         "observed_summary": {"acf1": round(float(summary_obs[0]), 4),
                                              "std_ratio": 1.0,
                                              "kurtosis": round(float(summary_obs[2]), 4)},
                         "implied_half_life_bars": round(float(-math.log(2) / math.log(
                             max(1e-6, 1.0 - post_theta.mean()))), 3)})
    if _library("sbi") is None:
        res.note("sbi", "not importable here; rejection ABC in numpy is what ran")
    res.counts = {"draws": n, "accepted": int(accept.sum())}
    return res


# ====================================================================== 4. MDL scoring
def mdl_score(expression: Any, panel: Panel, side_mode: str = "follow") -> dict[str, Any]:
    """Total description length of `eps ~ a + b * signal` in bits against the constant model.

    Model bits are the grammar's own MDL of the tree plus two 32-bit coefficients; data bits are
    the Gaussian code length (n/2) log2(RSS/n). A positive `gain_bits` means the expression
    COMPRESSES the residual on the training slice; the held-out gain is reported beside it and
    is the number that matters.
    """
    train, test = panel.split()
    obj = MathObject(kind="relationship", tradition="engines", expression=expression,
                     target=panel.target, horizon=panel.horizon, side_mode=side_mode)
    signal = np.nan_to_num(B.signal_of(obj, panel))
    y = np.nan_to_num(panel.epsilon)

    def bits(rows: np.ndarray, fit_rows: np.ndarray) -> tuple[float, float]:
        design = np.column_stack([np.ones(rows.size), signal[rows]])
        design_fit = np.column_stack([np.ones(fit_rows.size), signal[fit_rows]])
        beta = _ols(design_fit, y[fit_rows])
        rss = float(((y[rows] - design @ beta) ** 2).sum())
        null = float(((y[rows] - y[fit_rows].mean()) ** 2).sum())
        n = max(1, rows.size)
        return (0.5 * n * math.log2(max(rss / n, 1e-18)),
                0.5 * n * math.log2(max(null / n, 1e-18)))

    model_bits = G.mdl_bits(obj.expression) + 64.0
    data_train, null_train = bits(train, train)
    data_test, null_test = bits(test, train) if test.size else (0.0, 0.0)
    return {"canonical": obj.canonical, "model_bits": round(model_bits, 3),
            "data_bits_train": round(data_train, 3), "null_bits_train": round(null_train, 3),
            "gain_bits_train": round(null_train - model_bits - data_train, 3),
            "gain_bits_test": round(null_test - data_test, 3) if test.size else None}


def mdl_competition(panel: Panel, objects: list[MathObject], *, budget_s: float = 10.0,
                    rng: np.random.Generator | None = None) -> EngineResult:
    res = EngineResult("mdl_score")
    deadline = time.monotonic() + max(0.5, budget_s)
    for obj in objects[:40]:
        if time.monotonic() > deadline:
            res.note("objects", "deadline reached")
            break
        try:
            row = mdl_score(obj.expression, panel, obj.side_mode)
        except Exception as exc:
            res.note(obj.canonical[:60], f"{type(exc).__name__}")
            continue
        res.trials += 1
        res.findings.append({"object_id": obj.object_id, "tradition": obj.tradition, **row})
    res.findings.sort(key=lambda r: -(r.get("gain_bits_test") or -9e9))
    res.counts = {"scored": len(res.findings),
                  "compress_held_out": sum(1 for r in res.findings
                                           if (r.get("gain_bits_test") or 0) > 0)}
    if not objects:
        res.status = UNMEASURED
        res.note("objects", "nothing to score")
    _ = rng
    return res


# ================================================================ 5. model competition
def model_competition(panel: Panel, *, budget_s: float = 30.0,
                      rng: np.random.Generator | None = None) -> EngineResult:
    """Constant, AR(1), AR(2), threshold-AR and linear-in-columns models of the residual, judged
    by BIC, Laplace evidence and time-ordered cross-validation; the winners are compared."""
    res = EngineResult("model_competition")
    holder = _Holder()
    _state, x_raw = _realised(holder, panel)
    x = _z(np.nan_to_num(x_raw))
    x2 = np.concatenate([[0.0, 0.0], x[:-2]])
    y = np.nan_to_num(panel.epsilon)
    train, test = panel.split()
    cols = [c for c in G.BAR_VARIABLES if c in panel.columns and c not in ("open", "high",
                                                                            "low", "close")][:4]
    with _quiet():
        linear = [np.nan_to_num(G.evaluate(["z", c, 24], panel.columns, panel.n)) for c in cols]
    designs: dict[str, np.ndarray] = {
        "constant": np.ones((panel.n, 1)),
        "ar1": np.column_stack([np.ones(panel.n), x]),
        "ar2": np.column_stack([np.ones(panel.n), x, x2]),
        "threshold_ar": np.column_stack([np.ones(panel.n), x * (x > 0), x * (x < 0)]),
    }
    if linear:
        designs["linear_columns"] = np.column_stack([np.ones(panel.n), *linear])
    n = train.size
    folds = 4
    predictions: dict[str, np.ndarray] = {}
    for name, design in designs.items():
        beta = _ols(design[train], y[train])
        fitted = design @ beta
        rss = float(((y[train] - fitted[train]) ** 2).sum())
        k = design.shape[1]
        ll = -0.5 * n * (math.log(2 * math.pi * max(rss / n, 1e-18)) + 1.0)
        bic = k * math.log(n) - 2.0 * ll
        evidence = ll - 0.5 * k * math.log(n)
        cv = []
        for f in range(1, folds + 1):
            cut = int(n * f / (folds + 1))
            fit_rows, val_rows = train[:cut], train[cut:int(n * (f + 1) / (folds + 1))]
            if fit_rows.size < 30 or val_rows.size < 10:
                continue
            b_ = _ols(design[fit_rows], y[fit_rows])
            cv.append(float(np.mean((y[val_rows] - design[val_rows] @ b_) ** 2)))
        predictions[name] = fitted
        res.trials += 1
        res.findings.append({"model": name, "k": k, "log_likelihood": round(ll, 3),
                             "bic": round(bic, 3), "log_evidence": round(evidence, 3),
                             "cv_mse": round(float(np.mean(cv)), 8) if cv else None,
                             "test_mse": round(float(np.mean((y[test] - fitted[test]) ** 2)), 8)
                             if test.size else None})
    winners = {"bic": min(res.findings, key=lambda r: r["bic"])["model"],
               "evidence": max(res.findings, key=lambda r: r["log_evidence"])["model"],
               "cv": min((r for r in res.findings if r["cv_mse"] is not None),
                         key=lambda r: r["cv_mse"], default=res.findings[0])["model"],
               "test": min((r for r in res.findings if r["test_mse"] is not None),
                           key=lambda r: r["test_mse"], default=res.findings[0])["model"]}
    res.summary = {"winners": winners, "agree": len(set(winners.values())) == 1}
    res.summary["predictions"] = dict(predictions)
    res.counts = {"models": len(res.findings)}
    _ = (budget_s, rng)
    return res


# ================================================================ 6. latent -> symbolic
def latent_to_symbolic(panel: Panel, *, budget_s: float = 20.0,
                       rng: np.random.Generator | None = None, max_candidates: int = 400
                       ) -> EngineResult:
    """Fit a latent (the first principal component of the bar columns) and then search for the
    symbolic expression that reproduces it -- the latent is the target, not the residual."""
    res = EngineResult("latent_to_symbolic")
    rng = rng or np.random.default_rng(0)
    deadline = time.monotonic() + max(0.5, budget_s)
    cols = [c for c in G.BAR_VARIABLES if c in panel.columns and c not in ("open", "high", "low")]
    if len(cols) < 3:
        res.status = UNMEASURED
        res.note("columns", "fewer than three bar columns")
        return res
    train, test = panel.split()
    with _quiet():
        matrix = np.column_stack([_z(np.nan_to_num(G.evaluate(["z", c, 24], panel.columns,
                                                              panel.n))) for c in cols])
    cov = np.cov(matrix[train].T)
    vals, vecs = np.linalg.eigh(cov)
    loading = vecs[:, -1]
    latent = matrix @ loading
    best: tuple[float, Any] | None = None
    for _ in range(max_candidates):
        if time.monotonic() > deadline:
            break
        expr = G.random_expr(rng, cols, max_depth=3)
        with _quiet():
            values = np.nan_to_num(G.evaluate(expr, panel.columns, panel.n))
        c = abs(_corr(values[train], latent[train]))
        res.trials += 1
        if best is None or c > best[0]:
            best = (c, expr)
    if best is None:
        res.status = UNMEASURED
        res.note("search", "no candidate evaluated before the deadline")
        return res
    with _quiet():
        values = np.nan_to_num(G.evaluate(best[1], panel.columns, panel.n))
    res.findings.append({"latent": "PC1 of the z-scored bar columns",
                         "explained_share": round(float(vals[-1] / max(1e-12, vals.sum())), 4),
                         "loadings": {c: round(float(v), 4) for c, v in zip(cols, loading,
                                                                             strict=False)},
                         "expression": G.to_str(best[1]), "tree": best[1],
                         "corr_train": round(best[0], 4),
                         "corr_test": round(abs(_corr(values[test], latent[test])), 4)
                         if test.size else None,
                         "mdl_bits": round(G.mdl_bits(best[1]), 3)})
    res.counts = {"candidates": res.trials}
    return res


# ================================================================ 7. counterfactual simulator
def counterfactual_simulator(panel: Panel, law: dict[str, Any] | None, *,
                             budget_s: float = 5.0, rng: np.random.Generator | None = None
                             ) -> EngineResult:
    """Given a discovered law's terms over the library, what does the residual do under
    do(y := 0) and do(w := w + 1)? A simulator over the fitted law, on the held-out rows."""
    res = EngineResult("counterfactual_simulator")
    if not law or not law.get("terms"):
        res.status = UNMEASURED
        res.note("law", "no discovered law to intervene on")
        return res
    holder = _Holder()
    state, _x = _realised(holder, panel)
    lib, _trees = feature_library(panel, state)
    _train, test = panel.split()
    rows = test if test.size else _train

    def predict(columns: dict[str, np.ndarray]) -> np.ndarray:
        out = np.zeros(rows.size)
        for term, coef in law["terms"].items():
            if term == "1":
                out += coef
            elif "*" in term:
                a, b_ = term.split("*", 1)
                out += coef * columns[a][rows] * columns[b_][rows]
            elif term == "|x|":
                out += coef * np.abs(columns["x"][rows])
            elif term == "sin(x)":
                out += coef * np.sin(columns["x"][rows])
            elif term in columns:
                out += coef * columns[term][rows]
        return out

    base = {k: lib[k] for k in ("x", "y", "w", "u") if k in lib}
    factual = predict(base)
    for name, intervention in (("do(y := 0)", {"y": np.zeros(panel.n)}),
                               ("do(w := w + 1)", {"w": base.get("w", np.zeros(panel.n)) + 1.0}),
                               ("do(x := 0)", {"x": np.zeros(panel.n)})):
        if any(k not in base for k in intervention):
            continue
        cf = predict({**base, **intervention})
        res.trials += 1
        res.findings.append({"intervention": name,
                             "delta_mean": round(float(np.mean(cf - factual)), 8),
                             "delta_sd": round(float(np.std(cf - factual)), 8),
                             "factual_mean": round(float(np.mean(factual)), 8),
                             "rows": int(rows.size)})
    res.counts = {"interventions": len(res.findings)}
    _ = (budget_s, rng)
    return res


# ============================================================ 8. experimental discrimination
def experimental_discrimination(panel: Panel, predictions: dict[str, np.ndarray], *,
                                budget_s: float = 5.0, rng: np.random.Generator | None = None
                                ) -> EngineResult:
    """The slice (era x regime x session) where the competing models disagree most is the
    experiment to run next: it is where one observation discriminates the most hypotheses."""
    res = EngineResult("experimental_discrimination")
    if len(predictions) < 2:
        res.status = UNMEASURED
        res.note("models", "fewer than two competing predictions")
        return res
    stack = np.column_stack([np.nan_to_num(v) for v in predictions.values()])
    disagreement = stack.var(1)
    eras = panel.eras(4)
    regime = panel.regime if panel.regime is not None else np.full(panel.n, "?", dtype=object)
    session = panel.session if panel.session is not None else np.full(panel.n, "?",
                                                                       dtype=object)
    table: list[dict[str, Any]] = []
    for e in range(4):
        for g in sorted(set(np.asarray(regime).astype(str).tolist())):
            for s in sorted(set(np.asarray(session).astype(str).tolist())):
                rows = np.flatnonzero((eras == e) & (np.asarray(regime).astype(str) == g)
                                      & (np.asarray(session).astype(str) == s))
                if rows.size < 20:
                    continue
                table.append({"era": e, "regime": g, "session": s, "rows": int(rows.size),
                              "disagreement": round(float(disagreement[rows].mean()), 10)})
                res.trials += 1
    if not table:
        res.status = UNMEASURED
        res.note("slices", "no slice carries 20 rows")
        return res
    table.sort(key=lambda r: -r["disagreement"])
    res.findings = table[:8]
    res.summary = {"next_experiment": table[0], "models": list(predictions),
                   "rule": "test where the models disagree most; agreement teaches nothing"}
    res.counts = {"slices": len(table)}
    _ = (budget_s, rng)
    return res


# ============================================================ 9. synthetic calibration
def synthetic_panel(rng: np.random.Generator, n: int = 2600, *, planted: str = "true",
                    target: str = "SYNTH") -> Panel:
    """A synthetic market with a PLANTED law. `planted="true"`: eps = 0.5 y + 0.3 y^2 + noise
    everywhere. `planted="fake"`: the same law on the training slice ONLY and pure noise after
    it -- the adversarial world, a law that a training-slice search will find and that the
    held-out judge must reject."""
    ret = 0.0008 * np.sin(2 * np.pi * np.arange(n) / 24) + 0.0006 * rng.normal(0, 1, n)
    close = 100.0 * np.exp(np.cumsum(ret))
    columns = {"close": close, "open": close, "high": close * 1.0004, "low": close * 0.9996,
               "ret": ret, "range": np.abs(ret) * 2 + 1e-6, "body": ret,
               "activity": 100 + 8 * np.abs(rng.normal(0, 1, n)), "spread": np.full(n, 1e-4),
               "atr": np.abs(ret) * 3 + 1e-6, "vol": 0.001 + 0.0002 * np.abs(rng.normal(0, 1, n)),
               "flow": rng.normal(0, 1, n)}
    with _quiet():
        y = np.nan_to_num(G.evaluate(["z", "ret", 24], columns, n))
        w = np.nan_to_num(G.evaluate(["z", "range", 24], columns, n))
    noise = rng.normal(0, 1, n)
    if planted == "true":
        eps = 0.5 * y + 0.3 * y * y + noise
    else:
        cut = int(n * 0.6)
        eps = noise.copy()
        eps[:cut] += 0.8 * w[:cut]
    return Panel(target=target, times=np.arange(n, dtype=np.int64) * 3600 + 1_600_000_000,
                 epsilon=eps, columns=columns,
                 meta={k: Variable(k, f"synthetic:{target}", "bars") for k in columns},
                 regime=np.asarray(["low", "mid", "high"])[(np.arange(n) // 40) % 3],
                 session=np.asarray(["asia", "london", "ny"])[(np.arange(n) // 8) % 3],
                 horizon="4", source=f"synthetic_{planted}")


def synthetic_calibration(*, budget_s: float = 20.0, rng: np.random.Generator | None = None,
                          permutations: int = 60) -> EngineResult:
    """Plant a true law and check the discovery engine recovers it; plant a FAKE law that holds
    in-sample only and check the judge rejects it. Both verdicts are the calibration."""
    res = EngineResult("synthetic_calibration")
    rng = rng or np.random.default_rng(20260922)
    true_panel = synthetic_panel(rng, planted="true")
    law = law_discovery(true_panel, budget_s=budget_s / 2, rng=rng)
    best = (law.summary or {}).get("best") or {}
    terms = best.get("terms", {})
    recovered = ("y" in terms and terms["y"] > 0 and "y*y" in terms and terms["y*y"] > 0)
    res.trials += law.trials
    res.findings.append({"world": "true_law", "planted": "eps = 0.5 y + 0.3 y^2 + noise",
                         "recovered": bool(recovered), "terms": terms,
                         "r2_test": best.get("r2_test")})
    fake_panel = synthetic_panel(rng, planted="fake")
    fake = MathObject(kind="relationship", tradition="adversarial_world",
                      expression=["z", "range", 24], target=fake_panel.target,
                      horizon=fake_panel.horizon, side_mode="follow",
                      statement="the planted fake law: eps follows z(range, 24)")
    verdict = B.judge(fake, fake_panel, distinct_forms=1, rng=rng, permutations=permutations)
    res.trials += 1
    res.findings.append({"world": "adversarial_fake_law",
                         "planted": "eps = 0.8 z(range, 24) on the training slice only",
                         "ic_in_sample": fake.evidence.ic_in_sample,
                         "ic_held_out": fake.evidence.ic_held_out,
                         "rejected": not fake.passed, "value": round(verdict.value, 4),
                         "gates": verdict.gates})
    res.summary = {"true_law_recovered": bool(recovered), "fake_law_rejected": not fake.passed,
                   "calibrated": bool(recovered and not fake.passed)}
    res.counts = {"worlds": 2}
    if not res.summary["calibrated"]:
        res.status = "FAILED"
    return res


# ============================================================ 10. independent civilizations
def independent_civilizations(panel: Panel, populations: dict[str, list[Any]], *,
                              seeds: dict[str, int], budget_s: float = 30.0,
                              permutations: int = 60, judge: Callable[..., Any] | None = None
                              ) -> EngineResult:
    """Two or more isolated scientist populations with DISJOINT seeds over the same panel,
    compared only through the judge: what both find is replicated, what one finds is not."""
    res = EngineResult("independent_civilizations")
    if len(populations) < 2:
        res.status = UNMEASURED
        res.note("populations", "fewer than two civilizations")
        return res
    if len(set(seeds.values())) != len(seeds):
        res.status = "FAILED"
        res.note("seeds", "civilizations must not share a seed")
        return res
    per_pop = max(1.0, budget_s / len(populations))
    passed_by: dict[str, set[str]] = {}
    objects_by: dict[str, list[MathObject]] = {}
    judge = judge or B.judge
    for name, scientists in populations.items():
        rng = np.random.default_rng(seeds[name])
        view = Panel(target=panel.target, times=panel.times, epsilon=panel.epsilon,
                     columns=dict(panel.columns), meta=dict(panel.meta), regime=panel.regime,
                     session=panel.session, peers=panel.peers, horizon=panel.horizon,
                     source=panel.source)
        objects: list[MathObject] = []
        distinct: set[str] = set()
        for scientist in scientists:
            try:
                found = scientist.propose(view, per_pop / max(1, len(scientists)), rng)
            except Exception as exc:
                res.note(f"{name}/{scientist.tradition}", f"{type(exc).__name__}")
                continue
            objects.extend(found)
            distinct |= scientist.distinct
        passed: set[str] = set()
        for obj in objects:
            try:
                judge(obj, view, distinct_forms=max(1, len(distinct)), rng=rng,
                      permutations=permutations)
            except Exception as exc:
                res.note(f"{name}/{obj.canonical[:40]}", f"judge {type(exc).__name__}")
                continue
            res.trials += 1
            if obj.passed:
                passed.add(obj.canonical)
        passed_by[name] = passed
        objects_by[name] = objects
        res.findings.append({"civilization": name, "seed": seeds[name],
                             "scientists": [s.tradition for s in scientists],
                             "objects": len(objects), "distinct_forms": len(distinct),
                             "passed": len(passed)})
    names = list(populations)
    common = set.intersection(*(passed_by[n] for n in names)) if names else set()
    res.summary = {"replicated_across_civilizations": sorted(common),
                   "compared_by": "the judge only; no civilization reads another's objects",
                   "objects_by_civilization": {n: len(objects_by[n]) for n in names}}
    res.counts = {"civilizations": len(names), "replicated": len(common)}
    return res


# ============================================================ 11. method tournament
def wilson_lower(passed: int, trials: int, z: float = 1.64) -> float:
    # A method cannot pass more often than it tried: when the trials counter under-reports
    # (a tradition whose `evaluated` never incremented but whose objects survived), the number
    # of passes is itself a LOWER BOUND on the trials, and p is clamped to [0, 1] so the
    # interval is conservative rather than a domain error inside the square root.
    trials = max(int(trials), int(passed))
    if trials <= 0:
        return 0.0
    p = min(1.0, max(0.0, passed / trials))
    denom = 1.0 + z * z / trials
    centre = p + z * z / (2 * trials)
    margin = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials))
    return max(0.0, (centre - margin) / denom)


def method_tournament(stats: dict[str, dict[str, Any]], *, budget_s: float = 1.0,
                      rng: np.random.Generator | None = None) -> EngineResult:
    """Rank search methods by survivors per trial (Wilson lower bound) and per compute hour."""
    res = EngineResult("method_tournament")
    for method, row in stats.items():
        trials = int(row.get("trials") or row.get("distinct") or 0)
        passed = int(row.get("passed") or 0)
        forward = int(row.get("forward") or 0)
        trials = max(trials, passed)
        hours = max(0.0, float(row.get("compute_s") or 0.0)) / 3600.0
        res.findings.append({"method": method, "trials": trials, "passed": passed,
                             "forward": forward,
                             "survival_lower_bound": round(wilson_lower(passed, trials), 5),
                             "survivors_per_hour": round(passed / hours, 3) if hours > 0 else None,
                             "status": "MEASURED" if trials > 0 else UNMEASURED})
        res.trials += 1
    res.findings.sort(key=lambda r: (-r["survival_lower_bound"], -r["forward"], r["method"]))
    for rank, row in enumerate(res.findings, 1):
        row["rank"] = rank
    res.counts = {"methods": len(res.findings)}
    if not res.findings:
        res.status = UNMEASURED
    _ = (budget_s, rng)
    return res


# ============================================================ 12. distributed science
DEPARTMENT_FLOOR = 0.2


def distributed_science(budget_s: float, department_roi: dict[str, float | None], *,
                        floor: float = DEPARTMENT_FLOOR) -> EngineResult:
    """Split one budget across departments, two-sided around equal shares by measured ROI,
    floored so no department is ever starved of its scout."""
    res = EngineResult("distributed_science")
    names = list(department_roi)
    if not names:
        res.status = UNMEASURED
        return res
    measured = {k: v for k, v in department_roi.items() if isinstance(v, (int, float))}
    scale = float(np.mean([abs(v) for v in measured.values()])) if measured else 0.0
    raw: dict[str, float] = {}
    for k in names:
        value = department_roi[k]
        raw[k] = 1.0 if value is None or scale <= 0 else max(0.05, 1.0 + float(value) / scale)
    total = sum(raw.values())
    floor = min(floor, 1.0 / len(names))
    free = max(0.0, 1.0 - floor * len(names))
    shares = {k: floor + free * raw[k] / total for k in names}
    res.findings = [{"department": k, "share": round(shares[k], 4),
                     "budget_s": round(budget_s * shares[k], 1), "roi": department_roi[k],
                     "roi_status": "MEASURED" if department_roi[k] is not None else UNMEASURED}
                    for k in names]
    res.summary = {"budgets": {k: round(budget_s * shares[k], 1) for k in names},
                   "shares": {k: round(shares[k], 4) for k in names}, "floor": floor,
                   "two_sided": "shares move up and down with ROI; the floor keeps every "
                                "department's scout alive"}
    res.counts = {"departments": len(names)}
    return res


# ============================================================ 13. formal maths (sympy guard)
def formal_maths(expressions: list[Any], *, budget_s: float = 5.0,
                 rng: np.random.Generator | None = None) -> EngineResult:
    """Algebraic normal forms through sympy when it imports; the grammar's own canonicaliser
    otherwise, reported as such."""
    res = EngineResult("formal_maths")
    sympy = _library("sympy")
    for expr in expressions[:50]:
        _simplified, canonical = G.canonical(expr)
        row = {"input": G.to_str(expr), "canonical": canonical,
               "engine": "sympy" if sympy is not None else "grammar.simplify"}
        if sympy is not None:  # pragma: no cover - optional dependency
            try:
                row["algebraic_key"] = G.algebraic_key(expr)
            except Exception as exc:
                row["algebraic_key"] = f"{UNMEASURED}: {type(exc).__name__}"
        res.findings.append(row)
        res.trials += 1
    if sympy is None:
        res.note("sympy", "not importable here; formal simplification is the desk's own "
                          "canonicaliser (grammar.simplify), which is what dedup charges by")
    res.counts = {"simplified": len(res.findings)}
    if not expressions:
        res.status = UNMEASURED
    _ = (budget_s, rng)
    return res


# ============================================================ 14. differentiable science
def differentiable_science(panel: Panel, *, budget_s: float = 10.0,
                           rng: np.random.Generator | None = None, steps: int = 300
                           ) -> EngineResult:
    """Fit eps ~ a tanh(b x) + c by gradient descent: JAX when it imports, else the analytic
    numpy gradient. The saturation parameter b is the finding; the linear fit is the baseline."""
    res = EngineResult("differentiable_science")
    holder = _Holder()
    _state, x_raw = _realised(holder, panel)
    x = _z(np.nan_to_num(x_raw))
    y = np.nan_to_num(panel.epsilon)
    train, test = panel.split()
    xt, yt = x[train], y[train]
    a, b_, c = 0.1, 1.0, float(yt.mean())
    lr = 0.05
    jax = _library("jax")
    engine = "numpy analytic gradient"
    if jax is not None:  # pragma: no cover - optional dependency
        try:
            jnp = jax.numpy

            def loss(params: Any) -> Any:
                return jnp.mean((yt - (params[0] * jnp.tanh(params[1] * xt) + params[2])) ** 2)

            grad = jax.grad(loss)
            params = jnp.asarray([a, b_, c])
            for _ in range(steps):
                params = params - lr * grad(params)
            a, b_, c = (float(v) for v in params)
            engine = "jax.grad"
        except Exception as exc:
            res.note("jax", f"{type(exc).__name__}; numpy fallback ran")
            jax = None
    if jax is None:
        for _ in range(steps):
            t = np.tanh(b_ * xt)
            resid = yt - (a * t + c)
            grad_a = -2.0 * float(np.mean(resid * t))
            grad_b = -2.0 * float(np.mean(resid * a * (1 - t * t) * xt))
            grad_c = -2.0 * float(np.mean(resid))
            a, b_, c = a - lr * grad_a, b_ - lr * grad_b, c - lr * grad_c
        res.note("jax", "not importable here; the analytic numpy gradient is what ran")
    res.trials = steps
    fitted = a * np.tanh(b_ * x) + c
    lin = _ols(np.column_stack([np.ones(train.size), xt]), yt)
    linear = lin[0] + lin[1] * x
    res.findings.append({"model": "eps = a tanh(b x) + c", "engine": engine,
                         "a": round(a, 6), "b": round(b_, 6), "c": round(c, 6),
                         "mse_train": round(float(np.mean((yt - fitted[train]) ** 2)), 8),
                         "mse_test": round(float(np.mean((y[test] - fitted[test]) ** 2)), 8)
                         if test.size else None,
                         "linear_mse_test": round(float(np.mean((y[test] - linear[test]) ** 2)), 8)
                         if test.size else None, "steps": steps})
    res.counts = {"steps": steps}
    _ = (budget_s, rng)
    return res


# ============================================================ 15. primitive invention
def _subtrees(node: Any, out: list[Any]) -> None:
    if isinstance(node, list) and node:
        if G.depth(node) >= 2:
            out.append(node)
        for child in node[1:]:
            _subtrees(child, out)


def primitive_invention(objects: list[MathObject], *, min_support: int = 2, top: int = 8,
                        budget_s: float = 2.0, rng: np.random.Generator | None = None
                        ) -> EngineResult:
    """Subexpressions that recur across objects of DIFFERENT origins are proposed as new
    primitives: an operator the grammar should have, with its MDL saving measured."""
    res = EngineResult("primitive_invention")
    support: dict[str, dict[str, Any]] = {}
    for obj in objects:
        found: list[Any] = []
        _subtrees(obj.expression, found)
        seen: set[str] = set()
        for sub in found:
            key = G.to_str(sub)
            if key in seen or G.nodes(sub) < 3:
                continue
            seen.add(key)
            row = support.setdefault(key, {"definition": sub, "support": 0,
                                           "traditions": set(), "nodes": G.nodes(sub)})
            row["support"] += 1
            row["traditions"].add(obj.tradition)
    for key, row in support.items():
        if row["support"] >= min_support:
            res.findings.append({"name": "prim_" + G.fingerprint(row["definition"])[:10],
                                 "definition": key, "tree": row["definition"],
                                 "support": row["support"],
                                 "traditions": sorted(row["traditions"]),
                                 "mdl_saving_bits": round((row["nodes"] - 1) * row["support"]
                                                          * math.log2(G._VOCAB), 3)})
            res.trials += 1
    res.findings.sort(key=lambda r: (-r["support"], -r["mdl_saving_bits"], r["name"]))
    res.findings = res.findings[:top]
    res.counts = {"subexpressions": len(support), "proposed": len(res.findings)}
    if not objects:
        res.status = UNMEASURED
    _ = (budget_s, rng)
    return res


# ============================================================================ orchestration
ENGINE_NAMES: tuple[str, ...] = (
    "law_discovery", "ode_pde_discovery", "abc_inference", "mdl_score", "model_competition",
    "latent_to_symbolic", "counterfactual_simulator", "experimental_discrimination",
    "synthetic_calibration", "independent_civilizations", "method_tournament",
    "distributed_science", "formal_maths", "differentiable_science", "primitive_invention",
)


def run_engine(name: str, fn: Callable[..., EngineResult], *args: Any, **kwargs: Any
               ) -> EngineResult:
    """Run one engine, timed, never raising."""
    started = time.monotonic()
    try:
        out = fn(*args, **kwargs)
    except Exception as exc:
        out = EngineResult(name, status="FAILED")
        out.note("raised", f"{type(exc).__name__}: {exc}"[:300])
    out.compute_s = time.monotonic() - started
    return out


def run_all(panel: Panel, objects: list[MathObject], *, budget_s: float, rng: np.random.Generator,
            populations: dict[str, list[Any]] | None = None, seeds: dict[str, int] | None = None,
            method_stats: dict[str, dict[str, Any]] | None = None,
            department_roi: dict[str, float | None] | None = None, permutations: int = 60
            ) -> dict[str, EngineResult]:
    """Every engine once, each on a slice of the budget, in an order that lets the later ones
    read the earlier ones' findings. The dict is keyed by engine name so the wiring proof can
    count what ran."""
    slice_s = max(0.5, budget_s / len(ENGINE_NAMES))
    out: dict[str, EngineResult] = {}
    out["law_discovery"] = run_engine("law_discovery", law_discovery, panel, budget_s=slice_s,
                                      rng=rng)
    out["ode_pde_discovery"] = run_engine("ode_pde_discovery", ode_pde_discovery, panel,
                                          budget_s=slice_s, rng=rng)
    out["abc_inference"] = run_engine("abc_inference", abc_inference, panel, budget_s=slice_s,
                                      rng=rng)
    out["mdl_score"] = run_engine("mdl_score", mdl_competition, panel, objects,
                                  budget_s=slice_s, rng=rng)
    out["model_competition"] = run_engine("model_competition", model_competition, panel,
                                          budget_s=slice_s, rng=rng)
    out["latent_to_symbolic"] = run_engine("latent_to_symbolic", latent_to_symbolic, panel,
                                           budget_s=slice_s, rng=rng)
    out["counterfactual_simulator"] = run_engine(
        "counterfactual_simulator", counterfactual_simulator, panel,
        (out["law_discovery"].summary or {}).get("best"), budget_s=slice_s, rng=rng)
    out["experimental_discrimination"] = run_engine(
        "experimental_discrimination", experimental_discrimination, panel,
        (out["model_competition"].summary or {}).get("predictions") or {}, budget_s=slice_s,
        rng=rng)
    out["synthetic_calibration"] = run_engine("synthetic_calibration", synthetic_calibration,
                                              budget_s=slice_s, rng=rng,
                                              permutations=permutations)
    out["independent_civilizations"] = run_engine(
        "independent_civilizations", independent_civilizations, panel, populations or {},
        seeds=seeds or {}, budget_s=slice_s, permutations=permutations)
    out["method_tournament"] = run_engine("method_tournament", method_tournament,
                                          method_stats or {}, budget_s=slice_s, rng=rng)
    out["distributed_science"] = run_engine("distributed_science", distributed_science, budget_s,
                                            department_roi or {"mathematics": None,
                                                               "physics": None})
    out["formal_maths"] = run_engine("formal_maths", formal_maths,
                                     [o.expression for o in objects[:50]], budget_s=slice_s,
                                     rng=rng)
    out["differentiable_science"] = run_engine("differentiable_science", differentiable_science,
                                               panel, budget_s=slice_s, rng=rng)
    out["primitive_invention"] = run_engine("primitive_invention", primitive_invention, objects,
                                            budget_s=slice_s, rng=rng)
    # The model predictions are arrays: they served the discrimination engine and do not belong
    # in the artifact.
    out["model_competition"].summary.pop("predictions", None)
    return out
