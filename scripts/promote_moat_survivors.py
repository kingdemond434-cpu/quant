#!/usr/bin/env python3
"""EXPLOIT THE SURVIVORS -- turn a persistent moat finding into a PRE-REGISTERED forward clock.

THE GAP THIS CLOSES. `screen_moat.py` hunts the desk's self-recorded L2 tape continuously and
records every triple it promotes, together with the far more important denominator: how many times
that same triple was screened and did NOT survive. Nothing read that file. A survivor that is
recorded and never acted on is worth exactly what a survivor that was never found is worth -- and
the archive it came from is the one asset a competitor cannot buy, which makes leaving it inert
the most expensive form of idleness available to this desk.

WHY A SEPARATE ORGAN AND NOT A BRANCH INSIDE THE SCREEN. The screen's declared authority is NONE:
it screens, and it must be free to run ten thousand times a day without any of those runs moving
the desk. Pre-registration is an ACT -- it starts a clock the desk is then accountable to. Putting
the act inside the hunt would mean every extra pass of the hunt was also an extra promotion, which
is precisely how a search becomes a slot machine. Two organs, one direction of travel.

THE BAR IS DERIVED, NOT CHOSEN, AND THIS IS THE WHOLE STATISTICAL CONTENT.

Romano-Wolf controls family-wise error WITHIN one screening pass. Nothing controls it ACROSS
passes: screen the archive a thousand times and the sweep returns false survivors at the nominal
rate BY CONSTRUCTION. So "it survived" is not evidence -- the question is whether it survived MORE
OFTEN THAN THE SWEEP'S OWN FALSE-POSITIVE RATE would produce.

That rate is not assumed. It is MEASURED from the registry itself: total survivals over total
screenings across every triple the desk has ever screened is the empirical per-screening survival
probability under the desk's actual operating conditions. A candidate that survived k of n times
is then tested against Binomial(n, p_base) -- and only a tail probability below `ALPHA` earns a
clock. When the desk's base rate is high, the bar rises automatically; when the sweep gets
stricter, it falls. Nobody has to remember to retune it.

THREE MORE REFUSALS, EACH FOR A FAILURE THIS DESK HAS ALREADY MADE:

  ONE CELL IS NOT REPLICATION. Surviving twice on the same (venue, symbol, day) is one draw
  counted twice -- the same tape re-read. Independent CELLS are required, because a real
  microstructure effect does not care which day it is measured on.

  A SIGN THAT FLIPS IS A FIT. A genuine effect points the same way every time; a fitted one
  alternates, and its mean IC hides that by cancelling. Sign stability is checked BEFORE
  magnitude, because a large mean IC assembled from opposing days is the more convincing lie.

  SUSPECT-LOOKAHEAD IS NEVER PROMOTED, however persistent. The desk's own bithumb IC-0.72 fake was
  persistent too -- it was persistently misaligned. Consistency of an artifact is not evidence.

WHAT PROMOTION ACTUALLY BUYS: a forward clock, in the same shape `libs/research/axis_screen` uses,
and a line in the pre-registration ledger. NOT capital, NOT a weight, NOT a gate change. The
two-stage law is unchanged; this organ moves candidates from stage A to the waiting room, and the
waiting room's rent is paid in days.

Read-only over data/. Writes two artifacts. No keys, no order paths, no sizing.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REGISTRY = ROOT / "data/moat_survivors.json"
SCREEN = ROOT / "data/moat_screen.json"
PREREG = ROOT / "data/moat_preregistered.json"
CLOCK_DIR = ROOT / "data/moat_clocks"
REPORT = ROOT / "data/moat_promotion.json"

#: Tail probability under the measured base rate below which persistence stops looking like luck.
#: Deliberately tighter than a nominal 0.05: this is the LAST filter before the desk starts
#: spending days on a candidate, and days are the resource the two-stage law actually charges.
ALPHA = 0.01

#: Independent cells required. Two survivals on one cell is one tape read twice.
MIN_CELLS = 2

#: Minimum screenings before a hit rate means anything at all. 1-for-1 is a 100% hit rate.
MIN_SCREENINGS = 4

#: |mean(sign(IC))|. 1.0 is perfectly one-directional; below this the effect changes its mind.
MIN_SIGN_STABILITY = 0.8

#: A base rate at or above this means the SWEEP is broken, not that the desk found an edge. The
#: desk's prior is 420 screened, 420 dead; a sweep promoting a third of everything it sees is
#: mis-calibrated, and promoting off it would industrialise the error.
MAX_CREDIBLE_BASE_RATE = 0.25


def binom_tail(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p). Exact, no scipy -- n is tiny and stays tiny.

    This is the entire promotion test. A candidate that survived k of n screenings is asked how
    surprising that is GIVEN the rate at which this sweep promotes anything at all.
    """
    if n <= 0 or k <= 0:
        return 1.0
    if p <= 0.0:
        return 0.0 if k > 0 else 1.0
    if p >= 1.0:
        return 1.0
    return float(sum(math.comb(n, i) * p**i * (1.0 - p) ** (n - i) for i in range(k, n + 1)))


