"""THE SOFT DEADLINE: a leg knows when it will be killed, stops before it, and keeps its work.

MEASURED 2026-11-10 (box LEG_ROTATION) and again in the 2026-11-25 producer triage:
`axis_registry`, `qd_frontier`, `graveyard_resurrection` and `discovery_compiler` each ran to
their cycle cap and were SIGKILLed having written nothing. A producer that is killed at the same
prefix every hour is not slow, it is BROKEN -- and it reads identically to slow on every board.

The harness (`hourly_cycle._producer_impl`, `_auto_leg`) already exported the cap as
`QUANT_LEG_BUDGET_S`; it now also exports `QUANT_LEG_DEADLINE_TS`, the ABSOLUTE wall-clock
instant (epoch seconds) at which the kill lands. The absolute form is what a producer needs: it
does not care how long the interpreter took to start, only how long is left.

    from libs.ops import leg_deadline as ld
    for item in work:
        if ld.expired(margin_s=30):        # stop BETWEEN units, never inside one
            break
        ...
    ld.publish_partial(OUT, report, complete=False)

    cur = ld.Cursor(DESK / "data" / "my_cursor.json")   # resume where the last pass stopped
    start = cur.load().get("offset", 0)
    cur.save({"offset": n})

NEVER RAISES. A producer must never die because its deadline helper did; every entry point is
total, and an unreadable or absent deadline means "no deadline" (math.inf left), which is
exactly the behaviour every producer had before this module existed.
"""
from __future__ import annotations

import json
import math
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ENV_BUDGET = "QUANT_LEG_BUDGET_S"
ENV_DEADLINE = "QUANT_LEG_DEADLINE_TS"

#: Seconds a producer keeps in hand by default for its final write. One minute matches the
#: margin `hunt12` and the tape walk already use.
DEFAULT_MARGIN_S = 60.0

#: The process start, so a bare `QUANT_LEG_BUDGET_S` (an older harness, a hand run) still gives
#: an absolute deadline: the budget counts from when this module was first imported.
_T0_WALL = time.time()


def deadline_ts(environ: dict[str, str] | None = None) -> float | None:
    """The absolute epoch instant the leg will be killed, or None when nothing says so."""
    env = os.environ if environ is None else environ
    raw = env.get(ENV_DEADLINE)
    if raw:
        try:
            ts = float(raw)
            if math.isfinite(ts) and ts > 0:
                return ts
        except (TypeError, ValueError):
            pass
    raw = env.get(ENV_BUDGET)
    if raw:
        try:
            budget = float(raw)
            if math.isfinite(budget) and budget > 0:
                return _T0_WALL + budget
        except (TypeError, ValueError):
            pass
    return None


def env_for(budget_s: float, *, now: float | None = None) -> dict[str, str]:
    """The two variables a harness exports to a child it will kill after `budget_s`."""
    start = time.time() if now is None else float(now)
    return {ENV_BUDGET: str(int(budget_s)), ENV_DEADLINE: f"{start + float(budget_s):.3f}"}


def deadline_left(margin_s: float = 0.0, *, environ: dict[str, str] | None = None,
                  now: float | None = None) -> float:
    """Seconds left before the kill, less `margin_s`; math.inf when no deadline is declared."""
    ts = deadline_ts(environ)
    if ts is None:
        return math.inf
    current = time.time() if now is None else float(now)
    return ts - current - float(margin_s)


def expired(margin_s: float = DEFAULT_MARGIN_S, **kw: Any) -> bool:
    """True once fewer than `margin_s` seconds remain: stop starting new units of work."""
    return deadline_left(margin_s, **kw) <= 0.0


def own_budget(cli_budget_s: float | None, margin_s: float = DEFAULT_MARGIN_S,
               **kw: Any) -> float | None:
    """The tighter of a producer's own `--budget-s` and what the harness leaves it.

    None means neither says anything (run unbounded, as before)."""
    left = deadline_left(margin_s, **kw)
    vals = [v for v in (cli_budget_s, None if math.isinf(left) else max(left, 1.0))
            if v is not None]
    return min(vals) if vals else None


def _atomic(path: Path, text: str) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
        return True
    except OSError:
        return False


def publish_partial(path: Path, doc: dict[str, Any], *, complete: bool = False,
                    stopped_by: str = "deadline") -> bool:
    """Write `doc` atomically, stamped, and marked `partial` unless `complete`.

    A report a producer writes when its deadline arrives is EVIDENCE of how far it got, not a
    failure: the stamp proves it ran and `partial` says the pass was cut, so a reader never
    mistakes a cut pass for a complete one, nor an absent file for a cut pass."""
    out = dict(doc)
    out.setdefault("generated_utc", datetime.now(UTC).isoformat(timespec="seconds"))
    out["partial"] = not complete
    if not complete:
        out["stopped_by"] = stopped_by
    try:
        text = json.dumps(out, indent=1, default=str)
    except (TypeError, ValueError):
        return False
    return _atomic(Path(path), text)


class Cursor:
    """A resume cursor: one small JSON document, written atomically, read tolerantly."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, Any]:
        try:
            doc = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return doc if isinstance(doc, dict) else {}

    def save(self, state: dict[str, Any]) -> bool:
        try:
            text = json.dumps({**state, "saved_utc": datetime.now(UTC).isoformat(
                timespec="seconds")}, indent=1, default=str)
        except (TypeError, ValueError):
            return False
        return _atomic(self.path, text)
