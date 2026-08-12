#!/usr/bin/env python3
"""BUILD STANDARD (L1.41) -- nothing enters this desk below the standard, so timid or half-wired
work never has to be caught later.

PRINCIPAL ORDER (2026-07-31): *"everything ever built and implemented in quant must be done with
all the principles enforced -- anti-timidity, max aggression, all families -- which stops the
problem of things ending up timid, not following things, not at ceiling, noticed later, from
growing in the first place."*

WHY A BUILD-BOUNDARY FENCE AND NOT ANOTHER AUDIT. Every other fence here is a DETECTOR: it finds
the built-never-wired organ, the unmeasured-reports-OK check, the cadence nobody decided -- after
they exist, often days later, by which time the desk has been quietly running on them. This one
runs at the moment of creation and refuses entry. The evidence it is needed is this very
session: EVERY fence built on 2026-07-31 initially shipped with at least one standard violation
(check_calibration reported OK on zero forecasts; check_replacement_rate published a phantom-key
zero as DYING; check_change_window blocked pre-launch). All three were caught by hand. Hand is
not a mechanism.

THE FIVE CONDITIONS, each a law this desk already carries:
  1. REFUSAL PATH (L1.28a)  -- the organ must have a way to say UNMEASURED / REFUSED / BLOCKED /
     NO-DATA. An organ with no vocabulary for "I could not measure" will report OK on absent
     input, which is how an all-green board hides an empty one.
  2. TESTED (L2.2)          -- a test file must reference it. Untested wiring is wiring that
     silently rots the first time something around it moves.
  3. SCHEDULED OR EXEMPT (L1.28c) -- either a manifest line, or an explicit exemption recorded
     below with a reason. Built-never-scheduled is the desk's most expensive recurring defect.
  4. LAW-MAPPED (L2.0)      -- named in the enforcement matrix, so the check has authority
     behind its failures rather than being complexity nobody voted for.
  5. NO SILENT SWALLOW (L2.4) -- a bare `except: pass` in an organ turns a failure into a
     success signal for every caller downstream.
  6. LAWFUL ENTRY (L1.42)   -- the organ calls libs.ops.lawful.guard() at start, so it cannot
     run under a tampered core or a doctrine stripped of a law family. 60 manifest lines
     bypassed every gate before this condition existed.

SCOPE, deliberately narrow so the fence stays credible: only NEW-STANDARD organs (those declared
in _GOVERNED). The desk's older scripts predate the standard and retrofitting them wholesale
would produce a wall of noise nobody reads -- the honest move is to hold the line going forward
and migrate deliberately, which check_orphan_code and the max_audit fences already push on.

    python scripts/check_build_standard.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent

#: Organs built to the standard. EVERY new organ joins this list in the same commit that creates
#: it -- that is the whole mechanism. Adding a file here and failing the checks is a red build.
_GOVERNED: tuple[str, ...] = (
    "check_conversion.py", "check_calibration.py", "check_replacement_rate.py",
    "check_exploration.py", "check_law_families.py", "check_change_window.py",
    "run_law_gate.py", "run_moat_backup.py", "run_capability_hunt.py",
    "screen_funding_spread.py", "screen_collateral_allocation.py",
    "check_build_standard.py",                              # this fence holds itself to it
    "check_input_provenance.py",                            # L1.55 transitive freshness
    "check_denominators.py",                                # L1.57 the denominator of a verdict
    "check_denominator_attrition.py",                       # L1.60 what that denominator LOST
    "check_citation_integrity.py",                          # R0369 can the proof-of-work be cashed
    "check_birth_properties.py",                            # §36/L2.9 born with its properties
    "check_capital_basis.py",                               # R0287 return-denominator invariant
    "collect_unlock_calendar.py",                           # R0288 point-in-time unlock calendar
    "check_fence_yield.py",
    "ship_restart.py",                                      # the actuator for stale-code daemons
    "run_stale_daemon_repair.py",                           # detect->repair loop closed (L1.28b)
    "derive_walcl_clock.py",                                # R0031 forward clock (2026-07-31)
    "run_llm_trader.py",
    "collect_announcements.py",
    "run_upbit_snapshot.py",                                # R0303 purge-proof candle archive
    "run_conviction_trader.py",
    "resolve_paper_book.py",
    "build_chart_context.py",
    "check_sizing_derivation.py",
    "check_mechanism_attribution.py",
    "run_trade_review.py",
    "screen_copytrading.py",
    "run_sleeve_allocator.py",
    "run_calibration_probe.py",
    "check_return_targeting.py",
    "check_organ_liveness.py",
    "check_freshness.py",                                   # L1.44 fence (capability hunt s5)
    "check_excitation.py",                                  # L1.45 fence (capability hunt s4)
    "check_clock_provenance.py",                            # L1.46 fence (capability hunt s0)
    "check_funding_capture.py",                             # L1.47 fence (capability hunt s1)
    "check_idle_cost.py",                                   # L1.51 fence (capability hunt s1)
    "run_cost_identification.py",                           # L1.45 producer (capability hunt s4)
    "fit_print_impact.py",                                  # L1.45 third cost basis (hunt s1)
    "check_free_roster.py",                                 # R0344 degraded-fallback canary
    "screen_carry_basis_path.py",                           # R0206 carry attribution (2026-07-31)
    "check_promotion_gate.py",
    "run_discretionary_max.py",
    "run_discretionary_hunt.py",
    "run_cost_hunt.py",
    "run_strategy_coverage.py",
    "check_strategy_breadth.py",
    "run_principal_benchmark.py",
    "run_organ_er.py",
    "check_enforcement_execution.py",       # L1.43 execution-vs-existence (capability hunt s3)
    "check_campaign_retention.py",          # R0270 L1.0 campaign observation-retention ratchet
    "build_event_calendar.py",              # R0276 scheduled-event calendar the guard reads
    "check_doctrine_diff.py",               # R0093: doctrine order -> blind-spot row (L2.5)
    "run_paper_sleeve_spawner.py",          # R0102 paper-sleeve auto-spawn (2026-08-05)
    "collect_dexscreener.py",               # R0100 axis 3 (2026-08-05)
    "collect_geckoterminal_trades.py",      # R0291 signed DEX flow (2026-08-12)
    "collect_holder_concentration.py",      # R0100 axis 4 (2026-08-05)
    "collect_perpdex_funding.py",           # R0100 axis 5 + screen-on-discovery (2026-08-05)
    "retire_unfillable_candidates.py",      # §42 capacity retirement (2026-08-05)
    "check_crowding.py",                    # R0119 residual crowding fence (2026-08-05)
    "collect_funding_cross_section.py",     # R0119 producer: the crowding denominator
    "screen_funding_interval_mismatch.py",  # R0121 Stage-A settlement-calendar screen (2026-08-05)
    "resolve_llm_trader_book.py",           # R0123 decline grader (2026-08-05)
    "run_natural_experiment.py",            # R0207 first causal study, DiD (2026-08-05)
    "probe_bybit_archive.py",               # R0243 T7 retention alarm (2026-08-05)
    "fit_passive_impact.py",                # R0267 passive-fill impact model (2026-08-06)
    "collect_kr_venue_flags.py",            # R0299 KR flag surface, snapshot-only (2026-08-12)
    "probe_delisted_instruments.py",        # R0313 venue-side dead rosters (2026-08-12)
    "read_xls.py",                          # R0317 stdlib .xls extraction, L1.11a (2026-08-12)
    "check_extractor_invariants.py",        # R0318 OP-024 in-data invariants (2026-08-12)
    "check_repair_capacity.py",             # R0330 L1.28b repair service rate (2026-08-12)
    "run_execution_quality.py",             # R0334 six-component exec quality (2026-08-12)
)

#: Organs that legitimately owe no cron line, with the reason. "No schedule" must be a DECISION.
_SCHEDULE_EXEMPT: dict[str, str] = {
    "run_law_gate.py": "runs at BOUNDARIES (organ spawn, pre-push hook, CI) as well as its own "
                       "hourly line -- boundary invocation is the point, not a cadence",
    "check_build_standard.py": "runs inside the law gate's battery and in CI on every push; a "
                               "separate cron line would add nothing a commit does not already "
                               "trigger",
    "check_sizing_derivation.py": "a build-boundary fence like check_build_standard -- it reads "
                                  "source, not state, so it belongs in the law gate and CI where "
                                  "constants are actually written, not on a clock",
    "check_return_targeting.py": "reads doctrine and source, not state -- a target is written at "
                                 "commit time, so the gate that catches it is the commit gate",
    "derive_walcl_clock.py": "runs as the walcl_clock step of daily_research_cycle's _STEPS "
                             "chain, immediately after collect_fred_macro refreshes its input "
                             "(phase-correct by construction); a separate cron line would race "
                             "the archive it reads",
    "ship_restart.py": "an ACTUATOR, not a detector: it is invoked by deploy/pull_deploy.sh at "
                       "the moment a pull invalidates a supervised process, and by an operator "
                       "closing a daemon-stale-code defect. Putting it on a clock would restart "
                       "daemons on a TIMER -- the opposite of event-driven, and a standing "
                       "outage risk for the money path. Its detector (max_audit "
                       "check_stale_daemons) is the scheduled half of the pair",
    "check_extractor_invariants.py": "reads SOURCE, not state, exactly like check_sizing_derivation "
                                     "and check_return_targeting -- an extractor gains or loses its "
                                     "invariant at COMMIT time, so the commit gate is the "
                                     "information-arrival ceiling (L1.28c) and an hourly line would "
                                     "re-parse an unchanged tree 24 times a day. IT IS IN THAT GATE: "
                                     "run_law_gate.py _LAW_FENCES, beside both peers named above. "
                                     "This exemption spent a week citing a gate that did not invoke "
                                     "it, which is a cron exemption resting on nothing",
    "check_birth_properties.py": "reads the REPO -- docs/, scripts/ and the tracked decision "
                                 "ledger -- not live state, so an object gains or loses a birth "
                                 "property at COMMIT time and the commit gate is the "
                                 "information-arrival ceiling (L1.28c); an hourly line would "
                                 "re-scan an unchanged tree 24 times a day. IT IS IN THAT GATE: "
                                 "run_law_gate.py _LAW_FENCES, beside check_extractor_invariants "
                                 "and check_build_standard -- and it ALSO runs hourly there, via "
                                 "the same battery, so the cadence is covered without a second "
                                 "line. Whole-tree scope was chosen over a git-diff of added "
                                 "files because a merge-base is not resolvable on the shallow "
                                 "clone actions/checkout produces by default",
    "read_xls.py": "a TOOL, not an organ: it reads a file a seat hands it, so there is no state "
                   "for a clock to re-read (L1.28c information-arrival ceiling). Scheduling it "
                   "would mean scheduling it against WHAT -- there is no standing input, and a "
                   "cron line over an empty argument is a line that fails every minute",
    "check_doctrine_diff.py": "runs as the doctrine_diff step of daily_research_cycle's _STEPS "
                              "chain, beside doctrine_guard; doctrine edits arrive at most a "
                              "few per week, so the daily chain IS the information-arrival "
                              "ceiling (L1.28c) and a second cron line would re-read unchanged "
                              "state",
}

#: Organs that legitimately do not call guard(), with the reason. The gate organs THEMSELVES
#: must not: run_law_gate invokes the checks that guard() delegates to, so guarding inside them
#: is a loop, and check_constitution_core IS the seal authority.
_GUARD_EXEMPT: dict[str, str] = {
    "run_law_gate.py": "it IS the gate -- guarding inside it recurses into itself",
    "check_law_families.py": "guard() imports FAMILIES from this module; guarding here is a loop",
    "check_build_standard.py": "runs inside the law gate, which has already verified the core "
                               "before this fence executes",
    "check_sizing_derivation.py": "runs inside the law gate, which has already verified the core "
                                  "before this fence executes",
    "check_return_targeting.py": "runs inside the law gate, which has already verified the core "
                                 "before this fence executes",
    "check_birth_properties.py": "runs inside the law gate, which has already verified the core "
                                 "before this fence executes",
}

#: Vocabulary that proves an organ can say "I could not measure this".
#: Kept deliberately BROAD: a fence that flags a legitimate refusal state as missing is a false
#: positive, and false positives are how a build gate gets switched off. check_calibration's
#: "UNFORECASTING"/"BLIND" were flagged on the first run for exactly this reason -- the organ was
#: correct and this list was short. Add vocabulary here rather than reword an organ to suit it.
_REFUSAL_WORDS = ("UNMEASURED", "REFUSED", "REFUSING", "BLOCKED", "NO-DATA", "DARK",
                  "FLATLINE", "NOTHING-REPLICATED", "UNMEASURABLE", "UNCOUNTABLE",
                  "UNFORECASTING", "BLIND", "INSUFFICIENT", "UNKNOWN", "STERILE", "ABSENT",
                  "UNJUSTIFIED", "UNREADABLE", "UNPARSEABLE",
                  "DYING", "BELOW-STANDARD", "INCOMPLETE", "UNREACHED", "DECORATIVE",
                  "UNATTRIBUTED", "UNDECIDABLE",
                  "NOTHING-TO-REVIEW", "NO-REVIEW", "STALE", "RETIRED", "PROVISIONAL",
                  "CONTAMINATED", "UNDERPOWERED", "FORWARD-CLOCK", "NO-DATA",
                  "DUPLICATION", "DUPLICATE",
                  "UNINFORMATIVE", "ACCUMULATING", "UNSCORABLE", "NO-ANSWER",
                  "NO-CANDIDATES", "LENS-EXHAUSTED", "EXHAUSTED",
                  "RETURN-TARGETING",
                  "UNIDENTIFIED", "ABSORBING", "NO-EXCITATION", "UNDERPOWERED")


def _has_silent_swallow(tree: ast.AST) -> bool:
    """`except ...: pass` -- a failure converted into a success signal for every caller."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            body = [b for b in node.body if not isinstance(b, ast.Expr)
                    or not isinstance(getattr(b, "value", None), ast.Constant)]
            if body and all(isinstance(b, ast.Pass) for b in body):
                return True
    return False


