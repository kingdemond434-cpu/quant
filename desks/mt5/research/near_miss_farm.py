#!/usr/bin/env python3
"""NEAR-MISS FARM -- paper-forward every near-miss cell, 24/7, on its own ledger with no authority.

WHY (principal 2026-10-13, idea 4: "paper-forward every near-miss cell 24/7 so untouched evidence
accumulates while the judge works")

`reports/FORWARD_CURE_ROSTER.json` holds every cell that cleared ALL FIVE validity gates and
missed only on power -- 1,240 of them on 2026-09-24, every one failing `deflated_sharpe`. Since
the power-cure lane was deleted from `shadow_admission` (principal 2026-09-24, "delete the
other") those cells gather no evidence at all: the honest relief valve the deletion named is
"MORE HISTORY", and the only history that does not exist yet is the history after the judge
looked. Each day un-farmed is a day of out-of-sample evidence the desk will never be able to
collect retroactively.

WHAT THIS IS, and every line below is a fence:

  * ONE ENGINE. Rows go through `shadow_forward.main(rows=..., ledger=...)`, the parameterised
    entry point that exists so no second forward evaluator is ever written: same bars, costs,
    side resolution, banned-family door, universe-policy door and clock-breach fence.
  * ITS OWN LEDGER, OUTSIDE EVERY CLOCK STORE. `reports/shadow/farm/near_miss_farm.json` -- a
    subdirectory and a name that no `*shadow_state.json` / `*_state.json` glob, no
    `retired_clocks.CLOCK_STORES` entry, and no promoter, enrolment census or allocator reads.
  * NO AUTHORITY. Every row is passed with `promotion_authority=False` and admission
    `NEAR_MISS_FARM`, a label `pipeline/promote.py` matches to no branch. A farm clock is not a
    certificate, is not counted as one, and joins no multiplicity cohort: this is exactly the
    distinction whose absence got the 2026-09-24 lane deleted (120 cure clocks reported as
    certificates). The farm adds evidence; the judge's bar, trial counts and verdicts are
    untouched.
  * ITS OWN WATERMARK. `shadow_forward.main` records `leg:enrol_clocks` progress; the farm
    records `leg:near_miss_farm` instead, so the certified lane's stall detector never reads a
    farm count.

WHAT IT PUBLISHES: `reports/NEAR_MISS_FARM.json` -- per cell the forward n, expectancy, drawdown
and days, and whether that forward record alone already meets the gate spec's
`forward_cure_thresholds`. That flag is EVIDENCE for the judge and the research loop (which
near-miss mechanisms hold up on data nobody fitted), never a promotion.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORTS = BASE / "reports"
ROSTER = REPORTS / "FORWARD_CURE_ROSTER.json"
SNAPSHOT = REPORTS / "POWER_CURE_CANDIDATES.json"
LEDGER_REL = "farm/near_miss_farm.json"
OUT = REPORTS / "NEAR_MISS_FARM.json"
ADMISSION = "NEAR_MISS_FARM"
UNMEASURED = "UNMEASURED"
#: The gate spec's cure thresholds, read from the spec; these literals are the fallback and are
#: byte-identical to policy/gate_spec.yaml today.
FALLBACK_CURE = {"min_trades": 50, "min_exp_r": 0.05, "max_dd_r": -25.0, "min_days_active": 14}


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def cure_thresholds() -> dict[str, float]:
    try:
        import yaml
        spec = yaml.safe_load((BASE / "policy" / "gate_spec.yaml").read_text("utf-8"))
        found = _find(spec, "forward_cure_thresholds")
        if isinstance(found, dict) and all(k in found for k in FALLBACK_CURE):
            return {k: float(found[k]) for k in FALLBACK_CURE}
    except Exception:
        pass
    return {k: float(v) for k, v in FALLBACK_CURE.items()}


def _find(doc: Any, key: str) -> Any:
    if isinstance(doc, dict):
        if key in doc:
            return doc[key]
        for v in doc.values():
            hit = _find(v, key)
            if hit is not None:
                return hit
    return None


def roster_rows() -> tuple[dict[str, dict[str, Any]], str]:
    """The cumulative roster, else this sweep's snapshot, else nothing (and say which)."""
    doc = _read(ROSTER)
    rows = doc.get("rows") if isinstance(doc, dict) else None
    if isinstance(rows, dict) and rows:
        return rows, "reports/FORWARD_CURE_ROSTER.json"
    snap = _read(SNAPSHOT)
    rows = snap.get("candidates") if isinstance(snap, dict) else None
    if isinstance(rows, dict) and rows:
        return rows, "reports/POWER_CURE_CANDIDATES.json (roster absent)"
    return {}, f"{UNMEASURED}: neither the cure roster nor the snapshot is on disk"


