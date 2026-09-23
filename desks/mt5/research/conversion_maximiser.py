#!/usr/bin/env python3
"""THE CONVERSION MAXIMISER -- every mined row ends as a testable cell or a reasoned refusal.

THE PRINCIPAL'S STANDING ORDER (2026-09-23): "permanently maximise 100 percent conversion to
testable cells of all minings ... conversion in general for everything must be fully maximised
24/7 of all factories, research processes, recommendations, everything ... we always squeeze the
life out of everything we get and have, always, now and in future."

WHAT THIS ORGAN IS FOR, MEASURED, NOT ASSERTED. The desk's failure has never been finding
things. Measured on the trading box 2026-09-23 against ROOT `data/alpha_registry.sqlite`:
66,898 discoveries of which 31,226 BLOCKED and 2,843 never processed at all; 305,265 research
candidates of which 234,996 sat in status `donated` having never become a gauntlet cell; 31
survivors. Roughly 47% of everything mined was parked and ~77% of every candidate ever written
had never been offered to a judge. That is not a shortage of ideas. It is a conversion defect,
and an unmeasured conversion rate COUNTS AS ZERO (sealed core, L1.28a).

`discovery_compiler` converts what arrives. `experiment_spine` converts what the compilers'
ARTIFACTS carry. NOTHING attacked the residue already inside the registry -- the rows that
arrived, failed one contract field, and stopped. This organ is that attack, and it ACTS rather
than reports.

THE FIVE STEPS OF A PASS.

  1. MEASURE   the debt, in cheap SQL over the whole population, in five named components
               (`measure_debt`). Not a sample: the ratchet in `scripts/check_conversion_debt.py`
               is only worth something if the number it ratchets is the whole number.
  2. CLASSIFY  every row the pass touches through `libs.research.experiment_spec.compile_row`,
               so the blocker is named in the SAME vocabulary the compilers use: PROSE_ONLY,
               NO_INSTRUMENT, NO_FAMILY, NO_FALSIFIER, NO_DATA, OFF_UNIVERSE, UNREADABLE. The
               histogram is published with the organ that OWNS each class.
  3. PRIORITISE by ORTHOGONAL BREADTH, never by raw count (LAWS 5b: "ten candidates in ten new
               economic mechanisms outrank a hundred thousand parameter mutations of one").
               A debt row whose axis cell is empty or thin in the testable population is
               repaired first; the 235k backlog drains toward independent cells rather than
               toward more copies of what the docket already holds.
  4. ACT       per blocker class, with the desk's own machinery and nothing invented:
                 NO_FALSIFIER  the standing re-judgement rule (`experiment_spine.enrich`) --
                               the exact rule re-judged on bars after the snapshot fails the
                               ten gates -- stamped `falsifier_basis: derived`.
                 NO_DATA       NEVER A BLOCKER (principal's addendum 2026-09-23, "they should
                               never ever be blocked on bars"). `ensure_bars` supplies the
                               series: a chart COARSER than one the desk holds is built by exact
                               aggregation and written; a chart FINER than the finest held
                               cannot be manufactured, so the cell is bound to the finest series
                               the desk DOES hold and the fetch is requested. Only a symbol with
                               no series at all keeps the blocker, and even then the row stays
                               QUEUED with the blocker named.
                 NO_INSTRUMENT resolved through the MT5 universe registry, and only into the
                               HYPOTHESIS lane (`universe_policy.may_hypothesise`).
                 NO_FAMILY     bound from the mechanism through `discovery_compiler.interpret`
                               and `axis_registry.FAMILY_TABLE`; a mechanism no registered
                               family implements keeps that exact blocker, never a family that
                               would test a different claim.
                 PROSE_ONLY    routed to the understanding/naming seat as a naming request.
                 OFF_UNIVERSE  RETIRED with the mandate that forbids it. A crypto-exchange-native
                 EVENT_LANE    row and a single-name equity are never converted -- the two-lane
                               law (2026-09-06) says the equity's edge is sought in the event
                               lane, and the universe mandate (2026-08-18) says the exchange
                               ground is never hunted again.
  5. RE-ENQUEUE everything repaired through `registry.enqueue_candidate` (via
               `experiment_spec.enqueue`, which also writes the `experiment -> cell` and
               `discovery -> experiment` provenance edges), and CHARGE the pass its effective
               trials -- `trial_ledger.effective_count_of_records`, the participation ratio, not
               the raw count -- so re-enqueued work pays the multiple-testing bill it owes.

NOTHING IS PARKED AND FORGOTTEN (principal's addendum 2026-09-23). A row this pass could not
repair STAYS QUEUED carrying its named blocker and its owner (`_keep_queued`), so the next pass
sees it again, `untestable_queued` keeps counting it, and the ratchet keeps the pressure on. The
ONLY admissible permanent refusals are ground the desk is forbidden to hunt (OFF_UNIVERSE, the
2026-08-18 universe mandate) and an instrument the venue does not quote for this lane (EVENT_LANE,
the 2026-09-06 two-lane law). Every other blocker is WORK TO DO. A `parked_past_grace` component
still counts any row another organ parks, so this rule is measured rather than assumed.

NO LEGAL OR POLICY GATE LIVES HERE (principal 2026-09-23, second order). "Public and licensed
ground only" was REMOVED everywhere: a licence, a robots directive, an access label or a source
class is ROUTING AND PROVENANCE METADATA, never a reason a row fails to convert. A row carrying
one converts and is tested WITH the label attached. The only permanent refusals left are an
instrument the broker does not quote for this lane and ground the universe mandate forbids --
`REFUSAL_POLICY` is published in the artifact every pass so that absence is visible rather than
assumed.

NO QUEUES (principal 2026-09-23). A pass that runs out of budget does not park its remainder: the
leftover ids are handed to the next pass as its FIRST work (`_write_carry` / `_read_carry`), and
the age of the OLDEST row still waiting is published every pass (`oldest_unconverted`). A count
alone cannot tell a drain from a stall; that age can, because it rises one day per day when a
backlog is being re-counted instead of drained.

PUBLISHED EVERY PASS, PER BLOCKER CLASS: the count, the repair rate and the MEDIAN AGE -- "so a
class that stops falling is visible the same day". Plus the per-symbol per-timeframe BAR
COVERAGE that drives the backfill, and the effective breadth before and after.

WHAT IT NEVER DOES. It adds no cap, no veto, no shrink and no brake: it only moves rows from
"untestable" to "testable" or to "refused for a named reason". It writes no certificate, no
sleeve and no capital number. It converts NOTHING off-universe.

    python desks/mt5/research/conversion_maximiser.py --once --budget-s 900
    python desks/mt5/research/conversion_maximiser.py --dry-run --budget-s 60
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(BASE), str(BASE / "research"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from libs.research import experiment_spec as XS  # noqa: E402

# --------------------------------------------------------------------------------- constants
OUT = BASE / "reports" / "CONVERSION_MAXIMISER.json"
SEAT = "conversion_maximiser"
SEAT_DIR = BASE / "data" / "intelligence" / SEAT
UNIVERSE_DIR = BASE / "data" / "universe"
UNIVERSE_JSON = UNIVERSE_DIR / "universe.json"

#: Wall clock for one `--once` pass. The hourly leg gives it 900 s.
BUDGET_S = 900.0

#: This organ parks nothing. The component exists to count rows ANOTHER organ parked and never
#: collected: past this many days a `routed` row counts as debt again and the ratchet sees it.
GRACE_DAYS = 7.0

#: Bytes one debt row costs while held (the registry dict plus the compiled spec). The pass cap
#: is DERIVED from measured free memory through these, never from a machine size: the trading box
#: has 98 GB and the build box 8 GB, and a floor sized off either is sized for the wrong machine
#: (CLAUDE.md, the 96 GB lesson).
BYTES_PER_ROW = 4096
FREE_MEMORY_SHARE = 0.10
MAX_ROWS_FLOOR = 2_000

#: How many rows are examined to fill one repair slot. Ranking by breadth needs a pool wider than
#: the slots, or "prioritise by breadth" is just "take the first N in id order".
POOL_FACTOR = 4
POOL_CEILING = 20_000

#: The candidate statuses that ARE a gauntlet cell (they sit on the CampaignQueue or past it).
TESTABLE_STATUSES = ("queued", "claimed", "judged", "survived", "rejected", "live", "forward")

#: NO QUEUES (principal 2026-09-23): a pass that runs out of budget does not PARK its remainder,
#: it hands it to the next pass as the FIRST work, and publishes its age. This file is that hand,
#: and it holds ids only -- never rows, so it can never become a second store beside the registry.
CARRY = BASE / "data" / "conversion_maximiser_carry.json"
MAX_CARRY = 20_000

#: THE ONLY PERMANENT REFUSALS (principal 2026-09-23, two orders). A symbol the broker does not
#: quote for this lane, ground the universe mandate forbids, and the five forbidden acts. NOTHING
#: ELSE. Licence, robots and access labels are ROUTING AND PROVENANCE METADATA and were removed as
#: a reason a row may fail to convert -- a row that carries one converts and is tested WITH the
#: label attached, never refused for it. This organ therefore holds no legal or policy gate at all,
#: and this constant is published in the artifact so the absence is visible rather than assumed.
REFUSAL_POLICY = {
    "admissible_permanent_refusals": [
        "OFF_UNIVERSE -- ground the MT5/Fusion universe mandate (2026-08-18) forbids hunting",
        "EVENT_LANE -- the instrument is not quoted for the hypothesis lane; the two-lane law "
        "(2026-09-06) tests it in the event lane instead, so this is a LANE ROUTING and not a "
        "refusal of the claim",
    ],
    "never_a_refusal": [
        "a licence, a robots directive, an access label or a source class -- routing and "
        "provenance metadata, carried onto the cell and never a blocker (principal 2026-09-23)",
        "a missing bar at any timeframe -- supplied by `ensure_bars` or requested",
        "a missing falsifier, family or instrument -- repaired, or kept queued with its owner",
    ],
}

#: The siding this organ NEVER writes to and still measures, so a regression that starts parking
#: rows again shows up in `parked_past_grace` instead of disappearing.
ROUTED = "routed"
RETIRED = "retired"

#: STUDY, not judged. A family banned from live capital is still mined and still stored -- what
#: stops is spending the scarce judge on it, because it cannot reach the book even if it passes.
STUDY = "study"
STUDY_REASON = ("family {family!r} is banned from live capital (mt5desk/live_policy.py "
                "DEFAULT_BANNED_FAMILIES) and refused at both live doors, so it cannot reach the "
                "book even if it passes; kept for study, never judged, never deleted, and mining "
                "it stays unrestricted")


def live_banned_families() -> frozenset[str]:
    """Families the desk has already forbidden from live capital, read from the live policy.

    ONE TRUTH, NOT A COPY. `merge_hypotheses.live_banned_families` reads the same policy for the
    docket; this door reads it for the queue, so the two can never disagree about which family
    the judge is not spending on.
    """
    try:
        from research.merge_hypotheses import live_banned_families as _f
        return _f()
    except Exception:                                                    # pragma: no cover
        try:
            from mt5desk.live_policy import DEFAULT_BANNED_FAMILIES
            return frozenset(str(f) for f in DEFAULT_BANNED_FAMILIES)
        except Exception:
            return frozenset({"discovered"})

#: Which organ owns each blocker class. Published every pass so the bottleneck has an address.
DEFECT_OWNER: dict[str, str] = {
    "NO_FALSIFIER": "desks/mt5/research/experiment_spine.py (enrich: the standing re-judgement "
                    "rule) -- repaired here",
    "NO_DATA": "desks/mt5/research/conversion_maximiser.py ensure_bars (resample) then "
               "research/fetch_universe.py via the hourly `refresh_bars` leg (fetch) -- a "
               "missing bar is work to do, never a verdict",
    "NO_INSTRUMENT": "desks/mt5/data/universe/universe.json + research/universe_policy.py "
                     "(the MT5 registry and the two-lane router) -- repaired here",
    "NO_FAMILY": "desks/mt5/research/axis_registry.py FAMILY_TABLE (which family implements "
                 "which mechanism)",
    "PROSE_ONLY": "desks/mt5/research/understanding_seat.py (the naming seat)",
    "OFF_UNIVERSE": "docs/LAWS.md 1 -- the MT5/Fusion universe mandate; never converted",
    "EVENT_LANE": "desks/mt5/research/universe_policy.py -- single names are traded on news, "
                  "never hunted for statistical hypotheses; never converted",
    "UNREADABLE": "the generator that wrote the row (named per row in `refusals`)",
}

#: Classes that are REFUSALS, not repairs. A row in one of these is retired with its reason.
REFUSAL_CLASSES = ("OFF_UNIVERSE", "EVENT_LANE")

RULE = ("every mined row ends as a testable cell or a recorded, reasoned refusal; an unconverted "
        "row is a defect with an owner; conversion debt ratchets DOWN and never up")

UNMEASURED = "UNMEASURED"


# --------------------------------------------------------------------------------- utilities
def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _atomic_write(path: Path, doc: Any) -> Path:
    """Write JSON atomically. A read-only destination is made writable first: `os.replace` onto
    one is legal on POSIX and raises WinError 5 on Windows, and this desk trades on Windows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True, default=str)
    try:
        os.replace(tmp, path)
    except PermissionError:
        with contextlib.suppress(OSError):
            os.chmod(path, 0o644)
        os.replace(tmp, path)
    return path


