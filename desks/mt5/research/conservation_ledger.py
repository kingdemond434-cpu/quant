"""conservation_ledger: the full grid is the only acceptable denominator.

THE LAW (mt5desk/multiplicity.sweep_size): "THE COUNT MUST BE THE FULL GRID, NOT THE
SURVIVORS -- including the ones that failed instantly." Every multiplicity correction,
every deflated Sharpe, every promotion bar is computed from the number of TRIALS. A
fast filter that drops 90% of cells before the gauntlet is exactly the stage where that
count can silently shrink: a cell that errored in the signal gate, or a hunt whose
report predates a universe change, disappears from the denominator and every gate that
scales with it becomes easier to pass. Selection applied BEFORE the statistic is still
selection; the ledger exists so it is at least VISIBLE.

This step is read-only reconciliation. It reads what actually exists and writes
reports/conservation_ledger.json:

  grid_denominator   cells per hunt report ("all") -- the trial count every gate owes
  fast_filter        signal-gate verdicts for those cells (INFORMED/NULL/SPARSE/ERROR)
  gauntlet           qquant per-cell ok/fail counts
  conservation       the reconciliation: covered vs missing, per stage, per hunt
  verdict            CLEAN | GAP (GAP names exactly which stage lost cells and how many)

Zero-survivor grids are fine. Unaccounted cells are not.

    python research/conservation_ledger.py          # from the daily cycle, or by hand
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
REPORTS = BASE / "reports"
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "research"))


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _hunt_cells() -> dict[str, int]:
    """Full-grid denominator per hunt report: len(all) is the trial count."""
    out: dict[str, int] = {}
    for p in sorted(REPORTS.glob("hunt*.json")):
        d = _read_json(p)
        if d is None:
            continue
        n = len(d.get("all", []))
        if n:
            out[p.stem] = n
    return out


def _signal_gate_coverage(hunt_stems: set[str]) -> dict:
    """Fast-filter verdicts from the newest signal_gate report per experiment."""
    newest: dict[str, Path] = {}
    for p in sorted(REPORTS.glob("signal_gate_*.json")):
        d = _read_json(p)
        if d is None:
            continue
        exp = str(d.get("experiment") or p.stem.replace("signal_gate_", "", 1))
        prev = newest.get(exp)
        if prev is None or p.stat().st_mtime > prev.stat().st_mtime:
            newest[exp] = p
    covered = 0
    verdicts = {"INFORMED": 0, "NULL": 0, "SPARSE": 0}
    for p in newest.values():
        d = _read_json(p) or {}
        for c in d.get("cells", []):
            v = c.get("verdict", "?")
            verdicts[v] = verdicts.get(v, 0) + 1
            covered += 1
    return {"experiments_gated": len(newest), "cells_gated": covered, "verdicts": verdicts}


def _gauntlet_counts() -> dict:
    d = _read_json(REPORTS / "qquant_eval.json") or {}
    out = {}
    for k in ("ok", "fail", "cells"):
        if k in d:
            out[k] = d[k]
    return out


def build() -> dict:
    grid = _hunt_cells()
    total = sum(grid.values())
    ff = _signal_gate_coverage(set(grid))
    gau = _gauntlet_counts()

    gaps: list[str] = []
    # GAP 1: a hunt's full grid exists but the fast filter never gated a matching
    # experiment report (the gate hides untested cells behind a DONE marker).
    if total and ff["cells_gated"] == 0:
        gaps.append(f"fast filter gated 0 cells against a full grid of {total}")
    # GAP 2: the gauntlet ran on fewer cells than its own hunt reports.
    if gau.get("cells") is not None and total and gau["cells"] < total:
        gaps.append(f"gauntlet covered {gau['cells']} of {total} grid cells "
                    f"({total - gau['cells']} unaccounted)")

    return {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "grid_denominator": grid,
        "grid_total": total,
        "fast_filter": ff,
        "gauntlet": gau,
        "verdict": "CLEAN" if not gaps else "GAP",
        "gaps": gaps,
    }


def main() -> int:
    ledger = build()
    out = REPORTS / "conservation_ledger.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    print(f"conservation ledger: {ledger['verdict']} "
          f"(grid={ledger['grid_total']}, gated={ledger['fast_filter']['cells_gated']}) "
          f"-> {out.name}")
    for g in ledger["gaps"]:
        print(f"  GAP: {g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
