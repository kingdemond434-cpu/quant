"""VENUE SUBSIDY / REBATE RENT -- the accounting that decides whether a maker rebate is INCOME.

WHAT THIS CLASS IS, AND WHY IT IS NOT AN EDGE IN THE PRICE. `data/mechanism_census.json` ranks
`venue_subsidy_rent` #4 of 20 (gap 0.340, NAMED-UNTESTED, ZERO tested candidates) with the payer
named explicitly: *the venue itself, paying a maker rebate or listing incentive to buy liquidity it
cannot otherwise attract*. That makes it RENT -- a payment for a service rendered (resting size that
would not otherwise be there) -- and not an informational edge. Rent has a property an edge does
not: it is capturable only by whoever actually PERFORMS the service at the size the tier requires.
A rebate schedule is public; reaching tier 4 is not.

=================================================================================================
THE HONEST HAZARD, AND IT IS THE WHOLE REASON THIS MODULE IS SHAPED THE WAY IT IS:

    A REBATE IS ONLY INCOME IF THE STRATEGY WOULD HAVE TRADED ANYWAY.

A strategy that trades TO EARN THE REBATE is churn wearing a subsidy's name. The desk has already
paid for this lesson in cash: the 2026-07 fee fire burned $1,750 of commission against ~$126 of
logged round-trips (`libs/execution/economics`), and 24.2% of fills -- the taker tail -- were paying
96.5% of all fees (`scripts/fill_quality_monitor`). A gross rebate number computed over that same
tape would have read as a profitable liquidity-provision business.

So this module makes a GROSS-ONLY ANSWER STRUCTURALLY UNAVAILABLE. There is no function here that
returns a rebate total on its own. `RebateCapture.net_usd` is `None` whenever the cost side is
unmeasured, `headline()` returns REFUSED in that state, and the refusal names which input is
missing. If the net cannot be computed, the correct output is a refusal, not a smaller claim.
=================================================================================================

R0143 IS A HARD RAIL HERE, NOT A FOOTNOTE. Every rebate tier is a volume threshold, so the shortest
path from this mechanism to a recommendation is "trade more / bigger to reach tier N". That is the
SIZE lever, which the desk's own law forbids as a growth argument (geometric growth peaks at Kelly
f* and falls after it). This module therefore never reports a tier the desk has not ALREADY reached
on its OWN observed volume: `TierReachability` is a measurement of attained volume, and a tier that
would require more volume yields the verdict NOT-EARNABLE-AT-CURRENT-SIZE -- which is a kill, and
is explicitly NOT an argument to grow into it.

EFFECTIVE DATES ARE LOAD-BEARING, NOT METADATA. A fee schedule scraped today and applied to fills
from three months ago silently prices history at today's rates. `FeeSchedule.tier_at` returns None
-- never "the current tier" -- when no tier's effective window covers the timestamp asked about, so
a schedule without provenance cannot be used to value a historical fill at all.

Pure stdlib + numpy. No network, no file I/O, no argv: fetching and artifact-writing live in
`scripts/screen_venue_subsidy.py`, so every rule below is testable without a venue. Zero promotion
authority.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np

__all__ = [
    "CONSTRUCTIONS",
    "COUNTERFACTUALS",
    "MIN_TIER_DAYS",
    "NOT_READABLE",
    "REFUSED",
    "FeeSchedule",
    "FeeTier",
    "Fill",
    "RebateCapture",
    "TierReachability",
    "attributed_counterfactual",
    "net_execution_bps_series",
    "net_rebate_capture",
    "tier_reachability",
]

#: The ONE string this desk uses for "the input for this row is not present on this machine".
#: Copied verbatim from `libs.execution.economics` so a reader never has to decide whether two
#: spellings mean the same thing. It names the READER's state, not the money's -- and it is never
#: 0.0, because a zero in an execution report is a claim that money did not move.
NOT_READABLE = "NOT-READABLE-HERE"

#: The verdict when the net cannot be computed. A refusal is the DELIVERABLE in that state, not an
#: error path: reporting a gross rebate instead would be the fee-fire shape all over again.
REFUSED = "REFUSED-NET-UNTESTABLE"

#: Consecutive days the desk's own volume must have SAT INSIDE a tier before its rebate is treated
#: as reachable. One day above a 30-day-volume threshold is a spike, not a tier: the rebate accrues
#: only while the tier holds, and a capture rate extrapolated from a single qualifying day is the
#: same arithmetic error as annualising one good week.
MIN_TIER_DAYS = 20

#: THE TWO COUNTERFACTUALS. Which one a fill belongs to decides whether its rebate is income, and
#: nothing else in this module matters more.
COUNTERFACTUALS = (
    # The trade happened for a reason that does not reference the rebate (an incumbent strategy's
    # own entry/exit). The round trip was going to be paid for anyway, so the rebate is genuine
    # incremental income and the incremental cost of earning it is zero.
    "INCUMBENT",
    # The trade exists in order to earn the rebate. Its ENTIRE round-trip cost is the cost of
    # earning it, and the net is what remains after that cost. This is the churn case.
    "REBATE_SEEKING",
    # The fill carries no attribution. Treated as REBATE_SEEKING, because assuming INCUMBENT would
    # let an unattributed tape claim the whole rebate as free money -- the exact error the fee fire
    # made. Conservative in the only direction that cannot lose the desk cash.
    "UNATTRIBUTED",
)


@dataclass(frozen=True)
class FeeTier:
    """One venue fee tier WITH the window it was in force. Negative maker bps = a rebate paid TO us.

    `effective_from` / `effective_to` are timezone-aware datetimes or None. A None `effective_from`
    means the schedule row carries no effective date -- which is the common case when a venue
    publishes only its CURRENT table -- and such a row can never value a historical fill (see
    `FeeSchedule.tier_at`). That is deliberate: an undated schedule applied to old fills prices the
    past at today's rates, and the error is invisible in the output.
    """

    venue: str
    tier: str
    maker_bps: float
    taker_bps: float
    min_30d_volume_usd: float
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    source_url: str = ""
    retrieved_utc: str = ""

    def __post_init__(self) -> None:
        for name in ("effective_from", "effective_to"):
            v = getattr(self, name)
            if v is not None and v.tzinfo is None:
                raise ValueError(f"{name} must be timezone-aware")

    @property
    def is_rebate(self) -> bool:
        """True when the maker leg is PAID rather than charged. Strict: zero is not a rebate."""
        return float(self.maker_bps) < 0.0

    @property
    def rebate_bps(self) -> float:
        """Rebate magnitude in bps of notional, 0.0 when the tier charges the maker instead."""
        return max(0.0, -float(self.maker_bps))

    def covers(self, when: datetime) -> bool:
        """Was this tier in force at `when`? An undated row covers NOTHING."""
        if self.effective_from is None:
            return False
        if when.tzinfo is None:
            raise ValueError("`when` must be timezone-aware")
        if when < self.effective_from:
            return False
        return not (self.effective_to is not None and when >= self.effective_to)

    def as_dict(self) -> dict[str, Any]:
        return {
            "venue": self.venue, "tier": self.tier,
            "maker_bps": float(self.maker_bps), "taker_bps": float(self.taker_bps),
            "is_rebate": self.is_rebate, "rebate_bps": self.rebate_bps,
            "min_30d_volume_usd": float(self.min_30d_volume_usd),
            "effective_from": (self.effective_from.isoformat()
                               if self.effective_from is not None else NOT_READABLE),
            "effective_to": (self.effective_to.isoformat()
                             if self.effective_to is not None else "open"),
            "source_url": self.source_url or NOT_READABLE,
            "retrieved_utc": self.retrieved_utc or NOT_READABLE,
        }


@dataclass(frozen=True)
class FeeSchedule:
    """One venue's tiers. `tier_at` is the only legitimate way to price a fill."""

    venue: str
    tiers: tuple[FeeTier, ...] = ()

    def tier_at(self, volume_30d_usd: float, when: datetime) -> FeeTier | None:
        """The tier in force at `when` for a 30-day volume. None when the schedule cannot say.

        NONE IS A REAL ANSWER AND IT IS THE IMPORTANT ONE. Falling back to "the current tier" or
        "tier 0" would let an undated or partial schedule value every historical fill anyway, and
        the resulting rebate total would look exactly like a measured one. The caller's honest move
        on None is to leave the term unmeasured and let the net refuse.
        """
        live = [t for t in self.tiers if t.covers(when) and
                float(volume_30d_usd) >= float(t.min_30d_volume_usd)]
        if not live:
            return None
        return max(live, key=lambda t: float(t.min_30d_volume_usd))

    def dated_fraction(self) -> float:
        """Share of tiers carrying an effective date. 0.0 = the schedule cannot price history."""
        if not self.tiers:
            return 0.0
        return sum(1 for t in self.tiers if t.effective_from is not None) / len(self.tiers)

    def best_rebate_tier(self) -> FeeTier | None:
        """The richest rebate tier on the sheet, whether or not the desk can reach it."""
        rebates = [t for t in self.tiers if t.is_rebate]
        return max(rebates, key=lambda t: t.rebate_bps) if rebates else None


