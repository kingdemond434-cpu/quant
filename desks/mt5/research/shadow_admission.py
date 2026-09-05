"""Fail-closed bridge from canonical ten-gate certificates to shadow work."""
from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from pathlib import Path

try:  # package import (tests/library callers) versus direct script execution
    from .gate_policy import all_ten_pass, is_exact_policy
except ImportError:  # pragma: no cover - exercised by production script entrypoints
    from gate_policy import all_ten_pass, is_exact_policy

BASE = Path(__file__).resolve().parent.parent


def _read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


#: The qquant report writes its family as the shorthand "breakout"; the executable family on
#: this desk is "session_range_breakout". That translation is why the old literal was there, and
#: it must survive -- emitting the raw token produces a spec no family function matches, so the
#: sleeve is silently unrunnable. What must NOT survive is the EXCLUSION that sat beside it:
#: every other family was dropped entirely. Normalise known aliases, pass everything else
#: through, exclude nothing.
_FAMILY_ALIASES = {"breakout": "session_range_breakout"}


def _exec_family(name: str) -> str:
    return _FAMILY_ALIASES.get(str(name).casefold(), str(name) or "session_range_breakout")


#: THE ONLY SIDE THE FIVE-TUPLE SPEC CAN EXPRESS -- which is NOT the same question as what the
#: forward engine can run, and conflating the two is what made this constant say something false.
#:
#: WHAT WAS TRUE WHEN THIS WAS WRITTEN AND IS NOT TRUE NOW. It read "THE ONLY SIDE THE FORWARD
#: ENGINE CAN ACTUALLY RUN", justified by "shadow_forward freezes direction=LONG and calls
#: fam_fn(h1, side=1, ...)". Both halves have since been fixed in the engine: `_runnable_side`
#: resolves the certified side, `run_forward` calls `fam_fn(h1, side=-1, ...)` for a short, and
#: the identity is stamped `direction=str(side).upper()`. The engine HAS a short leg. Leaving the
#: old text in place meant every unreachable certificate on the health report was attributed to a
#: cause that no longer exists -- a measurement pointing the reader at code that is already
#: correct, which is worse than no measurement at all.
#:
#: WHAT IS STILL TRUE, AND IS WHY THE DOOR STAYS SHUT. The five-tuple
#: `(symbol, selector, state, family, is_universe)` carries no side at all, and every consumer
#: depends on that shape. So a SHORT certificate admitted here would hash to exactly the same
#: tuple as its LONG twin: a door comparing tuples could not tell the two apart, and a LONG
#: certificate would silently authorise a SHORT clock or the reverse. That is an evidence defect,
#: not a capability one, and deleting the test would not open the door -- it would corrupt the
#: authority set.
#:
#: So the door stays shut for the RIGHT reason, and `unreachable_certificates` now prices the
#: real fix: it says, per blocked certificate, whether the ENGINE could replay it. A cap nobody
#: can see is a cap nobody will ever pay to remove, and a cap misattributed to the wrong cause is
#: one somebody pays to remove in the wrong place.
SPEC_TUPLE_SIDES = frozenset({"LONG"})
#: Historical name, kept because the ceiling test and the health report both read it. Its VALUE
#: is unchanged; only the claim it makes about WHY has been corrected above.
ENGINE_SIDES = SPEC_TUPLE_SIDES

#: Why a certified row could not enrol. One string per cause, so the health
#: report can group by it instead of showing a bare total.
UNREACHABLE_SIDE_NOT_IN_SPEC_TUPLE = (
    "the five-tuple spec carries no side, so admitting this SHORT certificate would collapse it "
    "onto its LONG twin's tuple; the forward engine CAN replay this family short, so the cost is "
    "a missing field in the spec, not a missing short leg -- thread `side` through the spec "
    "tuple, the frozen identity and fam_fn")
UNREACHABLE_ENGINE_CANNOT_REPLAY_SHORT = (
    "the forward engine cannot replay this family short: its constructor either does not resolve "
    "in this lane or takes no `side` parameter, so enrolling it would accrue forward evidence "
    "for the opposite direction under an identity claiming LONG")
#: The pre-2026-09-05 text, kept ONLY so a reader who greps the health archive can find what the
#: old rows meant. Nothing emits it any more; it described an engine that no longer exists.
UNREACHABLE_NO_SHORT_LEG = ("forward engine has no short leg: shadow_forward "
                            "freezes direction=LONG and calls fam_fn(side=1)")


