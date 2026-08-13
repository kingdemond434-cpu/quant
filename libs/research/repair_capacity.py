"""REPAIR CAPACITY -- the service rate behind the queue length (R0330 / R0075 remainder, L1.28b).

L1.28b was written from an arrival-vs-service comparison (lambda/mu ~4) and the desk can see only
one side of it. check_conversion publishes the QUEUE: backlog, past_due, arrivals and dispositions
per day. Nothing publishes the CAPACITY: how long a row actually takes to repair, what share of
raised rows ever get fixed, and whether the stock is growing. Without those the desk cannot tell
whether repair capacity it just added is working -- only that the queue is long, which it would be
either way. Per L1.28a an unmeasured rate counts as ZERO, so all three counted as zero.

THREE MEASUREMENT TRAPS THIS MODULE EXISTS TO NOT FALL INTO. Each was measured on the real ledger
before a line of the producer was written, and each would have published a confidently wrong number.

1. SURVIVORSHIP. The obvious MTTR -- mean(disposed - raised) over disposed rows -- conditions on
   having been disposed, which is the event whose timing is being measured. Measured 2026-08-12:
   42.8% of rows are still in the backlog (censored), the completed-only median reads 3.37 days,
   and the censoring-aware Kaplan-Meier median is 5.27 -- the naive figure understates the true
   median by 36% of it (equivalently, the true median is 56% longer than the naive one).
   64 of the 83 open rows had ALREADY been waiting longer than the "typical" repair time it
   reported. A desk reading 3.4 days would conclude its repair loop was fast while the majority of
   its live queue had already outlived that estimate. KM is used instead, and the 75th percentile
   is reported as NOT-REACHED rather than extrapolated when more than a quarter are still waiting.

2. THE IDLE-DAY DENOMINATOR. The ledger is bursty: measured 2026-08-07 through 08-10, four
   consecutive days with ZERO arrivals and ZERO dispositions, because no worker session ran at
   all. A per-calendar-day service rate averages those in as "fixed nothing today", which conflates
   "we worked and repaired nothing" with "no observation". It would make the metric deteriorate the
   longer the desk is quiet and turn a capacity measure into a cadence measure. Rates are therefore
   per ACTIVE day -- a day carrying at least one ledger event -- and the idle days are reported, not
   hidden. This is L1.48 applied to the desk's own instrumentation: evidence is the clock, and a
   shortfall is reported in observations rather than in days.

3. FIX IS NOT DISPOSITION. L1.28b(b) makes a reasoned rejection a conversion, and it is right: the
   queue really did drain. But "P(fix)" is a capacity question, and a rejection consumes no repair
   capacity. Counting them together would let the desk raise its apparent repair rate by rejecting
   more, which is the denominator trick one level in. Both are published, separately and named.

MEASURES ONLY. Nothing here promotes, sizes, gates or throttles anything, and no threshold in it
can turn a failure into a pass. Its entire effect is to make "we are repairing faster" a checkable
claim instead of an impression.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

__all__ = [
    "HORIZON_DAYS",
    "TERMINAL_STATUSES",
    "WINDOW_DAYS",
    "Capacity",
    "km_median",
    "measure",
    "parse_ts",
]

#: Statuses that mean the row has LEFT the backlog. Deliberately a copy rather than an import:
#: scripts/check_conversion.py and libs/research/capability_ratchet.py already carry this set, and
#: a test asserts all three agree, so drift is caught by a failing test rather than by a heavy
#: import of a 1500-line module for one frozenset. NOTE `scheduled` is absent on purpose -- a
#: scheduled row is still owed work and check_conversion counts it in the backlog.
TERMINAL_STATUSES = frozenset({"implemented", "rejected", "retired", "done", "screened"})

#: The window P(fix) is asked over. 14 days matches libs/research/recommendation_forecast.base_rate
#: so the desk cannot end up with two different definitions of the same probability.
HORIZON_DAYS = 14.0

#: Trailing window for the flow rates. 14 days matches HORIZON_DAYS and is short enough to MOVE
#: when the repair loop changes, which the lifetime average structurally cannot. While the ledger
#: itself is younger than about two windows the figure is still dominated by the ledger's birth
#: burst -- `stock_growth_note` says so out loud rather than letting the reader assume otherwise.
WINDOW_DAYS = 14.0

#: Below this many completed observations a distribution statistic is noise wearing a number.
#: Matches the desk's convention of publishing INSUFFICIENT rather than a figure.
MIN_EVENTS = 8


@dataclass(frozen=True)
class Capacity:
    """Every field is either a measurement or None. None means UNMEASURED and never zero."""

    status: str
    mttr_days: float | None            # Kaplan-Meier median -- the headline, censoring-aware
    mttr_naive_days: float | None      # completed-only median, published to expose the bias
    mttr_p75_days: float | None        # None = NOT-REACHED, a real answer
    censored_frac: float | None
    p_fix: float | None                # P(implemented within HORIZON_DAYS | eligible)
    p_disposed: float | None           # P(left the backlog at all) -- rejections included
    stock_growth_per_active_day: float | None
    n_rows: int
    n_events: int
    n_censored: int
    n_active_days: int
    n_window_active_days: int
    n_idle_days: int
    n_negative_latency: int
    stock_growth_note: str
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "mttr_days": self.mttr_days,
            "mttr_naive_days": self.mttr_naive_days,
            "mttr_p75_days": self.mttr_p75_days,
            "censored_frac": self.censored_frac,
            "p_fix": self.p_fix,
            "p_disposed": self.p_disposed,
            "stock_growth_per_active_day": self.stock_growth_per_active_day,
            "horizon_days": HORIZON_DAYS,
            "window_days": WINDOW_DAYS,
            "stock_growth_note": self.stock_growth_note,
            "n_window_active_days": self.n_window_active_days,
            # THE DENOMINATORS, PUBLISHED (L1.57). A rate whose denominator the reader cannot see
            # is an opinion, and every one of these can be zero for a different reason.
            "n_rows": self.n_rows,
            "n_events": self.n_events,
            "n_censored": self.n_censored,
            "n_active_days": self.n_active_days,
            "n_idle_days": self.n_idle_days,
            "n_negative_latency": self.n_negative_latency,
            "detail": self.detail,
        }


def parse_ts(value: Any) -> datetime | None:
    """ISO-8601 or nothing. Naive stamps are coerced to UTC, matching check_conversion."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def km_median(obs: Sequence[tuple[float, int]], quantile: float = 0.5) -> float | None:
    """Kaplan-Meier quantile of time-in-backlog. None means NOT REACHED, never 'no delay'.

    obs is (duration_days, event) where event=1 means the row left the backlog and event=0 means
    it is still waiting and its true duration is only known to be AT LEAST this long. Dropping the
    censored rows instead -- the naive MTTR -- is the survivorship trap the module docstring
    measures at 3.37 days against a true 5.27 on the real ledger.

    Returned as None when survival never falls to the quantile, which is the honest reading of "we
    do not yet know how long the slow tail takes": extrapolating past the last observation would
    manufacture a figure out of rows that have not finished waiting.
    """
    if not obs:
        return None
    ordered = sorted(obs)
    at_risk = len(ordered)
    surv = 1.0
    i = 0
    target = 1.0 - quantile
    while i < len(ordered):
        t = ordered[i][0]
        deaths = censored = 0
        j = i
        while j < len(ordered) and ordered[j][0] == t:
            if ordered[j][1] == 1:
                deaths += 1
            else:
                censored += 1
            j += 1
        if deaths and at_risk > 0:
            surv *= 1.0 - deaths / at_risk
            if surv <= target + 1e-12:
                return round(t, 3)
        at_risk -= deaths + censored
        i = j
    return None


