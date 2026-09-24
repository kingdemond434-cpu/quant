#!/usr/bin/env python3
"""EVERY FAMILY A PRODUCER MINTS, AND WHETHER ANYTHING CAN EVALUATE IT.

THE DEFECT THIS EXISTS FOR, measured 2026-09-24 on the build box.

`pack_cells.emit_world` mints cells under the family name `regional_information`. That name is in
NEITHER family registry -- not `mt5desk.families.family_<name>`, not
`mt5desk.families_orthogonal.ORTHOGONAL_FAMILIES` -- which are the only two things
`miner_candidate_compiler._registered_family` consults. So every cell it produces exits as
NEEDS_EXACT_RULE_EXTRACTION and can never reach a docket, a gate or a verdict.

    6,336 cells        every one status='queued', judged_at NULL on all of them
    JUDGE_COVERAGE.json ranks it #1 by value: "unjudged": 960, "judged_total": 0

It is the third-largest family in the registry and the single largest unexecutable population on
the desk. Two claims in the record are WRONG and this fence is partly here to stop the next one:
commit a24a8918eaf's message and `families_orthogonal.py:2197` both state that
`regional_information` "is not minted either". It is, 6,336 times, and both statements were
written by reading `desks/mt5/data/alpha_registry.sqlite`, which is 0 bytes, instead of
`data/alpha_registry.sqlite`, which is 203 MB. A measurement taken against an empty file reads
like a clean result and is how an unjudgeable population stayed invisible.

WHY THIS IS A FENCE AND NOT A FIX, AND THE EVIDENCE THAT CLOSED BOTH BRANCHES. The honest
resolutions were to give the name a real rule derived from what its cells name, or to stop
minting under it. Both were measured and both are shut today:

  A RULE. `exogenous_conditioner` was registerable an hour earlier because its cells name a lake
  series, a column and a transform -- literally the generator's kwargs. `regional_information`
  cells carry `{source, region, country, kind}` and nothing else: `required_data` empty on
  6,336 of 6,336, `exact_rules` empty on 6,336 of 6,336. Its `source` is a CRAWLER GROUND, whose
  documents live in the `claims` table. Measured there:
      - 2 of its 270 grounds have a `data/lake/series/<id>.parquet` at all;
      - 3 of 6,336 cells name a ground with even TWO distinct parseable `knowable_at` stamps,
        and ZERO name one with ten. The column is populated on 3,737 of 3,737 claims and its
        VALUES are the literal string "UNMEASURED", or "2026", or "1300".
  There is no series and no point-in-time clock to build one from. A family written on that reads
  a constant, and the gauntlet would judge noise with the desk's own name on it.

  STOP MINTING. `pack_cells`'s world lane is, in its own words, "the ONLY lane that mints a cell
  carrying a region". Gating it would take twelve of the thirteen regions' cell counts toward zero
  and drive the `REGION_RATCHET` high-waters DOWN, which L1.50 forbids and which would destroy
  the regional coverage the desk spent the week building.

So the defect is REAL, both obvious repairs are worse than the defect, and the remaining honest
act is to MEASURE it, name it, and refuse to let it grow. Which is what this does.

THE RULE IT ENFORCES. The unjudgeable population may SHRINK and may not GROW. The high-water is
recorded in the report itself, exactly like the coverage floors, so the fence is actionable rather
than permanently red -- a wall that is red about something nobody can fix this hour trains the
desk to stop reading it (L1.43), and then it is worth less than nothing on the day it fires on
something real.

    python scripts/check_family_evaluability.py          # verify (rc=1 when the population grew)
    python scripts/check_family_evaluability.py --json
"""
from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "desks" / "mt5" / "reports" / "FAMILY_EVALUABILITY.json"

#: A `family` column value that is a formula, not a name. Measured: 55 such values across 230
#: cells (`"(sign(diff(close, 48)) * z(range, 240))"`). They are a DIFFERENT defect -- a producer
#: writing an expression where a family belongs -- and are counted apart so the two never hide
#: inside one number.
_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


def registered() -> set[str]:
    """The union of the two registries `miner_candidate_compiler._registered_family` consults."""
    names: set[str] = set()
    for p in (ROOT / "desks" / "mt5", ROOT):
        sp = str(p)
        if sp not in sys.path:
            sys.path.insert(0, sp)
    try:
        families = importlib.import_module("mt5desk.families")
        orthogonal = importlib.import_module("mt5desk.families_orthogonal")
    except Exception:              # an unimportable registry is UNMEASURED, never zero
        # NOT JUST ImportError. These two modules pull numpy and pandas in at import, and a fresh
        # checkout or a CI image without them raises something else entirely. An empty set here
        # would make EVERY minted family look unevaluable and turn this fence into a 90-name
        # false alarm, which is worse than the defect it watches -- so `survey` refuses to read an
        # empty result as a measurement.
        return names
    names |= {a[len("family_"):] for a in dir(families)
              if a.startswith("family_") and callable(getattr(families, a, None))}
    names |= set(getattr(orthogonal, "ORTHOGONAL_FAMILIES", {}) or {})
    return names


