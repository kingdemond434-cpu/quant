"""PER-PRODUCER STATUS AND RATCHETING FLOORS for the funnel's `producers` rows (2026-11-25).

The funnel (research/funnel.py) already measures, per producer, RAW -> ROWS -> TESTABLE -> ... and
ratchets DESK-level floors. Nothing held a single producer to its own best: a seat whose testable
breadth halved, or whose conversion fell from 40% to 4%, read exactly as it had the week before.
This module gives every producer row three floors that only rise and one status:

    breadth     distinct testable breadth units (claim_selection.breadth_unit at TESTABLE)
    depth       testable cells per family that has one
    conversion  ROWS -> TESTABLE rate (the share of what the producer made that the judge can run)

    status      OK           producing, every measured floor met
                BELOW_FLOOR  producing, a floor violated (named in `violated`)
                STALE        the heartbeat says it has not produced inside its window
                             (STALE / ERROR / TIMEOUT / SILENT / NO_INPUT in PRODUCER_HEARTBEAT)
                DEAD         nothing testable and nothing raw on record, or the heartbeat says DEAD

THE FLOORS RATCHET UP ONLY, through the funnel's own `ratchet_one` (a met floor lifts to
RATCHET_SHARE of the reading; it never falls; there is no ceiling), and the writer merges with
the file on disk so no writer -- this one included -- can lower one. An unmeasured reading leaves
its floor where it was and says UNMEASURED for that metric; the producer's STATUS is still one of
the four names above, never UNMEASURED.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

METRICS = ("breadth", "depth", "conversion")
OK, BELOW_FLOOR, STALE, DEAD = "OK", "BELOW_FLOOR", "STALE", "DEAD"
STATUSES = (OK, BELOW_FLOOR, STALE, DEAD)
#: Heartbeat statuses that mean "not producing in its window".
_HB_STALE = frozenset({"STALE", "ERROR", "TIMEOUT", "SILENT", "NO_INPUT"})


def _num(v: Any) -> float | int | None:
    return v if isinstance(v, int | float) and not isinstance(v, bool) else None


def readings(row: Mapping[str, Any]) -> dict[str, Any]:
    """The three floor metrics of one funnel producer row (None where unmeasured)."""
    depth = row.get("depth") if isinstance(row.get("depth"), Mapping) else {}
    units = depth.get("breadth_units") if isinstance(depth.get("breadth_units"), Mapping) else {}
    conv = None
    for t in row.get("transitions") or []:
        if isinstance(t, Mapping) and t.get("transition") == "ROWS->TESTABLE":
            conv = _num(t.get("rate"))
    return {"breadth": _num(units.get("TESTABLE")),
            "depth": _num(depth.get("testable_cells_per_family")),
            "conversion": conv}


def read_heartbeat(path: Path | None) -> dict[str, dict[str, Any]]:
    """producer -> its PRODUCER_HEARTBEAT row (legs and seats); {} when absent or unreadable."""
    if path is None:
        return {}
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for r in (doc.get("producers") or []) if isinstance(doc, dict) else []:
        if isinstance(r, dict) and r.get("producer") and r.get("kind") in ("leg", "seat"):
            out.setdefault(str(r["producer"]), r)
    return out


def annotate(rows: list[dict[str, Any]], floors: Mapping[str, Any] | None,
             heartbeat: Mapping[str, Mapping[str, Any]] | None, now: datetime,
             *, ratchet: Any) -> dict[str, Any]:
    """Write `status`, `floors` and `violated` onto every producer row; return the new floors
    block (producer -> {metric: {floor, raised_at}}). `ratchet` is funnel.ratchet_one."""
    old_all = dict(floors or {})
    hb = heartbeat or {}
    stamp = now.isoformat(timespec="seconds")
    new_all: dict[str, Any] = {}
    for row in rows:
        name = str(row.get("producer") or "")
        if not name:
            continue
        got = readings(row)
        old = old_all.get(name) if isinstance(old_all.get(name), Mapping) else {}
        new: dict[str, Any] = {}
        verdicts: dict[str, Any] = {}
        for m in METRICS:
            prev = (old.get(m) or {}) if isinstance(old.get(m), Mapping) else {}
            f_old = prev.get("floor")
            f_new, v = ratchet(f_old, got[m], integer=(m == "breadth"))
            new[m] = {"floor": f_new,
                      "raised_at": stamp if f_new != f_old else prev.get("raised_at")}
            verdicts[m] = {"value": got[m], "floor": f_old, "status": v}
        new_all[name] = new
        stages = row.get("stages") if isinstance(row.get("stages"), Mapping) else {}
        raw, testable = _num(stages.get("RAW")), _num(stages.get("TESTABLE"))
        beat = hb.get(name) or {}
        violated = sorted(m for m, v in verdicts.items() if v["status"] == "VIOLATED")
        if str(beat.get("status")) == "DEAD" or (not raw and not testable):
            status, why = DEAD, (f"heartbeat DEAD: {beat.get('why')}" if beat.get("status")
                                 == "DEAD" else "no raw row and no testable cell on record")
        elif str(beat.get("status")) in _HB_STALE:
            status, why = STALE, f"heartbeat {beat.get('status')}: {beat.get('why')}"
        elif violated:
            status, why = BELOW_FLOOR, "below its own floor on " + ", ".join(violated)
        else:
            status, why = OK, "producing; every measured floor met"
        row["status"] = status
        row["status_why"] = str(why)[:240]
        row["floors"] = verdicts
        row["violated"] = violated
        row["heartbeat"] = {k: beat.get(k) for k in ("status", "kind", "last_ok_at",
                                                     "last_write_at") if beat.get(k)} or None
    # A producer that vanished from this pass keeps its floors: silence never lowers one.
    for name, prev in old_all.items():
        new_all.setdefault(name, prev)
    return new_all


def merge_up(disk: Mapping[str, Any] | None, new: Mapping[str, Any] | None) -> dict[str, Any]:
    """Every per-producer floor the max of the file on disk and the new reading."""
    out: dict[str, Any] = {k: dict(v) for k, v in (new or {}).items() if isinstance(v, Mapping)}
    for name, prev in (disk or {}).items():
        if not isinstance(prev, Mapping):
            continue
        cur = out.setdefault(name, {})
        for m in METRICS:
            p = prev.get(m) if isinstance(prev.get(m), Mapping) else {}
            c = cur.get(m) if isinstance(cur.get(m), Mapping) else {}
            pf, cf = _num(p.get("floor")), _num(c.get("floor"))
            if pf is not None and (cf is None or pf > cf):
                cur[m] = {"floor": pf, "raised_at": p.get("raised_at")}
            elif m not in cur and p:
                cur[m] = dict(p)
    return out


def summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    out = dict.fromkeys(STATUSES, 0)
    for r in rows:
        s = r.get("status")
        if s in out:
            out[s] += 1
    return out
