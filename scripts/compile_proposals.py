"""Proposals and audits become runnable cells, or a named refusal. Nothing sits in a queue.

WHY THIS EXISTS (principal, 2026-08-29)

    "so all research proposals -- who will implement them"
    "and all audits and recommendations by the openrouters -- who will"

Nobody, and that was the honest answer. The free panel writes `NAME | MECHANISM | PAYER | TEST |
KILL` into `hypothesis_queue.jsonl` and audit recommendations into a report, and both were
terminal: a human read them or nothing happened. A research role whose output nobody consumes is
the same defect as a role that never runs, wearing a more convincing artifact.

THIS IS THE CONSUMER. Two paths, and a proposal takes exactly one:

    COMPILED   the proposal maps onto a semantic coordinate `family_generic` can execute, so it
               becomes a docket cell today. No code is generated, nothing a model returned is
               executed -- the mapping picks five axis values and the family is already written.
    REFUSED    the proposal needs something the generic family cannot express (a cross-sectional
               rank, a multi-leg spread, options data the desk does not have). It is recorded
               with the reason and the missing capability NAMED, which is a research finding in
               itself: a queue of refusals is a list of what to build next.

REFUSING BY NAME IS THE LOAD-BEARING PART. An approximation would enter the docket as if it were
the proposal, and the gauntlet would judge something nobody meant to test -- then the result would
be attributed to the mechanism. That is worse than not testing it, because it produces a
confident wrong answer about an idea that was never tried.

AUDIT RECOMMENDATIONS BECOME EXPLORATION PRIORS, not prose. When the cold auditor names a region
worth searching, that region's coordinates are enumerated and queued. A recommendation that stays
a paragraph changes nothing; a recommendation that becomes cells changes where the next trials go.

NOTHING COMPILED HERE HAS ANY AUTHORITY. Cells enter the docket where every other candidate does
and face the identical gauntlet. A free model's idea is exactly as unprivileged as a parameter
sweep's, which is what makes running weak models safe.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DESK = ROOT / "desks" / "mt5"
sys.path.insert(0, str(DESK))

QUEUE = ROOT / "data" / "hypothesis_queue.jsonl"
FREE = ROOT / "data" / "free_research.json"
COMPILED = DESK / "data" / "hypotheses" / "compiled_proposals.json"
OUT = ROOT / "data" / "proposal_compiler.json"

#: Words in a proposal that map to a semantic EVENT. Matched against the whole record, because a
#: model names the mechanism in the text rather than in a field.
_EVENT_WORDS: dict[str, tuple[str, ...]] = {
    "benchmark_flow": ("fix", "fixing", "benchmark", "rebalanc", "index", "close auction"),
    "options_hedging": ("gamma", "vega", "option", "hedg", "expiry", "dealer"),
    "liquidity_shock": ("liquidity", "spread", "depth", "illiquid", "thin"),
    "volatility_shock": ("volatility", "vol spike", "variance", "realized vol",
                         "vol regime", "regime transition", "squeeze", "expansion"),
    "forced_deleveraging": ("margin", "liquidation", "deleverag", "forced", "stop-out"),
    "inventory_rebalance": ("inventory", "imbalance", "flow", "positioning pressure"),
    "macro_release": ("macro", "cpi", "nfp", "central bank", "release", "announcement",
                      "intervention", "data surprise", "publication", "disclosure"),
    "carry_change": ("carry", "swap", "rate differential", "roll", "basis"),
    "cross_market_move": ("cross", "lead", "lag", "correlat", "spillover", "transmission",
                          "information asymmetry", "propagat", "transmit", "relative value"),
    "positioning_extreme": ("cot", "positioning", "crowd", "extreme", "sentiment"),
    "session_transition": ("session", "open", "handoff", "asia", "tokyo", "london", "overnight"),
}

_CONTEXT_WORDS: dict[str, tuple[str, ...]] = {
    "asia": ("asia", "tokyo", "overnight"),
    "london": ("london", "european", "euro session"),
    "new_york": ("new york", "us session", "ny ", "comex", "cme"),
    "overlap": ("overlap",),
    "high_vol": ("high volatility", "elevated vol", "stressed"),
    "low_vol": ("low volatility", "quiet", "calm"),
    "month_end": ("month-end", "month end", "quarter-end", "dividend record"),
    "high_liquidity": ("liquid", "deep"),
    "low_liquidity": ("thin", "illiquid"),
}

#: COVER EVERY LEGAL DIRECTION. This table named four of the six values in semantic_space
#: DIRECTIONS: volatility_expansion and volatility_compression were absent, so a proposal about
#: a vol regime could never resolve a direction and was refused for being unreadable rather than
#: for being wrong. 796 compilable proposals failed direction resolution on 2026-09-04.
_DIRECTION_WORDS: dict[str, tuple[str, ...]] = {
    "reversal": ("revers", "mean revert", "decay", "unwind", "correct", "fade", "pressure clears",
                 "retrace", "snap back", "overshoot", "exhaust", "give back", "normalis",
                 "normaliz", "round-trip", "round trip"),
    "continuation": ("continu", "momentum", "persist", "drift", "trend", "extend",
                     "follow-through", "follow through", "propagat", "diffus", "transmit",
                     "carry through", "sustain", "lead-lag", "leads the"),
    "convergence": ("converg", "narrow", "spread compress", "re-couple", "recouple",
                    "arbitrage away", "close the gap", "realign", "catch up", "catch-up"),
    "divergence": ("diverg", "widen", "decoupl", "de-coupl", "disconnect", "dislocat",
                   "asymmetr", "gap between", "separat", "break down"),
    "volatility_expansion": ("volatility expansion", "vol expansion", "range expansion",
                             "breakout", "expansion", "expands", "vol spike",
                             "volatility increase", "variance rises", "regime shift to high"),
    "volatility_compression": ("compress", "contraction", "squeeze", "coil", "narrowing range",
                               "volatility decline", "vol collapse", "variance falls",
                               "consolidat", "quiet regime"),
}

#: THE HORIZON IS PART OF THE CLAIM TOO. family_generic supports 1h/4h/daily, but the compiler
#: pinned "1h" for every proposal, so a weekly-rebalance idea and an hourly one landed on the
#: SAME coordinate and the second was refused as a duplicate of the first. 365 proposals were
#: refused for duplicate_coordinate on 2026-09-04 with two of the five axes frozen.
_OUTPUT_WORDS: dict[str, tuple[str, ...]] = {
    "daily": ("daily", "weekly", "week", "multi-day", "multi day", "overnight hold", "t+1",
              "monthly", "per day", "day-over-day", "8y sample", "quarterly"),
    "4h": ("4h", "four-hour", "four hour", "intraday swing", "several hours", "half-session",
           "multi-hour", "6h", "8h"),
    "1h": ("hourly", "1h", "per hour", "one-hour", "one hour", "60-minute"),
}

#: Capabilities the generic family cannot express. Naming them turns a refusal into a build list.
#: MATCHED ON WORD BOUNDARIES, NOT SUBSTRINGS. The plain-substring version refused a proposal
#: whenever "skew" appeared -- distributional skew is not options skew -- and "iv " matched
#: inside "relative ", "derivative " and "positive ". "1m" and "5m" matched any text containing
#: those two characters. 786 capability refusals were recorded on 2026-09-04 and the first three
#: hypotheses the world crawler ever produced were all refused for options_data it never needed.
#: A capability refusal is expensive: it is the one refusal that means "never retry until built".
_UNSUPPORTED_RX: dict[str, tuple[str, ...]] = {
    "cross_sectional_rank": (r"\brank(s|ed|ing)?\b", r"cross-section", r"universe-wide",
                             r"percentile across"),
    "multi_leg_spread": (r"spread between", r"pair trade", r"\blegs?\b", r"\bbaskets?\b",
                         r"relative value"),
    "options_data": (r"implied vol", r"\biv\b", r"option[\s-]*skew", r"vol(atility)?[\s-]+skew",
                     r"open interest", r"gamma exposure", r"\bgamma\b", r"delta[\s-]*hedg"),
    "order_flow_data": (r"order book", r"depth of book", r"tick flow", r"\baggressor\b"),
    # A bare "m" after a number is not a timeframe: "$1m", "0.15 m" and "30 ms" all matched it
    # and sub_hourly jumped 309 -> 780 refusals. A real sub-hourly claim spells the unit out or
    # names the MT5 frame, so require one of those.
    "sub_hourly": (r"\b(1|5|15|30)\s*-?\s*min(ute)?s?\b", r"\bm(1|5|15|30)\b",
                   r"\b(1|5|15|30)m\s+(bar|candle|chart|data|frame)", r"minute bars?",
                   r"sub-hourly", r"tick data", r"final 30"),
}


#: Language that means executing this proposal would COST the desk something beyond a trial.
#: Each key is a distinct way a "good idea" is net-negative, and each is refused by name.
#:
#: WHY A TEXT CHECK IS LEGITIMATE HERE. These are not subtle properties inferred from data -- they
#: are things a proposal SAYS about itself. A proposal that asks to relax a gate says so; one that
#: introduces a cap says so. Catching them at intake costs microseconds; catching them after they
#: are wired costs whatever they regressed.
_NEGATIVE_ROI: dict[str, tuple[str, ...]] = {
    "regresses_a_gate": (
        "loosen", "relax", "lower the threshold", "reduce the bar", "weaken", "waive",
        "skip validation", "bypass", "less strict", "ease the", "soften"),
    "adds_a_quota": (
        "quota", "cap the", "limit the number", "throttle", "restrict search", "only test the top",
        "prune to", "budget cap", "max candidates"),
    "names_a_tradeoff": (
        "trade-off", "tradeoff", "at the cost of", "in exchange for", "sacrific",
        "we would lose", "downside is", "requires giving up"),
    "needs_paid_data": (
        "subscription", "licensed data", "paid feed", "vendor data", "bloomberg", "refinitiv",
        "purchase", "\\$ per month", "commercial licence", "commercial license"),
    "needs_new_infrastructure": (
        "new database", "rewrite the", "replace the engine", "migrate", "re-architect",
        "new execution venue", "requires a broker change"),
}

#: TIMIDITY: language admitting the proposal will not move E[log W] by any path.
#:
#: The constitution's sole objective is max E[log W_T]; realized CAGR and alpha are MEASURES, not
#: goals. So a proposal earns a trial by claiming a path to geometric growth -- and the path may
#: be indirect. A candidate that raises the book's INDEPENDENCE raises geometric growth at
#: unchanged arithmetic return, and one that kills a live hypothesis frees the budget its
#: successor needs. Both are growth paths.
#:
#: WHAT IS ACTUALLY REJECTED is a proposal that names no path at all: purely defensive, purely
#: cosmetic, or self-described as marginal. "Reduce drawdown slightly" with no edge claim and no
#: independence claim is a smaller version of the book the desk already has.
_TIMID: dict[str, tuple[str, ...]] = {
    "self_described_marginal": (
        "marginal improvement", "slight improvement", "modest gain", "small tweak",
        "incremental adjustment", "minor refinement", "fine-tune the existing",
        "slightly better", "a small edge on top of"),
    "purely_defensive": (
        "reduce risk only", "risk reduction only", "purely defensive", "hedge only",
        "no additional return", "without adding return", "capital preservation only",
        "lower volatility only"),
    "conservative_by_construction": (
        "conservative approach", "play it safe", "avoid taking positions",
        "trade less frequently to be safe", "sit out", "stay flat"),
}

#: Words that indicate a GROWTH PATH, direct or indirect. A proposal carrying any of these is not
#: timid even if its claimed effect is small -- a 0.05R edge that is INDEPENDENT is worth more to
#: geometric growth than a 0.20R clone, which is the whole n_eff argument, and rejecting it for
#: modesty would invert the objective.
_GROWTH_PATH = (
    "independent", "uncorrelated", "orthogonal", "diversif", "new mechanism", "new payer",
    "forced", "compelled", "constraint", "edge", "expectancy", "premium", "mispricing",
    "kill condition", "falsif", "unexplored", "untested", "residual",
)

#: A coordinate this heavily attempted with nothing to show is saturated ground. Re-testing it is
#: a trial spent to re-learn something measured. Deliberately generous -- the desk has been wrong
#: about "barren" before, and this is a spending decision rather than a verdict on the mechanism.
_SATURATED_ATTEMPTS = 400


def _saturation_map() -> dict[str, int]:
    """Attempts per (event, direction) region, from the measured intake artifact."""
    try:
        intake = json.loads((ROOT / "data" / "research_intake.json").read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    # `coverage.never_touched` names regions with zero; the census carries the counts.
    try:
        alloc = json.loads((ROOT / "data" / "research_allocation.json").read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, int] = {}
    for row in alloc.get("ranked", []):
        counts = row.get("counts") or {}
        out[str(row.get("family"))] = int(counts.get("candidates", 0))
    _ = intake
    return out


def _existing_coordinates() -> set[str]:
    """Coordinates the desk has already CERTIFIED. Duplicating one adds no information.

    READ CERTIFICATES, NOT THE COMPILER'S OWN LAST OUTPUT. A first version seeded this from
    `compiled_proposals.json` -- the file this script writes -- so every coordinate it produced
    minutes earlier counted as an incumbent and the next run refused ALL FIFTEEN proposals as
    duplicates of itself. A check whose baseline is its own output rejects everything on the
    second run and reports it as a finding.

    An incumbent is something the desk OWNS: a survivor that passed the gauntlet. A cell merely
    queued for testing is not evidence of anything and must not block a second look.
    """
    out: set[str] = set()
    try:
        surv = json.loads((DESK / "reports" / "UNIVERSAL_SURVIVORS.json")
                          .read_text("utf-8")).get("survivors") or {}
    except (OSError, json.JSONDecodeError):
        return out
    for row in surv.values():
        spec = (row or {}).get("shadow_spec") or {}
        fam = spec.get("family")
        if fam:
            # Certificates predate the coordinate system, so match on the EVENT they map to
            # rather than on a full coordinate they never carried.
            out.add(str(fam))
    return out


def _roi_refusal(rec: dict[str, Any], text: str, coordinate: str,
                 saturation: dict[str, int], seen: set[str]) -> dict[str, Any] | None:
    """Would executing this cost more than it returns? Returns a refusal, or None to proceed.

    CRITICAL THINKING BEFORE AUTOMATIC EXECUTION (principal, 2026-08-29). Automatic execution is
    right -- a proposal nobody runs is a proposal nobody made. But automatic execution WITHOUT
    this check is how a research loop quietly spends its budget re-testing saturated ground,
    duplicating cells it already owns, or wiring in a constraint that narrows every future search.
    """
    t = text.lower()
    for reason, words in _NEGATIVE_ROI.items():
        hit = next((w for w in words if w in t), None)
        if hit:
            return {"name": rec.get("name"), "compiled": False,
                    "refused_for": reason, "trigger": hit,
                    "why": (f"the proposal itself says {hit!r}, which means executing it "
                            f"{'regresses an existing gate' if reason == 'regresses_a_gate' else ''}"
                            f"{'narrows what the desk may search' if reason == 'adds_a_quota' else ''}"
                            f"{'costs something it names' if reason == 'names_a_tradeoff' else ''}"
                            f"{'needs data the desk cannot obtain free' if reason == 'needs_paid_data' else ''}"
                            f"{'requires infrastructure work the trial does not pay for' if reason == 'needs_new_infrastructure' else ''}"
                            f". Refused before any trial is spent.")}

    if coordinate in seen:
        return {"name": rec.get("name"), "compiled": False, "refused_for": "duplicate_coordinate",
                "trigger": coordinate,
                "why": (f"{coordinate} is already carried by a CERTIFIED cell. Testing the same "
                        f"claim twice adds no information while charging the trial count every "
                        f"other candidate's bar is computed against.")}

    # TIMIDITY: refuse only when the proposal admits it moves nothing AND names no growth path.
    # Both conditions, because the first alone would reject a modestly-worded proposal carrying a
    # genuinely new mechanism -- and a small INDEPENDENT edge is worth more to E[log W] than a
    # large correlated one.
    has_growth_path = any(w in t for w in _GROWTH_PATH)
    for reason, words in _TIMID.items():
        hit = next((w for w in words if w in t), None)
        if hit and not has_growth_path:
            return {"name": rec.get("name"), "compiled": False, "refused_for": reason,
                    "trigger": hit,
                    "why": (f"says {hit!r} and names no path to geometric growth -- no edge, no "
                            f"independence claim, no information gain. The constitution's sole "
                            f"objective is max E[log W_T]; a proposal that moves it by no path, "
                            f"direct or indirect, is a smaller version of the book the desk "
                            f"already owns and does not earn a trial.")}

    ev = coordinate.split("|")[0] if "|" in coordinate else ""
    attempts = saturation.get(ev, 0)
    if attempts >= _SATURATED_ATTEMPTS:
        return {"name": rec.get("name"), "compiled": False, "refused_for": "saturated_ground",
                "trigger": f"{ev}:{attempts}",
                "why": (f"{ev} already carries {attempts} attempts on this desk. This is a "
                        f"SPENDING decision, not a verdict on the mechanism -- the region may "
                        f"well be real, but one more trial there buys less than the same trial "
                        f"spent where nothing has been measured.")}
    return None


#: Populated by `main` before compiling. Module-level so `compile_proposal` stays a pure
#: single-record function that a test can call directly.
_SATURATION: dict[str, int] = {}
_SEEN: set[str] = set()


def _declared(rec: dict[str, Any], field: str, legal: tuple[str, ...]) -> str | None:
    """The proposal's OWN axis value, when it stated one and that value is legal.

    Inferring an axis from keywords when the record already declares it throws away the only
    unambiguous evidence in the row. Illegal values fall through to inference rather than
    failing, because a generator typo is not a reason to refuse a stated mechanism.
    """
    v = str(rec.get(field) or "").strip().lower().replace(" ", "_")
    return v if v in legal else None


def _match(text: str, table: dict[str, tuple[str, ...]]) -> str | None:
    t = text.lower()
    best, best_hits = None, 0
    for key, words in table.items():
        hits = sum(1 for w in words if w in t)
        if hits > best_hits:
            best, best_hits = key, hits
    return best


def _unsupported(text: str) -> list[str]:
    t = text.lower()
    return [k for k, pats in _UNSUPPORTED_RX.items()
            if any(re.search(p, t) for p in pats)]


def compile_proposal(rec: dict[str, Any], supported: dict[str, list[str]]) -> dict[str, Any]:
    """One proposal -> a runnable cell spec, or a refusal that names what is missing."""
    # Read EVERY field the proposal carries. A fixed list here silently ignored `data_source`
    # and `lens` once the prompt contract changed, and the capability check reads the whole text.
    text = " ".join(str(v) for k, v in rec.items()
                    if k in ("name", "mechanism", "data_source", "payer", "test", "kill",
                             "lens", "event", "context", "direction"))
    missing = _unsupported(text)
    # A VALIDATED DSL TREE WAIVES THE CAPABILITIES IT ACTUALLY EXPRESSES -- and only those.
    # `cross_sectional_rank` and `multi_leg_spread` were refused because family_generic cannot
    # express them, which was true and is why refusing was correct: an approximation would enter
    # the docket as if it were the proposal. libs/research_os/dsl.py CAN express them (rank,
    # spread, ratio, resid), so a proposal that SUPPLIES a tree is no longer approximating -- it
    # is stating the factor exactly, in a language whose 22 operators are checked against an
    # allowlist before any data is touched.
    #
    # NO TREE, NO WAIVER. A proposal that merely mentions "spread between" without supplying one
    # is still refused, because naming a shape is not expressing it. That keeps the refusal
    # queue meaningful: it now lists proposals that need a tree, not capabilities the desk lacks.
    if missing:
        _tree = rec.get("factor")
        if _tree is not None:
            try:
                from libs.research_os.dsl import validate as _dsl_validate

                _dsl_validate(_tree)
                _EXPRESSIBLE = {"cross_sectional_rank", "multi_leg_spread"}
                missing = [m for m in missing if m not in _EXPRESSIBLE]
            except Exception as _exc:
                return {"name": rec.get("name"), "compiled": False,
                        "refused_for": "invalid_factor_tree", "trigger": str(_exc)[:90],
                        "why": (f"the proposal supplied a factor tree the DSL refuses "
                                f"({str(_exc)[:70]}). Refused by name rather than approximated -- "
                                f"the refusal names the operator worth adding.")}
    if missing:
        return {"name": rec.get("name"), "compiled": False, "missing_capability": missing,
                "refused_for": "missing_capability",
                "why": (f"needs {', '.join(missing)}, which family_generic cannot express. "
                        f"Recorded rather than approximated: an approximation would enter the "
                        f"docket as if it were this proposal and the gauntlet would judge "
                        f"something nobody meant to test.")}

    from libs.research.semantic_space import CONTEXTS, DIRECTIONS, EVENTS, OUTPUTS

    event = _declared(rec, "event", EVENTS) or _match(text, _EVENT_WORDS)
    context = _declared(rec, "context", CONTEXTS) or _match(text, _CONTEXT_WORDS)
    direction = _declared(rec, "direction", DIRECTIONS) or _match(text, _DIRECTION_WORDS)
    # Unstated horizon stays "1h" -- the family's own default, and unchanged behaviour. What
    # changes is that a proposal which DOES name its horizon now keeps it instead of being
    # flattened onto 1h and refused as a duplicate of an unrelated hourly claim.
    output = _declared(rec, "output", OUTPUTS) or _match(text, _OUTPUT_WORDS) or "1h"
    if output not in supported["output"]:
        output = "1h"
    unresolved = [n for n, v in (("event", event), ("direction", direction)) if not v]
    if unresolved:
        return {"name": rec.get("name"), "compiled": False, "missing_capability": [],
                "refused_for": "unresolved_axis",
                "why": (f"could not resolve {unresolved} from the proposal text. The axis is the "
                        f"claim: guessing 'continuation' for a mechanism that never said so would "
                        f"test the opposite of the hypothesis half the time.")}

    # NO SILENT DEFAULT. `context = context or "asia"` turned an unresolved axis into a
    # confident specification -- the desk's own law is that absence is never permission, and a
    # compiler that fills in the missing half of a claim is deciding what the hypothesis says.
    # STILL NO SILENT DEFAULT -- but refusal was not the only alternative to guessing. A proposal
    # that names no session makes a claim about every bar, so it compiles to the UNCONDITIONED
    # context and is tested there. `context = context or "asia"` remains forbidden: that would
    # record the result against a session nobody named. This records it against all of them.
    context_declared = context is not None
    if not context:
        context = "unconditioned"

    # MEASUREMENT CONTRACT. A mechanism whose implementation cannot see it does not compile.
    from libs.research.measurement import contract_for

    mc = contract_for(event)
    if mc is not None and not mc.may_run:
        return {"name": rec.get("name"), "compiled": False, "refused_for": "unmeasurable",
                "why": mc.verdict()}

    if event not in supported["event"] or direction not in supported["direction"]:
        return {"name": rec.get("name"), "compiled": False,
                "missing_capability": [f"event:{event}"],
                "why": f"{event}/{direction} is outside family_generic's vocabulary"}

    coordinate = f"{event}|{context}|magnitude|{direction}|{output}"
    veto = _roi_refusal(rec, text, coordinate, _SATURATION, _SEEN)
    if veto is not None:
        return veto
    _SEEN.add(coordinate)

    return {"name": rec.get("name"), "compiled": True,
            "family": "generic",
            "params": {"event": event, "context": context, "direction": direction,
                       "output": output, "quality_atr": 1.0},
            "coordinate": coordinate,
            # Carried onto the cell so every downstream reader knows whether this result may be
            # attributed to the mechanism, or is exploration under its own coordinate only.
            # False means the proposal named no session and is running unconditioned -- a reader
            # must not attribute an unconditioned result to a session-specific mechanism.
            "context_declared": context_declared,
            "measurement_class": mc.measurement_class if mc else "UNKNOWN",
            "attribution_allowed": bool(mc.attribution_allowed) if mc else False,
            "measurement_note": mc.verdict() if mc else "no contract recorded for this event",
            "data_source": rec.get("data_source"), "kill": rec.get("kill"),
            "lens": rec.get("lens"),
            "promotion_authority": False}


def main() -> int:
    from mt5desk.family_generic import supported as generic_supported

    now = datetime.now(tz=UTC)
    sup = generic_supported()

    global _SATURATION, _SEEN
    _SATURATION = _saturation_map()
    _SEEN = _existing_coordinates()

    props: list[dict[str, Any]] = []
    if QUEUE.exists():
        for line in QUEUE.read_text("utf-8").splitlines():
            try:
                props.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    # AUDIT RECOMMENDATIONS BECOME CELLS, NOT PROSE. A named region is enumerated into the same
    # coordinate shape a proposal compiles to, so a recommendation changes where trials go.
    audit_props: list[dict[str, Any]] = []
    try:
        free = json.loads(FREE.read_text("utf-8"))
        for res in free.get("results", []):
            for row in res.get("regions", []) or []:
                region = str(row.get("region", "")).strip()
                m = re.match(r"^([a-z_]+)\s*\|?\s*([a-z_]*)", region.lower())
                if not m:
                    continue
                # ONE COMPILER, NO PRIVILEGED ENTRANCE. This branch used to build the cell
                # itself: it defaulted an unparsed direction to "continuation", hardcoded
                # `context: "asia"`, and set `compiled: True` without ever calling
                # `compile_proposal` -- so it skipped the capability check, the axis resolution,
                # the ROI refusal, the saturation check and the novelty gate in one step.
                #
                # Both of those defaults are the EXACT failures the ordinary path refuses by name
                # thirty lines above: "guessing 'continuation' for a mechanism that never said so
                # would test the opposite of the hypothesis half the time", and "a compiler that
                # fills in the missing half of a claim is deciding what the hypothesis says".
                # Removing them from one entrance while leaving them in another removed nothing.
                #
                # Audit regions now become PROPOSALS and take the same door. Most will be REFUSED
                # for unresolved context, because a region named `event|direction` genuinely does
                # not say when it fires -- and a refusal that names the missing axis is a research
                # finding, where a cell built on a guessed axis is a confident answer to a
                # question nobody asked.
                audit_props.append({
                    "name": f"audit:{region[:48]}",
                    "mechanism": region,
                    "test": str(row.get("why") or row.get("evidence") or ""),
                    "data_source": "named by cold audit; capability checked at compile",
                    "lens": "cold_audit_recommendation",
                    "origin": "cold_audit"})
    except (OSError, json.JSONDecodeError):
        pass

    results = [compile_proposal(p, sup) for p in props + audit_props]
    ok = [r for r in results if r.get("compiled")]
    refused = [r for r in results if not r.get("compiled")]

    print(f"PROPOSAL COMPILER {now.isoformat(timespec='seconds')}")
    print(f"  queue: {len(props)} proposal(s), audit regions: {len(audit_props)} "
          f"(both through the SAME compiler)")
    print(f"  COMPILED {len(ok)}   REFUSED {len(refused)}")
    for r in ok[:10]:
        print(f"    ok   {str(r.get('name'))[:34]:36s} {r['coordinate']}")
    for r in refused[:10]:
        miss = (r.get("refused_for")
                or ",".join(r.get("missing_capability") or [])
                or "axis unresolved")
        print(f"    --   {str(r.get('name'))[:34]:36s} [{miss}]")
        print(f"         {r['why'][:120]}")

    COMPILED.parent.mkdir(parents=True, exist_ok=True)
    COMPILED.write_text(json.dumps({"built_at": now.isoformat(timespec="seconds"),
                                    "cells": ok}, indent=1), "utf-8")
    OUT.write_text(json.dumps({"ran_at": now.isoformat(timespec="seconds"),
                               "compiled": len(ok), "refused": len(refused),
                               "refusals": refused,
                               "missing_capabilities": sorted({m for r in refused
                                                               for m in (r.get("missing_capability")
                                                                         or [])}),
                               "note": ("a refusal names the capability to build next; "
                                        "approximating would put a wrong answer in the docket "
                                        "under the proposal's name")}, indent=1), "utf-8")
    print(f"\n  -> {COMPILED}")
    print(f"  -> {OUT}")
    if refused:
        gaps = sorted({m for r in refused for m in (r.get("missing_capability") or [])})
        if gaps:
            print(f"\n  BUILD LIST (capabilities refusals are waiting on): {gaps}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
