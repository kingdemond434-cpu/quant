"""THE PRODUCER HEARTBEAT: every producer has a NAMED status, every hour, and nothing is UNMEASURED.

WHY THIS EXISTS (2026-11-25 producer census, `LAB_STATUS.json`): of 202 labs, factories, miners
and generators, 57 read UNMEASURED -- not dead, not alive, simply unprovable -- and 58 more were
STALE. Most of the 57 were organs that were RUNNING: residents whose task reports "still running"
(0x800710E0), box tasks with no artifact contract, and box tasks whose artifact is real but never
leaves the box, so no off-box reader can see a timestamp in it. "Running" and "producing" are
different facts, and the desk had a record of neither in one place.

THREE SOURCES OF PROOF, ONE PUBLISHED SUMMARY.

  1. LEG RUNS. Every hourly leg already passes `hourly_cycle._costed`; that boundary now appends
     one row per run to `desks/mt5/data/producer_heartbeat.jsonl` -- start, end, status
     (ok / timeout / error / silent_no_op / skipped_no_input), rows_out and artifacts_moved. The
     write-or-explain ledger, which predates this, is read as history so the summary is
     populated from the first pass on a box that already has months of it.
  2. CONTRACTED BOX TASKS. `ops/organ_contract.CONTRACTS` names each task's artifact and max age;
     the summary stats each one ON THE BOX (internal stamp where declared, else mtime) and carries
     the stamp and a row count off-box inside this one file -- so a task whose artifact never
     leaves the box is still provable from anywhere. A manifest task with no contract is listed
     NO_CONTRACT by name rather than omitted.
  3. INTELLIGENCE SEATS. `data/intelligence/<seat>/` (both roots): last write and rows in the
     window, so a seat that went quiet is STALE or DEAD with the hour it stopped.

THE STATUS VOCABULARY IS CLOSED: OK, STALE, DEAD, ERROR, TIMEOUT, SILENT, NO_INPUT, RETIRED,
NO_CONTRACT. Every producer gets exactly one, with the evidence that decided it. There is no
UNMEASURED: no proof is itself a named status (DEAD or NO_CONTRACT), which is what the order
"nothing is ever UNMEASURED again" means in practice.

    python -m libs.ops.producer_heartbeat            # build and publish the summary
    python -m libs.ops.producer_heartbeat --print    # and print the non-OK rows

NEVER FAILS A LEG. Every entry point is total; the cycle treats telemetry the way it treats the
compute ledger and the event log -- an organ that dies because its heartbeat failed is worse than
one that runs without one.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import socket
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"

#: The append-only run ledger (state path: the box keeps its own copy).
LEDGER = Path(os.environ.get("PRODUCER_HEARTBEAT_LEDGER")
              or (DESK / "data" / "producer_heartbeat.jsonl"))
#: The published per-producer summary, carried off-box by sync_shadow_to_git $reportPaths.
ARTIFACT = DESK / "reports" / "PRODUCER_HEARTBEAT.json"
#: History the summary reads before this ledger existed.
WOE_LEDGER = Path(os.environ.get("WRITE_OR_EXPLAIN_LEDGER")
                  or (DESK / "data" / "write_or_explain.jsonl"))
MANIFEST = DESK / "ops" / "box_tasks.manifest"
SEAT_ROOTS = (DESK / "data" / "intelligence", ROOT / "data" / "intelligence")

#: The heartbeat window: a producer that has not produced inside it is not OK.
WINDOW_H = 24.0
#: Beyond this with nothing at all, a producer is DEAD rather than STALE.
DEAD_AFTER_H = 72.0
#: Bytes read from the tail of each ledger. A year of rows costs the reader nothing.
TAIL_BYTES = 16 * 1024 * 1024
#: Bytes counted per seat when tallying rows in the window; beyond it the count is extrapolated
#: from the bytes already read (and says so), so one huge seat cannot stall the summary.
SEAT_COUNT_BYTES = 32 * 1024 * 1024
#: Artifacts larger than this are stamped by mtime only, never parsed.
MAX_PARSE_BYTES = 24 * 1024 * 1024
#: How stale the published summary may get before a leg boundary rebuilds it.
PUBLISH_EVERY_S = 900

OK, STALE, DEAD = "OK", "STALE", "DEAD"
ERROR, TIMEOUT, SILENT, NO_INPUT = "ERROR", "TIMEOUT", "SILENT", "NO_INPUT"
RETIRED, NO_CONTRACT = "RETIRED", "NO_CONTRACT"
STATUSES = (OK, STALE, DEAD, ERROR, TIMEOUT, SILENT, NO_INPUT, RETIRED, NO_CONTRACT)

#: Leg-run statuses written to the ledger (the harness's own words, lower case).
RUN_OK, RUN_TIMEOUT, RUN_ERROR = "ok", "timeout", "error"
RUN_SILENT, RUN_NO_INPUT, RUN_SKIPPED = "silent_no_op", "skipped_no_input", "skipped"

#: write-or-explain verdict -> run status.
_WOE_TO_RUN = {"OK": RUN_OK, "UNDECLARED": RUN_OK, "DECLARED_NO_OP": RUN_NO_INPUT,
               "SILENT_NO_OP": RUN_SILENT, "LEG_FAILED": RUN_ERROR, "LEG_TIMEOUT": RUN_TIMEOUT,
               "SKIPPED": RUN_SKIPPED, "NEVER_OBSERVED": RUN_ERROR}

#: The line a producer prints LAST to declare how many rows it emitted. The harness keeps the last
#: 300 characters of stdout, so it must be the final line.
ROWS_MARKER = "PRODUCER_ROWS_OUT"
_ROWS_RE = re.compile(rf"{ROWS_MARKER}\s*[:=]\s*(\d+)")
#: Result-dict keys an in-process leg may use for its row count, in order of preference.
_ROWS_KEYS = ("rows_out", "donated_rows", "n_donated", "donated", "cells_proposed", "n_rows",
              "rows_written", "cells_out", "n_cells", "candidates_out", "proposals")

_TS_KEYS = ("generated_utc", "generated_at", "generated", "at", "updated_at", "measured_at",
            "built_at", "checked_at", "swept_at", "heartbeat_utc", "last_decided_utc",
            "last_tick_utc", "ts", "saved_utc", "compiled_at")


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") if dt else None


def _parse_ts(raw: Any) -> datetime | None:
    if raw is None:
        return None
    try:
        if isinstance(raw, int | float) and not isinstance(raw, bool):
            return datetime.fromtimestamp(float(raw), UTC)
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError, OSError, OverflowError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _age_h(dt: datetime | None, now: datetime) -> float | None:
    return None if dt is None else (now - dt).total_seconds() / 3600.0


# ------------------------------------------------------------------------------- the writer
def report_rows(n: int, stream: Any = None) -> None:
    """Print the rows-out marker. Call it as the LAST line a subprocess producer prints."""
    with contextlib.suppress(TypeError, ValueError, OSError):
        print(f"{ROWS_MARKER}: {int(n)}", file=stream or sys.stdout, flush=True)


def rows_out(result: object) -> int | None:
    """The row count a leg declared, from its result dict or its stdout marker; None if none."""
    if not isinstance(result, dict):
        return None
    for key in _ROWS_KEYS:
        val = result.get(key)
        if isinstance(val, bool):
            continue
        if isinstance(val, int) and val >= 0:
            return val
        if isinstance(val, list):
            return len(val)
    for field in ("tail", "stdout_tail", "stderr_tail"):
        blob = result.get(field)
        if isinstance(blob, str):
            hits = _ROWS_RE.findall(blob)
            if hits:
                return int(hits[-1])
    return None


def run_status(woe_verdict: Any, result: object = None) -> str:
    """The run's status in the heartbeat's words. A result the contract never saw is judged
    from the result itself, so a missing contract row still yields a named status."""
    got = _WOE_TO_RUN.get(str(woe_verdict or "").upper())
    if got:
        return got
    if isinstance(result, dict):
        status = str(result.get("status") or "").upper()
        if status in {"SKIPPED_BY_PLAN", "ROTATED_OUT", "SKIPPED"}:
            return RUN_SKIPPED
        if result.get("error") or status in {"LEG_FAILED", "MISSING", "ERROR", "FAILED"}:
            return RUN_ERROR
        if result.get("timeout_s") and result.get("exit_code") is None:
            return RUN_TIMEOUT
        if result.get("exit_code") not in (None, 0):
            return RUN_ERROR
    return RUN_OK


def record(row: dict[str, Any], *, ledger: Path | None = None) -> bool:
    """Append one run row. O_APPEND, one line. Never raises; never writes under a test unless
    the test names a ledger (R0748: the suite never writes desk state)."""
    if ledger is None and os.environ.get("PYTEST_CURRENT_TEST") \
            and not os.environ.get("PRODUCER_HEARTBEAT_LEDGER"):
        return False
    path = ledger or LEDGER
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str, ensure_ascii=False) + "\n")
        return True
    except (OSError, TypeError, ValueError):
        return False


def beat(leg: str, *, started: datetime | None, result: object,
         woe: dict[str, Any] | None = None, ledger: Path | None = None,
         publish: bool = True) -> dict[str, Any]:
    """Record one leg run and (throttled) republish the summary. Total: returns the row."""
    try:
        ended = _now()
        woe = woe or {}
        status = run_status(woe.get("verdict"), result)
        moved = woe.get("wrote")
        row = {"producer": leg, "kind": "leg", "started_at": _iso(started),
               "ended_at": _iso(ended),
               "wall_s": (round((ended - started).total_seconds(), 3) if started else None),
               "status": status, "rows_out": rows_out(result),
               "artifacts_moved": len(moved) if isinstance(moved, list) else None,
               "exit_code": result.get("exit_code") if isinstance(result, dict) else None,
               "contract_verdict": woe.get("verdict"), "host": socket.gethostname()}
        if status == RUN_NO_INPUT and woe.get("reason"):
            row["reason"] = str(woe.get("reason"))[:200]
    except Exception as exc:                                  # telemetry never fails a leg
        return {"producer": leg, "status": RUN_ERROR, "recorded": False,
                "why": f"{type(exc).__name__}: {exc}"[:200]}
    row["recorded"] = record(row, ledger=ledger)
    if publish:
        maybe_publish()
    return row


# ------------------------------------------------------------------------------- the readers
def _tail_rows(path: Path, tail_bytes: int = TAIL_BYTES) -> list[dict[str, Any]]:
    try:
        size = path.stat().st_size
        with open(path, "rb") as fh:
            if size > tail_bytes:
                fh.seek(size - tail_bytes)
                fh.readline()                                 # drop the partial first line
            blob = fh.read()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in blob.decode("utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def leg_runs(*, ledger: Path | None = None, woe_ledger: Path | None = None
             ) -> list[dict[str, Any]]:
    """Every run row, heartbeat ledger first-class, write-or-explain history as backfill."""
    runs: list[dict[str, Any]] = []
    for row in _tail_rows(woe_ledger or WOE_LEDGER):
        leg = str(row.get("leg") or "")
        if not leg:
            continue
        wrote = row.get("wrote")
        runs.append({"producer": leg, "kind": "leg", "ended_at": row.get("at"),
                     "status": run_status(row.get("verdict")),
                     "artifacts_moved": len(wrote) if isinstance(wrote, list) else None,
                     "rows_out": None, "from": "write_or_explain"})
    for row in _tail_rows(ledger or LEDGER):
        if row.get("producer"):
            runs.append({**row, "from": "producer_heartbeat"})
    return runs


def judge_leg(runs: list[dict[str, Any]], now: datetime, *, window_h: float = WINDOW_H,
              dead_after_h: float = DEAD_AFTER_H) -> dict[str, Any]:
    """One leg's status from its runs. Skipped runs (plan, rotation) decide nothing."""
    real = [r for r in runs if r.get("status") != RUN_SKIPPED]
    stamped = [(_parse_ts(r.get("ended_at")), r) for r in real]
    ts: list[tuple[datetime, dict[str, Any]]] = [(t, r) for t, r in stamped if t is not None]
    ts.sort(key=lambda tr: tr[0])
    win = [(t, r) for t, r in ts if (_age_h(t, now) or 0.0) <= window_h]
    oks = [(t, r) for t, r in win if r.get("status") == RUN_OK]
    last_ok = max((t for t, r in ts if r.get("status") == RUN_OK), default=None)
    last = ts[-1] if ts else None
    rows = [r.get("rows_out") for _t, r in win if isinstance(r.get("rows_out"), int)]
    moved = [r.get("artifacts_moved") for _t, r in win
             if isinstance(r.get("artifacts_moved"), int)]
    rec: dict[str, Any] = {
        "runs_window": len(win), "ok_window": len(oks),
        "rows_out_window": sum(rows) if rows else None,
        "artifacts_moved_window": sum(moved) if moved else None,
        "last_run_at": _iso(last[0]) if last else None,
        "last_run_status": last[1].get("status") if last else None,
        "last_ok_at": _iso(last_ok),
    }
    if oks:
        rec.update(status=OK, why=f"{len(oks)} ok run(s) of {len(win)} in {window_h:g} h")
    elif win:
        latest = win[-1][1].get("status")
        status = {RUN_TIMEOUT: TIMEOUT, RUN_ERROR: ERROR, RUN_SILENT: SILENT,
                  RUN_NO_INPUT: NO_INPUT}.get(str(latest), ERROR)
        counts = Counter(str(r.get("status")) for _t, r in win)
        rec.update(status=status, why=f"no ok run in {window_h:g} h; {dict(counts)}")
    elif last and (_age_h(last[0], now) or 0.0) <= dead_after_h:
        rec.update(status=STALE, why=f"last run {rec['last_run_at']} is older than "
                                     f"{window_h:g} h")
    else:
        rec.update(status=DEAD, why=(f"no run in {dead_after_h:g} h (last {rec['last_run_at']})"
                                     if last else "no run on record on this host"))
    return rec


