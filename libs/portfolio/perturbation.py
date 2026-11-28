"""Allocation perturbation test: how hard does the book move when its inputs move a little?

Mandate 2026-10-06 (D15, P0 item 6): "perturb expected returns, covariance, correlations,
strategy-health estimates, Jev probabilities, costs, capacity; measure dweights/dinputs; add
weight instability to allocator proof (huge Jacobian sensitivity loses authority)." Jev was
dropped (zuck 2026-11-11); the probability input perturbed here is the desk's own regime mix.

EACH CLASS IS ONE SMALL, STATED MOVE, sized from the evidence's own uncertainty, never a number
someone liked:

    mu            every sleeve's mean shifted by one standard error, random sign
    covariance    a moving-block bootstrap of the days (block = the worlds' own `block_days`)
    correlation   a random tenth of the days re-ordered independently per sleeve, which lowers
                  co-movement while keeping every sleeve's own distribution exactly
    health        each sleeve's decay probability scaled by U(0.5, 1.5) (blanket when unset)
    probabilities the regime mix redrawn from a Dirichlet centred on it with the HMM's own
                  effective sample (`n_obs`) as concentration
    costs         each sleeve's `cost_bias_r` scaled by U(0.5, 1.5) plus its `cost_r` uncertainty
    capacity      per-sleeve bounds scaled by U(0.8, 1.2) when bounds exist

For each class: the L1 distance between the base book and the perturbed book over twice the
base total (0 = unchanged, 1 = a completely different book), averaged over draws, and the
elasticity = that distance / the relative size of the input move. The INSTABILITY of a book is
the mean distance over all classes.

THE NULL IS THE SOLVER'S OWN NOISE. Re-solving the SAME inputs on a different world seed moves
the book too; a book is only "unstable" beyond that. `instability_excess` = instability minus the
re-seed distance.

AUTHORITY, SHADOW ONLY. `would_lose_authority` is True when the allocator's excess instability is
the largest of every book measured AND at least twice the median challenger's. It is published,
never enforced: Growth Governance Rule 1 says a mechanism that can take capital away must first
prove it raises robust forward E[log W], and this one has not yet been measured doing so.
"""
from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import numpy as np

CLASSES = ("mu", "covariance", "correlation", "health", "probabilities", "costs", "capacity")
#: Draws per class. DERIVATION: the distance is a mean of [0, 1] values; 6 draws put its standard
#: error under 0.2 of its spread, enough to rank books, and keep one pass inside an hourly leg.
DRAWS = 6
#: Share of days whose order is broken per sleeve in the correlation move.
CORR_SHARE = 0.10
#: The authority flag's ratio to the median challenger (see module docstring).
AUTHORITY_RATIO = 2.0


def distance(a: Mapping[str, float], b: Mapping[str, float]) -> float:
    keys = set(a) | set(b)
    tot = sum(abs(float(v)) for v in a.values())
    if tot <= 0:
        return 0.0 if not any(abs(float(v)) > 1e-12 for v in b.values()) else 1.0
    return min(1.0, sum(abs(float(a.get(k, 0.0)) - float(b.get(k, 0.0))) for k in keys)
               / (2.0 * tot))


def _obs(ev: Sequence[Any]) -> int:
    return min(int(np.asarray(e.daily_r).size) for e in ev)


def perturb(ev: Sequence[Any], cls: str, rng: np.random.Generator, *, block: int = 5,
            decay_blanket: float = 0.30) -> tuple[list[Any], float]:
    """One perturbed copy of the evidence, and the relative size of the move."""
    obs = _obs(ev)
    out: list[Any] = []
    if cls == "mu":
        rel = []
        for e in ev:
            r = np.asarray(e.daily_r, dtype=float)
            w = np.nan_to_num(r[-obs:], nan=0.0)
            se = float(w.std(ddof=1)) / math.sqrt(max(obs, 1)) if obs > 1 else 0.0
            shift = se * (1.0 if rng.random() < 0.5 else -1.0)
            rel.append(abs(shift) / max(abs(float(w.mean())), se, 1e-12))
            out.append(dataclasses.replace(e, daily_r=r + shift))
        return out, float(np.mean(rel)) if rel else 0.0
    if cls == "covariance":
        b = max(1, int(block))
        starts = rng.integers(0, max(obs - b, 1), size=math.ceil(obs / b))
        idx = np.concatenate([np.arange(s, s + b) for s in starts])[:obs]
        for e in ev:
            r = np.asarray(e.daily_r, dtype=float)
            head, tail = r[:-obs], r[-obs:]
            out.append(dataclasses.replace(e, daily_r=np.concatenate([head, tail[idx]])))
        return out, 1.0
    if cls == "correlation":
        k = max(2, int(CORR_SHARE * obs))
        days = rng.choice(obs, size=min(k, obs), replace=False)
        for e in ev:
            r = np.asarray(e.daily_r, dtype=float).copy()
            tail = r[-obs:]
            tail[days] = tail[rng.permutation(days)]
            r[-obs:] = tail
            out.append(dataclasses.replace(e, daily_r=r))
        return out, CORR_SHARE
    if cls == "health":
        rel = []
        for e in ev:
            base = getattr(e, "decay_prob_i", None)
            base = decay_blanket if base is None else float(base)
            f = float(rng.uniform(0.5, 1.5))
            rel.append(abs(f - 1.0))
            out.append(dataclasses.replace(e, decay_prob_i=min(max(base * f, 0.0), 1.0)))
        return out, float(np.mean(rel)) if rel else 0.0
    if cls == "costs":
        rel = []
        for e in ev:
            f = float(rng.uniform(0.5, 1.5))
            rel.append(abs(f - 1.0))
            out.append(dataclasses.replace(
                e, cost_bias_r=float(getattr(e, "cost_bias_r", 0.0)) * f,
                cost_r=float(getattr(e, "cost_r", 0.0)) * f))
        return out, float(np.mean(rel)) if rel else 0.0
    return list(ev), 0.0


