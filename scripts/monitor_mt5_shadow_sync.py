#!/usr/bin/env python3
"""Read-only watchdog for the authoritative Contabo/Fusion shadow state synced to the VPS."""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHADOW = ROOT / "desks" / "mt5" / "reports" / "shadow"
OUT = ROOT / "data" / "shadow_sync_monitor.json"
TERMINAL = {"KILL", "PROMOTED", "DEAD", "REJECTED", "RETIRED", "QUARANTINED"}


def _read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text("utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _terminal(status: object) -> bool:
    text = str(status or "").upper()
    return any(text == prefix or text.startswith(prefix + "_") for prefix in TERMINAL)


def main() -> int:
    now = datetime.now(UTC)
    health = _read(SHADOW / "shadow_health.json")
    files = ("shadow_state.json", "qquant_shadow_state.json", "scalp_shadow_state.json",
             "external_shadow_state.json")
    rows = []
    for name in files:
        doc = _read(SHADOW / name)
        rows.extend((name, key, value) for key, value in doc.items()
                    if isinstance(value, dict) and "status" in value)
        sub = doc.get("sleeves")
        if isinstance(sub, dict):
            rows.extend((name, key, value) for key, value in sub.items()
                        if isinstance(value, dict) and "status" in value)

    defects = []
    try:
        updated = datetime.fromisoformat(str(health["updated_at"]))
        max_age = int(os.environ.get("SHADOW_SYNC_MAX_AGE_SECONDS", "2700"))
        age = max(0.0, (now - updated).total_seconds())
        if age > max_age:
            defects.append(f"shadow health sync stale: {age:.0f}s > configured {max_age}s")
    except (KeyError, TypeError, ValueError):
        age = None
        defects.append("shadow health has no parseable updated_at")

    active = [(name, key, row) for name, key, row in rows if not _terminal(row.get("status"))]
    for name, key, row in active:
        status = str(row.get("status") or "").upper()
        if status == "IDENTITY_BROKEN" or row.get("identity_drift"):
            defects.append(f"{name}:{key}: identity broken")
        if row.get("bar_source_stale") is True or row.get("bars_stale") is True:
            defects.append(f"{name}:{key}: source bars stale")
    expected = int(health.get("certified_sleeves_total", 0) or 0)
    represented = int(health.get("represented_sleeves", 0) or 0)
    if represented < expected:
        defects.append(f"shadow missing {expected - represented} certified sleeve(s)")
    blocked = int(health.get("evidence_blocked_sleeves", 0) or 0)
    health_status = str(health.get("status") or "UNKNOWN").upper()
    if blocked:
        defects.append(f"shadow health reports {blocked} evidence-blocked sleeve(s)")
    if health_status not in {"OPERATING", "HEALTHY", "OK"}:
        defects.append(f"shadow aggregate status is {health_status}")

    report = {
        "checked_at": now.isoformat(timespec="seconds"),
        "mode": "READ_ONLY_SYNC_WATCHDOG",
        "authoritative_writer": "contabo-mt5/FusionMarkets-Live",
        "vps_writer_disabled": True,
        "shadow_health_age_seconds": age,
        "certified": expected,
        "represented": represented,
        "active_rows": len(active),
        "rows_with_forward_trades": sum(int(row.get("n", 0) or 0) > 0
                                         for _name, _key, row in active),
        "evidence_blocked_sleeves": blocked,
        "authoritative_health_status": health_status,
        "defects": sorted(set(defects)),
        "status": "FAILED" if defects else "OPERATING",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(report, indent=2), "utf-8")
    os.replace(tmp, OUT)
    print(json.dumps(report, indent=2))
    return 1 if defects else 0


if __name__ == "__main__":
    raise SystemExit(main())