@dataclass(frozen=True)
class Fill:
    """One own-fill, normalised. `fee_usd` is POSITIVE when WE PAID -- the executor's own sign.

    `fee_usd is None` is the state that matters most and it is the state this desk is actually in:
    the executor's tape (`libs/execution/execution_tape`) records event, symbol, notional, leg modes
    and slippage, but NOT the commission the venue charged -- that lives in the venue income ledger
    (`binance_testnet.commission_events`), behind keys. A rebate is a FEE OUTCOME, so a tape without
    fees cannot measure one however many fills it holds.
    """

    ts: datetime
    venue: str
    symbol: str
    notional_usd: float
    is_maker: bool
    fee_usd: float | None = None
    counterfactual: str = "UNATTRIBUTED"
    slip_bps: float | None = None

    def __post_init__(self) -> None:
        if self.ts.tzinfo is None:
            raise ValueError("Fill.ts must be timezone-aware")
        if self.counterfactual not in COUNTERFACTUALS:
            raise ValueError(f"counterfactual must be one of {COUNTERFACTUALS}")


@dataclass(frozen=True)
class TierReachability:
    """Did the desk's OWN volume reach a rebate tier, and for how long. Never a recommendation.

    `verdict` is one of:
      REACHED                       trailing 30-day volume sat at or above the tier for at least
                                    MIN_TIER_DAYS days.
      NOT-EARNABLE-AT-CURRENT-SIZE  the tier exists and the desk's observed volume does not reach
                                    it. THIS IS A KILL. Under R0143 it is explicitly not an
                                    argument to trade more or larger: size is not a growth lever.
      NO-REBATE-TIER                the venue's sheet has no tier that pays the maker at all.
      NOT-READABLE-HERE             own fills or the schedule are absent, so nothing was measured.
    """

    venue: str
    tier: str | None
    days_at_or_above: int
    max_30d_volume_usd: float | None
    required_30d_volume_usd: float | None
    verdict: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "venue": self.venue, "tier": self.tier or NOT_READABLE,
            "days_at_or_above": int(self.days_at_or_above),
            "max_30d_volume_usd": (float(self.max_30d_volume_usd)
                                   if self.max_30d_volume_usd is not None else NOT_READABLE),
            "required_30d_volume_usd": (float(self.required_30d_volume_usd)
                                        if self.required_30d_volume_usd is not None
                                        else NOT_READABLE),
            "verdict": self.verdict,
            "r0143": ("a tier the desk does not already reach is a KILL, never a reason to add "
                      "size or leverage -- geometric growth peaks at Kelly f* and falls after it"),
        }


