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
import contextlib
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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

_DECODER = json.JSONDecoder()
_WS = " \t\r\n"


def _iter_array(fh: Any, buf: str, pos: int, chunk: int) -> Iterator[Any]:
    """Yield each element of a JSON array whose '[' is at `buf[pos-1]`, reading `fh` lazily."""
    eof = False
    while True:
        while True:
            while pos < len(buf) and buf[pos] in _WS + ",":
                pos += 1
            if pos < len(buf) or eof:
                break
            more = fh.read(chunk)
            if not more:
                eof = True
            buf, pos = buf[pos:] + more, 0
        if pos >= len(buf):
            return                      # truncated file: what was read stands, nothing invented
        if buf[pos] == "]":
            return
        try:
            obj, end = _DECODER.raw_decode(buf, pos)
        except ValueError:
            if eof:
                return
            more = fh.read(chunk)
            if not more:
                eof = True
            buf, pos = buf[pos:] + more, 0
            continue
        yield obj
        pos = end
        if pos > chunk:
            buf, pos = buf[pos:], 0


def handoff_header(path: Path) -> dict[str, Any]:
    """schema_version / generated_utc / n and the file's format, from its first 64 KiB."""
    out: dict[str, Any] = {"path": str(path), "exists": path.exists()}
    if not out["exists"]:
        return out
    try:
        with path.open("r", encoding="utf-8") as fh:
            head = fh.read(65536)
    except OSError as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out
    first = head.split("\n", 1)[0].strip()
    try:
        row = json.loads(first) if first else None
    except ValueError:
        row = None
    if isinstance(row, dict) and "cell" in row:
        out["format"] = "jsonl"
        return out
    out["format"] = "json"
    for key, pat in (("schema_version", r'"schema_version"\s*:\s*(\d+)'),
                     ("generated_utc", r'"generated_utc"\s*:\s*"([^"]*)"'),
                     ("n", r'"n"\s*:\s*(\d+)')):
        m = re.search(pat, head.split('"rows"', 1)[0])
        if m:
            out[key] = int(m.group(1)) if key != "generated_utc" else m.group(1)
    return out


def iter_handoff(path: Path, chunk: int = 1 << 20) -> Iterator[dict[str, Any]]:
    """Every handoff row, streamed. JSONL (one row per line) and the writer's JSON object form
    (`{"schema_version", "generated_utc", "n", "rows": [...]}`, indent=1) are both read."""
    head = handoff_header(path)
    if not head.get("exists") or head.get("error"):
        return
    with path.open("r", encoding="utf-8") as fh:
        if head.get("format") == "jsonl":
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    yield row
            return
        buf = ""
        eof = False
        while True:
            m = re.search(r'"rows"\s*:\s*\[', buf)
            if m:
                break
            if eof:
                return
            more = fh.read(chunk)
            if not more:
                eof = True
            buf += more
        for row in _iter_array(fh, buf, m.end(), chunk):
            if isinstance(row, dict):
                yield row


def iter_json_list(path: Path, chunk: int = 1 << 20) -> Iterator[dict[str, Any]]:
    """Each element of a top-level JSON list (the docket), streamed."""
    try:
        fh = path.open("r", encoding="utf-8")
    except OSError:
        return
    with fh:
        buf = fh.read(chunk)
        i = buf.find("[")
        if i < 0:
            return
        for row in _iter_array(fh, buf, i + 1, chunk):
            if isinstance(row, dict):
                yield row


# =============================================================================================
# THE RESOLUTION LEDGER
# =============================================================================================

