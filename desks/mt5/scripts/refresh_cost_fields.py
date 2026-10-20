#!/usr/bin/env python3
"""Fill `tick_value` for every registry symbol from the live terminal. Runs on the desk box.

THE GAP THIS CLOSES (measured 2026-08-27). 82 of 197 registry rows carried no `tick_value` --
67 Equities, 15 Indices, 23 uncategorised. That field is the only one carrying a price in ACCOUNT
currency, so `spread_cost_per_lot` returns 0.0 without it and gate 8 (stress_costs) cannot judge
the candidate at all. 42% of the desk's own universe was therefore structurally incapable of
producing a certificate, however many bars it had -- and L1.5 is explicit that no alpha is valid
until it survives realistic costs.

WHY IT WAS EMPTY, AND WHY DERIVATION CANNOT FIX IT. The only producer that ever wrote
`tick_value` (`fetch_universe.py`) carries a HARDCODED 32-symbol list -- the anti-hardcode law's
exact target (LAWS §1): a literal list that silently caps exploration. The producers that do
cover all 197 read `symbol_info` on every iteration and threw the field away.
`universe_registry.backfill_tick_values` can DERIVE one, but only when the quote currency is
known, and for a share or index CFD the name ("3M", "AUS200") carries no code to parse -- so
derivation returns None by design rather than guessing a denomination. The terminal is the only
honest source, and it has had the answer in hand the whole time.

MERGE, NEVER CLOBBER. Writes through `universe_registry.merge`, and a degenerate reading
(`trade_tick_value == 0.0`, which is what a symbol with no fresh tick reports) is OMITTED rather
than written, so this organ can never delete a good prior value. A symbol the terminal cannot
answer for is REPORTED as still-missing, never filled with a guess: absence is not a clean
verdict, and a made-up cost is worse than a known gap because the gauntlet would believe it.

Registry-driven: the symbol list comes from the registry itself, so this organ never needs
editing when the universe changes.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import argparse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from mt5desk.universe_registry import cost_fields_from_symbol_info, merge  # noqa: E402

REGISTRY = BASE / "data" / "universe" / "universe.json"
OUT = BASE / "data" / "cost_field_refresh.json"


def refresh(registry: dict[str, Any], mt5: Any, *, symbols: set[str] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (merged registry, report). Pure apart from the mt5 reads, so it is testable."""
    incoming: dict[str, Any] = {}
    unanswered: list[str] = []
    for sym in sorted(k for k, v in registry.items() if isinstance(v, dict)
                      and (symbols is None or k in symbols)):
        try:
            mt5.symbol_select(sym, True)
            info = mt5.symbol_info(sym)
        except Exception:
            info = None
        if info is None:
            unanswered.append(sym)
            continue
        # FILL-ONLY, NEVER OVERWRITE. `cost_hash` is part of sleeve identity, so replacing a
        # symbol's existing `tick_value` with the terminal's would flip the hash and break every
        # live forward clock on it TERMINALLY -- eleven were IDENTITY_BROKEN that way once
        # already. Measured 2026-08-27: all 7 live-clock symbols carry DERIVED values close to
        # but not equal to the terminal's, so a blanket refresh would have broken all of them.
        # Adopting terminal truth where a derived value already exists is a real improvement and
        # a genuinely separate decision -- it must enter at the NEXT window as a new identity,
        # never be smuggled into a gap-filling pass.
        present = registry.get(sym) or {}
        fields = {k: v for k, v in cost_fields_from_symbol_info(info).items()
                  if present.get(k) in (None, 0, 0.0, "")}
        # The promoter's live cost identity includes both financing directions. These are
        # genuine broker terms even when one direction is zero; keep the broker's mode too.
        for key in ("swap_long", "swap_short", "swap_mode"):
            value = getattr(info, key, None)
            if value is not None and present.get(key) is None:
                fields[key] = value
        if fields:
            incoming[sym] = fields
        elif present.get("tick_value") in (None, 0, 0.0):
            unanswered.append(sym)

    before = sum(1 for v in registry.values()
                 if isinstance(v, dict) and v.get("tick_value") is not None)
    merged = merge(registry, incoming, source="refresh_cost_fields")
    after = sum(1 for v in merged.values()
                if isinstance(v, dict) and v.get("tick_value") is not None)
    still = sorted(k for k, v in merged.items()
                   if isinstance(v, dict) and v.get("tick_value") is None)
    report: dict[str, Any] = {
        "checked_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "rows": len(registry), "costable_before": before, "costable_after": after,
        "filled": after - before, "terminal_unanswered": len(unanswered),
        "still_uncostable": still,
    }
    return merged, report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="*", help="restrict broker refresh to these registry symbols")
    args = ap.parse_args()
    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("refresh_cost_fields: MetaTrader5 unavailable -- this organ runs on the desk box")
        return 2
    if mt5.terminal_info() is None and not mt5.initialize():
        print(f"refresh_cost_fields: terminal unavailable {mt5.last_error()}")
        return 2
    wanted = set(args.symbols) if args.symbols else None
    for attempt in range(3):
        try:
            before = REGISTRY.read_bytes()
            registry = json.loads(before)
        except (OSError, ValueError) as exc:
            print(f"refresh_cost_fields: registry unreadable ({exc}) -- REFUSING to write")
            return 2
        merged, report = refresh(registry, mt5, symbols=wanted)
        if REGISTRY.read_bytes() != before:
            continue  # an independent collector wrote meanwhile; recompute on its new state
        fd, tmp = tempfile.mkstemp(prefix=".cost-refresh-", suffix=".json", dir=REGISTRY.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                json.dump(merged, out, indent=2)
            if REGISTRY.read_bytes() != before:
                continue
            os.replace(tmp, REGISTRY)
        finally:
            if Path(tmp).exists():
                Path(tmp).unlink()
        break
    else:
        print("refresh_cost_fields: registry changed three times -- refusing to clobber")
        return 2
    OUT.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"refresh_cost_fields: costable {report['costable_before']} -> "
          f"{report['costable_after']} of {report['rows']} "
          f"(+{report['filled']}); {len(report['still_uncostable'])} still uncostable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
