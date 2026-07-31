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
               "libs/autodiscovery/validation.py:capacity_status",
               "scripts/run_promotion_queue.py", "libs/research/promotion_latency.py"],
    "L1.16a": ["negative_knowledge.py", "check_findings_ratchet"],
    "L1.19": ["revalidate_clocks.py", "libs/research/dist_shift.py"],
    "L1.20": ["check_post_gate0_activation", "check_production"],
    "L1.21": ["check_depth_parity", "check_coverage"],
    "L1.22": ["run_intelligence_cycle.py", "check_self_application", "check_self_sufficiency"],
    "L1.23": ["run_deadman_switch.py (Tier-3)", "libs/risk/gate.py", "check_production",
              "scripts/run_drills.py", "libs/risk/capital_events.py",
              # the moat is capital in information form: replicas drilled on every run, disk
              # fuse fails loud ~14 days before the 80% guard would start eating the moat
              "scripts/run_moat_backup.py"],
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
    "L2.8a": ["scripts/check_constitution_core.py", "tests/governance/test_constitution_core.py",
              "data/constitution_core.lock"],
    # L1.21a is a bar on the ORGANS' reasoning, not on an artifact, so its enforcement is the
    # injection path: it is in principal_doctrine.txt, which check_prompt_layer proves reaches
    # every claude invocation and check_universal_doctrine proves no organ omits.
    "L1.21a": ["ops/principal_doctrine.txt", "check_prompt_layer", "check_universal_doctrine"],
    # L1.28 fences the CONSTITUTION's own language: every scope restraint must state its non-timid
    # reading, or an organ reading it defaults to doing less.
    "L1.28": ["scripts/check_timidity_language.py", "tests/governance/test_timidity_fence.py",
              "ops/principal_doctrine.txt"],
    # L1.28a is measured, not asserted: every ceiling reports utilisation or counts as zero.
    "L1.28a": ["scripts/check_utilisation.py", "check_idle_capability", "check_clock_saturation",
               "check_capacity_runway"],
    # L1.28b: conversion hunts 100% daily -- FLATLINE (7d of silence on a non-empty queue) fails.
    "L1.28b": ["scripts/check_conversion.py"],
    # L1.28c: every cadence hunts its own ceiling. The manifest fence requires a decided cadence
    # with evidence per line; brain_seat_throughput measures the resource they all compete for,
    # so "raise the cron" vs "buy a second seat" is settled by measurement.
    "L1.28c": ["scripts/check_scheduler_manifest.py", "scripts/check_utilisation.py"],
    # L1.29: the desk scores its own confidence or its confidence is fiction. The fence fails
    # on ungraded predictions; the shrinkage closes the loop back into sizing/promotion.
    "L1.29": ["scripts/check_calibration.py",
              "libs/self_improvement/forecast_calibration.py"],
    # L1.30: births vs deaths of validated edges -- the number that sets terminal wealth.
    "L1.30": ["scripts/check_replacement_rate.py"],
    # L1.31: two model families hunt the missing capability daily AND one builds it. The organ
    # is the fence: check_organs catches it going quiet, and its artifacts are dated evidence.
    "L1.31": ["scripts/run_capability_hunt.py", "ops/run_capability_hunt.sh", "check_organs"],
    # L1.32: the unknown-unknown organs measured as ONE family -- DARK when any has never
    # produced. L1.33: the GPT seat as standing partner on every one of them.
    "L1.32": ["scripts/check_exploration.py"],
    "L1.33": ["libs/research/second_family.py", "scripts/run_capability_hunt.py"],
    # L1.34: source-class universality reaches the seats through their PROMPTS, so the fence is
    # the prompt-layer wire that proves every brief carries it (same shape as L1.21a).
    "L1.34": ["ops/frontier_en_prompt.txt", "scripts/kimi_hunter.py", "check_prompt_layer",
              "tests/governance/test_source_universality.py"],
    # L1.35: the hunters are the never-finished organ. Fenced by the mandate's presence in every
    # brief, the family-level exploration fence, and the productivity ratchet that catches an
    # organ going quiet whatever reason it gives.
    "L1.35": ["tests/governance/test_source_universality.py", "scripts/check_exploration.py",
              "check_organs", "scripts/check_ratchets.py"],
    # L1.36: families enforced AS families -- complete, fenced per member, reaching every organ
    # via the doctrine, and guarded by a family-level check. A gate, not a report.
    "L1.36": ["scripts/check_law_families.py"],
    # L1.37: the gate itself -- four boundaries (organ spawn, pre-push, CI, hourly cron).
    "L1.37": ["scripts/run_law_gate.py", "deploy/git_hooks/pre-push", "ops/brain_env.sh",
              ".github/workflows/ci.yml"],
    # L1.25a: null streaks throttle nothing -- an organ going quiet is caught by the freshness/
    # productivity wires REGARDLESS of its reason, so "stopped because nothing was working" trips
    # the same fence as "stopped because broken". The pessimism-freeze cannot hide.
    "L1.25a": ["check_organs", "check_stub_deaths", "check_idle_capability",
               "scripts/check_ratchets.py"],
}

