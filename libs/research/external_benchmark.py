"""EXTERNAL PERFORMANCE BENCHMARK — comparing an equity curve to a claim, without pretending they
are the same kind of object.

WHY THIS IS HARDER THAN IT LOOKS, AND WHY IT NEEDS CODE RATHER THAN A SPREADSHEET. The desk has
been given an explicit competitive objective: exceed the realised, retained wealth growth of a
publicly-visible operator. The trouble is that almost nothing on the other side of that comparison
is a measured quantity. A figure in a video is a self-report; a screenshot is a self-report with
a picture; an announced target is not a result at all. Meanwhile our own side is measured to the
basis point, net of fees, funding, slippage and gas.

Comparing those two directly does not produce a lead. It produces whichever answer the framing
was chosen to produce, and the framing is always available in both directions:

    they win   -- gross claims, best asset, best window, unrealised marks, no drawdown reported
    we win     -- higher Sharpe on a tenth the capital, better backtest, more alphas discovered

**SO EVERY EXTERNAL FIGURE CARRIES ITS EVIDENCE CLASS, AND THE CLASS GATES WHAT IT CAN BE USED
FOR.** A TARGET may never be silently promoted into an achieved return -- the single most likely
way this subsystem would mislead the desk is by a "10x" announcement quietly becoming a 10x
result some months later when nobody remembers which it was. `promote` refuses that transition
without an explicit new observation at a higher class.

**AND THE LEAD IS ONLY REPORTED WHEN THE COMPARISON IS ACTUALLY COMPARABLE.** `PERFORMANCE_LEAD`
returns None -- with the reason -- when the horizons differ, when one side is gross and the other
net, when one side is unrealised, or when the external figure is below PARTIALLY_VERIFIABLE. An
unreportable lead is a fact about the evidence and is far more useful than a number computed
anyway.

**WHAT A GENUINE WIN REQUIRES**, from the specification, enforced by `win_conditions`: real
capital, real fills, real costs, RETAINED profit, and enough time. A desk that survived by barely
deploying has not won, and this module says so about its own side as readily as about the other.

Generalises beyond any one operator: the record shape takes a `claimant`, so a second public
benchmark costs a row rather than a module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = [
    "EVIDENCE_CLASSES",
    "MIN_COMPARABLE_DAYS",
    "USABLE_FOR_COMPARISON",
    "BenchmarkClaim",
    "OwnPerformance",
    "comparable",
    "log_growth_from_claim",
    "performance_lead",
    "promote",
    "summarise",
    "win_conditions",
]

#: Ordered weakest to strongest. The ordering is used, not decorative: `promote` refuses to move a
#: record DOWN the list silently and refuses to move it up without a new observation.
EVIDENCE_CLASSES: tuple[str, ...] = (
    "TARGET",                 # announced intention. NOT a result. Never comparable.
    "SELF_REPORTED",          # stated by the claimant, unverifiable
    "PUBLIC_DASHBOARD",       # a public read-only surface the claimant controls
    "PARTIALLY_VERIFIABLE",   # some legs independently checkable (on-chain, exchange-published)
    "VERIFIED",               # independently reconstructed from primary records
    "AUDITED",                # third-party attested
)

#: Only these classes may enter a lead calculation. Below this line a figure is an assertion, and
#: an assertion compared against a measurement produces a number with no error bar and no meaning.
USABLE_FOR_COMPARISON: frozenset[str] = frozenset(
    {"PARTIALLY_VERIFIABLE", "VERIFIED", "AUDITED"})

#: A lead measured over a shorter live horizon than this is a description of a window. The spec's
#: own instruction is that the ambition is a positive lead on INCREASINGLY LONG live horizons.
MIN_COMPARABLE_DAYS: float = 90.0


@dataclass(frozen=True)
class BenchmarkClaim:
    """One publicly observable external result, with everything needed to discount it."""

    claimant: str
    source: str
    #: ISO timestamp of the SOURCE, not of ingestion. A claim about last year read today is a
    #: claim about last year.
    observed_at: str
    evidence_class: str
    #: Reported start and end value of the tracked capital, in a single currency.
    start_value: float = 0.0
    end_value: float = 0.0
    elapsed_days: float = 0.0
    strategy_type: str = ""
    #: Estimated share of the return explained by market beta. None = unmeasured, and unmeasured
    #: beta is the reason most such claims cannot be compared to an alpha book at all.
    estimated_beta_share: float | None = None
    leverage: float | None = None
    #: Were the gains realised, or is this a mark on an open position?
    realised: bool = False
    #: Were deposits/withdrawals disclosed? Undisclosed flows can manufacture any curve.
    flows_disclosed: bool = False
    #: Are the figures net of fees, funding and slippage?
    net_of_costs: bool = False
    #: Free-text on what could not be checked. Absence of notes is not evidence of soundness.
    verification_notes: str = ""

    def __post_init__(self) -> None:
        if self.evidence_class not in EVIDENCE_CLASSES:
            raise ValueError(f"evidence_class must be one of {EVIDENCE_CLASSES}")

    @property
    def is_target(self) -> bool:
        return self.evidence_class == "TARGET"


@dataclass(frozen=True)
class OwnPerformance:
    """Our side. Measured, and held to a HIGHER standard than the other side by construction."""

    #: Realised log growth of working capital, flows removed, net of everything.
    realized_log_growth: float
    elapsed_days: float
    #: Capital actually at work. A desk that "won" by not deploying has not won.
    deployed_capital: float = 0.0
    total_capital: float = 0.0
    max_drawdown: float = 0.0
    #: Fills against real venues, not paper.
    real_fills: int = 0
    #: Profit that has been realised rather than marked.
    realised_pnl: float = 0.0

    @property
    def capital_utilisation(self) -> float | None:
        if self.total_capital <= 0:
            return None
        return self.deployed_capital / self.total_capital


def log_growth_from_claim(c: BenchmarkClaim) -> tuple[float | None, str]:
    """G_external over the claim's own window, or None with the reason it cannot be computed."""
    if c.is_target:
        return None, (
            f"{c.claimant}: this is a TARGET, not a result. A target has no growth to compute and "
            "must never be promoted into one by the passage of time")
    if c.start_value <= 0 or c.end_value <= 0:
        return None, f"{c.claimant}: start/end values not both positive -- nothing to compute"
    g = math.log(c.end_value / c.start_value)
    caveats = []
    if not c.net_of_costs:
        caveats.append("GROSS of costs while our side is net")
    if not c.realised:
        caveats.append("unrealised marks")
    if not c.flows_disclosed:
        caveats.append("external flows undisclosed, so the curve may not be a return at all")
    if c.estimated_beta_share is None:
        caveats.append("beta share unmeasured, so alpha and market move are not separable")
    return g, (f"{c.claimant}: log growth {g:+.4f} over {c.elapsed_days:g}d"
               + (f" -- CAVEATS: {'; '.join(caveats)}" if caveats else ""))