def _engine_can_run(side: str) -> bool:
    """Can the five-tuple spec express a certificate on this side?

    NAMED FOR WHAT IT DECIDES. It gates `authorized_specs`, which returns tuples with no side
    field, so the question it can honestly answer is about the SPEC and never about the engine.
    `engine_can_replay` below asks the engine.
    """
    return str(side or "LONG").upper() in SPEC_TUPLE_SIDES


def engine_can_replay(family: str, side: str) -> bool | None:
    """Could the forward engine actually run this certificate, asked of the ENGINE?

    ASKED, NOT ASSERTED. The answer lives in `shadow_forward`'s own resolver and its own
    signature check, so reading it here means this file cannot drift from what the engine does --
    which is exactly how the previous constant came to describe an engine that had been fixed
    underneath it. Imported lazily because `shadow_forward` imports this module.

    None means the engine could not be asked on this host (import failure, no bars module): an
    unaskable question is reported as unknown, never as a False that would read as a capability
    gap nobody has.
    """
    if str(side or "LONG").upper() != "SHORT":
        return True
    try:
        import shadow_forward as _sf
    except Exception:
        return None
    try:
        fn = _sf._family_fn(str(family))
        return bool(fn is not None and _sf._accepts_side(fn))
    except Exception:
        return None


def _unreachable_cause(family: str, side: str) -> tuple[str, bool | None]:
    """(cause, engine_can_replay) for one certified row the five-tuple door refuses."""
    replay = engine_can_replay(family, side)
    if replay is False:
        return UNREACHABLE_ENGINE_CANNOT_REPLAY_SHORT, replay
    return UNREACHABLE_SIDE_NOT_IN_SPEC_TUPLE, replay


#: THE SCALP LANE'S CERTIFICATES live in the same canon, under `scalp.<candidate>`, minted by
#: `scripts/scalp_gauntlet.py` through the one validator and merged by the canon's one writer.
#: Until they existed, the promoter compared the tuple below against an authority set that
#: could never contain it and had to call the forward clock the lane's certificate. The tuple is
#: the promoter's own historical construction (`("XAUUSD", name, None, "gold_scalp", False)`) and
#: the shape `tests/test_scalp_promotion.py` certifies -- matched exactly, not approximately,
#: because a certificate that hashes differently from the door is a certificate that never opens
#: it, and that is the failure this lane was in.
SCALP_KEY_PREFIX = "scalp."
SCALP_LANE_FAMILY = "gold_scalp"
SCALP_EXEC = "scalp_market"
#: The exact executable the gateway trades through `mt5desk.scalp_exec` -- the six keys
#: `promoter.promote_scalp` writes on a sleeve row. A row missing any of them is not runnable and
#: is refused here rather than guessed at, which is the same rule `authorized_runs` applies to
#: H1 params.
SCALP_RECIPE_KEYS = ("timeframe", "family", "session", "stop_atr", "target_atr", "max_hold")


def scalp_spec(symbol: str, candidate: str) -> tuple[str, str, str | None, str, bool]:
    """The five-tuple the promoter compares for a scalp sleeve.

    Symbol, the candidate name as selector, no condition, the LANE family (not the mechanism --
    the recipe's `anti_donchian_breakout` is carried on the run row, not here), not-universe.
    """
    return (str(symbol), str(candidate), None, SCALP_LANE_FAMILY, False)


def scalp_certificates(universal: dict) -> dict[str, dict]:
    """candidate name -> canon row, for every `scalp.*` row that is an exact ten-gate pass under
    the exact attestation and carries the complete recipe. Fail closed on every other shape."""
    out: dict[str, dict] = {}
    if not is_exact_policy(universal.get("gate_policy")):
        return out
    survivors = universal.get("survivors")
    if not isinstance(survivors, dict):
        return out
    for key, row in survivors.items():
        name = str(key)
        if not name.startswith(SCALP_KEY_PREFIX):
            continue
        if not isinstance(row, dict) or not all_ten_pass(row.get("gates")):
            continue
        spec = row.get("shadow_spec")
        if not isinstance(spec, dict) or not {"symbol", *SCALP_RECIPE_KEYS} <= set(spec):
            continue
        out[name[len(SCALP_KEY_PREFIX):]] = row
    return out


