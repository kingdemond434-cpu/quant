"""Exact identity and economic-prior rules shared by discovery and the universal gauntlet."""
from __future__ import annotations

import hashlib
import json


def cell_id(cell: dict) -> str:
    """Executable identity; arbitrary DSL parameters must never collapse onto rr=?/wb=? IDs."""
    params = dict(cell.get("params") or {})
    # THE LEGACY SHORT FORM IS ONLY SAFE WHEN rr/wait_bars ARE THE WHOLE PARAMETER SET.
    # It used to fire whenever EITHER key was present, so every other parameter collapsed out
    # of the identity -- measured 2026-08-29 on H-20260828-005, where 24 distinct trials
    # (3 symbols x 2 rr x 2 ttl_bars x 2 directions) printed as 8 ids, three cells deep each,
    # with opposite-signed Sharpes under the SAME name. The docstring above already forbade
    # exactly this; the branch predicate did not enforce it. Anything richer than {rr,
    # wait_bars} now takes the digest form, so no historical id whose params were only those
    # two keys changes value.
    if params and set(params) <= {"rr", "wait_bars"}:
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