def _free_bytes() -> int | None:
    """Free physical memory on THIS box, or None when it cannot be read -- never a zero."""
    try:
        from libs.ops.host_resources import mem_available_mb
        mb = mem_available_mb()
        return None if mb is None else int(mb) * 1024 * 1024
    except Exception:
        return None


def max_rows_per_pass() -> int:
    """The pass cap, DERIVED from measured free memory, floored at the historic 2,000 so an
    unreadable counter changes nothing."""
    free = _free_bytes()
    if free is None:
        return MAX_ROWS_FLOOR
    return max(MAX_ROWS_FLOOR, int(free * FREE_MEMORY_SHARE / BYTES_PER_ROW))


class Budget:
    """Wall-clock budget. Every stage checks it and the artifact says which stage ran out."""

    def __init__(self, seconds: float) -> None:
        self.seconds = float(seconds)
        self.t0 = time.monotonic()
        self.stopped_at: str | None = None

    def left(self) -> float:
        return self.seconds - (time.monotonic() - self.t0)

    def spent(self) -> float:
        return round(time.monotonic() - self.t0, 2)

    def ok(self, stage: str, reserve: float = 0.0) -> bool:
        if self.left() > reserve:
            return True
        if self.stopped_at is None:
            self.stopped_at = stage
        return False


# ------------------------------------------------------------------------------- the debt
#: The five components of conversion debt, each one cheap SQL over the WHOLE population. A row
#: that is a testable cell, or that carries a recorded reasoned refusal, is NOT debt.
_DEBT_SQL: tuple[tuple[str, str, str], ...] = (
    ("silent_discoveries",
     "SELECT COUNT(*) FROM discoveries WHERE state='UNPROCESSED' AND created_at<:cut",
     "mined and never given any disposition at all"),
    ("unreasoned_blocks",
     "SELECT COUNT(*) FROM discoveries WHERE state='BLOCKED' "
     "AND COALESCE(blocked_reason,'')='' AND created_at<:cut",
     "parked as BLOCKED with no reason -- a refusal nobody can audit"),
    ("donated_never_cell",
     "SELECT COUNT(*) FROM research_candidates WHERE status='donated' AND created_at<:cut",
     "donated to the docket and never offered to a judge"),
    ("untestable_queued",
     "SELECT COUNT(*) FROM research_candidates WHERE status IN ('queued','claimed') "
     "AND COALESCE(falsifier,'')='' AND created_at<:cut",
     "on the queue but missing the falsifier the compile contract requires (LAWS 5k)"),
)

#: IN FLIGHT IS NOT DEBT, AND IT IS NOT HIDDEN EITHER. A row minted minutes ago has not yet had
#: its turn: the compiler mints cells on one hourly leg and this organ drains them on the next,
#: so a debt measured at an arbitrary instant would count the pipeline's own work-in-progress and
#: the fence would go red for a producer that ran one minute before its consumer. That is how a
#: fence gets disabled, which protects nothing. This is the SAME distinction `check_conversion.py`
#: already draws between `backlog` and `owed`: two cycles of the hourly leg is one turn missed,
#: and at that point the row IS owed. `in_flight` is published every pass, so nothing hides here
#: -- it is a delay, never a disposition, and every row in it becomes debt on the clock.
IN_FLIGHT_GRACE_H = 2.0


def measure_debt(conn: sqlite3.Connection, *, grace_days: float = GRACE_DAYS,
                 in_flight_grace_h: float = IN_FLIGHT_GRACE_H) -> dict[str, Any]:
    """CONVERSION DEBT: rows that are neither a testable cell nor a reasoned refusal.

    Whole-population counts, not a sample: the ratchet is only worth something if the number it
    ratchets is the number. A component whose table cannot be read is UNMEASURED and NAMED -- it
    is never silently counted as zero (L1.28a), and it makes the total unmeasured too.
    """
    parts: dict[str, int] = {}
    why: dict[str, str] = {}
    unmeasured: list[dict[str, str]] = []
    now = datetime.now(tz=UTC)
    cut = {"cut": (now - timedelta(hours=float(in_flight_grace_h))).isoformat()}
    never = {"cut": now.isoformat()}
    in_flight: dict[str, int] = {}
    for name, sql, reason in _DEBT_SQL:
        try:
            parts[name] = int(conn.execute(sql, cut).fetchone()[0])
            why[name] = reason
            # Published, never netted away: the same query with no grace, minus the debt, is
            # exactly the pipeline's work-in-progress for this component.
            in_flight[name] = max(0, int(conn.execute(sql, never).fetchone()[0]) - parts[name])
        except sqlite3.Error as exc:
            unmeasured.append({"component": name, "why": f"{type(exc).__name__}: {exc}"})
    cutoff = (now - timedelta(days=float(grace_days))).isoformat()
    try:
        parts["parked_past_grace"] = int(conn.execute(
            "SELECT COUNT(*) FROM research_candidates WHERE status=? AND updated_at<?",
            (ROUTED, cutoff)).fetchone()[0])
        why["parked_past_grace"] = (f"routed to an owner more than {grace_days:g} days ago and "
                                    "still not collected -- silence with extra steps")
    except sqlite3.Error as exc:
        unmeasured.append({"component": "parked_past_grace",
                           "why": f"{type(exc).__name__}: {exc}"})
    total = sum(parts.values())
    return {"measured_at": _now(), "components": parts, "why": why,
            "total_debt": total if not unmeasured else None,
            "status": UNMEASURED if unmeasured else "MEASURED",
            "unmeasured": unmeasured, "grace_days": float(grace_days),
            "in_flight": in_flight, "in_flight_total": sum(in_flight.values()),
            "in_flight_grace_h": float(in_flight_grace_h),
            "in_flight_rule": (f"a row minted in the last {in_flight_grace_h:g}h has not yet had "
                               "its turn; it is counted here, it is never a disposition, and it "
                               "becomes debt on the clock"),
            "rule": RULE}