def authorized_specs(base: Path = BASE) -> set[tuple[str, str, str | None, str, bool]]:
    """Return exact executable specs certified under the original policy only.

    Legacy qquant session rows are reconstructible from REAL_SURVIVORS. Newer
    universal survivors must publish an explicit ``shadow_spec``; guessing lost
    parameters from a display cell name is forbidden.
    """
    reports = base / "reports"
    out: set[tuple[str, str, str | None, str, bool]] = set()

    qquant = _read(reports / "QQUANT_GATES.json")
    if is_exact_policy(qquant.get("gate_policy")):
        for row in qquant.get("verdicts", []):
            if not isinstance(row, dict) or row.get("passed") is not True:
                continue
            if not all_ten_pass(row.get("stages")):
                continue
            parts = str(row.get("id") or "").split()
            if len(parts) != 5:
                continue
            symbol, family, side, selector, condition = parts
            # NO FAMILY WHITELIST, and the family is CARRIED rather than asserted. This dropped
            # every certified row whose family was not "breakout", and then wrote the literal
            # "session_range_breakout" into the spec regardless -- so a certificate for any other
            # mechanism was either discarded or relabelled as something it is not. Both are the
            # same defect: a door that only one family can walk through cannot diversify a book,
            # and diversification is the binding constraint here.
            # The guards that matter are unchanged and do the real work: is_exact_policy on the
            # report, and all_ten_pass on the row. Only genuinely certified rows reach this line.
            if not _engine_can_run(side):
                continue                    # counted by unreachable_certificates; see ENGINE_SIDES
            state = None if condition.upper() in {"NONE", "ALL", "UNCONDITIONED"} else condition
            out.add((symbol, selector, state, _exec_family(family), False))

    # Compatibility rows are accepted only when they carry the same complete
    # policy attestation; they cannot bypass or strengthen the QQUANT authority.
    real = _read(reports / "REAL_SURVIVORS.json")
    for row in real.get("real_survivors", []):
        if not isinstance(row, dict) or row.get("REAL3") is not True:
            continue
        cert = row.get("qquant_gates") or {}
        if not is_exact_policy(cert.get("policy")) or not all_ten_pass(cert.get("stages")):
            continue
        # Normalise the alias, exclude nothing, and CARRY the family into the spec instead of
        # asserting a literal. This dropped every certified compatibility row outside one family
        # and then wrote "session_range_breakout" regardless, so a certificate for any other
        # mechanism was either discarded or relabelled as something it is not.
        family = str(row.get("fam") or "SESSION_RANGE_BREAKOUT")
        if not _engine_can_run(str(row.get("side") or "LONG")):
            continue                        # counted by unreachable_certificates; see ENGINE_SIDES
        state = row.get("state") or None
        out.add((str(row["sym"]), str(row["win"]), state, _exec_family(family), False))

    universal = _read(reports / "UNIVERSAL_SURVIVORS.json")
    if is_exact_policy(universal.get("gate_policy")):
        for key, row in universal.get("survivors", {}).items():
            if str(key).startswith(SCALP_KEY_PREFIX):
                # The scalp lane's rows carry the mechanism as `family`; read through the
                # generic branch they would mint a tuple no door compares. They are admitted
                # below, in the lane's own shape.
                continue
            if not isinstance(row, dict) or not all_ten_pass(row.get("gates")):
                continue
            spec = row.get("shadow_spec")
            if not isinstance(spec, dict):
                continue
            required = {"symbol", "selector", "family", "is_universe"}
            if not required <= set(spec):
                continue
            out.add((str(spec["symbol"]), str(spec["selector"]),
                     spec.get("condition") or None, str(spec["family"]),
                     spec["is_universe"] is True))
        for candidate, row in scalp_certificates(universal).items():
            out.add(scalp_spec(row["shadow_spec"]["symbol"], candidate))
    return out


