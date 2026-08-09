"""APPEND-ONLY PROMOTION HISTORY -- the dated record of forward-clock BIRTHS (L1.30, R0113).

WHY THIS EXISTS. `data/promotion_queue.json` recorded CURRENT slot occupancy and nothing else, so
`scripts/check_replacement_rate.py` could count DEATHS (dated graveyard entries) and not BIRTHS,
and honestly reported UNMEASURED-BIRTHS forever. Replacement rate = births/deaths is the number
that sets long-run CAGR, and it was structurally uncomputable for want of one dated list.

THE ONE TRAP THIS MODULE EXISTS TO AVOID, and it is the desk's own most-repeated failure class: a
watcher that starts today and stamps `promoted_at = now` on every clock it happens to see would
manufacture twelve births on its first run -- a phantom measurement in the COMPLACENT direction
(births up => status OK => the countdown nobody is watching goes back to being unwatched). So the
three ways a row can get its date are kept distinct and are never conflated:

  DECLARED  the clock's own artifact carries its start (`shadow_start`). A real date, from the
            source. Counts as a birth if it falls in the window.
  OBSERVED  the edge was ABSENT from the previous observation and is present now, so it was born
            between the two runs. A real date, to within one cadence period. Counts.
  UNKNOWN   present on the very first run, with no declared start. It was born at some unknown
            point in the past. `promoted_at` is None and it NEVER counts as a birth -- the count
            becomes a LOWER BOUND, which the fence is told about explicitly rather than left to
            infer from a number that looks complete.

RETIREMENT IS ONLY RECORDED ON A COMPLETE READ. `derive_slots()` reports `complete=False` when any
source was unreadable, which makes its slot list a LOWER BOUND. Retiring on a lower bound would
book a false death now and -- worse -- a false BIRTH when the file becomes readable again and the
edge "reappears". Flapping storage would then look exactly like a healthy pipeline. So an
incomplete read retires nothing and says so.

A RESURRECTED EDGE GETS A NEW ROW. A forward clock that was retired and later restarted is a new
clock accruing new evidence, so it is a new birth with its own date; the retired row is never
rewritten. Rows are append-only: the only field ever mutated on an existing row is `retired_at`,
and only from None.

Pure stdlib, no I/O -- the caller owns the file. import from libs.research.promotion_history.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

#: How a row's `promoted_at` was obtained. UNKNOWN rows are undatable and never count as births.
DECLARED = "DECLARED"
OBSERVED = "OBSERVED"
UNKNOWN = "UNKNOWN"


def _key(row: Any) -> tuple[str, str]:
    if not isinstance(row, dict):
        return ("", "")
    return (str(row.get("edge", "")), str(row.get("kind", "")))


def _open_rows(history: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Rows not yet retired, keyed by (edge, kind). Later rows win -- a resurrection's row is the
    live one, and the retired row it replaced stays untouched in the list."""
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for r in history:
        if isinstance(r, dict) and not r.get("retired_at"):
            out[_key(r)] = r
    return out


def update(
    slots: list[dict[str, Any]],
    *,
    complete: bool,
    now: datetime,
    previous: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Merge the currently-observed forward slots into the append-only history.

    `previous is None` means the history has never been written -- the BOOTSTRAP run, where an
    already-running clock cannot be dated unless its own artifact declares a start.

    Returns `(history, summary)`. The history is a new list; existing rows are carried through by
    reference and only `retired_at` is ever set on them.
    """
    bootstrap = previous is None
    history: list[dict[str, Any]] = [r for r in (previous or []) if isinstance(r, dict)]
    live = _open_rows(history)

    seen: set[tuple[str, str]] = set()
    born: list[str] = []
    for s in slots:
        if not isinstance(s, dict):
            continue
        edge, kind = str(s.get("name", "?")), str(s.get("kind", "?"))
        seen.add((edge, kind))
        if (edge, kind) in live:
            continue
        declared = s.get("started")
        if isinstance(declared, str) and declared.strip():
            promoted_at, provenance = declared.strip(), DECLARED
        elif bootstrap:
            # PRE-EXISTING AND UNDATABLE. Stamping `now` here is the phantom-birth bug this
            # module is built around; None is the honest value and the fence excludes it.
            promoted_at, provenance = None, UNKNOWN
        else:
            promoted_at, provenance = now.isoformat(), OBSERVED
        row = {
            "edge": edge,
            "kind": kind,
            "family": str(s.get("family", kind)),
            "promoted_at": promoted_at,
            "provenance": provenance,
            "first_seen": now.isoformat(),
            "source": s.get("source"),
            "retired_at": None,
        }
        history.append(row)
        live[(edge, kind)] = row
        if provenance != UNKNOWN:
            born.append(edge)

    retired: list[str] = []
    if complete:
        for key, row in live.items():
            if key not in seen:
                row["retired_at"] = now.isoformat()
                retired.append(row["edge"])
    # else: an incomplete read is a LOWER BOUND on the live set. Retiring on it books a false
    # death now and a false birth on the next complete read -- said out loud in the summary.

    undated = sum(1 for r in history if r.get("provenance") == UNKNOWN)
    return history, {
        "rows": len(history),
        "born_this_run": born,
        "retired_this_run": retired,
        "undated_rows": undated,
        "bootstrap": bootstrap,
        "retirement_checked": complete,
        "note": (
            "births are a LOWER BOUND while undated_rows > 0 (clocks already running when the "
            "history was first written carry no derivable start)" if undated else
            "every row is dated -- births are a complete count"),
    }