def row_key(row: Mapping[str, Any]) -> str:
    """A handoff row's identity: the judge's cell id, its parked reason and when it was parked.
    The cell id is the judge's own (`frontier_identity.docket_cell_id`, carried as `cell`); the
    parked stamp makes a cell the judge re-admits and re-parks a NEW row, never a resolved one."""
    raw = "|".join(str(row.get(k) or "") for k in ("cell", "reason", "first_parked_utc"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def parent_key(reason: Any, cell: Any) -> str:
    """A converted parent's identity across re-parks: the same cell under the same reason."""
    return f"{reason or ''}|{cell or ''}"


def load_ledger(path: Path, today: str | None = None) -> dict[str, Any]:
    """What the append-only ledger already settled. A torn line skips itself, never the rest.
    `today` (an ISO date) is the UTC day whose charges count against the day's budget."""
    resolved: dict[str, str] = {}
    retry_at: dict[str, tuple[str, str]] = {}
    charged_children: dict[str, str] = {}
    converted_parents: dict[str, list[str]] = {}
    family_day: Counter[str] = Counter()
    lifetime_trials: Counter[str] = Counter()
    lifetime_converted: Counter[str] = Counter()
    lifetime_by_reason_family: Counter[str] = Counter()
    today = today or _now().date().isoformat()
    try:
        fh = path.open("r", encoding="utf-8")
    except OSError:
        fh = None
    if fh is not None:
        with fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(rec, dict) or not rec.get("key"):
                    continue
                st = str(rec.get("status") or "")
                key = str(rec["key"])
                if st in TERMINAL:
                    resolved[key] = st
                    retry_at.pop(key, None)
                elif st in RETRYABLE and key not in resolved:
                    retry_at[key] = (st, str(rec.get("at") or ""))
                if st == CONVERTED:
                    fam = str(rec.get("trial_family") or rec.get("family") or "?")
                    lifetime_converted[fam] += 1
                    n = int(rec.get("trials_charged") or 0)
                    if n:
                        lifetime_trials[fam] += n
                        lifetime_by_reason_family[f"{rec.get('reason')}|{fam}"] += n
                        if str(rec.get("at") or "")[:10] == today:
                            family_day[fam] += n
                    for cid in rec.get("child_ids") or []:
                        charged_children.setdefault(str(cid), key)
                    if rec.get("cell") and rec.get("child_ids"):
                        converted_parents.setdefault(parent_key(rec.get("reason"), rec["cell"]),
                                                     [str(c) for c in rec["child_ids"]])
    return {"resolved": resolved, "retry_at": retry_at,
            "charged_children": charged_children, "converted_parents": converted_parents,
            "family_day": family_day, "lifetime_by_reason_family": lifetime_by_reason_family,
            "lifetime_trials": lifetime_trials, "lifetime_converted": lifetime_converted}


def append_ledger(path: Path, recs: Sequence[Mapping[str, Any]]) -> int:
    if not recs:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
        fh.flush()
        with contextlib.suppress(OSError):
            os.fsync(fh.fileno())
    return len(recs)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _atomic_write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, path)


# =============================================================================================
# build_failed -> the family defect report
# =============================================================================================

_HEX = re.compile(r"\b[0-9a-f]{8,}\b")
_NUM = re.compile(r"\d+(?:\.\d+)?")
_SPACE = re.compile(r"\s+")


def failure_signature(why: Any, symbol: Any = "") -> str:
    """The failure message with the parts that vary per cell (symbol, hashes, numbers) folded,
    so one defect in one family reads as one line however many cells hit it."""
    s = str(why or "").strip()
    if not s:
        return "(no message recorded)"
    sym = str(symbol or "").strip()
    if sym:
        s = s.replace(sym, "<SYM>")
    s = _HEX.sub("<HEX>", s)
    s = _NUM.sub("N", s)
    return _SPACE.sub(" ", s)[:200]


class DefectAggregate:
    """(family -> signature -> count, samples) over every build_failed row in the handoff."""

    def __init__(self) -> None:
        self.by_family: dict[str, Counter[str]] = defaultdict(Counter)
        self.samples: dict[tuple[str, str], dict[str, Any]] = {}
        self.total = 0

    def add(self, row: Mapping[str, Any]) -> None:
        fam = str(row.get("family") or "?")
        sig = failure_signature(row.get("why"), row.get("symbol"))
        self.total += 1
        self.by_family[fam][sig] += 1
        s = self.samples.setdefault((fam, sig), {"message": str(row.get("why") or "")[:300],
                                                 "cells": [], "symbols": set(),
                                                 "timeframes": Counter()})
        if len(s["cells"]) < DEFECT_SAMPLES:
            s["cells"].append(str(row.get("cell") or ""))
        if len(s["symbols"]) < 50:
            s["symbols"].add(str(row.get("symbol") or ""))
        s["timeframes"][str(row.get("timeframe") or "H1")] += 1

    def report(self, owners: Mapping[str, str], *, at: str, handoff: Mapping[str, Any],
               partial: bool) -> dict[str, Any]:
        fams = sorted(self.by_family.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))
        ranked = []
        for fam, sigs in fams[:DEFECT_FAMILIES_LISTED]:
            msgs = []
            for sig, n in sigs.most_common(DEFECT_MESSAGES_PER_FAMILY):
                s = self.samples.get((fam, sig), {})
                msgs.append({"signature": sig, "count": n,
                             "sample_message": s.get("message"),
                             "sample_cells": list(s.get("cells") or []),
                             "sample_symbols": sorted(s.get("symbols") or [])[:DEFECT_SAMPLES],
                             "timeframes": dict(s.get("timeframes") or {})})
            total = sum(sigs.values())
            ranked.append({
                "family": fam, "count": total, "distinct_messages": len(sigs),
                "owner": owners.get(fam) or "UNMEASURED (family constructor not resolvable)",
                "messages": msgs,
                "issue": (f"{fam}: {total} parked cells failed to BUILD (signal construction "
                          f"raised). Top cause ({msgs[0]['count'] if msgs else 0}x): "
                          f"{msgs[0]['signature'] if msgs else '?'}. Fix the constructor; the "
                          "judge re-admits these cells after BUILD_FAILED_RETRY_DAYS once code "
                          "ships. No trial was minted for them.")})
        return {
            "generated_utc": at, "schema_version": 1, "producer": SEAT,
            "handoff": dict(handoff), "partial": partial,
            "build_failed_rows": self.total, "families": len(self.by_family),
            "ranked": ranked,
            "rule": ("build_failed is a family defect report, never a hypothesis: each row "
                     "resolves DEFECT_REPORTED and no trial is minted or charged for it. The "
                     "family's owner is the source file of its constructor "
                     "(mt5desk.families.get_family_func)."),
        }


def family_owners(families: Sequence[str]) -> dict[str, str]:
    """family -> the repo-relative file that builds it, or nothing when it cannot be resolved."""
    out: dict[str, str] = {}
    try:
        import inspect

        from mt5desk.families import get_family_func
    except Exception:
        return out
    for fam in families:
        try:
            fn = get_family_func(fam)
            src = inspect.getsourcefile(fn) if fn is not None else None
        except Exception:
            src = None
        if src:
            try:
                out[fam] = str(Path(src).resolve().relative_to(ROOT)).replace("\\", "/")
            except ValueError:
                out[fam] = str(src)
    return out


