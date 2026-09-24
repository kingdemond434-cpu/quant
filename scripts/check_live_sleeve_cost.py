#!/usr/bin/env python3
"""LIVE-SLEEVE COST FENCE (L1.5 / L1.28a / L2.10) -- is every clock the desk calls LIVE priced?

A NULL COST IS NOT A ZERO COST, AND THAT DISTINCTION IS THE WHOLE DEFECT. A sleeve marked LIVE
is one the desk is trading with real money right now. Its `cost_fields` are the numeric basis the
clock froze with, and the forward engine replays the whole series against them every pass. When
they are ABSENT, `shadow_forward` line 758 (`if _ff:`) falls straight through to LIVE re-measured
costs -- so the row does not read as free, it reads as a clock whose cost basis moves under it
roughly twice a day. That is precisely the identity churn the frozen basis exists to prevent, and
it is invisible: no artifact anywhere said "this LIVE row has no cost".

MEASURED ON THE TRADING BOX 2026-09-24 (account 495044, FusionMarkets-Live, 355 LIVE rows):

    13 LIVE rows carried NO cost_fields at all -- 8 of them XAUUSD, covering the asia,
       london_am and afternoon gold windows, which are essentially the desk's entire realised
       P&L. Every one of the 13 was frozen by `desks/mt5/scripts/heal_identity_broken_clocks.py`,
       the ONE `sleeve_registry.freeze()` caller that omitted the `cost_fields=` argument that
       `shadow_forward` has always passed.

     1 LIVE row carried its FAMILY AND SELECTOR THE WRONG WAY ROUND:
       `XAUUSD.multi_speed_trend.continuous@D1` froze as
       `family=session_range_breakout, selector=multi_speed_trend`. Same cause, same script:
       `legacy_identity` hardcoded the hunt16 family and read slot 1 as a window, and its guard
       rejected only keys containing `=` or `#`, so a modern `SYM.family.selector@TF` key with
       empty params fell through. 20+ RETIRED rows carry the same swap.

WHY THE SWAP IS NOT COSMETIC. The canonical identity is `symbol|family|selector` lowercased --
what the sealed gauntlet stamps and what the promoter matches on. A row whose family and selector
are transposed cannot join its own certificate, its allocator cell or its ledger, and every join
it participates in silently misses. It is detectable because a SELECTOR names a window
(`asia`, `london_am`, `continuous`); a selector that is itself a REGISTERED FAMILY NAME is a
transposition, and the vocabulary is taken from the registry's own `identity.family` values so
this fence cannot drift away from the store it is judging.

NO RATCHET, DELIBERATELY. Every other cost fence on this desk carries a shrink-only declaration,
because a fence that is red on day one gets switched off (L1.43) and the debt it names lives in
files its author does not own. This one is different on both counts: the defect is a LIVE row on
the money path, and the repair is local and safe -- the writer is fixed so no new row is born
null, and the residue is thirteen rows a named repair can clear. A declaration here would be the
softening the defect does not deserve.

WHAT IT DOES NOT DO. It never sizes, vetoes, retires or disables anything. A sleeve that is LIVE
stays LIVE and stays traded; this reports that the desk cannot say what it is being charged.

  OK                (exit 0) -- every LIVE row carries a complete, finite cost basis and an
                               identity whose selector is not a family name.
  NULL-COST         (exit 2) -- a LIVE row has absent, null, non-finite or incomplete
                               `cost_fields`. UNMEASURED is a real answer, never a clean one.
  IDENTITY-SWAPPED  (exit 2) -- a LIVE row's selector is a registered family name.
  UNMEASURED        (exit 2) -- the registry parsed but holds no LIVE row to judge. Never OK:
                               absence is not a clean verdict (L1.28a / WS-005).
  NOT-READABLE-HERE (exit 0) -- no sleeve registry on this host. A verdict about the HOST, never
                               folded into OK.

Run: python scripts/check_live_sleeve_cost.py [--json] [--registry PATH] [--report PATH]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.fence_exit import fence_exit  # noqa: E402

_DESK = _ROOT / "desks" / "mt5"
REGISTRY = _DESK / "data" / "sleeve_registry.json"
#: The gateway's own roster. Measured and published beside the registry because its LIVE rows
#: carry no cost field in ANY row -- the schema has never had one -- so it is reported as a
#: named observation rather than a failure. Failing on a field a file never carried is how a
#: fence becomes noise; leaving it unmeasured is how the desk stopped noticing.
GATEWAY_ROSTER = _DESK / "data" / "sleeves.json"
REPORT = _DESK / "reports" / "LIVE_SLEEVE_COST.json"

#: The four numbers `mt5desk.engine.Costs` needs to charge a round trip. `shadow_forward`
#: requires exactly this set before it will use a frozen basis at all (`_frozen_costs`), so the
#: fence and the engine agree on what "priced" means by construction.
REQUIRED = ("spread_per_lot", "commission_per_lot", "contract_oz", "quote_per_account")
#: Fields that are a DIVISOR or a scale in the charge and are therefore meaningless at zero.
#: `spread_per_lot` and `commission_per_lot` may legitimately be 0.0 -- Fusion Zero genuinely
#: quotes 0.0 spread on EURUSD for 95% of M1 bars, measured on this account.
POSITIVE = ("contract_oz", "quote_per_account")

OK, NULL_COST, SWAPPED, UNMEASURED, NOT_READABLE = (
    "OK", "NULL-COST", "IDENTITY-SWAPPED", "UNMEASURED", "NOT-READABLE-HERE")
_PASSING = frozenset({OK, NOT_READABLE})


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _rows(registry: Any) -> dict[str, dict[str, Any]]:
    """key -> row, for whichever shape the registry is on disk."""
    sleeves = registry.get("sleeves") if isinstance(registry, dict) else registry
    if isinstance(sleeves, dict):
        return {str(k): v for k, v in sleeves.items() if isinstance(v, dict)}
    if isinstance(sleeves, list):
        return {str(i): v for i, v in enumerate(sleeves) if isinstance(v, dict)}
    return {}


def family_vocabulary(rows: dict[str, dict[str, Any]]) -> set[str]:
    """Every family name the registry itself uses, over ALL rows and not only the LIVE ones.

    DERIVED FROM THE STORE BEING JUDGED, never a hardcoded list. A second vocabulary maintained
    beside the first is the producer collapse that put three different meanings into
    `median_spread_pts`; this one cannot drift because it IS the registry's own answer.
    RETIRED rows are included on purpose: a family retired yesterday is still a family name, and
    excluding it would make the swap detector quietly weaker every time a clock is retired.
    """
    out: set[str] = set()
    for row in rows.values():
        fam = (row.get("identity") or {}).get("family")
        if isinstance(fam, str) and fam.strip():
            out.add(fam.strip())
    return out


def cost_defect(row: dict[str, Any]) -> str | None:
    """Why this row's frozen cost basis cannot be used, or None when it is complete and finite."""
    cf = row.get("cost_fields")
    if cf is None:
        return "cost_fields absent"
    if not isinstance(cf, dict) or not cf:
        return "cost_fields empty"
    missing = [f for f in REQUIRED if f not in cf]
    if missing:
        return f"cost_fields missing {', '.join(missing)}"
    for field in REQUIRED:
        value = cf.get(field)
        if value is None:
            return f"{field} is null"
        try:
            num = float(value)
        except (TypeError, ValueError):
            return f"{field} is not numeric ({value!r})"
        if not math.isfinite(num):
            return f"{field} is not finite ({value!r})"
        if field in POSITIVE and num <= 0:
            return f"{field} is {num} -- a scale of zero prices nothing"
    return None


