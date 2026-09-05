"""Generators for the alpha grammar beyond uniform random trees.

WHY MORE THAN ONE GENERATOR. `alpha_grammar.random_expr` draws trees uniformly over the closed
operator set, so every generation of the evolution spends most of its budget re-discovering that
`corr(spread, spread, 5)` is not an alpha. Two published ideas fix different halves of that waste,
and neither needs a neural network to earn its place at one desk's scale:

    GFLOWNET-LITE (`FlowSampler`). AlphaGen / GFlowNet-style generation learns to sample
        structures in proportion to reward. Stripped to a table: every tree is a set of
        transitions (parent operator -> child token, and root -> first token); a transition's
        weight is exp(temperature x smoothed mean fitness of the trees that contained it); a new
        tree is grown top-down by those weights. Transitions that keep appearing in fit trees are
        sampled more, ones that only appear in culled trees fade, and with no history the table
        is flat -- the sampler is then a random generator with a different shape prior.

    SYMBOLIC REGRESSION (`symbolic_regression`). A hill-climb on the grammar's own mutation move
        toward the expression whose z-scored value best fits a supervised target on the FIRST
        70% of the history. The holdout error on the remaining 30% is reported beside the result
        and NEVER used to choose it: the output is an expression the gauntlet then judges on its
        own terms, with the fit slice named so nobody mistakes in-sample fit for edge.

ONE SIGNATURE. Every generator is (rng, frames, ret, history, allow_drivers, max_depth) -> Expr,
so the evolution can pick between them by weight and record which one produced each individual.
`choose_generator` reads a weight table (uniform when there is none). The weights are meant to
be WRITTEN by a yield ledger that scores each generator by what its individuals went on to
certify; this module never scores itself.

NOTHING HERE HAS AUTHORITY. A generated expression is a trial like any other: charged as one,
screened and deflated by the evolution, judged by the gauntlet.
"""
from __future__ import annotations

import json
import math
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from libs.research import alpha_grammar as ag

Expr = Any                                      # str | list[Any]; JSON-shaped (alpha_grammar)
History = Sequence[tuple[Any, float]]
Generator = Callable[[np.random.Generator, dict[str, pd.Series], pd.Series, History, bool, int],
                     Any]

ROOT_NODE = "<root>"
#: Flow-table defaults. Temperature scales fitness differences into odds; the prior count is
#: how many pseudo-observations at the population mean a transition carries before its own
#: evidence dominates, so one lucky tree cannot own a transition.
TEMPERATURE = 1.0
PRIOR_COUNT = 2.0
MAX_TRIES = 20
EXP_CLIP = 30.0
#: Symbolic-regression defaults: the train slice, and the fewest finite train observations a
#: candidate needs before its error means anything.
TRAIN_FRAC = 0.70
MIN_OBS = 50

#: The last symbolic-regression fit -- train and holdout error, slice sizes -- for the caller
#: that wants them beside the expression (the shared generator signature returns only the tree).
LAST_FIT: dict[str, Any] = {}


# --------------------------------------------------------------------------- flow sampler
def _token(x: Expr) -> str:
    return x if isinstance(x, str) else str(x[0])


def transitions(expr: Expr) -> set[tuple[str, str]]:
    """The (parent -> child token) edges of a tree, plus (root -> first token)."""
    out: set[tuple[str, str]] = {(ROOT_NODE, _token(expr))}

    def _walk(x: Expr) -> None:
        if not isinstance(x, (list, tuple)) or not x:
            return
        op = str(x[0])
        for c in x[1:]:
            if isinstance(c, (str, list, tuple)):
                out.add((op, _token(c)))
                _walk(c)
    _walk(expr)
    return out


