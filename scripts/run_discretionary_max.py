#!/usr/bin/env python3
"""DISCRETIONARY MAX (R0151) -- the ceiling-pusher for the discretionary desk.

PRINCIPAL ORDER (2026-08-01): *"aim for 38 percent hit and maximise all parts of it, and make sure
there's a literal system dedicated to maxing this discretionary side and advancing it... push its
ceiling like the constitution forces everything, applies to this section too like everything, and
always."*

WHY A 38% HIT-RATE TARGET IS LEGAL HERE WHEN A CAGR TARGET IS NOT, because the two look similar
and are opposites. A return figure is reachable by SIZE, and size past full Kelly makes growth
negative -- so a stated return corrupts the optimizer into over-leverage (PROJECT_HANDOFF.md,
2026-07-12, and the fence R0143 that now enforces it). A HIT RATE cannot be reached by sizing at
all. It moves only through better selection, better information, and better filtering -- the exact
levers the desk wants pushed. Targeting the PROCESS variable is what makes the outcome variable
unnecessary to target. That distinction is the whole reason this organ is allowed to have a number.

WHY 38%: cost-adjusted breakeven is 31.1%, so 38 is roughly one full binomial standard error above
it at the sample sizes this sleeve will reach in a quarter -- the first level at which "this works"
is distinguishable from "this got lucky". Not a ceiling. If the measured rate reaches 38, this
organ re-aims at the next distinguishable level; it never reports "target met, stand down"
(L1.28c: every cadence hunts its own ceiling; L1.25a: the hunt never tires).

WHAT IT ACTUALLY DOES, and why it is not another dashboard. Every cycle it reads the sleeve's own
measurements, finds the BINDING constraint on the hit rate, and names the single highest-leverage
unbuilt lever for it. A board that lists ten things needing attention is a board that produces
none of them; naming ONE that is binding is what produces work.

THE LEVER LADDER, ordered by measured leverage rather than by appeal:

  1 INFORMATION   -- the sleeve reads PUBLIC charts. Public information cannot carry an edge for
                     long, so the largest single move is feeding it something that is not public
                     or not yet priced (the event sleeve's territory). Biggest lever, hardest.
  2 CROSS-FAMILY  -- an independent model family agreeing is a stronger filter than the same
                     family agreeing with itself. Blocked on the OpenRouter seat.
  3 SELECTION     -- once setup-conditional hit rates exist, trade only the setup classes that
                     measurably pay. Mechanical, and it needs only data.
  4 ENSEMBLE      -- already built (2-of-3). Its own value is measurable and it is reviewed here.
  5 EXECUTION     -- maker entries, tighter structural stops. Worth points of required hit rate
                     without touching the reasoning at all.

REFUSES TO IDLE. If every lever is either built or blocked on evidence, it says which evidence and
when it arrives -- it never returns "nothing to do", because on this desk an idle ceiling-pusher is
the failure it exists to prevent (L1.28a: idle capacity is unbooked loss).

    python scripts/run_discretionary_max.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_STATE = "data/discretionary_max.json"

#: The PROCESS target. Legal where a return target is not, because a hit rate cannot be reached by
#: sizing -- only by selection, information and filtering. 38% is ~one binomial standard error
#: above the 31.1% cost-adjusted breakeven at the sample sizes reachable in a quarter: the first
#: level at which "this works" is distinguishable from "this got lucky".
TARGET_HIT = 0.38
#: Re-aim step. On reaching the target this organ does not stand down; it advances to the next
#: distinguishable level, one standard error further (L1.25a -- the hunt never tires).
REAIM_STEP = 0.04


def _read(root: Path, rel: str) -> dict[str, Any]:
    try:
        return json.loads((root / rel).read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def levers(root: Path) -> list[dict[str, Any]]:
    """Every lever on the hit rate, with its state read from the desk's own measurements."""
    pnl = _read(root, "data/paper_book_pnl.json")
    probe = _read(root, "data/calibration_probe.json")
    alloc = _read(root, "data/sleeve_allocation.json")
    conv = _read(root, "data/conviction_trader.json")
    setup = pnl.get("setup_performance") or {}
    n_closed = int(pnl.get("n_resolved") or 0)

    measured_setups = sum(
        1 for f in setup.values() if isinstance(f, dict)
        for b in f.values() if isinstance(b, dict) and b.get("state") == "MEASURED")

    kimi_live = bool(_read(root, "data/kimi_hunt.json"))
    return [
        {"lever": "INFORMATION", "rank": 1,
         "state": "OPEN",
         "detail": "the sleeve reads PUBLIC chart structure; public information cannot carry an "
                   "edge for long. The event sleeve (R0122) is the non-public-information version "
                   "of the same hypothesis and is currently under-weighted against the chart one.",
         "action": "route effort to the event sleeve's feed quality -- more sources, lower "
                   "latency, richer documents -- rather than to more chart features"},
        {"lever": "CROSS-FAMILY", "rank": 2,
         "state": "BLOCKED" if not kimi_live else "OPEN",
         "detail": ("an INDEPENDENT model family agreeing is a stronger filter than one family "
                    "agreeing with itself; kimi_hunter has never produced (no OpenRouter seat)"
                    if not kimi_live else "second family is live and can be wired as a filter"),
         "action": ("fund the OpenRouter seat (~$5/mo on kimi-k2), then require cross-family "
                    "agreement on the conviction call" if not kimi_live
                    else "wire cross-family agreement into ensemble_consensus")},
        {"lever": "SELECTION", "rank": 3,
         "state": "BLOCKED" if measured_setups < 2 else "OPEN",
         "detail": (f"{measured_setups} setup buckets have enough closed trades to be MEASURED; "
                    "conditional hit rates are what say which setup classes to stop taking"),
         "action": ("accumulate closed trades -- this unlocks itself" if measured_setups < 2
                    else "gate the sleeve to the setup classes with a measured edge")},
        {"lever": "ENSEMBLE", "rank": 4,
         "state": "BUILT",
         "detail": f"2-of-3 consensus is live; last read {(conv.get('ensemble') or {}).get('state')}",
         "action": "measure whether agreement-filtered calls out-hit the rejected minority; "
                   "if not, the filter is costing frequency for nothing and goes"},
        {"lever": "EXECUTION", "rank": 5,
         "state": "BUILT",
         "detail": "maker-in entries and structural stops are worth ~1.8pp of required hit rate; "
                   "already assumed in the cost model",
         "action": "re-measure realised slippage against the 1.5bp assumption once live fills exist"},
        {"lever": "CALIBRATION", "rank": 2,
         "state": ("BLOCKED" if (probe.get("verdict") or {}).get("state") in
                   (None, "ACCUMULATING", "UNMEASURED") else "OPEN"),
         "detail": f"probe verdict {(probe.get('verdict') or {}).get('state')} after "
                   f"{(probe.get('verdict') or {}).get('n_resolved', 0)} resolved",
         "action": "if UNINFORMATIVE, strip the Kelly sizer and run flat size -- sizing on a "
                   "meaningless probability is strictly worse than not sizing on it"},
        {"lever": "EVIDENCE", "rank": 0,
         "state": "BLOCKED" if n_closed < 20 else "OPEN",
         "detail": f"{n_closed} closed marked trades; nothing conditional is measurable below ~20",
         "action": "the sleeve must actually run -- check_organ_liveness reports whether it is"},
        {"lever": "INDEPENDENCE", "rank": 6,
         "state": "BLOCKED" if alloc.get("status") in (None, "UNMEASURED") else "OPEN",
         "detail": f"sleeve allocation status {alloc.get('status')}",
         "action": "accumulate overlapping days so the conviction/event correlation is measurable; "
                   "until then both are assumed duplicates and share one budget"},
    ]


