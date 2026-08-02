#!/usr/bin/env python3
"""THE ENFORCER -- constitutional breaches are ACTED ON every cycle, never merely recorded.

THE GAP THIS CLOSES, AND IT WAS MINE. max_audit gained six constitutional checks and every one of
them was a DETECTOR: it produced a defect entry and nothing repaired anything. That is precisely
what P25 forbids -- a monitor that finds a defect and leaves it open gives the desk the defect AND
the false comfort of watching it -- and the checks enforcing the constitution were themselves the
last organs violating it.

So every breach is resolved into the same three tiers the rest of the desk uses:

  AUTOFIX      deterministic and reversible: the doctrine's copy of the constitution has drifted
               from the module, or the aggression high-water mark needs raising after a principle
               was strengthened. Repaired immediately, here, with before/after recorded.

  PATCH_READY  the fix is known exactly but touches source: an organ missing the preamble, a
               progress organ with no declared successor, a law with no enforcing check. Emitted
               as the precise edit and CHASED with a counter only closing clears.

  BLOCKED      deliberately unrepairable BY DESIGN, and the ratchet is the whole example. A
               weakened principle must NOT be auto-restored: the ratchet's entire value is that
               weakening costs a visible, argued, hand-edited act, and an enforcer that silently
               put the number back would destroy the mechanism while appearing to defend it.

NEVER-BREACHED IS A LEDGER, NOT A CLAIM. Every breach carries an age that only its disappearance
clears, so "we have been out of constitutional compliance for nine cycles" is visible rather than
re-reported as a fresh finding each morning. A breach older than the stale threshold stops being a
status and becomes a defect in its own right.

WHAT IT WILL NOT DO. It never edits a principle, never lowers a mark, never touches the money path
or a survival rail. An enforcer that can rewrite the law it enforces is not an enforcer.
"""
from __future__ import annotations

import contextlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.doctrine import ratchet as _ratchet  # noqa: E402
from libs.ops.remediation import (  # noqa: E402
    AUTOFIX,
    BLOCKED,
    PATCH_READY,
    Leak,
    LeakLedger,
)

OUT = ROOT / "data/constitution_enforcement.json"
BREACHES = ROOT / "data/constitution_breaches.json"

#: Cycles a breach may stand before it stops being a finding and becomes a defect. Three: one is
#: a cycle catching it, two is a cycle to act, and a third means nobody is acting.
BREACH_STALE_CYCLES = 3

