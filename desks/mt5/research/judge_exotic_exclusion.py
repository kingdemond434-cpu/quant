"""EXOTIC CELLS GET NO JUDGE SLOTS -- set aside BY NAME before the docket ships, never dropped.

THE ORDER (zuck, 2026-11-24 18:06Z, permanent): exotics are banned from mining, judging and
trading. The sealed judge (`scripts/external_gauntlet.py`) judges whatever the docket holds, so
the one place a cell can be kept from a judge slot without touching the seal is the docket door,
`research/merge_hypotheses.py`, beside the unbuildable set-aside it already runs.

WHAT IT DOES. Every docket row whose symbol `research.universe_policy.is_exotic_symbol` (the
desk's ONE exotic definition) calls exotic is moved out of the docket into
`data/hypotheses/exotic_set_aside.json`, with `excluded_reason: EXOTIC_BANNED`. The bank is
RE-OFFERED to every merge (so a row is never lost, and a symbol the registry re-classifies returns
the next pass) and re-split before ordering. The freed judge slots go to the non-exotic rows: the
judge's budget is unchanged and simply reaches further down a docket that no longer holds them.

WHAT IT NEVER DOES. It is not a verdict: an excluded cell is NOT charged as a trial (it is not
written to the parked-trials census, and no ledger row is created for it), no gate, threshold or
certificate is touched, and the count is published -- `count`, `reason`, `by_family`,
`by_symbol` -- so the exclusion is a named number, never a silent drop. Fails OPEN: a fault keeps
every row in the docket and says so in `status`.
"""
from __future__ import annotations

import contextlib
import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

REASON = "EXOTIC_BANNED"
SET_ASIDE_NAME = "exotic_set_aside.json"
RULE = ("zuck 2026-11-24 18:06Z: exotics banned from mining, judging and trading; classified by "
        "research.universe_policy.is_exotic_symbol; set aside by name, re-offered every merge, "
        "never charged as a trial")
_STAMPS = ("excluded_reason", "excluded_at")


def row_symbol(row: dict[str, Any]) -> str:
    return str(row.get("sym") or row.get("symbol") or "")


def _classifier() -> Callable[[str], bool]:
    from research.universe_policy import is_exotic_symbol
    memo: dict[str, bool] = {}

    def is_exotic(sym: str) -> bool:
        if sym not in memo:
            memo[sym] = bool(is_exotic_symbol(sym)) if sym else False
        return memo[sym]
    return is_exotic


def split(rows: list[dict[str, Any]], stamp: str, *,
          is_exotic: Callable[[str], bool] | None = None
          ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """(docket rows, exotic rows set aside, report). Fails open: a fault keeps every row."""
    try:
        fn = is_exotic or _classifier()
        keep: list[dict[str, Any]] = []
        aside: list[dict[str, Any]] = []
        for row in rows:
            if isinstance(row, dict) and fn(row_symbol(row)):
                row["excluded_reason"] = REASON
                row["excluded_at"] = stamp
                aside.append(row)
            else:
                keep.append(row)
    except Exception as exc:
        for row in rows:
            if isinstance(row, dict):
                for k in _STAMPS:
                    row.pop(k, None)
        return rows, [], {"status": f"FAILED: {type(exc).__name__}", "count": 0,
                          "reason": REASON}
    fam = Counter(str(r.get("family") or "") for r in aside)
    sym = Counter(row_symbol(r) for r in aside)
    return keep, aside, {
        "status": "APPLIED", "reason": REASON, "count": len(aside),
        "docket_rows_after": len(keep), "charged_as_trial": False,
        "by_family": dict(sorted(fam.items(), key=lambda kv: (-kv[1], kv[0]))),
        "by_symbol": dict(sorted(sym.items(), key=lambda kv: (-kv[1], kv[0]))[:40]),
        "symbols": len(sym), "rule": RULE,
    }


def read_set_aside(path: Path) -> list[dict[str, Any]]:
    """The banked rows with this module's stamps removed. An unreadable file is moved aside
    (never overwritten) so its rows are not lost."""
    if not path.exists():
        return []
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        with contextlib.suppress(OSError):
            path.replace(path.with_name(path.name + ".unreadable"))
        return []
    out = []
    for row in doc if isinstance(doc, list) else []:
        if isinstance(row, dict):
            for k in _STAMPS:
                row.pop(k, None)
            out.append(row)
    return out


def write_set_aside(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(rows, indent=1, default=str), "utf-8")
    tmp.replace(path)


def judged_split(judged_cells: Any, *, is_exotic: Callable[[str], bool] | None = None
                 ) -> dict[str, Any]:
    """Distinct cells carrying a real verdict, split exotic / non-exotic by the cell id's symbol
    (the gauntlet's id is `<sym>.<family>.p=<hash>`). UNMEASURED on a fault, never a zero."""
    try:
        fn = is_exotic or _classifier()
        ex = non = 0
        for cid in judged_cells or ():
            if fn(str(cid).split(".", 1)[0]):
                ex += 1
            else:
                non += 1
        return {"status": "MEASURED", "judged_cells_non_exotic": non,
                "judged_cells_exotic": ex,
                "basis": "distinct cells with a real verdict in gate_verdict_ledger.jsonl"}
    except Exception as exc:
        return {"status": "UNMEASURED", "why": type(exc).__name__}
