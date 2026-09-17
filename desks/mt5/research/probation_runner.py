"""PROBATION -- unwired organs run on a clock, in rotation, until someone promotes them.

`wiring_ceo` writes data/probation_queue.json: every organ that nothing schedules and that can
run standalone, plus the REVIVE list -- organs that ARE on a clock and have produced nothing
within two cadences. This leg (heavy plan, hourly; also the daily cycle) works through both under
a bounded budget and records the outcome. Nothing here edits the cycle: an organ earns its named
leg through the docket and through `wiring_ceo.auto_legs`, with this evidence attached (how many
clean runs, how long, what it wrote). What probation removes is the state the principal named: a
build that has never run, sitting in the tree while the desk grows around it.

THROUGHPUT, AND WHY IT IS THE WHOLE POINT (principal 2026-09-17: "wire everything the wiring
hunter discovered, revive and certify and put clocks on everything"). The first version ran EIGHT
organs a pass against a queue of ~300. At one pass an hour that is a 37-hour lap, and an organ
needs three clean runs before it is clocked on the core plan -- four and a half days for the
queue's tail, if nothing new landed, and something new lands every hour. The pass is now bounded
by `--max-organs` (40) and `--budget-s` (1800) instead of by a fixed count, the rotation is
persisted in `cursor`, and a pass that is cut short loses nothing: the next one continues from
where this one stopped.

STATE IS WRITTEN AFTER EVERY ORGAN, NEVER AT THE END. This leg runs inside hourly_cycle under
that cycle's own subprocess timeout (SEARCH_BUDGET_SEC, 720s today, unless the cycle gives
`probation` a LEG_BUDGET_SEC row). A pass that only saved its work in the last line would be
killed at the same point every hour and record NOTHING, forever -- which is exactly the shape
hourly_cycle's own comment calls broken rather than slow. Every organ's result is committed as it
finishes, so truncation costs the organ that was running and nothing else.

TWO PHASES, IN THIS ORDER AND FOR THIS REASON:

  1. REVIVE. An organ on a clock that produces nothing is the same defect as an organ on no clock
     -- LAWS III.16 makes no distinction -- and it is the more expensive one, because it is
     already costing a subprocess an hour to fail. Each is re-run FOR REAL (its declared
     PRODUCTION_ARGS, never `--dry-run`: the point is to make it produce), and whatever stops it
     is reported with the tail of its traceback. Reviving it is not this organ's job; NAMING what
     stops it, with evidence, is.
  2. PROBATION. The unwired queue, in `wiring_ceo`'s order, least recently run first. Here
     `--dry-run` IS passed when the organ declares it -- a build nobody has ever run is being
     asked to prove it STARTS, not to write. What the clock does afterwards is the other half of
     the 2026-09-17 fix and lives in `wiring_ceo.auto_legs`: the clocked leg never passes
     `--dry-run`, because a leg that runs an organ's dry mode donates nothing while every counter
     reports it as wired.

NEVER MONEY. The queue excludes anything whose name touches the gateway, releases, the deadman,
orders or the tree (wiring_ceo.NEVER_PROBATION); this runner refuses the same names a second
time, so a mistaken queue entry cannot reach them.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
QUEUE = DESK / "data" / "probation_queue.json"
STATE = DESK / "data" / "probation_state.json"
OUT = DESK / "reports" / "PROBATION.json"
NEVER = ("gateway", "e8_", "promoter", "run_gateway", "adopt", "seal", "release", "deadman",
         "kill", "close", "order", "executor", "install", "reboot", "no_log", "reclaim",
         "delete", "wipe", "prune", "rotate", "migrate", "sync_", "push", "commit")
#: A PASS: at most this many organs, and at most this many seconds of wall clock. 40 x hourly
#: drains a ~300 organ queue in eight passes; the budget is what actually stops a pass, because
#: an organ that needs its own budgeted leg should not be able to eat the hour on its own.
MAX_ORGANS = 40
PASS_BUDGET_S = 1800
#: The default per-organ timeout. A queue row may carry its own `budget_s` and that wins.
ORGAN_BUDGET_S = 120
#: The revive phase's share of a pass. Reviving is higher priority than probation, but a crawler
#: that hangs must not be able to consume the whole pass and starve the queue behind it.
MAX_REVIVE = 8
REVIVE_BUDGET_S = 300
REVIVE_PASS_SHARE = 0.5
WATCH_DEPTH = 2
#: Directories every organ's run would otherwise "produce": bar caches other processes rewrite
#: continuously, credential stores nothing may report, and caches that are not output.
WATCH_SKIP = frozenset({"universe", "secrets", "lake", "free_data_cache", "repo_cache",
                        "gauntlet_cache", "pf_allocator_cache", "__pycache__", "cell_series",
                        "tape", "vintages", "acquired"})
ARTIFACT_BASIS = ("files under reports/ and data/ whose mtime falls inside the organ's run "
                  "window: EVIDENCE of output, not proof of authorship -- another leg writing at "
                  "the same moment lands in the same window")


def _read(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _sub(doc: dict[str, Any] | None, key: str) -> dict[str, Any]:
    """`doc[key]` when it is a mapping, {} otherwise: the state file is written by this organ's
    own previous pass and may be of an older shape."""
    value = (doc or {}).get(key)
    return value if isinstance(value, dict) else {}


def _never(organ: str) -> bool:
    return any(tok in str(organ).lower() for tok in NEVER)


def pick(queue: list[dict[str, Any]], state: dict[str, Any], k: int) -> list[dict[str, Any]]:
    """The k organs least recently run (never-run first), refusing money-path names.

    TIES BREAK ON THE QUEUE'S OWN ORDER, not on the organ's name. Every never-run organ shares
    one key -- the empty last-run stamp -- so the tiebreak decides which end of a 300-organ
    backlog is worked first, and alphabetical order is not a priority: `wiring_ceo` sorts its
    queue by tests-then-size, so the queue order carries a judgement and the name does not."""
    rows = [(i, q) for i, q in enumerate(queue)
            if isinstance(q, dict) and q.get("organ") and not _never(q["organ"])]
    last = _sub(state, "last_run")
    rows.sort(key=lambda t: (str(last.get(str(t[1]["organ"])) or ""), t[0]))
    return [q for _i, q in rows[:k]]


def _watch_dirs() -> tuple[Path, ...]:
    """Where an organ's output can land. Resolved at CALL time, not at import: DESK and ROOT are
    what a test repoints to build a hermetic tree, and a tuple frozen at import would send every
    such test scanning the real desk."""
    return (DESK / "reports", DESK / "data", ROOT / "data")


def _scan(dirs: tuple[Path, ...] | None = None) -> list[tuple[str, float]]:
    """(path, mtime) for every watched file, one bounded walk."""
    out: list[tuple[str, float]] = []
    stack = [(d, 0) for d in (dirs or _watch_dirs())]
    while stack:
        d, depth = stack.pop()
        try:
            entries = list(os.scandir(d))
        except OSError:
            continue
        for e in entries:
            try:
                if e.is_dir(follow_symlinks=False):
                    if depth < WATCH_DEPTH and e.name not in WATCH_SKIP:
                        stack.append((Path(e.path), depth + 1))
                else:
                    out.append((e.path, e.stat().st_mtime))
            except OSError:
                continue
    return out


def artifacts_since(t0: float, limit: int = 5) -> tuple[int, list[str]]:
    """(count, sample) of watched files written since `t0`.

    DONE MEANS AN ARTIFACT (LAWS III.16). A probation run that exits 0 and writes nothing has
    proved that the organ starts, which is worth knowing and is NOT the same as proving it
    produces -- and the difference decides whether clocking it buys the desk anything. The basis
    string travels with the number because a concurrent leg's write lands in the same window;
    this is evidence, never an authorship claim."""
    hits = [p for p, m in _scan() if m >= t0 - 1.0]
    hits.sort()
    rels: list[str] = []
    for p in hits[:limit]:
        try:
            rels.append(Path(p).relative_to(ROOT).as_posix())
        except ValueError:
            rels.append(p)
    return len(hits), rels


def _argv_for(row: dict[str, Any]) -> list[str]:
    """What this row's organ is called with. An explicit `argv` (the revive rows carry the
    organ's declared PRODUCTION_ARGS) wins; otherwise probation's own `--dry-run`, and only when
    the organ declares that flag."""
    argv = row.get("argv")
    if isinstance(argv, (list, tuple)):
        return [str(a) for a in argv]
    return ["--dry-run"] if row.get("dry_run") else []


def run_one(row: dict[str, Any], budget_s: int, cwd: Path | None = None) -> dict[str, Any]:
    organ = str(row["organ"])
    path = ROOT / organ
    if _never(organ):
        return {"organ": organ, "status": "REFUSED",
                "why": "money-path name: never exercised blind"}
    if not path.exists():
        return {"organ": organ, "status": "MISSING", "why": f"{organ} is not in the tree"}
    argv = _argv_for(row)
    args = [sys.executable, "-u", "-W", "ignore", str(path), *argv]
    work = cwd or (ROOT / "desks" / "mt5" if organ.startswith("desks/mt5/") else ROOT)
    t0 = time.monotonic()
    wall0 = time.time()
    try:
        r = subprocess.run(args, capture_output=True, text=True, cwd=str(work),
                           timeout=budget_s, check=False)
        n_art, art = artifacts_since(wall0)
        out = {"organ": organ, "status": "OK" if r.returncode == 0 else "EXIT",
               "exit_code": r.returncode, "seconds": round(time.monotonic() - t0, 1),
               "dry_run": bool(row.get("dry_run")) and not row.get("argv"), "argv": argv,
               "artifacts": n_art, "artifacts_sample": art,
               "tail": (r.stdout or r.stderr or "").strip().splitlines()[-3:]}
        if r.returncode != 0:
            # THE REASON IS THE TRACEBACK'S TAIL, not the happy stream. stdout is where an organ
            # prints what it did; stderr is where it says why it stopped, and a revive row whose
            # reason reads "loaded 400 rows" names nothing anyone can fix.
            err = (r.stderr or "").strip().splitlines()
            out["reason"] = " | ".join(err[-4:]) if err else "exited non-zero with no stderr"
        return out
    except subprocess.TimeoutExpired:
        return {"organ": organ, "status": "TIMEOUT", "seconds": budget_s, "argv": argv,
                "dry_run": bool(row.get("dry_run")) and not row.get("argv"),
                "reason": f"exceeded {budget_s}s",
                "why": f"exceeded {budget_s}s; the organ needs its own budgeted leg"}
    except OSError as exc:
        return {"organ": organ, "status": "FAILED_TO_START", "argv": argv,
                "reason": f"{type(exc).__name__}: {exc}",
                "why": f"{type(exc).__name__}: {exc}"}


def _record(state: dict[str, Any], r: dict[str, Any], now: str) -> None:
    """Fold one result into the persisted history (in place)."""
    last = state.setdefault("last_run", {})
    hist = state.setdefault("history", {})
    organ = r["organ"]
    last[organ] = now
    h = hist.setdefault(organ, {"runs": 0, "clean": 0})
    h["runs"] = int(h.get("runs", 0)) + 1
    h["clean"] = int(h.get("clean", 0)) + (1 if r.get("status") == "OK" else 0)
    h["last_status"] = r.get("status")
    if isinstance(r.get("artifacts"), int):
        h["artifacts"] = int(r["artifacts"])
    if isinstance(r.get("seconds"), (int, float)):
        prev_s = h.get("seconds")
        h["seconds"] = (round(max(float(prev_s), float(r["seconds"])), 1)
                        if isinstance(prev_s, (int, float)) else round(float(r["seconds"]), 1))


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def _cursor(queue: list[dict[str, Any]], state: dict[str, Any]) -> str | None:
    """The organ the NEXT pass will start at -- the queue's persisted place."""
    nxt = pick(queue, state, 1)
    return str(nxt[0]["organ"]) if nxt else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--max-organs", type=int, default=MAX_ORGANS,
                    help=f"probation organs this pass (default {MAX_ORGANS})")
    ap.add_argument("--per-pass", type=int, default=None,
                    help="deprecated alias for --max-organs (daily_cycle still passes it)")
    ap.add_argument("--budget-s", type=int, default=PASS_BUDGET_S,
                    help=f"wall-clock budget for the whole pass (default {PASS_BUDGET_S})")
    ap.add_argument("--organ-budget-s", type=int, default=ORGAN_BUDGET_S,
                    help=f"per-organ timeout when the queue row names none (default "
                         f"{ORGAN_BUDGET_S})")
    ap.add_argument("--max-revive", type=int, default=MAX_REVIVE,
                    help=f"clocked-but-silent organs re-run this pass (default {MAX_REVIVE})")
    ap.add_argument("--no-revive", action="store_true", help="probation queue only")
    ap.add_argument("--dry-run", action="store_true", help="list what would run")
    a = ap.parse_args(argv)
    max_organs = int(a.per_pass if a.per_pass is not None else a.max_organs)
    doc_queue = _read(QUEUE)
    queue = [q for q in (doc_queue.get("queue") or []) if isinstance(q, dict)]
    revive_q = [q for q in (doc_queue.get("revive") or []) if isinstance(q, dict)]
    state = _read(STATE)
    chosen = pick(queue, state, max_organs)
    revive_pick = [] if a.no_revive else pick(revive_q, state, int(a.max_revive))
    print(f"probation: {len(queue)} queued, {len(revive_q)} to revive; running "
          f"{len(revive_pick)} revive + {len(chosen)} probation this pass "
          f"(budget {a.budget_s}s)")
    if a.dry_run:
        for c in revive_pick:
            print(f"  would REVIVE {c['organ']} {' '.join(_argv_for(c))}")
        for c in chosen:
            print(f"  would run {c['organ']} {' '.join(_argv_for(c))}")
        return 0

    t_start = time.monotonic()
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    results: list[dict[str, Any]] = []
    revived: list[dict[str, Any]] = []
    stopped = "queue drained"

    def publish() -> None:
        hist = _sub(state, "history")
        promotable = sorted((k for k, v in hist.items() if int(v.get("clean", 0)) >= 3),
                            key=lambda k: -int(_sub(hist, k).get("clean", 0)))
        ran_ok = sum(1 for r in results if r.get("status") == "OK")
        doc = {
            "at": now, "n_queued": len(queue), "n_revive_queued": len(revive_q),
            "pass": {"max_organs": max_organs, "budget_s": int(a.budget_s),
                     "organ_budget_s": int(a.organ_budget_s), "max_revive": int(a.max_revive),
                     "elapsed_s": round(time.monotonic() - t_start, 1),
                     "ran": len(results), "clean": ran_ok, "stopped_why": stopped},
            "cursor": {"next_probation": _cursor(queue, state),
                       "next_revive": _cursor(revive_q, state),
                       "never_run": sum(1 for q in queue if str(q.get("organ") or "")
                                        not in (state.get("last_run") or {})),
                       "rule": ("the pass continues from here; the rotation is persisted in "
                                "probation_state.json, so a truncated pass costs the organ that "
                                "was running and nothing else")},
            "ran": results,
            "revive": revived,
            "n_revived": sum(1 for r in revived if r.get("revived")),
            "unrevivable": [{k: r.get(k) for k in
                             ("organ", "clock", "last_output", "exit_code", "status", "reason")}
                            for r in revived if not r.get("revived")],
            "history": hist, "promotable": promotable,
            "artifact_basis": ARTIFACT_BASIS,
            "rule": ("revive first (a clocked organ producing nothing is the costlier defect), "
                     "then the unwired queue least recently run first; three clean runs make an "
                     "organ PROMOTABLE, and one clean run already puts it on an auto leg through "
                     "wiring_ceo.auto_legs"),
        }
        state["at"] = now
        _write(STATE, state)
        _write(OUT, doc)

    def left() -> float:
        return float(a.budget_s) - (time.monotonic() - t_start)

    for c in revive_pick:
        organ_budget = int(c.get("budget_s") or REVIVE_BUDGET_S)
        if left() <= 0 or (time.monotonic() - t_start) >= float(a.budget_s) * REVIVE_PASS_SHARE:
            stopped = "revive share of the pass budget spent"
            break
        r = run_one(c, min(organ_budget, max(15, int(left()))))
        r.update({"clock": c.get("clock"), "last_output": c.get("last_output"),
                  "source": c.get("source"), "cadence_s": c.get("cadence_s"),
                  "revived": r.get("status") == "OK"})
        revived.append(r)
        _record(state, r, now)
        print(f"  REVIVE {r['organ']:<52} {r.get('status'):<8} {r.get('seconds', '')}s "
              f"{'revived' if r.get('revived') else (r.get('reason') or '')[:60]}")
        publish()

    for c in chosen:
        if left() <= 0:
            stopped = f"pass budget {a.budget_s}s spent after {len(results)} organ(s)"
            break
        organ_budget = int(c.get("budget_s") or a.organ_budget_s)
        r = run_one(c, min(organ_budget, max(15, int(left()))))
        results.append(r)
        _record(state, r, now)
        print(f"  {r['organ']:<58} {r.get('status'):<8} {r.get('seconds', '')}s "
              f"art={r.get('artifacts', '-')}")
        publish()

    if not revive_pick and not chosen:
        stopped = "nothing queued"
    publish()
    doc = _read(OUT)
    print(f"  revived {doc.get('n_revived')} of {len(revived)}; "
          f"promotable: {len(doc.get('promotable') or [])} -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
