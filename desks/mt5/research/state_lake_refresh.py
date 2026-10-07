"""THE STATE LAKE ON A CLOCK: fetch its inputs, rebuild it, rebuild the PIT conditioners.

WHY `data/states/free_states.parquet` ENDS 2026-08-14 (measured 2026-10-06). Three defects, each
enough on its own:

  1. NO CLOCK FOR ANY INPUT. `mt5desk/fetch_cot.py`, `fetch_cot_disagg.py`, `fetch_tff.py` and
     `research/fetch_fred.py` were run by hand on the retired laptop and are on no task, timer,
     leg or battery. `data/cot/*.parquet` ends 2026-08-11.
  2. FRED WROTE TO THE LAPTOP. `fetch_fred.OUT` was `C:\\Users\\dell\\mt5-research\\data\\lake`;
     `free_shadows.load_fred` reads the desk's `data/lake`. Fixed in fetch_fred.py.
  3. THE BUILDER RAN ONLY AT THE TAIL OF A WEEKLY CHAIN. `run_gateway_loop` calls
     `free_shadows.main()` on Monday 23:00 UTC after `fetch_universe` and hunts 7-9, inside one
     try block: any earlier failure skips it, and with stale inputs it rebuilds the same past.

So this driver owns the whole lake, as one rostered organ of the hourly `organs` battery
(`research/batteries.py`). Each step is DUE when its last success is older than its cadence, runs
in-process (sys.path set here, so no launcher has to export PYTHONPATH), and is recorded with its
outcome. One step's failure never stops the next: `free_shadows` still rebuilds from whatever
inputs are on disk, and `pit_conditioners` still publishes the axes that are there. The whole
pass stops starting new steps after BUDGET_S so it fits the battery's slice; the rest run next
pass. The data itself is box state (`data/lake/` and `*.parquet` are gitignored): it is
regenerated here, on the box that reads it, never carried in git.

    python desks/mt5/research/state_lake_refresh.py [--force]
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

STATE = DESK / "data" / "state_lake_refresh.json"
REPORT = DESK / "reports" / "STATE_LAKE.json"
#: The battery slice is 150 s at most; stop STARTING steps well inside it.
BUDGET_S = 110.0
DAY = 86400.0


def _run_main(module: str) -> Callable[[], Any]:
    def run() -> Any:
        import importlib

        return importlib.import_module(module).main()
    return run


def _pit() -> Any:
    import pit_conditioners

    return pit_conditioners.main([])


#: (name, callable, cadence_s). Fetchers daily (COT publishes weekly, FRED daily); the two
#: builders every pass, because they are cheap and must follow any input that just landed.
STEPS: tuple[tuple[str, Callable[[], Any], float], ...] = (
    ("fetch_cot", _run_main("mt5desk.fetch_cot"), DAY),
    ("fetch_cot_disagg", _run_main("mt5desk.fetch_cot_disagg"), DAY),
    ("fetch_tff", _run_main("mt5desk.fetch_tff"), DAY),
    ("fetch_fred", _run_main("fetch_fred"), DAY),
    ("free_shadows", _run_main("free_shadows"), 0.0),
    ("pit_conditioners", _pit, 0.0),
)


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def _atomic(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    tmp.replace(path)


def free_states_end(path: Path | None = None) -> str | None:
    """The last bar the state lake reaches -- the number this organ exists to keep current."""
    import pandas as pd

    p = path or DESK / "data" / "states" / "free_states.parquet"
    try:
        idx = pd.read_parquet(p, columns=[]).index
    except Exception:
        return None
    return str(idx.max()) if len(idx) else None


def run(force: bool = False, steps: tuple[tuple[str, Callable[[], Any], float], ...] = STEPS,
        state_path: Path | None = None, budget_s: float = BUDGET_S) -> dict[str, Any]:
    sp = state_path or STATE
    state = _read(sp)
    t0 = time.time()
    ran: list[str] = []
    for name, fn, cadence in steps:
        last = state.get(name) or {}
        ok_at = float(last.get("ok_ts") or 0.0)
        if not force and cadence and time.time() - ok_at < cadence:
            continue
        if time.time() - t0 > budget_s:
            state.setdefault(name, {})["deferred"] = "pass budget spent; due next pass"
            continue
        s0 = time.time()
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                ret = fn()
            # A CLI-style main that RETURNS a non-zero code failed, even though it did not raise
            # (`fetch_fred.main` returns 1 on a partial fetch): recorded FAILED, retried next pass.
            if isinstance(ret, int) and not isinstance(ret, bool) and ret != 0:
                rec = {"outcome": "FAILED", "ok_ts": ok_at, "why": f"returned exit code {ret}"}
            else:
                rec = {"outcome": "OK", "ok_ts": time.time()}
        except BaseException as exc:          # SystemExit from a CLI main is an outcome too
            if isinstance(exc, KeyboardInterrupt):
                raise
            rec = {"outcome": "FAILED", "ok_ts": ok_at,
                   "why": f"{type(exc).__name__}: {str(exc)[:300]}"}
        tail = buf.getvalue().strip().splitlines()
        state[name] = {**rec, "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                       "s": round(time.time() - s0, 1), "tail": tail[-3:]}
        ran.append(name)
    _atomic(sp, state)
    doc = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"), "ran": ran,
           "steps": state, "free_states_end": free_states_end(),
           "failing": sorted(k for k, v in state.items()
                             if isinstance(v, dict) and v.get("outcome") == "FAILED"),
           "rule": ("each input is refetched when its last success is older than its cadence; "
                    "the state lake and the PIT conditioners are rebuilt every pass from what is "
                    "on disk; a consumer never reads a state older than its freshness window")}
    _atomic(REPORT, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true", help="run every step regardless of cadence")
    a = ap.parse_args(argv)
    doc = run(force=a.force)
    print(f"state lake: ran {', '.join(doc['ran']) or 'nothing due'}; "
          f"free_states ends {doc['free_states_end']}; failing {doc['failing'] or 'none'}")
    return 1 if doc["failing"] else 0


if __name__ == "__main__":
    sys.exit(main())
