#!/usr/bin/env python3
"""MECHANISM SUPPLY -- turn the census's ranked gaps into owed collector work, or say what blocks it.

THE BINDING CONSTRAINT, stated by the desk's own measurements and not by argument: DISTINCT
MECHANISM SUPPLY. Cross-mechanism N_eff is 4.08 against the ~100 a weak-edge portfolio needs; the
44-candidate maximum-power campaign covered 2.787 effective mechanism classes of 20 with ZERO carry
tests in it. More rules on the same OHLCV tape cannot move any of those numbers -- only new
economic mechanisms and new data axes can.

`mechanism_census` already does the hard half. It ranks every untested class by plausibility x
orthogonality x feasibility x depth-deficit, names WHO PAYS, and lists the exact datasets each
would need. What it does NOT do is convert that into work, so the highest-ranked gap on the desk's
single binding constraint has sat as a paragraph in a report. That is the conversion defect (L1.53)
landing on the one axis where it costs the most.

WHAT THIS ADDS. For each gap it asks the only question that decides whether the gap is actionable
today: ARE THE DATASETS IT NEEDS ALREADY REACHABLE? Four states, and NEEDS-A-LOOK is the one that
matters most:

    BUILDABLE-NOW      every dataset is on disk or free-acquirable -- owed COLLECTOR work, with
                       nothing but effort between the desk and a new mechanism class
    NEEDS-A-LOOK       no paywall anywhere; the only thing missing is that NOBODY HAS CHECKED
                       whether a dataset is obtainable. Two minutes with a browser, on the desk's
                       single binding constraint. The cheapest rung there is.
    PARTIALLY-BLOCKED  at least one dataset behind a paywall or a dead route -- the reachable half
                       can still start, and usually should
    BLOCKED            the load-bearing input is unreachable, with the blocker NAMED

THE FOURTH STATE EXISTS BECAUSE THE FIRST VERSION HAD ONLY THREE, and it lumped "behind a paid
vendor" together with "nobody has ever looked". Those owe completely different work -- a hunt that
is expensive and may fail, versus a two-minute check -- and reporting the second as if it were a
wall is how the cheapest available progress on the binding constraint stays invisible. Live: 21
gaps, and the top FIVE are all NEEDS-A-LOOK.

A gap that is BUILDABLE-NOW or NEEDS-A-LOOK and untouched is the most expensive idleness available
to this desk: the constraint is mechanism supply, the mechanism is ranked, the data is free or
one check away, and nobody is collecting it.

NOTHING HERE IS A PROMOTION. It reads the census and the paywall/route ledgers, cross-references
what is on disk, and writes a worklist. It runs no screen, admits nothing to a slot, and moves no
threshold -- a new mechanism still owes the identical Stage-A/Stage-B path as everything else.

    python scripts/report_mechanism_supply.py [--json] [--top N]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

CENSUS = "data/mechanism_census.json"
OUT = "reports/mechanism_supply.json"

#: Phrases in a dataset description that mean "the desk cannot simply go and get this". Matched on
#: the census's own prose, which already states availability in the text it wrote per dataset.
_BLOCKED_MARKERS: tuple[str, ...] = (
    "paid", "subscription", "licence", "license", "vendor", "tardis", "kaiko", "nansen",
    "glassnode", "coin metrics", "cryptoquant", "unpurchasable", "empty", "not recorded",
)
#: Phrases that mean it is reachable without buying anything.
_FREE_MARKERS: tuple[str, ...] = (
    "free", "public", "on disk", "on-disk", "rpc", "github", "api", "docket", "filing",
    "methodology", "governance", "event log", "own recorder", "chain",
)


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _on_disk(root: Path, text: str) -> list[str]:
    """Paths named in a dataset description that ACTUALLY exist. The census names candidate files;
    whether they are present is a fact about this box and is checked rather than assumed."""
    found: list[str] = []
    for hit in re.findall(r"\b(?:data|reports|web)/[\w./-]+", str(text)):
        if (root / hit).exists():
            found.append(hit)
    return sorted(set(found))


def classify(datasets: list[str], root: Path) -> tuple[str, list[str], list[str], list[str]]:
    """(state, reachable, unchecked, blocked). Reads the census's own prose about each dataset.

    THREE FACTS, NOT TWO, and collapsing them cost the worklist its usefulness. The first version
    had only reachable/blocked, so "behind a paid vendor" and "nobody has ever looked" landed in
    the same bucket -- and they owe completely different work. A paywalled dataset owes a
    replacement HUNT, which is expensive and may fail. An UNCHECKED one owes somebody two minutes
    with a browser, which is the cheapest possible action on the desk's single binding constraint
    and was being reported as if it were a wall.

    Conservative where it matters: a dataset naming a paid vendor is BLOCKED even if it also
    mentions a free route, because this desk has been burned by treating "reconstructable in
    principle" as "available". And UNCHECKED never counts toward BUILDABLE-NOW, or the worklist
    fills with work that stalls on contact.
    """
    reachable: list[str] = []
    unchecked: list[str] = []
    blocked: list[str] = []
    for ds in datasets:
        low = str(ds).lower()
        if any(m in low for m in _BLOCKED_MARKERS):
            blocked.append(str(ds)[:200])
        elif any(m in low for m in _FREE_MARKERS) or _on_disk(root, ds):
            reachable.append(str(ds)[:200])
        else:
            unchecked.append(str(ds)[:200])
    if not blocked and not unchecked:
        return "BUILDABLE-NOW", reachable, unchecked, blocked
    if blocked:
        return ("PARTIALLY-BLOCKED" if reachable or unchecked else "BLOCKED",
                reachable, unchecked, blocked)
    # No paywall anywhere -- the ONLY thing between the desk and this mechanism is somebody
    # looking. That is the cheapest rung on the binding constraint and it gets its own state.
    return "NEEDS-A-LOOK", reachable, unchecked, blocked


def run(root: Path | None = None) -> dict[str, Any]:
    base = root or _ROOT
    census = _load(base / CENSUS)
    if not isinstance(census, dict) or not isinstance(census.get("gaps"), list):
        return {"generated_utc": _now(), "status": "BLOCKED",
                "blocker": f"{CENSUS} absent or carries no gap list -- run "
                           "scripts/run_mechanism_census.py first",
                "consequence": ("the desk's single binding constraint (distinct mechanism supply) "
                                "has no ranked worklist, so nothing can be owed against it")}

    rows: list[dict[str, Any]] = []
    for gap in census["gaps"]:
        if not isinstance(gap, dict):
            continue
        req = gap.get("data_required")
        datasets = list(req.get("datasets") or []) if isinstance(req, dict) else []
        state, reachable, unchecked, blocked = classify(datasets, base)
        score = float(gap.get("gap_score") or 0.0)
        feas = float(gap.get("feasibility") or 0.0)
        rows.append({
            "class_id": gap.get("class_id"), "name": gap.get("name"),
            "gap_score": round(score, 4), "feasibility": feas,
            # RANKED BY WHAT IS WORTH DOING TIMES WHAT CAN BE DONE. A superb gap whose data is
            # unreachable is not this week's work, and a trivial gap whose data is free is not
            # either -- the product is the only ordering that respects both.
            "actionable_rank": round(score * feas, 4),
            "state": state, "payer": str(gap.get("payer") or "")[:220],
            "datasets_reachable": reachable, "datasets_unchecked": unchecked,
            "datasets_blocked": blocked,
            "n_datasets": len(datasets),
        })
    rows.sort(key=lambda r: (-float(r["actionable_rank"]), str(r["class_id"])))

    buildable = [r for r in rows if r["state"] == "BUILDABLE-NOW"]
    needs_look = [r for r in rows if r["state"] == "NEEDS-A-LOOK"]
    partial = [r for r in rows if r["state"] == "PARTIALLY-BLOCKED"]
    payload = {
        "generated_utc": _now(), "status": "OK",
        "taxonomy_size": census.get("taxonomy_size"),
        "n_gaps": len(rows),
        "n_buildable_now": len(buildable), "n_needs_a_look": len(needs_look),
        "n_partially_blocked": len(partial),
        "n_blocked": len(rows) - len(buildable) - len(needs_look) - len(partial),
        "cheapest_next_action": (
            [{"class_id": r["class_id"], "actionable_rank": r["actionable_rank"],
              "check": r["datasets_unchecked"][:3]} for r in needs_look[:5]]
            or "no gap is blocked solely on an unchecked dataset"),
        "binding_constraint": ("DISTINCT MECHANISM SUPPLY -- cross-mechanism N_eff 4.08 against "
                               "the ~100 a weak-edge portfolio needs. New economic mechanisms and "
                               "new data axes move this; new rules on the same OHLCV tape cannot."),
        "worklist": rows,
        "authority": ("MEASUREMENT AND CONVERSION ONLY. Runs no screen, admits nothing to a "
                      "forward slot, moves no threshold. A new mechanism owes the identical "
                      "Stage-A/Stage-B path as everything else."),
        "note": ("A gap that is BUILDABLE-NOW and untouched is the most expensive idleness "
                 "available to this desk: the constraint is mechanism supply, the mechanism is "
                 "ranked, the data is free, and nobody is collecting it."),
    }
    (base / OUT).parent.mkdir(parents=True, exist_ok=True)
    (base / OUT).write_text(json.dumps(payload, indent=1) + "\n", "utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--top", type=int, default=8)
    args = ap.parse_args(argv)
    rep = run()
    if args.json:
        print(json.dumps(rep, indent=1))
        return 0
    if rep["status"] == "BLOCKED":
        print(f"mechanism supply: BLOCKED -- {rep['blocker']}")
        return 2
    print(f"mechanism supply: {rep['n_gaps']} ranked gaps over a {rep['taxonomy_size']}-class "
          f"taxonomy -- {rep['n_buildable_now']} BUILDABLE-NOW, "
          f"{rep['n_needs_a_look']} NEEDS-A-LOOK, "
          f"{rep['n_partially_blocked']} partially blocked, {rep['n_blocked']} blocked")
    for r in rep["worklist"][:args.top]:
        print(f"  {r['actionable_rank']:.3f}  {r['state']:18s} {str(r['class_id'])[:36]:36s}"
              f" ({len(r['datasets_reachable'])}/{r['n_datasets']} datasets reachable)")
        if r["datasets_reachable"]:
            print(f"        GET: {r['datasets_reachable'][0][:96]}")
        if r["datasets_unchecked"]:
            print(f"        CHECK:   {r['datasets_unchecked'][0][:96]}")
        if r["datasets_blocked"]:
            print(f"        BLOCKED: {r['datasets_blocked'][0][:96]}")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
