"""PER-SOURCE HORIZON, DECAY AND SESSION TRANSFER (DATA-46, 2026-10-07).

A state the desk reads -- a central-bank decision, a COT print, a swap reprice, a Korean export
figure -- moves an MT5 price over a window it can plausibly reach and no other. Before this every
candidate was expanded onto every chart and every session alike, so a weekly positioning print
was minted as an M5 cell beside an H1 one, and a Tokyo release was tested in New York with no
record that the cell was a TRANSFER test rather than an own-session one.

`libs/mining/source_horizons.json` declares, per producing seat: `min_h` / `max_h` (the window the
state can reach), `decay_half_life_h` (how fast it fades), `release_session` (where it lands) and
`release` (when and in which timezone it is published). A row or candidate may override any horizon
key. From that:

  chart_fit      INSIDE when the chart fits at least MIN_BARS bars inside `max_h` and `min_h`
                 spans at most MAX_BARS bars of it; OUTSIDE otherwise; UNDECLARED with no row.
                 The compiler DEMOTES an OUTSIDE cell in queue order and never drops it:
                 research generation is never reduced, backpressure reorders (standing rule).
  transfer cells for a seat with a SCHEDULED release (`libs/mining/release_clock.py`), the
                 compiler mints NEW cells `release_gate = "<seat>:<k>"`: the same rule, kept
                 only in the k-th session after the release instant (k = 0 is the release's own
                 session), only once the state is public, and only while it keeps
                 `release_clock.DECAY_FLOOR` of its strength by `decay_half_life_h`. Each is its
                 own identity (the gate is in `params`), so it is charged once like any cell and
                 re-minted to the same id every hour. A seat whose release is row-dated mints no
                 transfer cell and is reported UNSCHEDULED: a session label with no release
                 instant behind it would claim a transfer test it cannot run.
  resolve        a cell two seats produce gets the most permissive fit among them (lowest
                 demotion), ties by seat name, so the label never depends on intake order.

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


def annotate(cell: dict[str, Any], chart: str, session: str = "all",
             seat: str | None = None) -> int:
    """Stamp a minted cell with its source horizon; returns the queue demotion (0 or 2) the
    compiler adds to its priority. Never removes the cell."""
    del session                            # the transfer test is a cell of its own now
    name = seat or seat_of(cell)
    decl = declared(name, cell)
    fit = chart_fit(chart, decl)
    demotion = 2 if fit == "OUTSIDE" else 0
    cell["source_horizon"] = {"fit": fit, "seat": name or None, "demotion": demotion,
                              **{k: (decl or {}).get(k) for k in _KEYS}}
    return demotion


def resolve(cell: dict[str, Any], sources: list[str]) -> None:
    """Re-label a cell several seats produced: the lowest demotion among them, ties broken by
    seat name. Adjusts `priority` by the difference; nothing else changes."""
    chart = str((cell.get("axis") or {}).get("chart") or "")
    stamp = cell.get("source_horizon")
    if not chart or not isinstance(stamp, dict):
        return
    old = int(stamp.get("demotion") or 0)
    best: tuple[int, str] | None = None
    for src in sorted(set(sources)):
        seat = src.split(":", 1)[1] if src.startswith("miner:") else src
        d = 2 if chart_fit(chart, declared(seat, cell)) == "OUTSIDE" else 0
        if best is None or (d, seat) < best:
            best = (d, seat)
    if best is None:
        return
    annotate(cell, chart, seat=best[1])
    cell["source_horizon"]["resolved_from"] = sorted(set(sources))
    cell["priority"] = int(cell.get("priority") or 0) - old + int(best[0])


def tally(cells: list[dict[str, Any]]) -> dict[str, Any]:
    fit = Counter(str((c.get("source_horizon") or {}).get("fit") or "UNSTAMPED") for c in cells)
    gates = Counter(str((c.get("params") or {}).get("release_gate")) for c in cells
                    if (c.get("params") or {}).get("release_gate"))
    seats = sorted({str((c.get("source_horizon") or {}).get("seat") or "") for c in cells} - {""})
    try:
        from libs.mining import release_clock
        releases: dict[str, Any] = {s: release_clock.describe(s) for s in seats}
    except Exception as exc:                # a broken clock costs the report, never a cell
        releases = {"state": f"UNMEASURED: {type(exc).__name__}: {exc}"}
    return {"fit": dict(fit), "transfer_cells": dict(sorted(gates.items())),
            "releases": releases,
            "rule": f"INSIDE = >= {MIN_BARS} bars inside max_h and min_h <= {MAX_BARS} bars; "
                    "OUTSIDE cells are demoted in queue order, never dropped; transfer cells "
                    "trade only after the release instant, in the k-th session after it",
            "table": str(TABLE.relative_to(TABLE.parents[2]))}
