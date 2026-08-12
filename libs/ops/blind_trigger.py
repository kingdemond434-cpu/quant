"""Blind-rediscovery trigger state: ONE counting rule, and the actuator that writes it.

check_blind_trigger (scripts/max_audit.py) fires blind-rediscovery-due-by-state off two
artifacts that until 2026-08-12 had NO programmatic writer: data/cadence_state.json
["last_blind_rediscovery"] and data/blind_trigger_baseline.json {sources, graveyard}.
Run 1 (2026-07-31) stamped the timestamp by hand and left the baseline at its 07-19
values; run 2 (2026-08-11, 8278e31) did the same -- so the trigger kept demanding a dig
over material fresh eyes had already seen. The actuatorless-law class (L1.28b): a
detector whose clearing state nothing writes is a fence that can only cry.

`stamp()` is called by ops/run_blindrediscovery_dig.sh after its claude run and REFUSES
unless the organ's deliverable (docs/research/blind_rediscovery_log.md) advanced past the
run's start -- an exit code proves a process ended, never that it produced. `counts()` is
the single counting rule; check_blind_trigger imports it so the detector and the actuator
cannot drift. By parity with the detector's `_j(..., default)` reads, an unreadable input
counts as 0 -- which biases the NEXT delta upward, the direction that makes the fence cry
rather than sleep.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ARTIFACT = "docs/research/blind_rediscovery_log.md"
STATE = "data/cadence_state.json"
BASELINE = "data/blind_trigger_baseline.json"


def counts(root: Path | str = ".") -> tuple[int, int]:
    """(data sources, graveyard rows): the two new-raw-material meters the trigger diffs."""
    root = Path(root)
    try:
        umap = json.loads((root / "data/data_universe_map.json").read_text("utf-8"))
        srcs = umap.get("sources", {})
        n_sources = len(srcs) if isinstance(srcs, (dict, list)) else 0
    except (OSError, json.JSONDecodeError, AttributeError):
        n_sources = 0
    gy = root / "docs/graveyard.md"
    try:
        n_grave = sum(1 for ln in gy.read_text("utf-8").splitlines() if ln.startswith("| "))
    except OSError:
        n_grave = 0
    return n_sources, n_grave


def stamp(root: Path | str = ".", *, min_artifact_ts: float = 0.0,
          ts: str | None = None) -> str:
    """Record a completed blind-rediscovery run: timestamp + the baseline it saw.

    Refuses (returns a REFUSED line, writes nothing) when the deliverable did not advance
    past `min_artifact_ts` -- a dead claude call must not clear the trigger.
    """
    root = Path(root)
    art = root / ARTIFACT
    if not art.exists():
        return f"REFUSED: {ARTIFACT} absent -- no production, nothing to stamp"
    if art.stat().st_mtime < min_artifact_ts:
        return (f"REFUSED: {ARTIFACT} did not advance past run start "
                f"({art.stat().st_mtime:.0f} < {min_artifact_ts:.0f}) -- run produced nothing")
    n_sources, n_grave = counts(root)
    when = ts or datetime.now(tz=UTC).isoformat()
    state_p = root / STATE
    try:
        state = json.loads(state_p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        state = {}
    state["last_blind_rediscovery"] = when
    state_p.parent.mkdir(parents=True, exist_ok=True)
    state_p.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n", "utf-8")
    (root / BASELINE).write_text(json.dumps(
        {"sources": n_sources, "graveyard": n_grave, "stamped": when,
         "by": "libs.ops.blind_trigger.stamp"}, indent=1) + "\n", "utf-8")
    return f"stamped last_blind_rediscovery={when} baseline sources={n_sources} graveyard={n_grave}"
