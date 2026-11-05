"""Each account's sizing charged at ITS OWN venue's spread (Judge, 2026-11-05).

`desks/mt5/research/cost_truth.py` writes one quotes file per venue,
`data/cost_truth_quotes.<venue slug>.json`, and a cross-venue max for the Judge's gate. The gate
charges the dearest venue a certificate can land on; SIZING charges each account its own venue,
so the dE[log W] an account is sized on is net of the spread that account actually pays.

ONE MECHANISM FOR EVERY ACCOUNT. The allocators already price execution as a ratio of the venue's
measured spread at the sleeve's fill hour to the spread the replay charged
(`execution_cost.cost_ratio` for Fusion, `prop_challenge_allocator.venue_cost_bias` for FTMO),
reading a cost surface: {"symbols": {sym: {"hours": {"H": {"status", "p50"}}}}} in that venue's
points. `overlay_surface` lays the venue's own quotes file over that surface, hour by hour, in
the same units, so neither allocator's pricing changes shape: only the venue's number gets
truer. An hour the quotes file has not measured keeps the surface's own cell; a missing file
changes nothing.
"""
from __future__ import annotations

import copy
import json
import statistics
from collections.abc import Mapping
from pathlib import Path
from typing import Any

MEASURED = "MEASURED"

#: Readings an hour needs before the venue's quotes may price it. DERIVATION: the smallest count
#: whose median is not a single reading -- cost_truth keeps up to HOUR_KEEP (14) readings per
#: venue, symbol and UTC hour precisely so that "one rollover spike must not become the hour's
#: price on its own", and a median of fewer than three readings can be exactly that spike.
MIN_HOUR_READINGS = 3


def venue_quotes(data_dir: Path, venue: str) -> tuple[dict[str, Any] | None, Path | None]:
    """The quotes file whose venue slug names `venue` ("fusion", "ftmo", "e8"), or (None, None).
    The cross-venue max file is the Judge's and is never an account's own; two files naming the
    same venue resolve to the one written most recently."""
    token = str(venue).lower()
    best: tuple[str, dict[str, Any], Path] | None = None
    for p in sorted(Path(data_dir).glob("cost_truth_quotes.*.json")):
        slug = p.name[len("cost_truth_quotes."):-len(".json")]
        if slug == "max" or token not in slug:
            continue
        try:
            doc = json.loads(p.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(doc, dict):
            continue
        at = str(doc.get("at") or "")
        if best is None or at > best[0]:
            best = (at, doc, p)
    return (best[1], best[2]) if best else (None, None)


def hour_spreads_pts(doc: Mapping[str, Any] | None,
                     min_n: int = MIN_HOUR_READINGS) -> dict[str, dict[str, dict[str, Any]]]:
    """{symbol: {hour "H": {"p50": median spread in THIS venue's points, "n": readings}}} for every
    hour with at least `min_n` readings. A symbol whose point size the file does not carry is
    left out (its price units cannot be turned into the surface's points)."""
    out: dict[str, dict[str, dict[str, Any]]] = {}
    if not isinstance(doc, Mapping):
        return out
    syms = doc.get("symbols") or {}
    for sym, per in (doc.get("spread_by_hour_utc") or {}).items():
        raw = (syms.get(sym) or {}).get("point")
        if not isinstance(raw, (int, float, str)):
            continue
        try:
            point = float(raw)
        except ValueError:
            continue
        if not point > 0 or not isinstance(per, Mapping):
            continue
        for hh, seq in per.items():
            vals = [float(x[1]) for x in (seq or [])
                    if isinstance(x, (list, tuple)) and len(x) == 2
                    and isinstance(x[1], (int, float)) and float(x[1]) >= 0]
            if len(vals) < int(min_n):
                continue
            out.setdefault(str(sym), {})[str(int(hh))] = {
                "p50": statistics.median(vals) / point, "n": len(vals)}
    return out


def overlay_surface(surface: Mapping[str, Any] | None, doc: Mapping[str, Any] | None, *,
                    source: str = "", min_n: int = MIN_HOUR_READINGS) -> dict[str, Any] | None:
    """`surface` with every hour the venue's quotes measured replaced by the venue's own median,
    in the venue's points. Returns the surface unchanged (a copy) when there is no quotes file,
    and None only when there is neither. Each replaced cell is labelled with its source and n."""
    hours = hour_spreads_pts(doc, min_n)
    if surface is None and not hours:
        return None
    out: dict[str, Any] = copy.deepcopy(dict(surface)) if surface else {"symbols": {}}
    out.setdefault("symbols", {})
    n_cells = 0
    for sym, per in hours.items():
        row = out["symbols"].setdefault(sym, {})
        cells = row.setdefault("hours", {})
        for h, v in per.items():
            cells[h] = {**(cells.get(h) or {}), "status": MEASURED, "p50": v["p50"],
                        "n_quotes": v["n"], "source": source or "venue quotes"}
            n_cells += 1
    out["venue_quotes"] = {"source": source, "at": (doc or {}).get("at") if doc else None,
                           "venue": (doc or {}).get("venue") if doc else None,
                           "cells_overlaid": n_cells}
    return out


def account_surface(data_dir: Path, venue: str,
                    surface: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """The cost surface an account on `venue` is sized on: its own quotes file over `surface`."""
    doc, path = venue_quotes(data_dir, venue)
    return overlay_surface(surface, doc, source=path.name if path else "")
