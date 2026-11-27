"""THE GUARDIAN SWEEP: an inventory of the whole box, built from the box, with a learned contract
for every item and a coverage number with a floor that only rises.

THE PRINCIPAL'S ASK (zuck 2026-11-25 22:16Z): "never ever miss anything ... box guardian as
advanced as possible knowing every bit of quant ... like it gave birth to it 24/7 noticing".

What the other guardian legs miss. process_health enumerates the scheduler and judges each task
against a hand contract; output_watch judges producers on compute-ledger OK finishes;
backup_watch judges the backup. Each is right about its own slice, and each is blind to anything
nobody put in its slice: a report that quietly stopped refreshing, a ledger that shrank to a
tenth of its size, a task that vanished from the scheduler, a disk filling up, a new producer
that nobody contracted. This leg looks at EVERYTHING it can see and asks two questions of each:

    1. INVENTORY DIFF. What exists now that did not exist last sweep (NEW: covered automatically
       from this sweep on) and what existed and is gone (VANISHED)? A manifest task the scheduler
       does not have is DECLARED_ABSENT; a scheduler task the manifest does not declare is
       UNDECLARED.
    2. LEARNED CONTRACT. For every item: how often does it change, how big is it, how often does
       its run fail. The contract is learned from the item's own history (median change interval
       over its last 20 changes, median size over its last 10), so nobody has to write it and it
       follows the item when the item's cadence changes. Drift flags:
         STALE_DRIFT   unchanged for > max(3x its median interval, 1h) after >= 3 intervals seen
         SHRANK        size < 20% of its median (median > 1 KB); EMPTY when it hits 0 bytes
         RESULT_STREAK the scheduler reports a non-zero result on 3 consecutive distinct runs
         DISK_HIGH / DISK_CRITICAL   a volume past 85% / 92%
       plus every declarative check in desks/mt5/ops/guardian_checks.d/*.json (below).

SAME-DAY CHECKS AS DATA. Every miss the 6h pass or the brain finds becomes a check the same day by
dropping a JSON file into desks/mt5/ops/guardian_checks.d/ -- no code, no review of logic:
    {"id": "e8_cert_book_fresh", "path": "desks/mt5/reports/CERT_BOOK_LIVE.json",
     "max_age_h": 26, "min_bytes": 200, "json_key": "e8", "why": "the 11-25 miss: ..."}
A check whose file is missing, older than max_age_h, smaller than min_bytes, or (json_key set)
not JSON or without that top-level key is CHECK_FAILED:<id>.

COVERAGE. An item is COVERED when it has a contract that can fire: a learned one (>= 3 changes
seen), a STATIC one (unchanged across >= 48h of sweeps: watched for VANISHED/SHRANK), a
declarative check, or (tasks) a process_health contract. Everything else is UNCOVERED, counted
and named, and counts against coverage_pct. The FLOOR ratchets: once a day it becomes
max(floor, the lowest coverage seen in the last 24h), so coverage can only be allowed to rise;
falling below the floor is COVERAGE_BELOW_FLOOR. Published in desks/mt5/reports/
GUARDIAN_COVERAGE.json for the 6h pass's HEADLINE.json.

ACTIONS. This leg pages ("GUARDIAN SWEEP:") on a change of shape or every 6h. It restarts
nothing itself: restarts stay with output_watch's allow-list (research/data lanes only) and
backup_watch, so there is exactly one place that may start a task. No Claude dependency.
"""
from __future__ import annotations

import json
import os
import shutil
import statistics
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from libs.ops import output_watch as ow

SCHEMA = "guardian_sweep/1"
OUT_REL = "desks/mt5/reports/GUARDIAN_SWEEP.json"
COVERAGE_REL = "desks/mt5/reports/GUARDIAN_COVERAGE.json"
STATE_REL = "desks/mt5/data/GUARDIAN_SWEEP_STATE.json"
CHECKS_REL = "desks/mt5/ops/guardian_checks.d"
MANIFEST_REL = ow.MANIFEST_REL
RETIRED_REL = "desks/mt5/ops/retired_tasks.json"
#: The sweep's own outputs change every sweep by construction; watching them is noise.
OWN = frozenset({OUT_REL, COVERAGE_REL, STATE_REL})
#: Where the sweep looks for artifacts, with the depth it descends. A directory holding more than
#: GROUP_OVER files is one item (newest mtime, file count, total bytes): tick tapes and ledger
#: shards are watched as a stream, not as 40 000 items.
SCAN: tuple[tuple[str, int], ...] = (("desks/mt5/reports", 3), ("desks/mt5/data", 2),
                                     ("data", 2), ("reports", 2))
