"""CERT YIELD -- when the pipeline certifies nothing, say WHICH KIND of nothing it is.

WHY THIS EXISTS

The desk sweeps hourly and mints nothing, and every organ reports success while it happens: the
searcher finds thousands of hypotheses, the merge banks them, the gauntlet judges them and writes
its report, the dashboard shows the funnel. Every component is green and the output is zero. The
principal has asked the same question four separate ways -- "we run tests every hour, thousands of
candidates flowed through, backtesting is so low, I expect certificates every hour" -- and the
desk has never once answered it, because no artifact anywhere asks WHY the count is zero.

Zero has several causes and they demand OPPOSITE responses, which is exactly why collapsing them
into one number is so expensive:

  * NOT RUNNING     -- the sweep is stale or dropped its cells. Fix the machinery.
  * TOO WEAK        -- cells are judged and rejected, and the best of them does not clear the bar
                       EVEN IN SAMPLE, before any out-of-sample penalty applies. Mining more cells
                       of this shape cannot ever produce a certificate; it can only raise the
                       multiplicity charge and make the next honest candidate harder to certify.
                       The answer is different MECHANISMS, not more cells.
  * MARGINAL        -- cells land near the bar and fail on POWER gates, which forward evidence is
                       designed to cure. The answer is patience and shadow clocks, not new mining.

MEASURED 2026-08-28, the night this was written -- and it found BOTH failure modes at once,
which is exactly why they must be reported separately:

  * 314 of 460 cells failed an `observations` floor with `days: 0` -- no trades at all, ever.
    That is machinery, and it was concentrated in two families: carry (194) and event_reaction
    (113). Carry's swap-terms reader globbed `*.json` while its own recorder writes `*.parquet`,
    so it had NEVER read a file and returned [] for every symbol. Fixing the glob turned those
    cells from 0 days into ~1,900 each.
  * The 146 cells that DID trade all failed `deflated_sharpe`, at 0.0000 for 144 of them against
    a 0.3786 hurdle. The docket's in-sample Sharpe ran -0.152 to 0.171, median 0.043: not one
    cell reached the bar BEFORE any out-of-sample penalty.

The first number looks like the second if nobody separates them -- "0 daily observations" reads
as a mechanism that fires rarely rather than a reader that never opened a file. The desk had been
responding to both by mining harder, which could not have helped either.

WHAT THIS DELIBERATELY DOES NOT DO

It does not touch a threshold, a trial count, or a gate. A watchdog that "fixes" a yield problem
by lowering the bar manufactures survivors, and the entire point of the ten gates is that they are
not negotiable by the thing they are judging. The trial charge in particular must keep counting
every hypothesis examined: screening candidates and then charging only the screened set is the
selection bias the deflated Sharpe exists to correct. So this reports, loudly and specifically,
and the response stays with the principal.
"""
from __future__ import annotations

import json
import statistics
from collections import Counter
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATES = ROOT / "desks" / "mt5" / "reports" / "universal_gates_external.json"
OUT = ROOT / "data" / "cert_yield.json"

#: A sweep older than this means the question "why zero" is about MACHINERY, not candidate
#: quality, and the two must never be confused. The sweep is hourly, so three hours is three
#: missed runs -- comfortably past noise.
STALE_HOURS = 3.0

#: Within this fraction of the hurdle, a cell is close enough that forward evidence could
#: plausibly carry it: the POWER gates are curable by design. Beyond it, the gap is not a
#: patience problem.
MARGINAL_BAND = 0.5


