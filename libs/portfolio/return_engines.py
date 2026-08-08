"""RETURN-ENGINE ATTRIBUTION — where every euro came from, and how many bets it really was.

TWO QUESTIONS, ONE MODULE, BECAUSE THEY ARE THE SAME QUESTION ASKED FORWARD AND BACKWARD.

    §53 backward: this euro of P&L -- was it alpha, or was it the market going up?
    §58 forward:  these five strategies -- are they five bets, or one bet placed five times?

A desk that cannot answer the first will eventually report beta as skill and size it accordingly,
which is fine until the beta turns. A desk that cannot answer the second will believe it is
diversified while holding one position, which is fine until it is not. Both failures are invisible
in the good state and total in the bad one, and both are arithmetic rather than judgement.

**BETA IS NOT A DIRTY WORD HERE.** The specification is explicit that intentional directional
exposure is allowed to compete for capital on its merits. What is forbidden is calling it
something else. So `BETA_REGIME` is a first-class engine with its own row, and a strategy whose
return is 90% explained by market beta is reported as a beta engine with 10% alpha rather than
being killed -- it may still be the best use of capital, and that is the allocator's call, taken
with the composition visible.

**REVENUE THAT IS NOT TRADING P&L NEVER ENTERS.** Business income and self-issued token
mark-to-model are excluded by construction rather than by discipline: they have no engine to be
attributed to, and `attribute` raises on an unknown engine rather than silently bucketing it into
RESIDUAL. The benchmarked operator's public figures mix these freely, which is one of the reasons
the comparison in `libs/research/external_benchmark.py` has to be built, not read off.

**RESIDUAL IS A MEASUREMENT, NOT A DUMPING GROUND.** A large residual means the attribution model
is missing an engine, and the report says so in those words instead of letting the number sit in a
table looking like rounding.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

__all__ = [
    "ENGINES",
    "MAX_HEALTHY_RESIDUAL_SHARE",
    "EngineReturn",
    "attribute",
    "beta_share",
    "effective_engine_count",
    "summarise",
]

#: The complete attribution basis from §53. Every euro belongs to exactly one of these. Adding an
#: engine is a deliberate act: an open-ended list would let RESIDUAL be renamed rather than
#: explained.
ENGINES: tuple[str, ...] = (
    "INDEPENDENT_ALPHA",
    "BETA_REGIME",
    "MOMENTUM_SELECTION",
    "REBOUND_TIMING",
    "PARTICIPANT_FLOW",
    "EVENT_INTELLIGENCE",
    "PROTOCOL_CARRY",
    "PROTOCOL_TOKEN_BETA",
    "PREDICTION_MARKET",
    "EXECUTION",
    "INCENTIVE_REWARD",
    "COST",
    "FUNDING",
    "RESIDUAL",
)

#: Above this share of gross P&L, the residual is the finding. The attribution is then a
#: description of a minority of the money and must not be presented as an explanation.
MAX_HEALTHY_RESIDUAL_SHARE: float = 0.25


@dataclass(frozen=True)
class EngineReturn:
    """One engine's contribution over a period, with the return series that proves independence.

    `returns` is required for the §58 half of the module and optional for the §53 half. A desk that
    reports contributions without series can attribute P&L and CANNOT tell whether its engines are
    distinct, which is the more expensive of the two blindnesses.
    """

    engine: str
    #: Currency contribution over the period. Signed.
    pnl: float
    #: Per-period return series for this engine. Empty = independence UNMEASURED for this engine.
    returns: tuple[float, ...] = field(default_factory=tuple)
    #: Realised beta of this engine's returns to the market factor, when measured. None =
    #: unmeasured, which is NOT the same as zero and must never be rendered as zero.
    market_beta: float | None = None
    #: Fraction of this engine's variance explained by the market factor. None = unmeasured.
    r2_market: float | None = None

    def __post_init__(self) -> None:
        if self.engine not in ENGINES:
            raise ValueError(
                f"unknown return engine {self.engine!r}. The basis is closed on purpose: an "
                f"engine that is not one of {ENGINES} is either a missing engine that must be "
                "added deliberately, or it is not trading P&L at all -- business revenue and "
                "self-issued token marks have no engine here and must not acquire one")


def attribute(rows: list[EngineReturn], *, gross_pnl: float | None = None) -> dict[str, object]:
    """§53. Every euro to an engine, with the residual computed rather than assumed.

    `gross_pnl` is the independently-known total (from the accounting system, not from these rows).
    When supplied, anything the engines fail to explain lands in RESIDUAL and is reported as the
    finding it is. When absent, the rows are treated as complete and the report says so, because
    "the parts sum to the whole" is trivially true when the whole was defined as the sum.
    """
    by_engine: dict[str, float] = {}
    for r in rows:
        by_engine[r.engine] = by_engine.get(r.engine, 0.0) + r.pnl
    explained = sum(by_engine.values())
    residual_added = 0.0
    if gross_pnl is not None:
        residual_added = gross_pnl - explained
        by_engine["RESIDUAL"] = by_engine.get("RESIDUAL", 0.0) + residual_added
    total = gross_pnl if gross_pnl is not None else explained
    scale = sum(abs(v) for v in by_engine.values()) or 1.0
    residual_share = abs(by_engine.get("RESIDUAL", 0.0)) / scale
    return {
        "total_pnl": round(total, 2),
        "by_engine": {k: round(v, 2) for k, v in sorted(
            by_engine.items(), key=lambda kv: -abs(kv[1]))},
        "share_by_engine": {k: round(v / scale, 4) for k, v in by_engine.items()},
        "residual_share": round(residual_share, 4),
        "independently_reconciled": gross_pnl is not None,
        "finding": (
            f"RESIDUAL is {residual_share:.0%} of gross, above {MAX_HEALTHY_RESIDUAL_SHARE:.0%}. "
            "The attribution explains a minority of the money, so it is a description rather than "
            "an explanation and must not be cited as one -- an engine is missing"
            if residual_share > MAX_HEALTHY_RESIDUAL_SHARE else
            "" if gross_pnl is not None else
            "NOT RECONCILED against an independent total: the engines were summed to define the "
            "whole, so their agreement with it carries no information"),
    }


def beta_share(rows: list[EngineReturn]) -> tuple[float | None, str]:
    """Fraction of POSITIVE P&L that came from directional exposure rather than from edge.

    None when no engine reports a market beta, which is the honest answer and the common one.
    Beta engines are named explicitly rather than inferred from the r2, so an alpha engine that
    turns out to be 90% market is caught by `hidden_beta` below instead of being reclassified here.
    """
    beta_engines = {"BETA_REGIME", "PROTOCOL_TOKEN_BETA"}
    gains = [(r.engine, r.pnl) for r in rows if r.pnl > 0]
    if not gains:
        return None, "no positive P&L in the period -- beta share is undefined, not zero"
    total = sum(p for _, p in gains)
    b = sum(p for e, p in gains if e in beta_engines)
    return b / total, (
        f"{b / total:.0%} of gross gains came from declared directional engines. This is not a "
        "criticism: intentional beta is allowed to compete for capital. It is a requirement that "
        "it be labelled, because a beta return sized as if it were alpha is sized against the "
        "wrong covariance")


def hidden_beta(rows: list[EngineReturn]) -> list[str]:
    """Engines that claim to be alpha and behave like beta. §58's most expensive case.

    Threshold at r2 >= 0.5 -- half the variance of a supposedly independent engine explained by
    the market factor is not a nuance, it is a different engine.
    """
    out = []
    for r in rows:
        if r.engine in ("BETA_REGIME", "PROTOCOL_TOKEN_BETA", "COST", "FUNDING", "RESIDUAL"):
            continue
        if r.r2_market is not None and r.r2_market >= 0.5:
            out.append(f"{r.engine}: r2 to market {r.r2_market:.2f}, beta "
                       f"{'unmeasured' if r.market_beta is None else f'{r.market_beta:.2f}'} -- "
                       "declared independent, behaves as directional exposure")
    return out


def _corr(a: tuple[float, ...], b: tuple[float, ...]) -> float | None:
    n = min(len(a), len(b))
    if n < 3:
        return None
    x, y = a[:n], b[:n]
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y, strict=True))
    sxx = sum((xi - mx) ** 2 for xi in x)
    syy = sum((yi - my) ** 2 for yi in y)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def effective_engine_count(rows: list[EngineReturn]) -> tuple[float | None, str]:
    """§58. How many INDEPENDENT return engines the book actually contains.

    Uses the standard participation-ratio form on the average pairwise correlation::

        n_eff = n / (1 + (n-1) * rho_bar)

    At rho_bar = 0 this returns n -- five uncorrelated engines are five bets. At rho_bar = 1 it
    returns 1, which is the correct and uncomfortable answer for five strategies that are all long
    crypto: they are one position wearing five names, and the nominal count is the number the
    desk would otherwise put on a dashboard.

    None when fewer than two engines carry return series, and the reason says which -- an
    unmeasured independence claim must never render as a healthy count.
    """
    with_series = [r for r in rows if len(r.returns) >= 3]
    n = len(with_series)
    if n < 2:
        return None, (
            f"{n} engine(s) carry a return series, so independence is UNMEASURED. The nominal "
            f"count is {len(rows)} and nothing here supports treating it as a count of BETS")
    cors: list[float] = []
    for i in range(n):
        for j in range(i + 1, n):
            c = _corr(with_series[i].returns, with_series[j].returns)
            if c is not None:
                cors.append(abs(c))
    if not cors:
        return None, "return series present but pairwise correlation was not computable"
    rho = sum(cors) / len(cors)
    n_eff = n / (1.0 + (n - 1) * rho)
    return n_eff, (
        f"{n} nominal engine(s), mean |pairwise rho| {rho:.2f} => {n_eff:.2f} EFFECTIVE "
        f"independent engine(s)" + (
            ". The book is substantially one bet placed several times, and any diversification "
            "credit taken on the nominal count is unearned" if n_eff < 0.5 * n else
            ". The engines are behaving as distinct return sources"))


def summarise(rows: list[EngineReturn], *, gross_pnl: float | None = None) -> dict[str, object]:
    """Report shape for `data/return_engine_attribution.json`."""
    if not rows:
        return {"engines": 0, "headline": (
            "no engine returns recorded -- P&L attribution is UNMEASURED, so every euro this "
            "desk has made or lost is currently unexplained. That is the state in which beta "
            "gets reported as alpha")}
    att = attribute(rows, gross_pnl=gross_pnl)
    bshare, bwhy = beta_share(rows)
    n_eff, nwhy = effective_engine_count(rows)
    hidden = hidden_beta(rows)
    head = []
    if att["finding"]:
        head.append(str(att["finding"]))
    if hidden:
        head.append(f"{len(hidden)} engine(s) declared independent behave as market beta")
    if n_eff is not None:
        head.append(f"{len(rows)} nominal engines -> {n_eff:.2f} effective")
    if bshare is not None:
        head.append(f"{bshare:.0%} of gains from declared beta")
    return {
        "engines": len(rows),
        "attribution": att,
        "beta_share_of_gains": None if bshare is None else round(bshare, 4),
        "beta_share_note": bwhy,
        "nominal_engine_count": len(rows),
        "effective_engine_count": None if n_eff is None else round(n_eff, 3),
        "effective_engine_note": nwhy,
        "hidden_beta": hidden,
        "headline": "; ".join(head) if head else "attribution measured, no finding",
        "note": ("Business revenue and self-issued token mark-to-model cannot be represented in "
                 "this basis and constructing an EngineReturn for them raises. Beta is a "
                 "first-class engine allowed to compete for capital -- what is forbidden is "
                 "attributing it to alpha. RESIDUAL above "
                 f"{MAX_HEALTHY_RESIDUAL_SHARE:.0%} of gross means an engine is missing."),
    }
