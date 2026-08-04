"""ROBUST KELLY, THE SIGNIFICANCE GATE, AND NON-DESTRUCTIVE COEXISTENCE.

ROBUST KELLY IS MANDATORY, NOT PERMITTED. Full Kelly is growth-optimal only when the edge is known
EXACTLY. Every edge this desk will ever have is estimated, from a finite sample, by a model that
might be wrong, executed at a venue that might behave differently tomorrow. Kelly's penalty curve
is asymmetric -- growth falls off a cliff on the overbet side and merely slopes on the underbet
side -- so betting naive Kelly on an estimated edge has LOWER expected log growth than betting the
shrunk fraction. Shrinkage here is therefore not caution and must never be argued about as though
it were: it IS the max-E[log W] bet under parameter uncertainty. Anyone proposing to remove it is
proposing to lower expected growth.

    f = f_Kelly x gamma_estimation x gamma_regime x gamma_execution x gamma_model

Four independent sources, multiplied because they compound: an edge estimated from a short sample
AND measured in one regime AND executed through an unproven path is far more uncertain than any
one of those alone. The estimation term delegates to libs/risk/kelly_shrink, which already derives
it from Lo (2002) -- re-deriving it here would create two sources of truth for one number, and the
one that drifts is always the copy.

THE SIGNIFICANCE GATE. If the edge is not distinguishable from zero at 80% confidence, allocation
is ZERO -- not small, zero. A position sized on an edge that might be nothing is a position whose
expected log contribution is negative once costs are counted, and "small enough not to matter" is
how a book fills with them.

NON-DESTRUCTIVE COEXISTENCE. Systematic and discretionary, every sleeve, every execution engine
are optimised JOINTLY. A strategy is judged by its MARGINAL contribution to the portfolio, never
by its standalone record:

    MC_i = Ê[log W | S] - Ê[log W | S \\ {i}]

A weaker standalone strategy that raises portfolio compounding through diversification BEATS a
stronger one that raises correlation. And when two families interact badly the answer is
orthogonalisation first -- execution separation, timing separation, capital separation, signal
orthogonalisation -- and retirement only after those fail. The desk expands orthogonality before
it reduces opportunity.

Depends only on libs/risk/kelly_shrink and the standard library.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from libs.doctrine.estimate import ADMIT_Z, Estimate
from libs.risk.kelly_shrink import shrink_fraction

__all__ = [
    "SIGNIFICANCE_Z",
    "coexistence_verdict",
    "concentration_cap",
    "deploy_or_wait",
    "dynamic_risk_budget",
    "marginal_contribution",
    "portfolio_entropy",
    "robust_kelly",
    "significance_gate",
]

#: One-sided 80%. An edge below this is allocated ZERO, not a token size.
SIGNIFICANCE_Z = 1.28

#: Ceiling on any single sleeve as a fraction of capital, scaled by how stable its regime is.
#: A sleeve whose regime is unstable earns a smaller ceiling automatically.
_CONCENTRATION_BASE = 0.5


def robust_kelly(kelly: float, *, sharpe_ann: float, n_days: float,
                 regime_stability: float = 1.0,
                 execution_confidence: float = 1.0,
                 model_confidence: float = 1.0) -> dict[str, Any]:
    """f = f_Kelly x gamma_estimation x gamma_regime x gamma_execution x gamma_model.

    MULTIPLICATIVE, because the uncertainties compound rather than average. An edge measured over
    20 days, in one regime, through an execution path that has never traded is not "somewhat
    uncertain" -- it is uncertain three times over, and an additive penalty would let two strong
    factors mask a fatal third.

    Every gamma is reported separately so the binding one is visible. That matters operationally:
    if gamma_execution is 0.4 the fix is a week of execution work, not more backtesting, and a
    single blended shrink factor hides which week to spend.
    """
    g_est = shrink_fraction(sharpe_ann, n_days)
    g_reg = max(0.0, min(1.0, float(regime_stability)))
    g_exe = max(0.0, min(1.0, float(execution_confidence)))
    g_mod = max(0.0, min(1.0, float(model_confidence)))
    gamma = g_est * g_reg * g_exe * g_mod
    gammas = {"estimation": round(g_est, 4), "regime": round(g_reg, 4),
              "execution": round(g_exe, 4), "model": round(g_mod, 4)}
    binding = min(gammas, key=lambda k: gammas[k])
    return {
        "kelly": round(float(kelly), 6),
        "gammas": gammas,
        "gamma": round(gamma, 6),
        "fraction": round(float(kelly) * gamma, 6),
        "binding_uncertainty": binding,
        "note": (f"'{binding}' is the binding uncertainty at {gammas[binding]}. Shrinkage is NOT "
                 "conservatism -- Kelly's penalty is asymmetric, so the shrunk fraction has "
                 "HIGHER expected log growth than naive Kelly on an estimated edge. Removing it "
                 "lowers expected growth."),
    }


def significance_gate(mu: float, se: float, *, z: float = SIGNIFICANCE_Z) -> dict[str, Any]:
    """Allocation is ZERO unless the edge clears z standard errors. Not small -- zero.

    "Size it small to keep learning" is the argument this refuses, and it is a real argument with
    a real answer: learning is what the forward-validation clock and the research budget are for,
    and neither of those risks capital on an edge that might be nothing. A live position sized on
    an indistinguishable edge pays full costs for an expected contribution that is negative once
    they are counted.
    """
    threshold = z * abs(float(se))
    ok = abs(float(mu)) > threshold
    return {
        "mu": round(float(mu), 6), "se": round(float(se), 6),
        "threshold": round(threshold, 6), "allocate": ok,
        "note": ("edge is distinguishable from zero at "
                 f"{int((1 - 0.5 * (1 - math.erf(z / math.sqrt(2)))) * 100)}% confidence"
                 if ok else
                 "edge NOT distinguishable from zero -- allocation is ZERO, not small. A "
                 "position on an edge that might be nothing pays full costs for a negative "
                 "expected log contribution; keep learning on the research clock instead."),
    }


def concentration_cap(regime_stability: float, *, base: float = _CONCENTRATION_BASE) -> float:
    """Maximum fraction of capital in one sleeve, scaled by regime stability.

    An unstable regime earns a smaller ceiling automatically rather than by anybody's judgement.
    The cap is not a growth limit but a correlation limit: concentration into a single structural
    regime is the failure that a strong Sharpe cannot save you from, because the whole book is
    one bet on that regime persisting.
    """
    return round(base * max(0.0, min(1.0, float(regime_stability))), 4)


def marginal_contribution(with_all: Estimate, without_i: Estimate,
                          name: str = "") -> dict[str, Any]:
    """MC_i = Ê[log W | S] - Ê[log W | S\\{i}]. Standalone performance is not the question.

    A weaker standalone strategy that raises portfolio compounding through diversification is
    PREFERRED over a stronger one that raises correlation. That inversion is the entire point:
    ranking sleeves by their own Sharpe builds a book of correlated winners, which is one bet
    wearing five names.
    """
    mc = float(with_all.value) - float(without_i.value)
    se = math.sqrt(float(with_all.se) ** 2 + float(without_i.se) ** 2)
    est = Estimate(mc, se, min(with_all.n, without_i.n), name or "MC")
    return {
        "name": name, "mc": round(mc, 6), "se": round(se, 6),
        "significant_positive": est.significant_positive(ADMIT_Z),
        "significant_negative": est.significant_negative(),
        "note": ("adds to portfolio compounding" if est.significant_positive(ADMIT_Z) else
                 "SUBTRACTS from portfolio compounding -- orthogonalise before retiring"
                 if est.significant_negative() else
                 "contribution not distinguishable from zero; keep and instrument, since "
                 "retiring on an indistinguishable estimate churns useful sleeves"),
    }


def coexistence_verdict(contributions: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    """Whether the families can coexist, and what to do FIRST when they cannot.

    ORTHOGONALISATION BEFORE RETIREMENT, in that order and without exception. When systematic and
    discretionary interact badly the loss is usually in the INTERACTION -- they trade the same
    liquidity, at the same moment, into the same book -- and separating execution, timing or
    capital recovers both. Retiring one recovers the interaction loss and gives up the strategy,
    which is strictly worse whenever separation was available.
    """
    harmful = sorted(k for k, v in contributions.items() if v.get("significant_negative"))
    unclear = sorted(k for k, v in contributions.items()
                     if not v.get("significant_negative") and not v.get("significant_positive"))
    return {
        "harmful": harmful,
        "indistinguishable": unclear,
        "verdict": "COEXISTENCE HARMFUL" if harmful else "COEXISTENCE NON-DESTRUCTIVE",
        "remedy_order": ["execution separation", "timing separation", "capital separation",
                         "signal orthogonalisation", "risk orthogonalisation", "retirement"],
        "note": ("expand orthogonality BEFORE reducing opportunity. Retiring a sleeve recovers "
                 "the interaction loss and gives up the strategy -- strictly worse than "
                 "separation whenever separation is available." if harmful else
                 "no family is significantly reducing another's contribution; both run at "
                 "maximum feasible size"),
    }


def portfolio_entropy(weights: Mapping[str, float]) -> dict[str, Any]:
    """Shannon entropy of the capital split -- how many INDEPENDENT bets are really on.

    Maximised subject to Ê[log W], never instead of it. The purpose is to discourage
    concentration into one structural market regime, which is the exposure that a strong
    backtest is least able to warn about: every sleeve looks different and all five stop working
    on the same morning.
    """
    vals = [max(0.0, float(v)) for v in weights.values()]
    tot = sum(vals)
    if tot <= 0:
        return {"entropy": 0.0, "effective_bets": 0.0,
                "note": "no capital allocated -- entropy undefined, reported as zero"}
    ps = [v / tot for v in vals if v > 0]
    h = -sum(p * math.log(p) for p in ps)
    return {
        "entropy": round(h, 4),
        "effective_bets": round(math.exp(h), 3),
        "n_sleeves": len(ps),
        "note": (f"{math.exp(h):.2f} effective independent bets across {len(ps)} sleeves. "
                 "Concentration into one structural regime is the exposure a strong backtest is "
                 "least able to warn about -- every sleeve looks different and they all stop "
                 "working on the same morning."),
    }


def dynamic_risk_budget(*, calibration_brier: float | None, regime_stability: float,
                        portfolio_correlation: float, execution_quality: float) -> dict[str, Any]:
    """R_t = f(calibration, regime stability, correlation, execution quality).

    Risk is an OPTIMISED VARIABLE, not a static limit. A fixed percentage is wrong in both
    directions at once: too large when calibration is poor and the regime is unstable, and too
    small exactly when the desk has earned the right to press. A static limit is therefore not
    the safe choice -- it is the choice that is wrong all the time, in whichever direction the
    world happens to have moved.

    Returned as a MULTIPLIER on the base budget rather than an absolute number, so it composes
    with the survival rails instead of competing with them. The rails remain the floor; this
    never raises anything through them.
    """
    from libs.doctrine.estimate import LAMBDA_MAX, uncertainty_penalty
    cal = 1.0 - (uncertainty_penalty(calibration_brier) - 0.25) / (LAMBDA_MAX - 0.25)
    reg = max(0.0, min(1.0, float(regime_stability)))
    cor = 1.0 - max(0.0, min(1.0, abs(float(portfolio_correlation))))
    exe = max(0.0, min(1.0, float(execution_quality)))
    parts = {"calibration": round(cal, 4), "regime": round(reg, 4),
             "diversification": round(cor, 4), "execution": round(exe, 4)}
    mult = cal * reg * cor * exe
    binding = min(parts, key=lambda k: parts[k])
    return {
        "components": parts,
        "multiplier": round(mult, 4),
        "binding": binding,
        "note": (f"'{binding}' binds at {parts[binding]}. This MULTIPLIES the base budget and "
                 "never raises anything through a survival rail -- the rails stay the floor. "
                 "Improving the binding component is a direct, measurable growth action."),
    }


def deploy_or_wait(e_log_w_deploy: Estimate, e_log_w_wait: Estimate,
                   execution_cost: float = 0.0) -> dict[str, Any]:
    """Deploy iff Ê[log W | deploy] - C_exec > Ê[log W | wait]. Cash is a position.

    WAITING IS NOT NEUTRAL and this is where most desks lose quietly. Holding cash is a short
    position on every edge the desk owns, and it has an expected cost that nobody books because
    nothing visibly happens. Making `wait` an explicit term with its own estimate is what stops
    "we'll deploy when things are clearer" from being free.

    Execution cost is subtracted from the DEPLOY side, not bolted on afterwards, because slippage,
    impact and capacity limits are real reductions in the edge rather than an administrative fee.
    """
    net = float(e_log_w_deploy.value) - float(execution_cost)
    gap = net - float(e_log_w_wait.value)
    se = math.sqrt(float(e_log_w_deploy.se) ** 2 + float(e_log_w_wait.se) ** 2)
    est = Estimate(gap, se, min(e_log_w_deploy.n, e_log_w_wait.n), "deploy-vs-wait")
    return {
        "deploy_net": round(net, 6),
        "wait": round(float(e_log_w_wait.value), 6),
        "gap": round(gap, 6),
        "deploy": est.significant_positive(ADMIT_Z),
        "note": ("deploy -- net of execution cost this beats holding cash with evidence"
                 if est.significant_positive(ADMIT_Z) else
                 "WAIT, and book the cost: holding cash is a short position on every edge the "
                 "desk owns. Nothing visibly happens while waiting, which is exactly why the "
                 "cost has to be stated rather than noticed."),
    }