def _artifact_facts(path: Path) -> dict[str, Any]:
    """mtime, an in-content stamp and a row count where the artifact is small enough to read."""
    out: dict[str, Any] = {"exists": False}
    try:
        st = path.stat()
    except OSError:
        return out
    out.update(exists=True, mtime=_iso(datetime.fromtimestamp(st.st_mtime, UTC)),
               bytes=st.st_size)
    if st.st_size > MAX_PARSE_BYTES:
        return out
    try:
        if path.suffix == ".jsonl":
            with open(path, "rb") as fh:
                out["rows"] = sum(1 for line in fh if line.strip())
            return out
        if path.suffix != ".json":
            return out
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return out
    if isinstance(doc, list):
        out["rows"] = len(doc)
    elif isinstance(doc, dict):
        for k in _TS_KEYS:
            t = _parse_ts(doc.get(k))
            if t is not None:
                out["content_ts"], out["content_key"] = _iso(t), k
                break
        lists = [len(v) for v in doc.values() if isinstance(v, list | dict)]
        if lists:
            out["rows"] = max(lists)
    return out


def contracted_tasks(now: datetime) -> list[dict[str, Any]]:
    """Every contracted box task, judged on its artifact on THIS host."""
    try:
        if str(ROOT / "ops") not in sys.path:
            sys.path.insert(0, str(ROOT / "ops"))
        import organ_contract as oc  # type: ignore[import-not-found]
    except Exception as exc:
        return [{"producer": "ops/organ_contract.py", "kind": "box_task", "status": ERROR,
                 "why": f"contracts unreadable: {type(exc).__name__}: {exc}"[:200]}]
    out: list[dict[str, Any]] = []
    for organ, (rel, max_age, _what) in sorted(oc.CONTRACTS.items()):
        facts = _artifact_facts(ROOT / rel)
        try:
            age = oc.artifact_age_min(rel, now)
        except Exception:
            age = None
        rec: dict[str, Any] = {"producer": organ, "kind": "box_task", "artifact": rel,
                               "max_age_min": max_age, "age_min": (None if age is None
                                                                   else round(age, 1)),
                               **{k: facts.get(k) for k in ("mtime", "content_ts", "content_key",
                                                            "rows", "bytes")
                                  if facts.get(k) is not None}}
        if age is None:
            rec.update(status=DEAD, why=f"{rel} absent or unstamped on this host")
        elif age <= max_age:
            rec.update(status=OK, why=f"{age:.0f} min old against a {max_age} min contract")
        elif age <= DEAD_AFTER_H * 60:
            rec.update(status=STALE, why=f"{age:.0f} min old against a {max_age} min contract")
        else:
            rec.update(status=DEAD, why=f"{age / 60:.0f} h old against a {max_age} min contract")
        out.append(rec)
    return out