def unreachable_certificates(base: Path = BASE) -> dict:
    """Certificates that passed all ten gates and STILL cannot enrol, and why.

    THE GAP THIS MEASURES. `authorized_specs` answers "what may run". Nothing
    answered "what passed everything and runs anyway". The difference is the
    desk's real enrolment ceiling, and it was invisible: a certified SHORT row
    hit a bare `continue` in two of the three sources and left no trace, so a
    reader comparing "63 certified" against "57 enrolled" had no way to learn
    whether the six were a bug, a queue, or a wall.

    IT IS DELIBERATELY NOT A DOOR. This function admits nothing and changes no
    behaviour; `authorized_specs` is untouched in what it returns. It exists so
    the ceiling is a NUMBER on the health report rather than a discrepancy
    somebody has to notice. A restriction nobody can see is a restriction nobody
    will ever pay to remove -- and the fix here is real work (thread `side`
    through the spec tuple, the frozen identity and `fam_fn`), so it needs a
    price before it can be ranked against anything else.

    UNREADABLE IS NOT ZERO. A report that fails `is_exact_policy`, or does not
    parse, contributes `None` to its source rather than 0: "no certificates are
    blocked" and "I could not read the certificates" are opposite facts and the
    desk has shipped that confusion before.
    """
    reports = base / "reports"
    blocked: list[dict] = []
    readable: dict[str, bool] = {}

    qquant = _read(reports / "QQUANT_GATES.json")
    readable["QQUANT_GATES"] = bool(qquant) and is_exact_policy(qquant.get("gate_policy"))
    if readable["QQUANT_GATES"]:
        for row in qquant.get("verdicts", []):
            if not isinstance(row, dict) or row.get("passed") is not True:
                continue
            if not all_ten_pass(row.get("stages")):
                continue
            parts = str(row.get("id") or "").split()
            if len(parts) != 5:
                continue
            symbol, family, side, selector, _condition = parts
            if _engine_can_run(side):
                continue
            cause, replay = _unreachable_cause(_exec_family(family), side)
            blocked.append({"source": "QQUANT_GATES", "symbol": symbol,
                            "family": _exec_family(family), "side": side.upper(),
                            "selector": selector, "cause": cause,
                            "engine_can_replay": replay})

    real = _read(reports / "REAL_SURVIVORS.json")
    readable["REAL_SURVIVORS"] = bool(real)
    if readable["REAL_SURVIVORS"]:
        for row in real.get("real_survivors", []):
            if not isinstance(row, dict) or row.get("REAL3") is not True:
                continue
            cert = row.get("qquant_gates") or {}
            if not is_exact_policy(cert.get("policy")) or not all_ten_pass(cert.get("stages")):
                continue
            side = str(row.get("side") or "LONG")
            if _engine_can_run(side):
                continue
            fam = _exec_family(str(row.get("fam") or ""))
            cause, replay = _unreachable_cause(fam, side)
            blocked.append({"source": "REAL_SURVIVORS", "symbol": str(row.get("sym") or "?"),
                            "family": fam,
                            "side": side.upper(), "selector": str(row.get("win") or "?"),
                            "cause": cause, "engine_can_replay": replay})

    by_cause: dict[str, int] = {}
    for row in blocked:
        by_cause[row["cause"]] = by_cause.get(row["cause"], 0) + 1
    # THE PRICE OF THE FIX, AS A NUMBER. A certificate the ENGINE can already replay is blocked
    # only by the missing side field in the five-tuple: threading `side` through the spec, the
    # frozen identity and fam_fn recovers exactly these, with no gate touched and no new
    # evidence required. The rest need the family itself to learn a side, which is real work and
    # a different job. Separating them is what makes either one rankable.
    recoverable = sum(1 for r in blocked if r.get("engine_can_replay") is True)
    unaskable = sum(1 for r in blocked if r.get("engine_can_replay") is None)
    return {"n": len(blocked) if any(readable.values()) else None,
            "sources_readable": readable,
            "by_cause": by_cause,
            # What the FIVE-TUPLE can express -- the thing this door actually tests.
            "spec_tuple_sides": sorted(SPEC_TUPLE_SIDES),
            "engine_sides": sorted(SPEC_TUPLE_SIDES),
            "recoverable_by_threading_side": recoverable,
            "engine_replay_unaskable_here": unaskable,
            "certificates": blocked}


def partition_work(
    declared: Iterable[tuple[str, str, str | None, str, bool]],
    base: Path = BASE,
) -> tuple[list[tuple[str, str, str | None, str, bool]],
           list[tuple[str, str, str | None, str, bool]]]:
    authority = authorized_specs(base)
    admitted, blocked = [], []
    for spec in declared:
        (admitted if spec in authority else blocked).append(spec)
    return admitted, blocked

