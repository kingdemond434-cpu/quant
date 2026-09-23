"""WHAT THE BACKLOG COSTS, RANKED -- the queue depth carrying a number instead of a count.

R0526. Every risk breach on this desk is priced to the cent and not one DELAY ever carried a
figure, so L1.27's question -- "am I protecting capital, or avoiding uncertainty?" -- was
rhetorical for the one population it matters most for: 100% of the desk's scheduled rows are
blocked on ENGINEERING, not on evidence. `roi_bps` sits on every ledger row and was never once
multiplied by age anywhere in scripts/ or libs/ (verified 2026-08-19), so a row worth 400bps
rotting for 20 days and a row worth 2bps rotting for 20 days arrived at the reader as the same
unit of "backlog".

IT IS A RANK-ORDERING SIGNAL AND NEVER A DOLLAR CLAIM. `roi_bps` is a desk estimate and
`days_overdue` is measured, so the product is an ESTIMATE x A MEASUREMENT carrying the estimate's
whole error. It is published to ORDER the queue, and any reader treating the total as money is
reading it wrong -- which is why `as_dict` publishes no currency and the unit is spelled
`bps_days` everywhere it appears.

THE CONTAMINATION THAT DECIDES THE DESIGN, measured on the live ledger before a line was written.
A naive `sum(roi_bps x days_overdue)` over the 121 past-due rows totals 12,437 bps-days and
**38.6% of it comes from four rows** whose `roi_bps` is not a return estimate at all: they are
rank ordinals wearing a bps label (R0477's 9999/9000/8000/7000 population, predating the
`scripts/recommendations.py` tripwire that now refuses them). The top contributor is a row FOURTEEN
HOURS late scoring 3,904 purely because somebody once typed 6500 into a field meaning "urgent".
Multiplying an ordinal by a day is arithmetic on a quantity that has no cardinal meaning, and
`libs/research/recommendation_forecast.py` had already recorded the same trap: those values "are
de-facto rank ordinals wearing a bps label, so conditioning on them would score noise."

So the population is SPLIT rather than summed, and every member is accounted for:

  PRICED    -- 0 < roi_bps < ORDINAL_BPS. The only rows in the total.
  ORDINAL   -- roi_bps >= ORDINAL_BPS. R0477's legacy population. Counted, never multiplied.
  UNPRICED  -- roi_bps absent, None, or 0. Counted, NEVER read as a zero-cost row (L1.28a):
               "this row costs nothing to delay" and "nobody estimated what this row is worth"
               are different claims and only one is evidence.

A TOTAL WITHOUT ITS DENOMINATOR IS AN OPINION (L1.57), and here the denominator is the whole
finding: 29 of 121 past-due rows carry no estimate at all and 13 carry a literal zero, so the
published total speaks for roughly two thirds of the queue and says so in `coverage`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

#: R0477's threshold, reused rather than re-derived so the two cannot drift. Every value ever seen
#: in the rank-wearing-bps population was >= 7500 while the largest MEASURED estimate on the ledger
#: is 400, so a four-digit "bps" is an ordinal. `scripts/recommendations.py` refuses new ones at
#: this exact bound; the legacy rows it predates are what this constant exists to quarantine.
ORDINAL_BPS = 1000.0

#: An untriaged row is owed this long after it is raised. Mirrors `scripts/check_conversion.py`
#: and `scripts/recommendations.py`; passed in by the caller so this module never disagrees.
GRACE_H = 24.0


@dataclass(frozen=True)
class Priced:
    """One row's delay, priced. `bps_days` is an ordering score, not money."""

    rid: str
    roi_bps: float
    days_overdue: float
    summary: str = ""

    @property
    def bps_days(self) -> float:
        return self.roi_bps * self.days_overdue