# ---------------------------------------------------------------------------- the breadth
def participation_ratio(counts: Sequence[float]) -> float:
    """EFFECTIVE BREADTH: how many INDEPENDENT axis regions the testable population spans.

        p_i = n_i / sum_j n_j ;   rank_eff = 1 / sum_i p_i^2 = (sum n_i)^2 / sum n_i^2

    This is the desk's own participation ratio, in closed form. It is IDENTICAL to
    `libs.risk.fx_exposure.effective_rank(diag(sqrt(n)))` -- the singular values of that diagonal
    are sqrt(n_i), so the spectrum-as-a-distribution is exactly p_i above -- and the test
    `test_breadth_is_the_desks_own_effective_rank` pins the two together. The closed form is used
    because the matrix route would SVD a 30,000 x 30,000 diagonal to learn a number two sums
    already give.

    A FLAT POPULATION IS 0.0, not 1.0: no cells is no breadth, and reporting 1.0 would assert a
    region that is not occupied. One thousand candidates in one cell read 1.0; one thousand
    spread evenly over forty cells read 40.0. THAT is the number the backlog must drain toward.
    """
    vals = [float(c) for c in counts if float(c) > 0.0]
    total = sum(vals)
    if not vals or total <= 0.0:
        return 0.0
    sq = sum(v * v for v in vals)
    return float(min(len(vals), (total * total) / sq)) if sq > 0.0 else 0.0


def cell_counts(conn: sqlite3.Connection,
                statuses: Sequence[str] = TESTABLE_STATUSES) -> dict[str, int]:
    """How many TESTABLE cells sit in each axis region (registry `grid_cell`)."""
    marks = ",".join("?" * len(statuses))
    try:
        rows = conn.execute(
            f"SELECT grid_cell, COUNT(*) n FROM research_candidates "  # noqa: S608
            f"WHERE status IN ({marks}) AND COALESCE(falsifier,'')<>'' GROUP BY grid_cell",
            list(statuses)).fetchall()
    except sqlite3.Error:
        return {}
    return {str(r[0] or "unknown"): int(r[1]) for r in rows}


def measure_breadth(conn: sqlite3.Connection) -> dict[str, Any]:
    counts = cell_counts(conn)
    if not counts:
        return {"status": UNMEASURED, "nominal_cells": 0, "effective_breadth": 0.0,
                "n_testable": 0,
                "why": "no testable candidate carries a falsifier -- an empty population is not "
                       "a population with no breadth (L1.28a)"}
    eff = participation_ratio(list(counts.values()))
    return {"status": "MEASURED", "nominal_cells": len(counts),
            "effective_breadth": round(eff, 4), "n_testable": int(sum(counts.values())),
            "concentration": round(sum(counts.values()) / max(eff, 1e-9), 3),
            "basis": "participation ratio over registry grid_cell "
                     "(= libs.risk.fx_exposure.effective_rank of diag(sqrt(counts)))"}


# ------------------------------------------------------------------------ universe / lanes
_SYMBOL_RE = re.compile(r"\b[A-Z][A-Z0-9&._-]{2,14}\b")


def universe_symbols(path: Path | None = None) -> dict[str, dict[str, Any]]:
    doc = _read_json(path or UNIVERSE_JSON)
    if not isinstance(doc, Mapping):
        return {}
    return {str(k): (dict(v) if isinstance(v, Mapping) else {}) for k, v in doc.items()}


def _lane_ok(symbol: str) -> bool | None:
    """The two-lane verdict for a symbol: True hypothesis lane, False event lane, None unknown.

    None is NOT a permission. A symbol the registry cannot classify is UNCLASSIFIED and hunted by
    nothing (`universe_policy`), so this organ parks it rather than converting it.
    """
    try:
        from research.universe_policy import lane
    except Exception:
        return None
    try:
        verdict = lane(symbol)
    except Exception:
        return None
    if verdict == "hypothesis":
        return True
    if verdict == "event":
        return False
    return None


def _bar_file(symbol: str, chart: str, universe_dir: Path | None = None) -> Path | None:
    """The desk's own bar file for this instrument and chart, or None."""
    root = universe_dir or UNIVERSE_DIR
    if not symbol:
        return None
    charts = [chart.upper()] if chart else list(CHART_LADDER)
    for ch in charts:
        p = root / f"{symbol}_{ch}.parquet"
        if p.exists():
            return p
    return None


# --------------------------------------------------------------------------- the bar supply
#: The desk's chart ladder, finest first, with each chart's length in minutes. A chart COARSER
#: than one the desk holds is arithmetic (aggregate the finer bars); a chart FINER than the
#: finest held cannot be manufactured from anything and must be fetched.
CHART_MINUTES: dict[str, int] = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240,
                                 "D1": 1440}
CHART_LADDER: tuple[str, ...] = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")

#: Pandas offset aliases for each chart, so a resample is the desk's chart and not a guess.
_RESAMPLE_RULE: dict[str, str] = {"M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min",
                                  "H1": "1h", "H4": "4h", "D1": "1D"}

#: How OHLCV aggregates when bars are coarsened. `spread` takes the mean because it is a level,
#: not a flow; volumes sum; the four prices take first/max/min/last. Any column not named here is
#: dropped rather than silently mis-aggregated.
_AGG: dict[str, str] = {"open": "first", "high": "max", "low": "min", "close": "last",
                        "tick_volume": "sum", "spread": "mean", "real_volume": "sum"}

#: A resample that produces fewer than this many bars is not a series a gauntlet cell can be
#: judged on, and writing it would replace "no data" with "data that fails the next gate".
MIN_RESAMPLED_BARS = 200


def held_charts(symbol: str, universe_dir: Path | None = None) -> list[str]:
    """Every chart the desk actually holds for this instrument, finest first."""
    root = universe_dir or UNIVERSE_DIR
    if not symbol:
        return []
    return [ch for ch in CHART_LADDER if (root / f"{symbol}_{ch}.parquet").exists()]


def ensure_bars(symbol: str, chart: str, *, universe_dir: Path | None = None,
                write: bool = True) -> tuple[str, str, str]:
    """SUPPLY THE BARS. Returns (chart_supplied, action, note) -- never a refusal.

    THE PRINCIPAL'S ADDENDUM (2026-09-23): "they should never ever be blocked on bars -- always
    have bars for every single timeframe for all symbols, intraday bars, everything, permanently
    ... no data blockers or conversion blocks anything ever, always have ways around all
    blockers." A missing bar is WORK TO DO, never a verdict. There are three ways around it and
    this tries all three in order:

      1. HELD        the file is already on disk. Nothing to do.
      2. RESAMPLED   the wanted chart is COARSER than one the desk holds, so it is arithmetic:
                     the finer bars are aggregated (first/max/min/last, volumes summed, spread
                     averaged) and the parquet is written. This is exact -- an H4 bar IS four H1
                     bars -- and it is why a symbol with H1 can never be missing H4 or D1 again.
      3. REBOUND     the wanted chart is FINER than the finest the desk holds, and finer bars
                     cannot be manufactured from coarser ones by any honest arithmetic. The cell
                     is bound to the FINEST chart the desk DOES hold, which is a testable cell
                     today, and the fetch is requested so the wanted chart exists tomorrow.

    Only a symbol with NO series at all returns `request`, and even then the caller keeps the row
    QUEUED with the blocker named -- it is never parked and never refused.
    """
    want = (chart or "H1").upper()
    if want not in CHART_MINUTES:
        want = "H1"
    root = universe_dir or UNIVERSE_DIR
    if not symbol:
        return "", "request", "no instrument, so no series can be supplied"
    if (root / f"{symbol}_{want}.parquet").exists():
        return want, "held", ""
    held = held_charts(symbol, universe_dir=root)
    if not held:
        return "", "request", (f"the desk holds no series at all for {symbol}; queued as a bar "
                               f"request for the fetcher (research/fetch_universe.py)")
    finer = [ch for ch in held if CHART_MINUTES[ch] < CHART_MINUTES[want]]
    if finer and write:
        src = max(finer, key=lambda ch: CHART_MINUTES[ch])   # the coarsest source that still fits
        ok, why = _resample(symbol, src, want, root)
        if ok:
            return want, f"resampled from {src}", why
        return src, "rebound", (f"{want} could not be built from {src} ({why}); the cell is bound "
                                f"to {src}, which the desk holds")
    if finer and not write:                                              # pragma: no cover
        return want, "resampleable", f"{want} can be built from {max(finer)}"
    coarsest_available = min(held, key=lambda ch: abs(CHART_MINUTES[ch] - CHART_MINUTES[want]))
    return coarsest_available, "rebound", (
        f"{want} is finer than the finest series the desk holds for {symbol} "
        f"({held[0]}) and finer bars cannot be made from coarser ones; the cell is bound to "
        f"{coarsest_available} and {want} is queued as a bar request")