class FlowSampler:
    """Transition weights learned from (expression, fitness) history; trees grown by them."""

    def __init__(self, history: History = (), *, temperature: float = TEMPERATURE,
                 prior_count: float = PRIOR_COUNT) -> None:
        self.temperature = float(temperature)
        self.prior_count = float(prior_count)
        self.prior_mean = 0.0
        self.n_history = 0
        self._sum: dict[tuple[str, str], float] = {}
        self._n: dict[tuple[str, str], int] = {}
        self.fit(history)

    def fit(self, history: History) -> FlowSampler:
        """Accumulate per-transition fitness sums and counts. Non-finite fitness is skipped."""
        rows: list[tuple[Expr, float]] = []
        for expr, fit in history:
            try:
                f = float(fit)
            except (TypeError, ValueError):
                continue
            if math.isfinite(f):
                rows.append((expr, f))
        self.n_history += len(rows)
        if rows:
            total = self.prior_mean * (self.n_history - len(rows)) + sum(f for _, f in rows)
            self.prior_mean = total / self.n_history
        for expr, f in rows:
            for t in transitions(expr):
                self._sum[t] = self._sum.get(t, 0.0) + f
                self._n[t] = self._n.get(t, 0) + 1
        return self

    def mean_fitness(self, parent: str, child: str) -> float:
        """Smoothed mean fitness of trees carrying the transition: the population mean counts
        `prior_count` times, so an unseen transition sits at the mean rather than at zero."""
        n = self._n.get((parent, child), 0)
        s = self._sum.get((parent, child), 0.0)
        return (s + self.prior_count * self.prior_mean) / (n + self.prior_count)

    def weight(self, parent: str, child: str) -> float:
        """exp(temperature x mean fitness), centred on the population mean. Centring changes
        no sampling probability (a common factor per parent) and keeps the exponent bounded."""
        x = self.temperature * (self.mean_fitness(parent, child) - self.prior_mean)
        return math.exp(max(-EXP_CLIP, min(EXP_CLIP, x)))

    def _pick(self, rng: np.random.Generator, parent: str, cands: list[str]) -> str:
        w = np.array([self.weight(parent, c) for c in cands], dtype=float)
        p = w / w.sum()
        return str(cands[int(rng.choice(len(cands), p=p))])

    def _grow(self, rng: np.random.Generator, parent: str, depth: int, max_depth: int,
              allow_drivers: bool) -> Expr:
        terms = list(ag.TERMINALS if allow_drivers else ag.BAR_TERMINALS)
        if depth >= max_depth:
            return self._pick(rng, parent, terms)
        # The root is always an operator: a bare terminal is a level, not an alpha.
        cands = list(ag.OPERATORS) + (terms if depth > 0 else [])
        tok = self._pick(rng, parent, cands)
        if tok in terms:
            return tok
        w = int(rng.choice(ag.WINDOWS))
        if tok in ag.UNARY:
            return [tok, self._grow(rng, tok, depth + 1, max_depth, allow_drivers)]
        if tok in ag.WINDOWED:
            return [tok, self._grow(rng, tok, depth + 1, max_depth, allow_drivers), w]
        if tok in ag.BINARY:
            return [tok, self._grow(rng, tok, depth + 1, max_depth, allow_drivers),
                    self._grow(rng, tok, depth + 1, max_depth, allow_drivers)]
        return [tok, self._grow(rng, tok, depth + 1, max_depth, allow_drivers),
                self._grow(rng, tok, depth + 1, max_depth, allow_drivers), w]

    def sample(self, rng: np.random.Generator, max_depth: int = 3,
               allow_drivers: bool = True) -> Expr:
        """A valid tree grown by the learned weights; `random_expr` after MAX_TRIES failures."""
        for _ in range(MAX_TRIES):
            e = self._grow(rng, ROOT_NODE, 0, max_depth, allow_drivers)
            if ag.is_valid(e, allow_drivers):
                return e
        return ag.random_expr(rng, max_depth, allow_drivers)

    def table(self, top: int = 20) -> list[dict[str, Any]]:
        """The strongest transitions, for a report: what the sampler has learned to prefer."""
        rows: list[dict[str, Any]] = [
            {"parent": p, "child": c, "n": n,
             "mean_fitness": round(self.mean_fitness(p, c), 4),
             "weight": round(self.weight(p, c), 4)}
            for (p, c), n in self._n.items()]
        rows.sort(key=lambda r: -float(r["weight"]))
        return rows[:top]


# --------------------------------------------------------------------------- symbolic regression
def _zscore_train(v: np.ndarray, cut: int) -> np.ndarray | None:
    """z-score with TRAIN-slice statistics only, applied to the whole series."""
    tr = v[:cut]
    ok = np.isfinite(tr)
    if int(ok.sum()) < MIN_OBS:
        return None
    m, s = float(tr[ok].mean()), float(tr[ok].std())
    if not math.isfinite(s) or s <= 1e-12:
        return None
    out: np.ndarray = (v - m) / s
    return out


def _mse(z: np.ndarray, y: np.ndarray, sl: slice) -> float:
    """Sign-free squared error: the evolution trades an expression followed OR faded, so a
    perfectly anti-correlated fit is as good as a perfectly correlated one."""
    a, b = z[sl], y[sl]
    ok = np.isfinite(a) & np.isfinite(b)
    if int(ok.sum()) < MIN_OBS:
        return math.inf
    a, b = a[ok], b[ok]
    return float(min(np.mean((a - b) ** 2), np.mean((-a - b) ** 2)))