def build_report(root: Path | None = None) -> dict[str, Any]:
    root = root or _ROOT
    pnl = _read(root, "data/paper_book_pnl.json")
    hit = pnl.get("win_rate")
    n = int(pnl.get("n_resolved") or 0)
    lv = levers(root)
    open_ = [x for x in lv if x["state"] == "OPEN"]
    blocked = [x for x in lv if x["state"] == "BLOCKED"]
    # BINDING = lowest rank overall, OPEN or BLOCKED. Preferring an open lever over a blocked
    # higher-leverage one was wrong: with zero closed trades this reported INFORMATION as binding
    # while the actual constraint was that the sleeve was not producing at all. A blocked lever's
    # ACTION is its unlock, so blocked-and-highest-leverage is still the right thing to name.
    binding = min(lv, key=lambda x: (x["rank"], x["state"] != "BLOCKED")) if lv else None

    if hit is None or n < 20:
        aim, aim_why = TARGET_HIT, (
            f"hit rate UNMEASURED ({n} closed) -- the target stands at {TARGET_HIT:.0%} and the "
            "binding constraint is evidence, not selection")
    elif float(hit) >= TARGET_HIT:
        aim = round(float(hit) + REAIM_STEP, 4)
        aim_why = (f"measured {float(hit):.1%} has REACHED {TARGET_HIT:.0%} -- re-aiming at "
                   f"{aim:.1%}. This organ never reports 'target met, stand down' (L1.25a).")
    else:
        aim, aim_why = TARGET_HIT, (
            f"measured {float(hit):.1%} against a {TARGET_HIT:.0%} target and a 31.1% breakeven; "
            f"gap is {TARGET_HIT - float(hit):.1%}")

    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.28c/L1.25a applied to the discretionary desk -- every cadence hunts its own "
               "ceiling and the hunt never tires. A HIT RATE is a legal target where a return "
               "figure is not: it cannot be reached by sizing, only by selection, information and "
               "filtering.",
        "target_hit_rate": aim, "measured_hit_rate": hit, "n_closed": n,
        "aim_note": aim_why,
        "binding_lever": binding,
        "levers": sorted(lv, key=lambda x: x["rank"]),
        "n_open": len(open_), "n_blocked": len(blocked),
        "never_idle": ("every lever is built or blocked on named evidence; the binding one is "
                       f"'{binding['lever']}' and its unlock is: {binding['action']}"
                       if binding else "NO LEVERS ENUMERATED -- this organ has failed, not the desk"),
        "detail": (f"target {aim:.0%} hit; measured "
                   + (f"{float(hit):.1%} over {n} closed" if hit is not None else "UNMEASURED")
                   + f"; binding lever {binding['lever'] if binding else 'NONE'}"),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / _STATE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"discretionary max (L1.28c): {rep['detail']}")
        b = rep["binding_lever"]
        if b:
            print(f"  BINDING: {b['lever']} [{b['state']}] -- {b['action'][:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
