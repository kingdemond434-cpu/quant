"""CANONICAL SLEEVE REGISTRY -- one exact identity, frozen at the clock, verified every cycle.

WHY ONE REGISTRY (principal 2026-08-26). The desk carried a sleeve's identity in five different
shapes at once: a display cell name in the certificate, a `(symbol, selector, condition, family,
is_universe)` tuple in admission, a `SYM.window` key in the forward state, a `sleeves.json` name
in the gateway, and a row label on the dashboard. Nothing forced them to agree, and they did not:
the dashboard reported 37 sleeves while the admission door authorised 6 and the reconciler found
26 of the 37 were stopped clocks. Worse, `shadow_spec` omitted the PARAMS, so five separately
gauntleted XAUUSD variants shared one identity and four were never forward-tested at all. When
identity is ambiguous, every count downstream is a different question answered with the same word.

WHAT AN IDENTITY IS HERE. Everything that, if changed, makes the forward evidence describe a
different strategy:

    family x instrument x direction x timeframe/session x regime/condition x params
          x code_hash (the signal function's own source)
          x cost_hash (spread/commission model actually applied)
          x data_identity (which venue's bars, on which clock)

`code_hash` and `cost_hash` are the two most people leave out and the two that fail silently. A
family function edited mid-window, or a cost model widened, changes what the sleeve DOES without
touching any name or parameter -- and the forward series then splices two different strategies
into one expectancy. That is not a smaller sample, it is a wrong one.

FREEZE, THEN VERIFY. `freeze()` records the identity when the clock starts. `verify()` recomputes
it every cycle and returns the fields that drifted. A drifted sleeve is NOT silently re-based and
NOT deleted: its clock is stopped (`IDENTITY_BROKEN`) and its accrued evidence is preserved for
audit, because evidence collected under a different identity is real evidence about a different
thing. Restarting means a NEW frozen identity and a NEW window -- never inheriting the old clock.

The registry is the single source every consumer reads: shadow health, the reconciler, the
promoter, the dashboard and execution. Absence is never permission -- an unregistered sleeve has
no identity, and a sleeve with no identity cannot promote.
"""
from __future__ import annotations

import hashlib
import inspect
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
REGISTRY = BASE / "data" / "sleeve_registry.json"

#: Fields whose drift invalidates a running clock. Order is fixed so the hash is stable.
IDENTITY_FIELDS = ("family", "symbol", "direction", "timeframe", "selector", "condition",
                   "params", "code_hash", "cost_hash", "data_venue")

#: WHAT THE FIELDS MEAN, versioned. A frozen row records the schema it was frozen under, because
#: a field can change MEANING without changing shape and that is invisible to every comparison
#: here. It happened: `data_venue` used to hold `Bars.source` -- the ROUTE the bars arrived by --
#: so a row frozen from a live terminal read "MT5:<server>" while the identical evidence replayed
#: from the parquet cache read "CACHE:<file>", and every clock broke terminally on every run the
#: Windows box was down. It now holds `Bars.evidence_venue`, WHOSE PRINTS the bars are. Rows
#: frozen under an older schema are not pre-registrations of the new quantity and must not be
#: silently re-blessed; `scripts/migrate_identity_venue.py` archives them and starts a NEW window.
IDENTITY_SCHEMA = "venue-2026-08-26"


def _read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text("utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def code_hash(fn: Any) -> str:
    """Hash of the signal function's own source -- the thing a parameter name cannot capture.

    Falls back to the qualified name when source is unavailable (C extensions, exec'd code): a
    weaker identity is still an identity, and pretending we hashed source we could not read would
    be worse than recording that we could not.
    """
    try:
        src = inspect.getsource(fn)
    except (OSError, TypeError):
        return "nosrc:" + getattr(fn, "__qualname__", str(fn))
    # THE FUNCTION'S OWN SOURCE, NOT ITS REGISTRATION. inspect.getsource includes decorator
    # lines, so adding @register_family (search-grid metadata -- param grids, tags) to a family
    # would have broken every live clock on it (nearly happened 2026-08-27: the decorator landed
    # while 15 fresh windows were running). A decorator changes how the SEARCH enumerates the
    # family, never what the frozen sleeve executes; identity starts at the def line.
    lines = src.splitlines(keepends=True)
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith(("def ", "async def ")):
            src = "".join(lines[i:])
            break
    return hashlib.sha256(src.encode("utf-8")).hexdigest()[:16]


def cost_hash(costs: Any) -> str:
    """Hash of the cost model actually applied. Widening costs mid-window changes the strategy."""
    try:
        fields = {k: round(float(v), 6) for k, v in vars(costs).items()
                  if isinstance(v, (int, float)) and not isinstance(v, bool)}
    except TypeError:
        return "nocost"
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()[:16]


def identity(*, family: str, symbol: str, direction: str = "LONG", timeframe: str = "H1",
             selector: str = "", condition: str | None = None,
             params: dict | None = None, code: str = "", cost: str = "",
             data_venue: str = "") -> dict:
    """Build the canonical identity dict plus its stable id."""
    ident = {
        "family": str(family), "symbol": str(symbol), "direction": str(direction).upper(),
        "timeframe": str(timeframe), "selector": str(selector),
        "condition": condition or None,
        "params": {k: params[k] for k in sorted(params or {})},
        "code_hash": code, "cost_hash": cost, "data_venue": data_venue,
    }
    blob = json.dumps({k: ident[k] for k in IDENTITY_FIELDS}, sort_keys=True, default=str)
    ident["sleeve_id"] = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]
    return ident


