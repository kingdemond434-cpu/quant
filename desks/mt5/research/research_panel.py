"""The symbols a discovery organ studies when the live book is empty (2026-11-05).

THE DEFECT. Representation discovery, causal discovery, market ecology, market posteriors and joint
evolution each carried a copy of one `_live_symbols()` that read ONLY the LIVE rows of
data/sleeves.json. Measured on the box on 2026-11-05: that file held 0 LIVE rows (990 RETIRED, 26
STANDBY, because gold trades through the gateway's windows, not through sleeve rows). Every copy
returned an empty list, and each organ did a pass of its hourly work over nothing.
REPRESENTATION_DISCOVERY.json last moved on 10-26, and its 70-second runs since then wrote nothing.

THE PANEL. LIVE sleeves first, then STANDBY sleeves, then the liquid hypothesis-lane core below:
only symbols that have H1 bars, in that order, up to the organ's own limit. A discovery organ
always has ground to test, and the live book still comes first whenever it has rows. Organs whose
job IS the live book (shift_watch, evidence_vault, execution_science, capacity_frontier) keep
reading LIVE only and do not use this.
"""

from __future__ import annotations

import json
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
UNI = DESK / "data" / "universe"
SLEEVES = DESK / "data" / "sleeves.json"

#: Liquid hypothesis-lane instruments (FX majors, metals, two indices, oil): never single names,
#: which are event-lane only for statistical families.
CORE_PANEL: tuple[str, ...] = (
    "EURUSD",
    "USDJPY",
    "XAUUSD",
    "GBPUSD",
    "AUDUSD",
    "USDCAD",
    "USDCHF",
    "NZDUSD",
    "XAGUSD",
    "US500",
    "NAS100",
    "XTIUSD",
)


def sleeve_symbols(status: str, sleeves: Path | None = None) -> list[str]:
    """Distinct symbols of the sleeve rows with `status`, in file order; [] when unreadable."""
    try:
        doc = json.loads((sleeves or SLEEVES).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = doc if isinstance(doc, list) else (doc.get("sleeves") or [])
    out: list[str] = []
    for r in rows:
        if isinstance(r, dict) and str(r.get("status", "")).upper() == status.upper():
            s = str(r.get("symbol") or "").strip()
            if s and s not in out:
                out.append(s)
    return out


def panel_symbols(
    limit: int | None = 12, *, sleeves: Path | None = None, universe: Path | None = None
) -> tuple[list[str], dict[str, int]]:
    """LIVE, then STANDBY, then CORE_PANEL, with H1 bars; and how many came from each."""
    uni = universe or UNI
    out: list[str] = []
    origin = {"live": 0, "standby": 0, "core_panel": 0}
    for name, cands in (
        ("live", sleeve_symbols("LIVE", sleeves)),
        ("standby", sleeve_symbols("STANDBY", sleeves)),
        ("core_panel", list(CORE_PANEL)),
    ):
        for s in cands:
            if limit is not None and len(out) >= limit:
                return out, origin
            if s not in out and (uni / f"{s}_H1.parquet").exists():
                out.append(s)
                origin[name] += 1
    return out, origin
