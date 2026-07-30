"""CONSTITUTION -> ENFORCEMENT MATRIX -- makes every principle auditable (EXECUTION_QUEUE rank 2).

THE GAP THIS CLOSES. The desk carries 42 constitutional principles (L1.x/L2.x) and 57 mechanical
fences in `scripts/max_audit.py`, and NOTHING mapped one to the other. So two failure directions
were both invisible:

  UNENFORCED PRINCIPLE  -- a law with no fence is prose. It cannot fire, cannot fail a cycle, and
                           degrades silently into decoration. Every defect found on 2026-07-30 was
                           of exactly this shape: a principle everyone agreed with, enforced by
                           nobody (capacity parity was written in L1.18 while a $100k floor ran in
                           the gauntlet; L2.9 activate-the-unused was written while 171 capabilities
                           sat dormant).
  UNJUSTIFIED FENCE     -- a check with no governing principle is complexity nobody voted for. It
                           consumes cycle time and its failures have no authority behind them.

This emits `data/enforcement_matrix.json`:
    principle -> requirement -> fences -> code_paths -> scheduler -> tests -> evidence -> status

STATUS is deliberately blunt: ENFORCED (>=1 fence or a named runtime mechanism) / UNENFORCED /
HUMAN-ONLY (a law only a person can satisfy -- key custody, licence rulings; a fence would be
theatre) / STANDING (a review cadence rather than a check).

IT FAILS THE BUILD on an unenforced principle, because a matrix that merely REPORTS gaps is the
same category of decoration it exists to detect.

Pure stdlib. Run from repo root.
    python scripts/build_enforcement_matrix.py [--json] [--report-only]
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_CONST = _ROOT / "docs/CONSTITUTION.md"
_AUDIT = _ROOT / "scripts/max_audit.py"
_MANIFEST = _ROOT / "ops/crontab.manifest"
_OUT = _ROOT / "data/enforcement_matrix.json"

# principle -> the fences / runtime mechanisms that enforce it. Hand-mapped ONCE because the link
# is semantic (a fence name does not contain its principle id), then kept honest by this script:
# any principle absent from this map with no keyword hit is reported UNENFORCED and fails the run.
_MAP: dict[str, list[str]] = {
    "L1.1": ["check_production", "check_gate_optimality"],
    "L1.2": ["check_directives"],
    "L1.3": ["check_data_utilization", "check_generation"],
    "L1.4": ["run_reality_gap.py", "check_forensics_fresh", "check_carry_funding_measured"],
    "L1.5": ["run_cost_model.py", "check_carry_funding_measured", "run_execution_intel.py"],
    "L1.6": ["libs/autodiscovery/validation.py", "check_welded_gates", "check_gate_optimality",
             "run_mutation.py"],
    "L1.7": ["check_rubberstamp_detector", "check_rubberstamp_enforcement", "deep_review.py"],
    "L1.8": ["check_no_mining_throttle", "check_mining_nonregression", "check_mine_flow"],
    "L1.9": ["check_blind_trigger", "check_interrogation", "check_dig_depth"],
    "L1.10": ["check_mine_conversion", "check_mine_gate"],
    "L1.11": ["moat_audit.py", "check_vendor_replacement", "run_recorder.py"],
    "L1.11a": ["ops/run_frontier_rotation.sh", "kimi_hunter.py"],
    "L1.12": ["check_orphan_code", "check_idle_capability", "libs/self_improvement/dormancy.py"],
    "L1.13": ["check_gap_register_health", "run_execution_intel.py"],
    "L1.14": ["check_directives", "research_erv.py"],
    "L1.15": ["check_self_application"],
    "L1.16": ["mechanism_board.py", "check_gate_optimality"],
    "L1.17": ["negative_knowledge.py", "check_findings_ratchet", "docs/graveyard.md"],
    "L1.18": ["tests/validation/test_capacity_parity.py"],
    "L1.18a": ["tests/validation/test_capacity_parity.py",
               "libs/autodiscovery/validation.py:capacity_status"],
    "L1.16a": ["negative_knowledge.py", "check_findings_ratchet"],
    "L1.19": ["revalidate_clocks.py", "libs/research/dist_shift.py"],
    "L1.20": ["check_post_gate0_activation", "check_production"],
    "L1.21": ["check_depth_parity", "check_coverage"],
    "L1.22": ["run_intelligence_cycle.py", "check_self_application", "check_self_sufficiency"],
    "L1.23": ["run_deadman_switch.py (Tier-3)", "libs/risk/gate.py", "check_production"],
    "L1.24": ["run_intelligence_cycle.py", "check_idle_capability", "check_data_utilization"],
    "L1.25": ["check_welded_gates", "check_gate_optimality", "check_rejection_shadow"],
    "L1.26": ["research_erv.py", "check_directives"],
    "L1.27": ["check_verify_lag", "check_carryover_skipped"],
    "L2.1": ["check_prompt_layer", "ops/principal_doctrine.txt"],
    "L2.2": ["scripts/max_audit.py (all 57 fences)"],
    "L2.3": ["recommendations.py", "check_directives"],
    "L2.4": ["check_rubberstamp_detector", "check_rubberstamp_enforcement"],
    "L2.5": ["blind_spot.py", "check_self_sufficiency"],
    "L2.6": ["run_trade_forensics.py", "check_forensics_fresh", "research_autopsy.py"],
    "L2.7": ["recommendations.py", "check_directives"],
    "L2.9": ["libs/self_improvement/dormancy.py", "run_intelligence_cycle.py",
             "check_idle_capability", "check_orphan_code"],
    "L2.10": ["run_reality_gap.py", "libs/research/dist_shift.py"],
}

# Laws a fence cannot satisfy, each with the reason. Being explicit is the point: an unfenceable law
# recorded as HUMAN-ONLY is a decision; one silently absent from the map is a hole.
_HUMAN_ONLY: dict[str, str] = {
    "L2.8": "constitutional review is a human judgement (default outcome STABILITY); a fence "
            "would either block legitimate change or rubber-stamp it",
}
_STANDING: dict[str, str] = {
    "L1.0": "ratchet meta-law -- enforced by check_ratchets.py across every measured property",
    "L2.0": "enforcement meta-law -- satisfied by the existence of this matrix",
}


def _principles() -> dict[str, str]:
    """principle id -> its first sentence (the requirement), read from the constitution."""
    text = _CONST.read_text("utf-8")
    out: dict[str, str] = {}
    for m in re.finditer(r"^\*\*(L\d+\.\d+[a-z]?)\s+([^*]+)\*\*(.*)$", text, re.MULTILINE):
        pid, title, rest = m.group(1), m.group(2).strip(), m.group(3).strip()
        first = re.split(r"(?<=[.!])\s", rest, maxsplit=1)[0] if rest else ""
        out[pid] = f"{title.rstrip('.')} — {first}".strip(" —")[:400]
    return out


def _fence_names() -> set[str]:
    return set(re.findall(r"^def (check_[a-z_0-9]+)", _AUDIT.read_text("utf-8"), re.MULTILINE))


def _exists(ref: str) -> bool:
    """Does the enforcing artifact actually exist? A mapping to a deleted file is worse than none."""
    bare = ref.split(":")[0].split(" ")[0]
    if bare.startswith("check_"):
        return bare in _fence_names()
    return any(cand.exists() for cand in (_ROOT / bare, _ROOT / "scripts" / bare))


def _scheduled(refs: list[str]) -> list[str]:
    man = _MANIFEST.read_text("utf-8") if _MANIFEST.exists() else ""
    return [r for r in refs if Path(r.split(":")[0].split(" ")[0]).name in man]


def build() -> dict[str, Any]:
    principles, fences = _principles(), _fence_names()
    rows: list[dict[str, Any]] = []
    for pid, requirement in sorted(principles.items()):
        refs = _MAP.get(pid, [])
        live = [r for r in refs if _exists(r)]
        broken = [r for r in refs if r not in live]
        if pid in _HUMAN_ONLY:
            status, note = "HUMAN-ONLY", _HUMAN_ONLY[pid]
        elif pid in _STANDING:
            status, note = "STANDING", _STANDING[pid]
        elif live:
            status, note = "ENFORCED", ""
        else:
            status, note = "UNENFORCED", "no fence or runtime mechanism maps to this principle"
        rows.append({"principle": pid, "requirement": requirement, "status": status,
                     "enforced_by": live, "broken_references": broken,
                     "scheduled": _scheduled(live), "note": note})

    mapped_fences = {r.split(":")[0] for refs in _MAP.values() for r in refs
                     if r.startswith("check_")}
    orphan_fences = sorted(fences - mapped_fences)
    counts: dict[str, int] = {}
    for r in rows:
        counts[str(r["status"])] = counts.get(str(r["status"]), 0) + 1
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L2.0/L2.2 -- a principle with no enforcement is prose; a fence with no principle "
               "is unvoted complexity. Both directions are engineering gaps.",
        "counts": counts, "n_principles": len(principles), "n_fences": len(fences),
        "unenforced": [r["principle"] for r in rows if r["status"] == "UNENFORCED"],
        "broken_references": {r["principle"]: r["broken_references"] for r in rows
                              if r["broken_references"]},
        "fences_without_a_principle": orphan_fences,
        "matrix": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report-only", action="store_true", help="always exit 0")
    args = ap.parse_args()
    m = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(m, indent=2), "utf-8")
    if args.json:
        print(json.dumps(m, indent=2))
    else:
        print(f"enforcement matrix: {m['counts']} over {m['n_principles']} principles / "
              f"{m['n_fences']} fences")
        for pid in m["unenforced"]:
            print(f"  UNENFORCED {pid}")
        for pid, refs in m["broken_references"].items():
            print(f"  BROKEN-REF {pid} -> {refs}")
        n_orph = len(m["fences_without_a_principle"])
        print(f"  fences with no governing principle: {n_orph}"
              + (f" (first 5: {m['fences_without_a_principle'][:5]})" if n_orph else ""))
        print(f"-> {_OUT.relative_to(_ROOT)}")
    if args.report_only:
        return 0
    # Fail on an unenforced principle or a mapping to a missing artifact. Orphan fences are
    # reported but do NOT fail: a fence predating this map is not a defect, it is unmapped work.
    return 1 if (m["unenforced"] or m["broken_references"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
