#!/usr/bin/env python3
"""THE ONLY REAL EVIDENCE IN THE CHAIN -- does a pre-registered moat candidate hold OUT OF SAMPLE?

THE LINK THAT WAS MISSING, AND IT IS THE ONE THAT MATTERS. The moat pipeline runs
mine -> screen -> register -> promote, and promotion buys a FORWARD CLOCK. Clocks accumulated and
nothing read them. That is the same failure as a survivor registry nobody adjudicates, one stage
later and more expensive: the desk would have been paying days into a waiting room with no door.

EVERYTHING UPSTREAM OF HERE IS IN-SAMPLE, INCLUDING THE PERSISTENCE TEST. `promote_moat_survivors`
asks whether a candidate survived more often than the sweep's own false-positive rate -- a real
question, answered on tape the screen had already seen. Repetition across cells is better evidence
than a single pass and it is still retrospective: every one of those cells existed, on disk,
before the candidate was named.

This organ asks the only question that is not: taking the candidate EXACTLY as pre-registered --
same mechanism, same symbol, same horizon, no re-fitting, no re-selection -- does it predict on
tape recorded AFTER the pre-registration date?

THE CUTOFF IS THE WHOLE DESIGN. A cell counts as forward ONLY if its day strictly postdates the
pre-registration timestamp. Include the registration day itself and the test quietly re-uses the
evidence that earned the clock, which converts an out-of-sample check into a slightly noisier
in-sample one -- the most flattering possible bug, and invisible in the output because the number
it produces looks exactly like a real one.

NOTHING IS RE-SELECTED HERE. The candidate is not re-screened across mechanisms or horizons to
find the version that still works: that would be a fresh search wearing the vocabulary of a
confirmation, and it would restore every multiple-testing problem the pipeline spent four organs
removing. One candidate, one specification, one number.

DECAY IS EXPECTED AND IS NOT FAILURE. A microstructure edge that half-lives is still tradeable at
the right size and horizon; one that inverts was never there. So the verdict distinguishes
HOLDING / DECAYED / INVERTED / DEAD rather than collapsing them into pass-fail, because those four
demand different responses and only the last two are refutations.

Read-only over data/. Writes one artifact. ZERO authority: no capital, no weight, no gate change.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.screen_moat as SM  # noqa: E402

PREREG = ROOT / "data/moat_preregistered.json"
REPORT = ROOT / "data/moat_clock_review.json"

#: Forward cells required before any verdict is issued. One cell is one day of one symbol -- a
#: reading, not evidence. Below this the honest answer is that the clock has not run long enough.
MIN_FORWARD_CELLS = 3

#: Forward |IC| as a fraction of the in-sample |IC|, above which the edge is HOLDING. Set at half
#: deliberately: in-sample magnitude is biased upward by the selection that produced it, so
#: demanding the full number would refute every real edge along with every false one.
HOLD_FRACTION = 0.5

#: Below this the forward reading is indistinguishable from nothing, whatever its sign.
IC_FLOOR = 0.02


def _day_after(day: str, cutoff_iso: str) -> bool:
    """Is this cell's tape STRICTLY after the pre-registration instant?

    The cell key is a date like `20260104`; the cutoff is a timestamp. A cell from the
    registration day itself is REJECTED -- part of it predates the clock and there is no way to
    tell which part, so including it would re-use the evidence that earned the clock.
    """
    try:
        d = datetime.strptime(day[:8], "%Y%m%d").replace(tzinfo=UTC)
        cut = datetime.fromisoformat(cutoff_iso)
    except (ValueError, TypeError):
        return False
    return d.date() > cut.date()


def forward_ic(symbol: str, mechanism: str, horizon_s: int, cutoff: str,
               *, budget: int = 12) -> dict:
    """Re-measure ONE pre-registered specification on post-registration tape only.

    Reuses `screen_moat.screen_symbol` rather than re-deriving the alignment. That is not tidiness:
    the screen's alignment took five corrections to get right (entry priced before the signal, a
    double-shifted target, a daily-calibrated Sharpe rail, horizons that were not strides, a
    stepdown fed constants), and a second implementation here would be a sixth waiting to happen.
    """
    venue, _, sym = symbol.partition(":")
    cells = {k: v for k, v in SM._cells().items()
             if k[0] == venue and k[1] == sym and _day_after(k[2], cutoff)}
    if not cells:
        return {"state": "NO-FORWARD-TAPE", "cells": 0}

    ics, ns, days = [], [], []
    for key in sorted(cells)[:budget]:
        rows: list[dict] = []
        for f in cells[key]:
            rows.extend(SM._rows(f))
        if not rows:
            continue
        for r in SM.screen_symbol(f"{key[0]}:{key[1]}@{key[2]}", rows):
            if (r.get("mechanism") == mechanism and r.get("horizon_s") == horizon_s
                    and np.isfinite(r.get("ic", np.nan))):
                ics.append(float(r["ic"]))
                ns.append(int(r.get("n", 0)))
                days.append(key[2])
    if not ics:
        return {"state": "NO-FORWARD-READING", "cells": len(cells),
                "why": ("forward tape exists but the mechanism resolved no IC on it -- too few "
                        "snapshots, or the venue stopped publishing an input")}
    a = np.asarray(ics)
    return {"state": "MEASURED", "cells": len(cells), "forward_cells": len(ics),
            "forward_ic_mean": round(float(a.mean()), 5),
            "forward_ic_median": round(float(np.median(a)), 5),
            "forward_sign_stability": round(float(abs(np.mean(np.sign(a)))), 3),
            "forward_n_total": int(sum(ns)), "days": days}


def verdict(in_sample_ic: float | None, fwd: dict) -> tuple[str, str]:
    """(verdict, why). Four outcomes, because they demand four different responses."""
    if fwd.get("state") != "MEASURED":
        return "NO-FORWARD-DATA", str(fwd.get("why") or
                                      "no tape recorded after the pre-registration date yet")
    if int(fwd["forward_cells"]) < MIN_FORWARD_CELLS:
        return "TOO-EARLY", (f"{fwd['forward_cells']} forward cell(s); "
                             f"{MIN_FORWARD_CELLS} required. One cell is a reading, not evidence.")
    if in_sample_ic is None or not np.isfinite(in_sample_ic) or in_sample_ic == 0:
        return "NO-BASELINE", "the registry recorded no in-sample IC to compare against"

    f = float(fwd["forward_ic_mean"])
    if np.sign(f) != np.sign(in_sample_ic):
        return "INVERTED", (f"forward IC {f:+.4f} points the OPPOSITE way to the in-sample "
                            f"{in_sample_ic:+.4f}. An effect that inverts was never there; this "
                            "is a refutation, not decay.")
    if abs(f) < IC_FLOOR:
        return "DEAD", (f"forward |IC| {abs(f):.4f} is below the {IC_FLOOR} floor -- "
                        "indistinguishable from nothing, whatever its sign.")
    ratio = abs(f) / abs(in_sample_ic)
    if ratio >= HOLD_FRACTION:
        return "HOLDING", (f"forward IC {f:+.4f} retains {ratio:.0%} of the in-sample "
                           f"{in_sample_ic:+.4f}, same sign, over {fwd['forward_cells']} cells "
                           "the candidate had never seen when it was named.")
    return "DECAYED", (f"forward IC {f:+.4f} retains only {ratio:.0%} of in-sample. Decay is not "
                       "failure -- an edge that half-lives can still be tradeable at the right "
                       "size -- but it is not the edge that was pre-registered.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cells", type=int, default=12,
                    help="max forward cells to read per candidate")
    a = ap.parse_args()

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    try:
        prereg = json.loads(PREREG.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        prereg = {}
    if not isinstance(prereg, dict) or not prereg:
        REPORT.write_text(json.dumps({
            "ts": datetime.now(tz=UTC).isoformat(), "state": "NOTHING PRE-REGISTERED",
            "reason": ("data/moat_preregistered.json absent or empty -- no candidate has cleared "
                       "promotion, so there is no clock to read. That is the expected state: the "
                       "desk's prior is 420 screened, 420 dead."),
        }, indent=1), "utf-8")
        print("moat-clocks: NOTHING PRE-REGISTERED -- no clock to read")
        return 0

    rows = []
    for key, rec in sorted(prereg.items()):
        fwd = forward_ic(str(rec.get("symbol")), str(rec.get("mechanism")),
                         int(rec.get("horizon_s") or 0), str(rec.get("pre_registered")),
                         budget=a.cells)
        v, why = verdict(rec.get("ic_mean"), fwd)
        rows.append({"key": key, "symbol": rec.get("symbol"),
                     "mechanism": rec.get("mechanism"), "horizon_s": rec.get("horizon_s"),
                     "pre_registered": rec.get("pre_registered"),
                     "clock_days": rec.get("clock_days"),
                     "in_sample_ic": rec.get("ic_mean"),
                     "verdict": v, "why": why, **fwd})

    tally: dict[str, int] = {}
    for r in rows:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1

    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "pre_registered": len(prereg), "reviewed": len(rows), "tally": tally,
        "holding": [r["key"] for r in rows if r["verdict"] == "HOLDING"],
        "refuted": [r["key"] for r in rows if r["verdict"] in ("INVERTED", "DEAD")],
        "results": rows,
        "note": ("The ONLY out-of-sample evidence in the moat pipeline. Everything upstream -- "
                 "including the persistence test -- is answered on tape that already existed when "
                 "the candidate was named. A forward cell must STRICTLY postdate the "
                 "pre-registration date: including the registration day would re-use the evidence "
                 "that earned the clock, which is the most flattering possible bug and invisible "
                 "in the output. Nothing is re-selected: one candidate, one specification, one "
                 "number, or a confirmation becomes a fresh search wearing its vocabulary."),
        "authority": ("NONE. Reports whether a pre-registered candidate held. Does not size, "
                      "allocate, promote or retire -- a HOLDING verdict is evidence for a later "
                      "decision, not the decision."),
    }
    REPORT.write_text(json.dumps(out, indent=1, default=str), "utf-8")

    print(f"moat-clocks: {len(rows)} pre-registered candidate(s) reviewed against forward tape")
    for v, c in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"  {v:<18} {c}")
    for r in rows:
        if r["verdict"] in ("HOLDING", "INVERTED", "DECAYED"):
            print(f"  {r['verdict']:<9} {r['symbol']}:{r['mechanism']}@{r['horizon_s']}s "
                  f"| {r['why'][:110]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
