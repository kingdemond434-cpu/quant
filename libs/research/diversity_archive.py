"""Quality-diversity archive for research opportunities, never trading admission.

Unlike the formula MAP-Elites grid, this archive spans the entire research funnel.  It keeps a
best representative and the full evidence trail for every source/mechanism/time/behaviour/
portfolio/evidence niche, including failed and blocked work.  That preserves weird useful ground
without weakening the universal gates.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any

DIMENSIONS = ("information_source", "economic_mechanism", "time_structure", "behavior",
              "portfolio_relationship", "evidence_state")
EVIDENCE_ORDER = {"UNTESTED": 0, "DATA_BLOCKED": 1, "ACCESS_BLOCKED": 1, "INCONCLUSIVE": 2,
                  "FAILED": 2, "TESTED": 3, "CERTIFIED": 4, "FORWARD_SUPPORTED": 5,
                  "LIVE_SUPPORTED": 6}


def _first(*values: Any, default: str = "UNCLASSIFIED") -> str:
    for value in values:
        if value not in (None, "", [], {}):
            return str(value)
    return default


def evidence_state(row: Mapping[str, Any]) -> str:
    status = str(row.get("status") or "").upper()
    verdict = str(row.get("verdict") or "").upper()
    if verdict in {"FAILED", "REJECTED", "FAIL"}:
        return "FAILED"
    blockers = " ".join(str(x).upper() for x in row.get("blockers") or
                        row.get("unresolved_blockers") or [])
    if "ACCESS" in blockers or "RIGHT" in blockers:
        return "ACCESS_BLOCKED"
    if blockers:
        return "DATA_BLOCKED"
    # Enrollment is lifecycle state, not evidence.  Support requires an explicit measured sample
    # and a positive result; otherwise SHADOW/FORWARD/LIVE merely says where observation occurs.
    try:
        raw_n = row.get("forward_trades", row.get("n_forward", row.get("n_trades")))
        count = float(raw_n)
        forward_n = (int(count) if not isinstance(raw_n, bool) and math.isfinite(count)
                     and count.is_integer() and count > 0 else 0)
    except (TypeError, ValueError, OverflowError):
        forward_n = 0
    forward_r = row.get("forward_r")
    measured_forward = forward_n > 0
    try:
        if forward_r is None:
            raise ValueError("forward result is unmeasured")
        result = float(forward_r)
        forward_positive = (not isinstance(forward_r, bool) and math.isfinite(result)
                            and result > 0.0)
    except (TypeError, ValueError):
        measured_forward = False
        forward_positive = False
    if (status == "LIVE" and row.get("live_supported") is True
            and measured_forward and forward_positive):
        return "LIVE_SUPPORTED"
    if status in {"FORWARD", "SHADOW", "LIVE"} and measured_forward and forward_positive:
        return "FORWARD_SUPPORTED"
    if verdict in {"SURVIVED", "CERTIFIED", "ELIGIBLE", "PASS"}:
        return "CERTIFIED"
    if status in {"FORWARD", "SHADOW", "LIVE"} or measured_forward:
        return "TESTED" if measured_forward else "UNTESTED"
    if verdict and verdict != "UNJUDGED":
        return "TESTED"
    return "UNTESTED"


def descriptor(row: Mapping[str, Any]) -> dict[str, str]:
    source = _first(row.get("source_type"), row.get("source"), row.get("generator"),
                    row.get("origin"))
    mechanism = _first(row.get("mechanism"), row.get("mechanism_id"), row.get("family"))
    time_structure = _first(row.get("event_clock"), row.get("session"), row.get("chart"),
                            row.get("horizon"))
    behavior = _first(row.get("behavior"), row.get("direction"), row.get("method"),
                      row.get("representation"))
    portfolio = _first(row.get("portfolio_relationship"), row.get("independence_bucket"),
                       row.get("asset_class"), row.get("symbol"))
    return {"information_source": source, "economic_mechanism": mechanism,
            "time_structure": time_structure, "behavior": behavior,
            "portfolio_relationship": portfolio, "evidence_state": evidence_state(row)}


def item_id(row: Mapping[str, Any]) -> str:
    named = _first(row.get("experiment_id"), row.get("candidate_id"), row.get("lead_id"),
                   row.get("input_version_id"), default="")
    if named:
        return named
    payload = json.dumps(dict(row), sort_keys=True, default=str).encode()
    return hashlib.sha256(payload).hexdigest()[:20]


def niche_key(desc: Mapping[str, str]) -> str:
    return "|".join(str(desc[name]) for name in DIMENSIONS)


def quality(row: Mapping[str, Any]) -> tuple[int, float, float]:
    """Evidence first, then measured portfolio value and information value; missing is zero."""
    state = evidence_state(row)
    de = float(row.get("delta_elogw") or row.get("live_delta_elogw") or 0.0)
    info = float(row.get("information_gain") or row.get("novelty") or 0.0)
    return EVIDENCE_ORDER[state], de, info


def update(archive: Mapping[str, Any] | None, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    old = dict(archive or {})
    items = dict(old.get("items") or {})
    niches = dict(old.get("niches") or {})
    for row in rows:
        iid = item_id(row)
        desc = descriptor(row)
        key = niche_key(desc)
        record: dict[str, Any] = {"item_id": iid, "descriptor": desc, "quality": list(quality(row)),
                  "source": _first(row.get("source"), row.get("generator"), row.get("origin")),
                  "lineage": row.get("lineage") or row.get("parent_lineages") or [],
                  "blockers": row.get("blockers") or row.get("unresolved_blockers") or [],
                  "verdict": row.get("verdict"), "status": row.get("status"),
                  "falsifier": row.get("falsifier"),
                  "authority": "archive only; universal gauntlet and forward evidence judge"}
        previous = items.get(iid)
        if previous:
            history = list(previous.get("history") or [])
            snap = {k: previous.get(k) for k in ("quality", "verdict", "status", "blockers")}
            if snap not in history:
                history.append(snap)
            record["history"] = history[-50:]
        else:
            record["history"] = []
        items[iid] = record
        niche = dict(niches.get(key) or {"descriptor": desc, "members": [], "champion": None})
        niche["members"] = sorted({*niche.get("members", []), iid})
        champion = niche.get("champion")
        if champion is None or tuple(record["quality"]) > tuple(items[champion]["quality"]):
            niche["champion"] = iid
        niches[key] = niche
    # Rebuild derived membership from current items. An updated verdict must not leave the
    # same candidate championing its old CERTIFIED/FORWARD niche indefinitely.
    niches = {}
    for iid, record in items.items():
        key = niche_key(record["descriptor"])
        niche = niches.setdefault(key, {"descriptor": record["descriptor"],
                                       "members": [], "champion": iid})
        niche["members"].append(iid)
        champion = niche["champion"]
        if tuple(record["quality"]) > tuple(items[champion]["quality"]):
            niche["champion"] = iid
    for niche in niches.values():
        niche["members"].sort()
    failed = sum(r["descriptor"]["evidence_state"] == "FAILED" for r in items.values())
    blocked = sum(r["descriptor"]["evidence_state"].endswith("BLOCKED") for r in items.values())
    return {"schema": 1, "dimensions": list(DIMENSIONS), "items": items, "niches": niches,
            "counts": {"items": len(items), "occupied_niches": len(niches),
                       "failed_preserved": failed, "blocked_preserved": blocked},
            "rule": "preserve research diversity; never convert archive membership into admission"}
