"""Does a change to the research brain actually help, or does it only feel like it?

WHY THIS EXISTS (2026-08-30)

Every structural change this desk has made to its own search -- surgical mutation, novelty V2,
Thompson allocation, the adapter registry -- was argued for and then shipped. None was MEASURED.
The desk cannot currently say whether diagnosis-driven mutation produces better candidates than
re-rolling, and "it is obviously better" is the reasoning that produced 10,624 candidates for
7 certificates.

THE HARD PART IS NOT THE TEST, IT IS THE HEADLINE METRIC. The metric anyone would name --
forward survivors -- is ZERO for both arms and has been zero for the desk's whole history. An A/B
on a metric that is identically zero returns "no difference" forever while looking rigorous, which
is worse than not running it: it manufactures evidence of no effect from an absence of data.

THE LADDER IS THE ANSWER. Four metrics, each a strictly harder filter, each a leading indicator of
the one below. The harness uses THE DEEPEST RUNG BOTH ARMS HAVE DATA ON and names the rung in
every report:

    forward_survived        terminal. What actually matters. Currently 0/0.
    forward_enrolled        passed the backtest gauntlet and got a clock
    cost_survived           gross edge outlived the spread
    attributable_measured   was measured by something that can speak about its own mechanism

A WIN ON A LEADING RUNG IS NOT A WIN. It is a reason to keep the arm alive until the terminal rung
has data. This is stated in the output rather than left to the reader, because a leading-metric
win read as a terminal one is how a desk convinces itself it is improving while its live P&L does
nothing. As soon as survivors exist the ladder promotes itself to the terminal rung and the
verdict changes basis automatically -- which is the sense in which this is "ready and fires once
we have survivors" rather than something to be rewritten then.

ASSIGNMENT IS DETERMINISTIC AND HAPPENS AT PROPOSAL TIME, from a hash of the candidate id --
before any outcome exists. Two consequences, both required for the result to mean anything: a
re-run assigns identically (so the comparison is reproducible), and nothing can steer a promising
candidate toward the arm being championed. `hash()` is NOT used: Python salts it per process, so
arms would silently reshuffle on restart and every historical comparison would be reading a
different experiment than it thought.

THE TEST IS ALWAYS-VALID, reusing the same Robbins mixture as the forward verdict. The hourly loop
looks at this every hour; a fixed-n t-test peeked at hourly has a false-positive rate far above
its nominal alpha, and would hand the desk a "significant" winner from noise within days. A
winner is declared only when the two confidence sequences stop overlapping -- conservative, and it
cannot be rushed by looking more often.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: The metric ladder, DEEPEST FIRST. Order is the algorithm: the harness reports on the first rung
#: where both arms clear MIN_PER_ARM, so the basis strengthens by itself as the desk matures.
METRIC_LADDER: tuple[tuple[str, str], ...] = (
    ("forward_survived", "survived the 14-day forward shadow -- the only rung that is money"),
    ("forward_enrolled", "cleared the backtest gauntlet and was given a forward clock"),
    ("cost_survived", "expectancy stayed positive after spread and slippage"),
    ("attributable_measured", "measured by an adapter that can speak about its own mechanism"),
)

#: Per arm, not in total. Two arms of 30 is a comparison; 60 in one arm and 3 in the other is a
#: description of the big arm with noise attached.
MIN_PER_ARM = 20

#: Matches the forward verdict's alpha so a claim about the brain is held to the same standard as
#: a claim about a strategy.
ALPHA = 0.05

#: The arms. Adding one is a dict entry; the harness never hardcodes two.
#:
#: `control` is NOT "do nothing" -- it is the desk's behaviour before the change, which is the
#: only comparison that answers "was shipping this correct".
ARMS: dict[str, dict[str, Any]] = {
    "control": {
        "breed_children": False,
        "why": "failures are diagnosed and logged; the budget goes to fresh proposals, which is "
               "what the desk did before surgical mutation existed",
    },
    "mutation": {
        "breed_children": True,
        "why": "each diagnosed failure breeds one child that changes ONLY the indicted link",
    },
}

#: Default arm when assignment cannot be computed. Control, deliberately: an unassignable
#: candidate must not be quietly counted toward the arm under test.
DEFAULT_ARM = "control"


def assign_arm(hypothesis_id: str, arms: tuple[str, ...] | None = None) -> str:
    """Stable arm for a candidate, from its id alone.

    blake2b rather than `hash()`: Python's builtin hash is salted per process, so arms would
    reshuffle on every restart and each report would silently describe a different experiment.
    """
    names = tuple(arms or sorted(ARMS))
    if not names or not hypothesis_id:
        return DEFAULT_ARM
    digest = hashlib.blake2b(hypothesis_id.encode("utf-8"), digest_size=8).digest()
    return names[int.from_bytes(digest, "big") % len(names)]


def _interval(xs: list[float]) -> tuple[float, float, float]:
    """Always-valid (lower, mean, upper) for a 0/1 sample, from the forward verdict's own test.

    THE SIGMA IS BERNOULLI, NOT THE SAMPLE DEVIATION, and that is the difference between a
    harness that works at zero survivors and one that does not. An arm with no successes has zero
    observed deviation; the engine's own guard reads that as "no usable proxy" and returns -inf,
    which is right for R-multiples and wrong here, because a proportion's variance is determined
    by its mean. Left alone it produces an infinitely wide interval for the empty arm, so no
    winner could EVER be declared on the terminal rung -- the exact rung this is being built for.

    The Jeffreys smoothing ((k+0.5)/(n+1)) is what keeps a 0/n arm honest: it says the true rate
    is small rather than certainly zero, which is the claim the data actually supports.
    """
    if not xs:
        return 0.0, 0.0, 0.0
    n = len(xs)
    mean = sum(xs) / n
    p = (sum(xs) + 0.5) / (n + 1.0)          # Jeffreys: 0/n is "small", never "certainly zero"
    sigma = math.sqrt(p * (1.0 - p))
    lower = float(_engine().sequential_lower_bound(xs, alpha=ALPHA, sigma=sigma))
    if lower == float("-inf"):
        return float("-inf"), mean, float("inf")
    half = mean - lower
    return lower, mean, mean + half


def _engine() -> Any:
    """The canonical forward verdict module, loaded by path.

    `desks/` is deliberately not a package, so a static import cannot reach the engine from
    `libs/`. It is imported dynamically -- the same pattern `libs/ops/audit_recheck.py` uses --
    rather than being reimplemented here: there is ONE always-valid test on this desk, and a
    second copy would drift from it the first time either was tuned.
    """
    research = Path(__file__).resolve().parents[2] / "desks" / "mt5" / "research"
    if str(research) not in sys.path:
        sys.path.insert(0, str(research))
    return importlib.import_module("forward_verdict")


@dataclass
class ArmResult:
    arm: str
    n: int
    successes: int
    rate: float
    lower: float
    upper: float


def compare(outcomes: dict[str, list[float]], metric: str, why: str) -> dict[str, Any]:
    """Two or more arms on ONE metric, with an always-valid verdict.

    A winner requires NON-OVERLAPPING confidence sequences. Comparing point estimates would
    declare a winner on the first lucky candidate; comparing fixed-n intervals hourly would
    declare one on the fifth. Neither survives contact with a desk that checks every hour.
    """
    results = []
    for arm, xs in sorted(outcomes.items()):
        lo, mean, hi = _interval(xs)
        results.append(ArmResult(arm=arm, n=len(xs), successes=int(sum(xs)),
                                 rate=round(mean, 4), lower=round(lo, 4), upper=round(hi, 4)))
    results.sort(key=lambda r: -r.rate)

    thin = [r.arm for r in results if r.n < MIN_PER_ARM]
    verdict = "INCONCLUSIVE"
    detail = ""
    if thin:
        verdict = "UNDERPOWERED"
        detail = (f"arm(s) {thin} below {MIN_PER_ARM} candidates. Not a null result -- the "
                  f"experiment has not run yet, and reporting it as 'no difference' would be a "
                  f"claim the data cannot support.")
    elif len(results) >= 2 and results[0].lower > results[1].upper:
        verdict = f"WINNER: {results[0].arm}"
        detail = (f"{results[0].arm} lower bound {results[0].lower} exceeds "
                  f"{results[1].arm} upper bound {results[1].upper} under an always-valid "
                  f"sequence, so hourly peeking did not manufacture this.")
    else:
        detail = ("confidence sequences still overlap. Keep both arms running -- an always-valid "
                  "bound narrows with n and cannot be hurried by checking more often.")

    return {
        "metric": metric, "metric_means": why, "verdict": verdict, "detail": detail,
        "terminal": metric == METRIC_LADDER[0][0],
        "caveat": ("" if metric == METRIC_LADDER[0][0] else
                   f"{metric!r} is a LEADING rung, not money. A win here is a reason to keep the "
                   f"arm alive until {METRIC_LADDER[0][0]!r} has data, not a reason to ship."),
        "arms": [{"arm": r.arm, "n": r.n, "successes": r.successes, "rate": r.rate,
                  "lower": r.lower, "upper": r.upper} for r in results],
        "alpha": ALPHA,
    }


def _outcomes_from_store() -> dict[str, dict[str, list[float]]]:
    """Per metric, per arm, a 0/1 outcome for every assigned candidate."""
    from libs.research_os import store
    from libs.research_os.credit import ATTRIBUTABLE, STAGE_VALUE, _stage_for

    per_metric: dict[str, dict[str, list[float]]] = {m: {a: [] for a in ARMS}
                                                     for m, _ in METRIC_LADDER}
    with store.connect() as conn:
        rows = conn.execute(
            "SELECT hypothesis_id, brain_version FROM hypotheses").fetchall()
        for hid, arm_col in rows:
            arm = str(arm_col or "") or assign_arm(str(hid))
            if arm not in ARMS:
                continue
            stage, mcls, _ = _stage_for(str(hid), conn)
            v = STAGE_VALUE.get(stage, 0.0)
            per_metric["forward_survived"][arm].append(
                1.0 if stage in ("FORWARD_SURVIVED", "CERTIFIED", "LIVE") else 0.0)
            per_metric["forward_enrolled"][arm].append(
                1.0 if v >= STAGE_VALUE["FORWARD_ENROLLED"] else 0.0)
            per_metric["cost_survived"][arm].append(
                1.0 if v >= STAGE_VALUE["COST_SURVIVED"] else 0.0)
            per_metric["attributable_measured"][arm].append(
                1.0 if mcls in ATTRIBUTABLE else 0.0)
    return per_metric


def report() -> dict[str, Any]:
    """The deepest rung both arms can support, plus every rung below it for context."""
    per_metric = _outcomes_from_store()
    rungs = []
    headline = None
    for metric, why in METRIC_LADDER:
        outcomes = per_metric.get(metric, {})
        res = compare(outcomes, metric, why)
        rungs.append(res)
        if headline is None and all(len(v) >= MIN_PER_ARM for v in outcomes.values()) \
                and outcomes:
            headline = res
    if headline is None:
        headline = rungs[-1] if rungs else {"verdict": "NO DATA"}
    return {
        "arms": {k: v["why"] for k, v in ARMS.items()},
        "headline": headline,
        "ladder": rungs,
        "assignment": ("deterministic blake2b of the candidate id, computed at proposal time "
                       "before any outcome exists -- reproducible across restarts and impossible "
                       "to steer"),
    }


def main() -> int:
    r = report()
    print("RESEARCH BRAIN A/B")
    for arm, why in r["arms"].items():
        print(f"  arm {arm:10s} {why}")
    h = r["headline"]
    print(f"\n  headline rung : {h.get('metric')}  ({h.get('metric_means','')})")
    print(f"  verdict       : {h.get('verdict')}")
    print(f"  {h.get('detail','')}")
    if h.get("caveat"):
        print(f"  CAVEAT: {h['caveat']}")
    for rung in r["ladder"]:
        arms = "  ".join(f"{a['arm']}={a['successes']}/{a['n']}" for a in rung["arms"])
        print(f"    {rung['metric']:24s} {arms:40s} {rung['verdict']}")
    out = __import__("pathlib").Path("data/brain_ab.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(r, indent=1), "utf-8")
    print(f"\n  -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
