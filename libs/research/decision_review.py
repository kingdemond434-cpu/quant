"""Decision-ledger maturity: make every logged decision REVIEWABLE, so scoring has a queue.

The ledger's own policy says "the monthly governance review scores each matured entry so decision
QUALITY compounds". Measured 2026-07-26: 189 decisions, 3 with an outcome, and -- the mechanical
cause -- only 14 carrying a `review_due`. "Matured" was never defined, so 175 decisions could not
come due, ever. The scoring cadence was running against an empty queue and reporting no work.

This module derives a review date for every decision and classifies where each one stands. It
deliberately does NOT decide outcomes. Scoring a decision correct/wrong/unclear is a judgement
about the world, and a calibration ledger filled with machine-guessed outcomes is worse than an
empty one: the Brier score would then be confidently wrong about how well the desk decides, which
is the exact failure the ledger exists to prevent.

What it produces is the worklist. Resolution stays a deliberate act.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

#: Default maturity. The ledger's policy language is "the monthly governance review", so a
#: decision with no stated horizon comes due one month after it was taken.
DEFAULT_HORIZON_D = 30

#: A horizon named in the success metric wins over the default -- "by day 90: sim vs real"
#: means ninety days, and pulling it forward to thirty would score the decision before its own
#: stated evidence exists.
_HORIZON = re.compile(
    r"\bday\s*(?P<day>\d{1,3})\b"
    r"|\b(?P<d>\d{1,3})\s*[-\s]?(?:d|days?)\b"
    r"|\b(?P<w>\d{1,2})\s*[-\s]?(?:wk|weeks?)\b"
    r"|\b(?P<m>\d{1,2})\s*[-\s]?(?:mo|months?)\b",
    re.IGNORECASE,
)

_ID_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")

#: An outcome of this value means "logged but not actually scored yet".
_NON_OUTCOMES = {"", "pending", "tbd", "open", "n/a", "none", "-"}


def stated_horizon_days(text: str) -> int | None:
    """Longest horizon named in a success metric, in days. None when none is stated.

    LONGEST, not first: a metric reading "funding/day rises within 7d and holds 90d" is not
    settled at day 7. Taking the first match would score decisions early and systematically
    flatter the desk, because early readings are the ones taken while the change is fresh.
    """
    best: int | None = None
    for m in _HORIZON.finditer(text or ""):
        if m.group("day"):
            v = int(m.group("day"))
        elif m.group("d"):
            v = int(m.group("d"))
        elif m.group("w"):
            v = int(m.group("w")) * 7
        elif m.group("m"):
            v = int(m.group("m")) * 30
        else:
            continue
        if 1 <= v <= 730 and (best is None or v > best):
            best = v
    return best


def decision_date(row: dict[str, Any]) -> date | None:
    """The date the decision was taken, from its id prefix. None when unparseable."""
    m = _ID_DATE.match(str(row.get("id", "")))
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def is_scored(row: dict[str, Any]) -> bool:
    """Has this decision actually been scored? A placeholder outcome does not count."""
    return str(row.get("outcome", "")).strip().lower() not in _NON_OUTCOMES


@dataclass(frozen=True)
class Review:
    row_id: str
    taken: date | None
    due: date | None
    horizon_d: int
    source: str           # "explicit" | "success_metric" | "default" | "unknown"
    scored: bool
    state: str            # "scored" | "due" | "maturing" | "undatable"
    days_overdue: int

    @property
    def actionable(self) -> bool:
        return self.state == "due"


def review_for(row: dict[str, Any], today: date) -> Review:
    """Where this one decision stands. Never invents an outcome."""
    rid = str(row.get("id", "<no id>"))
    scored = is_scored(row)
    taken = decision_date(row)

    explicit = str(row.get("review_due", "")).strip()
    due: date | None = None
    source = "unknown"
    horizon = 0

    if explicit:
        try:
            due = date.fromisoformat(explicit[:10])
            source = "explicit"
        except ValueError:
            due = None
    if due is None and taken is not None:
        stated = stated_horizon_days(str(row.get("success_metric", "")))
        horizon = stated if stated is not None else DEFAULT_HORIZON_D
        source = "success_metric" if stated is not None else "default"
        due = taken + timedelta(days=horizon)
    if due is not None and taken is not None:
        horizon = (due - taken).days

    if scored:
        state = "scored"
    elif due is None:
        # no id date and no explicit review date: this row can never come due, and no derivation
        # can rescue it. Reported rather than silently defaulted to today.
        state = "undatable"
    elif due <= today:
        state = "due"
    else:
        state = "maturing"

    overdue = (today - due).days if (due is not None and state == "due") else 0
    return Review(row_id=rid, taken=taken, due=due, horizon_d=horizon, source=source,
                  scored=scored, state=state, days_overdue=overdue)


def reviews(rows: list[dict[str, Any]], today: date) -> list[Review]:
    return [review_for(r, today) for r in rows]


def backfill_plan(rows: list[dict[str, Any]], today: date) -> list[tuple[str, str, str]]:
    """Rows needing a derived `review_due` written in. (id, iso_date, source).

    Only rows with NO explicit date are touched. A date a human set is never overwritten, even
    when the derivation would disagree -- the point is to give the queue a floor, not to
    relitigate horizons somebody chose on purpose.
    """
    out: list[tuple[str, str, str]] = []
    for r in rows:
        if str(r.get("review_due", "")).strip():
            continue
        rv = review_for(r, today)
        if rv.due is not None:
            out.append((rv.row_id, rv.due.isoformat(), rv.source))
    return out


@dataclass(frozen=True)
class LedgerHealth:
    total: int
    scored: int
    due: int
    maturing: int
    undatable: int
    no_review_date: int
    oldest_overdue_d: int

    @property
    def scored_pct(self) -> float:
        return round(100.0 * self.scored / self.total, 1) if self.total else 0.0

    @property
    def verdict(self) -> str:
        if self.no_review_date:
            return (f"{self.no_review_date} of {self.total} decisions carry NO review date -- "
                    "they can never come due, so the scoring cadence has nothing to pull")
        if self.due:
            return (f"{self.due} decision(s) matured and unscored, oldest {self.oldest_overdue_d}d "
                    f"past due ({self.scored}/{self.total} scored)")
        return (f"queue clean: {self.scored}/{self.total} scored, {self.maturing} still maturing")


def health(rows: list[dict[str, Any]], today: date) -> LedgerHealth:
    rv = reviews(rows, today)
    due = [r for r in rv if r.state == "due"]
    return LedgerHealth(
        total=len(rv),
        scored=sum(1 for r in rv if r.state == "scored"),
        due=len(due),
        maturing=sum(1 for r in rv if r.state == "maturing"),
        undatable=sum(1 for r in rv if r.state == "undatable"),
        no_review_date=sum(1 for r, src in zip(rv, rows, strict=True)
                           if not str(src.get("review_due", "")).strip() and not r.scored),
        oldest_overdue_d=max((r.days_overdue for r in due), default=0),
    )


def confidence_profile(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The desk's stated-confidence distribution -- the thing calibration will test.

    Reported because it is striking on its own: 85% of decisions logged at 0.8-0.9 is the
    signature of an anchor, not of judgement varying with the problem. Unfalsifiable while
    outcomes are missing, and immediately testable once they are not -- which is the single
    most valuable thing this ledger could eventually tell the desk about itself.
    """
    vals = [float(r["confidence"]) for r in rows
            if isinstance(r.get("confidence"), (int, float))]
    if not vals:
        return {"n": 0}
    buckets: dict[str, int] = {}
    for v in vals:
        buckets[f"{round(v, 1):.1f}"] = buckets.get(f"{round(v, 1):.1f}", 0) + 1
    top = max(buckets.items(), key=lambda kv: kv[1])
    return {
        "n": len(vals),
        "mean": round(sum(vals) / len(vals), 3),
        "buckets": dict(sorted(buckets.items())),
        "modal_bucket": top[0],
        "modal_share_pct": round(100.0 * top[1] / len(vals), 1),
    }
