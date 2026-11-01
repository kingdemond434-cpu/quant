"""THE ZERO-SPREAD RE-JUDGE LIST: every verdict whose 3x stress was priced on a zero spread.

The sealed `stress_costs` gate multiplied a zero spread on 14 FX majors
(`research/stress_cost_floor` explains the defect), so a pass on those symbols was a pass
against no stress at all.
`/mnt/project-files/patches/gauntlet_zero_spread_stress.patch` (desktop pass 2) makes the sealed
3x arm charge 3x a measured basis. After it lands, every cell on those symbols that PASSED
`stress_costs` must be judged again under the real stress.

THE LIST (`data/hypotheses/priority_rejudge_zero_spread.json`, {"attestation", "cells", ...}):
certified cells on a zero-spread symbol whose recorded gates passed `stress_costs` (the canon and
the survivors report), plus every gate-ledger cell on those symbols whose terminal gate comes
AFTER `stress_costs` in the sealed evaluation order or is PASSED -- it cleared stress to get there.
`research/stage1_record.PRIORITY_FILES` reads it: named priority, moved to the front of the sweep
right after the v4 re-mint cells by the two-stage sort-key patch.

LANDING IS DETECTED, NOT ASSUMED: the sealed `costs_for` is asked for EURUSD's 1x and 3x spread.
Equal means the patch has not landed; the list is then published with `cells: []`, status
WAITING_FOR_SEALED_PATCH and the count it WOULD queue, so no judge slot is spent re-judging under
the old stress. Once landed, the landing time is recorded, and a cell leaves the list when the
gate ledger shows a verdict for it after landing, or after `TTL_DAYS` -- the list is a one-time
front, never a standing re-judge. Order only: nothing is removed from any verdict store.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
HYP = DESK / "data" / "hypotheses"
LIST = HYP / "priority_rejudge_zero_spread.json"
CANON = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
REPORT = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
LEDGER = HYP / "gate_verdict_ledger.jsonl"
#: The sealed evaluation order of the gates (`run_gauntlet`'s `stages`, insertion-ordered).
GATE_ORDER = ("economic_prior", "in_sample_screen", "deflated_sharpe", "pbo", "reality_check_spa",
              "cpcv", "walk_forward", "stress_costs", "lockbox", "expected_value")
AFTER_STRESS = frozenset(GATE_ORDER[GATE_ORDER.index("stress_costs") + 1:]) | {"PASSED"}
TTL_DAYS = 3
META_LANDED = "zero_spread_patch_landed_at"


def _iso(t: datetime | None = None) -> str:
    return (t or datetime.now(tz=UTC)).isoformat(timespec="seconds")


def zero_spread_symbols(meta: dict[str, Any]) -> set[str]:
    from research.stress_cost_floor import is_zero_spread
    return {k for k, v in meta.items() if isinstance(v, dict) and "median_spread_pts" in v
            and is_zero_spread(v)}


def patch_landed(G: Any, meta: dict[str, Any], probe: str = "EURUSD") -> bool:
    """True when the sealed 3x arm on a zero-spread symbol costs more than its 1x arm."""
    try:
        return bool(G.costs_for(probe, meta, mult=G.COST_SCENARIO).spread_per_lot
                    > G.costs_for(probe, meta).spread_per_lot)
    except Exception:
        # a costs_for that REFUSES an unmeasured basis has landed too (it fails closed)
        return True


def _stress_passed_rows(path: Path, zs: set[str]) -> dict[str, str]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    sv = doc.get("survivors") if isinstance(doc, dict) else None
    rows = sv.values() if isinstance(sv, dict) else (sv or [])
    out: dict[str, str] = {}
    for r in rows:
        if not isinstance(r, dict) or str(r.get("sym") or "") not in zs:
            continue
        g = (r.get("gates") or {}).get("stress_costs") or {}
        if g.get("passed") and r.get("cell"):
            out[str(r["cell"])] = f"{path.name}: stress_costs passed"
    return out


def candidates(meta: dict[str, Any], *, canon: Path | None = None, report: Path | None = None,
               ledger: Path | None = None) -> tuple[dict[str, str], dict[str, str]]:
    """({cell: why}, {cell: last ledger 'at'}): stress-passed cells on zero-spread symbols."""
    zs = zero_spread_symbols(meta)
    out = {**_stress_passed_rows(Path(canon or CANON), zs),
           **_stress_passed_rows(Path(report or REPORT), zs)}
    last_at: dict[str, str] = {}
    last_gate: dict[str, str] = {}
    lp = Path(ledger or LEDGER)
    if not lp.exists():
        return out, last_at
    with lp.open(encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if not isinstance(r, dict) or str(r.get("sym") or "") not in zs:
                continue
            c = str(r.get("cell") or "")
            if c:
                last_gate[c] = str(r.get("terminal_gate") or "")
                last_at[c] = str(r.get("at") or "")
    for c, g in last_gate.items():
        if g in AFTER_STRESS:
            out.setdefault(c, f"gate ledger: terminal gate {g} (cleared stress_costs)")
    return out, last_at


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
    os.replace(tmp, path)


def run(con, G: Any, meta: dict[str, Any], *, list_path: Path | None = None,
        canon: Path | None = None, report: Path | None = None, ledger: Path | None = None,
        now: datetime | None = None, dry_run: bool = False) -> dict[str, Any]:
    from research import stage1_record as REC
    now = now or datetime.now(tz=UTC)
    cands, last_at = candidates(meta, canon=canon, report=report, ledger=ledger)
    landed = patch_landed(G, meta)
    landed_at = REC.get_meta(con, META_LANDED)
    if landed and not landed_at:
        landed_at = _iso(now)
        if not dry_run:
            REC.set_meta(con, META_LANDED, landed_at)
            con.commit()
    doc: dict[str, Any] = {"at": _iso(now), "source": "research/zero_spread_rejudge.py",
                           "symbols": sorted(zero_spread_symbols(meta)),
                           "would_queue": len(cands)}
    if not landed:
        doc.update(status="WAITING_FOR_SEALED_PATCH", cells=[], attestation=(
            "zero-spread stress basis: sealed patch not landed (3x == 1x on EURUSD)"))
    else:
        expired = landed_at is not None and now - datetime.fromisoformat(landed_at) > timedelta(
            days=TTL_DAYS)
        cells = [] if expired else sorted(
            c for c in cands if not (last_at.get(c) and landed_at and last_at[c] >= landed_at))
        doc.update(status="EXPIRED" if expired else "QUEUED", landed_at=landed_at, cells=cells,
                   attestation=f"zero-spread stress basis landed {landed_at}")
    if not dry_run:
        _write(Path(list_path or LIST), doc)
    return {k: v for k, v in doc.items() if k != "cells"} | {"queued": len(doc["cells"])}