def backfill_bars(coverage: Mapping[str, Any], *, budget: Budget,
                  universe_dir: Path | None = None, limit: int = 200) -> dict[str, Any]:
    """BUILD EVERY SERIES THE ARITHMETIC ALLOWS, every hour, until the ladder is full.

    The coverage report is not a description, it is a WORK LIST (principal's addendum
    2026-09-23: "keep a per-symbol per-timeframe bar-coverage report that drives that backfill
    every hour until every symbol has every timeframe including intraday"). Everything marked
    `resampleable` is built here under whatever budget the pass has left; everything marked
    `fetch` is genuinely finer than anything the desk holds and is named for the fetcher.
    """
    built: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []
    todo = list(coverage.get("resampleable") or [])[:limit]
    for job in todo:
        if not budget.ok("backfill_bars", reserve=3.0):
            break
        sym, chart = str(job.get("symbol") or ""), str(job.get("chart") or "")
        got, action, why = ensure_bars(sym, chart, universe_dir=universe_dir)
        if got == chart and action.startswith("resampled"):
            built.append({"symbol": sym, "chart": chart, "detail": why})
        elif action != "held":
            failed.append({"symbol": sym, "chart": chart, "why": why or action})
    return {"attempted": len(todo), "built": len(built), "failed": len(failed),
            "remaining_resampleable": max(0, len(coverage.get("resampleable") or []) - len(todo)),
            "examples": built[:20], "failures": failed[:20],
            "rule": "the coverage report is a work list, not a description: every series the "
                    "arithmetic allows is built each hour until the ladder is full"}


def _resample(symbol: str, src: str, want: str, root: Path) -> tuple[bool, str]:
    """Aggregate `src` bars into `want` bars and write the parquet. Exact, never interpolated."""
    try:
        import pandas as pd
    except Exception as exc:                                             # pragma: no cover
        return False, f"pandas is unavailable ({type(exc).__name__})"
    try:
        frame = pd.read_parquet(root / f"{symbol}_{src}.parquet")
    except Exception as exc:
        return False, f"the {src} series is unreadable ({type(exc).__name__}: {exc})"
    if frame.empty or not isinstance(frame.index, pd.DatetimeIndex):
        return False, f"the {src} series has no usable time index"
    agg = {c: how for c, how in _AGG.items() if c in frame.columns}
    if "close" not in agg:
        return False, f"the {src} series carries no close column"
    try:
        out = frame.resample(_RESAMPLE_RULE[want], label="left", closed="left").agg(agg).dropna(
            subset=["close"])
    except Exception as exc:                                             # pragma: no cover
        return False, f"resample raised {type(exc).__name__}: {exc}"
    if len(out) < MIN_RESAMPLED_BARS:
        return False, (f"{len(out)} bars is below the {MIN_RESAMPLED_BARS}-bar minimum a cell "
                       f"can be judged on")
    for col in ("tick_volume", "real_volume"):
        if col in out.columns:
            out[col] = out[col].astype("int64")
    path = root / f"{symbol}_{want}.parquet"
    tmp = path.with_suffix(".parquet.tmp")
    try:
        root.mkdir(parents=True, exist_ok=True)
        out.to_parquet(tmp)
        os.replace(tmp, path)
    except Exception as exc:                                             # pragma: no cover
        with contextlib.suppress(OSError):
            tmp.unlink()
        return False, f"the {want} parquet could not be written ({type(exc).__name__}: {exc})"
    return True, f"{len(out)} {want} bars aggregated from {len(frame)} {src} bars"


def bar_coverage(symbols: Sequence[str], *, universe_dir: Path | None = None,
                 limit: int = 400) -> dict[str, Any]:
    """PER SYMBOL x PER TIMEFRAME: what the desk holds, what is resampleable, what must be
    fetched. This is the report that DRIVES the backfill every hour rather than describing it.

    Only HYPOTHESIS-lane symbols are required to carry the full ladder: the two-lane law
    (2026-09-06) trades single names on news and never hunts them, so demanding M1 for 154 share
    CFDs would manufacture 900 fetch requests for series no hypothesis will ever be judged on.
    """
    root = universe_dir or UNIVERSE_DIR
    rows: dict[str, dict[str, str]] = {}
    fetch: list[dict[str, str]] = []
    by_chart: dict[str, int] = dict.fromkeys(CHART_LADDER, 0)
    resampleable = 0
    considered = 0
    for sym in list(dict.fromkeys(symbols))[:limit]:
        if _lane_ok(sym) is not True:
            continue
        considered += 1
        held = held_charts(sym, universe_dir=root)
        finest = CHART_MINUTES[held[0]] if held else None
        state: dict[str, str] = {}
        for ch in CHART_LADDER:
            if ch in held:
                state[ch] = "held"
                by_chart[ch] += 1
            elif finest is not None and CHART_MINUTES[ch] > finest:
                state[ch] = "resampleable"
                resampleable += 1
            else:
                state[ch] = "fetch"
                fetch.append({"symbol": sym, "chart": ch,
                              "why": "finer than the finest series held"
                                     if held else "the desk holds no series for this symbol"})
        rows[sym] = state
    full = sum(1 for s in rows.values() if all(v == "held" for v in s.values()))
    todo = [{"symbol": sym, "chart": ch} for sym, state in rows.items()
            for ch in CHART_LADDER if state[ch] == "resampleable"]
    return {"symbols_measured": considered, "charts": list(CHART_LADDER),
            "held_by_chart": by_chart, "symbols_with_full_ladder": full,
            "resampleable_series": resampleable, "fetch_requests": len(fetch),
            "resampleable": todo, "fetch": fetch[:200],
            "per_symbol": dict(list(rows.items())[:80]),
            "rule": "a missing bar is work to do, never a verdict: coarser charts are resampled "
                    "on the spot, finer ones are requested, and the cell is bound to the finest "
                    "series the desk holds meanwhile",
            "owner": "desks/mt5/research/fetch_universe.py via the hourly `refresh_bars` leg"}


def _family_for(mechanism: str, declared: str = "") -> tuple[str, str]:
    """A REGISTERED family that implements this mechanism, plus the basis. ('', reason) when the
    desk implements none -- never a family that would test a different claim."""
    try:
        from research import axis_registry as AR
        from research.discovery_compiler import interpret
    except Exception as exc:                                             # pragma: no cover
        return "", f"{UNMEASURED}: the family table is unreadable ({type(exc).__name__}: {exc})"
    try:
        mech_id, information = interpret(mechanism, declared)
    except Exception as exc:                                             # pragma: no cover
        return "", f"{UNMEASURED}: interpret raised {type(exc).__name__}: {exc}"
    table: dict[str, tuple[str, str, str]] = getattr(AR, "FAMILY_TABLE", {})
    not_a_family: frozenset[str] = getattr(AR, "NOT_A_FAMILY", frozenset())
    exact = sorted(f for f, (m, i, _s) in table.items()
                   if m == mech_id and i == information and f not in not_a_family)
    if exact:
        return exact[0], f"axis_registry.FAMILY_TABLE[{mech_id} / {information}]"
    loose = sorted(f for f, (m, _i, _s) in table.items()
                   if m == mech_id and f not in not_a_family)
    if loose:
        return loose[0], f"axis_registry.FAMILY_TABLE[{mech_id}]"
    return "", (f"no registered family implements mechanism {mech_id!r} on {information!r}; "
                "assigning one would test a different claim")


# ----------------------------------------------------------------------------- the repairs
def classify(row: Mapping[str, Any]) -> tuple[str, Any]:
    """('OK', spec) or (reason, defect) in the compilers' own defect vocabulary."""
    spec = XS.compile_row(row)
    if isinstance(spec, XS.CompileDefect):
        return spec.reason, spec
    return "OK", spec


