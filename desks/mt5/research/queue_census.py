"""THE QUEUE CENSUS -- every place a row WAITS instead of being tested, measured hourly.

THE LAW (principal's standing order, 2026-09-23): "keep no queues, crawl everything, nothing
should be queued in the research system, all immediate tested." A row is processed ON ARRIVAL.
Where a budget genuinely runs out, the leftover is the FIRST work of the next pass and its AGE IS
PUBLISHED -- never an indefinite park.

WHY THIS ORGAN EXISTS, MEASURED 2026-09-23. The desk had no idea how much of its own work was
parked. The survey that produced the registry below found, among other things:

    research_queue.json        23,776 rows, 17,749 of them QUEUED_CANONICAL_GAUNTLET, and
                               NO SCHEDULED DRAINER AT ALL -- the only readers are report
                               builders and an archive restorer that puts rows BACK
    research_candidates        6,062 sqlite rows at status 'queued'; `registry.claim_candidates`
                               (the lease that was meant to drain them) has zero callers
    miner_deepening_queue      28,450 rows carrying NO PER-ROW TIMESTAMP, so their age was
                               literally unknowable; the file's own `built_at` was 13 days old
    mechanism_naming_queue     a 4,000-row ring buffer that SILENTLY DROPS the oldest row on
                               every write, and the drain reads the NEWEST first
    task_queue.jsonl           78 rows, drained by nobody BY DESIGN, frozen since 2026-09-16

None of that was a secret and none of it was visible either: each number lived inside the organ
that produced it, in a different unit, and no artifact anywhere put them side by side. A backlog
nobody counts is a backlog nobody drains.

WHAT ONE PASS DOES. For every queue in `QUEUES` it measures DEPTH, the AGE OF THE OLDEST ROW, and
the DRAIN RATE (rows per hour, differenced against the previous census -- a measurement, never a
declaration), then writes `desks/mt5/reports/QUEUE_CENSUS.json` and appends one line to
`desks/mt5/data/queue_census_history.jsonl` so the next pass can difference against it.

IT CONSUMES, IT NEVER RE-DERIVES. Four organs already publish their own backlog and carry, and
they are owned by other builders: `conversion_maximiser` (CONVERSION_MAXIMISER.json:
carried_in/carried_out/oldest_unconverted), `judging_throughput` + the sealed gauntlet
(GAUNTLET_BACKPRESSURE.json: n_cells_deferred_build_budget), `coverage_drain`
(COVERAGE_DRAIN.json: backlog.oldest_wait_h) and `forward_enrolment` (FORWARD_ENROLMENT.json:
latency_h). This organ reads their artifacts and reports what they measured. It does not open
their stores and it does not second-guess their numbers.

AGE IS A VERDICT, NOT ALWAYS A NUMBER. A queue whose rows carry no enqueue timestamp reports
`oldest_age_h: null` with `age_measurable: false` and a named reason. That is UNMEASURED
(L1.28a), and `scripts/check_no_queues.py` treats it as a DEFECT to be fixed by stamping the
rows -- never as a pass.

BOUNDED BY MEASURED MEMORY, NEVER BY A MACHINE SIZE. The biggest store here is 74 MB and the box
that runs it has 8 GB. `_byte_budget()` derives the per-file cap from free physical memory and
floors at FLOOR_BYTES, so an unreadable counter changes nothing and a big box gets the bigger
budget it actually has. A file over the cap is measured by its CHEAP path (size and row count by
line, no full parse) and says so.

    python desks/mt5/research/queue_census.py --once --budget-s 120 [--json]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(REPO), str(BASE), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "QUEUE_CENSUS.json"
HISTORY = BASE / "data" / "queue_census_history.jsonl"
REGISTRY_DB = REPO / "data" / "alpha_registry.sqlite"

#: The floor is the historic bound and exists so an unreadable memory counter never shrinks the
#: pass below what it could always do. The live cap is DERIVED (see `_byte_budget`).
FLOOR_BYTES = 32 * 1024 * 1024
#: Share of measured free physical memory one pass may spend holding a queue file.
MEM_SHARE = 0.10
#: Rows sampled when a store must be scanned for its oldest timestamp.
MAX_SAMPLE = 200_000
#: Default wall budget. The cycle passes its own with --budget-s.
BUDGET_S = 120.0
#: History lines kept. One line per pass; a week at hourly is 168.
MAX_HISTORY = 2000

#: THE RULE, carried as text so the artifact states the law it is measuring against.
RULE = ("A row is processed ON ARRIVAL. Where a budget genuinely runs out the leftover is the "
        "FIRST work of the next pass and its age is published -- never an indefinite park. "
        "A queue whose oldest row is older than one cycle of the organ that owns it is a BREACH.")

#: EVERY QUEUE IN THE DESK, as data. `cycle_h` is one cycle of the organ that OWNS the queue --
#: the period the fence measures the oldest row against. `drainer` is None where the survey found
#: nothing on the other end, and that is the most important column in the table.
#:
#: kind: "json_list"  a JSON array of row dicts
#:       "json_key"   a JSON object with a list under `key`
#:       "jsonl"      one JSON row per line
#:       "sqlite"     a table in the alpha registry
#:       "artifact"   another organ already publishes this queue's depth and age; read it
QUEUES: tuple[dict[str, Any], ...] = (
    {"id": "research_queue", "kind": "json_list",
     "path": BASE / "data" / "research_queue.json",
     "time_field": "created_at", "status_field": "status",
     "open_states": ("PENDING", "QUEUED_CANONICAL_GAUNTLET", "QUEUED"),
     "writer": "scripts/promote_external_to_queue.py, scripts/convert_question_queues.py",
     "drainer": None, "owner_leg": None, "cycle_h": 1.0,
     "note": ("NO SCHEDULED DRAINER: research_loop.py and run_hunt18.py are manual CLI. Every "
              "open row here is parked by definition")},
    {"id": "registry_candidates", "kind": "sqlite", "table": "research_candidates",
     "time_field": "created_at", "status_field": "status", "open_states": ("queued", "claimed"),
     "writer": "libs/moat/registry.enqueue_candidate",
     "drainer": "conversion_maximiser (registry.mark_candidate)",
     "owner_leg": "conversion_maximiser", "cycle_h": 1.0,
     "carry_artifact": BASE / "reports" / "CONVERSION_MAXIMISER.json",
     "carry_keys": ("carried_in", "carried_out", "still_blocked", "oldest_unconverted"),
     "note": ("registry.claim_candidates() is the intended lease and has zero callers outside "
              "registry.py; rows move only through ad-hoc mark_candidate calls")},
    {"id": "registry_discoveries", "kind": "sqlite", "table": "discoveries",
     "time_field": "created_at", "status_field": "state",
     "open_states": ("UNPROCESSED", "QUEUED", "BLOCKED"),
     "writer": "libs/moat/registry.record_discovery",
     "drainer": "discovery_compiler (registry.set_discovery_state)",
     "owner_leg": "discovery_compiler", "cycle_h": 1.0,
     "note": "BLOCKED is a parked state with no re-examination clock"},
    {"id": "miner_deepening", "kind": "artifact",
     "carry_artifact": BASE / "reports" / "DEEPENING_BACKLOG.json",
     "depth_key": "depth", "age_key": "oldest_age_h",
     "carry_keys": ("depth", "oldest_age_h", "oldest_at", "rows_stamped", "decisions_per_h",
                    "days_to_clear", "lanes"),
     "writer": "research/miner_candidate_compiler.py",
     "drainer": "research/deepening_worker.py", "owner_leg": "deepen", "cycle_h": 1.0,
     "note": ("AGE IS MEASURED BY THE DRAIN, NOT THE QUEUE FILE (2026-09-24). This row read the "
              "queue file directly and reported UNMEASURED -- 28,450 rows, no per-row time -- "
              "with 'stamp the rows at build time' as the fix. Stamping there does not work: "
              "miner_candidate_compiler REWRITES the whole file every hour, so a build-time "
              "stamp resets hourly and would report a backlog permanently one hour old. "
              "deepening_worker publishes DEEPENING_BACKLOG.json instead, carrying the depth and "
              "the age of the oldest row measured from when the DRAIN first saw it, which is the "
              "number the no-queues law is actually asking for")},
    {"id": "mechanism_naming", "kind": "json_list",
     "path": BASE / "data" / "hypotheses" / "mechanism_naming_queue.json",
     "time_field": "asked_at", "status_field": None, "consumed_field": "consumed_at",
     "writer": "research/edge_search.py", "drainer": "libs/research/proposer_seat.py",
     "owner_leg": "proposer_seat", "cycle_h": 1.0,
     "note": ("RING BUFFER: edge_search writes existing[-4000:], so the oldest rows are dropped "
              "silently and the drain reads the newest first -- the loss is never counted")},
    {"id": "task_queue", "kind": "jsonl",
     "path": BASE / "data" / "task_queue.jsonl",
     "time_field": "created_at", "status_field": "state",
     "open_states": ("pending", "leased", "PENDING", "OPEN"),
     "writer": "libs/ops/task_queue.py via libs/ops/queue_cycle.py",
     "drainer": None, "owner_leg": "queue_cycle", "cycle_h": 1.0,
     "carry_artifact": BASE / "reports" / "QUEUE.json",
     "carry_keys": ("queue", "human_inbox", "needs_a_person"),
     "note": ("DRAINED BY NOBODY BY DESIGN (queue_cycle.py registers zero handlers); rows "
              "escalate to org.HUMAN_INBOX, which is a person's queue, not an immediate test")},
    {"id": "unknown_unknowns", "kind": "jsonl",
     "path": BASE / "data" / "unknown_unknowns_queue.jsonl",
     "time_field": "at", "writer": "research/unknown_unknowns.py",
     "drainer": "research/residual_queue.py", "owner_leg": "residual_queue", "cycle_h": 1.0,
     "note": ("the drain's own outputs (data/residual_queue.jsonl, reports/RESIDUAL_QUEUE.json) "
              "have never been written, so the drain has never landed")},
    {"id": "requeue_named", "kind": "json_list",
     "path": BASE / "data" / "hypotheses" / "requeue_named.json",
     "time_field": "requeued_at", "writer": "scripts/requeue_named_mechanisms.py",
     "drainer": "research/merge_hypotheses.py", "owner_leg": "merge_docket", "cycle_h": 1.0,
     "note": "merge_hypotheses skips it unless the docket was freshly rebuilt"},
    {"id": "frontier_queue", "kind": "jsonl",
     "path": BASE / "frontier_intel" / "data" / "frontier_queue.jsonl",
     "time_field": "at", "status_field": "state", "open_states": ("open", "OPEN", "new"),
     "writer": "desks/mt5/frontier_intel/queue.py",
     "drainer": "analyst_pipeline, discovery_compiler, knowledge_graph",
     "owner_leg": "analyst_pipeline", "cycle_h": 1.0, "note": ""},
    {"id": "frontier_inbox", "kind": "json_list",
     "path": BASE / "data" / "frontier_inbox.json",
     "time_field": "ts", "writer": "research/hourly_cycle.py mine()",
     "drainer": "research/hourly_cycle.py mine()", "owner_leg": "mine", "cycle_h": 1.0,
     "note": "self-draining: read, deduped and rewritten in one pass"},
    {"id": "conversion_carry", "kind": "artifact",
     "path": BASE / "data" / "conversion_maximiser_carry.json",
     "carry_artifact": BASE / "reports" / "CONVERSION_MAXIMISER.json",
     "carry_keys": ("carried_in", "carried_out", "still_blocked", "oldest_unconverted"),
     "depth_key": "still_blocked", "age_key": "oldest_unconverted",
     "writer": "research/conversion_maximiser.py", "drainer": "research/conversion_maximiser.py",
     "owner_leg": "conversion_maximiser", "cycle_h": 1.0,
     "note": ("THE PATTERN THE LAW WANTS: leftover is carried, taken first next pass, and both "
              "the count and the oldest age are published by the organ that owns it")},
    {"id": "coverage_uncrawled", "kind": "artifact",
     "carry_artifact": BASE / "reports" / "COVERAGE_DRAIN.json",
     "carry_keys": ("backlog",), "depth_path": ("backlog", "backlog_overdue"),
     "age_path": ("backlog", "oldest_wait_h"),
     "writer": "moat collectors / source registry", "drainer": "research/coverage_drain.py",
     "owner_leg": None, "cycle_h": 24.0,
     "note": ("coverage_drain has NO CLOCK: no hourly leg, no box task, no cron. Its lease is "
              "24 h, so every overdue source is parked until someone runs it by hand")},
    {"id": "gauntlet_build_deferral", "kind": "artifact",
     "carry_artifact": BASE / "reports" / "GAUNTLET_BACKPRESSURE.json",
     "carry_keys": ("capacity",),
     "depth_path": ("capacity", "measured", "n_cells_deferred_build_budget"),
     "age_path": ("capacity", "measured", "age_h"),
     "writer": "desks/mt5/scripts/external_gauntlet.py (SEALED)",
     "drainer": "desks/mt5/scripts/external_gauntlet.py (next sweep)",
     "owner_leg": "external_gauntlet", "cycle_h": 0.1667,
     "note": ("budget-deferred cells are re-picked by the next 10-minute sweep, which is the "
              "immediate-leftover pattern at its fastest cycle in the desk")},
    {"id": "forward_enrolment", "kind": "artifact",
     "carry_artifact": BASE / "reports" / "FORWARD_ENROLMENT.json",
     "carry_keys": ("latency_h",), "age_path": ("latency_h", "measured"),
     "writer": "the forward lanes", "drainer": "research/forward_enrolment.py",
     "owner_leg": "forward_enrolment", "cycle_h": 1.0,
     "note": "target latency is 0.0 h: a matured clock enrols on the same cycle"},
)

_OPEN_DEFAULT: tuple[str, ...] = ("pending", "queued", "open", "new", "unprocessed",
                                  "queued_canonical_gauntlet", "blocked", "claimed", "leased")


# ------------------------------------------------------------------------------- measurement


def _free_phys_mb() -> float | None:
    """Free physical memory, or None where the counter cannot be read. NEVER a machine size."""
    try:
        import ctypes

        class _MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        ms = _MS()
        ms.dwLength = ctypes.sizeof(_MS)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms)):
            return None
        return float(ms.ullAvailPhys) / (1024.0 * 1024.0)
    except Exception:
        pass
    try:
        import psutil  # type: ignore[import-untyped]

        return float(psutil.virtual_memory().available) / (1024.0 * 1024.0)
    except Exception:
        return None


def _byte_budget() -> tuple[int, str]:
    """The per-file cap, DERIVED from measured free memory and floored at the historic bound."""
    free = _free_phys_mb()
    if free is None:
        return FLOOR_BYTES, "free memory unreadable: the floor stands"
    derived = int(free * MEM_SHARE * 1024 * 1024)
    if derived <= FLOOR_BYTES:
        return FLOOR_BYTES, f"floor (derived {derived / 1048576:.0f} MB from {free:.0f} MB free)"
    return derived, f"derived: {MEM_SHARE:.0%} of {free:.0f} MB free"


def _now(now: datetime | None = None) -> datetime:
    return now or datetime.now(tz=UTC)


def parse_time(value: Any) -> datetime | None:
    """A row's enqueue time, or None. Accepts ISO strings and epoch seconds; never raises."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def is_open(row: dict[str, Any], spec: dict[str, Any]) -> bool:
    """Is this row still WAITING? A row with a `consumed_at` is done whatever its status says."""
    consumed = spec.get("consumed_field")
    if consumed and row.get(consumed):
        return False
    field = spec.get("status_field", "status")
    if not field:
        return True
    raw = row.get(field)
    if raw is None:
        return True
    state = str(raw).strip()
    allowed = spec.get("open_states")
    if allowed:
        return state in allowed or state.lower() in {s.lower() for s in allowed}
    return state.lower() in _OPEN_DEFAULT


