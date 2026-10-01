"""Measure the deflated-Sharpe inputs and publish reports/DSR_INPUTS.json (hourly leg `dsr_inputs`).

Harvests the latest sweep's judged trials (`reports/universal_gates_external.json`) into
`data/dsr_trial_sharpes.jsonl`, then measures the cross-trial Sharpe variance per family over the
trailing window and the lifetime effective trials per family, with provenance and a content hash.
The sealed judge reads the result through `libs.research.dsr_inputs.load_verified` and fails
closed (`dsr_inputs_unmeasured`) when it is absent, stale or does not verify. See that module.

Exit 0 whether or not the measurement is MEASURED: an UNMEASURED document is a published verdict,
not a crash. Exit 1 only when the document could not be written.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
#: What the hourly leg `dsr_inputs` publishes; mirrors `dsr_inputs.REPORT` (a test pins them).
OUT = DESK / "reports" / "DSR_INPUTS.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research import dsr_inputs  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg's form)")
    ap.add_argument("--report", type=Path, default=None, help="sweep report to harvest")
    ap.add_argument("--ledger", type=Path, default=None, help="trial-Sharpe ledger")
    ap.add_argument("--out", type=Path, default=None, help="where to write DSR_INPUTS.json")
    ap.add_argument("--window-days", type=int, default=dsr_inputs.WINDOW_DAYS)
    a = ap.parse_args(argv)
    try:
        doc = dsr_inputs.run(report_path=a.report, ledger_path=a.ledger, out=a.out,
                             window_days=a.window_days)
    except OSError as exc:
        print(f"dsr_inputs: could not write: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    pooled = doc["variance"]["pooled"]
    eff = doc["effective_trials"]
    print(json.dumps({"status": doc["status"], "why": doc.get("why"),
                      "pooled_variance": pooled["variance"], "n": pooled["n"],
                      "effective_trials": eff["effective"], "nominal_trials": eff["nominal"],
                      "harvest": doc["provenance"]["harvest"].get("appended"),
                      "content_sha256": doc["content_sha256"][:16]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