def audit_organ(root: Path, name: str, *, manifest: str, matrix_src: str,
                test_blob: str) -> dict[str, Any]:
    p = root / "scripts" / name
    if not p.exists():
        return {"organ": name, "ok": False, "violations": ["MISSING -- declared but not present"]}
    src = p.read_text("utf-8", errors="ignore")
    v: list[str] = []

    if not any(w in src for w in _REFUSAL_WORDS):
        v.append("NO-REFUSAL-PATH (L1.28a): no UNMEASURED/REFUSED/NO-DATA vocabulary -- this "
                 "organ cannot say 'I could not measure', so it will report OK on absent input")
    if Path(name).stem not in test_blob:
        v.append("UNTESTED (L2.2): no test file references it -- wiring nothing proves")
    if name not in manifest and name not in _SCHEDULE_EXEMPT:
        v.append("UNSCHEDULED (L1.28c): no manifest line and no recorded exemption -- "
                 "built-never-scheduled is this desk's most expensive recurring defect")
    if name not in matrix_src:
        v.append("UNMAPPED (L2.0): absent from the enforcement matrix -- its failures carry no "
                 "authority and no law claims it")
    if "lawful" not in src and name not in _GUARD_EXEMPT:
        v.append("NO-LAWFUL-ENTRY (L1.42): does not call libs.ops.lawful.guard() -- this organ "
                 "can start under a tampered core or a doctrine missing a law family")
    try:
        if _has_silent_swallow(ast.parse(src)):
            v.append("SILENT-SWALLOW (L2.4): an `except: pass` converts a failure into a success "
                     "signal for every caller downstream")
    except SyntaxError as exc:
        v.append(f"UNPARSEABLE: {exc}")
    return {"organ": name, "ok": not v, "violations": v,
            "schedule_exempt_reason": _SCHEDULE_EXEMPT.get(name)}


