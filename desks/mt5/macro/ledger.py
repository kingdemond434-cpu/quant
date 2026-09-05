"""THE EVENT LEDGER -- append-only, deduped, and the only thing here that must never lose a row.

WHY APPEND-ONLY AND WHY THAT IS NOT A DETAIL. Every learned quantity in this package is a
statistic over this file: a source's verification rate, a category's factor loadings, the
distribution of how much was already priced, the decay half-life that decides whether an
interrupt can ever pay. A ledger that is rewritten in place can be made to agree with any model
fitted on it, and nobody would be able to tell. It is opened in append mode, one JSON object per
line, and nothing in this package ever deletes or edits a line.

DEDUPE IS BY CONTENT, NOT BY ARRIVAL. `schema.content_id` hashes (source, title, url,
published_at), so a re-polled feed does not manufacture a second event -- but two DIFFERENT
sources reporting the same thing keep different ids, which is exactly what makes independent
confirmation countable in `credibility.py`. Collapsing them would silently destroy the evidence
that a claim was corroborated.

WHAT COUNTS AS SAMPLE. `category_stats` is the sample floor everything downstream consults, and
it counts only rows that have a MEASURED reaction attached -- a category with four hundred
recorded headlines and no measured reactions has n=0 for the purposes of any estimate. That
distinction is the difference between a ledger that is big and a ledger that is informative, and
conflating them is how a desk convinces itself it has evidence.

THE FIRST ROW IS THE POINT. On a box where the ledger is empty, every estimator in this package
returns UNMEASURED and every event is RECORDED_ONLY with no capital authority. That is not a
degraded mode to be engineered around; it is the correct state of a system that has not yet seen
anything, and the way out of it is rows, not code.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any

from .schema import EventRecord, Status, now_iso, parse_ts

DESK = Path(__file__).resolve().parents[1]
MACRO_DIR = DESK / "data" / "macro"
LEDGER_PATH = MACRO_DIR / "event_ledger.jsonl"

#: The floor below which a per-category statistic is UNMEASURED. Event conditioning multiplies
#: hypotheses enormously -- a "2x edge after CPI" found across twenty slices with n=6 each is
#: noise wearing a good number -- so this is a floor on the number of MEASURED REACTIONS in a
#: category, not on the number of headlines seen. It is never lowered to make a category
#: reportable; a category below it says UNMEASURED and stays there until it has sample.
MIN_CATEGORY_N = 30

#: Independent floor for source-level statistics. Lower than MIN_CATEGORY_N because a source's
#: verification rate is a single Bernoulli parameter rather than a conditional effect, and the
#: hierarchy in `credibility.py` shrinks a thin source to its tier rather than trusting it.
MIN_SOURCE_N = 12

__all__ = [
    "LEDGER_PATH",
    "MIN_CATEGORY_N",
    "MIN_SOURCE_N",
    "CategoryStats",
    "EventLedger",
]


@dataclass(frozen=True)
class CategoryStats:
    """What the ledger knows about one category's market behaviour, and whether that is enough.

    `total_move_sigma` is the median ABSOLUTE full-window response, in sigma, over instances
    with a measured reaction. It is the denominator of the unpriced fraction, which is why its
    status is carried beside it rather than a zero being returned when it is unknown.
    """

    category: str
    n_recorded: int
    n_measured: int
    total_move_sigma: float | None
    decay_half_life_s: float | None
    status: str

    @property
    def has_sample(self) -> bool:
        return self.status == Status.MEASURED


class EventLedger:
    """Append-only JSONL of scored events. Construct with a path to point it at a test tree."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else LEDGER_PATH
        self._seen: set[str] | None = None

    # ------------------------------------------------------------------ writing ----
    def append(self, rec: EventRecord) -> bool:
        """Write one row. Returns False when the id is already present (a re-poll, not an event).

        The directory is created lazily so importing this module on a box with no desk data tree
        does not manufacture directories, and the write is a single line so a crash mid-append
        can lose at most the row being written -- never corrupt the rows already there.
        """
        if rec.event_id in self.seen():
            return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(rec.to_json() + "\n")
        self.seen().add(rec.event_id)
        return True

    def extend(self, recs: Iterable[EventRecord]) -> int:
        return sum(1 for r in recs if self.append(r))

    # ------------------------------------------------------------------ reading ----
    def seen(self) -> set[str]:
        if self._seen is None:
            self._seen = {r.event_id for r in self.read()}
        return self._seen

    def read(self) -> Iterator[EventRecord]:
        """Every row, oldest first. A malformed line is SKIPPED and counted, never fatal: one
        bad row must not cost the desk the other ten thousand."""
        if not self.path.exists():
            return
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except ValueError:
                    continue
                if isinstance(raw, dict):
                    yield EventRecord.from_dict(raw)

    def records(self) -> list[EventRecord]:
        return list(self.read())

    def before(self, iso_ts: str) -> list[EventRecord]:
        """Rows the desk had FINISHED SCORING at `iso_ts`. The point-in-time view: a replay at
        time t may fit on this and nothing else, because `processed_at` is when the row existed.
        """
        cut = parse_ts(iso_ts)
        if cut is None:
            return []
        out = []
        for r in self.read():
            p = parse_ts(r.processed_at) or parse_ts(r.received_at)
            if p is not None and p <= cut:
                out.append(r)
        return out

    # ------------------------------------------------------------- statistics ----
    def category_stats(self, category: str,
                       records: list[EventRecord] | None = None,
                       decay_samples: Mapping[str, Sequence[float]] | None = None
                       ) -> CategoryStats:
        """This category's measured market behaviour, or an honest UNMEASURED.

        `decay_samples` comes from `attribution.feedback` and carries the half-lives measured
        AFTER each event's horizon closed. It is passed in rather than read off the rows on
        purpose: the ledger is append-only and a row records what was known when it was scored,
        so a quantity that can only be known later belongs to the attribution record. Reading the
        half-life off the rows would also be circular -- nothing would ever seed it, and the
        interrupt gate that depends on it would be permanently UNMEASURED.
        """
        rows = self.records() if records is None else records
        in_cat = [r for r in rows if r.category == category]
        moves: list[float] = []
        # Attribution's measurements are the authority. The row field is a FALLBACK only, used
        # when attribution has produced nothing for this category yet -- it holds whatever the
        # scorer knew at the time, which for a live row is the previous pass's estimate.
        from_attribution = [
            float(h) for h in ((decay_samples or {}).get(category) or ())
            if isinstance(h, int | float) and h > 0]
        from_rows: list[float] = []
        for r in in_cat:
            priced = r.priced or {}
            if priced.get("status") != Status.MEASURED:
                continue
            total = (r.extra.get("realised_total_sigma")
                     if r.extra else None) or priced.get("total_move_sigma")
            if isinstance(total, int | float) and total == total:
                moves.append(abs(float(total)))
            hl = r.decay_half_life_s
            if isinstance(hl, int | float) and hl and hl > 0:
                from_rows.append(float(hl))
        halves = from_attribution or from_rows
        n_measured = len(moves)
        if n_measured < MIN_CATEGORY_N:
            return CategoryStats(category, len(in_cat), n_measured, None, None,
                                 Status.UNMEASURED)
        return CategoryStats(
            category, len(in_cat), n_measured, float(median(moves)),
            float(median(halves)) if len(halves) >= MIN_CATEGORY_N else None,
            Status.MEASURED)

    def all_category_stats(self, decay_samples: Mapping[str, Sequence[float]] | None = None
                           ) -> dict[str, CategoryStats]:
        rows = self.records()
        cats = sorted({r.category for r in rows})
        return {c: self.category_stats(c, rows, decay_samples) for c in cats}

    def source_counts(self) -> dict[str, dict[str, int]]:
        """Per source: rows seen, and the verified/falsified tallies attribution wrote back.

        Verification is NOT inferred here. A row counts as verified only when
        `attribution.py` measured it and stamped the record, which is why a source with a
        thousand headlines and no attributions has n=0 and stays on its tier prior.
        """
        out: dict[str, dict[str, int]] = {}
        for r in self.read():
            d = out.setdefault(r.source_id, {"n": 0, "verified": 0, "falsified": 0})
            d["n"] += 1
            cred = r.credibility or {}
            d["verified"] += int(cred.get("n_verified", 0) or 0)
            d["falsified"] += int(cred.get("n_falsified", 0) or 0)
        return out

    def summary(self) -> dict[str, Any]:
        rows = self.records()
        cats = sorted({r.category for r in rows})
        measured = sum(1 for r in rows if (r.priced or {}).get("status") == Status.MEASURED)
        authorised = sum(1 for r in rows if r.capital_authority)
        return {
            "at": now_iso(),
            "path": str(self.path),
            "rows": len(rows),
            "categories": len(cats),
            "rows_with_measured_reaction": measured,
            "rows_with_capital_authority": authorised,
            "sources": sorted({r.source_id for r in rows}),
            "min_category_n": MIN_CATEGORY_N,
            "categories_with_sample": sorted(
                c for c, s in self.all_category_stats().items() if s.has_sample),
        }


def write_json_atomic(path: Path, obj: Any) -> None:
    """Replace a small JSON artifact without ever leaving a half-written file on disk.

    Used for the interrupt request and the reports -- files a SEPARATE PROCESS polls. A reader
    that catches a partial write there either crashes the supervisor or, worse, acts on half a
    request, so the write goes to a temp file in the same directory and is renamed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=1, sort_keys=True, default=str)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