def _iter_json_rows(path: Path, spec: dict[str, Any], cap: int) -> tuple[list[Any], str]:
    """Rows of a JSON store, or an empty list with a reason. Never raises on bad content."""
    try:
        size = path.stat().st_size
    except OSError:
        return [], "absent"
    if size > cap:
        return [], f"file is {size / 1048576:.1f} MB, over the {cap / 1048576:.0f} MB pass budget"
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return [], f"unreadable: {type(exc).__name__}"
    if spec["kind"] == "json_key":
        rows = doc.get(spec.get("key") or "rows") if isinstance(doc, dict) else None
        return (list(rows) if isinstance(rows, list) else []), ""
    if isinstance(doc, list):
        return doc, ""
    if isinstance(doc, dict):
        for key in ("rows", "items", "queue", "tasks"):
            if isinstance(doc.get(key), list):
                return list(doc[key]), ""
    return [], "no row list found in the document"


def _iter_jsonl_rows(path: Path, cap: int) -> tuple[list[Any], str]:
    try:
        size = path.stat().st_size
    except OSError:
        return [], "absent"
    if size > cap:
        return [], f"file is {size / 1048576:.1f} MB, over the {cap / 1048576:.0f} MB pass budget"
    rows: list[Any] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
                if len(rows) >= MAX_SAMPLE:
                    break
    except OSError as exc:
        return [], f"unreadable: {type(exc).__name__}"
    return rows, ""