#: defect key -> (tier, the exact action). Every constitutional check's output is classified HERE
#: rather than at each call site, so a new check cannot quietly ship as a pure detector -- an
#: unclassified key is itself reported below.
_RESOLUTION: dict[str, tuple[str, str]] = {
    "constitution-doctrine-stale": (
        AUTOFIX, "resync the doctrine's constitution block from the module (one-directional, "
                 "code -> prompt) so every local organ stops running on a superseded objective"),
    "constitution-absent-from-doctrine": (
        AUTOFIX, "prepend the constitution block to ops/principal_doctrine.txt -- every local "
                 "organ injects that file, so its absence means an aggression stance with no "
                 "objective for it to serve"),
    "constitution-ratchet-broken": (
        BLOCKED, "NOT auto-repairable BY DESIGN. Restoring the number silently would destroy the "
                 "ratchet while appearing to defend it: its entire value is that weakening costs "
                 "a visible, argued, hand-edited act. Either restore the principle deliberately "
                 "or edit docs/research/CONSTITUTION_RATCHET.json with a dated reason."),
    "constitution-ratchet-missing": (
        AUTOFIX, "regenerate the high-water mark from the live constitution and commit it -- with "
                 "no mark there is no floor under any principle"),
    "constitution-not-injected": (
        PATCH_READY, "prepend libs.doctrine.constitution.OBJECTIVE_PREAMBLE to the named organ's "
                     "system prompt. Until then it is still optimising something -- the objective "
                     "just is not stated, so nothing it proposes can be scored"),
    "constitution-weakening-language": (
        PATCH_READY, "rewrite the named statement so the weakening phrase is NAMED rather than "
                     "USED, or strengthen the principle; do not delete the detector"),
    "governance-asymmetry": (
        PATCH_READY, "add the enabling principles the guards were supposed to make possible. A "
                     "body of law follows its majority, so restraints outnumbering enablers means "
                     "the desk optimises for not being wrong however aggressive the preamble"),
    "no-ceiling-violated": (
        PATCH_READY, "delete the completion claim from the named organ. P20 recognises no 'done' "
                     "for any component -- a completion claim is an unexamined ceiling"),
    "coverage-without-next-ceiling": (
        PATCH_READY, "add a next_ceiling field naming the successor constraint, so the organ does "
                     "not go quiet the day its number turns green"),
    "law-unenforced": (
        PATCH_READY, "write a check that can go red for the named principle and register it in "
                     "CHECKS -- a law nothing can detect a violation of is not a law"),
    "law-enforced-by-phantom-check": (
        PATCH_READY, "register the named check or remove the claim. An unregistered check is a "
                     "law the desk BELIEVES it is enforcing"),
    "law-coverage-regressed": (
        PATCH_READY, "restore the lost enforcement, or enforce the newly-added law. Coverage "
                     "ratchets: a fall is either a law that lost its check or a law nobody "
                     "enforced"),
    "governing-layer-inert": (
        PATCH_READY, "run scripts/run_allocator.py in the cadence -- a governing layer nothing "
                     "calls governs nothing, and its unit tests stay green while it is inert"),
    "governing-layer-partial": (
        PATCH_READY, "the named artifact field is missing, so its code path did not execute; "
                     "restore the call rather than the field"),
    "governing-layer-ranked-on-nothing": (
        PATCH_READY, "state why the allocator refused to rank -- silence is indistinguishable "
                     "from an empty ranking, and a ranking gets acted on"),
    "detector-without-fix-path": (
        PATCH_READY, "resolve the organ's findings into AUTOFIX / PATCH_READY / BLOCKED. Only the "
                     "pager may notify without repairing"),
    "detector-cannot-age-its-findings": (
        PATCH_READY, "add a per-finding age counter that only CLOSING clears, or a standing leak "
                     "reads as a fresh finding every cycle"),
    "evig-not-wired": (
        PATCH_READY, "rank the funnel by EVIG -- otherwise L4 compute goes to whatever order the "
                     "generator emitted"),
    "evig-scored-nothing": (
        PATCH_READY, "supply p_validate and moat_advantage so candidates are scored; ranking by "
                     "nothing is ranking by emission order"),
    "evig-floor-silently-buried-everything": (
        PATCH_READY, "flag the floor as non-discriminating -- a ranking that buries everything IS "
                     "a filter, which EVIG has no authority to be"),
}

#: The constitutional checks whose output this enforcer owns. Named explicitly so a check added
#: later shows up as unowned rather than silently escaping enforcement.
_CONSTITUTIONAL_CHECKS = ("constitution", "no-ceiling", "law-coverage", "governing-layer",
                          "evig-ranking", "fixers-not-watchers")


def _autofix(key: str) -> dict:
    """Apply the deterministic repairs. Each is reversible and touches no principle."""
    if key in ("constitution-doctrine-stale", "constitution-absent-from-doctrine"):
        result = _ratchet.sync_preamble(ROOT / _ratchet.DOCTRINE_PATH)
        return {"applied": result != "doctrine-missing", "action": f"sync_preamble -> {result}",
                "reversible": "the prior doctrine text is in git; revert the file to undo"}
    if key == "constitution-ratchet-missing":
        mark = _ratchet.update_high_water(ROOT / _ratchet.BASELINE_PATH)
        return {"applied": True, "action": f"regenerated high-water mark for {len(mark)} "
                                           "principle(s) from the live constitution",
                "reversible": "the file is in git"}
    return {"applied": False, "action": f"no autofix implemented for '{key}'"}