def repair(row: Mapping[str, Any], reason: str, *,
           universe_dir: Path | None = None) -> tuple[dict[str, Any], list[str], str]:
    """Attempt the repair this blocker class needs. Returns (row, actions, note).

    NOTHING ABOUT THE WORLD IS GUESSED. Every field added is either the desk's own artifact (the
    bar file it holds) or the desk's own standing procedure (re-judgement, the family table, the
    universe registry), and each carries a `*_basis` key so a reader can tell a derived field from
    a declared one. That distinction is the difference between enrichment and invention.
    """
    out = dict(row)
    actions: list[str] = []
    note = ""
    if reason in ("NO_INSTRUMENT", "PROSE_ONLY"):
        sym, basis = _resolve_instrument(out, universe_dir=universe_dir)
        if sym:
            out["symbol"] = sym
            out["symbol_basis"] = basis
            actions.append(f"bound instrument {sym}")
        else:
            note = basis
    if reason in ("NO_FAMILY", "PROSE_ONLY") and not str(out.get("family") or ""):
        fam, basis = _family_for(str(out.get("mechanism") or ""),
                                 str(out.get("mechanism_id") or ""))
        if fam:
            out["family"] = fam
            out["family_basis"] = basis
            actions.append(f"bound family {fam}")
        else:
            note = note or basis
    # The falsifier and the data snapshot are filled for EVERY class, because a row repaired on
    # its instrument still fails the contract on the next field and would be counted as an
    # unrepairable NO_FALSIFIER one pass later.
    if not str(out.get("falsifier") or ""):
        fam = str(out.get("family") or "")
        sym = str(out.get("symbol") or "")
        if fam and sym:
            out["falsifier"] = (f"the exact {fam} rule on {sym} re-judged on bars after the "
                                f"snapshot no longer clears the ten gates")
            out["falsifier_basis"] = "derived: the desk's standing re-judgement procedure"
            actions.append("supplied falsifier")
    # THE BARS ARE SUPPLIED, NOT DEMANDED (principal's addendum 2026-09-23: "they should never
    # ever be blocked on bars"). A chart the desk does not hold is built by aggregation when the
    # arithmetic allows it, and otherwise the cell is bound to the finest series the desk DOES
    # hold and the fetch is requested. A missing bar never stops a conversion.
    if not _has_data(out):
        sym = str(out.get("symbol") or "")
        chart, action, why = ensure_bars(sym, str(out.get("chart") or ""),
                                         universe_dir=universe_dir)
        if chart:
            out["chart"] = chart
            if action != "held":
                out["chart_basis"] = f"{action}: {why}" if why else action
                actions.append(f"{action} {sym} {chart}")
            bar = _bar_file(sym, chart, universe_dir=universe_dir)
        else:
            bar = None
        if bar is not None:
            try:
                rel = str(bar.resolve().relative_to(REPO)).replace("\\", "/")
            except ValueError:
                rel = bar.name
            out["required_data_json"] = json.dumps([rel])
            out["required_data"] = [rel]
            out["data_vintage"] = datetime.fromtimestamp(
                bar.stat().st_mtime, tz=UTC).isoformat(timespec="seconds")
            out["required_data_basis"] = ("derived: the desk's own bar file for this instrument "
                                          "and chart; the vintage is that file's mtime")
            actions.append("named the data")
        else:
            note = note or why or (f"the desk holds no series for {sym or '?'}; the fetch is "
                                   f"requested and the row stays queued with this blocker")
    return out, actions, note


def _has_data(row: Mapping[str, Any]) -> bool:
    raw = row.get("required_data_json") or row.get("required_data")
    if isinstance(raw, str):
        return raw.strip() not in ("", "null", "[]", "None")
    return bool(raw)


def _resolve_instrument(row: Mapping[str, Any], *,
                        universe_dir: Path | None = None) -> tuple[str, str]:
    """Find the row's instrument in the MT5 universe registry, HYPOTHESIS LANE ONLY.

    A single-name equity mentioned in a claim is not an instrument this row may be hypothesised
    on: the two-lane law (2026-09-06) routes it to the event lane, and a symbol the registry
    cannot classify is UNCLASSIFIED and hunted by nothing. Both come back as a named refusal.
    """
    known = universe_symbols((universe_dir or UNIVERSE_DIR) / "universe.json")
    if not known:
        return "", f"{UNMEASURED}: the universe registry is unreadable, so no symbol resolves"
    declared = [str(row.get(k) or "") for k in ("symbol", "instrument")]
    blob = " ".join([*declared, str(row.get("mechanism") or ""),
                     str(row.get("causal_rationale") or ""), str(row.get("information") or "")])
    event_lane: list[str] = []
    for token in dict.fromkeys(_SYMBOL_RE.findall(blob.upper())):
        if token not in known:
            continue
        verdict = _lane_ok(token)
        if verdict is True:
            return token, "desks/mt5/data/universe/universe.json (hypothesis lane)"
        if verdict is False:
            event_lane.append(token)
    if event_lane:
        return "", (f"EVENT_LANE: {', '.join(event_lane[:4])} are single names; the two-lane law "
                    "(2026-09-06) trades them on news and never hunts them for hypotheses")
    return "", "no symbol in this row resolves to the MT5 universe registry"


# ------------------------------------------------------------------------------- the pass
def oldest_unconverted(conn: sqlite3.Connection) -> dict[str, Any]:
    """THE AGE OF THE OLDEST ROW STILL WAITING, published every pass.

    "Nothing should be queued in the research system, all immediate tested" (principal
    2026-09-23). A count alone cannot tell a drain from a stall: both look like a flat number.
    The OLDEST row's age can -- under a real drain it falls, and under a stall it rises one day
    per day. So it is published every pass, and it is the number to look at first.
    """
    try:
        row = conn.execute(
            "SELECT id, status, created_at FROM research_candidates WHERE status='donated' "
            "OR (status IN ('queued','claimed') AND COALESCE(falsifier,'')='') "
            "ORDER BY created_at LIMIT 1").fetchone()
    except sqlite3.Error as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    if row is None:
        return {"status": "NONE", "age_days": 0.0,
                "why": "no row is waiting: every candidate is either testable or refused"}
    age = _age_days({"created_at": row[2]})
    return {"status": "MEASURED", "id": str(row[0]), "row_status": str(row[1]),
            "created_at": str(row[2]), "age_days": age,
            "rule": "a stall shows here first: this number rises one day per day when the "
                    "backlog is being re-counted instead of drained"}


def judged_vs_docket(*, limit: int = 40) -> dict[str, Any]:
    """WHAT THE DESK MINES VERSUS WHAT THE JUDGE TESTS, per family, and the capacity a
    live-banned family was consuming.

    MEASURED ON THE BOX 2026-09-23 from 120,000 gate verdicts. The family `discovered` -- banned
    from live capital by the principal's order and refused at BOTH live doors by
    `mt5desk/live_policy.py` -- had taken 22,009 judgements, about 18% of recent capacity, and
    passed ZERO. It cannot reach the book even if it passes, so that whole share bought an
    outcome the desk had already forbidden. Meanwhile the docket's largest families
    (cross_asset_residual 55,190, overnight_drift 26,721, clock_transition 20,081,
    execution_state 13,660) barely appeared among judged cells at all.

    The imbalance was invisible because nobody divided one number by the other. This publishes
    `judged / docket` for every family every hour, so it can never hide again. The ROUTING lives
    in `merge_hypotheses` (the study bank and the least-judged-first docket order); this is the
    measurement that makes the routing auditable.
    """
    try:
        from research.merge_hypotheses import (
            STUDY_BANK,
            TARGET,
            judged_by_family,
            live_banned_families,
        )
    except Exception as exc:                                             # pragma: no cover
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    judged = judged_by_family()
    docket_rows = _read_json(TARGET)
    study_rows = _read_json(STUDY_BANK)
    if not isinstance(docket_rows, list):
        return {"status": UNMEASURED,
                "why": f"the docket at {TARGET} is unreadable, so no ratio can be formed"}
    docket: dict[str, int] = {}
    for row in docket_rows:
        if isinstance(row, Mapping):
            fam = str(row.get("family") or "unknown")
            docket[fam] = docket.get(fam, 0) + 1
    banned = live_banned_families()
    total_judged = sum(judged.values()) or 1
    table = {
        fam: {"docket": n, "judged": judged.get(fam, 0),
              "judged_per_docket_row": round(judged.get(fam, 0) / max(n, 1), 4),
              "share_of_judge": round(judged.get(fam, 0) / total_judged, 4)}
        for fam, n in docket.items()}
    # The worst rows are the biggest dockets the judge has touched least: that product is the
    # untested opportunity, in cells.
    worst = sorted(table.items(), key=lambda kv: (kv[1]["judged_per_docket_row"],
                                                  -kv[1]["docket"]))[:limit]
    freed = {fam: judged.get(fam, 0) for fam in sorted(banned)}
    return {"status": "MEASURED", "families": len(table),
            "docket_rows": len(docket_rows),
            "judged_rows_counted": sum(judged.values()),
            "least_judged_first": dict(worst),
            "banned_from_live": sorted(banned),
            "judge_capacity_freed": {"judgements": sum(freed.values()),
                                     "share_of_judge": round(
                                         sum(freed.values()) / total_judged, 4),
                                     "per_family": freed,
                                     "study_bank_rows": len(study_rows)
                                     if isinstance(study_rows, list) else None},
            "rule": "a family that cannot reach live capital is never judged and never deleted; "
                    "order is selection, so the least-judged family goes to the gates first"}


