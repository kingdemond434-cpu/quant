"""FORWARD PANELS OVER PUBLIC TRADER LEADERBOARDS -- one implementation, every venue.

WHY A PANEL AND NOT A SCREEN. A leaderboard is, by construction, the maximum of a very large
number of draws, and it never shows the denominator. Any statistic computed on the traders it
currently displays is computed on a sample selected for the outcome being measured, so it will show
skill whether or not skill exists. `screen_copytrading` demonstrated the size of the artifact on
real OKX data: sorted on pnl/aum/copiers, a 34-trader sample returns Spearman +0.33 between first-
and second-half returns, manufactured end-to-end by the selection.

The only unbiased design is to FIX A COHORT TODAY, follow it, and count the ones that disappear.
That is what this module holds, venue-agnostically, so Binance/Bybit/Hyperliquid do not each
re-derive it and disagree about what "persistence" means.

**EXITS ARE THE MEASUREMENT, NOT MISSING DATA.** A trader who leaves the leaderboard between two
snapshots left for a reason, and the overwhelmingly common reason is a drawdown. Dropping them --
which is what happens by default, since they are simply absent from the second file -- is the
survivorship bug in its purest form. So this reports the exit rate as a first-class number and
publishes the rank statistic TWICE: once over survivors only (labelled as biased upward, because it
is), and once with exits ranked last. Neither is published without the other, because the gap
between them IS the survivorship effect and a reader who sees only one cannot see it.

**A SNAPSHOT IS APPEND-ONLY AND NEVER REWRITTEN.** The panel's value is entirely in the fact that
the earlier rows were written before anyone knew what happened next. A corrected, re-fetched or
back-filled row destroys exactly that property while looking like an improvement.

Stdlib + a rank statistic. No venue code here: collectors normalise, this measures.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

__all__ = [
    "MIN_COHORT",
    "MIN_GAP_DAYS",
    "TraderRow",
    "append_snapshot",
    "forward_persistence",
    "read_snapshots",
    "spearman",
]

#: Two snapshots must be at least this far apart before ANY persistence figure is published.
#: Venues refresh their published return windows on a multi-day cadence, so a shorter gap re-reads
#: one datapoint twice and calls it two observations -- which inflates n without adding evidence,
#: the single most common way a forward panel lies about its own power.
MIN_GAP_DAYS = 5.0

#: Below 30 traders the Spearman standard error (~1/sqrt(n-1)) exceeds 0.19, so anything under
#: ~0.4 is indistinguishable from noise. Publishing a number there invites the exact over-reading
#: this module exists to prevent, so it returns UNDERPOWERED instead of a figure.
MIN_COHORT = 30

#: The normalised row every venue collector must produce. `trader_id` must be stable across
#: snapshots -- a venue that rotates its identifiers cannot support a forward panel at all, and
#: that fact belongs in the collector's report rather than as silently zero persistence.
TraderRow = dict[str, Any]


def read_snapshots(path: Path) -> list[dict[str, Any]]:
    """Every archived snapshot, oldest first. A malformed line is SKIPPED, never fatal: one bad
    write must not cost the desk a panel that took weeks of calendar time to accumulate."""
    try:
        raw = path.read_text("utf-8", errors="ignore")
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for ln in raw.splitlines():
        if not ln.strip():
            continue
        try:
            out.append(json.loads(ln))
        except ValueError:
            continue
    return out


def append_snapshot(path: Path, venue: str, traders: list[TraderRow], *,
                    at: datetime | None = None, source: str = "") -> bool:
    """Append one dated cohort. Returns False and writes NOTHING on an empty cohort.

    An empty snapshot is not a cohort of zero traders, it is a FAILED FETCH, and writing it would
    make every trader look like they exited -- turning a network error into a 100% exit rate, which
    is a spectacular false finding rather than a missing one.
    """
    if not traders:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"at": (at or datetime.now().astimezone()).isoformat(),
           "venue": venue, "source": source, "n": len(traders), "traders": traders}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    return True


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Rank correlation. None when undefined -- never 0.0, which reads as 'measured, no relation'
    and is the wrong claim when the answer is 'not measurable'."""
    n = len(xs)
    if n < 3 or n != len(ys):
        return None

    def rank(v: list[float]) -> list[float]:
        """MIDRANKS FOR TIES. Assigning distinct ranks to equal values invents an ordering that
        the data does not contain, and it does so in the direction of whatever the sort was
        stable on. A constant series then reports rank variance it does not have, and the
        correlation comes back 1.0 where the honest answer is 'undefined'. That matters here
        specifically: exits are deliberately assigned one shared value, so they are ALWAYS a tie
        block, and the naive version would silently rank them against each other."""
        order = sorted(range(len(v)), key=lambda i: v[i])
        out = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            mid = (i + j) / 2.0
            for k in range(i, j + 1):
                out[order[k]] = mid
            i = j + 1
        return out

    rx, ry = rank(xs), rank(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return None if dx == 0 or dy == 0 else num / (dx * dy)


def _metric(row: TraderRow) -> float:
    """The venue's published return figure, whatever it called it. Collectors normalise to `roi`."""
    for k in ("roi", "pnl_ratio", "pnlRatio", "return"):
        v = row.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return 0.0


def forward_persistence(path: Path, *, min_gap_days: float = MIN_GAP_DAYS,
                        min_cohort: int = MIN_COHORT) -> dict[str, Any]:
    """Same cohort, two separated snapshots, exits counted as failures.

    Publishes the rank statistic twice. `spearman_survivors_only` is what a naive analysis computes
    and is BIASED UPWARD, because everyone who blew up between the snapshots has been silently
    removed from it. `spearman_exits_ranked_last` puts each exited trader below every survivor on
    the forward axis, which is the weakest defensible assumption about someone who left a
    leaderboard. The DIFFERENCE between the two is the survivorship effect, and it is the number
    worth reading.
    """
    snaps = read_snapshots(path)
    if not snaps:
        return {"state": "NO-DATA", "n_snapshots": 0,
                "why": "no snapshot archived yet -- the forward clock starts on the first "
                       "successful collection, and UNMEASURED is not 'no persistence'"}
    if len(snaps) < 2:
        return {"state": "NO-DATA", "n_snapshots": 1,
                "why": "one snapshot cannot measure persistence; the clock is running"}

    first, last = snaps[0], snaps[-1]
    gap = (datetime.fromisoformat(last["at"]) - datetime.fromisoformat(first["at"])).days
    if gap < min_gap_days:
        return {"state": "NO-DATA", "n_snapshots": len(snaps), "gap_days": gap,
                "why": f"snapshots {gap}d apart, under the {min_gap_days}d minimum -- a shorter "
                       "gap re-reads one datapoint twice and calls it two observations"}

    then = {str(t.get("trader_id")): t for t in first.get("traders", [])}
    now = {str(t.get("trader_id")): t for t in last.get("traders", [])}
    survived = [c for c in then if c in now]
    exited = [c for c in then if c not in now]
    if len(then) < min_cohort:
        return {"state": "UNDERPOWERED", "n_snapshots": len(snaps), "gap_days": gap,
                "cohort": len(then), "exited": len(exited),
                "why": f"cohort {len(then)} < {min_cohort}; a rank statistic here is noise, and "
                       "publishing one invites the over-reading this panel exists to prevent"}

    xs = [_metric(then[c]) for c in survived]
    ys = [_metric(now[c]) - _metric(then[c]) for c in survived]
    surv_rho = spearman(xs, ys)

    # EXITS RANKED LAST. One step below the worst survivor -- not an invented return, just an
    # ordering, which is all a rank statistic consumes. Ties among exits are fine: they share the
    # same claim, that they did worse than everyone still standing.
    floor = (min(ys) - 1.0) if ys else -1.0
    xs_all = xs + [_metric(then[c]) for c in exited]
    ys_all = ys + [floor] * len(exited)
    all_rho = spearman(xs_all, ys_all)

    return {
        "state": "MEASURED", "n_snapshots": len(snaps), "gap_days": gap,
        "cohort": len(then), "survived": len(survived),
        "exited_counted_as_failures": len(exited),
        "exit_rate": round(len(exited) / len(then), 3),
        "spearman_survivors_only": surv_rho,
        "spearman_exits_ranked_last": all_rho,
        "survivorship_effect": (None if surv_rho is None or all_rho is None
                                else round(surv_rho - all_rho, 4)),
        "note": ("spearman_survivors_only is BIASED UPWARD -- everyone who blew up between the "
                 "snapshots is absent from it. spearman_exits_ranked_last places each exited "
                 "trader below every survivor on the forward axis, the weakest defensible "
                 "assumption about someone who left a leaderboard. The gap between the two IS the "
                 "survivorship effect; neither figure is publishable without the other."),
    }
