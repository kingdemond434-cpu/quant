#!/usr/bin/env python3
"""CALIBRATION FENCE (L1.29) -- the desk scores its own confidence, or its confidence is fiction.

WHY THIS IS A SURVIVAL ORGAN, not a nicety. Every Kelly bet, every promotion decision, every EV
ranking rests on a probability the desk assigned -- an alpha's survival odds, a task's success
odds, an audit's confidence. If those probabilities are systematically too high (over-confidence),
the desk over-bets EVERY position and over-promotes EVERY candidate, and the error is invisible
because each individual call looks reasonable. A Kelly bettor sized on over-confident estimates
converges to ruin with probability one. The only defense is to SCORE the forecasts against
outcomes and feed the measured bias back as a shrinkage -- which is what libs.self_improvement.
forecast_calibration now computes AND applies (calibrated_confidence), and what this fence hunts.

WHAT IT MEASURES (from data/forecast_log.json):
  OVERDUE       forecasts past their resolve_by, still unresolved -- the desk made a prediction
                and then refused to grade it. This is the primary fence FAILURE (exit 2): a
                belief the desk won't score is not a forecast, and it silently inflates the
                apparent hit-rate by never counting the misses.
  MISCALIBRATED enough resolved outcomes and |bias| material -- reported, ratcheted, queued.
                Not a hard fail (the fix is more resolved outcomes, not a code change), but the
                bias is now CONSUMED by calibrated_confidence so the desk self-corrects.
  BLIND         forecasts logged but almost none resolved -- a scorer with no inputs. Reported
                so a write-only calibration store cannot masquerade as calibration.

Feeds data/calibration_status.json -> run_max_push.py, so miscalibration ranks in the daily
hunt as its own aspect.

    python scripts/check_calibration.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# L1.42 LAWFUL ENTRY: this organ ran on a cron line that passed through no gate at
# all -- 60 manifest lines did. guard() verifies the sealed core and that the doctrine
# still carries every law family; it is TTL-cached (~0ms after the first call in a
# window) and pages-but-does-not-block, so a governance fault never silences an organ.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.self_improvement import forecast_calibration as fc  # noqa: E402


def build_report() -> dict[str, object]:
    rep = fc.report()
    od = fc.overdue()
    n_resolved = int(rep.get("n_resolved", 0) or 0)
    total = len(fc._load()["forecasts"])
    if total == 0:
        # NOT "OK". A desk with zero logged forecasts is not well-calibrated, it is
        # UNFORECASTING -- and under L1.28a unmeasured counts as zero, never as fine. This
        # fence caught it on its own first run, which is the behaviour it exists to enforce.
        status = "UNFORECASTING"
    elif od:
        status = "OVERDUE"
    elif total >= 5 and n_resolved < max(1, total // 4):
        status = "BLIND"                                   # logged a lot, scored almost none
    elif rep.get("bias_label") in ("over-confident", "under-confident"):
        status = "MISCALIBRATED"
    else:
        status = "OK"
    return {
        "status": status,
        "n_forecasts": total,
        "n_resolved": n_resolved,
        "n_overdue": len(od),
        "overdue": od[:15],
        "brier": rep.get("brier"),
        "reliability": rep.get("reliability"),
        "bias": rep.get("bias"),
        "bias_label": rep.get("bias_label"),
        "calibration_status": rep.get("status"),
        "detail": ("NO forecasts logged at all -- the desk asserts probabilities (alpha "
                   "survival, task success, audit confidence) without recording any of them, "
                   "so none can ever be scored. Log them at the decision points."
                   if total == 0 else
                   f"{len(od)} forecast(s) past their grading deadline -- score them"
                   if od else
                   f"{n_resolved}/{total} resolved; " + str(rep.get("status"))),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / "data/calibration_status.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"calibration fence (L1.29): {rep['status']} -- {rep['detail']}")
        print(f"-> {out}")
    if args.report_only:
        return 0
    return 2 if rep["status"] == "OVERDUE" else 0


if __name__ == "__main__":
    sys.exit(main())
