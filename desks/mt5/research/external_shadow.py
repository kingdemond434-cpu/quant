"""Retire the obsolete external-only forward ledger without deleting its evidence.

External certificates are now enrolled by :mod:`shadow_forward`, the canonical universal
engine. Keeping this former runner alive would execute the same certificate twice under two
keys and let a stale private ledger inflate clock counts. The module remains as an idempotent
compatibility/migration entrypoint because old schedules and sync manifests may still invoke it.
It never evaluates a signal and never creates a clock.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
STATE = BASE / "reports" / "shadow" / "external_shadow_state.json"
CERTS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
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
    try:
        certs = json.loads(CERTS.read_text("utf-8")).get("survivors", {})
    except (OSError, ValueError, AttributeError):
        certs = {}
    runnable = {
        str(key) for key, cert in certs.items()
        if isinstance(cert, dict)
        and isinstance((cert.get("shadow_spec") or {}).get("params"), dict)
    }
    now = datetime.now(UTC).isoformat()
    retired = 0
    for key, row in state.items():
        if not str(key).startswith("external.") or not isinstance(row, dict):
            continue
        if not _is_terminal(row.get("status")):
            duplicate = key in runnable
            row.update(
                status=("RETIRED_DUPLICATE_CLOCK" if duplicate
                        else "RETIRED_UNRECONSTRUCTIBLE"),
                retired_at=now,
                promotion_authority=False,
                order_authority=False,
                why=(("retired without deleting evidence: canonical shadow_state.json owns "
                      "this exact certificate through shadow_forward") if duplicate else
                     ("retired without deleting evidence: certificate omitted exact params; "
                      "the old private runner guessed family defaults, which cannot form a "
                      "valid forward clock")),
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
        retired_unreconstructible_sleeves=sum(
            isinstance(row, dict) and row.get("status") == "RETIRED_UNRECONSTRUCTIBLE"
            for key, row in state.items() if str(key).startswith("external.")
        ),
    )
    STATE.parent.mkdir(parents=True, exist_ok=True)
    # NOT an in-place overwrite: this file is read by the sync, the census and the reconciler,
    # and on Windows overwriting it while one of them holds it open raised PermissionError 13 --
    # which failed the whole shadow census (MT5-Shadow exit 1) on 2026-09-16.
    root = str(Path(__file__).resolve().parents[3])
    if root not in sys.path:
        sys.path.insert(0, root)
    from libs.ops.win_write import write_text_resilient
    write_text_resilient(STATE, json.dumps(state, indent=2))
    print(f"external shadow compatibility: retired {retired} obsolete private clock(s); "
          "canonical shadow_forward remains sole owner")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