def _rolling_30d_volume(fills: Sequence[Fill]) -> list[tuple[datetime, float]]:
    """(day, trailing-30-day notional) for every day on which the desk traded. Causal by build."""
    if not fills:
        return []
    ordered = sorted(fills, key=lambda f: f.ts)
    days = sorted({f.ts.date() for f in ordered})
    out: list[tuple[datetime, float]] = []
    for d in days:
        end = datetime.combine(d, datetime.min.time(), tzinfo=ordered[0].ts.tzinfo)
        start_ts = end.timestamp() - 30.0 * 86400.0
        vol = sum(float(f.notional_usd) for f in ordered
                  if start_ts <= f.ts.timestamp() <= end.timestamp() + 86400.0)
        out.append((end, vol))
    return out


def tier_reachability(schedule: FeeSchedule | None,
                      fills: Sequence[Fill] | None) -> TierReachability:
    """Measure -- never recommend -- whether the desk's own flow reaches a rebate tier."""
    venue = schedule.venue if schedule is not None else "?"
    if schedule is None or not schedule.tiers or fills is None or not fills:
        return TierReachability(venue, None, 0, None, None, NOT_READABLE)
    target = schedule.best_rebate_tier()
    if target is None:
        return TierReachability(venue, None, 0, None, None, "NO-REBATE-TIER")
    series = _rolling_30d_volume(fills)
    if not series:
        return TierReachability(venue, target.tier, 0, None,
                                float(target.min_30d_volume_usd), NOT_READABLE)
    need = float(target.min_30d_volume_usd)
    days = sum(1 for _, v in series if v >= need)
    peak = max(v for _, v in series)
    verdict = "REACHED" if days >= MIN_TIER_DAYS else "NOT-EARNABLE-AT-CURRENT-SIZE"
    return TierReachability(venue, target.tier, days, float(peak), need, verdict)


