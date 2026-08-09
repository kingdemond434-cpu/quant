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
from datetime import UTC, datetime
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
from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

#: OVERDUE was the only status that failed, so BLIND (logged a lot, scored almost none),
#: MISCALIBRATED (the measured bias this fence exists to surface) and UNFORECASTING (zero
#: forecasts -- the state the file's own comment calls 'NOT "OK"') all exited 0. A desk whose
#: confidence is measurably wrong reported green to CI while over-sizing every Kelly bet (L1.29).
_PASSING = frozenset({"OK"})
from libs.self_improvement import forecast_calibration as fc  # noqa: E402


def build_report() -> dict[str, object]:
    rep = fc.report()
    od = fc.overdue()
    try:
        from scripts.score_forecasts import auto_resolvable
    except Exception:                                      # broad: never lose the fence to an import
        auto_resolvable = None                             # type: ignore[assignment]
    unowned = fc.unowned(auto_resolvable, root=_ROOT)
    n_resolved = int(rep.get("n_resolved", 0) or 0)
    store = fc._load()["forecasts"]
    total = len(store)
    # THE DENOMINATOR THIS FENCE WAS DIVIDING BY WAS THE WRONG POPULATION (L1.57, R0260).
    # `n_resolved` is drawn from the SCOREABLE population -- rows with a resolve_by, of a sizing
    # kind, one per distinct claim. `total` was the raw store. Measured 2026-08-05: 42 against
    # 172, of which 43 rows can never enter the numerator by construction, so `42 < 172//4 = 43`
    # fired BLIND and exited 2; against the matched population it is `42 < 129//4 = 32`, which
    # does not fire. The desk's #1 max_push item was pinned by a category error, and the error ran
    # the wrong way twice over: every exclusion lowers the numerator AND raises the denominator,
    # so the hygiene that fixed the calibration SIGN INVERSION pushed this fence toward BLIND.
    n_eligible = int(rep.get("n_eligible", 0) or 0)
    if total == 0:
        # NOT "OK". A desk with zero logged forecasts is not well-calibrated, it is
        # UNFORECASTING -- and under L1.28a unmeasured counts as zero, never as fine. This
        # fence caught it on its own first run, which is the behaviour it exists to enforce.
        status = "UNFORECASTING"
    elif n_eligible == 0:
        # Rows exist but NONE can ever be scored -- a store made entirely of retrospective or
        # non-sizing rows. `n_resolved < n_eligible//4` is `0 < 0` there, which is False, so the
        # old shape would have read OK off a population of zero. A verdict over an empty
        # denominator is vacuous, never a pass (L1.57).
        status = "UNSCOREABLE"
    elif od:
        status = "OVERDUE"
    elif n_eligible >= 5 and n_resolved < max(1, n_eligible // 4):
        status = "BLIND"                                   # logged a lot, scored almost none
    elif rep.get("bias_label") in ("over-confident", "under-confident"):
        status = "MISCALIBRATED"
    else:
        status = "OK"
    return {
        # L1.44: a fence artifact without a content stamp cannot be age-checked -- mtime lies
        # fresh after every deploy. This fence shipped without one (capability hunt 2026-07-31).
        "generated": datetime.now(tz=UTC).isoformat(),
        "status": status,
        "n_forecasts": total,
        #: The population n_resolved is drawn from, published beside it so no future reader
        #: divides by n_forecasts again. n_eligible <= n_forecasts always.
        "n_eligible": n_eligible,
        "n_resolved": n_resolved,
        #: Raw resolved count. n_resolved is the DEDUPED, sizing-kind-only, pre-registered-only
        #: figure; publishing only that one made the artifact read "42/172 graded" when 81 rows
        #: carry an outcome. Two different questions, two fields.
        "n_resolved_raw": sum(1 for f in store.values() if f.get("resolved")),
        "n_overdue": len(od),
        "overdue": od[:15],
        #: Forecasts with a deadline and NO grader -- reported while grading is still possible.
        #: OVERDUE already fails once the date passes; by then there is no move left.
        "n_unowned": len(unowned),
        "unowned": unowned[:15],
        "unowned_next_due": unowned[0]["resolve_by"] if unowned else None,
        "brier": rep.get("brier"),
        "reliability": rep.get("reliability"),
        "bias": rep.get("bias"),
        "bias_label": rep.get("bias_label"),
        "calibration_status": rep.get("status"),
        "detail": ("NO forecasts logged at all -- the desk asserts probabilities (alpha "
                   "survival, task success, audit confidence) without recording any of them, "
                   "so none can ever be scored. Log them at the decision points."
                   if total == 0 else
                   f"{total} forecast(s) logged and NOT ONE is scoreable -- every row is "
                   "retrospective or of a non-sizing kind, so the calibration number would be "
                   "computed over an empty population"
                   if n_eligible == 0 else
                   f"{len(od)} forecast(s) past their grading deadline -- score them"
                   + (f"; {sum(1 for u in unowned for o in od if o['key'] == u['key'])} of them "
                      "have NO grader (see unowned) and cannot be cleared by any organ"
                      if unowned else "")
                   if od else
                   f"{n_resolved}/{n_eligible} scoreable resolved; " + str(rep.get("status"))
                   + (f"; {len(unowned)} forecast(s) have a deadline and no grader, next due "
                      f"{unowned[0]['resolve_by'][:10]}" if unowned else "")),
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
    return fence_exit(rep["status"], _PASSING)


if __name__ == "__main__":
    sys.exit(main())