def perturb_probs(probs: Sequence[tuple[str, float]], rng: np.random.Generator,
                  n_obs: int) -> tuple[tuple[tuple[str, float], ...], float]:
    if not probs:
        return (), 0.0
    keys = [k for k, _ in probs]
    p = np.array([max(float(v), 1e-6) for _, v in probs])
    p = p / p.sum()
    q = rng.dirichlet(p * max(int(n_obs), 2))
    return tuple(zip(keys, (float(x) for x in q), strict=True)), float(np.abs(q - p).sum() / 2)


Solve = Callable[[Sequence[Any], Mapping[str, Any]], Mapping[str, float]]


def measure(ev: Sequence[Any], books: Mapping[str, Solve], *, seed: int = 0,
            draws: int = DRAWS, regime_probs: Sequence[tuple[str, float]] = (),
            regime_n_obs: int = 250, bounds: Mapping[str, float] | None = None,
            block: int = 5) -> dict[str, Any]:
    """Run every class against every book. `books[name](evidence, ctx)` returns a book; `ctx`
    carries `seed`, `regime_probs` and `bounds`, so each book reads the perturbed probability and
    capacity inputs too. Returns per book: per-class distance and elasticity, instability, the
    re-seed null, the excess, and the shadow authority flag for `A_allocator`."""
    base_ctx = {"seed": seed, "regime_probs": tuple(regime_probs), "bounds": dict(bounds or {})}
    out: dict[str, Any] = {"classes": list(CLASSES), "draws": int(draws), "books": {}}
    for name, solve in books.items():
        try:
            base = dict(solve(ev, base_ctx))
        except Exception as exc:                      # a book that cannot be built is named
            out["books"][name] = {"error": f"{type(exc).__name__}: {exc}"}
            continue
        per: dict[str, Any] = {}
        rng = np.random.default_rng(seed + 7919)
        for cls in CLASSES:
            ds, el = [], []
            for _ in range(int(draws)):
                ctx = dict(base_ctx)
                ev_p, rel = list(ev), 0.0
                if cls == "probabilities":
                    if not regime_probs:
                        break
                    ctx["regime_probs"], rel = perturb_probs(regime_probs, rng, regime_n_obs)
                elif cls == "capacity":
                    if not bounds:
                        break
                    f = rng.uniform(0.8, 1.2, size=len(bounds))
                    ctx["bounds"] = {k: float(v) * float(x)
                                     for (k, v), x in zip(bounds.items(), f, strict=True)}
                    rel = float(np.mean(np.abs(f - 1.0)))
                else:
                    ev_p, rel = perturb(ev, cls, rng, block=block)
                try:
                    d = distance(base, solve(ev_p, ctx))
                except Exception:
                    continue
                ds.append(d)
                el.append(d / rel if rel > 0 else float("nan"))
            if ds:
                fin = [x for x in el if math.isfinite(x)]
                per[cls] = {"distance": round(float(np.mean(ds)), 6),
                            "elasticity": round(float(np.mean(fin)), 6) if fin else None,
                            "n": len(ds)}
        try:
            null = distance(base, solve(ev, {**base_ctx, "seed": seed + 1}))
        except Exception:
            null = 0.0
        inst = float(np.mean([v["distance"] for v in per.values()])) if per else float("nan")
        out["books"][name] = {"per_class": per, "instability": round(inst, 6),
                              "reseed_null": round(null, 6),
                              "instability_excess": round(max(inst - null, 0.0), 6)
                              if math.isfinite(inst) else None}
    ex = {k: v.get("instability_excess") for k, v in out["books"].items()
          if isinstance(v.get("instability_excess"), (int, float))}
    a = ex.get("A_allocator")
    others = [v for k, v in ex.items() if k != "A_allocator"]
    med = float(np.median(others)) if others else None
    flag = bool(a is not None and others and a >= max(others) and med is not None
                and a >= AUTHORITY_RATIO * max(med, 1e-9))
    out["authority"] = {
        "would_lose_authority": flag, "enforced": False,
        "allocator_excess": a, "median_challenger_excess": med,
        "rule": (f"shadow: allocator's excess instability is the largest of every book AND >= "
                 f"{AUTHORITY_RATIO}x the median challenger's. Not enforced: Growth Governance "
                 "Rule 1 needs measured forward E[log W] before anything may remove authority.")}
    return out