def base_rate(registry: dict) -> tuple[float, int, int]:
    """(survivals / screenings, survivals, screenings) over EVERY triple ever screened.

    THE DENOMINATOR IS THE POINT. Measuring the base rate from the winners alone would give 1.0
    and promote nothing; measuring it from the registry as a whole gives the sweep's own empirical
    false-positive rate under the desk's real operating conditions -- which is what a persistent
    candidate has to beat.
    """
    surv = sum(int(e.get("times_survived", 0)) for e in registry.values())
    seen = sum(int(e.get("times_screened", 0)) for e in registry.values())
    return (surv / seen if seen else 0.0), surv, seen


def _suspect(screen: dict) -> set[str]:
    """Triples the latest screen flagged SUSPECT-LOOKAHEAD or TIMING-ARTIFACT, by (symbol,
    mechanism). Persistence cannot rehabilitate an alignment artifact -- it was persistently
    misaligned."""
    bad: set[str] = set()
    for r in screen.get("results", []):
        if r.get("verdict") in ("SUSPECT-LOOKAHEAD", "TIMING-ARTIFACT"):
            sym = str(r.get("symbol", "")).split("@")[0]
            bad.add(f"{sym}|{r.get('mechanism')}")
    return bad


def adjudicate(registry: dict, suspect: set[str]) -> tuple[list[dict], list[dict], dict]:
    """(promoted, refused, stats). Every candidate gets a verdict WITH ITS REASON.

    Refusals are returned rather than dropped: "we looked and said no, because X" is a finding,
    and a promotion list without its refusals is a highlight reel.
    """
    p_base, surv, seen = base_rate(registry)
    stats = {"base_rate": round(p_base, 5), "total_survivals": surv, "total_screenings": seen,
             "triples_tracked": len(registry), "alpha": ALPHA}

    if p_base >= MAX_CREDIBLE_BASE_RATE:
        stats["state"] = "SWEEP-MISCALIBRATED"
        stats["why"] = (
            f"the sweep promotes {p_base:.1%} of everything it screens. The desk's prior is 420 "
            "hypotheses screened and 420 dead; a rate this high is a fact about the screen, not "
            "about the tape, and promoting off it would industrialise the error. NOTHING is "
            "promoted until the screen is re-examined.")
        return [], [], stats

    promoted, refused = [], []
    for key, e in sorted(registry.items()):
        k = int(e.get("times_survived", 0))
        n = int(e.get("times_screened", 0))
        cells = len(set(e.get("cells") or []))
        stab = e.get("ic_sign_stability")
        row = {"key": key, "symbol": e.get("symbol"), "mechanism": e.get("mechanism"),
               "horizon_s": e.get("horizon_s"), "times_survived": k, "times_screened": n,
               "cells": cells, "ic_mean": e.get("ic_mean"), "ic_sign_stability": stab,
               "best_p_adjusted": e.get("best_p_adjusted")}

        if k == 0:
            continue                                  # never survived; not a candidate at all
        if f"{e.get('symbol')}|{e.get('mechanism')}" in suspect:
            refused.append({**row, "refused": "SUSPECT-LOOKAHEAD",
                            "why": ("the screen flagged this mechanism as an alignment artifact. "
                                    "Persistence cannot rehabilitate one -- the desk's own "
                                    "bithumb IC-0.72 fake was persistent too, and persistently "
                                    "misaligned.")})
            continue
        if n < MIN_SCREENINGS:
            refused.append({**row, "refused": "TOO-FEW-SCREENINGS",
                            "why": f"{n} screening(s); 1-for-1 is a 100% hit rate and means "
                                   f"nothing. Needs {MIN_SCREENINGS}."})
            continue
        if cells < MIN_CELLS:
            refused.append({**row, "refused": "ONE-CELL",
                            "why": ("every survival came from the same (venue, symbol, day) -- "
                                    "one tape read twice, not replication")})
            continue
        if stab is None or float(stab) < MIN_SIGN_STABILITY:
            refused.append({**row, "refused": "SIGN-UNSTABLE",
                            "why": (f"IC sign stability {stab} < {MIN_SIGN_STABILITY}. A real "
                                    "effect points the same way every time; a fitted one "
                                    "alternates, and a mean IC hides that by cancelling.")})
            continue

        p = binom_tail(k, n, p_base)
        row["p_persistence"] = round(p, 6)
        if p > ALPHA:
            refused.append({**row, "refused": "NOT-BEYOND-CHANCE",
                            "why": (f"{k}/{n} survivals has probability {p:.4f} under the sweep's "
                                    f"own measured promotion rate of {p_base:.1%} -- above the "
                                    f"{ALPHA} bar. Romano-Wolf controls error WITHIN a pass; "
                                    "across passes only this does.")})
            continue
        promoted.append(row)

    promoted.sort(key=lambda r: (r["p_persistence"], -r["times_survived"]))
    return promoted, refused, stats