def power_cure_specs(base: Path = BASE) -> set[tuple[str, str, str | None, str, bool]]:
    """Specs that failed ONLY power gates -- admissible once forward evidence cures them.

    THE POLICY HAD NO INSTRUMENT (L1.46). gate_spec.yaml states `power_cure_via_forward: true`
    and classifies five gates as POWER (in_sample_screen, deflated_sharpe, cpcv, walk_forward,
    expected_value) versus five as VALIDITY (economic_prior, pbo, reality_check_spa,
    stress_costs, lockbox), with VALIDITY a hard fail. That is the whole reason 36 sleeves sit
    on forward clocks: they cleared every validity gate and missed on deflated Sharpe, which
    forward evidence is explicitly allowed to settle.

    But `authorized_specs` only ever admitted EXACT ten-gate certificates -- so a sleeve could
    complete the cure the policy promised and still be refused at the door, forever. The cure
    was unreachable, which makes it a wish rather than a rule. This function is the missing
    instrument: it returns the power-cure-eligible specs, and the PROMOTER (not this file)
    applies the forward thresholds before anything is promoted.
    """
    from gate_policy import is_exact_policy
    reports = base / "reports"
    out: set[tuple[str, str, str | None, str, bool]] = set()
    # CLASSIFICATIONS FROM THE SPEC, WITH FALLBACKS. The desk box runs a different branch whose
    # gate_policy predates get_validity_gates/get_power_gates, so importing them unconditionally
    # turned a policy improvement into an ImportError that killed the entire promoter run. A
    # capability that works only on one box's revision is not deployed. Read the spec when the
    # helpers are missing, the canonical literal when even the spec cannot be read, and FAIL
    # SOFT: a promoter that cannot classify skips the cure path, never aborts promotion.
    try:
        from gate_policy import get_power_gates, get_validity_gates
        validity, power = get_validity_gates(), get_power_gates()
    except ImportError:
        try:
            import yaml
            spec = yaml.safe_load((base / "policy" / "gate_spec.yaml").read_text("utf-8"))
            cls = spec.get("gate_classifications", {})
            validity = frozenset(cls.get("validity", ()))
            power = frozenset(cls.get("power", ()))
        except Exception:
            validity = frozenset({"economic_prior", "pbo", "reality_check_spa",
                                  "stress_costs", "lockbox"})
            power = frozenset({"in_sample_screen", "deflated_sharpe", "cpcv",
                               "walk_forward", "expected_value"})
    if not validity or not power:
        return out
    qq = _read(reports / "QQUANT_GATES.json")
    if not is_exact_policy(qq.get("gate_policy")):
        return out
    for r in qq.get("verdicts", []):
        stages = r.get("stages") if isinstance(r, dict) else None
        if not isinstance(stages, dict):
            continue
        # VALIDITY IS ABSOLUTE: one validity miss and the cell is DEAD, never cured.
        if not all(isinstance(stages.get(g), dict) and stages[g].get("passed") is True
                   for g in validity):
            continue
        # and it must actually be a POWER failure -- a full pass belongs to authorized_specs.
        failed_power = [g for g in power
                        if not (isinstance(stages.get(g), dict)
                                and stages[g].get("passed") is True)]
        if not failed_power:
            continue
        parts = str(r.get("id") or "").split()
        if len(parts) != 5:
            continue
        symbol, family, _side, selector, condition = parts
        # No whitelist here either -- the cure lane must be open to every mechanism that clears
        # the validity gates, which is the entire point of curing by forward evidence.
        state = None if condition.upper() in {"NONE", "ALL", "UNCONDITIONED"} else condition
        out.add((symbol, selector, state, _exec_family(family), False))

    # THE EXTERNAL LANE, which had no route at all. The qquant report above is one producer; the
    # gauntlet publishes its own validity-pass, power-deficient cells to POWER_CURE_CANDIDATES
    # with an EXACT executable shadow_spec (never a guessed selector). Certificates stay in
    # UNIVERSAL_SURVIVORS; these rows carry no promotion authority, and the promoter still
    # applies the forward cure thresholds before anything is promoted.
    # Measured 2026-08-29 -- 615 candidates across EIGHT families (cross_asset_residual 140,
    # session_range_breakout 96, overnight_gap_decay 79, relative_value 73, carry 72, ...), 598
    # of them failing deflated_sharpe alone. Without this block admission saw 68, all of one
    # family, which is what a cure lane looks like when only one producer can reach it.
    cure = _read(reports / "POWER_CURE_CANDIDATES.json")
    if is_exact_policy(cure.get("gate_policy")):
        for row in (cure.get("candidates") or {}).values():
            if not isinstance(row, dict) or row.get("validity_pass") is not True:
                continue
            if not row.get("failed_power_gates"):
                continue
            spec = row.get("shadow_spec")
            if not isinstance(spec, dict):
                continue
            if not {"symbol", "selector", "family", "is_universe"} <= set(spec):
                continue
            out.add((str(spec["symbol"]), str(spec["selector"]),
                     spec.get("condition") or None, _exec_family(spec["family"]),
                     spec["is_universe"] is True))
    return out