# =============================================================================================
# short_history_after_cut -> cross_asset_transplant
# =============================================================================================

def _cell_id(symbol: str, family: str, params: Mapping[str, Any], timeframe: str) -> str:
    try:
        from research.frontier_identity import docket_cell_id
    except ImportError:                                           # pragma: no cover - import ctx
        from frontier_identity import docket_cell_id  # type: ignore[no-redef]
    return str(docket_cell_id({"symbol": symbol, "family": family, "params": dict(params),
                               "timeframe": timeframe}))


_HIST_MEMO: dict[tuple[str, str], datetime | None] = {}


def history_start(symbol: str, timeframe: str, universe: Path | None = None) -> datetime | None:
    """The first bar on `symbol`'s `timeframe` chart, from the parquet footer (no bars read)."""
    k = (str(universe or UNIVERSE), f"{symbol}_{timeframe}")
    if k in _HIST_MEMO:
        return _HIST_MEMO[k]
    p = (universe or UNIVERSE) / f"{symbol}_{timeframe}.parquet"
    out: datetime | None = None
    if p.exists():
        try:
            import pyarrow.parquet as pq
            md = pq.ParquetFile(p).metadata
            names = [md.schema.column(i).name for i in range(md.num_columns)]
            col = names.index("time") if "time" in names else None
            lows = []
            if col is not None:
                for g in range(md.num_row_groups):
                    st = md.row_group(g).column(col).statistics
                    if st is not None and st.has_min_max:
                        lows.append(st.min)
            if lows:
                t = min(lows)
                if isinstance(t, datetime):
                    out = t if t.tzinfo else t.replace(tzinfo=UTC)
                elif isinstance(t, (int, float)):
                    out = datetime.fromtimestamp(float(t) / 1e9, tz=UTC)
        except Exception:
            out = None
    _HIST_MEMO[k] = out
    return out


def _policy() -> Any:
    try:
        import research.universe_policy as up
    except ImportError:                                           # pragma: no cover - import ctx
        import universe_policy as up  # type: ignore[no-redef]
    return up


def lane_allows(symbol: str, family: str) -> bool:
    """The two-lane law: a share CFD only in the cross-sectional class-book families, anything
    else only when the policy says it is hunted for hypotheses."""
    up = _policy()
    if up.is_equity(symbol):
        return family in up.CROSS_SECTIONAL_FAMILIES
    return bool(up.may_hypothesise(symbol, family))


def ranked_peers(symbol: str, family: str, timeframe: str, *,
                 now: datetime | None = None,
                 universe: Path | None = None,
                 min_lead_days: int | None = MIN_PEER_LEAD_DAYS) -> tuple[list[str], str | None]:
    """Same-class peers with enough history on the same chart, longest history first.

    Returns (peers, why-none). `min_lead_days=None` drops the lead over the parent's own first
    bar (a cross-sectional pool needs a long panel member, not one older than the parent).
    The class is `universe_policy.peer_class`, from the broker
    registry; an unclassified symbol has no peers (absence is not a permission)."""
    up = _policy()
    if not lane_allows(symbol, family):
        return [], ("two-lane law: the parent is a share CFD and the family is not a "
                    "cross-sectional class book (universe_policy.CROSS_SECTIONAL_FAMILIES)")
    klass = up.peer_class(symbol)
    if not klass:
        return [], f"{symbol} has no peer class in the broker registry (universe_policy)"
    members = [m for m in up.class_members(klass) if str(m).upper() != symbol.upper()]
    t_now = now or _now()
    own = history_start(symbol, timeframe, universe)
    scored: list[tuple[datetime, str]] = []
    for m in members:
        if not lane_allows(m, family):
            continue
        start = history_start(m, timeframe, universe)
        if start is None:
            continue
        if (t_now - start).days < MIN_PEER_HISTORY_DAYS:
            continue
        if (min_lead_days is not None and own is not None
                and (own - start).days < min_lead_days):
            continue
        scored.append((start, str(m)))
    scored.sort()
    if not scored:
        lead = (f" starting >= {min_lead_days}d before {symbol}'s"
                if min_lead_days is not None else "")
        return [], f"no {klass} peer with >= {MIN_PEER_HISTORY_DAYS}d of {timeframe} bars{lead}"
    return [m for _, m in scored], None


ParamsLookup = Callable[[Sequence[Mapping[str, Any]], Callable[[], bool]],
                        dict[str, dict[str, Any]]]
ExistsCheck = Callable[[str, str, Mapping[str, Any], str], bool]
Donor = Callable[[str, list[dict[str, Any]], int], dict[str, Any]]


