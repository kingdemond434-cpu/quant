"""FORWARD EVIDENCE AS A RATIO AND A LADDER, NOT A SINGLE VERDICT (R0601, L1.28a/L1.48).

WHAT WAS MISSING. `data/axis_shadow_state.json` already publishes a forward `ann_sharpe` per
clock. It publishes NOTHING about the screen Sharpe that candidate was admitted on, so the one
quantity that measures THIS DESK'S OWN SCREEN OPTIMISM -- forward Sharpe over screen Sharpe -- was
not persisted anywhere and therefore counted as zero (L1.28a). `data/axis_clock_registry.json`
stored `screen_ic` and dropped the Sharpe beside it; grep for `osISSharpeRatio`, `sharpe60` and
friends returned nothing across libs/ and scripts/ on 2026-08-20.

WHY THE RATIO PORTS WHERE THE THRESHOLD DOES NOT. `libs/validation/brain_calibration.py` correctly
refuses to let WorldQuant BRAIN's 1.25 Sharpe target become a gate here: it is US-equity, daily
rebalanced, dollar-neutral, on their PnL and annualisation conventions. A RATIO of two Sharpes is
dimensionless and those conventions cancel -- BUT ONLY IF BOTH HALVES WERE MEASURED THE SAME WAY.
That condition is load-bearing and is enforced below rather than assumed: Stage A annualises by
sqrt(365/horizon_days) (`axis_screen._sh`) and Stage B annualises by sqrt(365) on daily forward
observations (`run_axis_shadows._evaluate`), so a screen run at horizon_days=20 against a daily
forward clock differs by sqrt(20) = 4.47x. Dividing those two would publish a 4.5x annualisation
artifact as a measurement of overfitting. The desk imported the un-portable half of BRAIN once
already; publishing an unlike ratio would be importing the portable half wrongly.

THE LADDER IS IN OBSERVATIONS, NEVER DAYS (L1.48). BRAIN re-measures OOS Sharpe at 60/125/250/500
days. Those are not four arbitrary numbers -- against a ~250-day equity trading year they are
QUARTER, HALF, FULL and DOUBLE. That shape is what ports; the day-counts are an equity sampling
convention and copying them as days would import it as a law. Here the same shape is expressed as
fractions of the clock's OWN pre-registered decision point (`decision_at_obs`), so a fast clock and
a slow one are laddered on the same footing and neither is graded on a calendar it never ran on.

WHAT THIS IS NOT. No gate, no threshold, no promotion authority, no bar moved. Nothing below
returns a pass/fail and no caller may treat a ratio as one. It is a measurement duty only: it makes
"this desk's screen was 3x optimistic" distinguishable from "this desk has never measured its screen
optimism", which were byte-identical before.
"""
from __future__ import annotations

import math
from typing import Any

#: Quarter / half / full / double of the clock's pre-registered decision point -- the SHAPE of
#: BRAIN's 60/125/250/500 against a ~250-day equity year (0.24, 0.5, 1.0, 2.0), carried over as a
#: ratio so it survives the change of sampling convention. Ordered, deduplicated at use.
LADDER_FRACTIONS: tuple[float, ...] = (0.25, 0.5, 1.0, 2.0)

#: Below this a Sharpe denominator is not a measurement, it is a division by noise: a screen Sharpe
#: of 0.01 would turn a forward 0.5 into a "50x" that means nothing. Refused rather than published.
_MIN_DENOM = 0.05


def _ann_sharpe(arr: Any, periods_per_year: float = 365.0) -> float | None:
    """Annualised Sharpe of `arr`, or None when it cannot be formed.

    None, never 0.0: a zero-variance or too-short window has no Sharpe, and 0.0 is a MEASURED
    collapse. The two demand opposite readings and this desk has paid for merging them (L1.28a).
    """
    vals = [float(x) for x in arr]
    n = len(vals)
    if n < 2:
        return None
    mean = sum(vals) / n
    var = sum((v - mean) ** 2 for v in vals) / (n - 1)      # sample sd, matches numpy ddof=1
    sd = math.sqrt(var)
    if sd <= 0.0:
        return None
    return float(mean / sd * math.sqrt(periods_per_year))


