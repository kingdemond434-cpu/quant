"""Exact identity and economic-prior rules shared by discovery and the universal gauntlet."""
from __future__ import annotations

import hashlib
import json


def cell_id(cell: dict) -> str:
    """Executable identity; arbitrary DSL parameters must never collapse onto rr=?/wb=? IDs."""
    params = dict(cell.get("params") or {})
    if "rr" in params or "wait_bars" in params:
        return (f"{cell['sym']}.{cell['family']}.rr={params.get('rr', '?')}"
                f"_wb={params.get('wait_bars', '?')}")
    payload = json.dumps(params, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{cell['sym']}.{cell['family']}.p={digest}"


def economic_prior(cell: dict) -> dict:
    """Fail closed for unconstrained statistical finds; named mechanisms remain hypotheses."""
    status = str(cell.get("mechanism_status") or "")
    if not status:
        status = "STATISTICAL_ONLY" if cell.get("family") == "discovered" else "NAMED"
    passed = status == "NAMED"
    return {
        "passed": passed,
        "message": str(cell.get("mechanism_note") or (
            "named registered family" if passed else "statistical discovery has no economic prior"
        )),
        "mechanism_status": status,
    }