def _read_carry(path: Path | None = None) -> list[str]:
    doc = _read_json(path or CARRY)
    ids = doc.get("ids") if isinstance(doc, Mapping) else None
    return [str(i) for i in ids][:MAX_CARRY] if isinstance(ids, list) else []


def _write_carry(ids: Sequence[str], path: Path | None = None) -> None:
    """Hand this pass's leftover to the next one. IDS ONLY -- never rows.

    A file that held the rows themselves would be a second store beside the registry, which is
    the defect the registry exists to prevent. This holds names, so the next pass re-reads the
    rows from the one store and a row deleted meanwhile simply is not found.
    """
    _atomic_write(path or CARRY, {
        "generated_utc": _now(), "ids": list(ids)[:MAX_CARRY], "n": min(len(ids), MAX_CARRY),
        "rule": "no queues: a pass that ran out of budget hands its remainder to the next pass "
                "as the FIRST work, and the oldest waiting row's age is published every pass"})


def _rank_key(row: Mapping[str, Any], counts: Mapping[str, int]) -> tuple[float, str]:
    """ORTHOGONAL BREADTH FIRST. A row landing in an empty or thin axis region is repaired before
    one landing where the docket is already crowded, so the backlog drains toward INDEPENDENT
    cells. This is LAWS 5b applied to the conversion queue: quantity has zero intrinsic value."""
    try:
        cell = R.grid_cell(row)
    except Exception:                                                    # pragma: no cover
        cell = str(row.get("grid_cell") or "unknown")
    return (float(counts.get(cell, 0)), str(row.get("id") or row.get("discovery_id") or ""))


def _debt_rows(conn: sqlite3.Connection, pool: int, *,
               carry: Sequence[str] = ()) -> list[dict[str, Any]]:
    """The debt population this pass may work on. LAST PASS'S LEFTOVER COMES FIRST.

    "Nothing should be queued ... all immediate tested" (principal 2026-09-23): a row the last
    pass could not reach before its budget ran out is not parked, it is the FIRST work here. Only
    then does the pass draw fresh rows, the donated backlog first.
    """
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    if carry:
        head = list(carry)[:900]
        marks = ",".join("?" * len(head))
        try:
            cur = conn.execute(
                f"SELECT * FROM research_candidates WHERE id IN ({marks}) "  # noqa: S608
                "AND (status='donated' OR (status IN ('queued','claimed') "
                "AND COALESCE(falsifier,'')=''))", head)
            cols = [c[0] for c in cur.description]
            for r in cur.fetchall():
                row = dict(zip(cols, r, strict=False))
                rows.append(row)
                seen.add(str(row.get("id") or ""))
        except sqlite3.Error:
            pass
    # THE DONATED BACKLOG IS THE TARGET (principal's addendum 2026-09-23: "the 234,996 donated
    # candidates that never reached the judge are the target"), so it takes two thirds of the
    # pool. The queued-but-untestable rows take the rest: they are already on the queue and a
    # judge will reach them the moment their falsifier exists.
    donated = max(1, (pool * 2) // 3)
    for sql, args in (
        ("SELECT * FROM research_candidates WHERE status='donated' "
         "ORDER BY updated_at DESC LIMIT ?", (donated,)),
        ("SELECT * FROM research_candidates WHERE status IN ('queued','claimed') "
         "AND COALESCE(falsifier,'')='' ORDER BY updated_at DESC LIMIT ?",
         (max(1, pool - donated),)),
    ):
        try:
            cur = conn.execute(sql, args)
            cols = [c[0] for c in cur.description]
            for r in cur.fetchall():
                row = dict(zip(cols, r, strict=False))
                if str(row.get("id") or "") not in seen:
                    rows.append(row)
        except sqlite3.Error:
            continue
    return rows


def _age_days(row: Mapping[str, Any]) -> float | None:
    """How long this row has been unconverted, in days. None when nothing stamps it."""
    for key in ("created_at", "updated_at"):
        raw = str(row.get(key) or "")
        if not raw:
            continue
        try:
            stamp = datetime.fromisoformat(raw)
        except ValueError:
            continue
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=UTC)
        return round((datetime.now(tz=UTC) - stamp).total_seconds() / 86400.0, 3)
    return None


def _median(values: Sequence[float]) -> float | None:
    vals = sorted(float(v) for v in values)
    if not vals:
        return None
    mid = len(vals) // 2
    return round(vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2.0, 3)


def _keep_queued(conn: sqlite3.Connection, cid: str, blocker: str, owner: str,
                 detail: str) -> bool:
    """A row this pass could not repair STAYS QUEUED, carrying its blocker and its owner.

    THE PRINCIPAL'S ADDENDUM (2026-09-23): a row that cannot be repaired this pass "stays QUEUED
    with its named blocker and an owner ... it may never be parked as 'blocked' and forgotten".
    So the disposition is written onto the row rather than into a siding: the next pass sees it
    again, `untestable_queued` keeps counting it, and the ratchet keeps the pressure on.
    """
    if not cid:
        return False
    try:
        return bool(R.mark_candidate(
            cid, "queued", conn=conn, failure_class=blocker,
            rejection_reason=f"{blocker} (owner: {owner}): {detail}"[:400]))
    except sqlite3.Error:
        return False


def _park(conn: sqlite3.Connection, cid: str, status: str, reason: str) -> bool:
    try:
        return bool(R.mark_candidate(cid, status, conn=conn, rejection_reason=reason[:400],
                                     failure_class=status))
    except sqlite3.Error:
        return False


def _naming_requests(rows: Sequence[Mapping[str, Any]], seat_dir: Path | None = None) -> str:
    """Route prose-only rows to the understanding/naming seat as a seat donation.

    Seat output goes through `data/intelligence/<seat>/` (CLAUDE.md), which is where
    `understanding_seat.intelligence_documents` reads. The key is `naming_requests` rather than
    one of `discovery_compiler._ROW_KEYS` deliberately: these rows are a REQUEST for a name, and
    letting the compiler re-ingest them would mint a second discovery for a row that already has
    one and loop the debt back onto itself.
    """
    if not rows:
        return ""
    target = (seat_dir or SEAT_DIR)
    path = target / f"naming_requests_{datetime.now(tz=UTC).strftime('%Y%m%d_%H%M%S')}.json"
    _atomic_write(path, {"seat": SEAT, "generated_utc": _now(),
                         "task": "NAME_THE_MECHANISM",
                         "owner": DEFECT_OWNER["PROSE_ONLY"],
                         "rule": RULE, "naming_requests": list(rows)})
    return str(path)


def _acquisition_tasks(rows: Sequence[Mapping[str, Any]], seat_dir: Path | None = None) -> str:
    """Name the missing data as an acquisition task for the data-acquisition scientist."""
    if not rows:
        return ""
    target = (seat_dir or SEAT_DIR)
    path = target / f"acquisition_tasks_{datetime.now(tz=UTC).strftime('%Y%m%d_%H%M%S')}.json"
    _atomic_write(path, {"seat": SEAT, "generated_utc": _now(), "task": "ACQUIRE",
                         "owner": DEFECT_OWNER["NO_DATA"], "rule": RULE,
                         "acquisition_tasks": list(rows)})
    return str(path)


