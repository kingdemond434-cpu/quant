#!/usr/bin/env python3
"""CONVERSION FENCE (L1.28b) -- finding without fixing is half a deliverable.

THE MEASURED DEFECT THIS FENCE EXISTS FOR (deep sweep 2026-07-31, meta seat): findings arrive
at ~14/day across all organs and cross-session repairs complete at ~0.6/day; no ledger row older
than 3.67 days had ever been implemented; >=80% of audit output converted to nothing. The desk's
BUILD capability compounds while its CONVERT capability does not, and nothing measured that gap
daily -- so it widened silently, exactly like unmeasured utilisation before L1.28a.

WHAT IT MEASURES, from docs/research/recommendation_ledger.json (the de-facto winning queue --
the sweep's M10 finding is that split stores recreate the defect, so this fence reads ONE store):
  backlog            rows still open or scheduled
  past_due           backlog rows whose due date has passed
  dispositions_7d    rows moved to implemented/rejected in the last 7 days (a reasoned
                     rejection IS a conversion -- the defect is silence, not the verdict)
  arrivals_7d        rows raised in the last 7 days
  oldest_backlog_age the age of the oldest still-open row, in days
  queue_dispositioned all-time fraction of rows that reached a terminal verdict

STATUSES (fail LOUD, never advisory):
  FLATLINE     zero dispositions in 7 days while the backlog is non-empty -- found-never-fixed
               as a steady state. Exit 2: this is the fence failure.
  REPAIR-MODE  backlog above the deep-sweep backpressure line (25). Exit 0 but the artifact
               carries repair_mode=true, and every consumer of the artifact (max-push queue,
               sweep prompts, brain briefs) is expected to flip effort from finding to fixing.
               Queueing theory (meta M8): at rho~4, exhortation cannot drain a queue -- only
               capacity or admission control can, and this flag is the admission signal.
               BOUNDARY (L1.28b(f), principal 2026-07-31): repair-mode redirects DISCRETIONARY
               ENGINEERING ATTENTION ONLY. It never reduces raw information quantity --
               collectors, recorders, miners, diggers, screens-on-discovery, forward clocks and
               every scheduled detector run at full cadence unconditionally. Acquisition is
               never cut to meet extraction.
  DEBT-GROWING materially more rows arrived than were dispositioned over the last 7 days (a
               shortfall of >=5 AND a conversion ratio <0.75), with a non-empty backlog. Both
               numbers were computed and printed here from the start and never compared, so a
               desk raising 40 a week and dispositioning 3 read OK for as long as the backlog
               stayed under the REPAIR-MODE line -- falling further behind every week with the
               evidence sitting unread in its own artifact. The required move is CONVERT FASTER,
               never raise less.
               RANKS BELOW REPAIR-MODE as a headline, because the two prescribe the same action
               and REPAIR-MODE is the signal downstream consumers already read; this status
               covers what REPAIR-MODE cannot see, a backlog under the line that is still
               growing. But `debt_growing` is recorded as a FACT and fails the fence (exit 2)
               whichever status won -- a desk over the line AND falling further behind must not
               exit 0 because the more urgent-sounding label got there first.
  ARRIVALS-COLLAPSED
               7-day arrivals fell below 40% of the trailing 28-day rate. Exit 2, and it outranks
               every green status below it. This is the ANTI-GAMING status: every other reading
               here improves when arrivals fall, so the cheapest route to a clean conversion
               score is to stop looking -- and that would be indistinguishable from success. It
               is reported even when everything else is green, because that is exactly when it is
               invisible. L1.28b(f) forbade this in prose ("acquisition is never cut to meet
               extraction") and nothing measured it until now. The required move is FIND HARDER.
               Named separately from DEBT-GROWING on purpose: convert-faster and find-harder are
               opposite instructions, and one number holding both would let each mask the other.
  OK           dispositions keeping pace with arrivals, arrivals holding up, backlog under the
               line. All three, or it is not OK.

Artifact: data/conversion_status.json -- consumed by run_max_push.py so conversion debt ranks
in the SAME daily queue as every other below-ceiling aspect (L1.28b: conversion hunts 100%
daily exactly as utilisation does).

    python scripts/check_conversion.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent

# L1.42 LAWFUL ENTRY: this organ ran on a cron line that passed through no gate at
# all -- 60 manifest lines did. guard() verifies the sealed core and that the doctrine
# still carries every law family; it is TTL-cached (~0ms after the first call in a
# window) and pages-but-does-not-block, so a governance fault never silences an organ.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.fence_exit import FAIL, fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.ops.repair_mode import DIRECTION_FOR_STATUS  # noqa: E402  (L1.28b(d): one mapping)

#: REPAIR-MODE passes DELIBERATELY. It is not a failure but a designed MODE SIGNAL: L1.28b(d)
#: has it flip the next audit/brain window from finding to fixing, and run_max_push reads the
#: artifact to do exactly that. Failing the build on it would make the desk permanently red at
#: today's backlog and get the fence switched off (L1.43) -- turning the fix into the outage.
#: FLATLINE (dispositions stopped entirely) stays the failure, and any status added later fails.
_PASSING = frozenset({"OK", "REPAIR-MODE"})

# The deep-sweep backpressure line: open+past-due above this flips audit windows to repair.
REPAIR_MODE_BACKLOG = 25

#: A week's arrivals below this fraction of the trailing baseline is a COLLAPSE, not a quiet week.
#: 0.4 is deliberately generous -- real finding rates are lumpy (a deep sweep raises twenty rows
#: in an afternoon, the next week raises four), and a fence that fires on ordinary variance gets
#: disabled, taking the real signal with it. What it must catch is the SUSTAINED quiet that means
#: the desk stopped looking, which is the only way a conversion ratio can be gamed.
ARRIVAL_COLLAPSE_FRACTION = 0.4
#: Rows needed in the trailing 28d before a baseline means anything. Below it the comparison is
#: reported UNMEASURED rather than computed -- a collapse detector built on three rows would fire
#: on noise, and a detector that cries wolf is a detector nobody keeps.
ARRIVAL_BASELINE_MIN = 8

#: DEBT-GROWING needs BOTH a material shortfall and a materially poor rate. Either alone
#: cries wolf: one row raised and not yet dispositioned is a desk keeping pace, not a desk losing
#: ground, and a fence that fires on that gets switched off before it ever sees a real slide.
#: Calibrated against the live ledger, where the slide is unambiguous -- 341 raised vs 157
#: dispositioned in 7 days, a 184-row shortfall at a 0.46 conversion ratio.
DEBT_GROWTH_MIN_ROWS = 5
DEBT_GROWTH_MIN_RATIO = 0.75

#: The statuses this fence NAMES as failures. It is no longer the exit map -- ``_PASSING`` is,
#: and it fails closed on everything it does not name, which is the property that survives a
#: status added next year (R0237). This set is kept as the explicit record of the three the
#: author meant, and ``tests/governance/test_conversion_fence.py`` asserts it stays disjoint from
#: ``_PASSING``: widening the pass set is a legitimate edit, silently un-failing DEBT-GROWING
#: while doing it is not.
_FENCE_FAILURES = frozenset({"FLATLINE", "DEBT-GROWING", "ARRIVALS-COLLAPSED"})
# `done` and `screened` are written by organs that bypass the CLI (scripts/recommendations.py:223
# only permits implemented|rejected|scheduled). They read "built, N tests, in the law gate" and
# "Stage A run live" -- FINISHED WORK. Omitting them counted 15 completed rows as backlog forever
# AND, because they carry no `disposed` stamp, never as dispositions: a double penalty that
# inflated the apparent debt at both ends. Counting them is a correctness fix, NOT the denominator
# trick -- no row leaves the ledger, and `terminal_unstamped` below reports exactly how many are
# terminal without a timestamp so the disposition RATE understatement stays visible.
_TERMINAL = frozenset({"implemented", "rejected", "retired", "done", "screened"})
# scripts/recommendations.py:37 -- an untriaged row past this is a DEFECT, not backlog.
GRACE_H = 24.0


def _parse_ts(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        ts = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def build_report(root: Path, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    week_ago = now - timedelta(days=7)
    ledger = root / "docs/research/recommendation_ledger.json"
    try:
        rows = json.loads(ledger.read_text("utf-8")).get("recommendations", [])
    except (OSError, ValueError):
        rows = None

    if not rows:
        # A missing/empty ledger is UNMEASURED conversion, which counts as zero (L1.28a
        # inheritance) -- never as OK.
        return {
            "generated": now.isoformat(), "status": "FLATLINE", "repair_mode": True,
            "law": "L1.28b", "backlog": None, "past_due": None,
            "detail": f"ledger unreadable or empty at {ledger} -- unmeasured conversion "
                      "counts as ZERO conversion",
        }

    backlog = [r for r in rows if r.get("status") not in _TERMINAL]
    # PAST DUE, counted the way scripts/recommendations.py counts it. Two bugs lived here and both
    # ran in the FORGIVING direction, which is how the fence reported past_due=0 while
    # recommendations.py reported 34 DEFECTS on the same file in the same minute -- and
    # run_max_push.py:239 consumes THIS artifact, so the desk prioritised off the lenient number.
    #   (1) `r["due"] < today` compared ISO STRINGS, so "2026-08-01" < "2026-08-01" is False and a
    #       scheduled row was invisible for the entire day it came due (6 rows today).
    #   (2) it required a non-null `due`, but add() writes `due: None` and only `dispose
    #       --status scheduled` ever sets one -- so ZERO rows in the ledger have status `open` AND
    #       a due date. That branch was structurally dead in production, hiding every untriaged
    #       row. The unit test that "proved" it worked used an open row WITH a due date, a fixture
    #       the CLI cannot produce.
    overdue = [r for r in backlog
               if (d := _parse_ts(r.get("due"))) is not None and d < now]
    orphans = [r for r in backlog
               if r.get("status") == "open"
               and (t := _parse_ts(r.get("raised"))) is not None
               and (now - t).total_seconds() / 3600.0 > GRACE_H]
    seen: set[int] = set()
    past_due = [r for r in (*overdue, *orphans)
                if id(r) not in seen and not seen.add(id(r))]  # type: ignore[func-returns-value]
    terminal_unstamped = sum(1 for r in rows
                             if r.get("status") in _TERMINAL and not r.get("disposed"))
    arrivals_7d = sum(1 for r in rows if (t := _parse_ts(r.get("raised"))) and t >= week_ago)
    dispositions_7d = sum(
        1 for r in rows
        if r.get("status") in _TERMINAL
        and (t := _parse_ts(r.get("disposed"))) and t >= week_ago)
    terminal = sum(1 for r in rows if r.get("status") in _TERMINAL)
    oldest = min((_parse_ts(r.get("raised")) for r in backlog if _parse_ts(r.get("raised"))),
                 default=None)
    oldest_age = round((now - oldest).total_seconds() / 86400, 2) if oldest else 0.0

    # CONVERSION MUST CATCH UP TO ARRIVALS, AND MUST NEVER CATCH UP BY REDUCING THEM.
    #
    # Both numbers below were already computed, already printed in the artifact, and NEVER
    # COMPARED. Status asked only "is anything moving at all" (FLATLINE) and "is the pile big"
    # (REPAIR-MODE), so a desk raising 40 rows a week and dispositioning 3 read OK for as long as
    # the backlog stayed under the line -- falling 37 rows further behind every week, with the
    # evidence of it sitting unread in its own artifact. Measured-but-unread, again.
    #
    # AND THE SECOND HALF IS THE ONE THAT MATTERS MORE, because it is the direction a desk drifts
    # in without ever deciding to. Every status here improves when ARRIVALS FALL. Stop finding
    # things and the backlog shrinks, dispositions keep pace trivially, and the fence goes green
    # -- so the cheapest route to a clean conversion score is to look less hard. That is the
    # opposite of what the fence is for, and it would be indistinguishable from success.
    #
    # L1.28b(f) already forbids it in prose ("acquisition is never cut to meet extraction") and
    # nothing measured it. So arrivals are now compared against their own trailing baseline, and
    # a COLLAPSE is a defect in its own right -- reported even when everything else is green,
    # because that is exactly when it is invisible.
    #
    # The two failures are named separately on purpose: DEBT-GROWING means convert faster, and
    # ARRIVALS-COLLAPSED means find harder. Merging them into one "conversion" number would let
    # each mask the other, which is precisely how the ratio became gameable.
    prior_start, prior_end = now - timedelta(days=35), now - timedelta(days=7)
    arrivals_prior_28d = sum(
        1 for r in rows
        if (t := _parse_ts(r.get("raised"))) and prior_start <= t < prior_end)
    baseline_7d = arrivals_prior_28d / 4.0          # prior 28 days expressed as a weekly rate
    # Only meaningful once the baseline itself has enough mass; below that, say so rather than
    # inventing a comparison out of three rows.
    baseline_measurable = arrivals_prior_28d >= ARRIVAL_BASELINE_MIN
    arrivals_collapsed = (baseline_measurable
                          and arrivals_7d < ARRIVAL_COLLAPSE_FRACTION * baseline_7d)
    debt_growth_7d = arrivals_7d - dispositions_7d
    debt_growing = bool(
        backlog
        and debt_growth_7d >= DEBT_GROWTH_MIN_ROWS
        and arrivals_7d
        and dispositions_7d / arrivals_7d < DEBT_GROWTH_MIN_RATIO)

    # PRECEDENCE, and REPAIR-MODE deliberately outranks DEBT-GROWING. The two prescribe the same
    # action (convert more), but REPAIR-MODE is the already-wired admission signal that the
    # max-push queue, sweep prompts and brain briefs read, and demoting it would change behaviour
    # those consumers depend on for a headline that says the same thing. DEBT-GROWING exists to
    # cover what REPAIR-MODE cannot see: a backlog UNDER the line that is nevertheless growing --
    # the exact hole in the original logic, where a desk raising 40 a week and dispositioning 3
    # read OK indefinitely.
    #
    # But `debt_growing` is a FACT, not a headline, so it is recorded and it fails the fence
    # whichever status won. A desk that is over the line AND falling further behind must not exit
    # 0 merely because the more urgent-sounding label got there first.
    if dispositions_7d == 0 and backlog:
        status = "FLATLINE"
    elif arrivals_collapsed:
        status = "ARRIVALS-COLLAPSED"
    elif len(backlog) > REPAIR_MODE_BACKLOG:
        status = "REPAIR-MODE"
    elif debt_growing:
        status = "DEBT-GROWING"
    else:
        status = "OK"
    # THE DIRECTION IS NOT THE STATUS, AND CONFLATING THEM INVERTED THE REMEDY (2026-08-05).
    # `repair_mode` was `status != "OK"`, so it read TRUE for ARRIVALS-COLLAPSED -- and its
    # documented meaning, in L1.28b(d) and in run_max_push's own action string, is "flip the next
    # audit/brain window from FINDING to FIXING". That is precisely backwards for a status whose
    # entire content is that the desk is finding too little; line 215 of this file already said so
    # ("ARRIVALS-COLLAPSED means find harder") 42 lines above the code that contradicted it. The
    # flag was inert at the time -- its only consumer selected an advice string -- so the inversion
    # cost nothing until libs/ops/repair_mode.py gave it an actuator, which is exactly when a
    # latent inversion becomes an automated L1.25a fatigue-by-null defect.
    #
    # The mapping lives in ONE place (libs.ops.repair_mode.DIRECTION_FOR_STATUS) because a second
    # derivation of it is the bug. An unrecognised status maps to UNMEASURED, which OWES work.
    direction = DIRECTION_FOR_STATUS.get(status, "UNMEASURED")
    return {
        "generated": now.isoformat(), "status": status,
        # DRAIN / FIND-HARDER / STEADY / UNMEASURED -- what the next brain window should DO.
        "direction": direction,
        # Kept, and now meaning exactly what it says: this window owes the QUEUE its time.
        # ARRIVALS-COLLAPSED deliberately does NOT set it; that state owes the HUNT its time.
        "repair_mode": direction == "DRAIN",
        "law": "L1.28b -- conversion hunts 100% daily; a found-unfixed defect is unbooked "
               "loss aging at its stated ROI",
        "backlog": len(backlog), "past_due": len(past_due),
        "past_due_ids": [r.get("id") for r in past_due][:20],
        "past_due_overdue": len(overdue), "past_due_orphaned": len(orphans),
        "terminal_unstamped": terminal_unstamped,
        "arrivals_7d": arrivals_7d, "dispositions_7d": dispositions_7d,
        "arrival_rate_per_day": round(arrivals_7d / 7, 3),
        "disposition_rate_per_day": round(dispositions_7d / 7, 3),
        # The comparison the fence used to leave to the reader. Positive = the desk fell further
        # behind this week; conversion owes the difference, and the debt compounds at the ROI
        # each unconverted row states.
        "debt_growth_7d": debt_growth_7d,
        "debt_growing": debt_growing,
        "conversion_ratio_7d": (round(dispositions_7d / arrivals_7d, 3)
                                if arrivals_7d else None),
        # The anti-gaming half. A ratio can always be improved by shrinking its denominator, so
        # the denominator is watched on its own terms and against its own history.
        "arrivals_prior_28d": arrivals_prior_28d,
        "arrivals_baseline_7d": round(baseline_7d, 2) if baseline_measurable else None,
        "arrivals_collapsed": arrivals_collapsed,
        "arrivals_baseline_status": ("MEASURED" if baseline_measurable else
                                     f"UNMEASURED -- only {arrivals_prior_28d} row(s) in the "
                                     f"prior 28d, need {ARRIVAL_BASELINE_MIN} before a collapse "
                                     "can be distinguished from a quiet month"),
        "anti_gaming_note": ("conversion_ratio_7d must NEVER be raised by finding less. "
                             "L1.28b(f): acquisition is never cut to meet extraction, and "
                             "ARRIVALS-COLLAPSED outranks every green status below it."),
        "oldest_backlog_age_days": oldest_age,
        "queue_dispositioned": round(terminal / max(len(rows), 1), 4),
        "repair_mode_line": REPAIR_MODE_BACKLOG,
        "detail": f"{len(backlog)} rows in backlog ({len(past_due)} past due, oldest "
                  f"{oldest_age}d); last 7d: {arrivals_7d} raised vs {dispositions_7d} "
                  f"dispositioned",
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true",
                    help="write the artifact and always exit 0 (for queue refresh)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report(_ROOT)
    out = _ROOT / "data/conversion_status.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"conversion fence (L1.28b): {rep['status']} -- {rep.get('detail', '')}")
        print(f"-> {out}")
    if args.report_only:
        return 0
    # UNION OF TWO CONCURRENT FIXES TO THIS LINE, and both teeth are kept.
    #
    # (1) fence_exit(_PASSING) is the fail-CLOSED status map (R0237). It strictly subsumes the
    #     enumerate-the-failures form it replaced: FLATLINE, DEBT-GROWING and ARRIVALS-COLLAPSED
    #     are all outside _PASSING already, and so is a status added next year by someone who
    #     never reads this module. Enumerating passes is a list that cannot rot.
    #
    # (2) `debt_growing` is a BOOLEAN carried BESIDE the status, not a status, so no status map
    #     of any shape can see it. It stays an independent trigger, because conversion losing
    #     ground is the fence's own subject matter -- exit 0 there would report the failure this
    #     fence exists to catch in the same breath as success.
    if rep.get("debt_growing"):
        return FAIL
    return fence_exit(rep["status"], _PASSING)


if __name__ == "__main__":
    sys.exit(main())
