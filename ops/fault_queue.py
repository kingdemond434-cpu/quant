"""THE BOX FAULT QUEUE -- what the box could not heal by itself, waiting for the next reader.

The box heals what it can with no session involved: `never_stale` starts a stale task and
restarts a stuck research resident. Whatever survives that is a fault a person or a session has
to look at, and until now it lived only in that hour's NEVER_STALE.json, overwritten the next
hour, so a fault that outlived a week without a Claude session was invisible when one came back
(principal 2026-11-18: detection and the common fixes run on the box; anything unresolved is
written down so the next session picks it up FIRST).

This writes `desks/mt5/reports/FAULT_QUEUE.json`, carried off the box by the box-state push:

  open       one row per unresolved fault, with when it was FIRST queued (kept across passes),
             how many passes it has been open and the last error the box saw
  resolved   the last 50 faults that cleared, with when they cleared

A fault is queued when:
  * process_health has read the task bad three or more times in a row (`bad_reads`), whatever
    never_stale did about it -- a plain restart that did not fix it is the case this exists for
  * never_stale escalated it (NEEDS_HUMAN: no restart can fix it)
  * never_stale tried a start or restart and it FAILED
  * a regional deep forest has been IDLE (no claim, no completed pass) in DEEP_FOREST_REGIONS
  * an account ended a market day with zero fills (DAILY_FILLS.json `alarms`)

`last_error` is a fixed-vocabulary line (kind, verdict, exit code): raw error text and paths
stay in the box's own NEVER_STALE.json and process_health.json and are never published here.

Names, verdicts, exit codes and the box's own why-lines only: no secret, no account, no host.

    python ops/fault_queue.py
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "desks" / "mt5" / "reports"
HEALTH = REPORTS / "process_health.json"
NEVER_STALE = REPORTS / "NEVER_STALE.json"
FORESTS = REPORTS / "DEEP_FOREST_REGIONS.json"
DAILY_FILLS = REPORTS / "DAILY_FILLS.json"
OUT = REPORTS / "FAULT_QUEUE.json"
STREAK = 3
KEEP_RESOLVED = 50


def _read(p: Path) -> dict[str, Any]:
    try:
        doc = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _code(verdict: Any, code: Any, kind: str) -> str:
    """A FIXED-VOCABULARY error line (audit HOLD MF1, 2026-11-18). This file is published, and
    never_stale's detail and process_health's why-lines can carry raw schtasks output, exception
    text or paths. Only the verdict, the integer exit code and the fault kind leave the box; the
    full text stays in NEVER_STALE.json and process_health.json on the box."""
    c = code if isinstance(code, int) else None
    return f"{kind}: {verdict or 'UNKNOWN'}" + (f", exit code {c}" if c is not None else "")


def detect(health: dict[str, Any], never_stale: dict[str, Any], forests: dict[str, Any],
           daily_fills: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """fault key -> fault row, for every fault visible in this pass's readings."""
    out: dict[str, dict[str, Any]] = {}
    daily_fills = daily_fills or {}
    for row in health.get("processes") or []:
        if int(row.get("bad_reads") or 0) >= STREAK:
            name = str(row.get("name") or "")
            out[f"streak:{name}"] = {
                "kind": "bad_streak", "task": name, "verdict": row.get("verdict"),
                "code": row.get("last_result_code"), "bad_reads": row.get("bad_reads"),
                "bad_since": row.get("bad_since"), "lane": row.get("lane"),
                "last_error": _code(row.get("verdict"), row.get("last_result_code"),
                                    "bad_streak")}
    for row in never_stale.get("escalated") or []:
        name = str(row.get("task") or "")
        out.setdefault(f"escalated:{name}", {
            "kind": "needs_human", "task": name, "verdict": row.get("verdict"),
            "code": row.get("code"),
            "last_error": _code(row.get("verdict"), row.get("code"), "needs_human")})
    for row in never_stale.get("acted") or []:
        if "FAILED" in str(row.get("action") or ""):
            name = str(row.get("task") or "")
            out.setdefault(f"heal_failed:{name}", {
                "kind": "heal_failed", "task": name, "verdict": row.get("verdict"),
                "action": row.get("action"),
                "last_error": _code(row.get("verdict"), None, str(row.get("action")))})
    # The per-account zero-fill alarms (ops/daily_fills.py, PR #1314) carry their own keys and
    # fixed-code fields; absent until that lands, which adds nothing here.
    for a in daily_fills.get("alarms") or []:
        if isinstance(a, dict) and a.get("key"):
            out[str(a["key"])] = {k: v for k, v in a.items() if k != "key"}
    for row in forests.get("regions") or []:
        if row.get("verdict") == "IDLE":
            fid = str(row.get("forest") or "")
            out[f"forest_idle:{fid}"] = {
                "kind": "forest_idle", "task": row.get("task"), "verdict": "IDLE",
                "last_error": (f"no claim and no completed pass in 24h; newest claim "
                               f"{row.get('newest_claim_at')}, "
                               f"last pass {row.get('watermark_at')}")}
    return out


def merge(previous: dict[str, Any], found: dict[str, dict[str, Any]],
          now: datetime) -> dict[str, Any]:
    at = now.isoformat(timespec="seconds")
    prior = {str(r.get("key")): r for r in previous.get("open") or [] if isinstance(r, dict)}
    open_rows = []
    for key, row in sorted(found.items()):
        old = prior.get(key) or {}
        open_rows.append({"key": key, **row,
                          "first_queued_at": old.get("first_queued_at") or at,
                          "passes_open": int(old.get("passes_open") or 0) + 1,
                          "last_seen_at": at})
    cleared = [{**r, "resolved_at": at} for k, r in prior.items() if k not in found]
    resolved = (cleared + list(previous.get("resolved") or []))[:KEEP_RESOLVED]
    by_kind: dict[str, int] = {}
    for r in open_rows:
        by_kind[r["kind"]] = by_kind.get(r["kind"], 0) + 1
    return {"at": at, "n_open": len(open_rows), "open_by_kind": by_kind,
            "inputs": {"process_health_at": None, "never_stale_at": None},
            "open": sorted(open_rows, key=lambda r: r["first_queued_at"]),
            "resolved": resolved,
            "rule": ("the box heals what it can every hour; every row here is what survived that, "
                     "oldest first. A session reads this FIRST.")}


def build(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    health, ns, forests = _read(HEALTH), _read(NEVER_STALE), _read(FORESTS)
    doc = merge(_read(OUT), detect(health, ns, forests, _read(DAILY_FILLS)), now)
    doc["inputs"] = {"process_health_at": health.get("at") or health.get("generated_at"),
                     "never_stale_at": ns.get("at"), "deep_forest_regions_at": forests.get("at")}
    if not health and not ns:
        doc["status"] = "UNMEASURED"
        doc["why"] = "neither process_health.json nor NEVER_STALE.json is readable on this host"
    else:
        doc["status"] = "OPEN" if doc["n_open"] else "CLEAR"
    return doc


def main() -> int:
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    tmp.replace(OUT)
    print(f"FAULT QUEUE {doc['status']}: {doc['n_open']} open {doc['open_by_kind']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
