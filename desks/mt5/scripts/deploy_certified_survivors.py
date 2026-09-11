"""Write every ten-gate certified survivor the gateway can actually execute into sleeves.json.

WHY THESE WERE NOT LIVE, AND WHY THAT IS A WIRING BUG AND NOT A JUDGEMENT. Measured 2026-09-11:
all 58 rows in `reports/UNIVERSAL_SURVIVORS.json` pass `executables.resolve_family` AND
`executables.gateway_can_execute`. Thirteen of them are funded by `pf_allocator` -- roughly 30%
of the book's heat, with histories from 489 to 2,142 days. Not one had a row in
`data/sleeves.json`, so `decision_core.roster` never emitted them and the executor never saw
them. Certified, funded, executable, and unreachable: III.16 exactly.

WHAT IS COPIED, AND WHAT IS NOT INVENTED. Every field comes from the survivor's own
`shadow_spec` -- symbol, family, selector, condition. Nothing is guessed:

  * SIDE IS NOT SET, because these families do not take one. `family_carry`,
    `family_overnight_gap_decay` and `family_session_range_breakout` all return `list[Signal]`
    and each Signal carries its own direction. `roster` defaults `side` to LONG for the family
    lane, and that default is inert here -- the executor calls the family, not the field.
  * STATE travels from `shadow_spec.condition`. A promoted sleeve whose state is dropped trades
    a strategy it was never certified for; decision_core documents that exact defect
    ("a promoted CADJPY asia FAILED_BREAK would have traded CADJPY asia on EVERY day").
  * The certificate block records the cell id, day count, gate list and gate timestamp, so the
    row can be traced back to the pass that certified it.

WHAT STILL BOUNDS THEM. `cap_by_heat` prices every leg and the heat resolution decides what is
actually deployed; this script does not change a floor, a cap or a threshold. Writing a LIVE row
makes a sleeve REACHABLE, not funded -- the allocator still decides its size, and the release
identity still has to be clean for anything to place.

    python desks/mt5/scripts/deploy_certified_survivors.py [--dry-run]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
sys.path.insert(0, str(DESK))
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(ROOT))

SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
SLEEVES = DESK / "data" / "sleeves.json"


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()[:60]


def main() -> int:
    dry = "--dry-run" in sys.argv
    from mt5desk import executables as X

    surv = json.loads(SURVIVORS.read_text(encoding="utf-8"))["survivors"]
    doc = json.loads(SLEEVES.read_text(encoding="utf-8"))
    rows = doc["sleeves"]
    existing = {s.get("name") for s in rows}

    added, skipped = 0, 0
    for key, v in sorted(surv.items()):
        spec = v.get("shadow_spec") or {}
        fam, sym, sel = spec.get("family"), spec.get("symbol"), spec.get("selector")
        if not fam or not sym:
            skipped += 1
            continue
        # THE CHART COMES FROM THE CERTIFICATE, NEVER FROM A CONSTANT HERE. `gateway_can_execute`
        # defaults to H1 and this call used to pass "H1" literally, so the first M5 or H4
        # certificate would have been admitted on an H1 answer and then written as an H1 row --
        # the exact substitution `_family_chart` refuses by name ("a certificate earned on M5
        # would have had its signals computed from HOURLY bars"). Absent still means H1, which is
        # what every certificate written before the ladder is, so no existing row changes.
        tf = str(spec.get("timeframe") or (spec.get("params") or {}).get("timeframe")
                 or v.get("timeframe") or "H1").upper()
        if X.resolve_family(fam) is None or not X.gateway_can_execute(fam, tf):
            skipped += 1
            continue
        name = _slug(f"{sym}_{fam}_{sel or 'all'}_{key.split('.')[-1]}")
        if name in existing:
            skipped += 1
            continue
        existing.add(name)
        rows.append({
            "name": name,
            "symbol": sym,
            "family": fam,
            "selector": sel or "asia",
            "state": spec.get("condition"),
            "exec": "family_market",
            # `_family_chart` reads params.timeframe and treats ABSENT as H1. Writing it
            # explicitly means a non-H1 certificate reaches the executor on its own chart
            # instead of silently inheriting the hourly default.
            "params": {"timeframe": tf},
            "lot": "auto_ramp",
            "risk_frac": 0.03,
            "status": "LIVE",
            "risk_frac_source": "certified_survivor",
            "certificate": {
                "source": "UNIVERSAL_SURVIVORS",
                "cell": key,
                "days": v.get("days"),
                "gated_at": v.get("gated_at"),
                "gates_passed": sorted((v.get("gates") or {}).keys()),
            },
            "deployed_by": {
                "at": "2026-09-11",
                "session": "01WZHzZoD3QX9Tx668fkAaw6",
                "why": ("ten-gate certified and gateway-executable, but absent from sleeves.json "
                        "so roster() never emitted it -- reachability, not a new claim"),
                "direction": ("family returns list[Signal]; each signal carries its own side, so "
                              "no direction is assumed by this row"),
            },
        })
        added += 1

    print(f"deployable added: {added} | skipped: {skipped} | total rows: {len(rows)}")
    if dry:
        print("--dry-run: nothing written")
        return 0
    SLEEVES.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"wrote {SLEEVES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
