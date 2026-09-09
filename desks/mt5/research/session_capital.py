"""THE CLOCK'S CAPITAL: which hours of the day hold the book's heat, and which hours are empty.

MEASURED 2026-09-08 (Tier-1 programme item P18): the desk runs ONE heat budget per pass for the
whole clock. The session narrows a sleeve's posterior and decides which allocator is authorised,
but no session has a budget of its own, so heat that goes unfilled in the Asia band is not heat
the London band can bid for -- it is simply heat nobody spent. Nothing anywhere reports it.

A SESSION CAPITAL MARKET NEEDS A DENOMINATOR BEFORE IT NEEDS AN AUCTION, and this desk has
already paid for the other order (a compute allocator whose formula divided by hours nobody had
recorded). So this module reports, per four-hour band of the day:

    held_heat            heat the allocator's book actually holds in that band
    positive_marginal    the sum of positive marginal dE[log W] the allocator priced there
    certificates         certified sleeves whose window falls in the band
    funded_sleeves       how many of them carry heat
    realised_r           realised R booked in that band, from the live ledger

and then names the bands where the book is UNDERSPENT: positive marginal value priced, heat
available at the portfolio level, and little or no heat held. That list is what an auction
would bid on, and it is also a research mission in its own right -- an empty band with no
certificates is a generator's target, not an allocator's.

DECIDES NOTHING. No sizing, no cap, no shrink. The bands are read from the allocator's own
report through `portfolio_gap`'s window map, so this file and the gap report cannot disagree
about which hour a sleeve trades.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(REPO), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

ALLOC = BASE / "reports" / "pf_allocation.json"
SURVIVORS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
LEDGER = BASE / "data" / "live_ledger.jsonl"
OUT = BASE / "reports" / "session_capital.json"

#: A band is "underspent" when the allocator priced value there and the book holds nearly none
#: of its heat in it. Both numbers come from the allocator's own report.
UNDERSPENT_HEAT_SHARE = 0.05


def _read(path: Path) -> dict[str, Any]:
    try:
        d = json.loads(path.read_text("utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _ledger_by_band(path: Path, hour_of: Any) -> dict[str, dict[str, float]]:
    """Realised R per band, from the live ledger's closed rows. Absent file -> {}."""
    out: dict[str, dict[str, float]] = defaultdict(lambda: {"n": 0.0, "r": 0.0})
    try:
        text = path.read_text("utf-8")
    except OSError:
        return {}
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        r = row.get("realized_r", row.get("r_multiple"))
        stamp = row.get("closed_at") or row.get("at") or row.get("time")
        if not isinstance(r, (int, float)) or isinstance(r, bool) or not stamp:
            continue
        try:
            d = datetime.fromisoformat(str(stamp))
        except ValueError:
            continue
        band = hour_of(d.hour)
        out[band]["n"] += 1
        out[band]["r"] += float(r)
    return {k: {"n": int(v["n"]), "r": round(v["r"], 4),
                "mean_r": round(v["r"] / v["n"], 4) if v["n"] else None}
            for k, v in out.items()}


def build(alloc: dict[str, Any], survivors: list[dict[str, Any]],
          ledger: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    from portfolio_gap import BANDS, band_of, sleeve_axes, window_hours
    now = now or datetime.now(tz=UTC)
    hours = window_hours()
    book = {str(k): float(v) for k, v in (alloc.get("book") or {}).items()}
    marginal = {str(k): float(v) for k, v in (alloc.get("marginal_delta_elog") or {}).items()}
    heat = alloc.get("heat") or {}
    target = float(heat.get("target") or 0.0)
    held_total = float(heat.get("total") or 0.0)

    names = [f"{lo:02d}-{hi:02d}" for lo, hi in BANDS]
    bands: dict[str, dict[str, Any]] = {
        b: {"held_heat": 0.0, "positive_marginal": 0.0, "certificates": 0, "funded_sleeves": 0,
            "symbols": set()} for b in names}

    def _band(key: str) -> dict[str, Any]:
        return bands.setdefault(key, {"held_heat": 0.0, "positive_marginal": 0.0,
                                      "certificates": 0, "funded_sleeves": 0, "symbols": set()})

    for s in survivors:
        b = _band(band_of(hours.get(str(s.get("window") or ""), -1)))
        b["certificates"] += 1
        b["symbols"].add(str(s.get("symbol") or "?"))
    for name, h in book.items():
        ax = sleeve_axes(name)
        b = _band(band_of(hours.get(ax["window"], -1)))
        b["held_heat"] += h
        b["funded_sleeves"] += 1
        b["symbols"].add(ax["symbol"])
    for name, mv in marginal.items():
        if mv > 0:
            ax = sleeve_axes(name)
            _band(band_of(hours.get(ax["window"], -1)))["positive_marginal"] += mv

    realised = _ledger_by_band(ledger or LEDGER, band_of)
    unfilled = round(max(0.0, target - held_total), 6)
    rows = []
    for name, b in bands.items():
        share = round(b["held_heat"] / held_total, 4) if held_total else None
        rows.append({
            "band": name, "held_heat": round(b["held_heat"], 6), "heat_share": share,
            "positive_marginal": round(b["positive_marginal"], 8),
            "certificates": b["certificates"], "funded_sleeves": b["funded_sleeves"],
            "symbols": sorted(b["symbols"])[:8], "realised": realised.get(name),
        })
    rows.sort(key=lambda r: r["band"])
    underspent = [r for r in rows
                  if r["positive_marginal"] > 0 and unfilled > 0
                  and (r["heat_share"] is None or r["heat_share"] < UNDERSPENT_HEAT_SHARE)]
    dark = [r for r in rows if r["certificates"] == 0 and r["funded_sleeves"] == 0]
    return {
        "at": now.isoformat(timespec="seconds"), "bands": rows,
        "target_heat": target, "held_heat": held_total, "unfilled_heat": unfilled,
        "underspent_bands": [r["band"] for r in underspent],
        "dark_bands": [r["band"] for r in dark],
        "measured": bool(book or survivors),
        "why": ("one heat budget serves the whole clock; a band with priced value and almost no "
                "held heat is capital the day never bid for. Report only -- no sizing, no cap"),
        "consumer": "the allocator wave (a session auction), portfolio_gap's missions",
    }


def main(argv: list[str] | None = None) -> int:
    alloc = _read(ALLOC)
    surv_doc = _read(SURVIVORS)
    survivors = []
    certs = surv_doc.get("survivors")
    if isinstance(certs, dict):
        for row in certs.values():
            spec = (row or {}).get("shadow_spec") or {}
            survivors.append({"symbol": row.get("sym") or spec.get("symbol"),
                              "window": spec.get("selector") or "",
                              "family": spec.get("family") or row.get("family")})
    doc = build(alloc, survivors)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"session capital: held {doc['held_heat']:.4f} of target {doc['target_heat']:.4f}; "
          f"underspent {doc['underspent_bands'] or 'none'}; dark {doc['dark_bands'] or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
