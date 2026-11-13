#!/usr/bin/env python3
"""THE CONVERSION-HANDOFF CONVERTER -- the organ the judge's parked cells were handed to.

WHAT WAS MISSING (box read JG3, 2026-11-11). `judge_coverage.write_conversion_handoff` writes
every parked cell the converter owns to `data/hypotheses/conversion_handoff.json` with its class
and route axes (coarser_timeframe, regime_child, cross_asset_transplant, event_study,
proxy_series, family_defect_report). Measured on the trading box: 718,558 rows, none resolved,
no status field, and NOTHING in the repository read the axes. A queue with no consumer is a
parking lot (III.16: unwired is a defect).

WHAT THIS ORGAN DOES, PER HANDOFF REASON, AND WHY IT STOPS WHERE IT STOPS.

  build_failed              A FAMILY DEFECT, NOT A HYPOTHESIS. The cell's signal construction
                            raised; minting variants of it would spend trials on code that does
                            not run. Every row is aggregated by (family, failure message) into
                            `reports/FAMILY_BUILD_DEFECTS.json`, ranked by count with sample
                            cells and the family's source file as its owner, and resolves
                            DEFECT_REPORTED. No trial is minted or charged.
  short_history_after_cut   ROUTED TO `cross_asset_transplant`. The cell traded, but its chart's
                            whole history sits after the lockbox cut. The SAME family and params
                            are minted on a same-class peer (universe_policy.peer_class, from the
                            broker registry) whose history on the same chart starts well before.
                            Each transplant is a NEW TRIAL charged to its trial_family and enters
                            the judge's normal intake; the parent cell id rides on it as lineage.
  lockbox_consumed_history  NOT_CONVERTIBLE. The cell's history exists but the campaign lockbox
                            consumed its development window. Every axis the route offers on the
                            same instrument (coarser chart, regime child, proxy series) reads the
                            SAME calendar span, so it would develop on the consumed holdout --
                            and holdout boundaries are an immutable rail (LAWS §4b "sealed
                            holdouts", §5c "holdout boundaries"; RESEARCH §6a gate 9 "untouched
                            20% holdout"). The judge's own bank re-admits the cell as its history
                            grows past the cut; that is the only legal road back.
  never_fires               ROUTED TO `relaxed_threshold`. The spec produced not one signal on
                            bars that are present. Up to MAX_CHILDREN_NEVER_FIRES children: the
                            same family, instrument and chart with ONE entry param relaxed along
                            the family's OWN grid toward firing (mt5desk.families.FAMILY_REGISTRY
                            / families_cross_sectional.PARAM_GRID, read-only): the next grid step
                            and the loosest grid value. Exit-side params (rr, ttl, hold, stop) are
                            never touched. A family whose grid exposes no relaxable entry param is
                            NOT_CONVERTIBLE with that reason, counted.
  too_rare                  ROUTED TO `cross_sectional_pool` for a family in
                            universe_policy.CROSS_SECTIONAL_FAMILIES (the same class book on the
                            longest-history same-class peer), otherwise -- and as that route's
                            fallback -- to `coarser_timeframe`: the same rule one rung up the
                            chart ladder (M1..D1; params carry the chart, as the judge's
                            `timeframe_of` reads it). One child per parent, one trial.
  build_input_missing       A DATA GAP, NOT A HYPOTHESIS, UNTIL THE INPUT EXISTS. Every row is
                            aggregated by the input it lacks into `reports/BUILD_INPUT_GAPS.json`,
                            ranked by cells blocked. A row whose inputs are still absent is
                            AWAITING_INPUT (retryable, re-examined after RETRY_H) and charges
                            nothing; once every named input exists the SAME rule is minted
                            (`input_restored`) -- one trial if the registry does not already
                            hold it, none if its minter already paid for it.
  anything else             UNHANDLED_REASON: counted per reason and reported, never skipped.

EVERY ROW HAS AN OUTCOME. A pass ends each handoff row CONVERTED, DEFECT_REPORTED,
NOT_CONVERTIBLE (with its specific reason), retryable (UNMEASURED params / AWAITING_INPUT, each
with its next step), DEFERRED_BUDGET (queue position kept by the per-family cursor) or
UNHANDLED_REASON. Nothing is held.

THE MULTIPLE-TESTING BUDGET (`trial_budget`) is derived from the judge's MEASURED capacity, never a
constant: cells the last sweep judged (JUDGING_THROUGHPUT.json `queue.judged_last_sweep`, else
GAUNTLET_BACKPRESSURE.json `capacity.measured.n_judged`) over that sweep's wall time
(JUDGE_RESIDENT.json `last_sweep_s`), scaled to a day, less the cells every other producer mints a
day (JUDGING_RATE.json `created_per_day`). The judge volume floor (JUDGE_VOLUME_FLOOR_PER_DAY) is
the judge's TARGET, not its capacity: a child is charged at donation, so feeding above what the
judge can test would raise every lane's deflated-Sharpe bar with cells nobody tests. A measured
capacity below the floor is published as `judge_gap_per_day` (a judge problem), never fed. That
spare capacity is the day's conversion budget; the pass takes what is left of it divided by the
passes left in the UTC day, so a missed hour is caught up. With no capacity artifact the budget is
FALLBACK_TRIALS_PER_DAY and the report says UNMEASURED. Work is ordered ROUND-ROBIN across
trial_family (the family charged least today first), so the family with 500k parked cells cannot
starve the one with fifty.

TRIAL CHARGING. Every new child (transplant, relaxed, coarser, pooled or restored) is donated
through `proposer_common.donate` -- one contract file per trial_family with `tests_run` = the new
children of that family, whatever their route -- which is the mechanism
`libs.research.experiment_ledger._proposer_counts` reads into the lifetime and per-family trial
census, and which also writes the registry candidate the judge's lease drinks from. One family
per file, so the charge lands on the right family exactly (the ledger splits a mixed file evenly).
No `search_trials` or effective-N is attached to any row (L1.60).

IDEMPOTENT BY CONSTRUCTION. `conversion_handoff_resolved.jsonl` is append-only and keyed by
(cell, reason, first_parked_utc): a row resolves once; a cell the judge re-parks later carries a
new parked stamp and is a new handoff row. A transplant child that this organ has already charged
is never charged again, nor is a child the registry already holds -- a parent that lands only on
such children resolves CONVERTED with
`trials_charged: 0` and its lineage recorded. The donation is written BEFORE the resolution row,
so a crash between the two can only over-count a trial, never under-count one.

    python desks/mt5/research/conversion_handoff_converter.py --once --budget-s 420
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


from research.conversion_handoff_children import (  # noqa: E402
    _PINNED as _PINNED,
)
from research.conversion_handoff_children import (  # noqa: E402
    _SLIM as _SLIM,
)
from research.conversion_handoff_children import (  # noqa: E402
    CHART_LADDER as CHART_LADDER,
)
from research.conversion_handoff_children import (  # noqa: E402
    EXIT_PARAM as EXIT_PARAM,
)
from research.conversion_handoff_children import (  # noqa: E402
    HIGHER_FIRES as HIGHER_FIRES,
)
from research.conversion_handoff_children import (  # noqa: E402
    LOOSE_CATEGORIES as LOOSE_CATEGORIES,
)
from research.conversion_handoff_children import (  # noqa: E402
    LOWER_FIRES as LOWER_FIRES,
)
from research.conversion_handoff_children import (  # noqa: E402
    GapAggregate as GapAggregate,
)
from research.conversion_handoff_children import (  # noqa: E402
    InputPresence as InputPresence,
)
from research.conversion_handoff_children import (  # noqa: E402
    ParamSpace as ParamSpace,
)
from research.conversion_handoff_children import (  # noqa: E402
    _budget_s as _budget_s,
)
from research.conversion_handoff_children import (  # noqa: E402
    _looser as _looser,
)
from research.conversion_handoff_children import (  # noqa: E402
    coarser_chart as coarser_chart,
)
from research.conversion_handoff_children import (  # noqa: E402
    family_param_space as family_param_space,
)
from research.conversion_handoff_children import (  # noqa: E402
    input_labels as input_labels,
)
from research.conversion_handoff_children import (  # noqa: E402
    lane_refusal as lane_refusal,
)
from research.conversion_handoff_children import (  # noqa: E402
    pinned_timeframes as pinned_timeframes,
)
from research.conversion_handoff_children import (  # noqa: E402
    plan_children as plan_children,
)
from research.conversion_handoff_children import (  # noqa: E402
    relaxed_children as relaxed_children,
)
from research.conversion_handoff_children import (  # noqa: E402
    round_robin as round_robin,
)
from research.conversion_handoff_common import (  # noqa: E402
    AWAITING_INPUT as AWAITING_INPUT,
)
from research.conversion_handoff_common import (  # noqa: E402
    BUDGET_SHARE as BUDGET_SHARE,
)
from research.conversion_handoff_common import (  # noqa: E402
    BUILD_FAILED as BUILD_FAILED,
)
from research.conversion_handoff_common import (  # noqa: E402
    CAPACITY_MAX_AGE_H as CAPACITY_MAX_AGE_H,
)
from research.conversion_handoff_common import (  # noqa: E402
    CHILDREN_PER_PARENT as CHILDREN_PER_PARENT,
)
from research.conversion_handoff_common import (  # noqa: E402
    CONVERTED as CONVERTED,
)
from research.conversion_handoff_common import (  # noqa: E402
    CONVERTING_REASONS as CONVERTING_REASONS,
)
from research.conversion_handoff_common import (  # noqa: E402
    CURSOR as CURSOR,
)
from research.conversion_handoff_common import (  # noqa: E402
    DEFAULT_BUDGET_S as DEFAULT_BUDGET_S,
)
from research.conversion_handoff_common import (  # noqa: E402
    DEFECT_FAMILIES_LISTED as DEFECT_FAMILIES_LISTED,
)
from research.conversion_handoff_common import (  # noqa: E402
    DEFECT_MESSAGES_PER_FAMILY as DEFECT_MESSAGES_PER_FAMILY,
)
from research.conversion_handoff_common import (  # noqa: E402
    DEFECT_REPORTED as DEFECT_REPORTED,
)
from research.conversion_handoff_common import (  # noqa: E402
    DEFECT_SAMPLES as DEFECT_SAMPLES,
)
from research.conversion_handoff_common import (  # noqa: E402
    DEFECTS as DEFECTS,
)
from research.conversion_handoff_common import (  # noqa: E402
    DEFERRED_BUDGET as DEFERRED_BUDGET,
)
from research.conversion_handoff_common import (  # noqa: E402
    DESK as DESK,
)
from research.conversion_handoff_common import (  # noqa: E402
    DOCKET as DOCKET,
)
from research.conversion_handoff_common import (  # noqa: E402
    EXAMINE_FACTOR as EXAMINE_FACTOR,
)
from research.conversion_handoff_common import (  # noqa: E402
    FALLBACK_TRIALS_PER_DAY as FALLBACK_TRIALS_PER_DAY,
)
from research.conversion_handoff_common import (  # noqa: E402
    GAPS as GAPS,
)
from research.conversion_handoff_common import (  # noqa: E402
    GAPS_LISTED as GAPS_LISTED,
)
from research.conversion_handoff_common import (  # noqa: E402
    HANDLED_REASONS as HANDLED_REASONS,
)
from research.conversion_handoff_common import (  # noqa: E402
    HANDOFF as HANDOFF,
)
from research.conversion_handoff_common import (  # noqa: E402
    HYP as HYP,
)
from research.conversion_handoff_common import (  # noqa: E402
    INPUT_MISSING as INPUT_MISSING,
)
from research.conversion_handoff_common import (  # noqa: E402
    JUDGE_VOLUME_FLOOR_PER_DAY as JUDGE_VOLUME_FLOOR_PER_DAY,
)
from research.conversion_handoff_common import (  # noqa: E402
    LEDGER as LEDGER,
)
from research.conversion_handoff_common import (  # noqa: E402
    LOCKBOX as LOCKBOX,
)
from research.conversion_handoff_common import (  # noqa: E402
    LOCKBOX_RULE as LOCKBOX_RULE,
)
from research.conversion_handoff_common import (  # noqa: E402
    MAX_CHILDREN_NEVER_FIRES as MAX_CHILDREN_NEVER_FIRES,
)
from research.conversion_handoff_common import (  # noqa: E402
    MAX_EXAMINED_CEILING as MAX_EXAMINED_CEILING,
)
from research.conversion_handoff_common import (  # noqa: E402
    MAX_EXAMINED_PER_PASS as MAX_EXAMINED_PER_PASS,
)
from research.conversion_handoff_common import (  # noqa: E402
    MAX_INPUT_CHECKS_PER_PASS as MAX_INPUT_CHECKS_PER_PASS,
)
from research.conversion_handoff_common import (  # noqa: E402
    MIN_PEER_HISTORY_DAYS as MIN_PEER_HISTORY_DAYS,
)
from research.conversion_handoff_common import (  # noqa: E402
    MIN_PEER_LEAD_DAYS as MIN_PEER_LEAD_DAYS,
)
from research.conversion_handoff_common import (  # noqa: E402
    NEVER_FIRES as NEVER_FIRES,
)
from research.conversion_handoff_common import (  # noqa: E402
    NOT_CONVERTIBLE as NOT_CONVERTIBLE,
)
from research.conversion_handoff_common import (  # noqa: E402
    PASSES_PER_DAY as PASSES_PER_DAY,
)
from research.conversion_handoff_common import (  # noqa: E402
    REPORT as REPORT,
)
from research.conversion_handoff_common import (  # noqa: E402
    REPORTS as REPORTS,
)
from research.conversion_handoff_common import (  # noqa: E402
    RETRY_H as RETRY_H,
)
from research.conversion_handoff_common import (  # noqa: E402
    RETRYABLE as RETRYABLE,
)
from research.conversion_handoff_common import (  # noqa: E402
    ROOT as ROOT,
)
from research.conversion_handoff_common import (  # noqa: E402
    ROUTE_COARSER as ROUTE_COARSER,
)
from research.conversion_handoff_common import (  # noqa: E402
    ROUTE_POOL as ROUTE_POOL,
)
from research.conversion_handoff_common import (  # noqa: E402
    ROUTE_RELAXED as ROUTE_RELAXED,
)
from research.conversion_handoff_common import (  # noqa: E402
    ROUTE_RESTORED as ROUTE_RESTORED,
)
from research.conversion_handoff_common import (  # noqa: E402
    ROUTE_TRANSPLANT as ROUTE_TRANSPLANT,
)
from research.conversion_handoff_common import (  # noqa: E402
    SEAT as SEAT,
)
from research.conversion_handoff_common import (  # noqa: E402
    SHORT_HISTORY as SHORT_HISTORY,
)
from research.conversion_handoff_common import (  # noqa: E402
    TERMINAL as TERMINAL,
)
from research.conversion_handoff_common import (  # noqa: E402
    TOO_RARE as TOO_RARE,
)
from research.conversion_handoff_common import (  # noqa: E402
    UNHANDLED_REASON as UNHANDLED_REASON,
)
from research.conversion_handoff_common import (  # noqa: E402
    UNIVERSE as UNIVERSE,
)
from research.conversion_handoff_common import (  # noqa: E402
    UNMEASURED as UNMEASURED,
)
from research.conversion_handoff_common import (  # noqa: E402
    UNMEASURED_RETRY_H as UNMEASURED_RETRY_H,
)
from research.conversion_handoff_common import (  # noqa: E402
    _iso as _iso,
)
from research.conversion_handoff_common import (  # noqa: E402
    _now as _now,
)
from research.conversion_handoff_io import (  # noqa: E402
    _DECODER as _DECODER,
)
from research.conversion_handoff_io import (  # noqa: E402
    _HEX as _HEX,
)
from research.conversion_handoff_io import (  # noqa: E402
    _NUM as _NUM,
)
from research.conversion_handoff_io import (  # noqa: E402
    _SPACE as _SPACE,
)
from research.conversion_handoff_io import (  # noqa: E402
    _WS as _WS,
)
from research.conversion_handoff_io import (  # noqa: E402
    DefectAggregate as DefectAggregate,
)
from research.conversion_handoff_io import (  # noqa: E402
    _atomic_write as _atomic_write,
)
from research.conversion_handoff_io import (  # noqa: E402
    _iter_array as _iter_array,
)
from research.conversion_handoff_io import (  # noqa: E402
    _read_json as _read_json,
)
from research.conversion_handoff_io import (  # noqa: E402
    append_ledger as append_ledger,
)
from research.conversion_handoff_io import (  # noqa: E402
    failure_signature as failure_signature,
)
from research.conversion_handoff_io import (  # noqa: E402
    family_owners as family_owners,
)
from research.conversion_handoff_io import (  # noqa: E402
    handoff_header as handoff_header,
)
from research.conversion_handoff_io import (  # noqa: E402
    iter_handoff as iter_handoff,
)
from research.conversion_handoff_io import (  # noqa: E402
    iter_json_list as iter_json_list,
)
from research.conversion_handoff_io import (  # noqa: E402
    load_ledger as load_ledger,
)
from research.conversion_handoff_io import (  # noqa: E402
    parent_key as parent_key,
)
from research.conversion_handoff_io import (  # noqa: E402
    row_key as row_key,
)
from research.conversion_handoff_routes import (  # noqa: E402
    _HIST_MEMO as _HIST_MEMO,
)
from research.conversion_handoff_routes import (  # noqa: E402
    Donor as Donor,
)
from research.conversion_handoff_routes import (  # noqa: E402
    ExistsCheck as ExistsCheck,
)
from research.conversion_handoff_routes import (  # noqa: E402
    ParamsLookup as ParamsLookup,
)
from research.conversion_handoff_routes import (  # noqa: E402
    _age_h as _age_h,
)
from research.conversion_handoff_routes import (  # noqa: E402
    _cell_id as _cell_id,
)
from research.conversion_handoff_routes import (  # noqa: E402
    _num as _num,
)
from research.conversion_handoff_routes import (  # noqa: E402
    _policy as _policy,
)
from research.conversion_handoff_routes import (  # noqa: E402
    child_candidate as child_candidate,
)
from research.conversion_handoff_routes import (  # noqa: E402
    docket_params as docket_params,
)
from research.conversion_handoff_routes import (  # noqa: E402
    donate_family as donate_family,
)
from research.conversion_handoff_routes import (  # noqa: E402
    history_start as history_start,
)
from research.conversion_handoff_routes import (  # noqa: E402
    judge_capacity as judge_capacity,
)
from research.conversion_handoff_routes import (  # noqa: E402
    judge_inflow as judge_inflow,
)
from research.conversion_handoff_routes import (  # noqa: E402
    lane_allows as lane_allows,
)
from research.conversion_handoff_routes import (  # noqa: E402
    ranked_peers as ranked_peers,
)
from research.conversion_handoff_routes import (  # noqa: E402
    registry_has as registry_has,
)
from research.conversion_handoff_routes import (  # noqa: E402
    registry_params as registry_params,
)
from research.conversion_handoff_routes import (  # noqa: E402
    transplant_candidate as transplant_candidate,
)
from research.conversion_handoff_routes import (  # noqa: E402
    trial_budget as trial_budget,
)
from research.conversion_handoff_steer import (  # noqa: E402
    UNSTEERED,
    asset_class,
    exotic_quota,
    is_exotic,
    load_steer,
    steer_group,
    unsteered_share,
)


def _exotic_split(recs: Sequence[Mapping[str, Any]], work: Sequence[Mapping[str, Any]],
                  examined_rows: Sequence[Mapping[str, Any]],
                  exotic: Callable[[Mapping[str, Any]], bool], quota: float,
                  selected: int, held: int) -> dict[str, Any]:
    """The realised non-exotic vs exotic split of this pass: rows examined, parents converted
    and child cells minted, with the quota and what it held back."""
    parent = {str(r.get("key")): r for r in work}

    def split(pairs: Sequence[tuple[Mapping[str, Any], int]]) -> dict[str, Any]:
        ex = sum(n for r, n in pairs if exotic(r))
        tot = sum(n for _, n in pairs)
        return {"non_exotic": tot - ex, "exotic": ex,
                "exotic_share": round(ex / tot, 4) if tot else None}

    conv = [(parent.get(str(r.get("key"))) or r, int(r.get("trials_charged") or 0))
            for r in recs if r.get("status") == CONVERTED]
    return {"quota_max_exotic_share": quota,
            "selected_exotic_rows": selected, "exotic_rows_held_by_quota": held,
            "examined": split([(r, 1) for r in examined_rows]),
            "converted_parents": split([(r, 1) for r, _ in conv]),
            "child_cells": split(conv),
            "rule": ("zuck 2026-11-13 19:46Z: at most 10% of mining and conversion compute on "
                     "exotic-currency markets; a hard quota on each pass's examined rows "
                     "(desks/mt5/data/breadth_steer.json exotic_share_max)")}


def _interleave(first: list[dict[str, Any]], second: list[dict[str, Any]],
                share: float) -> list[dict[str, Any]]:
    """Both lists whole, `second` spread through `first` so that it never holds more than
    `share` of any prefix while `first` still has rows (the floor or quota holds under every
    per-pass cap, not only over the whole list)."""
    out: list[dict[str, Any]] = []
    i = j = 0
    while i < len(first) or j < len(second):
        if j < len(second) and (i >= len(first) or j + 1 <= share * (len(out) + 1)):
            out.append(second[j])
            j += 1
        else:
            out.append(first[i])
            i += 1
    return out


def _breadth_counts(recs: Sequence[Mapping[str, Any]], work: Sequence[Mapping[str, Any]],
                    steer: list[dict[str, Any]], selected: Counter[str],
                    group_of: Callable[[Mapping[str, Any]], str],
                    class_of: Callable[[str], str], share: float = 1.0) -> dict[str, Any]:
    """This pass's conversions per asset class and per steer group (parents and child cells),
    so every cycle reports where the converted breadth went."""
    parent = {str(r.get("key")): r for r in work}
    by_class: dict[str, Counter[str]] = defaultdict(Counter)
    by_group: dict[str, Counter[str]] = defaultdict(Counter)
    for rec in recs:
        if rec.get("status") != CONVERTED:
            continue
        row = parent.get(str(rec.get("key"))) or rec
        sym = str(row.get("symbol") or rec.get("child_symbol") or "")
        cls = class_of(sym) if sym else "UNCLASSIFIED"
        grp = group_of(row) or "unsteered"
        for tgt in (by_class[cls], by_group[grp]):
            tgt["parents"] += 1
            tgt["child_cells"] += int(rec.get("trials_charged") or 0)
    return {"steer": [str(g["name"]) for g in steer],
            "unsteered_share": share,
            "selected_by_group": {(k or "unsteered"): v for k, v in sorted(selected.items())},
            "converted_by_asset_class": {k: dict(v) for k, v in sorted(by_class.items())},
            "converted_by_steer_group": {k: dict(v) for k, v in sorted(by_group.items())},
            "rule": ("steered groups are examined first in the steer's order; a steer reorders "
                     "the work list and never removes a row (desks/mt5/data/breadth_steer.json)")}


def run_pass(*, handoff: Path | None = None, ledger: Path | None = None,
             cursor_path: Path | None = None, report: Path | None = None,
             defects: Path | None = None, gaps: Path | None = None,
             budget_s: float = DEFAULT_BUDGET_S,
             params_lookup: ParamsLookup | None = None, exists: ExistsCheck | None = None,
             donor: Donor | None = None, universe: Path | None = None,
             max_per_pass: int | None = None, max_per_family_day: int | None = None,
             env: Mapping[str, str] | None = None,
             capacity_dir: Path | None = None, param_space: ParamSpace | None = None,
             input_present: Callable[[str], bool | None] | None = None,
             now: datetime | None = None,
             steer: list[dict[str, Any]] | None = None,
             steer_share: float | None = None,
             exotic_share: float | None = None,
             class_of: Callable[[str], str] | None = None,
             clock: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    handoff = handoff or HANDOFF
    steer = load_steer() if steer is None else steer
    class_of = class_of or asset_class
    ledger = ledger or LEDGER
    cursor_path = cursor_path or CURSOR
    report = report or REPORT
    defects = defects or DEFECTS
    gaps = gaps or GAPS
    lookup = params_lookup or registry_params
    exists_fn = exists or registry_has
    donate = donor or donate_family
    space = param_space or family_param_space
    t0 = clock()
    limit = _budget_s(budget_s, env)

    def time_ok() -> bool:
        return clock() - t0 < limit

    t_now = now or _now()
    at = _iso(t_now)
    head = handoff_header(handoff)
    led = load_ledger(ledger, t_now.date().isoformat())
    resolved: dict[str, str] = led["resolved"]
    cur = _read_json(cursor_path)
    cur = cur if isinstance(cur, dict) else {}
    legacy_cursor = str(cur.get("cursor_cell") or "")
    family_cursors: dict[str, str] = {str(k): str(v) for k, v in
                                      dict(cur.get("family_cursors") or {}).items()}

    # THE BUDGET, from the judge's measured spare capacity (or UNMEASURED and the fallback).
    family_day: Counter[str] = Counter(led["family_day"])
    budget = trial_budget(capacity_dir, charged_today=int(sum(family_day.values())), now=t_now)
    cap_pass = int(budget["per_pass"]) if max_per_pass is None else int(max_per_pass)
    cap_fam = None if max_per_family_day is None else int(max_per_family_day)
    examine_cap = min(MAX_EXAMINED_CEILING, max(MAX_EXAMINED_PER_PASS, EXAMINE_FACTOR * cap_pass))

    counts: dict[str, Counter[str]] = defaultdict(Counter)
    agg = DefectAggregate()
    gap = GapAggregate()
    new_defects: list[dict[str, Any]] = []
    lockbox_recs: list[dict[str, Any]] = []
    queues: dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]]]] = defaultdict(
        lambda: ([], []))
    input_due: list[dict[str, Any]] = []
    due: Counter[str] = Counter()
    unhandled: Counter[str] = Counter()
    rows_read = 0
    stream_complete = True
    retry_cut = t_now.timestamp() - RETRY_H * 3600.0

    for row in iter_handoff(handoff):
        if rows_read % 1000 == 0 and not time_ok():
            stream_complete = False
            break
        rows_read += 1
        reason = str(row.get("reason") or "unnamed")
        key = row_key(row)
        if reason == BUILD_FAILED:
            agg.add(row)
        done = resolved.get(key)
        if done:
            counts[reason][done] += 1
            continue
        if reason == BUILD_FAILED:
            new_defects.append({"key": key, "cell": row.get("cell"), "reason": reason,
                                "status": DEFECT_REPORTED, "at": at,
                                "family": row.get("family"),
                                "trial_family": row.get("trial_family"),
                                "signature": failure_signature(row.get("why"),
                                                               row.get("symbol")),
                                "trials_charged": 0, "report": str(defects)})
            counts[reason][DEFECT_REPORTED] += 1
        elif reason == LOCKBOX:
            lockbox_recs.append({"key": key, "cell": row.get("cell"), "reason": reason,
                                 "status": NOT_CONVERTIBLE, "at": at,
                                 "family": row.get("family"),
                                 "trial_family": row.get("trial_family"),
                                 "why": LOCKBOX_RULE, "trials_charged": 0})
            counts[reason][NOT_CONVERTIBLE] += 1
        elif reason in CONVERTING_REASONS:
            if reason == INPUT_MISSING:
                gap.add(row)
            waiting = led["retry_at"].get(key)
            if waiting:
                st, last = waiting
                try:
                    if datetime.fromisoformat(last).timestamp() > retry_cut:
                        counts[reason][st] += 1
                        continue
                except ValueError:
                    pass
            due[reason] += 1
            slim = {k: row.get(k) for k in _SLIM}
            slim["key"] = key
            if reason == INPUT_MISSING:
                slim["inputs"] = input_labels(row)
                if len(input_due) < MAX_INPUT_CHECKS_PER_PASS:
                    input_due.append(slim)
                continue
            tfam = str(row.get("trial_family") or row.get("family") or "")
            after, before = queues[tfam]
            target = (after if str(row.get("cell") or "") > family_cursors.get(tfam,
                                                                               legacy_cursor)
                      else before)
            if len(target) < examine_cap:
                target.append(slim)
        else:
            counts[reason][UNHANDLED_REASON] += 1
            unhandled[reason] += 1

    # 1. THE DEFECT REPORT FIRST, then the rows it reports are marked -- never the other way.
    fams = [f for f, _ in sorted(agg.by_family.items(),
                                 key=lambda kv: -sum(kv[1].values()))][:DEFECT_FAMILIES_LISTED]
    defect_doc = agg.report(family_owners(fams), at=at, handoff=head,
                            partial=not stream_complete)
    _atomic_write(defects, defect_doc)
    append_ledger(ledger, new_defects)
    append_ledger(ledger, lockbox_recs)

    # 2. build_input_missing: the gap report, then each due row's inputs are checked.
    presence = input_present or InputPresence(universe)
    restored: list[dict[str, Any]] = []
    input_recs: list[dict[str, Any]] = []
    for row_in in input_due:
        if not time_ok():
            break
        labels = list(row_in.get("inputs") or [])
        states = [presence(lab) for lab in labels]
        if labels and all(st is True for st in states):
            restored.append(row_in)
            continue
        absent = [lab for lab, st in zip(labels, states, strict=True) if st is False]
        unknown = [lab for lab, st in zip(labels, states, strict=True) if st is None]
        why = ("the row names no input, so its arrival cannot be checked" if not labels else
               f"absent: {absent[:5]}" + (f"; presence UNMEASURED: {unknown[:5]}" if unknown
                                          else ""))
        input_recs.append({"key": row_in["key"], "cell": row_in.get("cell"),
                           "reason": INPUT_MISSING, "family": row_in.get("family"),
                           "trial_family": row_in.get("trial_family"),
                           "at": at, "status": AWAITING_INPUT, "trials_charged": 0,
                           "missing": labels, "why": why,
                           "next_step": (f"re-examined after {RETRY_H:.0f}h; minted as the same "
                                         "rule (input_restored) once every named input exists; "
                                         "the inputs are ranked in BUILD_INPUT_GAPS.json")})
        counts[INPUT_MISSING][AWAITING_INPUT] += 1
    append_ledger(ledger, input_recs)
    _atomic_write(gaps, gap.report(presence, at=at, handoff=head, partial=not stream_complete))

    # 3. THE WORK LIST: restored inputs first, then round-robin across trial_family, the family
    # charged least today first.
    # THE BREADTH STEER (2026-11-13): steered groups first, in the steer's order, each served
    # round-robin across families; every other row keeps its place behind them. Nothing dropped.
    fam_order = sorted(queues, key=lambda f: (family_day[f], f))
    names = [str(g["name"]) for g in steer]
    group_memo: dict[str, str] = {}

    def group_of(row: Mapping[str, Any]) -> str:
        if not names:
            return UNSTEERED
        k = str(row.get("key") or "")
        if k not in group_memo:
            group_memo[k] = steer_group(row, steer, class_of)
        return group_memo[k]

    lanes: dict[str, dict[str, list[dict[str, Any]]]] = {n: {} for n in [*names, UNSTEERED]}
    for f, (a, b) in queues.items():
        for row_q in a + b:
            lanes[group_of(row_q)].setdefault(f, []).append(row_q)
    # EVERY STEER LANE ROTATES (Auditor MF1): a steered row moves no family cursor, so each
    # (group, family) lane keeps its own -- the last steered cell examined -- and the next pass
    # starts after it. A steered row left unresolved is re-examined only after the rest of its
    # lane has had a turn, never pinned at the head of the queue.
    steer_cursors: dict[str, str] = {str(k): str(v) for k, v in
                                     dict(cur.get("steer_cursors") or {}).items()}
    steer_cursors_in = dict(steer_cursors)
    for n in names:
        for f, rows_l in lanes[n].items():
            rows_l.sort(key=lambda r: str(r.get("cell") or ""))
            mark = steer_cursors.get(f"{n}|{f}", "")
            cut = next((i for i, r in enumerate(rows_l) if str(r.get("cell") or "") > mark), 0)
            rows_l[:] = rows_l[cut:] + rows_l[:cut]
    # THE UNSTEERED FLOOR (Auditor MF2): a fixed share of the examined rows is unsteered, and the
    # two are interleaved, so the steer reorders the queue without starving the rest of it --
    # in examination and in the per-pass conversion cap alike.
    share = (unsteered_share() if steer_share is None else steer_share) if names else 1.0
    # THE EXOTIC QUOTA (zuck's standing rule, 2026-11-13 19:46Z): at most `exotic_share` (10%)
    # of every pass's examined rows are exotic-currency cells; the rest of the capacity goes to
    # majors, minor crosses, metals, indices and the other liquid markets. A HARD quota on the
    # pass's capacity, not a priority: an exotic row over it is not examined this pass (it keeps
    # its queue place and is counted DEFERRED_BUDGET), whatever its steer group.
    q = exotic_quota() if exotic_share is None else min(1.0, max(0.0, exotic_share))
    exotic_memo: dict[str, bool] = {}

    def exotic(row: Mapping[str, Any]) -> bool:
        k = str(row.get("key") or "")
        if k not in exotic_memo:
            exotic_memo[k] = is_exotic(str(row.get("symbol") or ""), class_of)
        return exotic_memo[k]

    steered_all: list[dict[str, Any]] = []
    for n in names:
        if len(steered_all) >= examine_cap:
            break
        steered_all += round_robin(lanes[n], examine_cap - len(steered_all), fam_order)
    rest_all = round_robin(lanes[UNSTEERED], examine_cap, fam_order)
    ex_cap = math.floor(q * examine_cap)
    ex_rows = [r for r in steered_all + rest_all if exotic(r)][:ex_cap]
    major_cap = examine_cap - len(ex_rows)
    steered = [r for r in steered_all if not exotic(r)]
    rest = [r for r in rest_all if not exotic(r)]
    floor_n = min(len(rest), math.ceil(share * major_cap))
    steered = steered[:major_cap - floor_n]
    rest = rest[:major_cap - len(steered)]
    majors = _interleave(steered, rest, share)
    exotic_selected = len(ex_rows)
    exotic_held = sum(1 for r in steered_all + rest_all if exotic(r)) - exotic_selected
    mixed = _interleave(majors, ex_rows,
                        q if majors else 1.0)
    work = list(restored) + mixed
    steer_selected = Counter(group_of(r) for r in mixed)
    charged_children: dict[str, str] = dict(led["charged_children"])
    converted_parents: dict[str, list[str]] = dict(led["converted_parents"])
    params_by_cell = lookup(work, time_ok) if work and time_ok() else {}
    by_family: dict[str, list[tuple[dict[str, Any], list[dict[str, Any]]]]] = defaultdict(list)
    recs: list[dict[str, Any]] = []
    new_this_pass = 0
    examined = 0
    examined_by_reason: Counter[str] = Counter()
    # A FAMILY'S CURSOR NEVER PASSES ITS FIRST DEFERRED ROW: it stops at the last row settled
    # before it, so that row is the first one the next pass examines in that family.
    fam_last: dict[str, str] = {}
    fam_deferred: set[str] = set()
    deferred_by_family: Counter[str] = Counter()
    not_convertible_why: Counter[str] = Counter()
    out_of_time = False

    def defer(reason: str, tfam: str) -> None:
        counts[reason][DEFERRED_BUDGET] += 1
        deferred_by_family[tfam] += 1
        fam_deferred.add(tfam)

    for parent in work:
        if not time_ok():
            out_of_time = True
            break
        if new_this_pass >= cap_pass:
            break
        examined += 1
        reason = str(parent.get("reason") or "")
        examined_by_reason[reason] += 1
        fam = str(parent.get("family") or "")
        tfam = str(parent.get("trial_family") or fam)
        cell = str(parent.get("cell") or "")
        base = {"key": parent["key"], "cell": parent.get("cell"), "reason": reason,
                "family": fam, "trial_family": tfam, "at": at}
        # a steered row is served out of turn, so it never moves its family's cursor: the cursor
        # stays the unsteered queue's place, and a steered row once resolved is skipped by key
        grp = group_of(parent)
        if grp != UNSTEERED:
            steer_cursors[f"{grp}|{tfam}"] = cell
        settled = (tfam not in fam_deferred and reason != INPUT_MISSING
                   and grp == UNSTEERED)
        prior = converted_parents.get(parent_key(reason, cell))
        if prior:
            # THE SAME CELL, PARKED AGAIN: its children exist and were charged once.
            if settled:
                fam_last[tfam] = cell
            recs.append({**base, "status": CONVERTED, "child_ids": list(prior),
                         "parent_cell": parent.get("cell"), "trials_charged": 0,
                         "why": "this cell was converted when it was parked before; the same "
                                "children stand and no second trial is charged"})
            counts[reason][CONVERTED] += 1
            continue
        if cap_fam is not None and family_day[tfam] >= cap_fam:
            defer(reason, tfam)
            continue
        found = params_by_cell.get(cell)
        if not found:
            if settled:
                fam_last[tfam] = cell
            recs.append({**base, "status": UNMEASURED, "trials_charged": 0,
                         "why": "the parent's params are in neither the registry nor the docket",
                         "next_step": f"asked again after {RETRY_H:.0f}h"})
            counts[reason][UNMEASURED] += 1
            continue
        tf = str(parent.get("timeframe") or found.get("timeframe") or "H1")
        params = dict(found.get("params") or {})
        specs, max_new, why_none = plan_children(parent, params, tf, universe=universe,
                                                 space=space)
        if not specs:
            if settled:
                fam_last[tfam] = cell
            recs.append({**base, "status": NOT_CONVERTIBLE, "trials_charged": 0,
                         "why": why_none})
            counts[reason][NOT_CONVERTIBLE] += 1
            not_convertible_why[f"{reason}: {str(why_none)[:120]}"] += 1
            continue
        new: list[tuple[dict[str, Any], str]] = []
        reuse: list[tuple[dict[str, Any], str]] = []
        for spec in specs:
            cid = _cell_id(spec["symbol"], fam, spec["params"], spec["tf"])
            if any(cid == c for _, c in new):
                continue
            if cid in charged_children or exists_fn(fam, spec["symbol"], spec["params"],
                                                     spec["tf"]):
                reuse.append((spec, cid))
                continue
            new.append((spec, cid))
            if len(new) >= max_new:
                break
        if not new:
            spec, cid = reuse[0] if reuse else (specs[0], _cell_id(
                specs[0]["symbol"], fam, specs[0]["params"], specs[0]["tf"]))
            if settled:
                fam_last[tfam] = cell
            recs.append({**base, "status": CONVERTED, "route": spec["route"],
                         "child_ids": [c for _, c in reuse[:max(1, max_new)]] or [cid],
                         "child_symbol": spec["symbol"], "parent_cell": parent.get("cell"),
                         "trials_charged": 0,
                         "why": "every eligible child already exists; its trial was charged "
                                "when it was first minted, so none is charged again and this "
                                "parent is recorded as its lineage"})
            counts[reason][CONVERTED] += 1
            continue
        room = cap_pass - new_this_pass
        if cap_fam is not None:
            room = min(room, cap_fam - family_day[tfam])
        if len(new) > room:
            if new_this_pass == 0 and room > 0:
                new = new[:room]            # a budget smaller than one parent's children
            else:
                defer(reason, tfam)
                continue
        if settled:
            fam_last[tfam] = cell
        cands = []
        for spec, cid in new:
            charged_children[cid] = parent["key"]
            cands.append(child_candidate(parent, spec["symbol"], spec["params"], spec["tf"],
                                         cid, spec["route"], spec["mechanism"], spec["detail"]))
        family_day[tfam] += len(cands)
        new_this_pass += len(cands)
        by_family[tfam].append((parent, cands))

    # 4. DONATE (the charge), THEN RECORD -- a crash between can only over-count.
    donations: dict[str, Any] = {}
    donation_failed = False
    trials_this_pass: Counter[str] = Counter()
    conv_this_pass: dict[str, Counter[str]] = defaultdict(Counter)
    for tfam, items in sorted(by_family.items()):
        cands = [c for _, cs in items for c in cs]
        try:
            res = donate(tfam, cands, len(cands))
        except Exception as exc:
            res = {"error": f"{type(exc).__name__}: {exc}", "donated": 0}
        donations[tfam] = res
        if res.get("error") or not res.get("path"):
            donation_failed = True
            for parent, _cs in items:
                defer(str(parent.get("reason") or ""), tfam)
            continue
        trials_this_pass[tfam] += len(cands)
        for parent, cs in items:
            reason = str(parent.get("reason") or "")
            conv_this_pass[reason][tfam] += len(cs)
            recs.append({"key": parent["key"], "cell": parent.get("cell"), "reason": reason,
                         "family": cs[0]["family"], "trial_family": tfam, "at": at,
                         "route": cs[0]["lineage"]["route"], "status": CONVERTED,
                         "child_ids": [c["cell"] for c in cs],
                         "child_symbol": cs[0]["symbol"],
                         "children": [{"cell": c["cell"], "symbol": c["symbol"],
                                       "timeframe": c["timeframe"],
                                       **{k: v for k, v in c["lineage"].items()
                                          if k in ("relaxed_param", "from", "to", "pooled_onto",
                                                   "to_timeframe")}} for c in cs],
                         "parent_cell": parent.get("cell"), "timeframe": cs[0]["timeframe"],
                         "trials_charged": len(cs), "donation": res.get("path")})
            counts[reason][CONVERTED] += 1
    append_ledger(ledger, recs)

    # Rows due but never examined this pass: deferred by the budget, their queue place kept.
    settled_outside = Counter({INPUT_MISSING: len(input_recs)})
    for r in CONVERTING_REASONS:
        left = due[r] - settled_outside[r] - examined_by_reason[r]
        if left > 0:
            counts[r][DEFERRED_BUDGET] += left
    partial = (not stream_complete) or out_of_time

    # 5. THE CURSORS: per family, the last row settled before its first deferred one.
    lap = int(cur.get("laps") or 0)
    if not donation_failed:
        for tfam, cell in fam_last.items():
            old = family_cursors.get(tfam, legacy_cursor)
            if old and cell <= old:
                lap += 1
            family_cursors[tfam] = cell
    cursor_doc = {"cursor_cell": max(family_cursors.values()) if family_cursors else
                  legacy_cursor, "family_cursors": dict(sorted(family_cursors.items())),
                  "laps": lap, "steer_cursors": dict(sorted(
                      (steer_cursors_in if donation_failed else steer_cursors).items())),
                  "at": at, "handoff_generated_utc": head.get("generated_utc"),
                  "rule": ("each trial_family's rows are worked in the handoff's cell order from "
                           "its own cursor; families are interleaved round-robin")}
    _atomic_write(cursor_path, cursor_doc)

    lifetime_trials = Counter(led["lifetime_trials"])
    lifetime_trials.update(trials_this_pass)
    lifetime_rf = Counter(led["lifetime_by_reason_family"])
    for r, c in conv_this_pass.items():
        for f, n in c.items():
            lifetime_rf[f"{r}|{f}"] += n
    lifetime_conv: dict[str, dict[str, int]] = defaultdict(dict)
    for k, n in sorted(lifetime_rf.items()):
        r, _, f = k.partition("|")
        lifetime_conv[r][f] = n
    by_status: Counter[str] = Counter()
    for c in counts.values():
        by_status.update(c)
    deferred_by_reason = {r: int(counts[r].get(DEFERRED_BUDGET, 0)) for r in CONVERTING_REASONS
                          if counts[r].get(DEFERRED_BUDGET)}
    open_rows = {r: int(sum(counts[r].get(st, 0) for st in (DEFERRED_BUDGET, UNMEASURED,
                                                             AWAITING_INPUT)))
                 for r in CONVERTING_REASONS}
    backlog_trials = {r: n * CHILDREN_PER_PARENT[r] for r, n in open_rows.items() if n}
    per_day = int(budget["per_day"])
    total_backlog = int(sum(backlog_trials.values()))
    accounted = int(sum(by_status.values()))
    doc = {
        "generated_utc": at, "schema_version": 2, "producer": SEAT,
        "handoff": {**head, "rows_read": rows_read, "complete": stream_complete,
                    "rows_unread": (max(0, int(head["n"]) - rows_read)
                                    if isinstance(head.get("n"), int) else None)},
        "partial": partial,
        "counts": {r: dict(sorted(c.items())) for r, c in sorted(counts.items())},
        "by_status": dict(sorted(by_status.items())),
        "accounting": {
            "rows_read": rows_read, "rows_with_outcome": accounted,
            "every_row_accounted": accounted == rows_read,
            "outcomes": [CONVERTED, DEFECT_REPORTED, NOT_CONVERTIBLE, UNMEASURED, AWAITING_INPUT,
                         DEFERRED_BUDGET, UNHANDLED_REASON],
            "rule": ("every handoff row read ends with one outcome: converted, deferred by the "
                     "budget (its queue place kept), retryable with a named next step, "
                     "NOT_CONVERTIBLE with its reason, or UNHANDLED_REASON; nothing is held")},
        "unhandled_reasons": {"rows": int(sum(unhandled.values())),
                              "by_reason": dict(sorted(unhandled.items())),
                              "rule": ("a handoff reason this organ has no route for is counted "
                                       "here every pass until a route is written for it")},
        "trial_budget": {**budget, "applied_per_pass": cap_pass,
                         "applied_per_family_per_day": cap_fam,
                         "examined_per_pass_cap": examine_cap},
        "conversions": {
            "this_pass": {r: dict(sorted(c.items())) for r, c in sorted(conv_this_pass.items())},
            "lifetime": dict(lifetime_conv),
            "unit": "new child cells (= trials charged), per handoff reason x trial_family"},
        "not_convertible_reasons": dict(not_convertible_why.most_common(30)),
        "converted_per_family": {
            "this_pass": dict(sorted(trials_this_pass.items())),
            "lifetime": dict(sorted((Counter(led["lifetime_converted"])
                                     + Counter(trials_this_pass)).items()))},
        "trials_charged": {
            "this_pass": int(sum(trials_this_pass.values())),
            "this_pass_by_family": dict(sorted(trials_this_pass.items())),
            "lifetime": int(sum(lifetime_trials.values())),
            "lifetime_by_family": dict(sorted(lifetime_trials.items())),
            "mechanism": ("proposer_common.donate: one data/intelligence/" + SEAT
                          + "/discoveries_<stamp>_<family>.json per trial_family with tests_run "
                          "= its new children of every route; libs.research.experiment_ledger."
                          "_proposer_counts reads tests_run into the lifetime and per-family "
                          "census. One trial per new child; none for a reused child, a defect "
                          "report, a data gap or a refusal. No search_trials is attached "
                          "(L1.60)."),
        },
        "donations": donations,
        "deferred_backlog": {
            "rows": int(sum(deferred_by_reason.values())),
            "by_reason": deferred_by_reason,
            "capped_by_family": dict(sorted(deferred_by_family.items())),
            "unread_rows": (max(0, int(head["n"]) - rows_read)
                            if isinstance(head.get("n"), int) else None),
            "retried": "every pass, from each family's cursor"},
        "projection": {
            "open_rows_by_reason": {r: n for r, n in open_rows.items() if n},
            "backlog_trials_by_reason": backlog_trials,
            "backlog_trials": total_backlog,
            "budget_per_day": per_day,
            "days_to_clear": (round(total_backlog / per_day, 2) if per_day > 0 else None),
            "complete": stream_complete,
            "basis": ("open rows (deferred + retryable) x children per parent "
                      f"{CHILDREN_PER_PARENT}, over the day's trial budget; an upper bound, "
                      "since refusals and reused children charge nothing")},
        "lockbox": {"decision": NOT_CONVERTIBLE, "rule": LOCKBOX_RULE},
        "caps": {"MAX_CHILDREN_NEVER_FIRES": MAX_CHILDREN_NEVER_FIRES,
                 "JUDGE_VOLUME_FLOOR_PER_DAY": JUDGE_VOLUME_FLOOR_PER_DAY,
                 "FALLBACK_TRIALS_PER_DAY": FALLBACK_TRIALS_PER_DAY,
                 "MIN_PEER_HISTORY_DAYS": MIN_PEER_HISTORY_DAYS,
                 "MIN_PEER_LEAD_DAYS": MIN_PEER_LEAD_DAYS, "RETRY_H": RETRY_H},
        "cursor": cursor_doc,
        "breadth": {**_breadth_counts(recs, work, steer, steer_selected, group_of, class_of,
                                      share),
                    "exotic_quota": _exotic_split(recs, work, work[:examined], exotic, q,
                                                  exotic_selected, exotic_held)},
        "budget": {"requested_s": budget_s, "work_limit_s": round(limit, 1),
                   "elapsed_s": round(clock() - t0, 2), "examined": examined,
                   "selected": len(work), "not_examined": len(work) - examined,
                   "input_rows_checked": len(input_recs) + len(restored)},
        "artifacts": {"ledger": str(ledger), "defects": str(defects), "gaps": str(gaps),
                      "cursor": str(cursor_path)},
        "family_build_defects": {"rows": agg.total, "families": len(agg.by_family),
                                 "top": [{"family": r["family"], "count": r["count"]}
                                         for r in defect_doc["ranked"][:10]]},
        "build_input_gaps": {"rows": gap.rows, "distinct_inputs": len(gap.by_input),
                             "top": [{"input": k, "cells_blocked": n}
                                     for k, n in gap.by_input.most_common(10)]},
    }
    if not head.get("exists"):
        doc["status"] = UNMEASURED
        doc["why"] = f"{handoff} is absent: the judge has written no handoff here"
    _atomic_write(report, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true", help="run one pass (the hourly leg)")
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    ap.add_argument("--handoff", type=Path, default=None)
    a = ap.parse_args(argv)
    doc = run_pass(handoff=a.handoff, budget_s=a.budget_s)
    print(json.dumps({"by_status": doc.get("by_status"), "partial": doc.get("partial"),
                      "trials_charged": doc["trials_charged"]["this_pass"],
                      "report": str(REPORT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