def _active_days(stamps: Iterable[datetime]) -> set[Any]:
    return {t.date() for t in stamps}


def measure(rows: Sequence[dict[str, Any]], *, now: datetime | None = None) -> Capacity:
    """The three repair-capacity rates, or an honest refusal.

    A row with no parseable `raised` stamp is skipped rather than defaulted -- an invented arrival
    time would land in the latency distribution as a real observation.
    """
    now = now or datetime.now(tz=UTC)
    if not rows:
        return Capacity("UNMEASURED", None, None, None, None, None, None, None,
                        0, 0, 0, 0, 0, 0, 0, "",
                        "no ledger rows -- an empty ledger is UNMEASURED, never a clean board")

    obs: list[tuple[float, int]] = []      # (days_in_backlog, left_backlog)
    completed: list[float] = []
    events: list[datetime] = []
    negative = 0
    n_rows = 0

    for row in rows:
        raised = parse_ts(row.get("raised"))
        if raised is None:
            continue
        n_rows += 1
        events.append(raised)
        terminal = row.get("status") in TERMINAL_STATUSES
        disposed = parse_ts(row.get("disposed"))
        if terminal and disposed is not None:
            latency = (disposed - raised).total_seconds() / 86400.0
            if latency < 0:
                # DISPOSED BEFORE RAISED. 15 such rows exist, all legacy backfills whose two
                # stamps came from different sources. Averaging them in drags the mean toward
                # zero; silently clamping to 0 does the same thing while looking tidy. Excluded
                # and COUNTED, so the exclusion is visible rather than a quiet correction.
                negative += 1
                continue
            events.append(disposed)
            obs.append((latency, 1))
            completed.append(latency)
        else:
            # Still in the backlog: censored at its current age. `scheduled` lands here by design.
            obs.append(((now - raised).total_seconds() / 86400.0, 0))

    if not obs:
        return Capacity("UNMEASURED", None, None, None, None, None, None, None,
                        n_rows, 0, 0, 0, 0, 0, negative, "",
                        f"{n_rows} row(s) carry no usable raised/disposed pair")

    n_events = len(completed)
    n_censored = sum(1 for _, e in obs if e == 0)

    day_set = _active_days(events)
    first = min(events).date()
    span_days = (now.date() - first).days + 1
    n_active = len(day_set)
    n_idle = max(0, span_days - n_active)

    # STOCK GROWTH, per ACTIVE day, over a TRAILING WINDOW. Two choices here, both load-bearing.
    #
    # Windowed, not lifetime: the question this metric exists to answer is "is the repair capacity
    # the desk just added working", and a lifetime average cannot answer it. Measured 2026-08-12
    # the lifetime figure is +19.3 rows/active day, dominated entirely by the ledger's birth burst
    # (150 and 131 arrivals on 07-31 and 08-01) -- a number that will still read +19 next month no
    # matter what the repair loop does.
    #
    # Per ACTIVE day, not per calendar day: four consecutive days in this very window carried zero
    # arrivals AND zero dispositions because no session ran. Calendar-averaging scores a quiet
    # stretch as improving capacity, turning a capacity measure into a cadence measure (L1.48).
    w_start = now - timedelta(days=WINDOW_DAYS)
    w_events = [t for t in events if t >= w_start]
    w_active = len(_active_days(w_events))
    w_arrivals = sum(1 for r in rows if (t := parse_ts(r.get("raised"))) and t >= w_start)
    w_departures = sum(1 for r in rows
                       if r.get("status") in TERMINAL_STATUSES
                       and (t := parse_ts(r.get("disposed"))) and t >= w_start)
    stock_growth = (w_arrivals - w_departures) / w_active if w_active else None
    # THE CAVEAT THAT KEEPS THE NUMBER HONEST WHILE THE LEDGER IS YOUNG. A trailing window can only
    # separate current capacity from history once history extends past it. Tuning the window until
    # the figure looked reasonable would be fitting the instrument to the data; saying which regime
    # the number is in costs nothing and stops it being read as a clean current rate.
    ledger_age = (now - min(events)).total_seconds() / 86400.0 if events else 0.0
    if stock_growth is None:
        note = "no active ledger day inside the window -- UNMEASURED, not zero"
    elif ledger_age < 2 * WINDOW_DAYS:
        note = (f"the ledger is {ledger_age:.1f}d old against a {WINDOW_DAYS:.0f}d window, so this "
                "still carries the ledger's birth burst and is not yet a clean current rate")
    else:
        note = f"trailing {WINDOW_DAYS:.0f}d over {w_active} active day(s)"

    # P(FIX) and P(DISPOSED). Eligible = raised long enough ago that the horizon has actually
    # elapsed; asking of a row raised yesterday whether it was fixed within 14 days is a question
    # that cannot yet have an answer, and counting it as a miss understates the rate.
    cutoff = now - timedelta(days=HORIZON_DAYS)
    eligible = fixed = drained = 0
    for row in rows:
        raised = parse_ts(row.get("raised"))
        if raised is None or raised > cutoff:
            continue
        eligible += 1
        disposed = parse_ts(row.get("disposed"))
        if disposed is None or row.get("status") not in TERMINAL_STATUSES:
            continue
        latency = (disposed - raised).total_seconds() / 86400.0
        if not 0 <= latency <= HORIZON_DAYS:
            continue
        drained += 1
        if row.get("status") == "implemented":
            fixed += 1

    p_fix = fixed / eligible if eligible >= MIN_EVENTS else None
    p_disposed = drained / eligible if eligible >= MIN_EVENTS else None

    thin = n_events < MIN_EVENTS
    mttr = None if thin else km_median(obs)
    naive = None if thin else round(sorted(completed)[len(completed) // 2], 3)
    p75 = None if thin else km_median(obs, quantile=0.75)

    if thin:
        status = "INSUFFICIENT"
        detail = (f"{n_events} completed observation(s), fewer than {MIN_EVENTS} -- a latency "
                  "distribution on this many is noise wearing a number")
    elif mttr is None:
        status = "MEASURED"
        detail = (f"{n_events} completed of {len(obs)} ({n_censored} still waiting); the KM median "
                  "is NOT REACHED -- more than half the rows raised have not left the backlog, so "
                  "the typical repair time is longer than the observation window, not short")
    else:
        bias = "" if naive is None else (
            f"; the completed-only median reads {naive}d, understating by "
            f"{(mttr - naive) / mttr * 100:.0f}% because it conditions on having been disposed")
        detail = (f"KM median {mttr}d over {n_events} completed and {n_censored} censored "
                  f"({n_censored / len(obs) * 100:.1f}% still waiting){bias}")
        status = "MEASURED"

    return Capacity(
        status=status,
        mttr_days=mttr,
        mttr_naive_days=naive,
        mttr_p75_days=p75,
        censored_frac=round(n_censored / len(obs), 4),
        p_fix=None if p_fix is None else round(p_fix, 4),
        p_disposed=None if p_disposed is None else round(p_disposed, 4),
        stock_growth_per_active_day=(None if stock_growth is None
                                     else round(stock_growth, 3)),
        n_rows=n_rows,
        n_events=n_events,
        n_censored=n_censored,
        n_active_days=n_active,
        n_window_active_days=w_active,
        n_idle_days=n_idle,
        n_negative_latency=negative,
        stock_growth_note=note,
        detail=detail,
    )


def p_fix_ratio(cap: Capacity) -> float | None:
    """The ratchet-shaped view: P(fix) is already a fraction in [0,1] where higher is better.

    Exposed as its own function so the ratchet extractor never has to reach into the artifact's
    shape, and so a change to what "fix" means has exactly one place to happen.
    """
    if cap.p_fix is None or not math.isfinite(cap.p_fix):
        return None
    return max(0.0, min(1.0, cap.p_fix))
