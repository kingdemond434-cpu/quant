"""F20 -- WHAT FRACTION OF PURE NOISE WOULD THIS FORWARD LANE PROMOTE?

THE PRINCIPAL, 2026-09-12:

    Forward testing must become sequential statistical inference, not simply accumulation. Run
    placebo/null candidates beside real ones, measure observed false-admission continuously, use
    always-valid/sequential tests or Bayesian updating, pre-register stopping rules, and
    explicitly calibrate selection pressure versus forward capacity. This is especially important
    because your earlier audit showed the forward queue could be saturated by nulls.

WHAT THE DESK ALREADY HAS, AND WHY IT IS NOT THIS. `adversary.py` runs poison canaries against the
GAUNTLET -- i.i.d. noise fed to the ten gates, and it proves they reject it (5/5 rejected on the
last clean run). That is the in-sample judge. The FORWARD lane is a different judge with a
different rule -- expectancy above a bar, a day count, a trade count -- and nothing has ever asked
what that rule does to noise.

THE QUESTION IS COMPUTABLE TODAY AND HAS NEVER BEEN COMPUTED. The promotion rule is explicit, and
the desk's own clocks supply the empirical n and R distributions. So: draw NULL clocks with the
same trade counts and the same per-trade R dispersion, zero true edge, and count how many clear
the bar. That fraction IS the false-admission rate of the forward lane -- not an assumption about
it, a measurement of it.

WHY IT MATTERS MORE THAN IT SOUNDS. Forward capacity is finite: a clock occupies a lane for
fourteen days minimum. If the lane admits noise at 20%, then one in five funded sleeves is paying
rent on a coin flip, the book's measured n_eff is flattered by bets that are pure variance, and
the desk cannot tell a thinning edge from a lane that was never selective. Selection pressure and
capacity are the same constraint seen from two ends.

IT MEASURES AND NEVER TIGHTENS. If the false-admission rate is high, the answer is NOT to raise
the bar by fiat -- that is a growth cut wearing a statistic, and the standing order forbids it.
The answer is more forward capacity or a longer window, and which one is a decision the CEO docket
takes on evidence. This organ supplies the evidence.

    python desks/mt5/research/forward_calibration.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = DESK / "reports" / "FORWARD_CALIBRATION.json"
LANES = (
    DESK / "reports" / "shadow" / "shadow_state.json",
    DESK / "reports" / "shadow" / "qquant_shadow_state.json",
    DESK / "reports" / "shadow" / "scalp_shadow_state.json",
)

#: The promotion rule, restated here as the thing being TESTED rather than imported, because the
#: point is to measure what THIS rule does to noise. Restating it means a change to the rule that
#: is not reflected here shows up as a disagreement rather than silently re-calibrating.
MIN_DAYS = 14
MIN_TRADES = 20
MIN_EXPECTANCY_R = 0.05

#: Null draws per clock. 4,000 keeps the standard error on a 5% rate near 0.3pp -- fine enough to
#: separate "the lane admits noise at 5%" from "at 15%", which is the only distinction that
#: changes a decision.
DRAWS = 4000
SEED = 20260912


def _clocks() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in LANES:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for key, row in d.items():
            if isinstance(row, dict) and "status" in row:
                rows.append({"key": key, **row})
    return rows


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    rows = _clocks()
    live = [r for r in rows if str(r.get("status", "")).upper() == "ACTIVE"]
    ns = [int(r.get("n") or 0) for r in live if (r.get("n") or 0) >= 2]
    exps = [float(r.get("exp_r")) for r in live
            if isinstance(r.get("exp_r"), (int, float))]
    if len(ns) < 5 or len(exps) < 5:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": (f"only {len(ns)} clock(s) carry a trade count and {len(exps)} an "
                        f"expectancy -- too few to estimate the lane's own R dispersion. "
                        f"UNMEASURED is the answer, not a default false-admission rate.")}

    # THE DISPERSION IS THE DESK'S OWN, not an assumed one. A null clock must look like this
    # desk's clocks in everything except edge, or the rate measured is about a fictional lane.
    sd = statistics.pstdev(exps) if len(exps) > 1 else 0.0
    # Per-TRADE dispersion, recovered from the dispersion of per-clock MEANS: sd(mean) = s/sqrt(n),
    # so s = sd(mean) * sqrt(median n). Using the median n keeps one very long clock from
    # dominating the estimate.
    med_n = statistics.median(ns)
    per_trade_sd = sd * (med_n ** 0.5) if med_n else 0.0

    # Deterministic null draws, never a secret -- the seed is published so the
    # measurement is reproducible, which is the opposite of a cryptographic need.
    rng = random.Random(SEED)  # noqa: S311
    admitted = 0
    per_n: dict[int, int] = {}
    trials = 0
    for n in ns:
        if n < 2:
            continue
        hits = 0
        for _ in range(DRAWS):
            # A null clock: n trades, ZERO true edge, this desk's own per-trade dispersion.
            draws = [rng.gauss(0.0, per_trade_sd) for _ in range(n)]
            mean_r = sum(draws) / n
            if n >= MIN_TRADES and mean_r > MIN_EXPECTANCY_R:
                hits += 1
        per_n[n] = hits
        admitted += hits
        trials += DRAWS

    rate = admitted / trials if trials else 0.0
    # Wilson interval -- an always-valid-flavoured bound rather than a bare point estimate, so a
    # rate read off few clocks cannot be quoted as if it were precise.
    z = 1.96
    denom = 1 + z * z / trials if trials else 1
    centre = (rate + z * z / (2 * trials)) / denom if trials else 0.0
    half = (z * ((rate * (1 - rate) / trials + z * z / (4 * trials * trials)) ** 0.5)) / denom \
        if trials else 0.0

    eligible = [r for r in live
                if int(r.get("n") or 0) >= MIN_TRADES
                and int(r.get("days_active") or r.get("days") or 0) >= MIN_DAYS]
    passing = [r for r in eligible
               if isinstance(r.get("exp_r"), (int, float)) and float(r["exp_r"]) > MIN_EXPECTANCY_R]
    observed = len(passing) / len(eligible) if eligible else None
    expected_false = rate * len(eligible) if eligible else 0.0

    return {
        "at": now.isoformat(timespec="seconds"),
        "rule": {"min_days": MIN_DAYS, "min_trades": MIN_TRADES,
                 "min_expectancy_r": MIN_EXPECTANCY_R},
        "lane": {"n_clocks": len(rows), "n_active": len(live),
                 "n_eligible": len(eligible), "n_passing": len(passing),
                 "observed_pass_rate": None if observed is None else round(observed, 4)},
        "dispersion": {"per_clock_expectancy_sd": round(sd, 5),
                       "median_trades": med_n,
                       "implied_per_trade_sd": round(per_trade_sd, 5)},
        "null": {"draws_per_clock": DRAWS, "total_draws": trials,
                 "false_admission_rate": round(rate, 5),
                 "ci95": [round(max(0.0, centre - half), 5), round(centre + half, 5)],
                 "expected_false_admissions_now": round(expected_false, 2)},
        "verdict": _verdict(rate, observed, expected_false, len(eligible)),
        "status": "ATTENTION" if rate > 0.10 else "OK",
        "boundary": ("MEASURES, NEVER TIGHTENS. A high rate is not licence to raise the bar -- "
                     "that is a growth cut wearing a statistic, and the standing order forbids "
                     "it. The remedies are more forward capacity or a longer window, and which "
                     "is the CEO docket's decision on this evidence."),
        "why": ("forward capacity is finite: a clock holds a lane for at least 14 days. A lane "
                "that admits noise pays rent on coin flips, flatters the book's n_eff with bets "
                "that are pure variance, and cannot distinguish a thinning edge from a lane that "
                "was never selective."),
    }


def _verdict(rate: float, observed: float | None, expected_false: float,
             n_eligible: int) -> dict[str, Any]:
    if observed is None:
        return {"state": "UNMEASURED",
                "why": "no clock has yet cleared both the day and trade minimums"}
    if rate <= 0.0:
        return {"state": "SELECTIVE",
                "why": ("no null draw cleared the bar: at this desk's measured dispersion the "
                        "forward rule is not passable by noise at these trade counts")}
    lift = observed / rate if rate else float("inf")
    if lift < 1.5:
        return {"state": "SATURATED_BY_NOISE",
                "why": (f"the lane passes {observed:.1%} of eligible clocks and pure noise would "
                        f"pass {rate:.1%} -- a lift of only {lift:.2f}x. Roughly "
                        f"{expected_false:.1f} of {n_eligible} eligible clocks are what chance "
                        f"alone would deliver, so the forward record is close to uninformative.")}
    return {"state": "INFORMATIVE",
            "why": (f"the lane passes {observed:.1%} against a noise rate of {rate:.1%} -- a lift "
                    f"of {lift:.2f}x. About {expected_false:.1f} of {n_eligible} eligible clocks "
                    f"would be expected from chance, so the surplus is the lane's information.")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    if doc.get("status") == "UNMEASURED":
        print(f"forward calibration: UNMEASURED -- {doc['why'][:140]}")
    else:
        n, lane, v = doc["null"], doc["lane"], doc["verdict"]
        print(f"forward calibration: {doc['status']}   {v['state']}")
        print(f"  rule           : n>={doc['rule']['min_trades']}, "
              f"days>={doc['rule']['min_days']}, exp>{doc['rule']['min_expectancy_r']}R")
        print(f"  lane           : {lane['n_eligible']} eligible, {lane['n_passing']} passing "
              f"({lane['observed_pass_rate']})")
        print(f"  noise would pass {n['false_admission_rate']:.2%} "
              f"CI95 [{n['ci95'][0]:.2%}, {n['ci95'][1]:.2%}] "
              f"-> {n['expected_false_admissions_now']} false admission(s) expected now")
        print(f"  {v['why'][:170]}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