def swap_defect(row: dict[str, Any], families: set[str]) -> str | None:
    """Why this row's identity reads transposed, or None when family and selector are in place."""
    ident = row.get("identity") or {}
    family = ident.get("family")
    selector = ident.get("selector")
    if not isinstance(selector, str) or not isinstance(family, str):
        return None
    if selector.strip() and selector.strip() in families and selector.strip() != family.strip():
        return (f"selector {selector!r} is a registered family name while family reads "
                f"{family!r} -- family and selector are transposed")
    return None


def scan(registry_path: Path = REGISTRY, roster_path: Path = GATEWAY_ROSTER) -> dict[str, Any]:
    """Judge every LIVE row. Returns the report; never writes and never changes a row."""
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    registry = _load(registry_path)
    if registry is None:
        return {"status": NOT_READABLE, "at": now, "n_live": 0,
                "why": f"no readable sleeve registry at {registry_path}",
                "registry": str(registry_path), "null_cost": [], "swapped": []}
    rows = _rows(registry)
    families = family_vocabulary(rows)
    live = {k: r for k, r in rows.items() if str(r.get("status") or "").upper() == "LIVE"}

    null_cost, swapped = [], []
    for key, row in sorted(live.items()):
        ident = row.get("identity") or {}
        base = {"key": key, "symbol": ident.get("symbol"), "family": ident.get("family"),
                "selector": ident.get("selector"),
                "canonical_identity": row.get("canonical_identity"),
                "frozen_at": row.get("frozen_at")}
        why = cost_defect(row)
        if why:
            null_cost.append({**base, "why": why, "cost_fields": row.get("cost_fields")})
        swap = swap_defect(row, families)
        if swap:
            swapped.append({**base, "why": swap})

    roster = _load(roster_path)
    roster_rows = _rows(roster) if roster is not None else {}
    roster_live = [r for r in roster_rows.values()
                   if str(r.get("status") or "").upper() == "LIVE"]

    status = OK
    if not live:
        status = UNMEASURED
    elif null_cost:
        status = NULL_COST
    elif swapped:
        status = SWAPPED

    return {
        "status": status, "at": now, "registry": str(registry_path),
        "n_rows": len(rows), "n_live": len(live),
        "n_null_cost": len(null_cost), "n_swapped": len(swapped),
        "n_families_in_vocabulary": len(families),
        "null_cost": null_cost, "swapped": swapped,
        "gateway_roster": {
            "path": str(roster_path),
            "n_live": len(roster_live),
            "carries_a_cost_field": any(
                f in r for r in roster_rows.values() for f in REQUIRED),
            "note": ("the gateway roster has never carried a cost field in its schema; its rows "
                     "are priced by the terminal at fill. Published so the gap is named rather "
                     "than assumed fine -- it is not counted as a failure here."),
        },
        "repair": {
            "writer": ("desks/mt5/scripts/heal_identity_broken_clocks.py now passes "
                       "cost_fields=cost_fields_for(symbol) and resolves slot 1 against the "
                       "engine's own family registry, so no new row is born null or transposed"),
            "residue": ("rows already frozen are NOT repaired by that fix -- freeze() is "
                        "idempotent by the row's presence. sleeve_registry.rebase_cost refuses "
                        "them too (it fires on a sole cost_hash drift and these legacy "
                        "identities carry no cost_hash), so clearing the residue is a named "
                        "act on the box, not a side effect of this fence"),
        },
        "why": (f"{len(null_cost)} LIVE row(s) cannot say what they are charged; "
                f"{len(swapped)} carry a transposed family/selector"),
    }