def farm_rows(roster: dict[str, dict[str, Any]]
              ) -> tuple[list[tuple[Any, ...]], list[dict[str, Any]]]:
    """Engine rows for every roster cell with a runnable spec; refusals named, never guessed."""
    from research import shadow_forward as sf
    rows: list[tuple[Any, ...]] = []
    refused: list[dict[str, Any]] = []
    for key, r in sorted(roster.items()):
        spec = r.get("shadow_spec") if isinstance(r, dict) else None
        if not isinstance(spec, dict) or not spec.get("symbol") or not spec.get("selector"):
            refused.append({"cell": key, "why": "no shadow_spec with a symbol and a selector"})
            continue
        fam = str(spec.get("family") or "session_range_breakout")
        params = dict(spec.get("params") or {})
        # THE SIDE LIVES IN PARAMS ON A JUDGE CELL. The gauntlet calls fn(bars, **params) when
        # `side` is a param, so a short cell is short there; the forward engine passes side as
        # its own argument, and a second `side` in params would raise. Moved, never dropped.
        if not spec.get("side") and "side" in params:
            raw = params.pop("side")
            spec = {**spec, "side": "SHORT" if str(raw).strip().upper() in ("-1", "SHORT")
                    else "LONG"}
        side = sf._runnable_side(spec, fam)
        if side is None:
            refused.append({"cell": key, "why": f"side {spec.get('side')!r} not runnable"})
            continue
        rows.append((str(spec["symbol"]), str(spec["selector"]), params, fam, side, ADMISSION, tuple(r.get("failed_power_gates") or ()), False))
    return rows, refused


def _farm_watermark(enrolled: int, ledger: str) -> None:
    try:
        from libs.ops.control_plane import watermarks as wm
        wm.progress("leg:near_miss_farm", "forward_observations", enrolled, ledger=ledger)
    except Exception:
        pass


def evaluate(rows: list[tuple[Any, ...]]) -> Path:
    """Run the one forward engine over the farm rows into the farm ledger."""
    from research import shadow_forward as sf
    ledger = sf.SHADOW_DIR / LEDGER_REL
    ledger.parent.mkdir(parents=True, exist_ok=True)
    original = sf._enrolment_watermark
    sf._enrolment_watermark = _farm_watermark
    try:
        sf.main(rows=rows, ledger=LEDGER_REL)
    finally:
        sf._enrolment_watermark = original
    return ledger


def summarise(ledger: Path, rows: list[tuple[Any, ...]]) -> dict[str, Any]:
    """Per-cell forward record, and whether it alone meets the cure thresholds (evidence only)."""
    from research import shadow_forward as sf
    state = _read(ledger) or {}
    th = cure_thresholds()
    cells: list[dict[str, Any]] = []
    meets = with_trades = authority_leaks = 0
    for row in rows:
        key = sf.sleeve_key(row[0], row[1], row[2], row[3], row[4])
        st = state.get(key) if isinstance(state, dict) else None
        if not isinstance(st, dict):
            cells.append({"key": key, "status": UNMEASURED, "why": "not yet evaluated"})
            continue
        if st.get("promotion_authority"):
            authority_leaks += 1
        n = int(st.get("n") or 0)
        exp_r = st.get("exp_r")
        dd = float(st.get("max_dd_r") or 0.0)
        days = None
        try:
            first = datetime.fromisoformat(str(st.get("forward_start") or st.get("enrolled_at")))
            if first.tzinfo is None:
                first = first.replace(tzinfo=UTC)
            days = (datetime.now(tz=UTC) - first).days
        except ValueError:
            pass
        ok = (n >= th["min_trades"] and exp_r is not None and float(exp_r) > th["min_exp_r"]
              and dd > th["max_dd_r"] and days is not None and days >= th["min_days_active"])
        with_trades += n > 0
        meets += ok
        cells.append({"key": key, "symbol": row[0], "family": row[3], "side": row[4],
                      "failed_power_gates": list(row[6]), "status": st.get("status"),
                      "n": n, "exp_r": exp_r, "max_dd_r": dd, "days": days,
                      "meets_forward_cure_thresholds": bool(ok)})
    cells.sort(key=lambda c: (-(c.get("n") or 0), str(c.get("key"))))
    return {"cells_farmed": len(rows), "cells_with_forward_trades": with_trades,
            "meeting_forward_cure_thresholds": meets, "thresholds": th,
            "authority_leaks": authority_leaks, "cells": cells[:2000]}


def run(*, dry_run: bool = False, out: Path | None = None) -> dict[str, Any]:
    roster, source = roster_rows()
    rows, refused = farm_rows(roster)
    doc: dict[str, Any] = {
        "generated_at": _now(), "producer": "desks/mt5/research/near_miss_farm.py",
        "source": source, "roster_rows": len(roster), "refused": refused[:200],
        "n_refused": len(refused), "ledger": f"reports/shadow/{LEDGER_REL}",
        "authority": ("NONE. Every farm row is passed with promotion_authority=False and "
                      f"admission {ADMISSION}; the ledger is outside every clock store the "
                      "promoter, enrolment census or allocator reads. Evidence, never a "
                      "certificate."),
    }
    if rows and not dry_run:
        ledger = evaluate(rows)
        doc.update(summarise(ledger, rows))
    else:
        doc.update({"cells_farmed": len(rows),
                    "status": "DRY_RUN" if dry_run else f"{UNMEASURED}: no runnable rows"})
    path = out or OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(path)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    doc = run(dry_run=args.dry_run, out=args.out)
    print(f"near_miss_farm: source={doc['source']} roster={doc['roster_rows']} "
          f"farmed={doc.get('cells_farmed')} with_trades={doc.get('cells_with_forward_trades')} "
          f"meets_cure={doc.get('meeting_forward_cure_thresholds')} "
          f"refused={doc['n_refused']} leaks={doc.get('authority_leaks')}")
    return 1 if doc.get("authority_leaks") else 0


if __name__ == "__main__":                                       # pragma: no cover - CLI
    raise SystemExit(main())
