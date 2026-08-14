"""HOW FAST IS THIS CLOCK EARNING EVIDENCE, AND WHAT SPECIFICALLY IS SLOWING IT DOWN.

THE QUESTION THIS ANSWERS, AND WHY IT IS THE ONLY ONE WORTH ASKING ABOUT SPEED.

"Forward validation takes 40 days" is the desk's most-repeated complaint, and the obvious fixes
are all forbidden or already refuted:

  * SHORTEN THE CLOCK -- lowers the evidence bar for everything, including noise. L1.6 forbids it.
  * USE A CLEVERER TEST -- already built (`libs.research.anytime_valid`) and already MEASURED, in
    its own docstring: on a Sharpe-2 daily edge the e-process graduated 6 of 40 paths at a MEDIAN
    of 132 days, SLOWER than the fixed 90-day clock, because a Sharpe-2 daily edge carries
    per-observation signal of ~0.105 and log-wealth grows at ~mu^2/2sigma^2 per observation. That
    is fundamental to sequential testing on weak per-observation signal, not an implementation
    flaw. The desk wrote "there is no free lunch on validation speed" and it is correct.

What is left is the accelerant that module names: MORE EFFECTIVE OBSERVATIONS PER DAY. And the
desk already owns the arithmetic for it -- `evidence_clock.effective_n` deflates a raw count for
serial correlation, event clustering, cross-symbol correlation and regime concentration -- but
`annualised_information_rate` and `regime_penalty` had ZERO callers outside their own module. The
desk could say how much evidence a clock had. Nothing said how fast it was arriving, or which of
the four deflators was eating it.

That difference is the whole file. A clock at 0.2 effective observations per day needs 150 days to
reach 30; the same clock run across the cross-section it already has data for reaches it in 3. The
speed-up is real, it is large, and it is invisible while nobody computes the rate.

**IT RANKS ACCELERANTS BY MEASURED GAIN, NEVER BY PLAUSIBILITY.** Each one below is an arithmetic
consequence of `effective_n`'s own formula, computed against THIS clock's measured correlations,
not a rule of thumb. Cross-section looks spectacular at low rho and nearly worthless at high rho,
and the same clock gets both answers depending on what its symbols actually did.

**IT LOWERS NOTHING AND PROMOTES NOTHING.** `required` is an input, never an output. Every path
here changes how fast evidence ARRIVES; none changes how much is needed, which is the one edit
that would make the whole exercise self-defeating.

Stdlib only. import from libs.research.information_rate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from libs.research.evidence_clock import (
    MIN_EFFECTIVE,
    EvidenceState,
    _serial_deflator,
    effective_n,
    regime_penalty,
)

__all__ = [
    "Accelerant",
    "RateReport",
    "accelerants",
    "binding_constraint",
    "cross_section_gain",
    "measure",
]


@dataclass(frozen=True)
class Accelerant:
    """One concrete change, and what it would MULTIPLY the effective observation count by.

    `gain` is a multiplier on effective observations, derived from `effective_n`'s own formula.
    A gain of 1.0 means the change buys nothing HERE -- which is a real and useful answer, and the
    reason these are computed per clock rather than recommended generically.
    """

    lever: str
    #: The multiplier, or None when an input it depends on is UNMEASURED. NEVER a point estimate
    #: computed from a defaulted zero -- see `gain_low`.
    gain: float | None
    why: str
    #: What the desk must already possess for this to be available. Named so an accelerant that
    #: needs data nobody has is not confused with one that needs a config change.
    requires: str
    #: THE RANGE, when the gain cannot be a number. The cross-section lever spans 213x at rho=0
    #: and 1.0x at rho=1.0 for the same 213 symbols, so an unmeasured rho does not narrow to
    #: "213x" -- it narrows to nothing, and publishing the optimistic end of a two-order-of-
    #: magnitude range as if it were measured is exactly the WS-005 substitution this desk keeps
    #: making. `gain_low` is the conservative end and is what RANKING uses, so an unmeasured lever
    #: can never outrank a measured one on the strength of a default.
    gain_low: float | None = None
    gain_high: float | None = None

    @property
    def measured(self) -> bool:
        return self.gain is not None

    @property
    def rank_key(self) -> float:
        return self.gain if self.gain is not None else (self.gain_low or 0.0)

    @property
    def days_saved_from(self) -> str:
        if self.gain is None:
            return (f"UNMEASURED: between {self.gain_low:.1f}x and {self.gain_high:.1f}x"
                    if self.gain_low is not None and self.gain_high is not None
                    else "UNMEASURED")
        return f"divides the remaining wait by {self.gain:.1f}x" if self.gain > 1.0 else "no gain"


@dataclass(frozen=True)
class RateReport:
    """What one clock is earning per day, and the single thing most responsible for it."""

    clock: str
    raw_observations: int
    effective: float
    days_elapsed: float
    effective_per_day: float | None
    required: float
    days_remaining: float | None
    binding: str
    binding_cost: float
    accelerants: list[Accelerant]

    def as_row(self) -> dict[str, Any]:
        return {
            "clock": self.clock,
            "raw_observations": self.raw_observations,
            "effective": round(self.effective, 2),
            "days_elapsed": round(self.days_elapsed, 1),
            "effective_per_day": (None if self.effective_per_day is None
                                  else round(self.effective_per_day, 3)),
            "required": self.required,
            "days_remaining": (None if self.days_remaining is None
                               else round(self.days_remaining, 1)),
            "binding_constraint": self.binding,
            "binding_costs_multiplier": round(self.binding_cost, 3),
            "accelerants": [{"lever": a.lever,
                             "gain": (None if a.gain is None else round(a.gain, 2)),
                             "gain_low": (None if a.gain_low is None else round(a.gain_low, 2)),
                             "gain_high": (None if a.gain_high is None else round(a.gain_high, 2)),
                             "measured": a.measured,
                             "why": a.why, "requires": a.requires}
                            for a in self.accelerants],
        }


def cross_section_gain(n_symbols: int, rho: float) -> float:
    """What running the SAME signal across `n_symbols` correlated symbols multiplies evidence by.

    THE ONE PIECE OF ARITHMETIC THIS FILE EXISTS FOR, so it is derived rather than asserted.
    `effective_n` scales a raw count by ``(1 + (S-1)(1-rho)) / S``. Widening from one symbol to S
    multiplies the RAW count by S and the factor by that expression over 1, so the two S's cancel:

        gain = 1 + (S - 1) * (1 - rho)

    At 213 symbols and rho=0.7 that is 64.6x; at rho=0.95 it is 11.6x; at rho=1.0 it is 1.0x -- one
    instrument wearing 213 tickers, which is exactly what a perfectly correlated cross-section is.
    The formula gets all three right, which is why it is used instead of "breadth is good".
    """
    s = max(1, int(n_symbols))
    r = max(0.0, min(1.0, float(rho)))
    return 1.0 + (s - 1) * (1.0 - r)


def binding_constraint(state: EvidenceState) -> tuple[str, float]:
    """Which deflator is costing this clock the most, and the multiplier it is costing.

    Reported as the SMALLEST multiplier rather than the largest loss, because these compose
    multiplicatively: a 0.5 regime penalty and a 0.9 serial deflator are not "0.5 and 0.1 of the
    damage", they are 0.45 together, and naming the smaller one names the thing worth fixing.
    """
    cands: list[tuple[str, float]] = [
        ("serial correlation", _serial_deflator(state.autocorrelation)),
        ("regime concentration", regime_penalty(state.distinct_regimes)),
    ]
    if state.distinct_events > 0 and state.raw_observations > 0:
        # The event cap is a MIN, not a product, so its effective multiplier is the ratio it
        # imposed. 500 fills inside one cascade is one observation of one cascade.
        cands.append(("event clustering",
                      min(1.0, state.distinct_events / float(state.raw_observations))))
    if state.distinct_symbols > 1:
        rho = max(0.0, min(1.0, state.cross_symbol_rho))
        cands.append(("cross-symbol correlation",
                      (1.0 + (state.distinct_symbols - 1) * (1.0 - rho))
                      / state.distinct_symbols))
    name, mult = min(cands, key=lambda kv: kv[1])
    return name, mult


def accelerants(
    state: EvidenceState,
    *,
    available_symbols: int = 1,
    bars_per_day: float = 1.0,
    available_bars_per_day: float = 1.0,
) -> list[Accelerant]:
    """Ranked, measured ways to earn the SAME evidence sooner. Never ways to need less of it.

    `available_symbols` and `available_bars_per_day` are what the desk ALREADY HAS DATA FOR. An
    accelerant that needs data nobody holds is not an accelerant, it is a data project, and
    conflating the two is how a speed report becomes a wish list.
    """
    out: list[Accelerant] = []

    if available_symbols > max(1, state.distinct_symbols):
        rho = state.cross_symbol_rho
        now = cross_section_gain(state.distinct_symbols, rho)
        then = cross_section_gain(available_symbols, rho)
        if state.measured:
            out.append(Accelerant(
                lever=f"widen the cross-section {state.distinct_symbols} -> {available_symbols}",
                gain=(then / now if now > 0 else 1.0),
                why=(f"the same signal on {available_symbols} symbols at MEASURED rho={rho:.2f} "
                     f"earns {then:.1f} independent observations per bar against {now:.1f} now. "
                     "Usually the largest available gain, and it needs no new data -- the bars "
                     "are already in the lake"),
                requires="bars already in the lake for the wider universe"))
        else:
            # THE DEFECT THIS BRANCH EXISTS FOR, caught by running the report on the live box.
            # `cross_symbol_rho` defaults to 0.0 when unmeasured, and 0.0 is the value at which
            # this lever looks BEST: it published "213x available" for a macro timing clock whose
            # true cross-sectional correlation is high enough to make the real number a fraction
            # of that. A defaulted zero read as a measurement, in the flattering direction, on the
            # number that decides where the desk spends a month of build time -- WS-005 exactly.
            #
            # The range spans two orders of magnitude for the SAME 213 symbols, so an unmeasured
            # rho does not narrow to the optimistic end, it narrows to nothing. Both ends are
            # published and the CONSERVATIVE one carries the ranking.
            hi = cross_section_gain(available_symbols, 0.0) / (now or 1.0)
            lo = cross_section_gain(available_symbols, 0.9) / (now or 1.0)
            out.append(Accelerant(
                lever=f"widen the cross-section {state.distinct_symbols} -> {available_symbols}",
                gain=None, gain_low=lo, gain_high=hi,
                why=(f"UNMEASURED. Across {available_symbols} symbols this is worth {hi:.0f}x at "
                     f"rho=0 and {lo:.0f}x at rho=0.9, and exactly 1.0x at rho=1.0 -- 213 tickers "
                     "on one instrument. Crypto daily returns sit near the pessimistic end, and a "
                     "MARKET-WIDE TIMING signal gains least of all because one macro reading per "
                     "day is one observation however many symbols it is scored against. Measure "
                     "the clock's cross-symbol correlation before spending build time on this"),
                requires="the clock's measured cross-symbol correlation, which no forward "
                         "artifact currently publishes"))

    if available_bars_per_day > bars_per_day > 0:
        ratio = available_bars_per_day / bars_per_day
        # HIGHER FREQUENCY IS NOT A FREE MULTIPLIER, and pretending it is would be the single
        # easiest way to manufacture evidence here. Sampling the same process faster raises serial
        # correlation, and the deflator takes it straight back. The honest bound is the raw
        # multiplier ATTENUATED by the deflator this clock already measures.
        atten = _serial_deflator(state.autocorrelation)
        out.append(Accelerant(
            lever=f"sample {bars_per_day:g} -> {available_bars_per_day:g} bars/day",
            gain=max(1.0, ratio * atten),
            why=(f"{ratio:.0f}x the raw observations, ATTENUATED by this clock's own serial "
                 f"deflator ({atten:.2f}) because sampling one process faster does not make it "
                 "more independent. A strategy whose edge lives at a daily horizon gains almost "
                 "nothing here; one whose edge is intraday gains nearly the full multiple"),
            requires="a signal whose mechanism actually operates at the finer horizon"))

    if state.distinct_regimes <= 1:
        now = regime_penalty(state.distinct_regimes)
        out.append(Accelerant(
            lever="cover a second regime",
            gain=regime_penalty(2) / now if now > 0 else 1.0,
            why=("evidence from one regime is evidence about one regime, and the clock says so "
                 "with a 0.5 multiplier. THIS ONE CANNOT BE BOUGHT WITH COMPUTE -- it arrives "
                 "when the market changes, or by backfilling the signal over a period that "
                 "already contained a different regime"),
            requires="a second regime in the observation window, or a historical one to replay"))

    out.sort(key=lambda a: a.rank_key, reverse=True)
    return out


def measure(
    clock: str,
    state: EvidenceState,
    *,
    days_elapsed: float,
    required: float = MIN_EFFECTIVE,
    available_symbols: int = 1,
    bars_per_day: float = 1.0,
    available_bars_per_day: float = 1.0,
) -> RateReport:
    """One clock's information rate, its binding constraint, and its ranked accelerants.

    `days_elapsed` is used ONLY as a denominator for the rate and to project a remaining wait. It
    can never shorten the requirement: L1.48 removed calendar time from every promotion path, and
    reporting a rate is not the same as spending one.

    AN UNMEASURED STATE PROJECTS NOTHING (L1.28a). Zero elapsed days gives `None` for the rate and
    for the projection rather than a division that would produce a confident infinity.
    """
    eff = effective_n(state)
    rate = (eff / days_elapsed) if days_elapsed > 0 else None
    remaining = None
    if rate is not None and rate > 0:
        remaining = max(0.0, (required - eff) / rate)
    name, mult = binding_constraint(state)
    return RateReport(
        clock=clock,
        raw_observations=int(state.raw_observations),
        effective=eff,
        days_elapsed=float(days_elapsed),
        effective_per_day=rate,
        required=float(required),
        days_remaining=remaining,
        binding=name,
        binding_cost=mult,
        accelerants=accelerants(state, available_symbols=available_symbols,
                                bars_per_day=bars_per_day,
                                available_bars_per_day=available_bars_per_day),
    )
