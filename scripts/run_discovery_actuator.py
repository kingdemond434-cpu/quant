#!/usr/bin/env python3
"""DISCOVERY AUTHORITY ACTUATOR -- transmits check_discovery_gate.py's verdict, per sleeve.

Mirrors scripts/run_promotion_actuator.py's asymmetry exactly, applied per-sleeve instead of to
one discretionary book: DOWN is immediate (evidence that stopped supporting a fraction stops
supporting it the moment the gate says so), UP waits CONFIRM_HOLD_H wall-clock hours so a fraction
oscillating across a boundary cannot flap. It never decides anything -- it cannot authorize a
fraction the gate did not compute, and it cannot reach the ruin rail or the deadman switch.

IT WRITES AN AUTHORITY, NOT AN ORDER, AND NOT EVEN A SIZE. data/discovery_authority.json states a
fraction-of-full-Kelly per sleeve. No execution path reads this file yet -- there is no order-
routing wiring from a systematic-discovery sleeve to the book, which is a separate, larger, and
still-unbuilt piece. This organ's job stops at "here is what the evidence would justify, and here
is why," exactly as far as run_sleeve_allocator.py's own L1.6 zero-promotion-authority mandate
already goes for paper risk budgets.

    python scripts/run_discovery_actuator.py            # apply
    python scripts/run_discovery_actuator.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

GATE = "data/discovery_promotion_gate.json"
OUT = "data/discovery_authority.json"

#: Same wall-clock (not run-count) rationale as run_promotion_actuator.CONFIRM_HOLD_H: a fraction
#: flickering across a boundary must not be granted more room just because the cycle runs faster.
CONFIRM_HOLD_H = 24.0


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _refresh_gate(root: Path) -> str:
    try:
        r = subprocess.run([sys.executable, "scripts/check_discovery_gate.py"],
                           cwd=root, capture_output=True, text=True, timeout=300)
        return "OK" if r.returncode == 0 else f"rc={r.returncode}"
    except (OSError, subprocess.SubprocessError) as exc:
        return f"{type(exc).__name__}: {exc}"


def _apply_one(name: str, gate_frac: float, prev: dict[str, Any], now: datetime) -> dict[str, Any]:
    prev_frac = float(prev.get("fraction") or 0.0)
    prev_gate = prev.get("gate_fraction")
    prev_gate = prev_frac if prev_gate is None else float(prev_gate)
    streak = int(prev.get("confirm_streak") or 0)
    streak = streak + 1 if gate_frac == prev_gate else 1

    since = prev.get("gate_fraction_since") if gate_frac == prev_gate else None
    if not since:
        since = now.isoformat()
    try:
        held_h = (now - datetime.fromisoformat(str(since))).total_seconds() / 3600.0
    except (TypeError, ValueError):
        held_h = 0.0

    if gate_frac < prev_frac:
        applied, direction = gate_frac, "DERISK"
        why = f"gate dropped {prev_frac} -> {gate_frac}; de-risking applies immediately."
    elif gate_frac > prev_frac and held_h < CONFIRM_HOLD_H:
        applied, direction = prev_frac, "HOLD-PENDING-CONFIRM"
        why = (f"gate grants {gate_frac}, held {held_h:.1f}h of {CONFIRM_HOLD_H:.0f}h required; "
               f"authority stays at {prev_frac} until it holds.")
    else:
        applied = gate_frac
        direction = "RAISE" if gate_frac > prev_frac else "STEADY"
        why = (f"gate grants {gate_frac}, held {held_h:.1f}h, past the {CONFIRM_HOLD_H:.0f}h bar."
               if gate_frac > prev_frac else f"unchanged at {gate_frac}.")

    return {"fraction": applied, "gate_fraction": gate_frac, "gate_fraction_since": since,
           "confirm_streak": streak, "held_h": round(held_h, 2), "direction": direction,
           "why": why, "changed": applied != prev_frac}


def run(root: Path | None = None, *, dry_run: bool = False) -> dict[str, Any]:
    base = root or _ROOT
    now = datetime.now(tz=UTC)
    refreshed = _refresh_gate(base)
    gate = _read(base / GATE)
    prev = _read(base / OUT) or {}
    prev_sleeves = prev.get("sleeves") or {}

    doc: dict[str, Any] = {
        "generated_utc": now.isoformat(timespec="seconds"), "gate_refresh": refreshed,
        "law": "the gate decides a fraction of full Kelly; this transmits it per sleeve with an "
               "immediate-down / wall-clock-gated-up asymmetry. No execution path consumes this "
               "file -- it authorizes nothing that can place an order.",
    }

    if not isinstance(gate, dict) or gate.get("status") != "OK":
        doc.update(status="UNMEASURED", sleeves=prev_sleeves,
                   why=f"{GATE} unreadable or not status OK (refresh: {refreshed}). Previous "
                       "authority stands unchanged.")
        _write(base, doc, dry_run=dry_run)
        return doc

    sleeves: dict[str, Any] = {}
    for name, row in (gate.get("sleeves") or {}).items():
        gate_frac = float(row.get("authorized_fraction_of_kelly") or 0.0)
        sleeves[name] = _apply_one(name, gate_frac, prev_sleeves.get(name, {}), now)
    doc.update(status="OK", sleeves=sleeves)
    _write(base, doc, dry_run=dry_run)
    return doc


def _write(root: Path, doc: dict[str, Any], *, dry_run: bool) -> None:
    if dry_run:
        return
    p = root / OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1), "utf-8")


def main(argv: list[str] | None = None) -> int:
    from libs.ops.lawful import guard as _law_guard
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    doc = run(dry_run=args.dry_run)
    if args.json:
        print(json.dumps(doc, indent=2))
    else:
        print(f"discovery authority: {doc['status']} -- {len(doc.get('sleeves', {}))} sleeve(s)")
        for name, s in doc.get("sleeves", {}).items():
            print(f"  {name:18} fraction={s.get('fraction')} {s.get('direction', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
