"""WHERE THE MID WENT AFTER EACH FILL -- the only measurement that separates a cost from a signal.

TWO NUMBERS THAT LOOK ALIKE AND MEAN OPPOSITE THINGS. `mt5desk/markout.py` already measures what
the desk ASKED for against what it GOT: `entry_slip = (fill - intended) * direction`. That is
execution quality against the desk's own intent, and it is the right first question. It cannot
answer the second one, which is what a microstructure desk exists to ask:

    EFFECTIVE COST     (fill - mid_at_fill) * direction        what crossing the quote cost
    MARKOUT(h)         (mid_at_fill_plus_h - mid_at_fill) * direction
                                                               where the market went next
    REALISED SPREAD(h) effective_cost - markout(h)             what the other side KEPT

A fill whose markout is strongly NEGATIVE was adversely selected: the mid ran away from the trade
in the seconds after it, so the quote that looked available was about to move and the desk paid a
spread to stand in front of it. A fill whose markout is POSITIVE was a good fill -- the desk took
liquidity ahead of a move it was right about, and the spread was a fee it should happily pay
again. THE SPREAD IS IDENTICAL IN BOTH CASES. Only the markout tells them apart, and no amount of
slippage measurement can, because slippage is measured against an intent and this is measured
against the market.

That distinction is what changes an order. Toxic cohorts want a limit rather than a market order,
or a later entry, or a different hour; clean ones want to keep crossing and should not be slowed
down by a cost rule fitted to the toxic ones' average.

THE POINT-IN-TIME TRAP THIS FILE IS BUILT AROUND, and it is the one that quietly ruins a markout
study. Markout at horizon h is not knowable until h has elapsed. A cohort mean taken over every
fill, including this morning's, silently scores the newest fills at whatever the truncated tape
gives -- usually a partial or zero move -- and drags the estimate toward "no adverse selection"
exactly as the sample grows. So `cohort` REFUSES any fill whose horizon extends past the tape's
last quote, counts the refusals by name, and reports the surviving n. A markout number without
its n and its as-of is not a measurement.

WHAT IT REFUSES TO INFER

  * AN UNFILLED INTENT IS NOT A ZERO-MARKOUT FILL. It never traded; it has no mid to mark out
    from. `markout.py` records the same refusal for slippage and the reason is the same.
  * A FILL WITH NO TAPE COVERING IT IS UNMEASURED, NEVER ZERO. If the tick tape has no quote
    within `MAX_STALE_MS` of the fill, the mid at fill is unknown and every quantity above is
    unknown with it. Substituting the last quote from an hour earlier would produce a number
    whose error is the size of the effect.
  * A COHORT BELOW `MIN_FILLS` IS UNMEASURED. Markout is noisy at the single-fill level by
    construction -- it is a few seconds of a random walk plus an effect -- and three fills cannot
    separate them (L1.28a).

NO I/O AND NO PANDAS IN THE CORE. Every function below takes ARRAYS and PLAIN ROWS, so the whole
module is testable with no tape, which matters on a desk whose tape lives on another machine.
`load_fills` is the only reader and it opens one jsonl.

ZERO PROMOTION AUTHORITY. It measures fills. It does not size, gate, veto or choose an order type
-- it publishes the evidence an execution policy would need, and the policy stays where policies
live.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

#: Horizons in milliseconds. The short end prices the quote the desk crossed; the long end prices
#: whether it was right. Both are needed: a fill can be clean at 1s and toxic at 5m, which is a
#: signal about the SIGNAL rather than about the execution.
HORIZONS_MS: tuple[int, ...] = (1_000, 5_000, 30_000, 60_000, 300_000)

#: A quote older than this is not a quote for this fill. Beyond it the mid is unknown, and the
#: error of substituting a stale one is the size of the effect being measured.
MAX_STALE_MS = 2_000

#: Below this a cohort is UNMEASURED. Markout at a few seconds is mostly a random walk; separating
#: the effect from it needs a sample, and three fills is not one.
MIN_FILLS = 20

BUY, SELL = 1, -1


@dataclass(frozen=True)
class Fill:
    """One executed deal, in the only fields a markout needs."""

    ts_ms: int
    price: float
    direction: int                 # +1 bought, -1 sold
    symbol: str = ""
    sleeve: str = ""
    order_type: str = ""           # market | limit | stop -- the thing a policy would change
    ticket: str = ""

    @property
    def hour(self) -> int:
        return int((self.ts_ms // 3_600_000) % 24)


@dataclass(frozen=True)
class Marked:
    """One fill priced against the tape, or an explicit refusal to price it."""

    fill: Fill
    mid_at_fill: float | None
    effective_cost_pts: float | None
    markout_pts: dict[int, float | None] = field(default_factory=dict)
    why: str = ""

    @property
    def measured(self) -> bool:
        return self.mid_at_fill is not None

    def realised_spread_pts(self, horizon_ms: int) -> float | None:
        """What the other side kept: the cost the desk paid, less where the market then went."""
        mk = self.markout_pts.get(horizon_ms)
        if self.effective_cost_pts is None or mk is None:
            return None
        return round(self.effective_cost_pts - mk, 6)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticket": self.fill.ticket, "symbol": self.fill.symbol,
            "sleeve": self.fill.sleeve, "order_type": self.fill.order_type,
            "ts_ms": self.fill.ts_ms, "hour": self.fill.hour,
            "direction": self.fill.direction, "price": self.fill.price,
            "mid_at_fill": self.mid_at_fill,
            "effective_cost_pts": self.effective_cost_pts,
            "markout_pts": {str(h): v for h, v in sorted(self.markout_pts.items())},
            "realised_spread_pts": {str(h): self.realised_spread_pts(h)
                                    for h in sorted(self.markout_pts)},
            "measured": self.measured, "why": self.why,
        }


def _mid_at(ts_ms: np.ndarray, mid: np.ndarray, at_ms: int) -> float | None:
    """The mid from the last quote AT OR BEFORE `at_ms`, or None if there is none close enough.

    AT OR BEFORE, NEVER THE NEAREST. A nearest-quote lookup would happily return a quote from
    AFTER the instant asked about, which at a one-second horizon is most of the answer -- the
    markout would be reading the move it is supposed to be predicting.
    """
    if ts_ms.size == 0:
        return None
    pos = int(np.searchsorted(ts_ms, at_ms, side="right")) - 1
    if pos < 0:
        return None
    if at_ms - int(ts_ms[pos]) > MAX_STALE_MS:
        return None
    return float(mid[pos])


def mark(fill: Fill, ts_ms: np.ndarray, bid: np.ndarray, ask: np.ndarray, *,
         point: float, horizons: tuple[int, ...] = HORIZONS_MS) -> Marked:
    """Price one fill against the tape. Every unknown is None with a reason, never a zero.

    `point` IS ALWAYS PASSED IN. `mt5desk/universe.py` records what a units bug costs on a mixed
    universe -- a JPY cross came out 150x more expensive than a dollar pair and would have been
    excluded as unaffordable. Nothing here guesses a unit.
    """
    if point <= 0:
        return Marked(fill, None, None, dict.fromkeys(horizons),
                      "point size must be positive; nothing here guesses a unit")
    mid = (np.asarray(bid, dtype=float) + np.asarray(ask, dtype=float)) / 2.0
    ts = np.asarray(ts_ms, dtype=np.int64)

    m0 = _mid_at(ts, mid, fill.ts_ms)
    if m0 is None:
        return Marked(fill, None, None, dict.fromkeys(horizons),
                      f"no quote within {MAX_STALE_MS}ms of the fill: the mid at fill is unknown, "
                      "and so is every quantity derived from it")

    cost = round((fill.price - m0) * fill.direction / point, 6)
    last = int(ts[-1])
    out: dict[int, float | None] = {}
    for h in horizons:
        # THE POINT-IN-TIME REFUSAL. A horizon that extends past the tape is not knowable yet, and
        # scoring it from a truncated tape would report "no adverse selection" for every recent
        # fill -- biasing the estimate toward clean exactly as the sample grows.
        if fill.ts_ms + h > last:
            out[h] = None
            continue
        mh = _mid_at(ts, mid, fill.ts_ms + h)
        out[h] = None if mh is None else round((mh - m0) * fill.direction / point, 6)
    return Marked(fill, m0, cost, out, "")


def cohort(marked: list[Marked], horizon_ms: int, *, min_fills: int = MIN_FILLS) -> dict[str, Any]:
    """Aggregate one horizon over one cohort, with its n and its refusals attached.

    THE MEDIAN AND NOT THE MEAN for the headline. One fill during a release print carries a
    markout tens of times the typical one, and a mean over twenty fills is that one fill. The mean
    is reported beside it because the two disagreeing is itself the finding: a cohort whose mean
    is far worse than its median is being hurt by rare events, which wants a different fix than
    one that is uniformly toxic.
    """
    usable = [m for m in marked if m.measured and m.markout_pts.get(horizon_ms) is not None]
    refused = {
        "no_tape_at_fill": sum(1 for m in marked if not m.measured),
        "horizon_not_elapsed": sum(1 for m in marked
                                   if m.measured and m.markout_pts.get(horizon_ms) is None),
    }
    if len(usable) < min_fills:
        return {"status": "UNMEASURED", "n": len(usable), "min_fills": min_fills,
                "horizon_ms": horizon_ms, "refused": refused,
                "why": (f"{len(usable)} usable fills against a floor of {min_fills}; markout at "
                        "a few seconds is mostly a random walk and a small sample cannot "
                        "separate the effect from it")}

    mk = np.array([m.markout_pts[horizon_ms] for m in usable], dtype=float)
    cost = np.array([m.effective_cost_pts for m in usable], dtype=float)
    rs = cost - mk
    return {
        "status": "MEASURED", "n": len(usable), "horizon_ms": horizon_ms, "refused": refused,
        "markout_median_pts": round(float(np.median(mk)), 4),
        "markout_mean_pts": round(float(mk.mean()), 4),
        "effective_cost_median_pts": round(float(np.median(cost)), 4),
        "realised_spread_median_pts": round(float(np.median(rs)), 4),
        # THE SHARE, not a verdict. "62% of these fills were followed by the mid moving against
        # them" is a fact; "this cohort is toxic" is a decision, and it is not this file's.
        "share_adverse": round(float((mk < 0).mean()), 4),
        "why": ("markout is where the MID went after the fill, priced from the tape and not from "
                "the intent: negative means the quote the desk crossed was about to move"),
    }


def by_cohort(marked: list[Marked], key: str = "sleeve", *,
              horizon_ms: int = 30_000, min_fills: int = MIN_FILLS) -> dict[str, Any]:
    """Split by the thing an execution policy could actually change.

    `sleeve`, `order_type`, `hour` and `symbol` are the four axes a policy has levers on: which
    strategy, market versus limit, when, and where. Splitting by anything else produces a number
    with no available action attached to it.
    """
    if key not in ("sleeve", "order_type", "hour", "symbol"):
        raise ValueError(f"{key!r} is not an axis an execution policy has a lever on")
    groups: dict[str, list[Marked]] = {}
    for m in marked:
        groups.setdefault(str(getattr(m.fill, key)), []).append(m)
    return {k: cohort(v, horizon_ms, min_fills=min_fills) for k, v in sorted(groups.items())}


def load_fills(path: Path) -> list[Fill]:
    """The desk's own deals, from the deals journal. The only reader in this module.

    A ROW THAT DOES NOT CARRY A PRICE, A STAMP AND A SIDE IS SKIPPED, not defaulted. A fill with
    a guessed direction contributes its markout with the sign reversed, which is worse than
    contributing nothing: it moves the estimate toward zero and looks like data.
    """
    out: list[Fill] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        ts, px = row.get("ts_ms"), row.get("price")
        side = str(row.get("side") or row.get("direction") or "").strip().lower()
        direction = (BUY if side in ("buy", "long", "1", "+1") else
                     SELL if side in ("sell", "short", "-1") else 0)
        if ts is None or px is None or direction == 0:
            continue
        try:
            out.append(Fill(ts_ms=int(ts), price=float(px), direction=direction,
                            symbol=str(row.get("symbol") or ""),
                            sleeve=str(row.get("sleeve") or ""),
                            order_type=str(row.get("order_type") or ""),
                            ticket=str(row.get("ticket") or "")))
        except (TypeError, ValueError):
            continue
    return out


def census(marked: list[Marked], *, min_fills: int = MIN_FILLS) -> dict[str, Any]:
    """The picture: every horizon over everything, and the split by the levers a policy has."""
    return {
        "n_fills": len(marked),
        "n_priced": sum(1 for m in marked if m.measured),
        "horizons_ms": list(HORIZONS_MS),
        "min_fills": min_fills,
        "all": {str(h): cohort(marked, h, min_fills=min_fills) for h in HORIZONS_MS},
        "by_order_type": by_cohort(marked, "order_type", min_fills=min_fills) if marked else {},
        "by_sleeve": by_cohort(marked, "sleeve", min_fills=min_fills) if marked else {},
        "by_hour": by_cohort(marked, "hour", min_fills=min_fills) if marked else {},
        "rule": (
            "markout is measured against the MID FROM THE TAPE, never against the intent: an "
            "intent says what the desk wanted and the mid says what the market did. A horizon "
            "that has not elapsed is refused rather than scored from a truncated tape, because "
            "scoring it biases every recent fill toward clean exactly as the sample grows"),
    }
