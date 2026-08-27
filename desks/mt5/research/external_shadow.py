"""Retire the obsolete external-only forward ledger without deleting its evidence.

External certificates are now enrolled by :mod:`shadow_forward`, the canonical universal
engine. Keeping this former runner alive would execute the same certificate twice under two
keys and let a stale private ledger inflate clock counts. The module remains as an idempotent
compatibility/migration entrypoint because old schedules and sync manifests may still invoke it.
It never evaluates a signal and never creates a clock.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
STATE = BASE / "reports" / "shadow" / "external_shadow_state.json"
_TERMINAL = ("RETIRED", "KILL", "DEAD", "REJECT", "QUARANTIN", "PROMOTED")


def _is_terminal(value: object) -> bool:
    return str(value or "").upper().startswith(_TERMINAL)


def main() -> int:
    try:
        state = json.loads(STATE.read_text("utf-8"))
        if not isinstance(state, dict):
            state = {}
    except (OSError, ValueError):
        state = {}
    now = datetime.now(UTC).isoformat()
    retired = 0
    for key, row in state.items():
        if not str(key).startswith("external.") or not isinstance(row, dict):
            continue
        if not _is_terminal(row.get("status")):
            row.update(
                status="RETIRED_DUPLICATE_CLOCK",
                retired_at=now,
                promotion_authority=False,
                order_authority=False,
                why=("retired without deleting evidence: canonical shadow_state.json owns "
                     "this certificate through shadow_forward"),
            )
            retired += 1
    state.update(
        updated_at=now,
        pipeline_status="RETIRED_REDUNDANT",
        replacement="shadow_state.json / shadow_forward",
        active_external_sleeves=0,
        retired_duplicate_sleeves=sum(
            isinstance(row, dict) and row.get("status") == "RETIRED_DUPLICATE_CLOCK"
            for key, row in state.items() if str(key).startswith("external.")
        ),
    )
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2), "utf-8")
    print(f"external shadow compatibility: retired {retired} duplicate clock(s); "
          "canonical shadow_forward remains sole owner")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
