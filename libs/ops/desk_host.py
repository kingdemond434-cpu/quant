"""IS THIS THE HOST THAT OWNS THE DESK'S STATE? Read the answer; never infer it.

TWO DEFECTS, ONE MISSING FACT (GAP 111, GAP 113).

`data/` is gitignored, so every artifact the running desk writes is absent from every clone. Two
organs each guessed at that and each guessed in the direction that looks clean:

  * `slot_registry.derive_slots` treats an absent birth certificate as a clock NEVER BORN -- true
    on the owning host, false on a clone -- and so published a small Holm `m` as MEASURED. A
    smaller cohort is a LOOSER bar, which is the phantom-edge direction, on the single most
    load-bearing integer on the path to capital.
  * the test suite RECOMPUTES tracked ratchet files from whatever the host can see, so a full
    `pytest` on a clone rewrote `next_law_number.txt` 60 -> 43 and overwrote real trade forensics
    with `n_closes: 0`. A ratchet any host can recompute downward is not a ratchet.

Both are the same missing fact, and neither can be settled by looking at the files themselves: on
a clone the evidence and its absence look identical. So the desk states it, once, explicitly.

**A MARKER IS ONLY HONEST IF IT IS WRITTEN BY THE THING IT CLAIMS.** This file is stamped by the
running cycle (`ops/run_research_cycle.sh` -> `scripts/stamp_desk_host.py`), never by a test, never
by a library on read, and never as a side effect of asking the question. A marker that any caller
can create on demand answers "did someone ask?" instead of "did a desk run here?", which is the
same substitution the two defects above already made.

**FAIL-CLOSED, AND THE DIRECTION IS THE POINT.** Absent or unreadable resolves to NOT the owning
host. That is the conservative answer for both callers: the cohort floors at the cap (a TIGHTER
bar, never looser) and the ratchet writes are skipped (no downward recompute). Guessing the other
way restores exactly the two defects this exists to remove.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

__all__ = ["MARKER", "is_owning_host", "stamp"]

_ROOT = Path(__file__).resolve().parents[2]

#: Under data/, so it is gitignored exactly like the state it vouches for. A marker that travelled
#: with the repo would assert "this is the owning host" on every clone that checked it out, which
#: is the failure it exists to prevent.
MARKER = "data/.desk_host.json"

#: Escape hatch for CI that genuinely does own its state (a runner with a restored data/ volume).
#: Named rather than magic, and read as a STRING equal to "1" so a stray non-empty value cannot
#: silently enable it.
ENV_OVERRIDE = "QUANT_DESK_HOST"


def is_owning_host(root: Path | str | None = None) -> tuple[bool, str]:
    """Does this box own the desk's runtime state? Returns ``(owns, why)``.

    Never raises: every caller is a fail-closed path, and an exception here would be a third way
    to get the wrong answer.
    """
    if os.environ.get(ENV_OVERRIDE) == "1":
        return True, f"{ENV_OVERRIDE}=1 set explicitly in the environment"
    base = Path(root) if root is not None else _ROOT
    p = base / MARKER
    try:
        blob = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return False, (
            f"{MARKER} absent or unreadable -- this host does not own the desk's runtime state. "
            "FAIL-CLOSED on purpose: absent state must never be read as measured zeros (the Holm "
            "cohort floors at the cap instead, a TIGHTER bar) and must never license a ratchet "
            "recompute (a clone would drive it DOWN). Stamped by the running cycle only")
    stamped = str(blob.get("stamped") or "")
    return True, f"{MARKER} present, stamped {stamped or 'at an unrecorded time'}"


def stamp(root: Path | str | None = None) -> str:
    """Write the marker. Called by the CYCLE, never by a library and never by a test."""
    base = Path(root) if root is not None else _ROOT
    p = base / MARKER
    p.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(tz=UTC).isoformat()
    p.write_text(json.dumps({
        "stamped": now,
        "note": ("This box owns the desk's runtime state under data/. Written by the research "
                 "cycle so that `absent artifact` can be read as a MEASUREMENT here and as a "
                 "fact about the HOST everywhere else. Never create this by hand on a clone: it "
                 "would make a small Holm cohort publish as MEASURED and let a test run recompute "
                 "a ratchet downward."),
    }, indent=1) + "\n", "utf-8")
    return now