def _file_level_age(path: Path, spec: dict[str, Any], now: datetime) -> tuple[float | None, str]:
    """A store whose ROWS carry no timestamp still has a file-level stamp. That is the honest
    granularity, and saying so is the point: it names the fix (stamp the rows)."""
    field = spec.get("file_time_field")
    if not field:
        return None, "rows carry no enqueue timestamp and the file declares none"
    try:
        doc = json.loads(path.read_text("utf-8")) if path.exists() else {}
    except (OSError, ValueError):
        return None, "rows carry no enqueue timestamp and the file could not be read"
    stamp = parse_time(doc.get(field)) if isinstance(doc, dict) else None
    if stamp is None:
        return None, f"rows carry no enqueue timestamp and {field} is absent"
    return round((now - stamp).total_seconds() / 3600.0, 3), (
        f"FILE GRANULARITY ONLY ({field}): no row carries its own enqueue time")


def _dig(doc: dict[str, Any], path: tuple[str, ...]) -> Any:
    cur: Any = doc
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _read_artifact(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _measure_sqlite(spec: dict[str, Any], now: datetime) -> dict[str, Any]:
    table = str(spec["table"])
    status = str(spec.get("status_field") or "status")
    field = str(spec.get("time_field") or "created_at")
    states = tuple(spec.get("open_states") or ())
    if not REGISTRY_DB.exists():
        return {"depth": None, "oldest_age_h": None, "age_measurable": False,
                "why": f"registry {REGISTRY_DB.name} absent: UNMEASURED, not zero"}
    marks = ",".join("?" for _ in states) or "''"
    try:
        with sqlite3.connect(f"file:{REGISTRY_DB}?mode=ro", uri=True, timeout=5.0) as conn:
            row = conn.execute(
                f"SELECT COUNT(*), MIN({field}) FROM {table} "  # noqa: S608 -- names are constants
                f"WHERE {status} IN ({marks})", states).fetchone()
    except sqlite3.Error as exc:
        return {"depth": None, "oldest_age_h": None, "age_measurable": False,
                "why": f"sqlite: {type(exc).__name__}: {exc}"}
    depth = int(row[0] or 0)
    oldest = parse_time(row[1])
    if oldest is None:
        return {"depth": depth, "oldest_age_h": None, "age_measurable": False,
                "why": f"no readable {field} on the open rows"}
    return {"depth": depth, "age_measurable": True,
            "oldest_age_h": round((now - oldest).total_seconds() / 3600.0, 3),
            "oldest_at": oldest.isoformat(timespec="seconds"), "why": ""}


def _measure_artifact(spec: dict[str, Any]) -> dict[str, Any]:
    doc = _read_artifact(spec.get("carry_artifact"))
    if not doc:
        art = spec.get("carry_artifact")
        return {"depth": None, "oldest_age_h": None, "age_measurable": False,
                "why": (f"{Path(art).name if art else 'artifact'} not written yet: UNMEASURED, "
                        f"not zero -- the owning organ has not run")}
    depth_path = spec.get("depth_path") or ((spec["depth_key"],) if spec.get("depth_key") else ())
    age_path = spec.get("age_path") or ((spec["age_key"],) if spec.get("age_key") else ())
    depth_raw = _dig(doc, tuple(depth_path)) if depth_path else None
    age_raw = _dig(doc, tuple(age_path)) if age_path else None
    if isinstance(age_raw, dict):
        for key in ("measured", "hours", "h", "value"):
            if isinstance(age_raw.get(key), (int, float)):
                age_raw = age_raw[key]
                break
    depth = int(depth_raw) if isinstance(depth_raw, (int, float)) else None
    age = float(age_raw) if isinstance(age_raw, (int, float)) else None
    return {"depth": depth, "oldest_age_h": None if age is None else round(age, 3),
            "age_measurable": age is not None,
            "source_artifact": Path(str(spec["carry_artifact"])).name,
            "why": ("" if age is not None else
                    "the owning organ publishes no oldest-row age; depth only")}


def measure(spec: dict[str, Any], cap: int, now: datetime) -> dict[str, Any]:
    """One queue -> depth, oldest-row age and why, without ever raising."""
    kind = str(spec["kind"])
    if kind == "sqlite":
        core = _measure_sqlite(spec, now)
    elif kind == "artifact":
        core = _measure_artifact(spec)
    else:
        path = Path(str(spec["path"]))
        if kind == "jsonl":
            rows, why = _iter_jsonl_rows(path, cap)
        else:
            rows, why = _iter_json_rows(path, spec, cap)
        if why:
            core = {"depth": None, "oldest_age_h": None, "age_measurable": False, "why": why}
        else:
            open_rows = [r for r in rows if isinstance(r, dict) and is_open(r, spec)]
            field = spec.get("time_field")
            stamps = ([parse_time(r.get(field)) for r in open_rows] if field else [])
            live = [s for s in stamps if s is not None]
            if live:
                oldest = min(live)
                core = {"depth": len(open_rows), "age_measurable": True,
                        "oldest_age_h": round((now - oldest).total_seconds() / 3600.0, 3),
                        "oldest_at": oldest.isoformat(timespec="seconds"),
                        "rows_total": len(rows), "rows_stamped": len(live), "why": ""}
            else:
                age, why2 = _file_level_age(path, spec, now)
                core = {"depth": len(open_rows), "oldest_age_h": age, "age_measurable": False,
                        "rows_total": len(rows), "rows_stamped": 0, "why": why2}
    carry = _read_artifact(spec.get("carry_artifact")) if spec.get("carry_keys") else {}
    core.update({
        "id": spec["id"], "kind": kind,
        "store": str(spec.get("path") or spec.get("table") or spec.get("carry_artifact") or ""),
        "writer": spec.get("writer", ""), "drainer": spec.get("drainer"),
        "owner_leg": spec.get("owner_leg"), "cycle_h": float(spec.get("cycle_h") or 1.0),
        "note": spec.get("note", ""),
        "carry": ({k: carry.get(k) for k in spec["carry_keys"] if k in carry}
                  if spec.get("carry_keys") else {}),
    })
    return core


# ------------------------------------------------------------------- drain rate and verdicts


def _history() -> list[dict[str, Any]]:
    if not HISTORY.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with HISTORY.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    doc = json.loads(line)
                except ValueError:
                    continue
                if isinstance(doc, dict):
                    rows.append(doc)
    except OSError:
        return []
    return rows[-MAX_HISTORY:]


def drain_rate(qid: str, depth: int | None, now: datetime,
               history: list[dict[str, Any]]) -> dict[str, Any]:
    """Rows per hour, DIFFERENCED against the previous pass. A measurement, never a claim.

    A negative rate means the queue GREW. `None` means there is no previous pass to difference
    against, which is UNMEASURED and says so rather than reporting a comfortable zero.
    """
    if depth is None:
        return {"rows_per_h": None, "why": "depth unmeasured"}
    for prev in reversed(history):
        depths = prev.get("depths")
        stamp = parse_time(prev.get("at"))
        if not isinstance(depths, dict) or stamp is None or depths.get(qid) is None:
            continue
        hours = (now - stamp).total_seconds() / 3600.0
        if hours <= 0.0:
            continue
        before = depths.get(qid)
        if not isinstance(before, (int, float)):
            continue
        return {"rows_per_h": round((float(before) - float(depth)) / hours, 3),
                "over_h": round(hours, 3), "depth_before": int(before),
                "why": "" if before >= depth else "the queue GREW over this interval"}
    return {"rows_per_h": None, "why": "no previous census to difference against"}


def verdict(row: dict[str, Any]) -> dict[str, Any]:
    """BREACH / PARKED / UNMEASURED / CLEAN for one queue, against the law in `RULE`."""
    cycle = float(row.get("cycle_h") or 1.0)
    depth = row.get("depth")
    age = row.get("oldest_age_h")
    if row.get("drainer") is None and isinstance(depth, (int, float)) and depth > 0:
        return {"state": "PARKED", "why": (
            f"{int(depth)} open rows and NO DRAINER: nothing on the desk's clocks processes "
            f"this queue, so every row in it waits indefinitely")}
    if depth is None:
        return {"state": "UNMEASURED", "why": row.get("why") or "depth could not be measured"}
    if depth == 0:
        return {"state": "CLEAN", "why": "empty: nothing is waiting"}
    if not row.get("age_measurable"):
        return {"state": "UNMEASURED", "why": (
            f"{int(depth)} open rows whose age cannot be measured: "
            f"{row.get('why') or 'no enqueue timestamp'}. Stamp the rows")}
    if isinstance(age, (int, float)) and age > cycle:
        return {"state": "BREACH", "why": (
            f"oldest row is {age:.2f} h old against a {cycle:.2f} h cycle of "
            f"{row.get('owner_leg') or 'its owner'}: it has survived "
            f"{age / cycle:.1f} cycles without being processed")}
    return {"state": "CLEAN", "why": (
        f"{int(depth)} rows, oldest {age} h inside the {cycle} h cycle: this is carry, "
        f"not a park")}


def build(now: datetime | None = None, budget_s: float = BUDGET_S) -> dict[str, Any]:
    stamp = _now(now)
    cap, cap_why = _byte_budget()
    history = _history()
    t0 = time.monotonic()
    rows: list[dict[str, Any]] = []
    skipped: list[str] = []
    for spec in QUEUES:
        if time.monotonic() - t0 > budget_s:
            skipped.append(str(spec["id"]))
            continue
        row = measure(spec, cap, stamp)
        row["drain"] = drain_rate(str(spec["id"]), row.get("depth"), stamp, history)
        row["verdict"] = verdict(row)
        rows.append(row)
    states = {s: [r["id"] for r in rows if r["verdict"]["state"] == s]
              for s in ("BREACH", "PARKED", "UNMEASURED", "CLEAN")}
    total_depth = sum(int(r["depth"]) for r in rows if isinstance(r.get("depth"), (int, float)))
    ages = [float(r["oldest_age_h"]) for r in rows
            if isinstance(r.get("oldest_age_h"), (int, float))]
    doc: dict[str, Any] = {
        "at": stamp.isoformat(timespec="seconds"),
        "rule": RULE,
        "law": "principal's standing order 2026-09-23: keep no queues, all immediate tested",
        "queues": rows,
        "by_state": states,
        "totals": {"queues": len(rows), "rows_waiting": total_depth,
                   "oldest_age_h": max(ages) if ages else None,
                   "queues_without_a_drainer": len(
                       [r for r in rows if r.get("drainer") is None]),
                   "queues_without_a_clock": len(
                       [r for r in rows if not r.get("owner_leg")])},
        "budget": {"bytes_per_file": cap, "why": cap_why, "budget_s": budget_s,
                   "elapsed_s": round(time.monotonic() - t0, 3), "skipped": skipped},
        "consumes": ["CONVERSION_MAXIMISER.json", "GAUNTLET_BACKPRESSURE.json",
                     "COVERAGE_DRAIN.json", "FORWARD_ENROLMENT.json", "QUEUE.json"],
    }
    worst = max(rows, key=lambda r: float(r.get("oldest_age_h") or 0.0), default=None)
    doc["headline"] = (
        f"{len(rows)} queues, {total_depth} rows waiting, "
        f"{len(states['BREACH'])} BREACH / {len(states['PARKED'])} PARKED / "
        f"{len(states['UNMEASURED'])} UNMEASURED; oldest "
        f"{(worst or {}).get('oldest_age_h')} h in {(worst or {}).get('id')}")
    return doc


def append_history(doc: dict[str, Any]) -> None:
    """One line per pass, so the NEXT pass can difference depths into a drain rate."""
    line = {"at": doc["at"],
            "depths": {r["id"]: r.get("depth") for r in doc.get("queues", [])}}
    try:
        HISTORY.parent.mkdir(parents=True, exist_ok=True)
        with HISTORY.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, default=str) + "\n")
    except OSError:
        return
    rows = _history()
    if len(rows) >= MAX_HISTORY:
        try:
            HISTORY.write_text("\n".join(json.dumps(r, default=str) for r in rows) + "\n",
                               "utf-8")
        except OSError:
            return


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--json", action="store_true", help="print the artifact")
    args = ap.parse_args(argv)
    doc = build(budget_s=float(args.budget_s))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    append_history(doc)
    try:
        from libs.ops import events

        events.emit("QUEUE_CENSUS_TAKEN", leg="queue_census",
                    rows_waiting=doc["totals"]["rows_waiting"],
                    breaches=len(doc["by_state"]["BREACH"]),
                    parked=len(doc["by_state"]["PARKED"]))
    except Exception:
        pass
    print(f"queue census: {doc['headline']}")
    if args.json:
        print(json.dumps(doc, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
