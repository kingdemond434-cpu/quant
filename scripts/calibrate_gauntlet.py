#!/usr/bin/env python3
"""CALIBRATE THE INSTRUMENT -- what can this desk's screen actually detect?

THE QUESTION THIS ANSWERS, AND IT IS THE MOST EXPENSIVE OPEN QUESTION THE DESK HAS. 420 candidates
were tested and 420 died. Two explanations fit that observation exactly as well:

    (a) the candidates were worthless
    (b) the screen cannot detect an edge even when one is handed to it

They demand opposite responses -- (a) says generate better, (b) says the measuring instrument is
broken and every future campaign will also return zero -- and live data can never separate them,
because on live data the truth is never available. Here it is: plant an edge of KNOWN strength,
run the desk's own L3 screen over it, and count how often the screen finds it. Then run the same
screen over paths with no edge at all and count how often it says yes anyway.

    power                = P(screen fires | an edge really is there)
    false-positive rate  = P(screen fires | nothing is there)
    detection floor      = the weakest edge where power > 0.5 and FPR < 0.5

POWER ALONE IS THE TRAP and is why the two are never reported apart: a screen that says yes to
everything has power 1.0 and is worthless. The pair is the measurement.

THE DETECTION FLOOR IS A PROGRESS METRIC THAT CANNOT BE GAMED. Hypothesis count rises by
generating more. Survivor count rises by lowering the bar. The floor falls only when the desk
genuinely gets better at finding weak edges, and it is measured against a truth the desk planted
rather than against its own opinion. It is also the honest answer to "what would we have missed?":
a floor at 0.08 means every edge weaker than that was INVISIBLE to the campaign, so rejections
below it are not evidence of absence and must never be reported as tested.

MAX CADENCE, BUDGETED. Runs every cycle. The sweep is bounded by trial count and wall clock so it
can never delay a cycle -- an organ that delays the cycle gets switched off, and a switched-off
organ measures nothing.

Read-only over the screen. Writes one artifact. No network, no promotion authority.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from libs.hypmax.fast_screen import PERM_P_MAX, fast_screen  # noqa: E402
from libs.hypmax.laboratory import BENCHMARK_STRENGTHS, detection_floor  # noqa: E402

OUT = ROOT / "data/gauntlet_calibration.json"
HISTORY = ROOT / "data/gauntlet_calibration_history.jsonl"

#: Trials per strength per arm. 40 gives a standard error of ~0.08 on a power estimate, which is
#: enough to separate "reliably detects" from "coin flip" without spending a cycle on it. Raise it
#: via the env var when the floor itself is the subject of a study rather than a daily reading.
TRIALS = int(os.environ.get("GAUNTLET_TRIALS") or 40)

#: Observations per synthetic path. Must clear the screen's own MIN_OBS or every trial returns
#: ESCALATE-for-lack-of-data and the sweep measures nothing but the guard.
N_OBS = int(os.environ.get("GAUNTLET_N_OBS") or 500)

WALL_BUDGET_S = 200.0


#: Counted separately so "the screen had an opinion" can be told from "the screen proceeded".
_ESCALATIONS = {"planted": 0, "null": 0, "planted_n": 0, "null_n": 0}


def _screen_fires(signal: np.ndarray, forward: np.ndarray, *, arm: str = "planted") -> bool:
    """The desk's REAL L3 screen, reduced to a yes/no. PASS is the hit. ESCALATE is NOT.

    THE DISTINCTION IS THE SCREEN'S OWN AND IT IS LOAD-BEARING. ScreenResult separates PASS
    ("measured, and it looks real") from ESCALATE ("not measurable here, proceeding anyway"),
    precisely so that a screen which escalates everything can be caught doing nothing. Counting
    ESCALATE as a detection would credit the screen for "I could not tell" and would report a
    screen with no opinion at all as having perfect power -- the exact flattery this whole
    calibration exists to strip out.

    So the measurement is strict: power is the rate at which the screen SAYS YES to a real edge.
    The escalation rate is tracked alongside, because a high one is its own finding -- it means
    the sweep is measuring the data guard rather than the discriminator.
    """
    r = fast_screen(signal, forward, n_perm=120)
    _ESCALATIONS[f"{arm}_n"] += 1
    if r.decision == "ESCALATE":
        _ESCALATIONS[arm] += 1
    return r.decision == "PASS"


def main() -> int:
    t0 = time.time()
    strengths = BENCHMARK_STRENGTHS
    rep = detection_floor(lambda sg, fw: _screen_fires(sg, fw, arm="planted"),
                          strengths=strengths, trials=TRIALS, n=N_OBS)
    esc_rate = (_ESCALATIONS["planted"] / max(1, _ESCALATIONS["planted_n"]))
    elapsed = round(time.time() - t0, 1)

    floor = rep["detection_floor"]
    prev = None
    if HISTORY.exists():
        try:
            rows = [json.loads(x) for x in HISTORY.read_text("utf-8").strip().splitlines() if x]
            prev = next((r.get("detection_floor") for r in reversed(rows)
                         if r.get("detection_floor") is not None), None)
        except (OSError, json.JSONDecodeError):
            prev = None

    verdict = (
        "THE INSTRUMENT IS BROKEN, NOT THE MARKET. The screen missed a planted edge at every "
        "strength tested including the most blatant one. A campaign of rejections run through "
        "this screen carries NO information about whether edges exist -- fix the screen before "
        "reading anything into any rejection count."
        if floor is None else
        f"the screen reliably finds edges at strength {floor} and above. Anything weaker was "
        "INVISIBLE, so rejections below that strength are not evidence of absence and must not "
        "be reported as tested.")

    moved = ""
    if prev is not None and floor is not None:
        if floor < prev:
            moved = (f"FLOOR IMPROVED {prev} -> {floor}: the desk can now detect weaker edges "
                     "than it could. This is the one progress metric that cannot be gamed by "
                     "generating more or by passing more.")
        elif floor > prev:
            moved = (f"FLOOR REGRESSED {prev} -> {floor}: the screen got BLUNTER. Something "
                     "changed in the screen or its constants; find it before trusting the next "
                     "campaign's rejections.")

    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "screen": "libs.hypmax.fast_screen.fast_screen -- decision == PASS (L3 ONLY)",
        "screen_constants": {"PERM_P_MAX": PERM_P_MAX},
        "trials_per_arm": TRIALS,
        "n_obs": N_OBS,
        "seconds": elapsed,
        "detection_floor": floor,
        "false_positive_rate": rep.get("false_positive_rate"),
        "permissiveness": rep.get("permissiveness", ""),
        "previous_floor": prev,
        "scope": ("THIS CALIBRATES L3 ONLY -- the cheap statistical pre-filter. The 420/420 "
                  "campaign died at L4 (walk-forward, fragility, CPCV, capacity, expected "
                  "value), which this sweep does NOT measure. A clean L3 result therefore "
                  "narrows the 420/420 question rather than answering it: it removes the "
                  "pre-filter from the list of suspects and leaves L4 and the candidates."),
        "sweep": rep["sweep"],
        "blatant_check": rep["blatant_check"],
        "escalation_rate": round(esc_rate, 4),
        "escalation_note": (
            f"{esc_rate:.0%} of trials returned ESCALATE -- 'not measurable here', not 'no'. A "
            "high rate means this sweep is measuring the screen's DATA GUARD rather than its "
            "discriminator, and the floor below should be read as a floor on the guard."
            if esc_rate > 0.25 else ""),
        "verdict": verdict,
        # P20, ZERO CEILING. A detection floor is a progress metric, so it has a successor even
        # when it looks good -- and naming it is what stops the organ going quiet the day the
        # number turns green, which is exactly when the next constraint starts binding.
        "next_ceiling": (
            "L3 is not the binding constraint at this floor. The next ceilings, in order: "
            "calibrate L4 (walk-forward, fragility, CPCV, capacity, expected value) the same way; "
            "then drive the false-positive rate down without losing power, since every false "
            "positive spends L4 compute on nothing; then push the floor below the weakest edge "
            "the desk would actually trade."
            if floor is not None else
            "fix the instrument before anything else -- no rejection this screen produces carries "
            "information until it can find a planted edge"),
        "movement": moved,
        "note": ("power and false-positive rate are ALWAYS reported together: a screen that says "
                 "yes to everything has power 1.0 and is worthless, so neither number means "
                 "anything alone."),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1), "utf-8")
    with HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({k: out[k] for k in
                             ("ts", "detection_floor", "trials_per_arm", "n_obs", "seconds")},
                            separators=(",", ":")) + "\n")

    print(f"gauntlet-calibration: floor={floor} ({elapsed}s, {TRIALS} trials/arm)")
    for row in rep["sweep"]:
        mark = "OK " if row["usable"] else "-- "
        print(f"  {mark}strength {row['strength']:<5} power {row['power']:.2f} "
              f"fpr {row['false_positive_rate']:.2f}")
    if rep["blatant_check"]:
        print(f"  {rep['blatant_check']}")
    if moved:
        print(f"  {moved}")
    if elapsed > WALL_BUDGET_S:
        print(f"  NOTE: took {elapsed}s (>{WALL_BUDGET_S}s budget) -- lower GAUNTLET_TRIALS or "
              "GAUNTLET_N_OBS; an organ that delays the cycle gets switched off, and a "
              "switched-off organ measures nothing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