def registry_params(rows: Sequence[Mapping[str, Any]],
                    time_ok: Callable[[], bool]) -> dict[str, dict[str, Any]]:
    """cell -> {"params", "timeframe"} from the canonical registry (`id` or the `donated_cell`
    alias, both indexed), checked against the judge's own identity; the docket is the fallback."""
    out: dict[str, dict[str, Any]] = {}
    want = {str(r.get("cell")): r for r in rows if r.get("cell")}
    try:
        from libs.moat import registry as reg
        conn = reg.connect()
    except Exception:
        conn = None
    if conn is not None:
        try:
            for cell, r in want.items():
                if not time_ok():
                    break
                for hit in conn.execute(
                        "SELECT family, symbol, params_json, chart FROM research_candidates "
                        "WHERE id=? OR donated_cell=? LIMIT 8", (cell, cell)).fetchall():
                    try:
                        params = json.loads(hit[2] or "{}")
                    except ValueError:
                        continue
                    tf = str(hit[3] or r.get("timeframe") or "H1")
                    if _cell_id(str(hit[1]), str(hit[0]), params, tf) == cell:
                        out[cell] = {"params": params, "timeframe": tf, "source": "registry"}
                        break
        except Exception:
            pass
        finally:
            conn.close()
    missing = {c: r for c, r in want.items() if c not in out}
    if missing and time_ok():
        out.update(docket_params(missing, time_ok))
    return out


def docket_params(want: Mapping[str, Mapping[str, Any]], time_ok: Callable[[], bool],
                  path: Path | None = None) -> dict[str, dict[str, Any]]:
    """cell -> params from the docket, streamed; only rows on a wanted (symbol, family) pair are
    hashed, so the scan costs one parse per docket row."""
    pairs = {(str(r.get("symbol") or ""), str(r.get("family") or "")) for r in want.values()}
    out: dict[str, dict[str, Any]] = {}
    for i, row in enumerate(iter_json_list(path or DOCKET)):
        if i % 2000 == 0 and not time_ok():
            break
        pair = (str(row.get("symbol") or row.get("sym") or ""), str(row.get("family") or ""))
        if pair not in pairs or not isinstance(row.get("params"), dict):
            continue
        try:
            from research.frontier_identity import docket_cell_id
            cid = str(docket_cell_id(row))
        except Exception:
            continue
        if cid in want and cid not in out:
            out[cid] = {"params": dict(row["params"]),
                        "timeframe": str(row.get("timeframe") or want[cid].get("timeframe")
                                         or "H1"),
                        "source": "docket"}
            if len(out) == len(want):
                break
    return out


def registry_has(family: str, symbol: str, params: Mapping[str, Any], chart: str) -> bool:
    """True when the exact rule is already a candidate (its trial was charged by its minter)."""
    try:
        from libs.moat import registry as reg
        conn = reg.connect()
    except Exception:
        return False
    try:
        h = reg.content_hash(family, symbol, params, chart)
        return conn.execute("SELECT 1 FROM research_candidates WHERE content_hash=? LIMIT 1",
                            (h,)).fetchone() is not None
    except Exception:
        return False
    finally:
        conn.close()


def donate_family(trial_family: str, candidates: list[dict[str, Any]],
                  tests_run: int) -> dict[str, Any]:
    """ONE contract file per trial_family through the desk's one donation door, so
    `experiment_ledger._proposer_counts` charges exactly `tests_run` trials to that family."""
    import proposer_common as pc
    slug = re.sub(r"[^A-Za-z0-9_]+", "_", trial_family)[:60] or "family"
    path = pc.donate(source=SEAT, candidates=candidates, tests_run=tests_run, suffix=slug)
    last = dict(pc.LAST_DONATION)
    return {"path": str(path) if path else None, "donated": int(last.get("donated") or 0),
            "refused_wrong_lane": int(last.get("refused_wrong_lane") or 0),
            "refused_unstamped": int(last.get("refused_unstamped") or 0),
            "registry_error": last.get("registry_error")}


