"""PER-SOURCE HORIZON, DECAY AND SESSION TRANSFER (DATA-46, 2026-10-07).

A state the desk reads -- a central-bank decision, a COT print, a swap reprice, a Korean export
figure -- moves an MT5 price over a window it can plausibly reach and no other. Before this every
candidate was expanded onto every chart and every session alike, so a weekly positioning print
was minted as an M5 cell beside an H1 one, and a Tokyo release was tested in New York with no
record that the cell was a TRANSFER test rather than an own-session one.

`libs/mining/source_horizons.json` declares, per producing seat: `min_h` / `max_h` (the window the
state can reach), `decay_half_life_h` (how fast it fades), and `release_session` (where it lands).
A row or candidate may override any of them with the same keys. From that:

  chart_fit      INSIDE when the chart fits at least MIN_BARS bars inside `max_h` and `min_h`
                 spans at most MAX_BARS bars of it; OUTSIDE otherwise; UNDECLARED with no row.
                 The compiler DEMOTES an OUTSIDE cell in queue order and never drops it:
                 research generation is never reduced, backpressure reorders (standing rule).
  session_transfer  for a source with a `release_session`, every session cell names its path:
                 `own` in the release session, `transfer` k sessions later (asia->london->ny).
                 The cell is the same shared session filter; the label makes the transfer test
                 explicit, countable and charged as its own trial like every other cell.

Undeclared is a real answer (L1.28a): counted UNDECLARED, never read as INSIDE.
"""
from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

TABLE = Path(__file__).resolve().parent / "source_horizons.json"

TF_HOURS: dict[str, float] = {"M1": 1 / 60, "M5": 5 / 60, "M15": 0.25, "M30": 0.5,
                              "H1": 1.0, "H4": 4.0, "D1": 24.0}
#: A chart expresses a state only if at least this many of its bars fit inside the window.
MIN_BARS = 2
#: ...and is too fine once the window's floor spans more than this many of its bars.
MAX_BARS = 96
#: The day's broad sessions in the order a release travels through them.
SESSION_ORDER: tuple[str, ...] = ("asia", "london", "ny")
_KEYS = ("min_h", "max_h", "decay_half_life_h", "release_session")


@lru_cache(maxsize=4)
def _table(path: str) -> dict[str, Any]:
    doc = json.loads(Path(path).read_text("utf-8"))
    return doc if isinstance(doc, dict) else {}


def seat_of(candidate: dict[str, Any]) -> str:
    src = str(candidate.get("source") or "")
    return src.split(":", 1)[1] if src.startswith("miner:") else src


def declared(seat: str, row: dict[str, Any] | None = None,
             path: Path | None = None) -> dict[str, Any] | None:
    """The seat's declaration with any row-level override on top; None when nothing declares."""
    base = dict((_table(str(path or TABLE)).get("seats") or {}).get(seat) or {})
    for k in _KEYS:
        if row and row.get(k) is not None:
            base[k] = row[k]
    if base.get("kind") == "strategy":
        return None                        # a strategy record carries its own horizon
    return base if any(base.get(k) is not None for k in _KEYS) else None


def chart_fit(tf: str, decl: dict[str, Any] | None) -> str:
    if not decl:
        return "UNDECLARED"
    bar = TF_HOURS.get(str(tf).upper())
    if bar is None:
        return "UNDECLARED"
    hi, lo = decl.get("max_h"), decl.get("min_h")
    if hi is not None and bar * MIN_BARS > float(hi):
        return "OUTSIDE"
    if lo is not None and float(lo) > bar * MAX_BARS:
        return "OUTSIDE"
    return "INSIDE"


def session_transfer(decl: dict[str, Any] | None, session: str) -> dict[str, Any] | None:
    rel = str((decl or {}).get("release_session") or "")
    if rel not in SESSION_ORDER or session not in SESSION_ORDER:
        return None
    k = (SESSION_ORDER.index(session) - SESSION_ORDER.index(rel)) % len(SESSION_ORDER)
    return {"from": rel, "to": session, "lag_sessions": k, "kind": "own" if k == 0 else "transfer"}


def annotate(cell: dict[str, Any], chart: str, session: str) -> int:
    """Stamp a minted cell with its source horizon and transfer path; returns the queue demotion
    (0 or 2) the compiler adds to its priority. Never removes the cell."""
    decl = declared(seat_of(cell), cell)
    fit = chart_fit(chart, decl)
    cell["source_horizon"] = {"fit": fit, **{k: (decl or {}).get(k) for k in _KEYS}}
    path = session_transfer(decl, session)
    if path:
        cell["session_transfer"] = path
    return 2 if fit == "OUTSIDE" else 0


def tally(cells: list[dict[str, Any]]) -> dict[str, Any]:
    fit = Counter(str((c.get("source_horizon") or {}).get("fit") or "UNSTAMPED") for c in cells)
    paths = Counter(f"{p['from']}->{p['to']}" for c in cells
                    if (p := c.get("session_transfer")))
    return {"fit": dict(fit), "session_transfer_paths": dict(sorted(paths.items())),
            "rule": f"INSIDE = >= {MIN_BARS} bars inside max_h and min_h <= {MAX_BARS} bars; "
                    "OUTSIDE cells are demoted in queue order, never dropped",
            "table": str(TABLE.relative_to(TABLE.parents[2]))}