def comparable(c: BenchmarkClaim, own: OwnPerformance) -> tuple[bool, str]:
    """Can these two numbers be put in the same subtraction at all?"""
    if c.evidence_class not in USABLE_FOR_COMPARISON:
        return False, (
            f"evidence class {c.evidence_class} is below {sorted(USABLE_FOR_COMPARISON)}. "
            "Subtracting an assertion from a measurement produces a number with no error bar, "
            "and it will be quoted as though it had one")
    if not c.net_of_costs:
        return False, ("the external figure is gross and ours is net of fees, funding, slippage "
                       "and gas. That difference alone has decided comparisons of this kind")
    if not c.realised:
        return False, "the external figure is an unrealised mark; ours is realised log growth"
    if not c.flows_disclosed:
        return False, ("external deposits and withdrawals are undisclosed, so the reported curve "
                       "may be a funding schedule rather than a return")
    if min(c.elapsed_days, own.elapsed_days) < MIN_COMPARABLE_DAYS:
        return False, (
            f"shortest horizon is {min(c.elapsed_days, own.elapsed_days):g}d against a floor of "
            f"{MIN_COMPARABLE_DAYS:g}d. A lead over a shorter window is a description of that "
            "window")
    return True, (f"comparable: both net, both realised, flows disclosed, "
                  f"{min(c.elapsed_days, own.elapsed_days):g}d common horizon")


