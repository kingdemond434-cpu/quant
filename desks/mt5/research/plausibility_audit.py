"""PLAUSIBILITY AUDIT -- a certified cell that looks too good is examined for leaks, never assumed.

zuck, 2026-11-06 (a transcript: an LLM loop threw out an 11,000% PnL as look-ahead) and
2026-11-11: "the too good to be true one should know the difference between a true mind blowing
edge and the fake one ... only dismiss after proof not assuming".

WHAT IT DOES. For every runnable certificate (`shadow_admission.authorized_runs`, H1 lane) it
rebuilds the exact certified cell through the sealed judge's own `build_cell`, takes its daily
net-R series with the judge's own `daily_series`, and applies `libs.validation.plausibility`:

* the screen (annualised Sharpe > 6, or > 95% winning days on >= 40 days) only FLAGS;
* a flagged cell runs the forensics from its own signals -- truncation (the family re-run, via
  `build_cell(h1_override=...)`, on bars cut short; a past signal that changes was computed from
  the future, which is PROOF), +1-bar entry delay, mirrored-direction and shuffled-time nulls,
  PIT availability of declared inputs, later-slice robustness.

WHAT IT WRITES, evidence either way:

* `data/plausibility/forensics.jsonl` -- one row per flagged cell per run, every test's numbers;
* `data/plausibility/FAST_TRACK.json` -- MONSTER_CANDIDATE / DELAY_FRAGILE cells, which forward
  shadow should read first (every sizing rail unchanged);
* `data/plausibility/LEAK_PROVEN.json` -- cells whose leak was PROVEN, with the proof;
* `reports/PLAUSIBILITY_AUDIT.json` -- the run summary.

WHAT IT DOES NOT DO. It changes no certificate, no sizing and no live book: the judge and the
promoter are byte-sealed, so the in-gauntlet stage that refuses a LEAK_PROVEN cell ships as a
sealed patch for the re-sign train (`patches/plausibility_forensics/`). Until it lands, a proven
leak is published here for the Judge's own revocation path, never revoked by this script.

    python desks/mt5/research/plausibility_audit.py [--max-cells N]

ROTATING, so the hourly leg stays bounded: each pass examines at most ``--max-cells`` certificates
from a cursor kept in ``data/plausibility/cursor.json`` and wraps, so every certificate is
re-examined every few hours whatever the book's size.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK), str(DESK / "research"), str(DESK / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.validation.plausibility import (  # noqa: E402
    build_arms,
    forensics,
    pit_violations,
    screen,
    truncation_test,
)

OUT_DIR = DESK / "data" / "plausibility"
REPORT = DESK / "reports" / "PLAUSIBILITY_AUDIT.json"
FAST = ("MONSTER_CANDIDATE", "DELAY_FRAGILE")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def examine(cell: dict[str, Any], rebuild: Any, daily_series: Any) -> dict[str, Any]:
    """Screen one built cell; run forensics only when the screen flags it."""
    df, sigs, costs = cell["df"], list(cell.get("sigs") or []), cell["costs"]
    ds = daily_series(df, sigs, costs)
    arr = ds.to_numpy(float) if ds is not None else []
    sc = screen(arr)
    row: dict[str, Any] = {"screen": sc, "verdict": "PLAUSIBLE"}
    if not sc["suspect"]:
        return row

    def _arm(sg: list[Any]) -> Any:
        a = daily_series(df, sg, costs)
        return None if a is None else a.to_numpy(float)

    def _regen(frame: Any) -> list[Any]:
        rebuilt = rebuild(frame)
        return list((rebuilt or {}).get("sigs") or [])

    arms = build_arms(df, sigs, _arm)
    first = min((s.time for s in sigs), default=None)
    fx = forensics(arr, delayed=arms.get("delayed"), flipped=arms.get("flipped"),
                   shuffled=arms.get("shuffled"),
                   pit_violations=pit_violations(cell.get("pit_rows"), first),
                   truncation=truncation_test(df, sigs, _regen))
    fx["arm_errors"] = {k: v for k, v in arms.items() if k.endswith("_error")}
    row.update(fx)
    return row


def _merge(path: Path, fresh: list[dict[str, Any]], examined: set[str], at: str,
           rule: str) -> None:
    """Replace this pass's certificates in a standing list; keep every other certificate's row
    (the audit rotates, so one pass sees only part of the book)."""
    try:
        old = json.loads(path.read_text("utf-8")).get("cells") or []
    except (OSError, ValueError, AttributeError):
        old = []
    kept = [c for c in old if str(c.get("certificate")) not in examined]
    path.write_text(json.dumps({"updated_at": at, "cells": kept + fresh, "rule": rule},
                               indent=2, default=str), encoding="utf-8")


def _write_lists(rows: list[dict[str, Any]], examined: set[str]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / "forensics.jsonl").open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str) + "\n")
    at = _now()

    def _brief(r: dict[str, Any]) -> dict[str, Any]:
        return {k: r.get(k) for k in ("certificate", "sym", "family", "params", "verdict",
                                      "proof")} | {
            "annual_sharpe": (r.get("screen") or {}).get("annual_sharpe"), "at": r.get("at")}

    _merge(OUT_DIR / "FAST_TRACK.json",
           [_brief(r) | {"forward_priority": "FAST_TRACK"} for r in rows
            if r.get("verdict") in FAST], examined, at,
           "flagged too-good, cleared every forensic test run: forward shadow first, "
           "normal sizing rails")
    _merge(OUT_DIR / "LEAK_PROVEN.json",
           [_brief(r) for r in rows if r.get("verdict") == "LEAK_PROVEN"], examined, at,
           "leak PROVEN by forensics; published for the Judge's revocation path, never "
           "revoked by this script")


CURSOR = OUT_DIR / "cursor.json"
MAX_CELLS = 25


def _rotate(runs: list[dict[str, Any]], max_cells: int) -> tuple[list[dict[str, Any]], int]:
    if not runs:
        return [], 0
    try:
        start = int(json.loads(CURSOR.read_text("utf-8")).get("next", 0)) % len(runs)
    except (OSError, ValueError, TypeError):
        start = 0
    take = [runs[(start + i) % len(runs)] for i in range(min(max_cells, len(runs)))]
    return take, (start + len(take)) % len(runs)


def run(max_cells: int = MAX_CELLS) -> dict[str, Any]:
    import external_gauntlet as eg
    from shadow_admission import authorized_runs

    meta = json.loads((DESK / "data" / "universe" / "universe.json").read_text("utf-8"))
    all_runs = sorted(authorized_runs(DESK, lanes=("h1",)),
                      key=lambda r: str(r.get("certificate")))
    runs, nxt = _rotate(all_runs, max_cells)
    examined: list[dict[str, Any]] = []
    flagged: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for r in runs:
        sym, fam = str(r.get("symbol")), str(r.get("family") or "")
        params = dict(r.get("params") or {})
        try:
            cell = eg.build_cell(sym, fam, params, meta)
            if not cell:
                skipped.append({"certificate": r.get("certificate"), "why": "not rebuildable"})
                continue

            def _rebuild(frame: Any, _s: str = sym, _f: str = fam,
                         _p: dict[str, Any] = params) -> Any:
                return eg.build_cell(_s, _f, dict(_p), meta, h1_override=frame)

            row = examine(cell, _rebuild, eg.daily_series)
        except Exception as exc:  # one cell's failure is reported, never the batch's
            skipped.append({"certificate": r.get("certificate"),
                            "why": f"{type(exc).__name__}"})
            continue
        row = {"at": _now(), "certificate": r.get("certificate"), "sym": sym, "family": fam,
               "params": params} | row
        examined.append({k: row[k] for k in ("certificate", "verdict")})
        if row["verdict"] != "PLAUSIBLE":
            flagged.append(row)
    _write_lists(flagged, {str(e['certificate']) for e in examined})
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CURSOR.write_text(json.dumps({"next": nxt, "of": len(all_runs), "at": _now()}),
                      encoding="utf-8")
    counts: dict[str, int] = {}
    for e in examined:
        counts[e["verdict"]] = counts.get(e["verdict"], 0) + 1
    doc = {"at": _now(), "certificates": len(all_runs), "this_pass": len(runs),
           "examined": len(examined),
           "verdicts": counts, "skipped": skipped[:50], "n_skipped": len(skipped),
           "flagged": [{k: f.get(k) for k in ("certificate", "verdict", "proof")}
                       for f in flagged],
           "status": "MEASURED" if examined else "UNMEASURED"}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-cells", type=int, default=MAX_CELLS)
    ap.add_argument("--once", action="store_true", help="accepted for the hourly leg")
    a = ap.parse_args(argv)
    doc = run(a.max_cells)
    print(json.dumps({k: doc[k] for k in ("certificates", "examined", "verdicts", "n_skipped",
                                          "status")}))
    return 0 if doc["status"] == "MEASURED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
