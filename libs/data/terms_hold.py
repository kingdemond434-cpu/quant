"""THE TERMS HOLD -- which sources' numbers may reach the gauntlet (audit #204 item 4, #211).

A held source is MEASURED AND KEPT: its rows are stored, counted and written to the sensor ledger
as state. What it may not do until its terms are cleared is reach a gauntlet cell, a conditioning
key or a donation. `libs.data.terms_fence` (#162) is a block list and is consulted first when it
is present; this module adds the named holds whose machine-use terms are UNMEASURED and the
clearance record that lifts them. Unknown sources pass: a hold on named terms, not a whitelist.

One door: `release_vintages`, `event_surprise`, `market_state` and every world-sensor engine's
`sensor_engines.emit_conditioner_cells` call `gauntlet_terms` and nothing else.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
#: Where a cleared source is recorded: {"<held key>": {"status": "CLEARED", "by": ..., "why": ...}}
#: written by whoever clears the terms (the global data thread's terms work, #162).
CLEARANCES = ROOT / "desks" / "mt5" / "data" / "terms_clearances.json"

TERMS_HELD: dict[str, str] = {
    "ff_calendar": "Forex Factory survey median: machine-use terms UNMEASURED",
    "forexfactory": "Forex Factory survey median: machine-use terms UNMEASURED",
    "faireconomy": "Forex Factory survey median (faireconomy mirror): terms UNMEASURED",
    "tradingeconomics": "Trading Economics calendar: commercial terms, machine use not cleared",
    "yahoo": "Yahoo Finance chart API: its terms restrict automated use; machine use UNCLEARED",
    "cboe": "CBOE index values (VIX family): CBOE copyright; machine use for trading UNCLEARED",
}


def gauntlet_terms(source_id: str, clearances: Path | None = None) -> tuple[bool, str]:
    """(may this source's numbers reach the gauntlet?, why)."""
    sid = str(source_id or "").lower()
    try:
        from libs.data import terms_fence as tf  # type: ignore[attr-defined]
        fenced = tf.fenced_source(sid)
        if fenced:
            return False, f"terms fence: {fenced}"
    except Exception:
        pass
    for key, why in TERMS_HELD.items():
        if key in sid:
            try:
                doc = json.loads((clearances or CLEARANCES).read_text("utf-8"))
            except (OSError, ValueError):
                doc = {}
            row = doc.get(key) if isinstance(doc, dict) else None
            if isinstance(row, dict) and str(row.get("status")) == "CLEARED":
                return True, f"cleared: {row.get('why') or row.get('by') or 'recorded'}"
            return False, f"HELD_TERMS: {why}"
    return True, ""


__all__ = ["CLEARANCES", "TERMS_HELD", "gauntlet_terms"]