def sharpe_ladder(arr: Any, decision_at_obs: int,
                  periods_per_year: float = 365.0) -> list[dict[str, Any]]:
    """Forward Sharpe re-measured at cumulative OBSERVATION checkpoints.

    Each rung is the Sharpe of the FIRST k observations, so the rungs are nested and a reader can
    watch an edge decay WHILE it is being confirmed -- which a single end-of-clock verdict cannot
    show (L1.19/L1.30). A rung the clock has not reached yet is emitted with `sharpe: null` and
    `reached: false` rather than omitted: a missing rung and an unreachable one must never be
    byte-identical (L1.60), and dropping them would let the ladder shrink its own denominator.
    """
    vals = [float(x) for x in arr]
    n = len(vals)
    point = max(int(decision_at_obs), 1)
    rungs: list[dict[str, Any]] = []
    seen: set[int] = set()
    for frac in LADDER_FRACTIONS:
        k = max(round(point * frac), 1)
        if k in seen:
            continue                    # a short decision point can collapse two rungs onto one
        seen.add(k)
        reached = n >= k and k >= 2
        rungs.append({
            "obs": k,
            "fraction_of_decision_point": frac,
            "reached": bool(reached),
            "sharpe": (round(s, 3) if reached
                       and (s := _ann_sharpe(vals[:k], periods_per_year)) is not None else None),
        })
    return rungs


def os_is_ratio(forward_sharpe: float | None, screen_sharpe: float | None, *,
                forward_horizon_days: float = 1.0,
                screen_horizon_days: float | None = None) -> dict[str, Any]:
    """Forward Sharpe / screen Sharpe -- the desk's own screen-optimism measurement.

    Returns {"ratio": float|None, "status": str, ...}. `status` is the whole value when `ratio` is
    None, because the four ways this can be unmeasurable demand four different repairs:

      MEASURED             -- both halves present and like-annualised.
      UNMEASURED-NO-SCREEN -- the candidate's screen Sharpe was never persisted. The repair is at
                              REGISTRATION (`axis_screen._register_clock`), not here. Every clock
                              registered before 2026-08-20 is in this state and that is honest.
      UNLIKE-ANNUALISATION -- both present, measured on different horizons, so the conventions do
                              NOT cancel and the quotient would be an annualisation artifact.
      DENOM-TOO-SMALL      -- |screen Sharpe| < _MIN_DENOM: division by noise.

    A ratio ABOVE 1.0 is not a success and BELOW 1.0 is not a failure; nothing here grades. The
    distribution of this number across the desk's screened candidates is the measurement (L1.29).
    """
    if screen_sharpe is None or forward_sharpe is None:
        return {"ratio": None, "status": "UNMEASURED-NO-SCREEN",
                "forward_sharpe": forward_sharpe, "screen_sharpe": screen_sharpe,
                "why": ("one half of the ratio was never persisted; repair at the registration "
                        "site, not by defaulting it to a number")}
    if screen_horizon_days is None or not math.isclose(
            float(screen_horizon_days), float(forward_horizon_days), rel_tol=1e-9):
        return {"ratio": None, "status": "UNLIKE-ANNUALISATION",
                "forward_sharpe": forward_sharpe, "screen_sharpe": screen_sharpe,
                "forward_horizon_days": forward_horizon_days,
                "screen_horizon_days": screen_horizon_days,
                "why": ("Stage A annualises by sqrt(365/horizon_days) and Stage B by sqrt(365) on "
                        "daily observations, so on different horizons the quotient is a "
                        "sqrt(horizon) artifact, not a measurement of screen optimism")}
    if abs(float(screen_sharpe)) < _MIN_DENOM:
        return {"ratio": None, "status": "DENOM-TOO-SMALL",
                "forward_sharpe": forward_sharpe, "screen_sharpe": screen_sharpe,
                "why": f"|screen Sharpe| < {_MIN_DENOM}: the quotient is division by noise"}
    return {"ratio": round(float(forward_sharpe) / float(screen_sharpe), 3), "status": "MEASURED",
            "forward_sharpe": forward_sharpe, "screen_sharpe": screen_sharpe,
            "horizon_days": float(forward_horizon_days)}


def coverage(records: Any) -> dict[str, Any]:
    """How many scored clocks carry a MEASURED ratio -- a RATCHET whose gap is the work queue.

    Publishes the ATTEMPTED count beside the measured one (L1.60): a clock skipped for want of a
    screen Sharpe must stay visible in the denominator, or coverage rises by losing its members.
    Zero scored clocks reads UNMEASURED, never 100% and never OK (L1.28a, L1.57).
    """
    rows = [r for r in records if isinstance(r, dict)]
    scored = [r for r in rows if isinstance(r.get("os_is_sharpe"), dict)]
    measured = [r for r in scored if r["os_is_sharpe"].get("status") == "MEASURED"]
    by_status: dict[str, int] = {}
    for r in scored:
        s = str(r["os_is_sharpe"].get("status") or "UNKNOWN")
        by_status[s] = by_status.get(s, 0) + 1
    if not scored:
        return {"status": "UNMEASURED", "scanned": len(rows), "measured": 0, "pct": None,
                "by_status": by_status,
                "why": "no scored clock carried an os_is_sharpe block -- absence is not 100%"}
    return {"status": "OK" if len(measured) == len(scored) else "PARTIAL",
            "scanned": len(scored), "measured": len(measured),
            "pct": round(100.0 * len(measured) / len(scored), 1),
            "by_status": by_status}