def minted() -> tuple[dict[str, int], str]:
    """{family: cells} over the registry the compiler actually reads, and the db it came from."""
    from libs.moat.registry import connect
    conn = connect()
    try:
        rows = list(conn.execute(
            "SELECT family, COUNT(*) FROM research_candidates GROUP BY family"))
    finally:
        conn.close()
    return ({str(f or ""): int(n) for f, n in rows}, "libs.moat.registry.connect()")


def survey() -> dict[str, Any]:
    reg = registered()
    if not reg:
        # AN EMPTY REGISTRY IS NOT "NOTHING IS REGISTERED". It is a registry this host could not
        # import, and taking it at face value would mark all 90 minted names unevaluable -- a
        # fence that is loudest exactly where it knows least (L1.28a).
        return {"status": "UNMEASURED", "at": datetime.now(tz=UTC).isoformat(),
                "why": "neither family registry could be imported on this host, so 'registered' "
                       "is unknown, not empty; UNMEASURED is a verdict, never a pass (L1.28a)",
                "n_registered": 0}
    try:
        mint, source = minted()
    except Exception as exc:                        # reported as UNMEASURED, never raised
        return {"status": "UNMEASURED", "at": datetime.now(tz=UTC).isoformat(),
                "why": f"the candidate registry could not be read ({type(exc).__name__}: {exc}); "
                       "UNMEASURED is a verdict, never a pass (L1.28a)",
                "registered": sorted(reg), "n_registered": len(reg)}
    named = {f: n for f, n in mint.items() if _NAME.match(f)}
    unnamed = {f: n for f, n in mint.items() if f and not _NAME.match(f)}
    gap = {f: n for f, n in named.items() if f not in reg}
    dead = sorted(f for f in reg if f not in named)
    return {"status": "MEASURED", "at": datetime.now(tz=UTC).isoformat(), "source": source,
            "n_registered": len(reg), "n_minted_names": len(named),
            "unevaluable_families": len(gap),
            "unevaluable_cells": sum(gap.values()),
            "unevaluable": dict(sorted(gap.items(), key=lambda kv: -kv[1])),
            "expression_shaped_family_values": {"families": len(unnamed),
                                                "cells": sum(unnamed.values())},
            "registered_never_minted": dead,
            "rule": "a family a producer mints and no registry implements can never be judged; "
                    "that population may shrink and may never grow"}


def _prior() -> dict[str, Any]:
    try:
        doc = json.loads(REPORT.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def check() -> tuple[list[str], dict[str, Any]]:
    now = survey()
    prior = _prior()
    if now["status"] != "MEASURED":
        now["high_water_cells"] = prior.get("high_water_cells")
        return [], now
    # THE RATCHET, IN THE REPORT ITSELF. A prior run's high-water is the floor; the first run
    # records it and passes, naming the number rather than pretending it found nothing.
    was = prior.get("high_water_cells")
    hw = int(was) if isinstance(was, int) else int(now["unevaluable_cells"])
    findings: list[str] = []
    if int(now["unevaluable_cells"]) > hw:
        worst = next(iter(now["unevaluable"].items()), ("none", 0))
        findings.append(
            f"the unjudgeable population GREW: {hw} -> {now['unevaluable_cells']} cell(s) in "
            f"{now['unevaluable_families']} family name(s) that no registry implements. Largest: "
            f"{worst[0]!r} at {worst[1]} cell(s). Register a rule for it or stop minting under "
            "the name -- a cell no judge can reach is a trial the desk paid for and cannot cash "
            "(L1.49)")
    now["high_water_cells"] = min(hw, int(now["unevaluable_cells"]))
    now["baseline_recorded"] = not isinstance(was, int)
    return findings, now


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    findings, doc = check()
    doc["findings"] = findings
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1), "utf-8")
    if a.json:
        print(json.dumps(doc, indent=1))
    else:
        print(f"family evaluability: {'OK' if not findings else f'{len(findings)} finding(s)'} "
              f"[{doc['status']}]")
        if doc["status"] == "MEASURED":
            print(f"  registered {doc['n_registered']}  minted names {doc['n_minted_names']}  "
                  f"UNEVALUABLE {doc['unevaluable_families']} name(s) / "
                  f"{doc['unevaluable_cells']} cell(s)  high-water {doc['high_water_cells']}")
            for fam, n in list(doc["unevaluable"].items())[:6]:
                print(f"    {fam:34s} {n:7d} cell(s) no registry implements")
        else:
            print(f"  {doc['why']}")
        for f in findings:
            print(f"  FINDING {f}")
    print(f"  -> {REPORT}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
