#!/usr/bin/env python3
"""STRATEGY-BREADTH FENCE (R0211) -- the clock behind "never limit to just one thing".

PRINCIPAL, twice (2026-07-31): *"miners n explorers kimi etc all should find every crypto strat
even discretionary n all n never limit to just one thing."*

WHY A FENCE AND NOT ANOTHER PARAGRAPH. The first pass at this order widened eleven miner prompts
and built a coverage map. Both were necessary and neither is enforcement: a prompt is a request,
a map is a report, and this desk's own §36 says a conversion rule with no clock behind it is
decoration. The failure mode is not that a miner refuses the instruction -- it is that a miner
drifts back to the family it knows, one comfortable session at a time, while every dashboard
stays green because the volume never drops. Nothing would have caught that. This does.

WHAT IT FAILS ON, and each is a way breadth dies quietly:

  NARROW      the miners' recent output is concentrated in families already worked. Depth in a
              HUNTED family returns correlated candidates, and correlated candidates are one bet
              wearing many names -- the desk pays N times to learn once.
  UNWIDENED   a hunting surface has lost the breadth mandate. Prompts are edited by hand and by
              other sessions; this is the regression check that the instruction is still THERE,
              because an instruction silently deleted is indistinguishable from one never given.
  BLIND       the coverage map itself is missing or unreadable, so breadth is UNMEASURED -- which
              can never read as OK (L1.28a), because "no evidence of narrowing" and "no evidence"
              are the same sentence only to a broken gate.

WHAT IT DELIBERATELY DOES NOT DO: demand a quota of findings per family. A miner that returns
nothing from an unhunted family has produced negative knowledge, which this desk counts as a
result (L1.25a) -- and a fence that punished empty seams would push the miners straight back to
the crowded families where finds are easy and worthless. It measures where they LOOKED, never
what they brought back.

    python scripts/check_strategy_breadth.py [--json] [--report-only]
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

_STATE = "data/strategy_breadth.json"

#: The marker every hunting surface must carry. Checked as a STRING rather than by re-reading the
#: policy, because the failure this catches is the text going missing.
_MANDATE = "STRATEGY-FAMILY BREADTH"

#: Surfaces that brief a HUNTER. Deliberately not every prompt on the desk: second_family.py is a
#: transport that forwards its caller's prompt, and external_panel is a review seat -- putting a
#: hunting mandate in either would be policy in a pipe. Each entry is a file that tells some organ
#: WHAT TO GO LOOK FOR.
_HUNT_SURFACES: tuple[str, ...] = (
    "ops/prospector_dig_prompt.txt", "ops/litminer_dig_prompt.txt",
    "ops/dataaxis_dig_prompt.txt", "ops/blindrediscovery_dig_prompt.txt",
    "ops/frontier_en_prompt.txt", "ops/frontier_cn_prompt.txt", "ops/frontier_jp_prompt.txt",
    "ops/frontier_kr_prompt.txt", "ops/frontier_ru_prompt.txt", "ops/frontier_ar_prompt.txt",
    "ops/frontier_br_prompt.txt",
    "scripts/kimi_hunter.py",              # the only non-Claude hunter -- the widest lens owned
    "scripts/run_capability_hunt.py",
    "prompts/deep_sweep_core.txt",
)

#: Fraction of families that must be genuinely worked before breadth stops being the binding
#: constraint. 0.5 because below half the map, the cheapest growth available is a family nobody
#: has looked at once -- an unhunted family is uncorrelated with everything already tested by
#: construction, which is the property the sleeve allocator prices highest. Above it, depth in a
#: THIN family starts to beat opening the next one.
MIN_HUNTED_FRACTION = 0.5


def _coverage(root: Path) -> dict[str, Any] | None:
    try:
        return json.loads((root / "data/strategy_coverage.json").read_text("utf-8"))
    except (OSError, ValueError):
        return None


def build_report(root: Path | None = None, *, surfaces_only: bool = False) -> dict[str, Any]:
    """`surfaces_only` runs the PORTABLE half alone -- the mandate-present check, which reads
    only committed files and therefore means the same thing in CI, in a fresh clone and on the
    box. The breadth measurement reads data/strategy_coverage.json, which is LIVE STATE that no
    clean checkout has; running it as a commit gate would report BLIND on every PR and a gate
    that cries wolf gets switched off (L1.43). Same law/state split as
    check_scheduler_manifest --report-only, and for the same reason.

    The half that belongs at commit time is the right one: a mandate is deleted from a prompt by
    an edit, so the edit is the moment to catch it.
    """
    root = root or _ROOT
    # (a) UNWIDENED -- is the instruction still present on every hunting surface?
    unwidened = []
    for rel in _HUNT_SURFACES:
        p = root / rel
        try:
            if _MANDATE not in p.read_text("utf-8", errors="ignore"):
                unwidened.append(rel)
        except OSError:
            unwidened.append(f"{rel} (UNREADABLE)")

    # (b) NARROW / BLIND -- what does the coverage map say about where they have looked?
    cov = None if surfaces_only else _coverage(root)
    if surfaces_only:
        breadth = {"state": "NOT-RUN",
                   "why": "surfaces-only mode: the breadth measurement reads live state that a "
                          "clean checkout does not have, so it runs in the box gate where its "
                          "verdict is real"}
    elif cov is None or cov.get("status") == "UNREADABLE":
        breadth = {"state": "BLIND",
                   "why": "data/strategy_coverage.json missing or unreadable -- breadth is "
                          "UNMEASURED, and unmeasured never reads as OK (L1.28a). Run "
                          "scripts/run_strategy_coverage.py."}
    else:
        n_fam = int(cov.get("n_families") or 0)
        hunted = int(cov.get("n_hunted") or 0)
        frac = (hunted / n_fam) if n_fam else 0.0
        breadth = {
            "state": "OK" if frac >= MIN_HUNTED_FRACTION else "NARROW",
            "n_families": n_fam, "n_hunted": hunted,
            "hunted_fraction": round(frac, 3), "floor": MIN_HUNTED_FRACTION,
            "unhunted": cov.get("unhunted") or [], "thin": cov.get("thin") or [],
            "why": (f"{hunted}/{n_fam} families genuinely worked" if frac >= MIN_HUNTED_FRACTION
                    else f"only {hunted}/{n_fam} families worked ({frac:.0%} < "
                         f"{MIN_HUNTED_FRACTION:.0%}). The next dig belongs in "
                         f"{(cov.get('unhunted') or cov.get('thin') or ['an unhunted family'])[0]}"
                         ", not deeper in one already worked -- a worked family returns "
                         "correlated candidates, and correlated candidates are one bet wearing "
                         "many names."),
        }

    fails = bool(unwidened) or breadth["state"] in ("NARROW", "BLIND")
    status = ("UNWIDENED" if unwidened else breadth["state"] if fails else "OK")
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.32/L1.34 -- breadth is enforced, not requested. A prompt is a request and a "
               "coverage map is a report; neither fails when a miner drifts back to the family "
               "it knows, which is how breadth actually dies -- one comfortable session at a "
               "time, with the volume never dropping.",
        "status": status,
        "n_surfaces": len(_HUNT_SURFACES),
        "unwidened_surfaces": unwidened,
        "breadth": breadth,
        "not_a_quota": "this measures where the miners LOOKED, never what they brought back. A "
                       "miner returning nothing from an unhunted family produced negative "
                       "knowledge, which counts as a result (L1.25a); punishing empty seams "
                       "would push every seat back to the crowded families where finds are easy "
                       "and worthless.",
        "detail": (f"{len(unwidened)}/{len(_HUNT_SURFACES)} hunting surfaces have LOST the "
                   f"breadth mandate: {', '.join(unwidened[:4])}" if unwidened else
                   f"all {len(_HUNT_SURFACES)} hunting surfaces carry the mandate; "
                   + str(breadth["why"])),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--surfaces-only", action="store_true",
                    help="portable half only: the mandate-present check (repo files)")
    args = ap.parse_args()
    rep = build_report(_ROOT, surfaces_only=args.surfaces_only)
    out = _ROOT / _STATE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    print(json.dumps(rep, indent=2) if args.json else
          f"strategy breadth (L1.32): {rep['status']} -- {rep['detail'][:160]}")
    if args.report_only:
        return 0
    return 0 if rep["status"] == "OK" else 2


if __name__ == "__main__":
    sys.exit(main())