def attributed_counterfactual(fills: Sequence[Fill]) -> str:
    """The counterfactual the WHOLE fill set must be valued under. Conservative by construction.

    A set is INCUMBENT only when EVERY fill in it is individually attributed as incumbent. One
    unattributed fill drags the set to REBATE_SEEKING, because the alternative -- majority voting,
    or averaging the two treatments -- would let a mostly-unattributed tape claim most of its
    rebate as free money. There is no cheap way to be sure a trade would have happened anyway, and
    pretending otherwise is precisely the mistake this class exists to avoid.
    """
    if not fills:
        return "UNATTRIBUTED"
    kinds = {f.counterfactual for f in fills}
    return "INCUMBENT" if kinds == {"INCUMBENT"} else "REBATE_SEEKING"


@dataclass(frozen=True)
class RebateCapture:
    """The NET result. Every money term is `float | None`; None renders as NOT-READABLE-HERE.

    THE ONE INVARIANT: `net_usd` is not None ONLY when the rebate side AND the incremental
    round-trip cost side were both measured. There is deliberately no accessor that exposes
    `gross_rebate_usd` without `headline()` having first had the chance to refuse -- callers are
    expected to render `as_dict()`, whose `verdict` is REFUSED whenever the net is unavailable.
    """

    venue: str
    window_start: datetime | None
    window_end: datetime | None
    counterfactual: str
    n_fills: int
    maker_notional_usd: float | None
    gross_rebate_usd: float | None
    incremental_roundtrip_cost_usd: float | None
    net_usd: float | None
    missing: tuple[str, ...] = ()
    reachability: TierReachability | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    def headline(self) -> str:
        """REFUSED, or a NET statement. Never a gross one."""
        if self.net_usd is None:
            return (f"{REFUSED}: {self.venue} rebate capture cannot be stated net -- missing "
                    f"{', '.join(self.missing) if self.missing else 'an unnamed input'}. "
                    "A gross number is not reported, because a rebate earned by trades that "
                    "would not otherwise have happened is churn, not income.")
        sign = "net income" if self.net_usd > 0 else "net LOSS"
        return (f"{self.venue}: {sign} ${self.net_usd:,.2f} over the window under the "
                f"{self.counterfactual} counterfactual, AFTER the round-trip cost of the trades "
                f"required to earn it.")

    def as_dict(self) -> dict[str, Any]:
        """Render for an artifact. THE GROSS FIGURE IS SUPPRESSED WHENEVER THE NET IS UNAVAILABLE.

        This is the load-bearing line of the module. Printing a gross rebate beside a REFUSED
        verdict looks like transparency and is not: the number is the only thing a reader carries
        away, and once it exists in an artifact it gets quoted without its caveat. A rebate earned
        by trades that would not otherwise have happened is churn, so a gross figure with no cost
        side is not a partial answer -- it is the wrong answer, and it is the exact arithmetic that
        made the 2026-07 fee fire look like a business. So the field is replaced by the refusal
        itself, and there is no accessor anywhere in this module that returns it unguarded.
        """
        def _m(x: float | None) -> Any:
            return float(x) if x is not None else NOT_READABLE
        refused = self.net_usd is None
        return {
            "venue": self.venue,
            "window_start": (self.window_start.isoformat()
                             if self.window_start is not None else NOT_READABLE),
            "window_end": (self.window_end.isoformat()
                           if self.window_end is not None else NOT_READABLE),
            "counterfactual": self.counterfactual,
            "n_fills": int(self.n_fills),
            "maker_notional_usd": _m(self.maker_notional_usd),
            "gross_rebate_usd": (
                "SUPPRESSED -- a gross rebate is not reported without its cost side"
                if refused else _m(self.gross_rebate_usd)),
            "incremental_roundtrip_cost_usd": _m(self.incremental_roundtrip_cost_usd),
            "net_usd": _m(self.net_usd),
            "verdict": REFUSED if refused else "NET-MEASURED",
            "missing": list(self.missing),
            "reachability": (self.reachability.as_dict()
                             if self.reachability is not None else NOT_READABLE),
            "notes": list(self.notes),
            "gross_is_never_reported_alone": (
                "the desk's 2026-07 fee fire ($1,750 commission against ~$126 of logged "
                "round-trips) is what a gross rebate number looks like when the cost side is "
                "left out"),
        }