# ---------------------------------------------------------------------------------------------
# SECOND DIRECTION: every FENCE claimed by a law (2026-07-30).
#
# The first pass mapped principles -> fences and left 39 of 71 fences governed by nothing. That is
# the failure mode this script's own docstring names -- "a check with no governing principle is
# complexity nobody voted for" -- and it was sitting in the script's own output, unactioned, which
# is precisely the decoration pattern L2.9 exists to kill. So the reverse index is now explicit.
#
# These are appended into _MAP rather than written inline above so the read direction stays clean:
# above answers "what enforces this law", below answers "why does this check exist at all".
_FENCE_OWNERS: dict[str, str] = {
    # --- conversion parity (L1.28b): the repair wire's two halves. check_conversion measures the
    # daily flow (arrival vs disposition, FLATLINE on silence); check_recommendation_rows (§42 X1,
    # built independently by the box the same day) applies per-row carry-over pressure so old
    # rows are seen again. Same law, complementary directions.
    "check_recommendation_rows": "L1.28b",
    # --- capacity (§42 / L1.18a): six fences, one law. Small edges are hunted, filled and RETIRED
    # on arithmetic, never ranked down for being small.
    "check_capacity_hunt": "L1.18a",
    "check_capacity_knobs_are_wired": "L1.18a",
    "check_capacity_governor_reachable": "L1.18a",
    "check_capacity_allocation_honesty": "L1.18a",
    "check_capacity_runway": "L1.18a",
    "check_capacity_single_source": "L1.18a",
    # --- artifact-over-claim (L2.4): a capability exists only if something it wrote is FRESH.
    "check_organs": "L2.4",              # organ never fired / always dies
    "check_stub_deaths": "L2.4",         # runs that died at birth on quota/auth still "ran"
    "check_stale_daemons": "L2.4",       # daemon older than its source = a fix that never shipped
    "check_producer_cadence": "L2.4",    # an inventory-accumulating artifact declares a cadence
    "check_deploy_path": "L2.4",         # code that never reaches the box was never deployed
    # --- forced disposition (L2.3): every finding gets a ruling, and rulings are not allowed to rot.
    "check_findings": "L2.3",
    "check_findings_tracked": "L2.3",
    "check_findings_scope": "L2.3",
    "check_review_risks_tracked": "L2.3",
    "check_decision_ledger_matures": "L2.3",
    # --- execution physics (L1.5): the costs that quietly eat a carry.
    "check_bnb_funded": "L1.5",          # fee-burn discount only applies while BNB is held
    "check_fee_carry_ratio": "L1.5",
    "check_close_retry_loop": "L1.5",    # a carry that cannot close is a churn engine
    # --- survival rails (L1.23): states that read HEALTHY while being terminal.
    "check_book_collapse": "L1.23",
    "check_book_absorbing_state": "L1.23",   # a rail that can never release the book is not safety
    # --- injection + fence integrity (L2.1 / L2.2): the enforcement layer auditing itself.
    "check_constitution": "L2.1",
    "check_universal_doctrine": "L2.1",
    "check_registry_complete": "L2.2",   # an unregistered check is a law believed-but-not-enforced
    "check_artifact_governance": "L2.2",
    "check_ci_scope": "L2.2",            # a CI gate on a hardcoded subset is a map, not a territory
    "check_law_numbers_unique": "L2.8",  # a law number naming two laws breaks amendment itself
    # --- dormancy / reachability (L2.9): built-but-unwired, in three shapes.
    "check_orphan_scripts": "L2.9",
    "check_orphan_modules": "L2.9",
    "check_money_path_wired": "L2.9",    # a money-path module with only a test caller
    # --- discovery duties (L1.8 / L1.9 / L1.11a / L1.24).
    "check_clock_saturation": "L1.8",    # objective-#2 duty: the clock is the scarce resource
    "check_mine_scope": "L1.8",          # a find written somewhere unscanned is outside the law
    "check_source_backlog": "L1.9",      # a catalogue that grows faster than it is verified
    "check_dig_uncommitted": "L1.9",     # VPS disk is not institutional memory
    "check_paid_target_registry": "L1.11a",
    "check_holdings_never_shrink": "L1.24",  # information advantage measured as a holding, not act
    # --- remaining singletons.
    "check_panel": "L1.7",               # adversarial review capability being DOWN is a defect
    "check_memory_hygiene": "L1.17",     # research debt is only debt if it is written and findable
    "check_mine_evidence_base": "L1.6",  # a ratchet calibrated on n=2 is superstition with a JSON
}
for _fence, _pid in _FENCE_OWNERS.items():
    _MAP.setdefault(_pid, []).append(_fence)

# Laws a fence cannot satisfy, each with the reason. Being explicit is the point: an unfenceable law
# recorded as HUMAN-ONLY is a decision; one silently absent from the map is a hole.
_HUMAN_ONLY: dict[str, str] = {
    "L2.8": "the REVIEW is a human judgement (default outcome STABILITY); a fence would either "
            "block legitimate change or rubber-stamp it. Its BOUNDARY is not human-only: L2.8a "
            "hashes the five clauses evolution may never touch (check_constitution_core.py), so "
            "what is unfenced here is the judgement, not the safety margin",
}
_STANDING: dict[str, str] = {
    "L1.0": "ratchet meta-law -- check_ratchets.py enforces the FLOORS across every measured "
            "property, and run_max_push.py enforces the DIRECTION: one ranked queue of everything "
            "not yet at 100%, which never reports done (all-green escalates to "
            "MEASUREMENT-SET-TOO-SMALL). STANDING rather than ENFORCED because the law is a "
            "standing duty on every cycle, not a single pass/fail condition",
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
    # Fail on an unenforced principle, a mapping to a missing artifact, OR an unclaimed fence.
    #
    # That last one is a RATCHET (L1.0), turned on the day the backlog hit zero (2026-07-30). While
    # 39 fences predating this map were unclaimed, failing on them would only have taught the desk
    # to run --report-only. Now that every fence is claimed, a NEW unclaimed fence is a real defect
    # and it is exactly one line of work to fix: name the law it serves in _FENCE_OWNERS. If no law
    # covers it, that is the finding -- either the fence is unvoted complexity, or the constitution
    # is missing a principle the fence already assumes. Both need a decision, not silence.
    return 1 if (m["unenforced"] or m["broken_references"]
                 or m["fences_without_a_principle"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
