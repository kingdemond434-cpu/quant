"""TIER6_CLOSURE.json and .md -- mandate §159, and the three claims it is allowed to make.

THE MANDATE DEFINES EXACTLY WHEN EACH SENTENCE MAY BE WRITTEN, and the point of computing them
rather than writing them is that a person cannot talk themselves into one:

    ARCHITECTURAL COVERAGE = 100%   every capability at least legitimately CODED + WIRED +
                                    scheduled or declared event-driven
    OPERATIONAL COVERAGE  = 100%    every required organ RUNNING
    MEASUREMENT COVERAGE  = 100%    every decision-affecting capability has a valid measurement
                                    protocol and enough evidence where data availability permits

and, in the mandate's own words, it "may never fabricate PROVEN status simply because live time
has not elapsed yet". So a capability waiting on the market to supply observations reports
MEASURING, which is an honest state, and is never counted toward PROVEN.

THE THREE ARE INDEPENDENT AND THE ORDER MATTERS. Architectural coverage can be 100% while
operational is 40%, because scheduling something is cheap and running it is not. Publishing one
number for "completion" would let the cheap one carry the expensive one -- exactly how a desk
comes to believe it has a capability that has never produced anything.

    python blueprint/closure_report.py --write
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
# THIS PACKAGE'S DIRECTORY GOES FIRST, and that is not cosmetic: `scripts/dependency_graph.py`
# already exists and shadowed `blueprint/dependency_graph.py` when scripts/ sorted earlier --
# closure_report imported the wrong module and died on a missing name. Two files with one module
# name is a fact of this tree; the fix is to be explicit about which one this package means.
_HERE = str(Path(__file__).resolve().parent)
for _p in (str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.append(_p)
if _HERE in sys.path:
    sys.path.remove(_HERE)
sys.path.insert(0, _HERE)

OUT_JSON = BASE / "reports" / "TIER6_CLOSURE.json"
OUT_MD = BASE / "reports" / "TIER6_CLOSURE.md"

ARCHITECTURAL_OK = ("SCHEDULED", "RUNNING", "DECISION_AFFECTING", "MEASURED", "PROVEN")
OPERATIONAL_OK = ("RUNNING", "DECISION_AFFECTING", "MEASURED", "PROVEN")
MEASUREMENT_OK = ("MEASURED", "PROVEN")


def closure() -> dict[str, Any]:
    from coverage import registry
    from dependency_graph import graph
    from rent import rent

    reg, g, r = registry(), graph(), rent()
    caps = reg["capabilities"]
    n = len(caps) or 1

    arch = sum(1 for c in caps if c["status"] in ARCHITECTURAL_OK)
    oper = sum(1 for c in caps if c["status"] in OPERATIONAL_OK)
    deciding = [c for c in caps if c["status"] in ("DECISION_AFFECTING", "MEASURED", "PROVEN")]
    meas = sum(1 for c in caps if c["status"] in MEASUREMENT_OK)

    rows = []
    rent_by_id = {x["id"]: x for x in r["capabilities"]}
    chain_by_id = {x["id"]: x for x in g["chains"]}
    for c in caps:
        ch, rn = chain_by_id.get(c["id"], {}), rent_by_id.get(c["id"], {})
        rows.append({
            "id": c["id"], "name": c["name"], "category": c["category"],
            "status": c["status"],
            "code": c["producer"], "wiring": c["consumers"][:4],
            "scheduler": c["scheduler"],
            "decision_path": ch.get("first_broken_link") or "complete",
            "measurement": rn.get("metric") or "",
            "rent": rn.get("rent_kind") or "UNPRICED",
            "blockers": c["blockers"][:3],
            "evidence": {"links_ok": ch.get("links_ok"), "links_total": ch.get("links_total")},
        })

    return {
        "generated_at": reg["generated_at"], "git_sha": reg["git_sha"],
        "total_capabilities": len(caps),
        "architectural_coverage_pct": round(100.0 * arch / n, 1),
        "operational_coverage_pct": round(100.0 * oper / n, 1),
        "measurement_coverage_pct": round(100.0 * meas / max(len(deciding), 1), 1)
        if deciding else 0.0,
        "declarations": {
            "ARCHITECTURAL COVERAGE = 100%": arch == len(caps),
            "OPERATIONAL COVERAGE = 100%": oper == len(caps),
            # THE RENT CLAUSE IS LOAD-BEARING AND ITS ABSENCE MADE THIS DECLARATION VACUOUS.
            # The first version asked only `meas == len(deciding)`. With nothing at
            # DECISION_AFFECTING, `deciding` was the 7 PROVEN rows and `meas` was the same 7, so
            # the test compared a set with itself and printed EARNED -- while `rent.py` was
            # simultaneously reporting three of those very capabilities (P64, P69, A6) as
            # decision-affecting and UNPRICED. A partition that cannot fail carries no
            # information (L1.63), and this one asserted the desk's measurement discipline was
            # complete at the exact moment it was not.
            #
            # §159 requires a valid measurement protocol AND enough evidence; §136 says an
            # unpriced decision-affecting module must not keep its authority. So the claim now
            # requires both, and `owing_rent` is the thing that falsifies it.
            "MEASUREMENT COVERAGE = 100%": (bool(deciding) and meas == len(deciding)
                                            and not r["owing"]),
        },
        "measurement_denominator": len(deciding),
        "measurement_note": (
            f"{len(deciding)} of {len(caps)} capabilities have reached a decision-affecting rung; "
            f"the measurement claim is about THOSE, and is refused while any of them is unpriced. "
            f"A high percentage over a small denominator is not coverage."),
        "by_status": reg["by_status"],
        "chains_complete": g["chains_complete"],
        "rent_by_kind": r["by_kind"],
        "owing_rent": r["owing"],
        "capabilities": rows,
        "law": ("Each declaration is COMPUTED. PROVEN is never granted because live time has not "
                "elapsed; a capability waiting on observations reports MEASURING, which is honest, "
                "and does not count toward it. The three coverages are published separately so a "
                "cheap one cannot carry an expensive one."),
    }


def to_markdown(rep: dict[str, Any]) -> str:
    lines = [
        "# Tier-6+ closure report",
        "",
        f"`{rep['git_sha'] or 'no sha'}` — {rep['generated_at']}",
        "",
        "## The three declarations",
        "",
        "| Claim | Earned | Coverage |",
        "|---|---|---|",
    ]
    for claim, ok in rep["declarations"].items():
        pct = (rep["architectural_coverage_pct"] if "ARCHITECTURAL" in claim
               else rep["operational_coverage_pct"] if "OPERATIONAL" in claim
               else rep["measurement_coverage_pct"])
        lines.append(f"| {claim} | {'**YES**' if ok else 'no'} | {pct}% |")
    lines += [
        "",
        "Each is computed, never asserted. A capability waiting on the market to supply",
        "observations reports MEASURING and does not count toward PROVEN.",
        "",
        "## Status distribution",
        "",
        "| Rung | Count |",
        "|---|---|",
    ]
    for s, c in rep["by_status"].items():
        lines.append(f"| {s} | {c} |")
    lines += [
        "",
        f"Chains complete end to end: **{rep['chains_complete']} / {rep['total_capabilities']}**",
        "",
        "## Rent",
        "",
        "| Kind | Count |",
        "|---|---|",
    ]
    for k, c in sorted(rep["rent_by_kind"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {k} | {c} |")
    if rep["owing_rent"]:
        lines += ["", "Decision-affecting and unpriced (§136 says these must not keep authority):",
                  "", "  " + ", ".join(rep["owing_rent"][:20])]
    lines += ["", "## Capabilities", "",
              "| ID | Status | Producer | Chain | Rent |", "|---|---|---|---|---|"]
    for c in rep["capabilities"]:
        lines.append(f"| {c['id']} | {c['status']} | `{c['code'] or '—'}` | "
                     f"{c['decision_path']} | {c['rent']} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    rep = closure()
    if args.write:
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(rep, indent=2, default=str), encoding="utf-8")
        OUT_MD.write_text(to_markdown(rep), encoding="utf-8")
        print(f"{OUT_JSON}\n{OUT_MD}")
    if args.json:
        print(json.dumps(rep, indent=2, default=str))
        return 0
    print(f"Tier-6 closure @ {rep['git_sha'] or 'no sha'}")
    print(f"  architectural {rep['architectural_coverage_pct']:5.1f}%")
    print(f"  operational   {rep['operational_coverage_pct']:5.1f}%")
    print(f"  measurement   {rep['measurement_coverage_pct']:5.1f}%")
    for claim, ok in rep["declarations"].items():
        print(f"  {'EARNED ' if ok else 'not yet'}  {claim}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
