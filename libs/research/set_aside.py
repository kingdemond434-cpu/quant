"""THE NAMED REFUSAL: what a batch budget did NOT look at, written down instead of dropped.

THE LAW (docs/LAWS.md §7, principal 2026-09-23): there is ONE judge. A producer proposes and
the sealed gauntlet disposes -- only the four immutable evaluator files may refuse a cell. A
`rows[:MAX_N]` is not a quality screen, it is a BATCH BUDGET, and the budget stays: a pass that
tried to carry every row would spend the hour on bookkeeping. What the budget may not do is
discard silently, because a silent discard is indistinguishable from an empty search, and the
desk then reads "this organ found nothing" when the truth is "this organ found 900 and looked
at 40".

So the remedy is not to remove the truncation. It is to RECORD it: the organ, the stage, how
many rows were considered, how many were kept, the ORDERING KEY that decided which ones (so a
reader can tell a principled top-N from an arbitrary one), and the pass. Cumulative totals per
`organ/stage` are never truncated; the recent-row window is, because it is an illustration and
the totals are the measurement.

    findings = set_aside.take(out, MAX_FINDINGS, organ="alpha_lineage_search",
                              stage="unsearched_axes", ordering="-untried,-n_nodes")

`take` returns the truncated list exactly as `out[:MAX_FINDINGS]` did, so a call site changes
by one line and the budget is unchanged. `note` is the same record without the slicing, for a
site whose truncation is already written another way.

NEVER RAISES. A ledger that can take down the organ it measures is removed within a week.
"""
from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "desks" / "mt5" / "reports" / "SET_ASIDE_LEDGER.json"

#: The rolling window of individual refusal rows. The per-(organ, stage) TOTALS below are
#: cumulative and never trimmed -- trimming the measurement would repeat the defect this file
#: exists to fix. Only the illustrative rows roll.
MAX_ROWS = 500

T = TypeVar("T")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def take(rows: Sequence[T], limit: int, *, organ: str, stage: str, ordering: str,
         pass_id: str | None = None, path: Path | None = None) -> list[T]:
    """`rows[:limit]`, with the remainder recorded as a named refusal. Budget unchanged."""
    kept = list(rows[:limit]) if limit >= 0 else list(rows)
    note(organ, stage, kept=len(kept), considered=len(rows), ordering=ordering,
         pass_id=pass_id, path=path)
    return kept


def note(organ: str, stage: str, *, kept: int, considered: int, ordering: str,
         pass_id: str | None = None, path: Path | None = None) -> dict[str, Any] | None:
    """Record that `considered - kept` rows were set aside. Returns the row, or None when the
    ledger could not be written (which is never an error the caller has to handle)."""
    aside = max(0, int(considered) - int(kept))
    row = {"at": _now(), "organ": str(organ), "stage": str(stage), "considered": int(considered),
           "kept": int(kept), "set_aside": aside, "ordering": str(ordering),
           "pass": str(pass_id or os.environ.get("QUANT_PASS_ID") or _now())}
    try:
        _append(row, path or PATH)
    except Exception:
        return None
    return row


def _append(row: dict[str, Any], path: Path) -> None:
    doc: dict[str, Any] = {}
    with contextlib.suppress(Exception):
        if path.exists():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                doc = loaded
    totals = doc.get("totals")
    if not isinstance(totals, dict):
        totals = {}
    rows = doc.get("rows")
    if not isinstance(rows, list):
        rows = []
    key = f"{row['organ']}/{row['stage']}"
    t = totals.get(key)
    if not isinstance(t, dict):
        t = {"passes": 0, "considered": 0, "kept": 0, "set_aside": 0, "ordering": row["ordering"]}
    t["passes"] = int(t.get("passes", 0)) + 1
    t["considered"] = int(t.get("considered", 0)) + int(row["considered"])
    t["kept"] = int(t.get("kept", 0)) + int(row["kept"])
    t["set_aside"] = int(t.get("set_aside", 0)) + int(row["set_aside"])
    t["ordering"] = row["ordering"]
    t["last_at"] = row["at"]
    totals[key] = t
    if int(row["set_aside"]) > 0:
        rows.append(row)
    doc = {"at": row["at"],
           "rule": ("a batch budget may truncate, it may not discard silently: every row here "
                    "names the organ, the stage, the count set aside, the ordering key that "
                    "chose the survivors and the pass. Only the four immutable evaluator files "
                    "may REFUSE a cell (LAWS 7); everything here is a budget, not a verdict."),
           "organs": sorted({str(v).split("/")[0] for v in totals}),
           "set_aside_total": sum(int(v.get("set_aside", 0)) for v in totals.values()
                                  if isinstance(v, dict)),
           "totals": totals, "rows_window": MAX_ROWS, "rows": rows[-MAX_ROWS:]}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=False), encoding="utf-8")
    os.replace(tmp, path)


def read(path: Path | None = None) -> dict[str, Any]:
    """The ledger, or an empty shell when nothing has been recorded yet (UNMEASURED, not zero)."""
    p = path or PATH
    with contextlib.suppress(Exception):
        if p.exists():
            doc = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(doc, dict):
                return doc
    return {"at": None, "totals": {}, "rows": [], "set_aside_total": 0, "organs": []}
