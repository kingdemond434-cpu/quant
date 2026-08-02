"""LAW COVERAGE -- which constitutional principles are actually ENFORCED, measured.

THE PRINCIPAL'S REQUIREMENT (2026-08-02): every law enforced desk-wide, in every interaction, at
full coverage -- now and for anything added later. That last clause is the hard half. A one-time
audit of twenty-five principles is a snapshot; the twenty-sixth principle lands next week with no
enforcement and nothing notices, because nothing was watching for it.

So enforcement coverage is a MEASURED FRACTION with a chase behind it, exactly like moat coverage
and instrumentation coverage. A principle with no enforcement is a gap, gaps are ranked and
persisted, and a NEW principle defaults to unenforced -- which is fail-loud rather than fail-quiet
and is the only way "and upcoming always" can be true of a mechanism rather than of an intention.

TWO MODES OF ENFORCEMENT, AND THEY ARE NOT INTERCHANGEABLE:

  MECHANICAL -- a registered max_audit check that can go red. This is real enforcement: it fires
  without anybody reading anything, and the desk stops being able to violate the law silently.

  INTERACTIONAL -- the principle is in OBJECTIVE_PREAMBLE, so it governs every model interaction
  on the desk. This is real too, and it is what "in every interaction" means, but it constrains
  what gets PROPOSED rather than what gets DONE: a model that ignores the preamble produces a bad
  recommendation and nothing catches it.

A principle with only interactional cover is therefore NOT fully enforced, and this module says so
rather than counting it as done. Both modes together is the target; mechanical alone is stronger
than interactional alone; neither is a gap at the front of the chase.

WHAT THIS DELIBERATELY DOES NOT DO. It does not claim a check enforces a principle merely because
somebody wrote the mapping down. The map is verified: the named check must exist AND be registered
in CHECKS, or the entry is treated as no enforcement at all -- an unregistered check is a law the
desk believes it is enforcing, which is the failure four consecutive charters shipped with.

Pure, dependency-free. The verification of registration happens in max_audit, which owns CHECKS.
"""

from __future__ import annotations

from libs.doctrine.constitution import OBJECTIVE_PREAMBLE, PRINCIPLES

__all__ = [
    "ENFORCEMENT",
    "PREAMBLE_MARKERS",
    "coverage",
    "unenforced",
]

#: principle id -> max_audit check names that mechanically enforce it. A check may enforce several
#: principles and a principle may need several checks; both are normal. An EMPTY tuple is an
#: honest declaration that nothing mechanical enforces this yet -- it is not an omission to be
#: filled in with a plausible-looking name, because a wrong entry is worse than an empty one: it
#: reports the law as covered while nothing fires.
ENFORCEMENT: dict[str, tuple[str, ...]] = {
    # P0  sole objective -- the preamble carries it to every organ; the audit checks it is there
    "P0": ("constitution", "law-coverage"),
    # P1  information value -- the funnel now ORDERS by expected shift in E[log W] rather
    #     than by the order the generator emitted candidates in. Checked on the artifact,
    #     and the compute floor is audited for BITE so a ranking cannot become a filter.
    "P1": ("evig-ranking",),
    # P2  alpha is modelled, not implied -- the two-stage discovery law is exactly this rule
    "P2": ("mine-gate", "rejection-shadow"),
    # P3  research aggression -- idle capability and unspent capacity are scored defects
    "P3": ("idle", "clock-saturation", "no-mining-throttle"),
    # P4  constraint elimination -- the allocator re-identifies the bottleneck every cycle, and
    #     the check reads the ARTIFACT field, which exists only if that path actually ran
    "P4": ("governing-layer",),
    # P5  maximum sustainable aggression -- sizing on evidence, neither under nor over
    "P5": ("gate-optimality",),
    # P6  survival is a growth argument -- the rails themselves
    "P6": ("production", "stale-daemons"),
    # P7  resource expansion -- a binding resource is bought, not rationed
    "P7": ("source-backlog", "data-utilization"),
    # P8  validation integrity never traded for throughput
    "P8": ("mine-gate", "findings-ratchet", "depth-parity"),
    # P9  the ratchet -- aggression AND, since 2026-08-02, enforcement coverage itself
    "P9": ("constitution", "law-coverage"),
    # P10 everything is an estimate -- the allocator states WHY it refused to rank
    "P10": ("governing-layer",),
    # P11 retirement requires evidence -- the three-verdict rule, asserted on the artifact
    "P11": ("governing-layer",),
    # P12 global optimum first, then everyone to their maximum
    "P12": ("governing-layer",),
    # P13 no permanent neglect -- the starvation ledger, which only exists if allocate() ran
    "P13": ("governing-layer",),
    # P14 the bottleneck scales upward -- discovery is never throttled to clear a backlog
    "P14": ("no-mining-throttle", "mining-nonregression", "mine-flow"),
    # P15 robust Kelly is mandatory
    "P15": ("gate-optimality",),
    # P16 non-destructive coexistence -- MC_i per family, and the separation ladder,
    #     which binds immediately even while the measurement is dormant
    "P16": ("coexistence",),
    # P17 maximum exploration
    "P17": ("dig-depth", "generation", "source-backlog"),
    # P18 optimise the rate, not only the level -- closure_rate over recorded history
    "P18": ("governing-layer",),
    # P19 output-only cycles -- production, not exit code
    "P19": ("production", "producer-cadence"),
    # P20 zero ceiling
    "P20": ("no-ceiling", "governing-layer"),
    # P21 governance is subordinate / a weapon
    "P21": ("constitution",),
    # P22 immutable core preserved
    "P22": ("universal-doctrine", "self-application"),
    # P23 anti-timidity on every axis
    "P23": ("idle", "no-mining-throttle"),
    # P24 the governance asymmetry law
    "P24": ("constitution",),
    # P25 detect implies repair -- every detector carries a fix path; only the pager may notify
    "P25": ("fixers-not-watchers",),
    # P26 under-exploration of owned data is a breach, and the breach is the gap NOT CLOSING
    "P26": ("under-exploration", "mining-nonregression", "no-mining-throttle"),
}

