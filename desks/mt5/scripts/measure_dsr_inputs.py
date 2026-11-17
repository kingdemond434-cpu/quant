"""Measure the deflated-Sharpe inputs and publish reports/DSR_INPUTS.json (hourly leg `dsr_inputs`).

Harvests the latest sweep's judged trials (`reports/universal_gates_external.json`) into
`data/dsr_trial_sharpes.jsonl`, then measures the cross-trial Sharpe variance per family over the
trailing window and the lifetime effective trials per family, with provenance and a content hash.
The sealed judge reads the result through `libs.research.dsr_inputs.load_verified` and fails
closed (`dsr_inputs_unmeasured`) when it is absent, stale or does not verify. See that module.

PUBLISH FIRST, HARVEST BOUNDED (2026-10-21): an unchanged report costs a stat; otherwise the
document is written from the existing ledger before the harvest, and the harvest stops at
`--budget-s` (default: `dsr_inputs.DEFAULT_HARVEST_BUDGET_S`, or 60% of the cycle's
`QUANT_LEG_BUDGET_S` when that is smaller) and says DEFERRED rather than being killed at the cap.

Exit 0 whether or not the measurement is MEASURED: an UNMEASURED document is a published verdict,
not a crash. Exit 1 only when the document could not be written.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
#: What the hourly leg `dsr_inputs` publishes; mirrors `dsr_inputs.REPORT` (a test pins them).
OUT = DESK / "reports" / "DSR_INPUTS.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research import dsr_inputs  # noqa: E402


def default_budget_s() -> float:
    """The harvest deadline: the library default, or 60% of the cap the cycle told us, if lower,
    so the final measure and write fit inside the leg."""
    budget = float(dsr_inputs.DEFAULT_HARVEST_BUDGET_S)
    try:
        leg = float(os.environ.get("QUANT_LEG_BUDGET_S") or 0)
    except ValueError:
        leg = 0.0
    return min(budget, 0.6 * leg) if leg > 0 else budget


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg's form)")
    ap.add_argument("--report", type=Path, default=None, help="sweep report to harvest")
    ap.add_argument("--ledger", type=Path, default=None, help="trial-Sharpe ledger")
    ap.add_argument("--out", type=Path, default=None, help="where to write DSR_INPUTS.json")
    ap.add_argument("--window-days", type=int, default=dsr_inputs.WINDOW_DAYS)
    ap.add_argument("--budget-s", type=float, default=None,
                    help="seconds the harvest may take before it stops and reports DEFERRED")
    a = ap.parse_args(argv)
    budget = default_budget_s() if a.budget_s is None else a.budget_s
    try:
        doc = dsr_inputs.run(report_path=a.report, ledger_path=a.ledger, out=a.out,
                             window_days=a.window_days, budget_s=budget)
    except OSError as exc:
        print(f"dsr_inputs: could not write: {type(exc).__name__}", file=sys.stderr)
        return 1
    pooled = (doc.get("variance") or {}).get("pooled") or {}
    eff = doc.get("effective_trials") or {}
    h = (doc.get("provenance") or {}).get("harvest") or {}
    print(json.dumps({"status": doc["status"], "why": doc.get("why"),
                      "pooled_variance": pooled.get("variance"), "n": pooled.get("n"),
                      "effective_trials": eff.get("effective"),
                      "nominal_trials": eff.get("nominal"),
                      "harvest": h.get("appended"), "harvest_status": h.get("status"),
                      "harvest_why": h.get("why"), "budget_s": budget,
                      "content_sha256": doc["content_sha256"][:16]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
