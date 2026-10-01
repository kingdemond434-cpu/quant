"""RISK AS HARD CONSTRAINTS INSIDE THE E[log W] SOLVE (Tier-1 audit item #6, 2026-09-29).

    maximise   E_posterior[ log W_T ]                         (the desk's objective, unchanged)
    subject to P(ruin)            < eps_ruin
               P(drawdown stop)   < eps_stop                  (the principal's 35% pain limit)
               P(broker stop-out) < eps_stop                  (margin level < the venue's SO)
               margin use         <= max_margin_use
               CVaR_alpha(log W_T) >= log(1 - tail_max_loss)  (the tail, not the mean)
               heat(symbol)/heat  <= max_symbol_share         (concentration)
               heat(class)/heat   <= max_class_share
               h_i                <= liquidity_cap_i          (capacity, where it is MEASURED)
               floor <= sum h <= ceiling                      (the heat law, flat 20% floor)

WHY A SECOND SOLVE AND NOT A SECOND RULE. The allocator already prices ruin and stop-out on its
posterior paths (`posterior_growth.solve`) and feeds the measured broker margin clause into its
survival envelope by default (P13, LANDED in #53; `desks/mt5/data/MARGIN_CLAUSE_DISABLED` reverts
it). What no organ does is solve the book
with EVERY risk clause as a constraint at once and say which one binds and what it costs in
E[log W]. That is this module: a pure function of a path tensor and a spec. It sizes nothing.

POSTERIOR, NOT POINT ESTIMATES. The paths are the allocator's own world population
(`robust_elog.Worlds`: posterior mean draws, per-sleeve decay, crisis overlay with a common factor
so correlations converge in the tail, cost uncertainty) cut into T-day blocks by
`posterior_growth.sample_paths`. Tail dependence is therefore the crisis worlds' dependence, the
same one the live allocator is stressed at, not a Gaussian copula invented here.

TWO-SIDED. The constrained book is solved from scratch between the floor and the ceiling. When
the constraints are slack it may carry MORE heat than today's book, and the report says so; a
constraint that binds is billed in dE[log W] against the unconstrained solve on identical paths,
which is the missed-growth line the growth governance requires of every restraint.

AN UNMEASURED CLAUSE IS NOT A SATISFIED ONE. A clause whose input is absent (no margin reading,
no capacity ceiling) is recorded as UNMEASURED and does not constrain the solve -- it is never
reported as slack, because slack is a measurement.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from libs.portfolio.posterior_growth import (
    EPS_RUIN,
    EPS_STOP,
    STOPOUT_DD,
    PosteriorPaths,
    compare,
    simulate,
    solve,
)

__all__ = ["FEEDS_LIVE", "ConstraintSpec", "evaluate", "solve_constrained"]

#: THE SWITCH. The constrained book is a MEASURED SHADOW: nothing on the money path reads it.
#: Feeding it into live sizing is the principal's decision (it can move heat in either direction
#: and it changes which sleeves the gateway funds). Flipping this does nothing by itself -- no
#: consumer exists -- and `desks/mt5/tests/test_constrained_book.py` pins it False so it cannot be
#: flipped by accident.
FEEDS_LIVE = False


@dataclass(frozen=True)
class ConstraintSpec:
    """Every bound is a stated belief with its provenance; `None` means UNMEASURED, not slack."""

    eps_ruin: float = EPS_RUIN
    eps_stop: float = EPS_STOP
    #: The principal's stated pain limit (MAX_DRAWDOWN_TOLERANCE), as posterior_growth uses it.
    stopout_dd: float = STOPOUT_DD
    #: Account margin as a fraction of equity per unit of heat, measured by pf_allocator's
    #: `margin_use_from` from the live terminal. None = UNMEASURED (a flat book reads 0/0).
    margin_per_heat: float | None = None
    #: The venue's stop-out margin level as a fraction (0.5 = 50%). None = UNMEASURED.
    stop_out_level: float | None = None
    #: Ceiling on margin use as a fraction of equity (pf_allocator._MAX_MARGIN_USE).
    max_margin_use: float | None = None
    #: CVaR tail over the horizon: the mean of the worst `cvar_alpha` of T-day log wealth must be
    #: no worse than log(1 - tail_max_loss).
    cvar_alpha: float = 0.05
    tail_max_loss: float = 0.20
    #: Concentration, as shares of total heat. The book is one venue and mostly one metal, so
    #: these are the clauses most likely to bind, and binding is what they are here to show.
    max_symbol_share: float = 0.60
    max_class_share: float = 0.80
    #: Per-sleeve liquidity ceiling in heat, where capacity is MEASURED. Absent = UNMEASURED.
    liquidity_cap: Mapping[str, float] = field(default_factory=dict)
    #: The heat law: flat floor, growth free to the ceiling.
    floor: float = 0.20
    ceiling: float = 0.30

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["liquidity_cap"] = {k: round(float(v), 6) for k, v in self.liquidity_cap.items()}
        return d


def _vec(book: Mapping[str, float], names: Sequence[str]) -> np.ndarray:
    return np.array([max(0.0, float(book.get(n, 0.0) or 0.0)) for n in names], dtype=float)


def _groups(names: Sequence[str], key: Mapping[str, str]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for i, n in enumerate(names):
        g = str(key.get(n) or "")
        if g:
            out.setdefault(g, []).append(i)
    return out


def _cvar(x: np.ndarray, alpha: float) -> float:
    """Mean of the worst `alpha` share of `x`, -inf when any of that tail is -inf (ruin)."""
    if x.size == 0:
        return float("nan")
    k = max(1, math.ceil(alpha * x.size))
    worst = np.sort(x)[:k]
    return float(worst.mean()) if np.all(np.isfinite(worst)) else float("-inf")


def _margin_stop_prob(paths: PosteriorPaths, h: np.ndarray, spec: ConstraintSpec) -> float | None:
    """P(the venue closes the book): equity / margin falls below the stop-out level.

    Margin is set when the book opens (per-lot, so proportional to heat): m = margin_per_heat * H
    of the starting equity. The venue stops out when W_t / m < SO, i.e. log W_t < log(SO * m).
    """
    if spec.margin_per_heat is None or spec.stop_out_level is None:
        return None
    total = float(h.sum())
    m = spec.margin_per_heat * total
    if m <= 0:
        return 0.0
    thresh = spec.stop_out_level * m
    if thresh >= 1.0:
        return 1.0
    port = np.einsum("mtn,n->mt", paths.r, h)
    x = np.maximum(1.0 + port, 1e-12)
    cum = np.cumsum(np.log(x), axis=1)
    return float((cum.min(axis=1) <= math.log(thresh)).mean())


def evaluate(paths: PosteriorPaths, book: Mapping[str, float] | np.ndarray, spec: ConstraintSpec,
             *, symbol_of: Mapping[str, str], class_of: Mapping[str, str],
             h_prev: Mapping[str, float] | None = None) -> dict[str, Any]:
    """Every constraint measured on one book, on the given paths, with its verdict."""
    names = list(paths.names)
    h = np.asarray(book, dtype=float) if isinstance(book, np.ndarray) else _vec(book, names)
    total = float(h.sum())
    out = simulate(paths, h, h_prev, stopout_dd=spec.stopout_dd)
    cvar = _cvar(out.logw, spec.cvar_alpha)
    clauses: dict[str, dict[str, Any]] = {}

    def clause(name: str, value: float | None, bound: float | None, ok: bool | None,
               why: str) -> None:
        status = ("UNMEASURED" if ok is None else ("SATISFIED" if ok else "VIOLATED"))
        clauses[name] = {"status": status,
                         "value": (None if value is None or not math.isfinite(value)
                                   else round(float(value), 6)),
                         "bound": None if bound is None else round(float(bound), 6),
                         "why": why}

    clause("ruin", out.p_ruin, spec.eps_ruin, out.p_ruin < spec.eps_ruin,
           "P(a sampled day takes the book to -100%)")
    clause("drawdown_stop", out.p_stopout, spec.eps_stop, out.p_stopout < spec.eps_stop,
           f"P(wealth path falls {spec.stopout_dd:.0%} below its start within the horizon)")
    pm = _margin_stop_prob(paths, h, spec)
    clause("broker_stop_out", pm, spec.eps_stop, None if pm is None else pm < spec.eps_stop,
           ("P(equity/margin falls below the venue's stop-out level)" if pm is not None else
            "UNMEASURED: no margin-per-heat reading or no stop-out level from the terminal"))
    mu = (None if spec.margin_per_heat is None else spec.margin_per_heat * total)
    clause("margin_use", mu, spec.max_margin_use,
           None if (mu is None or spec.max_margin_use is None) else mu <= spec.max_margin_use,
           ("margin as a fraction of equity at this heat" if mu is not None else
            "UNMEASURED: the book deployed no margin when last read (0/0 is not a reading)"))
    tail_bound = math.log(max(1e-12, 1.0 - spec.tail_max_loss))
    clause("tail_cvar", cvar, tail_bound, bool(cvar >= tail_bound),
           f"mean of the worst {spec.cvar_alpha:.0%} of {paths.horizon}-day log wealth")
    shares: dict[str, dict[str, float]] = {}
    for label, key, cap in (("symbol", symbol_of, spec.max_symbol_share),
                            ("asset_class", class_of, spec.max_class_share)):
        grp = _groups(names, key)
        sh = ({g: float(h[idx].sum()) / total for g, idx in grp.items()} if total > 0 else {})
        shares[label] = {g: round(v, 6) for g, v in sorted(sh.items(), key=lambda t: -t[1])}
        worst = max(sh.values(), default=0.0)
        n_unmapped = sum(1 for n in names if not key.get(n))
        clause(f"concentration_{label}", worst, cap,
               None if not grp else worst <= cap + 1e-9,
               (f"largest {label} share of total heat; {n_unmapped} sleeve(s) carry no {label}"
                if grp else f"UNMEASURED: no sleeve could be mapped to a {label}"))
    if spec.liquidity_cap:
        excess = {n: float(h[i]) - float(spec.liquidity_cap[n]) for i, n in enumerate(names)
                  if n in spec.liquidity_cap and h[i] > float(spec.liquidity_cap[n]) + 1e-9}
        clause("liquidity", max(excess.values(), default=0.0), 0.0, not excess,
               f"heat above the measured capacity ceiling on {len(excess)} sleeve(s)")
    else:
        clause("liquidity", None, None, None,
               "UNMEASURED: no sleeve carries a MEASURED capacity ceiling (market impact needs "
               "realised fills)")
    clause("execution_feasibility", None, None, None,
           "UNMEASURED: min-lot feasibility per sleeve needs the venue's volume_min at the "
           "sleeve's stop distance, which no artifact publishes per sleeve")
    violated = sorted(k for k, v in clauses.items() if v["status"] == "VIOLATED")
    return {
        "total_heat": round(total, 6),
        "elogw_per_day": (None if not math.isfinite(out.elogw_per_day)
                          else round(out.elogw_per_day, 8)),
        "elogw_p10": (None if not math.isfinite(out.quantile_per_day(0.10))
                      else round(out.quantile_per_day(0.10), 8)),
        "clauses": clauses, "shares": shares, "violated": violated,
        "feasible": not violated,
        "n_unmeasured": sum(1 for v in clauses.values() if v["status"] == "UNMEASURED"),
    }


def _largest_scale(ok: Callable[[float], bool], lo: float, hi: float) -> float:
    if ok(hi):
        return hi
    if not ok(lo):
        return lo
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if ok(mid):
            lo = mid
        else:
            hi = mid
    return lo


def solve_constrained(paths: PosteriorPaths, spec: ConstraintSpec, *,
                      symbol_of: Mapping[str, str], class_of: Mapping[str, str],
                      h_prev: Mapping[str, float] | None = None, rounds: int = 6,
                      iterations: int = 200) -> dict[str, Any]:
    """The book that maximises posterior E[log W] with every MEASURED clause as a constraint.

    Order: the per-sleeve caps (liquidity) and the margin-use ceiling shape the feasible set;
    `posterior_growth.solve` handles ruin and the drawdown stop inside the heat band; the group
    shares are enforced by tightening member caps and re-solving (so freed heat is re-placed by
    marginal growth, not dropped); the tail and broker stop-out clauses are enforced last by the
    largest feasible scale, never below the floor -- a clause that cannot be met at the floor is
    reported as `violated_at_floor`, because only the ruin guard may go below the heat law.
    """
    names = list(paths.names)
    n = len(names)
    ceiling = float(spec.ceiling)
    notes: list[str] = []
    if spec.margin_per_heat and spec.max_margin_use:
        m_ceiling = float(spec.max_margin_use) / float(spec.margin_per_heat)
        if m_ceiling < ceiling:
            notes.append(f"margin use caps total heat at {m_ceiling:.4f}")
            ceiling = max(float(spec.floor), m_ceiling)
    ub = np.full(n, ceiling)
    for i, nm in enumerate(names):
        if nm in spec.liquidity_cap:
            ub[i] = min(ub[i], max(0.0, float(spec.liquidity_cap[nm])))
    free = solve(paths=paths, h_prev=h_prev, floor=spec.floor, ceiling=float(spec.ceiling),
                 eps_ruin=spec.eps_ruin, eps_stop=spec.eps_stop, stopout_dd=spec.stopout_dd,
                 iterations=iterations)
    book = free
    binding: list[str] = []
    for _ in range(max(1, rounds)):
        book = solve(paths=paths, h_prev=h_prev, floor=spec.floor, ceiling=ceiling,
                     caps={nm: float(ub[i]) for i, nm in enumerate(names)},
                     eps_ruin=spec.eps_ruin, eps_stop=spec.eps_stop,
                     stopout_dd=spec.stopout_dd, iterations=iterations)
        h = _vec(book.h, names)
        total = float(h.sum())
        tightened = False
        for label, key, cap in (("symbol", symbol_of, spec.max_symbol_share),
                                ("asset_class", class_of, spec.max_class_share)):
            for g, idx in _groups(names, key).items():
                if total <= 0:
                    continue
                share = float(h[idx].sum()) / total
                if share > cap + 1e-6:
                    scale = cap * total / float(h[idx].sum())
                    for i in idx:
                        ub[i] = min(ub[i], h[i] * scale)
                    tightened = True
                    tag = f"concentration_{label}:{g}"
                    if tag not in binding:
                        binding.append(tag)
        if not tightened:
            break
    h = _vec(book.h, names)
    if book.binding in ("stopout_guard", "ruin_guard", "cap"):
        binding.append(book.binding)
    # The tail and the broker stop-out: largest scale that satisfies both, floored at the law.
    total = float(h.sum())
    tail_bound = math.log(max(1e-12, 1.0 - spec.tail_max_loss))

    def _ok(s: float) -> bool:
        out = simulate(paths, s * h, h_prev, stopout_dd=spec.stopout_dd)
        if _cvar(out.logw, spec.cvar_alpha) < tail_bound:
            return False
        pm = _margin_stop_prob(paths, s * h, spec)
        return pm is None or pm < spec.eps_stop

    violated_at_floor: list[str] = []
    if total > 0 and not _ok(1.0):
        s_lo = min(1.0, float(spec.floor) / total)
        s = _largest_scale(_ok, s_lo, 1.0)
        if not _ok(s):
            violated_at_floor.append("tail_or_broker_stop_out")
            notes.append("tail / broker stop-out clause cannot be met at the heat floor; the "
                         "floor is held and the breach reported")
        if s < 1.0 - 1e-12:
            h = s * h
            binding.append("tail_or_broker_stop_out")
            notes.append(f"tail / broker stop-out scaled the book by {s:.4f}")
    constrained = {nm: float(h[i]) for i, nm in enumerate(names) if h[i] > 1e-7}
    try:
        cost_of_constraints = compare(constrained, free.h, paths, h_prev=h_prev, n_boot=500)
    except Exception as exc:  # the contest is a report; its failure never loses the book
        cost_of_constraints = {"error": f"{type(exc).__name__}: {exc}"}
    return {
        "book": {k: round(v, 6) for k, v in sorted(constrained.items(), key=lambda t: -t[1])},
        "total_heat": round(float(h.sum()), 6),
        "unconstrained_total_heat": round(float(free.total_heat), 6),
        "unconstrained_book": {k: round(v, 6) for k, v in sorted(free.h.items(),
                                                                  key=lambda t: -t[1])
                               if v > 1e-7},
        "binding": binding or ["none"],
        "violated_at_floor": violated_at_floor,
        "cost_of_constraints_vs_unconstrained": cost_of_constraints,
        "notes": notes,
    }
