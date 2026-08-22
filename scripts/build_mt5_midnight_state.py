"""Publish a small, read-only snapshot for the MT5-only midnight controller."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any


def _read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def _mtime(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()


def _older_than(stamp: str | None, now: datetime, hours: float) -> bool:
    if not stamp:
        return True
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    age = now - parsed.astimezone(UTC)
    return age < -timedelta(minutes=5) or age > timedelta(hours=hours)


def build(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    now = (now or datetime.now(tz=UTC)).astimezone(UTC)
    desk = root / "desks" / "mt5"
    data = desk / "data"
    reports = desk / "reports"
    universe_dir = data / "universe"
    meta = _read(universe_dir / "universe.json", {})
    queue = _read(data / "research_queue.json", [])
    survivors = _read(reports / "UNIVERSAL_SURVIVORS.json", {})
    shadow = _read(reports / "shadow" / "shadow_state.json", {})
    reuse_path = root / "data" / "intelligence" / "mt5_capability_reuse.json"
    reuse = _read(reuse_path, {})

    queue_rows = queue if isinstance(queue, list) else []
    queue_states = Counter(
        str(row.get("status", "UNKNOWN")) for row in queue_rows if isinstance(row, dict)
    )
    shadow_rows = (
        [row for key, row in shadow.items() if key != "last_run" and isinstance(row, dict)]
        if isinstance(shadow, dict)
        else []
    )
    survivor_rows = survivors.get("survivors", survivors) if isinstance(survivors, dict) else []
    survivor_count = len(survivor_rows) if isinstance(survivor_rows, (dict, list)) else 0
    h1 = sorted(universe_dir.glob("*_H1.parquet"))
    newest_h1 = max((_mtime(path) for path in h1), default=None)
    research_loop = _mtime(reports / "hypothesis_demo.jsonl")
    universal_gate = _mtime(reports / "UNIVERSAL_SURVIVORS.json")
    allocation = _mtime(reports / "allocation.json")
    markout = _mtime(reports / "markout.json")
    shadow_last = shadow.get("last_run") if isinstance(shadow, dict) else None

    defects: list[str] = []
    if not desk.is_dir():
        defects.append("MT5 desk missing")
    if not meta:
        defects.append("universe metadata missing or unreadable")
    if not h1:
        defects.append("no MT5 H1 universe bars")
    if not queue_rows:
        defects.append("research queue empty or unreadable")
    if not shadow_rows:
        defects.append("forward shadow state missing or empty")
    else:
        try:
            shadow_day = date.fromisoformat(str(shadow_last))
        except ValueError:
            shadow_day = date.min
        if shadow_day < now.date() - timedelta(days=1):
            defects.append("forward shadow daily clock stale")
    if _older_than(research_loop, now, 2):
        defects.append("hourly research loop stale or unmeasured")
    if markout is None:
        defects.append("execution markout missing; costs remain unmeasured")
    if _older_than(newest_h1, now, 48):
        defects.append("MT5 universe bars stale")
    if not reuse:
        defects.append("shared-library to MT5 capability reuse audit missing")
    elif _older_than(str(reuse.get("generated_at") or ""), now, 30):
        defects.append("shared-library to MT5 capability reuse audit stale")

    return {
        "schema_version": 1,
        "generated_at": now.isoformat(),
        "scope": "MT5_FUSION_ONLY",
        "execution_authority": False,
        "universe": {
            "metadata_entities": len(meta) if isinstance(meta, (dict, list)) else 0,
            "h1_bar_files": len(h1),
            "metadata_mtime": _mtime(universe_dir / "universe.json"),
            "newest_h1_mtime": newest_h1,
        },
        "conversion": {
            "research_queue": dict(sorted(queue_states.items())),
            "universal_survivors": survivor_count,
            "shadow_sleeves": len(shadow_rows),
            "shadow_observations": sum(int(row.get("n", 0) or 0) for row in shadow_rows),
            "shadow_last_run": shadow_last,
        },
        "freshness": {
            "research_loop": research_loop,
            "universal_gate": universal_gate,
            "allocation": allocation,
            "markout": markout,
        },
        "capability_reuse": {
            "artifact": str(reuse_path.relative_to(root)),
            "generated_at": reuse.get("generated_at") if isinstance(reuse, dict) else None,
            "counts": reuse.get("counts", {}) if isinstance(reuse, dict) else {},
            "proof_level": "STATIC_REACHABILITY_ONLY",
        },
        "defects": defects,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output or root / "data" / "intelligence" / "mt5_midnight_state.json"
    payload = build(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), "utf-8")
    os.replace(tmp, output)
    print(json.dumps(payload, sort_keys=True))
    return 0 if not payload["defects"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
