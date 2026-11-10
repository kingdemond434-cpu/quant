"""Sources whose terms forbid commercial use do not reach the candidate compiler.

The desk's rule: a source whose own terms forbid machine or commercial use stays fail-closed.
The BIS speech feed was read on 2026-11-10 as "allowed for noncommercial purposes" and its rows
sat in the donation tree, where the compiler reads every file. This is the fence: a matching
file is parked (left on disk, counted, named with what it costs) and not read.

FAIL-CLOSED IN BOTH DIRECTIONS. The registry (`terms_fences.json`) can add fences and can reopen
one, but a fence built into this module is enforced even if the registry is missing, unreadable
or has had the row removed; and a fence is open only with `open: true` AND a pasted permitting
clause, so a stray flag cannot reopen it.
"""
from __future__ import annotations

import fnmatch
import json
from collections.abc import Mapping
from pathlib import Path, PurePath
from typing import Any

REGISTRY = Path(__file__).with_name("terms_fences.json")

#: Enforced whatever the registry says, unless the registry reopens it with a clause.
BUILT_IN: tuple[dict[str, Any], ...] = (
    {"id": "bis_speeches",
     "match": ["bis_speeches/*", "central_banks/bis_speech_tone.jsonl",
               "central_banks/cb_tone_series.jsonl"],
     "seats": ["bis_speeches"],
     "reason": "BIS terms allow noncommercial use only",
     "missed_growth": "central bank speech titles and tone from BIS are not compiled into "
                      "candidates"},
)


def is_open(fence: Mapping[str, Any]) -> bool:
    """Reopened only on the flag AND a permitting sentence someone pasted from the terms page."""
    return fence.get("open") is True and len(str(fence.get("permit_clause") or "").strip()) >= 20


def load(registry: Path | None = None) -> list[dict[str, Any]]:
    """The fences in force: the registry's rows, plus any built-in one the registry lacks."""
    try:
        doc = json.loads((registry or REGISTRY).read_text("utf-8"))
        rows = [dict(f) for f in doc.get("fences") or [] if isinstance(f, dict) and f.get("id")]
    except (OSError, ValueError, AttributeError):
        rows = []
    have = {str(f["id"]) for f in rows}
    rows += [dict(f) for f in BUILT_IN if f["id"] not in have]
    return [f for f in rows if not is_open(f)]


def path_fenced(path: Path | str, fences: list[dict[str, Any]] | None = None
                ) -> dict[str, Any] | None:
    """THE ONE PREDICATE for a file: is it behind a closed fence? The path is read relative to
    the last `intelligence` directory in it; a path outside any intelligence tree is not fenced.
    Every reader whose output can reach a candidate, a factor, a verdict or sizing calls this
    (or `seat_fenced`) before it reads."""
    parts = PurePath(path).parts
    if "intelligence" not in parts:
        return None
    i = len(parts) - 1 - parts[::-1].index("intelligence")
    rel = PurePath(*parts[i + 1:]) if parts[i + 1:] else None
    if rel is None:
        return None
    return fence_for(rel, load() if fences is None else fences)


def seat_fenced(seat: str, fences: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """The same question for a whole source directory or miner name (`seats` in the fence)."""
    for f in (load() if fences is None else fences):
        if str(seat).lower() in {str(x).lower() for x in f.get("seats") or []}:
            return f
    return None


def fence_for(rel: PurePath | str, fences: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The closed fence this intelligence-relative path falls behind, if any."""
    s = PurePath(rel).as_posix().lower()
    for f in fences:
        if any(fnmatch.fnmatchcase(s, str(pat).lower()) for pat in f.get("match") or []):
            return f
    return None