def freeze(key: str, ident: dict, *, forward_start: str | None = None,
           cost_fields: dict | None = None) -> dict:
    """Record the identity for `key` if absent; return the FROZEN identity (never the new one).

    Idempotent by construction: a second freeze on a live key returns what was already frozen, so
    a caller cannot re-base a running clock by calling this again.

    `cost_fields` are the NUMERIC cost-model values the clock froze with, stored so the forward
    engine can keep RUNNING the window on that exact basis. Without them the engine rebuilt costs
    from live universe metadata every cycle, and the spread re-measure (~2x/day) changed
    cost_hash and terminally broke every clock mid-window -- identity churn, not identity
    protection. The doctrine stands: a certificate's cost basis IS part of the strategy, so the
    window runs on the frozen basis and a re-measured cost enters at the NEXT window as a new
    identity, never spliced into a running one. Real execution is judged by markouts regardless.
    """
    reg = _read(REGISTRY)
    rows = reg.setdefault("sleeves", {})
    if key in rows and rows[key].get("identity"):
        return rows[key]["identity"]
    rows[key] = {
        "identity": ident,
        "identity_schema": IDENTITY_SCHEMA,
        "frozen_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "forward_start": forward_start,
        "status": "LIVE",
    }
    if cost_fields:
        rows[key]["cost_fields"] = {k: round(float(v), 6) for k, v in cost_fields.items()
                                    if isinstance(v, (int, float)) and not isinstance(v, bool)}
    reg["updated_at"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(reg, indent=1, default=str), "utf-8")
    return ident


def frozen_cost_fields(key: str) -> dict | None:
    """The numeric cost basis `key` froze with, or None for rows frozen before it was stored."""
    row = _read(REGISTRY).get("sleeves", {}).get(key) or {}
    fields = row.get("cost_fields")
    return dict(fields) if isinstance(fields, dict) and fields else None


def verify(key: str, ident: dict) -> list[str]:
    """Return the identity fields that have DRIFTED since freezing. Empty list means intact."""
    row = _read(REGISTRY).get("sleeves", {}).get(key)
    if not row or not row.get("identity"):
        return []                       # never frozen -- freeze() is the caller's next move
    frozen = row["identity"]
    return [f for f in IDENTITY_FIELDS
            if json.dumps(frozen.get(f), sort_keys=True, default=str)
            != json.dumps(ident.get(f), sort_keys=True, default=str)]


def mark(key: str, status: str, why: str) -> None:
    """Record a terminal or degraded state against a registered sleeve, with its reason."""
    reg = _read(REGISTRY)
    row = reg.setdefault("sleeves", {}).setdefault(key, {})
    row["status"] = status
    row["status_why"] = why
    row["status_at"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
    reg["updated_at"] = row["status_at"]
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(reg, indent=1, default=str), "utf-8")


def live_keys() -> set[str]:
    """Keys the registry considers live -- the ONE answer to 'how many sleeves are running'."""
    return {k for k, v in _read(REGISTRY).get("sleeves", {}).items()
            if str(v.get("status") or "").upper() == "LIVE"}


def snapshot() -> dict:
    """Registry summary for dashboards and health, so they stop counting rows for themselves."""
    rows = _read(REGISTRY).get("sleeves", {})
    by_status: dict[str, int] = {}
    for v in rows.values():
        s = str(v.get("status") or "UNKNOWN").upper()
        by_status[s] = by_status.get(s, 0) + 1
    return {"total": len(rows), "by_status": by_status,
            "live": sorted(live_keys()),
            "note": "the registry is the only authority on sleeve identity and count"}
