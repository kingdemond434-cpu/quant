"""Derive executable descendants for banked peer/factor cells with missing inputs.

The old claim is retained. A completed specification is a *new* hypothesis born at
this pass, not a retroactive rewrite of the old cell or its verdict.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from research import discovery_compiler as compiler

FAMILIES = frozenset({*compiler.PEER_KEY_BY_FAMILY, *compiler.FACTOR_FAMILIES})
VERSION = "family-input-descendant-v1"
SAFE_FIELDS = ("source", "producer", "origin", "title", "url", "mechanism",
               "mechanism_status", "mechanism_note", "timeframe", "chart")


def missing(row: dict[str, Any]) -> bool:
    family = str(row.get("family") or "")
    params = row.get("params") or {}
    if family in compiler.FACTOR_FAMILIES:
        return not bool(params.get("factor_symbols"))
    key = compiler.PEER_KEY_BY_FAMILY.get(family)
    return bool(key and not params.get(key))


def derive(rows: list[dict[str, Any]], *, identity: Callable[[dict[str, Any]], str],
           ctx: Any = None, meta: dict[str, Any] | None = None,
           now: datetime | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return new children and a conservation report; never mutate or remove inputs."""
    at = (now or datetime.now(UTC)).astimezone(UTC).isoformat(timespec="seconds")
    targets = [row for row in rows if isinstance(row, dict) and missing(row)]
    report: dict[str, Any] = {"at": at, "version": VERSION, "targets": len(targets),
                              "created": 0, "already_present": 0,
                              "unresolved": 0, "unresolved_by_reason": {}}
    if not targets:
        return [], report
    ctx = ctx if ctx is not None else compiler.build_context()
    meta = meta if meta is not None else compiler._universe_meta()
    present = {identity(row) for row in rows if isinstance(row, dict)}
    children: list[dict[str, Any]] = []
    unresolved: Counter[str] = Counter()
    # Input selection depends on family, traded symbol, chart and this pass's context/meta,
    # never on the parent's entry/exit variant. Cache ONLY the named added leg(s), not a whole
    # completed params object: copying one variant's knobs onto its siblings changes the claim.
    selections: dict[tuple[str, str, str], tuple[str, Any] | None] = {}
    cache_hits = 0
    for row in targets:
        family = str(row.get("family") or "")
        symbol = str(row.get("symbol") or row.get("sym") or "")
        chart = str((row.get("params") or {}).get("timeframe") or row.get("timeframe")
                    or row.get("chart") or "H1").upper()
        if not symbol:
            unresolved["missing_symbol"] += 1
            continue
        try:
            selector = (family, symbol, chart)
            original_params = dict(row.get("params") or {})
            if selector in selections:
                cache_hits += 1
                selected = selections[selector]
                completed = {"params": original_params}
                if selected is not None:
                    added, value = selected
                    completed["params"][added] = deepcopy(value)
                    completed["input_completed"] = added
            else:
                completed = compiler.complete_inputs({"symbol": symbol, "family": family,
                                                      "chart": chart,
                                                      "params": original_params}, ctx, meta)
                added = completed.get("input_completed")
                selections[selector] = ((added, deepcopy(completed["params"][added]))
                                        if added else None)
        except Exception as exc:
            unresolved[f"compiler_error:{type(exc).__name__}"] += 1
            continue
        if not completed.get("input_completed"):
            unresolved[f"no_compatible_input_on_{chart}"] += 1
            continue
        # Never carry an old verdict, backtest statistic, certification, or registry candidate
        # identifier onto a newly specified claim. Only source/mechanism provenance survives.
        child = {key: row[key] for key in SAFE_FIELDS if key in row}
        child.update({"symbol": symbol, "family": family, "params": completed["params"],
                      "timeframe": chart})
        child["input_completed"] = completed["input_completed"]
        child["input_descendant"] = {"version": VERSION,
                                     "parent_identity": identity(row), "at": at}
        child["available_time"] = at
        child["ingested_time"] = at
        child["source_version"] = VERSION
        # The new point-in-time stamp covers the completed executable specification.
        payload = {"symbol": symbol, "family": family, "chart": chart,
                   "params": child["params"], "parent_identity": identity(row),
                   "version": VERSION}
        child["payload_hash"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        key = identity(child)
        if key in present:
            report["already_present"] += 1
            continue
        present.add(key)
        children.append(child)
    report["created"] = len(children)
    report["unresolved"] = sum(unresolved.values())
    report["unresolved_by_reason"] = dict(unresolved)
    report["input_selection"] = {
        "unique_selections": len(selections), "cache_hits": cache_hits,
        "basis": "one context/meta snapshot per pass; only added legs cached"}
    assert report["targets"] == (report["created"] + report["already_present"]
                                  + report["unresolved"])
    return children, report