def start_clock(row: dict, *, clock_dir: Path) -> str:
    """Append today's observation to this candidate's forward clock. Idempotent per day.

    Same shape `libs/research/axis_screen` writes, so anything that already reads a forward clock
    reads this one -- a second clock format would be a second thing to remember.
    """
    clock_dir.mkdir(parents=True, exist_ok=True)
    safe = str(row["key"]).replace("/", "_").replace("|", "__").replace(":", "-")
    p = clock_dir / f"{safe}.jsonl"
    today = datetime.now(tz=UTC).date().isoformat()
    prev = p.read_text("utf-8").splitlines() if p.exists() else []
    if prev:
        try:
            if json.loads(prev[-1]).get("date") == today:
                return str(p.relative_to(ROOT))
        except json.JSONDecodeError:
            pass
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"date": today, "ic_mean": row.get("ic_mean"),
                             "times_survived": row["times_survived"],
                             "times_screened": row["times_screened"],
                             "p_persistence": row.get("p_persistence"),
                             "authority": "FORWARD CLOCK ONLY -- no capital, no weight"}) + "\n")
    return str(p.relative_to(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="adjudicate and report, but start no clocks")
    a = ap.parse_args()

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    try:
        registry = json.loads(REGISTRY.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        registry = {}
    if not isinstance(registry, dict) or not registry:
        REPORT.write_text(json.dumps({
            "ts": datetime.now(tz=UTC).isoformat(), "state": "NO REGISTRY",
            "reason": (f"{REGISTRY.relative_to(ROOT)} absent or empty -- the screen has not run, "
                       "or has run and promoted nothing. data/ is gitignored, so this is expected "
                       "in a fresh checkout and means the recorders are the blocker on the VPS."),
        }, indent=1), "utf-8")
        print("moat-promotion: NO REGISTRY -- scripts/screen_moat.py has produced nothing yet")
        return 0

    try:
        screen = json.loads(SCREEN.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        screen = {}

    promoted, refused, stats = adjudicate(registry, _suspect(screen))

    prereg: dict = {}
    try:
        prereg = json.loads(PREREG.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        prereg = {}
    if not isinstance(prereg, dict):
        prereg = {}

    now = datetime.now(tz=UTC).isoformat()
    clocks = []
    for row in promoted:
        rec = prereg.setdefault(row["key"], {**row, "pre_registered": now, "clock_days": 0})
        rec.update({k: row[k] for k in ("times_survived", "times_screened", "cells", "ic_mean",
                                        "ic_sign_stability", "p_persistence")})
        rec["last_confirmed"] = now
        if not a.dry_run:
            rec["clock"] = start_clock(row, clock_dir=CLOCK_DIR)
            rec["clock_days"] = len(
                (ROOT / rec["clock"]).read_text("utf-8").splitlines())
            clocks.append(rec["clock"])
    if not a.dry_run:
        PREREG.write_text(json.dumps(prereg, indent=1, sort_keys=True, default=str), "utf-8")

    out = {
        "ts": now, "dry_run": a.dry_run,
        "stats": stats,
        "promoted": promoted, "refused": refused,
        "pre_registered_total": len(prereg),
        "clocks_advanced": len(clocks),
        "note": ("A promotion here buys a FORWARD CLOCK and nothing else -- no capital, no weight, "
                 "no gate change. The bar is the sweep's OWN measured promotion rate, so it "
                 "tightens automatically when the screen gets looser. Zero promotions is the "
                 "expected outcome and a publishable one."),
        "authority": ("PRE-REGISTRATION ONLY. Stage A -> waiting room. Nothing here sizes, "
                      "allocates or trades, and no path from this file reaches an order."),
    }
    REPORT.write_text(json.dumps(out, indent=1, default=str), "utf-8")

    print(f"moat-promotion: base rate {stats['base_rate']:.2%} "
          f"({stats['total_survivals']}/{stats['total_screenings']} over "
          f"{stats['triples_tracked']} triples)")
    if stats.get("state") == "SWEEP-MISCALIBRATED":
        print(f"  SWEEP MISCALIBRATED -- nothing promoted. {stats['why'][:140]}")
        return 0
    if promoted:
        print(f"  PROMOTED ({len(promoted)}) -> forward clock, no capital:")
        for r in promoted:
            print(f"    {r['symbol']}:{r['mechanism']}@{r['horizon_s']}s "
                  f"{r['times_survived']}/{r['times_screened']} on {r['cells']} cells "
                  f"p={r['p_persistence']:.5f} ic={r['ic_mean']}")
    else:
        print("  NOTHING PROMOTED -- the expected outcome and a publishable one")
    by_reason: dict[str, int] = {}
    for r in refused:
        by_reason[r["refused"]] = by_reason.get(r["refused"], 0) + 1
    for reason, n in sorted(by_reason.items(), key=lambda kv: -kv[1]):
        print(f"  refused {reason:<22} {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