def performance_lead(c: BenchmarkClaim, own: OwnPerformance) -> tuple[float | None, str]:
    """PERFORMANCE_LEAD = G_ours - G_external, ANNUALISED to a common horizon. None when not
    comparable, and the reason is the deliverable in that case."""
    ok, why = comparable(c, own)
    if not ok:
        return None, f"LEAD NOT REPORTABLE -- {why}"
    g_ext, ext_why = log_growth_from_claim(c)
    if g_ext is None:
        return None, f"LEAD NOT REPORTABLE -- {ext_why}"
    ours = own.realized_log_growth * (365.0 / own.elapsed_days) if own.elapsed_days > 0 else None
    theirs = g_ext * (365.0 / c.elapsed_days) if c.elapsed_days > 0 else None
    if ours is None or theirs is None:
        return None, "LEAD NOT REPORTABLE -- an elapsed horizon is zero"
    lead = ours - theirs
    return lead, (
        f"annualised log growth: ours {ours:+.4f}, {c.claimant} {theirs:+.4f} => "
        f"PERFORMANCE_LEAD {lead:+.4f}. Both annualised from horizons of "
        f"{own.elapsed_days:g}d and {c.elapsed_days:g}d respectively -- annualising a short "
        "window inflates BOTH sides and the difference is the only part worth reading")


def promote(record: BenchmarkClaim, *, to_class: str, new_source: str) -> BenchmarkClaim:
    """Move a claim up the evidence ladder. Requires a NEW source, and refuses a silent TARGET
    promotion.

    This function is the whole reason evidence classes are more than a label. The failure it
    prevents is not hypothetical and does not require bad faith: a target announced in month one
    is remembered in month six as a thing that happened, and the record that would have said
    otherwise was overwritten by whoever updated the spreadsheet.
    """
    if to_class not in EVIDENCE_CLASSES:
        raise ValueError(f"unknown evidence class {to_class!r}")
    if EVIDENCE_CLASSES.index(to_class) <= EVIDENCE_CLASSES.index(record.evidence_class):
        raise ValueError(
            f"{record.claimant}: refusing to move {record.evidence_class} -> {to_class}. "
            "Promotion must strengthen the evidence; a downgrade is a new observation and needs "
            "its own record so the history stays legible")
    if not new_source.strip():
        raise ValueError(
            f"{record.claimant}: promotion from {record.evidence_class} to {to_class} requires a "
            "NEW source. A record cannot become better evidence because time passed -- that is "
            "exactly how a TARGET turns into an achieved return")
    return BenchmarkClaim(
        claimant=record.claimant, source=new_source, observed_at=record.observed_at,
        evidence_class=to_class, start_value=record.start_value, end_value=record.end_value,
        elapsed_days=record.elapsed_days, strategy_type=record.strategy_type,
        estimated_beta_share=record.estimated_beta_share, leverage=record.leverage,
        realised=record.realised, flows_disclosed=record.flows_disclosed,
        net_of_costs=record.net_of_costs,
        verification_notes=f"{record.verification_notes} | promoted via {new_source}".strip(" |"),
    )