def net_rebate_capture(*, venue: str, fills: Sequence[Fill] | None,
                       schedule: FeeSchedule | None,
                       roundtrip_cost_usd: float | None = None,
                       window: tuple[datetime, datetime] | None = None) -> RebateCapture:
    """Value a fill set NET, or refuse and say exactly which input is missing.

    THE ARITHMETIC, and the counterfactual decides which line applies:

      INCUMBENT        net = gross rebate. The round trip was paid for by a decision that did not
                       reference the rebate, so the incremental cost of earning it is zero. This
                       branch requires EVERY fill to be individually attributed; see
                       `attributed_counterfactual`.
      REBATE_SEEKING   net = gross rebate - the FULL round-trip cost of the trades that earned it.
                       If that cost is not supplied, the net is None and the capture REFUSES.

    `roundtrip_cost_usd` is a parameter with no default value of its own on the churn branch -- it
    is not defaulted to zero anywhere, because a zero cost is a claim that money did not move.

    Refusals are ALSO produced when the rebate side cannot be valued: no schedule, an undated
    schedule (which cannot price a historical fill), no rebate tier, no fills, or fills lacking the
    venue-charged fee. Each of those appends its own line to `missing`.
    """
    missing: list[str] = []
    notes: list[str] = []
    reach = tier_reachability(schedule, fills)

    if schedule is None or not schedule.tiers:
        missing.append("per-venue fee schedule with maker-rebate tiers")
    elif schedule.dated_fraction() <= 0.0:
        missing.append("EFFECTIVE DATES on the fee schedule (an undated sheet prices history at "
                       "today's rates, and the error is invisible in the output)")
    elif schedule.best_rebate_tier() is None:
        missing.append(f"any maker-REBATE tier at {venue} (the published sheet charges the maker, "
                       "so there is no rent to capture at this venue)")

    if fills is None or not fills:
        missing.append("own fill records proving the tier is reachable at the desk's size")
        return RebateCapture(venue, None, None, "UNATTRIBUTED", 0, None, None, None, None,
                             tuple(missing), reach, tuple(notes))

    ordered = sorted(fills, key=lambda f: f.ts)
    w_start = window[0] if window is not None else ordered[0].ts
    w_end = window[1] if window is not None else ordered[-1].ts
    inwin = [f for f in ordered if w_start <= f.ts <= w_end]
    counterfactual = attributed_counterfactual(inwin)
    if counterfactual != "INCUMBENT":
        notes.append("fills are not all attributed to a decision independent of the rebate, so "
                     "the whole set is valued as REBATE_SEEKING -- the conservative branch")

    maker = [f for f in inwin if f.is_maker]
    maker_notional = float(sum(f.notional_usd for f in maker)) if maker else 0.0

    gross: float | None = None
    if schedule is not None and schedule.tiers and reach.verdict == "REACHED":
        vol30 = dict(_rolling_30d_volume(inwin))
        per_fill: list[float] = []
        priced = True
        for f in maker:
            day = datetime.combine(f.ts.date(), datetime.min.time(), tzinfo=f.ts.tzinfo)
            tier = schedule.tier_at(vol30.get(day, 0.0), f.ts)
            if tier is None:
                priced = False
                break
            per_fill.append(float(f.notional_usd) * tier.rebate_bps / 1e4)
        if priced and per_fill:
            gross = float(sum(per_fill))
        elif not priced:
            missing.append("a tier in force at the fill's own timestamp (the schedule's effective "
                           "windows do not cover part of the fill window)")
    elif reach.verdict == "NOT-EARNABLE-AT-CURRENT-SIZE":
        missing.append(f"tier attainment: the desk's own volume reaches the rebate tier on "
                       f"{reach.days_at_or_above} day(s), below the {MIN_TIER_DAYS}-day floor. "
                       "Under R0143 this is a KILL, not a reason to add size")

    if any(f.fee_usd is None for f in maker):
        missing.append("venue-charged fee per fill (the executor's tape records notional, leg "
                       "mode and slippage but NOT commission; that lives in the venue income "
                       "ledger behind keys)")

    cost = float(roundtrip_cost_usd) if roundtrip_cost_usd is not None else None
    if counterfactual == "INCUMBENT":
        cost = 0.0
        notes.append("INCUMBENT counterfactual: the round trip was paid for by a decision that "
                     "did not reference the rebate, so the INCREMENTAL cost of earning it is zero")
    elif cost is None:
        missing.append("round-trip cost of the trades required to earn the rebate (spread, taker "
                       "legs, slippage) -- without it only a GROSS number exists, and a gross "
                       "number is refused")

    net = (gross - cost) if (gross is not None and cost is not None and not missing) else None
    return RebateCapture(venue, w_start, w_end, counterfactual, len(inwin),
                         maker_notional, gross, cost, net, tuple(missing), reach, tuple(notes))