def render(rep: dict[str, Any]) -> str:
    lines = [f"LIVE-SLEEVE COST: {rep['status']}",
             f"  registry {rep.get('registry')}",
             f"  LIVE rows {rep.get('n_live')} of {rep.get('n_rows')}"]
    if rep["status"] == NOT_READABLE:
        return "\n".join([*lines, f"  {rep.get('why')}"])
    lines.append(f"  null/absent cost basis: {rep.get('n_null_cost')}")
    for row in (rep.get("null_cost") or [])[:20]:
        lines.append(f"    {row['key']}  [{row['symbol']}]  {row['why']}")
    lines.append(f"  transposed family/selector: {rep.get('n_swapped')}")
    for row in (rep.get("swapped") or [])[:20]:
        lines.append(f"    {row['key']}  {row['why']}")
    roster = rep.get("gateway_roster") or {}
    lines.append(f"  gateway roster LIVE {roster.get('n_live')} "
                 f"(carries a cost field: {roster.get('carries_a_cost_field')})")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Is every LIVE sleeve priced?")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    ap.add_argument("--registry", type=Path, default=REGISTRY)
    ap.add_argument("--roster", type=Path, default=GATEWAY_ROSTER)
    ap.add_argument("--report", type=Path, default=REPORT)
    args = ap.parse_args(argv)

    rep = scan(args.registry, args.roster)
    try:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(rep, indent=1, default=str), "utf-8")
    except OSError:
        pass
    print(json.dumps(rep, indent=1, default=str) if args.json else render(rep))
    # THE ZERO-DENOMINATOR GUARD APPLIES TO THE DESK, NOT TO THE HOST. `scanned` refuses a pass
    # over nothing examined, which is exactly right for a registry that parsed and held no LIVE
    # row -- and exactly wrong for NOT-READABLE-HERE, where the honest verdict is that this
    # machine has no registry at all. Passing 0 there would turn a statement about the HOST into
    # a failure of the DESK, which is the confusion this status exists to prevent.
    scanned = None if rep["status"] == NOT_READABLE else rep.get("n_live")
    return fence_exit(rep["status"], _PASSING, scanned=scanned,
                      of="LIVE rows in sleeve_registry.json", fence="check_live_sleeve_cost")


if __name__ == "__main__":
    raise SystemExit(main())
