#!/usr/bin/env python3
"""Append one day of PER-MECHANISM returns. The missing link in the rho chain.

WHY THIS EXISTS: THE CHAIN WAS BROKEN AND THE BREAK WAS SILENT

`track_sleeve_correlation.py` measures the cross-mechanism correlation that every growth
projection on this desk rests on. It reads `data/sleeve_returns.json`. NOTHING WROTE THAT FILE.

So the tracker would have sat there printing "nothing to measure yet" forever, looking patient,
while the thing it was waiting for was never going to arrive. That is the worst shape a defect can
take: a component that is correct, wired, scheduled, and starved -- indistinguishable from one
that is simply early.

An empty input read by a working reader is not a pipeline. This is the writer.

WHAT A "MECHANISM RETURN" IS HERE, AND WHY IT IS NOT P&L

The unit is the CENSUS CLASS, not the rule and not the symbol. Seven of the eleven discretionary
rules are `liquidity_provision_immediacy` -- seven triggers on one bet -- and correlating them as
seven streams would report six spurious near-1.0 pairs and inflate every k_eff that follows. The
census is the authority on what a thing tests; this aggregates to it.

Within a class, per-symbol returns are AVERAGED before anything is correlated. Momentum-on-BTC
against momentum-on-ETH is same-mechanism cross-symbol correlation, which the desk already
measured at 0.348 and which is a different question entirely. Averaging first is what makes the
output about MECHANISMS.

WHAT IT REFUSES TO DO

Interpolate. A mechanism that produced no position on a day has NO RETURN that day -- not zero.
Writing 0.0 would say "this bet was made and broke even", which is a claim about a trade that did
not happen, and a run of fabricated zeros drags every correlation toward zero and manufactures
diversification that does not exist. Absent days are simply absent, and the tracker intersects on
common dates.

    python scripts/record_sleeve_returns.py                # append today
    python scripts/record_sleeve_returns.py --date 2026-08-14
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import argparse
import json
from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Any

_OUT = _ROOT / "data" / "sleeve_returns.json"

#: Where per-strategy daily results are published. Each is tried in order and whatever is present
#: is used; a source that is absent is reported, never silently treated as "no return".
_SOURCES = (
    "reports/discretionary_live.json",
    "reports/mechanism_sleeves.json",
    "reports/spot_momentum.json",
    "reports/margin_executor.json",
)


def _census_class(name: str) -> str:
    """Map a rule or generator id to the CENSUS CLASS it actually tests.

    Falls back to the raw name rather than to a catch-all bucket: an unmapped mechanism correlated
    under 'other' with three unrelated things would produce a correlation about nothing.
    """
    try:
        from libs.research.mechanism_census import SUBTYPE_TO_CLASS  # type: ignore
        m = dict(SUBTYPE_TO_CLASS)
    except Exception:
        m = {}
    # The discretionary rules carry their own ids and are not in the generator map.
    m.update({
        "H1_structural_fade": "liquidity_provision_immediacy",
        "H3_ict_sweep_shift": "liquidity_provision_immediacy",
        "H4_auction_value": "liquidity_provision_immediacy",
        "H6_wyckoff": "liquidity_provision_immediacy",
        "H7_vwap_reversion": "liquidity_provision_immediacy",
        "H8_supply_demand": "liquidity_provision_immediacy",
        "H11_band_fade": "liquidity_provision_immediacy",
        "H2_volume_breakout": "price_continuation",
        "H9_opening_range": "price_continuation",
        "H10_vol_compression": "price_continuation",
        "H5_cvd_divergence": "informed_order_flow",
    })
    key = str(name)
    return m.get(key, m.get(key.split("[")[0], key))


def _rows_from(doc: Any) -> list[tuple[str, float]]:
    """(mechanism_or_rule_id, daily_return) pairs from one report, shape-tolerantly."""
    out: list[tuple[str, float]] = []
    if not isinstance(doc, dict):
        return out
    for key in ("returns", "sleeves", "strategies", "rules", "positions"):
        block = doc.get(key)
        if isinstance(block, dict):
            for k, v in block.items():
                r = v.get("return") if isinstance(v, dict) else v
                if isinstance(r, (int, float)):
                    out.append((str(k), float(r)))
        elif isinstance(block, list):
            for row in block:
                if not isinstance(row, dict):
                    continue
                k = row.get("mechanism") or row.get("rule_id") or row.get("name")
                r = row.get("return") or row.get("daily_return") or row.get("pnl_frac")
                if k and isinstance(r, (int, float)):
                    out.append((str(k), float(r)))
    return out


def collect(root: Path) -> tuple[dict[str, float], list[str]]:
    """Today's return per CENSUS CLASS, and a note per source that could not be read."""
    per_class: dict[str, list[float]] = defaultdict(list)
    notes: list[str] = []
    for rel in _SOURCES:
        p = root / rel
        if not p.exists():
            notes.append(f"{rel}: absent")
            continue
        try:
            doc = json.loads(p.read_text("utf-8"))
        except (OSError, ValueError) as exc:
            notes.append(f"{rel}: unreadable ({type(exc).__name__})")
            continue
        rows = _rows_from(doc)
        if not rows:
            notes.append(f"{rel}: no return rows in a readable file")
            continue
        for name, r in rows:
            per_class[_census_class(name)].append(r)
        notes.append(f"{rel}: {len(rows)} row(s)")
    # AVERAGE WITHIN A CLASS. Seven triggers on one bet is one bet.
    return ({k: sum(v) / len(v) for k, v in per_class.items() if v}, notes)


def append(day: str, values: dict[str, float], out: Path) -> dict[str, Any]:
    doc: dict[str, Any] = {"what": "daily return per CENSUS MECHANISM CLASS. Absent day = the "
                                   "mechanism produced no position; NEVER written as 0.0.",
                           "streams": {}}
    if out.exists():
        try:
            existing = json.loads(out.read_text("utf-8"))
            if isinstance(existing, dict) and isinstance(existing.get("streams"), dict):
                doc = existing
        except (OSError, ValueError):
            pass                      # a corrupt file is replaced, not appended to blindly
    for mech, r in values.items():
        doc["streams"].setdefault(mech, {})[day] = round(float(r), 8)
    doc["updated"] = datetime.now(tz=UTC).isoformat()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2), "utf-8")
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--out", default=str(_OUT))
    a = ap.parse_args()

    values, notes = collect(_ROOT)
    print("SOURCES")
    for n in notes:
        print(f"  {n}")
    if not values:
        print("\nNo mechanism returns available for this day. Nothing written.\n"
              "  An absent day is ABSENT, not zero: writing 0.0 would claim a bet was\n"
              "  made and broke even, and a run of fabricated zeros drags every\n"
              "  correlation toward zero and manufactures diversification.")
        return 0

    doc = append(a.date, values, Path(a.out))
    print(f"\nRECORDED {a.date}")
    for mech, r in sorted(values.items()):
        n = len(doc["streams"].get(mech, {}))
        print(f"  {mech:<34} {r:>+8.4%}   ({n} day(s) of history)")
    counts = sorted(len(v) for v in doc["streams"].values())
    print(f"\n  {len(doc['streams'])} mechanism(s); shortest stream {counts[0]} day(s)")
    if counts[0] < 30:
        print(f"  rho needs 30 overlapping days -- about {30 - counts[0]} more to go.")
    print(f"-> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