@dataclass(frozen=True)
class DelayCost:
    """The backlog's delay bill, split by whether the row could be priced at all."""

    priced: tuple[Priced, ...] = ()
    n_ordinal: int = 0
    n_unpriced: int = 0
    n_no_clock: int = 0

    @property
    def total_bps_days(self) -> float:
        return sum(p.bps_days for p in self.priced)

    @property
    def n_rows(self) -> int:
        """Every row considered -- the denominator, so the total cannot read as the whole queue."""
        return len(self.priced) + self.n_ordinal + self.n_unpriced + self.n_no_clock

    @property
    def coverage(self) -> float:
        """Share of past-due rows the total actually speaks for. 0.0 when nothing was scanned."""
        return (len(self.priced) / self.n_rows) if self.n_rows else 0.0

    def top(self, n: int = 5) -> tuple[Priced, ...]:
        return tuple(sorted(self.priced, key=lambda p: -p.bps_days)[:n])

    def as_dict(self, *, top: int = 5) -> dict[str, Any]:
        """The published shape. UNMEASURED when nothing could be priced -- never a bare 0.0.

        A zero total from an empty queue and a zero total from a queue nobody could price are
        opposite facts, and only the first is good news.
        """
        measured = bool(self.priced)
        return {
            "delay_cost_bps_days": round(self.total_bps_days, 1) if measured else None,
            "delay_cost_status": "MEASURED" if measured else (
                "UNMEASURED" if self.n_rows else "EMPTY-QUEUE"),
            "delay_cost_unit": "bps x days -- a RANK-ORDERING signal, never a dollar claim",
            "delay_cost_rows_priced": len(self.priced),
            "delay_cost_rows_ordinal": self.n_ordinal,
            "delay_cost_rows_unpriced": self.n_unpriced,
            "delay_cost_rows_no_clock": self.n_no_clock,
            "delay_cost_rows_attempted": self.n_rows,
            "delay_cost_coverage": round(self.coverage, 3),
            "delay_cost_top": [
                {"id": p.rid, "bps_days": round(p.bps_days, 1), "roi_bps": p.roi_bps,
                 "days_overdue": round(p.days_overdue, 2), "summary": p.summary[:90]}
                for p in self.top(top)
            ],
        }


def _days_overdue(row: dict[str, Any], now: datetime,
                  parse: Any, grace_h: float) -> float | None:
    """How long this row has been owed. None when it has no clock at all.

    TWO CLOCKS, because the ledger genuinely has two and collapsing them would invent a number.
    A SCHEDULED row is late relative to its `due`; an untriaged `open` row is late relative to
    `raised + grace`. A CHRONIC row (re-snoozed twice) is owed regardless of date and may carry a
    due date in the future -- it has no meaningful overdue span, so it returns None and is counted
    as no-clock rather than silently priced at zero.
    """
    due = parse(row.get("due"))
    if due is not None:
        secs = (now - due).total_seconds()
        return secs / 86400.0 if secs > 0 else None
    raised = parse(row.get("raised"))
    if raised is not None:
        secs = (now - (raised + timedelta(hours=grace_h))).total_seconds()
        return secs / 86400.0 if secs > 0 else None
    return None


def measure(rows: list[dict[str, Any]], *, now: datetime | None = None,
            parse_ts: Any = None, grace_h: float = GRACE_H) -> DelayCost:
    """Price every past-due row, and account for every row that could not be priced.

    `rows` is the PAST-DUE population -- this module does not decide who is late, the fence does.
    """
    now = now or datetime.now(tz=UTC)
    parse = parse_ts or _default_parse
    priced: list[Priced] = []
    ordinal = unpriced = no_clock = 0
    for row in rows:
        # L1.60: every member is accounted for before any skip, so the denominator cannot lose
        # rows silently. `n_rows` sums the four buckets, so a row can only leave by being counted.
        days = _days_overdue(row, now, parse, grace_h)
        if days is None:
            no_clock += 1
            continue
        raw = row.get("roi_bps")
        if not isinstance(raw, int | float) or isinstance(raw, bool) or raw <= 0:
            unpriced += 1
            continue
        if float(raw) >= ORDINAL_BPS:
            ordinal += 1
            continue
        priced.append(Priced(rid=str(row.get("id") or "?"), roi_bps=float(raw),
                             days_overdue=days, summary=str(row.get("summary") or "")))
    return DelayCost(priced=tuple(priced), n_ordinal=ordinal,
                     n_unpriced=unpriced, n_no_clock=no_clock)


def _default_parse(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        d = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)