def build_report(root: Path | None = None) -> dict[str, Any]:
    root = root or _ROOT
    manifest, unreadable = "", []
    for m in ("ops/crontab.manifest", "ops/crontab.research.manifest"):
        try:
            manifest += (root / m).read_text("utf-8", errors="ignore")
        except OSError as exc:
            # NOT a silent pass (this fence's own rule): an unreadable manifest means every
            # scheduling verdict below is UNMEASURED, and that must surface, not vanish.
            unreadable.append(f"{m}: {exc}")
    # A daily-cycle organ IS scheduled -- daily_research_cycle.py is itself on a manifest line, and
    # its _STEPS chain invokes each member every run. Until now that fact could only be asserted in
    # prose on _SCHEDULE_EXEMPT (derive_walcl_clock's entry says exactly this), which meant the
    # claim was never CHECKED: delete an organ from _STEPS and its static exemption still reads
    # fine. Reading the chain turns a prose assertion into a verified one, and the repair is
    # upward -- the fence now recognises real scheduling instead of being told to look away.
    for chain in ("scripts/daily_research_cycle.py",):
        try:
            manifest += (root / chain).read_text("utf-8", errors="ignore")
        except OSError as exc:
            unreadable.append(f"{chain}: {exc}")
    try:
        matrix_src = (root / "scripts/build_enforcement_matrix.py").read_text("utf-8")
    except OSError as exc:
        matrix_src, _ = "", unreadable.append(f"enforcement matrix unreadable: {exc}")
    test_blob = ""
    for t in (root / "tests").rglob("*.py"):
        test_blob += t.read_text("utf-8", errors="ignore")

    organs = [audit_organ(root, n, manifest=manifest, matrix_src=matrix_src,
                          test_blob=test_blob) for n in _GOVERNED]
    bad = [o for o in organs if not o["ok"]]
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.41 -- nothing enters below the standard: refusal path, tested, scheduled or "
               "exempt-with-reason, law-mapped, no silent swallow. Prevention at the build "
               "boundary, so timid or half-wired work never has to be caught later.",
        "status": "OK" if not bad else "BELOW-STANDARD",
        "n_governed": len(_GOVERNED), "n_failing": len(bad),
        "failing": [o["organ"] for o in bad],
        "unreadable_inputs": unreadable,
        "organs": organs,
        "detail": (f"{len(_GOVERNED) - len(bad)}/{len(_GOVERNED)} organs meet the build standard"
                   + ("" if not bad else "; " + "; ".join(
                       f"{o['organ']}: {len(o['violations'])} violation(s)" for o in bad))),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / "data/build_standard.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"build standard (L1.41): {rep['status']} -- {rep['detail']}")
        for o in rep["organs"]:
            for viol in o["violations"]:
                print(f"  {o['organ']}: {viol}")
    if args.report_only:
        return 0
    return 2 if rep["status"] != "OK" else 0


if __name__ == "__main__":
    sys.exit(main())