def main() -> int:
    t0 = time.time()
    import scripts.max_audit as audit

    by_name = dict(audit.CHECKS)
    missing = [c for c in _CONSTITUTIONAL_CHECKS if c not in by_name]

    found: list[tuple[str, str]] = []
    for name in _CONSTITUTIONAL_CHECKS:
        fn = by_name.get(name)
        if fn is None:
            continue
        d: list = []
        try:
            fn(d)
        except Exception as e:                     # a broken check must not stop enforcement
            found.append((f"check-raised-{name}", f"{type(e).__name__}: {e}"))
            continue
        found.extend(d)

    breaches: list[Leak] = []
    unclassified: list[str] = []
    for key, msg in found:
        tier, action = _RESOLUTION.get(key, ("", ""))
        if not tier:
            unclassified.append(key)
            tier, action = (PATCH_READY,
                            "NO RESOLUTION DECLARED for this defect key. A constitutional check "
                            "that ships without a fix path is itself a P25 violation -- add an "
                            "entry to _RESOLUTION naming the exact repair.")
        breaches.append(Leak(id=key, what=msg[:400], evidence="max_audit constitutional check",
                             tier=tier, action=action,
                             verify="the same check returns clean on the next cycle"))

    ledger = LeakLedger.load(BREACHES)
    ledger.observe(breaches)
    applied = [{"breach": b.id, **_autofix(b.id)} for b in breaches if b.tier == AUTOFIX]

    # Re-run after autofixes so the artifact reflects the REPAIRED state, not the pre-fix one.
    # Reporting a breach this run already closed would make the enforcer look like it is losing.
    if applied:
        recheck: list = []
        for name in _CONSTITUTIONAL_CHECKS:
            fn = by_name.get(name)
            if fn is not None:
                with contextlib.suppress(Exception):
                    fn(recheck)
        still = {k for k, _ in recheck}
        breaches = [b for b in breaches if b.id in still or b.tier != AUTOFIX]
        ledger.observe(breaches)
    ledger.save(BREACHES)

    stale = [b for b in breaches if ledger.age(b.id) >= BREACH_STALE_CYCLES]
    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "seconds": round(time.time() - t0, 2),
        "checks_run": [c for c in _CONSTITUTIONAL_CHECKS if c in by_name],
        "checks_missing": missing,
        "breaches": [b.as_dict() | {"cycles_open": ledger.age(b.id)} for b in breaches],
        "autofixes_applied": applied,
        "unclassified_defect_keys": unclassified,
        "stale_breaches": [b.id for b in stale],
        "compliant": not breaches,
        "posture": (
            "every breach carries a tier and an exact action. AUTOFIX is applied here and now; "
            "PATCH_READY names the precise edit and is chased; BLOCKED is unrepairable BY DESIGN "
            "-- the ratchet is the example, because silently restoring a weakened principle would "
            "destroy the mechanism while appearing to defend it."),
        "will_not_do": (
            "never edits a principle, never lowers a mark, never touches the money path or a "
            "survival rail. An enforcer that can rewrite the law it enforces is not an enforcer."),
        "next_ceiling": (
            "auto-repair the PATCH_READY tier where the edit is mechanical (a missing preamble "
            "import is a deterministic insertion); then catch SUBTLE breaches -- a law obeyed in "
            "letter and violated in effect -- which no absence-detector can see."),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1), "utf-8")

    print(f"constitution: {len(breaches)} breach(es), {len(applied)} autofixed, "
          f"{len(stale)} STALE | {'COMPLIANT' if out['compliant'] else 'IN BREACH'} "
          f"| {out['seconds']}s")
    for b in breaches:
        print(f"  [{b.tier:11s}|x{ledger.age(b.id)}] {b.id}: {b.what[:110]}")
        print(f"        FIX: {b.action[:150]}")
    for a in applied:
        print(f"  AUTOFIX {'APPLIED' if a.get('applied') else 'NOOP'}: {a['action'][:120]}")
    if missing:
        print(f"  CHECKS MISSING from max_audit: {missing}")
    if unclassified:
        print(f"  UNCLASSIFIED defect keys (no declared fix): {unclassified}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
