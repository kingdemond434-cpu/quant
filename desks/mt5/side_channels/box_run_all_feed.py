"""THE RUN_ALL MINERS, ON THE BOX: reddit, github, mql5, central banks, sec_edgar and the rest.

WHY THIS EXISTS (2026-11-03). The principal's standing order that day: every miner runs 24/7,
never finishes, never rests -- "same w all miners". `run_all_miners.ALL_MINERS` (25 seats) had
exactly one family of clocks, all on the Hetzner VPS (`hourly-controller.timer`,
`full-pipeline.timer`, the brain chain), and the VPS went silent at 02:50Z. `box_intel_feed`
(the `intel_feed` leg) carried seed_miners and hourly_discovery onto the box and deliberately
never calls run_all_miners; the `youtube_miner` and `youtube_corpus` legs carry YouTube. This
leg carries the other 24.

WHAT ONE PASS DOES. Under the intel department's resident (MT5-Dept-Intel: 24/7, SYSTEM,
BELOW_NORMAL), whose own loop is what makes it never stop:
  1. gates itself to MIN_INTERVAL_S since its last start, and takes a lease so two passes never
     run at once (the lease and cadence code is box_intel_feed's, reused, not copied);
  2. runs each miner as its own child process -- `--child <name>` -- which installs the box
     rails (honest UA, robots.txt on every host, no VPS-walled host) BEFORE any miner module is
     imported, then calls that miner's own `run_and_save`, which writes its seat under
     data/intelligence/ where local_converter reads it;
  3. kills a child at MINER_TIMEOUT_S (run_all_miners' own 180 s) or at what is left of the
     budget, whichever is first, and starts the next pass where this one stopped (a cursor), so a
     budget cut never starves the same miners twice;
  4. writes reports/BOX_RUN_ALL_FEED.json: per miner its status, rows and the hosts the rails
     refused (each named with a missed-growth line -- a refusal is a recorded fact, never a 0).

    python desks/mt5/side_channels/box_run_all_feed.py --budget-s 2040
    python desks/mt5/side_channels/box_run_all_feed.py --dry-run
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = BASE.parent.parent
for _p in (str(HERE), str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import box_intel_feed as feed  # noqa: E402

REPORT = BASE / "reports" / "BOX_RUN_ALL_FEED.json"
STATE = BASE / "data" / "box_run_all_feed_state.json"
LEASE = BASE / "data" / "locks" / "box_run_all_feed.lease"
RAILS_LOG = BASE / "logs" / "box_run_all_feed_rails.jsonl"
BUDGET_S = 2040.0
MIN_INTERVAL_S = 1800.0
MINER_TIMEOUT_S = 180.0
MIN_CHILD_S = 20.0
WRITE_MARGIN_S = 60.0
RESULT_PREFIX = feed.RESULT_PREFIX     # one result-line format for every rails child
#: Carried by their own legs (`youtube_miner`, `youtube_corpus`): run here too and the quota is
#: spent twice.
OWN_LEG: frozenset[str] = frozenset({"youtube"})

Runner = Callable[[list[str], float, dict[str, str]], tuple[int | None, str]]


def roster() -> list[str]:
    """run_all_miners' names, in its order, minus the ones another leg carries. Read from the
    source, not imported: importing run_all_miners imports every miner, which must happen only
    in a child that has its rails installed."""
    import ast
    src = (HERE / "run_all_miners.py").read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "ALL_MINERS" for t in node.targets):
            names = [e.elts[0].value for e in getattr(node.value, "elts", [])
                     if isinstance(e, ast.Tuple) and isinstance(e.elts[0], ast.Constant)]
            return [str(n) for n in names if n not in OWN_LEG]
    return []


def child_cmd(name: str) -> list[str]:
    return [sys.executable, "-u", str(Path(__file__).resolve()), "--child", name]


def run_pass(budget_s: float = BUDGET_S, *, runner: Runner | None = None, force: bool = False,
             now: float | None = None, write: bool = True) -> dict[str, Any]:
    t0 = time.monotonic()
    state = feed._read(STATE)
    ok, why = feed.due(state, now, MIN_INTERVAL_S)
    if not ok and not force:
        return {"status": "NOT_DUE", "why": why}
    held, lwhy = feed.take_lease(LEASE)
    if not held:
        return {"status": "LEASE_HELD", "why": lwhy}
    try:
        return _pass(state, why, budget_s, runner or feed._default_runner, write, t0)
    finally:
        feed.release_lease(LEASE)


def _pass(state: dict[str, Any], why: str, budget_s: float, runner: Runner, write: bool,
          t0: float) -> dict[str, Any]:
    names = roster()
    start = int(state.get("cursor") or 0) % max(len(names), 1)
    order = names[start:] + names[:start]
    state["last_started_at"] = feed._now_iso()
    if write:
        feed._write(STATE, state)
    with contextlib.suppress(OSError):
        RAILS_LOG.unlink()
    env = feed.child_env(str(RAILS_LOG))
    miners: dict[str, Any] = {}
    done = 0
    for name in order:
        left = budget_s - (time.monotonic() - t0) - WRITE_MARGIN_S
        if left < MIN_CHILD_S:
            break
        rc, tail = runner(child_cmd(name), min(MINER_TIMEOUT_S, left), env)
        res = feed._parse(tail)
        miners[name] = {"status": feed._status(rc), "rc": rc, "rows": res.get("rows"),
                        **({"error": res["error"]} if res.get("error") else {})}
        done += 1
    state["cursor"] = (start + done) % max(len(names), 1)
    hosts, missed = feed.refused_by_host(_logged(RAILS_LOG))
    statuses = [m["status"] for m in miners.values()]
    rep = {
        "at": feed._now_iso(), "why_due": why, "budget_s": budget_s,
        "spent_s": round(time.monotonic() - t0, 1),
        "status": ("FAILED" if statuses and all(s != "OK" for s in statuses) else
                   "OK" if statuses else "NO_TIME"),
        "roster": names, "own_leg_elsewhere": sorted(OWN_LEG),
        "ran": done, "not_reached_this_pass": len(names) - done, "next_cursor": state["cursor"],
        "miners": miners, "rows": sum(int(m.get("rows") or 0) for m in miners.values()),
        "rails": {"refused_n": sum(h["n"] for h in hosts.values()), "by_host": hosts,
                  "missed_growth": missed},
        "law": ("every miner 24/7, never finishing (principal 2026-11-03); the intel resident's "
                "loop is the 24/7, this leg is one pass of it"),
    }
    if write:
        feed._write(STATE, state)
        feed._write(REPORT, rep)
    return rep


def _logged(path: Path) -> list[dict[str, Any]]:
    try:
        import box_rails
        return box_rails.logged_refusals(path)
    except Exception:
        return []


def _child(name: str) -> int:
    """One miner in this process, the rails installed before any miner module is imported."""
    import box_rails
    try:
        box_rails.install()
    except Exception as exc:
        print(RESULT_PREFIX + json.dumps({"status": "FAILED", "error": (
            f"box rails could not install, nothing fetched: {type(exc).__name__}: {exc}")[:300]}),
              flush=True)
        return 1
    import run_all_miners as ram
    fn = dict(ram.ALL_MINERS).get(name)
    if fn is None or name in OWN_LEG:
        print(RESULT_PREFIX + json.dumps({"status": "FAILED", "error": f"no miner {name!r}"}),
              flush=True)
        return 2
    disc = fn() or []
    print(RESULT_PREFIX + json.dumps({"status": "OK", "rows": len(disc),
                                      "rails_refused_here": len(box_rails.refused())}),
          flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--child", default="")
    a = ap.parse_args(argv)
    if a.child:
        return _child(a.child)
    if a.dry_run:
        ok, why = feed.due(feed._read(STATE), None, MIN_INTERVAL_S)
        print(f"due={ok} ({why}); roster ({len(roster())}): {', '.join(roster())}")
        return 0
    rep = run_pass(a.budget_s, force=a.force)
    if rep.get("status") in ("NOT_DUE", "LEASE_HELD"):
        print(f"RUN_ALL FEED {rep['status']}: {rep['why']}", flush=True)
        return 0
    print(f"RUN_ALL FEED {rep['status']} ran={rep['ran']}/{len(rep['roster'])} "
          f"rows={rep['rows']} refused={rep['rails']['refused_n']} -> {REPORT}", flush=True)
    return 0 if rep["status"] != "FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