def run(*, budget: Budget, conn: sqlite3.Connection, max_rows: int, dry_run: bool,
        universe_dir: Path | None = None, seat_dir: Path | None = None,
        carry_path: Path | None = None,
        grace_days: float = GRACE_DAYS) -> dict[str, Any]:
    """One pass: measure, classify, prioritise by breadth, act, re-enqueue, measure again."""
    debt_before = measure_debt(conn, grace_days=grace_days)
    breadth_before = measure_breadth(conn)
    counts = cell_counts(conn)

    pool = min(POOL_CEILING, max(max_rows, max_rows * POOL_FACTOR))
    carried = _read_carry(carry_path)
    population = _debt_rows(conn, pool, carry=carried)
    # THE LEFTOVER KEEPS ITS PLACE AT THE FRONT. Within each half the order is by the breadth a
    # conversion adds, but a row the last pass could not reach is not re-ranked against fresh
    # arrivals -- that is how a tail starves while the report says the backlog is being worked.
    carried_set = set(carried)
    population.sort(key=lambda r: (str(r.get("id") or "") not in carried_set,
                                   *_rank_key(r, counts)))

    histogram: dict[str, int] = {}
    per_source: dict[str, dict[str, int]] = {}
    per_class: dict[str, dict[str, Any]] = {}
    banned_families = live_banned_families()
    repaired: list[dict[str, Any]] = []
    studied: list[dict[str, Any]] = []
    refusals: list[dict[str, Any]] = []
    parked: list[dict[str, Any]] = []
    naming: list[dict[str, Any]] = []
    acquisitions: list[dict[str, Any]] = []
    wanted_symbols: list[str] = []
    enqueued = created = 0
    examined = 0

    def _class(name: str) -> dict[str, Any]:
        return per_class.setdefault(name, {"seen": 0, "repaired": 0, "refused": 0,
                                           "still_blocked": 0, "ages_days": []})

    leftover: list[str] = []
    for index, row in enumerate(population):
        if examined >= max_rows or not budget.ok("convert", reserve=5.0):
            leftover = [str(r.get("id") or "") for r in population[index:]
                        if str(r.get("id") or "")]
            break
        examined += 1
        cid = str(row.get("id") or "")
        origin = str(row.get("origin") or row.get("generator") or "unknown")
        stat = per_source.setdefault(origin, {"examined": 0, "repaired": 0, "refused": 0,
                                              "still_blocked": 0})
        stat["examined"] += 1
        reason, obj = classify(row)
        histogram[reason] = histogram.get(reason, 0) + 1
        age = _age_days(row)
        cls = _class(reason)
        cls["seen"] += 1
        if age is not None:
            cls["ages_days"].append(age)
        wanted_symbols.append(str(row.get("symbol") or ""))
        if reason == "OFF_UNIVERSE":
            detail = getattr(obj, "detail", "") or DEFECT_OWNER["OFF_UNIVERSE"]
            refusals.append({"id": cid, "reason": "OFF_UNIVERSE", "detail": detail,
                             "owner": DEFECT_OWNER["OFF_UNIVERSE"]})
            stat["refused"] += 1
            cls["refused"] += 1
            if not dry_run:
                _park(conn, cid, RETIRED, f"OFF_UNIVERSE: {detail}")
            continue
        if reason == "OK":
            # Already compiles: it was debt because it sat in `donated` and nobody offered it to
            # a judge. Enqueueing IS the repair.
            fixed, actions, note = dict(row), ["already compiled -- never offered to a judge"], ""
        else:
            fixed, actions, note = repair(row, reason, universe_dir=universe_dir)
            reason2, obj = classify(fixed)
            if reason2 != "OK":
                owner = DEFECT_OWNER.get(reason2, "unassigned")
                detail = note or getattr(obj, "detail", "") or reason2
                if detail.startswith("EVENT_LANE"):
                    reason2, owner = "EVENT_LANE", DEFECT_OWNER["EVENT_LANE"]
                entry = {"id": cid, "reason": reason2, "detail": detail[:400], "owner": owner,
                         "actions_taken": actions, "age_days": age}
                if reason2 in REFUSAL_CLASSES:
                    # THE ONLY ADMISSIBLE PERMANENT REFUSALS (principal's addendum 2026-09-23):
                    # ground the desk is forbidden to hunt, and an instrument the venue does not
                    # quote for this lane. Everything else is work, not a verdict.
                    refusals.append(entry)
                    stat["refused"] += 1
                    cls["refused"] += 1
                    if not dry_run:
                        _park(conn, cid, RETIRED, f"{reason2}: {detail}"[:400])
                    continue
                # NOT PARKED, EVER (principal's addendum). A row this pass could not repair stays
                # QUEUED carrying its named blocker and its owner, so the next pass sees it again
                # and the unrepaired backlog ratchets down instead of quietly becoming "blocked".
                parked.append(entry)
                stat["still_blocked"] += 1
                cls["still_blocked"] += 1
                if reason2 in ("PROSE_ONLY", "NO_INSTRUMENT"):
                    naming.append({"id": cid, "mechanism": str(row.get("mechanism") or "")[:400],
                                   "origin": origin, "needs": "an instrument and a family",
                                   "detail": detail[:400]})
                elif reason2 == "NO_DATA":
                    acquisitions.append({"id": cid, "symbol": str(fixed.get("symbol") or ""),
                                         "chart": str(fixed.get("chart") or ""),
                                         "origin": origin, "detail": detail[:400]})
                if not dry_run:
                    _keep_queued(conn, cid, reason2, owner, detail)
                continue
        spec = obj if not isinstance(obj, XS.CompileDefect) else None
        if spec is None:
            spec_or_defect = XS.compile_row(fixed)
            if isinstance(spec_or_defect, XS.CompileDefect):             # pragma: no cover
                continue
            spec = spec_or_defect
        if spec.family in banned_families:
            # REPAIRED, AND STILL NOT PUT IN FRONT OF THE JUDGE. The row is complete and stays --
            # mining is unrestricted -- but its family is refused at both live doors, so a
            # gate-second spent on it buys an outcome the desk has already forbidden.
            studied.append({"id": cid, "family": spec.family, "reason": reason,
                            "detail": STUDY_REASON.format(family=spec.family)})
            stat["studied"] = stat.get("studied", 0) + 1
            cls["studied"] = int(cls.get("studied") or 0) + 1
            if not dry_run:
                _park(conn, cid, STUDY, STUDY_REASON.format(family=spec.family))
            continue
        repaired.append({"id": cid, "reason": reason, "actions": actions,
                         "family": spec.family, "symbol": spec.symbols[0] if spec.symbols else "",
                         "grid_cell_before": str(row.get("grid_cell") or ""), "age_days": age})
        stat["repaired"] += 1
        cls["repaired"] += 1
        if dry_run:
            continue
        try:
            new_id, was_new = XS.enqueue(spec, conn=conn)
            enqueued += 1
            created += int(was_new)
            if cid and new_id != cid:
                # Binding a family or an instrument CHANGES the content hash, so the repair is a
                # NEW cell and the original row is its ancestor, not a second copy of it. Marking
                # the ancestor `queued` too would put one rule on the queue twice and charge the
                # desk two trials for one look at the tape.
                R.link("cell", cid, "cell", new_id, "conversion_repair", conn=conn)
                R.mark_candidate(cid, RETIRED, conn=conn,
                                 rejection_reason=f"superseded: repaired by {SEAT} into cell "
                                                  f"{new_id} ({', '.join(actions)})"[:400])
            elif cid:
                R.mark_candidate(cid, "queued", conn=conn, falsifier=spec.falsifier,
                                 required_data_json=json.dumps(list(spec.data_snapshot.datasets)),
                                 family=spec.family or str(row.get("family") or ""))
        except (sqlite3.Error, ValueError) as exc:                       # pragma: no cover
            parked.append({"id": cid, "reason": "ENQUEUE_FAILED",
                           "detail": f"{type(exc).__name__}: {exc}",
                           "owner": "libs/moat/registry.py enqueue_candidate"})
            repaired.pop()
            stat["repaired"] -= 1
            cls["repaired"] -= 1

    # EFFECTIVE TRIALS, not raw count: re-enqueued work pays the multiple-testing bill it owes,
    # and 500 mutations of one rule are not 500 independent looks at the tape.
    charge = _charge_trials(repaired, conn, dry_run=dry_run)
    naming_path = "" if dry_run else _naming_requests(naming, seat_dir)
    acq_path = "" if dry_run else _acquisition_tasks(acquisitions, seat_dir)

    if not dry_run:
        _write_carry(leftover, carry_path)
    # THE WHOLE HYPOTHESIS-LANE UNIVERSE, not only the symbols this pass happened to touch: the
    # mandate is every symbol at every timeframe, so the coverage that drives the backfill has to
    # be measured over the registry rather than over the sample.
    coverage = bar_coverage([*universe_symbols((universe_dir or UNIVERSE_DIR) / "universe.json"),
                             *wanted_symbols], universe_dir=universe_dir)
    coverage["backfill"] = ({"skipped": "dry run"} if dry_run else
                            backfill_bars(coverage, budget=budget, universe_dir=universe_dir))
    debt_after = measure_debt(conn, grace_days=grace_days)
    breadth_after = measure_breadth(conn)
    return {
        "examined": examined, "pool": len(population), "max_rows": max_rows,
        "blocker_histogram": dict(sorted(histogram.items(), key=lambda kv: -kv[1])),
        "blocker_owner": {k: DEFECT_OWNER.get(k, "unassigned") for k in histogram},
        "per_blocker_class": _class_table(per_class),
        "repaired": len(repaired), "enqueued": enqueued, "new_cells": created,
        "refused": len(refusals), "still_blocked": len(parked),
        "routed_to_study": len(studied), "study_rows": studied[:40],
        "banned_from_live": sorted(banned_families),
        "repairs": repaired[:60], "refusals": refusals[:60], "still_blocked_rows": parked[:60],
        "bar_coverage": coverage,
        "refusal_policy": REFUSAL_POLICY,
        "judged_vs_docket": judged_vs_docket(),
        "oldest_unconverted": oldest_unconverted(conn),
        "carried_in": len(carried), "carried_out": len(leftover),
        "carry_rule": "no queues: this pass's leftover is the FIRST work of the next pass, and "
                      "the oldest waiting row's age is published every pass",
        "per_source": per_source,
        "naming_requests": {"rows": len(naming), "path": naming_path,
                            "owner": DEFECT_OWNER["PROSE_ONLY"]},
        "acquisition_tasks": {"rows": len(acquisitions), "path": acq_path,
                              "owner": DEFECT_OWNER["NO_DATA"]},
        "effective_trials_charged": charge,
        "debt_before": debt_before, "debt_after": debt_after,
        "breadth_before": breadth_before, "breadth_after": breadth_after,
        "breadth_delta": _breadth_delta(breadth_before, breadth_after),
    }


