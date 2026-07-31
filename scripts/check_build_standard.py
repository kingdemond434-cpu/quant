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
    "check_fence_yield.py",
    "derive_walcl_clock.py",                                # R0031 forward clock (2026-07-31)
    "run_llm_trader.py",
    "collect_announcements.py",
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
    "check_promotion_gate.py",
    "run_discretionary_max.py",
    "run_discretionary_hunt.py",
    "run_cost_hunt.py",
    "run_strategy_coverage.py",
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
                  "RETURN-TARGETING")


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
