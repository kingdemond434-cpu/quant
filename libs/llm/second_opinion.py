"""THE ASK-A-SECOND-MODEL-FAMILY PATTERN, EXTRACTED TO ONE PLACE (R0114; L1.33 rollout).

libs/research/second_family.py holds the PRIMITIVES (ask_second_family / merge_verdict /
blindspot_prompt), but the CALLING PATTERN around them -- summarise this run's own findings, ask
the partner family what the run MISSED, merge, record the verdict into the organ's artifact,
print one honest status line, and never let any of that break the organ -- lived in exactly one
organ (scripts/blindspot_max.py). A pattern that exists once is a copy waiting to happen: the
moment the prober or the sweep wanted the partner, the block would have been pasted and the
copies would drift. So the pattern moves here, and every exploration organ gets it by calling
ONE function the same way.

DARK BEHAVIOUR IS THE CONTRACT. ``consult_second_family`` NEVER raises:

  - an unavailable seat (missing key, 402/unfunded, dead provider, empty response) comes back
    from ask_second_family as available=False and is recorded as SOLO -- a single-family run,
    honestly labelled, never passed off as cross-family corroboration;
  - any local fault (unimportable partner module, unreadable artifact, disk error) degrades to
    a printed SKIPPED line and a returned SKIPPED verdict.

Either way the calling organ keeps its exit-0 cadence: a dark partner can never take down the
organ that consulted it. Stdlib-only at import time; the partner primitives are imported lazily
inside the guard for the same reason the organs used to import them lazily -- the partner must
never break the organ.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

__all__ = ["consult_second_family"]


def consult_second_family(
    context: str,
    own_findings: object,
    *,
    artifact: Path | None = None,
    key: str = "second_family",
    text_cap: int = 4000,
    timeout: float = 300.0,
) -> dict[str, Any]:
    """Ask the independent family what THIS run missed; record and return the honest verdict.

    ``own_findings`` is either a ready string or any JSON-serialisable summary of what the organ
    just found. When ``artifact`` is given, the verdict block is merged into that JSON file under
    ``key`` (created if the organ has not written it yet). Returns the recorded block: a
    merge_verdict() dict (CONFIRMED / CONTESTED / SOLO) plus the partner's text, or
    ``{"verdict": "SKIPPED", ...}`` on a local fault. NEVER raises.
    """
    try:
        from libs.research.second_family import (
            ask_second_family,
            blindspot_prompt,
            merge_verdict,
        )
        own = (own_findings if isinstance(own_findings, str)
               else json.dumps(own_findings, indent=1, default=str))
        op = ask_second_family(blindspot_prompt(context, own), context=context, timeout=timeout)
        verdict = merge_verdict(own, op)
        block: dict[str, Any] = {**verdict, "text": op.text[:text_cap] if op.available else ""}
        if artifact is not None:
            try:
                recorded = json.loads(artifact.read_text("utf-8"))
            except (OSError, ValueError):
                recorded = {}
            if not isinstance(recorded, dict):
                recorded = {"artifact": recorded}
            recorded[key] = block
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text(json.dumps(recorded, indent=1), "utf-8")
        print(f"  second family: {verdict['verdict']}"
              + (f" -- {verdict.get('reason', '')}" if verdict["verdict"] == "SOLO" else ""))
        return block
    except Exception as exc:               # the partner must never break the organ
        print(f"  second family: SKIPPED ({exc})")
        return {"verdict": "SKIPPED", "reason": str(exc)}
