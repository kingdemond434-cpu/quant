"""daily_cycle: the three processes that actually move an edge toward capital.

    shadow_forward  ->  promoter  ->  markout

WHY THIS FILE HAD TO EXIST. `research_supervisor` restarts hunts and `hourly_cycle` checks health,
mines the web and writes a frontier report. Both work. Neither has ever run `shadow_forward`,
`promoter` or `markout` -- so nine validated candidates sat in `shadow_forward.SLEEVES` with
nothing to execute them, accruing no evidence, unable to promote, for as long as that remained
true. A pipeline that does not terminate in a decision is not a pipeline.

The supervisor could not have been the home for this. It is built around one-shot DONE markers: a
target runs until its marker exists and is never started again. That is right for a hunt and wrong
for anything daily, which is why these three were never added to it.

WHY DATE-STAMPED AND NOT CLOCK-TRIGGERED. The execution box is a laptop that sleeps. A task
scheduled for 22:00 simply never runs on a day the lid was shut at 21:30, and the failure is
silent -- the desk looks idle rather than broken. This runs the day's work on the FIRST invocation
of each UTC day and no-ops on every later one, so an hourly caller gets exactly one run per day
whenever the machine happens to be awake. `shadow_forward` is independently idempotent on the same
key, so a double call is safe even if this guard is bypassed.

    python research/daily_cycle.py            # from the hourly loop, or by hand
    python research/daily_cycle.py --force    # re-run today (after fixing a failure)
"""

from __future__ import annotations

