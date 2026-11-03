"""Fusion sizes as if a principal withdrawal had not happened, until real equity is back.

THE ASK (zuck, 2026-11-03 00:34Z, cmsg CcZQMZFSSTj9cYUKZHgZzF): "i took 200 out from fusion use
same risk n all till account equity rises back dont reduce risk or anyth act like its still at
460". A withdrawal is not a loss, so it must not shrink the book the way a drawdown would.

THE RULE. desks/mt5/data/FUSION_EQUITY_REFERENCE.json, written on the box:
    {"reference_equity": 460, "withdrawn": 200, "set_by": "...", "set_at": "..."}
    sizing equity = max(real, min(real + withdrawn, reference))
so a loss after the withdrawal still shrinks sizing euro for euro (real + withdrawn falls), the
uplift never exceeds the reference, and it fades to nothing once real equity reaches it. The
deadman's equity floor is judged on the same real + withdrawn while the reference is active, so
the floor keeps the euro distance it had before the money left. Daily and weekly loss rails stay
on real equity. A missing, unreadable or implausible file means no uplift at all.
"""

from __future__ import annotations

import json
from pathlib import Path

REF_PATH = Path(__file__).resolve().parent.parent / "data" / "FUSION_EQUITY_REFERENCE.json"
#: An implausible file is ignored rather than trusted: the reference is a principal's number for a
#: small account, never a way to size a book as if it were large.
MAX_REFERENCE = 5000.0


def load(path: Path | None = None) -> tuple[float, float] | None:
    """(reference_equity, withdrawn), or None when there is no valid reference."""
    try:
        doc = json.loads((path or REF_PATH).read_text(encoding="utf-8"))
        ref = float(doc["reference_equity"])
        out = float(doc["withdrawn"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not (0.0 < out < ref <= MAX_REFERENCE):
        return None
    return ref, out


def active_offset(real: float, path: Path | None = None) -> float:
    """The withdrawn amount while real equity is below the reference, else 0."""
    got = load(path)
    if got is None or real <= 0:
        return 0.0
    ref, out = got
    return out if real < ref else 0.0


def sizing_equity(real: float, path: Path | None = None) -> float:
    got = load(path)
    if got is None or real <= 0:
        return real
    ref, out = got
    return max(real, min(real + out, ref))