#: principle id -> a phrase that must appear in OBJECTIVE_PREAMBLE for the law to be in scope for
#: every model interaction. Checked against the live preamble rather than asserted, so a preamble
#: edit that drops a clause shows up as lost interactional cover instead of passing silently.
PREAMBLE_MARKERS: dict[str, str] = {
    "P0": "max_pi E[log W_T]",
    "P1": "E[log W | DELTA_I] - E[log W] > 0",
    "P2": "MODELLING RELATIONSHIP",
    "P3": "research spend is bounded by the objective",
    "P4": "B = argmax_i |dE[log W]/dC_i|",
    "P5": "Bet the most",
    "P6": "log(0) = -inf",
    "P7": "the answer is to BUY MORE OF IT",
    "P8": "",                                    # throughput/bar clause lives in the mission text
    "P9": "no principle may be revised toward conservatism",
    "P10": "EVERYTHING IS AN ESTIMATE",
    "P11": "RETIREMENT NEEDS EVIDENCE",
    "P12": "GLOBAL FIRST, THEN EVERYONE",
    "P13": "never entitlement",
    "P14": "BOTTLENECK SCALES UPWARD",
    "P15": "ROBUST KELLY IS MANDATORY",
    "P16": "COEXISTENCE",
    "P17": "MAXIMUM EXPLORATION",
    "P18": "RATE OVER LEVEL",
    "P19": "OUTPUT-ONLY",
    "P20": "ZERO CEILING",
    "P21": "GOVERNANCE IS A WEAPON, NOT A POLICE FORCE",
    "P22": "IMMUTABLE CORE",
    "P23": "TIMIDITY IS SCORED ON EVERY AXIS",
    "P24": "must name the throughput it multiplies",
    "P25": "DETECT IMPLIES REPAIR",
    "P26": "UNDER-EXPLORATION IS A BREACH",
}


def _interactional(pid: str, preamble: str = OBJECTIVE_PREAMBLE) -> bool:
    marker = PREAMBLE_MARKERS.get(pid, "")
    return bool(marker) and marker in preamble


def coverage(registered: set[str] | None = None,
             preamble: str = OBJECTIVE_PREAMBLE) -> dict:
    """Per-principle enforcement, with the two modes reported SEPARATELY.

    `registered` is the set of check names actually in max_audit's CHECKS. When supplied, a
    mapping that names an unregistered check counts as NO enforcement -- an unregistered check is
    a law the desk believes it is enforcing, and four consecutive charters shipped exactly that
    way before the registry check existed. Passing None skips verification and is only for
    callers that genuinely have no access to CHECKS.
    """
    rows = []
    for p in PRINCIPLES:
        named = tuple(ENFORCEMENT.get(p.id, ()))
        live = tuple(c for c in named if registered is None or c in registered)
        phantom = tuple(c for c in named if registered is not None and c not in registered)
        inter = _interactional(p.id, preamble)
        rows.append({
            "id": p.id,
            "name": p.name,
            "posture": p.posture,
            "aggression": p.aggression,
            "mechanical": list(live),
            "phantom_checks": list(phantom),
            "interactional": inter,
            "mode": ("BOTH" if live and inter else
                     "MECHANICAL" if live else
                     "INTERACTIONAL" if inter else "NONE"),
        })
    both = [r for r in rows if r["mode"] == "BOTH"]
    mech = [r for r in rows if r["mode"] == "MECHANICAL"]
    only_inter = [r for r in rows if r["mode"] == "INTERACTIONAL"]
    none = [r for r in rows if r["mode"] == "NONE"]
    total = max(1, len(rows))
    return {
        "principles": len(rows),
        "both": len(both),
        "mechanical_only": len(mech),
        "interactional_only": len(only_inter),
        "unenforced": len(none),
        "mechanical_pct": round(100.0 * (len(both) + len(mech)) / total, 1),
        "interactional_pct": round(100.0 * (len(both) + len(only_inter)) / total, 1),
        "full_pct": round(100.0 * len(both) / total, 1),
        "rows": rows,
        "phantom": sorted({c for r in rows for c in r["phantom_checks"]}),
        "note": ("interactional cover constrains what gets PROPOSED; mechanical cover constrains "
                 "what gets DONE. A law with only the first is not fully enforced -- a model that "
                 "ignores the preamble produces a bad recommendation and nothing catches it."),
    }


def unenforced(registered: set[str] | None = None,
               preamble: str = OBJECTIVE_PREAMBLE) -> list[dict]:
    """Gaps, worst first: nothing at all, then interactional-only, then by aggression rank.

    ORDERED BY AGGRESSION DESCENDING within each tier, deliberately. An unenforced principle at
    aggression 10 is a law the desk considers maximally binding and cannot actually detect a
    violation of; one at 7 is the same defect with less at stake. Ranking them together would let
    the loudest law wait behind three quiet ones.
    """
    rows = coverage(registered, preamble)["rows"]
    gaps = [r for r in rows if r["mode"] in ("NONE", "INTERACTIONAL")]
    return sorted(gaps, key=lambda r: (r["mode"] != "NONE", -r["aggression"], r["id"]))