def _class_table(per_class: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """PER BLOCKER CLASS: the count, the repair rate and the MEDIAN AGE.

    The principal's addendum asks for exactly these three, "so a class that stops falling is
    visible the same day". The age is what makes the difference between a class that is being
    drained and one that is merely being re-counted: under a real drain the old rows convert and
    the median falls, while treading water raises it one day per day with the count unchanged.
    """
    out: dict[str, dict[str, Any]] = {}
    for name, stat in per_class.items():
        seen = int(stat.get("seen") or 0)
        ages = list(stat.get("ages_days") or [])
        out[name] = {
            "seen": seen, "repaired": int(stat.get("repaired") or 0),
            "refused": int(stat.get("refused") or 0),
            "still_blocked": int(stat.get("still_blocked") or 0),
            "repair_rate": round(int(stat.get("repaired") or 0) / seen, 4) if seen else None,
            "median_age_days": _median(ages),
            "oldest_age_days": round(max(ages), 3) if ages else None,
            "owner": DEFECT_OWNER.get(name, "unassigned" if name != "OK" else "converted"),
        }
    return dict(sorted(out.items(), key=lambda kv: -int(kv[1]["seen"])))


def _breadth_delta(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    b = before.get("effective_breadth")
    a = after.get("effective_breadth")
    if not isinstance(b, (int, float)) or not isinstance(a, (int, float)):
        return {"status": UNMEASURED,
                "why": "one side of the comparison has no measured breadth"}
    return {"status": "MEASURED", "effective_breadth_before": round(float(b), 4),
            "effective_breadth_after": round(float(a), 4),
            "added_effective_cells": round(float(a) - float(b), 4),
            "nominal_cells_before": before.get("nominal_cells"),
            "nominal_cells_after": after.get("nominal_cells")}


def _charge_trials(repaired: Sequence[Mapping[str, Any]], conn: sqlite3.Connection, *,
                   dry_run: bool) -> dict[str, Any]:
    if not repaired:
        return {"n_raw": 0, "n_effective": 0.0,
                "basis": "libs.research.trial_ledger.effective_count_of_records "
                         "(participation ratio)"}
    try:
        from libs.research.trial_ledger import effective_count_of_records
        n_eff = float(effective_count_of_records(repaired))
    except Exception as exc:                                             # pragma: no cover
        return {"n_raw": len(repaired), "n_effective": None,
                "status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    out = {"n_raw": len(repaired), "n_effective": round(n_eff, 3),
           "inflation": round(len(repaired) / n_eff, 4) if n_eff > 0 else None,
           "basis": "libs.research.trial_ledger.effective_count_of_records "
                    "(participation ratio over the repaired batch)"}
    if not dry_run:
        with contextlib.suppress(Exception):
            R.metric("conversion_maximiser.effective_trials_charged", n_eff,
                     {"n_raw": len(repaired)}, conn=conn)
    return out


def largest_blocker(doc: Mapping[str, Any]) -> dict[str, Any]:
    """THE DAILY ATTACK: the single biggest blocker class and the organ that owns it.

    One line, every day, so the bottleneck has a name and an address instead of being a number
    in a histogram nobody ranks.
    """
    hist = doc.get("blocker_histogram") or {}
    ranked = [(k, v) for k, v in hist.items() if k != "OK"]
    if not ranked:
        return {"status": UNMEASURED,
                "why": "no row was classified this pass -- nothing to attack, and that is a "
                       "measurement of the pass, not of the debt"}
    ranked.sort(key=lambda kv: -int(kv[1]))
    name, n = ranked[0]
    total = sum(int(v) for _k, v in ranked) or 1
    return {"status": "MEASURED", "blocker": name, "rows": int(n),
            "share_of_blocked": round(int(n) / total, 4),
            "owner": DEFECT_OWNER.get(name, "unassigned"),
            "attack": _ATTACK.get(name, "classify the rows and name the missing field"),
            "line": f"LARGEST BLOCKER: {name} ({n} rows, "
                    f"{100 * int(n) / total:.1f}% of blocked) -- owner "
                    f"{DEFECT_OWNER.get(name, 'unassigned')}"}


_ATTACK: dict[str, str] = {
    "NO_FALSIFIER": "supply the standing re-judgement falsifier and re-enqueue; if the family or "
                    "the instrument is missing too, that is the real blocker",
    "NO_DATA": "supply the bars: resample the coarser charts from the finest series held, bind "
               "the cell to the finest chart the desk holds, and request the fetch for the rest",
    "NO_INSTRUMENT": "resolve through the MT5 universe registry in the hypothesis lane",
    "NO_FAMILY": "bind a registered family through axis_registry.FAMILY_TABLE, or park with the "
                 "mechanism no family implements -- never assign a family that tests another "
                 "claim",
    "PROSE_ONLY": "route to the understanding/naming seat; a mechanism with no name cannot be a "
                  "cell",
    "OFF_UNIVERSE": "retire: the universe mandate forbids this ground",
    "EVENT_LANE": "retire from the hypothesis lane: single names are traded on news",
    "UNREADABLE": "fix the generator that wrote the row",
}


# ----------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg)")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--max-rows", type=int, default=0,
                    help="0 derives the cap from measured free memory")
    ap.add_argument("--grace-days", type=float, default=GRACE_DAYS)
    ap.add_argument("--dry-run", action="store_true", help="classify and measure, write nothing")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--carry", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    budget = Budget(a.budget_s)
    max_rows = a.max_rows if a.max_rows > 0 else max_rows_per_pass()
    conn = R.connect()
    try:
        body = run(budget=budget, conn=conn, max_rows=max_rows, dry_run=a.dry_run,
                   carry_path=a.carry, grace_days=a.grace_days)
    finally:
        with contextlib.suppress(sqlite3.Error):
            conn.close()

    doc: dict[str, Any] = {
        "generated_utc": _now(), "organ": SEAT, "rule": RULE,
        "budget_s": budget.seconds, "spent_s": budget.spent(),
        "stopped_at": budget.stopped_at, "dry_run": bool(a.dry_run),
        "registry": str(R.path()),
        **body,
    }
    doc["largest_blocker"] = largest_blocker(doc)
    doc["conversion_rate"] = _conversion_rates(doc)
    if not a.dry_run:
        _atomic_write(a.out or OUT, doc)
        with contextlib.suppress(Exception):
            from libs.ops import events as EV
            EV.emit("CANDIDATES_COMPILED", leg=SEAT, organ=SEAT,
                    examined=doc["examined"],
                    repaired=doc["repaired"], refused=doc["refused"],
                    debt_before=(doc["debt_before"] or {}).get("total_debt"),
                    debt_after=(doc["debt_after"] or {}).get("total_debt"))
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    before = (doc["debt_before"] or {}).get("total_debt")
    after = (doc["debt_after"] or {}).get("total_debt")
    print(f"conversion maximiser: examined {doc['examined']}, repaired {doc['repaired']}, "
          f"refused {doc['refused']}, still blocked {doc['still_blocked']}; "
          f"debt {before} -> {after}; "
          f"breadth {doc['breadth_delta'].get('effective_breadth_before')} -> "
          f"{doc['breadth_delta'].get('effective_breadth_after')}")
    print(doc["largest_blocker"].get("line", doc["largest_blocker"].get("why", "")))
    oldest = doc.get("oldest_unconverted") or {}
    print(f"  oldest unconverted row: {oldest.get('age_days')} days "
          f"({oldest.get('id') or oldest.get('status')}); carried in {doc['carried_in']}, "
          f"out {doc['carried_out']} -- the leftover is the next pass's first work")
    return 0


def _conversion_rates(doc: Mapping[str, Any]) -> dict[str, Any]:
    """Conversion rate per stage and per source -- the measurement the mandate asks for."""
    examined = int(doc.get("examined") or 0)
    per_source = {
        name: {**stat,
               "conversion_rate": (round(stat["repaired"] / stat["examined"], 4)
                                   if stat.get("examined") else None)}
        for name, stat in (doc.get("per_source") or {}).items()}
    stages = {
        "classified": examined,
        "repaired": int(doc.get("repaired") or 0),
        "enqueued": int(doc.get("enqueued") or 0),
        "refused_with_reason": int(doc.get("refused") or 0),
        "still_blocked_with_owner": int(doc.get("still_blocked") or 0),
        "routed_to_study": int(doc.get("routed_to_study") or 0),
    }
    disposed = (stages["repaired"] + stages["refused_with_reason"]
                + stages["still_blocked_with_owner"] + stages["routed_to_study"])
    return {"per_stage": stages, "per_source": per_source,
            "disposition_rate": round(disposed / examined, 4) if examined else None,
            "conversion_rate": round(stages["repaired"] / examined, 4) if examined else None,
            "silent_drops": examined - disposed,
            "rule": "every examined row leaves with a disposition; silent_drops must be 0"}


if __name__ == "__main__":                                               # pragma: no cover
    raise SystemExit(main())