#: Certificates that passed all ten gates and were still dropped before enrolment, with the
#: reason. Reset at the start of every `authorized_runs` call so it always describes the LAST
#: pass rather than accumulating across a long-lived process.
#:
#: Exposed as module state, not just printed, because the two readers need different things: the
#: shadow log needs a line a human greps at 3am, and `same_day_enrolment` needs to be able to say
#: WHY a certificate it is flagging has no clock instead of only that it has none.
DROPPED_CERTIFICATES: list[dict[str, str]] = []


def _drop(name: object, why: str) -> None:
    """Record and announce a ten-gate certificate that will not reach the forward engine.

    Printed to stderr rather than through a logging framework because this module is imported by
    the forward engine, the promoter and three scripts, and it has never carried a logger; stderr
    is what the VPS's own cron redirection already captures for all of them. The prefix matches
    `shadow_forward`'s ENROL-GAP lines on purpose, so both halves of the same failure grep
    together.
    """
    line = f"ENROL-GAP: certified {name} dropped before enrolment -- {why}"
    DROPPED_CERTIFICATES.append({"certificate": str(name), "why": why})
    print(line, file=sys.stderr, flush=True)


#: The canon, in the order it is trusted. THE GAUNTLET'S FRESH REPORT FIRST, THE SEALED CANON
#: SECOND -- and the second entry is the whole point of this tuple.
#:
#: MEASURED 2026-09-05, and it is the largest silent stop on the desk. `authorized_runs` read
#: `reports/UNIVERSAL_SURVIVORS.json` and nothing else. That file is the external gauntlet's
#: OUTPUT, so when the gauntlet fails the file is stale or absent -- and an absent file reads as
#: `gate_policy = None`, which trips the whole-canon policy refusal and returns ZERO authorized
#: runs. Not "the newest certificates cannot enrol": NOTHING can enrol, including certificates
#: that passed all ten gates days earlier and are sitting in the sealed canon with a valid
#: attestation.
#:
#: The dashboard was showing exactly that shape and it read as four unrelated faults:
#:     GAUNTLET: canon last swept 60.8h ago ... the desk gauntlet or the cert pull stopped
#:     healed: FAILING MT5-Gauntlet: last result 1
#:     CERTIFIED-NOT-ENROLLED: external.USDZAR.overnight_gap_decay ... 91 hours ago, no clock
#:     CERTIFIED-NOT-ENROLLED: external.AUDCHF / CADCHF / GBPCHF ... 117-142 hours, no clock
#: One cause: the gauntlet crashes, its report goes missing, and enrolment silently drops to zero
#: for every certificate the desk has ever earned.
#:
#: THIS IS NOT A LOOSENING, and the distinction is exact. `is_exact_policy` still runs on whatever
#: file is used, and `all_ten_pass` still runs per row -- a canon without the exact ten-gate
#: attestation is still refused whole. What changes is WHICH ARTIFACT carries the attestation: the
#: sealed `data/UNIVERSAL_SURVIVORS.canon.json` is the same certificates under the same policy,
#: dated, and it is already what the promoter, the allocator and `alpha_genome` read as the canon.
#: Enrolling on the last sealed canon while the gauntlet is down is strictly better than enrolling
#: nothing, and it is the same evidence either way.
CANON_SOURCES: tuple[tuple[str, str], ...] = (
    ("reports/UNIVERSAL_SURVIVORS.json", "the gauntlet's latest sweep"),
    ("data/UNIVERSAL_SURVIVORS.canon.json", "the last SEALED canon"),
)


def _canon(base: Path) -> tuple[dict, str]:
    """(canon document, where it came from). Prefers the fresh sweep, falls back to the seal.

    A source is used only if it carries the exact ten-gate attestation, so the fallback cannot
    admit anything the primary would have refused -- it can only find the same certificates in
    the artifact that still has them.
    """
    first: dict = {}
    for rel, what in CANON_SOURCES:
        doc = _read(base / rel)
        if not first:
            first = doc
        if is_exact_policy(doc.get("gate_policy")):
            return doc, f"{rel} ({what})"
    return first, CANON_SOURCES[0][0]


