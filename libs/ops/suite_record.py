"""THE SUITE RECORD MUST RATCHET ON PASS/FAIL, NOT ONLY ON COLLECTION (R0543).

`docs/research/test_suite_record.json` held one number -- `max_collected`, the high-water mark of
COLLECTABLE test modules -- and COLLECTABLE is the operative word. A test that imports fine and
FAILS is still collected, so the ratchet cannot fall when the thing it exists to protect breaks.
That is the L1.57 constant-denominator class pointed at the test suite: a count that cannot move
in the one direction it exists to reveal.

NOT HYPOTHETICAL, AND THE PARTICULARS ARE THE ARGUMENT. Measured 2026-08-12: 13 tests in
tests/self_improvement/test_forecast_calibration.py had been RED since d13999b1 (2026-08-01) --
eleven days, verified pre-existing by running the same file in a clean-HEAD worktree. WHICH 13 IS
THE POINT: d13999b1 is "The calibration bias was INVERTED and inflating Kelly sizing on a live
sleeve". It taught `_scoreable` to exclude rows with no resolve_by; the fixture still logged bare
rows, so every row fell below the n>=5 gate and every test of THE SIGN CONVENTION THAT COMMIT
EXISTED TO FIX spent eleven days asserting against a report of Nones. A fix that silently retires
the tests pinning the behaviour it changed is the most expensive shape a green suite can hide.

THE ONLY DETECTOR WAS CI, AND A RED GATE HIDES NEW RED. The ci-gate-red ack of the day reasoned
"all 4 red tests shared one cause" -- measurably incomplete, since 13 more sat in a file that ack
never looked at. That is why acking a CI gate is different from acking anything else, and why this
instrument is deliberately NOT the CI gate: it is a second, cheap reader of a durable record, so a
newly-red file fails something even while the gate that would have caught it is acked.

TWO NUMBERS, TWO DIRECTIONS, AND THEY ARE NOT THE SAME KIND OF CLAIM:
  * ``n_failed`` has a floor of ZERO. Any red is a defect. No tolerance, no high-water.
  * ``n_passed`` RATCHETS UP. A fall is a defect for the same reason `test-suite-shrank` is: a
    suite loses coverage one quiet decision at a time while "tests pass" stays true the whole way
    down. A pass that legitimately becomes a skip is a decision, and it is recorded in the file --
    the same escape hatch `max_collected` already documents.

UNMEASURED IS A DEFECT, NEVER A CLEAN BILL (L1.28a). A record with no pass/fail block, or one too
old to speak for the current tree, means the suite's health is unknown -- which is exactly the
state this row was raised from, and it must not render as green.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RECORD_REL = "docs/research/test_suite_record.json"

#: Beyond this the record describes a tree that has moved on. Generous on purpose: the full suite
#: takes 60-80 minutes on this box, so it runs nightly at best, and a fence that demanded a
#: fresher number than the desk can produce would be red every day and get switched off (L1.43).
MAX_AGE_H = 48.0

#: HOW LONG RED IS ALLOWED TO BE BACKLOG BEFORE IT IS A DEFECT ROW (R0564). Derived, not chosen
#: for comfort: the full suite is 60-80 minutes and runs nightly at best, so a red that survives
#: THREE consecutive nightly runs is not an in-flight fix somebody is holding -- it is a gate the
#: desk has started carrying. That is the L1.43 welded-gate argument pointed at the test suite: a
#: check that has been failing long enough to be normal stops changing anybody's behaviour, which
#: is the state 13 red tests spent ELEVEN DAYS in while the collection ratchet read green.
RED_ENTRENCHED_DAYS = 3.0

#: pytest's terminal summary, `-q` or not: "5 failed, 700 passed, 2 errors in 100.00s". Parsed by
#: OUTCOME NAME rather than by position, because the set of outcomes present varies run to run and
#: a positional parse would silently read `xfailed` as `failed` the first time one appears.
_OUTCOME = re.compile(r"(\d+)\s+(passed|failed|error|errors|skipped|xfailed|xpassed)\b")

#: Outcomes that mean A TEST DID NOT PASS AND THAT IS NOT EXPECTED. `xfailed` is excluded because
#: it is a declared expectation; `xpassed` is excluded because it is a pass. `error` is INCLUDED
#: and that is load-bearing: a collection or fixture error is not a softer failure, it is a test
#: that never ran while the suite still reported a pass count beside it.
_RED = ("failed", "error", "errors")


#: Marks a run that REACHED ITS OWN END without printing counts. pytest emits the short-summary
#: header, the failures header and the progress percentage right up to the terminal line -- so
#: their presence separates "this run finished and its verbosity ate the number" from "this run
#: died". They are OPPOSITE repairs (fix the invocation vs re-run the suite) and a desk that
#: cannot tell them apart debugs the wrong organ (L1.55).
_COMPLETED_MARKERS = ("short test summary info", "=== FAILURES ===", "[100%]", "no tests ran")


def completed_without_counts(text: str) -> bool:
    """True when the output shows a finished run whose counts line was suppressed.

    THE -qq TRAP, MEASURED 2026-08-20 AND IT COST THIS RECORD ITS ENTIRE LIFE. pyproject's
    addopts is `-ra -q`; every desk invocation added its own `-q`, reaching pytest as `-qq`, which
    suppresses the terminal counts line outright. `run_ci.py` -- the record's only producer --
    did it on line 108, so `parse_summary` returned None on every run it ever made and the block
    was never written once. The same `-q` sits in /home/quant/run_suite_verdict.sh. Diagnosing
    that as "killed or hung" sends the operator to re-run an 80-minute suite that was never the
    problem.
    """
    return any(m in text for m in _COMPLETED_MARKERS)


def parse_summary(text: str) -> dict[str, int] | None:
    """Counts from a pytest run's output, or None when no summary line is present.

    None is not zero. A run that was killed, hung, or never started has NO summary, and returning
    zeros there would publish a perfect record for a suite that did not execute -- the fabricated
    -measurement class (L1.55). The caller must keep them apart.

    THE 15-LINE WINDOW IS NOT THE BUG AND WAS DELIBERATELY LEFT ALONE. It was the obvious suspect
    on the 2026-08-20 log -- a 100-line `-rf` short-summary block sits between the failures and
    the end -- but pytest prints the counts line LAST, after that block, so it lands inside any
    window at all. Widening it would only raise the odds of matching a stray "3 failed" inside a
    traceback. The actual cause was `completed_without_counts` above: there was no line to find.
    """
    tail = "\n".join(text.strip().splitlines()[-15:])
    found = _OUTCOME.findall(tail)
    if not found:
        return None
    counts: dict[str, int] = {}
    for n, name in found:
        key = "errors" if name == "error" else name
        counts[key] = counts.get(key, 0) + int(n)
    if "passed" not in counts and not any(k in counts for k in _RED):
        return None
    return {
        "n_passed": counts.get("passed", 0),
        "n_failed": sum(counts.get(k, 0) for k in _RED),
        "n_skipped": counts.get("skipped", 0),
    }


def read_file(path: Path) -> dict[str, Any]:
    """The record at an EXPLICIT path.

    Exposed beside `read(root)` so a caller that already owns the path -- max_audit holds it as
    TEST_RECORD -- reads through its own constant rather than re-deriving it from a root. Two ways
    to name one file is how a test that redirects the record finds only half of it redirected, and
    two sources of truth for one artifact is the class this desk keeps paying for.
    """
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def read(root: Path) -> dict[str, Any]:
    return read_file(root / RECORD_REL)


def record_run(root: Path, counts: dict[str, int], *, source: str,
               now: datetime | None = None) -> dict[str, Any]:
    """Merge one run's counts into the record and write it back. Returns the new pass_fail block.

    THE HIGH-WATER AND THE LAST READING ARE BOTH KEPT, and conflating them is how a ratchet
    becomes unreadable: `high_water_passed` is the bar, `n_passed` is what the last run actually
    got, and a fence needs both to say "it fell" rather than only "it is low". `max_collected` is
    left exactly as it was -- this is additive, and the collection ratchet keeps its own meaning.

    `red_since` IS THE AGE OF THE REDNESS, AND IT IS A DIFFERENT CLAIM FROM THE REDNESS (R0564).
    A single number cannot say whether a failing suite is an in-flight fix or a gate the desk has
    been carrying for a week and a half, and only the second one is a defect row. It is carried
    forward across runs that stay red and CLEARED by any green run -- one green resets the clock,
    because the question is how long the CURRENT redness has stood.

    AN UNRECORDED PRIOR RED STARTS THE CLOCK NOW rather than inventing a start date. A block
    written before this field existed, or one whose stamp is unparseable, knows the suite was red
    and not for how long; back-dating it to the block's own `at` would be a measurement nobody
    took (L1.28a). The cost is that the first entrenched red is reported up to three days late,
    once, and that is strictly better than a fabricated duration nobody can check.
    """
    stamp = (now or datetime.now(tz=UTC)).isoformat()
    rec = read(root)
    raw = rec.get("pass_fail")
    prior: dict[str, Any] = raw if isinstance(raw, dict) else {}
    high = max(int(prior.get("high_water_passed", 0)), int(counts["n_passed"]))
    was_red = int(prior.get("n_failed", 0)) > 0
    prior_red_since = str(prior.get("red_since") or "") if was_red else ""
    red_since = (prior_red_since or stamp) if int(counts["n_failed"]) > 0 else ""
    block = {
        "n_passed": int(counts["n_passed"]),
        "n_failed": int(counts["n_failed"]),
        "n_skipped": int(counts.get("n_skipped", 0)),
        "high_water_passed": high,
        "at": stamp,
        "red_since": red_since,
        "source": source,
        "note": "n_failed has a floor of ZERO; high_water_passed ratchets UP only. Collection "
                "alone cannot fall when a test goes red -- a red test is still collected (R0543). "
                "red_since is the start of the CURRENT redness, cleared by any green run (R0564).",
    }
    rec["pass_fail"] = block
    rec.setdefault("max_collected", 0)
    (root / RECORD_REL).parent.mkdir(parents=True, exist_ok=True)
    (root / RECORD_REL).write_text(json.dumps(rec, indent=1), "utf-8")
    return block


def hours_since(stamp: str, now: datetime | None = None) -> float | None:
    """Hours since an ISO stamp, or None when it cannot be read. None is never zero.

    Public because the collector needs the SAME reading the grader uses: it decides whether a log
    postdates the recorded run, and two parsers for one stamp is how two organs come to disagree
    about whether a thing is stale."""
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return ((now or datetime.now(tz=UTC)) - parsed).total_seconds() / 3600.0


def grade(rec: dict[str, Any], *, now: datetime | None = None,
          max_age_h: float = MAX_AGE_H,
          red_entrenched_days: float = RED_ENTRENCHED_DAYS) -> tuple[str, str]:
    """(status, detail). Status is RED-ENTRENCHED / RED / FELL / UNMEASURED / STALE / OK.

    STALE AND UNMEASURED STAY DISTINCT. "no full run has ever been recorded" and "the last one is
    older than the tree" demand different first moves -- wire the writer, versus run the suite --
    and a desk that cannot tell them apart debugs the wrong organ (L1.55).

    RED-ENTRENCHED AND RED STAY DISTINCT FOR THE SAME REASON (R0564). Both mean a test is failing;
    they differ in what the desk should DO, and that is the only thing a status is for. RED is
    work in flight. RED-ENTRENCHED is a gate that has been failing long enough to be read as
    normal -- the state the merge-union regression sat in for 8 days while the suite's own alarm
    provided its cover, and the state 13 Kelly-sign tests sat in for 11. A red suite that nobody
    has cleared in three nightly runs is not backlog, it is a disabled gate (L1.43).
    """
    block = rec.get("pass_fail")
    if not isinstance(block, dict) or "n_passed" not in block:
        return "UNMEASURED", (
            "no pass/fail run has ever been recorded, so the suite ratchets on COLLECTION alone "
            "and a test that imports fine and FAILS is still collected. Nothing on this desk can "
            "currently see a test file go red except the CI gate, and a red CI gate hides new red")
    n_failed = int(block.get("n_failed", 0))
    n_passed = int(block.get("n_passed", 0))
    high = int(block.get("high_water_passed", 0))
    at = str(block.get("at", ""))
    age_h = hours_since(at, now)
    where = f"last run {at or 'unstamped'} via {block.get('source', 'unknown')}"

    # RED FIRST, ALWAYS. A stale record that recorded failures still says a test was broken; the
    # age qualifies how current that is, and can never withdraw it.
    if n_failed > 0:
        red_at = str(block.get("red_since") or "")
        red_h = hours_since(red_at, now) if red_at else None
        # UNRECORDED IS NOT ZERO AND IT IS NOT ENTRENCHED. A block predating `red_since` knows the
        # suite is red and not for how long, so it grades RED and says the duration is unmeasured
        # rather than claiming a short one -- the direction that cannot manufacture a clean read.
        # TWO DECIMALS, against a threshold measured in whole days. At one, a red of 2.96 days
        # prints "3.0d" beside a RED verdict and reads as a fence that failed to fire.
        span = (f"red for {red_h / 24.0:.2f}d (since {red_at})" if red_h is not None
                else "duration UNMEASURED (this record predates red_since, so the clock starts at "
                     "the next recorded run rather than being back-dated)")
        detail = (f"{n_failed} test(s) FAILED and {n_passed} passed ({where}); {span}. A red test "
                  f"is still COLLECTED, so the collection ratchet cannot see this")
        if red_h is not None and red_h > red_entrenched_days * 24.0:
            return "RED-ENTRENCHED", (
                f"{detail}. Past {red_entrenched_days:.0f} days this is no longer a fix in "
                f"flight: the suite runs nightly at best, so a red surviving three runs is a "
                f"gate the desk is CARRYING, and a permanently-red gate changes nobody's "
                f"behaviour (L1.43). Raise it as a row and clear it, or record here which tests "
                f"are red and why that is the accepted state")
        return "RED", detail
    if n_passed < high:
        return "FELL", (f"passing tests fell to {n_passed} from a high-water {high} ({where}). "
                        "A suite loses coverage one quiet decision at a time while 'tests pass' "
                        "stays true the whole way down; restore them, or record here why the "
                        "coverage is legitimately gone")
    if age_h is None:
        return "STALE", f"the recorded run carries no readable timestamp ({where})"
    if age_h > max_age_h:
        return "STALE", (f"the last recorded full run is {age_h:.0f}h old (max {max_age_h:.0f}h, "
                         f"{where}); it describes a tree that has moved on")
    return "OK", (f"{n_passed} passed, 0 failed, high-water {high}, {age_h:.1f}h old ({where})")