def net_execution_bps_series(fills: Sequence[Fill], days: Sequence[datetime]) -> np.ndarray:
    """Per-day NET execution economics in bps of notional -- the screen's ONLY target.

    net_bps[d] = -( sum(fee_usd) + sum(|slip_bps| * notional / 1e4) ) / sum(notional) * 1e4

    SIGN: positive means the desk was PAID to trade that day, i.e. rebates exceeded every cost it
    can see. The executor's own convention is "positive bps ALWAYS MEANS WE PAID", so it is negated
    exactly once, here, and the direction is stated in the artifact.

    NaN -- never 0.0 -- on any day whose fills lack a venue-charged fee. A day of trading whose
    commission was not readable is not a day of free trading, and a zero there would let the very
    absence this class is blocked by read as a favourable result.
    """
    out = np.full(len(days), np.nan)
    if not fills:
        return out
    by_day: dict[Any, list[Fill]] = {}
    for f in fills:
        by_day.setdefault(f.ts.date(), []).append(f)
    for i, d in enumerate(days):
        rows = by_day.get(d.date())
        if not rows:
            continue
        notional = float(sum(f.notional_usd for f in rows))
        if notional <= 0.0 or any(f.fee_usd is None for f in rows):
            continue
        fees = float(sum(f.fee_usd for f in rows if f.fee_usd is not None))
        slip = float(sum(abs(f.slip_bps) * f.notional_usd / 1e4
                         for f in rows if f.slip_bps is not None))
        out[i] = -(fees + slip) / notional * 1e4
    return out


def _tier_rate_series(schedule: FeeSchedule, fills: Sequence[Fill],
                      days: Sequence[datetime]) -> np.ndarray:
    """Rebate bps in force on each day at the desk's own trailing volume. NaN where undated."""
    vol30 = dict(_rolling_30d_volume(fills))
    out = np.full(len(days), np.nan)
    for i, d in enumerate(days):
        tier = schedule.tier_at(vol30.get(d, 0.0), d)
        if tier is not None:
            out[i] = tier.rebate_bps
    return out


def _tier_headroom_series(schedule: FeeSchedule, fills: Sequence[Fill],
                          days: Sequence[datetime]) -> np.ndarray:
    """log(trailing 30d volume / the best rebate tier's threshold). NaN when either is unknown."""
    target = schedule.best_rebate_tier()
    out = np.full(len(days), np.nan)
    if target is None or float(target.min_30d_volume_usd) <= 0.0:
        return out
    vol30 = dict(_rolling_30d_volume(fills))
    for i, d in enumerate(days):
        v = vol30.get(d)
        if v is not None and v > 0.0:
            out[i] = float(np.log(v / float(target.min_30d_volume_usd)))
    return out


#: PRE-REGISTERED CONSTRUCTION SET -- two, fixed, named before any result. Both are computable ONLY
#: from a dated schedule plus own fills, which is the point: there is no construction here that a
#: public fee page alone can feed, because the census's own note says the load-bearing missing input
#: is evidence the desk can REACH the tier, and only its own fills can supply that.
CONSTRUCTIONS: dict[str, Any] = {
    "rebate_rate_in_force": _tier_rate_series,
    "tier_headroom": _tier_headroom_series,
}


def daily_grid(fills: Iterable[Fill]) -> list[datetime]:
    """Every UTC day the desk traded, ascending. The screen's index; no gaps are interpolated."""
    rows = list(fills)
    if not rows:
        return []
    tz = rows[0].ts.tzinfo
    return [datetime.combine(d, datetime.min.time(), tzinfo=tz)
            for d in sorted({f.ts.date() for f in rows})]