def symbolic_regression(rng: np.random.Generator, frames: dict[str, pd.Series],
                        target: pd.Series, *, iters: int = 60, allow_drivers: bool = True,
                        max_depth: int = 3, train_frac: float = TRAIN_FRAC) -> Expr:
    """Hill-climb from a random tree by `mutate`, accepting a move when the train-slice error
    falls. The holdout error is measured for the report and never consulted for a decision."""
    LAST_FIT.clear()
    if not frames:
        LAST_FIT["why"] = "no frames: fell back to random_expr"
        return ag.random_expr(rng, max_depth, allow_drivers)
    idx = next(iter(frames.values())).index
    n = len(idx)
    cut = int(n * train_frac)
    y = pd.Series(target).reindex(idx).to_numpy(dtype=float)
    yz = _zscore_train(y, cut)
    if yz is None:
        LAST_FIT["why"] = f"target has under {MIN_OBS} finite train observations: random_expr"
        return ag.random_expr(rng, max_depth, allow_drivers)
    memo: dict[str, pd.Series] = {}

    def score(expr: Expr) -> tuple[float, float]:
        v = ag.evaluate(expr, frames, memo).to_numpy(dtype=float)
        z = _zscore_train(v, cut)
        if z is None:
            return math.inf, math.inf
        return _mse(z, yz, slice(0, cut)), _mse(z, yz, slice(cut, n))

    best = ag.random_expr(rng, max_depth, allow_drivers)
    best_s = score(best)
    accepted = 0
    for _ in range(int(iters)):
        cand = ag.mutate(best, rng, allow_drivers)
        s = score(cand)
        if s[0] < best_s[0]:
            best, best_s, accepted = cand, s, accepted + 1
    LAST_FIT.update({
        "expr": ag.to_str(best),
        "train_mse": (best_s[0] if math.isfinite(best_s[0]) else None),
        "holdout_mse": (best_s[1] if math.isfinite(best_s[1]) else None),
        "n_train": cut, "n_holdout": n - cut, "iters": int(iters), "accepted": accepted,
        "rule": "fitted on the first 70% of the index only; the holdout error is reported and "
                "never used to choose",
    })
    return best


# --------------------------------------------------------------------------- the shared surface
def _gen_random(rng: np.random.Generator, frames: dict[str, pd.Series], ret: pd.Series,
                history: History, allow_drivers: bool, max_depth: int) -> Expr:
    return ag.random_expr(rng, max_depth, allow_drivers)


def _gen_gflow(rng: np.random.Generator, frames: dict[str, pd.Series], ret: pd.Series,
               history: History, allow_drivers: bool, max_depth: int) -> Expr:
    return FlowSampler(history).sample(rng, max_depth, allow_drivers)


def _gen_symreg(rng: np.random.Generator, frames: dict[str, pd.Series], ret: pd.Series,
                history: History, allow_drivers: bool, max_depth: int) -> Expr:
    # NEXT-bar return: the expression at bar t is fitted to what happens from t to t+1. That is
    # a supervised target forward of the expression's own causal inputs, not a leak into them.
    target = pd.Series(ret).shift(-1)
    return symbolic_regression(rng, frames, target, allow_drivers=allow_drivers,
                               max_depth=max_depth)


GENERATORS: dict[str, Generator] = {
    "random": _gen_random,
    "gflow": _gen_gflow,
    "symreg": _gen_symreg,
}


def choose_generator(rng: np.random.Generator, weights: dict[str, float] | None = None) -> str:
    """A generator name drawn by weight. No weights, all-zero, unknown-only or non-finite
    weights all mean uniform -- a bad table degrades to the flat prior, never to a crash."""
    names = list(GENERATORS)
    w = np.ones(len(names), dtype=float)
    if weights:
        cand = np.array([max(0.0, float(weights.get(n, 0.0) or 0.0)) for n in names], dtype=float)
        if np.isfinite(cand).all() and cand.sum() > 0:
            w = cand
    return str(names[int(rng.choice(len(names), p=w / w.sum()))])


def load_weights(path: Path) -> tuple[dict[str, float] | None, str]:
    """The generator weight table and where it came from. `{"weights": {...}}` or a flat table;
    (None, reason) -- uniform -- when the file is absent or unreadable. Never raises."""
    try:
        doc = json.loads(Path(path).read_text("utf-8"))
    except OSError:
        return None, f"{Path(path).name} absent: uniform"
    except ValueError as exc:
        return None, f"{Path(path).name} unreadable ({type(exc).__name__}): uniform"
    table = doc.get("weights", doc) if isinstance(doc, dict) else None
    if not isinstance(table, dict):
        return None, f"{Path(path).name} carries no weight table: uniform"
    out: dict[str, float] = {}
    for k, v in table.items():
        try:
            out[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    known = {k: v for k, v in out.items() if k in GENERATORS}
    if not known:
        return None, f"{Path(path).name} names no known generator: uniform"
    return known, f"{Path(path).name}: {json.dumps(known, sort_keys=True)}"
