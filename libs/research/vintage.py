"""POINT-IN-TIME STORE for revised data -- what was KNOWABLE on date d (R0316, OP-047).

THE LEAK THIS CLOSES IS IN THE CONDITIONING VARIABLE, WHICH IS WHY NOTHING CAUGHT IT. Tax panels,
national accounts, central-bank series and exchange restatements are all REVISED after publication.
A backtest that reads today's file applies knowledge that did not exist at the time -- but the
RETURN series is spotless, so every leak check the desk owns passes cleanly (R0289's class). It
fails toward a FALSE POSITIVE, so it does not merely waste a study: it costs a Holm slot and
manufactures an edge that cannot survive live.

MEASURED, NOT ASSUMED. Across three vintages of the Receita Federal Brazil crypto panel, 39/42
common months were revised within three months and 42/42 by the latest vintage; the worst,
March 2023, moved R$15,828mn -> R$22,308mn (+40.9%) and was still moving on a month 2.4 years old.
Revisions run systematically UPWARD (late and amended filings), so the bias has a sign: today's
file makes the past look bigger than anyone could have known it was.

THE STORE IS A REVISION LOG, NOT A PILE OF SNAPSHOTS. A row is appended only when a value is NEW or
has CHANGED, so re-recording an unchanged 800-observation series costs nothing. That is what makes
keeping every vintage forever affordable, and affordability is the whole design constraint: a store
expensive enough to prune is one that gets pruned, and a pruned vintage is unrecoverable.

TWO CLOCKS, KEPT APART (L1.46). ``period`` is the reference period the value DESCRIBES -- the
source's clock. ``vintage`` is when THIS DESK first saw that value -- our clock, never the source's
publication stamp, which we usually cannot observe. Reading them as one is the mistake the whole
module exists to prevent, so they never share a field.

    record(root, "M2SL", {"2026-06-01": 21987.3}, vintage="2026-08-12")
    as_of(root, "M2SL", "2026-08-12")     # -> {"2026-06-01": 21987.3}
    as_of(root, "M2SL", "2026-08-01")     # -> {}  -- not knowable yet, and that is the point
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

#: One append-only log per source. Splitting by series keeps a rewrite of one source from
#: touching another's history, and makes a corrupt file cost exactly one series.
STORE_DIR: Final = "data/vintages"

EXTRACTOR_INVARIANT = (
    "every row carries series/period/value/vintage; vintages are non-decreasing within a file; "
    "a row is appended only when the value is new or CHANGED, so reading a period back at its own "
    "vintage returns the value recorded then"
)


def _path(root: Path, series: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in series)
    return root / STORE_DIR / f"{safe}.jsonl"


def read_log(root: Path, series: str) -> list[dict[str, Any]]:
    """Every recorded revision for a series, oldest first.

    A malformed line is SKIPPED but counted by the caller's own invariant rather than silently
    dropped here -- and it can only ever be a trailing partial write, because the file is
    append-only and each row is written whole.
    """
    path = _path(root, series)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and {"period", "value", "vintage"} <= set(row):
            rows.append(row)
    return rows


def latest_known(root: Path, series: str) -> dict[str, float]:
    """The most recent value recorded for each period -- what the desk believes TODAY."""
    out: dict[str, float] = {}
    for row in read_log(root, series):
        out[str(row["period"])] = float(row["value"])
    return out


def record(
    root: Path,
    series: str,
    observations: Mapping[str, float],
    *,
    vintage: str,
) -> int:
    """Append only what CHANGED, and return how many revisions were recorded.

    Returning the count is not decoration. Zero on a first run means the fetch came back empty and
    the caller is about to report a healthy collection over nothing; zero on a later run is the
    normal, expected state. The two are told apart by the log's own length, never by this number.
    """
    known = latest_known(root, series)
    fresh = [
        {"series": series, "period": str(period), "value": float(value), "vintage": vintage}
        for period, value in sorted(observations.items())
        # `!=` on floats is correct here: these are values as PUBLISHED, and a revision that moves
        # a number by one ULP is still a revision. Rounding to a tolerance would silently drop the
        # smallest ones, which is the half of the distribution nobody would notice missing.
        if period not in known or known[str(period)] != float(value)
    ]
    if not fresh:
        return 0
    path = _path(root, series)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in fresh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    return len(fresh)


def as_of(root: Path, series: str, when: str) -> dict[str, float]:
    """The panel AS IT WAS KNOWN on ``when`` -- the whole point of the module.

    Two rules, and the second is the one a naive implementation gets wrong:
      * a period takes the value from the latest vintage recorded on or before ``when``;
      * a period whose FIRST vintage is later than ``when`` is ABSENT, not zero and not
        back-filled. It was not knowable, and an absent input must stay distinguishable from a
        measured one (L1.28a).
    """
    out: dict[str, float] = {}
    for row in read_log(root, series):
        if str(row["vintage"])[:10] <= when[:10]:
            out[str(row["period"])] = float(row["value"])
    return out


def revisions(root: Path, series: str) -> list[dict[str, Any]]:
    """Every period that moved after it was first published, with the size of the move.

    This is the evidence that decides whether a source NEEDS point-in-time treatment at all. A
    series that has never been revised can be read at current vintage safely, and saying so with a
    measurement beats assuming it in either direction.
    """
    first: dict[str, float] = {}
    last: dict[str, float] = {}
    count: dict[str, int] = {}
    for row in read_log(root, series):
        period = str(row["period"])
        value = float(row["value"])
        if period not in first:
            first[period] = value
        else:
            count[period] = count.get(period, 0) + 1
        last[period] = value
    return [
        {
            "period": period,
            "first": first[period],
            "latest": last[period],
            "n_revisions": count.get(period, 0),
            "pct_change": (
                100.0 * (last[period] - first[period]) / first[period] if first[period] else None
            ),
        }
        for period in sorted(count)
    ]


def summarise(root: Path, series: str) -> dict[str, Any]:
    """Coverage of one series' vintage history, with the refusal states kept distinct."""
    rows = read_log(root, series)
    if not rows:
        return {
            "series": series,
            "status": "UNMEASURED",
            "n_rows": 0,
            "n_periods": 0,
            "n_vintages": 0,
            "detail": "no vintage history recorded -- current-vintage reads are unaudited",
        }
    vintages = sorted({str(row["vintage"])[:10] for row in rows})
    revised = revisions(root, series)
    if len(vintages) < 2:
        # ONE vintage cannot show a revision, so "no revisions found" here would be a statement
        # about the sample, not the source. The clock has started; it has not finished (L1.48).
        status = "ACCRUING"
        detail = (
            f"1 vintage recorded ({vintages[0]}); a revision needs two, so this series is not yet "
            f"evidence either way"
        )
    else:
        status = "OK"
        detail = (
            f"{len(vintages)} vintages {vintages[0]}..{vintages[-1]}, {len(revised)} of "
            f"{len({str(r['period']) for r in rows})} periods revised since first publication"
        )
    return {
        "series": series,
        "status": status,
        "n_rows": len(rows),
        "n_periods": len({str(row["period"]) for row in rows}),
        "n_vintages": len(vintages),
        "first_vintage": vintages[0],
        "last_vintage": vintages[-1],
        "n_revised_periods": len(revised),
        "detail": detail,
    }
