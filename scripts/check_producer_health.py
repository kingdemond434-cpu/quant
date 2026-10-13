#!/usr/bin/env python3
"""THE PRODUCER-HEALTH FENCE -- nothing goes stale or unwired without the gate saying so.

    "hourly make sure all sources and producers produce nth is stale n unwired n etc"
                                                                  -- the principal, 2026-10-13

Reads `desks/mt5/reports/PRODUCER_HEALTH.json` (`research/producer_health.py`, hourly) and FAILS,
naming every lane:

  * REGRESSION: a lane that was LIVE at the previous reading and is STALE now, or was WIRED and
    is UNWIRED now. This is the "something just stopped" alarm.
  * RATCHET: more clocked STALE lanes, or more clocked UNWIRED lanes, than the ratchet the organ
    carries (which may only fall).

The standing backlog -- every clocked STALE and UNWIRED lane -- is printed loudly every run as a
WARN with the counts and names, and every one of them carries an upgrade action in the report.
Failing on the raw backlog would be red from the first pass and switched off inside a week; the
ratchet makes the backlog's direction the law.

PORTABLE BY DEFAULT: no report reads UNMEASURED and passes. `--require-state` (box): an absent,
unmeasured or stale (> STALE_H) report FAILS -- the census stopping is itself a stale producer.

    python scripts/check_producer_health.py [--require-state] [--report PATH] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "desks" / "mt5" / "reports" / "PRODUCER_HEALTH.json"
STALE_H = 6.0


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def judge(report: Path | None = None, *, require_state: bool = False,
          now: datetime | None = None) -> dict[str, Any]:
    at = now or datetime.now(tz=UTC)
    doc = _read(report or REPORT)
    out: dict[str, Any] = {"at": at.isoformat(timespec="seconds"), "failures": [],
                           "warnings": []}
    fail, warn = out["failures"], out["warnings"]
    if not isinstance(doc, dict) or doc.get("verdict") != "MEASURED":
        why = ("PRODUCER_HEALTH.json absent or unreadable" if not isinstance(doc, dict)
               else f"PRODUCER_HEALTH UNMEASURED: {doc.get('why')}")
        (fail if require_state else warn).append(why)
        out["verdict"] = "FAIL" if require_state else "UNMEASURED"
        return out
    try:
        gen = datetime.fromisoformat(str(doc.get("generated_utc")).replace("Z", "+00:00"))
        age = (at - (gen if gen.tzinfo else gen.replace(tzinfo=UTC))).total_seconds() / 3600
    except ValueError:
        age = None
    out["report_age_h"] = round(age, 2) if age is not None else None
    if require_state and (age is None or age > STALE_H):
        fail.append(f"PRODUCER_HEALTH.json stale ({out['report_age_h']}h > {STALE_H}h)")
    c: Mapping[str, Any] = doc.get("counts") or {}
    out["counts"] = dict(c)
    for r in doc.get("regressions") or []:
        fail.append(f"REGRESSION {r.get('lane')}: {r.get('went')}"
                    + (f" ({', '.join(r.get('because') or [])})" if r.get("because") else ""))
    rp = doc.get("ratchet_previous") or {}
    for k in ("clocked_stale", "clocked_unwired"):
        if isinstance(rp.get(k), int) and int(c.get(k) or 0) > int(rp[k]):
            fail.append(f"RATCHET {k}: {c.get(k)} > {rp[k]} at the previous reading")
    if c.get("clocked_stale") or c.get("clocked_unwired"):
        warn.append(f"STALE {c.get('clocked_stale')} / UNWIRED {c.get('clocked_unwired')} of "
                    f"{c.get('clocked')} clocked lanes ({c.get('lanes')} in the roster); each "
                    f"carries an upgrade action. stale e.g. "
                    + ", ".join((doc.get("stale_clocked_sample") or [])[:10]))
    out["actions_by_kind"] = doc.get("actions_by_kind")
    out["verdict"] = "FAIL" if fail else "OK"
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--require-state", action="store_true")
    ap.add_argument("--report", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    doc = judge(Path(a.report) if a.report else None, require_state=bool(a.require_state))
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        print(f"producer health fence: {doc['verdict']}  {doc.get('counts') or ''}")
        for r in doc["failures"]:
            print(f"  FAIL  {r}")
        for r in doc["warnings"]:
            print(f"  WARN  {r}")
    return 1 if doc["verdict"] == "FAIL" else 0


if __name__ == "__main__":                                              # pragma: no cover
    sys.exit(main())
