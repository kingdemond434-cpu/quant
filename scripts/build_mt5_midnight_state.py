"""Publish a small, read-only snapshot for the MT5-only midnight controller."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import UTC, datetime
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


def build(root: Path) -> dict[str, Any]:
    desk = root / "desks" / "mt5"
    data = desk / "data"
    reports = desk / "reports"
    universe_dir = data / "universe"
    meta = _read(universe_dir / "universe.json", {})
    queue = _read(data / "research_queue.json", [])
    survivors = _read(reports / "UNIVERSAL_SURVIVORS.json", {})
    shadow = _read(reports / "shadow" / "shadow_state.json", {})

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

    return {
        "schema_version": 1,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "scope": "MT5_FUSION_ONLY",
        "execution_authority": False,
        "universe": {
            "metadata_entities": len(meta) if isinstance(meta, (dict, list)) else 0,
            "h1_bar_files": len(h1),
            "metadata_mtime": _mtime(universe_dir / "universe.json"),
            "newest_h1_mtime": max((_mtime(path) for path in h1), default=None),
        },
        "conversion": {
            "research_queue": dict(sorted(queue_states.items())),
            "universal_survivors": survivor_count,
            "shadow_sleeves": len(shadow_rows),
            "shadow_observations": sum(int(row.get("n", 0) or 0) for row in shadow_rows),
            "shadow_last_run": shadow.get("last_run") if isinstance(shadow, dict) else None,
        },
        "freshness": {
            "research_loop": _mtime(reports / "hypothesis_demo.jsonl"),
            "universal_gate": _mtime(reports / "UNIVERSAL_SURVIVORS.json"),
            "allocation": _mtime(reports / "allocation.json"),
            "markout": _mtime(reports / "markout.json"),
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
