#!/usr/bin/env python3
"""CI fence for the blueprint (mandate §4): fail when a capability's claim outruns its evidence.

WHAT A FENCE IS FOR, AND WHAT THIS ONE REFUSES TO DO. Every condition below is a way for the desk
to believe it has a capability it does not have. None of them is a style rule, and none can be
satisfied by writing a file: the registry derives status from imports, scheduler surfaces,
artifacts, the capability graph and MODULE_RENT, so the only way to clear a breach here is to
actually wire, schedule, run or price the thing.

THE HOST DISTINCTION IS LOAD-BEARING (§159's three coverage levels). ARCHITECTURAL conditions --
does the code exist, is it imported, is it scheduled -- are answerable on any checkout and are
ENFORCED everywhere, including CI. OPERATIONAL conditions -- has the artifact been produced, does
the capability graph see a decision, is there a rent line -- can only be answered where the desk
actually runs; on a bare CI checkout every one of them answers "no" for honest reasons, and
failing the build on that would train everybody to ignore this fence (L1.37: a detector that is
always red is one everybody scrolls past). So they are REPORTED everywhere and ENFORCED only with
--operational, which the box and the VPS pass and CI does not.

    python scripts/check_blueprint_coverage.py                  # architectural, CI-safe
    python scripts/check_blueprint_coverage.py --operational    # everything, on a live host
    python scripts/check_blueprint_coverage.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "scripts"), str(ROOT / "desks" / "mt5" / "blueprint")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: Rungs at which a capability is claimed to affect money. At or above these, the mandate's
#: stricter conditions apply: §4 forbids capital authority claimed without measurement.
CAPITAL_STAGES = ("DECISION_AFFECTING", "MEASURED", "PROVEN")


def _findings(reg: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    """(architectural, operational) breaches -- separated by what a bare checkout can know."""
    arch: list[dict] = []
    oper: list[dict] = []
    for cap in reg["capabilities"]:
        cid, status = cap["id"], cap["status"]

        # ---- ARCHITECTURAL: answerable from the tree alone -----------------------------------
        if status == "MISSING":
            arch.append({"id": cid, "rule": "MISSING",
                         "why": "the mandate requires this and no owner module exists"})
        elif status == "CODED":
            arch.append({"id": cid, "rule": "CODED_ONLY",
                         "why": "code exists and no production module imports it -- a capability "
                                "nothing can reach is not a capability"})
        elif status == "WIRED":
            arch.append({"id": cid, "rule": "UNSCHEDULED",
                         "why": "imported but no scheduler surface runs it; if it is genuinely "
                                "event-driven, say so in the registry rather than leaving it here"})
        if cap["artifacts"] and not cap["consumers"]:
            arch.append({"id": cid, "rule": "SILENT_ARTIFACT",
                         "why": f"{cap['artifacts'][0]} is produced and nothing reads it -- the "
                                f"producer succeeds into a place no consumer looks"})
        if status in CAPITAL_STAGES and not cap["producer"]:
            arch.append({"id": cid, "rule": "AUTHORITY_WITHOUT_PRODUCER",
                         "why": "claims to affect decisions with no module behind it"})

        # ---- OPERATIONAL: only a live host can answer these ----------------------------------
        if status in CAPITAL_STAGES and cap["rent_status"] != "PRICED":
            oper.append({"id": cid, "rule": "AUTHORITY_WITHOUT_MEASUREMENT",
                         "why": "decision-affecting with no MODULE_RENT line pricing it"})
        if status == "SCHEDULED":
            oper.append({"id": cid, "rule": "NO_ARTIFACT_YET",
                         "why": "scheduled, but its artifact has never appeared on this host"})
    return arch, oper


def _lineage() -> list[dict]:
    """§4's last condition: the running release must be able to name its own upstream."""
    try:
        ident = json.loads((ROOT / "desks" / "mt5" / "data"
                            / "release_identity.json").read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return [{"id": "P0.1", "rule": "NO_LINEAGE",
                 "why": f"release_identity.json unreadable ({type(exc).__name__}) -- the release "
                        f"cannot identify its upstream, so no capital authority is licensed"}]
    missing = [k for k in ("git_sha", "release_id") if not ident.get(k)]
    return [{"id": "P0.1", "rule": "NO_LINEAGE",
             "why": f"release identity carries no {', '.join(missing)}"}] if missing else []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--operational", action="store_true",
                    help="also enforce the rungs only a live host can answer")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    from coverage import registry                  # the enriched view over the one judge
    reg = registry()
    arch, oper = _findings(reg)
    lineage = _lineage()
    if args.operational:
        oper += lineage

    enforced = arch + (oper if args.operational else [])
    report = {
        "at": reg["generated_at"], "git_sha": reg["git_sha"],
        "total_capabilities": reg["total"], "by_status": reg["by_status"],
        "architectural_breaches": arch,
        "operational_findings": oper,
        "enforced": len(enforced),
        "mode": "operational" if args.operational else "architectural",
        "problems_from_auditor": reg.get("problems", []),
        "status": "BREACH" if (enforced or reg.get("problems")) else "PASS",
    }
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(f"blueprint coverage @ {reg['git_sha'] or 'no sha'} "
              f"({report['mode']}) -- {reg['total']} capabilities")
        for s, n in reg["by_status"].items():
            print(f"    {s:20s} {n:4d}")
        for label, rows in (("ARCHITECTURAL", arch), ("OPERATIONAL", oper)):
            print(f"\n  {label}: {len(rows)} finding(s)")
            seen: dict[str, int] = {}
            for r in rows:
                seen[r["rule"]] = seen.get(r["rule"], 0) + 1
            for rule, n in sorted(seen.items(), key=lambda kv: -kv[1]):
                sample = next(r for r in rows if r["rule"] == rule)
                print(f"    {rule:30s} {n:4d}   e.g. {sample['id']}: {sample['why'][:70]}")
        for p in reg.get("problems", []):
            print(f"\n  AUDITOR PROBLEM: {p}")
        print(f"\n  {report['status']}")
    # The auditor's own problems (the flat 20% floor, MEASURED without rent) are ALWAYS fatal:
    # they are the principal's fixed policy and the mandate's measurement law, and neither
    # depends on which host is asking.
    return 1 if (enforced or reg.get("problems")) else 0


if __name__ == "__main__":
    sys.exit(main())
