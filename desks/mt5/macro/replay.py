"""POINT-IN-TIME REPLAY -- nothing here sizes a position until it has been replayed honestly.

THE RULE. Information is released to the model only at `received_at` -- when the desk actually had
the bytes -- never at `happened_at` and never at `published_at`. The gap between those clocks is
the desk's blindness, and a replay that closes it is a replay that proves the desk can trade
information it did not have.

THE GUARD HAS TEETH, WHICH IS THE ONLY KIND WORTH HAVING. `PITGuardedReader` wraps the price
reader and RAISES `PITViolation` on any read past the replay clock. It does not clip, warn or
return None -- clipping is exactly how a backtest reads Friday's report on Wednesday and reports
an edge, and the desk's own `libs/research/information_decay.py` refuses a negative age for the
same reason. A leak in a macro replay is not a rounding error: the whole claim of this package is
that it reacts to information at arrival speed, so reading the future is reading the answer.

ONE DELIBERATE ASYMMETRY, AND IT IS NOT A LEAK. Prices BETWEEN `published_at` and `received_at`
are readable. That window is precisely what `priced.py` measures -- the move that happened while
the desk was blind -- and it is knowable at `received_at` because it is in the past by then.
Reading it is how the desk learns it was late. Reading past `received_at` is the violation.

WHAT THE REPLAY COVERS TODAY, SAID PLAINLY RATHER THAN IMPLIED. It covers whatever is in the
ledger. On this box the ledger is EMPTY, so the replay covers ZERO real historical events, and
`coverage()` says so in those words. The harness is exercised in tests against synthetic events
with known answers, which proves the MACHINERY -- ordering, the guard, the scoring path, the
refusal to authorise thin categories -- and proves nothing whatsoever about CPI, NFP, FOMC, ECB,
BOJ, oil shocks or geopolitical events, none of which this desk has yet recorded a single
instance of.

Filling that gap requires history the desk does not have: an archive of when each item was
PUBLICLY AVAILABLE, not when it happened. That is a licensed-archive purchase, and until it lands
no event category can pass `clearance()`, and `assess.py` will refuse capital authority to every
one of them. That is the correct behaviour and it is not a soft gate -- it is the reason nothing
in this package can size a position today.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .ledger import MIN_CATEGORY_N, EventLedger
from .prices import PriceReader, Quote
from .schema import EventRecord, Status, now_iso, parse_ts

__all__ = [
    "PITGuardedReader",
    "PITViolation",
    "ReplayReport",
    "clearance",
    "coverage",
    "default_scorer",
    "replay",
]


class PITViolation(RuntimeError):
    """A read of information that did not exist yet. Fatal by design."""


class PITGuardedReader:
    """A price reader frozen at `clock`. Every read past it raises.

    Wrapping rather than filtering: a filtered reader that silently returns fewer bars lets a
    leaky estimator quietly produce a weaker number, and the desk would never know the difference
    between "no leak" and "leak that returned little". A raise cannot be misread.
    """

    def __init__(self, inner: PriceReader, clock: datetime) -> None:
        self.inner = inner
        self.clock = clock
        self.violations: list[str] = []

    def _check(self, ts: datetime | None, what: str) -> None:
        if ts is not None and ts > self.clock:
            msg = (f"point-in-time violation: {what} at {ts.isoformat()} is after the replay "
                   f"clock {self.clock.isoformat()}")
            self.violations.append(msg)
            raise PITViolation(msg)

    def symbols(self) -> Sequence[str]:
        return self.inner.symbols()

    def bar_span_s(self, symbol: str) -> float | None:
        return self.inner.bar_span_s(symbol)

    def price_at(self, symbol: str, ts: datetime) -> Quote | None:
        self._check(ts, f"price_at({symbol})")
        return self.inner.price_at(symbol, ts)

    def returns_before(self, symbol: str, ts: datetime, n: int) -> Sequence[float]:
        self._check(ts, f"returns_before({symbol})")
        return self.inner.returns_before(symbol, ts, n)

    def bars(self, symbol: str, start: datetime | None = None,
             end: datetime | None = None) -> Sequence[Quote]:
        self._check(end, f"bars({symbol}) end")
        if end is None:
            return self.inner.bars(symbol, start, self.clock)
        return self.inner.bars(symbol, start, end)


@dataclass
class ReplayReport:
    n_events: int = 0
    n_scored: int = 0
    n_violations: int = 0
    violations: list[str] = field(default_factory=list)
    per_category: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    results: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "at": now_iso(), "n_events": self.n_events, "n_scored": self.n_scored,
            "n_violations": self.n_violations, "violations": self.violations[:20],
            "per_category": self.per_category, "errors": self.errors[:20],
            "clean": self.n_violations == 0 and not self.errors,
        }


def replay(records: Sequence[EventRecord], reader: PriceReader,
           scorer: Callable[[EventRecord, PITGuardedReader, list[EventRecord]], dict[str, Any]],
           *, strict: bool = True) -> ReplayReport:
    """Release each record at its own `received_at`, in order, and score it with what existed.

    `scorer` receives the record, a reader frozen at that instant, and the records the desk had
    already FINISHED SCORING -- `processed_at <= received_at`, not merely received. A model
    fitted on an event the desk was still scoring is a model fitted on its own future.
    """
    rep = ReplayReport()
    ordered = sorted(
        (r for r in records if parse_ts(r.received_at) is not None),
        key=lambda r: parse_ts(r.received_at))  # type: ignore[arg-type,return-value]
    rep.n_events = len(ordered)
    for rec in ordered:
        clock = parse_ts(rec.received_at)
        if clock is None:
            continue
        history = [h for h in ordered
                   if (parse_ts(h.processed_at) or parse_ts(h.received_at) or clock) <= clock
                   and h.event_id != rec.event_id]
        guarded = PITGuardedReader(reader, clock)
        try:
            out = scorer(rec, guarded, history)
        except PITViolation as ex:
            rep.n_violations += 1
            rep.violations.append(str(ex))
            if strict:
                raise
            continue
        except Exception as ex:  # a scorer bug must not read as a clean replay
            rep.errors.append(f"{rec.event_id}: {ex!r}")
            continue
        rep.n_scored += 1
        rep.per_category[rec.category] = rep.per_category.get(rec.category, 0) + 1
        rep.results.append({"event_id": rec.event_id, "category": rec.category, **out})
    return rep


def clearance(rep: ReplayReport, *, min_n: int = MIN_CATEGORY_N) -> tuple[list[str], list[str]]:
    """Which categories have survived replay with sample, and which have not. (cleared, refused)

    A clean replay is necessary and not sufficient: a category replayed six times cleanly has
    been replayed six times, which is not evidence about anything. Clearance needs both.
    """
    if rep.n_violations or rep.errors:
        return [], sorted(rep.per_category)
    cleared = sorted(c for c, n in rep.per_category.items() if n >= min_n)
    refused = sorted(c for c, n in rep.per_category.items() if n < min_n)
    return cleared, refused


def coverage(ledger: EventLedger | None = None,
             rep: ReplayReport | None = None) -> dict[str, Any]:
    """WHAT THE REPLAY COVERS AND WHAT IT DOES NOT -- written to be quotable without hedging."""
    led = ledger or EventLedger()
    rows = led.records()
    cleared, refused = clearance(rep) if rep is not None else ([], [])
    return {
        "at": now_iso(),
        "ledger_rows": len(rows),
        "categories_in_ledger": sorted({r.category for r in rows}),
        "replayed": (rep.to_dict() if rep is not None else None),
        "categories_cleared_for_capital": cleared,
        "categories_refused": refused,
        "covers": ("Every event IN THE LEDGER, released at its own received_at, scored against a "
                   "price reader that raises on any read past that instant."),
        "does_not_cover": [
            "Any event the desk never recorded. The ledger is the entire universe of this "
            "replay, and on this box it starts empty -- so today the replay covers ZERO "
            "historical CPI, NFP, FOMC, ECB, BOJ, oil-shock or geopolitical events.",
            "Availability times the desk never observed. Replaying an archive stamped with when "
            "an event HAPPENED rather than when it was PUBLICLY AVAILABLE would leak, so such "
            "an archive cannot be replayed here at all -- it is refused, not approximated.",
            "Execution. This replays the information path only; fills, slippage and the "
            "event-window cost distribution are the gateway's and the execution twin's ground.",
            "The pre-arrival window's own microstructure. With H1 as the fastest series for most "
            "instruments, a sub-hour pre-move is UNMEASURABLE rather than estimated.",
        ],
        "gate": ("assess.py refuses capital authority to any category not in "
                 "categories_cleared_for_capital. With an empty ledger that is every category, "
                 "which is why nothing in this package can size a position today."),
    }


def default_scorer(unpriced_key: str = "unpriced_fraction") -> Callable[
        [EventRecord, PITGuardedReader, list[EventRecord]], dict[str, Any]]:
    """A minimal scorer: re-derive the recorded unpriced fraction under the guard.

    Deliberately thin. Its job in the harness is to EXERCISE the point-in-time path -- if a
    scorer can produce the recorded number without tripping the guard, the number was obtainable
    at the time. A richer scorer belongs to whoever is validating a specific model.
    """

    def _score(rec: EventRecord, reader: PITGuardedReader,
               history: list[EventRecord]) -> dict[str, Any]:
        priced = rec.priced or {}
        return {
            "recorded": priced.get(unpriced_key),
            "status": priced.get("status", Status.UNMEASURED),
            "history_available": len(history),
            "reader_symbols": len(reader.symbols()),
        }

    return _score