import json
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
for p in (str(BASE), str(BASE / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

STAMP = BASE / "data" / "daily_cycle_state.json"
LOG = BASE / "logs" / "daily_cycle.log"


def dlog(msg: str) -> None:
    line = f"{datetime.now(UTC).isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _load_stamp() -> dict:
    if not STAMP.exists():
        return {}
    try:
        return json.loads(STAMP.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def run_step(name: str, fn) -> dict:
    """Run one step, recording the outcome either way.

    A step that raises must NOT abort the cycle. Shadow needs a live MT5 terminal and will fail on
    a research box; the promoter and markout read files and do not. Stopping the whole cycle on the
    first failure would mean a closed laptop silently suppresses the execution measurement too --
    and an unmeasured failure is the thing this desk is least willing to have.
    """
    started = datetime.now(UTC)
    try:
        fn()
        out = {"ok": True}
        dlog(f"{name}: ok")
    except Exception as exc:
        out = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        dlog(f"{name}: FAILED -- {out['error']}")
        dlog(traceback.format_exc().rstrip())
    out["seconds"] = round((datetime.now(UTC) - started).total_seconds(), 1)
    return out


def _shadow() -> None:
    import shadow_forward
    shadow_forward.main()


def _qquant_shadow() -> None:
    import qquant_shadow
    qquant_shadow.main()


def _execution() -> None:
    """Reconstruct execution quality from the venue's own ticks BEFORE the promoter runs."""
    from mt5desk import shadow_execution
    shadow_execution.main()


def _promote() -> None:
    import promoter
    promoter.main()


def _reconcile() -> None:
    import forward_reconcile
    forward_reconcile.main()


def _decay() -> None:
    import decay_monitor
    decay_monitor.main()


def _markout() -> None:
    from mt5desk.markout import compute, load_jsonl, render
    data = BASE / "data"
    m = compute(load_jsonl(data / "order_intents.jsonl"),
                load_jsonl(data / "live_ledger.jsonl"))
    for line in render(m).splitlines():
        dlog("  " + line)
    markout_path = BASE / "reports" / "markout.json"
    markout_path.parent.mkdir(parents=True, exist_ok=True)
    markout_path.write_text(json.dumps({
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "usable": m.usable, "n_matched": m.n_matched,
        "n_unfilled_intents": m.n_unfilled_intents,
        "n_unmatched_deals": m.n_unmatched_deals,
        "mean_slip_quote": m.mean_slip_quote, "mean_slip_r": m.mean_slip_r,
        "edge_share": m.edge_share, "why": m.why,
    }, indent=2), encoding="utf-8")


def _futures_curves() -> None:
    """Accrue real contract curves so roll/calendar hypotheses stop remaining prose-blocked."""
    import fetch_futures_curves

    rc = fetch_futures_curves.main([])
    if rc not in (0, 2):
        raise RuntimeError(f"fetch_futures_curves returned {rc}")


def _curve_strategies() -> None:
    """Test causal HP/trend/contrarian descendants immediately after refreshing curves."""
    import curve_strategy_screen

    curve_strategy_screen.main()


def _export_aurum() -> None:
    """Re-export the findings Aurum's absorption channel reads.

    ABSORPTION WAS A ONE-SHOT SCRIPT AND THEREFORE IDLE BY DEFAULT. Aurum's
    step_absorb runs daily and reads inbox/quant_findings.jsonl; nothing on
    this side wrote it until export_aurum_findings.py existed, and a script
    that only runs when a human remembers is the same defect one step later --
    the channel reports "0 new findings" and that is indistinguishable from
    this desk having learned nothing.

    Runs LAST, after shadow and the promoter, so any finding derived from
    today's forward evidence is exported the same day it is produced rather
    than a cycle behind. The exporter appends and content-hashes, and Aurum's
    Absorber dedups by claim, so a repeat run is a no-op rather than a
    duplicate -- which is what makes it safe to run unconditionally, every
    day, forever.
    """
    import export_aurum_findings
    rc = export_aurum_findings.main()
    # rc 2 means NO SWEEP ARTEFACTS, which is a real state and not a failure of
    # this step: reports/ is gitignored and lives on whichever host ran the
    # hunts. Raising on it would make the whole cycle report FAILED every day
    # on a clone that legitimately has no reports.
    if rc not in (0, 2):
        raise RuntimeError(f"export_aurum_findings returned {rc}")


def _zentech() -> None:
    root = BASE.parent.parent
    sys.path.insert(0, str(root / "scripts"))
    import build_zentech_state
    build_zentech_state.main()


#: ORDER IS LOAD-BEARING. The promoter reads the state shadow has just written, so running it
#: first would decide today on yesterday's evidence. Markout runs last-but-one and
#: unconditionally: it reads the live ledger, so it reports on the armed book whether or not
#: shadow could reach a terminal. The Aurum export runs after all of them, so it can carry
#: anything today's cycle produced.
STEPS = (("futures_curves", _futures_curves), ("curve_strategies", _curve_strategies),
         ("reconcile", _reconcile), ("shadow", _shadow), ("qquant_shadow", _qquant_shadow),
         ("execution", _execution), ("promoter", _promote), ("markout", _markout),
         ("decay", _decay),
         ("zentech", _zentech), ("export_aurum", _export_aurum))


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    force = "--force" in argv
    today = datetime.now(UTC).date().isoformat()
    stamp = _load_stamp()

    if stamp.get("last_run") == today and not force:
        dlog(f"daily cycle already ran {today}; skip (--force to re-run)")
        return 0

    dlog(f"daily cycle {today} starting")
    results = {name: run_step(name, fn) for name, fn in STEPS}

    # THE STAMP RECORDS THE ATTEMPT, NOT A SUCCESS. Marking the day done only on a clean run would
    # make a broken step retry every hour, and a step that fails at 09:00 because the terminal is
    # shut fails identically at 10:00 -- turning one honest failure into a log full of them. The
    # per-step outcome is kept alongside so the failure stays visible and `--force` is the explicit
    # way to try again.
    stamp["last_run"] = today
    stamp["steps"] = results
    STAMP.parent.mkdir(parents=True, exist_ok=True)
    STAMP.write_text(json.dumps(stamp, indent=2), encoding="utf-8")

    failed = [n for n, r in results.items() if not r["ok"]]
    dlog(f"daily cycle {today} done" + (f" -- FAILED: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
