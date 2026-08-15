#!/usr/bin/env python3
"""RUNS the six order-book constructions from the principal's 175-item list. Stage A only.

**WHY THIS FILE EXISTS AT ALL: `libs/research/book_microstructure.py` HAD NO CALLER.** It was
written, tested and committed, and the only thing that imported it was its own test. That is
III.16 -- built is not a status -- and it is the same defect this wave spent the day removing from
the execution path, committed on the research path by the same session on the same day. A screen
that never runs produces no evidence, and a family of six constructions that produces no evidence
is indistinguishable from six constructions that were refuted.

**IT SHARES A CENSUS CLASS WITH `screen_orderbook_state.py` AND THAT IS A MULTIPLICITY PROBLEM,
NOT A DUPLICATION ONE.** Both test `orderbook_microstructure_state`. They are not redundant --
that screen is the desk's own pre-registered construction set over the raw L2 partitions, this one
is the principal's six -- but they are TRIALS ON ONE FAMILY. Run independently and read
independently, the desk would pay the family-wise bar twice and report neither payment: the
classic way a class accumulates a survivor that no single report can be blamed for. So this
artifact DECLARES the sibling and the pooled count, and anything reading a survivor out of either
must charge it against the union. The declaration is the honest half; pooling them into one
corrected report is follow-up work and is named here rather than implied to be done.

**HORIZON IS IN SNAPSHOTS, NOT MINUTES.** The depth poll is 5 seconds, so the default 12 is one
minute -- the horizon the immediacy and decay claims are actually about. A horizon expressed in
bars would be a different hypothesis wearing the same name.

**ZERO PROMOTION AUTHORITY.** A survivor earns a forward clock in its census family, never capital.
That is L1.6 and this file is not covered by the live-sleeve exception, which is scoped to
`run_mechanism_sleeves.py` by name.

    python scripts/screen_book_constructions.py [--symbols BTCUSDT,ETHUSDT] [--files 48] [--json]
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_OUT = Path("web/book_constructions.json")

#: The sibling screen on the same census class. Named so the multiplicity debt is visible in the
#: artifact rather than living in one commit message nobody re-reads.
SIBLING = "scripts/screen_orderbook_state.py"

DEFAULT_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")


def build(symbols: tuple[str, ...] = DEFAULT_SYMBOLS, *, max_files: int = 48,
          horizon: int = 12) -> dict[str, Any]:
    """Screen every symbol that has readable depth. A symbol with none is UNMEASURED, not refuted."""
    from libs.discretionary.tape import load_book
    from libs.research.book_microstructure import (
        MIN_OBS,
        N_CONSTRUCTIONS,
        UNSUPPORTED,
        screen,
        uncorrected_bar,
    )

    rep: dict[str, Any] = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "census_class": "orderbook_microstructure_state",
        "authority": ("STAGE A ONLY -- zero promotion authority. A survivor earns a forward clock "
                      "in its census family, never capital (L1.6)"),
        "constructions": N_CONSTRUCTIONS,
        "unsupported": UNSUPPORTED,
        "min_obs": MIN_OBS,
        "horizon_snapshots": horizon,
        # THE BAR A SINGLE CONSTRUCTION WOULD FACE ALONE, published beside the corrected ones so
        # the price of testing six is a number on the page rather than an assurance. The per-row
        # `bh_bar` is what each construction is actually judged at; the gap between them is what a
        # reader would otherwise have to take on trust.
        "uncorrected_bar": uncorrected_bar(),
        "uncorrected_bar_why": ("what ONE construction would face with no family correction. Every "
                                "row below is judged at its own BH bar instead; a construction "
                                "clearing only this number is a construction that did not clear"),
        "multiplicity_debt": {
            "sibling": SIBLING,
            "why": ("both screens test ONE census class. Read independently they each pay the "
                    "family-wise bar once and the class pays it twice, which is how a family "
                    "accumulates a survivor no single report can be blamed for"),
            "required": ("a survivor from either must be charged against the UNION of both "
                         "construction counts before it is treated as evidence"),
            "done": False,
        },
        "symbols": {}, "n_survivors": 0, "verdict": "UNMEASURED",
    }

    any_run = False
    for sym in symbols:
        try:
            books = load_book(sym, max_files=max_files)
        except Exception as exc:
            rep["symbols"][sym] = {"status": "UNREADABLE",
                                   "why": f"{type(exc).__name__}: {exc}"}
            continue
        if not books:
            # ABSENT TAPE IS NOT A NULL RESULT. This clone gitignores data/moat; the box records it.
            rep["symbols"][sym] = {
                "status": "NO-TAPE",
                "why": ("no depth partitions readable for this symbol. UNMEASURED -- absence must "
                        "never resolve to a clean verdict (L1.28a)")}
            continue
        out = screen(books, horizon=horizon)
        rep["symbols"][sym] = out
        if out.get("status") == "RUN":
            any_run = True
            rep["n_survivors"] += int(out.get("n_survivors") or 0)

    if not any_run:
        rep["verdict"] = "UNMEASURED"
        rep["why"] = ("no symbol produced a powered screen. That is a statement about the tape on "
                      "this host, not about the six constructions")
    else:
        rep["verdict"] = "SURVIVES-STAGE-A" if rep["n_survivors"] else "REFUTED"
    return rep


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    ap.add_argument("--files", type=int, default=48,
                    help="depth partitions per symbol. More is more power and more gzip scanning")
    ap.add_argument("--horizon", type=int, default=12,
                    help="forward horizon in SNAPSHOTS (5s poll, so 12 is one minute)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rep = build(tuple(s.strip() for s in args.symbols.split(",") if s.strip()),
                max_files=int(args.files), horizon=int(args.horizon))
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=1), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=1))
        return 0

    print(f"book-constructions: {rep['verdict']} -- {rep['n_survivors']} survivor(s) across "
          f"{rep['constructions']} constructions of {rep['census_class']}")
    for sym, out in rep["symbols"].items():
        st = out.get("status", "?")
        print(f"  [{st:<14}] {sym:<10} {str(out.get('why', ''))[:100]}")
        for r in out.get("results", []):
            print(f"      {r['verdict']:<17} {r['construction']:<22} "
                  f"IC={r['ic']} n={r['n']} t={r['t']} bar={r['bh_bar']}")
    print(f"  multiplicity debt vs {SIBLING}: NOT YET POOLED")
    print(f"-> {_OUT}")
    # UNMEASURED exits 0: on a clone without data/moat that is the correct and expected state, and
    # a red cycle step for a gitignored directory teaches the operator to ignore red cycle steps.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