def manifest_tasks(path: Path | None = None) -> list[str]:
    try:
        text = (path or MANIFEST).read_text(encoding="utf-8")
    except OSError:
        return []
    return sorted(set(re.findall(r'^TASK name="([^"]+)"', text, flags=re.MULTILINE)))


def uncontracted_tasks(contracted: set[str], path: Path | None = None) -> list[dict[str, Any]]:
    """Manifest tasks no contract covers: NO_CONTRACT, by name, never omitted."""
    return [{"producer": name, "kind": "box_task", "status": NO_CONTRACT,
             "why": "declared in box_tasks.manifest with no artifact contract in "
                    "ops/organ_contract.py: it may run, but nothing proves it produced"}
            for name in manifest_tasks(path)
            if name not in contracted and not any(c.startswith(name + " (") for c in contracted)]


def _count_lines(path: Path, budget: list[int]) -> tuple[int, bool]:
    """(rows, exact). Reads at most `budget[0]` bytes, shared across a seat."""
    try:
        size = path.stat().st_size
    except OSError:
        return 0, True
    if budget[0] <= 0:
        return max(1, size // 400), False
    try:
        with open(path, "rb") as fh:
            blob = fh.read(min(size, budget[0]))
    except OSError:
        return 0, True
    budget[0] -= len(blob)
    n = blob.count(b"\n")
    if len(blob) < size:
        return max(1, round(n * size / max(len(blob), 1))), False
    return max(n, 1), True


def seats(now: datetime, *, roots: tuple[Path, ...] = SEAT_ROOTS,
          window_h: float = WINDOW_H, retired: dict[str, str] | None = None
          ) -> list[dict[str, Any]]:
    """Every intelligence seat: last write, files and rows inside the window."""
    cutoff = now.timestamp() - window_h * 3600.0
    agg: dict[str, dict[str, Any]] = {}
    budgets: dict[str, list[int]] = {}
    for root in roots:
        try:
            dirs = [d for d in os.scandir(root) if d.is_dir()]
        except OSError:
            continue
        for d in dirs:
            rec = agg.setdefault(d.name, {"last": 0.0, "files_window": 0, "rows_window": 0,
                                          "exact": True})
            budget = budgets.setdefault(d.name, [SEAT_COUNT_BYTES])
            try:
                entries = list(os.scandir(d.path))
            except OSError:
                continue
            for e in entries:
                if not e.name.endswith((".json", ".jsonl")):
                    continue
                try:
                    mt = e.stat().st_mtime
                except OSError:
                    continue
                rec["last"] = max(rec["last"], mt)
                if mt >= cutoff:
                    rec["files_window"] += 1
                    n, exact = _count_lines(Path(e.path), budget)
                    rec["rows_window"] += n
                    rec["exact"] = rec["exact"] and exact
    retired = retired or {}
    out: list[dict[str, Any]] = []
    for name, rec in sorted(agg.items()):
        last = datetime.fromtimestamp(rec["last"], UTC) if rec["last"] else None
        age = _age_h(last, now)
        row: dict[str, Any] = {"producer": name, "kind": "seat", "last_write_at": _iso(last),
                               "files_window": rec["files_window"],
                               "rows_window": rec["rows_window"],
                               "rows_exact": rec["exact"]}
        if rec["files_window"]:
            row.update(status=OK, why=f"{rec['files_window']} file(s) written in "
                                      f"{window_h:g} h")
        elif name in retired:
            row.update(status=RETIRED, why=retired[name][:240])
        elif age is not None and age <= DEAD_AFTER_H:
            row.update(status=STALE, why=f"last write {age:.0f} h ago")
        else:
            row.update(status=DEAD, why=(f"last write {age:.0f} h ago" if age is not None
                                         else "seat directory holds no donation"))
        out.append(row)
    return out


def _retired_seats() -> dict[str, str]:
    try:
        if str(ROOT / "scripts") not in sys.path:
            sys.path.insert(0, str(ROOT / "scripts"))
        import check_producer_yield as cpy  # type: ignore[import-not-found]
        return dict(cpy.RETIRED_SEATS)
    except Exception:
        return {}


def build(now: datetime | None = None, *, ledger: Path | None = None,
          woe_ledger: Path | None = None, seat_roots: tuple[Path, ...] = SEAT_ROOTS,
          manifest: Path | None = None, window_h: float = WINDOW_H) -> dict[str, Any]:
    now = now or _now()
    t0 = time.monotonic()
    by_leg: dict[str, list[dict[str, Any]]] = {}
    for r in leg_runs(ledger=ledger, woe_ledger=woe_ledger):
        by_leg.setdefault(str(r["producer"]), []).append(r)
    rows: list[dict[str, Any]] = []
    for leg, runs in sorted(by_leg.items()):
        rows.append({"producer": leg, "kind": "leg",
                     **judge_leg(runs, now, window_h=window_h)})
    tasks = contracted_tasks(now)
    rows.extend(tasks)
    rows.extend(uncontracted_tasks({t["producer"] for t in tasks}, manifest))
    rows.extend(seats(now, roots=seat_roots, window_h=window_h, retired=_retired_seats()))
    counts = Counter(r["status"] for r in rows)
    by_kind: dict[str, dict[str, int]] = {}
    for r in rows:
        k = by_kind.setdefault(r["kind"], {})
        k[r["status"]] = k.get(r["status"], 0) + 1
    return {
        "generated_utc": _iso(now), "organ": "libs/ops/producer_heartbeat.py",
        "host": socket.gethostname(),
        "law": ("Every producer -- hourly leg, contracted box task, intelligence seat -- carries "
                "exactly one NAMED status from a closed vocabulary, with the evidence that "
                "decided it. No proof is a status (DEAD / NO_CONTRACT), never UNMEASURED."),
        "statuses": list(STATUSES), "window_h": window_h, "dead_after_h": DEAD_AFTER_H,
        "n_producers": len(rows), "counts": {s: counts.get(s, 0) for s in STATUSES},
        "by_kind": by_kind,
        "not_ok": sorted((r["producer"] for r in rows
                          if r["status"] not in (OK, RETIRED)), key=str),
        "producers": rows,
        "elapsed_s": round(time.monotonic() - t0, 2),
    }


def publish(doc: dict[str, Any], path: Path | None = None) -> Path:
    out = path or ARTIFACT
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, out)
    return out


def maybe_publish(*, every_s: int = PUBLISH_EVERY_S) -> bool:
    """Rebuild the summary when it is older than `every_s`. Throttled, total, never in a test."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    try:
        try:
            if time.time() - ARTIFACT.stat().st_mtime < every_s:
                return False
        except OSError:
            pass
        publish(build())
        return True
    except Exception:
        return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--print", action="store_true", help="print the non-OK rows")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    doc = build()
    path = publish(doc, a.out)
    print(f"producer heartbeat: {doc['n_producers']} producers  "
          + "  ".join(f"{k}={v}" for k, v in doc["counts"].items() if v) + f"  -> {path}")
    if a.print:
        for r in doc["producers"]:
            if r["status"] not in (OK, RETIRED):
                print(f"  {r['status']:<11} {r['kind']:<8} {r['producer']}: {r.get('why', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
