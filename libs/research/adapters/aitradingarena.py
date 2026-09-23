"""AI Trading Arena adapter (REBUILT) -- the arena's published methodology is a LIFECYCLE: a claim
transitions, and the transitions are the telemetry. This desk keeps its own, so the adapter
reads the desk's ledgers and reports the transition counts and the age of each ledger. Nothing
is fetched and nothing external is trusted; a ledger that is absent is named as absent, which is
the measurement the arena's own method asks for."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "aitradingarena"
CAPABILITY_FAMILY = "telemetry_source"
LICENCE_EXPECTED = "N/A (public methodology)"
RUNS_WITHOUT_LIBRARY = True

LEDGERS: tuple[str, ...] = (
    "desks/mt5/reports/SURVIVORS_LEDGER.json", "desks/mt5/reports/UNIVERSAL_SURVIVORS.json",
    "desks/mt5/reports/SANDBOX_RUNNER.json", "desks/mt5/reports/SANDBOX_ROSTER.json",
)


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import json
    from datetime import UTC, datetime
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    rows: list[dict[str, Any]] = []
    transitions: dict[str, int] = {}
    for rel in LEDGERS:
        p = root / rel
        row: dict[str, Any] = {"ledger": rel, "exists": p.exists()}
        if p.exists():
            try:
                row["age_h"] = round((datetime.now(tz=UTC).timestamp() - p.stat().st_mtime)
                                     / 3600.0, 2)
                row["bytes"] = p.stat().st_size
                doc = json.loads(p.read_text(encoding="utf-8-sig"))
                entries = doc if isinstance(doc, list) else (
                    doc.get("entries") or doc.get("systems") or doc.get("survivors") or [])
                if isinstance(entries, dict):
                    entries = list(entries.values())
                row["n_rows"] = len(entries) if isinstance(entries, list) else None
                for e in entries if isinstance(entries, list) else []:
                    if isinstance(e, dict):
                        st = str(e.get("status") or e.get("last_status") or "")
                        if st:
                            transitions[st] = transitions.get(st, 0) + 1
            except (OSError, ValueError) as exc:
                row["why"] = f"{type(exc).__name__}: {exc}"[:160]
        rows.append(row)
    present = [r for r in rows if r.get("exists")]
    if not present:
        return A.unmeasured(SYSTEM, bundle, "none of the desk's lifecycle ledgers exist here")
    return A.packet(
        SYSTEM, bundle, trials=len(LEDGERS),
        representations=[{
            "kind": "lifecycle_telemetry", "system": SYSTEM, "ledgers": rows,
            "transition_counts": dict(sorted(transitions.items())),
            "n_present": len(present), "n_ledgers": len(rows),
            "representation": ("the desk's own lifecycle transitions, counted from its ledgers "
                               "-- the arena's method applied to this desk instead of a "
                               "leaderboard")}],
        note=f"{len(present)}/{len(rows)} lifecycle ledgers present")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
