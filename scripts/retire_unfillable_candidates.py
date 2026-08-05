#!/usr/bin/env python3
"""One-shot §42 retirement: bank + archive every scored candidate the live book cannot fill.

WHY (max_audit 2026-08-05): `capacity-hunt-unfillable` and `capacity-already-outgrown` both fired
on the same 1051 of 1799 scored candidates -- measured capacities the live book cannot absorb the
required headroom for at all ("the desk would BE the edge") and growth runways below 1x (already
outgrown). The audit's prescription is executed literally: "retire them and bank the mechanism,
do not keep ranking them."

WHAT IT DOES, per candidate whose band is UNFILLABLE or whose growth_runway < 1.0 at today's live
book (both judged by THE capacity policy, libs/research/capacity_policy -- imported, never
inlined, declared allocations honoured exactly as check_capacity_hunt honours them):

  1. append the FULL mechanism record to data/capacity_retired_bank.jsonl (L1.17: research debt,
     preserved forever, with a named L1.16a resurrection condition). NOTE the store never
     persisted `edge_source`/`failure_modes`, so those fields are empty for these legacy rows --
     family/subtype/symbol/params/mechanism/metrics are the complete stored mechanism.
  2. mark it retired in the store via the store's OWN API: `CandidateStore.retire(id)`, i.e.
     UPDATE research_candidates SET status='archived', updated_at=? WHERE id=?. The table is
     append-only with a no-delete trigger (migrations/m0005) and the API had no delete/status
     operation at all, so `retire` was ADDED to the API for this -- a status transition is the
     one mutation the migration sanctions. Metrics, original rejection_reason and `survived`
     stay untouched: dedup, trial counts and family deflation priors still see the row.

SAFETY:
  * guard() at the top of main() -- refuses to act if the law boundary fails.
  * refuses if the DB is absent (never creates one) and refuses -- after a brief retry -- while
    a live writer holds the DB (fuser on the db/-wal files + a ps scan for the factory entry
    points; there is NO flock convention around this DB -- the factory cron lines run bare --
    so process inspection is the only pre-check available, and sqlite's busy_timeout=5000 plus
    per-row transactions are the backstop if a writer starts mid-run).
  * idempotent: re-runs walk only non-retired rows (default `all()` excludes archived) and
    skip bank appends for ids already banked, so a crash between bank and mark cannot
    double-bank and cannot lose a mechanism (bank-first ordering).
  * --dry-run reports every count and writes nothing.

Usage:
    .venv/bin/python scripts/retire_unfillable_candidates.py --dry-run
    .venv/bin/python scripts/retire_unfillable_candidates.py
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

_DB = _ROOT / "data/sor_research.sqlite"

#: Every entry point that writes this store (single writer: CandidateStore.record, called only by
#: the orchestrator; these are the scripts that construct it). Matched with a `.venv/bin/python`
#: prefix so a sibling Claude session whose prompt merely MENTIONS these names cannot self-match
#: (the pgrep -f trap, desk memory 2026-08-04).
_WRITER_SCRIPTS = ("run_autodiscovery.py", "run_research_tick.py", "run_worker.py",
                   "run_supervisor.py", "daily_research_cycle.py", "smoke_orchestration.py")
_BUSY_RETRIES = 5
_BUSY_WAIT_S = 3.0


def _live_writers(db: Path) -> tuple[list[str], list[str]]:
    """(writer evidence, probe failures) -- both returned, because they mean opposite things.

    NO SILENT SWALLOW (L2.4). An unavailable probe is NOT an idle store: swallowing the failure
    would turn "I could not look" into "nothing is there", which is exactly the reading that lets
    this script retire rows underneath a live factory writer. Both probes report their own failure
    and the caller REFUSES when every probe failed (UNMEASURED counts as unsafe, never as safe).
    """
    hits: list[str] = []
    probe_failures: list[str] = []
    fuser_ran = False
    for f in (db, Path(str(db) + "-wal")):
        if not f.exists():
            continue
        try:
            r = subprocess.run(["fuser", str(f)], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired) as exc:
            probe_failures.append(f"fuser({f.name}) unavailable: {exc!r}")
            continue
        fuser_ran = True
        # rc 1 = "no process holds it" (a real measurement); only rc>1 is a probe malfunction.
        if r.returncode > 1:
            probe_failures.append(f"fuser({f.name}) rc={r.returncode}: {r.stderr.strip()[:80]}")
        elif r.returncode == 0 and r.stdout.strip():
            hits.append(f"fuser: {f.name} held by pid(s) {r.stdout.strip()}")
    try:
        r = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        probe_failures.append(f"ps scan unavailable: {exc!r}")
    else:
        if r.returncode != 0:
            probe_failures.append(f"ps scan rc={r.returncode}: {r.stderr.strip()[:80]}")
        else:
            fuser_ran = True          # at least one probe delivered a real measurement
            for line in r.stdout.splitlines():
                if "python" not in line:
                    continue  # a real interpreter cmdline, not a prompt that names a script
                for s in _WRITER_SCRIPTS:
                    if f"scripts/{s}" in line:
                        hits.append(f"ps: {line.strip()[:120]}")
    if not fuser_ran:
        probe_failures.append("NO probe delivered a measurement -- idleness is UNMEASURED")
    return hits, probe_failures


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", type=Path, default=_DB)
    ap.add_argument("--bank", type=Path, default=None,
                    help="retirement bank path (default: data/capacity_retired_bank.jsonl)")
    ap.add_argument("--dry-run", action="store_true", help="report counts; write nothing")
    a = ap.parse_args()

    from libs.ops.lawful import guard
    g = guard()
    if not g.ok:
        print(f"REFUSED (law guard): {'; '.join(g.failures)}", file=sys.stderr)
        return 3

    if not a.db.exists():
        # Never create the DB: a writable Database() would happily make an empty one and this
        # script would then "succeed" at retiring nothing on the wrong box.
        print(f"REFUSED: {a.db} absent -- not the research box, nothing to retire.",
              file=sys.stderr)
        return 2

    writers, probe_failures = _live_writers(a.db)
    for attempt in range(_BUSY_RETRIES):
        if not writers:
            break
        print(f"store busy (attempt {attempt + 1}/{_BUSY_RETRIES}): {writers[0]} -- "
              f"waiting {_BUSY_WAIT_S:.0f}s", file=sys.stderr)
        time.sleep(_BUSY_WAIT_S)
        writers, probe_failures = _live_writers(a.db)
    if writers:
        print("REFUSED: live writer still holds the store; retiring under it risks corruption. "
              "Re-run when the factory is idle. Evidence: " + "; ".join(writers[:3]),
              file=sys.stderr)
        return 4
    if probe_failures and not a.dry_run:
        # UNMEASURED IS NOT IDLE. Every probe failing means we never established the store is
        # unheld; proceeding would mutate rows under a possible live writer on the strength of a
        # measurement that did not happen. --dry-run writes nothing, so it may proceed and say so.
        print("REFUSED: could not establish the store is idle -- " + "; ".join(probe_failures[:3])
              + ". Re-run where the probes work, or use --dry-run to report without writing.",
              file=sys.stderr)
        return 4
    if probe_failures:
        print(f"WARNING (dry-run, writes nothing): idleness UNMEASURED -- {probe_failures[0]}",
              file=sys.stderr)

    from libs.autodiscovery.capacity_screen import (
        BANK_PATH,
        bank_append,
        banked_ids,
        build_bank_record,
    )
    from libs.autodiscovery.memory import CandidateStore
    from libs.research.capacity_policy import (
        capacity_band,
        growth_runway,
        live_book_usd,
        live_sleeves,
    )
    from libs.store.connection import Database

    bank = a.bank if a.bank is not None else BANK_PATH
    already_banked = banked_ids(bank)
    book, sleeves = live_book_usd(), live_sleeves()
    print(f"live book ${book:,.2f} across {sleeves} sleeves; bank={bank}")

    counts = {"walked": 0, "kept_fillable": 0, "kept_unknown_capacity": 0,
              "retired_unfillable": 0, "retired_already_outgrown": 0,
              "bank_appends": 0, "bank_skipped_already_banked": 0}
    try:
        with Database(a.db, read_only=a.dry_run) as db:
            store = CandidateStore(db)
            # Default all() excludes archived rows, which is exactly the idempotency this walk
            # needs: a re-run never re-banks or re-marks what a prior run already retired.
            for rec in store.all():
                counts["walked"] += 1
                cap = float(rec.metrics.capacity_usd or 0.0)
                if cap <= 0.0:
                    counts["kept_unknown_capacity"] += 1   # unknown is not unfillable (R0080)
                    continue
                # Same band call as max_audit.check_capacity_hunt: sleeve=subtype resolves the
                # declared allocation identically to allocation_usd=declared_allocation(name).
                band = capacity_band(cap, book, sleeves, sleeve=rec.subtype)
                runway = growth_runway(cap, book, sleeves)
                if band == "UNFILLABLE":
                    reason = "unfillable"
                elif runway < 1.0:
                    reason = "already-outgrown"
                else:
                    counts["kept_fillable"] += 1
                    continue
                counts[f"retired_{reason.replace('-', '_')}"] = \
                    counts.get(f"retired_{reason.replace('-', '_')}", 0) + 1
                if a.dry_run:
                    continue
                if rec.id in already_banked:
                    counts["bank_skipped_already_banked"] += 1
                else:
                    bank_append(build_bank_record(
                        candidate_id=rec.id, family=rec.family, subtype=rec.subtype,
                        symbol=rec.symbol, params=dict(rec.params),
                        content_hash=rec.content_hash, mechanism=rec.mechanism,
                        capacity_usd=cap, book_usd=book, n_sleeves=sleeves,
                        metrics=rec.metrics.model_dump(), campaign_id=rec.campaign_id,
                        status_at_retirement=rec.status.value, survived=rec.survived,
                        rejection_reason=rec.rejection_reason, reason=reason,
                    ), bank=bank)
                    counts["bank_appends"] += 1
                # Bank FIRST, then mark: a crash here leaves a banked-but-live row, which the
                # next run detects (id already banked) and finishes -- never a lost mechanism.
                if not store.retire(rec.id):
                    print(f"WARNING: retire({rec.id}) changed no row", file=sys.stderr)
    except sqlite3.OperationalError as exc:
        print(f"REFUSED mid-run (store locked/busy: {exc}). Partial progress is safe -- the "
              f"walk is idempotent; re-run when the factory is idle. Counts so far: "
              f"{json.dumps(counts)}", file=sys.stderr)
        return 4

    mode = "DRY-RUN (nothing written)" if a.dry_run else \
        "store op: CandidateStore.retire -> UPDATE research_candidates SET status='archived'"
    print(json.dumps({"mode": mode, **counts}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
