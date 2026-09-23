"""One-shot: retire sleeve identities frozen on a TRANSPORT string, not a venue.

WHY A MIGRATION RATHER THAN A QUIET RE-BLESS. Every row in the registry was frozen with
`data_venue` = `Bars.source`, the route the bars arrived by. That is not the quantity the
identity check claims to hold fixed, so those rows never constituted a valid pre-registration
of the venue. The fix (h1_source.Bars.evidence_venue) changes what the field means, and a row
whose meaning changed is not the row that was frozen.

The two-stage law's answer to that is a NEW frozen identity and a NEW window, so this script
takes it literally and does the CONSERVATIVE thing at every choice:

  * the legacy rows are ARCHIVED in-file under `archived_identities`, never deleted -- the audit
    trail of what was frozen, when, and why it was retired survives (evidence is preserved; only
    authority is withdrawn);
  * `forward_start` is CLEARED in the shadow state, so the next run starts the clock at NOW.
    Days accrued under the old identity are forfeited rather than inherited. This can only ever
    LOSE forward days, never manufacture them -- it cannot bring a promotion closer;
  * trade ledgers on disk are untouched.

Idempotent: rows already carrying a venue-shaped `data_venue` are left alone, so a second run
is a no-op and cannot re-base a clock that is legitimately running.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "research"))
import sleeve_registry as _reg  # noqa: E402
REGISTRY = BASE / "data" / "sleeve_registry.json"
SHADOW_STATE = BASE / "reports" / "shadow" / "shadow_state.json"

#: A route string, never a venue. These are exactly the prefixes `Bars.source` emits for a
#: retrieval path; a venue is "MT5:<server>" or "HTTP:<feed>".
_ROUTE_PREFIXES = ("CACHE:", "HTTP:yfinance/")

#: THE TEST IS THE SCHEMA STAMP, NOT THE STRING. A row frozen under the old semantics can happen
#: to LOOK venue-shaped -- every current row reads "MT5:FusionMarkets-Live" because it was frozen
#: on the Windows box while its terminal was up -- yet it is still a `Bars.source` value and still
#: not a pre-registration of the venue. Measured 2026-08-26: those rows are replayed on this box
#: from a parquet cache that broker_info.json says came from FusionMarkets-DEMO, so the string
#: test alone would have re-blessed a genuine Live-vs-Demo venue mismatch as intact.

REASON = (f"frozen on Bars.source (a RETRIEVAL ROUTE) rather than the evidence venue; the field "
          f"changed meaning when h1_source.Bars.evidence_venue landed, so this row is no longer "
          f"a pre-registration of the venue it appears to name. Re-freezes under schema "
          f"{_reg.IDENTITY_SCHEMA}")


def _is_route(venue: str) -> bool:
    """A frozen venue that names a file or a per-ticker URL is a route, not a venue."""
    return venue.startswith(_ROUTE_PREFIXES)


def main() -> int:
    if not REGISTRY.exists():
        print("no registry -- nothing to migrate")
        return 0
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = reg.get("sleeves", {})
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")

    retired: list[str] = []
    for key, row in list(rows.items()):
        ident = row.get("identity") or {}
        venue = str(ident.get("data_venue") or "")
        # A row is legacy if its frozen venue is a route, OR if it was killed by the very drift
        # this fix removes -- those two sets are the whole broken cohort and neither can be
        # rescued by leaving it in place: the first names the wrong thing, the second is already
        # terminal and nothing in the codebase clears an IDENTITY_BROKEN status.
        stale_schema = row.get("identity_schema") != _reg.IDENTITY_SCHEMA
        if not (stale_schema or _is_route(venue)):
            continue
        reg.setdefault("archived_identities", []).append(
            {**row, "sleeve_key": key, "archived_at": now, "archived_why": REASON})
        rows.pop(key)
        retired.append(key)

    if not retired:
        print("no legacy identities -- registry already venue-shaped (no-op)")
        return 0

    reg["updated_at"] = now
    REGISTRY.write_text(json.dumps(reg, indent=1, default=str), encoding="utf-8")

    cleared = 0
    if SHADOW_STATE.exists():
        state = json.loads(SHADOW_STATE.read_text(encoding="utf-8"))
        for key in retired:
            st = state.get(key)
            if isinstance(st, dict) and st.get("forward_start"):
                st["forward_start"] = None
                st["forward_start_reset_why"] = REASON
                st["forward_start_reset_at"] = now
                cleared += 1
        SHADOW_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")

    print(f"retired {len(retired)} legacy identity row(s) to archived_identities; "
          f"cleared {cleared} forward_start stamp(s) -- the next shadow run freezes a venue-shaped "
          f"identity and starts a NEW 14-day window at that moment")
    for k in retired:
        print(f"  - {k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
