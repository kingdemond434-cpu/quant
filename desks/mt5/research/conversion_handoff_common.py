"""conversion_handoff_common: constants, statuses, reasons and routes.

Split out of conversion_handoff_converter.py so each file of the organ is a size the
independent reviewer can read whole. conversion_handoff_converter re-exports every name here;
the organ's behaviour and docstring live there."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SEAT = "conversion_handoff_converter"
HYP = DESK / "data" / "hypotheses"
HANDOFF = HYP / "conversion_handoff.json"
LEDGER = HYP / "conversion_handoff_resolved.jsonl"
CURSOR = HYP / "conversion_handoff_cursor.json"
DOCKET = HYP / "external_survivors.json"
UNIVERSE = DESK / "data" / "universe"
REPORT = DESK / "reports" / "CONVERSION_HANDOFF.json"
DEFECTS = DESK / "reports" / "FAMILY_BUILD_DEFECTS.json"
GAPS = DESK / "reports" / "BUILD_INPUT_GAPS.json"

# ---- statuses ---------------------------------------------------------------------------------
CONVERTED = "CONVERTED"
DEFECT_REPORTED = "DEFECT_REPORTED"
DEFERRED_BUDGET = "DEFERRED_BUDGET"
NOT_CONVERTIBLE = "NOT_CONVERTIBLE"
UNMEASURED = "UNMEASURED"
#: Retryable: a build_input_missing row whose named input is still absent. Nothing is charged.
AWAITING_INPUT = "AWAITING_INPUT"
#: A handoff reason this organ has no route for. Counted and reported, never skipped silently.
UNHANDLED_REASON = "UNHANDLED_REASON"
TERMINAL = frozenset({CONVERTED, DEFECT_REPORTED, NOT_CONVERTIBLE})
#: Ledgered, not terminal: the row is asked again after RETRY_H.
RETRYABLE = frozenset({UNMEASURED, AWAITING_INPUT})

BUILD_FAILED = "build_failed"
SHORT_HISTORY = "short_history_after_cut"
LOCKBOX = "lockbox_consumed_history"
NEVER_FIRES = "never_fires"
TOO_RARE = "too_rare"
INPUT_MISSING = "build_input_missing"
#: Reasons that mint charged children, through the budget and the round-robin.
CONVERTING_REASONS = (SHORT_HISTORY, NEVER_FIRES, TOO_RARE, INPUT_MISSING)
HANDLED_REASONS = frozenset({BUILD_FAILED, LOCKBOX, *CONVERTING_REASONS})

ROUTE_TRANSPLANT = "cross_asset_transplant"
ROUTE_RELAXED = "relaxed_threshold"
ROUTE_COARSER = "coarser_timeframe"
ROUTE_POOL = "cross_sectional_pool"
ROUTE_RESTORED = "input_restored"
#: Children a parent of each reason may mint (the backlog projection uses the same numbers).
MAX_CHILDREN_NEVER_FIRES = 2
CHILDREN_PER_PARENT = {SHORT_HISTORY: 1, NEVER_FIRES: MAX_CHILDREN_NEVER_FIRES, TOO_RARE: 1,
                       INPUT_MISSING: 1}

# ---- the multiple-testing budget: DERIVED from the judge's measured capacity -------------------
#: The judge volume floor, cells a day: the judge's TARGET, not its capacity. A measured rate
#: below it is published as judge_gap_per_day -- a judge shortfall to fix -- and never fed.
JUDGE_VOLUME_FLOOR_PER_DAY = 150_000
#: Used ONLY when no capacity artifact can be read, and reported UNMEASURED: the organ's previous
#: fixed cap (200 a pass x 24 passes), the most conservative figure the desk ever ran.
FALLBACK_TRIALS_PER_DAY = 4_800
#: Hourly leg: the passes in a UTC day the day's budget is spread over.
PASSES_PER_DAY = 24
#: A capacity artifact older than this is not a measurement of today's judge.
CAPACITY_MAX_AGE_H = 72.0
REPORTS = DESK / "reports"
#: Rows examined per pass (params lookup + route search) = this many times the pass's trial
#: budget, inside [MAX_EXAMINED_PER_PASS, MAX_EXAMINED_CEILING] so memory stays bounded.
EXAMINE_FACTOR = 2
MAX_EXAMINED_PER_PASS = 800
MAX_EXAMINED_CEILING = 50_000
#: build_input_missing rows whose inputs are re-checked per pass (a stat per distinct input).
MAX_INPUT_CHECKS_PER_PASS = 20_000
#: A retryable row (params not found, input still absent) is asked again after this long.
RETRY_H = 24.0
UNMEASURED_RETRY_H = RETRY_H

# ---- what "enough history" means for a peer ---------------------------------------------
#: The peer's bars on the cell's chart must span at least this many calendar days ...
MIN_PEER_HISTORY_DAYS = 730
#: ... and start at least this many days before the parent's own first bar.
MIN_PEER_LEAD_DAYS = 180

#: Share of the pass budget the work may use; the rest is the write margin.
BUDGET_SHARE = 0.85
DEFAULT_BUDGET_S = 420.0
#: Samples kept per (family, message) in the defect report.
DEFECT_SAMPLES = 5
DEFECT_FAMILIES_LISTED = 200
DEFECT_MESSAGES_PER_FAMILY = 10
GAPS_LISTED = 200

LOCKBOX_RULE = (
    "NOT_CONVERTIBLE: every route axis on the same instrument (coarser_timeframe, regime_child, "
    "proxy_series) reads the same calendar span, so its development window would sit inside the "
    "consumed lockbox. Holdout boundaries are an immutable rail (LAWS §4b 'sealed holdouts', "
    "§5c 'holdout boundaries'; RESEARCH §6a gate 9 'untouched 20% holdout') and a consumed "
    "lockbox is never reused. The judge's bank re-admits the cell as its history grows past the "
    "cut (judge_coverage.readmit_due), which is the only legal road back.")


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(t: datetime | None = None) -> str:
    return (t or _now()).isoformat()


# =============================================================================================
# STREAMING READS -- the handoff is a 718k-row JSON object written with indent=1; never load it.
# =============================================================================================