def child_candidate(parent: Mapping[str, Any], symbol: str, params: Mapping[str, Any],
                    timeframe: str, child_id: str, route: str, mechanism: str,
                    detail: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """One child cell, in the donation door's shape, with the parent and the route as lineage."""
    fam = str(parent.get("family") or "")
    return {
        "source": SEAT, "kind": SEAT, "symbol": symbol, "family": fam,
        "params": dict(params), "chart": timeframe, "timeframe": timeframe,
        "mechanism": mechanism,
        "title": f"{route} {fam} {parent.get('symbol')} -> {symbol} {timeframe}",
        "url": "", "cell": child_id, "trial_family": parent.get("trial_family") or fam,
        "lineage": {"parent_cell": parent.get("cell"), "route": route,
                    "handoff_reason": parent.get("reason"), "parent_symbol": parent.get("symbol"),
                    "converter": SEAT, **dict(detail or {})},
        "evidence": {"route": route, "parent_cell": parent.get("cell"),
                     "parent_why": str(parent.get("why") or "")[:200],
                     "screen": "none: a conversion, judged only by the ten gates"},
    }


def transplant_candidate(parent: Mapping[str, Any], peer: str, params: Mapping[str, Any],
                         timeframe: str, child_id: str) -> dict[str, Any]:
    fam = str(parent.get("family") or "")
    return child_candidate(
        parent, peer, params, timeframe, child_id, ROUTE_TRANSPLANT,
        f"{fam} on {peer}: the same rule as {parent.get('cell')}, transplanted to a same-class "
        "peer whose history predates the lockbox cut")


# =============================================================================================
# THE MULTIPLE-TESTING BUDGET -- derived from the judge's measured spare capacity
# =============================================================================================

def _num(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)


def _age_h(stamp: Any, now: datetime) -> float | None:
    try:
        t = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return (now - t).total_seconds() / 3600.0


def judge_capacity(reports: Path | None = None, *,
                   now: datetime | None = None) -> dict[str, Any]:
    """Cells the judge judges a day, MEASURED: the last sweep's judged cells over its wall time.

    Returns {"status": "MEASURED", "per_day", "judged_per_sweep", "sweep_s", "sources"} or
    {"status": "UNMEASURED", "why"}. A source older than CAPACITY_MAX_AGE_H is not today's judge."""
    root = reports or REPORTS
    t_now = now or _now()
    judged: float | None = None
    src_judged = ""
    why: list[str] = []
    thr = _read_json(root / "JUDGING_THROUGHPUT.json")
    if isinstance(thr, dict):
        age = _age_h(thr.get("at"), t_now)
        q = thr.get("queue")
        v = _num(q.get("judged_last_sweep")) if isinstance(q, dict) else None
        if age is not None and age > CAPACITY_MAX_AGE_H:
            why.append(f"JUDGING_THROUGHPUT.json is {age:.0f}h old")
        elif v and v > 0:
            judged, src_judged = v, "JUDGING_THROUGHPUT.json queue.judged_last_sweep"
    if judged is None:
        bp = _read_json(root / "GAUNTLET_BACKPRESSURE.json")
        cap = bp.get("capacity") if isinstance(bp, dict) else None
        meas = cap.get("measured") if isinstance(cap, dict) else None
        if isinstance(meas, dict):
            age = _age_h(meas.get("swept_at") or (bp or {}).get("at"), t_now)
            v = _num(meas.get("n_judged"))
            if age is not None and age > CAPACITY_MAX_AGE_H:
                why.append(f"GAUNTLET_BACKPRESSURE.json is {age:.0f}h old")
            elif v and v > 0:
                judged = v
                src_judged = "GAUNTLET_BACKPRESSURE.json capacity.measured.n_judged"
    res = _read_json(root / "JUDGE_RESIDENT.json")
    sweep_s = _num(res.get("last_sweep_s")) if isinstance(res, dict) else None
    if judged is None:
        why.append("no judged-per-sweep figure in JUDGING_THROUGHPUT.json or "
                   "GAUNTLET_BACKPRESSURE.json")
    if not sweep_s or sweep_s <= 0:
        why.append("no sweep wall time (JUDGE_RESIDENT.json last_sweep_s)")
    if judged is None or not sweep_s or sweep_s <= 0:
        return {"status": UNMEASURED, "why": "; ".join(why)}
    return {"status": "MEASURED", "per_day": int(judged * 86400.0 / sweep_s),
            "judged_per_sweep": int(judged), "sweep_s": round(sweep_s, 1),
            "sources": [src_judged, "JUDGE_RESIDENT.json last_sweep_s"]}


def judge_inflow(reports: Path | None = None) -> dict[str, Any]:
    """Cells every other producer mints a day (they compete for the same judge)."""
    doc = _read_json((reports or REPORTS) / "JUDGING_RATE.json")
    v = _num(doc.get("created_per_day")) if isinstance(doc, dict) else None
    if v is None or v < 0:
        return {"status": UNMEASURED, "per_day": 0,
                "why": "JUDGING_RATE.json created_per_day absent: no inflow subtracted"}
    return {"status": "MEASURED", "per_day": int(v),
            "source": "JUDGING_RATE.json created_per_day"}


def trial_budget(reports: Path | None = None, *, charged_today: int = 0,
                 now: datetime | None = None) -> dict[str, Any]:
    """The day's and this pass's conversion budget, in NEW TRIALS (child cells).

    day = measured capacity - other producers' daily inflow (the volume floor is the judge's
    target, published as judge_gap_per_day when capacity is short of it, never fed);
    pass = what is left of the day / the hourly passes left in the UTC day (a missed pass is
    caught up). No capacity artifact: FALLBACK_TRIALS_PER_DAY, labelled UNMEASURED."""
    t_now = now or _now()
    cap = judge_capacity(reports, now=t_now)
    inflow = judge_inflow(reports)
    if cap["status"] == "MEASURED":
        capacity = int(cap["per_day"])
        day = max(0, capacity - int(inflow["per_day"]))
        status = "MEASURED"
        basis = f"measured {cap['per_day']}/day - inflow {inflow['per_day']}/day"
        gap = max(0, JUDGE_VOLUME_FLOOR_PER_DAY - capacity)
    else:
        capacity = None
        gap = None
        day = FALLBACK_TRIALS_PER_DAY
        status = UNMEASURED
        basis = (f"UNMEASURED: {cap.get('why')}; fallback constant FALLBACK_TRIALS_PER_DAY="
                 f"{FALLBACK_TRIALS_PER_DAY}")
    passes_left = max(1, PASSES_PER_DAY - t_now.hour)
    left = max(0, day - int(charged_today))
    per_pass = -(-left // passes_left) if left else 0
    return {"status": status, "per_day": int(day), "per_pass": int(per_pass),
            "charged_today": int(charged_today), "remaining_today": int(left),
            "passes_left_today": passes_left, "capacity_per_day": capacity,
            "judge_volume_floor_per_day": JUDGE_VOLUME_FLOOR_PER_DAY,
            "judge_gap_per_day": gap,
            "capacity": cap, "inflow": inflow, "basis": basis,
            "rule": ("every converted child is a new trial charged to its trial_family; the "
                     "budget is the judge's spare capacity so conversion never outruns what the "
                     "judge can absorb, and never stops short of it")}


# =============================================================================================
# never_fires -> relaxed_threshold, read off the family's own grid
# =============================================================================================

#: Never relaxed: exit-side params (they change how a trade ends, not whether the entry fires)
#: and params with no single firing direction (wait_bars widens one window and delays another).
EXIT_PARAM = re.compile(r"^(rr|rr_mult|ttl_bars|ttl_mult|hold_bars|hold_d|stop_atr|atr_n|"
                        r"timeframe|wait_bars)$")
#: Entry params where a HIGHER value fires more often (a low quantile, an oversold level, a cap).
HIGHER_FIRES = re.compile(r"^(lo_q|oversold)$|^max_")
#: Entry params where a LOWER value fires more often (thresholds, band widths, ATR triggers,
#: an upper quantile, an overbought level, a breakout channel, any minimum).
LOWER_FIRES = re.compile(r"thresh|_atr$|^bb_k$|^vol_mult$|^overbought$|^hi_q$|^stress_q$|"
                         r"^channel$|^min_|_pct$|^z$|^k$|sigma|_mult$")
#: The loosest value a categorical entry filter can take, when the grid offers it.
LOOSE_CATEGORIES = ("any", "all", "none", "off")


def family_param_space(family: str) -> tuple[dict[str, list[Any]], dict[str, Any]]:
    """(grid, defaults) for `family` from the family registry, READ-ONLY; ({}, {}) if none."""
    grid: dict[str, list[Any]] = {}
    defaults: dict[str, Any] = {}
    try:
        from mt5desk.families import FAMILY_REGISTRY
        entry = FAMILY_REGISTRY.get(family)
        if entry:
            grid = {k: list(v) for k, v in dict(entry.get("param_grid") or {}).items()}
            defaults = dict(entry.get("defaults") or {})
    except Exception:
        pass
    if not grid:
        try:
            from mt5desk import families_cross_sectional as xs
            grid = {k: list(v) for k, v in dict(xs.PARAM_GRID.get(family) or {}).items()}
        except Exception:
            pass
    return grid, defaults


def _looser(name: str, current: Any, values: Sequence[Any]) -> list[Any]:
    """Grid values of `name` looser than `current`, nearest first; [] when none or no direction."""
    if EXIT_PARAM.search(name):
        return []
    if isinstance(current, str):
        loose = [v for v in values if v in LOOSE_CATEGORIES]
        return [loose[0]] if loose and current not in LOOSE_CATEGORIES else []
    cur = _num(current)
    if cur is None:
        return []
    nums = sorted({float(v) for v in values if _num(v) is not None})
    if HIGHER_FIRES.search(name):
        out = [v for v in nums if v > cur]
    elif LOWER_FIRES.search(name):
        out = sorted((v for v in nums if v < cur), reverse=True)
    else:
        return []
    # Keep the grid's own spelling (an int stays an int).
    spelled = {float(v): v for v in values if _num(v) is not None}
    return [spelled[v] for v in out]


def relaxed_children(params: Mapping[str, Any], grid: Mapping[str, Sequence[Any]],
                     defaults: Mapping[str, Any] | None = None,
                     max_children: int = MAX_CHILDREN_NEVER_FIRES
                     ) -> tuple[list[dict[str, Any]], str | None]:
    """Up to `max_children` relaxations, ONE param each: the first relaxable param's next grid
    step, then its loosest grid value (or the next param's step when it has only one).
    Returns ([{"param", "from", "to", "params"}], why-none)."""
    defaults = defaults or {}
    steps: list[tuple[str, Any, list[Any]]] = []
    for name in sorted(grid):
        cur = params.get(name, defaults.get(name))
        if cur is None:
            continue
        loose = _looser(name, cur, list(grid[name]))
        if loose:
            steps.append((name, cur, loose))
    if not steps:
        return [], ("the family's grid exposes no relaxable entry param "
                    f"(grid params: {sorted(grid) or 'none'}; exit-side params are never "
                    "relaxed)")
    out: list[dict[str, Any]] = []
    name, cur, loose = steps[0]
    picks = [(name, cur, loose[0])]
    if len(loose) > 1:
        picks.append((name, cur, loose[-1]))
    elif len(steps) > 1:
        picks.append((steps[1][0], steps[1][1], steps[1][2][0]))
    for name, cur, to in picks[:max_children]:
        out.append({"param": name, "from": cur, "to": to, "params": {**params, name: to}})
    return out, None


# =============================================================================================
# too_rare -> coarser_timeframe / cross_sectional_pool
# =============================================================================================

CHART_LADDER: tuple[str, ...] = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")
_PINNED: dict[str, str] | None = None


def pinned_timeframes() -> dict[str, str]:
    """The judge's per-family chart pins (`external_gauntlet._PINNED_TIMEFRAME`), read from its
    source text so the sealed module is neither imported nor edited; {} when unreadable."""
    global _PINNED
    if _PINNED is None:
        _PINNED = {}
        try:
            import ast
            text = (DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")
            m = re.search(r"^_PINNED_TIMEFRAME\s*=\s*(\{[^}]*\})", text, re.M)
            if m:
                got = ast.literal_eval(m.group(1))
                if isinstance(got, dict):
                    _PINNED = {str(k): str(v) for k, v in got.items()}
        except Exception:
            _PINNED = {}
    return _PINNED


def coarser_chart(timeframe: str, family: str = "") -> tuple[str | None, str | None]:
    """The next rung up the chart ladder, or (None, why)."""
    if family in pinned_timeframes():
        return None, f"{family} is pinned to {pinned_timeframes()[family]} by the judge"
    tf = str(timeframe or "H1").upper()
    if tf not in CHART_LADDER:
        return None, f"{tf} is not on the chart ladder {CHART_LADDER}"
    i = CHART_LADDER.index(tf)
    if i + 1 >= len(CHART_LADDER):
        return None, f"{tf} is already the coarsest chart on the ladder"
    return CHART_LADDER[i + 1], None


# =============================================================================================
# build_input_missing -> the data-gap report, and the retry
# =============================================================================================

def input_labels(row: Mapping[str, Any]) -> list[str]:
    """The inputs a parked row lacks, as stable labels (`bars:<file>`, `surface:<sym>`, ...)."""
    mi = row.get("missing_input")
    items: Any = None
    if isinstance(mi, dict):
        items = mi.get("inputs") if mi.get("inputs") is not None else (
            [mi.get("input")] if mi.get("input") else None)
    if items is None:
        items = row.get("missing")
    out: list[str] = []
    for it in items if isinstance(items, list) else ([items] if items else []):
        if isinstance(it, str) and it:
            out.append(it)
        elif isinstance(it, dict):
            kind = str(it.get("kind") or "unknown")
            what = it.get("file") or it.get("symbol") or it.get("input") or ""
            out.append(f"{kind}:{what}" if what else kind)
    return out


class InputPresence:
    """Is a labelled input present now? True / False / None (cannot say), memoised per pass.
    Bars are a stat in the universe directory; other kinds ask `build_input_probe.present`."""

    def __init__(self, universe: Path | None = None) -> None:
        self.universe = universe or UNIVERSE
        self.memo: dict[str, bool | None] = {}
        self._probe: Any = None
        self._ctx: Any = None
        self._probe_failed = False

    def __call__(self, label: str) -> bool | None:
        if label in self.memo:
            return self.memo[label]
        kind, _, rest = label.partition(":")
        got = (self.universe / rest).exists() if kind == "bars" and rest else (
            self._ask_probe(label))
        self.memo[label] = got
        return got

    def _ask_probe(self, label: str) -> bool | None:
        if self._probe_failed:
            return None
        try:
            if self._probe is None:
                try:
                    import build_input_probe as probe
                except ImportError:                               # pragma: no cover - import ctx
                    from research import build_input_probe as probe
                self._probe = probe
                self._ctx = probe._Pass()
            parsed = self._probe.parse_label(label)
            if parsed is None:
                return None
            return bool(self._probe.present(parsed, self._ctx))
        except Exception:
            self._probe_failed = True
            return None


class GapAggregate:
    """(missing input -> cells blocked, families, samples) over every unresolved
    build_input_missing row in the handoff."""

    def __init__(self) -> None:
        self.by_input: Counter[str] = Counter()
        self.families: dict[str, Counter[str]] = defaultdict(Counter)
        self.samples: dict[str, list[str]] = defaultdict(list)
        self.rows = 0

    def add(self, row: Mapping[str, Any]) -> list[str]:
        labels = input_labels(row) or ["(input not named)"]
        self.rows += 1
        for lab in labels:
            self.by_input[lab] += 1
            self.families[lab][str(row.get("family") or "?")] += 1
            if len(self.samples[lab]) < DEFECT_SAMPLES:
                self.samples[lab].append(str(row.get("cell") or ""))
        return labels

    def report(self, present: Callable[[str], bool | None], *, at: str,
               handoff: Mapping[str, Any], partial: bool) -> dict[str, Any]:
        ranked = []
        for lab, n in self.by_input.most_common(GAPS_LISTED):
            now = present(lab) if lab != "(input not named)" else None
            ranked.append({"input": lab, "kind": lab.partition(":")[0], "cells_blocked": n,
                           "present_now": now,
                           "families": dict(self.families[lab].most_common(10)),
                           "sample_cells": list(self.samples[lab])})
        return {"generated_utc": at, "schema_version": 1, "producer": SEAT,
                "handoff": dict(handoff), "partial": partial,
                "build_input_missing_rows": self.rows, "distinct_inputs": len(self.by_input),
                "ranked": ranked,
                "rule": ("a missing input is a data gap, never a hypothesis: no trial is charged "
                         "until the input exists and a real cell is minted. Rows are re-examined "
                         f"every {RETRY_H:.0f}h and convert (route input_restored) when every "
                         "input they name is present. `present_now: null` means the desk could "
                         "not say (UNMEASURED), never present.")}


# =============================================================================================
# THE PASS
# =============================================================================================

def _budget_s(requested: float, env: Mapping[str, str] | None = None) -> float:
    """BUDGET_SHARE of the smaller of --budget-s and the cycle's cap (QUANT_LEG_BUDGET_S)."""
    src = os.environ if env is None else env
    cap = requested
    try:
        leg = float(src.get("QUANT_LEG_BUDGET_S") or 0)
    except ValueError:
        leg = 0.0
    if leg > 0:
        cap = min(cap, leg)
    return max(1.0, cap) * BUDGET_SHARE


def lane_refusal(symbol: str, family: str) -> str | None:
    """Why a child on `symbol` may not be minted in `family`, or None when the lane allows it."""
    up = _policy()
    if lane_allows(symbol, family):
        return None
    if up.is_equity(symbol):
        return ("two-lane law: the parent is a share CFD and the family is not a cross-sectional "
                "class book (universe_policy.CROSS_SECTIONAL_FAMILIES)")
    return (f"{symbol} is not in the hypothesis lane (universe_policy.lane={up.lane(symbol)!r}): "
            "unclassified, event-lane or off the MT5 universe, never hunted")


ParamSpace = Callable[[str], tuple[dict[str, list[Any]], dict[str, Any]]]


def plan_children(parent: Mapping[str, Any], params: Mapping[str, Any], tf: str, *,
                  universe: Path | None, space: ParamSpace
                  ) -> tuple[list[dict[str, Any]], int, str | None]:
    """The candidate children of one parent, most preferred first, and how many may be new.

    Returns (specs, max_new, why-none); each spec is {symbol, params, tf, route, mechanism,
    detail}. The caller skips specs already charged or already in the registry."""
    reason = str(parent.get("reason") or "")
    sym = str(parent.get("symbol") or "")
    fam = str(parent.get("family") or "")
    cell = parent.get("cell")
    if reason == SHORT_HISTORY:
        peers, why = ranked_peers(sym, fam, tf, universe=universe)
        return ([{"symbol": p, "params": dict(params), "tf": tf, "route": ROUTE_TRANSPLANT,
                  "mechanism": (f"{fam} on {p}: the same rule as {cell}, transplanted to a "
                                "same-class peer whose history predates the lockbox cut"),
                  "detail": {}} for p in peers], 1, why)
    refusal = lane_refusal(sym, fam)
    if refusal:
        return [], 0, refusal
    if reason == NEVER_FIRES:
        grid, defaults = space(fam)
        kids, why = relaxed_children(params, grid, defaults)
        return ([{"symbol": sym, "params": k["params"], "tf": tf, "route": ROUTE_RELAXED,
                  "mechanism": (f"{fam} on {sym} {tf}: {cell} never fired, so its entry param "
                                f"{k['param']} is relaxed {k['from']} -> {k['to']} along the "
                                "family's own grid toward firing"),
                  "detail": {"relaxed_param": k["param"], "from": k["from"], "to": k["to"]}}
                 for k in kids], MAX_CHILDREN_NEVER_FIRES, why)
    if reason == TOO_RARE:
        specs: list[dict[str, Any]] = []
        whys: list[str] = []
        if fam in _policy().CROSS_SECTIONAL_FAMILIES:
            peers, pwhy = ranked_peers(sym, fam, tf, universe=universe, min_lead_days=None)
            specs += [{"symbol": p, "params": dict(params), "tf": tf, "route": ROUTE_POOL,
                       "mechanism": (f"{fam}: {cell} fires too rarely on {sym}; the same class "
                                     f"book is pooled onto same-class panel member {p}, whose "
                                     "longer history gives the ranking more dates"),
                       "detail": {"pooled_onto": p}} for p in peers]
            if pwhy:
                whys.append(pwhy)
        child_tf, cwhy = coarser_chart(tf, fam)
        if child_tf:
            specs.append({"symbol": sym, "params": {**params, "timeframe": child_tf},
                          "tf": child_tf, "route": ROUTE_COARSER,
                          "mechanism": (f"{fam} on {sym}: {cell} fires on too few days on {tf}; "
                                        f"the same rule one rung up the chart ladder, on "
                                        f"{child_tf} (resampled exactly from {tf} by "
                                        "conversion_maximiser.backfill_bars, or served native)"),
                          "detail": {"from_timeframe": tf, "to_timeframe": child_tf}})
        elif cwhy:
            whys.append(cwhy)
        return specs, 1, ("; ".join(whys) or None) if not specs else None
    if reason == INPUT_MISSING:
        return ([{"symbol": sym, "params": dict(params), "tf": tf, "route": ROUTE_RESTORED,
                  "mechanism": (f"{fam} on {sym} {tf}: every input {cell} lacked now exists, "
                                "so the same rule is minted as the cell it always was"),
                  "detail": {"inputs": list(parent.get("inputs") or [])}}], 1, None)
    return [], 0, f"no route for reason {reason!r}"


def round_robin(queues: Mapping[str, Sequence[dict[str, Any]]], limit: int,
                order: Sequence[str] | None = None) -> list[dict[str, Any]]:
    """One row from each family in turn until `limit`, so no family starves another."""
    fams = list(order) if order is not None else sorted(queues)
    idx = dict.fromkeys(fams, 0)
    out: list[dict[str, Any]] = []
    while len(out) < limit:
        moved = False
        for f in fams:
            q = queues.get(f) or ()
            if idx[f] < len(q):
                out.append(q[idx[f]])
                idx[f] += 1
                moved = True
                if len(out) >= limit:
                    break
        if not moved:
            break
    return out


_SLIM = ("cell", "family", "trial_family", "symbol", "timeframe", "reason", "why",
         "first_parked_utc")


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
             clock: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    handoff = handoff or HANDOFF
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
    fam_order = sorted(queues, key=lambda f: (family_day[f], f))
    work = restored + round_robin({f: a + b for f, (a, b) in queues.items()}, examine_cap,
                                  fam_order)
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
        settled = tfam not in fam_deferred and reason != INPUT_MISSING
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
                  "laps": lap, "at": at, "handoff_generated_utc": head.get("generated_utc"),
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