GROUP_OVER = 200
MAX_ITEMS = 20000
NEVER = ("secret",)          # a path component starting with this is never read or listed
SKIP_SUFFIX = (".tmp", ".lock", ".pyc")
HIST = 20
SIZES = 10
MIN_INTERVALS = 3
STALE_MULT = 3.0
STALE_MIN = timedelta(hours=1)
STATIC_AFTER = timedelta(hours=48)
SHRINK_FRAC = 0.2
SHRINK_MIN_MEDIAN = 1024
RESULT_STREAK = 3
DISK_HIGH, DISK_CRITICAL = 85.0, 92.0
REPAGE_EVERY = timedelta(hours=6)
FLOOR_EVERY = timedelta(hours=24)
#: Flags that are information, not faults: they never page alone.
INFO = frozenset({"NEW"})


def _ts(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _read(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def _secretish(rel: str) -> bool:
    return any(part.lower().startswith(NEVER) for part in Path(rel).parts)


# ----------------------------------------------------------------------------------- observe
def scan_artifacts(root: Path, scan: Iterable[tuple[str, int]] = SCAN) -> dict[str, dict[str, Any]]:
    """{item id: {mtime, size[, files]}} for every file (or grouped directory) under `scan`."""
    out: dict[str, dict[str, Any]] = {}

    def walk(d: Path, rel: str, depth: int) -> None:
        if len(out) >= MAX_ITEMS or _secretish(rel):
            return
        try:
            entries = list(os.scandir(d))
        except OSError:
            return
        files = [e for e in entries if e.is_file(follow_symlinks=False)
                 and not e.name.endswith(SKIP_SUFFIX)]
        if len(files) > GROUP_OVER or depth < 0:
            # A stream, judged by the directory's own mtime (NTFS and ext4 both move it when an
            # entry is created, deleted or renamed) and its entry count: no per-file stat, so a
            # 100 000-file tape costs one scandir, not 100 000 stats.
            try:
                dm = d.stat().st_mtime
            except OSError:
                return
            out[f"dir:{rel}"] = {"mtime": dm, "size": len(files), "files": len(files)}
            return
        for f in files:
            if _secretish(f.name) or f"{rel}/{f.name}" in OWN:
                continue
            s = f.stat()
            out[f"file:{rel}/{f.name}"] = {"mtime": s.st_mtime, "size": s.st_size}
        for e in entries:
            if e.is_dir(follow_symlinks=False) and not e.name.startswith((".", "__")):
                walk(Path(e.path), f"{rel}/{e.name}", depth - 1)

    for rel, depth in scan:
        p = root / rel
        if p.is_dir():
            walk(p, rel, depth)
    return out


def disks(probe: Callable[[str], Any] = shutil.disk_usage,
          drives: Iterable[str] | None = None) -> dict[str, float]:
    """{volume: used %} for every volume that answers."""
    if drives is None:
        drives = [f"{c}:\\" for c in "CDEFGH"] if os.name == "nt" else ["/"]
    out = {}
    for d in drives:
        try:
            u = probe(d)
        except OSError:
            continue
        if u.total:
            out[d] = round(100.0 * u.used / u.total, 1)
    return out


def load_checks(root: Path) -> list[dict[str, Any]]:
    out = []
    d = root / CHECKS_REL
    for p in sorted(d.glob("*.json")) if d.is_dir() else []:
        c = _read(p)
        if c.get("id") and c.get("path"):
            out.append(c)
    return out


def run_check(root: Path, c: Mapping[str, Any], now: datetime) -> str | None:
    """None when the check holds, else why it failed. Never reads a secrets path."""
    rel = str(c["path"])
    if _secretish(rel):
        return "refused: a secrets path"
    p = root / rel
    try:
        p.resolve().relative_to(root.resolve())
    except ValueError:
        return "refused: outside the repository"
    try:
        st = p.stat()
    except OSError:
        return "missing"
    age_h = (now.timestamp() - st.st_mtime) / 3600
    if c.get("max_age_h") is not None and age_h > float(c["max_age_h"]):
        return f"{age_h:.1f}h old > {c['max_age_h']}h"
    if c.get("min_bytes") is not None and st.st_size < int(c["min_bytes"]):
        return f"{st.st_size} bytes < {c['min_bytes']}"
    if c.get("json_key"):
        d = _read(p)
        if str(c["json_key"]) not in d:
            return f"no key {c['json_key']!r}"
    return None


# ------------------------------------------------------------------------------------- learn
def learn(item: dict[str, Any], obs: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    """Fold one observation into an item's learned model. Pure (returns the new model)."""
    m = dict(item)
    mt = obs.get("mtime")
    if mt is not None:
        if m.get("mtime") is not None and float(mt) > float(m["mtime"]):
            m["intervals"] = ([*m.get("intervals", []), float(mt) - float(m["mtime"])])[-HIST:]
            m["changed_at"] = now.isoformat()
        m["mtime"] = float(mt)
    if obs.get("size") is not None:
        m["sizes"] = ([*m.get("sizes", []), int(obs["size"])])[-SIZES:]
        m["size"] = int(obs["size"])
    m.setdefault("first_seen", now.isoformat())
    m["last_seen"] = now.isoformat()
    return m


def drift(m: Mapping[str, Any], now: datetime) -> tuple[list[str], str]:
    """(flags, contract kind) for one learned artifact model. Pure."""
    flags: list[str] = []
    iv = m.get("intervals") or []
    kind = "LEARNING"
    if len(iv) >= MIN_INTERVALS:
        kind = "LEARNED"
        med = statistics.median(iv)
        allowed = max(STALE_MULT * med, STALE_MIN.total_seconds())
        if m.get("mtime") is not None and now.timestamp() - float(m["mtime"]) > allowed:
            flags.append("STALE_DRIFT")
    else:
        since = _ts(m.get("changed_at")) or _ts(m.get("first_seen"))
        if since is not None and now - since >= STATIC_AFTER:
            kind = "STATIC"
    sizes = m.get("sizes") or []
    if len(sizes) >= 3:
        med_s = statistics.median(sizes[:-1])
        cur = sizes[-1]
        if med_s > SHRINK_MIN_MEDIAN and cur == 0:
            flags.append("EMPTY")
        elif med_s > SHRINK_MIN_MEDIAN and cur < SHRINK_FRAC * med_s:
            flags.append("SHRANK")
    return flags, kind


def task_items(health: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out = {}
    for p in health.get("processes") or []:
        if isinstance(p, dict) and p.get("name") and p.get("state") != "COMPONENT":
            out[f"task:{p['name']}"] = p
    return out


def result_streak(m: dict[str, Any], p: Mapping[str, Any]) -> dict[str, Any]:
    """Track consecutive distinct runs with a non-zero result. Pure."""
    m = dict(m)
    run, code = str(p.get("last_run") or ""), p.get("last_result_code")
    if run and run != m.get("last_run"):
        m["last_run"] = run
        m["bad_runs"] = (int(m.get("bad_runs", 0)) + 1) if code not in (0, None) else 0
    return m


# -------------------------------------------------------------------------------------- sweep
def run_once(root: Path, *, now: datetime | None = None,
             page: Callable[[str], None] | None = None,
             disk_probe: Callable[[str], Any] = shutil.disk_usage,
             drives: Iterable[str] | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    st_path = root / STATE_REL
    state = _read(st_path)
    raw_items = state.get("items")
    models: dict[str, dict[str, Any]] = raw_items if isinstance(raw_items, dict) else {}
    first_sweep = not models
    seen = scan_artifacts(root)
    health = _read(root / ow.HEALTH_REL)
    tasks = task_items(health)
    try:
        declared = ow.manifest_lanes((root / MANIFEST_REL).read_text(encoding="utf-8",
                                                                      errors="replace"))
    except OSError:
        declared = {}
    retired = {str(r.get("task")) for r in (_read(root / RETIRED_REL).get("retired") or [])
               if isinstance(r, dict)}

    findings: dict[str, list[str]] = {}
    coverage: dict[str, str] = {}

    def flag(item: str, f: str) -> None:
        findings.setdefault(item, []).append(f)

    # artifacts: diff + learned contract
    for iid, obs in seen.items():
        if iid not in models and not first_sweep:
            flag(iid, "NEW")
        models[iid] = learn(models.get(iid, {}), obs, now)
        fl, kind = drift(models[iid], now)
        for f in fl:
            flag(iid, f)
        coverage[iid] = kind
    grouped = tuple(i[4:] + "/" for i in seen if i.startswith("dir:"))
    for iid in [i for i in models if i.startswith(("file:", "dir:")) and i not in seen]:
        if iid.startswith("file:") and iid[5:].startswith(grouped):
            models.pop(iid)   # now watched as part of its directory's stream, not gone
            continue
        flag(iid, "VANISHED")
        coverage[iid] = "VANISHED"
        models.pop(iid)

    # tasks: scheduler vs manifest, result streaks, contract from process_health
    raw_tasks = state.get("tasks")
    tmodels: dict[str, dict[str, Any]] = raw_tasks if isinstance(raw_tasks, dict) else {}
    if tasks:
        for iid, p in tasks.items():
            name = iid[5:]
            if iid not in tmodels and tmodels:
                flag(iid, "NEW")
            tmodels[iid] = result_streak(tmodels.get(iid, {}), p)
            if int(tmodels[iid].get("bad_runs", 0)) >= RESULT_STREAK:
                flag(iid, "RESULT_STREAK")
            if declared and name not in declared and name.startswith(("MT5-", "Quant")):
                flag(iid, "UNDECLARED")
            contracted = str(p.get("verdict") or "") not in ("UNCONTRACTED", "")
            coverage[iid] = "CONTRACTED" if contracted else "UNCONTRACTED"
        for iid in [i for i in tmodels if i not in tasks]:
            flag(iid, "VANISHED")
            tmodels.pop(iid)
        for name in declared:
            if f"task:{name}" not in tasks and name not in retired:
                flag(f"task:{name}", "DECLARED_ABSENT")
                coverage[f"task:{name}"] = "ABSENT"
    else:
        flag("process_health", "NO_TASK_VIEW")

    # disks
    for d, pct in disks(disk_probe, drives).items():
        iid = f"disk:{d}"
        coverage[iid] = "LEARNED"
        if pct >= DISK_CRITICAL:
            flag(iid, "DISK_CRITICAL")
        elif pct >= DISK_HIGH:
            flag(iid, "DISK_HIGH")

    # declarative same-day checks
    for c in load_checks(root):
        iid = f"check:{c['id']}"
        coverage[iid] = "CHECK"
        why = run_check(root, c, now)
        if why:
            flag(iid, f"CHECK_FAILED({why})")

    covered = sum(1 for k in coverage.values()
                  if k in ("LEARNED", "STATIC", "CONTRACTED", "CHECK"))
    total = sum(1 for k in coverage.values() if k != "VANISHED")
    pct = round(100.0 * covered / total, 2) if total else 0.0
    uncovered = sorted(i for i, k in coverage.items() if k in ("LEARNING", "UNCONTRACTED",
                                                               "ABSENT"))
    # ratcheting floor: once a day, floor := max(floor, min coverage seen since last raise)
    floor = float(state.get("floor") or 0.0)
    lows = [*(state.get("lows") or []), pct][-200:]
    raised_at = _ts(state.get("floor_raised_at"))
    if raised_at is None:
        state["floor_raised_at"] = now.isoformat()
    elif now - raised_at >= FLOOR_EVERY:
        floor = max(floor, min(lows))
        lows, state["floor_raised_at"] = [pct], now.isoformat()
    if floor and pct < floor:
        flag("coverage", "COVERAGE_BELOW_FLOOR")

    faults = {i: f for i, f in findings.items() if any(x not in INFO for x in f)}
    by_flag: dict[str, int] = {}
    for fl in faults.values():
        for x in fl:
            if x not in INFO:
                key = x.split("(")[0]
                by_flag[key] = by_flag.get(key, 0) + 1
    doc = {"schema": SCHEMA, "at": now.isoformat(), "items": total, "covered": covered,
           "coverage_pct": pct, "floor_pct": floor, "uncovered_n": len(uncovered),
           "uncovered": uncovered[:500], "faults_n": len(faults), "by_flag": by_flag,
           "faults": dict(sorted(faults.items())[:1000]),
           "new": sorted(i for i, f in findings.items() if "NEW" in f)[:500],
           "first_sweep": first_sweep}
    cov = {"schema": "guardian_coverage/1", "at": now.isoformat(), "coverage_pct": pct,
           "floor_pct": floor, "items": total, "covered": covered,
           "uncovered_n": len(uncovered), "faults_n": len(faults), "by_flag": by_flag,
           "below_floor": bool(floor and pct < floor)}

    key = "|".join(sorted(by_flag))
    paged_at = _ts(state.get("paged_at"))
    if faults and page is not None and not first_sweep and (
            key != state.get("paged_key") or paged_at is None or now - paged_at > REPAGE_EVERY):
        top = "; ".join(f"{i}: {','.join(f)}" for i, f in sorted(faults.items())[:8])
        page(f"GUARDIAN SWEEP: {len(faults)} item(s) drifting or missing "
             f"({', '.join(f'{k} {v}' for k, v in sorted(by_flag.items()))}); coverage {pct}% "
             f"(floor {floor}%), {len(uncovered)} uncovered. {top}. Detail: {OUT_REL}")
        state["paged_at"], state["paged_key"] = now.isoformat(), key

    state.update(items=models, tasks=tmodels, floor=floor, lows=lows)
    for dest, body in ((root / OUT_REL, doc), (root / COVERAGE_REL, cov), (st_path, state)):
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        tmp.write_text(json.dumps(body, indent=1, sort_keys=True, default=str), encoding="utf-8")
        tmp.replace(dest)
    return doc
