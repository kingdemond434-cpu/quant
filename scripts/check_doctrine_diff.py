#!/usr/bin/env python3
"""DOCTRINE-DIFF TRIGGER (R0093, deep-sweep SYNTH0731 P1-8c, meta X6/M6).

ops/principal_doctrine.txt is the principal's order channel: every edit to it is the
principal surfacing a gap the desk did not find itself -- the exact FAILURE SIGNAL the
blind-spot origin gauge (L2.5, blind_spot.py) exists to count. The gauge logged ZERO
principal rows across 6+ doctrine orders since 07-26 because nothing wired the channel
to it; a failure-signal gauge nothing feeds reads as success. This organ closes the wire:
it hashes the doctrine every run, and a changed hash auto-logs ONE blind-spot row
origin=principal carrying a real diff summary.

Design decisions that matter:
  * state = data/doctrine_hash.json plus a full previous copy (data/doctrine_prev.txt),
    so the row carries "+a/-r lines" and the first added line, not just "changed".
  * FIRST RUN BASELINES silently -- the gauge measures orders, not this wiring's birthday.
  * corrupt state re-baselines LOUDLY: the degrade direction is never-suppress-the-NEXT-
    detection, accepting one missed diff over a permanently welded gauge.
  * doctrine ABSENT or UNREADABLE exits 2 -- this organ cannot measure, and an unrunnable
    fence counts as FAILED, never skipped (L1.37).
  * the row is written through blind_spot.log (one writer, one schema); logging happens
    BEFORE the state update, so a crash between the two duplicates a row rather than
    silently dropping an order.

    python scripts/check_doctrine_diff.py
"""
from __future__ import annotations

import difflib
import hashlib
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

DOCTRINE = _ROOT / "ops/principal_doctrine.txt"
STATE = _ROOT / "data/doctrine_hash.json"
PREV = _ROOT / "data/doctrine_prev.txt"


def _summary(prev_text: str, new_text: str) -> str:
    diff = list(difflib.unified_diff(prev_text.splitlines(), new_text.splitlines(),
                                     lineterm="", n=0))
    added = [ln[1:].strip() for ln in diff if ln.startswith("+") and not ln.startswith("+++")]
    removed = [ln for ln in diff if ln.startswith("-") and not ln.startswith("---")]
    first = next((a for a in added if a), "")
    return (f"principal_doctrine.txt changed: +{len(added)}/-{len(removed)} lines"
            + (f'; first added: "{first[:140]}"' if first else ""))


def check(doctrine: Path = DOCTRINE, state: Path = STATE, prev: Path = PREV,
          log_row: Callable[[SimpleNamespace], None] | None = None) -> tuple[str, int]:
    """Returns (verdict, exit_code). Verdicts: UNREADABLE / BASELINED / REBASELINED /
    UNCHANGED / ORDER-LOGGED."""
    try:
        text = doctrine.read_text("utf-8")
    except OSError as exc:
        print(f"DOCTRINE-UNREADABLE: {doctrine} ({exc}) -- cannot measure, refusing to pass")
        return "UNREADABLE", 2

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    now = datetime.now(tz=UTC).isoformat()
    fresh_state = {"sha256": digest, "lines": len(text.splitlines()), "seen_at": now}

    old: dict | None = None
    rebaseline = False
    if state.exists():                       # absent state = first run, not a failure
        try:
            parsed = json.loads(state.read_text("utf-8"))
            if not isinstance(parsed, dict) or not parsed.get("sha256"):
                raise ValueError("state carries no hash")
            old = parsed
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            rebaseline = True
            print(f"STATE-CORRUPT ({exc!r}): re-baselining LOUDLY -- one diff may be lost, "
                  "the next one will not be")

    if old is None or rebaseline:
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps(fresh_state, indent=1), "utf-8")
        prev.write_text(text, "utf-8")
        verdict = "REBASELINED" if rebaseline else "BASELINED"
        print(f"{verdict}: sha {digest[:12]} ({fresh_state['lines']} lines)")
        return verdict, 0

    if old["sha256"] == digest:
        print(f"UNCHANGED: sha {digest[:12]} (last change seen {old.get('seen_at', '?')[:19]})")
        return "UNCHANGED", 0

    prev_text = prev.read_text("utf-8") if prev.exists() else ""
    summary = _summary(prev_text, text)
    if log_row is None:
        from scripts.blind_spot import log as log_row  # one writer, one schema
    log_row(SimpleNamespace(origin="principal", summary=summary,
                            angle="doctrine-diff", severity="high"))
    state.write_text(json.dumps(fresh_state, indent=1), "utf-8")
    prev.write_text(text, "utf-8")
    print(f"ORDER-LOGGED: {summary[:160]}")
    return "ORDER-LOGGED", 0


def main() -> int:
    from libs.ops.lawful import guard
    guard()
    _, rc = check()
    return rc


if __name__ == "__main__":
    sys.exit(main())
