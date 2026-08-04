"""PROMOTION GATE -- make the barrier into capital an explicit, auditable, fail-closed verdict.

THE GAP. libs/stage15/governance.alpha_governance_gate is the desk's hard barrier: an alpha may
enter promotion ONLY if every one of eight gates passes -- CPCV, PBO, DSR, Reality Check,
economic mechanism, capacity, fragility, walk-forward. It was imported by nothing. Promotion
decisions were therefore assembled implicitly, per screen, from whichever checks that screen
happened to run -- which is exactly how a gate silently becomes optional.

WHY EXPLICIT MATTERS MORE THAN THE CHECKS THEMSELVES. Every individual check already exists
somewhere on this desk. What did not exist was one place that says "these eight, all of them, or
it does not pass" and RECORDS the verdict. A checklist nobody renders is a checklist nobody can
be shown to have skipped. The Two-Stage Discovery Law gives promotion authority to forward
evidence alone; this makes the screen-side prerequisite legible so a promotion can be audited
after the fact.

FAIL-CLOSED, AND UNKNOWN IS NOT PASS. Any gate whose evidence is missing counts as FAILED, never
as passed-by-default. That is the single most important property here: the fail-open guard --
where an absent check reads as an approval -- is the defect class this codebase's own auditor
prompt lists FIRST in its measured history ("a safety gate whose default/ambiguous branch ALLOWS
the action"). An alpha that has not been checked has not passed.

ECONOMIC MECHANISM IS NOT A FORMALITY. The desk's graveyard records four FAMILY KILLS reached by
mechanism reasoning, and its doctrine is "NOT INDICATORS. MECHANISM." A statistically clean alpha
with no causal story is a fitted curve that has not been caught yet.

Reports only -- it renders and records the verdict; it does not itself promote anything.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from libs.stage15.governance import alpha_governance_gate  # noqa: E402

OUT = ROOT / "data/promotion_gate.json"
CANDIDATES = ROOT / "data/gauntlet_survivors.json"

# The eight gates, with the evidence key each is read from. Order matches the governance
# function's own signature so the mapping stays auditable against the source.
_GATES = (
    ("cpcv_passed", "cpcv"),
    ("pbo_acceptable", "pbo"),
    ("dsr_passed", "dsr"),
    ("reality_check_passed", "reality_check"),
    ("economic_mechanism_present", "mechanism"),
    ("capacity_acceptable", "capacity"),
    ("fragility_acceptable", "fragility"),
    ("walk_forward_passed", "walk_forward"),
)


def evidence_to_gates(ev: dict[str, Any]) -> dict[str, bool]:
    """Map a candidate's evidence dict onto the eight booleans. UNKNOWN -> False, always.

    A missing key is not a neutral outcome. Treating it as passed would let an alpha through on
    the strength of checks nobody ran, which is the fail-open class. Explicit False on absence.
    """
    return {arg: bool(ev.get(key) is True) for arg, key in _GATES}


def judge(name: str, ev: dict[str, Any]) -> dict[str, Any]:
    gates = evidence_to_gates(ev)
    verdict = alpha_governance_gate(**gates)
    d = json.loads(verdict.model_dump_json())
    missing = [key for arg, key in _GATES if key not in ev]
    d["candidate"] = name
    d["missing_evidence"] = missing
    if missing:
        d["note"] = (f"{len(missing)} gate(s) had NO evidence and were counted as FAILED: "
                     f"{', '.join(missing)}. Unchecked is not passed.")
    return d


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        cases = {
            "all_pass": dict.fromkeys([k for _, k in _GATES], True),
            "no_mechanism": {**dict.fromkeys([k for _, k in _GATES], True), "mechanism": False},
            "unchecked_capacity": {k: True for _, k in _GATES if k != "capacity"},
        }
        print("=== PROMOTION GATE (self-test) ===")
        for name, ev in cases.items():
            d = judge(name, ev)
            print(f"  {name:<20} accepted={d['accepted']!s:<6} "
                  f"reasons={d['rejected_reasons'] or '-'}")
        assert judge("a", cases["all_pass"])["accepted"] is True
        assert judge("b", cases["no_mechanism"])["accepted"] is False
        # the critical one: a gate with NO evidence must not pass by default
        assert judge("c", cases["unchecked_capacity"])["accepted"] is False
        print("  fail-closed confirmed: an UNCHECKED gate rejects, it does not pass by default")
        return

    try:
        raw = json.loads(CANDIDATES.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        print(f"promotion-gate: {CANDIDATES.relative_to(ROOT)} unavailable -- no candidates")
        return
    cands = raw if isinstance(raw, dict) else {}
    print("=== PROMOTION GATE ===")
    if not cands:
        print("  no screen survivors awaiting the gate")
        return

    rows = [judge(n, ev if isinstance(ev, dict) else {}) for n, ev in sorted(cands.items())]
    for d in rows:
        state = "ACCEPT" if d["accepted"] else "REJECT"
        print(f"  {d['candidate']:<28} {state}")
        for r in d["rejected_reasons"][:4]:
            print(f"      {r}")
    n_ok = sum(1 for d in rows if d["accepted"])
    print(f"\n  {n_ok}/{len(rows)} cleared all eight gates")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"ran": datetime.now(tz=UTC).isoformat(), "verdicts": rows},
                              indent=1), "utf-8")
    print(f"  -> {OUT.relative_to(ROOT)}")
    print("  Screen-side prerequisite only. Promotion authority remains with pre-registered")
    print("  FORWARD evidence under the Two-Stage Discovery Law.")


if __name__ == "__main__":
    main()