def _read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def main() -> int:
    now = datetime.now(tz=UTC)
    prev = _read(OUT) or {}
    m: dict = {"measured_at": now.isoformat(timespec="seconds")}

    rep = _read(GATES)
    if not rep:
        m["verdict"] = "NO REPORT: the gauntlet has never written a gate report here"
        m["breach"] = "CERT-YIELD-NO-REPORT"
        OUT.write_text(json.dumps(m, indent=1), "utf-8")
        print(m["verdict"])
        return 1

    swept = str(rep.get("swept_at") or "")
    m["swept_at"] = swept
    age_h = None
    with suppress(ValueError):
        age_h = (now - datetime.fromisoformat(swept)).total_seconds() / 3600.0
    m["sweep_age_hours"] = None if age_h is None else round(age_h, 2)

    verdicts = rep.get("verdicts") or []
    submitted = int(rep.get("n_cells") or len(verdicts))
    judged = [v for v in verdicts if (v.get("stages") or {})]
    passed = [v for v in judged if v.get("passed") is True]
    m["submitted"] = submitted
    m["judged"] = len(judged)
    m["unmeasured"] = max(0, submitted - len(judged))
    m["passed"] = len(passed)
    m["trial_charge"] = rep.get("n_trials")

    # WHICH GATE BINDS. Counting every failure would credit gates that only ever saw cells already
    # doomed upstream; the FIRST failure in policy order is the one actually costing the cell.
    binding = Counter()
    for v in judged:
        for name, st in (v.get("stages") or {}).items():
            if st.get("passed") is False:
                binding[name] += 1
                break
    m["binding_gate"] = dict(binding.most_common())

    # HOW FAR SHORT, in the one unit that separates "too weak" from "not yet proven": the
    # in-sample Sharpe against the multiplicity-adjusted hurdle the deflated Sharpe applies. A
    # cell below this bar IN SAMPLE cannot pass out of sample -- no amount of further mining of
    # the same shape changes that, and saying so is the whole value of this check.
    hurdles = {round(float(st["sr0"]), 4)
               for v in judged
               for st in [(v.get("stages") or {}).get("deflated_sharpe") or {}]
               if isinstance(st.get("sr0"), (int, float))}
    hurdle = max(hurdles) if hurdles else None
    sharpes = sorted(float(st["sharpe"])
                     for v in judged
                     for st in [(v.get("stages") or {}).get("in_sample_screen") or {}]
                     if isinstance(st.get("sharpe"), (int, float)))
    m["hurdle_sr0"] = hurdle
    if sharpes:
        m["in_sample_sharpe"] = {
            "min": round(sharpes[0], 4),
            "median": round(statistics.median(sharpes), 4),
            "max": round(sharpes[-1], 4),
            "n": len(sharpes),
        }
        if hurdle:
            m["cells_above_hurdle_in_sample"] = sum(1 for s in sharpes if s > hurdle)
            m["cells_marginal"] = sum(1 for s in sharpes if s > hurdle * MARGINAL_BAND)
            m["best_as_fraction_of_hurdle"] = round(sharpes[-1] / hurdle, 3)

    # CONSECUTIVE BARREN SWEEPS. One zero is noise; a run of them on FRESH sweeps is a standing
    # condition, and the count is what makes it undeniable rather than a thing to explain away
    # each hour. Only a genuinely new sweep advances the streak -- re-reading the same report must
    # never inflate it.
    streak = int(prev.get("barren_streak") or 0)
    if swept and swept != prev.get("swept_at"):
        streak = streak + 1 if not passed else 0
    m["barren_streak"] = streak

    # --- THE VERDICT: name which kind of zero this is.
    if age_h is not None and age_h > STALE_HOURS:
        m["breach"] = "CERT-YIELD-STALE"
        m["verdict"] = (f"MACHINERY, not candidates: the last sweep is {age_h:.1f}h old "
                        f"(hourly cadence). Nothing can certify because nothing is judging.")
    elif passed:
        m["breach"] = None
        m["verdict"] = f"{len(passed)} cell(s) passed all ten gates in the latest sweep."
    elif not judged:
        m["breach"] = "CERT-YIELD-NO-JUDGMENT"
        m["verdict"] = (f"MACHINERY: {submitted} cells submitted and NONE judged -- every cell "
                        f"was dropped before a verdict.")
    elif hurdle and sharpes and sharpes[-1] < hurdle:
        m["breach"] = "CERT-YIELD-SHAPE"
        m["verdict"] = (
            f"TOO WEAK BY SHAPE, not by luck: {len(judged)} cells judged, 0 passed, and the BEST "
            f"in-sample Sharpe in the whole docket is {sharpes[-1]:.3f} against a {hurdle:.3f} "
            f"hurdle ({m['best_as_fraction_of_hurdle']:.0%} of the bar) -- before any "
            f"out-of-sample penalty. Mining more cells of this shape cannot certify one; it only "
            f"raises the trial charge and makes the next honest candidate harder to pass. "
            f"{streak} barren sweep(s) in a row. This needs different MECHANISMS, not more cells."
        )
    else:
        m["breach"] = "CERT-YIELD-MARGINAL"
        near = m.get("cells_marginal", 0)
        m["verdict"] = (
            f"NOT YET PROVEN: {len(judged)} judged, 0 passed, but {near} cell(s) sit within reach "
            f"of the {hurdle if hurdle else '?'} hurdle and the binding gate is "
            f"{next(iter(m['binding_gate']), '?')}. Power gates are curable by forward evidence -- "
            f"this is a patience and shadow-clock problem, not a mining problem."
        )

    OUT.write_text(json.dumps(m, indent=1), "utf-8")
    print(m["verdict"])
    print(f"  submitted={m['submitted']} judged={m['judged']} unmeasured={m['unmeasured']} "
          f"passed={m['passed']} trials={m['trial_charge']}")
    print(f"  binding gate: {m['binding_gate']}")
    print(f"  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