def authorized_runs(base: Path = BASE,
                    lanes: tuple[str, ...] = ("h1", "scalp")) -> list[dict]:
    """Exactly-specified RUNNABLE certificates: symbol, selector, family AND certified params.

    `lanes` names which engines' rows to return. H1 rows are what `shadow_forward` enrols; scalp
    rows (`scalp.*` keys, `exec == "scalp_market"`) carry the recipe `mt5desk.scalp_exec` trades
    and belong to `scalp_shadow`'s clock. Both are returned by default so a reader that counts
    certificates counts all of them; an H1-only consumer passes `lanes=("h1",)`, or skips rows
    whose `exec` names an executor it is not.

    WHY THIS EXISTS ALONGSIDE `authorized_specs`. That function answers "is this cell allowed?"
    and its five-tuple deliberately has no params -- every existing consumer depends on that
    shape. This one answers a different question the forward engine actually needs: "what,
    precisely, do I run?" Measured 2026-08-26: 21 certificates collapsed to 6 five-tuples, so
    five separately-gauntleted XAUUSD parameterizations became one clock executing the engine's
    own default (rr=2.0). Four certified strategies were therefore never forward-tested while
    still being counted as certificates.

    A certificate WITHOUT `params` is not returned. It cannot be: running it means guessing the
    parameterization that passed, and `authorized_specs`' own rule is that reconstructing lost
    parameters from a display name is forbidden. Those rows are re-certified with params by the
    next daily gauntlet pass rather than run on a guess.
    """
    # Cleared BEFORE the policy early-return, not after: a pass that refuses the whole canon on a
    # policy mismatch must not leave the previous pass's drops standing as if they were this
    # pass's findings. This list always describes the run that just happened, never a backlog.
    DROPPED_CERTIFICATES.clear()
    universal, canon_from = _canon(base)
    if not is_exact_policy(universal.get("gate_policy")):
        # THE LARGEST SILENT DROP OF ALL, and this desk has already paid for it once.
        # `is_exact_policy`'s own docstring records 2026-09-02: "this is the whole reason the desk
        # had no new forward clocks. Sixty-three certificates passed all ten gates and carried a
        # valid shadow_spec, and `authorized_specs` returned ZERO." A policy mismatch refuses the
        # ENTIRE canon in one line, and it did it without saying anything -- so the symptom was
        # "no new clocks" and the cause was invisible in every log and artifact.
        #
        # Reported by name now, with the count of what was refused, so the same outage announces
        # itself instead of being re-diagnosed from first principles a second time.
        n = len(universal.get("survivors") or {})
        _drop(f"<entire canon: {n} survivor row(s)>",
              f"NO canon on this tree carries the exact ten-gate attestation. Tried, in order: "
              f"{', '.join(rel for rel, _ in CANON_SOURCES)}. The last read carried "
              f"{universal.get('gate_policy')!r}; every certificate is refused together, so "
              f"NOTHING can enrol until one of those artifacts is re-minted under the exact "
              f"policy. If the gauntlet is failing, the SEALED canon is the one to check first")
        return []
    runs: list[dict] = []
    for name, row in (universal.get("survivors") or {}).items():
        if str(name).startswith(SCALP_KEY_PREFIX):
            continue                       # a scalp recipe is not an H1 parameterization
        if "h1" not in lanes:
            continue
        if not isinstance(row, dict) or not all_ten_pass(row.get("gates")):
            continue                       # not certified: no clock is owed, nothing to report
        # PAST THIS LINE EVERY ROW HAS PASSED ALL TEN GATES, so every remaining `continue` drops a
        # CERTIFICATE -- and until 2026-09-05 all of them dropped it SILENTLY.
        #
        # THE DEFECT, off the live dashboard. Four certificates (USDZAR, AUDCHF, CADCHF and
        # GBPCHF on overnight_gap_decay) sat CERTIFIED-NOT-ENROLLED for 89, 115, 139 and 139
        # hours. `shadow_forward.certified_sleeves` logs an ENROL-GAP line for every refusal it
        # makes -- but it can only refuse what it is HANDED, and a certificate dropped here never
        # reaches it. So the same-day fence reported the breach correctly and the reason for it
        # existed nowhere: not in the shadow log, not in an artifact, not on the dashboard. The
        # operator sees "certified 139 hours ago, no clock" and has nothing to act on.
        #
        # This is the exact failure `certified_sleeves` names in its own comment -- "a silent skip
        # is indistinguishable from enrolment that works" -- committed one function upstream of
        # the place that took care to avoid it. Certification and enrolment are one act
        # (RESEARCH §6d); a door that closes without saying so breaks that law quietly.
        spec = row.get("shadow_spec")
        if not isinstance(spec, dict):
            _drop(name, "carries no `shadow_spec`, so there is nothing to enrol from -- the "
                        "publisher wrote a certificate without the specification that makes it "
                        "runnable")
            continue
        params = spec.get("params")
        if not isinstance(params, dict):
            # `{}` is NOT this case: an empty dict is the complete parameterization "family
            # defaults", byte-exactly what the gauntlet executed, and excluding it once already
            # held two overnight_gap_decay certificates un-enrolled (2026-08-27). Only a params
            # that is absent or not a mapping lands here.
            _drop(name, f"`shadow_spec.params` is {type(params).__name__}, not a mapping -- "
                        f"unrunnable without guessing the parameterization that passed")
            continue
        # {} is NOT "lost parameters": it is the complete parameterization "family defaults",
        # byte-exactly what the gauntlet executed (build_cell with params={}) and what the
        # p=<hash-of-empty> cell identity certifies. Excluding it kept both overnight_gap_decay
        # certificates CERTIFIED-NOT-ENROLLED while the same-day fence flagged them (2026-08-27).
        runs.append({
            "certificate": name,
            "symbol": str(spec["symbol"]), "selector": str(spec["selector"]),
            "family": str(spec.get("family") or "session_range_breakout"),
            "condition": spec.get("condition") or None,
            "params": dict(params),
            # THE SIDE THE CERTIFICATE WAS EARNED ON, CARRIED RATHER THAN ASSUMED.
            #
            # `survivor_publication._shadow_spec` has been writing `side` into every
            # published spec, straight off the certificate id -- and this reader
            # dropped it on the floor. The forward engine then stamped
            # direction="LONG" on the clock and replayed `fam_fn(side=1)`, so a
            # certified SHORT strategy accrued forward evidence for the OPPOSITE
            # direction under an identity claiming it was LONG all along.
            #
            # That is protocol rule 4 exactly: the side gate held at
            # `authorized_specs` and was absent here, and this -- not that one --
            # is the door the engine actually walks through.
            #
            # None means the spec predates the field. It is NOT silently read as
            # LONG here; `side_basis` carries the distinction to the engine, which
            # decides, and the identity records which of the two it was.
            "side": (str(spec["side"]).upper() if spec.get("side") else None),
            "side_basis": "declared" if spec.get("side") else "undeclared",
        })
    if "scalp" in lanes:
        for candidate, row in scalp_certificates(universal).items():
            spec = row["shadow_spec"]
            runs.append({
                "certificate": f"{SCALP_KEY_PREFIX}{candidate}",
                "symbol": str(spec["symbol"]), "selector": str(candidate),
                # the MECHANISM, which is what the executor needs; the lane family
                # (`gold_scalp`) is the tuple's business, see `scalp_spec`
                "family": str(spec["family"]), "condition": None,
                "params": {k: spec[k] for k in SCALP_RECIPE_KEYS},
                "side": str(spec.get("side") or "BOTH").upper(),
                "side_basis": "declared" if spec.get("side") else "undeclared",
                "exec": SCALP_EXEC, "lane": "scalp", "timeframe": str(spec["timeframe"]),
            })
    return runs


