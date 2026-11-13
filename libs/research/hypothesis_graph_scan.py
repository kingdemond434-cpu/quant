"""Bounded reads of the hypothesis graph for research producers -- never imported by the money path.

WHY A SEPARATE MODULE (2026-11-11). `libs/research/hypothesis_graph.py` sits in the money-path
import closure, so replay-shadow treats any change to it as a money-path change and every new
keyword as a knob it cannot bound. `latest_rows` serves one research producer
(graveyard_resurrection) and touches nothing that sizes or routes an order, so it lives here and
reuses the graph's own line patterns and constants unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from libs.research.hypothesis_graph import _FATE_FATE, _FATE_ID, BORN, LEDGER


def latest_rows(fates: frozenset[str] | set[str], path: Path = LEDGER,
                limit: int | None = None,
                problems: list[str] | None = None) -> tuple[list[dict[str, Any]], set[str]]:
    """(the latest row of every node whose PRESENT fate is in `fates`, every node id).

    WHY THIS EXISTS (2026-11-03, dead-producer triage). `graveyard_resurrection` read the graph
    through a full `json.loads` of its first 400,000 lines -- the OLDEST rows of a 4.4 GB file --
    and was killed at its leg cap on 1,934 runs. It needs the dead (FAILED/BURIED) and certified
    rows in full and only the ids of the rest. Pass one reads ids, fates and line offsets by
    pattern, as `current_fates` does; pass two seeks to and parses only the lines asked for, newest
    first, so `limit` keeps the most RECENT rows rather than the first ones in the file; they
    come back in file order, as `Graph.current()` returns them.
    Last row per id wins, exactly as `Graph.current()`; a line the pattern cannot explain falls
    back to `json.loads`.

    AN UNREADABLE GRAPH IS NOT AN EMPTY ONE. A file that cannot be opened returns ([], set()) as
    an empty graph does, so a caller that must tell them apart passes `problems`: the reason is
    appended to it, and an empty list after the call means the graph was read.
    """
    want = {str(f).upper() for f in fates}
    last: dict[str, tuple[str, int]] = {}
    try:
        fh = path.open("rb")
    except OSError as exc:
        if problems is not None:
            problems.append(f"{path.name} unreadable: {type(exc).__name__}: {exc}"[:240])
        return [], set()
    with fh:
        off = 0
        for ln in fh:
            here, off = off, off + len(ln)
            m = _FATE_ID.match(ln)
            f = _FATE_FATE.findall(ln) if m else None
            if m and f is not None and len(f) == 1:
                last[m.group(1).decode("utf-8", "replace")] = ((f[0].decode() or BORN).upper(),
                                                                here)
                continue
            if not ln.strip():
                continue
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if isinstance(r, dict) and r.get("id") is not None:
                last[str(r["id"])] = (str(r.get("fate") or BORN).upper(), here)
        picks = sorted((o for fate, o in last.values() if fate in want), reverse=True)
        if limit is not None:
            picks = picks[: max(0, int(limit))]
        picks.sort()                            # the newest `limit`, returned in file order
        rows: list[dict[str, Any]] = []
        for o in picks:
            fh.seek(o)
            try:
                r = json.loads(fh.readline())
            except ValueError:
                continue
            if isinstance(r, dict):
                rows.append(r)
    return rows, set(last)
