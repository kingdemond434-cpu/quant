"""SHADOW -> LIVE LATENCY, MEASURED -- and the only two honest ways to shorten it.

THE PRINCIPAL'S CONCERN (2026-07-30), stated exactly: the promotion process must not be so slow
that *"by the time they reach live the capital is already outgrown its capacity."* At 100%/yr the
book doubles in 253 days; at the desk's stretch pace it doubles in weeks. An edge that needs 90
days of clock plus an unbounded queue wait can be a rounding error on arrival. That is not caution
-- caution that guarantees a zero is just a slower way of declining.

`libs.autodiscovery.validation.capacity_race` already answers "does this edge reach live before the
book outgrows it?" -- but it takes `validation_days` as an ARGUMENT, and until now every caller was
a test passing a hardcoded 90. The race was therefore run against an assumption. This module
measures the number instead, decomposed, with the PROVENANCE of each component attached, because
an unmeasured component quoted as measured is precisely the reality gap L2.10 exists to catch.

THREE COMPONENTS, and the middle one is the one everybody forgets:
  CLOCK       the pre-registered forward window itself.
  QUEUE WAIT  time spent waiting for a free forward slot. The cohort is capped at
              MAX_FORWARD_SLOTS=12 (that cap is what keeps the Holm bar fixed), so when every slot
              is occupied a new candidate accrues NOTHING while its capacity decays. This is real
              latency, it is invisible in any per-candidate view, and it is usually the largest
              term when the desk is busy.
  DECISION    clock completion -> a promotion decision actually taken.

=================================================================================================
THE ACCELERANT, AND THE TRAP INSIDE IT
=================================================================================================
L1.6 is not negotiable: the confirmation bar never loosens, and a DOA edge is NEVER fixed by a
shorter clock. So the only honest accelerants are (1) NOT QUEUEING -- run the slot now rather than
later, which costs nothing statistically -- and (2) MORE OBSERVATIONS PER DAY.

The second one is where a desk quietly deceives itself, so it is fenced here.

  * FOR EVENT-DRIVEN P&L -- funding settlements, auctions, rebalances, discrete cash flows -- a
    higher observation frequency means MORE ACTUAL EVENTS. Perp funding settles 3x daily, so an 8h
    panel accrues 3 realised payments per day instead of 1. The desk measured these at vif 1.008,
    i.e. essentially independent, so effective N genuinely triples and the same t-stat bar is
    reached in roughly a third of the wall clock. The BAR IS UNCHANGED; only the calendar moves.

  * FOR DIFFUSIVE P&L -- anything whose return is a price change -- it is FALSE. Estimating the
    drift of a diffusion depends on the HORIZON, not the sampling frequency: sampling a 90-day
    window hourly instead of daily gives 24x the rows and no additional information about the
    mean. (Merton 1980; it is why realised volatility converges under fine sampling and expected
    return does not.) A desk that "accelerates" a price-based signal by sampling faster has not
    accelerated anything -- it has manufactured a t-stat out of oversampling and loosened its own
    bar while believing it did the opposite.

So `frequency_accelerant` REFUSES to grant a speed-up unless the caller declares the P&L is
event-driven AND the event rate itself rises. Refusal is the default: an unknown process gets no
accelerant. This is the direction that costs a few days of calendar and cannot manufacture edge.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]

#: Design clock for a cohort candidate, in days. The cash-carry PRIMARY carries a measured 40-day
#: fast-track (run_cashcarry_shadow.py) because it was registered alone, before any cohort; a
#: cohort entrant carries the Holm correction and the full window.
DESIGN_CLOCK_DAYS = 90.0

#: Measured variance-inflation for 8h funding observations (gap #44). Near 1.0 => near-independent.
FUNDING_8H_VIF = 1.008

#: Observations per day at each supported cadence.
_CADENCE_PER_DAY = {"daily": 1.0, "8h": 3.0, "hourly": 24.0}


@dataclass(frozen=True)
class LatencyComponent:
    days: float
    provenance: str          # MEASURED | DESIGN | ESTIMATED
    detail: str


@dataclass(frozen=True)
class PipelineLatency:
    clock: LatencyComponent
    queue_wait: LatencyComponent
    decision: LatencyComponent
    generated: str = field(default_factory=lambda: datetime.now(tz=UTC).isoformat())

    @property
    def total_days(self) -> float:
        return self.clock.days + self.queue_wait.days + self.decision.days

    @property
    def fully_measured(self) -> bool:
        return all(c.provenance == "MEASURED"
                   for c in (self.clock, self.queue_wait, self.decision))

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_days": round(self.total_days, 1),
            "fully_measured": self.fully_measured,
            "generated": self.generated,
            "components": {name: {"days": round(c.days, 1), "provenance": c.provenance,
                                  "detail": c.detail}
                           for name, c in (("clock", self.clock), ("queue_wait", self.queue_wait),
                                           ("decision", self.decision))},
        }


def _slot_occupancy() -> tuple[int, int, list[str]]:
    """(occupied, cap, names). Import-guarded: a missing registry must not crash the queue."""
    try:
        from libs.research.slot_registry import MAX_FORWARD_SLOTS, derive_slots
    except ImportError:
        return 0, 12, []
    snap = derive_slots()
    slots = snap.get("slots", []) or []
    return len(slots), int(MAX_FORWARD_SLOTS), [str(s.get("name", "?")) for s in slots]


def queue_wait_days() -> LatencyComponent:
    """How long a NEW candidate waits before its clock can even start.

    THE TERM EVERYBODY FORGETS. The forward cohort is capped so the Holm bar stays fixed; when the
    cap is full, a new candidate accrues zero evidence while its capacity decays against a growing
    book. Per-candidate views never show this -- the candidate looks 'in progress' while it is
    actually parked. It is real latency and it belongs in the race.
    """
    occupied, cap, names = _slot_occupancy()
    free = cap - occupied
    if free > 0:
        return LatencyComponent(
            0.0, "MEASURED",
            f"{free}/{cap} forward slots free ({occupied} occupied) -- a new clock starts today")
    # Full cohort: the wait is until the longest-running clock completes. Without per-slot start
    # dates this is the design clock, and it is labelled as such rather than dressed as measured.
    return LatencyComponent(
        DESIGN_CLOCK_DAYS, "ESTIMATED",
        f"cohort FULL ({occupied}/{cap}: {', '.join(names[:6])}) -- a new candidate cannot start "
        f"a clock until one completes; upper-bounded by the design clock")


def clock_days(*, fast_track_eligible: bool = False) -> LatencyComponent:
    """The pre-registered forward window. Never shortened by this module -- only reported."""
    if fast_track_eligible:
        return LatencyComponent(
            40.0, "MEASURED",
            "40d fast-track (run_cashcarry_shadow.py): NW-t>=1.65 + fwd>=0.5x backtest + regime "
            "evidence. Applies to a PRE-REGISTERED PRIMARY registered before any cohort, which is "
            "why it is Holm-exempt -- it is not a shorter bar, it is a smaller family")
    return LatencyComponent(
        DESIGN_CLOCK_DAYS, "DESIGN",
        "design forward window for a cohort entrant (carries the Holm correction over all "
        "trailing-180d entrants including killed ones)")


def decision_lag_days() -> LatencyComponent:
    """Clock completion -> decision taken. Measured from the decision ledger when it has rows."""
    ledger = _ROOT / "data/decision_ledger.json"
    try:
        rows = json.loads(ledger.read_text("utf-8"))
        rows = rows.get("decisions", rows) if isinstance(rows, dict) else rows
    except (OSError, ValueError):
        rows = []
    lags: list[float] = []
    for r in rows if isinstance(rows, list) else []:
        raised, closed = r.get("raised") or r.get("opened"), r.get("closed") or r.get("decided")
        if not (raised and closed):
            continue
        try:
            lags.append((datetime.fromisoformat(str(closed))
                         - datetime.fromisoformat(str(raised))).total_seconds() / 86400.0)
        except ValueError:
            continue
    if len(lags) >= 3:
        lags.sort()
        med = lags[len(lags) // 2]
        return LatencyComponent(max(med, 0.0), "MEASURED",
                                f"median of {len(lags)} closed decision-ledger rows")
    # The cycle runs daily, so one day is the floor a decision can possibly take.
    return LatencyComponent(1.0, "ESTIMATED",
                            f"only {len(lags)} closed ledger rows (<3) -- floored at the daily "
                            "cycle cadence; re-measures automatically as the ledger fills")


def measure(*, fast_track_eligible: bool = False) -> PipelineLatency:
    return PipelineLatency(clock=clock_days(fast_track_eligible=fast_track_eligible),
                           queue_wait=queue_wait_days(), decision=decision_lag_days())


def frequency_accelerant(cadence: str, *, pnl_is_event_driven: bool,
                         event_rate_rises: bool, vif: float = FUNDING_8H_VIF) -> dict[str, Any]:
    """Wall-clock speed-up from observing faster -- GRANTED ONLY WHERE IT IS REAL.

    Returns the multiplier on effective sample size and the resulting wall-clock divisor, or a
    REFUSED verdict with the reason. Refusal is the default.

    The refusal is the entire value of this function. Granting a diffusive process a speed-up for
    finer sampling would loosen the confirmation bar while looking like an optimisation -- the
    exact shape of self-deception L1.6 and the two-stage law exist to prevent, and the shape a
    desk under time pressure is most likely to talk itself into.
    """
    per_day = _CADENCE_PER_DAY.get(cadence)
    if per_day is None:
        return {"granted": False, "divisor": 1.0,
                "reason": f"unknown cadence {cadence!r} -- no accelerant without a declared rate"}
    if per_day <= 1.0:
        return {"granted": False, "divisor": 1.0, "reason": "cadence is not faster than daily"}
    if not pnl_is_event_driven:
        return {"granted": False, "divisor": 1.0,
                "reason": "P&L is DIFFUSIVE (price-change). Drift estimation depends on the "
                          "HORIZON, not the sampling frequency -- finer sampling of the same "
                          "window adds rows and zero information about the mean. Granting a "
                          "speed-up here would manufacture a t-stat out of oversampling."}
    if not event_rate_rises:
        return {"granted": False, "divisor": 1.0,
                "reason": "P&L is event-driven but the EVENT RATE does not rise at this cadence "
                          "-- sampling between events resamples the same cash flows"}
    eff = per_day / max(vif, 1e-9)
    return {"granted": True, "divisor": eff, "effective_n_multiple": round(eff, 3),
            "reason": f"event-driven P&L at {per_day:.0f} events/day, vif {vif} -- effective N "
                      f"x{eff:.2f}, so the SAME t-stat bar is reached in 1/{eff:.2f} of the wall "
                      "clock. The bar is unchanged; only the calendar moves."}