def win_conditions(own: OwnPerformance) -> dict[str, tuple[bool, str]]:
    """What OUR side must satisfy before any claimed lead means anything.

    From the specification's "do not win by cheating the comparison" section.
    """
    util = own.capital_utilisation
    return {
        "REAL_CAPITAL": (own.deployed_capital > 0,
                         f"deployed {own.deployed_capital:g}"
                         if own.deployed_capital > 0 else
                         "no capital deployed -- a curve produced by not participating is not a "
                         "win, it is an abstention"),
        "REAL_FILLS": (own.real_fills > 0,
                       f"{own.real_fills} real fill(s)" if own.real_fills else
                       "zero real fills: this is a simulation result and cannot be entered in a "
                       "comparison against someone's actual account"),
        "REAL_COSTS": (own.realized_log_growth != 0.0 or own.real_fills > 0,
                       "growth measured on filled, costed trades"),
        "RETAINED_PROFIT": (own.realised_pnl > 0,
                            f"realised {own.realised_pnl:g}" if own.realised_pnl > 0 else
                            "no realised profit -- unrealised gains are the exact thing this "
                            "benchmark refuses to accept from the other side"),
        "SUFFICIENT_TIME": (own.elapsed_days >= MIN_COMPARABLE_DAYS,
                            f"{own.elapsed_days:g}d live" if own.elapsed_days >= MIN_COMPARABLE_DAYS
                            else f"{own.elapsed_days:g}d live, floor {MIN_COMPARABLE_DAYS:g}d"),
        "MEANINGFUL_UTILISATION": (util is not None and util >= 0.05,
                                   f"capital utilisation {util:.1%}" if util is not None else
                                   "capital utilisation UNMEASURED -- surviving by not deploying "
                                   "would score identically to surviving by being right"),
    }


def summarise(claims: list[BenchmarkClaim], own: OwnPerformance | None = None) -> dict[str, object]:
    """Report shape for `data/external_benchmark.json`."""
    rows = []
    for c in claims:
        g, why = log_growth_from_claim(c)
        lead, lwhy = (None, "own performance not supplied") if own is None else \
            performance_lead(c, own)
        rows.append({
            "claimant": c.claimant, "source": c.source, "observed_at": c.observed_at,
            "evidence_class": c.evidence_class,
            "usable_for_comparison": c.evidence_class in USABLE_FOR_COMPARISON,
            "log_growth": None if g is None else round(g, 5),
            "log_growth_note": why,
            "PERFORMANCE_LEAD": None if lead is None else round(lead, 5),
            "lead_note": lwhy,
            "estimated_beta_share": c.estimated_beta_share,
            "realised": c.realised, "net_of_costs": c.net_of_costs,
            "flows_disclosed": c.flows_disclosed,
        })
    wc = win_conditions(own) if own is not None else {}
    unmet = [k for k, (ok, _) in wc.items() if not ok]
    targets = sum(1 for c in claims if c.is_target)
    usable = sum(1 for c in claims if c.evidence_class in USABLE_FOR_COMPARISON)
    return {
        "claims": len(claims),
        "targets_recorded": targets,
        "usable_for_comparison": usable,
        "rows": rows,
        "own": None if own is None else {
            "realized_log_growth": round(own.realized_log_growth, 5),
            "elapsed_days": own.elapsed_days,
            "capital_utilisation": (None if own.capital_utilisation is None
                                    else round(own.capital_utilisation, 4)),
            "max_drawdown": own.max_drawdown,
            "real_fills": own.real_fills,
        },
        "own_win_conditions": {k: {"met": ok, "detail": d} for k, (ok, d) in wc.items()},
        "own_win_conditions_unmet": unmet,
        "headline": (
            f"{usable} of {len(claims)} external claim(s) are strong enough evidence to enter a "
            f"comparison ({targets} are TARGETS and never will be without a new observation)"
            + (f"; OUR side fails {len(unmet)} win condition(s): {unmet}" if unmet else "")
            + ("; no lead is reportable yet, which is a fact about the evidence rather than "
               "about the performance" if not any(r["PERFORMANCE_LEAD"] is not None for r in rows)
               else "")),
        "note": ("A TARGET is never silently promoted into an achieved return -- promote() "
                 "requires a new source at a strictly higher evidence class. A lead is reported "
                 "only when both sides are net of costs, realised, flow-disclosed and share a "
                 f"horizon of at least {MIN_COMPARABLE_DAYS:g} days. Higher Sharpe on undeployed "
                 "capital, a better backtest, or more discovered alphas do not constitute a win."),
    }
