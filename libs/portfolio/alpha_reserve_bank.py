"""THE ALPHA RESERVE BANK — how much of the live book could be replaced if it died this morning.

THE GAP THIS CLOSES, and it is a compounding gap rather than a discovery one. This desk measures
discovery throughput carefully: candidates generated, killed, survivors banked. It has never
measured the thing that decides what discovery is WORTH -- **replacement latency.** A factory that
finds four independent edges a year and takes five months to field each replacement runs a book
that is empty a third of the time, and capital that is not deployed does not compound. Throughput
without a bench is a research metric wearing a P&L metric's clothes.

**THE QUESTION THIS MODULE EXISTS TO ANSWER.** If 25%, 50% or 75% of current live alpha died
today, how much could be replaced IMMEDIATELY, without lowering the evidence standard? Every word
of that sentence is load-bearing, and the last clause is the one that makes it hard: a bench is
trivially deep if the bar is allowed to fall the day it is needed. So `replacement_coverage`
counts only candidates that ALREADY clear the standing bar, and a candidate that would clear it in
three weeks contributes to `replacement_latency` instead -- it is a promise, not a reserve.

**THREE CLONES ARE ONE REPLACEMENT.** The bench is deflated by effective independence before it is
counted. A bench of eight momentum variants cannot replace three independent dead engines; it can
replace roughly one. This is the same arithmetic as `libs/validation/effective_sample.py` applied
to strategies instead of observations, and it is the reason a raw bench count is a vanity number.

**AND A MECHANISM-LEVEL DEATH KILLS THE BENCH TOO.** If funding-carry stops working, every
funding-carry candidate on the bench stops working on the same morning -- they were never a
reserve against that failure, they were more of the exposure that just died. `replacement_coverage`
takes a `dead_mechanisms` argument for exactly this, and refuses to count same-mechanism cover.

**A STRATEGY REMOVED FROM CAPITAL NEED NOT DISAPPEAR.** DORMANT_MONITORED keeps observing a
plausible mechanism with no capital at risk, because the state that killed it may not be permanent
and re-deriving a retired edge from scratch costs far more than watching it. Retirement is a
capital decision; deletion is an information decision, and the desk has been conflating them.

Reports. Allocates nothing, promotes nothing, retires nothing: `capital_competition.py` owns
allocation and `libs/research/alpha_state.py` owns the evidence ladder this module reads.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "LAYERS",
    "ReserveCandidate",
    "alpha_reserve_ratio",
    "bench_effective_count",
    "replacement_coverage",
    "replacement_latency",
    "summarise",
    "switch_verdict",
]

#: Capital proximity, live to dormant. A strategy moves BOTH ways along this: demotion is not
#: deletion, and DORMANT_MONITORED exists so that a mechanism can be revived by new state rather
#: than rediscovered from nothing.
LAYERS: tuple[str, ...] = (
    "LIVE_CORE",            # funded, full size
    "LIVE_CANARY",          # funded, deliberately small; earning live evidence
    "SHADOW_CHALLENGER",    # trading on paper against a live incumbent, right now
    "INCUBATION",           # accruing forward evidence, no incumbent assigned
    "DORMANT_MONITORED",    # no capital, still observed -- mechanism remains plausible
    "RETIRED",              # mechanism disbelieved; counts toward nothing
)

_LIVE = ("LIVE_CORE", "LIVE_CANARY")
_BENCH = ("SHADOW_CHALLENGER", "INCUBATION", "DORMANT_MONITORED")


@dataclass(frozen=True)
class ReserveCandidate:
    """One strategy anywhere on the ladder, priced by what it would contribute FORWARD."""

    strategy_id: str
    layer: str
    #: Named mechanism. Two candidates sharing this share their failure mode, and the bank refuses
    #: to count one as cover for the other's mechanism-level death.
    mechanism: str = "UNKNOWN"
    #: Expected forward log-growth contribution at its intended size. 0.0 = UNMEASURED, and an
    #: UNMEASURED candidate contributes to no reserve total -- absence is not a small number.
    forward_elog: float = 0.0
    #: Posterior width on that estimate. Charged when the candidate is asked to replace something,
    #: because a replacement chosen on a wide posterior is a coin flip wearing a forecast.
    forward_elog_sigma: float = 0.0
    #: True when the candidate ALREADY meets the standing evidence bar. This is the field that
    #: makes the bench honest: everything else is a promise.
    meets_evidence_bar: bool = False
    #: Days until it would meet the bar on its current evidence path. 0 with
    #: `meets_evidence_bar=False` means UNKNOWN, not imminent.
    days_to_bar: float = 0.0
    #: Mean correlation of this candidate's returns to the rest of the bench, in [0, 1].
    bench_correlation: float = 0.0
    #: Capital fraction if live. Only meaningful on the LIVE_* layers.
    live_weight: float = 0.0
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.layer not in LAYERS:
            raise ValueError(f"unknown layer {self.layer!r}; expected one of {LAYERS}")

    @property
    def is_live(self) -> bool:
        return self.layer in _LIVE

    @property
    def is_bench(self) -> bool:
        return self.layer in _BENCH

    @property
    def measured(self) -> bool:
        return self.forward_elog != 0.0

    @property
    def eligible_now(self) -> bool:
        """Deployable this morning: on the bench, measured, and already over the bar."""
        return self.is_bench and self.measured and self.meets_evidence_bar

    @property
    def shrunk_elog(self) -> float:
        """Forward E[log W] less one posterior width. Never negative-credited."""
        return max(0.0, self.forward_elog - self.forward_elog_sigma)


def bench_effective_count(bench: list[ReserveCandidate]) -> tuple[float, str]:
    """How many INDEPENDENT replacements the bench really holds.

    `n_eff = n / (1 + (n-1) * rho_bar)` -- the participation ratio, the same deflator the desk
    applies to overlapping observations. At rho=0 the bench is worth its headcount; at rho=1 the
    whole bench is one idea implemented repeatedly, which is the usual state of a bench nobody
    deflated.
    """
    usable = [c for c in bench if c.is_bench and c.measured]
    n = len(usable)
    if n == 0:
        return 0.0, ("bench is empty or entirely UNMEASURED -- effective depth is not low, it is "
                     "unknown, and a bench nobody has priced is not a reserve")
    if n == 1:
        return 1.0, "one measured bench candidate; independence is not yet a question"
    rho = sum(max(0.0, min(1.0, c.bench_correlation)) for c in usable) / n
    n_eff = n / (1.0 + (n - 1) * rho)
    return n_eff, (
        f"{n} measured bench candidates at mean rho {rho:.2f} => {n_eff:.2f} EFFECTIVE. "
        + (f"{n - n_eff:.1f} of them are duplicates of each other and would die on the same "
           "morning -- a bench counted by headcount overstates cover by that much"
           if n_eff < n - 0.5 else
           "the bench is close to genuinely independent, so headcount is roughly honest here"))


def alpha_reserve_ratio(book: list[ReserveCandidate]) -> tuple[float | None, str]:
    """Eligible forward economic value on the bench / forward economic value live.

    1.0 means the desk could rebuild its entire book this morning at the same standard. Below 0.25
    means most of the live book has no ready successor, and every day such a strategy survives is
    borrowed rather than earned.
    """
    live = [c for c in book if c.is_live and c.measured]
    if not live:
        return None, ("no MEASURED live strategy -- the reserve ratio has no denominator. This is "
                      "the honest state of a desk with no live book, and it is not a ratio of zero")
    live_value = sum(c.shrunk_elog for c in live)
    if live_value <= 0:
        return None, ("live forward E[log W] is not positive, so 'replacement' is the wrong "
                      "question -- the live book is the thing that needs replacing")
    ready = [c for c in book if c.eligible_now]
    n_eff, _ = bench_effective_count([c for c in book if c.is_bench])
    raw = sum(c.shrunk_elog for c in ready)
    # Deflate the eligible pile by the bench's independence, not by its headcount.
    measured_bench = [c for c in book if c.is_bench and c.measured]
    deflator = (n_eff / len(measured_bench)) if measured_bench else 0.0
    ratio = (raw * deflator) / live_value
    return ratio, (
        f"ALPHA_RESERVE_RATIO {ratio:.2f}: {len(ready)} eligible bench candidate(s) worth "
        f"{raw:.4f} forward E[log W], deflated x{deflator:.2f} for bench dependence, against "
        f"{live_value:.4f} live. "
        + ("The bench could rebuild the book at the current standard" if ratio >= 1.0 else
           f"Roughly {ratio:.0%} of live forward value has a ready successor; the rest is running "
           "without one, and if it dies the capital goes idle rather than rotating"))


def replacement_coverage(book: list[ReserveCandidate], *, fraction: float,
                         dead_mechanisms: tuple[str, ...] = ()) -> tuple[float | None, str]:
    """If `fraction` of live alpha died today, what share is replaceable WITHOUT lowering the bar.

    WORST CASE BY CONSTRUCTION: the dead are taken from the LARGEST live contributors first, not a
    random draw. A desk that models its own failures as average has modelled the wrong failure --
    edges do not die in order of unimportance, and the crowded winner is the likeliest casualty.

    `dead_mechanisms` names mechanisms that failed at the MECHANISM level. Bench candidates on
    those mechanisms are excluded from cover: they did not survive the event, they were more of it.
    """
    if not 0.0 < fraction <= 1.0:
        raise ValueError("fraction must be in (0, 1]")
    live = sorted((c for c in book if c.is_live and c.measured),
                  key=lambda c: c.shrunk_elog, reverse=True)
    if not live:
        return None, ("no MEASURED live strategy, so 'what if it died' is unanswerable -- "
                      "UNMEASURED, not fully covered")
    total = sum(c.shrunk_elog for c in live)
    if total <= 0:
        return None, "live forward value is not positive; replacement coverage is undefined"
    target = total * fraction
    lost, killed = 0.0, []
    for c in live:
        if lost >= target:
            break
        lost += c.shrunk_elog
        killed.append(c)
    dead = set(dead_mechanisms) | {c.mechanism for c in killed if c.mechanism in dead_mechanisms}
    ready = [c for c in book if c.eligible_now and c.mechanism not in dead]
    blocked = [c for c in book if c.eligible_now and c.mechanism in dead]
    n_eff, _ = bench_effective_count([c for c in book if c.is_bench])
    measured_bench = [c for c in book if c.is_bench and c.measured]
    deflator = (n_eff / len(measured_bench)) if measured_bench else 0.0
    available = sum(c.shrunk_elog for c in ready) * deflator
    cover = min(1.0, available / lost) if lost > 0 else 1.0
    return cover, (
        f"{fraction:.0%} SHOCK: the {len(killed)} largest live contributor(s) carry {lost:.4f} "
        f"forward E[log W]. {len(ready)} eligible bench candidate(s) supply {available:.4f} after "
        f"dependence deflation => {cover:.0%} covered immediately at the current bar"
        + (f". {len(blocked)} otherwise-eligible candidate(s) were EXCLUDED because they share a "
           f"failed mechanism {sorted(dead)} -- same-mechanism cover is not cover" if blocked
           else "")
        + (". The uncovered share is capital that goes idle on the day of the shock, and idle "
           "capital does not compound" if cover < 1.0 else
           ". The book is rebuildable at this shock size without touching the evidence standard"))


def replacement_latency(book: list[ReserveCandidate]) -> tuple[float | None, str]:
    """Days until the bench could cover a 50% shock. The number the factory is actually optimising.

    Zero is the target and it is reached by INCUBATING EARLY, not by promoting fast. A desk can
    always drive this to zero by lowering the bar, which is why the bar is not an input here.
    """
    now, _ = replacement_coverage(book, fraction=0.5)
    if now is None:
        return None, "no measured live book, so replacement latency is UNMEASURED"
    if now >= 1.0:
        return 0.0, ("REPLACEMENT_LATENCY 0 days: a 50% shock is already covered by candidates "
                     "that clear the bar today. This is the state the reserve bank exists to hold")
    pipeline = sorted((c for c in book
                       if c.is_bench and c.measured and not c.meets_evidence_bar
                       and c.days_to_bar > 0), key=lambda c: c.days_to_bar)
    if not pipeline:
        unknown = [c for c in book if c.is_bench and not c.meets_evidence_bar
                   and c.days_to_bar <= 0]
        return None, (
            f"a 50% shock is only {now:.0%} covered and NOTHING on the bench has a dated path to "
            f"the bar ({len(unknown)} candidate(s) carry no `days_to_bar`). Latency is UNBOUNDED, "
            "not long: there is no evidence the gap ever closes, and that is the more serious "
            "finding of the two")
    # Walk the dated pipeline forward, admitting candidates as they cross the bar.
    admitted = list(book)
    for c in pipeline:
        admitted = [ReserveCandidate(**{**x.__dict__, "meets_evidence_bar": True})
                    if x.strategy_id == c.strategy_id else x for x in admitted]
        cov, _ = replacement_coverage(admitted, fraction=0.5)
        if cov is not None and cov >= 1.0:
            return c.days_to_bar, (
                f"REPLACEMENT_LATENCY {c.days_to_bar:g} days: a 50% shock is {now:.0%} covered "
                f"today and reaches full cover once {c.strategy_id} clears the bar. Those days are "
                "the compounding the desk forfeits if the shock lands first")
    horizon = pipeline[-1].days_to_bar
    return None, (
        f"a 50% shock is {now:.0%} covered today and STILL short after the whole dated pipeline "
        f"lands at {horizon:g} days. The bench is not merely late, it is too small -- more "
        "incubation time does not fix a reserve that is undersized at the end of it")


def switch_verdict(incumbent: ReserveCandidate, challenger: ReserveCandidate, *,
                   switching_cost: float = 0.0, execution_transition_cost: float = 0.0,
                   lost_option_value: float = 0.0) -> tuple[str, str]:
    """REPLACE / DEMOTE_INCUMBENT / KEEP / UNMEASURED — never on drawdown alone.

    **INCUMBENT DRAWDOWN IS NOT AN INPUT AND THAT IS DELIBERATE.** Firing a strategy for being down
    is the single most expensive reflex in systematic trading: it sells the bottom of a mechanism
    that is working, and it does so at exactly the moment the evidence is weakest. The comparison
    is forward against forward, with every cost of the switch charged to the challenger, because
    the challenger is the one asking for the change.

    LOST_OPTION_VALUE is the one people forget. Retiring the incumbent destroys the ability to
    revive it cheaply if the state that hurt it reverses -- which is why DEMOTE_INCUMBENT to
    DORMANT_MONITORED, and not RETIRED, is usually the right form of a successful switch.
    """
    if not (incumbent.measured and challenger.measured):
        missing = [c.strategy_id for c in (incumbent, challenger) if not c.measured]
        return "UNMEASURED", (
            f"forward E[log W] absent for {missing} -- the switch cannot be priced. An unpriceable "
            "switch defaults to KEEP, because the incumbent's evidence is at least live")
    if not challenger.meets_evidence_bar:
        return "KEEP", (
            f"{challenger.strategy_id} does not clear the evidence bar"
            + (f" and is {challenger.days_to_bar:g} days from it" if challenger.days_to_bar > 0
               else " and has no dated path to it")
            + ". A challenger promoted early is a bar lowered quietly, which is the failure this "
              "whole bank is built to prevent")
    # Model uncertainty is charged to the challenger TWICE over: once as its own posterior width,
    # once as the incumbent's -- because replacing a known quantity with an estimate is the risk.
    gain = challenger.forward_elog - incumbent.forward_elog
    uncertainty = challenger.forward_elog_sigma + incumbent.forward_elog_sigma
    costs = switching_cost + execution_transition_cost + lost_option_value
    net = gain - uncertainty - costs
    detail = (f"{challenger.strategy_id} forward {challenger.forward_elog:+.4f} vs "
              f"{incumbent.strategy_id} {incumbent.forward_elog:+.4f} => {gain:+.4f} gross, less "
              f"{uncertainty:.4f} model uncertainty, {switching_cost:.4f} switching, "
              f"{execution_transition_cost:.4f} transition, {lost_option_value:.4f} lost option "
              f"value => {net:+.4f} NET")
    if net <= 0:
        return "KEEP", (
            detail + ". The challenger is "
            + ("better gross but the switch costs more than it gains" if gain > 0 else "not better")
            + " -- and incumbent drawdown is deliberately not an input, because firing a strategy "
              "for being down sells the bottom of a mechanism that still works")
    if incumbent.forward_elog > 0:
        return "DEMOTE_INCUMBENT", (
            detail + f". Switch is justified, but {incumbent.strategy_id} still has POSITIVE "
            "forward expectation: demote it to DORMANT_MONITORED rather than retiring it. It costs "
            "nothing to keep observing and far less than rediscovering it if the state reverses")
    return "REPLACE", (
        detail + f". {incumbent.strategy_id} has non-positive forward expectation and a funded "
        "challenger clears the bar -- this is a replacement, not a rotation")


def summarise(book: list[ReserveCandidate]) -> dict[str, object]:
    """Report shape for the opportunity books."""
    if not book:
        return {"measured": False, "headline": (
            "ALPHA RESERVE BANK is empty -- no live strategy and no bench. Replacement latency is "
            "therefore UNMEASURED rather than zero, and a desk with no bench discovers its "
            "replacement gap on the morning it needs one")}
    live = [c for c in book if c.is_live]
    bench = [c for c in book if c.is_bench]
    ratio, ratio_why = alpha_reserve_ratio(book)
    n_eff, indep_why = bench_effective_count(bench)
    latency, latency_why = replacement_latency(book)
    shocks = {}
    for f in (0.25, 0.5, 0.75):
        cov, why = replacement_coverage(book, fraction=f)
        shocks[f"{int(f * 100)}pct"] = {"coverage": cov, "why": why}
    layers = {ly: sum(1 for c in book if c.layer == ly) for ly in LAYERS}
    return {
        "measured": ratio is not None,
        "layers": layers,
        "live": len(live),
        "bench": len(bench),
        "bench_effective_count": round(n_eff, 3),
        "bench_independence_note": indep_why,
        "alpha_reserve_ratio": None if ratio is None else round(ratio, 4),
        "alpha_reserve_ratio_note": ratio_why,
        "replacement_latency_days": latency,
        "replacement_latency_note": latency_why,
        "shock_coverage": shocks,
        "headline": (ratio_why if ratio is not None else
                     "ALPHA RESERVE BANK UNMEASURED -- " + ratio_why),
        "note": ("Counts only candidates that clear the standing evidence bar TODAY; a candidate "
                 "three weeks from the bar is a promise and lands in replacement latency instead. "
                 "The bench is deflated by effective independence before it is counted, because "
                 "three clones of one mechanism are one replacement and they die on the same "
                 "morning. Reports only -- allocation stays with capital_competition and the "
                 "evidence ladder stays with alpha_state."),
    }