def run_key(run: dict) -> str:
    """The clock key for an authorized run -- DELEGATED to the engine that writes the ledger.

    THIS FUNCTION USED TO BUILD ITS OWN KEY, and it built a different one. It returned
    `AUDCHF.asia#` where the forward engine's `sleeve_key` writes `AUDCHF.overnight_gap_decay.asia`
    -- a different shape (family omitted), a different signature rule (every param, rather than
    only those differing from the window default) and a trailing `#` on empty params. Two builders
    for one identity, in the two modules that must agree about which clock is which.

    It survived because NOTHING IN PRODUCTION CALLED IT. The disagreement was real from the day it
    was written and cost nothing until something finally compared authorized runs against the
    ledger, at which point it reported 34 of 35 certificates as having no clock -- every one of
    them running. An orphaned function is not harmless; it is a wrong answer waiting for its first
    caller, and this desk has now been given that wrong answer twice.

    The engine's key is canonical because the engine writes the file. Imported lazily for the same
    reason `shadow_forward` imports THIS module lazily: they need each other and neither may own
    the other's import time.
    """
    # Reachable both ways: the box runs this with `desks/mt5/research` on sys.path, while checks
    # on the VPS import it as `research.shadow_admission`. A single-form import works in whichever
    # context its author happened to test and fails in the other.
    try:
        from shadow_forward import sleeve_key
    except ImportError:
        from research.shadow_forward import sleeve_key  # type: ignore[no-redef]

    # SIDE IS PART OF THE IDENTITY, so it is part of the key. This function exists
    # precisely because two builders for one identity disagreed once already and
    # reported 34 of 35 certificates as clockless while every one of them ran; a
    # short clock whose key here omitted the side would recreate that exact split.
    return sleeve_key(run["symbol"], run["selector"], run.get("params") or {},
                      run.get("family") or "session_range_breakout",
                      run.get("side") or "LONG")
