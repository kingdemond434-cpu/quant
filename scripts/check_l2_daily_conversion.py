#!/usr/bin/env python3
"""Publish L2 tape-to-survivor conversion debt for the midnight controller."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/l2_daily_conversion.json"
HEARTBEATS = {
    "futures": "data/recorder_heartbeat",
    "spot": "data/recorder_spot_heartbeat",
    "bybit": "data/recorder_bybit_heartbeat",
}
ARTIFACTS = {
    "mine": ("data/moat_mine.json", 1800),
    "screen": ("data/moat_screen.json", 1800),
    "utilisation": ("data/moat_utilisation.json", 108000),
}


def _json(p: Path) -> dict[str, Any] | None:
    try:
        v = json.loads(p.read_text("utf-8"))
        return v if isinstance(v, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def _age(p: Path, now: datetime) -> float | None:
    try:
        return max(0.0, now.timestamp() - p.stat().st_mtime)
    except OSError:
        return None


def _pct(v: Any) -> float | None:
    try:
        n = float(v)
        return n if 0 <= n <= 100 else None
    except (TypeError, ValueError):
        return None


def build_report(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    now = (now or datetime.now(UTC)).astimezone(UTC)
    checks: dict[str, Any] = {}
    actions: list[dict[str, str]] = []
    for name, rel in HEARTBEATS.items():
        age = _age(root / rel, now)
        ok = age is not None and age <= 600
        checks[f"recorder_{name}"] = {"path": rel, "age_seconds": age, "fresh": ok}
        if not ok:
            actions.append(
                {
                    "stage": "RECORD",
                    "owner": "scripts/ensure_recorder.py",
                    "action": f"restore {name} recorder and prove new tape bytes, not only a process",
                }
            )
    docs: dict[str, dict[str, Any] | None] = {}
    for name, (rel, limit) in ARTIFACTS.items():
        age = _age(root / rel, now)
        docs[name] = _json(root / rel)
        ok = docs[name] is not None and age is not None and age <= limit
        checks[name] = {"path": rel, "age_seconds": age, "fresh_and_valid": ok}
        if not ok:
            owner = {
                "mine": "scripts/mine_moat.py",
                "screen": "scripts/screen_moat.py",
                "utilisation": "scripts/run_moat_utilisation.py",
            }[name]
            actions.append(
                {"stage": name.upper(), "owner": owner, "action": f"refresh and validate {rel}"}
            )
    mine, screen, utilisation = docs["mine"] or {}, docs["screen"] or {}, docs["utilisation"] or {}
    mine_pct = _pct((mine.get("cumulative_coverage") or {}).get("coverage_pct"))
    closure = mine.get("closure") or {}
    growing = closure.get("coverage_is_meaningful") is True
    file_pct, cell_pct = _pct(screen.get("coverage_pct")), _pct(screen.get("cells_covered_pct"))
    util = utilisation.get("utilisation") or {}
    symbol_pct, hour_pct = (
        _pct(util.get("symbols_read_pct")),
        _pct(util.get("symbol_hours_read_pct")),
    )
    candidates = screen.get("persistent_candidates") or []
    coverage = {
        "mine_cells_pct": mine_pct,
        "mine_coverage_meaningful": growing,
        "screen_files_pct": file_pct,
        "screen_cells_pct": cell_pct,
        "utilised_symbols_pct": symbol_pct,
        "utilised_symbol_hours_pct": hour_pct,
        "persistent_candidates": len(candidates),
        "fresh_survivors_this_pass": len(screen.get("survivors") or []),
    }
    if not growing:
        disk = closure.get("disk") or {}
        actions.append(
            {
                "stage": "RECORD",
                "owner": "existing backup/retention and recorder organs",
                "action": "restore safe tape growth; archive/compress only with verified recoverability "
                f"(state={disk.get('state')}, free_bytes={disk.get('free_bytes')})",
            }
        )
    if mine_pct is None or mine_pct < 100:
        actions.append(
            {
                "stage": "MINE",
                "owner": "scripts/mine_moat.py",
                "action": "continue the persisted mining frontier to its measured denominator",
            }
        )
    if file_pct is None or file_pct < 100 or cell_pct is None or cell_pct < 100:
        actions.append(
            {
                "stage": "TEST",
                "owner": "scripts/screen_moat.py",
                "action": "screen the highest-value untested file/cell/mechanism/horizon residual",
            }
        )
    if symbol_pct is None or symbol_pct < 100 or hour_pct is None or hour_pct < 100:
        for item in (utilisation.get("next_actions") or [])[:5]:
            actions.append(
                {
                    "stage": "UTILISE",
                    "owner": "scripts/run_moat_utilisation.py",
                    "action": str(item.get("action") or item.get("slice") or item),
                }
            )
    if candidates:
        actions.append(
            {
                "stage": "CONVERT",
                "owner": "existing hypothesis, validation, portfolio-admission and paper-sleeve organs",
                "action": f"route {len(candidates)} persistent L2 candidates through preregistration, "
                "cost/leakage/multiplicity tests, independence, portfolio contribution and "
                "zero-capital shadow clocks; preserve rejections and near-survivors",
            }
        )
    unique = []
    seen = set()
    for row in actions:
        key = (row["stage"], row["action"])
        if key not in seen:
            seen.add(key)
            unique.append(row)
    complete = not unique and all(
        c.get("fresh", c.get("fresh_and_valid", False)) for c in checks.values()
    )
    return {
        "schema_version": "1.0.0",
        "generated_utc": now.isoformat(),
        "status": "OPERATING_FULL_CHAIN" if complete else "REDIRECT_REQUIRED",
        "claim": "100% means the current measured denominator traversed every conversion stage; new tape or mechanisms reopen it",
        "checks": checks,
        "coverage": coverage,
        "redirect_queue": unique,
        "controller_instruction": "consume every non-blocked positive-EV row tonight; persist exact BLOCKED dependencies",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--out", type=Path, default=OUT)
    a = p.parse_args(argv)
    report = build_report(a.root)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=1) + "\n", "utf-8")
    print(
        f"L2 daily conversion: {report['status']} -- {len(report['redirect_queue'])} routed residual(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
