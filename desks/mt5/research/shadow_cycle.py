"""Frequent, idempotent owner of every configured MT5 forward-shadow sleeve.

This is deliberately separate from daily research. Forward evidence follows data arrival, not a
calendar ceremony: each invocation replays the latest bars, refreshes all sleeve states, then runs
the deterministic promoter. Replays overwrite content-addressable ledgers, so cadence cannot
double-count trades.
"""
from __future__ import annotations

import json
import os
import traceback
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "reports" / "shadow" / "shadow_health.json"


def _refresh_scalp_bars() -> None:
    """Refresh broker M1/M5/M15 before replay; never place or modify an order."""
    if os.name != "nt":
        return
    import fetch_gold_scalp
    import h1_source

    failures: list[str] = []
    for terminal in h1_source._terminal_candidates():
        if not Path(terminal).exists():
            continue
        try:
            rows = fetch_gold_scalp.fetch(terminal, "XAUUSD", BASE / "data" / "universe",
                                           bars=20_000)
            if all(rows.values()):
                return
            failures.append(f"{terminal}: incomplete {rows}")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{terminal}: {type(exc).__name__}: {exc}")
    raise RuntimeError("no read-only MT5 history source: " + " | ".join(failures))


def _legacy_keys(shadow_forward) -> set[str]:  # type: ignore[no-untyped-def]
    keys = {
        f"{sym}.{window}" + (f".{state}" if state else "")
        for sym, window, state in shadow_forward.SLEEVES
    }
    keys.update(f"{sym}.{family}" for sym, family in shadow_forward.UNIVERSE_SLEEVES)
    return keys


def _read(path: Path) -> dict:
    try:
        row = json.loads(path.read_text("utf-8"))
        return row if isinstance(row, dict) else {}
    except (OSError, ValueError):
        return {}


def run() -> tuple[dict, int]:
    import promoter
    import scalp_shadow
    import shadow_forward

    started = datetime.now(UTC)
    errors: dict[str, str] = {}
    for name, fn in (
        ("scalp_bar_refresh", _refresh_scalp_bars),
        ("legacy_shadow", shadow_forward.main),
        ("scalp_shadow", scalp_shadow.main),
        ("promoter", promoter.main),
    ):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            errors[name] = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()

    legacy = _read(BASE / "reports" / "shadow" / "shadow_state.json")
    scalp = _read(BASE / "reports" / "shadow" / "scalp_shadow_state.json")
    expected_legacy = _legacy_keys(shadow_forward)
    represented_legacy = {key for key in expected_legacy if isinstance(legacy.get(key), dict)}
    expected_scalp = set(scalp_shadow.CANDIDATES)
    represented_scalp = {
        key for key in expected_scalp
        if isinstance((scalp.get("sleeves") or {}).get(key), dict)
    }
    rows = [legacy[key] for key in represented_legacy]
    rows += [(scalp.get("sleeves") or {})[key] for key in represented_scalp]
    missing = sorted((expected_legacy - represented_legacy) | (expected_scalp - represented_scalp))
    blocked = sum(row.get("status") in {"NO_DATA", "WAITING_FOR_FORWARD_BARS", "STALE_SOURCE"}
                  for row in rows)
    health = {
        "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "configured_sleeves": len(expected_legacy) + len(expected_scalp),
        "represented_sleeves": len(represented_legacy) + len(represented_scalp),
        "sleeves_with_forward_trades": sum(int(row.get("n", 0) or 0) > 0 for row in rows),
        "evidence_blocked_sleeves": blocked,
        "missing_sleeves": missing,
        "errors": errors,
        "seconds": round((datetime.now(UTC) - started).total_seconds(), 3),
    }
    health["status"] = "OPERATING" if not missing and not errors else "FAILED"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(health, indent=2), "utf-8")
    print(json.dumps(health, indent=2))
    return health, 0 if health["status"] == "OPERATING" else 1


def main() -> int:
    return run()[1]


if __name__ == "__main__":
    raise SystemExit(main())
